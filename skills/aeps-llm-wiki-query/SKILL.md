---
name: aeps-llm-wiki-query
description: 用户提问,从 knowledge/ 做规模探查与 4 跳扫描找答案,每条断言附 wikilink 不编造;满足 G11 gating 才询问落档为 analysis 页
plugin-version: 0.6.8
allowed-tools: Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/query/count-pages.js *),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/query/gating-check.js *),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/query/comparison-counter.js *),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/query/append-log.js *),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/check-qmd.js *),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/gen-page.js *),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/aggregate-index.js *)
---

## 脚本路径约定

- 本 skill 所有 `node scripts/xxx.js` 命令以 `${CLAUDE_PLUGIN_ROOT}` 为 plugin 根;该变量由调用方注入(plugin 自动注入或用户 shell 导出)。
- 脚本均在 plugin 仓根的 `scripts/` 下,**不**在 `skills/<skill>/scripts/` 下。
- query 脚本(`scripts/query/*.js`)与 `gen-page.js` 用 `--project <用户工程根绝对路径>` 显式指定工程根,**必须显式传**(脚本内 `import.meta.dirname` 解析 plugin 路径,不依赖 cwd;用户工程根绝无默认值)。
- `scripts/check-qmd.js` 只探查本机 qmd CLI,不需要 `--project`。
- 所有脚本 `--json` 时输出结构化 JSON 到 stdout,诊断/进度到 stderr;SKILL.md 用 `JSON.parse` 解析 stdout。exit code:0 成功 / 1 用法或环境错误 / 2 数据校验 FAIL。

# /aeps-llm-wiki-query

用户提问,plugin 从 `knowledge/` 里找答案:wiki 规模探查 → 引擎分流(index + 4 跳 / qmd)→ intent 三档路由 → 4 跳扫描组织回答(每条断言附 `[[wikilink]]`,不编造)→ G11 gating 判定 → 满足才询问落档为 `analyses/{timestamp}-{slug}.md` + log `**Creation**` 行 + index 刷新。

## 触发

用户跑 `/aeps-llm-wiki-query {question}`(必带一个自然语言问句)。

## 设计原则(必读)

- **不编造**(AC-3):回答只基于阶段 2-5 实际读过的 wiki 页;未覆盖 → 答"我读到的 wiki 里没有覆盖这点"。
- **wikilink 主推裸文件名**(PRD Q9):每条断言附 `[[filename]]`(目标 .md 去 .md 的 basename);标准 markdown 链接仅作兼容降级。
- **LLM 不做算术**:字数阈值比较 / 命中页计数 / 子目录去重全部由 `gating-check.js` 机械判定,intent 由 LLM 语义判断后传入。
- **拍板门强制**:落档 analysis / 建常驻 comparison 页 / prefer-qmd 降级,全部必须用户明确同意,脚本与 LLM 均不静默决定。
- **qmd 三档分流**(design §7.6,唯一阈值升级条款):< 500 页纯 index + 4 跳不调 qmd;500-1000 页优先 qmd,未装提示降级;> 1000 页必须 qmd,未装报错退出(G-Q2,不降级)。
- **计数仅在拍板后更新**:comparison 计数器只在 intent=comparison 且用户拍板落档后 +1(implement-query.md v0.1.0 冻结语义);拒绝落档不计数。

## 编排流程(对齐 PRD §4.3 流程表步骤 0-11.5)

### 步骤 0:wiki 规模探查(阻塞)

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/query/count-pages.js --project <用户工程根> --json
```

读 stdout JSON:`pages` / `scale`(small|medium|large)/ `engine`(index|prefer-qmd|require-qmd)/ `qmd_required`。

- `engine == "index"`(< 500 页)→ 不调 qmd,直接进入步骤 1。
- `engine == "require-qmd"`(> 1000 页)→ 必须探查 qmd:

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/check-qmd.js --json
```

  - `available == false` → **报错退出**(G-Q2,design §7.6 唯一阈值升级条款,不降级),提示用户安装 qmd 后重试。
  - `available == true` → 进入步骤 1,步骤 2 用 qmd 检索。
- `engine == "prefer-qmd"`(500-1000 页)→ 探查 qmd;`available == true` → 步骤 2 用 qmd;`available == false` → **拍板门**:装 qmd / 降级 index(降级需用户确认)。

### 步骤 1:intent 路由(阻塞,LLM 判定)

LLM 对 `{question}` 推断 intent 三档:

| 档 | 含义 | 落档 |
|---|---|---|
| `exact` | 纯事实查证(某参数值 / 某条引用在第几页) | gating 必跳过 |
| `ambiguous` | 语义模糊 fallthrough | 回答但**永不落档** |
| `overview` / `comparison` / `other` | 全局方案评估 / X vs Y 对比 / 其他 | 由步骤 8 gating 判定 |

路径 C 触发词(`vs` / `对比` / `区别` / `异同` / `优缺点` / `X vs Y` 型对象对)**仅作推断辅助**,不替代语义判断;ambiguous fallthrough 不因含触发词而改变(PRD §4.3 Intent 路由)。

### 步骤 2:第 1 跳 — index + tags 关键词过滤(非阻塞)

- `engine == "index"`(< 500 页):读 `knowledge/index.md`,按问句关键词 + 行尾 tags 过滤候选页(index.md 每行尾渲染灰色 `#tag`,grep 数据源)。
- 500-1000 页且 qmd 已装:`qmd query "{question}"` 检索候选;调用失败 → 降级 index.md 检索并告知用户(medium 档允许降级)。
- 产出:候选页相对路径列表(相对 `knowledge/`)。

### 步骤 3:第 2 跳 — 读候选页 frontmatter(非阻塞)

优先级:`description` / `summary` → `title` → 全文。二进制源页(pptx/docx/pdf 等)经 frontmatter `converted_path` 直读 `raw/` 下的 `.converted.md` 副本。

### 步骤 4:第 3 跳 — wikilink 1 跳深邻居(非阻塞)

沿候选页正文 `[[wikilink]]` / 关联导引节,1 跳深度读 `entities/` `concepts/` `analyses/` `comparisons/` 邻居页。**只跳 1 跳,不递归展开**。

### 步骤 5:第 4 跳 — glossary 消歧 + log 近期记录(非阻塞)

读 `knowledge/glossary.md`(同名词消歧)+ `knowledge/log.md` 近期 10 条(了解最近 ingest / query 活动,避免重复落档)。

### 步骤 6:组织回答(阻塞)

每条断言附 `[[wikilink]]` 裸文件名;综合页 / 对照页优先引用(`[[syntheses/...]]` 类常驻页)。回答组织完全由 LLM 决定结构,不锁模板。

### 步骤 7:诚实声明(阻塞)

- 只基于阶段 2-5 实际读过的页回答,不编造 wiki 里没有的内容。
- 未覆盖 → 明确回答"我读到的 wiki 里没有覆盖这点"(该字样触发步骤 8 的 `--not-covered`)。

### 步骤 8:G11 gating 判定 + comparison 计数器提议(阻塞)

LLM 准备机械量(intent 来自步骤 1;字数按**空白分词 + CJK 字符逐字计数**口径统计回答;hit-pages = 阶段 2-5 实际读过的 wiki 页相对路径,逗号分隔;回答含"未覆盖"声明 → 加 `--not-covered`):

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/query/gating-check.js \
  --intent <overview|comparison|exact|ambiguous|other> \
  --answer-words <回答字数> \
  --hit-pages "<path1,path2,...>" [--not-covered] --json
```

读 stdout JSON:

- `should_ask == true`(triggers 任一命中且 skips 全不命中)→ 询问用户是否落档为 analysis 页。
- `should_ask == false` → 不询问,跳过步骤 9-11;若用户主动要求落档,按用户指示执行步骤 9 起。

同时读 comparison 计数器:

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/query/comparison-counter.js read --project <用户工程根> --json
```

`should_propose == true`(累计 ≥ 3 次 comparison 落档)且本次将落档 → 落档询问时**加问**是否建常驻 comparison 页(PRD §4.6 路径 B;`themes[]` 列出历史主题供用户参考)。

### 步骤 9:建 analysis 页 skeleton(用户同意后,阻塞)

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/gen-page.js --project <用户工程根> \
  --type analysis --slug {YYYYMMDD-HHMMSS}-{短横线slug} \
  --answer-to "{原问句}" \
  --sources-used "<逗号分隔的 wiki 页相对路径>" \
  --summary "<首行 **问题**: {原问句},余下 ≤ 280 字精要>" \
  --title "<如能提炼标题>" --json
```

- `{timestamp}-{slug}` 整体作为 `--slug` 传入,落 `knowledge/analyses/{slug}.md`。
- `--answer-to` + `--sources-used` 为 analysis 必填(gen-page 校验,缺失即报错,不落半成品)。
- `sources_used` 只收**阶段 2-5 实际读过的 wiki 页相对路径**,不收正文出现过但未读的页。
- tags 走 6 轴字典(`doc/template/tag-spec.md`),必含 `docform/` + `domain/`,≥ 5 条;skeleton 自带示例 tags,LLM 按需用 `--patch-frontmatter-only` 精修。

### 步骤 10:LLM 填 analysis 正文(阻塞)

- **不锁 H2 骨架**:方案推演 / 维度对比 / 利弊权衡 / 决策树 / 适用场景,任何结构都可以。
- 正文链接主推 `[[wikilink]]` 裸文件名;需要别名用 `[[filename|显示别名]]`。
- **唯一硬约束**:文末必须有一行 `> 引用:[[a]], [[b]], ...`,其 wikilink 列表与 frontmatter `sources_used` **Set 一致**(lint C15.4 承接;缺失或不一致 → 修复后才算完成)。
- **禁止** `## 摘要` / `## Summary` H2:若想写摘要,内容迁移到 frontmatter `summary` 字段(首行 `**问题**: {原问句}`,余下 ≤ 280 字)。
- frontmatter 不手改:需要补字段用 `--patch-frontmatter-only` 重跑 gen-page;不发明字段。

### 步骤 11:追加 log **Creation** 行(非阻塞)

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/query/append-log.js --project <用户工程根> \
  --question "{原问句}" --analysis-path "analyses/{slug}.md" --json
```

- 已有当天 `## [YYYY-MM-DD]` H2 → 行追加到该节下末尾;无 → 新 H2 插到最新在前位置。
- **默认不写拒绝留痕**:`--skip-analysis` 仅在用户显式选择"gating 判定不落档 / 拒绝落档但要留痕"时传入,行写 `→ (未落档)`。

### 步骤 11.5:刷 index + comparison 计数(非阻塞)

```bash
# aggregate-index.js 的 --knowledge 相对 cwd 解析(与 ingest SKILL.md 步骤 14 同款);
# 在用户工程根下执行,不传 --project
node ${CLAUDE_PLUGIN_ROOT}/scripts/aggregate-index.js --knowledge knowledge/ --json
```

(本步为 query / synthesize 与 ingest 共享;落档后必跑一次,确保 index.md 反映新 analysis 页)

```bash
# 仅当 intent == comparison 且本次用户拍板落档后执行;非 comparison 落档不动计数
node ${CLAUDE_PLUGIN_ROOT}/scripts/query/comparison-counter.js increment \
  --project <用户工程根> --theme "<主题短语,如 S32G vs S32K3>" --json
```

```bash
# 仅当用户拍板"建常驻 comparison 页"后执行(建页走 gen-page --type comparison,归 ingest/PRD §4.6 流程)
node ${CLAUDE_PLUGIN_ROOT}/scripts/query/comparison-counter.js reset --project <用户工程根> --json
```

## 拍板门总结

| 时机 | 拍板内容 | 默认 |
|---|---|---|
| 步骤 0 | prefer-qmd 未装 → 装 qmd / 降级 index | 等用户明确(降级需确认) |
| 步骤 8 | 是否落档 analysis(gating `should_ask == true` 时) | 等用户明确;拒绝 → 跳过 9-11(默认不写 log) |
| 步骤 8 | 计数 ≥ 3 → 是否建常驻 comparison 页 | 等用户明确;同意 → 建页 + counter reset |

## 失败语义(权威源 = implement-query.md §4)

失败语义表权威源:[doc/design/implement-query.md §4 风险与回滚](../../doc/design/implement-query.md)。三条 G 系列:

- **G-Q1**:步骤 0 `count-pages.js` 失败或 `knowledge/` 目录不存在(exit 1)→ 停止,提示先跑 `/aeps-llm-wiki-init` 初始化 vault。
- **G-Q2**:large 档(> 1000 页)+ `check-qmd.js` 返回 `available == false` → **报错退出**(design §7.6 唯一阈值升级条款,不降级);medium 档未装 → 拍板门降级,不算失败。
- **G-Q3**:gen-page 校验失败(`--answer-to` / `--sources-used` 缺失,exit 1)→ 修复参数重跑,不落半成品。

其他场景(counter 状态文件损坏自动按零值重建 / log.md 写坏手改)归回滚点处理,不纳入 G 系列。

## wikilink 硬约束(贯穿步骤 6 / 10 所有正文写入)

- 所有写入正文的 wikilink **必须用文件名形式 `[[filename]]`**(目标 .md 去 .md 的 basename),**禁止 title / alias 形式**:Obsidian resolver 只索引文件名 basename,title 形式 wikilink 点击会创建空白页。需要可读别名时写 `[[filename|显示别名]]`(与 ingest SKILL.md 步骤 16.1 同款约束)。
- analysis 文末 `> 引用:` 行的 wikilink 列表必须与 `sources_used` **Set 一致**:不遗漏、不多列;`sources_used` 只收实际读过的页。

## 不做什么(SKILL.md 边界)

- 不写 RAG / embedding / 向量检索(NFR-1);qmd 是唯一可选外部搜索引擎。
- 不写 intent 推断脚本(intent 是 LLM 语义判断,SKILL.md 管)。
- 不写 answer 生成脚本(组织回答是 LLM 职责)。
- 不修改 `gen-page.js` / `aggregate-index.js` / `scripts/ingest/*` 本体(query 的 log 追加走独立 `scripts/query/append-log.js`,不与 ingest batch 契约耦合)。
- 不新增 npm 依赖(0 个新增,query 脚本纯 Node 内置 fs / path / child_process)。
- 不自动 commit;不调 git。
- 不发明 frontmatter 字段;不自动 `npm install`;qmd 未装不自动装(提示用户手动装)。

## 回滚点

- 步骤 0-8:**无写副作用**(count-pages / check-qmd / gating-check / counter read 全部只读或内存态),任意重跑。
- 步骤 9 之后:analysis 页写坏 → 删除 `knowledge/analyses/{slug}.md` 重跑步骤 9-10。
- 步骤 11:log.md 行写错 → 手改该行。
- counter 写坏 → 删 `knowledge/.aeps-state/comparison-counter.json`(下次 increment 自动重建);误 increment → `reset` 归零后按正确次数补 increment。

## 引用

- 设计文档:`doc/design/implement-query.md`(脚本契约 §1.1 / 编排 §2 / 测试矩阵 §3 / 失败语义 §4)
- 上游契约:`doc/design/prd.md` §4.3 + §4.6(路径 B/C)+ AC-3/11/12/13;`doc/design/design.md` §4.2 / §7.4 / §7.5 / §7.6
- 工作流入口:`doc/schema/schema.md` §1.2
- 字段权威:`doc/schema/frontmatter-spec.md` §11.7(`answer_to` / `sources_used` / `sources_count` / `summary`)
- 模板:`doc/template/page-analysis.md`(唯一硬约束 `> 引用:` 行)+ `doc/template/page-log.md`(Creation 行格式)
- 可复用:`scripts/gen-page.js` + `scripts/aggregate-index.js`(均复用不改)

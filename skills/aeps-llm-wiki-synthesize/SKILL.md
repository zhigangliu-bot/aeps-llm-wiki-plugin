---
name: aeps-llm-wiki-synthesize
description: 用户指定 topic,对已有 knowledge/ 做跨页综合,产出常驻 type: synthesis 页;机械候选扫描 + LLM 三信号定范围,sources_count < 3 必经用户拍板,已存在语义相近页走 update 路径禁止全量重生成
plugin-version: 0.6.10
allowed-tools: Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/synthesize/check-topic.js *),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/synthesize/append-log.js *),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/gen-page.js *),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/aggregate-index.js *)
---

## 脚本路径约定

- 本 skill 所有 `node scripts/xxx.js` 命令以 `${CLAUDE_PLUGIN_ROOT}` 为 plugin 根;该变量由调用方注入(plugin 自动注入或用户 shell 导出)。
- 脚本均在 plugin 仓根的 `scripts/` 下,**不**在 `skills/<skill>/scripts/` 下。
- `check-topic.js` / `append-log.js` / `gen-page.js` 用 `--project <用户工程根绝对路径>` 显式指定工程根,**必须显式传**(脚本不依赖 cwd;用户工程根绝无默认值)。
- `aggregate-index.js` 的 `--knowledge` 纯按 cwd 解析(相对路径,无 `--project` 入参);调用时 cwd = 用户工程根(与 ingest 步骤 14 / query 步骤 11.5 逐字同款)。
- 所有脚本 `--json` 时输出结构化 JSON 到 stdout,诊断/进度到 stderr。exit code:0 成功 / 1 用法或环境错误 / 2 写盘失败(仅 append-log)。

# /aeps-llm-wiki-synthesize

用户给一个 topic,plugin 对已有 `knowledge/` 做跨页综合:机械候选扫描(index.md 关键词命中 + 既有 synthesis 页清点)→ LLM 按 tags / title / wikilink 三信号决定纳入页集合 → `sources_count < 3` 用户拍板 → `gen-page.js` 建骨架或 patch 既有页 → LLM 填正文 → log 留痕 → index 重建。产物是**常驻** `type: synthesis` 页(不带时间戳,后续同 topic 重跑走 update)。

## 触发

用户跑 `/aeps-llm-wiki-synthesize {topic}`(必带一个综合主题,如「ASIL 分解」「S32K3 低功耗设计」)。

## 设计原则(必读)

- **synthesis 是常驻页,不是一次性快照**:不带时间戳、落 `knowledge/syntheses/{topic-slug}.md`、可 update;一次性的"当时综合"是 query 落档 `analysis` 页的职责,两者不混。
- **既有页守卫(陷阱 2)**:`gen-page.js` 全量模式会**静默覆盖**已存在文件。任何 gen-page 调用前必须先看步骤 0 `syntheses[]` 清单:有语义相近页 → 走 `--patch-frontmatter-only` update 路径,**禁止全量重生成**。
- **`--sources-count` 必须显式传(陷阱 1)**:count 必须与步骤 1 纳入集合条数严格一致,不依赖 gen-page 的推导兜底;缺省落 `0`(触发 lint C6 WARN)。
- **LLM 语义判定范围,脚本零产出**:纳入哪些页由 LLM 按 tags / title / wikilink 三信号判定;`check-topic.js` 只做机械候选预过滤(ponytail),不判定"可否综合"。
- **拍板门强制**:`sources_count < 3`(空综合风险)必须用户明确同意才建页;脚本与 LLM 均不静默决定。机械兜底:lint C6 事后扫。
- **frontmatter 不发明字段**:`resource` 留空(综合页多源融合走 `sources[]`,frontmatter-spec §12.1);补字段用 gen-page 重跑,不手写字段。
- 不修改 `gen-page.js` / `aggregate-index.js` / `scripts/{init,ingest,query,lint}/*` 本体(冻结产物);不新增 npm 依赖;不自动 commit;不调 git。

## 编排流程(对齐 PRD §4.5 流程表步骤 0-6)

### 步骤 0:topic 校验(阻塞)

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/synthesize/check-topic.js --project <用户工程根> --topic "{topic}" --json
```

读 stdout JSON:`match_count` / `matched[]`(title / rel / tags)/ `syntheses[]`(file / title / sources_count / updated)。

- exit 1(`knowledge/` 不存在)→ **停止**,提示先跑 `/aeps-llm-wiki-init`(G-S1)。
- `match_count == 0` → 提示**「先 ingest 再 synthesize」**,正常结束(exit 0):不建页、不写 log。
- `syntheses[]` 非空 → LLM 逐个语义比对 topic 与 `title` / `file`:语义相近 → 标记 **update 路径**(步骤 3b),记住该页 slug;多篇相近 → 询问用户选哪篇(或仍新建)。
- `matched[]` 是步骤 1 的机械候选种子;零命中不阻塞步骤 1(LLM 仍可全库语义补扫)。

### 步骤 1:LLM 决定范围(阻塞,LLM 判定)

LLM 按三信号决定纳入页集合:

1. frontmatter `tags` 命中(`matched[].tags` 是种子);
2. `title` 语义相关(可用 `matched[].title` 起步,不受限于它);
3. 正文 `[[wikilink]]` 关联(沿候选页正文 1 跳邻居,不递归展开)。

对候选页读 frontmatter(`description` / `summary` 优先)后定纳入集合;产出 `sources[]`:**相对 `knowledge/` 的路径列表**(如 `concepts/term/asil.md`)。范围判定完全由 LLM 语义判断,脚本零产出。

### 步骤 2:sources_count 拍板门(阻塞,SKILL.md 算术 + 用户)

`n = sources[]` 条数:

- `n < 3` → **WARN**(空综合风险)+ 用户拍板:`[y]` 继续建页 / `[n]` 拒绝 → **直接结束**(不建页、不写 log、不跑步骤 6;拒绝不留痕)。
- `n ≥ 3` → 直接进入步骤 3。

机械兜底:lint C6 对产物持续扫(`sources_count < 3` WARN),本 skill 不新建脚本。

### 步骤 3a:新建 skeleton(无语义相近既有页时,阻塞)

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/gen-page.js --type synthesis --slug {topic-slug} \
  --project <用户工程根> \
  --title "<综合页标题>" --description "<≤ 280 字一句话定位>" --summary "<≤ 280 字精要>" \
  --sources "<逗号分隔的步骤 1 纳入页相对路径,如 concepts/term/asil.md,entities/product/xxx.md>" \
  --sources-count {n} --json
```

- `{topic-slug}` 由 LLM 拟:ASCII 场景用小写连字符;纯中文 topic 可保留中文文件名(Obsidian 原生支持)。
- 落 `knowledge/syntheses/{topic-slug}.md`,**不带时间戳,常驻**。
- **陷阱 1**:`--sources-count` 必须显式传(见设计原则)。
- **`--description` 必传**:lint C1 对所有 type 必查 `description`;gen-page 对空占位符是**整行删除**(不传 → 产物无该字段 → C1 FAIL)。
- **`--sources` 必传**(M2A B1/N4 根修):synthesis 的 `sources` 必填(对象数组,每条含 `resource`);gen-page 按多行块管道渲染为合法 YAML(每条 `resource: "[[<页 stem>]]"`),LLM **不手写 frontmatter sources 块**。
- 全量模式静默覆盖已存在文件 → 走到这里的唯一前提是步骤 0 `syntheses[]` 确认无同名页(陷阱 2)。

### 步骤 3b:update 既有页(步骤 0 检出语义相近页时,阻塞)

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/gen-page.js --type synthesis --slug {同一 slug} \
  --project <用户工程根> \
  --sources "<逗号分隔的更新后纳入页相对路径>" \
  --sources-count {n} --summary "<≤ 280 字精要>" --json --patch-frontmatter-only
```

- `--patch-frontmatter-only`:只重渲染 frontmatter,**正文不动**;`updated` 随 patch 刷新。
- `--sources` 传**更新后的完整清单**:gen-page 以脚本渲染重写整个 `sources:` 块(合法 YAML,LLM 不手改)。
- **禁止**全量重生成(正文会被占位符覆盖);update 时正文由 LLM 直改(步骤 4)。

### 步骤 4:LLM 填正文(阻塞)

- frontmatter `sources:` 块**已由步骤 3/3b 的 gen-page 脚本渲染**(M2A B1 根修:多行块管道,合法 YAML):gen-page 按 `--sources "<逗号分隔的纳入页相对路径>"` 渲染为**对象数组**(每条 `resource: "[[<页 stem>]]"`)。LLM **不手写、不机械重写** frontmatter `sources:` 块(不做"每条一行补路径"的字符串列表编辑);需要调整清单时重跑 `--patch-frontmatter-only --sources "<新清单>"`。
- **正文只改 H2 之间**:synthesis 不锁骨架(模板 v0.5.7 起权威),体系总览 / 关键议题 / 演进时间线 / 决策树等任何结构都允许。
- 正文链接主推 `[[wikilink]]` 裸文件名(目标 .md 去 .md 的 basename),禁止 title 形式;需要别名用 `[[filename|显示别名]]`。综合页期望 ≥ 5 条 wikilink 跨链多个 wiki 页(软期望,lint 不 FAIL)。
- update 路径:LLM **直改既有正文**(增量修订,不推倒重写);`updated` 已由步骤 3b 刷新。
- **完成自检**:frontmatter 能被 YAML 解析;`sources:` 条数 == `sources_count`;`description` / `summary` 非空(lint C1 必填);正文无 `$TITLE` / `$SOURCES` 等占位符残留。

### 步骤 5:追加 log 留痕(非阻塞,仅建页成功后)

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/synthesize/append-log.js --project <用户工程根> \
  --topic "{topic}" --synthesis-path "syntheses/{slug}.md" --json
```

- 唯一形态 `**Creation**`(N1 前缀收敛,2026-09-17 拍板:删 `--update` / `--skipped` 两形态):新建落档(步骤 3a/4 完成)后写 `**Creation**: synthesis "{topic}" → syntheses/{slug}.md`;update 路径(步骤 3b)**不写 log**;步骤 2 拍板拒绝**不写 log**。
- 日期 H2 契约与 query 同款:已有当天 `## [YYYY-MM-DD]` H2 → 行追加到该节末尾;无 → 新 H2 插最新在前;frontmatter / 旧日期节 / `## 维护` 节原样保留。

### 步骤 6:重建 index(非阻塞)

```bash
# --knowledge 纯按 cwd 解析(相对路径,无 --project 入参);cwd = 用户工程根
node ${CLAUDE_PLUGIN_ROOT}/scripts/aggregate-index.js --plugin-root ${CLAUDE_PLUGIN_ROOT} --knowledge knowledge/ --json
```

- `index.md` syntheses 区按 title 字典序登记;不过滤 `sources_count = 0`(空综合已被步骤 2 拍板门 + lint C6 双重拦截)。
- 拍板拒绝路径不跑本步(无新页,index 不变)。

## frontmatter 产物契约(对齐 frontmatter-spec §12.1 + page-synthesis.md)

| 字段 | 约束 |
|---|---|
| `type` | `synthesis`(固定,gen-page 写) |
| `title` / `description` | LLM 拟;description ≤ 280 字 |
| `tags` | 6 轴字典(`doc/template/tag-spec.md`),必含 `maturity/synthesis`,≥ 5 条 |
| `sources` | 对象数组(每条 `resource: "[[<页 stem>]]"`),= 步骤 1 纳入页集合(步骤 3/3b gen-page 脚本渲染,M2A B1 根修) |
| `sources_count` | int,= `sources` 项数;`< 3` 仅在用户拍板通过后允许(C6 WARN 兜底) |
| `summary` | REQUIRED(≤ 280 字) |
| `generated` / `updated` / `status` | gen-page 自动;update 时 `updated` 刷新 |
| `resource` | **留空**(综合页多源融合走 `sources[]`,不填顶层 resource) |

## 拍板门总结

| 时机 | 拍板内容 | 默认 |
|---|---|---|
| 步骤 0 | `syntheses[]` 多篇语义相近 → 选 update 目标还是新建 | 等用户明确 |
| 步骤 2 | `n < 3` → 是否继续建页 | 等用户明确;拒绝 → 直接结束(不写 log) |

## 失败语义(权威源 = implement-synthesize.md)

- **G-S1**:步骤 0 `check-topic.js` exit 1(`knowledge/` 不存在)→ 停止,提示先跑 `/aeps-llm-wiki-init` 初始化 vault。
- **G-S2**:gen-page 校验失败(缺 `--sources-count` / `--slug` 等,exit 1)→ 修复参数重跑,不落半成品。
- **G-S3**:update 场景误跑全量模式 → 已有正文被占位符覆盖且脚本无法恢复;唯一防线是步骤 0 既有页守卫(**任何 gen-page 调用前必查 `syntheses[]`**)。

其他场景(log.md 写坏手改 / index 幂等重建)归回滚点处理,不纳入 G 系列。

## 不做什么(SKILL.md 边界)

- 不做一次性"当时综合"(那是 query 落档 `analysis` 页的职责;synthesis 常驻可 update)。
- 不做范围自动判定(纳入页由 LLM 语义判定,脚本只做机械候选扫描)。
- 不锁正文骨架(模板 v0.5.7 起不锁 H2;LLM 自由组织)。
- 不修改 `gen-page.js` / `aggregate-index.js` / `scripts/{init,ingest,query,lint}/*` 本体(log 留痕走独立 `scripts/synthesize/append-log.js`,日期 H2 契约同 query 但不 import)。
- 不新增 npm 依赖(synthesize 脚本纯 Node 内置 fs / path;js-yaml 已有则用,无则不引)。
- 不做 `syntheses/` 的合并与清理(膨胀防控靠步骤 2 拍板门 + sources_count 门槛)。
- 不自动 commit;不调 git;不发明 frontmatter 字段。

## 回滚点

- 步骤 0-2:**无写副作用**(check-topic 只读;拍板对话不落盘),任意重跑。
- 步骤 3a 之后:synthesis 页写坏 → 删 `knowledge/syntheses/{slug}.md` 重跑步骤 3a-4。
- 步骤 3b:frontmatter patch 写坏 → 重跑步骤 3b(`--patch-frontmatter-only` 幂等);正文写坏由 LLM 手改。
- 步骤 5:log 行写错 → 手改该行。
- 步骤 6:aggregate-index 幂等,重跑即可。

## 引用

- 设计文档:`doc/design/implement-synthesize.md`(脚本契约 §1 / 编排 §2 / 产物契约 §3 / 测试矩阵 §4)
- 上游契约:`doc/design/prd.md` v0.5.6 §4.5 + G8;`doc/design/design.md` v0.1.1 §3.1 / §7
- 工作流入口:`doc/schema/schema.md` §1.2
- 字段权威:`doc/schema/frontmatter-spec.md` §12.1(`sources_count` / `summary` 对 synthesis REQUIRED)
- 模板:`doc/template/page-synthesis.md`(不锁骨架权威)+ `doc/template/page-log.md`(`**Creation**` 行格式)
- 可复用:`scripts/gen-page.js` + `scripts/aggregate-index.js`(均复用不改)

# aeps-llm-wiki-plugin — implement-query (M2.3)

> **状态**:frozen(v0.1.0,2026-09-12 用户确认;§1.1 comparison-counter 语义读法 A 已拍板:increment 仅在 intent=comparison 且用户拍板落档后,reset 仅在用户拍板建常驻 comparison 页后)
> **上游契约**:`prd.md v0.4.1` §4.3 + AC-3/11/12/13 + `design.md v0.1.1` §4.2/§7.4/§7.5/§7.6 + `schema.md` §1.2 + `frontmatter-spec.md`(字段权威)
> **范围**:仅 `aeps-llm-wiki-query` skill 实现细节;init / ingest / lint / synthesize 各有独立文档,本文件不交叉污染
> **完成定义(M2.3 done =)**:本 `implement-query.md` 冻结 + `skills/aeps-llm-wiki-query/SKILL.md` + `scripts/query/*` + `scripts/check-qmd.js` 全套写完 + 单元测试 + gating e2e + `trellis-check` 全套通过

---

## Change History

| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1.0 | 2026-09-12 | 冻结候选初版:5 个脚本契约(count-pages / check-qmd / gating-check / comparison-counter / append-log)+ qmd 三档分流 + 4 跳扫描编排 + G11 gating 4×4 矩阵 + 路径 B 计数器 + 12 步流程对齐 PRD §4.3 + 测试矩阵 AC-3/11/12/13 | zhigang.liu(Claude Code 起草) |
| v0.1.1 | 2026-09-12 | M2.3 落地修正:§3.1 "gating 200 字边界" 用例与 §1.1 判定表(PRD §4.3 "命中源 < 2 个"不触发)矛盾,用例参数改为"双源同目录"表达字数边界语义;判定逻辑本身零改动 | zhigang.liu(Claude Code 实施 + 复核) |

---

## 0. 任务总览

### 0.1 目标

实现 `/aeps-llm-wiki-query {question}` skill。用户提问,plugin 从 `knowledge/` 里找答案:

1. wiki 规模探查 → 引擎分流(index+4 跳 / qmd)
2. intent 三档路由(`exact` / `ambiguous` / `{overview, comparison, other}`)
3. 4 跳扫描组织答案,每条断言附 `[[wikilink]]`,不编造
4. G11 gating 判定 → 满足才询问是否落档为 analysis 页
5. 落档 → `analyses/{timestamp}-{slug}.md` + log `**Creation**` 行 + index 刷新

### 0.2 不做(明确边界,避免 scope creep)

- **不写** RAG / embedding / 向量检索(NFR-1);qmd 是唯一外部搜索引擎,且可选
- **不写** `infer-intent.js`(intent 是 LLM 语义判断,SKILL.md 管)
- **不写** answer 生成脚本(组织回答是 LLM 职责)
- **不修改** `gen-page.js` / `aggregate-index.js` 本体(`--type analysis` + `--answer-to` + `--sources-used` 已支持,gen-page.js:519-650)
- **不修改** `scripts/ingest/*`(冻结产物;query 的 log 追加走独立小脚本,不与 batch 契约耦合)
- **不新增** npm 依赖(纯 Node 内置:fs / path / child_process)
- **不自动 commit**、不调 git

### 0.3 上下游

- **上游**:init skill(目录骨架 + index/overview/glossary/log 四文件)+ ingest skill(sources/entities/concepts 页 + 双向反链;query 的候选页数据源)
- **下游**:lint skill(C7/C8/C15.4 校验 analysis 落档产物);synthesize skill(复用 4 跳扫描编排)

---

## 1. 脚本清单

| 脚本 | 新建/复用 | 职责 | PRD 步骤 |
|---|---|---|---|
| `scripts/query/count-pages.js` | 新建 | 数 `knowledge/**/*.md` → 引擎分流 | 0 |
| `scripts/check-qmd.js` | 新建 | qmd 可用性探查(design §4.2 指定路径在 `scripts/` 根) | 0 |
| `scripts/query/gating-check.js` | 新建 | G11 gating 判定(4×4 矩阵机械部分) | 8 |
| `scripts/query/comparison-counter.js` | 新建 | 路径 B 计数器持久化 | 8(提议)/ 落档后 |
| `scripts/query/append-log.js` | 新建 | `**Creation**` 行追加 log.md | 11 |
| `scripts/gen-page.js` | 复用不改 | analysis 页 skeleton(`--type analysis --answer-to --sources-used`) | 9 |
| `scripts/aggregate-index.js` | 复用不改 | 落档后刷 index.md | 11.5(共享步骤) |

### 1.1 脚本接口契约

**`count-pages.js`**(步骤 0,规模探查):

```
node scripts/query/count-pages.js --project <用户工程根> --json
```

stdout JSON:

```json
{
  "pages": 123,
  "scale": "small",
  "engine": "index",
  "qmd_required": false
}
```

- `pages`:`knowledge/` 下全部 `**/*.md` 计数(含 reserved index/overview/glossary/log 四文件,与 PRD §4.3 "数 knowledge/**/*.md" 字面一致,不做剔除特判)
- `scale`:`small`(< 500)/ `medium`(500-1000)/ `large`(> 1000)
- `engine`:`index` / `prefer-qmd` / `require-qmd`
- `qmd_required`:`true` 仅当 scale = large(design §7.6 唯一阈值升级条款)
- 阈值常量:`QUERY_INDEX_THRESHOLD = 500` / `QUERY_QMD_REQUIRED_THRESHOLD = 1000`
- 目录不存在 → ERROR exit 1(先 init)

**`check-qmd.js`**(design §4.2):

```
node scripts/check-qmd.js --json
```

stdout JSON:`{ "available": true, "version": "x.y.z" }` 或 `{ "available": false }`;内部跑 `qmd --version`,spawn 失败/超时(3s)= 不可用。**不计入 package.json 依赖清单**(design §4.4)。

**`gating-check.js`**(步骤 8,G11 判定):

```
node scripts/query/gating-check.js --intent <overview|comparison|exact|ambiguous|other> \
  --answer-words <n> --hit-pages "<path1,path2,...>" [--not-covered] --json
```

stdout JSON:

```json
{
  "should_ask": true,
  "triggers": ["intent=overview", "hit_dirs>=2"],
  "skips": []
}
```

判定逻辑(全 trigger 任一命中 **且** 全 skip 均不命中 → `should_ask: true`):

| triggers(任一) | skips(任一) |
|---|---|
| `intent=overview` | `intent=exact` |
| `intent=comparison` | `intent=ambiguous` |
| `hit_dirs>=2`(hit-pages 按 `knowledge/<dir>/` 首段去重计数) | `answer_words<200` |
| `answer_words>=200` | `hit_pages<2` |
| | `not_covered=true`(回答含"Wiki 未覆盖此问题") |

- intent 由 LLM 传入(步骤 1 判定),机械量(字数/命中页/子目录数)脚本算 —— LLM 不做算术,防 gating 误判
- **ambiguous + 词命中是两回事**:路径 C 触发词(`vs`/`对比`/`区别`/`异同`/`优缺点`)只是 LLM 推断 intent 的辅助,不改变 ambiguous fallthrough(PRD §4.3 Intent 路由)

**`comparison-counter.js`**(路径 B,design §7.5):

```
node scripts/query/comparison-counter.js read  --project <用户工程根> --json
node scripts/query/comparison-counter.js increment --project <用户工程根> --theme "<主题短语>" --json
node scripts/query/comparison-counter.js reset --project <用户工程根> --json
```

- 持久化:`<project>/knowledge/.aeps-state/comparison-counter.json`,结构 `{ "count": 0, "themes": [] , "updated": "<ISO 8601>" }`
- `read` → `{ "count": 2, "should_propose": false }`(`should_propose = count >= 3`)
- `increment`:**仅用户拍板落档 analysis 后**由 SKILL.md 调用(intent = comparison 时 +1;非 comparison 落档不动计数)——对齐 design §7.5 "计数仅在用户拍板建页后才更新,避免噪声查询污染计数"
- `reset`:用户拍板建常驻 comparison 页后归零(SKILL.md 编排,脚本不自动触发)
- `.aeps-state/` 目录不存在 → 自动创建

**`append-log.js`**(步骤 11):

```
node scripts/query/append-log.js --project <用户工程根> --question "<原问句>" --analysis-path "analyses/2026-09-12-xxx.md" [--skip-analysis] --json
```

- 写入格式(对齐 `doc/template/page-log.md` + schema.md:190 示例):

  ```markdown
  ## [2026-09-12]

  **Creation**: query "S32G vs S32K3 怎么选?" → analyses/2026-09-12-s32g-vs-s32k3.md
  ```

- 已有当天 `## [YYYY-MM-DD]` H2 → 行追加到该 H2 下末尾;无 → 新 H2 插到最新在前位置(与 ingest append-log 同规则,独立实现,不复用 ingest 脚本)
- `--skip-analysis`:gating 判定为不落档 / 用户拒绝落档时,仍记一条 `**Creation**: query "<原问句>" → (未落档)` 留痕——**可选行为,默认不传不写**(log 只记落档,拒绝不进 log,避免噪声;该参数保留给 SKILL.md 显式选择)

### 1.2 JSON stdout 契约(全脚本)

对齐 ingest 惯例:所有脚本 `--json` 输出结构化 JSON 到 stdout,诊断/进度到 stderr;SKILL.md 用 `JSON.parse` 解析。exit code:0 成功 / 1 用法或环境错误 / 2 数据校验 FAIL。

### 1.3 与已有脚本的边界

- `gen-page.js`:`--type analysis` 路径已有(analysis 必填校验 `--answer-to` + (`--sources-used` | `--sources-count`),gen-page.js:645-650);`{timestamp}-{slug}` 作为 slug 传入;**不修改本体**
- `aggregate-index.js`:落档后跑一次刷 index.md(ingest SKILL.md 步骤 14 注明"本步为 query/synthesize 共享");**不修改本体**

---

## 2. SKILL.md 编排(`skills/aeps-llm-wiki-query/SKILL.md`)

格式对齐 ingest SKILL.md(frontmatter `allowed-tools` + 脚本路径约定 + 设计原则 + 编排流程 + 拍板门 + 失败语义 + 不做什么 + 回滚点 + 引用)。**skill 文件是纯规范,不放日志/测试/change history**。

### 流程(对齐 PRD §4.3 流程表 0-11)

| # | 步骤 | 执行者 | 阻塞 |
|---|---|---|---|
| 0 | `count-pages.js` 规模探查;`qmd_required=true` 时调 `check-qmd.js`,未装 → **报错退出**;`prefer-qmd` + 未装 → 提示降级 index | 脚本 | 是 |
| 1 | intent 路由三档(路径 C 触发词仅辅助);ambiguous → 回答但永不落档 | LLM | 是 |
| 2 | 第 1 跳:`index.md` + tags 关键词过滤候选(<500 页);或 `qmd query "{question}"`(500-1000 已装) | LLM | 否 |
| 3 | 第 2 跳:读候选页 frontmatter(`description`/`summary` → `title` → 全文);二进制源页经 `converted_path` 直读副本 | LLM | 否 |
| 4 | 第 3 跳:沿 `[[wikilink]]` 1 跳深跳 entities/concepts/analyses/comparisons 邻居 | LLM | 否 |
| 5 | 第 4 跳:`glossary.md` 消歧 + `log.md` 近期 10 条 | LLM | 否 |
| 6 | 组织回答:每条断言附 `[[wikilink]]` 裸文件名 | LLM | 是 |
| 7 | 诚实声明:不编造;未覆盖 → "我读到的 wiki 里没有覆盖这点" | LLM | 是 |
| 8 | `gating-check.js` 判定 → `should_ask` 时询问落档;同时 `comparison-counter.js read`,`should_propose=true` 时加问常驻 comparison 页 | 脚本+LLM | 是 |
| 9 | 用户同意 → `gen-page.js --type analysis --slug {timestamp}-{slug} --answer-to "{原问句}" --sources-used "<逗号分隔>"` | 脚本 | 是 |
| 10 | LLM 填正文(不锁 H2 骨架;`summary` 首行 `**问题**: {原问句}`;文末 `> 引用:` 行与 `sources_used` Set 一致;出现 `## 摘要`/`## Summary` → 内容迁移 frontmatter) | LLM | 是 |
| 11 | `append-log.js` 追加 `**Creation**` 行 | 脚本 | 否 |
| 11.5 | `aggregate-index.js` 刷 index.md(共享步骤)+ intent=comparison 时 `comparison-counter.js increment` | 脚本 | 否 |

### 硬约束(写入 SKILL.md)

- `sources_used` 只收**阶段 2-5 实际读过的 wiki 页相对路径**,不收正文出现过但未读的页
- `> 引用:` 行 wikilink 列表与 `sources_used` **Set 一致**(lint C15.4 承接,Q7 死循环防护)
- analysis frontmatter 不手改,全走 gen-page 参数(patch 场景用 `--patch-frontmatter-only`)
- wikilink 用文件名 basename 形式(ingest SKILL.md 步骤 16.1 同款约束)
- LLM 只填正文;不发明 frontmatter 字段;不自动 commit

### 拍板门

| 时机 | 拍板内容 | 默认 |
|---|---|---|
| 步骤 0 | prefer-qmd 未装 → 装 / 降级 index | 等用户明确(降级需确认) |
| 步骤 8 | 是否落档 analysis | 等用户明确 |
| 步骤 8 | 计数 ≥3 → 是否建常驻 comparison 页 | 等用户明确;同意 → 建页 + counter reset |

---

## 3. 测试用例表(scripts/query/test/,node:test,不入库)

### 3.1 单元测试

| 用例 | 断言 | 对齐 |
|---|---|---|
| count-pages 空目录 | pages=0, engine=index | §1.1 |
| count-pages 阈值边界 | 499/500/1000/1001 → small/medium/medium/large | design §7.6 |
| count-pages 目录不存在 | exit 1 | §1.1 |
| check-qmd 正常环境 | JSON 契约字段齐(available boolean) | §1.1 |
| gating exact | should_ask=false, skips 含 intent=exact | AC-13 |
| gating ambiguous | should_ask=false | AC-13 |
| gating overview | should_ask=true | AC-13 |
| gating comparison | should_ask=true | AC-13 |
| gating 200 字边界 | 199 字 + 双源同目录 → false;200 字 + 双源同目录 → true(单源场景 hit_pages<2 skip 永远拦截,false) | PRD §4.3 表 |
| gating not-covered | 含 not_covered → 永不询问 | PRD §4.3 表 |
| gating hit_dirs 去重 | 同目录 5 页 → hit_dirs=1 不触发;2 目录 2 页 → 触发 | §1.1 |
| counter increment/reset | JSON 文件读写 roundtrip;≥3 → should_propose | design §7.5 |
| append-log 新日期 | 新 H2 插最前,行格式含 `**Creation**: query` | §1.1 |
| append-log 已有日期 | 行追加到既有 H2 下 | §1.1 |

### 3.2 e2e(gating)

临时 vault fixture(ingest e2e 同款 `temp/` 方式):建 3 页不同子目录 → overview 问题 → should_ask=true;exact 问题 → false;全流程落档 → analysis 文件含 `> 引用:` 行 + log 含 `**Creation**` 行。

### 3.3 手动验收(需要真实 vault,SKILL.md 层)

- AC-3:回答含 wikilink、未覆盖点诚实声明(真 LLM 会话)
- AC-13:Exact 无 prompt / Overview 必有 prompt(SKILL.md 编排验证)

---

## 4. 风险与回滚

| 风险 | 缓解 |
|---|---|
| intent 误判(exact 判成 overview)→ gating 误问 | 拍板门兜底:询问后用户可拒绝;误判只是多问一句,不写文件 |
| `sources_used` 填写过宽 | SKILL.md 硬约束"只收实际读过的页";lint C7/C8 兜底 |
| 字数统计口径(中文 vs 英文) | gating-check 按空白分词 + CJK 字符逐字计数(文档写明口径);边界 ±1 字不影响拍板门 |
| comparison-counter 语义歧义 | 本文锁定:increment 仅在 intent=comparison 且用户拍板落档后;reset 仅在用户拍板建常驻页后 |
| qmd CLI 行为变化 | check-qmd 只探 `--version`;query 调用失败 → SKILL.md 降级 index 并告知用户(medium 档) |

**回滚点**:步骤 0-8 无写副作用,任意重跑;步骤 9 之后写坏 analysis 页 → 删除该文件重跑;步骤 11 log 写错 → 手改;counter 写坏 → 删 `.aeps-state/comparison-counter.json`(下次 increment 重建)。

**失败语义**(G 系列权威,SKILL.md 引用此处):

- **G-Q1**:步骤 0 `count-pages.js` 失败或目录不存在 → exit,提示先跑 init
- **G-Q2**:large 档 + qmd 未装 → **报错退出**(design §7.6 唯一阈值升级条款,不降级)
- **G-Q3**:gen-page 校验失败(`--answer-to` / `--sources-used` 缺失)→ 修复参数重跑,不落半成品

---

## 5. 引用

- 上游:`doc/design/prd.md` §4.3 + §7.1(AC-3/11/12/13);`doc/design/design.md` §4.2 / §7.4 / §7.5 / §7.6
- 工作流入口:`doc/schema/schema.md` §1.2
- 字段权威:`doc/schema/frontmatter-spec.md`(§11.7 `answer_to` / `sources_used`;`summary` 首行约定 §4.x)
- 模板:`doc/template/page-analysis.md`(唯一硬约束 `> 引用:` 行)+ `doc/template/page-log.md`(Creation 行格式)
- 可复用:`scripts/gen-page.js`(analysis 支撑 gen-page.js:519-650)+ `scripts/aggregate-index.js`
- 兄弟实现:`doc/design/implement-ingest.md`(脚本契约风格 + JSON stdout 惯例 + 测试矩阵风格)

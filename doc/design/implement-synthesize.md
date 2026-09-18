# aeps-llm-wiki-plugin — implement-synthesize (M2.5)

> **状态**:frozen(v0.1.2,2026-09-18 M2 评审 N1 + S3 落地修正)

## Change History

| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1.2 | 2026-09-18 | M2 跨子整合评审 N1 + S3:**N1 log 前缀收敛**(用户拍板 2026-09-17):§1.2 append-log 删 `--skipped` 形态(连同 v0.1.0 三形态中的 `--update` 一并收敛),仅剩 `**Creation**`;步骤 2 拍板拒绝不写 log,update 路径(3b)不写 log;§2 步骤 2 / update 路径汇总 / §4 U4·E2·E3 同步裁剪。**S3 sources 写法对齐 M2A B1 根修**:§1.3 陷阱 1 重写 —— v0.1.1 的「不传 `--sources`、步骤 4 LLM 按锚点注释行机械重写 `sources:` 块」教法**作废**(gen-page v0.6.9 M2A 起 sources 统一走 `*_BODY` 块替换管道渲染,产物恒为合法 YAML);新建 / update 均必传 `--sources "<逗号分隔的纳入页相对路径>"`,脚本渲染为对象数组(每条 `resource: "[[<页 stem>]]"`),LLM 不手写不机械重写;§2 步骤 4 同步 | zhigang.liu(Claude Code) |
| v0.1.1 | 2026-09-16 | 质检落地修正:§1.3 撤 `--sources` 传参(gen-page v0.6.9 对 synthesis 模板 `sources: $SOURCES` 行内占位符 + yamlListBody 渲染出非法 YAML,实测 js-yaml bad indentation;改由步骤 4 LLM 机械重写 `sources:` 块,3b 传 `--sources ""` 显式清空)+ 步骤 3a/3b 补必传 `--description`(lint C1 全 type 必查,缺则产物必 FAIL)+ §1.4 调用形态改为 `--knowledge`(位置参数无效,resolve 相对 cwd)+ §3 "update 时 generated 不动"撤注(gen-page patch 从模板重渲染,`generated.at` 随 `$NOW` 刷新,仅承诺 `updated` 刷新)+ §1.1 匹配域收紧注记(仅登记含 markdown 链接的条目行,避免 `## Syntheses` 标题噪声) | zhigang.liu(Claude Code 起草) |
| v0.1.0 | 2026-09-16 | 冻结初版:2 新脚本(check-topic.js 候选扫描 + syntheses 清点 / append-log.js Creation·Skipped·Update 三形态)+ 复用 gen-page / aggregate-index;update 路径(--patch-frontmatter-only + LLM 直改正文,防 gen-page 全量静默覆盖);落地修正 2 处(§1.4 index 登记不过滤 sources_count=0;§1.3 陷阱 1 SKILL.md 显式传 --sources-count);测试矩阵 8 组 | zhigang.liu(Claude Code 起草) |

> **上游契约**:`prd.md v0.5.6` §4.5 + G8 + `design.md v0.1.1` §3.1 / §7 + `schema.md`(冻结 v0.5.6)+ `frontmatter-spec.md` §12.1(字段权威)+ `doc/template/page-synthesis.md`(不锁骨架权威)
> **范围**:仅 `aeps-llm-wiki-synthesize` skill 实现细节;init / ingest / query / lint 各有独立文档,本文件不交叉污染
> **完成定义(M2.5 done =)**:本 `implement-synthesize.md` 冻结 + `skills/aeps-llm-wiki-synthesize/SKILL.md` + `scripts/synthesize/*` 全套写完 + 测试用例先行 + 单元 + e2e + `trellis-check` 全套通过

---

## 0. 任务总览

### 0.1 目标

实现 `/aeps-llm-wiki-synthesize {topic}` skill。对已有 wiki 做跨页综合,产出**常驻** `type: synthesis` 页:

1. 步骤 0 机械候选扫描(index.md 关键词命中 + syntheses/ 既有页清点)→ LLM 语义判定 topic 是否可综合
2. LLM 按 tags / title / wikilink 三信号决定纳入页集合;`sources_count < 3` → WARN + 用户拍板
3. 复用 `gen-page.js` 建骨架 / `--patch-frontmatter-only` 更新既有页(常驻页防覆盖)
4. 复用 `aggregate-index.js` 重建 index;新写 `append-log.js` 留痕 `**Creation**` 行

### 0.2 不做(明确边界,避免 scope creep)

- **不做**一次性"当时综合":那是 query 落档 `analysis` 的职责;synthesis 页不带时间戳、常驻可 update(PRD §4.5"不应")
- **不做**范围自动判定:纳入哪些页由 LLM 语义判定,脚本零产出(脚本只做机械候选扫描)
- **不做**正文骨架约束:synthesis 不锁 H2(模板 v0.5.7 起权威);LLM 自由组织
- **不修改** `gen-page.js` / `aggregate-index.js` / `scripts/{init,ingest,query,lint}/*` 本体(冻结产物)
- **不新增** npm 依赖(纯 Node 内置 fs / path;js-yaml 已有则用,无则不引)
- **不自动 commit**、不调 git

### 0.3 上下游

- **上游**:init(目录骨架)、ingest(sources / entities / concepts 页)、query(analysis 页)、lint(质量门槛,"lint 跑过"是 synthesize 前置)
- **下游**:lint C6(sources_count < 3 WARN)对产物持续体检;后续 `/aeps-llm-wiki-synthesize` 同 topic 重跑走 update 路径

---

## 1. 脚本清单

2 个新脚本 + 2 个复用。机械逻辑全部下沉脚本,LLM 只做语义判定与正文写作。

| 脚本 | 新建/复用 | 职责 | PRD §4.5 步骤 |
|---|---|---|---|
| `scripts/synthesize/check-topic.js` | 新建 | index.md 关键词候选扫描 + syntheses/ 既有页清点(--json) | 0(候选产出),3(既有页守卫输入) |
| `scripts/synthesize/append-log.js` | 新建 | log.md 追加 `**Creation**: synthesis` 行(日期 H2 契约同 query) | 5 |
| `scripts/gen-page.js` | 复用 | `--type synthesis` 建骨架 / `--patch-frontmatter-only` 更新 frontmatter | 3(update 路径) |
| `scripts/aggregate-index.js` | 复用 | 重建 `knowledge/index.md` | 6 |

### 1.1 check-topic.js 契约

```bash
node scripts/synthesize/check-topic.js --project <用户工程根> --topic "<topic>" [--json]
```

- `knowledge/` 不存在 → ERROR exit 1(先跑 init)
- 机械匹配规则(ponytail:候选预过滤,语义判定归 LLM):index.md **含 markdown 链接的条目行**(v0.1.1 收紧,避免 `## Syntheses` 等标题行噪声)行文本包含**完整 topic 串**或任一空白切分 token(长度 ≥ 2,大小写不敏感)即命中;行解析出 `[title](rel)` 与行尾 `#tag` 列表
- 同时清点 `knowledge/syntheses/*.md` frontmatter(`title` / `sources_count` / `updated`)→ `syntheses[]`(LLM 语义比对 topic 与既有页,决定新建 vs update)
- `--json` stdout:`{ ok: true, topic, match_count, matched: [{ title, rel, tags[] }], syntheses: [{ file, title, sources_count, updated }] }`;诊断到 stderr
- exit:0 正常(含 match_count = 0 —— 是否阻塞由 SKILL.md 判定)/ 1 用法或环境错误

### 1.2 append-log.js 契约

```bash
node scripts/synthesize/append-log.js --project <用户工程根> \
  --topic "<topic>" --synthesis-path "syntheses/<slug>.md" [--json]
```

- 唯一形态(N1 前缀收敛,2026-09-17 拍板):写入行 `**Creation**: synthesis "{topic}" → syntheses/{slug}.md`;仅新建落档后调用
- 拒绝路径(步骤 2 拍板 `[n]`)**不写 log**;update 路径(步骤 3b)**不写 log**(常驻页 update 属常规维护,不产生新档案事件)
- `--synthesis-path` 归一:剥前导 `knowledge/` 与 `./`,反斜杠归一正斜杠
- 日期 H2 契约与 `scripts/query/append-log.js` 一致:当天 H2 下末尾追加;无当天 H2 → 新 H2 插最新在前;已有 frontmatter / 旧日期节 / `## 维护` 节原样保留(round-trip 安全)。独立实现,不 import query 脚本(对齐 implement-lint.md "不与 append-log.js 契约耦合"先例)
- `knowledge/` 不存在 → ERROR exit 1;log.md 不存在 → 创建(仅当天节 + 行)
- `--json` stdout:`{ written: true, date, action: "appended|new-section|created", log_path, line }`
- exit:0 成功 / 1 用法或环境错误 / 2 写盘失败

### 1.3 gen-page.js 复用契约(陷阱注记)

```bash
# 新建路径(步骤 3a;v0.1.2:--sources 必传,见陷阱 1)
node scripts/gen-page.js --type synthesis --slug <topic-slug> \
  --project <用户工程根> \
  --title "<综合页标题>" --description "<≤280字一句话定位>" --summary "<≤280字>" \
  --sources "<逗号分隔的纳入页相对路径,如 concepts/term/asil.md,entities/product/xxx.md>" \
  --sources-count <n> --json

# update 路径(已存在页,仅刷 frontmatter;v0.1.2:--sources 传更新后完整清单)
node scripts/gen-page.js --type synthesis --slug <topic-slug> \
  --project <用户工程根> \
  --sources "<逗号分隔的更新后纳入页相对路径>" --sources-count <n> \
  --description "<≤280字>" --summary "<≤280字>" \
  --patch-frontmatter-only --json
```

- **陷阱 1(v0.1.2 重写,对齐 M2A B1 根修)**:`--sources` **必传**(逗号分隔的所引 wiki 页相对 `knowledge/` 路径)。gen-page v0.6.9 M2A 起 sources 统一走 `*_BODY` 块替换管道(`replaceListBody`)渲染为**对象数组**(每条 `resource: "[[<页 stem>]]"`),产物恒为合法 YAML —— v0.1.1 的「不传 `--sources`、步骤 4 LLM 按锚点注释行机械重写 `sources:` 块」教法**作废**,LLM 不手写、不逐行补路径;需要调整清单时重跑 `--patch-frontmatter-only --sources "<新清单>"`(脚本整块重写 `sources:`)。
- **陷阱 1.1(v0.1.1 新增)**:`--description` 必传。lint C1 对所有 type 必查 `description`,gen-page 对空占位符整行删行,缺省产物必 FAIL C1
- **陷阱 2**:gen-page 全量模式**静默覆盖**已存在文件 → SKILL.md 必须先查 `syntheses[]` 既有清单(check-topic.js 产出),命中即走 update 路径,禁止全量重生成

### 1.4 aggregate-index.js 复用契约

```bash
node scripts/aggregate-index.js --knowledge knowledge/ --json   # cwd = 用户工程根(v0.1.1:只认 --knowledge,位置参数无效)
```

- 现实现无 "sources_count = 0 不写入" 过滤(PRD §4.5 步骤 6 括号注记无对应代码)。**落地修正(评审已拍板)**:不改冻结产物,登记不过滤;空综合已被步骤 2 拍板门 + lint C6 双重拦截,"0 不写入"防线冗余
- syntheses 区按 title 字典序登记(analysis 按 mtime,synthesis/comparison 按 title —— 现实现行为)

---

## 2. 编排流程步骤细化(对齐 PRD §4.5 流程表 0-6)

| # | 步骤 | 执行者 | 阻塞 | 细化 |
|---|---|---|---|---|
| 0 | topic 校验 | check-topic.js → LLM | 是 | `match_count == 0` → 提示"先 ingest 再 synthesize",**exit 0**,不建页不写 log。`syntheses[]` 命中语义相近页 → 标记 update 路径 |
| 1 | LLM 决定范围 | LLM | 是 | 三信号:frontmatter `tags` 命中 / `title` 语义相关 / 正文 `[[wikilink]]` 关联。对候选页读 frontmatter(`description`/`summary` 优先)后定纳入集合;产出 `sources[]` 相对路径列表 |
| 2 | sources_count 拍板门 | SKILL.md(算术)+ 用户 | 是 | `n < 3` → WARN + 拍板(`[y]` 继续 / `[n]` 拒绝 → **直接结束,不写 log**,N1);`n ≥ 3` 直接进入。机械兜底:lint C6 事后扫(不新建脚本,避免与 lint 职责重复) |
| 3a | 新建 skeleton | gen-page.js | 是 | §1.3 新建命令;slug 由 LLM 定(ascii 小写连字符;纯中文 topic 可保留中文文件名,Obsidian 原生支持) |
| 3b | update 既有页 | gen-page.js | 是 | §1.3 `--patch-frontmatter-only` 命令;正文由 LLM 直改(步骤 4) |
| 4 | LLM 填正文 | LLM | 是 | 仅 H2 之间正文;不锁骨架;正文 wikilink 期望 ≥ 5 条跨链(软期望,lint 不 FAIL);frontmatter `sources:` 块**已由步骤 3a/3b gen-page 脚本渲染**(对象数组,每条 `resource: "[[<页 stem>]]"`),LLM 不手写不机械重写(v0.1.2,对齐 M2A B1);完成自检:`description` / `summary` 非空(lint C1 必填);update 时 `updated` 由 patch 刷新 |
| 5 | 追加 log | append-log.js | 否 | §1.2 契约 |
| 6 | 重建 index | aggregate-index.js | 否 | §1.4 契约 |

**update 路径汇总(步骤 0 检出既有页时)**:3b → 4 → 6(**跳过步骤 5**,update 不写 log,N1 前缀收敛:append-log 仅剩 `**Creation**` 一形态,`--update` / `--skipped` 已删)。

---

## 3. frontmatter 产物契约(对齐 frontmatter-spec §12.1 + page-synthesis.md)

| 字段 | 约束 |
|---|---|
| `type` | `synthesis`(固定) |
| `title` / `description` | LLM 拟;description ≤ 280 字 |
| `tags` | 6 轴字典(tag-spec.md),`maturity/synthesis` 必含(模板示例权威) |
| `sources` | YAML list,= 步骤 1 纳入页相对路径集合 |
| `sources_count` | int,= `sources` 项数;`< 3` 仅在用户拍板通过后允许(C6 WARN 兜底) |
| `summary` | REQUIRED(≤ 280 字) |
| `generated` / `updated` / `status` | gen-page 自动;update 时 patch 从模板重渲染,`updated` 与 `generated.at` 一并刷新(v0.1.1 实测注记;对外仅承诺 `updated` 刷新) |
| `resource` | **留空**(frontmatter-spec:综合页不填顶层 resource,多源融合走 `sources[]`) |

---

## 4. 测试矩阵(node:test,scripts/synthesize/test/,本机不入库)

| # | 组 | 覆盖 |
|---|---|---|
| U1 | check-topic 命中 | index.md 含 topic 完整串 / 单 token / 大小写混合 → matched 正确 |
| U2 | check-topic 零命中 + 环境错 | 无 knowledge/ → exit 1;空 index → match_count 0 exit 0 |
| U3 | check-topic syntheses 清点 | 既有 synthesis 页 frontmatter 解析(含 sources_count / updated) |
| U4 | append-log Creation 形态 | `**Creation**` 行内容逐字断言;`--skipped` / `--update` 入参不再存在(N1 裁剪) |
| U5 | append-log 日期 H2 | 当天有节末尾追加 / 无节新插最新在前 / round-trip 保留旧节与 `## 维护` |
| E1 | e2e 新建 | 临时 vault:init 骨架 + 假 index → 步骤 0-6 全跑 → 断言页 / log / index 三产物 |
| E2 | e2e update | 既有 synthesis 页重跑 → 断言正文未被占位符覆盖 + `updated` 刷新 + **log 无新行**(update 不写 log,N1) |
| E3 | e2e 拒绝 | n < 3 拍板拒绝 → 无页、**log 无新行**(拒绝不写 log,N1) |

---

## 5. 不动清单与风险

| 项 | 说明 |
|---|---|
| gen-page.js 全量覆盖行为 | **不改**(冻结产物);由 SKILL.md 步骤 0 既有页守卫规避(§1.3 陷阱 2) |
| aggregate-index 无 sources_count=0 过滤 | **不改**;落地修正注记 §1.4,评审拍板 |
| query/lint append 逻辑重复 | 接受(各 skill 独立契约,先例:lint.js 内联实现);若未来抽 lib 另立任务 |
| 纯中文 topic 的 slug | 允许中文文件名(Obsidian 原生);ASCII 场景 LLM 拟小写连字符 slug |
| syntheses/ 膨胀 | design §7:必须用户拍板 + sources_count 门槛;本 skill 不做合并/清理 |

# aeps-llm-wiki-plugin — implement-ingest (M2.2)

> **状态**:frozen(v0.1.0,v0.1.4 起解冻同步 4 bug 修复,见 Change History)
> **冻结日期**:2026-09-07(v0.1.4 解冻日:2026-09-09)
> **作者**:zhigang.liu(由 Claude Code 起草)
> **上游契约**:`prd.md v0.4.1`(已冻结)+ `design.md v0.1.1`(已冻结)+ `schema.md v0.5.5`(工作流入口)+ `frontmatter-spec.md`(字段权威)+ `tag-spec.md v1.0`(tag 字典)
> **范围**:仅 `aeps-llm-wiki-ingest` skill 实现细节;init / query / lint / synthesize 各有独立 `implement-{skill}.md`,**本文件不交叉污染**
> **完成定义(M2.2 done =)**:本 `implement-ingest.md` 冻结 + `skills/aeps-llm-wiki-ingest/SKILL.md` + `scripts/ingest/*` 全套写完 + 单元测试 + 至少 1 个 e2e 跑通 + `trellis-check` 全套通过

---

## Change History

| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1.0 | 2026-09-07 | 冻结初版:7 个 scripts/ingest/* 脚本契约 + 双向反链规则 + 5 路径分流 + 19 步流程对齐 PRD §4.2 + 测试矩阵 AC-2/6/7/8/9/10/14/15/16 + NFR-1/2/4/5 + COMPAT-1 + 5 路径分流 + raw 拍板门 + 命名飘 + 幂等 + lint C17/18/19 + e2e | zhigang.liu(Claude Code 起草) |
| v0.1.1 | 2026-09-07 | M2.2 落地:7 个 scripts/ingest/* 脚本 + lint-stub 占位 + 8 个测试文件(40 → 43 用例,均 pass);build-related-pages.js 加 ajv 校验 + 删 TYPE_DIRS 死代码;classify.js 加 `--route <2\|3>`;测试 `os.tmpdir()` → 项目 `temp/`;`scripts/ingest/test/fixtures/` 创目录 + sample-source.md/sample-note.txt;同步升 plugin 版本 0.5.5 → 0.5.6(plugin.json + schema.md 顶部 + schema.md Change History) | zhigang.liu(Claude Code 实施 + 复核) |
| v0.1.2 | 2026-09-08 | 批次 4 (P3 文档与版本一致):(1) §6.1 由"风险表"扩展为"**失败语义权威源**"(G3 / G6 / G10 三规则) + 风险表(原 6.1 → 6.2) + 回滚点(原 6.2 → 6.3)重新编号;SKILL.md 改为引用本表。(2) §5.1 plugin 版本号描述 0.5.5 → 0.5.6。**注**:本版本号描述是文档自身的版本号;plugin 主版本号由 `.claude-plugin/plugin.json` 锁定,本批次不修改 plugin.json(由父任务在所有批次完成后统一发版到 0.6.0)。 | zhigang.liu(Claude Code 实施 + 复核) |
| v0.1.3 | 2026-09-08 | 批次 2 (P1 易修 + ajv 噪音):(1) §2 反链语义由"每次 ingest 完全重建"改为"**追加 + 保留**(v0.5.6 起)"。(2) ajv date-time format WARN 降级:doc/schema/frontmatter.schema.json 把 `format: "date-time"` 替换为等价 pattern,零新增 npm 依赖。**注**:本批次为批次 2 P1 易修内容,R3 是 breaking change(SKILL.md 步骤 12 已显式说明)。 | zhigang.liu(Claude Code 实施 + 复核) |
| v0.1.4 | 2026-09-09 | **解冻** 批次 6 (issue #1/#2/#3/#4 修复):用户 GitHub issue 报告的 4 个 P0/P1 bug — `(1)` `init-batch.js` 保留 LLM 拍板字段(slug/target_subdir/route/...):旧版 map 重写 file 静默丢为 null 导致下游 move-to-raw fail `(2)` `gen-page.js` 加 `--patch-frontmatter-only` flag:只 patch frontmatter 不动正文,解决 SKILL.md 步骤 7 "重跑 --out 覆盖正文" 痛点 `(3)` `aggregate-index.js` 注入最小 frontmatter(type/title/updated/generated/status/tags)到 index/overview/glossary.md,解决 lint R7.2 fail `(4)` `append-log.js` wikilink 优先用 file.slug 而非 inbox 原文件名 basename。**解冻范围**:仅 §1.1 契约表 4 脚本行 + §1.3 复用表 gen-page 条款;§0/2/3/4/5/6 不动。**配套**:SKILL.md Change History 批次 6 + 3 个新测试 (gen-page-patch-fm / aggregate-index-frontmatter / append-log-slug) + 1 个扩测试 (init-batch 保留字段) + fixture 更新 (`## YYYY-MM-DD` → `## [YYYY-MM-DD]`,对齐 v0.5.6 起约定)。**plugin 主版本号**:plugin.json 当前已是 0.6.0(本批次前 issue 报告时已升级),本次不需动作。 | zhigang.liu(Claude Code 实施 + 复核) |

---

## 0. 任务总览

### 0.1 目标

实现 `/aeps-llm-wiki-ingest` skill。用户把资料丢进 `{project}/inbox/`,跑一次命令,自动完成:

1. 扫 inbox → 5 路径分流(原生多模态优先 / anydoc / docling / paddleocr)
2. LLM 提议 raw 子目录 + 用户拍板 → 迁 `raw/{subdir}/`
3. 生成 `type: source` 源页 + 抽取 entity / concept 子页 + 双向反链
4. 更新 `index.md` / `overview.md` / `glossary.md` / `log.md`
5. lint C17/C18/C19 校验本次产出

### 0.2 完成定义(M2.2 done =)

1. 本 `implement-ingest.md` 冻结 → commit
2. `skills/aeps-llm-wiki-ingest/SKILL.md` 写完
3. `scripts/ingest/*` 全套写完(7 个脚本,见 §1.1)
4. 单元测试(`scripts/ingest/test/*.test.js`)+ 至少 1 个 e2e(丢 3 类文件:md / pdf / docx → 走完 ingest 流程)
5. `trellis-check` 全套通过(jsonl 4 条 + check.jsonl 4 条)
6. 一个 atomic commit 落盘

### 0.3 不做(明确边界,避免 scope creep)

- ❌ 不写 init / query / lint / synthesize 任何代码 → 见 `implement-{init,query,lint,synthesize}.md`
- ❌ 不发明 frontmatter 字段(只复述 `frontmatter-spec.md` + `schema.json`)
- ❌ 不实现 `safe-mv.py`(PRD §4.2 流程表步骤 4 提到的别名,本任务把它合并到 `move-to-raw.js`,**单一职责**;Python 已废弃,改 Node.js 实现,与 G6 Node.js 单栈对齐)
- ❌ 不引入 LLM API 调用(ingest 流程的脚本部分**纯机械**,LLM 只在 SKILL.md 编排层调用)
- ❌ 不重写 `gen-page.js` / `aggregate-index.js` —— 已对齐 PRD §4.2,只补小补丁
- ❌ 不写 `update-check` skill(M2 之外,见 HANDOVER)
- ❌ **不**对任何路径写"自动 npm install" —— 依赖按 `package.json` `engines` + `dependencies` 写死,缺依赖 SKILL.md 提示用户手动装

### 0.4 上下游

```
[上游契约]
prd.md v0.4.1 §4.2 ingest 流程表(19 步) + AC-2/AC-6/AC-7/AC-8/AC-9/AC-10/AC-14/AC-15/AC-16
design.md v0.1.1 §3.2 5 路径分流表 + §4.1 职责分层 + §4.2 脚本契约 + §6 Source 页骨架生成 + §7.1 不重转 + §7.2 原生优先 + §7.3 幂等策略
schema.md v0.5.5 §1.1 ingest 工作流
frontmatter-spec.md §4.1.1 22 项硬枚举 + §11.7 plugin 扩展字段 + §12.5 source_file vs converted_path
tag-spec.md v1.0 6 轴 tag 字典
rawdir-spec.md 15 raw 子目录字典
concept-entities-spec.md 14 子类判定示例
doc/template/page-{source,entity-person,concept-theory,analysis,comparison,synthesis}.md 模板

[下游消费]
- query skill 命中 source 页后,可通过 `converted_path` 直接读 .converted.md 副本
- lint skill 校验 C17/C18/C19(本次 ingest 产出)
- synthesize skill 范围扫描包括本次新增的 entity / concept 子页
```

---

## 1. 脚本清单(scripts/ingest/*)

> **设计哲学**:对齐 init — 能调用脚本的尽量调用脚本(用户全局 CLAUDE.md),ingest 流程中确定性动作 100% 走脚本,SKILL.md 只做编排 + 用户对话拍板 + LLM 抽取判定。
>
> **命名**:所有 ingest 脚本放 `scripts/ingest/`,不与 init / update-check 混用。
>
> **测试**:每个脚本配一个 `scripts/ingest/test/<name>.test.js`,用 `node:test`(内置,零依赖)。

### 1.1 脚本接口契约

| 脚本 | 入参 | 行为 | 出参 / 副作用 | 单测覆盖 |
|---|---|---|---|---|
| `scripts/ingest/scan-inbox.js` | `--inbox <dir>` | 递归扫 `inbox/`,过滤 `.gitkeep` / `.DS_Store` / `README.md` / 隐藏文件;返回 JSON `{ files: [{path, size, ext, mtime}], count }` | stdout JSON,exit 0 | 3 fixture:空目录 / 含 1 个 md / 含 1 个 md + 1 个 pdf + 隐藏文件 |
| `scripts/ingest/classify.js` | `--file <path> [--batch <json>]` | 按扩展名 → 5 路径分流表;返回 JSON `{ ext, path, route: 1\|2\|3\|4, converter: null\|claude-native\|anydoc\|docling\|paddleocr, native_text: bool, converted_path: null\|template }`。路径 2 与路径 3 区分需要 SKILL.md 探测 LLM 原生能力,默认建议 `route: 2` + `converter: claude-native`(若 SKILL.md 探测失败 → SKILL.md 走拍板门降级路径 3);路径 4 拍板门 PaddleOCR 未装 → FAIL 不降级 Python(G6) | stdout JSON,exit 0 | 5 fixture:每路径一个 |
| `scripts/ingest/convert-to-md.js` | `--file <path> --emit-to <dir>` | **统一入口**,按 `classify.js` 结果派发:`.pdf` → `anydoc/anydoc_pdf_to_md.js`;`.pptx/.docx/.xlsx/.html/.htm` → `anydoc/docling_to_md.py`(docling);`.png/.jpg/.jpeg/.bmp/.tiff` → `ocr/ocr_to_md.py`(PaddleOCR)。**纯文本(.md/.txt/...)不调本脚本**(SKILL.md 直接读)。**失败抛 non-zero exit**(原文件保留 inbox,符合 PRD §4.2 流程表步骤 2 FAIL 语义) | 写文件:`<dir>/<basename>.<ext>.converted.md` + stdout OK / FAIL | 4 fixture:每路径成功 + PDF 失败(扫描件) |
| `scripts/ingest/init-batch.js` | `--project <dir> --files <json> --emit-dir <dir>` | 创建 `temp/ingest-batch-{ISO-timestamp}.json` 工作文件,记录本次批处理所有文件状态。**v0.6.0 起(v0.1.4 批次 6,issue #1 fix)**:`files[]` **保留 LLM 拍板字段**(slug / target_subdir / route / converter / native_text / converted_path / converted_emitted / 等),旧版 map 重写会把这些静默丢为 null 导致下游 move-to-raw fail。透传策略:`{ ...LLM输入, path, size, ext, mtime, moved:false, status:'pending', converted_emitted, target_subdir }`(`moved`/`status` 强制覆盖 LLM 误传,其他透传)。后续 4 个脚本(`move-to-raw` / `build-related-pages` / `append-log` / 后续 lint)读这个文件共享状态 | 写 `temp/ingest-batch-{ts}.json`,stdout JSON | 3 fixture:基础 + 保留 LLM 拍板字段 + 脚本必需字段覆盖 LLM 误传 |
| `scripts/ingest/move-to-raw.js` | `--project <dir> --batch <json> [--apply]` | **替换 PRD §4.2 步骤 4 提到的 safe-mv.py**。逐文件:① raw 子目录拍板门(由 SKILL.md 传入 `target_subdir`);② raw/{subdir}/{file} 已存在同名 → 强制拍板门(`[y]` 覆盖 → 先备份 `temp/raw_backup_{hash}/` + `os.replace()` 原子替换 / `[n]` 跳过 / `[d]` 仅删旧副本);③ 同时迁原文件 + `.converted.md`(若有);④ 删除 inbox 原文件;⑤ 不重转(PRD §7.1)。dry-run 默认输出 diff;`--apply` 才写盘 | stdout JSON `{moved: [...], skipped: [...], conflicts: [...], backed_up: [...]}` | 4 fixture:正常迁 / raw 已存在同名 / 仅删旧副本 / dry-run |
| `scripts/ingest/build-related-pages.js` | `--project <dir> --batch <json>` | **双向反链生成**。读 `batch.json` 的 `files[]` + 扫 `knowledge/sources/<slug>.md` frontmatter + 扫 `knowledge/entities/**` + `knowledge/concepts/**` frontmatter 的 `## 来源资料` 节。对每对(source ↔ entity/concept):① source 页 → 写 `## 相关页面(Related Pages)` 区块(按 Entities / Concepts 分组 wikilink;某组空则省子标题,全空则省整节);② entity/concept 页 → 反向追加 `## 来源资料` 节(按 source title 排序 wikilink;空则省整节)。**每次 ingest 完全重建**,不保留人工条目 | 写文件:`knowledge/sources/*.md` + `knowledge/{entities,concepts}/**/*.md` | 3 fixture:1 source → 2 entity/concept / 多 source 共享同一 entity / 空 source(无抽取) |
| `scripts/ingest/append-log.js` | `--project <dir> --batch <json>` | 追加 `**Ingest**: inbox/<file> → raw/<subdir>/<file> (+ converted.md);新建 <list>` 到 `knowledge/log.md` 对应 ISO 8601 日期 H2 下。最新在前(Q5);不动已有 Init/Creation/LintFix 等条目。**v0.6.0 起(v0.1.4 批次 6,issue #4 fix)**:`**Ingest**` 行的 wikilink 和 raw 路径**优先用 `batch.files[].slug`**(wikilink = `[[slug]]`,raw 路径 = `{slug}.{原扩展名}`),fallback 到 inbox 原文件名 basename。inbox 来源路径保留原文件名(人类追溯用)。 | 写文件:`knowledge/log.md` | 4 fixture:首次追加 / 已有当天 H2 复用 / 不同日期新 H2 插入最前 / dry-run / slug 优先 |

> **显式禁**(不写这些脚本):
> - ❌ `scripts/ingest/infer-intent.js`(LLM 决策,SKILL.md 管)
> - ❌ `scripts/ingest/converse.js`(对话 SKILL.md 管)
> - ❌ `scripts/ingest/check-deps.js`(依赖检查 SKILL.md 跑 `node --version` / `python --version` / `node_modules/@firecrawl/anydoc` 是否存在)

### 1.2 关键设计决策

- **7 个脚本分而治之**:`scan-inbox` 扫 / `classify` 分流 / `convert-to-md` 转换 / `init-batch` 状态 / `move-to-raw` 迁移 / `build-related-pages` 反链 / `append-log` 日志;每个脚本职责单一,易测易换;`batch.json` 跨步骤共享状态,**所有写入幂等**(同一 batch 重跑产出相同)
- **不写 `safe-mv.py`,合并到 `move-to-raw.js`** 的理由:① PRD §4.2 流程表步骤 4 把"迁原文件 + md 副本"作为**单一动作**,拆成 Python 反而增加跨语言 spawn 开销;② `gen-page.js` 等已是 Node.js,统一栈减少环境负担(G6 Node.js 单栈);③ SKILL.md 只需调一个 `move-to-raw --apply`
- **dry-run 普遍可用**:除 `init-batch` 和 `append-log` 外,其余脚本默认接 `--dry-run`;SKILL.md 拍板前先用 dry-run 展示给用户看
- **JSON stdout 是契约**:所有脚本输出结构化 JSON 时用 stdout,日志/进度走 stderr;SKILL.md 用 `JSON.parse` 解析(避免脆弱字符串匹配)
- **batch.json 是状态总线**:`temp/ingest-batch-{ts}.json` 由 `init-batch` 创建,后续 4 个脚本顺序读它;`ts = ISO 8601 时间戳`,保证幂等
- **依赖**:复用了 `gen-page.js` / `aggregate-index.js` 已声明的 `js-yaml` + `@firecrawl/anydoc` + `ajv`(`scripts/package.json` 已含);**不**新增 npm 依赖;**OCR 路径按 G6 失败不降级 Python**(`ocr_to_md.py` 是 PaddleOCR 路径,未装 → 路径 4 FAIL,提示用户)
- **绝对路径禁令**(NFR-4):所有脚本路径参数用相对项目根的 `inbox/` / `raw/` / `knowledge/` 等;`scripts/init/` / `scripts/ingest/` 跨项目拷贝后仍工作
- **不发明新字段**(PRD §10 Q7):`batch.json` 是临时状态文件,在 `temp/`(NFR-5),不入 git;不进入 wiki 任何 frontmatter
- **路径探测留给 SKILL.md**:`classify.js` 默认建议路径 2(claude-native),**实际是否走路径 2 由 SKILL.md 在第 1 步探测 LLM 原生能力后决定**(PRD §4.2 流程表步骤 0)— SKILL.md 调完 LLM 后再调 `classify --route 3 --converter anydoc` 覆盖默认

### 1.3 与已有脚本的边界

| 已有脚本 | 是否复用 | 如何复用 |
|---|---|---|
| `scripts/gen-page.js` | ✅ 复用 | SKILL.md 调 `gen-page.js --type source --slug ... --ext ... --converter ... --subdir ... --source-file ...` 生成 source 页骨架;同理 entity/concept 子页。**v0.6.0 起(v0.1.4 批次 6,issue #2 fix)** 加 `--patch-frontmatter-only` flag:SKILL.md 步骤 7 "写完正文后回填 --summary" 改用此 flag,只 patch frontmatter 不动正文;目标文件不存在 → fallback 全量生成(WARN)。 |
| `scripts/aggregate-index.js` | ✅ 复用 | SKILL.md 步骤 16-17 调 `aggregate-index.js` 重建 index.md / glossary.md / overview.md。**v0.6.0 起(v0.1.4 批次 6,issue #3 fix)** 三页注入最小 frontmatter(`type` ∈ {index, overview, glossary}, 已对齐 schema enum / `title` / `updated` ISO 8601 / `generated` / `status: stable` / `tags` 5 项),解决 lint R7.2 fail。 |
| `scripts/anydoc/anydoc_pdf_to_md.js` | ✅ 复用 | `convert-to-md.js` 内部 spawn 它处理 `.pdf` |
| `scripts/anydoc/docling_to_md.py` | ✅ 复用 | `convert-to-md.js` 内部 spawn 它处理 `.docx/.pptx/.xlsx/.html/.htm` |
| `scripts/ocr/ocr_to_md.py` | ✅ 复用 | `convert-to-md.js` 内部 spawn 它处理 `.png/.jpg/...` |
| `scripts/init/*` | ❌ 不复用 | init/ 与 ingest/ 命名空间分开,init 跑过的产物(`knowledge/` 22 目录 + 15 raw 子目录)由 ingest 直接消费 |

### 1.4 不写的脚本(显式禁)

- ❌ 不写 `scripts/ingest/convert-to-md.py`(Python);**统一入口** `convert-to-md.js` 用 Node.js `spawnSync` 派发到 anydoc_pdf_to_md.js / docling_to_md.py / ocr_to_md.py 三个底层脚本(Python 底层不重复实现)
- ❌ 不写 `scripts/ingest/safe-mv.py`(PRD §4.2 流程表步骤 4 提到的别名);合并到 `move-to-raw.js`(见 §1.2)
- ❌ 不写 `scripts/ingest/dedupe.js`(同名检测);由 `move-to-raw.js` 拍板门处理
- ❌ 不写 `scripts/ingest/auto-tag.js`(LLM 打标);LLM 决策,SKILL.md 管
- ❌ 不写 `scripts/ingest/auto-extract.js`(LLM 抽取 entity/concept);LLM 决策,SKILL.md 管

---

## 2. frontmatter 字段填写规则

ingest 主要写 `type: source` / `type: entity.*` / `type: concept.*` 三类页。其余 type(analysis / comparison / synthesis)分别由 query / ingest 拍板门 / synthesize 触发,**本次不实现**。

### 2.1 `type: source` 页(由 `gen-page.js` 生成,ingest 步骤 6-7)

对齐 `frontmatter-spec.md` §11.7 + `schema.json` `allOf[0]` source 必填字段组。`gen-page.js` 已实现,ingest 仅在 SKILL.md 步骤 6 调用时传 `--ext` / `--converter` / `--subdir` / `--source-file` / `--title` 参数。完整 frontmatter 见 `doc/template/page-source.md` 模板头部。

**字段一致性 lint**(由 lint 实现,ingest 不实现):

| `converter` | `native_text` | `converted_path` |
|---|---|---|
| `null` | `true` | `null` |
| `claude-native` | `true` | `null` |
| `anydoc` / `docling` / `paddleocr` | `false` | 非 null(指向 `.converted.md`) |

任何不一致 → FAIL(对齐 `design.md §6` 字段一致性 lint 表)。

### 2.2 `type: entity.*` / `type: concept.*` 页(由 `gen-page.js` 生成,ingest 步骤 10-11)

对齐 `frontmatter-spec.md` §11.7 + `schema.json` `allOf[5]` entity.* / `allOf[6]` concept.* 必填字段组。`gen-page.js` 7 子类共用骨架(已实现)。

**`sources[]` 字段**(必填,SKILL.md 步骤 11 填):指向本次 ingest 的 source 页(OKF §5.1)。plugin 写法:只写 `id` + `resource`(其他子字段 plugin §11.3 不写):

```yaml
sources:
  - id: iso26262-source
    resource: ./raw/06_功能安全/iso26262.pdf
```

### 2.3 ingest **不动** frontmatter 字段

- `gen-page.js` 输出的 frontmatter,**SKILL.md 步骤 7 / 11 仅替换占位段 / 写正文**,**不改**任何字段值(对齐 `design.md §4.3` SKILL.md 硬约束)
- `template/page-source.md` 的 `## 维护说明` 区块由模板自带(脚本透传,SKILL.md **不**改)
- `template/page-{entity,concept}-*.md` 的 `## 维护说明` 区块同上
- 双向反链(`## 相关页面` + `## 来源资料`)由 `build-related-pages.js` 写,SKILL.md **不**手写(Q5 死循环防护)

### 2.4 双向反链字段(由 `build-related-pages.js` 写)

**source 页 → `## 相关页面(Related Pages)`**:

```markdown
## 相关页面(Related Pages)

### Entities

- [[andrej-karpathy]]
- [[openai]]

### Concepts

- [[llm-wiki]]
```

- 按 `### Entities` / `### Concepts` 两个固定子标题分组
- 每条用目标页 `[[wikilink]]`(裸文件名或 aliases 别名;主推 PRD §10 Q9)
- 某组空 → 删该子标题;全空 → 删整个区块
- **v0.5.6 起改为追加模式**:每次 ingest 在区块末尾追加新确认的反链(去重 wikilink 字符串),保留人工写的条目。同 wikilink 重复 → 保留人工条目 + stderr WARN。如需完全重建,先手工删除 `## 相关页面` / `## 来源资料` 区块再跑脚本。

**entity/concept 页 → `## 来源资料`**:

```markdown
## 来源资料

- [[iso26262]]
- [[llm-wiki-pattern]]
```

- 按 source `title` 排序 wikilink
- 无 source 引用 → 区块不存在 + 本次有引用 → 新建区块;区块已存在 → 保留 + 末尾追加
- **v0.5.6 起改为追加模式**,同 source 页规则

---

## 3. CI 矩阵

### 3.1 平台 / Node 版本

| 项 | 基线 | 锁的方式 |
|---|---|---|
| Node.js | LTS(20.x 或更新) | `package.json` `engines.node: ">=20"`(已锁) |
| Python | 3.10+ | 仅 OCR 路径需要;`engines` 不锁(脚本 `python3` 自检) |
| OS | Windows 10+ / macOS 13+ / Ubuntu 22.04+ | CI 多平台 matrix |
| PaddleOCR | 2.7.x | `package.json` 不锁;SKILL.md 启动时 `python -c "import paddleocr"` 探查 |
| `@firecrawl/anydoc` | ^0.2.4 | `package.json` `dependencies`(已锁) |

### 3.2 CI 触发矩阵

| 事件 | 跑什么 | 目的 |
|---|---|---|
| PR open / push | 单测 + `node --check` 语法 | 防回归 |
| PR merge to master | 单测 + e2e(丢 3 类文件走完 ingest)+ 跨平台 smoke | 集成验证 |
| tag push `v*` | 同上 + `package.json` 版本一致性检查 | 发版前 |
| manual dispatch | 全部 | 调试 |

### 3.3 依赖校验

ingest 涉及的依赖:

- 强依赖:`@firecrawl/anydoc` ^0.2.4(路径 3 PDF 转换;已锁)
- 强依赖:`js-yaml` ^4.1.0(frontmatter 解析;已锁)
- 强依赖:`ajv` ^8.17.0(frontmatter schema 校验;**新增**!原因:`build-related-pages.js` 解析目标页 frontmatter 时复用 ajv 做轻量校验)
- 可选:`paddleocr`(路径 4 OCR;Python 包;**未装 → 路径 4 FAIL,不静默降级**,对齐 G6)
- 可选:`docling`(路径 3 docx/pptx/xlsx;Python 包;**未装 → 路径 3 部分 FAIL**)

> **新增 `ajv` 依赖**(init 不需要,ingest 需要解析 entity/concept 子页 frontmatter 时复用 ajv 做轻量校验;`package.json` `dependencies` 已锁 ^8.17.0)。

### 3.4 静态检查

- `node --check scripts/ingest/*.js`(语法)
- `node --check scripts/ingest/test/*.test.js`(测试语法)
- ESLint 可选(实现期决定;Ponytail 默认不开)

---

## 4. 测试用例表

> 对齐 `prd.md §7` 中 ingest 涉及的所有 AC / NFR / COMPAT。每条标"测什么 / 怎么测 / 通过标准 / 优先级"。
>
> **测试方式**:Node.js 内置 `node:test` + `node:assert` + `node:fs/promises`。fixture 放 `scripts/ingest/test/fixtures/`(commit 进 git,小文件)。
>
> **e2e**:在 `temp/` 下跑一个完整 ingest 流程,丢 3 类文件(`.md` / `.pdf` / `.docx`),验证产物结构 + 反链 + log 追加 + lint 通过。

### 4.1 功能验收(对齐 AC-2 / AC-6 / AC-7 / AC-8 / AC-9 / AC-10 / AC-14 / AC-15 / AC-16)

| ID | 测什么 | 怎么测 | 通过标准 | 优先级 |
|---|---|---|---|---|
| AC-2 | ingest `raw/okf-spec.md` → ≥ 5 个 OKF 兼容概念页;`index.md` 反映新增 | e2e:丢 OKF spec 到 inbox → 跑 SKILL.md → 验证产物 | ≥ 5 个 `type: concept.*` + `index.md` 列出 | P0 |
| AC-6 | 未拍板前 inbox 文件不动;拍板后 → `raw/{subdir}/` + `inbox/{file}` 删除 + `log.md` 留痕 | fixture:dry-run → inbox 不变;--apply → inbox 删 + raw 有 + log.md 有 **Ingest** 条目 | 3 处全验证 | P0 |
| AC-7 | 目标目录不存在 → 经用户拍板才能创建和迁移 | fixture:`raw/99_新分类/` 不存在 → SKILL.md 拍板门 → 创建 + 迁 | 子目录被建 | P0 |
| AC-8 | `inbox/` 为空 → 提示信息,exit 0 | fixture:空 inbox 跑 scan-inbox | scan-inbox 返回 `{files: [], count: 0}` exit 0 | P0 |
| AC-9(G10) | `.pdf` 原生优先 / 失败回退 anydoc 二选一 | 2 fixture:① 原生可读 PDF → `converter: claude-native` + `native_text: true` + `converted_path: null`;② 扫描件 PDF → `converter: anydoc` + `native_text: false` + `converted_path` 非 null | 2 fixture 全过 | P0 |
| AC-10(G10) | `.md` 纯文本 → 不生成 `.converted.md` | fixture:丢 `.md` 到 inbox | `converter: null` + `native_text: true` + `converted_path: null` + 无 `.converted.md` | P0 |
| AC-14 | source 页 `## 相关页面(Related Pages)` 固定含 `### Entities` + `### Concepts`;每次重建;某组空省子标题;全空省整节 | 3 fixture:全填 / 仅 entity / 全空 | 3 fixture 全过 | P0 |
| AC-15 | entity/concept 页 `## 来源资料` 按 source title 排序;完全重建;无 source 省整节;Obsidian 反链面板可见 | 2 fixture:多 source 共享 entity / 无 source entity | 2 fixture 全过 | P0 |
| AC-16 | docling 抽图 → `<basename>.converted.md` + `<basename>.converted_media/` + 所有 `![](image_NN.png)` resolve;lint 副本图片链接 | fixture:丢 .pptx → 走完 → lint 校验 | 副本图片存在 + 链接全部 resolve | P1 |

### 4.2 非功能验收(对齐 NFR-1 / NFR-2 / NFR-4 / NFR-5)

| ID | 测什么 | 怎么测 | 通过标准 | 优先级 |
|---|---|---|---|---|
| NFR-1 | 不引入 MCP / CLI daemon / RAG / embedding | 代码审查:`scripts/ingest/*` 不引用 child_process 启动 daemon;不依赖任何 LLM 包 | grep 无 `spawn` 长驻模式;无 `openai` / `anthropic` / `chromadb` | P0 |
| NFR-2 | plugin 代码 / 文档 / 测试 / schema 各居其位 | 文件路径规范 | `scripts/ingest/*.js` + `scripts/ingest/test/*.test.js` + 引用 `doc/*` 规范 | P0 |
| NFR-4 | 无绝对路径 | grep `scripts/ingest/*.js` 检查路径 | 无 `C:\\` / `/Users/` / `/home/` 等绝对路径 | P0 |
| NFR-5 | 临时文件进 `temp/` | grep `scripts/ingest/*.js` 检查临时目录 | 所有 `os.tmpdir()` 之外写的临时文件路径在 `temp/` 下(`temp/ingest-batch-{ts}.json`) | P0 |

### 4.3 兼容性验收(对齐 COMPAT-1)

| ID | 测什么 | 怎么测 | 通过标准 | 优先级 |
|---|---|---|---|---|
| COMPAT-1 | ingest 产出的 wiki 页 frontmatter 通过 OKF reader 校验 | e2e:跑完 ingest 后用 ajv + `frontmatter.schema.json` 校验所有新增页 | 0 FAIL | P0 |

### 4.4 5 路径分流验收

| ID | 测什么 | 怎么测 | 通过标准 | 优先级 |
|---|---|---|---|---|
| PATH-1 | 路径 1 纯文本 `.md` 不调 `convert-to-md.js` | fixture:丢 `.md` → 跑 SKILL.md → 验证未调 `convert-to-md` | `convert-to-md` 没被 spawn | P0 |
| PATH-2 | 路径 2 PDF 原生可读 → `converter: claude-native` + 无 `.converted.md` | fixture:丢原生可读 PDF | frontmatter 字段值正确 | P0 |
| PATH-3 | 路径 3 PDF 失败 → `converter: anydoc` + `.converted.md` 存在 | fixture:丢扫描件 PDF(anydoc exit 3) | frontmatter 字段值正确 + 副本存在 | P0 |
| PATH-3b | 路径 3 docx/pptx/xlsx → `converter: docling` + `.converted.md` + `_media/` 目录 | fixture:丢 .pptx | frontmatter + 副本 + `_media/` 全在 | P0 |
| PATH-4 | 路径 4 图片 → `converter: paddleocr` + `.converted.md` | fixture:丢 .png(PaddleOCR 已装) | frontmatter + 副本存在 | P1 |
| PATH-FAIL | 路径 4 PaddleOCR 未装 → FAIL,不降级 Python | fixture:不装 paddleocr → 丢 .png | exit non-zero + inbox 文件保留 + 错误提示装 paddleocr | P0 |

### 4.5 raw 子目录拍板门验收(对齐 PRD §4.2 步骤 3)

| ID | 测什么 | 怎么测 | 通过标准 | 优先级 |
|---|---|---|---|---|
| RAW-1 | SKILL.md 提议新子目录 → 用户拍板 → 创建 + 迁 | fixture:丢 1 .md + LLM 提议 `99_新分类/` | 子目录被建 + 文件迁过去 | P0 |
| RAW-2 | raw/{subdir}/ 已存在同名 → `[y]` 覆盖 + 备份到 `temp/raw_backup_{hash}/` + 原子替换 | fixture:raw 已存在同名 → 拍板 `[y]` | 备份目录存在 + 新文件替换 + inbox 删除 | P0 |
| RAW-3 | raw/{subdir}/ 已存在同名 → `[n]` 跳过 + inbox 保留 | fixture:同上 → 拍板 `[n]` | inbox 文件不动 + raw 文件不变 | P0 |
| RAW-4 | raw/{subdir}/ 已存在同名 → `[d]` 仅删旧副本(为保险重新生成 .converted.md) | fixture:同上 → 拍板 `[d]` | raw 旧文件删 + 重新生成 | P1 |

### 4.6 命名飘检测验收(对齐 PRD §4.2 步骤 3 + `lint §5.2`)

| ID | 测什么 | 怎么测 | 通过标准 | 优先级 |
|---|---|---|---|---|
| NAMING-1 | 已有 wiki 页与新抽 entity slug Levenshtein ≤ 2 → WARN 提示强制改用 | fixture:已有 `andrej-karpathy.md` + 新源页含 "Andrew Karpathy" | WARN 提示 + 拍板门 | P1 |
| NAMING-2 | 命名飘合并提案 → `--fix` lint 应用(不属 M2.2 范围,仅占位) | (lint 任务) | (lint 任务验证) | P2 |

### 4.7 幂等性验收

| ID | 测什么 | 怎么测 | 通过标准 | 优先级 |
|---|---|---|---|---|
| IDEMP-1 | `batch.json` 重跑产出相同(除 log.md) | fixture:跑完 ingest → 不删 batch.json → 重跑 move-to-raw --apply | 产物哈希一致 | P0 |
| IDEMP-2 | `--dry-run` 不写盘,只输出 diff | fixture:跑 `--dry-run`,再跑实,确认 dry-run 没写任何文件 | mtime 一致 / stdout 有 diff 输出 | P0 |
| IDEMP-3 | `build-related-pages.js` 重跑 source 页 `## 相关页面` 完全重建 | fixture:手工往 source 页加 1 条伪 wikilink → 重跑 → 伪条目消失 | 伪条目消失 | P0 |

### 4.8 lint C17/C18/C19 验收(对齐 PRD §4.2 步骤 19 + `design.md §5`)

> C17/C18/C19 由 lint skill 实现(M2.4),M2.2 仅在 SKILL.md 步骤 19 调 lint;本表验证 SKILL.md 是否正确触发 lint。

| ID | 测什么 | 怎么测 | 通过标准 | 优先级 |
|---|---|---|---|---|
| LINT-1 | ingest 完成后 SKILL.md 调 lint,捕获 FAIL/WARN | e2e:跑完 ingest → 调 lint → 捕获输出 | lint 输出包含 C17/C18/C19 检查项 | P0 |
| LINT-2 | FAIL 必须修复后 ingest 才算完成 | fixture:故意制造 C18 矛盾(原生 + 副本)→ 跑 lint | FAIL 列表非空 + SKILL.md 提示修复 | P0 |

### 4.9 e2e 验收

| ID | 测什么 | 怎么测 | 通过标准 | 优先级 |
|---|---|---|---|---|
| E2E-1 | 丢 3 类文件(`.md` / `.pdf` / `.docx`)走完 ingest 流程 | `temp/e2e-ingest-3-files/`:init → 丢 3 文件 → SKILL.md 跑完 → 验证产物 | 3 个 source 页 + 反链 + log + index 更新 | P0 |
| E2E-2 | SKILL.md 拍板门覆盖 5 路径分流 + raw 子目录拍板 + 命名飘 | (在 E2E-1 fixture 上扩展) | 5 路径全部覆盖 | P1 |

---

## 5. 部署策略

### 5.1 plugin 本体版本号

- `package.json` `version` = 与 `schema.md` 顶部 `plugin 版本` 字段**强一致**
- 当前 `schema.md 0.5.6` → `package.json 0.5.6`(M2.1 init 落实现时已同步,后随 M2.2 升到 0.5.6)
- M2.2 落地后 → 是否升号待用户拍板(对齐 implement-init.md §5.1);M2.2 **不**强升 minor,除非加了对外可见的新字段或行为

### 5.2 跨版本兼容

- ingest 对老版本 plugin 生成的项目做"幂等兼容":re-run init 后跑 ingest,产物结构与新项目一致;老项目的 `knowledge/index.md` 等被 `aggregate-index.js` 完全重建(PRD §7.3 幂等策略)

### 5.3 用户工程的 scripts/ 同步策略

对齐 `prd.md §4.1 表 scripts/* 行`:init 时拷全部 `scripts/`(含 init/ ingest/ query/ lint/ synthesize/ anydoc/ ocr/ update-check),re-run init 缺失补建、已有不覆盖。

### 5.4 ingest 输出分发路径

- `scripts/ingest/*` → plugin 本体 `aeps-llm-wiki-plugin/scripts/ingest/`
- ingest 跑时 → 用户工程 `{project}/scripts/ingest/*`(由 init 拷贝)
- ingest 不在用户工程写 SKILL.md(SKILL.md 留在 plugin 本体,Claude Code 通过 plugin 机制加载)

### 5.5 临时文件

- 单次 ingest batch:`temp/ingest-batch-{ISO-timestamp}.json`;用完即删(SKILL.md 步骤 19 跑完 lint 后删)
- e2e fixture:`temp/e2e-ingest-*/`(用完即删,`scripts/ingest/test/cleanup.js` 在 CI 跑完自动清)
- raw 备份:`temp/raw_backup_{hash}/`(拍板 `[y]` 覆盖时);**SKILL.md 步骤 19 后保留**(用户可能想找回旧版)
- SKILL.md 跑 ingest 时不创建 `os.tmpdir()` 之外的其他临时目录

---

## 6. 风险与回滚点

### 6.1 失败语义(权威源;v0.5.6 起 SKILL.md 引用此处)

> **本节是失败语义的唯一权威表**(P3-3 修复:`skills/aeps-llm-wiki-ingest/SKILL.md` 不再独立维护失败语义表,改为引用本节)。SKILL.md 步骤遇到失败时按本表 G3 / G6 / G10 对照处理。

| 规则 ID | 覆盖场景 | 期望行为 | 对应 SKILL.md 步骤 |
|---|---|---|---|
| G3 | `convert-to-md.js` spawn 失败(spawnSync 不抛 exit 0 或 exit non-zero);**任意路径 3/4 失败都 FAIL,不降级** | 原文件保留 inbox;batch.json 该条 status=failed;步骤 19 报 FAIL | 步骤 2 |
| G6 | `build-related-pages.js` ajv schema 校验失败(任意 frontmatter 字段不通过 `frontmatter.schema.json` 校验);entity/concept 任意子页失败 | FAIL,该 page 不入库(不进 knowledge/);stderr WARN;反链略过此页 | 步骤 12 |
| G10 | preflight 缺依赖 / `--plugin-root` 解析失败 / plugin-root 不存在 | inline ERROR + 精确 `npm install <pkg>` 命令,exit 2,**不自动装**;用户拍板手动装 | 步骤 0(可跳过,inline 兜底) |

> 与旧 SKILL.md 表的差异说明:
>
> - 旧 SKILL.md "convert-to-md.js spawn 失败" 行 → 对齐本表 G3(语义扩为"任意路径 3/4 失败都 FAIL")
> - 旧 SKILL.md "路径 4 paddleocr 未装 → FAIL 不降级" → 是 G3 的子场景
> - 旧 SKILL.md "build-related-pages 字段不匹配 / ajv 校验失败" → 合并为本表 G6
> - 旧 SKILL.md "move-to-raw 覆盖 raw 已存在同名" → 不在本表(G3/G6/G10 之外的"用户拍板门"场景,归 SKILL.md 步骤 4 处理)

### 6.2 风险表

| 风险 | 影响 | 缓解 |
|---|---|---|
| `convert-to-md.js` spawn 失败(spawnSync 不抛 exit 0) → 见 G3 | path 3/4 失败 → 原文件保留 inbox | 每个 spawn 包 try/catch + FAIL 提示用户手动跑底层脚本;`move-to-raw` 步骤前置依赖 `convert-to-md` 完成 |
| `move-to-raw.js` 覆盖 raw 已存在同名 → 用户误操作 | 旧文件丢失 | 先备份到 `temp/raw_backup_{hash}/` + 原子替换(`os.replace`);SKILL.md 拍板门强制 `[y]/[n]/[d]` |
| `build-related-pages.js` 双向反链循环(source A → entity X,source B → entity X,且 X 又被 source A 通过 wikilink 引用) | 误判为反链 | 反链只看 frontmatter `sources[].resource` 字段,不解析正文 wikilink;避免循环 |
| docling 转换慢(11 页 ~82s) | SKILL.md 步骤 2 阻塞 | 路径 3 PDF 优先 anydoc(<1s),docling 仅在 docx/pptx/xlsx 走;SKILL.md 步骤 2 显式提示"docling 转换可能慢" |
| PaddleOCR 未装 → 路径 4 FAIL → 见 G3 | 图片无法 ingest | SKILL.md 步骤 0 探查 `python -c "import paddleocr"`,未装 → 步骤 2 跳过路径 4 拍板门 + 提示用户装 |
| ajv 校验 entity/concept 子页 frontmatter → 错字段类型 → 见 G6 | 反链错 | 用 ajv + `frontmatter.schema.json` 兜底,失败 → 报错退出 + SKILL.md 提示 |
| `batch.json` 大文件(100+ ingest 文件) → 内存涨 | 性能 | 按需读取 + 限制单次 ingest 上限 50 文件(超过 → 提示分批) |
| Windows 路径反斜杠 `\` vs `/` 在 frontmatter `source_file` wikilink 渲染失败 | Obsidian 渲染错 | `source_file` 写时统一用 `/`(参考 `gen-page.js` 已用 `/`);`converted_path` 同样 |
| `temp/ingest-batch-{ts}.json` 残留 → 下次 SKILL.md 误读 | 状态污染 | SKILL.md 步骤 0 检测残留 → 提示用户确认删除;e2e cleanup 自动删 |
| 跨平台 spawn `.cmd`(Windows) vs 不用 shell(macOS/Linux) → 见 G3 | 路径 3/4 失败 | `convert-to-md.js` 派发用 `process.platform === "win32"` 决定 `shell: true`,与 anydoc_pdf_to_md.js 已实现对齐 |

### 6.3 回滚点

- **整个 M2.2 没落地前的回滚**:`git checkout HEAD -- scripts/ingest/` 一键回滚 SKILL.md + scripts
- **单次回滚**:用户发现本次 ingest 错了 → `temp/raw_backup_{hash}/` 找旧版恢复 + `inbox/{file}`(若未删)直接拷回去;`knowledge/sources/<slug>.md` 手动删
- **`gen-page.js` / `aggregate-index.js` 不修改**,本次 M2.2 不引入它们的不兼容变更
- **不**对 ingest 写"事务回滚"机制(单文件 → 拍板门 + 备份已够;Ponytail 默认行为)

### 6.3 不应(显式禁)

- ❌ 不应在 ingest 中"自动 `npm install`"任何依赖——用户工程可能未配 npm;若需依赖,SKILL.md 提示用户手动装
- ❌ 不应在 ingest 中调 git 命令(G7 不强制 git,用户可能用 SVN / Mercurial)
- ❌ 不应 ingest 中执行任何 `child_process.spawn` 启动 daemon / watch / serve(对齐 NFR-1)
- ❌ 不应在 `convert-to-md.js` 内自动装 `paddleocr`(用户工程可能未配 pip);缺依赖 → FAIL + SKILL.md 提示用户手动 `pip install paddleocr`
- ❌ 不应在 ingest 中创建 Obsidian `.obsidian/` 配置(项目级 Obsidian 配置由用户自己管)

---

## 7. 引用

- 上游契约:
  - [prd.md v0.4.1 §4.2](../design/prd.md)—— ingest 功能需求 + 流程表(19 步)+ AC-2/6/7/8/9/10/14/15/16 + NFR-1/2/4/5
  - [design.md v0.1.1 §3.2 + §4 + §6 + §7.1-§7.3](../design/design.md)—— 5 路径分流 + 脚本契约 + Source 骨架 + 不重转 + 原生优先 + 幂等
  - [schema.md v0.5.5 §1.1 + §2](../schema/schema.md)—— ingest 工作流 + 22 项硬枚举
- 规范字典:
  - [doc/template/rawdir-spec.md](../template/rawdir-spec.md)—— 15 raw 子目录字典
  - [doc/template/concept-entities-spec.md](../template/concept-entities-spec.md)—— 14 子类判定示例
  - [doc/template/tag-spec.md](../template/tag-spec.md)—— 6 轴 tag 字典
  - [doc/schema/frontmatter-spec.md](../schema/frontmatter-spec.md)—— frontmatter 字段规范
  - [doc/schema/frontmatter.schema.json](../schema/frontmatter.schema.json)—— 机器读校验
- 模板:
  - [doc/template/page-source.md](../template/page-source.md)—— source 页模板
  - [doc/template/page-entity.md](../template/page-entity.md)—— entity 通用骨架(v0.5.7 起,7 子类共用)
  - [doc/template/page-concept.md](../template/page-concept.md)—— concept 通用骨架(v0.5.7 起,7 子类共用)
- 已有可复用脚本:
  - `scripts/gen-page.js`—— 22 type 全齐的骨架生成
  - `scripts/aggregate-index.js`—— index/overview/glossary 聚合
  - `scripts/anydoc/anydoc_pdf_to_md.js`—— PDF 路径 3 降级
  - `scripts/anydoc/docling_to_md.py`—— docx/pptx/xlsx 路径 3 降级 + 自动 OCR
  - `scripts/ocr/ocr_to_md.py`—— 路径 4 OCR
- 下游消费:
  - `implement-query.md`(M2.3)—— query 命中 source 页后,通过 `converted_path` 直读副本
  - `implement-lint.md`(M2.4)—— lint C17/C18/C19 校验本次 ingest 产出
  - `implement-synthesize.md`(M2.5)—— synthesize 范围扫描包括本次新增 entity/concept

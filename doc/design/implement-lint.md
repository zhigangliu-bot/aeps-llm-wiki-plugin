# aeps-llm-wiki-plugin — implement-lint (M2.4)

> **状态**:frozen(v0.1.1,2026-09-13 用户确认 v0.1.0 后落地修正:收编 C15.5 + 新增 C21 承接 AC-16 + 契约注记)

## Change History

| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1.1 | 2026-09-13 | 质检落地修正:§2 收编 C15.5 行 + 新增 C21(source converted_path 副本图片链接 resolve,承接 PRD AC-16 docling 抽图回归)+ §0.1 规则数 13 → 14 + §1.1 契约注记(`fixed[]` 仅 `--fix` 时存在 / 补 `c20_free_sections[]` 加性字段)+ §4 C3 fix 措辞对齐实现(按 C17 规范顺序插入、复扫 C3/C17 双清)+ §2.3 矛盾候选对上限 20 注记 + §2 C15.4 措辞对齐 AC-12 + §5 补 U-C21 测试行 | zhigang.liu(Claude Code) |
| v0.1.0 | 2026-09-13 | 冻结候选初版:单脚本 `scripts/lint/lint.js`(扫描 + `--fix` 一体)+ 规则定稿表 13 条(C1-C9 + C17-C20 + C15.4;C4 空缺不复用)+ C17 运行时读模板零漂移 + C9 半成品骨架页(§2.4 模板逐字行排除法)+ C19 以 log.md Ingest 行为判据 + 保留 4 文件豁免 + 测试矩阵 12 组 | zhigang.liu(Claude Code 起草) |
> **上游契约**:`prd.md v0.4.1` §4.4 + AC-4 + `design.md v0.1.1` §5 + §6.4 + `schema.md` + `frontmatter-spec.md`(字段权威)
> **范围**:仅 `aeps-llm-wiki-lint` skill 实现细节;init / ingest / query / synthesize 各有独立文档,本文件不交叉污染
> **完成定义(M2.4 done =)**:本 `implement-lint.md` 冻结 + `skills/aeps-llm-wiki-lint/SKILL.md` + `scripts/lint/*` 全套写完 + 测试用例先行 + 单元 + e2e + `trellis-check` 全套通过

---

## 0. 任务总览

### 0.1 目标

实现 `/aeps-llm-wiki-lint [--fix]` skill。对 `knowledge/**/*.md` 全量机械体检:

1. 14 条规则(C1-C9 + C17-C21,C15.4 承接 analyses 校验;C9 半成品骨架页;C21 承接 AC-16 副本图片链接)→ FAIL / WARN 分级
2. 孤儿 / 陈旧 / 漏链 / 命名飘 机械扫描 → WARN 候选;矛盾 = LLM 判定(脚本不产出)
3. `--fix` 分流:确定性结构修复(直接 patch + log `**LintFix**`)vs 语义级问题(仅 stdout `**LintProposal**` 提案,等用户拍板)
4. C20 溯源自检报告:SKILL.md 输出,软约束不 FAIL

### 0.2 不做(明确边界,避免 scope creep)

- **不做**矛盾自动判定(语义级,LLM 在 SKILL.md 步骤做,脚本零产出)
- **不做**语义级自动修复:矛盾 / 命名飘合并 / 漏链 / 陈旧页处理永远只出提案,`--fix` 不改文件(Q7 死循环防护)
- **不修改** `gen-page.js` / `aggregate-index.js` / `scripts/ingest/*` / `scripts/query/*` 本体(冻结产物)
- **不做** `stale_after` 未填页的陈旧推断(未填一律静默跳过,不报陈旧、不 WARN)
- **不新增** npm 依赖(ajv / js-yaml 已有;纯 Node 内置 fs / path)
- **不自动 commit**、不调 git、不刷 index(--fix 不改名不删页,index 无需重建)

### 0.3 上下游

- **上游**:init(目录骨架 + 4 保留文件)、ingest(sources/entities/concepts 页)、query(analysis 页 + `> 引用:` 行)、synthesize(synthesis 页)
- **下游**:用户拍板语义级提案后手动 / LLM 辅助修复;synthesize 前置"lint 跑过"

---

## 1. 脚本清单

单脚本拓扑:检测逻辑只在 `lint.js` 一处,`--fix` 复用同一趟扫描结果原地 patch,无报告文件交接。

| 脚本 | 新建/复用 | 职责 | PRD §4.4 步骤 |
|---|---|---|---|
| `scripts/lint/lint.js` | 新建 | 全量扫描 → FAIL/WARN 报告(--json);`--fix` 确定性修复 + log 追加 | 0-12 全部 |

```bash
node scripts/lint/lint.js --project <用户工程根> [--fix] --json
```

- `--project` 必填,显式传(同 query 惯例;脚本内无默认值,无绝对路径)
- exit code:`0` 成功(含 wiki 为空)/ `1` 用法或环境错误 / `2` 存在 FAIL(--fix 后仍剩 FAIL 也为 2)
- stdout:JSON 报告(`--json`)或人读文本;诊断到 stderr

### 1.1 JSON 报告契约

```jsonc
{
  "pages_scanned": 42,              // 非保留文件页数
  "reserved_skipped": 4,            // index/overview/glossary/log
  "fails":    [ { "rule": "C1", "file": "entities/product/s32g.md", "detail": "缺少必填字段 updated" } ],
  "warns":    [ { "rule": "C6", "file": "syntheses/xxx.md", "detail": "sources_count=2 < 3" } ],
  "proposals":[ { "kind": "orphan|stale|missing-link|name-drift|contradiction-hint",
                  "file": "...", "detail": "...", "fixable": false } ],
  "fixed":    [ { "rule": "C1", "file": "...", "action": "补 frontmatter updated" } ],  // 仅 --fix 时存在(无 --fix 零写入,字段缺省)
  "c20_free_sections": [ { "file": "sources/xxx.md", "sections": ["阅读路线"] } ],  // 加性字段:C20 自由追加节清单(有才输出;SKILL.md 溯源自检消费)
  "stats":    { "fail": 3, "warn": 7, "proposal": 4, "fixed": 2 }
}
```

---

## 2. 规则定稿表(编号演化至此冻结)

> design §5 声明"具体编号规则实现期定",本表为定稿。C4(v0.5.6 起 analyses 不再校验 H2 骨架)被 C15.4 取代,编号 C4 保留空缺不复用。

| 规则 | 级别 | 校验内容 | 适用 type | `--fix` |
|---|---|---|---|---|
| C1 | FAIL | frontmatter 必填 + 类型(§2.1 必填表;ajv + frontmatter.schema.json 先验,再加 per-type 补充表) | 全部 | 补占位 / 强转(§4) |
| C2 | FAIL | `## 摘要` / `## Summary` H2 残留 | 全部 | 内容迁 frontmatter `summary` 后删 H2 |
| C3 | FAIL | source 3 节骨架:`## 重点摘录` + `## 我的思考` + `## 总结:最有收获的一句话` | source | 文末追加占位 H2 |
| C5 | FAIL | `sources` 字段必填非空 | comparison | 提案(值语义未知) |
| C7 | FAIL | `sources_used` 每条解析到真实 `knowledge/**/*.md` | analysis | 提案(删哪条语义未知) |
| C15.4 | FAIL | analysis 正文任意位置存在 `> 引用:` 行(习惯文末,AC-12) | analysis | 按 `sources_used` 生成追加 |
| C15.5 | WARN | 标准 markdown 链接残留(仅 knowledge 内页目标;raw/http 不转) | 全部 | 转 [[wikilink]] |
| C17 | FAIL | 模板一致性:模板必有 H2 存在且相对顺序一致(§2.2);运行时读 `<project>/doc/templates/` 提取,与 gen-page.js 同源零漂移 | 全部(按型) | 提案 |
| C18 | FAIL | source 三字段一致性矛盾:`converter: claude-native` 且 `converted_path` 非 null / `native_text: true` 且 `converted_path` 非 null / converter 非空但 `native_text ≠ false` | source | 提案 |
| C9 | FAIL | 半成品骨架页:正文无实质内容(判定见 §2.4) | 全部 | 提案(填正文 / 删页由用户拍板) |
| C6 | WARN | `sources_count < 3` | synthesis | 无 |
| C8 | WARN | `> 引用:` 行 wikilink Set ≠ `sources_used` Set | analysis | 重写该行对齐 `sources_used` |
| C19 | WARN | converter ∈ {pyoffice, anydoc, docling, libreoffice, paddleocr}(路径 3/4)但 `knowledge/log.md` 无含该原文件名的 `**Ingest**` 行 | source | 提示补 log |
| C20 | 软约束 | source 页 `## 维护说明` 之前非 3 节必选 H2 → 标记「自由追加节」清单进报告;**不 FAIL**(§6.4) | source | 无(自检报告) |
| C21 | WARN | source converted_path 副本图片链接 resolve(AC-16) | source | 无 |
| C1t | WARN | tags 数量 < 5 / > 10,或缺 `docform/` + `domain/` 必填轴 | 全部 | 提案 |

### 2.4 C9 半成品骨架页判定

**实质内容行** = 页面去掉 frontmatter 后的全部行,减去:

- 标题行(`#` ~ `######`)
- 脚本生成区块整节:`## 维护说明(` / `## 相关页面(Related Pages` / `## 关联导引(Related Links` / `## 来源资料(由 ingest 自动生成)` / `## 字段一致性 lint` 起至下一 H2 或文末
- 空行
- **逐字出现在对应 type 模板文件中的行**(运行时读 `<project>/doc/templates/page-*.md`,与 C17 同源;gen-page v0.6.5 起「模板内容 = 脚本输出」,未填骨架的正文行全部逐字来自模板,故该口径零误报、零占位符正则)

**实质内容行数 == 0 → C9 FAIL**(gen-page 出骨架后 LLM 一直没填的半成品页)。LLM / 用户写过任意一行真内容即通过。

`--fix` 不自动填正文(语义级):输出 `**LintProposal**`,提示用 ingest / query / synthesize 对应流程补正文,或经用户拍板删除该页。

### 2.1 C1 per-type 必填字段表(权威 = frontmatter-spec §4 / §11.7 / §13)

| type | 必填(缺失 → FAIL) |
|---|---|
| 全部 | `type` / `updated` / `title` / `description` / `tags` |
| source | + `resource`(单源必填)/ `format` / `converter` / `native_text` / `converted_path` / `source_file` |
| analysis | + `answer_to` / `sources_used` / `sources_count` / `summary` |
| synthesis | + `sources_count` / `summary` |
| comparison | + `sources` / `sources_count` / `summary` |
| entity / concept | (无额外) |

### 2.2 C17 模板必有 H2 表(运行时从模板文件提取,本表为验收基准)

| type | 模板必有 H2(须为页面 H2 序列的**子序列**,自由追加节不破坏) |
|---|---|
| source | `## 重点摘录` → `## 我的思考` → `## 总结:最有收获的一句话` → `## 相关页面(Related Pages` → `## 维护说明(` |
| entity / concept | `## 关联导引(Related Links` → `## 来源资料(由 ingest 自动生成)` → `## 维护说明(` |
| analysis / comparison / synthesis | `## 关联导引(Related Links` → `## 维护说明(`(v0.5.6:analysis 不锁正文骨架) |

注:H2 前缀匹配(模板行含括号注释,页面行须以相同前缀开头);保留 4 文件不参与。

### 2.3 无编号机械扫描(PRD §4.4 步骤 10)

| 规则 | 级别 | 判定 |
|---|---|---|
| 孤儿页 | proposal | 全 wiki 无任何其他页正文 `[[该页 basename]]` 链入 |
| 陈旧页 | proposal | `stale_after` 已填(ISO 日期)且 < 今日;**未填一律静默跳过** |
| 漏链 | proposal | 其他页 basename / aliases 在本页正文出现 ≥ 2 次但无对应 wikilink |
| 命名飘 | proposal | 同 type 子目录内文件名 Levenshtein ≤ 2 或互为前缀(≥ 4 字符) |
| 矛盾 | proposal(hint) | 脚本仅列同 topic 候选页对(候选对上限 20,防大 wiki 刷屏);判定由 LLM 在 SKILL.md 步骤做 |

---

## 3. SKILL.md 编排(对齐 PRD §4.4 流程表)

1. **步骤 0**:跑 `lint.js --json`;`pages_scanned == 0` → "wiki 为空,先 init + ingest",exit 0(阻塞)
2. **步骤 1-11**:脚本一趟完成;LLM 解读报告:FAIL 逐条列(阻塞点:先报告,未经同意不改文件)
3. **LLM 语义审查**:读 proposal 候选对 → 矛盾判定;输出 C20 溯源自检报告(重点摘录 / 自由追加节逐条断言复核提示)
4. **步骤 12 拍板**:用户同意 → 重跑 `lint.js --fix`(确定性项 patch + log `**LintFix**`);语义级项仅 stdout `**LintProposal**` 提案行,等用户后续拍板
5. **不应**:无 `--fix` 时静默修改任何文件

---

## 4. `--fix` 确定性修复明细(直接 patch + log)

| 项 | 行为 |
|---|---|
| C1 缺字段 | 补占位:`updated` ← 当前 ISO 时间;`title` ← H1 文本;`description` ← `""`;`tags` ← `["docform/other", "domain/other"]`(取值对齐 tag-spec);`sources_count` ← `0`;`summary` ← `""`。**不补**:`converter` / `converted_path` / `source_file` / `answer_to` / `sources_used` / `resource`(值语义未知 → 提案) |
| C1 类型错位 | 强转:`tags` 字符串 → 单元素数组;`sources_count` / `sources_count` 数字字符串 → 整数;`native_text` "true"/"false" → 布尔 |
| C2 残留 | H2 下内容迁 frontmatter `summary`(空 → 迁入;非空 → 空行拼接),删除该 H2 区块 |
| C3 / C15.4 缺失 | 按 C17 规范顺序插入缺失节占位 H2(source 3 节;保持模板 H2 子序列,复扫 C3/C17 双清)/ 按 `sources_used` 生成 `> 引用:` 行(仅当 C7 无 FAIL 项) |
| C8 不一致 | 重写 `> 引用:` 行与 `sources_used` Set 一致(仅当 C7 无 FAIL 项) |
| md 链接残留 | 正文 `[text](目标.md)` 且目标解析到 `knowledge/**/*.md` → `[[basename]]`(text == basename)或 `[[basename|text]]`;指向 `raw/` 等非 wiki 页的链接不转 |

每次 `--fix` 运行在 `knowledge/log.md` 当日 `## [YYYY-MM-DD]` 节末尾追加一行 `**LintFix**: <n> 个文件确定性修复(C1×2, C2×1, ...)`(节不存在则按 latest-first 新建;log 插入逻辑在 lint.js 内实现 ~40 行,不改动冻结的 `scripts/query/append-log.js` —— ponytail:重复小逻辑,query 契约不动)。

---

## 5. 测试矩阵(测试用例先行)

`scripts/lint/test/`(node:test;随 init/ingest 惯例 gitignore,本机跑):

| 组 | 用例 | 断言 |
|---|---|---|
| U-C1 | 缺 updated / 缺 type / tags 字符串错型 | 各 1 FAIL;--fix 后占位补齐 + 强转 |
| U-C2 | `## 摘要` 残留(空 summary / 非空 summary) | FAIL;迁移后 summary 内容正确、H2 删除 |
| U-C3 | source 缺 1 节 / 全缺 | FAIL 数正确;--fix 追加占位 |
| U-C5/C6 | comparison 缺 sources;synthesis count=2 | FAIL / WARN |
| U-C7/C8/C15.4 | sources_used 指向不存在页;引用行缺失;Set 不一致 | FAIL×2;WARN×1;--fix 重写行 |
| U-C17 | 删维护说明节 / 自由追加节插入正确位置 | FAIL / 通过(子序列判定) |
| U-C18 | claude-native + converted_path 非 null | FAIL |
| U-C9 | 未填骨架页(正文全为模板行)/ 仅多写一行真内容 / 空白页 | FAIL / 通过 / FAIL |
| U-C19 | 路径 3 页无 Ingest log 行 / 有 | WARN / 通过 |
| U-C21 | converted_path 正常全 resolve / 缺图 / 副本悬空 / converted_path null / http 图 / 缺图 > 5 张 | 零输出 / WARN×1 含图名 / WARN 悬空 / 零输出 / 跳过 / 截断「等 N 个」 |
| U-扫描 | 孤儿 / 陈旧(填与未填)/ 漏链 / 命名飘 | proposal 数与对象正确;未填 stale_after 零输出 |
| E2E | tmp vault:合法页 + 5 类破坏页 → scan(exit 2)→ --fix → 复扫(exit 0)+ log 有 LintFix 行 | 全链路 |
| 契约 | wiki 空 exit 0;缺 --project exit 1;保留文件不扫 | exit code |

---

## 6. 风险与回滚

- **G-L1**:`knowledge/` 不存在 → exit 1,提示先 init(同 query G-Q1)。
- **G-L2**:ajv 校验 schema.json 本身失败(spec 与 schema 漂移)→ exit 1 并指明漂移,不带病扫。
- **G-L3**:`--fix` 写坏页 → 单文件 patch 前 no backup 策略不可接受?**保留策略**:fix 前整文件内容仅存内存,patch 是幂等字符串替换;写坏 → git / 手改恢复(lint 不引入备份文件,对齐 cleanup-backups 已有治理)。
- 模板 H2 表(§2.2)与 `<project>/doc/templates/` 漂移 → C17 运行时读模板为准,本表仅验收基准;模板大改时同步本表并记 Change History。

---

## 7. 引用

- 上游:`prd.md` §4.4 + AC-4;`design.md` §5 / §6.4;`frontmatter-spec.md` §4 / §11.7 / §13(字段权威)
- 模板:`doc/template/page-*.md`(C17 基准)+ `doc/template/page-log.md`(LintFix / LintProposal 前缀)
- 同源实现:`scripts/gen-page.js`(GENERATED_H2_PATTERNS / 模板读取)、`scripts/query/append-log.js`(log 节插入语义参照)

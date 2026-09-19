---
name: aeps-llm-wiki-lint
description: 对 knowledge/ 做全量机械体检,规则定稿表 FAIL/WARN 分级报告 + 孤儿/陈旧/漏链/命名飘/矛盾候选扫描;先报告后动手,用户拍板才 --fix 做确定性修复,矛盾判定与 C20 溯源自检由 LLM 完成,语义级问题只出 LintProposal 提案
plugin-version: 0.6.9
allowed-tools: Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/lint/lint.js *)
---

## 脚本路径约定

- 本 skill 所有 `node scripts/xxx.js` 命令以 `${CLAUDE_PLUGIN_ROOT}` 为 plugin 根;该变量由调用方注入(plugin 自动注入或用户 shell 导出)。
- 脚本在 plugin 仓根的 `scripts/lint/` 下,**不**在 `skills/<skill>/scripts/` 下。
- `lint.js` 用 `--project <用户工程根绝对路径>` 显式指定工程根,**必须显式传**(脚本内 `import.meta.dirname` 解析 plugin 路径,不依赖 cwd;用户工程根绝无默认值)。
- `--json` 时输出结构化 JSON 报告到 stdout,诊断 / 进度到 stderr;SKILL.md 用 `JSON.parse` 解析 stdout。
- exit code:`0` 成功(含 wiki 为空)/ `1` 用法或环境错误(缺 `--project`、`knowledge/` 不存在 G-L1、schema 编译失败 G-L2)/ `2` 存在 FAIL(`--fix` 后按剩余 FAIL 判定,仍剩也为 2)。
- 保留 4 文件(`index.md` / `overview.md` / `glossary.md` / `log.md`,任意层级按 basename)与 `knowledge/.aeps-state/` 不扫,计入 `reserved_skipped`。

# /aeps-llm-wiki-lint

对 `knowledge/**/*.md` 全量机械体检:脚本一趟扫描(`lint.js --json`)→ LLM 解读报告(FAIL 逐条列)→ LLM 语义审查(矛盾判定 + C20 溯源自检报告)→ 用户拍板后才 `--fix`(确定性项 patch + log `**LintFix**`;语义级只出 `**LintProposal**` 提案)。默认只读,**无 `--fix` 零写入**。

## 触发

用户跑 `/aeps-llm-wiki-lint`(默认只读体检)或 `/aeps-llm-wiki-lint --fix`(用户已预授权确定性修复)。

- 用户显式带 `--fix` 触发 → 视为已对确定性修复拍板,步骤 0 直接 `--fix --json`,报告解读时一并覆盖 `fixed[]`;语义级仍只出提案。
- 默认(无 `--fix`)→ 严格走步骤 0 只读扫描 → 步骤 12 拍板后才重跑 `--fix`。

## 设计原则(必读)

- **先报告后动手**(步骤 12 拍板门):FAIL 逐条列给用户,未经用户明确同意不改任何文件;拒绝 `--fix` → 零写入结束。
- **确定性 vs 语义级分流**(PRD Q7 死循环防护):`--fix` 只 patch 确定性结构项 + 追加 log `**LintFix**` 行;语义级问题(矛盾 / 命名飘合并 / 漏链 / 陈旧页 / 半成品页正文 / 骨架重排 / 值语义 / tags 代定 / 补 log / 副本缺图重转 C21)**永远只出 `**LintProposal**` 提案**,`--fix` 不改文件。
- **矛盾判定归 LLM**:脚本只列同 topic 候选页对(`kind: contradiction-hint`),矛盾是否成立由 LLM 读页判定,脚本零产出结论。
- **溯源自检是软约束**:C20 不 FAIL,由 LLM 输出「重点摘录 / 自由追加节 溯源自检报告」,无法溯源的断言显式标注 `[来源不足,需人工复核]`,等用户复核;`--fix` 不自动改写用户认可的内容。
- **stale_after 未填一律静默跳过**:不报陈旧、不 WARN、不猜(非 ISO 日期也不猜)。
- **LLM 不做机械判定**:规则评估 / 阈值比较 / Set 比对 / 路径解析全部由 `lint.js` 机械判定;LLM 只做报告解读、矛盾语义判定、溯源自检。

## 编排流程(对齐 PRD §4.4 流程表步骤 0-12)

### 步骤 0:全量扫描(阻塞)

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/lint/lint.js --project <用户工程根> --json
```

读 stdout JSON(§1.1 契约):`pages_scanned` / `reserved_skipped` / `fails[]` / `warns[]` / `proposals[]` / `stats`(加性字段:`c20_free_sections[]`;仅 `--fix` 时另有 `fixed[]`)。

- `pages_scanned == 0` → **wiki 为空**:提示"wiki 为空,先跑 `/aeps-llm-wiki-init` + `/aeps-llm-wiki-ingest` 再 lint",本次结束(exit 0,不是失败)。
- exit 1 → 失败语义 G-L1 / G-L2(见失败语义节),停止。
- exit 2 → 存在 FAIL,正常进入报告解读。
- exit 0 且 `pages_scanned > 0` → 无 FAIL,仍解读 WARN / proposal。

### 步骤 1-11:规则扫描(脚本一趟完成,只读)+ 报告解读(阻塞)

PRD §4.4 步骤 1-11 的全部规则评估由脚本一趟完成,LLM 读 JSON 解读:

- `fails[]`(`{rule, file, detail}`):**FAIL 逐条列给用户**(阻塞点:先报告,未经同意不改文件)。
- `warns[]`(`{rule, file, detail}`):逐条列,注明 WARN 级不阻塞。
- `proposals[]`(`{kind: orphan|stale|missing-link|name-drift|contradiction-hint, file, detail, fixable}`):语义级候选,只提案。
- `stats`:`{fail, warn, proposal, fixed}` 汇总收尾。

规则定稿表(implement-lint.md §2 冻结;C4 编号空缺不复用;JSON 字段契约权威 = implement-lint.md §1.1,行为权威 = scripts/lint/lint.js):

| 规则 | 级别 | 校验内容 | `--fix` |
|---|---|---|---|
| C1 | FAIL | frontmatter 必填 + 类型(ajv + schema 先验 + per-type 补充表) | 补占位白名单(`updated`←当前 ISO / `title`←H1 / `description`←`""` / `tags`←6 轴兜底 2 条 / `sources_count`←0 / `summary`←`""`;**不补** converter / converted_path / source_file / answer_to / sources_used / resource → 提案)+ 强转(tags 字符串 → 单元素数组 / sources_count 数字字符串 → 整数 / native_text "true"/"false" → 布尔) |
| C1t | WARN | tags 数量 < 5 / > 10,或缺 `docform/` + `domain/` 必填轴,或单条非 6 轴字典格式(对齐 tag-spec 六轴) | 提案(--fix 不代定 tags) |
| C2 | FAIL | `## 摘要` / `## Summary` H2 残留 | 内容迁 frontmatter `summary` 后删 H2 区块 |
| C3 | FAIL | source 3 节骨架(重点摘录 / 我的思考 / 总结:最有收获的一句话) | 文末追加占位 H2 |
| C5 | FAIL | sources 分治(M2A N4):analysis / synthesis / comparison `sources` 必填非空;其余 type 出现 `sources` → FAIL | 三综合类缺失/空 → 提案(值语义未知);非综合类 → `--fix` 删除该字段 |
| C6 | WARN | synthesis `sources_count < 3` | 无 |
| C7 | FAIL | analysis `sources_used` 每条解析到真实 `knowledge/**/*.md` | 提案(删哪条语义未知) |
| C8 | WARN | `> 引用:` 行 wikilink Set ≠ `sources_used` Set | 重写该行对齐 `sources_used`(仅当该页 C7 无 FAIL 项) |
| C9 | FAIL | 半成品骨架页(§2.4 模板逐字行排除法,实质内容行 == 0) | 提案(填正文 / 删页由用户拍板) |
| C15.4 | FAIL | analysis 正文存在 `> 引用:` 行(任意位置,习惯文末) | 按 `sources_used` 生成追加(仅当该页 C7 无 FAIL 项) |
| C15.5 | WARN | 标准 markdown 链接残留(`[text](目标.md)`) | 转 `[[basename]]`(text == basename)或 `[[basename|text]]`;指向 `raw/` 等非 wiki 页的链接不转 |
| C17 | FAIL | 模板一致性:模板必有 H2 须为页面 H2 序列子序列(运行时读 `<project>/doc/templates/page-*.md`,与 gen-page.js 同源零漂移);**analysis 豁免 `## 关联导引` 键**(analysis 仅要求 `## 维护说明(`,与 query「analysis 不锁 H2 骨架」承诺一致,删该节不 FAIL) | 提案(--fix 不代排骨架) |
| C18 | FAIL | source 三字段一致性矛盾(claude-native + converted_path 非 null / native_text true + converted_path 非 null / 真转换器(markitdown/pyoffice/anydoc/docling/libreoffice/paddleocr)但 native_text ≠ false;`converter: claude-native` 豁免第 3 条 —— 它与 native_text 正交,表示「Claude 原生直读无副本」,是 path 1/2 的默认合法组合) | 提案 |
| C19 | WARN | converter ∈ {markitdown, pyoffice, anydoc, docling, libreoffice, paddleocr} 但 `knowledge/log.md` 无含该原文件名的 `**Ingest**` 行 | 提案(提示补 log) |
| C20 | 软约束 | source 页 `## 维护说明` 之前非 3 节必选 / 非脚本生成区块的 H2 → 「自由追加节」清单 | 无(进 LLM 溯源自检报告,不 FAIL) |
| C21 | WARN | source converted_path 副本图片链接 resolve(AC-16;`.converted.md` 悬空单列 WARN;http(s):// 图片跳过不查) | 无(--fix 不改 raw 副本) |

无编号机械扫描(全部 proposal 级,`fixable: false`):孤儿页(全 wiki 无任何其他页正文 `[[该页 basename]]` 链入;`analyses/` 页豁免 —— 被顶层 `overview.md` / `index.md` 反链即不算孤儿,query 落档后「近期分析」节保证反链)/ 陈旧页(`stale_after` 已填且过期;未填静默跳过)/ 漏链(其他页 basename / aliases 在本页正文出现 ≥ 2 次但无对应 wikilink)/ 命名飘(同 type 子目录内 Levenshtein ≤ 2 或互为前缀 ≥ 4 字符)/ 矛盾 hint(仅候选对)。

边界行为:模板缺失(`<project>/doc/templates/` 缺对应文件)→ C9 / C17 **降级 WARN** 并注明,不 crash;单文件读失败 → 跳过并 stderr WARN。

### LLM 语义审查(阻塞)

**矛盾判定**:对 `proposals[]` 中 `kind == "contradiction-hint"` 的候选页对,LLM 逐对读两页正文 → 判定同一事实是否存在不同说法。成立 → 向用户报告矛盾对 + 具体分歧点(出 `**LintProposal**`,修复由用户拍板,--fix 不代做);不成立 → 说明"候选对经语义审查不构成矛盾"。

**C20 溯源自检报告**(design §6.3 / §6.4):对 `c20_free_sections[]`(`{file, sections[]}`)列出的每个 source 页,LLM 读该页 `## 重点摘录` 与每个自由追加节,**逐条断言**自检能否在该页 `source_file` 指向的源文件(或 `converted_path` 指向的 `.converted.md`)找到依据:

- 找到 → 通过。
- 无法溯源 → **显式标注 `[来源不足,需人工复核]`**,不静默删除、不悄悄改写。
- `## 我的思考` / `## 总结:最有收获的一句话` 不参与溯源自检(LLM 解读产出,本不来自源文件)。
- 软约束:不 FAIL、`--fix` 不自动改写,报告输出后等用户复核。

### 步骤 12:拍板 + `--fix` 分流(阻塞)

**拍板门:用户明确同意才执行**:

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/lint/lint.js --project <用户工程根> --fix --json
```

- 确定性项自动 patch;有修复时在 `knowledge/log.md` 当日 `## [YYYY-MM-DD]` 节末尾追加一行 `**LintFix**: <n> 个文件确定性修复(C1×2, C2×1, ...)`(节不存在按 latest-first 新建;零修复不写 log)。
- 报告 `fixed[]`(`{rule, file, action}`)列出每笔修复;脚本内部复扫,`fails` / `stats` 反映修复后状态;**仍剩 FAIL → exit 2**,剩余项继续按语义级提案解读。
- 语义级项(C5 / C7 / C9 / C17 / C18 / C21 / C1t / C19 / 全部 5 类机械扫描)即使带 `--fix` 也只出 `**LintProposal**` 提案(JSON `proposals[]`,文本模式 `**LintProposal**: [kind] file — detail` 行),等用户后续逐项拍板(合并 / 改名 / 删页 / 补 log / 补正文 / 重转副本),lint 本体不代做。
- 用户拒绝 `--fix` → 到此结束,零写入。

**不应**:无 `--fix` 时静默修改任何文件。

## 拍板门总结

| 时机 | 拍板内容 | 默认 |
|---|---|---|
| 触发时 | 用户命令行带 `--fix` = 预授权确定性修复 | 未带 → 步骤 12 再拍板 |
| 步骤 12 | 是否执行 `--fix` 确定性修复 | 等用户明确;拒绝 → 零写入结束 |
| 步骤 12 后 | 语义级 `**LintProposal**` 逐项(合并 / 改名 / 删页 / 补 log / 补正文) | 等用户逐项拍板;lint 不代做,按对应上游流程处理 |
| C20 复核 | `[来源不足,需人工复核]` 标记断言 | 等用户复核;不 FAIL、不自动改写 |

## 失败语义(权威源 = implement-lint.md §6)

失败语义表权威源:[doc/design/implement-lint.md §6 风险与回滚](../../doc/design/implement-lint.md)。三条 G 系列:

- **G-L1**:`knowledge/` 目录不存在(exit 1)→ 停止,提示先跑 `/aeps-llm-wiki-init` 初始化 vault(同 query G-Q1)。
- **G-L2**:ajv 编译 `frontmatter.schema.json` 失败(疑似 spec 与 schema 漂移,exit 1)→ 停止并指明漂移,不带病扫。
- **G-L3**:`--fix` 写坏页 → patch 是幂等字符串替换、无备份文件;写坏 → git / 手改恢复(lint 不引入备份文件,对齐 cleanup-backups 已有治理)。

其他场景(模板缺失 → C9/C17 降级 WARN / 单文件读失败跳过)归边界处理,不纳入 G 系列。

## wikilink 硬约束(贯穿报告 / 提案 / --fix 所有链接写入)

- 所有写入正文的 wikilink **必须用文件名形式 `[[filename]]`**(目标 .md 去 .md 的 basename),**禁止 title / alias 形式**:Obsidian resolver 只索引文件名 basename,title 形式 wikilink 点击会创建空白页。需要可读别名时写 `[[filename|显示别名]]`(与 ingest / query 同款约束)。
- C15.5 `--fix` 转换同口径:链接 text == 目标 basename → `[[basename]]`;text 为别名 → `[[basename|text]]`;指向 `raw/` 等非 wiki 页的链接**不转**。
- analysis 文末 `> 引用:` 行的 wikilink 列表必须与 `sources_used` **Set 一致**:不遗漏、不多列(C15.4 / C8 承接;`--fix` 重写时以 `sources_used` 为准)。

## 不做什么(SKILL.md 边界)

- 不做矛盾自动判定(脚本零产出,只列候选对;判定在本 SKILL 语义审查步骤由 LLM 做)。
- 不做语义级自动修复:矛盾 / 命名飘合并 / 漏链 / 陈旧页处理 / C9 半成品页正文 / C17 骨架重排 / C5 / C7 值语义 / C1t tags 代定 / C19 补 log / C21 副本缺图重转 —— `--fix` 永不改,只出提案。
- 不修改 `gen-page.js` / `aggregate-index.js` / `scripts/ingest/*` / `scripts/query/*` 本体(冻结产物;log 节插入逻辑在 lint.js 内实现,不与 append-log.js 契约耦合)。
- 不做 `stale_after` 未填页的陈旧推断(未填一律静默跳过,不报陈旧、不 WARN;非 ISO 不猜)。
- 不新增 npm 依赖(js-yaml / ajv 已有;纯 Node 内置 fs / path)。
- 不自动 commit;不调 git;不刷 index(`--fix` 不改名不删页,index 无需重建)。
- 不扫保留 4 文件(index / overview / glossary / log)与 `knowledge/.aeps-state/`。

## 回滚点

- 步骤 0 至语义审查:**无写副作用**(不带 `--fix` 的 lint.js 纯只读),任意重跑。
- 步骤 12 `--fix`:patch 为幂等字符串替换,重跑结果一致;写坏单页 → git / 手改恢复(无备份文件,G-L3)。
- log.md `**LintFix**` 行写错 → 手改该行。
- 语义级提案误采纳 → 按对应上游流程(ingest / query / synthesize)回退,lint 不代做。

## 引用

- 设计文档:`doc/design/implement-lint.md`(JSON 报告契约 §1.1 / 规则定稿表 §2 + C9 判定 §2.4 / SKILL 编排 §3 / `--fix` 明细 §4 / 失败语义 §6)
- 上游契约:`doc/design/prd.md` §4.4 + AC-4;`doc/design/design.md` §5 / §6.3 / §6.4
- 字段权威:`doc/schema/frontmatter-spec.md` §4 / §11.7 / §13;机器读 `doc/schema/frontmatter.schema.json`(C1 先验)
- 模板:`doc/template/page-*.md`(C17 验收基准;运行时读 `<project>/doc/templates/`,与 `scripts/gen-page.js` 同源零漂移)+ `doc/template/page-log.md`(`**LintFix**` / `**LintProposal**` 前缀)+ `doc/template/tag-spec.md`(C1t 六轴口径)
- 同源实现:`scripts/lint/lint.js`(唯一脚本;扫描 + `--fix` 一体,无报告文件交接)

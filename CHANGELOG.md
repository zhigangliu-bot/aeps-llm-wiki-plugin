# Changelog

All notable changes to `aeps-llm-wiki-plugin` are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.6.12] - 2026-09-30

### Fixed

- **#63 / P1 wikilink 方向** `scripts/gen-page.js`:source_file wikilink 左右段颠倒纠正为 Obsidian 语法 `[[路径|显示名]]`(0.6.10 起产出 `[[slug|path]]`,左段裸 slug 点击只跳同名 wiki 页,无法打开 raw/ 原 PDF)。三处统一:frontmatter 显式输入 `[[path|alias]]`(alias 原样保留)/ 缺省 `[[{subdir/}{slug}.{ext}|{slug}]]` / 正文 `> 原始来源:[[raw/<subdir>/<file>|<末段 stem>]]`;`normalizeSourceFileRef` 返回值扩为 `{stem, path, alias}`,`pickPathierSide` 兼容两种输入方向(0.6.10 旧产物 patch 时自动纠正),幂等与「不出现 `[[[` / `]]]`」不变量保持。`frontmatter-spec.md` §12.5 裁决:frontmatter 路径不带 `raw/` 前缀。同步 `scripts/ingest/lint-stub.js` R7.10 排除 `> 原始来源:` blockquote 行(指向 raw/ 原文件而非 knowledge .md,与 lint.js S1 排除先例对称)。
- **#59 / P1 pdf-route** `scripts/ingest/classify.js`:PDF route 2 判定从「扩展名/元数据即信」改为 `pdftotext` 实抽前 3 页文本验证,每页有效字符 < 10 或抽取失败(损坏/加密/非 PDF)自动降级 route 3;显式 `--route 2` 保留人工兜底跳过探测。
- **#60 / P1 windows-path** `scripts/ingest/convert-to-md.js`:`runPython()` 去掉 Windows 下 `shell: true`,参数数组原样传递,含空格路径不再被拆参;失败分支补 `ENOENT` 明确报错。
- **#61 / P2 type-enum** `scripts/gen-page.js`:`unknown type` 报错追加列出全部 18 个合法 type 及权威源 `frontmatter-spec.md` §4.1.1(`concept.framework` 不在枚举内,不新增类型)。
- **#62 / P1 backlink** `scripts/ingest/build-related-pages.js`:batch 声明条目字符串形态经 `normalizeDeclEntry()` 归一为 `{slug}`(此前被静默丢弃,concept 页 `## 来源资料` 留空触发 lint R7.11);形态不符条目 WARN 精确定位到文件 + 数组下标 + 原值;ajv 校验失败跳过页记入 `warnings_by_file`(`--json` 可见)。

### Documentation

- 全仓版本号字串 0.6.11 → 0.6.12(`plugin.json` / 6 个 SKILL.md frontmatter / README badge / doc template + schema / frontmatter-spec 示例 / init-batch.js 默认 plugin_version / lint fixture),`check-version-consistency.js` 校验通过。

## [0.6.11] - 2026-09-25

### Changed

- **#58 research 单文件布局** `skills/aeps-llm-wiki-research/SKILL.md`:调研产物从「一题一目录 + 一源一文件」(`{YYYYMMDD-HHMMSS}-{slug}/` 下 `00-research-note.md` + `NNN-{source-slug}.md`)改为单文件 `inbox/research/{YYYYMMDD}-{slug}.md` 平铺。单文件内部 H2 节承载原目录结构:文档头(时间/判定/总问题数)→ 研究问题(证据源用节内锚点,锚点 = 标题原文)→ 未决问题 → 源清单(三态)→ 每精读源一「源 N」节(节首 4 行 blockquote 溯源头 + 摘录内嵌,不设独立「重点摘录」节)→ 工具可用性。同名文件已存在 → 文件名追加 `-HHMMSS` 消歧;frontmatter description 同步「一题一 md」。ingest 衔接随之简化:单 `.md` 走路径 1 纯文本,无子目录特例(issue #57 相关发现 1/2 对 research 场景自动消失);存量旧布局目录不迁移。

### Fixed

- `skills/aeps-llm-wiki-research/SKILL.md`:源清单「状态」列自称「四种值」实列 3 种 → 改「三种值」(历史遗留)。

### Documentation

- 全仓 16 处版本号字串 0.6.10 → 0.6.11(6 个 SKILL.md frontmatter / README badge / doc template + schema / init-batch.js 默认 plugin_version / lint fixture),`check-version-consistency.js` 校验通过。

## [0.6.10] - 2026-09-19

### Fixed

- **#52 / P0 data-loss** `scripts/gen-page.js`:写入模式默认幂等(已存在同名 → `action: "skipped-existing"`);`--force` 才覆盖且旧文件先备份到 `<wiki-plugin>/temp/raw_backup_{YYYY-MM-DD}_{sha8}/<relpath>`(stderr `INFO: backup written to ...`);不影响 patch-frontmatter-only 模式。
- **#55 / P1 wikilink** `scripts/ingest/build-related-pages.js`:`renderSourcesBlock` / `renderRelatedBlock` / `appendSourcesEntries` / `appendRelatedEntries` 四处反链渲染统一改为 `[[{slug}|{title}]]`(左段恒为 slug,右段 = title 作 alias;Obsidian 1.12.7 resolver 只认左段)。同步更新 6 处 build-related-pages 测试断言从 `\[\[slug\]\]` → `\[\[slug\|`。
- **#53 / P1 lint-不一致** `scripts/gen-page.js`:CLI `--tags < 5 条` 自动合并 `DEFAULT_TAGS_BY_TYPE[type]` 兜底补足到 ≥5 条(LLM tags 优先级高,缺省只是兜底);stdout `hints[]` 输出 `CLI --tags 仅 N 条 <5,已合并 DEFAULT_TAGS_BY_TYPE 兜底到 M 条 (lint-stub R7.4)`。
- **#54 / P2 三括号嵌套** `scripts/gen-page.js`:`--source-file` 缺省拼接从 `[[${subdir}/${slug}.${ext}|${title}]]` 改 `[[${slug}|${subdir}/${slug}.${ext}]]`(左段 = slug,符合 #55 精神;若 LLM 显式传 `--source-file` 含 `[[` `]]` 直接使用,不二次包裹)。

### Tests

- 新增 `scripts/ingest/test/gen-page-write-idempotent.test.js`(3 用例:skip / --force+backup / create)。
- 新增 `scripts/ingest/test/gen-page-tags-floor.test.js`(3 用例:缺省 / <5 合并 / ≥5 尊重)。
- 现有 build-related-pages 测试断言更新为新 wikilink 形态。

### Documentation

- `doc/schema/frontmatter-spec.md` §5 / §6 / §7 示例块 `generated.by` 版本号 `producer/aeps-llm-wiki-plugin/0.6.9` → `0.6.10`(与 `check-version-consistency.js` 同步);规格语义未变。
- 6 个 `skills/aeps-llm-wiki-*/SKILL.md` + `README.md` + `doc/template/page-{glossary,index,overview}.md` + `doc/schema/schema.md` 顶部 plugin 版本号 0.6.9 → 0.6.10。
- `scripts/ingest/init-batch.js` 默认 `plugin_version` + `scripts/lint/test/_fixture.js` fixture 版本号同步。

## [0.6.8] - 2026-09-12

### Added

- **M2.3 query skill** `skills/aeps-llm-wiki-query/SKILL.md` (新增): `/aeps-llm-wiki-query {question}` 12 步编排(对齐 PRD §4.3 流程表 0-11 + 共享聚合步骤 11.5),intent 三档路由 + 4 跳扫描 + G11 gating 落档询问 + analysis 落档。
- `scripts/query/count-pages.js` (新增): wiki 规模探查,三档分流(<500 纯 index / 500-1000 优先 qmd / >1000 必须 qmd);`QUERY_INDEX_THRESHOLD=500` / `QUERY_QMD_REQUIRED_THRESHOLD=1000`。
- `scripts/check-qmd.js` (新增): qmd 可用性探查(spawn `qmd --version`,3s 超时),design §4.2 契约。
- `scripts/query/gating-check.js` (新增): G11 gating 4×4 矩阵机械判定(triggers 任一 + skips 全不命中 → 询问落档),intent 由 LLM 传入,算术归脚本。
- `scripts/query/comparison-counter.js` (新增): 路径 B 计数器,持久化 `knowledge/.aeps-state/comparison-counter.json`;increment 仅在 intent=comparison 且用户拍板落档后(design §7.5),`should_propose = count >= 3`。
- `scripts/query/append-log.js` (新增): `**Creation**: query "..." → analyses/...` 行追加 log.md,当天 H2 复用 / 新 H2 最新在前。
- `doc/design/implement-query.md` (新增): M2.3 实施设计 v0.1.0 冻结 + v0.1.1 用例参数修正。

## [0.6.7] - 2026-09-10

### Fixed

- **#18 / PR-A** `scripts/gen-page.js`: 增加 `--json` stdout + summary fallback chain（description > "" + WARN） + `--strip-generated-h2` + `--stale-after-base<generated|updated>`; `doc/schema/frontmatter-spec.md` §4.5.2 新增 `stale_after` 字段。LLM 与脚本之间的页面生成契约更明确，避免静默 fallback 到 title。
- **#21 / PR-C** `scripts/ingest/lint-stub.js`: 新增 R7.4 字典前缀校验（`^(domain|layer|phase|docform|maturity|tec)/[a-z0-9][a-z0-9-]*$`），含必填轴 `docform`/`domain` + 单值轴 `docform`/`maturity`。违规 → `fail++`（非 warn）。`STUB_VERSION` M2.4-stub → M2.5-stub。
- **#25 / PR-C** `scripts/ingest/init-batch.js`: 新增 `normalizeFileEntry()` 函数，吃 `path` / `source_path` / `file_path` / `file` 4 种字段名别名（v0.6.6 回归 bug 修复）。3 字段同时写时 `path` 优先，剔除非规范键避免下游误读。
- **#27 / PR-D** `scripts/ingest/move-to-raw.js`: `backupToTemp()` 改 `temp/raw_backup_{hash}/` → `temp/raw_backup_{YYYY-MM-DD}_{hash}/`，让人/脚本一眼看出备份日期。
- **#28 / PR-B** `scripts/aggregate-index.js`: 行尾 `<span ...>#...</span>` tags 默认不渲染（解决视觉/设计意图冲突）；保留 `--show-tags` CLI 开关恢复旧行为。
- **#29 / PR-B** `scripts/aggregate-index.js`: `renderGlossaryDynamic()` 按术语首字母分组输出 `## A` / `## B` / ... / `## Z`；中文术语归 `## 中文`；数字术语归 `## 0-9`；空字母节省略（修复与 `page-glossary.md` 模板的契约漂移）。
- **#30 / PR-C** `scripts/ingest/append-log.js`: 读 `batch.files[].entities[]` / `batch.files[].concepts[]` 追加到 `**Ingest**` 行末尾，元素 schema `{type, slug, title?}` 与 `build-related-pages.js:697-700` 对齐，知识图谱变化追溯完整。
- **#31 / PR-B** `scripts/aggregate-index.js`: 抽 `renderTagsLineSuffix(fm, { showTags })` 函数，source / entity / concept / analysis / comparison / synthesis 6 type 共用，行为完全一致。

### Documentation

- `doc/schema/frontmatter-spec.md`: §4.5.2 新增 `stale_after` 字段。
- `doc/template/page-{source,entity-*,concept-*,analysis,comparison,synthesis}.md`: LLM reading prompts 改写。
- `doc/template/page-index.md`: 行尾 tags 说明改写（默认不渲染 + `--show-tags` 开关）。
- `doc/template/page-glossary.md`: 中文节说明 + 与代码 A-Z 分组对齐。
- `doc/template/page-log.md`: `**Ingest**` 格式说明追加 entity/concept 列说明。
- `skills/aeps-llm-wiki-ingest/SKILL.md`: 步骤 3/4/9/11/14/15/17/18 全部同步更新；`allowed-tools` 加 `cleanup-backups.js`。

### Changed

- `scripts/aggregate-index.js`: 抽 `renderTagsLineSuffix` + `bucketKey` 两个共用函数；`main()` 解析 `--show-tags`。
- `scripts/cleanup-backups.js` (新增, ~80 行): 扫 `temp/raw_backup_*/` 目录，按日期（YYYY-MM-DD 前缀）/ mtime fallback（旧格式）计算 age，超过 `--days`（默认 7）TTL 标记为 expired；默认 `--dry-run` 只列决策，加 `--apply` 才真删；`--json` 输出结构化。兼容 v0.6.6 旧格式 `raw_backup_{hash}/`。

### Tests

- `scripts/ingest/test/` 追加 27 个 PR-A/C/D case（gitignored, 本地）：gen-page patch-fm / template-order, lint-stub R7.4 (3), init-batch normalize (6), append-log entries (1), cleanup-backups (4)。
- `scripts/test/` 追加 8 个 PR-B case（gitignored, 本地）：aggregate-index tags 默认不渲染 (4) + `--show-tags` (1) + glossary A-Z 分组 (3)。

### Follow-up (留待后续 PR)

- `doc/design/design.md:340` + `doc/design/implement-ingest.md` 多处仍引旧命名 `temp/raw_backup_{hash}/`（frozen 文档，按规则修改需先加 change history 条目）。建议另开 doc-sync PR 修复。
- `scripts/test/aggregate-index-sentinel.test.js:154` 断言 `^## [A-Z]$` 因 PR-B #29 故意改写行为而失败（gitignored 本地测试，不阻塞 commit）。

## [0.6.6] - 2026-09-04

（详见 git log：4 commits on main before 0.6.7 batch）

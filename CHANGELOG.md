# Changelog

All notable changes to `aeps-llm-wiki-plugin` are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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

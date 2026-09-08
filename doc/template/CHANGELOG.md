# aeps-llm-wiki-plugin — Template Changelog

> **权威性**(scope of authority):本文件是 `doc/template/` 目录所有 `page-*.md` 模板文件的变更日志;plugin 升级时由维护者追加新条目,用户 re-run init 时**不**自动应用(对齐 [README.md §6.6](README.md))。

## v0.5.6(2026-09-08)—— 模板骨架全面松绑

**触发**:用户反馈"ingest 模板限制 LLM 自我发挥"。

**核心变更**:**LLM 写作自由大幅提升**,entity/concept/comparison/synthesis/analysis 5 类 wiki 页结构约束由「H2 硬约束 FAIL」变为「frontmatter + 链接 + `> 引用:`」三重校验。

### 变更清单

#### 1. 删除(14 个差异化模板文件)

- [ ] `page-entity-person.md`(原 `entity.person` 用)
- [ ] `page-entity-organization.md`(原 `entity.organization` 用)
- [ ] `page-entity-project.md`(原 `entity.project` 用)
- [ ] `page-entity-product.md`(原 `entity.product` 用)
- [ ] `page-entity-event.md`(原 `entity.event` 用)
- [ ] `page-entity-place.md`(原 `entity.place` 用)
- [ ] `page-entity-other.md`(原 `entity.other` 用)
- [ ] `page-concept-theory.md`(原 `concept.theory` 用)
- [ ] `page-concept-method.md`(原 `concept.method` 用)
- [ ] `page-concept-field.md`(原 `concept.field` 用)
- [ ] `page-concept-phenomenon.md`(原 `concept.phenomenon` 用)
- [ ] `page-concept-standard.md`(原 `concept.standard` 用)
- [ ] `page-concept-term.md`(原 `concept.term` 用)
- [ ] `page-concept-other.md`(原 `concept.other` 用)

#### 2. 新建(2 个通用模板)

- [x] [`page-entity.md`](page-entity.md)—— `entity.*` 7 子类通用骨架
- [x] [`page-concept.md`](page-concept.md)—— `concept.*` 7 子类通用骨架

#### 3. 改写(3 个完全松绑)

- [x] [`page-analysis.md`](page-analysis.md)—— 删除 3 节专属骨架(`## 方案推演 / 架构分析` + `## 关联溯源` + `## 总结:最有收获的一句话`),正文完全自由发挥。**唯一硬约束**:文末 `> 引用:` 行 wikilink 列表与 `sources_used` Set 一致(lint C15.4 WARN)
- [x] [`page-comparison.md`](page-comparison.md)—— 删除硬推荐 H2(`## 维度对比表` / `## 适用场景` / `## 风险点`),正文完全自由发挥。保留 `sources:` 必填 ≥ 2 条
- [x] [`page-synthesis.md`](page-synthesis.md)—— 删除硬推荐 H2(`## 体系总览` / `## ASIL 等级分解` 等),正文完全自由发挥。保留 `sources_count` < 3 WARN(避免空综合)

#### 4. 不动(1 个保持混合骨架)

- [ ] [`page-source.md`](page-source.md)—— **不动**。3 节必选(`## 重点摘录` / `## 我的思考` / `## 总结:最有收获的一句话`)+ 自由追加节的混合骨架符合「raw 层忠实摘录」语义,且 v0.5.0 之前已写得很清楚(LLM 阅读须知段落)。

#### 5. 同步改动(7 个文档)

- [x] [`doc/template/README.md`](README.md)—— §3 模板清单更新;§5 lint 规则表「3 节骨架硬约束」适用类型从 `source / analysis` 改为 `source only`;§6.1 模板文件数量从 9 改为 6;§6.4 表格 query 描述更新
- [x] [`doc/template/concept-entities-spec.md`](concept-entities-spec.md)—— §2 / §3 7 子类差异化骨架表删除,改为「子类共用通用骨架」表 + 「子类差异如何体现」说明
- [x] [`doc/template/tag-spec.md`](tag-spec.md)—— §1 引用列表从「7 个 entity 子类 + 7 个 concept 子类」改为「`page-entity.md` / `page-concept.md` 通用模板」
- [x] [`doc/design/prd.md`](../design/prd.md)—— v0.5.6 状态;Change History 新增 v0.5.6 行;G11 M1 结构段落改写;§4.3 流程表步骤 9 / 步骤 10 / 步骤 11 描述更新;§4.4 lint `--fix` 范围 + 步骤 5 描述更新;AC-11 / AC-12 重写
- [x] [`doc/design/implement-ingest.md`](../design/implement-ingest.md)—— §引用 模板路径从 `page-entity-person.md` / `page-concept-theory.md` 改为 `page-entity.md` / `page-concept.md`
- [x] [`skills/aeps-llm-wiki-ingest/SKILL.md`](../../skills/aeps-llm-wiki-ingest/SKILL.md)—— 步骤 10 entity.* / concept.* 模板选择说明改写
- [x] [`scripts/gen-page.js`](../../scripts/gen-page.js)—— L261-269 模板选择逻辑:entity.* / concept.* 不再按 7 子类选 14 个差异化模板,统一走 `page-entity.md` / `page-concept.md` 通用模板

### Lint 强度变化

| type | v0.5.6 之前 | v0.5.6 起 |
|---|---|---|
| `source` | 必含 3 节 H2(FAIL) | **不变**:必含 3 节 H2(FAIL) |
| `analysis` | 必含 3 节专属骨架 H2(FAIL) | **仅校验** `> 引用:` 行存在 + `sources_used` 一致(WARN);H2 完全自由 |
| `comparison` | 推荐 H2(软) | 正文完全自由;`sources` 必填 ≥ 2(FAIL);H2 不锁 |
| `synthesis` | 推荐 H2(软) | 正文完全自由;`sources_count` < 3 WARN;H2 不锁 |
| `entity.*` | 7 子类差异化 H2 硬推荐 | 正文完全自由;frontmatter + 链接 + `> 引用:` 三重校验;H2 不锁 |
| `concept.*` | 7 子类差异化 H2 硬推荐 | 正文完全自由;frontmatter + 链接 + `> 引用:` 三重校验;H2 不锁 |

### 用户工程同步策略

- **init skill re-run**:`doc/template/` → `templates/` 是 **backfill missing;preserve existing** 策略(SYNC-6)。re-run init 会把 `page-entity.md` / `page-concept.md` 通用模板**新增**到 `templates/`,但**不删除**用户本地可能存在的旧 14 个差异化模板文件(避免破坏用户已有工作流)
- **建议用户手工操作**:
  1. 删除本地 `templates/page-entity-{person,organization,...}.md` 与 `templates/page-concept-{theory,method,...}.md` 共 14 个文件(可选;不影响生成)
  2. 跑 `/aeps-llm-wiki-lint --fix` 让 lint 应用新的判定规则(确定性结构修复不再补 analysis 3 节骨架)
  3. 对已有 entity/concept/analysis/comparison/synthesis 页可手改或保留(不会被 lint 强制重写,因结构约束已放宽)

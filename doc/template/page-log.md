# 项目名 Wiki 变更日志

> **plugin 版本**:0.5.2
>
> 本文件无 frontmatter(OKF §9 reserved filename);按 ISO 8601 日期做 H2,最新在前。

---

## 2026-09-04

**Init**: 用户项目 wiki 初始化,生成 17 个叶子存储目录 + 5 份管理文件

**Ingest**: inbox/iso26262.pdf → raw/06_功能安全/iso26262.pdf (+ converted.md);新建 entities/person/andrej-karpathy.md + concepts/theory/llm-wiki.md + concepts/standard/okf-v0.2.md

**Creation**: query "S32G vs NXP S32K3 在车身控制器选型上怎么选?" → analyses/2026-09-04-s32g-vs-s32k3.md

**LintFix**: entities/product/s32g.md 补 frontmatter `updated` 字段 + 类型错位 `tags` 强转

**LintProposal**: comparisons/layerzero-vs-wormhole.md 与 comparisons/layerzero-vs-wormhole-bridge.md 命名飘合并提案(等用户拍板)

---

## {YYYY-MM-DD}

【占位:用户后续 ingest / query / lint 追加。最新的日期在前。】

---

## 维护

- 字段定义权威:`../doc/schema/frontmatter-spec.md`(人读规范,唯一权威);`../doc/schema/frontmatter.schema.json` 跟随对齐
- 本文件由 SKILL.md 在每次 ingest / query 落档 / lint 时追加;前缀 5 种(PRD §4.6 路径 B 注释):
  - `**Init**`:项目初始化
  - `**Ingest**`:inbox → raw 迁移 + 知识页生成
  - `**Creation**`:query 落档为 analysis 页(G11 M1)
  - `**LintFix**`:`--fix` 模式确定性结构修复
  - `**LintProposal**`:`--fix` 模式语义级问题(仅提案)

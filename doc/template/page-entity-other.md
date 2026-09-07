---
# OKF v0.2 §4.1 必填字段
type: "entity.other"        # 子类:other(兜底)
title: "<entity 名>"
description: "一句话描述。"
# OKF §4.1 tags
tags:
  - docform/study-notes

# OKF §5.1 sources
sources:
  - id: self-source
    resource: ./raw/<subdir>/<file>

# OKF §5.2 generated
generated:
  by: "producer/aeps-llm-wiki-plugin/0.5.6"
  at: "2026-09-04T11:30:00Z"

# OKF §5.4 lifecycle
status: stable

# plugin 推荐字段
updated: "2026-09-04T11:30:00Z"
summary: "<一句话精要>"

# plugin 推荐字段(可选)
aliases: []
---

# <entity 名>

【正文自由发挥,**主推 `[[wikilink]]` 裸文件名**(PRD §10 Q9)。`entity.other` 是兜底子类,适用于不属于 person / organization / project / product / event / place 6 类的具象存在。

不强制任何 H2 节;LLM 按资料特点自行组织。如常用结构重复出现,可考虑新增子类。】

【自由发挥 H2,建议至少包含:
- 简要描述该实体是什么
- 它与其他 wiki 页的关系(用 `[[wikilink]]`)
】

## 关联导引(Related Links)

- 相关:[[<wikilink>]]

## 来源资料(由 ingest 自动生成)

【本节由 `/aeps-llm-wiki-ingest` 根据抽取本页的 `type: source` 源页列表生成,每次 ingest **完全重建**。】

---

## 维护说明(本节由 plugin 自动追加,可手删)

- 本页由 `/aeps-llm-wiki-ingest` 从源页抽取 entity 时自动生成,或用户手工创建
- `type` 取值必须与目录 1:1 绑死:`entity.other` → `knowledge/entities/other/`
- **aliases 字段**(可选):本页别名通过 `aliases: [...]` 注册
- 实体页**不强制 3 节骨架**;lint 只校 frontmatter + 链接
- 兜底子类,如常用结构重复出现应新增子类而非继续用 `other`
- 与 `entity.person` 模板差异化(见 `concept-entities-spec.md` §3)
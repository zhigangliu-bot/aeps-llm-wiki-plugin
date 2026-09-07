---
# OKF v0.2 §4.1 必填字段
type: "concept.method"          # 子类:method
title: "单元级别需求"
description: "在 AUTOSAR / ECU 层级以下,以信号 / 变量为单位书写需求的实践方法。"
# OKF §4.1 tags
tags:
  - docform/technical-doc
  - domain/automotive

# OKF §5.1 sources(指向关联的源页/原始资料)
sources:
  - id: self-source
    resource: ./raw/<subdir>/<file>

# OKF §5.2 generated
generated:
  by: "producer/aeps-llm-wiki-plugin/0.5.6"
  at: "2026-09-07T12:00:00Z"

# OKF §5.4 / §5.5 lifecycle(可选)
status: stable
stale_after: "2027-09-07T00:00:00Z"

# plugin 推荐字段
updated: "2026-09-07T12:00:00Z"
summary: "<一句话精要>"

# plugin 推荐字段(Obsidian 原生别名机制)
aliases: []
---

# <concept 名>

【正文自由发挥,**主推 `[[wikilink]]` 裸文件名**(PRD §10 Q9)。方法论页推荐 H2 骨架见下:】

## 核心思想

【方法论的核心论点、解决什么问题、为什么有效。】

## 适用场景

【方法论适用的边界条件、典型用例。涉及 concept.field / concept.phenomenon 可 link。】

## 操作步骤

1. 第一步
2. 第二步
3. 第三步

【分步骤的实操路径。涉及 entity.tool / entity.product 可 link。】

## 局限 / 反模式

【该方法论不适用的情况、常见误用、与替代方法的对比。涉及 concept.phenomenon 可 link。】

## 关联导引(Related Links,`doc/schema/schema.md` §3.1 规则 3)

- 对照:[[<wikilink>]]
- 综合:[[<wikilink>]]

## 来源资料(由 ingest 自动生成)

【本节由 `/aeps-llm-wiki-ingest` 根据抽取本页的 `type: source` 源页列表生成,每次 ingest **完全重建**。】

---

## 维护说明(本节由 plugin 自动追加,可手删)

- 本页由 `/aeps-llm-wiki-ingest` 从源页抽取 concept.method 时自动生成,或用户手工创建
- `type` 取值必须与目录 1:1 绑死:`concept.method` → `knowledge/concepts/method/`
- 与 `concept.theory` 模板差异化(见 `concept-entities-spec.md` §3)
- **aliases 字段**(plugin 推荐):常用缩写/同义词通过 `aliases: [...]` 注册,详见 `frontmatter-spec.md` §12.4
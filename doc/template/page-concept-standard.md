---
# OKF v0.2 §4.1 必填字段
type: "concept.standard"          # 子类:standard
title: "ISO 26262"
description: "汽车功能安全国际标准 ISO 26262:2018,定义汽车电子电气系统功能安全的完整生命周期与 ASIL 等级。"
# OKF §4.1 tags
tags:
  - docform/standard-doc
  - domain/automotive
  - tec/functional-safety

# OKF §5.1 sources(指向关联的源页/原始资料)
sources:
  - id: iso-26262-2018
    resource: ./raw/<subdir>/<file>

# OKF §5.2 generated
generated:
  by: "producer/aeps-llm-wiki-plugin/0.5.6"
  at: "2026-09-07T12:00:00Z"

# OKF §5.4 / §5.5 lifecycle(可选)
status: stable
stale_after: "2031-09-07T00:00:00Z"   # 标准类 stale 默认 +5 年

# plugin 推荐字段
updated: "2026-09-07T12:00:00Z"
summary: "<一句话精要>"

# plugin 推荐字段
aliases: []
---

# <concept 名>

【正文自由发挥,**主推 `[[wikilink]]` 裸文件名**(PRD §10 Q9)。标准 / 规范页推荐 H2 骨架见下:】

## 标准概述

【发布机构、当前版本、发布日期、适用范围。涉及 entity.organization 可 link。】

## 核心内容

【该标准定义的核心概念、关键术语、关键章节。涉及 concept.term 可 link。】

## 关键要求 / 等级划分

【标准对实施方的硬性要求、等级划分(如 ISO 26262 ASIL-A/B/C/D)、合规检查点。涉及 concept.field / concept.method 可 link。】

## 与相关标准的关系

【与配套标准(如 ISO 21434 / ISO 8800 / SAE J3061)的关系:互补 / 重叠 / 引用。】

## 版本演进

【从 v1 到当前版本的关键变化、演进方向。涉及 entity.event 可 link。】

## 关联导引(Related Links,`doc/schema/schema.md` §3.1 规则 3)

- 配套标准:[[<wikilink>]]
- 实施方法:[[<wikilink>]]

## 来源资料(由 ingest 自动生成)

【本节由 `/aeps-llm-wiki-ingest` 根据抽取本页的 `type: source` 源页列表生成,每次 ingest **完全重建**。】

---

## 维护说明(本节由 plugin 自动追加,可手删)

- 本页由 `/aeps-llm-wiki-ingest` 从源页抽取 concept.standard 时自动生成,或用户手工创建
- `type` 取值必须与目录 1:1 绑死:`concept.standard` → `knowledge/concepts/standard/`
- 标准类 `stale_after` 默认 `generated.at + 5 年`(SKILL.md 步骤 6);重大修订 / 新版本发布需手动更新
- 与 `concept.theory` 模板差异化(见 `concept-entities-spec.md` §3)
- **aliases 字段**(plugin 推荐):常用缩写/同义词通过 `aliases: [...]` 注册
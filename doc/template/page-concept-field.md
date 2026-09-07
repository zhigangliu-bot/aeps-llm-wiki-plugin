---
# OKF v0.2 §4.1 必填字段
type: "concept.field"          # 子类:field
title: "SDV"
description: "Software-Defined Vehicle,软件定义汽车,把汽车从分布式 ECU 架构迁移到集中式高性能计算平台。"
# OKF §4.1 tags
tags:
  - docform/technical-doc
  - domain/automotive
  - layer/architecture

# OKF §5.1 sources
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

# plugin 推荐字段
aliases: []
---

# <concept 名>

【正文自由发挥,**主推 `[[wikilink]]` 裸文件名**(PRD §10 Q9)。领域页推荐 H2 骨架见下:】

## 领域范畴

【该领域的研究对象、关注的核心问题、与其他领域(concept.field)的边界。】

## 关键议题

【该领域的几个核心子议题,逐条 `[[wikilink]]` 到对应 concept.* 或 entity.*。】

## 主要玩家 / 学术派系

【该领域的主要研究机构 / 公司 / 学术派系;涉及 entity.organization 可 link。】

## 发展趋势

【当前的技术演进方向、标准化动态、产业化阶段。涉及 concept.phenomenon / concept.standard 可 link。】

## 关联导引(Related Links,`doc/schema/schema.md` §3.1 规则 3)

- 上位:[[<wikilink>]]
- 子领域:[[<wikilink>]]

## 来源资料(由 ingest 自动生成)

【本节由 `/aeps-llm-wiki-ingest` 根据抽取本页的 `type: source` 源页列表生成,每次 ingest **完全重建**。】

---

## 维护说明(本节由 plugin 自动追加,可手删)

- 本页由 `/aeps-llm-wiki-ingest` 从源页抽取 concept.field 时自动生成,或用户手工创建
- `type` 取值必须与目录 1:1 绑死:`concept.field` → `knowledge/concepts/field/`
- 与 `concept.theory` 模板差异化(见 `concept-entities-spec.md` §3)
- **aliases 字段**(plugin 推荐):常用缩写/同义词通过 `aliases: [...]` 注册
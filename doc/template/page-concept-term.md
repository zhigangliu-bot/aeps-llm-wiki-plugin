---
# OKF v0.2 §4.1 必填字段
type: "concept.term"          # 子类:term
title: "AaaS"
description: "Algorithm-as-a-Service,算法即服务:把核心算法从本地 ECU 抽到云端或集中式 HPC,以服务方式按需调用。"
# OKF §4.1 tags
tags:
  - docform/glossary
  - domain/automotive

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

# plugin 推荐字段(Obsidian 原生别名机制)
aliases:
  - "Algorithm as a Service"
  - "算法即服务"
---

# <concept 名>

【正文自由发挥,**主推 `[[wikilink]]` 裸文件名**(PRD §10 Q9)。术语 / 概念词页推荐 H2 骨架见下。术语页通常较短,1-3 段即可。】

## 定义

【一句话精确定义,加出处。】

## 上下文 / 来源

【该术语在哪个标准 / 论文 / 厂商文档中首次提出,目前主流用法。涉及 entity.organization / entity.person 可 link。】

## 同义 / 反义

- 同义:[[<wikilink>]]
- 反义:[[<wikilink>]]

## 关联导引(Related Links,`doc/schema/schema.md` §3.1 规则 3)

- 上位概念:[[<wikilink>]]
- 下位实例:[[<wikilink>]]

## 来源资料(由 ingest 自动生成)

【本节由 `/aeps-llm-wiki-ingest` 根据抽取本页的 `type: source` 源页列表生成,每次 ingest **完全重建**。】

---

## 维护说明(本节由 plugin 自动追加,可手删)

- 本页由 `/aeps-llm-wiki-ingest` 从源页抽取 concept.term 时自动生成,或用户手工创建
- `type` 取值必须与目录 1:1 绑死:`concept.term` → `knowledge/concepts/term/`
- 术语页强推荐填 `aliases`(常用缩写/同义词),便于 wikilink 直接用别名
- 与 `concept.theory` 模板差异化(见 `concept-entities-spec.md` §3)
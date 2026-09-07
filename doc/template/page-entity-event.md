---
# OKF v0.2 §4.1 必填字段
type: "entity.event"        # 子类:event
title: "IEEE Ethernet Day 2024"
description: "IEEE 802.3 Ethernet & IP @ Automotive Tech Day,2024 年汽车以太网技术日。"
# OKF §4.1 tags
tags:
  - docform/event-notes
  - domain/networking
  - phase/conference

# OKF §5.1 sources
sources:
  - id: self-source
    resource: ./raw/10_会议与活动/ieee-ethernet-day-2024.md

# OKF §5.2 generated
generated:
  by: "producer/aeps-llm-wiki-plugin/0.5.6"
  at: "2026-09-04T11:30:00Z"

# OKF §5.4 lifecycle
status: stable

# plugin 推荐字段
updated: "2026-09-04T11:30:00Z"
summary: "IEEE Ethernet Day 2024 是面向汽车以太网技术的高规格技术日,聚焦 TSN / 100BASE-T1 / 多 Gig 应用。"

# plugin 推荐字段
aliases:
  - "Ethernet Day 2024"
---

# IEEE Ethernet Day 2024

【正文自由发挥,**主推 `[[wikilink]]` 裸文件名**(PRD §10 Q9)。事件页推荐 H2 骨架见下:】

## 会议概览

【会议名称、主办方、规模、定位。涉及 entity.organization 可 link 到对应组织。】

## 时间 / 地点

【日期、城市、场馆。涉及 entity.place 可 link 到对应地点。】

## 主题

【会议主线主题、技术焦点、议程结构。】

## 关键演讲

【重点演讲 / 主题报告 / keynote;若有 entity.person 页 link 到对应人。】

## 重要发布

【会议期间发布的白皮书 / 标准草案 / 产品 / 工具;通过 `[[wikilink]]` 链接到对应 `source` 或 `entity.*` 页。】

## 关联导引(Related Links)

- 主题:[[automotive-ethernet]]
- 标准:[[ieee-802-3]]

## 来源资料(由 ingest 自动生成)

【本节由 `/aeps-llm-wiki-ingest` 根据抽取本页的 `type: source` 源页列表生成,每次 ingest **完全重建**。】

---

## 维护说明(本节由 plugin 自动追加,可手删)

- 本页由 `/aeps-llm-wiki-ingest` 从源页抽取 entity 时自动生成,或用户手工创建
- `type` 取值必须与目录 1:1 绑死:`entity.event` → `knowledge/entities/event/`
- **aliases 字段**:本页 `[[IEEE Ethernet Day 2024]]` 别名通过 `aliases: [...]` 注册
- 实体页**不强制 3 节骨架**;lint 只校 frontmatter + 链接
- 与 `entity.person` 模板差异化(见 `concept-entities-spec.md` §3)
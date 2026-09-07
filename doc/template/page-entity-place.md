---
# OKF v0.2 §4.1 必填字段
type: "entity.place"        # 子类:place
title: "Munich"
description: "德国巴伐利亚州首府,汽车电子产业重镇(BMW / Infineon / 半导体头部集中地)。"
# OKF §4.1 tags
tags:
  - docform/study-notes
  - domain/automotive

# OKF §5.1 sources
sources:
  - id: self-source
    resource: ./raw/09_域控制器/munich-ecosystem.md

# OKF §5.2 generated
generated:
  by: "producer/aeps-llm-wiki-plugin/0.5.6"
  at: "2026-09-04T11:30:00Z"

# OKF §5.4 lifecycle
status: stable

# plugin 推荐字段
updated: "2026-09-04T11:30:00Z"
summary: "Munich 是德国汽车电子产业核心地带,聚集 BMW / Infineon / Vector 等头部厂商。"

# plugin 推荐字段
aliases:
  - "慕尼黑"
  - "München"
---

# Munich

【正文自由发挥,**主推 `[[wikilink]]` 裸文件名**(PRD §10 Q9)。地点页推荐 H2 骨架见下:】

## 地理位置

【所在国家 / 区域 / 行政区 / 坐标 / 海拔 / 周边地理特征。】

## 历史

【该地点的历史沿革、关键历史事件、命名来源。涉及 entity.event 可 link。】

## 产业意义

【该地点在产业链中的角色(总部聚集地 / 制造中心 / 研发中心 / 会议中心);涉及 entity.organization / entity.event 可 link。】

## 相关组织 / 设施

【位于该地点的代表性组织 / 高校 / 工厂 / 园区,逐条 `[[wikilink]]`。】

## 关联导引(Related Links)

- 国家:[[germany]]
- 厂商:[[infineon]]

## 来源资料(由 ingest 自动生成)

【本节由 `/aeps-llm-wiki-ingest` 根据抽取本页的 `type: source` 源页列表生成,每次 ingest **完全重建**。】

---

## 维护说明(本节由 plugin 自动追加,可手删)

- 本页由 `/aeps-llm-wiki-ingest` 从源页抽取 entity 时自动生成,或用户手工创建
- `type` 取值必须与目录 1:1 绑死:`entity.place` → `knowledge/entities/place/`
- **aliases 字段**:本页 `[[慕尼黑]]` / `[[München]]` 别名通过 `aliases: [...]` 注册
- 实体页**不强制 3 节骨架**;lint 只校 frontmatter + 链接
- 与 `entity.person` 模板差异化(见 `concept-entities-spec.md` §3)
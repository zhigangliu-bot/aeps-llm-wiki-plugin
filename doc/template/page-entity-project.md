---
# OKF v0.2 §4.1 必填字段
type: "entity.project"      # 子类:project
title: "AES 2026"
description: "Automotive Ecosystem Summit 2026,汽车软件生态峰会。"
# OKF §4.1 tags
tags:
  - docform/study-notes
  - domain/automotive
  - phase/conference

# OKF §5.1 sources
sources:
  - id: self-source
    resource: ./raw/10_会议与活动/aes-2026.md

# OKF §5.2 generated
generated:
  by: "producer/aeps-llm-wiki-plugin/0.5.6"
  at: "2026-09-04T11:30:00Z"

# OKF §5.4 lifecycle
status: stable

# plugin 推荐字段
updated: "2026-09-04T11:30:00Z"
summary: "AES 2026 是聚焦汽车软件生态的高规格产业峰会。"

# plugin 推荐字段
aliases:
  - "Automotive Ecosystem Summit 2026"
  - "汽车生态峰会 2026"
---

# AES 2026

【正文自由发挥,**主推 `[[wikilink]]` 裸文件名**(PRD §10 Q9)。项目页推荐 H2 骨架见下:】

## 项目目标

【该项目的核心目标、解决什么问题、为什么立项。】

## 范围

【项目覆盖的范围(技术、产品、市场);明确 **不** 做什么(out-of-scope)。】

## 阶段

【项目所处阶段(规划 / 启动 / 执行 / 收尾 / 已完成)+ 时间节点。】

## 关键里程碑

【关键交付物 / 决策点 / 评审 / 发布,按时间倒序。涉及 entity.event 可 link 到对应事件页。】

## 团队 / 干系人

【项目 owner / 核心贡献者 / 干系方;若有 entity.person / entity.organization 页可 link。】

## 关联导引(Related Links)

- 标准:[[iso-26262]]
- 产品:[[aurix-tc3xx]]

## 来源资料(由 ingest 自动生成)

【本节由 `/aeps-llm-wiki-ingest` 根据抽取本页的 `type: source` 源页列表生成,每次 ingest **完全重建**。】

---

## 维护说明(本节由 plugin 自动追加,可手删)

- 本页由 `/aeps-llm-wiki-ingest` 从源页抽取 entity 时自动生成,或用户手工创建
- `type` 取值必须与目录 1:1 绑死:`entity.project` → `knowledge/entities/project/`
- **aliases 字段**:本页 `[[AES 2026]]` / `[[Automotive Ecosystem Summit 2026]]` 别名通过 `aliases: [...]` 注册
- 实体页**不强制 3 节骨架**;lint 只校 frontmatter + 链接
- 与 `entity.person` 模板差异化(见 `concept-entities-spec.md` §3)
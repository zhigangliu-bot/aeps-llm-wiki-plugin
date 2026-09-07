---
# OKF v0.2 §4.1 必填字段
type: "entity.product"      # 子类:product
title: "AURIX TC3xx"
description: "Infineon AURIX 第二代 32 位汽车 MCU,支持功能安全 ASIL-D 与多核架构。"
# OKF §4.1 tags
tags:
  - docform/datasheet
  - domain/embedded
  - tec/aurix-tc3xx

# OKF §5.1 sources
sources:
  - id: self-source
    resource: ./raw/02_芯片/aurix-tc3xx-datasheet.pdf

# OKF §5.2 generated
generated:
  by: "producer/aeps-llm-wiki-plugin/0.5.6"
  at: "2026-09-04T11:30:00Z"

# OKF §5.4 lifecycle
status: stable

# plugin 推荐字段
updated: "2026-09-04T11:30:00Z"
summary: "AURIX TC3xx 是 Infineon 第二代汽车 MCU 平台,广泛用于域控制器与功能安全应用。"

# plugin 推荐字段
aliases:
  - "AURIX"
  - "TC3xx"
---

# AURIX TC3xx

【正文自由发挥,**主推 `[[wikilink]]` 裸文件名**(PRD §10 Q9)。产品页推荐 H2 骨架见下:】

## 产品定位

【产品类别、目标市场、目标应用领域(整车 / 域控制器 / 传感器 / 网关)。】

## 核心特性

【关键技术指标:算力 / 内存 / 接口 / 安全等级 / 工艺节点 / 功耗。每条配来源页 wikilink。】

## 适用场景

【典型应用案例与适用整车平台;涉及 entity.project / entity.event 可 link。】

## 竞品对照

【同档位竞品(如 Renesas RH850 / NXP S32K3 / TI Jacinto);通过 `[[对比页]]` 链接到对应 `comparison` 页或直接列出对照表。】

## 版本演进

【产品代际(TriCore 1.x → 2.x)、发布日期、EOL 计划。涉及 entity.event 可 link 到发布事件。】

## 关联导引(Related Links)

- 供应商:[[infineon]]
- 标准:[[iso-26262]]

## 来源资料(由 ingest 自动生成)

【本节由 `/aeps-llm-wiki-ingest` 根据抽取本页的 `type: source` 源页列表生成,每次 ingest **完全重建**。】

---

## 维护说明(本节由 plugin 自动追加,可手删)

- 本页由 `/aeps-llm-wiki-ingest` 从源页抽取 entity 时自动生成,或用户手工创建
- `type` 取值必须与目录 1:1 绑死:`entity.product` → `knowledge/entities/product/`
- **aliases 字段**:本页 `[[AURIX]]` / `[[TC3xx]]` 别名通过 `aliases: [...]` 注册
- 实体页**不强制 3 节骨架**;lint 只校 frontmatter + 链接
- 与 `entity.person` 模板差异化(见 `concept-entities-spec.md` §3)
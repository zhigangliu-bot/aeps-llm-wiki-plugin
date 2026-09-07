---
# OKF v0.2 §4.1 必填字段
type: "entity.organization"  # 子类:organization
title: "Infineon Technologies"
description: "Infineon Technologies AG,德国半导体公司,汽车 MCU / 功率半导体头部供应商。"
# OKF §4.1 tags(6 轴字典)
tags:
  - docform/study-notes
  - domain/embedded
  - layer/chip-vendor

# OKF §5.1 sources
sources:
  - id: self-source
    resource: ./raw/02_芯片/infineon-overview.md

# OKF §5.2 generated
generated:
  by: "producer/aeps-llm-wiki-plugin/0.5.6"
  at: "2026-09-04T11:30:00Z"

# OKF §5.4 lifecycle
status: stable

# plugin 推荐字段
updated: "2026-09-04T11:30:00Z"
summary: "Infineon 汽车 MCU 头部供应商,AURIX TC3xx 系列支撑域控制器与功能安全应用。"

# plugin 推荐字段(Obsidian 原生别名机制)
aliases:
  - "Infineon"
  - "英飞凌"
---

# Infineon Technologies

【正文自由发挥,**主推 `[[wikilink]]` 裸文件名**(PRD §10 Q9,`doc/schema/schema.md` §3.1)。本组织页推荐 H2 骨架见下,LLM 可按资料调整:】

## 业务范围

【该组织的主营业务、覆盖领域、客户群体。例如 Infineon 覆盖汽车 / 工业 / 电源管理 / 安全 IC。】

## 核心产品 / 关键产品线

【列举代表产品/平台,用 `[[wikilink]]` 引用对应 wiki 页(如 [[aurix-tc3xx]])。若产品单独有 entity 页则 link 到对应 product。】

## 关键人物

【该组织内对领域有影响的关键人物(若有 entity.person 页则 link)。例如 Infineon CEO、CTO、首席架构师等。】

## 历史沿革

【该组织重要里程碑事件(若有 entity.event 页则 link)。例如成立时间、重大并购、上市、关键产品发布年代。】

## 关联导引(Related Links)

- 综合:[[automotive-functional-safety]]
- 标准:[[iso-26262]]

## 来源资料(由 ingest 自动生成)

【本节由 `/aeps-llm-wiki-ingest` 根据抽取本页的 `type: source` 源页列表生成。每次 ingest **完全重建**,不保留人工条目。】

---

## 维护说明(本节由 plugin 自动追加,可手删)

- 本页由 `/aeps-llm-wiki-ingest` 从源页抽取 entity 时自动生成,或用户手工创建
- `type` 取值必须与目录 1:1 绑死:`entity.organization` → `knowledge/entities/organization/`
- **aliases 字段**:本页 `[[Infineon]]` / `[[英飞凌]]` 别名通过 `aliases: [...]` 注册,详见 `frontmatter-spec.md` §12.4
- 实体页**不强制 3 节骨架**;lint 只校 frontmatter + 链接
- 与 `entity.person` 模板差异化(见 `concept-entities-spec.md` §3 7 子类骨架建议)
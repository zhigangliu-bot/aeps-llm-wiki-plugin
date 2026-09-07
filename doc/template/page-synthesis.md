---
# OKF v0.2 §4.1 必填字段
type: synthesis
title: "汽车功能安全体系综合"
description: "整合 wiki 内 ISO 26262 / ASIL 分解 / 硬件架构度量 / 软件单元测试等所有相关概念的综合页。"
# OKF §4.1 tags(plugin 强化为 6 轴字典约束,详见 doc/template/tag-spec.md —— 本文件 tags: 行权威来源)
tags:
  - docform/technical-doc
  - domain/fusa
  - tec/iso26262
  - phase/architecture

# OKF §5.1 sources(综合引用的所有相关 wiki 页)
sources:
  - id: iso26262-concept
    resource: ./knowledge/concepts/standard/iso-26262.md
  - id: asil-concept
    resource: ./knowledge/concepts/term/asil.md
  - id: autosar-concept
    resource: ./knowledge/concepts/standard/autosar.md
  - id: hardware-metric-concept
    resource: ./knowledge/concepts/method/hardware-architecture-metric.md
  - id: sw-unit-test-concept
    resource: ./knowledge/concepts/method/software-unit-testing.md

# OKF §5.2 generated
generated:
  by: "producer/aeps-llm-wiki-plugin/0.5.2"
  at: "2026-09-04T16:00:00Z"

# OKF §5.4 lifecycle(可选)
status: stable

# plugin 扩展字段
sources_count: 5

# plugin 推荐字段
updated: "2026-09-04T16:00:00Z"
summary: "汽车功能安全体系以 ISO 26262 为核心,围绕 ASIL 等级分解、硬件架构度量、软件单元测试三大支柱展开,本综合页整合 wiki 内全部相关概念。"
---

# 汽车功能安全体系综合

【正文综合 LLM 自由发挥。**正文链接主推 `[[wikilink]]` 裸文件名**(PRD §10 Q9,`doc/schema/schema.md` §3.1),lint 期望至少 5 条 wikilink 引用,体现"综合"价值(非简单罗列)。常见 H2 结构:】

## 体系总览

【从 [[iso-26262]] 出发,串联 [[asil]] 等级分解、[[hardware-architecture-metric]]、[[software-unit-testing]] 三大支柱,勾勒完整的功能安全体系图谱。】

## ASIL 等级分解

【参考 [[asil]] 概念页,详解 QM / ASIL A / B / C / D 的适用场景与硬件指标要求。】

## 硬件架构度量

【参考 [[hardware-architecture-metric]],讲解 SPFM / LFM / PMHF 三大指标的计算方法与门槛值。】

## 软件单元测试要求

【参考 [[software-unit-testing]],覆盖结构覆盖 / 需求覆盖 / 接口覆盖等测试层级与 ASIL 映射关系。】

## 工具链与生态

【参考 [[autosar]] 概念页,介绍 CP / AP 平台与功能安全模块(FSM / E2E 保护)的集成。】

## 关联导引(Related Links,`doc/schema/schema.md` §3.1 规则 3)

- 对照:[[layerzero-vs-wormhole]]
- 综合:[[automotive-functional-safety]]
- 分析:[[s32g-vs-s32k3-body-controller]]

---

## 维护说明(本节由 plugin 自动追加,可手删)

- 本页由 `/aeps-llm-wiki-synthesize {topic}` 显式触发,SKILL.md 扫 `knowledge/index.md` + 涉及 `{topic}` 的全部页后自动生成
- 命名:**不带时间戳,常驻** `knowledge/syntheses/{topic-slug}.md`(后续 LLM 可 update)
- lint 必查:
  - `type` 必须是 `synthesis`(否则 FAIL)
  - `sources_count` < 3 WARN(避免空综合)
  - 正文**不锁骨架**(LLM 自由发挥,但 lint 期望至少 5 条 wikilink 引用)
  - C15.5 反转(PRD Q9):wikilink 不再 FAIL;`--fix` 反向将正文标准 markdown 链接 → `[[wikilink]]`(代码层待实现)
- 与 `type: analysis` **职责分开**:synthesis 是常驻综合页(用户主动 `/synthesize` 触发),analysis 是 query 落档的一次性快照(PRD §4.5)
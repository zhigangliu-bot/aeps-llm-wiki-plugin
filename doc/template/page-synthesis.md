<!-- 提示:模板示例 tags 故意 ≥ 6 条,避免 LLM 按 5 条填导致 WARN;真实生成时按需保留全部或精简到 ≥ 5 条 -->
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
  - maturity/synthesis
  - layer/bsw-os

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
  by: "producer/aeps-llm-wiki-plugin/0.6.0"
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

【正文完全自由发挥。**正文链接主推 `[[wikilink]]` 裸文件名**(PRD §10 Q9,`doc/schema/schema.md` §3.1)。

synthesis 是**常驻**综合页(后续 LLM 可 update),不是 query 的一次性快照。LLM 根据 topic 特性决定组织 —— 体系总览 / 关键议题 / 演进时间线 / 跨领域交叉 / 决策树 / 工具链生态,任何结构都允许,**不锁骨架、不强制任何 H2 节名**。

**lint 期望**:`sources_count` ≥ 3(避免空综合,`< 3` WARN;不 FAIL)。正文 wikilink 引用数量无硬约束,但作为"综合"价值体现,期望 ≥ 5 条 wikilink 跨链多个 wiki 页(由 LLM 自行判断)。】

## 关联导引(Related Links,`doc/schema/schema.md` §3.1 规则 3)

- 对照:[[<wikilink>]]
- 分析:[[<wikilink>]]

---

## 维护说明(本节由 plugin 自动追加,可手删)

- 本页由 `/aeps-llm-wiki-synthesize {topic}` 显式触发,SKILL.md 扫 `knowledge/index.md` + 涉及 `{topic}` 的全部页后自动生成
- 命名:**不带时间戳,常驻** `knowledge/syntheses/{topic-slug}.md`(后续 LLM 可 update)
- lint 必查:
  - `type` 必须是 `synthesis`(否则 FAIL)
  - `sources_count` < 3 WARN(避免空综合)
  - 正文**不锁骨架**(v0.5.7 起;旧版推荐的 `## 体系总览` / `## ASIL 等级分解` 等示例已废除)
  - C15.5 反转(PRD Q9):wikilink 不再 FAIL;`--fix` 反向将正文标准 markdown 链接 → `[[wikilink]]`(代码层待实现)
- 与 `type: analysis` **职责分开**:synthesis 是常驻综合页(用户主动 `/synthesize` 触发),analysis 是 query 落档的一次性快照(PRD §4.5)

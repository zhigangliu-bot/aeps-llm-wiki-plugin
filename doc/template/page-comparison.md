---
# OKF v0.2 §4.1 必填字段
type: comparison
title: "LayerZero vs Wormhole 跨链机制对比"
description: "两条主流跨链桥实现机制的安全模型、信任假设、性能与生态差异。"
# OKF §4.1 tags(plugin 强化为 6 轴字典约束,详见 doc/template/tag-spec.md —— 本文件 tags: 行权威来源)
tags:
  - docform/technical-doc
  - domain/cross-domain
  - layer/middleware-soa
  - tec/someip

# OKF §5.1 sources(对比的两个对象 wiki 页)
sources:
  - id: lz-entity
    resource: ./knowledge/entities/product/layerzero.md
  - id: wh-entity
    resource: ./knowledge/entities/product/wormhole.md
  - id: cross-chain-theory
    resource: ./knowledge/concepts/theory/cross-chain-bridge.md

# OKF §5.2 generated
generated:
  by: "producer/aeps-llm-wiki-plugin/0.5.6"
  at: "2026-09-04T15:00:00Z"

# OKF §5.4 lifecycle(可选)
status: stable

# plugin 扩展字段
sources_count: 3

# plugin 推荐字段
updated: "2026-09-04T15:00:00Z"
summary: "LayerZero 走 Ultra Light Node 预言机轻客户端,Wormhole 走 Guardian 多签守护网络;两者在信任假设、性能、跨链消息安全性上各有取舍。"
---

# LayerZero vs Wormhole 跨链机制对比

【正文完全自由发挥。**正文链接主推 `[[wikilink]]` 裸文件名**(PRD §10 Q9,`doc/schema/schema.md` §3.1)。

comparison 页是**常驻**对照页(后续 LLM 可 update),不是 query 的一次性快照。LLM 根据对比对象的特性决定组织 —— 维度对比表 / 适用场景 / 风险点 / 决策树 / 时间线演进,任何结构都允许,**不锁骨架、不强制任何 H2 节名**。

**唯一硬约束**:
- frontmatter `sources:` 至少 2 条 entity/concept 页(lint C5 FAIL on 缺失)
- `sources_count` 推荐填写,实际 ≥ 2】

## 关联导引(Related Links,`doc/schema/schema.md` §3.1 规则 3)

- 综合:[[<wikilink>]]
- 分析:[[<wikilink>]]

---

## 维护说明(本节由 plugin 自动追加,可手删)

- 本页由 `/aeps-llm-wiki-ingest` 路径 A(同类 entity 触发)或 `/aeps-llm-wiki-query` 路径 B(累积检索触发)提议,**用户拍板才建**(PRD §4.6)
- 命名:**不带时间戳,常驻** `knowledge/comparisons/{a}-vs-{b}.md`
- lint 必查:
  - `type` 必须是 `comparison`(否则 FAIL)
  - `sources` 必填,至少 2 条 entity/concept 页(否则 FAIL)
  - `sources_count` 推荐填写,实际 ≥ 2
  - 正文**不锁骨架**(v0.5.7 起;旧版推荐的 `## 维度对比表` / `## 适用场景` / `## 风险点` 已废除)
  - C15.5 反转(PRD Q9):wikilink 不再 FAIL;`--fix` 反向将正文标准 markdown 链接 → `[[wikilink]]`(代码层待实现)
- 与 `type: analysis` **职责分开**:analysis 是 LLM 综合推演的一次性快照,comparison 是用户长期查阅的对照表(PRD §4.6 路径 C 决策)

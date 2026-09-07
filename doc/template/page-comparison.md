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
  by: "producer/aeps-llm-wiki-plugin/0.5.2"
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

【正文链接主推 `[[wikilink]]` 裸文件名(PRD §10 Q9,`doc/schema/schema.md` §3.1)。正文可放 `## 维度对比表` / `## 适用场景` / `## 风险点` 等;**常驻页**,后续 LLM 可 update。】

## 维度对比表

| 维度 | [[layerzero]] | [[wormhole]] |
|---|---|---|
| 信任假设 | 预言机 + Relayer 双签 | Guardian 多签守护网络 |
| 安全模型 | Ultra Light Node 轻客户端 | Guardian 节点验证 |
| 跨链消息延迟 | < 1 分钟 | 1-5 分钟 |
| TVL(2026-09) | $X | $Y |
| 适用场景 | 大量高频跨链消息 | 高价值跨链转账 |

## 适用场景

【基于 wiki 内 LayerZero / Wormhole 实体页与跨链桥概念页,总结两条路径的适用场景。】

## 风险点

【总结两条路径的已知风险与历史事故。】

## 关联导引(Related Links,`doc/schema/schema.md` §3.1 规则 3)

- 综合:[[automotive-functional-safety]]
- 分析:[[s32g-vs-s32k3-body-controller]]

---

## 维护说明(本节由 plugin 自动追加,可手删)

- 本页由 `/aeps-llm-wiki-ingest` 路径 A(同类 entity 触发)或 `/aeps-llm-wiki-query` 路径 B(累积检索触发)提议,**用户拍板才建**(PRD §4.6)
- 命名:**不带时间戳,常驻** `knowledge/comparisons/{a}-vs-{b}.md`
- lint 必查:
  - `type` 必须是 `comparison`(否则 FAIL)
  - `sources` 必填,至少 2 条 entity/concept 页(否则 FAIL)
  - `sources_count` 推荐填写,实际 ≥ 2
  - 正文不锁骨架(LLM 自由发挥)
  - C15.5 反转(PRD Q9):wikilink 不再 FAIL;`--fix` 反向将正文标准 markdown 链接 → `[[wikilink]]`(代码层待实现)
- 与 `type: analysis` **职责分开**:analysis 是 LLM 综合推演的一次性快照,comparison 是用户长期查阅的对照表(PRD §4.6 路径 C 决策)
---
# OKF v0.2 §4.1 必填字段
type: analysis
title: "S32G vs NXP S32K3 在车身控制器选型上的权衡"
description: "基于 wiki 已有 S32G / S32K3 实体页与功能安全概念页,综合推演两类芯片在车身控制器选型中的适用场景。"
# OKF §4.1 tags(plugin 强化为 6 轴字典约束,详见 doc/template/tag-spec.md —— 本文件 tags: 行权威来源)
tags:
  - docform/technical-doc
  - domain/body-gateway
  - layer/bsw-os
  - tec/nxp
  - phase/architecture

# OKF §5.1 sources(原 query 引用的 wiki 页)
sources:
  - id: s32g-entity
    resource: ./knowledge/entities/product/s32g.md
  - id: s32k3-entity
    resource: ./knowledge/entities/product/s32k3.md
  - id: autosar-concepts
    resource: ./knowledge/concepts/standard/autosar.md

# OKF §5.2 generated
generated:
  by: "producer/aeps-llm-wiki-plugin/0.5.2"
  at: "2026-09-04T14:00:00Z"

# OKF §5.4 lifecycle(可选)
status: stable

# plugin 扩展字段(G11 M1 + M2,analysis 专属必填)
answer_to: "S32G vs NXP S32K3 在车身控制器选型上怎么选?"
sources_used:
  - ./knowledge/entities/product/s32g.md
  - ./knowledge/entities/product/s32k3.md
  - ./knowledge/concepts/standard/autosar.md
sources_count: 3

# plugin 推荐字段
updated: "2026-09-04T14:00:00Z"
summary: "**问题**:S32G vs NXP S32K3 在车身控制器选型上怎么选?S32G 偏网关域,S32K3 偏车身控制域;核心差异在算力(应用处理器 vs 微控制器)、功能安全等级(ASIL D vs ASIL B)和软件栈(AUTOSAR Adaptive vs Classic)。"
---

# S32G vs NXP S32K3 在车身控制器选型上的权衡

## 方案推演 / 架构分析

【LLM 综合推演正文。从 query 引用的 wiki 页中抽取关键事实,组织成有逻辑链的方案推演。本节是 analysis 页的核心价值,替代原 sources 风格的"重点摘录",语义对齐"LLM 综合推演"。】

## 关联溯源

【本次推演用到的关键 Wiki 事实与依据。本节是 analysis 页的引用链 + 推演依据,替代原 sources 风格的"我的思考"。正文链接主推 `[[wikilink]]` 裸文件名(PRD §10 Q9),示例:`参考 [[s32g]] 与 [[s32k3]] 在功能安全等级上的差异...`。】

> 引用:[[s32g]], [[s32k3]], [[autosar]]

> 注意:`> 引用:` 行的链接列表必须与 frontmatter `sources_used` 字段**完全一致**(lint C15.4 Set 比对)。**禁止**从全文 grep 抽;**禁止**列入 `## 关联溯源` 段正文里出现过但未在引用行的页(PRD §8 风险表 G11)。

## 总结:最有收获的一句话

【一句话 Core Verdict / 核心结论。】

---

## 维护说明(本节由 plugin 自动追加,可手删)

- 本页由 `/aeps-llm-wiki-query` 在满足 G11 M3 gating 触发条件时**自动落档**(路径 `knowledge/analyses/{timestamp}-{slug}.md`)
- **3 节分析专属骨架硬约束**(lint C15.1,缺一即 FAIL):
  - `## 方案推演 / 架构分析`(替代 source 风格的 `## 重点摘录`)
  - `## 关联溯源`(替代 source 风格的 `## 我的思考`)
  - `## 总结:最有收获的一句话`
- **禁止**含 `## 重点摘录` / `## 我的思考` / `## 摘要` / `## Summary` H2
- lint 必查:C15.1(3 节骨架)+ C15.2(`sources_used` 每条路径存在)+ C15.3(gating 触发条件)+ C15.4(`> 引用:` 行与 `sources_used` 一致)+ C15.5(反转后:wikilink 不再 FAIL,标准 markdown 链接 → wikilink 自动转换,`--fix` 待实现,详见 `doc/schema/schema.md` §3.4 + `frontmatter-spec.md` §11.4)
- `--fix` 重写 `sources_used` 时**不动 `updated` 字段 + 文件 mtime**(Q7 死循环防护规则延续)

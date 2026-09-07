---
# OKF v0.2 §4.1 必填字段
type: "concept.theory"          # 子类:theory / method / field / phenomenon / standard / term / other
title: "LLM Wiki 模式"
description: "由 Andréj Karpathy 提出的基于 LLM 长期维护个人知识库的方法论:LLM 读源 → 写 wiki → 人策展。"
# OKF §4.1 tags(plugin 强化为 6 轴字典约束,详见 doc/template/tag-spec.md —— 本文件 tags: 行权威来源)
tags:
  - docform/technical-doc
  - domain/ai
  - layer/ai-agent
  - tec/langchain

# OKF §5.1 sources(指向关联的源页/原始资料)
sources:
  - id: karpathy-tweet
    resource: "https://x.com/karpathy/status/..."
    author: "human:karpathy"
  - id: self-related
    resource: ./knowledge/entities/person/andrej-karpathy.md

# OKF §5.2 generated
generated:
  by: "producer/aeps-llm-wiki-plugin/0.5.2"
  at: "2026-09-04T12:00:00Z"

# OKF §5.4 / §5.5 lifecycle(可选)
status: stable
stale_after: "2027-09-04T00:00:00Z"

# plugin 推荐字段
updated: "2026-09-04T12:00:00Z"
summary: "LLM Wiki 模式将 LLM 作为知识整理的执行者,人作为策展人,产出累积、互相链接、可长期演进的 markdown 知识库。"

# plugin 推荐字段(Obsidian 原生别名机制)
aliases:
  - "LLM Wiki"
  - "LLM-Wiki"
  - "Karpathy LLM Wiki"
---

# LLM Wiki 模式

【正文自由发挥,不强制小节。**正文链接主推 `[[wikilink]]` 裸文件名**(PRD §10 Q9,`doc/schema/schema.md` §3.1);本页通过 `aliases` 注册 [[LLM Wiki]] 等别名,wikilink 可直接使用别名。常见可选 H2:】

## 核心原则

【总结该概念的核心原则或定义。】

## 工作流

1. 第一步:把资料丢进 inbox/
2. 第二步:跑 /aeps-llm-wiki-ingest
3. 第三步:LLM 提议 + 用户拍板 + 文件迁 raw/
4. 第四步:跑 /aeps-llm-wiki-query 检索

## 与传统笔记的差异

【对比 Obsidian / Logseq / Notion / Evernote 等传统笔记工具。】

## 关联导引(Related Links,`doc/schema/schema.md` §3.1 规则 3)

- 对照:[[layerzero-vs-wormhole]]
- 综合:[[automotive-functional-safety]]

## 来源资料(由 ingest 自动生成)

【本节由 `/aeps-llm-wiki-ingest` 根据抽取本页的 `type: source` 源页列表生成,作为 source 页 `## 相关页面(Related Pages)` 的反向链接(双向反链)。每次 ingest **完全重建**本节,不保留人工添加的条目;没有任何 source 页引用本页时省略本节。链接使用源页的 `[[wikilink]]`,按源页 `title` 排序。】

---

## 维护说明(本节由 plugin 自动追加,可手删)

- 本页由 `/aeps-llm-wiki-ingest` 从源页抽取 concept 时自动生成,或用户手工创建
- `type` 取值必须与目录 1:1 绑死:`concept.theory` → `knowledge/concepts/theory/`
- concept 7 子类使用各自差异化模板(详见 `concept-entities-spec.md` §3),不再共用本骨架
- **aliases 字段**(plugin 推荐,概念页强推荐):常用缩写/同义词通过 `aliases: [...]` 注册,详见 `frontmatter-spec.md` §12.4
- lint 必查:同 entity;C15.5 反转(PRD Q9):wikilink 不再 FAIL,`--fix` 反向标准 markdown 链接 → `[[wikilink]]`(代码层待实现)

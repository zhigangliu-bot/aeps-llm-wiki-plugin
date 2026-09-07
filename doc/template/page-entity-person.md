---
# OKF v0.2 §4.1 必填字段
type: "entity.person"          # 子类:person / organization / project / product / event / place / other
title: "Andréj Karpathy"
description: "前特斯拉 AI 总监、OpenAI 创始成员,提出 LLM Wiki 模式的研究者。"
# OKF §4.1 tags(plugin 强化为 6 轴字典约束,详见 doc/template/tag-spec.md —— 本文件 tags: 行权威来源)
tags:
  - docform/study-notes
  - domain/ai
  - layer/ai-agent
  - tec/claude

# OKF §5.1 sources(指向关联的源页/原始资料)
sources:
  - id: self-source
    resource: ./raw/08_AI与AI工程/karpathy-bio.md

# OKF §5.2 generated
generated:
  by: "producer/aeps-llm-wiki-plugin/0.5.2"
  at: "2026-09-04T11:30:00Z"

# OKF §5.4 lifecycle(可选)
status: stable

# plugin 推荐字段
updated: "2026-09-04T11:30:00Z"
summary: "Karpathy 是 LLM-Wiki 理念的提出者,本实体页整理其代表工作与对个人知识管理的影响。"

# plugin 推荐字段(Obsidian 原生别名机制)
aliases:
  - "Andréj Karpathy"
  - "Karpathy"
---

# Andréj Karpathy

【正文自由发挥,不强制小节。**正文链接主推 `[[wikilink]]` 裸文件名**(PRD §10 Q9,`doc/schema/schema.md` §3.1);本页通过 `aliases` 注册 [[Karpathy]] 等别名,wikilink 可直接使用别名。常见可选 H2:】

## 代表工作

【列举 Karpathy 的代表项目/论文,每条用 `[[wikilink]]` 引用相关 wiki 页(如 [[llm-wiki]]、[[openai]]、[[tesla-ai]])。】

## 关键思想

【总结该人物的核心思想与方法论。】

## 关联导引(Related Links,`doc/schema/schema.md` §3.1 规则 3)

- 综合:[[automotive-functional-safety]]
- 分析:[[s32g-vs-s32k3-body-controller]]

## 来源资料(由 ingest 自动生成)

【本节由 `/aeps-llm-wiki-ingest` 根据抽取本页的 `type: source` 源页列表生成,作为 source 页 `## 相关页面(Related Pages)` 的反向链接(双向反链)。每次 ingest **完全重建**本节,不保留人工添加的条目;没有任何 source 页引用本页时省略本节。链接使用源页的 `[[wikilink]]`,按源页 `title` 排序。】

---

## 维护说明(本节由 plugin 自动追加,可手删)

- 本页由 `/aeps-llm-wiki-ingest` 从源页抽取 entity 时自动生成,或用户手工创建
- `type` 取值必须与目录 1:1 绑死:`entity.person` → `knowledge/entities/person/`
- 其他 6 个子类**各自有差异化骨架**(`page-entity-organization.md` / `project` / `product` / `event` / `place` / `other`),不再共用本骨架:
  - `entity.organization` → `page-entity-organization.md`
  - `entity.project` → `page-entity-project.md`
  - `entity.product` → `page-entity-product.md`
  - `entity.event` → `page-entity-event.md`
  - `entity.place` → `page-entity-place.md`
  - `entity.other` → `page-entity-other.md`
- **aliases 字段**(plugin 推荐,人名页强推荐):本页 `[[Karpathy]]` 别名通过 `aliases: [...]` 注册,`aliases` 详见 `frontmatter-spec.md` §12.4
- lint 必查:frontmatter 必填字段 + `type` 与目录一致 + 正文链接目标存在(`[[wikilink]]` 与标准 markdown 链接混用检测,优先 wikilink)
- C15.5 反转(PRD Q9):wikilink 不再 FAIL;`--fix` 反向将正文标准 markdown 链接 → `[[wikilink]]`(代码层待实现)
- 实体页**不强制 3 节骨架**(与 source / analysis 不同;lint 只校 frontmatter + 链接)

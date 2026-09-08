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
  by: "producer/aeps-llm-wiki-plugin/0.5.6"
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

【正文完全自由发挥,**不强制任何 H2 骨架**(v0.5.7 起;7 个差异化骨架 `## 代表工作` / `## 业务范围` / `## 项目目标` / `## 产品定位` / `## 会议概览` / `## 地理位置` / 兜底自由已全部废除)。

LLM 根据 entity 本身的特性决定如何组织 —— 7 子类(person / organization / project / product / event / place / other)之间的差异**不应**用 H2 节名体现,而应通过:
- `type: entity.<subtype>` 字段(type 字段是 schema,不是 layout 指令)
- `aliases` 注册常用缩写 / 同义词 / 别名(如 `[[AURIX]]` / `[[英飞凌]]`)
- `tags` 6 轴字典约束
- 自由正文的内部逻辑组织

**正文链接主推 `[[wikilink]]` 裸文件名**(PRD §10 Q9,`doc/schema/schema.md` §3.1);本页通过 `aliases` 注册的别名可直接用于 wikilink。

仅保留两个**结构性节**(由 plugin 自动追加 / 维护):
- `## 关联导引(Related Links)` —— LLM 可手填,非强制
- `## 来源资料` —— 由 `build-related-pages.js` 步骤 12 自动完全重建,LLM 不修改

lint 只校 frontmatter + 链接目标存在 + `> 引用:`(若有),不校 H2 结构。】

## 关联导引(Related Links,`doc/schema/schema.md` §3.1 规则 3)

- 综合:[[<wikilink>]]
- 分析:[[<wikilink>]]

## 来源资料(由 ingest 自动生成)

【本节由 `/aeps-llm-wiki-ingest` 根据抽取本页的 `type: source` 源页列表生成,作为 source 页 `## 相关页面(Related Pages)` 的反向链接(双向反链)。每次 ingest **完全重建**本节,不保留人工添加的条目;没有任何 source 页引用本页时省略本节。链接使用源页的 `[[wikilink]]`,按源页 `title` 排序。】

---

## 维护说明(本节由 plugin 自动追加,可手删)

- 本页由 `/aeps-llm-wiki-ingest` 从源页抽取 entity 时自动生成,或用户手工创建
- `type` 取值必须与目录 1:1 绑死:`entity.<subtype>` → `knowledge/entities/<subtype>/`(7 子类 person / organization / project / product / event / place / other 共用本通用模板)
- **不强制任何 H2 骨架**(v0.5.7 起)
- **aliases 字段**(plugin 推荐):常用缩写 / 同义词 / 别名通过 `aliases: [...]` 注册,详见 `frontmatter-spec.md` §12.4
- lint 必查:
  - frontmatter 必填字段
  - `type` 与目录一致
  - 正文链接目标存在(`[[wikilink]]` 与标准 markdown 链接混用检测,优先 wikilink)
  - C15.5 反转(PRD Q9):wikilink 不再 FAIL;`--fix` 反向将正文标准 markdown 链接 → `[[wikilink]]`(代码层待实现)
- 实体页**不强制 H2 骨架**;lint 只校 frontmatter + 链接(沿用 v0.5.6 之前的 entity 页规则,仅替换"差异化骨架"为"通用骨架")

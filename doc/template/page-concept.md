<!-- 提示:模板示例 tags 故意 ≥ 6 条,避免 LLM 按 5 条填导致 WARN;真实生成时按需保留全部或精简到 ≥ 5 条 -->
---
# OKF v0.2 §4.1 必填字段
type: $TYPE
title: "$TITLE"
description: "$DESCRIPTION"
# OKF §4.1 tags(plugin 强化为 6 轴字典约束,详见 doc/template/tag-spec.md —— 本文件 tags: 行权威来源)
tags:
  - docform/technical-doc
  - domain/ai
  - layer/ai-agent
  - tec/langchain
  - maturity/standard
  - phase/concept

# OKF §5.1 sources(指向关联的源页/原始资料;对象格式,gen-page 按 --source-resource/--source-title 注入)
sources:
  - resource: "[[<source-slug>]]"
    title: "来源页标题"

# OKF §5.2 generated
generated:
  by: "producer/aeps-llm-wiki-plugin/$VERSION"
  at: "$NOW"

# OKF §5.4 / §5.5 lifecycle(可选;stale_after 由 gen-page 自动推导,标准类 +5 年 / 其它 +1 年)
status: stable
stale_after: "$STALE_AFTER"

# plugin 推荐字段
updated: "$NOW"
summary: "$SUMMARY"

# plugin 推荐字段(Obsidian 原生别名机制;gen-page 按 --aliases 注入,缺省 fallback [title])
aliases:
  - "页面标题或常用别名"
---

# LLM Wiki 模式

【正文完全自由发挥,**不强制任何 H2 骨架**(v0.5.7 起;7 个差异化骨架 `## 核心原则` / `## 核心思想` / `## 领域范畴` / `## 现象描述` / `## 标准概述` / `## 定义` / 兜底自由已全部废除)。

LLM 根据 concept 本身的特性决定如何组织 —— 7 子类(theory / method / field / phenomenon / standard / term / other)之间的差异**不应**用 H2 节名体现,而应通过:
- `type: concept.<subtype>` 字段(type 字段是 schema,不是 layout 指令)
- `aliases` 注册常用缩写 / 同义词(术语页强推荐,如 `[[AaaS]]` / `[[算法即服务]]`)
- `tags` 6 轴字典约束
- `stale_after`(标准类默认 +5 年;其它 +1 年)
- 自由正文的内部逻辑组织

**正文链接主推 `[[wikilink]]` 裸文件名**(PRD §10 Q9,`doc/schema/schema.md` §3.1);本页通过 `aliases` 注册的别名可直接用于 wikilink。

仅保留两个**结构性节**(由 plugin 自动追加 / 维护):
- `## 关联导引(Related Links)` —— LLM 可手填,非强制
- `## 来源资料` —— 由 `build-related-pages.js` 步骤 12 自动完全重建,LLM 不修改

lint 只校 frontmatter + 链接目标存在,不校 H2 结构。】

## 关联导引(Related Links,`doc/schema/schema.md` §3.1 规则 3)

- 对照:[[<wikilink>]]
- 综合:[[<wikilink>]]

## 来源资料(由 ingest 自动生成)

【本节由 `/aeps-llm-wiki-ingest` 根据抽取本页的 `type: source` 源页列表生成,作为 source 页 `## 相关页面(Related Pages)` 的反向链接(双向反链)。每次 ingest **完全重建**本节,不保留人工添加的条目;没有任何 source 页引用本页时省略本节。链接使用源页的 `[[wikilink]]`,按源页 `title` 排序。】

---

## 维护说明(本节由 plugin 自动追加,可手删)

- 本页由 `/aeps-llm-wiki-ingest` 从源页抽取 concept 时自动生成,或用户手工创建
- `type` 取值必须与目录 1:1 绑死:`concept.<subtype>` → `knowledge/concepts/<subtype>/`(7 子类 theory / method / field / phenomenon / standard / term / other 共用本通用模板)
- concept 7 子类**不再差异化骨架**(v0.5.7 起;详见 `concept-entities-spec.md` §2-§3 变更历史)
- **不强制任何 H2 骨架**(v0.5.7 起)
- **aliases 字段**(plugin 推荐):常用缩写 / 同义词 / 别名通过 `aliases: [...]` 注册,详见 `frontmatter-spec.md` §12.4
- lint 必查:
  - frontmatter 必填字段
  - `type` 与目录一致
  - 正文链接目标存在(`[[wikilink]]` 与标准 markdown 链接混用检测,优先 wikilink)
  - C15.5 反转(PRD Q9):wikilink 不再 FAIL;`--fix` 反向将正文标准 markdown 链接 → `[[wikilink]]`(代码层待实现)
- 概念页**不强制 H2 骨架**;lint 只校 frontmatter + 链接(沿用 v0.5.6 之前的 concept 页规则,仅替换"差异化骨架"为"通用骨架")

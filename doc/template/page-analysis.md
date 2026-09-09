<!-- 提示:模板示例 tags 故意 ≥ 6 条,避免 LLM 按 5 条填导致 WARN;真实生成时按需保留全部或精简到 ≥ 5 条 -->
---
# OKF v0.2 §4.1 必填字段
type: analysis
title: "$TITLE"
description: "$DESCRIPTION"
# OKF §4.1 tags(plugin 强化为 6 轴字典约束,详见 doc/template/tag-spec.md —— 本文件 tags: 行权威来源)
tags:
  - docform/technical-doc
  - domain/body-gateway
  - layer/bsw-os
  - tec/nxp
  - phase/architecture
  - maturity/analysis

# OKF §5.1 sources(原 query 引用的 wiki 页)
sources: $SOURCES

# OKF §5.2 generated
generated:
  by: "producer/aeps-llm-wiki-plugin/$VERSION"
  at: "$NOW"

# OKF §5.4 lifecycle(可选)
status: stable

# plugin 扩展字段(G11 M1 + M2,analysis 专属必填)
answer_to: "$ANSWER_TO"
sources_used: $SOURCES_USED
sources_count: $SOURCES_COUNT

# plugin 推荐字段
updated: "$NOW"
summary: "$SUMMARY"
---

# S32G vs NXP S32K3 在车身控制器选型上的权衡

【正文完全自由发挥。**正文链接主推 `[[wikilink]]` 裸文件名**(PRD §10 Q9,`doc/schema/schema.md` §3.1),示例:`参考 [[s32g]] 与 [[s32k3]] 在功能安全等级上的差异...`。

**这是 analysis 页唯一保留的硬约束**:
- 文末必须出现一行 `> 引用:[[a]], [[b]], [[c]]`,其 wikilink 列表必须与 frontmatter `sources_used` 字段**完全一致**(lint C15.4 Set 比对)
- **禁止**从全文 grep 抽;**禁止**列入正文里出现过但未在引用行的页(PRD §8 风险表 G11)

LLM 根据 query 性质与所引 wiki 页决定如何组织正文 —— 方案推演 / 维度对比 / 利弊权衡 / 决策树 / 适用场景 / 风险点,任何结构都可以。**不锁骨架、不强制任何 H2 节名**。如果 LLM 想写 `## 方案推演 / 架构分析` 或 `## 关联溯源` 来对齐旧模板风格,完全 OK;但**不写这两节也不会 FAIL**。】

## 关联导引(Related Links)

- 综合:[[<wikilink>]]
- 对照:[[<wikilink>]]

---

## 维护说明(本节由 plugin 自动追加,可手删)

- 本页由 `/aeps-llm-wiki-query` 在满足 G11 M3 gating 触发条件时**自动落档**(路径 `knowledge/analyses/{timestamp}-{slug}.md`)
- **唯一硬约束**(lint C15.4):
  - 文末 `> 引用:` 行必须存在;其 wikilink 列表必须与 `sources_used` Set 一致
- **不强制任何 H2 骨架**(v0.5.7 起;旧版 3 节专属骨架 `## 方案推演 / 架构分析` + `## 关联溯源` + `## 总结:最有收获的一句话` 已废除)
- **禁止** 含 `## 摘要` / `## Summary` H2(走 frontmatter `summary`)
- lint 必查:
  - C15.2(`sources_used` 每条路径存在)
  - C15.3(gating 触发条件)
  - C15.4(`> 引用:` 行与 `sources_used` 一致)
  - C15.5(反转后:wikilink 不再 FAIL,标准 markdown 链接 → wikilink 自动转换,`--fix` 待实现,详见 `doc/schema/schema.md` §3.4 + `frontmatter-spec.md` §11.4)
- `--fix` 重写 `sources_used` 时**不动 `updated` 字段 + 文件 mtime**(Q7 死循环防护规则延续)
- C2 变更(v0.5.7):analysis 不再强制 3 节骨架;lint C4 改为"无 H2 存在性要求,仅校验 `> 引用:` 行"

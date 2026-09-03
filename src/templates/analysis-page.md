# analysis-page.md — analyses/ 页生成模板

> **角色**:query skill 落档 `type: analysis` 页时的 frontmatter + 正文骨架模板。
> **生成方**:`/aeps-llm-wiki-query` 落档阶段调用(详见 prd §4.3 + design §4.3.2)
> **修改权限**:生成后归用户主,plugin 不再覆盖
> **G11 v0.5.0 升级**:`analyses/` **不再复用** `sources/` 的 3 节骨架,改用**分析专属骨架** —— 语义对齐"LLM 综合推演"而非"human reading material"

---

## frontmatter 锁

```yaml
---
type: analysis
title: "<一句话标题,通常 <slug> kebab-case 转可读>"
updated: <ISO 8601>           # 最近一次有意义更新(重新生成 ≠ 更新)
tags: [<六轴受控词表 tag>]     # 详见 templates/tag-template.md
status: stable                 # draft / stable / deprecated,缺省 stable

# G11 v0.5.0 必填 — 溯源链(M2 溯源丢失修复,详见 prd §4.3 + lint C15.2 + design §3.6)
# - sources_used: 本次回答参考的 wiki 页相对路径列表,字符串数组,每条形如:
#   sources/<basename>.md / entities/<子类>/<slug>.md / concepts/<子类>/<slug>.md
#   / syntheses/<slug>.md / comparisons/<a>-vs-<b>.md
# - 与 ## 关联溯源 末尾 `> 引用:` 行镜像同步(Set 比对,Q7 死循环防护)
# - Q7: --fix 重写不动 updated 字段 + 文件 mtime
sources_used:
  - sources/<basename-1>.md
  - entities/person/<basename-2>.md
  - syntheses/<topic-slug>.md

# G11 v0.5.0 必填 — 原问题保留(便于 LLM 检索上下文)
answer_to: "<原 query 问句原样>"

# G11 v0.5.0 必填 — plugin 写入统一格式
generated_by: agent: producer/aeps-llm-wiki-plugin/<version>

# 长摘要(≤ 280 字符,首行强制保留 query 原问句,**问题**: 前缀,纪律见 design §3.1 §C)
summary: |
  **问题**: <原问句>
  <一段话总结本次推演的核心结论与推演依据,≤ 280 字符>
---

# G11 v0.5.0 — links 镜像(OKF v0.2 §9 + Q6 双格式同步,详见 design §3.6.2)
# - analysis 页通常引用多个 wiki 页;links 镜像按正文 ## 关联溯源 段的 wikilink 列表自动同步
# - Q7 死循环防护: --fix 重写不动 updated + 文件 mtime
# - 允许手填,但建议由 lint --fix 自动维护
links:
  - "[[<wikilink-1>]]"
  - "[[<wikilink-2>]]"
```

### G11 四必填字段的写入指引

1. **`sources_used`**(G11 M2):
   - **必填**,string[],空数组 / 字段缺失 → lint C15.2 FAIL
   - **路径校验**:每条字符串相对 `knowledge/` 必须解析到真实存在的 `.md` 文件
   - **派生来源**:**仅**从 `## 关联溯源` 末尾 `> 引用:` 行 + query 阶段实际引用路径抓,**禁止**从全文 grep 抽
   - **去重**:相同路径出现多次只保留一条
   - **lint 断言**(lint C15.2):
     - 字段存在且非空
     - 每条路径文件存在
     - Q7 重写不动 `updated` + 文件 mtime
2. **`answer_to`**:原 query 问句**原样**保留(便于后续 LLM 检索上下文,grep `answer_to: "..."` 可复现"这个问题当初是怎么问的")
3. **`generated_by`**:固定格式 `agent: producer/aeps-llm-wiki-plugin/<version>`,`<version>` 取自 `raw/.aeps-plugin-version`(详见 SCHEMA.md §4 actor 字符串)
4. **`summary`**(沿用 §3.1 §C 纪律):
   - 首行强制 `**问题**: <原问句>`
   - 余下 ≤ 280 字符 multiline
   - **禁止**包含 `## 摘要` 小节对应的内容(长摘要走这里)

### LLM 写入指引

1. `sources_used` 写入时机:**query 回答生成时**,SKILL.md 阶段 3 末尾,从阶段 2 命中的 wiki 页 + 阶段 3 实际引用路径自动抓
2. `answer_to` 写入时机:同 `sources_used`,从 query 原问句原样拷
3. `generated_by` 写入时机:同 `sources_used`,`<version>` 取自 plugin `package.json` / `pyproject.toml` 的 `__version__`
4. `summary` 首行 `**问题**: ` 前缀**强制保留**,**禁止**省略
5. `updated` 字段值反映**内容**变更时间,**不是**文件重新生成时间(沿用 SCHEMA.md §2.3 纪律)
6. `links:` 镜像字段(Q6 + G10 M3 延续):SKILL.md 写完正文后,扫 `## 关联溯源` 段所有 `[[wikilink]]` 自动生成;Q7 死循环防护

## 正文骨架锁(分析专属 3 节 H2 硬约束,G11 M1,lint C15.1)

```markdown
## 方案推演 / 架构分析

<本次推演的核心分析与架构逻辑,语义对齐"LLM 综合推演">

- 不再是 sources 风格的"原文摘出来"(analysis 页没有原文可摘)
- 重点是:**面对 query,LLM 是怎么推演的?核心假设 / 推理链 / 边界条件 / 备选方案对比 / 结论**

## 关联溯源

<本次推演用到的关键 Wiki 事实与依据,语义对齐"引用链 + 推演依据">

- 每条依据附 wiki 链接(Q6 `[[wikilink]]` 一等公民)
- 末尾**强制**追加 `> 引用:` 行列源路径,与 frontmatter `sources_used` Set 比对(详见 lint C15.4)

> 引用: sources/foo.md, entities/person/bar.md, syntheses/topic.md

## 总结:最有收获的一句话

<一句话 Core Verdict / 核心结论,可独立成立,无前言后语>
```

### LLM 写入正文指引

1. **3 节齐全,缺一 FAIL**(lint C15.1)
2. **禁止 `## 摘要` / `## Summary` / `## 重点摘录` / `## 我的思考` 小节**(lint C15.1 forbidden_h2,语义不符)
3. **`[[wikilink]]` 一等公民**(Q6 + design §3.6.2):指向已有 entity / concept / 其他 source / 另一个 analysis 页用 `[[page]]` / `[[page|显示]]` / `[[page#章节]]`
4. **`> 引用:` 行镜像**:位于 `## 关联溯源` 段末尾,与 frontmatter `sources_used` 走 Set 比对(lint C15.4);逗号分隔,无尾逗号
5. **`## 方案推演 / 架构分析` 写的是"推演"**:不是"摘录",不是"事实复述";是**面对 query 的逻辑链** —— 假设 → 推理 → 边界 → 结论
6. **`## 关联溯源` 写的是"依据"**:每条用一句简短陈述 + `[[wikilink]]`,末尾 `> 引用:` 行汇总路径(便于 lint 校验)

---

## 与 sources/ 骨架的对比(G11 M1 动机)

| 维度       | sources/ 骨架(读后感)              | analyses/ 骨架(G11 综合推演)                       |
| ---------- | ---------------------------------- | -------------------------------------------------- |
| 触发       | ingest 时 LLM 读源后写              | query 时 LLM 答用户问后写                          |
| 输入       | 原始资料(已有原文可摘)             | query 问句(无原文可摘,需 LLM 推演)                |
| ## 第一节  | `## 重点摘录`(原文摘出)            | `## 方案推演 / 架构分析`(LLM 推演逻辑)             |
| ## 第二节  | `## 我的思考`(读后感)              | `## 关联溯源`(引用链 + 依据)                       |
| ## 第三节  | `## 总结:最有收获的一句话`          | 同(语义对齐"Core Verdict")                         |
| 溯源机制   | frontmatter `sources[].resource`   | frontmatter `sources_used` + `> 引用:` 镜像行       |
| 落档询问   | ingest 拍板后直接写盘               | query 受 gating 控制(详见 design §4.3.2)           |
| 长度       | 中等(读后感 200-500 字)            | 中等偏长(综合推演 300-800 字)                      |

**为什么 v0.5.0 起分开**(M1 结构断层):硬塞 sources 骨架到 analysis 页 = 把"综合推演"伪装成"摘录",失真。专属骨架把"推演逻辑"和"引用依据"显式分两节,语义对齐"LLM 综合推演"的人脑活动流。

---

## G11 不应做(analysis 页 frontmatter 写入侧)

- ❌ 不在 frontmatter 留 `summary` 与 `answer_to` 的哈希相关字段(可由 lint 按需计算,非 AC)
- ❌ 不为 `sources_used` 字段填非 wiki 路径(如 `https://...` / `raw/...` —— 这些走 `sources[].resource`,不是 `sources_used`)
- ❌ 不在正文写 `## 重点摘录` / `## 我的思考`(sources 风格,lint C15.1 forbidden_h2)
- ❌ 不在 `> 引用:` 行用 markdown 链接 / 完整路径,**只用 wikilink 形式**(`sources/foo.md` 不加方括号)
- ❌ 不在 query 落档询问被 gating 跳过时仍写盘(详见 design §4.3.2,不触发 → 不问 → 不写)

## 文件名约定

- 路径:`knowledge/analyses/<时间戳>-<slug>.md`
- `<时间戳>` 格式:`YYYYMMDDTHHmmss`(ISO 8601 basic,无冒号无连字符,与文件系统兼容)
- `<slug>` kebab-case,LLM 从 query 问句自动生成
- 中文 / 空格 / 大写在 `<slug>` 里**保留原样**(与 sources/ 一致)

## 不变量

- **G11 lint C15.1** —— 3 节 H2 骨架齐全(`## 方案推演 / 架构分析` + `## 关联溯源` + `## 总结:最有收获的一句话`);不含 `## 重点摘录` / `## 我的思考` / `## 摘要` / `## Summary`(缺 / 含任一即 FAIL)
- **G11 lint C15.2** —— `sources_used` 必填且每条路径解析到真实存在的 `knowledge/**/*.md`(FAIL)
- **G11 lint C15.4** —— `## 关联溯源` 末尾 `> 引用:` 行与 frontmatter `sources_used` Set 比对,不一致 WARN(Q7 死循环防护:`--fix` 重写不动 `updated` + 文件 mtime)
- `summary` 字段首行 `**问题**: ` 前缀强制保留(沿用 §3.1 §C 纪律)
- 6 轴 tag 受控词表(详见 `templates/tag-template.md`)
- `updated` 字段值反映**内容**变更时间,**不是**文件重新生成时间

## 引用

- `templates/knowledge-SCHEMA.md` §2.2(analysis 类型必填字段)+ §3.1(正文骨架纪律)
- `templates/source-page.md`(对比 G11 前后骨架差异表)
- `design.md` §3.6(分析页结构 + sources_used 派生)+ §4.3.2(落档 gating)+ §5.4(lint C15.1-C15.4 详解)
- `prd.md` §4.3(query skill G11 M1-M3)+ §7.1 AC-11/AC-12/AC-13
- `implement.md` §C15(G11 4 个 fixture:test_analysis_dedicated_skeleton / test_analysis_sources_used_required / test_query_gating_logic / test_analysis_sources_used_mirror)

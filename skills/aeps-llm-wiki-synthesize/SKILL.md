---
name: aeps-llm-wiki-synthesize
description: 写 / 更新常驻综合页 knowledge/syntheses/<topic-slug>.md(不带时间戳)。聚合所有 entity/concept 页 + 引用它们的 source 页(LLM 决定边界)。重复触发同 topic → update 而非新建。
---

# aeps-llm-wiki-synthesize

> **触发**:`/aeps-llm-wiki-synthesize <topic> [--project-dir <path>]`
> **权威设计**:`src/prd.md §4.5` + `src/design.md §4.5`
> **对应实现阶段**:plugin v0.5.5 阶段 B

## 必读文件

启动 skill 时,**先 Read**:

| 优先级 | 路径 | 用途 |
|---|---|---|
| 1 | `<project>/knowledge/SCHEMA.md` | 用户操作手册(必读) |
| 2 | `<project>/knowledge/index.md` | 主索引(筛 topic 相关页) |
| 3 | `<project>/knowledge/log.md` | 现有 synthesis 历史 + 重复触发检测 |
| 4 | `<project>/raw/raw-readme.md`(若 raw/ 已存在) | 派生 raw_category |
| 5 | `aeps-llm-wiki-plugin/src/schema/frontmatter.schema.yaml`(若已落地) | frontmatter schema 校验 |

## 工作流

### 阶段 1:解析 topic

- topic 形如 "OKF 生态全景" / "AUTOSAR 实战方法论" / "ISO 26262 与 SOTIF 的关系"
- SKILL.md 在 Claude 对话层接收用户输入

### 阶段 2:检测是否已存在(重复触发判定)

检查 `<project>/knowledge/syntheses/<topic-slug>.md` 是否存在:

- **存在** → 走 **§阶段 3 update** 流程(同 slug 覆盖式更新)
- **不存在** → 走 **§阶段 4 创建** 流程

**slug 派生规则**:topic 字符串小写 → 全角转半角 → 空格 → `-` → 去标点 → 全小写 + 连字符。例:

- "OKF 生态全景" → `okf-生态全景`(中文保留)
- "AUTOSAR 实战方法论" → `autosar-实战方法论`
- "ISO 26262 与 SOTIF 的关系" → `iso-26262-与-sotif-的关系`

### 阶段 3:update 流程(已存在)

1. **不动** `updated` 字段(Q7 死循环防护:写盘逻辑在 scripts 实现层强制 stat → write → utime 4 步,SKILL.md 不直接写盘)
2. **更新** `last_updated` 字段为当前 ISO 8601
3. 重新读 topic 相关页,**追加** 新观点 / 删去过时段落
4. **更新** `sources_count`(重新统计引用页数)
5. log.md 追加 `**Update**`(不是 `**Creation**`):
   ```markdown
   * **Update**: synthesized update on [topic-slug.md](syntheses/<topic-slug>.md) — sources_count now N
   ```

### 阶段 4:创建流程(不存在)

#### 4.1 收集相关页(LLM 决定边界)

默认范围:**所有 entity/concept 页 + 引用它们的 source 页**。

筛选规则:

- 读 `index.md`,筛 frontmatter 含 topic tag 或被 tag 关联的页
- 读 entity/concept 页的 `aliases` / `description` / 关键词
- 读 source 页 frontmatter `tags` + `description`
- LLM 综合判断边界(允许扩张 / 收紧)

#### 4.2 写 synthesis 页

路径:`<project>/knowledge/syntheses/<topic-slug>.md`(**不带时间戳,常驻**)

**frontmatter 必填**:

```yaml
type: synthesis
title: <topic 原始字符串>
topic: <topic 原始字符串>
sources_count: <N>                 # 引用页数,lint 评估成熟度的硬指标
last_updated: <ISO 8601>
updated: <ISO 8601>
tags:
  - <6 轴 tag,至少含 maturity + docform>
generated:
  by: agent: producer/aeps-llm-wiki-plugin/0.5.5
  at: <ISO 8601>
links:
  - type: wikilink
    target: <相关页 1>
  - type: wikilink
    target: <相关页 2>
summary: |
  <2-3 句话主题脉络>
```

**正文**:**自由发挥**(典型结构 = 主题脉络梳理 + 多观点融合 + 个人判断)。

**禁止 H2**(同 sources / analyses 纪律):

- `## 摘要` / `## Summary`(违规 FAIL)

**不强制** 3 节骨架(entities / concepts / comparison / synthesis 正文**自由发挥**,只有 sources / analyses 锁骨架)。

#### 4.3 更新索引

- `<project>/knowledge/index.md` 追加条目:
  ```markdown
  - [topic-slug](syntheses/<topic-slug>.md) — type: synthesis · sources_count: N · <一句话>
  ```
- `<project>/knowledge/log.md` 追加:
  ```markdown
  * **Creation**: synthesize "<topic>" → [topic-slug.md](syntheses/<topic-slug>.md) by agent: producer/aeps-llm-wiki-plugin/0.5.5
  ```

## 不应做

1. **不写一次性"当时综合"**(那是 `analysis` → `analyses/<时间戳>-<slug>.md`,**不是** `synthesis`)。
2. **不带时间戳**(`syntheses/<topic-slug>.md`,**不带时间戳,常驻**,后续 LLM 可 update)。
3. **不写 `sources_count < 3` 的合成页**(lint 警告空综合;若确实资料不足,提示用户先 `/aeps-llm-wiki-ingest`)。
4. **不写正文 `## 摘要` / `## Summary` H2**(沿用 §3.1 §C 纪律)。
5. **不强制 3 节骨架**(entities / concepts / comparison / synthesis 正文**自由发挥**,只有 sources / analyses 锁骨架)。
6. **不覆盖已存在的 synthesis 页内容**(synthesis 是常驻,update 而非 overwrite;走 §阶段 3 update 流程)。
7. **不在 frontmatter `updated` 字段做不必要的改写**(对齐 Q7 死循环防护业务意图,update 流程仅改 `last_updated`)。
8. **不调用 convert-to-md.py / safe-mv.py 等写操作脚本**(synthesize 是纯 LLM 读源 + 写文件)。
9. **不创建 `<project>/syntheses/` 目录**(固定路径是 `<project>/knowledge/syntheses/`)。
10. **不在 user-project 写 plugin 本体路径或绝对路径**(对齐 NFR-4)。

## 输出格式

### 创建完成

```markdown
✅ 已创建常驻综合页:knowledge/syntheses/<topic-slug>.md
- topic: <原始 topic>
- sources_count: <N> 页
- 引用页列表(摘):
  - [page 1](<path>)
  - [page 2](<path>)
- log.md: append 1 条 **Creation**
- index.md: append 1 条
- 下一步:可再次跑 `/aeps-llm-wiki-synthesize <topic>` 更新
```

### 更新完成

```markdown
✅ 已更新常驻综合页:knowledge/syntheses/<topic-slug>.md
- 上次 last_updated: <原 ISO 8601>
- 本次 last_updated: <新 ISO 8601>
- sources_count: <旧 N> → <新 N>
- 新增引用页(摘):
  - [new page](<path>)
- log.md: append 1 条 **Update**
```

### sources_count < 3 警告

```
💡 topic "<topic>" 当前仅聚合 N(< 3) 页相关资料,sources_count 不足。
建议:
1. 先跑 /aeps-llm-wiki-ingest 把更多资料丢进 inbox
2. 或缩小 topic 范围,聚焦某子主题
是否继续创建(sources_count 留 N)?[y/n]
```

### 重复触发提示

```
💡 synthesis "<topic-slug>" 已存在(创建于 <ISO 8601>)。
   走 update 流程(同 slug 覆盖式更新,不创建新页)。
   继续?[Y/n]
```

## 脚本调用

本 skill **基本无 scripts 调用**(纯 LLM 读源 + 写文件)。

可选辅助(写完后建议运行):

```bash
python3 ./scripts/validate-frontmatter.py \
  --project-dir . \
  --file knowledge/syntheses/<topic-slug>.md
# Bash timeout: 30000
```

(此为**建议**,不在 synthesize 流程强制)。

## 与 analysis / comparison 的边界

| 类型 | 路径 | 时间戳 | 触发 | 锁骨架 |
|---|---|---|---|---|
| **source** | `knowledge/sources/<basename>.md` | 不带 | ingest | 3 H2(`## 重点摘录` / `## 我的思考` / `## 总结`) |
| **entity** | `knowledge/entities/<子类>/<slug>.md` | 不带 | ingest 抽取 | 自由发挥 |
| **concept** | `knowledge/concepts/<子类>/<slug>.md` | 不带 | ingest 抽取 | 自由发挥 |
| **analysis** | `knowledge/analyses/<timestamp>-<slug>.md` | **带** | query 落档(用户同意) | 3 H2 G11(`## 方案推演` / `## 关联溯源` / `## 总结`) |
| **comparison** | `knowledge/comparisons/<a>-vs-<b>.md` | 不带 | ingest 路径 A / query 路径 B / 路径 C | 自由发挥 |
| **synthesis** | `knowledge/syntheses/<topic-slug>.md` | 不带 | synthesize | **自由发挥**(唯一不锁骨架的"知识页") |
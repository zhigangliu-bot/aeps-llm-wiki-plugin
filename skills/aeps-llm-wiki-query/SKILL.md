---
name: aeps-llm-wiki-query
description: 基于 knowledge/ 知识库回答用户问题。4 跳扫描(index 模式)或 qmd query(qmd 模式)。落档 gating 防止 over-prompting:intent=overview/comparison 或回答 ≥ 200 字 / ≥ 2 子目录源时问"是否存为 analysis";exact/ambiguous/短答/单源/未覆盖时跳过。
---

# aeps-llm-wiki-query

> **触发**:`/aeps-llm-wiki-query <question> [--project-dir <path>]`
> **权威设计**:`src/prd.md §4.3` + `src/design.md §4.3` + `§4.3.1 4 跳扫描` + `§4.3.2 落档 gating` + `§5.2` + `§5.3`
> **对应实现阶段**:plugin v0.5.5 阶段 B
> **关键 PATCH**:G11 analysis 专属骨架 + C15 gating 规则 + 路径 B comparison 累积触发 + v0.5.2 ambiguous fallback

## 必读文件

启动 skill 时,**先 Read**:

| 优先级 | 路径 | 用途 |
|---|---|---|
| 1 | `<project>/knowledge/SCHEMA.md` | 用户操作手册(必读) |
| 2 | `<project>/knowledge/index.md` | 主索引(跳 1 强候选过滤) |
| 3 | `<project>/knowledge/glossary.md` | 术语消歧(跳 4) |
| 4 | `<project>/knowledge/log.md`(最近 10 条) | 跳 4 + 路径 B 累积探测 |
| 5 | `<project>/knowledge/overview.md` | 跨主题脉络 |
| 6 | `aeps-llm-wiki-plugin/src/templates/analysis-page.md` | G11 专属骨架(落档用) |
| 7 | `aeps-llm-wiki-plugin/src/scripts/README.md` | scripts/ 约定 |
| 8 | `aeps-llm-wiki-plugin/src/schema/frontmatter.schema.yaml`(若已落地) | frontmatter schema 校验 |

## 工作流

### 阶段 0:引擎决策

```bash
python3 ./scripts/check-qmd.py --project-dir .
# 返回 JSON: {"pageCount": N, "qmdAvailable": bool, "qmdVersion": "...", "engine": "index"|"qmd"|"fail", "reason": "..."}
```

**阈值常量**(硬编码):

```python
QUERY_CANDIDATE_K = 10
QUERY_NEIGHBOR_MAX = 8
QUERY_LOG_RECENT = 10
QUERY_INDEX_THRESHOLD = 500
QUERY_QMD_REQUIRED_THRESHOLD = 1000
```

**引擎决策矩阵**:

| N(页数) | qmd 状态 | engine | 行为 |
|---|---|---|---|
| N < 500 | 任意 | `index` | 走 §阶段 2 4 跳扫描 |
| 500 ≤ N < 1000 | 已装 | `qmd` | 走 §阶段 2 qmd query |
| 500 ≤ N < 1000 | 未装 | `index` | 走 §阶段 2 4 跳扫描 + 提示"推荐装 qmd" |
| N ≥ 1000 | 已装 | `qmd` | 走 §阶段 2 qmd query |
| N ≥ 1000 | 未装 | `fail` | **直接退出**,提示"必须装 qmd" |

`engine == "fail"` 退出码非 0,输出:

```
❌ knowledge/ 页数 N ≥ QUERY_QMD_REQUIRED_THRESHOLD(1000),qmd 强依赖未装。
请先安装:npm install -g @tobilu/qmd
```

### 阶段 1:Intent 路由(LLM 阶段 3 推断)

LLM 读 `<user-question>` 后推断 intent ∈ {`exact`, `ambiguous`, `overview`, `comparison`, `other`}。

| intent | 含义 | 示例 |
|---|---|---|
| `exact` | 单点查证 | "ISO 26262 ASIL D 等级是多少?" |
| `ambiguous` | 语义模糊,LLM 无法稳定分类 | "这篇芯片文档和上一篇有什么异同?" |
| `overview` | 跨领域综述 | "AUTOSAR 整体架构" |
| `comparison` | 对比 | "SOME/IP vs DDS" |
| `other` | 无法归入上述 | (兜底) |

### 阶段 2:候选检索(2 模式)

#### 模式 A:index 4 跳扫描(N < 500 / qmd 未装降级)

**跳 1:index.md 过滤**

- 读 `<project>/knowledge/index.md` 全部条目
- tags 与 query 关键词匹配,选 `top-K`(K = `QUERY_CANDIDATE_K = 10`)为**强候选**
- tags 命中的条目优先入选

**跳 2:读强候选页**

- 按优先级读 `description` / `summary` / `title` / 全文
- 选 ≤ K 个**最相关页**

**跳 3:`[[wikilink]]` 邻居(深度 1,硬上限 8 页)**

- 优先级降权读:
  1. frontmatter `sources[]` 数组
  2. `## 关联溯源` 末尾 `> 引用:` 行
  3. `syntheses/*` 的 `## 子主题` + `## 引用` 段
  4. 正文其他 `[[wikilink]]`(降权不忽略)
- **硬上限** `QUERY_NEIGHBOR_MAX = 8`;**不**递归深度 > 1(避免雪崩)

**跳 4:glossary + log + comparison 累积**

- glossary 提供同义词消歧
- log 最近 `QUERY_LOG_RECENT = 10` 条用于上下文
- **路径 B 探测**:grep `**Creation**: ... query "X.*Y"` 模式(全 `**Creation**` 而非 `**Update**`,避免旧数据误触发),X.*Y 是对比对象对(如 "SOME/IP vs DDS")
- 累计 ≥ 3 次 → **触发**路径 B 提示(见 §阶段 4 落档模板)

#### 模式 B:qmd query(qmd 模式)

```bash
qmd query "<question>" --collection knowledge --limit 20
# --limit 20:plugin 预设上限
```

拿 top-20 进入跳 2 / 跳 3(同上)。

### 阶段 3:Gating(决定是否问"是否落档")

**伪代码**:

```python
def should_prompt_save(intent, answer_length, sources_by_subdir, answer_body):
    # 跳过条件(任一命中即跳过)
    if intent in {"exact", "ambiguous"}:
        return "skip"
    if "Wiki 未覆盖" in answer_body:
        return "skip"
    if answer_length < 200:
        return "skip"
    if len(sources_by_subdir) < 2:
        return "skip"

    # 触发条件(任一命中即问)
    if intent in {"overview", "comparison"}:
        return "prompt"
    if answer_length >= 200:
        return "prompt"
    if len(sources_by_subdir) >= 2:
        return "prompt"

    # 兜底
    return "skip"
```

**优先级澄清**:

- 跳过条件**优先于**触发条件(v0.5.2 PATCH ambiguous fallback)
- `intent == "ambiguous"` 即使其他条件触发,也走跳过(避免 LLM 误判被兜底绕过)
- `intent == "other"` 走触发路径(仅 ambiguous 走跳过)

**回答末尾必加标记**(lint C15.3 FAIL 若缺失):

- 触发 → `❓ ... [Y/n]`
- 跳过 → `💡 ... 跳过落档询问`

### 阶段 4:落档(用户同意后)

#### 4.1 analysis 页(G11 专属)

路径:`<project>/knowledge/analyses/<ISO 8601 timestamp>-<slug>.md`

**时间戳格式**:`2026-09-01T14-30-00Z`(冒号 → 连字符,Windows 文件名安全)。

**frontmatter 必填**:

```yaml
type: analysis
title: <回答主题>
answer_to: <原问句>                       # 一句话回填
sources_used:                              # string[],lint C15.2 FAIL 若缺失
  - sources/autosar-classic-overview.md
  - concepts/standard/autosar.md
generated_by: agent: producer/aeps-llm-wiki-plugin/0.5.5
summary: |
  **问题**: <原问句>
  <2-3 句话摘要>
updated: <ISO 8601>
tags:
  - <6 轴 tag,至少含 maturity + docform>
links:
  - type: wikilink
    target: <path>
```

**正文 3 节 H2 骨架硬约束**(lint C15.1,逐字匹配):

```markdown
## 方案推演 / 架构分析

<替代 sources 的 ## 重点摘录;放分析过程与推理>

## 关联溯源

<替代 sources 的 ## 我的思考;放跨源关联>

> 引用: sources/a.md, concepts/standard/b.md, syntheses/topic.md

## 总结:最有收获的一句话

<一句话概括>
```

**禁止 H2**(lint FAIL):

- `## 重点摘录`(sources 风格)
- `## 我的思考`(sources 风格)
- `## 摘要` / `## Summary`(一律禁止)

**`## 关联溯源` 末尾 `> 引用:` 行**(lint C15.4 WARN):

- 逗号分隔路径集合
- 与 frontmatter `sources_used` 走 **Set 比对**(Q7 死循环防护)
- 不一致 → WARN(报告 diff),`--fix --apply` 自动补

**Q7 死循环防护**(v0.5.3 PATCH):写 analysis 页时,**不动** `updated` 字段(继承现状);保留原文件 mtime + atime(stat → write → utime 4 步流程在 scripts/validate-frontmatter.py 实现)。

#### 4.2 log.md 追加(G11 兼容)

走 `**Creation**` 前缀(便于路径 B grep):

```markdown
* **Creation**: query "<原问句>" → [analysis.md](analyses/<timestamp>-<slug>.md) by agent: producer/aeps-llm-wiki-plugin/0.5.5
```

#### 4.3 路径 B comparison 触发(v0.5.1 PATCH)

跳 4 探测到 `**Creation**: query "X vs Y"` 累计 ≥ 3 次,**额外**输出提示:

```
💡 X vs Y 这个对比已问过 N 次,要不要建一个常驻 comparison 页?
   (path: knowledge/comparisons/<a>-vs-<b>.md)
```

用户同意后落档为 comparison 页(design §3.4):

- 路径:`<project>/knowledge/comparisons/<a>-vs-<b>.md`(**不带时间戳,常驻**)
- frontmatter:`type: comparison` + `title` + `sources:`(≥ 2 条 wikilink,lint FAIL 若缺)+ `tags`
- 正文**自由发挥**(只 sources / analyses 锁骨架)
- log.md 追加 `**Creation**: comparison "<a> vs <b>" → ...`

#### 4.4 G11 旧骨架 detect(v0.4.0 → v0.5.0 升级)

query 阶段 detect 到落档 analysis 页含 `## 重点摘录` + `## 我的思考` 旧骨架 → **提示**:

```
💡 检测到 analyses/<file>.md 仍是 v0.4.0 旧骨架,请跑迁移脚本:
   python3 ./scripts/migrate-analysis-skeleton.py --from v0.4.0 --to v0.5.0
```

**不**自动改;留给用户拍板。

## 不应做

1. **不编造 wiki 里没有的内容**(AC-3 硬验收);wiki 未覆盖时显式声明"我读到的 wiki 里没有覆盖这点"。
2. **不无 gating 触发时每次都问"要不要落档"**(v0.4.0 以前的 over-prompting bug)。
3. **不让 intent=ambiguous 走触发路径**(v0.5.2 PATCH fallback;冲突时 ambiguous 优先于词命中)。
4. **不让 intent=exact 走触发路径**(纯事实查证不落档)。
5. **不让单源(<2 子目录)回答触发落档询问**。
6. **不让短答(<200 字)触发落档询问**。
7. **不让含 "Wiki 未覆盖" 字样的回答触发落档询问**。
8. **不在落档 analysis 页正文出现 `## 重点摘录` / `## 我的思考` / `## 摘要` / `## Summary` H2**(G11)。
9. **不在落档 analysis 页 frontmatter 缺 `sources_used`**(lint C15.2 FAIL)。
10. **不在落档 analysis 页 `## 关联溯源` 末尾缺 `> 引用:` 行**(C15.4 WARN)。
11. **不支持 `--no-save` 参数**(query 永远按 gating 规则决定;用户可自然 say no 跳过)。
12. **不让 query 输出末尾既无 `❓` 也无 `💡` 标记**(C15.3 FAIL)。
13. **不跳邻居深度 > 1**(避免雪崩;硬上限 `QUERY_NEIGHBOR_MAX = 8`)。
14. **不对 analysis 页 `updated` 字段或 mtime 做 `--fix` 重写**(Q7 死循环防护)。

## 输出格式

### 回答正文格式

```markdown
<直接回答用户问题,用 `[[wikilink]]` 引用 wiki 内页>

参考:[page A](sources/a.md) / [concept B](concepts/standard/b.md) / [synthesis C](syntheses/topic-c.md)

❓ 本次回答命中 ≥2 个 Wiki 源、深度 ≥200 字,符合 analysis 落档门槛。
   是否落档为 `knowledge/analyses/<timestamp>-<slug>.md`?[Y/n]
```

或:

```markdown
<直接回答>

💡 本次回答为单点查证 / 语义模糊 / 短答 / Wiki 未覆盖,跳过落档询问。
```

### 触发模板(任一条件命中)

```
❓ 本次回答命中 ≥2 个 Wiki 源、深度 ≥200 字,符合 analysis 落档门槛。
   是否落档为 `knowledge/analyses/<时间戳>-<slug>.md`?[Y/n]
```

### 不触发模板(任一条件命中)

```
💡 本次回答为单点查证 / 语义模糊 / 短答 / Wiki 未覆盖,跳过落档询问。
```

### 路径 B 触发模板

```
💡 X vs Y 这个对比已问过 N 次,要不要建一个常驻 comparison 页?
   (path: knowledge/comparisons/<a>-vs-<b>.md)
```

### G11 旧骨架 detect 模板

```
💡 检测到 analyses/<file>.md 仍是 v0.4.0 旧骨架,请跑迁移脚本:
   python3 ./scripts/migrate-analysis-skeleton.py --from v0.4.0 --to v0.5.0
```

### 引擎 fail 退出模板

```
❌ knowledge/ 页数 N ≥ QUERY_QMD_REQUIRED_THRESHOLD(1000),qmd 强依赖未装。
请先安装:npm install -g @tobilu/qmd
```

## 脚本调用汇总

| 阶段 | 脚本 | timeout | 备注 |
|---|---|---|---|
| 阶段 0 | `check-qmd.py --project-dir .` | 30000 | 引擎决策 |
| 阶段 2B | `qmd query "<q>" --collection knowledge --limit 20` | 60000 | qmd 模式 |
| 阶段 4(可选) | `validate-frontmatter.py --project-dir . --file knowledge/analyses/<file>.md` | 30000 | 写完校验 |
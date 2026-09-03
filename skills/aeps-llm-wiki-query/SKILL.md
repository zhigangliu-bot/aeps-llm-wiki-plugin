---
name: aeps-llm-wiki-query
description: 基于 knowledge/ 知识库回答用户问题。4 跳扫描(index 模式)或 qmd query(qmd 模式)。落档 gating 防止 over-prompting:intent=overview/comparison 或回答 ≥ 200 字 / ≥ 2 子目录源时问"是否存为 analysis";exact/ambiguous/短答/单源/未覆盖时跳过。
---

# aeps-llm-wiki-query

> **触发**:`/aeps-llm-wiki-query <question> [--project-dir <path>]`
> **权威设计**:`src/prd.md §4.3` + `src/design.md §4.3` + `§4.3.1 4 跳扫描` + `§4.3.2 落档 gating` + `§5.2` + `§5.3` + `src/scripts/DESIGN.md §1.1 query/`
> **对应实现阶段**:plugin v0.5.5 阶段 B(本文档) + 阶段 C(query/ 子目录 + 顶层 3 个 .py 全部落地)
> **关键 PATCH**:G11 analysis 专属骨架 + C15 gating 规则 + 路径 B comparison 累积触发 + v0.5.2 ambiguous fallback
> **核心原则**:LLM 只做思考(intent 推断 / gating 拍板 / 路径 B 判定)+ 调度;4 跳扫描 / gating / 落档 IO 全部交脚本(详见 `scripts/DESIGN.md §0.1`)

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

### 阶段 0:引擎决策(LLM 调 check-qmd.py)

```bash
python3 ./scripts/check-qmd.py --project-dir .
# Bash timeout: 30000
```

**返回 JSON**:

```json
{
  "pageCount": 123,
  "qmdAvailable": true,
  "qmdVersion": "1.2.3",
  "engine": "index|qmd|fail",
  "reason": "<引擎决策理由>"
}
```

**阈值常量**(硬编码在 `check-qmd.py` 内,与本 SKILL.md 一致):

```python
QUERY_CANDIDATE_K = 10
QUERY_NEIGHBOR_MAX = 8
QUERY_LOG_RECENT = 10
QUERY_INDEX_THRESHOLD = 500
QUERY_QMD_REQUIRED_THRESHOLD = 1000
```

**引擎决策矩阵**(LLM 读返回 `engine` 字段分支):

| N(页数) | qmd 状态 | engine | 行为 |
|---|---|---|---|
| N < 500 | 任意 | `index` | 走 §阶段 2A 4 跳扫描 |
| 500 ≤ N < 1000 | 已装 | `qmd` | 走 §阶段 2B qmd query |
| 500 ≤ N < 1000 | 未装 | `index` | 走 §阶段 2A 4 跳扫描 + 提示"推荐装 qmd" |
| N ≥ 1000 | 已装 | `qmd` | 走 §阶段 2B qmd query |
| N ≥ 1000 | 未装 | `fail` | **直接退出**,LLM 输出 |

`engine == "fail"` LLM 输出:

```
❌ knowledge/ 页数 N ≥ QUERY_QMD_REQUIRED_THRESHOLD(1000),qmd 强依赖未装。
请先安装:npm install -g @tobilu/qmd
```

### 阶段 1:Intent 路由(LLM 推断)

LLM 读 `<user-question>` 后推断 intent ∈ {`exact`, `ambiguous`, `overview`, `comparison`, `other`}。

| intent | 含义 | 示例 |
|---|---|---|
| `exact` | 单点查证 | "ISO 26262 ASIL D 等级是多少?" |
| `ambiguous` | 语义模糊,LLM 无法稳定分类 | "这篇芯片文档和上一篇有什么异同?" |
| `overview` | 跨领域综述 | "AUTOSAR 整体架构" |
| `comparison` | 对比 | "SOME/IP vs DDS" |
| `other` | 无法归入上述 | (兜底) |

LLM 自行推断,**不**调用脚本。

### 阶段 2A:index 4 跳扫描(engine == "index")

#### 跳 1:index.md 过滤(LLM 调 index-filter.py)

```bash
python3 ./scripts/query/index-filter.py \
  --project-dir . \
  --query "<user-question>" \
  --k 10
# Bash timeout: 30000
```

**返回 JSON**:

```json
{
  "candidates": [
    "sources/autosar-classic-overview.md",
    "concepts/standard/autosar.md",
    ...
  ]
}
```

**脚本职责**:读 `index.md` 全部条目,tags 命中加权,选 top-K(K = `QUERY_CANDIDATE_K = 10`)。

LLM 读 `candidates` 列表进入跳 2。

#### 跳 2:读强候选页(LLM 直接 Read)

LLM 用 Read 工具按优先级读每个候选页的 `description` / `summary` / `title` / 全文,选 ≤ K 个**最相关页**。

LLM **不**调脚本;这是 LLM 的语义判断环节。

#### 跳 3:`[[wikilink]]` 邻居(LLM 调 collect-neighbors.py)

```bash
python3 ./scripts/query/collect-neighbors.py \
  --project-dir . \
  --candidates /tmp/candidates.json \
  --max-depth 1 \
  --max-n 8
# Bash timeout: 30000
```

**`--candidates` 文件**(LLM 提前写):JSON 列表 `["sources/foo.md", "concepts/standard/bar.md", ...]`

**返回 JSON**:

```json
{
  "neighbors": [
    "syntheses/autosar-全景.md",
    "sources/iso26262-overview.md",
    ...
  ]
}
```

**脚本职责**:深度 1,硬上限 8 页;优先级降权读:

1. frontmatter `sources[]` 数组
2. `## 关联溯源` 末尾 `> 引用:` 行
3. `syntheses/*` 的 `## 子主题` + `## 引用` 段
4. 正文其他 `[[wikilink]]`(降权不忽略)

**硬上限** `QUERY_NEIGHBOR_MAX = 8`;**不**递归深度 > 1(避免雪崩)。

#### 跳 4:glossary + log + comparison 累积(LLM 直接 Read)

- LLM 直接 Read `glossary.md` 提供同义词消歧
- LLM 直接 Read `log.md` 最近 `QUERY_LOG_RECENT = 10` 条用于上下文
- **路径 B 探测**(LLM 调 path-b-detect.py):
  ```bash
  python3 ./scripts/query/path-b-detect.py \
    --project-dir . \
    --log knowledge/log.md \
    --x "SOME/IP" \
    --y "DDS"
  # Bash timeout: 30000
  ```
  **返回 JSON**:
  ```json
  {
    "hit_count": 4,
    "trigger": true
  }
  ```
  累计 ≥ 3 次 → **触发**路径 B 提示(见 §阶段 6)

LLM 自行 grep `**Creation**: ... query "X.*Y"` 模式时,统一调 `path-b-detect.py`;**不**直接 inline regex。

### 阶段 2B:qmd query(engine == "qmd")

LLM 直接调 `qmd` 命令:

```bash
qmd query "<question>" --collection knowledge --limit 20
# Bash timeout: 60000
# plugin 预设 --limit 20
```

拿 top-20 进入跳 2 / 跳 3(同上,LLM 直接 Read 候选页 + 调 `collect-neighbors.py`)。

### 阶段 3:Gating 决策(LLM 读 + 调 gating.py)

LLM 用 Read 工具读回答正文 + 推断的 intent + sources 分布后,调:

```bash
python3 ./scripts/query/gating.py \
  --intent "<exact|ambiguous|overview|comparison|other>" \
  --answer-length <N> \
  --sources-json /tmp/sources.json \
  --body /tmp/answer-body.md
# Bash timeout: 30000
```

**`--sources-json`**(LLM 提前写):按子目录归类的 sources,例如:

```json
{
  "sources/": ["autosar-classic-overview.md"],
  "concepts/standard/": ["autosar.md"],
  "syntheses/": ["autosar-全景.md"]
}
```

**`--body`**(LLM 提前写):回答正文 markdown 文件

**返回 JSON**:

```json
{
  "decision": "prompt|skip"
}
```

**决策规则**(脚本内部实现,LLM 信任返回):

```python
# 跳过条件(任一命中即 skip)
if intent in {"exact", "ambiguous"}: return "skip"
if "Wiki 未覆盖" in body: return "skip"
if answer_length < 200: return "skip"
if len(sources_by_subdir) < 2: return "skip"

# 触发条件(任一命中即 prompt)
if intent in {"overview", "comparison"}: return "prompt"
if answer_length >= 200: return "prompt"
if len(sources_by_subdir) >= 2: return "prompt"

# 兜底
return "skip"
```

**优先级澄清**:

- 跳过条件**优先于**触发条件(v0.5.2 PATCH ambiguous fallback)
- `intent == "ambiguous"` 即使其他条件触发,也走跳过(避免 LLM 误判被兜底绕过)
- `intent == "other"` 走触发路径(仅 ambiguous 走跳过)

LLM **不**自行伪代码判定;统一调 `gating.py` 拿 decision。

### 阶段 4:回答输出 + 末尾标记

LLM 组合回答正文,用 `[[wikilink]]` 引用 wiki 内页。

回答末尾必加标记(根据 gating decision):

- `decision == "prompt"` → `❓ 本次回答命中 ≥2 个 Wiki 源、深度 ≥200 字,符合 analysis 落档门槛。是否落档为 knowledge/analyses/<时间戳>-<slug>.md?[Y/n]`
- `decision == "skip"` → `💡 本次回答为单点查证 / 语义模糊 / 短答 / Wiki 未覆盖,跳过落档询问`

LLM 在 Claude 对话层**自然**问用户是否落档(`[Y/n]`),**不**让脚本读 stdin。

### 阶段 5:落档(用户同意后,LLM 调 generate-analysis-page.py)

用户输入 `[Y]` 后,LLM 准备 frontmatter + 正文文件,然后:

```bash
python3 ./scripts/generate-analysis-page.py \
  --project-dir . \
  --timestamp "<ISO 8601,冒号→连字符>" \
  --slug <slug> \
  --meta-json /tmp/analysis-meta.json \
  --body-file /tmp/analysis-body.md
# Bash timeout: 30000
```

**LLM 需提前准备**:

- `--timestamp`:`2026-09-01T14-30-00Z`(冒号 → 连字符,Windows 文件名安全)
- `--slug`:从 question 派生的 slug(小写 + 连字符,中文保留)
- `--meta-json`:必填 `type: analysis` / `title` / `answer_to`(原问句原样)/ `sources_used[]`(每条解析到真实存在的 `knowledge/**/*.md`)/ `generated_by: agent: producer/aeps-llm-wiki-plugin/0.5.5` / `updated` / `tags` / `summary`(首行 `**问题**: `)/ `links`
- `--body-file`:G11 3 H2 骨架正文(`## 方案推演 / 架构分析` / `## 关联溯源` + 末尾 `> 引用: sources/a.md, concepts/standard/b.md` / `## 总结:最有收获的一句话`)

**脚本职责**:

- 路径:`<project>/knowledge/analyses/<timestamp>-<slug>.md`
- frontmatter `sources_used` 校验(每条解析到真实存在路径,lint C15.2 FAIL 若缺失)
- 正文末尾 `> 引用:` 行 Set 比对(与 `sources_used`,C15.4 WARN)
- Q7 atomic_write_preserving_mtime(若文件已存在,atime + mtime 双还原,不动 `updated`)

#### 5.1 log.md 追加(LLM 调 append-log.py)

```bash
python3 ./scripts/append-log.py \
  --project-dir . \
  --action Creation \
  --source query "<原问句>" \
  --dest analyses/<timestamp>-<slug>.md \
  --actor "agent: producer/aeps-llm-wiki-plugin/0.5.5"
# Bash timeout: 30000
```

走 `**Creation**` 前缀(便于路径 B grep):

```markdown
* **Creation**: query "<原问句>" → [analysis.md](analyses/<timestamp>-<slug>.md) by agent: producer/aeps-llm-wiki-plugin/0.5.5
```

### 阶段 6:路径 B comparison 触发(v0.5.1 PATCH,LLM 调 path-b-detect.py)

§阶段 2A 跳 4 中 `path-b-detect.py` 返回 `trigger == true` 时,LLM 在回答外**额外**输出提示:

```
💡 X vs Y 这个对比已问过 N 次,要不要建一个常驻 comparison 页?
   (path: knowledge/comparisons/<a>-vs-<b>.md)
```

用户同意后 LLM 直接 Write `knowledge/comparisons/<a>-vs-<b>.md`(**不带时间戳,常驻**):

- frontmatter:`type: comparison` + `title` + `sources:`(≥ 2 条 wikilink,lint FAIL 若缺)+ `tags`
- 正文**自由发挥**(只 sources / analyses 锁骨架)
- log.md 追加(LLM 调 `append-log.py`):
  ```bash
  python3 ./scripts/append-log.py \
    --project-dir . \
    --action Creation \
    --source query comparison "<a> vs <b>" \
    --dest comparisons/<a>-vs-<b>.md \
    --actor "agent: producer/aeps-llm-wiki-plugin/0.5.5"
  ```

### 阶段 7:G11 旧骨架 detect(v0.4.0 → v0.5.0 升级,LLM 提示 + 建议调脚本)

LLM Read 分析页发现含 `## 重点摘录` + `## 我的思考` 旧骨架 → **提示** + 建议用户跑迁移脚本:

```
💡 检测到 analyses/<file>.md 仍是 v0.4.0 旧骨架,请跑迁移脚本:
   python3 ./scripts/migrate-analysis-skeleton.py --from v0.4.0 --to v0.5.0
```

**不**自动改;留给用户拍板。LLM **不**直接调 `migrate-analysis-skeleton.py`(用户拍板后再跑)。

### 阶段 8:末尾标记校验(LLM 调 lint-query-output.py)

回答输出后,LLM 调:

```bash
python3 ./scripts/lint-query-output.py --input /tmp/last-response.md
# Bash timeout: 30000
```

**返回 JSON**:

```json
{
  "ok": true,
  "marker": "prompt|skip|missing"
}
```

- `marker == "missing"` → LLM 补充 `❓` / `💡` 标记后重输出(C15.3 FAIL 防护)
- `marker == "prompt"` / `"skip"` → 通过

## 不应做

1. **不编造 wiki 里没有的内容**(AC-3 硬验收);wiki 未覆盖时显式声明"我读到的 wiki 里没有覆盖这点"。
2. **不无 gating 触发时每次都问"要不要落档"**(v0.4.0 以前的 over-prompting bug;LLM 必须先调 `gating.py`)。
3. **不让 intent=ambiguous 走触发路径**(v0.5.2 PATCH fallback;`gating.py` 内部 ambiguous 优先于词命中)。
4. **不让 intent=exact 走触发路径**(纯事实查证不落档)。
5. **不让单源(<2 子目录)回答触发落档询问**。
6. **不让短答(<200 字)触发落档询问**。
7. **不让含 "Wiki 未覆盖" 字样的回答触发落档询问**。
8. **LLM 不直接调 `qmd` 命令**(若 engine=qmd,LLM 直接调 `qmd query ...`;若 engine=index,LLM 走 index-filter.py)。
9. **LLM 不直接伪代码判定 gating**(统一调 `query/gating.py`)。
10. **LLM 不直接 inline regex 跑路径 B 探测**(统一调 `query/path-b-detect.py`)。
11. **LLM 不直接 atomic write knowledge/ 下任何文件**(统一调 `generate-analysis-page.py`)。
12. **不在落档 analysis 页正文出现 `## 重点摘录` / `## 我的思考` / `## 摘要` / `## Summary` H2**(G11)。
13. **不在落档 analysis 页 frontmatter 缺 `sources_used`**(lint C15.2 FAIL)。
14. **不在落档 analysis 页 `## 关联溯源` 末尾缺 `> 引用:` 行**(C15.4 WARN)。
15. **不支持 `--no-save` 参数**(query 永远按 gating 规则决定;用户可自然 say no 跳过)。
16. **不让 query 输出末尾既无 `❓` 也无 `💡` 标记**(C15.3 FAIL;LLM 必须调 `lint-query-output.py` 校验)。
17. **不跳邻居深度 > 1**(避免雪崩;硬上限 `QUERY_NEIGHBOR_MAX = 8`;`collect-neighbors.py --max-depth 1` 强制)。
18. **不对 analysis 页 `updated` 字段或 mtime 做 `--fix` 重写**(Q7 死循环防护)。

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
| 阶段 2A 跳 1 | `query/index-filter.py --query ... --k 10` | 30000 | 跳 1 top-K 过滤 |
| 阶段 2A 跳 3 | `query/collect-neighbors.py --candidates ... --max-depth 1 --max-n 8` | 30000 | 跳 3 邻居收集 |
| 阶段 2A 跳 4 | `query/path-b-detect.py --log ... --x ... --y ...` | 30000 | 路径 B 探测 |
| 阶段 2B | `qmd query "<q>" --collection knowledge --limit 20` | 60000 | qmd 模式 |
| 阶段 3 | `query/gating.py --intent ... --answer-length ... --sources-json ... --body ...` | 30000 | gating 决策 |
| 阶段 5 | `generate-analysis-page.py --timestamp ... --slug ... --meta-json ... --body-file ...` | 30000 | 落档 analysis |
| 阶段 5.1 | `append-log.py --action Creation --source ... --dest ...` | 30000 | log.md Creation 记录 |
| 阶段 8 | `lint-query-output.py --input <last-response>.md` | 30000 | C15.3 末尾标记校验 |

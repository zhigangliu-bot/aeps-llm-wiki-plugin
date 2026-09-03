---
name: aeps-llm-wiki-synthesize
description: 写 / 更新常驻综合页 knowledge/syntheses/<topic-slug>.md(不带时间戳)。聚合所有 entity/concept 页 + 引用它们的 source 页(LLM 决定边界)。重复触发同 topic → update 而非新建。
---

# aeps-llm-wiki-synthesize

> **触发**:`/aeps-llm-wiki-synthesize <topic> [--project-dir <path>]`
> **权威设计**:`src/prd.md §4.5` + `src/design.md §4.5` + `src/scripts/DESIGN.md §1.1 synthesize/`
> **对应实现阶段**:plugin v0.5.5 阶段 B(本文档) + 阶段 C(synthesize/ 子目录 4 个 .py 全部落地)
> **核心原则**:LLM 只做思考(topic 解析 / 正文撰写)+ 调度;slug 派生 / 探测存在 / 写页 / index 追加 / log 全部交脚本(详见 `scripts/DESIGN.md §0.1`)

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
- LLM 自行解析 topic 字符串,**不**调脚本

### 阶段 2:slug 派生(LLM 调 synthesize/make-slug.py)

```bash
python3 ./scripts/synthesize/make-slug.py --topic "OKF 生态全景"
# Bash timeout: 30000
```

**返回 JSON**:

```json
{
  "slug": "okf-生态全景"
}
```

**脚本职责**(纯字符串处理,无 IO):

- 全角 → 半角(FF01-FF5E → 21-7E;U+3000 → 半角空格)
- ASCII 标点 → 删
- CJK 标点 → 删
- 空格 → `-`
- ASCII 大写 → 小写
- 连续 `-` 折叠
- 收尾去 `-`
- NFKC 兜底
- 中文保留

**预期示例**(与脚本测试用例一致):

- `"OKF 生态全景"` → `okf-生态全景`
- `"AUTOSAR 实战方法论"` → `autosar-实战方法论`
- `"ISO 26262 与 SOTIF 的关系"` → `iso-26262-与-sotif-的关系`

### 阶段 3:探测是否已存在(LLM 调 synthesize/detect-existing.py)

```bash
python3 ./scripts/synthesize/detect-existing.py \
  --project-dir . \
  --slug <slug>
# Bash timeout: 30000
```

**返回 JSON**:

```json
{
  "exists": true,
  "current_sources_count": 7
}
```

或:

```json
{
  "exists": false,
  "current_sources_count": 0
}
```

**脚本职责**(只读,无写盘):

- 探测 `<project>/knowledge/syntheses/<slug>.md` 是否存在
- 从 frontmatter 解析 `sources_count`(int,默认 0)
- 不带 frontmatter schema 校验(留给 `validate-frontmatter.py`)
- `syntheses/` 目录不存在时 `exists=false`(不 mkdir,留给 build-page 路径)

LLM 读 `exists` 字段分支:

- `exists == true` → 走 **§阶段 4 update** 流程
- `exists == false` → 走 **§阶段 5 创建** 流程

### 阶段 4:update 流程(已存在,LLM 调 synthesize/build-page.py --update)

LLM 准备 frontmatter + 正文文件,然后调:

```bash
python3 ./scripts/synthesize/build-page.py \
  --project-dir . \
  --slug <slug> \
  --meta-json /tmp/synth-meta.json \
  --body-file /tmp/synth-body.md \
  --update
# Bash timeout: 30000
```

**LLM 需提前准备**:

- `--meta-json`:必填 `type: synthesis` / `title: <topic>` / `topic: <topic>` / `sources_count: <新 N>` / `tags` / `summary` / `generated`(脚本内部自动加 `last_updated: <ISO 8601 now>` + 保留原 `updated`)
- `--body-file`:正文(自由发挥)

**脚本职责**(UPDATE 流程):

- 路径:`<project>/knowledge/syntheses/<slug>.md`
- 读原文件 frontmatter `updated` 字段,**保留写入**(Q7 死循环防护:**不动** `updated`,只改 `last_updated` + `sources_count`)
- 二次写盘走 `atomic_write_preserving_mtime`(atime + mtime 双还原)
- frontmatter 其他字段(title / topic / tags / generated.by)在 UPDATE 流程**不动**
- log.md 内部自动 append-log.py 写 `**Update**: synthesized update on [<slug>](syntheses/<slug>.md) — sources_count now N`

**返回 JSON**:

```json
{
  "ok": true,
  "path": "knowledge/syntheses/<slug>.md",
  "created_or_updated": true
}
```

LLM **不**直接 Edit 文件;统一走 `build-page.py --update`。

### 阶段 5:创建流程(不存在,LLM 调 synthesize/build-page.py)

LLM 准备 frontmatter + 正文文件,然后调:

```bash
python3 ./scripts/synthesize/build-page.py \
  --project-dir . \
  --slug <slug> \
  --meta-json /tmp/synth-meta.json \
  --body-file /tmp/synth-body.md
# Bash timeout: 30000
```

**LLM 需提前准备**:

- `--meta-json`:必填 `type: synthesis` / `title: <topic>` / `topic: <topic>` / `sources_count: <N>` / `tags` / `summary` / `generated`(脚本内部自动加 `updated = last_updated = <ISO 8601 now>`)
- `--body-file`:正文(自由发挥)

**脚本职责**(CREATE 流程):

- 路径:`<project>/knowledge/syntheses/<slug>.md`(**不带时间戳,常驻**)
- `updated = last_updated = now`(脚本生成,覆盖 meta 传入值)
- 首次写盘走 `target.write_text()`(无 mtime 保留价值)
- log.md 内部自动 append-log.py 写 `**Creation**: synthesize "<topic>" → [<slug>](syntheses/<slug>.md)`

**返回 JSON**:

```json
{
  "ok": true,
  "path": "knowledge/syntheses/<slug>.md",
  "created_or_updated": true
}
```

**frontmatter 必填**(脚本内部固化):

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

#### 5.1 收集相关页(LLM 决定边界)

默认范围:**所有 entity/concept 页 + 引用它们的 source 页**。

筛选规则:

- 读 `index.md`,筛 frontmatter 含 topic tag 或被 tag 关联的页
- 读 entity/concept 页的 `aliases` / `description` / 关键词
- 读 source 页 frontmatter `tags` + `description`
- LLM 综合判断边界(允许扩张 / 收紧)

LLM **不**调脚本收集相关页;这是 LLM 的语义判断环节。

### 阶段 6:更新索引(LLM 调 synthesize/append-index.py)

```bash
python3 ./scripts/synthesize/append-index.py \
  --project-dir . \
  --slug <slug> \
  --sources-count <N> \
  --summary "<一句话>"
# Bash timeout: 30000
```

**返回 JSON**:

```json
{
  "appended": true,
  "already_present": false
}
```

**脚本职责**:

- append `<project>/knowledge/index.md` 一行 `- [<slug>](syntheses/<slug>.md) — type: synthesis · sources_count: <N> · <summary>`
- **幂等检测**:同 slug 重复 → `appended=false, already_present=true`,文件不改
- 行格式严格(em dash `—` + 中点 `·` 硬要求)
- frontmatter 之后插入(latest-first)

LLM **不**直接 Edit `index.md`;统一走 `append-index.py`。

### 阶段 7:sources_count 不足警告(LLM 拍板)

`detect-existing.py` 返回 `current_sources_count < 3` 时,LLM 输出警告 + 拍板门:

```
💡 topic "<topic>" 当前仅聚合 N(< 3) 页相关资料,sources_count 不足。
建议:
1. 先跑 /aeps-llm-wiki-ingest 把更多资料丢进 inbox
2. 或缩小 topic 范围,聚焦某子主题
是否继续创建(sources_count 留 N)?[y/n]
```

用户拍板 `[y]` 后继续 §阶段 4 / 5;`[n]` → 退出。

**该警告由 LLM 触发**,**不**在脚本内部 hard fail(design §3.7 + SKILL.md 拍板门)。

## 不应做

1. **不写一次性"当时综合"**(那是 `analysis` → `analyses/<时间戳>-<slug>.md`,**不是** `synthesis`)。
2. **不带时间戳**(`syntheses/<topic-slug>.md`,**不带时间戳,常驻**,后续 LLM 可 update)。
3. **不写 `sources_count < 3` 的合成页**(lint 警告空综合;若确实资料不足,提示用户先 `/aeps-llm-wiki-ingest`;由 LLM 拍板门确认)。
4. **不写正文 `## 摘要` / `## Summary` H2**(沿用 §3.1 §C 纪律)。
5. **不强制 3 节骨架**(entities / concepts / comparison / synthesis 正文**自由发挥**,只有 sources / analyses 锁骨架)。
6. **不覆盖已存在的 synthesis 页内容**(synthesis 是常驻,update 而非 overwrite;走 §阶段 4 update 流程)。
7. **不在 frontmatter `updated` 字段做不必要的改写**(对齐 Q7 死循环防护业务意图,UPDATE 流程仅改 `last_updated`;由 `build-page.py` 内部强制)。
8. **LLM 不直接 atomic write `<project>/knowledge/syntheses/*.md`**(统一 `synthesize/build-page.py`)。
9. **LLM 不直接 Edit `<project>/knowledge/index.md`**(统一 `synthesize/append-index.py`)。
10. **LLM 不直接调 `append-log.py`**(由 `build-page.py` 内部自动调;LLM 不重复写 log)。
11. **LLM 不直接 inline regex 派生 slug**(统一 `synthesize/make-slug.py`)。
12. **LLM 不直接探路 `<project>/knowledge/syntheses/<slug>.md` 是否存在**(统一 `synthesize/detect-existing.py`)。
13. **不创建 `<project>/syntheses/` 目录**(固定路径是 `<project>/knowledge/syntheses/`)。
14. **不在 user-project 写 plugin 本体路径或绝对路径**(对齐 NFR-4)。
15. **LLM 不调用 convert-to-md.py / safe-mv.py 等写操作脚本**(synthesize 只调 `synthesize/*` 4 个 + 必要时的 `append-log.py` — 后者由 `build-page.py` 内部调)。

## 输出格式

### 创建完成

```markdown
✅ 已创建常驻综合页:knowledge/syntheses/<topic-slug>.md
- topic: <原始 topic>
- sources_count: <N> 页
- 引用页列表(摘):
  - [page 1](<path>)
  - [page 2](<path>)
- log.md: append 1 条 **Creation**(由 build-page.py 自动写)
- index.md: append 1 条(由 append-index.py 写)
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
- log.md: append 1 条 **Update**(由 build-page.py 自动写)
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

## 脚本调用汇总

| 阶段 | 脚本 | timeout | 备注 |
|---|---|---|---|
| 阶段 2 | `synthesize/make-slug.py --topic "<topic>"` | 30000 | slug 派生 |
| 阶段 3 | `synthesize/detect-existing.py --project-dir . --slug <slug>` | 30000 | 探测是否已存在 + 读 sources_count |
| 阶段 4(UPDATE) | `synthesize/build-page.py --slug <slug> --meta-json ... --body-file ... --update` | 30000 | 写/更新 synthesis 页(UPDATE 流程) |
| 阶段 5(CREATE) | `synthesize/build-page.py --slug <slug> --meta-json ... --body-file ...` | 30000 | 写 synthesis 页(CREATE 流程) |
| 阶段 6 | `synthesize/append-index.py --slug <slug> --sources-count N --summary "..."` | 30000 | append index.md 一行(幂等) |

**LLM 不直接调** `append-log.py`(由 `build-page.py` 内部自动调)。

## 与 analysis / comparison 的边界

| 类型 | 路径 | 时间戳 | 触发 | 锁骨架 |
|---|---|---|---|---|
| **source** | `knowledge/sources/<basename>.md` | 不带 | ingest | 3 H2(`## 重点摘录` / `## 我的思考` / `## 总结`) |
| **entity** | `knowledge/entities/<子类>/<slug>.md` | 不带 | ingest 抽取 | 自由发挥 |
| **concept** | `knowledge/concepts/<子类>/<slug>.md` | 不带 | ingest 抽取 | 自由发挥 |
| **analysis** | `knowledge/analyses/<timestamp>-<slug>.md` | **带** | query 落档(用户同意) | 3 H2 G11(`## 方案推演` / `## 关联溯源` / `## 总结`) |
| **comparison** | `knowledge/comparisons/<a>-vs-<b>.md` | 不带 | ingest 路径 A / query 路径 B / 路径 C | 自由发挥 |
| **synthesis** | `knowledge/syntheses/<topic-slug>.md` | 不带 | synthesize | **自由发挥**(唯一不锁骨架的"知识页") |

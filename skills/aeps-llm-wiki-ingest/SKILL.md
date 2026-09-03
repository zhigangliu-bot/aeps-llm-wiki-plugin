---
name: aeps-llm-wiki-ingest
description: 把 inbox/ 里的资料转 md、抽 entity / concept / source,经拍板门后迁到 raw/ + 写入 knowledge/。三阶段并发模型(N ≥ 2):batch IO → LLM 并行(≤ 5 subagent,只写 proposal JSON)→ 主 agent 串行 9 步合并。N = 1 跳过阶段 2。
---

# aeps-llm-wiki-ingest

> **触发**:`/aeps-llm-wiki-ingest [--raw-subdir=<已存在 15 类>] [--project-dir <path>]`
> **权威设计**:`src/prd.md §4.2` + `src/design.md §4.2` + `§4.2.1 三阶段并发` + `§5.1` + `§5.4`
> **对应实现阶段**:plugin v0.5.5 阶段 B(本文档) + 阶段 C(scripts 落地)
> **关键 PATCH**:G10 派生文件副本 / Q5 命名飘前移 / Q11 subagent 写权矩阵 / Q7 死循环防护 / v0.5.2 atomic overwrite / v0.5.4 proposal JSON 强校验 + 损坏降级

## 必读文件

启动 skill 时,**先 Read**:

| 优先级 | 路径 | 用途 |
|---|---|---|
| 1 | `<project>/knowledge/SCHEMA.md` | **用户本机**操作手册(必读,**不是** plugin 本体版本) |
| 2 | `<project>/raw/README.md` | **用户本机**15 类字典 |
| 3 | `<project>/templates/concept-entities-readme.md` | **用户本机**子类 ↔ 目录绑死字典 |
| 4 | `<project>/templates/tag-template.md` | **用户本机**六轴 tag 词表 |
| 5 | `aeps-llm-wiki-plugin/src/templates/source-page.md` | sources/ 页生成模板 |
| 6 | `aeps-llm-wiki-plugin/src/scripts/README.md` | scripts/ 约定(proposal-apply 两阶段 / 无交互 / 无 daemon) |
| 7 | `aeps-llm-wiki-plugin/src/scripts/requirements.txt` | 强依赖(anydoc / paddleocr / jsonschema / pyyaml) |
| 8 | `aeps-llm-wiki-plugin/src/schema/proposal.schema.yaml`(若已落地) | proposal JSON 强校验 |

## 工作流(4 阶段)

### 阶段 0:依赖预检(必跑)

```bash
python3 -c "import anydoc, paddleocr, jsonschema, yaml" 2>&1
```

- 全部 import 成功 → 进入阶段 1
- 任一 ImportError → **提示并退出**:
  ```
  ❌ 依赖未装: <pkg>
  请先跑: pip install -r scripts/requirements.txt
  ```
- **不进入任何后续阶段**

### 阶段 1:扫描 + 入口决策(主 agent)

1. **递归**遍历 `<project>/inbox/`(含子目录),统计 N。
2. inbox 为空 → 输出提示语,退出码 0:
   ```
   inbox/ 为空,先把资料丢进 inbox 再跑。
   ```
3. N = 1 → 走 **§阶段 1A 单文件**。
4. N ≥ 2 → 走 **§阶段 1B 批量**。
5. 检查 `<project>/raw/.aeps-plugin-version` 是否存在;不存在 → 提示用户先跑 `/aeps-llm-wiki-init`。

#### 阶段 1A:单文件入口

```bash
python3 ./scripts/convert-to-md.py \
  --project-dir . \
  --input inbox/<file> \
  --output temp/<basename>.md
# Bash timeout: 60000(单文件 60s 足够)
```

文件分派规则(本 agent 内联判定):

- `.md` / `.txt` / `.csv` / `.json` / `.yaml` / `.yml` / `.xml` / `.html` / `.htm` / `.rst` → **直接读**(native_text: true),不调 convert-to-md.py
- `.pptx` / `.docx` / `.xlsx` / `.pdf` → 调 convert-to-md.py;Claude converter 失败则降级 anydoc
- `.png` / `.jpg` / `.jpeg` / `.bmp` / `.tiff` → convert-to-md.py(paddleocr)
- 其他 / 失败 → **FAIL**:无法转换 `<file>`,请手动预处理。

#### 阶段 1B:批量入口(N ≥ 2,**显式 Bash timeout 600000ms**)

```bash
python3 ./scripts/convert-to-md.py \
  --project-dir . \
  --batch inbox/<f1> inbox/<f2> ... inbox/<fn> \
  --output-dir temp/ \
  --emit-to temp/
# Bash timeout: 600000ms(Claude Code max;paddleocr 冷启动 5-30s + N 文件 OCR ≈ N×1-3s)
```

**关键约束**:批量入口保证 **paddleocr Engine 只加载 1 次**(避免 N 次冷启动叠加)。

`--emit-to temp/` 让 pptx/docx/xlsx/pdf 在 `temp/<basename>.md` 之外,**同时**产出 `temp/<basename>.<ext>.converted.md`(G10 双产物落盘)。纯文本文件 `.md`/`.txt`/... **不** 生成 `.converted.md` 副本。

### 阶段 2:LLM 并行(N ≥ 2 时走;N = 1 跳过)

**仅在 N ≥ 2 时执行**;**严禁**在 N = 1 时调用,避免派发开销。

#### 派发规则

- 主 agent 切 ≤ 5 批(每批 N/5 份文件,**不**超过 5 个 subagent)
- 用 Claude Code Task 工具派 subagent,**每个独立 LLM 上下文**

#### subagent prompt 硬约束(Q11 写权矩阵)

每个 subagent **只能**写 `temp/proposal-<doc-id>.json`,**严禁**写以下路径:

```
knowledge/**/*         # 任意子目录(sources / entities / concepts / analyses / comparisons / syntheses / index.md / glossary.md / log.md / overview.md / SCHEMA.md)
raw/**/*.md           # raw 子目录任何文件
scripts/_meta.json    # plugin 元数据
```

subagent **严禁**调用:

- `convert-to-md.py`(零 paddleocr 调用,冷启动已在阶段 1 batch 进程内完成)
- `safe-mv.py` / `ensure-dirs.py` / `append-log.py` / `validate-frontmatter.py` / `validate-proposal.py`(任何写操作脚本)

subagent **可**读取:

- `temp/<basename>.md`(阶段 1 产物)
- `temp/<basename>.<ext>.converted.md`(G10 转换副本)
- `<project>/knowledge/SCHEMA.md` / `<project>/raw/README.md` / `<project>/templates/concept-entities-readme.md` / `<project>/templates/tag-template.md`
- `aeps-llm-wiki-plugin/src/schema/proposal.schema.yaml`(若已落地)

#### proposal JSON 必填 8 字段(v0.5.4 PATCH)

```json
{
  "file": "inbox/<basename>.<ext>",
  "suggested_subdir": "raw/<15 类字典之一>",
  "raw_category": "<01_EE架构|02_芯片|...|15_算法>",
  "format": "<md|txt|csv|json|yaml|xml|html|htm|rst|pptx|docx|xlsx|pdf|png|jpg|jpeg|bmp|tiff>",
  "converter": "<anydoc|claude-native|paddleocr|null>",
  "native_text": <bool>,
  "converted_path": "<raw/<subdir>/<file>.converted.md 或 null>",
  "concepts": [{"name": "...", "type": "<entities|concepts>", "subtype": "<子类>", "aliases": ["..."]}, ...]
}
```

subagent 还要写 **`_meta`** 元数据:

```json
"_meta": {
  "doc_id": "<basename>-<sha256 前 8 位>",
  "schema_version": "1.0",
  "extracted_at": "<ISO 8601>",
  "extracted_by": "agent: producer/aeps-llm-wiki-plugin/0.5.5"
}
```

### 阶段 3:主 agent 串行 9 步合并

**所有 9 步在主 agent 上下文串行执行,无并发写冲突**。

#### step 1:命名飘仲裁(Q5 前移自 lint)

对每个 `proposal.suggested_subdir` 与 `<project>/raw/` 已有子目录做相似度比较:

- **Levenshtein 距离 ≤ 2** 或 **全小写 + `-` 归一后相同** → **强制改用已有目录**(LLM 命名飘检测)
- 命中已有目录 → 直接用,无需拍板
- 未命中 + 与 raw-readme 15 类中某类匹配 → 拍板门(已存在目录免拍板)
- 未命中 + 不在 15 类 → **必须拍板**,新目录创建需用户同意

#### step 2:拍板门汇总

把所有需要拍板的决策合成一次对话提问(LLM 在对话层发起,**不**让脚本读 stdin):

```
❓ 建议把 [file.pdf](inbox/file.pdf) 迁到 [raw/06_功能安全/](raw/06_功能安全/),
   理由:ISO 26262 标准文件。是否同意?[y/n/改建议]

❓ 检测到 raw/02_芯片/<file> 已存在,是否覆盖?[y 覆盖 / n 跳过 / d 仅删旧副本]
```

**用户回复格式**:

- `[y]` / `[Y]` → 同意,**继续**
- `[n]` / `[N]` → 跳过该文件,**继续**其他文件
- `[d]` → 仅删旧副本,不写入新内容(v0.5.2 PATCH 重 ingest)

汇总后写 `temp/decision-<hash>.json`,**用户拍板后**才调 `safe-mv.py --apply`。

**decision JSON 模板**:

```json
{
  "type": "ingest_decision",
  "schema_version": "1.0",
  "decided_at": "<ISO 8601>",
  "actor": "human:<id>",
  "proposal_refs": ["temp/proposal-<doc-id>.json", ...],
  "actions": [
    {
      "op": "mv|overwrite|skip|delete-only",
      "source": "inbox/<file>",
      "dest": "raw/<subdir>/<file>"
    }
  ]
}
```

`op` 枚举仅 4 种:`mv` / `overwrite` / `skip` / `delete-only`。

#### step 3:concept 去重(跨 proposal 按 aliases 合并)

聚合所有 proposal.concepts:

- 同 `name`(aliases 累加)+ 不重复建页
- 跨 subagent 抽到同名 entity / concept(如 subagent A 抽 "ISO 26262" + subagent B 抽 "ISO26262")→ **合并到 1 页**,aliases 累加

#### step 4:entity 去重(按 name + aliases 合并)

同 step 3,聚合所有 entity 抽取。

#### step 5:proposal JSON 5 步校验 + 字符清洗 + 截断检测(v0.5.4 PATCH)

对每个 proposal 跑 5 步:

1. **JSON 解析**:`json.load()` 失败 → `JSONDecodeError` 抛出
2. **schema 校验**:`jsonschema.validate()` 失败 → `ValidationError` 抛出
3. **字符集清洗**:BOM 保留;`\x00` NUL / `\x1f` 单元分隔符 → strip;`</script>` 注入字面量 → 替换为 `<\/script>`
4. **截断检测**:`concepts` 数组 ≤ 200 条(超过视为 LLM 输出截断)
5. **重写清洗后 JSON**:写入 `temp/<doc-id>-proposal.json.sanitized`

**失败降级路径**:

- **JSONDecodeError / ValidationError / maxItems 超限** → **不派 subagent 重试**(避免同样模式),**主 agent 单线程**重跑该文件(走 §阶段 1A 单文件分支)
- **重试限额 1 次**(防 token 耗尽)
- **重跑仍失败** → 标记跳过 + 写 **`**IngestFailure**`** log 段(在原 9 步串行清单之外)
- **其他正常 proposal 继续合并**——**不阻断整批 ingest**
- 损坏文件 inbox 原文件**保留**(后续用户手动重 ingest)
- 损坏 proposal 备份到 `temp/<doc-id>-proposal.json.corrupt.bak`(供用户人工排查)

#### step 6:safe-mv.py --apply(G10 双文件迁移 + atomic overwrite)

```bash
python3 ./scripts/safe-mv.py \
  --project-dir . \
  --apply temp/decision-<hash>.json
```

**G10 双文件迁移**(适用 `native_text: false` 的 pptx/docx/xlsx/pdf):

- 同时迁移原文件 + `.converted.md` 副本到 `raw/<subdir>/`
- inbox 原文件 + temp 副本**同步删除**

**v0.5.2 PATCH atomic overwrite**(拍板 `[y]`):

- **先备份**到 `temp/raw_backup_<hash>/<basename>.<ext>` + `<basename>.<ext>.converted.md`
- `os.replace()` **atomic 替换**两文件
- 中途任何一步失败 → 两文件均保持旧值
- 同 subdir 内无关文件 mtime / 内容不变

**拍板 `[d]`(仅删旧副本)**:

- 仅删除 `raw/<subdir>/<basename>.<ext>` + `<basename>.<ext>.converted.md`
- inbox 原文件保留(等用户手动处理)

#### step 7:写 source 页(每个 inbox 文件 1 页)

路径:`<project>/knowledge/sources/<basename>.md`

frontmatter 必填 8+1 字段:

```yaml
type: source
title: <文档标题>
description: <一句话描述>
source_file: raw/<subdir>/<basename>.<ext>           # Obsidian UI 可点
sources:
  - id: <basename>
    resource: raw/<subdir>/<basename>.<ext>            # OKF §5.1 机器读
    title: <文档标题>
    author: <author>
    last_modified: <ISO 8601 或 null>
format: <md|txt|...|tiff>
converter: <anydoc|claude-native|paddleocr|null>
native_text: <bool>
converted_path: <raw/<subdir>/<basename>.<ext>.converted.md 或 null>
generated:
  by: agent: producer/aeps-llm-wiki-plugin/0.5.5
  at: <ISO 8601>
verified:
  - { by: human:<id>, at: <ISO 8601> }
status: stable
tags:
  - <6 轴 tag,至少含 maturity + docform>
updated: <ISO 8601>
summary: |
  <1-3 句话摘要>
links:
  - type: wikilink
    target: <basename>.<ext>.converted 或 basenme>     # 纯文本不带 .converted 后缀
```

**Q9 双字段同源断言**:`source_file` 与 `sources[0].resource` 值必须相等(Q9 硬验收,C5.1 lint FAIL)。

**G10 links 镜像**:正文末尾加一行 `> 原始来源:[[<basename>.<ext>.converted]]` 或 `[[<basename>]]`(纯文本);frontmatter `links:` 与该 wikilink 走 Set 比对(Q7 死循环防护)。

**正文 3 节 H2 骨架硬约束**(lint C15.1 + 旧版 sources 规则):

```markdown
## 重点摘录

<文档核心内容摘录>

## 我的思考

<阅读时的思考与关联>

## 总结:最有收获的一句话

<一句话概括>
```

**禁止** H2:

- `## 摘要` / `## Summary`(违规 FAIL)
- `## 方案推演 / 架构分析` / `## 关联溯源`(这是 analyses/ 专属,G11)

#### step 8:写 entity / concept 子页

按 step 3-4 去重后的清单,逐个写:

- entity → `<project>/knowledge/entities/<子类>/<slug>.md`(子类 ∈ {person, organization, project, product, event, place, other})
- concept → `<project>/knowledge/concepts/<子类>/<slug>.md`(子类 ∈ {theory, method, field, phenomenon, standard, term, other})

frontmatter:

```yaml
type: entity|concept
title: <名称>
description: <一句话>
aliases: [<别名 1>, <别名 2>]
summary: |
  <简介>
tags:
  - <6 轴 tag>
updated: <ISO 8601>
links: []
generated:
  by: agent: producer/aeps-llm-wiki-plugin/0.5.5
```

**子类 ↔ 目录 1:1 绑死**(concept-entities-readme 字典权威),**不可跨目录**。

正文**自由发挥**(只 sources / analyses 锁骨架)。

#### step 9:更新全局索引(收尾一次性)

**只在此阶段做一次**,**严禁**在 step 7 / 8 边写边更新(并发写冲突)。

- `<project>/knowledge/log.md`:append 段 `## <YYYY-MM-DD>` + N 条 `**Migration**` / `**Converted**`(G10 适用)
- `<project>/knowledge/glossary.md`:append 新增的 entity / concept 名
- `<project>/knowledge/index.md`:整体重写(列出所有新增 source / entity / concept 路径)
- `<project>/knowledge/overview.md`:按需更新(LLM 决定是否新增主题脉络)

### 阶段 4:收尾

- 删 `temp/<basename>.md` / `temp/<basename>.<ext>.converted.md` / `temp/<doc-id>-proposal.json`(默认 `--cleanup`)
- 保留 `temp/<doc-id>-proposal.json.sanitized`(供用户复查)
- 损坏备份 `temp/<doc-id>-proposal.json.corrupt.bak` 保留
- G10 备份 `temp/raw_backup_<hash>/` 保留(用户可手动回滚)

## 不应做

1. **不扫 raw/**(G7 不可变层);调整归档走 `git mv` 或手工。
2. **不未经用户拍板就创建新 raw 子目录**(创建新目录必须拍板;已存在目录免拍板)。
3. **不为纯文本文件**(`.md`/`.txt`/`.json`/...)**生成 `.converted.md` 副本**(`native_text: true`)。
4. **不原地覆盖已有 `.converted.md`**(G7 + Q5);用户需重转时把原文件 `cp` 回 inbox/ 走标准 ingest。
5. **不新增"重转 skill"**(v0.5.2 PATCH 拍板)。
6. **不在 raw/ 下生成 `_converted/` 子目录**(保持 raw 子目录语义单一)。
7. **不让 subagent 写 knowledge/ 下任何文件**(Q11 写权矩阵)。
8. **不让 subagent 调 safe-mv.py / ensure-dirs.py / append-log.py 等写操作脚本**。
9. **不让 subagent 调 convert-to-md.py**(零 paddleocr 调用,冷启动已在阶段 1 batch 进程内完成)。
10. **不在 SKILL.md 里出现"裸目录名参数"`--raw-dir custom-raw` 等**(6 顶层目录名硬编码)。
11. **不为 source 页生成包含 `## 摘要` / `## Summary` H2 的正文**(lint FAIL)。
12. **不在 source 页 frontmatter `updated` 字段上动 safe-mv.py 重写**(Q7 死循环防护)。
13. **不用 `Path.write_text` 默认行为**(必须 stat → write → utime 4 步流程,v0.5.3 PATCH)。但 SKILL.md 不直接写盘,此约束在 scripts 实现层强制。
14. **不让 proposal JSON 损坏文件整体 raise 中断整批**(v0.5.4 PATCH:按文件粒度降级,主 agent 单线程重跑 ≤ 1 次)。
15. **不为 `comparisons/*.md` 缺 `sources:` 字段放过 lint**(C4 FAIL)。

## 输出格式

### log.md 追加模板(收尾时一次性 append)

**首次 ingest**:

```markdown
## <YYYY-MM-DD>
* **Migration**: [file.md](inbox/file.md) → [file.md](../raw/02_芯片/file.md)
* **Converted**: raw/02_芯片/file.pdf.converted.md (via anydoc)
* **Creation**: [s32g.md](entities/product/s32g.md) by agent: producer/aeps-llm-wiki-plugin/0.5.5
* **Creation**: [autosar.md](concepts/standard/autosar.md) by agent: producer/aeps-llm-wiki-plugin/0.5.5
```

**G10 v0.5.2 PATCH 重 ingest(拍板 `[y]`)**:

```markdown
* **Migration**(overwrite): inbox/file.pdf → raw/02_芯片/file.pdf
* **Converted**(overwrite): raw/02_芯片/file.pdf.converted.md (via anydoc)
* **Backup**: temp/raw_backup_<hash>/file.pdf
```

**v0.5.4 PATCH 损坏降级**:

```markdown
* **IngestFailure**: temp/<doc-id>-proposal.json — JSONDecodeError: Expecting ',' delimiter
```

(`**IngestFailure**` 是 5 种前缀之外的新段,plugin v0.5.4 引入)

### 拍板门提示语模板

**新目录创建**:

```
❓ 建议把 [file.pdf](inbox/file.pdf) 迁到 [raw/12_法规_标准_政策/](raw/12_法规_标准_政策/),
   理由:V2X 标准文件。是否同意?[y/n/改建议]
```

**G10 v0.5.2 重 ingest**:

```
❓ 检测到 raw/02_芯片/file.pdf 已存在,是否覆盖?[y 覆盖 / n 跳过 / d 仅删旧副本]
```

### 命名飘强制合并提示

```
💡 检测到 LLM 提议 raw/03_芯片_v2/(Levenshtein 距离 1,与已有 raw/02_芯片/ 高度相似)
   强制改用 raw/02_芯片/,不创建新目录。
```

## 脚本调用汇总

| 阶段 | 脚本 | timeout | 备注 |
|---|---|---|---|
| 阶段 0 | (内置 `python3 -c "import ..."`) | 30000 | 依赖预检 |
| 阶段 1A | `convert-to-md.py --input ... --output ...` | 60000 | 单文件 |
| 阶段 1B | `convert-to-md.py --batch ... --output-dir temp/ --emit-to temp/` | **600000** | N ≥ 2 批量,**必须**显式 timeout |
| 阶段 3 step 6 | `safe-mv.py --apply temp/decision-<hash>.json` | 60000 | 拍板应用 |

辅助脚本(可选,阶段 C 落地后启用):

- `ensure-dirs.py --project-dir . --path "raw/<subdir>"`(拍板创建子目录)
- `append-log.py --project-dir . --action Migration --source inbox/<f> --dest raw/<sub>/<f>`
- `validate-frontmatter.py --project-dir . --file knowledge/sources/<basename>.md`
- `validate-proposal.py --input temp/<doc-id>-proposal.json`(v0.5.4 PATCH schema 强校验)

## 子命令

`--raw-subdir=<已存在 15 类>`(可选,prd §4.2 AC-7):

- 仅 inbox 非空时生效
- 跳过分类交互,**直接**走 `mv inbox/<file> → raw/<name>/<file>`
- 不在 init 预建 15 类时 → **WARN**"自定义目录,需要拍板门确认"
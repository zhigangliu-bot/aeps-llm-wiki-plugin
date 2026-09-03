# scripts/ 设计文档

> **来源**:`src/prd.md` + `src/design.md` + `src/implement.md` 阶段 C 测试清单
> **状态**:v0.5.5(2026-09-03,与 plugin.json version 一致);阶段 B 5 份 SKILL.md 已 commit 78e6a41;本设计文档落地阶段 C .py 实现前的架构契约
> **定位**:`scripts/` 子系统的**软件架构设计文档**(CLAUDE.md "写代码之前必须要写软件架构设计文档"硬约束)
> **读者**:plugin 维护者 + 阶段 C .py 实现者 + tests/ 测试用例编写者

---

## 0. 设计意图

### 0.1 SKILL.md ↔ scripts/ 边界(本设计的核心原则)

**用户拍板**(2026-09-03):

> "其实我希望 skill 做一些思考和调度的事情,具体的操作尽量使用脚本"

**原则**:

| 层 | 职责 | 不应做 |
|---|---|---|
| **SKILL.md**(Claude 对话层) | 思考 + 调度 + 决策:拍板门 / 命名飘 / 矛盾 / 漏链 / 陈旧 / intent 推断 / sources_count 不足警告 | 直接拷文件 / 写 frontmatter / 写源页 / 写 entity/concept / 落档 analysis / 写 log.md |
| **scripts/*.py**(Python 实现层) | 机械执行 IO + schema 校验 + 字符清洗 + atomic write + 安全锁 | 用户交互 / 阻塞 loop / stdin 读取 / daemon 监听 |

### 0.2 与 scripts/README.md 的关系

`scripts/README.md` 已固化"无 daemon / 无 stdin / proposal-apply 两阶段"硬契约 + 未来脚本候选清单。本文档是 README 的**架构细化**(模块边界 + 数据契约 + PATCH 映射 + 测试对齐)。

---

## 1. scripts/ 模块边界(22 个 .py + 2 个数据文件 + 1 个测试)

### 1.1 文件总览

| .py | 触发 skill | 主要职责 | 输入 | 输出 |
|---|---|---|---|---|
| **`init-vault.py`** | init | 6 顶层 + raw 15 + knowledge 18 + temp/ + .gitkeep + .gitignore + 拷 templates/scripts + 写 _meta.json + 写 .aeps-plugin-version + 写 4 个种子文件 + 字典 append 同步 | `--project-dir [--re-run]` | `{created, copied, synced_at, plugin_version}` |
| **`check-deps.py`** | ingest | 跑前 import anydoc / paddleocr / jsonschema / yaml;任意 ImportError → FAIL | (无) | `{ok, missing: list}` |
| **`convert-to-md.py`** | ingest | 扩展名分流(扩展名 → native / claude-native / anydoc / paddleocr);支持 `--batch` 共享单 Engine 实例;支持 `--emit-to` 写 `.converted.md` 副本(G10) | `--project-dir --input / --batch ... --output-dir --emit-to` | 单文件:md 文本;批量:`temp/<basename>.md` + (G10)`temp/<basename>.<ext>.converted.md` |
| **`safe-mv.py`** | ingest | 读 `temp/decision-<hash>.json`,执行 mv / atomic overwrite / G10 双文件迁移;`op ∈ {mv, overwrite, skip, delete-only}`;先备份到 `temp/raw_backup_<hash>/` | `--project-dir --apply temp/decision-<hash>.json` | `{moved: list, backed_up: list, atomic: bool, errors}` |
| **`ensure-dirs.py`** | ingest | `mkdir -p raw/<subdir>`(二级路径 / 新建自定义目录) | `--project-dir --path "raw/<subdir>"` | `{created: bool, path}` |
| **`append-log.py`** | 所有 skill | 写 `log.md` 一条记录(6 种前缀:`**Creation/Update/Deprecation/Migration/LintFix/IngestFailure**`;最新在前) | `--project-dir --action <prefix> --source --dest --actor` | `{appended: bool, line}` |
| **`validate-frontmatter.py`** | lint / ingest / query / synthesize | 按 `schema/frontmatter.schema.yaml` jsonschema 校验字段;6 轴 tag 校验;maturity / docform 必填;unknown type WARN(OKF §11);G10 三元组强绑定(native_text ↔ converter ↔ converted_path) | `--project-dir --file <path>` | `{ok, missing, typecast, unknown_keys}` |
| **`validate-proposal.py`** | ingest | proposal JSON 5 步校验 + 字符清洗 + 截断检测(v0.5.4 PATCH);BOM 保留 / `\x00` strip / `</script>` → `&lt;\/script&gt;`;concepts ≤ 200;失败降级 backup `.corrupt.bak` | `--input temp/<doc-id>-proposal.json` | `{ok, sanitized_path: temp/<doc-id>-proposal.json.sanitized, errors}` |
| **`generate-source-page.py`** | ingest | 写 `knowledge/sources/<basename>.md` frontmatter + 3 H2 骨架;G10 增字段(format / converter / native_text / converted_path / links 镜像);`source_file` ↔ `sources[0].resource` 双字段同源(Q9) | `--project-dir --basename --meta-json --body-file` | `{path}` |
| **`generate-entity-page.py`** | ingest | 写 `knowledge/entities/<subtype>/<slug>.md`(frontmatter: type + aliases + summary + 6 轴 tag) | `--project-dir --subtype --slug --meta-json --body-file` | `{path}` |
| **`generate-concept-page.py`** | ingest | 写 `knowledge/concepts/<subtype>/<slug>.md`(同上 entity) | `--project-dir --subtype --slug --meta-json --body-file` | `{path}` |
| **`generate-analysis-page.py`** | query | 写 `knowledge/analyses/<timestamp>-<slug>.md`(frontmatter: sources_used 必填 + answer_to + generated_by + summary 首行 `**问题**: `);G11 3 H2 骨架;末尾 `> 引用:` 行(Set 比对 C15.4);atomic write 4 步保留 mtime(Q7) | `--project-dir --timestamp --slug --meta-json --body-file` | `{path}` |
| **`check-qmd.py`** | query | 数 knowledge 页 + `qmd --version`,按阈值返回引擎决策 JSON | `--project-dir` | `{pageCount, qmdAvailable, qmdVersion, engine, reason}` |
| **`query/index-filter.py`** | query | 跳 1 index.md 过滤 top-K(K=10);tags 命中的条目优先入选 | `--query --k 10 --project-dir` | `{candidates: list[path]}` |
| **`query/collect-neighbors.py`** | query | 跳 3 邻居收集(深度 1,硬上限 8 页);优先级:sources[] → `## 关联溯源` 末尾 `> 引用:` → syntheses 子主题 → 其他 `[[wikilink]]` | `--candidates --max-depth 1 --max-n 8 --project-dir` | `{neighbors: list[path]}` |
| **`query/path-b-detect.py`** | query | 跳 4 grep `**Creation**: query "X.*Y"` 模式(全 `**Creation**` 而非 `**Update**`,避免旧数据误触发),X.*Y 是对比对象对,累计 ≥ 3 次触发 | `--log --x --y --project-dir` | `{hit_count, trigger: bool}` |
| **`query/gating.py`** | query | gating 决策伪代码(intent / length / sources / "Wiki 未覆盖");ambiguous 优先于词命中(v0.5.2 PATCH) | `--intent --answer-length --sources-json --body` | `{decision: "prompt"\|"skip"}` |
| **`lint.py`** | lint | 11 类检查入口;`--fix --apply` 双开关;事务原子写入;git 脏检查;`--by raw_category/type/maturity/docform` | `--project-dir [--fix] [--apply] [--allow-dirty] [--by <axis>]` | `{issues: list, written: list, atomic: bool}` |
| **`lint-orphans.py`** | lint | 扫知识库找孤儿页 / 孤立页(豁免 index/overview/glossary) | `--project-dir` | `{orphans: list}` |
| **`okf-lint.py`** | ingest / lint | OKF v0.2 合规 + frontmatter `links:` 镜像同步(扫正文 wikilink + markdown link + URL,生成 `links:`,Set 比对 + Link Normalizer,Q7 死循环防护 4 步流程,atime + mtime 双还原) | `--file [--apply]` | `{drift, scanned, current, added, removed, reordered}` |
| **`okf-reader.py`** | query / ingest | plugin 自实现 OKF reader,产 OKF `sources` 列表(优先 frontmatter `links:`;fallback 扫正文 wikilink + markdown link) | `--project-dir --file` | `{sources: list}` |
| **`lint-query-output.py`** | query | C15.3 末尾标记校验(必须含 `❓` 或 `💡` 二者必居其一) | `--input <last-response>.md` | `{ok, marker: "prompt"\|"skip"\|"missing"}` |
| **`migrate-analysis-skeleton.py`** | query / lint | G11 v0.4.0 → v0.5.0 旧骨架迁移(检测 `## 重点摘录` + `## 我的思考` → 改写为 G11 专属 3 节) | `--from v0.4.0 --to v0.5.0 --file` | `{ok, h2_migrated}` |
| **`synthesize/make-slug.py`** | synthesize | slug 派生(小写 → 全角→半角 → 空格→ `-` → 去标点 → 全小写+连字符;中文保留) | `--topic` | `{slug: str}` |
| **`synthesize/detect-existing.py`** | synthesize | 检测 `<project>/knowledge/syntheses/<slug>.md` 是否存在 | `--project-dir --slug` | `{exists: bool, current_sources_count: int}` |
| **`synthesize/build-page.py`** | synthesize | 写 / 更新 synthesis 页(frontmatter: type + topic + sources_count + last_updated + tags + links 镜像);update 流程不动 `updated`,只改 `last_updated` + `sources_count`(Q7);atomic write 4 步 | `--project-dir --slug --meta-json --body-file [--update]` | `{path, created_or_updated: bool}` |
| **`synthesize/append-index.py`** | synthesize | append index.md 一行 `- [slug](syntheses/<slug>.md) — type · 一句话` | `--project-dir --slug --summary` | `{appended: bool}` |
| **`_common.py`** | 所有 | `atomic_write_preserving_mtime`(stat → write → utime 4 步;atime + mtime 双还原;Q7 v0.5.3 PATCH);`derive_raw_category`(`split('/')[1]`);`link_normalizer`(aliases 剥离 / `#anchor` 剥离 / path prefix 归一);`assert_no_input_calls`(C10.1 AST 自检);`git_dirty_check`(脏状态检查 + `--allow-dirty` 放行 + 干净时自动 stash) | (内部) | — |
| **`_meta.json`** | init | 记录 `{plugin, version, synced_at}`(plugin 升级总是覆盖) | — | JSON |
| **`README.md`** | (文档) | scripts/ 约定 + "无 daemon"边界 + 严禁交互硬契约 + Q10 lint C10.1 静态扫描 | — | (文件) |
| **`requirements.txt`** | (依赖) | `anydoc>=0.3.0` / `paddleocr>=2.7` / `jsonschema>=4.0` / `pyyaml>=6.0` / `pytest>=7.0` | — | (文件) |
| **`tests/test_no_daemon.py`** | (单测) | `ast` 模块扫 `scripts/*.py`,断言不出现 `input` / `sys.stdin.read` / `sys.stdin.readline` / `getpass` / `select.select([sys.stdin])`(lint C10.1) | — | pytest 报告 |

> 注:实际拆分粒度可合并到更少文件(如 `query/` 子目录、`synthesize/` 子目录);本表按"职责清晰"维度拆。

---

## 2. 数据契约(5 个跨边界数据形态)

### 2.1 proposal JSON schema(8 必填 + `_meta` 元数据)

**来源**:ingest SKILL.md §阶段 2 + design §3.2 + v0.5.4 PATCH

```yaml
{
  "file": "inbox/<basename>.<ext>",          # 必填,string,相对路径
  "suggested_subdir": "raw/<15 类字典之一>", # 必填,string
  "raw_category": "<01_EE架构|02_芯片|...|15_算法>",  # 必填,enum
  "format": "<md|txt|csv|json|yaml|xml|html|htm|rst|pptx|docx|xlsx|pdf|png|jpg|jpeg|bmp|tiff>",  # 必填,enum(小写)
  "converter": "<anydoc|claude-native|paddleocr|null>",  # 必填,enum(4 选 1)
  "native_text": <bool>,                                        # 必填,bool
  "converted_path": "<raw/<subdir>/<file>.converted.md 或 null>",  # 必填,string|null
  "concepts": [
    {"name": "...", "type": "<entities|concepts>", "subtype": "<子类>", "aliases": ["..."]}
  ],                                                             # 必填,array(maxItems=200)
  "_meta": {
    "doc_id": "<basename>-<sha256 前 8 位>",  # 必填
    "schema_version": "1.0",                  # 必填,固定 "1.0"
    "extracted_at": "<ISO 8601>",             # 必填
    "extracted_by": "agent: producer/aeps-llm-wiki-plugin/0.5.5"  # 必填
  }
}
```

**5 步校验**(v0.5.4 PATCH):

1. JSON 解析
2. jsonschema 校验
3. 字符集清洗(BOM 保留 / `\x00` & `\x1f` strip / `</script>` → `<\/script>`)
4. 截断检测(concepts ≤ 200)
5. 重写 `temp/<doc-id>-proposal.json.sanitized`

### 2.2 decision JSON schema(4 必填 + actions op 枚举)

**来源**:ingest SKILL.md §阶段 3 step 2 + v0.5.2 PATCH

```yaml
{
  "type": "ingest_decision",         # 必填,固定字符串
  "schema_version": "1.0",           # 必填
  "decided_at": "<ISO 8601>",        # 必填
  "actor": "human:<id>",             # 必填(actor 字符串规范)
  "proposal_refs": ["temp/proposal-<doc-id>.json", ...],  # 必填,string[]
  "actions": [
    {
      "op": "mv|overwrite|skip|delete-only",  # 必填,enum(4 选 1)
      "source": "inbox/<file>",                 # 必填
      "dest": "raw/<subdir>/<file>"             # 必填
    }
  ]
}
```

**`op 语义`**:

- `[y]` → `op: "overwrite"`(atomic overwrite,先备份 `temp/raw_backup_<hash>/`)
- `[n]` → `op: "skip"`
- `[d]` → `op: "delete-only"`(仅删旧副本,inbox 原文件保留)

### 2.3 temp/ 文件命名(全清单)

| 文件 | 触发 | 来源 | 生命周期 |
|---|---|---|---|
| `temp/<basename>.md` | ingest 阶段 1A/1B | `convert-to-md.py` 输出 | OCR 中间产物,`--cleanup` 默认删 |
| `temp/<basename>.<ext>.converted.md` | ingest 阶段 1B(G10) | `convert-to-md.py --emit-to temp/` | G10 双产物,跟随原文件迁到 `raw/<subdir>/` |
| `temp/proposal-<doc-id>.json` | ingest 阶段 2 subagent | subagent 写,`doc_id = <basename>-<sha256 前 8 位>` | Q11 写权矩阵,**严禁**其他 agent 改;`--cleanup` 默认删 |
| `temp/proposal-<doc-id>.json.sanitized` | ingest 阶段 3 step 5 | `validate-proposal.py` 5 步校验后重写 | **保留**,供用户复查 |
| `temp/proposal-<doc-id>.json.corrupt.bak` | ingest 阶段 3 step 5 损坏降级 | `validate-proposal.py.backup_corrupt` | **保留**,用户人工排查 |
| `temp/decision-<hash>.json` | ingest 阶段 3 step 2 拍板后 | 主 agent 汇总拍板 | `safe-mv.py --apply` 读取 |
| `temp/raw_backup_<hash>/<basename>.<ext>` | ingest 阶段 3 step 6 atomic overwrite | `safe-mv.py` 拍板 `[y]` 前置备份(Q7 防护) | **保留**,用户可手动回滚 |
| `temp/raw_backup_<hash>/<basename>.<ext>.converted.md` | 同上 G10 | 同上 | 同上 |

> 注:`hash` 算法未在 SKILL.md / design 中显式规定,从"内容 hash"语义推断建议 **sha256 前 8-12 位**(与 proposal `doc_id` 一致算法,降低 lint / 用户审计复杂度)。

### 2.4 temp/.gitignore 内容(5 行)

```
*
!.gitkeep
!proposal-*.json
!decision-*.json
!plan-*.json
```

**5 行规范**:

- 第 1 行 `*` — 屏蔽 temp/ 下所有默认内容(OCR 中间 md / scratch / 损坏备份 / raw_backup 等都进忽略)
- 第 2 行 `!.gitkeep` — 保留目录占位
- 第 3-5 行 `!proposal-*.json` / `!decision-*.json` / `!plan-*.json` — 显式允许 plan 文件(可选审计)

### 2.5 frontmatter 字段(3 层必填 + G10/G11 增量)

#### 通用必填(全 wiki)

| 字段 | 类型 | 必填 | 备注 |
|---|---|---|---|
| `type` | string | ✅ | OKF §4.1;取值见 design §3.1 §A(18 合法值) |
| `title` | string | ✅ | OKF §4.1 推荐 |
| `description` | string | ✅ | OKF §4.1 推荐;一句话短摘要 |
| `updated` | ISO 8601 | ✅ | plugin 扩展(Q7 死循环防护) |
| `tags` | string[] | ✅ | 6 轴受控词表;`docform/` + `domain/` 单值必填;`maturity/` 单值推荐 |

#### type-specific 必填

| 字段 | type | 必填 | 备注 |
|---|---|---|---|
| `source_file` | `source` | ✅ | 顶层字符串,Obsidian UI 可点(Q9) |
| `sources[].resource` | `source` | ✅ | OKF §5.1;**与 `source_file` 值相等**(Q9 双字段同源,C5 lint FAIL) |
| `summary` | `source` / `analysis` | ✅ | ≤ 280 字符 |
| `sources_used` | `analysis` | ✅ | G11 必填,string[],每条解析到真实存在的 `knowledge/**/*.md`(lint C15.2 FAIL) |
| `answer_to` | `analysis` | ✅ | G11 必填,原 query 问句原样保留 |
| `generated_by` | `analysis` | ✅ | `agent: producer/aeps-llm-wiki-plugin/<version>` |
| `sources:` | `comparison` | ✅ | ≥ 2 条 wikilink |
| `topic` / `sources_count` / `last_updated` | `synthesis` | ✅ | sources_count < 3 → WARN |
| `aliases:[]` | `entity` / `concept` | ✅ | 同义 / 别名 |

#### G10 增量(plugin 扩展)

| 字段 | type | 必填 | 备注 |
|---|---|---|---|
| `format` | `source` | ✅ | 原文件扩展名小写(`PDF` → `pdf`) |
| `converter` | `source` | ✅ | `anydoc` / `paddleocr` / `claude-native` / `null` |
| `native_text` | `source` | ✅ | bool;`true ⇔ converter=null ⇔ converted_path=null`(强绑定 C13) |
| `converted_path` | `source` | ✅ | `raw/<subdir>/<basename>.<ext>.converted.md` 或 `null` |
| `links` | 所有 | ⚠️ plugin 自动 | OKF §9 镜像字段;Set 比对 + Link Normalizer + 4 步 atomic write |

### 2.6 log.md 6 种前缀模板

**来源**:design §3.4 + ingest SKILL.md §输出格式

plugin 强制 5 种(便于 lint 解析);v0.5.4 PATCH 新增 **第 6 种** `**IngestFailure**`(在原 9 步串行清单之外):

| 前缀 | 触发 | 模板 |
|---|---|---|
| `**Creation**` | 新建 wiki 页 | `**Creation**: [<page>](<path>) by agent: producer/aeps-llm-wiki-plugin/<version>` |
| `**Update**` | 修改既有页 | `**Update**: re-run init at <ISO> by agent: ...` / `**Update**: synthesized update on [<slug>](syntheses/<slug>.md) — sources_count now N` |
| `**Deprecation**` | 归档 / `status: deprecated` | `**Deprecation**: [<page>](<path>) — reason` |
| `**Migration**` | inbox → raw 文件迁移 | `**Migration**: [<file>](inbox/<file>) → [<file>](../raw/<subdir>/<file>)` |
| `**LintFix**` | lint `--fix` 自动应用的结构修复 | `**LintFix**: <rule-name> on [<file>](<path>) — <one-line summary>` |
| `**Converted**` | G10 v0.4.0 转换产物落盘(配合 `**Migration**`) | `**Converted**: raw/<subdir>/<file>.converted.md (via <converter>)` |
| `**IngestFailure**` | v0.5.4 PATCH 损坏降级(第 6 种,plugin 引入) | `**IngestFailure**: temp/<doc-id>-proposal.json — <error>` |

**强约束**:日期 heading `## YYYY-MM-DD`;**最新在前**;粗体前缀仅这 6 种;actor 字符串遵循 SCHEMA.md §4(`agent: producer/<plugin>/<ver>` / `human:<id>` / `process:<id>`)。

---

## 3. 关键 PATCH 影响 scripts/ 的(7 项)

### 3.1 G10 双文件迁移

**`convert-to-md.py`**:新增 `--emit-to <subdir>` 参数,单文件:stdout(向后兼容);batch:`--batch ... --emit-to temp/` 同时写 `temp/<basename>.md` + `temp/<basename>.<ext>.converted.md`(G10 适用,**纯文本不生成** `.converted.md`)。**命名规则**:保留原扩展名(`iso26262.pdf.converted.md`)。

**`safe-mv.py`**:同时迁原文件 + `.converted.md` 到 `raw/<subdir>/`;inbox 原文件 + temp 副本**同步删除**;纯文本场景跳过 md 副本迁移。

**`generate-source-page.py`**:frontmatter 增字段:`format` / `converter` / `native_text` / `converted_path` / `links: ["[[<basename>.<ext>.converted]]"]`(纯文本:`[[<basename>]]`)。

### 3.2 Q5 命名飘检测

**判定规则**:**Levenshtein 距离 ≤ 2** 或 **全小写 + `-` 归一后相同** → **强制改用已有目录**(不创建新目录);前缀 / 后缀差异 / 同义拼写 → 提示。

**Linter**:`_common.detect_name_drift(suggested, raw_existing)`。

**触发点**:ingest 阶段 3 step 1(LLM 提议 raw 子目录名的瞬间,前移自 lint,design §4.4);lint 1.4 `--fix` 输出提案(仅报告,不自动合并)。

**入参**:`suggested_subdir`(string) + `raw_existing`(list of str)。

**返回**:`{hit: bool, forced_to: str|null, distance: int, reason}`。

### 3.3 Q7 死循环防护 v0.5.3(影响所有写盘脚本)

**强制 4 步流程**(所有 lint `--fix` / safe-mv overwrite / okf-lint links-mirror apply 写盘):

1. **`stat` 取原始时间戳**:`stat = os.stat(path); original_atime = stat.st_atime; original_mtime = stat.st_mtime`
2. **`write` 写盘**:`Path.write_text(new_content, encoding='utf-8')` 或 atomic(先 `.tmp` 再 `os.replace`)
3. **`utime` 还原**:`os.utime(path, (original_atime, original_mtime))` — **atime 与 mtime 都必须显式还原**
4. **`assert` 自检**(测试代码):`assert os.stat(path).st_mtime == original_mtime and os.stat(path).st_atime == original_atime`

**`updated` 字段绝对不改**(`links:` 同步是机械镜像修复,不是业务内容变更)。

**封装位置**:`_common.atomic_write_preserving_mtime(path, content)`。

**反例警戒**:

- ❌ `Path.write_text(content)` 默认行为 + 不调 utime → mtime / atime 必变
- ❌ 只还原 mtime 不还原 atime → 部分 FS(inotify / FSEvents)误判
- ❌ `Path.touch()` 模拟时间戳还原(刷新为当前时间,反向 bug)

### 3.4 Q10 scripts 严禁交互(影响所有 scripts/,lint C10.1 静态扫描)

**禁止调用清单**(`tests/test_no_daemon.py` 用 `ast` 扫描断言):

| 禁止调用 | 替代 |
|---|---|
| `input()` / `input(prompt)` | SKILL.md 在 Claude 对话层发起交互,拍板结果通过 `--apply temp/decision-<hash>.json` 等参数传入 |
| `sys.stdin.read()` / `sys.stdin.readline()` | 同上 |
| `getpass.getpass()` | 完全禁 |
| `select.select([sys.stdin], ...)` 等 stdin 阻塞 | 同上 |
| `while True: pass` 等阻塞事件循环 | §1.4 NFR-1 单次运行即退 |

**stdin 全禁原则**:无论 `sys.stdin.isatty()` 是否成立,scripts 一律不读 stdin。所有 plan / decision / proposal / 配置走 `--apply <filepath>` / `--output <path>` / `--config <path>` 显式文件参数。`cat foo.json | python script.py` 这类非交互式管道**同样判定违规**。

### 3.5 Q11 subagent 写权矩阵(影响 ingest 阶段 2 subagent prompt 硬约束)

**subagent 只能写**:

- `temp/proposal-<doc-id>.json`

**subagent 严禁写**:

- `knowledge/**/*`(任意子目录:sources / entities / concepts / analyses / comparisons / syntheses / index.md / glossary.md / log.md / overview.md / SCHEMA.md)
- `raw/**/*.md`
- `scripts/_meta.json`

**subagent 严禁调用**:

- `convert-to-md.py`(零 paddleocr 调用,冷启动已在阶段 1 batch 进程内完成)
- `safe-mv.py` / `ensure-dirs.py` / `append-log.py` / `validate-frontmatter.py` / `validate-proposal.py`(任何写操作脚本)

**subagent 可读**:

- `temp/<basename>.md`(阶段 1 产物)
- `temp/<basename>.<ext>.converted.md`(G10 转换副本)
- `<project>/knowledge/SCHEMA.md` / `<project>/raw/README.md` / `<project>/templates/concept-entities-readme.md` / `<project>/templates/tag-template.md`
- `aeps-llm-wiki-plugin/src/schema/proposal.schema.yaml`(若已落地)

### 3.6 v0.5.2 atomic overwrite(影响 `safe-mv.py`)

**拍板 `[y]` → `op: "overwrite"` 行为**:

1. **先备份**旧文件到 `temp/raw_backup_<hash>/<basename>.<ext>` + `<basename>.<ext>.converted.md`(Q7 防护,可回滚)
2. **atomic 替换**两文件:`os.replace(temp/<file>.converted.md, raw/<subdir>/<file>.converted.md)` + `os.replace(<new>, raw/<subdir>/<file>)`
4. **写盘要么全部成功要么全失败**(G10 双文件绑定)
5. **覆盖范围**:仅 `<file>` + `<file>.converted.md` 两个目标;**不动**同 subdir 其他文件;**不动** frontmatter `updated` + 文件 mtime(Q7 死循环防护延续)
6. log.md 追加 `**Migration**(overwrite): inbox/<file> → raw/<subdir>/<file>` + `**Converted**(overwrite): raw/<subdir>/<file>.converted.md (via <converter>)` + 备份路径

**拍板 `[d]` → `op: "delete-only"`**:

- 仅删 `raw/<subdir>/<basename>.<ext>` + `<basename>.<ext>.converted.md`
- inbox 原文件保留(等用户手动处理)

**不开"重转 skill"**:不对历史所有 `.converted.md` 提供批量重转入口(对齐 v0.4.0 G10 拍板);用户需批量时自己写脚本 loop 此流程。

### 3.7 v0.5.4 proposal JSON 5 步校验 + 字符清洗 + 损坏降级(影响 `validate-proposal.py`)

**5 步校验**(对每个 proposal):

1. **JSON 解析**:`json.load()` 失败 → `JSONDecodeError` 抛出
2. **schema 校验**:`jsonschema.validate()` 失败 → `ValidationError` 抛出
3. **字符集清洗**:BOM 保留;`\x00` NUL / `\x1f` 单元分隔符 → strip;`</script>` 注入字面量 → 替换为 `<\/script>`
4. **截断检测**:`concepts` 数组 ≤ 200 条(超过视为 LLM 输出截断)
5. **重写清洗后 JSON**:写 `temp/<doc-id>-proposal.json.sanitized`

**失败降级路径**(不阻断整批):

- **JSONDecodeError / ValidationError / maxItems 超限** → **不派 subagent 重试**(避免同样模式);**主 agent 单线程**重跑该文件(走 §阶段 1A 单文件分支)
- **重试限额 1 次**(防 token 耗尽)
- **重跑仍失败** → 标记跳过 + 写 `**IngestFailure**` log 段
- **其他正常 proposal 继续合并**
- **损坏文件 inbox 原文件保留**(后续用户手动重 ingest)
- **损坏 proposal 备份到 `temp/<doc-id>-proposal.json.corrupt.bak`**(供用户人工排查)

---

## 4. 测试对齐(implement.md §1 阶段 C 测试清单 → .py 函数)

> 阶段 C 测试用 pytest(`tests/test_*.py`),断言 `scripts/*.py` 行为。每条 AC 一组 fixture。

| 测试用例(待 §阶段 C 落地) | 对应 .py 函数 | design / scripts/README 锚点 |
|---|---|---|
| `test_convert_to_md_dispatch`(按扩展名走 native / anydoc / paddleocr) | `convert-to-md.py:classify` + `:convert_one` | design §4.2 + scripts/README.md |
| `test_convert_to_md_batch_share_engine`(批量共享单 Engine) | `convert-to-md.py:convert_batch` | design §4.2.1 三阶段并发 |
| `test_convert_to_md_emit_to_g10`(`--emit-to` 写 `.converted.md`) | `convert-to-md.py:convert_batch --emit-to` | design §4.2 G10 M1/M4 |
| `test_check_qmd_threshold`(N < 500 / 500-1000 / ≥1000 三档) | `check-qmd.py:run` | design §4.3 query 引擎决策矩阵 |
| `test_check_qmd_fail_exitcode`(≥1000 + 未装 → 非零退出) | `check-qmd.py` | design §4.3 |
| `test_safe_mv_overwrite_atomic`([y]`→ atomic 替换 + 备份) | `safe-mv.py:apply --op=overwrite` | design §4.2 v0.5.2 PATCH |
| `test_safe_mv_delete_only`([d]`→ 仅删旧副本) | `safe-mv.py:apply --op=delete-only` | design §4.2 v0.5.2 PATCH |
| `test_safe_mv_g10_pair_migration`(原文件 + `.converted.md` 同步) | `safe-mv.py:move_pair` | design §4.2 G10 M1 |
| `test_safe_mv_preserve_mtime`(Q7 — overwrite 不改 updated + mtime) | `safe-mv.py` + `_common.atomic_write_preserving_mtime` | design §3.6.2 |
| `test_append_log_creation/update/migration/lintfix/converted/ingestfailure` | `append-log.py` | design §3.4 log.md 6 种前缀 |
| `test_append_log_latest_first`(`log.md` append 最新在前) | `append-log.py` | design §3.4 + SCHEMA.md §7 |
| `test_append_log_actor_format`(`agent:` / `human:` / `process:` 正则) | `append-log.py` | design §3.1 §A actor_patterns |
| `test_validate_frontmatter_jsonschema`(按 schema.yaml 校验) | `validate-frontmatter.py` | design §3.2 schema |
| `test_validate_frontmatter_g10_consistency`(native_text ↔ converter ↔ converted_path 三元组) | `validate-frontmatter.py` | design §3.2 g10_source_consistency |
| `test_validate_frontmatter_unknown_type_warn_not_fail`(OKF §11) | `validate-frontmatter.py` | design §3.1 lint §A |
| `test_validate_frontmatter_6轴_tag`(docform/ + maturity/ 必填,axis prefix 校验) | `validate-frontmatter.py` | design §3.1 §B tags_format |
| `test_validate_proposal_5_5steps`(JSON 解析 → schema → 字符清洗 → 截断 → 重写) | `validate-proposal.py:run` | ingest SKILL.md §阶段 3 step 5 + v0.5.4 PATCH |
| `test_validate_proposal_char_clean`(`\x00` strip / `</script>` replace / BOM keep) | `validate-proposal.py` | ingest SKILL.md §阶段 3 step 5 |
| `test_validate_proposal_truncate`(concepts > 200 → 截断检测) | `validate-proposal.py` | ingest SKILL.md §阶段 3 step 5 |
| `test_validate_proposal_corrupt_backup`(JSONDecodeError → `.corrupt.bak`) | `validate-proposal.py:backup_corrupt` | ingest SKILL.md §阶段 3 step 5 |
| `test_lint_eleven_categories`(11 类检查) | `lint.py:scan` | lint SKILL.md §阶段 1 + design §4.4 |
| `test_lint_stale_180_days_with_log_fallback`(陈旧判定优先级) | `lint.py` | lint SKILL.md §1.3 + design §5.4 |
| `test_lint_name_drift_levenshtein_le_2`(Q5) | `lint.py:detect_name_drift` + `_common.detect_name_drift` | design §4.4 LLM 命名飘 |
| `test_lint_orphans_with_exemptions`(index/overview/glossary 豁免) | `lint-orphans.py:run` | lint SKILL.md §1.1 |
| `test_lint_sources_skeleton_3h2`(`## 重点摘录` / `## 我的思考` / `## 总结`) | `lint.py:check_skeleton` | lint SKILL.md §1.9 + design §3.6 |
| `test_lint_analyses_skeleton_g11`(`## 方案推演 / 架构分析` / `## 关联溯源` / `## 总结`) | `lint.py:check_skeleton --type=analysis` | lint SKILL.md §1.9 + templates/analysis-page.md |
| `test_lint_summary_section_extract`(`## 摘要` → 合并到 frontmatter `summary`) | `lint.py:extract_summary_section` | lint SKILL.md §1.9 + design §3.1 §C |
| `test_lint_comparisons_sources_required`(≥ 2 wikilink FAIL) | `lint.py:check_comparisons` | lint SKILL.md §1.10 |
| `test_lint_syntheses_sources_count_warn`(< 3 WARN) | `lint.py:check_syntheses` | lint SKILL.md §1.11 |
| `test_okf_lint_links_mirror_set_compare`(Set 比对 / 顺序无关) | `okf-lint.py:links_mirror_check` | design §3.6.2 Link Normalizer |
| `test_okf_lint_links_mirror_apply_4_steps`(stat → write → utime 4 步) | `okf-lint.py:links_mirror_apply` | design §3.6.2 v0.5.3 PATCH |
| `test_okf_lint_links_mirror_preserve_atime_mtime`(atime + mtime 双还原) | `okf-lint.py:links_mirror_apply` | design §3.6.2 v0.5.3 PATCH |
| `test_okf_lint_updated_unchanged_after_apply`(`--fix` 不改 `updated`) | `okf-lint.py:links_mirror_apply` | design §3.6.2 + §3.4 不变量 |
| `test_okf_lint_alias_anchor_normalizer`(`[[page\|Alias]]` / `[[page#section]]` 归一) | `okf-lint.py:_normalizer` | design §3.6.2 Link Normalizer |
| `test_lint_raw_category_derive`(`sources[0].resource.split('/')[1]`) | `_common.py:derive_raw_category` + `lint.py:check_raw_category` | design §3.6.1 |
| `test_lint_by_raw_category_group` | `lint.py:group_by` | design §3.6.1 lint group by |
| `test_lint_fix_default_dry_run`(`--fix` ≠ `--apply`) | `lint.py:apply` | lint SKILL.md §阶段 3 安全锁 + design §5.4 |
| `test_lint_fix_apply_atomic_transaction`(事务原子写入) | `lint.py:apply` + `_common.transactional_apply` | design §5.4 |
| `test_lint_fix_apply_git_dirty_block`(脏状态退出非 0) | `_common.git_dirty_check` + `lint.py` | design §5.4 |
| `test_lint_fix_apply_allow_dirty`(`--allow-dirty` 放行) | `lint.py` | design §5.4 |
| `test_lint_fix_apply_clean_auto_stash`(干净时自动 stash) | `_common.git_dirty_check` | design §5.4 |
| `test_lint_query_output_gating_marker`(C15.3 末尾 `❓` 或 `💡`) | `lint-query-output.py:check` | design §3.2 g11_query_gating |
| `test_migrate_analysis_skeleton_v040_v050`(G11 旧骨架迁移) | `migrate-analysis-skeleton.py:run` | query SKILL.md §4.4 + templates/analysis-page.md |
| `test_generate_source_page_g10_fields`(`format` / `converter` / `native_text` / `converted_path` / `links`) | `generate-source-page.py:write` | design §3.6 + templates/source-page.md |
| `test_generate_source_page_double_source_q9`(`source_file` ↔ `sources[0].resource` 等值) | `generate-source-page.py:write` | design §3.6.1.1 Q9 |
| `test_generate_entity_page_subtype_dictate_dir`(entities/person/<slug>.md) | `generate-entity-page.py:write` | design §3.6 子目录 ↔ type 1:1:1 |
| `test_generate_concept_page_subtype_dictate_dir`(concepts/standard/<slug>.md) | `generate-concept-page.py:write` | 同上 |
| `test_generate_analysis_page_sources_used_mirror`(`> 引用:` 行 Set 比对 C15.4) | `generate-analysis-page.py:write` | design §3.6 + templates/analysis-page.md + lint C15.4 |
| `test_generate_analysis_page_summary_question_prefix`(首行 `**问题**: ` 强制) | `generate-analysis-page.py:write` | templates/analysis-page.md |
| `test_generate_analysis_page_atomic_preserve_mtime`(Q7 analysis 页不更新 mtime) | `generate-analysis-page.py:write_preserving_mtime` | design §4.3.2 Q7 |
| `test_init_vault_first_run`(建 6 顶层 + raw 15 + knowledge 18 + temp + 拷 templates/scripts + 写 seed) | `init-vault.py:create_top_dirs/create_raw_subdirs/create_knowledge_subdirs/copy_templates/copy_scripts/create_temp/write_seed_files` | design §4.1 + init SKILL.md §阶段 1-3 |
| `test_init_vault_re_run_dict_append`(字典 append 策略) | `init-vault.py:append_dict` | design §4.1.1 幂等再入 + init SKILL.md §阶段 4 |
| `test_init_vault_re_run_no_overwrite_index/overview/glossary`(LLM 累积维护) | `init-vault.py` | design §4.1.1 文件 sync 策略 |
| `test_init_vault_temp_gitignore_5_lines`(5 行规范) | `init-vault.py:create_temp` | design §4.1 init 步骤 5 |
| `test_init_vault_meta_json_always_overwrite`(`_meta.json` 总是覆盖) | `init-vault.py:copy_scripts` | design §2.4 _meta.json |
| `test_check_deps_missing_packages_fail`(import 失败 → FAIL) | `check-deps.py:run` | ingest SKILL.md §阶段 0 + design §2.4 |
| `test_synthesize_make_slug`(`OKF 生态全景` → `okf-生态全景`) | `synthesize/make-slug.py:make_slug` | synthesize SKILL.md §阶段 2 |
| `test_synthesize_update_preserves_updated`(update 不动 `updated`) | `synthesize/build-page.py:update` | synthesize SKILL.md §阶段 3 + Q7 |
| `test_synthesize_create_log_md_creation`(`**Creation**: synthesize "<topic>"`) | `synthesize/build-page.py` + `append-log.py` | synthesize SKILL.md §阶段 4.3 + design §3.4 |
| `test_synthesize_update_log_md_update`(`**Update**: synthesized update on <slug>`) | `synthesize/build-page.py` + `append-log.py` | 同上 |
| `test_synthesize_sources_count_lt_3_warn` | (LLM prompt,无脚本强制) | synthesize SKILL.md §输出格式 |
| `test_ingest_dedupe_concepts_aliases_merge`(跨 proposal aliases 合并) | `ingest/dedupe_concepts.py:dedupe_concepts` | ingest SKILL.md §阶段 3 step 3 |
| `test_ingest_dedupe_entities_name_aliases_merge` | `ingest/dedupe_entities.py:dedupe_entities` | ingest SKILL.md §阶段 3 step 4 |
| `test_ingest_pre_classify_raw_subdir`(`--raw-subdir=02_芯片` 跳过拍板) | `ingest/pre_classify.py:pre_classify` | ingest SKILL.md §子命令 |
| `test_ingest_cleanup_keeps_sanitized_drops_md`(cleanup 策略) | `ingest/cleanup.py:cleanup` | ingest SKILL.md §阶段 4 |
| `test_query_path_b_detect_3_creation_query_x_vs_y`(路径 B 触发) | `query/path-b-detect.py:path_b_detect` | query SKILL.md §4.3 + design §4.6 路径 B |
| `test_query_index_filter_top_k_10` | `query/index-filter.py:index_filter` | design §4.3 4 跳扫描 + query SKILL.md §阶段 2 跳 1 |
| `test_query_neighbors_depth_1_max_8` | `query/collect-neighbors.py:collect_neighbors` | design §4.3 跳 3 + query SKILL.md §阶段 2 跳 3 |
| `test_query_gating_intent_ambiguous_skip`(ambiguous 优先于词命中) | `query/gating.py:gating` | design §4.3.2 v0.5.2 PATCH |
| `test_query_gating_4_triggers_4_skips`(4 触发 / 4 不触发) | `query/gating.py:gating` | design §4.3.2 + lint C15.3 |
| **`test_no_daemon_static_scan`(C10.1 AST 扫)** | `tests/test_no_daemon.py:scan` + `_common.assert_no_input_calls` | **design §2.4.1 + Q10 + implement §C10.1** |
| `test_atomic_write_preserving_mtime_4_steps`(stat → write → utime 4 步 + assert) | `_common.atomic_write_preserving_mtime` | design §3.6.2 v0.5.3 PATCH |
| `test_link_normalizer_alias_anchor_path`(aliases / `#anchor` / path prefix 归一) | `_common.link_normalizer` | design §3.6.2 Link Normalizer |

---

## 5. CLAUDE.md 硬约束落地(NFR-1 ~NFR-7)

### 5.1 NFR-1:无 daemon(NFR-1 + C10)

- ❌ scripts/ **不**带 HTTP server / MCP server / RAG / embedding 服务
- ❌ scripts/ **不**开监听 / 阻塞 loop
- ✅ scripts/ 单次运行即退(`python3 scripts/foo.py --args` 执行完退出码 0/非 0)
- ✅ 静态扫描:`tests/test_no_daemon.py` 用 `ast` 模块扫所有 `scripts/*.py`,断言不出现:
  - `http.server.HTTPServer` / `socketserver.TCPServer` / `http.server.BaseHTTPRequestHandler`(Python 服务接口)
  - `subprocess.Popen(` 启动**长生命周期**子进程(单次 `subprocess.run` 允许)
  - `signal.signal(` + 阻塞 loop(`while True:` + `time.sleep()` 之类)
  - `sys.stdin` 长时间读取 / `signal.pause()` 阻塞

### 5.2 NFR-3:中文为主 + 术语英文

- scripts/ 输出日志 / 错误消息**中文为主**,关键术语英文保留(`proposal` / `decision` / `op` / `native_text` 等)
- 单元测试报告中文
- 函数 / 变量命名英文(代码约定)

### 5.3 NFR-4:无绝对路径

- ❌ scripts/ 内**不出现**绝对路径(`/Users/...` / `C:\...` / `~/.claude/...` / `${CLAUDE_PLUGIN_ROOT}`)
- ✅ 统一用 `--project-dir <path>`(默认 `.`),相对路径
- ✅ 静态扫描:`tests/test_no_absolute_paths.py` 扫 `scripts/*.py`,断言不出现:
  - 绝对 Unix 路径:`/(Users|home|tmp|opt)/...`、`/etc/...`、`/var/...`
  - 绝对 Windows 路径:`C:\` / `D:\` / `E:\`
  - plugin 反向引用:`${CLAUDE_PLUGIN_ROOT}`
  - 显式 home:`~/.claude/...` / `~/.config/...`

### 5.4 NFR-5:临时文件进 `temp/`

- ❌ scripts/ **不**写 `/tmp/` / `C:\Users\...\AppData\Local\Temp\`
- ✅ 全部临时文件进 `--project-dir` 下的 `temp/`
- ✅ `temp/.gitignore` 5 行规范(见 §2.4)
- ✅ `tests/test_temp_dir_usage.py` 运行时验证

### 5.5 NFR-6:LICENSE = Apache 2.0

- `LICENSE` 文件已在阶段 A 落地;scripts/ **不**修改 LICENSE 字段
- 静态扫描:`tests/test_license.py`

### 5.6 NFR-7:`scripts/requirements.txt` 依赖清单

- `anydoc>=0.3.0`(强依赖,`.pptx/.docx/.xlsx/.pdf` 降级)
- `paddleocr>=2.7`(强依赖,`.png/.jpg/.jpeg/.bmp/.tiff` OCR)
- `jsonschema>=4.0`(强依赖,frontmatter schema 校验)
- `pyyaml>=6.0`(强依赖,YAML 读写)
- `pytest>=7.0`(单测时需要;运行时不需要)
- 不强制 `qmd`(可选依赖,对应 §4.3 wiki 规模较大时降级)

---

## 6. SKILL.md ↔ scripts/ 重构契约(下一轮)

> **本轮不重写 SKILL.md**(commit 78e6a41 已落地);下一轮(DESIGN.md 确认 + .py 落地后)按以下原则重写 5 份 SKILL.md。

| SKILL.md | 当前直接做(LLM) | 重构后(Llm 仅调度) |
|---|---|---|
| **init** | 6 顶层目录创建 + .gitkeep + 拷 README + 拷 templates + 拷 scripts + 写种子文件 + 字典 append + 写 log | 调 `init-vault.py --project-dir . [--re-run]`,读返回的 sync 摘要,展示给用户 |
| **ingest** | 阶段 2 抽 entity/concept 写 proposal(LLM) + 阶段 3 拍板门汇总(LLM) + 阶段 3 step 6 mv(LLM) + step 7 写源页(LLM) + step 8 写 entity/concept(LLM) + step 9 更新 index/log/glossary(LLM) | LLM 只做:阶段 1 调 `check-deps.py` + `convert-to-md.py` 拿产物 → 阶段 2 subagent 写 proposal(Llm 仍在,但**只**写 temp/proposal-*.json)→ 阶段 3 调 `validate-proposal.py` 5 步校验 → 拍板门汇总后写 temp/decision-*.json → 调 `safe-mv.py --apply temp/decision-*.json` + `generate-source-page.py` + `generate-entity-page.py` + `generate-concept-page.py` + `append-log.py` |
| **query** | 4 跳扫描(LLM 读 index + 读候选页 + 读邻居 + grep log)+ intent 推断(LLM)+ gating(LLM 伪代码)+ 落档 analysis 页(LLM 写 frontmatter + 3 H2 + log) | LLM 只做:调 `check-qmd.py` 拿 engine → 调 `query/index-filter.py` 拿 candidates → 调 `query/collect-neighbors.py` 拿 neighbors → 读 + 推断 intent + gating → 拍板后调 `generate-analysis-page.py` 写落档 + `append-log.py` |
| **lint** | 11 类检查逐项报告(LLM prompt 提示)+ `--fix` 提案(LLM 提示)+ 双开关(LLM 提示)+ 安全锁(LLM 提示) | LLM 调 `lint.py --project-dir . [--fix --apply] [--allow-dirty] [--by <axis>]`,读返回报告;语义级判断(矛盾 / 命名飘 / 漏链 / 陈旧)若需 LLM 参与,**附加**调 `lint-orphans.py` / `okf-lint.py` 拿结构化结果 |
| **synthesize** | 自由发挥写正文(LLM)+ 写 index 一行(LLM)+ 写 log.md(LLM) | LLM 自由发挥写正文;调 `synthesize/make-slug.py` 拿 slug → 调 `synthesize/detect-existing.py` 判定 create/update → 调 `synthesize/build-page.py [--update]` 写页 → 调 `synthesize/append-index.py` 更新索引 → 调 `append-log.py` 写 log |

**LLM 仍保留的判断/决策**(不能脚本化):

- 命名飘判定(LLM 比对 raw/ 已有目录)
- 矛盾判定(LLM 语义判断)
- 陈旧判定语义(LLM 判断页面是否真过期)
- 漏链候选术语抽取(LLM 语义)
- intent 推断(LLM)
- sources_count 不足时的用户拍板
- subagent 抽 entity/concept(LLM 任务)

---

## 7. 不在本次范围(后续版本)

- v0.6:knowledge-base 类 MCP server(目前 NFR-1 硬约束禁止)
- v0.6:Web 端 UI(目前纯 CLI / Claude Code 形态)
- v0.7:多语言(目前 NFR-3 中文优先)
- v1.0:正式 GA,定稿 schema,冻结 tag-template.md 6 轴

---

## 8. 验收 checklist

DESIGN.md 落地后,跑下列自检:

```bash
ls f:/llm-wiki/aeps-llm-wiki-plugin/src/scripts/DESIGN.md
head -5 f:/llm-wiki/aeps-llm-wiki-plugin/src/scripts/DESIGN.md
grep -rn "C:\\\\\|D:\\\\\|/Users/" f:/llm-wiki/aeps-llm-wiki-plugin/src/scripts/DESIGN.md  # 应无命中
```

DESIGN.md 内部一致性自检:

- §1.1 列出的 22 个 .py + `_meta.json` + README + requirements.txt + tests/test_no_daemon.py,每个都在 §3 PATCH 映射或 §4 测试对齐里有体现
- §2.1 / §2.2 JSON schema 字段名与 §1.1 函数入参 / 返回字段一致
- §2.5 frontmatter 必填字段与 templates/source-page.md / analysis-page.md / knowledge-SCHEMA.md 一致
- §2.6 log.md 6 种前缀与 SKILL.md §输出格式一致

---

## 9. Change History

### v0.5.5(2026-09-03)— 阶段 C-1.3 query 组落地

- **新增 5 个 .py 顶层**:
  - `check-qmd.py`(199 行 / 6032 字节)— 引擎决策(N<500 / 500-1000 / ≥1000 三档 + qmd 探测)
  - `generate-analysis-page.py`(404 行 / 13995 字节)— G11 3 H2 骨架 + sources_used 必填(C15.2)+ Q7 atomic 防护 + > 引用: 行 Set 比对(C15.4)
  - `lint-query-output.py`(120 行 / 3515 字节)— 末尾 `❓` / `💡` 标记校验(C15.3)
  - `migrate-analysis-skeleton.py`(275 行 / 9100 字节)— v0.4.0 → v0.5.0 旧骨架迁移(默认 dry-run;--apply 写盘)
  - `okf-reader.py`(248 行 / 7676 字节)— OKF v0.2 sources 列表(frontmatter links 优先 + 正文 wikilink/markdown/url fallback)
- **新增 query/ 子目录 4 个 .py**:
  - `query/index-filter.py`(264 行 / 7786 字节)— 跳 1 K=10 过滤 + frontmatter tags 命中加权
  - `query/collect-neighbors.py`(430 行 / 14744 字节)— 跳 3 深度 1 上限 8 + 4 级优先级降权
  - `query/path-b-detect.py`(177 行 / 5302 字节)— 路径 B 触发探测(Creation-only 匹配,日 ≥3 trigger)
  - `query/gating.py`(250 行 / 7986 字节)— 4 跳过 / 4 触发的伪代码实现(ambiguous 优先)
- **新增 tests/test_query_group.py**(1123 行 / 39814 字节)— 覆盖 34 个测试用例
- **pytest 结果**:64 旧 + 34 新 = **98 passed in 22.57s**(0 failed)
- **DESIGN.md 落地注脚**:
  - `check-qmd.py` 阈值常量与 query SKILL.md §阶段 0 完全一致(`QUERY_INDEX_THRESHOLD=500` / `QUERY_QMD_REQUIRED_THRESHOLD=1000`);qmd 探测在子进程跑 `qmd --version`,允许 `FileNotFoundError` 兜底
  - `generate-analysis-page.py` 时间戳格式 `2026-09-01T14:30:00Z` → 文件名 `2026-09-01T14-30-00Z-autosar.md`(冒号 → 连字符,Windows 文件名安全);`sources_used` 必填 + `answer_to` 必填 + `generated_by` 自动补 plugin 统一格式
  - `generate-analysis-page.py` 二次写盘走 Q7 `atomic_write_preserving_mtime`(atime + mtime 双还原);`> 引用:` 行 Set 比对走 `_validate_set_compare`(C15.4)
  - `migrate-analysis-skeleton.py` 默认 dry-run,`--apply` 才走 `atomic_write_preserving_mtime`;与 lint 风格一致
  - `okf-reader.py` frontmatter `links:` 数组优先级最高;list 内嵌套 dict(`- resource: ...\n    title: ...`)由自实现 mini-YAML 解析器处理;`[[page|Alias]]` / `[[page#anchor]]` 走 `_common.link_normalizer` 归一
  - `query/index-filter.py` 中文按字拆 + 英文按非字母数字拆的极简分词;`domain/xxx` 形 token 视为 tag 命中加权
  - `query/collect-neighbors.py` 4 级权重降权不忽略:`sources_field=1.0` > `reference_line(= 引用: 行)=0.9` > `syntheses_subtopic=0.8` > `wikilink=0.5`;`_norm` 函数支持 wikilink 与相对路径两种形态,`[[page]]` 走 `link_normalizer`,`xxx/yyy/zzz.md` 保留目录结构
  - `query/path-b-detect.py` 用 3 段 lookahead 正则同时校验该行含 `**Creation**: query` + X + Y(顺序无关),避免贪婪 `.*` 越过 X 匹配失败
  - `query/gating.py` 跳过条件先判定(任一命中即 skip),触发条件后判定(任一命中即 prompt),兜底 skip;`ambiguous` 优先于词命中(v0.5.2 PATCH)
  - `query/` 子目录脚本顶部加 `sys.path.insert(0, Path(__file__).resolve().parent.parent)` 复用 `_common.emit_json` / `link_normalizer`,无功能影响
  - **Windows 路径分隔符**:`path-b-detect.py` 的 `--log` 参数同时支持 `/` 和 `os.sep`(`\`),避免 Windows 默认传递 `knowledge\logs.md` 时错误地走"无分隔符"分支
- **不 bump 版本号**:仍是 v0.5.5 MINOR 修订

- **问题**:`init-vault.py` 第 47-63 行 `RAW_SUBDIRS` 与 plugin 权威 `src/templates/raw-readme.md` 第 5-19 行 15 类字典存在 13 类不同名
- **修正**:`RAW_SUBDIRS` 改用 raw-readme.md 权威清单(02_芯片 / 03_通信与网络 / 04_操作系统与中间件 / 05_软件工程 / 08_AI与AI工程 / 09_域控制器 / 10_会议与活动 / 11_开发工具 / 12_法规_标准_政策 / 13_流程体系 / 14_测试与验证 / 15_算法)
- **影响**:仅 init 首次启用行为(re-run 幂等不影响已建目录);9/9 pytest 复跑全绿
- **同步**:DESIGN.md §1.1 表 + §4.1 raw 字典表全部对齐 raw-readme.md(若引用了具体目录名)
- **commit**:不 bump v0.5.5,MINOR 修订;commit 前询问用户是否更新版本号

### v0.5.5(2026-09-03)— 阶段 C-1.1 / C-1.2.1 落地补丁

- **新增 schema/ 2 个 YAML**:
  - `src/schema/frontmatter.schema.yaml`(120 行)— frontmatter 字段 SSOT,validate-frontmatter.py 通过 importlib + 相对 `Path(__file__).parent.parent/schema/` 加载
  - `src/schema/proposal.schema.yaml`(136 行)— proposal JSON 8 必填字段 SSOT,validate-proposal.py 同上加载
  - 落地原因:DESIGN.md §1.1 早列 schema/ 为 Single Source of Truth,本轮补建(原 src/schema/ 目录为空)
- **新增 scripts/ 6 个 .py(本轮 C-1.2.1 ingest 骨架)**:
  - `append-log.py`(231 行)— log.md 6 种前缀 + Q7 防护
  - `ensure-dirs.py`(171 行)— raw 15 类子目录 mkdir + 已存在幂等
  - `convert-to-md.py`(309 行)— 扩展名四路由(native / claude-native / anydoc / paddleocr)+ G10 双产物(本轮仅 stub,SKILL.md 后续替换正文)
  - `safe-mv.py`(322 行)— decision JSON 4 必填 + 4 op 语义 + G10 双文件迁移
  - `validate-frontmatter.py`(459 行)— 5 必填 + 6 轴 tag + type enum + G10 三元组 + Q9 双字段
  - `validate-proposal.py`(277 行)— v0.5.4 PATCH 5 步流程 + 字符清洗 + 截断检测 + 损坏降级
- **修改 test_no_daemon.py**:6 个新脚本加入 AST 静态扫描参数化列表(无功能变更,仅覆盖范围扩展)
- **pytest**:42 passed in 6.52s(9 no_daemon + 24 ingest skeleton + 9 no_daemon AST 新覆盖)
- **DESIGN.md 落地注脚**:
  - `safe-mv.py` overwrite op 实际依赖 `shutil.move`(Windows 行为为替换内容,非真删),与 DESIGN.md §3.6 "atomic 替换"设计意图对齐 — 备份由脚本主动写在 `temp/raw_backup_<hash>/`,Windows 上原子性由 `shutil.move` 提供;非 Windows 平台(无 atomic rename)fallback 行为需另行核验,留作 v0.6 PATCH
  - `convert-to-md.py` anydoc / paddleocr 当前仅做 importlib 探测 + 中文报错 + stub 占位,实际转换留给 SKILL.md 后续调真转换器时替换 stub 文件
- **不 bump 版本号**:仍是 v0.5.5 MINOR 修订

### v0.5.5(2026-09-03)— 初版落地

- 阶段 C 启动前对齐用户拍板:"SKILL.md 做思考 + 调度,具体 IO 尽量脚本化"
- 同步阶段 B 5 份 SKILL.md(commit 78e6a41)的"prompt 驱动"形态,标记下一轮 SKILL.md 重构方向
- 22 个 .py + `_meta.json` + README + requirements.txt + tests/test_no_daemon.py 模块边界首版固化
- 5 个数据契约(proposal JSON 8 必填 + decision JSON 4 必填 + temp/ 文件命名 + .gitignore 5 行 + frontmatter 字段映射)+ log.md 6 种前缀
- 7 项关键 PATCH 影响映射(G10 / Q5 / Q7 / Q10 / Q11 / v0.5.2 / v0.5.4)
- 测试用例 ↔ .py 函数对照表(60+ 项)
- CLAUDE.md 5 条硬约束落地(NFR-1 / NFR-3 / NFR-4 / NFR-5 / NFR-6 / NFR-7)
- SKILL.md ↔ scripts/ 重构契约(下一轮)

**兼容性**:v0.5.5 MINOR bump(新增设计文档 + 模块边界,**无 breaking change**);既有 SKILL.md 保留有效,下一轮按 §6 重构契约迁移。
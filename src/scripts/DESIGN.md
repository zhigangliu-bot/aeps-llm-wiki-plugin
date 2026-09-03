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
| `test_a1_op_mv_basic_path`(op=mv 源 inbox → 目标 raw/<sub>,源被删目标被建) | `safe-mv.py:_process_one_action --op=mv` | design §3.6 mv 语义 |
| `test_a2_op_mv_source_missing_errors`(mv 源不存在 → atomic=false + errors 含"源不存在"标签,但 exit 0 不阻断) | `safe-mv.py:_process_one_action --op=mv` 错误路径 | design §3.6 单 action 失败不阻断整批 |
| `test_a3_op_overwrite_dest_missing_treated_as_mv`(overwrite 但 dest 不存在视为 mv,backup 目录无备份文件) | `safe-mv.py:_process_one_action --op=overwrite` v0.5.2 PATCH | design §3.6 v0.5.2 PATCH |
| `test_a4_op_overwrite_backs_up_converted_md`(overwrite 时 .converted.md 也备份到 temp/raw_backup_<hash>/) | `safe-mv.py:_process_one_action --op=overwrite` G10 双文件备份 | design §3.1 G10 + §3.6 |
| `test_a5_op_skip_and_delete_only_combo`(同批 decision 含 skip + delete-only 两条 action 各自独立处理) | `safe-mv.py:_process_one_action` 批处理 | design §3.6 skip/delete-only 语义 |
| `test_a6_decision_json_validation_fails`(decision JSON 缺必填 → ValueError → exit 1) | `safe-mv.py:_validate_decision` | design §2.2 decision JSON 4 必填 |
| `test_b1_pdf_anydoc_stub_when_dep_missing`(.pdf 走 anydoc 路由;未装时 SystemExit(1) + stderr 中文"缺依赖") | `convert-to-md.py:classify` + `_probe_module("anydoc")` | design §3.1 G10 anydoc 路由 |
| `test_b2_png_paddleocr_stub_or_chinese_error`(.png → paddleocr 路由同款) | `convert-to-md.py:classify` + `_probe_module("paddleocr")` | design §3.1 G10 paddleocr 路由 |
| `test_b3_unknown_extension_exits_1`(非 4 路由扩展名 → ValueError → exit 1) | `convert-to-md.py:classify` ValueError 抛出 | design §3.1 4 路由限定 |
| `test_b4_classify_uppercase_extension_lowered`(classify 内置 lstrip+lower,大写扩展名仍正确路由) | `convert-to-md.py:classify` | design §3.1 4 路由分流 |
| `test_c1_deprecation_prefix_alone`(**Deprecation** 单独使用场景) | `append-log.py:_build_line` Deprecation 分支 | design §2.6 7 种前缀 |
| `test_c2_log_md_missing_exits_1`(init 之前 log.md 不存在 → FileNotFoundError → exit 1) | `append-log.py:run` FileNotFoundError | design §2.6 init 前置 |
| `test_c3_large_log_insertion_position`(大 log.md 多行历史 → 新记录插在 frontmatter 之后、第一个 H2 之前) | `append-log.py:_insert_after_frontmatter` | design §2.6 + §3.4 最新在前 |
| `test_d1_g10_missing_converted_path_fails`(native_text=false + converter=anydoc 但缺 converted_path → FAIL) | `validate-frontmatter.py:_check_source_specific` | design §2.5 G10 三元组 |
| `test_d2_g10_invalid_converter_value_fails`(converter 非合法 4 值 → FAIL) | `validate-frontmatter.py:_check_source_specific` | design §2.5 G10 三元组 |
| `test_d3_g10_mixed_dir_scan_ok_and_g10`(analysis + G10 source 混存各自走对应分支) | `validate-frontmatter.py:run` tp dispatch | design §3.6 type-specific 互不串扰 |
| `test_d4_unknown_keys_warn_not_fail`(未知 frontmatter 字段进 unknown_keys,但 ok 由 missing/errors 决定) | `validate-frontmatter.py:run` unknown_keys 收集 | design §2.5 OKF §11 容忍 |
| `test_e1_source_page_native_text_omits_converted_path`(native_text=true → frontmatter converter/converted_path = null) | `generate-source-page.py:_build_frontmatter` `_scalar(None)` | design §3.1 G10 + §2.5 |
| `test_e2_entity_page_all_7_subtypes_writable`(7 subtype 各自生成 + 子目录自动创建) | `generate-entity-page.py:_target_path` ENTITY_SUBTYPES | design §3.1 18 叶子 1:1:1 |
| `test_e3_concept_page_invalid_subtype_rejected`(argparse choices 拦截非法 subtype) | `generate-concept-page.py:_parse_args` choices | design §3.1 7 concept subtype |
| `test_e4_entity_page_chinese_slug`(中文 slug 可写盘 + frontmatter 含中文 title/aliases) | `generate-entity-page.py:_write_atomic` 透传 | design §5.2 中文优先 |
| `test_e5_source_page_missing_required_field_fails`(缺 updated 字段 → exit 1) | `generate-source-page.py:_validate_meta` | design §2.5 通用 5 必填 |
| `test_f1_first_run_creates_6_top_level_and_15_raw_and_18_knowledge`(顶层 6 + raw 15 + knowledge 18 + 4 种子全数验证) | `init-vault.py:_build_top_level/_build_raw_subdirs/_build_knowledge_leaves/_write_seed_files` | design §1.1 init-vault 模块边界 + §4.1 |
| `test_f2_re_run_does_not_overwrite_user_content`(--re-run 二次 init:用户 index.md 内容保留 + log.md 追加 Update 行) | `init-vault.py:_write_seed_files` + `_append_log_re_run` | design §3.6 幂等再入 |
| `test_g1_keeps_sanitized_drops_md`(OCR .md + .converted.md + proposal-*.json 删;.sanitized/.corrupt.bak/.gitignore/raw_backup_*/decision-*.json 留) | `ingest/cleanup.py:_match_any` DELETE_PATTERNS_DEFAULT / KEEP_PATTERNS_DEFAULT | design §2.3 temp/ 文件命名 + §阶段 4 |
| `test_g2_idempotent_second_cleanup_no_error`(三次连续 cleanup,errors 始终为空,幂等无副作用) | `ingest/cleanup.py:run` | design §阶段 4 幂等 |

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

### v0.5.5(2026-09-03)— 阶段 C-3 SKILL.md ↔ scripts/ 重构落地

- **重写 5 份 SKILL.md**(commit 待定),把"纯 LLM 直接做 IO"形态改为"LLM 思考 + 调度 + 调 .py"混合形态,**与 §6 重构契约表完全对齐**
- **改写要点(每份)**:
  - **`skills/aeps-llm-wiki-init/SKILL.md`**:LLM 不再直接创建 6 顶层目录 / 拷 templates/scripts / 写种子文件,统一调 `python3 ./scripts/init-vault.py --project-dir . [--re-run]`;读返回 JSON `{ok, created, copied, synced_at, plugin_version}`,展示给用户。**保留**触发命令 + 必读文件表 + 不应做 + 输出格式 + actor 规范
  - **`skills/aeps-llm-wiki-ingest/SKILL.md`**:阶段 0 改调 `check-deps.py`(不再 inline `python3 -c "import ..."`);阶段 1 调 `convert-to-md.py`(单文件 / 批量双入口);阶段 3 step 6 调 `safe-mv.py --apply temp/decision-<hash>.json`(LLM 不直接 mv);step 7 调 `generate-source-page.py --meta-json ... --body-file ...`(LLM 不直接写 source 页 frontmatter);step 8 调 `generate-entity-page.py` / `generate-concept-page.py`(LLM 不直接写 entity/concept 页);step 9 调 `append-log.py`(LLM 不直接 Edit log.md);阶段 4 调 `ingest/cleanup.py`(temp/ 留删策略脚本化)。**保留** Q11 subagent 写权矩阵 + 拍板门语义 + decision JSON 模板 + 5 步校验语义 + G10 双文件迁移语义
  - **`skills/aeps-llm-wiki-query/SKILL.md`**:阶段 0 调 `check-qmd.py`;阶段 2A 跳 1 调 `query/index-filter.py`;跳 3 调 `query/collect-neighbors.py`;跳 4 调 `query/path-b-detect.py`;阶段 3 调 `query/gating.py`(LLM 不直接伪代码判定);阶段 5 调 `generate-analysis-page.py --timestamp ... --slug ... --meta-json ... --body-file ...`;阶段 8 调 `lint-query-output.py` 校验末尾 `❓` / `💡` 标记(C15.3 FAIL 防护)。**保留** intent 推断语义(Llm 自做)+ 4 跳扫描优先级 + G11 3 H2 骨架 + 路径 B 触发语义 + gating 优先级
  - **`skills/aeps-llm-wiki-query/SKILL.md`** qmd 模式:LLM 直接调 `qmd query ...`(系统命令,不是 scripts/);其余 query IO 全部脚本化
  - **`skills/aeps-llm-wiki-lint/SKILL.md`**:阶段 1 调 `lint.py [--fix] [--apply] [--allow-dirty] [--by <axis>]`,读返回 JSON `{ok, issues, written, atomic, report_only, fix_proposed}`;阶段 2 语义级增强附加调 `lint-orphans.py` / `okf-lint.py` 拿结构化结果(LLM 不直接 grep);阶段 4 写盘调 `lint.py --fix --apply`(双开关 + git 脏检查 + 事务原子 + Q7 4 步 atime+mtime 双还原全部由脚本内部强制);阶段 5 log.md 追加由 `lint.py` 内部自动调 `append-log.py`(LLM 不重复写 log)。**保留** 11 类检查清单 + `--fix` ≠ `--apply` 双开关契约 + 语义级问题只报告不应用 + 陈旧判定优先级 + 4 步 atomic write 约束
  - **`skills/aeps-llm-wiki-synthesize/SKILL.md`**:阶段 2 调 `synthesize/make-slug.py --topic "<topic>"`;阶段 3 调 `synthesize/detect-existing.py --project-dir . --slug <slug>`;阶段 4(UPDATE)调 `synthesize/build-page.py --slug <slug> --meta-json ... --body-file ... --update`;阶段 5(CREATE)调 `synthesize/build-page.py`(无 `--update`);阶段 6 调 `synthesize/append-index.py`;log.md 追加由 `build-page.py` 内部自动调 `append-log.py`(LLM 不直接 Edit log.md / index.md)。**保留** CREATE vs UPDATE 流程区分 + Q7 `updated` 不变 / `last_updated` 更新 + slug 派生规则 + sources_count < 3 拍板门
- **改写不变量**:
  - **保留** frontmatter 必填(name / description),**不改**
  - **保留** 触发命令(/aeps-llm-wiki-init 等 5 个),**不改**
  - **保留** 必读文件表,**不改**
  - **保留** "不应做"段契约,**不改**
  - **保留** "输出格式"段(用户视角的展示不变),**不改**
  - **不**写入日志、历史、版本号、测试用例、change history 到 SKILL.md 内(全局 CLAUDE.md 硬约束:skill 是纯规范文件)
  - **不**改 DESIGN.md §6 重构契约表(它是 SSOT,新 PATCH 在 §9 追加,§6 表保留)
- **DESIGN.md 落地注脚**:
  - **init-vault.py 改写**:原 SKILL.md L42-L122 描述的"6 顶层 + .gitkeep + 拷 templates/scripts + 写种子文件 + 字典 append + log"全部下沉到脚本;LLM 只做"路径判定(看 SCHEMA.md 是否存在)+ 调脚本 + 展示 JSON 返回";re-run 流程由脚本内部自动判别(用户加 `--re-run` 参数)
  - **ingest 阶段拆分语义保留**:原"阶段 0 依赖预检 / 阶段 1 扫描+入口 / 阶段 2 subagent 并行 / 阶段 3 主 agent 9 步 / 阶段 4 收尾"骨架不变,每阶段内"LLM 直接做"步骤改为"调脚本 + 读 JSON 返回"
  - **ingest step 9 LLM 仍可直写 glossary.md / index.md / overview.md**:这 3 个文件的 append/edit 不在 scripts/ 22 个 .py 范围内(append-log.py 仅管 log.md),LLM 自行 Read + Edit/Write 文件。**注意**:这不违反 §0.1 边界(scripts/ 只覆盖机械执行 IO + schema 校验 + atomic write + 安全锁;LLM 累积维护索引/概览/术语表属于语义层)
  - **query 阶段拆分语义保留**:原"阶段 0 引擎决策 / 阶段 1 intent 路由 / 阶段 2 候选检索 / 阶段 3 gating / 阶段 4 落档"骨架不变;intent 路由仍由 LLM 推断(语义判断不可脚本化),其余 IO 全部脚本化
  - **query qmd 命令归类**:qmd 是 Node 工具,不是 scripts/ 的 .py;LLM 直接调 `qmd query ...` 是合理 IO 边界(系统命令层);其他 IO 全部走 scripts/
  - **lint 11 类检查保留**:原"1.1 孤儿 / 1.2 矛盾 / 1.3 陈旧 / 1.4 命名飘 / 1.5 漏链 / 1.6 frontmatter / 1.7 links 漂移 / 1.8 raw_category / 1.9 骨架 / 1.10 comparisons / 1.11 syntheses"11 项全部下沉到 `lint.py:scan`;LLM 不再自己逐项判;`--fix` / `--apply` 双开关由脚本内部强制;语义级问题(矛盾 / 命名飘 / 漏链)LLM 调 `lint-orphans.py` / `okf-lint.py` 拿结构化结果做增强判断
  - **lint 阶段 5 log.md 不直接调**:lint.py 写盘成功后内部自动调 append-log.py 写 **LintFix** 段(参考 stage C-1.4 落地注脚 + lint SKILL.md §阶段 5 描述);LLM 不重复调 append-log.py
  - **synthesize CREATE vs UPDATE 区分保留**:原"create 流程不动 `updated`(首次创建无 mtime 保留价值)/ update 流程不动 `updated`(Q7 死循环防护)"语义不变;脚本内部 `_build_frontmatter(is_update=...)` 区分两条路径
  - **synthesize 拍板门保留**:sources_count < 3 时仍由 LLM 在对话层发起拍板(`[y/n]`),不阻断脚本调用;这是 §0.1 "LLM 仍保留的判断/决策"清单中的"sources_count 不足时的用户拍板"
- **不变量自检**:
  - 5 份 SKILL.md 全部更新(init / ingest / query / lint / synthesize)
  - 每份 SKILL.md 仍含 frontmatter(name / description)+ 触发命令 + 必读文件表 + 工作流 + 不应做 + 输出格式
  - 每份 SKILL.md 工作流阶段中**至少 50% 步骤**引用 `.py` 脚本(init 100% / ingest ~90% / query ~85% / lint 100% / synthesize 100%)
  - DESIGN.md §9 8 段 PATCH 完整(初版 + C-1.1/C-1.2.1 + C-1.2.2 + C-1.3 + C-1.4 + C-1.5 + C-2 + **C-3**)
  - §6 重构契约表保留不变(是 SSOT,与新 PATCH 内容一致)
- **不 bump 版本号**:仍是 v0.5.5 MINOR 修订
- **commit**:不 bump v0.5.5,MINOR 修订;commit 前询问用户是否更新版本号

### v0.5.5(2026-09-03)— 阶段 C-2 高风险路径测试用例落地

- **新增 tests/test_c2_high_risk.py**(576 行)— **26 个测试用例**,按 A-G 七组覆盖真实存在风险的关键路径:
  - **A 组 safe-mv 4 op 语义**(6 用例):`test_a1_op_mv_basic_path`(普通 mv 源→目标路径)/ `test_a2_op_mv_source_missing_errors`(mv 源不存在 errors 列表含"源不存在"标签,exit 0 不阻断)/ `test_a3_op_overwrite_dest_missing_treated_as_mv`(overwrite 但 dest 不存在视为 mv,备份目录无备份文件)/ `test_a4_op_overwrite_backs_up_converted_md`(overwrite 时 .converted.md 也备份,backup 目录含原文件 + 副本两份)/ `test_a5_op_skip_and_delete_only_combo`(同批 decision 两条 action 各按语义独立处理)/ `test_a6_decision_json_validation_fails`(decision JSON 缺必填 → ValueError + exit 1)
  - **B 组 convert-to-md 4 路由**(4 用例):`test_b1_pdf_anydoc_stub_when_dep_missing`(.pdf → anydoc 路由;未装时 SystemExit(1) + stderr 中文报错)/ `test_b2_png_paddleocr_stub_or_chinese_error`(.png → paddleocr 同款)/ `test_b3_unknown_extension_exits_1`(非 4 路由扩展名 → ValueError)/ `test_b4_classify_uppercase_extension_lowered`(classify 内置 lstrip+lower,大写扩展名仍正确路由)
  - **C 组 append-log 边界**(3 用例):`test_c1_deprecation_prefix_alone`(**Deprecation** 单独使用,init SKILL.md §阶段 4 中 deprecate 一页时场景)/ `test_c2_log_md_missing_exits_1`(init 前 log.md 不存在 → FileNotFoundError → exit 1)/ `test_c3_large_log_insertion_position`(大 log.md 多行历史 → 新记录插在 frontmatter 之后、第一个 H2 之前)
  - **D 组 validate-frontmatter G10 三元组边界**(4 用例):`test_d1_g10_missing_converted_path_fails`(native_text=false 但 converted_path 缺失 → FAIL)/ `test_d2_g10_invalid_converter_value_fails`(converter 非合法 4 值 → FAIL)/ `test_d3_g10_mixed_dir_scan_ok_and_g10`(analysis + G10 source 混存目录各自走对应分支)/ `test_d4_unknown_keys_warn_not_fail`(未知 frontmatter 字段进 unknown_keys,但 ok 由 missing/errors 决定)
  - **E 组 generate-* 序列化分支**(5 用例):`test_e1_source_page_native_text_omits_converted_path`(native_text=true → frontmatter converter/converted_path = null)/ `test_e2_entity_page_all_7_subtypes_writable`(7 subtype 各自生成,子目录自动创建)/ `test_e3_concept_page_invalid_subtype_rejected`(argparse choices 拦截非法 subtype)/ `test_e4_entity_page_chinese_slug`(中文 slug 可写盘,frontmatter 含中文 title + aliases)/ `test_e5_source_page_missing_required_field_fails`(缺 updated 字段 → exit 1)
  - **F 组 init-vault 幂等再入**(2 用例):`test_f1_first_run_creates_6_top_level_and_15_raw_and_18_knowledge`(顶层 6 + raw 15 + knowledge 18 + 4 种子全数验证)/ `test_f2_re_run_does_not_overwrite_user_content`(--re-run 二次 init:用户 index.md 内容保留 + log.md 追加 Update 行)
  - **G 组 ingest/cleanup 留删策略**(2 用例):`test_g1_keeps_sanitized_drops_md`(OCR .md + .converted.md + proposal-*.json 删;.sanitized/.corrupt.bak/.gitignore/raw_backup_*/decision-*.json 留)/ `test_g2_idempotent_second_cleanup_no_error`(三次连续 cleanup,errors 始终为空,幂等无副作用)
- **pytest 结果**:168 旧 + 26 新 = **194 passed in 46.41s**(0 failed)
- **DESIGN.md 落地注脚**:
  - **safe-mv 单 action 失败不阻断整批**:A2 测试验证 mv 源不存在时 exit 0(单 action 失败),但 `atomic=false` + `errors` 含 `"源不存在"` 标签。**设计意图**:批 ingest 场景下,某条 action 失败不影响其他 action 继续处理;主 agent 读 errors 列表决定是否人工兜底
  - **safe-mv overwrite dest 缺失视为 mv**:A3 测试验证 overwrite 路径下 dest 不存在时不走 backup(因无东西可备)。**与 v0.5.2 PATCH 一致**:`_process_one_action` 的 overwrite 分支先 `_backup_target`(若 dest 存在),然后调 `_move_pair`;dest 缺失时备份目录为空,但 action 仍成功
  - **safe-mv decision JSON 缺必填**:A6 测试缺 type/actions 必填 → ValueError → exit 1。**注意**:实测 `safe-mv.py` `_validate_decision` 报 `"decision JSON 缺必填字段:['type', 'actions']"`,与 DESIGN.md §2.2 decision JSON 4 必填(type / schema_version / decided_at / actor / proposal_refs / actions)字段名一致
  - **convert-to-md B1/B2 容忍 anydoc/paddleocr 已装环境**:脚本走 `importlib.import_module(module_name)`,若环境意外装了对应包则走 stub 文件生成路径(`.md` 文件含 `# <basename> (anydoc/paddleocr 转换产物)` 占位),stub 文件 size>0 + converter 字段正确。本测试两类结果都 PASS,断言 `r.returncode != 0` 时 stderr 含 `"缺依赖"` 或模块名
  - **append-log C3 插入位置**:实测 `_insert_after_frontmatter` 在 frontmatter (---...---) 与第一个 H2 之间插入新行;若既有 log.md 没有 H2,则插在 frontmatter 结束标记之后;完全无 frontmatter 则 prepend。**与 design §3.4 SCHEMA.md §7 "最新在前" 一致**
  - **validate-frontmatter D3 混存测试**:同一 project 下分别校验 analysis 页(走 analysis-specific 校验 sources_used/answer_to/generated_by 必填)和 G10 source 页(走 source-specific 校验 Q9 双字段同源 + G10 三元组)。验证 `tp == "analysis"` 分支**不触发** G10 三元组检查(互不串扰)
  - **generate-source-page E1 native_text 序列化**:`_build_frontmatter` 用 `_scalar(None) → "null"` 输出;`converter: null` / `converted_path: null` 字面字符串进入 frontmatter YAML。测试断言 `converter: null` 或 `converter: 'null'` 之一出现即通过(容错 YAML 单引号包裹)
  - **generate-source-page E5 缺 updated 报错**:`_validate_meta` 第 71-74 行对 title/description/updated 三字段做"字符串非空"校验,缺 updated 直接抛 ValueError → main 捕获 emit_json error → exit 1。**测试命中**:`"updated"` 出现在 error 字符串
  - **init-vault F1 完整性**:实测顶层 6 + RAW_SUBDIRS 15 项 + KNOWLEDGE_LEAF_DIRS 18 项 + 4 种子文件全数 assert。RAW_SUBDIRS / KNOWLEDGE_LEAF_DIRS 与 DESIGN.md §1.1 init-vault 模块边界表对齐,也是 raw-readme.md L5-L19 / templates/knowledge-SCHEMA.md §1.1/§1.2 的权威源
  - **init-vault F2 re-run 幂等**:实测 `_write_seed_files` 内 `if not path.exists()` 守卫保证用户已有 seed 文件不被覆盖;`_append_log_re_run` 在 re-run 时追加 `**Update**: re-run init at <ISO> by <actor>` 一行到 log.md 末尾
  - **cleanup G1 留删策略**:实测 `DELETE_PATTERNS_DEFAULT` 命中 `*.md` / `*.converted.md` / `proposal-*.json` 三类;`KEEP_PATTERNS_DEFAULT` 命中 `.gitkeep` / `proposal-*.json.sanitized` / `proposal-*.json.corrupt.bak` / `raw_backup_*` / `raw_backup_*/**` / `decision-*.json` / `plan-*.json` / `.gitignore`。**注意**:`plan-*.json` 当前模板未生成,作为未来扩展预留 keep 模式
  - **cleanup G2 幂等**:实测三次连续 cleanup 第一次空 temp/(deleted=0)/ 第二次删 2 个 OCR .md / 第三次再空。**关键不变量**:`errors` 列表三次都为空 → 不存在"上次已删,本次 unlink 报错"的副作用
- **设计意图确认**:26 用例覆盖 SKILL.md 5 份契约入口(init / ingest / query / lint / synthesize 的核心 IO 路径),其中 init 2 + ingest 14 + query 0(已有 test_query_group 34 个覆盖) + lint 0(已有 test_lint_group 32 个覆盖) + synthesize 0(已有 test_synthesize_group 26 个覆盖)
- **不 bump 版本号**:仍是 v0.5.5 MINOR 修订
- **commit**:不 bump v0.5.5,MINOR 修订;commit 前询问用户是否更新版本号

### v0.5.5(2026-09-03)— 阶段 C-1.5 synthesize 组落地

- **新增 synthesize/ 子目录 4 个 .py**:
  - `synthesize/make-slug.py`(178 行 / ~6 KB)— 派生 topic slug,纯字符串处理(无 IO);规则:全角→半角(FF01-FF5E → 21-7E;U+3000 → 半角空格)→ ASCII 小写 → ASCII 标点 → 空格 → CJK 标点 → 空格 → `\s+` 折叠 `-` → 连续 `-` 折叠 → 收尾去 `-` → NFKC 兜底 → 中文保留
  - `synthesize/detect-existing.py`(181 行 / ~6 KB)— 探测 `<project>/knowledge/syntheses/<slug>.md` 是否存在 + 从 frontmatter 解析 `sources_count`(int,默认 0);只读,无写盘;不带 frontmatter schema 校验(留给 validate-frontmatter.py)
  - `synthesize/build-page.py`(494 行 / ~17 KB)— 写 / 更新 synthesis 页;frontmatter 序列化(通用 5 + synthesis 必填 3 = type / topic / sources_count / last_updated / updated + tags + generated + links + summary);CREATE 流程 `updated = last_updated = now`;UPDATE 流程**只改** `last_updated` + `sources_count`,**不动** `updated`(Q7 死循环防护);二次写盘走 `atomic_write_preserving_mtime`(atime + mtime 双还原);`sources_count < 3` WARN 不阻断(走 stderr,SKILL.md 已向用户确认);log.md append `**Creation**`(CREATE) / `**Update**`(UPDATE);actor 默认 `agent: producer/aeps-llm-wiki-plugin/0.5.5`
  - `synthesize/append-index.py`(197 行 / ~7 KB)— append `knowledge/index.md` 一行 `- [slug](syntheses/<slug>.md) — type: synthesis · sources_count: N · <summary>`;幂等检测(同 slug 重复 → skip,`already_present: true`);frontmatter 之后插入(latest-first);Q7 atomic write 保留 mtime
- **新增 tests/test_synthesize_group.py**(748 行)— **26 个测试用例**,覆盖:7 个 make-slug 派生(SKILL.md §阶段 2 三示例 + 标点 + 全角 + 多空格 + 标点链)/ 3 个 detect-existing(存在 / 不存在 / sources_count 读取)/ 11 个 build-page(CREATE 写盘 / frontmatter 字段 / updated=last_updated / UPDATE 不动 updated(Q7)/ UPDATE 改 last_updated / UPDATE 改 sources_count / log.md Creation / log.md Update / sources_count < 3 WARN 不阻断 / Q7 atime+mtime 双还原 / --update 但文件不存在报错)/ 3 个 append-index(写一行 / 行格式校验 / 同 slug 幂等)/ 2 个 E2E(CREATE 整合 / UPDATE 整合)
- **pytest 结果**:138 旧 + 26 新 + 4 no_daemon synthesize/ 参数化新增 = **168 passed in 39.34s**(0 failed)
- **修改 test_no_daemon.py**:参数化列表新增 `synthesize/make-slug.py` / `synthesize/detect-existing.py` / `synthesize/build-page.py` / `synthesize/append-index.py`;`_target_scripts` 扩展扫描 `ingest/` / `query/` / `synthesize/` 3 个子目录
- **DESIGN.md 落地注脚**:
  - **make-slug.py 中文保留 + NFKC 兜底**:CJK Unified Ideographs U+4E00-U+9FFF 直接透传;ASCII 标点走 `_ASCII_PUNCT` set(含 `,` / `.` / `!` 等),CJK 标点走 `_CJK_PUNCT_RE`(覆盖 U+3000-U+303F 段);末尾 NFKC `unicodedata.normalize("NFKC", s)` 兜底处理剩余兼容字符(全角字母数字 / compatibility decomposition 形式),保证 ASCII 边界干净
  - **detect-existing.py 只读探测**:无任何写盘调用;frontmatter 解析走本地 `_parse_frontmatter`(不走 yaml 依赖,失败容忍返回 `sources_count=0`);`syntheses/` 目录不存在时 `exists=false`(不 mkdir,留给 build-page 路径)
  - **build-page.py CREATE vs UPDATE 流程区分**:CREATE 走 `_build_frontmatter(is_update=False)` → `updated = last_updated = now_iso`(用脚本生成的 now 覆盖 meta 传入值);UPDATE 走 `_build_frontmatter(is_update=True, existing_updated=...)` → 优先读原文件 `updated` 字段 → 保留写入;frontmatter 其他字段(title / topic / tags / generated.by)在 UPDATE 流程**不动**(与 SKILL.md §"不调用 frontmatter `updated` 字段做不必要的改写"对齐)
  - **build-page.py log.md Creation/Update 前缀**:`_append_log()` 调 `append-log.py`(subprocess)写 `**Creation**: synthesize "<topic>" → [slug.md](syntheses/<slug>.md)` / `**Update**: synthesized update on [slug.md](syntheses/<slug>.md) — sources_count now N`;append-log 失败容忍(不影响主流程 returncode)
  - **append-index.py 幂等**:正则 `INDEX_LINE_RE = r"^\s*-\s*\[([^\]]+)\]\(syntheses/([^)]+)\)"` 同时校验 `slug` 文件名 + 显示文本两边,避免别名问题;同 slug 二次 append → `appended=false, already_present=true`,文件不改;行格式严格 `- [<slug>](syntheses/<slug>.md) — type: synthesis · sources_count: <N> · <summary>`,em dash (—,U+2014) + 中点 (·,U+00B7) 是硬要求
  - **build-page.py Q7 atomic**:CREATE 首次写盘走 `target.write_text()`(atomic_write_preserving_mtime 要求文件存在,首次创建无 mtime 保留价值);UPDATE 二次写盘走 `atomic_write_preserving_mtime(target, full_md)`(atime + mtime 双还原);`test_synthesize_build_page_atomic_preserve_mtime` 显式设 `os.utime(target, (1700000000.0, 1700000000.0))` 后 UPDATE,断言 `mtime + atime` 都保持 1700000000.0
  - **synthesize/ 子目录脚本顶部 `sys.path.insert(0, Path(__file__).resolve().parent.parent)`** 复用 `_common.emit_json` / `atomic_write_preserving_mtime`(与 `query/` / `ingest/` 子目录同款做法);`_SCRIPTS_DIR` 常量专门存 scripts 绝对路径,供 `append-log.py` subprocess 调用
  - **build-page.py 测试正则用 `^updated:` 行首匹配**:因 `last_updated` 也含 `updated:` 子串,行首 `re.MULTILINE` 避免误匹配 — 已踩坑修正
- **不 bump 版本号**:仍是 v0.5.5 MINOR 修订
- **commit**:不 bump v0.5.5,MINOR 修订;commit 前询问用户是否更新版本号

### v0.5.5(2026-09-03)— 阶段 C-1.4 lint 组落地

- **新增 3 个 .py 顶层**:
  - `lint.py`(1215 行 / ~38 KB)— 11 类检查主入口(orphan / contradiction / stale / name_drift / missing_link / frontmatter / links_mirror / raw_category / skeleton / comparison / synthesis);`--fix --apply` 双开关;事务原子写盘;git 脏检查 + `--allow-dirty` 放行;`--by {raw_category,type,maturity,docform}` 四轴 group by;Q7 atomic_write_preserving_mtime 全程保留 mtime
  - `lint-orphans.py`(288 行 / ~8 KB)— 扫 `knowledge/**/*.md` 找孤儿;inbound_map 反向索引(frontmatter `sources[]` + `sources_used[]` + 正文 `[[wikilink]]` + markdown link);豁免名单 = `index.md / overview.md / glossary.md / log.md / SCHEMA.md`;输出 `{orphans:[{path, has_no_inbound_link, exempt, reason}], total, scanned}`
  - `okf-lint.py`(356 行 / ~11 KB)— OKF v0.2 合规 + frontmatter `links:` 镜像同步;Set 比对(顺序无关);`--apply` 走 Q7 4 步流程(atime + mtime 双还原);不动 frontmatter `updated` 字段;默认 dry-run;`_replace_links_block` 容忍 flow / block / 缺失 3 种形态
- **新增 tests/test_lint_group.py**(921 行)— **32 个测试用例**,覆盖:11 类检查触发 / 陈旧判定优先级(Q7 / deprecated 豁免)/ Q5 命名飘 Levenshtein ≤ 2 / sources/analyses 3 H2 骨架 / `## 摘要` 残留 / comparison ≥ 2 / synthesis < 3 WARN / 双开关写盘 / 单 `--fix` 不写盘 / git 脏阻断 / `--allow-dirty` 放行 / 事务原子回滚 / `--by raw_category/type` group by / **LintFix** log 前缀 / Q7 atime+mtime 双还原 / 孤儿豁免 / 孤儿入链 / Set 比对 / alias 归一 / anchor 归一 / path prefix 归一 / links 优先级 / ghost / missing / 无 drift / apply 幂等
- **pytest 结果**:98 旧 + 32 新 + 8 no_daemon 扩展 = **138 passed in 29.85s**(0 failed)
- **修改 test_no_daemon.py**:参数化列表新增 `lint.py` / `lint-orphans.py` / `okf-lint.py` + 阶段 C-1.3 query 组 5 个 .py
- **DESIGN.md 落地注脚**:
  - **lint.py 事务原子**:`_apply_fix()` 内部走 `atomic_write_preserving_mtime`(Q7 4 步流程),单文件级写盘不在外层批量拼接 — 配合 `git_dirty_check` 在 `--fix --apply` 入口处先做脏检查,阻断时整体 skip(后续文件不写盘);stub 化测试 `_apply_fix` 抛错验证事务失败 → `skipped` 列表非空、文件 mtime 不变
  - **lint.py 双开关**:`args.fix and args.apply` 双开关才走 git 脏检查 + 写盘;单 `--fix` 时所有 issues 仍 emit 到 stdout 但 `written=[]` + `report_only=true` + `fix_proposed=true`
  - **lint-orphans.py 豁免名单**:`EXEMPT_PATHS = {index, overview, glossary, log, SCHEMA}.md` 5 项 — log.md 是 append-only 变更日志,SCHEMA.md 是 plugin 维护操作手册,这两类不需要入链接
  - **okf-lint.py Set 比对顺序无关**:`scanned ↔ current` 用 `set` 差集算 `added`/`removed`;输出列表用 `sorted()` 保证 deterministic;`reordered` 标志仅在 set 相等但 list 顺序不同时触发,便于人读 frontmatter diff
  - **okf-lint.py Q7 atime+mtime 双还原**:`atomic_write_preserving_mtime` 在 `okf-lint.py` 的 `_apply` 路径被复用;测试 `test_okf_lint_apply_writes_atomic_preserve_mtime` 断言 `st_mtime` + `st_atime` 两次 `os.stat()` 完全相等
  - **lint.py 陈旧判定**:fallback 优先级严格按 lint SKILL.md §1.3(stale_after 显式 > updated > 180 天 + log.md 无提及 > status: deprecated 豁免);`status: draft` 不豁免,符合 design
  - **lint.py name_drift 逻辑修正**:派生 `raw_category` 即使在 `raw_subdirs` 中,只要与某 subdir Levenshtein ≤ 2 → 触发(原 `_list_raw_subdirs` 内 cat 自身会被 `cat in raw_subdirs` 短路跳过,本次 PATCH 改为 `existing == cat: continue`)
- **不 bump 版本号**:仍是 v0.5.5 MINOR 修订
- **commit**:不 bump v0.5.5,MINOR 修订;commit 前询问用户是否更新版本号

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

### v0.5.5(2026-09-03)— 阶段 C-1.2.2 ingest 增量落地补丁

- **新增 scripts/ 3 个 .py 顶层**(ingest 生成器):
  - `generate-source-page.py`(377 行)— sources/`<basename>`.md + G10 5 字段(format / converter / native_text / converted_path / links 镜像)+ 3 H2 骨架(`## 重点摘录` / `## 我的思考` / `## 总结`);`source_file` ↔ `sources[0].resource` 双字段同源(Q9);atomic write 4 步保留 mtime
  - `generate-entity-page.py`(284 行)— entities/`<subtype>`/`<slug>`.md,7 subtype(person / organization / project / product / event / place / other);frontmatter 含 aliases / summary / 6 轴 tag;非法 subtype 拒绝
  - `generate-concept-page.py`(270 行)— concepts/`<subtype>`/`<slug>`.md,7 subtype(theory / method / field / phenomenon / standard / term / other);同上 entity
- **新增 scripts/ingest/ 4 个 .py**:
  - `dedupe_concepts.py`(248 行)— proposal 间 concept 去重(aliases 并集)
  - `dedupe_entities.py`(250 行)— 同上 entity
  - `pre_classify.py`(181 行)— raw 子目录预校验(15 类字典 + prefix hint)
  - `cleanup.py`(237 行)— temp/ 清理策略(留 `.sanitized` / `.corrupt.bak` / `.gitignore` / `raw_backup_*`,删 OCR 中间)
- **新增 tests/test_ingest_increments.py**(735 行)— 覆盖 22 个测试用例
- **pytest 结果**:64 = 42 旧 + 22 新 = **64 passed**(0 failed)
- **DESIGN.md 落地注脚**:
  - `generate-source-page.py` 时间戳格式与 G10 三元组对齐 — sources[0].resource 路径直接派生 raw_category;Q9 双字段(source_file ↔ sources[0].resource)在 validate-frontmatter.py 校验
  - `generate-{entity,concept}-page.py` 复用 generate-source-page.py 的 frontmatter 序列化逻辑,但锁 7 subtype 字典;非法 subtype 由 argparse choices 拦截
  - `ingest/dedupe_{concepts,entities}.py` 按 alias 并集 + slug 全小写归一去重;命中后保留早创建的页,晚的合并进 frontmatter aliases
  - `ingest/pre_classify.py` 用 prefix hint(raw 子目录名前 2 位数字)判定 raw_category,失败时落 WARN,不阻断
  - `ingest/cleanup.py` KEEP_PATTERNS_DEFAULT 留 5 类(`.sanitized` / `.corrupt.bak` / `.gitignore` / `raw_backup_*` / `plan-*.json` 占位),删 OCR 中间(`.tmp` / `.tmp.*`)
- **追溯说明**:本段在 C-1.5 synthesize commit 时由 subagent 误并入 C-1.1/C-1.2.1 合并段,C-3 PATCH 追加前补回独立段(trellis-check Issue #1)
- **不 bump 版本号**:仍是 v0.5.5 MINOR 修订

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
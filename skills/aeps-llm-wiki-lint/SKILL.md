---
name: aeps-llm-wiki-lint
description: 扫 knowledge/**/*.md,11 类检查(孤儿 / 矛盾 / 陈旧 / 命名飘 / 漏链 / frontmatter / links: 漂移 / raw_category / 正文骨架 / comparisons / syntheses)。默认只报告;--fix 提案确定性结构修复;--fix --apply 双开关才写盘(Q7 死循环防护 + git 脏状态检查 + 事务原子写入)。
---

# aeps-llm-wiki-lint

> **触发**:`/aeps-llm-wiki-lint [--fix] [--apply] [--allow-dirty] [--by <axis>] [--project-dir <path>]`
> **权威设计**:`src/prd.md §4.4` + `src/design.md §4.4` + `§5.4 安全锁` + `src/scripts/DESIGN.md §1.1 lint/`
> **对应实现阶段**:plugin v0.5.5 阶段 B(本文档) + 阶段 C(lint.py / lint-orphans.py / okf-lint.py 全部落地)
> **关键 PATCH**:Q7 死循环防护 v0.5.3(4 步流程) + Q6 wikilink 一等公民 + v0.3.2 安全锁(双开关 + 事务 + git 兜底) + G11 lint C15.1-C15.4
> **核心原则**:LLM 只做思考 + 调度;11 类检查 / 提案 / 双开关写盘全部交 `lint.py`(详见 `scripts/DESIGN.md §0.1`)

## 必读文件

启动 skill 时,**先 Read**:

| 优先级 | 路径 | 用途 |
|---|---|---|
| 1 | `<project>/knowledge/SCHEMA.md` | 用户操作手册(必读) |
| 2 | `<project>/templates/concept-entities-readme.md` | 子类 ↔ 目录字典 |
| 3 | `<project>/templates/tag-template.md` | 六轴 tag 词表 |
| 4 | `<project>/raw/raw/README.md` | 15 类字典(派生 raw_category) |
| 5 | `<project>/knowledge/log.md` | 陈旧判定 + LintFix 历史 |
| 6 | `aeps-llm-wiki-plugin/src/schema/frontmatter.schema.yaml`(若已落地) | frontmatter schema |
| 7 | `aeps-llm-wiki-plugin/src/schema/proposal.schema.yaml`(若已落地) | proposal JSON schema |
| 8 | `aeps-llm-wiki-plugin/src/scripts/README.md` | scripts/ 约定 |

## 工作流

### 阶段 0:模式判定(LLM 根据参数分支)

| 参数组合 | 行为 |
|---|---|
| (无参数) | 调 `lint.py --project-dir .` → 只**报告** |
| `--fix` | 调 `lint.py --project-dir . --fix` → 输出**确定性结构修复提案**(默认 dry-run,不写盘) |
| `--fix --apply` | 调 `lint.py --project-dir . --fix --apply` → **写盘**(必须双开关) |
| `--fix --apply --allow-dirty` | 调 `lint.py --project-dir . --fix --apply --allow-dirty` → git 脏状态下强制写盘 |
| `--by raw_category` / `--by type` / `--by maturity` / `--by docform` | 调 `lint.py --project-dir . --by <axis>` → group by 报告模式 |

`--fix` ≠ `--apply`:**单开关 `--fix` 不写盘**,仅输出提案(diff)。LLM **不**自行判定写盘开关;参数透传给 `lint.py`。

### 阶段 1:扫 `knowledge/**/*.md` —— 11 类检查(LLM 调 lint.py)

```bash
# 默认只报告
python3 ./scripts/lint.py --project-dir .
# Bash timeout: 60000

# 提案(dry-run)
python3 ./scripts/lint.py --project-dir . --fix
# Bash timeout: 60000

# 双开关写盘
python3 ./scripts/lint.py --project-dir . --fix --apply
# Bash timeout: 300000

# 脏状态下强制
python3 ./scripts/lint.py --project-dir . --fix --apply --allow-dirty
# Bash timeout: 300000

# group by
python3 ./scripts/lint.py --project-dir . --by raw_category
# Bash timeout: 60000
```

**返回 JSON 形态**:

```json
{
  "ok": true,
  "issues": [
    {"file": "knowledge/sources/a.md", "rule": "frontmatter-tags", "severity": "FAIL", "detail": "tags string → list"},
    {"file": "knowledge/sources/b.md", "rule": "links-mirror-sync", "severity": "WARN", "detail": "3 added, 2 removed, 1 reordered"},
    {"file": "knowledge/analyses/c.md", "rule": "lint-C15.1", "severity": "FAIL", "detail": "missing ## 方案推演"}
  ],
  "written": ["knowledge/sources/a.md", "knowledge/sources/b.md"],
  "atomic": true,
  "report_only": false,
  "fix_proposed": true
}
```

**11 类检查**(脚本内部):

| 编号 | 检查项 | 严重度 | 行为 |
|---|---|---|---|
| 1.1 | 孤儿页(无入链接) | FAIL | 报告 |
| 1.2 | 矛盾 | WARN | 仅报告,`--fix` 不应用 |
| 1.3 | 陈旧页(stale_after / updated > 180d / deprecated 豁免) | WARN | 报告 |
| 1.4 | LLM 命名飘(Levenshtein ≤ 2) | WARN | `--fix` 输出提案,LLM 拍板 git mv |
| 1.5 | 漏链(LLM 语义) | WARN | 仅报告 |
| 1.6 | frontmatter 不合规(必填 / 类型 / 裸 tag) | FAIL | `--fix --apply` 自动补 |
| 1.7 | frontmatter `links:` 漂移(Set 比对 + Normalizer) | WARN | `--fix --apply` 自动同步 |
| 1.8 | raw_category 派生失败(sources[0].resource 不在 raw/) | FAIL | 报告 |
| 1.9 | 正文骨架不合规(sources / analyses 缺 3 H2) | FAIL | `--fix --apply` 追加占位 H2 |
| 1.10 | `comparisons/*.md` 缺 `sources:` 字段(≥2 wikilink) | FAIL | 报告 |
| 1.11 | `syntheses/*.md` 缺 `sources_count` 或 <3 | WARN | 报告 |

### 阶段 2:语义级增强(LLM 视需求附加调 lint-orphans.py / okf-lint.py)

若用户要"补漏链 / 矛盾分析 / 命名飘合并"等语义级判断,LLM 附加调:

```bash
# 找孤儿页(豁免 index/overview/glossary/log/SCHEMA)
python3 ./scripts/lint-orphans.py --project-dir .
# Bash timeout: 30000
```

**返回 JSON**:

```json
{
  "orphans": [
    {"path": "knowledge/concepts/theory/foo.md", "has_no_inbound_link": true, "exempt": false, "reason": "no inbound references"}
  ],
  "total": 1,
  "scanned": 123
}
```

```bash
# OKF v0.2 合规 + frontmatter `links:` 漂移(详细 diff)
python3 ./scripts/okf-lint.py --file knowledge/<path>
# Bash timeout: 30000

# 同步 links: 字段(默认 dry-run)
python3 ./scripts/okf-lint.py --file knowledge/<path> --apply
# Bash timeout: 30000
```

**返回 JSON**:

```json
{
  "ok": true,
  "drift": true,
  "scanned": 5,
  "current": 3,
  "added": 2,
  "removed": 0,
  "reordered": 1
}
```

LLM 拿这些**结构化结果**做语义增强判断(命名飘 / 漏链 / 矛盾候选);**不**自行 grep / 解析 frontmatter。

### 阶段 3:提案 + 用户拍板(LLM 在对话层)

LLM 读 §阶段 1 返回的 `issues` 列表,**只**展示:

- **确定性结构修复**(safe,`--fix --apply` 可自动应用):
  - frontmatter 必填字段缺失补占位
  - frontmatter 类型错位(string → list)
  - `## 摘要` / `## Summary` 残留合并到 `summary`
  - sources/analyses 缺 3 H2 追加占位
  - `links:` ↔ wikilink 漂移同步
  - `sources_used` 缺自动填
- **语义级建议**(unsafe,LLM 仅报告,**不**自动应用):
  - 矛盾页 → 输出冲突 diff + 建议改写
  - 命名飘合并 → 输出 `git mv` 命令
  - 漏链 → 输出候选链接列表
  - 陈旧页 → 输出处理建议(deprecate / rewrite / archive)

用户在 Claude 对话层拍板,**不**让脚本读 stdin。

### 阶段 4:写盘(LLM 调 lint.py --fix --apply)

用户拍板后,LLM 调:

```bash
python3 ./scripts/lint.py --project-dir . --fix --apply
# Bash timeout: 300000
```

**双开关安全锁**(脚本内部):

- **`--fix --apply` 才写盘**:单 `--fix` 走 dry-run,`written=[]` + `report_only=true` + `fix_proposed=true`
- **事务原子写盘**:全 in-memory 预生成所有改写 → 图结构预检(孤立节点 / 循环引用 / links 反向链接)→ `os.replace()` 一次性原子写入;校验失败 → 全部回滚(0 文件被修改)
- **Q7 死循环防护**(v0.5.3 PATCH):所有确定性写盘走 `_common.atomic_write_preserving_mtime`(stat → write → utime atime + mtime 双还原 4 步流程),**不动** frontmatter `updated` 字段
- **Git 脏状态前置检查**:
  - 不在 git 仓库 → 注记后继续
  - 在 git + 脏状态 → 默认退出非 0;`--allow-dirty` 放行
  - 在 git + 干净 → 写入前自动 `git stash push` 创建快照(stash 名 `lint-fix-pre-snapshot`)

**失败兜底**:

- 脚本退出非 0 → LLM 读取 stderr 中的中文错误,展示给用户
- 脏状态退出非 0 → LLM 建议用户先 commit / stash,或重跑带 `--allow-dirty`
- 事务校验失败 → 0 文件被修改,LLM 展示报告里的失败文件名 + 行号

LLM **不**自行 atomic write / git stash / git dirty check;全部由 `lint.py` 内部完成。

### 阶段 5:log.md 追加(由 lint.py 内部自动调 append-log.py)

**LLM 不直接调** `append-log.py`;`lint.py` 写盘成功后**内部**自动调 `append-log.py --action LintFix`。

log.md 追加模板:

```markdown
* **LintFix**: <rule-name> on [file.md](<path>) — <one-line summary>
* **LintFix**: links-mirror-sync on [file.md](sources/foo.md) — 3 added, 2 removed, 1 reordered
* **LintFix**: lint-C15.1 on analyses/<file>.md — added placeholder H2
* **LintFix**: lint-C15.2 on analyses/<file>.md — sources_used auto-filled (n=3 paths)
```

最新在前(由 `append-log.py` 内部保证)。

## 不应做

1. **无 `--fix` 时不静默改文件**(默认只报告;LLM 不绕过脚本直接 Edit 文件)。
2. **`--fix` 不静默应用语义级修改**(矛盾 / 命名飘合并 / 漏链 / 陈旧页只输出提案;LLM 不自行 git mv 或 Edit)。
3. **LLM 不直接 atomic write knowledge/ 下任何文件**(统一调 `lint.py --fix --apply`;Q7 死循环防护由脚本内部强制)。
4. **`--fix` 改 `links:` / `sources_used` 时不动 `updated` + 文件 mtime / atime**(Q7 死循环防护 v0.5.3 PATCH atime + mtime 双还原;脚本内部强制)。
5. **`--fix` 不把 `## 重点摘录` 自动重命名为 `## 方案推演 / 架构分析`**(语义级 → 必须 LLM 重写或跑 `migrate-analysis-skeleton.py`;LLM 不直接调用)。
6. **单开关触发磁盘写入**(`--fix` ≠ `--apply`,**强制**双开关;LLM 不绕过)。
7. **`--fix --apply` 在 git 脏状态下不阻断**(必须 commit / stash,或显式 `--allow-dirty` 放行;LLM 不绕过)。
8. **逐文件写**(必须事务原子:全 in-memory 预生成 → 图结构预检 → `os.replace` 一次性;LLM 不绕过)。
9. **把"裸 tag"(`ai` 无 `<axis>/` 前缀)放过**(FAIL)。
10. **放过 `comparisons/*.md` 缺 `sources:` 字段**(FAIL)。
11. **放过 `syntheses/*.md` 缺 `sources_count` 字段**(WARN,<3 警告空综合)。
12. **放过 type 已知但目录错位**(FAIL;`type: other` 在 entities 和 concepts 都合法,靠目录路径区分)。
13. **把 wikilink 当残留处理**(Q6 一等公民,**不当残留**)。
14. **对未知 type 报错**(OKF §11 要求消费者容忍),只给建议。
15. **放过 `## 摘要` / `## Summary` 残留**(FAIL;合并到 frontmatter `summary`)。
16. **放过 sources/analyses 缺 3 节骨架**(FAIL;追加占位 H2,留用户填)。
17. **LLM 不直接调 `append-log.py --action LintFix`**(由 `lint.py` 内部自动调;LLM 不重复写 log)。
18. **LLM 不直接调 `git mv` / `git stash`**(统一走 `lint.py` 安全锁)。

## 输出格式

### 默认报告格式(LLM 读 issues 列表展示)

```
[孤儿页] knowledge/concepts/theory/foo.md - 无出入链接
[矛盾] knowledge/sources/a.md ↔ knowledge/sources/b.md - 关于 X 的说法不同
[陈旧页] knowledge/sources/c.md - updated > 180 天 + log.md 无提及
[命名飘] raw/ 下检测到相似子目录:
  - 02_芯片与控制器 (15 篇) ↔ 03_芯片 (8 篇)
  建议:统一为 02_芯片
[漏链] knowledge/sources/d.md - 反复出现 "S32G" 但未链接
[frontmatter] knowledge/sources/e.md - tags 字段类型错位(string → list)
[骨架] knowledge/sources/f.md - 缺 ## 重点摘录
[raw_category] knowledge/sources/g.md - 无法派生,sources[0] 缺失
```

### `--by raw_category` group by 格式

```
按 raw_category 分组(从 sources[0].resource 路径派生):
[12_法规_标准_政策] 8 篇
  - sources/okf-spec.md
  - sources/un-r155.md
[06_功能安全] 5 篇
  - sources/iso26262-asil-d.md
[未分类] 2 篇
  - sources/legacy-doc.md        ← raw_category 派生失败
```

### `--fix` 提案格式(默认 dry-run)

```
[提案] knowledge/sources/a.md - frontmatter tags 字段: domain/ai → [domain/ai]
[提案] knowledge/sources/b.md - 末尾追加占位 H2: ## 重点摘录
[提案] knowledge/sources/c.md - links: 同步(3 added, 2 removed, 1 reordered)
```

### log.md 追加格式(`**LintFix**`)

```markdown
* **LintFix**: <rule-name> on [file.md](<path>) — <one-line summary>
* **LintFix**: links-mirror-sync on [file.md](sources/foo.md) — 3 added, 2 removed, 1 reordered
* **LintFix**: lint-C15.1 on analyses/<file>.md — added placeholder H2
* **LintFix**: lint-C15.2 on analyses/<file>.md — sources_used auto-filled (n=3 paths)
```

## 脚本调用汇总

| 命令 | timeout | 备注 |
|---|---|---|
| `python3 ./scripts/lint.py` | 60000 | 默认只报告 |
| `python3 ./scripts/lint.py --fix` | 60000 | 提案(dry-run) |
| `python3 ./scripts/lint.py --fix --apply` | 300000 | 双开关写盘 |
| `python3 ./scripts/lint.py --fix --apply --allow-dirty` | 300000 | 脏状态下强制 |
| `python3 ./scripts/lint.py --by <axis>` | 60000 | group by(raw_category/type/maturity/docform) |
| `python3 ./scripts/lint-orphans.py --project-dir .` | 30000 | 孤儿页结构化结果(语义级增强) |
| `python3 ./scripts/okf-lint.py --file <path>` | 30000 | OKF v0.2 合规 + links 漂移详细 diff |
| `python3 ./scripts/okf-lint.py --file <path> --apply` | 30000 | links: 同步(Set 比对 + 4 步 atomic) |
| `python3 ./scripts/migrate-analysis-skeleton.py --from v0.4.0 --to v0.5.0` | 300000 | G11 旧骨架迁移(LLM 不直接调,建议用户跑) |

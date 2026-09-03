---
name: aeps-llm-wiki-lint
description: 扫 knowledge/**/*.md,11 类检查(孤儿 / 矛盾 / 陈旧 / 命名飘 / 漏链 / frontmatter / links: 漂移 / raw_category / 正文骨架 / comparisons / syntheses)。默认只报告;--fix 提案确定性结构修复;--fix --apply 双开关才写盘(Q7 死循环防护 + git 脏状态检查 + 事务原子写入)。
---

# aeps-llm-wiki-lint

> **触发**:`/aeps-llm-wiki-lint [--fix] [--apply] [--allow-dirty] [--by <axis>] [--project-dir <path>]`
> **权威设计**:`src/prd.md §4.4` + `src/design.md §4.4` + `§5.4 安全锁`
> **对应实现阶段**:plugin v0.5.5 阶段 B(本文档) + 阶段 C(scripts 落地)
> **关键 PATCH**:Q7 死循环防护 v0.5.3(4 步流程) + Q6 wikilink 一等公民 + v0.3.2 安全锁(双开关 + 事务 + git 兜底) + G11 lint C15.1-C15.4

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

### 阶段 0:模式判定

| 参数组合 | 行为 |
|---|---|
| (无参数) | 扫 `knowledge/**/*.md` → 只**报告** |
| `--fix` | 扫 → 输出**确定性结构修复提案**(默认 dry-run,不写盘) |
| `--fix --apply` | 扫 → **写盘**(必须双开关) |
| `--fix --apply --allow-dirty` | git 脏状态下强制写盘 |
| `--by raw_category` / `--by type` / `--by maturity` / `--by docform` | group by 报告模式 |

`--fix` ≠ `--apply`:**单开关 `--fix` 不写盘**,仅输出提案(diff)。

### 阶段 1:扫 `knowledge/**/*.md` —— 11 类检查

#### 1.1 孤儿页

- 无任何入链接(`[[wikilink]]` / frontmatter `sources[]`)
- **豁免**:`knowledge/index.md` / `knowledge/overview.md` / `knowledge/glossary.md`

#### 1.2 矛盾(LLM 判断)

- 两页对同一事实不同说法
- 仅**报告**,`--fix` **不自动应用**(语义级)

#### 1.3 陈旧页

判定顺序:

1. **优先**:`stale_after` 存在且 `now >= stale_after` → 陈旧
2. **回退**:`stale_after` 缺失 + `updated > 180 天` + `log.md` 无提及 → 陈旧
3. **豁免**:`status: deprecated`
4. **不豁免**:`status: draft`

阈值常量:`STALE_THRESHOLD_DAYS = 180`。

#### 1.4 LLM 命名飘(仅**报告**,**不**自动合并)

- Levenshtein ≤ 2 + 全小写 + `-` 归一
- 前缀 / 后缀差异
- 同义命名漂移(同目录下 `soc_design.md` + `soc-design.md`)
- `--fix` 输出**提案 + 用户拍板命令**(如 `git mv raw/03_芯片_v2/* raw/02_芯片/`)

#### 1.5 漏链

- 某页正文反复出现术语(LLM 判断),但未链接到对应 entity / concept / source 页

#### 1.6 frontmatter 不合规

- 必填字段缺失(`type` / `title` / `description` / `tags` / `updated`)
- 类型错位(如 `tags` 是 string 而不是 list)
- 未知 `type`(OKF §11 要求消费者容忍,只给建议)
- **裸 tag** 无 `<axis>/` 前缀(FAIL,六轴必须)

#### 1.7 frontmatter `links:` 漂移(design §3.6.2)

- 与正文 `[[wikilink]]` 走 **Set 比对**(Q7 死循环防护,alias / anchor / path prefix 已 Normalizer)
- `links:` 多 ghost(target 不在正文)→ WARN
- 正文 wikilink 多 target(`links:` 漏)→ WARN

**`--fix --apply` 自动重生成 `links:`**(满足 Set 相等即可):

- stat → write_text → utime(atime + mtime 双还原,4 步流程)
- **不动** frontmatter `updated` 字段
- **保留** 文件 atime + mtime(`os.stat().st_atime` 与 fix 前浮点精度 1e-6 相等;`os.stat().st_mtime` 同)
- 跑两遍结果完全相同(幂等)

#### 1.8 raw_category 派生失败

从 `sources[0].resource` 路径派生:

- `sources` 字段缺失
- 路径不在 `<project>/raw/` 下
- 分类不在 15 类字典内

→ FAIL。

#### 1.9 正文骨架不合规

**`sources/*.md`** 必含 3 H2:

```markdown
## 重点摘录
## 我的思考
## 总结:最有收获的一句话
```

**`analyses/*.md`**(G11)必含 3 H2:

```markdown
## 方案推演 / 架构分析
## 关联溯源              (末尾必须有 > 引用: 行)
## 总结:最有收获的一句话
```

**全部禁止 H2**(lint FAIL):

- `## 摘要` / `## Summary`
- `## 重点摘录` / `## 我的思考`(在 analyses/ 内,这是 sources 风格)

**`--fix --apply`**:缺 H2 → 文件末尾追加**空占位** H2(用户手动填内容);log.md 追加 `**LintFix**: lint-C15.1 on analyses/<file>.md — added placeholder H2`。

**`--fix` 不自动重命名** `## 重点摘录` → `## 方案推演`(语义级,需 LLM 重写或跑迁移脚本)。

#### 1.10 `comparisons/*.md`

- `type: comparison`
- frontmatter `sources:` 字段 ≥ 2 条 wikilink(FAIL 若缺)

#### 1.11 `syntheses/*.md`

- `type: synthesis`
- frontmatter `sources_count` 字段缺失或 < 3 → WARN(空综合)

### 阶段 2:`--fix` 分流

**确定性结构修复**(`--fix --apply` 写盘):

| 修复项 | 行为 | log.md 条目 |
|---|---|---|
| frontmatter 必填字段缺失 | 补占位值 + WARN | `**LintFix**: frontmatter-fill on [file.md] — added <field>` |
| frontmatter 类型错位 | 强转 | `**LintFix**: frontmatter-typecast on [file.md] — tags string → list` |
| `## 摘要` / `## Summary` 残留 | 删小节,内容合并到 frontmatter `summary` | `**LintFix**: summary-extract on [file.md] — extracted N chars to summary` |
| sources/analyses 缺 3 节骨架 | 文件末尾追加占位 H2(空内容) | `**LintFix**: lint-C15.1 on analyses/<file>.md — added placeholder H2` |
| `links:` ↔ wikilink 漂移 | 同步 `links:` 字段(Set 比对;4 步流程) | `**LintFix**: links-mirror-sync on [file.md] — N added, M removed, K reordered` |
| `sources_used` 缺(analyses) | 从 `## 关联溯源` 末尾 `> 引用:` 行 + query 阶段引用路径派生 | `**LintFix**: lint-C15.2 on analyses/<file>.md — sources_used auto-filled (n=K paths)` |

**Q7 死循环防护**:所有确定性写盘**必须**走 4 步流程(stat → write_text → utime(atime + mtime 双还原)),**不动** frontmatter `updated` 字段。

**语义级问题**(`--fix` **仅输出提案**,**不应用**):

- 矛盾页 → 输出冲突 diff + 建议改写
- 命名飘合并 → 输出 `git mv` 命令
- 漏链 → 输出候选链接列表
- 陈旧页 → 输出处理建议(deprecate / rewrite / archive)

### 阶段 3:Lint --fix 安全锁(design §5.4,v0.3.2 新增)

**1. 默认 dry-run**

- `--fix` ≠ `--apply`:**单开关** `--fix` **不写盘**
- 必须 `--fix --apply` 双开关才触发磁盘写入
- `--fix` 输出每文件的 diff 提案(用户可见)

**2. 事务原子写入**

- 全 in-memory 预生成所有改写 → **图结构预检**(孤立节点 / 循环引用 / links 反向链接) → `os.replace()` 一次性原子写入
- 校验失败 → **全部回滚**(0 文件被修改),报告"图结构预检失败 / 校验失败" + 失败文件名 + 行号

**3. Git 脏状态前置检查**

| 工作区状态 | `--fix --apply` 行为 | `--fix --apply --allow-dirty` 行为 |
|---|---|---|
| 不在 git 仓库 | 注记后继续 | 同左 |
| 在 git + 脏状态 | **退出非 0** + 提示"工作区有未提交改动,请先 commit 或 stash" | 退出 0 + 报告注明"已忽略脏状态检查" |
| 在 git + 干净 | 写入前自动 `git stash push` 创建快照(stash 名 `lint-fix-pre-snapshot`) | 同左 |

### 阶段 4:log.md 追加

写盘后追加 `**LintFix**` 条目(5 种前缀之一,plugin 强制):

```markdown
* **LintFix**: <rule-name> on [file.md](<path>) — <one-line summary>
```

最新在前。

## 不应做

1. **无 `--fix` 时不静默改文件**(默认只报告)。
2. **`--fix` 不静默应用语义级修改**(矛盾 / 命名飘合并 / 漏链 / 陈旧页只输出提案)。
3. **`--fix` 改 `links:` / `sources_used` 时不动 `updated` + 文件 mtime / atime**(Q7 死循环防护 v0.5.3 PATCH atime + mtime 双还原)。
4. **`--fix` 不把 `## 重点摘录` 自动重命名为 `## 方案推演 / 架构分析`**(语义级 → 必须 LLM 重写或跑 `migrate-analysis-skeleton.py`)。
5. **单开关触发磁盘写入**(`--fix` ≠ `--apply`,**强制**双开关)。
6. **`--fix --apply` 在 git 脏状态下不阻断**(必须 commit / stash,或显式 `--allow-dirty` 放行)。
7. **逐文件写**(必须事务原子:全 in-memory 预生成 → 图结构预检 → `os.replace` 一次性)。
8. **把"裸 tag"(`ai` 无 `<axis>/` 前缀)放过**(FAIL)。
9. **放过 `comparisons/*.md` 缺 `sources:` 字段**(FAIL)。
10. **放过 `syntheses/*.md` 缺 `sources_count` 字段**(WARN,<3 警告空综合)。
11. **放过 type 已知但目录错位**(FAIL;`type: other` 在 entities 和 concepts 都合法,靠目录路径区分)。
12. **把 wikilink 当残留处理**(Q6 一等公民,**不当残留**)。
13. **对未知 type 报错**(OKF §11 要求消费者容忍),只给建议。
14. **放过 `## 摘要` / `## Summary` 残留**(FAIL;合并到 frontmatter `summary`)。
15. **放过 sources/analyses 缺 3 节骨架**(FAIL;追加占位 H2,留用户填)。

## 输出格式

### 默认报告格式

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
| `python3 ./scripts/lint.py --by raw_category` | 60000 | group by |
| `python3 ./scripts/lint-query-output.py --input <last-response>.md` | 30000 | C15.3 末尾标记校验 |
| `python3 ./scripts/migrate-analysis-skeleton.py --from v0.4.0 --to v0.5.0` | 300000 | G11 旧骨架迁移 |

辅助脚本(阶段 C 落地后):

- `lint-orphans.py` / `lint-frontmatter.py` / `okf-lint.py` / `validate-frontmatter.py`
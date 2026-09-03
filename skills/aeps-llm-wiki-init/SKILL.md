---
name: aeps-llm-wiki-init
description: 在用户项目里搭建 / 同步 aeps-llm-wiki 知识库目录结构(inbox / raw / scripts / templates / temp / knowledge)。幂等再入:首次启用与升级走同一条入口,本地字典保留用户修改。
---

# aeps-llm-wiki-init

> **触发**:`/aeps-llm-wiki-init [项目路径]`
> **权威设计**:`src/prd.md §4.1` + `src/design.md §4.1` + `§4.1.1 幂等再入` + `src/scripts/DESIGN.md §1.1 init-vault`
> **对应实现阶段**:plugin v0.5.5 阶段 B(SKILL.md)+ 阶段 C(init-vault.py 已落地)
> **核心原则**:LLM 只做思考 + 调度;具体 IO 全部交 `init-vault.py`(详见 `scripts/DESIGN.md §0.1`)

## 必读文件

启动 skill 时,**先 Read** 以下文件,再做任何动作:

| 优先级 | 路径 | 用途 |
|---|---|---|
| 1 | `aeps-llm-wiki-plugin/src/templates/knowledge-SCHEMA.md` | 用户项目操作手册(初版;实化时占位符替换) |
| 2 | `aeps-llm-wiki-plugin/src/templates/raw-readme.md` | 15 类 raw 子目录权威字典(plugin 主) |
| 3 | `aeps-llm-wiki-plugin/src/templates/concept-entities-readme.md` | 14 子类 ↔ 目录 1:1 绑死字典(plugin 主) |
| 4 | `aeps-llm-wiki-plugin/src/templates/tag-template.md` | 六轴受控词表 v0.4(plugin 主) |
| 5 | `aeps-llm-wiki-plugin/src/templates/inbox-readme.md` | inbox 入口提示(plugin 主) |
| 6 | `aeps-llm-wiki-plugin/src/scripts/README.md` | scripts/ 约定(无 daemon / 无交互 / proposal-apply 两阶段) |
| 7 | `aeps-llm-wiki-plugin/src/scripts/requirements.txt` | 强依赖清单(anydoc / paddleocr / jsonschema / pyyaml) |

若 plugin 本体 `schema/frontmatter.schema.yaml` 已落地(阶段 C),**追加**必读第 8 项;未落地则跳过,frontmatter 校验降级为最小校验。

## 工作流

### 阶段 0:路径与现状判定

1. 取用户传入的 `<project>/`(默认 cwd)。
2. 检查 `<project>/knowledge/SCHEMA.md` 是否存在:
   - **存在** → 走 **§阶段 4 re-run** 流程(Llm 调用 `init-vault.py --re-run`)。
   - **不存在** → 走 **§阶段 1-3 首次启用**(Llm 调用 `init-vault.py --project-dir .`)。

LLM **不**直接创建任何顶层目录 / 拷贝任何模板;所有 IO 委托脚本。

### 阶段 1:首次启用 - 调用 init-vault.py

```bash
python3 ./scripts/init-vault.py --project-dir .
# Bash timeout: 120000(60s 足够,首启最坏情况 = 拷贝 templates + scripts)
```

**脚本职责**(LLM 不再做):

- 建 6 顶层目录(inbox / raw / scripts / templates / temp / knowledge)+ 每个目录 `.gitkeep`
- 建 `raw/` 下 15 子目录 + 各 `.gitkeep`
- 建 `knowledge/` 下 18 叶子存储目录(sources / entities/7 子类 / concepts/7 子类 / analyses / comparisons / syntheses)+ 各 `.gitkeep`
- 拷贝 `templates/source-page.md` / `templates/analysis-page.md` / `templates/concept-entities-readme.md` / `templates/tag-template.md` 到 `<project>/templates/`
- 拷贝 `scripts/README.md` / `scripts/requirements.txt` + 所有 .py 到 `<project>/scripts/`
- 写 `<project>/raw/.aeps-plugin-version: 0.5.5`
- 写 `<project>/scripts/_meta.json`
- 写 4 个种子文件:`knowledge/SCHEMA.md`(占位符替换)/ `raw/README.md` / `inbox/README.md` / `knowledge/index.md`
- 写 `temp/.gitignore`(5 行规范:`*` / `!.gitkeep` / `!proposal-*.json` / `!decision-*.json` / `!plan-*.json`)
- 写空 `overview.md` / `glossary.md` / `log.md`

**返回 JSON 形态**:

```json
{
  "ok": true,
  "created": ["inbox/", "raw/", "knowledge/sources/", ...],
  "copied": ["templates/source-page.md", "scripts/init-vault.py", ...],
  "synced_at": "<ISO 8601>",
  "plugin_version": "0.5.5"
}
```

### 阶段 2:首次启用 - 校验脚本返回

LLM 读返回 JSON,做以下判断:

- `ok == true` → 进入 §阶段 3 展示摘要
- `ok == false` → 读取 stderr 中的中文错误,展示给用户;**不**继续后续步骤

### 阶段 3:首次启用 - 展示 sync 摘要

向用户报告(基于 `created` / `copied` / `synced_at` 字段):

```
Init 完成。详细 sync 摘要:
- 顶层目录: 新建 N / 跳过 K
- 15 raw 子目录: 新建 N / 跳过 K
- 18 叶子存储目录: 新建 N / 跳过 K
- templates/: 拷贝 4 份页生成模板 + 2 份字典
- scripts/: 拷贝 N 个 .py + README + requirements.txt
- 种子文件: SCHEMA.md / raw/README.md / inbox/README.md / index.md 已写入
- 同步 plugin 版本: <plugin_version>
- 下一步: 把资料丢进 inbox/ 跑 /aeps-llm-wiki-ingest
```

### 阶段 4:re-run - 调用 init-vault.py --re-run

```bash
python3 ./scripts/init-vault.py --project-dir . --re-run
# Bash timeout: 120000
```

**脚本职责**(LLM 不再做):

- 顶层目录 + 15 raw 子目录 + 18 叶子目录**补缺**(已有则跳过)
- 字典 sync(`templates/concept-entities-readme.md` / `templates/tag-template.md` 走 append,plugin 新章节 / 词条加到用户文件末尾,**不删不改**用户已有内容)
- 文件 sync:`knowledge/SCHEMA.md` / `inbox/README.md` / `raw/README.md` / `templates/source-page.md` / `templates/analysis-page.md` **覆盖**(plugin 主,版本对齐);`scripts/` 内 .py + README + requirements.txt **覆盖**
- **不动**:`index.md` / `overview.md` / `glossary.md`(LLM 累积维护,plugin 升级不覆盖)
- `log.md` 追加一行 `**Update**: re-run init at <ISO 8601> by agent: producer/aeps-llm-wiki-plugin/0.5.5`

**返回 JSON 形态**:同首次启用,但 `created` 列表只含本次**新建**的项;已存在的不重复出现。

### 阶段 5:re-run - 展示 sync 摘要

向用户报告:

```
Init re-run 完成。详细 sync 摘要:
- 顶层目录: 新建 N / 跳过 K(已存在)
- 15 raw 子目录: 新建 N / 跳过 K
- 18 叶子存储目录: 新建 N / 跳过 K
- 字典 templates/concept-entities-readme.md: append M 章节 / 跳过 K
- 字典 templates/tag-template.md: append M 词条 / 跳过 K
- 字典 templates/source-page.md / analysis-page.md: 覆盖
- knowledge/SCHEMA.md / raw/README.md / inbox/README.md: 覆盖
- log.md: append 1 行 re-run 记录
- scripts/: 同步 N 个 .py(覆盖式)
- 你的本地修改一律保留(index.md / overview.md / glossary.md + 用户新增字典条目不动)
```

## 不应做

1. **不接受任何目录名参数**(`--raw-dir custom-raw` / `--knowledge-dir my-kb` 等全部拒绝;6 个顶层目录名硬编码)。
2. **LLM 不直接创建任何目录**(顶层 / raw 子目录 / knowledge 叶子目录一律 `init-vault.py` 建)。
3. **LLM 不直接拷贝 templates / scripts 文件**(一律 `init-vault.py` 拷)。
4. **LLM 不直接写任何种子文件**(SCHEMA.md / index.md / log.md 等一律 `init-vault.py` 写)。
5. **LLM 不直接写 frontmatter / 文件内容**(scripts 层职责,SKILL.md 只调度)。
6. **LLM 不调用除 `init-vault.py` 之外的写盘脚本**(init 阶段不涉及 `safe-mv.py` / `generate-source-page.py` / `append-log.py` 等)。
7. **不跳过 `.gitkeep`**:每个初始空目录都必须建 `.gitkeep**(由 `init-vault.py` 强制)。
8. **不调 `${CLAUDE_PLUGIN_ROOT}` / 绝对路径 / `~/.claude/`**:所有路径统一 `<project>/<dir>/` 占位,脚本接收 `--project-dir .` 相对路径参数。
9. **不在 user-project 任何文件里写 plugin 本体路径**(plugin.json 引用除外,但 SKILL.md 不直接写)。
10. **不问用户"是否覆盖"**(init 是幂等的,sync 策略已固定;若有冲突,日志 + 摘要里提示用户)。

## 输出格式

### init / re-run 完成摘要(对话层向用户展示)

```
<init|re-run> 完成。详细见上方 sync 摘要。
- 本次同步的 plugin 版本: <plugin_version from JSON>
- <project>/ 顶层目录: 已就绪(6 个)
- knowledge/ 叶子存储目录: 已就绪(18 个)
- raw/ 子目录: 已就绪(15 类)
- 你的本地字典 / 索引 / 概览 一律保留
- 下一步: 把资料丢进 inbox/ 跑 /aeps-llm-wiki-ingest
```

### actor 字符串规范

- 生成方:`agent: producer/aeps-llm-wiki-plugin/0.5.5`
- 验证方:`human:<id>`(如 `human:zhigang.liu`)
- 处理链:`process:<skill-name>`(如 `process:aeps-llm-wiki-init`)

## 脚本调用汇总

| 阶段 | 脚本 | timeout | 备注 |
|---|---|---|---|
| 阶段 1(首次启用) | `init-vault.py --project-dir .` | 120000 | 顶层 / raw / knowledge + 拷贝 templates/scripts + 写种子 |
| 阶段 4(re-run) | `init-vault.py --project-dir . --re-run` | 120000 | 补缺 + 字典 append + 文件覆盖(保留 index/overview/glossary) |

**LLM 不直接调任何其他脚本**;init 阶段是单脚本全包,无需 `safe-mv.py` / `append-log.py` / `validate-frontmatter.py` 等。

阶段 C 落地后,init 末尾可建议用户跑:

```bash
pip install -r scripts/requirements.txt
```

(此为**建议**,不在 init 流程强制)。

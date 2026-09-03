---
name: aeps-llm-wiki-init
description: 在用户项目里搭建 / 同步 aeps-llm-wiki 知识库目录结构(inbox / raw / scripts / templates / temp / knowledge)。幂等再入:首次启用与升级走同一条入口,本地字典保留用户修改。
---

# aeps-llm-wiki-init

> **触发**:`/aeps-llm-wiki-init [项目路径]`
> **权威设计**:`src/prd.md §4.1` + `src/design.md §4.1` + `§4.1.1 幂等再入`
> **对应实现阶段**:plugin v0.5.5 阶段 B

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
   - **存在** → 走 **§阶段 4 幂等再入**。
   - **不存在** → 走 **§阶段 1-3 首次启用**。

### 阶段 1:首次启用 - 创建 6 个顶层目录

每个目录都建 `.gitkeep`(保证 git 跟踪)。

```
<project>/
├── inbox/         + README.md(从 templates/inbox-readme.md)+ .gitkeep
├── raw/           + README.md(从 templates/raw-readme.md,占位符替换)+ 15 子目录 + .gitkeep
├── scripts/       + README.md + requirements.txt + 所有 .py(阶段 C 落地;此阶段为空,留 .gitkeep)
├── templates/     + source-page.md + analysis-page.md + concept-entities-readme.md + tag-template.md
├── temp/          + .gitkeep + .gitignore(内容:* / !.gitkeep / !proposal-*.json / !decision-*.json / !plan-*.json)
└── knowledge/     + SCHEMA.md(从 templates/knowledge-SCHEMA.md,占位符替换)+ index.md + overview.md + glossary.md + log.md + 18 个叶子存储目录
```

**18 个叶子存储目录清单**(1 + 7 + 7 + 1 + 1 + 1 = 18):

- `sources/`
- `entities/{person, organization, project, product, event, place, other}/`(7 子类)
- `concepts/{theory, method, field, phenomenon, standard, term, other}/`(7 子类)
- `analyses/`
- `comparisons/`
- `syntheses/`

**15 个 raw 子目录**(详见 templates/raw-readme.md):

`01_EE架构` / `02_芯片` / `03_通信与网络` / `04_操作系统与中间件` / `05_软件工程` / `06_功能安全` / `07_信息安全` / `08_AI与AI工程` / `09_域控制器` / `10_会议与活动` / `11_开发工具` / `12_法规_标准_政策` / `13_流程体系` / `14_测试与验证` / `15_算法`

### 阶段 2:首次启用 - 复制 templates

按以下规则把 plugin `src/templates/` 拷到 `<project>/`:

| plugin 源 | user-project 落点 | 策略 |
|---|---|---|
| `knowledge-SCHEMA.md` | `knowledge/SCHEMA.md` | **实化**:占位符 `{{plugin_version}}` / `{{init_at}}` / actor 字符串替换 |
| `raw-readme.md` | `raw/README.md` | **覆盖**(权威字典) |
| `inbox-readme.md` | `inbox/README.md` | **覆盖** |
| `source-page.md` | `templates/source-page.md` | **覆盖** |
| `analysis-page.md` | `templates/analysis-page.md` | **覆盖** |
| `concept-entities-readme.md` | `templates/concept-entities-readme.md` | **append 策略**(见 §阶段 4) |
| `tag-template.md` | `templates/tag-template.md` | **append 策略**(见 §阶段 4) |

### 阶段 3:首次启用 - 写版本戳与空索引

- 写 `<project>/raw/.aeps-plugin-version: 0.5.5`(一行版本号,plugin 升级检查用)
- 写空 `index.md`(只有 frontmatter `okf_version: "0.2"` + 空 body)
- 写空 `overview.md` / `glossary.md`(LLM 后续维护)
- 写 `log.md` 顶部一行:`## <ISO 8601 today>`(当日 heading,空内容)

### 阶段 4:幂等再入 - sync 策略

**触发条件**:`<project>/knowledge/SCHEMA.md` 已存在。

按以下顺序处理(每项独立报告):

1. **顶层目录补缺**:6 个顶层目录任一缺失 → 补建 + `.gitkeep`;**plugin 新版新增的子类目录一律不预建**,留给 ingest 拍板门。
2. **18 个叶子存储目录补缺**:缺失 → 补建 + `.gitkeep`。
3. **15 个 raw 子目录补缺**:缺失 → 补建 + `.gitkeep`。
4. **字典 sync(三份全栈字典走 append,plugin 主)**:
   - `templates/concept-entities-readme.md`:plugin 版新章节 **append** 到用户文件末尾(不删不改用户已有内容)
   - `templates/tag-template.md`:plugin 版新词条 **append** 到用户文件末尾
   - **不** 整文件覆盖,避免破坏用户本地新增的子类 / 词条
5. **文件 sync(分类处理)**:
   - `knowledge/SCHEMA.md` / `inbox/README.md` / `raw/README.md`:**覆盖**(plugin 主,版本对齐)
   - `templates/source-page.md` / `templates/analysis-page.md`:**覆盖**
   - `log.md`:**append** 一行 `**Update**: re-run init at <ISO 8601> by agent: producer/aeps-llm-wiki-plugin/0.5.5`
   - `index.md` / `overview.md` / `glossary.md`:**不动**(LLM 累积维护,plugin 升级不覆盖)
6. **scripts/ 与 requirements.txt 同步**:plugin 本体 → `<project>/scripts/` 拷最新版本。scripts/ 内部 .py 文件阶段 C 落地时由 plugin 维护者统一同步。

### 阶段 5:输出 sync 摘要

向用户报告本次 init / re-run 的 sync 摘要(参考格式):

```
Init re-run 完成。sync 摘要:
- 顶层目录: 新建 N / 跳过 K
- 15 raw 子目录: 新建 N / 跳过 K
- 18 叶子存储目录: 新建 N / 跳过 K
- 字典 templates/concept-entities-readme.md: append M 章节 / 跳过 K
- 字典 templates/tag-template.md: append M 词条 / 跳过 K
- 字典 templates/source-page.md: 覆盖 / 跳过
- 字典 templates/analysis-page.md: 覆盖 / 跳过
- knowledge/SCHEMA.md / raw/README.md / inbox/README.md: 覆盖
- log.md: append 1 行 re-run 记录
- 你的本地修改一律保留(index.md / overview.md / glossary.md + 用户新增字典条目不动)
```

## 不应做

1. **不接受任何目录名参数**(`--raw-dir custom-raw` / `--knowledge-dir my-kb` 等全部拒绝;6 个顶层目录名硬编码)。
2. **不覆盖已有 knowledge/ 的非 sync 清单文件**:`index.md` / `overview.md` / `glossary.md` 一律不动。
3. **不整文件覆盖三份全栈字典**(concept-entities-readme / tag-template / raw-readme 走 append,避免破坏用户本地新增)。
4. **不预建 plugin 新版新增的子类目录**(留给 ingest 拍板门)。
5. **不跳过 `.gitkeep`**:每个初始空目录都必须建 `.gitkeep`。
6. **不调 `${CLAUDE_PLUGIN_ROOT}` / 绝对路径 / `~/.claude/`**:所有路径统一 `<project>/<dir>/` 占位。
7. **不在 user-project 任何文件里写 plugin 本体路径**(plugin.json 引用除外,但 SKILL.md 不直接写)。
8. **不创建 `temp/<files>` 内容**(只建目录 + `.gitkeep` + `.gitignore`;proposal/decision 文件由 ingest 运行时生成)。
9. **不为非 bundle 根的 `index.md` 加 frontmatter `okf_version`**:只有 `knowledge/index.md` 允许。
10. **不问用户"是否覆盖"**(init 是幂等的,sync 策略已固定;若有冲突,日志 + 摘要里提示用户)。

## 输出格式

### init / re-run 完成摘要(对话层向用户展示)

```
<init|re-run> 完成。详细见上方 sync 摘要。
- 本次同步的 plugin 版本: 0.5.5
- <project>/ 顶层目录: 已就绪(6 个)
- knowledge/ 叶子存储目录: 已就绪(18 个)
- raw/ 子目录: 已就绪(15 类)
- 你的本地字典 / 索引 / 概览 一律保留
- 下一步: 把资料丢进 inbox/ 跑 /aeps-llm-wiki-ingest
```

### log.md 追加模板

首次启用 + re-run **都**追加一条:

```markdown
## <YYYY-MM-DD>(init 时)或留空(re-run 时)
* **Update**: re-run init at <YYYY-MM-DDTHH:MM:SSZ> by agent: producer/aeps-llm-wiki-plugin/0.5.5
```

> 注:`re-run` 走 `**Update**` 前缀(5 种前缀之一:`**Creation**` / `**Update**` / `**Deprecation**` / `**Migration**` / `**LintFix**`)。

### actor 字符串规范

- 生成方:`agent: producer/aeps-llm-wiki-plugin/0.5.5`
- 验证方:`human:<id>`(如 `human:zhigang.liu`)
- 处理链:`process:<skill-name>`(如 `process:aeps-llm-wiki-init`)

## 脚本调用

本 skill **不直接调任何 scripts**(纯 LLM 拷文件 + 写 log)。

阶段 C 落地后,init 末尾可建议用户跑:

```bash
pip install -r scripts/requirements.txt
```

(此为**建议**,不在 init 流程强制)。
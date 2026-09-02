# aeps-llm-wiki-plugin — design.md

> **状态**:v0.2 已冻结(2026-09-02)
> **创建日期**:2026-09-01
> **作者**:zhigang.liu
> **范围**:本文件承接 [prd.md](prd.md) 里抽出 / 简化的实现细节;具体任务拆分见 [implement.md](implement.md)
> **读者**:plugin 维护者 + 任何要改 schema / skill 行为的开发者

---

## 0. 文档关系

| 文档                        | 角色                                                        |
| --------------------------- | ----------------------------------------------------------- |
| [prd.md](prd.md)             | **产品需求** —— 用户能感知什么、验收什么、不做什么  |
| [design.md](design.md)       | **本文档** —— 怎么实现:模块边界、数据契约、关键流程 |
| [implement.md](implement.md) | **执行清单** —— 拆任务、测试用例、提交节奏          |

**权威顺序**(冲突时):prd > design > implement。**任何反 prd 的 design 决定必须先回 prd 改**。

---

## 0. 前端契约:Obsidian 直读约束(顶级约束)

plugin 生成的 `knowledge/` 必须能直接被 **Obsidian** 打开使用,无需任何格式转换或中间映射层。Obsidian 是 LLM 写完 wiki 之后**人真正读 / 浏览 / 跳链 / 反查**的工具,所有数据契约(链接 / tag / 目录 / frontmatter / 文件命名)都要按 Obsidian 原生语义设计。

| 维度                  | Obsidian 期望                                                                               | plugin 必须做                                                                               | 不得做                                               |
| --------------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| **链接**        | `[[page]]` / `[[page\|显示]]` / `[[page#章节]]` 双链原生可跳;反向链接面板自动生成      | 把`[[wikilink]]` 写为一等公民(Q6)                                                         | ~~强制只写标准 markdown 链接 / 把 wikilink 当残留~~ |
| **tag**         | frontmatter`tags: [a, b]` 自动扫到 tag 面板;hierarchical tag `#domain/autosar` 也支持   | frontmatter`tags` 字段走 YAML list;六轴受控词表允许斜杠分层的层次 tag                     | ~~把 tag 塞进正文随机位置 / 用别名 / 拼写漂移~~     |
| **目录**        | vault 子文件夹 = Obsidian 左侧栏树状结构                                                    | `knowledge/{entities,concepts,sources,analyses,comparisons,syntheses}/` 即 vault 子文件夹 | ~~加映射层 / 中间目录 / 软链~~                      |
| **frontmatter** | YAML 块必须严格合法(YAML 1.2);`title` / `tags` / `aliases` 字段 Obsidian 识别为元数据 | frontmatter 走 YAML,字段名小写连字符 / 下划线两种都接受                                     | ~~JSON 风格 / TOML / 内联字段~~                     |
| **文件名**      | Obsidian 用文件名作为 page 标识,文件名即 wikilink 解析目标                                  | 文件名用`<slug>.md` 形式,slug 全小写、连字符                                              | ~~文件名含中文 / 空格 / 大写混用~~                  |
| **反向链接**    | Obsidian 自动建反向链接图谱                                                                 | 自然产生(每页 frontmatter`sources:` 字段 + 正文 `[[wikilink]]` 是反向链接的天然输入)    | ~~手工维护反向链接 / 单独建 backlinks 索引~~        |

**Obsidian 兼容 ≠ OKF 兼容**:Obsidian 双链 + tag 不在 OKF v0.2 §4/§6 的强制要求里,但 Obsidian 兼容性通过以下方式保证 OKF v0.2 严格兼容:

- **正文 wiki link 走 `[[wikilink]]` 一等公民**(Q6)—— Obsidian 原生双链 + Karpathy 老 wiki 无需转换;**OKF 兼容性靠 frontmatter `links:` 镜像字段同步**(详见 §3.6)
- frontmatter `type:` 严格 OKF 必填字段,OKF 工具可识别为 source/analysis/concept/entity 等
- frontmatter `links:`(OKF v0.2 §9 推荐字段)由 plugin 维护镜像,与正文 `[[wikilink]]` 同步(详见 §3.6)

**Obsidian 不兼容 = plugin FAIL**:任何 Obsidian 不识别的链接 / tag / 目录 / 文件名约定,plugin 设计阶段就要拒绝(NFR-1 衍生)。lint 不容忍这些隐性破坏。

---

## 1. 模块边界

### 1.1 目录布局(plugin 本体 = `src/`)

```
src/
├── .claude-plugin/
│ └── plugin.json                  # plugin manifest(name / version / skills 列表)
├── hooks/                         # 【运行路径】Claude Code 事件回调
│   └── hooks.json                 # SessionStart → plugin 更新检查;详见 §8
├── skills/                        # 【运行路径】Agent 入口
│   ├── aeps-llm-wiki-init/SKILL.md
│   ├── aeps-llm-wiki-ingest/SKILL.md
│   ├── aeps-llm-wiki-query/SKILL.md
│   ├── aeps-llm-wiki-lint/SKILL.md
│   └── aeps-llm-wiki-synthesize/SKILL.md
├── templates/                     # 【运行路径】init 时复制到用户项目
│   ├── index.md
│   ├── log.md
│   ├── glossary.md
│   ├── overview.md
│   ├── source-page.md
│   ├── concept-page.md
│   ├── knowledge-SCHEMA.md
│   ├── raw-readme.md              # raw/ 子目录分类字典(权威文件,plugin 维护者直接编辑)
│   ├── concept-entities-readme.md # entities/concepts 子类枚举字典(权威文件,plugin 维护者直接编辑)
│   └── inbox-readme.md
├── schema/
│ └── frontmatter.schema.yaml   # 【运行路径】frontmatter 字段机器可读定义
├── scripts/                      # 【运行路径】skill 调用的辅助脚本(拷到 user-project;Python 3.10+ .py)
│   ├── README.md                  # scripts/ 约定 + 未来脚本规划 + "不带运行时"边界
│   └── requirements.txt           # 【运行路径】第三方 Python 依赖清单(anydoc / paddleocr / jsonschema / pyyaml / pytest);init 时随 scripts/ 一起拷到 user-project 的 scripts/requirements.txt
├── docs/                         # 【不进运行路径】给 plugin 用户看
│   ├── README.md
│   ├── architecture.md
│   └── customization.md
├── tests/                        # 【不进运行路径】离线验证 plugin 产物
│   ├── test_templates.py
│   ├── test_frontmatter_compliance.py
│   └── test_okf_compliance.py
├── prd.md                        # 【不进运行路径】产品需求
├── design.md                     # 【不进运行路径】本文档
├── implement.md                  # 【不进运行路径】执行清单
├── LICENSE
 └── .gitignore
```

> **注**:`templates/` 跨节引用说明 —— 上图列的是 **plugin 本体** 的目录布局。init 时按 §2.5.1 路由规则把 templates/ 下 7 份核心文件**散落**到 user-project 不同位置(SCHEMA → `knowledge/SCHEMA.md`,raw-readme → `raw/README.md`,inbox-readme → `inbox/README.md`,concept-entities-readme / tag-template / 4 份页生成模板 → `templates/` 顶层)。**user-project 的 `templates/` 不会出现 SCHEMA / raw-readme / inbox-readme**(因为它们**只**与某一个子目录相关,按 §2.5.1 判定规则 1 已散落)。详见 §2.5.1 路由表。

### 1.2 模块职责(每个一行)

| 模块                                          | 职责                                                                                                                                                                                                                                                                                                          | 进 plugin 运行路径?                         |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| `.claude-plugin/plugin.json`                | plugin manifest,声明 name / version / skills 列表                                                                                                                                                                                                                                                             | ✅                                          |
| `skills/*/SKILL.md`                         | 每个 skill 是一个独立的 Agent 入口                                                                                                                                                                                                                                                                            | ✅                                          |
| `templates/*`                               | 静态模板,init 时复制到用户项目                                                                                                                                                                                                                                                                                | ✅                                          |
| `schema/frontmatter.schema.yaml`            | frontmatter 字段机器可读定义,单一真理源                                                                                                                                                                                                                                                                       | ✅(被 skills/templates 引用)                |
| `scripts/*`                                 | skill 调用的辅助脚本(**Python 3.10+ .py**,init 时拷到 user-project);所有脚本必须**单次运行即退出**,不开 daemon / 不挂监听 / 不暴露服务(与 NFR-1 兼容)                                                                                                                                             | ✅(被 skills 调用)                          |
| `scripts/check-qmd.py`                      | query skill 跑前探查 qmd 可用性 + 数 knowledge 页数,按阈值返回`index` / `qmd` / `fail`(详见 §4.3)                                                                                                                                                                                                      | ✅(被 query skill 调用)                     |
| `hooks/hooks.json`                          | Claude Code 事件回调;SessionStart → plugin 仓库更新检查,详见 §8;事件回调同步跑完即退,不开监听                                                                                                                                                                                                               | ✅(被 Claude Code 自动触发)                 |
| `scripts/requirements.txt`                  | 第三方 Python 依赖清单(anydoc / paddleocr / jsonschema / pyyaml 强依赖;pytest 单测时需要;qmd 不在此清单,单独`npm install -g @tobilu/qmd`);init 时随 scripts/ 拷到`<project>/scripts/requirements.txt`,用户必须 `pip install -r scripts/requirements.txt` 才能用 ingest 的 pptx/docx/xlsx/pdf/图片类 OCR | ✅(被 convert-to-md.py / check-qmd.py 调用) |
| `docs/*`                                    | 用户文档                                                                                                                                                                                                                                                                                                      | ❌                                          |
| `tests/*`                                   | 离线验证 plugin 产物                                                                                                                                                                                                                                                                                          | ❌                                          |
| `prd.md` / `design.md` / `implement.md` | 文档三件套                                                                                                                                                                                                                                                                                                    | ❌                                          |
| `LICENSE`                                   | Apache 2.0                                                                                                                                                                                                                                                                                                    | ❌                                          |
| `.gitignore`                                | git 忽略规则                                                                                                                                                                                                                                                                                                  | ❌                                          |

### 1.3 边界规则(明确"进 / 不进运行路径"的作用)

- **运行路径** = plugin 装到用户 Claude Code 后会被读 / 调用的部分(skills + templates + schema + scripts)
- **不进运行路径** = plugin 维护者自己看 + 开发者自测用;**用户装上 plugin 后不需要这些文件也能正常工作**
- **`scripts/requirements.txt` 是运行时依赖**:ingest 调 `scripts/convert-to-md.py` 需要 anydoc / paddleocr(均为 Python 包),用户必须先 `pip install -r scripts/requirements.txt`;**未装 SKILL.md 会先校验并提示**,不进入转换流程。query 在 wiki 规模较大时调 qmd(详见 §4.3),用户需另行 `npm install -g @tobilu/qmd`(可选,未装按阈值降级或 FAIL)。frontmatter 骨架 + schema 校验 + YAML 读写需要 jsonschema / pyyaml(详见 scripts/README.md)

### 1.4 scripts/ 与 hooks/ 的边界

CLAUDE.md 约束 "plugin 不带运行时"。**真实含义**:不开常驻进程 / 不对外暴露接口 / 不持续监听文件。scripts/ 与 hooks/ 都必须满足这条边界。

**scripts/ 约束**(Python 3.10+ 栈,详见 §2.4):

- ✅ 单次运行就退出(`python3 scripts/<name>.py <args>`,SKILL.md 默认显式调用避免依赖 PATH)
- ✅ **支持 `--batch` 多输入模式**(N 文件一次性喂入,内部共享单 Engine 实例,详见 §2.4 + §4.2.1) — 仍是单次进程跑完即退,**不**缓存 Engine 到下次调用
- ✅ 无状态(不读全局配置 / 不写 user-project 之外的缓存 / 不维护 session)
- ✅ 路径用相对路径(对齐 CLAUDE.md「代码中不得使用绝对路径」)
- ✅ 用 stdlib 优先(`subprocess.run` 不 fork 出脱离 Claude Code 生命周期的进程 / `signal.signal` 而非阻塞监听 / `sys.stdin` 不挂 resume)
- ❌ 不开 daemon / 不挂监听 / 不暴露服务
- ❌ 不监听文件系统变化
- ❌ 不调用 `${CLAUDE_PLUGIN_ROOT}`(plugin 装在 `~/.claude/plugins/cache/` 下,cache 易清)

**hooks/ 约束**(Python 3.10+ 栈,详见 §7):

- ✅ **事件回调同步跑完即退**(Claude Code 触发 SessionStart → 跑命令 → 退出)
- ✅ **只读不写 user-project**(hooks 不能动 inbox/raw/knowledge,只能向 system-reminder/conversation 注入提示)
- ✅ **可失败可跳过**(网络不通 / `git` 不可用 / 远程无响应 → 静默,不阻塞 plugin 启动)
- ❌ 不开持续后台进程(hooks 不能 fork 出脱离 Claude Code 生命周期的进程)
- ❌ 不监听文件系统变化
- ❌ 不修改 plugin 自身目录(`~/.claude/plugins/cache/...` 外的修改一律禁止)
- ✅ 允许用 `${CLAUDE_PLUGIN_ROOT}`(与 scripts/ 不同 —— hook 是 Claude Code 加载阶段跑,plugin 安装目录稳定可知;CLAUDE.md 路径约束是 user-project 内代码,plugin 本体 hooks.json 由维护者掌控)

**判断候选脚本/hook 是否允许加进 plugin**:执行模型是"agent(或 Claude Code)调一次,跑完退,产出结果或修改文件/注入提示",允许;是"持续跑 / 持续监听 / 对外暴露接口",不允许。

---

## 2. 目录与文件命名

### 2.1 用户项目目录(默认)

```
<user-project>/
├── inbox/                          # 暂存入口,G7,init 时建 + README + .gitkeep
├── scripts/                        # plugin 单次运行脚本(Python 3.10+,.py),init 时从 plugin 拷贝(详见 §2.4)
│   ├── _meta.json                  # 来源 plugin + 版本 + 同步时间
│   └── *.py                        # 至少:init-vault / lint-frontmatter / check-inbox-target
├── templates/                      # scripts 生成文件时读的"页模板源",init 时拷过来(详见 §2.5)
│   ├── source-page.md              # sources/ 页生成模板
│   ├── analysis-page.md            # analyses/ 页生成模板
│   ├── entity-page.md              # entities/<子类>/ 页生成模板
│   └── concept-page.md             # concepts/<子类>/ 页生成模板
├── raw/                            # 归档,不可变。init 时按 templates/raw-readme.md 的 15 类**全部预建默认子目录**,每个用 .gitkeep 占位 + raw-readme.md
│   ├── raw-readme.md
│   ├── 01_EE架构/.gitkeep
│   ├── 02_芯片/.gitkeep
│   ├── 03_通信与网络/.gitkeep
│   ├── 04_操作系统与中间件/.gitkeep
│   ├── 05_软件工程/.gitkeep
│   ├── 06_功能安全/.gitkeep
│   ├── 07_信息安全/.gitkeep
│   ├── 08_AI与AI工程/.gitkeep
│   ├── 09_域控制器/.gitkeep
│   ├── 10_会议与活动/.gitkeep
│   ├── 11_开发工具/.gitkeep
│   ├── 12_法规_标准_政策/.gitkeep
│   ├── 13_流程体系/.gitkeep
│   ├── 14_测试与验证/.gitkeep
│   └── 15_算法/.gitkeep
└── knowledge/                      # LLM 维护
    ├── SCHEMA.md
    ├── index.md
    ├── overview.md
    ├── glossary.md
    ├── log.md
    ├── sources/                    # type: source
    ├── entities/                  # 具象存在(7 子类)
    │   ├── person/                 # type: person
    │   ├── organization/           # type: organization
    │   ├── project/                # type: project
    │   ├── product/                # type: product
    │   ├── event/                  # type: event
    │   ├── place/                  # type: place
    │   └── other/                  # type: other
    ├── concepts/                  # 抽象知识(7 子类)
    │   ├── theory/                 # type: theory
    │   ├── method/                 # type: method
    │   ├── field/                  # type: field
    │   ├── phenomenon/             # type: phenomenon
    │   ├── standard/               # type: standard
    │   ├── term/                   # type: term
    │   └── other/                  # type: other
    ├── analyses/                   # type: analysis
    │   └── .gitkeep
    ├── comparisons/                # type: comparison(常驻对照页,query 自然触发)
    │   └── .gitkeep
    └── syntheses/                  # type: synthesis(常驻综合页,/aeps-llm-wiki-synthesize 触发)
        └── .gitkeep
```

### 2.2 raw/ 子目录分类机制

**权威字典**:[templates/raw-readme.md](templates/raw-readme.md) —— plugin 维护者直接编辑维护。完整的 15 类清单 + 边界规则全部在这份文件里,**不在本节重复**。

**Plugin 行为**:

1. **init 时**:从 templates/raw-readme.md 复制一份到 `<project>/raw/raw-readme.md`,**并按字典里的 15 类全部创建默认子目录**,每个用 `.gitkeep` 占位
2. **ingest 时**(inbox 入口):
   - LLM 读 `inbox/<file>` + `<project>/raw/raw-readme.md`
   - LLM 根据字典提议目标目录
   - **目标目录已存在**(包括 init 时预建的 15 类) → **直接放文件**,**无需人工拍板**
   - **目标目录不存在**(字典外的自定义目录,或 LLM 判定的二级子目录如 `12_法规_标准_政策/V2X/`) → **必须人工拍板**才创建并移动
   - 移动后写 `log.md`

**Plugin 不做**:

- ❌ 不实现分类决策(分类是 LLM 的判断,plugin 只提供字典)

**修改 raw-readme.md 的影响范围**(用户为王 + lint 提示):

- plugin templates/raw-readme.md 改了 → 已存在的用户项目,用户**再次调用 init skill** 时按"幂等再入"策略同步(详见 §4.1)
- **用户本地副本里新增的内容**(自定义目录说明、手动补充的边界规则等)**一律保留**,plugin 不删
- **用户本地副本里修改过的内容**(plugin 新版要加但用户改过的地方)**不覆盖**,lint 在报告里列出"plugin 新版有 X 条本地没有,要不要加?",由用户决定
- 用户可以**随时**手动调 init 触发同步;不会自动静默执行

**典型流程举例**:

| 用户动作                   | LLM 提议                       | 目录状态                                      | 是否拍板                    |
| -------------------------- | ------------------------------ | --------------------------------------------- | --------------------------- |
| 丢`inbox/iso26262.pdf`   | `raw/06_功能安全/`           | 已存在(init 预建)                             | ❌ 不需要,直接放            |
| 丢`inbox/v2x白皮书.md`   | `raw/12_法规_标准_政策/V2X/` | `12_法规_标准_政策/` 已存在,`V2X/` 不存在 | ✅ 需要拍板(创建二级)       |
| 丢`inbox/某内部规范.pdf` | `raw/16_公司内部/`           | 完全不存在                                    | ✅ 需要拍板(创建自定义目录) |

### 2.3 命名约定

- **目录**:遵循 raw/ 规范,可用中文 + `01_`~`15_` 编号 + `_` 分隔;**编号前缀保留**(用户希望目录按编号排序)
- **knowledge/ 内文件**:全小写、单词用 `-`(OKF 强烈推荐),例 `knowledge/concepts/field/okf.md`
- **analysis 页命名**:`knowledge/analyses/<ISO 8601 timestamp>-<slug>.md`,例:`2026-09-01T14-30-00z-okf-faq.md`
- **log.md 日期 heading**:`## YYYY-MM-DD`(裸日期,不带时间;带时间的写到条目的 timestamp 字段)
- **actor 字符串**(frontmatter `generated.by` / `verified.by`):
  - agent / 工具:`agent: <producer>/<plugin>`,例 `agent: producer/aeps-llm-wiki-plugin/0.4.0`(对齐 SCHEMA.md §4)
  - 人:`human:<id>`,例 `human:zhigang.liu`
  - 进程:`process:<id>`,例 `process:aeps-llm-wiki-lint`

### 2.4 用户项目 `scripts/` 目录

#### 为什么需要

SKILL.md 是 prompt(Llm 读),但**有外部依赖或系统调用**的逻辑(批量建目录、frontmatter jsonschema 校验、文件拍板门检测)用纯 prompt 不可靠,需要脚本。

**关键约束**:`CLAUDE.md` 第 5 条「代码中不得使用绝对路径」+ plugin 不带运行时(NFR-1)。所以:

- **不**调用 `${CLAUDE_PLUGIN_ROOT}`(plugin 装在 `C:\Users\ThinkPad\.claude\plugins\cache\` 下,cache 易清,symlink 易丢)
- **不**走 `npx` + npm(违背离线可用)
- **改**:把脚本**拷到 user-project 的 `scripts/`**,SKILL.md 用**相对路径** `./scripts/<name>.py` 调,**永远在 user-project 目录里跑**

#### 拷贝内容

由实现侧按 plugin 本体 `scripts/` 目录扫描拷贝,本文档不列举具体文件。具体清单随 plugin 版本演进,**prd/design 不维护列表**。

#### 运行时

- **Python 3.10+**(Claude Code 内置 Python;**单栈** —— scripts/ 与 hooks/ 统一,见 §7)
- **禁止**绝对路径、禁止 `${CLAUDE_PLUGIN_ROOT}`、禁止从 plugin 安装目录反向引用
- 脚本必须接受 `--project-dir <path>` 参数(默认 `.`),**不假设 cwd**
- SKILL.md 默认用 `python3 ./scripts/<name>.py ...` 显式调用(避免依赖 PATH + shebang);脚本顶部加 `#!/usr/bin/env python3` 仍允许双调用形式
- 脚本单次执行即退(`subprocess.run` 不 fork 出脱离 Claude Code 生命周期的进程,`signal.signal` 而非阻塞监听,`sys.stdin` 不挂 resume)

#### §2.4.1 scripts/*.py 无交互纯工具契约(硬约束)

`scripts/` 下的所有脚本必须为**无状态、无交互(Non-interactive)**的 CLI 工具。

**禁止调用清单**(等价 lint C10.1 静态扫描,详见 implement §C10.1):

| 禁止调用 | 替代方案 |
|---|---|
| `input()` / `input(prompt)` | SKILL.md 在 Claude 对话层发起交互,拍板结果通过参数传入 |
| `sys.stdin.read()` / `sys.stdin.readline()` | 同上 |
| `getpass.getpass()` | 完全禁 |
| `select.select([sys.stdin], ...)` 等 stdin 阻塞 | 同上 |

**输入约定**:所有流程控制(`--batch` / `--apply-plan` / `--project-dir`)一律通过**命令行参数**或 **JSON / YAML 配置文件**传入,严禁依赖 stdin / TTY / 环境变量隐式传入。

**人机交互边界**:

- ✅ **人机交互层**完全由 **SKILL.md(Claude Prompt)** 承担 —— 对话问答、拍板确认、错误恢复均走 SKILL.md 提示用户
- ✅ **scripts/ 仅负责机械式 IO 转换、校验、文件移动** —— 接收决策结果(命令行 / JSON 文件),执行,退出
- ✅ **`--apply` 模式**:scripts 读 `temp/decision-<hash>.json` 或 `temp/<id>-proposal.json` 这类已拍板文件,**不**重新发起任何 prompt

**调用方契约**:

- ✅ SKILL.md(Bash tool)显式 `python3 ./scripts/<name>.py [args]` 调用
- ✅ pytest 单测断言返回值 / 文件副作用
- ✅ hooks(Claude Code 事件驱动)调 scripts,**也不得交互**
- ❌ 用户手动 `cd <project> && python3 scripts/<name>.py` 直接跑决策性脚本(应走 SKILL.md 拍板)
- ❌ scripts 内部 `os.system` / `subprocess` 调起**第二次**交互式 CLI(交互污染)

**为什么硬约束**(详见 §4.2.x Q10 + §1.4):

- Claude Skill 调用时若脚本自己抓 stdin,会与 Claude tool use 流抢输入、状态不可预测
- 任何 `input()` 在非交互终端(如 CI / 自动化批处理)直接 EOFError 崩溃
- 脚本必须 idempotent / 可重试,主 agent 阶段 3 重跑时不能卡在等用户输入

#### Python 依赖

`scripts/requirements.txt` 是 scripts/ 的运行时依赖清单(强依赖,任何未装 → SKILL.md 跑前 FAIL 提示),init 时一并拷贝到 user-project:

```
# scripts/requirements.txt
anydoc>=0.3.0        # pptx/docx/xlsx/pdf → md
paddleocr>=2.7       # png/jpg/jpeg/bmp/tiff → md
jsonschema>=4.0      # frontmatter schema 校验
pyyaml>=6.0          # frontmatter 读写
pytest>=7.0          # tests/ 单测(运行时不需要,跑测试时需要)
```

**用户必须装**(自己虚拟环境 / venv 都行,plugin 不强制创建 venv):

```bash
pip install -r scripts/requirements.txt
```

**未装 → SKILL.md 跑前先校验**,提示"请先 `pip install -r scripts/requirements.txt`",**退出**(避免跑到一半才报缺包)。

#### SKILL.md 调用约定(convert-to-md.py)

ingest skill 跑前先校验依赖,再按扩展名分流调用。**两种调用形式**(单文件 / 批量):

```bash
# 单文件入口(按扩展名分流;inbox 仅 1 份文件时走这个)
python3 ./scripts/convert-to-md.py --project-dir . --input inbox/<file> --output <tmp-md-path>

# 批量入口(inbox 多文件时走这个;避免 N 次 paddleocr 冷启动,详见 §4.2.1 阶段 1)
python3 ./scripts/convert-to-md.py --project-dir . --batch inbox/<f1> inbox/<f2> ... inbox/<fn> --output-dir temp/
# SKILL.md 必须显式 Bash timeout: 600000ms(Claude Code max)
```

- **单文件模式**:`--input <file> --output <tmp-md-path>`,1 次冷启动处理 1 个文件
- **批量模式**:`--batch <f1> <f2> ... <fn> --output-dir temp/`,**单次进程内只初始化 1 次 paddleocr Engine / anydoc 实例**,依次处理 N 个文件,输出 `temp/<basename>.md`(N 份独立 md)
- 脚本内部按扩展名走"Claude converter → 降级 anydoc / OCR"的三段策略(详见 §4.2 步骤 2 表格)
- 两种模式都仍"单次跑完即退"(NFR-1 兼容,详见 §1.4);**不开 daemon、不缓存 Engine 到下次调用**(避免违反 NFR-1)

#### SKILL.md 调用约定(check-qmd.py)

query skill 跑前先探查引擎决策:

```bash
# 探查 qmd 可用性 + 数 knowledge 页数 → 返回 JSON
python3 ./scripts/check-qmd.py --project-dir .
```

- 输出:`{pageCount, qmdAvailable, qmdVersion, engine: 'index'|'qmd'|'fail', reason}`
- SKILL.md 据此决定走 4 跳扫描还是调 `qmd query`,以及是否降级(详见 §4.3)
- **`fail` 模式退出码非零**(SKILL.md 直接退出,提示用户装 qmd)

#### SKILL.md 写法约束(plugin 维护者 + LLM 写都遵守)

```bash
# ✅ 正确:相对路径 + 传 --project-dir
python3 ./scripts/<script>.py --project-dir .

# ✅ 正确(batch 模式):显式 Bash timeout 600000ms
python3 ./scripts/convert-to-md.py --project-dir . --batch inbox/<f1> inbox/<f2> --output-dir temp/

# ❌ 错误
python3 /absolute/path/to/scripts/<script>.py
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/<script>.py
python3 ~/.claude/plugins/cache/.../scripts/<script>.py
python3 ./scripts/<script>.py --raw-dir custom-raw    # 目录名固定,不允许自定义
python3 ./scripts/convert-to-md.py --batch ...       # 不显式 timeout(PaddleOCR 冷启动可能超时)
```

#### Sync 策略(plugin 升级时)

| 情况                                                     | 行为                                                                                 |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| plugin 新版**新增**脚本                            | 拷贝到 user-project`scripts/`                                                      |
| plugin 新版**修改了**脚本                          | **直接覆盖** user-project 副本(plugin 自带脚本以 plugin 本体为权威,升级时跟随) |
| 用户本地**新增**了脚本(如 `my-custom-check.py`) | **保留**,plugin 不动                                                           |
| 用户本地**删了** plugin 自带的脚本                 | 不补回,lint 提示"plugin 新版有 X 你本地没有"                                         |

**为什么用户本地修改不自动覆盖**:用户可能在 scripts/ 里写了自定义 helper,plugin 升级不能覆盖用户资产。

#### 与 NFR-1「plugin 不带运行时」兼容

scripts 是**单次执行就退**(`agent 调一次,跑完退,产出结果或修改文件`),符合 design §1.4 允许形态;不开 daemon、不挂监听、不对外暴露接口。

#### 不在 scripts/ 里的逻辑

- 纯 LLM 读源 + 写文件的(ingest 抽取概念、query 拼答案)→ 走 SKILL.md prompt,不要脚本
- 复杂 UI 交互(进度条、确认对话)→ 走 SKILL.md prompt
- 跨平台不确定的原生调用(Win32 API、macOS launchctl)→ **禁**,改用 stdlib

#### scripts/ 严禁交互硬契约(NFR-1 加严,Q10)

**问题根源澄清**:scripts/ 当前是空设计(M3 才落地),不存在"挂起卡死"的现实现状;但设计若**不**明确禁止交互式调用,未来实现者(图省事)很容易在脚本里写 `input()` 或 `sys.stdin.read()`,导致:
- 无交互终端调用时挂死(如 CI / git hook / 用户手动命令行)
- Claude Skill 调用时若脚本自己抓 stdin,会与 Claude 的 tool use 流抢输入、状态不可预测
- 单测无法跑(测试环境无 stdin)

**硬契约(NFR-1 加严)**:`scripts/*.py` 严禁任何形式的运行时交互,**纯函数工具**:

| 禁止调用 | 替代方案 |
|---|---|
| `input()` / `input(prompt)` | 由 SKILL.md 在 Claude 对话层发起交互,拍板结果通过参数传入 |
| `sys.stdin.read()` / `sys.stdin.readline()` | 同上 |
| `getpass.getpass()` | 完全禁 |
| `select.select([sys.stdin], ...)` 等待 stdin | 同上 |
| 任何阻塞事件循环(`while True: pass` 等) | 同 §1.4 NFR-1 单次运行即退约束 |

**scripts/ 边界**:scripts 是**机械执行器**(IO / 校验 / OCR / qmd / 命名飘检测),决策永远在 Claude 对话层(SKILL.md prompt)。scripts 接受**确定参数 + 配置文件**(如 `--apply temp/plan-<hash>.md`),按参数执行,不发起任何 prompt。

**lint C10 静态扫描断言**(M3 实现时加):`tests/test_no_daemon.py` 增加 `ast` 模块扫描所有 `scripts/*.py` 源文件,断言不出现 `input` / `sys.stdin.read` / `sys.stdin.readline` / `getpass` 调用。**违反 FAIL**。

**scripts/ 与 SKILL.md 责任分工**:

| 职责 | 谁负责 |
|---|---|
| 读 inbox 文件 / 提取文本 / OCR | scripts (`convert-to-md.py`) |
| LLM 提议 raw 子目录 / entity / concept 抽取 | SKILL.md (Claude LLM) |
| 拍板门(目标目录不存在 / 命名飘仲裁) | SKILL.md (Claude 对话问用户) |
| mv / mkdir / 写 log | scripts (`safe-mv.py` / `ensure-dirs.py` / `append-log.py`) |
| 提案 / 拍板落档(详见 §4.2) | SKILL.md 写 `temp/plan-<hash>.md` |
| 读 plan 文件应用 | scripts (CLI 参数 `--apply temp/plan-<hash>.md`) |

#### `_meta.json` 字段定义

init / re-run init 时,`<project>/scripts/_meta.json` 记录"这次 scripts/ 来自哪个 plugin 版本 + 什么时候同步的",用于后续 lint 报告"plugin 新版修改了 X.py,要采纳吗?"时定位 sync 来源。**没有用户价值,plugin 升级时总是覆盖**(详见 §4.1.1 scripts/ sync 策略)。

```json
{
  "plugin": "aeps-llm-wiki-plugin",
  "version": "<plugin 本体 plugin.json 的 version 字段,如 0.1>",
  "synced_at": "<ISO 8601 + 显式 UTC 偏移,如 2026-09-02T18:00:00Z>"
}
```

**字段说明**:

| 字段          | 类型             | 必填? | 含义                                                                                                |
| ------------- | ---------------- | ----- | --------------------------------------------------------------------------------------------------- |
| `plugin`    | string           | ✅    | plugin 名称(固定`aeps-llm-wiki-plugin`)                                                           |
| `version`   | string           | ✅    | 来自 plugin 本体`.claude-plugin/plugin.json` 的 `version` 字段;语义化版本 `MAJOR.MINOR.PATCH` |
| `synced_at` | string(ISO 8601) | ✅    | 本次 sync 触发时间;`init` 时 = init 触发时间;`re-run init` 时 = 当前时间                        |

**约束**:

- ❌ 不存任何 user-project 私有信息(防止 plugin 升级泄露)
- ❌ 不存 git commit hash / plugin 本体绝对路径(plugin 装在 `~/.claude/plugins/cache/` 下,cache 易清)
- ❌ 不存脚本内容 hash(增量 sync 不是 M2 范围,M5 再说)
- ✅ 文件只由 init skill 写,其他 skill 不动

### 2.5 用户项目 `templates/` 目录(B 简化版)

#### 职责边界

`templates/` 是 **scripts 生成文件时读的页模板源 + 全栈字典副本**,**不是**用户日常读的"操作手册 / 字典"主入口。后者(SCHEMA.md / raw-readme.md / inbox-readme.md)**按分散落位策略**进 knowledge/、raw/、inbox/。**全栈字典**(`concept-entities-readme.md` / `tag-template.md`)放 templates/ 顶层,因为它们涉及 knowledge/ 内所有页 + raw/,**不属于 raw 专属**。

三类文件切分:

| 类别                                             | 放在 user-project 哪                       | 谁读              | 例子                                                                                 |
| ------------------------------------------------ | ------------------------------------------ | ----------------- | ------------------------------------------------------------------------------------ |
| **页生成模板**(scripts 用)                 | `<project>/templates/`(B 简化版,新增)    | scripts(`.py`) | `source-page.md` / `analysis-page.md` / `entity-page.md` / `concept-page.md` |
| **全栈字典**(人 + LLM 读)                  | `<project>/templates/`(与页生成模板同层) | LLM agent + 用户  | `concept-entities-readme.md` / `tag-template.md`                                 |
| **子目录专属字典 / 操作手册**(人 + LLM 读) | 分散落到对应子目录顶层                     | LLM agent + 用户  | `knowledge/SCHEMA.md` / `raw/README.md` / `inbox/README.md`                    |

**判定规则**:横跨 ≥ 2 个 user-project 子目录的字典 → `templates/`;只与一个子目录相关的字典 / 操作手册 → 该子目录顶层。详见 §2.5.1 路由规则。

#### 拷贝内容(初始集)

| 文件                           | 类别       | 用途                                                                                                 |
| ------------------------------ | ---------- | ---------------------------------------------------------------------------------------------------- |
| `source-page.md`             | 页生成模板 | sources/ 页生成模板(3 节 H2 骨架:重点摘录 / 我的思考 / 总结)                                         |
| `analysis-page.md`           | 页生成模板 | analyses/ 页生成模板(同上 3 节)                                                                      |
| `entity-page.md`             | 页生成模板 | entities/<子类>/ 页生成模板(自由发挥,不锁骨架)                                                       |
| `concept-page.md`            | 页生成模板 | concepts/<子类>/ 页生成模板(自由发挥)                                                                |
| `concept-entities-readme.md` | 全栈字典   | 14 子类 ↔ 目录绑死表(entities × 7 + concepts × 7);被 SKILL.md 显式读、被 lint 显式对照            |
| `tag-template.md`            | 全栈字典   | 六轴受控词表(domain / layer / phase / docform / maturity / tec);被 SKILL.md 显式读、被 lint 显式对照 |

#### §2.5.1 路由规则:plugin 本体 `templates/*.md` 拷到 user-project 哪里

plugin 本体 `templates/` 下维护 7 份核心 .md(操作手册 / 字典 / 页生成模板)。init 时按"用途路由"散落到 user-project 不同位置,**不**全部堆在 user-project 顶层 `templates/`:

| plugin 本体`templates/` 文件                                                                        | 类型               | 拷到 user-project 哪里                         | 理由                                                                                       |
| ----------------------------------------------------------------------------------------------------- | ------------------ | ---------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `knowledge-SCHEMA.md`                                                                               | 操作手册           | `knowledge/SCHEMA.md`                        | SCHEMA 是 knowledge 操作手册,**只**与 knowledge 相关                                 |
| `knowledge-index.md` / `knowledge-overview.md` / `knowledge-glossary.md` / `knowledge-log.md` | knowledge 种子     | `knowledge/{index,overview,glossary,log}.md` | 同上                                                                                       |
| `raw-readme.md`                                                                                     | raw 专属字典       | `raw/README.md`                              | raw 15 类边界规则,**只**与 raw 相关                                                  |
| `inbox-readme.md`                                                                                   | inbox 专属提示     | `inbox/README.md`                            | 同上                                                                                       |
| `concept-entities-readme.md`                                                                        | **全栈字典** | `templates/concept-entities-readme.md`       | 14 子类 ↔ 目录映射涉及 entities/ + concepts/,**不属于 raw 专属**,放 templates/ 顶层 |
| `tag-template.md`                                                                                   | **全栈字典** | `templates/tag-template.md`                  | 六轴受控词表涉及 knowledge/ 内所有页 + raw/,**不属于 raw 专属**,放 templates/ 顶层   |
| `source-page.md`                                                                                    | 页生成模板         | `templates/source-page.md`                   | 通用页模板,与 skills 协作,放 templates/ 顶层                                               |
| `analysis-page.md`                                                                                  | 页生成模板         | `templates/analysis-page.md`                 | 同上                                                                                       |
| `entity-page.md`                                                                                    | 页生成模板         | `templates/entity-page.md`                   | 同上                                                                                       |
| `concept-page.md`                                                                                   | 页生成模板         | `templates/concept-page.md`                  | 同上                                                                                       |

**判定规则**:

1. **只在某个子目录使用** → 放那个子目录顶层(SCHEMA → knowledge/;raw-readme → raw/;inbox-readme → inbox/)
2. **横跨多个子目录的字典 / 页模板** → 放 user-project 顶层 `templates/`
3. **plugin 本体 `templates/` 不强求按此分组** —— plugin 维护者可以"全栈混放",init 时按上表路由,**user-project 顶层 `templates/` 自然只出现全栈字典 + 页生成模板**(不超过 6 份,清楚)

#### Sync 策略(同 §2.4)

文件级合并:plugin 新版新增模板 → 拷贝;plugin 新版修改模板 → user-project 副本不动,lint 报告让用户拍板;用户本地新增/删除 → plugin 不动。

---

## 3. frontmatter 契约(从 prd §6.2 抽出,机器读源)

### 3.1 字段分层

所有 OKF 概念文件 frontmatter 分四层。Plugin 必须强制 §A,支持 §B/§C,可忽略 §D。

#### §A — OKF v0.2 必填 + 强烈推荐

```yaml
---
type: source                          # 必填(OKF §4.1,§11)
title: Open Knowledge Format         # 推荐(OKF §4.1)
description: 一句话摘要               # 推荐(OKF §4.1)
---
```

合法 `type` 初始集合(在 `schema/frontmatter.schema.yaml` 定义,后续可扩):

**目录分组哲学**:参考 [`templates/concept-entities-readme.md`](templates/concept-entities-readme.md) 把可分类对象先分两大组:

- **Entities(具象存在)** —— "具体存在着什么?"人/事/物/组织/产品/地点
- **Concepts(抽象知识)** —— "这是什么类型的知识?"理论/方法/领域/现象/标准/术语

每组下面再分子类,**子类 ↔ 目录 ↔ type 值 三者 1:1:1 绑死**。

| 值(=`type`)    | 所在目录                             | 含义             | 来源                        |
| ---------------- | ------------------------------------ | ---------------- | --------------------------- |
| `source`       | `knowledge/sources/`               | 原始资料摘要     | OKF 常规                    |
| `analysis`     | `knowledge/analyses/`              | query 落档分析   | OKF 常规                    |
| `person`       | `knowledge/entities/person/`       | 个人             | concept-entities-readme §1 |
| `organization` | `knowledge/entities/organization/` | 组织             | concept-entities-readme §1 |
| `project`      | `knowledge/entities/project/`      | 项目 / 计划      | concept-entities-readme §1 |
| `product`      | `knowledge/entities/product/`      | 产品 / 工具      | concept-entities-readme §1 |
| `event`        | `knowledge/entities/event/`        | 事件 / 会议      | concept-entities-readme §1 |
| `place`        | `knowledge/entities/place/`        | 地点             | concept-entities-readme §1 |
| `other`        | `knowledge/entities/other/`        | 实体兜底         | concept-entities-readme §1 |
| `theory`       | `knowledge/concepts/theory/`       | 理论             | concept-entities-readme §2 |
| `method`       | `knowledge/concepts/method/`       | 方法 / 实践      | concept-entities-readme §2 |
| `field`        | `knowledge/concepts/field/`        | 领域             | concept-entities-readme §2 |
| `phenomenon`   | `knowledge/concepts/phenomenon/`   | 现象 / 问题      | concept-entities-readme §2 |
| `standard`     | `knowledge/concepts/standard/`     | 标准 / 规范      | concept-entities-readme §2 |
| `term`         | `knowledge/concepts/term/`         | 术语 / 概念词    | concept-entities-readme §2 |
| `other`        | `knowledge/concepts/other/`        | 概念兜底         | concept-entities-readme §2 |
| `comparison`   | `knowledge/comparisons/`           | 多源对照页(常驻) | Karpathy line 31            |
| `synthesis`    | `knowledge/syntheses/`             | 综合分析页(常驻) | Karpathy line 31            |
| `overview`     | `knowledge/overview.md`            | 顶层大图         | OKF bundle-root             |
| `schema`       | `knowledge/SCHEMA.md`              | Agent 操作手册   | plugin 自加                 |

**注意**:`type: other` 在 entities 和 concepts 目录都合法 —— **靠目录路径区分**,lint 必须联合目录路径校验。

**lint 规则**:未知 `type` 不报错(OKF §11 要求消费者容忍),但**给出建议**(可能拼错)。已知 type 但目录错位 → FAIL。

#### 字典升级规则(`templates/concept-entities-readme.md`)

权威字典: [`templates/concept-entities-readme.md`](templates/concept-entities-readme.md) —— plugin 维护者直接编辑维护。两段枚举(§1 Entities 7 子类 / §2 Concepts 7 子类) + 含义 + 例子全部在这份文件里,**不在本节重复**。

**Plugin 行为**:

1. **init 时**:复制一份到 `<project>/templates/concept-entities-readme.md`(对齐 templates/ 的同步策略,详见 §2.5.1)
2. **ingest/query/lint 时**:LLM 直接读 `<project>/templates/concept-entities-readme.md` 决定子类(用户项目副本为权威,plugin 本体仅供 plugin 维护者编辑);**SKILL.md 显式告诉 LLM "读用户项目里的 templates/concept-entities-readme.md"**

**Plugin 不做**:

- ❌ 不预建 entities/concepts 之外的自定义 type 子目录(用户要加新 type 走 `entities/other/` 或 `concepts/other/` 兜底,或者手动加目录)
- ❌ 不实现子类判定决策(完全由 LLM 决定,lint 只校验"目录 ↔ type"一致)

**修改字典的影响范围**(用户为王 + lint 提示):

- plugin 改了 `templates/concept-entities-readme.md`(比如新增 `entities/tool/` 子类)→ plugin 本体的 frontmatter.schema.yaml + SKILL.md 都要同步更新(type 枚举、SKILL 提示)
- 已存在的用户项目,用户**再次调用 init skill** 时按"幂等再入"策略同步(详见 §4.1)
- **用户本地副本里新增的内容**(自定义子类、手动补充的含义等)**一律保留**,plugin 不删
- **用户本地副本里修改过的内容**不覆盖,lint 在报告里列出"plugin 新版有 X 条本地没有,要不要加?",由用户决定
- 已存在的用户项目:升级 plugin 后,**用户在 lint 输出里会看到新增子类提示**;**不**自动创建 `entities/tool/` 目录,用户按需手动创建
- 用户已有 `type: <新子类>` 的文件但目录未建 → lint 给出警告 + 建议建目录

**lint 规则**:未知 `type` 不报错(OKF §11 要求消费者容忍),但**给出建议**(可能拼错)。

#### §B — OKF v0.2 新增家族(强烈推荐写,plugin 必须支持识别)

```yaml
---
# ... 继承 §A
# 1. Provenance(OKF §5.1)
sources:
  - id: okf-spec
    resource: raw/okf-spec.md
    title: OKF v0.2 SPEC
    author: team:google-cloud-data
    last_modified: 2026-07-25T00:00:00Z
# 2. Trust: how the content was generated(OKF §5.2)
generated:
  by: agent: producer/aeps-llm-wiki-plugin/0.4.0
  at: 2026-09-01T14:00:00Z
# 3. Trust: who verified(OKF §5.2)
verified:
  - { by: human:zhigang.liu, at: 2026-09-01T14:30:00Z }
# 4. Lifecycle: status(OKF §5.4)
status: stable
# 5. Lifecycle: stale_after(OKF §5.5)
stale_after: 2026-12-31T00:00:00Z
# 6. Cross-cutting(OKF §4.1 推荐)
resource: https://googlecloud.../okf
tags:
  - domain/standards
  - layer/platform
  - phase/design
  - maturity/standard
---
```

**强制约定**:

- 时间戳一律 ISO 8601 + 显式 UTC 偏移:`2026-09-01T14:00:00Z`(裸日期 `2026-09-01` 仅允许用于 `log.md` heading)
- `verified` 接受 list 或单 mapping(OKF §5.2 `Consumers MUST treat a bare mapping as a one-element list`)
- `status` 缺省 = `stable`

**`tags` 六轴受控词表设计**(plugin 行为约束,**OKF 字段 + plugin 强制写法**):

> OKF v0.2 §4.1 把 `tags` 定义为 "a YAML list of short strings for cross-cutting categorization",本身是 folksonomy 层。Plugin 在此基础上引入 **六轴受控词表**,解决两个真实痛点:拼写漂移(`autosar` / `AUTOSAR` / `Autosar` 三种写法)+ 维度混乱(同一 tag 跨多个语义维度)。详见 [`templates/tag-template.md`](templates/tag-template.md),权威字典。

**写法**:**`<axis>/<value>` 前缀命名空间**(如 `domain/ai`),Obsidian YAML 不解析为 map key,机读友好。**禁止**无前缀的裸 tag(`ai` 单独出现非法)。

**六轴**:

| axis         | 词数 | 单值/多值                                                                                   | 必填?         |
| ------------ | ---- | ------------------------------------------------------------------------------------------- | ------------- |
| `domain`   | 14   | 单值(软上限 ≤ 2,最多 5)                                                                    | ⚠️ 推荐必填 |
| `layer`    | 9    | 单值优先(纯物理/逻辑堆栈)                                                                   | 可选          |
| `phase`    | 8    | **可多值**(纯时间/研发阶段)                                                           | 可选          |
| `docform`  | 14   | **单值必填**(文档用途;详见 `templates/tag-template.md` §6)                         | ✅ 必填       |
| `maturity` | 5    | **单值必填**(`concept < research < pilot < production < standard`,用于笔记权重判断) | ✅ 必填       |
| `tec`      | ~45  | 单值优先                                                                                    | 可选          |

**LLM 工作流**(SKILL.md 显式告诉 LLM):

1. 读源文件 → 候选 tag 草稿
2. 读 `templates/tag-template.md` 比对**六轴**词表
   - 候选 tag ∈ 词表 → 采用,加 axis 前缀
   - 候选 tag ∉ 词表 → 同义/近义词表词 → 用词表词替代 + WARN;新概念 → 提议加入字典 + 临时用自由 tag + WARN
3. 落 frontmatter,例:`tags: [domain/ai, layer/algorithm, phase/design, phase/verification, maturity/research]`
4. log.md 记一笔 "tags: 取自字典 X 个,字典外 Y 个"

**lint 规则**(对应 §4.4):

| 现象                                                  | 行为                                            |
| ----------------------------------------------------- | ----------------------------------------------- |
| 裸 tag(`ai` 无前缀)                                 | FAIL                                            |
| 字典外 tag                                            | WARN,累计 ≥ 5 次建议下次 plugin 升级时加入字典 |
| 缺失`maturity/`                                     | FAIL(必填)                                      |
| 缺失`domain/`                                       | WARN                                            |
| 单页`domain` > 5 个                                 | 提示"切片失去区分度,建议合并"                   |
| 同一 axis 重复(如`domain/ai` 出现 2 次)             | FAIL                                            |
| 拼写变体聚类(`autosar` / `AUTOSAR`)               | WARN,推荐字典 prefLabel                         |
| 词序变体(`autosar-adaptive` / `adaptive-autosar`) | WARN,推荐字典 prefLabel                         |
| 频次 ≥ 10                                            | "热门,可考虑固化"                               |
| 频次 = 1                                              | "冷僻,真的需要保留?"                            |

**理论参考**(轻量版,详细见 `templates/tag-template.md` §1、§8):

- **SKOS `ConceptScheme`** + `prefLabel`:字典本身 = 词表;每个词唯一推荐写法
- **OWL Disjointness**:同一轴内词条两两不相交(字典已实现)
- **OWL Naming Conventions**:全小写 + `-` 连字符 + 无版本/状态
- **不升级到 full ontology**:tag 字段保持自由字符串,关系由字典承载

**trust tier 推断**(派生信号,**不落 frontmatter**):

- 无 `verified` ⇒ `unverified`
- 仅非 `human:` actor ⇒ `machine-confirmed`
- 有 `human:` ⇒ `human-reviewed`

#### §C — Karpathy 模式扩展(plugin 内部约定,OKF 工具忽略)

OKF §4.1 允许任意扩展键,消费者保留但不解析。Plugin 只用做 OKF 原生无法表达的事:

```yaml
---
# ... 继承 §A 和 §B
updated: 2026-09-15T10:00:00Z      # OKF 无对应字段,plugin 自己加
summary: |
  Open Knowledge Format 是 Google Cloud 推出的厂商中立 markdown 知识格式规范。
  本文覆盖 v0.2 规范:frontmatter 分层、bundle-root、链接规范、log 格式。
---
```

**字段集合**(plugin 内部允许的扩展,**仅两个**):

| 字段        | 类型               | 用途                            |
| ----------- | ------------------ | ------------------------------- |
| `updated` | ISO 8601 timestamp | 最后修改时间(OKF 无对应)        |
| `summary` | string (multiline) | 长摘要(2-5 段),详见下方写作纪律 |

**字段命名原则**(plugin 维护者遵守,LLM 写入时遵守):

- 能在 OKF 原生字段表达 → **必须**用 OKF 原生。已清理掉的冗余字段:
  - `sources_internal` → 用 OKF `sources`
  - `created` → 用 OKF `generated.at`
- 不允许再扩展新字段;Lint 遇到未在白名单的扩展键 → warning

**写作纪律:摘要归属**(plugin 强制,LLM 写入 / lint 校验都遵守):

- **长摘要一律写进 frontmatter `summary` 字段**(2-5 段 multiline)
- **正文里禁止出现 `## 摘要` / `# 摘要` / `## Summary` / `# Summary` 小节**
- `description` 仍然是一句话短摘要(OKF §A 推荐字段),`summary` 是长摘要
- 例外:聚合类页面(`type: comparison` / `type: synthesis`)允许在正文用 `## 对照表` / `## 综合结论` 这类**具体内容**小节,不要用通用名"摘要"

**为什么这样设计**(回应"为什么不让正文写 ## 摘要"疑问):

- **`description` 太短**:LLM 想给概念页写一段完整概述时没地方放,长摘要必须有归属 —— 走 frontmatter `summary`(2-5 段 multiline)而非正文 `## 摘要`
- **避免正文顶部冗余小节**:如果正文允许 `## 摘要`,每页顶部都会有这个通用名小节,UI 重复且无信息密度;**强制**用 `## 重点摘录` / `## 我的思考` / `## 总结:最有收获的一句话` 这种**有语义角色**的 3 节骨架,读者一进页面就知道"这段是源文摘录 / 这是我的思考 / 这是结论"
- **OKF v0.2 不规定正文必须有 `## 摘要`**:OKF spec §4-§6 只规定 frontmatter 必填 `type:`,**未**对正文小节命名做强制要求;Karpathy LLM-wiki 风格 wiki 同样鼓励 frontmatter 摘要 + 正文结构化小节。我们的纪律**与 OKF / Karpathy 一致**,并非冲突
- **frontmatter `summary` 字段是机器 + 人双通道**:OKF 工具读 `summary`(机器)、Obsidian 笔记属性面板显示 `summary`(人);**与正文摘要小节是**双轨而非冗余 —— 一个走 frontmatter / 一个走结构化正文
- **prd §1.5 + design §0 一致**:prd.md 行 127/157/172/179 与本节同步写"禁止 `## 摘要` 小节",并非 design 单方面强加
- **若用户**坚持要"人类可读 Markdown 单文件分发"场景(导出 markdown 给无 Obsidian 的读者),应通过 **OKF reader 渲染**生成 `summary-prose.md`(把 frontmatter `summary` 转成 H2 段落),**不**回写原页 — 保持数据源唯一(frontmatter),避免双源漂移

#### §D — bundle 根 `index.md` 专用(OKF §8 / §12)

```yaml
---
okf_version: "0.2"
---
```

- 只有 bundle 根的 `index.md` 允许带 frontmatter
- 只允许 `okf_version` 一个键
- 非 bundle 根的 `index.md` 一律无 frontmatter

### 3.2 `schema/frontmatter.schema.yaml` 设计

```yaml
# 顶层
required: [type]                        # OKF 必填
recommended: [title, description]       # OKF 推荐
extensions:                             # 允许的扩展键(白名单),其它 lint 报警
  okf:
    - sources
    - generated
    - verified
    - status
    - stale_after
    - resource
    - tags  # 六轴受控词表设计:详见 §3.1 §B 与 templates/tag-template.md
    - last_modified
    - timestamp
  plugin:
    - updated
    - summary

# type 合法值(与 §3.1 表对齐,entities/concepts 14 子类由 templates/concept-entities-readme.md 字典为权威;另含 `source` `analysis` `comparison` `synthesis` 共 4 个非子类类型;`knowledge/` 顶层合计 17 个子目录 = sources + 7 entities + 7 concepts + analyses + comparisons + syntheses)
type_enum:
  # 资料与分析
  - source
  - analysis
  # Entities(具象存在) — 7 子类
  - person
  - organization
  - project
  - product
  - event
  - place
  - other  # entities/other 兜底
  # Concepts(抽象知识) — 7 子类
  - theory
  - method
  - field
  - phenomenon
  - standard
  - term
  - other  # concepts/other 兜底(与 entities/other 靠目录路径区分)
  # Karpathy 常驻聚合页
  - comparison
  - synthesis
  # bundle-root 特殊页
  - overview
  - schema

# actor 字符串格式
actor_patterns:
  agent: '^agent: producer/[a-z0-9-]+/[0-9]+\.[0-9]+\.[0-9]+$'    # 例 agent: producer/aeps-llm-wiki-plugin/0.4.0(对齐 SCHEMA.md §4)
  human: '^human:.+$'                            # 例 human:zhigang.liu
  process: '^process:.+$'                         # 例 process:weekly-lint

# tags 值格式(强制前缀命名空间)
tags_format:
  pattern: '^(domain|layer|phase|docform|maturity|tec)/[a-z][a-z0-9-]*$'    # 强制 <axis>/<value>,value 全小写 + 连字符
  vocabulary_source: templates/tag-template.md                 # 六轴词表权威字典
  maturity_required: true                                       # maturity 单值必填
  docform_required: true                                        # docform 单值必填(对照 §1 设计原则)
  domain_max_per_page: 5                                        # 软上限
```

### 3.2.1 扩展工作流(US-6:加新实体/概念类型)

**触发场景**:用户要加新 type(例:`entities/tool/` 或 `concepts/protocol/`),plugin 维护者要加新一档字段到 schema。

**权威依据**:变更必须保证"三件套同步",否则 lint 误报或 SKILL.md 行为不一致。

**3 步走**(每步必跑自检):

1. **改 `schema/frontmatter.schema.yaml`** —— `type_enum` 列表追加新值,如有新 frontmatter 字段也在 `extensions.plugin` / `extensions.okf` 白名单追加
2. **改 `templates/concept-entities-readme.md`** —— 对应 H2 章节(§1 Entities 或 §2 Concepts)追加新子类条目 + 含义 + 例子 + 目录名(`<entities|concepts>/<子类>/`)
3. **新项目 init 自检** —— `python3 ./scripts/init-vault.py --project-dir /tmp/<test-vault>`,验证:
   - `<entities|concepts>/<新子类>/.gitkeep` 自动建好
   - 在 `/tmp/<test-vault>/templates/concept-entities-readme.md` 副本里看到新子类条目
   - 写一份 fixture `<新子类>.md`,跑 `python3 ./scripts/lint-frontmatter.py`,断言不报"未知 type"
   - 跑 `python3 ./scripts/lint-frontmatter.py --fix` 验证派生/补缺路径仍正常

**变更传播路径**:

| 改的文件                                               | 影响范围                                                            | 自检方法                            |
| ------------------------------------------------------ | ------------------------------------------------------------------- | ----------------------------------- |
| `schema/frontmatter.schema.yaml` 的 `type_enum`    | 所有 SKILL.md(写页时引用 type)+ lint 脚本                           | lint 自检                           |
| `schema/frontmatter.schema.yaml` 的 `extensions.*` | lint(未知扩展键警告)                                                | 写一份带新扩展键的 fixture 验证     |
| `templates/concept-entities-readme.md`               | 所有 SKILL.md 显式读(instruct LLM 比对字典)+ lint 子类 ↔ 目录 校验 | init 副本验证 + lint 自检           |
| `templates/tag-template.md`(新 axis 或新词)          | ingest/query/lint 走 tag 校验的全部路径                             | 写一份带新 axis tag 的 fixture 验证 |
| `knowledge/SCHEMA.md`(用户项目副本)                  | 由 init 自动覆盖(详见 §4.1),plugin 维护者**不需要手动改**    | re-run init 验证                    |

**plugin 升级到已有项目**:用户跑 `/aeps-llm-wiki-init`(幂等再入,详见 §4.1.1)→ 字典 sync 走 append 策略(§4.1.1 字典文件 sync 策略段),用户本地副本里"自定义子类/自定义 tag"**保留**,plugin 新版内容**append**到对应 H2 末尾。

### 3.3 链接约定(从 prd §6.2 §E 抽出)

- **正文 wiki link 走 `[[wikilink]]` 一等公民**(Q6):`[[page]]` / `[[page|显示]]` / `[[page#章节]]`,Obsidian 原生可双链跳,Karpathy 老 wiki 无需转换
- 优先 bundle-relative 绝对路径:`[customers](/tables/customers.md)`(OKF §6.1 推荐)
- 也接受相对路径:`[neighbor](./other.md)`
- frontmatter `links:`(OKF §9 推荐字段)由 plugin 维护镜像,与正文 `[[wikilink]]` 自动同步(Q6 OKF 兼容性靠它,详见 §3.6)
- 链接类型(父子 / 引用 / 依赖)由**正文描述**,不由链接类型化
- plugin 必须容忍断链(OKF §6.1:不是 malformed)

### 3.4 `log.md` 格式(从 prd §6.2 §F 抽出)

```markdown
# Directory Update Log

## 2026-09-01
* **Creation**: Established [Open Knowledge Format](../concepts/open-knowledge-format.md).
* **Update**: Updated [glossary](../glossary.md).

## 2026-08-25
* **Creation**: Initialized foundational directory structure (first init).
```

**强制**:

- 日期 heading 一律 ISO 8601 `YYYY-MM-DD`
- **最新在前**
- 粗体前缀仅五种(plugin 强制以便 lint 解析):
  - `**Creation**` —— 新建 wiki 页
  - `**Update**` —— 修改既有 wiki 页(增删正文段、改 frontmatter)
  - `**Deprecation**` —— 归档 / `status: deprecated`
  - `**Migration**` —— inbox → raw 文件迁移
  - `**LintFix**` —— lint `--fix` 自动应用的结构修复记录(详见 §4.4)
- inbox → raw 迁移 log 模板:`**Migration**: [file.md](inbox/file.md) → [file.md](../raw/<subdir>/file.md)`
- lint `--fix` 修复记录模板:`**LintFix**: <rule-name> on [file.md](<path>) — <one-line summary>(如 frontmatter 字段补缺 / 3 节骨架补占位)`

### 3.5 `knowledge/` 种子文件(顶层 5 个)

| 文件            | 谁写                                    | 模板                                | 模板里要锁什么                                                                                                                                                                                                                                                                                                                                         |
| --------------- | --------------------------------------- | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `index.md`    | LLM 每次 ingest/query 后自动维护        | `templates/knowledge-index.md`    | ✅**格式锁**:OKF frontmatter(`type` 必填,`bundle-root: true` 标记,§D);条目格式 `- [name](path) — type · 一句话`;排序规则(按 type 分组?按字母?);空状态文案("还没有条目,先把资料丢进 inbox/ 再跑 /aeps-llm-wiki-ingest")                                                                                                                  |
| `overview.md` | LLM 视情况更新(大图变化时)              | `templates/knowledge-overview.md` | ⚠️**格式软锁**:frontmatter `type: overview` + `bundle-root: true`;**结构骨架锁**(标题层级:领域全景 / 关键概念 / 当前工作重点 / 待补),具体内容 LLM 自由发挥                                                                                                                                                                           |
| `glossary.md` | LLM 在 ingest 时新增/修改术语           | `templates/knowledge-glossary.md` | ✅**条目格式锁**:`**术语** (英文) — 一句话定义`;**不带 frontmatter**(索引体不是 wiki 页);排序规则(中英按拼音)                                                                                                                                                                                                                           |
| `log.md`      | LLM 在每次变更后追加一条(多 skill 共写) | `templates/knowledge-log.md`      | ✅**格式锁严**:ISO 8601 时间戳;**最新在前**;条目模板 `**Action**: <verb> <object> by <actor>` + 关联路径链接;actor 字符串约定(`agent: producer/aeps-llm-wiki-plugin/<version>` / `human:<id>` / `process:<id>`,与 SCHEMA.md §4 一致);粗体前缀仅 `Creation/Update/Deprecation/Migration/LintFix` 五种(plugin 强制以便 lint 解析) |
| `SCHEMA.md`   | plugin 在 init 时一次性写入             | `templates/knowledge-SCHEMA.md`   | ✅**格式锁 + 内容锁**:frontmatter(`type: schema`);完整目录结构图(用户项目视角)+ frontmatter schema(§A §B §C 三层)+ skill 操作手册(ingest/query/lint 步骤)+ 链接约定 + log 格式。**这是 LLM 的操作手册,不能漂**                                                                                                                        |

> **澄清(防止读者混淆)**:SCHEMA.md 的"内容锁"指**骨架** —— 目录结构图、三个工作流(ingest/query/lint)步骤、链接约定、log 格式。**frontmatter 字段集合不重复列**,在 SCHEMA.md 里**直接引用** plugin 本体的 `schema/frontmatter.schema.yaml`(权威源)。三件套权威顺序:**OKF 规范** > `schema/frontmatter.schema.yaml` > `knowledge/SCHEMA.md`。前者是字段机器读定义,后者是给人 + LLM 读的入口;改 schema.yaml 后,SCHEMA.md 的引用自动指向新版本,**不需要改 SCHEMA.md 里的字段列表**。

### 3.6 `knowledge/` 类型子目录与正文骨架

子目录与 `type` 1:1:1 绑死 —— `type: person` 必在 `entities/person/`,`type: theory` 必在 `concepts/theory/`,等等(违规由 lint FAIL)。完整 type ↔ 目录 ↔ 含义 三联表见 §3.1 §A。

| 子目录                     | OKF`type`      | 模板要锁什么                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| -------------------------- | ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sources/`               | `source`       | ✅**frontmatter + 正文骨架都锁死**。frontmatter type-specific 必填字段:`source_file`(指向 `raw/<subdir>/<file>`)+ `summary`(≤ 280 字符,长摘要走 `summary` 字段纪律见 §3.1 §C)。**正文禁止出现 `## 摘要` 小节**(纪律见 §3.1 §C)。正文 **3 节骨架硬约束**(任何缺失 = lint FAIL):`## 重点摘录`、`## 我的思考`、`## 总结:最有收获的一句话`。`## 我的思考` 用第一人称。**raw_category 派生字段**:不在 frontmatter 写死,而是从 `sources[0].resource` 路径解析得到,例 `resource: raw/12_法规_标准_政策/okf-spec.md` → `raw_category: 12_法规_标准_政策`。lint 报告支持按 `raw_category` group by,便于扫"法规相关的源页"。详见 §3.6.1。字段完整集合与 SCHEMA.md §2.2 一致。 |
| `entities/person/`       | `person`       | ⚠️**frontmatter 锁**(`type: person` + `aliases:[]` + `summary`,字段完整集合见 SCHEMA.md §2.2 entity/concept 必填项),**正文自由发挥**(人物页通常包含:身份、关键贡献、引用源)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `entities/organization/` | `organization` | ⚠️**frontmatter 锁**;**正文自由发挥**(组织页通常包含:领域定位、代表产品/项目、引用源)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `entities/project/`      | `project`      | ⚠️**frontmatter 锁**;**正文自由发挥**(项目页通常包含:范围、时间线、关键里程碑、引用源)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `entities/product/`      | `product`      | ⚠️**frontmatter 锁**;**正文自由发挥**(产品页通常包含:定位、关键参数、典型应用、引用源)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `entities/event/`        | `event`        | ⚠️**frontmatter 锁**;**正文自由发挥**(事件页通常包含:时间、地点、参与者、产出)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `entities/place/`        | `place`        | ⚠️**frontmatter 锁**;**正文自由发挥**(地点页通常包含:地理位置、相关活动/组织)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `entities/other/`        | `other`        | ⚠️**frontmatter 锁**;**正文自由发挥**(兜底)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `concepts/theory/`       | `theory`       | ⚠️**frontmatter 锁**;**正文自由发挥**(理论页通常包含:核心命题、推导过程、适用边界)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `concepts/method/`       | `method`       | ⚠️**frontmatter 锁**;**正文自由发挥**(方法页通常包含:适用场景、步骤、工具链、对比其他方法)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `concepts/field/`        | `field`        | ⚠️**frontmatter 锁**;**正文自由发挥**(领域页通常包含:范畴、关键问题、与相邻领域关系)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `concepts/phenomenon/`   | `phenomenon`   | ⚠️**frontmatter 锁**;**正文自由发挥**(现象页通常包含:现象描述、根因分析、影响、应对)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `concepts/standard/`     | `standard`     | ⚠️**frontmatter 锁**;**正文自由发挥**(标准页通常包含:发布机构、版本、约束范围、与相邻标准关系)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `concepts/term/`         | `term`         | ⚠️**frontmatter 锁**;**正文自由发挥**(术语页通常包含:定义、起源、典型用例、相邻术语)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `concepts/other/`        | `other`        | ⚠️**frontmatter 锁**;**正文自由发挥**(兜底)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `analyses/`              | `analysis`     | ✅**frontmatter + 正文骨架都锁死**(query 落档强制套)。frontmatter type-specific 必填:`answer_to`(原问题)+ `generated_by: agent: producer/aeps-llm-wiki-plugin/<version>` + 长摘要走 `summary` 字段(必须**首行保留 query 原问句** `**问题**: <原问句>`,纪律见 §3.1 §C)。**正文禁止出现 `## 摘要` 小节**。正文 **3 节骨架硬约束**(任何缺失 = lint FAIL):`## 重点摘录`、`## 我的思考`、`## 总结:最有收获的一句话`。字段完整集合与 SCHEMA.md §2.2 一致。                                                                                                                                                                                                                               |
| `comparisons/`           | `comparison`   | ⚠️**frontmatter 锁**(`type: comparison` + `sources:` ≥ 2 条 `[[wikilink]]` 链接到对比的 entity/concept 页 + `last_updated`);**正文自由发挥**,但典型结构:多栏对照表 + 维度差异 + 各自适用场景                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `syntheses/`             | `synthesis`    | ⚠️**frontmatter 锁**(`type: synthesis` + `topic:` + `sources_count` 引用了多少页 + `last_updated`);**正文自由发挥**,但典型结构:主题脉络梳理 + 多观点融合 + 个人判断                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |

**为什么 `sources/` 和 `analyses/` 要锁死正文而其他 type 不锁**:

- 这两类是**个人色彩最重**的页(读后感 + 思考),骨架统一便于快速浏览、横向对比、长期复盘
- 其他 type(14 个 entities/concepts 子类 + comparison + synthesis)是**客观/结构化内容**,强加"我的思考"会污染 OKF 工具消费的语义,只能 LLM 自由发挥
- `comparison` 用对照表 + 维度差异更自然,`synthesis` 用脉络梳理 + 多观点融合更自然 —— 这俩**不**用 `sources/analyses` 的 3 节骨架

**lint 规则**(对应 §4.4):

- `sources/*.md` / `analyses/*.md` 必含 3 节 H2 标题(`## 重点摘录`、`## 我的思考`、`## 总结:最有收获的一句话`),**逐字匹配**,缺一即 FAIL
- `sources/*.md` / `analyses/*.md` **禁止**含 `## 摘要` / `## Summary` H2 标题(纪律见 §3.1 §C),命中即 FAIL
- 其他 type 不检查 H2 骨架
- `analyses/*.md` 的 `summary` 字段首行必须含 `**问题**:` 前缀(LLM 在写完后必须保留 query 原问句作为引用锚;从原正文移到 summary)
- 14 子类目录的 .md 必须 frontmatter `type` 等于该目录对应的子类值(目录 ↔ type 联合校验),违规 FAIL

#### §3.6.1 `raw_category` 派生字段约定

**动机**:`raw/` 按 15 类子目录组织(来自 `templates/raw-readme.md`),`knowledge/sources/` 想"复制 raw 目录的接口"—— 浏览/查询时按 raw 分类 group by,但**不改 sources/ 目录结构**(否则破坏 §3.6 的"子目录 ↔ type 1:1:1 绑死"原则,因为 source 永远只有一个 `type: source`,没有子类)。

**字段定义**:

- **派生字段,不在 frontmatter 写死**:由 lint / query 在运行时从 `sources[0].resource` 路径解析得到
- **解析规则**:`raw_category = sources[0].resource.split('/')[1]`(取路径第二段,即 raw 一级子目录名)
- **示例**:

  ```yaml
  sources:
    - id: okf-spec
      resource: raw/12_法规_标准_政策/okf-spec.md   # 第二段是分类
  ```

  派生得到 `raw_category: 12_法规_标准_政策`

**为什么是派生而非写死**:

- **零迁移成本**:已有 source 页无需补字段,lint 自动从现有 frontmatter 计算
- **零同步问题**:raw 分类改名 / 迁移 / 拍板门后,`raw_category` 跟着 `sources[0].resource` 走,**没有双源不一致风险**
- **零 frontmatter 噪声**:不污染 frontmatter,OKF 工具扫描时不感知 plugin 私有字段

**派生失败处理**(lint 行为):

- `sources[0]` 缺失 → lint WARN "无法派生 raw_category,sources[0] 缺失"
- `sources[0].resource` 不是 `raw/<category>/<file>` 格式(异常路径,可能是 URL 或外部引用) → lint WARN "raw_category 无法派生,resource 不是 raw/ 本地路径"
- 派生得到的 `raw_category` 不在 `templates/raw-readme.md` 的 15 类清单内 → **FAIL**(说明 ingest 漏走拍板门,文件落到了非预建目录)

**lint group by 能力**:

```
$ /aeps-llm-wiki-lint --by raw_category

按 raw_category 分组报告(便于扫"法规相关的源页"):

[12_法规_标准_政策] 8 篇
  - sources/okf-spec.md
  - sources/un-r155.md
  - ...
[06_功能安全] 5 篇
  - sources/iso26262-asil-d.md
  - ...
[06_功能安全 + 12_法规_标准_政策] 1 篇(罕见,跨分类 source)  ← 同一 source 引用了多个 raw 文件
  - sources/v2x-cybersecurity.md
[未分类] 2 篇
  - sources/legacy-doc.md        ← raw_category 派生失败
  - sources/url-only-ref.md      ← 外部引用
```

**query 过滤能力**:

- 用户问"X 分类相关的资料",query 走 raw_category 过滤 candidate source 页,不用扫全集
- 用户问"X 分类下哪些 entity/concept 被引用过",query join raw_category 过滤

**为什么不做候选 A(目录镜像)**:

- A 方案 `knowledge/sources/<分类>/<basename>.md` 会破坏 §3.6"子目录 ↔ type 1:1:1 绑死"
- A 方案需要 frontmatter 新增 `raw_category` 字段(写死),引入双源不一致风险(目录名改了但 frontmatter 没改)
- B 方案派生字段**零成本拿到 80% 价值**(group by + 过滤),无目录结构变动

#### §3.6.1.1 `source_file` + `sources[].resource` 双字段同源(source 页)

**动机**:`type: source` 的页需要指回 `raw/<subdir>/<file>` 原始文件。当前设计用 OKF §5.1 的 `sources[].resource` 字段(机器可读),但 Obsidian UI 不解析 frontmatter 任意字段为可点击链接——用户点不到原始文件(Q9)。

**新方案**:`type: source` 页 frontmatter 同时含两个字段,值同源:

| 字段 | 类型 | 谁读 | 作用 |
|---|---|---|---|
| `source_file:` | 顶层字符串 | **Obsidian UI**(笔记属性面板) | Obsidian 识别 `source_file` 字段为可点击链接,用户点这个字段值就能跳转 / 打开原始文件 |
| `sources[0].resource` | OKF §5.1 数组元素 | **OKF reader / lint / 外部工具** | OKF v0.2 spec 必填,机器可读 + 带 id / title / author / last_modified provenance |

**为什么不只留一个**:

- 单留 `source_file:` → OKF 工具不识别(非 spec 字段)、失去 provenance 子字段
- 单留 `sources[].resource:` → Obsidian 用户在笔记属性面板看不到可点击链接(Q9 解决不了)
- 两个并存 = Obsidian 用户能点 + OKF reader 能消费 + lint 能校验一致性,零妥协

**示例**:

```yaml
type: source
title: Andes Overview and RISC-V Solutions
source_file: raw/02_芯片/Andes Overview and RISC-V Solutions_260130.pdf   # Obsidian 可点
sources:
  - id: andes-overview-risc-v
    resource: raw/02_芯片/Andes Overview and RISC-V Solutions_260130.pdf   # OKF §5.1
    title: Andes Overview and RISC-V Solutions
    author: "Andes Technology(晶心科技)"
    last_modified: 2026-08-28T00:00:00Z
```

**lint C5 一致性断言**:`source_file` 与 `sources[0].resource` **必须值相等**(同源)。不一致 FAIL。

**`raw_category` 派生继续走 `sources[0].resource`**(不变):§3.6.1 解析规则 `raw_category = sources[0].resource.split('/')[1]` 不受新字段影响。

#### §3.6.2 frontmatter `links:` 镜像字段(Q6 OKF 兼容机制)

**动机**:正文 wiki link 走 `[[wikilink]]` 一等公民(Q6),但 OKF v0.2 外部工具读 wiki 时可能不识别 `[[wikilink]]` 语法。frontmatter `links:`(OKF v0.2 §9 推荐字段)以结构化形式记录所有出链,使 OKF 工具无需解析正文即可消费链接。

**镜像机制**:

- 字段名:`links`(top-level array of {type, target} 对象,OKF v0.2 §9 约定)
- 写时机:plugin 在每次写页 / `--fix` lint / ingest 结束时,**自动扫描正文所有 `[[wikilink]]` 与 `[text](path.md)` 链接,生成对应 `links:` 字段值**(全量覆盖,不增量)
- 读时机:外部 OKF 工具读 frontmatter `links:` 字段,无需解析正文
- 唯一数据源 = **正文 wiki link 扫描**(`links:` 是镜像输出,不是 source of truth)

**示例**:

```yaml
type: concept
title: AUTOSAR 方法论
links:
  - type: wikilink
    target: entities/project/aeps-platform.md
  - type: wikilink
    target: concepts/standard/iso-26262.md
  - type: markdown
    target: concepts/standard/iso-21434.md
```

**lint C4.2 漂移断言**(详见 implement §C4.2):

- 扫正文 wikilink + markdown link
- 与 frontmatter `links:` 对比,差异(Wikilink 漏登记 / `links:` 多余)→ WARN
- `--fix` 模式:自动重生成 `links:` 字段(全量覆盖,user 拍板写入)

**对 ingest / query 的影响**:

- ingest 写 source / entity / concept 页时,扫正文 wikilink 自动生成 `links:`
- query 4 跳扫描中跳 3 顺正文 `[[wikilink]]` 跳邻居 —— 不变(仍读正文,不读 `links:`)
- lint `--fix` 自动同步 `links:` 与正文

**配套模板文件**(init 时复制/填充):

| 模板文件                            | 内容                                                                                                                                                                                                        |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `templates/raw-readme.md`         | 字典本体(15 类 + 边界规则)—— ✅ 已存在                                                                                                                                                                    |
| `templates/inbox-readme.md`       | 简版提示,告诉用户"放什么、放完跑 ingest"                                                                                                                                                                    |
| `templates/knowledge-SCHEMA.md`   | 锁得最严(8 节,占位符 init 替换)                                                                                                                                                                             |
| `templates/knowledge-index.md`    | 锁结构                                                                                                                                                                                                      |
| `templates/knowledge-overview.md` | 锁骨架                                                                                                                                                                                                      |
| `templates/knowledge-glossary.md` | 锁条目格式                                                                                                                                                                                                  |
| `templates/knowledge-log.md`      | 锁得严                                                                                                                                                                                                      |
| `templates/source-page.md`        | sources/ 页生成模板:3 节 H2 骨架 + frontmatter 锁;**模板注释里写明 raw_category 派生规则**(从 `sources[0].resource` 解析,详见 §3.6.1),便于 LLM 生成 source 页时正确填 `sources[0].resource` 路径 |

**`schema/frontmatter.schema.yaml`(插件本体权威字段表)** —— 与上面 7 个模板是**两类不同东西**,不混在 templates/ 下:

| 文件                               | 角色                                                   | 谁读                          | 进用户项目吗                               |
| ---------------------------------- | ------------------------------------------------------ | ----------------------------- | ------------------------------------------ |
| `templates/knowledge-SCHEMA.md`  | **Agent 操作手册**(流程指引)                     | LLM agent(人读)               | ✅ 进,init 时实化为`knowledge/SCHEMA.md` |
| `schema/frontmatter.schema.yaml` | **字段机器可读定义**(每个字段必不必须、什么类型) | lint 脚本、自动化工具(机器读) | ❌ 不进,留 plugin 本体                     |

**关系**:

- `knowledge/SCHEMA.md` 里写"frontmatter 必填字段"时,**直接引用 plugin 本体的 `schema/frontmatter.schema.yaml`**,**不**在 markdown 里再列一遍字段(避免双源不同步)
- lint 脚本从 plugin 读 `schema/frontmatter.schema.yaml` 作为权威,不从用户项目读(避免用户改坏)
- 三者的权威顺序:**OKF 规范** > `schema/frontmatter.schema.yaml` > `knowledge/SCHEMA.md`(后者是给人看的入口)

---

## 4. Skill 接口契约(从 prd §4 抽出)

每个 skill = 一个 SKILL.md(Claude Code skill 规范要求)。**SKILL.md 是给 LLM 读的**,写法遵循 Claude Code skill 文档约定:description 必须明确触发条件、prompt 给具体步骤。

### 4.1 `/aeps-llm-wiki-init`

**触发场景**:用户首次启用,**或已存在项目再次启用**(幂等再入,见下方)。

**Agent 行为**:

**目录名约定**(硬约束,无参数):五个顶层目录名(`inbox/` `raw/` `scripts/` `templates/` `knowledge/`)**全部固定默认**,init 不接受 `--xxx-dir` 之类的目录名参数。

1. 创建 `<project>/inbox/.gitkeep` + `<project>/inbox/README.md`(从 templates/inbox-readme.md)
2. 创建 `<project>/raw/.gitkeep` + `<project>/raw/README.md`(从 templates/raw-readme.md)。**按 raw-readme.md 的 15 类全部预建默认子目录**,每个子目录放 `.gitkeep` 占位
3. **创建 `<project>/scripts/`**:从 plugin 本体 `scripts/` 目录下**所有文件**拷贝过去。详见 §2.4。
4. **创建 `<project>/templates/`**:从 plugin 本体 `templates/` 拷贝 4 份页生成模板(`source-page.md` / `analysis-page.md` / `entity-page.md` / `concept-page.md`)+ 2 份全栈字典(`concept-entities-readme.md` / `tag-template.md`)。**注意**:plugin 本体 `templates/` 里那些分散落到 user-project 对应位置的(SCHEMA / raw-readme / inbox-readme)由步骤 1-2 处理,**不**进 user-project 的 `templates/` 顶层目录。详见 §2.5 / §2.5.1。
5. 创建 `<project>/knowledge/` 下:
   - `SCHEMA.md`(从 templates/knowledge-SCHEMA.md,**替换 plugin 内部占位符**:`{{plugin_version}}` / `{{init_at}}` / actor 字符串等;**不**替换目录名,因为目录名固定)
   - `index.md` + `overview.md` + `glossary.md` + `log.md`(从对应模板)
   - `sources/` + `entities/{person,organization,project,product,event,place,other}/` + `concepts/{theory,method,field,phenomenon,standard,term,other}/` + `analyses/` + `comparisons/` + `syntheses/`,**每个叶子目录放 `.gitkeep`**(合计 17 个子目录)
6. 若 `knowledge/` 已存在 → **走幂等再入**(见下方 §4.1.1)

**`.gitkeep` 生成方式**(用户项目里的占位文件,design.md 这层不指定,touch 还是别的由 init skill 实现时定):

- 用户项目里的 inbox/、raw/、knowledge/<子目录>/ 是**初始空目录**,需要 .gitkeep 让 git 跟踪
- init skill 自己决定怎么生成(直接 touch / 拼字符串写 / 用 cat heredoc),**不在 design.md 里锁定**
- design.md 仅规定"init 后这些 .gitkeep 必须存在"

**SCHEMA.md 关键内容**(LLM 操作手册,plugin 写入):

- 三个工作流:ingest / query / lint 的步骤
- 类型映射表(type → 目录)
- frontmatter 必填字段
- link 约定
- log 格式约定

#### 4.1.1 幂等再入(已存在项目再次 init)

**触发场景**:用户已有一个 aeps-llm-wiki 项目,plugin 升级后想跟进新字典 / 补齐缺失文件 / 补缺失 raw 子目录 / 改 SCHEMA.md。

**核心原则**:**用户为主,plugin 不静默覆盖**(对齐 Git 三方合并的 "theirs/ours" 思路)。

**字典文件 sync 策略**(按 §2.5.1 路由规则,3 份字典分别落到 user-project 不同位置;sync 策略一致):

| 情况                                                                              | 行为                                                                            |
| --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| 用户项目里**没有**该字典文件                                                | **直接复制**整份                                                          |
| 用户项目里有,但 plugin 新版**新增了 H2 章节**                               | 把新章节 append 到文件末尾                                                      |
| 用户项目里有,plugin 新版**新增了某个 H2 章节内的条目**                      | 把新条目 append 到该 H2 章节末尾                                                |
| 用户项目里有,**条目已存在但 plugin 新版内容更新了**(说明文字变了)           | **不覆盖**用户本地;lint 报告"plugin 新版有 X 条本地无/不一致,要不要采纳?" |
| 用户项目里有,**用户本地新增的内容**(自定义目录说明、自定义子类、自定义 tag) | **保留**,plugin 不动                                                      |
| 用户项目里有,**用户本地删除的条目**                                         | **不补回**,lint 提示"plugin 新版有 X 条本地无"                            |

**目录 sync 策略**(`raw/<15 类>/`、`knowledge/<17 子目录 = sources + 7 entities + 7 concepts + analyses + comparisons + syntheses>/`):

- plugin 新版 dict 新增了 raw 子目录(例:`16_xxx/`)? → **不动**(用户没主动建就不建,见 §2.2 ingest 拍板门)
- plugin 新版新增了 entities/concepts 子类(例:`entities/tool/`)? → **不动**(同上)
- 用户项目里**缺的** 15 类 / 17 knowledge 子目录? → **补建 + 放 .gitkeep**

**scripts/ sync 策略**(详见 §2.4):

| 情况                                                     | 行为                                                                                  |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| plugin 新版**新增**脚本                            | 拷贝到 user-project`scripts/`                                                       |
| plugin 新版**修改了**脚本                          | **直接覆盖** user-project 副本(plugin 自带脚本以 plugin 本体为权威,升级时跟随)  |
| 用户本地**新增**了脚本(如 `my-custom-check.py`) | **保留**,plugin 不动                                                            |
| 用户本地**删了** plugin 自带脚本                   | 不补回,lint 提示"plugin 新版有 X 你本地没有"                                          |
| `scripts/` 整个目录缺失                                | 重建 + 拷贝 plugin 自带脚本 + 写`_meta.json`                                        |
| `_meta.json`                                           | **总是覆盖**(只记录 plugin 来源 + 版本 + 时间,无用户价值,plugin 升级时正确反映) |

**templates/ sync 策略**(详见 §2.5):同 scripts/ —— plugin 修改的页生成模板(`source-page.md` / `analysis-page.md` / `entity-page.md` / `concept-page.md`)**直接覆盖** user-project 副本(plugin 自带页模板以 plugin 本体为权威,升级时跟随);**全栈字典**(`concept-entities-readme.md` / `tag-template.md`)仍走 append 策略(用户本地可能自定义子类/标签,见 §4.1.1 字典 sync 细则)。

**文件 sync 策略**(覆盖首启 + re-run 全部受 init 影响的文件;字典 sync 细则按上方独立表格):

| 文件                                     | 首次 init                       | re-run init           |
| ---------------------------------------- | ------------------------------- | --------------------- |
| `SCHEMA.md`                            | 从 templates/ 复制 + 占位符替换 | **覆盖**        |
| `index.md`                             | 从 templates/ 复制(空模板)      | **不动**        |
| `overview.md`                          | 从 templates/ 复制(空模板)      | **不动**        |
| `inbox/README.md`                      | 从 templates/ 复制              | **覆盖**        |
| `log.md`                               | 从 templates/ 复制              | **append**      |
| `glossary.md`                          | 从 templates/ 复制              | **不动**        |
| `raw/README.md`                        | 从 templates/ 复制              | append 字典策略(已有) |
| `templates/concept-entities-readme.md` | 从 templates/ 复制              | append 字典策略(已有) |
| `templates/tag-template.md`            | 从 templates/ 复制              | append 字典策略(已有) |

**为什么不覆盖 index.md / overview.md**:它们由 LLM 在 ingest/query/synthesize 时持续 append 用户积累的内容,plugin 升级是配置变更,**不会**影响 LLM 维护这些文件的逻辑;如果直接覆盖,**用户积累的内容会被清零**。plugin 升级带来的模板变化如果真要反映到 index.md / overview.md,**应由 LLM 在后续 ingest/query 流程中自然演进**,不是 plugin re-run 时强行覆盖。

**`user.dir` 缺失目录补建策略**:

- 用户项目里 inbox/ 不存在 → 重建
- 用户项目里 raw/<某子类>/ 不存在 → 补建 + .gitkeep
- 用户项目里 knowledge/<某子类>/ 不存在 → 补建 + .gitkeep
- 用户项目里 scripts/ 不存在 → 重建
- 用户项目里 templates/ 不存在 → 重建
- 用户项目里 .gitkeep 缺失 → 补

**结束提示**:init 完成后,**向用户报告**:

```
Init re-run 完成。sync 摘要:
- 字典 raw-readme.md(raw/ 顶层): 复制 0 / append 2 章节 0 条 / 跳过(本地已删) 1 条
- 字典 concept-entities-readme.md(templates/ 顶层): 复制 0 / append 1 章节 / 跳过 0
- 字典 tag-template.md(templates/ 顶层): 复制 0 / append 1 章节 3 条 / 跳过 0
- scripts/: 新增 1(init-vault) / 跳过 0 / 提示 0
- templates/: 新增 1(source-page) / 跳过 0 / 提示 0
- 缺失目录补建: raw/02_芯片/  (其它都齐)
- log.md 追加: 1 条 re-run 记录
- 你的本地修改一律保留,以上只是 plugin 新版 append
```

**不应**:静默覆盖任何用户本地新增/修改/删除的内容。

### 4.2 `/aeps-llm-wiki-ingest`

**触发场景**:用户在 `inbox/` 放好资料后。无参数 —— skill 自动递归扫当前工程 `<project>/inbox/` 全部文件。

**Agent 行为**:

1. **扫描入口**:递归遍历 `<project>/inbox/` 下所有文件(含子目录)

   - inbox 下无文件 → 提示"inbox/ 为空,先把资料丢进 inbox 再跑",**退出**
   - ~~`raw/<path>` → 走 `arch` 分支(不移动文件)~~ —— **已废弃**:raw/ 是已归档层,**不再支持直接 ingest**;调整归档分类走 `git mv` 或手工
   - **raw/ 已有但无 knowledge 页** → 用户手动 `cp` 回 `inbox/` 再走标准 ingest(详见 prd §4.2 "raw/ 已有但无 knowledge 页的场景"),**不**给 plugin 开 raw/ 直接入口(G7 不可变层原则不变)
2. **文件读取策略**(统一入口 `scripts/convert-to-md.py`):

   | 扩展名                                                                                                    | 一级处理                                        | 降级处理                  | 失败行为                      |
   | --------------------------------------------------------------------------------------------------------- | ----------------------------------------------- | ------------------------- | ----------------------------- |
   | `.md` `.markdown` `.rst` `.txt` `.csv` `.json` `.yaml` `.yml` `.xml` `.html` `.htm` | **直接读**(纯文本,无 converter)           | —                        | —                            |
   | `.pptx` `.docx` `.xlsx` `.pdf`                                                                    | **Claude 内置 converter** → 转 md        | **anydoc** → 转 md | **FAIL**,提示手工预处理 |
   | `.png` `.jpg` `.jpeg` `.bmp` `.tiff`                                                            | **paddleocr** → 转 md                    | —                        | **FAIL**,提示手工预处理 |
   | 其他                                                                                                      | **FAIL**,提示"未支持的扩展名 <ext></ext>" | —                        | —                            |

   **SKILL.md 必须先校验依赖**:跑 convert-to-md.py 之前检查 `scripts/requirements.txt` 的依赖(anydoc / paddleocr)是否安装;**未装 → 提示并退出**,避免跑到一半才报缺包。详见 §2.4。
3. **路径来自 `inbox/`**:

   - LLM **提议**一个 raw 子目录分类 + 短理由(参考 `<project>/raw/raw-readme.md` 的 15 类清单和边界规则)
   - 提议格式:`建议迁到 raw/<subdir>/<basename>`,其中 `<subdir>` 可能是:
     - 一级:`06_功能安全`(从 15 类中选)
     - 二级:`12_法规_标准_政策/V2X`(LLM 自主判定需要二级时)
   - **命名飘检查(Q5,前移自 lint)**:LLM 提议的子目录名,先与 `raw/` 下已有子目录做相似度比较(规则同 §4.4 LLM 命名飘:Levenshtein ≤ 2 / 前缀差异 / 同义拼写)
     - 命中已有相似目录 → **强制改用已有目录**,LLM 输出归并理由,用户拍板通过后直接 mv
     - 未命中 → 进入下面"拍板门"
   - **拍板门**:
     - 目标目录已存在(包括 init 时预建的 15 类)→ **无需拍板**,直接 mv 文件
     - 目标目录不存在 → **必须拍板**才创建并 mv(创建一级 `mkdir`;二级 `mkdir -p`)
   - mv 文件后从 inbox 删除
   - 在 `knowledge/log.md` 记 `**Migration**: inbox/<file> → raw/<subdir>/<file>`
   - **绝不静默创建未存在的目录**
4. 与用户做要点确认(不阻塞,可一句"继续"跳过)
5. 生成 `type: source` 的源页,放在 `knowledge/sources/<basename>.md`(frontmatter §A + §B 都写)
6. 抽取概念 / 特性 / 术语,**自动**生成对应子页(frontmatter §A + §B + §C 全写)
7. 追加 `knowledge/log.md`(本次 ingest 涉及的所有文件)
8. 更新 `knowledge/index.md`(新增条目)
9. 更新 `knowledge/glossary.md`(新增 / 修改术语)
10. 视情况更新 `knowledge/overview.md`(大图变化时)

**frontmatter 填充规则**:

- `type` = 所在目录对应类型
- `title` = 文件首行(去掉 #)
- `description` = LLM 生成摘要(中文为主)
- `sources` = OKF §B 结构化对象,指向 raw/ 源文件
- `generated` = `{ by: agent: producer/aeps-llm-wiki-plugin/0.4.0, at: <now ISO 8601> }`
- `tags` = LLM 抽取 3~5 个
- `created` / `updated` = `<now ISO 8601>`
- `summary` = `description` 同值(Q1 暂留冗余)

#### 4.2.1 并发处理 + batch OCR(ingest 多文件并行)

**触发场景**:inbox/ 下有 ≥ 2 份文档需要 ingest 时(用户期望加速,而不是逐个串行等)。

**核心动机**:`paddleocr` / `anydoc` 加载权重模型首次冷启动 5-30 秒,每次脚本重启重新初始化 Engine 2-5 秒 ——**冷启动开销远大于单文件 OCR 本身**。如果走"subagent 并行 N 份文档,每份都调 convert-to-md.py 一次",等于 **N 次冷启动叠加**,反而更慢。正确做法是**IO 批处理 + LLM 并行 + 主 agent 收尾** 三阶段,把冷启动压到 1 次,LLM 任务并行。

**3 阶段流程**:

```
┌─ 阶段 1:batch IO(主 agent 单进程)───────────────┐
│ 主 agent 收齐 inbox/ 全部待处理文件(按 §4.2 step1)│
│ 一次性调 python3 ./scripts/convert-to-md.py    │
│   --batch <f1> <f2> ... <fn>                     │
│   --project-dir . --output-dir temp/             │
│   ↓                                              │
│ 脚本内部:                                         │
│   - 共享单 paddleocr Engine(只1 次冷启动)        │
│   - 共享单 anydoc 实例                           │
│   - 依次处理 N 个文件,输出 temp/<basename>.md   │
│   - 仍单次跑完即退(NFR-1 约束)                  │
│   - Bash timeout 显式 600000ms(Claude Code max) │
└──────────────────────────────────────────────────┘
                       ↓
┌─ 阶段 2:LLM 并行(subagent 派发)──────────────┐
│ 主 agent 把 N 个 temp/<basename>.md 按 N ≤ 5  切批│
│ 派 ≤ 5 个 subagent(Claude Code Task 工具),每个:   │
│   - 读自己那批的 md 内容                          │
│   - LLM 提议 raw 子目录 + 抽概念/特性/术语       │
│   - 写到 temp/<doc-id>-proposal.json:           │
│       {file, suggested_subdir, raw_category,    │
│        concepts:[{name,type,aliases}],...}       │
│   - 不动 knowledge/ 任何文件(避免并发写冲突)    │
│ ↓                                                │
│ 主 agent 收齐所有 subagent 的 proposal JSON     │
└──────────────────────────────────────────────────┘
                       ↓
┌─ 阶段 3:主 agent 收尾合并─────────────────────┐
│ 主 agent 串行做(并发不安全):                       │
│   1. 命名飘仲裁:按 design §4.2 step3 命名飘规则  │
│      对每个 proposal 的 suggested_subdir 与      │
│      raw/ 已有子目录做相似度比较;命中已有 → 强制 │
│      改用已有目录                                  │
│   2. concept 去重:跨 proposal 按 aliases 合并,  │
│      同一概念不同名 → 合并到一页                 │
│   3. mv inbox → raw/<subdir>/(走拍板门)         │
│   4. 写 knowledge/sources/<basename>.md         │
│   5. 写 knowledge/entities/<子类>/*.md          │
│      /knowledge/concepts/<子类>/*.md            │
│   6. 追加 knowledge/log.md(一次写完,N 条合并)  │
│   7. 更新 knowledge/index.md / glossary.md      │
│      / overview.md                              │
│ 所有写入在主 agent 进程内串行,无并发冲突       │
└──────────────────────────────────────────────────┘
```

**关键边界**:

- **batch IO 入口**:`convert-to-md.py --batch <f1> <f2> ... <fn>`(替代逐文件调用);脚本内部仍"单次跑完即退"(NFR-1 兼容,详见 §1.4 / §2.4)
- **subagent 仅用于 LLM 任务**,不用于 IO/OCR 调用;每个 subagent 独立的 LLM 上下文(读 md + 提议),**不**直接动 knowledge/
- **并发上限 ≤ 5**(Claude Code Task 工具工程保守值;Claude Code 文档上限 10,留缓冲)
- **Bash timeout**:**SKILL.md 调 convert-to-md.py --batch 必须显式 `timeout: 600000`**(Claude Code Bash 工具 max 600000ms = 10 分钟;paddleocr 冷启动 5-30s + N 文件 OCR ≈ N×1-3s + 收尾合并,远低于 10 分钟上限;若实测不够,M5 调整)
- **冷启动只发生 1 次**(在阶段 1 batch 进程内);阶段 2 subagent 不调 convert-to-md,完全不触发 paddleocr
- **写文件只在阶段 3**(主 agent 串行);阶段 2 subagent 只产出 JSON proposal,不直接写 knowledge/
- **不阻塞单文件场景**:inbox 仅 1 份文件时,跳过阶段 2 subagent 派发,主 agent 自己跑完整流程(避免派发开销)

#### 写权矩阵(并发安全硬约束,Q11)

**问题根源**:多个 subagent 并发处理 inbox 多份文档,LLM 抽取的 entity / concept 经常有重叠(如"ISO 26262"和"功能安全"两个 subagent 都可能抽到)。若允许 subagent 直接写 `knowledge/`,会触发竞争条件:
- index.md / glossary.md / log.md / overview.md 这类全局索引被多 subagent 并发改写 → 丢失条目 / 顺序错乱
- 同名 entity/concept 被多 subagent 重复建页 → 漂移目录 / 重复内容
- inbox mv 操作并发触发 → 文件名冲突 / raw/ 不一致

**硬约束(写权矩阵)**:

| 路径/操作 | 阶段 1 batch | 阶段 2 subagent | 阶段 3 主 agent |
|---|---|---|---|
| 读 `inbox/<file>` | ✅(convert-to-md.py 读) | ❌(只读 temp/<basename>.md) | ❌ |
| 写 `temp/<basename>.md` | ✅ | ❌ | ❌ |
| 写 `temp/<id>-proposal.json` | ❌ | ✅(**唯一**允许 subagent 写的路径) | ❌ |
| 读 `temp/<id>-proposal.json` | ❌ | ❌(自己那份写完即退) | ✅ |
| 读 `raw/`(字典比对) | ❌ | ✅(只读,做命名飘检查) | ✅ |
| **写** `raw/<subdir>/<file>`(mv) | ❌ | ❌(**绝对禁**) | ✅(串行,拍板后) |
| 写 `knowledge/sources/<basename>.md` | ❌ | ❌(**绝对禁**) | ✅ |
| 写 `knowledge/entities/<子类>/*.md` | ❌ | ❌(**绝对禁**) | ✅ |
| 写 `knowledge/concepts/<子类>/*.md` | ❌ | ❌(**绝对禁**) | ✅ |
| 写 `knowledge/comparisons/*.md` | ❌ | ❌(**绝对禁**) | ✅(用户拍板后) |
| **改** `knowledge/index.md`(全局索引) | ❌ | ❌(**绝对禁**) | ✅(最后一次合并写) |
| **改** `knowledge/glossary.md`(常驻,append-only) | ❌ | ❌(**绝对禁**) | ✅(append 收集到的术语) |
| **改** `knowledge/log.md`(append-only) | ❌ | ❌(**绝对禁**) | ✅(追加所有迁移条目) |
| **改** `knowledge/overview.md`(大图) | ❌ | ❌(**绝对禁**) | ✅(总结后整体改写) |

**子代理 prompt 硬约束**(M3 SKILL.md 落地时嵌入 subagent prompt):

```
你(阶段 2 subagent)的唯一可写路径是 temp/<id>-proposal.json。
绝对禁止:
- 修改 knowledge/ 下任何文件(index.md / glossary.md / log.md / overview.md / sources/ / entities/ / concepts/ / analyses/ / syntheses/ / comparisons/)
- 移动 inbox/ 下任何文件
- 创建 raw/ 下任何目录
- 调用 safe-mv.py / ensure-dirs.py / append-log.py 等任何写操作脚本
你的输出:只产出 temp/<id>-proposal.json,主 agent 阶段 3 统一收尾。
```

**为什么这样设计**:

- **写权分离**:并发任务只在"写 proposal JSON"上竞争(各自独立文件名),其他所有写动作集中在主 agent 阶段 3,串行执行
- **JSON proposal 是并发安全的介质**:每个 subagent 写自己的 `<id>-proposal.json`,文件名带 hash,不冲突;主 agent 阶段 3 收集所有 JSON,按需合并
- **全局索引一致性**:index.md / glossary.md / log.md / overview.md 只能在主 agent 阶段 3 写一次,避免多 subagent 并发改写导致丢失 / 顺序错乱

#### 阶段 3 主 agent 串行动作清单(Q11)

主 agent 收集完所有 `temp/<id>-proposal.json` 后,**严格按顺序串行**执行以下动作:

```
1. 命名飘仲裁(读 raw/ 已有子目录做相似度比较)
   - 命中已有相似目录 → 强制改用已有目录
   - 未命中 → 进入拍板门

2. 拍板门汇总(把所有需要拍板的决策合成一次对话提问)
   - 用户回复 → 写 temp/decision-<hash>.json(详见 §4.2.x Q10)

3. 概念去重(跨 proposal 按 aliases 合并同义 concept)
   - 例:subagent A 提出 concept "SOME/IP" + subagent B 提出 "Someip"
   - 阶段 3 选一名(优先级:更早出现 / 字数更多 / 用户历史偏好)

4. entity 去重(同 concept,按 name + aliases 合并)
   - 同名 entity 跨 proposal → 合并到一页(选最早出现,aliases 累加)

5. 串行 mv inbox → raw/<subdir>/(读 temp/decision-<hash>.json 应用)
   - 用 scripts/safe-mv.py --apply temp/decision-<hash>.json(零交互)

6. 串行写 knowledge/sources/<basename>.md(每份文件)
   - 用 scripts/generate-source-page.py(零交互)

7. 串行写 knowledge/entities/<子类>/*.md
   - 用 scripts/generate-entity-page.py(零交互)

8. 串行写 knowledge/concepts/<子类>/*.md
   - 用 scripts/generate-concept-page.py(零交互)

9. 最后一次性更新全局索引(在所有 source/entity/concept 写完后):
   - knowledge/index.md — 整体重写(基于最新 sources/entities/concepts 全集)
   - knowledge/glossary.md — append(收集到的术语,绝不覆盖)
   - knowledge/log.md — append(本次 ingest 所有迁移条目,**Migration** + **Creation** 格式)
   - knowledge/overview.md — 整体重写(总结新增内容)
```

**为什么 9 在最后**:如果先改索引再写 page,过程中失败会导致索引指向不存在的 page;反之,page 全写完再一次性算索引,要么全成功要么全失败(主 agent 阶段 3 收尾前的所有动作都有 idempotent / 可重试的设计,详见 §4.2.x Q10)。

**并发上限 ≤ 5 仍生效**:只限制 subagent 数量,**不**影响阶段 3 串行动作的执行。

**为什么不用 IO 并发替代 LLM 并发**:

- **IO 并发**(Layer 2,`concurrent.futures.ThreadPoolExecutor` 多线程调 convert-to-md)→ N 份文件**各自 1 个 paddleocr Engine** → N 次冷启动叠加 → 不节省时间反而更慢
- **batch 模式**才解决冷启动问题(1 次 Engine,N 文件复用)

**为什么不动 query / lint**:

- query 是单问题串行的 4 跳扫描,无"多文件并行"语义
- lint 是扫已知结构(knowledge/**/*.md),无 paddleocr 等冷启动瓶颈,串行已够
- 仅 ingest 同时具备"多文件 + paddleocr 冷启动"两个并行动机

#### 阶段 2 & 阶段 3 边界约定(总览,Q11)

**阶段 2 subagent 规则与约束**:

- subagent **独立且隔离**,只调 LLM 解析 `temp/<basename>.md`(阶段 1 阶段 1 batch IO 的产物)
- **仅做只读文本解析 + 实体 / 概念提取 + 命名飘建议**,**严禁写** `knowledge/` 任何文件
- **唯一可写路径**:`temp/proposal-<doc_id>.json`(每个 subagent 各自独立文件,带 hash 不冲突)
- **零 paddleocr 调用**(冷启动已在阶段 1 batch 进程内完成),不触发任何 IO 写入
- 输出 JSON 字段:`{ doc_id, raw_category_suggestion, entities[], concepts[], raw_suggested_path, decision_needed: bool }`

**阶段 3 主 agent 合并收尾逻辑**:

1. **收集所有 `temp/proposal-*.json`**,按 doc_id 排序
2. **跨文件汇总所有 entities / concepts**,按 `name + aliases` 做模糊匹配(Levenshtein ≤ 2 / 前缀差异 / 同义拼写),合并去重
3. **命名飘仲裁**(读 `raw/` 现有子目录做相似度比较;命中已有相似目录 → 强制改用;未命中 → 走拍板门)
4. **拍板门汇总**:把所有 subagent 提的"未存在 raw 子目录 / 文件归类"决策合成**一次性合并提问**(避免 N 次来回)
   - 用户回复 → 写 `temp/decision-<hash>.json`(详见 §4.2.x Q10)
   - 触发条件:`raw_category_suggestion` 指向未存在的 `raw/` 子目录,或 `decision_needed: true`
5. **一次性串行调用** `python3 ./scripts/safe-mv.py --apply temp/decision-<hash>.json` **批量迁移** `inbox/` → `raw/<subdir>/`(含拍板门通过的 mkdir)
6. **串行落盘**:
   - `knowledge/sources/<basename>.md`(每份 inbox 文件一份)
   - `knowledge/entities/<子类>/<slug>.md`(去重合并后)
   - `knowledge/concepts/<子类>/<slug>.md`(去重合并后)
7. **最后增量更新全局索引**(必须在所有 source/entity/concept 写完后,详见上面"为什么 9 在最后"):
   - `knowledge/log.md` —— append(本次 ingest 所有迁移条目,**Migration** + **Creation** 格式)
   - `knowledge/glossary.md` —— append(收集到的术语,**绝不覆盖**)
   - `knowledge/index.md` —— 整体重写(基于最新 sources/entities/concepts 全集)
   - `knowledge/overview.md` —— 整体重写(总结新增内容)

**写权矩阵总览**(详见上面"写权矩阵"段):

| 路径 / 操作 | 阶段 1 batch | 阶段 2 subagent | 阶段 3 主 agent |
|---|---|---|---|
| `inbox/<f>` | 只读 | 只读 | 串行 mv |
| `temp/<basename>.md` | 写 | 只读 | 只读 |
| `temp/proposal-<id>.json` | — | 写(独占) | 只读 + 合并 |
| `temp/decision-<hash>.json` | — | — | 写 |
| `raw/<subdir>/` | 只读 | 只读 | mkdir + 串行 mv |
| `knowledge/sources/` | 只读 | **严禁写** | 串行写 |
| `knowledge/entities/` `concepts/` | 只读 | **严禁写** | 串行写 |
| `knowledge/log.md` `glossary.md` `index.md` `overview.md` | 只读 | **严禁写** | 最后一步写 |

**并发安全保证**:

- 阶段 2 subagent 并发上限 ≤ 5,**只**在 `temp/proposal-<id>.json` 上并发写,文件名带 hash 互不冲突
- 阶段 3 串行 9 步动作为单进程顺序执行,**无并发竞争**
- 全局索引(index/glossary/log/overview)只在阶段 3 最后一步写,**避免** N subagent 并发改写导致丢失 / 顺序错乱
- 阶段 3 任何一步失败可断点续跑(每个动作 idempotent,见 §4.2.x Q10)

### 4.3 `/aeps-llm-wiki-query`

**触发场景**:用户对 wiki 提问(`/aeps-llm-wiki-query <question>`)。

**Agent 行为**(4 跳扫描):

**先决条件** —— 跑前跑 `scripts/check-qmd.py`(单次,探查 `qmd --version` 是否可用),并数 `knowledge/**/*.md` 当前页数 N,按阈值决定用 `index.md` 还是 `qmd`:

| 页数 N          | 入口                                           | qmd 缺失行为                                                |
| --------------- | ---------------------------------------------- | ----------------------------------------------------------- |
| N < 500         | **纯 `index.md` + 4 跳扫描**           | 不需要 qmd                                                  |
| 500 ≤ N < 1000 | **优先 qmd**(`qmd query "<question>"`) | 提示用户装 qmd,走纯`index.md` 降级                        |
| N ≥ 1000       | **必须 qmd**                             | **报错**(提示"wiki 已超 1000 页,请装 qmd"),不进入回答 |

阈值常量:

```python
# scripts/check-qmd.py 内部(仅示意,实际由该脚本返回)
QUERY_INDEX_THRESHOLD = 500      # N < 此值纯 index
QUERY_QMD_REQUIRED_THRESHOLD = 1000  # N ≥ 此值必须 qmd
```

**4 跳扫描算法**(当选择纯 `index.md` 或 qmd 缺失降级时):

```
跳 1:index 过滤
  - 读 knowledge/index.md 全部条目
  - 每个条目 frontmatter 的 tags 与 query 关键词做匹配
  - 选 top-K(K=10,常量,详见 §4.3.1)作为"强候选"
  - 余下条目作为"弱候选"(兜底用,如果强候选答案不够)

跳 2:读强候选页
  - 优先级:description / summary → title → 全文
  - 提取与 query 直接相关的"显式答案"
  - 同时记录每个候选页出现的 [[wikilink]] 链接,准备跳 3

跳 3:跳邻居(1 跳深度,避免雪崩)
  - 顺着强候选页里出现的 [[wikilink]] 跳
  - 目标页类型偏好:concepts/* > entities/* > sources/* > analyses/* > syntheses/* > comparisons/*
  - 1 跳深度(不从邻居再追邻居),硬上限 8 个邻居页

跳 4:glossary + log 辅助
  - glossary.md:用 query 关键词消歧(同义词 / 术语官方翻译)
  - log.md:取最近 10 条,找近期 ingest 是否含相关源(避免新内容没消化)
```

**qmd 入口**(当 wiki 规模达到阈值且 qmd 已装):

```bash
qmd query "<question>" --collection <wiki-knowledge-dir> --limit 20
```

- `--collection`:qmd 的 collection 名(plugin 不预设,init 时让用户配一次或留默认 `knowledge`)
- `--limit 20`:plugin 预设上限
- SKILL.md 拿 qmd 返回的 top-20 命中,直接进入"跳 2"逻辑(跳 1 由 qmd 替代)

**回答与落档**:

3. 回答,**每条断言附 wiki 标准 markdown 链接**
4. 回答结束后**问用户是否落档** → 落档则新建 `type: analysis` 页,放 `knowledge/analyses/<时间戳>-<slug>.md`,追加 log
5. **不应**:编造 wiki 里没有的内容

#### 4.3.1 top-K 与命中阈值常量

```python
# scripts/query-rank.py(纯算法骨架,实际由 SKILL.md 提示词驱动,不写死)
QUERY_CANDIDATE_K = 10           # 跳 1 选 top-K
QUERY_NEIGHBOR_MAX = 8           # 跳 3 邻居硬上限
QUERY_LOG_RECENT = 10            # 跳 4 log 取最近 N 条
QUERY_INDEX_THRESHOLD = 500      # N < 此值纯 index
QUERY_QMD_REQUIRED_THRESHOLD = 1000  # N ≥ 此值必须 qmd
```

**为何不引入 RAG / 向量索引**:`index.md` + 4 跳在 ~100 个源 / 几百页规模足够(Karpathy `llm-wiki.md` line 47 验证);qmd 作为可选搜索引擎补充更大规模,plugin 不自建 RAG(对齐 NFR-1)。

### 4.4 `/aeps-llm-wiki-lint`

**Agent 行为**:

1. 扫所有 `knowledge/**/*.md` 文件
2. 报告:
   - **孤儿页**:无出入链接的页(可豁免 `index.md` / `overview.md` / `glossary.md`)
   - **矛盾**:两个页对同一事实说法不同(LLM 判断)
   - **陈旧页**:

     - **优先判定**:`stale_after` 字段存在且 `now >= stale_after` → 陈旧(OKF §5.5 语义)
     - **回退判定**:`stale_after` 缺失 + `updated` 时间 > **180 天** + 最近 `log.md` 无提及 → 陈旧
     - **豁免**:`status: deprecated` 页(已声明归档,不算陈旧)
     - **不豁免**:`status: draft`(草稿也会陈旧,提示"长期未更新草稿")
     - 阈值常量 `STALE_THRESHOLD_DAYS = 180`,plugin 本体 `scripts/constants.py` 可改(与 design §1.4 scripts 约束一致,Python 3.10+ .py)
   - **LLM 命名飘**:相似子目录/页面名检测,触发"合并建议"

     - **触发条件**(任意一条):(a) 两目录名归一化后(Levenshtein 距离 ≤ 2 + 全小写 + `-` 归一)高度相似(如 `socke-design` vs `socket-design`);(b) 两目录仅前缀或后缀差异(如 `01_驱动` vs `01_驱动_v2`);(c) 同一目录下出现 `soc_design.md` + `soc-design.md`(同义命名漂移)
     - **lint 报告**:
       ```
       [命名飘] raw/ 下检测到相似子目录:
         - 02_芯片与控制器 (15 篇) ↔ 03_芯片 (8 篇)
         建议:统一为 02_芯片,SCHEMA.md 已用此名
       ```
     - **不自动合并** —— lint 只提示,**用户拍板**后才用 `git mv` 归档旧目录到 `raw/_archived/`
     - **LLM ingest 时**也要预警,提议新文件归档到已有目录名而非新建漂移名
   - **漏链**:某 page 里反复出现但链接缺失的术语
   - **frontmatter 不合规**:必填字段缺失 / 类型错位 / 未知 type
   - **frontmatter `links:` 与正文 `[[wikilink]]` 漂移**:正文 wikilink 增减后 `links:` 未同步 → lint 告警 + `--fix` 自动同步(详见 §3.6)
   - **raw_category 派生失败**:从 `sources[0].resource` 路径解析失败(无 sources / 非 raw 本地路径 / 分类不在 15 类清单)→ WARN/FAIL(详见 §3.6.1)
3. 默认只报告;**`--fix` 模式按问题级别分流**:
   - **确定性结构修复** —— `--fix` 直接 patch 应用,`log.md` 追加 `**LintFix**` 条目记录每处改动:
     - **frontmatter 字段缺失** → 补占位值 + WARN(`type` 缺失用 frontmatter 路径推测的实体/概念子类填充)
     - **frontmatter 字段类型错位** → 强转(如 `tags: domain/ai` → `tags: [domain/ai]`,list 化即可;**不**做轴前缀补全或拼写改写,那种是语义级问题)
     - **`## 摘要` / `## Summary` H2 残留** → 删小节,把内容合并到 frontmatter `summary` 字段
     - **sources/analyses 缺 3 节骨架** → 文件末尾追加占位 H2(`## 重点摘录` / `## 我的思考` / `## 总结:最有收获的一句话`),空内容
     - **frontmatter `links:` ↔ 正文 `[[wikilink]]` 漂移** → 同步 `links:` 字段,与正文 wikilink 一致(详见 §3.6)
   - **语义级问题** —— `--fix` 模式仍**只输出提案**(不应用,等用户确认):
     - **矛盾**(LLM 判定两页同一事实不同说法)→ 输出 diff + 候选改写 + 用户拍板
     - **命名飘合并** → 输出建议 + `git mv` 命令(用户手动执行,不自动改文件)
     - **漏链** → 输出候选链接列表 + 用户确认
     - **陈旧页处理** → 输出建议(归档到 `_archived/` / `status: deprecated` / 续期),用户拍板
4. **不应**:无 `--fix` 时静默修改文件;`--fix` 模式也不静默应用语义级修改

**`--by <axis>` 模式**:除默认全量报告外,支持按指定 axis group by 输出:

- `--by raw_category`:按 raw 分类 group by source 页(详见 §3.6.1 示例输出)
- `--by type`:按 OKF `type` group by(原有能力,显式化)
- `--by maturity`:按成熟度 group by
- `--by docform`:按文档形态 group by

**`--by raw_category` 输出示例**:

```
按 raw_category 分组(从 sources[0].resource 路径派生):
[12_法规_标准_政策] 8 篇
  - sources/okf-spec.md
  - sources/un-r155.md
  - ...
[06_功能安全] 5 篇
  - sources/iso26262-asil-d.md
  - ...
[06_功能安全 + 12_法规_标准_政策] 1 篇(罕见,跨分类 source)
  - sources/v2x-cybersecurity.md
[未分类] 2 篇
  - sources/legacy-doc.md        ← raw_category 派生失败
  - sources/url-only-ref.md      ← 外部引用
```

### 4.5 `/aeps-llm-wiki-synthesize <topic>`

**触发场景**:用户对某主题积累足够多(读 N 篇 source、有 K 个 entity/concept 页)后,主动想让 LLM 写一份"宏大综合"。

**Agent 行为**:

1. **解析 topic**:topic 形如 `OKF 生态全景` / `AUTOSAR 实战方法论`
2. **收集相关页**:
   - 读 `knowledge/index.md`,筛 frontmatter 含 topic tag 或与 topic 有引用关系的页
   - 默认范围:"所有 entity/concept 页 + 引用它们的 source 页"(由 LLM 决定具体边界)
3. **写 synthesis 页**:
   - 路径:`knowledge/syntheses/<topic-slug>.md`(**不带时间戳,常驻**)
   - frontmatter:`type: synthesis` + `topic: <topic>` + `sources_count: N` + `last_updated: <ISO 8601>`
   - 正文**自由发挥**,但 SKILL.md 给提示:典型结构 = 主题脉络梳理 + 多观点融合 + 个人判断
4. **更新索引**:追加 `knowledge/index.md`、追加 `knowledge/log.md`(`**Creation**` / `**Update**`)
5. **不应**:写一次性"当时综合"(那应该走 `analyses/`);synthesis 是常驻页,后续 LLM 可 update

**与 query skill 落档的差别**:

- query 落档 = `analyses/<时间戳>-<slug>.md`(`type: analysis`,时间戳,**一次性视角**)
- synthesize = `syntheses/<topic-slug>.md`(`type: synthesis`,**常驻**,多次 update)

### 4.6 `/aeps-llm-wiki-query` 内 comparison 自然触发机制

**不增加 skill**,由 query skill + ingest skill 共同承担:

#### 路径 A — ingest 触发(同类 entity 提议)

触发点:`/aeps-llm-wiki-ingest` 完成,**在 source 页落档询问时**(§4.2 末尾),LLM 检查:

- `entities/<子类>/` 下**同 type** 的现有 entity 数
- 这次新 ingest 涉及的 entity 是否 ≥ 2 个同类
- 若满足,LLM 在询问时**附一句**:"现有同类 entity X 个(列表),要不要建一个常驻 comparison 页把它们对照一下?"

#### 路径 B — query 累计触发(高频检索提议)

触发点:`/aeps-llm-wiki-query` 完成,**在落档询问时**,LLM 检查 `knowledge/log.md`:

- 用模式 `**Update**: ... query ... "X.*Y"` 匹配历史 query 条目(query 落档的 log 行走 §3.4 五种前缀里的 `Update`,因为 query 会更新 glossary + index + 候选页)
- 若 "X vs Y" 累计 ≥ 3 次,**下次落档询问时只提一次**:"X vs Y 这个对比提过几次了,要不要建一个常驻 comparison 页?"

**comparison 页生成规则**:

- 路径:`knowledge/comparisons/<a>-vs-<b>.md`(**不带时间戳**,常驻)
- frontmatter:`type: comparison` + `sources:` 字段(≥ 2 条 `[[wikilink]]`,对齐 SCHEMA.md §2.2 + design §3.6 comparisons 行) + `last_updated: <ISO 8601>`
- 正文**自由发挥**,SKILL.md 给提示:典型结构 = 多栏对照表 + 维度差异 + 各自适用场景

**关键边界**:

- query **一次性**给完对比表就结束 → 是 answer,不是 comparison(**不建**)
- comparison 是**常驻页**,需要用户拍板后才建
- lint 兜底:`comparisons/*.md` 必须有 `type: comparison` + `sources:` 字段(否则 FAIL)

---

## 5. 关键流程

### 5.1 Ingest 流程(inbox → raw → knowledge)

**单文件场景**(N=1,跳过 subagent 派发,主 agent 直接跑完整流程):

```
[用户丢 inbox/<file>]
       ↓
[用户跑 /aeps-llm-wiki-ingest(无参数,自动扫 inbox/)]
       ↓
[主 agent:阶段 1 batch IO]
   └→ python3 ./scripts/convert-to-md.py --input inbox/<file> --output temp/<basename>.md
       ↓
[主 agent:阶段 2 + 3 合并(N=1 时跳过 subagent 派发,主 agent 自己完成)]
   ├→ 提议 raw/<subdir>/<file> + 理由
   ├→ 拍板门 / 命名飘仲裁
   ├→ mv inbox/<file> → raw/<subdir>/<file>
   ├→ log.md 记 **Migration**
   ├→ 生成 knowledge/sources/<basename>.md
   ├→ 抽取 → 生成 knowledge/entities/<子类>/*.md / knowledge/concepts/<子类>/*.md
   ├→ 更新 knowledge/index.md / glossary.md / overview.md
   └→ log.md 记 **Creation** / **Update**
       ↓
[可选路径 A:同类 entity ≥ 2 → LLM 提议建 knowledge/comparisons/<a>-vs-<b>.md]
```

**多文件场景**(N ≥ 2,走 §4.2.1 三阶段并发处理):

```
[用户丢 inbox/<f1> ... inbox/<fn>]
       ↓
[用户跑 /aeps-llm-wiki-ingest]
       ↓
[主 agent:阶段 1 batch IO(单进程共享 1 次冷启动)]
   └→ python3 ./scripts/convert-to-md.py --batch inbox/<f1> ... inbox/<fn> --output-dir temp/
       ↓
[主 agent:阶段 2 LLM 并行(N ≤ 5 subagent)]
   ├→ subagent 1:读 temp/<f1>.md → 写 temp/f1-proposal.json
   ├→ subagent 2:读 temp/<f2>.md → 写 temp/f2-proposal.json
   ├→ ...
   └→ subagent k(k ≤ 5):读 temp/<fk>.md → 写 temp/fk-proposal.json
       ↓
[主 agent:阶段 3 收尾合并(串行,无并发写冲突)]
   ├→ 命名飘仲裁(各 proposal.suggested_subdir 与 raw/ 已有目录相似度比较)
   ├→ concept aliases 去重(跨 proposal 合并同义)
   ├→ mv inbox → raw/<subdir>/(走拍板门)
   ├→ 写 knowledge/sources/<basename>.md(每份)
   ├→ 写 knowledge/entities/<子类>/*.md / knowledge/concepts/<子类>/*.md
   ├→ 追加 knowledge/log.md(一次写完 N 条 **Creation** / **Migration**)
   ├→ 更新 knowledge/index.md / glossary.md / overview.md
   └→ 删 temp/*.md / temp/*.json(临时文件不进版本)
       ↓
[可选路径 A:同类 entity ≥ 2 → LLM 提议建 knowledge/comparisons/<a>-vs-<b>.md]
```

**SKILL.md 怎么挑流程**:扫描 inbox/ 后,统计待处理文件数 N。N = 1 → 单文件流程;N ≥ 2 → 三阶段并发流程。详见 §4.2.1。

**`--raw-subdir=<name>` 适用边界**:

ingest skill 无参数 —— 扫 `inbox/` 全部文件。`--raw-subdir=<name>` 是可选快捷参数:跳过分类交互,直接 `mv inbox/<file> → raw/<name>/<file>`,`log.md` 记迁移路径(inbox 是暂存层,参数等价于"我知道该放哪")。

**Lint 规则**:

- 出现 `ingest --raw-subdir=<name>` 且 `<name>` 不在 init 预建的 15 类 → **WARN**,提示"自定义目录,需要拍板门确认"

#### §4.2.x ingest 提案 / 拍板 / 应用 三段落档(audit trail,Q10)

**目的**:ingest 涉及 LLM 提议 → 用户拍板 → 脚本机械执行三阶段,需要**显式中间文件**作为 audit trail,便于:
- 拍板后 `log.md` 引用 plan 文件追溯决策(谁拍的 / 何时拍 / 改了啥)
- 多 subagent 并发 ingest(§4.2.1)各产 proposal → 主 agent 阶段 3 仲裁 → 应用,需共享 plan 介质
- 用户事后可读 `temp/plan-<hash>.md` 复核决策
- `scripts/*.py` **零交互**(§1.4 硬契约)— 读 plan 文件应用,不发起任何 prompt

**三段落档流程**:

```
阶段 ① 提议(proposal)
  SKILL.md 调 scripts/convert-to-md.py --batch ...
  scripts 读 inbox/<file> → 输出 temp/proposal-<hash>.json
    (内容:inbox 文件清单 + 每份的 suggested_subdir + 命名飘候选 + 概念抽取候选)

阶段 ② 拍板(confirmation)
  SKILL.md 读 proposal → Claude 在对话里展示给用户
  用户回复 yes/no/改建议 → SKILL.md 写 temp/decision-<hash>.json
    (内容:用户对每份文件的拍板结果 — 接受提议 / 改子目录 / 跳过)

阶段 ③ 应用(application)
  SKILL.md 调 scripts/safe-mv.py --apply temp/decision-<hash>.json
  scripts 读 decision 文件 → 机械 mkdir / mv / 写 log.md / 写 knowledge/
    (任何 LLM 不参与的环节都委托给 scripts,零交互)
```

**plan 文件格式**(`temp/proposal-<hash>.json` / `temp/decision-<hash>.json`):

- 文件名:`<type>-<hash>.json`,`hash` = 内容 sha256 前 8 位(便于去重 / 复用)
- 位置: `<project>/temp/`(CLAUDE.md "临时文件 temp/ 目录"约束)
- 生命周期: ingest 完成后由 SKILL.md 提示用户"是否保留 plan 文件供回溯";默认 `--cleanup` 删除,留 `--keep` 备份
- **后缀统一 `.json`**:proposal + decision 都用 JSON,scripts 用 `json.load()` 解析,**零 markdown 解析路径**,彻底落实 §2.4.1 无交互硬约束
- **log.md 引用**:`**Migration**: inbox/... → raw/... (see plan temp/decision-<hash>.json)` — plan 文件路径留痕

**proposal JSON schema**(`temp/proposal-<doc_id>.json`,阶段 2 subagent 写):

```json
{
  "schema_version": "1.0",
  "type": "ingest_proposal",
  "doc_id": "okf-v0-2-spec",
  "created_at": "2026-09-02T14:30:00Z",
  "actor": "agent: producer/aeps-llm-wiki-plugin/0.2.0",
  "source": "inbox/okf-v0-2-spec.md",
  "raw_category_suggestion": "12_法规_标准_政策",
  "raw_path_suggestion": "raw/12_法规_标准_政策/okf-v0-2-spec.md",
  "decision_needed": true,
  "decision_reason": "raw_category_suggestion 目录已存在,可直迁;但子目录 raw/12_法规_标准_政策/OKF/ 不存在,需拍板门确认是否新建",
  "entities": [
    {"name": "Open Knowledge Format", "type": "concept", "subtype": "standard", "aliases": ["OKF"]}
  ],
  "concepts": [
    {"name": "frontmatter", "type": "concept", "subtype": "term", "aliases": []}
  ]
}
```

**decision JSON schema**(`temp/decision-<hash>.json`,SKILL.md 拍板后写):

```json
{
  "schema_version": "1.0",
  "type": "ingest_decision",
  "decided_at": "2026-09-02T14:32:00Z",
  "actor": "human:zhigang.liu",
  "proposal_refs": ["temp/proposal-okf-v0-2-spec.json"],
  "actions": [
    {"op": "mv", "src": "inbox/okf-v0-2-spec.md", "dst": "raw/12_法规_标准_政策/okf-v0-2-spec.md", "mkdir_parent": false},
    {"op": "mkdir", "path": "raw/12_法规_标准_政策/OKF"},
    {"op": "mv", "src": "inbox/okf-v0-2-errata.md", "dst": "raw/12_法规_标准_政策/OKF/okf-v0-2-errata.md", "mkdir_parent": false}
  ],
  "merge_concepts": [
    {"canonical": "Open Knowledge Format", "merge": ["OKF", "okf"]}
  ]
}
```

**scripts 调用形式**(举例):

```bash
# 阶段 ①:提脚本读 inbox,产出 proposal JSON(无 stdin / 无 input)
python3 ./scripts/propose-ingest.py --project-dir . --output temp/proposal-abc123.json

# 阶段 ③:scripts 读用户拍板后的 decision JSON,机械应用
python3 ./scripts/safe-mv.py --project-dir . --apply temp/decision-abc123.json

# scripts 内部用 json.load() 解析,无 markdown 解析、无 stdin、无 input
```

**scripts 不发起任何 prompt**(NFR-1 + §2.4.1 硬契约)。SKILL.md 负责:
- 把 proposal JSON 渲染为人类可读文本在 Claude 对话展示(LLM 自己解释,scripts 不参与)
- 接收用户回复(yes/no/改建议)
- 把结果按 decision schema 写入 decision JSON 文件
- 调用 `python3 ./scripts/<name>.py --apply temp/decision-<hash>.json`

**schema_version 字段**:JSON 顶层带 `schema_version: "1.0"`,scripts 读到不认版本 → FAIL + 报错(避免 schema 演化后 silently 解析错)。详见 implement §C10.2 schema_version 校验测试。

**与 lint `--fix` 的一致性**:lint 提案同样落 `temp/lint-proposal-<hash>.json`,确定性结构修复走 `temp/lint-decision-<hash>.json` → scripts 应用;语义级问题不进 decision,只输出报告(详见 §4.4.x)。

### 5.2 Synthesize 流程(/aeps-llm-wiki-synthesize)

```
[用户跑 /aeps-llm-wiki-synthesize <topic>]
       ↓
[skill:LLM 读 knowledge/index.md,筛与 topic 相关的 entity/concept/source 页]
       ↓
[skill:LLM 综合,写 knowledge/syntheses/<topic-slug>.md]
       ↓
[skill:frontmatter 写 sources_count = 引用页数]
       ↓
[skill:更新 knowledge/index.md]
       ↓
[skill:log.md 记 **Creation**]
```

### 5.3 Comparison 路径 B 触发流程(高频检索)

```
[用户跑 /aeps-llm-wiki-query "X vs Y"]
       ↓
[skill:LLM 查 log.md 历史,数 "X vs Y" 出现次数]
       ↓
[skill:次数 < 3 → 正常回答,不提议]
       ↓
[skill:次数 ≥ 3 → 落档询问时附一句提议建常驻 comparison 页]
       ↓
[用户拍板 / 否决]
```

### 5.4 异常处理

| 场景                                      | 行为                                       |
| ----------------------------------------- | ------------------------------------------ |
| inbox 文件已迁移过(inbox 不存在)          | 报错,提示文件位置                          |
| 用户拍板的子目录名含非法字符(空格、`/`) | 报错,要求重命名                            |
| 同一文件已被 ingest 过(sources/ 已有名)   | 警告 + 问用户是覆盖还是新版本              |
| LLM 抽取生成 0 个概念页                   | 不报错,只生成 source 页 + 警告"没抽到概念" |
| frontmatter schema 校验失败               | 不写盘,要求 LLM 重写 frontmatter           |

---

## 6. 测试要点(从 implement.md 抽框架)

### 6.1 单元测试

- `test_templates.py`:每个 templates/* 渲染后 frontmatter 合规
- `test_frontmatter_compliance.py`:模拟各种 §A~§D 输入,断言 OKF 字段识别正确
- `test_okf_compliance.py`:用 [input/google-OKF/OKF-SPEC.md](../../input/google-OKF/OKF-SPEC.md) 的 OKF 校验规则,反向校验 plugin 产物

### 6.2 端到端手动测试

1. 在临时空目录跑 `/aeps-llm-wiki-init`
2. 复制 `input/google-OKF/OKF-SPEC.md` 到 `inbox/`
3. 跑 `/aeps-llm-wiki-ingest`(无参数,自动扫 inbox/),**拍板** raw/okf/
4. 验证:文件已迁、source 页存在、index.md 更新、log.md 有 **Migration** 条目
5. 跑 `/aeps-llm-wiki-query "OKF 必填字段"`(prd AC-3)
6. 跑 `/aeps-llm-wiki-lint` 看报告
7. 把 `knowledge/` 喂给 OKF 第三方 reader,确认无报错

### 6.3 兼容性测试

- 用户从 Karpathy 风格 wiki 导入,plugin **不再警告** `[[wikilink]]`(Q6 一等公民),无需任何转换
- 不同 OKF v0.x 字段(schema 校验脚本跑过两个 v0.1 + v0.2 样本)

---

## 7. Hooks 设计

### 7.1 唯一支持的 hook:SessionStart → plugin 仓库更新检查

**触发事件**:`SessionStart`(Claude Code 每次启动加载 plugin 时)

**逻辑**:

```bash
# 伪代码,plugin 本体 hooks/hooks.json 触发
git ls-remote --tags --refs origin \
  https://github.com/zhigangliu-bot/aeps-llm-wiki-plugin.git
```

对比 plugin 本体 `plugin.json` 的 `version` 字段与 remote 最新 tag。

**行为**:

| 情况                             | 行为                                                                                                                                                                    |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| remote 有更高版本                | 向 system-reminder / conversation 注入提示:`[plugin 更新提示] 当前 v<current>,remote 有 v<latest> 可用。升级命令:/plugin install zhigangliu-bot/aeps-llm-wiki-plugin` |
| 当前已是最新                     | 不注入任何提示,完全静默                                                                                                                                                 |
| `git` 不可用 / 无网 / 仓库 404 | 静默,不报错,不阻塞 plugin 启动                                                                                                                                          |
| `git ls-remote` 超时(> 3s)     | 静默跳过,下次启动再查                                                                                                                                                   |

**关键边界**:

- **不自动 pull / 不自动升级** —— 只提示,**由用户主动拍板**
- **不修改 user-project** —— hook 不得动 inbox/raw/knowledge,只能向 conversation 注入文本
- **不修改 plugin 本体** —— hook 不得 `git pull`,不得改 plugin.json
- **失败可静默** —— 网络/git/超时 任何失败一律静默,不阻塞 plugin 加载

### 7.2 hook 配置(`hooks/hooks.json`)

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/check-update.py",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

**注意**:

- `command` 里**允许**用 `${CLAUDE_PLUGIN_ROOT}`(Claude Code 官方变量,此处**与 scripts/ 不同**)—— 因为 hook 是**在 Claude Code 加载阶段**跑,Plugin 安装目录是稳定可知的(不像 scripts 是 skill 触发时才跑);hooks 是 Claude Code 自身的事,**CLAUDE.md「不引入绝对路径」是 user-project 内代码约束,plugin 本体的 hooks.json 由 plugin 维护者掌控**
- `timeout: 5` —— 超时 5s 强制 kill(避免阻塞 plugin 启动)
- `check-update.py` 是 Python 3.10+ 脚本,与 scripts/ 同样的"单次运行即退"约束(详见 §1.4)

### 7.3 与已有 G6 / NFR-1 兼容性声明

| 约束                       | 检查                                                         |
| -------------------------- | ------------------------------------------------------------ |
| G6 "plugin 不带常驻运行时" | ✅ hook 是事件回调,跑完即退,**不是 daemon**            |
| G3 "不做自动监控文件变动"  | ✅ 监控的是**plugin 仓库**,**不是 user-project** |
| inbox 拍板门               | ✅ 完全不涉及 user-project 写入                              |
| 离线可用                   | ✅ 失败静默,无网环境也能装上 plugin                          |

### 7.4 未来可能加的 hook(列出但当前不实现)

| 触发事件               | 用途                                                                | 当前实现?       |
| ---------------------- | ------------------------------------------------------------------- | --------------- |
| `SessionStart`       | plugin 仓库更新检查                                                 | ✅ 已实现       |
| `PostToolUse(Write)` | 检测写入路径是否为`inbox/`,若有则提示"是否要 ingest"              | ❌ 后续版本考虑 |
| `PreCompact`         | compact 前给 LLM 提示"即将压缩上下文,plugin 相关状态保留 X / Y / Z" | ❌ 后续版本考虑 |

**判断新 hook 是否加**:能用 prompt(SKILL.md) 解决的不加 hook;hook 仅用于**跨 session / 跨 skill 的全局事件**(更新检查 / 写盘提示 / 上下文压缩)。

---

## 8. 待定(TBD)

> **状态**:以下条目**已拍板**(决策已写入对应章节),本表保留仅作历史索引。冻结后将统一移入末尾「变更历史」章节。

- [X] **T2**:`summary` 字段去留(Q1) — 留 `summary`,去掉 source 正文里的 `## 摘要` 小节(summary 走 frontmatter;动机:frontmatter 字段承担长摘要职责,正文强制 3 节骨架 `## 重点摘录` / `## 我的思考` / `## 总结` 替代通用"## 摘要",避免 UI 冗余;OKF v0.2 不强制正文必须有摘要小节,纪律与 OKF / Karpathy 风格一致;prd §1.5 + design §3.1 §C + SCHEMA.md §3.1 三处同步)
- [X] **T3**:`--raw-subdir` 适用边界 + 取消 raw/ 入口 — **`--raw-subdir` 仅 inbox 生效**;**取消 raw/ 直接 ingest 入口**,raw/ 是已归档不可变层,调整走 `git mv` 或手工
- [X] **T4**:`SCHEMA.md` 模板 — `templates/knowledge-SCHEMA.md`(8 节,含占位符 init 替换)
- [X] **T5**:`templates/inbox-readme.md` 提示语 — 已完成
- [X] **T6**:陈旧阈值 + LLM 起名飘 lint — 180 天 / `stale_after` 优先 / 命名飘仅 prompt 不合并
- [X] **T7**:hooks 支持 + SessionStart plugin 仓库更新检查 — 允许 hooks;触发 SessionStart → `git ls-remote` → 注入更新提示;失败静默。详见 §7

---

## 9. 参考

- [prd.md](prd.md) —— 产品需求(本文件的源头)
- [implement.md](implement.md) —— 执行清单(下一步)
- [../../input/karpathy-llm-wiki/karpathy-llm-wiki.en.md](../../input/karpathy-llm-wiki/karpathy-llm-wiki.en.md) —— Karpathy LLM Wiki 理念
- [../../input/google-OKF/OKF-SPEC.md](../../input/google-OKF/OKF-SPEC.md) —— OKF v0.x 规范(本文件 §3 主要依据)
- [../../reference/balukosuri__llm-wiki-karpathy/CLAUDE.md](../../reference/balukosuri__llm-wiki-karpathy/CLAUDE.md) —— Karpathy 模式 Agent 操作手册范本

---

**下一步**:等本文件 review 通过 + T1~T7 拍板 → 进入 M3(写 `implement.md`)

---

## 9. Change History

### v0.2(2026-09-02) — 五轮增量

**Round 1: Python 化(scripts/ Node 18+ .mjs → Python 3.10+ .py)**

- §1.1 目录树 scripts/ 节点 + §1.2 模块职责表 + §1.3 边界说明 + §1.4 scripts/ 与 hooks/ 边界(整段重写为 Python 3.10+ 约束:`subprocess.run` / `signal.signal` / `sys.stdin` 不挂 resume / 单次运行即退)
- §2.4 scripts 内容段 + hooks 段引用(`check-update.mjs` → `check-update.py`)
- §4.2 / §4.3 / §4.4 / §4.3.1 SKILL.md 流程所有 `node ./scripts/<name>.mjs` → `python3 ./scripts/<name>.py`
- §7.2 hooks 配置 JSON `command` 字段全部切到 `python3`
- §2.4 增加 frontmatter 骨架 / schema 校验 / YAML 读写需要 `jsonschema` / `pyyaml` / `pytest`
- §1.4 增加"支持 `--batch` 多输入模式"约束

**Round 2: 3-stage ingest 并发 + batch OCR**

- §1.4 / §2.4 / §4.2.1(新整段,含 ASCII flow 图 + 关键边界 + 为什么不用 IO 并发 + 为什么不动 query/lint)
- §5.1 Ingest 流程分**单文件场景 (N=1)** + **多文件场景 (N ≥ 2)** 两版本
- `convert-to-md.py` 两调用模式:`--input inbox/<file>`(单文件入口) + `--batch inbox/<f1>...inbox/<fn>`(批量入口)
- SKILL.md 调 convert-to-md.py --batch 必须显式 Bash timeout: 600000ms(Claude Code Bash 工具 max)

**Round 3: Q9 双字段 source_file + sources[].resource**

- **§3.6.1.1** 新整段:`source_file:` 顶层字符串(Obsidian 笔记属性面板可点击)+ `sources[].resource` OKF §5.1 数组(机器可读),值必须相等(lint C5.1 一致性断言);`raw_category` 派生继续走 `sources[0].resource`(不变)
- 物理新建 `templates/source-page.md`(frontmatter 锁 + LLM 写入指引 + 不变量)
- SCHEMA.md §2.2 `type: source` 必填字段表拆 3 行

**Round 4: Q10 scripts 严禁交互硬契约 + plan 文件 audit trail**

- **§1.4** 新整段 "scripts/ 严禁交互硬契约(NFR-1 加严,Q10)":禁止 `input(` / `sys.stdin.read` / `getpass` / `select` 等调用 + 替代方案 + scripts/ 与 SKILL.md 责任分工表
- **§4.2.x** 新整段 "ingest 提案 / 拍板 / 应用 三段落档(audit trail)":`temp/proposal-<hash>.json` → SKILL.md 拍板 → `temp/decision-<hash>.json` → scripts `--apply`;log.md 引用 plan 文件路径留痕
- scripts/README.md 新增"调用约定(scripts/ 严禁交互)"段

**Round 5: Q11 subagent 写权矩阵 + 阶段 3 串行动作清单**

- **§4.2.1** 新整段 "写权矩阵(并发安全硬约束,Q11)":13 行路径 × 3 阶段写权表 + 子代理 prompt 硬约束文本 + 为什么这样设计 3 条
- **§4.2.1** 新整段 "阶段 3 主 agent 串行动作清单(Q11)":命名飘 → 拍板汇总 → concept 去重 → entity 去重 → mv → source 页 → entity 页 → concept 页 → 最后一次性改索引(9 步严格串行)
- 关键设计:索引写顺序——所有 page 写完**才**统一改 index.md / glossary.md / log.md / overview.md,避免过程中失败导致索引指向不存在页

**附带**:Q6 wikilink 改造 + `links:` 镜像字段机制(frontmatter `links:` 自动从正文 wikilink / markdown link 同步生成,OKF v0.2 §9 推荐字段,供外部 OKF 工具无正文解析消费)在 v0.2 一并冻结。

**兼容性**:v0.2 MINOR bump,所有改动对 OKF v0.2 spec §9 兼容性保持。无 breaking change。

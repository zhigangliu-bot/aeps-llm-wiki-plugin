# aeps-llm-wiki-plugin — design.md

> **状态**:草稿 v0.1(待 review)
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

## 1. 模块边界

### 1.1 目录布局(plugin 本体 = `src/`)

```
src/
├── .claude-plugin/
│ └── plugin.json                  # plugin manifest(name / version / skills 列表)
├── skills/                        # 【运行路径】Agent 入口
│   ├── aeps-llm-wiki-init/SKILL.md
│   ├── aeps-llm-wiki-ingest/SKILL.md
│   ├── aeps-llm-wiki-query/SKILL.md
│   ├── aeps-llm-wiki-lint/SKILL.md
│   └── aeps-llm-wiki-status/SKILL.md  # 可选
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
├── scripts/                      # 【运行路径】skill 调用的辅助脚本(当前空)
│   └── README.md                  # scripts/ 约定 + 未来脚本规划 + "不带运行时"边界
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
├── requirements.txt              # 【不进运行路径】第三方 Python 依赖清单
├── LICENSE
 └── .gitignore
```

### 1.2 模块职责(每个一行)

| 模块                                          | 职责                                                                                                                                       | 进 plugin 运行路径?          |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------- |
| `.claude-plugin/plugin.json`                | plugin manifest,声明 name / version / skills 列表                                                                                          | ✅                           |
| `skills/*/SKILL.md`                         | 每个 skill 是一个独立的 Agent 入口                                                                                                         | ✅                           |
| `templates/*`                               | 静态模板,init 时复制到用户项目                                                                                                             | ✅                           |
| `schema/frontmatter.schema.yaml`            | frontmatter 字段机器可读定义,单一真理源                                                                                                    | ✅(被 skills/templates 引用) |
| `scripts/*`                                 | skill 调用的辅助脚本;**当前为空**;所有脚本必须**单次运行即退出**,不开 daemon / 不挂监听 / 不暴露服务(与"不带运行时"约束不冲突) | ✅(将来被 skills 调用)       |
| `requirements.txt`                          | 第三方 Python 依赖清单(为 scripts/ 将来用到的库预留);plugin README 指引用户`pip install -r requirements.txt`                             | ❌(构建/部署时用)            |
| `docs/*`                                    | 用户文档                                                                                                                                   | ❌                           |
| `tests/*`                                   | 离线验证 plugin 产物                                                                                                                       | ❌                           |
| `prd.md` / `design.md` / `implement.md` | 文档三件套                                                                                                                                 | ❌                           |
| `LICENSE`                                   | Apache 2.0                                                                                                                                 | ❌                           |
| `.gitignore`                                | git 忽略规则                                                                                                                               | ❌                           |

### 1.3 边界规则(明确"进 / 不进运行路径"的作用)

- **运行路径** = plugin 装到用户 Claude Code 后会被读 / 调用的部分(skills + templates + schema + scripts)
- **不进运行路径** = plugin 维护者自己看 + 开发者自测用;**用户装上 plugin 后不需要这些文件也能正常工作**
- **`requirements.txt` 是边界案例**:plugin 本身不需要它工作(因为 scripts/ 当前为空),但**当 scripts/ 里有 Python helper 时,用户必须先 `pip install -r requirements.txt`**才能用那些 helper。这层依赖关系在 `docs/README.md` 里说清楚

### 1.4 scripts/ 与"不带运行时"的边界

CLAUDE.md 约束 "plugin 不带运行时"。scripts/ 必须满足:

- ✅ 单次运行就退出(`python script.py <args>` 或 `bash script.sh <args>`)
- ✅ 无状态(不读全局配置 / 不写缓存文件 / 不维护 session)
- ❌ 不开 daemon / 不挂监听 / 不暴露服务
- ❌ 不监听文件系统变化

**判断一个候选脚本是否允许加进 scripts/**:如果它的执行模型是"agent 调一次,跑完退,产出结果或修改文件",允许;如果是"持续跑 / 持续监听 / 对外暴露接口",不允许。

---

## 2. 目录与文件命名

### 2.1 用户项目目录(默认)

```
<user-project>/
├── inbox/                          # 暂存入口,G7,init 时建 + README + .gitkeep
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
  - agent / 工具:`<producer>/<version>`,例 `aeps-llm-wiki/0.1`
  - 人:`human:<id>`,例 `human:zhigang.liu`
  - 进程:`process:<id>`,例 `process:weekly-lint`

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

1. **init 时**:复制一份到 `<project>/<raw-dir>/concept-entities-readme.md`(对齐 raw-readme.md 的复制策略)
2. **ingest/query/lint 时**:LLM 直接读 `<project>/<raw-dir>/concept-entities-readme.md` 决定子类(用户项目副本为权威,plugin 本体仅供 plugin 维护者编辑);**SKILL.md 显式告诉 LLM "读用户项目里的 concept-entities-readme.md"**

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
  by: aeps-llm-wiki/0.1
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

**`tags` 五轴受控词表设计**(plugin 行为约束,**OKF 字段 + plugin 强制写法**):

> OKF v0.2 §4.1 把 `tags` 定义为 "a YAML list of short strings for cross-cutting categorization",本身是 folksonomy 层。Plugin 在此基础上引入 **五轴受控词表**,解决两个真实痛点:拼写漂移(`autosar` / `AUTOSAR` / `Autosar` 三种写法)+ 维度混乱(同一 tag 跨多个语义维度)。详见 [`templates/tag-template.md`](templates/tag-template.md),权威字典。

**写法**:**`<axis>/<value>` 前缀命名空间**(如 `domain/ai`),Obsidian YAML 不解析为 map key,机读友好。**禁止**无前缀的裸 tag(`ai` 单独出现非法)。

**五轴**:

| axis      | 词数 | 单值/多值                            | 必填?                                |
| --------- | ---- | ------------------------------------ | ------------------------------------ |
| `domain`   | 14   | 单值(软上限 ≤ 2,最多 5;v0.6 加 `fusa` + `cybersecurity` 主题入口)| ⚠️ 推荐必填                          |
| `layer`    | 9    | 单值优先(纯物理/逻辑堆栈,v0.6 撤回 fusa/cybersecurity)| 可选                                 |
| `phase`    | 8    | **可多值**(纯时间/研发阶段,v0.6 缩回 8 个值)| 可选                                 |
| `docform`  | 14   | **单值必填**(文档用途;详见 `templates/tag-template.md` §6;对齐 AE 2026-03 标签规范"核心分类")| ✅ 必填 |
| `maturity` | 5    | **单值必填**(`concept < research < pilot < production < standard`,用于笔记权重判断) | ✅ 必填 |
| `tec`      | ~45  | 单值优先(v0.5 加 `iso26262-asil-b` `secoc` `hsm` 保留)| 可选                                 |

**LLM 工作流**(SKILL.md 显式告诉 LLM):

1. 读源文件 → 候选 tag 草稿
2. 读 `templates/tag-template.md` 比对**六轴**词表
   - 候选 tag ∈ 词表 → 采用,加 axis 前缀
   - 候选 tag ∉ 词表 → 同义/近义词表词 → 用词表词替代 + WARN;新概念 → 提议加入字典 + 临时用自由 tag + WARN
3. 落 frontmatter,例:`tags: [domain/ai, layer/algorithm, phase/design, phase/verification, maturity/research]`
4. log.md 记一笔 "tags: 取自字典 X 个,字典外 Y 个"

**lint 规则**(对应 §4.4):

| 现象 | 行为 |
|---|---|
| 裸 tag(`ai` 无前缀) | FAIL |
| 字典外 tag | WARN,累计 ≥ 5 次建议下次 plugin 升级时加入字典 |
| 缺失 `maturity/` | FAIL(必填) |
| 缺失 `domain/` | WARN |
| 单页 `domain` > 5 个 | 提示"切片失去区分度,建议合并" |
| 同一 axis 重复(如 `domain/ai` 出现 2 次) | FAIL |
| 拼写变体聚类(`autosar` / `AUTOSAR`) | WARN,推荐字典 prefLabel |
| 词序变体(`autosar-adaptive` / `adaptive-autosar`) | WARN,推荐字典 prefLabel |
| 频次 ≥ 10 | "热门,可考虑固化" |
| 频次 = 1 | "冷僻,真的需要保留?" |

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

| 字段 | 类型 | 用途 |
|---|---|---|
| `updated` | ISO 8601 timestamp | 最后修改时间(OKF 无对应) |
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

**为什么这样设计**:`description` 太短,LLM 想给概念页写一段完整概述时没地方放;放正文又会让所有页面顶部都有一个"## 摘要"小节,UI 重复且冗余。Frontmatter 字段既能被工具消费,又不在正文里占位。

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

# type 合法值(与 §3.1 表对齐,entities/concepts 14 子类由 templates/concept-entities-readme.md 字典为权威)
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
  agent: '^[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+$'    # 例 aeps-llm-wiki/0.1
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

### 3.3 链接约定(从 prd §6.2 §E 抽出)

- **仅标准 markdown 链接**:`[text](url)`(OKF §6.1 强制;plugin 强制)
- 优先 bundle-relative 绝对路径:`[customers](/tables/customers.md)`(OKF §6.1 推荐)
- 也接受相对路径:`[neighbor](./other.md)`
- 链接类型(父子 / 引用 / 依赖)由**正文描述**,不由链接类型化
- plugin 必须容忍断链(OKF §6.1:不是 malformed)
- **lint 规则**:遇到 `[[wikilink]]` 给 warning(OKF 不认,但不报错以兼容老 Karpathy 仓库)

### 3.4 `log.md` 格式(从 prd §6.2 §F 抽出)

```markdown
# Directory Update Log

## 2026-09-01
* **Creation**: Established [Open Knowledge Format](../concepts/open-knowledge-format.md).
* **Update**: Updated [glossary](../glossary.md).

## 2026-08-25
* **Initialization**: Created foundational directory structure.
```

**强制**:

- 日期 heading 一律 ISO 8601 `YYYY-MM-DD`
- **最新在前**
- 粗体前缀仅三个词:`**Creation**` / `**Update**` / `**Deprecation**`(plugin 强制以便 lint 解析)
- inbox → raw 迁移 log 模板:`**Migration**: [file.md](inbox/file.md) → [file.md](../raw/<subdir>/file.md)`

### 3.5 `knowledge/` 种子文件(顶层 5 个)

| 文件            | 谁写                                    | 模板                                | 模板里要锁什么                                                                                                                                                                                                                                                                             |
| --------------- | --------------------------------------- | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `index.md`    | LLM 每次 ingest/query 后自动维护        | `templates/knowledge-index.md`    | ✅**格式锁**:OKF frontmatter(`type` 必填,`bundle-root: true` 标记,§D);条目格式 `- [name](path) — type · 一句话`;排序规则(按 type 分组?按字母?);空状态文案("还没有条目,跑 /aeps-llm-wiki-ingest 起步")                                                                       |
| `overview.md` | LLM 视情况更新(大图变化时)              | `templates/knowledge-overview.md` | ⚠️**格式软锁**:frontmatter `type: overview` + `bundle-root: true`;**结构骨架锁**(标题层级:领域全景 / 关键概念 / 当前工作重点 / 待补),具体内容 LLM 自由发挥                                                                                                               |
| `glossary.md` | LLM 在 ingest 时新增/修改术语           | `templates/knowledge-glossary.md` | ✅**条目格式锁**:`**术语** (英文) — 一句话定义`;**不带 frontmatter**(索引体不是 wiki 页);排序规则(中英按拼音)                                                                                                                                                               |
| `log.md`      | LLM 在每次变更后追加一条(多 skill 共写) | `templates/knowledge-log.md`      | ✅**格式锁严**:ISO 8601 时间戳;**最新在前**;条目模板 `**Action**: <verb> <object> by <actor>` + 关联路径链接;actor 字符串约定(`agent: aeps-llm-wiki/<skill>` / `human:zhigang.liu`);粗体前缀仅 `Creation/Update/Deprecation/Migration` 四种(plugin 强制以便 lint 解析) |
| `SCHEMA.md`   | plugin 在 init 时一次性写入             | `templates/knowledge-SCHEMA.md`   | ✅**格式锁 + 内容锁**:frontmatter(`type: schema`);完整目录结构图(用户项目视角)+ frontmatter schema(§A §B §C 三层)+ skill 操作手册(ingest/query/lint 步骤)+ 链接约定 + log 格式。**这是 LLM 的操作手册,不能漂**                                                            |

### 3.6 `knowledge/` 类型子目录与正文骨架

子目录与 `type` 1:1:1 绑死 —— `type: person` 必在 `entities/person/`,`type: theory` 必在 `concepts/theory/`,等等(违规由 lint FAIL)。完整 type ↔ 目录 ↔ 含义 三联表见 §3.4。

| 子目录                     | OKF`type`      | 模板要锁什么                                                                                                                                                                                                                                                                                                                                                      |
| -------------------------- | ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sources/`               | `source`       | ✅**frontmatter + 正文骨架都锁死**。frontmatter:`type: source` + `source_path` 指向 raw/ 原件相对路径 + `created_at` + 长摘要走 `summary` 字段(2-5 段,见 §3.1 §C)。**正文禁止出现 `## 摘要` 小节**(纪律见 §3.1 §C)。正文 **3 节骨架硬约束**(任何缺失 = lint FAIL):`## 重点摘录`、`## 我的思考`、`## 总结:最有收获的一句话`。`## 我的思考` 用第一人称。                                                                   |
| `entities/person/`       | `person`       | ⚠️**frontmatter 锁**(`type: person` + `summary` + `last_reviewed`),**正文自由发挥**(人物页通常包含:身份、关键贡献、引用源)                                                                                                                                                                                                                    |
| `entities/organization/` | `organization` | ⚠️**frontmatter 锁**;**正文自由发挥**(组织页通常包含:领域定位、代表产品/项目、引用源)                                                                                                                                                                                                                                                               |
| `entities/project/`      | `project`      | ⚠️**frontmatter 锁**;**正文自由发挥**(项目页通常包含:范围、时间线、关键里程碑、引用源)                                                                                                                                                                                                                                                              |
| `entities/product/`      | `product`      | ⚠️**frontmatter 锁**;**正文自由发挥**(产品页通常包含:定位、关键参数、典型应用、引用源)                                                                                                                                                                                                                                                              |
| `entities/event/`        | `event`        | ⚠️**frontmatter 锁**;**正文自由发挥**(事件页通常包含:时间、地点、参与者、产出)                                                                                                                                                                                                                                                                      |
| `entities/place/`        | `place`        | ⚠️**frontmatter 锁**;**正文自由发挥**(地点页通常包含:地理位置、相关活动/组织)                                                                                                                                                                                                                                                                       |
| `entities/other/`        | `other`        | ⚠️**frontmatter 锁**;**正文自由发挥**(兜底)                                                                                                                                                                                                                                                                                                         |
| `concepts/theory/`       | `theory`       | ⚠️**frontmatter 锁**;**正文自由发挥**(理论页通常包含:核心命题、推导过程、适用边界)                                                                                                                                                                                                                                                                  |
| `concepts/method/`       | `method`       | ⚠️**frontmatter 锁**;**正文自由发挥**(方法页通常包含:适用场景、步骤、工具链、对比其他方法)                                                                                                                                                                                                                                                          |
| `concepts/field/`        | `field`        | ⚠️**frontmatter 锁**;**正文自由发挥**(领域页通常包含:范畴、关键问题、与相邻领域关系)                                                                                                                                                                                                                                                                |
| `concepts/phenomenon/`   | `phenomenon`   | ⚠️**frontmatter 锁**;**正文自由发挥**(现象页通常包含:现象描述、根因分析、影响、应对)                                                                                                                                                                                                                                                                |
| `concepts/standard/`     | `standard`     | ⚠️**frontmatter 锁**;**正文自由发挥**(标准页通常包含:发布机构、版本、约束范围、与相邻标准关系)                                                                                                                                                                                                                                                      |
| `concepts/term/`         | `term`         | ⚠️**frontmatter 锁**;**正文自由发挥**(术语页通常包含:定义、起源、典型用例、相邻术语)                                                                                                                                                                                                                                                                |
| `concepts/other/`        | `other`        | ⚠️**frontmatter 锁**;**正文自由发挥**(兜底)                                                                                                                                                                                                                                                                                                         |
| `analyses/`              | `analysis`     | ✅**frontmatter + 正文骨架都锁死**(query 落档强制套)。frontmatter:`type: analysis` + `answer_to`(原问题)+ `generated_by: agent: aeps-llm-wiki/<skill>` + 长摘要走 `summary` 字段(必须**首行保留 query 原问句** `**问题**: <原问句>`,纪律见 §3.1 §C)。**正文禁止出现 `## 摘要` 小节**。正文 **3 节骨架硬约束**(任何缺失 = lint FAIL):`## 重点摘录`、`## 我的思考`、`## 总结:最有收获的一句话`。 |
| `comparisons/`           | `comparison`   | ⚠️**frontmatter 锁**(`type: comparison` + `sources:` 链接到对比的 entity/concept 页 + `last_updated`);**正文自由发挥**,但典型结构:多栏对照表 + 维度差异 + 各自适用场景                                                                                                                                                                        |
| `syntheses/`             | `synthesis`    | ⚠️**frontmatter 锁**(`type: synthesis` + `sources_count` 引用了多少页 + `last_updated`);**正文自由发挥**,但典型结构:主题脉络梳理 + 多观点融合 + 个人判断                                                                                                                                                                                      |

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

**配套模板文件**(init 时复制/填充):

| 模板文件                            | 内容                                              |
| ----------------------------------- | ------------------------------------------------- |
| `templates/raw-readme.md`         | 字典本体(15 类 + 边界规则)—— ✅ 已存在          |
| `templates/inbox-readme.md`       | 简版提示,告诉用户"放什么、放完跑 ingest"(2026-09-02 完成) |
| `templates/knowledge-SCHEMA.md`   | 锁得最严(8 节,占位符 init 替换)               |
| `templates/knowledge-index.md`    | 锁结构                                            |
| `templates/knowledge-overview.md` | 锁骨架                                            |
| `templates/knowledge-glossary.md` | 锁条目格式                                        |
| `templates/knowledge-log.md`      | 锁得严                                            |

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

1. **询问**(一次):
   - `--knowledge-dir`(默认 `knowledge/`)
   - `--raw-dir`(默认 `raw/`)
   - `--inbox-dir`(默认 `inbox/`)
2. 创建 `<project>/<inbox-dir>/.gitkeep` + `<project>/<inbox-dir>/README.md`(从 templates/inbox-readme.md)
3. 创建 `<project>/<raw-dir>/.gitkeep` + `<project>/<raw-dir>/README.md`(从 templates/raw-readme.md) + `<project>/<raw-dir>/concept-entities-readme.md`(从 templates/concept-entities-readme.md) + `<project>/<raw-dir>/tag-template.md`(从 templates/tag-template.md)。**按 raw-readme.md 的 15 类全部预建默认子目录**,每个子目录放 `.gitkeep` 占位
4. 创建 `<project>/<knowledge-dir>/` 下:
   - `SCHEMA.md`(从 templates/knowledge-SCHEMA.md,**写入具体目录名和 actor 字符串**)
   - `index.md` + `overview.md` + `glossary.md` + `log.md`(从对应模板)
   - `sources/` + `entities/{person,organization,project,product,event,place,other}/` + `concepts/{theory,method,field,phenomenon,standard,term,other}/` + `analyses/`,**每个叶子目录放 `.gitkeep`**
5. **不应**:覆盖已存在的内容(若 `<knowledge-dir>/` 已存在,**走幂等再入**,见下方)

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

**字典文件 sync 策略**(`raw-readme.md` / `concept-entities-readme.md` / `tag-template.md`):

| 情况 | 行为 |
|---|---|
| 用户项目里**没有**该字典文件 | **直接复制**整份 |
| 用户项目里有,但 plugin 新版**新增了 H2 章节** | 把新章节 append 到文件末尾 |
| 用户项目里有,plugin 新版**新增了某个 H2 章节内的条目** | 把新条目 append 到该 H2 章节末尾 |
| 用户项目里有,**条目已存在但 plugin 新版内容更新了**(说明文字变了) | **不覆盖**用户本地;lint 报告"plugin 新版有 X 条本地无/不一致,要不要采纳?" |
| 用户项目里有,**用户本地新增的内容**(自定义目录说明、自定义子类、自定义 tag) | **保留**,plugin 不动 |
| 用户项目里有,**用户本地删除的条目** | **不补回**,lint 提示"plugin 新版有 X 条本地无" |

**目录 sync 策略**(`raw/<15 类>/`、`knowledge/<14 子类 + comparisons + syntheses>/`):

- plugin 新版 dict 新增了 raw 子目录(例:`16_xxx/`)? → **不动**(用户没主动建就不建,见 §2.2 ingest 拍板门)
- plugin 新版新增了 entities/concepts 子类(例:`entities/tool/`)? → **不动**(同上)
- 用户项目里**缺的** 15 类 / 14 子类? → **补建 + 放 .gitkeep**

**普通文件 sync 策略**(`SCHEMA.md` / `index.md` / `overview.md` / `glossary.md` / `log.md` / `inbox/README.md`):

- `SCHEMA.md` / `index.md` / `overview.md`:plugin 自己写的,**幂等再入时直接覆盖**(SCHEMA.md 是 plugin 操作手册,plugin 维护者改完应该生效;index.md / overview.md 是 LLM 维护的,但首次 init 后用户没主动改过的话,直接覆盖是 OK 的)
- `log.md`: **绝不覆盖**,append 一条 `**Init re-run**: plugin v<x.y.z> by human:zhigang.liu at <ISO 8601>`
- `glossary.md`: **绝不覆盖**,不动
- `inbox/README.md`: 直接覆盖(简版提示,plugin 维护)

**`user.dir` 缺失目录补建策略**:

- 用户项目里 inbox/ 不存在 → 重建
- 用户项目里 raw/<某子类>/ 不存在 → 补建 + .gitkeep
- 用户项目里 knowledge/<某子类>/ 不存在 → 补建 + .gitkeep
- 用户项目里 .gitkeep 缺失 → 补

**结束提示**:init 完成后,**向用户报告**:

```
Init re-run 完成。sync 摘要:
- 字典 raw-readme.md: 复制 0 / append 2 章节 0 条 / 跳过(本地已删) 1 条
- 字典 concept-entities-readme.md: 复制 0 / append 1 章节 / 跳过 0
- 字典 tag-template.md: 复制 0 / append 1 章节 3 条 / 跳过 0
- 缺失目录补建: raw/02_芯片/  (其它都齐)
- 文件覆盖: SCHEMA.md / index.md / overview.md / inbox/README.md
- log.md 追加: 1 条 re-run 记录
- 你的本地修改一律保留,以上只是 plugin 新版 append
```

**不应**:静默覆盖任何用户本地新增/修改/删除的内容。

### 4.2 `/aeps-llm-wiki-ingest`

**触发场景**:用户把资料放 raw/ 或 inbox/ 后。

**Agent 行为**:

1. **解析路径**:
   - `raw/<path>` → 走 `arch` 分支(不移动文件)
   - `inbox/<path>` → 走 `staging` 分支(用户拍板后迁移)
2. 读源文件(markdown / txt / pdf / docx,Claude 内置 converter)
3. **路径来自 `inbox/`**:
   - LLM **提议**一个 raw 子目录分类 + 短理由(参考 `<project>/raw/raw-readme.md` 的 15 类清单和边界规则)
   - 提议格式:`建议迁到 raw/<subdir>/<basename>`,其中 `<subdir>` 可能是:
     - 一级:`06_功能安全`(从 15 类中选)
     - 二级:`12_法规_标准_政策/V2X`(LLM 自主判定需要二级时)
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
- `generated` = `{ by: aeps-llm-wiki/0.1, at: <now ISO 8601> }`
- `tags` = LLM 抽取 3~5 个
- `created` / `updated` = `<now ISO 8601>`
- `summary` = `description` 同值(Q1 暂留冗余)

### 4.3 `/aeps-llm-wiki-query`

**Agent 行为**:

1. 读 `knowledge/index.md` 找候选页
2. **优先级**(从低到高读):
   - description / summary(几乎所有候选都先读这个)
   - title 段
   - 全文(只在 description 不够时)
3. 回答,**每条断言附 wiki 标准 markdown 链接**
4. 回答结束后**问用户是否落档** → 落档则新建 `type: analysis` 页,放 `knowledge/analyses/<时间戳>-<slug>.md`,追加 log
5. **不应**:编造 wiki 里没有的内容

### 4.4 `/aeps-llm-wiki-lint`

**Agent 行为**:

1. 扫所有 `knowledge/**/*.md` 文件
2. 报告:
   - **孤儿页**:无出入链接的页(可豁免 `index.md` / `overview.md` / `glossary.md`)
   - **矛盾**:两个页对同一事实说法不同(LLM 判断)
   - **陈旧页**(拍板 2026-09-02):
     - **优先判定**:`stale_after` 字段存在且 `now >= stale_after` → 陈旧(OKF §5.5 语义)
     - **回退判定**:`stale_after` 缺失 + `updated` 时间 > **180 天** + 最近 `log.md` 无提及 → 陈旧
     - **豁免**:`status: deprecated` 页(已声明归档,不算陈旧)
     - **不豁免**:`status: draft`(草稿也会陈旧,提示"长期未更新草稿")
     - 阈值常量 `STALE_THRESHOLD_DAYS = 180`,plugin 本体 `constants.py` 可改

   - **LLM 命名飘**(拍板 2026-09-02):相似子目录/页面名检测,触发"合并建议"
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
   - **`[[wikilink]]` 残留**:warning,建议改标准 markdown
3. 默认只报告;`--fix` 模式提议一次性 diff 让用户确认后应用
4. **不应**:静默修改文件

### 4.5 `/aeps-llm-wiki-status`(可选)

- 只读:列总页数、按 type 分组、最近 10 条 log、孤儿数
- 不写

### 4.6 `/aeps-llm-wiki-synthesize <topic>`

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

### 4.7 `/aeps-llm-wiki-query` 内 comparison 自然触发机制

**不增加 skill**,由 query skill + ingest skill 共同承担:

#### 路径 A — ingest 触发(同类 entity 提议)

触发点:`/aeps-llm-wiki-ingest` 完成,**在 source 页落档询问时**(§4.2 末尾),LLM 检查:

- `entities/<子类>/` 下**同 type** 的现有 entity 数
- 这次新 ingest 涉及的 entity 是否 ≥ 2 个同类
- 若满足,LLM 在询问时**附一句**:"现有同类 entity X 个(列表),要不要建一个常驻 comparison 页把它们对照一下?"

#### 路径 B — query 累计触发(高频检索提议)

触发点:`/aeps-llm-wiki-query` 完成,**在落档询问时**,LLM 检查 `knowledge/log.md`:

- 用模式 `**Action**: ... query ... X.*Y` 匹配历史 query 条目
- 若 "X vs Y" 累计 ≥ 3 次,**下次落档询问时只提一次**:"X vs Y 这个对比提过几次了,要不要建一个常驻 comparison 页?"

**comparison 页生成规则**:

- 路径:`knowledge/comparisons/<a>-vs-<b>.md`(**不带时间戳**,常驻)
- frontmatter:`type: comparison` + `sources:` 字段(`[aurix.md, tc397.md]` 列表) + `last_updated: <ISO 8601>`
- 正文**自由发挥**,SKILL.md 给提示:典型结构 = 多栏对照表 + 维度差异 + 各自适用场景

**关键边界**:

- query **一次性**给完对比表就结束 → 是 answer,不是 comparison(**不建**)
- comparison 是**常驻页**,需要用户拍板后才建
- lint 兜底:`comparisons/*.md` 必须有 `type: comparison` + `sources:` 字段(否则 FAIL)

---

## 5. 关键流程

### 5.1 Ingest 流程(inbox → raw → knowledge)

```
[用户丢 inbox/<file>]
       ↓
[用户跑 /aeps-llm-wiki-ingest inbox/<file>]
       ↓
[skill:LLM 读 inbox/<file>]
       ↓
[skill:LLM 提议 raw/<subdir>/<file> + 理由]
       ↓
[用户拍板 / 改 / --raw-subdir]
       ↓
[skill:mv inbox/<file> → raw/<subdir>/<file>]
       ↓
[skill:log.md 记 **Migration**]
       ↓
[skill:LLM 读 raw/<subdir>/<file>]
       ↓
[skill:生成 knowledge/sources/<basename>.md]
       ↓
[skill:抽取 → 生成 knowledge/entities/<子类>/*.md / knowledge/concepts/<子类>/*.md]
       ↓
[skill:更新 knowledge/index.md / glossary.md / overview.md]
       ↓
[skill:log.md 记 **Creation** / **Update**]
       ↓
[可选路径 A:同类 entity ≥ 2 → LLM 提议建 knowledge/comparisons/<a>-vs-<b>.md]
```

**`--raw-subdir=<name>` 适用边界(拍板 2026-09-02)**:

| 来源            | `--raw-subdir=<name>` 行为                                                                   | 理由                                                                |
| --------------- | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| `inbox/<file>` | **生效** —— 跳过分类交互,直接 `mv inbox/<file> → raw/<name>/<file>`,`log.md` 记迁移路径       | inbox 是暂存层,目标就是"迁到 raw/<subdir>/",参数等价于"我知道该放哪"  |
| `raw/<path>`   | **不生效,lint 报错** —— raw 路径文件已归档,移动文件超出 ingest 语义,应走 `git mv` 或手工调整 | ingest 只读 + 生成知识页,**不该**改 raw 目录结构,否则破坏归档      |

**Lint 规则**:

- 出现 `ingest --raw-subdir=<name> raw/<file>` → **FAIL**,提示"raw 路径不支持 `--raw-subdir`,文件已归档,请走 `git mv` 或在 raw/ 内手工调整"
- 出现 `ingest --raw-subdir=<name> inbox/<file>` 且 `<name>` 不在 init 预建的 15 类 → **WARN**,提示"自定义目录,需要拍板门确认"

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
3. 跑 `/aeps-llm-wiki-ingest inbox/OKF-SPEC.md`,**拍板** raw/okf/
4. 验证:文件已迁、source 页存在、index.md 更新、log.md 有 **Migration** 条目
5. 跑 `/aeps-llm-wiki-query "OKF 必填字段"`(prd AC-3)
6. 跑 `/aeps-llm-wiki-lint` 看报告
7. 把 `knowledge/` 喂给 OKF 第三方 reader,确认无报错

### 6.3 兼容性测试

- 用户从 Karpathy 风格 wiki 导入,plugin 警告 `[[wikilink]]` 残留但不强转
- 不同 OKF v0.x 字段(schema 校验脚本跑过两个 v0.1 + v0.2 样本)

---

## 7. 待定(TBD)

- [x] **T2**:`summary` 字段去留(Q1,倾向只留 `description`)— 拍板:留 `summary`,去掉 source 正文里的 `## 摘要` 小节(summary 走 frontmatter)
- [x] **T3**:`--raw-subdir` 适用边界(2026-09-02 拍板)— **仅 inbox 生效**,raw 路径走 `git mv`
- [x] **T4**:`SCHEMA.md` 模板 — 已完成 `templates/knowledge-SCHEMA.md`(8 节,含占位符 init 替换)(2026-09-02)
- [x] **T5**:`templates/inbox-readme.md` 提示语 — 已完成(2026-09-02)
- [x] **T6**:陈旧阈值 + LLM 起名飘 lint — 拍板:180 天 / `stale_after` 优先 / 命名飘仅 prompt 不合并(2026-09-02)

---

## 8. 参考

- [prd.md](prd.md) —— 产品需求(本文件的源头)
- [implement.md](implement.md) —— 执行清单(下一步)
- [../../input/kapathy-llm-wiki/kapathy-llm-wiki.en.md](../../input/kapathy-llm-wiki/kapathy-llm-wiki.en.md) —— Karpathy LLM Wiki 理念
- [../../input/google-OKF/OKF-SPEC.md](../../input/google-OKF/OKF-SPEC.md) —— OKF v0.x 规范(本文件 §3 主要依据)
- [../../reference/balukosuri__llm-wiki-karpathy/CLAUDE.md](../../reference/balukosuri__llm-wiki-karpathy/CLAUDE.md) —— Karpathy 模式 Agent 操作手册范本

---

**下一步**:等本文件 review 通过 + T1~T6 拍板 → 进入 M3(写 `implement.md`)

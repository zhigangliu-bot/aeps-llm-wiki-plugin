# knowledge / SCHEMA.md — 本知识库操作手册

> **角色**:对应 Karpathy LLM Wiki 的 `CLAUDE.md`,Agent 必读。
> **生成方式**:`/aeps-llm-wiki-init` 首次启用时,从 `templates/knowledge-SCHEMA.md` 复制。
> **修改权限**:**用户主**。plugin 升级不会覆盖(对齐字典文件的 sync 策略:本地优先 + lint 提示)。
> **本文件权威**:目录拓扑、actor 字符串、命名约定以本文件为最终口径;plugin 文档若与本文件冲突,以本文件为准。

---

## 1. 目录拓扑

```
project-root/
├── inbox/                              # 暂存层(用户随手丢的资料)
├── raw/                                # 归档层(已分类的源文件)
│   ├── README.md
│   ├── concept-entities-readme.md
│   ├── tag-template.md
│   └── 15_类预建子目录/
└── knowledge/                   # LLM 维护的"知识页"
    ├── SCHEMA.md                       # 本文件
    ├── index.md                        # 主索引(自动生成)
    ├── overview.md                     # 大图(LLM 维护)
    ├── glossary.md                     # 术语表(LLM 维护,**绝不覆盖**)
    ├── log.md                          # 变更日志(append-only)
    ├── sources/basename.md           # 源页(`type: source`)
    ├── entities/子类/slug.md       # 实体页
    ├── concepts/子类/slug.md       # 概念页
    ├── analyses/topic.md             # 分析页(`type: analysis`)
    ├── syntheses/topic-slug.md       # 综合页(`type: synthesis`,常驻)
    └── comparisons/a-vs-b.md       # 对比页(`type: comparison`)
```

### 1.1 raw/ 15 类预建子目录

(由 `raw/README.md` 列出,init 时按 `raw-readme.md` 全量预建 + `.gitkeep` 占位)

### 1.2 knowledge/ 子目录子类

| 路径前缀 | OKF `type` | 子类目录 | 说明 |
|---|---|---|---|
| `sources/` | `source` | — | 源页(对每个源文件一份),正文 3 节 H2 骨架 |
| `entities/person/` | `entity` | `person` | 自然人 |
| `entities/organization/` | `entity` | `organization` | 组织(公司 / 团队 / 部门) |
| `entities/project/` | `entity` | `project` | 项目(BE13-VDP、FAW-CGW 等) |
| `entities/product/` | `entity` | `product` | 产品(域控、S32G 板卡) |
| `entities/event/` | `entity` | `event` | 事件(技术评审、产品发布) |
| `entities/place/` | `entity` | `place` | 地点(总部、研发中心) |
| `entities/other/` | `entity` | `other` | 其他具象存在 |
| `concepts/theory/` | `concept` | `theory` | 学说 / 原理(信息论、控制论) |
| `concepts/method/` | `concept` | `method` | 方法(AUTOSAR 方法论、敏捷 V-Model) |
| `concepts/field/` | `concept` | `field` | 学科 / 领域(EE 架构、网络安全) |
| `concepts/phenomenon/` | `concept` | `phenomenon` | 现象(鞭击效应、过充过放) |
| `concepts/standard/` | `concept` | `standard` | 标准(ISO 26262、ISO 21434) |
| `concepts/term/` | `concept` | `term` | 术语(SOME/IP、FOTA) |
| `concepts/other/` | `concept` | `other` | 其他抽象知识 |
| `analyses/` | `analysis` | — | 分析页(LLM 撰写的深度对比 / 拆解) |
| `syntheses/` | `synthesis` | — | 综合页(topic 宏大综合,常驻) |
| `comparisons/` | `comparison` | — | 对比页(同类 ≥ 2 时 LLM 提议建) |

**子类 ↔ 目录 1:1 绑死**,**禁止**错位(如 `entities/project/foo.md` 不能叫 `entities/project/foo/concept.md`)。

---

## 2. frontmatter 契约

详见 plugin `src/schema/frontmatter.schema.yaml`(OKF v0.2 §A 必填 + §B 推荐 + §C plugin 扩展)。

### 2.1 关键必填字段(全 wiki 通用)

| 字段 | 类型 | 必填 | 备注 |
|---|---|---|---|
| `type` | string | ✅ | 取值见 §1.2 子目录映射表 |
| `title` | string | ✅ | 人类可读标题 |
| `updated` | ISO 8601 | ✅ | 最近一次有意义更新;**重新生成 ≠ 更新** |
| `tags` | string[] | ✅ | 六轴受控词表,详见 `raw/tag-template.md` |

### 2.2 type-specific 字段

- `type: source` 额外必填:`source_file`(指向 `raw/<subdir>/<file>`)、`summary`(≤ 280 字符)
- `type: comparison` 额外必填:`sources:`(≥ 2 条 `[[wikilink]]`)
- `type: synthesis` 额外必填:`topic:`、`sources_count:`、`last_updated:`
- `type: entity` / `type: concept` 额外必填:`aliases:[]`(同义 / 别名)

### 2.3 状态字段(不进 tag)

- `status: draft / stable / deprecated`,缺省 `stable`
- `stale_after: <ISO 8601>`(OKF §5.5),陈旧判定优先看它

---

## 3. 写作纪律

### 3.1 正文骨架硬约束

| 类型 | 必有 H2 小节 | 禁止 H2 小节 |
|---|---|---|
| `source` | `## 重点摘录`、`## 我的思考`、`## 总结:最有收获的一句话`(3 节齐全,缺一 FAIL) | `## 摘要` / `## Summary`(长摘要走 frontmatter `summary` 字段) |
| `analysis` | 同上 3 节 | 同上 |
| `entity` / `concept` | **自由发挥**,不强制小节 | 无 |
| `synthesis` | 自由,但需有 `## 大图` / `## 子主题` / `## 引用` | 无 |
| `comparison` | `## 维度对比表` / `## 结论` | 无 |

### 3.2 tag 纪律

- tag 来自 `raw/tag-template.md` 六轴受控词表,**禁止**裸 tag / 字典外 tag / 拼写漂移
- `docform/`、`maturity/` 单值必填
- 文档状态走 `status` 字段,项目名走 `entities/project/`,**不进 tag**

---

## 4. actor 字符串(操作日志标准化)

本知识库所有 `knowledge/log.md` 记录使用统一 actor 字符串格式:

| 类别 | 格式 | 示例 |
|---|---|---|
| LLM 写 | `agent: producer/<plugin-version>` | `agent: producer/aeps-llm-wiki-plugin/0.4.0` |
| 人类写 | `human:<id>` | `human:zhigang.liu` |
| 工具 / 脚本 | `process:<id>` | `process:aeps-llm-wiki-lint` |

**`<plugin-version>`** 取自本项目 `raw/.aeps-plugin-version`(`init` 时写入),例:

```
agent: producer/aeps-llm-wiki-plugin/0.4.0
```

---

## 5. 工作流速查

### 5.1 ingest(资料入 wiki)

```
1. 用户丢 inbox/<file>(含子目录文件)
2. 跑 /aeps-llm-wiki-ingest(无参数,递归扫 inbox/)
3. SKILL.md 校验 scripts/requirements.txt 依赖(anydoc / paddleocr)是否安装;未装 → 提示并退出
4. 文件读取走 scripts/convert-to-md.mjs,按扩展名分流:
   - md / txt / csv / json / yaml / xml / html / htm / rst → 直接读
   - pptx / docx / xlsx / pdf → Claude converter,失败降级 anydoc
   - png / jpg / jpeg / bmp / tiff → paddleocr
5. LLM 读源 + 提议 raw/<subdir>/
6. 用户拍板(目标目录已存在 → 无需拍板;不存在 → 必须拍板)
7. mv inbox → raw/<subdir>/
8. 生成 knowledge/sources/basename.md
9. 抽取 entity / concept → 自动生成子页
10. 更新 index.md / glossary.md / log.md / overview.md
```

### 5.2 query(查询)

```
1. 跑 /aeps-llm-wiki-query "<question>"
2. SKILL.md 先跑 node ./scripts/check-qmd.mjs --project-dir . → 拿到 engine 决策
   - engine=index(< 500 页):走 4 跳扫描
   - engine=qmd(≥ 500 页且 qmd 在):qmd query "<question>" --collection knowledge --limit 20,拿 top-20 进跳 2
   - engine=fail(≥ 1000 页且 qmd 不在):直接退出,提示"必须装 qmd"
3. (4 跳扫描)跳 1:读 index.md,按 tag 关键词过滤选 top-K(K=10)强候选
4. (4 跳扫描)跳 2:读候选页(优先级 description/summary → title → 全文)
5. (4 跳扫描)跳 3:顺候选页 [[wikilink]] 跳邻居(1 跳深度,硬上限 8 页)
6. (4 跳扫描)跳 4:读 glossary.md(术语消歧)+ log.md 近期 10 条(新 ingest 是否已消化)
7. 回答,每条断言附 wiki [[wikilink]]
8. 落档询问 → type: analysis 页放 knowledge/analyses/<时间戳>-<slug>.md
9. 不编造 wiki 里没有的内容
```

### 5.3 lint(健康检查)

```
1. 跑 /aeps-llm-wiki-lint
2. LLM 扫所有 knowledge/**/*.md
3. 报告:孤儿页 / 矛盾 / 陈旧页 / LLM 命名飘 / 漏链 / frontmatter 不合规 / 摘要小节残留
4. --fix 模式按问题级别分流:
   - 确定性结构修复(frontmatter / 3 节骨架 / `## 摘要` 残留)直接 patch 应用,log.md 追加 **LintFix** 条目
   - 语义级问题(矛盾 / 命名飘合并 / 漏链 / 陈旧处理)仅出提案,不应用,等用户确认
   - `[[wikilink]]` 是一等公民(Q6):Obsidian 原生双链 / Karpathy 老 wiki 兼容;OKF 兼容靠 frontmatter `links:` 字段镜像;lint 不再警告 wikilink
```

### 5.4 synthesis(综合页)

```
1. 跑 /aeps-llm-wiki-synthesize "topic"
2. LLM 收集 topic 相关 entity/concept/source 页
3. 写常驻 synthesis 页到 knowledge/syntheses/topic-slug.md
```

---

## 6. lint 规则摘要

| 类别 | 现象 | 行为 | `--fix` 模式 |
|---|---|---|---|
| frontmatter | 必填字段缺失 / 类型错位 / 未知 type | FAIL | **自动修复**(补占位 / 强转) |
| frontmatter | `summary` 缺失(仅 source/analysis) | FAIL | **自动修复**(从正文首段提取) |
| 正文骨架 | source/analysis 缺 3 节 H2 | FAIL | **自动修复**(末尾追加占位 H2) |
| 正文骨架 | 含 `## 摘要` / `## Summary` H2 | FAIL | **自动修复**(删小节,内容合并到 frontmatter `summary`) |
| 类型映射 | type 与子目录不符(如 `entities/foo/concept.md` 用了 `type: concept`) | FAIL | **自动修复**(按子目录推 type) |
| 陈旧页 | `stale_after` 已超越 / `updated > 180 天` + log 未提 | WARN(可配 FAIL) | **仅出提案**(归档 / `status: deprecated` / 续期,等用户拍板) |
| LLM 命名飘 | 相似子目录(归一化后 Levenshtein ≤ 2) / 同义拼写 | WARN + 合并建议 | **仅出提案**(`git mv` 命令,用户手动执行) |
| 漏链 | 正文反复出现但未链接的术语 | WARN | **仅出提案**(候选链接列表,等用户确认) |
| 矛盾 | 两页同一事实不同说法 | WARN | **仅出提案**(diff + 候选改写,等用户拍板) |
| 孤儿页 | 无出入链接的页 | WARN(豁免 index/overview/glossary) | **仅出提案**(候选出入链接 / 删除候选,等用户拍板) |
| tag | 裸 tag / 字典外 tag / 拼写漂移 / 状态词混 tag | FAIL/WARN 视 lint 细则 | 部分自动(`tags` 拼写归一化),其余仅出提案 |

**LLM 命名飘不自动合并** —— lint 只提示,人工 `git mv` 归档到 `raw/_archived/`。
**但 ingest 时前移拦截(Q5)**:LLM 提议 raw 子目录名的瞬间,先与 `raw/` 现有子目录做相似度比较(Levenshtein ≤ 2 / 前缀差异 / 同义拼写);命中已有相似目录 → **强制改用已有目录**(LLM 输出归并理由,用户拍板通过后直接 mv,**不**新建飘名子目录)。lint 是事后被动检测,ingest 是事前主动拦截,两道闸门互补。

---

## 7. 不变量(agent 必守)

- `glossary.md` **绝不覆盖**,LLM 只能 append
- `inbox/<file>` **绝不静默迁出**,必须拍板门
- `raw/<subdir>/` **绝不静默创建未存在的目录**
- raw 路径文件 **不通过 ingest 移动**(超语义),走 `git mv` 手工
- frontmatter `updated` 字段 **重新生成不算更新**,必须有内容变更
- `log.md` **append-only**,不删旧记录
- SCHEMA.md 本文件 **本地优先**,plugin 升级不覆盖

---

## 8. plugin 元信息

- plugin:`aeps-llm-wiki-plugin`
- version:`plugin-version`(由 `init` 写入 `raw/.aeps-plugin-version`)
- OKF spec: v0.2(`src/schema/frontmatter.schema.yaml` 对齐)
- tag 字典:`raw/tag-template.md`(6 轴)
- entity/concept 子类字典:`raw/concept-entities-readme.md`
- raw 分类字典:`raw/README.md`

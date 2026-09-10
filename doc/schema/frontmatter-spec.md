# aeps-llm-wiki-plugin —— Frontmatter 字段规范

> **职责**:本文件是 plugin 的 frontmatter **人读字段规范** 唯一权威定义,`frontmatter.schema.json`(机器读)必须向本文件对齐。
> **权威顺序**:OKF v0.2 > **本文件**(`frontmatter-spec.md`,人读规范,唯一权威) > `frontmatter.schema.json`(机器读,跟随本文件) > `doc/template/README.md` > `doc/schema/schema.md`(工作流入口)。
> **对齐原则**:人只能读懂人读规范,因此 `frontmatter.schema.json` 在字段定义、约束、描述上必须**以本文件为准**;若两者不一致,**以本文件为最终裁决**,`frontmatter.schema.json` 必须修改对齐。
> **规范来源**:基于 OKF v0.2(`doc/input/google-OKF/OKF-SPEC.md`)。

---

## 0. Change History

| 日期 | 变更人 | 变更内容 |
|---|---|---|
| 2026-09-05 | zhigangliu-bot | 开头权威顺序声明重写:**人读规范 (`frontmatter-spec.md`) 提升为唯一权威**;`frontmatter.schema.json` (机器读) 必须向本文件对齐,字段定义/约束/描述不一致时以本文件为准。同步修改 `doc/schema/schema.md` 开头权威顺序声明,保持两处一致。 |
| 2026-09-05 | zhigangliu-bot | §4.2 `tags:` 数量约束由"最少 3 条"调整为"最少 5 条",与 `frontmatter.schema.json` 的 `minItems: 5` 及 `tag-spec.md` §8 Lint 阈值对齐(原 3 条会导致 Lint < 5 的 WARN 区间与 Schema 合规区间错位) |
| 2026-09-05 | zhigangliu-bot | 全文档清除 `<>` 占位符(详见 §0.1 编写铁律);frontmatter 字段值改双引号字符串、`tags` 改多行 YAML list、`generated` 改多行嵌套;正文占位符改 `【...】` 形式,模板变量改 `{name}` 大括号形式 |
| 2026-09-08 | zhigangliu-bot | 批次 4 (P3-1):§4.3.1 + §7 + §10.1 + §10.2 共 4 处 `producer/aeps-llm-wiki-plugin/<旧版本号>` 示例统一升级为 0.5.6;无字段语义变化 |
| 2026-09-09 | zhigangliu-bot | 批次 8 (v0.6.3):§3.3 新增 plugin 扩展 reserved filenames 子节(overview.md / glossary.md);明确 4 个 reserved filenames(index/log/overview/glossary)均不携带 frontmatter;引用 `scripts/ingest/lint-stub.js` R7.3 检测 + `scripts/aggregate-index.js` v0.6.3 起读模板不注 frontmatter 行为。修复 issue #5/#6。 |
| 2026-09-09 | zhigangliu-bot | 批次 9 (v0.6.5):§3.3 lint 联动段更新——旧 R7.1(tags<5 WARN)被 **R7.4(tags 数量 5-10 → ERROR)** 取代,新增 **R7.5(stale_after 须 ISO 8601 datetime → ERROR)** / **R7.6(sources[] 元素须对象 → ERROR)** 三条 ERROR 规则(修复 issue #12)。§4.4.1 `sources[]` 对象格式为既有权威,`frontmatter.schema.json` `stale_after` 描述已对齐 ISO datetime 语义。 |
| 2026-09-10 | zhigangliu-bot | v0.6.7:3 处 `generated.by` 示例的 producer 版本号字串同步升级为 0.6.7(修复 issue #18 伴随的版本基线刷新);无字段语义变化。 |
| 2026-09-10 | zhigangliu-bot | v0.6.7 (PR-A):§4.5.2 `stale_after` 明确**基准时间**为 `generated.at`(权威);`updated` 仅展示维护时间,不参与过期判断;TTL 默认值表格化(`concept.standard` +5y,其他 +1y);新增 `--stale-after-base <generated|updated>` 开关文档化(修复 issue #24)。 |

### 0.1 编写铁律(YAML / Obsidian Properties 兼容性)

**绝对禁止**:frontmatter 字段值 / 正文占位符 / 模板变量使用 `<` 与 `>` 作为包裹符号。

| 错误写法 | 后果 | 正确写法 |
|---|---|---|
| `title: <ISO 26262>` | YAML 解析成普通文本,Obsidian Tags 控件把 `<docform/...` 当标签名,样式崩溃 | `title: "ISO 26262"` |
| `tags: [<a, b, c>]` | 行内数组含尖括号,Obsidian Properties 报错显示为 `?` | 多行 YAML list,每行 `- a` / `- b` / `- c` |
| `generated: { by: <x>, at: <y> }` | 单行嵌套含尖括号,Obsidian Properties 误判为未知类型(显示 `?`) | 多行嵌套 `generated:` `  by: "x"` `  at: "y"` |
| `aliases: [<LLM Wiki>]` | YAML list 项含尖括号 | `aliases:` `  - "LLM Wiki"` |
| 正文 `<LLM 自动填充...>` | 渲染原样输出丑陋,占位意图丢失 | 正文 `【LLM 自动填充...】` 或 `**LLM 自动填充**:...` |
| 模板变量 `<file>` / `<subdir>` / `<topic>` | 在 markdown 行内代码或表格中混用易误读 | `{file}` / `{subdir}` / `{topic}` 大括号形式 |

**双链引用例外**:wiki 引用保持 `[[path|alias]]` 形式,不加 `<>` 包络。

**OKF 规范本身不改**:`doc/input/google-OKF/` 下的 Google 原版 OKF 规范保留尖括号写法(那是第三方参考文档,plugin 不改上游)。

**lint 联动(待实现)**:`--fix` 检测 frontmatter 字段值仍含 `<...>` 字面字符 → FAIL。

---

## 1. 适用范围与术语

### 1.1 适用范围

本规范定义 aeps-llm-wiki-plugin 输出的每一个 **concept 文档**(OKF §3 中"目录树中的非保留 markdown 文件")必须/可以携带的 frontmatter 字段。

### 1.2 核心术语

| 术语 | 定义 |
|------|------|
| **Concept(概念)** | bundle 内的一个知识单元,一个 markdown 文件对应一个概念 |
| **Concept ID** | 文件相对 bundle 根的路径,去掉 `.md` 后缀 |
| **Frontmatter** | 文件首部由 `---` 包围的 YAML 块 |
| **Body(正文)** | frontmatter 之后的所有 markdown 内容 |
| **Source(来源)** | 概念所引用的外部或内部材料,通过 `sources` frontmatter 字段记录 |
| **Provenance(出处)** | 一个概念所引用的全部 source 的集合 |
| **Credibility signal(可信度信号)** | 客观的、per-source 的事实(`author` / `usage_count` / `last_modified`),供消费方推断信任(OKF 不存评分,只存信号) |
| **Actor(行为者)** | 标识"谁做了这个动作"的字符串,约定见 §7 |
| **Trust tier(信任等级)** | 由 `verified` 字段推导的三档:unverified / machine-confirmed / human-reviewed,见 §4.3.3 |
| **Attested Computation(可证计算)** | 一种特殊 concept 类型,同时承载"是什么值"和"该如何计算",见 §4.6 |

---

## 2. 核心字段层级速查表

> 这是字段总览,详细语义与示例见 §3-§10。"MUST"/"REQUIRED"/"OPTIONAL"/"RECOMMENDED" 等关键词遵循 RFC 2119 习惯用法。

| 层级 | 字段 | 必需性 | 简要说明 |
|------|------|--------|----------|
| **顶层 (Root)** | `type` | **MUST** | 概念类型识别符;唯一全局必填字段(§4.1) |
| **顶层 (Root)** | `title` | RECOMMENDED | 可读显示名;缺省时可由文件名推导 |
| **顶层 (Root)** | `description` | RECOMMENDED | 单句摘要;供 Agent 路由与索引生成 |
| **顶层 (Root)** | `resource` | OPTIONAL(plugin:单源必填,多源不填) | 底层资产的规范 URI;plugin 收紧:单源模式必填,多源融合模式**不填**(详见 §4.2.3 + §13) |
| **顶层 (Root)** | `tags` | REQUIRED(plugin 强化为 6 轴字典约束) | YAML 字符串列表;每条必须以 `domain/` / `layer/` / `phase/` / `docform/` / `maturity/` / `tec/` 之一为前缀(详见 §4.2.4 + `doc/template/tag-spec.md`) |
| **Trust (§4.3)** | `generated` | OPTIONAL | 内容生产记录 `{ by, at }`,详见 §4.3.1 |
| ↳ `generated` | `by` | **REQUIRED** (在 `generated` 内) | actor 字符串(§7) |
| ↳ `generated` | `at` | OPTIONAL | ISO 8601 UTC 时间戳 |
| **Trust (§4.3)** | `verified` | OPTIONAL | 验证事件列表,详见 §4.3.2 |
| **Provenance (§4.4)** | `sources` | OPTIONAL | 来源对象数组;多源融合时 RECOMMENDED |
| ↳ `sources[]` | `resource` | **REQUIRED** (在 sources 内) | URL / 路径 / scope 描述符 |
| ↳ `sources[]` | `id` | OPTIONAL | 稳定键,供脚注归属使用 |
| ↳ `sources[]` | `title` | OPTIONAL | 显示名;**真实范例几乎不用**,顶层 `title` 已足够 |
| ↳ `sources[]` | `author` | OPTIONAL | 数据源责任方,actor 字符串 |
| ↳ `sources[]` | `usage_count` | OPTIONAL | 活跃度信号(整数) |
| ↳ `sources[]` | `last_modified` | OPTIONAL | 来源本身最后修改时间,ISO 8601 |
| **Provenance (§4.4)** | `usage_window` | OPTIONAL | `sources[].usage_count` 的时间窗口,**顶层兄弟字段**(单数),详见 §4.4.2 |
| **Lifecycle (§4.5)** | `status` | OPTIONAL | `draft` / `stable` / `deprecated`;缺省 `stable` |
| **Lifecycle (§4.5)** | `stale_after` | OPTIONAL | ISO 8601 绝对时刻;`now >= stale_after` 视为陈旧 |
| **Attested Computation (§4.6)** | `runtime` | **REQUIRED** (仅该类型) | 解释 `parameters` 含义,见 §4.6.2 |
| **Attested Computation (§4.6)** | `parameters` | OPTIONAL | `[{ name, type, required }]` 列表 |
| **Attested Computation (§4.6)** | `computation` | OPTIONAL | 计算文件路径;缺省用正文 `# Computation` 围栏 |
| **Attested Computation (§4.6)** | `executor` | OPTIONAL | `{ resource, receipt }` |
| **Attested Computation (§4.6)** | `attester` | OPTIONAL | `{ resource }` |
| **plugin 扩展 (§11.7)** | `format` | OPTIONAL(source 必填) | 原文件扩展名(小写):pdf / pptx / docx / xlsx / png ... 见 §13 |
| **plugin 扩展 (§11.7)** | `converter` | OPTIONAL(source 必填) | 枚举 `anydoc` \| `paddleocr` \| `claude-native` \| **null**(YAML 空值,纯文本路径);`null` 是 JSON Schema 空值类型,非字符串 `'null'`,见 §13 |
| **plugin 扩展 (§11.7)** | `native_text` | OPTIONAL(source 必填) | 是否原生纯文本;决定是否生成 `.converted.md` 副本,见 §13 |
| **plugin 扩展 (§11.7)** | `sources_used` | OPTIONAL(analysis 必填) | 本次 query 参考的 wiki 页相对路径列表;lint C15.2 校每条存在,见 §13 |
| **plugin 扩展 (§11.7)** | `sources_count` | REQUIRED(analysis / synthesis / comparison 必填,其他 type 推荐) | 整数;当前 wiki 页引用的 wiki 页/资料数(入度);synthesis `< 3` WARN,详见 §12.1 |
| **plugin 扩展 (§11.7)** | `updated` | **REQUIRED**(plugin 强化) | ISO 8601;LLM 最后一次综合推演该页的时间(读事件);lint 必填,FAIL on 缺失,见 §12.2 + §13 |
| **plugin 扩展 (§11.7)** | `summary` | REQUIRED(analysis / synthesis / comparison 必填,其他 type 推荐) | 字符串(≤ 280 字);长摘要卡片;详见 §13 + §12.3 |
| **plugin 扩展 (§11.7)** | `aliases` | OPTIONAL | `string[]`;Obsidian 原生别名机制,使 `[[alias]]` 形式的 wikilink 可解析到本页,见 §5.1 + §12.4 |
| **plugin 扩展 (§11.7)** | `source_file` | OPTIONAL(source 必填) | Obsidian wikilink 文本,指向 raw/ 原文件,见 §12.5 |
| **plugin 扩展 (§11.7)** | `converted_path` | OPTIONAL(source 必填) | `.converted.md` 副本相对路径;纯文本为 `null`(YAML 空值,非字符串 `'null'`),见 §12.5 |
| **plugin 扩展 (§11.7)** | `answer_to` | OPTIONAL(analysis 必填) | 原 query 问句;G11 落档分析页必备,见 §13 |
| **Producer 扩展** | 任意自定义键 | OPTIONAL | 消费者 MUST NOT reject,见 §4.7 |

---

## 3. Bundle 结构与保留文件名

### 3.1 目录结构

bundle 是一个 markdown 文件树,目录组织由生产者按知识内容自行决定:

```
{bundle_root}/
  index.md                          # 可选,bundle 根目录索引(§6.1)
  log.md                            # 可选,变更日志(§6.2)
  {concept}.md                      # bundle 根概念
  {subdirectory}/
    index.md                        # 可选,子目录索引
    {concept}.md
    {subdirectory}/
      ...
```

### 3.2 保留文件名

以下文件名在 bundle 任意层级都有定义,**不得** 用作概念文档:

| 文件名 | 用途 |
|--------|------|
| `index.md` | 目录索引,见 §6.1 |
| `log.md` | 变更日志,见 §6.2 |

### 3.3 plugin 扩展保留文件名(v0.6.3 起)

plugin 在 OKF §3.2 基础上扩展 2 个保留文件名,**同样不得携带 frontmatter**:

| 文件名 | 用途 | 模板 |
|--------|------|------|
| `overview.md` | 项目大图(LLM 在 ingest 大图变化时维护) | `doc/template/page-overview.md` |
| `glossary.md` | 项目术语表(`aggregate-index.js` 增量维护) | `doc/template/page-glossary.md` |

plugin 的 4 个 reserved filenames 合计:

- `index.md`(OKF §3.2)
- `log.md`(OKF §3.2)
- `overview.md`(plugin 扩展)
- `glossary.md`(plugin 扩展)

**共同约束**(OKF §6.1 + 模板注释):4 个文件均**不携带 frontmatter**。结构化正文(标题 / 分组 / 链接列表)是其唯一组织方式。

**lint 联动**(v0.6.3 起,`scripts/ingest/lint-stub.js`):

- reserved filename 跳过 R7.4(tags 数量 5-10)/ R7.2(updated 非 ISO 8601)/ R7.5(stale_after 非 ISO datetime)/ R7.6(sources[] 元素非对象)(这些规则的前提是文件有 frontmatter,reserved file 没有所以无意义)
- 新增 **R7.3(WARN)**:reserved filename 误含 `^--- ... ---` frontmatter 块 → 报告到 `warnings_by_file`,**不改文件**
- **lint 规则 ERROR 化**(v0.6.5 起,修复 issue #12):**R7.4** tags 数量 <5 或 >10 → ERROR(exit 2,取代旧 R7.1 的 WARN);**R7.5** `stale_after` 非 ISO 8601 datetime(纯 date 如 `2027-09-09` 不合规,须为 `2027-09-09T00:00:00Z` 形态)→ ERROR,报错附正确格式示例;**R7.6** `sources[]` 元素非 `{resource, ...}` 对象(字符串元素不合规)→ ERROR,报错附对象写法示例

**plugin 脚本行为**(v0.6.3 起):

- `scripts/aggregate-index.js` 读 `doc/template/page-{index,glossary}.md` 骨架生成 index.md / glossary.md,**不再注入 frontmatter**(修复 issue #5)
- `scripts/ingest/append-log.js` 维护 log.md,无 frontmatter
- overview.md 自 v0.6.2 起由 LLM 在 ingest 大图变化时维护,无 frontmatter

### 3.3 bundle 分布形态

bundle 可按以下任意方式分发:

- git 仓库(推荐,提供历史/署名/diff)
- tarball 或 zip 压缩包
- 嵌入更大仓库的子目录

---

## 4. Frontmatter 详细规范

### 4.1 必备字段:`type`

**`type` 是唯一全局必填字段。**

- 短字符串,标识概念类型。
- 消费方据此做路由、过滤、呈现。
- **取值不集中注册**:生产者自取,宜取描述性、自解释的命名。常见取值:`BigQuery Table` / `BigQuery Dataset` / `API Endpoint` / `Metric` / `Playbook` / `Reference` / `Attested Computation` / `Checkpoint` 等。
- **消费方 MUST NOT reject 未知 type**(§8):遇到未知 type 应作为通用概念处理。

> 仅携带 `type` 一个字段的 frontmatter 仍完全合规(§8)。

#### 4.1.1 plugin 收敛的 18 项硬枚举

OKF 标准下 `type` 取值**开放**(§4.1),消费方 MUST NOT reject 未知 type。但 **plugin 为保证与 knowledge/ 叶子存储目录 1:1 绑死**(README §2.4 + page-schema §2),**收紧为 18 项硬枚举**(见 `frontmatter.schema.json` `type.enum`)。plugin 取值必须落在下表,否则 lint FAIL。

| # | 取值 | 目录 | 用途 |
|---|------|------|------|
| 1 | `source` | `knowledge/sources/` | 原资料源页(由 `/aeps-llm-wiki-ingest` 生成) |
| 2 | `analysis` | `knowledge/analyses/` | LLM 综合推演一次性快照(由 `/aeps-llm-wiki-query` 落档) |
| 3 | `comparison` | `knowledge/comparisons/` | 同类实体常驻对照页 |
| 4 | `synthesis` | `knowledge/syntheses/` | 跨概念常驻综合页 |
| 5 | `entity.person` | `knowledge/entities/person/` | 具象存在 — 人物 |
| 6 | `entity.organization` | `knowledge/entities/organization/` | 具象存在 — 组织 |
| 7 | `entity.project` | `knowledge/entities/project/` | 具象存在 — 项目 |
| 8 | `entity.product` | `knowledge/entities/product/` | 具象存在 — 产品 |
| 9 | `entity.event` | `knowledge/entities/event/` | 具象存在 — 事件 |
| 10 | `entity.place` | `knowledge/entities/place/` | 具象存在 — 地点 |
| 11 | `entity.other` | `knowledge/entities/other/` | 具象存在 — 其他 |
| 12 | `concept.theory` | `knowledge/concepts/theory/` | 抽象知识 — 理论 |
| 13 | `concept.method` | `knowledge/concepts/method/` | 抽象知识 — 方法 |
| 14 | `concept.field` | `knowledge/concepts/field/` | 抽象知识 — 领域 |
| 15 | `concept.phenomenon` | `knowledge/concepts/phenomenon/` | 抽象知识 — 现象 |
| 16 | `concept.standard` | `knowledge/concepts/standard/` | 抽象知识 — 标准 |
| 17 | `concept.term` | `knowledge/concepts/term/` | 抽象知识 — 术语 |
| 18 | `concept.other` | `knowledge/concepts/other/` | 抽象知识 — 其他 |

**与 OKF 标准的兼容边界**:

- ✅ **OKF 标准范例的 `type: Reference` / `Metric` / `Agent Memory` / `Attested Computation` 等取值在 plugin 范围外**——lint FAIL;plugin 不为开放概念提供容器(知识库的目录结构必须事先确定)
- ✅ **plugin 写出的 page 必须落在 enum 内**——frontmatter.schema.json `not.anyOf` 不直接禁 enum 外取值(由 enum 字段本身强制),但 lint C15.x 校 `type` ∈ enum
- ✅ **plugin 不实现 `Attested Computation` 语义**(§11.5)——不在 enum 内,也无法被选用
- ❌ **plugin 不接受 OKF 标准的 `type: Reference` 等开放类型**——这是 plugin 收敛 OKF 开放性的关键决策

**未来扩展**:新增 `type` 取值 = 三件事同时改(1)schema.json enum 加项 (2)新增 knowledge/ 子目录 (3)新增 frontmatter 必填字段组 `allOf`。

### 4.2 推荐字段

#### 4.2.1 `title`

- 可读显示名。
- 缺省时消费方可以由文件名推导。

#### 4.2.2 `description`

- 单句摘要,概述概念要点。
- 用于 `index.md` 自动生成、搜索摘要、预览。

#### 4.2.3 `resource`

- 唯一标识底层资产的 URI。
- 描述抽象概念时可省略。
- 接受三种形式,详见 §5.2:
  - 绝对 URL(如 `https://...`)
  - bundle 相对路径,以 `/` 起头(如 `/tables/customers.md`)
  - 相对路径(如 `../computations/revenue.md`)
- 也允许 **scope 描述符**(如 `all queries in BigQuery project X`),此时不是路径而是范围说明。

**plugin 落地收紧**(plugin 不发明字段,与 OKF §4.2.3 RECOMMENDED 对齐后进一步收口):

| 模式 | 顶层 `resource` | `sources[]` | 典型场景 |
|------|----------------|------------|----------|
| **单源模式** | ✅ **必填**(指底层资产 URI) | 通常不写 | `type: source` 源页、单一资产描述页 |
| **多源融合模式** | ❌ **不填**(改用 `sources[]` 表达多源融合) | ✅ 必填(≥ 1 条) | `type: analysis` / `synthesis` / `comparison` 等综合页 |

**为什么这样收**:plugin 与 OKF §5.1 一致——多源融合时,lineage 走 `sources[]` 数组(每条带独立 `resource`);顶层 `resource` 此时语义重叠且会误导(让消费方以为只引了一个)。单源时顶层 `resource` 直接给出底层资产 URI,比强制走数组更简洁。

**lint 联动**(待实现):
- `type: source` 页 → 顶层 `resource` 必填,FAIL on 缺失
- 其他 type(`analysis` / `synthesis` / `comparison` / `entity.*` / `concept.*`)→ 顶层 `resource` 应**留空**;若填了且 `sources[]` 也有,lint WARN("顶层 resource 与 sources[] 语义重叠,以 sources[] 为准")
- 范例见 §10.1(单源)/ §10.2(多源融合)

#### 4.2.4 `tags`

- YAML 字符串列表,跨切面分类。
- **plugin 强化为 6 轴字典约束**(由 RECOMMENDED 升级为 REQUIRED 字典行为):每条 tag 必须以 `domain/` / `layer/` / `phase/` / `docform/` / `maturity/` / `tec/` 之一为前缀(正则 `^(domain|layer|phase|docform|maturity|tec)/[a-z0-9][a-z0-9-]*$`),全小写 + `-` 连字符,2-3 词。
- **裸 tag**(无 `axis/` 前缀,如 `tags: [AI, 芯片]`)FAIL;**状态词 / 版本号 / OKF type 值进 tags** 一律 FAIL(走对应 frontmatter 字段,详见 tag-spec §1.4 隔离机制)。
- **数量约束**:最少 5 条(覆盖度下限 WARN),最多 10 条(切片区分度上限 WARN);**必填轴**:`docform/` + `domain/`(tag-spec §1.2)。
- **范式校验**(由 tag-spec §8 范式 1-4 提供,SKILL.md 必须先读 tag-spec):主题-技术共存 / 层级-技术对齐 / 形态-成熟度约束 / 跨域粒度控制。
- plugin 内部 tag 字典见 `doc/template/tag-spec.md`(v1.0 冻结,6 轴 / 14 + 9 + 9 + 14 + 5 + ~40 词条)。

### 4.3 Trust 家族:`generated` / `verified`

`generated` 记录"当前内容是怎么产出的",`verified` 记录"谁/什么校验过它"。两者分开,因为**作者 ≠ 校验者**。

#### 4.3.1 `generated`

```yaml
generated:
  by: "producer/aeps-llm-wiki-plugin/0.6.7"
  at: "2026-09-05T10:30:00Z"
```

- **`generated.by` REQUIRED**(在 `generated` 内):actor 字符串,见 §7。
- `generated.at` OPTIONAL:ISO 8601 时间戳,标记内容最后有意义的变更时刻。

#### 4.3.2 `verified`

```yaml
verified:
  - { by: "human:ahormati", at: "2026-08-12T11:00:00Z" }
  - { by: "process:lint-nightly", at: "2026-08-13T02:00:00Z" }
```

- 验证事件列表,每条含 `by`(actor)和 `at`(ISO 8601)。
- 多条记录独立校验,例如人工签收 + 每晚 lint。
- **"最近一次校验时间"取 `at` 的最大值**。
- **Bare mapping 兜底**:单个验证者可写成无列表短横的 `{ by, at }` 映射;消费方 MUST 把 bare mapping 当作单元素列表处理:

  ```yaml
  verified: { by: "human:ahormati", at: "2026-08-12T11:00:00Z" }
  ```

#### 4.3.3 Trust Tier 推导

消费方由 `verified` 推导信任等级,自低至高:

| `verified` 内容 | Trust Tier |
|-----------------|------------|
| 无 `verified` 键 | **unverified** |
| 仅含非 `human:` actor | **machine-confirmed** |
| 至少含一个 `human:{id}` | **human-reviewed** |

- Trust tier 是**建议信号**,不是访问控制。
- **消费方 MUST NOT reject** 缺失 trust frontmatter 的概念(§8)。

### 4.4 Provenance 家族:`sources` / `usage_window`

#### 4.4.1 `sources[]`

```yaml
sources:
  - id: ga4-schema
    resource: https://developers.google.com/analytics/bigquery/export-schema
    title: GA4 BigQuery Export schema
    author: "team:ga4-docs"
    usage_count: 5000
    last_modified: "2026-05-30T00:00:00Z"
```

每个 `sources` 条目:

| 子字段 | 必需性 | 说明 |
|--------|--------|------|
| `resource` | **REQUIRED** | URL / 路径 / scope 描述符,见 §4.2.3 |
| `id` | OPTIONAL | 稳定键,用于 `[^id]` 脚注归属(见 §4.4.3);正文引用时建议携带 |
| `title` | OPTIONAL | 来源显示名;**真实范例几乎不写**,顶层 `title` 已足够 |
| `author` | OPTIONAL | 来源责任方,actor 字符串(§7) |
| `usage_count` | OPTIONAL | 整数活跃度信号(详见 §4.4.2) |
| `last_modified` | OPTIONAL | 来源本身最后修改时间,ISO 8601 |

**Credibility signals(可信度信号)** 三件套:

- **不存评分**:OKF 不存可信度分数(主观、不可移植、易过期),只存客观信号,由消费方按 §4.3.3 同样的方式从信号推导信任。
- `usage_count` 是粗粒度信号,适合活跃度与趋势对比,**不**适合跨类型精排。
- 当 `resource` 指向另一个 OKF concept 时,链路信息已经在 bundle 图里(§5),消费方可递归进入该来源的 `sources` 让可信度自然传播;外部叶子来源只携带自身信号。

#### 4.4.2 `usage_window`(顶层兄弟字段,非 `sources[]` 内部)

> **重要位置修正**:`usage_window` 是 `sources` 的 **顶层兄弟字段**,**单数形式**,**不属于** `sources[]` 内部。OKF 设计上由它为整组 `usage_count` 框定时间窗;单条 `sources[]` 可自带 `usage_window` 覆盖默认值。

```yaml
usage_window:
  from: "2026-06-01T00:00:00Z"
  to: "2026-06-30T00:00:00Z"
```

#### 4.4.3 Per-claim attribution(脚注归属)

为单句主张归属来源,使用 markdown 脚注,标签为 `sources[].id`:

```markdown
The `events_` table is sharded daily as `events_YYYYMMDD`.[^ga4-schema]

[^ga4-schema]: GA4 BigQuery Export schema
```

- 脚注标签是 join key,消费方通过它找到 `sources[]` 对应条目,**不**解析脚注正文。
- **用 `id` 而非位置索引**(`sources[0]`):agents 重写文档时列表会乱序,位置索引会静默错配;稳定 `id` 抗重排。

### 4.5 Lifecycle 家族:`status` / `stale_after`

#### 4.5.1 `status`

```yaml
status: stable        # draft | stable | deprecated
```

| 取值 | 含义 |
|------|------|
| `draft` | 未审阅,可能不完整 |
| `stable` | 默认;可用于消费 |
| `deprecated` | 仅为链接与历史保留,不再现行 |

**缺省 ⇒ `stable`**。

#### 4.5.2 `stale_after`

```yaml
stale_after: "2026-09-23T00:00:00Z"
```

- 可选,绝对时刻。
- 判断规则:`now >= stale_after` 即视为陈旧(**闭区间**)。
- 采用绝对时刻而非相对 TTL,保证陈旧性是纯比较,不依赖读取时机。

**基准时间**(`v0.6.7` 起,PR-A 引入):**`generated.at`** 为唯一权威基准。

`updated` 字段(§12.2)仅展示「最近一次维护时间」，**不**参与过期判断。
陈旧度一律用 `stale_after < now` 判断；`updated > N 天` 等相对阈值已废弃(v0.6.5 起)。

**TTL 默认值**(由 `gen-page.js` 自动推导):

| type | TTL |
|---|---|
| `concept.standard` | 5 年 |
| 其他所有 type | 1 年 |

**显式覆盖**:可通过 `gen-page.js --stale-after-base <generated|updated>` 切换基准。
默认 `generated`;LLM 显式传 `updated` 时按 `updated + TTL` 重算(用于 `--patch-frontmatter-only` 模式)。

### 4.6 Attested Computation 类型(OKF §10)

> **plugin 当前不使用此类型**(plugin 是 Claude Code plugin,不是 data pipeline plugin)。本节为完整性保留,供未来扩展或对接其他工具参考。

`type: Attested Computation` 的概念不仅承载"是什么值",还承载**该值的官方计算方式**,使消费方能确认 agent 跑的是被认可的算法。

#### 4.6.1 设计动机:计算是一个独立 concept

三方面理由:

- **`runtime` 决定 `parameters` 的语义**:SQL bind / dbt var / Python arg 含义不同,绑定语义必须随 `runtime` 一起看。
- **一个计算,多个消费方**:同一计算可服务 metric、dashboard、report 多个概念,作为独立 concept 引用一次、复用多次。
- **信任状态是 per computation 的**:`verified` / `stale_after` / 单个 `attester` 描述一件事;revenue、profit、margin 各自独立校验,所以是三个概念,不是一条 frontmatter。

#### 4.6.2 契约字段

在 §4.3 / §4.4 / §4.5 的家族之外,Attested Computation 概念额外携带:

| 字段 | 必需性 | 说明 |
|------|--------|------|
| `runtime` | **REQUIRED** | 决定如何跑、attester 如何看、`parameters` 如何绑定;如 `bigquery` / `postgres` / `dbt` / `python` / `Looker` |
| `parameters` | OPTIONAL | `[{ name, type, required }]`,agent 仅可填值,不可改写或编辑计算本身 |
| `computation` | OPTIONAL | 路径(§5.2)指向计算文件;**缺省则使用正文 `# Computation` 围栏**(§4.6.3) |
| `executor` | OPTIONAL | `{ resource, receipt: [{field_names}] }`——如何跑、跑出什么 |
| `attester` | OPTIONAL | `{ resource }`——确定性核验代码路径 |

#### 4.6.3 计算的两种写法

- **内联(inline)**:正文 `# Computation` 标题下的单个围栏代码块。适合短小、可与契约一起审阅的计算。
- **文件(file)**:设置 `computation` 字段指向路径,**省略**正文围栏。适合长计算、生成式计算、或与非 OKF 工具共享的文件。

```yaml
runtime: bigquery
computation: references/computations/lib/revenue.sql
parameters:
  - { name: year, type: integer, required: true }
```

#### 4.6.4 核验 vs 校验

- `verified`(**§4.3.2**)确认"定义"仍匹配策略:doc 级别、慢、记入 bundle。
- Attestation 确认"单次运行"是否走官方路径:per-call、运行时、**不**存 bundle。
- 两者并存:陈旧定义仍可干净 attest,新近校验的定义每次运行仍需 attest。

### 4.7 Producer 扩展字段

- 生产者可在 frontmatter 加入任意自定义键。
- **消费方 MUST NOT reject** 未识别键。
- **消费方 SHOULD** 在 round-trip 时保留未识别键。

### 4.8 时间戳格式统一约束

**所有时间型字段(`generated.at` / `verified[].at` / `sources[].last_modified` / `usage_window.from` / `usage_window.to` / `stale_after`)必须使用 ISO 8601 datetime,并带显式 UTC 偏移**(如 `Z` 或 `+08:00`)。仅日期型(如 `sources[].last_modified` 简写)允许 `YYYY-MM-DD`,但推荐完整 datetime 以避免时区歧义。

---

## 5. 跨链接与路径

### 5.1 概念间链接

两种形式:

- **Bundle 相对**(推荐):以 `/` 起头,相对 bundle 根。在子目录间移动时稳定。

  ```markdown
  See the [customers table](/tables/customers.md) for the join key.
  ```

- **相对**:标准 markdown 相对路径。

  ```markdown
  See the [neighboring concept](./other.md).
  ```

**plugin 主推 `[[wikilink]]` 裸文件名**(PRD §10 Q9 决策,§11.4 落地差异):

```markdown
参考 [[andrej-karpathy]] 的课程...
```

裸文件名依赖 Obsidian 唯一名解析;若目标页已注册 `aliases`,wikilink 也可写别名。OKF reader 仍可识别标准 markdown 链接,作为兼容降级。

**链接是有向边**,具体关系(parent/child、references、joins-with、depends-on)由上下文语义传达,不由链接本身标识。

**消费方 MUST tolerate 死链**:目标不存在不算格式错误,可能代表"知识尚未写入"。

### 5.2 路径型字段的三种形式

`resource`、`sources[].resource`、`computation`、`executor.resource`、`attester.resource` 这些路径型字段都接受:

- 绝对 URL(如 `https://...`)
- bundle 相对路径,以 `/` 起头
- 相对路径(如 `../computations/revenue.md`)

例外:`sources[].resource` 可用 scope 描述符(§4.2.3),此时不是路径。

### 5.3 `references/` 约定

`references/` 子目录按惯例存放外部材料的镜像、运行说明或代码,在 bundle 内作为一等概念存在。来源、executor、attester 常指向此处(如 `references/attesters/revenue.py`)。这是命名约定,**不是**强求。

---

## 6. 索引与日志文件

### 6.1 Index 文件(`index.md`)

任意目录可放置 `index.md`,枚举本目录内容,支持**渐进披露**:让人或 agent 先看见"有什么",再决定打开哪个。

- **bundle 根 `index.md`**:可以携带 frontmatter,**仅** 允许 `okf_version` 一个键,声明目标版本(§9.2)。
- **子目录 `index.md`**:**不得**携带 frontmatter。
- 正文按章节分组,每节用标题 + 链接列表:

  ```markdown
  # Section / Group Heading

  * [Title 1](relative-url-1) - short description
  * [Title 2](relative-url-2) - short description
  ```

- 条目 SHOULD 包含被链接概念的 frontmatter `description`。
- 生产者可自动生成 `index.md`;消费方在缺失时可即时合成。

### 6.2 Log 文件(`log.md`)

任意层级可放置 `log.md`,记录该范围内变更历史。扁平按日期分组列表,**最新在前**:

```markdown
# Directory Update Log

## 2026-05-22
* **Update**: Added a BigQuery table reference for [Customer Metrics](/tables/customer-metrics.md).
* **Creation**: Established the [Dataplex Playbook](/playbooks/dataplex.md).

## 2026-05-15
* **Initialization**: Created foundational directory structure.
```

- 日期标题 MUST 使用 ISO 8601 `## YYYY-MM-DD`。
- 条目是散文,前导加粗词(`**Update**` / `**Creation**` / `**Deprecation**`)是**约定**而非要求。

**plugin 当前使用的条目前缀**(与 OKF §9 略有差异,详见 §11.7):

- OKF 标准:`Creation` / `Update` / `Deletion` / `Deprecation`
- plugin 扩展:`Creation` / `Init` / `Ingest` / `LintFix` / `LintProposal`

`Creation` 与 OKF 兼容;其余 4 个为 plugin 特有语义。

---

## 7. Actor 命名约定

记录身份(`generated.by` / `verified[].by` / `sources[].author`)的字段使用统一的 actor 字符串:

| 形式 | 适用 | 示例 |
|------|------|------|
| `{producer}/{version}` | agents / 工具 | `producer/aeps-llm-wiki-plugin/0.5.2`<br>`reference_agent/gemini-2.5-pro` |
| `human:{id}` | 人 | `human:ahormati` |
| `process:{id}` | 自动化进程 | `process:lint-nightly` |

- 消费方按 §4.3.3 推导 trust tier 时以 `human:` 前缀作为分界,**人工撰写或人工确认的内容必须** 使用 `human:` 前缀。
- team/部门形式的 actor(如 `team:iso-tc22`、`team:ga4-docs`)作为 `author` 责任方标识被 OKF 规范接受,但在 trust tier 推导中不属于 `human:` 前缀,只能算 machine-confirmed。

---

## 8. Conformance(§11)

一个 bundle **符合** OKF v0.2 当且仅当:

1. 树中每个非保留 `.md` 文件包含**可解析的 YAML frontmatter 块**。
2. 每个 frontmatter 块包含**非空 `type` 字段**。
3. 每个保留文件名(`index.md`、`log.md`)按 §6 的结构组织(若存在)。

当 trust / lifecycle / provenance / computation 家族出现时,生产者 SHOULD 遵循 §4.3-§4.6,消费方:

- MUST 把 bare `verified` mapping 当作单元素列表处理(§4.3.2)。
- MUST NOT 因缺失任何可选家族而拒绝该概念(§4.3.3)。
- SHOULD 仅按本规范推导 trust tier 与 staleness;对 attest 失败 SHOULD 表面化(Surface),不静默丢弃。

消费方 MUST NOT 因为以下任何一项拒绝 bundle:

- 缺失可选 frontmatter 字段
- 未知 `type` 取值
- 未知 frontmatter 键
- 死链
- 缺失 `index.md`

---

## 9. 版本与兼容

### 9.1 版本号约定

`{major}.{minor}`:

- **minor**:向后兼容的增量(新可选字段、新约定标题)。
- **major**:可能引入破坏性变更(重命名必填字段、变更保留文件名)。

### 9.2 bundle 版本声明

bundle 可通过 **bundle 根 `index.md` 的 frontmatter** 声明目标版本:

```yaml
okf_version: "0.2"
```

- 仅此处允许 frontmatter(见 §6.1)。
- 消费方若不理解声明的版本,SHOULD 尽力消费而非拒绝。

### 9.3 v0.1 → v0.2 兼容

v0.1 是 v0.2 的子集。v0.2 bundle 可被 v0.1 消费方尽力消费,未识别字段被忽略。

两处破坏性变更(从 v0.1 升级时需要适配):

- **`timestamp` → `generated.at`**:v0.1 的顶层 `timestamp` 在 v0.2 中变为 `generated: { by, at }` 的 `at`。消费方可在 `generated` 缺失时回退读取 legacy `timestamp`。
- **正文 `# Citations` 列表 → `sources`**:出处从正文移到 frontmatter。消费方 SHOULD 读 `sources`,MAY 解析 legacy 正文 `# Citations` 列表兜底。

---

## 10. 完整 YAML 范例

### 10.1 模式 A:单源模式(简洁)

```yaml
---
type: Reference
title: Customer Orders
description: One row per completed customer order across all channels.
resource: https://example.com/data/orders
tags: [sales, orders, revenue]
generated:
  by: "producer/aeps-llm-wiki-plugin/0.6.7"
  at: "2026-09-05T10:30:00Z"
verified:
  - by: "human:ahormati"
    at: "2026-09-05T11:00:00Z"
status: stable
stale_after: "2027-09-05T00:00:00Z"
---
```

### 10.2 模式 B:多源融合模式(完整 provenance)

```yaml
---
type: Metric
title: Income statement (fiscal year)
description: Headline income-statement figures for a fiscal year.
tags: [finance, income-statement]
status: stable
generated:
  by: "producer/aeps-llm-wiki-plugin/0.6.7"
  at: "2026-09-05T10:30:00Z"
verified:
  - by: "human:ahormati"
    at: "2026-09-05T11:00:00Z"
stale_after: "2026-12-31T00:00:00Z"
sources:
  - id: fpa-handbook
    resource: https://wiki.acme/finance/fpa-handbook
    title: FP&A reporting handbook
  - id: rev-policy
    resource: https://wiki.acme/finance/revenue-recognition
    title: Revenue recognition policy
    author: "team:finance-fpa"
    last_modified: "2026-04-02T00:00:00Z"
usage_window:
  from: "2026-09-01T00:00:00Z"
  to: "2026-09-30T00:00:00Z"
---
```

正文引用采用 per-claim attribution:

```markdown
The income statement reports revenue and gross profit for a fiscal year,
per the FP&A reporting handbook.[^fpa-handbook]

[^fpa-handbook]: FP&A reporting handbook
```

### 10.3 Agent Memory 范例

```yaml
---
type: Agent Memory
title: "用户编程风格偏好"
description: "用户偏好 Tab 缩进与函数式注释风格"
resource: "/user/preferences/coding_style.md"
tags: [preferences, python]

generated:
  by: "human:ahormati"
  at: "2026-08-12T10:30:00Z"

verified:
  - by: "human:ahormati"
    at: "2026-08-12T11:00:00Z"

sources:
  - resource: "/user/preferences/coding_style.md"
    id: "style-guide"
    title: "Engineering Style Guide"
    author: "human:ahormati"
    usage_count: 42
    last_modified: "2026-08-12"

usage_window:
  from: "2026-01-01"
  to: "2026-12-31"

status: stable
stale_after: "2027-01-01"
---
```

### 10.4 Attested Computation 范例(plugin 当前未使用,保留供参考)

```yaml
---
type: Attested Computation
title: Revenue for fiscal year
description: Recognized revenue for a fiscal year, per Finance's definition.
status: stable
runtime: bigquery
parameters:
  - { name: year, type: integer, required: true }
executor:
  resource: references/skills/run-on-bq.md
  receipt: [job_id, executed_sql, result]
attester:
  resource: references/attesters/sql-equality.py
generated:
  by: "reference_agent/gemini-2.5-pro"
  at: "2026-09-05T10:30:00Z"
verified:
  - by: "human:ahormati"
    at: "2026-09-05T11:00:00Z"
stale_after: "2026-12-31T00:00:00Z"
sources:
  - id: rev-policy
    resource: https://wiki.acme/finance/revenue-recognition
    title: Revenue recognition policy
---

# Computation

    SELECT SUM(amount) AS revenue
    FROM finance.recognized_revenue
    WHERE fiscal_year = @year

The computation binds only the declared `parameters`, per the recognition
policy.[^rev-policy]

[^rev-policy]: Revenue recognition policy
```

---

## 11. plugin 落地差异表(与 OKF 标准对比)

> 本节记录 plugin 实际行为与 OKF 标准的差异及原因,作为后续维护时的速查。差异项按 OKF 规则维度列出,plugin 已对齐项仅一行带过,需要扩展的项明确标注为"未来扩展"。

### 11.1 字段必填性差异

| OKF 规则 | plugin 落地 | 差异原因 |
|----------|-------------|----------|
| `type` 必填 | plugin 严格遵守(PRD §4.1-§4.6 全部 type 必填) | 无差异 |
| `type` 取值开放(OKF §4.1 "取值不集中注册") | **plugin 收敛为 18 项硬枚举**(§4.1.1) | plugin 与 knowledge/ 叶子目录 1:1 绑死,不支持 OKF 的 `Reference` / `Metric` / `Agent Memory` 等开放类型 |
| `title` / `description` / `tags` 推荐 | plugin 全部 page template 必填 | 比 OKF 更严格 |
| `generated` / `verified` / `status` / `stale_after` 推荐 | plugin 按需填写,不强制 | OKF 也只 RECOMMENDED |

### 11.2 Bundle 结构差异

| OKF 规则 | plugin 落地 | 差异原因 |
|----------|-------------|----------|
| Root `index.md` 必须 `okf_version: "0.2"` | plugin 当前不写 | plugin 是客户端工具,不强求 OKF 声明;**未来扩展点** |
| 子目录 `index.md` 不得含 frontmatter | plugin 符合 | 无差异 |
| `log.md` 日期标题 `## YYYY-MM-DD` | plugin 符合 | 无差异 |
| `log.md` 条目前缀 `Creation` / `Update` / `Deletion` / `Deprecation` | plugin 用 `Creation` / `Init` / `Ingest` / `LintFix` / `LintProposal` | plugin 扩展;`Creation` 兼容,其余 4 个为 plugin 特有语义 |

### 11.3 来源字段差异

| OKF 规则 | plugin 落地 | 差异原因 |
|----------|-------------|----------|
| `sources[].title` 可选 | plugin **不写** | 顶层 `title` 已足够;OKF 真实范例也几乎不用此子字段 |
| `sources[].author` 可选 | plugin 写 `producer/aeps-llm-wiki-plugin/{version}` | 与 `generated.by` 走相同 actor 约定 |
| `usage_count` / `usage_window` | plugin 不写 | plugin 不需要活跃度统计 |
| `sources[].id` 用于脚注归属 | plugin 用 `sources_used` 字段 + 正文 wikilink | plugin 走自有引用风格,详见 PRD §10 Q9 决策(裸文件名 + aliases) |

### 11.4 链接风格差异

| OKF 规则 | plugin 落地 | 差异原因 |
|----------|-------------|----------|
| Bundle 相对路径 `/xxx` 优先 | plugin 用相对路径 `./xxx.md` | OKF §6.1 允许但不强制 |
| 正文链接 | **plugin 主推 `[[wikilink]]` 裸文件名**,标准 markdown 链接作为兼容降级 | PRD §10 Q9 决策;Q6 决策 A 已废。OKF §6.1 原文 "MAY standard markdown link" 是允许而非禁止,wikilink 不与之冲突 |
| `links:` frontmatter 字段 | **plugin 不发明** | 对齐 OKF §5「Lineage is expressed through links, not a dedicated field」 |
| wikilink 别名机制 | **plugin 扩展 `aliases` 字段**(Obsidian 原生兼容,OKF reader 按未知字段忽略) | §12.4 |

### 11.5 Attested Computation 差异

plugin **不使用** `type: Attested Computation`(plugin 是 Claude Code plugin,不是 data pipeline plugin)。详见 §4.6 与 §10.4,保留供未来扩展。

### 11.6 Last Memory Continuity Protocol 差异

plugin **不强制使用** 此协议(规范键名 `system/last_memory`、类型 `Checkpoint`、agent 初始化调用 `memory_get_last` 等)。详见 OKF-SPEC §Last Memory Continuity Protocol。plugin 当前不实现,留作未来扩展。

### 11.7 plugin 扩展字段

以下字段为 plugin 特有,**OKF 消费方 MUST NOT reject**(§4.7):

`source_file` / `format` / `converter` / `native_text` / `converted_path` / `sources_used` / `answer_to` / `sources_count` / **`updated`(plugin 强化为 REQUIRED)** / **`summary`(analysis / synthesis / comparison 必填,其他 type 推荐)** / `aliases`

---

## 12. plugin 字段语义边界

本节专门澄清 plugin 扩展字段与 OKF 标准字段的语义边界,避免字段混淆。三对易混淆字段对照如下。

### 12.1 `sources_count`(plugin) vs `sources[].usage_count`(OKF)

| | `sources_count` | `sources[].usage_count` |
|---|---|---|
| **归属** | plugin 扩展,顶层字段 | OKF §5.1,`sources[]` 条目内 |
| **主语** | **当前 wiki 页** | **某条来源资料** |
| **含义** | 当前页引用的 wiki 页/资料数量(入度) | 该原始素材被消费/查询/执行的次数(原始活跃度) |
| **典型场景** | synthesis/comparison 评估综合成熟度(`< 3` WARN) | 评估某 raw source 的活跃度 |
| **写入方** | LLM ingest 时自动统计 | 来源系统的统计(如 dashboard 浏览数、job 执行数) |
| **plugin 现状** | ✅ 实际用(`sources_count: 5`) | ❌ 不写(plugin §11.3) |

**两者不互斥**:同一条来源既可出现在 `sources[]` 里、又参与统计当前页的 `sources_count`。但**统计口径完全不同**——`sources_count` 是"我引用了多少"(我指向外),`usage_count` 是"源头被读了多少次"(外指向源头)。

### 12.2 `updated`(plugin) vs `sources[].last_modified`(OKF) vs `generated.at`(OKF)

| | `generated.at` | `last_modified` | `updated` |
|---|---|---|---|
| **归属** | OKF §5.2,顶层 `generated` 内 | OKF §5.1,`sources[]` 条目内 | plugin,顶层 |
| **主语** | **当前 wiki 页** | **某条来源资料** | **当前 wiki 页** |
| **含义** | 内容最后被生成/重写的时刻(写事件) | 原始素材自己最后被修改的时刻 | LLM 最后一次综合推演该页的时刻(读事件) |
| **OKF 语义** | "作者改了它" | "源头本身改了" | (OKF 无此字段) |
| **典型写入** | ingest 重写、`--fix` 改文件 | safe-mv.py 检测到 raw 新版本 | query 阶段 LLM 命中后 |
| **plugin 现状** | ✅ | ✅(`source` 页内) | ✅(plugin 推荐) |

**实战语义**:`generated.at` 和 `updated` 都标"当前页",**两次可以是同一时刻,也可以不同**。区分要点:

- `--fix` 只补字段不改正文 → 仅更 `updated`,不动 `generated.at`
- LLM 大幅改写正文 → 同时更两个
- query 命中但未改写 → 仅更 `updated`

**plugin 旧版曾用 `updated > N 天` 作为陈旧度 fallback**,本规范要求**陈旧度判断统一用 `stale_after`(§4.5.2)**;`updated` 退回为纯时间戳元数据,不参与 lint 逻辑。

### 12.3 `summary`(plugin) vs `description`(OKF)

| | `description` | `summary` |
|---|---|---|
| **归属** | OKF §4.1,顶层 | plugin,顶层 |
| **性质** | 单句**静态**语义摘要 | 长摘要(≤ 280 字)**状态化**概览 |
| **作用** | 路由/索引/分类的"导航标签" | Obsidian 顶部 summary 卡片的内容来源 |
| **内容性质** | "这页**是**什么" | "这页**现在**讲到什么程度" |
| **更新频率** | 概念定义变化时才改 | 几乎每次 ingest/query 都要刷新 |
| **plugin 现状** | ✅ 必填 | ✅ **analysis / synthesis / comparison 必填**,其他 type 推荐;首行 `**问题**: {answer_to}`(analysis 专属) |

**核心区别是"静态/动态"**:`description` 是定义,`summary` 是当前快照。同一页面的 `description` 一年内可能不变,`summary` 在每次新 query 命中后都可能改。

**analysis 页 `summary` 首行约定**:`**问题**: {answer_to}`,余下 ≤ 280 字符——保证卡片首屏直接呈现 query 问句与本页结论。

### 12.4 `aliases`(plugin)

```yaml
---
type: entity.person
title: "Andrej Karpathy"
aliases:
  - "Andrej Karpathy"
  - "Karpathy"
---
```

| 属性 | 说明 |
|---|---|
| **归属** | plugin 扩展,顶层字段 |
| **类型** | `string[]`,每个元素为不含 `[[ ]]` 的纯字符串 |
| **作用** | 为页面注册别名,`[[alias]]` 形式的 wikilink 可解析到本页(PRD §10 Q9 + §11.4) |
| **与 `source_file` 区别** | `source_file` 指向原文件路径(wiki 引用 raw 素材);`aliases` 是 wiki 页自身的人读别名(双向链接解析) |
| **OKF 兼容** | OKF reader 按未知字段忽略(MUST NOT reject, MUST preserve on round-trip,§4.7) |
| **plugin 现状** | ✅ 推荐,entity/concept 页与人名页强推荐 |

**别名约定**:
- 必须为字符串,不含 `[[ ]]` 包络
- 推荐加进 frontmatter 而非正文(避免解析歧义)
- 同一别名被多页声明时 lint 报 WARN(解析二义性)

**lint 联动**(待实现):`--fix` 检测正文 `[[alias]]` 找不到唯一目标页时,若别名唯一命中某页的 `aliases`,自动注入该页;多命中要求人工确认。

### 12.5 `source_file`(plugin) vs `converted_path`(plugin)

```yaml
---
type: source
title: "ISO 26262:2018 功能安全标准"
source_file: "[[06-功能安全/iso26262.pdf|ISO 26262:2018 原文]]"
converted_path: ./raw/06_功能安全/iso26262.pdf.converted.md
---
```

| | `source_file` | `converted_path` |
|---|---|---|
| **归属** | plugin 扩展,顶层字段 | plugin 扩展,顶层字段 |
| **类型** | `string`(Obsidian wikilink 文本) | `string\|null`(路径字符串) |
| **语法** | `[[{subdir}/{basename}.{ext}]]` 或 `[[...\|{显示文本}]]`(裸文件名 + 可选显示文本) | `./raw/{subdir}/{basename}.{ext}.converted.md` 或 `null`(纯文本) |
| **主语** | 原文件自身(pdf / docx / png / ...) | `.converted.md` 副本(可读 md 文本) |
| **作用** | **Obsidian 渲染为可点击蓝色下划线链接**,点击直接打开原文件 | 给程序消费(ingest/lint)解析真实路径,定位 md 副本 |
| **使用方** | 人(在 Obsidian 里点跳转) | 程序(脚本读 `.converted.md`) |
| **必填范围** | `type: source` 必填 | `type: source` 必填(纯文本为 `null`) |
| **OKF 兼容** | OKF reader 按未知字段忽略(MUST NOT reject) | OKF reader 按未知字段忽略 |
| **跨 reader** | GitHub/VSCode 预览降级为原始 `[[...]]` 文本(灰色不可点) | GitHub/VSCode 预览降级为路径字符串(可点但需相对路径有效) |

**示例** —— Obsidian 内显示 + 点击效果:

```yaml
source_file: "[[01-晶心/Andeis Overview and RISC-V Solutions 260130.pdf]]"
```

Obsidian 渲染为蓝色下划线链接 `Andeis Overview and RISC-V Solutions 260130.pdf`,点击用系统默认 pdf 阅读器打开原文件。

**为什么两者并存**:plugin 把"给 Obsidian 人看的跳转"和"给程序消费的解析路径"分到两个字段,各司其职。**`source_file` 不承担程序解析责任** —— 它是 wikilink 文本(含 `[[ ]]` 包络),程序要路径时读 `converted_path`;**`converted_path` 不承担跳转责任** —— 它是路径字符串,Obsidian 渲染为灰色不可点的纯文本。

**与 `aliases` 的区别**:`source_file` 指向 raw 原始文件(被引用方是文件);`aliases` 是 wiki 页自身的人读别名(被引用方是 wiki 页本身)。

**lint 联动**(待实现):
- `--fix` 校验 `source_file` 的 wikilink 目标文件必须存在于项目根下的 `raw/{subdir}/`(防止空链)
- 多原始文件场景:`source_file` 保持单值,如需多原始文件由 sources[] 数组表达(OKF §5.1)

### 12.6 YAML 空值 vs 字符串 `'null'` 语义约定(plugin)

plugin 的 `converter` / `converted_path`(以及未来可能扩展的同构字段)支持"无值"语义,但**绝不允许用字符串 `'null'` 占位**。两者的差异必须严格区分:

| 写法 | YAML 解析 | JSON Schema 校验 | plugin 行为 |
|---|---|---|---|
| `converter: null`(无引号) | `null`(空值) | ✅ 命中 enum `null` | 路径 1 纯文本,程序识别为"未走转换" |
| `converter: 'null'`(带单引号) | 字符串 `"null"` | ❌ 不在 enum 内 | lint FAIL(YAML 误用,违反类型契约) |
| `converter: ""`(空字符串) | `""` | ❌ 不在 enum 内 | lint FAIL |
| 字段直接缺失 | 字段不存在 | ⚠️ source 必填,FAIL | 同 FAIL |

**为什么禁止字符串 `'null'`**:
- `page-source.md` 模板路径 1 行 `converter: null` 是 YAML 空值,不是字符串
- `frontmatter.schema.json` `enum: ["anydoc", "paddleocr", "claude-native", null]` 第 4 项是 JSON null 字面量
- 程序读 YAML 时,`null` 是 `None`,字符串 `'null'` 是 `"null"`,后续 if/else 分支逻辑完全不同
- 误填字符串 `'null'` 会让 SKILL.md 误判"走 anydoc 转换过",触发 `converted_path` 一致性 lint FAIL

**lint 规则**(待实现):
- converter / converted_path 若值类型是 string 且内容等于 `"null"` / `"None"` / `"~"`,FAIL on 类型误用
- 推荐方案:让 SKILL.md 用 `yaml.safe_dump({"converter": None})` 生成(天然产生空值),避免人类手写

---

## 13. 参考资料

- 原始规范:[`OKF-SPEC.md`](../input/google-OKF/OKF-SPEC.md)(同目录,OKF v0.2 官方原始 spec)
- 发布说明:[`OKF-README.md`](../input/google-OKF/OKF-README.md)(同目录)
- 在线源 URL:[https://okf.md/spec/](https://okf.md/spec/)

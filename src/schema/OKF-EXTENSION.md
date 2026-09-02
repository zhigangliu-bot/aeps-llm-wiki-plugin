# OKF-EXTENSION.md — plugin 对 OKF v0.2 的扩展声明

> **角色**:声明本 plugin 的产出对 [OKF v0.2 spec](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md) 的兼容性 + opt-in 扩展。
> **权威来源**:plugin 设计文档 `src/design.md` §3.6.2;OKF spec 字段详见 `src/schema/frontmatter.schema.yaml`(锁 OKF v0.2 字段)。
> **本文件目的**:让外部 OKF 工具 / 评测者 / 集成者明白"读到本 plugin 产物时,哪些是 OKF 标准、哪些是 plugin 扩展、哪些扩展是 opt-in / 必须"。

---

## 1. 基础声明

本 plugin(`aeps-llm-wiki-plugin`)产出的 `knowledge/` 目录是 **OKF v0.2 兼容的 bundle**:

- ✅ **bundle 结构**:UTF-8 Markdown 文件 + YAML frontmatter + 目录拓扑(OKF §5 / §6)
- ✅ **必填字段 `type`**:每个 concept 文件 frontmatter 都有非空 `type:` 字段(OKF §5)
- ✅ **可选字段**:不写 `title` / `tags` / `description` 不违反 spec(OKF §9 "consumers MUST NOT reject bundle because of missing optional frontmatter fields")
- ✅ **reserved 文件**:`index.md` 无 frontmatter(`SCHEMA.md` / OKF §6);`log.md` 走本地优先级策略(详见 `SCHEMA.md` §0)

## 2. opt-in 扩展(对外可见,OKF 工具可识别为扩展)

### 2.1 wiki link 双格式

**扩展内容**:正文 wiki link 同时支持两种 markdown 形式:

| 形式 | 来源 | 解析器 |
|---|---|---|
| `[[wikilink]]` / `[[page\|显示]]` / `[[page#章节]]` | Obsidian 原生 + Karpathy 老 wiki 兼容 | Obsidian(原生)+ plugin 自实现 OKF reader |
| `[text](path/to/page.md)` | OKF §6.1 标准 markdown bundle-relative 链接 | 通用 markdown 渲染器 + OKF 工具 |

**为什么需要扩展**:OKF v0.2 §6.1 只定义标准 markdown bundle-relative 链接,Obsidian 用户的工作流严重依赖 `[[wikilink]]` 双链语义(双链面板 / 反向链接图谱 / 全文跳转)。强迫只写 `[text](path.md)` 会:

- 破坏 Obsidian 反向链接图谱(Obsidian 不解析 `[text](path.md)` 为双链)
- 拒绝从 Karpathy 老 wiki / 其他 Obsidian vault 导入
- 增加人工编辑负担(Obsidian UI 自动补全的就是 `[[wikilink]]`)

**Spec 兼容性**:

- OKF v0.2 §9 写明 "consumers MUST NOT reject bundle because of missing optional frontmatter fields" + "consumers SHOULD tolerate unknown constructs"(原则性约束)
- 本扩展**仅扩展链接语法**,**不动** spec 任何字段语义
- OKF 工具不识别 `[[wikilink]]` 时,会自动 fallback 到仅解析 `[text](path.md)`,**不报错**(符合 §9 容忍未知 construct 原则)

**plugin 自实现 OKF reader**:`src/scripts/okf-reader.py`(M3 落地)同时解析两种形式,产出 OKF `sources` 列表供外部 OKF 工具消费。

### 2.2 不依赖 frontmatter `links:` 镜像字段

**扩展内容**:**plugin 不生成、不校验、不维护 frontmatter `links:` 字段**。OKF v0.2 spec 也**未要求**该字段(spec 必填只有 `type:`),所以本 plugin 的产物在 spec 层面无 `links:` 字段也是完全兼容的。

**为什么不镜像**:

- OKF 兼容靠 plugin 自实现 OKF reader 双格式识别(见 §2.1)
- 镜像字段会引入 Single Source of Truth 违反风险——用户改 Obsidian UI 的 `[[wikilink]]` 后,frontmatter `links:` 不会自动同步;lint 自动同步又破坏人工编辑精度
- OKF v0.2 §9 已明确 optional 字段缺失不构成 incompat

**对外部 OKF 工具的影响**:工具读本 plugin 产物时,**不应**要求 `links:` 字段存在;`sources` / 反向链接关系应通过解析正文 wiki link 得到。

## 3. plugin 内部约定(对外不可见)

下面约定**仅**对 plugin 内部子系统(ingest / query / lint / synthesize skill + 自实现 OKF reader)有意义,外部 OKF 工具无需关心:

### 3.1 6 轴 tag 受控词表

- frontmatter `tags` 走 YAML list(OKF 标准)
- 值受限于 `templates/tag-template.md` 6 轴受控词表(`domain/` / `layer/` / `phase/` / `docform/` / `maturity/` / `tec/` 六个 axis 前缀)
- hierarchical tag `#domain/autosar` 形式兼容(OKF `tags` 字段语义未禁)

### 3.2 `raw_category` 派生字段约定

- 不写 frontmatter,运行时由 lint / query 从 `sources[0].resource` 路径解析
- 详见 design §3.6.1

### 3.3 actor 字符串

- `log.md` 写入格式:`agent: producer/aeps-llm-wiki-plugin/<version>` / `human:<id>` / `process:<id>`
- 详见 SCHEMA.md §4

## 4. 兼容性矩阵

| 角色 | 行为 |
|---|---|
| Obsidian 用户打开 `knowledge/` | ✅ 直接 vault 化打开,`[[wikilink]]` 双链图谱完整 |
| 通用 markdown 渲染器(GitHub / VSCode) | ✅ 渲染 `[text](path.md)` 链接;`[[wikilink]]` 显示为纯文本(无副作用) |
| OKF v0.2 工具 / spec 校验器 | ✅ 必填 `type` 满足;其他字段缺失不违反 spec(§9) |
| OKF 工具读 wiki link | ⚠️ 标准工具只解析 `[text](path.md)`;`[[wikilink]]` 被忽略但不报错;若需完整双向链接请用本 plugin 自实现 OKF reader |
| Karpathy 老 wiki 导入 | ✅ `[[wikilink]]` 一等公民兼容,无需任何转换 |

## 5. 升级 OKF 版本的策略**:当 OKF spec 升到 v0.3+:

- plugin 维护者对比新 spec 字段,识别新增 optional / mandatory 字段
- 新 mandatory 字段 → plugin 必须适配(SCHEMA.md §2 + frontmatter.schema.yaml)
- 新 optional 字段 → plugin 评估是否启用,默认不启用(避免 spec 漂移)
- 本文件作为 changelog 入口,记录每次 OKF 升级时的 plugin 适配说明

## 6. 引用

- [OKF v0.2 spec](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md)
- [OKF spec §9 容忍策略](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md#9-conformance-and-extension)
- plugin 内部设计:`src/design.md` §3.6.2
- 模板:`src/templates/knowledge-SCHEMA.md`
- plugin 自实现 OKF reader:`src/scripts/okf-reader.py`(M3 落地)
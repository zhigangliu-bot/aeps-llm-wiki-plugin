# aeps-llm-wiki-plugin — PRD

> **状态**:已冻结(v0.5.0,2026-09-07)
> **创建日期**:2026-09-01
> **作者**:zhigang.liu
> **范围**:仅本文档;实现期细节见 [design.md](./design.md),执行清单见 `implement.md`(待写)

## Change History

| 版本 | 日期 | 变更 |
|---|---|
| v0.2.0 | 2026-09-01 | 基线快照(commit `88b2ba9`,696 行) |
| v0.3.0 | 2026-09-06 | 瘦身(commit `f3351e8`,573 行):6 个 X.X.1 时序表合并到各 skill 主节;lint 规则 C1-C20 集中到 §4.4;§10 并入 §6.2/6.3;AC 改为断言格式;风险从 16 行砍到 8 行。freeze commit `f9d1274`(状态 + Change History) |
| v0.4.0-draft | 2026-09-06 | 二次瘦身(573 → 431 行,-25%):§4.1.1 职责分层整节外移;§4.2 5 路径分流表 + frontmatter 扩展字段表 + source 页正文结构 + 强制溯源范围表外移;§4.4 lint C1-C20 集中表 + `--fix` 分流细节外移;§4.6 路径 B 计数器细节并入 design.md;§6.1 目录树缩成简表;§10「参考」并入 design.md §9;同步修复 §4.1 重复 CLAUDE.md 区块导致的代码块错位(虚假 `## Wiki 工作流` 占用 200 行)。design.md v0.1.0-draft 同批落地 |
| v0.4.0 | 2026-09-06 | freeze(状态 + Change History) |
| v0.4.1 | 2026-09-06 | AC-9(G10)重写为"原生优先 / 失败回退 anydoc"二选一验收(对齐 design.md §3.2 + §7.2 原生优先原则);不放宽其它目标 |
| v0.5.0 | 2026-09-07 | 新增 G12 + §4.7 Update check hook(SessionStart 自动检测远端 commit + ff-only 拉取 + force-push diverge 自动 reset + 拉取失败告知)。hook 代码 `scripts/update-check/check.js` + `hooks/hooks.json`,纯 Node.js 单文件零 npm 依赖。冻结基础为已实现 commit `92ba7a3` |

---

## 1. 背景

LLM 时代做个人 / 团队知识沉淀,有两个互补的范式 + 一个不可绕开的前端:

1. **Andrej Karpathy 的 LLM Wiki 模式** —— LLM 读源一次,产出持久、累积、互相链接的 markdown wiki,人做策展。代表实现:`balukosuri/llm-wiki-karpathy`,核心是 `CLAUDE.md` 作为 Agent 操作手册 + `wiki/` + `raw/` 两层结构 + `index.md` / `log.md` 双索引。
2. **Google Cloud 的 Open Knowledge Format(OKF)** —— 把"LLM-wiki pattern"形式化成一个厂商中立、零运行时的开放规范。`markdown + YAML frontmatter`,**唯一必填字段 `type`**,OKF 工具链可直接消费。
3. **Obsidian 作为 LLM-wiki 的前端** —— Obsidian 是当前最成熟的本地 markdown 知识库 UI(`vault/` + 双链 + tag 面板 + 反向链接图谱),plugin 生成的 `knowledge/` 必须能直接被 Obsidian 打开使用,无需任何格式转换。具体约束:
   - **链接写法**:**plugin 正文主推 `[[wikilink]]` 裸文件名**(`[[andrej-karpathy]]` 或带别名 `[[Andrej Karpathy]]`),依赖 Obsidian 唯一名 + 别名解析,三条规则(首字链接 / 裸文件名 + aliases / 关联导引)见 §10 Q9。标准 markdown 链接降级为兼容写法,plugin 不发明 `links:` frontmatter 字段、不做镜像同步。
   - **tag 必须 Obsidian 原生可识别**:frontmatter `tags:` 走 YAML list,Obsidian 自动扫到 tag 面板;六轴受控词表与 Obsidian tag 体系并存(`#domain/autosar` 这种 hierarchical tag 也兼容)
   - **目录结构 Obsidian 直读**:`knowledge/{entities,concepts,sources,...}/` 即 vault 子文件夹,无需任何映射层
   - **反向链接图谱**:Obsidian 自动生成的反向链接面板(`[[wikilink]]` 原生) = plugin 第 3 跳扫描的"邻居页"佐证;OKF reader 兼容解析 wikilink 与标准 markdown 链接(§6.1 "MAY standard markdown link"为允许而非禁止),plugin 不在 frontmatter 重复存链接(避免与 OKF §5「Lineage is expressed through links, not a dedicated field」冲突)

`aeps-llm-wiki-plugin` 把这三个范式整合成一个**Claude Code plugin**,让用户用一个 `/aeps-llm-wiki-init` 就在自己的研究 / 学习 / 笔记项目里跑起来,产出**OKF 兼容的、Karpathy 启发的、Obsidian 直读的**知识库。LLM 写,人用 Obsidian 读,plugin 管一致性。

**目标用户**:汽车电子软件工程师、架构师,用 Claude Code + Obsidian 做内部研究 / 知识沉淀 / 学习笔记等长期知识管理的人。

---

## 2. 目标 / 非目标

### 2.1 目标(必须达成)

- **G1**:用户 install plugin + 跑一次 `/aeps-llm-wiki-init`,**5 分钟内**得到一个可用的 OKF 知识库目录,无需手动建文件、写 schema。
- **G2**:用户在 `inbox/` 放一份资料,跑 `/aeps-llm-wiki-ingest`(无参数,自动扫 inbox/),**由 LLM 生成**对应的 OKF 概念页,并自动维护 `index.md`、`log.md`、`glossary.md`。
- **G3**:用户用 `/aeps-llm-wiki-query {question}`,plugin 帮用户**从 `knowledge/` 里找答案 + 引用**,并询问是否把回答落档为 `analysis` 页。
- **G4**:plugin 生成的 wiki **严格兼容 OKF v0.2** —— 任何 OKF 工具(Knowledge Catalog、其他 agent 的 reader)能直接消费。
- **G5**:plugin 的所有 skill 前缀统一为 `aeps-llm-wiki-`(防命名空间冲突)。
- **G6**:`plugin **不自带常驻运行时**(无 Node CLI daemon、无 Python CLI daemon、无 MCP server、无 RAG/embedding 服务)—— 纯规范 + skill + 单次运行的 scripts + 事件回调 hooks。**语言基线**:scripts 单栈 Node.js(Node.js LTS,具体基线由实现期 `package.json` engines 字段锁定,本文档不锁版本号);**仅在 Node 端 PaddleOCR 实现不可用或精度不达预期时**,允许在 OCR 路径降级 Python(`paddleocr`官方包)作为兜底,**不引入 Python 常驻 daemon**(跑完即退)。允许 hooks(plugin 本体`hooks/hooks.json`,事件回调同步跑完即退,不开监听);scripts 与 hooks 都遵循"agent 调一次就跑完退"原则。
- **G7**:用户把资料丢进 `inbox/`(暂存入口,**唯一入口**),跑 `/aeps-llm-wiki-ingest`(无参数,自动扫 inbox/),**LLM 提议 raw/ 子目录分类 + 用户拍板**后,文件迁移到 `raw/{subdir}/`,inbox 清空。统一为 `inbox/` 入口;raw/ 是已归档的不可变层。
- **G8**:用户跑 `/aeps-llm-wiki-synthesize {topic}`,plugin 帮用户在 `knowledge/syntheses/` 写一份**常驻综合页**(`type: synthesis`,不带时间戳),引用 wiki 里所有与 `{topic}` 相关的页(Karpathy line 31 "synthesis")。
- **G9**:plugin 在 ingest 多份同类 entity 或 query 累计"X vs Y"高频时,**主动提议**建 `knowledge/comparisons/{a}-vs-{b}.md` 常驻对照页(Karpathy line 31 "comparisons"),由用户拍板才建。
- **G10**:**外部工具转换的 md 副本随原文件一起入 raw**,源页正文主推 `[[wikilink]]` 指向 md 副本(G10 衍生需求,见 §4.2 M1-M4,Q9 决策):
  - `.pptx` / `.docx` / `.xlsx` / `.pdf` / `.png` / `.jpg` / `.jpeg` / `.bmp` / `.tiff` 经 anydoc / paddleocr / Claude converter 转换后,转换产物 **必须落盘到 raw/**(命名 `{basename}.{ext}.converted.md`),与原文件**同一子目录共存**
  - 源页 `type: source` frontmatter `source_file:` 与 `sources[].resource` 仍指向**原文件**;`converted_path:` plugin 扩展字段指向 **md 副本**(详见 §4.2 M2)
  - query 阶段 LLM 通过 `converted_path` 字段直接读 md 副本,**不再二次跑转换**(原"raw/ 里 .pdf LLM 解析不了"痛点解决)
  - 重转策略:**不重转**(对齐 raw/ 不可变层 + G7 + Q5);需重转时由用户手工 `cp` 回 `inbox/` 走标准 ingest
  - 纯文本类(.md / .markdown / .rst / .txt / .csv / .json / .yaml / .yml / .xml / .html / .htm) **不生成** .converted.md 副本(原生可直接读)
- **G11**:**query skill 落档为 analysis 页时消除 3 个隐患**(G11 衍生需求,见 §4.3):
  - **结构**:`analyses/` 使用专属 3 节骨架：`## 方案推演 / 架构分析`、`## 关联溯源`、`## 总结:最有收获的一句话`。
  - **溯源丢失**:`type: analysis` frontmatter **新增必填 `sources_used`**(本次回答参考的 wiki 页相对路径列表,供图跳转 + 后续 lint 校验;C15)
  - **Over-prompting**:**落档询问加 gating**(防 Exact 查证型 spam):仅在跨领域综述 / 对比分析 / 整合 ≥ 2 源 / 深度 ≥ 200 字 触发,Exact / 短答 / 未命中 / Wiki 未覆盖自动跳过

### 2.2 非目标(明确不做)

- ❌ **不**带版本 / 基线 / 变体管理字段 —— 目标用户做的是内部研究,不是项目交付,基线无意义。如果将来需要,在 `schema/frontmatter.schema.yaml` 加 3 行。
- ❌ **不**做 RAG / 向量搜索 / embedding —— 由 OKF 生态或用户自选 qmd 等工具承担。
- ❌ **不**做自动监控文件变动 —— 用户主动 say "ingest",符合 Karpathy 哲学。
- ❌ **不**做 Claude Code plugin 之外的兼容(Codex/Cursor 等)—— 其它 Agent 用户手动读 `schema/aeps-llm-wiki.schema.md` 也能用,但不在本 plugin 维护范围。
- ❌ **不**内置 marketplace 配置(等 plugin 稳定后再说,见 `MEMORY: aeps-llm-wiki marketplace 待办`)。

---

## 3. 用户故事

| ID   | 角色          | 场景                                           | 期望                                                                                                                                                                                                |
| ---- | ------------- | ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| US-1 | 研究者        | 想在新项目里开 wiki                            | 跑一次 init 就得到可用结构,不用手动建 7 个文件                                                                                                                                                      |
| US-2 | 研究者        | 把刚下载的 OKF spec 放到`inbox/`             | ingest 后`knowledge/concepts/open-knowledge-format.md` 自动出现,`index.md` 自动更新                                                                                                             |
| US-3 | 学习者        | 读 wiki 时想确认某概念是否被覆盖               | query 给出**带 wiki 引用的**回答,并问要不要落档                                                                                                                                               |
| US-4 | 长期用户      | wiki 长到 50+ 页,担心维护成本                  | lint 报告孤儿页、矛盾、过期;`--fix` 模式**只自动应用确定性结构修复**(frontmatter / 3 节骨架 / `## 摘要` 残留),**语义级问题**(矛盾 / 命名飘合并 / 漏链 / 陈旧处理)仍出提案等用户确认 |
| US-5 | 好奇者        | 在 OKF Knowledge Catalog 里发现一个别人的 wiki | 能直接导入到本地(因为我们输出严格 OKF)                                                                                                                                                              |
| US-6 | plugin 维护者 | 想加新实体类型"法规"或"标准"                   | 改`schema/frontmatter.schema.yaml` + 一行 skill 配置,不用改 plugin 主代码                                                                                                                         |
| US-7 | 研究者        | 拿到一份资料但还没决定归档到 raw/ 哪个分类     | 丢`inbox/`,ingest 时 LLM 提议子目录(如`raw/okf/`),用户一句"好"或改后确认,文件自动迁移                                                                                                           |

---

## 4. 功能需求

### 4.1 Init skill

- **触发**:`/aeps-llm-wiki-init`(首次启用或已存在项目再次启用,后者走"幂等再入",见下方)
- **目录名约定**(硬约束,无参数):`inbox/` `raw/` `scripts/` `schema/` `templates/` `knowledge/` **六个**顶层目录名**全部固定默认**(顺序按契约→执行流:`schema/` 是 frontmatter 契约,放 `templates/` 之前),init 不接受 `--xxx-dir` 之类的目录名参数;子目录名见 §6.1
- **必须**(首次启用,**全栈建好**):
  1. **创建 `{project}/inbox/`**:放 `README.md`(从 `doc/template/inbox-readme.md`) + `.gitkeep`
  2. **创建 `{project}/raw/`**:放 `README.md`(从 `doc/template/rawdir-spec.md`) + `.gitkeep`;**预建 15 类子目录,每个放 `.gitkeep`**
  3. **创建 `{project}/scripts/`**:从 plugin 本体 `scripts/` 目录下**所有文件**拷贝过去(具体文件清单由实现侧按目录扫描决定,不写入本文档)
  4. **创建 `{project}/templates/`**：从 plugin 本体 `doc/template/` 目录下拷贝所有文件过去
  5. **创建 `{project}/schema/`**：从 plugin 本体 `doc/schema/` 目录下拷贝所有文件过去
  6. **创建 `{project}/knowledge/`**:
     - `index.md` + `overview.md` + `glossary.md` + `log.md`(从对应模板)
     - **预建 18 个叶子存储目录**(`sources/` + `entities/{person,organization,project,product,event,place,other}/` + `concepts/{theory,method,field,phenomenon,standard,term,other}/` + `analyses/` + `comparisons/` + `syntheses/`;算术 1+7+7+1+1+1=18),**每个叶子目录放 `.gitkeep`**
- **必须**（已存在项目再次启用，**幂等再入**）：
  - 除表格明确标注“覆盖”的受控文件外，不静默覆盖任何用户本地新增、修改或删除的内容。
  - 缺失的标准目录补建；plugin 新增但用户项目中不存在的目录不自动创建，留给 ingest 拍板。
  - 文件同步策略见下表；每个文件的首次 init 与 re-run 行为仅以表格为准。

    | 文件路径                               | 首次 init                                                | re-run init                                                    |
    | -------------------------------------- | -------------------------------------------------------- | -------------------------------------------------------------- |
    | `knowledge/SCHEMA.md`                | 不创建。工作流入口统一使用`doc/schema/schema.md`。     | 不适用                                                         |
    | `knowledge/index.md`                 | 从`doc/template/` 复制空模板。                         | 不修改，保留用户内容。                                         |
    | `knowledge/overview.md`              | 从`doc/template/` 复制空模板。                         | 不修改，保留用户内容。                                         |
    | `knowledge/log.md`                   | 从`doc/template/` 复制，并写入一条 `Init` 起始记录。 | 追加 plugin 运行产生的记录，不删除已有记录。                   |
    | `knowledge/glossary.md`              | 从`doc/template/` 复制空模板。                         | 按字典同步：只追加 plugin 新增内容，不恢复用户主动删除的内容。 |
    | `inbox/README.md`                    | 从`doc/template/` 复制。                               | 覆盖为 plugin 当前版本提示文案。                               |
    | `raw/README.md`                      | 从`doc/template/` 复制。                               | 按字典同步，只追加新的分类规则。                               |
    | `templates/page-*.md`                | 从`doc/template/` 复制全部页面模板。                   | 缺失模板补建；已有模板不覆盖。                                 |
    | `templates/README.md`                | 从`doc/template/` 复制。                               | 覆盖为 plugin 当前版本说明。                                   |
    | `templates/concept-entities-spec.md` | 从`doc/template/` 复制。                               | 按字典同步，只追加新的子类判定示例。                           |
    | `templates/tag-spec.md`              | 从`doc/template/` 复制。                               | 按字典同步，只追加新的 tag 模板。                              |
    | `scripts/*`                          | 从 plugin 的`scripts/` 复制全部脚本。                  | 缺失脚本补建；已有脚本不覆盖。                                 |
    | `schema/*`                           | 从`doc/schema/` 复制全部 schema 文件。                 | 覆盖为 plugin 当前版本文件。                                   |
  - 完成后向用户报告 sync 摘要：追加条数、覆盖文件、补建目录。
  - **最后**，幂等维护用户工程根目录的 `CLAUDE.md`：

    - 没有 `CLAUDE.md` 时创建文件并写入以下受控区块；已有文件时在末尾追加该区块。
    - 已存在完全相同区块时不重复追加。
    - 已存在旧版本的 plugin 受控区块时替换该区块，不继续追加。
    - 只修改 plugin 自己管理的受控区块，不修改用户其他内容。

      ```md
      <!-- aeps-llm-wiki-plugin:start -->
      ## Wiki 工作流

      你的身份是一个汽车电子软件工程师、架构师,开始任何工作前，先读取 `schema/schema.md`，并遵循其中的工作流与数据契约。
      <!-- aeps-llm-wiki-plugin:end -->
      ```
  - `CLAUDE.md` 不纳入上表文件同步策略；重复运行 init 时按上述规则幂等维护。
- **不应**:覆盖已存在 `knowledge/` 用户内容;若 `knowledge/` 非空走幂等再入分支,不警告阻止

**流程表**(步骤 / 做什么 / 写什么 / 是否阻塞):

| #   | 步骤           | 做什么                                                                         | 写什么文件 / 操作                                                                  | 阻塞?                          |
| --- | -------------- | ------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------- | ------------------------------ |
| 0   | 检测工程状态   | 判`{project}/` 是否已含 6 顶层目录 + 各自 `.gitkeep`                       | 只读                                                                               | **是**                   |
| 0-A | 幂等再入分支   | 按「文件同步策略表」判定每个文件覆盖 vs 保留                                   | LLM 判定                                                                           | 是                             |
| 0-B | 首次启用分支   | 按下表建 6 顶层 + 各 .gitkeep                                                  | LLM 判定                                                                           | 是                             |
| 1   | 建 inbox/      | 从`doc/template/inbox-readme.md` 拷 README                                   | `inbox/README.md` + `inbox/.gitkeep`                                           | 否                             |
| 2   | 建 raw/        | 拷字典副本 + 预建 15 类子目录                                                  | `raw/rawdir-spec.md` + `raw/{01_EE架构,...,15_算法}/.gitkeep` × 15            | 否                             |
| 3   | 建 scripts/    | 从 plugin 本体`scripts/` 目录**所有文件**拷贝(清单由实现期决定)        | `scripts/*`(整目录递归)                                                          | 否                             |
| 4   | 建 templates/  | 从`doc/template/` 全拷                                                       | `templates/*`(整目录递归)                                                        | 否                             |
| 5   | 建 schema/     | 从`doc/schema/` 全拷                                                         | `schema/*`(整目录递归)                                                           | 否                             |
| 6   | 建 knowledge/  | 首次:建 index/overview/glossary/log + 预建 18 个叶子目录;幂等:按同步策略表分流 | `knowledge/{index,overview,glossary,log}.md` + 18 叶子 `.gitkeep` 或同步后文件 | 否                             |
| 7   | 维护 CLAUDE.md | 幂等管理 plugin 受控区块(规则见上)                                             | `{project}/CLAUDE.md` 受控区块                                                   | 否                             |
| 8   | sync 摘要报告  | 打印覆盖 / 追加 / 跳过清单                                                     | `stdout`                                                                         | **是**(报告后 init 完成) |

> 实现期细节(脚本契约 / 职责分层 / SKILL.md 硬约束)见 [design.md §4](./design.md)。

### 4.2 Ingest skill

- **触发**:`/aeps-llm-wiki-ingest`(无参数,递归扫 `inbox/`)
- **入口**:**仅 `{project}/inbox/`**(G7 唯一入口);raw/ 不被扫描,调整走 `git mv`;历史归档补建 → `cp` 回 `inbox/` 重跑
- **第一原则(原生多模态优先)**:**先让 Claude Code 原生读**,能读 → 路径 1/2 直接结束,不生成 `.converted.md`、不调 `convert-to-md.py`、不消耗 OCR / 转换依赖;只有 LLM 真的无法识别时才降级路径 3/4

> 实现期细节(5 路径分流表 / source frontmatter 扩展字段 / Source 页正文结构 / 强制溯源范围 / 来源不足自检 / SKILL.md 调用顺序 / 重 ingest 拍板门 / 不重转策略)见 [design.md §3 + §6](./design.md)。

转换失败 → FAIL,原文件保留 inbox。

**Entity / Concept 抽取**:具象 → `knowledge/entities/{子类}/{slug}.md`(`type` = 子类);抽象 → `knowledge/concepts/{子类}/{slug}.md`;子类 ↔ 目录 1:1 绑死(详见 `concept-entities-spec.md`);正文自由发挥。

**反链机制**:source 页 `## 相关页面(Related Pages)`(Entities / Concepts 分组 wikilink)与 entity/concept 页 `## 来源资料` 小节互为反链,Obsidian 反链面板依赖此约定;每次 ingest 完全重建,不保留人工条目;空组 / 全空时分别省略该组或整个区块。

**流程表**(步骤 / 做什么 / 写什么 / 阻塞):

| #  | 步骤                                     | 做什么                                                                                       | 写什么文件 / 操作                                      | 阻塞?                                           |
| -- | ---------------------------------------- | -------------------------------------------------------------------------------------------- | ------------------------------------------------------ | ----------------------------------------------- |
| 0  | 探测 LLM 原生能力                        | 对 inbox 每个文件,先让 Claude Code 直接读                                                    | 只探                                                   | **是**(能读 → 跳 1-2,直接 5;不能 → 1-2) |
| 1  | 扫 inbox/ 找新文件                       | 递归扫描                                                                                     | 只读                                                   | 是                                              |
| 2  | 5 路径分流                               | 扩展名 → 路径 0/1/2/3/4                                                                     | 必要时`raw/{subdir}/{file}.converted.md`             | 是(转换失败 → FAIL)                            |
| 3  | LLM 提议 raw 子目录 + 命名飘检查         | Levenshtein ≤ 2 / 前缀差异 / 同义;命中已有 → 强制改用,未命中 → 拍板门分流                 | 对话                                                   | 是                                              |
| 4  | mv 原文件 + md 副本                      | `safe-mv.py --apply`                                                                       | `raw/{subdir}/{file}` + `.converted.md`            | 是                                              |
| 5  | 提取要点对话(可"继续"跳过)               | 防 spam 对话                                                                                 | 对话                                                   | 否                                              |
| 6  | 建 source 页 skeleton                    | `gen-page.js --type source`                                                                | `knowledge/sources/<slug>.md`(frontmatter + 3 节 H2) | 是                                              |
| 7  | LLM 填 source 正文                       | 仅 H2 之间正文(不改 frontmatter / H2 顺序 / 维护说明);3 节骨架 + 自由追加节;输出溯源自检报告 | `knowledge/sources/<slug>.md`                        | 是                                              |
| 8  | 追加`> 原始来源:` + Related Pages 占位 | M3 链接目标按 native_text 切;路径 1/2 → 原文件,路径 3/4 → md 副本                          | 同上(脚本写)                                           | 是                                              |
| 9  | 判定 entity / concept 抽取               | LLM 读 raw +`concept-entities-spec.md` 判 18 子类                                          | LLM 判定                                               | 是                                              |
| 10 | 建 entity / concept 页 skeleton          | `gen-page.js --type {entity/concept}.{subtype}`                                            | `knowledge/{entities,concepts}/{subtype}/{slug}.md`  | 否                                              |
| 11 | LLM 填 entity / concept 正文             | 自由发挥                                                                                     | 同上                                                   | 否                                              |
| 12 | 追加`## 来源资料` 小节                 | 反链 wikilink(按 title 排序)                                                                 | 同上(脚本写)                                           | 否                                              |
| 13 | 回填 source 页`## 相关页面`            | 实际 wikilink(完全重建)                                                                      | `knowledge/sources/<slug>.md`                        | 否                                              |
| 14 | 更新受影响已有 wiki 页                   | 命名飘合并 / 改链                                                                            | LLM 决定                                               | 否                                              |
| 15 | 更新 glossary.md                         | 增量合并,不改用户手写                                                                        | `aggregate-index.js`                                 | 否                                              |
| 16 | 更新 index.md                            | 登记新页(modified 栏)                                                                        | `aggregate-index.js`(幂等)                           | 否                                              |
| 17 | 更新 overview.md                         | 仅大图变化时                                                                                 | LLM 决定                                               | 否                                              |
| 18 | 追加 log.md                              | ISO 8601,最新在前                                                                            | `knowledge/log.md`                                   | 否                                              |
| 19 | lint C17/C18/C19 校验本次产出            | 只读                                                                                         | FAIL 列表 + WARN                                       | **是**(FAIL 必须修)                       |

### 4.3 Query skill

- **触发**:`/aeps-llm-wiki-query {question}`
- **Intent 路由(3 档)**:LLM 分 `exact` / `ambiguous` / `{overview, comparison, other}`;**`ambiguous` 走 fallthrough 不触发**(低扰动 fallback,非路径 C 词命中);路径 C 触发词清单(`vs` / `对比` / `区别` / `异同` / `优缺点` / `X vs Y` 型对象对)仅作 LLM 推断辅助,不替代语义判断
- **4 跳扫描**:

  1. `knowledge/index.md` + tags 关键词 top-K 过滤
  2. 读候选页 frontmatter(`description` / `summary` → `title` → 全文)
  3. 1 跳深度沿 `[[wikilink]]` / 关联导引节跳 `entities/` `concepts/` `analyses/` `comparisons/` 邻居页
  4. `glossary.md` 消歧 + `log.md` 近期 10 条
- **本地搜索引擎 qmd 分流**:

  | wiki 规模   | 引擎选择                             | 未装 qmd 行为               |
  | ----------- | ------------------------------------ | --------------------------- |
  | < 500 页    | 纯`index.md` + 4 跳扫描            | 不调 qmd                    |
  | 500~1000 页 | 优先 qmd(`qmd query "{question}"`) | 提示用户装,降级`index.md` |
  | > 1000 页   | **必须** qmd                   | **报错退出**          |

  阈值常量:`QUERY_INDEX_THRESHOLD = 500` / `QUERY_QMD_REQUIRED_THRESHOLD = 1000`;探查入口:`scripts/check-qmd.js`
- **回答格式**:每条断言附 `[[wikilink]]`(主推);标准 markdown 链接降级兼容;**绝不**编造 wiki 里没有的内容,未覆盖答"我读到的 wiki 里没有覆盖这点"
- **G11 落档 gating**:回答结束后**仅在满足触发条件之一**时询问是否落档

  | 触发(任一命中即问)                         | 不触发(任一命中即跳过)                      |
  | ------------------------------------------ | ------------------------------------------- |
  | intent = overview(全局设计 / 方案评估)     | intent =`exact`(纯事实查证)               |
  | intent = comparison(`X vs Y` 型对象对比) | intent =`ambiguous`(语义模糊,fallthrough) |
  | 命中 ≥ 2 个不同 wiki 子目录的源页         | 回答字数 < 200 字                           |
  | 回答字数 ≥ 200 字                         | 命中源 < 2 个                               |
  |                                            | 含 "Wiki 未覆盖此问题" 字样                 |
- **落档为 analysis 页**(G11 M1 + M2,触发后):

  - 路径:`knowledge/analyses/{timestamp}-{slug}.md`
  - frontmatter 必填:`answer_to`(原问句)/ `sources_used`(本次回答参考的 wiki 页相对路径列表,SKILL.md 自动抓阶段 2 命中 + 阶段 3 引用路径)/ `generated_by: agent: producer/aeps-llm-wiki-plugin/{version}` / `summary`(首行 `**问题**: {原问句}`,余下 ≤ 280 字符)
  - 正文 3 节专属骨架(缺一即 FAIL):
    - `## 方案推演 / 架构分析` —— 核心推演与架构逻辑
    - `## 关联溯源` —— 关键 Wiki 事实与依据;末行 `> 引用:` 列源路径(标准 markdown 链接),与 `sources_used` 双向引用,lint 校一致(Q7 死循环防护)
    - `## 总结:最有收获的一句话` —— Core Verdict
  - 出现 `## 摘要` / `## Summary` → 内容迁移到 frontmatter `summary` 字段

**流程表**(步骤 / 做什么 / 写什么 / 阻塞):

| #  | 步骤                    | 做什么                                                                           | 写什么 / 操作                                | 阻塞?                                |
| -- | ----------------------- | -------------------------------------------------------------------------------- | -------------------------------------------- | ------------------------------------ |
| 0  | wiki 规模探查           | 数`knowledge/**/*.md` → 选引擎                                                | 只读                                         | 是(> 1000 页 + qmd 未装 → 报错退出) |
| 1  | Intent 路由             | LLM 推断 intent(3 档)+ 路径 C 触发词辅助                                         | LLM 判定                                     | 是                                   |
| 2  | 第 1 跳                 | `index.md` + tags 过滤                                                         | 只读                                         | 否                                   |
| 3  | 第 2 跳                 | 读候选页 frontmatter                                                             | 只读                                         | 否                                   |
| 4  | 第 3 跳                 | 1 跳深度 wikilink / 关联导引节                                                   | 只读                                         | 否                                   |
| 5  | 第 4 跳                 | `glossary.md` 消歧 + `log.md` 近期 10 条                                     | 只读                                         | 否                                   |
| 6  | 组织回答                | 每条断言附`[[wikilink]]`                                                       | 对话                                         | 是                                   |
| 7  | 诚实声明                | 不编造;未覆盖 → 答"我读到的 wiki 里没有覆盖这点"                                | 对话                                         | 是                                   |
| 8  | G11 gating 判定         | 4 触发任一命中 + 4 不触发全不命中 → 落档询问;否则跳过                           | 对话                                         | 是(触发 → 询问;不触发 → 跳过 9-11) |
| 9  | 建 analysis 页 skeleton | `gen-page.js --type analysis --slug {timestamp}-{slug}` + 3 节专属骨架         | `knowledge/analyses/{timestamp}-{slug}.md` | 是                                   |
| 10 | LLM 填 analysis 正文    | 仅 H2 之间正文;`answer_to` + `sources_used` + `summary` + 末行 `> 引用:` | 同上                                         | 是                                   |
| 11 | 追加 log                | `**Creation**: query "{原问句}" → analyses/{file}.md                      | `knowledge/log.md`                         | 否                                   |

### 4.4 Lint skill

- **触发**:`/aeps-llm-wiki-lint [--fix]`
- **报告项**:孤儿页 / 矛盾 / 陈旧页(`stale_after` 已填且过期,**未填一律静默跳过,不报陈旧、不 WARN**)/ 命名飘 / 漏链 / frontmatter 不合规 / 正文骨架不合规
- **`--fix` 分流**:
  - **确定性结构修复**(直接 patch + `log.md` 追加 `**LintFix**`):frontmatter 字段缺失补占位 / 类型错位强转 / `## 摘要` 残留删除并保留内容到 `summary` / sources/analyses 缺 3 节骨架 H2 追加占位 / 标准 markdown 链接残留转 `[[wikilink]]`
  - **语义级问题**(仅出**提案**等用户确认):矛盾 / 命名飘合并 / 漏链 / 陈旧页处理
- **不应**:无 `--fix` 时静默修改文件

> Lint 规则实现细节(12 条 C1-C20 规则表 + 孤儿/矛盾/陈旧/漏链/命名飘 + `--fix` 确定性 vs 语义级分流)见 [design.md §5](./design.md)。

**流程表**(步骤 / 做什么 / 写什么 / 阻塞):

| #  | 步骤                               | 做什么                                                                        | 写什么 / 操作                                                   | 阻塞?                                             |
| -- | ---------------------------------- | ----------------------------------------------------------------------------- | --------------------------------------------------------------- | ------------------------------------------------- |
| 0  | 扫描入口                           | 扫`knowledge/**/*.md`                                                       | 只读                                                            | 是(扫不到 → "wiki 为空,先 init + ingest",exit 0) |
| 1  | C1 frontmatter 必填                | OKF + plugin 扩展字段                                                         | 只读                                                            | 否                                                |
| 2  | C17 模板一致性                     | 比对`gen-page.js` 模板产出                                                  | 只读                                                            | 否                                                |
| 3  | C18 原生 + 副本矛盾                | source frontmatter 组合检查                                                   | 只读                                                            | 否                                                |
| 4  | C19 降级日志                       | raw 对应原文件降级日志                                                        | 只读                                                            | 否                                                |
| 5  | C3 + C4 3 节骨架                   | sources / analyses H2 存在性                                                  | 只读                                                            | 否                                                |
| 6  | C2`## 摘要` 残留                 | 全部 type 禁用                                                                | 只读                                                            | 否                                                |
| 7  | C5`comparison.sources`           | 必填校验                                                                      | 只读                                                            | 否                                                |
| 8  | C6`synthesis.sources_count`      | < 3 WARN                                                                      | 只读                                                            | 否                                                |
| 9  | C7 + C8 analysis 引用一致性        | 路径解析 + Set 比对                                                           | 只读                                                            | 否                                                |
| 10 | 孤儿 / 矛盾 / 陈旧 / 漏链 / 命名飘 | 综合扫描                                                                      | 只读                                                            | 否                                                |
| 11 | 汇总报告                           | FAIL 列表 + WARN 列表 + 统计                                                  | `stdout`                                                      | 否(仅`--fix` 跑 12)                             |
| 12 | `--fix` 分流                     | 确定性 → patch +`log.md` 追加 `**LintFix**`;语义级 → 仅 `stdout` 提案 | 确定性 →`knowledge/**/*.md` + `log.md`;语义级 → 仅 stdout | 否                                                |

### 4.5 Synthesize skill(Karpathy line 31 "synthesis")

- **触发**:`/aeps-llm-wiki-synthesize {topic}`
- **行为**:LLM 决定范围(默认"所有 frontmatter 含 topic 标签或被 tag 关联的页")→ 写 `type: synthesis` 常驻综合页(`knowledge/syntheses/{topic-slug}.md`,**不带时间戳**,后续 LLM 可 update)+ frontmatter `sources_count`(供 lint 评估成熟度)+ 追加 `log.md` + 更新 `index.md`
- **不应**:写一次性"当时综合"(那是 `analysis`,不是 `synthesis`)

**流程表**(步骤 / 做什么 / 写什么 / 阻塞):

| # | 步骤                     | 做什么                                                                          | 写什么 / 操作                           | 阻塞?                                              |
| - | ------------------------ | ------------------------------------------------------------------------------- | --------------------------------------- | -------------------------------------------------- |
| 0 | topic 校验               | 查`index.md` 看是否有任何页与 topic 关联                                      | 只读                                    | 是(无命中 → 提示"先 ingest 再 synthesize",exit 0) |
| 1 | LLM 决定范围             | tags / title / wikilink 三种信号                                                | LLM 判定                                | 是                                                 |
| 2 | sources_count 校验       | < 3 → WARN + 用户拍板;≥ 3 → 进入 3                                           | 对话                                    | 是(`[n]` → 跳过;`[y]` → 进入 3)              |
| 3 | 建 synthesis 页 skeleton | `gen-page.js --type synthesis --slug {topic-slug}`(**不带时间戳,常驻**) | `knowledge/syntheses/{topic-slug}.md` | 是                                                 |
| 4 | LLM 填 synthesis 正文    | 仅 H2 之间正文;`sources_count` 写本次纳入页数                                 | 同上                                    | 是                                                 |
| 5 | 追加 log                 | `**Creation**: synthesis "{topic}" → syntheses/{file}.md                 | `knowledge/log.md`                    | 否                                                 |
| 6 | 重建 index.md 聚合       | `aggregate-index.js` 登记(sources_count = 0 → 不写入)                        | `knowledge/index.md`                  | 否                                                 |

### 4.6 Comparison 自然触发规则(Karpathy line 31 "comparisons")

不增加 skill,由 query / ingest 内置三路径触发:

| 路径                  | 触发                                                                                                                   | 产物                                      |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| A — 同类 entity 触发 | ingest 完成,source 页落档询问时,`entities/{子类}/` 同类 entity ≥ 2 且都本次 ingest                                  | 常驻`comparison` 页(用户拍板才建)       |
| B — 累积检索触发     | query 累计 ≥ 3 次"X vs Y"(全局累计,按主题近似匹配,不要求精确 X/Y)                                                     | 常驻`comparison` 页(下次落档询问时提议) |
| C — 单次词命中       | query 含`vs` / `对比` / `区别` / `异同` / `优缺点` / `X vs Y` 型对象对 → LLM 判定 `intent = comparison` | 本次 analysis 落档(走 §4.3 步骤 8-11)    |

**职责不重叠**:A / B → 常驻 `comparison` 页(`knowledge/comparisons/{a}-vs-{b}.md`,**不带时间戳**,常驻);C → 本次 analysis 落档(职责分开:analysis 一次性快照 / comparison 长期对照表)。

**frontmatter**:`type: comparison` + `sources:` 字段链接到对比的 entity / concept 页。

**不应**:query 一次性给完对比表就结束(那是 answer,不是 comparison);comparison 常驻页必须用户拍板才建。

> 路径 B 计数器(`knowledge/.aeps-state/comparison-counter.json`)细节见 [design.md §7.5](./design.md)。

**流程表**(步骤 / 做什么 / 阻塞):

| # | 步骤              | 做什么                                                            | 阻塞?            |
| - | ----------------- | ----------------------------------------------------------------- | ---------------- |
| 0 | 路径判定          | A / B / C;C → 跳本表,走 §4.3 步骤 8-11                          | 是(C → 跳走)    |
| 1 | LLM 提议主题      | `{a}-vs-{b}` + 对比维度清单                                       | 是               |
| 2 | 用户拍板          | 必须同意才建;[y]/[n]/[d]                                          | 是(拒绝 → 跳 8) |
| 3 | 建 skeleton       | `gen-page.js --type comparison`(不带时间戳,常驻)             | 是               |
| 4 | LLM 填正文        | 仅 H2 之间正文                                                    | 是               |
| 5 | 追加 log          | `**Creation**: comparison ...`                                  | 否               |
| 6 | C5 lint 校验      | `comparison` 必含 `sources` 字段                                  | 否               |
| 7 | 路径 B 计数器更新 | 仅 B + 仅拍板建页后更新                                           | 否               |
| 8 | 拒绝路径          | 仅追加 `**Creation Skipped**` 到 log                              | 否               |

### 4.7 Update check hook

**触发**:`SessionStart` event hook(`hooks/hooks.json`,matcher = `startup`)。每次新会话开始时由 Claude Code 自动调用 `scripts/update-check/check.js`,无用户感知延迟。

**目标**(**G12**,对应 M3 里程碑):

- **G12**:用户在每个 session 开始时**自动**获得 plugin 最新版本,**无需手动卸载重装**。具体:
  - hook 启动时 `git ls-remote origin HEAD` 拿远端 commit SHA,跟本地 `git rev-parse HEAD` 比对
  - 一致 → 静默,exit 0,session 正常初始化
  - 不一致 → `git pull --ff-only origin main` 自动拉取;成功后通过 `hookSpecificOutput.additionalContext` 在 session 开头告知用户(📦 ... → ...);失败或 force-push diverge 见下表
  - 每个 session 都 fetch(无 throttle);版本未变不告知
  - 只拉 `aeps-llm-wiki-plugin`(仓根即 plugin 根,无 monorepo 拆分)
  - 不阻断 session 初始化:任何 throw / 网络异常 / git 缺失 / plugin.json 缺字段 → 静默,exit 0
  - 零 npm 依赖(Node.js 内置 `node:fs/promises` / `node:child_process` / `node:path`),单文件 ~250 行可读可审

**状态机**(hook 报告给用户的 4 类消息):

| 状态 | 触发条件 | 告知用户文案(模板) | 用户下一步动作 |
|---|---|---|---|
| `no-update` | local SHA == remote SHA | (无,静默) | 无 |
| `updated` | `git pull --ff-only origin main` 成功 | `📦 aeps-llm-wiki 已升级(local → remote)。当前 session 仍使用旧代码,运行 /reload-plugins 后生效。` | 跑 `/reload-plugins` |
| `pull-failed` | pull --ff-only 拒绝(dirty tree / 网络 / 鉴权),且 fetch 也失败 | `⚠️ aeps-llm-wiki 有新版本但自动升级失败(原因:truncated)。请手动处理:git pull --ff-only origin main,或重装 plugin。` | 手动 `git pull` 或 `/plugin install aeps-llm-wiki@aeps-public-marketplace` |
| `diverged-reset` | pull --ff-only 拒绝(force-push 重写远端),但 `git fetch` + `git reset --hard origin/main` 成功 | `📦 aeps-llm-wiki 远端历史被改写(force-push),已重置到最新版本(local → remote)。当前 session 仍使用旧代码,运行 /reload-plugins 后生效。` | 跑 `/reload-plugins` |
| `diverged-reset-failed` | reset 也失败(如 dirty working tree 阻挡 reset) | `⚠️ aeps-llm-wiki 远端历史被改写(force-push),本地 cache 跟远端已分叉(原因:truncated)。请手动处理:卸载后重装 plugin,或手动进 plugin 仓跑 git fetch && git reset --hard origin/main。` | 手动 reset 或 uninstall+install |

**契约**(R1-R4,hook 必须满足):

- **R1** 检测:`git ls-remote origin HEAD` + `git rev-parse HEAD`,SHA 一致则 `no-update`,不一致才继续走 R2
- **R2** 拉取:`git pull --ff-only origin main`,失败 → fallback 到 `git fetch origin main` + `git reset --hard origin/main`,再失败 → `pull-failed` 状态(告知用户手动)
- **R3** 告知(成功):stdout 输出 `{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"📦 ..."}}` + 单换行;版本号取自 `.claude-plugin/plugin.json` 的 `version` 字段
- **R4** 静默(失败):任何 throw / git 缺失 / plugin.json 缺字段 / exit 非 0 → stdout 空,exit 0,session 初始化不受影响

**调用约定**(便于调试 / CI):

- 默认(无 flag):hook 模式,JSON stdout,任何情况 exit 0
- `--check-only`:CLI,只检测不拉取,纯文本 stdout,exit 0 / 1 / 2(便于手测 `node scripts/update-check/check.js --check-only`)
- `--pull`:CLI,检测 + 拉取,纯文本 stdout,exit 0 / 1 / 2

**非目标**:

- ❌ 不实现 diff 显示(用户拉完直接看 plugin 仓根的 README/CHANGELOG)
- ❌ 不实现版本号硬校验(只比对 commit SHA;plugin.json `version` 字段仅用于告知文案)
- ❌ 不实现多 plugin 并行检测(marketplace 范围内本 plugin 独立)
- ❌ 不实现 marketplace 级别的更新通知(单 plugin scope)
- ❌ 不写 G11 gating 规则里那种"用户拍板才执行"的逻辑 —— 升级由 hook 自动执行,失败才打断用户

**实现位置**:

- hook 代码:`scripts/update-check/check.js`(单文件,零 npm 依赖)
- hook 配置:`hooks/hooks.json`(SessionStart matcher = startup)
- 单测:`scripts/update-check/test/check.test.js`(36 用例覆盖 semver / SHA / 状态机 / 静默分支 / JSON 协议)
- 模块 README:`scripts/update-check/README.md`

---

## 6. 数据契约(高层)

### 6.1 知识库目录结构(默认)

6 顶层固定:`inbox/` `raw/` `scripts/` `schema/` `templates/` `knowledge/`(init 不接受目录名参数;详见 §4.1)。

**raw/ 预建 15 类子目录**(编号前缀 `\d+_`,init 时按 `templates/rawdir-spec.md` 字典建):`01_EE架构 / 02_芯片 / 03_通信与网络 / 04_操作系统与中间件 / 05_软件工程 / 06_功能安全 / 07_信息安全 / 08_AI与AI工程 / 09_域控制器 / 10_会议与活动 / 11_开发工具 / 12_法规_标准_政策 / 13_流程体系 / 14_测试与验证 / 15_算法`

**knowledge/ 预建 18 个叶子存储目录**(`1 + 7 + 7 + 1 + 1 + 1 = 18`):

| 子目录 | type 值 | 用途 |
|---|---|---|
| `knowledge/sources/` | `source` | 原件归档 |
| `knowledge/entities/{person,organization,project,product,event,place,other}/` | `entity.{...}` | 具象存在(7 子类) |
| `knowledge/concepts/{theory,method,field,phenomenon,standard,term,other}/` | `concept.{...}` | 抽象知识(7 子类) |
| `knowledge/analyses/` | `analysis` | query 落档专用(带时间戳) |
| `knowledge/comparisons/` | `comparison` | 常驻对照页 |
| `knowledge/syntheses/` | `synthesis` | 常驻综合页 |

**顶层索引 4 件**:`knowledge/index.md`(主目录)/ `overview.md`(大图)/ `glossary.md`(术语表)/ `log.md`(变更日志,ISO 8601,最新在前)。

字段集合与格式细节走 `doc/schema/frontmatter-spec.md` 与 `doc/template/`(PRD 不规定)。

### 6.2 正文链接规则

- 关键名词首次出现时添加 `[[wikilink]]`,避免重复链接
- wikilink 使用裸文件名或目标页 `aliases` 中的别名
- 不增加 `links:` frontmatter 字段(对齐 OKF §5)
- 标准 markdown 链接降级兼容;`--fix` 转 wikilink

### 6.3 文档权威关系

- `doc/schema/frontmatter-spec.md` —— frontmatter 字段规范(人读权威)
- `doc/schema/frontmatter.schema.json` —— 机器读,跟随 spec 对齐
- 用户工程 `schema/schema.md` —— Agent 执行工作流入口

---

## 7. 验收标准

### 7.1 功能验收

- [ ] AC-1:`init` 5 分钟内得到完整目录;`schema/schema.md` 覆盖 ingest/query/lint
- [ ] AC-2:ingest `raw/okf-spec.md` → ≥ 5 个 OKF 兼容概念页;`index.md` 反映新增
- [ ] AC-3:`query` 回答含 wiki 链接,**不编造**未覆盖内容
- [ ] AC-4:`lint` 能识别孤儿 / 过期 / frontmatter 不合规
- [ ] AC-5:任意 wiki 页 frontmatter 通过 OKF v0.2 校验脚本(自动测试)
- [ ] AC-6:`ingest` 未拍板前 inbox 文件不动;拍板后 → `raw/{subdir}/` + `inbox/{file}` 删除 + `log.md` 留痕
- [ ] AC-7:目标目录不存在 → 经用户拍板才能创建和迁移
- [ ] AC-8:`inbox/` 为空 → 提示信息,**退出码 0**
- [ ] AC-9(G10,原生优先):丢 `inbox/iso26262.pdf` → SKILL.md 在步骤 0 探测 Claude Code 原生 PDF reader 可用性,**(a)/(b) 二选一验收,不强制锁死 anydoc**(对齐 design.md §3.2 + §7.2 绝不"为保险先生成副本"):
   - (a) **原生可读**:文件直迁 `raw/06_功能安全/iso26262.pdf`,**不生成** `.converted.md`;frontmatter `format: pdf` + `converter: claude-native` + `native_text: true` + `converted_path: null`;正文 `> 原始来源:` 指向原文件
   - (b) **原生失败**(双栏 / 扫描 / 加密 / 表格错位等):回退路径 3 → `raw/06_功能安全/iso26262.pdf` + `.converted.md` **同时存在**;frontmatter `format: pdf` + `converter: anydoc` + `native_text: false` + `converted_path: raw/06_功能安全/iso26262.pdf.converted.md`;正文 `> 原始来源:` 指向 md 副本
- [ ] AC-10(G10):丢 `inbox/notes.md`(纯文本) → `raw/{subdir}/notes.md` 存在,**不**生成 `.converted.md`;frontmatter `format: md` + `converter: null` + `native_text: true` + `converted_path: null`;正文 `> 原始来源:` 指向原文件
- [ ] AC-11(G11 M1):query 触发落档 → `analyses/{timestamp}-{slug}.md` 含**分析 3 节骨架**(`## 方案推演 / 架构分析` + `## 关联溯源` + `## 总结:最有收获的一句话`);**不含** `## 重点摘录` / `## 我的思考` / `## 摘要` / `## Summary`;lint C4 FAIL
- [ ] AC-12(G11 M2):analysis `sources_used` 每条解析到真实 `knowledge/**/*.md`,否则 FAIL(C7);`## 关联溯源` 末行 `> 引用:` 与 `sources_used` Set 比对,不一致 WARN(C8);`--fix` 重写不动 `updated` + mtime(Q7)
- [ ] AC-13(G11 M3):gating e2e:Exact 无 prompt;Overview / Comparison 必有 prompt
- [ ] AC-14(Related Pages source → entity/concept):source 页 `## 相关页面(Related Pages)` 固定含 `### Entities` + `### Concepts` 子标题;每次 ingest 完全重建,人工条目不保留;某组空仅删该子标题,全空删整节
- [ ] AC-15(Related Pages 双向反链):entity / concept 页 `## 来源资料` 小节按 source `title` 排序;完全重建,人工条目不保留;无 source 引用删整节;Obsidian 反链面板可见
- [ ] AC-16(docling 抽图回归):PPTX / DOCX / XLSX 走 docling → `<basename>.converted.md` 与 `<basename>.converted_media/` 同目录,所有 `![](image_NN.png)` resolve;lint 校验副本图片链接,否则 WARN

### 7.2 非功能验收

- [ ] NFR-1:不引入 MCP / CLI daemon / RAG / embedding;**唯一例外**:qmd(N≥1000 强依赖)
- [ ] NFR-2:plugin 代码 / 文档 / 测试 / schema 各居其位(模块化)
- [ ] NFR-3:中文为主,术语保留英文(如 `type: source` 不翻译)
- [ ] NFR-4:无绝对路径
- [ ] NFR-5:临时文件进 `temp/`
- [ ] NFR-6:LICENSE = Apache 2.0
- [ ] NFR-7:`scripts/package.json` 写 Node 依赖(`@firecrawl/anydoc` 强依赖;Node 版 PaddleOCR 可选;qmd 单独探查不计入);SKILL.md 跑前校验,按页数 / 文件类型降级或 FAIL

### 7.3 兼容性验收

- [ ] COMPAT-1:OKF reader 安全消费所有 frontmatter;plugin 扩展字段按未知忽略;**不发明 `links:`**;`[[wikilink]]` 在 OKF reader 视为正文文本
- [ ] COMPAT-2:Karpathy 风格 wiki 直接搬入可被 lint 识别(允许 `type` 缺省并提示)
- [ ] COMPAT-3:`schema/schema.md` zero-shot 可执行

## 8. 风险 / 取舍

| 风险                                                   | 影响                                 | 缓解                                                                                 |
| ------------------------------------------------------ | ------------------------------------ | ------------------------------------------------------------------------------------ |
| OKF v0.x 演进,字段变化                                 | 扩展字段将来要适配                   | 只锁 v0.2 已定义字段,扩展字段显式标注 plugin 扩展,OKF 工具忽略                       |
| LLM 跑偏(漏抽 / 错判 entity vs concept / 错选 14 子类) | wiki 质量下降                        | lint 兜底识别目录名 ↔ type 不一致;`concept-entities-spec.md` 给判定示例           |
| 老格式`.ppt/.doc/.xls`                               | docling 不支持,路径 3 失败           | 路径 0 LibreOffice headless 预归一化;未装 → 提示用户                                |
| 比较 / 综合页噪声                                      | `comparisons/` `syntheses/` 膨胀 | 必须用户拍板;`sources_count` 最小门槛 C6                                           |
| `sources_used` 填写过宽                              | 引用列表污染                         | C7 + C8 严格校验;`--fix` 不动 updated + mtime(Q7)                                  |
| 老文件 / 二进制无法解析                                | query 失败                           | source 页`## 重点摘录` + `converted_path`;query 通过 `converted_path` 直读副本 |
| `knowledge/` 与 git 仓污染                           | 用户误提交                           | README 建议`.gitignore` `knowledge/`;plugin 不强制 git 操作                      |
| 降级路径 3/4 静默发生                                  | 用户不知情                           | C19 校验降级日志必出                                                                 |

## 9. 里程碑

- **当前**:PRD v0.4.0 已冻结(2026-09-06);design.md v0.1.0 已冻结
- **下一步**:`implement.md`(M2)→ 测试用例(M3)→ 代码(M4)→ 自测(M5)→ 上 GitHub(M6,暂不配 marketplace)

---

## 10. 参考

见 [design.md §9](./design.md)。

---

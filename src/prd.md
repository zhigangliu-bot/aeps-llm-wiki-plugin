# aeps-llm-wiki-plugin — PRD

> **状态**:v0.1 已冻结(2026-09-02)
> **创建日期**:2026-09-01
> **作者**:zhigang.liu
> **范围**:仅本文档;具体 skill 接口、frontmatter schema、数据流等在 `design.md`

---

## Change History

> 设计文档冻结前的中间日志、测试用例、变更记录都不进文档;统一在本节汇总。冻结后新增变更以追加方式记录。

| 日期 | 版本 | 变更 | 关联 commit |
|---|---|---|---|
| 2026-09-01 | v0.1 草稿 | 初始创建:8 目标 + 7 用户故事 + 6 功能需求 + NFR + Q1-Q5 开放问题 | (历史) |
| 2026-09-02 | v0.1 | **§4.1 init 同步策略表** 扩展到 9 行(raw/README.md / templates/concept-entities-readme.md / templates/tag-template.md),prd/design 镜像同步 | 设计会话内 |
| 2026-09-02 | v0.1 | **§4.2 ingest** 触发简化:移除 `--into <type>` / `--as <page-name>` / `<path>` 三个参数(无参数,自动扫 inbox/);文件读取走统一 `scripts/convert-to-md.mjs`,按扩展名 4 类分流(md/txt/... 直接读 / pptx/docx/xlsx/pdf Claude converter 失败降级 anydoc / png/jpg/jpeg/bmp/tiff paddleocr / 其他 FAIL) | 设计会话内 |
| 2026-09-02 | v0.1 | **§4.3 query** 4 跳扫描(index → 候选 → wikilink 邻居 → glossary/log)+ qmd 阈值分流(< 500 纯 index / 500-1000 优先 qmd / ≥ 1000 必须 qmd);新增 NFR-1 qmd 为可选依赖例外 | 设计会话内 |
| 2026-09-02 | v0.1 | **§4.4 lint --fix** 按问题级别分流:**确定性结构修复**(frontmatter / 3 节骨架 / `## 摘要` 残留)直接 patch 应用 + log.md 追加 `**LintFix**`;**语义级问题**(矛盾 / 命名飘合并 / 漏链 / 陈旧处理)仅出提案,等用户确认 | 设计会话内 |
| 2026-09-02 | v0.1 | **Q1**:权威顺序 = OKF 规范 > `schema/frontmatter.schema.yaml` > `knowledge/SCHEMA.md` | `afa40fa` |
| 2026-09-02 | v0.1 | **Q2**:query 不加 `--no-save` 参数 | 设计会话内 |
| 2026-09-02 | v0.1 | **Q3**:`--fix` 模式按问题级别分流(详见 §4.4) | 设计会话内 |
| 2026-09-02 | v0.1 | **Q4**:`raw-readme.md` 全量 15 类边界规则 + `inbox-readme.md` 简版提示 | 设计会话内 |
| 2026-09-02 | v0.1 | **Q5**:inbox → raw 命名飘检查前移到 ingest 提议时(LLM 先比 raw/ 已有子目录,命中相似目录强制改用已有目录) | `316a66b` |
| 2026-09-02 | v0.1 | **Q6**:`[[wikilink]]` 升为一等公民(Obsidian 原生双链 + Karpathy 老 wiki 兼容);OKF 兼容靠 frontmatter `links:` 字段镜像 | `c726a96` |
| 2026-09-02 | v0.1 | **§1 背景**:加第三条范式 "Obsidian 作为 LLM-wiki 前端",列 4 条具体约束(链接 / tag / 目录 / 双链图谱) | `8cbfb33` |
| 2026-09-02 | v0.1 | **目标用户**:改 "汽车电子软件工程师、架构师 + Claude Code + Obsidian"(去掉具体人名) | `136cee1` |
| 2026-09-02 | v0.1 | **冻结**:本版本 v0.1 已冻结,后续变更追加在 Change History 表,新章节另起 | 本 commit |

---

## 1. 背景

LLM 时代做个人 / 团队知识沉淀,有两个互补的范式 + 一个不可绕开的前端:

1. **Andrej Karpathy 的 LLM Wiki 模式** —— LLM 读源一次,产出持久、累积、互相链接的 markdown wiki,人做策展。代表实现:`balukosuri/llm-wiki-karpathy`,核心是 `CLAUDE.md` 作为 Agent 操作手册 + `wiki/` + `raw/` 两层结构 + `index.md` / `log.md` 双索引。
2. **Google Cloud 的 Open Knowledge Format(OKF)** —— 把"LLM-wiki pattern"形式化成一个厂商中立、零运行时的开放规范。`markdown + YAML frontmatter`,**唯一必填字段 `type`**,OKF 工具链可直接消费。
3. **Obsidian 作为 LLM-wiki 的前端** —— Obsidian 是当前最成熟的本地 markdown 知识库 UI(`vault/` + 双链 `[[wikilink]]` + tag 面板 + 反向链接图谱),plugin 生成的 `knowledge/` 必须能直接被 Obsidian 打开使用,无需任何格式转换。具体约束:
   - **链接必须 Obsidian 原生可跳**:`[[page]]` / `[[page|显示文本]]` / `[[page#章节]]` 一等公民(Q6),不要强行只写标准 markdown 链接
   - **tag 必须 Obsidian 原生可识别**:frontmatter `tags:` 走 YAML list,Obsidian 自动扫到 tag 面板;六轴受控词表与 Obsidian tag 体系并存(`#domain/autosar` 这种 hierarchical tag 也兼容)
   - **目录结构 Obsidian 直读**:`knowledge/{entities,concepts,sources,...}/` 即 vault 子文件夹,无需任何映射层
   - **双链图谱即反向链接图谱**:Obsidian 自动生成的反向链接面板 = plugin 第 3 跳扫描的"邻居页"佐证

`aeps-llm-wiki-plugin` 把这三个范式整合成一个**Claude Code plugin**,让用户用一个 `/aeps-llm-wiki-init` 就在自己的研究 / 学习 / 笔记项目里跑起来,产出**OKF 兼容的、Karpathy 启发的、Obsidian 直读的**知识库。LLM 写,人用 Obsidian 读,plugin 管一致性。

**目标用户**:汽车电子软件工程师、架构师,用 Claude Code + Obsidian 做内部研究 / 知识沉淀 / 学习笔记等长期知识管理的人。

---

## 2. 目标 / 非目标

### 2.1 目标(必须达成)

- **G1**:用户 install plugin + 跑一次 `/aeps-llm-wiki-init`,**5 分钟内**得到一个可用的 OKF 知识库目录,无需手动建文件、写 schema。
- **G2**:用户在 `inbox/` 放一份资料,跑 `/aeps-llm-wiki-ingest`(无参数,自动扫 inbox/),**由 LLM 生成**对应的 OKF 概念页,并自动维护 `index.md`、`log.md`、`glossary.md`。
- **G3**:用户用 `/aeps-llm-wiki-query <question>`,plugin 帮用户**从 `knowledge/` 里找答案 + 引用**,并询问是否把回答落档为 `analysis` 页。
- **G4**:plugin 生成的 wiki **严格兼容 OKF v0.2** —— 任何 OKF 工具(Knowledge Catalog、其他 agent 的 reader)能直接消费。
- **G5**:plugin 的所有 skill 前缀统一为 `aeps-llm-wiki-`(防命名空间冲突)。
- **G6**:`plugin **不自带常驻运行时**(无 Python CLI daemon、无 MCP server、无 RAG/embedding 服务)—— 纯规范 + skill + 单次运行的 scripts + 事件回调 hooks。允许 hooks(plugin 本体 `hooks/hooks.json`,事件回调同步跑完即退,不开监听);scripts 与 hooks 都遵循"agent 调一次就跑完退"原则。
- **G7**:用户把资料丢进 `inbox/`(暂存入口,**唯一入口**),跑 `/aeps-llm-wiki-ingest`(无参数,自动扫 inbox/),**LLM 提议 raw/ 子目录分类 + 用户拍板**后,文件迁移到 `raw/<subdir>/`,inbox 清空。统一为 `inbox/` 入口;raw/ 是已归档的不可变层。
- **G8**:用户跑 `/aeps-llm-wiki-synthesize <topic>`,plugin 帮用户在 `knowledge/syntheses/` 写一份**常驻综合页**(`type: synthesis`,不带时间戳),引用 wiki 里所有与 `<topic>` 相关的页(Karpathy line 31 "synthesis")。
- **G9**:plugin 在 ingest 多份同类 entity 或 query 累计"X vs Y"高频时,**主动提议**建 `knowledge/comparisons/<a>-vs-<b>.md` 常驻对照页(Karpathy line 31 "comparisons"),由用户拍板才建。

### 2.2 非目标(明确不做)

- ❌ **不**带版本 / 基线 / 变体管理字段 —— 目标用户做的是内部研究,不是项目交付,基线无意义。如果将来需要,在 `schema/frontmatter.schema.yaml` 加 3 行。
- ❌ **不**做 RAG / 向量搜索 / embedding —— 由 OKF 生态或用户自选 qmd 等工具承担。
- ❌ **不**做自动监控文件变动 —— 用户主动 say "ingest",符合 Karpathy 哲学。
- ❌ **不**做 Claude Code plugin 之外的兼容(Codex/Cursor 等)—— 其它 Agent 用户手动读 `schema/aeps-llm-wiki.schema.md` 也能用,但不在本 plugin 维护范围。
- ❌ **不**内置 marketplace 配置(等 plugin 稳定后再说,见 [MEMORY: aeps-llm-wiki marketplace 待办](../../../../../../../../../../../../Users/ThinkPad/.claude/projects/f--llm-wiki/memory/aeps-llm-wiki-marketplace-reminder.md))。

---

## 3. 用户故事

| ID   | 角色          | 场景                                           | 期望                                                                                      |
| ---- | ------------- | ---------------------------------------------- | ----------------------------------------------------------------------------------------- |
| US-1 | 研究者        | 想在新项目里开 wiki                            | 跑一次 init 就得到可用结构,不用手动建 7 个文件                                            |
| US-2 | 研究者        | 把刚下载的 OKF spec 放到`inbox/`             | ingest 后`knowledge/concepts/open-knowledge-format.md` 自动出现,`index.md` 自动更新   |
| US-3 | 学习者        | 读 wiki 时想确认某概念是否被覆盖               | query 给出**带 wiki 引用的**回答,并问要不要落档                                     |
| US-4 | 长期用户      | wiki 长到 50+ 页,担心维护成本                  | lint 报告孤儿页、矛盾、过期;`--fix` 模式**只自动应用确定性结构修复**(frontmatter / 3 节骨架 / `## 摘要` 残留),**语义级问题**(矛盾 / 命名飘合并 / 漏链 / 陈旧处理)仍出提案等用户确认 |
| US-5 | 好奇者        | 在 OKF Knowledge Catalog 里发现一个别人的 wiki | 能直接导入到本地(因为我们输出严格 OKF)                                                    |
| US-6 | plugin 维护者 | 想加新实体类型"法规"或"标准"                   | 改`schema/frontmatter.schema.yaml` + 一行 skill 配置,不用改 plugin 主代码               |
| US-7 | 研究者        | 拿到一份资料但还没决定归档到 raw/ 哪个分类     | 丢`inbox/`,ingest 时 LLM 提议子目录(如`raw/okf/`),用户一句"好"或改后确认,文件自动迁移 |

---

## 4. 功能需求

### 4.1 Init skill

- **触发**:`/aeps-llm-wiki-init`(首次启用或已存在项目再次启用,后者走"幂等再入",见下方)
- **目录名约定**(硬约束,无参数):`inbox/` `raw/` `scripts/` `templates/` `knowledge/` 五个顶层目录名**全部固定默认**,init 不接受 `--xxx-dir` 之类的目录名参数;子目录名见 §6.1
- **必须**(首次启用,**全栈建好**):
  1. **创建 `<project>/inbox/`**:放 `README.md`(从 `templates/inbox-readme.md`) + `.gitkeep`
  2. **创建 `<project>/raw/`**:放 `README.md`(从 `templates/raw-readme.md`) + `.gitkeep`;**预建 15 类子目录,每个放 `.gitkeep`**
  3. **创建 `<project>/scripts/`**:从 plugin 本体 `scripts/` 目录下**所有文件**拷贝过去(具体文件清单由实现侧按目录扫描决定,不写入本文档)
  4. **创建 `<project>/templates/`**:从 plugin 本体 `templates/` 拷贝 4 份页生成模板(`source-page.md` / `analysis-page.md` / `entity-page.md` / `concept-page.md`)+ **2 份全栈字典**(`concept-entities-readme.md` / `tag-template.md`)
  5. **创建 `<project>/knowledge/`**:
     - `SCHEMA.md`(从 `templates/knowledge-SCHEMA.md`,**替换 plugin 内部占位符**:`{{plugin_version}}` / `{{init_at}}` / actor 字符串等;**不**替换目录名,因为目录名固定)
     - `index.md` + `overview.md` + `glossary.md` + `log.md`(从对应模板)
     - **预建 17 个子目录**(`sources/` + `entities/{person,organization,project,product,event,place,other}/` + `concepts/{theory,method,field,phenomenon,standard,term,other}/` + `analyses/` + `comparisons/` + `syntheses/`),**每个叶子目录放 `.gitkeep`**
- **必须**(已存在项目再次启用,**幂等再入**):
  - **不静默覆盖**任何用户本地新增/修改/删除的内容
  - 字典 sync(3 份):用户项目里**没有** → 直接复制;**新增章节/条目** → append 到对应 H2 末尾;**用户已删** → 不补回,lint 提示"plugin 新版有 X 条本地无,要不要采纳?"
  - 目录 sync:用户项目里**缺失**的 15 raw 类 / 17 knowledge 子类 → **补建 + .gitkeep**;plugin 新版**新增的**(用户项目里没有) → **不建**(留给 ingest 拍板门)
  - scripts/ 与 templates/ sync 策略详见 design §2.4 / §2.5
  - 文件 sync(完整表;字典 sync 细则按上方独立条目):
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
  - 结束向用户报告 sync 摘要(append 条数、覆盖文件列表、补建目录列表)
- **不应**:覆盖已存在的 `knowledge/` 用户内容;若检测到非空 `knowledge/`,走"幂等再入"分支,**不**警告阻止

### 4.2 Ingest skill

- **触发**:`/aeps-llm-wiki-ingest`(无参数,递归扫描当前工程 `inbox/` 全部文件;raw 子目录 LLM 自动提议,新页路径 / slug 按 SCHEMA.md 自动生成)
- **入口**:**仅 `<project>/inbox/`**(递归扫描子目录,G7)
  - inbox 文件读完 + 用户拍板分类后**迁移**到 `raw/<subdir>/`,`inbox/<file>` 删除(inbox 子目录里的文件也按相同逻辑:LLM 提议 raw 子目录分类、拍板、迁移)
  - raw/ 不被扫描(G7)—— raw 是已归档的不可变层,调整走 `git mv` 或手工
- **不应**:扫描 `raw/` 下的文件(用户想调整 raw 归档 → `git mv`)
- **子命令 `--raw-subdir=<name>`**:跳过分类交互,强制把 inbox 文件迁到 `raw/<name>/`(LLM 不再提议)。**仅 inbox 非空时生效**(详见 design §5.1)
- **必须**(文件读取策略,详见 design §4.2):
  - `.md` / `.markdown` / `.rst` / `.txt` / `.csv` / `.json` / `.yaml` / `.yml` / `.xml` / `.html` / `.htm` —— **直接读**(纯文本)
  - `.pptx` / `.docx` / `.xlsx` / `.pdf` —— 先试 Claude 内置 converter,**失败后降级 anydoc 转 markdown**
  - `.png` / `.jpg` / `.jpeg` / `.bmp` / `.tiff` —— **paddleocr 转 md**(OCR)
  - 转换失败的 → **FAIL**,提示"无法转换 <file></file>,请手动预处理"
  - 转换入口:**统一 `scripts/convert-to-md.mjs`**,按扩展名分流(详见 design §4.2 / §2.4)
  - 依赖库清单:`scripts/requirements.txt`(anydoc / paddleocr 等 Python 依赖),**用户必须装**;未装 → 提示并退出
- **必须**(分类 + 写入):
  - **路径来自 `inbox/`**:LLM 先**提议**一个 raw 子目录分类 + 短理由
    - **命名飘检查**(Q5,前移自 lint):LLM 提议的子目录名,先与 `raw/` 下已有子目录做相似度比较(Levenshtein ≤ 2 / 前缀差异 / 同义拼写,详见 design §4.4)
      - 命中已有相似目录 → **强制改用已有目录**(LLM 必须解释归并理由,用户拍板通过后直接 mv)
      - 未命中 → 进入下面"拍板门分流"
    - **拍板门分流**:
      - 目标目录已存在(init 预建的 15 类或二级已有目录)→ **无需拍板**,直接 mv
      - 目标目录不存在(字典外的自定义目录、LLM 判定的二级子目录)→ **必须人工拍板**才创建 + mv
    - **绝不静默创建未存在的目录**
  - 与用户做要点确认(不阻塞,可一句"继续"跳过)
  - 生成 `type: source` 的源页,放在 `knowledge/sources/<basename>.md`(正文 **3 节骨架硬约束**:`## 重点摘录` / `## 我的思考` / `## 总结:最有收获的一句话`,**任何缺失 = lint FAIL**;**禁止**含 `## 摘要` 小节,长摘要走 frontmatter `summary` 字段;详见 design §3.1 §C)
  - 抽取实体 / 概念 / 术语,**自动**生成对应子页:
    - 具象存在 → `knowledge/entities/<子类>/<slug>.md`,`type` 取子类值(`person` / `organization` / `project` / `product` / `event` / `place` / `other`)
    - 抽象知识 → `knowledge/concepts/<子类>/<slug>.md`,`type` 取子类值(`theory` / `method` / `field` / `phenomenon` / `standard` / `term` / `other`)
    - **子类 ↔ 目录 1:1 绑死**(详见 `concept_entities_template.md` 与 `SCHEMA.md`)
    - **正文自由发挥**,不强制小节
  - 追加 `knowledge/log.md`(本次迁移也要留痕)
  - 更新 `knowledge/index.md`(新增条目)
  - 更新 `knowledge/glossary.md`(新增 / 修改术语)
  - 视情况更新 `knowledge/overview.md`(大图变化时)
- **必须遵循**:frontmatter 严格符合 `schema/frontmatter.schema.yaml`
- **必须遵循**:OKF v0.2 兼容性 —— type 必填,所有 frontmatter 字段 OKF 工具可读
- **不应**:未经用户拍板就把 inbox 文件迁到**未存在的目录**(创建新目录必须拍板;已存在目录无需拍板,直接放)

### 4.3 Query skill

- **触发**:`/aeps-llm-wiki-query <question>`
- **必须**(4 跳扫描,详见 design §4.3):
  - **第 1 跳**:`knowledge/index.md` 找候选页;按 `tags` 关键词做第一轮过滤(条目 frontmatter 的 tag 与 query 关键词重合数,top-K 入选)
  - **第 2 跳**:读候选页(优先级:`description` / `summary` → `title` → 全文)
  - **第 3 跳**:顺着候选页内的 `[[wikilink]]` / `Related pages` 段跳到相邻 `entities/` `concepts/` `analyses/` `comparisons/` 页(1 跳深度,避免雪崩)
  - **第 4 跳**:读 `glossary.md`(query 关键词消歧)+ `log.md` 近期 10 条(检查是否近期 ingest 了相关源没消化)
- **必须**(本地搜索引擎 qmd 分流,详见 design §4.3):
  - **< 500 页**:纯 `index.md` + 4 跳扫描,**不**调 qmd
  - **500~1000 页**:**优先 qmd**(`qmd query "<question>"`);未装 → 提示用户装,降级走 `index.md`
  - **> 1000 页**:**必须 qmd**;未装 → **报错**(提示"wiki 已超 1000 页,请装 qmd 后再 query"),不进入回答
  - 阈值常量:`QUERY_INDEX_THRESHOLD = 500`、`QUERY_QMD_REQUIRED_THRESHOLD = 1000`(详见 design §4.3)
  - 探查入口:`scripts/check-qmd.mjs`(单次脚本,跑 `qmd --version` 探查可用性)
- **必须**:
  - 回答,**每条断言附 wiki 标准 markdown 链接**
  - 回答结束后**问用户是否落档** —— 落档则新建 `type: analysis` 页,放在 `knowledge/analyses/<时间戳>-<slug>.md`(正文 **3 节骨架硬约束**:`## 重点摘录` / `## 我的思考` / `## 总结:最有收获的一句话`,与 `sources/` 同约束;**禁止**含 `## 摘要` 小节,query 原问句必须保留在 frontmatter `summary` 字段首行 `**问题**: ...`;详见 design §3.1 §C),追加 log
- **不应**:编造 wiki 里没有的内容(必须诚实说"我读到的 wiki 里没有覆盖这点")

### 4.4 Lint skill

- **触发**:`/aeps-llm-wiki-lint [--fix]`
- **必须**:
  - 扫所有 `knowledge/**/*.md` 文件
  - 报告:
    - **孤儿页**:无出入链接的页
    - **矛盾**:两个页对同一事实说法不同(LLM 判断)
    - **陈旧页**:`stale_after` 优先;`updated > 180 天` 回退(详见 design §4.4);`status: deprecated` 豁免
    - **LLM 命名飘**:相似子目录/页面名检测(Levenshtein ≤ 2 / 前缀差异 / 同义拼写),不自动合并,仅 prompt + 用户拍板(详见 design §4.4)
    - **漏链**:某 page 里反复出现但链接缺失的术语
    - **frontmatter 不合规**:必填字段缺失 / 类型错位
    - **正文骨架不合规**:`sources/*.md` 和 `analyses/*.md` 必含 3 节 H2(`## 重点摘录`、`## 我的思考`、`## 总结:最有收获的一句话`),缺一即 FAIL;**禁止**含 `## 摘要` / `## Summary` H2(详见 design §3.1 §C)
    - **`comparisons/*.md` 不合规**:`type` 必须是 `comparison` + 必须含 `sources:` 字段(否则 FAIL)
    - **`syntheses/*.md` 不合规**:`type` 必须是 `synthesis` + `sources_count` < 3 警告(避免空综合)
  - 默认只报告;**`--fix` 模式按问题级别分流**(详见 design §4.4):
    - **确定性结构修复** —— `--fix` 直接 patch 应用(在 `log.md` 追加 `**LintFix**` 条目):
      - frontmatter 字段缺失 → 补占位值 + WARN
      - frontmatter 字段类型错位(如 `tags` 不是 list)→ 强转
      - `## 摘要` / `## Summary` 小节残留 → 删除并保留内容到 frontmatter `summary`
      - sources/analyses 缺 3 节骨架 H2 → 文件末尾追加占位 H2
      - ~~`[[wikilink]]` 残留未替换为标准 markdown 链接~~ —— **wikilink 是一等公民(Q6),不再当残留处理**
    - **语义级问题** —— `--fix` 模式仍只输出**提案**(不应用,等用户确认):
      - 矛盾(两个页对同一事实不同说法)
      - 命名飘合并(子目录/页面名相似)
      - 漏链(正文反复出现但未链接的术语)
      - 陈旧页处理(归档 / `status: deprecated`)
- **不应**:无 `--fix` 时静默修改文件

### 4.5 Synthesize skill(Karpathy line 31 "synthesis")

- **触发**:`/aeps-llm-wiki-synthesize <topic>`
- **必须**:
  - 读 `knowledge/index.md` + 涉及 `<topic>` 的全部页(LLM 决定范围,默认"所有 frontmatter 含 topic 标签或被 tag 关联的页")
  - 写一份 `type: synthesis` 综合页,放 `knowledge/syntheses/<topic-slug>.md`(**不带时间戳,常驻,后续 LLM 可 update**)
  - frontmatter `sources_count`(引用了多少页),便于 lint 评估成熟度
  - 追加 `knowledge/log.md`
  - 更新 `knowledge/index.md`(新增条目)
- **不应**:写一次性"当时综合"(那是 `analysis`,不是 `synthesis`)

### 4.6 Comparison 自然触发规则(Karpathy line 31 "comparisons")

不增加 skill,**由 query skill 内置两条触发路径**:

- **路径 A — 同类 entity 触发**:ingest 完成后,LLM 在 source 页落档询问时,如果发现 `entities/<子类>/` 下已有同类 entity(同一 type)≥ 2 个且都是这次新 ingest 的相关对象,**提议**:"要不要建一个常驻 comparison 页把它们对照一下?"
- **路径 B — 高频检索触发**:query 累计发现用户 ≥ 3 次问"X vs Y"型问题(grep `log.md` 检测模式 `**Action**: ... query ... X.*Y`),**下次落档询问时只提一次**:"X vs Y 这个对比提过几次了,要不要建一个常驻 comparison 页?"
- **命名**:`knowledge/comparisons/<a>-vs-<b>.md`(**不带时间戳**,常驻)
- **frontmatter**:`type: comparison` + `sources:` 字段链接到对比的 entity/concept 页
- **不应**:query 一次性给完对比表就结束(那是 answer,不是 comparison);comparison 是**常驻页**,由用户拍板后才建

---

## 6. 数据契约(高层,细节在 design.md)

### 6.1 知识库目录结构(默认)

```
<user-project>/
├── inbox/                             # 暂存入口(G7):用户丢新资料,ingest 时 LLM 提议分类 + 用户拍板后迁移到 raw/
│   └── .gitkeep
├── raw/                              # 已分类归档(不可变)。init 时按 templates/raw-readme.md 预建 15 类子目录,每个用 .gitkeep 占位
│   ├── raw-readme.md                  # 字典副本(15 类 + 边界规则)
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
├── scripts/                          # plugin 维护的单次运行脚本(Node 18+,.mjs),init 时从 plugin 拷贝到此(具体文件由实现侧按目录扫描决定,本文档不列举)
├── templates/                        # scripts 生成文件时读的"页模板源",init 时拷过来;其他字典/操作手册仍按分散落位策略
│   ├── source-page.md                # sources/ 页生成模板
│   ├── analysis-page.md              # analyses/ 页生成模板
│   ├── entity-page.md                # entities/<子类>/ 页生成模板
│   └── concept-page.md               # concepts/<子类>/ 页生成模板
└── knowledge/                        # LLM 维护的知识层
    ├── SCHEMA.md                     # Agent 操作手册(plugin 写的)
    ├── index.md                      # 主目录
    ├── overview.md                   # 大图
    ├── glossary.md                   # 术语表
    ├── log.md                        # 变更日志(ISO 8601,最新在前,内容详见 design)
    ├── sources/                      # type: source(1:1 绑死,原件归档)
    │   └── .gitkeep
    ├── entities/                     # 具象存在:人/事/物/组织/产品/地点/兜底
    │   ├── person/.gitkeep           # type: person
    │   ├── organization/.gitkeep     # type: organization
    │   ├── project/.gitkeep          # type: project
    │   ├── product/.gitkeep          # type: product
    │   ├── event/.gitkeep            # type: event
    │   ├── place/.gitkeep            # type: place
    │   └── other/.gitkeep            # type: other(兜底)
    ├── concepts/                     # 抽象知识:理论/方法/领域/现象/标准/术语/兜底
    │   ├── theory/.gitkeep           # type: theory
    │   ├── method/.gitkeep           # type: method
    │   ├── field/.gitkeep            # type: field
    │   ├── phenomenon/.gitkeep       # type: phenomenon
    │   ├── standard/.gitkeep         # type: standard
    │   ├── term/.gitkeep             # type: term
    │   └── other/.gitkeep            # type: other(兜底)
    ├── analyses/                     # type: analysis(1:1 绑死,query 落档专用)
    │   └── .gitkeep
    ├── comparisons/                  # type: comparison,常驻对照页(Karpathy line 31,LLM 主动提议)
    │   └── .gitkeep
    └── syntheses/                    # type: synthesis,常驻综合页(Karpathy line 31,/aeps-llm-wiki-synthesize 显式触发)
        └── .gitkeep
```

**frontmatter、链接、log.md 格式等具体契约详见 `design.md`**;PRD 不规定字段集合或格式细节。

---

## 7. 验收标准

## 7. 验收标准

### 7.1 功能验收

- [ ] AC-1:用户 install plugin + `/aeps-llm-wiki-init`,5 分钟内得到完整目录;`SCHEMA.md` 内容可读、覆盖 ingest/query/lint 三个工作流
- [ ] AC-2:把 `raw/okf-spec.md`(已存在的样例)做 ingest,产出 ≥ 5 个 OKF 兼容的概念页,且 `index.md` 反映新增
- [ ] AC-3:`/aeps-llm-wiki-query "OKF 必填字段是哪个"`,回答含 wiki 链接,且**不编造 wiki 里没有的内容**
- [ ] AC-4:`/aeps-llm-wiki-lint` 能正确识别孤儿页、过期页、frontmatter 不合规页
- [ ] AC-5:**生成的任意 wiki 页 frontmatter 都能被 OKF v0.2 校验脚本通过**(自动测试)
- [ ] AC-6:`/aeps-llm-wiki-ingest`(无参数,扫 inbox/):LLM 输出迁移提议,**未拍板前 inbox 文件不动**;用户拍板后文件出现在 `raw/<subdir>/`,`inbox/<file>` 删除,`log.md` 记录迁移路径
- [ ] AC-7:`/aeps-llm-wiki-ingest --raw-subdir=<name>`:跳过分类交互,直接迁到 `raw/<name>/`;`log.md` 仍记迁移路径
- [ ] AC-8:`/aeps-llm-wiki-ingest` 但 `inbox/` 为空:提示"inbox/ 为空,先把资料丢进 inbox 再跑",**不报错**(退出码 0,符合 SKILL 调用语义)

### 7.2 非功能验收

- [ ] NFR-1:plugin 装上后,**不引入**任何 MCP server / CLI / hooks / RAG 依赖(**可选**例外:[qmd](https://github.com/tobi/qmd) —— 仅作为 query skill 在 wiki 规模较大时的本地搜索引擎;用户必须自行 `npm install -g @tobilu/qmd`,plugin 不强制装,详见 §4.3)
- [ ] NFR-2:plugin 本身在 `F:\llm-wiki\aeps-llm-wiki-plugin\src\` 下,代码 / 文档 / 测试 / schema 各居其位(模块化原则)
- [ ] NFR-3:所有文档 / 用户消息 / skill 输出中文为主,术语保持英文(如 `type: source` 不翻译)
- [ ] NFR-4:plugin 不带绝对路径(CLAUDE.md 硬约束)
- [ ] NFR-5:所有临时文件进 `temp/`(CLAUDE.md 硬约束)
- [ ] NFR-6:LICENSE = Apache 2.0(对齐 OKF)
- [ ] NFR-7:**Python / Node 外部依赖清单**写进 `scripts/requirements.txt`(anydoc / paddleocr 强依赖;qmd 可选依赖;**SKILL.md 跑前先校验**,按页面数 / 文件类型走降级或 FAIL,详见 §4.2 / §4.3)

### 7.3 兼容性验收

- [ ] COMPAT-1:`knowledge/` 目录被第三方 OKF reader 读取时,**所有 frontmatter 字段都在 OKF v0.2 已定义字段集合内**(不发明 OKF 之外的必填字段)
- [ ] COMPAT-2:用户把 Karpathy 风格 wiki 直接搬到 `knowledge/`,plugin 的 lint 能识别(允许 `type` 缺省并提示补全)
- [ ] COMPAT-3:`SCHEMA.md` 是人可读的,任意 LLM 读后能在 zero-shot 下正确执行 ingest / query / lint

---

## 8. 风险 / 取舍

| 风险                                                                 | 影响                                                  | 缓解                                                                                                                                                          |
| -------------------------------------------------------------------- | ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| OKF v0.x 仍在演进(v0.2 已发),字段可能变化                            | plugin 锁定的 type 集合将来要适配                     | 只锁定 OKF v0.2 已定义的字段,扩展字段显式标注为 plugin 扩展,OKF 工具可忽略                                                                                    |
| LLM 在 ingest 时跑偏(漏抽 / 错判 entity 还是 concept / 错选 14 子类) | wiki 质量下降                                         | lint skill 兜底,识别"目录名 ↔ type"不一致;SCHEMA.md 给明确子类判定示例                                                                                       |
| `[[wikilink]]` 与标准 markdown 链接混用                            | OKF 工具可能不解析`[[]]`                            | **plugin 以 `[[wikilink]]` 为一等公民**(详见 Q6)——Obsidian 原生可双链跳;OKF 兼容靠 frontmatter `links:` 字段镜像一份标准 markdown 链接列表,OKF reader 读 frontmatter 即可;lint 不再警告 wikilink |
| `knowledge/` 与 git 仓污染                                         | 用户误把生成的 wiki 提交                              | README 明确建议`.gitignore` `knowledge/` 或选择性提交;plugin 不强制 git 操作                                                                              |
| plugin 内部`schema/frontmatter.schema.yaml` 与用户实际 wiki drift  | lint 误报                                             | lint 只读 plugin 的 schema.yaml(权威字段表),不读用户项目;用户项目的`knowledge/SCHEMA.md` 引用同一份 plugin 字段表,不重复列字段                              |
| inbox 文件被 LLM 误迁移到错误目录                                    | 用户资料找不到                                        | 已存在目录(15 类预建)直接放,出错概率低;字典外的创建**必须拍板**;拍板后 log 留完整 `inbox/ → raw/` 路径便于回滚                                       |
| inbox 文件用户拍板后忘了删                                           | 下次 ingest 重复处理                                  | ingest 流程内强制`inbox/<file>` 删除;不是用户操作,是 skill 原子步骤                                                                                         |
| raw 子目录无限增长,LLM 起名飘(15 类之外)                             | 子目录碎片化(`16_公司内部_a`、`16_公司内部_b`...) | init 时 15 类全部预建,日常基本不会触发创建;字典外的创建必须拍板,用户当场就拦下;lint 仍建议合并相似的子目录                                                    |
| comparison 触发逻辑误报(LLM 提议用户不需要的对比页)                  | `comparisons/` 出现噪声                             | 两条触发路径(同类 entity / 高频检索)都只在落档询问时**提议**,用户拍板才建;**只提一次**,后续不再重复                                               |
| synthesis 写得太空(只是简单罗列,没真正"综合")                        | synthesis 页失去价值                                  | frontmatter`sources_count` 字段是"参考多少页"硬指标,sources_count 太低(<3)的 synthesis lint 警告;正文不锁骨架,LLM 自由发挥,但搜索功能可"找引用最广的综合页" |

---

## 9. 里程碑

- **M1 — prd 拍板**(本文档):本轮 review + 确认 ✅ 当前阶段
- **M2 — design.md + implement.md**:本文档确认后,进入设计阶段;具体 skill 接口契约、frontmatter schema 细节
- **M3 — 测试用例**:按 implement.md 拆任务,**先写测试用例**(CLAUDE.md 硬约束),确认后再写代码
- **M4 — 代码**:templates / skills / schema / tests 落地
- **M5 — 自测**:在本地用一个示例 wiki(用 OKF spec 本身做 raw)端到端跑一遍 ingest → query → lint
- **M6 — 上 GitHub**:建 `zhigangliu-bot/aeps-llm-wiki-plugin` 仓库,推 main 分支;**暂不**配 marketplace

---

## 10. 待确认事项(去 design 之前要回答)

- [X] **Q1**:✅ ~~`SKILL.md` / `SCHEMA.md` / `frontmatter.schema.yaml` 哪个作为"权威"~~ —— 已定:**权威顺序**为 OKF 规范 > `schema/frontmatter.schema.yaml` > `knowledge/SCHEMA.md`(`frontmatter.schema.yaml` 机器读字段定义,`SCHEMA.md` 人读入口,SCHEMA.md 不重复列字段而是直接引用 plugin 本体的 `schema/frontmatter.schema.yaml`,详见 [design §3.2 + §5](src/design.md))
- [X] **Q2**:✅ ~~`/aeps-llm-wiki-query` 是不是要支持**纯文本模式**(用户想用 `--no-save` 跳过落档询问)~~ —— 已定:**不加 `--no-save` 参数**,query 永远问"要不要落档",与 ingest / synthesize 行为一致
- [X] **Q3**:✅ `--fix` 模式按问题级别分流 —— 已定:**确定性结构修复**(frontmatter / 3 节骨架 / `## 摘要` 残留)直接 patch 应用,`log.md` 追加 `**LintFix**` 条目;**语义级问题**(矛盾 / 命名飘合并 / 漏链 / 陈旧处理)仅输出提案,等用户确认(详见 §4.4 + design §4.4)
- [X] **Q4**:✅ ~~`raw/` / `inbox/` 要不要各放一个 `README.md` 告诉用户放什么、不放什么~~ —— 已定:`raw-readme.md` 全量放 15 类边界规则(权威文件:plugin 本体 `templates/raw-readme.md`);`inbox-readme.md` 简版提示
- [X] **Q5**:✅ ~~`inbox → raw` 迁移时,LLM 提议的子目录名要不要走 `lint` 风格的"相似合并建议"~~ —— 已定:**需要**,命名飘检查**前移到 ingest 提议时**,LLM 必须先比 raw/ 已有子目录,命中相似目录则强制改用已有目录(详见 §4.2 必须 + design §4.4)
- [X] **Q6**:✅ ~~`[[wikilink]]` 是不是要当"残留"处理?~~ —— 已定:**`[[wikilink]]` 是一等公民**(Obsidian 原生双链 / Karpathy 老 wiki 兼容)。plugin 正文写 `[[page]]` / `[[page|显示]]` / `[[page#章节]]` 形式;OKF 兼容性靠 frontmatter `links:` 字段镜像标准 markdown 链接列表(OKF reader 读 frontmatter 即可);lint **不**再警告 wikilink(详见 §8 风险表对应行 + SCHEMA.md §6 + design §4.4)

---

## 11. 参考

- `input/kapathy-llm-wiki/kapathy-llm-wiki.en.md` —— Karpathy LLM Wiki 理念
- `input/google-OKF/OKF-SPEC.md` —— Open Knowledge Format v0.x 规范
- `input/google-OKF/OKF-README.md` —— Google Cloud 的 OKF 发布说明
- `reference/balukosuri__llm-wiki-karpathy/CLAUDE.md` —— Karpathy 模式的 Agent 操作手册范本
- `reference/balukosuri__llm-wiki-karpathy/README.md` —— Karpathy 模式的 README 结构范本
- `reference/balukosuri__llm-wiki-karpathy/wiki/` —— Karpathy 模式的目录结构范本

---

**下一步**:等本文档 review 通过 → 进入 M2(写 `design.md` + `implement.md`)

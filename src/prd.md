# aeps-llm-wiki-plugin — PRD

> **状态**:v0.5.0 已冻结(2026-09-03);**v0.5.3 PATCH 已就位**(2026-09-03)— Round 13 修复 PRD 缺陷 5(Q7 mtime + atime 双还原)
> **创建日期**:2026-09-01
> **作者**:zhigang.liu
> **范围**:仅本文档;具体 skill 接口、frontmatter schema、数据流等在 `design.md`

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
- **G10**:**外部工具转换的 md 副本随原文件一起入 raw**,源页 link 指向 md 副本(G10 衍生需求,见 §4.2 M1-M4 + design §4.2 + implement §C13):
  - `.pptx` / `.docx` / `.xlsx` / `.pdf` / `.png` / `.jpg` / `.jpeg` / `.bmp` / `.tiff` 经 anydoc / paddleocr / Claude converter 转换后,转换产物 **必须落盘到 raw/**(命名 `<basename>.<ext>.converted.md`),与原文件**同一子目录共存**
  - 源页 `type: source` frontmatter `source_file:` / `sources[].resource` 仍指向**原文件**;`links:` 镜像字段与正文 `[[<basename>.<ext>.converted]]` 指向 **md 副本**(OKF v0.2 §9 `links:` 镜像机制,详见 design §3.6.2)
  - query 阶段 LLM 通过 `links:` 直接读 md 副本,**不再二次跑转换**(原"raw/ 里 .pdf LLM 解析不了"痛点解决)
  - 重转策略:**不重转**(对齐 raw/ 不可变层 + G7 + Q5);需重转时由用户手工 `cp` 回 `inbox/` 走标准 ingest
  - 纯文本类(.md / .markdown / .rst / .txt / .csv / .json / .yaml / .yml / .xml / .html / .htm) **不生成** .converted.md 副本(原生可直接读)
- **G11**:**query skill 落档为 analysis 页时消除 3 个隐患**(G11 衍生需求,见 §4.3 + design §3.6.1 + implement §C15):
  - **结构断层**:`analyses/` **不再复用** `sources/` 的 3 节骨架(原 v0.4.0 复用导致"LLM 推演回答被强行套'重点摘录'"),改用 **analyses 专属骨架**:`## 方案推演 / 架构分析` + `## 关联溯源` + `## 总结:最有收获的一句话`(语义对齐"LLM 综合推演";见 §4.3 + design §3.6.1)
  - **溯源丢失**:`type: analysis` frontmatter **新增必填 `sources_used`**(本次回答参考的 wiki 页相对路径列表,供图跳转 + 后续 lint 校验;C15)
  - **Over-prompting**:**落档询问加 gating**(防 Exact 查证型 spam):仅在跨领域综述 / 对比分析 / 整合 ≥ 2 源 / 深度 ≥ 200 字 触发,Exact / 短答 / 未命中 / Wiki 未覆盖自动跳过

### 2.2 非目标(明确不做)

- ❌ **不**带版本 / 基线 / 变体管理字段 —— 目标用户做的是内部研究,不是项目交付,基线无意义。如果将来需要,在 `schema/frontmatter.schema.yaml` 加 3 行。
- ❌ **不**做 RAG / 向量搜索 / embedding —— 由 OKF 生态或用户自选 qmd 等工具承担。
- ❌ **不**做自动监控文件变动 —— 用户主动 say "ingest",符合 Karpathy 哲学。
- ❌ **不**做 Claude Code plugin 之外的兼容(Codex/Cursor 等)—— 其它 Agent 用户手动读 `schema/aeps-llm-wiki.schema.md` 也能用,但不在本 plugin 维护范围。
- ❌ **不**内置 marketplace 配置(等 plugin 稳定后再说,见 [MEMORY: aeps-llm-wiki marketplace 待办](../../../../../../../../../../../../Users/ThinkPad/.claude/projects/f--llm-wiki/memory/aeps-llm-wiki-marketplace-reminder.md))。

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
- **目录名约定**(硬约束,无参数):`inbox/` `raw/` `scripts/` `templates/` `knowledge/` 五个顶层目录名**全部固定默认**,init 不接受 `--xxx-dir` 之类的目录名参数;子目录名见 §6.1
- **必须**(首次启用,**全栈建好**):
  1. **创建 `<project>/inbox/`**:放 `README.md`(从 `templates/inbox-readme.md`) + `.gitkeep`
  2. **创建 `<project>/raw/`**:放 `README.md`(从 `templates/raw-readme.md`) + `.gitkeep`;**预建 15 类子目录,每个放 `.gitkeep`**
  3. **创建 `<project>/scripts/`**:从 plugin 本体 `scripts/` 目录下**所有文件**拷贝过去(具体文件清单由实现侧按目录扫描决定,不写入本文档)
  4. **创建 `<project>/templates/`**:从 plugin 本体 `templates/` 拷贝 4 份页生成模板(`source-page.md` / `analysis-page.md` / `entity-page.md` / `concept-page.md`)+ **2 份全栈字典**(`concept-entities-readme.md` / `tag-template.md`)
  5. **创建 `<project>/knowledge/`**:
     - `SCHEMA.md`(从 `templates/knowledge-SCHEMA.md`,**替换 plugin 内部占位符**:`{{plugin_version}}` / `{{init_at}}` / actor 字符串等;**不**替换目录名,因为目录名固定)
     - `index.md` + `overview.md` + `glossary.md` + `log.md`(从对应模板)
     - **预建 18 个叶子存储目录**(`sources/` + `entities/{person,organization,project,product,event,place,other}/` + `concepts/{theory,method,field,phenomenon,standard,term,other}/` + `analyses/` + `comparisons/` + `syntheses/`;算术 1+7+7+1+1+1=18,**权威清单详见 design §4.1.1 "knowledge/ 叶子存储目录清单"**),**每个叶子目录放 `.gitkeep`**
- **必须**(已存在项目再次启用,**幂等再入**):
  - **不静默覆盖**任何用户本地新增/修改/删除的内容
  - 字典 sync(3 份):用户项目里**没有** → 直接复制;**新增章节/条目** → append 到对应 H2 末尾;**用户已删** → 不补回,lint 提示"plugin 新版有 X 条本地无,要不要采纳?"
  - 目录 sync:用户项目里**缺失**的 15 raw 类 / 18 knowledge 叶子存储目录 → **补建 + .gitkeep**;plugin 新版**新增的**(用户项目里没有) → **不建**(留给 ingest 拍板门)
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
- **raw/ 已有但无 knowledge 页的场景**:用户历史归档(`cp` 进 raw/ 或 git checkout 旧版)需要补建 → 把文件 `cp` 回 `inbox/` 再走标准 ingest(等价于"先把资料丢 inbox"的标准流),**不**给 plugin 开 raw/ 直接入口(G7 不可变层原则不变)
- **子命令 `--raw-subdir=<name>`**:跳过分类交互,强制把 inbox 文件迁到 `raw/<name>/`(LLM 不再提议)。**仅 inbox 非空时生效**(详见 design §5.1)
- **必须**(文件读取策略,详见 design §4.2):
  - `.md` / `.markdown` / `.rst` / `.txt` / `.csv` / `.json` / `.yaml` / `.yml` / `.xml` / `.html` / `.htm` —— **直接读**(纯文本;**不**生成 .converted.md 副本)
  - `.pptx` / `.docx` / `.xlsx` / `.pdf` —— 先试 Claude 内置 converter,**失败后降级 anydoc 转 markdown**
  - `.png` / `.jpg` / `.jpeg` / `.bmp` / `.tiff` —— **paddleocr 转 md**(OCR)
  - 转换失败的 → **FAIL**,提示"无法转换 <file></file>,请手动预处理"
  - 转换入口:**统一 `scripts/convert-to-md.py`**(Python 3.10+ 单栈),按扩展名分流(详见 design §4.2 / §2.4)
  - 依赖库清单:`scripts/requirements.txt`(anydoc / paddleocr / jsonschema / pyyaml 等 Python 依赖),**用户必须装**;未装 → 提示并退出
- **必须 M1**(G10 — 转换产物落盘到 raw/,详见 design §4.2 step 2 + §4.2.1 阶段 1):
  - 转换成功后,`scripts/convert-to-md.py` 通过 `--emit-to <subdir>` 参数把产物落盘到 `<subdir>/<file>.converted.md`(同 subdir)
  - ingest 阶段 3 `safe-mv.py --apply temp/decision-*.json` 时,**同时迁移两个文件**:`inbox/<file>` → `raw/<subdir>/<file>`(原文件)+ `temp/<file>.converted.md`(或 inbox 内的对应副本)→ `raw/<subdir>/<file>.converted.md`(md 副本)
  - **G10 — 重新 ingest 同名文件的覆盖策略**(v0.5.2 PATCH 修复缺陷 2,G10 派生):
    - **场景**:用户把 `inbox/<file>`(原文件可能已更新 / 转换器升级 / 修正后重转) 再次走标准 ingest,且 `raw/<subdir>/<file>` **已存在**(原文件)+ `raw/<subdir>/<file>.converted.md` **已存在**(md 副本)
    - **行为**:**不报 FileExistsError**,而是**用户拍板 + atomic overwrite**
      - SKILL.md 检测到 raw/ 下已有同名 → **强制拍板询问**(即使是用户主动重 ingest,也要明确告知"raw/ 下已存在同文件,是否覆盖?")
      - 拍板选项:`[y]` 覆盖 / `[n]` 跳过 / `[d]` 仅删除旧副本并跳过 ingest(用户自己手动处理)
      - `safe-mv.py --apply` 收到 `decision.action = "overwrite"` → **atomic overwrite**:**先备份旧文件到 `temp/raw_backup_<hash>/<file>` + `<file>.converted.md`**(Q7 防护,出问题时可回滚),再用 `os.replace()` 一次性替换两个文件
      - **覆盖范围**:仅 `<file>` + `<file>.converted.md` 两个目标,不动同 subdir 其他文件;不动 frontmatter `updated` 字段 + 文件 mtime(对齐 Q7 死循环防护)
    - **不开"重转 skill"**(对齐 v0.4.0 G10 拍板):不提供批量重转历史所有 .converted.md 的入口;用户需批量重转时,自己写脚本 loop 这个流程
  - 纯文本类 **不生成** .converted.md 副本(原生直接读,`native_text: true`)
  - 转换失败 → **不迁原文件,也不生成空副本**(原文件保留在 inbox,等用户预处理)
  - 命名:`<basename>.<ext>.converted.md`(例 `iso26262.pdf.converted.md`),保留原扩展名语义 + 视觉关联
- **必须 M2**(G10 — 源页 frontmatter 增字段,与 OKF v0.2 兼容):
  - `type: source` 源页 frontmatter 在原有 `source_file:` + `sources[]` 双字段基础上,**追加 4 个字段**:

    | 字段 | 类型 | 含义 | 例 |
    |---|---|---|---|
    | `format` | string | 原文件扩展名(OKF 风格,小写) | `pdf` / `pptx` / `docx` / `png` ... |
    | `converter` | string \| null | 实际走过的转换器;`null` 表示纯文本直接读 | `anydoc` / `paddleocr` / `claude-native` / `null` |
    | `native_text` | bool | 是否原生纯文本(决定是否生成 .converted.md) | `false`(走过转换) / `true`(纯文本) |
    | `converted_path` | string \| null | md 副本相对 raw/ 的路径;`null` 表示纯文本(无副本) | `raw/06_功能安全/iso26262.pdf.converted.md` / `null` |

  - `source_file:` 与 `sources[].resource` **仍指原文件**(不变,与 v0.2 Q9 兼容);`converted_path` 与 `links:` 指 md 副本
- **必须 M3**(G10 — `links:` 镜像字段自动同步,详见 design §3.6.2 + §5.4):
  - 源页 frontmatter `links:` **必须**包含 `[[<basename>.<ext>.converted]]`(经转换的)或 `[[<basename>]]`(纯文本)
  - 正文 `## 重点摘录` 末尾加一行 `> 原始来源:[[<basename>.<ext>.converted]]`(纯文本则 `[[<basename>]]`)
  - `scripts/okf-lint.py` 在每次 ingest/lint 时校验 frontmatter `links:` 与正文 wikilink 一致(沿用 v0.2 Q6 + Q7 死循环防护机制)
- **必须 M4**(G10 — `convert-to-md.py` 行为变更):
  - `--batch temp/inbox-batch.json --emit-to temp/` —— 批量模式 + 把产物落到 temp/(供后续 mv 到 raw/)
  - 单文件模式保留现有"stdout 输出 md 文本"行为(不变)
  - SKILL.md 调用顺序固定 3 步:**Step 1 转换产物落 temp/** → **Step 2 拍板门(LLM 对话层)** → **Step 3 `safe-mv.py --apply` 同时 mv 原文件 + md 副本**
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
- **不应**(G10 — 外部转换副本相关):
  - ❌ 不为纯文本文件(.md / .txt / .json / ...)生成 .converted.md 副本(native_text: true)
  - ❌ 不允许原地覆盖已有 .converted.md(对齐 raw/ 不可变层 + Q5 + G7)
  - ❌ 不新增 "重转" skill(用户主动 `cp` 回 inbox/ 走标准 ingest,见 G10)
  - ❌ 不在 `source_path` / `links:` 留任何与 md 副本哈希相关的字段(可由 lint 按需计算;非 AC)
  - ❌ 不在 raw/ 下生成 `_converted/` 子目录(保持 raw 子目录语义单一:放哪类就只放哪类)

### 4.3 Query skill

- **触发**:`/aeps-llm-wiki-query <question>`
- **必须**(Intent 路由 + 4 跳扫描,详见 design §4.3):
  - **Intent 路由(3 档)**(v0.5.2 PATCH 修复缺陷 1,G11 M3 gating 语义对齐):
    - LLM 在阶段3推断 intent,**显式分 3 档**:`exact` / `ambiguous` / `{overview, comparison, other}`(overview/comparison/other 走触发路径)
    - **`ambiguous` 档含义**:语义模糊,LLM **不能**明确判断是纯事实查证还是综合推演(例:"这篇芯片文档和上一篇有什么异同?" —— 既含"异同"对比倾向词,又含"上一篇"指代模糊;LLM 无法在阶段3稳定分类)
    - **`ambiguous` 档默认行为**:**走 fallthrough 不触发** ——"低扰动路线"(Skip Proposing Analysis),避免误判导致 over-prompting 或误杀;**这是 fallback,不是路径 C 词命中场景**
    - **路径 C 触发词清单**(v0.5.1 PATCH,vs/对比/区别/异同/优缺点/X vs Y)是**SKILL.md 提示词辅助倾向词**,不替代 LLM 阶段3 3 档推断;**显式冲突时以 LLM 推断的 `ambiguous` 为准**(避免路径 C 词命中覆盖模糊语义)
  - **第 1 跳**:`knowledge/index.md` 找候选页;按 `tags` 关键词做第一轮过滤(条目 frontmatter 的 tag 与 query 关键词重合数,top-K 入选)
  - **第 2 跳**:读候选页(优先级:`description` / `summary` → `title` → 全文)
  - **第 3 跳**:顺着候选页内的 `[[wikilink]]` / `Related pages` 段跳到相邻 `entities/` `concepts/` `analyses/` `comparisons/` 页(1 跳深度,避免雪崩)
  - **第 4 跳**:读 `glossary.md`(query 关键词消歧)+ `log.md` 近期 10 条(检查是否近期 ingest 了相关源没消化)
- **必须**(本地搜索引擎 qmd 分流,详见 design §4.3):
  - **< 500 页**:纯 `index.md` + 4 跳扫描,**不**调 qmd
  - **500~1000 页**:**优先 qmd**(`qmd query "<question>"`);未装 → 提示用户装,降级走 `index.md`
  - **> 1000 页**:**必须 qmd**;未装 → **报错**(提示"wiki 已超 1000 页,请装 qmd 后再 query"),不进入回答
  - 阈值常量:`QUERY_INDEX_THRESHOLD = 500`、`QUERY_QMD_REQUIRED_THRESHOLD = 1000`(详见 design §4.3)
  - 探查入口:`scripts/check-qmd.py`(Python 3.10+ 单次脚本,跑 `qmd --version` 探查可用性)
- **必须**:
  - 回答,**每条断言附 wiki 标准 markdown 链接**
  - **G11 — 落档 gating**(G11 M3,详见 design §4.3 + implement §C15.3):回答结束后,**仅在满足下列触发条件之一时才在末尾问用户是否落档**:
    - **触发条件**(任一命中即问):
      - **跨领域综述 / Overview**:intent 判定为 overview 类(全局设计 / 方案评估)
      - **对比分析 / Comparison**:intent 判定为 comparison 类(提问含 "X vs Y" 型对象对比)
      - **整合多源**:本次 query 命中 ≥ 2 个不同 wiki 子目录的源页
      - **深度回答**:回答字数 ≥ 200 字(LLM 综合推演,非短答)
    - **不触发**(任一命中即跳过):
      - intent = `exact`(纯事实查证,如"S32G PCIe 几个接口")
      - intent = `ambiguous`(语义模糊,fallback 低扰动,v0.5.2 PATCH 修复缺陷 1)
      - 回答字数 < 200 字
      - 命中源 < 2 个
      - 回答含 "Wiki 未覆盖此问题" 字样(LLM 诚实声明)
    - **Gating 提示语模板**(SKILL.md 用):
      - 触发:`❓ 本次回答命中 ≥2 个 Wiki 源、深度 ≥200 字,符合 analysis 落档门槛。是否落档为 \`knowledge/analyses/<时间戳>-<slug>.md\`?[Y/n]`
      - 不触发:`💡 本次回答为单点查证 / 语义模糊 / 短答 / Wiki 未覆盖,跳过落档询问。`
  - **G11 — 落档为 analysis 页**(G11 M1 + M2,详见 design §3.6.1 + templates/analysis-page.md):
    - 新建 `type: analysis` 页,放在 `knowledge/analyses/<时间戳>-<slug>.md`
    - frontmatter 必填:
      - `type: analysis` + `title` + `updated` + `tags`
      - `answer_to`:原 query 问句
      - `sources_used`:string[],**本次回答参考的 wiki 页相对路径列表**(去重,SKILL.md 扫阶段 2 命中 + 阶段 3 引用路径自动抓)
      - `generated_by: agent: producer/aeps-llm-wiki-plugin/<version>`
      - `summary`:首行 `**问题**: <原问句>`,余下 ≤ 280 字符
    - **正文 3 节专属骨架硬约束**(lint C15.1 + C15.4,缺一即 FAIL):
      - `## 方案推演 / 架构分析` —— 本次推演的核心分析与架构逻辑(替代原 sources 风格的"重点摘录",语义对齐"LLM 综合推演")
      - `## 关联溯源` —— 本次推演用到的关键 Wiki 事实与依据(替代原 sources 风格的"我的思考",语义对齐"引用链 + 推演依据");末尾追加 `> 引用:` 行列源路径,与 frontmatter `sources_used` 镜像同步(Q7 死循环防护)
      - `## 总结:最有收获的一句话` —— 一句话 Core Verdict / 核心结论
    - **禁止**含 `## 摘要` / `## Summary` 小节(对齐 v0.4.0 纪律,§3.1 §C)
  - 追加 log(`**Creation**: query "<原问句>" → analyses/<file>.md`)
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
    - **正文骨架不合规**:`sources/*.md` 和 `analyses/*.md` 必含 3 节 H2(`## 重点摘录`、`## 我的思考`、`## 总结:最有收获的一句话`),缺一即 FAIL;**禁止**含 `## 摘要` / `## Summary` H2(详见 design §3.1 §C;动机:frontmatter `summary` 字段承担长摘要职责,正文 `## 摘要` 会与 3 节骨架产生 UI 冗余;OKF v0.2 不强制正文必须有 `## 摘要`,纪律与 OKF / Karpathy 风格一致)
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

不增加 skill,**由 query skill 内置三条触发路径**(v0.5.1 PATCH 显式化 + 新增路径 C):

- **路径 A — 同类 entity 触发**(ingest 阶段):ingest 完成后,LLM 在 source 页落档询问时,如果发现 `entities/<子类>/` 下已有同类 entity(同一 type)≥ 2 个且都是这次新 ingest 的相关对象,**提议**:"要不要建一个常驻 comparison 页把它们对照一下?"
- **路径 B — 累积检索触发**(query 阶段,跳 4 探测):query 累计发现用户 ≥ 3 次问"X vs Y"型问题(grep `log.md` 检测模式 `**Creation**: ... query "X.*Y"`,query 落档 log 走 §3.4 五种前缀里的 **`Creation`** —— 因为 query 落档是新建 analysis 页,不是修改既有页;同时 description 含 query 原问句标记 `query "<原问句>"`,便于正则匹配),**下次落档询问时只提一次**:"X vs Y 这个对比提过几次了,要不要建一个常驻 comparison 页?"
  - **v0.5.1 PATCH 显式化**:计数阈值 **≥ 3 次,全局累计,不加 7 天时间窗**(D4 决策);SKILL.md 跳 4 探测时按主题近似匹配(首实体名 / slug),**不**要求精确 X/Y 完全相同(避免"X vs Y" 和 "X vs Z" 被算两次的边缘情况)
- **路径 C — 单次词命中触发**(query 阶段,v0.5.1 PATCH 新增,D3 决策):query 中含以下触发词任一 → LLM 在阶段3判定 `intent = comparison`,本次回答直接走 gating 触发 analysis 落档(对照 G11 M3,详见 prd §4.3 + design §4.3.2 + lint C15.3)
  - **触发词清单**:`vs` / `对比` / `区别` / `异同` / `优缺点` / `X vs Y` 型对象对
  - **D1 决策**:**不引入 Python 本地 intent router**,intent 仍由 LLM 在阶段3推断(详见 design §4.3.2 `should_prompt_save()` 伪代码假设);触发词清单是**SKILL.md 提示词里的辅助倾向词**,不是硬规则 —— LLM 可根据语义判断"虽然含'vs' 但用户其实在解释用法而非比较"等边界
- **三路径职责不重叠**:
  - **路径 A** → 触发**常驻 comparison 页**(建到 `knowledge/comparisons/`)
  - **路径 B** → 触发**常驻 comparison 页**(同上)
  - **路径 C** → 触发**本次分析页 analysis 落档**(建到 `knowledge/analyses/<时间戳>-<slug>.md`,与 comparison 常驻页**职责分开**:analysis 是 LLM 综合推演的一次性快照,comparison 是用户长期查阅的对照表)
- **命名**:
  - 常驻页:`knowledge/comparisons/<a>-vs-<b>.md`(**不带时间戳**,常驻)
  - 一次性落档:`knowledge/analyses/<时间戳>-<slug>.md`(带时间戳,G11 v0.5.0 沿用)
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
├── scripts/                          # plugin 维护的单次运行脚本(Python 3.10+,.py),init 时从 plugin 拷贝到此(具体文件由实现侧按目录扫描决定,本文档不列举)
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

### 7.1 功能验收

- [ ] AC-1:用户 install plugin + `/aeps-llm-wiki-init`,5 分钟内得到完整目录;`SCHEMA.md` 内容可读、覆盖 ingest/query/lint 三个工作流
- [ ] AC-2:把 `raw/okf-spec.md`(已存在的样例)做 ingest,产出 ≥ 5 个 OKF 兼容的概念页,且 `index.md` 反映新增
- [ ] AC-3:`/aeps-llm-wiki-query "OKF 必填字段是哪个"`,回答含 wiki 链接,且**不编造 wiki 里没有的内容**
- [ ] AC-4:`/aeps-llm-wiki-lint` 能正确识别孤儿页、过期页、frontmatter 不合规页
- [ ] AC-5:**生成的任意 wiki 页 frontmatter 都能被 OKF v0.2 校验脚本通过**(自动测试)
- [ ] AC-6:`/aeps-llm-wiki-ingest`(无参数,扫 inbox/):LLM 输出迁移提议,**未拍板前 inbox 文件不动**;用户拍板后文件出现在 `raw/<subdir>/`,`inbox/<file>` 删除,`log.md` 记录迁移路径
- [ ] AC-7:`/aeps-llm-wiki-ingest --raw-subdir=<name>`:跳过分类交互,直接迁到 `raw/<name>/`;`log.md` 仍记迁移路径
- [ ] AC-8:`/aeps-llm-wiki-ingest` 但 `inbox/` 为空:提示"inbox/ 为空,先把资料丢进 inbox 再跑",**不报错**(退出码 0,符合 SKILL 调用语义)
- [ ] AC-9(G10):丢 `inbox/iso26262.pdf` → ingest 完成后 `raw/06_功能安全/iso26262.pdf` 与 `raw/06_功能安全/iso26262.pdf.converted.md` **同时存在**;源页 frontmatter 含 `format: pdf` + `converter: anydoc` + `native_text: false` + `converted_path: raw/06_功能安全/iso26262.pdf.converted.md`,且 `links:` 含 `[[iso26262.pdf.converted]]`
- [ ] AC-10(G10):丢 `inbox/notes.md`(纯文本) → ingest 完成后 `raw/<subdir>/notes.md` 存在,**不**生成 `notes.md.converted.md`;源页 frontmatter `format: md` + `converter: null` + `native_text: true` + `converted_path: null`,`links:` 含 `[[notes]]`
- [ ] AC-11(G11 M1):`/aeps-llm-wiki-query "<深度架构问题>"` 触发落档后,新建 `knowledge/analyses/<时间戳>-<slug>.md`,正文含**分析专属 3 节骨架**(`## 方案推演 / 架构分析` + `## 关联溯源` + `## 总结:最有收获的一句话`),**不含** `## 重点摘录` / `## 我的思考` / `## 摘要` / `## Summary` H2;lint C15.1 命中 FAIL
- [ ] AC-12(G11 M2):落档的 analysis 页 frontmatter **必填** `sources_used: [相对路径列表]`,且 lint C15.2 校验:每条路径都解析到真实存在的 `knowledge/**/*.md`(相对 `knowledge/`),否则 FAIL;`## 关联溯源` 末尾 `> 引用:` 行与 `sources_used` 走 Set 比对(Q7),不一致 WARN;`sources_used` 任意一条被 `--fix` 重写时,**不动 `updated` 字段 + 文件 mtime**(Q7 死循环防护规则延续)
- [ ] AC-13(G11 M3):落档询问**受 gating 控制**,四种触发条件任一命中才问(Overview / Comparison / ≥2 不同子目录的源 / ≥200 字),四种不触发任一命中即跳过(Exact / <200 字 / <2 源 / "Wiki 未覆盖")。可写 e2e 测试:同一 query skill,三种 query 类型(Exact 单点 / Overview 多源 / Comparison 对比)分别跑,**断言**落档询问输出与 gating 规则一致(Exact 无 prompt;Overview 必有 prompt;Comparison 必有 prompt)

### 7.2 非功能验收

- [ ] NFR-1:plugin 装上后,**不引入**任何 MCP server / CLI / hooks / RAG 依赖(**可选**例外:[qmd](https://github.com/tobi/qmd) —— 仅作为 query skill 在 wiki 规模较大时的本地搜索引擎;用户必须自行 `npm install -g @tobilu/qmd`,plugin 不强制装,详见 §4.3;**唯一阈值升级条款**:当 `knowledge/` 目录页数 $N \ge 1000$ 时,§4.3 规定的 `QUERY_QMD_REQUIRED_THRESHOLD` 触发,query skill 直接报错退出(此时 qmd **临时升级为强依赖**),其余规模下 qmd 仍为可选)
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

| 风险                                                                 | 影响                                                  | 缓解                                                                                                                                                                                                         |
| -------------------------------------------------------------------- | ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| OKF v0.x 仍在演进(v0.2 已发),字段可能变化                            | plugin 锁定的 type 集合将来要适配                     | 只锁定 OKF v0.2 已定义的字段,扩展字段显式标注为 plugin 扩展,OKF 工具可忽略                                                                                                                                   |
| LLM 在 ingest 时跑偏(漏抽 / 错判 entity 还是 concept / 错选 14 子类) | wiki 质量下降                                         | lint skill 兜底,识别"目录名 ↔ type"不一致;SCHEMA.md 给明确子类判定示例                                                                                                                                      |
| `[[wikilink]]` 与标准 markdown 链接混用                            | OKF 工具可能不解析`[[]]`                            | **plugin 以 `[[wikilink]]` 为一等公民**(详见 Q6)——Obsidian 原生可双链跳;**OKF 兼容靠 frontmatter `links:` 镜像字段自动同步**(详见 design §3.6.2):plugin 扫正文 wikilink + markdown link 自动生成 `links:`(OKF v0.2 §9 推荐字段,供外部 OKF 工具无正文解析消费);lint 检测漂移并 `--fix` 自动同步 |
| `knowledge/` 与 git 仓污染                                         | 用户误把生成的 wiki 提交                              | README 明确建议`.gitignore` `knowledge/` 或选择性提交;plugin 不强制 git 操作                                                                                                                             |
| plugin 内部`schema/frontmatter.schema.yaml` 与用户实际 wiki drift  | lint 误报                                             | lint 只读 plugin 的 schema.yaml(权威字段表),不读用户项目;用户项目的`knowledge/SCHEMA.md` 引用同一份 plugin 字段表,不重复列字段                                                                             |
| inbox 文件被 LLM 误迁移到错误目录                                    | 用户资料找不到                                        | 已存在目录(15 类预建)直接放,出错概率低;字典外的创建**必须拍板**;拍板后 log 留完整 `inbox/ → raw/` 路径便于回滚                                                                                      |
| inbox 文件用户拍板后忘了删                                           | 下次 ingest 重复处理                                  | ingest 流程内强制`inbox/<file>` 删除;不是用户操作,是 skill 原子步骤                                                                                                                                        |
| raw 子目录无限增长,LLM 起名飘(15 类之外)                             | 子目录碎片化(`16_公司内部_a`、`16_公司内部_b`...) | init 时 15 类全部预建,日常基本不会触发创建;字典外的创建必须拍板,用户当场就拦下;lint 仍建议合并相似的子目录                                                                                                   |
| comparison 触发逻辑误报(LLM 提议用户不需要的对比页)                  | `comparisons/` 出现噪声                             | 两条触发路径(同类 entity / 高频检索)都只在落档询问时**提议**,用户拍板才建;**只提一次**,后续不再重复                                                                                              |
| synthesis 写得太空(只是简单罗列,没真正"综合")                        | synthesis 页失去价值                                  | frontmatter`sources_count` 字段是"参考多少页"硬指标,sources_count 太低(<3)的 synthesis lint 警告;正文不锁骨架,LLM 自由发挥,但搜索功能可"找引用最广的综合页"                                                |
| **G10 — raw/ 体积翻倍**(每份非 md 资料都生成 .converted.md 副本)| 用户磁盘占用增加 | 仅对走过转换的文件生成;OCR md 副本通常 << 原文件;`raw/` 本就是归档层,体积增长在预期内;`source_file:` 仍指原文件,引用侧不受影响 |
| **G10 — 重转需求被用户触发**(anydoc / paddleocr 升级 / 转换异常)| 用户需要覆盖 raw/ 副本 | 不开重转 skill(G10 拍板);`cp` 回 inbox 走标准 ingest = 新文件,旧副本保留(可手工 `git rm`);raw/ 不可变层 + Q5 原则保护 |
| **G10 — query 仍读到 raw/ 原 .pdf**(用户未走 ingest 直接 `git mv` 进 raw)| query 仍解析不了 | lint 检查:`source_file` 指 raw/<subdir>/<file> 但 `converted_path` 为 null 且 `native_text: false` → 报错"该 source 缺 md 副本,请把原文件 `cp` 回 inbox/ 走 ingest" |
| **G11 — 旧 analysis 页骨架失效**(v0.4.0 及以前落档的 analyses 用 sources 风格 3 节)| lint 跑在 v0.5.0 上 FAIL | 提供迁移脚本 `scripts/migrate-analysis-skeleton.py --from v0.4.0 --to v0.5.0`:把 `## 重点摘录` → `## 方案推演 / 架构分析` + 把 `## 我的思考` → `## 关联溯源`,保留正文,frontmatter 补 `sources_used`(从正文 wikilink 提取 + 推断);SKILL.md query 阶段 detect 到旧骨架时**提示**用户跑迁移 |
| **G11 — sources_used 误填**(LLM 把 `## 关联溯源` 段落里出现的所有 wikilink 都塞进去)| 列表膨胀 / 含大量无关页 | lint C15.2 + C15.4 双重校验:仅 `## 关联溯源` 末尾 `> 引用:` 行 + query 阶段实际引用路径 + lint 验存在;**禁止**从全文 grep 抽;**禁止**列入 `## 关联溯源` 段正文里出现过但未在引用行的页 |
| **G11 — gating 误判**(短答但其实重要 / Exact 但其实跨域)| 落档询问过松或过严 | gating 触发条件**任一命中即问**,是 OR 不是 AND;不触发条件也是 OR;边界条件(log.md 最近条目是否含 query "<原问句>" 模式)走 `log.md` 检测;lint 仅校 schema,语义误判由用户在 prompt 时回退 |

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
- [X] **Q6**:✅ ~~`[[wikilink]]` 是不是要当"残留"处理?~~ —— 已定:**`[[wikilink]]` 是一等公民**(Obsidian 原生双链 / Karpathy 老 wiki 兼容)。plugin 正文写 `[[page]]` / `[[page|显示]]` / `[[page#章节]]` 形式;**OKF 兼容性靠 frontmatter `links:` 镜像字段自动同步**(OKF v0.2 §9 推荐字段,plugin 扫正文 wikilink + markdown link 自动生成),lint 检测漂移并 `--fix` 自动同步(详见 §8 风险表对应行 + SCHEMA.md §5.3 + design §3.6.2)

---

## 11. 参考

- `input/karpathy-llm-wiki/karpathy-llm-wiki.en.md` —— Karpathy LLM Wiki 理念
- `input/google-OKF/OKF-SPEC.md` —— Open Knowledge Format v0.x 规范
- `input/google-OKF/OKF-README.md` —— Google Cloud 的 OKF 发布说明
- `reference/balukosuri__llm-wiki-karpathy/CLAUDE.md` —— Karpathy 模式的 Agent 操作手册范本
- `reference/balukosuri__llm-wiki-karpathy/README.md` —— Karpathy 模式的 README 结构范本
- `reference/balukosuri__llm-wiki-karpathy/wiki/` —— Karpathy 模式的目录结构范本

---

**下一步**:等本文档 review 通过 → 进入 M2(写 `design.md` + `implement.md`)

---

## 12. Change History

### v0.5.2(2026-09-03) — Round 12 PATCH 修复 2 个 PRD 缺陷(Intent fallback + G10 atomic overwrite)

| # | 增量 | 关联 Q/A | 主要文档改动 |
|---|---|---|---|
| 15 | **Intent 3 档分类 + ambiguous fallback**(修复缺陷 1):LLM 阶段3推断 intent **显式分 3 档** `exact` / `ambiguous` / `{overview, comparison, other}`;**`ambiguous` 走 fallthrough 不触发**,语义模糊时默认低扰动(例:"这篇芯片文档和上一篇有什么异同?" 含路径 C 触发词"异同"但"上一篇"指代模糊 → LLM 无法稳定分类 → 走 ambiguous 跳过);**路径 C 触发词清单不覆盖 ambiguous fallback**(冲突时 ambiguous 胜,避免硬词命中误判);`should_prompt_save()` 伪代码新增 `intent == "ambiguous"` 早返回分支(优先级 > 不触发条件其他项,先判 ambiguous 再判 sources/length/Wiki 未覆盖) | 用户提"PRD §4.3 Intent Router 保底策略:语义模糊时默认走低扰动路线 Skip Proposing Analysis";v0.5.1 路径 C 触发词 + v0.5.0 G11 M3 gating 语义冲突修复 | prd §4.3 Intent 路由段(3 档分类 + ambiguous 默认行为 + 路径 C 不替代说明)+ §4.3 不触发条件 5 行(`exact` / `ambiguous` / <200 字 / <2 源 / Wiki 未覆盖);design §4.3.2 `should_prompt_save()` 伪代码新增 ambiguous 早返回分支 + 注释说明路径 C 不覆盖;implement §C15.3 fixture 8/9/10/11(ambiguous 语义模糊 + ambiguous vs 路径 C 冲突 + intent=other vs 触发条件兜底)|
| 16 | **G10 重 ingest 同名文件 atomic overwrite**(修复缺陷 2):用户重新跑 ingest 且 `raw/<subdir>/<file>` + `<file>.converted.md` 已存在时,**不**报 FileExistsError,而是 **SKILL.md 强制拍板**(`[y]` 覆盖 / `[n]` 跳过 / `[d]` 仅删旧副本)+ `safe-mv.py --apply` 收到 `action: "overwrite"` 走 **atomic overwrite**:**先备份到 `temp/raw_backup_<hash>/`**,再 `os.replace()` 一次性替换两文件(写盘要么全成要么全败);覆盖范围仅 `<file>` + `<file>.converted.md`,**不动**同 subdir 其他文件 + frontmatter `updated` + 文件 mtime(Q7 死循环防护延续);**不开"重转 skill"**(对齐 v0.4.0 G10 拍板:不提供批量重转历史 .converted.md 入口) | 用户提"PRD §4.2 G10 重转与 G7 不可变层死锁:重新 ingest 同名文件应用户拍板 atomic overwrite,而不是 FileExistsError";v0.4.0 G10 不开重转 skill + Q7 死循环防护规则延续 | prd §4.2 G10 派生决策段(覆盖场景 + 拍板选项 + atomic overwrite 行为 + 不动 updated/mtime + 不开重转 skill);design §4.2 step 3 G10 双文件迁移段(atomic overwrite 4 步行为 + 拍板 JSON action schema);implement §C16(4 fixture 脚本:C16.1 重 ingest 检测 + 强制拍板 / C16.2 atomic overwrite 行为 / C16.3 不开重转 skill / C16.4 首次 ingest 回归不触发拍板)|

**兼容性**:**v0.5.2 PATCH bump**(MINOR bump 内小补丁)。本次改动:
- **不引入**新 frontmatter 字段
- **不引入**新正文骨架
- **不引入**新 scripts 入口(只是 `safe-mv.py --apply` 新增 `action: overwrite` 分支处理,**不**新增脚本)
- **不修改**OKF v0.2 schema,不动 lint C15 (analysis 骨架 / sources_used / gating)
- **只扩 intent 档位**(`exact` → `exact` / `ambiguous` / `{overview, comparison, other}`)+ **扩 safe-mv.py --apply decision JSON 字段**(`action` 字段新增 `"overwrite"` 值)

**升级路径**:既有 v0.5.1 wiki 升级到 v0.5.2 plugin **无需**重跑 init,**无需**跑迁移脚本;SKILL.md 内部行为升级即可(ambiguous fallback + safe-mv overwrite 分支)。

### v0.5.3(2026-09-03) — Round 13 PATCH 修复 PRD 缺陷 5(Q7 `links:` 自动重写时 mtime + atime 双还原)

| # | 增量 | 关联 Q/A | 主要文档改动 |
|---|---|---|---|
| 17 | **Q7 `links:` 自动重写强制 4 步流程:stat → write → utime → assert**(修复缺陷 5):lint `--fix` 重写 `links:` 时,虽然 `updated` 字段已强制不改(v0.3.2 Round 7),但**文件 a/mtime 必须显式还原** —— 普通 `Path.write_text` 会让 mtime 必变 + atime 必变,触发 Obsidian 文件监视器(macOS FSEvents / Windows ReadDirectoryChangesW / Linux inotify)+ git `working tree modified` 假阳性;**强制 4 步流程** (1) `os.stat(path)` 取 `(st_atime, st_mtime)` 二元组 → (2) `Path.write_text(new_content)`(允许 `temp/<path>.tmp + os.replace` atomic 写入)→ (3) `os.utime(path, (original_atime, original_mtime))` 显式双还原 → (4) 测试中 `assert os.stat(path).st_mtime == original_mtime and st_atime == original_atime`(仅 fixture,生产代码不强制 assert 避免性能损耗);**atime 必还原**:macOS APFS Spotlight 索引 + 部分 inotify watcher 以 atime 触发 metadata 刷新,只还原 mtime 不还原 atime 会触发"假修改";**反例警戒**:不用 `Path.write_text` 默认行为 + 不调 utime / 只还原 mtime 不还原 atime / 用 `Path.touch()` 假装还原(它会刷为当前时间) | 用户提"缺陷 5:Q7 死循环防护在真实文件系统中的死穴 —— mtime 必变 + atime 必变,必须显式 stat → utime 还原" | design §3.6.2 Q7 第 3 条扩写为强制 4 步流程(原 atime/mtime 双还原 + 反例警戒 4 条 + 不动 a/mtime 根本原因 3 条:§5.4 陈旧检测 / §3.4 不变量 / Obsidian + git working tree);implement §C4.2 新增 2 个 fixture:`test_links_mirror_preserves_atime_and_mtime.py`(atime 浮点精度 1e-6 断言 + monkeypatch 监视 `os.utime` 调用 + 参数二元组断言 + content hash 不变)+ `test_links_mirror_utime_flow_order.py`(monkeypatch `os.stat / Path.write_text / os.utime` 记录顺序,断言严格 stat → write → utime + 反例测试 utime no-op 触发 mtime 必变) |

**兼容性**:**v0.5.3 PATCH bump**(MINOR bump 内小补丁)。本次改动:
- **不引入**新 frontmatter 字段
- **不引入**新正文骨架
- **不引入**新 scripts 入口(只是 `okf-lint.py` / `lint.py` 内部 `fix_links_mirror()` 函数行为升级,**不**新增脚本)
- **不修改**OKF v0.2 schema,不动 G10 / G11 / Q6 / 路径 C / Intent ambiguous fallback / G10 atomic overwrite
- **只升级** Q7 第 3 条规则的**实现细节**(atime/mtime 双还原 + 4 步流程),**不**改 Q7 业务意图(`updated` 不改 + Set 比对 + 文件无副作用)

**升级路径**:既有 v0.5.2 wiki 升级到 v0.5.3 plugin **无需**重跑 init,**无需**跑迁移脚本;`okf-lint.py` / `lint.py` 内部 `fix_links_mirror()` 函数行为升级即可(下次跑 `--fix` 自动按 4 步流程写盘)。

### v0.5.1(2026-09-03) — Round 11 PATCH query skill 路径 C + 跳 3 权重降权 + 跳 4 累积触发显式化

| # | 增量 | 关联 Q/A | 主要文档改动 |
|---|---|---|---|
| 13 | **路径 C — 单次词命中触发**(D3 决策,v0.5.1 PATCH 新增):query 含 `vs` / `对比` / `区别` / `异同` / `优缺点` / `X vs Y` 型对象对 → LLM 阶段3推断 intent=comparison → 本次回答走 G11 gating 触发 analysis 落档(对照常驻 comparison 页是**另一职责**)。**D1 不引入 Python 本地 intent router**:intent 仍由 LLM 推断,触发词清单是 SKILL.md 提示词里的**辅助倾向词**,不是硬规则 —— LLM 可按语义判断边界(如"虽含 vs 但在解释用法而非比较") | 用户提"Comparison 触发词清单(intent=comparison 立即识别)" | prd §4.6 路径 C 整段(词表 + D1 决策 + 三路径职责不重叠说明);design §4.3 跳 4 + prd §4.6 三路径关系表 |
| 14 | **跳 3 权重降权 + 跳 4 累积触发显式化**(D2 + D4 决策):跳 3 优先级(sources: 数组 → `## 关联溯源` 末尾 `> 引用:` 行 → syntheses 的 `## 子主题`/`## 引用` → `## Related pages`(可选)→ 正文其他 wikilink(降权不忽略));跳 4 comparison 累积触发探测显式化(全局累计 ≥3 次,**不加 7 天时间窗**,D4 决策,按主题近似匹配非精确 X/Y);**D2 不引入新 `parent:` 字段 + 不引入强制 `## Related pages` 节**(契约零扩张) | 用户提"第 3 跳带权重剪枝 + 若近 7 天 X vs Y ≥3 次提示建 comparison 页" | design §4.3 跳 3(优先级降权伪代码 + D2 决策)+ 跳 4(累积触发探测 + D4 决策);prd §4.6 路径 B 全局累计说明 + 三路径职责不重叠表 |

**兼容性**:**v0.5.1 PATCH bump**(MINOR bump 内的小补丁)。本次改动:
- **不引入**新 frontmatter 字段(原 `parent:` 提议被 D2 决策否决)
- **不引入**新正文骨架(原 `## Related pages` 强制节被 D2 决策否决)
- **不引入**新 scripts 入口(原 Python intent router 被 D1 决策否决)
- **不修改**OKF v0.2 schema,不动 lint C15 (analysis 骨架 / sources_used / gating),不动 G10 转换契约
- **只细化**设计澄清(§4.3 跳 3 优先级伪代码)+ §4.6 路径 C 词表显式化

**升级路径**:既有 v0.5.0 wiki 升级到 v0.5.1 plugin **无需**重跑 init,**无需**跑迁移脚本;SKILL.md 内部行为升级即可(weight-based pruning + comparison 路径 C 词表)。

### v0.5.0(2026-09-03) — Round 10 G11 query 落档消除 3 个隐患(专属骨架 + sources_used + gating)

| # | 增量 | 关联 Q/A | 主要文档改动 |
|---|---|---|---|
| 11 | **G11 目标 + M1-M3 必须**:query skill 落档为 analysis 页时消除 3 个隐患 —— (M1 结构断层) `analyses/` **不再复用** sources 的 3 节骨架,改用**分析专属骨架**:`## 方案推演 / 架构分析`(替代 ## 重点摘录)+ `## 关联溯源`(替代 ## 我的思考,末尾追加 `> 引用:` 行列源路径)+ `## 总结:最有收获的一句话`(语义对齐"LLM 综合推演"而非"human reading material");(M2 溯源丢失) `type: analysis` frontmatter **新增必填 `sources_used`**(string[],本次回答参考的 wiki 页相对路径列表,Q7 死循环防护:lint 重写时不动 `updated` + 文件 mtime);(M3 Over-prompting) **落档询问加 gating**,4 触发(Overview / Comparison / ≥2 子目录源 / ≥200 字)任一命中即问,4 不触发(Exact / <200 字 / <2 源 / Wiki 未覆盖)任一命中即跳过 | 用户提"query skill 3 个隐患:结构断层(analysis 不该用 sources 骨架)+ 溯源丢失(sources_used 缺位变孤岛节点)+ Over-prompting(纯事实查证不该问落档)" | prd §2.1(G11 + M1-M3 描述)+ §4.3(G11 gating 4 触发 + 4 不触发 + analysis 专属骨架硬约束 + sources_used 必填 + Q7 死循环防护延续)+ §7.1 AC-11/AC-12/AC-13 + §8 风险表新增 3 行(G11 旧骨架失效 / sources_used 误填 / gating 误判);design §3.2 schema extensions.plugin 新增 `sources_used` 字段 + §3.6.1 analysis 段专属骨架锁 + §4.3 query skill 落档 gating 流程 + §5.4 lint C15(C15.1 专属骨架校验 / C15.2 sources_used 路径存在 / C15.3 gating 输出断言 / C15.4 `> 引用:` 镜像);templates/analysis-page.md(**新建**,frontmatter 锁 + 写入指引 + 不变量 lint C15);implement §C15(G11 4 个 fixture:test_analysis_dedicated_skeleton / test_analysis_sources_used_required / test_query_gating_logic / test_analysis_sources_used_mirror) |
| 12 | **G11 迁移路径拍板**:v0.5.0 lint 跑在 v0.4.0 落档的旧 analysis 页上会 FAIL(骨架语义变化);提供 `scripts/migrate-analysis-skeleton.py --from v0.4.0 --to v0.5.0`(映射 `## 重点摘录` → `## 方案推演 / 架构分析` / `## 我的思考` → `## 关联溯源`,frontmatter 补 `sources_used`,正文保留);SKILL.md query 阶段 detect 旧骨架时**提示**用户跑迁移(不自动改) | G11 派生决策 | prd §8 风险表第 1 行 G11 缓解 + design §4.3 query skill 落档 detect 段 |

**兼容性**:v0.5.0 是 **MINOR bump**(analysis 页骨架语义变化 + `sources_used` 必填,**OKF v0.2 schema 无 breaking change** —— `sources_used` 是 plugin 扩展字段,§9 规则"consumers MUST NOT reject bundle because of missing optional frontmatter fields"保证兼容)。**唯一强约束**:v0.4.0 及以前落档的 analysis 页在 v0.5.0 lint 上会 FAIL,用户必须跑一次 `migrate-analysis-skeleton.py` 迁移。

**升级路径**:既有 v0.4.0 wiki 升级到 v0.5.0 plugin:
1. 升级 plugin → 跑 `/aeps-llm-wiki-init`(幂等再入,scripts/ + templates/ 同步;新加 `templates/analysis-page.md` + `scripts/migrate-analysis-skeleton.py`)
2. **跑 `python ./scripts/migrate-analysis-skeleton.py --from v0.4.0 --to v0.5.0`**:`analyses/` 下旧骨架页批量转新骨架 + 补 `sources_used`
3. 跑 `/aeps-llm-wiki-lint --fix --apply` 二次确认所有 FAIL 已清零
4. 后续 query 落档走 v0.5.0 新规则(专属骨架 + sources_used 必填 + gating)

### v0.4.0(2026-09-03) — Round 8 G10 外部转换副本入 raw + 源页 link 指副本

| # | 增量 | 关联 Q/A | 主要文档改动 |
|---|---|---|---|
| 9 | **G10 目标 + M1-M4 必须**:新增 G10(外部工具转换的 md 副本随原文件入 raw,源页 link 指 md 副本);§4.2 追加 M1(转换产物落盘到 raw/,命名 `<basename>.<ext>.converted.md`,与原文件同 subdir 共存)+ M2(源页 frontmatter 增 `format` / `converter` / `native_text` / `converted_path` 四字段,OKF v0.2 兼容)+ M3(`links:` 镜像字段自动同步 + Q7 死循环防护)+ M4(`convert-to-md.py --batch --emit-to` 参数 + SKILL.md 三步调用顺序) | 用户提"ingest 增加需求:外部工具转换的 md 文件也要拷贝到 raw,源页 link 指 md 副本而不是原文件,query 时 llm 同样解析不了原文件" | prd §2.1(G10)+ §4.2(M1-M4)+ §4.2 不应做段(G10 相关 5 条)+ §7.1 AC-9/AC-10 + §8 风险表 3 行;design §3.2(extensions.plugin + g10_source_consistency + g10_links_mirror)+ §4.2 step 2/3/5(G10 整段)+ §4.2.1 阶段 1/2/3(G10 适配)+ §3.6.2(links 镜像扩展);templates/source-page.md(frontmatter 锁 + G10 写入指引 + 不变量 lint C13);implement §C13(12 个 fixture,见 Change History Round 9 列表) |
| 10 | **G10 重转策略拍板**:不对 .converted.md 开重转入口(raw/ 不可变层 + Q5 原则 + G7);用户需重转时 `cp` 回 inbox/ 走标准 ingest(新文件生成新副本,旧副本手工 `git rm` 即可) | G10 派生决策 | prd §2.1 G10 + §4.2 不应做 + §8 风险表 |

**兼容性**:v0.4.0 是 **MINOR bump**(新增 G 级目标 + 4 字段,无 OKF schema breaking change —— `format` / `converter` / `native_text` / `converted_path` 均为 OKF v0.2 §B 推荐字段或 plugin 扩展字段,§9 规则:"consumers MUST NOT reject bundle because of missing optional frontmatter fields")。

**升级路径**:既有 v0.3.1 wiki 升级到 v0.4.0 plugin:
1. 升级 plugin → 跑 `/aeps-llm-wiki-init`(幂等再入,scripts/ + templates/ 同步)
2. **历史 raw/ 中已有的非 md 文件**(无 .converted.md 副本)**不需要强制补建**(G10 是 ingest 增量,历史归档不变);lint 检查时按需报"该 source 缺 md 副本"提示
3. 用户主动补建:把原文件 `cp` 回 inbox/ → 跑 ingest(走 M1-M4 新流程,自动生成副本)

### v0.2(2026-09-02) — 五轮增量

| # | 增量 | 关联 Q/A | 主要文档改动 |
|---|---|---|---|
| 1 | **Python 化**:scripts/ 从 Node 18+ `.mjs` 切到 Python 3.10+ `.py` 单栈(任何doc/convert-to-md 直接调 anydoc/paddleocr,消除 Node 套壳 + Python 内核的伪单栈);新增 `scripts/requirements.txt` 含 jsonschema / pyyaml / pytest | — | design §1.1 / §1.2 / §1.4 / §2.4 / §4.2-§4.4 / §7.2;implement §0 / §B2-§B4 / §C10 / §C12 / §C14;scripts/README.md 全文;物理删除 `scripts/check-qmd.mjs`;新增 `scripts/requirements.txt` |
| 2 | **3-stage ingest 并发 + batch OCR**:多文件场景走 `convert-to-md.py --batch` 单次冷启动 + ≤ 5 subagent 并行 LLM + 主 agent 阶段 3 串行收尾;Bash timeout 显式 600000ms | 用户提"subagent 并行处理" + "paddleocr 冷启动耗时" | design §1.4(支持 --batch) / §2.4(双调用模式) / §4.2.1(新整段) / §5.1(分 N=1 / N≥2 双流程);implement §B2(两调用模式) / §C2.4(8 个测试用例) |
| 3 | **Q9 双字段 source_file + sources[]**:type: source 页 frontmatter 同时含 `source_file:`(顶层字符串,Obsidian 笔记属性面板可点击)与 `sources[].resource`(OKF §5.1 必填数组,机器可读),值必须相等(lint C5.1 一致性断言) | 用户贴 Obsidian 笔记属性面板截图,Q9 | design §3.6.1.1(新整段);templates/source-page.md(物理新建,frontmatter 锁 + LLM 写入指引 + 不变量);SCHEMA.md §2.2(必填字段表拆 3 行);implement §C5.1(4 个测试用例) |
| 4 | **Q10 scripts 严禁交互硬契约 + plan 文件 audit trail**:scripts/*.py 严禁 input() / sys.stdin.read() / getpass 等阻塞调用(NFR-1 加严);ingest/lint 走 `temp/proposal-<doc-id>.json` → SKILL.md 拍板 → `temp/decision-<hash>.json` → scripts --apply 三段落档(后缀统一 .json,scripts 用 json.load() 解析,**零 markdown 解析路径**) | 用户提"自动化分流 vs 人工拍板 卡点" | design §2.4.1(整段 scripts/*.py 无交互纯工具契约) + §4.2.x(新整段"ingest 提案/拍板/应用 三段落档(audit trail)" + proposal/decision JSON schema);implement §C10.1(ast 静态扫描断言) + §C10.2(plan JSON schema 校验);scripts/README.md 新增"调用约定(scripts/ 严禁交互)"段 |
| 5 | **Q11 subagent 写权矩阵 + 阶段 3 串行动作清单**:subagent 唯一可写路径是 `temp/<id>-proposal.json`;knowledge/ 下任何文件(index.md / glossary.md / log.md / overview.md / sources/ / entities/ / concepts/ / analyses/ / syntheses/ / comparisons/)在阶段 3 主 agent 串行收尾前绝对禁改;阶段 3 严格 9 步串行(命名飘仲裁 → 拍板汇总 → concept 去重 → entity 去重 → mv → source 页 → entity 页 → concept 页 → 最后一次性改索引) | 用户提"并发处理与阶段解耦(§4.2.1 未完结部分)" | design §4.2.1 新增"写权矩阵(并发安全硬约束,Q11)"整段 + "阶段 3 主 agent 串行动作清单(Q11)"整段;implement §C2.4 新增 Q11 测试用例(4 项) |

**附带**:Q6 wikilink 改造 + frontmatter `links:` 镜像字段机制 + 双格式识别 OKF reader,已在 v0.2 一并冻结(详见 design §3.6.2 + implement §C4.2)。本表仅列 v0.2 5 轮增量。

**兼容性**:v0.2 是 MINOR bump,所有改动对 OKF v0.2 spec 兼容性保持(§9 "consumers MUST NOT reject bundle because of missing optional frontmatter fields" + "consumers SHOULD tolerate unknown constructs")。无 breaking change;既有 v0.1 wiki 升级到 v0.2 plugin 只需重跑 init(scripts/ 重新同步)。

### v0.3(2026-09-02) — Round 6 temp/ 目录契约补丁

| # | 增量 | 关联 Q/A | 主要文档改动 |
|---|---|---|---|
| 6 | **temp/ 顶层目录契约补全**:§2.1 目录树新增 `temp/` 节点 + `.gitkeep` + `.gitignore`(`*` 屏蔽 / `!.gitkeep` 保留 / `!proposal-*.json` / `!decision-*.json` / `!plan-*.json` 显式允许);§4.1 init 步骤 5 创建 temp/;§4.1 顶层目录"五个"→"六个";§4.1.1 sync 策略纳入 temp/ | 用户提"内部冲突:Subagent 写权隔离(Q11)与目录结构的临时文件路径契约(temp/ not in tree, not init'd)" | design §2.1(目录树 temp/ 节点)+ §4.1(步骤 5 新建整段)+ §4.1.1(sync 策略纳入 temp/)+ §9 Round 6 整段;implement §6 v0.3(4 个测试用例:init 创建 temp/、scripts --output/--apply 路径断言、.md plan 拒绝、gitignore audit) |
| 7 | **plan 文件命名契约细化(ingest vs lint)**:ingest 路径 `temp/proposal-<doc-id>.json`(按 inbox 文件标识,与 §4.2.1 subagent 写权矩阵对齐);decision 走 `temp/decision-<hash>.json`(按内容 hash,内容变更时复用);lint 路径继续 `temp/lint-proposal-<hash>.json` / `temp/lint-decision-<hash>.json`(lint 无 doc-id 维度) | Q10 + Q11 设计细化收尾 | design §2.4.1 + §4.2.x 流程图 + plan 文件格式段 + §9 Round 4 描述;prd.md §12 Round 4 描述(已同步) |

**附带**:本次为 MINOR bump,无 OKF schema breaking change;既有 v0.2 wiki 升级到 v0.3 plugin 只需重跑 init(temp/ 自动补建)。

**兼容性**:v0.3 MINOR bump,目录结构新增顶层节点 + 命名契约细化,所有改动对 OKF v0.2 spec 兼容性保持。无 breaking change。

### v0.3.1(2026-09-02) — Round 7 `links:` 死循环防护 PATCH

| # | 增量 | 关联 Q/A | 主要文档改动 |
|---|---|---|---|
| 8 | **`links:` 自动重写硬约束(Q7 死循环防护)**:为 §3.6.2 + §5.4 已有"`links:` 自动重写"机制补 3 条确定性规则 —— (1) Set 比对(顺序无关,`frozenset({type, target})` 相等即一致);(2) `updated` 字段绝对不改(对齐 §3.4 "重新生成 ≠ 更新" + SCHEMA.md §7 不变量);(3) 文件 mtime 保留(`os.utime` 强制),禁止用 `Path.write_text` 默认行为。LintFix 日志模板:`**LintFix**: links-mirror-sync on <path> — N added, M removed, K reordered` | 用户提"内部隐患:links: 镜像字段(Q6)与 stale_after / updated 触发 Lint Fix 的死循环风险" | design §3.6.2 新增"`links:` 自动重写的硬约束(Q7 死循环防护)"子段 + LintFix 日志模板;design §5.4 报告段 + 确定性修复段交叉引用;SCHEMA.md §5.3 lint 段加 Q7 死循环防护说明;implement §C4.2 补 2 个测试用例(idempotent + preserves_updated_and_mtime) |

**附带**:本轮无新增顶层结构 / 无命名契约变化,纯 lint 行为加固。

**兼容性**:v0.3.1 PATCH bump:OKF v0.2 schema 无 breaking change;既有 v0.3 wiki 升级到 v0.3.1 plugin **无需**重跑 init(纯 lint 行为规则,scripts/ 不变)。

### v0.1(2026-09-02) — 初版冻结

详见 git log:`75502e6` / `078fc0d` / `136cee1` / `8cbfb33` / `c726a96`。初版含 Q1-Q6 拍板、9 节里程碑、M1-M6 阶段切分。

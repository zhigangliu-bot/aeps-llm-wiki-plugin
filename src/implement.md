# implement.md — 执行清单

> **来源**:[prd.md](prd.md) 产品需求 + [design.md](design.md) 技术设计。
> **状态**:截至 2026-09-03,文档层 src/design.md v0.5.5 + src/prd.md v0.5.5 + 7 份 templates(含 v0.5.0 新增 analysis-page.md + source-page.md)已完成。
> **剩余工作**:把 src/ 内容打包为可上架的 Claude Code plugin(目录结构 + SKILL.md + plugin.json + 测试 + GitHub 发布)。

---

## 0. 现状盘点(2026-09-02)

**产品定位**(2026-09-02 增):`aeps-llm-wiki-plugin` 的输出 `knowledge/` 目录是给 **Obsidian** 消费的。LLM 写、人用 Obsidian 读、plugin 管一致性。Obsidian 直读是产品级硬约束,所有链接 / tag / 目录 / 文件名设计必须 Obsidian 原生可识别(详见 prd §1 背景 + design §0 前端契约)。

```
src/                                    已完成
├── design.md                           ✅
├── prd.md                              ✅
├── implement.md                        ✅
├── schema/                             ⚠️ 设计阶段保留(frontmatter + proposal .yaml 待阶段 C 实现 scripts 时落地)
│   ├── frontmatter.schema.yaml         ⚠️ 待新建(阶段 C,见 design §1.2)
│   └── proposal.schema.yaml            ⚠️ 待新建(阶段 C,见 design §1.2)
├── scripts/                            ⚠️ 设计阶段仅 README.md + requirements.txt
│   ├── README.md                       ✅(scripts/ 约定 + 未来脚本规划)
│   └── requirements.txt                ✅(anydoc / paddleocr / jsonschema / pyyaml / pytest)
│   └── *.py                            ❌ 设计阶段未生成,阶段 C 实现(convert-to-md.py + 其他,Python 3.10+ 单栈)
└── templates/                          ✅(7 份现状;设计意图 9 份含 analysis-page.md + tag-template.md)
    ├── raw-readme.md                   ✅(15 类权威字典,plugin 主)
    ├── concept-entities-readme.md      ✅(子类 ↔ 目录绑死)
    ├── tag-template.md                 ✅(6 轴受控词表 v0.4)
    ├── inbox-readme.md                 ✅(简版提示,plugin 主)
    ├── knowledge-SCHEMA.md             ✅(用户项目下操作手册,含占位符)
    ├── source-page.md                  ✅(sources/ 页生成模板)
    └── analysis-page.md                ✅(analyses/ 页生成模板,G11 v0.5.0 专属骨架)

plugin 上架资产                          ❌ 待新建
├── .claude-plugin/plugin.json          ❌
├── skills/
│   ├── aeps-llm-wiki-init/SKILL.md     ❌
│   ├── aeps-llm-wiki-ingest/SKILL.md   ❌
│   ├── aeps-llm-wiki-query/SKILL.md    ❌
│   ├── aeps-llm-wiki-lint/SKILL.md     ❌
│   └── aeps-llm-wiki-synthesize/SKILL.md ❌
├── tests/                              ❌
└── docs/                               ❌(对外文档)
```

---

## 1. 执行任务(分阶段)

### 阶段 A:plugin 骨架(预计 1 天)

- [ ] **A1** 在 plugin 根目录建 `.claude-plugin/plugin.json`
  - 字段:`name`、`version: 0.4.0`、`description`(中文)、`author: zhigang.liu`、`license`
  - `keywords`:claude-code / plugin / llm-wiki / okf / automotive-electronics
- [ ] **A2** 在 plugin 根目录建 `README.md`(对外)
  - 一句话定位 + 截图占位 + 5 个 skill 简介 + 安装方式(`/plugin install ...`)
  - 指向 `src/prd.md` / `src/design.md` / `src/templates/`
- [ ] **A3** 在 plugin 根目录建 `LICENSE`(MIT 或 Apache 2.0,用户拍板)
- [ ] **A4** 建立 `docs/` 目录:把 `src/prd.md` / `src/design.md` / `src/implement.md` 镜像过去(对外文档)
  - 在 `docs/README.md` 写"内部维护在 src/,对外快照在 docs/"

### 阶段 B:5 个 SKILL.md 撰写(预计 2-3 天)

每个 SKILL.md 走"prompt 驱动"形态 —— **不是 Python 脚本**,而是一段 Claude Code 会读的提示词,告诉 LLM 在用户触发 skill 时该做什么。

**通用约束**(所有 SKILL.md 遵守):

- 开头固定块:`## 必读文件` 列出该 skill 工作时必须读的文档(从 templates/ 选)
- `## 工作流` 步骤化(对应 design.md §5 各流程图)
- `## 不应做` 列出"绝不要做"的边界(防 LLM 漂)
- `## 输出格式` 标准化(actor 字符串、log.md 条目模板)
- 用中文写(对齐 NFR-3),术语保留英文(如 `type: source`)
- 不引用绝对路径(对齐 NFR-4),用 `<project>/<dir>/` 占位

#### B1:`/aeps-llm-wiki-init` SKILL.md

对应 prd.md §4.1,设计见 design.md §4.1 + §4.1.1(幂等再入)。
必读:`templates/raw-readme.md` + `templates/concept-entities-readme.md` + `templates/tag-template.md` + `templates/inbox-readme.md` + `templates/knowledge-SCHEMA.md`。
输出:5 步执行清单(读模板 → 问 raw-dir / knowledge-dir → 复制 → 预建子目录 → 写 SCHEMA.md)。
**核心边界**:

- 检测 `<project>/knowledge/SCHEMA.md` 是否存在:存在走幂等再入流程(design §4.1.1),不存在走首次启用
- 三份字典(raw-readme / concept-entities-readme / tag-template)按 append 策略同步
- inbox-readme / SCHEMA.md / index.md / overview.md 走覆盖或实化策略
- 写入 `<project>/raw/.aeps-plugin-version: 0.4.0`

#### B2:`/aeps-llm-wiki-ingest` SKILL.md

对应 prd.md §4.2,设计见 design.md §5.1。
必读:`knowledge/SCHEMA.md`(本机已实化版)+ `raw/README.md` + `raw/tag-template.md` + `raw/concept-entities-readme.md`。
**核心边界**:

- 入口:**递归**扫 `<project>/inbox/`(含子目录),不递归 raw/
- **跑前先校验依赖**:`scripts/requirements.txt` 的 anydoc / paddleocr 是否安装;未装 → 提示 + 退出
- 文件读取走统一入口(两种模式,详见 design §2.4 + §4.2.1):
  - **单文件**(inbox N=1):`python3 ./scripts/convert-to-md.py --project-dir . --input inbox/<file> --output <tmp>`
  - **批量**(inbox N ≥ 2):`python3 ./scripts/convert-to-md.py --project-dir . --batch inbox/<f1> ... inbox/<fn> --output-dir temp/`(**显式 Bash timeout: 600000ms**,Claude Code max;paddleocr 冷启动 5-30s + N 文件 OCR ≈ N×1-3s)
  - md / txt / csv / json / yaml / xml / html / htm / rst → 直接读
  - pptx / docx / xlsx / pdf → Claude converter 失败则降级 anydoc
  - png / jpg / jpeg / bmp / tiff → paddleocr
  - 其他 / 失败 → FAIL,提示"无法转换 <file></file>,请手动预处理"
- **三阶段并发处理**(design §4.2.1;N ≥ 2 时走):
  - **阶段 1 batch IO**:主 agent 单进程跑 convert-to-md.py --batch,**paddleocr Engine 只加载 1 次**(避免 N 次冷启动叠加)
  - **阶段 2 LLM 并行**:主 agent 切 ≤ 5 批,派 ≤ 5 个 subagent(Claude Code Task 工具)各自读自己那批 md + 写 proposal JSON,**不动 knowledge/**
  - **阶段 3 主 agent 收尾**:命名飘仲裁 / concept aliases 去重 / mv / 写 sources + entities + concepts / 追加 log.md / 更新 index / glossary / overview — 全部串行,无并发写冲突
  - **N = 1 时跳过阶段 2**(避免派发开销);主 agent 自己跑完阶段 1 + 3
- 拍板门分流:目标目录已存在无需拍板;不存在必须拍板
- 3 节 H2 骨架硬约束(## 重点摘录 / ## 我的思考 / ## 总结:最有收获的一句话)
- 禁止 `## 摘要` / `## Summary` 小节
- 抽取 entity / concept 子页,子类 ↔ 目录 1:1 绑死

#### B3:`/aeps-llm-wiki-query` SKILL.md

对应 prd.md §4.3,设计见 design.md §4.3。
必读:`knowledge/index.md` → 锚定相关页 → 读对应页 + `log.md`。
**核心边界**:

- 一次性 query:直接答 + `[[wikilink]]`,不建页
- 多次 query 同主题 / 用户显式说"对比一下" → 提议建 `knowledge/comparisons/<a>-vs-<b>.md`,用户拍板
- **绝不编造 wiki 里没有的内容**(AC-3 硬验收)
- **跑前先跑** `python3 ./scripts/check-qmd.py --project-dir .`,根据返回 `engine` 决定入口:
  - `engine: index` → 4 跳扫描(跳 1 读 index.md + tag 过滤;跳 2 读候选页 description/title/全文;跳 3 顺 `[[wikilink]]` 跳邻居 ≤ 8;跳 4 读 glossary + log 最近 10 条)
  - `engine: qmd` → `qmd query "<question>" --collection knowledge --limit 20`,拿 top-20 进入跳 2
  - `engine: fail` → 直接退出,提示用户装 qmd(N ≥ 1000 强约束)
- top-K 常量:`QUERY_CANDIDATE_K=10` / `QUERY_NEIGHBOR_MAX=8` / `QUERY_LOG_RECENT=10` / `QUERY_INDEX_THRESHOLD=500` / `QUERY_QMD_REQUIRED_THRESHOLD=1000`

#### B4:`/aeps-llm-wiki-lint` SKILL.md

对应 prd.md §4.4,设计见 design.md §4.4。
必读:`knowledge/SCHEMA.md`(读 lint 规则)+ 扫 `knowledge/**/*.md`。
**核心边界**:

- 默认只报告
- `--fix` 模式按问题级别分流(详见 prd §4.4 + design §4.4):
  - **确定性结构修复直接 patch 应用**,`log.md` 追加 `**LintFix**` 条目:frontmatter 字段补缺 / 类型强转 / `## 摘要` 残留转 `summary` / sources/analyses 缺 3 节骨架 H2 占位
  - **wikilink 是一等公民(Q6)**:plugin 正文写 `[[page]]` / `[[page|显示]]` / `[[page#章节]]`,Obsidian 原生双链 / Karpathy 老 wiki 兼容;**OKF 兼容靠 frontmatter `links:` 镜像字段自动同步**(详见 design §3.6.2):lint 检测正文 wikilink 增减时告警,`--fix` 自动重生成 `links:`
  - **语义级问题仅输出提案**(不应用):矛盾 / 命名飘合并 / 漏链 / 陈旧页处理
- 无 `--fix` 时不静默改文件;`--fix` 模式也不静默应用语义级修改
- lint 规则全集见 SCHEMA.md §6 + design.md §4.4(含 LLM 命名飘 / 陈旧 / frontmatter / 摘要小节残留)

#### B5:`/aeps-llm-wiki-synthesize` SKILL.md

对应 prd.md §4.5,设计见 design.md §4.5(synthesize 段)。
必读:`knowledge/index.md` + topic 相关页。
**核心边界**:

- 路径:`knowledge/syntheses/<topic-slug>.md`,不带时间戳,常驻
- 范围:所有 entity/concept 页 + 引用它们的 source 页(LLM 决定边界)
- 重复触发同 topic → 更新而非新建(同 slug 覆盖)

### 阶段 C:测试用例(预计 1-2 天,CLAUDE.md 硬约束)

按 AC 清单编写可执行测试。每条 AC 一组测试用例。

**测试组织**:`tests/` 下的测试脚本包括但不限于 [design §6.1](../src/design.md) 列出的三个核心脚本:

| 脚本                                     | 用途                                                                                                    | 对应阶段 C 子段                            |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| `tests/test_templates.py`              | 每份`templates/*.md` 渲染后 frontmatter 合规                                                          | C1(模板锁验证)+ C5(模板填充验证)           |
| `tests/test_frontmatter_compliance.py` | 模拟各种 §A~§D frontmatter 输入,断言 OKF 字段识别正确 + jsonschema 校验                               | C5(AC-5)+ C4.1(`--fix` frontmatter 修复) |
| `tests/test_okf_compliance.py`         | 用[input/google-OKF/OKF-SPEC.md](../../input/google-OKF/OKF-SPEC.md) 的 OKF 校验规则反向校验 plugin 产物 | COMPAT-1(§7.3)+ M5 端到端                 |

**本阶段其他子段**(C1~C14 + M-V1/M-V2)的测试用例可以**直接用 pytest 函数写在上面三个脚本里**,也可以拆成 `tests/test_<scenario>.py`(`test_init_vault.py` / `test_ingest_pipeline.py` / `test_query_ranking.py` / `test_lint_rules.py` / `test_requirements_txt.py` 等)。**不强求一一对应**,按 fixture 复用度自定。

**scripts/ 与 tests/ 一律 Python 3.10+ 单栈**:tests/ 跑 `pytest`,断言 `scripts/*.py` 内容(原 Node 18+ .mjs 设计已切到 Python,见 design §1.4 + §2.4)。

#### C1:AC-1(init 首次 5 分钟建齐)

- [ ] 临时目录跑 init,验证 `inbox/`、`raw/`(15 子目录 + .gitkeep)、`knowledge/`(SCHEMA.md / index.md / overview.md / glossary.md / log.md + 14 子目录 + .gitkeep)都建好
- [ ] `raw/` 下 4 份字典复制完整
- [ ] `knowledge/SCHEMA.md` 占位符全部替换(用户项目目录名 / actor 字符串)

#### C2:AC-2(ingest inbox/OKF-SPEC.md 产出 ≥ 5 概念页)

- [ ] 准备 fixture:把 `input/google-OKF/OKF-SPEC.md` 复制到 fixture 的 `inbox/`
- [ ] 跑 `/aeps-llm-wiki-ingest`(无参数),验证产出 ≥ 5 个 `concepts/<子类>/*.md`
- [ ] `index.md` 自动反映新增

#### C2.1:AC-2 扩展(文件类型分流)

- [ ] fixture 准备 `inbox/` 含: `.md` / `.txt` / `.pdf` / `.docx` / `.xlsx` / `.pptx` / `.png` 各一份
- [ ] 跑 ingest,验证每份都生成对应的 `knowledge/sources/<basename>.md`(OCR 类需 paddleocr 装好)
- [ ] 验证转换日志(`log.md` 里的 Action 条目)分别记"直接读 / Claude converter / anydoc 降级 / paddleocr"
- [ ] 故意放一个 `.bin` 或未知扩展名,验证 FAIL + 提示"未支持的扩展名"

#### C2.2:依赖未装场景

- [ ] fixture 在虚拟环境卸载 paddleocr / anydoc,跑 ingest 含 `.png` / `.pdf` 的 inbox
- [ ] 验证 SKILL.md 跑前就提示"请先 pip install -r scripts/requirements.txt",**不**中途才报错

#### C2.3:inbox 递归子目录

- [ ] fixture 在 `inbox/notes/s32g/` 下放两个 `.md` 文件
- [ ] 跑 ingest,验证两个文件都被处理(子目录文件路径作为 LLM 分类依据之一,raw_category 派生按最终 raw 路径,与 inbox 子目录无关)

#### C2.4:三阶段并发处理(N ≥ 2 + batch OCR + 收尾合并)

- [ ] **batch OCR 单次冷启动**:fixture inbox 放 5 份 `.png`(每份 1-3s OCR 时间);mock paddleocr 加载计数,验证 convert-to-md.py --batch 只调 1 次 Engine 初始化(N=5 个文件 → 冷启动 = 1 次,**不是** 5 次)
- [ ] **单文件场景跳过阶段 2**:fixture inbox 放 1 份 `.md`;验证 SKILL.md 直接走主 agent 完整流程,**不**派 subagent(避免派发开销)
- [ ] **subagent 并发上限 ≤ 5**:fixture inbox 放 12 份 `.md`;验证派发的 subagent 数 = min(12, 5) = 5,每批 ≤ 5 个 subagent 共享 N/5 份文件
- [ ] **阶段 2 不写 knowledge/**:fixture inbox 放 3 份 `.md`;验证 subagent 只产出 `temp/<doc-id>-proposal.json`,**不**直接写 `knowledge/sources/` / `index.md` / `log.md`(并发写冲突检测)
- [ ] **阶段 3 命名飘仲裁**:fixture inbox 放 2 份 `.md`,subagent 提议 `raw/03_芯片` + `raw/芯片_v2`(均与已有 `raw/02_芯片/` Levenshtein ≤ 2);验证主 agent 收尾时**强制合并**到 `raw/02_芯片/`,**不**新建漂移目录
- [ ] **阶段 3 concept 去重**:fixture inbox 放 2 份 `.md`,subagent 抽 concept "AUTOSAR" + "Autosar"(同义);验证主 agent 收尾时按 aliases 合并到 1 页,**不**生成 2 个 concept 页
- [ ] **log.md 不冲突**:fixture inbox 放 5 份;验证 `log.md` 只追加 1 段 (按日期 heading 汇总 N 条 `**Migration**` / `**Creation**`),**不**并发 5 段写入
- [ ] **Bash timeout = 600000**:SKILL.md 调 convert-to-md.py --batch 必须显式 `timeout: 600000ms`(模拟超过 30s 默认 timeout 不报错)
- [ ] **冷启动时间断言**:fixture 5 份 `.png` + 1 份 `.pdf`,跑 batch 模式;断言脚本 wall-clock 启动 + 处理总时间 < (5 × 30s) — 必须**显著小于**串行调用 N 次的耗时
- [ ] **Q11 subagent 写权隔离**(详见 design §4.2.1 写权矩阵):
  - [ ] fixture inbox 放 3 份相关 `.md`(会抽到重叠 entity/concept);验证 subagent 跑完后,`knowledge/` 下**任何文件均未被修改**(包括 index.md / glossary.md / log.md / overview.md / sources/ / entities/ / concepts/);只有 `temp/<id>-proposal.json` 新增
  - [ ] fixture 同上,跑完整 ingest 走阶段 3;验证 `knowledge/index.md` / `glossary.md` / `log.md` / `overview.md` 在所有 source/entity/concept 页写完后**才**统一修改一次(快照对比 — 阶段 3 收尾后这些文件 mtime 接近)
  - [ ] fixture 同名 entity 跨 subagent 重复抽取(如 subagent A 抽 "ISO 26262",subagent B 抽 "ISO26262");验证阶段 3 合并到 1 页 + aliases 累加,不重复建页
  - [ ] **subagent prompt 硬约束扫描**:fixture 提供一个故意违反的 SKILL.md 子代理 prompt(如包含 "请直接修改 knowledge/index.md");验证 SKILL.md 的 M3 review 流程拒绝该 prompt(subagent 必须只允许写 temp/<id></id>-proposal.json)
- [ ] **v0.5.4 PATCH Proposal JSON Schema 强校验 + 损坏降级**(详见 design §4.2.1 阶段 3 收尾前):
  - [ ] 写 `tests/test_proposal_schema_valid.py`:fixture 写一份合规 proposal JSON(含 file / suggested_subdir / raw_category / format / converter / native_text / converted_path / concepts 8 必填字段 + _meta 元数据)→ 跑 ingest → 断言 (a) `jsonschema.validate()` 通过;(b) 字符集清洗后写入 `temp/<id>-proposal.json.sanitized`;(c) 进入阶段 3 正常合并流程
  - [ ] 写 `tests/test_proposal_schema_invalid_missing_field.py`:fixture proposal 缺 `suggested_subdir` 字段 → 跑 ingest → 断言 (a) `jsonschema.ValidationError` 抛出(必填缺失);(c) **触发降级**——主 agent 单线程重跑该文件;(d) 重跑结果若合规 → 进入合并,否则标记 ingest 失败
  - [ ] 写 `tests/test_proposal_schema_invalid_enum.py`:fixture `format: "exe"`(不在 enum 白名单)→ 跑 ingest → 断言 (a) `ValidationError` 触发;(b) 走降级路径
  - [ ] 写 `tests/test_proposal_json_decode_error.py`(关键集成测试):fixture 故意把 proposal JSON 末尾 `}` 删除(模拟 LLM 输出截断)→ 跑 ingest → 断言 (a) `json.JSONDecodeError` 抛出;(b) **不**阻断整批 ingest —— 其他正常 proposal 继续合并;(c) 损坏文件 inbox 原文件**保留**(后续用户手动重 ingest);(d) 主 agent 退出 0
  - [ ] 写 `tests/test_proposal_control_chars_strip.py`:fixture proposal.concepts[0].name 含 `\x00` NUL + `\x1f` 单元分隔符 + BOM + `</script>` 注入字面量 → 跑 ingest → 断言 (a) `jsonschema.validate` 通过(字符本身在 string 范围内);(b) 字符集清洗函数 strip 控制字符(BOM 保留,其他 strip);(c) `</script>` 替换为 `<\/script>`(避免下游 web 渲染);(d) 清洗后 JSON 写入安全版本
  - [ ] 写 `tests/test_proposal_truncation_detect.py`:fixture proposal.concepts 数组 250 条(`maxItems: 200` 超限)→ 跑 ingest → 断言 (a) `ValidationError`(maxItems 超限)触发;(b) 走降级路径
  - [ ] 写 `tests/test_proposal_failure_log_only.py`(**关键集成测试,不阻断整批**):fixture inbox 放 3 份文件 + 故意让其中 1 份(`temp/notes.md-proposal.json`)损坏(JSONDecodeError)+ 其他 2 份正常 → 跑完整 ingest → 断言 (i) 其他 2 份正常进入 `knowledge/sources/` + 对应 entities/concepts + `log.md` 追加 `**Migration**` 行;(ii) 损坏那份 inbox 原文件 `inbox/notes.md` 保留(未 mv 到 raw/);(iii) `knowledge/log.md` 末尾追加 `**IngestFailure**` 段(NEW 段,不在原 9 步串行清单里)含 `proposal_path: temp/notes.md-proposal.json` + `exception_type: JSONDecodeError` + `exception_message: ...`;(iv) 主 agent 退出 0(整批不阻断);(v) `temp/notes.md-proposal.json.corrupt.bak` 备份存在(供用户人工排查)
  - [ ] 写 `tests/test_proposal_retry_main_agent_single.py`(**关键集成测试,降级路径**):fixture proposal 损坏 → 跑 ingest → 断言 (a) **不**再派 subagent 重试(避免同样的 JSON 损坏模式);(b) 主 agent **单线程**重跑该文件 LLM 抽取(走 §4.2 单文件分支);(c) 重跑结果合规 → 进入合并;(d) 若重跑仍失败 → 标记跳过 + `**IngestFailure**` 段;(e) retry 限额 1 次(防止 token 耗尽)

#### C3:AC-3(query 不编造)

- [ ] 准备 fixture:已知 wiki 内容
- [ ] 跑 query 问已知答案 → 答对 + 链接
- [ ] 跑 query 问 wiki 里没有的内容 → 显式声明"未找到"而非编造

#### C3.1:query 4 跳扫描(< 500 页)

- [ ] fixture wiki 50 页,跑 `/aeps-llm-wiki-query "<已知答案>"`,验证走 4 跳:
  - 跳 1:index.md 命中 N 个候选
  - 跳 2:候选页 description/summary 给出答案
  - 跳 3:候选页的 `[[wikilink]]` 跳邻居,邻居页参与回答
  - 跳 4:glossary.md 提供术语消歧
- [ ] fixture query 关键词命中 index 条目 frontmatter `tags` 的,验证该条目优先入选(top-K)

#### C3.2:query qmd 分流(500 ≤ N < 1000)

- [ ] fixture wiki 600 页,qmd 已装,跑 query → 验证 `qmd query` 被调用
- [ ] fixture wiki 600 页,qmd 未装,跑 query → 验证降级走 index + 4 跳,并提示"推荐装 qmd"

#### C3.3:query qmd 强约束(N ≥ 1000)

- [ ] fixture wiki 1100 页,qmd 未装,跑 query → 验证直接报错退出,提示"必须装 qmd",**不**进入回答
- [ ] fixture wiki 1100 页,qmd 已装,跑 query → 正常返回 qmd top-20 命中

#### C3.4:check-qmd.py 单测

- [ ] 单元测 `<500 / 500~1000 / ≥1000` 三种 pageCount 边界
- [ ] qmd 在 / 不在两种组合 → 共 6 种 case,验证返回 `engine` 字段正确

#### C4:AC-4(lint 全规则)

- [ ] 准备 fixture:故意造孤儿页 / 矛盾页 / 陈旧页(`stale_after` 早于 today)/ 缺必填 frontmatter / 含 `## 摘要` 小节 / 命名飘(`soc-design` vs `socke-design`)
- [ ] 跑 lint,验证每条都报
- [ ] **C4.1 lint --fix 确定性 vs 语义分流**:
  - [ ] 确定性结构修复 fixture:造缺 frontmatter `type` / `tags` 不是 list / `## 摘要` 小节 / sources 缺 3 节骨架 各一份 → 跑 `--fix` → 验证文件被改 + log.md 追加 `**LintFix**` 条目
  - [ ] 语义级问题 fixture:造矛盾页 + 命名飘子目录 + 漏链 + 陈旧页 → 跑 `--fix` → 验证**文件未被改**,只输出提案(包含候选改写 / `git mv` 命令 / 候选链接列表 / 陈旧处理建议)
- [ ] **C4.2 frontmatter `links:` 镜像同步**(详见 design §3.6.2):
  - [ ] 写 `tests/test_links_mirror_generation.py`:fixture 写一份页含正文 wikilink `[[concept/a]]` + `[[entity/b]]`,跑 ingest / lint --fix → 验证 frontmatter `links:` 自动生成 2 条对应 `{type: wikilink, target: ...}` 条目
  - [ ] 写 `tests/test_links_mirror_drift.py`:fixture 故意把 frontmatter `links:` 加一条 ghost(target 不在正文)→ 跑 lint → 验证告警 WARN + `--fix` 自动重生成 `links:` 抹掉 ghost
  - [ ] 写 `tests/test_links_mirror_obsidian_edit.py`:fixture 模拟用户 Obsidian UI 加 wikilink(正文有,frontmatter `links:` 漏)→ 跑 lint → 验证告警 + `--fix` 同步
  - [ ] 写 `tests/test_links_mirror_types.py`:fixture 含正文 `[text](path.md)` markdown 链接 → 跑 ingest → 验证 frontmatter `links:` 含 `{type: markdown, target: path.md}` 条目
  - [ ] 写 `tests/test_links_mirror_idempotent.py`(**Q7 Round 7 新增**,Set 比对规则):fixture 写一份页 frontmatter `links: [A, B]`(顺序 A→B)+ 正文 wikilink `[[B]]` + `[[A]]`(顺序 B→A)→ 跑 lint → **不告警**(Set 相等)、`--fix` **不重写**文件(content hash 不变 + mtime 不变);正反两次跑结果完全相同(幂等)
  - [ ] 写 `tests/test_links_mirror_preserves_updated_and_mtime.py`(**Q7 Round 7 新增**,死循环防护):fixture 造一份页 frontmatter `updated: 2026-01-01T00:00:00Z` + 故意把 `links:` 加 ghost → 跑 lint --fix → 断言 (a) `updated` 字段值不变;(b) 文件 mtime 在 fix 前后保持相等(`os.stat().st_mtime` 一致);(c) log.md 追加 `**LintFix**: links-mirror-sync ...` 不含 `updated` 字段字样(暗示业务时间未受影响)
  - [ ] 写 `tests/test_links_mirror_preserves_atime_and_mtime.py`(**Q7 Round 13 v0.5.3 PATCH 新增**,修复缺陷 5,atime + mtime 双还原):fixture 同上 → 跑 lint --fix → 断言 (a) `os.stat(path).st_atime` 与 fix 前**完全相等**(浮点精度 1e-6 容差);(b) `os.stat(path).st_mtime` 与 fix 前**完全相等**;(c) 用 `monkeypatch` 监视 `os.utime` 调用,断言 lint 代码路径中**确实调用** `os.utime(path, (original_atime, original_mtime))` 至少一次,参数是二元组(不允许只传 mtime 不传 atime);(d) 断言 fix 前后 content hash 完全相等(说明 `links:` 同步是 no-op,业务无变更)
  - [ ] 写 `tests/test_links_mirror_utime_flow_order.py`(**Q7 Round 13 v0.5.3 PATCH 新增**,流程性 fixture):fixture 同上 + 用 `monkeypatch` 包装 `os.stat` / `Path.write_text` / `os.utime` 三个调用并记录顺序 → 断言调用顺序严格为 `stat → write_text → utime`(四步流程,design §3.6.2 行 1199-1201);**反例测试**:故意把 fixture 中 `os.utime` 替换成 no-op(模拟"只 write 不 utime"的实现错误)→ 跑 lint --fix → 断言 `mtime` 必变(说明测试有效)+ `utime` 未被调用(说明实现漏掉了第 3 步)
  - [ ] **C4.3 Link Normalizer 解析规则**(详见 design §3.6.2,v0.3.2 新增):
    - [ ] 写 `tests/test_links_normalizer_alias.py`:fixture 正文 `[[NoteName|Alias]]` + frontmatter `links: [{type: wikilink, target: NoteName}]` → 跑 lint → **不告警**(别名已剥离,不进比对)
    - [ ] 写 `tests/test_links_normalizer_anchor.py`:fixture 正文 `[[NoteName#section]]` + `links: [{type: wikilink, target: NoteName}]` → 跑 lint → **不告警**(锚点剥离且不进 links:);fixture 含 2 处不同锚点同 Note → 跑 lint → **不告警**(去重后 Set 相等)
    - [ ] 写 `tests/test_links_normalizer_path_prefix.py`:fixture 正文 `[[entities/person/foo]]` + `links: [{type: wikilink, target: entities/person/foo}]` 与 `[[foo]]` + `links: [{type: wikilink, target: foo}]` 两份页混合 → 跑 lint 全局图扫描 → Set 比对后应**指向同一节点**(basename 等价);写入 frontmatter 时**保留原始路径**(OKF 兼容需要)
    - [ ] **反例测试**:fixture 正文 `[[NoteName|Alias]]` 与 frontmatter `links: [{type: wikilink, target: NoteName|Alias}]`(实现错误地把别名当 target)→ 跑 lint → 断言 **FAIL** + 报告"`Alias` 是显示文本,不应进比对 key"
  - [ ] **C4.4 Lint --fix 安全锁**(详见 design §5.4,v0.3.2 新增):
    - [ ] 写 `tests/test_lint_fix_dry_run.py`:fixture 含 3 个待修复文件 → 跑 `lint.py --fix`(无 `--apply`)→ 断言 (a) 3 个文件**未被修改**(mtime + content hash 双双不变);(b) 报告输出每文件的 diff 提案;跑 `--fix --apply` → 断言 3 个文件**被修改**
    - [ ] 写 `tests/test_lint_fix_transactional.py`:fixture 含 5 个待修复文件,故意在第 3 个文件注入 frontmatter schema 校验失败 → 跑 `lint.py --fix --apply` → 断言 (a) 0 个文件被修改(全部回滚);(b) 报告指出"图结构预检失败 / 校验失败" + 失败文件名 + 行号
    - [ ] 写 `tests/test_lint_fix_git_dirty_guard.py`:fixture 在 git 仓库 + 工作区脏状态(故意改 1 个文件不 commit)→ 跑 `lint.py --fix --apply` → 断言 (a) 退出非 0;(b) 报告"工作区有未提交改动,请先 commit 或 stash";跑同命令加 `--allow-dirty` → 断言 (a) 退出 0;(b) 报告注明"已忽略脏状态检查";fixture 在 git 仓库 + 工作区干净 → 跑 `--fix --apply` → 断言 (a) 写入成功;(b) 写入前自动 `git stash push` 创建快照(可在 stash list 找到 `lint-fix-pre-snapshot`)

#### C5:AC-5(frontmatter 自动校验)

- [ ] 写 Python 脚本 `tests/test_frontmatter_schema.py`,对所有 fixture `knowledge/**/*.md` 跑 jsonschema 校验
- [ ] 任何不合规立刻 FAIL
- [ ] **C5.1 source 页双字段同源断言**(详见 design §3.6.1.1):
  - [ ] fixture 造 `type: source` 页:`source_file: raw/02_芯片/foo.pdf` + `sources[0].resource: raw/02_芯片/foo.pdf` → 跑 lint → 通过
  - [ ] fixture 改 source_file 与 sources[0].resource 值不一致(如 source_file 指向 foo.pdf,sources[0].resource 指向 bar.pdf)→ 跑 lint → FAIL
  - [ ] fixture 缺 source_file 或 sources[0].resource 任一字段 → 跑 lint → FAIL
  - [ ] 写 `tests/test_source_obsidian_link.py`:fixture 在 Obsidian 笔记属性面板里 source_file 字段值渲染为可点击链接(由 jsonschema 校验该字段存在 + 值符合 `raw/<subdir>/<basename>.<ext>` 正则)

#### C13:G10 外部转换副本入 raw + 源页 link 指副本(详见 prd §4.2 M1-M4 + design §4.2 + design §4.2.1)

- [ ] **C13.1 `convert-to-md.py --batch --emit-to` 双产物落盘**(G10 M1 + M4):
  - [ ] 写 `tests/test_convert_emit_to_pdf.py`:fixture `inbox/iso26262.pdf` + `inbox/someip-spec.pptx` + `inbox/notes.md`,跑 `python3 scripts/convert-to-md.py --batch <...> --emit-to temp/`,断言:
    - (a) `temp/iso26262.md` + `temp/iso26262.pdf.converted.md` 同时存在(走 anydoc)
    - (b) `temp/someip-spec.md` + `temp/someip-spec.pptx.converted.md` 同时存在(走 claude-native / 降级 anydoc)
    - (c) `temp/notes.md` 存在(`notes.md.converted.md` **不**存在,native_text: true)
    - (d) 单文件模式 `--emit-to temp/ iso26262.pdf` 也按 (a) 输出(向后兼容)
  - [ ] 写 `tests/test_convert_emit_to_image.py`:fixture `inbox/screenshot.png`,跑 `--batch --emit-to temp/`,断言 `temp/screenshot.png.converted.md` 存在(paddleocr)
  - [ ] 写 `tests/test_convert_emit_to_failure.py`:fixture 故意造一个空 .pdf(anydoc 解析失败)→ 跑 --batch --emit-to → 断言 (a) **不**生成 `*.pdf.converted.md` 空副本;(b) 退出非 0;(c) inbox 原文件保留
- [ ] **C13.2 safe-mv 双文件迁移**(G10 M1):
  - [ ] 写 `tests/test_safe_mv_dual_file.py`:fixture (a) `inbox/iso26262.pdf` + `temp/iso26262.pdf.converted.md`(G10 适用)+ (b) `inbox/notes.md` + 无 .converted.md(纯文本);写两份 `temp/decision-*.json`;跑 `safe-mv.py --apply`;断言:
    - (a) `raw/<subdir>/iso26262.pdf` + `raw/<subdir>/iso26262.pdf.converted.md` 同时存在;`inbox/iso26262.pdf` + `temp/iso26262.pdf.converted.md` 已删
    - (b) `raw/<subdir>/notes.md` 存在;`notes.md.converted.md` **不**被创建;`inbox/notes.md` 已删
    - (c) `log.md` 追加 3 行:1 条 `**Migration**: inbox/iso26262.pdf → raw/<subdir>/iso26262.pdf` + 1 条 `**Converted**: raw/<subdir>/iso26262.pdf.converted.md (via anydoc)` + 1 条 `**Migration**: inbox/notes.md → raw/<subdir>/notes.md`(无 Converted 行)
- [ ] **C13.3 源页 frontmatter G10 四字段 + links 镜像**(G10 M2 + M3):
  - [ ] 写 `tests/test_source_frontmatter_g10_fields.py`:fixture 跑 ingest `inbox/iso26262.pdf` → 验证生成的 `knowledge/sources/iso26262.md` frontmatter 含:
    - (a) `format: pdf` + `converter: anydoc` + `native_text: false`
    - (b) `converted_path: raw/<subdir>/iso26262.pdf.converted.md`
    - (c) `links: ["[[iso26262.pdf.converted]]"]`
    - (d) `source_file: raw/<subdir>/iso26262.pdf`(仍指原文件,**不**指 md 副本;Q9 兼容)
  - [ ] 写 `tests/test_source_frontmatter_g10_native.py`:fixture 跑 ingest `inbox/notes.md` → 验证 `format: md` + `converter: null` + `native_text: true` + `converted_path: null` + `links: ["[[notes]]"]`
  - [ ] 写 `tests/test_source_frontmatter_g10_consistency.py`(lint C13 强校验):fixture 故意造 frontmatter 三元组不一致:
    - (i) `native_text: true` + `converter: anydoc`(矛盾)→ 跑 lint → FAIL + 报告"native_text 与 converter 不一致"
    - (ii) `native_text: false` + `converted_path: null`(矛盾)→ 跑 lint → FAIL + 报告"缺 md 副本路径"
    - (iii) `native_text: false` + `converted_path: raw/<subdir>/foo.pdf`(与原文件名不匹配)→ 跑 lint → WARN + 报告"converted_path 与 source_file basename 不一致"
    - (iv) `native_text: true` + `converted_path: raw/<subdir>/foo.md.converted.md`(矛盾)→ 跑 lint → FAIL
- [ ] **C13.4 links 镜像含 .converted 后缀 + 正文原始来源行**(G10 M3):
  - [ ] 写 `tests/test_links_mirror_for_converted.py`(扩 §C4.2):fixture 跑 ingest `inbox/iso26262.pdf` → 验证:
    - (a) frontmatter `links: ["[[iso26262.pdf.converted]]"]`(走 wikilink 解析后 target = `iso26262.pdf.converted`)
    - (b) 正文 `## 重点摘录` 末尾行 `> 原始来源:[[iso26262.pdf.converted]]`
    - (c) 跑 lint → **不告警**(links[0] 与正文 `> 原始来源` 一致,Set 相等,Q7 死循环防护规则生效)
  - [ ] 写 `tests/test_links_mirror_for_native.py`:fixture 跑 ingest `inbox/notes.md` → 验证 frontmatter `links: ["[[notes]]"]` + 正文 `> 原始来源:[[notes]]`(纯文本走 basename,**不**带 `.converted` 后缀)
  - [ ] 写 `tests/test_links_mirror_drift_converted.py`:fixture 故意把 frontmatter `links: ["[[wrong-name]]"]`(与正文 `> 原始来源:[[iso26262.pdf.converted]]` 不一致)→ 跑 lint → WARN + `--fix` 自动同步(`links: ["[[iso26262.pdf.converted]]"]`)
- [ ] **C13.5 历史归档兼容**(G10 不强制历史补建):
  - [ ] 写 `tests/test_g10_historical_compat.py`:fixture 模拟 v0.3.1 历史 wiki ——`raw/<subdir>/old-spec.pdf` 存在但**无** `old-spec.pdf.converted.md`;对应 source 页 frontmatter `native_text: false` + `converted_path: null`(旧版未填);跑 lint → **WARN**(不是 FAIL):"该 source 缺 md 副本,请把原文件 `cp` 回 inbox/ 走 ingest 补建";不阻塞 plugin 运行
- [ ] **C13.6 重转策略拒绝**(G10 不开重转入口):
  - [ ] 写 `tests/test_g10_no_reconvert.py`:fixture 已存在 `raw/<subdir>/iso26262.pdf` + `raw/<subdir>/iso26262.pdf.converted.md`;模拟用户跑 `--emit-to` 试图覆盖 .converted.md → 断言 **FAIL** + 报告"raw/ 不可变 + G7 原则 + Q5 + G10;如需重转请把原文件 cp 回 inbox/ 走标准 ingest"

#### C6:AC-6(ingest inbox 拍板门)

- [ ] fixture 在 `inbox/<file>`,跑 `/aeps-llm-wiki-ingest`,验证未拍板前 inbox 文件不动
- [ ] 用户拍板后,文件出现在 `raw/<subdir>/`,`inbox/<file>` 删除,`log.md` 记 Migration

#### C7:AC-7(--raw-subdir inbox 直迁)

- [ ] fixture 在 `inbox/<file>`,跑 `/aeps-llm-wiki-ingest --raw-subdir=<已存在 15 类>`,验证无交互直迁 + log 记路径

#### C8:AC-8(ingest inbox 空)

- [ ] fixture 的 `inbox/` 为空,跑 `/aeps-llm-wiki-ingest`,验证提示"inbox/ 为空,先把资料丢进 inbox 再跑",退出码 0

#### C9:陈旧 + 命名飘专项

- [ ] 造 fixture:`stale_after: 2025-01-01`(早已过期),lint 标陈旧
- [ ] 造子目录:`raw/02_芯片/` + `raw/03_芯片_v2/`,lint 命名飘提示
- [ ] **C9.1 命名飘前移到 ingest**:fixture 已存在 `raw/02_芯片/`,丢一份 `s32g-datasheet.pdf` 到 inbox,跑 ingest,验证 LLM 提议的子目录若写成 `03_芯片` / `芯片_v2` / `soc_chips`(与已有 `02_芯片` Levenshtein ≤ 2 或同义拼写),会被检测并**强制改用 `raw/02_芯片/`**,而不是新增

- [ ] **C9.2 comparison 路径 B 高频检索触发**(详见 prd §4.6 + design §3.4 query 落档 log 模板):
  - [ ] fixture:`knowledge/log.md` 已有 3 条 `**Creation**: query "SOME/IP vs DDS"` + `**Creation**: query "SOME/IP vs DDS latency"` + `**Creation**: query "SOME/IP vs DDS over TCP"`(累计 ≥ 3 次 "X vs Y" 型 query)
  - [ ] 跑下一次 `/aeps-llm-wiki-query "SOME/IP vs DDS 性能对比"`,触发落档询问 → 验证 SKILL.md **提议**建 `knowledge/comparisons/some-ip-vs-dds.md`(只提一次)
  - [ ] **反例 1**:fixture `log.md` 含 3 条 `**Update**: ... query ... "X vs Y"`(旧版用 Update 写的)→ 跑同一 query → 验证**不**触发路径 B(因为正则要求 `**Creation**` 不是 `**Update**`,避免旧数据 silently 误触发)
  - [ ] **反例 2**:fixture `log.md` 含 2 条 `**Creation**: query "SOME/IP vs DDS"` + 1 条不带 query 标记的 `**Creation**` → 跑 query → 验证**不**触发(不足 3 次匹配)

#### C10:NFR-1 + NFR-4(无 daemon + 无绝对路径)

**CLAUDE.md 硬约束 + PRD NFR-1 + NFR-4**:plugin 不开 daemon + 代码中不得使用绝对路径。

- [ ] `tests/test_no_absolute_paths.py`:扫所有 `scripts/*.py` + `skills/*/SKILL.md` + `templates/*.md` + `schema/*.yaml`,断言**不出现**以下模式:
  - 绝对 Unix 路径:`/(Users|home|tmp|opt)/...`、`/etc/...`、`/var/...`
  - 绝对 Windows 路径:`C:\` / `D:\` / `E:\`(任意盘符)
  - plugin 反向引用:`${CLAUDE_PLUGIN_ROOT}`(scripts/ 内禁用,hooks/ 内允许,见 design §1.4)
  - 显式 home:`~/.claude/...` / `~/.config/...`
- [ ] `tests/test_no_daemon.py`:扫 `scripts/*.py`,断言**不出现**:
  - `http.server.HTTPServer` / `socketserver.TCPServer` / `http.server.BaseHTTPRequestHandler`(Python 服务接口)
  - `subprocess.Popen(` 启动**长生命周期**子进程(单次 `subprocess.run` 允许)
  - `signal.signal(` + 阻塞 loop(`while True:` + `time.sleep()` 之类)
  - **C10.1 scripts/ 严禁交互(Q10,详见 design §1.4 硬契约)**:
    - [ ] 用 `ast` 模块扫所有 `scripts/*.py`,断言不出现以下调用(**含非 TTY 管道在内一律禁止**,详见 design §2.4.1 "stdin 全禁原则"):
      - `input(` / `input (`(Python 内置 `input()` / `input(prompt)`)
      - `sys.stdin.read` / `sys.stdin.readline` / `sys.stdin.readlines`
      - `getpass.getpass` / `getpass(`
      - `select.select([sys.stdin]` 等 stdin 等待调用
    - [ ] **管道不豁免**:即便 `not sys.stdin.isatty()`,scripts 仍禁止从 stdin 读取 plan / decision / proposal / 配置;统一走 `--apply <filepath>` / `--output <path>` / `--config <path>` 显式文件参数(decision 模板参考 design §4.2.1)。AST 扫描**不**做 `isatty()` 判定门 —— 直接 FAIL。
    - [ ] fixture 反例测试:故意造一个 `scripts/_bad_example.py` 含 `input("拍板:")` → 跑 `tests/test_no_daemon.py` → 断言 **FAIL** + 报告指出文件路径与行号
    - [ ] fixture 正例测试:现有所有 `scripts/*.py` → 跑 `tests/test_no_daemon.py` → 断言 **PASS**
  - **C10.2 plan 文件格式硬约束(详见 design §4.2.x JSON schema)**:
    - [ ] 写 `tests/test_plan_json_schema.py`,断言所有 `temp/<type>-<hash>.json` 文件符合设计 schema:
      - 顶层 `schema_version` 字段必填,scripts 读到不认版本 → FAIL + 报错
      - proposal JSON `type: ingest_proposal` / `doc_id` / `source` / `raw_category_suggestion` / `decision_needed` 必填
      - decision JSON `type: ingest_decision` / `decided_at` / `actor` / `proposal_refs[]` / `actions[]` 必填
      - `actions[].op` 仅允许 `mv` / `mkdir` / `cp` / `write_file`(枚举)
      - **反例测试**:造一个 `temp/proposal-test.json` 缺 `schema_version` → 跑 `safe-mv.py --apply temp/decision-test.json` → 断言 FAIL + 报告"missing schema_version field"
      - **反例测试**:造一个 `temp/decision-test.json` 含 `op: rm`(不允许的操作)→ 跑 scripts → 断言 FAIL
      - **反例测试**:造一个 `temp/proposal-test.json` `schema_version: "0.9"`(scripts 只认 1.0+)→ 跑 → 断言 FAIL + 报告"unsupported schema_version"
    - [ ] 写 `tests/test_decision_apply_idempotent.py`:同一 `decision-<hash>.json` 跑两次 → 第二次应判定 no-op 并退出 0,避免重跑误操作
  - `sys.stdin` 长时间读取 / `signal.pause()` 阻塞
- [ ] 全部断言通过 → PASS;任意一条命中 → FAIL + 列出文件:行号 + 命中字符串

#### C11:NFR-3(中文为主 + 术语英文)

- [ ] `tests/test_chinese_first.py`:抽查以下文件的**正文**字符占比:
  - `skills/*/SKILL.md`(5 份)
  - `templates/*.md`(5 份)
  - `prd.md` / `design.md` / `implement.md`(3 份,内部维护文档同样遵循)
- [ ] 断言:中文字符(Unicode 范围 `\u4e00-\u9fff`)占**总可读字符数**(去除空白 + Markdown 控制符)的 > 60%
- [ ] 例外:代码块(`` ``` `` 包裹的内容)、frontmatter YAML 块、frontmatter schema.yaml 不计入
- [ ] 术语保留英文(`type: source` / `raw_category` / `bundle-root` 等)**不**翻译,本测试只看语言比例不查翻译

#### C12:NFR-5(临时文件进 `temp/`)

- [ ] `tests/test_gitignore_temp.py`:验证 `temp/` 出现在 `.gitignore`
- [ ] `tests/test_temp_dir_usage.py`(运行时验证):fixture 跑一遍 init + ingest,检查**临时目录**只创建在 `<project>/temp/` 下,**不**在 `/tmp/` / `C:\Users\...\AppData\Local\Temp\` 等系统临时目录
- [ ] `scripts/convert-to-md.py` / `scripts/check-qmd.py` 输出临时 md 文件 → 必须在 `temp/`(可通过 grep `--output temp/` 断言调用约定)

#### C13:NFR-6(LICENSE = Apache 2.0)

- [ ] `tests/test_license.py`:验证:
  - `LICENSE` 文件存在
  - 文件首 50 行包含 `Apache License` / `Version 2.0` / `Licensed under the Apache License` 之一
  - 包含完整 Apache 2.0 必备条款(Grant of Copyright License / Grant of Patent License / Redistributions / 等等关键短语)
- [ ] 校验脚本可选:`tests/test_license.py` 用 regex 抓"Apache 2.0 + 关键短语 ≥ 5 处"作为最低门槛

#### C14:NFR-7(`scripts/requirements.txt` 依赖清单)

- [ ] `tests/test_requirements_txt.py`:
  - `scripts/requirements.txt` 存在
  - 包含 `anydoc`(强依赖,对应 §4.2 .pptx/.docx/.xlsx/.pdf 降级)
  - 包含 `paddleocr`(强依赖,对应 §4.2 .png/.jpg/.jpeg/.bmp/.tiff OCR)
  - 包含 `jsonschema` + `pyyaml`(强依赖,对应 frontmatter schema 校验 + YAML 读写)
  - 包含 `pytest`(单测时需要;运行时不需要)
- [ ] 不强制 `qmd`(可选依赖,对应 §4.3 wiki 规模较大时降级),但若有 `qmd` 引用应在 README.md 单独标注"可选,`npm install -g @tobilu/qmd`"

#### C15:G11 query 落档分析专属骨架 + sources_used 必填 + gating(详见 prd §4.3 + design §3.6 + §4.3.2 + §5.4 C15)

- [ ] **C15.1 `tests/test_analysis_dedicated_skeleton.py`** —— M1 结构断层修复:
  - [ ] fixture 1:正确骨架(3 节齐全 `## 方案推演 / 架构分析` + `## 关联溯源` + `## 总结:最有收获的一句话`,不含 sources 风格 / `## 摘要` / `## Summary`)→ lint C15.1 PASS
  - [ ] fixture 2:缺 `## 关联溯源` → FAIL,lint 报告 `missing H2: ## 关联溯源`
  - [ ] fixture 3:含 `## 重点摘录`(sources 风格)→ FAIL,lint 报告 `forbidden H2: ## 重点摘录 (sources-style, use ## 方案推演 / 架构分析)`
  - [ ] fixture 4:含 `## 我的思考`(sources 风格)→ FAIL,lint 报告 `forbidden H2: ## 我的思考`
  - [ ] fixture 5:含 `## 摘要` → FAIL,lint 报告 `forbidden H2: ## 摘要 (use frontmatter summary)`
  - [ ] fixture 6:含 `## Summary` → FAIL,lint 报告 `forbidden H2: ## Summary`
  - [ ] fixture 7:`--fix --apply` 跑 fixture 2 → 自动追加占位 H2(空内容),`log.md` 含 `**LintFix**: lint-C15.1 on analyses/<file>.md — added placeholder H2`
- [ ] **C15.2 `tests/test_analysis_sources_used_required.py`** —— M2 溯源丢失修复:
  - [ ] fixture 1:`sources_used` 含 3 条已存在路径(`sources/foo.md` / `entities/person/bar.md` / `syntheses/topic.md`,fixture 预建)→ PASS
  - [ ] fixture 2:`sources_used` 字段缺失 → FAIL,lint 报告 `missing required field: sources_used`
  - [ ] fixture 3:`sources_used` 空数组 → FAIL,lint 报告 `sources_used must be non-empty array`
  - [ ] fixture 4:`sources_used` 含 1 条不存在的路径 `sources/missing.md` → FAIL,lint 报告 `path not found: sources/missing.md`
  - [ ] fixture 5:`sources_used` 含 `https://...` 或 `raw/...`(非 wiki 路径)→ FAIL,lint 报告 `path must be relative to knowledge/, got: <path>`
  - [ ] fixture 6:`--fix --apply` 跑 fixture 4(自动从 `## 关联溯源` 末尾 `> 引用:` 行 + query 阶段引用路径派生)→ `sources_used` 自动补正确路径,Q7 死循环防护断言:`updated` 字段值不变 + 文件 mtime 不变(stat 前后对比)
  - [ ] fixture 7:`--fix --apply` 跑 fixture 2 → `sources_used` 自动派生后,**断言** `updated` 字段值与 mtime 均未变
  - [ ] fixture 8:派生来源严格性断言:故意把 `## 关联溯源` 段正文里出现 `[[sources/unrelated.md]]` 但 `> 引用:` 行没有 → `--fix --apply` 后,**断言** `sources_used` 不含 `sources/unrelated.md`(禁止全文 grep 抽)
- [ ] **C15.3 `tests/test_query_gating_logic.py`** —— M3 Over-prompting 修复:
  - [ ] fixture 1:query 走 intent=overview(跨领域综述)+ 命中 ≥ 2 子目录源 + 回答 350 字 → query 输出末尾必须含 `❓` 触发 prompt + 字面 `是否落档为 analyses/<...>.md ?[Y/n]`
  - [ ] fixture 2:query 走 intent=comparison + 命中 ≥ 2 子目录源 + 回答 280 字 → 末尾必须含 `❓` 触发 prompt
  - [ ] fixture 3:query 走 intent=exact(单点查证)+ 命中 1 子目录 + 回答 80 字 → 末尾必须含 `💡` 跳过标记 + 字面 `跳过落档询问`
  - [ ] fixture 4:query 回答含 `Wiki 未覆盖此问题` → 末尾必须含 `💡` 跳过标记
  - [ ] fixture 5:query 走 intent=overview + 回答 50 字(< 200) → 末尾必须含 `💡` 跳过标记(不触发优先级 > 触发)
  - [ ] fixture 6:query 输出末尾既无 `❓` 也无 `💡` → lint C15.3 FAIL,report-only(语义级)
  - [ ] fixture 7:e2e 端到端:模拟同一 wiki 跑三种 query 类型(Exact 单点 / Overview 多源 / Comparison 对比),**断言** 落档询问输出与 gating 规则一致(Exact 无 prompt / Overview 必有 / Comparison 必有)
  - [ ] fixture 8(v0.5.2 PATCH,修复缺陷 1):query 走 intent=ambiguous(语义模糊,例:"这篇芯片文档和上一篇有什么异同?" 含"异同"对比倾向词 + "上一篇"指代模糊)→ LLM 阶段3推断无法稳定分类 → 走 `intent == "ambiguous"` 分支 → 末尾必须含 `💡` 跳过标记(v0.5.2 fallback 低扰动)
  - [ ] fixture 9(v0.5.2 PATCH):query 走 intent=ambiguous + 命中 2 子目录源 + 回答 350 字 → 仍然走 `intent == "ambiguous"` 跳过(intent 不触发优先级 > 触发,避免 ambiguous 误判被 sources_count / answer_length 兜底绕过)
  - [ ] fixture 10(v0.5.2 PATCH,冲突测试):query 含路径 C 触发词"异同"(v0.5.1 PATCH)+ 但 LLM 阶段3推断 intent=ambiguous(语义模糊)→ **断言** ambiguous 优先于词命中,走 `💡` 跳过;**路径 C 触发词清单不覆盖 fallback**
  - [ ] fixture 11(v0.5.2 PATCH):query 走 intent=other(无法归入 overview/comparison/exact/ambiguous)+ 命中 ≥ 2 子目录源 + 回答 ≥ 200 字 → 走触发条件 `sources_count_ge:2` 或 `answer_length_ge:200` → 末尾必须含 `❓` 触发 prompt(intent=other 走触发路径,仅 ambiguous 走跳过)
- [ ] **C15.4 `tests/test_analysis_sources_used_mirror.py`** —— `## 关联溯源` 末尾 `> 引用:` 行与 `sources_used` Set 比对:
  - [ ] fixture 1:一致(>` 引用:` 行 3 条 + `sources_used` 3 条完全相同)→ WARN 不触发
  - [ ] fixture 2:`sources_used` 多 1 条(`sources/extra.md`,fixture 预建) → WARN,lint diff 输出 `sources_used 中有但 > 引用行没有 = [sources/extra.md]`
  - [ ] fixture 3:`> 引用:` 行多 1 条(`sources/extra.md`) → WARN,lint diff 输出 `> 引用行中有但 sources_used 没有 = [sources/extra.md]`
  - [ ] fixture 4:`--fix --apply` 跑 fixture 3 → 自动把 `sources/extra.md` 补进 `sources_used`,**断言** `updated` 字段值与文件 mtime 均未变(Q7 死循环防护)

#### C15 派生脚本(必备)

- [ ] `scripts/migrate-analysis-skeleton.py` —— G11 v0.5.0 升级迁移脚本:
  - 入口:`python ./scripts/migrate-analysis-skeleton.py --from v0.4.0 --to v0.5.0 [--project-dir <path>] [--dry-run]`
  - 扫描 `knowledge/analyses/*.md`,识别旧骨架(`## 重点摘录` + `## 我的思考`)
  - 映射规则:
    - `## 重点摘录` → `## 方案推演 / 架构分析`(保留正文)
    - `## 我的思考` → `## 关联溯源`(保留正文;**若**正文末尾已有 `> 引用:` 行,保留;**否则**自动从正文 wikilink 抽取生成 `> 引用:` 行)
    - `## 总结:最有收获的一句话` → 保留(同名 G11 兼容)
  - frontmatter:
    - 补 `sources_used`(从正文 wikilink 抽取 + `## 关联溯源` 末尾 `> 引用:` 行,推断去重)
    - 补 `answer_to`(若缺失,从 summary 首行 `**问题**: ` 前缀反向提取;若仍缺 → 抛错)
    - 补 `generated_by` = `agent: producer/aeps-llm-wiki-plugin/<version>`
  - 写入策略(Q7 死循环防护):**不动 `updated` 字段 + 文件 mtime**(即使迁移内容变了也保留原值;若用户想刷 `updated`,手动)
  - 原子写入:用临时文件 + `os.replace`(同 lint --fix 安全锁)
  - git 脏状态检查:同 lint --fix
  - 干跑:`--dry-run` 输出每个文件的预期改动(diff),不写盘
  - log:`log.md` 追加 `**Migration**: analyse-skeleton <basename>.md from v0.4.0 to v0.5.0 — sources_used auto-filled (n=<k> paths)`
  - **测试**:`tests/test_migrate_analysis_skeleton.py`:
    - fixture 1:旧骨架(`## 重点摘录` + `## 我的思考` + `## 总结:...`) → 迁移后新骨架(3 节齐全 + sources_used + answer_to + generated_by + `updated` 不变 + mtime 不变)
    - fixture 2:无 `## 我的思考`(v0.4.0 异常页) → 迁移时**仅**追加占位 `## 关联溯源` + 派生 sources_used,lint C15.1 后续校验 PASS
    - fixture 3:`--dry-run` 模式不写盘(原文件 mtime 不变,内容不变)
    - fixture 4:迁移后跑 `lint C15.1-C15.4` 全部 PASS

#### C16:G10 v0.5.2 PATCH 重 ingest 同名文件 atomic overwrite(详见 prd §4.2 + design §4.2 step 3)

- [ ] **C16.1 `tests/test_safe_mv_overwrite_detect.py`** —— 重 ingest 场景检测 + 强制拍板:
  - [ ] fixture 1:`raw/<subdir>/iso26262.pdf` + `raw/<subdir>/iso26262.pdf.converted.md` 已存在;`inbox/iso26262.pdf` 新版本;跑 ingest → SKILL.md **不**直接迁移,而是**强制拍板**:`[y]` 覆盖 / `[n]` 跳过 / `[d]` 仅删除旧副本
  - [ ] fixture 2:fixture 1 拍板 `[n]` → safe-mv.py --apply 不执行任何写动作,**断言** `inbox/iso26262.pdf` 仍存在 + `raw/<subdir>/iso26262.pdf` 内容不变 + log.md 无新增条目
  - [ ] fixture 3:fixture 1 拍板 `[d]` → safe-mv.py --apply 删除 `raw/<subdir>/iso26262.pdf` + `iso26262.pdf.converted.md`,**不**写入新内容;`inbox/iso26262.pdf` 仍存在(等用户手动处理)
- [ ] **C16.2 `tests/test_safe_mv_overwrite_atomic.py`** —— 拍板 `[y]` 的 atomic overwrite 行为:
  - [ ] fixture 1:fixture 拍板 `[y]` → safe-mv.py --apply 收到 `action: "overwrite"` → **先备份**到 `temp/raw_backup_<hash>/iso26262.pdf` + `iso26262.pdf.converted.md`(断言备份文件存在)
  - [ ] fixture 2:**atomic 替换**:`os.replace()` 一次性替换 `raw/<subdir>/iso26262.pdf` + `raw/<subdir>/iso26262.pdf.converted.md`;**断言** 中途任何一步失败 → 两文件均保持旧值(模拟中途失败:故意在备份后 / 替换前 kill 进程,断言两文件不变)
  - [ ] fixture 3:覆盖范围边界:故意构造同 subdir 含 3 个文件:`raw/<subdir>/foo.pdf` + `foo.pdf.converted.md` + 无关文件 `raw/<subdir>/bar.pdf`(bar 在 subdir 内但与本次 ingest 无关)→ 拍板 `[y]` 重 ingest foo → **断言** `bar.pdf` 内容不变 + mtime 不变
  - [ ] fixture 4:Q7 死循环防护:拍板 `[y]` 后,**断言** `raw/<subdir>/iso26262.pdf` 对应的源页 `knowledge/sources/iso26262.md` 的 frontmatter `updated` 字段值不变 + 文件 mtime 不变(Q7 防护延续,覆盖 raw 不影响 source 页 updated)
  - [ ] fixture 5:log.md 追加:`**Migration**(overwrite): inbox/iso26262.pdf → raw/<subdir>/iso26262.pdf` + `**Converted**(overwrite): raw/<subdir>/iso26262.pdf.converted.md (via anydoc)` + 备份路径 `**Backup**: temp/raw_backup_<hash>/iso26262.pdf`(便于用户回滚)
- [ ] **C16.3 `tests/test_safe_mv_no_reconvert_skill.py`** —— v0.5.2 PATCH 不开重转 skill:
  - [ ] fixture 1:`scripts/` 下不应有 `reconvert-raw.py` / `reconvert-all.py` / `bulk-reconvert.py` 等批量重转入口(G10 派生决策:不开批量重转 skill)
  - [ ] fixture 2:用户尝试跑 `python ./scripts/reconvert-raw.py --all` → **FileNotFoundError**,**不**新增此脚本
  - [ ] fixture 3:文档层 grep `reconvert` / `bulk-reconvert` 关键字 → **不应**出现在 SKILL.md 入口列表(对齐 v0.4.0 G10 拍板)
- [ ] **C16.4 `tests/test_safe_mv_first_ingest_no_overwrite.py`** —— 首次 ingest 不触发拍板门(回归测试):
  - [ ] fixture 1:`raw/<subdir>/` 不存在目标文件(首次 ingest 同名文件)→ safe-mv.py --apply **直接 mv**,**不**强制拍板(拍板门仅在覆盖场景触发)

### 手动验证清单(自动测试难以覆盖的项目)

> **范围**:COMPAT-3(SCHEMA.md zero-shot)+ hooks `SessionStart` 行为。两者**难自动化**,走"LLM 阅读 + 人工评估"或"本地手动跑 + 现象记录"路径。CLAUDE.md "写完代码必须要做你所能做的测试"硬约束下,作为自动测试的**降级方案**记录在案,M5 自测阶段逐项跑一遍。

#### M-V1:COMPAT-3(SCHEMA.md zero-shot 可执行)

- [ ] 准备一份独立 fixture wiki(50 页)+ 全新聊天上下文(脱离本对话的 LLM 实例)
- [ ] 把 `knowledge/SCHEMA.md` 给该 LLM,任务:"按 SCHEMA.md 步骤给 fixture 加一篇 source 页"
- [ ] 评估清单(每条 PASS/FAIL):
  - [ ] 产出页 frontmatter 必填字段齐全(`type` / `title` / `description` / `tags` 含 maturity + docform)
  - [ ] 产出页正文含 3 节骨架(`## 重点摘录` / `## 我的思考` / `## 总结:最有收获的一句话`)
  - [ ] 产出页**无** `## 摘要` / `## Summary` H2
  - [ ] log.md 追加 `**Creation**` 条目,actor 字符串符合 `agent: producer/aeps-llm-wiki-plugin/<version>`(对齐 SCHEMA.md §4)
  - [ ] 关联的 entity/concept 子页路径符合 §3.1 §A 子类 ↔ 目录 1:1 绑死
- [ ] 任意一条 FAIL → SCHEMA.md 表述有歧义,回 §3.5 调整措辞

#### M-V2:hooks `SessionStart` 行为(design §7)

- [ ] **更新提示注入**:mock `git ls-remote` 返回高于本地版本号,启动 Claude Code,验证 system-reminder 出现 `[plugin 更新提示]` 字样
- [ ] **已是最新**:mock `git ls-remote` 返回等于本地版本号,验证**不**出现更新提示
- [ ] **无网静默**:断开网络启动,验证不报错、不阻塞 plugin 加载
- [ ] **git 不可用**:`PATH` 移除 `git`,启动 Claude Code,验证不报错
- [ ] **超时 kill**:`--mock-delay 10s`(hooks `timeout: 5`),验证 5s 后 kill,不阻塞 plugin 启动
- [ ] **不修改 user-project**:跑完任一场景,验证 `<user-project>/inbox/` / `raw/` / `knowledge/` 内容未变
- [ ] **不修改 plugin 本体**:跑完任一场景,验证 `plugin.json` version / 文件 mtime 未变

### 阶段 D:GitHub release 准备清单(预计 0.5 天,git commit 走 Trellis `Phase 3.4 Commit changes`)

**与 Trellis 流程的边界**:本阶段只列 GitHub release 相关动作(创建仓库、推 main、配 Pages、tag + release)。日常 commit / PR / 分支管理全部走 Trellis `Phase 3.4 Commit changes` + `/trellis:finish-work`,**不**在本阶段列 git commit 命令。

- [ ] **D1** 用 `gh repo create zhigangliu-bot/aeps-llm-wiki-plugin --public --description "<plugin 一句话定位>"`(public;private 也可但后续 marketplace 公开更顺)
- [ ] **D2** 把 plugin 根目录内容(`.claude-plugin/` / `skills/` / `templates/` / `scripts/` / `schema/` / `docs/` / `tests/` / `prd.md` / `design.md` / `implement.md` / `LICENSE` / `README.md` / `.gitignore`)push 到 main;**首次 push 用 `git push -u origin main`**
- [ ] **D3** 在 `docs/` 配 GitHub Pages(可选,等 plugin 稳定后再开;Pages 源选 `Deploy from a branch` → `main` / `/docs`)
- [ ] **D4** 在 README.md 写明 `/plugin install zhigangliu-bot/aeps-llm-wiki-plugin` + 链接到 `docs/` 对外快照(由 `src/prd.md` / `src/design.md` / `src/implement.md` 镜像)
- [ ] **D5** 发 GitHub release:
  - `gh release create v0.4.0 --title "v0.4.0" --notes-file CHANGELOG.md`
  - **CHANGELOG.md 从设计文档提炼**(M4 上架前从 design.md §0 + implement.md §0 现状盘点摘出"v0.4.0 含哪些能力";tag-template.md §9 是 tag 组合实例,不是演进记录,**不**作为 CHANGELOG 来源)
  - tag 命名规范:`v<MAJOR>.<MINOR>.<PATCH>`,与 plugin.json `version` 字段一致
  - release notes 必须包含:G1~G9 达成情况、AC-1~8 自测结果、手动验证清单 M-V1/M-V2 通过情况
- [ ] **D6** 在 GitHub 仓库 About 栏贴 plugin 简介 + 关键词(`claude-code` / `plugin` / `llm-wiki` / `okf` / `automotive-electronics`),便于 GitHub 搜索发现

**Trellis 衔接**:本阶段完成后,`/trellis:finish-work` 会处理剩余 task 收尾 + 文档冻结 + 下次 session 上下文加载。本文档不重复列。

---

## 2. 验收 checklist

每阶段完成后,跑下列命令自检:

```bash
# 阶段 A 自检
ls .claude-plugin/plugin.json && cat .claude-plugin/plugin.json

# 阶段 B 自检(每个 skill)
ls skills/aeps-llm-wiki-init/SKILL.md
head -5 skills/aeps-llm-wiki-init/SKILL.md   # 确认开头格式

# 阶段 C 自检
cd tests && python -m pytest -v

# 阶段 D 自检
git tag -l "v*" | sort -V | tail -5
```

---

## 3. 风险与回滚

| 风险                           | 缓解                                                                      | 回滚                              |
| ------------------------------ | ------------------------------------------------------------------------- | --------------------------------- |
| SKILL.md 提示词不够具体,LLM 漂 | 用 design.md §4 流程图作为强约束 + 测试覆盖                              | 改 SKILL.md 措辞,本地再跑测试     |
| 测试 fixture 与 OKF v0.2 漂移  | 测试 fixture 锁定版本                                                     | 重读 OKF-SPEC.md,改 schema 后再测 |
| GitHub push 误推敏感文件       | `.gitignore` 提前建好(排除 `tests/fixtures/secrets/`、`*.local.md`) | 删 remote + force push + 撤 token |
| plugin 升级破坏用户项目副本    | 字典 sync 策略已固化为"本地优先 + append"                                 | 用户可手动从 templates/ 重新复制  |

---

## 4. 时间预算汇总

| 阶段            | 工作量              | 备注                                  |
| --------------- | ------------------- | ------------------------------------- |
| A:plugin 骨架   | 0.5–1 天           | 模板化,快                             |
| B:5 个 SKILL.md | 2–3 天             | 每个 SKILL.md 重点在"边界规则",不能省 |
| C:测试用例      | 1–2 天             | CLAUDE.md 硬约束,必须做               |
| D:发布          | 0.5 天              | GitHub 操作 + release notes           |
| **合计**  | **4–6.5 天** | 集中 1 周可完成                       |

---

## 5. 不在本次范围(后续版本)

- v0.5:knowledge-base 类 MCP server(目前 NFR-1 硬约束禁止,可解约后考虑)
- v0.5:Web 端 UI(目前纯 CLI / Claude Code 形态)
- v0.6:多语言(目前 NFR-3 中文优先,英文术语保留)
- v1.0:正式 GA,定稿 schema,冻结 tag-template.md 6 轴

---

## 6. Change History

### v0.2(2026-09-02) — 五轮增量

**Round 1: Python 化(测试栈同步切 Python 3.10+)**

- §0 现状盘点 scripts/ 节点 → Python 3.10+ 单栈
- §阶段 B2 ingest 核心边界 / §阶段 B3 query 核心边界 / §阶段 B4 lint 核心边界 命令行约定切 Python
- §阶段 C10 NFR-1 + NFR-4 测试:`tests/test_no_daemon.py` 扫 `http.server.HTTPServer` / `socketserver.TCPServer` / `subprocess.Popen` / `signal.signal` / `sys.stdin` 等 Python 等价断言(原 Node jest 等价);tests/ 跑 pytest
- §阶段 C 测试组织表:"scripts/ 与 tests/ 一律 Python 3.10+ 单栈"

**Round 2: 3-stage ingest 并发测试用例(§C2.4 整段)**

- 8 个测试用例:batch OCR 单次冷启动 / 单文件场景跳过阶段 2 / subagent 并发上限 ≤ 5 / 阶段 2 不写 knowledge/ / 阶段 3 命名飘仲裁 / 阶段 3 concept 去重 / log.md 不冲突 / Bash timeout = 600000

**Round 3: Q9 双字段同源测试用例(§C5.1 新子段)**

- 4 个测试用例:source_file 与 sources[0].resource 值相等 PASS / 不一致 FAIL / 缺字段 FAIL / Obsidian 笔记属性面板识别(`tests/test_source_obsidian_link.py` 用 jsonschema 校验字段值正则)

**Round 4: Q10 scripts 严禁交互静态扫描(§C10.1 新子段)**

- 用 `ast` 模块扫所有 `scripts/*.py`,断言不出现 `input(` / `sys.stdin.read` / `sys.stdin.readline` / `getpass.getpass` / `select.select([sys.stdin]`
- fixture 反例:`scripts/_bad_example.py` 含 `input("拍板:")` → 测试 FAIL + 报告行号
- fixture 正例:现有所有 scripts/*.py → 测试 PASS

**Round 5: Q11 subagent 写权隔离测试用例(§C2.4 新增 4 项)**

- fixture inbox 3 份相关 .md,subagent 跑完后 `knowledge/` 下**任何文件均未被修改**(包括 index.md / glossary.md / log.md / overview.md / sources/ / entities/ / concepts/),只有 `temp/<id>-proposal.json` 新增
- fixture 同上,跑完整 ingest 阶段 3 收尾;验证全局索引文件 mtime 接近(在所有 source/entity/concept 页写完后**才**统一修改一次)
- fixture 同名 entity 跨 subagent 重复抽取;验证阶段 3 合并到 1 页 + aliases 累加,不重复建页
- subagent prompt 硬约束扫描:fixture 提供故意违反的 SKILL.md 子代理 prompt;验证 SKILL.md M3 review 流程拒绝该 prompt

**附带**:Q6 wikilink 改造测试用例在 §C4.2(4 项:links 镜像生成 / 漂移检测 / Obsidian 编辑同步 / markdown 链接 type 区分),在 v0.2 一并冻结。

**兼容性**:v0.2 MINOR bump,无 breaking change。

### v0.3(2026-09-02) — Round 6 temp/ 目录契约补丁

**Round 6:temp/ 目录契约 + plan 文件命名统一**

- `tests/test_init_creates_temp.py`(新):跑 init,断言 `<project>/temp/` 创建 + `temp/.gitkeep` + `temp/.gitignore`(内容校验 5 行:`*` / `!.gitkeep` / `!proposal-*.json` / `!decision-*.json` / `!plan-*.json`)
- `tests/test_temp_dir_usage.py`(已存在,本 round 加固):除原有"无 /tmp / AppData"断言外,新增断言 scripts/ 的 `--output` / `--apply` 参数路径全部以 `temp/` 开头(grep `--output temp/` / `--apply temp/` 枚举所有 scripts/* 调用约定)
- `tests/test_plan_filename_extension.py`(新):断言 scripts/ 拒绝 `--apply temp/<id>.md`(只认 `.json`),跑 fixtures 反例 → 报错"unsupported plan format, must be .json"
- `tests/test_temp_gitignore_audit.py`(新):验证默认 git 跟踪状态(`git check-ignore`)对 `temp/<basename>.md` 返回 ignored、对 `temp/proposal-<doc-id>.json` 返回 not ignored、对 `temp/decision-<hash>.json` 返回 not ignored、对 `temp/.gitkeep` 返回 not ignored

**§C12 NFR-5(temp/)测试已存在,本 round 不重复新增**,仅作 anchor。

**附带**:Q11 subagent 写权矩阵(§C2.4 已冻结 4 项)+ Q10 plan JSON contract(§C10.1 / §C10.2 已冻结)在本 round 通过 temp/ 目录契约补全落地路径,无新增独立测试。

**兼容性**:v0.3 MINOR bump:目录结构新增 `temp/` 顶层节点 + plan 文件命名契约细化(proposal 用 doc-id、decision 用 hash),但 OKF v0.2 schema 无 breaking change;既有 v0.2 wiki 升级到 v0.3 plugin 只需重跑 init(temp/ 自动补建 + scripts/ 重新同步)。

### v0.3.1(2026-09-02) — Round 7 `links:` 死循环防护 PATCH

**Round 7:`links:` 自动重写硬约束(Q7 死循环防护)**

- §C4.2 补 2 个新测试用例(详见 design §3.6.2 "硬约束"子段 + 设计 §3.6.2 LintFix 日志模板):
  - **`tests/test_links_mirror_idempotent.py`**:验证 Set 比对规则 —— fixture frontmatter `links: [A, B]`(顺序 A→B)+ 正文 wikilink 顺序 B→A → lint **不告警**、`--fix` **不重写**(content hash + mtime 双双不变);跑 2 遍结果完全相同(幂等)
  - **`tests/test_links_mirror_preserves_updated_and_mtime.py`**:验证 3 条硬约束 —— fixture `updated: 2026-01-01T00:00:00Z` + `links:` 含 ghost → 跑 `--fix` → 断言 (a) `updated` 字段值不变;(b) `os.stat().st_mtime` 在 fix 前后保持相等;(c) log.md 追加 `**LintFix**: links-mirror-sync ...` 不含 `updated` 字段字样

**§C4.2 已有 4 个测试用例**(`test_links_mirror_generation` / `_drift` / `_obsidian_edit` / `_types`)在 v0.2 已冻结,本轮不重复新增,仅作 anchor。

**兼容性**:v0.3.1 PATCH bump:无新增顶层结构 / 无命名契约变化,只是为已有 `links:` 镜像机制加 3 条确定性规则(Set 比对 + 不动 `updated` + mtime 保留)。OKF v0.2 schema 无 breaking change;既有 v0.3 wiki 升级到 v0.3.1 plugin **无需**重跑 init(纯 lint 行为加固)。

---

**补丁登记(2026-09-02):design §2.4.1 / implement §C10.1 stdin 全禁原则**

- **背景**:原 §2.4.1 / §C10.1 把 `input()` 与 `sys.stdin.*` 并列禁止,但未明确"非 TTY 管道 stdin 是否豁免"。理论上 `cat decision.json | python scripts/safe-mv.py` 会被 C10.1 AST 扫描判 FAIL,但若脚本意图就是非交互管道接收 JSON,又显失公平。
- **决议**:一律走显式文件参数(`--apply <filepath>` / `--output <path>` / `--config <path>`),**管道 stdin 同样禁止**;AST 扫描**不**做 `isatty()` 判定门,直接 FAIL。
- **影响面**:仅 spec 措辞加严,无测试新增(原 C10.1 禁单已覆盖,fixtures 正/反例用例不受影响),无 OKF schema 变化。
- **版本号**:v0.3.1 PATCH 不 bump(行为面无变化,合并入同次提交)。

---

**补丁登记(2026-09-02):NFR-1 qmd 阈值升级条款 + 三处措辞对齐**

- **背景**:prd §7.2 NFR-1 措辞「qmd 可选,plugin 不强制装」与 §4.3 / implement §B3 / §C3.3 的 $N \ge 1000$ 强约束(未装 → 报错退出)存在语气冲突。design §1.2 / §4.3 已隐含「按阈值降级或 FAIL」语义,但未在 prd NFR-1 显式登记。
- **决议**:NFR-1 加**唯一阈值升级条款** —— `knowledge/` 页数 $N \ge 1000$ 时 qmd 临时升级为强依赖(query skill 报错退出);其余规模下 qmd 仍为可选降级。**不改** prd §4.3 / implement §B3 / §C3.3 现有 FAIL 行为,design §1.2 / §4.3「降级或 FAIL」表述与之兼容。
- **影响面**:仅 prd.md NFR-1 一句话措辞加严;无测试新增(C3.3 fixture 1100 页 qmd 未装 FAIL 已覆盖);design.md / implement.md 行为面无变化。
- **版本号**:v0.3.1 PATCH 不 bump(行为面无变化,合并入同次提交)。

---

### v0.3.2(2026-09-02) — Round 8 Link Normalizer + Lint --fix 安全锁

**背景**:Round 7 Q7 死循环防护只覆盖"单个文件写入无副作用",未覆盖"wikilink 解析归一化"与"批量写入整体一致性"。两处都是真实设计空缺:

- **空缺 1 Normalizer**:正文 `[[NoteName|Alias]]` / `[[NoteName#章节]]` / `[[dir/NoteName]]` 与 frontmatter `links:` 字符串字面比对,会导致 Obsidian 别名 / 锚点 / 路径前缀差异被误判为 drift → 反复"纠错"
- **空缺 2 安全锁**:`--fix` 是批量写文件,任一中断会留下 frontmatter 已更新 / 正文未更新 / 索引未同步 的不一致状态;且无 git 兜底 → 变更不可回滚

**改动**:

- **design §3.6.2 新增 "Link Normalizer" 子段**(Q7 之前,作为输入约束),5 条解析规则:
  - 别名剥离(`[[NoteName|Alias]]` → `NoteName`)
  - 锚点剥离与归档(`[[NoteName#章节]]` → `(NoteName, anchor="章节")`,锚点不进 links: 但写入 log.md)
  - 路径前缀归一化(比对走 basename,写入保留完整字符串对齐 OKF §9)
  - 类型区分(wikilink / markdown / url 三类,与现有 frozenset 元素结构对齐)
  - 反例警戒 3 条(避免实现走偏)
- **design §5.4 新增 "Lint --fix 安全锁" 子段**,3 条硬约束:
  - **默认 dry-run**:`--fix` ≠ `--apply`,必须双开关才触发磁盘写入
  - **事务原子写入**:全部改写先生成 in-memory 模型 → 图结构预检(孤立/循环/反向链接) → 通过后 `os.replace` 一次性原子写入
  - **Git 脏状态前置检查**:`git status --porcelain` 检脏 → 阻断;`--allow-dirty` 显式放行;干净时自动 `git stash push` 创快照
- **implement §C4.3 Link Normalizer 解析规则 fixture**(4 项):
  - 别名剥离不告警 / 锚点剥离不告警且去重 / 路径前缀 basename 等价但写入保留原字符串 / 反例 FAIL(`Alias` 当 target)
- **implement §C4.4 Lint --fix 安全锁 fixture**(3 项):
  - dry-run 不写盘 / 事务校验失败全部回滚 / git 脏状态阻断 + `--allow-dirty` 放行 + 干净时自动 stash

**与已有规则的关系**:
- **Q7 死循环防护**(`§3.6.2`):管"单文件写入无副作用"—— 不动 `updated`、保留 mtime、Set 比对
- **Normalizer**(`§3.6.2`):管"统一解析 → 标准键"—— 避免 drift 假阳性
- **安全锁**(`§5.4`):管"批量写入不破坏整体一致性"—— dry-run + 事务 + git 兜底
- 三者**层层独立**,缺任一都会留下不一致隐患

**不动**:
- Q6 wikilink 一等公民 / Q10 plan JSON / Q11 subagent 写权矩阵:已冻结
- design §4.4 / §C4.1 lint 行为边界(确定性 vs 语义分流):已冻结
- scripts/ 严禁交互硬契约(NFR-1 加严,本轮 stdin 全禁):v0.3.1 PATCH 已冻结

**兼容性**:**v0.3.2 PATCH bump**。本次是**新增设计契约**(Normalizer + 安全锁两条全新约束),不是已有规则的加严;OKF v0.2 schema 无 breaking change;既有 v0.3.1 wiki 升级到 v0.3.2 plugin **无需**重跑 init,但需要新 fixture 测试通过验证。lint `--fix` 命令行行为有用户可见变化(从单开关 → 双开关),需要在 plugin manifest / README 注明迁移提示。

### v0.5.0(2026-09-03) — Round 10 G11 query 落档 3 隐患(分析专属骨架 + sources_used + gating)

**新增 §C15**:`tests/test_analysis_dedicated_skeleton.py` / `test_analysis_sources_used_required.py` / `test_query_gating_logic.py` / `test_analysis_sources_used_mirror.py` / `test_migrate_analysis_skeleton.py`(共 5 个 fixture 脚本,覆盖 G11 M1-M3 全部 + 迁移兼容)。

**关键边界测试用例**:

- C15.1 骨架校验(7 个 fixture):3 节齐全 / 缺 1 节 / 含 `## 重点摘录` / 含 `## 我的思考` / 含 `## 摘要` / 含 `## Summary` / `--fix` 自动追加占位
- C15.2 sources_used 校验(8 个 fixture):3 条已存在 / 字段缺失 / 空数组 / 1 条不存在 / 含非 wiki 路径 / `--fix` 自动派生 + Q7 死循环防护(updated + mtime 不变) / `--fix` 补全 + Q7 / 派生来源严格性(禁止全文 grep,`## 关联溯源` 段正文 wikilink 不在 `> 引用:` 行的不被收)
- C15.3 gating 校验(7 个 fixture):Overview + ≥2 子目录 + ≥200 字 / Comparison / Exact + <200 字 / "Wiki 未覆盖" / intent=overview 但短答(不触发优先级) / 输出末尾无标记 → FAIL / e2e 三种 query 类型断言
- C15.4 `> 引用:` 行与 sources_used Set 比对(4 个 fixture):一致 / sources_used 多 1 条 / `> 引用:` 行多 1 条 / `--fix` 自动同步 + Q7 不动 updated + mtime
- C15 派生脚本 `migrate-analysis-skeleton.py`(4 个 fixture):旧骨架 → 新骨架 / 无 `## 我的思考` 异常页 → 仅追加占位 / `--dry-run` 不写盘 / 迁移后 lint C15.1-C15.4 全 PASS

**新增 frontmatter 字段**:`sources_used` + `answer_to` + `generated_by`(均为 plugin 扩展字段,OKF v0.2 §9 "consumers MUST NOT reject bundle because of missing optional frontmatter fields" 兼容)。

**新增正文骨架**:G11 v0.5.0 起 `analyses/*.md` **不再复用** sources 的 3 节骨架,改用**分析专属骨架**(`## 方案推演 / 架构分析` + `## 关联溯源` + `## 总结:最有收获的一句话`)。M1 结构断层修复:硬塞 sources 骨架 = 把"综合推演"伪装成"摘录",失真。

**不动**:
- Q6 wikilink 一等公民 / Q7 死循环防护 / Q9 source_file + sources[] 双字段 / Q10 scripts 严禁交互 / Q11 subagent 写权矩阵:已冻结
- design §3.6.2 / §4.4 / §C4.1 lint 行为边界(确定性 vs 语义分流):已冻结
- v0.3.2 Normalizer + Lint --fix 安全锁:已冻结
- G10 转换副本入 raw + 源页 link 指副本:已冻结(G11 是 G10 之后的查询侧修复)

**兼容性**:**v0.5.0 MINOR bump**。本次新增 G 级目标(G11)+ 3 个 frontmatter 字段(`sources_used` / `answer_to` / `generated_by`),均属 plugin 扩展字段,OKF v0.2 §9 兼容。**唯一强约束**:**v0.4.0 及以前落档的 analysis 页在 v0.5.0 lint 上会 FAIL**(骨架语义变化),用户必须跑一次 `python ./scripts/migrate-analysis-skeleton.py --from v0.4.0 --to v0.5.0`。既有 v0.4.0 wiki 升级到 v0.5.0 plugin:
1. 升级 plugin → 跑 `/aeps-llm-wiki-init`(幂等再入,新加 `templates/analysis-page.md` + `scripts/migrate-analysis-skeleton.py`)
2. **跑 `migrate-analysis-skeleton.py`**:`analyses/` 下旧骨架页批量转新骨架 + 补 sources_used
3. 跑 `/aeps-llm-wiki-lint --fix --apply` 二次确认所有 FAIL 已清零

### v0.5.1(2026-09-03) — Round 11 PATCH query skill 路径 C + 跳 3 权重降权 + 跳 4 累积触发显式化

**不动 fixture**:无新 pytest 文件;原 §C15 全部 fixture 仍 PASS(本次 PATCH 不动 analysis 骨架 / sources_used / gating)。

**新增 fixture 段**(可写可不写,v0.5.1 PATCH 范围内可选):

- [ ] `tests/test_query_path_c_keywords.py` —— 路径 C 词命中单元:
  - fixture 1:query 含 "S32G vs NXP S32K 优缺点" → SKILL.md 阶段3输出 intent=comparison → 走 gating 触发 analysis 落档
  - fixture 2:query 含 "PCIe 接口数"(无 vs/对比/区别/异同/优缺点)→ intent=exact → 不触发
  - fixture 3:query 含 "vs" 但语义是"我之前 vs 现在"(非对象对比)→ LLM 阶段3 推断 intent ≠ comparison(不硬命中) → 走默认意图(overview 或 other)
  - fixture 4:query 含 "对比" 但语义是"请把这两段对比起来"(隐含对比,对象未指定)→ LLM 阶段3 推断 intent=comparison(强倾向词)
- [ ] `tests/test_query_hop3_weight_pruning.py` —— 跳 3 权重降权单元:
  - fixture 1:候选页含 `sources:` 数组 + 正文 5 个 wikilink → 跳 3 优先采 `sources:` 数组里的(优先级 1),再采正文(优先级 3)
  - fixture 2:analyses 页候选含 `## 关联溯源` 末尾 `> 引用:` 3 条 + 正文 8 个 wikilink → 跳 3 优先采 `> 引用:` 行
  - fixture 3:用户手填 `## Related pages`(可选) → 跳 3 优先采该节
  - fixture 4:无结构化引用段 + 正文大量 wikilink → 跳 3 降权采正文(权重 3,但仍采,不忽略)
  - fixture 5:邻居页硬上限仍 8 个(QUERYY_NEIGHBOR_MAX 不变)
- [ ] `tests/test_query_hop4_comparison_accumulation.py` —— 跳 4 累积触发单元:
  - fixture 1:`log.md` 含 3 条 `**Creation**: ... query "S32G vs NXP S32K ..."`(全局累计)→ 跳 4 探测命中 → 提示建 comparison 页
  - fixture 2:`log.md` 含 2 条 S32G vs NXP S32K + 1 条 S32G vs Renesas RH850(主题近似匹配)→ 跳 4 探测命中 3 次(主题近似,非精确 X/Y)→ 提示建 comparison 页
  - fixture 3:`log.md` 含 3 条 S32G vs NXP S32K 但**全部在 7 天前**(D4 不加时间窗)→ 仍命中 → 提示
  - fixture 4:`log.md` 含 2 条 S32G vs NXP S32K + 1 条 S32G 单点查证 → 跳 4 探测不命中(主题不同)→ 不提示
  - fixture 5:跳 4 探测**不**自动建 comparison,只**提示**(语义级,等用户拍板;prd §4.6 三路径职责不重叠)

**新增 frontmatter 字段**:无(D2 决策:不引入 `parent:` + 不引入强制 `## Related pages` 节)。

**新增正文骨架**:无(D2 决策:`## Related pages` 是可选,不强锁)。

**新增 scripts 入口**:无(D1 决策:不引入 Python 本地 intent router,LLM 阶段3推断)。

**不动**:
- Q6 wikilink 一等公民 / Q7 死循环防护 / Q9 source_file + sources[] 双字段 / Q10 scripts 严禁交互 / Q11 subagent 写权矩阵:已冻结
- design §3.6.2 / §4.4 / §C4.1 lint 行为边界(确定性 vs 语义分流):已冻结
- v0.3.2 Normalizer + Lint --fix 安全锁:已冻结
- G10 转换副本入 raw + 源页 link 指副本:已冻结
- G11 分析专属骨架 + sources_used 必填 + gating:已冻结(v0.5.0)
- 所有 v0.5.0 §C15 fixture:已冻结

**兼容性**:**v0.5.1 PATCH bump**(MINOR bump 内的小补丁)。本次**不引入**新 frontmatter 字段 / 不新正文骨架 / 不新 scripts 入口;只细化设计澄清(§4.3 跳 3 优先级伪代码 + §4.6 路径 C 词表显式化)。OKF v0.2 schema 无 breaking change;既有 v0.5.0 wiki 升级到 v0.5.1 plugin **无需**重跑 init,无需跑迁移脚本,SKILL.md 内部行为升级即可。

### v0.5.2(2026-09-03) — Round 12 PATCH 修复 2 个 PRD 缺陷(Intent ambiguous fallback + G10 atomic overwrite)

**新增 §C15.3 fixture 8/9/10/11**:(详见 §C15.3 fixture 列表)

- fixture 8:**intent=ambiguous**(语义模糊,例:"这篇芯片文档和上一篇有什么异同?")→ 走 `💡` 跳过(v0.5.2 fallback 低扰动)
- fixture 9:intent=ambiguous + 命中 2 子目录 + ≥200 字 → 仍走 ambiguous 跳过(优先级 > 不触发其他项)
- fixture 10:**冲突测试** —— 路径 C 触发词"异同" + LLM 推断 intent=ambiguous → 走 ambiguous 跳过(路径 C 不覆盖 fallback)
- fixture 11:intent=other + 命中 2 子目录 + ≥200 字 → 走触发条件 → `❓` 触发 prompt(intent=other 走触发路径)

**新增 §C16**(v0.5.2 PATCH 修复缺陷 2):4 个 fixture 脚本:

- C16.1 `tests/test_safe_mv_overwrite_detect.py`:重 ingest 同名文件检测 + 强制拍板(`[y]`/`[n]`/`[d]`)+ `[n]` 不写盘 / `[d]` 仅删旧副本
- C16.2 `tests/test_safe_mv_overwrite_atomic.py`:拍板 `[y]` 的 atomic overwrite 行为(备份到 `temp/raw_backup_<hash>/` → `os.replace()` 一次性替换 + 覆盖范围边界 + Q7 死循环防护延续 + log.md 追加 Migration/Converted/Backup 三行)
- C16.3 `tests/test_safe_mv_no_reconvert_skill.py`:不开重转 skill(grep 断言 `scripts/` 下无 `reconvert-raw.py` / `bulk-reconvert.py` + 文档层无对应 SKILL.md 入口)
- C16.4 `tests/test_safe_mv_first_ingest_no_overwrite.py`:首次 ingest 同名文件回归(不触发拍板,直接 mv)

**新增 frontmatter 字段**:无(只扩 intent 档位,不动 schema)

**新增正文骨架**:无

**新增 scripts 入口**:无(只扩 `safe-mv.py --apply` decision JSON `action` 字段,新增 `"overwrite"` 值)

**不动**:

- Q6 wikilink 一等公民 / Q7 死循环防护 / Q9 source_file + sources[] 双字段 / Q10 scripts 严禁交互 / Q11 subagent 写权矩阵:已冻结
- design §3.6.2 / §4.4 / §C4.1 lint 行为边界:已冻结
- v0.3.2 Normalizer + Lint --fix 安全锁:已冻结
- G10 转换副本入 raw + 源页 link 指副本:已冻结
- G11 分析专属骨架 + sources_used 必填 + gating:已冻结
- v0.5.1 路径 C / 跳 3 权重 / 跳 4 累积触发:已冻结
- 所有 v0.5.1 §C15 fixture(原 7 个):已冻结 + 新增 4 个

**兼容性**:**v0.5.2 PATCH bump**(MINOR bump 内小补丁)。本次**不引入**新 frontmatter 字段 / 不新正文骨架 / 不新 scripts 入口;只扩 intent 档位 + 扩 safe-mv.py --apply decision JSON `action` 字段。OKF v0.2 schema 无 breaking change;既有 v0.5.1 wiki 升级到 v0.5.2 plugin **无需**重跑 init,无需跑迁移脚本,SKILL.md 内部行为升级即可。

### v0.5.3(2026-09-03) — Round 13 PATCH 修复 PRD 缺陷 5(Q7 `links:` 自动重写时 mtime + atime 双还原)

**§C4.2 新增 2 个 fixture**(v0.5.3 PATCH,修复缺陷 5):

- **新增 `tests/test_links_mirror_preserves_atime_and_mtime.py`**(Q7 Round 13 v0.5.3 PATCH 新增,atime + mtime 双还原):fixture 同原 `test_links_mirror_preserves_updated_and_mtime.py`(frontmatter `updated: 2026-01-01T00:00:00Z` + `links:` 加 ghost)→ 跑 lint --fix → 断言:
  - (a) `os.stat(path).st_atime` 与 fix 前**完全相等**(浮点精度 1e-6 容差)
  - (b) `os.stat(path).st_mtime` 与 fix 前**完全相等**
  - (c) 用 `monkeypatch` 监视 `os.utime` 调用,断言 lint 代码路径中**确实调用** `os.utime(path, (original_atime, original_mtime))` 至少一次,参数是**二元组**(不允许只传 mtime 不传 atime)
  - (d) fix 前后 content hash 完全相等(说明 `links:` 同步是 no-op,业务无变更)

- **新增 `tests/test_links_mirror_utime_flow_order.py`**(Q7 Round 13 v0.5.3 PATCH 新增,流程性 fixture):fixture 同上 + 用 `monkeypatch` 包装 `os.stat` / `Path.write_text` / `os.utime` 三个调用并记录顺序 → 断言:
  - 调用顺序严格为 **`stat → write_text → utime`**(design §3.6.2 行 1199-1231 四步流程的强制 3 步)
  - **反例测试**:故意把 fixture 中 `os.utime` 替换成 no-op(模拟"只 write 不 utime"的实现错误)→ 跑 lint --fix → 断言 `mtime` 必变(说明测试有效)+ `utime` 未被调用(说明实现漏掉了第 3 步)

**不动**:

- Q6 wikilink 一等公民 / Q7 死循环防护业务意图 / Q9 source_file + sources[] 双字段 / Q10 scripts 严禁交互 / Q11 subagent 写权矩阵:已冻结
- v0.3.2 Normalizer(v0.5.3 PATCH 不动 Normalizer 解析规则)
- G10 转换副本入 raw + 源页 link 指副本:已冻结
- G11 分析专属骨架 + sources_used 必填 + gating:已冻结
- v0.5.1 路径 C / 跳 3 权重 / 跳 4 累积触发:已冻结
- v0.5.2 Intent ambiguous fallback + G10 atomic overwrite:已冻结
- 原 `test_links_mirror_preserves_updated_and_mtime.py`(v0.3.2 Round 7):**已冻结**,v0.5.3 PATCH 不重写,**只新增** atime + 流程性两个 fixture

**兼容性**:**v0.5.3 PATCH bump**(MINOR bump 内小补丁)。本次**不引入**新 frontmatter 字段 / 不新正文骨架 / 不新 scripts 入口;**只升级** `okf-lint.py` / `lint.py` 内部 `fix_links_mirror()` 函数的**实现细节**(atime/mtime 双还原 + 4 步流程),**不**改 Q7 业务意图。OKF v0.2 schema 无 breaking change;既有 v0.5.2 wiki 升级到 v0.5.3 plugin **无需**重跑 init,无需跑迁移脚本,`okf-lint.py` / `lint.py` 内部函数行为升级即可(下次跑 `--fix` 自动按 4 步流程写盘)。

### v0.5.4(2026-09-03) — Round 14 PATCH 修复 PRD 缺陷 3(§4.2.1 proposal JSON schema 强校验 + 损坏降级单线程重解析)

**§C2.4 新增 8 个 fixture**(v0.5.4 PATCH,修复缺陷 3):

- **单元级 schema 校验(3 个)**:
  - `tests/test_proposal_schema_valid.py`:合规 proposal(8 必填字段 + _meta 元数据)→ `jsonschema.validate()` 通过 + 字符清洗写入 `temp/<id>-proposal.json.sanitized` + 进入阶段 3 合并
  - `tests/test_proposal_schema_invalid_missing_field.py`:缺 `suggested_subdir` → `ValidationError` 必填缺失 + 触发降级(主 agent 单线程重跑)
  - `tests/test_proposal_schema_invalid_enum.py`:`format: "exe"`(不在 enum 白名单)→ `ValidationError` + 走降级路径

- **关键集成测试(2 个,不阻断整批)**:
  - `tests/test_proposal_json_decode_error.py`:故意删除 proposal JSON 末尾 `}`(模拟 LLM 输出截断)→ `json.JSONDecodeError` 抛出 + **不**阻断整批 ingest(其他正常 proposal 继续合并) + 损坏文件 inbox 原文件**保留** + 主 agent 退出 0
  - `tests/test_proposal_failure_log_only.py`:inbox 3 份 + 故意让 1 份(`temp/notes.md-proposal.json`)损坏 + 其他 2 份正常 → 跑完整 ingest → 断言 (i) 其他 2 份正常进入 `knowledge/sources/` + 对应 entities/concepts + `log.md` 追加 `**Migration**` 行;(ii) 损坏那份 `inbox/notes.md` 保留;(iii) `knowledge/log.md` 末尾追加 `**IngestFailure**` 段(NEW 段,不在原 9 步串行清单里)含 `proposal_path` + `exception_type` + `exception_message`;(iv) 主 agent 退出 0(整批不阻断);(v) `temp/notes.md-proposal.json.corrupt.bak` 备份存在

- **字符清洗 + 截断检测(2 个)**:
  - `tests/test_proposal_control_chars_strip.py`:concept.name 含 `\x00` NUL + `\x1f` 单元分隔符 + BOM + `</script>` 注入 → `jsonschema.validate` 通过(字符本身在 string 范围内) + 字符集清洗函数 strip 控制字符(BOM 保留,其他 strip) + `</script>` 替换为 `<\/script>`(避免下游 web 渲染) + 清洗后写入安全版本
  - `tests/test_proposal_truncation_detect.py`:concepts 数组 250 条(`maxItems: 200` 超限)→ `ValidationError`(maxItems 超限) + 走降级路径

- **关键集成测试,降级路径(1 个)**:
  - `tests/test_proposal_retry_main_agent_single.py`:proposal 损坏 → 跑 ingest → 断言 (a) **不**再派 subagent 重试(避免同样的 JSON 损坏模式);(b) 主 agent **单线程**重跑该文件 LLM 抽取(走 §4.2 单文件分支);(c) 重跑结果合规 → 进入合并;(d) 若重跑仍失败 → 标记跳过 + `**IngestFailure**` 段;(e) retry 限额 1 次(防止 token 耗尽)

**不动**:

- Q6 wikilink 一等公民 / Q7 死循环防护业务意图 / Q9 source_file + sources[] 双字段 / Q10 scripts 严禁交互 / Q11 subagent 写权矩阵:已冻结
- v0.3.2 Normalizer(v0.5.4 PATCH 不动 Normalizer 解析规则)
- G10 转换副本入 raw + 源页 link 指副本:已冻结

### v0.5.5(2026-09-03) — Round 15 PATCH 一致性对齐(plugin 本体目录布局与现状对齐)

**§0 现状盘点对齐**(v0.5.5 PATCH,三文档一致性):

- **`templates/` 行**:从 5 份 → **7 份现状**(补 `source-page.md` + `analysis-page.md`);新增 `templates/README.md` 未生成 / `tag-template.md` 已生成标注
- **`scripts/` 行**:从"❌ 待新建" → **设计阶段仅 README.md + requirements.txt**(对齐 design §1.1);`*.py` 标注为"阶段 C 实现"
- **`schema/` 行**:新增 ⚠️ 设计阶段保留(frontmatter + proposal .yaml 待阶段 C 实现 scripts 时落地)
- **状态行 bump**:从 v0.5.4 → v0.5.5;templates 计数从 5 → 7(含 v0.5.0 新增 analysis-page.md)

**不动**:

- Q1-Q11 设计决策 / G1-G11 业务纪律 / 5 个 SKILL.md 触发契约:已冻结
- v0.5.3 Q7 atime + mtime 双还原 / v0.5.4 proposal JSON schema 校验 + 损坏降级:已冻结
- §C 阶段 B/C 测试清单:已冻结(本轮纯文档一致性,不动测试用例)
- 5 个 SKILL.md / plugin.json / tests/ / docs/:仍为 ❌ 待新建(plugin 上架资产,阶段 D)
- G11 分析专属骨架 + sources_used 必填 + gating:已冻结
- v0.5.1 路径 C / 跳 3 权重 / 跳 4 累积触发:已冻结
- v0.5.2 Intent ambiguous fallback + G10 atomic overwrite:已冻结
- v0.5.3 Q7 mtime + atime 双还原:已冻结
- 原 §C2.4 全部 fixture(batch OCR / 并发上限 / 写权隔离 / 命名飘仲裁 / concept 去重 / log.md 不冲突 / Bash timeout / 冷启动时间断言):**已冻结**,v0.5.4 PATCH 不重写,**只新增** 8 个 proposal JSON 校验 + 降级 fixture

**兼容性**:**v0.5.4 PATCH bump**(MINOR bump 内小补丁)。本次**不引入**新 frontmatter 字段 / 不新正文骨架 / 不新 scripts 入口;**只新增** `src/schema/proposal.schema.yaml`(JSON schema 草案,**可选**落地,scripts 实现阶段由 LLM 根据草案生成);若 schema 文件暂未落地,SKILL.md 阶段 3 校验逻辑可走"必填字段最小校验 + JSON 解析"两件套兜底。OKF v0.2 schema 无 breaking change;既有 v0.5.3 wiki 升级到 v0.5.4 plugin **无需**重跑 init,无需跑迁移脚本;**新增** `**IngestFailure**` log 段是 NEW,既有 log.md 兼容(只在末尾追加,**不**重写历史条目)。

### v0.4.0(2026-09-03) — Round 9 G10 外部转换副本入 raw + 源页 link 指副本

**新增 §C13**:`tests/test_convert_emit_to_pdf.py` / `test_convert_emit_to_image.py` / `test_convert_emit_to_failure.py` / `test_safe_mv_dual_file.py` / `test_source_frontmatter_g10_fields.py` / `test_source_frontmatter_g10_native.py` / `test_source_frontmatter_g10_consistency.py` / `test_links_mirror_for_converted.py` / `test_links_mirror_for_native.py` / `test_links_mirror_drift_converted.py` / `test_g10_historical_compat.py` / `test_g10_no_reconvert.py`(共 12 个 fixture,覆盖 G10 M1-M4 全部 + 历史兼容 + 重转拒绝)。

**关键边界测试用例**:

- C13.1 --emit-to 双产物落盘(batch / 单文件 / 图片 OCR / 失败不生成空副本)
- C13.2 safe-mv 双文件迁移 + log.md 双行(`**Migration**` + `**Converted**`)
- C13.3 源页 frontmatter 4 字段一致性(转换的 + 纯文本 + lint C13 强校验 4 种矛盾组合)
- C13.4 links 镜像含 `.converted` 后缀 + 正文 `> 原始来源:[[...]]` 行(Q7 死循环防护规则继续生效)
- C13.5 历史归档兼容(lint WARN 不 FAIL)
- C13.6 重转策略拒绝(覆盖 .converted.md → FAIL)

**不动**:
- Q6 wikilink 一等公民 / Q7 死循环防护 / Q9 source_file + sources[] 双字段 / Q10 scripts 严禁交互 / Q11 subagent 写权矩阵:已冻结
- design §4.4 / §C4.1 lint 行为边界(确定性 vs 语义分流):已冻结
- v0.3.2 Normalizer + Lint --fix 安全锁:已冻结

**兼容性**:**v0.4.0 MINOR bump**。本次新增 G 级目标(G10)+ 4 个 frontmatter 字段(`format` / `converter` / `native_text` / `converted_path`),均属 OKF v0.2 §B 推荐字段或 plugin 扩展字段,§9 "consumers MUST NOT reject bundle because of missing optional frontmatter fields" 兼容。既有 v0.3.2 wiki 升级到 v0.4.0 plugin **无需**重跑 init(G10 是 ingest 增量,历史 raw/ 归档不变);用户主动补建历史转换副本时把原文件 `cp` 回 inbox/ 走 ingest。

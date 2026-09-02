# implement.md — 执行清单

> **来源**:[prd.md](prd.md) 产品需求 + [design.md](design.md) 技术设计。
> **状态**:截至 2026-09-02,文档层(src/design.md + src/prd.md + 4 份 templates)已完成。
> **剩余工作**:把 src/ 内容打包为可上架的 Claude Code plugin(目录结构 + SKILL.md + plugin.json + 测试 + GitHub 发布)。

---

## 0. 现状盘点(2026-09-02)

**产品定位**(2026-09-02 增):`aeps-llm-wiki-plugin` 的输出 `knowledge/` 目录是给 **Obsidian** 消费的。LLM 写、人用 Obsidian 读、plugin 管一致性。Obsidian 直读是产品级硬约束,所有链接 / tag / 目录 / 文件名设计必须 Obsidian 原生可识别(详见 prd §1 背景 + design §0 前端契约)。

```
src/                                    已完成
├── design.md                           ✅
├── prd.md                              ✅
├── scripts/                            ❌ 待新建(convert-to-md.py + 其他脚本,Python 3.10+ 单栈)
│   └── (暂无)                           ❌
└── templates/                          ✅
    ├── raw-readme.md                   ✅(15 类权威字典,plugin 主)
    ├── concept-entities-readme.md      ✅(子类 ↔ 目录绑死)
    ├── tag-template.md                 ✅(6 轴受控词表 v0.4)
    ├── inbox-readme.md                 ✅(简版提示,plugin 主)
    └── knowledge-SCHEMA.md             ✅(用户项目下操作手册,含占位符)

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

#### C5:AC-5(frontmatter 自动校验)

- [ ] 写 Python 脚本 `tests/test_frontmatter_schema.py`,对所有 fixture `knowledge/**/*.md` 跑 jsonschema 校验
- [ ] 任何不合规立刻 FAIL
- [ ] **C5.1 source 页双字段同源断言**(详见 design §3.6.1.1):
  - [ ] fixture 造 `type: source` 页:`source_file: raw/02_芯片/foo.pdf` + `sources[0].resource: raw/02_芯片/foo.pdf` → 跑 lint → 通过
  - [ ] fixture 改 source_file 与 sources[0].resource 值不一致(如 source_file 指向 foo.pdf,sources[0].resource 指向 bar.pdf)→ 跑 lint → FAIL
  - [ ] fixture 缺 source_file 或 sources[0].resource 任一字段 → 跑 lint → FAIL
  - [ ] 写 `tests/test_source_obsidian_link.py`:fixture 在 Obsidian 笔记属性面板里 source_file 字段值渲染为可点击链接(由 jsonschema 校验该字段存在 + 值符合 `raw/<subdir>/<basename>.<ext>` 正则)

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
    - [ ] 用 `ast` 模块扫所有 `scripts/*.py`,断言不出现以下调用:
      - `input(` / `input (`(Python 内置 `input()` / `input(prompt)`)
      - `sys.stdin.read` / `sys.stdin.readline` / `sys.stdin.readlines`
      - `getpass.getpass` / `getpass(`
      - `select.select([sys.stdin]` 等 stdin 等待调用
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

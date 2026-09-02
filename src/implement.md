# implement.md — 执行清单

> **来源**:[prd.md](prd.md) 产品需求 + [design.md](design.md) 技术设计。
> **状态**:截至 2026-09-02,文档层(src/design.md + src/prd.md + 4 份 templates)已完成。
> **剩余工作**:把 src/ 内容打包为可上架的 Claude Code plugin(目录结构 + SKILL.md + plugin.json + 测试 + GitHub 发布)。

---

## 0. 现状盘点(2026-09-02)

```
src/                                    已完成
├── design.md                           ✅
├── prd.md                              ✅
├── requirements.txt                    ❌ 已删除(统一归 scripts/requirements.txt)
├── scripts/                            ❌ 待新建(convert-to-md.mjs + 其他脚本)
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
- 文件读取走统一入口 **`scripts/convert-to-md.mjs --project-dir . --input inbox/<file> --output <tmp>`**:
  - md / txt / csv / json / yaml / xml / html / htm / rst → 直接读
  - pptx / docx / xlsx / pdf → Claude converter 失败则降级 anydoc
  - png / jpg / jpeg / bmp / tiff → paddleocr
  - 其他 / 失败 → FAIL,提示"无法转换 <file>,请手动预处理"
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
- **跑前先跑** `node ./scripts/check-qmd.mjs --project-dir .`,根据返回 `engine` 决定入口:
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
  - **wikilink 是一等公民(Q6)**:plugin 正文写 `[[page]]` / `[[page|显示]]` / `[[page#章节]]`,Obsidian 原生双链 / Karpathy 老 wiki 兼容;OKF 兼容靠 frontmatter `links:` 字段镜像;lint **不再警告** wikilink
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

#### C3.4:check-qmd.mjs 单测
- [ ] 单元测 `<500 / 500~1000 / ≥1000` 三种 pageCount 边界
- [ ] qmd 在 / 不在两种组合 → 共 6 种 case,验证返回 `engine` 字段正确

#### C4:AC-4(lint 全规则)
- [ ] 准备 fixture:故意造孤儿页 / 矛盾页 / 陈旧页(`stale_after` 早于 today)/ 缺必填 frontmatter / 含 `## 摘要` 小节 / 命名飘(`soc-design` vs `socke-design`)
- [ ] 跑 lint,验证每条都报
- [ ] **C4.1 lint --fix 确定性 vs 语义分流**:
  - [ ] 确定性结构修复 fixture:造缺 frontmatter `type` / `tags` 不是 list / `## 摘要` 小节 / sources 缺 3 节骨架 各一份 → 跑 `--fix` → 验证文件被改 + log.md 追加 `**LintFix**` 条目
  - [ ] 语义级问题 fixture:造矛盾页 + 命名飘子目录 + 漏链 + 陈旧页 → 跑 `--fix` → 验证**文件未被改**,只输出提案(包含候选改写 / `git mv` 命令 / 候选链接列表 / 陈旧处理建议)

#### C5:AC-5(frontmatter 自动校验)
- [ ] 写 Python 脚本 `tests/test_frontmatter_schema.py`,对所有 fixture `knowledge/**/*.md` 跑 jsonschema 校验
- [ ] 任何不合规立刻 FAIL

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

### 阶段 D:发布(预计 0.5 天)

- [ ] **D1** 在 GitHub 建 `zhigangliu-bot/aeps-llm-wiki-plugin` 仓库(public)
- [ ] **D2** 把 plugin 根目录内容 push 到 main
- [ ] **D3** 在 `docs/` 配 GitHub Pages(可选)
- [ ] **D4** 在 README.md 写明 `/plugin install zhigangliu-bot/aeps-llm-wiki-plugin`
- [ ] **D5** 发 GitHub release `v0.4.0`,挂上 changelog(从 `templates/tag-template.md` §9 演进记录提炼)

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

| 风险 | 缓解 | 回滚 |
|---|---|---|
| SKILL.md 提示词不够具体,LLM 漂 | 用 design.md §4 流程图作为强约束 + 测试覆盖 | 改 SKILL.md 措辞,本地再跑测试 |
| 测试 fixture 与 OKF v0.2 漂移 | 测试 fixture 锁定版本 | 重读 OKF-SPEC.md,改 schema 后再测 |
| GitHub push 误推敏感文件 | `.gitignore` 提前建好(排除 `tests/fixtures/secrets/`、`*.local.md`) | 删 remote + force push + 撤 token |
| plugin 升级破坏用户项目副本 | 字典 sync 策略已固化为"本地优先 + append" | 用户可手动从 templates/ 重新复制 |

---

## 4. 时间预算汇总

| 阶段 | 工作量 | 备注 |
|---|---|---|
| A:plugin 骨架 | 0.5–1 天 | 模板化,快 |
| B:5 个 SKILL.md | 2–3 天 | 每个 SKILL.md 重点在"边界规则",不能省 |
| C:测试用例 | 1–2 天 | CLAUDE.md 硬约束,必须做 |
| D:发布 | 0.5 天 | GitHub 操作 + release notes |
| **合计** | **4–6.5 天** | 集中 1 周可完成 |

---

## 5. 不在本次范围(后续版本)

- v0.5:knowledge-base 类 MCP server(目前 NFR-1 硬约束禁止,可解约后考虑)
- v0.5:Web 端 UI(目前纯 CLI / Claude Code 形态)
- v0.6:多语言(目前 NFR-3 中文优先,英文术语保留)
- v1.0:正式 GA,定稿 schema,冻结 tag-template.md 6 轴

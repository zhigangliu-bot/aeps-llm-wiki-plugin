# aeps-llm-wiki-plugin — implement-init (M2.1)

> **状态**:草稿(待 review)
> **创建日期**:2026-09-06
> **作者**:zhigang.liu(由 Claude Code 起草)
> **上游契约**:`prd.md v0.4.1`(已冻结)+ `design.md v0.1.1`(已冻结)+ `schema.md v0.5.4`(工作流入口)
> **范围**:仅 `aeps-llm-wiki-init` skill 实现细节;lint/ingest/query/synthesize 各有独立 `implement-{skill}.md`,**本文件不交叉污染**
> **完成定义**:`SKILL.md(/aeps-llm-wiki-init)` + `scripts/init/*` + `trellis-check` 全套通过;本文档冻结

---

## 0. 任务总览

### 0.1 目标

实现 `/aeps-llm-wiki-init` skill,让用户跑一次,在 5 分钟内得到一个可用的 OKF 知识库目录结构(首次启用 / 幂等再入)。

### 0.2 完成定义(M2.1 done = )

1. ✅ 本 `implement-init.md` 冻结 → commit
2. ✅ `SKILL.md(/aeps-llm-wiki-init)` 写完
3. ✅ `scripts/init/*` 全套写完(`init` skill 在 `scripts/init/` 目录,后续 ingest/query/lint/synthesize 各占独立子目录)
4. ✅ 单元测试(`scripts/init/test/*`)+ 至少 1 个 e2e(空目录 + 首次启用)跑通
5. ✅ `trellis-check` 全套通过(本 task 的 check.jsonl 4 条目 + implement.jsonl 4 条目一致性)
6. ✅ 一个 atomic commit 落盘;分支 feature 提 PR(若已 fork)

### 0.3 不做(明确边界,避免 scope creep)

- ❌ 不写 ingest / query / lint / synthesize 任何代码 —— 见 `implement-{ingest,query,lint,synthesize}.md`
- ❌ 不发明 frontmatter 字段(只复述 `frontmatter-spec.md`)
- ❌ 不实现 CLAUDE.md 受控区块之外的项目级配置文件(`.gitignore` / Obsidian `.obsidian/` 由用户自己管)
- ❌ 不引入 LLM API 调用(init 流程**纯机械**,LLM 不参与)
- ❌ 不实现除"6 顶层目录固定 + 22 知识目录(18 叶子 + 4 顶层索引)+ 15 raw 子目录"以外的目录结构
- ❌ **不**引入任何 npm 依赖(init 阶段零 npm 依赖,全部 Node.js 内置 API)

### 0.4 上下游

```
[上游契约]
prd.md v0.4.1 §4.1 init + 流程表 + AC-1 + NFR-1/2/4/5/6
design.md v0.1.1 §1.2 6 顶层目录 + §4 脚本契约 + §7.3 幂等策略
schema.md v0.5.5 §2 type↔目录绑死(22 知识目录: 18 叶子 + 4 顶层索引) + §6 变更历史
doc/template/rawdir-spec.md (15 raw 子目录字典)
doc/template/concept-entities-spec.md (14 子类判定示例)
doc/template/tag-spec.md (6 轴 tag 字典)

[下游消费]
- ingest skill 启动前必须 init 完成(knowledge/ 22 目录存在)
- query / lint / synthesize 启动前 init 必须完成
```

---

## 1. 脚本清单(scripts/init/*)

> **设计哲学**:能调用脚本的尽量调用脚本(用户全局 CLAUDE.md),init 流程中确定性动作 100% 走脚本,SKILL.md 只做编排 + 用户对话拍板。
>
> **命名**:所有脚本放 `scripts/init/`,不用单文件如 `scripts/init.js`(便于后续新增子脚本时命名空间清晰)。
>
> **测试**:每个脚本配一个 `scripts/init/test/<name>.test.js`,用 `node:test`(内置,零依赖)。

### 1.1 脚本接口契约

| 脚本 | 入参 | 行为 | 出参 / 副作用 | 单测覆盖 |
|---|---|---|---|---|
| `scripts/init/detect-state.js` | `--project <dir>` | 检测 `{project}/` 是否已含 6 顶层目录 + `.gitkeep`;返回 JSON `{ state: "fresh" \| "reentry", missing: [...], present: [...] }` | stdout JSON,exit 0 | 3 个 fixture:空目录 / 部分初始化 / 完全初始化 |
| `scripts/init/build-skeleton.js` | `--project <dir> [--dry-run]` | 首次启用 → 建6 顶层 + 各 `.gitkeep` + 18 知识叶子 + 15 raw 子目录;**不动用户已有内容** | 写文件(6+18+15 = 39 个 `.gitkeep`)+ 4 件顶层索引模板 | 1 个 fixture:空目录跑完,验证 39 目录 + 4 件索引存在 |
| `scripts/init/sync-files.js` | `--project <dir> [--dry-run]` | 幂等再入:按 `prd.md §4.1 文件同步策略表` 对 `inbox/README.md` / `raw/README.md` / `templates/*` / `templates/README.md` / `templates/concept-entities-spec.md` / `templates/tag-spec.md` / `templates/page-*.md` / `scripts/*` / `schema/*` / `knowledge/index.md` / `knowledge/overview.md` / `knowledge/glossary.md` / `knowledge/log.md` 走"覆盖 vs 保留 vs 补建 vs 字典同步"4 分流;返回 JSON `{ added: [...], updated: [...], skipped: [...], warned: [...] }` | 写文件 + stdout JSON 摘要 | 4 个 fixture:首次同步 / re-run 不覆盖 / 字典追加 / 用户删除的不恢复 |
| `scripts/init/patch-claude-md.js` | `--project <dir> [--dry-run]` | 幂等管理 `{project}/CLAUDE.md` 受控区块(标记 `<!-- aeps-llm-wiki-plugin:start/end -->`):不存在 → 末尾追加;已存在相同区块 → 跳过;旧版本 → 替换;不修改用户其他内容 | 写 `CLAUDE.md`(必要时) | 4 个 fixture:无文件 / 已存在同区块 / 旧版本区块 / 用户手写在区块外 |
| `scripts/init/sync-report.js` | `--project <dir> [--json]` | 综合输出本次 init 摘要:首次 vs 幂等 / added / updated / skipped / warned 计数 + 文件列表 | stdout 人类可读或 JSON | 1 个 fixture:跑完一次完整 init,验证摘要格式 |

### 1.2 关键设计决策

- **5 个脚本分而治之**的理由:`detect-state` 是只读探测,`build-skeleton` 是首次启用,`sync-files` 是幂等再入,`patch-claude-md` 是特殊单点(CLAUDE.md 受控区块算法独立),`sync-report` 是输出聚合;每个脚本职责单一,易测易换
- **不用单文件 `init.js` 巨型入口** 的理由:用户全局 CLAUDE.md 要求"skill 越薄越好,确定性的动作能调用脚本的尽量调用脚本";SKILL.md 只编排,5 个 `.js` 各管一段
- **每个 skill 一个子目录**(`scripts/init/`、`scripts/ingest/`、`scripts/query/`、`scripts/lint/`、`scripts/synthesize/`),命名空间清晰;init 跑时用户工程的 `scripts/init/*` 也按此布局
- **`--dry-run` 普遍可用**:每个脚本默认接 `--dry-run`,不写盘只输出 diff;SKILL.md 在用户拍板前先用 dry-run 展示给用户看
- **JSON stdout 是契约**:所有脚本输出结构化 JSON 时用 stdout,日志/进度走 stderr;便于 SKILL.md 用 `JSON.parse` 解析(避免脆弱字符串匹配)
- **依赖**:**init 阶段零 npm 依赖** —— 全用 Node.js 内置 API(`node:fs` / `node:path` / `node:fs/promises` / `node:process` / `node:test` / `node:assert`);**不**引入 `js-yaml`(init 不解析 frontmatter,只写4 件顶层索引的初始 frontmatter 字符串);**不**引入 `commander` / `yargs`(`process.argv` 手解析,顶层目录约定本身就是参数上限)

### 1.3 不写的脚本(显式禁)

- ❌ 不写 `scripts/init/infer-intent.js`(LLM 决策,不放脚本)
- ❌ 不写 `scripts/init/converse.js`(对话由 SKILL.md 管)
- ❌ 不写 `scripts/init/check-deps.js`(依赖检查由 SKILL.md 跑 `npm --version` / `node --version` / `@firecrawl/anydoc` 是否可解析)

---

## 2. frontmatter 字段填写规则

> init 流程**不写** `knowledge/**/*.md` 内容页;但要写 `knowledge/{index,overview,glossary,log}.md` 4 件顶层索引模板,这 4 件的 frontmatter 由 init 一次性填好,**后续由 `aggregate-index.js` 增量维护**(详见 `implement-ingest.md §2`)。

### 2.1 4 件顶层索引初始 frontmatter

```yaml
# knowledge/index.md (主目录)
---
type: index                    # OKF 兼容(新增类型,仅用于主目录)
title: "{project} Knowledge Index"
aliases: ["index", "Index"]
generated:
  by: agent: aeps-llm-wiki-init/{plugin-version}
  at: "{ISO 8601}"             # init 跑完的当时时间
updated: "{ISO 8601}"          # init 写入,后续 ingest 增量维护(Q7 死循环防护:不动)
tags:
  - "domain/knowledge-management"
  - "layer/index"
  - "docform/index"
  - "maturity/sketch"
---

# knowledge/overview.md (大图)
---
type: overview
title: "{project} Knowledge Overview"
aliases: ["overview", "Overview"]
generated:
  by: agent: aeps-llm-wiki-init/{plugin-version}
  at: "{ISO 8601}"
updated: "{ISO 8601}"
tags:
  - "domain/knowledge-management"
  - "layer/overview"
  - "docform/overview"
  - "maturity/sketch"
---

# knowledge/glossary.md (术语表)
---
type: glossary
title: "{project} Knowledge Glossary"
aliases: ["glossary", "Glossary"]
generated:
  by: agent: aeps-llm-wiki-init/{plugin-version}
  at: "{ISO 8601}"
updated: "{ISO 8601}"
tags:
  - "domain/knowledge-management"
  - "layer/glossary"
  - "docform/glossary"
  - "maturity/sketch"
---

# knowledge/log.md (变更日志)
---
type: log
title: "{project} Knowledge Log"
aliases: ["log", "Log"]
generated:
  by: agent: aeps-llm-wiki-init/{plugin-version}
  at: "{ISO 8601}"
updated: "{ISO 8601}"
tags:
  - "domain/knowledge-management"
  - "layer/log"
  - "docform/log"
  - "maturity/sketch"
---
```

### 2.2 init 写出的其它文件 frontmatter

- `inbox/README.md`:`type` 字段不写(OKF 兼容——`type` 不是 OKF 强制;在 `templates/inbox-readme.md` 里就不写)
- `raw/README.md` / `raw/{subdir}/.gitkeep`:`.gitkeep` 不写 frontmatter,空文件即可
- `templates/*`:模板的 frontmatter 由模板自带(已存在,init 拷贝即可,不二次改写)
- `schema/*`:纯规范文件,frontmatter 不强制;按 `schema/*.md` 原样拷贝

### 2.3 init **不动** frontmatter 字段

按 `design.md §4.3` 规则 + `prd.md §4.1 文件同步策略表`:

- `templates/page-*.md`:模板自带 frontmatter,init **只补建缺失,不覆盖已有**
- `scripts/*`:脚本无 frontmatter
- `schema/*`:规范无 frontmatter

### 2.4 18 叶子存储目录的 `.gitkeep`

每个叶子目录放一个空 `.gitkeep` 文件(无 frontmatter),**不预填任何 markdown 模板**——内容页由 ingest 时按 `gen-page.js --type <type>` 生成(详见 `implement-ingest.md §1`)。

---

## 3. CI 矩阵

### 3.1 平台 / Node 版本

| 项 | 基线 | 锁的方式 |
|---|---|---|
| Node.js | LTS(20.x 或更新) | `package.json` `engines.node: ">=20"` |
| OS | Windows 10+ / macOS 13+ / Ubuntu 22.04+ | CI 多平台 matrix(见 §3.2) |
| Git | 2.30+ | 不锁(init 不依赖 git 操作) |
| Shell | bash(Git Bash / WSL / Unix) | SKILL.md 不调 shell,只 `node` |

### 3.2 CI 触发矩阵

| 事件 | 跑什么 | 目的 |
|---|---|---|
| PR open / push to feature branch | 单测 + 静态检查 + `node --check` 语法 | 防回归 |
| PR merge to master | 单测 + e2e(init 首次启用 + 幂等再入)+ 跨平台 smoke | 集成验证 |
| tag push `v*` | 同上 + `package.json` 版本号一致性检查 | 发版前 |
| manual dispatch | 全部 | 调试 |

### 3.3 依赖校验

init 涉及的依赖**全部内置或弱依赖**——不需要外部 binary:

- 无 `@firecrawl/anydoc`(init 不转换)
- 无 Node 版 PaddleOCR
- 无 LibreOffice
- 无 qmd
- 无 `js-yaml`(init 不解析已有 frontmatter,只写4 件顶层索引的初始 frontmatter 字符串模板)
- 无任何 npm 依赖——`package.json` `dependencies: {}` 空对象

> **init 阶段零 npm 依赖** 是有意为之。YAML 解析由 ingest 阶段的 `gen-page.js` + `aggregate-index.js` 处理,在 `implement-ingest.md` §3.3 里锁定 `js-yaml ^4.1.0`。init 走过的 4 件顶层索引,后续 ingest 跑 `aggregate-index.js` 时才用 YAML 库解析;init 阶段只需要把模板字符串原样写入文件。

### 3.4 静态检查

- `node --check scripts/init/*.js`(语法)
- `node --check scripts/init/test/*.test.js`(测试语法)
- ESLint 可选(实现期决定;Ponytail 默认不开,内置 lint 够了再说)

---

## 4. 测试用例表

> 对齐 `prd.md §7` 中 init 涉及的所有 AC / NFR / COMPAT。每条标"测什么 / 怎么测 / 通过标准 / 优先级"。
>
> **测试方式**:Node.js 内置 `node:test` + `node:assert` + `node:fs/promises`。fixture 放在 `scripts/init/test/fixtures/`(空仓库 / 部分初始化 / 完全初始化 / 字典追加场景)。
>
> **e2e**:在 `temp/` 下跑一个完整 init 流程,验证产物结构。

### 4.1 功能验收(对齐 AC-1)

| ID | 测什么 | 怎么测 | 通过标准 | 优先级 |
|---|---|---|---|---|
| AC-1.1 | 首次启用 5 分钟内得到完整目录 | e2e:在 `temp/e2e-init-fresh/` 跑全套脚本 | 6 顶层 + 39 `.gitkeep`(18 知识 + 15 raw + 6 顶层)+ 4 件顶层索引模板存在 | P0 |
| AC-1.2 | 幂等再入不破坏用户内容 | e2e:在 `temp/e2e-init-reentry/` 跑首次 + 用户手改 `knowledge/index.md` + re-run | re-run 后 `knowledge/index.md` 内容不变;sync 摘要正确 | P0 |
| AC-1.3 | `schema/schema.md` 覆盖 ingest/query/lint | 单测:grep `schema.md` 是否引用 ingest / query / lint | 3 个关键词都出现 | P0(对齐 `schema.md §1`) |

### 4.2 非功能验收(对齐 NFR-1/2/4/5/6)

| ID | 测什么 | 怎么测 | 通过标准 | 优先级 |
|---|---|---|---|---|
| NFR-1 | 不引入 MCP / CLI daemon / RAG / embedding | 代码审查:`scripts/init/*` 不引用 `child_process` 启动常驻进程;不依赖任何 LLM 包 | grep 无 `child_process.spawn` 启动 daemon 模式;无 `openai` / `anthropic` / `chromadb` | P0 |
| NFR-2 | plugin 代码 / 文档 / 测试 / schema 各居其位 | 文件路径规范 | `scripts/init/*.js` + `scripts/init/test/*.test.js` + 引用 `doc/*` 规范 | P0 |
| NFR-4 | 无绝对路径 | grep `scripts/init/*.js` 检查路径 | 无 `C:\\` / `/Users/` / `/home/` 等绝对路径 | P0 |
| NFR-5 | 临时文件进 `temp/` | grep `scripts/init/*.js` 检查临时目录 | 所有 `os.tmpdir()` 之外写的临时文件路径在 `temp/` 下 | P0 |
| NFR-6 | LICENSE = Apache 2.0 | 文件存在性 | `LICENSE` 文件存在且包含 "Apache License, Version 2.0" 字样 | P1 |

### 4.3 兼容性验收(对齐 COMPAT-3)

| ID | 测什么 | 怎么测 | 通过标准 | 优先级 |
|---|---|---|---|---|
| COMPAT-3 | `schema/schema.md` zero-shot 可执行 | 人工 review + 关键路径 e2e(将 `schema.md` 拷到空工程跑一次 init) | e2e 不报错且产物结构正确 | P0 |

### 4.4 文件同步策略表验收(对齐 prd.md §4.1 表)

| ID | 测什么 | 怎么测 | 通过标准 | 优先级 |
|---|---|---|---|---|
| SYNC-1 | `inbox/README.md` re-run 覆盖为 plugin 当前版本 | fixture:首次 sync → 改 inbox/README → re-run | 第二次内容 = plugin 模板当前内容 | P0 |
| SYNC-2 | `templates/page-*.md` 缺失补建 / 已有不覆盖 | fixture:首次建所有模板 → 删一个 → re-run | 缺失模板重建;已有模板内容不变 | P0 |
| SYNC-3 | `templates/README.md` 覆盖 | fixture:首次 sync → 改 README → re-run | 第二次内容 = plugin 当前 | P0 |
| SYNC-4 | `templates/concept-entities-spec.md` / `tag-spec.md` 字典同步(只追加,不恢复) | fixture:首次 sync → 用户删一段 → re-run | 用户删的不恢复;plugin 新增内容追加 | P0 |
| SYNC-5 | `scripts/*` 缺失补建 / 已有不覆盖 | fixture:首次 sync → 删一个 → re-run | 缺失补建;已有不变 | P0 |
| SYNC-6 | `schema/*` 覆盖为 plugin 当前版本 | fixture:首次 sync → 改 schema/* → re-run | 第二次 = plugin 当前 | P0 |
| SYNC-7 | `knowledge/index.md` / `overview.md` / `glossary.md` 不修改,保留用户内容 | fixture:首次 sync → 改这三件 → re-run | 内容不变 | P0 |
| SYNC-8 | `knowledge/log.md` 追加 Init 记录,不删除已有 | fixture:首次 sync → 用户追加 log → re-run | 用户追加的记录保留 + Init 记录存在 | P0 |
| SYNC-9 | CLAUDE.md 受控区块不存在 → 创建;相同 → 跳过;旧版 → 替换;不动区块外 | 4 个 fixture:无文件 / 已存在同区块 / 旧版本区块 / 用户手写在区块外 | 4 个 fixture 全过 | P0 |

### 4.5 幂等性验收

| ID | 测什么 | 怎么测 | 通过标准 | 优先级 |
|---|---|---|---|---|
| IDEMP-1 | init 跑 N 次产出与跑 1 次一致(差异只在 log.md 追加 Init 记录) | fixture:跑 3 次,比对产物(除 log.md) | 哈希一致 | P0 |
| IDEMP-2 | `--dry-run` 不写盘,只输出 diff | fixture:跑 `--dry-run`,再跑实,确认 dry-run 没写任何文件 | mtime 一致 / stdout 有 diff 输出 | P0 |

### 4.6 init sync 摘要报告验收

| ID | 测什么 | 怎么测 | 通过标准 | 优先级 |
|---|---|---|---|---|
| REPORT-1 | sync 摘要含 added / updated / skipped / warned 计数 + 文件列表 | fixture:跑一次 sync,捕获 stdout | JSON 含 4 字段且非空 | P1 |
| REPORT-2 | init 末尾输出"init 完成"信号(供 SKILL.md 拍板) | fixture:跑完 init,exit 0 + stdout 摘要 | exit 0 + 摘要完整 | P1 |

---

## 5. 部署策略

### 5.1 plugin 本体版本号

- `package.json` `version` = 与 `schema.md` 顶部 `plugin 版本` 字段**强一致**
- **手动同步**:任何时候改 `schema.md` `plugin 版本` 字段,**必须**同步 `package.json` `version`(用 `trellis-check` 卡校验)
- 升号策略:`patch` = bugfix / 文档修订;`minor` = 新 skill / 新功能 / 新字段;`major` = 字段语义变化 / OKF 兼容性破坏
- 当前目标版本:`schema.md 0.5.5` → `package.json 0.5.5`(M2.1 落 init 实现时同步)

### 5.2 跨版本兼容

- init **不**对老版本 plugin 生成的项目做"升级迁移"(老项目走幂等再入,自然补齐新增文件)
- 老项目用户主动 `git diff` 看 sync 摘要决定是否接受补建
- **不**写"自动升级"脚本(init 的 sync 策略表就是升级策略,无需额外脚本)

### 5.3 用户工程的 schema/ 同步策略

- init 第 5 步建 `schema/` 时**全量覆盖**(对齐 prd.md §4.1 表 `schema/*` 行)
- 老用户若自定义 schema 字段,re-run init **会覆盖丢失**——这是已知取舍,README 警告用户
- 升级提示文案放 `templates/README.md` 顶部,init 拷过去

### 5.4 init 输出分发路径

- `scripts/init/*` → plugin 本体 `aeps-llm-wiki-plugin/scripts/init/`
- init 跑时 → 用户工程 `{project}/scripts/init/*`
- init 不在用户工程写 SKILL.md(SKILL.md 留在 plugin 本体,Claude Code 通过 plugin 机制加载)

### 5.5 临时文件

- e2e fixture 放 `temp/e2e-init-*/`(用完即删,`scripts/init/test/cleanup.js` 在 CI 跑完自动清)
- 单测 fixture 放 `scripts/init/test/fixtures/`(commit 进 git,小文件)
- SKILL.md 跑 init 时不创建任何 `temp/` 文件(全在用户工程)

---

## 6. 风险与回滚点

### 6.1 风险表

| 风险 | 影响 | 缓解 |
|---|---|---|
| 用户工程已有同名目录但内容非 .gitkeep | init 误判为"已初始化",跳过建目录 | `detect-state.js` 检查每个顶层目录含 `.gitkeep`;**任意一个**缺失 → 视为首次启用分支 |
| 用户手改 `schema/*` 后 re-run init | 用户修改丢失 | README 警告;sync 摘要显示 `updated` 行让用户知情 |
| CLAUDE.md 受控区块正则匹配失败(用户手改 start/end 标记) | 受控区块算法失效,init 重复追加 | `patch-claude-md.js` 用严格正则 `<!-- aeps-llm-wiki-plugin:start -->[\s\S]*?<!-- aeps-llm-wiki-plugin:end -->`;匹配失败 → 报错退出,不静默追加 |
| 跨平台路径(`/` vs `\`)在 Windows 测试通过,macOS 失败 | 跨平台 e2e 跑挂 | CI 矩阵 macOS + Ubuntu + Windows 三平台跑同一套单测;`node:path` 全程 `join` 不硬编码 |
| `js-yaml` 解析失败(用户工程已有 yaml 文件但格式非标准) | sync-files 报错 | 单测覆盖异常路径;SKILL.md 拍板时显示错误给用户 |
| init 第 2 步建 39 个 `.gitkeep` 时磁盘满 / 权限错 | 部分目录已建,半完成 | 每个 `mkdir` 包 try/catch;失败 → 已建的回滚(rmdir)+ 报错退出 |
| 首次启用 5 分钟超时(网速慢导致 `npm install js-yaml` 卡住) | AC-1 失败 | init 跑前检查 `js-yaml` 是否已装;未装 → 提示用户先 `npm install`,不静默安装 |
| `temp/` 不存在导致 e2e 写失败 | CI 跑挂 | `scripts/init/test/setup.js` 在跑前 `mkdir -p temp/` |

### 6.2 回滚点

- **init 全程无回滚压力**:init 是**首次启用 + 幂等再入**,跑完用户不满意可以 `rm -rf` 整个 `{project}/` 重建(除了 CLAUDE.md 受控区块,init 保留该区块)— Ponytail 默认行为,**不**写"软删除"或"事务"机制
- **CLAUDE.md 受控区块**:误替换 / 误删 → 重新跑 init 修复(幂等再入会重新建区块)
- **schema/ 全量覆盖**:`git checkout HEAD~ -- schema/` 回滚
- **scripts/init/* 自身**:`git checkout HEAD -- scripts/init/` 回滚

### 6.3 不应(显式禁)

- ❌ 不应在 init 中"自动 `npm install`"任何依赖——用户工程可能未配 npm;若需依赖,README 提示用户手动装
- ❌ 不应 init 中调 git 命令(G7 不强制 git,用户可能用 SVN / Mercurial)
- ❌ 不应 init 中创建 Obsidian `.obsidian/` 配置(项目级 Obsidian 配置由用户自己管)
- ❌ 不应 init 中执行任何 `child_process.spawn` 启动 daemon / watch / serve(对齐 NFR-1)

---

## 7. 引用

- 上游契约:
  - [prd.md v0.4.1 §4.1](../design/prd.md)—— init 功能需求 + 流程表 + AC-1 + NFR
  - [design.md v0.1.1 §1.2 + §4 + §7.3](../design/design.md)—— 6 顶层目录 + 脚本契约 + 幂等策略
  - [schema.md v0.5.4 §2 + §6](../schema/schema.md)—— type↔目录绑死 + 变更历史
- 规范字典:
  - [doc/template/rawdir-spec.md](../template/rawdir-spec.md)—— 15 raw 子目录字典
  - [doc/template/concept-entities-spec.md](../template/concept-entities-spec.md)—— 14 子类判定示例
  - [doc/template/tag-spec.md](../template/tag-spec.md)—— 6 轴 tag 字典
  - [doc/schema/frontmatter-spec.md](../schema/frontmatter-spec.md)—— frontmatter 字段规范
  - [doc/schema/frontmatter.schema.json](../schema/frontmatter.schema.json)—— 机器读校验
- 下游消费:
  - `implement-ingest.md`(M2.2)—— ingest 启动前依赖 init 产物
  - `implement-query.md`(M2.3)—— query 启动前依赖 init + ingest
  - `implement-lint.md`(M2.4)—— lint 检查 init 产物 + 后续 ingest 产物
  - `implement-synthesize.md`(M2.5)—— synthesize 启动前依赖 init + ingest

---

## 8. 变更历史

| 版本 | 日期 | 变更 |
|---|---|---|
| v0.1.0-draft | 2026-09-06 | 初版(370 行):§0 任务总览 + §1 5 脚本清单 + §2 4 件顶层索引 frontmatter 规则 + §3 CI 矩阵 + §4 24 条测试用例 + §5 部署策略 + §6 风险与回滚 + §7 引用 + §8 变更历史 |
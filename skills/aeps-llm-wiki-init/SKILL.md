---
name: aeps-llm-wiki-init
description: 初始化 aeps-llm-wiki 知识库目录结构(首次启用 / 幂等再入)
plugin-version: 0.6.0
allowed-tools: Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/init/detect-state.js*),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/init/build-skeleton.js*),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/init/sync-files.js*),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/init/patch-claude-md.js*),Bash(node ${CLAUDE_PLUGIN_ROOT}/scripts/init/sync-report.js*)
---

## Change History

- 2026-09-08 / 批次 1 / R1 (P0-1):顶部新增"脚本路径约定"段;说明 `${CLAUDE_PLUGIN_ROOT}` 由调用方注入,或用 `--plugin-root` CLI 参数显式传递冗余兜底;明确脚本位于 plugin 仓根的 `scripts/` 下,**不**在 `skills/<skill>/scripts/` 下。
- 2026-09-08 / 批次 1 / R4 (P0-1):命令行全部追加 `--plugin-root ${CLAUDE_PLUGIN_ROOT}` 参数,确保 `${CLAUDE_PLUGIN_ROOT}` env 未注入时仍能跑通。
- 2026-09-08 / 批次 3 / R6 (P2-4):步骤 5 `sync-report.js` 输出改为展示工程根实际状态(`state_snapshot`)+ 本次变更数(`delta_from_last_run`),幂等再跑不再全 0。
- 2026-09-08 / 批次 3 / R3 (P1-6):inline preflight 已内置到所有 ingest/init 脚本顶部,缺包立即 ERROR 并打印精确 `npm install` 命令;旧的 `scripts/ingest/preflight.js` 仍保留(SKILL.md ingest 步骤 0.5 可继续主动调用),与 inline 并存不冲突。
- 2026-09-08 / 批次 4 / P3-2:新增步骤 0 依赖 preflight(inline 内置,可选显式跑),统一为"plugin 内置 preflight,缺包即停并给精确 `npm install <pkg>` 命令,不自动安装";后续步骤 1-7 重新编号。
- 2026-09-08 / 批次 4 / P3-1:frontmatter `plugin-version` 字段从旧版本字符串升级为 0.5.6(对齐 plugin.json)。
- 2026-09-08 / 批次 5 (P4-1):**breaking** —— 用户工程根从 6 顶层改为 5 顶层 + `doc/` 子目录布局(`schema/` `templates/` → `doc/schema/` `doc/templates/`);`detect-state.js` 输出新增 `legacyDirs` 字段;re-run init 自动迁移老用户遗留目录(merge,doc 优先;空目录删,非空保留 + WARN);`patch-claude-md.js` 受控区块文案指向 `doc/schema/schema.md`;`sync-files.js` 输出新增 `migrated` 字段。

## 脚本路径约定(批次 1,2026-09-08)

> **脚本路径约定**:本 skill 所有 `node scripts/xxx.js` 命令以 `${CLAUDE_PLUGIN_ROOT}` 为 plugin-root;该变量由调用方注入(plugin 自动注入或用户 shell 导出),或通过 `--plugin-root` CLI 参数显式传递冗余兜底。

- 脚本均在 plugin 仓根的 `scripts/` 下,**不**在 `skills/<skill>/scripts/` 下。
- 默认调用形式:`node ${CLAUDE_PLUGIN_ROOT}/scripts/init/detect-state.js ...`(env 已注入)
- 兜底调用形式:`node ${CLAUDE_PLUGIN_ROOT}/scripts/init/detect-state.js --plugin-root ${CLAUDE_PLUGIN_ROOT} ...`(env 注入失败时显式冗余)
- 当 `${CLAUDE_PLUGIN_ROOT}` env 未注入(plugin loader 未生效 / shell 没 export),`--plugin-root` 是唯一兜底,**必须**显式传。

# /aeps-llm-wiki-init

初始化用户的 wiki 项目工程,生成 5 顶层目录 + `doc/{schema,templates}/` 2 子目录 + 18 知识叶子 + 15 raw 子目录 + 4 件顶层索引模板。已存在工程走幂等再入(只补缺失,不覆盖用户内容);v0.5.7 之前的老工程自动迁移遗留目录到 `doc/` 下。

## 路径布局(plugin 仓 vs 用户工程,v0.5.8 起)

init skill 把 plugin 仓的 `doc/{schema,template}/` + `scripts/` 同步到用户工程 `doc/` 下;**用户工程与 plugin 仓的「文档」层级 1:1 对齐**(消除脚本路径混淆):

| plugin 仓根 | 用户工程根 | sync 行为 |
|---|---|---|
| `doc/schema/` | `doc/schema/` | overwrite |
| `doc/template/` | `doc/templates/`(复数,可接受差异) | backfill missing;preserve existing |
| `scripts/` | `scripts/` | backfill missing;preserve existing |

**老用户迁移**(v0.5.7 之前 init 过的工程):`detect-state.js` 探到根目录遗留 `schema/` `templates/` → `sync-files.js` 自动 merge 到 `doc/{schema,templates}/`(doc 优先,仅补缺失);空目录自动删,非空保留 + WARN 提示用户手动 `git rm`。

## 触发

用户在新项目里跑 `/aeps-llm-wiki-init`,或在已有项目里再跑一次。

## 编排流程(SKILL.md 只编排,不写实现)

### 步骤 0:依赖 preflight(inline 内置,可选显式跑)

> **plugin 内置 preflight,缺包即停并给精确 `npm install <pkg>` 命令,不自动安装**(对齐批次 3 R3 + P3-2 修复)。

所有 init 脚本顶部已 inline 调用 `scripts/lib/preflight.js` 的 `requireDeps`,缺包时脚本启动即 ERROR 并打印精确 `npm install` 命令,LLM 跳此步也会被拦截。

如需显式探查:

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/ingest/preflight.js --plugin-root ${CLAUDE_PLUGIN_ROOT} --scripts-dir <用户工程根>/scripts --json
```

- `ok == true` → 进入步骤 1
- `ok == false` → 按 stderr `npm install` 提示让用户装,exit 0 后重跑本步

### 步骤 1:探测工程状态(只读)

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/init/detect-state.js --project <用户工程根> --plugin-root ${CLAUDE_PLUGIN_ROOT} --json
```

读 stdout JSON 解析:
- `state: "fresh"` → 走步骤 2-7 完整流程
- `state: "reentry"` → 走步骤 4-7 同步策略表
- `missing: [...]` → 提示用户缺哪些顶层目录(首次启用必走完整流程)
- `legacyDirs: ["schema","templates",...]` → 老用户迁移(步骤 4 sync-files.js 自动执行,无需单独步骤);`legacyDirs: []` → 正常

### 步骤 2:首次启用 dry-run 预览

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/init/build-skeleton.js --project <dir> --plugin-root ${CLAUDE_PLUGIN_ROOT} --dry-run --json
```

把 JSON 输出展示给用户(包含 `created[]` 列表),询问"是否继续?是 / 否 / 调整路径"。

### 步骤 3:首次启用实跑

用户拍板后:

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/init/build-skeleton.js --project <dir> --plugin-root ${CLAUDE_PLUGIN_ROOT} --json
```

JSON 含 `counts.gitkeepTotal`(应为 38=5+18+15)+ `created[]` 列表。

### 步骤 4:同步策略文件(scripts/templates/schema)

无论是首次还是幂等再入,都跑:

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/init/sync-files.js --project <dir> --plugin-root ${CLAUDE_PLUGIN_ROOT} --json
```

JSON 含 `migrated / added / updated / skipped / warned` 5 数组 + 计数。

- 首次启用:`added` 应有 doc/templates/page-*.md、tag-spec.md、concept-entities-spec.md、rawdir-spec.md 等;`migrated` 应为空
- 老用户迁移:`migrated` 应含 `{from:"./schema", to:"./doc/schema", ...}` 与 `{from:"./templates", to:"./doc/templates", ...}`;若 `warned` 有 `non_empty_legacy_dir` → 摘要时提醒用户手动 `git rm` 遗留目录
- 幂等再入:`updated` 应含 doc/schema/* 全量覆盖 + doc/templates/README.md 覆盖 + inbox/raw README 覆盖;`skipped` 应含用户已改的 doc/templates/page-*.md

### 步骤 5:CLAUDE.md 受控区块

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/init/patch-claude-md.js --project <dir> --plugin-root ${CLAUDE_PLUGIN_ROOT} --json
```

JSON 含 `action: created|appended|updated|skipped|error`。

- `action: error` → 报错给用户,让用户手修 CLAUDE.md(orphan markers),不静默追加
- 其他 → 继续

### 步骤 6:聚合摘要报告

```bash
# 把步骤 3/4/5 的 stdout JSON 串起来
(node ${CLAUDE_PLUGIN_ROOT}/scripts/init/build-skeleton.js --project <dir> --plugin-root ${CLAUDE_PLUGIN_ROOT} --json; \
 node ${CLAUDE_PLUGIN_ROOT}/scripts/init/sync-files.js --project <dir> --plugin-root ${CLAUDE_PLUGIN_ROOT} --json; \
 node ${CLAUDE_PLUGIN_ROOT}/scripts/init/patch-claude-md.js --project <dir> --plugin-root ${CLAUDE_PLUGIN_ROOT} --json) \
 | node ${CLAUDE_PLUGIN_ROOT}/scripts/init/sync-report.js --project <dir>
```

人类可读输出,展示 added/updated/skipped/warned 计数 + 文件列表。

### 步骤 7:用户拍板完成

- 把摘要给用户看
- 用户拍板"完成" → init 流程结束
- 用户拍板"回滚" → 提示用户 `rm -rf` 整个工程根重建(对齐 implement-init.md §6.2:init 不写软删除)

## 拍板门总结

| 时机 | 拍板内容 | 默认 |
|---|---|---|
| 步骤 2 | dry-run diff 是否符合预期 | 等用户明确"是" |
| 步骤 6 | 摘要是否接受(skipped 列表确认用户改的文件保留) | 等用户明确"完成" |
| 步骤 5 orphan markers | 用户手修 CLAUDE.md | 不静默追加,报错退出 |

## 不做什么(SKILL.md 边界)

- 不写 frontmatter 字段(只引用 `frontmatter-spec.md`)
- 不调 LLM API(init 是纯机械)
- 不实现 CLAUDE.md 受控区块之外的配置文件(`.gitignore`、`.obsidian/` 由用户自己管)
- 不引入 npm 依赖(5 个 init 脚本零依赖)
- 不自动 commit(主 session 决定)
- 不调 git / SVN / Mercurial

## 拍板门失败的回滚点

- 步骤 0-1 之间:**无副作用**,可任意重跑
- 步骤 3-6 之间:不满意 → `rm -rf` 工程根(除 CLAUDE.md 受控区块)重建
- CLAUDE.md 受控区块误改:重新跑 init,自动替换

## 引用

- 设计文档:`doc/design/implement-init.md`
- 上游契约:`doc/design/prd.md` §4.1
- 工作流入口:`doc/schema/schema.md` §1

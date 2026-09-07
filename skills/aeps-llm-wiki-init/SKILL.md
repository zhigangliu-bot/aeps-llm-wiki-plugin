---
name: aeps-llm-wiki-init
description: 初始化 aeps-llm-wiki 知识库目录结构(首次启用 / 幂等再入)
plugin-version: 0.5.5
---

# /aeps-llm-wiki-init

初始化用户的 wiki 项目工程,生成 6 顶层目录 + 18 知识叶子 + 15 raw 子目录 + 4 件顶层索引模板。已存在工程走幂等再入(只补缺失,不覆盖用户内容)。

## 触发

用户在新项目里跑 `/aeps-llm-wiki-init`,或在已有项目里再跑一次。

## 编排流程(SKILL.md 只编排,不写实现)

### 步骤 0:探测工程状态(只读)

```bash
node scripts/init/detect-state.js --project <用户工程根> --json
```

读 stdout JSON 解析:
- `state: "fresh"` → 走步骤 1-6 完整流程
- `state: "reentry"` → 走步骤 3-6 同步策略表
- `missing: [...]` → 提示用户缺哪些顶层目录(首次启用必走完整流程)

### 步骤 1:首次启用 dry-run 预览

```bash
node scripts/init/build-skeleton.js --project <dir> --dry-run --json
```

把 JSON 输出展示给用户(包含 `created[]` 列表),询问"是否继续?是 / 否 / 调整路径"。

### 步骤 2:首次启用实跑

用户拍板后:

```bash
node scripts/init/build-skeleton.js --project <dir> --json
```

JSON 含 `counts.gitkeepTotal`(应为 39=6+18+15)+ `created[]` 列表。

### 步骤 3:同步策略文件(scripts/templates/schema)

无论是首次还是幂等再入,都跑:

```bash
node scripts/init/sync-files.js --project <dir> --plugin-root <plugin-root> --json
```

JSON 含 `added / updated / skipped / warned` 4 数组 + 计数。

- 首次启用:`added` 应有 templates/page-*.md、tag-spec.md、concept-entities-spec.md、rawdir-spec.md 等
- 幂等再入:`updated` 应含 schema/* 全量覆盖 + templates/README.md 覆盖 + inbox/raw README 覆盖;`skipped` 应含用户已改的 templates/page-*.md

### 步骤 4:CLAUDE.md 受控区块

```bash
node scripts/init/patch-claude-md.js --project <dir> --json
```

JSON 含 `action: created|appended|updated|skipped|error`。

- `action: error` → 报错给用户,让用户手修 CLAUDE.md(orphan markers),不静默追加
- 其他 → 继续

### 步骤 5:聚合摘要报告

```bash
# 把步骤 2/3/4 的 stdout JSON 串起来
(node scripts/init/build-skeleton.js --project <dir> --json; \
 node scripts/init/sync-files.js --project <dir> --plugin-root <plugin-root> --json; \
 node scripts/init/patch-claude-md.js --project <dir> --json) \
 | node scripts/init/sync-report.js --project <dir>
```

人类可读输出,展示 added/updated/skipped/warned 计数 + 文件列表。

### 步骤 6:用户拍板完成

- 把摘要给用户看
- 用户拍板"完成" → init 流程结束
- 用户拍板"回滚" → 提示用户 `rm -rf` 整个工程根重建(对齐 implement-init.md §6.2:init 不写软删除)

## 拍板门总结

| 时机 | 拍板内容 | 默认 |
|---|---|---|
| 步骤 1 | dry-run diff 是否符合预期 | 等用户明确"是" |
| 步骤 5 | 摘要是否接受(skipped 列表确认用户改的文件保留) | 等用户明确"完成" |
| 步骤 4 orphan markers | 用户手修 CLAUDE.md | 不静默追加,报错退出 |

## 不做什么(SKILL.md 边界)

- 不写 frontmatter 字段(只引用 `frontmatter-spec.md`)
- 不调 LLM API(init 是纯机械)
- 不实现 CLAUDE.md 受控区块之外的配置文件(`.gitignore`、`.obsidian/` 由用户自己管)
- 不引入 npm 依赖(5 个 init 脚本零依赖)
- 不自动 commit(主 session 决定)
- 不调 git / SVN / Mercurial

## 拍板门失败的回滚点

- 步骤 1 之前:**无副作用**,可任意重跑
- 步骤 2-5 之间:不满意 → `rm -rf` 工程根(除 CLAUDE.md 受控区块)重建
- CLAUDE.md 受控区块误改:重新跑 init,自动替换

## 引用

- 设计文档:`doc/design/implement-init.md`
- 上游契约:`doc/design/prd.md` §4.1
- 工作流入口:`doc/schema/schema.md` §1

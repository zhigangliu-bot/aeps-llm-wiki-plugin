# scripts/init/ — init skill 脚本集

> 本目录是 `/aeps-llm-wiki-init` skill 的 5 个脚本实现,init 流程纯机械,SKILL.md 只编排。

## 脚本清单

| 脚本 | 职责 |
|---|---|
| `detect-state.js` | 探测 `{project}/` 是否含 6 顶层 + `.gitkeep`,输出 `state: fresh\|reentry` |
| `build-skeleton.js` | 首次启用:建 6 顶层 + 18 知识叶子 + 15 raw 子目录 + 4 件顶层索引 |
| `sync-files.js` | 幂等再入:按 sync 策略表覆盖 / 保留 / 补建 / 字典追加 |
| `patch-claude-md.js` | 幂等管理 `{project}/CLAUDE.md` 受控区块(start/end 标记) |
| `sync-report.js` | 综合输出 init 摘要(added/updated/skipped/warned) |

## 调用约定

- 所有脚本输出 JSON 到 stdout,日志/进度走 stderr
- 所有脚本支持 `--dry-run`(不写盘,只输出 diff)
- 所有脚本支持 `--project <dir>`(目标工程根目录)
- 跨平台:`node:path.join` 全程,无硬编码 `/` 或 `\`
- 零 npm 依赖:仅用 Node.js 内置 API

## 测试

```bash
node --test scripts/init/test/*.test.js
node scripts/init/test/e2e.js
```

## 引用

- 上游契约:`doc/design/prd.md` §4.1(同步策略表 + 流程表)
- 设计文档:`doc/design/implement-init.md`
- 工作流入口:`doc/schema/schema.md`

# scripts/update-check/ — SessionStart auto-update 检测

> 本目录是 SessionStart hook 的实现:每次新会话开始时检测远端是否有新 commit,若有则 `git pull --ff-only` 到本地,并在会话开头告知用户。

## 脚本清单

| 脚本 | 职责 |
|---|---|
| `check.js` | SessionStart hook 主入口:读 plugin.json → git rev-parse → git ls-remote → SHA 比对 → 必要时 `pull --ff-only` → stdout 走 hook JSON 协议 |

## 调用约定

- 无参数:hook 协议路径,stdout 输出 JSON(`hookSpecificOutput.additionalContext`)或空(无更新时)。
- `--check-only`:CLI 模式,只跑检测不 pull,纯文本 stdout,退出码 0/1/2。
- `--pull`:CLI 模式,跑检测 + pull,纯文本 stdout,退出码 0/1/2。
- 任何 throw / 网络异常 / git 缺失 / plugin.json 缺字段 → 静默,exit 0(绝不阻塞 session 初始化)。
- 零 npm 依赖:仅用 Node.js 内置 API。

## 测试

```bash
node --test scripts/update-check/test/
```

## 引用

- 上游契约:`doc/design/prd.md` §R1-R4
- 设计文档:`doc/design/design.md` §3
- 实施清单:`doc/design/implement.md`

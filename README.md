# aeps-llm-wiki-plugin

> **一个 Claude Code plugin,把 Karpathy LLM Wiki + Google OKF v0.2 + Obsidian 整合成一个本地知识库工具链。**

![plugin version](https://img.shields.io/badge/version-0.6.6-blue)
![license](https://img.shields.io/badge/license-Apache_2.0-green)
![node](https://img.shields.io/badge/node-%E2%89%A520.0.0-brightgreen)

---

## Change History

| 版本 | 日期 | 变更 |
|---|---|---|
| 0.5.6 | 2026-09-08 | 批次 4 (P3 文档与版本一致):删除过期升级提示(0.5.4 → 0.5.5 模板);安装章节加"plugin 内置 preflight,缺包即停 + 不自动 install"统一描述(P3-2);`scripts/check-version-consistency.js` 新增,CI 兜底扫描版本号字串(P3-1) |

---

## 项目定位

`aeps-llm-wiki-plugin` 是面向 **汽车电子软件工程师 / 架构师** 的 Claude Code plugin,把三个范式整合成一个 OKF 兼容的本地 wiki 工具链:

- **Andrej Karpathy 的 LLM Wiki 模式** —— LLM 读源,人做策展
- **Google Cloud 的 Open Knowledge Format (OKF v0.2)** —— `markdown + YAML frontmatter`,`type` 唯一硬必填
- **Obsidian 作为前端** —— 生成 `knowledge/` 直接被 Obsidian vault 打开使用

**目标用户**:用 Claude Code + Obsidian 做长期知识沉淀的人。

---

## 5 个 skill 一句话介绍

| Skill | 一句话 |
|---|---|
| `/aeps-llm-wiki-init` | 5 分钟内初始化一个 OKF 兼容的知识库目录结构(首次启用 / 幂等再入) |
| `/aeps-llm-wiki-ingest` | 把 `inbox/` 资料自动转成 OKF 源页 + entity / concept 子页,LLM 提议 raw 子目录分类 + 用户拍板 |
| `/aeps-llm-wiki-query` | 从 `knowledge/` 找答案 + 引用,可落档为 `analysis` 页(G11 gating 控制 spam) |
| `/aeps-llm-wiki-synthesize` | 写一份常驻综合页(`type: synthesis`),引用 wiki 里所有与 topic 相关的页 |
| `/aeps-llm-wiki-lint` | 扫 `knowledge/**/*.md` 报告孤儿 / 矛盾 / 过期 / 漏链 / frontmatter 不合规 |

---

## 快速上手(5 分钟)

### 1. 安装 plugin

```bash
# 在 Claude Code 中加载 plugin
claude --plugin-dir aeps-llm-wiki-plugin
```

> **依赖说明**:plugin **不自动安装** 任何 npm 包。首次跑 `init` / `ingest` 时,若发现缺包,plugin 内置 preflight 立即 ERROR 并打印精确的 `npm install <pkg>` 命令,用户拍板手动装。详见 `skills/<skill>/SKILL.md` 步骤 0.5 + P3-2 修复。

### 2. 初始化新项目

```bash
# 在你的研究 / 学习 / 笔记项目根目录
claude

> /aeps-llm-wiki-init
```

plugin 会自动建好:
- 6 顶层目录(`inbox/`、`raw/`、`scripts/`、`templates/`、`schema/`、`knowledge/`)
- 18 个知识叶子目录(`sources/` + 7 entity 子类 + 7 concept 子类 + `analyses/` + `comparisons/` + `syntheses/`)
- 15 个 raw 子目录(EE架构 / 芯片 / 通信与网络 / ...)
- 4 件顶层索引模板(`index.md` / `overview.md` / `glossary.md` / `log.md`)
- `{project}/CLAUDE.md` 受控区块(告诉 Claude Code 走 wiki 工作流)

### 3. 把资料丢进 inbox

```bash
cp my-research.pdf your-project/inbox/
```

### 4. 触发 ingest

```bash
> /aeps-llm-wiki-ingest
```

plugin 走 5 路径分流(原生优先 → anydoc → paddleocr),自动建 OKF 源页 + entity / concept 子页。

### 5. 在 Obsidian 打开 `knowledge/`

把 `your-project/knowledge/` 作为 vault 根目录在 Obsidian 中打开,即可:
- tag 面板 / 反向链接图谱自动生成
- `[[wikilink]]` 裸文件名直接跳转
- 双链、tag、搜索全文

---

## 架构核心:5 分钟看完

```
┌──────────────────────────────────────────────────────────┐
│ Claude Code (Host)                                        │
│  ┌──────────────────────────────────────────────────┐    │
│  │ /aeps-llm-wiki-{init,ingest,query,synthesize,lint}│   │
│  │  └─→ 读 schema/schema.md (Agent 工作流入口)       │    │
│  │  └─→ 调 scripts/*.js (单次运行,即跑即退)        │    │
│  │  └─→ LLM 自驱步骤 (SKILL.md 描述)               │    │
│  └──────────────────────────────────────────────────┘    │
└────────────┬─────────────────────────────────┬────────────┘
             │                                 │
             ▼                                 ▼
   ┌──────────────────┐              ┌────────────────────────┐
   │ scripts/*.js     │              │ SKILL.md               │
   │ (Node.js 单栈)   │              │ (Claude Code 内 SKILL)  │
   └────────┬─────────┘              └────────────────────────┘
            │
            ▼
   ┌──────────────────────────────────────────────────────────┐
   │ 用户工程                                                  │
   │  inbox/  →  raw/{subdir}/  →  knowledge/{sources,...}/    │
   │  templates/  schema/  scripts/  (init 时从 plugin 拷贝)   │
   └──────────────────────────────────────────────────────────┘
            │
            ▼
   ┌──────────────────────────────────────────────────────────┐
   │ Obsidian (本地 vault)                                     │
   │  直接打开 knowledge/ 目录,无需任何映射                    │
   └──────────────────────────────────────────────────────────┘
```

**关键设计原则**(详见 `doc/design/prd.md` / `doc/design/design.md`):

- **零常驻运行时** —— 纯规范 + skill + 单次运行的 scripts + 事件回调 hooks(G6)
- **Node.js 单栈** —— scripts 单栈 Node.js LTS(`>=20`),OCR 路径仅在必要时降级 Python
- **原生多模态优先** —— 先让 Claude Code 原生读,失败才走 anydoc / paddleocr(G10)
- **OKF 严格兼容** —— `type` 唯一硬必填,plugin 收敛到 18 项硬枚举与 knowledge/ 目录 1:1 绑死
- **`[[wikilink]]` 裸文件名主推** —— 依赖 Obsidian 唯一名 + aliases 别名解析
- **不发明 `links:` frontmatter 字段** —— 对齐 OKF §5「Lineage is expressed through links」

---

## 文档导航

| 文档 | 用途 |
|---|---|
| [`doc/design/prd.md`](aeps-llm-wiki-plugin/doc/design/prd.md) | 产品需求(已冻结 v0.4.1) |
| [`doc/design/design.md`](aeps-llm-wiki-plugin/doc/design/design.md) | 技术设计(已冻结 v0.1.1) |
| [`doc/design/implement-init.md`](aeps-llm-wiki-plugin/doc/design/implement-init.md) | init skill 实现设计 |
| [`doc/schema/schema.md`](aeps-llm-wiki-plugin/doc/schema/schema.md) | Agent 工作流入口 |
| [`doc/schema/frontmatter-spec.md`](aeps-llm-wiki-plugin/doc/schema/frontmatter-spec.md) | frontmatter 字段规范(人读权威) |
| [`doc/schema/frontmatter.schema.json`](aeps-llm-wiki-plugin/doc/schema/frontmatter.schema.json) | frontmatter 机器读校验 |
| [`doc/template/README.md`](aeps-llm-wiki-plugin/doc/template/README.md) | 模板字典总览 |
| [`doc/template/tag-spec.md`](aeps-llm-wiki-plugin/doc/template/tag-spec.md) | 6 轴 tag 字典 |
| [`doc/template/rawdir-spec.md`](aeps-llm-wiki-plugin/doc/template/rawdir-spec.md) | 15 类 raw 子目录字典 |
| [`doc/template/concept-entities-spec.md`](aeps-llm-wiki-plugin/doc/template/concept-entities-spec.md) | 14 子类判定示例 |

---

## 仓库结构

```
aeps-llm-wiki-plugin/
├── doc/                       # 设计规范(已冻结,init 时按需拷贝到用户工程)
│   ├── design/                # prd.md / design.md / implement-*.md
│   ├── schema/                # frontmatter 规范 + schema.json
│   └── template/              # 页面模板 + 字典(tag/rawdir/concept-entities)
├── skills/                    # 5 个 SKILL.md(Claude Code plugin skill 入口)
├── scripts/                   # init / ingest / query / lint / synthesize 脚本(单次运行)
├── hooks/                     # 事件回调 hooks
├── LICENSE                    # Apache 2.0
└── README.md                  # 本文件
```

---

## Auto update(每个 session 自动)

本 plugin 在 `SessionStart` event 注册了一个 hook(`hooks/hooks.json`,matcher = `startup`)。每次新会话开始时,hook 会**静默**执行:

1. `git ls-remote origin HEAD` 拿远端 commit SHA,跟本地 `git rev-parse HEAD` 比对
2. 一致 → 静默,session 正常初始化(**无打扰**)
3. 不一致 → `git pull --ff-only origin main` 自动拉取;成功后通过 `hookSpecificOutput.additionalContext` 在 session 开头告知你已升级:
   ```
   📦 aeps-llm-wiki 已升级(旧版本 → 当前版本)。当前 session 仍使用旧代码,运行 `/reload-plugins` 后生效。
   ```
4. 拉取失败 → 在 session 开头告知你手动处理:
   ```
   ⚠️ aeps-llm-wiki 有新版本但自动升级失败(原因:truncated)。请手动处理:
   在 plugin 根目录跑 `git pull --ff-only origin main`,
   或重新 `/plugin install aeps-llm-wiki@aeps-public-marketplace`。
   ```
5. 远端历史被 force-push 重写过(导致 cache 跟远端分叉) → 自动 `git fetch` + `git reset --hard origin/main`,告知文案里说「远端历史被改写」+ `/reload-plugins`

**关键不变量**:

- **零打扰**:hook 成功(sha 一致)→ 完全静默,session 开头**没有**任何额外输出
- **不阻断**:任何 throw / git 缺失 / plugin.json 缺字段 / 网络异常 → stdout 空,exit 0,session 初始化不受影响
- **无 npm 依赖**:纯 Node.js 内置 API(`node:fs/promises` / `node:child_process` / `node:path`),~250 行可读可审
- **每个 session 都 fetch**:不节流;版本未变不告知

**注意**:升级在本 session **不生效**(hook 跑完后,本 session 已加载的 plugin 代码是旧的);要立即用新代码,跑 `/reload-plugins`。下一个 session 会自然用新代码。

详见 `doc/design/prd.md` §4.7 + `scripts/update-check/README.md`。

---

## 开发

### 环境要求

- Node.js `>=20.0.0`
- Claude Code `>=1.0.0`

### 本地测试

```bash
# init skill 单测
cd aeps-llm-wiki-plugin
node --test scripts/init/test/*.test.js

# init skill 端到端
node scripts/init/test/e2e.js
```

### 贡献

参见 `doc/design/prd.md` §2 目标 / 非目标 + `doc/design/design.md` §7 关键决策。修改冻结文档前先在文档开头写 `change history` 并在 commit 前询问文档版本号。

---

## 引用

- **Karpathy LLM Wiki**:`balukosuri/llm-wiki-karpathy`(本仓库 `reference/` 镜像)
- **OKF v0.2**:Google Cloud Open Knowledge Format(本仓库 `doc/input/google-OKF/` 镜像)
- **Obsidian**:https://obsidian.md/

---

## 踩过的坑(Auto update 实现期间的真实教训)

> 这一节是给后续维护者看的真实记录,不是教程。Auto update hook 看似简单(`ls-remote` + `rev-parse` + `pull`),实际落地遇到了三个非预期问题。

### 坑 1:远端 force-push 会破坏 cache 的 `git pull --ff-only`

**场景**:我们在 plugin 仓做了一次 `git push --force-with-lease`(为了清理老 init/test 目录的提交历史)。用户的 cache 仓(`~/.claude/plugins/cache/.../0.5.6/`)本来 `git pull --ff-only origin main` 应该一路顺畅,**但因为远端历史被改写**,本地 HEAD 找不到 ancestor,fast-forward 失败 → 永远停在老 commit,hook 报 `pull-failed`,session 开头一直骚扰用户「请手动 pull」。

**修复**:hook 检测到 `pull --ff-only` 失败时,**不立刻报错**,而是 fallback 跑 `git fetch origin main` + `git reset --hard origin/main`。前提是 working tree 干净(若有未提交改动,reset 会失败,这时才报 `diverged-reset-failed` 让用户手动处理)。

**给维护者的提示**:任何时候**对 plugin 远端仓做 force-push 前**,先在团队/社群公告;否则所有已安装用户的 cache 都会掉队一次,且只能靠 hook 的 reset fallback 自动恢复。

### 坑 2:plugin cache 默认 remote URL 是 **SSH**,不是 HTTPS

**场景**:Claude Code install plugin 时把 remote URL 记录成 `git@github.com:zhigangliu-bot/aeps-llm-wiki-plugin.git`(SSH)。多数 Windows 用户(以及部分 CI 环境)**没配 GitHub SSH key**,hook 跑 `git ls-remote` 时报:

```
git@github.com: Permission denied (publickey).
fatal: Could not read from remote repository.
```

hook 退化成 `detect-failed` → 静默退出,**用户根本不知道有更新可拉**(等于 hook 失效了)。

**最终解决方案**(三个候选,我们选了 B):

| 方案 | 操作 | 代价 |
|---|---|---|
| A. 卸载重装 | `/plugin uninstall aeps-llm-wiki@aeps-public-marketplace` 后再 `/plugin install ...` | 让用户多走两步;cache 丢失 |
| B. 改 cache 仓 remote 为 HTTPS(保留 cache) | `git -C "<cache>" remote set-url origin https://github.com/zhigangliu-bot/aeps-llm-wiki-plugin.git` + `git fetch origin` + `git reset --hard origin/main` | 用户手动一次;cache 保留,版本对齐 |
| C. 给 GitHub 配 SSH key | 一劳永逸 | 用户门槛高(SSH key 生成 + GitHub 账号加 key) |

我们最终选 **B**:cache 里其他 plugin 还在,只改本仓的 remote URL,然后 `reset --hard origin/main` 同步到远端最新 commit。**这是开发期一次性操作,生产用户不会主动触发**(他们直接 install plugin,remote 是 SSH;hook 会退化成 detect-failed 静默,**这是已知 trade-off**,后续考虑在 hook 里 fallback 到 HTTPS remote)。

### 坑 3:hook 代码**本身也在 cache 里**,更新 hook 要重装 plugin

**场景**:`scripts/update-check/check.js` 跟 plugin 其它文件一起装到 cache 仓里。**修改 hook 行为 → 必须让用户重装 plugin**(才能拿到新版 check.js)。但 hook 本身做的就是「自动帮用户拉最新 plugin」,**这构成了一个鸡生蛋的问题**:

- hook 升级时 cache 还停在旧 hook 版本
- 旧 hook 跑 `git pull --ff-only` 会拉到新 hook 版本
- 但 hook 是 SessionStart 时跑一次,**已经在跑的 session 仍用旧 check.js 加载的代码**(语义不变,因为 check.js 是 stateless 函数,只是缺新状态机分支)

**结论**:本地开发调试 hook 行为时,**别用 install 出来的 cache 仓**,直接 `cd` 到开发仓跑 `node scripts/update-check/check.js --check-only` / `--pull`(CLI 模式);发布到远端后,用户**下个 session** 自然用上新 hook。

### 坑 4:`CLAUDE_PLUGIN_ROOT` env **根本没注入**,hook 实际静默失效

**这是最坑的坑**。check.js 设计假设 Claude Code 跑 SessionStart hook 时会 export `CLAUDE_PLUGIN_ROOT` env 变量指向 plugin cache 根,代码第一件事就是 `process.env.CLAUDE_PLUGIN_ROOT`。

**实测**:2026-09-08 看 cache 仓 `.in_use/{pid}` 文件证明 hook **确实跑了**(pid=10072,Sep 8 09:28),但 `process.env.CLAUDE_PLUGIN_ROOT` **是 undefined**。

**后果**:
- hook 进入 `if (!pluginRoot || pluginRoot.length === 0) return;` 静默分支
- stdout 空,exit 0
- session 开头**完全没有任何告知**、**没有任何 pull 动作**
- cache 永远停在旧 commit,直到用户手动进 cache 仓跑 `node scripts/update-check/check.js --pull`

**这是个真 bug,当前 v0.5.1 文档里已记录为已知缺陷**。**修复方向**(v0.5.2,未实施):把 plugin 根定位从「单 env」改成「cwd 兜底 + 向上递归找 `.claude-plugin/plugin.json`」多源 fallback。

**临时手动同步**(如果你等不及修复):
```bash
cd "C:/Users/ThinkPad/.claude/plugins/cache/aeps-public-marketplace/aeps-llm-wiki-plugin/0.5.6"
CLAUDE_PLUGIN_ROOT="$(pwd)" node scripts/update-check/check.js --pull
```

### 总结:Auto update 不是「装完就一劳永逸」的

- 远端 force-push → 触发 hook 的 reset 分支(已自动处理)
- 用户的 cache remote 是 SSH 且没配 key → hook 静默失效(用户需手动改 HTTPS 一次,见坑 2)
- hook 代码自身升级 → 用户下个 session 自动生效,本 session 仍用旧(预期行为)
- **`CLAUDE_PLUGIN_ROOT` 不注入 → hook 完全失效**(坑 4,**v0.5.1 已知缺陷**)

任何 hook 边界外的特殊情况(本地有未提交改动 / cache 仓被手工破坏 / 多个 plugin 互相冲突),走 fallback 文案告诉用户手动。

---

## License

Apache License 2.0. 详见 [LICENSE](aeps-llm-wiki-plugin/LICENSE)。

Copyright 2026 zhigang.liu

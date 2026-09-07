# aeps-llm-wiki-plugin

> **一个 Claude Code plugin,把 Karpathy LLM Wiki + Google OKF v0.2 + Obsidian 整合成一个本地知识库工具链。**

![plugin version](https://img.shields.io/badge/version-0.5.5-blue)
![license](https://img.shields.io/badge/license-Apache_2.0-green)
![node](https://img.shields.io/badge/node-%E2%89%A520.0.0-brightgreen)

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

## License

Apache License 2.0. 详见 [LICENSE](aeps-llm-wiki-plugin/LICENSE)。

Copyright 2026 zhigang.liu

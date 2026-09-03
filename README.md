# aeps-llm-wiki-plugin 插件

> 把 Karpathy 的 LLM Wiki 模式、Google Cloud 的 OKF v0.2 开放规范、Obsidian 直读前端三种范式合成到一处的 Claude Code 插件。

**一句话定位**:在自己的研究项目里跑一次初始化命令,即可得到 OKF 兼容、Karpathy 启发、Obsidian 可直读的知识库;LLM 写、Obsidian 读、插件管一致性。

---

## 1. 它是什么

面向 Claude Code 的插件,目标用户是汽车电子软件工程师、架构师,以及任何用 Claude Code 加 Obsidian 做内部研究、知识沉淀、学习笔记的人。`knowledge/` 目录是给 Obsidian 消费的 —— LLM 维护、人用 Obsidian 读、插件保证一致性。

设计基线三条:

- **LLM Wiki 模式**(来自 Karpathy):LLM 读源一次,产出持久、互相链接的 markdown 知识网
- **OKF v0.2**:厂商中立、零运行时、`markdown + YAML frontmatter`,唯一必填字段为 `type`
- **Obsidian 前端契约**:`[[page]]` 双链、`tags` YAML 列表、`knowledge/{entities,concepts,...}/` 即 vault 子文件夹

---

## 2. 五个技能简介

| 技能 | 触发 | 入口 | 关键职责 |
|---|---|---|---|
| **初始化** | `/aeps-llm-wiki-init` | 当前工作目录 | 五分钟建好知识库骨架;**幂等再入**不静默覆盖用户本地内容 |
| **收录** | `/aeps-llm-wiki-ingest` | 入口目录 | 递归扫入口目录;LLM 提议原始资料子目录,用户拍板;入口迁移到原始资料库 |
| **查询** | `/aeps-llm-wiki-query <问题>` | 知识库目录 | 带知识网引用回答;命中闸门条件时询问是否落档为分析页 |
| **校验** | `/aeps-llm-wiki-lint [--fix --apply]` | 知识库目录 | 扫前置元数据、三节骨架、链接镜像、命名飘、漏链、陈旧页;`--fix` 只自动应用确定性结构修复,语义问题出提案等用户确认 |
| **综合** | `/aeps-llm-wiki-synthesize <主题>` | 知识库目录 | 写常驻综合页(类型为综合,不带时间戳),引用知识网全相关页 |

详细契约见 `docs/prd.md` / `docs/design.md` / `docs/implement.md`。

---

## 3. 安装方式

### 3.1 安装插件

```text
/plugin install aeps-llm-wiki-plugin
```

或本地路径预览(从仓库根):

```text
/plugin install <project>/aeps-llm-wiki-plugin
```

### 3.2 安装 Python 依赖(必须)

插件的脚本目录走 Python 3.10+ 单栈,收录技能需要 anydoc 与 paddleocr 做非文本类文件转换:

```bash
pip install -r <project>/scripts/requirements.txt
```

依赖清单:`anydoc` / `paddleocr` / `jsonschema` / `pyyaml` / `pytest`。

### 3.3 安装 qmd(可选)

查询技能在知识网规模较大时使用本地搜索引擎 qmd 加速。**默认可选**,仅当 `knowledge/` 页数 $N \ge 1000$ 时**临时升级为强依赖**(未装将报错退出)。安装方式:

```bash
npm install -g @tobilu/qmd
qmd status
```

---

## 4. 快速开始

```bash
# 1. 在你的研究项目根目录跑初始化
cd <your-research-project>
/aeps-llm-wiki-init

# 2. 把资料丢进入口目录
cp ~/Downloads/iso26262-spec.pdf <your-research-project>/inbox/

# 3. 让 LLM 帮你归档 + 抽取概念
/aeps-llm-wiki-ingest

# 4. 查询
/aeps-llm-wiki-query "OKF 必填字段是哪个"

# 5. 校验知识网一致性
/aeps-llm-wiki-lint
```

详细工作流见 `docs/prd.md`。

---

## 5. 设计文档(对外快照)

| 文档 | 路径 | 作用 |
|---|---|---|
| **PRD** | [docs/prd.md](docs/prd.md) | 产品需求 / 用户故事 / 验收标准 / 非目标 |
| **设计** | [docs/design.md](docs/design.md) | 模块边界 / 数据契约 / 关键流程 / Obsidian 前端契约 |
| **实施** | [docs/implement.md](docs/implement.md) | 分阶段执行清单 + 测试用例 + 提交节奏 |

> 内部权威维护在 `src/prd.md` / `src/design.md` / `src/implement.md`。`docs/` 是对外快照,以 `src/` 为准。

---

## 6. 关键约束

- **无运行时**:插件不带 Python 命令行守护进程 / 模型上下文协议服务 / 检索增强 / 向量嵌入服务。脚本与钩子都遵守"代理调一次就跑完退"。
- **入口目录唯一性**:收录技能仅扫入口目录(递归);原始资料库是已归档的不可变层,调整走 `git mv`,不开原始资料库直接入口。
- **OKF v0.2 兼容**:前置元数据 `type:` 必填;`links:` 镜像字段由插件维护,与正文双链引用同步。
- **Obsidian 直读**:`knowledge/` 是 Obsidian 保险库,无需任何格式转换。
- **无绝对路径**:代码 / 模板 / 技能文件中所有路径占位都用 `<project>/<dir>/`。

---

## 7. 致谢与参考

本插件的设计参考了以下三个互补范式,在此向原作者致谢:

- **Karpathy 的 LLM Wiki 模式**:核心理念是"LLM 读源一次,产出持久、互相链接的 markdown 知识网,人做策展"。这种模式启发了本插件的整体数据流设计 —— 由 LLM 主导知识库的内容生产与组织,人类负责资料筛选与方向决策。
- **Google Cloud 的 OKF v0.2 开放规范**:提供了厂商中立、零运行时的知识表示格式。本插件生成的所有知识库页面在 frontmatter 层严格遵循该规范,确保第三方工具可直接消费。
- **Obsidian 作为本地知识库前端**:成熟的本地 markdown 知识库用户界面,提供了双链、标签面板、反向链接图谱等强大能力。本插件的知识库目录必须能被 Obsidian 直接打开,无需任何格式转换,这是产品级的硬约束。

---

## 8. 许可证

Apache License 2.0。详见 [LICENSE](LICENSE)。

```text
Copyright 2026 zhigang.liu
```

---

## 9. 反馈与协作

本插件当前处于早期阶段,功能与边界仍在持续迭代。如果你试用后有任何问题、建议或反馈,欢迎通过仓库的议题跟踪系统提交。在提交反馈时,建议同时附上你的知识库目录结构、变更日志最近几条记录,以及你执行的命令与期望结果,这能大幅缩短定位问题的时间。

## 10. 设计哲学小结

本插件坚持以下几条设计原则,作为后续演进时的取舍依据:

- **LLM 主导内容生产,人主导方向拍板**:所有知识页的内容由 LLM 在提示词的引导下生成,但关键决策点(如新子目录是否创建、命名飘合并、陈旧页处理)始终由人拍板,LLM 仅出提案。
- **Obsidian 直读优于格式转译**:`knowledge/` 是给 Obsidian 消费的,Llm 写、人用 Obsidian 读、插件管一致性。任何需要格式转译才能被前端消费的方案,都视为失败设计。
- **入口唯一 + 原始资料不可变**:`inbox/` 是唯一的资料入口;`raw/` 一旦归档不再变动,变更走 `git mv` 或手工复制回 `inbox/` 走标准收录流程。
- **OKF 兼容优于 plugin 私货**:plugin 扩展的 frontmatter 字段必须能被 OKF v0.2 工具作为"未知可选字段"容忍,任何阻塞 OKF 兼容性的设计都视为失败。
- **无运行时优于功能完整**:插件不带 Python 命令行守护进程、不带模型上下文协议服务、不带检索增强与向量嵌入服务,所有脚本与钩子都遵守"代理调一次就跑完退"。这一边界宁可保守。
- **本地优先优于云同步**:所有数据都保留在用户项目本地,不向任何外部服务上传;plugin 升级走 git 发布,不走热更新通道。

## 11. 版本与演进

本插件当前版本号 `0.5.5`,处于早期迭代阶段,详细变更历史见 `src/implement.md` 的 `## change history` 章节。每次版本号变更都会同步在三个文档(需求 / 设计 / 实施)中留痕,便于跨版本对照设计决策。

后续里程碑(M5 端到端自测、M6 上线发布)见需求文档第九节。社区用户在使用过程中积累的最佳实践、踩坑经验,也会逐步沉淀进设计文档,作为后续版本的输入。

## 12. 常见疑问快速参考

在试用过程中,以下几个问题经常被问到,这里统一作答:

- **问:能否修改原始资料库里的归档?** 答:不建议。原始资料库是已归档的不可变层,调整请走 `git mv`;若必须重新生成副本,请把原文件复制回入口目录走标准收录流程。
- **问:校验的 `--fix` 与 `--apply` 区别是什么?** 答:`--fix` 仅输出修改提案,不写盘;必须再加 `--apply` 才会真正写文件。这是为防止语义级误改而设置的双开关保护。
- **问:能否在分析页里只写两节骨架?** 答:不能。分析页有专属的三节骨架硬约束 —— 方案推演与架构分析、关联溯源、总结:最有收获的一句话,缺一即校验失败。
- **问:本地引擎 qmd 必须装吗?** 答:不必须,只是推荐。知识库页数少于五百时不会用到;五百至一千之间为推荐;超过一千页为强依赖,未装将无法查询。
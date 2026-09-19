---
name: aeps-llm-wiki-research
description: 知识库覆盖不足时 LLM 自动联网调研;一源一文件+调研纪要落 inbox/research/;不直写 knowledge/;三触发(用户显式 / query 步骤 7 衔接 / 对话自主)
plugin-version: 0.6.9
allowed-tools: mcp__jina-mcp-server__search_web,mcp__jina-mcp-server__search_arxiv,mcp__jina-mcp-server__search_ssrn,mcp__jina-mcp-server__search_jina_blog,mcp__jina-mcp-server__read_url,mcp__bocha-mcp__bocha_web_search,mcp__bocha-mcp__bocha_ai_search,mcp__fetch__fetch,WebSearch(*),WebFetch(*),mcp__playwright__browser_navigate,mcp__playwright__browser_snapshot,mcp__playwright__browser_take_screenshot,mcp__playwright__browser_evaluate,mcp__plugin_playwright_playwright__browser_navigate,mcp__plugin_playwright_playwright__browser_snapshot,mcp__plugin_playwright_playwright__browser_take_screenshot,mcp__plugin_playwright_playwright__browser_evaluate
---

## 脚本路径约定

- 本 skill **不调任何 bash 脚本**;纯 LLM 编排 + MCP 联网工具 + 原生 `WebSearch` / `WebFetch` 兜底。
- `inbox/research/` 落盘由 LLM 用 `Write` 工具直接创建文件(无 ingest 流水线前置依赖);后续若用户决定入库,跑 `/aeps-llm-wiki-ingest` 走现有流水线。
- `doc/templates/research-sites.md` 走 `scripts/init/sync-files.js` else 分支自动 backfill / preserve existing,无需新脚本。

# /aeps-llm-wiki-research

知识库对某话题覆盖不足时,LLM 全自动联网调研,把取证材料落回 `inbox/research/`,由现有 ingest 流水线入库。research 是知识获取的进水口,**不碰 knowledge/ 写入**。

> **本 skill 默认建议在 subagent(Task 工具)里跑**,主上下文只保留拍板门①与最终汇报的纪要摘要。三路触发中,**query 衔接路径②**与**对话自主路径③**必须用 subagent;**用户显式路径①**由用户决定(默认建议走 subagent)。

## 触发

三路汇入同一步骤序列:

1. **用户显式**:`/aeps-llm-wiki-research {topic}` 直接拉起。
2. **query 步骤 7 衔接**:query 报「未覆盖」后,建议拉起 `/aeps-llm-wiki-research {question}` 补窟窿,**走 Task 工具启 subagent 隔离跑**(避免主上下文被多源精读内容灌爆)。
3. **对话自主**:LLM 判断对话主题在 knowledge/ 是盲区,主动建议拉起。

## 设计原则(必读)

- **不直写 knowledge/** — research 产物落 `inbox/research/`,由 ingest 流水线入库;LLM 不代跑 ingest。
- **先报告后动手** — 拍板门①双拍板强制:质量门槛三元组 + 软预算上限;不静默取默认。
- **每条事实带 URL + 抓取日期,不编造** — 源文件正文头必须含来源引用行。
- **预算每次向用户确认** — 软上限触顶或质量门槛三元组达标,任一先达即停(质量门槛优先)。
- **未解决问题显式标「未找到」** — 落 `00-research-note.md`「未决问题」节,落盘前不二次打断。
- **inbox 文件不写 frontmatter / 不写 wikilink** — 无脚本解析 inbox frontmatter;wikilink 会误导 Obsidian 解析到 inbox。
- **subagent 隔离** — 步骤 0/1/拍板门①/4 在主上下文跑;步骤 2/3 在 subagent 跑;主上下文不直接执行步骤 2/3。

## 编排流程(对齐 PRD §步骤 0-4)

> **切分点速览**:步骤 0/1/拍板门①/4 = 主上下文;步骤 2/3 = subagent(Task 工具)。每个步骤顶部用 `[主上下文]` / `[subagent]` 显式标注。

### 步骤 0:前置检查(阻塞)— [主上下文]

- 检查 vault 存在 `knowledge/`;缺失则报错提示先跑 `/aeps-llm-wiki-init`,对齐 query G-Q1。
- 检查会话工具列表,**报告联网工具可用性**(给拍板门①用):
  - 实际命中档位:扫 system-reminder 列出的 MCP 服务器 + 原生 WebSearch / WebFetch。
  - 必报项:`bocha-mcp` 两档 / `jina-mcp-server` 搜索 4 档 + `read_url` / `fetch` / 原生 `WebSearch` / 原生 `WebFetch` / `playwright` 子集(及 `plugin_playwright_playwright` 对应工具)。
  - **未挂载档位静默跳过**(不报错),直接降级到下一档。
  - 全链不可用时(无任何联网工具)→ 表格加一行 `⚠ 全链不可用`,**默认继续**,让用户在拍板门①选「改换环境重跑 / 降预算 / 继续」。
- **检查当前会话是否有 mcp__jina-mcp-server__primer 可用**(联网前必跑,拿当前时间 + 用户位置,日期用于源文件「抓取于」字段)。

### 步骤 1:缺口评估(阻塞,LLM 判定)— [主上下文]

- Grep `knowledge/index.md` + Glob `knowledge/**/{*.md}`,LLM 语义判定三值:
  - **`covered`**:≥1 页核心专对题 → 结束,告知无需调研。
  - **`thin`**:有零散命中但无对题专属页 → 进入拍板门①。
  - **`empty`**:无命中 → 进入拍板门①。
- **判定必须列出命中文件相对路径作为证据**(R4 硬约束)。
- 不写判定脚本(`gap-check.js` 是升级路径,实测飘时另立任务)。

### 拍板门 ①:联网前确认(阻塞,等用户)— [主上下文]

LLM 启动时给一组**提案基线**(参考值,用户可调):
- 总研究问题数:3-5 个
- 每问题搜索次数:≤2 次
- 整场精读页数:≤8 页
- 总搜索次数:由问题数 × 每问题搜索次数推得

LLM 一并列给用户,等明确「确认 / 改预算 / 改问题 / 取消」后才进步骤 2。

报告格式(双段):

**缺口报告**(LLM 输出):
- 话题:<topic>
- 判定:thin / empty
- 证据文件:`knowledge/<...>.md`(直接对题 / 边缘相关)
- 说明:一句解释

**拍板门表格**:

| 项 | 值 |
|---|---|
| 判定 | thin / empty |
| 拟研究问题 | 1. ... / 2. ... / 3. ... |
| 质量门槛(默认三元组) | ① 每问题 ≥2 独立源交叉验证 / ② 纪要「未决问题」节必填 / ③ 全部研究问题有结论或未决标记 — 用户可改单点 |
| 预算软上限 | SKILL.md 不写死具体数字;只列维度(总研究问题数 / 每问题搜索次数 / 整场精读页数 / 总搜索次数);LLM 启动拍板门①时给一组提案基线(参考值:3-5 个研究问题 / 每问题 ≤2 次搜索 / 整场精读 ≤8 页);预算触顶即强行停止联网,不再二次打断;未决问题落 `00-research-note.md` — 用户可接受默认 / 改数字 / 全砍 / 全扩 |
| 命中主题站点(来自 research-sites.md) | <主题 → 站点列表> |
| 工具可用性 | <bocha-mcp 两档 ✓ / jina search_web+read_url ✓ / fetch ✓ / 原生 WebSearch+WebFetch ✓>;全链不可用时此行加 ⚠ 告警 |

> 用户主动要求「没有原生 WebSearch 不准动手」时按特例处理:不联网,直接告知用户「当前会话未挂任何联网工具,请改换环境后重跑」并结束。

### 步骤 2:联网取证(非阻塞)— [subagent 内执行,主上下文不直接执行]

> **派发 Task 切分点**:用户确认拍板门①后,主上下文通过 Task 工具启 subagent,把(研究问题 / 授权预算 / 质量门槛 / 站点表 / 工具可用性表)传给 subagent;subagent 独立执行本步骤 + 步骤 3。

#### 2.1 读站点表

- 读 `{vault}/doc/templates/research-sites.md`(走 init sync-files.js else 分支);**文件不存在 → 视为空表**,直接全网检索。
- 站点表内容**软优先**:每研究问题先对命中主题的站点定向搜。
  - **优先方式**(按当前工具能力自动选):
    - 原生 WebSearch 支持 `allowed_domains` 参数 → 用之
    - 文本 query 类工具支持 `site:` 语法 → query 文本里写 `site:iso.org foo bar`
  - **兼容降级**(工具不支持限定域名参数 / 不支持 `site:` 语法):
    - 把站点关键词直接拼入搜索 query 文本,例如 `iso.org AUTOSAR adaptive platform`
    - LLM 在「工具可用性表」里标注「参数支持:仅 query 拼接」,用户知情
  - **放开全网**:命中不足(每问题 <2 独立来源)→ 不再限定站点,全网检索

#### 2.2 搜索工具优先链(R9)

按上到下优先级;**未挂载静默跳过**:

1. `mcp__jina-mcp-server__search_web` / `search_arxiv` / `search_ssrn` / `search_jina_blog`(质量优先)
2. `mcp__bocha-mcp__bocha_web_search` / `bocha_ai_search`
3. `mcp__playwright__browser_navigate` + `browser_snapshot` + `browser_evaluate`(及 `mcp__plugin_playwright_playwright__*` 对应工具)— **条件触发**:仅 LLM 判定此站搜索结果必须 JS 渲染 / 交互后才出时才降级到此档,默认走 bocha + 原生 WebSearch
4. 原生 `WebSearch`(全 MCP 不可用时最终兜底)

#### 2.3 精读工具优先链(R9)

按上到下优先级;**未挂载静默跳过**:

1. `mcp__jina-mcp-server__read_url`(质量优先,带 markdown 转换)
2. `mcp__fetch__fetch`
3. `mcp__playwright__browser_navigate` + `browser_snapshot` + `browser_take_screenshot` + `browser_evaluate`(及 `mcp__plugin_playwright_playwright__*` 对应工具)— **条件触发**:仅 LLM 判定此源必须 JS 渲染或登录后才出内容时才降级到此档,默认走 fetch;触发条件三选一即可降级:
   1. 源站明显需 JS 渲染(SPA / 框架渲染 / 动态加载)
   2. 源站内容需登录后才出(无凭据 → 降级也拿不到,此时不降级,改记「未决」)
   3. fetch 返回内容明显残缺(空 / 403 / SPA 占位符)
   - 不默认降级:fetch 已能拿到的内容不主动调 playwright
4. 原生 `WebFetch`(全 MCP 不可用时最终兜底)

#### 2.4 抓取与事实记录

- **中英双语搜**(汽车电子一手标准多为英文);材料保留原语言,纪要用中文。
- **每条事实记 URL + 抓取日期**(来源引用行内容);不编造 wiki 里没有的内容。
- **搜索→精读衔接**:搜索返回候选 URL + snippet(只够写纪要索引,不构成精读);**按候选逐个精读**(调精读档工具),精读过的源才落 `NNN-{slug}.md`;snippet 不精读的候选不进 inbox 文件,只在 `00-research-note.md` 源清单记「未精读(snippet 索引)」标记。
- **精读后无价值处理**(R6 硬约束):精读后判定为无价值 / 无效 / 无关的页面(典型:软广告 / 404 / 与研究问题无关 / 与已有源重复),**不**落盘 `NNN-{slug}.md`(避免 inbox/research/ 产生垃圾文件),**仅在 `00-research-note.md` 源清单标记「已精读(无效/无关)」**;**同样计入精读页数预算**。判定标准:页面是否回答了对应研究问题 → 否 → 无效标记。

#### 2.5 停机条件(质量门槛三元组 + 软预算,R5 升级)

LLM 达下表**任意一项**即停(**质量门槛优先**):

| 停机条件 | 触发语义 |
|---|---|
| 每研究问题 ≥2 独立源交叉验证 | 全部研究问题均达此门槛 |
| 纪要「未决问题」节已写 | 必填字段 |
| 全部研究问题有结论或未决标记 | 全问题不悬空 |
| 预算软上限触顶 | 任何一项触顶即停(质量门槛先达者先停) |

停机时 LLM 直接落盘,未决问题归 `00-research-note.md`「未决问题」节;**不再二次打断询问**。超预算停机不报错,只是记录「该问题未达质量门槛但已达预算上限」在「未决问题」节。

### 步骤 3:落 inbox(非阻塞)— [subagent 内执行]

#### 3.1 落盘路径

```
vault/inbox/research/{YYYYMMDD-HHMMSS}-{slug}/
├── 00-research-note.md            ← 调研纪要:研究问题 → 发现 → 未决问题 → 源清单
├── 001-{source-slug}.md           ← 精读过的源,每个一文件
├── 002-{source-slug}.md
└── ...
```

#### 3.2 源文件正文头部(必须)

```markdown
> 来源: <URL>
> 抓取于: YYYY-MM-DD
> 精读工具: mcp__jina-mcp-server__read_url | mcp__fetch__fetch | WebFetch (写实际用的)
> 研究问题: <对应 00-research-note.md 的问题编号>
```

源文件**不写 frontmatter**;不写 `[[wikilink]]`。

#### 3.3 `00-research-note.md` 结构(必须)

```markdown
# 调研纪要 — {topic}

**时间**: YYYY-MM-DD HH:MM:SS
**判定**: thin | empty
**总问题数**: N / 已答: M / 未决: K

## 研究问题

### Q1: <问题>
- **结论**: <一句>
- **证据源**: [001-...md](001-...md), [002-...md](002-...md)
- **未决**: <如有>

### Q2: <问题>
...

## 源清单

| # | URL | 抓取日 | 工具 | 状态 |
|---|---|---|---|---|
| 001 | https://... | YYYY-MM-DD | jina read_url | 已精读 / 落盘 |
| 002 | https://... | YYYY-MM-DD | fetch | 已精读(无效/无关) |
| 003 | https://... | — | — | 未精读(snippet 索引) |

## 工具可用性(本会话)

| 档位 | 状态 |
|---|---|
| bocha web_search | ✓ |
| ... | ... |
| 全链不可用? | 否 |
```

「状态」列四种值:
- **已精读 / 落盘**:对应 `NNN-{slug}.md` 已写入 inbox/research/
- **已精读(无效/无关)**:精读过但页面无价值,仍计入预算
- **未精读(snippet 索引)**:仅搜索档看到,未调精读档

### 步骤 4:汇报(非阻塞)— [主上下文,subagent 返回后]

subagent 返回(纪要摘要 + 文件清单),主上下文向用户报告:

- 研究问题 → 结论摘要(逐问题一行)
- 未决问题清单(如有)
- 文件清单(`inbox/research/{时间戳}-{slug}/` 下所有路径)
- **建议**用户跑 `/aeps-llm-wiki-ingest` 入库(不代跑;走现有 ingest 流水线对 `.md` 走路径 1 纯文本)

## 拍板门总结

| 时机 | 拍板内容 | 默认 |
|---|---|---|
| 步骤 1 → 步骤 2 之间(联网前) | 缺口报告 + 拟研究问题 + 质量门槛三元组 + 预算软上限基线 + 命中主题站点表 + 工具可用性表 是否确认 | 等用户明确;全链不可用时默认继续(用户可改「无原生 WebSearch 不准动手」特例处理) |
| 用户主动要求「无 WebSearch 不准动手」特例 | 全链不可用时是否中断结束 | 默认继续;用户可要求中断 |

## 不做什么(SKILL.md 边界)

- 不直写 `knowledge/`
- 不跑 ingest(仅建议用户跑)
- 不写判定 / 搜索脚本(LLM 语义判定)
- 零新 npm 依赖
- 不自动 commit;不调 git
- 不发明 frontmatter 字段
- inbox 文件不写 frontmatter / wikilink
- 不为登录墙站点降级调 playwright(无凭据 → 改记「未决」,非触发 playwright 降级)

## 回滚点

- 步骤 0-1:无写副作用,任意重跑无成本
- 步骤 3 落盘后:`rm -rf vault/inbox/research/{YYYYMMDD-HHMMSS}-{slug}/` 即可零残留
- SKILL.md 修改回滚:plugin 仓 `git revert <commit>`;query SKILL.md 单独 commit,回滚不影响 research 本体

## 引用

- **设计文档**:`doc/design/prd.md`(M2.6 research) + `doc/design/design.md`
- **工作流入口**:`doc/schema/schema.md §1.x`
- **字段权威**:`doc/schema/frontmatter-spec.md`(research 不写 frontmatter,本引用确认不冲突)
- **上下游**:`skills/aeps-llm-wiki-query/SKILL.md`(步骤 7 未覆盖 → research 衔接)+ `skills/aeps-llm-wiki-ingest/SKILL.md`(`inbox/research/` 落盘后入库,`.md` 走路径 1 纯文本)
- **工程可编辑**:`doc/template/research-sites.md`(主题 × 优先站点表,走 init sync-files.js else 分支)
- **可复用工具**:`mcp__jina-mcp-server__read_url` / `mcp__fetch__fetch` / 原生 `WebFetch`(网页精读优先链);`mcp__jina-mcp-server__search_web` / `mcp__bocha-mcp__bocha_web_search` / 原生 `WebSearch`(搜索优先链)
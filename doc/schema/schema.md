# aeps-llm-wiki-plugin — Agent 操作手册

> **plugin 版本**:0.6.7
> **初始化时间**:2026-09-04T10:30:00Z
> **维护者**:zhigang.liu

## Change History

| 版本 | 日期 | 变更 |
|---|---|---|
| 0.5.6 | 2026-09-08 | 批次 4(P3-1)版本号字串审计后保持一致(本批次未变更 schema.md 内容,仅补章节以严格对齐批次 4 R4 验收) |
| 0.6.7(措辞修正) | 2026-09-11 | prompt-audit 修正:`safe-mv.py` → `move-to-raw.js`、`scripts/convert-to-md.js` → `scripts/ingest/convert-to-md.js`(与 ingest SKILL.md 对齐);版本号不更新 |
> **权威顺序**:OKF v0.2 规范 > **`doc/schema/frontmatter-spec.md`(人读字段规范,唯一权威)** > `doc/schema/frontmatter.schema.json`(机器读,跟随 spec) > 本 `schema.md`(工作流入口) > `knowledge/glossary.md`(术语表)
>
> 本 `schema.md` **不重复列字段**,而是直接引用 `doc/schema/frontmatter-spec.md` (人读字段规范)与 `doc/schema/frontmatter.schema.json` (机器读) (PRD §10 Q1)。**字段定义以 `frontmatter-spec.md` 为最终裁决**,若本工作流描述与 spec 冲突,以 spec 为准。

---

## 1. 三种工作流

> **init 工作流**:本文件不重复 init 步骤序列;init 流程见 [PRD §4.1](../design/prd.md) + [design.md §1.2](../design/design.md)。本文件 §1 之后只描述需要 LLM 调度 / 创意性介入的 ingest / query / lint 三个工作流。

### 1.1 Ingest 工作流(用户 → inbox → raw → knowledge)

1. 用户把资料丢进 `{project}/inbox/`
2. 跑 `/aeps-llm-wiki-ingest`
3. SKILL.md 读 inbox 文件 → 按扩展名分流(详见 `doc/template/README.md` §1):
   - 纯文本(`.md` / `.txt` / `.json` / ...):直接读,**不生成 .converted.md**
   - 非文本(`.pdf` / `.docx` / `.pptx` / `.xlsx` / `.png` / ...):走 `scripts/ingest/convert-to-md.js` 转换,产物落 `raw/{subdir}/{basename}.{ext}.converted.md`
4. LLM 提议 `raw/{subdir}/` 分类 + 用户拍板 → `move-to-raw.js --apply` 同时迁原文件 + md 副本(走过转换的)
5. LLM 生成 `type: source` 源页(必选 3 节骨架 + LLM 自由追加节 + 强制溯源)+ 自动抽取 entity / concept 子页
   - **📋 最终正文结构(一眼看完)**:
     ```
     # 标题
     ─────────────────────────────────
     ## [自由追加节 1]       ← LLM 自主决定,文章独特结构呈现
     ## [自由追加节 2]       ← 强制溯源(忠于原文)
     ## [自由追加节 ...]
     ─────────────────────────────────
     ## 重点摘录              ← 必选,强制溯源
     ## 我的思考              ← 必选,LLM 解读产出,不需要溯源
     ## 总结:最有收获的一句话  ← 必选,LLM 解读产出,不需要溯源
     ─────────────────────────────────
     ## 相关页面(Related Pages)  ← 脚本自动生成
     ## 维护说明               ← 脚本自动生成
     ```
   - **✅ 关键约束(强制溯源的范围)**:
     | 节 | 强制溯源? | 备注 |
     |---|---|---|
     | 自由追加节(在 `## 重点摘录` 之前) | ✅ **必须忠于原文** | 不强制节名;演讲/标准/白皮书/论文类常见节名仅举例 |
     | `## 重点摘录` | ✅ **必须忠于原文** | 3-5 条要点 |
     | `## 我的思考` | ❌ 不需要溯源 | LLM 个人解读产出 |
     | `## 总结:最有收获的一句话` | ❌ 不需要溯源 | LLM 核心收获凝练,≤ 50 字 |
   - **必选 3 节骨架**(`## 重点摘录` / `## 我的思考` / `## 总结:最有收获的一句话`,缺一即 lint FAIL;详见 PRD §4.2 必须 M6):LLM 必须**先读源文件**(`raw/{subdir}/{file}` 原文件或 `.converted.md` 副本),从源文件实际抽取 3 节内容,不得用通用知识或 LLM 自身记忆填空
   - **可自由追加节**(**位于正文第一部分,在 `## 重点摘录` 之前**;LLM 自主决定叙述结构,**不**套固定模板):这些节是 LLM 对这篇文章的解读 —— LLM 必须**读完源文件后**判断这篇文章本身有什么独特结构,然后用相应的节名呈现;演讲实录类常用 `## 来源元信息` / `## 核心要点` / `## 关键引用`,标准文档类常用 `## 适用范围` / `## 术语定义` / `## 关键约束`,技术白皮书类常用 `## 技术原理` / `## 性能指标`,学术论文类常用 `## 研究背景` / `## 方法` / `## 结果` / `## 结论` —— 都是举例不是模板,LLM 应根据实际内容决定是否使用;**正文整体顺序**:`# 标题` → [自由追加节 0..n 个] → `## 重点摘录` → `## 我的思考` → `## 总结:最有收获的一句话` → `## 相关页面(Related Pages)` → `## 维护说明`
   - **强制溯源的范围**(**关键边界**):**`## 重点摘录` + 自由追加节**必须**忠于原文**,内容必须从源文件可溯源;**`## 我的思考` + `## 总结:最有收获的一句话` 不需要溯源**(这两节本身就是 LLM 的解读产出,原本就不来自源文件);来源不足自检(`[来源不足,需人工复核]` 标注)仅针对 `## 重点摘录` + 自由追加节
   - **强制溯源 + 来源不足自检**:LLM 写完后对每条断言自检能否在源文件中找到依据;**无法溯源 → 显式标注 `[来源不足,需人工复核]`**,不要静默删除、不要悄悄改写
   - **lint C20**(软约束):机械部分(3 节骨架缺失)→ FAIL;软约束部分(自由追加节溯源)→ SKILL.md 输出「重点摘录 / 自由追加节 溯源自检报告」等用户复核,不 FAIL、不自动改写
   - **页面结构指引**:模板 `templates/page-source.md` 在 `## 重点摘录` 之前以 blockquote 段(非 H2)写「LLM 阅读须知:页面结构约束」,scripts 解析 H2 时不识别该 blockquote,不影响骨架顺序
   - **生成 tags 前 SKILL.md 必须先读 [`doc/template/tag-spec.md`](tag-spec.md) 6 轴字典**;每条 tag 必须以 `domain/` / `layer/` / `phase/` / `docform/` / `maturity/` / `tec/` 之一为前缀;最少 5 条,最多 10 条;走完 tag-spec §8 范式 1-4 自检
   - **Related Pages(双向反链,ingest 阶段生成)**:对每个被抽取并创建的 entity / concept 子页,SKILL.md 完成如下两步:
     - **source 页 → 追加 `## 相关页面(Related Pages)` 区块**:位置在 3 节骨架之后、`## 维护说明` 之前;按 `### Entities` / `### Concepts` 两个固定子标题分组,每组使用目标页 `[[wikilink]]`(裸文件名或 `aliases` 别名);子标题占位始终保留,渲染时若某组为空则删除该子标题,全部为空则删除整个区块。每次 ingest **完全重建**该区块,**不保留人工添加的条目**。
     - **entity / concept 页 → 反向追加 source 链接**:在被抽取创建的 entity / concept 子页正文末尾、`## 维护说明` 之前,追加 `## 来源资料` 小节,列出本次 ingest 抽取该 entity / concept 的所有 `type: source` 页 `[[wikilink]]`。每次 ingest **完全重建**该小节,**不保留人工条目**;无任何 source 页引用时整节省略。该小节是 entity / concept 页的"被来源"区,与 source 页 Related Pages 的"导出引用"区互为反链;Obsidian 反向链接面板依赖此约定触发。
6. 更新 `knowledge/{index,overview,glossary,log}.md`

### 1.2 Query 工作流(用户问题 → wiki 答案 → analysis 落档)

1. 跑 `/aeps-llm-wiki-query "{question}"`
2. SKILL.md 走 4 跳扫描:
   - 第 1 跳:`knowledge/index.md` 找候选页(按 `tags` 关键词过滤)
   - 第 2 跳:读候选页(优先级:`description` / `summary` → `title` → 全文)
   - 第 3 跳:顺着正文标准 markdown 链接跳到相邻 `entities/` `concepts/` `analyses/` `comparisons/` 页(1 跳深度)
   - 第 4 跳:读 `glossary.md`(关键词消歧)+ `log.md` 近期 10 条
3. LLM 在阶段 3 推断 intent(`exact` / `ambiguous` / `{overview|comparison|other}`)
4. wiki 规模分流:< 500 页纯 4 跳扫描;500-1000 页优先 qmd;> 1000 页必须 qmd
5. 回答,**每条断言附 wiki 链接**——**主推 `[[wikilink]]` 裸文件名**(PRD §4.3 + Q9 决策;Q6 决策 A 已废),标准 markdown 链接作为兼容降级
6. G11 M3 gating:仅在 overview / comparison / ≥2 不同子目录 / ≥200 字任一命中才在末尾问用户是否落档
7. 用户拍板 → SKILL.md 生成 `type: analysis` 页(3 节分析专属骨架 + `sources_used` 必填 + `## 关联溯源` 末行 `> 引用:` 与 `sources_used` Set 比对)
   - **analysis 页 tags 同上,必须走 6 轴字典**(tag-spec.md);`docform/` 必填且单值(`docform/technical-doc` 或 `docform/experience` 常见);`sources_count` 与 `sources_used` 联动自检

### 1.3 Lint 工作流(`/aeps-llm-wiki-lint [--fix]`)

1. 扫所有 `knowledge/**/*.md` 文件
2. 报告:孤儿页、矛盾、**已填 `stale_after` 且过期的陈旧页**(未填静默跳过)、命名飘、漏链、frontmatter 不合规、正文骨架不合规
3. 默认只报告;**`--fix` 按问题级别分流**:
   - **确定性结构修复**(直接 patch 应用,`log.md` 追加 `**LintFix**` 条目):
     - frontmatter 字段缺失 → 补占位值 + WARN
     - frontmatter 字段类型错位 → 强转
     - `## 摘要` / `## Summary` 小节残留 → 删除并保留内容到 frontmatter `summary`
     - sources / analyses 缺 3 节骨架 H2 → 文件末尾追加占位 H2
     - `[[wikilink]]` 残留(方案 A 已废 wikilink)→ `--fix` 转为对应标准 markdown 链接
     - `links:` frontmatter 残留(对齐 OKF §5)→ `--fix` 删除
   - **语义级问题**(仅输出提案,不应用):
     - 矛盾、命名飘合并、漏链、陈旧页处理

> **陈旧度判断**(`frontmatter-spec.md` §4.5.2 + §12.2):仅在 `stale_after` 已填且 `now >= stale_after` 时报陈旧问题。**未填 `stale_after` 一律静默跳过,不报陈旧、不 WARN**。`updated` 字段是 plugin 综合推演时间(读事件),**不参与**陈旧度判断。

---

## 2. 类型 ↔ 目录绑死(详见 PRD §6.1 + `doc/template/README.md` §2.4)

> **权威 enum 清单**:见 [`doc/schema/frontmatter-spec.md` §4.1.1](../schema/frontmatter-spec.md);plugin 收敛 OKF §4.1 开放类型为 22 项硬枚举(18 叶子 + 4 顶层索引),与 knowledge/ 22 个目录 1:1 绑死。

| type 取值 | 知识库目录 |
|---|---|
| `source` | `knowledge/sources/` |
| `analysis` | `knowledge/analyses/` |
| `comparison` | `knowledge/comparisons/` |
| `synthesis` | `knowledge/syntheses/` |
| `entity.{person,organization,project,product,event,place,other}` | `knowledge/entities/{子类}/` |
| `concept.{theory,method,field,phenomenon,standard,term,other}` | `knowledge/concepts/{子类}/` |
| `index` | `knowledge/index.md` |
| `overview` | `knowledge/overview.md` |
| `glossary` | `knowledge/glossary.md` |
| `log` | `knowledge/log.md` |

合计 **1 + 7 + 7 + 1 + 1 + 1 + 4 = 22 个 type 值** ↔ **22 个目录**(18 叶子存储目录 `sources/` / `analyses/` / `comparisons/` / `syntheses/` + 7 entity + 7 concept + 4 顶层索引 `index.md` / `overview.md` / `glossary.md` / `log.md`)。

---

## 3. 正文链接规则(PRD §10 Q9 决策;Q6 决策 A 已废)

plugin 正文**主推 `[[wikilink]]` 裸文件名**,依赖 Obsidian 唯一名解析;目标页 frontmatter 通过 `aliases: [...]` 注册别名,wikilink 也可用别名。标准 markdown 链接降级为兼容写法,OKF reader 仍可识别。

### 3.1 三条核心规则

- **规则 1 - 关键名词首字链接(First-Mention Linking)**:同一实体/概念在一篇正文中只在第一次出现时添加 wikilink,避免 [[ ]] 淹没、保持排版干爽。
- **规则 2 - 裸文件名 + aliases 别名机制**:wikilink 形如 `[[andrej-karpathy]]`(裸文件名)或 `[[Andrej Karpathy]]`(别名,目标页 frontmatter `aliases: [...]` 声明)。OKF reader 兼容解析;OKF §6.1 用词为 "MAY standard markdown link"(允许而非禁止其他),plugin 扩展 wikilink 不与 OKF 冲突。
- **规则 3 - 关联导引(Related Links)**:正文最底部设立无序列表节，挂载相关 `comparisons/` / `syntheses/` / `analyses/` 页，示例:

  > 对 `type: source` 的源页，ingest 还必须在正文末尾生成 `## 相关页面(Related Pages)` 区块，按 `Entities` / `Concepts` 分组列出本次抽取并生成的相关页面。每次 ingest 完全重建该区块，不保留人工条目；某组为空时省略该组，全部为空时省略整个区块。该区块是 source 页模板的一部分，不在渲染阶段临时推断。详情见 §1.1 步骤 5 子步骤「Related Pages(双向反链,ingest 阶段生成)」。
  >
  > 对被抽取创建的 `entity.*` / `concept.*` 子页,ingest 还必须在正文末尾、`## 维护说明` 之前追加 `## 来源资料` 小节,列出本次抽取该 entity / concept 的所有 `type: source` 页 `[[wikilink]]`。每次 ingest 完全重建该小节,不保留人工条目;无任何 source 引用时整节省略。该小节与 source 页 `## 相关页面(Related Pages)` 互为反链,Obsidian 反向链接面板依赖此约定触发。


  ```markdown
  ## 关联导引

  - 对照:[[layerzero-vs-wormhole]]
  - 综合:[[automotive-functional-safety]]
  - 分析:[[s32g-vs-s32k3-body-controller]]
  ```

### 3.2 禁止规则

- **禁止 frontmatter `links:` 字段**:对齐 OKF §5「Lineage is expressed through links, not a dedicated field」;lint FAIL on 残留,`--fix` 删除。
- **禁止 `[[wikilink]]` 与标准 markdown 链接混用**:同段落二选一,优先 wikilink(Q9 决策)。

### 3.3 Obsidian 别名机制(plugins 扩展 `aliases` 字段)

- 字段类型:`string[]`,位于 frontmatter 顶层
- 作用:为页面注册别名,`[[alias]]` 形式的 wikilink 可解析到本页
- 与 OKF 兼容:OKF reader 按未知字段忽略(MUST NOT reject)
- 与 `source_file` 区别:`source_file` 指向原文件路径(wiki 引用 raw 素材),`aliases` 是 wiki 页自身的人读别名(双向链接解析)

示例:

```yaml
---
type: entity.person
title: "Andrej Karpathy"
aliases:
  - "Andrej Karpathy"
  - "Karpathy"
---
```

则 `[[Karpathy]]` 在 Obsidian 里直接跳转到本页。

### 3.4 lint C15.5 反转(待实现)

- **反转前**:`--fix` 自动 wikilink → 标准 markdown 链接,lint FAIL on wikilink 残留
- **反转后**(2026-09-05,PRD Q9):`--fix` 自动标准 markdown 链接 → wikilink,wikilink 不再 FAIL(代码层待实现)

> **lint C15.6(待实现)**:frontmatter `type` 必须落在 schema.json `enum` 18 项内(`frontmatter-spec.md` §4.1.1),否则 FAIL。plugin 收敛 OKF 开放类型,与目录 1:1 绑死(README §2.4)。

> **lint C15.7(待实现)**:frontmatter `updated` 必填(plugin 强化,所有 6 种 type 必含,`frontmatter-spec.md` §2 + §11.7 + §12.2),FAIL on 缺失。`--fix` 自动填 `generated.at` 作 fallback(若 generated.at 缺失则取文件 mtime),不动已有 `updated`(Q7 死循环防护)。

---

## 4. log.md 格式(OKF §9)

按 ISO 8601 日期做 H2,最新在前:

```markdown
# log

## 2026-09-04

**Creation**: query "S32G vs NXP S32K3 在车身控制器选型上怎么选?" → analyses/2026-09-04-s32g-vs-s32k3.md
**Ingest**: inbox/iso26262.pdf → raw/06_功能安全/iso26262.pdf (+ converted.md)
**LintFix**: entities/person/andrej-karpathy.md 补 frontmatter `updated` 字段
```

---

## 5. 引用本 SCHEMA

- 字段定义权威:**`plugin 源码/doc/schema/frontmatter-spec.md`**(人读字段规范,唯一权威);`plugin 源码/doc/schema/frontmatter.schema.json` 跟随对齐
- 字段总表人读入口:`plugin 源码/doc/template/README.md`
- 类型 ↔ 目录绑死清单:本文件 §2 + `doc/template/README.md` §2.4
- 正则化引用模板:`plugin 源码/doc/template/page-*.md`

---

## 6. 变更历史

| 版本 | 日期 | 变更 |
|---|---|---|
| 0.5.2 | 2026-09-04 | 初版,随 PRD v0.5.2 一起冻结 |
| 0.5.3 | 2026-09-05 | §3 链接规则反转:主推 `[[wikilink]]` 裸文件名 + aliases 别名机制(PRD §10 Q9;Q6 决策 A 已废);lint C15.5 反转(代码层待实现) |
| 0.5.3 | 2026-09-05 | §1 tag 数量约束下限由"3 条"对齐为"5 条",与 `frontmatter.schema.json` `minItems: 5` 及 `tag-spec.md` §8 Lint 阈值一致 |
| 0.5.4 | 2026-09-06 | §1 顶部加 init 工作流引用句(init 流程不在本文件重复);§1.1 步骤 3 `convert-to-md.py` → `convert-to-md.js`(对齐 design.md §4.2 Node.js 单栈 + G6);顶部 plugin 版本号 0.5.2 → 0.5.4(版本错位 bugfix) |
| 0.5.5 | 2026-09-06 | §2 表 + enum 扩到 22 项:`knowledge/` 根下4 件顶层索引 `index.md` / `overview.md` / `glossary.md` / `log.md` 对应新增 type 值 `index` / `overview` / `glossary` / `log`(init 首次启用时由 4 件顶层索引的初始 frontmatter 引用);合计 18 → 22 项硬枚举;`frontmatter.schema.json` enum +描述同步更新;顶部 plugin 版本号 0.5.4 → 0.5.5 |
| 0.5.6 | 2026-09-07 | M2.2 ingest skill 落地:`scripts/ingest/` 新增 7 脚本(scan-inbox/classify/convert-to-md/init-batch/move-to-raw/build-related-pages/append-log) + 1 lint-stub 占位;`skills/aeps-llm-wiki-ingest/SKILL.md` 19 步编排;§1.1 ingest 工作流描述从"待实现"→"已实现 0.5.6";顶部 plugin 版本号 0.5.5 → 0.5.6 |
| 0.5.6 | 2026-09-08 | 批次 4 (P3 文档与版本一致):失败语义表权威源迁移到 `doc/design/implement-ingest.md §6.1`(P3-3);`scripts/check-version-consistency.js` 新增校验脚本(P3-1);模板 tags 示例 ≥ 6 条 + 顶部加注释(P3-4)。**注**:顶部 plugin 版本号保持 0.5.6 不变,plugin.json 由父任务统一发版到 0.6.0 时再升 |

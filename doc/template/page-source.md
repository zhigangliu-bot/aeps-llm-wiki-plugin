<!-- 提示:模板示例 tags 故意 ≥ 6 条,避免 LLM 按 5 条填导致 WARN;真实生成时按需保留全部或精简到 ≥ 5 条 -->
---
# OKF v0.2 §4.1 必填字段
type: source
title: "$TITLE"
description: "$DESCRIPTION"

# OKF §4.1 tags (标准 YAML List 语法;值为示例,生成时保留全部或精简到 ≥ 5 条)
tags:
  - docform/standard-spec
  - domain/fusa
  - tec/iso26262-asil-d
  - maturity/standard
  - layer/bsw-os
  - phase/architecture

# OKF §4.1 resource
resource: "$RESOURCE"

# OKF §5.2 generated
generated:
  by: "producer/aeps-llm-wiki-plugin/$VERSION"
  at: "$NOW"

# OKF §5.4 / §5.5 lifecycle
status: stable
stale_after: "$STALE_AFTER"

# plugin 扩展字段
source_file: "$SOURCE_FILE"
format: $EXT
converter: $CONVERTER
native_text: $NATIVE_TEXT
converted_path: $CONVERTED_PATH

# plugin 推荐字段
updated: "$NOW"
summary: "$SUMMARY"

# plugin 推荐字段(Obsidian 原生别名机制,v0.6.5 起;gen-page 按 --aliases 注入,缺省 fallback [title])
aliases:
  - "页面标题或常用别名"
---
# ISO 26262:2018 功能安全标准

> **【LLM 阅读须知:页面结构约束】**(本段是 LLM 指引,不是 H2 标题;scripts 解析 H2 时不识别)
>
> ---
>
> ### 📋 最终正文结构(一眼看完)
>
> ```
> # 标题
> ─────────────────────────────────
> ## [自由追加节 1]       ← LLM 自主决定,文章独特结构呈现
> ## [自由追加节 2]       ← 强制溯源(忠于原文)
> ## [自由追加节 ...]
> ─────────────────────────────────
> ## 重点摘录              ← 必选,强制溯源
> ## 我的思考              ← 必选,LLM 解读产出,不需要溯源
> ## 总结:最有收获的一句话  ← 必选,LLM 解读产出,不需要溯源
> ─────────────────────────────────
> ## 相关页面(Related Pages)  ← 脚本自动生成
> ## 维护说明               ← 脚本自动生成
> ```
>
> ### ⚠️ 自由追加节强约束(v0.5.9 起)
>
> - **`## 重点摘录` 之前必须至少有 1 个 H2 节**(lint C21 WARN)。LLM 读完源文件后,先问自己:**这篇 source 有什么独特结构?** 立刻用 1 个(短文)或多个(长文)H2 节把它呈现出来。
> - **占位骨架节名默认是 `## 阅读路线`** —— LLM 在此基础上**强烈建议改名**为对本文具体的节名(如演讲实录类常见 `## 来源元信息` / `## 核心要点` / `## 关键引用`,标准文档类常见 `## 适用范围` / `## 术语定义` / `## 关键约束`,技术白皮书类常见 `## 技术原理` / `## 性能指标` / `## 与同类对比`,学术论文类常见 `## 研究背景` / `## 方法` / `## 结果` / `## 结论`)。**任何节名都可,任何节都可删可改**,只要对这篇具体文章是合理的。
> - **唯一豁免**:如果源文件极短(单页推文 / 一句话金句 / 一张表格图)实在无独特结构可挖,允许保留占位节名 `## 阅读路线` 并写一句话说明"原文为短文,无独立结构可挖,要点已并入 ## 重点摘录"。
> - **所有自由追加节都强制溯源**(对齐下方"强制溯源的范围"表):内容必须从源文件可溯源,不得用通用知识 / 外部信息 / LLM 自身记忆填空;无法溯源 → 显式标注 `[来源不足,需人工复核]`。
>
> ### ✅ 关键约束(强制溯源的范围)
>
> | 节 | 强制溯源? | 备注 |
> |---|---|---|
> | 自由追加节(在 `## 重点摘录` 之前) | ✅ **必须忠于原文** | 不强制节名;演讲/标准/白皮书/论文类常见节名仅举例 |
> | `## 重点摘录` | ✅ **必须忠于原文** | 3-5 条要点 |
> | `## 我的思考` | ❌ 不需要溯源 | LLM 个人解读产出 |
> | `## 总结:最有收获的一句话` | ❌ 不需要溯源 | LLM 核心收获凝练,≤ 50 字 |
>
> ---
>
> **必选骨架(3 节,缺一即 lint FAIL)**:`## 重点摘录` / `## 我的思考` / `## 总结:最有收获的一句话`,每节正文均由 LLM 从源文件(`raw/{subdir}/{file}` 原文件或 `.converted.md` 副本)**实际抽取**填写。
>
> **可自由追加节**(LLM 自主决定叙述结构,**不**套固定模板;**位于正文第一部分,在 `## 重点摘录` 之前**):LLM 根据**这篇源文件的实际内在结构**(是什么类型的资料、有什么独特的信息组织),在 `## 重点摘录` 之前自行决定追加任意数量的 H2 节。这些节是 **LLM 对这篇文章的解读**,不是通用模板:
>
> - **不强制任何具体节名** —— 不要看到模板里有"来源元信息"就每个 source 都加,看到"关键引用"就每个都抄,看到"核心要点"就每个都列。LLM 必须**读完这篇文章后**判断这篇文章本身有什么独特结构,然后**用相应的节名呈现**。
>
> - **按文章类型举例**(是举例不是模板,LLM 应根据实际内容决定是否使用):演讲实录类常见 `## 来源元信息` / `## 核心要点` / `## 关键引用`;标准文档类常见 `## 适用范围` / `## 术语定义` / `## 关键约束`;技术白皮书类常见 `## 技术原理` / `## 性能指标` / `## 与同类对比`;学术论文类常见 `## 研究背景` / `## 方法` / `## 结果` / `## 结论`。**任何节都用都删都改名都 OK,只要对这篇具体文章是合理的**。
>
> - **3 节骨架 vs 自由追加节的功能分工**:`重点摘录` / `我的思考` / `总结:最有收获的一句话` 是**对所有 source 统一的最小解读**(摘录 / 个人思考 / 一句话总结);自由追加节是**对本文独特结构的呈现**(本文有什么 metadata、有什么独特的论述框架、有什么金句、有什么内部表格等)。前者跨文章一致,后者跨文章差异巨大。
>
> **强制溯源的范围**(**关键边界**):**`## 重点摘录` + 自由追加节**必须**忠于原文**,内容必须从源文件可溯源(`raw/{subdir}/{file}` 原文件或 `.converted.md` 副本),**不得**用通用知识、外部信息或 LLM 自身记忆填空。**`## 我的思考` + `## 总结:最有收获的一句话` 不需要溯源**(这两节本身就是 LLM 的解读产出,原本就不来自源文件 —— `我的思考` 是 LLM 看完本文后触发的问题、与其他 wiki 页的联系、可深挖方向;`总结:最有收获的一句话` 是 LLM 对本文的核心收获凝练,本来就找不到对应原文段落)。
>
> **来源不足自检**:LLM 写完 `## 重点摘录` + 自由追加节后,必须对每条断言自检能否在源文件中找到依据;**无法溯源 → 显式标注 `[来源不足,需人工复核]`**,**不要**静默删除、不要悄悄改写。`## 我的思考` / `## 总结:最有收获的一句话` **不参与**溯源自检。
>
> **顺序约束**(对齐 `temp/huawei-accelerating-adas-to-ad.md` / `temp/aixin-metaix-back-to-business-essence.md` 两份实际源页):
>
> - **正文整体顺序**:`# 标题` → **[自由追加节(0..n 个,在 `## 重点摘录` 之前)]** → `## 重点摘录` → `## 我的思考` → `## 总结:最有收获的一句话` → `## 相关页面(Related Pages)` → `## 维护说明`
> - 自由追加节位于**正文第一部分**(在 `## 重点摘录` 之前);节之间相对顺序由 LLM 按文章类型与内在逻辑组织(如演讲实录常见 `## 来源元信息` → `## 核心要点` → `## 关键引用`)
> - 3 节必选骨架内部顺序固定:`重点摘录` → `我的思考` → `总结:最有收获的一句话`
> - **`## 相关页面(Related Pages)` 与 `## 维护说明` 由脚本自动生成,LLM 不修改**
>
> **对齐**:PRD §4.2 必须 M6 + §4.4 lint C20 + §4.4 lint C21。

## 阅读路线

【**v0.5.9 占位骨架节,LLM 必须改造**】

读完源文件后,**先**问自己:**这篇 source 有什么独特结构?** 在此节用 1-N 个 H2 节呈现它(短文至少 1 个,长文多个)。**强烈建议改名**(如 `## 来源元信息` / `## 核心要点` / `## 关键引用` / `## 适用范围` / `## 术语定义` / `## 关键约束` / `## 技术原理` / `## 性能指标` / `## 与同类对比` / `## 研究背景` / `## 方法` / `## 结果` / `## 结论` 等),**任何节名都可,任何节都可删可改**,只要对本文具体合理。短文豁免:极短源文件(单页推文 / 一句话金句 / 一张表格图)可保留此节名 + 一句"原文为短文,无独立结构可挖,要点已并入 ## 重点摘录"。

所有自由追加节**强制溯源**(对齐上方"强制溯源的范围"表):内容必须从源文件可溯源;无法溯源 → 显式标注 `[来源不足,需人工复核]`。

## 重点摘录


> 原始来源:[链接文本,见下方表格](链接目标,见下方表格)

【LLM 自动从原文摘录 3-5 条要点。**正文链接主推 `[[wikilink]]` 裸文件名**(PRD §10 Q9,`doc/schema/schema.md` §3.1),示例:`关键术语:[[asil]] / [[autosar]] / [[iso-26262]]`,依赖 Obsidian 唯一名解析;目标页 `aliases` 注册的别名也可直接使用。】

## 我的思考

【LLM 自动填充:从这份资料中触发的研究问题、与其他 wiki 页的联系、可深挖的方向。】

## 总结:最有收获的一句话

【LLM 自动填充:一句话 core verdict,≤ 50 字。】

## 相关页面(Related Pages,由 ingest 自动生成)

【本节由 `/aeps-llm-wiki-ingest` 根据本源页抽取并创建的实体页、概念页生成。每次 ingest **完全重建**本节，不保留人工添加的条目；没有相关页面时不输出本节。链接使用目标页面的 `[[wikilink]]`，按类别分组。】

### Entities

【自动填充相关实体页链接；无相关实体时省略本小节。】

### Concepts

【自动填充相关概念页链接；无相关概念时省略本小节。】

---

## 维护说明(本节由 plugin 自动追加,可手删)

- 本页由 `/aeps-llm-wiki-ingest` 自动生成
- **SKILL.md 必读下方「4 路径分流」表**,按原文件扩展名决定 `converter` / `native_text` / `converted_path` / 正文链接 4 个变量的具体取值
- 原文件迁移路径:`inbox/{file}` → `raw/{subdir}/{file}`
- lint 必查:frontmatter 必填字段(详见 `doc/schema/frontmatter.schema.json`)+ 3 节骨架 + `## 摘要` 禁用 + 正文链接目标存在(`[[wikilink]]` 与标准 markdown 链接混用检测,优先 wikilink)+ **`converter` 与 `native_text` / `converted_path` 三字段一致性**
- C15.5 反转(PRD Q9):wikilink 不再 FAIL;`--fix` 反向将正文标准 markdown 链接 → `[[wikilink]]`(代码层待实现,详见 `doc/schema/schema.md` §3.4 + `frontmatter-spec.md` §11.4)

### 总原则(原生多模态优先 · 第一原则)

> **SKILL.md 跑 ingest 时第一步永远是「先尝试 Claude Code 原生识别」**。
>
> **能识别 → 直接结束,不生成 `.converted.md`,不走 `convert-to-md.py`,不消耗任何 OCR / 转换依赖**。理由:**原生支持多模态的 LLM 对文件的理解能力一定是最强的**(版面 / 表格 / 图文位置 / 语义),**第三方 OCR / 版面还原工具在精度、保真度、上下文关联上永远输给 LLM 原生能力**,**只在 LLM 真的无法识别时才降级**。这一条是 plugin 的**第一原则**,不是路径 2 的局部策略。
>
> 具体见 PRD §4.2「总原则(原生多模态优先)」+ §4.2「必须 M5」硬约束 + lint C18/C19。

### 4 路径分流(SKILL.md 按下表填 4 个变量)

| 路径                                       | 原文件扩展名                                                                                              | `converter`     | `native_text` | `converted_path`                               | 正文`> 原始来源:` 链接文本 / 目标                                                |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------------- | ----------------- | --------------- | ------------------------------------------------ | ---------------------------------------------------------------------------------- |
| **路径 1 —— 纯文本直接读**         | `.md` `.markdown` `.rst` `.txt` `.csv` `.json` `.yaml` `.yml` `.xml` `.html` `.htm` | `null`          | `true`        | `null`                                         | `[notes](./raw/{subdir}/notes.md)`(指原文件)                                     |
| **路径 2 —— Claude Code 原生识别**(对齐 PRD §4.2 路径 2 收紧) | `.pdf` 等 Claude Code 当前能直接读取的格式 | `claude-native` | `true`        | `null`                                         | `[iso26262.pdf](./raw/{subdir}/iso26262.pdf)`(指原文件)                          |
| **路径 3 —— 外部工具转换**          | 同路径 2,但 Claude Code 不能识别;`.docx`/`.pptx`/`.xlsx` 优先级 **pyoffice → anydoc → docling**(scripts/RULES.md §1,`converter` 填实际走通的第一个) | `pyoffice` / `anydoc` / `docling` | `false`       | `./raw/{subdir}/{basename}.{ext}.converted.md` | `[iso26262.pdf.converted](./raw/{subdir}/iso26262.pdf.converted.md)`(指 md 副本) |
| **路径 4 —— OCR**                  | `.png` `.jpg` `.jpeg` `.bmp` `.tiff`                                                            | `paddleocr`     | `false`       | `./raw/{subdir}/{basename}.{ext}.converted.md` | `[chip.png.converted](./raw/{subdir}/chip.png.converted.md)`(指 md 副本)         |

### 完整 frontmatter 例子(每路径一个)

#### 路径 1(纯文本 `.md`)

```yaml
source_file: "[[15-算法/cross-chain-bridge-notes.md]]"
format: md
converter: null
native_text: true
converted_path: null
```

正文:`> 原始来源:[cross-chain-bridge-notes](./raw/15_算法/cross-chain-bridge-notes.md)`

#### 路径 2(Claude Code 原生识别 `.pdf`)

```yaml
source_file: "[[06-功能安全/iso26262.pdf|ISO 26262:2018 原文]]"
format: pdf
converter: claude-native
native_text: true
converted_path: null
```

正文:`> 原始来源:[iso26262.pdf](./raw/06_功能安全/iso26262.pdf)`

#### 路径 3(anydoc 降级 `.pdf`)

```yaml
source_file: "[[06-功能安全/iso26262.pdf|ISO 26262:2018 原文]]"
format: pdf
converter: anydoc
native_text: false
converted_path: ./raw/06_功能安全/iso26262.pdf.converted.md
```

正文:`> 原始来源:[iso26262.pdf.converted](./raw/06_功能安全/iso26262.pdf.converted.md)`

#### 路径 4(OCR `.png`)

```yaml
source_file: "[[02-芯片/chip-block-diagram.png]]"
format: png
converter: paddleocr
native_text: false
converted_path: ./raw/02_芯片/chip-block-diagram.png.converted.md
```

正文:`> 原始来源:[chip-block-diagram.png.converted](./raw/02_芯片/chip-block-diagram.png.converted.md)`

### 调用流程(SKILL.md 跑 `/aeps-llm-wiki-ingest` 时)

1. 读 `inbox/{file}` 扩展名 → 按上表分流到 4 路径之一
2. 填本 template 的 4 个变量
3. 走转换(路径 3/4 调用 `scripts/convert-to-md.py`;路径 1/2 跳过)
4. 原文件 + md 副本(若有)一起 `safe-mv.py --apply` 到 `raw/{subdir}/`
5. LLM 读原文件 / md 副本生成 `## 重点摘录` / `## 我的思考` / `## 总结`

### 能力边界

Claude Code 原生识别哪些格式**不写死清单**,由 SKILL.md 运行时动态探测(适配未来 Claude Code 新增能力)。新版本 Claude Code 能读 `.pdf` 文本 → 自动走路径 2;某天失效 → 自动降级路径 3。

---

## 字段一致性 lint(新增,SKILL.md 必走)

| `converter` 值           | 期望`native_text` | 期望`converted_path`                                          | 不一致行为 |
| -------------------------- | ------------------- | --------------------------------------------------------------- | ---------- |
| `null`                   | `true`            | `null`                                                        | FAIL       |
| `claude-native`          | `true`            | `null`                                                        | FAIL       |
| `anydoc` / `paddleocr` / `pyoffice` / `docling` | `false`           | 非 null(必须指向`raw/{subdir}/{basename}.{ext}.converted.md`) | FAIL       |

正文 `> 原始来源:` 链接目标存在性 + 链接目标与 `source_file` / `converted_path` 一致性也 FAIL on 不一致(详见 PRD §4.4 lint C16.x,待写)。

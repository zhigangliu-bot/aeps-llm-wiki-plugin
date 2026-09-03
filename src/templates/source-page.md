# source-page.md — sources/ 页生成模板

> **角色**:scripts 在 ingest 阶段生成 `knowledge/sources/<basename>.md` 时的 frontmatter + 正文骨架模板。
> **生成方**:`scripts/generate-source-page.py`(M3 落地)+ SKILL.md ingest 阶段调用
> **修改权限**:生成后归用户主,plugin 不再覆盖

---

## frontmatter 锁

```yaml
---
type: source
title: "<人类可读标题>"
updated: <ISO 8601>           # 最近一次有意义更新(重新生成 ≠ 更新)
tags: [<六轴受控词表 tag>]     # 详见 templates/tag-template.md
status: stable                 # draft / stable / deprecated,缺省 stable

# 原始文件定位 —— 双字段同源
# - source_file: 顶层字符串,Obsidian 笔记属性面板识别为可点击链接(Q9)
# - sources[].resource: OKF v0.2 §5.1 必填数组,外部 OKF reader 消费
# 两个字段值必须相等(LINT C5 一致性断言)
source_file: raw/<subdir>/<basename>.<ext>
sources:
  - id: <slug>                 # kebab-case,与文件名一致
    resource: raw/<subdir>/<basename>.<ext>
    title: "<原始资料标题>"
    author: "<作者 / 组织>"
    last_modified: <ISO 8601>

# G10 转换产物定位(详见 prd §4.2 M2 + design §4.2 frontmatter 填充规则)
# - format / converter / native_text: 描述原文件是否走过转换 + 走哪个转换器
# - converted_path: md 副本相对 raw/ 的路径(供 query 阶段 LLM 直接读)
# - links: OKF v0.2 §9 镜像字段,值 = [[<basename>.<ext>.converted]](转换的)或 [[<basename>]](纯文本)
# - native_text: true 时 converter=null + converted_path=null(纯文本直接读)
format: <pdf|pptx|docx|xlsx|png|jpg|jpeg|bmp|tiff|md|txt|...>     # 原文件扩展名(小写,OKF 风格)
converter: <anydoc|paddleocr|claude-native|null>                   # 实际转换器;纯文本 = null
native_text: <true|false>                                          # 是否原生纯文本
converted_path: <raw/<subdir>/<basename>.<ext>.converted.md|null>  # md 副本路径;纯文本 = null
links:
  - "[[<basename>.<ext>.converted]]"   # 走过转换;纯文本则 "[[<basename>]]"

# 长摘要(≤ 280 字符,source 类型必填,SCHEMA.md §2.2)
summary: "<一段话总结,≤ 280 字符>"
---
```

### 双字段 `source_file` + `sources[].resource` 为什么并存

| 字段 | 谁读 | 为什么需要 |
|---|---|---|
| `source_file:`(顶层字符串) | Obsidian UI | Obsidian 笔记属性面板识别 `source_file` / `source` 字段为可点击链接(Q9);用户在 Obsidian 里点这个字段值就能跳转 / 打开原始文件 |
| `sources[].resource`(OKF §5.1 数组) | 外部 OKF reader / lint / 工具链 | OKF v0.2 spec 必填字段,机器可读;携带 id / title / author / last_modified 等额外 provenance |

**为什么不只留一个**:
- 单留 `source_file:` → OKF 工具不识别(非 spec 字段)、失去 provenance 子字段
- 单留 `sources[].resource:` → Obsidian 用户在笔记属性面板看不到可点击链接(Q9 解决不了)
- 两个并存 = Obsidian 用户能点 + OKF reader 能消费 + lint 能校验一致性,零妥协

### G10 四字段 + links 镜像的写入指引

1. **`format`** = 原文件扩展名,**小写**(`PDF` → `pdf`);纯文本也照填(如 `.md` → `md`)
2. **`converter`** 三选一:
   - `anydoc` —— pptx / docx / xlsx / pdf 走过 anydoc 转 md
   - `paddleocr` —— png / jpg / jpeg / bmp / tiff 走 OCR
   - `claude-native` —— Claude Code 内置 converter 成功(无降级)
   - `null` —— 纯文本直接读(.md / .txt / .json / ...)
3. **`native_text`** 与 `converter` 强绑定:`true` ⇔ `converter: null`;`false` ⇔ `converter` ∈ {anydoc, paddleocr, claude-native}
4. **`converted_path`**:
   - 转换的 → `raw/<subdir>/<basename>.<ext>.converted.md`(与原文件**同一 subdir**)
   - 纯文本 → `null`
5. **`links:` 镜像**:v0.2 Q6 + Q7 死循环防护;转换的 → `[[<basename>.<ext>.converted]]`;纯文本 → `[[<basename>]]`
6. **lint 断言**(G10 新增):
   - `native_text: true` ⇔ `converter: null` ⇔ `converted_path: null`
   - `native_text: false` ⇔ `converter` ∈ {anydoc, paddleocr, claude-native} ⇔ `converted_path` 非 null
   - `links[0]` 与正文 `## 重点摘录` 末尾的 `> 原始来源:[[...]]` 一致

### LLM 写入指引

1. **`source_file:` 与 `sources[0].resource` 值必须相等**(同源,指向 `raw/<subdir>/<basename>.<ext>`)
2. `<subdir>` 是 ingest 时拍板的 raw 15 类子目录名(来自 `templates/raw-readme.md`)
3. `<basename>` 是 inbox 文件去掉扩展名的部分(中文 / 空格 / 大写保留原文件名)
4. `<ext>` 保留原扩展名(pptx / docx / xlsx / pdf / md / txt / png / jpg 等)
5. `sources[0].title` 取自原始资料标题(优先文件名 → 文件元数据 → LLM 推断)
6. `sources[0].author` 留原始作者 / 发布组织;无法判断时填 `unknown`
7. `sources[0].last_modified` 取文件 mtime;无元数据时取 ingest 当天

## 正文骨架锁(3 节 H2 硬约束,SCHEMA.md §3.1)

```markdown
## 重点摘录

<原始资料关键段摘录 + 来源标注(节 / 页码 / 时间戳)>

> 原始来源:[[<basename>.<ext>.converted]]   # G10(G10 转换场景,见 prd §4.2 M3 + design §4.2);纯文本则为 [[<basename>]]

## 我的思考

<LLM 读后的解读、对比、延伸思考>

## 总结:最有收获的一句话

<一句话总结,可独立成立,无前言后语>
```

### LLM 写入正文指引

1. **3 节齐全,缺一 FAIL**(lint C4 自动追加占位 H2,但空内容会被 WARN)
2. **禁止 `## 摘要` / `## Summary` 小节**(长摘要走 frontmatter `summary` 字段)
3. **`[[wikilink]]` 一等公民**(Q6 + design §3.6.2):指向已有 entity / concept / 其他 source 页用 `[[page]]` / `[[page|显示]]` / `[[page#章节]]`
4. **指向 raw 文件**(原文件):用 markdown 链接 `[text](raw/<subdir>/<basename>.<ext>)`(OKF §6.1 标准),**不用 `[[wikilink]]` 形式**(Obsidian 默认不把 `[[]]` 解析为非 markdown 文件,会红链)
5. **指向 raw/ 里的 md 副本**(G10 转换产物):用 `[[<basename>.<ext>.converted]]` 一等公民(纯文本则 `[[<basename>]]`),Obsidian 双链原生可跳;lint 校验正文与 frontmatter `links[0]` 一致
6. **正文里出现原始资料文件名时**,**不要**重复写 `source_file:` 路径(避免 DRY 违反);在 frontmatter 已经有可点击链接

---

### G10 不应做(源页 frontmatter 写入侧)

- ❌ 不在 frontmatter 留与 md 副本哈希相关的字段(可由 lint 按需计算,非 AC)
- ❌ 不在 raw/ 下生成 `_converted/` 子目录(保持 raw 子目录语义单一)
- ❌ 不为纯文本文件伪造 `converter` / `converted_path`(必须 native_text: true + null)

## 文件名约定

- 路径:`knowledge/sources/<basename>.md`
- `<basename>` 与 `raw/<subdir>/<basename>.<ext>` 共享文件名主体(便于视觉关联)
- 中文 / 空格 / 大写保留原文件名(由 LLM 在 ingest 时从 `inbox/<file>` 拷贝)

## 不变量

- `source_file:` 与 `sources[0].resource` **必须值相等**(lint C5 强校验)
- **G10 强校验**(lint C13):
  - `native_text: true` ⇔ `converter: null` ⇔ `converted_path: null`
  - `native_text: false` ⇔ `converter` ∈ {anydoc, paddleocr, claude-native} ⇔ `converted_path` 非 null 且以 `raw/<subdir>/` 开头
  - `links[0]` 值与正文 `## 重点摘录` 末尾 `> 原始来源:[[...]]` 一致(走 Set 比对,Q7 死循环防护规则)
- 3 节 H2 骨架齐全(缺一 FAIL)
- 6 轴 tag 受控词表(详见 `templates/tag-template.md`)
- `updated` 字段值必须反映**内容**变更时间,**不是**文件重新生成时间

## 引用

- `templates/knowledge-SCHEMA.md` §2.2(source 类型必填字段)+ §3.1(正文骨架)
- `design.md` §3.6(source 页结构 + `raw_category` 派生)+ §3.6.2(OKF 双格式 wiki link)+ §4.2(ingest G10 M2 + M3)
- `prd.md` §4.2 M1-M4(G10 增量需求)
- `templates/raw-readme.md`(raw 15 类子目录字典)
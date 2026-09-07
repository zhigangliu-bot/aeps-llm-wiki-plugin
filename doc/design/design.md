# aeps-llm-wiki-plugin — Design

> **状态**:已冻结(v0.1.1,2026-09-06)
> **创建日期**:2026-09-06
> **作者**:zhigang.liu
> **上游**:[prd.md v0.4.1](./prd.md)(已冻结)
> **范围**:架构 / 边界 / 关键决策(实现步骤 / 测试用例 / CI / 部署 → `implement.md`)

## Change History

| 版本 | 日期 | 变更 |
|---|---|
| v0.1.0 | 2026-09-06 | 初版(396 行,commit `10e6ca3`):§1 架构总览 + §2 边界 + §3 数据契约(含 5 路径分流表)+ §4 脚本契约 + §5 Lint 实现(C1-C20)+ §6 Source 骨架生成 + §7 关键决策(不重转 / 原生优先 / 幂等 / Gating / 路径 B / qmd 阈值)+ §8 风险 + §9 引用。同批配合 PRD v0.4.0 二轮瘦身 |
| v0.1.0 (post-freeze edit) | 2026-09-06 | 上游引用 v0.3.0 → v0.4.0(对齐 PRD 冻结版本号) |
| v0.1.1 | 2026-09-06 | §1.2 表底补 `knowledge/` 4 顶层索引 + 18 叶子目录注;§3.2 路径 2 注释明确 PDF 原生优先 / 失败回退 anydoc(对齐 PRD AC-9 G10 重写);上游引用 PRD v0.4.0 → v0.4.1 |

---

## 1. 架构总览

### 1.1 组件图

```
┌──────────────────────────────────────────────────────────────────┐
│ Claude Code (Host)                                                │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ /aeps-llm-wiki-{init,ingest,query,lint,synthesize}       │    │
│  │  └─→ 读 schema/schema.md (Agent 工作流入口)              │    │
│  │  └─→ 调 scripts/*.js (单次运行,即跑即退)               │    │
│  │  └─→ LLM 自驱步骤 (SKILL.md 描述)                      │    │
│  └──────────────────────────────────────────────────────────┘    │
└────────────┬──────────────────────────────────┬──────────────────┘
             │                                  │
             ▼                                  ▼
   ┌──────────────────┐              ┌────────────────────────┐
   │ scripts/*.js     │              │ SKILL.md (Claude Code   │
   │ (Node.js 单栈)   │              │  内 SKILL 入口)         │
   │                  │              └────────────────────────┘
   │ - gen-page.js    │
   │ - aggregate-idx  │              ┌────────────────────────┐
   │ - convert-to-md  │◄────────────►│ templates/page-*.md    │
   │ - check-qmd      │              │ schema/*.md            │
   │ - safe-mv.py?    │              │ (随 plugin 走)         │
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
   │ Obsidian (用户本地 vault)                                  │
   │  直接打开 knowledge/ 目录,无需任何映射                    │
   └──────────────────────────────────────────────────────────┘
```

### 1.2 6 顶层目录职责

| 目录 | 职责 | 写入者 | 时序 |
|---|---|---|---|
| `inbox/` | 暂存入口(G7 唯一入口) | 用户(手工拖入) | init 创建 + 每次 ingest 后清空 |
| `raw/{subdir}/` | 已归档不可变层 | ingest(safe-mv.py) | 文档生成后只增不改 |
| `scripts/` | plugin 维护的单次运行脚本 | init 全量覆盖 | 由 plugin 升级时增量补建 |
| `templates/` | 页面模板源 + 字典副本 | init 按需同步 | 用户不动 |
| `schema/` | frontmatter 契约层 | init 全量覆盖 | Agent 工作流入口 |
| `knowledge/` | LLM 维护的知识层 | ingest / query / synthesize / lint | 双向:用户手写 + LLM 自动 |

> `knowledge/` 根下含 **4 件顶层索引**(`index.md` / `overview.md` / `glossary.md` / `log.md`,均由 init 首次创建 + 增量聚合脚本维护)+ **18 叶子存储目录**(`sources/` + 7 `entities/{子类}/` + 7 `concepts/{子类}/` + `analyses/` + `comparisons/` + `syntheses/`,算术 `1 + 7 + 7 + 1 + 1 + 1 = 18`);每个叶子目录预建 `.gitkeep`,子目录 ↔ `type` 1:1 绑死(详见 PRD §6.1 + §4.1 流程表步骤 6)。

### 1.3 数据流

**Ingest**:`inbox/{file}` → (5 路径分流) → `raw/{subdir}/{file}` + `.converted.md` → `knowledge/sources/{slug}.md` + 抽取 `entities/{...}/{slug}.md` / `concepts/{...}/{slug}.md` → `index.md` 聚合

**Query**:`{question}` → (Intent 路由) → (4 跳扫描:index → frontmatter → wikilink → glossary+log) → (gating 判定) → 回答 + 可选 `analyses/{ts}-{slug}.md`

**Lint**:`knowledge/**/*.md` → (12 条规则) → FAIL/WARN 报告;`--fix` 模式按确定性 / 语义级分流

**Synthesize**:`{topic}` → (范围扫描) → `syntheses/{topic-slug}.md`(常驻,不带时间戳)

---

## 2. 边界 & 不做什么

### 2.1 Plugin 不做什么(同 PRD §2.2,本文不重复展开)

引用 PRD §2.2:版本管理 / RAG 向量 / 自动监控文件变动 / Claude Code 之外的兼容 / 内置 marketplace 配置。

### 2.2 与三大范式的边界

| 范式 | 边界 |
|---|---|
| **OKF v0.2** | plugin 输出严格 OKF 兼容;plugin 扩展字段按 OKF 未知字段忽略规则生效;**不发明** OKF 未定义的结构性字段(尤其 `links:`) |
| **Karpathy LLM Wiki** | 复用 `wiki/`(对应 `knowledge/`) + `raw/` 两层结构 + `index.md` / `log.md`;**不复用** `wiki/CLAUDE.md`(plugin 自带 CLAUDE.md 受控区块) |
| **Obsidian** | `knowledge/` 直接作 vault;`[[wikilink]]` 主推,标准 markdown 链接降级兼容;tag 走 frontmatter YAML list;**不做** Obsidian 插件 / .obsidian 配置生成 |

---

## 3. 数据契约

### 3.1 frontmatter 字段总览

OKF v0.2 原生字段:`type` (必填) / `id` / `title` / `summary` / `tags` / `generated` / `verified` / `sources` / `status` / `stale_after` / `resource` 等 —— 详见 `doc/schema/frontmatter-spec.md`。

**Plugin 扩展字段**(OKF reader 按未知字段忽略):

| 字段 | 类型 | 适用 type | 含义 |
|---|---|---|---|
| `format` | string | source | 原文件扩展名(小写) |
| `converter` | string \| null | source | 实际走过的路径:`null` / `claude-native` / `anydoc` / `paddleocr` / `docling` |
| `native_text` | bool | source | 是否实质等价于纯文本 |
| `converted_path` | string \| null | source | md 副本相对 `knowledge/` 的路径(仅 `anydoc` / `paddleocr` / `docling` 时非 null) |
| `sources_used` | string[] | analysis | 本次回答参考的 wiki 页相对路径列表 |
| `sources_count` | int | synthesis / analysis | 引用页数 |
| `answer_to` | string | analysis | 原 query 问句 |
| `generated_by` | string | analysis | `agent: producer/aeps-llm-wiki-plugin/{version}` |
| `aliases` | string[] | 全部 | Obsidian 别名解析 |

**不发明 `links:`**(对齐 OKF §5);**不发明 `_converted/` 子目录**(保持 raw/ 子目录语义单一)。

### 3.2 5 路径分流(扩展名 → frontmatter + 行为)

**第一原则**:原生多模态优先 —— 先让 Claude Code 直接读,能读 → 路径 1 / 2 结束;不能 → 降级路径 3 / 4。

**PDF 专属回退契约**(对齐 PRD AC-9 G10 v0.4.1):

- SKILL.md 在 ingest 步骤 0 对每个 `.pdf` 动态探测 Claude Code 原生 PDF reader 可用性,**绝不**"为保险先生成 `.converted.md`"
- 原生可读 → 路径 2 结束:`converter: claude-native` + `native_text: true` + `converted_path: null`,文件直迁 `raw/{subdir}/`
- 原生失败(双栏 / 扫描 / 加密 / 表格错位)→ 路径 3 回退:`converter: anydoc` + `native_text: false` + `converted_path` 指向 md 副本,**原文件与 `.converted.md` 同一子目录共存**
- AC-9(G10) 验收按"原生优先 / 失败回退"二选一,**不**强制锁死 anydoc

| 路径 | 触发扩展名 | converter | native_text | converted_path | 行为 |
|---|---|---|---|---|---|
| 0 | `.ppt` / `.doc` / `.xls`(老格式) | (转换后回到 1/2/3) | — | — | LibreOffice headless → 现代格式;失败提示装 LibreOffice |
| 1 | `.md` / `.markdown` / `.rst` / `.txt` / `.csv` / `.json` / `.yaml` / `.yml` / `.xml` / `.html` / `.htm` | `null` | `true` | `null` | SKILL.md 直接读全文,不生成副本 |
| 2 | `.pdf` 等 Claude Code 原生可读 | `claude-native` | `true` | `null` | Claude Code 直接读;失败(常见:双栏 / 扫描 / 加密)→ 回退路径 3 |
| 3 | `.pptx` / `.docx` / `.xlsx` / `.pdf`(LLM 不可读) / `.html` | `anydoc` 或 `docling` | `false` | md 副本路径 | `.pptx/.docx/.xlsx → docling`;`.pdf → anydoc`(中文双栏优);复杂版 → `docling` |
| 4 | `.png` / `.jpg` / `.jpeg` / `.bmp` / `.tiff` | `paddleocr` 或 `docling` | `false` | md 副本路径 | 表格截图走 `docling --layout`;否则 `paddleocr` |

**依赖**:
- `@firecrawl/anydoc` —— 路径 3 PDF / HTML 强依赖
- Node 版 PaddleOCR(`@arcships/light-ocr` 等候选)—— 路径 4 可选,未装 → FAIL 不降级 Python(G6)
- LibreOffice —— 路径 0 可选,未装 → 提示用户装,不静默降级
- 路径 1 / 2 **不需要任何转换库**

**docling 与 PaddleOCR 的协同**:docling 内置 PaddleOCR,通过 `append_ocr_quotes` 对每张抽出的图自动 OCR;docling 已在路径 3 处理 PPTX / DOCX / XLSX 时,抽出的图不再二次走独立 PaddleOCR 脚本(避免重复)。

**Claude Code 原生能力边界**:**不写死清单** —— SKILL.md 在路径 2 阶段动态探测;Claude Code 新版本新增可识别类型自动享受路径 2 优化;反之移除 → 自动降级路径 3。

### 3.3 OKF 兼容性约束

- `type` 必填;所有 frontmatter 字段 OKF 工具可读
- plugin 扩展字段命名无前缀(OKF reader 按未知字段忽略即可)
- 正文 `[[wikilink]]` 在 OKF reader 视为正文文本(OKF §6.1 "MAY standard markdown link" 未禁止其他)
- **不发明** `links:` / `_converted/` 等结构性字段

---

## 4. 脚本契约

### 4.1 职责分层(硬约束)

| 阶段 | 工具 | 职责 |
|---|---|---|
| 骨架生成 | 确定性脚本(Node.js) | 读 `templates/page-{type}.md` → 按扩展名填 frontmatter → 输出 `knowledge/{...}/{slug}.md`,正文留占位 + 末尾自动追加 `## 维护说明` |
| 内容生成 | LLM(SKILL.md 调) | 仅替换占位段;**不改** frontmatter 字段值 / H2 顺序 / 维护说明尾巴 |
| 聚合索引 | 确定性脚本(Node.js) | 扫 `knowledge/**/*.md` → 按 type + 子类聚合 → 重建 `index.md` / `overview.md` / `glossary.md` |
| LLM 抽取 / 判定 | LLM | 语义任务:从源文件抽取 entity / concept + 选 7 子类 + 6 轴 tag + raw 子目录 |

**为什么这样分**:
- 字段值由扩展名决定(`converter` 5 取值 / `native_text` 二值 / `converted_path` null/非 null) → 脚本 `switch(ext)` 100% 正确,LLM 偶有误填
- `## 维护说明` 区块含 5 路径分流表 + 字段一致性 lint 表,**每次重写会漂** → 脚本生成稳定
- `index.md` 按 type + 子类聚合是纯机械扫,模型做会编
- 正文内容是 plugin 的核心价值("LLM 读源,人做策展") → 脚本写不出来

### 4.2 脚本接口

**`gen-page.js`**:

```
scripts/gen-page.js --type {type} --slug {slug}
                    [--ext {ext}]
                    [--converter {auto|claude-native|anydoc|paddleocr|docling|null}]
                    [--subdir {raw_subdir}]
                    [--dry-run]
```

输出:`knowledge/{...}/{slug}.md`,YAML frontmatter + H2 顺序来自模板;若模板缺该 `type` → exit 1。

**`aggregate-index.js`**:

```
scripts/aggregate-index.js [--knowledge-dir ./knowledge]
```

- 输出**幂等**:同一 `knowledge/` 状态连续跑两次产物相同(增量更新按 mtime)
- `## Sources` 分组规则:按 frontmatter `resource` 路径解析的 `raw/{subdir}/` 分组;子目录名去掉 `\d+_` 编号前缀;每条用 `[[wikilink|alias]]`;行末直接展示 `status` + `tags`;无法解析 resource 路径的归到 `### 其他`
- **不发明新字段**,复用 frontmatter 已有字段

**`convert-to-md.js`**(统一入口,按扩展名分流):

```
scripts/convert-to-md.js --file {path} [--batch {json}] [--emit-to {dir}]
```

- 单文件模式:stdout 输出 md 文本(向后兼容)
- 批量模式(`--batch temp/inbox-batch.json --emit-to temp/`):把产物落到指定目录(供后续 mv 到 raw/)

**`check-qmd.js`**(Node.js 单次脚本,探查 qmd 可用性):

```
scripts/check-qmd.js
```

跑 `qmd --version`,输出可用性状态供 query skill 决策。

### 4.3 SKILL.md 调用顺序(实现期固定)

```
ingest / query / synthesize 流程必须是:
  脚本出骨架 → LLM 填正文 → 脚本聚合索引 → lint 校验
```

**SKILL.md 硬约束**:
- LLM **只被允许改 H2 之间的段落内容**
- **不允许** 改 frontmatter 任何字段值
- **不允许** 删/增 H2
- **不允许** 改 `## 维护说明` 区块

由 lint C17 强制。

### 4.4 安全与依赖

- 两个核心脚本**不依赖任何 LLM API**(Node.js 单栈,纯文件系统 + YAML 解析)
- `scripts/package.json` 写依赖清单:`@firecrawl/anydoc` 强依赖;Node 版 PaddleOCR 可选;qmd **单独探查,不计入依赖清单**
- 强依赖未装 → 提示并退出
- OCR 可选依赖未装 → 路径 3 / 4 遇扫描页 / 图片 OCR FAIL,不自动降级 Python(G6)
- 路径 1 / 2 **不需要任何转换库**

---

## 5. Lint 规则实现

12 条规则(`C1-C8` + `C17-C20`)。规则编号在历史 PRD 中跨版本演化,本文统一为 C1-C20,具体编号规则实现期定。

### 5.1 规则分类

| 级别 | 规则 | 行为 |
|---|---|---|
| FAIL | C1 frontmatter 必填(OKF + plugin 扩展) | 必填字段缺失 → FAIL |
| FAIL | C2 `## 摘要` / `## Summary` 残留 | 长摘要走 frontmatter `summary`;残留 → FAIL |
| FAIL | C3 sources 3 节骨架 | 必含 `## 重点摘录` / `## 我的思考` / `## 总结:最有收获的一句话`,任一缺失 → FAIL |
| FAIL | C4 analyses 3 节专属骨架 | 必含 `## 方案推演 / 架构分析` / `## 关联溯源` / `## 总结:最有收获的一句话`,任一缺失 → FAIL |
| FAIL | C5 comparison 必填 `sources` | 否则 FAIL |
| FAIL | C7 analysis `sources_used` 路径解析 | 每条必须解析到真实 `knowledge/**/*.md`,否则 FAIL |
| FAIL | C17 模板一致性 | `## 维护说明` + frontmatter + H2 顺序是否被 LLM 改动(比对 `gen-page.js` 模板),差异 → FAIL |
| FAIL | C18 原生 + 副本矛盾 | source 页「LLM 原生能读 + `converted_path` 非 null」组合(典型:`converter: claude-native` + `converted_path` 非 null)→ FAIL |
| WARN | C6 synthesis `sources_count < 3` | 避免空综合 |
| WARN | C8 analysis `## 关联溯源` 末行 `> 引用:` 与 `sources_used` Set 比对 | 不一致 WARN |
| WARN | C19 降级日志 | 走路径 3 / 路径 4 但无降级日志 → WARN |
| 软约束 | C20 source 页自由追加节 | 只校验 H2 存在性,不校验命名 / 数量 / 顺序;溯源自检报告输出,**不 FAIL** 来源不足(软约束 + 用户复核) |

### 5.2 孤儿 / 矛盾 / 陈旧 / 漏链 / 命名飘(无编号,沿用 lint 实现)

| 规则 | 行为 |
|---|---|
| 孤儿页 | 扫出入链接无 → 孤儿 |
| 矛盾 | 两页对同一事实不同说法 → 矛盾(LLM 判定) |
| 陈旧页 | `stale_after` 已填且过期 → 陈旧;**未填 `stale_after` 一律静默跳过,不报陈旧、不 WARN** |
| 漏链 | 正文反复出现但未链接术语 → 漏链 |
| 命名飘 | 子目录 / 页面名相似(Levenshtein ≤ 2 / 前缀差异 / 同义拼写)→ 提示 |

### 5.3 `--fix` 分流

**确定性结构修复**(直接 patch + `log.md` 追加 `**LintFix**`):
- frontmatter 字段缺失 → 补占位值 + WARN
- frontmatter 字段类型错位 → 强转
- `## 摘要` / `## Summary` 残留 → 删除并保留内容到 frontmatter `summary`
- sources / analyses 缺 3 节骨架 H2 → 文件末尾追加占位 H2
- 标准 markdown 链接残留(主推 wikilink)→ 转 `[[wikilink]]`

**语义级问题**(仅出**提案**等用户确认):
- 矛盾 / 命名飘合并 / 漏链 / 陈旧页处理

**不应**:无 `--fix` 时静默修改文件。

---

## 6. Source 页骨架生成

### 6.1 整体结构

```
# 标题
## [自由追加节 0..n 个]      ← LLM 自主决定文章独特结构;强制溯源(忠于原文)
## 重点摘录                   ← 必选,强制溯源,3-5 条要点
## 我的思考                   ← 必选,LLM 解读,不需要溯源
## 总结:最有收获的一句话      ← 必选,LLM 解读,≤ 50 字
## 相关页面(Related Pages)   ← 脚本自动,Entities/Concepts 分组
## 维护说明                   ← 脚本自动
```

### 6.2 强制溯源范围(关键边界)

| 节 | 强制溯源? | 备注 |
|---|---|---|
| 自由追加节(在 `## 重点摘录` 之前) | ✅ 必须忠于原文 | 不强制节名;演讲 / 标准 / 白皮书 / 论文类常见节名仅举例 |
| `## 重点摘录` | ✅ 必须忠于原文 | 3-5 条要点 |
| `## 我的思考` / `## 总结:最有收获的一句话` | ❌ LLM 解读产出 | 原本就不来自源文件 |

### 6.3 来源不足自检

LLM 写完 `## 重点摘录` + 自由追加节后,**必须**对每条断言自检能否在源文件找到依据:

- 找到 → 通过
- **无法溯源 → 显式标注 `[来源不足,需人工复核]`**(不要静默删除、不要悄悄改写)
- `## 我的思考` / `## 总结` **不参与**溯源自检

### 6.4 lint C20 联动

- 机械部分(脚本可执行):扫 source 页 `## 维护说明` 之前所有 H2,标记 `非 3 节必选 H2` 为「LLM 自由追加节」;**只校验 H2 存在性,不校验命名 / 数量 / 顺序**
- 软约束部分(LLM + 用户协同):机械 lint 跑完后,SKILL.md 输出 `**重点摘录 / 自由追加节 溯源自检报告**`,列出每节、每条断言,提示 LLM / 用户复核
- FAIL / WARN:机械部分 → FAIL(沿用既有规则);软约束部分 → **不 FAIL**,仅在自检报告里输出,等用户复核(Q7 死循环防护原则:`--fix` 不自动改写用户认可的内容)

### 6.5 占位指引

`templates/page-source.md` 在 `## 重点摘录` 之前以 blockquote 段(非 H2)写"LLM 阅读须知",包含上述规则;脚本 `gen-page.js` 解析 H2 时不识别该 blockquote,不影响骨架顺序。

---

## 7. 关键决策与不重转策略

### 7.1 不重转(对齐 PRD G10)

- raw/ 是已归档不可变层(G7),`converted_path` 一旦写入不可在原位修改
- 不提供批量重转 skill(避免 raw/ 不可变层被绕过)
- 需重转时:用户把文件 `cp` 回 `inbox/` → 走标准 ingest 流程
- raw/ 下已存在同名文件 → **强制拍板**:`[y]` 覆盖(先备份到 `temp/raw_backup_{hash}/` + `os.replace()` 原子替换)/ `[n]` 跳过 / `[d]` 仅删旧副本
- 覆盖范围:仅 `{file}` + `{file}.converted.md` 两个目标,不动同 subdir 其他文件;不动 frontmatter `updated` 字段 + 文件 mtime(Q7 死循环防护)

### 7.2 原生多模态优先

- Claude Code 原生能力(Current PDF 读取 / Vision 多模态)对版面 / 表格 / 图文位置 / 语义的理解一定强于第三方 OCR / 版面还原工具
- **第一步永远是探测**:SKILL.md 对 inbox 每个文件,先让 Claude Code 直接读;能读 → 路径 1 / 2 直接结束,**不**生成 `.converted.md`,**不**调 `convert-to-md.py`,**不**消耗 OCR / 转换依赖
- 部分能读(如 PDF 文本能读但图不能解析)→ 优先路径 2 结束 + 把图作为附件记录到 source 页 `## 重点摘录` 末尾,**不**为了图强行走路径 3 / 4
- 完全不能读 → 才走路径 3 / 4
- **绝不**「为了保险先生成 .converted.md 再说」:这是浪费 + 噪音 + 跟 G6「不发明常驻运行时」哲学冲突

### 7.3 幂等策略

- init 二态流程:首次启用 → 全栈建好;已存在项目 → 幂等再入(由步骤 0 分支闸口判定)
- 文件同步策略表(详见 PRD §4.1):每个文件首次 init 与 re-run 行为明确
- `aggregate-index.js` 输出幂等(增量更新按 mtime)
- source 页 / entity / concept 页相关区块(`## 相关页面` / `## 来源资料`)**每次 ingest 完全重建**,不保留人工条目(Q5)
- `CLAUDE.md` 受控区块幂等管理(详见 PRD §4.1)

### 7.4 Gating(G11 落档)

query skill 落档询问触发条件(详见 PRD §4.3):
- 4 触发条件任一命中 + 4 不触发条件全不命中 → 询问
- 否则跳过
- 防止 Exact 查证型 spam 落档

### 7.5 路径 B 计数器(comparison 累积)

- 路径 B(query 累计 ≥ 3 次"X vs Y")触发常驻 comparison 页
- 计数器持久化到 `knowledge/.aeps-state/comparison-counter.json`
- **计数仅在用户拍板建页后才更新**(避免噪声查询污染计数)

### 7.6 qmd 阈值升级条款

| wiki 规模 | 引擎 |
|---|---|
| < 500 页 | 纯 `index.md` + 4 跳扫描,不调 qmd |
| 500~1000 页 | 优先 qmd;未装 → 提示用户装,降级 `index.md` |
| **> 1000 页** | **必须** qmd;未装 → 报错退出 |

**唯一阈值升级条款**:当 `knowledge/` 目录页数 N ≥ 1000 时,qmd 临时升级为强依赖,query skill 直接报错退出;其余规模下 qmd 仍为可选。

阈值常量:`QUERY_INDEX_THRESHOLD = 500` / `QUERY_QMD_REQUIRED_THRESHOLD = 1000`。

---

## 8. 风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| OKF v0.x 演进,字段变化 | 扩展字段将来要适配 | 只锁 v0.2 已定义字段;扩展字段显式标注 plugin 扩展,OKF 工具忽略 |
| LLM 跑偏(漏抽 / 错判 entity vs concept / 错选 14 子类) | wiki 质量下降 | lint 兜底识别目录名 ↔ type 不一致;`concept-entities-spec.md` 给判定示例 |
| 老格式 `.ppt/.doc/.xls` | docling 不支持,路径 3 失败 | 路径 0 LibreOffice headless 预归一化;未装 → 提示用户 |
| 比较 / 综合页噪声 | `comparisons/` `syntheses/` 膨胀 | 必须用户拍板;`sources_count` 最小门槛 C6 |
| `sources_used` 填写过宽 | 引用列表污染 | C7 + C8 严格校验;`--fix` 不动 updated + mtime(Q7) |
| 老文件 / 二进制无法解析 | query 失败 | source 页 `## 重点摘录` + `converted_path`;query 通过 `converted_path` 直读副本 |
| 降级路径 3/4 静默发生 | 用户不知情 | C19 校验降级日志必出 |

实现期才暴露的额外风险(测试 / 性能 / 部署 / CI)见 `implement.md`。

---

## 9. 引用

- [prd.md v0.4.0](./prd.md)—— 已冻结,本文档上游
- [frontmatter-spec.md](../schema/frontmatter-spec.md)—— frontmatter 字段规范人读权威
- [frontmatter.schema.json](../schema/frontmatter.schema.json)—— 机器读,跟随 spec 对齐
- [schema.md](../schema/schema.md)—— Agent 工作流入口
- [concept-entities-spec.md](../template/concept-entities-spec.md)—— 14 子类判定示例
- [rawdir-spec.md](../template/rawdir-spec.md)—— 15 类 raw 子目录字典
- [tag-spec.md](../template/tag-spec.md)—— 6 轴 tag 字典
- `doc/input/google-OKF/OKF-SPEC.md`—— OKF v0.2 规范原文
- `doc/input/karpathy-llm-wiki/karpathy-llm-wiki.en.md`—— Karpathy LLM Wiki 理念
- `reference/balukosuri__llm-wiki-karpathy/CLAUDE.md`—— Karpathy 模式 Agent 操作手册范本

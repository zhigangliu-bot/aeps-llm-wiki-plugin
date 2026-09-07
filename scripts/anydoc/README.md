# anydoc / docling 转 md

把二进制 office / 文档文件转成 markdown,**只做原文 → md 的转换**,不加任何 frontmatter。frontmatter(`type` / `tags` / `created` 等 wiki 元数据)由 `ingest` skill 在文件落入 `inbox/` 后自动补。

按扩展名分两个脚本:

| 扩展名 | 脚本 | 引擎 | 速度 / 质量 |
|---|---|---|---|
| **.pdf** | `anydoc_pdf_to_md.js` | `@firecrawl/anydoc` | 0.x s / 108 行级(快) |
| **.docx / .pptx / .xlsx** | `docling_to_md.py` | IBM Docling | 几秒~几十秒 / 完整版面 + 抽图(精) |
| .pdf(精) | `docling_to_md.py` 也接受 PDF | Docling | 11 页 ~82s,18 页 10+ 分钟(慢) |

> **PDF 默认走 anydoc**(快);用户明确需要版面/抽图质量时改跑 `docling_to_md.py`。

## 工作流位置

```
                   ┌──────────────── 路径 3 ────────────────┐
                   │                                       │
   inbox/ ──►      │  .pdf   ────► anydoc_pdf_to_md.js     │
                   │           或    docling_to_md.py (精) │
                   │                                       │
                   │  .docx  ────► docling_to_md.py         │
                   │  .pptx  ────► docling_to_md.py         │
                   │  .xlsx  ────► docling_to_md.py         │
                   └───────────────────────────────────────┘
                                │
                                ▼  手动 mv 到 <vault>/inbox/
                   wiki-plugin ingest skill 自动补 frontmatter
                   + 归档到 knowledge/sources/
                   Obsidian vault 直接可看
```

## 在 wiki-plugin 4 路径分流里的位置

PRD §4.2 定义的文件读取策略:

| 路径 | 触发条件 | converter 字段 | 谁负责 |
|---|---|---|---|
| 路径 1 | `.md`/`.txt`/`.html` 等纯文本 | `null` | 直接读 |
| 路径 2 | `.pdf`/`.docx` 等二进制 | `claude-native` | Claude Code 原生识别 |
| **路径 3** | Claude Code 不能识别 / 强制外部转 | **`anydoc` / `docling`** ← 本工具 | **本目录脚本** |
| 路径 4 | 图片 | `paddleocr` | `scripts/ocr/ocr_to_md.py` |

**路径 3 是本工具的用途**:Claude Code 拿不到原文件 / 识别失败时,降级走这里。

---

## 一、anydoc 路径(PDF,快)

### 1.1 环境

- Node.js ≥ 20(`package.json` 锁了 `engines.node`)
- `@firecrawl/anydoc`(Node 库)
- 输入格式:`.pdf`
- 输出:UTF-8 编码 markdown(仅正文)

### 1.2 安装

```bash
cd <repo>/aeps-llm-wiki-plugin/scripts
npm install   # 装 @firecrawl/anydoc / ajv / js-yaml
```

### 1.3 使用

```bash
# 默认输出到 <input>.md(同目录)
node anydoc/anydoc_pdf_to_md.js doc.pdf

# 指定输出
node anydoc/anydoc_pdf_to_md.js doc.pdf -o out/my.md

# 批量
for %f in (inbox\*.pdf) do node anydoc/anydoc_pdf_to_md.js "%f"
```

**只接受 .pdf**:传 `.docx` / `.xlsx` / `.pptx` 会报错退出(2)。这些格式请走 §二 的 docling 路径。

### 1.4 局限

- 输出**没有图片引用**——纯文本 PDF 转 md 后图没了
- 表格/标题层级还原**比 docling 差**(实测 Vector 11 页英文 PDF:anydoc 0.25s / 108 行但表格乱,docling 82s / 13180 字符含图)
- 扫描件 PDF(anydoc 跑不动)→ 走 `../ocr/pdf_to_ocr_to_md.py`

---

## 二、docling 路径(docx / pptx / xlsx,精)

### 2.1 环境

- Python 3.11
- `docling`(pip 包,自带 RapidOCR + torch)
- 输入格式:`.docx` / `.pptx` / `.xlsx`(`.pdf` 也接受但慢)
- 输出:UTF-8 编码 markdown + `<stem>_media/` 内嵌图

### 2.2 安装

```bash
pip install docling
# 首次跑自动从 huggingface / paddleocr 站点下模型(~500 MB),
# 缓存到 ~/.cache/huggingface/ 和 ~/.paddleocr/
```

### 2.3 使用

```bash
# 默认输出到 <input>.md + <input>_media/(同目录)
python anydoc/docling_to_md.py foo.docx

# 指定输出
python anydoc/docling_to_md.py foo.pptx -o out/my.md

# PDF(慢,会打 stderr 警告)
python anydoc/docling_to_md.py foo.pdf
# [WARN] docling_to_md.py: PDF 转换慢(11 页 ~82s,18 页 10+ 分钟)。
#        纯文本 PDF 建议先试 anydoc_pdf_to_md.js(<1s)。
```

### 2.4 行为

1. docling 转 md(默认 PLACEHOLDER 模式)
2. 抽 `result.document.pictures` 到 `<stem>_media/image_NN.<ext>`(顺序编号)
4. 把 `<!-- image -->` 按出现顺序替换为 `![](<stem>_media/image_NN.<ext>)`
5. 对每张图调 `../ocr/ocr_to_md.py --json`,avg_confidence ≥ 0.5 → 在引用下一行贴 `> ` OCR 摘要
6. 写 `.md`(无 frontmatter)

**抽图兼容两种 docling 类型**:
- `DoclingImage`:`.data` 直接拿 bytes
- `ImageRef`(docx 常见):`.uri` 是 `data:<mime>;base64,<b64>`,解码后半部分

### 2.5 性能参考(实测,CPU)

| 文件 | 耗时 | 字符数 | 抽图数 |
|---|---|---|---|
| S32G docx (1.2 MB, 12 图) | ~12-92s | 16-19k | 10 引用 |
| edge AI pptx (4.3 MB, 23 图) | ~9-166s | 10-11k | 23 引用 |
| QNX xlsx (392 KB) | ~25s | 14k | 2 |
| Vector PDF (771 KB, 11 页英文) | ~82s | 13k | 11 |
| Andes PDF (3.9 MB, 18 页) | >10 分钟(超时) | — | — |

> OCR 子进程跑完会显著拖慢(每张图 ~3-8s);如果不需要 OCR 摘要,可手动禁用 `ocr_to_md.py` 子进程。

### 2.6 局限

- **PDF 太慢**(见上表)→ 默认走 anydoc
- 模型首次加载 ~30s
- 嵌字图 vs 装饰图按置信度门(0.5)区分,不精细

---

## 三、入库到 wiki(两个脚本相同)

**默认行为**:`.md` 落在原文件同目录(例:`D:\资料\foo.pdf` → `D:\资料\foo.md`)。这是中间产物,**不会自动送进 wiki**。

下一步:把 `.md` 手动 `mv`(或复制)进 `<vault>/inbox/`,wiki-plugin `ingest` skill 会自动识别为 source 并归档到 `knowledge/sources/`,同时把原文件 + `.md` 副本一起挪到 `raw/{subdir}/`(PRD §4.2 G10)。

直接输出到 inbox:`-o inbox/foo.md`。

---

## 四、和 PaddleOCR 工具的关系

```
                ┌──────────── 路径 3 ────────────┐
                │                                │
   inbox/ ──►   │ .pdf ─► anydoc_pdf_to_md.js   │
                │         或 docling_to_md.py    │
                │                                │
                │ .docx/.pptx/.xlsx ─► docling   │
                └────────────────────────────────┘
                              │
                              ▼
                   knowledge/sources/*.md
```

- 图片 OCR:`scripts/ocr/ocr_to_md.py`(纯图片)
- 扫描件 PDF OCR:`scripts/ocr/pdf_to_ocr_to_md.py`(anydoc 跑不动时降级)
- 扫描件 PPTX OCR:`scripts/ocr/pptx_to_ocr_to_md.py`(docling 跑不动时降级)
- **所有脚本都不写 frontmatter**——由 ingest skill 入库时统一补

---

## 五、常见问题

### Q1: `Error: Cannot find module '@firecrawl/anydoc'`

**原因**:`npm install` 没在 `scripts/` 下跑。
**解决**:

```bash
cd <repo>/aeps-llm-wiki-plugin/scripts
npm install
```

### Q2: docling 报 `ModuleNotFoundError: No module named 'docling'`

**原因**:Python 环境没装 docling。
**解决**:`pip install docling`,注意用项目要求的 Python 3.11(embeddable 也行)。

### Q3: docling PDF 跑了 10 分钟还没结果

正常。docling PDF 慢(见 §2.5 性能表)。**杀进程改走 anydoc**:`node anydoc_pdf_to_md.js f.pdf`。

### Q4: docling 抽出的图 OCR 文本混乱

avg_confidence < 0.5 已被门过滤掉,但有些图置信度高但**识别错**(复杂版面 / 表格)。这些靠 PaddleOCR 模型本身能力,本脚本不重 OCR。

### Q5: 为什么脚本不写 frontmatter?

按设计脚本只做"原文 → md"转换,frontmatter 是 wiki 元数据,由 `ingest` skill 在文件落 `inbox/` 后按规范补。这样脚本职责单一(转文本),入库职责单一(补元数据),互不耦合。

---

## 六、文件清单

| 文件 | 用途 |
|---|---|
| `anydoc_pdf_to_md.js` | PDF 转换(Node + anydoc,快) |
| `docling_to_md.py` | docx/pptx/xlsx/PDF 转换(Python + docling,精) |
| `README.md` | 本文档 |

---

## 七、许可

脚本以 Apache 2.0 发布。
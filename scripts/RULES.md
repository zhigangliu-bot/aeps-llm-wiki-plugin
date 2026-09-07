# RULES.md — 原生模型不支持时的工具选择策略

> **触发场景**:Claude Code / 其他 LLM 拿不到原文件、识别失败、或用户明确要求走本地转换工具时,按本文档分流到 `scripts/anydoc/` 或 `scripts/ocr/`。
>
> **第一原则(原生多模态优先)**:**SKILL.md 第一步永远是「探测 LLM 当前能不能直接读这个文件」**。能 → 直接结束,不消耗任何 OCR / 转换依赖。**原生支持多模态的 LLM 对文件的理解能力一定是最强的**,第三方 OCR / 版面还原工具在精度、保真度、上下文关联上永远输给 LLM 原生能力;**只在 LLM 真的无法识别时才降级**到下表的工具。这一条是 plugin 哲学,不是路径 2 的局部策略。
>
> **设计原则**:**版面完整度优先**(表格 / 标题 / 图文位置),**速度次之**;**中文 PDF 双栏**走 firecrawl/anydoc(唯一不超时的方案),**老格式**先 LibreOffice 预归一化。

---

## 1. 文档类型 → 工具矩阵

| 输入 | 第一选择 | 兜底 | 工具入口 | 实测耗时 |
|---|---|---|---|---|
| **`.pdf`** 普通单栏 ≤10 页 | firecrawl/anydoc | docling | `anydoc/anydoc_pdf_to_md.js` | < 2s |
| **`.pdf`** 双栏 / 复杂排版 / 含表格 | firecrawl/anydoc | docling(慢) | 同上 | anydoc < 2s,docling 可能 >25min |
| **`.pdf`** 扫描件(anydoc exit=3) | `pdftoppm` 转图 + PaddleOCR/RapidOCR | — | `ocr/pdf_to_ocr_to_md.py` | 5-15s/页 |
| **`.pptx`** 含图 | **docling** | ❌ 不用 anydoc(丢图) | `anydoc/docling_to_md.py` | < 1s(3 图),线性增长 |
| **`.docx`** 含表格 / 图 / 代码 | **docling** | — | `anydoc/docling_to_md.py` | 数秒 ~ 5min(64 图 TDA4) |
| **`.xlsx`** 多表 / 跨表 | docling | — | `anydoc/docling_to_md.py` | 历史 ~25s(13MB) |
| **`.ppt` / `.doc` / `.xls`** 老格式 | **LibreOffice 转现代格式** → docling | — | `soffice --headless --convert-to pptx` | 转几秒 + docling 几秒 |
| **`.jpg` / `.png` / `.jpeg` / `.bmp`** 手机截图 / 扫描件 | **PaddleOCR**(快) / **RapidOCR**(准) | docling(慢但出表格) | `ocr/ocr_to_md.py` / `ocr/rapidocr_to_md.py` | < 5s |
| **`.jpg` / `.png`** 复杂版面 / 海报 / 表格截图 | **docling** | PaddleOCR/RapidOCR | `anydoc/docling_to_md.py` | 首次 ~3min,稳态 ~10s |

---

## 2. OCR 引擎选择(PaddleOCR vs RapidOCR)

两者都是纯 OCR,都**不做版面还原** —— 输出纯文字流,表格由后处理还原。

| 引擎 | 模型 | 优势 | 何时用 |
|---|---|---|---|
| **PaddleOCR 2.7.3** | PP-OCRv4 mobile,中文优先 | 启动快,中文识别成熟 | 默认,中文为主 / 扫描件 |
| **RapidOCR 3.9.2** (docling 内置) | PP-OCRv6 small,中英 | 实测多识别 ~10% 内容,首字母 / 空格 / 标点更准 | 英文 / 特殊字体 / 准确度优先 |

**接口契约一致**:两者都接受 `--json` 输出 `{text, avg_confidence}`,`docling_to_md.py` 可一行切换。

**依赖现状**(实测 `C:\Python311` 环境):
- PaddleOCR: `paddlepaddle==2.6.2 + paddleocr==2.7.3 + numpy<2`
- RapidOCR: `rapidocr>=3.x + onnxruntime>=1.18 + protobuf>=4.25`
- 两个引擎 pip 警告冲突(protobuf 版本要求互斥),**实测回退到 protobuf 3.20.3 后可共存**;若后续冲突升级,把 RapidOCR 拆到独立 venv。

---

## 3. 决策流程(skill 调用时按此分流)

```
input file
  │
  ├─ ext ∈ {.ppt, .doc, .xls}?
  │    └─ yes → LibreOffice headless 转现代格式 → 进 docling
  │
  ├─ ext == .pdf?
  │    ├─ 试 firecrawl/anydoc
  │    │    ├─ exit=0 → 用 anydoc 输出(快,双栏 OK)
  │    │    └─ exit=3 → 扫描件,pdftoppm 转图 → PaddleOCR/RapidOCR
  │    └─ 用户明确要版面 / 抽图 / 图内 OCR → 改走 docling(慢)
  │
  ├─ ext ∈ {.pptx, .docx, .xlsx}?
  │    └─ → docling(自带版面 + 抽图 + 图内 OCR,一站式)
  │
  └─ ext ∈ {.jpg, .png, .jpeg, .bmp}?
       ├─ 是简单文字截图 / 扫描件 → PaddleOCR(默认) / RapidOCR(准确度优先)
       └─ 是表格截图 / 海报 / 复杂版面 → docling(出 markdown 表格)
```

---

## 4. docling 关键事实(踩过的坑)

- **支持格式**:`.docx / .pptx / .xlsx / .pdf`(以及单张图片直接喂也行)
- **不支持**:`.ppt / .doc / .xls`(要 LO 转)
- **首次跑会下 ~500MB 模型**(huggingface + paddleocr),缓存到 `~/.cache/huggingface/` 和 `~/.paddleocr/`
- **抽图路径**:用 `-o` 时 `media_dir` 跟随 `-o` 的输出目录(已修),产物 `<out>.md` + `<out>_media/`
- **图内 OCR 默认开启**:`append_ocr_quotes` 对每张抽出的图调 PaddleOCR,门限 `OCR_CONFIDENCE_THRESHOLD = 0.5`
- **超时基线**(CPU):单张图 5-15s;docx 64 图 ~5min;PDF 双栏 18 页 >25min(可 kill)

---

## 5. 工具链一图概览

```
图片源(pptx/docx 抽出图,或纯扫描件)
    ↓
┌─────────────────┬──────────────────────┐
   docling 路径    PaddleOCR/RapidOCR 路径
   (整篇文档)      (单张图)
   表格/标题/列表   纯文字流
   抽图 + 图内 OCR  快(<5s/图)
   <1s ~ 5min
```

---

## 6. 路径分流(对应 PRD §4.2 四路径)

| 路径 | 触发 | 工具 |
|---|---|---|
| 1 | LLM 原生读得了 | null(不转换) |
| 2 | LLM 原生能识别 | claude-native |
| 3 | 二进制 office / 普通 PDF | anydoc(快) / docling(精) |
| 4 | 纯图片 / 扫描件 | PaddleOCR / RapidOCR / docling(带版面) |

---

## 7. 实测样本(本 spike 跑过的)

| 样本 | 类型 | 最佳工具 | 产物大小 | 行数 |
|---|---|---|---|---|
| `Andes_Success Story & Partner Showcase.pdf` (双栏 18 页) | PDF 双栏 | **firecrawl/anydoc** | 38KB / 733 行 | < 2s |
| `TDA4调试方法与步骤.docx` (8MB, 64 图) | DOCX 复杂 | **docling** | 54KB / 2057 行 | ~5min(含 64 图 OCR) |
| `问题.pptx` (906KB, 3 图, TSN 协议) | PPTX | **docling** | 10KB / 180 行 | < 1s |
| `Catch(09-05-22-51-09).jpg` (对比表截图) | JPG 表格 | **docling**(出表格) vs PaddleOCR(70 行竖排) | 11KB / 111 行 vs 943B / 70 行 | docling 首次 3min,稳态 10s |

完整对比数据见 [`.trellis/workspace/zhigangliu-bot/research/ocr-layout-spike/REPORT.md`](../../.trellis/workspace/zhigangliu-bot/research/ocr-layout-spike/REPORT.md)。

---

## 8. 相关脚本清单

```
scripts/
├── anydoc/
│   ├── anydoc_pdf_to_md.js    # firecrawl/anydoc CLI 包装,只接 .pdf
│   ├── docling_to_md.py       # docling 主入口,接 office/pdf/图片
│   └── README.md
├── ocr/
│   ├── ocr_to_md.py           # PaddleOCR 入口,接单图
│   ├── rapidocr_to_md.py      # RapidOCR 入口,接口同 ocr_to_md.py
│   ├── pdf_to_ocr_to_md.py    # 扫描件 PDF → OCR
│   └── pptx_to_ocr_to_md.py   # 备用,PPTX 走 OCR fallback
├── RULES.md                   # ← 本文档
└── README.md                  # 安装 / 一次性配置
```

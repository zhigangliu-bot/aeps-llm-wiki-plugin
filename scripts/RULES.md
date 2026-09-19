# RULES.md — 原生模型不支持时的工具选择策略

> **change history**:
> - **2026-09-19(依赖收敛)** — 路径 3 全格式统一改走 **Microsoft MarkItDown**(pip 包),删除 `anydoc/`(firecrawl/anydoc + docling)与 `pyoffice/` 三条转换链;扫描件/图片仍走 `ocr/`(PaddleOCR/RapidOCR)。动机:依赖最小化(npm 2 个 + pip 2 个),消除 Windows 下 .cmd wrapper / poppler 一类环境坑。旧矩阵见 git history。

> **触发场景**:Claude Code / 其他 LLM 拿不到原文件、识别失败、或用户明确要求走本地转换工具时,按本文档分流到 `scripts/markitdown/` 或 `scripts/ocr/`。
>
> **第一原则(原生多模态优先)**:**SKILL.md 第一步永远是「探测 LLM 当前能不能直接读这个文件」**。能 → 直接结束,不消耗任何 OCR / 转换依赖。**原生支持多模态的 LLM 对文件的理解能力一定是最强的**;**只在 LLM 真的无法识别时才降级**到下表的工具。这一条是 plugin 哲学,不是路径 2 的局部策略。
>
> **设计原则**(2026-09-18 拍板):**依赖最小化优先** —— 单一转换器(MarkItDown)+ 单一 OCR(paddleocr);**老格式**先 LibreOffice 预归一化。

---

## 1. 文档类型 → 工具矩阵

| 输入 | 第一选择 | 兜底 | 工具入口 | 实测耗时 |
|---|---|---|---|---|
| **`.pdf`**(有文本层) | MarkItDown | — | `markitdown/markitdown_to_md.py` | < 3s |
| **`.pdf`** 扫描件(抽不出文本层,exit=3) | `pdftoppm` 转图 + PaddleOCR | — | `ocr/pdf_to_ocr_to_md.py` | 5-15s/页 |
| **`.pptx` / `.docx` / `.xlsx`** | MarkItDown | — | `markitdown/markitdown_to_md.py` | < 3s |
| **`.html` / `.htm`** | MarkItDown | — | 同上 | < 3s |
| **`.ppt` / `.doc` / `.xls`** 老格式 | LibreOffice 转现代格式 → MarkItDown | — | `soffice --headless --convert-to pptx` | 转几秒 + 转换几秒 |
| **`.jpg` / `.png` / `.jpeg` / `.bmp` / `.tiff`** 截图 / 扫描件 | **PaddleOCR**(快)/ **RapidOCR**(准) | — | `ocr/ocr_to_md.py` / `ocr/rapidocr_to_md.py` | < 5s |

---

## 2. OCR 引擎选择(PaddleOCR vs RapidOCR)

两者都是纯 OCR,都**不做版面还原** —— 输出纯文字流,表格由后处理还原。

| 引擎 | 模型 | 优势 | 何时用 |
|---|---|---|---|
| **PaddleOCR 2.7.3** | PP-OCRv4 mobile,中文优先 | 启动快,中文识别成熟 | 默认,中文为主 / 扫描件 |
| **RapidOCR 3.9.2** | PP-OCRv6 small,中英 | 实测多识别 ~10% 内容,首字母 / 空格 / 标点更准 | 英文 / 特殊字体 / 准确度优先 |

**接口契约一致**:两者都接受 `--json` 输出 `{text, avg_confidence}`,可一行切换。

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
  │    └─ yes → LibreOffice headless 转现代格式 → MarkItDown
  │
  ├─ ext == .pdf?
  │    ├─ MarkItDown(exit=0)→ 用输出
  │    └─ exit=3(抽不出文本层,扫描件)→ pdftoppm 转图 → PaddleOCR/RapidOCR
  │
  ├─ ext ∈ {.pptx, .docx, .xlsx, .html, .htm}?
  │    └─ → MarkItDown(唯一转换器,无降级链)
  │
  └─ ext ∈ {.jpg, .png, .jpeg, .bmp, .tiff}?
       └─ → PaddleOCR(默认)/ RapidOCR(准确度优先)
```

---

## 4. 路径分流(对应 PRD §4.2 四路径)

| 路径 | 触发 | 工具 |
|---|---|---|
| 1 | 纯文本,LLM 直接读 | null(不转换) |
| 2 | LLM 原生能识别(需 poppler;缺失自动降级路径 3) | claude-native |
| 3 | 二进制 office / 普通 PDF / html | markitdown |
| 4 | 纯图片 / 扫描件 | PaddleOCR / RapidOCR |

---

## 5. 相关脚本清单

```
scripts/
├── markitdown/
│   ├── markitdown_to_md.py    # Microsoft MarkItDown 包装,pdf/docx/pptx/xlsx/html 统一入口
│   └── (本目录无 README,用法见脚本头注释)
├── ocr/
│   ├── ocr_to_md.py           # PaddleOCR 入口,接单图
│   ├── rapidocr_to_md.py      # RapidOCR 入口,接口同 ocr_to_md.py
│   ├── pdf_to_ocr_to_md.py    # 扫描件 PDF → OCR
│   └── pptx_to_ocr_to_md.py   # 备用,PPTX 走 OCR fallback
├── RULES.md                   # ← 本文档
└── README.md                  # 安装 / 一次性配置
```

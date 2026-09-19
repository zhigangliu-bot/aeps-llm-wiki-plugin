# scripts/

wiki-plugin 的转换工具集。把 `inbox/` 里的非文本资料转成纯 markdown(不含 frontmatter),供 `ingest` skill 入库时统一补 wiki 元数据并归档到 `knowledge/sources/`。

> **change history**:
> - **2026-09-19(依赖收敛)** — 路径 3 全格式统一改走 **Microsoft MarkItDown**(pip 包 `markitdown/`),删除 `anydoc/` 与 `pyoffice/` 目录;依赖收敛为 npm 2 个(js-yaml / ajv)+ pip 2 个(markitdown / paddleocr)。旧工具链见 git history。

**职责分工**:脚本只做"原文 → md 文本",frontmatter(`type` / `tags` / `created` / `source_file` 等)由 `ingest` skill 在文件落 `inbox/` 后自动补。这样脚本职责单一(转文本),入库职责单一(补元数据)。

## 工具一览

| 子目录 | 用途 | 对应 PRD 路径 | 触发条件 |
|---|---|---|---|
| `markitdown/` | 二进制文档统一转 md | 路径 3 | `.pdf` / `.docx` / `.xlsx` / `.pptx` / `.html` |
| `ocr/` | 图片 OCR 转 md | 路径 4 | `.png` / `.jpg` / `.bmp` / `.tiff` |
| `ocr/pdf_to_ocr_to_md.py` | 扫描件 PDF OCR 转 md | 路径 4 | PDF 是扫描件 / 嵌图(markitdown 抽不出文本层时) |

PRD §4.2 定义了 4 路径分流:

| 路径 | converter | 谁负责 |
|---|---|---|
| 路径 1 | `null` | Claude Code 直接读 |
| 路径 2 | `claude-native` | Claude Code 原生识别 |
| 路径 3 | `markitdown` | 本目录 `markitdown/` |
| 路径 4 | `paddleocr` | 本目录 `ocr/` |

## 一、一次性安装

### 1. Python 工具(markitdown + paddleocr)

```bash
# 装 Python 3.11+(从 python.org 下,embeddable 免安装版也行)
# 然后:
pip install markitdown paddlepaddle==2.6.2 paddleocr==2.7.3 "numpy<2"
```

详细步骤见 [ocr/README.md](ocr/README.md)。

### 2. Node 工具(js-yaml / ajv)

```bash
# 装 Node.js ≥ 20(从 nodejs.org 下 LTS)
# 然后:
cd <repo>/aeps-llm-wiki-plugin/scripts
npm install
```

## 二、目录拷给用户的清单

把这个 `scripts/` 目录整目录(含 `node_modules/`)拷贝过去即可。如果不想带 node_modules(太大),就只拷源码,目标机器重跑 `npm install`。

`scripts/` 必须包含的:

- `package.json` + `package-lock.json`(锁定依赖版本)
- `markitdown/`(脚本)
- `ocr/`(脚本 + README)
- `node_modules/`(可选,也可 `npm install` 重装)

## 三、在另一台新机器上从零搭建

如果你 clone 了仓库,**scripts/ 下没有 node_modules/**(git 不跟),需要按下面顺序装齐。

### 1. 装 Python 3.11+(必需,markitdown / paddleocr 都靠它)

从 [python.org](https://www.python.org/) 下 Python 3.11 LTS,或用 embeddable 免安装版(Windows 用户见 [ocr/README.md §二](ocr/README.md#二一次性安装)):

```bash
python --version   # 应输出 Python 3.11.x
```

### 2. 装 Python 包(必需,markitdown / paddleocr)

```bash
pip install markitdown paddlepaddle==2.6.2 paddleocr==2.7.3 "numpy<2"
```

要点:

- `paddlepaddle==2.6.2`(避开 3.x onednn bug)
- `numpy<2`(避 ABI 不兼容)

### 3. 装 Node.js ≥ 20(必需,ingest 脚本)

`package.json` 的 `engines` 字段锁了 `node >= 20.0.0`。从 [nodejs.org](https://nodejs.org/) 下 LTS(当前 v22)安装:

```bash
node --version   # 应输出 v20.x 或更高
```

### 4. 装 npm 依赖(必需,js-yaml / ajv)

```bash
cd <repo>/aeps-llm-wiki-plugin/scripts
npm install      # 读 package.json + package-lock.json 装出 node_modules/
```

这一步装两个依赖:`js-yaml` + `ajv`。

**最少路径**(只跑路径 3 文档转换):只要 Python + `pip install markitdown`。
**完整路径**(含路径 4 图片 OCR):第 1-4 步全做。

> **poppler / LibreOffice**:扫描件 PDF 走 OCR 时需要 poppler(`pdftoppm`);老格式 `.ppt/.doc/.xls` 需要 LibreOffice headless 预归一化。详见 RULES.md。

## 四、使用方法

### 单文件

```bash
# pdf / docx / pptx / xlsx / html(markitdown 统一入口)
python scripts/markitdown/markitdown_to_md.py <file.pdf>

# 纯图片 OCR
python scripts/ocr/ocr_to_md.py <image.png>

# 扫描件 PDF(markitdown 抽不出文本层,exit 3 时降级)
python scripts/ocr/pdf_to_ocr_to_md.py <scanned.pdf>
```

### 批量

```bash
# Windows cmd
for %f in (inbox\*.pdf) do python scripts/markitdown/markitdown_to_md.py "%f"
for %f in (inbox\*.png) do python scripts/ocr/ocr_to_md.py "%f"

# bash / git-bash
for f in inbox/*.pdf; do python scripts/markitdown/markitdown_to_md.py "$f"; done
```

### 入库到 wiki

**默认行为:脚本生成的 `.md` 落在原文件同目录**(例:`D:\资料\foo.pdf` → `D:\资料\foo.md`),这是转换的**中间产物**,**不会**自动送进 wiki 的 `inbox/`。

下一步:把 `.md` 文件手动 `mv`(或复制)进 `<vault>/inbox/`,wiki-plugin `ingest` skill 会自动识别 `type: source` 并归档到 `knowledge/sources/`,同时把原文件 + `.md` 副本一起挪到 `raw/{subdir}/`(PRD §4.2 G10)。

如果你想**直接输出到 inbox** 而不是原文件旁,加 `-o inbox/foo.md`。

## 五、验证脚本能跑

```bash
# OCR 测试
python scripts/ocr/ocr_to_md.py scripts/ocr/README.md 2>&1 | head
# 应该报"no text detected"(README 是文本不是图片,正常)

# markitdown 测试(任意小 PDF / docx)
python scripts/markitdown/markitdown_to_md.py some.pdf
# 应该输出 "OK: N lines -> some.md"
```

## 六、故障排查速查

| 报错 | 原因 | 解决 |
|---|---|---|
| `ModuleNotFoundError: No module named 'markitdown'` | 没装 markitdown | `pip install markitdown` |
| `ModuleNotFoundError: No module named 'paddleocr'` | 没装 OCR | `pip install paddlepaddle==2.6.2 paddleocr==2.7.3 numpy<2` |
| `ConvertPirAttribute2RuntimeAttribute not support ArrayAttribute` | paddlepaddle 3.x onednn bug | 降到 `paddlepaddle==2.6.2` |
| `numpy.core.multiarray failed to import` | numpy 2.x ABI 不兼容 | `pip install "numpy<2"` |
| `Cannot find module 'js-yaml'` / `'ajv'` | 没 `npm install` | 在 `scripts/` 下跑 `npm install` |
| `markitdown 抽不出文本层 (exit 3)` | PDF 是扫描件 | 改跑 `python ocr/pdf_to_ocr_to_md.py file.pdf` |

## 七、文件清单

```
scripts/
├── README.md                    ← 本文件(总览)
├── RULES.md                     ← 工具选择策略(原生优先 → markitdown → OCR)
├── package.json                 ← Node 依赖清单
├── package-lock.json
├── node_modules/                ← npm install 产物
├── markitdown/
│   └── markitdown_to_md.py      ← Python 脚本(pdf/docx/pptx/xlsx/html → md)
└── ocr/
    ├── ocr_to_md.py             ← Python 脚本(图片 OCR → md)
    ├── rapidocr_to_md.py        ← Python 脚本(图片 OCR → md,RapidOCR 引擎)
    ├── pdf_to_ocr_to_md.py      ← Python 脚本(扫描件 PDF → OCR → md)
    ├── pptx_to_ocr_to_md.py     ← Python 脚本(扫描件 PPTX → OCR → md)
    └── README.md
```

## 八、许可

Apache 2.0。

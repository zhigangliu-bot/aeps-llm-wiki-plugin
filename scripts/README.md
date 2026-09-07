# scripts/

wiki-plugin 的转换工具集。把 `inbox/` 里的非文本资料转成纯 markdown(不含 frontmatter),供 `ingest` skill 入库时统一补 wiki 元数据并归档到 `knowledge/sources/`。

**职责分工**:脚本只做"原文 → md 文本",frontmatter(`type` / `tags` / `created` / `source_file` 等)由 `ingest` skill 在文件落 `inbox/` 后自动补。这样脚本职责单一(转文本),入库职责单一(补元数据)。

## 工具一览

| 子目录 | 用途 | 对应 PRD 路径 | 触发条件 |
|---|---|---|---|
| `anydoc/` | 二进制 office / PDF 转 md | 路径 3 | `.pdf` / `.docx` / `.xlsx` / `.pptx`(纯文本) |
| `ocr/` | 图片 OCR 转 md | 路径 4 | `.png` / `.jpg` / `.bmp` / `.tiff` |
| `ocr/pdf_to_ocr_to_md.py` | 扫描件 PDF OCR 转 md | 路径 4 | PDF 是扫描件 / 嵌图(anydoc 跑不动时) |

PRD §4.2 定义了 4 路径分流:

| 路径 | converter | 谁负责 |
|---|---|---|
| 路径 1 | `null` | Claude Code 直接读 |
| 路径 2 | `claude-native` | Claude Code 原生识别 |
| 路径 3 | `anydoc` | 本目录 `anydoc/` |
| 路径 4 | `paddleocr` | 本目录 `ocr/` |

## 一、一次性安装

### 1. Python OCR 工具

```bash
# 装 Python 3.11(从 python.org 下,embeddable 免安装版也行)
# 然后:
pip install paddlepaddle==2.6.2 paddleocr==2.7.3 "numpy<2"
```

详细步骤见 [ocr/README.md](ocr/README.md)。

### 2. Node anydoc 工具

```bash
# 装 Node.js ≥ 20(从 nodejs.org 下 LTS)
# 然后:
cd <repo>/aeps-llm-wiki-plugin/scripts
npm install
```

详细步骤见 [anydoc/README.md](anydoc/README.md)。

## 二、目录拷给用户的清单

把这个 `scripts/` 目录整目录(含 `node_modules/`)拷贝过去即可。如果不想带 node_modules(太大),就只拷源码,目标机器重跑 `npm install`。

`scripts/` 必须包含的:

- `package.json` + `package-lock.json`(锁定依赖版本)
- `anydoc/`(脚本 + README)
- `ocr/`(脚本 + README)
- `node_modules/`(可选,也可 `npm install` 重装)

**不**必须包含(可忽略):

- `node_modules/`(可选重装)
- `package-lock.json`(可选,有了能装出完全一样的版本)

## 三、在另一台新机器上从零搭建

如果你 clone 了仓库,**scripts/ 下没有 node_modules/**(git 不跟),需要按下面顺序装齐。

### 1. 装 Python 3.11(必需,docling / paddleocr 都靠它)

从 [python.org](https://www.python.org/) 下 Python 3.11 LTS,或用 embeddable 免安装版(Windows 用户见 [ocr/README.md §二](ocr/README.md#二一次性安装)):

```bash
python --version   # 应输出 Python 3.11.x
```

### 2. 装 Python 包(必需,docling / paddleocr)

```bash
pip install docling paddlepaddle==2.6.2 paddleocr==2.7.3 "numpy<2"
```

要点:

- `paddlepaddle==2.6.2`(避开 3.x onednn bug)
- `numpy<2`(避 ABI 不兼容)
- docling 自带 RapidOCR + torch,首次跑自动从 `paddleocr.bj.bcebos.com` + `~/.cache/huggingface/` 下模型(~500 MB)

### 3. 装 Node.js ≥ 20(必需,anydoc_pdf_to_md.js)

`package.json` 的 `engines` 字段锁了 `node >= 20.0.0`。从 [nodejs.org](https://nodejs.org/) 下 LTS(当前 v22)安装:

```bash
node --version   # 应输出 v20.x 或更高
```

### 4. 装 npm 依赖(必需,anydoc_pdf_to_md.js)

```bash
cd <repo>/aeps-llm-wiki-plugin/scripts
npm install      # 读 package.json + package-lock.json 装出 node_modules/
```

这一步装三个依赖:`@firecrawl/anydoc`(主用)/ `ajv`(备用)/ `js-yaml`(备用)。

**最少路径**(只跑 anydoc PDF 转 md):只要第 3 + 4 步,Node 一项搞定。
**完整路径**(docx / pptx / xlsx / PDF 都转):第 1 + 2 + 3 + 4 全做。

> **不再需要 poppler / LibreOffice**:docling 内置 PDF/PPTX 解析,不再走 `pdftoppm` / `soffice` 中转链。

## 四、使用方法

### 单文件

```bash
# PDF(anydoc 路径,快)
node scripts/anydoc/anydoc_pdf_to_md.js <file.pdf>

# docx / pptx / xlsx(docling 路径,精,自动抽内嵌图)
python scripts/anydoc/docling_to_md.py <file.docx>
python scripts/anydoc/docling_to_md.py <file.pptx>
python scripts/anydoc/docling_to_md.py <file.xlsx>

# PDF(走 docling,慢但版面精;会打 stderr 警告)
python scripts/anydoc/docling_to_md.py <file.pdf>

# 纯图片 OCR
python scripts/ocr/ocr_to_md.py <image.png>

# 扫描件 PDF(anydoc 跑不动时降级)
python scripts/ocr/pdf_to_ocr_to_md.py <scanned.pdf>
```

### 批量

```bash
# Windows cmd
for %f in (inbox\*.pdf) do node scripts/anydoc/anydoc_pdf_to_md.js "%f"
for %f in (inbox\*.docx) do python scripts/anydoc/docling_to_md.py "%f"
for %f in (inbox\*.png) do python scripts/ocr/ocr_to_md.py "%f"

# bash / git-bash
for f in inbox/*.pdf; do node scripts/anydoc/anydoc_pdf_to_md.js "$f"; done
for f in inbox/*.docx; do python scripts/anydoc/docling_to_md.py "$f"; done
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

# anydoc 测试(任意小 PDF)
node scripts/anydoc/anydoc_pdf_to_md.js some.pdf
# 应该输出 "OK: N lines -> some.md"

# docling 测试(任意 docx,首次会下载模型 ~30s)
python scripts/anydoc/docling_to_md.py some.docx
# 应该输出 "OK: N chars, M images -> some.md"
```

## 六、故障排查速查

| 报错 | 原因 | 解决 |
|---|---|---|
| `ModuleNotFoundError: No module named 'docling'` | 没装 docling | `pip install docling` |
| `ModuleNotFoundError: No module named 'paddleocr'` | 没装 OCR | `pip install paddlepaddle==2.6.2 paddleocr==2.7.3 numpy<2` |
| `ConvertPirAttribute2RuntimeAttribute not support ArrayAttribute` | paddlepaddle 3.x onednn bug | 降到 `paddlepaddle==2.6.2` |
| `numpy.core.multiarray failed to import` | numpy 2.x ABI 不兼容 | `pip install "numpy<2"` |
| `Cannot find module '@firecrawl/anydoc'` | 没 `npm install` | 在 `scripts/` 下跑 `npm install` |
| `anydoc 不处理扫描件 PDF (exit 3)` | PDF 是扫描件 | 改跑 `python ocr/pdf_to_ocr_to_md.py file.pdf` |
| `spawnSync anydoc ENOENT` | PATH 没 anydoc | 重新 `npm install`,脚本会找 `node_modules/.bin/anydoc.cmd` |
| docling PDF 跑 10+ 分钟没结果 | docling PDF 慢 | 杀进程改 `node anydoc_pdf_to_md.js f.pdf` |

## 七、文件清单

```
scripts/
├── README.md                    ← 本文件(总览)
├── package.json                 ← Node 依赖清单
├── package-lock.json
├── node_modules/                ← npm install 产物
├── anydoc/
│   ├── anydoc_pdf_to_md.js      ← Node 脚本(仅 PDF → md,快)
│   ├── docling_to_md.py         ← Python 脚本(docx/pptx/xlsx → md,精 + 抽图)
│   └── README.md
└── ocr/
    ├── ocr_to_md.py             ← Python 脚本(图片 OCR → md)
    ├── pdf_to_ocr_to_md.py      ← Python 脚本(扫描件 PDF → OCR → md)
    ├── pptx_to_ocr_to_md.py     ← Python 脚本(扫描件 PPTX → OCR → md)
    └── README.md
```

## 八、许可

Apache 2.0。

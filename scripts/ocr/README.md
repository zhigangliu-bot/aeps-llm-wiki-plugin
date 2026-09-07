# ocr_to_md

把图片(扫描件、截图、资料照片)里的文字 OCR 出来,生成纯文本 markdown(不含 frontmatter)。frontmatter(`type` / `tags` / `created` 等 wiki 元数据)由 `ingest` skill 在文件落入 `inbox/` 后自动补。

## 工作流位置

```
图片 / 扫描件 / 截图
        │
        ▼  python ocr_to_md.py img.png
   img.md (含 frontmatter,type=source)
        │
        ▼  移动到 <vault>/inbox/
   wiki-plugin ingest skill
        │
        ▼  knowledge/sources/img.md
   Obsidian vault 直接可看
```

## 一、环境

- Windows 10/11
- Python 3.11(`C:\Python311\`,embeddable 免安装版)
- PaddlePaddle 2.6.2 + PaddleOCR 2.7.3(CPU)
- 模型缓存:`C:\Users\<you>\.paddleocr\`

首次跑会自动从 `paddleocr.bj.bcebos.com` 下载 PP-OCRv4 中英文模型(~18MB),之后离线可用。

> **在 `scripts/` 里的位置**:`scripts/` 下有两个转换目录 ——
>
> - **`anydoc/`** —— 处理 `.pdf`(anydoc 路径,快)和 `.docx` / `.pptx` / `.xlsx`(docling 路径,精 + 抽图),**优先用**。
> - **`ocr/`**(本目录)—— 处理**纯图片** + **扫描件 PDF/PPTX** —— anydoc / docling 跑不动时的 **fallback**。
>
> 例:`任何资料.pdf` → `python ../anydoc/anydoc_pdf_to_md.js file.pdf`;`扫描件合同.pdf` → `python pdf_to_ocr_to_md.py scanned.pdf`。

---

## 二、一次性安装

### 1. 装 Python 3.11(embeddable,免安装)

```bash
# 在 temp 目录下
curl -L -o python-3.11.9-embed-amd64.zip \
  https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip

mkdir C:\Python311
unzip python-3.11.9-embed-amd64.zip -d C:\Python311
```

### 2. 启用 site(让 pip 能装第三方包)

编辑 `C:\Python311\python311._pth`,把 `#import site` 改成:

```
import site
```

### 3. 装 pip

```bash
curl -L -o C:\Python311\get-pip.py https://bootstrap.pypa.io/get-pip.py
C:\Python311\python.exe C:\Python311\get-pip.py
```

### 4. 装 paddle(锁定版本,避开 3.x 的 onednn bug)

```bash
C:\Python311\python.exe -m pip install ^
  "paddlepaddle==2.6.2" ^
  "paddleocr==2.7.3" ^
  "numpy<2"
```

### 5. 验证

```bash
C:\Python311\python.exe -c "from paddleocr import PaddleOCR; print('OK')"
```

应输出 `OK`,无报错。

---

## 三、使用方法

### 1. 准备图片

把图片放到任意目录(建议 `inbox/` 的子目录,方便后续归档)。支持 `.png / .jpg / .jpeg / .bmp`。

### 2. 跑 OCR

```bash
C:\Python311\python.exe ocr_to_md.py <图片路径>
```

例:

```bash
C:\Python311\python.exe ocr_to_md.py "F:\资料\手册截图.png"
```

输出在图片同目录,文件名 `手册截图.md`。

### 3. 进阶用法

```bash
# 指定输出路径
C:\Python311\python.exe ocr_to_md.py img.png -o out\my-note.md

# 英文图
C:\Python311\python.exe ocr_to_md.py english.png --lang en

# 繁体中文
C:\Python311\python.exe ocr_to_md.py tw.png --lang chinese_cht

# 日文 / 韩文
C:\Python311\python.exe ocr_to_md.py jp.png --lang japan
C:\Python311\python.exe ocr_to_md.py kr.png --lang korean
```

支持的语言:`ch`、`chinese_cht`、`en`、`korean`、`japan`、`fr`、`de`、`ru` 等,完整列表见 [PaddleOCR 多语言文档](https://github.com/PaddlePaddle/PaddleOCR/blob/main/doc/doc_ch/multi_languages.md)。

### 4. 入库到 wiki

**默认行为**:`.md` 落在原文件同目录(例:`D:\资料\foo.png` → `D:\资料\foo.md`)。这是中间产物,**不会自动送进 wiki**。

下一步:把 `.md` 手动 `mv`(或复制)进 `<vault>/inbox/`,wiki-plugin `ingest` skill 会自动识别 `type: source` 并归档到 `knowledge/sources/`。

直接输出到 inbox:`-o inbox/foo.md`。

### 5. PDF 里嵌扫描图怎么办?

`ocr_to_md.py` 只接图片,不能直接吃 PDF。如果 PDF 是**扫描件**(图片嵌在 PDF 里),用 `pdf_to_ocr_to_md.py`:

```bash
python pdf_to_ocr_to_md.py scanned.pdf -o out.md
```

它会:
1. 调 `pdftoppm` 把 PDF 每页转 PNG(需要 poppler)
2. 逐页 PaddleOCR
3. 拼成一份 markdown,按页用 `## 第 N 页` 分组(无 frontmatter)

前置条件:

```bash
# 装 poppler(让 pdftoppm 在 PATH 里)
# Windows: winget install poppler,或解压 https://github.com/oschwartz10612/poppler-windows/releases 到本地加 PATH
# macOS:   brew install poppler
# Linux:   apt install poppler-utils
pdftoppm -v   # 验证
```

---

## 四、输出格式

脚本只输出 OCR 识别到的纯文本,**不含任何 frontmatter**,不强行编号列表(每行就是 OCR 检测到的一行文字):

```markdown
第一行文字
第二行文字
第三行文字
...
```

**不做的事**(明确剥离):

- 不加 YAML frontmatter
- 不加 `>` 引用说明(置信度、生成自等元信息)
- 不加 `# 标题` 行
- 不加编号列表(`1. ...` / `- ...`),原图是什么格式就是什么格式

如果将来需要,wiki 元数据(如 `type: source` / `created` / `tags` / `source_file` / `ocr_confidence`)会在 ingest skill 入库时按规范统一补,不在脚本层处理。

---

## 五、常见问题

### Q1: 报 `NotImplementedError: ConvertPirAttribute2RuntimeAttribute not support ArrayAttribute<DoubleAttribute>`

**原因**:PaddlePaddle 3.x 在 Windows + onednn 路径上的已知 bug。
**解决**:用本文档锁定的 `paddlepaddle==2.6.2`,**不要装 3.x**。

### Q2: 报 `ImportError: numpy.core.multiarray failed to import`

**原因**:numpy 2.x 与 paddle 2.6 的 ABI 不兼容。
**解决**:`pip install "numpy<2"`(本文档锁 1.26.4)。

### Q3: 模型下载慢 / 失败

模型缓存到 `C:\Users\<you>\.paddleocr\`。多机部署直接拷贝这个目录,跳过下载。

### Q4: 报 `OSError: [WinError 126] ... opencv_videoio_ffmpeg` 或其他 DLL 缺失

embeddable Python 不带 Microsoft Visual C++ Runtime。装一个 [VC++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) 即可。

### Q5: 我想用 GPU 加速

本文档是 CPU 方案。GPU 需重装 `paddlepaddle-gpu==2.6.2` + 对应 CUDA/cuDNN,且 paddleocr 用 server 版模型(精度更高但慢)。
汽车电子文档截图 / 扫描件场景,**CPU 已足够,无需 GPU**。

### Q6: 我用的是 macOS / Linux

本文档步骤是 Windows 版。macOS / Linux 直接用 installer 装 Python 3.11 更简单,跳过 embeddable 那段。paddlepaddle 锁版本 `2.6.2` 这点不变。

---

## 六、性能参考(CPU,PP-OCRv4 mobile)

| 图片 | 耗时 | 备注 |
|---|---|---|
| 900×360 单行文字 | ~2s | 测试图 |
| A4 扫描件(200dpi,~2MB) | ~5-8s | 全页中英文 |
| 手机截图(1080p) | ~3-4s | 提前 `cv2.resize` 到 1500px 更快 |

---

## 七、文件清单

| 文件 | 用途 |
|---|---|
| `ocr_to_md.py` | 主脚本(CLI) |
| `README.md` | 本文档 |

---

## 八、许可

脚本以 Apache 2.0 发布。

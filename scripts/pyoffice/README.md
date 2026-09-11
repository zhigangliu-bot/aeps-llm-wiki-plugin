# pyoffice 转 md(docx / pptx / xlsx 第一优先级)

`pyoffice_to_md.py` 用纯 Python 库提取 office 文档内容转 markdown,**不依赖 docling、不下载模型、不抽图**:

| 扩展名 | 库 | 提取内容 |
|---|---|---|
| `.docx` | python-docx | 段落(Heading 样式 → `#` 层级)+ 表格(md 表格) |
| `.pptx` | python-pptx | 每页 `## Slide N: 标题` + 形状文本 + 备注 |
| `.xlsx` | openpyxl | 每 sheet `## Sheet: 名` + md 表格(去全空行) |

## 优先级位置

见 [../RULES.md](../RULES.md) §1:pyoffice(本脚本)→ anydoc(`../anydoc/anydoc_office_to_md.js`)→ docling(兜底)。失败降级由 `../ingest/convert-to-md.js` 统一派发,本脚本失败 exit 1 即可。

## 安装依赖

```bash
pip install python-docx python-pptx openpyxl
```

## 用法

```bash
python pyoffice/pyoffice_to_md.py foo.docx              # 输出 foo.md 到原文件旁
python pyoffice/pyoffice_to_md.py foo.pptx -o out/my.md
```

Exit codes:`0` 成功 / `1` 转换失败(文件损坏、依赖缺失)/ `2` 用法错。

## 限制

- **不抽图、不做图内 OCR** —— 含图且需要图的场景直接走 docling 兜底。
- 只认现代格式;`.ppt/.doc/.xls` 先 LibreOffice 归一化(见 RULES.md 路径 0)。

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
pyoffice_to_md.py — .docx / .pptx / .xlsx → markdown
第一优先级本地转换(RULES.md §1):
  .docx → python-docx   (段落 + 标题层级 + 表格)
  .pptx → python-pptx   (每页文本 + 备注)
  .xlsx → openpyxl      (每 sheet → markdown 表格)

失败时由调用方(convert-to-md.js)降级 anydoc → docling。

Usage:
  python pyoffice_to_md.py <file> [-o out.md]

Exit codes:
  0 - 成功
  1 - 转换失败(文件损坏 / 格式不对 / 依赖缺失)
  2 - 用法错(无参数 / 扩展名不支持)
"""
import argparse
import sys

SUPPORTED = {".docx", ".pptx", ".xlsx"}

HEADING_MAP = {  # docx 样式名 → markdown 标题层级
    "Heading 1": "#", "Heading 2": "##", "Heading 3": "###",
    "Heading 4": "####", "Heading 5": "#####", "Heading 6": "######",
    "标题 1": "#", "标题 2": "##", "标题 3": "###",
    "标题 4": "####", "标题 5": "#####", "标题 6": "######",
}


def _cell(text):
    """markdown 表格单元格转义:竖线与换行。"""
    return str(text if text is not None else "").replace("|", "\\|").replace("\n", " ").strip()


def _table_to_md(rows):
    """二维行列表 → markdown 表格(空表返回 None)。"""
    if not rows:
        return None
    width = max(len(r) for r in rows)
    norm = [list(r) + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(_cell(c) for c in norm[0]) + " |",
             "| " + " | ".join(["---"] * width) + " |"]
    lines += ["| " + " | ".join(_cell(c) for c in r) + " |" for r in norm[1:]]
    return "\n".join(lines)


def _iter_docx_blocks(doc):
    """按文档顺序产出 ('p', paragraph) / ('t', table)。python-docx >= 1.1。"""
    try:
        yield from (("p", b) if b.__class__.__name__ == "Paragraph" else ("t", b)
                    for b in doc.iter_inner_content())
    except AttributeError:  # 旧版 python-docx:只有段落
        for p in doc.paragraphs:
            yield "p", p


def docx_to_md(path):
    import docx  # python-docx
    doc = docx.Document(path)
    out = []
    for kind, block in _iter_docx_blocks(doc):
        if kind == "t":
            md = _table_to_md([[c.text for c in row.cells] for row in block.rows])
            if md:
                out.append(md)
        else:
            text = block.text.strip()
            if not text:
                continue
            style = (block.style.name or "").strip()
            prefix = HEADING_MAP.get(style)
            # 命名样式形如 "Heading 1 Char" / 无样式 → 正文
            if prefix is None and style.startswith("Heading "):
                prefix = "#" * min(int(style.split()[1] or 1), 6)
            out.append(f"{prefix} {text}" if prefix else text)
    return "\n\n".join(out) + "\n"


def pptx_to_md(path):
    from pptx import Presentation
    prs = Presentation(path)
    out = []
    for i, slide in enumerate(prs.slides, 1):
        title = ""
        texts = []
        title_el = slide.shapes.title._element if slide.shapes.title is not None else None
        for shape in slide.shapes:
            if title_el is not None and shape._element is title_el:
                continue
            if shape.has_text_frame:
                t = shape.text_frame.text.strip()
                if t:
                    texts.append(t)
        if title_el is not None:
            title = (slide.shapes.title.text or "").strip()
        out.append(f"## Slide {i}: {title}" if title else f"## Slide {i}")
        if texts:
            out.append("\n\n".join(texts))
        notes = ""
        if slide.has_notes_slide:
            notes = (slide.notes_slide.notes_text_frame.text or "").strip()
        if notes:
            out.append(f"> 备注: {notes}")
    return "\n\n".join(out) + "\n"


def xlsx_to_md(path):
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=True, read_only=True)
    out = []
    for ws in wb.worksheets:
        rows = [[c if c is not None else "" for c in row] for row in ws.iter_rows(values_only=True)]
        rows = [r for r in rows if any(str(c).strip() for c in r)]  # 去全空行
        if not rows:
            continue
        out.append(f"## Sheet: {ws.title}")
        out.append(_table_to_md(rows))
    return "\n\n".join(out) + "\n"


CONVERTERS = {".docx": docx_to_md, ".pptx": pptx_to_md, ".xlsx": xlsx_to_md}


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("input")
    ap.add_argument("-o", "--out")
    args = ap.parse_args()

    import os
    ext = os.path.splitext(args.input)[1].lower()
    if ext not in SUPPORTED:
        print(f"ERROR: unsupported extension '{ext}', supported: {', '.join(sorted(SUPPORTED))}",
              file=sys.stderr)
        sys.exit(2)
    if not os.path.isfile(args.input):
        print(f"ERROR: not a file: {args.input}", file=sys.stderr)
        sys.exit(2)

    try:
        md = CONVERTERS[ext](args.input)
    except ImportError as e:
        print(f"FAIL: Python 依赖缺失: {e}(docx→python-docx, pptx→python-pptx, xlsx→openpyxl)",
              file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # 文件损坏 / 格式不对 → 调用方降级
        print(f"FAIL: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

    out_path = args.out or (os.path.splitext(args.input)[0] + ".md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"OK: {md.count(chr(10))} lines -> {out_path}")


if __name__ == "__main__":
    main()

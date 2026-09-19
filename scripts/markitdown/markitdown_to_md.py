#!/usr/bin/env python
"""
markitdown_to_md.py — 任意文档 → markdown(Microsoft MarkItDown 统一转换)

依赖收敛(2026-09-18 拍板):路径 3 全部格式(pdf/docx/pptx/xlsx/html)统一走
MarkItDown,替换 anydoc / pyoffice / docling 三条链;扫描件仍走 ocr/paddleocr。

Usage:
    python markitdown_to_md.py <input> [-o out.md]

- 输出忠于 MarkItDown 产出的 markdown 文本,frontmatter 由 ingest skill 补
- 扫描件 PDF(MarkItDown 抽不出文本层)exit 3,提示走 OCR
"""
import argparse
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--out")
    a = ap.parse_args()

    try:
        from markitdown import MarkItDown
    except ImportError:
        print("ERROR: markitdown 未安装;pip install markitdown", file=sys.stderr)
        sys.exit(2)

    md = MarkItDown()
    try:
        result = md.convert(a.input)
    except Exception as e:  # noqa: BLE001 — 透传底层错误信息
        print(f"ERROR: convert 失败: {e}", file=sys.stderr)
        sys.exit(2)

    text = (result.text_content or "").strip()
    if not text:
        # 空正文大概率是扫描件(无文本层)→ 提示走 OCR 路径
        print("ERROR: 抽不出文本层(疑似扫描件);先转图片再走 OCR:\n"
              "  pdftoppm <input> page -png\n"
              "  python ../ocr/ocr_to_md.py page-1.png", file=sys.stderr)
        sys.exit(3)

    out = a.out or (a.input.rsplit(".", 1)[0] + ".md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"OK: {len(text.splitlines())} lines -> {out}")


if __name__ == "__main__":
    main()

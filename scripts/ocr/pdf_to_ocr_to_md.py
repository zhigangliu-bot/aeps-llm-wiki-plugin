"""Scan PDF → OCR per page → single markdown with frontmatter.

Use when anydoc exits 3 on a PDF (image-only / scanned pages).
Pipeline: pdftoppm → per-page PaddleOCR → concatenated markdown.

Usage:
    python ocr_pdf.py <file.pdf> [-o out.md] [--dpi 200]

Prereqs:
    - poppler / pdftoppm on PATH (https://github.com/oschwartz10612/poppler-windows)
    - paddleocr + paddlepaddle + numpy<2 already installed
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from paddleocr import PaddleOCR


def find_pdftoppm() -> str | None:
    return shutil.which("pdftoppm")


def pdf_to_pngs(pdf: Path, out_dir: Path, dpi: int) -> list[Path]:
    """Convert PDF pages to PNG using pdftoppm."""
    pdftoppm = find_pdftoppm()
    if not pdftoppm:
        raise RuntimeError(
            "pdftoppm not on PATH. Install poppler:\n"
            "  Windows: winget install poppler, or download from\n"
            "    https://github.com/oschwartz10612/poppler-windows/releases\n"
            "  macOS:   brew install poppler\n"
            "  Linux:   apt install poppler-utils"
        )
    prefix = out_dir / "page"
    subprocess.run(
        [pdftoppm, "-r", str(dpi), "-png", str(pdf), str(prefix)],
        check=True,
        capture_output=True,
    )
    return sorted(out_dir.glob("page-*.png"))


def ocr_pages(ocr: PaddleOCR, pages: list[Path]) -> list[list[tuple[str, float]]]:
    """Run OCR on each page; return list of pages, each page is [(text, score), ...]."""
    out = []
    for i, p in enumerate(pages, 1):
        result = ocr.ocr(str(p), cls=False)
        lines = []
        if result and result[0]:
            for _, (text, score) in result[0]:
                lines.append((text.strip(), float(score)))
        out.append(lines)
        print(f"  page {i}/{len(pages)}: {len(lines)} lines", file=sys.stderr)
    return out


# ponytail: frontmatter 由 wiki-plugin ingest skill 入库时补,
# 脚本只按页输出 OCR 文本,保留页结构(## 第 N 页)以贴近原文版面。
def to_markdown(pdf: Path, page_lines: list[list[tuple[str, float]]]) -> str:
    body: list[str] = []
    for i, lines in enumerate(page_lines, 1):
        if not lines:
            body += [f"## 第 {i} 页", "", "_（无可识别文字）_", ""]
            continue
        body += [f"## 第 {i} 页", ""]
        for t, _ in lines:
            body.append(t)
        body.append("")
    return "\n".join(body).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Scan PDF → OCR → markdown")
    ap.add_argument("pdf", type=Path, help="input PDF (scanned / image-only)")
    ap.add_argument("-o", "--out", type=Path, default=None)
    ap.add_argument("--dpi", type=int, default=200,
                    help="render DPI (default 200, range 150-300)")
    ap.add_argument("--lang", default="ch")
    args = ap.parse_args()

    if not args.pdf.is_file():
        print(f"ERROR: not a file: {args.pdf}", file=sys.stderr)
        return 2

    out = args.out or args.pdf.with_suffix(".md")
    tmpdir = Path(tempfile.mkdtemp(prefix="ocr_pdf_"))
    try:
        print(f"[1/3] pdftoppm → {tmpdir}", file=sys.stderr)
        pages = pdf_to_pngs(args.pdf, tmpdir, args.dpi)
        if not pages:
            print("ERROR: pdftoppm produced no pages", file=sys.stderr)
            return 1
        print(f"[2/3] OCR {len(pages)} pages", file=sys.stderr)
        ocr = PaddleOCR(use_angle_cls=False, lang=args.lang, show_log=False)
        page_lines = ocr_pages(ocr, pages)
        print(f"[3/3] write → {out}", file=sys.stderr)
        out.write_text(to_markdown(args.pdf, page_lines), encoding="utf-8")
        total = sum(len(p) for p in page_lines)
        print(f"OK: {len(pages)} pages, {total} lines -> {out}")
        return 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())

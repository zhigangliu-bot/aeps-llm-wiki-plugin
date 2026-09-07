"""Scanned-PPTX → OCR per slide → markdown with frontmatter.

Pipeline: pptx → pdf (via LibreOffice) → pdftoppm → PaddleOCR per page.

Use when a PPTX has embedded images / scanned slides that anydoc cannot
extract as text.

Usage:
    python pptx_to_ocr_to_md.py <file.pptx> [-o out.md] [--dpi 200]

Prereqs:
    - LibreOffice / soffice on PATH (winget install LibreOffice, or brew
      install --cask libreoffice, or apt install libreoffice)
    - poppler / pdftoppm on PATH
    - paddleocr + paddlepaddle + numpy<2 already installed
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def find_soffice() -> str | None:
    for cand in ("soffice", "libreoffice",
                 r"C:\Program Files\LibreOffice\program\soffice.exe",
                 r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"):
        if cand.startswith(("soffice", "libreoffice")):
            path = shutil.which(cand)
        else:
            path = cand if Path(cand).is_file() else None
        if path:
            return path
    return None


def find_pdftoppm() -> str | None:
    return shutil.which("pdftoppm")


def pptx_to_pdf(pptx: Path, out_dir: Path) -> Path:
    soffice = find_soffice()
    if not soffice:
        raise RuntimeError(
            "LibreOffice (soffice) not on PATH. Install:\n"
            "  Windows: winget install LibreOffice.LibreOffice\n"
            "           或 https://www.libreoffice.org/download\n"
            "  macOS:   brew install --cask libreoffice\n"
            "  Linux:   apt install libreoffice\n"
            "soffice --version   # 验证"
        )
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir",
         str(out_dir), str(pptx)],
        check=True, capture_output=True,
    )
    pdf = out_dir / (pptx.stem + ".pdf")
    if not pdf.is_file():
        raise RuntimeError(f"soffice did not produce expected PDF: {pdf}")
    return pdf


def pdf_to_pngs(pdf: Path, out_dir: Path, dpi: int) -> list[Path]:
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
        check=True, capture_output=True,
    )
    return sorted(out_dir.glob("page-*.png"))


def ocr_pages(pages: list[Path], lang: str) -> list[list[tuple[str, float]]]:
    # Late import — keeps this module importable without paddleocr present
    # (e.g. for --help or for users who only run anydoc / pdf_to_ocr_to_md).
    from paddleocr import PaddleOCR

    ocr = PaddleOCR(use_angle_cls=False, lang=lang, show_log=False)
    out: list[list[tuple[str, float]]] = []
    for i, p in enumerate(pages, 1):
        result = ocr.ocr(str(p), cls=False)
        lines: list[tuple[str, float]] = []
        if result and result[0]:
            for _, (text, score) in result[0]:
                lines.append((text.strip(), float(score)))
        out.append(lines)
        print(f"  page {i}/{len(pages)}: {len(lines)} lines", file=sys.stderr)
    return out


# ponytail: frontmatter 由 wiki-plugin ingest skill 入库时补,
# 脚本只按页输出 OCR 文本,保留页结构(## 第 N 页)以贴近原文版面。
def to_markdown(_src: Path, page_lines: list[list[tuple[str, float]]],
                _fmt: str, _converter: str, _extra_tags: list[str]) -> str:
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
    ap = argparse.ArgumentParser(description="Scanned PPTX → OCR → markdown")
    ap.add_argument("pptx", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=None)
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--lang", default="ch")
    args = ap.parse_args()

    if not args.pptx.is_file():
        print(f"ERROR: not a file: {args.pptx}", file=sys.stderr)
        return 2

    out = args.out or args.pptx.with_suffix(".md")
    tmpdir = Path(tempfile.mkdtemp(prefix="ocr_pptx_"))
    try:
        print(f"[1/4] soffice pptx → pdf  ({tmpdir})", file=sys.stderr)
        pdf = pptx_to_pdf(args.pptx, tmpdir)
        print(f"[2/4] pdftoppm → {tmpdir}", file=sys.stderr)
        pages = pdf_to_pngs(pdf, tmpdir, args.dpi)
        if not pages:
            print("ERROR: pdftoppm produced no pages", file=sys.stderr)
            return 1
        print(f"[3/4] OCR {len(pages)} slides", file=sys.stderr)
        page_lines = ocr_pages(pages, args.lang)
        print(f"[4/4] write → {out}", file=sys.stderr)
        md = to_markdown(args.pptx, page_lines,
                         fmt="pptx", converter="paddleocr",
                         extra_tags=["scanned-pptx"])
        out.write_text(md, encoding="utf-8")
        total = sum(len(p) for p in page_lines)
        print(f"OK: {len(pages)} slides, {total} lines -> {out}")
        return 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())

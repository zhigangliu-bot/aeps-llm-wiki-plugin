"""OCR image → OKF-flavored markdown.

Wraps PaddleOCR 2.7.x output with the wiki-plugin frontmatter spec
(see doc/schema/frontmatter-spec.md). Output is a `.md` file with
`type: source`, ready to be dropped into `inbox/` for the ingest skill.

Usage:
    python ocr_to_md.py <image.png> [-o out.md] [--lang ch] [--json]

`--json` makes the script print `{text, avg_confidence}` JSON to stdout
instead of writing the `.md` file. This is the entry point used by
docling_to_md.py to OCR images extracted from docx/pptx/xlsx.

See README.md in this directory for setup.
"""
import argparse
import json
import sys
from pathlib import Path

from paddleocr import PaddleOCR


def ocr_image(img_path: Path, ocr: PaddleOCR) -> list[tuple[str, float]]:
    """Return [(text, score), ...] in reading order."""
    result = ocr.ocr(str(img_path), cls=False)
    if not result or not result[0]:
        return []
    return [(text.strip(), float(score)) for _, (text, score) in result[0]]


# ponytail: frontmatter 由 wiki-plugin ingest skill 入库时补,
# 脚本只输出 OCR 识别到的文本,每行一段,不强行编号(列表/表格还原交给版面分析)。
def to_markdown(_img_path: Path, lines: list[tuple[str, float]]) -> str:
    return "\n".join(t for t, _ in lines).rstrip() + "\n"


def to_json(lines: list[tuple[str, float]]) -> str:
    avg = round(sum(s for _, s in lines) / max(len(lines), 1), 3)
    text = "\n".join(t for t, _ in lines)
    return json.dumps({"text": text, "avg_confidence": avg},
                      ensure_ascii=False)


def main() -> int:
    ap = argparse.ArgumentParser(description="OCR image → markdown")
    ap.add_argument("image", type=Path, help="input image (png/jpg)")
    ap.add_argument("-o", "--out", type=Path, default=None,
                    help="output .md path (default: <image>.md)")
    ap.add_argument("--lang", default="ch")
    ap.add_argument("--json", action="store_true",
                    help="print {text, avg_confidence} JSON to stdout "
                         "instead of writing .md (used by docling_to_md.py)")
    args = ap.parse_args()

    if not args.image.is_file():
        print(f"ERROR: not a file: {args.image}", file=sys.stderr)
        return 2

    ocr = PaddleOCR(use_angle_cls=False, lang=args.lang, show_log=False)
    lines = ocr_image(args.image, ocr)

    if args.json:
        print(to_json(lines))
        return 0

    if not lines:
        print(f"WARN: no text detected in {args.image}", file=sys.stderr)

    out = args.out or args.image.with_suffix(".md")
    md = to_markdown(args.image, lines)
    out.write_text(md, encoding="utf-8")
    print(f"OK: {len(lines)} lines -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

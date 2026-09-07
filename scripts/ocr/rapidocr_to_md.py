"""OCR image → OKF-flavored markdown via docling bundled RapidOCR.

Mirrors scripts/ocr/ocr_to_md.py byte-for-byte on CLI / output contract,
but uses docling's bundled RapidOCR (rapidocr >=3.x, PP-OCRv6 small)
instead of PaddleOCR.

Usage:
    python rapidocr_to_md.py <image.png> [-o out.md] [--json]

`--json` prints the same `{text, avg_confidence}` JSON shape as
ocr_to_md.py, so docling_to_md.py can swap between the two engines by
changing one path. (Not wired in by default — see README for the env
constraint: RapidOCR requires onnxruntime + protobuf>=4.25, which
conflicts with paddlepaddle 2.6.2's protobuf<=3.20 pin. Run this in a
separate venv.)

See README.md in this directory for setup.
"""
import argparse
import json
import sys
from pathlib import Path


def ocr_image(img_path: Path, engine) -> list[tuple[str, float]]:
    """Return [(text, score), ...] in reading order."""
    out = engine(str(img_path))
    txts = getattr(out, "txts", None) or []
    scores = getattr(out, "scores", None) or []
    if not txts:
        return []
    return [(t.strip(), float(s)) for t, s in zip(txts, scores)]


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
    ap = argparse.ArgumentParser(description="OCR image → markdown (RapidOCR)")
    ap.add_argument("image", type=Path, help="input image (png/jpg)")
    ap.add_argument("-o", "--out", type=Path, default=None,
                    help="output .md path (default: <image>.md)")
    ap.add_argument("--json", action="store_true",
                    help="print {text, avg_confidence} JSON to stdout "
                         "instead of writing .md (mirror of ocr_to_md.py)")
    args = ap.parse_args()

    if not args.image.is_file():
        print(f"ERROR: not a file: {args.image}", file=sys.stderr)
        return 2

    try:
        from rapidocr import RapidOCR
    except ImportError:
        print("ERROR: rapidocr not installed. See scripts/ocr/README.md §RapidOCR.",
              file=sys.stderr)
        return 3

    engine = RapidOCR()  # PP-OCRv6 small, ch+en default
    lines = ocr_image(args.image, engine)

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

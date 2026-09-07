"""docling 转换 docx / pptx / xlsx (+ PDF, 慢) → markdown.

走 IBM Docling 的 DocumentConverter。

docling 在不同格式下输出行为不一致:
- pptx: 把图写到 `<input>.stem_media/image_NN.<ext>`,md 用**绝对路径**引用
- docx: 给 `<!-- image -->` 占位符,图**未**写出

本脚本统一处理:
1. 调 docling.convert() → export_to_markdown()
2. 抽 `result.document.pictures`(双类型兼容:DoclingImage.data + ImageRef.uri 是 data:...;base64,...) 写到 `<input>.stem_media/image_NN.<ext>`
3. 把 md 里两种引用都改成相对路径 `![](<stem>_media/image_NN.<ext>)`:
   - `<!-- image -->` 占位符按出现顺序替换
   - docling 写的绝对路径引用也改相对
4. 对每张图调 `scripts/ocr/ocr_to_md.py --json` 拿 OCR 文本 + 平均置信度:
   - 置信度 ≥ 0.5 → 在 `![](...)` 下一行贴 `> ` 引用块摘要
   - 失败 / 置信度低 → 只显示图片

PDF 也接受(用户明确要版面质量时用),但 stderr 打慢速警告。

frontmatter 不写(由 wiki-plugin ingest skill 入库时补)。

Usage:
    python docling_to_md.py <input.{docx|pptx|xlsx|pdf}> [-o out.md]
"""
import argparse
import base64
import json
import re
import subprocess
import sys
from pathlib import Path

# ponytail: docling 导入慢,延迟到 main() 里,避免图片 OCR 等场景误装。


SUPPORTED = {".docx", ".pptx", ".xlsx", ".pdf"}
OCR_CONFIDENCE_THRESHOLD = 0.5  # 嵌字图 OCR 摘要门
OCR_TIMEOUT_S = 30
IMAGE_PLACEHOLDER_RE = re.compile(r"<!--\s*image\s*-->")


def warn_pdf_slow() -> None:
    print(
        "[WARN] docling_to_md.py: PDF 转换慢(11 页 ~82s,18 页 10+ 分钟)。\n"
        "       纯文本 PDF 建议先试 anydoc_pdf_to_md.js(<1s)。",
        file=sys.stderr,
    )


def mime_to_ext(mimetype: str | None) -> str:
    if not mimetype:
        return "png"
    return mimetype.split("/", 1)[-1].lower() or "png"


def image_bytes(image) -> bytes | None:
    """从 pic.image 抽 bytes。DoclingImage.data 直接拿;ImageRef.uri 是 data:<mime>;base64,<b64>。"""
    if image is None:
        return None
    if hasattr(image, "data") and image.data is not None:
        try:
            return bytes(image.data)
        except Exception:
            return None
    uri = getattr(image, "uri", None)
    if uri is None:
        return None
    s = str(uri)
    if not s.startswith("data:"):
        return None
    try:
        _, payload = s.split(",", 1)
        return base64.b64decode(payload)
    except Exception:
        return None


def ocr_subprocess(image_path: Path, scripts_root: Path) -> dict | None:
    """调 `python scripts/ocr/ocr_to_md.py <img> --json`,拿 {text, avg_confidence}。"""
    cmd = [
        sys.executable,
        str(scripts_root / "ocr" / "ocr_to_md.py"),
        str(image_path),
        "--json",
    ]
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", timeout=OCR_TIMEOUT_S, check=False,
        )
    except subprocess.TimeoutExpired:
        print(f"[WARN] OCR timeout: {image_path.name}", file=sys.stderr)
        return None
    except OSError as e:
        print(f"[WARN] OCR spawn failed: {e}", file=sys.stderr)
        return None

    if r.returncode != 0 or not r.stdout.strip():
        msg = (r.stderr or "").strip().splitlines()
        tail = msg[-1] if msg else f"exit={r.returncode}"
        print(f"[WARN] OCR failed ({image_path.name}): {tail}", file=sys.stderr)
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError as e:
        print(f"[WARN] OCR json decode failed: {e}", file=sys.stderr)
        return None


def extract_images(pictures, media_dir: Path) -> list[Path]:
    """抽图到 media_dir,返回 [image_NN.<ext>, ...] 顺序路径。

    已存在的同名图跳过(幂等)。
    """
    media_dir.mkdir(exist_ok=True)
    paths: list[Path] = []
    for i, pic in enumerate(pictures, 1):
        data = image_bytes(pic.image)
        if data is None:
            continue
        ext = mime_to_ext(getattr(pic.image, "mimetype", None))
        out = media_dir / f"image_{i:02d}.{ext}"
        if not out.exists():
            out.write_bytes(data)
        paths.append(out)
    return paths


def absolutize_to_relative(md_text: str, input_path: Path) -> str:
    """把 docling 写的绝对路径引用改为相对 `<stem>_media/...`。"""
    input_dir = str(input_path.parent).replace("\\", "/")
    media_dir_name = f"{input_path.stem}_media"
    pattern = re.compile(
        re.escape(input_dir) + r"/" + re.escape(media_dir_name) + r"/([^\s)]+)"
    )
    return pattern.sub(rf"{media_dir_name}/\1", md_text)


def replace_placeholders(md_text: str, image_paths: list[Path],
                          out_path: Path) -> str:
    """按出现顺序把 `<!-- image -->` 替换为 `![](<rel-to-md>)`。

    rel = `<stem>_media/image_NN.<ext>`(md 与 _media 同目录,只写相对名)。
    """
    iterator = iter(image_paths)
    base = out_path.parent.resolve()

    def rel(p: Path) -> str:
        try:
            return p.resolve().relative_to(base).as_posix()
        except ValueError:
            # 跨盘符 → 退化为只用文件名
            return p.name

    def repl(_m: re.Match) -> str:
        try:
            return f"![]({rel(next(iterator))})"
        except StopIteration:
            return _m.group(0)

    return IMAGE_PLACEHOLDER_RE.sub(repl, md_text)


def append_ocr_quotes(md_text: str, image_paths: list[Path],
                      scripts_root: Path) -> str:
    """每张图 OCR,avg_confidence ≥ 门 → 在 ![](...) 下一行贴 `> ` 摘要。"""
    for img in image_paths:
        rel = f"{img.parent.name}/{img.name}"
        image_md = f"![]({rel})"
        if image_md not in md_text:
            continue
        ocr = ocr_subprocess(img, scripts_root)
        if not ocr or ocr.get("avg_confidence", 0) < OCR_CONFIDENCE_THRESHOLD:
            continue
        text = (ocr.get("text") or "").rstrip()
        if not text:
            continue
        quote = "\n".join(f"> {line}" for line in text.splitlines())
        md_text = md_text.replace(image_md, f"{image_md}\n{quote}", 1)
    return md_text


def convert(input_path: Path, out_path: Path, scripts_root: Path) -> None:
    from docling.document_converter import DocumentConverter

    conv = DocumentConverter()
    result = conv.convert(str(input_path))
    md = result.document.export_to_markdown()

    media_dir = out_path.parent / f"{out_path.stem}_media"
    image_paths = extract_images(result.document.pictures, media_dir)

    md = absolutize_to_relative(md, input_path)
    md = replace_placeholders(md, image_paths, out_path)
    md = append_ocr_quotes(md, image_paths, scripts_root)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"OK: {len(md)} chars, {len(image_paths)} images -> {out_path}")


def main() -> int:
    ap = argparse.ArgumentParser(description="docling convert → markdown")
    ap.add_argument("input", type=Path,
                    help="input file (.docx / .pptx / .xlsx / .pdf)")
    ap.add_argument("-o", "--out", type=Path, default=None,
                    help="output .md path (default: <input>.md)")
    args = ap.parse_args()

    ext = args.input.suffix.lower()
    if ext not in SUPPORTED:
        print(
            f"ERROR: unsupported extension '{ext}', "
            f"supported: {', '.join(sorted(SUPPORTED))}",
            file=sys.stderr,
        )
        return 2
    if not args.input.is_file():
        print(f"ERROR: not a file: {args.input}", file=sys.stderr)
        return 2

    if ext == ".pdf":
        warn_pdf_slow()

    out = args.out or args.input.with_suffix(".md")
    scripts_root = Path(__file__).resolve().parent.parent

    try:
        convert(args.input, out, scripts_root)
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""convert-to-md.py — inbox/<file> 转为 markdown 文本,按扩展名分流。

CLI:
    # 单文件
    python3 convert-to-md.py --project-dir . --input inbox/<file> --output-dir temp/

    # 批量(共享单 Engine 实例,G10 PATCH)
    python3 convert-to-md.py --project-dir . --batch <file1> <file2> ...
        --output-dir temp/ [--emit-to temp/]

行为(DESIGN.md §1.1 + §3.1 G10):
    - 按扩展名分流 → converter enum:
        - md / txt         → native_text=true, converter=null, converted_path=null,纯文本 passthrough
        - csv / json / yaml / xml / html / htm / rst → claude-native(脚本暂 emit stub;真实内容由 SKILL.md 调度 Claude 处理)
        - pptx / docx / xlsx / pdf → anydoc(importlib 探测,失败报错)
        - png / jpg / jpeg / bmp / tiff → paddleocr(importlib 探测,失败报错)
    - 输出 temp/<basename>.md(纯文本直接复制内容 + 标 native_text=true)
    - --emit-to temp/(G10):同时写 temp/<basename>.<ext>.converted.md(纯文本不写 .converted.md)
    - 单文件 / batch 都 stdout JSON

输出:
    单文件:stdout JSON {"converted_path": "temp/<basename>.md", "format": ..., "converter": ..., "native_text": ...}
    batch:多 JSON 行(每文件 1 行)

约束(NFR-1 ~ NFR-7):
    - 不读 stdin(NFR-1)
    - 不开 daemon(NFR-1)
    - 路径全部相对 --project-dir(NFR-4)
    - 临时文件进 <project>/temp/(NFR-5)
    - 错误消息中文为主(NFR-3)
    - 缺包(importlib 失败)→ 中文报错并 exit 1
    - 本轮只做 importlib 探测 + stub;真实 anydoc/paddleocr 调用留给后续轮次
"""

from __future__ import annotations

import argparse
import importlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from _common import emit_json


# 4 路由分流(NATIVE_TEXT / CLAUDE_NATIVE / ANYDOC / PADDLEOCR)
# 来源:DESIGN.md §3.1 G10
NATIVE_TEXT_EXTS = {"md", "txt"}
CLAUDE_NATIVE_EXTS = {"csv", "json", "yaml", "xml", "html", "htm", "rst"}
ANYDOC_EXTS = {"pptx", "docx", "xlsx", "pdf"}
PADDLEOCR_EXTS = {"png", "jpg", "jpeg", "bmp", "tiff"}


def classify(ext: str) -> dict[str, Any]:
    """根据扩展名小写,返回 converter / native_text 决策。

    Returns:
        {"format": ext, "converter": "anydoc"|"claude-native"|"paddleocr"|None, "native_text": bool}
    """
    e = ext.lower().lstrip(".")
    if e in NATIVE_TEXT_EXTS:
        return {"format": e, "converter": None, "native_text": True}
    if e in CLAUDE_NATIVE_EXTS:
        return {"format": e, "converter": "claude-native", "native_text": False}
    if e in ANYDOC_EXTS:
        return {"format": e, "converter": "anydoc", "native_text": False}
    if e in PADDLEOCR_EXTS:
        return {"format": e, "converter": "paddleocr", "native_text": False}
    raise ValueError(f"扩展名不支持:.{e}")


def _probe_module(module_name: str) -> None:
    """探测模块是否可导入;失败抛中文报错并 exit 1。

    Args:
        module_name: importlib 导入名,如 "anydoc" / "paddleocr"。

    Raises:
        SystemExit: 通过 print + exit(1) 走中文报错分支。
    """
    try:
        importlib.import_module(module_name)
    except ImportError as e:
        print(
            f"❌ 缺依赖:{module_name}。请运行 pip install -r requirements.txt",
            file=sys.stderr,
        )
        print(f"详细错误:{e}", file=sys.stderr)
        sys.exit(1)


def _resolve_paths(
    input_path: str, output_dir: Path, emit_to: Path | None
) -> tuple[Path, Path, str]:
    """把 inbox/<file> 解析成 (输出目标 md, 输出目标 converted.md|None, basename)。

    Args:
        input_path: 形如 inbox/<basename>.<ext> 或 <basename>.<ext>(允许裸文件 fallback)
        output_dir: 主输出目录(必填)
        emit_to: G10 副本目录(若为 None 则不生成 converted.md)

    Returns:
        (out_md, converted_path_or_None, basename_no_ext)
    """
    src = Path(input_path)
    basename_no_ext = src.stem
    ext = src.suffix.lstrip(".")

    out_md = output_dir / f"{basename_no_ext}.md"

    converted_path: Path | None = None
    if emit_to is not None:
        if ext:
            converted_path = emit_to / f"{basename_no_ext}.{ext}.converted.md"
        else:
            converted_path = emit_to / f"{basename_no_ext}.converted.md"

    return out_md, converted_path, basename_no_ext


def _convert_one(
    input_file: Path,
    output_dir: Path,
    emit_to: Path | None,
) -> dict[str, Any]:
    """转换单个文件到 output_dir(emit_to 非空时,转换过的格式额外写副本)。"""
    ext = input_file.suffix.lstrip(".")
    decision = classify(ext)

    out_md, converted_target, basename = _resolve_paths(
        str(input_file), output_dir, emit_to
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    if emit_to is not None:
        emit_to.mkdir(parents=True, exist_ok=True)

    # 分支处理
    if decision["native_text"]:
        # 纯文本 passthrough:直接复制内容到 <basename>.md
        if not input_file.exists():
            raise FileNotFoundError(f"输入文件不存在:{input_file}")
        shutil.copy2(input_file, out_md)
        # 纯文本不写 .converted.md(G10 约定,DESIGN.md §3.1)
        converted_relative: str | None = None
    else:
        # 转换过的格式:先 stub 写一段"等待 SKILL.md 替换"的占位 markdown
        if decision["converter"] == "anydoc":
            _probe_module("anydoc")
            stub_body = (
                f"# {basename} (anydoc 转换产物)\n\n"
                f"<此文件由 convert-to-md.py 占位;SKILL.md 调度 Claude 替换为真正转换正文>\n"
                f"<原始输入:{input_file}>\n"
            )
        elif decision["converter"] == "paddleocr":
            _probe_module("paddleocr")
            stub_body = (
                f"# {basename} (paddleocr 转换产物)\n\n"
                f"<此文件由 convert-to-md.py 占位;SKILL.md 调度 OCR 管线替换为真正识别正文>\n"
                f"<原始输入:{input_file}>\n"
            )
        elif decision["converter"] == "claude-native":
            # claude-native 不需要依赖探测,SKILL.md 后续直接调用 Claude
            stub_body = (
                f"# {basename} (claude-native 转换产物)\n\n"
                f"<此文件由 convert-to-md.py 占位;SKILL.md 调度 Claude 内置转换能力>\n"
                f"<原始输入:{input_file}>\n"
            )
        else:
            raise RuntimeError(f"未知 converter:{decision['converter']}")

        out_md.write_text(stub_body, encoding="utf-8")
        converted_relative = None
        if converted_target is not None:
            if decision["converter"] in ("anydoc", "paddleocr", "claude-native"):
                # 副本走相同 stub(本轮只做 IO 占位;SKILL.md 后续替换)
                converted_target.write_text(stub_body, encoding="utf-8")
                # 相对路径(相对 project_dir)便于 log 引用
                try:
                    cwd = Path.cwd()
                    converted_relative = str(converted_target.relative_to(cwd))
                except ValueError:
                    converted_relative = str(converted_target)

    return {
        "input": str(input_file),
        "format": decision["format"],
        "converter": decision["converter"],
        "native_text": decision["native_text"],
        "converted_path": converted_relative or str(out_md),
    }


def run_single(args: argparse.Namespace) -> dict[str, Any]:
    """单文件模式主流程。"""
    project = Path(args.project_dir).resolve()
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = project / input_path

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = project / output_dir

    emit_to: Path | None = None
    if args.emit_to is not None:
        emit_to = Path(args.emit_to)
        if not emit_to.is_absolute():
            emit_to = project / emit_to

    result = _convert_one(input_path, output_dir, emit_to)
    return result


def run_batch(args: argparse.Namespace) -> list[dict[str, Any]]:
    """批量模式:共享单 Engine 实例,每文件 1 行 JSON 输出。"""
    project = Path(args.project_dir).resolve()
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = project / output_dir

    emit_to: Path | None = None
    if args.emit_to is not None:
        emit_to = Path(args.emit_to)
        if not emit_to.is_absolute():
            emit_to = project / emit_to

    results: list[dict[str, Any]] = []
    for input_path_str in args.batch:
        input_path = Path(input_path_str)
        if not input_path.is_absolute():
            input_path = project / input_path
        result = _convert_one(input_path, output_dir, emit_to)
        results.append(result)

    return results


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="convert-to-md.py",
        description="inbox/<file> 转 markdown(扩展名分流);支持 --batch 与 --emit-to(G10)。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    parser.add_argument(
        "--input",
        default=None,
        help="单文件模式:输入文件相对路径(相对 --project-dir)。",
    )
    parser.add_argument(
        "--batch",
        nargs="*",
        default=None,
        help="批量模式:空格分隔的多个文件。",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="主输出目录,如 temp/。",
    )
    parser.add_argument(
        "--emit-to",
        default=None,
        help="(G10)同时写 <basename>.<ext>.converted.md 副本目录,如 temp/。",
    )
    args = parser.parse_args(argv)

    # 模式互斥校验
    if (args.input is None and not args.batch) or (
        args.input is not None and args.batch is not None
    ):
        parser.error("--input 与 --batch 必填其一,且互斥")

    if not args.output_dir:
        parser.error("--output-dir 必填")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.batch:
            results = run_batch(args)
            for r in results:
                print(json.dumps({"ok": True, **r}, ensure_ascii=False))
        else:
            result = run_single(args)
            result["ok"] = True
            emit_json(result)
    except FileNotFoundError as e:
        emit_json({"ok": False, "error": f"{e}"})
        return 1
    except ValueError as e:
        emit_json({"ok": False, "error": f"{e}"})
        return 1
    except OSError as e:
        emit_json({"ok": False, "error": f"文件系统错误:{e}"})
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""lint-query-output.py — C15.3 query 末尾标记校验:必须含 ❓ 或 💡。

CLI:
    python3 lint-query-output.py --project-dir . --input <last-response>.md

行为(DESIGN.md §1.1 + lint SKILL.md §1.12 + query SKILL.md §阶段 3):
    - 读 --input md 文件
    - 末尾(最后 1 个非空行)必须含 ❓ 或 💡 二者必居其一
    - 输出 JSON:
        命中 ❓ → marker=prompt, ok=true
        命中 💡 → marker=skip,  ok=true
        缺标记 → marker=missing, ok=false, exit 1

输出:
    stdout JSON:{"ok": bool, "marker": "prompt"|"skip"|"missing",
                 "last_line": "...", "errors": [...]}
    exit 0(命中)/ 1(缺标记)

约束(NFR-1 ~ NFR-7):
    - 只读输入文件,不写盘
    - 不读 stdin
    - 错误消息中文为主
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from _common import emit_json


# 末尾标记字符
PROMPT_MARKER = "❓"   # query 输出结尾的提问 prompt(建议落档 analysis)
SKIP_MARKER = "💡"      # query 输出结尾的提示(已落档 / 无需落档)


def _last_non_empty_line(text: str) -> str:
    """返回 text 的最后 1 行非空字符串。"""
    for ln in reversed(text.splitlines()):
        if ln.strip():
            return ln
    return ""


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口:C15.3 末尾标记校验。"""
    project = Path(args.project_dir).resolve()
    if not project.exists():
        raise FileNotFoundError(f"--project-dir 不存在:{project}")

    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = project / input_path
    if not input_path.exists():
        raise FileNotFoundError(f"--input 不存在:{input_path}")

    text = input_path.read_text(encoding="utf-8")
    last_line = _last_non_empty_line(text)

    marker: str = "missing"
    errors: list[str] = []

    if PROMPT_MARKER in last_line:
        marker = "prompt"
    elif SKIP_MARKER in last_line:
        marker = "skip"
    else:
        errors.append("末尾必须含 ❓ 或 💡 标记")

    ok = marker != "missing"

    return {
        "ok": ok,
        "marker": marker,
        "last_line": last_line,
        "errors": errors,
        "input_path": str(input_path.relative_to(project)).replace("\\", "/")
        if project in input_path.parents or input_path.is_relative_to(project)
        else str(input_path),
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="lint-query-output.py",
        description="C15.3:query 末尾标记校验(❓ 或 💡 二者必居其一)。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="query 输出的 md 文件路径(LLM response 末段)。",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = run(args)
    except FileNotFoundError as e:
        emit_json({"ok": False, "marker": "missing", "errors": [f"{e}"]})
        return 1
    except OSError as e:
        emit_json({"ok": False, "marker": "missing", "errors": [f"读取失败:{e}"]})
        return 1

    emit_json(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

"""query/path-b-detect.py — 路径 B 触发探测:对比类 query 累计 ≥ 3 次。

CLI:
    python3 query/path-b-detect.py --project-dir . \\
        --log <log-file> --x "SOME/IP" --y "DDS"

行为(DESIGN.md §1.1 + §4 + query SKILL.md §阶段 2 跳 4):
    - grep log.md `**Creation**: query "X.*Y"` 模式(全 **Creation** 而非 **Update**,
      避免旧数据误触发)
    - X.*Y 是对比对象对(如 "SOME/IP vs DDS" → `SOME/IP.*DDS`,正则需 escape)
    - 累计计数 → hit_count
    - 触发阈值 ≥ 3 次 → trigger=true
    - 输出 JSON:{"hit_count": N, "trigger": true|false, "matched_lines": [...]}

输出:
    stdout JSON
    exit 0 / 1

约束(NFR-1 ~ NFR-7):
    - 只读 log.md(默认 knowledge/log.md)
    - 不写盘
    - 不读 stdin
    - 错误消息中文为主
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any

# scripts/ 顶层 _common.py 注入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _common import emit_json  # noqa: E402


# 路径 B 触发阈值(累计 ≥ N 次 → trigger=true)
PATH_B_TRIGGER_THRESHOLD = 3

# log.md query 行前缀(LDF-format:**Creation**: query "X vs Y")
# 设计:同时校验该行含 **Creation**: query + X + Y(X 和 Y 任意顺序)
# 因为用户 query 形如 "SOME/IP vs DDS"(或 "DDS vs SOME/IP")是不定的;
# 简单 X.*?Y 顺序匹配会漏"DDS vs SOME/IP";严格 X.*Y 反向亦然
QUERY_LINE_RE_TEMPLATE = (
    r'(?=.*\*\s*\*\*Creation\*\*:\s*query)'
    r'(?=.*?{x})'
    r'(?=.*?{y})'
)


def _escape_regex(s: str) -> str:
    """把 X / Y 等用户输入转义成正则特殊字符安全的字符串。"""
    return re.escape(s)


def _build_query_pattern(x: str, y: str) -> re.Pattern[str]:
    """构造匹配 log.md query 行的正则(全 Creation,不匹配 Update)。"""
    px = _escape_regex(x)
    py = _escape_regex(y)
    pat = QUERY_LINE_RE_TEMPLATE.format(x=px, y=py)
    return re.compile(pat, re.IGNORECASE)


def _read_log_lines(log_path: Path) -> list[str]:
    """读 log 文件全部行,过滤空。"""
    if not log_path.exists():
        return []
    text = log_path.read_text(encoding="utf-8")
    return [ln for ln in text.splitlines() if ln.strip()]


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口:路径 B 触发探测。"""
    project = Path(args.project_dir).resolve()
    if not project.exists():
        raise FileNotFoundError(f"--project-dir 不存在:{project}")

    log_arg = args.log
    log_path = Path(log_arg)
    if not log_path.is_absolute():
        # 默认相对 project/knowledge/log.md(Windows / Linux 都用 os.path 判路径分隔)
        sep = os.sep
        if sep not in log_arg and "/" not in log_arg:
            log_path = project / "knowledge" / log_arg
        else:
            log_path = project / log_arg

    if not log_path.exists():
        return {
            "hit_count": 0,
            "trigger": False,
            "threshold": PATH_B_TRIGGER_THRESHOLD,
            "matched_lines": [],
            "reason": f"log 文件不存在:{log_path}",
        }

    x = (args.x or "").strip()
    y = (args.y or "").strip()
    if not x or not y:
        raise ValueError("--x 和 --y 不能为空")

    pattern = _build_query_pattern(x, y)

    lines = _read_log_lines(log_path)
    matched_lines: list[str] = []
    for ln in lines:
        if pattern.search(ln):
            matched_lines.append(ln.strip())

    hit_count = len(matched_lines)
    trigger = hit_count >= PATH_B_TRIGGER_THRESHOLD

    return {
        "hit_count": hit_count,
        "trigger": trigger,
        "threshold": PATH_B_TRIGGER_THRESHOLD,
        "matched_lines": matched_lines,
        "x": x,
        "y": y,
        "log_path": str(log_path.relative_to(project)).replace("\\", "/")
        if project in log_path.parents or log_path.is_relative_to(project)
        else str(log_path),
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="query/path-b-detect.py",
        description="跳 4:路径 B 触发探测(对比类 query 累计 ≥ 3 次)。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    parser.add_argument(
        "--log",
        default="knowledge/log.md",
        help="log 文件相对路径(默认 knowledge/log.md)。",
    )
    parser.add_argument(
        "--x",
        required=True,
        help="对比对象 X(如 'SOME/IP',可含特殊字符)。",
    )
    parser.add_argument(
        "--y",
        required=True,
        help="对比对象 Y(如 'DDS')。",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = run(args)
    except FileNotFoundError as e:
        emit_json({"ok": False, "error": f"{e}"})
        return 1
    except ValueError as e:
        emit_json({"ok": False, "error": f"{e}"})
        return 1
    except OSError as e:
        emit_json({"ok": False, "error": f"文件系统错误:{e}"})
        return 1

    emit_json(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())

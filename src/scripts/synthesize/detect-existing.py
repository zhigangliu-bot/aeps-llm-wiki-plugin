"""detect-existing.py — 检测 synthesis 页是否已存在 + 读现有 sources_count。

CLI:
    python3 detect-existing.py --project-dir . --slug "okf-生态全景"

行为(DESIGN.md §1.1 synthesize 组 + synthesize SKILL.md §阶段 2):
    - 检查 <project>/knowledge/syntheses/<slug>.md 是否存在
    - 存在时从 frontmatter 解析 `sources_count`(默认 0)
    - 不校验 frontmatter schema(留给 validate-frontmatter.py)
    - 不做自动写入(只读探测)
    - knowledge/syntheses/ 目录不存在视为 "不存在"

输出:
    stdout JSON:{
        "exists": bool,
        "current_sources_count": int,
        "path": "knowledge/syntheses/<slug>.md"  (相对 project)
    }
    exit 0

约束(NFR-1 ~ NFR-4):
    - 不读 stdin(NFR-1)
    - 不开 daemon(NFR-1)
    - 路径全部相对 --project-dir(NFR-4)
    - 只读探测;不写文件
    - 错误消息中文为主(NFR-3)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

# 子目录脚本:把 scripts/ 加入 sys.path 以复用 _common
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _common import emit_json  # noqa: E402


# 极简 frontmatter 块定位正则(--- 起 --- 止,只取第一个)
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)


def _parse_frontmatter(text: str) -> dict[str, str]:
    """极简 frontmatter 解析:找第一个 --- 块,逐行读 `key: value`。

    只支持一层的标量值(字符串 + 数字 + 布尔);列表/嵌套 dict 走 fallback 不报。
    这是 _common 没暴露的本地工具,仅供 detect 阶段读 sources_count。
    """
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    block = m.group(1)
    result: dict[str, str] = {}
    for line in block.splitlines():
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        # 仅识别顶层 `key: value`(顶层不带缩进)
        if line.startswith((" ", "\t")):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        # 去掉单引号 / 双引号包裹
        if len(value) >= 2 and (
            (value.startswith("'") and value.endswith("'"))
            or (value.startswith('"') and value.endswith('"'))
        ):
            value = value[1:-1]
        result[key.strip()] = value
    return result


def _coerce_sources_count(value: str | None) -> int:
    """把 frontmatter `sources_count` 字符串值转 int。失败返回 0。"""
    if value is None:
        return 0
    value = value.strip()
    if not value:
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


def detect_existing(project_dir: str, slug: str) -> dict[str, Any]:
    """探测 <project>/knowledge/syntheses/<slug>.md 是否存在。

    Args:
        project_dir: 项目根目录(默认 `.`)。
        slug: 已派生的 synthesis 页 slug。

    Returns:
        dict: {
            "exists": bool,
            "current_sources_count": int,
            "path": str  (相对 project 的路径)
        }
    """
    project = Path(project_dir).resolve()
    syntheses_dir = project / "knowledge" / "syntheses"
    target = syntheses_dir / f"{slug}.md"

    rel_path = "knowledge/syntheses/" + f"{slug}.md"

    if not target.exists():
        return {
            "exists": False,
            "current_sources_count": 0,
            "path": rel_path,
        }

    # 文件存在 → 读 frontmatter sources_count
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as e:
        # 读失败(权限 / IO 错)→ 视作 "exists but unreadable"
        # current_sources_count 默认为 0(探测阶段容忍,不抛错)
        return {
            "exists": True,
            "current_sources_count": 0,
            "path": rel_path,
            "read_error": f"{e}",
        }

    fm = _parse_frontmatter(text)
    cur_count = _coerce_sources_count(fm.get("sources_count"))
    return {
        "exists": True,
        "current_sources_count": cur_count,
        "path": rel_path,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口。"""
    if not args.slug or not args.slug.strip():
        raise ValueError("--slug 必填且非空")
    return detect_existing(args.project_dir, args.slug.strip())


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="detect-existing.py",
        description="探测 <project>/knowledge/syntheses/<slug>.md 是否存在 + 读 sources_count。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    parser.add_argument(
        "--slug",
        required=True,
        help="已派生的 synthesis 页 slug(全小写连字符 + 中文保留)。",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = run(args)
    except ValueError as e:
        emit_json({"ok": False, "error": str(e)})
        return 1

    result["ok"] = True
    emit_json(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
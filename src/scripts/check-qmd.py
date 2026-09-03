"""check-qmd.py — query 引擎决策器。

CLI:
    python3 check-qmd.py --project-dir .

行为(DESIGN.md §1.1 + §4 + query SKILL.md §阶段 0):
    - 数 <project>/knowledge/**/*.md 页数(排除 index/overview/glossary/log)
    - 探测 qmd --version(subprocess.run,允许 FileNotFoundError)
    - 按阈值常量返回 engine 决策:
        * N < 500                → engine=index(reason: 用 LLM 读 index 即可)
        * 500 <= N < 1000        → engine=qmd(若 qmd 装)/index(若未装,但建议装 qmd)
        * N >= 1000              → engine=qmd(若 qmd 装);否则 engine=fail(必须装 qmd)
    - qmd 未装但 N >= 1000 → exit 1(强制要求);
        其他场景全部 exit 0

输出:
    stdout JSON: {
        "pageCount": <N>,
        "qmdAvailable": true|false,
        "qmdVersion": "<version>" | null,
        "engine": "index" | "qmd" | "fail",
        "reason": "<一句话解释>"
    }
    exit 0 / 1

约束(NFR-1 ~ NFR-7):
    - 不读 stdin(NFR-1)
    - 单次运行即退(NFR-1)
    - 路径相对 --project-dir(NFR-4)
    - 错误消息中文为主(NFR-3)
    - 只用 stdlib + subprocess(NFR-7)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from _common import emit_json


# 阈值常量(DESIGN.md §4.3 query 引擎决策矩阵;与 query SKILL.md §阶段 0 完全一致)
QUERY_INDEX_THRESHOLD = 500
QUERY_QMD_REQUIRED_THRESHOLD = 1000

# 排除的固定页面(不计入页数)
EXCLUDED_FROM_COUNT = {"index.md", "overview.md", "glossary.md", "log.md"}


def _count_knowledge_pages(project: Path) -> int:
    """数 <project>/knowledge/**/*.md 页数(排除固定 4 张页)。

    包含所有 knowledge/ 叶子目录(sources / entities/* / concepts/* /
    syntheses / analyses / comparisons)下的 .md 文件,但排除 4 张固定页。
    """
    knowledge = project / "knowledge"
    if not knowledge.exists():
        return 0

    count = 0
    for md in knowledge.rglob("*.md"):
        if md.is_file() and md.name not in EXCLUDED_FROM_COUNT:
            count += 1
    return count


def _detect_qmd() -> tuple[bool, str | None]:
    """跑 qmd --version 探测是否安装。

    Returns:
        (qmd_available, version_str)
    """
    try:
        proc = subprocess.run(
            ["qmd", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, OSError):
        return (False, None)

    if proc.returncode != 0:
        return (False, None)

    out = (proc.stdout or "") + (proc.stderr or "")
    version = out.strip() or None
    # 提取首个 version 形如 0.x.y
    if version:
        parts = version.replace(",", " ").split()
        for p in parts:
            if p and p[0].isdigit() and "." in p:
                version = p.rstrip(",.;:") or None
                break
    return (True, version)


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口:engine 决策。"""
    project = Path(args.project_dir).resolve()
    if not project.exists():
        raise FileNotFoundError(f"--project-dir 不存在:{project}")

    page_count = _count_knowledge_pages(project)
    qmd_available, qmd_version = _detect_qmd()

    # 决策矩阵
    engine: str
    reason: str
    if page_count < QUERY_INDEX_THRESHOLD:
        engine = "index"
        if qmd_available:
            reason = (
                f"N={page_count} < {QUERY_INDEX_THRESHOLD},使用 index 模式;"
                f"qmd 已装但暂不需要"
            )
        else:
            reason = f"N={page_count} < {QUERY_INDEX_THRESHOLD},使用 index 模式"
    elif page_count < QUERY_QMD_REQUIRED_THRESHOLD:
        if qmd_available:
            engine = "qmd"
            reason = (
                f"{QUERY_INDEX_THRESHOLD} <= N={page_count} < "
                f"{QUERY_QMD_REQUIRED_THRESHOLD},qmd 已装,用 qmd 模式"
            )
        else:
            engine = "index"
            reason = (
                f"{QUERY_INDEX_THRESHOLD} <= N={page_count} < "
                f"{QUERY_QMD_REQUIRED_THRESHOLD},qmd 未装,降级到 index 模式(建议装 qmd)"
            )
    else:
        # N >= 1000
        if qmd_available:
            engine = "qmd"
            reason = (
                f"N={page_count} >= {QUERY_QMD_REQUIRED_THRESHOLD},qmd 已装,用 qmd 模式"
            )
        else:
            engine = "fail"
            reason = (
                f"N={page_count} >= {QUERY_QMD_REQUIRED_THRESHOLD},"
                f"qmd 未装 — 强制要求安装 qmd"
            )

    return {
        "pageCount": page_count,
        "qmdAvailable": qmd_available,
        "qmdVersion": qmd_version,
        "engine": engine,
        "reason": reason,
        "thresholds": {
            "QUERINDEX": QUERY_INDEX_THRESHOLD,
            "QUERY_QMD_REQUIRED": QUERY_QMD_REQUIRED_THRESHOLD,
        },
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="check-qmd.py",
        description="query 引擎决策器(数 knowledge 页数 + 探测 qmd 可用性 + 阈值决策)。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
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
    # engine == fail → 非 0 退出码
    if result.get("engine") == "fail":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

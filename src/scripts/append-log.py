"""append-log.py — 向 knowledge/log.md 追加一条变更记录。

CLI:
    python3 append-log.py --project-dir . --action <prefix>
        [--source <path>] [--dest <path>] [--actor <id>] [--summary <text>]

行为(DESIGN.md §1.1 + §2.6):
    - 6 种前缀枚举:Creation / Update / Deprecation / Migration / LintFix / Converted / IngestFailure
    - 写盘格式:`* **<prefix>**: <one-line summary>`
    - append,**最新在前**(在 frontmatter 与第一个 H2 之间插入)
    - 默认 actor = agent: producer/aeps-llm-wiki-plugin/0.5.5
    - 若 log.md 不存在 → 报错(exit 1,init 应先建好)

输出:
    stdout JSON: {"appended": true, "line": "...", "path": "knowledge/log.md"}
    exit 0 / 1

约束(NFR-1 ~ NFR-5):
    - 不读 stdin(NFR-1)
    - 不开 daemon(NFR-1)
    - 路径全部相对 --project-dir(NFR-4)
    - 临时文件进 <project>/temp/(NFR-5);log.md 不属于 temp,由 --project-dir 直管
    - 错误消息中文为主(NFR-3)
    - 走 Q7 死循环防护:append 用 atomic_write_preserving_mtime 保留 mtime
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from _common import atomic_write_preserving_mtime, emit_json


PLUGIN_VERSION = "0.5.5"
PLUGIN_NAME = "aeps-llm-wiki-plugin"
DEFAULT_ACTOR = f"agent: producer/{PLUGIN_NAME}/{PLUGIN_VERSION}"

# 7 种前缀(DESIGN.md §2.6;Converted 是 G10 配套,第 7 种 IngestFailure 是 v0.5.4 PATCH)
LOG_ACTIONS = (
    "Creation",
    "Update",
    "Deprecation",
    "Migration",
    "LintFix",
    "Converted",
    "IngestFailure",
)

# actor 字符串正则(DESIGN.md §2.6 引 SCHEMA.md §4)
ACTOR_PATTERN = re.compile(
    r"^(agent:\sproducer/[a-z0-9-]+/[0-9]+\.[0-9]+\.[0-9]+|human:.+|process:.+)$"
)


def _build_line(action: str, summary: str, actor: str) -> str:
    """构造一行 log 记录(`* **<action>**: <summary>`)。"""
    summary = (summary or "").strip()
    if not summary:
        summary = "(无 summary)"
    return f"* **{action}**: {summary} by {actor}\n"


def _insert_after_frontmatter(text: str, line: str) -> str:
    """把一行新记录插入到 frontmatter 之外的"最新在前"位置。

    策略:
        - 若文件以 frontmatter (---...---) 开头 → 插在 frontmatter 之后、第一个 H2 之前
        - 若无 frontmatter → 插到文件最前

    这样保证最新记录出现在 log.md 顶部,且不破坏 YAML 结构。
    """
    lines = text.splitlines(keepends=True)

    # 找第一个 H2 标题(## YYYY-MM-DD)
    for i, ln in enumerate(lines):
        if ln.startswith("## "):
            insertion_idx = i
            break
    else:
        # 没找到 H2 → 检查 frontmatter
        if lines and lines[0].startswith("---"):
            for j in range(1, len(lines)):
                if lines[j].startswith("---"):
                    insertion_idx = j + 1
                    break
            else:
                insertion_idx = len(lines)
        else:
            insertion_idx = 0

    # 跳过相邻空行,保证一行紧贴 H2 之上
    while insertion_idx > 0 and lines[insertion_idx - 1].strip() == "":
        insertion_idx -= 1

    new_lines = lines[:insertion_idx] + [line, "\n"] + lines[insertion_idx:]
    return "".join(new_lines)


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口:append 一行到 knowledge/log.md。"""
    project = Path(args.project_dir).resolve()
    log_path = project / "knowledge" / "log.md"

    if not log_path.exists():
        raise FileNotFoundError(
            f"log.md 不存在,需要先跑 init:{log_path}"
        )

    action = args.action
    if action not in LOG_ACTIONS:
        raise ValueError(
            f"--action 非法:{action};合法值 = {LOG_ACTIONS}"
        )

    actor = (args.actor or DEFAULT_ACTOR).strip()
    if not ACTOR_PATTERN.match(actor):
        # 没有完整正则匹配时,降级 fallback:默认用 plugin 默认 actor
        # 但允许简化的 human:xxx(只要符合通用模式)
        if not (
            actor.startswith("human:")
            or actor.startswith("process:")
            or actor.startswith("agent:")
        ):
            raise ValueError(
                f"--actor 格式不合法:{actor};需符合 agent: producer/<plugin>/<ver> 或 human:<id> 或 process:<id>"
            )

    # 拼装 summary
    parts: list[str] = []
    if args.summary:
        parts.append(args.summary.strip())
    else:
        summary_bits: list[str] = []
        if args.source:
            summary_bits.append(f"<{args.source}>")
        if args.dest:
            summary_bits.append(f"→ <{args.dest}>")
        if summary_bits:
            parts.append(" ".join(summary_bits))
    if not parts:
        parts.append("由 append-log.py 追加(无 summary)")

    summary_text = " ".join(parts)
    line = _build_line(action, summary_text, actor)

    # 读取 → 插入 → atomic write(Q7 防护)
    try:
        text = log_path.read_text(encoding="utf-8")
    except OSError as e:
        raise OSError(f"读取 log.md 失败:{e}")

    new_text = _insert_after_frontmatter(text, line)

    try:
        atomic_write_preserving_mtime(log_path, new_text)
    except OSError as e:
        raise OSError(f"写 log.md 失败:{e}")

    return {
        "appended": True,
        "line": line.strip(),
        "path": "knowledge/log.md",
        "actor": actor,
        "action": action,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="append-log.py",
        description="向 knowledge/log.md 追加一条变更记录(7 种前缀,最新在前)。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=LOG_ACTIONS,
        help="log 记录前缀(7 种合法值)。",
    )
    parser.add_argument(
        "--source",
        default=None,
        help="(可选)源路径字符串,用于 summary 自动拼装。",
    )
    parser.add_argument(
        "--dest",
        default=None,
        help="(可选)目标路径字符串,用于 summary 自动拼装。",
    )
    parser.add_argument(
        "--actor",
        default=None,
        help="(可选)actor 字符串;缺省 agent: producer/aeps-llm-wiki-plugin/<version>。",
    )
    parser.add_argument(
        "--summary",
        default=None,
        help="(可选)自定 summary 文本;优先于 --source/--dest 拼装结果。",
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

    result["ok"] = True
    emit_json(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())

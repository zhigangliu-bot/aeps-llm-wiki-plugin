"""append-index.py — append knowledge/index.md 一行 synthesis 条目。

CLI:
    python3 append-index.py --project-dir . \\
        --slug "okf-生态全景" \\
        --sources-count 5 \\
        --summary "OKF 生态全景综合页"

行为(DESIGN.md §1.1 synthesize 组 + synthesize SKILL.md §阶段 4.3):
    - 路径:<project>/knowledge/index.md(主索引,plugin 生成 + 用户可补)
    - 追加格式:`- [slug](syntheses/<slug>.md) — type: synthesis · sources_count: N · <summary 一句话>`
    - 幂等:同 slug 重复 append → skip(检测已存在则不再追加)
    - index.md 不存在 → 报错(FileNotFoundError,exit 1)
    - 写盘走 atomic_write_preserving_mtime(Q7 atime + mtime 双还原)

输出:
    stdout JSON:{
        "appended": bool,
        "line": "<完整一行>",
        "already_present": bool,
        "path": "knowledge/index.md"
    }
    exit 0 / 1

约束(NFR-1 ~ NFR-5):
    - 不读 stdin(NFR-1)
    - 不开 daemon(NFR-1)
    - 路径全部相对 --project-dir(NFR-4)
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

from _common import atomic_write_preserving_mtime, emit_json  # noqa: E402


# 同一 slug 的索引行匹配正则:`- [<slug>](syntheses/<slug>.md)` 开头
INDEX_LINE_RE = re.compile(
    r"^\s*-\s*\[([^\]]+)\]\(syntheses/([^)]+)\)"
)


def _build_line(slug: str, sources_count: int, summary: str) -> str:
    """构造一行 index 条目。"""
    summary_clean = (summary or "").strip()
    if not summary_clean:
        summary_clean = "<一句话主题脉络>"
    return (
        f"- [{slug}](syntheses/{slug}.md) "
        f"— type: synthesis · sources_count: {int(sources_count)} "
        f"· {summary_clean}\n"
    )


def _is_already_present(text: str, slug: str) -> bool:
    """检查 index.md 内是否已有同 slug 的条目(幂等检测)。"""
    for line in text.splitlines():
        m = INDEX_LINE_RE.match(line)
        if m:
            # m.group(1) = slug 显示文本;m.group(2) = slug 文件名(无 .md)
            if m.group(2) == slug or m.group(1) == slug:
                return True
    return False


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口。"""
    project = Path(args.project_dir).resolve()
    index_path = project / "knowledge" / "index.md"

    if not index_path.exists():
        raise FileNotFoundError(
            f"index.md 不存在,需要先跑 init:{index_path}"
        )

    slug = args.slug.strip()
    if not slug:
        raise ValueError("--slug 必填且非空")

    sources_count = int(args.sources_count)
    if sources_count < 0:
        raise ValueError("--sources-count 必须是非负 int")

    summary = args.summary or ""

    # 读原文件
    try:
        text = index_path.read_text(encoding="utf-8")
    except OSError as e:
        raise OSError(f"读取 index.md 失败:{e}")

    # 幂等检测
    if _is_already_present(text, slug):
        return {
            "appended": False,
            "already_present": True,
            "line": "",
            "path": "knowledge/index.md",
            "ok": True,
        }

    # 构造新行 + 追加
    new_line = _build_line(slug, sources_count, summary)

    # 在 frontmatter 之后的"主索引"区域插入;若无 frontmatter → 追加到文件末尾
    if text.startswith("---"):
        # 找第一个 H2 之前插入(latest-first)
        lines = text.splitlines(keepends=True)
        insert_idx = len(lines)
        for i, ln in enumerate(lines):
            if ln.startswith("## "):
                insert_idx = i
                break
        # 跳过相邻空行
        while insert_idx > 0 and lines[insert_idx - 1].strip() == "":
            insert_idx -= 1
        new_lines = lines[:insert_idx] + [new_line, "\n"] + lines[insert_idx:]
        new_text = "".join(new_lines)
    else:
        # 无 frontmatter → 追加到末尾
        new_text = text.rstrip("\n") + "\n" + new_line

    # 写盘:走 Q7 死循环防护(atime + mtime 双还原)
    atomic_write_preserving_mtime(index_path, new_text)

    return {
        "appended": True,
        "already_present": False,
        "line": new_line.rstrip("\n"),
        "path": "knowledge/index.md",
        "ok": True,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="append-index.py",
        description=(
            "append knowledge/index.md 一行 synthesis 条目"
            "(幂等检测 + atomic write 保留 mtime)。"
        ),
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    parser.add_argument(
        "--slug",
        required=True,
        help="synthesis 页 slug。",
    )
    parser.add_argument(
        "--sources-count",
        required=True,
        type=int,
        help="本次 synthesis 页引用页数(非负 int)。",
    )
    parser.add_argument(
        "--summary",
        default="",
        help="一句话主题脉络(显示在 index 行尾)。",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = run(args)
    except FileNotFoundError as e:
        emit_json({"ok": False, "error": str(e)})
        return 1
    except ValueError as e:
        emit_json({"ok": False, "error": str(e)})
        return 1
    except OSError as e:
        emit_json({"ok": False, "error": f"文件系统错误:{e}"})
        return 1

    result["ok"] = True
    emit_json(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
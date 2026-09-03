"""ingest/cleanup.py — temp/ 目录清理策略。

CLI:
    # 默认清理:删 OCR 中间产物 + G10 副本 + 已合并 proposal
    python3 ingest/cleanup.py --project-dir .

    # 保留所有 sanitized / corrupt.bak / raw_backup / decision JSON
    python3 ingest/cleanup.py --project-dir . [--keep-sanitized] [--keep-decision]

行为(DESIGN.md §2.3 temp/ 8 种文件清单 + §阶段 4):
    默认清理(删):
        - temp/<basename>.md                           (OCR 中间产物)
        - temp/<basename>.<ext>.converted.md           (G10 转换副本;G10 副本随原文件迁到 raw/ 后,清 inbox 副本)
        - temp/proposal-<doc-id>.json                  (已合并的 proposal)

    默认保留(不删):
        - temp/proposal-<doc-id>.json.sanitized        (供用户复查)
        - temp/proposal-<doc-id>.json.corrupt.bak      (供用户人工排查)
        - temp/raw_backup_<hash>/                      (可回滚备份,用户手动)
        - temp/plan-*.json / temp/decision-*.json      (审计文件,默认保留)

    标志位:
        --keep-sanitized=True(默认)                   保留 .sanitized 副本
        --keep-decision=True(默认)                    保留 decision-*.json
        --no-keep-decision                            删除 decision-*.json(慎用)
        --no-keep-sanitized                           删除 .sanitized 副本

    走 Q7 死循环防护:虽然只删,但 log.md append 一行记录(由主流程触发,本脚本不直接调
    append-log,避免循环)。

输出:
    stdout JSON: {
        "deleted": [..files..],
        "kept": [..files..],
        "skipped": [..files..],   # 保留策略匹配上的
        "errors": [..msgs..]
    }
    exit 0 / 1

约束(NFR-1 ~ NFR-7):
    - 不读 stdin(NFR-1)
    - 不开 daemon(NFR-1)
    - 路径全部相对 --project-dir(NFR-4)
    - 错误消息中文为主(NFR-3)
"""

from __future__ import annotations

import argparse
import fnmatch
import sys
from pathlib import Path
from typing import Any

# scripts/ 顶层 _common.py 注入(sys.path)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _common import emit_json  # noqa: E402


# 删除模式(glob,相对 temp/)
DELETE_PATTERNS_DEFAULT = (
    "*.md",                              # temp/<basename>.md(OCR 中间产物)
    "*.converted.md",                    # temp/<basename>.<ext>.converted.md(G10 副本)
    "proposal-*.json",                   # 已合并的 proposal(非 .sanitized / .corrupt.bak)
)

# 保留模式(glob,优先于 DELETE_PATTERNS_DEFAULT)
KEEP_PATTERNS_DEFAULT = (
    "!.gitkeep",
    "!proposal-*.json.sanitized",        # 供用户复查
    "!proposal-*.json.corrupt.bak",      # 供用户人工排查
    "!raw_backup_*",                     # 可回滚备份目录
    "!raw_backup_*/**",                  # 备份目录内所有文件
    "!decision-*.json",                  # 审计文件(默认保留)
    "!plan-*.json",                      # 审计文件
    "!.gitignore",                       # temp/.gitignore 5 行规范
)


def _glob_to_regex(pattern: str) -> str:
    """简单 glob → regex 转换(支持 * 和 ? 通配符)。"""
    import re

    # 去掉前导 ! 标记(keep 模式)
    is_negation = pattern.startswith("!")
    if is_negation:
        pattern = pattern[1:]

    # 转义 regex 特殊字符,但保留 * 和 ?
    regex = ""
    for ch in pattern:
        if ch == "*":
            regex += ".*"
        elif ch == "?":
            regex += "."
        elif ch in r".^$+{}[]|()\\":
            regex += "\\" + ch
        else:
            regex += ch
    return regex


def _match_any(path: Path, patterns: list[str]) -> bool:
    """path 的 basename 或相对路径是否匹配任一 pattern。"""
    name = path.name
    rel = str(path).replace("\\", "/")
    for pat in patterns:
        regex = _glob_to_regex(pat)
        import re
        if re.match(f"^{regex}$", name) or re.match(f"^{regex}$", rel):
            return True
    return False


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口:扫描 temp/ 按策略删/留。"""
    project = Path(args.project_dir).resolve()
    if not project.exists():
        raise FileNotFoundError(f"--project-dir 不存在:{project}")

    temp_dir = project / "temp"
    if not temp_dir.exists():
        # temp/ 不存在不算错误(可能是 init 后还没跑过 ingest)
        return {
            "deleted": [],
            "kept": [],
            "skipped": [],
            "errors": [],
            "temp_existed": False,
        }

    # 收集 keep 模式(根据 CLI 调整)
    keep_patterns = list(KEEP_PATTERNS_DEFAULT)
    delete_patterns = list(DELETE_PATTERNS_DEFAULT)

    if not args.keep_sanitized:
        # 从 keep 移除 sanitized(允许删)
        keep_patterns = [
            p for p in keep_patterns
            if p != "!proposal-*.json.sanitized"
        ]
        # 显式 delete .sanitized
        delete_patterns = list(delete_patterns) + ["proposal-*.json.sanitized"]

    if not args.keep_decision:
        # 从 keep 移除 decision-*.json
        keep_patterns = [
            p for p in keep_patterns
            if p != "!decision-*.json"
        ]
        # 显式 delete decision
        delete_patterns = list(delete_patterns) + ["decision-*.json"]

    deleted: list[str] = []
    kept: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    # 遍历 temp/ 所有文件(递归,覆盖 raw_backup_* 子目录场景)
    for path in sorted(temp_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(temp_dir)).replace("\\", "/")
        # 跳过目录自身(虽然 is_file 过滤了)

        if _match_any(path, keep_patterns):
            kept.append(rel)
            continue

        if _match_any(path, delete_patterns):
            try:
                path.unlink()
                deleted.append(rel)
            except OSError as e:
                errors.append(f"删除失败 {rel}:{e}")
        else:
            # 既不在 keep 也不在 delete → 保守保留(报告但不删)
            skipped.append(rel)

    return {
        "deleted": deleted,
        "kept": kept,
        "skipped": skipped,
        "errors": errors,
        "temp_existed": True,
        "keep_sanitized": args.keep_sanitized,
        "keep_decision": args.keep_decision,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="cleanup.py",
        description="temp/ 目录清理(默认删 OCR 中间 + G10 副本 + 已合并 proposal;保留 sanitized/bak/backup/decision)。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    parser.add_argument(
        "--keep-sanitized",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="保留 temp/proposal-*.json.sanitized(默认 True;--no-keep-sanitized 删)。",
    )
    parser.add_argument(
        "--keep-decision",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="保留 temp/decision-*.json(默认 True;--no-keep-decision 删)。",
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

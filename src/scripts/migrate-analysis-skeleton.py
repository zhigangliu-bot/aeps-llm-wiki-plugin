"""migrate-analysis-skeleton.py — v0.4.0 → v0.5.0 G11 旧骨架迁移。

CLI:
    python3 migrate-analysis-skeleton.py --project-dir . \\
        --from v0.4.0 --to v0.5.0 --file <path> [--apply]

行为(DESIGN.md §1.1 + query SKILL.md §阶段 4.4):
    - 检测 analysis 页是否含 v0.4.0 旧骨架(`## 重点摘录` + `## 我的思考`)
    - 迁移策略(默认 dry-run,只输出迁移提案;--apply 才写盘):
        * `## 重点摘录` → `## 方案推演 / 架构分析`
        * `## 我的思考`  → `## 关联溯源`
        * 新增 `## 总结:最有收获的一句话` 末尾 H2
        * 在 ## 关联溯源 段末尾追加 `> 引用:` 行(若缺);数据从 sources_used 抽
    - 输出 JSON:{"ok": true, "is_v040": true,
                 "h2_migrated": [...],
                 "proposal_file": "<path>"}
    - 缺 --from v0.4.0 → exit 1 中文报错
    - 写盘走 Q7 死循环防护:atomic_write_preserving_mtime

输出:
    stdout JSON
    exit 0(已是 v0.5.0 OR dry-run 提案生成)/ 1(缺 --from v0.4.0)

约束(NFR-1 ~ NFR-7):
    - 只动 knowledge/analyses/*.md(Q7)
    - 不读 stdin
    - 不开 daemon
    - 错误消息中文为主
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from _common import atomic_write_preserving_mtime, emit_json


# v0.4.0 旧 2 H2
V040_H2_ZHAIYAO = "## 重点摘录"
V040_H2_THINK = "## 我的思考"

# G11 v0.5.0 新 3 H2
V050_H2_DEDUCTION = "## 方案推演 / 架构分析"
V050_H2_REFERENCE = "## 关联溯源"
V050_H2_SUMMARY = "## 总结:最有收获的一句话"

# > 引用: 行
REFERENCE_LINE_RE = re.compile(r"^>\s*引用[::]\s*(.+?)$", re.MULTILINE)

# frontmatter 极简解析
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _is_v040_skeleton(text: str) -> bool:
    """是否含 v0.4.0 旧骨架(`## 重点摘录` + `## 我的思考`)。"""
    return V040_H2_ZHAIYAO in text and V040_H2_THINK in text


def _parse_minimal_frontmatter(text: str) -> dict[str, list[str] | str]:
    """极简 frontmatter 解析(只关心 sources_used / answer_to 用作 fallback)。"""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    block = m.group(1)
    fm: dict[str, Any] = {}
    cur_key: str | None = None
    for ln in block.splitlines():
        if not ln.strip():
            cur_key = None
            continue
        if ln.startswith("  - ") and cur_key:
            item = ln[4:].strip()
            v = fm.get(cur_key)
            if isinstance(v, list):
                v.append(item)
            continue
        if ":" in ln:
            k, _, v = ln.partition(":")
            k = k.strip()
            v = v.strip()
            if not v:
                fm[k] = []
                cur_key = k
            else:
                cur_key = None
                if v.startswith("'") and v.endswith("'"):
                    v = v[1:-1]
                elif v.startswith('"') and v.endswith('"'):
                    v = v[1:-1]
                fm[k] = v
        else:
            cur_key = None
    return fm


def _migrate(text: str) -> tuple[str, list[str]]:
    """执行 v0.4.0 → v0.5.0 G11 迁移;返回 (new_text, h2_migrated)。"""
    migrated: list[str] = []
    new_text = text

    # 1. ## 重点摘录 → ## 方案推演 / 架构分析
    if V040_H2_ZHAIYAO in new_text:
        new_text = new_text.replace(V040_H2_ZHAIYAO, V050_H2_DEDUCTION)
        migrated.append(f"{V040_H2_ZHAIYAO} → {V050_H2_DEDUCTION}")

    # 2. ## 我的思考 → ## 关联溯源
    if V040_H2_THINK in new_text:
        new_text = new_text.replace(V040_H2_THINK, V050_H2_REFERENCE)
        migrated.append(f"{V040_H2_THINK} → {V050_H2_REFERENCE}")

    # 3. 检查是否缺 ## 总结:最有收获的一句话(若缺则追加到正文末尾)
    if V050_H2_SUMMARY not in new_text:
        new_text = new_text.rstrip() + f"\n\n{V050_H2_SUMMARY}\n\n<一句话核心结论>\n"
        migrated.append(f"新增末尾 H2: {V050_H2_SUMMARY}")

    # 4. 若 ## 关联溯源 段末尾缺 > 引用: 行 → 追加
    # 参考 sources_used 数据(从 frontmatter 抽)
    fm = _parse_minimal_frontmatter(new_text)
    sources_used = fm.get("sources_used", [])
    if not isinstance(sources_used, list):
        sources_used = []

    ref_match = REFERENCE_LINE_RE.search(new_text)
    if not ref_match:
        ref_line = "> 引用: " + ", ".join(sources_used) if sources_used else "> 引用: <待补>"
        # 插到 ## 关联溯源 段末尾(若无 ## 关联溯源 段则插到全文末尾)
        seg_re = re.compile(
            r"(##\s*关联溯源\s*\n.+?)(?=\n##\s|\Z)", re.DOTALL
        )
        seg_m = seg_re.search(new_text)
        if seg_m:
            section = seg_m.group(1).rstrip()
            new_section = section + "\n\n" + ref_line + "\n"
            new_text = new_text[: seg_m.start(1)] + new_section + new_text[seg_m.end(1):]
        else:
            new_text = new_text.rstrip() + f"\n\n{V050_H2_REFERENCE}\n\n{ '<依据>' }\n\n{ref_line}\n"
        migrated.append("追加 > 引用: 行(从 sources_used 抽)")

    return new_text, migrated


def _build_proposal(target_rel: str, migrated: list[str], is_v040: bool) -> Path | None:
    """在 temp/ 写一份 .migrate-proposal.json(供用户拍板 / 审计)。

    Args:
        target_rel: 相对 project 的目标文件路径
        migrated: H2 迁移明细列表
        is_v040: 是否确为 v0.4.0 旧骨架
    Returns:
        proposal 文件路径(若 is_v040=False 则不写,返回 None)
    """
    if not is_v040:
        return None
    return None  # 此脚本不再独立写 proposal 文件;h2_migrated 已在 stdout 返回


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口。"""
    project = Path(args.project_dir).resolve()
    if not project.exists():
        raise FileNotFoundError(f"--project-dir 不存在:{project}")

    from_v = (args.from_v or "").strip()
    if not from_v:
        raise ValueError("缺少 --from 版本号(如 --from v0.4.0)")
    if from_v != "v0.4.0":
        # 当前仅实现 v0.4.0 → v0.5.0;其他来源版本 → 提前报错(防误用)
        return {
            "ok": False,
            "is_v040": False,
            "h2_migrated": [],
            "error": f"本脚本仅支持 --from v0.4.0,实际={from_v}",
        }

    to_v = (args.to_v or "v0.5.0").strip()

    target_path = Path(args.file)
    if not target_path.is_absolute():
        target_path = project / target_path
    if not target_path.exists():
        raise FileNotFoundError(f"--file 不存在:{target_path}")

    text = target_path.read_text(encoding="utf-8")
    is_v040 = _is_v040_skeleton(text)

    if not is_v040:
        return {
            "ok": True,
            "is_v040": False,
            "h2_migrated": [],
            "to": to_v,
            "reason": "页面不含 v0.4.0 旧骨架(## 重点摘录 + ## 我的思考),无需迁移",
            "file": str(target_path.relative_to(project)).replace("\\", "/"),
        }

    new_text, migrated = _migrate(text)

    apply = bool(getattr(args, "apply", False))
    if apply:
        # Q7 防护写盘
        atomic_write_preserving_mtime(target_path, new_text)

    return {
        "ok": True,
        "is_v040": True,
        "h2_migrated": migrated,
        "to": to_v,
        "dry_run": not apply,
        "applied": apply,
        "file": str(target_path.relative_to(project)).replace("\\", "/"),
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="migrate-analysis-skeleton.py",
        description="G11 v0.4.0 → v0.5.0 analysis 骨架迁移(默认 dry-run;--apply 写盘)。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    parser.add_argument(
        "--from",
        dest="from_v",
        required=True,
        help="源版本号(必填 v0.4.0)。",
    )
    parser.add_argument(
        "--to",
        dest="to_v",
        default="v0.5.0",
        help="目标版本号(默认 v0.5.0)。",
    )
    parser.add_argument(
        "--file",
        required=True,
        help="目标 analysis 页相对路径(相对 --project-dir)。",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="实际写盘(默认 dry-run,只输出提案)。",
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
    if not result.get("ok", False):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

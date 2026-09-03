"""ingest/dedupe_concepts.py — 跨 proposal 合并去重 concept(同 name+type+subtype 视为同一概念)。

CLI:
    python3 ingest/dedupe_concepts.py --project-dir . \\
        --proposals-glob 'temp/proposal-*.json'

行为(DESIGN.md §1.1 + §2.1):
    - 读 glob 命中的所有 proposal JSON
    - 合并所有 concepts 数组
    - 去重规则:同 (name, type, subtype) 三元组 → 同一概念;aliases 走并集 + 去重
    - 不写盘(纯计算);SKILL.md 拿结果后用 validate-proposal.py 改写单个 proposal
    - 不读 inbox 任何文件
    - 不调 OCR / 任何转换器

输出:
    stdout JSON: {
        "concepts": [...deduped...],
        "merged_count": <N>,        # 去重后总数
        "original_count": <M>,      # 去重前总数
        "files_processed": <K>,     # 读了多少 proposal
        "merge_log": [              # 合并明细
            {"kept": "<name>", "merged_from": ["<name>", ...]}
        ]
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
import glob
import json
import os
import sys
from pathlib import Path
from typing import Any

# scripts/ 顶层 _common.py 注入(sys.path)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _common import emit_json  # noqa: E402


def _list_proposals(project: Path, glob_pattern: str) -> list[Path]:
    """列出匹配 glob 的 proposal JSON 路径。

    glob_pattern 可为绝对路径或相对路径(相对 project_dir 或 cwd)。
    """
    # 绝对路径:直接 glob
    if os.path.isabs(glob_pattern):
        return sorted(Path(p) for p in glob.glob(glob_pattern))
    # 相对路径:先试相对 project_dir,再试相对 cwd
    candidates = [
        project / glob_pattern,
        Path.cwd() / glob_pattern,
    ]
    seen: set[Path] = set()
    results: list[Path] = []
    for base in candidates:
        # 把 glob 模式拆 base + pattern
        pattern = str(base)
        for p in glob.glob(pattern):
            pp = Path(p).resolve()
            if pp not in seen:
                seen.add(pp)
                results.append(pp)
    return sorted(results)


def _read_proposal(path: Path) -> dict[str, Any] | None:
    """读取单个 proposal JSON;失败返回 None(跳过损坏文件)。"""
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _merge_aliases(*alias_lists: list[str]) -> list[str]:
    """多个 aliases 列表取并集并保持稳定顺序。"""
    seen: set[str] = set()
    out: list[str] = []
    for lst in alias_lists:
        for a in lst or []:
            if not isinstance(a, str):
                continue
            if a in seen:
                continue
            seen.add(a)
            out.append(a)
    return out


def _key(c: dict[str, Any]) -> tuple[str, str, str]:
    """concept 去重 key:(name, type, subtype) 三元组。"""
    name = str(c.get("name", "")).strip()
    tp = str(c.get("type", "")).strip()
    subtype = str(c.get("subtype", "")).strip()
    return (name, tp, subtype)


def dedupe_concepts(proposals: list[dict[str, Any]]) -> dict[str, Any]:
    """合并去重 concepts 数组。

    Returns:
        dict {concepts, merged_count, original_count, merge_log}
    """
    # bucket: key → {name, type, subtype, aliases 累积集合, sources 引用}
    bucket: dict[tuple[str, str, str], dict[str, Any]] = {}
    original_count = 0
    merge_log: list[dict[str, Any]] = []

    for p in proposals:
        concepts = p.get("concepts", [])
        if not isinstance(concepts, list):
            continue
        for c in concepts:
            if not isinstance(c, dict):
                continue
            # 仅处理 type=concept 的项(entity 由 dedupe_entities 处理)
            if c.get("type") != "concept":
                continue
            k = _key(c)
            if not k[0]:
                # 缺 name → 跳过
                continue
            original_count += 1
            aliases = c.get("aliases", [])
            if not isinstance(aliases, list):
                aliases = []

            if k not in bucket:
                bucket[k] = {
                    "name": k[0],
                    "type": k[1],
                    "subtype": k[2],
                    "aliases": list(aliases),
                    "_seen_in": 1,
                }
            else:
                # 合并 aliases + 记录合并源
                existing = bucket[k]
                existing_aliases = existing.get("aliases", [])
                merged = _merge_aliases(existing_aliases, aliases)
                # 检测是否真有新增(否则不必记入 log)
                if len(merged) > len(existing_aliases):
                    existing["aliases"] = merged
                existing["_seen_in"] = existing.get("_seen_in", 1) + 1
                merge_log.append({
                    "kept": k[0],
                    "merged_from": [k[0]],
                    "seen_count": existing["_seen_in"],
                })

    deduped: list[dict[str, Any]] = []
    for entry in bucket.values():
        deduped.append({
            "name": entry["name"],
            "type": entry["type"],
            "subtype": entry["subtype"],
            "aliases": entry["aliases"],
        })

    return {
        "concepts": deduped,
        "merged_count": len(deduped),
        "original_count": original_count,
        "merge_log": merge_log,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口。"""
    project = Path(args.project_dir).resolve()
    if not project.exists():
        raise FileNotFoundError(f"--project-dir 不存在:{project}")

    paths = _list_proposals(project, args.proposals_glob)
    if not paths:
        # 空输入不算错误,返回空列表
        return {
            "concepts": [],
            "merged_count": 0,
            "original_count": 0,
            "files_processed": 0,
            "merge_log": [],
        }

    proposals: list[dict[str, Any]] = []
    for p in paths:
        data = _read_proposal(p)
        if data is not None:
            proposals.append(data)

    result = dedupe_concepts(proposals)
    result["files_processed"] = len(proposals)
    result["proposal_files"] = [str(p) for p in paths]
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dedupe_concepts.py",
        description="跨 proposal 合并去重 concept(同 name+type+subtype 视为同一概念,aliases 走并集)。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    parser.add_argument(
        "--proposals-glob",
        default="temp/proposal-*.json",
        help="proposal JSON 的 glob 模式(默认 temp/proposal-*.json)。",
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

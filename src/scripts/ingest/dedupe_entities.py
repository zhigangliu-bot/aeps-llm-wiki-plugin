"""ingest/dedupe_entities.py — 跨 proposal 合并去重 entity(同 name+type+subtype 视为同一实体)。

CLI:
    python3 ingest/dedupe_entities.py --project-dir . \\
        --proposals-glob 'temp/proposal-*.json'

行为(DESIGN.md §1.1 + §2.1):
    - 读 glob 命中的所有 proposal JSON
    - 优先读 _meta.entity_extracts(若存在);fallback 扫 concepts 数组里 type=entity 的项
    - 去重规则:同 (name, type, subtype) 三元组 → 同一实体;aliases 走并集 + 去重
    - 不写盘(纯计算);SKILL.md 拿结果后用 validate-proposal.py 改写单个 proposal

输出:
    stdout JSON: {
        "entities": [...deduped...],
        "merged_count": <N>,
        "original_count": <M>,
        "files_processed": <K>,
        "source": "<_meta.entity_extracts|concepts_fallback>",
        "merge_log": [...]
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
    """列出匹配 glob 的 proposal JSON 路径(同 dedupe_concepts)。"""
    if os.path.isabs(glob_pattern):
        return sorted(Path(p) for p in glob.glob(glob_pattern))
    candidates = [
        project / glob_pattern,
        Path.cwd() / glob_pattern,
    ]
    seen: set[Path] = set()
    results: list[Path] = []
    for base in candidates:
        pattern = str(base)
        for p in glob.glob(pattern):
            pp = Path(p).resolve()
            if pp not in seen:
                seen.add(pp)
                results.append(pp)
    return sorted(results)


def _read_proposal(path: Path) -> dict[str, Any] | None:
    """读取单个 proposal JSON;失败返回 None。"""
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _extract_entities(p: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    """从 proposal 抽取 entity 数组。

    Returns:
        (entities, source_label)
        - 优先 _meta.entity_extracts
        - fallback:concepts 数组里 type=entity 的项
    """
    meta = p.get("_meta", {})
    if isinstance(meta, dict):
        extracts = meta.get("entity_extracts")
        if isinstance(extracts, list):
            return [e for e in extracts if isinstance(e, dict)], "_meta.entity_extracts"

    # fallback:扫 concepts
    concepts = p.get("concepts", [])
    if isinstance(concepts, list):
        entities = [c for c in concepts if isinstance(c, dict) and c.get("type") == "entity"]
        return entities, "concepts_fallback"

    return [], "empty"


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


def _key(e: dict[str, Any]) -> tuple[str, str, str]:
    """entity 去重 key。"""
    name = str(e.get("name", "")).strip()
    tp = str(e.get("type", "")).strip()
    subtype = str(e.get("subtype", "")).strip()
    return (name, tp, subtype)


def dedupe_entities(proposals: list[dict[str, Any]]) -> dict[str, Any]:
    """合并去重 entity 数组。"""
    bucket: dict[tuple[str, str, str], dict[str, Any]] = {}
    original_count = 0
    merge_log: list[dict[str, Any]] = []
    sources: set[str] = set()

    for p in proposals:
        entities, source_label = _extract_entities(p)
        sources.add(source_label)
        for e in entities:
            k = _key(e)
            if not k[0]:
                continue
            original_count += 1
            aliases = e.get("aliases", [])
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
                existing = bucket[k]
                existing_aliases = existing.get("aliases", [])
                merged = _merge_aliases(existing_aliases, aliases)
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
        "entities": deduped,
        "merged_count": len(deduped),
        "original_count": original_count,
        "source": "/".join(sorted(sources)) if sources else "empty",
        "merge_log": merge_log,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口。"""
    project = Path(args.project_dir).resolve()
    if not project.exists():
        raise FileNotFoundError(f"--project-dir 不存在:{project}")

    paths = _list_proposals(project, args.proposals_glob)
    if not paths:
        return {
            "entities": [],
            "merged_count": 0,
            "original_count": 0,
            "files_processed": 0,
            "source": "empty",
            "merge_log": [],
        }

    proposals: list[dict[str, Any]] = []
    for p in paths:
        data = _read_proposal(p)
        if data is not None:
            proposals.append(data)

    result = dedupe_entities(proposals)
    result["files_processed"] = len(proposals)
    result["proposal_files"] = [str(p) for p in paths]
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dedupe_entities.py",
        description="跨 proposal 合并去重 entity(同 name+type+subtype 视为同一实体,aliases 走并集)。",
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

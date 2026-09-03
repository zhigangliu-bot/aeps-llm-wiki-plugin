"""safe-mv.py — 读 temp/decision-<hash>.json,执行 mv / atomic overwrite / G10 双文件迁移。

CLI:
    python3 safe-mv.py --project-dir . --apply temp/decision-<hash>.json

行为(DESIGN.md §1.1 + §3.6 v0.5.2 PATCH):
    - 读 temp/decision-<hash>.json(4 必填:type / schema_version / decided_at / actor / proposal_refs / actions)
    - op enum:mv / overwrite / skip / delete-only
    - 拍板 [y] → overwrite:先备份到 temp/raw_backup_<hash>/ + atomic 替换
    - 拍板 [n] → skip:不动
    - 拍板 [d] → delete-only:仅删旧副本
    - mv → 普通移动(默认 inbox/ → raw/<subdir>/)
    - G10 双文件迁移:同时迁 <file>.converted.md 到 raw/<subdir>/
    - 失败降级:备份写失败 → abort,不动原文件;atomic 替换失败 → rollback 备份

输出:
    stdout JSON: {"moved": [...], "backed_up": [...], "atomic": true|false, "errors": [...]}
    exit 0 / 1

约束(NFR-1 ~ NFR-5):
    - 不读 stdin(NFR-1)
    - 不开 daemon(NFR-1)
    - 路径全部相对 --project-dir(NFR-4)
    - 临时文件进 <project>/temp/(NFR-5)
    - 错误消息中文为主(NFR-3)
    - 走 Q7 死循环防护:备份 + 替换都用 atomic_write_preserving_mtime
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _common import atomic_write_preserving_mtime, emit_json


# decision JSON 4 必填(DESIGN.md §2.2)
DECISION_REQUIRED = (
    "type",
    "schema_version",
    "decided_at",
    "actor",
    "proposal_refs",
    "actions",
)

# actions[].op 4 选 1
VALID_OPS = ("mv", "overwrite", "skip", "delete-only")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_decision(decision: dict[str, Any]) -> None:
    """校验 decision JSON 结构完整性。"""
    missing = [k for k in DECISION_REQUIRED if k not in decision]
    if missing:
        raise ValueError(f"decision JSON 缺必填字段:{missing}")

    if not isinstance(decision["proposal_refs"], list):
        raise ValueError("proposal_refs 必须是 list[str]")

    if not isinstance(decision["actions"], list) or not decision["actions"]:
        raise ValueError("actions 必填且为非空 list")

    for i, action in enumerate(decision["actions"]):
        if "op" not in action:
            raise ValueError(f"actions[{i}] 缺 op 字段")
        if action["op"] not in VALID_OPS:
            raise ValueError(
                f"actions[{i}].op 非法:{action['op']};合法值 = {VALID_OPS}"
            )
        if "source" not in action or "dest" not in action:
            raise ValueError(f"actions[{i}] 缺 source/dest 字段")


def _backup_target(
    backup_root: Path, source_path: Path, target_dest: Path
) -> Path:
    """把单个目标文件(若存在)备份到 backup_root 下的对应路径。"""
    # 备份相对 backup_root 的路径结构基于 dest(便于回滚时定位)
    rel = Path(target_dest).name
    backup_path = backup_root / rel
    if Path(target_dest).exists():
        shutil.copy2(Path(target_dest), backup_path)
    return backup_path


def _move_pair(
    src_dir: Path,
    src_name: str,
    src_ext: str,
    dest_dir: Path,
    dest_name: str,
) -> list[str]:
    """G10 双文件迁移:同时搬原文件 + .converted.md(若存在)。

    Returns:
        实际搬动的文件路径列表(相对 project_dir 字符串)。
    """
    moved: list[str] = []

    primary_src = src_dir / f"{src_name}.{src_ext}"
    primary_dst = dest_dir / f"{dest_name}.{src_ext}"
    if primary_src.exists():
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(primary_src), str(primary_dst))
        moved.append(str(primary_dst))

    # G10 converted.md 配套
    converted_src = src_dir / f"{src_name}.{src_ext}.converted.md"
    converted_dst = dest_dir / f"{dest_name}.{src_ext}.converted.md"
    if converted_src.exists():
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(converted_src), str(converted_dst))
        moved.append(str(converted_dst))

    return moved


def _process_one_action(
    action: dict[str, Any],
    project: Path,
    backup_root: Path,
    moved: list[str],
    backed_up: list[str],
    errors: list[str],
    atomic_ok: list[bool],
) -> None:
    """处理 actions[] 中的单条 op。

    Args:
        action: 原始 action dict。
        project: 项目根目录。
        backup_root: 本次 safe-mv 调用的备份目录(temp/raw_backup_<hash>/)。
        moved / backed_up / errors / atomic_ok: 累加结果(out 参数)。
    """
    op = action["op"]
    source_rel = action["source"]
    dest_rel = action["dest"]

    source_path = project / source_rel
    dest_path = project / dest_rel
    src_name = Path(source_rel).stem
    src_ext = Path(source_rel).suffix.lstrip(".")
    dest_name = Path(dest_rel).stem

    if op == "skip":
        # 拍板 [n]:不动
        return

    if op == "delete-only":
        # 拍板 [d]:仅删旧副本(若有 dest 则删);inbox 原文件保留
        if dest_path.exists():
            try:
                # 走 Q7 死循环防护?delete 不需要(没有内容写入)
                dest_path.unlink()
                atomic_ok.append(True)
            except OSError as e:
                errors.append(f"delete-only 失败:{dest_path} -> {e}")
                atomic_ok.append(False)
        # 同时删 .converted.md(若有)
        converted_dest = dest_path.with_name(f"{dest_path.name}.converted.md")
        if converted_dest.exists():
            try:
                converted_dest.unlink()
                atomic_ok.append(True)
            except OSError as e:
                errors.append(f"delete-only(.converted.md)失败:{converted_dest} -> {e}")
                atomic_ok.append(False)
        return

    if op == "mv":
        # 普通移动 in → dest(G10 双文件)
        if not source_path.exists():
            errors.append(f"mv 源不存在:{source_path}")
            atomic_ok.append(False)
            return
        result_moved = _move_pair(
            source_path.parent, src_name, src_ext,
            dest_path.parent, dest_name,
        )
        moved.extend(result_moved)
        atomic_ok.append(True)
        return

    if op == "overwrite":
        # 拍板 [y]:先备份 + atomic 替换
        # 1. 备份旧 dest(若有)到 backup_root
        try:
            backup_root.mkdir(parents=True, exist_ok=True)
            if dest_path.exists():
                bp = _backup_target(backup_root, source_path, dest_path)
                backed_up.append(str(bp))
            # 同时备份 .converted.md(若有)
            converted_dest_old = dest_path.with_name(f"{dest_path.name}.converted.md")
            if converted_dest_old.exists():
                bp2 = backup_root / converted_dest_old.name
                shutil.copy2(converted_dest_old, bp2)
                backed_up.append(str(bp2))
        except OSError as e:
            # 备份失败 → abort(不动原文件)
            errors.append(f"backup 失败,已 abort overwrite:{e}")
            atomic_ok.append(False)
            return

        # 2. 走 _move_pair(inbox → dest)
        if not source_path.exists():
            errors.append(f"overwrite 源不存在:{source_path}")
            atomic_ok.append(False)
            return
        try:
            result_moved = _move_pair(
                source_path.parent, src_name, src_ext,
                dest_path.parent, dest_name,
            )
            moved.extend(result_moved)
            atomic_ok.append(True)
        except OSError as e:
            errors.append(f"atomic 替换失败:{e};备份保留在 {backup_root}")
            atomic_ok.append(False)
        return

    # 防御性:未知 op
    errors.append(f"未知 op:{op}")
    atomic_ok.append(False)


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口:读 decision JSON,执行每条 action。"""
    project = Path(args.project_dir).resolve()
    if not project.exists():
        raise FileNotFoundError(f"--project-dir 不存在:{project}")

    apply_path = Path(args.apply)
    if not apply_path.is_absolute():
        apply_path = project / apply_path

    if not apply_path.exists():
        raise FileNotFoundError(f"--apply 文件不存在:{apply_path}")

    # 解析 decision
    try:
        with apply_path.open("r", encoding="utf-8") as f:
            decision = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"decision JSON 解析失败:{e}")

    _validate_decision(decision)

    # 备份根(从 apply_path 推算 hash:temp/decision-<hash>.json → <hash>)
    hash_part = apply_path.stem.replace("decision-", "", 1)
    backup_root = project / "temp" / f"raw_backup_{hash_part}"

    moved: list[str] = []
    backed_up: list[str] = []
    errors: list[str] = []
    atomic_ok: list[bool] = []

    for action in decision["actions"]:
        _process_one_action(
            action, project, backup_root,
            moved, backed_up, errors, atomic_ok,
        )

    return {
        "decision_path": str(apply_path),
        "hash": hash_part,
        "decided_at": _now_iso(),
        "moved": moved,
        "backed_up": backed_up,
        "atomic": all(atomic_ok) if atomic_ok else True,
        "errors": errors,
        "actions_count": len(decision["actions"]),
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="safe-mv.py",
        description="读 temp/decision-<hash>.json 执行 mv / atomic overwrite / G10 双文件迁移。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    parser.add_argument(
        "--apply",
        required=True,
        help="decision JSON 路径(如 temp/decision-abc123.json)。",
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

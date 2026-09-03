"""check-deps.py — 跑前 import 校验。

CLI:
    python3 check-deps.py [--project-dir .]

行为:
    - 读 <project>/scripts/requirements.txt
    - importlib.import_module 试 import anydoc / paddleocr / jsonschema / yaml / pytest
    - 任一 ImportError → 输出 {"ok": false, "missing": [...]} + exit 1
    - 全 OK → 输出 {"ok": true, "missing": []} + exit 0

约束:
    - 不读 stdin
    - 不修改文件
    - 纯检查,适合 SKILL.md 阶段 0 跑前探查
"""

from __future__ import annotations

import argparse
import importlib
import re
import sys
from pathlib import Path
from typing import Any

from _common import emit_json


# requirements.txt → import_name 映射(支持 "anydoc>=0.3.0" / "paddleocr>=2.7" 等写法)
REQUIRED_PACKAGES: dict[str, str] = {
    "anydoc": "anydoc",
    "paddleocr": "paddleocr",
    "jsonschema": "jsonschema",
    "pyyaml": "yaml",
    "pytest": "pytest",
}


def _parse_requirements(req_path: Path) -> list[tuple[str, str]]:
    """解析 requirements.txt,返回 (package_name, version_spec) 列表。

    支持注释行(#)和 pip 风格的 >= / == / < 等版本约束。
    """
    if not req_path.exists():
        return []

    items: list[tuple[str, str]] = []
    for line in req_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9_.\-]+)\s*([><=!~]=?\s*[^#\s]+)?", stripped)
        if match:
            name = match.group(1).strip()
            version = (match.group(2) or "").strip()
            items.append((name, version))
    return items


def _try_import(pkg_name: str, import_name: str) -> tuple[bool, str | None]:
    """尝试 import,返回 (success, error_msg)。"""
    try:
        importlib.import_module(import_name)
        return True, None
    except ImportError as e:
        return False, str(e)
    except Exception as e:  # noqa: BLE001
        return False, f"非 ImportError 异常: {type(e).__name__}: {e}"


def check(project_dir: Path) -> dict[str, Any]:
    """核心校验逻辑。"""
    req_path = project_dir / "scripts" / "requirements.txt"
    req_items = _parse_requirements(req_path)

    if not req_items:
        return {
            "ok": False,
            "missing": [],
            "requirements_path": str(req_path),
            "warning": "requirements.txt 不存在或无可解析条目",
        }

    missing: list[str] = []
    for pkg_name, version_spec in req_items:
        if pkg_name not in REQUIRED_PACKAGES:
            continue
        import_name = REQUIRED_PACKAGES[pkg_name]
        ok, err = _try_import(pkg_name, import_name)
        if not ok:
            missing.append(f"{pkg_name}{version_spec}".strip())
            _ = err  # 暂不暴露,避免 JSON 噪音

    return {
        "ok": len(missing) == 0,
        "missing": missing,
        "requirements_path": str(req_path),
        "checked": [name for name in REQUIRED_PACKAGES.keys()],
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="check-deps.py",
        description="跑前 import 校验:读 requirements.txt,逐个 import,缺包返回 missing 列表。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    project = Path(args.project_dir).resolve()
    if not project.exists():
        emit_json({"ok": False, "error": f"--project-dir 不存在: {project}"})
        return 1

    result = check(project)
    emit_json(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
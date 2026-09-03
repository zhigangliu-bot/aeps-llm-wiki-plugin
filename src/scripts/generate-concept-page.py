"""generate-concept-page.py — 写 knowledge/concepts/<subtype>/<slug>.md(concept 类型)。

CLI:
    python3 generate-concept-page.py --project-dir . --subtype theory --slug <slug> \\
        --meta-json <json> --body-file <path>

行为(DESIGN.md §1.1 + §2.5 + §3.1):
    - 校验 subtype ∈ {theory, method, field, phenomenon, standard, term, other}(7 合法值)
    - 自动建 knowledge/concepts/<subtype>/ 目录(若不存在)
    - 注入 frontmatter:通用 5 必填 + concept-specific aliases
    - 路径:knowledge/concepts/<subtype>/<slug>.md
    - 走 Q7 死循环防护(二次写盘用 atomic_write_preserving_mtime)

输出:
    stdout JSON: {"path": "knowledge/concepts/<subtype>/<slug>.md", "wrote": true, "size": <N>}
    exit 0 / 1

约束(NFR-1 ~ NFR-7):
    - 不读 stdin(NFR-1)
    - 不开 daemon(NFR-1)
    - 路径全部相对 --project-dir(NFR-4)
    - 错误消息中文为主(NFR-3)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from _common import atomic_write_preserving_mtime, emit_json


# 7 合法 concept subtype(权威源:src/templates/concept-entities-readme.md §2)
CONCEPT_SUBTYPES = frozenset({
    "theory", "method", "field", "phenomenon", "standard", "term", "other",
})

# 通用 5 必填
COMMON_REQUIRED = ("type", "title", "description", "updated", "tags")

# concept-specific 必填
CONCEPT_REQUIRED = ("aliases",)


def _validate_meta(meta: dict[str, Any], subtype: str) -> None:
    """校验 meta-json 字段完整性 + subtype 合法。"""
    missing = [k for k in COMMON_REQUIRED if k not in meta or meta[k] is None]
    if missing:
        raise ValueError(f"meta-json 缺通用必填字段:{missing}")

    for k in ("title", "description", "updated"):
        v = meta.get(k)
        if isinstance(v, str) and not v.strip():
            raise ValueError(f"{k} 不能为空字符串")

    tags = meta.get("tags")
    if not isinstance(tags, list) or not tags:
        raise ValueError("tags 必须是非空 list[str]")

    expected_type = subtype
    if meta.get("type") != expected_type:
        raise ValueError(
            f"type 字段值({meta.get('type')})与 --subtype({subtype})不一致"
        )

    concept_missing = [k for k in CONCEPT_REQUIRED if k not in meta]
    if concept_missing:
        raise ValueError(f"concept 类型必填字段缺失:{concept_missing}")

    aliases = meta.get("aliases")
    if aliases is None or not isinstance(aliases, list):
        raise ValueError("aliases 必须是 list(空数组合法)")


def _build_frontmatter(meta: dict[str, Any], subtype: str) -> str:
    """构造 YAML frontmatter。"""
    lines: list[str] = ["---"]

    def _scalar(v: Any) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        if v is None:
            return "null"
        if isinstance(v, (int, float)):
            return str(v)
        s = str(v)
        if "'" in s:
            s = s.replace("'", "''")
        return f"'{s}'"

    lines.append(f"type: {_scalar(meta['type'])}")
    lines.append(f"title: {_scalar(meta['title'])}")
    lines.append(f"description: {_scalar(meta['description'])}")
    lines.append(f"updated: {_scalar(meta['updated'])}")

    lines.append("tags:")
    for tag in meta["tags"]:
        lines.append(f"  - {_scalar(tag)}")

    lines.append("aliases:")
    for alias in meta["aliases"]:
        lines.append(f"  - {_scalar(alias)}")

    if "subtype" in meta:
        lines.append(f"subtype: {_scalar(meta['subtype'])}")
    else:
        lines.append(f"subtype: {_scalar(subtype)}")

    if "status" in meta and meta["status"] is not None:
        lines.append(f"status: {_scalar(meta['status'])}")

    lines.append("---")
    return "\n".join(lines) + "\n"


def _read_body_file(body_file: Path) -> str:
    """读取 LLM 已写好的正文。"""
    if not body_file.exists():
        raise FileNotFoundError(f"--body-file 不存在:{body_file}")
    try:
        return body_file.read_text(encoding="utf-8")
    except OSError as e:
        raise OSError(f"读取 body-file 失败:{e}")


def _target_path(project: Path, subtype: str, slug: str) -> Path:
    """计算目标文件路径:knowledge/concepts/<subtype>/<slug>.md。"""
    concept_dir = project / "knowledge" / "concepts" / subtype
    concept_dir.mkdir(parents=True, exist_ok=True)
    return concept_dir / f"{slug}.md"


def _write_atomic(target: Path, content: str) -> None:
    """首次写盘(直接 write_text,无 mtime 保留)。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _emit_progress(actor: str, dest_rel: str) -> None:
    """首次生成时向 log.md 追加 **Creation** 记录。"""
    import subprocess

    cmd = [
        "python",
        str(Path(__file__).resolve().parent / "append-log.py"),
        "--project-dir", str(Path(__file__).resolve().parent.parent.parent),
        "--action", "Creation",
        "--summary", f"[{Path(dest_rel).name}]({dest_rel})",
        "--actor", actor,
    ]
    try:
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except OSError:
        pass


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口:写 knowledge/concepts/<subtype>/<slug>.md。"""
    project = Path(args.project_dir).resolve()
    if not project.exists():
        raise FileNotFoundError(f"--project-dir 不存在:{project}")

    subtype = args.subtype
    if subtype not in CONCEPT_SUBTYPES:
        raise ValueError(
            f"--subtype 非法:{subtype};合法 7 值 = {sorted(CONCEPT_SUBTYPES)}"
        )

    try:
        meta = json.loads(args.meta_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"--meta-json 解析失败:{e}")
    if not isinstance(meta, dict):
        raise ValueError("--meta-json 必须是 JSON object")

    _validate_meta(meta, subtype)

    body_file = Path(args.body_file)
    if not body_file.is_absolute():
        body_file = project / body_file
    body_text = _read_body_file(body_file)

    fm = _build_frontmatter(meta, subtype)
    body = (body_text or "").rstrip() + "\n"
    full_md = fm + "\n" + body

    slug = args.slug
    target = _target_path(project, subtype, slug)
    if target.exists():
        atomic_write_preserving_mtime(target, full_md)
    else:
        _write_atomic(target, full_md)
        _emit_progress(
            actor=str(meta.get("_actor", "agent: producer/aeps-llm-wiki-plugin/0.5.5")),
            dest_rel=str(target.relative_to(project)).replace("\\", "/"),
        )

    return {
        "path": str(target.relative_to(project)).replace("\\", "/"),
        "wrote": True,
        "size": target.stat().st_size,
        "subtype": subtype,
        "slug": slug,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="generate-concept-page.py",
        description="写 knowledge/concepts/<subtype>/<slug>.md(7 合法 subtype + aliases 必填)。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    parser.add_argument(
        "--subtype",
        required=True,
        choices=sorted(CONCEPT_SUBTYPES),
        help="concept subtype(7 合法值之一)。",
    )
    parser.add_argument(
        "--slug",
        required=True,
        help="概念 slug(全小写连字符)。",
    )
    parser.add_argument(
        "--meta-json",
        required=True,
        help="LLM 抽出的 frontmatter 字段 JSON 字符串。",
    )
    parser.add_argument(
        "--body-file",
        required=True,
        help="LLM 已写好的正文 md 文件路径(不含 frontmatter)。",
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

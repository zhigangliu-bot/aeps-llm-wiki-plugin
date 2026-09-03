"""generate-source-page.py — 写 knowledge/sources/<basename>.md(source 类型)。

CLI:
    python3 generate-source-page.py --project-dir . --basename <basename> \\
        --meta-json <json> --body-file <path>

行为(DESIGN.md §1.1 + §2.5 + §3.1 G10 + Q9):
    - 读 <plugin>/src/templates/source-page.md 作为骨架参考
    - 注入 frontmatter(通用 5 必填 + G10 5 增量 + type-specific 必填)
    - 写 3 H2 骨架(## 重点摘录 / ## 我的思考 / ## 总结:最有收获的一句话)
    - --body-file 接收 LLM 已写好的正文(md 文本,不含 frontmatter);直接注入
    - 路径:knowledge/sources/<basename>.md
    - Q7 死循环防护:atomic_write_preserving_mtime 4 步流程

输出:
    stdout JSON: {"path": "knowledge/sources/<basename>.md", "wrote": true, "size": <N>}
    exit 0 / 1

约束(NFR-1 ~ NFR-7):
    - 不读 stdin(NFR-1)
    - 不开 daemon(NFR-1)
    - 路径全部相对 --project-dir(NFR-4)
    - 错误消息中文为主(NFR-3)
    - 通用必填字段:type / title / description / updated / tags;G10 增量:format /
      converter / native_text / converted_path / links;Q9:source_file ↔ sources[0].resource
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _common import atomic_write_preserving_mtime, emit_json


# 通用 5 必填(DESIGN.md §2.5)
COMMON_REQUIRED = ("type", "title", "description", "updated", "tags")

# G10 增量(必填)
G10_REQUIRED = ("format", "converter", "native_text", "converted_path", "links")

# type-specific(source)
SOURCE_REQUIRED = ("source_file", "sources")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_meta(meta: dict[str, Any]) -> None:
    """校验 meta-json 字段完整性。

    Raises:
        ValueError: 缺字段或格式错。
    """
    missing = [k for k in COMMON_REQUIRED if k not in meta or meta[k] is None]
    if missing:
        raise ValueError(f"meta-json 缺通用必填字段:{missing}")

    # type 必须是 source
    if meta.get("type") != "source":
        raise ValueError(
            f"type 必须是 source,实际={meta.get('type')}(generate-source-page 仅处理 source 页)"
        )

    # 字符串非空校验
    for k in ("title", "description", "updated"):
        v = meta.get(k)
        if isinstance(v, str) and not v.strip():
            raise ValueError(f"{k} 不能为空字符串")

    # tags 必须是 list[str](非空)
    tags = meta.get("tags")
    if not isinstance(tags, list) or not tags:
        raise ValueError("tags 必须是非空 list[str]")

    # G10 增量必填
    g10_missing = [k for k in G10_REQUIRED if k not in meta]
    if g10_missing:
        raise ValueError(f"G10 必填字段缺失:{g10_missing}")

    # native_text / converter 强绑定
    nt = meta.get("native_text")
    cv = meta.get("converter")
    cp = meta.get("converted_path")
    if nt is True:
        if cv is not None:
            raise ValueError(
                f"G10 三元组矛盾:native_text=true 时 converter 必须 null,实际={cv}"
            )
        if cp is not None:
            raise ValueError(
                f"G10 三元组矛盾:native_text=true 时 converted_path 必须 null,实际={cp}"
            )
    elif nt is False:
        if cv not in ("anydoc", "claude-native", "paddleocr"):
            raise ValueError(
                f"G10 三元组矛盾:native_text=false 时 converter 必须 ∈ "
                f"{{anydoc, claude-native, paddleocr}},实际={cv}"
            )
        if not isinstance(cp, str) or not cp:
            raise ValueError(
                f"G10 三元组矛盾:native_text=false 时 converted_path 必须非空 string,实际={cp}"
            )

    # type-specific 必填
    src_missing = [k for k in SOURCE_REQUIRED if k not in meta]
    if src_missing:
        raise ValueError(f"source 类型必填字段缺失:{src_missing}")

    # Q9 双字段同源
    sf = meta.get("source_file")
    sources = meta.get("sources")
    if isinstance(sources, list) and sources:
        first = sources[0]
        if not isinstance(first, dict):
            raise ValueError("sources[0] 必须是 dict")
        if first.get("resource") != sf:
            raise ValueError(
                f"Q9 双字段不同源:source_file={sf} vs sources[0].resource={first.get('resource')}"
            )


def _build_frontmatter(meta: dict[str, Any]) -> str:
    """根据 meta 构造 YAML frontmatter 字符串。"""
    # 按稳定顺序输出
    lines: list[str] = ["---"]

    def _scalar(v: Any) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        if v is None:
            return "null"
        if isinstance(v, (int, float)):
            return str(v)
        # 字符串:用单引号包裹(避免特殊字符问题)
        s = str(v)
        # YAML 单引号:内部单引号转义为 '';整体单引号包裹
        if "'" in s:
            s = s.replace("'", "''")
        return f"'{s}'"

    # 通用必填
    lines.append(f"type: {_scalar(meta['type'])}")
    lines.append(f"title: {_scalar(meta['title'])}")
    lines.append(f"description: {_scalar(meta['description'])}")
    lines.append(f"updated: {_scalar(meta['updated'])}")

    # tags(列表)
    lines.append("tags:")
    for tag in meta["tags"]:
        lines.append(f"  - {_scalar(tag)}")

    # source_file(Q9)
    lines.append(f"source_file: {_scalar(meta['source_file'])}")

    # sources(OKF 数组)
    lines.append("sources:")
    for src in meta["sources"]:
        lines.append(f"  - id: {_scalar(src.get('id', ''))}")
        lines.append(f"    resource: {_scalar(src['resource'])}")
        if "title" in src:
            lines.append(f"    title: {_scalar(src['title'])}")
        if "author" in src:
            lines.append(f"    author: {_scalar(src['author'])}")
        if "last_modified" in src:
            lines.append(f"    last_modified: {_scalar(src['last_modified'])}")

    # G10 增量
    lines.append(f"format: {_scalar(meta['format'])}")
    lines.append(f"converter: {_scalar(meta['converter'])}")
    lines.append(f"native_text: {_scalar(meta['native_text'])}")
    lines.append(f"converted_path: {_scalar(meta['converted_path'])}")

    # links(列表)
    lines.append("links:")
    for link in meta["links"]:
        lines.append(f"  - {_scalar(link)}")

    # summary(可选,若提供则写出)
    if "summary" in meta and meta["summary"] is not None:
        lines.append(f"summary: {_scalar(meta['summary'])}")

    # status(可选)
    if "status" in meta and meta["status"] is not None:
        lines.append(f"status: {_scalar(meta['status'])}")

    lines.append("---")
    return "\n".join(lines) + "\n"


def _build_skeleton(body_text: str, basename: str, native_text: bool) -> str:
    """构造正文:3 H2 骨架 + LLM 已写正文。

    若 LLM 已写正文已含 3 H2,直接返回;否则追加占位骨架。
    """
    text = (body_text or "").rstrip()
    has_zhaiyao = "## 重点摘录" in text
    has_think = "## 我的思考" in text
    has_summary = "## 总结" in text

    if has_zhaiyao and has_think and has_summary:
        return text + "\n"

    # 缺哪个 H2 就补哪个
    suffix_parts: list[str] = []
    if not has_zhaiyao:
        suffix_parts.append("## 重点摘录\n\n<请补充>\n")
    if not has_think:
        suffix_parts.append("\n## 我的思考\n\n<请补充>\n")
    if not has_summary:
        suffix_parts.append("\n## 总结:最有收获的一句话\n\n<请补充>\n")

    return text + "\n" + "".join(suffix_parts)


def _read_body_file(body_file: Path) -> str:
    """读取 LLM 已写好的正文。"""
    if not body_file.exists():
        raise FileNotFoundError(f"--body-file 不存在:{body_file}")
    try:
        return body_file.read_text(encoding="utf-8")
    except OSError as e:
        raise OSError(f"读取 body-file 失败:{e}")


def _target_path(project: Path, basename: str) -> Path:
    """计算目标文件路径:knowledge/sources/<basename>.md。"""
    sources_dir = project / "knowledge" / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    return sources_dir / f"{basename}.md"


def _write_atomic(target: Path, content: str) -> None:
    """首次写盘(目标文件不存在):直接 write_text,不调用 atomic_write_preserving_mtime。

    原因:atomic_write_preserving_mtime 强制要求文件已存在(target 首次生成时 mtime 没有保留价值)。
    后续 lint/links-mirror 等机械修复场景再走 atomic_write_preserving_mtime。
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _emit_progress(actor: str, dest_rel: str) -> None:
    """首次生成时向 log.md 追加 **Creation** 记录(便于溯源)。"""
    # 通过 subprocess 调 append-log.py 避免循环 import
    import subprocess

    cmd = [
        "python",
        str(Path(__file__).resolve().parent / "append-log.py"),
        "--project-dir", str(Path(__file__).resolve().parent.parent.parent),
        "--action", "Creation",
        "--summary", f"[{Path(dest_rel).name}]({dest_rel})",
        "--actor", actor,
    ]
    # 失败容忍:append-log 失败不影响主流程写盘结果
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
    """主流程入口:写 knowledge/sources/<basename>.md。"""
    project = Path(args.project_dir).resolve()
    if not project.exists():
        raise FileNotFoundError(f"--project-dir 不存在:{project}")

    # 解析 meta-json
    try:
        meta = json.loads(args.meta_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"--meta-json 解析失败:{e}")

    if not isinstance(meta, dict):
        raise ValueError("--meta-json 必须是 JSON object")

    _validate_meta(meta)

    # 读 body-file
    body_file = Path(args.body_file)
    if not body_file.is_absolute():
        body_file = project / body_file
    body_text = _read_body_file(body_file)

    # 拼装 frontmatter + 正文
    fm = _build_frontmatter(meta)
    basename = args.basename
    body = _build_skeleton(body_text, basename, meta["native_text"])

    # 拼成完整 md
    full_md = fm + "\n" + body

    # 写盘
    target = _target_path(project, basename)
    if target.exists():
        # 二次生成(更新场景):走 Q7 atomic_write_preserving_mtime 保留 mtime
        # 但 frontmatter updated 字段由调用方控制(Q7 死循环防护:不重置)
        atomic_write_preserving_mtime(target, full_md)
    else:
        _write_atomic(target, full_md)
        # 首次生成 → log.md 追加 Creation 记录
        _emit_progress(
            actor=str(meta.get("_actor", "agent: producer/aeps-llm-wiki-plugin/0.5.5")),
            dest_rel=str(target.relative_to(project)).replace("\\", "/"),
        )

    return {
        "path": str(target.relative_to(project)).replace("\\", "/"),
        "wrote": True,
        "size": target.stat().st_size,
        "basename": basename,
        "frontmatter_lines": fm.count("\n"),
        "body_lines": body.count("\n"),
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="generate-source-page.py",
        description="写 knowledge/sources/<basename>.md(G10 5 字段 + Q9 双字段同源 + 3 H2 骨架)。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    parser.add_argument(
        "--basename",
        required=True,
        help="源文件 basename(与 raw/<subdir>/<basename>.<ext> 共享)。",
    )
    parser.add_argument(
        "--meta-json",
        required=True,
        help="LLM 抽出的 frontmatter 字段 JSON 字符串(含 type/title/.../G10 5 字段/Q9 双字段)。",
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

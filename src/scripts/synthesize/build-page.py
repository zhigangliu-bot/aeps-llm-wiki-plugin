"""build-page.py — 写 / 更新 synthesis 页 knowledge/syntheses/<slug>.md。

CLI:
    python3 build-page.py --project-dir . \\
        --slug "okf-生态全景" \\
        --meta-json '<json>' \\
        --body-file <path> \\
        [--update]

行为(DESIGN.md §1.1 synthesize 组 + synthesize SKILL.md §阶段 3 + §阶段 4.2):
    - frontmatter 必填(从 meta-json 读):
        * type: synthesis
        * title / topic(synthesis-specific)
        * sources_count(DESIGN.md §2.5 type-specific)
        * last_updated(本次写盘时间)
        * updated(CREATE 时 = last_updated;UPDATE 时不动 — Q7 死循环防护)
        * tags(6 轴,至少含 maturity + docform)
        * generated.by / generated.at(LLM 填或脚本自动补)
        * links(OKF v0.2 §9 镜像;LLM 传或空)
        * summary(2-3 句话主题脉络)
    - CREATE 流程:<project>/knowledge/syntheses/<slug>.md 不存在
        * updated = last_updated = now
        * 写盘走 atomic_write_preserving_mtime(由于文件不存在 → 走首次 write_text 分支)
        * log.md append `**Creation**: synthesize "<topic>" → [slug.md](syntheses/<slug>.md) by <actor>`
    - UPDATE 流程:--update + 文件存在
        * 改 last_updated = now
        * 改 sources_count(从 meta-json 读)
        * **不动** updated(Q7)
        * **不动** frontmatter 其他字段(title / topic / generated / tags 保留)
        * log.md append `**Update**: synthesized update on [<slug.md>](syntheses/<slug>.md) — sources_count now N`
    - 二次写盘走 atomic_write_preserving_mtime(Q7 atime + mtime 双还原)
    - sources_count < 3:
        * UPDATE 模式不阻断(允许更新)
        * CREATE 模式写 WARN 到 stderr,不阻断(LLM 已在 SKILL.md §"sources_count < 3 警告"向用户确认)

输出:
    stdout JSON:{
        "path": "knowledge/syntheses/<slug>.md",
        "created_or_updated": bool,
        "log_md_appended": bool,
        "sources_count": int,
        "ok": true
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
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 子目录脚本:把 scripts/ 加入 sys.path 以复用 _common
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _common import atomic_write_preserving_mtime, emit_json  # noqa: E402


PLUGIN_VERSION = "0.5.5"
PLUGIN_NAME = "aeps-llm-wiki-plugin"
DEFAULT_ACTOR = f"agent: producer/{PLUGIN_NAME}/{PLUGIN_VERSION}"

# synthesis 页 frontmatter 必填字段(DESIGN.md §2.5 SYNTHESIS_REQUIRED)
SYNTHESIS_REQUIRED_FIELDS = ("topic", "sources_count", "last_updated")

# 通用必填(对齐其他 generate-*-page.py)
COMMON_REQUIRED_FIELDS = ("type", "title", "tags")

# type 必须是 synthesis
EXPECTED_TYPE = "synthesis"

# sources_count < 3 警告阈值(与 lint.py check_syntheses 对齐)
SOURCES_COUNT_WARN_THRESHOLD = 3

# 极简 frontmatter 块定位正则
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)


def _now_iso() -> str:
    """返回当前 UTC ISO 8601 时间戳(YYYY-MM-DDTHH:MM:SSZ)。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_meta(meta: dict[str, Any]) -> None:
    """校验 meta-json 必填字段完整性。

    Raises:
        ValueError: 缺字段 / 格式错。
    """
    missing = [k for k in COMMON_REQUIRED_FIELDS if k not in meta or meta[k] is None]
    if missing:
        raise ValueError(f"meta-json 缺通用必填字段:{missing}")

    if meta.get("type") != EXPECTED_TYPE:
        raise ValueError(
            f"type 必须是 {EXPECTED_TYPE},实际={meta.get('type')}"
        )

    title = meta.get("title")
    if isinstance(title, str) and not title.strip():
        raise ValueError("title 不能为空字符串")

    tags = meta.get("tags")
    if not isinstance(tags, list) or not tags:
        raise ValueError("tags 必须是非空 list[str]")

    # synthesis 必填 3 字段
    syn_missing = [k for k in SYNTHESIS_REQUIRED_FIELDS if k not in meta]
    if syn_missing:
        raise ValueError(f"synthesis 必填字段缺失:{syn_missing}")

    # sources_count 类型校验
    sc = meta.get("sources_count")
    if not isinstance(sc, int) or isinstance(sc, bool) or sc < 0:
        raise ValueError(
            f"sources_count 必须是非负 int,实际={sc!r}(type={type(sc).__name__})"
        )

    topic = meta.get("topic")
    if not isinstance(topic, str) or not topic.strip():
        raise ValueError("topic 必须是非空字符串(原始 topic)")

    # summary 可选但若传则必须 str
    if "summary" in meta and meta["summary"] is not None:
        if not isinstance(meta["summary"], str):
            raise ValueError("summary 必须是 string 或 None")

    # links 可选但若传则必须 list
    if "links" in meta and meta["links"] is not None:
        if not isinstance(meta["links"], list):
            raise ValueError("links 必须是 list 或 None")

    # generated 可选;若传则期望 dict 含 by/at
    if "generated" in meta and meta["generated"] is not None:
        gen = meta["generated"]
        if not isinstance(gen, dict):
            raise ValueError("generated 必须是 dict{by, at} 或 None")
        if "by" not in gen or "at" not in gen:
            raise ValueError("generated 必须含 'by' 和 'at' 字段")


def _scalar(v: Any) -> str:
    """YAML 单值序列化(与 generate-*-page.py 系列对齐)。"""
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


def _build_frontmatter(
    meta: dict[str, Any],
    *,
    now_iso: str,
    is_update: bool,
    existing_updated: str | None = None,
) -> str:
    """构造 YAML frontmatter。

    CREATE 流程:updated = last_updated = now
    UPDATE 流程:last_updated = now;updated = existing_updated(Q7 不动)
    """
    lines: list[str] = ["---"]

    # 通用必填(稳定顺序)
    lines.append(f"type: {_scalar(meta['type'])}")
    lines.append(f"title: {_scalar(meta['title'])}")
    lines.append(f"topic: {_scalar(meta['topic'])}")
    lines.append(f"sources_count: {int(meta['sources_count'])}")
    lines.append(f"last_updated: {_scalar(meta['last_updated'])}")

    # updated:CREATE = last_updated;UPDATE = existing_updated(从原文件读)
    if is_update and existing_updated:
        lines.append(f"updated: {_scalar(existing_updated)}")
    else:
        # CREATE:updated = last_updated = now(覆盖 meta 传入值,确保一致)
        lines.append(f"updated: {_scalar(now_iso)}")

    # tags
    lines.append("tags:")
    for tag in meta["tags"]:
        lines.append(f"  - {_scalar(tag)}")

    # generated{by, at}:CREATE 用当前时间;UPDATE 保留 LLM 传入
    generated = meta.get("generated")
    if generated and isinstance(generated, dict):
        lines.append("generated:")
        lines.append(f"  by: {_scalar(generated.get('by', DEFAULT_ACTOR))}")
        lines.append(f"  at: {_scalar(generated.get('at', now_iso))}")
    else:
        # 自动生成(默认 actor + 当前时间)
        lines.append("generated:")
        lines.append(f"  by: {_scalar(DEFAULT_ACTOR)}")
        lines.append(f"  at: {_scalar(now_iso)}")

    # links(OKF §9 镜像;空数组合法)
    links = meta.get("links", [])
    if not isinstance(links, list):
        links = []
    lines.append("links:")
    if links:
        for link in links:
            lines.append(f"  - {_scalar(link)}")
    else:
        lines.append("  []")

    # summary(块,| 形式,LLM 自由发挥 2-3 句话)
    summary_val = meta.get("summary")
    if summary_val:
        lines.append("summary: |")
        for ln in str(summary_val).splitlines():
            lines.append(f"  {ln}")
    else:
        lines.append("summary: |")
        lines.append("  <本次综合的主题脉络 2-3 句话>")

    lines.append("---")
    return "\n".join(lines) + "\n"


def _parse_existing_updated(text: str) -> str | None:
    """从已有 synthesis 页读 `updated` 字段(UPDATE 时保留)。"""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    block = m.group(1)
    for line in block.splitlines():
        if line.startswith("updated:"):
            value = line.partition(":")[2].strip()
            if len(value) >= 2 and (
                (value.startswith("'") and value.endswith("'"))
                or (value.startswith('"') and value.endswith('"'))
            ):
                value = value[1:-1]
            return value
    return None


def _read_body_file(body_file: Path) -> str:
    """读 body 文件(LLM 已写正文)。"""
    if not body_file.exists():
        raise FileNotFoundError(f"--body-file 不存在:{body_file}")
    try:
        return body_file.read_text(encoding="utf-8")
    except OSError as e:
        raise OSError(f"读取 body-file 失败:{e}")


def _target_path(project: Path, slug: str) -> Path:
    """目标文件路径:knowledge/syntheses/<slug>.md。"""
    syntheses_dir = project / "knowledge" / "syntheses"
    syntheses_dir.mkdir(parents=True, exist_ok=True)
    return syntheses_dir / f"{slug}.md"


def _append_log(
    project: Path,
    action: str,
    summary: str,
    actor: str,
) -> bool:
    """调 append-log.py 写 Creation/Update 条目;失败容忍(不影响主流程)。"""
    append_log = _SCRIPTS_DIR / "append-log.py"
    cmd = [
        sys.executable,
        str(append_log),
        "--project-dir", str(project),
        "--action", action,
        "--summary", summary,
        "--actor", actor,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except OSError as e:
        print(f"⚠️ append-log.py 调用失败(OSError):{e}", file=sys.stderr)
        return False

    if proc.returncode != 0:
        print(
            f"⚠️ append-log.py 退出码 {proc.returncode}:stderr={proc.stderr[:200]}",
            file=sys.stderr,
        )
        return False
    return True


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口:写 / 更新 synthesis 页。"""
    project = Path(args.project_dir).resolve()
    if not project.exists():
        raise FileNotFoundError(f"--project-dir 不存在:{project}")

    # 解析 meta-json
    try:
        meta_raw = json.loads(args.meta_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"--meta-json 解析失败:{e}")
    if not isinstance(meta_raw, dict):
        raise ValueError("--meta-json 必须是 JSON object")

    # 补 last_updated(若未传 → 用当前时间)
    meta = dict(meta_raw)
    if not meta.get("last_updated"):
        meta["last_updated"] = _now_iso()

    _validate_meta(meta)

    # 读 body-file
    body_file = Path(args.body_file)
    if not body_file.is_absolute():
        body_file = project / body_file
    body_text = _read_body_file(body_file)

    slug = args.slug.strip()
    if not slug:
        raise ValueError("--slug 必填且非空")

    target = _target_path(project, slug)
    is_update = bool(args.update)
    now_iso = _now_iso()

    sources_count = int(meta["sources_count"])
    topic = str(meta["topic"])

    # sources_count < 3 警告(不阻断)
    if sources_count < SOURCES_COUNT_WARN_THRESHOLD:
        print(
            f"⚠️ sources_count={sources_count} < {SOURCES_COUNT_WARN_THRESHOLD};"
            f" lint 会 WARN(不阻断)。SKILL.md 已与用户确认。",
            file=sys.stderr,
        )

    # UPDATE 流程
    existing_updated: str | None = None
    log_md_appended = False

    if is_update and target.exists():
        # 读原 updated 字段(UPDATE 强制不动)
        try:
            old_text = target.read_text(encoding="utf-8")
        except OSError as e:
            raise OSError(f"UPDATE 读已有文件失败:{e}")
        existing_updated = _parse_existing_updated(old_text)

        fm = _build_frontmatter(
            meta,
            now_iso=now_iso,
            is_update=True,
            existing_updated=existing_updated,
        )
        full_md = fm + "\n" + body_text.rstrip() + "\n"
        # 走 Q7 atomic_write_preserving_mtime(atime + mtime 双还原)
        atomic_write_preserving_mtime(target, full_md)

        # 追加 **Update** 条目
        summary_text = (
            f"synthesized update on [{slug}.md](syntheses/{slug}.md) "
            f"— sources_count now {sources_count}"
        )
        log_md_appended = _append_log(project, "Update", summary_text, DEFAULT_ACTOR)

        rel_path = str(target.relative_to(project)).replace("\\", "/")
        return {
            "path": rel_path,
            "created_or_updated": True,
            "log_md_appended": log_md_appended,
            "sources_count": sources_count,
            "is_update": True,
            "preserved_updated": existing_updated,
            "size": target.stat().st_size,
            "ok": True,
        }

    if is_update and not target.exists():
        # --update 但文件不存在 → 报错(防误用)
        raise FileNotFoundError(
            f"--update 但 synthesis 页不存在:{target};"
            f" 请去掉 --update 走 CREATE 流程"
        )

    # CREATE 流程(默认走这里)
    fm = _build_frontmatter(
        meta,
        now_iso=now_iso,
        is_update=False,
    )
    full_md = fm + "\n" + body_text.rstrip() + "\n"

    # 首次写盘:直接 write_text(target 不存在 → atomic_write_preserving_mtime 会抛错)
    target.write_text(full_md, encoding="utf-8")

    # 追加 **Creation** 条目
    summary_text = (
        f'synthesize "{topic}" → [{slug}.md](syntheses/{slug}.md)'
    )
    log_md_appended = _append_log(project, "Creation", summary_text, DEFAULT_ACTOR)

    rel_path = str(target.relative_to(project)).replace("\\", "/")
    return {
        "path": rel_path,
        "created_or_updated": True,
        "log_md_appended": log_md_appended,
        "sources_count": sources_count,
        "is_update": False,
        "size": target.stat().st_size,
        "ok": True,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="build-page.py",
        description=(
            "写 / 更新 knowledge/syntheses/<slug>.md(synthesis 页 frontmatter + "
            "CREATE/UPDATE 双流程 + Q7 atomic + log.md append)。"
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
        help="synthesis 页 slug(已派生,全小写连字符 + 中文保留)。",
    )
    parser.add_argument(
        "--meta-json",
        required=True,
        help=(
            "LLM 抽出的 frontmatter JSON,必填 type=synthesis / title / topic / "
            "sources_count / tags;可选 last_updated / summary / links / generated。"
        ),
    )
    parser.add_argument(
        "--body-file",
        required=True,
        help="LLM 已写好的正文 md 文件(不含 frontmatter)。",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="UPDATE 流程标志(文件必须存在;只动 last_updated + sources_count;不动 updated)。",
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
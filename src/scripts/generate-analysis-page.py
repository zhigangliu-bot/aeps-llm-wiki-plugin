"""generate-analysis-page.py — 写 knowledge/analyses/<timestamp>-<slug>.md(analysis 类型,G11)。

CLI:
    python3 generate-analysis-page.py --project-dir . \\
        --timestamp "2026-09-01T14-30-00Z" --slug "autosar-overview" \\
        --meta-json <json> --body-file <path>

行为(DESIGN.md §1.1 + §2.5 + query SKILL.md §阶段 4.1 + templates/analysis-page.md):
    - 路径:knowledge/analyses/<ISO 8601 timestamp>-<slug>.md
      (时间戳冒号 → 连字符,Windows 文件名安全)
    - 注入 frontmatter(G11 4 必填 + 通用 5 必填):
        * type: analysis
        * title / answer_to(原问句,1 句话)
        * sources_used:[] (必填,C15.2 FAIL 若缺)
        * generated_by: agent: producer/aeps-llm-wiki-plugin/0.5.5
        * summary: | 块,首行 `**问题**: <原问句>`
        * updated / tags(6 轴,含 docform/analysis + maturity/draft)
        * links(G10 §3.6.2 镜像,SKILL.md 后续接 okf-lint 同步)
    - 写 3 H2 G11 骨架(从 analysis-page.md 模板解析):
        * ## 方案推演 / 架构分析
        * ## 关联溯源(末尾必须有 > 引用: 行)
        * ## 总结:最有收获的一句话
    - 写盘走 Q7 死循环防护:atomic_write_preserving_mtime(二次写)
    - 校验 `> 引用:` 行与 sources_used 走 Set 比对(Q7 / C15.4)

输出:
    stdout JSON:{"path": "knowledge/analyses/<ts>-<slug>.md",
                 "wrote": true, "size": <N>, "ok": true}
    exit 0 / 1

约束(NFR-1 ~ NFR-7):
    - 不读 stdin(NFR-1)
    - 不写 inbox / raw(NFR-4,只写 knowledge/analyses/)
    - 不开 daemon(NFR-1)
    - 错误消息中文为主(NFR-3)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _common import atomic_write_preserving_mtime, emit_json


PLUGIN_VERSION = "0.5.5"
PLUGIN_NAME = "aeps-llm-wiki-plugin"
GENERATED_BY = f"agent: producer/{PLUGIN_NAME}/{PLUGIN_VERSION}"

# 通用必填(DESIGN.md §2.5)
COMMON_REQUIRED = ("type", "title", "description", "updated", "tags")

# G11 analysis 4 必填(DESIGN.md §2.5 + templates/analysis-page.md)
ANALYSIS_REQUIRED = ("sources_used", "answer_to", "generated_by")

# G11 3 H2 骨架
H2_DEDUCTION = "## 方案推演 / 架构分析"
H2_REFERENCE = "## 关联溯源"
H2_SUMMARY = "## 总结:最有收获的一句话"

# > 引用: 行正则
REFERENCE_LINE_RE = re.compile(r"^>\s*引用[::]\s*(.+?)$", re.MULTILINE)


def _sanitize_timestamp(ts: str) -> str:
    """把 timestamp 字符串中可能非 Windows-文件名安全的字符替换。

    形如 2026-09-01T14:30:00Z → 2026-09-01T14-30-00Z(冒号 → 连字符)
    同时去除路径分隔字符。
    """
    if not ts:
        return ts
    safe = ts.replace(":", "-").replace("/", "-").replace("\\", "-")
    return safe


def _validate_meta(meta: dict[str, Any]) -> None:
    """校验 meta-json 字段完整性(G11 analysis 页)。"""
    missing_common = [k for k in COMMON_REQUIRED if k not in meta or meta[k] is None]
    if missing_common:
        raise ValueError(f"meta-json 缺通用必填字段:{missing_common}")

    if meta.get("type") != "analysis":
        raise ValueError(
            f"type 必须是 analysis,实际={meta.get('type')}(generate-analysis-page 仅处理 analysis)"
        )

    # 字符串非空
    for k in ("title", "description", "updated"):
        v = meta.get(k)
        if isinstance(v, str) and not v.strip():
            raise ValueError(f"{k} 不能为空字符串")

    tags = meta.get("tags")
    if not isinstance(tags, list) or not tags:
        raise ValueError("tags 必须是非空 list[str]")

    # G11 4 必填
    g11_missing = [k for k in ANALYSIS_REQUIRED if k not in meta]
    if g11_missing:
        raise ValueError(f"G11 analysis 必填字段缺失:{g11_missing}")

    sources_used = meta.get("sources_used")
    if not isinstance(sources_used, list) or not sources_used:
        raise ValueError("C15.2 FAIL:sources_used 必须是非空 list[str]")

    answer_to = meta.get("answer_to", "")
    if not isinstance(answer_to, str) or not answer_to.strip():
        raise ValueError("answer_to 必须是非空字符串(原 query 问句)")

    # generated_by 格式弱校验
    gen = meta.get("generated_by", "")
    if not isinstance(gen, str) or "agent:" not in gen:
        # 若 meta 里没传,后面生成时用 GENERATED_BY;这里只在显式传错时报错
        raise ValueError(
            f"generated_by 应为 agent: ... 格式,实际={gen!r}(若不传则由脚本自动填)"
        )


def _inject_generated_by_if_missing(meta: dict[str, Any]) -> dict[str, Any]:
    """若 meta 未传 generated_by,默认用 plugin 统一格式。"""
    if not meta.get("generated_by"):
        meta = dict(meta)
        meta["generated_by"] = GENERATED_BY
    return meta


def _build_frontmatter(meta: dict[str, Any]) -> str:
    """构造 YAML frontmatter 字符串。"""

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

    lines: list[str] = ["---"]
    # 通用必填(稳定顺序)
    lines.append(f"type: {_scalar(meta['type'])}")
    lines.append(f"title: {_scalar(meta['title'])}")
    lines.append(f"description: {_scalar(meta['description'])}")
    lines.append(f"updated: {_scalar(meta['updated'])}")

    lines.append("tags:")
    for tag in meta["tags"]:
        lines.append(f"  - {_scalar(tag)}")

    # G11 4 必填
    # sources_used: list[str](按 OKF 风格单值字符串数组,不带嵌套)
    lines.append("sources_used:")
    for s in meta["sources_used"]:
        lines.append(f"  - {_scalar(s)}")

    lines.append(f"answer_to: {_scalar(meta['answer_to'])}")
    lines.append(f"generated_by: {_scalar(meta['generated_by'])}")

    # summary 块(首行强制 **问题**: <answer_to>)
    summary_val = meta.get("summary")
    if summary_val:
        lines.append("summary: |")
        for ln in str(summary_val).splitlines():
            lines.append(f"  {ln}")
    else:
        # 自动生成默认 summary(首行 `**问题**: ` 强制前缀)
        lines.append("summary: |")
        lines.append(f"  **问题**: {meta['answer_to']}")
        lines.append(f"  <本次推演的核心结论 ≤ 280 字符>")

    # links(列表;若 G10 §3.6.2 字段被 okf-lint 维护,可为空 list)
    links = meta.get("links", [])
    if not isinstance(links, list):
        links = []
    lines.append("links:")
    if links:
        for link in links:
            lines.append(f"  - {_scalar(link)}")
    else:
        lines.append("  []")  # 空数组等价

    # status(可选)
    if "status" in meta and meta["status"] is not None:
        lines.append(f"status: {_scalar(meta['status'])}")

    lines.append("---")
    return "\n".join(lines) + "\n"


def _build_skeleton_g11(body_text: str, sources_used: list[str], answer_to: str) -> str:
    """构造 G11 analysis 页 3 H2 骨架;保证末尾 > 引用: 行与 sources_used Set 一致。

    若 body_text 已经含 3 H2,直接返回(末尾 > 引用: 行校验);
    否则在末尾追加占位骨架(并强制把 > 引用: 行加在 ## 关联溯源 段)。
    """
    text = (body_text or "").rstrip()

    has_deduction = H2_DEDUCTION in text
    has_reference = H2_REFERENCE in text
    has_summary = H2_SUMMARY in text

    # 校验 / 补 > 引用: 行
    sources_set = set(sources_used)
    cur_refs = set()
    ref_match = REFERENCE_LINE_RE.search(text)
    if ref_match:
        line = ref_match.group(1)
        for tok in line.split(","):
            tok = tok.strip()
            if tok:
                cur_refs.add(tok)

    # 若正文无 > 引用: 行 → 必须追加(写到 ## 关联溯源 段末尾)
    if not has_reference:
        parts: list[str] = []
        parts.append(H2_REFERENCE)
        parts.append("")
        parts.append("<关联本次推演的关键 Wiki 事实与依据>")
        parts.append("")
        parts.append("> 引用: " + ", ".join(sources_used))
        text = (text + "\n\n" + "\n".join(parts)).rstrip() + "\n"
    elif not ref_match:
        # 已含 ## 关联溯源 段但无 > 引用: 行 → 追加
        # 找到 ## 关联溯源 段结束位置
        text = text + "\n\n> 引用: " + ", ".join(sources_used) + "\n"
    else:
        # 已有 > 引用: 行,但与 sources_used 不一致 → 强制同步(Set 校验 C15.4)
        if cur_refs != sources_set:
            text = re.sub(
                REFERENCE_LINE_RE,
                "> 引用: " + ", ".join(sources_used),
                text,
                count=1,
            )

    # 补缺 H2
    suffix_parts: list[str] = []
    if not has_deduction:
        suffix_parts.append(f"\n{H2_DEDUCTION}\n\n<本次推演的核心分析与架构逻辑>\n")
    if not has_summary:
        suffix_parts.append(f"\n{H2_SUMMARY}\n\n<一句话核心结论,可独立成立>\n")

    if suffix_parts:
        text = text.rstrip() + "\n" + "".join(suffix_parts).rstrip() + "\n"

    return text


def _read_body_file(body_file: Path) -> str:
    """读 body 文件(LLM 已写正文,不含 frontmatter)。"""
    if not body_file.exists():
        raise FileNotFoundError(f"--body-file 不存在:{body_file}")
    try:
        return body_file.read_text(encoding="utf-8")
    except OSError as e:
        raise OSError(f"读取 body-file 失败:{e}")


def _target_path(project: Path, ts_safe: str, slug: str) -> Path:
    """目标文件路径:knowledge/analyses/<ts>-<slug>.md。"""
    analyses_dir = project / "knowledge" / "analyses"
    analyses_dir.mkdir(parents=True, exist_ok=True)
    return analyses_dir / f"{ts_safe}-{slug}.md"


def _validate_set_compare(sources_used: list[str], body_text: str) -> None:
    """校验 > 引用: 行与 sources_used Set 一致(C15.4)。

    不一致 → 抛 ValueError(防 lint FAIL 蔓延)。
    """
    ref_match = REFERENCE_LINE_RE.search(body_text)
    if not ref_match:
        return  # _build_skeleton 已保证追加,这里兜底容忍
    line = ref_match.group(1)
    refs = {tok.strip() for tok in line.split(",") if tok.strip()}
    sources_set = set(sources_used)
    if refs != sources_set:
        raise ValueError(
            f"C15.4 FAIL:> 引用: 行 Set {refs} != sources_used Set {sources_set}"
        )


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口:写 knowledge/analyses/<ts>-<slug>.md。"""
    project = Path(args.project_dir).resolve()
    if not project.exists():
        raise FileNotFoundError(f"--project-dir 不存在:{project}")

    try:
        meta_raw = json.loads(args.meta_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"--meta-json 解析失败:{e}")
    if not isinstance(meta_raw, dict):
        raise ValueError("--meta-json 必须是 JSON object")

    # 自动补 generated_by(若未传)
    meta = _inject_generated_by_if_missing(meta_raw)
    _validate_meta(meta)

    # 校验保证 G11 4 必填已存在
    sources_used: list[str] = list(meta["sources_used"])
    answer_to: str = str(meta["answer_to"])

    body_file = Path(args.body_file)
    if not body_file.is_absolute():
        body_file = project / body_file
    body_text = _read_body_file(body_file)

    # 构造正文(注入 3 H2 骨架 + 同步 > 引用: 行)
    body = _build_skeleton_g11(body_text, sources_used, answer_to)
    _validate_set_compare(sources_used, body)

    # 构造 frontmatter
    fm = _build_frontmatter(meta)

    # 拼装 md
    full_md = fm + "\n" + body

    # 时间戳 sanitize
    ts_safe = _sanitize_timestamp(args.timestamp)
    slug = args.slug

    # 写盘:Q7 防护
    target = _target_path(project, ts_safe, slug)
    if target.exists():
        # 二次写:走 atomic_write_preserving_mtime
        atomic_write_preserving_mtime(target, full_md)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(full_md, encoding="utf-8")

    return {
        "path": str(target.relative_to(project)).replace("\\", "/"),
        "wrote": True,
        "size": target.stat().st_size,
        "ok": True,
        "ts_safe": ts_safe,
        "slug": slug,
        "sources_used_count": len(sources_used),
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="generate-analysis-page.py",
        description="写 knowledge/analyses/<timestamp>-<slug>.md(G11 analysis 4 必填 + 3 H2 + Q7)。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    parser.add_argument(
        "--timestamp",
        required=True,
        help="ISO 8601 时间戳(如 2026-09-01T14:30:00Z,内部冒号 → 连字符)。",
    )
    parser.add_argument(
        "--slug",
        required=True,
        help="analysis 页 slug(kebab-case)。",
    )
    parser.add_argument(
        "--meta-json",
        required=True,
        help="LLM 抽出的 frontmatter JSON(含 type=analysis + G11 4 必填)。",
    )
    parser.add_argument(
        "--body-file",
        required=True,
        help="LLM 已写好的正文 md 文件(不含 frontmatter)。",
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
    return 0


if __name__ == "__main__":
    sys.exit(main())

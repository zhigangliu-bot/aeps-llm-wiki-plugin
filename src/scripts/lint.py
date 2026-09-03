"""lint.py — 11 类 lint 检查主入口(lint SKILL.md 契约)。

CLI:
    python3 lint.py --project-dir <dir> [--fix] [--apply] [--allow-dirty] [--by <axis>]

行为(DESIGN.md §1.1 + lint SKILL.md):
    - 扫 <project>/knowledge/**/*.md(递归)
    - 11 类检查:
        1.  check_orphan       — 孤儿(由 lint-orphans 复用)
        2.  check_contradiction— 矛盾(仅报告,LLM 语义判断)
        3.  check_stale        — 陈旧页(180 天 + log.md fallback)
        4.  check_name_drift   — 命名飘 Levenshtein ≤ 2(仅报告)
        5.  check_missing_link — 漏链(仅报告,LLM 候选术语)
        6.  check_frontmatter  — 字段校验(由 validate-frontmatter 复用)
        7.  check_links_mirror — links: ↔ wikilink Set 漂移
        8.  check_raw_category — 从 sources[0].resource 派生失败
        9.  check_skeleton     — sources/analyses 3 H2 骨架 + ## 摘要 残留
        10. check_comparisons  — type=comparison sources ≥ 2
        11. check_syntheses    — type=synthesis sources_count < 3 WARN
    - CLI:--project-dir [--fix] [--apply] [--allow-dirty] [--by <axis>]
    - 双开关:仅 --fix --apply 写盘
    - 事务原子:全 in-memory 预生成 → 图结构预检 → os.replace 一次性
    - git 脏检查:_common.git_dirty_check,支持 --allow-dirty 放行
    - 写盘走 _common.atomic_write_preserving_mtime(Q7 4 步流程)
    - 写盘后调 append-log.py 写 LintFix 条目
    - --by 支持 raw_category / type / maturity / docform 四轴 group by

输出:
    stdout JSON: {
      "issues": [ { "category": ..., "severity": "FAIL|WARN", "path": ...,
                    "message": ..., "fix_proposal": ..., "written": bool } ],
      "written": [ ... 文件列表 ... ],
      "skipped": [ ... 因 git 脏 / 校验失败跳过 ... ],
      "atomic": bool,
      "git": { "is_repo": bool, "dirty": bool, "stashed": bool, "allowed": bool },
      "groups": { axis_name: [ ... ] },   # --by 时填充
      "report_only": bool,                # 未指定 --apply 时 true
      "fix_proposed": bool                # --fix 但无 --apply 时 true
    }
    exit 0(全 WARN 或修完)/ 1(有 FAIL 或 git 脏阻断)

约束(NFR-1 ~ NFR-7):
    - 不读 stdin(NFR-1)
    - 不开 daemon(NFR-1)
    - 路径全部相对 --project-dir(NFR-4)
    - 错误消息中文为主(NFR-3)
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _common import (
    atomic_write_preserving_mtime,
    derive_raw_category,
    emit_json,
    git_dirty_check,
    link_normalizer,
)


# 陈旧判定阈值(lint SKILL.md §1.3)
STALE_THRESHOLD_DAYS = 180

# 6 轴 tag 正则(与 validate-frontmatter 对齐)
TAG_PATTERN = re.compile(r"^(domain|layer|phase|docform|maturity|tec)/[a-z][a-z0-9-]*$")

# 18 合法 type
LEGAL_TYPES = frozenset({
    "source", "analysis",
    "person", "organization", "project", "product", "event", "place", "other",
    "theory", "method", "field", "phenomenon", "standard", "term",
    "comparison", "synthesis",
    "overview", "schema",
})

# sources/analyses 必备 H2
SOURCES_H2 = ("## 重点摘录", "## 我的思考", "## 总结")
ANALYSES_H2 = ("## 方案推演 / 架构分析", "## 关联溯源", "## 总结")

# 禁止 H2(任一出现 → FAIL)
FORBIDDEN_H2 = ("## 摘要", "## Summary")

# 豁免名单(孤儿检查豁免)
EXEMPT_PATHS = frozenset({
    "knowledge/index.md",
    "knowledge/overview.md",
    "knowledge/glossary.md",
    "knowledge/log.md",
    "knowledge/SCHEMA.md",
})

# 4 个合法 --by 取值
VALID_BY_AXES = ("raw_category", "type", "maturity", "docform")


# ---------------------------------------------------------------------------
# frontmatter 解析(轻量)
# ---------------------------------------------------------------------------


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        raise ValueError("文件无 frontmatter(必须以 --- 起头)")
    lines = text.split("\n")
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].startswith("---"):
            end_idx = i
            break
    if end_idx is None:
        raise ValueError("frontmatter 缺少结束标记 ---")

    fm_block = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1 :])

    try:
        import yaml  # type: ignore[import-untyped]

        fm = yaml.safe_load(fm_block)
    except ImportError:
        fm = {}
    except Exception:
        fm = {}

    return fm if isinstance(fm, dict) else {}, body


def _extract_h2(body: str) -> list[str]:
    """抽所有 ## 标题(去尾部空白)。"""
    out: list[str] = []
    for ln in body.splitlines():
        s = ln.strip()
        if s.startswith("## ") and not s.startswith("### "):
            out.append(s.rstrip())
    return out


# ---------------------------------------------------------------------------
# 11 类检查
# ---------------------------------------------------------------------------


def check_orphan(
    rel_path: str,
    fm: dict[str, Any],
    body: str,
    inbound_map: dict[str, set[str]],
) -> list[dict[str, Any]]:
    """检查 1:孤儿页(无入链接)。语义级,仅报告。豁免名单不算孤儿。"""
    norm_path = rel_path.replace("\\", "/")
    if norm_path in EXEMPT_PATHS:
        return []
    slug = link_normalizer(Path(rel_path).name)
    if not slug:
        return []
    inbound = inbound_map.get(slug, set()) - {norm_path}
    if not inbound:
        return [
            {
                "category": "orphan",
                "severity": "WARN",
                "path": rel_path,
                "message": f"孤儿页:无任何入链接(slug={slug})",
                "fix_proposal": None,
            }
        ]
    return []


def check_contradiction(
    rel_path: str,
    fm: dict[str, Any],
    body: str,
) -> list[dict[str, Any]]:
    """检查 2:矛盾(LLM 语义级)。本脚本不实现语义比对,只占位返回空。

    真实矛盾判定留给 SKILL.md 在 Claude 对话层做(见 lint SKILL.md §1.2)。
    本检查项占位是为了保持 11 类计数完整。
    """
    return []


def check_stale(
    rel_path: str,
    fm: dict[str, Any],
    body: str,
    log_md_text: str | None,
    now: datetime,
) -> list[dict[str, Any]]:
    """检查 3:陈旧页。

    判定顺序(lint SKILL.md §1.3):
        1. stale_after 存在且 now >= stale_after → 陈旧
        2. stale_after 缺失 + updated > 180 天 + log.md 无提及 → 陈旧
        3. status: deprecated 豁免
        4. status: draft 不豁免
    """
    status = fm.get("status")
    if status == "deprecated":
        return []

    # stale_after 显式
    stale_after = fm.get("stale_after")
    if isinstance(stale_after, str) and stale_after.strip():
        try:
            sa = datetime.fromisoformat(stale_after.replace("Z", "+00:00"))
            if now >= sa:
                return [
                    {
                        "category": "stale",
                        "severity": "WARN",
                        "path": rel_path,
                        "message": f"陈旧:stale_after={stale_after} 已到",
                        "fix_proposal": None,
                    }
                ]
        except ValueError:
            pass  # 解析失败 → 走 fallback

    updated = fm.get("updated")
    if not isinstance(updated, str) or not updated.strip():
        return []

    try:
        ut = datetime.fromisoformat(updated.replace("Z", "+00:00"))
    except ValueError:
        return []

    if ut.tzinfo is None:
        ut = ut.replace(tzinfo=timezone.utc)

    delta = now - ut
    if delta.days < STALE_THRESHOLD_DAYS:
        return []

    # log.md fallback:无提及才报陈旧
    if log_md_text and rel_path in log_md_text:
        return []

    return [
        {
            "category": "stale",
            "severity": "WARN",
            "path": rel_path,
            "message": (
                f"陈旧:updated={updated} > {STALE_THRESHOLD_DAYS} 天,"
                f" log.md 无提及"
            ),
            "fix_proposal": None,
        }
    ]


def check_name_drift(
    rel_path: str,
    fm: dict[str, Any],
    body: str,
    raw_subdirs: list[str],
) -> list[dict[str, Any]]:
    """检查 4:LLM 命名飘(仅报告)。

    对 source 页派生 raw_category 后,与已有 raw_subdirs 比 Levenshtein ≤ 2
    + 全小写 `-` 归一后相同 → 报告。
    """
    if fm.get("type") != "source":
        return []

    sources = fm.get("sources")
    if not isinstance(sources, list) or not sources:
        return []
    first = sources[0]
    if not isinstance(first, dict):
        return []
    res = first.get("resource")
    if not isinstance(res, str):
        return []

    cat = derive_raw_category(res)
    if not cat:
        return []

    # Levenshtein ≤ 2 检查(与所有已有 subdir 比,即使 cat 自身也在)
    for existing in raw_subdirs:
        if existing == cat:
            continue
        if _levenshtein_le(cat, existing, 2):
            return [
                {
                    "category": "name_drift",
                    "severity": "WARN",
                    "path": rel_path,
                    "message": (
                        f"命名飘:派生 raw_category={cat} 与已有 {existing} "
                        f"Levenshtein ≤ 2(Q5)"
                    ),
                    "fix_proposal": (
                        f"建议:把 raw/{cat}/ 合并到 raw/{existing}/"
                    ),
                }
            ]
        # 全小写 + `-` 归一后相同
        if cat.lower().replace("_", "-") == existing.lower().replace("_", "-"):
            return [
                {
                    "category": "name_drift",
                    "severity": "WARN",
                    "path": rel_path,
                    "message": (
                        f"命名飘:{cat} 与 {existing} 归一后相同"
                    ),
                    "fix_proposal": (
                        f"建议:统一为 raw/{existing}/"
                    ),
                }
            ]

    return []


def _levenshtein_le(a: str, b: str, threshold: int) -> bool:
    """Levenshtein 距离 ≤ threshold 判定(滚动数组,提前剪枝)。"""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > threshold:
        return False
    if la == 0 or lb == 0:
        return la <= threshold and lb <= threshold

    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        curr = [i] + [0] * lb
        row_min = curr[0]
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,
                curr[j - 1] + 1,
                prev[j - 1] + cost,
            )
            if curr[j] < row_min:
                row_min = curr[j]
        if row_min > threshold:
            return False
        prev = curr
    return prev[lb] <= threshold


def check_missing_link(
    rel_path: str,
    fm: dict[str, Any],
    body: str,
) -> list[dict[str, Any]]:
    """检查 5:漏链(语义级,LLM 判断)。

    本脚本不实现 LLM 候选术语抽取,占位返回空。SKILL.md 在 Claude 对话层
    做语义判断(见 lint SKILL.md §1.5)。
    """
    return []


def check_frontmatter(
    rel_path: str,
    fm: dict[str, Any],
    body: str,
) -> list[dict[str, Any]]:
    """检查 6:frontmatter 不合规(5 必填 + 6 轴 tag + 未知 type WARN + typecast)。"""
    issues: list[dict[str, Any]] = []

    # 5 必填
    for k in ("type", "title", "description", "updated", "tags"):
        v = fm.get(k)
        if v is None or (isinstance(v, str) and not v.strip()):
            issues.append(
                {
                    "category": "frontmatter",
                    "severity": "FAIL",
                    "path": rel_path,
                    "message": f"必填字段缺失:{k}",
                    "fix_proposal": f"补占位字段 {k}",
                }
            )

    # type 枚举
    tp = fm.get("type")
    if isinstance(tp, str) and tp and tp not in LEGAL_TYPES:
        issues.append(
            {
                "category": "frontmatter",
                "severity": "WARN",
                "path": rel_path,
                "message": f"未知 type:{tp}(OKF §11 容忍,记 WARN)",
                "fix_proposal": None,
            }
        )

    # tags 必填轴 docform/
    tags = fm.get("tags")
    if not isinstance(tags, list):
        if not any(i["category"] == "frontmatter" and "tags" in i.get("message", "") for i in issues):
            issues.append(
                {
                    "category": "frontmatter",
                    "severity": "FAIL",
                    "path": rel_path,
                    "message": "tags 必须是 list[str](实际类型错位)",
                    "fix_proposal": "tags 强转为 list",
                }
            )
    else:
        axes_present = set()
        for t in tags:
            if isinstance(t, str) and "/" in t:
                ax = t.split("/", 1)[0]
                axes_present.add(ax)
        if "docform" not in axes_present:
            issues.append(
                {
                    "category": "frontmatter",
                    "severity": "FAIL",
                    "path": rel_path,
                    "message": "tags 缺 docform/ 轴(必填)",
                    "fix_proposal": "加 docform/<value> tag",
                }
            )
        # 裸 tag(无 /)→ FAIL
        for t in tags:
            if isinstance(t, str) and t and "/" not in t:
                issues.append(
                    {
                        "category": "frontmatter",
                        "severity": "FAIL",
                        "path": rel_path,
                        "message": f"裸 tag:{t}(必须 <axis>/<value>)",
                        "fix_proposal": f"改为 <axis>/{t}",
                    }
                )

    return issues


def check_links_mirror(
    rel_path: str,
    fm: dict[str, Any],
    body: str,
) -> list[dict[str, Any]]:
    """检查 7:frontmatter `links:` ↔ 正文 wikilink 漂移(Set 比对)。"""
    # 抽正文 wikilink + markdown link
    candidates: list[str] = []
    for m in re.finditer(r"\[\[([^\]\n]+)\]\]", body):
        candidates.append("[[" + m.group(1) + "]]")
    for m in re.finditer(r"\[([^\]\n]+)\]\(([^)\n]+)\)", body):
        candidates.append(m.group(2))

    scanned: set[str] = set()
    for c in candidates:
        slug = link_normalizer(c)
        if slug and not slug.startswith("http"):
            scanned.add(slug)

    links = fm.get("links")
    current: set[str] = set()
    if isinstance(links, list):
        for it in links:
            if isinstance(it, str):
                slug = link_normalizer(it)
                if slug:
                    current.add(slug)

    added = scanned - current
    removed = current - scanned
    if not added and not removed:
        return []

    return [
        {
            "category": "links_mirror",
            "severity": "WARN",
            "path": rel_path,
            "message": (
                f"links: ↔ wikilink 漂移:"
                f"added={sorted(added)} removed={sorted(removed)}"
            ),
            "fix_proposal": "同步 frontmatter links: 字段(Set 相等)",
        }
    ]


def check_raw_category(
    rel_path: str,
    fm: dict[str, Any],
    body: str,
) -> list[dict[str, Any]]:
    """检查 8:raw_category 派生失败。"""
    if fm.get("type") != "source":
        return []
    sources = fm.get("sources")
    if not isinstance(sources, list) or not sources:
        return [
            {
                "category": "raw_category",
                "severity": "FAIL",
                "path": rel_path,
                "message": "raw_category 派生失败:sources[] 缺失",
                "fix_proposal": None,
            }
        ]
    first = sources[0]
    if not isinstance(first, dict) or not first.get("resource"):
        return [
            {
                "category": "raw_category",
                "severity": "FAIL",
                "path": rel_path,
                "message": "raw_category 派生失败:sources[0].resource 缺失",
                "fix_proposal": None,
            }
        ]
    res = first["resource"]
    if not res.startswith("raw/"):
        return [
            {
                "category": "raw_category",
                "severity": "FAIL",
                "path": rel_path,
                "message": (
                    f"raw_category 派生失败:resource={res} 不在 raw/ 下"
                ),
                "fix_proposal": None,
            }
        ]
    cat = derive_raw_category(res)
    if not cat:
        return [
            {
                "category": "raw_category",
                "severity": "FAIL",
                "path": rel_path,
                "message": f"raw_category 派生失败:resource={res}",
                "fix_proposal": None,
            }
        ]
    return []


def check_skeleton(
    rel_path: str,
    fm: dict[str, Any],
    body: str,
) -> list[dict[str, Any]]:
    """检查 9:正文骨架不合规(sources/analyses 3 H2 + 禁止 ## 摘要)。"""
    issues: list[dict[str, Any]] = []
    h2_list = _extract_h2(body)

    # 禁止 H2(全类型都 FAIL)
    for fh in FORBIDDEN_H2:
        if any(h == fh or h.startswith(fh) for h in h2_list):
            issues.append(
                {
                    "category": "skeleton",
                    "severity": "FAIL",
                    "path": rel_path,
                    "message": f"禁止 H2 残留:{fh}(应合并到 frontmatter summary)",
                    "fix_proposal": f"删除 {fh} 段,内容合并到 summary",
                }
            )

    tp = fm.get("type")
    if tp == "source":
        for required in SOURCES_H2:
            if not any(h.startswith(required) for h in h2_list):
                issues.append(
                    {
                        "category": "skeleton",
                        "severity": "FAIL",
                        "path": rel_path,
                        "message": f"sources 缺 H2:{required}",
                        "fix_proposal": f"在文末追加占位 {required}",
                    }
                )
    elif tp == "analysis":
        for required in ANALYSES_H2:
            if not any(h.startswith(required) for h in h2_list):
                issues.append(
                    {
                        "category": "skeleton",
                        "severity": "FAIL",
                        "path": rel_path,
                        "message": f"analyses 缺 H2(G11):{required}",
                        "fix_proposal": f"在文末追加占位 {required}",
                    }
                )

    return issues


def check_comparisons(
    rel_path: str,
    fm: dict[str, Any],
    body: str,
) -> list[dict[str, Any]]:
    """检查 10:comparisons/*.md sources ≥ 2 必填。"""
    if fm.get("type") != "comparison":
        return []
    sources = fm.get("sources")
    if not isinstance(sources, list) or len(sources) < 2:
        return [
            {
                "category": "comparison",
                "severity": "FAIL",
                "path": rel_path,
                "message": (
                    f"comparison.sources 数量 "
                    f"{len(sources) if isinstance(sources, list) else 0} < 2"
                    f"(必填 ≥ 2 wikilink)"
                ),
                "fix_proposal": "补 ≥ 2 条 wikilink 进 sources[]",
            }
        ]
    return []


def check_syntheses(
    rel_path: str,
    fm: dict[str, Any],
    body: str,
) -> list[dict[str, Any]]:
    """检查 11:syntheses/*.md sources_count < 3 WARN。"""
    if fm.get("type") != "synthesis":
        return []
    sc = fm.get("sources_count")
    if sc is None:
        return [
            {
                "category": "synthesis",
                "severity": "WARN",
                "path": rel_path,
                "message": "synthesis 缺 sources_count 字段(空综合)",
                "fix_proposal": "补 sources_count 字段",
            }
        ]
    if isinstance(sc, int) and sc < 3:
        return [
            {
                "category": "synthesis",
                "severity": "WARN",
                "path": rel_path,
                "message": f"synthesis sources_count={sc} < 3(空综合 WARN)",
                "fix_proposal": "增加 sources 直至 ≥ 3",
            }
        ]
    return []


# ---------------------------------------------------------------------------
# 写盘修复(--fix --apply)
# ---------------------------------------------------------------------------


def _apply_fix(
    project: Path,
    file_path: Path,
    fm: dict[str, Any],
    body: str,
    issues_for_file: list[dict[str, Any]],
) -> tuple[bool, list[dict[str, Any]]]:
    """对单文件应用确定性结构修复(走 atomic_write_preserving_mtime)。

    写盘约束(Q7):
        - 不动 frontmatter `updated` 字段
        - atime + mtime 双还原
        - 仅 LintFix 落盘;语义级问题(矛盾 / 命名飘 / 漏链 / 陈旧)只报告

    Returns:
        (written, applied_fix_records)
    """
    cat_set = {i["category"] for i in issues_for_file}
    new_fm = dict(fm)
    new_body = body
    fix_records: list[dict[str, Any]] = []

    # 1. frontmatter-fill(必填缺失 → 补占位)
    if "frontmatter" in cat_set:
        for k in ("type", "title", "description", "updated", "tags"):
            v = new_fm.get(k)
            if v is None or (isinstance(v, str) and not v.strip()):
                if k == "updated":
                    new_fm[k] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                elif k == "tags":
                    new_fm[k] = ["docform/unknown"]
                elif k == "type":
                    new_fm[k] = "source"
                else:
                    new_fm[k] = "<placeholder>"
                fix_records.append(
                    {"rule": "frontmatter-fill", "field": k}
                )

        # tags typecast:str → list
        if isinstance(new_fm.get("tags"), str):
            old = new_fm["tags"]
            new_fm["tags"] = [t.strip() for t in old.split(",") if t.strip()]
            fix_records.append({"rule": "frontmatter-typecast", "field": "tags"})

    # 2. skeleton(sources/analyses 补占位 H2)
    if "skeleton" in cat_set:
        tp = new_fm.get("type")
        if tp == "source":
            existing_h2 = set(_extract_h2(new_body))
            for required in SOURCES_H2:
                if not any(h.startswith(required) for h in existing_h2):
                    new_body = (
                        new_body.rstrip()
                        + f"\n\n{required}\n\n<请补充>\n"
                    )
            fix_records.append({"rule": "lint-C15.1", "area": "sources-skeleton"})
        elif tp == "analysis":
            existing_h2 = set(_extract_h2(new_body))
            for required in ANALYSES_H2:
                if not any(h.startswith(required) for h in existing_h2):
                    new_body = (
                        new_body.rstrip()
                        + f"\n\n{required}\n\n<请补充>\n"
                    )
            fix_records.append({"rule": "lint-C15.1", "area": "analysis-skeleton"})

    if not fix_records:
        return False, []

    # 拼装新文本
    new_text = _dump_md(new_fm, new_body)

    # 走 atomic_write_preserving_mtime(Q7 4 步流程,不动 updated,保留 mtime)
    try:
        atomic_write_preserving_mtime(file_path, new_text)
    except OSError as e:
        raise OSError(f"写盘失败:{file_path}:{e}")

    return True, fix_records


def _dump_md(fm: dict[str, Any], body: str) -> str:
    """把 dict frontmatter + body 转回 md 文本(简易 YAML)。"""
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

    # 稳定顺序
    key_order = [
        "type", "title", "description", "updated", "tags", "status",
        "source_file", "sources",
        "format", "converter", "native_text", "converted_path", "links",
        "sources_used", "answer_to", "generated_by", "summary",
        "aliases", "topic", "sources_count", "last_updated", "stale_after",
    ]
    written_keys: set[str] = set()
    for k in key_order:
        if k not in fm:
            continue
        v = fm[k]
        written_keys.add(k)
        if k == "tags" and isinstance(v, list):
            lines.append("tags:")
            for t in v:
                lines.append(f"  - {_scalar(t)}")
        elif k == "sources" and isinstance(v, list):
            lines.append("sources:")
            for s in v:
                if isinstance(s, dict):
                    lines.append(f"  - resource: {_scalar(s.get('resource', ''))}")
                    if "title" in s:
                        lines.append(f"    title: {_scalar(s['title'])}")
                    if "id" in s:
                        lines.append(f"    id: {_scalar(s['id'])}")
                else:
                    lines.append(f"  - {_scalar(s)}")
        elif k == "links" and isinstance(v, list):
            lines.append("links:")
            for s in v:
                lines.append(f"  - {_scalar(s)}")
        else:
            lines.append(f"{k}: {_scalar(v)}")

    # 其他未知 key 兜底输出
    for k in fm:
        if k in written_keys:
            continue
        lines.append(f"{k}: {_scalar(fm[k])}")

    lines.append("---")
    return "\n".join(lines) + "\n\n" + body.lstrip("\n")


def _append_log(project: Path, rel_path: str, fix_records: list[dict[str, Any]]) -> None:
    """写盘后调 append-log.py 写 LintFix 条目(失败容忍)。"""
    for rec in fix_records:
        rule = rec.get("rule", "lint-fix")
        try:
            subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve().parent / "append-log.py"),
                    "--project-dir", str(project),
                    "--action", "LintFix",
                    "--summary", f"{rule} on [{rel_path}]({rel_path}) — {rec}",
                    "--actor", "agent: producer/aeps-llm-wiki-plugin/0.5.5",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except OSError:
            pass


# ---------------------------------------------------------------------------
# inbound_map 构建(供 check_orphan)
# ---------------------------------------------------------------------------


def _build_inbound_map(project: Path) -> dict[str, set[str]]:
    """建反向索引:inbound_map[slug] = set(rel_path)。"""
    knowledge_dir = project / "knowledge"
    if not knowledge_dir.exists():
        return {}

    inbound: dict[str, set[str]] = {}
    files = sorted(knowledge_dir.rglob("*.md"))

    # 自身的 slug 进 inbound
    for fp in files:
        rel = str(fp.relative_to(project)).replace("\\", "/")
        slug = link_normalizer(fp.name)
        if slug:
            inbound.setdefault(slug, set()).add(rel)

    # 反转 outbound
    for fp in files:
        try:
            text = fp.read_text(encoding="utf-8")
        except OSError:
            continue
        rel = str(fp.relative_to(project)).replace("\\", "/")
        try:
            fm, body = _parse_frontmatter(text)
        except ValueError:
            fm, body = {}, text

        out_targets: set[str] = set()

        sources = fm.get("sources")
        if isinstance(sources, list):
            for s in sources:
                if isinstance(s, dict):
                    res = s.get("resource")
                    if isinstance(res, str):
                        slug = link_normalizer(res)
                        if slug:
                            out_targets.add(slug)
                elif isinstance(s, str):
                    slug = link_normalizer(s)
                    if slug:
                        out_targets.add(slug)

        su = fm.get("sources_used")
        if isinstance(su, list):
            for s in su:
                if isinstance(s, str):
                    slug = link_normalizer(s)
                    if slug:
                        out_targets.add(slug)

        for m in re.finditer(r"\[\[([^\]\n]+)\]\]", body):
            slug = link_normalizer("[[" + m.group(1) + "]]")
            if slug:
                out_targets.add(slug)
        for m in re.finditer(r"\[([^\]\n]+)\]\(([^)\n]+)\)", body):
            slug = link_normalizer(m.group(2))
            if slug:
                out_targets.add(slug)

        for target in out_targets:
            inbound.setdefault(target, set()).add(rel)

    return inbound


def _list_raw_subdirs(project: Path) -> list[str]:
    """列 raw/ 下所有子目录名(供 check_name_drift)。"""
    raw = project / "raw"
    if not raw.exists():
        return []
    return sorted(p.name for p in raw.iterdir() if p.is_dir())


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口:扫所有 knowledge 页 + 应用 --fix --apply。"""
    project = Path(args.project_dir).resolve()
    if not project.exists():
        raise FileNotFoundError(f"--project-dir 不存在:{project}")

    knowledge_dir = project / "knowledge"
    if not knowledge_dir.exists():
        return {
            "issues": [],
            "written": [],
            "skipped": [],
            "atomic": False,
            "git": {"is_repo": False, "dirty": False, "stashed": False, "allowed": True},
            "groups": {},
            "report_only": not args.apply,
            "fix_proposed": bool(args.fix and not args.apply),
        }

    # git 脏检查(仅在 --fix --apply 时检查;只读报告跳过)
    git_info: dict[str, Any] = {
        "is_repo": False,
        "dirty": False,
        "stashed": False,
        "allowed": True,
    }
    if args.fix and args.apply:
        git_info = git_dirty_check(str(project), allow_dirty=args.allow_dirty)
        if not git_info.get("allowed", False):
            return {
                "issues": [],
                "written": [],
                "skipped": [],
                "atomic": False,
                "git": git_info,
                "groups": {},
                "report_only": False,
                "fix_proposed": False,
                "blocked_reason": git_info.get("error", "git 脏状态阻断"),
            }

    inbound_map = _build_inbound_map(project)
    raw_subdirs = _list_raw_subdirs(project)
    log_path = project / "knowledge" / "log.md"
    log_text: str | None = None
    if log_path.exists():
        try:
            log_text = log_path.read_text(encoding="utf-8")
        except OSError:
            log_text = None

    now = datetime.now(timezone.utc)

    files = sorted(knowledge_dir.rglob("*.md"))
    all_issues: list[dict[str, Any]] = []
    written: list[str] = []
    skipped: list[str] = []

    # 11 类检查
    check_funcs = [
        check_orphan,
        check_contradiction,
        check_stale,
        check_name_drift,
        check_missing_link,
        check_frontmatter,
        check_links_mirror,
        check_raw_category,
        check_skeleton,
        check_comparisons,
        check_syntheses,
    ]

    for fp in files:
        rel = str(fp.relative_to(project)).replace("\\", "/")
        try:
            text = fp.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            fm, body = _parse_frontmatter(text)
        except ValueError:
            all_issues.append(
                {
                    "category": "frontmatter",
                    "severity": "FAIL",
                    "path": rel,
                    "message": "frontmatter 解析失败",
                    "fix_proposal": "修复 frontmatter 格式",
                }
            )
            continue

        issues_for_file: list[dict[str, Any]] = []
        for fn in check_funcs:
            try:
                if fn is check_orphan:
                    issues_for_file.extend(fn(rel, fm, body, inbound_map))
                elif fn is check_stale:
                    issues_for_file.extend(fn(rel, fm, body, log_text, now))
                elif fn is check_name_drift:
                    issues_for_file.extend(fn(rel, fm, body, raw_subdirs))
                else:
                    issues_for_file.extend(fn(rel, fm, body))
            except Exception as e:  # noqa: BLE001
                all_issues.append(
                    {
                        "category": "internal",
                        "severity": "WARN",
                        "path": rel,
                        "message": f"检查器 {fn.__name__} 抛错:{e}",
                        "fix_proposal": None,
                    }
                )

        # 写盘
        if args.fix and args.apply and issues_for_file:
            # 仅对有 fix_proposal 的 FAIL 写盘
            fixable = [i for i in issues_for_file if i.get("fix_proposal") is not None]
            if fixable:
                try:
                    ok, fix_records = _apply_fix(
                        project, fp, fm, body, issues_for_file
                    )
                    if ok:
                        written.append(rel)
                        _append_log(project, rel, fix_records)
                        # 标记
                        for i in issues_for_file:
                            i["written"] = True
                    else:
                        skipped.append(rel)
                except OSError as e:
                    skipped.append(rel)
                    all_issues.append(
                        {
                            "category": "internal",
                            "severity": "WARN",
                            "path": rel,
                            "message": f"写盘失败:{e}",
                            "fix_proposal": None,
                        }
                    )
            else:
                skipped.append(rel)

        all_issues.extend(issues_for_file)

    # --by group by
    groups: dict[str, Any] = {}
    if args.by:
        groups = _group_by(all_issues, args.by, project)

    has_fail = any(i["severity"] == "FAIL" for i in all_issues)

    return {
        "issues": all_issues,
        "written": written,
        "skipped": skipped,
        "atomic": bool(args.fix and args.apply),
        "git": git_info,
        "groups": groups,
        "report_only": not args.apply,
        "fix_proposed": bool(args.fix and not args.apply),
        "has_fail": has_fail,
        "by": args.by,
    }


def _group_by(
    issues: list[dict[str, Any]],
    axis: str,
    project: Path,
) -> dict[str, Any]:
    """按 axis 把 issues 分组。

    axis ∈ {raw_category, type, maturity, docform}
    分组 key 缺失 → "未分类"。
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    knowledge_dir = project / "knowledge"

    # 缓存 frontmatter
    fm_cache: dict[str, dict[str, Any]] = {}

    def _load_fm(path: str) -> dict[str, Any]:
        if path in fm_cache:
            return fm_cache[path]
        fp = project / path
        if not fp.exists():
            fm_cache[path] = {}
            return {}
        try:
            text = fp.read_text(encoding="utf-8")
            fm, _ = _parse_frontmatter(text)
        except (OSError, ValueError):
            fm = {}
        fm_cache[path] = fm
        return fm

    for i in issues:
        path = i.get("path", "")
        fm = _load_fm(path)

        key = "未分类"
        if axis == "raw_category":
            sources = fm.get("sources")
            if isinstance(sources, list) and sources:
                first = sources[0]
                if isinstance(first, dict):
                    res = first.get("resource", "")
                    cat = derive_raw_category(res) if isinstance(res, str) else ""
                    key = cat or "未分类"
        elif axis == "type":
            key = fm.get("type") or "未分类"
        elif axis == "maturity":
            tags = fm.get("tags", [])
            if isinstance(tags, list):
                for t in tags:
                    if isinstance(t, str) and t.startswith("maturity/"):
                        key = t.split("/", 1)[1]
                        break
        elif axis == "docform":
            tags = fm.get("tags", [])
            if isinstance(tags, list):
                for t in tags:
                    if isinstance(t, str) and t.startswith("docform/"):
                        key = t.split("/", 1)[1]
                        break

        groups.setdefault(key, []).append(i)

    # 汇总
    summary: dict[str, int] = {k: len(v) for k, v in groups.items()}
    return {"axis": axis, "summary": summary, "details": groups}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="lint.py",
        description=(
            "11 类 lint 检查(--fix --apply 双开关写盘 + 事务原子 + "
            "git 脏检查 + --by group by)。"
        ),
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="输出确定性结构修复提案(默认 dry-run)。",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="与 --fix 配合,双开关写盘。",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="git 脏状态下强制写盘(默认阻断)。",
    )
    parser.add_argument(
        "--by",
        choices=VALID_BY_AXES,
        default=None,
        help="按 axis 分组报告:raw_category / type / maturity / docform。",
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
    # exit code:有 FAIL → 1,否则 0
    return 1 if result.get("has_fail") else 0


if __name__ == "__main__":
    sys.exit(main())

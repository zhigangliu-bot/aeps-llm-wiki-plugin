"""lint-orphans.py — 扫 knowledge/**/*.md 找孤儿(无入链接 + 不在豁免名单)。

CLI:
    python3 lint-orphans.py --project-dir <dir>

行为(lint SKILL.md §1.1):
    - 扫 <project>/knowledge/**/*.md(递归)
    - 孤儿定义:无任何入链接(frontmatter `sources[]` + 正文 `[[wikilink]]`)
    - 豁免名单:
        * knowledge/index.md
        * knowledge/overview.md
        * knowledge/glossary.md
    - 入链接收集:
        * frontmatter `sources[].resource`(OKF §5.1)归一后作为 inbound
        * 正文 `[[wikilink]]` 出现 → 该 wikilink target 所在的 .md 视为有入链接
        * 其他 markdown link [text](path) 也算入(归一并经 link_normalizer)

输出:
    stdout JSON: {
      "orphans": [
        {"path": "knowledge/...", "has_no_inbound_link": true, "exempt": false,
         "reason": "..."}
      ],
      "total": N,
      "scanned": M
    }
    exit 0

约束(NFR-1 ~ NFR-7):
    - 不读 stdin(NFR-1)
    - 不开 daemon(NFR-1)
    - 路径全部相对 --project-dir(NFR-4)
    - 不写文件(纯扫描)
    - 错误消息中文为主(NFR-3)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from _common import emit_json, link_normalizer


# 豁免名单(精确相对路径,与 --project-dir 拼接)
EXEMPT_PATHS = frozenset({
    "knowledge/index.md",
    "knowledge/overview.md",
    "knowledge/glossary.md",
    "knowledge/log.md",
    "knowledge/SCHEMA.md",
})

# [[wikilink]] 提取
WIKILINK_RE = re.compile(r"\[\[([^\]\n]+)\]\]")
# markdown link
MD_LINK_RE = re.compile(r"\[([^\]\n]+)\]\(([^)\n]+)\)")


def _list_knowledge_files(knowledge_dir: Path) -> list[Path]:
    """递归扫 knowledge/ 下所有 .md(排除 SCHEMA.md / log.md / index.md 等豁免不剔除,仅扫描)。"""
    if not knowledge_dir.exists():
        return []
    return sorted(knowledge_dir.rglob("*.md"))


def _parse_frontmatter_minimal(text: str) -> dict[str, Any]:
    """极简 frontmatter 解析(只关心 sources[])。失败 → {}。"""
    if not text.startswith("---"):
        return {}
    lines = text.split("\n")
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].startswith("---"):
            end_idx = i
            break
    if end_idx is None:
        return {}

    fm_block = "\n".join(lines[1:end_idx])
    try:
        import yaml  # type: ignore[import-untyped]

        fm = yaml.safe_load(fm_block)
    except ImportError:
        return {}
    except Exception:
        return {}

    return fm if isinstance(fm, dict) else {}


def _extract_inbound_links(text: str) -> set[str]:
    """从单文件正文 + frontmatter 抽出所有归一后的 inbound target slug。

    inbound 含义:本页"指向"的其他页 slug 集合 — 用于判断"谁是 inbound target"。
    反向思考:文件 A 含 [[B]],则 B 的 inbound_set 包含 A 的 slug(即 A 反向链接 B)。
    在本脚本里,我们用 build_inbound_map:
        先对所有页跑一次本函数,得到每页 outbound_set,
        再反转成 inbound_map[target_slug] = set(source_path)。

    Args:
        text: 完整文件文本(含 frontmatter)。

    Returns:
        归一后的 outbound slug 集合。
    """
    fm, body = _parse_frontmatter_minimal(text), text
    # 找 frontmatter 边界,把 body 分离
    if text.startswith("---"):
        lines = text.split("\n")
        end_idx = None
        for i in range(1, len(lines)):
            if lines[i].startswith("---"):
                end_idx = i
                break
        if end_idx is not None:
            body = "\n".join(lines[end_idx + 1 :])

    out: set[str] = set()

    # frontmatter sources[].resource
    sources = fm.get("sources")
    if isinstance(sources, list):
        for s in sources:
            if isinstance(s, dict):
                res = s.get("resource")
                if isinstance(res, str):
                    slug = link_normalizer(res)
                    if slug:
                        out.add(slug)
            elif isinstance(s, str):
                slug = link_normalizer(s)
                if slug:
                    out.add(slug)

    # frontmatter sources_used(analysis 页)
    su = fm.get("sources_used")
    if isinstance(su, list):
        for s in su:
            if isinstance(s, str):
                slug = link_normalizer(s)
                if slug:
                    out.add(slug)

    # 正文 [[wikilink]]
    for m in WIKILINK_RE.finditer(body):
        slug = link_normalizer("[[" + m.group(1) + "]]")
        if slug:
            out.add(slug)

    # 正文 markdown link(相对路径)
    for m in MD_LINK_RE.finditer(body):
        slug = link_normalizer(m.group(2))
        if slug:
            out.add(slug)

    return out


def _build_inbound_map(project: Path) -> tuple[dict[str, set[str]], dict[Path, str]]:
    """建反向索引:inbound_map[slug] = set(rel_path_str)。

    同时返回 path → rel_path 映射,便于按 path 反查 slug。

    Returns:
        (inbound_map, path_to_relpath)
    """
    knowledge_dir = project / "knowledge"
    files = _list_knowledge_files(knowledge_dir)

    path_to_relpath: dict[Path, str] = {}
    outbound: dict[Path, set[str]] = {}

    for fp in files:
        try:
            text = fp.read_text(encoding="utf-8")
        except OSError:
            continue
        rel = str(fp.relative_to(project)).replace("\\", "/")
        path_to_relpath[fp] = rel
        outbound[fp] = _extract_inbound_links(text)

    inbound_map: dict[str, set[str]] = {}
    # 用所有页面的 slug(其文件名)作为 key 候选
    for fp in files:
        rel = path_to_relpath[fp]
        slug_for_self = link_normalizer(fp.name)
        if slug_for_self:
            inbound_map.setdefault(slug_for_self, set()).add(rel)

    # 反转 outbound
    for fp, targets in outbound.items():
        rel = path_to_relpath[fp]
        for target_slug in targets:
            inbound_map.setdefault(target_slug, set()).add(rel)

    return inbound_map, path_to_relpath


def _is_exempt(rel_path: str) -> bool:
    """豁免名单判定(精确相对路径)。"""
    # 统一分隔符
    norm = rel_path.replace("\\", "/")
    # 去掉前导 ./(允许)
    if norm.startswith("./"):
        norm = norm[2:]
    return norm in EXEMPT_PATHS


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口:扫 knowledge/**/*.md,识别孤儿。"""
    project = Path(args.project_dir).resolve()
    if not project.exists():
        raise FileNotFoundError(f"--project-dir 不存在:{project}")

    knowledge_dir = project / "knowledge"
    if not knowledge_dir.exists():
        return {"orphans": [], "total": 0, "scanned": 0}

    inbound_map, path_to_relpath = _build_inbound_map(project)

    orphans: list[dict[str, Any]] = []
    scanned = 0
    for fp, rel in path_to_relpath.items():
        scanned += 1
        slug = link_normalizer(fp.name)
        # 跳过无 slug 的(理论上 .md 文件都有 name,但保险)
        if not slug:
            continue

        exempt = _is_exempt(rel)
        inbound_sources = inbound_map.get(slug, set())

        # 去掉自己链接自己(self-loop 不算入)
        inbound_sources = {s for s in inbound_sources if s != rel}

        if not inbound_sources and not exempt:
            orphans.append(
                {
                    "path": rel,
                    "has_no_inbound_link": True,
                    "exempt": False,
                    "reason": "无任何入链接",
                }
            )

    return {
        "orphans": orphans,
        "total": len(orphans),
        "scanned": scanned,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="lint-orphans.py",
        description="扫 knowledge/**/*.md 找孤儿(豁免 index/overview/glossary)。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = run(args)
    except FileNotFoundError as e:
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

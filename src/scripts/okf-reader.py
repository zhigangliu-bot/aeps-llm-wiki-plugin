"""okf-reader.py — OKF v0.2 reader:产 frontmatter + sources 列表。

CLI:
    python3 okf-reader.py --project-dir . --file <knowledge-page>.md

行为(DESIGN.md §1.1 + §3.6 + OKF v0.2 §9):
    - 读 <project>/knowledge/<file> 知识页 frontmatter + 正文
    - 产 OKF `sources` 列表:
        * **优先**:frontmatter `links:` 数组
        * **fallback**:扫正文 `[[wikilink]]` + `[markdown link](path)`
        * **fallback**:扫正文裸 URL(http/https)
    - 去重(用 _common.link_normalizer 归一)
    - 纯读,不写盘

输出:
    stdout JSON: {
        "sources": [
            {"type": "wikilink"|"markdown"|"url"|"frontmatter_link",
             "target": "sources/foo.md" 或 "https://..."}
        ],
        "count": N,
        "frontmatter": { ... }
    }
    exit 0 / 1

约束(NFR-1 ~ NFR-7):
    - 只读 knowledge/<path>(NFR-4)
    - 不写盘
    - 不读 stdin
    - 错误消息中文为主
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from _common import emit_json, link_normalizer


# frontmatter 与正文分割
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)

# wikilink 抽取
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")

# markdown link 抽取 [text](path)
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

# 裸 URL 抽取
URL_RE = re.compile(r"https?://[^\s)\]\"\'<>]+")


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """极简 frontmatter 解析(支持 list / scalar,够 okf-reader 用)。"""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return ({}, text)
    block = m.group(1)
    body = text[m.end():]
    fm: dict[str, Any] = {}
    cur_key: str | None = None
    for ln in block.splitlines():
        if not ln.strip():
            cur_key = None
            continue
        if ln.startswith("  - ") and cur_key:
            item = ln[4:].strip()
            # 字符串单引号 / 双引号包裹(形如 '[[link]]' 或 "[[link]]")
            if len(item) >= 2 and ((item[0] == "'" and item[-1] == "'")
                                    or (item[0] == '"' and item[-1] == '"')):
                item = item[1:-1]
            v = fm.get(cur_key)
            if isinstance(v, list):
                v.append(item)
            continue
        if ":" in ln:
            k, _, v = ln.partition(":")
            k = k.strip()
            v = v.strip()
            if not v:
                fm[k] = []
                cur_key = k
            else:
                cur_key = None
                if v.startswith("'") and v.endswith("'"):
                    v = v[1:-1]
                elif v.startswith('"') and v.endswith('"'):
                    v = v[1:-1]
                # 尝试裸 list literal:空数组 []
                if v == "[]":
                    fm[k] = []
                else:
                    fm[k] = v
        else:
            cur_key = None
    return (fm, body)


def _extract_from_links(fm: dict[str, Any]) -> list[dict[str, str]]:
    """从 frontmatter `links:` 数组抽 targets。

    处理规则:
        - 字符串 "[[foo]]" → target=foo(去 brackets);字符串 "foo" → 直接 target=foo
        - 字典型(OKF 偶尔用)→ 抽 'resource' / 'target' / 'url' 字段
    """
    raw = fm.get("links")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, str):
            target = link_normalizer(item)
            if target:
                out.append({"type": "frontmatter_link", "target": target})
        elif isinstance(item, dict):
            for k in ("resource", "target", "url"):
                v = item.get(k)
                if isinstance(v, str) and v:
                    out.append({"type": "frontmatter_link", "target": link_normalizer(v)})
                    break
    return out


def _extract_wikilinks(body: str) -> list[dict[str, str]]:
    """正文 [[wikilink]] 抽取。"""
    out: list[dict[str, str]] = []
    for m in WIKILINK_RE.finditer(body):
        target = link_normalizer(m.group(1))
        if target:
            out.append({"type": "wikilink", "target": target})
    return out


def _extract_markdown_links(body: str) -> list[dict[str, str]]:
    """正文 [text](path) 抽取(.md / http 路径)。"""
    out: list[dict[str, str]] = []
    for m in MARKDOWN_LINK_RE.finditer(body):
        path = m.group(2).strip()
        # 跳过 [markdown link](#anchor) 这类
        if path.startswith("#"):
            continue
        # 仅 .md 相对路径纳入(外链 URL 走 URL_RE)
        if path.endswith(".md") or path.endswith(".md)"):
            normalized = link_normalizer(path)
            if normalized:
                out.append({"type": "markdown", "target": normalized})
    return out


def _extract_urls(body: str) -> list[dict[str, str]]:
    """正文裸 URL 抽取。"""
    out: list[dict[str, str]] = []
    for m in URL_RE.finditer(body):
        url = m.group(0).rstrip(".,;:)")
        out.append({"type": "url", "target": url})
    return out


def _dedupe_sources(sources: list[dict[str, str]]) -> list[dict[str, str]]:
    """按 (type, target) 去重,保留首次出现顺序。"""
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, str]] = []
    for s in sources:
        key = (s.get("type", ""), s.get("target", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口:OKF v0.2 reader。"""
    project = Path(args.project_dir).resolve()
    if not project.exists():
        raise FileNotFoundError(f"--project-dir 不存在:{project}")

    file_path = Path(args.file)
    if not file_path.is_absolute():
        file_path = project / file_path
    if not file_path.exists():
        raise FileNotFoundError(f"--file 不存在:{file_path}")

    text = file_path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)

    sources: list[dict[str, str]] = []

    # 1. 优先 frontmatter links
    fm_links = _extract_from_links(fm)
    if fm_links:
        sources.extend(fm_links)
    else:
        # 2. fallback:wikilink + markdown + url
        sources.extend(_extract_wikilinks(body))
        sources.extend(_extract_markdown_links(body))
        sources.extend(_extract_urls(body))

    sources = _dedupe_sources(sources)

    return {
        "sources": sources,
        "count": len(sources),
        "frontmatter_keys": sorted(fm.keys()),
        "file": str(file_path.relative_to(project)).replace("\\", "/"),
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="okf-reader.py",
        description="OKF v0.2 reader — frontmatter links 优先 + 正文 wikilink/markdown/URL fallback。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    parser.add_argument(
        "--file",
        required=True,
        help="知识页相对路径(相对 --project-dir)。",
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

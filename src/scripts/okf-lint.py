"""okf-lint.py — OKF v0.2 合规 + frontmatter `links:` 镜像同步。

CLI:
    python3 okf-lint.py --project-dir <dir> --file <rel-path> [--apply]

行为(DESIGN.md §1.1 + §3.6.2 + lint SKILL.md §1.7):
    - 单文件粒度(与 lint.py 整套粒度不同)
    - 扫正文 [[wikilink]] / [text](path) / URL → Set
    - 与 frontmatter `links:` Set 比对(diff:drift / scanned / current / added /
      removed / reordered)
    - 复用 _common.link_normalizer 归一 alias / anchor / path prefix
    - --apply 走 Q7 4 步流程(stat → write → utime(atime + mtime 双还原))
    - 复用 _common.atomic_write_preserving_mtime
    - 默认 dry-run;--apply 写盘
    - 不动 frontmatter `updated` 字段(Q7 死循环防护)

输出:
    stdout JSON: {
      "drift": bool,
      "scanned": [..],   # 正文扫到的归一后 target 列表
      "current": [..],   # frontmatter links 当前值
      "added": [..],     # 扫到但 links 没有
      "removed": [..],   # links 有但正文没扫到
      "reordered": bool, # 顺序不同(可选报)
      "applied": bool,   # --apply 是否真写盘
      "file": "..."
    }

约束(NFR-1 ~ NFR-7):
    - 不读 stdin(NFR-1)
    - 不开 daemon(NFR-1)
    - 路径全部相对 --project-dir(NFR-4)
    - 错误消息中文为主(NFR-3)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from _common import atomic_write_preserving_mtime, emit_json, link_normalizer


# 行内 [[wikilink]] 提取(取最长的 [...] 形式,避免与 markdown link 混淆)
WIKILINK_RE = re.compile(r"\[\[([^\]\n]+)\]\]")

# 行内 markdown link [text](path) 提取(URL 也走这个,但会被归一为自身)
MD_LINK_RE = re.compile(r"\[([^\]\n]+)\]\(([^)\n]+)\)")

# URL(只取 http/https;这些不进 frontmatter links,但用来 diff 报告)
URL_RE = re.compile(r"https?://[^\s\)\]\"']+")


def _extract_links(body: str) -> list[str]:
    """从 markdown 正文提取所有 link 候选(去重前)。

    抓取顺序:wikilink → markdown link(相对路径)→ URL(信息性,稍后过滤)。

    Args:
        body: 不含 frontmatter 的 md 正文。

    Returns:
        归一化前的原始字符串列表(后续过 link_normalizer)。
    """
    candidates: list[str] = []

    for m in WIKILINK_RE.finditer(body):
        candidates.append("[[" + m.group(1) + "]]")
    for m in MD_LINK_RE.finditer(body):
        candidates.append(m.group(2))

    return candidates


def _normalize_set(candidates: list[str]) -> list[str]:
    """对原始 candidates 走 link_normalizer,过滤空串、URL 自身,转 list(set) 排序。

    顺序无关:diff 用 set 比对;但输出给 frontmatter 的 list 用稳定排序便于人读。

    Args:
        candidates: 原始 link 字符串列表。

    Returns:
        去重 + 归一 + 排序后的 slug 列表。
    """
    normalized: set[str] = set()
    for c in candidates:
        slug = link_normalizer(c)
        if not slug:
            continue
        # 过滤纯 URL(没 .md 也没 wikilink 包裹)
        if slug.startswith("http://") or slug.startswith("https://"):
            continue
        normalized.add(slug)

    return sorted(normalized)


def _read_file(file_path: Path) -> str:
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在:{file_path}")
    try:
        return file_path.read_text(encoding="utf-8")
    except OSError as e:
        raise OSError(f"读取文件失败:{e}")


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """极简 frontmatter 解析。

    Returns:
        (frontmatter_dict, body_text)
    Raises:
        ValueError: 缺 frontmatter / 解析失败。
    """
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
    body_text = "\n".join(lines[end_idx + 1 :])

    # 轻量 YAML 解析(若 pyyaml 不可用 → 降级为只扫 body)
    try:
        import yaml  # type: ignore[import-untyped]

        fm = yaml.safe_load(fm_block)
    except ImportError:
        # 缺 pyyaml:不阻断 diff 报告,links 视为空 list
        fm = {}
    except Exception:
        fm = {}

    if not isinstance(fm, dict):
        fm = {}
    return fm, body_text


def _current_links(fm: dict[str, Any]) -> list[str]:
    """从 frontmatter 取 links: 字段(归一)。

    容忍 3 种形态:
        - links: [a, b, c](YAML flow list)
        - links:\n  - a\n  - b(block list)
        - links 缺 → []

    Args:
        fm: frontmatter dict。

    Returns:
        归一 + 排序后的 list[str](set 比对用)。
    """
    links = fm.get("links")
    if links is None:
        return []
    if isinstance(links, str):
        # 单值字符串(不应出现但容忍)
        return [link_normalizer(links)] if link_normalizer(links) else []
    if not isinstance(links, list):
        return []

    normalized: set[str] = set()
    for item in links:
        if not isinstance(item, str):
            continue
        slug = link_normalizer(item)
        if slug:
            normalized.add(slug)
    return sorted(normalized)


def _diff(scanned: list[str], current: list[str]) -> dict[str, Any]:
    """scanned ↔ current Set 比对。

    Returns:
        {
          "drift": bool,        # Set 不相等或顺序不同
          "added": [...],       # scanned - current
          "removed": [...],     # current - scanned
          "reordered": bool,    # 集合相等但顺序不同
        }
    """
    s_set = set(scanned)
    c_set = set(current)
    added = sorted(s_set - c_set)
    removed = sorted(c_set - s_set)
    set_equal = added == [] and removed == []
    reordered = set_equal and scanned != current
    return {
        "drift": not set_equal or reordered,
        "added": added,
        "removed": removed,
        "reordered": reordered,
    }


def _build_links_yaml_block(links_list: list[str]) -> str:
    """构造 `links:` YAML 块(block 风格,空 list 走 [] 兜底)。

    顺序按 scanned 排序后输出(保证 deterministic)。
    """
    if not links_list:
        return "links: []"
    lines = ["links:"]
    for s in links_list:
        # 单引号包裹(与 generate-source-page.py / generate-analysis-page.py 风格一致)
        safe = s.replace("'", "''")
        lines.append(f"  - '{safe}'")
    return "\n".join(lines)


def _replace_links_block(text: str, new_block: str) -> str:
    """原地替换 frontmatter 中 `links:` 字段(支持 flow / block / 缺失)。

    策略:
        - 若已有 `links:` 行(以 `links:` 起头,后接 flow 或 block)→ 替换到下一个
          顶层 key / --- 收尾为止
        - 若缺 `links:` → 在 frontmatter 末尾 --- 前插入新块
    """
    lines = text.split("\n")

    # 找 frontmatter 边界
    if not lines or not lines[0].startswith("---"):
        raise ValueError("文件无 frontmatter(必须以 --- 起头)")
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].startswith("---"):
            end_idx = i
            break
    if end_idx is None:
        raise ValueError("frontmatter 缺少结束标记 ---")

    # 在 frontmatter 内找 links 行
    links_start = None
    for i in range(1, end_idx):
        if lines[i].startswith("links:") or lines[i].startswith("links "):
            links_start = i
            break

    if links_start is None:
        # 缺 → 在 end_idx 之前插入
        new_lines = lines[:end_idx] + [new_block] + lines[end_idx:]
        return "\n".join(new_lines)

    # 找 links 块结束(下一个顶层 key 或 ---)
    block_end = links_start + 1
    # flow 形态 links: [a, b] → 单行
    if not lines[links_start].rstrip().endswith("]"):
        # block 形态:找下一个不以 "  -" 或 空格 起头的行
        while block_end < end_idx:
            ln = lines[block_end]
            if ln.startswith("  ") or ln.strip() == "":
                block_end += 1
                continue
            break

    new_lines = lines[:links_start] + [new_block] + lines[block_end:]
    return "\n".join(new_lines)


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口:扫正文 → 与 frontmatter links 比对 → (可选)写盘。"""
    project = Path(args.project_dir).resolve()
    file_path = Path(args.file)
    if not file_path.is_absolute():
        file_path = project / file_path

    text = _read_file(file_path)
    fm, body = _parse_frontmatter(text)

    raw_candidates = _extract_links(body)
    scanned = _normalize_set(raw_candidates)
    current = _current_links(fm)

    diff = _diff(scanned, current)

    applied = False
    if args.apply and diff["drift"]:
        # 写盘:不动 updated;走 atomic_write_preserving_mtime(Q7 4 步流程)
        new_block = _build_links_yaml_block(scanned)
        new_text = _replace_links_block(text, new_block)
        if new_text != text:
            try:
                atomic_write_preserving_mtime(file_path, new_text)
                applied = True
            except OSError as e:
                raise OSError(f"写盘失败:{e}")

    rel_path = str(file_path.relative_to(project)).replace("\\", "/")
    return {
        "drift": diff["drift"],
        "scanned": scanned,
        "current": current,
        "added": diff["added"],
        "removed": diff["removed"],
        "reordered": diff["reordered"],
        "applied": applied,
        "file": rel_path,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="okf-lint.py",
        description="OKF v0.2 合规 + frontmatter links: 镜像同步(Set 比对 + Q7 4 步流程)。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    parser.add_argument(
        "--file",
        required=True,
        help="待扫描 .md 文件相对路径。",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="写盘同步 links: 字段;默认 dry-run。",
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

"""query/collect-neighbors.py — 跳 3:从 candidates 收集邻居(深度 1,硬上限 8)。

CLI:
    python3 query/collect-neighbors.py --project-dir . \\
        --candidates <json-file> [--max-depth 1] [--max-n 8]

输入(--candidates JSON 格式):
    {
      "candidates": [
        {"path": "concepts/standard/autosar.md", "score": 0.85, ...},
        ...
      ]
    }

行为(DESIGN.md §1.1 + §4 + query SKILL.md §阶段 2 跳 3):
    - 对每个候选页,深度 1 收集邻居(不递归深度 > 1)
    - 优先级降权:
        1. frontmatter sources[] 数组(weight=1.0)
        2. ## 关联溯源 末尾 `> 引用:` 行(weight=0.9)
        3. syntheses/* 的 ## 子主题 + ## 引用 段(weight=0.8)
        4. 正文其他 [[wikilink]](weight=0.5)
    - 硬上限 QUERY_NEIGHBOR_MAX = 8;超过按 weight 降序 + path 字典序切到 8
    - 去重(同一 path 多次出现 → 留最高 weight)
    - 输出 JSON:{"neighbors": [...], "total_neighbors": N}

输出:
    stdout JSON
    exit 0 / 1

约束(NFR-1 ~ NFR-7):
    - 只读 knowledge/(不扫 inbox/raw)
    - 不写盘
    - 不读 stdin
    - 错误消息中文为主
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# scripts/ 顶层 _common.py 注入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _common import emit_json, link_normalizer  # noqa: E402


# 硬上限(对外暴露给 SKILL.md)
QUERY_NEIGHBOR_MAX = 8

# 优先级权重(降权不忽略)
WEIGHT_SOURCES_FIELD = 1.0       # frontmatter sources[]
WEIGHT_REFERENCE_LINE = 0.9      # > 引用: 行
WEIGHT_SYNTHESES_SUBTOPIC = 0.8  # syntheses/* 的 ## 子主题 / ## 引用
WEIGHT_WIKILINK = 0.5            # 正文其他 [[wikilink]]

# wikilink 抽取正则
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")

# > 引用: 行的路径抽取(逗号分隔、形如 sources/foo.md)
REFERENCE_LINE_PATH_RE = re.compile(r"[a-zA-Z0-9_\-./\\]+\.md")


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """极简 YAML frontmatter 解析(不依赖 pyyaml)。

    支持 keys:sources(数组,含 dict 元素如 `- resource: ...`)、简单 list、
    其余 key 字符串透传。
    Returns:
        (fm_dict, body_text)
    """
    if not text.startswith("---"):
        return ({}, text)
    rest = text[3:]
    end = rest.find("\n---")
    if end == -1:
        return ({}, text)
    fm_block = rest[:end]
    body = rest[end + 4 :]
    fm: dict[str, Any] = {}
    cur_key: str | None = None
    cur_list_indent_2: bool = False  # 缩进 2 的子属性行(对 dict 元素 / 子 list)

    for ln_raw in fm_block.splitlines():
        ln = ln_raw.rstrip()
        if not ln.strip():
            cur_key = None
            continue

        # list 项:`- xxx` 或 `- key: val`(子 dict)
        if ln.startswith("  - ") or ln.startswith("- "):
            prefix = ln[:4] if ln.startswith("  - ") else ln[:2]
            payload = ln[len(prefix):].strip()
            if not isinstance(fm.get(cur_key or ""), list):
                # 防御:跳过不在 list 上下文里的"-"行
                continue
            # `key: val`(list 内的 dict 元素)
            if ":" in payload and not payload.startswith("'") and not payload.startswith('"'):
                k, _, v = payload.partition(":")
                k = k.strip()
                v = v.strip()
                # 字符串去引号
                if v.startswith("'") and v.endswith("'"):
                    v = v[1:-1]
                elif v.startswith('"') and v.endswith('"'):
                    v = v[1:-1]
                # list 内插入 dict 元素(覆盖前一个若同 key)
                lst = fm[cur_key]
                if lst and isinstance(lst[-1], dict) and not lst[-1]:
                    lst[-1][k] = v
                else:
                    lst.append({k: v})
            else:
                # list 内 string 元素
                if payload.startswith("'") and payload.endswith("'"):
                    payload = payload[1:-1]
                elif payload.startswith('"') and payload.endswith('"'):
                    payload = payload[1:-1]
                fm[cur_key].append(payload)
            continue

        # 子项缩进行(4 空格,归属上一个 list 中 dict 的子键)
        if ln.startswith("    ") and cur_key:
            sub = ln[4:].strip()
            if ":" in sub and isinstance(fm.get(cur_key), list) and fm[cur_key]:
                lst = fm[cur_key]
                if isinstance(lst[-1], dict):
                    k, _, v = sub.partition(":")
                    k = k.strip()
                    v = v.strip()
                    if v.startswith("'") and v.endswith("'"):
                        v = v[1:-1]
                    elif v.startswith('"') and v.endswith('"'):
                        v = v[1:-1]
                    lst[-1][k] = v
            continue

        # 顶层 k: v 或 k:(列表开始)
        if ":" in ln:
            k, _, v = ln.partition(":")
            k = k.strip()
            v = v.strip()
            if not v:
                # 列表起始
                fm[k] = []
                cur_key = k
            else:
                cur_key = None
                if v.startswith("'") and v.endswith("'"):
                    v = v[1:-1]
                elif v.startswith('"') and v.endswith('"'):
                    v = v[1:-1]
                fm[k] = v
        else:
            cur_key = None
    return (fm, body)


def _read_page_fm_and_body(project: Path, rel_path: str) -> tuple[dict[str, Any], str] | None:
    """读 knowledge/<rel_path> 的 (frontmatter, body)。

    读不到(文件不存在)→ 返回 None。
    """
    full = project / "knowledge" / rel_path
    if not full.exists() or not full.is_file():
        return None
    text = full.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)
    return (fm, body)


def _extract_from_sources_field(fm: dict[str, Any]) -> list[str]:
    """从 frontmatter sources[] 抽路径(resource 字段优先,字符串也兼容)。"""
    out: list[str] = []
    raw = fm.get("sources")
    if not isinstance(raw, list):
        return out
    for item in raw:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            res = item.get("resource")
            if isinstance(res, str):
                out.append(res)
    return out


def _extract_from_reference_line(body: str) -> list[str]:
    """从 `## 关联溯源` 段末尾 `> 引用:` 行抽路径(逗号分隔)。"""
    # 找 ## 关联溯源 段(含 G11 / analysis 骨架)
    m = re.search(r"##\s*关联溯源\s*\n(.+?)(\n##\s|\Z)", body, re.DOTALL)
    if not m:
        return []
    section = m.group(1)
    # 找 `> 引用:` 行(或 `> 引用:` 前缀任意变体)
    ref_match = re.search(r"^>\s*引用[::]\s*(.+?)$", section, re.MULTILINE)
    if not ref_match:
        return []
    line = ref_match.group(1)
    paths: list[str] = []
    for tok in line.split(","):
        tok = tok.strip()
        if not tok:
            continue
        # 形如 sources/foo.md 或 wikilink [[foo]]
        tok = re.sub(r"^\[\[|\]\]$", "", tok).strip()
        if tok and tok.endswith(".md"):
            paths.append(tok)
    return paths


def _extract_from_syntheses_subtopic(body: str) -> list[str]:
    """从 syntheses/* 的 ## 子主题 / ## 引用 段抽 wikilink。"""
    paths: list[str] = []
    for sect_re in (r"##\s*子主题\s*\n(.+?)(\n##\s|\Z)",
                    r"##\s*引用\s*\n(.+?)(\n##\s|\Z)"):
        m = re.search(sect_re, body, re.DOTALL)
        if not m:
            continue
        section = m.group(1)
        for wm in WIKILINK_RE.finditer(section):
            tok = wm.group(1).split("|", 1)[0].split("#", 1)[0].strip()
            if tok and tok.endswith(".md"):
                paths.append(tok)
    return paths


def _extract_wikilinks_from_body(body: str, exclude_sections: bool = False) -> list[str]:
    """正文 [[wikilink]] 抽取(可选排除 ## 关联溯源 / ## 子主题 / ## 引用)。"""
    scan_body = body
    if exclude_sections:
        # 删除已抽取的 3 段(避免重复计权重)
        for sect_re in (
            r"##\s*关联溯源\s*\n.+?(?=\n##\s|\Z)",
            r"##\s*子主题\s*\n.+?(?=\n##\s|\Z)",
            r"##\s*引用\s*\n.+?(?=\n##\s|\Z)",
        ):
            scan_body = re.sub(sect_re, "", scan_body, flags=re.DOTALL)

    paths: list[str] = []
    for wm in WIKILINK_RE.finditer(scan_body):
        tok = wm.group(1).split("|", 1)[0].split("#", 1)[0].strip()
        if tok and tok.endswith(".md"):
            paths.append(tok)
    return paths


def _norm(path: str) -> str:
    """wikilink / 路径归一。

    若路径已经形如 knowledge 子路径(含 /)且以 .md 结尾 → 保留目录结构
    (frontmatter sources[].resource 是 "xxx/yyy/zzz.md" 形式,strip
    仅剥 .md 后缀、#anchor、aliases;若不含 / → 调用 link_normalizer 完全归一成 slug)

    简化:
        - "[[page|Alias]]" / "[[page#anchor]]" → "page"
        - "sources/foo.md" 或 "concepts/standard/foo.md" → 保留目录 + 去 .md
        - "foo.md" → "foo"
    """
    if not path:
        return ""
    s = path.strip()
    # wikilink 形式 → 用 _common 标准归一(strip aliases / anchor / 仅保留 slug)
    if s.startswith("[[") and s.endswith("]]"):
        return link_normalizer(s)
    # 已是相对路径(可能含 .md)→ 留目录 + 去 .md 后缀
    if "/" in s:
        if s.endswith(".md"):
            s = s[:-3]
        return s
    # 单名 → 用 link_normalizer(只剥 .md)
    return link_normalizer(s)


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口:收集 candidates 的邻居。"""
    project = Path(args.project_dir).resolve()
    if not project.exists():
        raise FileNotFoundError(f"--project-dir 不存在:{project}")

    candidates_path = Path(args.candidates)
    if not candidates_path.is_absolute():
        candidates_path = project / candidates_path
    if not candidates_path.exists():
        raise FileNotFoundError(f"--candidates 不存在:{candidates_path}")

    max_depth = int(args.max_depth) if args.max_depth is not None else 1
    max_n = int(args.max_n) if args.max_n is not None else QUERY_NEIGHBOR_MAX

    if max_depth < 1:
        max_depth = 1
    if max_n < 1:
        max_n = 1

    # 读 candidates JSON
    try:
        cand_data = json.loads(candidates_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"--candidates JSON 解析失败:{e}")

    candidates = cand_data.get("candidates") if isinstance(cand_data, dict) else None
    if not isinstance(candidates, list):
        raise ValueError("--candidates 必须是 {candidates: list} 形态")

    # 收集所有邻居:每条(weight, path, source)
    collected: list[tuple[float, str, str]] = []
    seen: dict[str, float] = {}  # path -> 当前最高 weight

    def _add(path: str, weight: float, source: str) -> None:
        np = _norm(path)
        # 排除 candidates 自身(避免自指)
        cand_paths = {_norm(c.get("path", "")) for c in candidates if isinstance(c, dict)}
        if np in cand_paths or not np:
            return
        # knowledge/ 路径限定(必须至少含一个 / 看成相对路径)
        if "/" not in np:
            return
        cur = seen.get(np, 0.0)
        if weight > cur:
            seen[np] = weight
        collected.append((weight, np, source))

    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        rel = cand.get("path", "")
        if not rel:
            continue
        result = _read_page_fm_and_body(project, rel)
        if result is None:
            continue
        fm, body = result

        # 1. sources[]
        for p in _extract_from_sources_field(fm):
            _add(p, WEIGHT_SOURCES_FIELD, "sources_field")
        # 2. > 引用: 行
        for p in _extract_from_reference_line(body):
            _add(p, WEIGHT_REFERENCE_LINE, "reference_line")
        # 3. syntheses 子主题 / 引用
        if "syntheses/" in rel:
            for p in _extract_from_syntheses_subtopic(body):
                _add(p, WEIGHT_SYNTHESES_SUBTOPIC, "syntheses_subtopic")
        # 4. 正文 [[wikilink]](排除已抽取的 3 段)
        for p in _extract_wikilinks_from_body(body, exclude_sections=True):
            _add(p, WEIGHT_WIKILINK, "wikilink")

        if max_depth < 1:
            break  # 兜底防止深度限制失效

    # 用 seen 字典做去重,补齐 path
    out: list[dict[str, Any]] = []
    seen_final: set[str] = set()
    # 先按 weight 降序排,遇同 weight 按 path 字典序
    collected.sort(key=lambda x: (-x[0], x[1]))
    for weight, path, source in collected:
        if path in seen_final:
            continue
        seen_final.add(path)
        out.append({
            "path": path,
            "weight": round(weight, 4),
            "source": source,
        })
        if len(out) >= max_n:
            break

    return {
        "neighbors": out,
        "total_neighbors": len(out),
        "max_n": max_n,
        "max_depth": max_depth,
        "candidates_count": len(candidates),
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="query/collect-neighbors.py",
        description="跳 3:从 candidates 收集邻居(深度 1,硬上限 8)。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    parser.add_argument(
        "--candidates",
        required=True,
        help="candidates JSON 文件路径(由 index-filter.py 产出)。",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=1,
        help="最大深度(默认 1,不递归)。",
    )
    parser.add_argument(
        "--max-n",
        type=int,
        default=QUERY_NEIGHBOR_MAX,
        help=f"最大邻居数(默认 {QUERY_NEIGHBOR_MAX})。",
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

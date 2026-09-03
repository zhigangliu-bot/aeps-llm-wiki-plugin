"""query/index-filter.py — 跳 1:读 knowledge/index.md 过滤 top-K。

CLI:
    python3 query/index-filter.py --project-dir . --query "AUTOSAR 架构" [--k 10]

行为(DESIGN.md §1.1 + §4 + query SKILL.md §阶段 2 跳 1):
    - 读 <project>/knowledge/index.md 全部条目
    - 行格式:"- [page](path) — type · 一句话"
      (兼容 init seed 空文件 / 用户累积加的格式)
    - 关键词匹配:query 字符串命中条目 → 入候选;
      同时扫整行 type / path / 一句话里的所有 token 做弱命中
    - frontmatter tags 命中(query 含 tag 关键字,如 "autosar") → score 加权
    - 取 top-K(K 默认 10,可用 --k 覆盖)
    - 输出 JSON:{"candidates": [...], "total_candidates": N, "k": K}

输出:
    stdout JSON
    exit 0 / 1

约束(NFR-1 ~ NFR-7):
    - 不读 inbox / raw(只读 knowledge/index.md,NFR-4)
    - 不写盘(纯计算)
    - 不读 stdin(NFR-1)
    - 错误消息中文为主(NFR-3)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

# scripts/ 顶层 _common.py 注入(sys.path)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _common import emit_json  # noqa: E402


# 阈值常量(对外暴露,供 SKILL.md / 测试引用)
QUERY_CANDIDATE_K = 10

# index.md 条目行正则:`- [<page>](<path>) — <type> · <一段话>`
INDEX_LINE_RE = re.compile(
    r"^-\s+\[(?P<page>[^\]]+)\]\((?P<path>[^)]+)\)\s*[—\-]\s*"
    r"(?P<type>[^·]+)·\s*(?P<summary>.+)$"
)

# 简单 tag 命中提取(从 query 里抽可能是 tag 的 token)
TAG_TOKEN_RE = re.compile(r"^([a-z][a-z0-9_-]+)/([a-z0-9_-]+)$")


def _parse_index_entries(index_path: Path) -> list[dict[str, str]]:
    """解析 index.md 一行一条的条目。

    行格式:"- [page](path) — type · 一句话"
    不命中格式的行(frontmatter / 注释 / 空行)→ 跳过。
    """
    if not index_path.exists():
        return []

    text = index_path.read_text(encoding="utf-8")
    entries: list[dict[str, str]] = []
    for line in text.splitlines():
        line = line.rstrip()
        m = INDEX_LINE_RE.match(line)
        if not m:
            continue
        entries.append({
            "page": m.group("page").strip(),
            "path": m.group("path").strip(),
            "type": m.group("type").strip(),
            "summary": m.group("summary").strip(),
        })
    return entries


def _tokenize(s: str) -> list[str]:
    """极简分词:转小写 + 中文按字拆 + 英文按非字母数字拆。"""
    s = s.lower()
    # 中文字符逐一拆开(粗暴实现,query 中文为主)
    tokens: list[str] = []
    buf: list[str] = []
    for ch in s:
        if "一" <= ch <= "鿿":
            if buf:
                tokens.append("".join(buf))
                buf = []
            tokens.append(ch)
        elif ch.isalnum():
            buf.append(ch)
        else:
            if buf:
                tokens.append("".join(buf))
                buf = []
    if buf:
        tokens.append("".join(buf))
    return tokens


def _score_entry(
    entry: dict[str, str],
    query_tokens: list[str],
    raw_query: str,
    tags_hint: list[str],
) -> tuple[float, list[str]]:
    """给一条 index 条目打分。

    评分规则:
        - query 各 token 在 (page + summary + path + type) 命中 → +1/tok
        - query 任一 token 命中 frontmatter tags 关键词(由 SKILL.md 推断或
          从 query 末尾抽)→ +0.5,且记录进 matched_tags

    Returns:
        (score, matched_tags)
    """
    if not query_tokens:
        return (0.0, [])

    haystack = " ".join([
        entry.get("page", ""),
        entry.get("summary", ""),
        entry.get("path", ""),
        entry.get("type", ""),
    ]).lower()

    matched = sum(1 for t in query_tokens if t and t in haystack)
    if matched == 0:
        return (0.0, [])

    score = float(matched)
    matched_tags: list[str] = []
    # tags 加权
    for tag in tags_hint:
        # tag 形如 "domain/autosar" → 取尾部
        if "/" in tag:
            tail = tag.split("/")[-1].lower()
        else:
            tail = tag.lower()
        if not tail:
            continue
        if tail in raw_query.lower() or tail in haystack:
            score += 0.5
            matched_tags.append(tag)

    # 命中比例做归一(0~1)
    return (min(score / max(len(query_tokens), 1), 1.0), matched_tags)


def _infer_tags_from_query(query: str) -> list[str]:
    """从 query 中抽可能的 tag(粗启发:`domain/xxx` / `maturity/xxx` 等)。

    Returns:
        推断出的 tag 列表(若无 → 空 list)
    """
    tags: list[str] = []
    for tok in re.split(r"\s+", query):
        m = TAG_TOKEN_RE.match(tok.strip())
        if m:
            tags.append(tok.strip().lower())
    # 兜底:把整个 query 拆词,fallback 成"软"命中权重已经在 _score 里做了
    return tags


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口:index.md top-K 过滤。"""
    project = Path(args.project_dir).resolve()
    if not project.exists():
        raise FileNotFoundError(f"--project-dir 不存在:{project}")

    raw_query = (args.query or "").strip()
    if not raw_query:
        raise ValueError("--query 不能为空")

    k = int(args.k) if args.k is not None else QUERY_CANDIDATE_K
    if k < 1:
        raise ValueError(f"--k 必须 >= 1,实际={k}")

    # 只读 knowledge/index.md(不扫 inbox/raw)
    index_path = project / "knowledge" / "index.md"
    entries = _parse_index_entries(index_path)
    if not entries:
        return {
            "candidates": [],
            "total_candidates": 0,
            "k": k,
            "query": raw_query,
            "index_entries_parsed": 0,
        }

    query_tokens = _tokenize(raw_query)
    tags_hint = _infer_tags_from_query(raw_query)

    # 打分
    scored: list[dict[str, Any]] = []
    for entry in entries:
        score, matched_tags = _score_entry(
            entry, query_tokens, raw_query, tags_hint
        )
        if score <= 0:
            continue
        scored.append({
            "path": entry["path"],
            "page": entry["page"],
            "type": entry["type"],
            "summary": entry["summary"],
            "score": round(score, 4),
            "matched_tags": matched_tags,
        })

    # 按 score 降序,稳定排序(score 一致时按 path 字典序)
    scored.sort(key=lambda c: (-c["score"], c["path"]))

    return {
        "candidates": scored[:k],
        "total_candidates": len(scored),
        "k": k,
        "query": raw_query,
        "index_entries_parsed": len(entries),
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="query/index-filter.py",
        description="跳 1:读 knowledge/index.md 过滤 top-K 候选。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    parser.add_argument(
        "--query",
        required=True,
        help="查询字符串(中文/英文均可)。",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=QUERY_CANDIDATE_K,
        help=f"取 top-K 条目(默认 {QUERY_CANDIDATE_K})。",
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

    emit_json(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())

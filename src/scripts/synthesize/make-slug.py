"""make-slug.py — 从 synthesize topic 字符串派生文件 slug。

CLI:
    python3 make-slug.py --topic "OKF 生态全景"

行为(DESIGN.md §1.1 synthesize 组 + synthesize SKILL.md §阶段 2):
    - slug 派生规则(按顺序):
        1. 全角字符 → 半角(FF01-FF5E → 21-7E;全角空格 U+3000 → 半角空格)
        2. 字符全小写(只对 ASCII a-z 起作用;中文不变)
        3. 空白(空格 / Tab)→ 单个连字符 `-`
        4. 去除标点符号(ASCII 标点 + 中文标点)
           - 标点定义:!"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~ + 全角 FF00-FFEF 中非字母数字部分
        5. 连续 `-` 折叠为单个
        6. 收尾 `-` 去掉
        7. **中文 / CJK 字符保留**(CJK Unified Ideographs U+4E00-U+9FFF)

    - 派生结果示例:
        "OKF 生态全景"        → "okf-生态全景"
        "AUTOSAR 实战方法论"   → "autosar-实战方法论"
        "ISO 26262 与 SOTIF 的关系" → "iso-26262-与-sotif-的关系"
        "Hello World!"         → "hello-world"
        "  Multiple   Spaces  " → "multiple-spaces"
        "ＡＢＣ"                → "abc"

输出:
    stdout JSON:{"slug": "okf-生态全景"}
    exit 0 / 1

约束(NFR-1 ~ NFR-4):
    - 不读 stdin(NFR-1)
    - 不开 daemon(NFR-1)
    - 纯字符串处理;不调任何 helper;不访问文件系统
    - 错误消息中文为主(NFR-3)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from typing import Any


# 半角 ASCII 标点集(从 string.punctuation 风格提炼)
_ASCII_PUNCT = set("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")

# CJK 标点匹配正则(全角 + 通用 CJK 符号)
_CJK_PUNCT_RE = re.compile(
    r"[　-〿＀-￯ -⁯⸀-⹿]"
)


def _fullwidth_to_halfwidth(s: str) -> str:
    """把全角 ASCII(Fullwidth Forms FF01-FF5E)归一为半角。

    全角空格 U+3000 也归一为半角空格。
    非 ASCII 段(CJK 等)直接保留。
    """
    result: list[str] = []
    for ch in s:
        code = ord(ch)
        # 全角 ASCII 范围:FF01-FF5E → 21-7E
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        elif code == 0x3000:
            # 全角空格 → 半角空格
            result.append(" ")
        else:
            result.append(ch)
    return "".join(result)


def _normalize_cjk_punct(s: str) -> str:
    """剥离 CJK 标点符号(CJK Symbols and Punctuation U+3000-U+303F)。"""
    return _CJK_PUNCT_RE.sub(" ", s)


def _strip_ascii_punct(s: str) -> str:
    """去除 ASCII 标点,替换为空格以便后续折叠为连字符。"""
    return "".join(" " if ch in _ASCII_PUNCT else ch for ch in s)


def _collapse_dashes(s: str) -> str:
    """连续 `-` 折叠为单个,收尾 `-` 去掉。"""
    s = re.sub(r"-+", "-", s)
    s = s.strip("-")
    return s


def make_slug(topic: str) -> str:
    """派生 synthesis 页 slug。

    规则顺序:
        1. 全角 → 半角
        2. ASCII 字符全小写
        3. ASCII 标点 → 空格
        4. CJK 标点 → 空格
        5. 空白(空格 / Tab)→ 单个连字符 `-`
        6. 连续 `-` 折叠 + 收尾去 `-`
        7. 中文 / CJK 字符保留

    Args:
        topic: synthesize 的原始 topic(可含中英文 + 数字 + 空格 + 标点)。

    Returns:
        派生后的文件名 slug(全小写连字符 + 中文保留)。
        空字符串输入 → 空字符串输出。
    """
    if not topic:
        return ""

    s = topic.strip()
    if not s:
        return ""

    # 1. 全角 → 半角
    s = _fullwidth_to_halfwidth(s)

    # 2. ASCII 字符全小写(只对 a-z 起作用;中文 / 其他 unicode 字符不变)
    s = s.lower()

    # 3. ASCII 标点 → 空格(让 `-` 自己留作连字符 — 后续会折叠)
    #    单独保留 `-` 不在这里替换;让"-"走空白折叠路径
    s = "".join(ch if ch == "-" else (" " if ch in _ASCII_PUNCT else ch) for ch in s)

    # 4. CJK 标点 → 空格
    s = _normalize_cjk_punct(s)

    # 5. 空白(空格 / Tab / 换行)→ 单个连字符 `-`
    s = re.sub(r"\s+", "-", s)

    # 6. 连续 `-` 折叠 + 收尾去 `-`
    s = _collapse_dashes(s)

    # 7. NFKC 标准化(覆盖剩余兼容字符:全角字母数字、compatibility forms)
    s = unicodedata.normalize("NFKC", s)
    s = _collapse_dashes(s)

    return s


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口。"""
    if args.topic is None:
        raise ValueError("--topic 必填")
    slug = make_slug(args.topic)
    return {"slug": slug, "topic": args.topic}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="make-slug.py",
        description="从 synthesize topic 派生文件 slug(全角→半角 / 去标点 / 中文保留)。",
    )
    parser.add_argument(
        "--topic",
        required=True,
        help="synthesize 的原始 topic 字符串。",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = run(args)
    except ValueError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 1

    result["ok"] = True
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
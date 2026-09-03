"""query/gating.py — gating 决策:query 回答后是否询问"落档 analysis 页"。

CLI:
    python3 query/gating.py --project-dir . \\
        --intent overview --answer-length 250 \\
        --sources-json <file> --body <file>

输入:
    --intent:overview | exact | comparison | ambiguous | ...
    --answer-length:int(回答字符数)
    --sources-json:JSON 文件,形如 {"by_subdir": {"sources": N, "concepts": M, ...}}
                                或 {"count": K, "sources": [...]}
    --body:md 文件(LLM 写的回答正文)

行为(DESIGN.md §1.1 + §3.2 v0.5.2 PATCH + query SKILL.md §阶段 3):
    伪代码(优先级:跳过条件 > 触发条件):
        # 跳过条件(任一命中即跳过)
        if intent in {"exact", "ambiguous"}: return "skip"
        if "Wiki 未覆盖" in answer_body: return "skip"
        if answer_length < 200: return "skip"
        if len(sources_by_subdir) < 2: return "skip"

        # 触发条件(任一命中即问)
        if intent in {"overview", "comparison"}: return "prompt"
        if answer_length >= 200: return "prompt"
        if len(sources_by_subdir) >= 2: return "prompt"

        return "skip"  # 兜底

    ambiguous 优先于词命中(v0.5.2 PATCH)
    不依赖 LLM(纯计算),SKILL.md 喂参数

输出:
    stdout JSON:{"decision": "prompt"|"skip", "triggered_by": "...", "skip_reasons": [...]}
    exit 0 / 1

约束(NFR-1 ~ NFR-7):
    - 不读 inbox / raw
    - 不写盘
    - 不读 stdin
    - 错误消息中文为主
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# scripts/ 顶层 _common.py 注入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _common import emit_json  # noqa: E402


# 跳过 / 触发的 intent 集合
SKIP_INTENTS = {"exact", "ambiguous"}
PROMPT_INTENTS = {"overview", "comparison"}

# 长度阈值(字符数)
ANSWER_LENGTH_MIN_PROMPT = 200
ANSWER_LENGTH_MIN_SKIP = 200  # 跳过阈值等价(小于此跳过)

# sources_by_subdir 数阈值
SOURCES_SUBDIR_MIN_PROMPT = 2
SOURCES_SUBDIR_MIN_SKIP = 2


def _count_sources_by_subdir(sources_json: dict[str, Any]) -> int:
    """从 sources_json 派生 sources_by_subdir 数。

    兼容 2 种 JSON 形态:
        A) {"by_subdir": {"sources": N, "concepts": M, ...}} → len(by_subdir) 的非零 key 数
        B) {"count": K, "sources": [{"subdir": "...", ...}]} → len(sources)
        C) 顶层 list → 数 len
    """
    if "by_subdir" in sources_json and isinstance(sources_json["by_subdir"], dict):
        # 形态 A
        non_zero = sum(1 for v in sources_json["by_subdir"].values() if v)
        return non_zero

    if isinstance(sources_json.get("sources"), list):
        # 形态 B
        return len(sources_json["sources"])

    if isinstance(sources_json.get("by_subdir_count"), int):
        return sources_json["by_subdir_count"]

    # 兜底:0
    return 0


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口:gating 决策。"""
    project = Path(args.project_dir).resolve()
    if not project.exists():
        raise FileNotFoundError(f"--project-dir 不存在:{project}")

    intent = (args.intent or "").strip()
    answer_length = int(args.answer_length) if args.answer_length is not None else 0

    # sources-json
    sources_path = Path(args.sources_json)
    if not sources_path.is_absolute():
        sources_path = project / sources_path
    if not sources_path.exists():
        raise FileNotFoundError(f"--sources-json 不存在:{sources_path}")

    try:
        sources_data = json.loads(sources_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"--sources-json JSON 解析失败:{e}")
    if not isinstance(sources_data, dict):
        sources_data = {"sources": sources_data} if isinstance(sources_data, list) else {}

    # body
    body_path = Path(args.body)
    if not body_path.is_absolute():
        body_path = project / body_path
    if not body_path.exists():
        raise FileNotFoundError(f"--body 不存在:{body_path}")
    answer_body = body_path.read_text(encoding="utf-8")

    sources_by_subdir = _count_sources_by_subdir(sources_data)

    # 跳过条件(任一命中即 skip)
    skip_reasons: list[str] = []

    # 1. intent 跳过(v0.5.2 PATCH: ambiguous 优先)
    if intent in SKIP_INTENTS:
        skip_reasons.append(f"intent={intent} 在跳过集合 {sorted(SKIP_INTENTS)}")

    # 2. "Wiki 未覆盖" 提示
    if "Wiki 未覆盖" in answer_body:
        skip_reasons.append("正文含 'Wiki 未覆盖' 提示")

    # 3. 答案过短
    if answer_length < ANSWER_LENGTH_MIN_SKIP:
        skip_reasons.append(
            f"answer_length={answer_length} < {ANSWER_LENGTH_MIN_SKIP}"
        )

    # 4. sources_by_subdir 子目录 < 2
    if sources_by_subdir < SOURCES_SUBDIR_MIN_SKIP:
        skip_reasons.append(
            f"sources_by_subdir={sources_by_subdir} < {SOURCES_SUBDIR_MIN_SKIP}"
        )

    if skip_reasons:
        return {
            "decision": "skip",
            "triggered_by": "skip",
            "skip_reasons": skip_reasons,
            "inputs": {
                "intent": intent,
                "answer_length": answer_length,
                "sources_by_subdir": sources_by_subdir,
            },
        }

    # 触发条件(任一命中即 prompt)
    triggered_by: list[str] = []
    if intent in PROMPT_INTENTS:
        triggered_by.append(f"intent={intent}")
    if answer_length >= ANSWER_LENGTH_MIN_PROMPT:
        triggered_by.append(f"answer_length={answer_length}")
    if sources_by_subdir >= SOURCES_SUBDIR_MIN_PROMPT:
        triggered_by.append(f"sources_by_subdir={sources_by_subdir}")

    if triggered_by:
        return {
            "decision": "prompt",
            "triggered_by": " + ".join(triggered_by),
            "skip_reasons": [],
            "inputs": {
                "intent": intent,
                "answer_length": answer_length,
                "sources_by_subdir": sources_by_subdir,
            },
        }

    # 兜底:任何触发条件都没命中 → skip(防御性)
    return {
        "decision": "skip",
        "triggered_by": "no_trigger_match_fallback",
        "skip_reasons": ["触发条件均未命中,兜底 skip"],
        "inputs": {
            "intent": intent,
            "answer_length": answer_length,
            "sources_by_subdir": sources_by_subdir,
        },
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="query/gating.py",
        description="query 落档询问 gating 决策(intent/length/sources/Wiki 未覆盖)。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    parser.add_argument(
        "--intent",
        required=True,
        help="意图分类:overview/exact/comparison/ambiguous 等。",
    )
    parser.add_argument(
        "--answer-length",
        type=int,
        required=True,
        help="回答字符数(LLM 估算)。",
    )
    parser.add_argument(
        "--sources-json",
        required=True,
        help="sources 统计 JSON 文件路径(by_subdir 或 count)。",
    )
    parser.add_argument(
        "--body",
        required=True,
        help="md 文件(LLM 写的回答正文)。",
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

"""ingest/pre_classify.py — LLM 提议 raw 子目录的预校验(不读文件内容)。

CLI:
    # 用户已拍板(子目录名合法)→ 校验后通过
    python3 ingest/pre_classify.py --project-dir . \\
        --inbox-file inbox/foo.pdf --raw-subdir 02_芯片

    # 用户未拍板 → 返回 15 类字典 + 前缀提示
    python3 ingest/pre_classify.py --project-dir . \\
        --inbox-file inbox/foo.pdf

行为(DESIGN.md §1.1 + §4):
    - 不读 inbox 文件内容(只读路径 + 扩展名)
    - 不调 OCR / anydoc / paddleocr
    - 若传 --raw-subdir:校验子目录名合法(在 15 类字典内),跳过 LLM 提议环节
    - 若不传:返回 15 类字典 + 5 字符前缀提示(让 LLM 按前缀拍)

输出(JSON):
    拍板通过:
        {"raw_subdir": "<subdir>", "valid": true, "skipped_llm_proposal": true}
    未拍板:
        {
            "raw_subdirs": [...15 个...],
            "prefix_hint": "02_",     # 例:inbox/02_xxx.pdf → 前 5 字符
            "ext": "pdf",
            "inbox_file": "inbox/foo.pdf",
            "decision_required": true
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
import sys
from pathlib import Path
from typing import Any

# scripts/ 顶层 _common.py 注入(sys.path)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _common import emit_json  # noqa: E402


# 15 类 raw 子目录(权威源:src/templates/raw-readme.md,与 init-vault RAW_SUBDIRS 对齐)
RAW_SUBDIRS = (
    "01_EE架构",
    "02_芯片",
    "03_通信与网络",
    "04_操作系统与中间件",
    "05_软件工程",
    "06_功能安全",
    "07_信息安全",
    "08_AI与AI工程",
    "09_域控制器",
    "10_会议与活动",
    "11_开发工具",
    "12_法规_标准_政策",
    "13_流程体系",
    "14_测试与验证",
    "15_算法",
)


def _validate_subdir(subdir_name: str) -> None:
    """校验子目录名在 15 类字典内。"""
    if subdir_name not in RAW_SUBDIRS:
        raise ValueError(
            f"raw 子目录名不合法:{subdir_name};合法 15 类 = {list(RAW_SUBDIRS)}"
        )


def _derive_prefix_hint(inbox_file: str) -> str:
    """从 inbox 文件名提取 5 字符前缀提示(LLM 拍板参考)。

    例:
        inbox/02_芯片手册.pdf     → "02_芯"
        inbox/foo.pdf             → ""
        inbox/06_功能安全/abc.pdf → "06_功"
    """
    name = Path(inbox_file).name  # 取文件名
    # 取前 5 字符(中文 + ASCII 混合时,简单按字符数;够用即可)
    if len(name) < 5:
        return ""
    return name[:5]


def _extract_ext(inbox_file: str) -> str:
    """从 inbox 文件名取扩展名(小写,无点)。"""
    return Path(inbox_file).suffix.lstrip(".").lower()


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口。"""
    project = Path(args.project_dir).resolve()
    if not project.exists():
        raise FileNotFoundError(f"--project-dir 不存在:{project}")

    inbox_file = args.inbox_file
    ext = _extract_ext(inbox_file)

    if args.raw_subdir is not None:
        # 拍板已传 → 校验合法性
        subdir = args.raw_subdir
        _validate_subdir(subdir)
        return {
            "raw_subdir": subdir,
            "valid": True,
            "skipped_llm_proposal": True,
            "inbox_file": inbox_file,
            "ext": ext,
            "decision_required": False,
        }

    # 未拍板 → 返回字典 + 提示
    prefix = _derive_prefix_hint(inbox_file)
    return {
        "raw_subdirs": list(RAW_SUBDIRS),
        "prefix_hint": prefix,
        "ext": ext,
        "inbox_file": inbox_file,
        "decision_required": True,
        "hint_message": (
            f"请 LLM 按前缀 '{prefix}' + 15 类字典,选择最匹配的 raw 子目录;"
            f"调用方传入 --raw-subdir 重跑本脚本以确认。"
            if prefix else
            f"未检测到文件名可推断的前缀;请 LLM 自由选择 15 类之一,传入 --raw-subdir 重跑。"
        ),
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pre_classify.py",
        description="LLM 提议 raw 子目录的预校验(15 类字典校验 + 前缀提示)。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    parser.add_argument(
        "--inbox-file",
        required=True,
        help="inbox 文件相对路径,如 inbox/02_芯片手册.pdf。",
    )
    parser.add_argument(
        "--raw-subdir",
        default=None,
        help="(可选)用户已拍板的 raw 子目录名;若传则校验合法性。",
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

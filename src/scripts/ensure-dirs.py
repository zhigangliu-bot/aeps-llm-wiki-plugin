"""ensure-dirs.py — 在用户项目里 mkdir raw/<subdir>。

CLI:
    python3 ensure-dirs.py --project-dir . --path raw/<subdir>

行为(DESIGN.md §1.1):
    - 接受 raw/ 下子目录(15 类字典之一)
    - 接受二级路径如 raw/06_功能安全(自动建两层)
    - 不接受顶层目录创建(只 raw 子目录层)
    - 已存在不报错(幂等)
    - 校验子目录名在 15 类字典内

输出:
    stdout JSON: {"created": false, "path": "raw/<subdir>"}
                   或 {"created": true, "path": "raw/<subdir>"}
    exit 0 / 1

约束(NFR-1 ~ NFR-5):
    - 不读 stdin(NFR-1)
    - 不开 daemon(NFR-1)
    - 路径全部相对 --project-dir(NFR-4)
    - 错误消息中文为主(NFR-3)

设计决策:
    - 15 类字典在这里硬编码(避免循环依赖 init-vault);RAW_SUBDIRS 与 init-vault 同步对齐
    - 若插件版本升级新增类别,需要同时改两处(这是设计取舍,DESIGN.md v0.5.5 PATCH 已经做了一次对齐)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from _common import emit_json


# 15 类 raw 子目录(权威源:src/templates/raw-readme.md,与 init-vault RAW_SUBDIRS 对齐)
# 硬约束避免循环导入 init-vault
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

# 顶层目录白名单(只允许 raw/,其他顶层不允许走此脚本)
ALLOWED_TOP_LEVEL = "raw"


def _validate_subdir(subdir_name: str) -> None:
    """校验子目录名是否在 15 类字典内。"""
    if subdir_name not in RAW_SUBDIRS:
        raise ValueError(
            f"raw 子目录名不合法:{subdir_name};"
            f"合法 15 类 = {list(RAW_SUBDIRS)}"
        )


def _validate_path_format(input_path: str) -> tuple[str, str]:
    """校验 --path 是 raw/<subdir> 格式,返回 (top, subdir)。

    Raises:
        ValueError: 路径不合法(非 raw 起 / 多层 / 子目录名非法)
    """
    # 路径规范化:去掉首尾 / 与 ../
    parts = [p for p in Path(input_path).parts if p not in ("", ".", "..")]

    if not parts:
        raise ValueError(
            f"--path 非法:空路径或仅 . / .."
        )

    if parts[0] != ALLOWED_TOP_LEVEL:
        raise ValueError(
            f"--path 非法:只接受 raw/ 下子目录,拒绝 {parts[0]}/"
        )

    if len(parts) < 2:
        raise ValueError(
            f"--path 必须含子目录名,如 raw/<subdir>;当前 parts={parts}"
        )

    if len(parts) > 2:
        raise ValueError(
            f"--path 暂只支持二级 raw/<subdir>,拒绝 {parts}"
        )

    subdir = parts[1]
    _validate_subdir(subdir)

    return parts[0], subdir


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口:mkdir raw/<subdir> 二级路径,幂等。"""
    project = Path(args.project_dir).resolve()
    if not project.exists():
        raise FileNotFoundError(f"--project-dir 不存在:{project}")

    top, subdir = _validate_path_format(args.path)

    target = project / top / subdir
    existed = target.exists()

    if not existed:
        target.mkdir(parents=True, exist_ok=True)
        # 顺手补 .gitkeep(若没有),保持 raw/ 下文件状态一致
        keep = target / ".gitkeep"
        if not keep.exists():
            keep.touch()

    return {
        "created": not existed,
        "path": f"{top}/{subdir}",
        "subdir": subdir,
        "existed": existed,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ensure-dirs.py",
        description="mkdir raw/<subdir>(15 类字典之一);二级路径;已存在幂等。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    parser.add_argument(
        "--path",
        required=True,
        help="相对路径,如 raw/06_功能安全;只接受 raw/ 下二级子目录。",
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

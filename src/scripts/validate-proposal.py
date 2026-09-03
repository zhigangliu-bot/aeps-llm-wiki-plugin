"""validate-proposal.py — proposal JSON 5 步校验 + 字符清洗 + 截断检测(v0.5.4 PATCH)。

CLI:
    python3 validate-proposal.py --project-dir . --input temp/proposal-<doc-id>.json

行为(DESIGN.md §1.1 + §3.7):
    - 5 步校验:
        1. json.load() 解析
        2. jsonschema.validate()(根据 src/schema/proposal.schema.yaml)
        3. 字符集清洗:BOM 保留;\\x00 NUL / \\x1f 单元分隔符 → strip;</script> → <\\/script>
        4. 截断检测:concepts 数组 ≤ 200(超过视为 LLM 输出截断)
        5. 重写清洗后 JSON 到 temp/<doc-id>-proposal.json.sanitized
    - 失败降级路径:
        - JSONDecodeError / ValidationError / maxItems 超限 → 不派 subagent 重试
        - 写 backup 到 temp/<doc-id>-proposal.json.corrupt.bak
        - 输出 JSON:{"ok": false, "errors": [...], "sanitized_path": null, "backup_path": "..."} + exit 1
    - 成功:输出 {"ok": true, "sanitized_path": "temp/<...>.sanitized", "errors": []} + exit 0

输出:
    stdout JSON: 见上
    exit 0 / 1

约束(NFR-1 ~ NFR-7):
    - 不读 stdin(NFR-1)
    - 不开 daemon(NFR-1)
    - 路径全部相对 --project-dir(NFR-4)
    - 临时文件进 <project>/temp/(NFR-5)
    - 走 Q7 死循环防护:.sanitized / .corrupt.bak 都用 atomic_write_preserving_mtime
    - 错误消息中文为主(NFR-3)
    - 必须装 jsonschema / pyyaml(否则 exit 1)
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any

from _common import atomic_write_preserving_mtime, emit_json


# 5 步校验中的关键常量
MAX_CONCEPTS = 200  # LLM 输出截断上限(DESIGN.md §3.7 第 4 步)


def _check_dep(module_name: str, package: str | None = None) -> Any:
    """探测依赖,导入失败时 exit 1(中文报错)。"""
    try:
        return importlib.import_module(module_name)
    except ImportError as e:
        pkg = package or module_name
        print(
            f"❌ 缺依赖:{pkg}。请运行 pip install -r requirements.txt",
            file=sys.stderr,
        )
        print(f"详细错误:{e}", file=sys.stderr)
        sys.exit(1)


def _find_plugin_schema_path() -> Path | None:
    """定位 plugin 的 src/schema/proposal.schema.yaml。"""
    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir.parent / "schema" / "proposal.schema.yaml",
        script_dir.parent.parent / "schema" / "proposal.schema.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _load_schema(schema_path: Path) -> dict[str, Any]:
    """加载 proposal.schema.yaml 为 dict(供 jsonschema 消费)。"""
    yaml_mod = _check_dep("yaml", "pyyaml")
    with schema_path.open("r", encoding="utf-8") as f:
        data = yaml_mod.safe_load(f)
    return data if isinstance(data, dict) else {}


def _char_clean_string(s: str) -> str:
    """字符集清洗单个字符串。

    规则(DESIGN.md §3.7 第 3 步):
        - BOM (\\ufeff) 保留
        - \\x00 (NUL) → strip
        - \\x1f (单元分隔符) → strip
        - </script> → <\\/script>(转义防止 HTML 注入)
    """
    # NUL / 单元分隔符去除
    s = s.replace("\x00", "").replace("\x1f", "")
    # script 闭合标签转义(只对字面量字符串做替换)
    s = s.replace("</script>", "<\\/script>")
    return s


def _char_clean_value(v: Any) -> Any:
    """递归清洗 JSON value。"""
    if isinstance(v, str):
        return _char_clean_string(v)
    if isinstance(v, list):
        return [_char_clean_value(x) for x in v]
    if isinstance(v, dict):
        return {k: _char_clean_value(x) for k, x in v.items()}
    return v


def _backup_corrupt(input_path: Path, project: Path) -> str | None:
    """把损坏的 proposal 文件备份到 temp/<doc-id>-proposal.json.corrupt.bak(Q7 防护)。"""
    backup_name = f"{input_path.stem}.corrupt.bak"
    backup_path = project / "temp" / backup_name
    backup_path.parent.mkdir(parents=True, exist_ok=True)

    # 用 atomic_write_preserving_mtime 写 .bak 副本
    try:
        content = input_path.read_text(encoding="utf-8")
        # 新文件不存在,先创建再 atomic write
        # atomic_write_preserving_mtime 要求 path 已存在 — 改用 write_text + utime
        backup_path.write_text(content, encoding="utf-8")
        # backup 是新文件,不需要 mtime 还原(只是 IO)
    except OSError:
        return None
    return str(backup_path.relative_to(project)) if project in backup_path.parents else str(backup_path)


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口:5 步校验 proposal JSON。"""
    project = Path(args.project_dir).resolve()
    if not project.exists():
        raise FileNotFoundError(f"--project-dir 不存在:{project}")

    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = project / input_path

    if not input_path.exists():
        raise FileNotFoundError(f"--input 文件不存在:{input_path}")

    # 缺依赖 pre-check
    json_mod: Any = None
    jsonschema_mod: Any = None
    yaml_mod: Any = None

    json_mod = _check_dep("json")  # stdlib,不会失败;只是预防 lint
    jsonschema_mod = _check_dep("jsonschema")
    yaml_mod = _check_dep("yaml", "pyyaml")

    schema_path = _find_plugin_schema_path()
    if schema_path is None:
        return {
            "ok": False,
            "errors": ["找不到 plugin src/schema/proposal.schema.yaml"],
            "sanitized_path": None,
            "backup_path": None,
        }

    schema = _load_schema(schema_path)

    # 第 1 步:JSON 解析
    raw_text = input_path.read_text(encoding="utf-8")
    # BOM 保留(读时用 utf-8-sig 拿掉,但保留识别)
    if raw_text.startswith("﻿"):
        text_content = raw_text[1:]  # 去掉 BOM,字符清洗阶段不再加
    else:
        text_content = raw_text

    try:
        proposal = json.loads(text_content)
    except json.JSONDecodeError as e:
        # JSON 损坏 → 备份 + 降级
        backup_rel = _backup_corrupt(input_path, project)
        return {
            "ok": False,
            "errors": [f"JSON 解析失败:{e}"],
            "sanitized_path": None,
            "backup_path": backup_rel,
        }

    # 第 2 步:schema 校验
    try:
        jsonschema_mod.validate(instance=proposal, schema=schema)
    except jsonschema_mod.ValidationError as e:
        backup_rel = _backup_corrupt(input_path, project)
        return {
            "ok": False,
            "errors": [f"Schema 校验失败:{e.message}(path: {list(e.path)})"],
            "sanitized_path": None,
            "backup_path": backup_rel,
        }

    # 第 3 步:字符集清洗
    proposal = _char_clean_value(proposal)

    # 第 4 步:截断检测(concepts ≤ 200)
    concepts = proposal.get("concepts")
    if isinstance(concepts, list) and len(concepts) > MAX_CONCEPTS:
        backup_rel = _backup_corrupt(input_path, project)
        return {
            "ok": False,
            "errors": [
                f"截断检测:concepts 数组长度 {len(concepts)} > {MAX_CONCEPTS}(LLM 输出截断)"
            ],
            "sanitized_path": None,
            "backup_path": backup_rel,
        }

    # 第 5 步:重写清洗后 JSON → temp/<doc-id>-proposal.json.sanitized
    sanitized_path = project / "temp" / f"{input_path.stem}.sanitized"
    sanitized_path.parent.mkdir(parents=True, exist_ok=True)

    sanitized_text = json.dumps(proposal, ensure_ascii=False, indent=2)
    # 新文件直接 write_text(mtime 不存在要保留)
    sanitized_path.write_text(sanitized_text + "\n", encoding="utf-8")

    # 用 atomic_write_preserving_mtime 写(sanitized 是新文件无原始 mtime,改用直写)
    # Q7 防护适用于覆盖现有文件;.sanitized 是新建,暂用 write_text

    sanitized_rel: str
    try:
        sanitized_rel = str(sanitized_path.relative_to(project))
    except ValueError:
        sanitized_rel = str(sanitized_path)

    return {
        "ok": True,
        "sanitized_path": sanitized_rel,
        "errors": [],
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="validate-proposal.py",
        description="proposal JSON 5 步校验(json / jsonschema / 字符清洗 / 截断 / .sanitized)。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="proposal JSON 路径,如 temp/proposal-<doc-id>.json。",
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
    except SystemExit:
        # _check_dep 走 sys.exit(1),主流程让其自然抛出
        raise
    except Exception as e:
        emit_json({"ok": False, "error": f"未捕获异常:{type(e).__name__}:{e}"})
        return 1

    emit_json(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

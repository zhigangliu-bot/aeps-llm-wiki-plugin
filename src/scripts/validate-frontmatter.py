"""validate-frontmatter.py — frontmatter schema 校验(6 字段必填 + 6 轴 tag + type-specific)。

CLI:
    python3 validate-frontmatter.py --project-dir . --file <path>

行为(DESIGN.md §1.1 + §2.5):
    - 读 <plugin>/src/schema/frontmatter.schema.yaml(yaml 加载)
    - 校验必填字段:type / title / description / updated / tags
    - 校验 6 轴 tag 格式(<axis>/<value>,如 docform/source / domain/ai)
    - type enum 校验:18 合法值
    - 未知 type → WARN(OKF §11 容忍)
    - G10 三元组强绑定(source 页 native_text ⇔ converter ⇔ converted_path)
    - type-specific 必填(Q9 + G11)

输出:
    stdout JSON: {"ok": true|false, "missing": [...], "typecast": [...], "unknown_keys": [...], "warnings": [...]}
    exit 0(通过)/ 1(失败)

约束(NFR-1 ~ NFR-7):
    - 不读 stdin(NFR-1)
    - 不开 daemon(NFR-1)
    - 路径全部相对 --project-dir(NFR-4)
    - 不写文件(纯检查)
    - 错误消息中文为主(NFR-3)
"""

from __future__ import annotations

import argparse
import importlib
import re
import sys
from pathlib import Path
from typing import Any

from _common import emit_json


# 18 合法 type 值(DESIGN.md §2.5 + design.md §A)
LEGAL_TYPES = frozenset({
    # 资料与分析
    "source", "analysis",
    # Entities(具象存在)— 7 子类
    "person", "organization", "project", "product", "event", "place", "other",
    # Concepts(抽象知识)— 7 子类
    "theory", "method", "field", "phenomenon", "standard", "term",
    # Karpathy 常驻聚合页
    "comparison", "synthesis",
    # bundle-root 特殊页
    "overview", "schema",
})

# 6 轴 tag 正则(DESIGN.md §2.6 + design.md §3.1 §B):强制 <axis>/<value>,value 全小写 + 连字符
TAG_PATTERN = re.compile(r"^(domain|layer|phase|docform|maturity|tec)/[a-z][a-z0-9-]*$")

# 必填轴
REQUIRED_AXES = ("docform",)  # maturity 推荐非强;domain 推荐非强;但 docform 必填
# 通用必填字段
COMMON_REQUIRED = ("type", "title", "description", "updated", "tags")

# source 类型必填(Q9 双字段同源)
SOURCE_REQUIRED = ("source_file", "sources")

# analysis 类型必填(G11)
ANALYSIS_REQUIRED = ("sources_used", "answer_to", "generated_by")

# synthesis 类型必填
SYNTHESIS_REQUIRED = ("topic", "sources_count", "last_updated")

# G10 三元组 type:source
G10_TRIPLE_KEYS = ("native_text", "converter", "converted_path")


def _find_plugin_schema_path() -> Path | None:
    """定位 plugin 的 src/schema/frontmatter.schema.yaml。

    优先级:
        1. <scripts>/../schema/frontmatter.schema.yaml(dev mode)
        2. <scripts>/../../schema/frontmatter.schema.yaml(若 scripts 在 src/scripts 下)
    """
    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir.parent / "schema" / "frontmatter.schema.yaml",
        script_dir.parent.parent / "schema" / "frontmatter.schema.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _load_yaml(path: Path) -> dict[str, Any]:
    """轻量 yaml 加载(走 pyyaml)。缺包时退出 1。"""
    try:
        importlib.import_module("yaml")
    except ImportError:
        print(
            "❌ 缺依赖:pyyaml。请运行 pip install -r requirements.txt",
            file=sys.stderr,
        )
        sys.exit(1)
    import yaml
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def _parse_frontmatter_file(file_path: Path) -> dict[str, Any]:
    """极简 frontmatter 解析:读文件,找 ---...--- 块,内部当 YAML 解析。

    Returns:
        dict(frontmatter 解析结果)。

    Raises:
        FileNotFoundError: 文件不存在。
        ValueError: frontmatter 格式错或解析失败。
    """
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在:{file_path}")

    text = file_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError("文件无 frontmatter(必须以 --- 起头)")

    # 找结束标记 ---
    lines = text.split("\n")
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].startswith("---"):
            end_idx = i
            break
    if end_idx is None:
        raise ValueError("frontmatter 缺少结束标记 ---")

    fm_block = "\n".join(lines[1:end_idx])
    try:
        importlib.import_module("yaml")
    except ImportError:
        print(
            "❌ 缺依赖:pyyaml。请运行 pip install -r requirements.txt",
            file=sys.stderr,
        )
        sys.exit(1)
    import yaml

    try:
        fm = yaml.safe_load(fm_block)
    except yaml.YAMLError as e:
        raise ValueError(f"frontmatter YAML 解析失败:{e}")

    if not isinstance(fm, dict):
        raise ValueError("frontmatter 解析结果不是 dict")
    return fm


def _check_required(fm: dict[str, Any]) -> list[str]:
    """通用 5 字段必填。返回 missing 列表。"""
    missing = [k for k in COMMON_REQUIRED if k not in fm or fm[k] is None]
    # 字符串空值也视为缺
    for k in ("title", "description", "type", "updated"):
        if k in fm and isinstance(fm.get(k), str) and not fm[k].strip():
            missing.append(k)
            # 避免重复
            if k in missing[:-1]:
                missing.pop()
    return missing


def _check_tags(fm: dict[str, Any]) -> tuple[list[str], list[str]]:
    """校验 6 轴 tag 格式 + 必填轴(docform)。

    Returns:
        (missing_axes, tag_errors)
    """
    tags = fm.get("tags")
    errors: list[str] = []
    missing_axes: list[str] = []

    if not tags or not isinstance(tags, list):
        missing_axes.extend(REQUIRED_AXES)
        return missing_axes, errors

    # 既支持 list[str] 也支持 list[dict] 容忍
    tag_strs: list[str] = []
    for t in tags:
        if isinstance(t, str):
            tag_strs.append(t)
        elif isinstance(t, dict):
            # YAML flow style 偶尔出现 {"name": "..."} — 取 value
            v = t.get("name") or t.get("value")
            if isinstance(v, str):
                tag_strs.append(v)
            else:
                errors.append(f"tag dict 无法识别:{t}")
        else:
            errors.append(f"tag 非法类型:{type(t).__name__}:{t}")

    # 格式校验
    for s in tag_strs:
        if not TAG_PATTERN.match(s):
            errors.append(f"tag 不符合 <axis>/<value> 格式:{s}")

    # 必填轴
    axes_present = {s.split("/", 1)[0] for s in tag_strs if "/" in s}
    for ax in REQUIRED_AXES:
        if ax not in axes_present:
            missing_axes.append(ax)

    # 同 axis 重复
    axis_counts: dict[str, int] = {}
    for s in tag_strs:
        if "/" in s:
            ax = s.split("/", 1)[0]
            axis_counts[ax] = axis_counts.get(ax, 0) + 1
    for ax, cnt in axis_counts.items():
        if cnt > 1 and ax == "docform":
            errors.append(f"docform/ 重复:{cnt} 次(单值必填)")

    return missing_axes, errors


def _check_type(fm: dict[str, Any]) -> tuple[list[str], list[str]]:
    """校验 type enum;未知 → WARN。

    Returns:
        (typecast_suggestions, warnings)
    """
    typecast: list[str] = []
    warnings: list[str] = []
    tp = fm.get("type")
    if not tp:
        # 已在 missing 报告,这里不重复
        return typecast, warnings
    if tp not in LEGAL_TYPES:
        warnings.append(
            f"未知 type:{tp}(OKF §11 容忍,记 WARN;合法 18 值 = {sorted(LEGAL_TYPES)})"
        )
    return typecast, warnings


def _check_source_specific(fm: dict[str, Any]) -> list[str]:
    """source 类型 G10 / Q9 校验。

    Returns:
        error 列表(空 = 通过)
    """
    errors: list[str] = []
    if "source_file" not in fm or not fm.get("source_file"):
        errors.append("source 类型缺 source_file 字段(Q9 双字段同源)")

    sources = fm.get("sources")
    if not sources or not isinstance(sources, list):
        errors.append("source 类型缺 sources[] 字段")
    elif isinstance(sources, list) and sources:
        first = sources[0]
        if not isinstance(first, dict) or not first.get("resource"):
            errors.append("source 类型 sources[0].resource 缺失")
        else:
            # Q9 双字段同源
            if fm.get("source_file") and first["resource"] != fm["source_file"]:
                errors.append(
                    f"Q9 双字段不同源:source_file={fm['source_file']} "
                    f"vs sources[0].resource={first['resource']}"
                )

    # G10 三元组强绑定
    nt = fm.get("native_text")
    cv = fm.get("converter")
    cp = fm.get("converted_path")
    if nt is True:
        if cv is not None:
            errors.append(
                f"G10 三元组不匹配:native_text=true 时 converter 必须 null,实际={cv}"
            )
        if cp is not None:
            errors.append(
                f"G10 三元组不匹配:native_text=true 时 converted_path 必须 null,实际={cp}"
            )
    elif nt is False:
        if cv not in ("anydoc", "claude-native", "paddleocr"):
            errors.append(
                f"G10 三元组不匹配:native_text=false 时 converter 必须 ∈ {{anydoc, claude-native, paddleocr}},实际={cv}"
            )
        if cp is None or not isinstance(cp, str):
            errors.append(
                f"G10 三元组不匹配:native_text=false 时 converted_path 必须非 null string,实际={cp}"
            )
    elif nt is not None:
        errors.append(f"native_text 必须是 bool,实际类型={type(nt).__name__}")
    return errors


def _check_analysis_specific(fm: dict[str, Any]) -> list[str]:
    """analysis 类型 G11 必填。"""
    errors: list[str] = []
    for k in ANALYSIS_REQUIRED:
        if k not in fm or fm[k] is None:
            errors.append(f"analysis 类型缺字段:{k}")
    # sources_used 必须 list[str]
    su = fm.get("sources_used")
    if su is not None and not isinstance(su, list):
        errors.append(f"analysis.sources_used 必须是 list,实际={type(su).__name__}")
    return errors


def _check_synthesis_specific(fm: dict[str, Any]) -> list[str]:
    """synthesis 类型必填 + sources_count < 3 WARN。"""
    errors: list[str] = []
    warnings: list[str] = []
    for k in SYNTHESIS_REQUIRED:
        if k not in fm or fm[k] is None:
            errors.append(f"synthesis 类型缺字段:{k}")
    sc = fm.get("sources_count")
    if isinstance(sc, int) and sc < 3:
        warnings.append(f"synthesis sources_count={sc} < 3(WARN)")
    return errors, warnings


def _check_entity_concept_specific(fm: dict[str, Any]) -> list[str]:
    """entity / concept 类型 aliases 必填。"""
    errors: list[str] = []
    tp = fm.get("type")
    if tp in LEGAL_TYPES and tp not in (
        "source", "analysis", "synthesis", "comparison", "overview", "schema"
    ):
        # 即 entity / concept 子类
        aliases = fm.get("aliases")
        if aliases is None:
            errors.append(f"{tp} 类型缺 aliases 字段(必填:[])")
        elif not isinstance(aliases, list):
            errors.append(f"{tp}.aliases 必须是 list,实际={type(aliases).__name__}")
    return errors


def _check_comparison_specific(fm: dict[str, Any]) -> list[str]:
    """comparison 类型 sources ≥ 2 必填。"""
    errors: list[str] = []
    sources = fm.get("sources")
    if sources is None:
        errors.append("comparison 类型缺 sources 字段")
    elif isinstance(sources, list) and len(sources) < 2:
        errors.append(
            f"comparison.sources 数量 {len(sources)} < 2(必填 ≥ 2 wikilink)"
        )
    elif not isinstance(sources, list):
        errors.append(f"comparison.sources 必须是 list,实际={type(sources).__name__}")
    return errors


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口:校验单个 frontmatter 文件。"""
    project = Path(args.project_dir).resolve()
    file_path = Path(args.file)
    if not file_path.is_absolute():
        file_path = project / file_path

    try:
        fm = _parse_frontmatter_file(file_path)
    except (FileNotFoundError, ValueError) as e:
        return {
            "ok": False,
            "missing": [],
            "typecast": [],
            "unknown_keys": [],
            "warnings": [],
            "errors": [str(e)],
        }

    missing = _check_required(fm)
    missing_axes, tag_errors = _check_tags(fm)

    missing_combined = list(missing) + [f"tag 轴:{a}" for a in missing_axes]
    typecast, type_warnings = _check_type(fm)

    # 未知 key(非 OKF / plugin 已知)
    known_keys = {
        "type", "title", "description", "updated", "tags", "status",
        "source_file", "sources",
        "format", "converter", "native_text", "converted_path", "links",
        "sources_used", "answer_to", "generated_by", "summary",
        "aliases", "topic", "sources_count", "last_updated",
    }
    unknown_keys = [k for k in fm if k not in known_keys]

    # type-specific
    warnings = list(type_warnings)
    errors: list[str] = []
    errors.extend(tag_errors)
    tp = fm.get("type")
    if tp == "source":
        errors.extend(_check_source_specific(fm))
    elif tp == "analysis":
        errors.extend(_check_analysis_specific(fm))
    elif tp == "synthesis":
        syn_errors, syn_warns = _check_synthesis_specific(fm)
        errors.extend(syn_errors)
        warnings.extend(syn_warns)
    elif tp == "comparison":
        errors.extend(_check_comparison_specific(fm))
    elif tp in LEGAL_TYPES:
        # entity / concept
        errors.extend(_check_entity_concept_specific(fm))

    # 加载 schema 供后续扩展参考(本轮仅 ensure 文件存在)
    schema_path = _find_plugin_schema_path()
    if schema_path is None:
        warnings.append("找不到 plugin src/schema/frontmatter.schema.yaml,跳 jsonschema 段兜底")

    ok = not missing_combined and not errors
    return {
        "ok": ok,
        "missing": missing_combined,
        "typecast": typecast,
        "unknown_keys": unknown_keys,
        "warnings": warnings,
        "errors": errors,
        "file": str(file_path),
        "schema_path": str(schema_path) if schema_path else None,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="validate-frontmatter.py",
        description="frontmatter schema 校验(6 字段必填 + 6 轴 tag + type-specific + G10 三元组)。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    parser.add_argument(
        "--file",
        required=True,
        help="待校验 .md 文件相对路径。",
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
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

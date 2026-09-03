"""init-vault.py — 在用户项目里搭建 / 同步 aeps-llm-wiki 知识库目录结构。

CLI:
    python3 init-vault.py --project-dir . [--re-run] [--plugin-dir <path>]

行为:
    - 首次启用:建 6 顶层 + raw 15 + knowledge 18 + temp + .gitkeep + .gitignore
    - 拷贝 templates/(7 份) → <project>/templates/
    - 拷 scripts/(除 DESIGN/README/requirements 外) → <project>/scripts/
    - 写 _meta.json + .aeps-plugin-version
    - 写 4 个种子文件(index.md / overview.md / glossary.md / log.md,带 .gitkeep + 头部说明)
    - 幂等再入(--re-run):已存在的种子文件不覆盖;log.md 追加 Update 行

输出:
    stdout: JSON {"created": [...], "copied": [...], "synced_at": "...", "plugin_version": "0.5.5"}
    exit:   0 成功 / 1 失败

约束(NFR-1 ~ NFR-7):
    - 不读 stdin(NFR-1)
    - 不开 daemon(NFR-1)
    - 路径全部相对 --project-dir(NFR-4)
    - 临时文件进 <project>/temp/(NFR-5)
    - 错误消息中文为主(NFR-3)
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _common import emit_json


PLUGIN_VERSION = "0.5.5"
PLUGIN_NAME = "aeps-llm-wiki-plugin"
ACTOR_PREFIX = f"agent: producer/{PLUGIN_NAME}/{PLUGIN_VERSION}"

# 6 个顶层目录(硬编码,init 不接受 --xxx-dir 类参数)
TOP_LEVEL_DIRS = ("inbox", "raw", "scripts", "templates", "knowledge", "temp")

# raw/ 下 15 类子目录(硬约束,DESIGN.md §4.1 + init SKILL.md §阶段 1)
# 权威源:src/templates/raw-readme.md 第 5-19 行,逐字对齐
RAW_SUBDIRS = (
    "01_EE架构",       # raw-readme.md L5
    "02_芯片",         # raw-readme.md L6
    "03_通信与网络",   # raw-readme.md L7
    "04_操作系统与中间件",  # raw-readme.md L8
    "05_软件工程",     # raw-readme.md L9
    "06_功能安全",     # raw-readme.md L10
    "07_信息安全",     # raw-readme.md L11
    "08_AI与AI工程",   # raw-readme.md L12
    "09_域控制器",     # raw-readme.md L13
    "10_会议与活动",   # raw-readme.md L14
    "11_开发工具",     # raw-readme.md L15
    "12_法规_标准_政策",  # raw-readme.md L16
    "13_流程体系",     # raw-readme.md L17
    "14_测试与验证",   # raw-readme.md L18
    "15_算法",         # raw-readme.md L19
)

# knowledge/ 下 18 个叶子目录(1 + 7 + 7 + 1 + 1 + 1 = 18)
KNOWLEDGE_LEAF_DIRS = (
    "sources",
    "entities/person",
    "entities/organization",
    "entities/project",
    "entities/product",
    "entities/event",
    "entities/place",
    "entities/other",
    "concepts/theory",
    "concepts/method",
    "concepts/field",
    "concepts/phenomenon",
    "concepts/standard",
    "concepts/term",
    "concepts/other",
    "analyses",
    "comparisons",
    "syntheses",
)

# temp/.gitignore 5 行规范(DESIGN.md §2.4)
TEMP_GITIGNORE_CONTENT = "*\n!.gitkeep\n!proposal-*.json\n!decision-*.json\n!plan-*.json\n"

# 4 个种子文件头部说明(plugin 升级不覆盖,LLM 累积维护)
SEED_INDEX_HEADER = "---\ntype: index\ntitle: 主索引\nupdated: {ts}\ntags:\n  - docform/index\n---\n\n# 知识库主索引\n\n> 由 LLM 累积维护,plugin 升级不覆盖。\n"

SEED_OVERVIEW_HEADER = "---\ntype: overview\ntitle: 知识库大图\nupdated: {ts}\ntags:\n  - docform/overview\n---\n\n# 知识库大图\n\n> 由 LLM 累积维护,plugin 升级不覆盖。\n"

SEED_GLOSSARY_HEADER = "---\ntype: glossary\ntitle: 术语表\nupdated: {ts}\ntags:\n  - docform/glossary\n---\n\n# 术语表\n\n> 由 LLM 累积维护,**绝不覆盖**。plugin 升级走 append 策略,见 init SKILL.md §阶段 4。\n"

SEED_LOG_HEADER = "---\ntype: log\ntitle: 变更日志\nupdated: {ts}\ntags:\n  - docform/log\n---\n\n# 变更日志\n\n> append-only;最新在前。详见 SCHEMA.md §7。\n"


def _now_iso() -> str:
    """返回当前 UTC 时间的 ISO 8601 字符串(末尾 Z)。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_plugin_dir(project_dir: Path, plugin_dir_arg: str | None) -> Path:
    """解析 --plugin-dir 路径(plugin 的 src/ 目录,即 templates/ 与 scripts/ 所在层)。

    解析顺序:
        1. --plugin-dir 显式传入(相对 project_dir 解析)
        2. 当前脚本所在目录的父目录(开发态:脚本在 <plugin>/src/scripts/ 时回退到 <plugin>/src)
        3. project_dir 的同级 ../aeps-llm-wiki-plugin/src
        4. 回退 ./templates(开发态)
    """
    if plugin_dir_arg:
        candidate = (project_dir / plugin_dir_arg).resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"--plugin-dir 解析失败,目录不存在: {candidate}")

    script_dir = Path(__file__).resolve().parent
    src_dir = script_dir.parent
    if (src_dir / "templates").exists() and (src_dir / "scripts").exists():
        return src_dir

    sibling = project_dir.resolve().parent / "aeps-llm-wiki-plugin" / "src"
    if sibling.exists():
        return sibling

    return (project_dir / "templates").resolve()


def _ensure_dir_with_gitkeep(parent: Path, name: str, created: list[str]) -> Path:
    """建目录 + .gitkeep(若已存在不删)。"""
    target = parent / name
    if not target.exists():
        target.mkdir(parents=True, exist_ok=True)
        created.append(str(target.relative_to(parent.parent)))
        keep = target / ".gitkeep"
        if not keep.exists():
            keep.touch()
    return target


def _write_gitignore(path: Path, content: str) -> None:
    """写 .gitignore(若已存在不覆盖)。"""
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def _copy_templates(plugin_src: Path, project: Path, copied: list[str]) -> None:
    """把 <plugin>/src/templates/*.md 拷到 <project>/templates/(覆盖)。"""
    templates_src = plugin_src / "templates"
    templates_dst = project / "templates"
    templates_dst.mkdir(parents=True, exist_ok=True)

    if not templates_src.exists():
        return

    for src_md in templates_src.glob("*.md"):
        dst_md = templates_dst / src_md.name
        shutil.copy2(src_md, dst_md)
        copied.append(f"templates/{dst_md.name}")


def _copy_scripts(plugin_src: Path, project: Path, copied: list[str]) -> list[Path]:
    """把 <plugin>/src/scripts/*.py + requirements.txt 拷到 <project>/scripts/。

    跳过 DESIGN.md / README.md(plugin 设计文档,不入项目)。
    返回拷过来的 .py 列表(供后续自检 AST 用)。
    """
    scripts_src = plugin_src / "scripts"
    scripts_dst = project / "scripts"
    scripts_dst.mkdir(parents=True, exist_ok=True)

    if not scripts_src.exists():
        return []

    skip_names = {"DESIGN.md", "README.md"}
    copied_py: list[Path] = []

    for src_file in scripts_src.iterdir():
        if not src_file.is_file():
            continue
        if src_file.name in skip_names:
            continue
        if src_file.suffix == ".py" or src_file.name == "requirements.txt":
            dst_file = scripts_dst / src_file.name
            shutil.copy2(src_file, dst_file)
            copied.append(f"scripts/{dst_file.name}")
            if src_file.suffix == ".py":
                copied_py.append(dst_file)

    return copied_py


def _write_meta_json(project: Path, synced_at: str) -> str:
    """写 scripts/_meta.json(plugin 升级总是覆盖)。"""
    meta = {
        "plugin": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "synced_at": synced_at,
    }
    meta_path = project / "scripts" / "_meta.json"
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return f"scripts/_meta.json"


def _write_version_file(project: Path) -> str:
    """写 .aeps-plugin-version(单行版本号)。"""
    version_path = project / ".aeps-plugin-version"
    version_path.write_text(PLUGIN_VERSION + "\n", encoding="utf-8")
    return ".aeps-plugin-version"


def _write_seed_files(
    project: Path, synced_at: str, re_run: bool, copied: list[str]
) -> None:
    """写 4 个种子文件。

    策略:
        - 不存在 → 新建 + 头部说明
        - 已存在 + re_run → 不覆盖(保留用户内容)
        - 已存在 + 首次启用 → 也不覆盖(同 init SKILL.md §阶段 4 不变量)
    """
    knowledge = project / "knowledge"
    knowledge.mkdir(parents=True, exist_ok=True)

    seeds = [
        ("index.md", SEED_INDEX_HEADER),
        ("overview.md", SEED_OVERVIEW_HEADER),
        ("glossary.md", SEED_GLOSSARY_HEADER),
        ("log.md", SEED_LOG_HEADER),
    ]

    for filename, header_tpl in seeds:
        path = knowledge / filename
        if not path.exists():
            content = header_tpl.format(ts=synced_at)
            path.write_text(content, encoding="utf-8")
            copied.append(f"knowledge/{filename}")


def _append_log_re_run(project: Path, synced_at: str, copied: list[str]) -> None:
    """re-run 时 log.md 追加一行 Update 记录。"""
    log_path = project / "knowledge" / "log.md"
    if not log_path.exists():
        return
    line = f"\n* **Update**: re-run init at {synced_at} by {ACTOR_PREFIX}\n"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line)
    copied.append("knowledge/log.md (re-run line appended)")


def _ensure_log_heading(project: Path, synced_at: str, copied: list[str]) -> None:
    """首次启用时,log.md 顶部加当日 heading(若还没有)。

    策略:若 log.md 顶层已有 frontmatter (---...---),把 heading 插在
    frontmatter 之前(避免破坏 YAML 结构);否则直接 prepend。
    """
    log_path = project / "knowledge" / "log.md"
    if not log_path.exists():
        return
    date_heading = f"## {synced_at[:10]}"
    try:
        text = log_path.read_text(encoding="utf-8")
    except OSError:
        return
    if date_heading in text:
        return

    lines = text.splitlines(keepends=True)
    insertion = f"{date_heading}\n\n"

    if lines and lines[0].startswith("---"):
        end_idx = None
        for i in range(1, len(lines)):
            if lines[i].startswith("---"):
                end_idx = i
                break
        if end_idx is not None:
            after_fm = end_idx + 1
            new_lines = lines[:after_fm] + ["\n", insertion] + lines[after_fm:]
            log_path.write_text("".join(new_lines), encoding="utf-8")
            copied.append("knowledge/log.md (date heading inserted after frontmatter)")
            return

    log_path.write_text(insertion + text, encoding="utf-8")
    copied.append("knowledge/log.md (date heading prepended)")


def _build_top_level(project: Path, created: list[str]) -> None:
    """建 6 个顶层目录 + .gitkeep。"""
    for name in TOP_LEVEL_DIRS:
        _ensure_dir_with_gitkeep(project, name, created)


def _build_temp_gitignore(project: Path) -> None:
    """写 temp/.gitignore 5 行规范。"""
    temp_dir = project / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    _write_gitignore(temp_dir / ".gitignore", TEMP_GITIGNORE_CONTENT)


def _build_raw_subdirs(project: Path, created: list[str]) -> None:
    """建 raw/ 下 15 个子目录。"""
    raw = project / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    for sub in RAW_SUBDIRS:
        target = raw / sub
        if not target.exists():
            target.mkdir(parents=True, exist_ok=True)
            created.append(f"raw/{sub}")
            keep = target / ".gitkeep"
            if not keep.exists():
                keep.touch()


def _build_knowledge_leaves(project: Path, created: list[str]) -> None:
    """建 knowledge/ 下 18 个叶子目录。"""
    knowledge = project / "knowledge"
    knowledge.mkdir(parents=True, exist_ok=True)
    for leaf in KNOWLEDGE_LEAF_DIRS:
        target = knowledge / leaf
        if not target.exists():
            target.mkdir(parents=True, exist_ok=True)
            created.append(f"knowledge/{leaf}")
            keep = target / ".gitkeep"
            if not keep.exists():
                keep.touch()


def _detect_re_run(project: Path) -> bool:
    """检测是否幂等再入(knowledge/SCHEMA.md 存在)。"""
    return (project / "knowledge" / "SCHEMA.md").exists()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="init-vault.py",
        description="搭建 / 同步 aeps-llm-wiki 知识库目录结构(6 顶层 + raw 15 + knowledge 18 + temp + 拷 templates/scripts)。",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="目标项目根目录(默认当前目录)。",
    )
    parser.add_argument(
        "--re-run",
        action="store_true",
        default=False,
        help="幂等再入:不覆盖已有种子文件;log.md 追加 Update 行。",
    )
    parser.add_argument(
        "--plugin-dir",
        default=None,
        help="plugin 的 src/ 路径(默认解析 project_dir 的同级 ../aeps-llm-wiki-plugin/src)。",
    )
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> dict[str, Any]:
    """主流程入口。"""
    project = Path(args.project_dir).resolve()
    if not project.exists():
        raise FileNotFoundError(f"--project-dir 不存在: {project}")

    plugin_src = _resolve_plugin_dir(project, args.plugin_dir)

    created: list[str] = []
    copied: list[str] = []

    synced_at = _now_iso()
    re_run = args.re_run or _detect_re_run(project)

    _build_top_level(project, created)
    _build_temp_gitignore(project)
    _build_raw_subdirs(project, created)
    _build_knowledge_leaves(project, created)

    _write_seed_files(project, synced_at, re_run, copied)
    if re_run:
        _append_log_re_run(project, synced_at, copied)
    else:
        _ensure_log_heading(project, synced_at, copied)

    _copy_templates(plugin_src, project, copied)
    _copy_scripts(plugin_src, project, copied)

    meta_rel = _write_meta_json(project, synced_at)
    copied.append(meta_rel)

    version_rel = _write_version_file(project)
    copied.append(version_rel)

    return {
        "created": created,
        "copied": copied,
        "synced_at": synced_at,
        "plugin_version": PLUGIN_VERSION,
        "re_run": re_run,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = run(args)
    except FileNotFoundError as e:
        emit_json({"ok": False, "error": f"路径解析失败: {e}"})
        return 1
    except OSError as e:
        emit_json({"ok": False, "error": f"文件系统错误: {e}"})
        return 1

    result["ok"] = True
    emit_json(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
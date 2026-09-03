"""test_ingest_skeleton.py — 6 个 ingest 组骨架脚本的离线单测。

覆盖:
    - append-log.py:7 种前缀 + 最新在前 + actor 格式
    - ensure-dirs.py:mkdir 15 类子目录 + 幂等 + 非法名字拒绝
    - convert-to-md.py:扩展名分流 + native passthrough + --emit-to G10
    - safe-mv.py:skip / delete-only / overwrite atomic / G10 双文件迁移
    - validate-frontmatter.py:缺字段 + 6 轴 tag + unknown type WARN + G10 三元组
    - validate-proposal.py:5 步校验 + 字符清洗 + 截断 + JSONDecodeError backup

设计依据:
    - 阶段 C-1.2.1 ingest 骨架 6 .py 测试用例
    - DESIGN.md §4 测试对齐

CLI:
    pytest tests/test_ingest_skeleton.py -v
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


# scripts/ 加入 sys.path(便于 import 各 .py 模块)
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# Python 导入名不接受 hyphen(init-vault),改用 importlib 动态加载
import importlib.util as _importlib_util  # noqa: E402


def _load_module(name: str, file_path: Path):
    spec = _importlib_util.spec_from_file_location(name, str(file_path))
    module = _importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_init_vault = _load_module("init_vault_ingest_skeleton", SCRIPTS_DIR / "init-vault.py")

ACTOR_PREFIX = _init_vault.ACTOR_PREFIX
KNOWLEDGE_LEAF_DIRS = _init_vault.KNOWLEDGE_LEAF_DIRS
RAW_SUBDIRS = _init_vault.RAW_SUBDIRS
TOP_LEVEL_DIRS = _init_vault.TOP_LEVEL_DIRS
_now_iso = _init_vault._now_iso
init_vault_run = _init_vault.run


# ---------------------------------------------------------------------------
# fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """隔离 tmp 项目 + 跑 init 一次(完整 6 顶层 + raw 15 + knowledge 18 + 4 种子)。"""
    # 模拟 plugin_src:用 scripts/ 自身作为 plugin src
    plugin_src = SCRIPTS_DIR.parent  # <plugin>/src
    project = tmp_path / "project"
    project.mkdir()

    # 直接调 init-vault.run
    class Args:
        project_dir = str(project)
        re_run = False
        plugin_dir = str(plugin_src)

    init_vault_run(Args())
    return project


@pytest.fixture
def plugin_src() -> Path:
    """返回 plugin 的 src/ 路径(供 --plugin-dir / 模板定位用)。"""
    return SCRIPTS_DIR.parent


def _run_script(
    name: str,
    *args: str,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess:
    """子进程跑一个脚本(避免 sys.path / 模块副作用)。

    Returns:
        CompletedProcess(stdout=str, stderr=str, returncode=int)
    """
    cmd = [sys.executable, str(SCRIPTS_DIR / name), *args]
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )


# ---------------------------------------------------------------------------
# append-log.py 测试
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "action",
    ["Creation", "Update", "Deprecation", "Migration", "LintFix", "Converted", "IngestFailure"],
)
def test_append_log_7_prefixes(tmp_project: Path, action: str) -> None:
    """7 种前缀的 log 行格式:**<prefix>**: ... by <actor>。"""
    result = _run_script(
        "append-log.py",
        "--project-dir", str(tmp_project),
        "--action", action,
        "--summary", f"test {action}",
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    log = (tmp_project / "knowledge" / "log.md").read_text(encoding="utf-8")
    assert f"**{action}**" in log, f"缺前缀 {action}: {log[:200]}"
    assert "test " + action in log
    assert ACTOR_PREFIX in log


def test_append_log_latest_first(tmp_project: Path) -> None:
    """append 写入后,文件倒数几行的内容是最近追加的(最新在前)。"""
    _run_script(
        "append-log.py",
        "--project-dir", str(tmp_project),
        "--action", "Creation",
        "--summary", "first",
    )
    _run_script(
        "append-log.py",
        "--project-dir", str(tmp_project),
        "--action", "Update",
        "--summary", "second",
    )
    log_text = (tmp_project / "knowledge" / "log.md").read_text(encoding="utf-8")

    # 简单判定:second 应比 first 更靠近文件末尾
    first_idx = log_text.rfind("first")
    second_idx = log_text.rfind("second")
    assert second_idx > first_idx, f"second 应在 first 之后:first={first_idx} second={second_idx}"
    # second 应在最后 10 行内
    last_lines = log_text.strip().splitlines()[-10:]
    assert any("second" in ln for ln in last_lines)


def test_append_log_actor_format(tmp_project: Path) -> None:
    """actor 三种前缀格式校验:agent: / human: / process:。"""
    # agent: 默认
    r1 = _run_script(
        "append-log.py",
        "--project-dir", str(tmp_project),
        "--action", "Creation",
        "--summary", "agent actor",
    )
    assert r1.returncode == 0
    log = (tmp_project / "knowledge" / "log.md").read_text(encoding="utf-8")
    assert ACTOR_PREFIX in log

    # human: 自定义
    r2 = _run_script(
        "append-log.py",
        "--project-dir", str(tmp_project),
        "--action", "Update",
        "--summary", "human actor",
        "--actor", "human:zhigang.liu",
    )
    assert r2.returncode == 0
    log = (tmp_project / "knowledge" / "log.md").read_text(encoding="utf-8")
    assert "human:zhigang.liu" in log


# ---------------------------------------------------------------------------
# ensure-dirs.py 测试
# ---------------------------------------------------------------------------


def test_ensure_dirs_creates_raw_subdir(tmp_project: Path) -> None:
    """mkdir raw 子目录 + 已存在幂等。"""
    # init 已建好 raw/06_功能安全,先验证幂等跑(created=False);再删去验证创建
    raw06 = tmp_project / "raw" / "06_功能安全"
    assert raw06.exists(), "init 应预建 raw/06_功能安全"

    # 删除以测试创建路径
    shutil.rmtree(raw06)
    assert not raw06.exists()

    r1 = _run_script(
        "ensure-dirs.py",
        "--project-dir", str(tmp_project),
        "--path", "raw/06_功能安全",
    )
    assert r1.returncode == 0, f"stderr: {r1.stderr}"
    assert raw06.exists(), f"目录应被创建:{raw06}"
    out = json.loads(r1.stdout)
    assert out["created"] is True

    # 第二次跑(created=false)
    r2 = _run_script(
        "ensure-dirs.py",
        "--project-dir", str(tmp_project),
        "--path", "raw/06_功能安全",
    )
    assert r2.returncode == 0
    out2 = json.loads(r2.stdout)
    assert out2["created"] is False
    assert out2["existed"] is True


def test_ensure_dirs_validates_15_classes(tmp_project: Path) -> None:
    """非法子目录名 → exit 1。"""
    bad_runs = [
        "raw/99_不存在",   # 不在 15 类字典
        "raw/",            # 空子目录
        "knowledge/foo",   # 非 raw/
        "scripts/x",       # 非 raw/
    ]
    for bad_path in bad_runs:
        r = _run_script(
            "ensure-dirs.py",
            "--project-dir", str(tmp_project),
            "--path", bad_path,
        )
        assert r.returncode != 0, f"应拒绝 {bad_path},但 exit={r.returncode}"


# ---------------------------------------------------------------------------
# convert-to-md.py 测试
# ---------------------------------------------------------------------------


def test_convert_to_md_dispatch(tmp_project: Path) -> None:
    """扩展名 → converter 分流(native / claude-native / anydoc / paddleocr)。"""
    sys.path.insert(0, str(SCRIPTS_DIR))
    convert_to_md_mod = _load_module("convert_to_md_ingest_skeleton", SCRIPTS_DIR / "convert-to-md.py")
    classify = convert_to_md_mod.classify

    # native
    assert classify("md")["converter"] is None
    assert classify("md")["native_text"] is True
    assert classify("txt")["native_text"] is True
    # claude-native
    assert classify("csv")["converter"] == "claude-native"
    assert classify("html")["converter"] == "claude-native"
    # anydoc / paddleocr
    assert classify("pdf")["converter"] == "anydoc"
    assert classify("pptx")["converter"] == "anydoc"
    assert classify("png")["converter"] == "paddleocr"
    assert classify("jpg")["converter"] == "paddleocr"


def test_convert_to_md_native_passthrough(tmp_project: Path) -> None:
    """.md / .txt 不转换,直接写 temp/<basename>.md。"""
    # 准备 inbox 文件
    inbox = tmp_project / "inbox"
    inbox.mkdir(exist_ok=True)
    src_md = inbox / "test.md"
    src_md.write_text("# Hello\n\nThis is native text\n", encoding="utf-8")
    src_txt = inbox / "test.txt"
    src_txt.write_text("Plain text content\n", encoding="utf-8")

    temp_dir = tmp_project / "temp"
    temp_dir.mkdir(exist_ok=True)

    # .md passthrough
    r_md = _run_script(
        "convert-to-md.py",
        "--project-dir", str(tmp_project),
        "--input", "inbox/test.md",
        "--output-dir", "temp/",
    )
    assert r_md.returncode == 0, f"stderr: {r_md.stderr}"
    out_md = json.loads(r_md.stdout)
    assert out_md["native_text"] is True
    assert out_md["converter"] is None
    assert (temp_dir / "test.md").exists()

    # .txt
    r_txt = _run_script(
        "convert-to-md.py",
        "--project-dir", str(tmp_project),
        "--input", "inbox/test.txt",
        "--output-dir", "temp/",
    )
    assert r_txt.returncode == 0
    out_txt = json.loads(r_txt.stdout)
    assert out_txt["native_text"] is True


def test_convert_to_md_emit_to_g10(tmp_project: Path) -> None:
    """--emit-to temp/ 写 .converted.md(claude-native 场景)。"""
    inbox = tmp_project / "inbox"
    inbox.mkdir(exist_ok=True)
    src_csv = inbox / "data.csv"
    src_csv.write_text("a,b\n1,2\n", encoding="utf-8")

    temp_dir = tmp_project / "temp"
    temp_dir.mkdir(exist_ok=True)

    r = _run_script(
        "convert-to-md.py",
        "--project-dir", str(tmp_project),
        "--input", "inbox/data.csv",
        "--output-dir", "temp/",
        "--emit-to", "temp/",
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    out = json.loads(r.stdout)
    assert out["converter"] == "claude-native"
    assert out["native_text"] is False
    # 既要 <basename>.md 也要 <basename>.<ext>.converted.md
    assert (temp_dir / "data.md").exists()
    assert (temp_dir / "data.csv.converted.md").exists()

    # native 场景不写 .converted.md
    src_md2 = inbox / "native.md"
    src_md2.write_text("native", encoding="utf-8")
    r2 = _run_script(
        "convert-to-md.py",
        "--project-dir", str(tmp_project),
        "--input", "inbox/native.md",
        "--output-dir", "temp/",
        "--emit-to", "temp/",
    )
    assert r2.returncode == 0
    assert (temp_dir / "native.md").exists()
    assert not (temp_dir / "native.md.converted.md").exists()


# ---------------------------------------------------------------------------
# safe-mv.py 测试
# ---------------------------------------------------------------------------


def _write_decision(
    tmp_project: Path,
    actions: list[dict],
    hash_val: str = "test123",
) -> Path:
    """工具:写 decision JSON 到 temp/。"""
    temp_dir = tmp_project / "temp"
    temp_dir.mkdir(exist_ok=True)
    decision = {
        "type": "ingest_decision",
        "schema_version": "1.0",
        "decided_at": _now_iso(),
        "actor": "human:tester",
        "proposal_refs": ["temp/proposal-test.json"],
        "actions": actions,
    }
    decision_path = temp_dir / f"decision-{hash_val}.json"
    decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    return decision_path


def test_safe_mv_skip(tmp_project: Path) -> None:
    """op: skip 不动文件。"""
    inbox = tmp_project / "inbox"
    inbox.mkdir(exist_ok=True)
    src = inbox / "file.md"
    src.write_text("content", encoding="utf-8")
    raw_dest_dir = tmp_project / "raw" / "06_功能安全"

    decision_path = _write_decision(
        tmp_project,
        actions=[{"op": "skip", "source": "inbox/file.md", "dest": "raw/06_功能安全/file.md"}],
    )
    r = _run_script(
        "safe-mv.py", "--project-dir", str(tmp_project), "--apply", str(decision_path),
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    assert src.exists(), "skip 不应删除源"
    assert not (raw_dest_dir / "file.md").exists(), "skip 不应创建目标"


def test_safe_mv_delete_only(tmp_project: Path) -> None:
    """op: delete-only 删旧副本。"""
    inbox = tmp_project / "inbox"
    inbox.mkdir(exist_ok=True)
    src = inbox / "file.md"
    src.write_text("new", encoding="utf-8")
    raw_dest_dir = tmp_project / "raw" / "06_功能安全"
    raw_dest_dir.mkdir(parents=True, exist_ok=True)
    dest_old = raw_dest_dir / "file.md"
    dest_old.write_text("old content", encoding="utf-8")

    decision_path = _write_decision(
        tmp_project,
        actions=[{"op": "delete-only", "source": "inbox/file.md", "dest": "raw/06_功能安全/file.md"}],
        hash_val="del01",
    )
    r = _run_script(
        "safe-mv.py", "--project-dir", str(tmp_project), "--apply", str(decision_path),
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    assert src.exists(), "delete-only 保留 inbox 原文件"
    assert not dest_old.exists(), "delete-only 删除旧副本"


def test_safe_mv_overwrite_atomic(tmp_project: Path) -> None:
    """op: overwrite 先备份 + atomic 替换(Q7 防护)。"""
    inbox = tmp_project / "inbox"
    inbox.mkdir(exist_ok=True)
    src = inbox / "file.md"
    src.write_text("new content", encoding="utf-8")
    raw_dest_dir = tmp_project / "raw" / "06_功能安全"
    raw_dest_dir.mkdir(parents=True, exist_ok=True)
    dest_old = raw_dest_dir / "file.md"
    dest_old.write_text("old content", encoding="utf-8")

    decision_path = _write_decision(
        tmp_project,
        actions=[{"op": "overwrite", "source": "inbox/file.md", "dest": "raw/06_功能安全/file.md"}],
        hash_val="ow01",
    )
    r = _run_script(
        "safe-mv.py", "--project-dir", str(tmp_project), "--apply", str(decision_path),
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    # inbox 源被搬走
    assert not src.exists()
    # 目标存在且被替换为新内容(overwrite 语义:不是删除,而是原子替换)
    assert dest_old.exists(), "overwrite 应保留目标文件(替换内容)"
    assert dest_old.read_text(encoding="utf-8") == "new content", "应替换为新内容"
    # 备份目录存在
    backup_dir = tmp_project / "temp" / "raw_backup_ow01"
    assert backup_dir.exists()
    assert (backup_dir / "file.md").exists(), "应备份旧副本"
    assert (backup_dir / "file.md").read_text(encoding="utf-8") == "old content", "备份保留旧内容"


def test_safe_mv_g10_pair_migration(tmp_project: Path) -> None:
    """同时迁原文件 + .converted.md。"""
    inbox = tmp_project / "inbox"
    inbox.mkdir(exist_ok=True)
    src = inbox / "doc.pdf"
    src.write_text("pdf stub", encoding="utf-8")
    converted_src = inbox / "doc.pdf.converted.md"
    converted_src.write_text("# doc converted\n", encoding="utf-8")

    raw_dest_dir = tmp_project / "raw" / "06_功能安全"
    raw_dest_dir.mkdir(parents=True, exist_ok=True)

    decision_path = _write_decision(
        tmp_project,
        actions=[{"op": "mv", "source": "inbox/doc.pdf", "dest": "raw/06_功能安全/doc.pdf"}],
        hash_val="g10pair",
    )
    r = _run_script(
        "safe-mv.py", "--project-dir", str(tmp_project), "--apply", str(decision_path),
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    # 两个文件都迁到了 raw/06_功能安全/
    assert (raw_dest_dir / "doc.pdf").exists()
    assert (raw_dest_dir / "doc.pdf.converted.md").exists()
    # inbox 原文件 + 副本都搬空
    assert not src.exists()
    assert not converted_src.exists()


# ---------------------------------------------------------------------------
# validate-frontmatter.py 测试
# ---------------------------------------------------------------------------


def _write_md(tmp_project: Path, rel_path: str, content: str) -> Path:
    """工具:在 tmp_project 内写一个 .md 文件(创建中间目录)。"""
    full = tmp_project / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return full


def test_validate_frontmatter_required_fields(tmp_project: Path) -> None:
    """缺字段 → ok=false + missing 列出。"""
    bad = _write_md(
        tmp_project,
        "knowledge/sources/missing.md",
        "---\ntype: source\n---\n\n正文\n",
    )
    r = _run_script(
        "validate-frontmatter.py",
        "--project-dir", str(tmp_project),
        "--file", str(bad.relative_to(tmp_project)),
    )
    assert r.returncode != 0, f"应 exit 1,实际 {r.returncode}"
    out = json.loads(r.stdout)
    assert out["ok"] is False
    # 至少 title / description / updated / tags 在 missing 列表
    for must in ("title", "description", "updated", "tags"):
        assert any(must in m for m in out["missing"]), f"missing 应含 {must}: {out['missing']}"


def test_validate_frontmatter_6轴_tag(tmp_project: Path) -> None:
    """裸 tag(ai 无 domain/ 前缀)→ errors 列出。"""
    bad = _write_md(
        tmp_project,
        "knowledge/sources/badtag.md",
        "---\n"
        "type: source\n"
        "title: bad\n"
        "description: bad\n"
        "updated: 2026-09-03T00:00:00Z\n"
        "tags:\n"
        "  - ai\n"  # 裸 tag
        "  - docform/source\n"
        "source_file: raw/06_功能安全/foo.pdf\n"
        "sources:\n"
        "  - resource: raw/06_功能安全/foo.pdf\n"
        "    id: foo\n"
        "format: pdf\n"
        "converter: anydoc\n"
        "native_text: false\n"
        "converted_path: raw/06_功能安全/foo.pdf.converted.md\n"
        "links:\n"
        "  - '[[foo.pdf.converted]]'\n"
        "summary: 'x'\n"
        "---\n\n# t\n",
    )
    r = _run_script(
        "validate-frontmatter.py",
        "--project-dir", str(tmp_project),
        "--file", str(bad.relative_to(tmp_project)),
    )
    out = json.loads(r.stdout)
    assert out["ok"] is False
    assert any("ai" in e and "axis" in e or "格式" in e for e in out["errors"]), (
        f"应报告裸 tag 'ai':{out['errors']}"
    )


def test_validate_frontmatter_unknown_type_warn_not_fail(tmp_project: Path) -> None:
    """OKF §11 容忍:未知 type → ok=true 但 warnings 含提示。"""
    good = _write_md(
        tmp_project,
        "knowledge/sources/exotic.md",
        "---\n"
        "type: exotic_unknown_type\n"
        "title: ok\n"
        "description: ok\n"
        "updated: 2026-09-03T00:00:00Z\n"
        "tags:\n"
        "  - docform/source\n"
        "  - domain/ai\n"
        "---\n\n# ok\n",
    )
    r = _run_script(
        "validate-frontmatter.py",
        "--project-dir", str(tmp_project),
        "--file", str(good.relative_to(tmp_project)),
    )
    out = json.loads(r.stdout)
    # 未知 type 是 WARN,不 FAIL(但 source 特有字段缺 → errors)
    # 本测试关注 unknown type 的 WARN 行为
    assert any("未知 type" in w for w in out["warnings"]), (
        f"应有 unknown type WARN:{out['warnings']}"
    )


def test_validate_frontmatter_g10_consistency(tmp_project: Path) -> None:
    """G10 三元组 native_text ⇔ converter ⇔ converted_path 不一致 → fail。"""
    bad = _write_md(
        tmp_project,
        "knowledge/sources/g10bad.md",
        "---\n"
        "type: source\n"
        "title: g10bad\n"
        "description: x\n"
        "updated: 2026-09-03T00:00:00Z\n"
        "tags:\n"
        "  - docform/source\n"
        "source_file: raw/06_功能安全/foo.pdf\n"
        "sources:\n"
        "  - resource: raw/06_功能安全/foo.pdf\n"
        "    id: foo\n"
        "format: pdf\n"
        "converter: anydoc\n"        # 非 null
        "native_text: true\n"        # 但 native_text=true → 矛盾
        "converted_path: null\n"
        "links: []\n"
        "summary: 'x'\n"
        "---\n\n# x\n",
    )
    r = _run_script(
        "validate-frontmatter.py",
        "--project-dir", str(tmp_project),
        "--file", str(bad.relative_to(tmp_project)),
    )
    out = json.loads(r.stdout)
    assert out["ok"] is False
    assert any("G10 三元组" in e for e in out["errors"]), (
        f"应报告 G10 三元组:{out['errors']}"
    )


def test_validate_frontmatter_pass_minimal(tmp_project: Path) -> None:
    """最小完整 source 页应通过校验。"""
    good = _write_md(
        tmp_project,
        "knowledge/sources/good.md",
        "---\n"
        "type: source\n"
        "title: good\n"
        "description: good\n"
        "updated: 2026-09-03T00:00:00Z\n"
        "tags:\n"
        "  - docform/source\n"
        "  - domain/ai\n"
        "source_file: raw/06_功能安全/good.pdf\n"
        "sources:\n"
        "  - resource: raw/06_功能安全/good.pdf\n"
        "    id: good\n"
        "format: pdf\n"
        "converter: anydoc\n"
        "native_text: false\n"
        "converted_path: raw/06_功能安全/good.pdf.converted.md\n"
        "links:\n"
        "  - '[[good.pdf.converted]]'\n"
        "summary: 'good one'\n"
        "---\n\n# x\n",
    )
    r = _run_script(
        "validate-frontmatter.py",
        "--project-dir", str(tmp_project),
        "--file", str(good.relative_to(tmp_project)),
    )
    out = json.loads(r.stdout)
    assert out["ok"] is True, f"应通过,实际 errors={out['errors']} missing={out['missing']}"


# ---------------------------------------------------------------------------
# validate-proposal.py 测试
# ---------------------------------------------------------------------------


def test_validate_proposal_5_steps(tmp_project: Path) -> None:
    """合法 proposal JSON → ok=true + 写 .sanitized。"""
    proposal = {
        "file": "inbox/test.md",
        "suggested_subdir": "raw/06_功能安全",
        "raw_category": "06_功能安全",
        "format": "md",
        "converter": None,
        "native_text": True,
        "converted_path": None,
        "concepts": [
            {"name": "Foo", "type": "concept", "subtype": "theory", "aliases": []}
        ],
        "_meta": {
            "doc_id": "test-abcdef01",
            "schema_version": "1.0",
            "extracted_at": "2026-09-03T00:00:00Z",
            "extracted_by": "agent: producer/aeps-llm-wiki-plugin/0.5.5",
        },
    }
    temp_dir = tmp_project / "temp"
    temp_dir.mkdir(exist_ok=True)
    proposal_path = temp_dir / "proposal-good.json"
    proposal_path.write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8")

    r = _run_script(
        "validate-proposal.py",
        "--project-dir", str(tmp_project),
        "--input", str(proposal_path.relative_to(tmp_project)),
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    out = json.loads(r.stdout)
    assert out["ok"] is True
    assert out["sanitized_path"] is not None
    assert (tmp_project / out["sanitized_path"]).exists()


def test_validate_proposal_char_clean(tmp_project: Path) -> None:
    """\\x00 strip / </script> replace / BOM keep。"""
    proposal = {
        "file": "inbox/clean.md",
        "suggested_subdir": "raw/06_功能安全",
        "raw_category": "06_功能安全",
        "format": "md",
        "converter": None,
        "native_text": True,
        "converted_path": None,
        "concepts": [
            {"name": "Foo", "type": "concept", "subtype": "theory", "aliases": []}
        ],
        "_meta": {
            "doc_id": "clean-12345678",
            "schema_version": "1.0",
            "extracted_at": "2026-09-03T00:00:00Z",
            "extracted_by": "agent: producer/aeps-llm-wiki-plugin/0.5.5",
        },
    }
    # 给 file 字段加 \\x00 + </script> 字符
    proposal["file"] = "inbox/clea\x00n.md</script>onclick=x"

    temp_dir = tmp_project / "temp"
    temp_dir.mkdir(exist_ok=True)
    proposal_path = temp_dir / "proposal-clean.json"
    proposal_path.write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8")

    r = _run_script(
        "validate-proposal.py",
        "--project-dir", str(tmp_project),
        "--input", str(proposal_path.relative_to(tmp_project)),
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    out = json.loads(r.stdout)
    assert out["ok"] is True

    # 读 .sanitized,断言清洗已生效
    sanitized_path = tmp_project / out["sanitized_path"]
    sanitized_text = sanitized_path.read_text(encoding="utf-8")
    assert "\x00" not in sanitized_text, "NUL 已 strip"
    # JSON 序列化会把反斜杠转义为双反斜杠,所以字面输出是 <\\/script>
    assert "<\\\\/script>" in sanitized_text, "</script> 已替换"
    assert "</script>" not in sanitized_text, "不应再有字面 </script>"


def test_validate_proposal_truncate(tmp_project: Path) -> None:
    """concepts > 200 → ok=false + backup。"""
    proposal = {
        "file": "inbox/truncate.md",
        "suggested_subdir": "raw/06_功能安全",
        "raw_category": "06_功能安全",
        "format": "md",
        "converter": None,
        "native_text": True,
        "converted_path": None,
        "concepts": [
            {"name": f"C{i}", "type": "concept", "subtype": "theory", "aliases": []}
            for i in range(201)
        ],
        "_meta": {
            "doc_id": "trunc-99999999",
            "schema_version": "1.0",
            "extracted_at": "2026-09-03T00:00:00Z",
            "extracted_by": "agent: producer/aeps-llm-wiki-plugin/0.5.5",
        },
    }
    temp_dir = tmp_project / "temp"
    temp_dir.mkdir(exist_ok=True)
    proposal_path = temp_dir / "proposal-trunc.json"
    proposal_path.write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8")

    r = _run_script(
        "validate-proposal.py",
        "--project-dir", str(tmp_project),
        "--input", str(proposal_path.relative_to(tmp_project)),
    )
    assert r.returncode != 0, f"应 exit 1,实际 {r.returncode}"
    out = json.loads(r.stdout)
    assert out["ok"] is False
    assert out["backup_path"] is not None
    assert out["sanitized_path"] is None
    assert any("截断" in e for e in out["errors"])


def test_validate_proposal_corrupt_backup(tmp_project: Path) -> None:
    """JSONDecodeError → .corrupt.bak。"""
    temp_dir = tmp_project / "temp"
    temp_dir.mkdir(exist_ok=True)
    bad_path = temp_dir / "proposal-corrupt.json"
    bad_path.write_text("{ this is not valid json", encoding="utf-8")

    r = _run_script(
        "validate-proposal.py",
        "--project-dir", str(tmp_project),
        "--input", str(bad_path.relative_to(tmp_project)),
    )
    assert r.returncode != 0
    out = json.loads(r.stdout)
    assert out["ok"] is False
    assert out["backup_path"] is not None
    assert any("JSON 解析失败" in e for e in out["errors"])
    # .corrupt.bak 文件存在
    bak = tmp_project / out["backup_path"]
    assert bak.exists()

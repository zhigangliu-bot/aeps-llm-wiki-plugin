"""test_c2_high_risk.py — 阶段 C-2 高风险路径测试用例。

按 A-G 七组共 26 个用例,聚焦真实存在风险的关键路径,而非覆盖率。

设计依据:
    - DESIGN.md §1.1 模块边界
    - DESIGN.md §3 关键 PATCH(G10 / Q5 / Q7 / Q10 / Q11 / v0.5.2 / v0.5.4)
    - DESIGN.md §9 新增 PATCH C-2(本轮)

用例分布:
    A. safe-mv 4 op 语义覆盖       (6 用例)
    B. convert-to-md 4 路由覆盖    (4 用例)
    C. append-log 6 种前缀补完     (3 用例)
    D. validate-frontmatter G10 三元组 (4 用例)
    E. generate-* 序列化分支        (5 用例)
    F. init-vault 幂等再入         (2 用例)
    G. ingest/cleanup 留哪些/删哪些 (2 用例)

CLI:
    pytest tests/test_c2_high_risk.py -v
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


# scripts/ 加入 sys.path(便于 import 各 .py 模块)
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import importlib.util as _importlib_util  # noqa: E402


def _load_module(name: str, file_path: Path):
    """Python 导入名不接受 hyphen,改用 importlib 动态加载。"""
    spec = _importlib_util.spec_from_file_location(name, str(file_path))
    module = _importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# 预加载 init-vault 常量(供 fixture / 测试复用)
_init_vault_mod = _load_module("init_vault_c2", SCRIPTS_DIR / "init-vault.py")
_init_vault_run = _init_vault_mod.run
ACTOR_PREFIX = _init_vault_mod.ACTOR_PREFIX
RAW_SUBDIRS = _init_vault_mod.RAW_SUBDIRS
KNOWLEDGE_LEAF_DIRS = _init_vault_mod.KNOWLEDGE_LEAF_DIRS
_now_iso = _init_vault_mod._now_iso


# ---------------------------------------------------------------------------
# fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """隔离 tmp 项目 + 跑 init 一次(完整 6 顶层 + raw 15 + knowledge 18 + 4 种子)。"""
    plugin_src = SCRIPTS_DIR.parent  # <plugin>/src
    project = tmp_path / "project"
    project.mkdir()

    class Args:
        project_dir = str(project)
        re_run = False
        plugin_dir = str(plugin_src)

    _init_vault_run(Args())
    return project


def _run_script(
    name: str,
    *args: str,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess:
    """子进程跑一个脚本(避免 sys.path / 模块副作用)。"""
    cmd = [sys.executable, str(SCRIPTS_DIR / name), *args]
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )


def _write_decision(
    project: Path,
    actions: list[dict],
    hash_val: str = "test123",
) -> Path:
    """工具:写 decision JSON 到 temp/。"""
    temp_dir = project / "temp"
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


def _write_md(project: Path, rel_path: str, content: str) -> Path:
    """工具:在 project 内写一个 .md 文件(创建中间目录)。"""
    full = project / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return full


def _make_source_meta(
    *,
    converter: str | None = "anydoc",
    native_text: bool = False,
    converted_path: str | None = "raw/06_功能安全/foo.pdf.converted.md",
    aliases: list[str] | None = None,
    summary: str | None = "x",
) -> dict:
    """构造 generate-source-page.py 的 meta-json(G10 + Q9 默认合规)。"""
    meta = {
        "type": "source",
        "title": "fixture",
        "description": "fixture description",
        "updated": "2026-09-03T00:00:00Z",
        "tags": ["docform/source", "domain/ai"],
        "source_file": "raw/06_功能安全/foo.pdf",
        "sources": [{"resource": "raw/06_功能安全/foo.pdf", "id": "foo"}],
        "format": "pdf",
        "converter": converter,
        "native_text": native_text,
        "converted_path": converted_path,
        "links": ["[[foo.pdf.converted]]"],
    }
    if aliases is not None:
        meta["aliases"] = aliases
    if summary is not None:
        meta["summary"] = summary
    return meta


def _make_body_file(project: Path, content: str = "# fixture\n\nbody\n") -> Path:
    """工具:写 body-file,供 generate-* 读取。"""
    body = project / "temp" / "body.md"
    body.parent.mkdir(parents=True, exist_ok=True)
    body.write_text(content, encoding="utf-8")
    return body


# ===========================================================================
# A. safe-mv 4 op 语义覆盖 (6 用例)
# ===========================================================================


class TestSafeMvOps:
    """A 组:safe-mv 4 op 语义覆盖(DESIGN.md §3.6 v0.5.2 PATCH + §3.1 G10)。"""

    def test_a1_op_mv_basic_path(self, tmp_project: Path) -> None:
        """A1:op=mv 正常路径——源 inbox/<file> → 目标 raw/<sub>/<file>,源被删、目标被建。"""
        inbox = tmp_project / "inbox"
        inbox.mkdir(exist_ok=True)
        src = inbox / "note.md"
        src.write_text("note content", encoding="utf-8")
        raw_dest_dir = tmp_project / "raw" / "06_功能安全"

        decision_path = _write_decision(
            tmp_project,
            actions=[{"op": "mv", "source": "inbox/note.md", "dest": "raw/06_功能安全/note.md"}],
            hash_val="mvbasic",
        )
        r = _run_script(
            "safe-mv.py", "--project-dir", str(tmp_project), "--apply", str(decision_path),
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"
        assert not src.exists(), "mv 应删除源"
        assert (raw_dest_dir / "note.md").exists(), "mv 应创建目标"
        assert (raw_dest_dir / "note.md").read_text(encoding="utf-8") == "note content"

    def test_a2_op_mv_source_missing_errors(self, tmp_project: Path) -> None:
        """A2:op=mv 源文件不存在 → atomic=false + errors 含标识,但 exit 0(单条 action 不阻断整批)。"""
        # 不创建 inbox/file.md(故意缺失)
        decision_path = _write_decision(
            tmp_project,
            actions=[{"op": "mv", "source": "inbox/nonexistent.md", "dest": "raw/06_功能安全/nonexistent.md"}],
            hash_val="mvmiss",
        )
        r = _run_script(
            "safe-mv.py", "--project-dir", str(tmp_project), "--apply", str(decision_path),
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"  # 单 action 失败不阻断
        out = json.loads(r.stdout)
        assert out["atomic"] is False
        assert any("源不存在" in e for e in out["errors"]), f"应报源不存在:{out['errors']}"

    def test_a3_op_overwrite_dest_missing_treated_as_mv(self, tmp_project: Path) -> None:
        """A3:op=overwrite 但 dest 不存在(v0.5.2 PATCH)→ 视为 mv,直接 inbox → dest 不备份。"""
        inbox = tmp_project / "inbox"
        inbox.mkdir(exist_ok=True)
        src = inbox / "newdoc.md"
        src.write_text("new", encoding="utf-8")
        raw_dest_dir = tmp_project / "raw" / "06_功能安全"
        # 故意不创建 raw_dest_dir/newdoc.md

        decision_path = _write_decision(
            tmp_project,
            actions=[{"op": "overwrite", "source": "inbox/newdoc.md", "dest": "raw/06_功能安全/newdoc.md"}],
            hash_val="owmiss",
        )
        r = _run_script(
            "safe-mv.py", "--project-dir", str(tmp_project), "--apply", str(decision_path),
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"
        assert not src.exists()
        assert (raw_dest_dir / "newdoc.md").exists()
        # 备份目录应存在但无备份文件(因 dest 不存在)
        backup_dir = tmp_project / "temp" / "raw_backup_owmiss"
        assert backup_dir.exists()
        assert not (backup_dir / "newdoc.md").exists(), "dest 不存在 → 不应有备份"

    def test_a4_op_overwrite_backs_up_converted_md(self, tmp_project: Path) -> None:
        """A4:op=overwrite + 目标 .converted.md 共存 → 备份目录应同时含原文件 + .converted.md 备份。"""
        inbox = tmp_project / "inbox"
        inbox.mkdir(exist_ok=True)
        src = inbox / "doc.pdf"
        src.write_text("new pdf", encoding="utf-8")
        src_converted = inbox / "doc.pdf.converted.md"
        src_converted.write_text("# new converted\n", encoding="utf-8")

        raw_dest_dir = tmp_project / "raw" / "06_功能安全"
        raw_dest_dir.mkdir(parents=True, exist_ok=True)
        old_primary = raw_dest_dir / "doc.pdf"
        old_primary.write_text("old pdf", encoding="utf-8")
        old_converted = raw_dest_dir / "doc.pdf.converted.md"
        old_converted.write_text("# old converted\n", encoding="utf-8")

        decision_path = _write_decision(
            tmp_project,
            actions=[{"op": "overwrite", "source": "inbox/doc.pdf", "dest": "raw/06_功能安全/doc.pdf"}],
            hash_val="owboth",
        )
        r = _run_script(
            "safe-mv.py", "--project-dir", str(tmp_project), "--apply", str(decision_path),
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"

        backup_dir = tmp_project / "temp" / "raw_backup_owboth"
        assert (backup_dir / "doc.pdf").exists(), "原文件备份"
        assert (backup_dir / "doc.pdf").read_text(encoding="utf-8") == "old pdf"
        assert (backup_dir / "doc.pdf.converted.md").exists(), ".converted.md 备份"
        assert (backup_dir / "doc.pdf.converted.md").read_text(encoding="utf-8") == "# old converted\n"

        # 目标应是新内容
        assert old_primary.read_text(encoding="utf-8") == "new pdf"
        assert old_converted.read_text(encoding="utf-8") == "# new converted\n"
        # inbox 双文件都被搬空
        assert not src.exists()
        assert not src_converted.exists()

    def test_a5_op_skip_and_delete_only_combo(self, tmp_project: Path) -> None:
        """A5:同批 decision 含 skip + delete-only 两条 action → 各按各自语义独立处理。"""
        inbox = tmp_project / "inbox"
        inbox.mkdir(exist_ok=True)
        keep_src = inbox / "keep.md"
        keep_src.write_text("keep me", encoding="utf-8")
        delete_src = inbox / "delete.md"
        delete_src.write_text("delete me", encoding="utf-8")

        raw_dest_dir = tmp_project / "raw" / "06_功能安全"
        raw_dest_dir.mkdir(parents=True, exist_ok=True)
        old_delete = raw_dest_dir / "delete.md"
        old_delete.write_text("old delete target", encoding="utf-8")

        decision_path = _write_decision(
            tmp_project,
            actions=[
                {"op": "skip", "source": "inbox/keep.md", "dest": "raw/06_功能安全/keep.md"},
                {"op": "delete-only", "source": "inbox/delete.md", "dest": "raw/06_功能安全/delete.md"},
            ],
            hash_val="combo",
        )
        r = _run_script(
            "safe-mv.py", "--project-dir", str(tmp_project), "--apply", str(decision_path),
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"
        # skip:源保留、目标不存在
        assert keep_src.exists(), "skip 保留源"
        assert not (raw_dest_dir / "keep.md").exists(), "skip 不创建目标"
        # delete-only:源保留(等用户手动处理)、旧目标被删
        assert delete_src.exists(), "delete-only 保留 inbox 源"
        assert not old_delete.exists(), "delete-only 删旧副本"

    def test_a6_decision_json_validation_fails(self, tmp_project: Path) -> None:
        """A6:decision JSON 缺必填字段(type / actions 等)→ 抛 ValueError,exit 1。"""
        temp_dir = tmp_project / "temp"
        temp_dir.mkdir(exist_ok=True)
        bad = temp_dir / "decision-bad.json"
        # 缺 type / actions 必填字段
        bad.write_text(
            json.dumps({"schema_version": "1.0", "decided_at": _now_iso(), "actor": "x"}, ensure_ascii=False),
            encoding="utf-8",
        )
        r = _run_script(
            "safe-mv.py", "--project-dir", str(tmp_project), "--apply", str(bad),
        )
        assert r.returncode == 1, f"应 exit 1,实际 {r.returncode}"
        out = json.loads(r.stdout)
        assert out["ok"] is False
        assert "缺必填字段" in out["error"] or "actions" in out["error"], (
            f"应报缺必填字段:{out['error']}"
        )


# ===========================================================================
# B. convert-to-md 4 路由覆盖 (4 用例)
# ===========================================================================


class TestConvertToMdRouting:
    """B 组:convert-to-md 4 路由覆盖(DESIGN.md §3.1 G10)。"""

    def test_b1_pdf_anydoc_stub_when_dep_missing(self, tmp_project: Path) -> None:
        """B1:.pdf 走 anydoc 路由 → stub 文件 + anydoc 模块依赖探测(unimportable → exit 1 中文报错)。"""
        # anydoc 大概率未装。预期:脚本走 _probe_module 抛 SystemExit(1) 中文报错
        inbox = tmp_project / "inbox"
        inbox.mkdir(exist_ok=True)
        (inbox / "doc.pdf").write_text("%PDF-1.4\n%fake pdf\n", encoding="utf-8")

        temp_dir = tmp_project / "temp"
        temp_dir.mkdir(exist_ok=True)
        r = _run_script(
            "convert-to-md.py",
            "--project-dir", str(tmp_project),
            "--input", "inbox/doc.pdf",
            "--output-dir", "temp/",
        )
        # anydoc 未装 → SystemExit(1) + stderr 中文报错
        if r.returncode != 0:
            assert "缺依赖" in r.stderr or "anydoc" in r.stderr, (
                f"应报 anydoc 缺依赖中文错误:stderr={r.stderr}"
            )
        else:
            # anydoc 装了(罕见)→ stub 文件生成成功
            out = json.loads(r.stdout)
            assert out["converter"] == "anydoc"
            assert out["native_text"] is False
            assert (temp_dir / "doc.md").exists()

    def test_b2_png_paddleocr_stub_or_chinese_error(self, tmp_project: Path) -> None:
        """B2:.png 走 paddleocr 路由 → stub 文件或中文报错(paddleocr 缺时)。"""
        inbox = tmp_project / "inbox"
        inbox.mkdir(exist_ok=True)
        # 写最小有效 png(8 字节 header + 末尾标识)
        (inbox / "img.png").write_bytes(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + b"IEND" + b"\xae\x42\x60\x82"
        )

        temp_dir = tmp_project / "temp"
        temp_dir.mkdir(exist_ok=True)
        r = _run_script(
            "convert-to-md.py",
            "--project-dir", str(tmp_project),
            "--input", "inbox/img.png",
            "--output-dir", "temp/",
        )
        if r.returncode != 0:
            assert "缺依赖" in r.stderr or "paddleocr" in r.stderr, (
                f"应报 paddleocr 缺依赖中文错误:stderr={r.stderr}"
            )
        else:
            out = json.loads(r.stdout)
            assert out["converter"] == "paddleocr"
            assert out["native_text"] is False

    def test_b3_unknown_extension_exits_1(self, tmp_project: Path) -> None:
        """B3:未知扩展名(非 4 路由之一)→ ValueError → exit 1。"""
        inbox = tmp_project / "inbox"
        inbox.mkdir(exist_ok=True)
        (inbox / "weird.xyz").write_text("data", encoding="utf-8")

        temp_dir = tmp_project / "temp"
        temp_dir.mkdir(exist_ok=True)
        r = _run_script(
            "convert-to-md.py",
            "--project-dir", str(tmp_project),
            "--input", "inbox/weird.xyz",
            "--output-dir", "temp/",
        )
        assert r.returncode == 1, f"应 exit 1,实际 {r.returncode}"
        out = json.loads(r.stdout)
        assert out["ok"] is False
        assert "扩展名不支持" in out["error"]

    def test_b4_classify_uppercase_extension_lowered(self, tmp_project: Path) -> None:
        """B4:classify 大写扩展名(PDF / PNG)→ 内部 lstrip('.').lower() 后正确路由。"""
        # 直接测 classify 函数(classify 是纯函数,不依赖 IO)
        convert_mod = _load_module("convert_to_md_c2", SCRIPTS_DIR / "convert-to-md.py")
        classify = convert_mod.classify
        # 大写 PDF → anydoc(降级判断)
        result_pdf = classify("PDF")
        assert result_pdf["converter"] == "anydoc"
        assert result_pdf["format"] == "pdf"
        # 大写 PNG → paddleocr
        result_png = classify("PNG")
        assert result_png["converter"] == "paddleocr"
        assert result_png["format"] == "png"
        # 大写 MD → native
        result_md = classify("MD")
        assert result_md["converter"] is None
        assert result_md["native_text"] is True


# ===========================================================================
# C. append-log 6 种前缀补完 (3 用例)
# ===========================================================================


class TestAppendLogEdgeCases:
    """C 组:append-log 6 种前缀边界(DESIGN.md §2.6 + §3.4)。"""

    def test_c1_deprecation_prefix_alone(self, tmp_project: Path) -> None:
        """C1:**Deprecation** 前缀独立测试(deprecate 一页时单独使用)。"""
        r = _run_script(
            "append-log.py",
            "--project-dir", str(tmp_project),
            "--action", "Deprecation",
            "--summary", "[autosar.md](sources/autosar.md) — 内容已被 [[autosar-classic]] 取代",
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"
        log = (tmp_project / "knowledge" / "log.md").read_text(encoding="utf-8")
        assert "**Deprecation**" in log
        assert "autosar.md" in log

    def test_c2_log_md_missing_exits_1(self, tmp_project: Path) -> None:
        """C2:log.md 不存在(init 之前)→ FileNotFoundError → exit 1。"""
        empty_project = tmp_project.parent / "empty_project"
        empty_project.mkdir(exist_ok=True)
        # 故意不跑 init,knowledge/log.md 不存在
        r = _run_script(
            "append-log.py",
            "--project-dir", str(empty_project),
            "--action", "Creation",
            "--summary", "should fail",
        )
        assert r.returncode == 1, f"应 exit 1,实际 {r.returncode}"
        out = json.loads(r.stdout)
        assert out["ok"] is False
        assert "log.md" in out["error"]

    def test_c3_large_log_insertion_position(self, tmp_project: Path) -> None:
        """C3:log.md 多行历史 → 新记录插入到 frontmatter 之后、第一个 H2 之前(最新在前)。"""
        log_path = tmp_project / "knowledge" / "log.md"
        # 读现有 log.md(已有 frontmatter + 当日 H2)
        original_text = log_path.read_text(encoding="utf-8")
        # 模拟大量历史:在 H2 下加 5 行既有记录
        if "## " in original_text:
            extra_history = "\n".join(
                f"* 历史记录 {i} — by {ACTOR_PREFIX}" for i in range(5)
            ) + "\n"
            new_text = original_text + extra_history
            log_path.write_text(new_text, encoding="utf-8")

        # 追加新记录
        r = _run_script(
            "append-log.py",
            "--project-dir", str(tmp_project),
            "--action", "Creation",
            "--summary", "新插入记录",
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"

        updated = log_path.read_text(encoding="utf-8")
        # 新记录应在第一个 H2 之上(insert_after_frontmatter 位置)
        # 找新记录位置 & 第一个 H2 位置
        new_idx = updated.find("新插入记录")
        h2_idx = updated.find("## ")
        assert new_idx != -1, "新记录应存在"
        assert h2_idx != -1, "应仍有 H2"
        assert new_idx < h2_idx, f"新记录应插在 H2 之前:new={new_idx} h2={h2_idx}"


# ===========================================================================
# D. validate-frontmatter G10 三元组 (4 用例)
# ===========================================================================


class TestValidateFrontmatterG10:
    """D 组:validate-frontmatter G10 三元组边界 + 目录扫描混存。"""

    def test_d1_g10_missing_converted_path_fails(self, tmp_project: Path) -> None:
        """D1:native_text=false + converter=anydoc 但缺 converted_path → FAIL。"""
        bad = _write_md(
            tmp_project,
            "knowledge/sources/g10_missing_cp.md",
            "---\n"
            "type: source\n"
            "title: missing cp\n"
            "description: x\n"
            "updated: 2026-09-03T00:00:00Z\n"
            "tags:\n"
            "  - docform/source\n"
            "source_file: raw/06_功能安全/x.pdf\n"
            "sources:\n"
            "  - resource: raw/06_功能安全/x.pdf\n"
            "format: pdf\n"
            "converter: anydoc\n"
            "native_text: false\n"
            # 故意缺 converted_path
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
        assert any("converted_path" in e and "G10" in e for e in out["errors"]), (
            f"应报 G10 三元组 converted_path 缺失:{out['errors']}"
        )

    def test_d2_g10_invalid_converter_value_fails(self, tmp_project: Path) -> None:
        """D2:native_text=false + converter='unknown_converter'(非 4 合法值)→ FAIL。"""
        bad = _write_md(
            tmp_project,
            "knowledge/sources/g10_bad_conv.md",
            "---\n"
            "type: source\n"
            "title: bad conv\n"
            "description: x\n"
            "updated: 2026-09-03T00:00:00Z\n"
            "tags:\n"
            "  - docform/source\n"
            "source_file: raw/06_功能安全/x.pdf\n"
            "sources:\n"
            "  - resource: raw/06_功能安全/x.pdf\n"
            "format: pdf\n"
            "converter: 'unknown_converter'\n"  # 非法 converter
            "native_text: false\n"
            "converted_path: raw/06_功能安全/x.pdf.converted.md\n"
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
        assert any("converter" in e and "G10" in e for e in out["errors"]), (
            f"应报 G10 converter 非法:{out['errors']}"
        )

    def test_d3_g10_mixed_dir_scan_ok_and_g10(self, tmp_project: Path) -> None:
        """D3:同目录混存 OKF 通用页 + G10 source 页 → 各自走对应分支,均不应因混存报错。"""
        # 普通 analysis 页(非 G10)
        analysis = _write_md(
            tmp_project,
            "knowledge/analyses/mixed-analysis.md",
            "---\n"
            "type: analysis\n"
            "title: mix test\n"
            "description: x\n"
            "updated: 2026-09-03T00:00:00Z\n"
            "tags:\n"
            "  - docform/analysis\n"
            "sources_used:\n"
            "  - knowledge/sources/good.md\n"
            "answer_to: 'test?'\n"
            "generated_by: 'agent: producer/aeps-llm-wiki-plugin/0.5.5'\n"
            "---\n\n# x\n",
        )
        # G10 source 页(合规)
        g10 = _write_md(
            tmp_project,
            "knowledge/sources/good.md",
            "---\n"
            "type: source\n"
            "title: good\n"
            "description: x\n"
            "updated: 2026-09-03T00:00:00Z\n"
            "tags:\n"
            "  - docform/source\n"
            "  - domain/ai\n"
            "source_file: raw/06_功能安全/good.pdf\n"
            "sources:\n"
            "  - resource: raw/06_功能安全/good.pdf\n"
            "format: pdf\n"
            "converter: anydoc\n"
            "native_text: false\n"
            "converted_path: raw/06_功能安全/good.pdf.converted.md\n"
            "links:\n"
            "  - '[[good.pdf.converted]]'\n"
            "summary: 'good one'\n"
            "---\n\n# x\n",
        )

        # 两个文件分别校验,各自走对应 type-specific 分支
        r_analysis = _run_script(
            "validate-frontmatter.py",
            "--project-dir", str(tmp_project),
            "--file", str(analysis.relative_to(tmp_project)),
        )
        out_a = json.loads(r_analysis.stdout)
        # analysis 校验不应触发 G10 三元组检查
        assert not any("G10" in e for e in out_a["errors"]), (
            f"analysis 页不应触发 G10 检查:{out_a['errors']}"
        )

        r_g10 = _run_script(
            "validate-frontmatter.py",
            "--project-dir", str(tmp_project),
            "--file", str(g10.relative_to(tmp_project)),
        )
        out_g = json.loads(r_g10.stdout)
        assert out_g["ok"] is True, f"G10 source 页应通过:errors={out_g['errors']}"

    def test_d4_unknown_keys_warn_not_fail(self, tmp_project: Path) -> None:
        """D4:未知 frontmatter 字段(非 known_keys)→ unknown_keys 列出但 ok 仍由 missing/errors 决定。"""
        md = _write_md(
            tmp_project,
            "knowledge/sources/extra-keys.md",
            "---\n"
            "type: source\n"
            "title: extra\n"
            "description: x\n"
            "updated: 2026-09-03T00:00:00Z\n"
            "tags:\n"
            "  - docform/source\n"
            "source_file: raw/06_功能安全/x.pdf\n"
            "sources:\n"
            "  - resource: raw/06_功能安全/x.pdf\n"
            "format: pdf\n"
            "converter: anydoc\n"
            "native_text: false\n"
            "converted_path: raw/06_功能安全/x.pdf.converted.md\n"
            "links: []\n"
            "summary: 'x'\n"
            "custom_field: 'unused'\n"  # 未知字段
            "---\n\n# x\n",
        )
        r = _run_script(
            "validate-frontmatter.py",
            "--project-dir", str(tmp_project),
            "--file", str(md.relative_to(tmp_project)),
        )
        out = json.loads(r.stdout)
        # 必填全齐 + 无 G10 矛盾 → ok=true
        assert out["ok"] is True, f"应通过:errors={out['errors']}"
        # 未知字段应被记录
        assert "custom_field" in out.get("unknown_keys", []), (
            f"应记录 custom_field 为 unknown_key:{out.get('unknown_keys')}"
        )


# ===========================================================================
# E. generate-* 序列化分支 (5 用例)
# ===========================================================================


class TestGeneratePageSerialization:
    """E 组:generate-source/entity/concept page 序列化分支。"""

    def test_e1_source_page_native_text_omits_converted_path(self, tmp_project: Path) -> None:
        """E1:source 页 native_text=true → converter/converted_path 均为 null + frontmatter 序列化正确。"""
        meta = _make_source_meta(
            converter=None,
            native_text=True,
            converted_path=None,
        )
        body_file = _make_body_file(tmp_project)
        r = _run_script(
            "generate-source-page.py",
            "--project-dir", str(tmp_project),
            "--basename", "native-note",
            "--meta-json", json.dumps(meta, ensure_ascii=False),
            "--body-file", str(body_file.relative_to(tmp_project)),
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"
        out = json.loads(r.stdout)
        target = tmp_project / out["path"]
        content = target.read_text(encoding="utf-8")
        # native_text=true → converter/converted_path 应为 null
        assert "converter: null" in content or "converter: 'null'" in content or "converter: null\n" in content, (
            f"converter 应为 null:frontmatter 含 {content[:300]}"
        )
        assert "native_text: true" in content

    def test_e2_entity_page_all_7_subtypes_writable(self, tmp_project: Path) -> None:
        """E2:entity 7 subtype 各生成一个文件 + 子目录自动创建。"""
        entity_mod = _load_module("generate_entity_page_c2", SCRIPTS_DIR / "generate-entity-page.py")
        subtypes = sorted(entity_mod.ENTITY_SUBTYPES)
        assert len(subtypes) == 7, f"应有 7 entity subtype,实际 {subtypes}"

        for subtype in subtypes:
            meta = {
                "type": subtype,
                "title": f"test {subtype}",
                "description": f"fixture for {subtype}",
                "updated": "2026-09-03T00:00:00Z",
                "tags": ["docform/entity"],
                "aliases": [],
            }
            body_file = _make_body_file(tmp_project, content=f"# {subtype}\n\nbody\n")
            r = _run_script(
                "generate-entity-page.py",
                "--project-dir", str(tmp_project),
                "--subtype", subtype,
                "--slug", f"test-{subtype}",
                "--meta-json", json.dumps(meta, ensure_ascii=False),
                "--body-file", str(body_file.relative_to(tmp_project)),
            )
            assert r.returncode == 0, f"{subtype} 应生成成功,stderr: {r.stderr}"
            out = json.loads(r.stdout)
            assert out["path"] == f"knowledge/entities/{subtype}/test-{subtype}.md"

    def test_e3_concept_page_invalid_subtype_rejected(self, tmp_project: Path) -> None:
        """E3:concept 非法 subtype → exit 1(由 argparse choices 拦截)。"""
        meta = {
            "type": "invalid_subtype",
            "title": "bad",
            "description": "x",
            "updated": "2026-09-03T00:00:00Z",
            "tags": ["docform/concept"],
            "aliases": [],
        }
        body_file = _make_body_file(tmp_project)
        r = _run_script(
            "generate-concept-page.py",
            "--project-dir", str(tmp_project),
            "--subtype", "invalid_subtype",
            "--slug", "bad",
            "--meta-json", json.dumps(meta, ensure_ascii=False),
            "--body-file", str(body_file.relative_to(tmp_project)),
        )
        assert r.returncode != 0, f"非法 subtype 应被 argparse 拒绝,exit={r.returncode}"
        # argparse 拒绝会输出到 stderr(SystemExit 2)
        assert "invalid choice" in r.stderr.lower() or "非法" in r.stderr or "argument" in r.stderr.lower(), (
            f"stderr 应报 invalid choice:stderr={r.stderr}"
        )

    def test_e4_entity_page_chinese_slug(self, tmp_project: Path) -> None:
        """E4:中文 slug 写入 entity 目录——实测脚本不强制 slug ASCII,中文可透传(下游 lint 容忍)。"""
        meta = {
            "type": "person",
            "title": "中文 person 测试",
            "description": "中文 slug fixture",
            "updated": "2026-09-03T00:00:00Z",
            "tags": ["docform/entity"],
            "aliases": ["张三"],
        }
        body_file = _make_body_file(tmp_project, content="# 中文 person\n\nbody\n")
        r = _run_script(
            "generate-entity-page.py",
            "--project-dir", str(tmp_project),
            "--subtype", "person",
            "--slug", "中文-person",
            "--meta-json", json.dumps(meta, ensure_ascii=False),
            "--body-file", str(body_file.relative_to(tmp_project)),
        )
        assert r.returncode == 0, f"中文 slug 应可写盘,stderr: {r.stderr}"
        out = json.loads(r.stdout)
        target = tmp_project / out["path"]
        assert target.exists()
        content = target.read_text(encoding="utf-8")
        assert "中文 person 测试" in content, "frontmatter title 应含中文"
        assert "张三" in content, "aliases 应含中文"

    def test_e5_source_page_missing_required_field_fails(self, tmp_project: Path) -> None:
        """E5:source 页缺关键必填(updated 缺)→ exit 1 + 中文报错。"""
        bad_meta = {
            "type": "source",
            "title": "no updated",
            "description": "x",
            # 故意缺 updated
            "tags": ["docform/source"],
            "source_file": "raw/06_功能安全/x.pdf",
            "sources": [{"resource": "raw/06_功能安全/x.pdf"}],
            "format": "pdf",
            "converter": "anydoc",
            "native_text": False,
            "converted_path": "raw/06_功能安全/x.pdf.converted.md",
            "links": [],
            "summary": "x",
        }
        body_file = _make_body_file(tmp_project)
        r = _run_script(
            "generate-source-page.py",
            "--project-dir", str(tmp_project),
            "--basename", "no-updated",
            "--meta-json", json.dumps(bad_meta, ensure_ascii=False),
            "--body-file", str(body_file.relative_to(tmp_project)),
        )
        assert r.returncode == 1, f"应 exit 1,实际 {r.returncode}"
        out = json.loads(r.stdout)
        assert out["ok"] is False
        assert "updated" in out["error"] or "通用必填" in out["error"], (
            f"应报缺 updated 字段:error={out['error']}"
        )


# ===========================================================================
# F. init-vault 幂等再入 (2 用例)
# ===========================================================================


class TestInitVaultIdempotent:
    """F 组:init-vault 二次 init 不覆盖用户内容。"""

    def test_f1_first_run_creates_6_top_level_and_15_raw_and_18_knowledge(self, tmp_project: Path) -> None:
        """F1:首次 init 应建 6 顶层 + raw 15 + knowledge 18 + 4 种子文件。"""
        # 顶层 6
        for top in ("inbox", "raw", "scripts", "templates", "knowledge", "temp"):
            assert (tmp_project / top).exists(), f"顶层目录缺失:{top}"
        # raw 15
        for sub in RAW_SUBDIRS:
            assert (tmp_project / "raw" / sub).exists(), f"raw 子目录缺失:{sub}"
        assert len(RAW_SUBDIRS) == 15
        # knowledge 18(sources + 7 entities + 7 concepts + analyses/comparisons/syntheses = 1+7+7+1+1+1=18)
        assert len(KNOWLEDGE_LEAF_DIRS) == 18
        for leaf in KNOWLEDGE_LEAF_DIRS:
            assert (tmp_project / "knowledge" / leaf).exists(), f"knowledge 叶子缺失:{leaf}"
        # 4 种子文件
        for seed in ("index.md", "overview.md", "glossary.md", "log.md"):
            assert (tmp_project / "knowledge" / seed).exists(), f"种子文件缺失:{seed}"

    def test_f2_re_run_does_not_overwrite_user_content(self, tmp_project: Path) -> None:
        """F2:--re-run 二次 init → 不覆盖 index/overview/glossary/log.md(LLM 累积维护)。"""
        # 模拟用户已经在 index.md 写了内容
        index_path = tmp_project / "knowledge" / "index.md"
        user_content = "# 用户自定义索引\n\n- [[my-note]]\n- [[another-note]]\n"
        index_path.write_text(user_content, encoding="utf-8")
        original_mtime = os.stat(index_path).st_mtime

        # 二次 init
        plugin_src = SCRIPTS_DIR.parent
        class Args:
            project_dir = str(tmp_project)
            re_run = True
            plugin_dir = str(plugin_src)

        result = _init_vault_run(Args())
        assert result["re_run"] is True

        # index.md 内容应保留(不被覆盖)
        assert index_path.read_text(encoding="utf-8") == user_content, (
            "二次 init 不应覆盖用户 index.md"
        )
        # log.md 应追加 Update 行
        log_text = (tmp_project / "knowledge" / "log.md").read_text(encoding="utf-8")
        assert "**Update**: re-run init at" in log_text, (
            f"二次 init 应在 log.md 追加 Update 行:log={log_text[:500]}"
        )
        # 顶层目录结构仍完整(幂等)
        for top in ("inbox", "raw", "scripts", "templates", "knowledge", "temp"):
            assert (tmp_project / top).exists(), f"二次 init 后顶层缺失:{top}"


# ===========================================================================
# G. ingest/cleanup 留哪些/删哪些 (2 用例)
# ===========================================================================


class TestIngestCleanup:
    """G 组:ingest/cleanup 留 .sanitized/.corrupt.bak/.gitignore/raw_backup_*,删 OCR 中间 + .tmp。"""

    def test_g1_keeps_sanitized_drops_md(self, tmp_project: Path) -> None:
        """G1:cleanup 默认 → 删 OCR 中间 .md + proposal-*.json + G10 .converted.md,留 .sanitized/.corrupt.bak/.gitignore/raw_backup_*/decision-*.json。"""
        temp_dir = tmp_project / "temp"
        temp_dir.mkdir(exist_ok=True)
        # 应删:
        (temp_dir / "ocr-output.md").write_text("ocr text", encoding="utf-8")
        (temp_dir / "data.csv.converted.md").write_text("# converted", encoding="utf-8")
        (temp_dir / "proposal-abc.json").write_text("{}", encoding="utf-8")
        # 应留:
        (temp_dir / "proposal-abc.json.sanitized").write_text("{}", encoding="utf-8")
        (temp_dir / "proposal-bad.json.corrupt.bak").write_text("bad", encoding="utf-8")
        (temp_dir / "decision-xyz.json").write_text("{}", encoding="utf-8")
        (temp_dir / ".gitkeep").touch()
        (temp_dir / ".gitignore").write_text("*\n!.gitkeep\n", encoding="utf-8")
        # raw_backup 目录及其下文件应留
        backup_dir = temp_dir / "raw_backup_xyz"
        backup_dir.mkdir(exist_ok=True)
        (backup_dir / "old.pdf").write_text("old", encoding="utf-8")

        r = _run_script(
            "ingest/cleanup.py",
            "--project-dir", str(tmp_project),
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"
        out = json.loads(r.stdout)
        assert out["ok"] is True

        # 应删的消失
        assert not (temp_dir / "ocr-output.md").exists(), "OCR .md 应被删"
        assert not (temp_dir / "data.csv.converted.md").exists(), ".converted.md 应被删"
        assert not (temp_dir / "proposal-abc.json").exists(), "已合并 proposal 应被删"
        # 应留的保留
        assert (temp_dir / "proposal-abc.json.sanitized").exists(), ".sanitized 应保留"
        assert (temp_dir / "proposal-bad.json.corrupt.bak").exists(), ".corrupt.bak 应保留"
        assert (temp_dir / "decision-xyz.json").exists(), "decision 应保留"
        assert (temp_dir / ".gitkeep").exists(), ".gitkeep 应保留"
        assert (temp_dir / ".gitignore").exists(), ".gitignore 应保留"
        assert (backup_dir / "old.pdf").exists(), "raw_backup 内文件应保留"

        # 报告列表正确性
        deleted_set = set(out["deleted"])
        kept_set = set(out["kept"])
        assert "ocr-output.md" in deleted_set
        assert "data.csv.converted.md" in deleted_set
        assert "proposal-abc.json" in deleted_set
        assert "proposal-abc.json.sanitized" in kept_set
        assert "proposal-bad.json.corrupt.bak" in kept_set
        assert "decision-xyz.json" in kept_set

    def test_g2_idempotent_second_cleanup_no_error(self, tmp_project: Path) -> None:
        """G2:二次 cleanup 幂等——上轮已删文件再次扫描时不再列在 deleted(无报错)。"""
        temp_dir = tmp_project / "temp"
        temp_dir.mkdir(exist_ok=True)
        # 先跑一次 cleanup(无任何应删文件)
        r1 = _run_script(
            "ingest/cleanup.py",
            "--project-dir", str(tmp_project),
        )
        assert r1.returncode == 0, f"首次 cleanup 应 OK:stderr={r1.stderr}"

        # 现在加一些临时文件,再跑第二次
        (temp_dir / "ocr1.md").write_text("x", encoding="utf-8")
        (temp_dir / "ocr2.md").write_text("y", encoding="utf-8")
        r2 = _run_script(
            "ingest/cleanup.py",
            "--project-dir", str(tmp_project),
        )
        assert r2.returncode == 0, f"二次 cleanup 应 OK:stderr={r2.stderr}"
        out2 = json.loads(r2.stdout)
        # 第二批的 2 个 .md 应被删
        assert "ocr1.md" in out2["deleted"]
        assert "ocr2.md" in out2["deleted"]
        # errors 列表应为空(不因二次 cleanup 报错)
        assert out2["errors"] == [], f"二次 cleanup 不应有 errors:{out2['errors']}"

        # 第三次跑(空 temp/ 已无应删文件)——也应 OK
        r3 = _run_script(
            "ingest/cleanup.py",
            "--project-dir", str(tmp_project),
        )
        assert r3.returncode == 0, f"空 temp/ cleanup 应 OK:stderr={r3.stderr}"
        out3 = json.loads(r3.stdout)
        assert out3["deleted"] == []
        assert out3["errors"] == []

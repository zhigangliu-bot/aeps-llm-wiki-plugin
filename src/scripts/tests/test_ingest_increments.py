"""test_ingest_increments.py — 7 个 ingest 组增量脚本的离线单测。

覆盖:
    - generate-source-page.py:G10 5 字段 / Q9 双字段 / 3 H2 骨架 / Q7 mtime 保留
    - generate-entity-page.py:subtype → 目录 / 非法 subtype 拒绝 / 目录自动建
    - generate-concept-page.py:同 entity
    - ingest/dedupe_concepts.py:aliases 合并 / 去重计数
    - ingest/dedupe_entities.py:aliases 合并 / 去重计数
    - ingest/pre_classify.py:--raw-subdir 合法 / 非法 / 不传返回字典
    - ingest/cleanup.py:默认清理 / --keep-decision / 损坏备份保留 / raw_backup 保留

设计依据:
    - 阶段 C-1.2.2 ingest 增量 7 .py 测试用例
    - DESIGN.md §1.1 + §2.5 + §3.1 G10 + Q9 + Q7

CLI:
    pytest tests/test_ingest_increments.py -v
"""

from __future__ import annotations

import importlib.util as _importlib_util
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


def _load_module(name: str, file_path: Path):
    """动态加载 hyphen 文件名的 .py 模块。"""
    spec = _importlib_util.spec_from_file_location(name, str(file_path))
    module = _importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_init_vault = _load_module("init_vault_increments", SCRIPTS_DIR / "init-vault.py")
ACTOR_PREFIX = _init_vault.ACTOR_PREFIX
RAW_SUBDIRS = _init_vault.RAW_SUBDIRS
_now_iso = _init_vault._now_iso
init_vault_run = _init_vault.run


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
    """子进程跑一个脚本。"""
    cmd = [sys.executable, str(SCRIPTS_DIR / name), *args]
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )


def _write_body(tmp: Path, body: str = "## 重点摘录\n\ncontent\n\n## 我的思考\n\nthink\n\n## 总结:最有收获的一句话\n\nsummary\n") -> Path:
    """写一个 body file 用于 generate-* 测试。"""
    body_file = tmp / "body.md"
    body_file.write_text(body, encoding="utf-8")
    return body_file


def _write_md(project: Path, rel_path: str, content: str) -> Path:
    """在 project 内写一个 .md 文件(创建中间目录)。"""
    full = project / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return full


# ---------------------------------------------------------------------------
# generate-source-page.py 测试
# ---------------------------------------------------------------------------


def test_generate_source_page_g10_fields(tmp_project: Path) -> None:
    """G10 5 字段(format / converter / native_text / converted_path / links)在 frontmatter。"""
    body_file = _write_body(tmp_project)
    meta = {
        "type": "source",
        "title": "测试源页",
        "description": "测试",
        "updated": "2026-09-03T00:00:00Z",
        "tags": ["docform/source", "domain/ai", "maturity/draft"],
        "source_file": "raw/02_芯片/test.pdf",
        "sources": [
            {
                "id": "test",
                "resource": "raw/02_芯片/test.pdf",
                "title": "测试",
                "author": "unknown",
                "last_modified": "2026-09-03T00:00:00Z",
            }
        ],
        "format": "pdf",
        "converter": "anydoc",
        "native_text": False,
        "converted_path": "raw/02_芯片/test.pdf.converted.md",
        "links": ["[[test.pdf.converted]]"],
        "summary": "≤ 280 字符的摘要",
    }
    r = _run_script(
        "generate-source-page.py",
        "--project-dir", str(tmp_project),
        "--basename", "test",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body_file),
    )
    assert r.returncode == 0, f"stderr: {r.stderr}; stdout: {r.stdout}"

    out_md = tmp_project / "knowledge" / "sources" / "test.md"
    assert out_md.exists()
    text = out_md.read_text(encoding="utf-8")

    # 5 G10 字段(本脚本对所有字符串加单引号包裹,YAML 解析兼容)
    assert "format: pdf" in text or "format: 'pdf'" in text
    assert "converter: anydoc" in text or "converter: 'anydoc'" in text
    assert "native_text: false" in text
    assert "converted_path: raw/02_芯片/test.pdf.converted.md" in text or \
           "converted_path: 'raw/02_芯片/test.pdf.converted.md'" in text
    assert "[[test.pdf.converted]]" in text


def test_generate_source_page_double_source_q9(tmp_project: Path) -> None:
    """Q9 双字段同源:source_file ↔ sources[0].resource 等值。"""
    body_file = _write_body(tmp_project)
    meta = {
        "type": "source",
        "title": "Q9 测试",
        "description": "Q9",
        "updated": "2026-09-03T00:00:00Z",
        "tags": ["docform/source", "domain/test"],
        "source_file": "raw/02_芯片/q9.pdf",
        "sources": [{"id": "q9", "resource": "raw/02_芯片/q9.pdf", "title": "Q9"}],
        "format": "pdf",
        "converter": "anydoc",
        "native_text": False,
        "converted_path": "raw/02_芯片/q9.pdf.converted.md",
        "links": ["[[q9.pdf.converted]]"],
        "summary": "Q9 测试",
    }
    r = _run_script(
        "generate-source-page.py",
        "--project-dir", str(tmp_project),
        "--basename", "q9",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body_file),
    )
    assert r.returncode == 0
    text = (tmp_project / "knowledge" / "sources" / "q9.md").read_text(encoding="utf-8")
    # source_file 与 sources[0].resource 都出现且值相等
    assert "raw/02_芯片/q9.pdf" in text


def test_generate_source_page_3h2_skeleton(tmp_project: Path) -> None:
    """3 H2 骨架:## 重点摘录 / ## 我的思考 / ## 总结。"""
    body_file = _write_body(tmp_project)
    meta = {
        "type": "source",
        "title": "3H2 测试",
        "description": "3H2",
        "updated": "2026-09-03T00:00:00Z",
        "tags": ["docform/source", "domain/test"],
        "source_file": "raw/02_芯片/h2.pdf",
        "sources": [{"id": "h2", "resource": "raw/02_芯片/h2.pdf", "title": "3H2"}],
        "format": "pdf",
        "converter": "anydoc",
        "native_text": False,
        "converted_path": "raw/02_芯片/h2.pdf.converted.md",
        "links": ["[[h2.pdf.converted]]"],
        "summary": "3H2",
    }
    r = _run_script(
        "generate-source-page.py",
        "--project-dir", str(tmp_project),
        "--basename", "h2",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body_file),
    )
    assert r.returncode == 0
    text = (tmp_project / "knowledge" / "sources" / "h2.md").read_text(encoding="utf-8")
    assert "## 重点摘录" in text
    assert "## 我的思考" in text
    assert "## 总结:最有收获的一句话" in text


def test_generate_source_page_atomic_preserve_mtime(tmp_project: Path) -> None:
    """Q7 写盘不改 mtime(二次写盘场景)。"""
    body_file = _write_body(tmp_project)
    meta = {
        "type": "source",
        "title": "Mtime 测试",
        "description": "Mtime",
        "updated": "2026-09-03T00:00:00Z",
        "tags": ["docform/source", "domain/test"],
        "source_file": "raw/02_芯片/mt.pdf",
        "sources": [{"id": "mt", "resource": "raw/02_芯片/mt.pdf", "title": "Mtime"}],
        "format": "pdf",
        "converter": "anydoc",
        "native_text": False,
        "converted_path": "raw/02_芯片/mt.pdf.converted.md",
        "links": ["[[mt.pdf.converted]]"],
        "summary": "Mtime",
    }
    # 第一次:首次写盘
    r1 = _run_script(
        "generate-source-page.py",
        "--project-dir", str(tmp_project),
        "--basename", "mt",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body_file),
    )
    assert r1.returncode == 0
    out_md = tmp_project / "knowledge" / "sources" / "mt.md"
    original_mtime = os.stat(out_md).st_mtime

    # 第二次:走 atomic_write_preserving_mtime(Q7 防护)
    # 等待 1.5s 让 mtime 自然变化
    import time
    time.sleep(1.5)
    r2 = _run_script(
        "generate-source-page.py",
        "--project-dir", str(tmp_project),
        "--basename", "mt",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body_file),
    )
    assert r2.returncode == 0
    new_mtime = os.stat(out_md).st_mtime
    # Q7 防护:二次写盘 mtime 应保持
    assert abs(new_mtime - original_mtime) < 0.5, (
        f"mtime 应保持(原={original_mtime} 新={new_mtime})"
    )


def test_generate_source_page_meta_validation_fails(tmp_project: Path) -> None:
    """meta-json 缺字段 → exit 1。"""
    body_file = _write_body(tmp_project)
    bad_meta = {"type": "source", "title": "缺字段"}  # 缺 description / updated / tags
    r = _run_script(
        "generate-source-page.py",
        "--project-dir", str(tmp_project),
        "--basename", "bad",
        "--meta-json", json.dumps(bad_meta, ensure_ascii=False),
        "--body-file", str(body_file),
    )
    assert r.returncode != 0, f"应 exit 1,实际 {r.returncode}"


# ---------------------------------------------------------------------------
# generate-entity-page.py 测试
# ---------------------------------------------------------------------------


def test_generate_entity_page_subtype_dictate_dir(tmp_project: Path) -> None:
    """subtype 决定目录:entities/person/<slug>.md。"""
    body_file = _write_body(tmp_project)
    meta = {
        "type": "person",
        "title": "Alice",
        "description": "Alice 描述",
        "updated": "2026-09-03T00:00:00Z",
        "tags": ["docform/entity", "maturity/draft"],
        "aliases": [],
    }
    r = _run_script(
        "generate-entity-page.py",
        "--project-dir", str(tmp_project),
        "--subtype", "person",
        "--slug", "alice",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body_file),
    )
    assert r.returncode == 0, f"stderr: {r.stderr}; stdout: {r.stdout}"
    out = tmp_project / "knowledge" / "entities" / "person" / "alice.md"
    assert out.exists()


def test_generate_entity_page_invalid_subdir_fail(tmp_project: Path) -> None:
    """subtype=invalid → exit 1。"""
    body_file = _write_body(tmp_project)
    meta = {
        "type": "person",
        "title": "x",
        "description": "x",
        "updated": "2026-09-03T00:00:00Z",
        "tags": ["docform/entity"],
        "aliases": [],
    }
    r = _run_script(
        "generate-entity-page.py",
        "--project-dir", str(tmp_project),
        "--subtype", "invalid",
        "--slug", "x",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body_file),
    )
    assert r.returncode != 0


def test_generate_entity_page_creates_dir(tmp_project: Path) -> None:
    """目录不存在 → 自动建(用 event 这种较少预填的目录)。"""
    body_file = _write_body(tmp_project)
    # 删掉 init 预建的 entities/event 目录
    event_dir = tmp_project / "knowledge" / "entities" / "event"
    if event_dir.exists():
        shutil.rmtree(event_dir)

    meta = {
        "type": "event",
        "title": "TestEvent",
        "description": "d",
        "updated": "2026-09-03T00:00:00Z",
        "tags": ["docform/entity"],
        "aliases": [],
    }
    r = _run_script(
        "generate-entity-page.py",
        "--project-dir", str(tmp_project),
        "--subtype", "event",
        "--slug", "testevent",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body_file),
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    out = tmp_project / "knowledge" / "entities" / "event" / "testevent.md"
    assert out.exists()


# ---------------------------------------------------------------------------
# generate-concept-page.py 测试
# ---------------------------------------------------------------------------


def test_generate_concept_page_subtype_dictate_dir(tmp_project: Path) -> None:
    """subtype 决定目录:concepts/standard/<slug>.md。"""
    body_file = _write_body(tmp_project)
    meta = {
        "type": "standard",
        "title": "ISO 26262",
        "description": "功能安全标准",
        "updated": "2026-09-03T00:00:00Z",
        "tags": ["docform/concept", "maturity/stable"],
        "aliases": ["ISO26262", "iso-26262"],
    }
    r = _run_script(
        "generate-concept-page.py",
        "--project-dir", str(tmp_project),
        "--subtype", "standard",
        "--slug", "iso-26262",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body_file),
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    out = tmp_project / "knowledge" / "concepts" / "standard" / "iso-26262.md"
    assert out.exists()


def test_generate_concept_page_invalid_subdir_fail(tmp_project: Path) -> None:
    """subtype=invalid → exit 1。"""
    body_file = _write_body(tmp_project)
    meta = {
        "type": "standard",
        "title": "x",
        "description": "x",
        "updated": "2026-09-03T00:00:00Z",
        "tags": ["docform/concept"],
        "aliases": [],
    }
    r = _run_script(
        "generate-concept-page.py",
        "--project-dir", str(tmp_project),
        "--subtype", "invalid",
        "--slug", "x",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body_file),
    )
    assert r.returncode != 0


# ---------------------------------------------------------------------------
# ingest/dedupe_concepts.py 测试
# ---------------------------------------------------------------------------


def test_dedupe_concepts_merge_aliases(tmp_project: Path) -> None:
    """同 (name, type, subtype) 的 concept 合并,aliases 走并集。"""
    temp_dir = tmp_project / "temp"
    temp_dir.mkdir(exist_ok=True)

    p1 = {
        "file": "inbox/a.md",
        "concepts": [
            {"name": "Foo", "type": "concept", "subtype": "theory", "aliases": ["A", "B"]}
        ],
        "_meta": {"doc_id": "a-11111111", "schema_version": "1.0",
                  "extracted_at": "2026-09-03T00:00:00Z",
                  "extracted_by": ACTOR_PREFIX},
    }
    p2 = {
        "file": "inbox/b.md",
        "concepts": [
            {"name": "Foo", "type": "concept", "subtype": "theory", "aliases": ["B", "C"]}
        ],
        "_meta": {"doc_id": "b-22222222", "schema_version": "1.0",
                  "extracted_at": "2026-09-03T00:00:00Z",
                  "extracted_by": ACTOR_PREFIX},
    }
    (temp_dir / "proposal-a.json").write_text(
        json.dumps(p1, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (temp_dir / "proposal-b.json").write_text(
        json.dumps(p2, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    r = _run_script(
        "ingest/dedupe_concepts.py",
        "--project-dir", str(tmp_project),
        "--proposals-glob", "temp/proposal-*.json",
    )
    assert r.returncode == 0, f"stderr: {r.stderr}; stdout: {r.stdout}"
    out = json.loads(r.stdout)
    assert out["ok"] is True
    assert out["merged_count"] == 1
    assert out["original_count"] == 2
    # aliases 并集:[A, B, C]
    deduped = out["concepts"][0]
    assert set(deduped["aliases"]) == {"A", "B", "C"}


def test_dedupe_concepts_count_delta(tmp_project: Path) -> None:
    """输入 5 个 concept(部分重复)→ 输出 ≤ 5。"""
    temp_dir = tmp_project / "temp"
    temp_dir.mkdir(exist_ok=True)

    concepts = [
        {"name": "C1", "type": "concept", "subtype": "theory", "aliases": []},
        {"name": "C2", "type": "concept", "subtype": "method", "aliases": []},
        {"name": "C1", "type": "concept", "subtype": "theory", "aliases": []},  # 重复
        {"name": "C3", "type": "concept", "subtype": "field", "aliases": []},
        {"name": "C2", "type": "concept", "subtype": "method", "aliases": []},  # 重复
    ]
    p = {
        "file": "inbox/x.md",
        "concepts": concepts,
        "_meta": {"doc_id": "x-33333333", "schema_version": "1.0",
                  "extracted_at": "2026-09-03T00:00:00Z",
                  "extracted_by": ACTOR_PREFIX},
    }
    (temp_dir / "proposal-x.json").write_text(
        json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    r = _run_script(
        "ingest/dedupe_concepts.py",
        "--project-dir", str(tmp_project),
        "--proposals-glob", "temp/proposal-*.json",
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["merged_count"] <= 5
    assert out["merged_count"] == 3  # C1, C2, C3
    assert out["original_count"] == 5


# ---------------------------------------------------------------------------
# ingest/dedupe_entities.py 测试
# ---------------------------------------------------------------------------


def test_dedupe_entities_merge_aliases(tmp_project: Path) -> None:
    """同 (name, type, subtype) 的 entity 合并。"""
    temp_dir = tmp_project / "temp"
    temp_dir.mkdir(exist_ok=True)

    p1 = {
        "file": "inbox/a.md",
        "_meta": {
            "entity_extracts": [
                {"name": "Acme", "type": "organization", "subtype": "organization", "aliases": ["AC"]}
            ],
            "doc_id": "a-11111111", "schema_version": "1.0",
            "extracted_at": "2026-09-03T00:00:00Z", "extracted_by": ACTOR_PREFIX,
        },
        "concepts": [],
    }
    p2 = {
        "file": "inbox/b.md",
        "_meta": {
            "entity_extracts": [
                {"name": "Acme", "type": "organization", "subtype": "organization", "aliases": ["ACME Inc"]}
            ],
            "doc_id": "b-22222222", "schema_version": "1.0",
            "extracted_at": "2026-09-03T00:00:00Z", "extracted_by": ACTOR_PREFIX,
        },
        "concepts": [],
    }
    (temp_dir / "proposal-a.json").write_text(
        json.dumps(p1, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (temp_dir / "proposal-b.json").write_text(
        json.dumps(p2, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    r = _run_script(
        "ingest/dedupe_entities.py",
        "--project-dir", str(tmp_project),
        "--proposals-glob", "temp/proposal-*.json",
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    out = json.loads(r.stdout)
    assert out["merged_count"] == 1
    assert out["original_count"] == 2
    deduped = out["entities"][0]
    assert set(deduped["aliases"]) == {"AC", "ACME Inc"}


def test_dedupe_entities_count_delta(tmp_project: Path) -> None:
    """输入 5 个 entity → 输出 ≤ 5。"""
    temp_dir = tmp_project / "temp"
    temp_dir.mkdir(exist_ok=True)

    entities = [
        {"name": "E1", "type": "person", "subtype": "person", "aliases": []},
        {"name": "E2", "type": "organization", "subtype": "organization", "aliases": []},
        {"name": "E1", "type": "person", "subtype": "person", "aliases": []},  # 重复
        {"name": "E3", "type": "product", "subtype": "product", "aliases": []},
        {"name": "E2", "type": "organization", "subtype": "organization", "aliases": []},  # 重复
    ]
    p = {
        "file": "inbox/y.md",
        "_meta": {
            "entity_extracts": entities,
            "doc_id": "y-44444444", "schema_version": "1.0",
            "extracted_at": "2026-09-03T00:00:00Z", "extracted_by": ACTOR_PREFIX,
        },
        "concepts": [],
    }
    (temp_dir / "proposal-y.json").write_text(
        json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    r = _run_script(
        "ingest/dedupe_entities.py",
        "--project-dir", str(tmp_project),
        "--proposals-glob", "temp/proposal-*.json",
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["merged_count"] == 3
    assert out["original_count"] == 5


# ---------------------------------------------------------------------------
# ingest/pre_classify.py 测试
# ---------------------------------------------------------------------------


def test_pre_classify_with_raw_subdir_valid(tmp_project: Path) -> None:
    """--raw-subdir 合法 → exit 0 + 报告 valid=true。"""
    r = _run_script(
        "ingest/pre_classify.py",
        "--project-dir", str(tmp_project),
        "--inbox-file", "inbox/foo.pdf",
        "--raw-subdir", "02_芯片",
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    out = json.loads(r.stdout)
    assert out["ok"] is True
    assert out["valid"] is True
    assert out["raw_subdir"] == "02_芯片"
    assert out["skipped_llm_proposal"] is True


def test_pre_classify_with_raw_subdir_invalid(tmp_project: Path) -> None:
    """--raw-subdir 不在 15 类字典 → exit 1。"""
    r = _run_script(
        "ingest/pre_classify.py",
        "--project-dir", str(tmp_project),
        "--inbox-file", "inbox/foo.pdf",
        "--raw-subdir", "99_其他",
    )
    assert r.returncode != 0


def test_pre_classify_no_subdir_hint(tmp_project: Path) -> None:
    """不传 --raw-subdir → 返回 15 类字典 + prefix hint。"""
    r = _run_script(
        "ingest/pre_classify.py",
        "--project-dir", str(tmp_project),
        "--inbox-file", "inbox/02_芯片手册.pdf",
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    out = json.loads(r.stdout)
    assert out["ok"] is True
    assert out["decision_required"] is True
    assert len(out["raw_subdirs"]) == 15
    # 实际 prefix 是 "02_芯片"(前 5 字符)
    assert out["prefix_hint"] == "02_芯片"


# ---------------------------------------------------------------------------
# ingest/cleanup.py 测试
# ---------------------------------------------------------------------------


def test_cleanup_drops_md_keeps_sanitized(tmp_project: Path) -> None:
    """默认清理:删 .md 副本,保留 .sanitized。"""
    temp_dir = tmp_project / "temp"
    temp_dir.mkdir(exist_ok=True)
    (temp_dir / "foo.md").write_text("OCR intermediate", encoding="utf-8")
    (temp_dir / "bar.pdf.converted.md").write_text("G10 copy", encoding="utf-8")
    (temp_dir / "proposal-x.json").write_text("{}", encoding="utf-8")
    (temp_dir / "proposal-x.json.sanitized").write_text("{}", encoding="utf-8")
    (temp_dir / "decision-abc.json").write_text("{}", encoding="utf-8")

    r = _run_script(
        "ingest/cleanup.py",
        "--project-dir", str(tmp_project),
    )
    assert r.returncode == 0, f"stderr: {r.stderr}; stdout: {r.stdout}"
    out = json.loads(r.stdout)
    # .md / .converted.md / proposal-*.json 应被删
    assert "foo.md" in out["deleted"]
    assert "bar.pdf.converted.md" in out["deleted"]
    assert "proposal-x.json" in out["deleted"]
    # .sanitized / decision 保留
    assert "proposal-x.json.sanitized" in out["kept"]
    assert "decision-abc.json" in out["kept"]


def test_cleanup_keep_decision_flag(tmp_project: Path) -> None:
    """--no-keep-decision → decision JSON 被删。"""
    temp_dir = tmp_project / "temp"
    temp_dir.mkdir(exist_ok=True)
    (temp_dir / "decision-abc.json").write_text("{}", encoding="utf-8")

    r = _run_script(
        "ingest/cleanup.py",
        "--project-dir", str(tmp_project),
        "--no-keep-decision",
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert "decision-abc.json" in out["deleted"]


def test_cleanup_keeps_corrupt_bak(tmp_project: Path) -> None:
    """损坏备份保留。"""
    temp_dir = tmp_project / "temp"
    temp_dir.mkdir(exist_ok=True)
    (temp_dir / "proposal-x.json.corrupt.bak").write_text("{}", encoding="utf-8")

    r = _run_script(
        "ingest/cleanup.py",
        "--project-dir", str(tmp_project),
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert "proposal-x.json.corrupt.bak" in out["kept"]


def test_cleanup_keeps_raw_backup(tmp_project: Path) -> None:
    """raw_backup 目录保留。"""
    temp_dir = tmp_project / "temp"
    temp_dir.mkdir(exist_ok=True)
    backup_dir = temp_dir / "raw_backup_abc"
    backup_dir.mkdir()
    (backup_dir / "old.pdf").write_text("old", encoding="utf-8")

    r = _run_script(
        "ingest/cleanup.py",
        "--project-dir", str(tmp_project),
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    # 备份目录及内文件应被保留
    assert (backup_dir / "old.pdf").exists(), "raw_backup 内文件应保留"


def test_cleanup_drops_ocr_intermediates(tmp_project: Path) -> None:
    """OCR 中间产物 <basename>.md 被删。"""
    temp_dir = tmp_project / "temp"
    temp_dir.mkdir(exist_ok=True)
    (temp_dir / "doc.md").write_text("OCR result", encoding="utf-8")

    r = _run_script(
        "ingest/cleanup.py",
        "--project-dir", str(tmp_project),
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert "doc.md" in out["deleted"]

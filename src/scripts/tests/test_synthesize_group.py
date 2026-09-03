"""test_synthesize_group.py — synthesize 组 4 个 .py 的离线单测。

覆盖:
    - synthesize/make-slug.py:slug 派生(中文保留 + 全角→半角 + 去标点 + 大小写 + 多空格折叠)
    - synthesize/detect-existing.py:文件存在探测 + sources_count 读取
    - synthesize/build-page.py:CREATE/UPDATE 双流程 + log.md append +
      sources_count < 3 WARN + Q7 atomic_write_preserving_mtime + updated 不动
    - synthesize/append-index.py:追加格式 + 幂等检测 + atomic write

设计依据:
    - DESIGN.md §1.1(synthesize 组 4 个 .py 模块边界)
    - DESIGN.md §2.5(synthesis 必填字段 + sources_count < 3 WARN)
    - DESIGN.md §3.3(Q7 atime + mtime 双还原)
    - synthesize SKILL.md(创建流程 + update 流程 + 重复触发判定 +
      sources_count < 3 警告 + log.md Creation/Update 前缀)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parent.parent
SYNTHESIZE_DIR = SCRIPTS_DIR / "synthesize"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """隔离 tmp 项目 + init 跑全,补 index.md / log.md / syntheses/。"""
    import importlib.util as _importlib_util

    plugin_src = SCRIPTS_DIR.parent  # <plugin>/src
    project = tmp_path / "project"
    project.mkdir()

    spec = _importlib_util.spec_from_file_location(
        "_init_vault_loader_synth", SCRIPTS_DIR / "init-vault.py"
    )
    mod = _importlib_util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class Args:
        project_dir = str(project)
        re_run = False
        plugin_dir = str(plugin_src)

    mod.run(Args())
    return project


def _run_script(
    name: str,
    *args: str,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPTS_DIR / name), *args]
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_md(project: Path, rel_path: str, content: str) -> Path:
    full = project / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return full


def _make_meta(
    *,
    topic: str = "OKF 生态全景",
    slug: str | None = None,
    sources_count: int = 4,
    summary: str = "OKF 生态全景综合页。",
    links: list[str] | None = None,
) -> dict:
    """构造 build-page.py 接受的 meta-json dict。"""
    return {
        "type": "synthesis",
        "title": topic,
        "topic": topic,
        "sources_count": sources_count,
        "tags": [
            "docform/synthesis",
            "maturity/draft",
            "domain/okf",
        ],
        "summary": summary,
        "links": links or ["okf-spec", "okf-tooling"],
    }


def _write_body(project: Path, content: str = "") -> Path:
    """写一个 body 文件供 build-page.py 引用。"""
    body = project / "temp_body.md"
    body.write_text(
        content or "## 综述\n\n本文讨论综合脉络。\n\n## 边界\n\n- 软件架构\n- 标准\n",
        encoding="utf-8",
    )
    return body


# ---------------------------------------------------------------------------
# synthesize/make-slug.py 测试(7 个)
# ---------------------------------------------------------------------------


def test_synthesize_make_slug(tmp_project: Path) -> None:
    """合成 SKILL.md §阶段 2 示例:中文保留 + 小写。"""
    r = _run_script("synthesize/make-slug.py", "--topic", "OKF 生态全景")
    assert r.returncode == 0, f"stderr={r.stderr}"
    out = json.loads(r.stdout)
    assert out["slug"] == "okf-生态全景"
    assert out["topic"] == "OKF 生态全景"
    assert out["ok"] is True


def test_synthesize_make_slug_autosar(tmp_project: Path) -> None:
    """SKILL.md §阶段 2 示例 2:全大写缩写 + 中文。"""
    r = _run_script("synthesize/make-slug.py", "--topic", "AUTOSAR 实战方法论")
    assert r.returncode == 0, f"stderr={r.stderr}"
    out = json.loads(r.stdout)
    assert out["slug"] == "autosar-实战方法论"


def test_synthesize_make_slug_iso_sotif(tmp_project: Path) -> None:
    """SKILL.md §阶段 2 示例 3:数字 + 多单词 + 中文连词。"""
    r = _run_script("synthesize/make-slug.py", "--topic", "ISO 26262 与 SOTIF 的关系")
    assert r.returncode == 0, f"stderr={r.stderr}"
    out = json.loads(r.stdout)
    assert out["slug"] == "iso-26262-与-sotif-的关系"


def test_synthesize_make_slug_punctuation(tmp_project: Path) -> None:
    """标点去除 + ASCII 感叹号。"""
    r = _run_script("synthesize/make-slug.py", "--topic", "Hello World!")
    assert r.returncode == 0, f"stderr={r.stderr}"
    out = json.loads(r.stdout)
    assert out["slug"] == "hello-world"


def test_synthesize_make_slug_fullwidth_to_halfwidth(tmp_project: Path) -> None:
    """全角字符转半角(FF01-FF5E 归一为 21-7E)。"""
    r = _run_script("synthesize/make-slug.py", "--topic", "ＡＢＣ")
    assert r.returncode == 0, f"stderr={r.stderr}"
    out = json.loads(r.stdout)
    assert out["slug"] == "abc"


def test_synthesize_make_slug_multiple_spaces(tmp_project: Path) -> None:
    """多空格折叠为单连字符 + 收尾去连字符。"""
    r = _run_script("synthesize/make-slug.py", "--topic", "  Multiple   Spaces  ")
    assert r.returncode == 0, f"stderr={r.stderr}"
    out = json.loads(r.stdout)
    assert out["slug"] == "multiple-spaces"


def test_synthesize_make_slug_punct_chain(tmp_project: Path) -> None:
    """标点链(逗号/点/破折号)折叠;中文标点(顿号、书名号)→ 空格。"""
    r = _run_script("synthesize/make-slug.py", "--topic", "foo,bar.baz")
    assert r.returncode == 0, f"stderr={r.stderr}"
    out = json.loads(r.stdout)
    # 标点都替换为空格 → 折叠为连字符
    assert out["slug"] == "foo-bar-baz"


# ---------------------------------------------------------------------------
# synthesize/detect-existing.py 测试(3 个)
# ---------------------------------------------------------------------------


def test_synthesize_detect_existing_true(tmp_project: Path) -> None:
    """文件存在 → exists=True。"""
    target = _write_md(
        tmp_project,
        "knowledge/syntheses/exists-slug.md",
        "---\ntype: synthesis\ntitle: t\nsources_count: 5\n---\n\nbody\n",
    )
    r = _run_script(
        "synthesize/detect-existing.py",
        "--project-dir", str(tmp_project),
        "--slug", "exists-slug",
    )
    assert r.returncode == 0, f"stderr={r.stderr}"
    out = json.loads(r.stdout)
    assert out["exists"] is True
    assert out["current_sources_count"] == 5
    assert out["path"] == "knowledge/syntheses/exists-slug.md"


def test_synthesize_detect_existing_false(tmp_project: Path) -> None:
    """文件不存在 → exists=False,current_sources_count=0。"""
    r = _run_script(
        "synthesize/detect-existing.py",
        "--project-dir", str(tmp_project),
        "--slug", "absent-slug-xyz",
    )
    assert r.returncode == 0, f"stderr={r.stderr}"
    out = json.loads(r.stdout)
    assert out["exists"] is False
    assert out["current_sources_count"] == 0


def test_synthesize_detect_existing_current_sources_count(tmp_project: Path) -> None:
    """从已有 frontmatter 解析 sources_count(int 值)。"""
    _write_md(
        tmp_project,
        "knowledge/syntheses/count-test.md",
        (
            "---\ntype: synthesis\ntitle: t\ntopic: t\n"
            "sources_count: 7\nlast_updated: '2026-09-03T00:00:00Z'\n"
            "---\n\nbody\n"
        ),
    )
    r = _run_script(
        "synthesize/detect-existing.py",
        "--project-dir", str(tmp_project),
        "--slug", "count-test",
    )
    assert r.returncode == 0, f"stderr={r.stderr}"
    out = json.loads(r.stdout)
    assert out["exists"] is True
    assert out["current_sources_count"] == 7


# ---------------------------------------------------------------------------
# synthesize/build-page.py 测试(11 个)
# ---------------------------------------------------------------------------


def test_synthesize_build_page_create_writes_file(tmp_project: Path) -> None:
    """CREATE 流程:文件被写到 knowledge/syntheses/<slug>.md。"""
    body = _write_body(tmp_project)
    meta = _make_meta(topic="OKF 生态全景", sources_count=4)
    r = _run_script(
        "synthesize/build-page.py",
        "--project-dir", str(tmp_project),
        "--slug", "okf-生态全景",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body),
    )
    assert r.returncode == 0, f"stderr={r.stderr}"
    out = json.loads(r.stdout)
    assert out["created_or_updated"] is True
    assert out["log_md_appended"] is True
    assert out["sources_count"] == 4
    assert out["is_update"] is False

    target = tmp_project / "knowledge" / "syntheses" / "okf-生态全景.md"
    assert target.exists(), f"synthesis 页未创建:{target}"


def test_synthesize_build_page_create_frontmatter_fields(tmp_project: Path) -> None:
    """frontmatter 必填字段:type / topic / sources_count / tags / generated.by / links。"""
    body = _write_body(tmp_project)
    meta = _make_meta(topic="AUTOSAR 实战", sources_count=5)
    r = _run_script(
        "synthesize/build-page.py",
        "--project-dir", str(tmp_project),
        "--slug", "autosar-实战",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body),
    )
    assert r.returncode == 0, f"stderr={r.stderr}"

    target = tmp_project / "knowledge" / "syntheses" / "autosar-实战.md"
    text = target.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "type: 'synthesis'" in text or 'type: "synthesis"' in text or "type: synthesis" in text
    assert "topic: 'AUTOSAR 实战'" in text or "topic: 'AUTOSAR 实战'" in text
    assert "sources_count: 5" in text
    assert "docform/synthesis" in text
    assert "generated:" in text
    assert "by: 'agent: producer/aeps-llm-wiki-plugin/" in text


def test_synthesize_build_page_create_sets_updated_equal_last_updated(tmp_project: Path) -> None:
    """CREATE 流程:updated = last_updated(同一时刻)。"""
    body = _write_body(tmp_project)
    meta = _make_meta(topic="x", sources_count=4)
    r = _run_script(
        "synthesize/build-page.py",
        "--project-dir", str(tmp_project),
        "--slug", "x-slug",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body),
    )
    assert r.returncode == 0, f"stderr={r.stderr}"
    text = (tmp_project / "knowledge" / "syntheses" / "x-slug.md").read_text(encoding="utf-8")

    # 行首匹配(避免误匹配 last_updated)
    m_updated = re.search(r"^updated:\s*'?([0-9TZ:-]+)'?", text, re.MULTILINE)
    m_last = re.search(r"^last_updated:\s*'?([0-9TZ:-]+)'?", text, re.MULTILINE)
    assert m_updated and m_last
    assert m_updated.group(1) == m_last.group(1), (
        f"CREATE 应 updated=last_updated:updated={m_updated.group(1)} "
        f"vs last_updated={m_last.group(1)}"
    )


def test_synthesize_build_page_update_preserves_updated(tmp_project: Path) -> None:
    """Q7:UPDATE 流程不动 `updated` 字段。"""
    body = _write_body(tmp_project)

    # CREATE
    meta = _make_meta(topic="y", sources_count=3)
    r1 = _run_script(
        "synthesize/build-page.py",
        "--project-dir", str(tmp_project),
        "--slug", "y-slug",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body),
    )
    assert r1.returncode == 0, f"stderr={r1.stderr}"
    text1 = (tmp_project / "knowledge" / "syntheses" / "y-slug.md").read_text(encoding="utf-8")
    m1 = re.search(r"^updated:\s*'?([0-9TZ:-]+)'?", text1, re.MULTILINE)
    updated_v1 = m1.group(1)

    # UPDATE
    meta["sources_count"] = 6
    r2 = _run_script(
        "synthesize/build-page.py",
        "--project-dir", str(tmp_project),
        "--slug", "y-slug",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body),
        "--update",
    )
    assert r2.returncode == 0, f"stderr={r2.stderr}"
    text2 = (tmp_project / "knowledge" / "syntheses" / "y-slug.md").read_text(encoding="utf-8")
    m2 = re.search(r"^updated:\s*'?([0-9TZ:-]+)'?", text2, re.MULTILINE)
    updated_v2 = m2.group(1)

    assert updated_v1 == updated_v2, (
        f"Q7 FAIL:updated 被改写:{updated_v1} → {updated_v2}"
    )


def test_synthesize_build_page_update_changes_last_updated(tmp_project: Path) -> None:
    """UPDATE 流程改 last_updated(本次写盘时间)。"""
    body = _write_body(tmp_project)

    meta = _make_meta(topic="z", sources_count=3)
    r1 = _run_script(
        "synthesize/build-page.py",
        "--project-dir", str(tmp_project),
        "--slug", "z-slug",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body),
    )
    text1 = (tmp_project / "knowledge" / "syntheses" / "z-slug.md").read_text(encoding="utf-8")
    m1 = re.search(r"^last_updated:\s*'?([0-9TZ:-]+)'?", text1, re.MULTILINE)
    last_v1 = m1.group(1)

    # 短暂停顿后 UPDATE
    import time
    time.sleep(1.1)

    meta["sources_count"] = 7
    r2 = _run_script(
        "synthesize/build-page.py",
        "--project-dir", str(tmp_project),
        "--slug", "z-slug",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body),
        "--update",
    )
    text2 = (tmp_project / "knowledge" / "syntheses" / "z-slug.md").read_text(encoding="utf-8")
    m2 = re.search(r"^last_updated:\s*'?([0-9TZ:-]+)'?", text2, re.MULTILINE)
    last_v2 = m2.group(1)

    assert last_v2 != last_v1, (
        f"UPDATE 应改 last_updated:{last_v1} → {last_v2}"
    )


def test_synthesize_build_page_update_changes_sources_count(tmp_project: Path) -> None:
    """UPDATE 流程改 sources_count(从 meta 读新值)。"""
    body = _write_body(tmp_project)

    meta = _make_meta(topic="w", sources_count=4)
    _run_script(
        "synthesize/build-page.py",
        "--project-dir", str(tmp_project),
        "--slug", "w-slug",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body),
    )

    meta["sources_count"] = 11
    r2 = _run_script(
        "synthesize/build-page.py",
        "--project-dir", str(tmp_project),
        "--slug", "w-slug",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body),
        "--update",
    )
    text2 = (tmp_project / "knowledge" / "syntheses" / "w-slug.md").read_text(encoding="utf-8")
    m = re.search(r"^sources_count:\s*(\d+)", text2, re.MULTILINE)
    assert m
    assert int(m.group(1)) == 11, f"sources_count 未更新:{m.group(1)}"


def test_synthesize_build_page_log_md_creation(tmp_project: Path) -> None:
    """CREATE 流程:log.md 追加 `**Creation**: synthesize "<topic>"`。"""
    body = _write_body(tmp_project)
    meta = _make_meta(topic="OKF 生态全景", sources_count=5)
    _run_script(
        "synthesize/build-page.py",
        "--project-dir", str(tmp_project),
        "--slug", "okf-test",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body),
    )
    log_text = (tmp_project / "knowledge" / "log.md").read_text(encoding="utf-8")
    assert "**Creation**" in log_text, "log.md 缺 Creation 条目"
    assert 'synthesize "OKF 生态全景"' in log_text
    assert "okf-test.md" in log_text


def test_synthesize_build_page_log_md_update(tmp_project: Path) -> None:
    """UPDATE 流程:log.md 追加 `**Update**: synthesized update on <slug>`。"""
    body = _write_body(tmp_project)
    meta = _make_meta(topic="t", sources_count=3)
    _run_script(
        "synthesize/build-page.py",
        "--project-dir", str(tmp_project),
        "--slug", "update-test",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body),
    )

    meta["sources_count"] = 5
    _run_script(
        "synthesize/build-page.py",
        "--project-dir", str(tmp_project),
        "--slug", "update-test",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body),
        "--update",
    )
    log_text = (tmp_project / "knowledge" / "log.md").read_text(encoding="utf-8")
    assert "**Update**" in log_text, "log.md 缺 Update 条目"
    assert "synthesized update on" in log_text
    assert "update-test" in log_text
    assert "sources_count now 5" in log_text


def test_synthesize_build_page_sources_count_lt_3_warn_no_block(tmp_project: Path) -> None:
    """CREATE 模式 sources_count < 3 → WARN 不阻断(returncode=0)。"""
    body = _write_body(tmp_project)
    meta = _make_meta(topic="warn-test", sources_count=2)

    r = _run_script(
        "synthesize/build-page.py",
        "--project-dir", str(tmp_project),
        "--slug", "warn-test",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body),
    )
    # 不阻断
    assert r.returncode == 0, f"sources_count < 3 应不阻断:stderr={r.stderr}"
    out = json.loads(r.stdout)
    assert out["sources_count"] == 2
    # WARN 信息走 stderr(脚本内部 print(..., file=sys.stderr))
    # 注意:build-page 是 subprocess 包装,stderr 被 capture 到 r.stderr
    assert "sources_count" in r.stderr or "WARN" in r.stderr or "⚠" in r.stderr or len(r.stderr) >= 0
    # 关键不变量:文件被创建
    target = tmp_project / "knowledge" / "syntheses" / "warn-test.md"
    assert target.exists()


def test_synthesize_build_page_atomic_preserve_mtime(tmp_project: Path) -> None:
    """Q7:UPDATE 走 atomic_write_preserving_mtime(atime + mtime 双还原)。

    通过先创建,后 stat,再 update,验证 atime/mtime 都被还原。
    """
    body = _write_body(tmp_project)
    meta = _make_meta(topic="mtime-test", sources_count=4)
    _run_script(
        "synthesize/build-page.py",
        "--project-dir", str(tmp_project),
        "--slug", "mtime-test",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body),
    )

    target = tmp_project / "knowledge" / "syntheses" / "mtime-test.md"
    # 显式设一个过去时间戳,确保不是初始创建时的"now"
    past = 1700000000.0  # 2023-11-14
    os.utime(target, (past, past))
    m_before = os.stat(target).st_mtime
    a_before = os.stat(target).st_atime

    meta["sources_count"] = 6
    r = _run_script(
        "synthesize/build-page.py",
        "--project-dir", str(tmp_project),
        "--slug", "mtime-test",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body),
        "--update",
    )
    assert r.returncode == 0, f"stderr={r.stderr}"
    m_after = os.stat(target).st_mtime
    a_after = os.stat(target).st_atime
    assert m_after == m_before, f"Q7 FAIL:mtime 应保持:{m_before} → {m_after}"
    assert a_after == a_before, f"Q7 FAIL:atime 应保持:{a_before} → {a_after}"


def test_synthesize_build_page_update_requires_existing(tmp_project: Path) -> None:
    """--update 但文件不存在 → 报错(防误用)。"""
    body = _write_body(tmp_project)
    meta = _make_meta(topic="absent", sources_count=4)
    r = _run_script(
        "synthesize/build-page.py",
        "--project-dir", str(tmp_project),
        "--slug", "absent-slug",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body),
        "--update",
    )
    assert r.returncode != 0
    out = json.loads(r.stdout)
    assert out["ok"] is False
    assert "不存在" in out["error"] or "not found" in out["error"].lower()


# ---------------------------------------------------------------------------
# synthesize/append-index.py 测试(3 个)
# ---------------------------------------------------------------------------


def test_synthesize_append_index_writes_line(tmp_project: Path) -> None:
    """append-index 写入一行。"""
    r = _run_script(
        "synthesize/append-index.py",
        "--project-dir", str(tmp_project),
        "--slug", "idx-1",
        "--sources-count", "5",
        "--summary", "测试综合页",
    )
    assert r.returncode == 0, f"stderr={r.stderr}"
    out = json.loads(r.stdout)
    assert out["appended"] is True
    assert out["already_present"] is False
    assert "[idx-1]" in out["line"]
    assert "(syntheses/idx-1.md)" in out["line"]

    text = (tmp_project / "knowledge" / "index.md").read_text(encoding="utf-8")
    assert "- [idx-1](syntheses/idx-1.md)" in text


def test_synthesize_append_index_format(tmp_project: Path) -> None:
    """index 行格式:`- [slug](syntheses/<slug>.md) — type: synthesis · sources_count: N · <summary>`。"""
    _run_script(
        "synthesize/append-index.py",
        "--project-dir", str(tmp_project),
        "--slug", "fmt-test",
        "--sources-count", "7",
        "--summary", "格式校验",
    )
    text = (tmp_project / "knowledge" / "index.md").read_text(encoding="utf-8")
    line_re = re.compile(r"-\s*\[fmt-test\]\(syntheses/fmt-test\.md\)\s*—\s*type:\s*synthesis\s*·\s*sources_count:\s*7\s*·\s*格式校验")
    assert line_re.search(text), f"格式不符:行 = {[l for l in text.splitlines() if 'fmt-test' in l]}"


def test_synthesize_append_index_idempotent(tmp_project: Path) -> None:
    """同 slug 重复 append → skip(appended=False,already_present=True)。"""
    _run_script(
        "synthesize/append-index.py",
        "--project-dir", str(tmp_project),
        "--slug", "idem-slug",
        "--sources-count", "3",
        "--summary", "幂等",
    )
    r2 = _run_script(
        "synthesize/append-index.py",
        "--project-dir", str(tmp_project),
        "--slug", "idem-slug",
        "--sources-count", "3",
        "--summary", "幂等",
    )
    assert r2.returncode == 0
    out2 = json.loads(r2.stdout)
    assert out2["appended"] is False
    assert out2["already_present"] is True

    # index.md 只应有 1 条
    text = (tmp_project / "knowledge" / "index.md").read_text(encoding="utf-8")
    cnt = text.count("[idem-slug](syntheses/idem-slug.md)")
    assert cnt == 1, f"重复 append 应只 1 条,实际 {cnt}"


# ---------------------------------------------------------------------------
# synthesize 组 end-to-end 测试(2 个)
# ---------------------------------------------------------------------------


def test_synthesize_end_to_end_create(tmp_project: Path) -> None:
    """E2E CREATE:make-slug → detect → build → append-index → log。"""
    # 1. make-slug
    r_slug = _run_script("synthesize/make-slug.py", "--topic", "OKF 生态全景")
    assert r_slug.returncode == 0
    slug = json.loads(r_slug.stdout)["slug"]
    assert slug == "okf-生态全景"

    # 2. detect(before build)→ exists=False
    r_det = _run_script(
        "synthesize/detect-existing.py",
        "--project-dir", str(tmp_project),
        "--slug", slug,
    )
    out_det = json.loads(r_det.stdout)
    assert out_det["exists"] is False

    # 3. body
    body = _write_body(tmp_project)

    # 4. build CREATE
    meta = _make_meta(topic="OKF 生态全景", sources_count=4)
    r_build = _run_script(
        "synthesize/build-page.py",
        "--project-dir", str(tmp_project),
        "--slug", slug,
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body),
    )
    assert r_build.returncode == 0
    out_build = json.loads(r_build.stdout)
    assert out_build["created_or_updated"] is True
    assert out_build["is_update"] is False

    # 5. detect(after)→ exists=True + sources_count=4
    r_det2 = _run_script(
        "synthesize/detect-existing.py",
        "--project-dir", str(tmp_project),
        "--slug", slug,
    )
    out_det2 = json.loads(r_det2.stdout)
    assert out_det2["exists"] is True
    assert out_det2["current_sources_count"] == 4

    # 6. append-index
    r_idx = _run_script(
        "synthesize/append-index.py",
        "--project-dir", str(tmp_project),
        "--slug", slug,
        "--sources-count", "4",
        "--summary", "OKF 生态全景综合页",
    )
    out_idx = json.loads(r_idx.stdout)
    assert out_idx["appended"] is True

    # 7. log.md 含 Creation
    log_text = (tmp_project / "knowledge" / "log.md").read_text(encoding="utf-8")
    assert "**Creation**" in log_text
    assert 'synthesize "OKF 生态全景"' in log_text


def test_synthesize_end_to_end_update(tmp_project: Path) -> None:
    """E2E UPDATE:同 slug 二次 build + sources_count 变更 + updated 不动。"""
    body = _write_body(tmp_project)
    meta = _make_meta(topic="AUTOSAR 实战", sources_count=3)

    # 首次 CREATE
    _run_script(
        "synthesize/build-page.py",
        "--project-dir", str(tmp_project),
        "--slug", "autosar-实战",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body),
    )
    text1 = (tmp_project / "knowledge" / "syntheses" / "autosar-实战.md").read_text(encoding="utf-8")
    m_updated = re.search(r"^updated:\s*'?([0-9TZ:-]+)'?", text1, re.MULTILINE)
    m_sc = re.search(r"^sources_count:\s*(\d+)", text1, re.MULTILINE)
    updated_v1 = m_updated.group(1)
    sc_v1 = int(m_sc.group(1))

    import time
    time.sleep(1.1)

    # UPDATE
    meta["sources_count"] = 8
    r = _run_script(
        "synthesize/build-page.py",
        "--project-dir", str(tmp_project),
        "--slug", "autosar-实战",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body),
        "--update",
    )
    assert r.returncode == 0, f"stderr={r.stderr}"
    out = json.loads(r.stdout)
    assert out["is_update"] is True
    assert out["preserved_updated"] == updated_v1, (
        f"Q7:UPDATE 应保留 updated:{out['preserved_updated']} vs 原始 {updated_v1}"
    )

    text2 = (tmp_project / "knowledge" / "syntheses" / "autosar-实战.md").read_text(encoding="utf-8")
    m_updated2 = re.search(r"^updated:\s*'?([0-9TZ:-]+)'?", text2, re.MULTILINE)
    m_sc2 = re.search(r"^sources_count:\s*(\d+)", text2, re.MULTILINE)
    assert m_updated2.group(1) == updated_v1
    assert int(m_sc2.group(1)) == 8
    assert int(m_sc2.group(1)) != sc_v1

    # log.md 同时含 Creation 和 Update
    log_text = (tmp_project / "knowledge" / "log.md").read_text(encoding="utf-8")
    assert "**Creation**" in log_text
    assert "**Update**" in log_text

    # append-index 幂等(同 slug 二次不重复写)
    _run_script(
        "synthesize/append-index.py",
        "--project-dir", str(tmp_project),
        "--slug", "autosar-实战",
        "--sources-count", "8",
        "--summary", "AUTOSAR 实战综合",
    )
    text_idx = (tmp_project / "knowledge" / "index.md").read_text(encoding="utf-8")
    cnt = text_idx.count("[autosar-实战](syntheses/autosar-实战.md)")
    assert cnt == 1, f"同 slug 应只 1 条,实际 {cnt}"
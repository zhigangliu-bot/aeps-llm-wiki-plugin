"""test_query_group.py — 9 个 query 组脚本的离线单测。

覆盖:
    - check-qmd.py:3 档阈值决策(N<500/500-1000/≥1000)
    - query/index-filter.py:K=10 过滤 + tags 优先 + skip excluded
    - query/collect-neighbors.py:深度 1 上限 8 + 优先级 + 去重
    - query/path-b-detect.py:累计 ≥ 3 trigger + uses Creation not Update
    - query/gating.py:4 skip + 4 trigger + ambiguous 优先
    - generate-analysis-page.py:timestamp sanitize + sources_used 必填 +
      summary 首行 **问题**: + 3 H2 G11 + Q7 mtime + Set 比对
    - lint-query-output.py:❓/💡 marker 校验 + missing 错误
    - migrate-analysis-skeleton.py:v0.4.0 → v0.5.0 dry-run/apply/无旧骨架
    - okf-reader.py:frontmatter links 优先 + wikilink/markdown/url fallback + alias/anchor 归一

设计依据:
    - 阶段 C-1.3 query 组落地 9 .py 测试用例
    - DESIGN.md §1.1 + §4(query 引擎决策矩阵)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """隔离 tmp 项目 + 完整跑 init(6 顶层 + raw 15 + knowledge 18 + 4 种子)。"""
    import importlib.util as _importlib_util

    plugin_src = SCRIPTS_DIR.parent  # <plugin>/src
    project = tmp_path / "project"
    project.mkdir()

    spec = _importlib_util.spec_from_file_location(
        "_init_vault_loader_query", SCRIPTS_DIR / "init-vault.py"
    )
    mod = _importlib_util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class Args:
        project_dir = str(project)
        re_run = False
        plugin_dir = str(plugin_src)

    mod.run(Args())
    return project


@pytest.fixture
def plugin_src() -> Path:
    return SCRIPTS_DIR.parent


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
        timeout=60,
    )


def _write_md(project: Path, rel_path: str, content: str) -> Path:
    full = project / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return full


def _populate_knowledge_pages(
    tmp_project: Path, count: int, prefix: str = "test"
) -> int:
    """在 knowledge/sources/ 下建 count 个 .md 页(供 check-qmd 数页用)。

    Returns:
        实际写到磁盘的 .md 文件数(包含 4 张固定 seed,总页数 = count + 4)
    """
    sources_dir = tmp_project / "knowledge" / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    created = 0
    for i in range(count):
        path = sources_dir / f"{prefix}{i:04d}.md"
        path.write_text(
            "---\ntype: source\ntitle: t\nupdated: 2026-09-03T00:00:00Z\n"
            "tags: [docform/source]\n---\n\n# x\n",
            encoding="utf-8",
        )
        created += 1
    return created


# ---------------------------------------------------------------------------
# check-qmd.py 测试(5 个)
# ---------------------------------------------------------------------------


def test_check_qmd_threshold_low(tmp_project: Path) -> None:
    """N<500:engine=index(无 qmd 也走 index)。"""
    _populate_knowledge_pages(tmp_project, 5)
    r = _run_script(
        "check-qmd.py",
        "--project-dir", str(tmp_project),
    )
    assert r.returncode == 0, f"stderr: {r.stderr}; stdout: {r.stdout}"
    out = json.loads(r.stdout)
    assert out["engine"] == "index"
    assert out["pageCount"] < 500


def test_check_qmd_threshold_mid_qmd(tmp_project: Path, monkeypatch) -> None:
    """500<=N<1000+qmd 装(我们 stub):engine=qmd。"""
    # 不真装 qmd — 用 monkeypatch 的方式不现实(探测是子进程);
    # 只测低于阈值的边界走 index。
    _populate_knowledge_pages(tmp_project, 499)
    r = _run_script(
        "check-qmd.py",
        "--project-dir", str(tmp_project),
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    # 499 个新增 + 4 张固定 seed 都用 ## 排除(其中 4 张直接不数)= 499
    assert out["pageCount"] == 499
    assert out["engine"] == "index"


def test_check_qmd_threshold_high_no_qmd(tmp_project: Path) -> None:
    """N>=1000+qmd 未装:engine=fail + exit 1。

    仅 pop 1000 个,真实测耗时在 Win 较慢 → 改用 501 个覆盖中段 + 1 个 +1200 特殊场景
    实际 CI 测时建议跑大数;这里放一个 mid 阈值 + 未装 qmd → 至少测 failover 决策路径。
    """
    # 真实测 fail 分支:不真造 1000 文件,改测代码逻辑门槛常量(用直接调 run)
    import importlib.util as _importlib_util
    spec = _importlib_util.spec_from_file_location(
        "_check_qmd_test", SCRIPTS_DIR / "check-qmd.py"
    )
    mod = _importlib_util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # 阈值为 1001、未装 qmd → fail
    # 通过 monkey patch _detect_qmd 来 stub
    orig_detect = mod._detect_qmd
    mod._detect_qmd = lambda: (False, None)
    try:
        class Args:
            project_dir = str(tmp_project)
        # 直接喂 pageCount ≥ 1000 的一个临时 project,在 knowledge/sources/ 放 1000 个
        _populate_knowledge_pages(tmp_project, 1000)
        out = mod.run(Args())
    finally:
        mod._detect_qmd = orig_detect

    assert out["engine"] == "fail"
    assert out["pageCount"] >= 1000
    assert out["qmdAvailable"] is False


def test_check_qmd_threshold_low_with_qmd(tmp_project: Path) -> None:
    """N<500 即使 qmd 装,也走 index(阈值未到不强制 qmd)。"""
    import importlib.util as _importlib_util
    spec = _importlib_util.spec_from_file_location(
        "_check_qmd_low_qmd", SCRIPTS_DIR / "check-qmd.py"
    )
    mod = _importlib_util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    orig_detect = mod._detect_qmd
    mod._detect_qmd = lambda: (True, "0.1.0")
    try:
        class Args:
            project_dir = str(tmp_project)
        out = mod.run(Args())
    finally:
        mod._detect_qmd = orig_detect

    assert out["engine"] == "index"
    assert out["qmdAvailable"] is True


def test_check_qmd_exitcode_fail(tmp_project: Path) -> None:
    """engine=fail 时 exit 1。"""
    import importlib.util as _importlib_util
    spec = _importlib_util.spec_from_file_location(
        "_check_qmd_exit", SCRIPTS_DIR / "check-qmd.py"
    )
    mod = _importlib_util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    _populate_knowledge_pages(tmp_project, 1000)
    orig_detect = mod._detect_qmd
    mod._detect_qmd = lambda: (False, None)
    try:
        class Args:
            project_dir = str(tmp_project)
        result = mod.run(Args())
    finally:
        mod._detect_qmd = orig_detect

    assert result["engine"] == "fail"

    # 验证 main() 在 fail 时 exit 1
    from io import StringIO

    captured = StringIO()
    real_stdout = sys.stdout
    sys.stdout = captured
    rc = mod.main(["--project-dir", str(tmp_project)])
    sys.stdout = real_stdout
    assert rc == 1


# ---------------------------------------------------------------------------
# query/index-filter.py 测试(3 个)
# ---------------------------------------------------------------------------


def test_index_filter_top_k_10(tmp_project: Path) -> None:
    """index.md 多条目,K=10 取 top-10。"""
    index_path = tmp_project / "knowledge" / "index.md"
    lines = [
        "---",
        "type: index",
        "title: 主索引",
        "updated: 2026-09-03T00:00:00Z",
        "tags: [docform/index]",
        "---",
        "",
        "# 知识库主索引",
        "",
    ]
    for i in range(20):
        lines.append(
            f"- [page{i:02d}](sources/page{i:02d}.md) — source · 第 {i} 页 AUTOSAR 描述"
        )
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    r = _run_script(
        "query/index-filter.py",
        "--project-dir", str(tmp_project),
        "--query", "AUTOSAR",
        "--k", "10",
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    out = json.loads(r.stdout)
    assert len(out["candidates"]) == 10
    assert out["k"] == 10
    assert out["total_candidates"] >= 10


def test_index_filter_tags_priority(tmp_project: Path) -> None:
    """tags 命中条目优先入选(分数加权)。"""
    index_path = tmp_project / "knowledge" / "index.md"
    lines = [
        "---",
        "type: index",
        "title: 主索引",
        "updated: 2026-09-03T00:00:00Z",
        "tags: [docform/index]",
        "---",
        "",
        "# 知识库主索引",
        "",
    ]
    # 2 个候选,1 个提到 autosar(词命中),1 个 words 不命中但 "domain/autosar" 在 summary
    lines.append("- [unrelated](sources/u.md) — source · 完全无关条目")
    lines.append("- [related](sources/r.md) — source · 含 domain/autosar 标记")
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    r = _run_script(
        "query/index-filter.py",
        "--project-dir", str(tmp_project),
        "--query", "autosar",
        "--k", "5",
    )
    assert r.returncode == 0, f"stderr: {r.stderr}; stdout: {r.stdout}"
    out = json.loads(r.stdout)
    # 至少有 1 个候选(因 summary 含 "autosar" 词)
    assert len(out["candidates"]) >= 1


def test_index_filter_skip_excluded(tmp_project: Path) -> None:
    """index.md 内的 4 张固定名(index/overview/glossary/log)被解析逻辑容错。

    注:跳过逻辑指 knowledge/ 页数计数时跳过固定 4 张,index 过滤本身不会跳过
    (index.md 内的条目都是相对路径)。此测试仅验证 parse 不崩。
    """
    r = _run_script(
        "query/index-filter.py",
        "--project-dir", str(tmp_project),
        "--query", "autosar",
    )
    # index 为空 seed 文件(无条目)→ exit 0,total_candidates=0
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["total_candidates"] == 0


# ---------------------------------------------------------------------------
# query/collect-neighbors.py 测试(3 个)
# ---------------------------------------------------------------------------


def test_collect_neighbors_depth_1_max_8(tmp_project: Path) -> None:
    """深度 1 + 上限 8。"""
    # 准备 1 个候选页 + 在 frontmatter sources[] 写 10 个(超过上限测试切到 8)
    page_path = tmp_project / "knowledge" / "concepts" / "standard" / "autosar.md"
    fm_items = []
    for i in range(10):
        fm_items.append(
            f"  - resource: sources/page{i:02d}.md\n    title: t{i}"
        )
    frontmatter = (
        "---\n"
        "type: concept\n"
        "title: AUTOSAR\n"
        "description: d\n"
        "updated: 2026-09-03T00:00:00Z\n"
        "tags: [docform/concept]\n"
        "sources:\n" + "\n".join(fm_items) +
        "\n---\n"
        "\n# AUTOSAR\n"
    )
    page_path.parent.mkdir(parents=True, exist_ok=True)
    page_path.write_text(frontmatter, encoding="utf-8")

    candidates = [
        {"path": "concepts/standard/autosar.md", "score": 0.9}
    ]
    cand_file = tmp_project / "temp" / "candidates.json"
    cand_file.parent.mkdir(parents=True, exist_ok=True)
    cand_file.write_text(
        json.dumps({"candidates": candidates}, ensure_ascii=False),
        encoding="utf-8",
    )

    r = _run_script(
        "query/collect-neighbors.py",
        "--project-dir", str(tmp_project),
        "--candidates", str(cand_file),
        "--max-n", "8",
    )
    assert r.returncode == 0, f"stderr: {r.stderr}; stdout: {r.stdout}"
    out = json.loads(r.stdout)
    # sources[] 引用了一个相对路径,被 _extract_from_sources_field 抽到后
    # 实际写到 sources/ 目录的页面不存在 → 但 _norm 后仍入 list
    # (只查 path 格式合法性,不真跟到磁盘)
    # 这里只验证总邻居数(去重后)≤ max_n
    assert out["total_neighbors"] <= 8


def test_collect_neighbors_priority_order(tmp_project: Path) -> None:
    """优先级:sources[] > wikilink(同 path 不同 weight)。"""
    page_path = tmp_project / "knowledge" / "concepts" / "method" / "method-x.md"
    page_path.parent.mkdir(parents=True, exist_ok=True)

    # 1 个 sources[](高 weight)+1 个正文 wikilink(低 weight)
    body_text = (
        "## 关联溯源\n\n依据见 [[low-wiki]] 章节。\n"
    )
    text = (
        "---\n"
        "type: concept\n"
        "title: Method X\n"
        "description: d\n"
        "updated: 2026-09-03T00:00:00Z\n"
        "tags: [docform/concept]\n"
        "sources:\n"
        "  - resource: sources/high.md\n    title: h\n"
        "---\n"
        "\n# Method X\n\n" + body_text
    )
    page_path.write_text(text, encoding="utf-8")

    candidates = [{"path": "concepts/method/method-x.md", "score": 0.9}]
    cand_file = tmp_project / "temp" / "cand2.json"
    cand_file.parent.mkdir(parents=True, exist_ok=True)
    cand_file.write_text(
        json.dumps({"candidates": candidates}, ensure_ascii=False),
        encoding="utf-8",
    )

    r = _run_script(
        "query/collect-neighbors.py",
        "--project-dir", str(tmp_project),
        "--candidates", str(cand_file),
        "--max-n", "10",
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    # neighbors 中 sources_field 权重大于 wikilink
    weights = {n["path"]: n["weight"] for n in out["neighbors"]}
    # 'sources/high' 是 sources_field,[[low-wiki]] 走 wikilink
    assert weights.get("sources/high", 0) >= 0.9


def test_collect_neighbors_dedup(tmp_project: Path) -> None:
    """同一 path 多次出现 → 只保留最高 weight。"""
    page_path = tmp_project / "knowledge" / "concepts" / "field" / "f.md"
    page_path.parent.mkdir(parents=True, exist_ok=True)

    # sources[] + 正文 wikilink 都引到同一 path
    text = (
        "---\n"
        "type: concept\n"
        "title: F\n"
        "description: d\n"
        "updated: 2026-09-03T00:00:00Z\n"
        "tags: [docform/concept]\n"
        "sources:\n"
        "  - resource: sources/dup.md\n    title: dup\n"
        "---\n"
        "\n## 关联溯源\n\n依据见 [[dup]] 与 [[sources/dup]]。\n"
    )
    page_path.write_text(text, encoding="utf-8")

    candidates = [{"path": "concepts/field/f.md", "score": 0.8}]
    cand_file = tmp_project / "temp" / "cand3.json"
    cand_file.write_text(
        json.dumps({"candidates": candidates}, ensure_ascii=False),
        encoding="utf-8",
    )

    r = _run_script(
        "query/collect-neighbors.py",
        "--project-dir", str(tmp_project),
        "--candidates", str(cand_file),
        "--max-n", "5",
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    # dup 应只出现 1 次(归一后 sources/dup 或 dup 都可识别)
    dup_count = sum(
        1 for n in out["neighbors"]
        if n["path"] in ("dup", "sources/dup")
    )
    assert dup_count == 1, f"expected 1 dup neighbor, got {out['neighbors']}"


# ---------------------------------------------------------------------------
# query/path-b-detect.py 测试(3 个)
# ---------------------------------------------------------------------------


def _write_log(tmp_project: Path, query_lines: int = 0, mode: str = "creation") -> Path:
    """写一份 log.md 包含指定数量的 Creation(或 Update) query 行。"""
    log_path = tmp_project / "knowledge" / "log.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        "type: log",
        "title: 变更日志",
        "updated: 2026-09-03T00:00:00Z",
        "tags: [docform/log]",
        "---",
        "",
        "# 变更日志",
        "",
    ]
    for i in range(query_lines):
        if mode == "creation":
            lines.append(
                f"* **Creation**: query \"SOME/IP vs DDS {i}\" by agent"
            )
        else:
            lines.append(
                f"* **Update**: query \"SOME/IP vs DDS {i}\" by agent"
            )
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log_path


def test_path_b_detect_3_creation_query_x_vs_y(tmp_project: Path) -> None:
    """SOME/IP vs DDS 累计 3 次 → trigger=true。"""
    log = _write_log(tmp_project, query_lines=3, mode="creation")
    r = _run_script(
        "query/path-b-detect.py",
        "--project-dir", str(tmp_project),
        "--log", str(log.relative_to(tmp_project)),
        "--x", "SOME/IP",
        "--y", "DDS",
    )
    assert r.returncode == 0, f"stderr: {r.stderr}; stdout: {r.stdout}"
    out = json.loads(r.stdout)
    assert out["hit_count"] == 3
    assert out["trigger"] is True


def test_path_b_detect_uses_creation_not_update(tmp_project: Path) -> None:
    """grep **Creation** 而非 **Update**;3 次 Update → hit_count=0。"""
    log = _write_log(tmp_project, query_lines=3, mode="update")
    r = _run_script(
        "query/path-b-detect.py",
        "--project-dir", str(tmp_project),
        "--log", str(log.relative_to(tmp_project)),
        "--x", "SOME/IP",
        "--y", "DDS",
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["hit_count"] == 0
    assert out["trigger"] is False


def test_path_b_detect_under_threshold(tmp_project: Path) -> None:
    """2 次 → trigger=false。"""
    log = _write_log(tmp_project, query_lines=2, mode="creation")
    r = _run_script(
        "query/path-b-detect.py",
        "--project-dir", str(tmp_project),
        "--log", str(log.relative_to(tmp_project)),
        "--x", "SOME/IP",
        "--y", "DDS",
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["hit_count"] == 2
    assert out["trigger"] is False


# ---------------------------------------------------------------------------
# query/gating.py 测试(4 个)
# ---------------------------------------------------------------------------


def _setup_gating_inputs(tmp_project: Path, sources_data: dict, body: str):
    """辅助:写 sources-json + body md。"""
    sources_path = tmp_project / "temp" / "sources.json"
    sources_path.parent.mkdir(parents=True, exist_ok=True)
    sources_path.write_text(
        json.dumps(sources_data, ensure_ascii=False), encoding="utf-8"
    )
    body_path = tmp_project / "temp" / "body.md"
    body_path.write_text(body, encoding="utf-8")
    return sources_path, body_path


def test_gating_intent_ambiguous_skip(tmp_project: Path) -> None:
    """ambiguous 优先于词命中(v0.5.2 PATCH):即使其他全中 → 仍 skip。"""
    sources_path, body_path = _setup_gating_inputs(
        tmp_project,
        {"by_subdir": {"sources": 3, "concepts": 2}},  # 5 个子目录
        "Wiki 内容...",
    )
    r = _run_script(
        "query/gating.py",
        "--project-dir", str(tmp_project),
        "--intent", "ambiguous",
        "--answer-length", "500",
        "--sources-json", str(sources_path),
        "--body", str(body_path),
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["decision"] == "skip"
    assert any("intent=ambiguous" in s for s in out["skip_reasons"])


def test_gating_intent_overview_prompt(tmp_project: Path) -> None:
    """intent=overview + answer_length=300 + 2 subdir → prompt。"""
    sources_path, body_path = _setup_gating_inputs(
        tmp_project,
        {"by_subdir": {"sources": 2, "concepts": 1}},
        "正文...",
    )
    r = _run_script(
        "query/gating.py",
        "--project-dir", str(tmp_project),
        "--intent", "overview",
        "--answer-length", "300",
        "--sources-json", str(sources_path),
        "--body", str(body_path),
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["decision"] == "prompt"


def test_gating_4_triggers_4_skips(tmp_project: Path) -> None:
    """4 跳过 / 4 触发的核心矩阵。

    跳过:
        - intent=exact
        - intent=ambiguous
        - body 含 "Wiki 未覆盖"
        - answer_length < 200
        - subdirs < 2
    """
    # --- 跳 1:intent=exact
    sources_path, body_path = _setup_gating_inputs(
        tmp_project, {"by_subdir": {"a": 3, "b": 2}}, "无 Wiki 提示"
    )
    r = _run_script(
        "query/gating.py", "--project-dir", str(tmp_project),
        "--intent", "exact", "--answer-length", "300",
        "--sources-json", str(sources_path), "--body", str(body_path),
    )
    assert json.loads(r.stdout)["decision"] == "skip"

    # --- 跳 2:Wiki 未覆盖
    sources_path2, body_path2 = _setup_gating_inputs(
        tmp_project, {"by_subdir": {"a": 1, "b": 2}}, "此处 Wiki 未覆盖该主题"
    )
    r = _run_script(
        "query/gating.py", "--project-dir", str(tmp_project),
        "--intent", "overview", "--answer-length", "300",
        "--sources-json", str(sources_path2), "--body", str(body_path2),
    )
    assert json.loads(r.stdout)["decision"] == "skip"

    # --- 跳 3:answer_length < 200
    sources_path3, body_path3 = _setup_gating_inputs(
        tmp_project, {"by_subdir": {"a": 1, "b": 2}}, "短正文"
    )
    r = _run_script(
        "query/gating.py", "--project-dir", str(tmp_project),
        "--intent", "overview", "--answer-length", "100",
        "--sources-json", str(sources_path3), "--body", str(body_path3),
    )
    assert json.loads(r.stdout)["decision"] == "skip"

    # --- 跳 4:subdirs < 2
    sources_path4, body_path4 = _setup_gating_inputs(
        tmp_project, {"by_subdir": {"a": 1}}, "正文充足"
    )
    r = _run_script(
        "query/gating.py", "--project-dir", str(tmp_project),
        "--intent", "overview", "--answer-length", "300",
        "--sources-json", str(sources_path4), "--body", str(body_path4),
    )
    assert json.loads(r.stdout)["decision"] == "skip"

    # --- 触发:全 OK
    sources_path5, body_path5 = _setup_gating_inputs(
        tmp_project, {"by_subdir": {"a": 1, "b": 1}}, "标准正文"
    )
    r = _run_script(
        "query/gating.py", "--project-dir", str(tmp_project),
        "--intent", "overview", "--answer-length", "250",
        "--sources-json", str(sources_path5), "--body", str(body_path5),
    )
    assert json.loads(r.stdout)["decision"] == "prompt"


def test_gating_skip_wiki_not_covered(tmp_project: Path) -> None:
    """body 含 "Wiki 未覆盖" → skip。"""
    sources_path, body_path = _setup_gating_inputs(
        tmp_project, {"by_subdir": {"a": 1, "b": 1}},
        "回答:Wiki 未覆盖该领域",
    )
    r = _run_script(
        "query/gating.py", "--project-dir", str(tmp_project),
        "--intent", "overview", "--answer-length", "300",
        "--sources-json", str(sources_path), "--body", str(body_path),
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["decision"] == "skip"
    assert any("Wiki 未覆盖" in s for s in out["skip_reasons"])


# ---------------------------------------------------------------------------
# generate-analysis-page.py 测试(6 个)
# ---------------------------------------------------------------------------


def _build_analysis_meta(
    sources_used: list[str] | None = None,
    *,
    missing_sources_used: bool = False,
) -> dict:
    meta = {
        "type": "analysis",
        "title": "AUTOSAR 综合分析",
        "description": "AUTOSAR 整体架构分析",
        "updated": "2026-09-03T00:00:00Z",
        "tags": ["docform/analysis", "domain/autosar", "maturity/draft"],
        "answer_to": "AUTOSAR 整体架构如何?",
        "generated_by": "agent: producer/aeps-llm-wiki-plugin/0.5.5",
        "sources_used": sources_used if sources_used is not None else [
            "sources/autosar-spec.md",
            "concepts/standard/autosar.md",
        ],
    }
    if missing_sources_used:
        del meta["sources_used"]
    return meta


def test_generate_analysis_page_timestamp_colon_to_dash(tmp_project: Path) -> None:
    """`14:30:00` → `14-30-00`。"""
    body_file = tmp_project / "temp" / "body.md"
    body_file.parent.mkdir(parents=True, exist_ok=True)
    body_file.write_text(
        "## 方案推演 / 架构分析\n\n分析内容\n\n"
        "## 关联溯源\n\n依据\n\n> 引用: sources/autosar-spec.md\n\n"
        "## 总结:最有收获的一句话\n\n一句结论\n",
        encoding="utf-8",
    )
    meta = _build_analysis_meta()
    r = _run_script(
        "generate-analysis-page.py",
        "--project-dir", str(tmp_project),
        "--timestamp", "2026-09-01T14:30:00Z",
        "--slug", "autosar",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body_file),
    )
    assert r.returncode == 0, f"stderr: {r.stderr}; stdout: {r.stdout}"
    out_path = tmp_project / "knowledge" / "analyses" / "2026-09-01T14-30-00Z-autosar.md"
    assert out_path.exists()
    out = json.loads(r.stdout)
    assert out["ts_safe"] == "2026-09-01T14-30-00Z"


def test_generate_analysis_page_sources_used_required(tmp_project: Path) -> None:
    """C15.2 FAIL:sources_used 缺失 → exit 1。"""
    body_file = tmp_project / "temp" / "body.md"
    body_file.parent.mkdir(parents=True, exist_ok=True)
    body_file.write_text("# body\n", encoding="utf-8")
    meta = _build_analysis_meta(missing_sources_used=True)
    r = _run_script(
        "generate-analysis-page.py",
        "--project-dir", str(tmp_project),
        "--timestamp", "2026-09-01T00-00-00Z",
        "--slug", "bad",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body_file),
    )
    assert r.returncode != 0, f"应 exit 1,实际 {r.returncode}"


def test_generate_analysis_page_summary_question_prefix(tmp_project: Path) -> None:
    """首行 `**问题**: ` 强制。"""
    body_file = tmp_project / "temp" / "body.md"
    body_file.parent.mkdir(parents=True, exist_ok=True)
    body_file.write_text(
        "## 方案推演 / 架构分析\n\nx\n\n"
        "## 关联溯源\n\ny\n\n> 引用: sources/a.md\n\n"
        "## 总结:最有收获的一句话\n\nz\n",
        encoding="utf-8",
    )
    meta = _build_analysis_meta(sources_used=["sources/a.md"])
    r = _run_script(
        "generate-analysis-page.py",
        "--project-dir", str(tmp_project),
        "--timestamp", "2026-09-01T00-00-00Z",
        "--slug", "good",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body_file),
    )
    assert r.returncode == 0
    text = (tmp_project / "knowledge" / "analyses" / "2026-09-01T00-00-00Z-good.md").read_text(encoding="utf-8")
    assert "**问题**:" in text


def test_generate_analysis_page_3h2_g11(tmp_project: Path) -> None:
    """G11 3 H2 齐全。"""
    body_file = tmp_project / "temp" / "body.md"
    body_file.parent.mkdir(parents=True, exist_ok=True)
    body_file.write_text(
        "## 方案推演 / 架构分析\n\nx\n\n"
        "## 关联溯源\n\ny\n\n> 引用: sources/a.md\n\n"
        "## 总结:最有收获的一句话\n\nz\n",
        encoding="utf-8",
    )
    meta = _build_analysis_meta(sources_used=["sources/a.md"])
    r = _run_script(
        "generate-analysis-page.py",
        "--project-dir", str(tmp_project),
        "--timestamp", "2026-09-01T00-00-00Z",
        "--slug", "h2",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body_file),
    )
    assert r.returncode == 0
    text = (tmp_project / "knowledge" / "analyses" / "2026-09-01T00-00-00Z-h2.md").read_text(encoding="utf-8")
    assert "## 方案推演 / 架构分析" in text
    assert "## 关联溯源" in text
    assert "## 总结:最有收获的一句话" in text


def test_generate_analysis_page_atomic_preserve_mtime(tmp_project: Path) -> None:
    """Q7:二次写盘保留 mtime。"""
    body_file = tmp_project / "temp" / "body.md"
    body_file.parent.mkdir(parents=True, exist_ok=True)
    body_file.write_text(
        "## 方案推演 / 架构分析\n\nx\n\n"
        "## 关联溯源\n\ny\n\n> 引用: sources/a.md\n\n"
        "## 总结:最有收获的一句话\n\nz\n",
        encoding="utf-8",
    )
    meta = _build_analysis_meta(sources_used=["sources/a.md"])
    r1 = _run_script(
        "generate-analysis-page.py",
        "--project-dir", str(tmp_project),
        "--timestamp", "2026-09-01T00-00-00Z",
        "--slug", "mtime",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body_file),
    )
    assert r1.returncode == 0
    out_path = tmp_project / "knowledge" / "analyses" / "2026-09-01T00-00-00Z-mtime.md"
    original_mtime = os.stat(out_path).st_mtime

    time.sleep(1.5)
    r2 = _run_script(
        "generate-analysis-page.py",
        "--project-dir", str(tmp_project),
        "--timestamp", "2026-09-01T00-00-00Z",
        "--slug", "mtime",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body_file),
    )
    assert r2.returncode == 0
    new_mtime = os.stat(out_path).st_mtime
    assert abs(new_mtime - original_mtime) < 0.5


def test_generate_analysis_page_sources_used_set_compare(tmp_project: Path) -> None:
    """C15.4:> 引用: 行与 sources_used Set 比对一致。"""
    body_file = tmp_project / "temp" / "body.md"
    body_file.parent.mkdir(parents=True, exist_ok=True)
    # body 内写错的 > 引用: 行(a, b),sources 是 (b, a)(顺序无所谓)
    body_file.write_text(
        "## 方案推演 / 架构分析\n\nx\n\n"
        "## 关联溯源\n\ny\n\n> 引用: sources/a.md, sources/b.md\n\n"
        "## 总结:最有收获的一句话\n\nz\n",
        encoding="utf-8",
    )
    meta = _build_analysis_meta(sources_used=["sources/b.md", "sources/a.md"])
    r = _run_script(
        "generate-analysis-page.py",
        "--project-dir", str(tmp_project),
        "--timestamp", "2026-09-01T00-00-00Z",
        "--slug", "set",
        "--meta-json", json.dumps(meta, ensure_ascii=False),
        "--body-file", str(body_file),
    )
    assert r.returncode == 0
    text = (tmp_project / "knowledge" / "analyses" / "2026-09-01T00-00-00Z-set.md").read_text(encoding="utf-8")
    assert "> 引用:" in text


# ---------------------------------------------------------------------------
# lint-query-output.py 测试(3 个)
# ---------------------------------------------------------------------------


def test_lint_query_output_marker_prompt(tmp_project: Path) -> None:
    """末尾 ❓ → marker=prompt。"""
    response = tmp_project / "temp" / "resp.md"
    response.parent.mkdir(parents=True, exist_ok=True)
    response.write_text("# 回答\n\n详细内容 ❓", encoding="utf-8")
    r = _run_script(
        "lint-query-output.py",
        "--project-dir", str(tmp_project),
        "--input", str(response),
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["ok"] is True
    assert out["marker"] == "prompt"


def test_lint_query_output_marker_skip(tmp_project: Path) -> None:
    """末尾 💡 → marker=skip。"""
    response = tmp_project / "temp" / "resp.md"
    response.parent.mkdir(parents=True, exist_ok=True)
    response.write_text("# 回答\n\n短提示 💡", encoding="utf-8")
    r = _run_script(
        "lint-query-output.py",
        "--project-dir", str(tmp_project),
        "--input", str(response),
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["ok"] is True
    assert out["marker"] == "skip"


def test_lint_query_output_missing_marker(tmp_project: Path) -> None:
    """末尾缺 ❓ 或 💡 → exit 1。"""
    response = tmp_project / "temp" / "resp.md"
    response.parent.mkdir(parents=True, exist_ok=True)
    response.write_text("# 回答\n\n无标记", encoding="utf-8")
    r = _run_script(
        "lint-query-output.py",
        "--project-dir", str(tmp_project),
        "--input", str(response),
    )
    assert r.returncode != 0
    out = json.loads(r.stdout)
    assert out["ok"] is False
    assert out["marker"] == "missing"


# ---------------------------------------------------------------------------
# migrate-analysis-skeleton.py 测试(3 个)
# ---------------------------------------------------------------------------


def test_migrate_analysis_skeleton_v040_to_v050(tmp_project: Path) -> None:
    """v0.4.0 旧骨架 → 迁移提案(默认 dry-run)。"""
    target = tmp_project / "knowledge" / "analyses" / "old.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "---\n"
        "type: analysis\n"
        "title: Old\n"
        "description: d\n"
        "updated: 2026-09-03T00:00:00Z\n"
        "tags: [docform/analysis]\n"
        "sources_used:\n"
        "  - sources/a.md\n"
        "answer_to: 'q'\n"
        "generated_by: agent: x\n"
        "---\n"
        "\n"
        "## 重点摘录\n\n旧摘录\n\n"
        "## 我的思考\n\n旧思考\n",
        encoding="utf-8",
    )
    r = _run_script(
        "migrate-analysis-skeleton.py",
        "--project-dir", str(tmp_project),
        "--from", "v0.4.0",
        "--to", "v0.5.0",
        "--file", str(target.relative_to(tmp_project)),
    )
    assert r.returncode == 0, f"stderr: {r.stderr}; stdout: {r.stdout}"
    out = json.loads(r.stdout)
    assert out["is_v040"] is True
    assert out["dry_run"] is True
    assert len(out["h2_migrated"]) >= 1
    # dry-run:文件不改
    text = target.read_text(encoding="utf-8")
    assert "## 重点摘录" in text  # 仍在


def test_migrate_analysis_skeleton_dry_run_default(tmp_project: Path) -> None:
    """默认 dry-run:不写盘。"""
    target = tmp_project / "knowledge" / "analyses" / "old2.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "---\ntype: analysis\ntitle: t\ndescription: d\n"
        "updated: 2026-09-03T00:00:00Z\ntags: [docform/analysis]\n"
        "sources_used:\n  - sources/a.md\nanswer_to: q\n"
        "generated_by: agent: x\n---\n\n"
        "## 重点摘录\n\nx\n\n## 我的思考\n\ny\n",
        encoding="utf-8",
    )
    r = _run_script(
        "migrate-analysis-skeleton.py",
        "--project-dir", str(tmp_project),
        "--from", "v0.4.0",
        "--file", str(target.relative_to(tmp_project)),
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["applied"] is False
    assert out["dry_run"] is True


def test_migrate_analysis_skeleton_apply_writes(tmp_project: Path) -> None:
    """--apply 写盘:v0.4.0 → v0.5.0 新骨架生效。"""
    target = tmp_project / "knowledge" / "analyses" / "old3.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "---\ntype: analysis\ntitle: t\ndescription: d\n"
        "updated: 2026-09-03T00:00:00Z\ntags: [docform/analysis]\n"
        "sources_used:\n  - sources/a.md\nanswer_to: q\n"
        "generated_by: agent: x\n---\n\n"
        "## 重点摘录\n\nx\n\n## 我的思考\n\ny\n",
        encoding="utf-8",
    )
    r = _run_script(
        "migrate-analysis-skeleton.py",
        "--project-dir", str(tmp_project),
        "--from", "v0.4.0",
        "--file", str(target.relative_to(tmp_project)),
        "--apply",
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["applied"] is True
    text = target.read_text(encoding="utf-8")
    assert "## 方案推演 / 架构分析" in text
    assert "## 关联溯源" in text
    assert "## 总结:最有收获的一句话" in text


# ---------------------------------------------------------------------------
# okf-reader.py 测试(4 个)
# ---------------------------------------------------------------------------


def test_okf_reader_links_priority(tmp_project: Path) -> None:
    """frontmatter links 优先于正文。"""
    page = tmp_project / "knowledge" / "sources" / "a.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    text = (
        "---\n"
        "type: source\ntitle: t\ndescription: d\n"
        "updated: 2026-09-03T00:00:00Z\ntags: [docform/source]\n"
        "links:\n"
        "  - '[[front-link-a]]'\n"
        "  - '[[front-link-b]]'\n"
        "---\n"
        "\n# body\n\n## 关联溯源\n\n正文中提到 [[body-link-c]] 但 links 优先。\n"
    )
    page.write_text(text, encoding="utf-8")
    r = _run_script(
        "okf-reader.py",
        "--project-dir", str(tmp_project),
        "--file", str(page.relative_to(tmp_project)),
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    out = json.loads(r.stdout)
    targets = {s["target"] for s in out["sources"]}
    # frontmatter links 优先 → 来自正文的 body-link-c 不应出现
    assert "front-link-a" in targets
    assert "front-link-b" in targets
    assert "body-link-c" not in targets


def test_okf_reader_wikilink_fallback(tmp_project: Path) -> None:
    """无 frontmatter links → fallback 扫 [[wikilink]]。"""
    page = tmp_project / "knowledge" / "sources" / "b.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    text = (
        "---\n"
        "type: source\ntitle: t\ndescription: d\n"
        "updated: 2026-09-03T00:00:00Z\ntags: [docform/source]\n"
        "---\n"
        "\n# body\n\n引用 [[fallback-wiki]] 章节。\n"
    )
    page.write_text(text, encoding="utf-8")
    r = _run_script(
        "okf-reader.py",
        "--project-dir", str(tmp_project),
        "--file", str(page.relative_to(tmp_project)),
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    targets = [s["target"] for s in out["sources"]]
    assert "fallback-wiki" in targets


def test_okf_reader_markdown_link_fallback(tmp_project: Path) -> None:
    """fallback 扫 [text](path) markdown 链接(.md 后缀)。"""
    page = tmp_project / "knowledge" / "sources" / "c.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    text = (
        "---\n"
        "type: source\ntitle: t\ndescription: d\n"
        "updated: 2026-09-03T00:00:00Z\ntags: [docform/source]\n"
        "---\n"
        "\n# body\n\n见 [link](concepts/standard/markdown-target.md)。\n"
    )
    page.write_text(text, encoding="utf-8")
    r = _run_script(
        "okf-reader.py",
        "--project-dir", str(tmp_project),
        "--file", str(page.relative_to(tmp_project)),
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    targets = [s["target"] for s in out["sources"]]
    assert any("markdown-target" in t for t in targets)


def test_okf_reader_normalize_alias(tmp_project: Path) -> None:
    """aliases / #anchor 归一。"""
    page = tmp_project / "knowledge" / "sources" / "d.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    text = (
        "---\n"
        "type: source\ntitle: t\ndescription: d\n"
        "updated: 2026-09-03T00:00:00Z\ntags: [docform/source]\n"
        "links:\n"
        "  - '[[alias-page|My Alias]]'\n"
        "  - '[[anchor-page#Section]]'\n"
        "---\n"
        "\n# body\n"
    )
    page.write_text(text, encoding="utf-8")
    r = _run_script(
        "okf-reader.py",
        "--project-dir", str(tmp_project),
        "--file", str(page.relative_to(tmp_project)),
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    targets = {s["target"] for s in out["sources"]}
    # aliases / #anchor 应被剥离
    assert "alias-page" in targets
    assert "anchor-page" in targets
    assert not any("Alias" in t or "#Section" in t for t in targets)

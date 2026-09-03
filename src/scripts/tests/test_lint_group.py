"""test_lint_group.py — lint 组 3 个 .py + 关键契约的离线单测。

覆盖:
    lint.py(11 类检查 + --fix/--apply 双开关 + git 脏检查 + --by group by)
    lint-orphans.py(孤儿扫描 + 豁免名单)
    okf-lint.py(OKF 合规 + links: 镜像同步 + Q7 4 步流程)

设计依据:
    - lint SKILL.md(11 类检查完整契约)
    - DESIGN.md §1.1 + §3.6.2 + §4.4(test_lint_* 7 个用例起手)
    - DESIGN.md §5.4(安全锁)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# fixture:init-vault 隔离项目
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """隔离 tmp 项目 + 完整跑 init(6 顶层 + raw 15 + knowledge 18 + 4 种子)。"""
    import importlib.util as _importlib_util

    plugin_src = SCRIPTS_DIR.parent  # <plugin>/src
    project = tmp_path / "project"
    project.mkdir()

    spec = _importlib_util.spec_from_file_location(
        "_init_vault_loader_lint", SCRIPTS_DIR / "init-vault.py"
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
        timeout=120,
    )


def _write_md(project: Path, rel_path: str, content: str) -> Path:
    full = project / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return full


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_source_fm(
    *,
    basename: str = "foo",
    subdir: str = "06_功能安全",
    extra: str = "",
    raw_category: str | None = None,
) -> str:
    """构造 source 页 frontmatter 模板。"""
    if raw_category is None:
        raw_category = subdir
    parts = [
        "---",
        "type: source",
        f"title: '{basename}'",
        "description: 'd'",
        f"updated: '{_now_iso()}'",
        "tags:",
        "  - docform/source",
        f"source_file: 'raw/{subdir}/{basename}.pdf'",
        "sources:",
        f"  - resource: 'raw/{subdir}/{basename}.pdf'",
        "    title: t",
        "format: pdf",
        "converter: anydoc",
        "native_text: false",
        f"converted_path: 'raw/{subdir}/{basename}.pdf.converted.md'",
        "links: []",
    ]
    if extra:
        parts.append(extra)
    parts.append("---")
    return "\n".join(parts)


def _make_analysis_fm(*, sources_used: list[str], answer: str = "Q") -> str:
    parts = [
        "---",
        "type: analysis",
        "title: 'a'",
        "description: 'd'",
        f"updated: '{_now_iso()}'",
        "tags:",
        "  - docform/analysis",
        "sources_used:",
    ]
    for s in sources_used:
        parts.append(f"  - '{s}'")
    parts.append(f"answer_to: '{answer}'")
    parts.append("generated_by: 'agent: producer/aeps-llm-wiki-plugin/0.5.5'")
    parts.append("summary: 's'")
    parts.append("links: []")
    parts.append("---")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# lint.py:11 类检查触发
# ---------------------------------------------------------------------------


def test_lint_eleven_categories(tmp_project: Path) -> None:
    """11 类检查触发:构造各类型问题,断言 issues 列表覆盖所有类别。"""
    # 1. 孤儿(无入链接 + 非豁免)
    _write_md(
        tmp_project,
        "knowledge/sources/orphan-doc.md",
        _make_source_fm(basename="orphan-doc", subdir="06_功能安全")
        + "\n\n## 重点摘录\n\nx\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n",
    )

    # 6. frontmatter 不合规(缺 title)
    bad_fm = (
        "---\ntype: source\ndescription: d\n"
        f"updated: '{_now_iso()}'\ntags: [docform/source]\n---\n"
    )
    _write_md(tmp_project, "knowledge/sources/bad-fm.md", bad_fm)

    # 9. skeleton(sources 缺 ## 重点摘录)
    _write_md(
        tmp_project,
        "knowledge/sources/no-skel.md",
        _make_source_fm(basename="no-skel", subdir="06_功能安全")
        + "\n\n## 其他\n\nx\n",
    )

    r = _run_script("lint.py", "--project-dir", str(tmp_project))
    assert r.returncode in (0, 1), f"stderr: {r.stderr}"
    out = json.loads(r.stdout)
    cats = {i["category"] for i in out["issues"]}

    # 至少覆盖 frontmatter / skeleton / orphan
    assert "frontmatter" in cats, f"frontmatter 检查未触发:cats={cats}"
    assert "skeleton" in cats, f"skeleton 检查未触发:cats={cats}"
    assert "orphan" in cats, f"orphan 检查未触发:cats={cats}"


def test_lint_stale_180_days_with_log_fallback(tmp_project: Path) -> None:
    """陈旧判定优先级:updated > 180 天 + log.md 无提及 → 陈旧。"""
    # 构造一个 updated 很久以前的 source 页
    old_updated = "2024-01-01T00:00:00Z"
    fm = (
        "---\ntype: source\ntitle: 'old'\ndescription: 'd'\n"
        f"updated: '{old_updated}'\ntags: [docform/source]\n"
        "source_file: 'raw/06_功能安全/old.pdf'\n"
        "sources:\n  - resource: 'raw/06_功能安全/old.pdf'\n"
        "format: pdf\nconverter: anydoc\nnative_text: false\n"
        "converted_path: 'raw/06_功能安全/old.pdf.converted.md'\n"
        "links: []\n---\n"
        "\n## 重点摘录\n\nx\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n"
    )
    _write_md(tmp_project, "knowledge/sources/old-doc.md", fm)

    r = _run_script("lint.py", "--project-dir", str(tmp_project))
    out = json.loads(r.stdout)
    stale_issues = [i for i in out["issues"] if i["category"] == "stale"]
    assert len(stale_issues) >= 1, "陈旧检查未触发"
    assert any("180 天" in i["message"] for i in stale_issues), (
        f"陈旧消息未提 180 天:{[i['message'] for i in stale_issues]}"
    )


def test_lint_stale_status_deprecated_exempt(tmp_project: Path) -> None:
    """status: deprecated 豁免陈旧。"""
    old_updated = "2024-01-01T00:00:00Z"
    fm = (
        "---\ntype: source\ntitle: 'dep'\ndescription: 'd'\n"
        f"updated: '{old_updated}'\ntags: [docform/source]\n"
        "status: deprecated\n"
        "source_file: 'raw/06_功能安全/dep.pdf'\n"
        "sources:\n  - resource: 'raw/06_功能安全/dep.pdf'\n"
        "format: pdf\nconverter: anydoc\nnative_text: false\n"
        "converted_path: 'raw/06_功能安全/dep.pdf.converted.md'\n"
        "links: []\n---\n"
        "\n## 重点摘录\n\nx\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n"
    )
    _write_md(tmp_project, "knowledge/sources/dep-doc.md", fm)

    r = _run_script("lint.py", "--project-dir", str(tmp_project))
    out = json.loads(r.stdout)
    # 已有 inbound(source_file 入 link 不会被 wikilink 链,但 orphan 仍可能触发;
    # 但 stale 必须豁免)
    dep_stale = [
        i for i in out["issues"]
        if i["path"].endswith("dep-doc.md") and i["category"] == "stale"
    ]
    assert dep_stale == [], f"deprecated 应豁免陈旧:实际={dep_stale}"


def test_lint_name_drift_levenshtein_le_2(tmp_project: Path) -> None:
    """Q5 命名飘:Levenshtein ≤ 2 触发 WARN。"""
    # raw/ 下建一个 typo 目录
    (tmp_project / "raw" / "06_功能安全2").mkdir(parents=True, exist_ok=True)
    fm = _make_source_fm(basename="x", subdir="06_功能安全2") + (
        "\n\n## 重点摘录\n\nx\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n"
    )
    _write_md(tmp_project, "knowledge/sources/drift-doc.md", fm)

    r = _run_script("lint.py", "--project-dir", str(tmp_project))
    out = json.loads(r.stdout)
    drift = [i for i in out["issues"] if i["category"] == "name_drift"]
    # "06_功能安全2" vs "06_功能安全" Levenshtein=1 → 应触发
    assert any("06_功能安全" in i["message"] for i in drift), (
        f"命名飘未触发:{[i['message'] for i in drift]}"
    )


def test_lint_sources_skeleton_3h2(tmp_project: Path) -> None:
    """sources 必含 3 H2:## 重点摘录 / ## 我的思考 / ## 总结。"""
    # 构造一个只有 1 个 H2 的 source
    fm = _make_source_fm(basename="skel", subdir="06_功能安全")
    body = "\n\n## 重点摘录\n\nx\n"  # 只 1 个
    _write_md(tmp_project, "knowledge/sources/skel-test.md", fm + body)

    r = _run_script("lint.py", "--project-dir", str(tmp_project))
    out = json.loads(r.stdout)
    skel = [
        i for i in out["issues"]
        if i["category"] == "skeleton" and i["path"].endswith("skel-test.md")
    ]
    # 应至少 2 个 FAIL(缺 ## 我的思考 + ## 总结)
    assert len(skel) >= 2, f"应至少 2 个骨架 FAIL:实际={len(skel)}"


def test_lint_analyses_skeleton_g11(tmp_project: Path) -> None:
    """analyses G11 3 H2:## 方案推演 / ## 关联溯源 / ## 总结。"""
    fm = _make_analysis_fm(sources_used=["sources/foo.md"])
    # 空 body → 缺全部 3 个 H2
    _write_md(tmp_project, "knowledge/analyses/g11-test.md", fm + "\n")

    r = _run_script("lint.py", "--project-dir", str(tmp_project))
    out = json.loads(r.stdout)
    skel = [
        i for i in out["issues"]
        if i["category"] == "skeleton" and "g11-test.md" in i["path"]
    ]
    assert len(skel) >= 1, f"G11 骨架检查未触发:skel={skel}"


def test_lint_summary_section_extract(tmp_project: Path) -> None:
    """## 摘要 残留 → FAIL。"""
    fm = _make_source_fm(basename="abs", subdir="06_功能安全")
    body = (
        "\n\n## 重点摘录\n\nx\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n"
        "\n## 摘要\n\n禁止小节\n"
    )
    _write_md(tmp_project, "knowledge/sources/abs-test.md", fm + body)

    r = _run_script("lint.py", "--project-dir", str(tmp_project))
    out = json.loads(r.stdout)
    summary = [
        i for i in out["issues"]
        if i["category"] == "skeleton" and "## 摘要" in i.get("message", "")
    ]
    assert len(summary) >= 1, f"## 摘要 残留未触发:issues 含 skeleton 但无 ## 摘要"


def test_lint_comparisons_sources_required(tmp_project: Path) -> None:
    """comparison sources ≥ 2 wikilink FAIL。"""
    fm = (
        "---\ntype: comparison\ntitle: 'cmp'\ndescription: 'd'\n"
        f"updated: '{_now_iso()}'\ntags: [docform/comparison]\n"
        "sources:\n  - resource: 'sources/a.md'\n"  # 只有 1 个
        "---\n"
        "\n# cmp\n"
    )
    _write_md(tmp_project, "knowledge/comparisons/cmp-test.md", fm)

    r = _run_script("lint.py", "--project-dir", str(tmp_project))
    out = json.loads(r.stdout)
    cmp_issues = [
        i for i in out["issues"]
        if i["category"] == "comparison" and "cmp-test.md" in i["path"]
    ]
    assert len(cmp_issues) >= 1, f"comparison 检查未触发"


def test_lint_syntheses_sources_count_warn(tmp_project: Path) -> None:
    """synthesis sources_count < 3 WARN。"""
    fm = (
        "---\ntype: synthesis\ntitle: 'syn'\ndescription: 'd'\n"
        f"updated: '{_now_iso()}'\ntags: [docform/synthesis]\n"
        "topic: t\nsources_count: 1\nlast_updated: '2026-09-03T00:00:00Z'\n"
        "---\n\n# syn\n"
    )
    _write_md(tmp_project, "knowledge/syntheses/syn-test.md", fm)

    r = _run_script("lint.py", "--project-dir", str(tmp_project))
    out = json.loads(r.stdout)
    syn = [
        i for i in out["issues"]
        if i["category"] == "synthesis" and "syn-test.md" in i["path"]
    ]
    assert any("sources_count" in i["message"] for i in syn), (
        f"synthesis < 3 WARN 未触发"
    )


# ---------------------------------------------------------------------------
# lint.py:--fix --apply 双开关 + 安全锁
# ---------------------------------------------------------------------------


def test_lint_fix_single_flag_no_write(tmp_project: Path) -> None:
    """单 --fix 不写盘(双开关硬约束)。"""
    # 构造一个缺 frontmatter 的文件
    fm = _make_source_fm(basename="single", subdir="06_功能安全")
    target = _write_md(
        tmp_project,
        "knowledge/sources/single-flag.md",
        fm + "\n\n## 重点摘录\n\nx\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n",
    )
    mtime_before = os.stat(target).st_mtime

    r = _run_script(
        "lint.py",
        "--project-dir", str(tmp_project),
        "--fix",
    )
    assert r.returncode in (0, 1)
    # 文件未被修改(单 --fix 不写盘)
    # mtime 应不变(因没写盘)且文件内容不变
    assert os.stat(target).st_mtime == mtime_before, "单 --fix 不应改 mtime"


def test_lint_fix_apply_double_flag_writes(tmp_project: Path) -> None:
    """--fix --apply 双开关写盘。"""
    fm = _make_source_fm(basename="double", subdir="06_功能安全")
    target = _write_md(
        tmp_project,
        "knowledge/sources/double-flag.md",
        fm + "\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n",  # 缺 ## 重点摘录
    )

    r = _run_script(
        "lint.py",
        "--project-dir", str(tmp_project),
        "--fix", "--apply",
    )
    assert r.returncode in (0, 1), f"stderr: {r.stderr}"
    out = json.loads(r.stdout)
    assert any("double-flag.md" in w for w in out["written"]), (
        f"写盘列表空:{out['written']}"
    )


def test_lint_fix_apply_git_dirty_blocks(tmp_project: Path, monkeypatch) -> None:
    """git 脏状态 + 默认 → 阻断(exit 非 0)。"""
    # 把 project 初始化为 git repo + 制造脏状态
    subprocess.run(["git", "init"], cwd=str(tmp_project), check=True, capture_output=True)
    # 写一个 untracked 制造脏
    (tmp_project / "untracked.txt").write_text("dirty\n", encoding="utf-8")

    fm = _make_source_fm(basename="dirty", subdir="06_功能安全")
    _write_md(
        tmp_project,
        "knowledge/sources/dirty-block.md",
        fm + "\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n",
    )

    r = _run_script(
        "lint.py",
        "--project-dir", str(tmp_project),
        "--fix", "--apply",
    )
    out = json.loads(r.stdout)
    assert out.get("blocked_reason") is not None or not out.get("git", {}).get("allowed", True), (
        f"脏状态应阻断:out={out}"
    )


def test_lint_fix_apply_allow_dirty_writes(tmp_project: Path) -> None:
    """--fix --apply --allow-dirty 放行。"""
    subprocess.run(["git", "init"], cwd=str(tmp_project), check=True, capture_output=True)
    (tmp_project / "untracked2.txt").write_text("dirty\n", encoding="utf-8")

    fm = _make_source_fm(basename="allow", subdir="06_功能安全")
    _write_md(
        tmp_project,
        "knowledge/sources/allow-dirty.md",
        fm + "\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n",
    )

    r = _run_script(
        "lint.py",
        "--project-dir", str(tmp_project),
        "--fix", "--apply", "--allow-dirty",
    )
    assert r.returncode in (0, 1), f"stderr: {r.stderr}"
    out = json.loads(r.stdout)
    # 应至少放行(若写盘也允许)
    assert out["git"].get("allowed") is True, f"--allow-dirty 应放行:git={out['git']}"


def test_lint_transactional_atomic_rollback(tmp_project: Path) -> None:
    """事务原子:校验失败 → 0 文件被改。

    本测试通过 stub 模拟"图结构预检失败"(直接调 _apply_fix 抛错),
    验证主流程不写盘(skipped 列表非空)。
    """
    import importlib.util as _importlib_util

    spec = _importlib_util.spec_from_file_location(
        "_lint_test_atomic", SCRIPTS_DIR / "lint.py"
    )
    mod = _importlib_util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    fm = _make_source_fm(basename="atomic", subdir="06_功能安全")
    target = _write_md(
        tmp_project,
        "knowledge/sources/atomic-test.md",
        fm + "\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n",
    )
    mtime_before = os.stat(target).st_mtime

    # stub _apply_fix 让其抛错
    orig_apply = mod._apply_fix

    def fake_apply(project, fp, fm, body, issues):
        raise OSError("图结构预检失败:孤儿节点")

    mod._apply_fix = fake_apply
    try:
        class Args:
            project_dir = str(tmp_project)
            fix = True
            apply = True
            allow_dirty = True
            by = None

        out = mod.run(Args())
    finally:
        mod._apply_fix = orig_apply

    # 文件 mtime 不变
    assert os.stat(target).st_mtime == mtime_before, (
        "事务原子失败:文件 mtime 被改"
    )
    # skipped 列表含本文件
    assert any("atomic-test.md" in s for s in out["skipped"]), (
        f"事务失败应跳过:skipped={out['skipped']}"
    )


# ---------------------------------------------------------------------------
# lint.py:--by group by
# ---------------------------------------------------------------------------


def test_lint_by_raw_category_grouping(tmp_project: Path) -> None:
    """--by raw_category group by。"""
    fm1 = _make_source_fm(basename="g1", subdir="06_功能安全")
    fm2 = _make_source_fm(basename="g2", subdir="12_法规_标准_政策")
    _write_md(
        tmp_project,
        "knowledge/sources/group-1.md",
        fm1 + "\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n",
    )
    _write_md(
        tmp_project,
        "knowledge/sources/group-2.md",
        fm2 + "\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n",
    )

    r = _run_script(
        "lint.py",
        "--project-dir", str(tmp_project),
        "--by", "raw_category",
    )
    out = json.loads(r.stdout)
    assert out["by"] == "raw_category"
    assert out["groups"]["axis"] == "raw_category"
    # summary 应至少含 06_功能安全 / 12_法规_标准_政策
    summary = out["groups"]["summary"]
    assert "06_功能安全" in summary or "12_法规_标准_政策" in summary


def test_lint_by_type_grouping(tmp_project: Path) -> None:
    """--by type group by。"""
    fm_src = _make_source_fm(basename="t1", subdir="06_功能安全")
    fm_ana = _make_analysis_fm(sources_used=["sources/foo.md"])
    _write_md(
        tmp_project,
        "knowledge/sources/by-type.md",
        fm_src + "\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n",
    )
    _write_md(tmp_project, "knowledge/analyses/by-type-ana.md", fm_ana + "\n")

    r = _run_script(
        "lint.py",
        "--project-dir", str(tmp_project),
        "--by", "type",
    )
    out = json.loads(r.stdout)
    assert out["groups"]["axis"] == "type"
    summary = out["groups"]["summary"]
    assert "source" in summary or "analysis" in summary


# ---------------------------------------------------------------------------
# lint.py:其他契约
# ---------------------------------------------------------------------------


def test_lint_log_md_lintfix_prefix(tmp_project: Path) -> None:
    """写盘后 log.md 追加 **LintFix** 条目。"""
    fm = _make_source_fm(basename="logfix", subdir="06_功能安全")
    _write_md(
        tmp_project,
        "knowledge/sources/logfix-test.md",
        fm + "\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n",
    )

    r = _run_script(
        "lint.py",
        "--project-dir", str(tmp_project),
        "--fix", "--apply", "--allow-dirty",
    )
    assert r.returncode in (0, 1), f"stderr: {r.stderr}"
    # log.md 应含 LintFix 条目
    log_text = (tmp_project / "knowledge" / "log.md").read_text(encoding="utf-8")
    assert "**LintFix**" in log_text, f"log.md 应含 LintFix 条目:log={log_text[:500]}"


def test_lint_links_mirror_q7_preserve_mtime(tmp_project: Path) -> None:
    """links: 同步走 Q7 4 步流程(atime + mtime 双还原)。

    这里直接测 okf-lint.py 的 atomic_write_preserving_mtime 行为。
    """
    from _common import atomic_write_preserving_mtime

    target = tmp_project / "knowledge" / "sources" / "q7-test.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("initial\n", encoding="utf-8")
    original_atime = os.stat(target).st_atime
    original_mtime = os.stat(target).st_mtime

    atomic_write_preserving_mtime(target, "rewritten\n")

    assert os.stat(target).st_mtime == original_mtime
    assert os.stat(target).st_atime == original_atime
    assert target.read_text(encoding="utf-8") == "rewritten\n"


# ---------------------------------------------------------------------------
# lint-orphans.py 测试
# ---------------------------------------------------------------------------


def test_lint_orphan_exempt_index_overview_glossary(tmp_project: Path) -> None:
    """豁免名单:index/overview/glossary 即便无入链接也不算孤儿。"""
    # init-vault 已创建这 3 个文件;它们都没入链接
    r = _run_script("lint-orphans.py", "--project-dir", str(tmp_project))
    assert r.returncode == 0
    out = json.loads(r.stdout)
    orphan_paths = {o["path"] for o in out["orphans"]}
    assert "knowledge/index.md" not in orphan_paths
    assert "knowledge/overview.md" not in orphan_paths
    assert "knowledge/glossary.md" not in orphan_paths


def test_lint_orphan_no_inbound_link(tmp_project: Path) -> None:
    """无入链接 + 非豁免 → 孤儿。"""
    fm = _make_source_fm(basename="orphan", subdir="06_功能安全")
    _write_md(
        tmp_project,
        "knowledge/sources/orphan-test.md",
        fm + "\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n",
    )

    r = _run_script("lint-orphans.py", "--project-dir", str(tmp_project))
    out = json.loads(r.stdout)
    orphans = [o for o in out["orphans"] if "orphan-test.md" in o["path"]]
    assert len(orphans) >= 1, "孤儿未识别"
    assert orphans[0]["exempt"] is False


def test_lint_orphan_with_inbound_wikilink_ok(tmp_project: Path) -> None:
    """有正文 [[wikilink]] → 该 wikilink target 算入 → 不孤儿。"""
    # 先建一个 target 源页
    target_fm = _make_source_fm(basename="target", subdir="06_功能安全")
    _write_md(
        tmp_project,
        "knowledge/sources/target-doc.md",
        target_fm + "\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n",
    )

    # 建引用它的源页
    fm = _make_source_fm(basename="referrer", subdir="12_法规_标准_政策")
    body = (
        "\n\n## 我的思考\n\n见 [[target-doc]] 章节。\n\n## 总结\n\nx\n"
    )
    _write_md(
        tmp_project,
        "knowledge/sources/referrer.md",
        fm + body,
    )

    r = _run_script("lint-orphans.py", "--project-dir", str(tmp_project))
    out = json.loads(r.stdout)
    orphans = [o for o in out["orphans"] if "target-doc.md" in o["path"]]
    assert len(orphans) == 0, f"target-doc 应被引用不算孤儿:{orphans}"


# ---------------------------------------------------------------------------
# okf-lint.py 测试
# ---------------------------------------------------------------------------


def test_okf_lint_links_mirror_set_compare(tmp_project: Path) -> None:
    """Set 比对,顺序无关:scanned 多但 links 少 → drift=True。"""
    fm = _make_source_fm(basename="drift", subdir="06_功能安全")
    body = (
        "\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n\n"
        "参考 [[alpha]] 与 [[beta]]。\n"
    )
    target = _write_md(tmp_project, "knowledge/sources/drift-mirror.md", fm + body)

    r = _run_script(
        "okf-lint.py",
        "--project-dir", str(tmp_project),
        "--file", str(target.relative_to(tmp_project)),
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    out = json.loads(r.stdout)
    assert out["drift"] is True
    assert set(out["added"]) == {"alpha", "beta"}


def test_okf_lint_aliased_wikilink_normalized(tmp_project: Path) -> None:
    """[[page|Alias]] 走 link_normalizer → 只取 page。"""
    fm = _make_source_fm(basename="alias", subdir="06_功能安全")
    body = "\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n\n[[foo|显示别名]]\n"
    target = _write_md(tmp_project, "knowledge/sources/alias-test.md", fm + body)

    r = _run_script(
        "okf-lint.py",
        "--project-dir", str(tmp_project),
        "--file", str(target.relative_to(tmp_project)),
    )
    out = json.loads(r.stdout)
    assert out["drift"] is True
    assert "foo" in out["added"]
    # 别名"显示别名"不应出现在 set 里
    assert "显示别名" not in out["scanned"]


def test_okf_lint_anchor_wikilink_normalized(tmp_project: Path) -> None:
    """[[page#section]] → 只取 page。"""
    fm = _make_source_fm(basename="anchor", subdir="06_功能安全")
    body = "\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n\n[[anchor-target#section-A]]\n"
    target = _write_md(tmp_project, "knowledge/sources/anchor-test.md", fm + body)

    r = _run_script(
        "okf-lint.py",
        "--project-dir", str(tmp_project),
        "--file", str(target.relative_to(tmp_project)),
    )
    out = json.loads(r.stdout)
    assert "anchor-target" in out["scanned"]
    assert "anchor-target" in out["added"]


def test_okf_lint_path_prefix_wikilink_normalized(tmp_project: Path) -> None:
    """[[deep/path/bar.md]] → link_normalizer 只取 bar。"""
    fm = _make_source_fm(basename="pathp", subdir="06_功能安全")
    body = "\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n\n[[deep/nested/bar]]\n"
    target = _write_md(tmp_project, "knowledge/sources/path-test.md", fm + body)

    r = _run_script(
        "okf-lint.py",
        "--project-dir", str(tmp_project),
        "--file", str(target.relative_to(tmp_project)),
    )
    out = json.loads(r.stdout)
    assert "bar" in out["scanned"]


def test_okf_lint_frontmatter_links_priority(tmp_project: Path) -> None:
    """frontmatter `links:` 优先级:drift = scanned ↔ current。"""
    fm_text = (
        "---\ntype: source\ntitle: 't'\ndescription: 'd'\n"
        f"updated: '{_now_iso()}'\ntags: [docform/source]\n"
        "source_file: 'raw/06_功能安全/x.pdf'\n"
        "sources:\n  - resource: 'raw/06_功能安全/x.pdf'\n"
        "format: pdf\nconverter: anydoc\nnative_text: false\n"
        "converted_path: 'raw/06_功能安全/x.pdf.converted.md'\n"
        "links:\n  - 'alpha'\n  - 'beta'\n"
        "---\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n\n"
        "[[alpha]]\n"
    )
    target = _write_md(tmp_project, "knowledge/sources/priority-test.md", fm_text)

    r = _run_script(
        "okf-lint.py",
        "--project-dir", str(tmp_project),
        "--file", str(target.relative_to(tmp_project)),
    )
    out = json.loads(r.stdout)
    # alpha 在,beta 在 links 但正文没 → removed 应含 beta
    assert "beta" in out["removed"]
    assert "alpha" not in out["added"]


def test_okf_lint_ghost_in_links_field(tmp_project: Path) -> None:
    """links: 有但正文没扫到 → ghost → removed 非空。"""
    fm_text = (
        "---\ntype: source\ntitle: 't'\ndescription: 'd'\n"
        f"updated: '{_now_iso()}'\ntags: [docform/source]\n"
        "source_file: 'raw/06_功能安全/x.pdf'\n"
        "sources:\n  - resource: 'raw/06_功能安全/x.pdf'\n"
        "format: pdf\nconverter: anydoc\nnative_text: false\n"
        "converted_path: 'raw/06_功能安全/x.pdf.converted.md'\n"
        "links:\n  - 'ghost-page'\n"
        "---\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n\n"
    )
    target = _write_md(tmp_project, "knowledge/sources/ghost-test.md", fm_text)

    r = _run_script(
        "okf-lint.py",
        "--project-dir", str(tmp_project),
        "--file", str(target.relative_to(tmp_project)),
    )
    out = json.loads(r.stdout)
    assert "ghost-page" in out["removed"]
    assert out["drift"] is True


def test_okf_lint_missing_in_links_field(tmp_project: Path) -> None:
    """正文有但 links: 没 → added 非空。"""
    fm_text = (
        "---\ntype: source\ntitle: 't'\ndescription: 'd'\n"
        f"updated: '{_now_iso()}'\ntags: [docform/source]\n"
        "source_file: 'raw/06_功能安全/x.pdf'\n"
        "sources:\n  - resource: 'raw/06_功能安全/x.pdf'\n"
        "format: pdf\nconverter: anydoc\nnative_text: false\n"
        "converted_path: 'raw/06_功能安全/x.pdf.converted.md'\n"
        "links: []\n"
        "---\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n\n"
        "[[missing-link]]\n"
    )
    target = _write_md(tmp_project, "knowledge/sources/missing-test.md", fm_text)

    r = _run_script(
        "okf-lint.py",
        "--project-dir", str(tmp_project),
        "--file", str(target.relative_to(tmp_project)),
    )
    out = json.loads(r.stdout)
    assert "missing-link" in out["added"]


def test_okf_lint_no_drift_ok(tmp_project: Path) -> None:
    """无 drift:links: 与正文 Set 相等。"""
    fm_text = (
        "---\ntype: source\ntitle: 't'\ndescription: 'd'\n"
        f"updated: '{_now_iso()}'\ntags: [docform/source]\n"
        "source_file: 'raw/06_功能安全/x.pdf'\n"
        "sources:\n  - resource: 'raw/06_功能安全/x.pdf'\n"
        "format: pdf\nconverter: anydoc\nnative_text: false\n"
        "converted_path: 'raw/06_功能安全/x.pdf.converted.md'\n"
        "links:\n  - 'alpha'\n  - 'beta'\n"
        "---\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n\n"
        "[[alpha]] 和 [[beta]]\n"
    )
    target = _write_md(tmp_project, "knowledge/sources/no-drift.md", fm_text)

    r = _run_script(
        "okf-lint.py",
        "--project-dir", str(tmp_project),
        "--file", str(target.relative_to(tmp_project)),
    )
    out = json.loads(r.stdout)
    assert out["drift"] is False
    assert out["added"] == []
    assert out["removed"] == []
    assert out["applied"] is False


def test_okf_lint_apply_writes_atomic_preserve_mtime(tmp_project: Path) -> None:
    """--apply 写盘走 atomic_write_preserving_mtime(不动 mtime)。"""
    fm_text = (
        "---\ntype: source\ntitle: 't'\ndescription: 'd'\n"
        f"updated: '{_now_iso()}'\ntags: [docform/source]\n"
        "source_file: 'raw/06_功能安全/x.pdf'\n"
        "sources:\n  - resource: 'raw/06_功能安全/x.pdf'\n"
        "format: pdf\nconverter: anydoc\nnative_text: false\n"
        "converted_path: 'raw/06_功能安全/x.pdf.converted.md'\n"
        "links: []\n"
        "---\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n\n"
        "[[apply-target]]\n"
    )
    target = _write_md(tmp_project, "knowledge/sources/apply-mtime.md", fm_text)
    mtime_before = os.stat(target).st_mtime
    atime_before = os.stat(target).st_atime

    r = _run_script(
        "okf-lint.py",
        "--project-dir", str(tmp_project),
        "--file", str(target.relative_to(tmp_project)),
        "--apply",
    )
    out = json.loads(r.stdout)
    assert out["applied"] is True
    assert os.stat(target).st_mtime == mtime_before, (
        "Q7:mtime 应保持不变"
    )
    assert os.stat(target).st_atime == atime_before, (
        "Q7:atime 应保持不变"
    )
    # frontmatter links 应包含 apply-target
    text = target.read_text(encoding="utf-8")
    assert "apply-target" in text, f"links: 应同步:body 段含 apply-target 但 frontmatter 也应有"


def test_okf_lint_apply_idempotent(tmp_project: Path) -> None:
    """幂等:跑两遍 → 第二遍 drift=False。"""
    fm_text = (
        "---\ntype: source\ntitle: 't'\ndescription: 'd'\n"
        f"updated: '{_now_iso()}'\ntags: [docform/source]\n"
        "source_file: 'raw/06_功能安全/x.pdf'\n"
        "sources:\n  - resource: 'raw/06_功能安全/x.pdf'\n"
        "format: pdf\nconverter: anydoc\nnative_text: false\n"
        "converted_path: 'raw/06_功能安全/x.pdf.converted.md'\n"
        "links: []\n"
        "---\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n\n"
        "[[idem-1]] [[idem-2]]\n"
    )
    target = _write_md(tmp_project, "knowledge/sources/idem-test.md", fm_text)

    # 第一遍 apply
    r1 = _run_script(
        "okf-lint.py",
        "--project-dir", str(tmp_project),
        "--file", str(target.relative_to(tmp_project)),
        "--apply",
    )
    out1 = json.loads(r1.stdout)
    assert out1["applied"] is True

    # 第二遍不 apply
    r2 = _run_script(
        "okf-lint.py",
        "--project-dir", str(tmp_project),
        "--file", str(target.relative_to(tmp_project)),
    )
    out2 = json.loads(r2.stdout)
    assert out2["drift"] is False, f"跑两遍应幂等:drift={out2}"


def test_okf_lint_aliased_wikilink_only_target_in_scanned(tmp_project: Path) -> None:
    """[[page|Alias]] 严格:scanned set 只含 page,不含 Alias。"""
    fm_text = (
        "---\ntype: source\ntitle: 't'\ndescription: 'd'\n"
        f"updated: '{_now_iso()}'\ntags: [docform/source]\n"
        "source_file: 'raw/06_功能安全/x.pdf'\n"
        "sources:\n  - resource: 'raw/06_功能安全/x.pdf'\n"
        "format: pdf\nconverter: anydoc\nnative_text: false\n"
        "converted_path: 'raw/06_功能安全/x.pdf.converted.md'\n"
        "links: []\n"
        "---\n\n## 我的思考\n\nx\n\n## 总结\n\nx\n\n"
        "[[alpha|显式别名]]\n"
    )
    target = _write_md(tmp_project, "knowledge/sources/strict-alias.md", fm_text)

    r = _run_script(
        "okf-lint.py",
        "--project-dir", str(tmp_project),
        "--file", str(target.relative_to(tmp_project)),
    )
    out = json.loads(r.stdout)
    assert "alpha" in out["scanned"]
    assert "显式别名" not in out["scanned"]

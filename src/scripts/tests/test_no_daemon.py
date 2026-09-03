"""test_no_daemon.py — C10.1 AST 静态扫描。

扫描 src/scripts/*.py(本组 _common / init-vault / check-deps),断言:
    - 不出现 ast 节点:input / sys.stdin.read / sys.stdin.readline / getpass / select.select
    - 不出现 daemon 模式:HTTPServer / TCPServer / BaseHTTPRequestHandler
    - 不出现 while True:pass(死循环)

设计依据:
    - DESIGN.md §1.4 NFR-1(无 daemon)
    - DESIGN.md §3.4 Q10(scripts 严禁交互)
    - DESIGN.md §4 测试对齐(test_no_daemon_static_scan)
    - DESIGN.md §5.1 C10.1 lint 静态扫描断言

CLI:
    pytest tests/test_no_daemon.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

# 把 scripts/ 目录加入 sys.path,以便 import _common
import sys

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _common import assert_no_input_calls  # noqa: E402


# ---------------------------------------------------------------------------
# fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def scripts_dir() -> Path:
    """提供本组 scripts/ 目录路径(_common / init-vault / check-deps)。"""
    return SCRIPTS_DIR


def _target_scripts(scripts_dir: Path) -> list[Path]:
    """返回本组 .py 文件列表(排除本测试文件自身)。"""
    targets: list[Path] = []
    for py_file in sorted(scripts_dir.glob("*.py")):
        if py_file.name.startswith("test_"):
            continue
        if py_file.name.startswith("_"):
            pass
        targets.append(py_file)
    return targets


# ---------------------------------------------------------------------------
# AST 自检测试
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "script_name",
    [
        "_common.py", "init-vault.py", "check-deps.py",
        # 阶段 C-1.2.1 ingest 组骨架(6 个 .py,2026-09-03 落地)
        "append-log.py", "ensure-dirs.py", "convert-to-md.py",
        "safe-mv.py", "validate-frontmatter.py", "validate-proposal.py",
        # 阶段 C-1.3 query 组(9 个 .py,2026-09-03 落地)
        "check-qmd.py", "generate-analysis-page.py",
        "lint-query-output.py", "migrate-analysis-skeleton.py", "okf-reader.py",
        # 阶段 C-1.4 lint 组(3 个 .py,2026-09-03 落地)
        "lint.py", "lint-orphans.py", "okf-lint.py",
    ],
)
def test_no_input_calls_in_scripts(scripts_dir: Path, script_name: str) -> None:
    """每个 .py 都通过 C10.1 AST 自检(无 input / stdin / getpass / select / 死循环 / daemon)。"""
    script_path = scripts_dir / script_name
    assert script_path.exists(), f"脚本不存在: {script_path}"

    violations = assert_no_input_calls(script_path)
    assert violations == [], (
        f"C10.1 静态扫描发现违规项 ({script_name}):\n"
        + "\n".join(f"  - {v}" for v in violations)
    )


def test_all_target_scripts_scanned(scripts_dir: Path) -> None:
    """fixture 完整性:确保 _common / init-vault / check-deps 都在扫描范围内。"""
    expected = {"_common.py", "init-vault.py", "check-deps.py"}
    found = {p.name for p in _target_scripts(scripts_dir)}
    missing = expected - found
    assert not missing, f"以下脚本未找到,无法 AST 自检: {missing}"


def test_atomic_write_preserving_mtime_4_steps(scripts_dir: Path) -> None:
    """Q7 v0.5.3 4 步流程存根:验证 _common.atomic_write_preserving_mtime 真的落盘且还原 mtime。

    本测试不强求覆盖 Q7 全部边界,只断言:
        1. 函数可调用
        2. 文件内容被正确写入
        3. 调用后 mtime 保持不变(只要 stat 未变)

    完整 Q7 测试套件在后续 _common.py 单测轮次中扩展。
    """
    import os
    import tempfile

    from _common import atomic_write_preserving_mtime

    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "fixture.md"
        target.write_text("初始内容\n", encoding="utf-8")
        original_mtime = os.stat(target).st_mtime
        original_atime = os.stat(target).st_atime

        atomic_write_preserving_mtime(target, "新内容\n")

        assert target.read_text(encoding="utf-8") == "新内容\n"
        assert os.stat(target).st_mtime == original_mtime
        assert os.stat(target).st_atime == original_atime


def test_link_normalizer_alias_anchor_path() -> None:
    """_common.link_normalizer 行为规约:aliases / #anchor / path prefix 归一。"""
    from _common import link_normalizer

    assert link_normalizer("[[page|Alias]]") == "page"
    assert link_normalizer("[[page#section]]") == "page"
    assert link_normalizer("[[../knowledge/foo.md|alias]]") == "foo"
    assert link_normalizer("foo.md") == "foo"
    assert link_normalizer("../knowledge/foo.md") == "foo"
    assert link_normalizer("[[deep/path/bar.md]]") == "bar"
    assert link_normalizer("") == ""
    assert link_normalizer("   [[page]]   ") == "page"


def test_derive_raw_category_basics() -> None:
    """_common.derive_raw_category 行为规约:sources[0].resource split('/')[1]。"""
    from _common import derive_raw_category

    assert derive_raw_category("raw/06_功能安全/foo.pdf") == "06_功能安全"
    assert derive_raw_category("raw/15_算法/bar.md") == "15_算法"
    assert derive_raw_category("") == ""
    assert derive_raw_category("notraw/foo") == ""
    assert derive_raw_category("raw") == ""
    assert derive_raw_category("raw/") == ""


def test_assert_no_input_calls_detects_input() -> None:
    """AST 自检必须能识别 input() 调用。"""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "bad.py"
        bad.write_text('x = input("prompt:")\n', encoding="utf-8")
        violations = assert_no_input_calls(bad)
        assert any("input" in v for v in violations), f"未识别 input 调用: {violations}"


def test_assert_no_input_calls_detects_dead_loop() -> None:
    """AST 自检必须能识别 while True: 死循环。"""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "deadloop.py"
        bad.write_text("while True:\n    pass\n", encoding="utf-8")
        violations = assert_no_input_calls(bad)
        assert any("while True" in v for v in violations), f"未识别死循环: {violations}"
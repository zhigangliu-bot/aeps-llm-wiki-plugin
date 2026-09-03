"""scripts/ 内部基础设施。

本模块为 scripts/ 下所有 .py 复用,不接受外部 import(下划线前缀)。
提供 5 个核心工具:

- atomic_write_preserving_mtime:Q7 v0.5.3 死循环防护 4 步流程(stat → write → utime)
- assert_no_input_calls:lint C10.1 AST 自检,扫脚本中是否有 input / sys.stdin / getpass / select
- link_normalizer:aliases / #anchor / path prefix 归一
- derive_raw_category:从 sources[0].resource 派生 raw_category
- git_dirty_check:脏状态检查 + --allow-dirty 放行 + 干净时自动 stash

约束:
- 只用 stdlib(os / pathlib / subprocess / ast / re),不引入新依赖
- encoding="utf-8" 写盘;BOM 保留(utf-8-sig 双向兼容)
- 函数 docstring 中文为主,变量名英文
- 不读 stdin、不开 daemon、不调 input
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Q7 v0.5.3 死循环防护 4 步流程
# ---------------------------------------------------------------------------


def atomic_write_preserving_mtime(path: Path, content: str, encoding: str = "utf-8") -> None:
    """保留 mtime/atime 的写盘(Q7 v0.5.3 死循环防护 4 步流程)。

    适用场景:lint --fix / safe-mv overwrite / okf-lint links-mirror 等所有写盘脚本,
    业务层"机械修复"不应触发 frontmatter `updated` 字段或 git mtime 变更。

    4 步流程:
        1. stat 取原始 atime + mtime
        2. write_text(或 atomic:.tmp + os.replace)
        3. utime(atime + mtime)双还原
        4. 文件不存在 / 只读时抛 OSError(强制外层处理)

    Args:
        path: 目标文件路径(Path 对象)。
        content: 待写入文本。
        encoding: 文件编码,默认 utf-8(BOM 保留)。

    Raises:
        OSError: 文件不存在 / 只读 / 父目录不存在。
    """
    if not path.exists():
        raise OSError(f"文件不存在,无法保留 mtime: {path}")
    if not os.access(path, os.W_OK):
        raise OSError(f"文件只读,无法写入: {path}")

    stat = os.stat(path)
    original_atime = stat.st_atime
    original_mtime = stat.st_mtime

    path.write_text(content, encoding=encoding)

    os.utime(path, (original_atime, original_mtime))


# ---------------------------------------------------------------------------
# lint C10.1 AST 自检
# ---------------------------------------------------------------------------


def assert_no_input_calls(source_path: Path) -> list[str]:
    """扫描 .py 源,断言不出现 input / sys.stdin / getpass / select / 死循环。

    用于 lint C10.1 + scripts/ 无 daemon 硬契约(Q10)。

    检查项:
        - ast.Call:input / sys.stdin.read / sys.stdin.readline / getpass / select.select
        - ast.While:test 是常量 True(死循环风险)
        - http.server.HTTPServer / socketserver.TCPServer / BaseHTTPRequestHandler(daemon)

    Args:
        source_path: 待扫描的 .py 文件。

    Returns:
        违规条目列表(空 list = 通过)。每条形如 "<行号>: <违规描述>"。
    """
    violations: list[str] = []

    try:
        source = source_path.read_text(encoding="utf-8")
    except OSError:
        return [f"无法读取源文件: {source_path}"]

    try:
        tree = ast.parse(source, filename=str(source_path))
    except SyntaxError as e:
        return [f"语法错误,AST 解析失败: {e.msg} (line {e.lineno})"]

    forbidden_names = {"input", "getpass"}
    forbidden_attrs_chain = [
        ("sys", "stdin"),
        ("sys", "stdin", "read"),
        ("sys", "stdin", "readline"),
    ]
    forbidden_callables = {
        ("select", "select"),
        ("http", "server", "HTTPServer"),
        ("socketserver", "TCPServer"),
        ("http", "server", "BaseHTTPRequestHandler"),
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            chain = _extract_call_chain(node.func)
            if chain in forbidden_callables:
                violations.append(
                    f"{node.lineno}: 禁止的调用 {'.'.join(chain)}(daemon / 服务接口)"
                )
                continue

            if len(chain) == 1 and chain[0] in forbidden_names:
                violations.append(f"{node.lineno}: 禁止调用 {chain[0]}(...)")
                continue

            if len(chain) >= 2 and chain in forbidden_attrs_chain:
                violations.append(f"{node.lineno}: 禁止调用 {'.'.join(chain)}(...)")

        elif isinstance(node, ast.While):
            if isinstance(node.test, ast.Constant) and node.test.value is True:
                violations.append(f"{node.lineno}: 死循环风险(while True:)")

    return violations


def _extract_call_chain(func: ast.AST) -> tuple[str, ...]:
    """从 ast.Call 的 func 节点抽取属性链。

    例如 sys.stdin.read → ("sys", "stdin", "read")。
    无法识别时返回空 tuple。
    """
    chain: list[str] = []
    node = func
    while isinstance(node, ast.Attribute):
        chain.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        chain.append(node.id)
        chain.reverse()
        return tuple(chain)
    return ()


# ---------------------------------------------------------------------------
# link_normalizer:aliases / #anchor / path prefix 归一
# ---------------------------------------------------------------------------


def link_normalizer(link: str) -> str:
    """wikilink / markdown link 归一化。

    规则:
        - [[page|Alias]]        → [[page]]
        - [[page#section]]      → [[page]]
        - [[../path/foo.md|alias]] → [[foo]]
        - foo.md                 → foo
        - ../knowledge/foo.md   → foo

    Args:
        link: 原始链接字符串。

    Returns:
        归一化后的 slug(无扩展名 / 无 anchor / 无 alias)。
    """
    if not link:
        return ""

    s = link.strip()

    if s.startswith("[[") and s.endswith("]]"):
        s = s[2:-2].strip()
        if "|" in s:
            s = s.split("|", 1)[0]
        if "#" in s:
            s = s.split("#", 1)[0]
        s = Path(s).name
    else:
        if "|" in s:
            s = s.split("|", 1)[0]
        s = Path(s).name

    if s.endswith(".md"):
        s = s[:-3]

    return s


# ---------------------------------------------------------------------------
# derive_raw_category:从 sources[0].resource 派生 raw_category
# ---------------------------------------------------------------------------


def derive_raw_category(resource: str) -> str:
    """从 sources[0].resource 派生 raw_category。

    规则:resource 形如 "raw/<subdir>/<file>.<ext>",split('/')[1] 即 <subdir>。
    异常路径(不以 raw/ 开头 / 层级不足)→ 返回 ""(调用方按缺省处理)。

    Args:
        resource: sources[0].resource 字符串。

    Returns:
        raw 子目录名(如 "06_功能安全"),失败返回 ""。
    """
    if not resource:
        return ""
    parts = resource.split("/")
    if len(parts) < 2:
        return ""
    if parts[0] != "raw":
        return ""
    return parts[1]


# ---------------------------------------------------------------------------
# git_dirty_check:脏状态检查 + --allow-dirty 放行 + 干净时自动 stash
# ---------------------------------------------------------------------------


def git_dirty_check(project_dir: str, allow_dirty: bool = False) -> dict[str, Any]:
    """检查 project_dir 是否是 git 仓库 + 工作树是否脏。

    行为:
        - 非 git 仓库 → is_repo=False,直接放行
        - 干净工作树 → 自动 git stash(便于 lint --fix 安全锁测试)
        - 脏 + allow_dirty=True → 放行但不打 stash
        - 脏 + allow_dirty=False → 返回 {"allowed": False}

    Args:
        project_dir: 项目根目录(默认 ".")。
        allow_dirty: 是否放行脏状态。

    Returns:
        dict: {"is_repo": bool, "dirty": bool, "stashed": bool, "allowed": bool}
    """
    result: dict[str, Any] = {
        "is_repo": False,
        "dirty": False,
        "stashed": False,
        "allowed": True,
    }

    cwd = Path(project_dir).resolve()
    git_dir = cwd / ".git"
    if not git_dir.exists():
        return result

    result["is_repo"] = True

    try:
        status_proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        result["allowed"] = False
        result["error"] = f"git status 调用失败: {e}"
        return result

    if status_proc.returncode != 0:
        result["allowed"] = False
        result["error"] = f"git status 非零退出: {status_proc.stderr.strip()}"
        return result

    dirty = bool(status_proc.stdout.strip())
    result["dirty"] = dirty

    if not dirty:
        stash_proc = subprocess.run(
            ["git", "stash", "--include-untracked"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        result["stashed"] = stash_proc.returncode == 0
        if stash_proc.returncode != 0:
            result["allowed"] = False
            result["error"] = f"git stash 失败: {stash_proc.stderr.strip()}"
        return result

    if allow_dirty:
        result["allowed"] = True
        return result

    result["allowed"] = False
    result["error"] = "工作树脏,需要 --allow-dirty 放行"
    return result


# ---------------------------------------------------------------------------
# JSON 输出工具(供 init-vault.py / check-deps.py 复用)
# ---------------------------------------------------------------------------


def emit_json(payload: dict[str, Any]) -> None:
    """统一 JSON 输出到 stdout(ensure_ascii=False 保证中文不转义)。"""
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    print("scripts/_common.py:内部基础设施模块,不直接执行。请调 init-vault.py / check-deps.py。")
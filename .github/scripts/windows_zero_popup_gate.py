#!/usr/bin/env python3
"""AST and lexical Windows zero-console-popup static gate (R4 / Guardrail P1.5).

[Role]
Verifies that Node.js child-process launches (`spawn`, `spawnSync`, `exec`, `execSync`,
`execFile`, `execFileSync`, `fork`) pass `windowsHide: true` on every call site, and that
Python subprocess wrappers across `mindie-agent`, all 7 host plugins, and shared runtime
components enforce `subprocess.CREATE_NO_WINDOW` without comment/candidate-fallback blind spots.

[Invariants]
- Every Node.js child-process call site is inspected after masking comments (`//`, `/* */`),
  string/template literals, and regex literals so JSDoc prose or sibling calls never mask an
  unhidden spawn; required Node host entrypoints must exist and contain `>= 1` call.
- Refactored Python candidate tuples never short-circuit past co-existing modules: the first
  present candidate must carry `CREATE_NO_WINDOW` in executable AST, and every additional
  present candidate must have zero unguarded `subprocess` spawns and actively invoke a
  windowless helper imported from the primary wrapper (or carry `CREATE_NO_WINDOW` itself).
- Runs purely on Python stdlib (`ast`, `re`, `pathlib`) before `mindie_knowledge` import checks.

[Timeouts & Locks]
- Pure synchronous local file parsing with zero subprocesses, network I/O, or locks.

[Side-Effect Policy]
- Strictly read-only static inspection of repository checkouts.
"""

from __future__ import annotations

import ast
from pathlib import Path
import re
from typing import Sequence

WINDOWS_NODE_WINDOWLESS_FILES: tuple[tuple[str, str], ...] = (
    ("mindie-agent-dsh", "host3.mjs"),
    ("mindie-agent-oc", "plugins/mindie-agent/opencode_host.mjs"),
)

NODE_SCANNED_REPOS: tuple[str, ...] = ("mindie-agent-dsh", "mindie-agent-oc")
NODE_SKIP_DIRS: frozenset[str] = frozenset({".git", "node_modules", "tests", ".venv", "dist", "build", "coverage"})

WINDOWS_NO_WINDOW_REQUIRED_FILES: tuple[tuple[str, str | tuple[str, ...]], ...] = (
    ("mindie-agent-dsh", "scripts/setup_process.py"),
    ("mindie-agent-dsh", "scripts/knowledge_mcp.py"),
    ("mindie-agent-agy", "plugins/mindie-agent/scripts/bounded.py"),
    ("mindie-agent-agy", "plugins/mindie-agent/scripts/component_update.py"),
    ("mindie-agent-wb", "plugins/mindie-agent/scripts/bounded.py"),
    ("mindie-agent-wb", "plugins/mindie-agent/scripts/component_update.py"),
    ("mindie-agent-oc", "plugins/mindie-agent/scripts/bounded.py"),
    ("mindie-agent-oc", "plugins/mindie-agent/scripts/component_update.py"),
    ("mindie-agent-oc", "plugins/mindie-agent/scripts/mindie_launch.py"),
    ("mindie-agent-cc", "scripts/bounded_win32.py"),
    ("mindie-agent-codex", "plugins/mindie-agent/scripts/windows_process.py"),
    ("mindie-agent-kimi", "scripts/bounded.py"),
    ("mindie-bench", ("src/mindie_bench/runner/host_platform.py", "src/mindie_bench/runner/process.py")),
    ("knowledge", "mindie_knowledge/windows_process.py"),
    ("knowledge", "mindie_knowledge/loop/process.py"),
    ("knowledge", "mindie_knowledge/gitread.py"),
    ("knowledge", "mindie_knowledge/release_http.py"),
    ("knowledge", "mindie_knowledge/graded/experiment_ledger.py"),
    ("diagnostics", "mindie_diagnostics/platform_service.py"),
    ("diagnostics", ("mindie_diagnostics/github_transport.py", "mindie_diagnostics/reporter.py")),
    ("remote-dev", "remote_dev/core/local_process.py"),
    ("coordinator", "mindie_coordinator/service_client.py"),
)

# Optional split subprocess modules verified whenever present in a repository checkout.
WINDOWS_NO_WINDOW_COMPANION_FILES: tuple[tuple[str, str], ...] = (
    ("mindie-bench", "src/mindie_bench/runner/termination.py"),
    ("diagnostics", "mindie_diagnostics/reporting_commands.py"),
    ("diagnostics", "mindie_diagnostics/reporting_runtime.py"),
)

INDEPENDENT_ONLY_GATED_REPOS: frozenset[str] = frozenset({"mindie-agent-oc"})
_PY_SPAWN_ATTRS: frozenset[str] = frozenset({"Popen", "run", "call", "check_call", "check_output"})
_JS_REGEX_PREFIX_KEYWORDS: frozenset[str] = frozenset(
    {"return", "throw", "case", "typeof", "void", "delete", "in", "instanceof", "new", "await", "yield", "of"}
)
_JS_REGEX_PREFIX_CHARS: frozenset[str] = frozenset("=(,[{:;!&|?+-~^%<>")
_JS_CHILD_CALL_RE = re.compile(
    r"(?:(?<!\.)\b(?:spawn|spawnSync|exec|execSync|execFile|execFileSync|fork)"
    r"|\b(?:child_process|cp)\.(?:spawn|spawnSync|exec|execSync|execFile|execFileSync|fork))\s*\("
)


def _resolve_repo(repo_name: str, siblings_roots: Sequence[Path], extra_repos: dict[str, Path] | None = None) -> Path | None:
    for root in siblings_roots:
        candidate = root / repo_name
        if (candidate / ".git").exists():
            return candidate
    if extra_repos and repo_name in extra_repos:
        return extra_repos[repo_name]
    return None


def _mask_js_non_code(source: str) -> str:
    """Replace JS comments, string/template text, and regex bodies with spaces (preserving newlines)."""
    out: list[str] = []
    n = len(source)
    i = 0
    prev_sig_char = ""
    prev_word = ""
    tpl_brace_stack: list[int] = []

    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            out.append("  ")
            i += 2
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if ch == "/" and nxt == "*":
            out.append("  ")
            i += 2
            while i < n and not (source[i] == "*" and i + 1 < n and source[i + 1] == "/"):
                out.append("\n" if source[i] == "\n" else " ")
                i += 1
            if i < n:
                out.append("  ")
                i += 2
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(quote)
            i += 1
            while i < n and source[i] != quote:
                if source[i] == "\\" and i + 1 < n:
                    out.append(" ")
                    out.append("\n" if source[i + 1] == "\n" else " ")
                    i += 2
                    continue
                out.append("\n" if source[i] == "\n" else " ")
                i += 1
            if i < n:
                out.append(quote)
                i += 1
            prev_sig_char = quote
            prev_word = ""
            continue
        if ch == "`" or (ch == "}" and tpl_brace_stack and tpl_brace_stack[-1] == 0):
            if ch == "}":
                tpl_brace_stack.pop()
            out.append(ch)
            i += 1
            while i < n:
                if source[i] == "\\" and i + 1 < n:
                    out.append(" ")
                    out.append("\n" if source[i + 1] == "\n" else " ")
                    i += 2
                    continue
                if source[i] == "$" and i + 1 < n and source[i + 1] == "{":
                    out.append("${")
                    tpl_brace_stack.append(0)
                    i += 2
                    prev_sig_char = "{"
                    prev_word = ""
                    break
                if source[i] == "`":
                    out.append("`")
                    i += 1
                    prev_sig_char = "`"
                    prev_word = ""
                    break
                out.append("\n" if source[i] == "\n" else " ")
                i += 1
            continue
        if ch == "/" and (not prev_sig_char or prev_sig_char in _JS_REGEX_PREFIX_CHARS or prev_word in _JS_REGEX_PREFIX_KEYWORDS):
            out.append("/")
            i += 1
            in_class = False
            while i < n:
                rc = source[i]
                if rc == "\\" and i + 1 < n:
                    out.append("  ")
                    i += 2
                    continue
                if rc == "[":
                    in_class = True
                elif rc == "]":
                    in_class = False
                elif rc == "/" and not in_class:
                    out.append("/")
                    i += 1
                    while i < n and source[i].isalpha():
                        out.append(source[i])
                        i += 1
                    break
                if rc == "\n":
                    out.append("\n")
                    i += 1
                    break
                out.append(" ")
                i += 1
            prev_sig_char = "/"
            prev_word = ""
            continue
        if tpl_brace_stack:
            if ch == "{":
                tpl_brace_stack[-1] += 1
            elif ch == "}":
                tpl_brace_stack[-1] -= 1
        if ch.isalpha() or ch in ("_", "$"):
            start = i
            while i < n and (source[i].isalnum() or source[i] in ("_", "$")):
                out.append(source[i])
                i += 1
            prev_word = source[start:i]
            prev_sig_char = prev_word[-1]
            continue
        out.append(ch)
        if not ch.isspace():
            prev_sig_char = ch
            prev_word = ""
        i += 1
    return "".join(out)


def inspect_node_windowless_file(path: Path, *, require_spawns: bool) -> list[str]:
    masked = _mask_js_non_code(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    call_count = 0
    for match in _JS_CHILD_CALL_RE.finditer(masked):
        call_count += 1
        open_idx = match.end() - 1
        depth = 1
        pos = open_idx + 1
        while pos < len(masked) and depth > 0:
            if masked[pos] == "(":
                depth += 1
            elif masked[pos] == ")":
                depth -= 1
            pos += 1
        call_slice = masked[open_idx:pos]
        if depth != 0 or not re.search(r"\bwindowsHide\s*:\s*true\b", call_slice):
            lineno = masked.count("\n", 0, match.start()) + 1
            call_name = match.group(0).rstrip("(").strip()
            errors.append(f"line {lineno} `{call_name}(...)` missing `windowsHide: true` (Windows console popup risk)")
    if require_spawns and call_count == 0:
        errors.append("expected >= 1 child_process spawn call with `windowsHide: true`, found 0")
    return errors


def _inspect_python_ast(
    path: Path,
) -> tuple[bool, bool, list[int], list[int], dict[str, set[str]], set[str]]:
    """Return (has_cnw, calls_wk, spawn_lines, unguarded_spawn_lines, imports_by_stem, called_names)."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    has_cnw = False
    calls_window_kwargs = False
    spawn_lines: list[int] = []
    unguarded_spawn_lines: list[int] = []
    imported_by_stem: dict[str, set[str]] = {}
    called_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "CREATE_NO_WINDOW":
            has_cnw = True
        elif isinstance(node, ast.Name) and node.id == "CREATE_NO_WINDOW":
            has_cnw = True
        elif isinstance(node, ast.ImportFrom) and node.module:
            stem = node.module.rsplit(".", 1)[-1]
            names = imported_by_stem.setdefault(stem, set())
            for alias in node.names:
                bound = alias.asname or alias.name
                names.add(bound)
                if alias.name == "CREATE_NO_WINDOW":
                    has_cnw = True
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name):
                called_names.add(fn.id)
                if fn.id == "subprocess_window_kwargs":
                    calls_window_kwargs = True
                if (
                    fn.id == "getattr"
                    and len(node.args) >= 2
                    and isinstance(node.args[1], ast.Constant)
                    and node.args[1].value == "CREATE_NO_WINDOW"
                ):
                    has_cnw = True
            elif isinstance(fn, ast.Attribute):
                called_names.add(fn.attr)
                if fn.attr == "subprocess_window_kwargs":
                    calls_window_kwargs = True
                if isinstance(fn.value, ast.Name) and fn.value.id == "subprocess" and fn.attr in _PY_SPAWN_ATTRS:
                    spawn_lines.append(node.lineno)
                    has_flag_kw = any(kw.arg in ("creationflags", None) for kw in node.keywords)
                    if not has_flag_kw:
                        unguarded_spawn_lines.append(node.lineno)
    return has_cnw, calls_window_kwargs, spawn_lines, unguarded_spawn_lines, imported_by_stem, called_names


def verify_windows_windowless_spawns(
    siblings_roots: Sequence[Path],
    *,
    main_repo: Path | None = None,
    require_siblings: bool = False,
    required_repos: Sequence[str] = (),
) -> list[str]:
    """Verify Node.js `windowsHide: true` per-call and Python `CREATE_NO_WINDOW` AST invariants."""
    errors: list[str] = []
    must_exist_repos = set(required_repos)
    extra_repos: dict[str, Path] = {}
    if _resolve_repo("knowledge", siblings_roots) is None:
        try:
            import mindie_knowledge  # type: ignore

            cand_k = Path(mindie_knowledge.__file__).resolve().parents[1]
            if (cand_k / "mindie_knowledge").is_dir():
                extra_repos["knowledge"] = cand_k
        except ImportError:
            pass

    reported_missing_repos: set[str] = set()

    def _need_repo(repo_name: str) -> Path | None:
        r_dir = _resolve_repo(repo_name, siblings_roots, extra_repos)
        if r_dir is None and repo_name not in reported_missing_repos:
            if repo_name in must_exist_repos or (require_siblings and repo_name not in INDEPENDENT_ONLY_GATED_REPOS):
                reported_missing_repos.add(repo_name)
                errors.append(
                    f"{repo_name}: sibling checkout not found in {list(siblings_roots)} for Windows zero-popup verification"
                )
        return r_dir

    if main_repo is not None and (main_repo / ".github/scripts").is_dir():
        for script_py in sorted((main_repo / ".github/scripts").glob("*.py")):
            has_cnw, calls_wk, spawn_lines, unguarded_lines, _, _ = _inspect_python_ast(script_py)
            if spawn_lines and (unguarded_lines or not (has_cnw or calls_wk)):
                rel = script_py.relative_to(main_repo).as_posix()
                errors.append(
                    f"mindie-agent: {rel} spawns subprocesses without CREATE_NO_WINDOW "
                    f"(lines {unguarded_lines or spawn_lines}; Windows console popup risk)"
                )

    required_mjs_by_repo: dict[str, set[str]] = {}
    for node_repo, rel_mjs in WINDOWS_NODE_WINDOWLESS_FILES:
        required_mjs_by_repo.setdefault(node_repo, set()).add(rel_mjs)
        r_dir = _need_repo(node_repo)
        if r_dir is None:
            continue
        host_mjs = r_dir / rel_mjs
        if not host_mjs.is_file():
            errors.append(f"{node_repo}: missing expected Node subprocess host {rel_mjs}")
            continue
        for detail in inspect_node_windowless_file(host_mjs, require_spawns=True):
            errors.append(f"{node_repo}: {rel_mjs} {detail}")

    for node_repo in NODE_SCANNED_REPOS:
        r_dir = _resolve_repo(node_repo, siblings_roots, extra_repos)
        if r_dir is None:
            continue
        already = required_mjs_by_repo.get(node_repo, set())
        for js_path in sorted(r_dir.rglob("*")):
            if not js_path.is_file() or js_path.suffix not in (".mjs", ".cjs", ".js"):
                continue
            rel_parts = js_path.relative_to(r_dir).parts
            if any(part in NODE_SKIP_DIRS for part in rel_parts):
                continue
            rel_posix = js_path.relative_to(r_dir).as_posix()
            if rel_posix in already:
                continue
            for detail in inspect_node_windowless_file(js_path, require_spawns=False):
                errors.append(f"{node_repo}: {rel_posix} {detail}")

    for repo_name, rel_spec in WINDOWS_NO_WINDOW_REQUIRED_FILES:
        repo_dir = _need_repo(repo_name)
        if repo_dir is None:
            continue
        candidates = (rel_spec,) if isinstance(rel_spec, str) else rel_spec
        present = [rel for rel in candidates if (repo_dir / rel).is_file()]
        if not present:
            label = candidates[0] if len(candidates) == 1 else f"one of {', '.join(candidates)}"
            errors.append(f"{repo_name}: missing expected subprocess wrapper {label}")
            continue
        primary_rel = present[0]
        primary_stem = Path(primary_rel).stem
        try:
            p_cnw, _, _, _, _, _ = _inspect_python_ast(repo_dir / primary_rel)
        except SyntaxError as exc:
            errors.append(f"{repo_name}: {primary_rel} syntax error during R4 AST check: {exc}")
            continue
        if not p_cnw:
            errors.append(f"{repo_name}: {primary_rel} missing subprocess.CREATE_NO_WINDOW (Windows console popup risk)")
        for sec_rel in present[1:]:
            try:
                s_cnw, s_wk, s_spawns, s_unguarded, s_imports, s_called = _inspect_python_ast(repo_dir / sec_rel)
            except SyntaxError as exc:
                errors.append(f"{repo_name}: {sec_rel} syntax error during R4 AST check: {exc}")
                continue
            if s_spawns and (s_unguarded or not (s_cnw or s_wk)):
                errors.append(
                    f"{repo_name}: {sec_rel} spawns subprocesses without subprocess.CREATE_NO_WINDOW (Windows console popup risk)"
                )
                continue
            delegated_syms = s_imports.get(primary_stem, set())
            actively_delegates = bool(delegated_syms & s_called)
            if not (s_cnw or s_wk or (not s_spawns and actively_delegates)):
                errors.append(
                    f"{repo_name}: {sec_rel} neither enforces subprocess.CREATE_NO_WINDOW nor delegates to {primary_rel} (Windows console popup risk)"
                )

    for repo_name, rel_path in WINDOWS_NO_WINDOW_COMPANION_FILES:
        repo_dir = _resolve_repo(repo_name, siblings_roots, extra_repos)
        if repo_dir is None or not (repo_dir / rel_path).is_file():
            continue
        try:
            c_cnw, c_wk, _, _, _, _ = _inspect_python_ast(repo_dir / rel_path)
        except SyntaxError as exc:
            errors.append(f"{repo_name}: {rel_path} syntax error during R4 AST check: {exc}")
            continue
        if not (c_cnw or c_wk):
            errors.append(f"{repo_name}: {rel_path} missing subprocess.CREATE_NO_WINDOW (Windows console popup risk)")

    return errors

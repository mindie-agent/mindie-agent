#!/usr/bin/env python3
"""Static AST gate for bounded storage lifecycle, legacy reclamation, and zero temp leak (R4 / Guardrail P8).

[Role]
Verifies that `mindie-agent`, all 7 native harness plugins, and shared/evaluation components
enforce bounded storage lifecycle GC (`storage_lifecycle.py` / `storage_gc.py`), avoid unowned
`tempfile.mkstemp` / `mkdtemp` / `NamedTemporaryFile(delete=False)` leaks in production Python
paths, avoid unguarded Windows `os.kill(pid, 0)` probes in storage lease modules, and isolate
host directories in repository test suites.

[Invariants]
- Runs purely on Python stdlib (`ast`, `json`, `pathlib`, `re`, `tomllib`) with zero imports from
  target repositories and zero subprocesses.
- Enforces `P8` checks whenever a checkout is explicitly targeted via `required_repos` or its
  manifest version meets `STORAGE_LIFECYCLE_FLOOR_VERSIONS`, allowing historical `channels/0.1.json`
  validator checkouts (`< P8 floor`) and unversioned minimal unit-test fixtures to coexist cleanly.
- Every `mkstemp` / `mkdtemp` / `NamedTemporaryFile(delete=False)` call in production modules must
  pair with explicit cleanup (`unlink`/`replace`/`rmtree`/`atexit.register`) in the enclosing
  function or return the allocated handle within a module that owns cleanup.

[Timeouts & Locks]
- Pure synchronous local file parsing (`< 2s` across all 15 repositories); acquires no locks.

[Side-Effect Policy]
- Strictly read-only static inspection of repository checkouts.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import tomllib
from typing import Sequence

STORAGE_LIFECYCLE_FLOOR_VERSIONS: dict[str, tuple[int, int, int]] = {
    "knowledge": (0, 13, 22),
    "diagnostics": (0, 5, 15),
    "remote-dev": (0, 11, 12),
    "coordinator": (0, 7, 11),
    "profiler": (0, 5, 15),
    "sim": (0, 9, 15),
    "mindie-bench": (0, 4, 10),
    "mindie-agent-codex": (0, 1, 34),
    "mindie-agent-cc": (0, 1, 25),
    "mindie-agent-kimi": (0, 1, 26),
    "mindie-agent-dsh": (0, 1, 22),
    "mindie-agent-agy": (0, 1, 16),
    "mindie-agent-wb": (0, 1, 14),
    "mindie-agent-oc": (0, 1, 7),
}

PRODUCTION_PYTHON_SCOPES: dict[str, tuple[str, ...]] = {
    "knowledge": ("mindie_knowledge",),
    "diagnostics": ("mindie_diagnostics",),
    "remote-dev": ("remote_dev",),
    "coordinator": ("mindie_coordinator",),
    "profiler": ("src", "mindie_profiler"),
    "sim": ("src", "mindie_sim"),
    "mindie-bench": ("src/mindie_bench",),
    "mindie-agent-codex": ("plugins/mindie-agent/scripts",),
    "mindie-agent-cc": ("scripts",),
    "mindie-agent-kimi": ("scripts",),
    "mindie-agent-dsh": ("scripts",),
    "mindie-agent-agy": ("plugins/mindie-agent/scripts",),
    "mindie-agent-wb": ("plugins/mindie-agent/scripts",),
    "mindie-agent-oc": ("plugins/mindie-agent/scripts",),
}

# (repo_name, gc_module_rel_path, required_exports, caller_candidates_rel_paths)
REQUIRED_STORAGE_WIRING: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "knowledge",
        "mindie_knowledge/storage/__init__.py",
        (
            "acquire_runtime_lease",
            "retire_directory",
            "prune_component_runtimes",
            "sweep_trash",
            "sweep_legacy_installations",
            "configure_same_volume_uv_cache",
        ),
        ("mindie_knowledge/component_runtime.py",),
    ),
    (
        "mindie-agent-codex",
        "plugins/mindie-agent/scripts/storage_gc.py",
        ("reclaim_storage", "dispatch_cleanup", "serving_runtime_lease"),
        ("plugins/mindie-agent/scripts/harness_update.py", "plugins/mindie-agent/scripts/component_update.py"),
    ),
    (
        "mindie-agent-cc",
        "scripts/storage_lifecycle.py",
        ("runtime_leases", "maintenance_tick", "post_switch", "pre_build_reclaim"),
        ("scripts/release_update.py", "scripts/component_update.py"),
    ),
    (
        "mindie-agent-kimi",
        "scripts/storage_gc.py",
        ("run", "pre_build", "post_switch", "reclaim_remote_state"),
        ("scripts/updater_check.py", "scripts/component_update.py"),
    ),
    (
        "mindie-agent-dsh",
        "scripts/storage_lifecycle.py",
        ("sweep", "safe_sweep", "prune", "configure_prebuild_uv_cache"),
        ("scripts/updater.py", "scripts/setup.py"),
    ),
    (
        "mindie-agent-agy",
        "plugins/mindie-agent/scripts/storage_lifecycle.py",
        ("hold_runtime_lease", "reclaim_after_switch", "configure_uv_cache"),
        ("plugins/mindie-agent/scripts/component_update.py", "plugins/mindie-agent/scripts/mcp_server.py"),
    ),
    (
        "mindie-agent-wb",
        "plugins/mindie-agent/scripts/storage_lifecycle.py",
        ("hold_runtime_lease", "post_update_maintenance", "prune_workbuddy_plugin_caches", "configure_uv_cache"),
        ("plugins/mindie-agent/scripts/component_update.py", "plugins/mindie-agent/scripts/mcp_server.py"),
    ),
    (
        "mindie-agent-oc",
        "plugins/mindie-agent/scripts/storage_gc.py",
        ("prune_component_generations", "sweep_legacy_baggage", "post_switch_reclaim", "acquire_service_lease"),
        ("plugins/mindie-agent/scripts/component_update.py", "plugins/mindie-agent/scripts/mcp_server.py"),
    ),
)

VERSION_MANIFESTS: tuple[str, ...] = (
    "pyproject.toml",
    "plugins/mindie-agent/pyproject.toml",
    "kimi.plugin.json",
    "package.json",
    ".claude-plugin/plugin.json",
    "plugins/mindie-agent/plugin.json",
    "plugins/mindie-agent/.codex-plugin/plugin.json",
)

_SKIP_PARTS: frozenset[str] = frozenset({"tests", "test", "__pycache__", "node_modules", "dist", "build"})
_CLEANUP_CALL_NAMES: frozenset[str] = frozenset(
    {
        "unlink",
        "replace",
        "rmtree",
        "rmtree_force",
        "remove",
        "register",
        "cleanup",
        "_safe_unlink",
        "_remove_path",
        "_rmtree_force",
        "_cleanup_temp",
    }
)
_GC_REFERENCE_TOKENS: frozenset[str] = frozenset(
    {
        "storage",
        "storage_lifecycle",
        "storage_gc",
        "storage_spool",
        "reclaim_storage",
        "prune_component_runtimes",
        "retire_directory",
    }
)
_SANDBOX_ISOLATION_TOKENS: tuple[str, ...] = (
    "MINDIE_CONFIG_HOME",
    "MINDIE_DATA_HOME",
    "MINDIE_DIAGNOSTICS_ROOT",
    "TemporaryDirectory",
    "tmp_path",
)


def _resolve_repo(repo_name: str, siblings_roots: Sequence[Path]) -> Path | None:
    for root in siblings_roots:
        candidate = root / repo_name
        if (candidate / ".git").exists():
            return candidate
    return None


def _parse_repo_semver(repo_dir: Path) -> tuple[int, int, int] | None:
    for rel in VERSION_MANIFESTS:
        manifest = repo_dir / rel
        if not manifest.is_file():
            continue
        try:
            raw = manifest.read_text(encoding="utf-8")
            meta = tomllib.loads(raw).get("project", {}) if manifest.suffix == ".toml" else json.loads(raw)
        except (OSError, ValueError):
            continue
        version = str(meta.get("version") or "").strip()
        match = re.match(r"^(\d+)\.(\d+)\.(\d+)", version)
        if match:
            return int(match.group(1)), int(match.group(2)), int(match.group(3))
    return None


def _call_name(node: ast.Call) -> str:
    fn = node.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        return fn.attr
    return ""


def _is_manual_temp_call(node: ast.Call) -> str | None:
    cname = _call_name(node)
    if cname in {"mkstemp", "mkdtemp"}:
        return cname
    if cname == "NamedTemporaryFile":
        for kw in node.keywords:
            if kw.arg == "delete" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                return "NamedTemporaryFile(delete=False)"
    return None


def _subtree_has_cleanup(root: ast.AST) -> bool:
    for node in ast.walk(root):
        if isinstance(node, ast.Call) and _call_name(node) in _CLEANUP_CALL_NAMES:
            return True
    return False


def inspect_python_temp_hygiene(path: Path) -> list[str]:
    """Verify every manual tempfile allocation in `path` has cleanup ownership."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    errors: list[str] = []
    module_has_cleanup = _subtree_has_cleanup(tree)

    fn_ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end_lineno = getattr(node, "end_lineno", node.lineno)
            fn_ranges.append((node.lineno, end_lineno))
            temp_calls: list[tuple[str, int]] = []
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    kind = _is_manual_temp_call(sub)
                    if kind is not None:
                        temp_calls.append((kind, sub.lineno))
            if not temp_calls:
                continue
            fn_cleans = _subtree_has_cleanup(node)
            returns_value = any(isinstance(sub, ast.Return) and sub.value is not None for sub in ast.walk(node))
            if not (fn_cleans or (returns_value and module_has_cleanup)):
                calls_desc = ", ".join(f"{kind} (line {ln})" for kind, ln in temp_calls)
                errors.append(
                    f"function `{node.name}` allocates {calls_desc} without local cleanup "
                    "(`unlink`/`replace`/`rmtree`/`atexit.register`)"
                )

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                kind = _is_manual_temp_call(sub)
                if kind is not None and not module_has_cleanup:
                    errors.append(
                        f"module top-level allocates {kind} (line {sub.lineno}) without cleanup registration"
                    )
    return errors


def inspect_storage_module_windows_pid_safety(path: Path) -> list[str]:
    """Ban unguarded `os.kill(pid, 0)` in cross-platform storage lease/GC modules."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    errors: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        fn_src = ast.get_source_segment(source, node) or ""
        has_posix_guard = ("os.name" in fn_src and '"nt"' in fn_src) or (
            "os.name" in fn_src and "'nt'" in fn_src
        ) or ("sys.platform" in fn_src and "win32" in fn_src)
        for sub in ast.walk(node):
            if (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and sub.func.attr == "kill"
                and len(sub.args) == 2
                and isinstance(sub.args[1], ast.Constant)
                and sub.args[1].value == 0
                and not has_posix_guard
            ):
                errors.append(
                    f"line {sub.lineno} `{node.name}` calls unguarded `os.kill(pid, 0)` "
                    "(terminates or misprobes processes on Windows; use `is_pid_alive` / Win32 `OpenProcess`)"
                )
    return errors


def _ast_identifiers_and_imports(path: Path) -> tuple[set[str], set[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    defined_fns: set[str] = set()
    referenced: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined_fns.add(node.name)
        elif isinstance(node, ast.Name):
            referenced.add(node.id)
        elif isinstance(node, ast.Attribute):
            referenced.add(node.attr)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                referenced.add(alias.name.rsplit(".", 1)[-1])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                referenced.add(node.module.rsplit(".", 1)[-1])
            for alias in node.names:
                bound = alias.asname or alias.name
                defined_fns.add(bound)
                referenced.add(alias.name)
    return defined_fns, referenced


def _iter_scoped_python_files(repo_dir: Path, scopes: Sequence[str]) -> list[Path]:
    found: list[Path] = []
    for scope in scopes:
        base = repo_dir / scope
        if not base.is_dir():
            continue
        for py_path in sorted(base.rglob("*.py")):
            rel_parts = py_path.relative_to(base).parts
            if any(part in _SKIP_PARTS or part.startswith(".") for part in rel_parts):
                continue
            found.append(py_path)
    return found


def verify_storage_lifecycle_hygiene(
    siblings_roots: Sequence[Path],
    *,
    main_repo: Path | None = None,
    require_siblings: bool = False,
    required_repos: Sequence[str] = (),
    enforce_unversioned: bool = False,
) -> list[str]:
    """Verify P8 storage lifecycle wiring, tempfile ownership, Windows PID safety, and test isolation."""
    errors: list[str] = []
    must_enforce = set(required_repos)

    if main_repo is not None and (main_repo / ".github/scripts").is_dir():
        for script_py in sorted((main_repo / ".github/scripts").glob("*.py")):
            try:
                for detail in inspect_python_temp_hygiene(script_py):
                    rel = script_py.relative_to(main_repo).as_posix()
                    errors.append(f"mindie-agent: {rel} {detail}")
            except SyntaxError as exc:
                rel = script_py.relative_to(main_repo).as_posix()
                errors.append(f"mindie-agent: {rel} syntax error during P8 AST check: {exc}")

    active_repos: dict[str, Path] = {}
    for repo_name, floor in STORAGE_LIFECYCLE_FLOOR_VERSIONS.items():
        repo_dir = _resolve_repo(repo_name, siblings_roots)
        if repo_dir is None:
            if repo_name in must_enforce or (require_siblings and repo_name != "mindie-agent-oc"):
                errors.append(
                    f"{repo_name}: sibling checkout not found in {list(siblings_roots)} for P8 storage lifecycle gate"
                )
            continue
        ver = _parse_repo_semver(repo_dir)
        if ver is None:
            if repo_name in must_enforce or enforce_unversioned:
                active_repos[repo_name] = repo_dir
            continue
        if ver < floor:
            if repo_name in must_enforce:
                errors.append(
                    f"{repo_name}: source version {'.'.join(map(str, ver))} < P8 floor {'.'.join(map(str, floor))}"
                )
            continue
        active_repos[repo_name] = repo_dir

    for repo_name, gc_rel, required_defs, caller_rels in REQUIRED_STORAGE_WIRING:
        repo_dir = active_repos.get(repo_name)
        if repo_dir is None:
            continue
        gc_path = repo_dir / gc_rel
        if not gc_path.is_file():
            errors.append(f"{repo_name}: missing P8 storage lifecycle module {gc_rel}")
            continue
        try:
            defined_fns, _ = _ast_identifiers_and_imports(gc_path)
            for detail in inspect_storage_module_windows_pid_safety(gc_path):
                errors.append(f"{repo_name}: {gc_rel} {detail}")
        except SyntaxError as exc:
            errors.append(f"{repo_name}: {gc_rel} syntax error during P8 AST check: {exc}")
            continue
        missing_defs = [fn for fn in required_defs if fn not in defined_fns]
        if missing_defs:
            errors.append(f"{repo_name}: {gc_rel} missing required function(s) {missing_defs}")
        if repo_name == "mindie-agent-oc":
            spool_rel = "plugins/mindie-agent/scripts/storage_spool.py"
            spool_path = repo_dir / spool_rel
            if not spool_path.is_file():
                errors.append(f"{repo_name}: missing bounded spool module {spool_rel}")
            else:
                for detail in inspect_storage_module_windows_pid_safety(spool_path):
                    errors.append(f"{repo_name}: {spool_rel} {detail}")

        present_callers = [rel for rel in caller_rels if (repo_dir / rel).is_file()]
        if not present_callers:
            errors.append(f"{repo_name}: missing storage GC caller module ({', '.join(caller_rels)})")
        else:
            wired = False
            for rel in present_callers:
                _, refs = _ast_identifiers_and_imports(repo_dir / rel)
                if refs & _GC_REFERENCE_TOKENS:
                    wired = True
                    break
            if not wired:
                errors.append(
                    f"{repo_name}: {', '.join(present_callers)} does not invoke P8 storage lifecycle GC in AST"
                )

    for repo_name, repo_dir in active_repos.items():
        scopes = PRODUCTION_PYTHON_SCOPES.get(repo_name, ())
        for py_path in _iter_scoped_python_files(repo_dir, scopes):
            rel = py_path.relative_to(repo_dir).as_posix()
            try:
                for detail in inspect_python_temp_hygiene(py_path):
                    errors.append(f"{repo_name}: {rel} {detail}")
            except SyntaxError as exc:
                errors.append(f"{repo_name}: {rel} syntax error during P8 AST check: {exc}")

        tests_dir = repo_dir / "tests"
        if tests_dir.is_dir():
            conftest = tests_dir / "conftest.py"
            sample_files = [conftest] if conftest.is_file() else sorted(tests_dir.glob("test_*.py"))[:10]
            isolated = False
            for tf in sample_files:
                try:
                    txt = tf.read_text(encoding="utf-8")
                except OSError:
                    continue
                if any(tok in txt for tok in _SANDBOX_ISOLATION_TOKENS):
                    isolated = True
                    break
            if not isolated:
                errors.append(
                    f"{repo_name}: tests/ missing host sandbox isolation "
                    f"(expected conftest.py or test fixtures isolating {_SANDBOX_ISOLATION_TOKENS[:3]})"
                )

    return errors

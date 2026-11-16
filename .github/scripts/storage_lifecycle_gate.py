#!/usr/bin/env python3
"""Static AST gate for bounded storage lifecycle, legacy reclamation, and zero temp leak (R4 / Guardrail P8).

[Role]
Verifies that `mindie-agent`, all 7 native harness plugins, and shared/evaluation components
enforce bounded storage lifecycle GC (`storage` / `storage_gc` / `storage_lifecycle`), delegates
per-allocation tempfile ownership and scope-aware Windows PID safety checks to `storage_temp_ast.py`,
and verifies host sandbox redirection in repository test suites.

[Invariants]
- Runs purely on Python stdlib (`ast`, `json`, `pathlib`, `re`, `tomllib`) with zero imports from
  target repositories and zero subprocesses.
- Enforces `P8` checks whenever a checkout is explicitly targeted via `required_repos` or its
  manifest version meets `STORAGE_LIFECYCLE_FLOOR_VERSIONS`, allowing historical `channels/0.1.json`
  validator checkouts (`< P8 floor`) and unversioned minimal unit-test fixtures to coexist cleanly.
- Caller wiring requires an unshadowed call to a verified storage GC export (or `importlib.import_module`
  helper defined in the caller module), rejecting unused imports, unbound factories, and shadowed names.

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

from storage_temp_ast import (
    inspect_python_temp_hygiene,
    inspect_storage_module_windows_pid_safety,
    iter_direct_nodes,
    local_bound_names,
)

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

REQUIRED_STORAGE_WIRING: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...], frozenset[str]], ...] = (
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
        frozenset({"storage", "lifecycle", "leases", "legacy"}),
    ),
    (
        "mindie-agent-codex",
        "plugins/mindie-agent/scripts/storage_gc.py",
        ("reclaim_storage", "dispatch_cleanup", "serving_runtime_lease"),
        ("plugins/mindie-agent/scripts/harness_update.py", "plugins/mindie-agent/scripts/component_update.py"),
        frozenset({"storage_gc", "storage"}),
    ),
    (
        "mindie-agent-cc",
        "scripts/storage_lifecycle.py",
        ("runtime_leases", "maintenance_tick", "post_switch", "pre_build_reclaim"),
        ("scripts/release_update.py", "scripts/component_update.py"),
        frozenset({"storage_lifecycle", "storage_reclaim", "storage_releases", "storage"}),
    ),
    (
        "mindie-agent-kimi",
        "scripts/storage_gc.py",
        ("run", "pre_build", "post_switch", "reclaim_remote_state"),
        ("scripts/updater_check.py", "scripts/component_update.py"),
        frozenset({"storage_gc", "storage"}),
    ),
    (
        "mindie-agent-dsh",
        "scripts/storage_lifecycle.py",
        ("sweep", "safe_sweep", "configure_prebuild_uv_cache", "discard_archives"),
        ("scripts/updater.py", "scripts/setup.py"),
        frozenset({"storage_lifecycle", "storage"}),
    ),
    (
        "mindie-agent-agy",
        "plugins/mindie-agent/scripts/storage_lifecycle.py",
        ("hold_runtime_lease", "reclaim_after_switch", "configure_uv_cache"),
        ("plugins/mindie-agent/scripts/component_update.py", "plugins/mindie-agent/scripts/mcp_server.py"),
        frozenset({"storage_lifecycle", "storage"}),
    ),
    (
        "mindie-agent-wb",
        "plugins/mindie-agent/scripts/storage_lifecycle.py",
        ("hold_runtime_lease", "post_update_maintenance", "prune_workbuddy_plugin_caches", "configure_uv_cache"),
        ("plugins/mindie-agent/scripts/component_update.py", "plugins/mindie-agent/scripts/mcp_server.py"),
        frozenset({"storage_lifecycle", "storage"}),
    ),
    (
        "mindie-agent-oc",
        "plugins/mindie-agent/scripts/storage_gc.py",
        ("prune_component_generations", "sweep_legacy_baggage", "post_switch_reclaim", "acquire_service_lease"),
        ("plugins/mindie-agent/scripts/component_update.py", "plugins/mindie-agent/scripts/mcp_server.py"),
        frozenset({"storage_gc", "storage_spool", "storage"}),
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
_HOME_ENV_KEYS: frozenset[str] = frozenset({"HOME", "USERPROFILE"})
_MINDIE_ENV_KEYS: frozenset[str] = frozenset(
    {"MINDIE_CONFIG_HOME", "MINDIE_DATA_HOME", "MINDIE_DIAGNOSTICS_ROOT", "XDG_CONFIG_HOME", "XDG_DATA_HOME"}
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


def _module_top_level_exports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    exports: set[str] = set()
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            exports.add(stmt.name)
        elif isinstance(stmt, ast.Assign):
            for tgt in stmt.targets:
                if isinstance(tgt, ast.Name):
                    exports.add(tgt.id)
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            exports.add(stmt.target.id)
        elif isinstance(stmt, ast.ImportFrom):
            for alias in stmt.names:
                exports.add(alias.asname or alias.name)
        elif isinstance(stmt, ast.Import):
            for alias in stmt.names:
                exports.add(alias.asname or alias.name.split(".", 1)[0])
    return exports


def _caller_invokes_storage_gc(
    caller_path: Path,
    storage_stems: frozenset[str],
    valid_gc_attrs: frozenset[str],
) -> bool:
    tree = ast.parse(caller_path.read_text(encoding="utf-8"), filename=str(caller_path))
    top_mods: set[str] = set()
    top_fns: set[str] = set()
    dynamic_loaders: set[str] = set()

    for stmt in tree.body:
        if isinstance(stmt, ast.Import):
            for alias in stmt.names:
                stem = alias.name.rsplit(".", 1)[-1]
                if stem in storage_stems:
                    top_mods.add(alias.asname or stem)
        elif isinstance(stmt, ast.ImportFrom) and stmt.module:
            if set(stmt.module.split(".")) & storage_stems:
                for alias in stmt.names:
                    bound = alias.asname or alias.name
                    if alias.name in storage_stems:
                        top_mods.add(bound)
                    else:
                        top_fns.add(bound)
        elif isinstance(stmt, ast.FunctionDef):
            for sub in ast.walk(stmt):
                if (
                    isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr == "import_module"
                ):
                    dynamic_loaders.add(stmt.name)

    def _scope_calls_gc(scope: ast.AST, mods: set[str], fns: set[str], loaders: set[str]) -> bool:
        local_mods = set(mods)
        local_fns = set(fns)
        for sub in iter_direct_nodes(scope):
            if isinstance(sub, ast.Import):
                for alias in sub.names:
                    stem = alias.name.rsplit(".", 1)[-1]
                    if stem in storage_stems:
                        local_mods.add(alias.asname or stem)
            elif isinstance(sub, ast.ImportFrom) and sub.module:
                if set(sub.module.split(".")) & storage_stems:
                    for alias in sub.names:
                        bound = alias.asname or alias.name
                        if alias.name in storage_stems:
                            local_mods.add(bound)
                        else:
                            local_fns.add(bound)

        for sub in iter_direct_nodes(scope):
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                shadowed = local_bound_names(sub)
                if _scope_calls_gc(sub, local_mods - shadowed, local_fns - shadowed, loaders - shadowed):
                    return True
            elif isinstance(sub, ast.Call):
                fn = sub.func
                if isinstance(fn, ast.Name) and fn.id in local_fns:
                    return True
                if isinstance(fn, ast.Attribute) and fn.attr in valid_gc_attrs:
                    if isinstance(fn.value, ast.Name) and fn.value.id in local_mods:
                        return True
                    if (
                        isinstance(fn.value, ast.Call)
                        and isinstance(fn.value.func, ast.Name)
                        and fn.value.func.id in loaders
                        and fn.value.args
                        and isinstance(fn.value.args[0], ast.Constant)
                        and str(fn.value.args[0].value) in storage_stems
                    ):
                        return True
        return False

    return _scope_calls_gc(tree, top_mods, top_fns, dynamic_loaders)


def _test_dir_isolates_sandbox_ast(tests_dir: Path) -> bool:
    """Verify tests redirect HOME/USERPROFILE and MindIE/XDG roots via actual env mutation calls."""
    candidates: list[Path] = []
    for special in ("conftest.py", "support.py"):
        if (tests_dir / special).is_file():
            candidates.append(tests_dir / special)
    candidates.extend(sorted(tests_dir.glob("test_*.py"))[:10])

    all_keys = _HOME_ENV_KEYS | _MINDIE_ENV_KEYS
    redirected_keys: set[str] = set()
    has_env_write = False

    for path in candidates:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):
            continue
        # Collect module-level dicts/tuples holding sandbox env key names (e.g. `_ISOLATED_PATHS = {"HOME": ...}`).
        key_tables: dict[str, set[str]] = {}
        for stmt in tree.body:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                found = {
                    sub.value
                    for sub in ast.walk(stmt.value)
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and sub.value in all_keys
                }
                if found:
                    key_tables[stmt.targets[0].id] = found

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                cname = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "")
                is_env_mutation = cname in {"setenv", "setdefault", "update"} or (
                    cname == "dict"
                    and isinstance(fn, ast.Attribute)
                    and isinstance(fn.value, ast.Name)
                    and fn.value.id == "patch"
                )
                if is_env_mutation:
                    has_env_write = True
                    for sub in ast.walk(node):
                        if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and sub.value in all_keys:
                            redirected_keys.add(sub.value)
                        elif isinstance(sub, ast.Name) and sub.id in key_tables:
                            redirected_keys |= key_tables[sub.id]
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                iter_keys: set[str] = set()
                for sub in ast.walk(node.iter):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and sub.value in all_keys:
                        iter_keys.add(sub.value)
                    elif isinstance(sub, ast.Name) and sub.id in key_tables:
                        iter_keys |= key_tables[sub.id]
                if iter_keys:
                    body_mutates = any(
                        (isinstance(b, ast.Call) and isinstance(b.func, ast.Attribute) and b.func.attr in {"setenv", "setdefault"})
                        or isinstance(b, ast.Subscript)
                        for b in ast.walk(node)
                    )
                    if body_mutates:
                        has_env_write = True
                        redirected_keys |= iter_keys
            elif isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Subscript):
                        has_env_write = True
                        for sub in ast.walk(tgt.slice):
                            if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and sub.value in all_keys:
                                redirected_keys.add(sub.value)

    return has_env_write and bool(redirected_keys & _HOME_ENV_KEYS) and len(redirected_keys & _MINDIE_ENV_KEYS) >= 2


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

    for repo_name, gc_rel, required_exports, caller_rels, storage_stems in REQUIRED_STORAGE_WIRING:
        repo_dir = active_repos.get(repo_name)
        if repo_dir is None:
            continue
        gc_path = repo_dir / gc_rel
        if not gc_path.is_file():
            errors.append(f"{repo_name}: missing P8 storage lifecycle module {gc_rel}")
            continue
        try:
            top_exports = _module_top_level_exports(gc_path)
        except SyntaxError as exc:
            errors.append(f"{repo_name}: {gc_rel} syntax error during P8 AST check: {exc}")
            continue
        missing_defs = [fn for fn in required_exports if fn not in top_exports]
        if missing_defs:
            errors.append(f"{repo_name}: {gc_rel} missing top-level export(s) {missing_defs}")
        if repo_name == "mindie-agent-oc":
            spool_rel = "plugins/mindie-agent/scripts/storage_spool.py"
            if not (repo_dir / spool_rel).is_file():
                errors.append(f"{repo_name}: missing bounded spool module {spool_rel}")

        present_callers = [rel for rel in caller_rels if (repo_dir / rel).is_file()]
        if not present_callers:
            errors.append(f"{repo_name}: missing storage GC caller module ({', '.join(caller_rels)})")
        else:
            valid_gc_attrs = frozenset(top_exports) | frozenset(required_exports)
            wired = False
            for rel in present_callers:
                try:
                    if _caller_invokes_storage_gc(repo_dir / rel, storage_stems, valid_gc_attrs):
                        wired = True
                        break
                except SyntaxError as exc:
                    errors.append(f"{repo_name}: {rel} syntax error during P8 AST check: {exc}")
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
                if "storage" in py_path.parts or py_path.stem.startswith("storage"):
                    for detail in inspect_storage_module_windows_pid_safety(py_path):
                        errors.append(f"{repo_name}: {rel} {detail}")
            except SyntaxError as exc:
                errors.append(f"{repo_name}: {rel} syntax error during P8 AST check: {exc}")

        tests_dir = repo_dir / "tests"
        if tests_dir.is_dir() and not _test_dir_isolates_sandbox_ast(tests_dir):
            errors.append(
                f"{repo_name}: tests/ missing AST-verified host sandbox isolation "
                "(expected conftest.py or test fixtures redirecting HOME and MindIE roots)"
            )

    return errors

#!/usr/bin/env python3
"""Static AST gate for bounded storage lifecycle, legacy reclamation, and zero temp leak (R4 / Guardrail P8).

[Role]
Verifies that `mindie-agent`, all 7 native harness plugins, and shared/evaluation components
enforce bounded storage lifecycle GC (`storage` / `storage_gc` / `storage_lifecycle`), delegates
per-allocation tempfile ownership to `storage_temp_ast.py` and scope-aware Windows PID safety
checks to `storage_pid_ast.py`, and verifies host sandbox redirection in repository test suites.

[Invariants]
- Runs purely on Python stdlib (`ast`, `json`, `pathlib`, `re`, `tomllib`) with zero imports from
  target repositories and zero subprocesses.
- Enforces `P8` checks whenever a checkout is explicitly targeted via `required_repos` or its
  manifest version meets `STORAGE_LIFECYCLE_FLOOR_VERSIONS`, allowing historical `channels/0.1.json`
  validator checkouts (`< P8 floor`) and unversioned minimal unit-test fixtures to coexist cleanly.
- Caller wiring requires an unshadowed, unreassigned static import and call to a verified storage
  GC export, rejecting unused imports, reassigned bindings, and arbitrary factory calls.

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

from storage_pid_ast import (
    inspect_helper_windows_pid_safety,
    inspect_storage_module_windows_pid_safety,
)
from storage_temp_ast import (
    inspect_python_temp_hygiene,
    iter_direct_nodes,
    non_import_bound_names,
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
    """Require an unshadowed, unreassigned static import and call to a verified GC export."""
    tree = ast.parse(caller_path.read_text(encoding="utf-8"), filename=str(caller_path))

    def _scope_calls_gc(scope: ast.AST, inherited_mods: set[str], inherited_fns: set[str]) -> bool:
        rebound = non_import_bound_names(scope)
        # Also invalidate names overwritten by imports from non-storage modules in this scope.
        non_storage_imports: set[str] = set()
        local_mods = set(inherited_mods) - rebound
        local_fns = set(inherited_fns) - rebound
        for sub in iter_direct_nodes(scope):
            if isinstance(sub, ast.Import):
                for alias in sub.names:
                    bound = alias.asname or alias.name.split(".", 1)[0]
                    stem = alias.name.rsplit(".", 1)[-1]
                    if stem in storage_stems and bound not in rebound:
                        local_mods.add(bound)
                    else:
                        non_storage_imports.add(bound)
            elif isinstance(sub, ast.ImportFrom):
                mod_parts = set((sub.module or "").split("."))
                is_storage = bool(mod_parts & storage_stems)
                for alias in sub.names:
                    bound = alias.asname or alias.name
                    if is_storage and bound not in rebound:
                        if alias.name in storage_stems:
                            local_mods.add(bound)
                        elif alias.name in valid_gc_attrs:
                            local_fns.add(bound)
                    else:
                        non_storage_imports.add(bound)
        local_mods -= non_storage_imports
        local_fns -= non_storage_imports

        child_mods = inherited_mods if isinstance(scope, ast.ClassDef) else local_mods
        child_fns = inherited_fns if isinstance(scope, ast.ClassDef) else local_fns
        for sub in iter_direct_nodes(scope):
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                if _scope_calls_gc(sub, child_mods, child_fns):
                    return True
            elif isinstance(sub, ast.Call):
                fn = sub.func
                if isinstance(fn, ast.Name) and fn.id in local_fns:
                    return True
                if (
                    isinstance(fn, ast.Attribute)
                    and fn.attr in valid_gc_attrs
                    and isinstance(fn.value, ast.Name)
                    and fn.value.id in local_mods
                ):
                    return True
        return False

    return _scope_calls_gc(tree, set(), set())


def _is_os_environ_expr(expr: ast.AST, os_aliases: set[str]) -> bool:
    return (
        isinstance(expr, ast.Attribute)
        and isinstance(expr.value, ast.Name)
        and expr.value.id in os_aliases
        and expr.attr == "environ"
    )


def _extract_key_constants(expr: ast.AST, all_keys: frozenset[str], key_tables: dict[str, set[str]]) -> set[str]:
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str) and expr.value in all_keys:
        return {expr.value}
    if isinstance(expr, ast.Name) and expr.id in key_tables:
        return set(key_tables[expr.id])
    if isinstance(expr, ast.Dict):
        return {
            k.value
            for k in expr.keys
            if isinstance(k, ast.Constant) and isinstance(k.value, str) and k.value in all_keys
        }
    if isinstance(expr, (ast.Tuple, ast.List, ast.Set)):
        keys: set[str] = set()
        for elt in expr.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str) and elt.value in all_keys:
                keys.add(elt.value)
            elif (
                isinstance(elt, (ast.Tuple, ast.List))
                and elt.elts
                and isinstance(elt.elts[0], ast.Constant)
                and isinstance(elt.elts[0].value, str)
                and elt.elts[0].value in all_keys
            ):
                keys.add(elt.elts[0].value)
        return keys
    if isinstance(expr, ast.DictComp) and len(expr.generators) == 1:
        gen = expr.generators[0]
        if isinstance(expr.key, ast.Constant) and isinstance(expr.key.value, str) and expr.key.value in all_keys:
            return {expr.key.value}
        if isinstance(expr.key, ast.Name):
            key_var = expr.key.id
            binds_key = (isinstance(gen.target, ast.Name) and gen.target.id == key_var) or (
                isinstance(gen.target, (ast.Tuple, ast.List))
                and gen.target.elts
                and isinstance(gen.target.elts[0], ast.Name)
                and gen.target.elts[0].id == key_var
            )
            if binds_key:
                return _extract_key_constants(gen.iter, all_keys, key_tables)
        return set()
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr in {"items", "keys"}:
        return _extract_key_constants(expr.func.value, all_keys, key_tables)
    return set()


def _test_dir_isolates_sandbox_ast(tests_dir: Path) -> bool:
    """Verify tests redirect HOME/USERPROFILE and MindIE/XDG roots via real env mutations."""
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
        top_rebound = non_import_bound_names(tree)
        top_os_aliases: set[str] = set()
        top_patch_aliases: set[str] = set()
        for stmt in tree.body:
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    bound = alias.asname or alias.name.split(".", 1)[0]
                    if (alias.name == "os" or (alias.asname is None and alias.name.startswith("os."))) and bound not in top_rebound:
                        top_os_aliases.add(bound)
            elif isinstance(stmt, ast.ImportFrom) and stmt.module == "unittest.mock":
                for alias in stmt.names:
                    bound = alias.asname or alias.name
                    if alias.name == "patch" and bound not in top_rebound:
                        top_patch_aliases.add(bound)

        scopes: list[tuple[ast.AST, dict[str, set[str]], set[str], set[str], set[str]]] = []
        top_tables: dict[str, set[str]] = {}
        top_counts: dict[str, int] = {}
        for sub in iter_direct_nodes(tree):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                top_counts[sub.id] = top_counts.get(sub.id, 0) + 1
        for stmt in tree.body:
            if (
                isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
                and top_counts.get(stmt.targets[0].id, 0) == 1
            ):
                ks = _extract_key_constants(stmt.value, all_keys, {})
                if ks:
                    top_tables[stmt.targets[0].id] = ks
        scopes.append((tree, top_tables, set(), top_os_aliases, top_patch_aliases))

        for fn_node in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            fn_rebound = non_import_bound_names(fn_node)
            fn_os = set(top_os_aliases) - fn_rebound
            fn_patch = set(top_patch_aliases) - fn_rebound
            for sub in iter_direct_nodes(fn_node):
                if isinstance(sub, ast.Import):
                    for alias in sub.names:
                        bound = alias.asname or alias.name.split(".", 1)[0]
                        if (alias.name == "os" or (alias.asname is None and alias.name.startswith("os."))) and bound not in fn_rebound:
                            fn_os.add(bound)
                elif isinstance(sub, ast.ImportFrom) and sub.module == "unittest.mock":
                    for alias in sub.names:
                        bound = alias.asname or alias.name
                        if alias.name == "patch" and bound not in fn_rebound:
                            fn_patch.add(bound)
            fn_tables = dict(top_tables)
            fn_counts: dict[str, int] = {}
            for sub in iter_direct_nodes(fn_node):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                    fn_counts[sub.id] = fn_counts.get(sub.id, 0) + 1
            for name in fn_counts:
                fn_tables.pop(name, None)
            for sub in iter_direct_nodes(fn_node):
                if (
                    isinstance(sub, ast.Assign)
                    and len(sub.targets) == 1
                    and isinstance(sub.targets[0], ast.Name)
                    and fn_counts.get(sub.targets[0].id, 0) == 1
                ):
                    ks = _extract_key_constants(sub.value, all_keys, top_tables)
                    if ks:
                        fn_tables[sub.targets[0].id] = ks
            mp_params = {
                a.arg
                for a in (*fn_node.args.posonlyargs, *fn_node.args.args, *fn_node.args.kwonlyargs)
                if a.arg == "monkeypatch" and fn_counts.get(a.arg, 0) == 0
            }
            scopes.append((fn_node, fn_tables, mp_params, fn_os, fn_patch))

        for scope_node, tables, mp_names, os_aliases, patch_aliases in scopes:
            loop_var_keys: dict[str, set[str]] = {}
            for sub in iter_direct_nodes(scope_node):
                if isinstance(sub, (ast.For, ast.AsyncFor)):
                    ks = _extract_key_constants(sub.iter, all_keys, tables)
                    if ks:
                        if isinstance(sub.target, ast.Name):
                            loop_var_keys[sub.target.id] = ks
                        elif isinstance(sub.target, (ast.Tuple, ast.List)) and sub.target.elts and isinstance(sub.target.elts[0], ast.Name):
                            loop_var_keys[sub.target.elts[0].id] = ks

            effective_tables = {**tables, **loop_var_keys}
            for sub in iter_direct_nodes(scope_node):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                    recv, attr = sub.func.value, sub.func.attr
                    # 1. `monkeypatch.setenv(key, val)`
                    if isinstance(recv, ast.Name) and recv.id in mp_names and attr == "setenv" and len(sub.args) >= 2:
                        ks = _extract_key_constants(sub.args[0], all_keys, effective_tables)
                        if ks:
                            has_env_write = True
                            redirected_keys |= ks
                    # 2. `os.environ.setdefault(key, val)` or `os.environ.update(mapping)`
                    elif _is_os_environ_expr(recv, os_aliases):
                        if attr == "setdefault" and len(sub.args) >= 2:
                            ks = _extract_key_constants(sub.args[0], all_keys, effective_tables)
                            if ks:
                                has_env_write = True
                                redirected_keys |= ks
                        elif attr == "update" and sub.args:
                            ks = _extract_key_constants(sub.args[0], all_keys, effective_tables)
                            if ks:
                                has_env_write = True
                                redirected_keys |= ks
                    # 3. `patch.dict(os.environ, mapping)`
                    elif (
                        isinstance(recv, ast.Name)
                        and recv.id in patch_aliases
                        and attr == "dict"
                        and len(sub.args) >= 2
                        and _is_os_environ_expr(sub.args[0], os_aliases)
                    ):
                        ks = _extract_key_constants(sub.args[1], all_keys, effective_tables)
                        if ks:
                            has_env_write = True
                            redirected_keys |= ks
                # 4. `os.environ[key] = val` (strictly `ast.Store`, never read `ast.Load`)
                elif isinstance(sub, ast.Assign):
                    for tgt in sub.targets:
                        if (
                            isinstance(tgt, ast.Subscript)
                            and isinstance(tgt.ctx, ast.Store)
                            and _is_os_environ_expr(tgt.value, os_aliases)
                        ):
                            ks = _extract_key_constants(tgt.slice, all_keys, effective_tables)
                            if ks:
                                has_env_write = True
                                redirected_keys |= ks

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


_STORAGE_HELPER_STEMS: frozenset[str] = frozenset({
    "_host_exec", "bounded_process", "filesystem", "genstate", "host_pin_refresh",
    "locks", "mindie_paths", "paths", "product_contract", "remote_state_guard", "state_layout",
})


def _storage_reachable_helpers(repo_dir: Path, scopes: Sequence[str], scoped_files: Sequence[Path]) -> set[Path]:
    file_set = set(scoped_files)
    search_roots = [repo_dir, *(repo_dir / s for s in scopes if (repo_dir / s).is_dir())]
    queue = [p for p in scoped_files if "storage" in p.parts or p.stem.startswith("storage") or p.stem in _STORAGE_HELPER_STEMS]
    visited = set(queue)
    while queue:
        cur = queue.pop()
        try:
            tree = ast.parse(cur.read_text(encoding="utf-8"), filename=str(cur))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            specs: list[tuple[int, str, str | None]] = []
            if isinstance(node, ast.Import):
                specs.extend((0, al.name, None) for al in node.names)
            elif isinstance(node, ast.ImportFrom):
                specs.extend((node.level or 0, node.module or "", al.name) for al in node.names)
            for lvl, mod, name in specs:
                anchors: list[Path] = []
                if lvl > 0:
                    anc = cur.parent
                    for _ in range(lvl - 1):
                        anc = anc.parent
                    anchors.append(anc)
                else:
                    anchors.extend(search_roots)
                mp = mod.replace(".", "/")
                rels = [mp] if mp else []
                if name and name != "*":
                    rels.append(f"{mp}/{name}" if mp else name)
                for anc in anchors:
                    for rel in rels:
                        for cand in (anc / f"{rel}.py", anc / rel / "__init__.py"):
                            if cand in file_set and cand not in visited:
                                visited.add(cand)
                                queue.append(cand)
    return visited


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
        scoped_files = _iter_scoped_python_files(repo_dir, scopes)
        helper_files = _storage_reachable_helpers(repo_dir, scopes, scoped_files)
        for py_path in scoped_files:
            rel = py_path.relative_to(repo_dir).as_posix()
            try:
                for detail in inspect_python_temp_hygiene(py_path):
                    errors.append(f"{repo_name}: {rel} {detail}")
                if "storage" in py_path.parts or py_path.stem.startswith("storage"):
                    for detail in inspect_storage_module_windows_pid_safety(py_path):
                        errors.append(f"{repo_name}: {rel} {detail}")
                elif py_path in helper_files:
                    for detail in inspect_helper_windows_pid_safety(py_path):
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

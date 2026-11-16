#!/usr/bin/env python3
"""Static AST gate for bounded storage lifecycle, legacy reclamation, and zero temp leak (R4 / Guardrail P8).

[Role]
Verifies that `mindie-agent`, all 7 native harness plugins, and shared/evaluation components
enforce bounded storage lifecycle GC (`storage` / `storage_gc` / `storage_lifecycle`), track
per-allocation cleanup or ownership transfer for `mkstemp` / `mkdtemp` / `NamedTemporaryFile(delete=False)`,
forbid unguarded Windows `os.kill(pid, 0)` probes across all storage modules, and isolate host
directories in repository test suites.

[Invariants]
- Runs purely on Python stdlib (`ast`, `json`, `pathlib`, `re`, `tomllib`) with zero imports from
  target repositories and zero subprocesses.
- Enforces `P8` checks whenever a checkout is explicitly targeted via `required_repos` or its
  manifest version meets `STORAGE_LIFECYCLE_FLOOR_VERSIONS`, allowing historical `channels/0.1.json`
  validator checkouts (`< P8 floor`) and unversioned minimal unit-test fixtures to coexist cleanly.
- Every manual tempfile allocation is tracked individually to a real filesystem cleanup call
  (`os.unlink`/`os.replace`/`shutil.rmtree`/`Path.unlink`/1-arg `Path.replace`, never `str.replace`)
  or an explicit `return`/`yield` of that allocated binding in a module owning cleanup.

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

# (repo_name, gc_module_rel_path, required_top_exports, caller_candidates, storage_mod_stems)
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
_DIRECT_FS_CLEANUP_FNS: frozenset[str] = frozenset(
    {
        "unlink",
        "remove",
        "rmdir",
        "rmtree",
        "rmtree_force",
        "_rmtree_force",
        "_safe_unlink",
        "_remove_path",
        "_cleanup_temp",
        "retire_directory",
    }
)
_SANDBOX_ENV_KEYS: frozenset[str] = frozenset(
    {
        "HOME",
        "USERPROFILE",
        "MINDIE_CONFIG_HOME",
        "MINDIE_DATA_HOME",
        "MINDIE_DIAGNOSTICS_ROOT",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
    }
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


def _iter_direct_nodes(root: ast.AST) -> list[ast.AST]:
    """Walk AST nodes inside `root` without crossing into nested function or class scopes."""
    out: list[ast.AST] = []
    stack: list[ast.AST] = list(ast.iter_child_nodes(root))
    while stack:
        cur = stack.pop()
        out.append(cur)
        if not isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            stack.extend(ast.iter_child_nodes(cur))
    return out


def _names_in_expr(node: ast.AST | None) -> set[str]:
    if node is None:
        return set()
    names: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            names.add(sub.id)
        elif (
            isinstance(sub, ast.Attribute)
            and isinstance(sub.value, ast.Name)
            and sub.value.id == "self"
        ):
            names.add(f"self.{sub.attr}")
    return names


def _transferred_vars_in_expr(node: ast.AST | None) -> set[str]:
    """Extract bindings genuinely transferred out via `return`/`yield` (excluding `.replace()`/`.read_text()` etc.)."""
    if node is None:
        return set()
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        out: set[str] = set()
        for elt in node.elts:
            out |= _transferred_vars_in_expr(elt)
        return out
    if isinstance(node, ast.Dict):
        out = set()
        for val in node.values:
            out |= _transferred_vars_in_expr(val)
        return out
    if isinstance(node, ast.Call):
        # Allow `Path(d)` or dataclass/class/namedtuple wrappers `Profile(root=d)`,
        # but never method calls on the path string like `d.replace('a', 'b')`.
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            if node.func.attr in {"replace", "split", "strip", "encode", "startswith", "endswith", "read_text", "read_bytes"}:
                return set()
        out = set()
        for arg in node.args:
            out |= _transferred_vars_in_expr(arg)
        for kw in node.keywords:
            out |= _transferred_vars_in_expr(kw.value)
        return out
    return set()


def _collect_temp_aliases(tree: ast.Module) -> tuple[set[str], set[str], set[str], set[str], set[str], set[str]]:
    mkstemp_names = {"mkstemp"}
    mkdtemp_names = {"mkdtemp"}
    ntf_names = {"NamedTemporaryFile"}
    os_aliases = {"os"}
    shutil_aliases = {"shutil"}
    atexit_aliases = {"atexit"}
    os_replace_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name
                if alias.name == "os":
                    os_aliases.add(bound)
                elif alias.name == "shutil":
                    shutil_aliases.add(bound)
                elif alias.name == "atexit":
                    atexit_aliases.add(bound)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                bound = alias.asname or alias.name
                if mod == "tempfile":
                    if alias.name == "mkstemp":
                        mkstemp_names.add(bound)
                    elif alias.name == "mkdtemp":
                        mkdtemp_names.add(bound)
                    elif alias.name == "NamedTemporaryFile":
                        ntf_names.add(bound)
                elif mod == "os" and alias.name == "replace":
                    os_replace_names.add(bound)
    return mkstemp_names, mkdtemp_names, ntf_names, os_aliases | os_replace_names, shutil_aliases, atexit_aliases


def _manual_temp_kind(
    node: ast.Call,
    mkstemp_names: set[str],
    mkdtemp_names: set[str],
    ntf_names: set[str],
) -> str | None:
    fn = node.func
    cname = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "")
    if cname in mkstemp_names:
        return "mkstemp"
    if cname in mkdtemp_names:
        return "mkdtemp"
    if cname in ntf_names:
        for kw in node.keywords:
            if kw.arg == "delete" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                return "NamedTemporaryFile(delete=False)"
    return None


def _is_fs_cleanup_call(
    call: ast.Call,
    os_or_replace: set[str],
    shutil_aliases: set[str],
    atexit_aliases: set[str],
    helper_cleaners: set[str],
) -> set[str]:
    """Return variable/self.attr names cleaned by `call` (strictly excluding `str.replace`)."""
    fn = call.func
    arg_names: set[str] = set()
    for arg in call.args:
        arg_names |= _names_in_expr(arg)
    for kw in call.keywords:
        arg_names |= _names_in_expr(kw.value)

    if isinstance(fn, ast.Name):
        if fn.id in _DIRECT_FS_CLEANUP_FNS or fn.id in helper_cleaners:
            return arg_names
        if fn.id in os_or_replace and call.args:
            return _names_in_expr(call.args[0])
        return set()

    if isinstance(fn, ast.Attribute):
        recv = fn.value
        if isinstance(recv, ast.Name):
            if recv.id in os_or_replace:
                if fn.attr in {"unlink", "remove", "rmdir"} and call.args:
                    return _names_in_expr(call.args[0])
                if fn.attr in {"replace", "rename"} and len(call.args) >= 2:
                    return _names_in_expr(call.args[0])
                return set()
            if recv.id in shutil_aliases and fn.attr in {"rmtree", "move"} and call.args:
                return _names_in_expr(call.args[0])
            if recv.id in atexit_aliases and fn.attr == "register":
                return arg_names
        if fn.attr in {"unlink", "cleanup"} and not isinstance(recv, ast.Constant):
            return _names_in_expr(recv) | arg_names
        # `Path.replace(target)` / `Path.rename(target)` takes 1 positional arg; `str.replace(old, new)` takes >= 2.
        if fn.attr in {"replace", "rename"} and len(call.args) == 1 and not call.keywords and not isinstance(recv, ast.Constant):
            return _names_in_expr(recv)
    return set()


def _extract_binding_vars(target: ast.AST, kind: str) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id} if target.id != "_" else set()
    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
        return {f"self.{target.attr}"}
    if isinstance(target, (ast.Tuple, ast.List)):
        if kind == "mkstemp" and len(target.elts) >= 2:
            return _extract_binding_vars(target.elts[1], kind)
        out: set[str] = set()
        for elt in target.elts:
            out |= _extract_binding_vars(elt, kind)
        return out
    return set()


def inspect_python_temp_hygiene(path: Path) -> list[str]:
    """Verify every manual tempfile allocation in `path` is individually cleaned up or transferred."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    errors: list[str] = []
    mkstemp_n, mkdtemp_n, ntf_n, os_rep, shutil_a, atexit_a = _collect_temp_aliases(tree)

    all_fns = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    helper_cleaners: set[str] = set()
    for _ in range(2):
        for fn_node in all_fns:
            param_names = {a.arg for a in fn_node.args.args + fn_node.args.kwonlyargs}
            for sub in _iter_direct_nodes(fn_node):
                if isinstance(sub, ast.Call):
                    cleaned = _is_fs_cleanup_call(sub, os_rep, shutil_a, atexit_a, helper_cleaners)
                    if cleaned & param_names or (cleaned and not param_names):
                        helper_cleaners.add(fn_node.name)

    module_has_fs_cleanup = bool(helper_cleaners)
    if not module_has_fs_cleanup:
        for sub in ast.walk(tree):
            if isinstance(sub, ast.Call) and _is_fs_cleanup_call(sub, os_rep, shutil_a, atexit_a, helper_cleaners):
                module_has_fs_cleanup = True
                break

    class_cleaned_attrs: dict[int, set[str]] = {}
    for cls_node in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        attrs: set[str] = set()
        for sub in ast.walk(cls_node):
            if isinstance(sub, ast.Call):
                attrs |= {v for v in _is_fs_cleanup_call(sub, os_rep, shutil_a, atexit_a, helper_cleaners) if v.startswith("self.")}
        class_cleaned_attrs[id(cls_node)] = attrs

    parent_map: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_map[id(child)] = parent

    def _enclosing_class_attrs(scope_node: ast.AST) -> set[str]:
        cur = parent_map.get(id(scope_node))
        while cur is not None:
            if isinstance(cur, ast.ClassDef):
                return class_cleaned_attrs.get(id(cur), set())
            cur = parent_map.get(id(cur))
        return set()

    scopes: list[tuple[str, ast.AST]] = [("module top-level", tree)]
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            scopes.append((f"class `{node.name}` body", node))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scopes.append((f"function `{node.name}`", node))

    for scope_label, scope_node in scopes:
        direct = _iter_direct_nodes(scope_node)
        allocs: list[tuple[str, int, set[str], int]] = []
        for sub in direct:
            if isinstance(sub, ast.Call):
                kind = _manual_temp_kind(sub, mkstemp_n, mkdtemp_n, ntf_n)
                if kind is None:
                    continue
                bound: set[str] = set()
                cur: ast.AST | None = sub
                while cur is not None and cur is not scope_node:
                    par = parent_map.get(id(cur))
                    if isinstance(par, ast.Assign) and cur is par.value or (
                        isinstance(par, ast.Assign) and any(cur is s for s in ast.walk(par.value))
                    ):
                        for tgt in par.targets:
                            bound |= _extract_binding_vars(tgt, kind)
                        break
                    if isinstance(par, ast.AnnAssign) and par.value is not None:
                        bound |= _extract_binding_vars(par.target, kind)
                        break
                    if isinstance(par, ast.NamedExpr) and cur is par.value:
                        bound |= _extract_binding_vars(par.target, kind)
                        break
                    if isinstance(par, ast.withitem) and par.optional_vars is not None:
                        bound |= _extract_binding_vars(par.optional_vars, kind)
                        break
                    if isinstance(par, (ast.Return, ast.Yield)):
                        bound.add("__returned__")
                        break
                    cur = par
                allocs.append((kind, sub.lineno, bound, id(sub)))

        if not allocs:
            continue

        # Propagate local aliases (`p = Path(tmp)`, `name = f.name`, etc.) inside `scope_node`.
        alias_edges: list[tuple[set[str], set[str]]] = []
        for sub in direct:
            if isinstance(sub, ast.Assign):
                rhs = _names_in_expr(sub.value)
                lhs: set[str] = set()
                for tgt in sub.targets:
                    lhs |= _names_in_expr(tgt)
                if lhs and rhs:
                    alias_edges.append((lhs, rhs))
            elif isinstance(sub, ast.AnnAssign) and sub.value is not None:
                lhs = _names_in_expr(sub.target)
                rhs = _names_in_expr(sub.value)
                if lhs and rhs:
                    alias_edges.append((lhs, rhs))

        nested_defs = {
            n.name: n
            for n in ast.iter_child_nodes(scope_node)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        called_names = {
            (sub.func.id if isinstance(sub.func, ast.Name) else "")
            for sub in direct
            if isinstance(sub, ast.Call)
        }
        # Include nested helpers registered via atexit.register(helper).
        for sub in direct:
            if isinstance(sub, ast.Call):
                for arg in sub.args:
                    if isinstance(arg, ast.Name) and arg.id in nested_defs:
                        called_names.add(arg.id)

        cleaned_vars: set[str] = set(_enclosing_class_attrs(scope_node))
        for sub in direct:
            if isinstance(sub, ast.Call):
                cleaned_vars |= _is_fs_cleanup_call(sub, os_rep, shutil_a, atexit_a, helper_cleaners)
        for hname in called_names & set(nested_defs):
            hnode = nested_defs[hname]
            for sub in _iter_direct_nodes(hnode):
                if isinstance(sub, ast.Call):
                    cleaned_vars |= _is_fs_cleanup_call(sub, os_rep, shutil_a, atexit_a, helper_cleaners)

        returned_vars: set[str] = set()
        if isinstance(scope_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in direct:
                if isinstance(sub, (ast.Return, ast.Yield)) and sub.value is not None:
                    returned_vars |= _transferred_vars_in_expr(sub.value)

        for kind, lineno, initial_bound, _ in allocs:
            if not initial_bound:
                errors.append(
                    f"{scope_label} allocates {kind} (line {lineno}) without binding or cleaning up the path"
                )
                continue
            tracked = set(initial_bound)
            for _ in range(4):
                for lhs, rhs in alias_edges:
                    if rhs & tracked:
                        tracked |= lhs
            locally_cleaned = bool(tracked & cleaned_vars)
            transferred = ("__returned__" in tracked or bool(tracked & returned_vars)) and module_has_fs_cleanup
            if not (locally_cleaned or transferred):
                errors.append(
                    f"{scope_label} allocates {kind} (line {lineno}) without cleanup "
                    "(`unlink`/`os.replace`/`rmtree`/`atexit.register`) or ownership transfer"
                )
    return errors


def _expr_platform_polarity(
    expr: ast.AST,
    os_aliases: set[str],
    sys_aliases: set[str],
    win_bools: set[str],
    posix_bools: set[str],
) -> str | None:
    """Return 'windows', 'posix', or None for an AST boolean guard expression."""
    if isinstance(expr, ast.Name):
        if expr.id in win_bools:
            return "windows"
        if expr.id in posix_bools:
            return "posix"
        return None
    if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.Not):
        inner = _expr_platform_polarity(expr.operand, os_aliases, sys_aliases, win_bools, posix_bools)
        return "posix" if inner == "windows" else ("windows" if inner == "posix" else None)
    if isinstance(expr, ast.BoolOp):
        parts = [_expr_platform_polarity(v, os_aliases, sys_aliases, win_bools, posix_bools) for v in expr.values]
        if isinstance(expr.op, ast.And) and "posix" in parts and "windows" not in parts:
            return "posix"
        if isinstance(expr.op, ast.Or) and all(p == "windows" for p in parts):
            return "windows"
        return None
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute):
        recv = expr.func.value
        if (
            isinstance(recv, ast.Attribute)
            and isinstance(recv.value, ast.Name)
            and recv.value.id in sys_aliases
            and recv.attr == "platform"
            and expr.func.attr == "startswith"
            and expr.args
            and isinstance(expr.args[0], ast.Constant)
            and str(expr.args[0].value).startswith("win")
        ):
            return "windows"
    if isinstance(expr, ast.Compare) and len(expr.ops) == 1 and len(expr.comparators) == 1:
        left, op, right = expr.left, expr.ops[0], expr.comparators[0]
        if (
            isinstance(left, ast.Attribute)
            and isinstance(left.value, ast.Name)
            and left.value.id in os_aliases
            and left.attr == "name"
            and isinstance(right, ast.Constant)
        ):
            if right.value == "nt":
                return "windows" if isinstance(op, (ast.Eq, ast.Is)) else ("posix" if isinstance(op, (ast.NotEq, ast.IsNot)) else None)
            if right.value == "posix" and isinstance(op, (ast.Eq, ast.Is)):
                return "posix"
        if (
            isinstance(left, ast.Attribute)
            and isinstance(left.value, ast.Name)
            and left.value.id in sys_aliases
            and left.attr == "platform"
            and isinstance(right, ast.Constant)
        ):
            if str(right.value).startswith("win"):
                return "windows" if isinstance(op, (ast.Eq, ast.Is)) else ("posix" if isinstance(op, (ast.NotEq, ast.IsNot)) else None)
    return None


def _block_terminates(stmts: list[ast.stmt]) -> bool:
    return bool(stmts) and isinstance(stmts[-1], (ast.Return, ast.Raise, ast.Continue, ast.Break))


def inspect_storage_module_windows_pid_safety(path: Path) -> list[str]:
    """Ban `os.kill(pid, 0)` (or imported `kill(pid, 0)`) unless AST-proven POSIX-only."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    os_aliases = {"os"}
    sys_aliases = {"sys"}
    kill_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name
                if alias.name == "os":
                    os_aliases.add(bound)
                elif alias.name == "sys":
                    sys_aliases.add(bound)
        elif isinstance(node, ast.ImportFrom) and node.module == "os":
            for alias in node.names:
                if alias.name == "kill":
                    kill_names.add(alias.asname or alias.name)

    win_bools: set[str] = set()
    posix_bools: set[str] = set()
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            pol = _expr_platform_polarity(stmt.value, os_aliases, sys_aliases, win_bools, posix_bools)
            if pol == "windows":
                win_bools.add(stmt.targets[0].id)
            elif pol == "posix":
                posix_bools.add(stmt.targets[0].id)

    errors: list[str] = []

    def _visit(node: ast.AST, posix_proven: bool, scope_name: str) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # A function definition resets control-flow guards unless already inside a POSIX-only block.
            _visit_stmt_list(node.body, posix_proven, node.name)
            return
        if isinstance(node, ast.ClassDef):
            _visit_stmt_list(node.body, posix_proven, node.name)
            return
        if isinstance(node, ast.If):
            pol = _expr_platform_polarity(node.test, os_aliases, sys_aliases, win_bools, posix_bools)
            _visit_stmt_list(node.body, posix_proven or (pol == "posix"), scope_name)
            _visit_stmt_list(node.orelse, posix_proven or (pol == "windows"), scope_name)
            return
        if isinstance(node, ast.IfExp):
            pol = _expr_platform_polarity(node.test, os_aliases, sys_aliases, win_bools, posix_bools)
            _visit(node.test, posix_proven, scope_name)
            _visit(node.body, posix_proven or (pol == "posix"), scope_name)
            _visit(node.orelse, posix_proven or (pol == "windows"), scope_name)
            return
        if isinstance(node, ast.Call):
            fn = node.func
            is_kill_zero = (
                len(node.args) == 2
                and isinstance(node.args[1], ast.Constant)
                and type(node.args[1].value) is int
                and node.args[1].value == 0
                and (
                    (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id in os_aliases and fn.attr == "kill")
                    or (isinstance(fn, ast.Name) and fn.id in kill_names)
                )
            )
            if is_kill_zero and not posix_proven:
                errors.append(
                    f"line {node.lineno} `{scope_name}` calls unguarded `os.kill(pid, 0)` "
                    "(terminates or misprobes processes on Windows; guard with `os.name != 'nt'` or use Win32 `OpenProcess`)"
                )
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                if value and all(isinstance(item, ast.stmt) for item in value):
                    _visit_stmt_list(value, posix_proven, scope_name)
                else:
                    for item in value:
                        if isinstance(item, ast.AST):
                            _visit(item, posix_proven, scope_name)
            elif isinstance(value, ast.AST):
                _visit(value, posix_proven, scope_name)

    def _visit_stmt_list(stmts: list[ast.stmt], posix_proven: bool, scope_name: str) -> None:
        cur_posix = posix_proven
        for stmt in stmts:
            _visit(stmt, cur_posix, scope_name)
            if isinstance(stmt, ast.If) and not stmt.orelse:
                pol = _expr_platform_polarity(stmt.test, os_aliases, sys_aliases, win_bools, posix_bools)
                if pol == "windows" and _block_terminates(stmt.body):
                    cur_posix = True

    _visit_stmt_list(tree.body, False, "<module>")
    return errors


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


def _caller_invokes_storage_gc(caller_path: Path, storage_stems: frozenset[str]) -> bool:
    tree = ast.parse(caller_path.read_text(encoding="utf-8"), filename=str(caller_path))
    imported_modules: set[str] = set()
    imported_callables: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                stem = alias.name.rsplit(".", 1)[-1]
                if stem in storage_stems:
                    imported_modules.add(alias.asname or stem)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mod_parts = set(node.module.split("."))
            if mod_parts & storage_stems:
                for alias in node.names:
                    bound = alias.asname or alias.name
                    if alias.name in storage_stems:
                        imported_modules.add(bound)
                    else:
                        imported_callables.add(bound)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Name) and fn.id in imported_callables:
            return True
        if isinstance(fn, ast.Attribute):
            if isinstance(fn.value, ast.Name) and fn.value.id in imported_modules:
                return True
            if (
                isinstance(fn.value, ast.Call)
                and isinstance(fn.value.func, ast.Name)
                and fn.value.args
                and isinstance(fn.value.args[0], ast.Constant)
                and str(fn.value.args[0].value) in storage_stems
            ):
                return True
    return False


def _test_file_isolates_sandbox_ast(path: Path) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return False
    seen_env_keys: set[str] = set()
    uses_temp_fixture = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in _SANDBOX_ENV_KEYS:
            seen_env_keys.add(node.value)
        elif isinstance(node, ast.Call):
            fn = node.func
            cname = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "")
            if cname in {"TemporaryDirectory", "mkdtemp", "setenv", "patch"}:
                uses_temp_fixture = True
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if any(a.arg in {"tmp_path", "monkeypatch"} for a in node.args.args):
                uses_temp_fixture = True
    return uses_temp_fixture and len(seen_env_keys) >= 2


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
            wired = False
            for rel in present_callers:
                try:
                    if _caller_invokes_storage_gc(repo_dir / rel, storage_stems):
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
        if tests_dir.is_dir():
            conftest = tests_dir / "conftest.py"
            sample_files = [conftest] if conftest.is_file() else sorted(tests_dir.glob("test_*.py"))[:10]
            if not any(_test_file_isolates_sandbox_ast(tf) for tf in sample_files):
                errors.append(
                    f"{repo_name}: tests/ missing AST-verified host sandbox isolation "
                    "(expected conftest.py or test fixtures redirecting HOME and MindIE roots)"
                )

    return errors

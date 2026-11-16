#!/usr/bin/env python3
"""Per-allocation tempfile ownership and scope-aware Windows PID AST analyzers (Guardrail P8).

[Role]
Provides pure-stdlib AST analyzers (`inspect_python_temp_hygiene` and
`inspect_storage_module_windows_pid_safety`) imported by `storage_lifecycle_gate.py` to keep
each module well under the 800-line Agent-Native budget.

[Invariants]
- Tracks each manual tempfile allocation (`mkstemp`, `mkdtemp`, `NamedTemporaryFile(delete=False)`)
  by allocation identity and line range so overwriting a variable (`d = mkdtemp(); d = mkdtemp()`)
  or cleaning a child/string expression (`rmtree(Path(d) / 'x')`, `d.replace('a', 'b')`) never
  discharges an uncleaned directory or file.
- Treats nested cleanup helpers as invoked only when directly called (`helper()`) or registered
  as the callback in `atexit.register(helper)`, never when passed to arbitrary calls (`print(helper)`).
- Proves `os.kill(pid, 0)` POSIX-only execution across `If.test`, branches, early-return guards,
  and scope-shadowed bindings.

[Timeouts & Locks]
- Pure in-memory AST traversal; acquires no locks and spawns no subprocesses.

[Side-Effect Policy]
- Read-only inspection of Python source files.
"""

from __future__ import annotations

import ast
from pathlib import Path

_DIRECT_FS_CLEANUP_FNS: frozenset[str] = frozenset(
    {
        "unlink", "remove", "rmdir", "rmtree", "rmtree_force",
        "_rmtree_force", "_safe_unlink", "_remove_path", "_cleanup_temp", "retire_directory",
    }
)
_PATH_WRAPPERS: frozenset[str] = frozenset({"Path", "PurePath", "PosixPath", "WindowsPath", "str"})
_NON_TRANSFER_BUILTINS: frozenset[str] = frozenset(
    {
        "bool", "int", "float", "len", "repr", "ascii", "hash", "id", "type",
        "isinstance", "issubclass", "callable", "print", "any", "all", "sum",
        "min", "max", "sorted", "enumerate", "Exception", "RuntimeError",
        "ValueError", "TypeError", "OSError",
    }
)


def iter_direct_nodes(root: ast.AST) -> list[ast.AST]:
    """Walk AST nodes inside `root` without crossing into nested function or class scopes."""
    out: list[ast.AST] = []
    stack: list[ast.AST] = list(ast.iter_child_nodes(root))
    while stack:
        cur = stack.pop()
        out.append(cur)
        if not isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            stack.extend(ast.iter_child_nodes(cur))
    return out


def local_bound_names(scope: ast.AST) -> set[str]:
    """Return all identifier names locally bound inside `scope` (excluding nested scopes)."""
    bound: set[str] = set()
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        args = scope.args
        for a in (*args.posonlyargs, *args.args, *args.kwonlyargs):
            bound.add(a.arg)
        if args.vararg:
            bound.add(args.vararg.arg)
        if args.kwarg:
            bound.add(args.kwarg.arg)
    for node in iter_direct_nodes(scope):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                for sub in ast.walk(tgt):
                    if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                        bound.add(sub.id)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            for sub in ast.walk(node.target):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                    bound.add(sub.id)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            for sub in ast.walk(node.target):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                    bound.add(sub.id)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    for sub in ast.walk(item.optional_vars):
                        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                            bound.add(sub.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bound.add(alias.asname or alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                bound.add(alias.asname or alias.name)
    return bound


def _whole_path_vars(
    expr: ast.AST | None,
    *,
    os_aliases: set[str],
    ntf_vars: set[str] = frozenset(),
    tuple_vars: set[str] = frozenset(),
) -> set[str]:
    """Return variable/`self.attr` names only when `expr` denotes the whole path/handle itself."""
    if expr is None:
        return set()
    if isinstance(expr, ast.Name):
        return {expr.id}
    if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
        if expr.value.id == "self":
            return {f"self.{expr.attr}"}
        if expr.attr == "name":
            return {expr.value.id} if not ntf_vars or expr.value.id in ntf_vars else {expr.value.id}
        return set()
    if (
        isinstance(expr, ast.Subscript)
        and isinstance(expr.value, ast.Name)
        and isinstance(expr.slice, ast.Constant)
        and expr.slice.value == 1
        and (not tuple_vars or expr.value.id in tuple_vars)
    ):
        return {expr.value.id}
    if isinstance(expr, ast.IfExp):
        return _whole_path_vars(
            expr.body, os_aliases=os_aliases, ntf_vars=ntf_vars, tuple_vars=tuple_vars
        ) | _whole_path_vars(
            expr.orelse, os_aliases=os_aliases, ntf_vars=ntf_vars, tuple_vars=tuple_vars
        )
    if isinstance(expr, ast.Call) and len(expr.args) == 1 and not expr.keywords:
        fn = expr.func
        if isinstance(fn, ast.Name) and fn.id in _PATH_WRAPPERS:
            return _whole_path_vars(expr.args[0], os_aliases=os_aliases, ntf_vars=ntf_vars, tuple_vars=tuple_vars)
        if (
            isinstance(fn, ast.Attribute)
            and isinstance(fn.value, ast.Name)
            and fn.value.id in os_aliases
            and fn.attr in {"fspath", "abspath", "realpath"}
        ):
            return _whole_path_vars(expr.args[0], os_aliases=os_aliases, ntf_vars=ntf_vars, tuple_vars=tuple_vars)
        if isinstance(fn, ast.Attribute) and fn.attr in {"resolve", "absolute"} and not expr.args:
            return _whole_path_vars(fn.value, os_aliases=os_aliases, ntf_vars=ntf_vars, tuple_vars=tuple_vars)
    if isinstance(expr, ast.Call) and not expr.args and not expr.keywords:
        fn = expr.func
        if isinstance(fn, ast.Attribute) and fn.attr in {"resolve", "absolute"}:
            return _whole_path_vars(fn.value, os_aliases=os_aliases, ntf_vars=ntf_vars, tuple_vars=tuple_vars)
    return set()


def _transferred_whole_vars(
    node: ast.AST | None,
    *,
    os_aliases: set[str],
    module_classes: set[str],
    ntf_vars: set[str],
    tuple_vars: set[str],
) -> set[str]:
    if node is None:
        return set()
    direct = _whole_path_vars(node, os_aliases=os_aliases, ntf_vars=ntf_vars, tuple_vars=tuple_vars)
    if direct:
        return direct
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        out: set[str] = set()
        for elt in node.elts:
            out |= _transferred_whole_vars(
                elt, os_aliases=os_aliases, module_classes=module_classes, ntf_vars=ntf_vars, tuple_vars=tuple_vars
            )
        return out
    if isinstance(node, ast.Dict):
        out = set()
        for val in node.values:
            out |= _transferred_whole_vars(
                val, os_aliases=os_aliases, module_classes=module_classes, ntf_vars=ntf_vars, tuple_vars=tuple_vars
            )
        return out
    if isinstance(node, ast.Call):
        fn = node.func
        is_carrier_ctor = (
            isinstance(fn, ast.Name)
            and fn.id not in _NON_TRANSFER_BUILTINS
            and (fn.id in module_classes or fn.id[:1].isupper() or fn.id == "dict")
        )
        if is_carrier_ctor:
            out = set()
            for arg in node.args:
                out |= _transferred_whole_vars(
                    arg, os_aliases=os_aliases, module_classes=module_classes, ntf_vars=ntf_vars, tuple_vars=tuple_vars
                )
            for kw in node.keywords:
                out |= _transferred_whole_vars(
                    kw.value, os_aliases=os_aliases, module_classes=module_classes, ntf_vars=ntf_vars, tuple_vars=tuple_vars
                )
            return out
    return set()


def _collect_temp_aliases(tree: ast.Module) -> tuple[set[str], set[str], set[str], set[str], set[str], set[str], set[str]]:
    mkstemp_names = {"mkstemp"}
    mkdtemp_names = {"mkdtemp"}
    ntf_names = {"NamedTemporaryFile"}
    os_aliases = {"os"}
    os_replace_names: set[str] = set()
    shutil_aliases = {"shutil"}
    atexit_aliases = {"atexit"}
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
                elif mod == "os" and alias.name in {"replace", "rename", "unlink", "remove", "rmdir"}:
                    os_replace_names.add(bound)
                elif mod == "shutil" and alias.name in {"rmtree", "move"}:
                    os_replace_names.add(bound)
    return mkstemp_names, mkdtemp_names, ntf_names, os_aliases, os_replace_names, shutil_aliases, atexit_aliases


def _manual_temp_kind(node: ast.Call, mkstemp_n: set[str], mkdtemp_n: set[str], ntf_n: set[str]) -> str | None:
    fn = node.func
    cname = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "")
    if cname in mkstemp_n:
        return "mkstemp"
    if cname in mkdtemp_n:
        return "mkdtemp"
    if cname in ntf_n:
        for kw in node.keywords:
            if kw.arg == "delete" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                return "NamedTemporaryFile(delete=False)"
    return None


def _cleaned_whole_targets(
    call: ast.Call,
    *,
    os_aliases: set[str],
    os_direct_fns: set[str],
    shutil_aliases: set[str],
    atexit_aliases: set[str],
    helper_cleaners: set[str],
    ntf_vars: set[str] = frozenset(),
    tuple_vars: set[str] = frozenset(),
) -> set[str]:
    fn = call.func
    kw_opts = dict(os_aliases=os_aliases, ntf_vars=ntf_vars, tuple_vars=tuple_vars)
    if isinstance(fn, ast.Name):
        if fn.id in _DIRECT_FS_CLEANUP_FNS or fn.id in helper_cleaners or fn.id in os_direct_fns:
            return _whole_path_vars(call.args[0], **kw_opts) if call.args else set()
        return set()
    if isinstance(fn, ast.Attribute):
        recv = fn.value
        if isinstance(recv, ast.Name):
            if recv.id in os_aliases:
                if fn.attr in {"unlink", "remove", "rmdir"} and call.args:
                    return _whole_path_vars(call.args[0], **kw_opts)
                if fn.attr in {"replace", "rename"} and len(call.args) >= 2:
                    return _whole_path_vars(call.args[0], **kw_opts)
                return set()
            if recv.id in shutil_aliases and fn.attr in {"rmtree", "move"} and call.args:
                return _whole_path_vars(call.args[0], **kw_opts)
            if recv.id in atexit_aliases and fn.attr == "register":
                out: set[str] = set()
                for arg in call.args[1:]:
                    out |= _whole_path_vars(arg, **kw_opts)
                if call.args and isinstance(call.args[0], ast.Lambda):
                    for sub in ast.walk(call.args[0]):
                        if isinstance(sub, ast.Call):
                            out |= _cleaned_whole_targets(
                                sub,
                                os_aliases=os_aliases,
                                os_direct_fns=os_direct_fns,
                                shutil_aliases=shutil_aliases,
                                atexit_aliases=atexit_aliases,
                                helper_cleaners=helper_cleaners,
                                ntf_vars=ntf_vars,
                                tuple_vars=tuple_vars,
                            )
                return out
        if fn.attr in {"unlink", "cleanup"} and not isinstance(recv, ast.Constant):
            return _whole_path_vars(recv, **kw_opts)
        if fn.attr in {"replace", "rename"} and len(call.args) == 1 and not call.keywords and not isinstance(recv, ast.Constant):
            return _whole_path_vars(recv, **kw_opts)
    return set()


def _extract_binding_vars(target: ast.AST, kind: str) -> tuple[set[str], bool]:
    if isinstance(target, ast.Name):
        if target.id == "_":
            return set(), False
        return {target.id}, (kind == "mkstemp")
    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
        return {f"self.{target.attr}"}, (kind == "mkstemp")
    if isinstance(target, (ast.Tuple, ast.List)):
        if kind == "mkstemp" and len(target.elts) >= 2:
            v, _ = _extract_binding_vars(target.elts[1], "path")
            return v, False
        out: set[str] = set()
        for elt in target.elts:
            v, _ = _extract_binding_vars(elt, kind)
            out |= v
        return out, False
    return set(), False


def inspect_python_temp_hygiene(path: Path) -> list[str]:
    """Verify every manual tempfile allocation in `path` is individually cleaned up or transferred."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    errors: list[str] = []
    mkstemp_n, mkdtemp_n, ntf_n, os_a, os_fns, shutil_a, atexit_a = _collect_temp_aliases(tree)
    module_classes = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}

    all_fns = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    helper_cleaners: set[str] = set()
    for _ in range(2):
        for fn_node in all_fns:
            params = {a.arg for a in (*fn_node.args.posonlyargs, *fn_node.args.args, *fn_node.args.kwonlyargs)}
            for sub in iter_direct_nodes(fn_node):
                if isinstance(sub, ast.Call):
                    cleaned = _cleaned_whole_targets(
                        sub,
                        os_aliases=os_a,
                        os_direct_fns=os_fns,
                        shutil_aliases=shutil_a,
                        atexit_aliases=atexit_a,
                        helper_cleaners=helper_cleaners,
                    )
                    if cleaned & params:
                        helper_cleaners.add(fn_node.name)

    module_has_fs_cleanup = bool(helper_cleaners) or any(
        isinstance(sub, ast.Call)
        and bool(
            _cleaned_whole_targets(
                sub,
                os_aliases=os_a,
                os_direct_fns=os_fns,
                shutil_aliases=shutil_a,
                atexit_aliases=atexit_a,
                helper_cleaners=helper_cleaners,
            )
        )
        for sub in ast.walk(tree)
    )

    class_cleaned_attrs: dict[int, set[str]] = {}
    for cls_node in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        attrs: set[str] = set()
        for sub in ast.walk(cls_node):
            if isinstance(sub, ast.Call):
                cleaned = _cleaned_whole_targets(
                    sub,
                    os_aliases=os_a,
                    os_direct_fns=os_fns,
                    shutil_aliases=shutil_a,
                    atexit_aliases=atexit_a,
                    helper_cleaners=helper_cleaners,
                )
                attrs |= {v for v in cleaned if v.startswith("self.")}
        class_cleaned_attrs[id(cls_node)] = attrs

    parent_map: dict[int, ast.AST] = {
        id(child): parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)
    }

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
        direct = iter_direct_nodes(scope_node)
        ntf_vars: set[str] = set()
        tuple_vars: set[str] = set()
        # (kind, lineno, bound_vars, call_id)
        allocs: list[tuple[str, int, set[str], int]] = []
        for sub in direct:
            if isinstance(sub, ast.Call):
                kind = _manual_temp_kind(sub, mkstemp_n, mkdtemp_n, ntf_n)
                if kind is None:
                    continue
                bound: set[str] = set()
                is_tup = False
                cur: ast.AST | None = sub
                while cur is not None and cur is not scope_node:
                    par = parent_map.get(id(cur))
                    if isinstance(par, ast.Assign) and any(cur is s for s in ast.walk(par.value)):
                        for tgt in par.targets:
                            v, t = _extract_binding_vars(tgt, kind)
                            bound |= v
                            is_tup = is_tup or t
                        break
                    if isinstance(par, ast.AnnAssign) and par.value is not None:
                        bound, is_tup = _extract_binding_vars(par.target, kind)
                        break
                    if isinstance(par, ast.NamedExpr) and cur is par.value:
                        bound, is_tup = _extract_binding_vars(par.target, kind)
                        break
                    if isinstance(par, ast.withitem) and par.optional_vars is not None:
                        bound, is_tup = _extract_binding_vars(par.optional_vars, kind)
                        break
                    if isinstance(par, (ast.Return, ast.Yield)):
                        bound.add("__returned__")
                        break
                    cur = par
                if kind == "NamedTemporaryFile(delete=False)":
                    ntf_vars |= bound
                if is_tup:
                    tuple_vars |= bound
                allocs.append((kind, sub.lineno, bound, id(sub)))

        if not allocs:
            continue

        # Record assignment lines per variable to catch `d = mkdtemp(); d = mkdtemp()` overwrites.
        assign_events: list[tuple[int, set[str], set[str], int | None]] = []
        alloc_ids = {cid for _, _, _, cid in allocs}
        for sub in direct:
            if isinstance(sub, ast.Assign):
                matched_cid = next((cid for cid in alloc_ids if any( id(s) == cid for s in ast.walk(sub.value))), None)
                lhs: set[str] = set()
                for tgt in sub.targets:
                    v, _ = _extract_binding_vars(tgt, "path")
                    lhs |= v
                rhs = _whole_path_vars(sub.value, os_aliases=os_a, ntf_vars=ntf_vars, tuple_vars=tuple_vars)
                if lhs:
                    assign_events.append((sub.lineno, lhs, rhs, matched_cid))
            elif isinstance(sub, ast.AnnAssign) and sub.value is not None:
                matched_cid = next((cid for cid in alloc_ids if any(id(s) == cid for s in ast.walk(sub.value))), None)
                lhs, _ = _extract_binding_vars(sub.target, "path")
                rhs = _whole_path_vars(sub.value, os_aliases=os_a, ntf_vars=ntf_vars, tuple_vars=tuple_vars)
                if lhs:
                    assign_events.append((sub.lineno, lhs, rhs, matched_cid))

        nested_defs = {
            n.name: n
            for n in ast.iter_child_nodes(scope_node)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        invoked_nested: list[tuple[str, int]] = []
        for sub in direct:
            if isinstance(sub, ast.Call):
                if isinstance(sub.func, ast.Name) and sub.func.id in nested_defs:
                    invoked_nested.append((sub.func.id, sub.lineno))
                elif (
                    isinstance(sub.func, ast.Attribute)
                    and isinstance(sub.func.value, ast.Name)
                    and sub.func.value.id in atexit_a
                    and sub.func.attr == "register"
                    and sub.args
                    and isinstance(sub.args[0], ast.Name)
                    and sub.args[0].id in nested_defs
                ):
                    invoked_nested.append((sub.args[0].id, 10**9))

        cleanup_events: list[tuple[int, set[str]]] = []
        for attr_name in _enclosing_class_attrs(scope_node):
            cleanup_events.append((10**9, {attr_name}))
        for sub in direct:
            if isinstance(sub, ast.Call):
                cv = _cleaned_whole_targets(
                    sub,
                    os_aliases=os_a,
                    os_direct_fns=os_fns,
                    shutil_aliases=shutil_a,
                    atexit_aliases=atexit_a,
                    helper_cleaners=helper_cleaners,
                    ntf_vars=ntf_vars,
                    tuple_vars=tuple_vars,
                )
                if cv:
                    cleanup_events.append((sub.lineno, cv))
        for hname, call_ln in invoked_nested:
            for sub in iter_direct_nodes(nested_defs[hname]):
                if isinstance(sub, ast.Call):
                    cv = _cleaned_whole_targets(
                        sub,
                        os_aliases=os_a,
                        os_direct_fns=os_fns,
                        shutil_aliases=shutil_a,
                        atexit_aliases=atexit_a,
                        helper_cleaners=helper_cleaners,
                        ntf_vars=ntf_vars,
                        tuple_vars=tuple_vars,
                    )
                    if cv:
                        cleanup_events.append((call_ln, cv))

        return_events: list[tuple[int, set[str]]] = []
        if isinstance(scope_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in direct:
                if isinstance(sub, (ast.Return, ast.Yield)) and sub.value is not None:
                    rv = _transferred_whole_vars(
                        sub.value,
                        os_aliases=os_a,
                        module_classes=module_classes,
                        ntf_vars=ntf_vars,
                        tuple_vars=tuple_vars,
                    )
                    if rv:
                        return_events.append((sub.lineno, rv))

        for kind, alloc_ln, initial_bound, alloc_cid in allocs:
            if not initial_bound:
                errors.append(
                    f"{scope_label} allocates {kind} (line {alloc_ln}) without binding or cleaning up the path"
                )
                continue
            if "__returned__" in initial_bound and module_has_fs_cleanup:
                continue

            # Compute `[start_ln, overwrite_ln)` live window for each variable holding this allocation.
            var_windows: dict[str, tuple[int, int]] = {}
            for v in initial_bound:
                overwrites = [
                    ln
                    for ln, lhs, rhs, cid in assign_events
                    if v in lhs and cid != alloc_cid and ln > alloc_ln and v not in rhs
                ]
                var_windows[v] = (alloc_ln, min(overwrites) if overwrites else 10**9 + 1)

            for _ in range(3):
                for ln, lhs, rhs, cid in sorted(assign_events, key=lambda x: x[0]):
                    if cid == alloc_cid:
                        continue
                    if any(r in var_windows and var_windows[r][0] <= ln < var_windows[r][1] for r in rhs):
                        for v in lhs:
                            overwrites = [
                                oln
                                for oln, olhs, orhs, _ in assign_events
                                if v in olhs and oln > ln and v not in orhs
                            ]
                            var_windows[v] = (ln, min(overwrites) if overwrites else 10**9 + 1)

            cleaned = any(
                v in var_windows and var_windows[v][0] <= cln < var_windows[v][1]
                for cln, cvars in cleanup_events
                for v in cvars
            )
            transferred = module_has_fs_cleanup and any(
                v in var_windows and var_windows[v][0] <= rln < var_windows[v][1]
                for rln, rvars in return_events
                for v in rvars
            )
            if not (cleaned or transferred):
                errors.append(
                    f"{scope_label} allocates {kind} (line {alloc_ln}) without cleanup "
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
    if isinstance(expr, ast.Name):
        return "windows" if expr.id in win_bools else ("posix" if expr.id in posix_bools else None)
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
            and str(right.value).startswith("win")
        ):
            return "windows" if isinstance(op, (ast.Eq, ast.Is)) else ("posix" if isinstance(op, (ast.NotEq, ast.IsNot)) else None)
    return None


def inspect_storage_module_windows_pid_safety(path: Path) -> list[str]:
    """Ban `os.kill(pid, 0)` (or imported `kill(pid, 0)`) unless AST-proven POSIX-only."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    base_os = {"os"}
    base_sys = {"sys"}
    base_kill: set[str] = set()
    for stmt in tree.body:
        if isinstance(stmt, ast.Import):
            for alias in stmt.names:
                bound = alias.asname or alias.name
                if alias.name == "os":
                    base_os.add(bound)
                elif alias.name == "sys":
                    base_sys.add(bound)
        elif isinstance(stmt, ast.ImportFrom) and stmt.module == "os":
            for alias in stmt.names:
                if alias.name == "kill":
                    base_kill.add(alias.asname or alias.name)

    top_assign_counts: dict[str, int] = {}
    for node in iter_direct_nodes(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            top_assign_counts[node.id] = top_assign_counts.get(node.id, 0) + 1

    base_win: set[str] = set()
    base_posix: set[str] = set()
    for stmt in tree.body:
        if (
            isinstance(stmt, ast.Assign)
            and len(stmt.targets) == 1
            and isinstance(stmt.targets[0], ast.Name)
            and top_assign_counts.get(stmt.targets[0].id, 0) == 1
        ):
            pol = _expr_platform_polarity(stmt.value, base_os, base_sys, base_win, base_posix)
            if pol == "windows":
                base_win.add(stmt.targets[0].id)
            elif pol == "posix":
                base_posix.add(stmt.targets[0].id)

    errors: list[str] = []

    def _visit(
        node: ast.AST,
        posix_proven: bool,
        scope_name: str,
        os_a: set[str],
        sys_a: set[str],
        win_b: set[str],
        pos_b: set[str],
        kill_n: set[str],
    ) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            shadowed = local_bound_names(node)
            n_os, n_sys = os_a - shadowed, sys_a - shadowed
            n_win, n_pos = win_b - shadowed, pos_b - shadowed
            n_kill = kill_n | {
                alias.asname or alias.name
                for sub in iter_direct_nodes(node)
                if isinstance(sub, ast.ImportFrom) and sub.module == "os"
                for alias in sub.names
                if alias.name == "kill"
            }
            label = getattr(node, "name", scope_name)
            if isinstance(node, ast.Lambda):
                _visit(node.body, posix_proven, label, n_os, n_sys, n_win, n_pos, n_kill)
            else:
                # Visit default arg expressions at outer scope before entering body.
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for dflt in (*node.args.defaults, *(d for d in node.args.kw_defaults if d is not None)):
                        _visit(dflt, posix_proven, scope_name, os_a, sys_a, win_b, pos_b, kill_n)
                _visit_stmts(node.body, posix_proven, label, n_os, n_sys, n_win, n_pos, n_kill)
            return
        if isinstance(node, ast.If):
            _visit(node.test, posix_proven, scope_name, os_a, sys_a, win_b, pos_b, kill_n)
            pol = _expr_platform_polarity(node.test, os_a, sys_a, win_b, pos_b)
            _visit_stmts(node.body, posix_proven or (pol == "posix"), scope_name, os_a, sys_a, win_b, pos_b, kill_n)
            _visit_stmts(node.orelse, posix_proven or (pol == "windows"), scope_name, os_a, sys_a, win_b, pos_b, kill_n)
            return
        if isinstance(node, ast.IfExp):
            _visit(node.test, posix_proven, scope_name, os_a, sys_a, win_b, pos_b, kill_n)
            pol = _expr_platform_polarity(node.test, os_a, sys_a, win_b, pos_b)
            _visit(node.body, posix_proven or (pol == "posix"), scope_name, os_a, sys_a, win_b, pos_b, kill_n)
            _visit(node.orelse, posix_proven or (pol == "windows"), scope_name, os_a, sys_a, win_b, pos_b, kill_n)
            return
        if isinstance(node, ast.Call):
            fn = node.func
            is_kill_zero = (
                len(node.args) == 2
                and isinstance(node.args[1], ast.Constant)
                and type(node.args[1].value) is int
                and node.args[1].value == 0
                and (
                    (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id in os_a and fn.attr == "kill")
                    or (isinstance(fn, ast.Name) and fn.id in kill_n)
                )
            )
            if is_kill_zero and not posix_proven:
                errors.append(
                    f"line {node.lineno} `{scope_name}` calls unguarded `os.kill(pid, 0)` "
                    "(terminates or misprobes processes on Windows; guard with `os.name != 'nt'` or use Win32 `OpenProcess`)"
                )
        for _, value in ast.iter_fields(node):
            if isinstance(value, list):
                if value and all(isinstance(item, ast.stmt) for item in value):
                    _visit_stmts(value, posix_proven, scope_name, os_a, sys_a, win_b, pos_b, kill_n)
                else:
                    for item in value:
                        if isinstance(item, ast.AST):
                            _visit(item, posix_proven, scope_name, os_a, sys_a, win_b, pos_b, kill_n)
            elif isinstance(value, ast.AST):
                _visit(value, posix_proven, scope_name, os_a, sys_a, win_b, pos_b, kill_n)

    def _visit_stmts(
        stmts: list[ast.stmt],
        posix_proven: bool,
        scope_name: str,
        os_a: set[str],
        sys_a: set[str],
        win_b: set[str],
        pos_b: set[str],
        kill_n: set[str],
    ) -> None:
        cur_posix = posix_proven
        for stmt in stmts:
            _visit(stmt, cur_posix, scope_name, os_a, sys_a, win_b, pos_b, kill_n)
            if isinstance(stmt, ast.If) and not stmt.orelse:
                pol = _expr_platform_polarity(stmt.test, os_a, sys_a, win_b, pos_b)
                if pol == "windows" and stmt.body and isinstance(stmt.body[-1], (ast.Return, ast.Raise, ast.Continue, ast.Break)):
                    cur_posix = True

    _visit_stmts(tree.body, False, "<module>", base_os, base_sys, base_win, base_posix, base_kill)
    return errors

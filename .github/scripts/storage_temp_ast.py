#!/usr/bin/env python3
"""Per-allocation tempfile ownership AST analyzer and scope helpers (Guardrail P8).

[Role]
Provides pure-stdlib AST scope helpers (`iter_direct_nodes`, `pattern_bound_names`,
`non_import_bound_names`, `local_bound_names`) and per-allocation tempfile hygiene verification
(`inspect_python_temp_hygiene`) imported by `storage_lifecycle_gate.py` and `storage_pid_ast.py`
so every module stays well below the 800-line Agent-Native budget.

[Invariants]
- Tracks each manual tempfile allocation (`mkstemp`, `mkdtemp`, `NamedTemporaryFile(delete=False)`)
  by monotonic pre-order AST sequence ID (`seq`), catching same-line `;` overwrites, `NamedExpr`
  walrus reassignments, `Path.name` basename misuse, uninvoked lambdas, `atexit.register(print, d)`,
  prior-expression cleanups (`d = rmtree(d) or mkdtemp()`), and inline scalar returns
  (`return bool(tempfile.mkdtemp())`).

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
_SCOPE_BOUNDARY_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def iter_direct_nodes(root: ast.AST) -> list[ast.AST]:
    """Walk AST nodes inside `root` in pre-order without crossing into nested function/class/lambda scopes."""
    out: list[ast.AST] = []
    stack: list[ast.AST] = list(reversed(list(ast.iter_child_nodes(root))))
    while stack:
        cur = stack.pop()
        out.append(cur)
        if not isinstance(cur, _SCOPE_BOUNDARY_TYPES):
            stack.extend(reversed(list(ast.iter_child_nodes(cur))))
    return out


def pattern_bound_names(pat: ast.AST) -> set[str]:
    names: set[str] = set()
    for sub in ast.walk(pat):
        if isinstance(sub, ast.MatchAs) and sub.name:
            names.add(sub.name)
        elif isinstance(sub, ast.MatchStar) and sub.name:
            names.add(sub.name)
        elif isinstance(sub, ast.MatchMapping) and sub.rest:
            names.add(sub.rest)
    return names


def non_import_bound_names(scope: ast.AST) -> set[str]:
    """Return all identifier names bound by parameters, assignments, loops, handlers, defs, or match patterns."""
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
                bound |= {s.id for s in ast.walk(tgt) if isinstance(s, ast.Name) and isinstance(s.ctx, ast.Store)}
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            bound |= {s.id for s in ast.walk(node.target) if isinstance(s, ast.Name) and isinstance(s.ctx, ast.Store)}
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            bound |= {s.id for s in ast.walk(node.target) if isinstance(s, ast.Name) and isinstance(s.ctx, ast.Store)}
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    bound |= {
                        s.id for s in ast.walk(item.optional_vars) if isinstance(s, ast.Name) and isinstance(s.ctx, ast.Store)
                    }
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.Delete):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    bound.add(tgt.id)
        elif isinstance(node, ast.match_case):
            bound |= pattern_bound_names(node.pattern)
    return bound


def local_bound_names(scope: ast.AST) -> set[str]:
    """Return all identifier names locally bound inside `scope` (including imports and match patterns)."""
    bound = non_import_bound_names(scope)
    for node in iter_direct_nodes(scope):
        if isinstance(node, ast.Import):
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
            return {expr.value.id} if expr.value.id in ntf_vars else set()
        return set()
    if (
        isinstance(expr, ast.Subscript)
        and isinstance(expr.value, ast.Name)
        and isinstance(expr.slice, ast.Constant)
        and expr.slice.value == 1
        and expr.value.id in tuple_vars
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
    if isinstance(expr, ast.Call) and not expr.args and not expr.keywords:
        if isinstance(expr.func, ast.Attribute) and expr.func.attr in {"resolve", "absolute"}:
            return _whole_path_vars(expr.func.value, os_aliases=os_aliases, ntf_vars=ntf_vars, tuple_vars=tuple_vars)
    return set()


def _expr_transfers_target(
    node: ast.AST | None,
    *,
    os_aliases: set[str],
    module_classes: set[str],
    ntf_vars: set[str],
    tuple_vars: set[str],
    target_call_id: int | None = None,
) -> tuple[set[str], bool]:
    """Return `(transferred_vars, transfers_inline_call_id)` excluding scalar/string transforms."""
    if node is None:
        return set(), False
    if target_call_id is not None and id(node) == target_call_id:
        return set(), True
    direct = _whole_path_vars(node, os_aliases=os_aliases, ntf_vars=ntf_vars, tuple_vars=tuple_vars)
    if direct:
        return direct, False
    if isinstance(node, ast.Call) and len(node.args) == 1 and not node.keywords:
        fn = node.func
        if (isinstance(fn, ast.Name) and fn.id in _PATH_WRAPPERS) or (
            isinstance(fn, ast.Attribute)
            and isinstance(fn.value, ast.Name)
            and fn.value.id in os_aliases
            and fn.attr in {"fspath", "abspath", "realpath"}
        ):
            return _expr_transfers_target(
                node.args[0],
                os_aliases=os_aliases,
                module_classes=module_classes,
                ntf_vars=ntf_vars,
                tuple_vars=tuple_vars,
                target_call_id=target_call_id,
            )
    if isinstance(node, ast.Call) and not node.args and not node.keywords:
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"resolve", "absolute"}:
            return _expr_transfers_target(
                node.func.value,
                os_aliases=os_aliases,
                module_classes=module_classes,
                ntf_vars=ntf_vars,
                tuple_vars=tuple_vars,
                target_call_id=target_call_id,
            )
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        out: set[str] = set()
        hit = False
        for elt in node.elts:
            v, h = _expr_transfers_target(
                elt, os_aliases=os_aliases, module_classes=module_classes,
                ntf_vars=ntf_vars, tuple_vars=tuple_vars, target_call_id=target_call_id,
            )
            out |= v
            hit = hit or h
        return out, hit
    if isinstance(node, ast.Dict):
        out = set()
        hit = False
        for val in node.values:
            v, h = _expr_transfers_target(
                val, os_aliases=os_aliases, module_classes=module_classes,
                ntf_vars=ntf_vars, tuple_vars=tuple_vars, target_call_id=target_call_id,
            )
            out |= v
            hit = hit or h
        return out, hit
    if isinstance(node, ast.Call):
        fn = node.func
        is_carrier_ctor = (
            isinstance(fn, ast.Name)
            and fn.id not in _NON_TRANSFER_BUILTINS
            and (fn.id in module_classes or fn.id[:1].isupper() or fn.id == "dict")
        )
        if is_carrier_ctor:
            out = set()
            hit = False
            for arg in (*node.args, *(kw.value for kw in node.keywords)):
                v, h = _expr_transfers_target(
                    arg, os_aliases=os_aliases, module_classes=module_classes,
                    ntf_vars=ntf_vars, tuple_vars=tuple_vars, target_call_id=target_call_id,
                )
                out |= v
                hit = hit or h
            return out, hit
    return set(), False


def _collect_temp_aliases(tree: ast.Module) -> tuple[set[str], set[str], set[str], set[str], set[str], set[str], set[str]]:
    mkstemp_n, mkdtemp_n, ntf_n = {"mkstemp"}, {"mkdtemp"}, {"NamedTemporaryFile"}
    os_a, os_fns, shutil_a, atexit_a = {"os"}, set(), {"shutil"}, {"atexit"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name
                if alias.name == "os":
                    os_a.add(bound)
                elif alias.name == "shutil":
                    shutil_a.add(bound)
                elif alias.name == "atexit":
                    atexit_a.add(bound)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                bound = alias.asname or alias.name
                if mod == "tempfile":
                    if alias.name == "mkstemp":
                        mkstemp_n.add(bound)
                    elif alias.name == "mkdtemp":
                        mkdtemp_n.add(bound)
                    elif alias.name == "NamedTemporaryFile":
                        ntf_n.add(bound)
                elif mod == "os" and alias.name in {"replace", "rename", "unlink", "remove", "rmdir"}:
                    os_fns.add(bound)
                elif mod == "shutil" and alias.name in {"rmtree", "move"}:
                    os_fns.add(bound)
    return mkstemp_n, mkdtemp_n, ntf_n, os_a, os_fns, shutil_a, atexit_a


def _manual_temp_kind(node: ast.Call, mkstemp_n: set[str], mkdtemp_n: set[str], ntf_n: set[str]) -> tuple[str | None, bool]:
    fn = node.func
    cname = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "")
    has_self_dir = any(
        kw.arg == "dir"
        and isinstance(kw.value, ast.Attribute)
        and isinstance(kw.value.value, ast.Name)
        and kw.value.value.id == "self"
        for kw in node.keywords
    )
    if cname in mkstemp_n:
        return "mkstemp", has_self_dir
    if cname in mkdtemp_n:
        return "mkdtemp", has_self_dir
    if cname in ntf_n:
        if len(node.args) >= 8 and not (isinstance(node.args[7], ast.Constant) and node.args[7].value is True):
            return "NamedTemporaryFile(delete=False)", has_self_dir
        for kw in node.keywords:
            if kw.arg == "delete" and not (isinstance(kw.value, ast.Constant) and kw.value.value is True):
                return "NamedTemporaryFile(delete=False)", has_self_dir
    return None, False


def _is_verified_atexit_cleaner(
    cb: ast.AST,
    *,
    os_aliases: set[str],
    os_direct_fns: set[str],
    shutil_aliases: set[str],
    helper_cleaners: set[str],
) -> bool:
    if isinstance(cb, ast.Name):
        return cb.id in _DIRECT_FS_CLEANUP_FNS or cb.id in helper_cleaners or cb.id in os_direct_fns
    if isinstance(cb, ast.Attribute) and isinstance(cb.value, ast.Name):
        if cb.value.id in os_aliases and cb.attr in {"unlink", "remove", "rmdir"}:
            return True
        if cb.value.id in shutil_aliases and cb.attr == "rmtree":
            return True
    return False


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
            if recv.id in atexit_aliases and fn.attr == "register" and call.args:
                cb = call.args[0]
                if _is_verified_atexit_cleaner(
                    cb,
                    os_aliases=os_aliases,
                    os_direct_fns=os_direct_fns,
                    shutil_aliases=shutil_aliases,
                    helper_cleaners=helper_cleaners,
                ):
                    return _whole_path_vars(call.args[1], **kw_opts) if len(call.args) >= 2 else set()
                if isinstance(cb, ast.Lambda):
                    lam_params = [a.arg for a in cb.args.args]
                    bound_map = {
                        lam_params[idx]: _whole_path_vars(call.args[idx + 1], **kw_opts)
                        for idx in range(min(len(lam_params), len(call.args) - 1))
                    }
                    out: set[str] = set()
                    for sub in iter_direct_nodes(cb):
                        if isinstance(sub, ast.Call):
                            raw = _cleaned_whole_targets(
                                sub,
                                os_aliases=os_aliases,
                                os_direct_fns=os_direct_fns,
                                shutil_aliases=shutil_aliases,
                                atexit_aliases=atexit_aliases,
                                helper_cleaners=helper_cleaners,
                                ntf_vars=ntf_vars,
                                tuple_vars=tuple_vars,
                            )
                            for v in raw:
                                out |= bound_map.get(v, {v} if v not in lam_params else set())
                    return out
                return set()
        if fn.attr in {"unlink", "cleanup"} and not isinstance(recv, ast.Constant):
            return _whole_path_vars(recv, **kw_opts)
        if fn.attr in {"replace", "rename"} and len(call.args) == 1 and not call.keywords and not isinstance(recv, ast.Constant):
            return _whole_path_vars(recv, **kw_opts)
    return set()


def _extract_binding_vars(target: ast.AST, kind: str) -> tuple[set[str], bool]:
    if isinstance(target, ast.Name):
        return (set(), False) if target.id == "_" else ({target.id}, kind == "mkstemp")
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

    node_seq: dict[int, int] = {}
    for idx, n in enumerate(ast.walk(tree), start=1):
        node_seq[id(n)] = idx

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
        elif isinstance(node, ast.Lambda):
            scopes.append((f"lambda at line {node.lineno}", node))

    for scope_label, scope_node in scopes:
        direct = iter_direct_nodes(scope_node)
        order_seq = {id(n): i for i, n in enumerate(direct, start=1)}
        ntf_vars: set[str] = set()
        tuple_vars: set[str] = set()
        # (kind, lineno, seq_idx, bound_vars, call_id, has_self_dir, inline_ret_node)
        allocs: list[tuple[str, int, int, set[str], int, bool, ast.AST | None]] = []
        for sub in direct:
            if isinstance(sub, ast.Call):
                kind, has_self_dir = _manual_temp_kind(sub, mkstemp_n, mkdtemp_n, ntf_n)
                if kind is None:
                    continue
                bound: set[str] = set()
                is_tup = False
                inline_ret: ast.AST | None = None
                assign_seq = order_seq[id(sub)]
                cur: ast.AST | None = sub
                while cur is not None and cur is not scope_node:
                    par = parent_map.get(id(cur))
                    if isinstance(par, ast.Assign) and any(cur is s for s in ast.walk(par.value)):
                        for tgt in par.targets:
                            v, t = _extract_binding_vars(tgt, kind)
                            bound |= v
                            is_tup = is_tup or t
                        assign_seq = order_seq.get(id(par), assign_seq)
                        break
                    if isinstance(par, ast.AnnAssign) and par.value is not None:
                        bound, is_tup = _extract_binding_vars(par.target, kind)
                        assign_seq = order_seq.get(id(par), assign_seq)
                        break
                    if isinstance(par, ast.NamedExpr) and any(cur is s for s in ast.walk(par.value)):
                        bound, is_tup = _extract_binding_vars(par.target, kind)
                        assign_seq = order_seq.get(id(par), assign_seq)
                        break
                    if isinstance(par, ast.withitem) and par.optional_vars is not None:
                        bound, is_tup = _extract_binding_vars(par.optional_vars, kind)
                        assign_seq = order_seq.get(id(par), assign_seq)
                        break
                    if isinstance(par, (ast.Return, ast.Yield)):
                        inline_ret = par
                        break
                    cur = par
                if kind == "NamedTemporaryFile(delete=False)":
                    ntf_vars |= bound
                if is_tup:
                    tuple_vars |= bound
                # Use max(assign_seq, call_seq) so earlier sibling expressions on the same RHS
                # (e.g. `d = rmtree(d) or mkdtemp()`) cannot count as post-allocation cleanup.
                effective_alloc_seq = max(assign_seq, order_seq[id(sub)])
                allocs.append((kind, sub.lineno, effective_alloc_seq, bound, id(sub), has_self_dir, inline_ret))

        if not allocs:
            continue

        assign_events: list[tuple[int, set[str], set[str], int | None]] = []
        alloc_ids = {cid for _, _, _, _, cid, _, _ in allocs}
        for sub in direct:
            sq = order_seq[id(sub)]
            if isinstance(sub, ast.Assign):
                mcid = next((cid for cid in alloc_ids if any(id(s) == cid for s in ast.walk(sub.value))), None)
                lhs: set[str] = set()
                for tgt in sub.targets:
                    v, _ = _extract_binding_vars(tgt, "path")
                    lhs |= v
                rhs = _whole_path_vars(sub.value, os_aliases=os_a, ntf_vars=ntf_vars, tuple_vars=tuple_vars)
                if isinstance(sub.value, ast.Dict):
                    for val in sub.value.values:
                        rhs |= _whole_path_vars(val, os_aliases=os_a, ntf_vars=ntf_vars, tuple_vars=tuple_vars)
                if lhs:
                    assign_events.append((sq, lhs, rhs, mcid))
            elif isinstance(sub, (ast.AnnAssign, ast.NamedExpr)) and getattr(sub, "value", None) is not None:
                mcid = next((cid for cid in alloc_ids if any(id(s) == cid for s in ast.walk(sub.value))), None)
                lhs, _ = _extract_binding_vars(sub.target, "path")
                rhs = _whole_path_vars(sub.value, os_aliases=os_a, ntf_vars=ntf_vars, tuple_vars=tuple_vars)
                if lhs:
                    assign_events.append((sq, lhs, rhs, mcid))

        nested_defs = {
            n.name: n
            for n in ast.iter_child_nodes(scope_node)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        invoked_nested: list[tuple[str, int]] = []
        for sub in direct:
            if isinstance(sub, ast.Call):
                if isinstance(sub.func, ast.Name) and sub.func.id in nested_defs:
                    invoked_nested.append((sub.func.id, order_seq[id(sub)]))
                elif (
                    isinstance(sub.func, ast.Attribute)
                    and isinstance(sub.func.value, ast.Name)
                    and sub.func.value.id in atexit_a
                    and sub.func.attr == "register"
                    and len(sub.args) == 1
                    and isinstance(sub.args[0], ast.Name)
                    and sub.args[0].id in nested_defs
                ):
                    invoked_nested.append((sub.args[0].id, 10**9))

        cleanup_events: list[tuple[int, set[str]]] = [(10**9, {a}) for a in _enclosing_class_attrs(scope_node)]
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
                    cleanup_events.append((order_seq[id(sub)], cv))
        for hname, call_sq in invoked_nested:
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
                        cleanup_events.append((call_sq, cv))

        return_events: list[tuple[int, set[str]]] = []
        if isinstance(scope_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in direct:
                if isinstance(sub, (ast.Return, ast.Yield)) and sub.value is not None:
                    rv, _ = _expr_transfers_target(
                        sub.value,
                        os_aliases=os_a,
                        module_classes=module_classes,
                        ntf_vars=ntf_vars,
                        tuple_vars=tuple_vars,
                    )
                    if rv:
                        return_events.append((order_seq[id(sub)], rv))

        for kind, alloc_ln, alloc_sq, initial_bound, alloc_cid, has_self_dir, inline_ret in allocs:
            if inline_ret is not None:
                _, ok_inline = _expr_transfers_target(
                    getattr(inline_ret, "value", None),
                    os_aliases=os_a,
                    module_classes=module_classes,
                    ntf_vars=ntf_vars,
                    tuple_vars=tuple_vars,
                    target_call_id=alloc_cid,
                )
                if ok_inline and module_has_fs_cleanup:
                    continue
                errors.append(
                    f"{scope_label} allocates inline {kind} (line {alloc_ln}) without transferring path ownership"
                )
                continue
            if not initial_bound:
                errors.append(
                    f"{scope_label} allocates {kind} (line {alloc_ln}) without binding or cleaning up the path"
                )
                continue

            var_windows: dict[str, tuple[int, int]] = {}
            for v in initial_bound:
                overwrites = [
                    sq
                    for sq, lhs, rhs, cid in assign_events
                    if v in lhs and cid != alloc_cid and sq > alloc_sq and v not in rhs
                ]
                var_windows[v] = (alloc_sq, min(overwrites) if overwrites else 10**9 + 1)

            for _ in range(3):
                for sq, lhs, rhs, cid in sorted(assign_events, key=lambda x: x[0]):
                    if cid == alloc_cid:
                        continue
                    if any(r in var_windows and var_windows[r][0] <= sq < var_windows[r][1] for r in rhs):
                        for v in lhs:
                            overwrites = [
                                osq
                                for osq, olhs, orhs, _ in assign_events
                                if v in olhs and osq > sq and v not in orhs
                            ]
                            var_windows[v] = (sq, min(overwrites) if overwrites else 10**9 + 1)

            cleaned = any(
                v in var_windows and var_windows[v][0] <= csq < var_windows[v][1]
                for csq, cvars in cleanup_events
                for v in cvars
            )
            transferred = (module_has_fs_cleanup or has_self_dir) and any(
                v in var_windows and var_windows[v][0] <= rsq < var_windows[v][1]
                for rsq, rvars in return_events
                for v in rvars
            )
            if not (cleaned or transferred):
                errors.append(
                    f"{scope_label} allocates {kind} (line {alloc_ln}) without cleanup "
                    "(`unlink`/`os.replace`/`rmtree`/`atexit.register`) or ownership transfer"
                )
    return errors

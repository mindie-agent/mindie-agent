#!/usr/bin/env python3
"""Scope-aware Windows PID safety AST analyzer for storage modules (Guardrail P8).

[Role]
Verifies via Python stdlib `ast` that storage lifecycle/lease/GC modules never invoke
`os.kill(pid, 0)` (or imported `kill(pid, 0)`) unless guarded by a direct literal POSIX branch.

[Invariants]
- Uses scope-hereditary monotonic `may` taint (`may_os`, `may_kill`, never cleared by rebindings,
  loops, comprehensions, or exception handlers) to detect every `os.kill(pid, 0)` / `kill(pid, 0)`.
- Trusts an identifier in `_guard_implications` (`must_os`, `must_sys`) ONLY when bound by a
  direct top-of-scope `import os` / `import sys` prior to use and never rebound or shadowed by any
  parameter, assignment, walrus `:=`, loop, comprehension target, `match` pattern, handler, or
  nested import anywhere in the scope chain (propagated into nested lambdas/functions/classes).
- Evaluates two-valued `(true_implies_posix, false_implies_posix)` De Morgan implications.

[Timeouts & Locks]
- Pure in-memory AST traversal; acquires no locks and spawns no subprocesses.

[Side-Effect Policy]
- Strictly read-only inspection of Python source files.
"""

from __future__ import annotations

import ast
from pathlib import Path

from storage_temp_ast import iter_direct_nodes, non_import_bound_names, pattern_bound_names

_COMPREHENSION_TYPES = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _stmts_always_exit(stmts: list[ast.stmt]) -> bool:
    for stmt in stmts:
        if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
            return True
        if isinstance(stmt, ast.If) and stmt.orelse:
            if _stmts_always_exit(stmt.body) and _stmts_always_exit(stmt.orelse):
                return True
    return False


def _guard_implications(expr: ast.AST, os_aliases: frozenset[str], sys_aliases: frozenset[str]) -> tuple[bool, bool]:
    """Return `(true_implies_posix, false_implies_posix)` for literal platform guard `expr`."""
    if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.Not):
        t_pos, f_pos = _guard_implications(expr.operand, os_aliases, sys_aliases)
        return f_pos, t_pos
    if isinstance(expr, ast.BoolOp):
        parts = [_guard_implications(v, os_aliases, sys_aliases) for v in expr.values]
        if isinstance(expr.op, ast.And):
            return any(t for t, _ in parts), all(f for _, f in parts)
        if isinstance(expr.op, ast.Or):
            return all(t for t, _ in parts), any(f for _, f in parts)
        return False, False
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
            and isinstance(expr.args[0].value, str)
            and expr.args[0].value in {"win", "win32"}
        ):
            return False, True
    if isinstance(expr, ast.Compare) and len(expr.ops) == 1 and len(expr.comparators) == 1:
        left, op, right = expr.left, expr.ops[0], expr.comparators[0]
        if not (isinstance(left, ast.Attribute) and isinstance(left.value, ast.Name) and isinstance(right, ast.Constant)):
            return False, False
        if left.value.id in os_aliases and left.attr == "name":
            if right.value == "nt":
                if isinstance(op, (ast.Eq, ast.Is)):
                    return False, True
                if isinstance(op, (ast.NotEq, ast.IsNot)):
                    return True, False
            elif right.value == "posix" and isinstance(op, (ast.Eq, ast.Is)):
                return True, False
        if left.value.id in sys_aliases and left.attr == "platform" and right.value == "win32":
            if isinstance(op, (ast.Eq, ast.Is)):
                return False, True
            if isinstance(op, (ast.NotEq, ast.IsNot)):
                return True, False
    return False, False


def _is_int_zero(expr: ast.AST | None) -> bool:
    if expr is None:
        return False
    if isinstance(expr, ast.Constant):
        return type(expr.value) is int and expr.value == 0
    if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, (ast.UAdd, ast.USub)):
        return _is_int_zero(expr.operand)
    return False


def _is_dynamic_os_expr(expr: ast.AST) -> bool:
    if not isinstance(expr, ast.Call) or not expr.args:
        return False
    arg0 = expr.args[0]
    if not (isinstance(arg0, ast.Constant) and arg0.value == "os"):
        return False
    fn = expr.func
    return (isinstance(fn, ast.Name) and fn.id in {"__import__", "import_module"}) or (
        isinstance(fn, ast.Attribute) and fn.attr == "import_module"
    )


def _target_names(node: ast.AST) -> set[str]:
    return {sub.id for sub in ast.walk(node) if isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del))}


def _scope_may_taint(scope: ast.AST, inherited_os: frozenset[str], inherited_kill: frozenset[str]) -> tuple[frozenset[str], frozenset[str]]:
    """Collect monotonic `may_os` and `may_kill` aliases across `scope` (never cleared)."""
    may_os = set(inherited_os)
    may_kill = set(inherited_kill)
    direct = iter_direct_nodes(scope)
    for node in direct:
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".", 1)[0]
                if alias.name == "os" or (alias.asname is None and alias.name.startswith("os.")):
                    may_os.add(bound)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*" and node.module == "os":
                    may_kill.add("kill")
                elif node.module == "os" and alias.name == "kill":
                    may_kill.add(alias.asname or alias.name)
    for _ in range(3):
        for node in direct:
            rhs: ast.AST | None = None
            targets: set[str] = set()
            if isinstance(node, ast.Assign):
                rhs = node.value
                for t in node.targets:
                    targets |= _target_names(t)
            elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)) and node.value is not None:
                rhs = node.value
                targets = _target_names(node.target)
            if rhs is not None and targets:
                if isinstance(rhs, ast.Name) and rhs.id in may_os:
                    may_os |= targets
                elif _is_dynamic_os_expr(rhs):
                    may_os |= targets
                elif isinstance(rhs, ast.Name) and rhs.id in may_kill:
                    may_kill |= targets
                elif isinstance(rhs, ast.Attribute) and rhs.attr == "kill" and isinstance(rhs.value, ast.Name) and rhs.value.id in may_os:
                    may_kill |= targets
    return frozenset(may_os), frozenset(may_kill)


def _scope_shadowed_for_must(scope: ast.AST) -> set[str]:
    """Return every name bound by non-top-import constructs in `scope` (invalidates `must` guards)."""
    bad = non_import_bound_names(scope)
    raw_body = getattr(scope, "body", ())
    top_stmts = {id(s) for s in raw_body if isinstance(s, ast.stmt)} if isinstance(raw_body, list) else set()
    import_counts: dict[str, int] = {}
    has_star_import = False
    for node in iter_direct_nodes(scope):
        if isinstance(node, ast.Import):
            in_top = id(node) in top_stmts
            for alias in node.names:
                bound = alias.asname or alias.name.split(".", 1)[0]
                import_counts[bound] = import_counts.get(bound, 0) + 1
                is_std = alias.name in {"os", "sys"} or (alias.asname is None and alias.name.startswith("os."))
                if not in_top or not is_std or import_counts[bound] > 1:
                    bad.add(bound)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    has_star_import = True
                else:
                    bad.add(alias.asname or alias.name)
    if has_star_import:
        bad.update({"os", "sys"})
    return bad


def inspect_storage_module_windows_pid_safety(path: Path) -> list[str]:
    """Ban `os.kill(pid, 0)` (or imported `kill(pid, 0)`) unless guarded by literal POSIX branch."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    errors: list[str] = []

    def _visit_expr(
        node: ast.AST,
        posix_proven: bool,
        scope_name: str,
        must_os: frozenset[str],
        must_sys: frozenset[str],
        may_os: frozenset[str],
        may_kill: frozenset[str],
    ) -> None:
        if isinstance(node, ast.Lambda):
            for dflt in (*node.args.defaults, *(d for d in node.args.kw_defaults if d is not None)):
                _visit_expr(dflt, posix_proven, scope_name, must_os, must_sys, may_os, may_kill)
            bad = _scope_shadowed_for_must(node)
            l_may_os, l_may_kill = _scope_may_taint(node, may_os, may_kill)
            _visit_expr(node.body, posix_proven, scope_name, must_os - bad, must_sys - bad, l_may_os, l_may_kill)
            return
        if isinstance(node, _COMPREHENSION_TYPES):
            c_must_os, c_must_sys = must_os, must_sys
            for idx, gen in enumerate(node.generators):
                i_os = must_os if idx == 0 else c_must_os
                i_sys = must_sys if idx == 0 else c_must_sys
                _visit_expr(gen.iter, posix_proven, scope_name, i_os, i_sys, may_os, may_kill)
                drop = _target_names(gen.target)
                c_must_os, c_must_sys = c_must_os - drop, c_must_sys - drop
                for cond in gen.ifs:
                    _visit_expr(cond, posix_proven, scope_name, c_must_os, c_must_sys, may_os, may_kill)
                    t_pos, _ = _guard_implications(cond, c_must_os, c_must_sys)
                    posix_proven = posix_proven or t_pos
            if isinstance(node, ast.DictComp):
                _visit_expr(node.key, posix_proven, scope_name, c_must_os, c_must_sys, may_os, may_kill)
                _visit_expr(node.value, posix_proven, scope_name, c_must_os, c_must_sys, may_os, may_kill)
            else:
                _visit_expr(node.elt, posix_proven, scope_name, c_must_os, c_must_sys, may_os, may_kill)
            return
        if isinstance(node, ast.IfExp):
            _visit_expr(node.test, posix_proven, scope_name, must_os, must_sys, may_os, may_kill)
            t_pos, f_pos = _guard_implications(node.test, must_os, must_sys)
            _visit_expr(node.body, posix_proven or t_pos, scope_name, must_os, must_sys, may_os, may_kill)
            _visit_expr(node.orelse, posix_proven or f_pos, scope_name, must_os, must_sys, may_os, may_kill)
            return
        if isinstance(node, ast.Call):
            fn = node.func
            sig_expr: ast.AST | None = node.args[1] if len(node.args) >= 2 else None
            if sig_expr is None:
                for kw in node.keywords:
                    if kw.arg == "sig":
                        sig_expr = kw.value
                        break
            is_os_kill_fn = (
                (
                    isinstance(fn, ast.Attribute)
                    and fn.attr == "kill"
                    and ((isinstance(fn.value, ast.Name) and fn.value.id in may_os) or _is_dynamic_os_expr(fn.value))
                )
                or (isinstance(fn, ast.Name) and fn.id in may_kill)
            )
            if is_os_kill_fn and _is_int_zero(sig_expr) and not posix_proven:
                errors.append(
                    f"line {node.lineno} `{scope_name}` calls unguarded `os.kill(pid, 0)` "
                    "(terminates or misprobes processes on Windows; guard with `os.name != 'nt'` or use Win32 `OpenProcess`)"
                )
        for child in ast.iter_child_nodes(node):
            _visit_expr(child, posix_proven, scope_name, must_os, must_sys, may_os, may_kill)

    def _visit_scope(
        scope: ast.AST,
        stmts: list[ast.stmt],
        posix_proven: bool,
        scope_name: str,
        inh_must_os: frozenset[str],
        inh_must_sys: frozenset[str],
        inh_may_os: frozenset[str],
        inh_may_kill: frozenset[str],
        *,
        is_class_body: bool = False,
    ) -> None:
        bad = _scope_shadowed_for_must(scope)
        may_os, may_kill = _scope_may_taint(scope, inh_may_os, inh_may_kill)
        cur_must_os = inh_must_os - bad
        cur_must_sys = inh_must_sys - bad

        def _walk_block(
            block: list[ast.stmt],
            blk_posix: bool,
            m_os: frozenset[str],
            m_sys: frozenset[str],
            *,
            top_block: bool,
        ) -> None:
            cur_pos = blk_posix
            cur_o, cur_s = set(m_os), set(m_sys)
            for stmt in block:
                fo, fs = frozenset(cur_o), frozenset(cur_s)
                enc_mo = inh_must_os if is_class_body else fo
                enc_ms = inh_must_sys if is_class_body else fs
                enc_may_o = inh_may_os if is_class_body else may_os
                enc_may_k = inh_may_kill if is_class_body else may_kill

                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for dec in stmt.decorator_list:
                        _visit_expr(dec, cur_pos, scope_name, fo, fs, may_os, may_kill)
                    for tp in getattr(stmt, "type_params", ()):
                        _visit_expr(tp, cur_pos, scope_name, fo, fs, may_os, may_kill)
                    for arg in (*stmt.args.posonlyargs, *stmt.args.args, *stmt.args.kwonlyargs, stmt.args.vararg, stmt.args.kwarg):
                        if arg is not None and arg.annotation is not None:
                            _visit_expr(arg.annotation, cur_pos, scope_name, fo, fs, may_os, may_kill)
                    if stmt.returns is not None:
                        _visit_expr(stmt.returns, cur_pos, scope_name, fo, fs, may_os, may_kill)
                    for dflt in (*stmt.args.defaults, *(d for d in stmt.args.kw_defaults if d is not None)):
                        _visit_expr(dflt, cur_pos, scope_name, fo, fs, may_os, may_kill)
                    _visit_scope(stmt, stmt.body, cur_pos, stmt.name, enc_mo, enc_ms, enc_may_o, enc_may_k)
                elif isinstance(stmt, ast.ClassDef):
                    for dec in stmt.decorator_list:
                        _visit_expr(dec, cur_pos, scope_name, fo, fs, may_os, may_kill)
                    for tp in getattr(stmt, "type_params", ()):
                        _visit_expr(tp, cur_pos, scope_name, fo, fs, may_os, may_kill)
                    for b in stmt.bases:
                        _visit_expr(b, cur_pos, scope_name, fo, fs, may_os, may_kill)
                    for kw in stmt.keywords:
                        _visit_expr(kw.value, cur_pos, scope_name, fo, fs, may_os, may_kill)
                    _visit_scope(stmt, stmt.body, cur_pos, stmt.name, enc_mo, enc_ms, enc_may_o, enc_may_k, is_class_body=True)
                elif isinstance(stmt, ast.If):
                    _visit_expr(stmt.test, cur_pos, scope_name, fo, fs, may_os, may_kill)
                    t_pos, f_pos = _guard_implications(stmt.test, fo, fs)
                    _walk_block(stmt.body, cur_pos or t_pos, fo, fs, top_block=False)
                    _walk_block(stmt.orelse, cur_pos or f_pos, fo, fs, top_block=False)
                    if not stmt.orelse and f_pos and _stmts_always_exit(stmt.body):
                        cur_pos = True
                elif isinstance(stmt, ast.Match):
                    _visit_expr(stmt.subject, cur_pos, scope_name, fo, fs, may_os, may_kill)
                    for mc in stmt.cases:
                        pat_names = pattern_bound_names(mc.pattern)
                        co, cs = fo - pat_names, fs - pat_names
                        c_pos = cur_pos
                        if mc.guard is not None:
                            _visit_expr(mc.guard, cur_pos, scope_name, co, cs, may_os, may_kill)
                            t_pos, _ = _guard_implications(mc.guard, co, cs)
                            c_pos = c_pos or t_pos
                        _walk_block(mc.body, c_pos, co, cs, top_block=False)
                else:
                    for _, val in ast.iter_fields(stmt):
                        if isinstance(val, list):
                            if val and all(isinstance(it, ast.stmt) for it in val):
                                _walk_block(val, cur_pos, fo, fs, top_block=False)
                            else:
                                for it in val:
                                    if isinstance(it, ast.AST):
                                        _visit_expr(it, cur_pos, scope_name, fo, fs, may_os, may_kill)
                        elif isinstance(val, ast.AST):
                            _visit_expr(val, cur_pos, scope_name, fo, fs, may_os, may_kill)

                if top_block and isinstance(stmt, ast.Import):
                    for alias in stmt.names:
                        bound = alias.asname or alias.name.split(".", 1)[0]
                        if bound in bad:
                            continue
                        if alias.name == "os" or (alias.asname is None and alias.name.startswith("os.")):
                            cur_o.add(bound)
                        elif alias.name == "sys":
                            cur_s.add(bound)

        _walk_block(stmts, posix_proven, cur_must_os, cur_must_sys, top_block=True)

    _visit_scope(tree, tree.body, False, "<module>", frozenset(), frozenset(), frozenset(), frozenset())
    return errors

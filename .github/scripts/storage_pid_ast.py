#!/usr/bin/env python3
"""Scope-aware Windows PID safety AST analyzer for storage modules (Guardrail P8).

[Role]
Verifies via Python stdlib `ast` that storage lifecycle/lease/GC modules never invoke
`os.kill(pid, 0)` (or imported `kill(pid, 0)`) unless guarded by a direct literal POSIX branch.

[Invariants]
- Inspects decorators, type parameters, parameter annotations/defaults, class bases/keywords,
  lambda bodies, `If.test` conditions, `IfExp` ternaries, and `match`/`case` guards/bodies.
- Evaluates exact two-valued `(true_implies_posix, false_implies_posix)` De Morgan boolean
  implications so compound guards like `if not (os.name != 'nt' and flag): return` or
  `if os.name == 'nt' and flag: return` never falsely prove POSIX reachability on Windows.
- Tracks `import os`, `import os.path`, `import sys`, `from os import kill` / `*`, `sig=0`
  keyword calls, `__import__('os')`, local reassignments, and `match` pattern captures.

[Timeouts & Locks]
- Pure in-memory AST traversal; acquires no locks and spawns no subprocesses.

[Side-Effect Policy]
- Strictly read-only inspection of Python source files.
"""

from __future__ import annotations

import ast
from pathlib import Path

from storage_temp_ast import non_import_bound_names, pattern_bound_names


def _guard_implications(expr: ast.AST, os_aliases: set[str], sys_aliases: set[str]) -> tuple[bool, bool]:
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


def inspect_storage_module_windows_pid_safety(path: Path) -> list[str]:
    """Ban `os.kill(pid, 0)` (or imported `kill(pid, 0)`) unless guarded by literal POSIX branch."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    errors: list[str] = []

    def _discard_targets(node: ast.AST, os_a: set[str], sys_a: set[str], kill_n: set[str]) -> None:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del)):
                os_a.discard(sub.id)
                sys_a.discard(sub.id)
                kill_n.discard(sub.id)

    def _apply_stmt_bindings(stmt: ast.AST, os_a: set[str], sys_a: set[str], kill_n: set[str]) -> None:
        if isinstance(stmt, ast.Import):
            for alias in stmt.names:
                bound = alias.asname or alias.name.split(".", 1)[0]
                os_a.discard(bound)
                sys_a.discard(bound)
                kill_n.discard(bound)
                if alias.name == "os" or (alias.asname is None and alias.name.startswith("os.")):
                    os_a.add(bound)
                elif alias.name == "sys":
                    sys_a.add(bound)
        elif isinstance(stmt, ast.ImportFrom):
            for alias in stmt.names:
                if alias.name == "*":
                    if stmt.module == "os":
                        kill_n.add("kill")
                    continue
                bound = alias.asname or alias.name
                os_a.discard(bound)
                sys_a.discard(bound)
                kill_n.discard(bound)
                if stmt.module == "os" and alias.name == "kill":
                    kill_n.add(bound)
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for s in (os_a, sys_a, kill_n):
                s.discard(stmt.name)
        elif isinstance(stmt, ast.Assign):
            for tgt in stmt.targets:
                _discard_targets(tgt, os_a, sys_a, kill_n)
        elif isinstance(stmt, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr, ast.For, ast.AsyncFor)):
            _discard_targets(stmt.target, os_a, sys_a, kill_n)
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            for item in stmt.items:
                if item.optional_vars is not None:
                    _discard_targets(item.optional_vars, os_a, sys_a, kill_n)
        elif isinstance(stmt, ast.Delete):
            for tgt in stmt.targets:
                _discard_targets(tgt, os_a, sys_a, kill_n)

    def _visit(
        node: ast.AST,
        posix_proven: bool,
        scope_name: str,
        os_a: set[str],
        sys_a: set[str],
        kill_n: set[str],
        *,
        enclosing_os: set[str],
        enclosing_sys: set[str],
        enclosing_kill: set[str],
    ) -> None:
        enc_kw = dict(enclosing_os=enclosing_os, enclosing_sys=enclosing_sys, enclosing_kill=enclosing_kill)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                _visit(dec, posix_proven, scope_name, os_a, sys_a, kill_n, **enc_kw)
            for tp in getattr(node, "type_params", ()):
                _visit(tp, posix_proven, scope_name, os_a, sys_a, kill_n, **enc_kw)
            for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs, node.args.vararg, node.args.kwarg):
                if arg is not None and arg.annotation is not None:
                    _visit(arg.annotation, posix_proven, scope_name, os_a, sys_a, kill_n, **enc_kw)
            if node.returns is not None:
                _visit(node.returns, posix_proven, scope_name, os_a, sys_a, kill_n, **enc_kw)
            for dflt in (*node.args.defaults, *(d for d in node.args.kw_defaults if d is not None)):
                _visit(dflt, posix_proven, scope_name, os_a, sys_a, kill_n, **enc_kw)
            shadowed = non_import_bound_names(node)
            f_os, f_sys, f_kill = set(enclosing_os) - shadowed, set(enclosing_sys) - shadowed, set(enclosing_kill) - shadowed
            _visit_stmts(node.body, posix_proven, node.name, f_os, f_sys, f_kill, is_class_body=False)
            return
        if isinstance(node, ast.ClassDef):
            for dec in node.decorator_list:
                _visit(dec, posix_proven, scope_name, os_a, sys_a, kill_n, **enc_kw)
            for tp in getattr(node, "type_params", ()):
                _visit(tp, posix_proven, scope_name, os_a, sys_a, kill_n, **enc_kw)
            for b in node.bases:
                _visit(b, posix_proven, scope_name, os_a, sys_a, kill_n, **enc_kw)
            for kw in node.keywords:
                _visit(kw.value, posix_proven, scope_name, os_a, sys_a, kill_n, **enc_kw)
            shadowed = non_import_bound_names(node)
            c_os, c_sys, c_kill = set(enclosing_os) - shadowed, set(enclosing_sys) - shadowed, set(enclosing_kill) - shadowed
            _visit_stmts(
                node.body, posix_proven, node.name, c_os, c_sys, c_kill,
                is_class_body=True, lex_os=enclosing_os, lex_sys=enclosing_sys, lex_kill=enclosing_kill,
            )
            return
        if isinstance(node, ast.Lambda):
            for dflt in (*node.args.defaults, *(d for d in node.args.kw_defaults if d is not None)):
                _visit(dflt, posix_proven, scope_name, os_a, sys_a, kill_n, **enc_kw)
            shadowed = non_import_bound_names(node)
            l_os, l_sys, l_kill = set(enclosing_os) - shadowed, set(enclosing_sys) - shadowed, set(enclosing_kill) - shadowed
            _visit(
                node.body, posix_proven, scope_name, l_os, l_sys, l_kill,
                enclosing_os=l_os, enclosing_sys=l_sys, enclosing_kill=l_kill,
            )
            return
        if isinstance(node, ast.If):
            _visit(node.test, posix_proven, scope_name, os_a, sys_a, kill_n, **enc_kw)
            t_pos, f_pos = _guard_implications(node.test, os_a, sys_a)
            _visit_stmts(
                node.body, posix_proven or t_pos, scope_name, set(os_a), set(sys_a), set(kill_n),
                is_class_body=False, lex_os=enclosing_os, lex_sys=enclosing_sys, lex_kill=enclosing_kill,
            )
            _visit_stmts(
                node.orelse, posix_proven or f_pos, scope_name, set(os_a), set(sys_a), set(kill_n),
                is_class_body=False, lex_os=enclosing_os, lex_sys=enclosing_sys, lex_kill=enclosing_kill,
            )
            return
        if isinstance(node, ast.IfExp):
            _visit(node.test, posix_proven, scope_name, os_a, sys_a, kill_n, **enc_kw)
            t_pos, f_pos = _guard_implications(node.test, os_a, sys_a)
            _visit(node.body, posix_proven or t_pos, scope_name, os_a, sys_a, kill_n, **enc_kw)
            _visit(node.orelse, posix_proven or f_pos, scope_name, os_a, sys_a, kill_n, **enc_kw)
            return
        if isinstance(node, ast.Match):
            _visit(node.subject, posix_proven, scope_name, os_a, sys_a, kill_n, **enc_kw)
            for mc in node.cases:
                bound_pat = pattern_bound_names(mc.pattern)
                c_os, c_sys, c_kill = set(os_a) - bound_pat, set(sys_a) - bound_pat, set(kill_n) - bound_pat
                if mc.guard is not None:
                    _visit(mc.guard, posix_proven, scope_name, c_os, c_sys, c_kill, **enc_kw)
                _visit_stmts(
                    mc.body, posix_proven, scope_name, c_os, c_sys, c_kill,
                    is_class_body=False, lex_os=enclosing_os, lex_sys=enclosing_sys, lex_kill=enclosing_kill,
                )
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
                    and ((isinstance(fn.value, ast.Name) and fn.value.id in os_a) or _is_dynamic_os_expr(fn.value))
                )
                or (isinstance(fn, ast.Name) and fn.id in kill_n)
            )
            if is_os_kill_fn and _is_int_zero(sig_expr) and not posix_proven:
                errors.append(
                    f"line {node.lineno} `{scope_name}` calls unguarded `os.kill(pid, 0)` "
                    "(terminates or misprobes processes on Windows; guard with `os.name != 'nt'` or use Win32 `OpenProcess`)"
                )
        for _, value in ast.iter_fields(node):
            if isinstance(value, list):
                if value and all(isinstance(item, ast.stmt) for item in value):
                    _visit_stmts(
                        value, posix_proven, scope_name, set(os_a), set(sys_a), set(kill_n),
                        is_class_body=False, lex_os=enclosing_os, lex_sys=enclosing_sys, lex_kill=enclosing_kill,
                    )
                else:
                    for item in value:
                        if isinstance(item, ast.AST):
                            _visit(item, posix_proven, scope_name, os_a, sys_a, kill_n, **enc_kw)
            elif isinstance(value, ast.AST):
                _visit(value, posix_proven, scope_name, os_a, sys_a, kill_n, **enc_kw)

    def _visit_stmts(
        stmts: list[ast.stmt],
        posix_proven: bool,
        scope_name: str,
        os_a: set[str],
        sys_a: set[str],
        kill_n: set[str],
        *,
        is_class_body: bool,
        lex_os: set[str] | None = None,
        lex_sys: set[str] | None = None,
        lex_kill: set[str] | None = None,
    ) -> None:
        cur_posix = posix_proven
        for stmt in stmts:
            enc_os = lex_os if is_class_body and lex_os is not None else os_a
            enc_sys = lex_sys if is_class_body and lex_sys is not None else sys_a
            enc_kill = lex_kill if is_class_body and lex_kill is not None else kill_n
            _visit(
                stmt, cur_posix, scope_name, os_a, sys_a, kill_n,
                enclosing_os=enc_os, enclosing_sys=enc_sys, enclosing_kill=enc_kill,
            )
            _apply_stmt_bindings(stmt, os_a, sys_a, kill_n)
            if isinstance(stmt, ast.If) and not stmt.orelse:
                _, f_pos = _guard_implications(stmt.test, os_a, sys_a)
                if f_pos and stmt.body and isinstance(stmt.body[-1], (ast.Return, ast.Raise, ast.Continue, ast.Break)):
                    cur_posix = True

    _visit_stmts(tree.body, False, "<module>", set(), set(), set(), is_class_body=False)
    return errors

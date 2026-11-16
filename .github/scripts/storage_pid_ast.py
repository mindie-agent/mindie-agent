#!/usr/bin/env python3
"""Scope-aware Windows PID safety AST analyzer for storage modules (Guardrail P8).

[Role]
Verifies via Python stdlib `ast` that storage lifecycle/lease/GC modules never invoke
`os.kill(pid, 0)` (or imported `kill(pid, 0)`) unless guarded by a direct literal POSIX branch.

[Invariants]
- Separates `must` platform aliases (intersection across non-exiting control-flow branches, used
  only to prove literal POSIX guards) from `may` kill aliases (union across reachable branches,
  used to flag `os.kill(pid, 0)`), propagating imports out of `try`/`if`/`with`/`for`/`match`.
- Establishes dedicated lexical scopes for comprehensions (`ListComp`, `SetComp`, `DictComp`,
  `GeneratorExp`), lambdas, functions, and classes so comprehension targets (e.g. `for sys in xs`)
  or `NamedExpr` (`:=`) bindings never spoof `os`/`sys` guards.
- Evaluates two-valued `(true_implies_posix, false_implies_posix)` De Morgan implications.

[Timeouts & Locks]
- Pure in-memory AST traversal; acquires no locks and spawns no subprocesses.

[Side-Effect Policy]
- Strictly read-only inspection of Python source files.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import NamedTuple

from storage_temp_ast import iter_direct_nodes, non_import_bound_names, pattern_bound_names


class _AliasState(NamedTuple):
    must_os: frozenset[str]
    must_sys: frozenset[str]
    may_os: frozenset[str]
    may_kill: frozenset[str]

    def drop(self, names: set[str] | frozenset[str]) -> _AliasState:
        if not names:
            return self
        return _AliasState(
            self.must_os - names,
            self.must_sys - names,
            self.may_os - names,
            self.may_kill - names,
        )


_EMPTY_STATE = _AliasState(frozenset(), frozenset(), frozenset(), frozenset())
_COMPREHENSION_TYPES = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _join_states(states: list[_AliasState], fallback: _AliasState) -> _AliasState:
    if not states:
        return fallback
    must_os = set(states[0].must_os)
    must_sys = set(states[0].must_sys)
    may_os: set[str] = set()
    may_kill: set[str] = set()
    for st in states:
        must_os &= st.must_os
        must_sys &= st.must_sys
        may_os |= st.may_os
        may_kill |= st.may_kill
    return _AliasState(frozenset(must_os), frozenset(must_sys), frozenset(may_os), frozenset(may_kill))


def _stmts_always_exit(stmts: list[ast.stmt]) -> bool:
    for stmt in stmts:
        if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
            return True
        if isinstance(stmt, ast.If) and stmt.orelse:
            if _stmts_always_exit(stmt.body) and _stmts_always_exit(stmt.orelse):
                return True
    return False


def _expr_named_stores(expr: ast.AST) -> set[str]:
    return {
        sub.target.id
        for sub in iter_direct_nodes(expr)
        if isinstance(sub, ast.NamedExpr) and isinstance(sub.target, ast.Name)
    } | ({expr.target.id} if isinstance(expr, ast.NamedExpr) and isinstance(expr.target, ast.Name) else set())


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


def _apply_simple_stmt(stmt: ast.AST, st: _AliasState) -> _AliasState:
    must_os, must_sys = set(st.must_os), set(st.must_sys)
    may_os, may_kill = set(st.may_os), set(st.may_kill)

    def _clear(bound: str) -> None:
        must_os.discard(bound)
        must_sys.discard(bound)
        may_os.discard(bound)
        may_kill.discard(bound)

    # Discard any inline walrus `:=` targets inside expressions in this statement.
    for sub in iter_direct_nodes(stmt):
        if isinstance(sub, ast.NamedExpr) and isinstance(sub.target, ast.Name):
            _clear(sub.target.id)

    if isinstance(stmt, ast.Import):
        for alias in stmt.names:
            bound = alias.asname or alias.name.split(".", 1)[0]
            _clear(bound)
            if alias.name == "os" or (alias.asname is None and alias.name.startswith("os.")):
                must_os.add(bound)
                may_os.add(bound)
            elif alias.name == "sys":
                must_sys.add(bound)
    elif isinstance(stmt, ast.ImportFrom):
        for alias in stmt.names:
            if alias.name == "*":
                if stmt.module == "os":
                    may_kill.add("kill")
                must_os.clear()
                must_sys.clear()
                continue
            bound = alias.asname or alias.name
            _clear(bound)
            if stmt.module == "os" and alias.name == "kill":
                may_kill.add(bound)
    elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        _clear(stmt.name)
    elif isinstance(stmt, ast.Assign):
        for tgt in stmt.targets:
            for name in _target_names(tgt):
                _clear(name)
    elif isinstance(stmt, (ast.AnnAssign, ast.AugAssign)):
        for name in _target_names(stmt.target):
            _clear(name)
    elif isinstance(stmt, ast.Delete):
        for tgt in stmt.targets:
            for name in _target_names(tgt):
                _clear(name)
    return _AliasState(frozenset(must_os), frozenset(must_sys), frozenset(may_os), frozenset(may_kill))


def inspect_storage_module_windows_pid_safety(path: Path) -> list[str]:
    """Ban `os.kill(pid, 0)` (or imported `kill(pid, 0)`) unless guarded by literal POSIX branch."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    errors: list[str] = []

    def _visit_expr(node: ast.AST, posix_proven: bool, scope_name: str, st: _AliasState, enc: _AliasState) -> None:
        if isinstance(node, ast.Lambda):
            for dflt in (*node.args.defaults, *(d for d in node.args.kw_defaults if d is not None)):
                _visit_expr(dflt, posix_proven, scope_name, st, enc)
            l_st = enc.drop(non_import_bound_names(node))
            _visit_expr(node.body, posix_proven, scope_name, l_st, l_st)
            return
        if isinstance(node, _COMPREHENSION_TYPES):
            comp_st = st
            for idx, gen in enumerate(node.generators):
                iter_st = st if idx == 0 else comp_st
                _visit_expr(gen.iter, posix_proven, scope_name, iter_st, enc)
                comp_st = comp_st.drop(_target_names(gen.target) | _expr_named_stores(gen.iter))
                for cond in gen.ifs:
                    cond_clean = comp_st.drop(_expr_named_stores(cond))
                    _visit_expr(cond, posix_proven, scope_name, comp_st, enc)
                    t_pos, _ = _guard_implications(cond, cond_clean.must_os, cond_clean.must_sys)
                    posix_proven = posix_proven or t_pos
                    comp_st = cond_clean
            if isinstance(node, ast.DictComp):
                _visit_expr(node.key, posix_proven, scope_name, comp_st, enc)
                _visit_expr(node.value, posix_proven, scope_name, comp_st.drop(_expr_named_stores(node.key)), enc)
            else:
                _visit_expr(node.elt, posix_proven, scope_name, comp_st, enc)
            return
        if isinstance(node, ast.IfExp):
            _visit_expr(node.test, posix_proven, scope_name, st, enc)
            post_test = st.drop(_expr_named_stores(node.test))
            t_pos, f_pos = _guard_implications(node.test, post_test.must_os, post_test.must_sys)
            _visit_expr(node.body, posix_proven or t_pos, scope_name, post_test, enc)
            _visit_expr(node.orelse, posix_proven or f_pos, scope_name, post_test, enc)
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
                    and ((isinstance(fn.value, ast.Name) and fn.value.id in st.may_os) or _is_dynamic_os_expr(fn.value))
                )
                or (isinstance(fn, ast.Name) and fn.id in st.may_kill)
            )
            if is_os_kill_fn and _is_int_zero(sig_expr) and not posix_proven:
                errors.append(
                    f"line {node.lineno} `{scope_name}` calls unguarded `os.kill(pid, 0)` "
                    "(terminates or misprobes processes on Windows; guard with `os.name != 'nt'` or use Win32 `OpenProcess`)"
                )
        for child in ast.iter_child_nodes(node):
            _visit_expr(child, posix_proven, scope_name, st, enc)

    def _visit_stmt(stmt: ast.stmt, posix_proven: bool, scope_name: str, st: _AliasState, enc: _AliasState) -> tuple[_AliasState, bool]:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in stmt.decorator_list:
                _visit_expr(dec, posix_proven, scope_name, st, enc)
            for tp in getattr(stmt, "type_params", ()):
                _visit_expr(tp, posix_proven, scope_name, st, enc)
            for arg in (*stmt.args.posonlyargs, *stmt.args.args, *stmt.args.kwonlyargs, stmt.args.vararg, stmt.args.kwarg):
                if arg is not None and arg.annotation is not None:
                    _visit_expr(arg.annotation, posix_proven, scope_name, st, enc)
            if stmt.returns is not None:
                _visit_expr(stmt.returns, posix_proven, scope_name, st, enc)
            for dflt in (*stmt.args.defaults, *(d for d in stmt.args.kw_defaults if d is not None)):
                _visit_expr(dflt, posix_proven, scope_name, st, enc)
            f_st = enc.drop(non_import_bound_names(stmt))
            _visit_stmts(stmt.body, posix_proven, stmt.name, f_st, is_class_body=False)
            return _apply_simple_stmt(stmt, st), posix_proven
        if isinstance(stmt, ast.ClassDef):
            for dec in stmt.decorator_list:
                _visit_expr(dec, posix_proven, scope_name, st, enc)
            for tp in getattr(stmt, "type_params", ()):
                _visit_expr(tp, posix_proven, scope_name, st, enc)
            for b in stmt.bases:
                _visit_expr(b, posix_proven, scope_name, st, enc)
            for kw in stmt.keywords:
                _visit_expr(kw.value, posix_proven, scope_name, st, enc)
            c_st = enc.drop(non_import_bound_names(stmt))
            _visit_stmts(stmt.body, posix_proven, stmt.name, c_st, is_class_body=True, lex_enc=enc)
            return _apply_simple_stmt(stmt, st), posix_proven
        if isinstance(stmt, ast.If):
            _visit_expr(stmt.test, posix_proven, scope_name, st, enc)
            post_test = st.drop(_expr_named_stores(stmt.test))
            t_pos, f_pos = _guard_implications(stmt.test, post_test.must_os, post_test.must_sys)
            b_st = _visit_stmts(stmt.body, posix_proven or t_pos, scope_name, post_test, is_class_body=False, lex_enc=enc)
            e_st = _visit_stmts(stmt.orelse, posix_proven or f_pos, scope_name, post_test, is_class_body=False, lex_enc=enc)
            b_exits = _stmts_always_exit(stmt.body)
            e_exits = bool(stmt.orelse) and _stmts_always_exit(stmt.orelse)
            survivors: list[_AliasState] = []
            if not b_exits:
                survivors.append(b_st)
            if not e_exits:
                survivors.append(e_st if stmt.orelse else post_test)
            next_posix = posix_proven or (b_exits and not stmt.orelse and f_pos)
            return _join_states(survivors, post_test), next_posix
        if isinstance(stmt, (ast.For, ast.AsyncFor)):
            _visit_expr(stmt.iter, posix_proven, scope_name, st, enc)
            loop_in = st.drop(_target_names(stmt.target) | _expr_named_stores(stmt.iter))
            b_st = _visit_stmts(stmt.body, posix_proven, scope_name, loop_in, is_class_body=False, lex_enc=enc)
            e_st = _visit_stmts(stmt.orelse, posix_proven, scope_name, _join_states([loop_in, b_st], loop_in), is_class_body=False, lex_enc=enc)
            return _join_states([st, b_st, e_st], st), posix_proven
        if isinstance(stmt, ast.While):
            _visit_expr(stmt.test, posix_proven, scope_name, st, enc)
            post_test = st.drop(_expr_named_stores(stmt.test))
            t_pos, _ = _guard_implications(stmt.test, post_test.must_os, post_test.must_sys)
            b_st = _visit_stmts(stmt.body, posix_proven or t_pos, scope_name, post_test, is_class_body=False, lex_enc=enc)
            e_st = _visit_stmts(stmt.orelse, posix_proven, scope_name, post_test, is_class_body=False, lex_enc=enc)
            return _join_states([post_test, b_st, e_st], post_test), posix_proven
        if isinstance(stmt, (ast.With, ast.AsyncWith)):
            cur = st
            for item in stmt.items:
                _visit_expr(item.context_expr, posix_proven, scope_name, cur, enc)
                cur = cur.drop(_expr_named_stores(item.context_expr))
                if item.optional_vars is not None:
                    cur = cur.drop(_target_names(item.optional_vars))
            b_st = _visit_stmts(stmt.body, posix_proven, scope_name, cur, is_class_body=False, lex_enc=enc)
            return b_st, posix_proven
        if isinstance(stmt, (ast.Try, getattr(ast, "TryStar", ast.Try))):
            b_st = _visit_stmts(stmt.body, posix_proven, scope_name, st, is_class_body=False, lex_enc=enc)
            o_st = _visit_stmts(stmt.orelse, posix_proven, scope_name, b_st, is_class_body=False, lex_enc=enc)
            # An exception in `body` can arise before or after imports inside `body`.
            exc_entry = _AliasState(st.must_os & b_st.must_os, st.must_sys & b_st.must_sys, st.may_os | b_st.may_os, st.may_kill | b_st.may_kill)
            survivors = []
            if not _stmts_always_exit(stmt.body) and not _stmts_always_exit(stmt.orelse):
                survivors.append(o_st)
            for handler in stmt.handlers:
                if handler.type is not None:
                    _visit_expr(handler.type, posix_proven, scope_name, exc_entry, enc)
                h_in = exc_entry.drop({handler.name} if handler.name else set())
                h_st = _visit_stmts(handler.body, posix_proven, scope_name, h_in, is_class_body=False, lex_enc=enc)
                if not _stmts_always_exit(handler.body):
                    survivors.append(h_st)
            joined = _join_states(survivors, exc_entry)
            if stmt.finalbody:
                joined = _visit_stmts(stmt.finalbody, posix_proven, scope_name, joined, is_class_body=False, lex_enc=enc)
            return joined, posix_proven
        if isinstance(stmt, ast.Match):
            _visit_expr(stmt.subject, posix_proven, scope_name, st, enc)
            post_subj = st.drop(_expr_named_stores(stmt.subject))
            survivors = []
            for mc in stmt.cases:
                c_in = post_subj.drop(pattern_bound_names(mc.pattern))
                c_pos = posix_proven
                if mc.guard is not None:
                    _visit_expr(mc.guard, posix_proven, scope_name, c_in, enc)
                    c_in = c_in.drop(_expr_named_stores(mc.guard))
                    t_pos, _ = _guard_implications(mc.guard, c_in.must_os, c_in.must_sys)
                    c_pos = c_pos or t_pos
                c_out = _visit_stmts(mc.body, c_pos, scope_name, c_in, is_class_body=False, lex_enc=enc)
                if not _stmts_always_exit(mc.body):
                    survivors.append(c_out)
            return _join_states(survivors, post_subj), posix_proven
        for child in ast.iter_child_nodes(stmt):
            _visit_expr(child, posix_proven, scope_name, st, enc)
        return _apply_simple_stmt(stmt, st), posix_proven

    def _visit_stmts(
        stmts: list[ast.stmt],
        posix_proven: bool,
        scope_name: str,
        st: _AliasState,
        *,
        is_class_body: bool,
        lex_enc: _AliasState | None = None,
    ) -> _AliasState:
        cur_st = st
        cur_posix = posix_proven
        for stmt in stmts:
            enc = lex_enc if is_class_body and lex_enc is not None else cur_st
            cur_st, cur_posix = _visit_stmt(stmt, cur_posix, scope_name, cur_st, enc)
        return cur_st

    _visit_stmts(tree.body, False, "<module>", _EMPTY_STATE, is_class_body=False)
    return errors

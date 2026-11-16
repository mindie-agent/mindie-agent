#!/usr/bin/env python3
"""Scope-aware Windows PID safety AST analyzer for storage modules (Guardrail P8).

[Role]
Verifies via Python stdlib `ast` that storage lifecycle/lease/GC modules never invoke
`os.kill(pid, 0)` (or any aliased/imported `kill(pid, 0)`) unless guarded by a direct literal
POSIX branch.

[Invariants]
- Flags every `<expr>.kill(..., 0)` call unconditionally (eliminating module-alias dataflow
  evasion across comprehensions, loops, and exception handlers) plus every bare/dynamic callee
  reaching `"kill"` in an unbounded whole-tree fixed point (`while changed:`).
- Trusts an identifier in `_guard_implications` (`must_os`, `must_sys`) ONLY when imported by a
  direct top-of-scope `import os` / `import sys` prior to use and NEVER stored, deleted,
  parameterized, captured, declared `global`/`nonlocal`, or re-imported anywhere in `ast.walk(tree)`.
- Evaluates two-valued `(true_implies_posix, false_implies_posix)` De Morgan implications and
  requires exact 1-arg `sys.platform.startswith('win'|'win32')` calls.

[Timeouts & Locks]
- Pure in-memory AST traversal; acquires no locks and spawns no subprocesses.

[Side-Effect Policy]
- Strictly read-only inspection of Python source files.
"""

from __future__ import annotations

import ast
from pathlib import Path

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
            and len(expr.args) == 1
            and not expr.keywords
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


def _call_passes_zero_signal(call: ast.Call) -> bool:
    if len(call.args) >= 2 and _is_int_zero(call.args[1]):
        return True
    for arg in call.args:
        if isinstance(arg, ast.Starred) and isinstance(arg.value, (ast.Tuple, ast.List)):
            elts = arg.value.elts
            if (len(call.args) == 1 and len(elts) >= 2 and _is_int_zero(elts[1])) or (
                arg is not call.args[0] and elts and _is_int_zero(elts[0])
            ):
                return True
    for kw in call.keywords:
        if kw.arg == "sig" and _is_int_zero(kw.value):
            return True
        if kw.arg is None and isinstance(kw.value, ast.Dict):
            for k, v in zip(kw.value.keys, kw.value.values):
                if isinstance(k, ast.Constant) and k.value == "sig" and _is_int_zero(v):
                    return True
    return False


def _target_names(node: ast.AST) -> set[str]:
    return {sub.id for sub in ast.walk(node) if isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del))}


def _expr_mentions_kill(expr: ast.AST, may_kill: set[str]) -> bool:
    for sub in ast.walk(expr):
        if isinstance(sub, ast.Attribute) and sub.attr == "kill":
            return True
        if isinstance(sub, ast.Name) and sub.id in may_kill:
            return True
        if (
            isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Name)
            and sub.func.id == "getattr"
            and len(sub.args) >= 2
            and isinstance(sub.args[1], ast.Constant)
            and sub.args[1].value == "kill"
        ):
            return True
    return False


def _collect_whole_tree_kill_taint(tree: ast.Module) -> frozenset[str]:
    """Compute unbounded whole-tree fixed point of identifier names that may reference `os.kill`."""
    may_kill: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "os":
            for alias in node.names:
                if alias.name == "*":
                    may_kill.add("kill")
                elif alias.name == "kill":
                    may_kill.add(alias.asname or alias.name)
    changed = True
    while changed:
        changed = False
        before = len(may_kill)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and _expr_mentions_kill(node.value, may_kill):
                for tgt in node.targets:
                    may_kill |= _target_names(tgt)
            elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)) and node.value is not None:
                if _expr_mentions_kill(node.value, may_kill):
                    may_kill |= _target_names(node.target)
            elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
                if _expr_mentions_kill(node.iter, may_kill):
                    may_kill |= _target_names(node.target)
            elif isinstance(node, ast.withitem) and node.optional_vars is not None:
                if _expr_mentions_kill(node.context_expr, may_kill):
                    may_kill |= _target_names(node.optional_vars)
        if len(may_kill) != before:
            changed = True
    return frozenset(may_kill)


def _collect_globally_impure_guard_names(tree: ast.Module) -> frozenset[str]:
    """Return every identifier anywhere in `tree` that is ever non-stdlib-imported or mutated/shadowed."""
    impure: set[str] = set()
    scope_top_stmts: set[int] = {id(s) for s in tree.body}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            impure.add(node.name)
            scope_top_stmts.update(id(s) for s in node.body)
            for a in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                impure.add(a.arg)
            if node.args.vararg:
                impure.add(node.args.vararg.arg)
            if node.args.kwarg:
                impure.add(node.args.kwarg.arg)
        elif isinstance(node, ast.Lambda):
            for a in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                impure.add(a.arg)
            if node.args.vararg:
                impure.add(node.args.vararg.arg)
            if node.args.kwarg:
                impure.add(node.args.kwarg.arg)
        elif isinstance(node, ast.ClassDef):
            impure.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            impure.add(node.id)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            impure.update(node.names)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            impure.add(node.name)
        elif isinstance(node, ast.MatchAs) and node.name:
            impure.add(node.name)
        elif isinstance(node, ast.MatchStar) and node.name:
            impure.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            impure.add(node.rest)

    import_sources: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            in_top = id(node) in scope_top_stmts
            for alias in node.names:
                bound = alias.asname or alias.name.split(".", 1)[0]
                src = "os" if (alias.name == "os" or (alias.asname is None and alias.name.startswith("os."))) else (
                    "sys" if alias.name == "sys" else "other"
                )
                if not in_top or src == "other":
                    impure.add(bound)
                import_sources.setdefault(bound, set()).add(src)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    impure.update({"os", "sys"})
                else:
                    impure.add(alias.asname or alias.name)
    for bound, srcs in import_sources.items():
        if len(srcs) > 1:
            impure.add(bound)
    return frozenset(impure)


def inspect_storage_module_windows_pid_safety(path: Path) -> list[str]:
    """Ban `os.kill(pid, 0)` (or imported `kill(pid, 0)`) unless guarded by literal POSIX branch."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    errors: list[str] = []
    may_kill = _collect_whole_tree_kill_taint(tree)
    impure = _collect_globally_impure_guard_names(tree)

    def _visit_expr(node: ast.AST, posix_proven: bool, scope_name: str, m_os: frozenset[str], m_sys: frozenset[str]) -> None:
        if isinstance(node, ast.Lambda):
            for dflt in (*node.args.defaults, *(d for d in node.args.kw_defaults if d is not None)):
                _visit_expr(dflt, posix_proven, scope_name, m_os, m_sys)
            _visit_expr(node.body, posix_proven, scope_name, m_os, m_sys)
            return
        if isinstance(node, _COMPREHENSION_TYPES):
            for gen in node.generators:
                _visit_expr(gen.iter, posix_proven, scope_name, m_os, m_sys)
                for cond in gen.ifs:
                    _visit_expr(cond, posix_proven, scope_name, m_os, m_sys)
                    t_pos, _ = _guard_implications(cond, m_os, m_sys)
                    posix_proven = posix_proven or t_pos
            if isinstance(node, ast.DictComp):
                _visit_expr(node.key, posix_proven, scope_name, m_os, m_sys)
                _visit_expr(node.value, posix_proven, scope_name, m_os, m_sys)
            else:
                _visit_expr(node.elt, posix_proven, scope_name, m_os, m_sys)
            return
        if isinstance(node, ast.IfExp):
            _visit_expr(node.test, posix_proven, scope_name, m_os, m_sys)
            t_pos, f_pos = _guard_implications(node.test, m_os, m_sys)
            _visit_expr(node.body, posix_proven or t_pos, scope_name, m_os, m_sys)
            _visit_expr(node.orelse, posix_proven or f_pos, scope_name, m_os, m_sys)
            return
        if isinstance(node, ast.Call):
            if _call_passes_zero_signal(node) and _expr_mentions_kill(node.func, set(may_kill)) and not posix_proven:
                errors.append(
                    f"line {node.lineno} `{scope_name}` calls unguarded `os.kill(pid, 0)` "
                    "(terminates or misprobes processes on Windows; guard with `os.name != 'nt'` or use Win32 `OpenProcess`)"
                )
        for child in ast.iter_child_nodes(node):
            _visit_expr(child, posix_proven, scope_name, m_os, m_sys)

    def _walk_block(
        block: list[ast.stmt],
        blk_posix: bool,
        scope_name: str,
        m_os: frozenset[str],
        m_sys: frozenset[str],
        *,
        top_block: bool,
        is_class_body: bool = False,
        lex_os: frozenset[str] = frozenset(),
        lex_sys: frozenset[str] = frozenset(),
    ) -> None:
        cur_pos = blk_posix
        cur_o, cur_s = set(m_os), set(m_sys)
        for stmt in block:
            fo, fs = frozenset(cur_o), frozenset(cur_s)
            child_o = lex_os if is_class_body else fo
            child_s = lex_sys if is_class_body else fs
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in stmt.decorator_list:
                    _visit_expr(dec, cur_pos, scope_name, fo, fs)
                for tp in getattr(stmt, "type_params", ()):
                    _visit_expr(tp, cur_pos, scope_name, fo, fs)
                for arg in (*stmt.args.posonlyargs, *stmt.args.args, *stmt.args.kwonlyargs, stmt.args.vararg, stmt.args.kwarg):
                    if arg is not None and arg.annotation is not None:
                        _visit_expr(arg.annotation, cur_pos, scope_name, fo, fs)
                if stmt.returns is not None:
                    _visit_expr(stmt.returns, cur_pos, scope_name, fo, fs)
                for dflt in (*stmt.args.defaults, *(d for d in stmt.args.kw_defaults if d is not None)):
                    _visit_expr(dflt, cur_pos, scope_name, fo, fs)
                _walk_block(stmt.body, cur_pos, stmt.name, child_o, child_s, top_block=True)
            elif isinstance(stmt, ast.ClassDef):
                for dec in stmt.decorator_list:
                    _visit_expr(dec, cur_pos, scope_name, fo, fs)
                for tp in getattr(stmt, "type_params", ()):
                    _visit_expr(tp, cur_pos, scope_name, fo, fs)
                for b in stmt.bases:
                    _visit_expr(b, cur_pos, scope_name, fo, fs)
                for kw in stmt.keywords:
                    _visit_expr(kw.value, cur_pos, scope_name, fo, fs)
                _walk_block(
                    stmt.body, cur_pos, stmt.name, child_o, child_s,
                    top_block=False, is_class_body=True, lex_os=child_o, lex_sys=child_s,
                )
            elif isinstance(stmt, ast.If):
                _visit_expr(stmt.test, cur_pos, scope_name, fo, fs)
                t_pos, f_pos = _guard_implications(stmt.test, fo, fs)
                _walk_block(stmt.body, cur_pos or t_pos, scope_name, fo, fs, top_block=False)
                _walk_block(stmt.orelse, cur_pos or f_pos, scope_name, fo, fs, top_block=False)
                if not stmt.orelse and f_pos and _stmts_always_exit(stmt.body):
                    cur_pos = True
            elif isinstance(stmt, (ast.Try, getattr(ast, "TryStar", ast.Try))):
                _walk_block(stmt.body, cur_pos, scope_name, fo, fs, top_block=False)
                _walk_block(stmt.orelse, cur_pos, scope_name, fo, fs, top_block=False)
                for h in stmt.handlers:
                    if h.type is not None:
                        _visit_expr(h.type, cur_pos, scope_name, fo, fs)
                    _walk_block(h.body, cur_pos, scope_name, fo, fs, top_block=False)
                _walk_block(stmt.finalbody, cur_pos, scope_name, fo, fs, top_block=False)
            elif isinstance(stmt, ast.Match):
                _visit_expr(stmt.subject, cur_pos, scope_name, fo, fs)
                for mc in stmt.cases:
                    c_pos = cur_pos
                    if mc.guard is not None:
                        _visit_expr(mc.guard, cur_pos, scope_name, fo, fs)
                        t_pos, _ = _guard_implications(mc.guard, fo, fs)
                        c_pos = c_pos or t_pos
                    _walk_block(mc.body, c_pos, scope_name, fo, fs, top_block=False)
            else:
                for _, val in ast.iter_fields(stmt):
                    if isinstance(val, list):
                        if val and all(isinstance(it, ast.stmt) for it in val):
                            _walk_block(val, cur_pos, scope_name, fo, fs, top_block=False)
                        else:
                            for it in val:
                                if isinstance(it, ast.AST):
                                    _visit_expr(it, cur_pos, scope_name, fo, fs)
                    elif isinstance(val, ast.AST):
                        _visit_expr(val, cur_pos, scope_name, fo, fs)

            if top_block and isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    bound = alias.asname or alias.name.split(".", 1)[0]
                    if bound in impure:
                        continue
                    if alias.name == "os" or (alias.asname is None and alias.name.startswith("os.")):
                        cur_o.add(bound)
                    elif alias.name == "sys":
                        cur_s.add(bound)

    _walk_block(tree.body, False, "<module>", frozenset(), frozenset(), top_block=True)
    return errors

#!/usr/bin/env python3
"""Capability-restricted Windows PID safety AST verifier for storage modules (Guardrail P8).

[Role]
Verifies via Python stdlib `ast` that storage lifecycle/lease/GC modules never invoke
`os.kill(pid, 0)` (or any aliased, reflective, or wildcard-imported equivalent) unless guarded
by a proven literal POSIX branch.

[Invariants]
- Enforces a syntactic capability allowlist rather than heuristic alias taint:
  1. Bans wildcard imports (`from ... import *`), reflective/dynamic attribute access to `"kill"`
     (non-literal `getattr`, `getattr(..., 'kill')`, `__getattribute__`, `__dict__`, `attrgetter`,
     `methodcaller`, `eval`, `exec`, non-call references to `getattr`/`setattr`/`delattr`), and
     any mutation/deletion of `.name`, `.platform`, or `.kill` attributes.
  2. Bans first-class value references to `.kill` or imported `kill` (`check=os.kill`, `[os.kill]`,
     `f = os.kill`, `match os.kill:`): `.kill` / `kill` may ONLY appear directly as `Call.func`.
  3. Requires every direct `<expr>.kill(...)` / `kill(...)` call (except 0-arg `proc.kill()` or
     explicit 2-arg non-zero `int` signal literal) to execute at a proven literal POSIX point.
  4. Trusts `os`/`sys` in `_guard_implications` ONLY via `==`/`!=` (never `is`/`is not`) and 1-arg
     `startswith('win'|'win32')` when the identifier is top-of-scope imported and globally unmutated.

[Timeouts & Locks]
- Pure in-memory AST traversal; acquires no locks and spawns no subprocesses.

[Side-Effect Policy]
- Strictly read-only inspection of Python source files.
"""

from __future__ import annotations

import ast
from pathlib import Path

_COMPREHENSION_TYPES = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
_REFLECTIVE_FNS = frozenset(
    {"getattr", "setattr", "delattr", "eval", "exec", "compile", "vars", "globals", "locals", "attrgetter", "methodcaller"}
)


def _stmts_always_exit(stmts: list[ast.stmt], *, in_loop: bool) -> bool:
    for stmt in stmts:
        if isinstance(stmt, (ast.Return, ast.Raise)):
            return True
        if in_loop and isinstance(stmt, (ast.Break, ast.Continue)):
            return True
        if isinstance(stmt, ast.If) and stmt.orelse:
            if _stmts_always_exit(stmt.body, in_loop=in_loop) and _stmts_always_exit(stmt.orelse, in_loop=in_loop):
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
        if not (
            isinstance(left, ast.Attribute)
            and isinstance(left.value, ast.Name)
            and isinstance(right, ast.Constant)
            and isinstance(right.value, str)
        ):
            return False, False
        if left.value.id in os_aliases and left.attr == "name":
            if right.value == "nt":
                if isinstance(op, ast.Eq):
                    return False, True
                if isinstance(op, ast.NotEq):
                    return True, False
            elif right.value == "posix" and isinstance(op, ast.Eq):
                return True, False
        if left.value.id in sys_aliases and left.attr == "platform" and right.value == "win32":
            if isinstance(op, ast.Eq):
                return False, True
            if isinstance(op, ast.NotEq):
                return True, False
    return False, False


def _is_exempt_direct_kill_call(call: ast.Call, imported_kill_names: frozenset[str]) -> bool:
    """Exempt only 0-arg `proc.kill()` or explicit 2-arg non-zero `int` signal literal."""
    is_bare_imported_kill = isinstance(call.func, ast.Name) and call.func.id in imported_kill_names
    if not is_bare_imported_kill and not call.args and not call.keywords:
        return True
    if (
        len(call.args) == 2
        and not call.keywords
        and not isinstance(call.args[0], ast.Starred)
        and isinstance(call.args[1], ast.Constant)
        and type(call.args[1].value) is int
        and call.args[1].value != 0
    ):
        return True
    return False


def _collect_tree_facts(tree: ast.Module) -> tuple[frozenset[str], frozenset[str], list[str]]:
    """Collect `(imported_kill_names, impure_guard_names, capability_errors)` across `tree`."""
    call_func_ids = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    imported_kills: set[str] = set()
    impure: set[str] = set()
    cap_errors: list[str] = []
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
                    cap_errors.append(
                        f"line {node.lineno} wildcard `from {node.module or '.'} import *` is banned in storage modules"
                    )
                else:
                    bound = alias.asname or alias.name
                    impure.add(bound)
                    if alias.name == "kill":
                        imported_kills.add(bound)

    for bound, srcs in import_sources.items():
        if len(srcs) > 1:
            impure.add(bound)

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if isinstance(node.ctx, (ast.Store, ast.Del)) and node.attr in {"name", "platform", "kill"}:
                cap_errors.append(
                    f"line {node.lineno} mutating or deleting `.{node.attr}` is banned in storage modules"
                )
            elif node.attr in {"__dict__", "__getattribute__"}:
                cap_errors.append(
                    f"line {node.lineno} reflective `.{node.attr}` access is banned in storage modules"
                )
            elif isinstance(node.ctx, ast.Load) and node.attr == "kill" and id(node) not in call_func_ids:
                cap_errors.append(
                    f"line {node.lineno} first-class/aliased `.kill` reference is banned in storage modules"
                )
            elif isinstance(node.ctx, ast.Load) and node.attr in _REFLECTIVE_FNS and id(node) not in call_func_ids:
                cap_errors.append(
                    f"line {node.lineno} first-class/aliased `.{node.attr}` reference is banned in storage modules"
                )
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id in imported_kills and id(node) not in call_func_ids:
                cap_errors.append(
                    f"line {node.lineno} first-class/aliased `{node.id}` reference is banned in storage modules"
                )
            elif node.id in _REFLECTIVE_FNS and id(node) not in call_func_ids:
                cap_errors.append(
                    f"line {node.lineno} first-class/aliased `{node.id}` reference is banned in storage modules"
                )
        elif isinstance(node, ast.Call):
            fn = node.func
            fn_name = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "")
            if fn_name in {"setattr", "delattr", "eval", "exec", "compile", "vars", "globals", "locals", "attrgetter", "methodcaller"}:
                cap_errors.append(f"line {node.lineno} `{fn_name}(...)` is banned in storage modules")
            elif fn_name == "getattr":
                if (
                    len(node.args) < 2
                    or len(node.args) > 3
                    or node.keywords
                    or not isinstance(node.args[1], ast.Constant)
                    or not isinstance(node.args[1].value, str)
                    or node.args[1].value in {"kill", "name", "platform", "__dict__", "__getattribute__"}
                ):
                    cap_errors.append(
                        f"line {node.lineno} dynamic or sensitive `getattr(...)` is banned in storage modules"
                    )

    return frozenset(imported_kills), frozenset(impure), cap_errors


def inspect_storage_module_windows_pid_safety(path: Path) -> list[str]:
    """Verify storage module `path` never calls `os.kill(pid, 0)` outside proven POSIX branches."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    imported_kills, impure, errors = _collect_tree_facts(tree)

    def _visit_expr(node: ast.AST, posix_proven: bool, scope_name: str, m_os: frozenset[str], m_sys: frozenset[str]) -> None:
        if isinstance(node, ast.Lambda):
            for dflt in (*node.args.defaults, *(d for d in node.args.kw_defaults if d is not None)):
                _visit_expr(dflt, posix_proven, scope_name, m_os, m_sys)
            _visit_expr(node.body, posix_proven, scope_name, m_os, m_sys)
            return
        if isinstance(node, _COMPREHENSION_TYPES):
            for gen in node.generators:
                _visit_expr(gen.iter, posix_proven, scope_name, m_os, m_sys)
                _visit_expr(gen.target, posix_proven, scope_name, m_os, m_sys)
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
            fn = node.func
            is_kill_call = (isinstance(fn, ast.Attribute) and fn.attr == "kill") or (
                isinstance(fn, ast.Name) and fn.id in imported_kills
            )
            if is_kill_call and not _is_exempt_direct_kill_call(node, imported_kills) and not posix_proven:
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
        in_loop: bool = False,
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
                _walk_block(stmt.body, cur_pos, stmt.name, child_o, child_s, top_block=True, in_loop=False)
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
                    top_block=False, in_loop=False, is_class_body=True, lex_os=child_o, lex_sys=child_s,
                )
            elif isinstance(stmt, ast.If):
                _visit_expr(stmt.test, cur_pos, scope_name, fo, fs)
                t_pos, f_pos = _guard_implications(stmt.test, fo, fs)
                _walk_block(stmt.body, cur_pos or t_pos, scope_name, fo, fs, top_block=False, in_loop=in_loop)
                _walk_block(stmt.orelse, cur_pos or f_pos, scope_name, fo, fs, top_block=False, in_loop=in_loop)
                if not stmt.orelse and f_pos and _stmts_always_exit(stmt.body, in_loop=in_loop):
                    cur_pos = True
            elif isinstance(stmt, (ast.For, ast.AsyncFor)):
                _visit_expr(stmt.iter, cur_pos, scope_name, fo, fs)
                _visit_expr(stmt.target, cur_pos, scope_name, fo, fs)
                _walk_block(stmt.body, cur_pos, scope_name, fo, fs, top_block=False, in_loop=True)
                _walk_block(stmt.orelse, cur_pos, scope_name, fo, fs, top_block=False, in_loop=in_loop)
            elif isinstance(stmt, ast.While):
                _visit_expr(stmt.test, cur_pos, scope_name, fo, fs)
                t_pos, _ = _guard_implications(stmt.test, fo, fs)
                _walk_block(stmt.body, cur_pos or t_pos, scope_name, fo, fs, top_block=False, in_loop=True)
                _walk_block(stmt.orelse, cur_pos, scope_name, fo, fs, top_block=False, in_loop=in_loop)
            elif isinstance(stmt, (ast.Try, getattr(ast, "TryStar", ast.Try))):
                _walk_block(stmt.body, cur_pos, scope_name, fo, fs, top_block=False, in_loop=False)
                _walk_block(stmt.orelse, cur_pos, scope_name, fo, fs, top_block=False, in_loop=in_loop)
                for h in stmt.handlers:
                    if h.type is not None:
                        _visit_expr(h.type, cur_pos, scope_name, fo, fs)
                    _walk_block(h.body, cur_pos, scope_name, fo, fs, top_block=False, in_loop=in_loop)
                _walk_block(stmt.finalbody, cur_pos, scope_name, fo, fs, top_block=False, in_loop=in_loop)
            elif isinstance(stmt, ast.Match):
                _visit_expr(stmt.subject, cur_pos, scope_name, fo, fs)
                for mc in stmt.cases:
                    c_pos = cur_pos
                    if mc.guard is not None:
                        _visit_expr(mc.guard, cur_pos, scope_name, fo, fs)
                        t_pos, _ = _guard_implications(mc.guard, fo, fs)
                        c_pos = c_pos or t_pos
                    _walk_block(mc.body, c_pos, scope_name, fo, fs, top_block=False, in_loop=in_loop)
            else:
                for _, val in ast.iter_fields(stmt):
                    if isinstance(val, list):
                        if val and all(isinstance(it, ast.stmt) for it in val):
                            _walk_block(val, cur_pos, scope_name, fo, fs, top_block=False, in_loop=in_loop)
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

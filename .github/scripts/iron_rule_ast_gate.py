#!/usr/bin/env python3
"""R4 AST Structural Gate: Router Read/Control Fast-Lane, Iron Rule 3 & Iron Rule 4.

[Role]
Enforces three structural AST invariants across `harness` and the 7 native host plugins:
1. `P2.7`: `MCPRouter.call_tool` in `harness/mindie_harness/mcp/router.py` never calls `claim_bind`
   before read/control classification (`is_readonly_tool_call` / `is_readonly_or_control_tool`) or
   outside a mutation-only / explicit-bind-id `ast.If` guard (0 `claim_bind` calls passes cleanly).
2. `Iron Rule 4`: Bans speculative `_call_variants` / `call_variants` and `inspect.signature`
   probing across `harness` and all 7 host plugins.
3. `Iron Rule 3`: Bans plugin-local `rpc_knowledge` / `knowledge_transport` / `knowledge_rpc` /
   `_knowledge_fallback` / `"knowledge_unavailable"` shadow dispatchers in the 7 host plugins.

[Invariants]
- Pure Python 3.11+ stdlib (`ast`, `os`, `pathlib`); ignores module/class/function docstrings.

[Timeouts & Locks]
- Pure synchronous local file reads and AST traversal (`< 1s`); zero subprocesses or locks.

[Side-Effect Policy]
- Strictly read-only static inspection of repository checkouts.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Mapping, Sequence

from repo_roots import ALL_PLUGINS, resolve_repo
from storage_lifecycle_gate import PRODUCTION_PYTHON_SCOPES

_READONLY_CLASSIFIERS: frozenset[str] = frozenset({"is_readonly_tool_call", "is_readonly_or_control_tool"})
_BANNED_VARIANTS: frozenset[str] = frozenset({"_call_variants", "call_variants"})
_BANNED_SHADOW_STEMS: frozenset[str] = frozenset({"rpc_knowledge", "knowledge_transport", "knowledge_rpc"})
_BANNED_SHADOW_SYMBOLS: frozenset[str] = frozenset(
    {"rpc_knowledge", "knowledge_transport", "knowledge_rpc", "_knowledge_fallback"}
)
_SKIP_DIRS: frozenset[str] = frozenset({"__pycache__", "tests", "test", "node_modules", "dist", "build", ".git", ".venv"})


def _docstring_ids(tree: ast.AST) -> set[int]:
    return {
        id(n.body[0].value)
        for n in ast.walk(tree)
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and n.body
        and isinstance(n.body[0], ast.Expr)
        and isinstance(n.body[0].value, ast.Constant)
        and isinstance(n.body[0].value.value, str)
    }


def _iter_scoped_py_files(repo_dir: Path, scopes: Sequence[str]) -> list[Path]:
    found: list[Path] = []
    for scope in scopes:
        base = repo_dir / scope
        if not base.is_dir():
            continue
        for dpath, dnames, fnames in os.walk(base):
            dnames[:] = sorted(d for d in dnames if d not in _SKIP_DIRS and not d.startswith("."))
            found.extend(Path(dpath) / fn for fn in sorted(fnames) if fn.endswith(".py"))
    return found


def _call_name(node: ast.Call) -> str | None:
    return node.func.id if isinstance(node.func, ast.Name) else (node.func.attr if isinstance(node.func, ast.Attribute) else None)


def _expr_calls_classifier(expr: ast.AST, extra: set[str]) -> bool:
    return any(isinstance(s, ast.Call) and _call_name(s) in (_READONLY_CLASSIFIERS | extra) for s in ast.walk(expr))


def _is_bind_id_symbol(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        tok = node.id.lower()
    elif isinstance(node, ast.Attribute):
        tok = node.attr.lower()
    elif isinstance(node, ast.Call) and (cn := _call_name(node)):
        tok = cn.lower()
    else:
        return False
    return "bind_id" in tok and "session" not in tok


def _is_explicit_bind_id_guard(expr: ast.AST) -> bool:
    for sub in ast.walk(expr):
        if isinstance(sub, ast.Name) and "session" in sub.id.lower():
            return False
        if isinstance(sub, ast.Attribute) and "session" in sub.attr.lower():
            return False
    if _is_bind_id_symbol(expr):
        return True
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and expr.func.id == "bool" and len(expr.args) == 1:
        return _is_bind_id_symbol(expr.args[0])
    if isinstance(expr, ast.Compare) and len(expr.ops) == 1 and len(expr.comparators) == 1:
        left, op, right = expr.left, expr.ops[0], expr.comparators[0]
        if isinstance(op, (ast.IsNot, ast.NotEq)):
            if isinstance(right, ast.Constant) and right.value is None and _is_bind_id_symbol(left):
                return True
            if isinstance(left, ast.Constant) and left.value is None and _is_bind_id_symbol(right):
                return True
    if isinstance(expr, ast.BoolOp) and isinstance(expr.op, ast.And):
        return any(_is_explicit_bind_id_guard(v) for v in expr.values)
    return False


def _guard_is_mutation_only(
    polarity: str, test: ast.AST, readonly_vars: set[str], mutating_vars: set[str], extra: set[str]
) -> bool:
    def _is_ro(e: ast.AST) -> bool:
        if isinstance(e, ast.UnaryOp) and isinstance(e.op, ast.Not):
            return False
        return (isinstance(e, ast.Name) and e.id in readonly_vars) or _expr_calls_classifier(e, extra)

    def _is_mut(e: ast.AST) -> bool:
        if isinstance(e, ast.Name) and e.id in mutating_vars:
            return True
        if isinstance(e, ast.UnaryOp) and isinstance(e.op, ast.Not) and _is_ro(e.operand):
            return True
        if isinstance(e, ast.Compare) and len(e.ops) == 1 and len(e.comparators) == 1:
            left, op, right = e.left, e.ops[0], e.comparators[0]
            if isinstance(op, (ast.Is, ast.Eq)) and isinstance(right, ast.Constant) and right.value is False:
                return _is_ro(left)
            if isinstance(op, (ast.IsNot, ast.NotEq)) and isinstance(right, ast.Constant) and right.value is True:
                return _is_ro(left)
        return isinstance(e, ast.BoolOp) and isinstance(e.op, ast.And) and any(_is_mut(v) for v in e.values)

    if polarity == "pos":
        if _is_mut(test):
            return True
        if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.Or):
            return any(_is_mut(v) for v in test.values) and all(
                _is_mut(v) or _is_explicit_bind_id_guard(v) for v in test.values
            )
        return False
    return any(_is_ro(v) for v in test.values) if (isinstance(test, ast.BoolOp) and isinstance(test.op, ast.Or)) else _is_ro(test)


def _block_terminates(stmts: Sequence[ast.stmt]) -> bool:
    return bool(stmts) and isinstance(stmts[-1], (ast.Return, ast.Raise))


def _check_harness_router_claim_bind(harness_dir: Path, errors: list[str]) -> None:
    router_path = harness_dir / "mindie_harness/mcp/router.py"
    if not router_path.is_file():
        return
    try:
        tree = ast.parse(router_path.read_text(encoding="utf-8"), filename=str(router_path))
    except SyntaxError as exc:
        errors.append(f"harness: mindie_harness/mcp/router.py syntax error during Iron Rule AST gate: {exc}")
        return
    router_cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MCPRouter"), None)
    if router_cls is None:
        return
    methods = {n.name: n for n in router_cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    call_tool = methods.get("call_tool")
    if call_tool is None:
        return

    claim_helpers = {
        m for m, n in methods.items() if m != "call_tool" and any(isinstance(s, ast.Call) and _call_name(s) == "claim_bind" for s in ast.walk(n))
    }
    cls_helpers = {
        m for m, n in methods.items() if m != "call_tool" and any(isinstance(s, ast.Call) and _call_name(s) in _READONLY_CLASSIFIERS for s in ast.walk(n))
    }
    cls_lines = [s.lineno for s in ast.walk(call_tool) if isinstance(s, ast.Call) and _call_name(s) in (_READONLY_CLASSIFIERS | cls_helpers)]
    earliest_cls = min(cls_lines) if cls_lines else None

    readonly_vars, mutating_vars = set(), set()
    for sub in ast.walk(call_tool):
        if isinstance(sub, ast.Assign) and len(sub.targets) == 1 and isinstance(sub.targets[0], ast.Name):
            tgt = sub.targets[0].id
            if isinstance(sub.value, ast.UnaryOp) and isinstance(sub.value.op, ast.Not) and (
                (isinstance(sub.value.operand, ast.Name) and sub.value.operand.id in readonly_vars)
                or _expr_calls_classifier(sub.value.operand, cls_helpers)
            ):
                mutating_vars.add(tgt)
            elif _expr_calls_classifier(sub.value, cls_helpers):
                readonly_vars.add(tgt)

    claim_sites: list[tuple[int, list[tuple[str, ast.AST]]]] = []
    targets = {"claim_bind"} | claim_helpers

    def _scan_expr(expr: ast.AST | None, guards: list[tuple[str, ast.AST]]) -> None:
        if expr is not None:
            claim_sites.extend((s.lineno, list(guards)) for s in ast.walk(expr) if isinstance(s, ast.Call) and _call_name(s) in targets)

    def _walk_stmts(stmts: Sequence[ast.stmt], guards: list[tuple[str, ast.AST]]) -> None:
        cur_guards = list(guards)
        for stmt in stmts:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(stmt, ast.If):
                _scan_expr(stmt.test, cur_guards)
                _walk_stmts(stmt.body, [*cur_guards, ("pos", stmt.test)])
                _walk_stmts(stmt.orelse, [*cur_guards, ("neg", stmt.test)])
                if _block_terminates(stmt.body) and not stmt.orelse:
                    cur_guards = [*cur_guards, ("neg", stmt.test)]
                elif _block_terminates(stmt.orelse) and not _block_terminates(stmt.body):
                    cur_guards = [*cur_guards, ("pos", stmt.test)]
                continue
            if isinstance(stmt, (ast.With, ast.AsyncWith)):
                for item in stmt.items:
                    _scan_expr(item.context_expr, cur_guards)
                    _scan_expr(item.optional_vars, cur_guards)
            elif isinstance(stmt, (ast.For, ast.AsyncFor)):
                _scan_expr(stmt.iter, cur_guards)
            elif isinstance(stmt, ast.While):
                _scan_expr(stmt.test, cur_guards)
            has_block = False
            for attr in ("body", "orelse", "finalbody"):
                if isinstance(child := getattr(stmt, attr, None), list):
                    has_block = True
                    _walk_stmts(child, cur_guards)
            if isinstance(stmt, ast.Try):
                for h in stmt.handlers:
                    _walk_stmts(h.body, cur_guards)
            elif not has_block:
                _scan_expr(stmt, cur_guards)

    _walk_stmts(call_tool.body, [])
    for lineno, active_guards in claim_sites:
        if earliest_cls is None or earliest_cls >= lineno:
            errors.append(
                f"harness: mindie_harness/mcp/router.py line {lineno} invokes `claim_bind` before "
                "`is_readonly_tool_call` classification in `MCPRouter.call_tool` (violates P2.7)"
            )
        if not active_guards or not any(
            _guard_is_mutation_only(pol, tst, readonly_vars, mutating_vars, cls_helpers) for pol, tst in active_guards
        ):
            errors.append(
                f"harness: mindie_harness/mcp/router.py line {lineno} invokes `claim_bind` outside a "
                "`not readonly` mutation-only `if` guard in `MCPRouter.call_tool` (violates P2.7)"
            )


def _check_file_iron_rules(repo_name: str, repo_dir: Path, py_path: Path, *, is_plugin: bool, errors: list[str]) -> None:
    rel = py_path.relative_to(repo_dir).as_posix()
    if is_plugin and py_path.stem in _BANNED_SHADOW_STEMS:
        errors.append(
            f"{repo_name}: {rel} defines forbidden plugin-local shadow module `{py_path.stem}.py` "
            "(violates Iron Rule 3; `mindie_harness` owns knowledge RPC)"
        )
    try:
        tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
    except SyntaxError as exc:
        errors.append(f"{repo_name}: {rel} syntax error during Iron Rule AST gate: {exc}")
        return

    docs = _docstring_ids(tree)
    inspect_aliases = {"inspect"} | {
        al.asname or "inspect" for n in ast.walk(tree) if isinstance(n, ast.Import) for al in n.names if al.name == "inspect"
    }
    for node in ast.walk(tree):
        if id(node) in docs:
            continue
        ln = getattr(node, "lineno", 1)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name in _BANNED_VARIANTS:
                errors.append(f"{repo_name}: {rel}:{ln} defines banned `{node.name}` (violates Iron Rule 4)")
            if is_plugin and node.name in _BANNED_SHADOW_SYMBOLS:
                errors.append(f"{repo_name}: {rel}:{ln} defines banned plugin shadow `{node.name}` (violates Iron Rule 3)")
        elif isinstance(node, ast.Name):
            if node.id in _BANNED_VARIANTS:
                errors.append(f"{repo_name}: {rel}:{ln} references banned `{node.id}` (violates Iron Rule 4)")
            if is_plugin and node.id in _BANNED_SHADOW_SYMBOLS:
                errors.append(f"{repo_name}: {rel}:{ln} references banned plugin shadow `{node.id}` (violates Iron Rule 3)")
        elif isinstance(node, ast.Attribute):
            if node.attr in _BANNED_VARIANTS:
                errors.append(f"{repo_name}: {rel}:{ln} accesses banned `.{node.attr}` (violates Iron Rule 4)")
            if node.attr == "signature" and isinstance(node.value, ast.Name) and node.value.id in inspect_aliases:
                errors.append(f"{repo_name}: {rel}:{ln} calls `inspect.signature` speculative probing (violates Iron Rule 4)")
            if is_plugin and node.attr in _BANNED_SHADOW_SYMBOLS:
                errors.append(f"{repo_name}: {rel}:{ln} accesses banned plugin shadow `.{node.attr}` (violates Iron Rule 3)")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for al in node.names:
                for tok in filter(None, (al.name, al.asname)):
                    if tok in _BANNED_VARIANTS:
                        errors.append(f"{repo_name}: {rel}:{ln} imports banned `{tok}` (violates Iron Rule 4)")
                    if is_plugin and (tok in _BANNED_SHADOW_SYMBOLS or mod.split(".")[-1] in _BANNED_SHADOW_SYMBOLS):
                        errors.append(f"{repo_name}: {rel}:{ln} imports banned plugin shadow `{tok}` (violates Iron Rule 3)")
                if mod == "inspect" and al.name == "signature":
                    errors.append(f"{repo_name}: {rel}:{ln} imports `inspect.signature` speculative probing (violates Iron Rule 4)")
        elif isinstance(node, ast.Import) and is_plugin:
            for al in node.names:
                if hit := (set(al.name.split(".")) | ({al.asname} if al.asname else set())) & _BANNED_SHADOW_SYMBOLS:
                    errors.append(f"{repo_name}: {rel}:{ln} imports banned plugin shadow {sorted(hit)} (violates Iron Rule 3)")
        elif isinstance(node, ast.Constant) and is_plugin and node.value == "knowledge_unavailable":
            errors.append(f"{repo_name}: {rel}:{ln} emits plugin-local `'knowledge_unavailable'` shadow error (violates Iron Rule 3)")


def verify_iron_rule_ast_contracts(
    siblings_roots: Sequence[Path], *, explicit_repos: Mapping[str, Path] | None = None
) -> list[str]:
    """Enforce P2.7 router ordering, Iron Rule 4 signature-probing bans, and Iron Rule 3 shadow bans."""
    errors: list[str] = []
    try:
        harness_dir = resolve_repo("harness", siblings_roots, explicit_repos=explicit_repos)
    except ValueError as exc:
        errors.append(str(exc))
        harness_dir = None
    if harness_dir is not None:
        _check_harness_router_claim_bind(harness_dir, errors)
        for py_path in _iter_scoped_py_files(harness_dir, PRODUCTION_PYTHON_SCOPES.get("harness", ())):
            _check_file_iron_rules("harness", harness_dir, py_path, is_plugin=False, errors=errors)
    for plugin_name in ALL_PLUGINS:
        try:
            plugin_dir = resolve_repo(plugin_name, siblings_roots, explicit_repos=explicit_repos)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if plugin_dir is not None:
            for py_path in _iter_scoped_py_files(plugin_dir, PRODUCTION_PYTHON_SCOPES.get(plugin_name, ())):
                _check_file_iron_rules(plugin_name, plugin_dir, py_path, is_plugin=True, errors=errors)
    return list(dict.fromkeys(errors))

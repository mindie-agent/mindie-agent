#!/usr/bin/env python3
"""Focused AST boundary gate for Windows PID safety and zero control-plane NPU init (P8 / AD-08).
[Role] Verifies via stdlib `ast` across all MindIE Agent repos that Windows-reachable code never
invokes `os.kill(pid, 0)` outside a proven POSIX guard and control-plane modules never execute
top-level `import torch_npu`.
[Invariants] Tracks per-scope bindings without locking private variable names or banning `match`.
[Timeouts & Locks] Pure synchronous in-memory AST traversal; zero subprocesses or locks.
[Side-Effect Policy] Strictly read-only inspection of Python source files.
"""
from __future__ import annotations
import ast
from pathlib import Path
from storage_temp_ast import iter_direct_nodes, local_bound_names
_COMPS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _scope_binding_counts(scope: ast.AST, *, walk_nested: bool = False) -> dict[str, int]:
    counts: dict[str, int] = {}
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        for a in (*scope.args.posonlyargs, *scope.args.args, *scope.args.kwonlyargs, scope.args.vararg, scope.args.kwarg):
            if a is not None:
                counts[a.arg] = counts.get(a.arg, 0) + 1
    for sub in (list(ast.walk(scope))[1:] if walk_nested else iter_direct_nodes(scope)):
        names: list[str] = []
        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and sub.name:
            names.append(sub.name)
        elif walk_nested and isinstance(sub, ast.arg):
            names.append(sub.arg)
        elif isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del)):
            names.append(sub.id)
        elif isinstance(sub, (ast.Global, ast.Nonlocal)):
            names.extend(sub.names)
        elif isinstance(sub, ast.MatchMapping) and sub.rest:
            names.append(sub.rest)
        elif isinstance(sub, (ast.Import, ast.ImportFrom)):
            names.extend(al.asname or al.name.split(".", 1)[0] for al in sub.names)
        for nm in names:
            counts[nm] = counts.get(nm, 0) + 1
    return counts


def _guard_implications(expr: ast.AST, pure_os: frozenset[str], pure_sys: frozenset[str], pflags: frozenset[str], wflags: frozenset[str]) -> tuple[bool, bool]:
    if isinstance(expr, ast.Name):
        return (True, False) if expr.id in pflags else ((False, True) if expr.id in wflags else (False, False))
    if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.Not):
        t, f = _guard_implications(expr.operand, pure_os, pure_sys, pflags, wflags)
        return f, t
    if isinstance(expr, ast.BoolOp):
        pts = [_guard_implications(v, pure_os, pure_sys, pflags, wflags) for v in expr.values]
        return (any(t for t, _ in pts), all(f for _, f in pts)) if isinstance(expr.op, ast.And) else ((all(t for t, _ in pts), any(f for _, f in pts)) if isinstance(expr.op, ast.Or) else (False, False))
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute):
        rc = expr.func.value
        if isinstance(rc, ast.Attribute) and isinstance(rc.value, ast.Name) and rc.value.id in pure_sys and rc.attr == "platform" and expr.func.attr == "startswith" and len(expr.args) == 1 and not expr.keywords and isinstance(expr.args[0], ast.Constant) and expr.args[0].value in {"win", "win32", "darwin", "linux"}:
            return (False, True) if expr.args[0].value in {"win", "win32"} else (True, False)
    if isinstance(expr, ast.Compare) and len(expr.ops) == 1 and len(expr.comparators) == 1:
        l, op, r = expr.left, expr.ops[0], expr.comparators[0]
        if isinstance(l, ast.Name) and l.id in {"platform", "os_name"} and isinstance(r, ast.Constant) and r.value == "posix" and isinstance(op, ast.Eq):
            return True, False
        if isinstance(l, ast.Attribute) and isinstance(l.value, ast.Name) and isinstance(r, ast.Constant) and isinstance(r.value, str):
            if l.value.id in pure_os and l.attr == "name":
                return ((False, True) if isinstance(op, ast.Eq) else ((True, False) if isinstance(op, ast.NotEq) else (False, False))) if r.value == "nt" else ((True, False) if r.value == "posix" and isinstance(op, ast.Eq) else (False, False))
            if l.value.id in pure_sys and l.attr == "platform":
                return ((False, True) if isinstance(op, ast.Eq) else ((True, False) if isinstance(op, ast.NotEq) else (False, False))) if r.value == "win32" else ((True, False) if r.value in {"darwin", "linux"} and isinstance(op, ast.Eq) else (False, False))
    return False, False


def _exits(stmts: list[ast.stmt], *, in_loop: bool) -> bool:
    return any(isinstance(s, (ast.Return, ast.Raise)) or (in_loop and isinstance(s, (ast.Break, ast.Continue))) or (isinstance(s, ast.If) and bool(s.orelse) and _exits(s.body, in_loop=in_loop) and _exits(s.orelse, in_loop=in_loop)) or (isinstance(s, ast.Try) and (_exits(s.finalbody, in_loop=in_loop) or (_exits(s.body, in_loop=in_loop) and all(_exits(h.body, in_loop=in_loop) for h in s.handlers)))) for s in stmts)


def analyze_module_platform_guards(tree: ast.Module) -> tuple[frozenset[str], frozenset[str], bool, list[tuple[ast.AST, str, bool]]]:
    top_counts = _scope_binding_counts(tree)
    rebound = {nm for n in ast.walk(tree) if isinstance(n, (ast.Global, ast.Nonlocal)) for nm in n.names} | {n.target.id for n in ast.walk(tree) if isinstance(n, ast.NamedExpr) and isinstance(n.target, ast.Name)}
    all_os, all_sys, all_kills, pure_os, pure_sys = set(), set(), set(), set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for al in node.names:
                b = al.asname or al.name.split(".", 1)[0]
                is_pure = node in tree.body and top_counts.get(b) == 1 and b not in rebound
                if al.name == "os" or (al.asname is None and al.name == "os.path"):
                    all_os.add(b)
                    pure_os.update((b,) if is_pure else ())
                elif al.name == "sys":
                    all_sys.add(b)
                    pure_sys.update((b,) if is_pure else ())
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".", 1)[0] == "os":
            all_kills.update(al.asname or al.name for al in node.names if al.name == "kill")
    for _ in range(4):
        for n in ast.walk(tree):
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
                t, v = n.targets[0].id, n.value
                all_os.update((t,) if isinstance(v, ast.Name) and v.id in all_os else ())
                all_kills.update((t,) if (isinstance(v, ast.Name) and v.id in all_kills) or (isinstance(v, ast.Attribute) and v.attr == "kill" and ((isinstance(v.value, ast.Name) and v.value.id in all_os) or (isinstance(v.value, ast.Attribute) and v.value.attr == "os"))) else ())
            elif isinstance(n, ast.comprehension) and isinstance(n.target, ast.Name) and isinstance(n.iter, (ast.List, ast.Tuple, ast.Set)) and any(isinstance(e, ast.Name) and e.id in all_os for e in n.iter.elts):
                all_os.add(n.target.id)
    tampered = any((isinstance(n, ast.Attribute) and isinstance(n.ctx, (ast.Store, ast.Del)) and n.attr in {"name", "platform"} and isinstance(n.value, ast.Name) and n.value.id in (all_os | all_sys)) or (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in {"setattr", "delattr"} and len(n.args) >= 2 and isinstance(n.args[1], ast.Constant) and n.args[1].value in {"name", "platform"}) or (isinstance(n, ast.Subscript) and isinstance(n.ctx, (ast.Store, ast.Del)) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name) and n.value.func.id == "globals") for n in ast.walk(tree))
    if tampered:
        pure_os.clear(); pure_sys.clear()  # noqa: E702
    pflags, wflags, visited = set(), set(), []
    for st in tree.body:
        if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name) and top_counts.get(st.targets[0].id) == 1 and st.targets[0].id not in rebound:
            tp, fp = _guard_implications(st.value, frozenset(pure_os), frozenset(pure_sys), frozenset(), frozenset())
            (pflags if tp else (wflags if fp else set())).add(st.targets[0].id)

    def _wexpr(ex: ast.AST | None, sc: str, pos: bool, eos: frozenset[str], esys: frozenset[str], epf: frozenset[str], ewf: frozenset[str]) -> None:
        if ex is None:
            return
        visited.append((ex, sc, pos))
        if isinstance(ex, ast.IfExp):
            tp, fp = _guard_implications(ex.test, eos, esys, epf, ewf)
            _wexpr(ex.test, sc, pos, eos, esys, epf, ewf)
            _wexpr(ex.body, sc, pos or tp, eos, esys, epf, ewf)
            _wexpr(ex.orelse, sc, pos or fp, eos, esys, epf, ewf)
        elif isinstance(ex, ast.Lambda):
            for d in (*ex.args.defaults, *(x for x in ex.args.kw_defaults if x is not None)):
                _wexpr(d, sc, pos, eos, esys, epf, ewf)
            sh = local_bound_names(ex)
            _wexpr(ex.body, sc, False, eos - sh, esys - sh, epf - sh, ewf - sh)
        elif isinstance(ex, _COMPS):
            sh = set(_scope_binding_counts(ex, walk_nested=True))
            cos, csys, cpf, cwf, cpos = eos - sh, esys - sh, epf - sh, ewf - sh, pos
            for idx, g in enumerate(ex.generators):
                _wexpr(g.iter, sc, cpos if idx else pos, cos if idx else eos, csys if idx else esys, cpf if idx else epf, cwf if idx else ewf)
                _wexpr(g.target, sc, cpos, cos, csys, cpf, cwf)
                for cond in g.ifs:
                    tp, _ = _guard_implications(cond, cos, csys, cpf, cwf)
                    _wexpr(cond, sc, cpos, cos, csys, cpf, cwf)
                    cpos = cpos or tp
            for elt in ([ex.key, ex.value] if isinstance(ex, ast.DictComp) else [ex.elt]):
                _wexpr(elt, sc, cpos, cos, csys, cpf, cwf)
        else:
            for ch in ast.iter_child_nodes(ex):
                _wexpr(ch, sc, pos, eos, esys, epf, ewf)

    def _wstmts(stmts: list[ast.stmt], sc: str, pos: bool, eos: frozenset[str], esys: frozenset[str], epf: frozenset[str], ewf: frozenset[str], *, in_loop: bool) -> None:
        cur = pos
        for st in stmts:
            if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for d in (*st.decorator_list, *st.args.defaults, *(x for x in st.args.kw_defaults if x is not None)):
                    _wexpr(d, sc, cur, eos, esys, epf, ewf)
                fc, sh = _scope_binding_counts(st), local_bound_names(st)
                fos, fsys = (set(), set()) if tampered else (set(eos - set(fc)), set(esys - set(fc)))
                if not tampered:
                    for s in st.body:
                        if isinstance(s, ast.Import):
                            for al in s.names:
                                b = al.asname or al.name.split(".", 1)[0]
                                if fc.get(b) == 1 and b not in rebound:
                                    (fos if al.name == "os" else (fsys if al.name == "sys" else set())).add(b)
                _wstmts(st.body, st.name, False, frozenset(fos), frozenset(fsys), epf - sh, ewf - sh, in_loop=False)
            elif isinstance(st, ast.ClassDef):
                for d in (*st.decorator_list, *st.bases, *(kw.value for kw in st.keywords)):
                    _wexpr(d, sc, cur, eos, esys, epf, ewf)
                sh = local_bound_names(st)
                _wstmts(st.body, st.name, cur, eos - sh, esys - sh, epf - sh, ewf - sh, in_loop=False)
            elif isinstance(st, ast.If):
                tp, fp = _guard_implications(st.test, eos, esys, epf, ewf)
                _wexpr(st.test, sc, cur, eos, esys, epf, ewf)
                _wstmts(st.body, sc, cur or tp, eos, esys, epf, ewf, in_loop=in_loop)
                _wstmts(st.orelse, sc, cur or fp, eos, esys, epf, ewf, in_loop=in_loop)
                if (fp and not st.orelse and _exits(st.body, in_loop=in_loop)) or (tp and st.orelse and _exits(st.orelse, in_loop=in_loop)):
                    cur = True
            else:
                loop_next = in_loop or isinstance(st, (ast.For, ast.AsyncFor, ast.While))
                for ch in ast.iter_child_nodes(st):
                    if isinstance(ch, ast.stmt):
                        _wstmts([ch], sc, cur, eos, esys, epf, ewf, in_loop=loop_next and ch in getattr(st, "body", ()))
                    elif isinstance(ch, (ast.ExceptHandler, ast.match_case)):
                        for sub in ast.iter_child_nodes(ch):
                            _wstmts([sub], sc, cur, eos, esys, epf, ewf, in_loop=in_loop) if isinstance(sub, ast.stmt) else _wexpr(sub, sc, cur, eos, esys, epf, ewf)
                    else:
                        _wexpr(ch, sc, cur, eos, esys, epf, ewf)

    _wstmts(tree.body, "<module>", False, frozenset(pure_os), frozenset(pure_sys), frozenset(pflags), frozenset(wflags), in_loop=False)
    return frozenset(all_os), frozenset(all_kills), tampered, visited


def _inspect_pid_safety(path: Path, *, strict_storage: bool) -> list[str]:
    if not strict_storage and any(tag in path.stem.lower() for tag in ("posix", "linux", "systemd", "darwin")): return []  # noqa: E701
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    os_names, kill_names, _, visited = analyze_module_platform_guards(tree)
    cfunc_ids, errors = {id(n.func) for n, _, _ in visited if isinstance(n, ast.Call)}, []
    _is_os = lambda ex: (isinstance(ex, ast.Name) and ex.id in os_names) or (isinstance(ex, ast.Attribute) and ex.attr == "os")
    for node, scope, posix in visited:
        if posix or (not strict_storage and any(tag in scope.lower() for tag in ("posix", "linux", "systemd", "darwin"))): continue  # noqa: E701
        if (isinstance(node, ast.Attribute) and node.attr == "kill" and _is_os(node.value) and id(node) not in cfunc_ids) or (isinstance(node, ast.Name) and node.id in kill_names and isinstance(node.ctx, ast.Load) and id(node) not in cfunc_ids) or (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) >= 2 and _is_os(node.args[0]) and isinstance(node.args[1], ast.Constant) and node.args[1].value == "kill"):
            errors.append(f"in `{scope}` line {node.lineno}: first-class/aliased `.kill` reference outside POSIX guard")
        elif isinstance(node, ast.Call) and ((isinstance(node.func, ast.Name) and node.func.id in kill_names) or (isinstance(node.func, ast.Attribute) and node.func.attr == "kill" and _is_os(node.func.value))):
            s2 = node.args[1] if len(node.args) == 2 and not node.keywords and not isinstance(node.args[0], ast.Starred) else None
            is_zero = any(isinstance(a, ast.Constant) and a.value in (0, False) and type(a.value) in (int, bool) for a in (*node.args[1:], *(kw.value for kw in node.keywords if kw.arg in ("sig", None))))
            if is_zero or (strict_storage and not (s2 is not None and ((isinstance(s2, ast.Constant) and type(s2.value) is int and s2.value != 0) or (isinstance(s2, ast.Attribute) and isinstance(s2.value, ast.Name) and s2.value.id == "signal" and s2.attr.startswith("SIG")) or (isinstance(s2, ast.UnaryOp) and isinstance(s2.op, ast.USub))))):
                errors.append(f"in `{scope}` line {node.lineno}: unguarded `os.kill(pid, 0)` on Windows")
    return errors
def inspect_storage_module_windows_pid_safety(path: Path) -> list[str]: return _inspect_pid_safety(path, strict_storage=True)  # noqa: E704
def inspect_helper_windows_pid_safety(path: Path) -> list[str]: return _inspect_pid_safety(path, strict_storage=False)  # noqa: E704


def inspect_control_plane_torch_npu(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [f"line {s.lineno}: control-plane top-level `import torch_npu` is prohibited" for s in tree.body if (isinstance(s, ast.Import) and any(a.name == "torch_npu" or a.name.startswith("torch_npu.") for a in s.names)) or (isinstance(s, ast.ImportFrom) and (s.module or "").startswith("torch_npu"))]

#!/usr/bin/env python3
"""R4 AST & Guide Static Gate: Zero Pre-Call Session Binding & Silent Default-On Across All Surfaces.

[Role]
Prevents regression of two classes of historical anti-patterns (`P2.7` & `P2.8`):
1. Pre-call host-session / `PreToolUse` nonce / `context_file` fail-closed gates on ANY
   single-user MCP or CLI tool (`remote-dev`, `coordinator`, `profiler`, `sim`, `debugger`,
   `diagnostics`, `npu-top`, and `knowledge_*`).
2. Manual `/mindie-agent` / `$mindie-agent` activation ceremonies, `disable-model-invocation`
   blocks, or install/onboarding documentation inside runtime `skills/`.

[Invariants]
- Pure Python 3.11+ standard library (`ast`, `json`, `pathlib`, `re`).
- Uses structural AST inspection (never fragile line-number regexes) and path-safe command
  token matching (never false-positiving `${PLUGIN_ROOT}/mindie-agent/...` or `/mindie-agent-*`):
  * `harness`: MCP router never marks `request_nonce`, `_mindie_bind_id`, or `context_file`
    required, never hides `knowledge_*` in `list_tools`, and never raises
    `session_identity_required` on `knowledge_*`.
  * `coordinator`: `task_server.py` resolves MCP callers via `_resolve_mcp_caller` (never
    `native_turn_context`), `agent_session.py` provides `ensure_context` and
    `context_for_execution`, and `ops.py` never marks `context_file` required.
  * `mindie-agent-codex`: `mcp_transport.py` and `mcp_gate.py` use optional turn/session
    identity (`optional_turn_identity` / `optional_native_identity`), never fail-closed
    `native_identity` / `native_turn_identity` / `turn_identity`; `openai.yaml` enables
    implicit invocation (`allow_implicit_invocation: true`) without `$mindie-agent`.
  * `mindie-agent-cc`: `scripts/mcp_server.py` falls back to `_CONNECTION_SESSION_ID`
    without fail-closed `claim_bind`.
  * `mindie-agent-kimi`: `scripts/mcp_server.py` never requires `request_nonce`
    (`_nonce_tools(..., require=False)` and no `require_nonce` gate in `handle`), falling
    back to `_CONNECTION_SESSION_ID`.
  * `mindie-agent-agy`: `plugins/mindie-agent/scripts/mcp_server.py` `_resolve_session`
    falls back to `_CONNECTION_SESSION_ID` and never raises fail-closed exceptions.
  * `mindie-agent-wb`: `plugins/mindie-agent/scripts/mcp_server.py` `_resolve_claim`
    falls back to `_CONNECTION_SESSION_ID` without fail-closed raises (allowing `TimeoutError`
    propagation per Principle 14), and no surface passes `require=True`.
  * `mindie-agent-dsh`: `scripts/component_mcp.py` has zero session/nonce gate imports and
    `scripts/knowledge_mcp.py` (when present) exposes tools unconditionally with
    `_CONNECTION_SESSION_ID` fallback and zero `/mindie-agent` gate strings.
  * `mindie-agent-oc`: `plugins/mindie-agent/scripts/mcp_server.py` never injects
    `_mindie_bind_id` and `_resolve_session` falls back to `_CONNECTION_SESSION_ID` without
    uncaught `claim_bind` / `require_session`.
  * Runtime `skills/` & plugin manifests: zero `disable-model-invocation: true`, zero
    user-facing `/mindie-agent` or `$mindie-agent` commands, and zero install docs in `skills/`.

[Timeouts & Locks]
- Pure local file reads and in-memory AST parsing (`< 50ms` across all repositories); zero
  subprocesses, zero network calls, zero file locks.

[Side-Effect Policy]
- Strictly read-only; returns human-actionable error strings.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re
from typing import Mapping, Sequence

from repo_roots import INDEPENDENT_COMPONENTS, INDEPENDENT_PLUGINS, resolve_repo

GATED_REPOS: tuple[str, ...] = (
    "harness",
    "coordinator",
    "mindie-agent-codex",
    "mindie-agent-cc",
    "mindie-agent-kimi",
    "mindie-agent-agy",
    "mindie-agent-wb",
    "mindie-agent-dsh",
    "mindie-agent-oc",
)

_INDEPENDENT_EXEMPT: frozenset[str] = frozenset({*INDEPENDENT_COMPONENTS, *INDEPENDENT_PLUGINS})
# Matches standalone `/mindie-agent`, `/mindie-agent:mindie-agent`, `$mindie-agent`, etc.,
# while never matching `${VAR}/mindie-agent/...`, `plugins/mindie-agent`, or `/mindie-agent-*`.
_SLASH_CMD_RE = re.compile(r"(?<![A-Za-z0-9_./:-])(?<!\})[/\$]mindie-agent(?::mindie-agent)?(?![A-Za-z0-9_./-])")
_DISABLED_MODEL_INVOCATION_RE = re.compile(
    r"(?m)^[ \t]*(?:disable-model-invocation|disableModelInvocation)[ \t]*:[ \t]*true\b"
)


def _parse_ast(
    repo_name: str, repo_dir: Path, rel_path: str, *, strict_files: bool, errors: list[str]
) -> ast.Module | None:
    target = repo_dir / rel_path
    if not target.is_file():
        if strict_files:
            errors.append(f"{repo_name}: missing expected MCP/session boundary file {rel_path}")
        return None
    try:
        return ast.parse(target.read_text(encoding="utf-8"), filename=str(target))
    except SyntaxError as exc:
        errors.append(f"{repo_name}: {rel_path} syntax error during R4 zero-binding AST check: {exc}")
        return None


def _top_functions(tree: ast.AST) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    body = getattr(tree, "body", ())
    return {
        node.name: node
        for node in body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _top_assign_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _called_names(node: ast.AST) -> set[str]:
    called: set[str] = set()
    for item in ast.walk(node):
        if isinstance(item, ast.Call):
            if isinstance(item.func, ast.Name):
                called.add(item.func.id)
            elif isinstance(item.func, ast.Attribute):
                called.add(item.func.attr)
    return called


def _referenced_names(node: ast.AST) -> set[str]:
    return {item.id for item in ast.walk(node) if isinstance(item, ast.Name)}


def _call_keyword_const(func_node: ast.AST, callee_name: str, kw_name: str) -> list[object]:
    values: list[object] = []
    for item in ast.walk(func_node):
        if not isinstance(item, ast.Call):
            continue
        name = item.func.id if isinstance(item.func, ast.Name) else (
            item.func.attr if isinstance(item.func, ast.Attribute) else None
        )
        if name != callee_name:
            continue
        for kw in item.keywords:
            if kw.arg == kw_name and isinstance(kw.value, ast.Constant):
                values.append(kw.value.value)
    return values


def _all_functions(tree: ast.AST) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _is_allowed_reraise(stmt: ast.Raise, *, in_except_handler: bool) -> bool:
    if stmt.exc is None:
        return in_except_handler
    if isinstance(stmt.exc, ast.Name) and stmt.exc.id == "TimeoutError":
        return True
    if isinstance(stmt.exc, ast.Call) and isinstance(stmt.exc.func, ast.Name):
        return stmt.exc.func.id == "TimeoutError"
    return False


def _has_fail_closed_raise(fn_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return True if `fn_node` has an explicit non-`TimeoutError` `raise <Exc>` gate."""

    def _walk_stmts(stmts: Sequence[ast.stmt], *, in_except_handler: bool = False) -> bool:
        for stmt in stmts:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(stmt, ast.Raise):
                if not _is_allowed_reraise(stmt, in_except_handler=in_except_handler):
                    return True
                continue
            if isinstance(stmt, ast.Try):
                for handler in stmt.handlers:
                    if _walk_stmts(handler.body, in_except_handler=True):
                        return True
                if _walk_stmts(stmt.orelse, in_except_handler=in_except_handler):
                    return True
                if _walk_stmts(stmt.finalbody, in_except_handler=in_except_handler):
                    return True
                continue
            for attr in ("body", "orelse", "finalbody"):
                sub = getattr(stmt, attr, None)
                if isinstance(sub, list) and _walk_stmts(sub, in_except_handler=in_except_handler):
                    return True
        return False

    return _walk_stmts(fn_node.body)


def _unconditional_calls(fn_node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Return function/method call names executed unconditionally at function body / `try` body level."""
    names: set[str] = set()

    def _walk_expr(node: ast.AST) -> None:
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
        for child in ast.iter_child_nodes(node):
            _walk_expr(child)

    def _walk_stmts(stmts: Sequence[ast.stmt]) -> None:
        for stmt in stmts:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.If)):
                continue
            if isinstance(stmt, ast.Try):
                _walk_stmts(stmt.body)
                _walk_stmts(stmt.finalbody)
                continue
            _walk_expr(stmt)

    _walk_stmts(fn_node.body)
    return names


def _calls_outside_try(fn_node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Return function/method call names executed outside `try:` blocks."""
    names: set[str] = set()

    def _walk_node(node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node is not fn_node:
            return
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                for st in handler.body:
                    _walk_node(st)
            for st in node.orelse:
                _walk_node(st)
            for st in node.finalbody:
                _walk_node(st)
            return
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
        for child in ast.iter_child_nodes(node):
            _walk_node(child)

    _walk_node(fn_node)
    return names


def _plugin_delegates_mcp_to_harness(repo_dir: Path, scripts_rel: str) -> bool:
    scripts_dir = repo_dir / scripts_rel
    if not scripts_dir.is_dir():
        return False
    for py_path in sorted(scripts_dir.rglob("*.py")):
        if "__pycache__" in py_path.parts:
            continue
        try:
            tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(
                al.name == "mindie_harness" or al.name.startswith("mindie_harness.") for al in node.names
            ):
                return True
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("mindie_harness"):
                return True
    return False


def _check_harness(repo_dir: Path, *, strict_files: bool, errors: list[str]) -> None:
    pkg_dir = repo_dir / "mindie_harness"
    if not pkg_dir.is_dir():
        if strict_files:
            errors.append("harness: missing expected package directory mindie_harness/")
        return
    router_candidates = (
        "mindie_harness/mcp/router.py",
        "mindie_harness/mcp_router.py",
        "mindie_harness/mcp/server.py",
    )
    router_rel = next((rel for rel in router_candidates if (repo_dir / rel).is_file()), None)
    if router_rel is None:
        errors.append(f"harness: missing MCP router module (expected one of {', '.join(router_candidates)})")
        return
    tree = _parse_ast("harness", repo_dir, router_rel, strict_files=True, errors=errors)
    if tree is None:
        return
    for item in ast.walk(tree):
        if isinstance(item, ast.Dict):
            for k, v in zip(item.keys, item.values):
                if isinstance(k, ast.Constant) and k.value == "required" and isinstance(v, (ast.List, ast.Tuple)):
                    req_vals = {elt.value for elt in v.elts if isinstance(elt, ast.Constant)}
                    bad_req = req_vals & {"request_nonce", "_mindie_bind_id", "context_file"}
                    if bad_req:
                        errors.append(
                            f"harness: {router_rel} marks {sorted(bad_req)} as required in MCP schema (violates P2.7)"
                        )
        elif isinstance(item, ast.Constant) and item.value == "session_identity_required":
            errors.append(
                f"harness: {router_rel} enforces fail-closed `session_identity_required` gate (violates silent default-on)"
            )
    router_cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MCPRouter"), None)
    if router_cls is not None:
        list_fn = _top_functions(router_cls).get("list_tools")
        if list_fn is not None and "_verify_knowledge_admission" in _called_names(router_cls):
            errors.append(
                f"harness: {router_rel} `MCPRouter` still calls fail-closed `_verify_knowledge_admission`"
            )


def _check_coordinator(repo_dir: Path, *, strict_files: bool, errors: list[str]) -> None:
    sess_tree = _parse_ast("coordinator", repo_dir, "mindie_coordinator/agent_session.py", strict_files=strict_files, errors=errors)
    srv_tree = _parse_ast("coordinator", repo_dir, "mindie_coordinator/task_server.py", strict_files=strict_files, errors=errors)
    ops_tree = _parse_ast("coordinator", repo_dir, "mindie_coordinator/ops.py", strict_files=strict_files, errors=errors)
    if sess_tree is not None:
        fn_map = _all_functions(sess_tree)
        for required_fn in ("ensure_context", "context_for_execution"):
            if required_fn not in fn_map:
                errors.append(
                    f"coordinator: mindie_coordinator/agent_session.py missing `{required_fn}` "
                    "(on-demand/handle-based task resolution required by Iron Rule 5)"
                )
    if srv_tree is not None:
        fn_map = _top_functions(srv_tree)
        if "_resolve_mcp_caller" not in fn_map:
            errors.append(
                "coordinator: mindie_coordinator/task_server.py missing `_resolve_mcp_caller` "
                "zero-_meta fallback resolver"
            )
        dispatch_fn = fn_map.get("_call_tool") or fn_map.get("_handle_call")
        if dispatch_fn is None:
            errors.append("coordinator: mindie_coordinator/task_server.py missing `_call_tool`")
        else:
            called = _called_names(dispatch_fn)
            if "native_turn_context" in called:
                errors.append(
                    "coordinator: mindie_coordinator/task_server.py `_call_tool` calls strict "
                    "`native_turn_context` (re-introduces pre-call session-binding gate)"
                )
            if "_resolve_mcp_caller" not in called:
                errors.append(
                    "coordinator: mindie_coordinator/task_server.py `_call_tool` must resolve "
                    "MCP callers via `_resolve_mcp_caller` without requiring `_meta`"
                )
    if ops_tree is not None:
        fn_map = _top_functions(ops_tree)
        schema_fn = fn_map.get("task_schema")
        if schema_fn is None:
            errors.append("coordinator: mindie_coordinator/ops.py missing `task_schema`")
        else:
            for item in ast.walk(schema_fn):
                if isinstance(item, ast.Dict):
                    for k, v in zip(item.keys, item.values):
                        if isinstance(k, ast.Constant) and k.value == "required" and isinstance(v, (ast.List, ast.Tuple)):
                            req_vals = {elt.value for elt in v.elts if isinstance(elt, ast.Constant)}
                            if "context_file" in req_vals:
                                errors.append(
                                    "coordinator: mindie_coordinator/ops.py `task_schema` marks `context_file` "
                                    "as required (violates Iron Rule 5)"
                                )


def _check_codex(repo_dir: Path, *, strict_files: bool, errors: list[str]) -> None:
    if not (repo_dir / "plugins/mindie-agent/scripts/mcp_gate.py").is_file() and _plugin_delegates_mcp_to_harness(
        repo_dir, "plugins/mindie-agent/scripts"
    ):
        return
    id_tree = _parse_ast("mindie-agent-codex", repo_dir, "plugins/mindie-agent/scripts/mcp_identity.py", strict_files=strict_files, errors=errors)
    tr_tree = _parse_ast("mindie-agent-codex", repo_dir, "plugins/mindie-agent/scripts/mcp_transport.py", strict_files=strict_files, errors=errors)
    gate_tree = _parse_ast("mindie-agent-codex", repo_dir, "plugins/mindie-agent/scripts/mcp_gate.py", strict_files=strict_files, errors=errors)
    if id_tree is not None:
        fn_map = _top_functions(id_tree)
        for name in ("optional_native_identity", "optional_turn_identity"):
            if name not in fn_map:
                errors.append(f"mindie-agent-codex: mcp_identity.py missing `{name}`")
    if tr_tree is not None:
        tr_called = _called_names(tr_tree)
        strict_tr = tr_called & {"native_identity", "native_turn_identity"}
        if strict_tr or "optional_turn_identity" not in tr_called:
            errors.append(
                "mindie-agent-codex: mcp_transport.py must use `optional_turn_identity` across all MCP surfaces "
                "(never fail-closed `native_identity` / `native_turn_identity`)"
            )
    if gate_tree is not None:
        gate_cls = next((n for n in gate_tree.body if isinstance(n, ast.ClassDef) and n.name == "Gate"), None)
        if gate_cls is None:
            errors.append("mindie-agent-codex: mcp_gate.py missing `Gate`")
        else:
            methods = _top_functions(gate_cls)
            call_fn = methods.get("call")
            remote_fn = methods.get("_remote_call")
            if call_fn is None:
                errors.append("mindie-agent-codex: mcp_gate.py missing `Gate.call`")
            else:
                call_names = _called_names(call_fn)
                if call_names & {"native_identity", "native_turn_identity", "turn_identity"}:
                    errors.append(
                        "mindie-agent-codex: `Gate.call` invokes strict `native_identity` / `native_turn_identity` / "
                        "`turn_identity` (all MCP surfaces must use `optional_native_identity` / `optional_turn_identity`)"
                    )
                if "optional_native_identity" not in call_names and "optional_turn_identity" not in call_names:
                    errors.append(
                        "mindie-agent-codex: `Gate.call` must resolve optional identity via `optional_native_identity`"
                    )
            rem_target = remote_fn or call_fn
            if (
                rem_target is None
                or "optional_turn_identity" not in _called_names(rem_target)
                or bool(_called_names(rem_target) & {"turn_identity", "native_turn_identity"})
            ):
                errors.append("mindie-agent-codex: `Gate` remote path must use `optional_turn_identity` (never strict `turn_identity`)")


def _check_cc(repo_dir: Path, *, strict_files: bool, errors: list[str]) -> None:
    if not (repo_dir / "scripts/mcp_server.py").is_file() and _plugin_delegates_mcp_to_harness(repo_dir, "scripts"):
        return
    tree = _parse_ast("mindie-agent-cc", repo_dir, "scripts/mcp_server.py", strict_files=strict_files, errors=errors)
    if tree is None:
        return
    fn_map = _top_functions(tree)
    if _plugin_delegates_mcp_to_harness(repo_dir, "scripts") and "handle" not in fn_map:
        return
    assigns = _top_assign_names(tree)
    if "_CONNECTION_SESSION_ID" not in assigns:
        errors.append("mindie-agent-cc: scripts/mcp_server.py missing `_CONNECTION_SESSION_ID` fallback")
    handle_fn = fn_map.get("handle")
    if handle_fn is None:
        errors.append("mindie-agent-cc: scripts/mcp_server.py missing `handle`")
        return
    if "claim_bind" in _calls_outside_try(handle_fn):
        errors.append(
            "mindie-agent-cc: `handle` calls uncaught strict `claim_bind` (violates silent default-on zero-binding MCP)"
        )
    refs = set(_referenced_names(handle_fn))
    for callee in _called_names(handle_fn):
        if callee in fn_map:
            refs |= _referenced_names(fn_map[callee])
    if "_CONNECTION_SESSION_ID" not in refs:
        errors.append("mindie-agent-cc: `handle` must fall back to `_CONNECTION_SESSION_ID` across all surfaces")


def _check_kimi(repo_dir: Path, *, strict_files: bool, errors: list[str]) -> None:
    if not (repo_dir / "scripts/mcp_server.py").is_file() and _plugin_delegates_mcp_to_harness(repo_dir, "scripts"):
        return
    tree = _parse_ast("mindie-agent-kimi", repo_dir, "scripts/mcp_server.py", strict_files=strict_files, errors=errors)
    if tree is None:
        return
    fn_map = _top_functions(tree)
    if _plugin_delegates_mcp_to_harness(repo_dir, "scripts") and "handle" not in fn_map:
        return
    assigns = _top_assign_names(tree)
    if "_CONNECTION_SESSION_ID" not in assigns:
        errors.append("mindie-agent-kimi: scripts/mcp_server.py missing `_CONNECTION_SESSION_ID` fallback")
    for fn_name in ("remote_tools", "component_tools", "knowledge_tools"):
        fn = fn_map.get(fn_name)
        if fn is None:
            if fn_name in ("remote_tools", "component_tools"):
                errors.append(f"mindie-agent-kimi: scripts/mcp_server.py missing `{fn_name}`")
            continue
        if "_nonce_tools" in _called_names(fn):
            req_vals = _call_keyword_const(fn, "_nonce_tools", "require")
            if not req_vals or any(v is not False for v in req_vals):
                errors.append(
                    f"mindie-agent-kimi: scripts/mcp_server.py `{fn_name}` must call "
                    "`_nonce_tools(..., require=False)` so `request_nonce` is never required"
                )
    handle_fn = fn_map.get("handle")
    if handle_fn is None:
        errors.append("mindie-agent-kimi: scripts/mcp_server.py missing `handle`")
        return
    if _unconditional_calls(handle_fn) & {"require_nonce", "strip_nonce"}:
        errors.append(
            "mindie-agent-kimi: `handle` calls strict `require_nonce` (violates silent default-on zero-binding MCP)"
        )
    refs = set(_referenced_names(handle_fn))
    for callee in _called_names(handle_fn):
        if callee in fn_map:
            refs |= _referenced_names(fn_map[callee])
    if "_CONNECTION_SESSION_ID" not in refs:
        errors.append("mindie-agent-kimi: `handle` must fall back to `_CONNECTION_SESSION_ID` across all surfaces")


def _check_agy(repo_dir: Path, *, strict_files: bool, errors: list[str]) -> None:
    if not (repo_dir / "plugins/mindie-agent/scripts/mcp_server.py").is_file() and _plugin_delegates_mcp_to_harness(
        repo_dir, "plugins/mindie-agent/scripts"
    ):
        return
    tree = _parse_ast("mindie-agent-agy", repo_dir, "plugins/mindie-agent/scripts/mcp_server.py", strict_files=strict_files, errors=errors)
    if tree is None:
        return
    if _plugin_delegates_mcp_to_harness(repo_dir, "plugins/mindie-agent/scripts") and "_resolve_session" not in _top_functions(tree):
        return
    assigns = _top_assign_names(tree)
    if "_CONNECTION_SESSION_ID" not in assigns:
        errors.append("mindie-agent-agy: mcp_server.py missing `_CONNECTION_SESSION_ID` fallback")
    resolve_fn = _top_functions(tree).get("_resolve_session")
    if resolve_fn is None:
        errors.append("mindie-agent-agy: mcp_server.py missing `_resolve_session`")
        return
    if "_CONNECTION_SESSION_ID" not in _referenced_names(resolve_fn):
        errors.append("mindie-agent-agy: `_resolve_session` must fall back to `_CONNECTION_SESSION_ID`")
    if _has_fail_closed_raise(resolve_fn):
        errors.append(
            "mindie-agent-agy: `_resolve_session` raises fail-closed exception on missing session identity "
            "(violates Iron Rule 5 zero-binding surface)"
        )


def _check_wb(repo_dir: Path, *, strict_files: bool, errors: list[str]) -> None:
    if not (repo_dir / "plugins/mindie-agent/scripts/mcp_server.py").is_file() and _plugin_delegates_mcp_to_harness(
        repo_dir, "plugins/mindie-agent/scripts"
    ):
        return
    tree = _parse_ast("mindie-agent-wb", repo_dir, "plugins/mindie-agent/scripts/mcp_server.py", strict_files=strict_files, errors=errors)
    if tree is None:
        return
    fn_map = _top_functions(tree)
    if _plugin_delegates_mcp_to_harness(repo_dir, "plugins/mindie-agent/scripts") and "_resolve_claim" not in fn_map:
        return
    assigns = _top_assign_names(tree)
    if "_CONNECTION_SESSION_ID" not in assigns:
        errors.append("mindie-agent-wb: mcp_server.py missing `_CONNECTION_SESSION_ID` fallback")
    resolve_fn = fn_map.get("_resolve_claim")
    if resolve_fn is None:
        errors.append("mindie-agent-wb: mcp_server.py missing `_resolve_claim`")
        return
    if "_CONNECTION_SESSION_ID" not in _referenced_names(resolve_fn):
        errors.append("mindie-agent-wb: `_resolve_claim` must fall back to `_CONNECTION_SESSION_ID`")
    if _has_fail_closed_raise(resolve_fn):
        errors.append(
            "mindie-agent-wb: `_resolve_claim` raises fail-closed exception instead of falling back to `_CONNECTION_SESSION_ID`"
        )
    for fn_name in ("call_remote_surface", "call_tools_surface", "call_knowledge_surface"):
        fn = fn_map.get(fn_name)
        if fn is None:
            if fn_name in ("call_remote_surface", "call_tools_surface"):
                errors.append(f"mindie-agent-wb: mcp_server.py missing `{fn_name}`")
            continue
        if True in _call_keyword_const(fn, "_resolve_claim", "require"):
            errors.append(
                f"mindie-agent-wb: `{fn_name}` passes `require=True` to `_resolve_claim` "
                "(re-introduces pre-call session-binding gate)"
            )


def _check_dsh(repo_dir: Path, *, strict_files: bool, errors: list[str]) -> None:
    if not (repo_dir / "scripts/component_mcp.py").is_file() and _plugin_delegates_mcp_to_harness(repo_dir, "scripts"):
        return
    tree = _parse_ast("mindie-agent-dsh", repo_dir, "scripts/component_mcp.py", strict_files=strict_files, errors=errors)
    if tree is not None:
        forbidden = {"claim_bind", "claim_nonce", "require_nonce", "ManagedTaskContextRequired"}
        used = (_called_names(tree) | _referenced_names(tree)) & forbidden
        if used:
            errors.append(
                f"mindie-agent-dsh: scripts/component_mcp.py references session-binding gate symbol(s) {sorted(used)}"
            )
    kmcp_path = repo_dir / "scripts/knowledge_mcp.py"
    if kmcp_path.is_file():
        kmcp_text = kmcp_path.read_text(encoding="utf-8")
        if _SLASH_CMD_RE.search(kmcp_text):
            errors.append(
                "mindie-agent-dsh: scripts/knowledge_mcp.py exposes `/mindie-agent` gate text (violates silent default-on)"
            )
        kmcp_tree = _parse_ast("mindie-agent-dsh", repo_dir, "scripts/knowledge_mcp.py", strict_files=False, errors=errors)
        if kmcp_tree is not None:
            fn_map = _top_functions(kmcp_tree)
            sess_fn = fn_map.get("session_identity")
            if sess_fn is not None and "_CONNECTION_SESSION_ID" not in _referenced_names(sess_fn):
                errors.append(
                    "mindie-agent-dsh: scripts/knowledge_mcp.py `session_identity` raises on missing env session "
                    "instead of falling back to `_CONNECTION_SESSION_ID`"
                )
            disc_fn = fn_map.get("discoverable_tools")
            if disc_fn is not None and "knowledge_lease" in _called_names(disc_fn):
                errors.append(
                    "mindie-agent-dsh: scripts/knowledge_mcp.py `discoverable_tools` hides tools behind `knowledge_lease`"
                )


def _check_oc(repo_dir: Path, *, strict_files: bool, errors: list[str]) -> None:
    """Close AD-01 blindspot: OpenCode MCP tools must never require `_mindie_bind_id` or fail-closed session claims."""
    if not (repo_dir / "plugins/mindie-agent/scripts/mcp_server.py").is_file() and _plugin_delegates_mcp_to_harness(
        repo_dir, "plugins/mindie-agent/scripts"
    ):
        return
    tree = _parse_ast("mindie-agent-oc", repo_dir, "plugins/mindie-agent/scripts/mcp_server.py", strict_files=strict_files, errors=errors)
    if tree is None:
        return
    fn_map = _top_functions(tree)
    if "_with_bind_property" in fn_map or "_with_bind_property" in _called_names(tree):
        errors.append(
            "mindie-agent-oc: mcp_server.py injects `_mindie_bind_id` via `_with_bind_property` (AD-01 / violates P2.7)"
        )
    if _plugin_delegates_mcp_to_harness(repo_dir, "plugins/mindie-agent/scripts") and "_resolve_session" not in fn_map:
        return
    assigns = _top_assign_names(tree)
    if "_CONNECTION_SESSION_ID" not in assigns:
        errors.append("mindie-agent-oc: mcp_server.py missing `_CONNECTION_SESSION_ID` fallback (AD-01 / violates P2.7)")
    resolve_fn = fn_map.get("_resolve_session")
    if resolve_fn is None:
        errors.append("mindie-agent-oc: mcp_server.py missing `_resolve_session`")
        return
    uncaught_calls = _calls_outside_try(resolve_fn)
    if "claim_bind" in uncaught_calls:
        errors.append("mindie-agent-oc: `_resolve_session` calls uncaught fail-closed `claim_bind`")
    if "require_session" in uncaught_calls and "_CONNECTION_SESSION_ID" not in _referenced_names(resolve_fn):
        errors.append(
            "mindie-agent-oc: `_resolve_session` calls strict `require_session` without `_CONNECTION_SESSION_ID` fallback (AD-01)"
        )
    if _has_fail_closed_raise(resolve_fn):
        errors.append("mindie-agent-oc: `_resolve_session` raises fail-closed exception on missing session")
    if "_CONNECTION_SESSION_ID" not in _referenced_names(resolve_fn):
        errors.append("mindie-agent-oc: `_resolve_session` must fall back to `_CONNECTION_SESSION_ID`")


_CHECKERS = {
    "harness": _check_harness,
    "coordinator": _check_coordinator,
    "mindie-agent-codex": _check_codex,
    "mindie-agent-cc": _check_cc,
    "mindie-agent-kimi": _check_kimi,
    "mindie-agent-agy": _check_agy,
    "mindie-agent-wb": _check_wb,
    "mindie-agent-dsh": _check_dsh,
    "mindie-agent-oc": _check_oc,
}

_SKILL_PATHS: tuple[tuple[str, str], ...] = (
    ("mindie-agent-codex", "plugins/mindie-agent/skills/mindie-agent/SKILL.md"),
    ("mindie-agent-cc", "skills/mindie-agent/SKILL.md"),
    ("mindie-agent-kimi", "skills/mindie-agent/SKILL.md"),
    ("mindie-agent-dsh", "skills/mindie-agent/SKILL.md"),
    ("mindie-agent-agy", "plugins/mindie-agent/skills/mindie-agent/SKILL.md"),
    ("mindie-agent-wb", "plugins/mindie-agent/skills/mindie-agent/SKILL.md"),
    ("mindie-agent-oc", "plugins/mindie-agent/skills/mindie-agent/SKILL.md"),
)

_MANIFEST_PATHS: tuple[tuple[str, str], ...] = (
    ("mindie-agent-codex", "plugins/mindie-agent/.codex-plugin/plugin.json"),
    ("mindie-agent-cc", ".claude-plugin/plugin.json"),
    ("mindie-agent-kimi", "kimi.plugin.json"),
    ("mindie-agent-dsh", "package.json"),
    ("mindie-agent-agy", "plugins/mindie-agent/plugin.json"),
    ("mindie-agent-wb", "plugins/mindie-agent/plugin.json"),
    ("mindie-agent-oc", "plugins/mindie-agent/plugin.json"),
    ("mindie-agent-oc", "package.json"),
)

_MANIFEST_TEXT_KEYS: frozenset[str] = frozenset(
    {"description", "shortDescription", "defaultPrompt", "suggestedPrompts", "systemPrompt"}
)

_FORBIDDEN_SKILL_SNIPPETS: tuple[tuple[str, str], ...] = (
    ("Native call identity still applies to plugin tools", "re-introduces pre-call session-binding prompt"),
    ("remote, and components MCP call must include a fresh request_nonce", "requires request_nonce on MCP tools"),
    ("(out_tensor, metrics_dict)", "leaks benchmark-specific verifier tuple signature into production SKILL.md (AD-10)"),
    ("brute-force test capture hashes", "leaks benchmark anti-cheat rule into production SKILL.md (AD-10)"),
    ("Non-Intrusive First-Use Onboarding", "mixes install/onboarding prompts into runtime SKILL.md"),
    ("needs_onboarding_prompt", "mixes install/onboarding prompts into runtime SKILL.md"),
    ("workspace-setup.md", "references install-only workspace setup guide inside runtime SKILL.md"),
    ("github-authentication.md", "references install-only GitHub login guide inside runtime SKILL.md"),
    ("user-notice.md", "references install-only consent notice inside runtime SKILL.md"),
    ("starred/mindie-agent", "mixes install-time GitHub star prompt into runtime SKILL.md"),
    ("Manually enable MindIE knowledge", "re-introduces manual activation prompt in silent default-on SKILL.md"),
)

_FORBIDDEN_SKILL_FILES: frozenset[str] = frozenset(
    {"workspace-setup.md", "github-authentication.md", "user-notice.md"}
)


def _extract_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---\n", 4)
    return text[4:end] if end != -1 else ""


def _iter_manifest_text_values(obj: object) -> list[str]:
    found: list[str] = []
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            if k in _MANIFEST_TEXT_KEYS:
                if isinstance(v, str):
                    found.append(v)
                elif isinstance(v, list):
                    found.extend(item for item in v if isinstance(item, str))
            else:
                found.extend(_iter_manifest_text_values(v))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_iter_manifest_text_values(item))
    return found


def _check_prompt_and_guide_hygiene(
    siblings_roots: Sequence[Path],
    explicit_repos: Mapping[str, Path] | None,
    strict_repos: set[str],
    errors: list[str],
) -> None:
    for repo_name, rel_skill in _SKILL_PATHS:
        repo_dir = resolve_repo(repo_name, siblings_roots, explicit_repos=explicit_repos)
        if repo_dir is None:
            continue
        skill_file = repo_dir / rel_skill
        if not skill_file.is_file():
            if repo_name in strict_repos:
                errors.append(f"{repo_name}: missing expected runtime skill file {rel_skill}")
            continue
        text = skill_file.read_text(encoding="utf-8")
        fm = _extract_frontmatter(text)
        if not fm:
            errors.append(f"{repo_name}: {rel_skill} missing valid `---` YAML frontmatter")
        for fm_line in fm.splitlines():
            stripped = fm_line.strip()
            if not stripped or stripped.startswith("#") or ":" not in stripped:
                continue
            _key, raw_val = stripped.split(":", 1)
            val = raw_val.strip()
            if val and not val.startswith(('"', "'", "|", ">", "[", "{")) and ": " in val:
                errors.append(
                    f"{repo_name}: {rel_skill} YAML frontmatter has unquoted `: ` in scalar `{_key.strip()}` "
                    "(invalid YAML; wrap in quotes)"
                )
        if _DISABLED_MODEL_INVOCATION_RE.search(fm):
            errors.append(
                f"{repo_name}: {rel_skill} sets `disable-model-invocation: true` / `disableModelInvocation: true` "
                "(violates silent default-on skill routing)"
            )
        for child in sorted(skill_file.parent.rglob("*.md")):
            rel_child = child.relative_to(repo_dir).as_posix()
            if child.name in _FORBIDDEN_SKILL_FILES:
                errors.append(
                    f"{repo_name}: {rel_child} places installation/onboarding documentation inside runtime `skills/` directory"
                )
                continue
            child_text = text if child == skill_file else child.read_text(encoding="utf-8")
            for snippet, reason in _FORBIDDEN_SKILL_SNIPPETS:
                if snippet in child_text:
                    errors.append(f"{repo_name}: {rel_child} contains `{snippet}` ({reason})")
            if _SLASH_CMD_RE.search(child_text):
                errors.append(
                    f"{repo_name}: {rel_child} exposes `/mindie-agent` or `$mindie-agent` command "
                    "(violates silent default-on invariant)"
                )
    codex_dir = resolve_repo("mindie-agent-codex", siblings_roots, explicit_repos=explicit_repos)
    if codex_dir is not None:
        openai_yaml = codex_dir / "plugins/mindie-agent/skills/mindie-agent/agents/openai.yaml"
        if openai_yaml.is_file():
            yaml_text = openai_yaml.read_text(encoding="utf-8")
            if re.search(r"(?m)^[ \t]*allow_implicit_invocation[ \t]*:[ \t]*false\b", yaml_text):
                errors.append("mindie-agent-codex: agents/openai.yaml sets `allow_implicit_invocation: false` (violates silent default-on)")
            if _SLASH_CMD_RE.search(yaml_text):
                errors.append("mindie-agent-codex: agents/openai.yaml exposes `/mindie-agent` or `$mindie-agent`")
    for repo_name, rel_manifest in _MANIFEST_PATHS:
        m_repo = resolve_repo(repo_name, siblings_roots, explicit_repos=explicit_repos)
        if m_repo is None or not (m_repo / rel_manifest).is_file():
            continue
        raw_manifest = (m_repo / rel_manifest).read_text(encoding="utf-8")
        if repo_name == "mindie-agent-kimi" and (
            "MindIE tools use a fresh request_nonce" in raw_manifest
            or "fresh PreToolUse-bound request_nonce" in raw_manifest
        ):
            errors.append("mindie-agent-kimi: kimi.plugin.json systemPrompt mandates request_nonce on MindIE tools")
        try:
            parsed_manifest = json.loads(raw_manifest)
        except ValueError:
            continue
        for val in _iter_manifest_text_values(parsed_manifest):
            if _SLASH_CMD_RE.search(val):
                errors.append(f"{repo_name}: {rel_manifest} exposes `/mindie-agent` or `$mindie-agent` command")
                break
    diag_dir = resolve_repo("diagnostics", siblings_roots, explicit_repos=explicit_repos)
    if diag_dir is not None and (diag_dir / "AGENTS.md").is_file():
        if "Can be vendored as a single file" in (diag_dir / "AGENTS.md").read_text(encoding="utf-8"):
            errors.append("diagnostics: AGENTS.md encourages single-file vendoring of fallback.py (violates Iron Rule 3)")
    npu_top_dir = resolve_repo("npu-top", siblings_roots, explicit_repos=explicit_repos)
    if npu_top_dir is not None and (npu_top_dir / ".agents/skills/vaws-top").exists():
        errors.append("npu-top: legacy `.agents/skills/vaws-top` directory still present (violates Principle 1)")


def verify_zero_session_binding_gates(
    siblings_roots: Sequence[Path],
    *,
    require_siblings: bool = False,
    required_repos: Sequence[str] = (),
    explicit_repos: Mapping[str, Path] | None = None,
) -> list[str]:
    """Verify Iron Rule 5 & silent default-on boundaries across sibling repos."""
    errors: list[str] = []
    must_exist = set(required_repos)
    strict_repos: set[str] = set()
    for repo_name in GATED_REPOS:
        try:
            repo_dir = resolve_repo(repo_name, siblings_roots, explicit_repos=explicit_repos)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        strict_files = (repo_name in must_exist) or (require_siblings and repo_name not in _INDEPENDENT_EXEMPT)
        if strict_files:
            strict_repos.add(repo_name)
        if repo_dir is None:
            if strict_files:
                errors.append(
                    f"{repo_name}: sibling checkout not found in {list(siblings_roots)} for zero-binding gate verification"
                )
            continue
        _CHECKERS[repo_name](repo_dir, strict_files=strict_files, errors=errors)
    _check_prompt_and_guide_hygiene(siblings_roots, explicit_repos, strict_repos, errors)
    return errors

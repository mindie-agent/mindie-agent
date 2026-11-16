#!/usr/bin/env python3
"""AST gate enforcing zero pre-call session-binding gates on deterministic tools (R4 / Iron Rule 5 / P2.7).

[Role]
Verifies across `coordinator` and all host plugins (`codex`, `cc`, `kimi`, `agy`, `wb`, `dsh`)
that deterministic MCP/CLI surfaces (`remote`, `components`/`tools`, and `coordinator`) never
enforce mandatory pre-call chat-session identity, `PreToolUse` SQLite nonces/binds, or
`context_file` gates—while preserving strict session/consent admission on `knowledge` (`P2.1`).

[Invariants]
- Deterministic surfaces execute over standard JSON-RPC `tools/call` with zero `_meta`, zero
  `PreToolUse` hooks, zero required `request_nonce`/`context_file` schema fields, and connection
  or auto-attached fallbacks when host metadata is absent.
- `knowledge` surfaces retain strict native session identity (`native_identity`, `claim_bind`,
  `require=True` / `require_nonce`) so Passive Default (`P2.1`) is never weakened.
- Runs purely on Python stdlib (`ast`, `pathlib`) before `mindie_knowledge` import checks.

[Timeouts & Locks]
- Pure synchronous local AST parsing (`< 20ms`) with zero subprocesses, network I/O, or locks.

[Side-Effect Policy]
- Strictly read-only static inspection of repository checkouts.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Sequence

GATED_REPOS: tuple[str, ...] = (
    "coordinator",
    "mindie-agent-codex",
    "mindie-agent-cc",
    "mindie-agent-kimi",
    "mindie-agent-agy",
    "mindie-agent-wb",
    "mindie-agent-dsh",
)


def _resolve_repo(repo_name: str, siblings_roots: Sequence[Path]) -> Path | None:
    for root in siblings_roots:
        candidate = Path(root) / repo_name
        if (candidate / ".git").exists():
            return candidate
    return None


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


def _top_functions(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    return {
        node.name: node
        for node in tree.body
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
                if isinstance(item, ast.Constant) and item.value == "context_file":
                    continue
                if isinstance(item, ast.Dict):
                    for k, v in zip(item.keys, item.values):
                        if isinstance(k, ast.Constant) and k.value == "required" and isinstance(v, (ast.List, ast.Tuple)):
                            req_vals = {elt.value for elt in v.elts if isinstance(elt, ast.Constant)}
                            if "context_file" in req_vals:
                                errors.append(
                                    "coordinator: mindie_coordinator/ops.py `task_schema` marks `context_file` "
                                    "as required (violates Iron Rule 5)"
                                )


def _is_surface_var(node: ast.AST) -> bool:
    if isinstance(node, ast.Name) and node.id == "surface":
        return True
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
        and node.attr == "surface"
    )


def _is_surface_eq(test: ast.AST, target_surface: str) -> bool:
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return False
    left, right = test.left, test.comparators[0]
    if _is_surface_var(left) and isinstance(right, ast.Constant) and right.value == target_surface:
        return True
    if _is_surface_var(right) and isinstance(left, ast.Constant) and left.value == target_surface:
        return True
    return False


def _stmts_called_names(stmts: Sequence[ast.stmt]) -> set[str]:
    out: set[str] = set()
    for stmt in stmts:
        out |= _called_names(stmt)
    return out


def _stmts_referenced_names(stmts: Sequence[ast.stmt]) -> set[str]:
    out: set[str] = set()
    for stmt in stmts:
        out |= _referenced_names(stmt)
    return out


def _surface_eq_branches(node: ast.AST, target_surface: str) -> list[tuple[list[ast.stmt], list[ast.stmt]]]:
    return [
        (item.body, item.orelse)
        for item in ast.walk(node)
        if isinstance(item, ast.If) and _is_surface_eq(item.test, target_surface)
    ]


def _check_codex(repo_dir: Path, *, strict_files: bool, errors: list[str]) -> None:
    id_tree = _parse_ast("mindie-agent-codex", repo_dir, "plugins/mindie-agent/scripts/mcp_identity.py", strict_files=strict_files, errors=errors)
    tr_tree = _parse_ast("mindie-agent-codex", repo_dir, "plugins/mindie-agent/scripts/mcp_transport.py", strict_files=strict_files, errors=errors)
    gate_tree = _parse_ast("mindie-agent-codex", repo_dir, "plugins/mindie-agent/scripts/mcp_gate.py", strict_files=strict_files, errors=errors)
    if id_tree is not None:
        fn_map = _top_functions(id_tree)
        for name in ("native_identity", "optional_native_identity", "optional_turn_identity"):
            if name not in fn_map:
                errors.append(f"mindie-agent-codex: mcp_identity.py missing `{name}`")
    if tr_tree is not None:
        branches = _surface_eq_branches(tr_tree, "knowledge")
        branches += [
            ([node.body], [node.orelse])  # type: ignore[list-item]
            for node in ast.walk(tr_tree)
            if isinstance(node, ast.IfExp) and _is_surface_eq(node.test, "knowledge")
        ]
        strict = {"native_identity", "native_turn_identity"}
        if not any(
            (_stmts_called_names(body) & strict)
            and "optional_turn_identity" not in _stmts_called_names(body)
            and "optional_turn_identity" in _stmts_called_names(other)
            and not (_stmts_called_names(other) & strict)
            for body, other in branches
        ):
            errors.append(
                "mindie-agent-codex: mcp_transport.py must branch `surface == 'knowledge'` to strict turn identity and deterministic surfaces to `optional_turn_identity`"
            )
    if gate_tree is not None:
        gate_cls = next(
            (n for n in gate_tree.body if isinstance(n, ast.ClassDef) and n.name == "Gate"),
            None,
        )
        if gate_cls is None:
            errors.append("mindie-agent-codex: mcp_gate.py missing `Gate`")
        else:
            methods = _top_functions(gate_cls)  # type: ignore[arg-type]
            call_fn = methods.get("call")
            remote_fn = methods.get("_remote_call")
            if call_fn is None:
                errors.append("mindie-agent-codex: mcp_gate.py missing `Gate.call`")
            else:
                comp_branches = _surface_eq_branches(call_fn, "components")
                know_branches = _surface_eq_branches(call_fn, "knowledge")
                comp_ok = any(
                    "optional_native_identity" in _stmts_called_names(body)
                    and "native_identity" not in _stmts_called_names(body)
                    for body, _ in comp_branches
                )
                if not comp_ok:
                    errors.append(
                        "mindie-agent-codex: `Gate.call` `components` branch must use `optional_native_identity` (never strict `native_identity`)"
                    )
                if know_branches:
                    know_ok = any(
                        "native_identity" in _stmts_called_names(body)
                        and "optional_native_identity" not in _stmts_called_names(body)
                        for body, _ in know_branches
                    )
                else:
                    know_ok = "native_identity" in _called_names(call_fn)
                if not know_ok:
                    errors.append("mindie-agent-codex: `Gate.call` `knowledge` path must enforce strict `native_identity`")
            rem_target = remote_fn or call_fn
            if rem_target is None or "optional_turn_identity" not in _called_names(rem_target) or "turn_identity" in _called_names(rem_target):
                errors.append("mindie-agent-codex: `Gate` remote path must use `optional_turn_identity` (never strict `turn_identity`)")


def _check_cc(repo_dir: Path, *, strict_files: bool, errors: list[str]) -> None:
    tree = _parse_ast("mindie-agent-cc", repo_dir, "scripts/mcp_server.py", strict_files=strict_files, errors=errors)
    if tree is None:
        return
    assigns = _top_assign_names(tree)
    if "_CONNECTION_SESSION_ID" not in assigns:
        errors.append("mindie-agent-cc: scripts/mcp_server.py missing `_CONNECTION_SESSION_ID` fallback")
    handle_fn = _top_functions(tree).get("handle")
    if handle_fn is None:
        errors.append("mindie-agent-cc: scripts/mcp_server.py missing `handle`")
        return
    branches = _surface_eq_branches(handle_fn, "knowledge")
    valid = any(
        "claim_bind" in _stmts_called_names(body)
        and "_CONNECTION_SESSION_ID" not in _stmts_referenced_names(body)
        and "_CONNECTION_SESSION_ID" in _stmts_referenced_names(orelse)
        for body, orelse in branches
    )
    if not valid:
        errors.append(
            "mindie-agent-cc: `handle` must branch on `surface == 'knowledge'` with strict `claim_bind` "
            "(no `_CONNECTION_SESSION_ID` fallback) and fall back to `_CONNECTION_SESSION_ID` on deterministic surfaces"
        )


def _check_kimi(repo_dir: Path, *, strict_files: bool, errors: list[str]) -> None:
    tree = _parse_ast("mindie-agent-kimi", repo_dir, "scripts/mcp_server.py", strict_files=strict_files, errors=errors)
    if tree is None:
        return
    assigns = _top_assign_names(tree)
    if "_CONNECTION_SESSION_ID" not in assigns:
        errors.append("mindie-agent-kimi: scripts/mcp_server.py missing `_CONNECTION_SESSION_ID` fallback")
    fn_map = _top_functions(tree)
    for det_fn_name in ("remote_tools", "component_tools"):
        det_fn = fn_map.get(det_fn_name)
        if det_fn is None:
            errors.append(f"mindie-agent-kimi: scripts/mcp_server.py missing `{det_fn_name}`")
            continue
        req_vals = _call_keyword_const(det_fn, "_nonce_tools", "require")
        if req_vals != [False]:
            errors.append(
                f"mindie-agent-kimi: scripts/mcp_server.py `{det_fn_name}` must call "
                "`_nonce_tools(..., require=False)` so `request_nonce` is never required on deterministic tools"
            )
    handle_fn = fn_map.get("handle")
    if handle_fn is None:
        errors.append("mindie-agent-kimi: scripts/mcp_server.py missing `handle`")
        return
    branches = _surface_eq_branches(handle_fn, "knowledge")
    valid = any(
        {"require_nonce", "claim_nonce"} <= _stmts_called_names(body)
        and "_CONNECTION_SESSION_ID" not in _stmts_referenced_names(body)
        and "_CONNECTION_SESSION_ID" in _stmts_referenced_names(orelse)
        for body, orelse in branches
    )
    if not valid:
        errors.append(
            "mindie-agent-kimi: `handle` must branch on `surface == 'knowledge'` with strict `require_nonce` + `claim_nonce` "
            "and fall back to `_CONNECTION_SESSION_ID` on deterministic surfaces"
        )


def _check_agy(repo_dir: Path, *, strict_files: bool, errors: list[str]) -> None:
    tree = _parse_ast("mindie-agent-agy", repo_dir, "plugins/mindie-agent/scripts/mcp_server.py", strict_files=strict_files, errors=errors)
    if tree is None:
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
    for item in ast.walk(resolve_fn):
        if isinstance(item, ast.Raise) and item.exc is not None:
            if isinstance(item.exc, ast.Call) and isinstance(item.exc.func, ast.Name) and item.exc.func.id == "RuntimeError":
                errors.append(
                    "mindie-agent-agy: `_resolve_session` raises `RuntimeError` on missing session identity "
                    "(violates Iron Rule 5 zero-binding deterministic surface)"
                )


def _has_knowledge_guard(resolve_fn: ast.AST) -> bool:
    for body, _ in _surface_eq_branches(resolve_fn, "knowledge"):
        if any(isinstance(n, ast.Raise) for n in body) and "_CONNECTION_SESSION_ID" not in _stmts_referenced_names(body):
            return True
    return False


def _check_wb(repo_dir: Path, *, strict_files: bool, errors: list[str]) -> None:
    tree = _parse_ast("mindie-agent-wb", repo_dir, "plugins/mindie-agent/scripts/mcp_server.py", strict_files=strict_files, errors=errors)
    if tree is None:
        return
    assigns = _top_assign_names(tree)
    if "_CONNECTION_SESSION_ID" not in assigns:
        errors.append("mindie-agent-wb: mcp_server.py missing `_CONNECTION_SESSION_ID` fallback")
    fn_map = _top_functions(tree)
    resolve_fn = fn_map.get("_resolve_claim")
    if resolve_fn is None:
        errors.append("mindie-agent-wb: mcp_server.py missing `_resolve_claim`")
        return
    if "_CONNECTION_SESSION_ID" not in _referenced_names(resolve_fn):
        errors.append("mindie-agent-wb: `_resolve_claim` must fall back to `_CONNECTION_SESSION_ID` on deterministic surfaces")
    for det_fn_name in ("call_remote_surface", "call_tools_surface"):
        det_fn = fn_map.get(det_fn_name)
        if det_fn is None:
            errors.append(f"mindie-agent-wb: mcp_server.py missing `{det_fn_name}`")
            continue
        if True in _call_keyword_const(det_fn, "_resolve_claim", "require"):
            errors.append(
                f"mindie-agent-wb: `{det_fn_name}` passes `require=True` to `_resolve_claim` "
                "(re-introduces pre-call session-binding gate on deterministic surface)"
            )
    know_fn = fn_map.get("call_knowledge_surface")
    know_guarded = know_fn is not None and (
        _call_keyword_const(know_fn, "_resolve_claim", "require") == [True]
        or (_has_knowledge_guard(resolve_fn) and "_resolve_claim" in _called_names(know_fn))
    )
    if not know_guarded:
        errors.append(
            "mindie-agent-wb: `call_knowledge_surface` / `_resolve_claim` must strictly fail closed on `knowledge`"
        )


def _check_dsh(repo_dir: Path, *, strict_files: bool, errors: list[str]) -> None:
    tree = _parse_ast("mindie-agent-dsh", repo_dir, "scripts/component_mcp.py", strict_files=strict_files, errors=errors)
    if tree is None:
        return
    forbidden = {"claim_bind", "claim_nonce", "require_nonce", "ManagedTaskContextRequired"}
    used = (_called_names(tree) | _referenced_names(tree)) & forbidden
    if used:
        errors.append(
            f"mindie-agent-dsh: scripts/component_mcp.py references session-binding gate symbol(s) {sorted(used)}"
        )


_CHECKERS = {
    "coordinator": _check_coordinator,
    "mindie-agent-codex": _check_codex,
    "mindie-agent-cc": _check_cc,
    "mindie-agent-kimi": _check_kimi,
    "mindie-agent-agy": _check_agy,
    "mindie-agent-wb": _check_wb,
    "mindie-agent-dsh": _check_dsh,
}


_SKILL_PATHS: tuple[tuple[str, str], ...] = (
    ("mindie-agent-codex", "plugins/mindie-agent/skills/mindie-agent/SKILL.md"),
    ("mindie-agent-cc", "skills/mindie-agent/SKILL.md"),
    ("mindie-agent-kimi", "skills/mindie-agent/SKILL.md"),
    ("mindie-agent-dsh", "skills/mindie-agent/SKILL.md"),
    ("mindie-agent-agy", "plugins/mindie-agent/skills/mindie-agent/SKILL.md"),
    ("mindie-agent-wb", "plugins/mindie-agent/skills/mindie-agent/SKILL.md"),
)

_FORBIDDEN_SKILL_SNIPPETS: tuple[tuple[str, str], ...] = (
    ("Native call identity still applies to plugin tools", "re-introduces pre-call session-binding prompt"),
    ("remote, and components MCP call must include a fresh request_nonce", "requires request_nonce on deterministic tools"),
    ("(out_tensor, metrics_dict)", "leaks benchmark-specific verifier tuple signature into production SKILL.md (Principle 10)"),
    ("brute-force test capture hashes", "leaks benchmark anti-cheat rule into production SKILL.md (Principle 10)"),
)


def _check_prompt_and_guide_hygiene(siblings_roots: Sequence[Path], errors: list[str]) -> None:
    for repo_name, rel_skill in _SKILL_PATHS:
        repo_dir = _resolve_repo(repo_name, siblings_roots)
        if repo_dir is None or not (repo_dir / rel_skill).is_file():
            continue
        text = (repo_dir / rel_skill).read_text(encoding="utf-8")
        for snippet, reason in _FORBIDDEN_SKILL_SNIPPETS:
            if snippet in text:
                errors.append(f"{repo_name}: {rel_skill} contains `{snippet}` ({reason})")
    kimi_dir = _resolve_repo("mindie-agent-kimi", siblings_roots)
    if kimi_dir is not None and (kimi_dir / "kimi.plugin.json").is_file():
        manifest_text = (kimi_dir / "kimi.plugin.json").read_text(encoding="utf-8")
        if "MindIE tools use a fresh request_nonce" in manifest_text:
            errors.append("mindie-agent-kimi: kimi.plugin.json systemPrompt mandates request_nonce on all MindIE tools")
    diag_dir = _resolve_repo("diagnostics", siblings_roots)
    if diag_dir is not None and (diag_dir / "AGENTS.md").is_file():
        if "Can be vendored as a single file" in (diag_dir / "AGENTS.md").read_text(encoding="utf-8"):
            errors.append("diagnostics: AGENTS.md encourages single-file vendoring of fallback.py (violates Iron Rule 3)")
    npu_top_dir = _resolve_repo("npu-top", siblings_roots)
    if npu_top_dir is not None and (npu_top_dir / ".agents/skills/vaws-top").exists():
        errors.append("npu-top: legacy `.agents/skills/vaws-top` directory still present (violates Principle 1)")


def verify_zero_session_binding_gates(
    siblings_roots: Sequence[Path],
    *,
    require_siblings: bool = False,
    required_repos: Sequence[str] = (),
) -> list[str]:
    """Verify Iron Rule 5 (zero pre-call session-binding gates on deterministic surfaces) across sibling repos."""
    errors: list[str] = []
    must_exist = set(required_repos)
    for repo_name in GATED_REPOS:
        repo_dir = _resolve_repo(repo_name, siblings_roots)
        strict_files = require_siblings or (repo_name in must_exist)
        if repo_dir is None:
            if strict_files:
                errors.append(
                    f"{repo_name}: sibling checkout not found in {list(siblings_roots)} for zero-binding gate verification"
                )
            continue
        _CHECKERS[repo_name](repo_dir, strict_files=strict_files, errors=errors)
    _check_prompt_and_guide_hygiene(siblings_roots, errors)
    return errors

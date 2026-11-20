#!/usr/bin/env python3
"""Focused AST & lexical Windows zero-console-popup boundary gate (R4 / P1.5 / AD-08).
[Role] Verifies across all MindIE Agent repos that Node.js child-process calls pass `windowsHide: true`
without unconditional `detached: true`, and Python launches enforce `CREATE_NO_WINDOW` while banning
`CREATE_NEW_CONSOLE` and `DETACHED_PROCESS`.
[Invariants] Masks JS comments/strings/interpolated templates/regexes; honors `--repo` overrides.
[Timeouts & Locks] Pure synchronous in-memory parsing; zero subprocesses, network I/O, or locks.
[Side-Effect Policy] Strictly read-only static inspection of repository checkouts.
"""
from __future__ import annotations
import ast
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from repo_roots import ALL_PLUGINS, INDEPENDENT_COMPONENTS, INDEPENDENT_PLUGINS, resolve_repo
from storage_lifecycle_gate import THIN_HOST_PLUGIN_FLOOR_VERSIONS, _parse_repo_semver
from storage_pid_ast import analyze_module_platform_guards

WINDOWS_NODE_WINDOWLESS_FILES: tuple[tuple[str, str], ...] = (("mindie-agent-dsh", "host3.mjs"), ("mindie-agent-oc", "plugins/mindie-agent/opencode_host.mjs"))
NODE_SCANNED_REPOS: tuple[str, ...] = ("mindie-agent-dsh", "mindie-agent-oc", "npu-top")
NODE_SKIP_DIRS: frozenset[str] = frozenset({".git", "node_modules", "tests", ".venv", "dist", "build", "coverage", "static"})

WINDOWS_NO_WINDOW_REQUIRED_FILES: tuple[tuple[str, str | tuple[str, ...]], ...] = (
    ("mindie-agent-codex", ("any", ("plugins/mindie-agent/scripts/windows_process.py", "plugins/mindie-agent/scripts/with_runtime.py", "plugins/mindie-agent/scripts/hook_launcher.py", "plugins/mindie-agent/scripts/mcp_entry.py", "plugins/mindie-agent/scripts/entry.py", "plugins/mindie-agent/scripts/host_adapter.py", "plugins/mindie-agent/scripts/setup.py"))),
    ("mindie-agent-cc", ("any", ("scripts/bounded_win32.py", "scripts/mindie_launch.py", "scripts/hook_launcher.py", "scripts/entry.py", "scripts/bridge.py", "scripts/host_adapter.py", "scripts/setup.py"))),
    ("mindie-agent-kimi", ("any", ("scripts/bounded.py", "scripts/mindie_launch.py", "scripts/hook_launcher.py", "scripts/entry.py", "scripts/bridge.py", "scripts/host_adapter.py", "scripts/setup.py"))),
    ("mindie-agent-dsh", ("any", ("scripts/setup_process.py", "scripts/knowledge_mcp.py", "scripts/mindie_launch.py", "scripts/hook_launcher.py", "scripts/entry.py", "scripts/bridge.py", "scripts/host_adapter.py", "scripts/setup.py"))),
    ("mindie-agent-agy", ("any", ("plugins/mindie-agent/scripts/bounded.py", "plugins/mindie-agent/scripts/component_update.py", "plugins/mindie-agent/scripts/mindie_launch.py", "plugins/mindie-agent/scripts/bridge.py", "plugins/mindie-agent/scripts/entry.py", "plugins/mindie-agent/scripts/host_adapter.py", "plugins/mindie-agent/scripts/setup.py"))),
    ("mindie-agent-wb", ("any", ("plugins/mindie-agent/scripts/bounded.py", "plugins/mindie-agent/scripts/component_update.py", "plugins/mindie-agent/scripts/mindie_launch.py", "plugins/mindie-agent/scripts/bridge.py", "plugins/mindie-agent/scripts/entry.py", "plugins/mindie-agent/scripts/host_adapter.py", "plugins/mindie-agent/scripts/setup.py"))),
    ("mindie-agent-oc", ("any", ("plugins/mindie-agent/scripts/bounded.py", "plugins/mindie-agent/scripts/mindie_launch.py", "plugins/mindie-agent/scripts/bridge.py", "plugins/mindie-agent/scripts/entry.py", "plugins/mindie-agent/scripts/host_adapter.py", "plugins/mindie-agent/scripts/setup.py"))),
    ("mindie-bench", ("src/mindie_bench/runner/host_platform.py", "src/mindie_bench/runner/process.py")), ("knowledge", "mindie_knowledge/windows_process.py"),
    ("diagnostics", "mindie_diagnostics/platform_service.py"), ("remote-dev", "remote_dev/core/local_process.py"),
    ("diagnostics", ("mindie_diagnostics/github_transport.py", "mindie_diagnostics/reporter.py")), ("coordinator", "mindie_coordinator/service_client.py"),
)
WINDOWS_NO_WINDOW_COMPANION_FILES: tuple[tuple[str, str], ...] = (
    ("harness", "mindie_harness/process/win32.py"), ("harness", "mindie_harness/bootstrap/seed_main.py"), ("knowledge", "mindie_knowledge/loop/process.py"),
    ("mindie-bench", "src/mindie_bench/runner/termination.py"), ("diagnostics", "mindie_diagnostics/reporting_commands.py"), ("diagnostics", "mindie_diagnostics/reporting_runtime.py"),
)
_FLAG_SCOPES: tuple[tuple[str, str], ...] = (
    ("harness", "mindie_harness"), ("debugger", "mindie_debugger"), ("npu-top", "npu_top"), ("knowledge", "mindie_knowledge"), ("diagnostics", "mindie_diagnostics"),
    ("remote-dev", "remote_dev"), ("coordinator", "mindie_coordinator"), ("mindie-bench", "src/mindie_bench"), ("mindie-agent-codex", "plugins/mindie-agent/scripts"),
    ("mindie-agent-cc", "scripts"), ("mindie-agent-kimi", "scripts"), ("mindie-agent-dsh", "scripts"), ("mindie-agent-agy", "plugins/mindie-agent/scripts"),
    ("mindie-agent-wb", "plugins/mindie-agent/scripts"), ("mindie-agent-oc", "plugins/mindie-agent/scripts"),
)
INDEPENDENT_ONLY_GATED_REPOS: frozenset[str] = frozenset({*INDEPENDENT_COMPONENTS, *INDEPENDENT_PLUGINS})
_PY_SPAWN_ATTRS: frozenset[str] = frozenset({"Popen", "run", "call", "check_call", "check_output"})
_BANNED_WIN_FLAGS: frozenset[str] = frozenset({"CREATE_NEW_CONSOLE", "DETACHED_PROCESS"})
_JS_RX_KW: frozenset[str] = frozenset({"return", "throw", "case", "typeof", "void", "delete", "in", "instanceof", "new", "await", "yield", "of"})
_JS_RX_CH: frozenset[str] = frozenset("=(,[{:;!&|?+-~^%<>")
_JS_CALL_RE = re.compile(r"(?:(?<!\.)\b(?:spawn|spawnSync|exec|execSync|execFile|execFileSync|fork)|\b(?:child_process|cp)\.(?:spawn|spawnSync|exec|execSync|execFile|execFileSync|fork))\s*\(")
_MANIFEST_JSON_NAMES: frozenset[str] = frozenset(
    {".mcp.json", "mcp.json", "mcp_config.json", "hooks.json", "kimi.plugin.json", "plugin.json"}
)
_MANIFEST_SKIP_DIRS: frozenset[str] = frozenset(
    {"tests", "test", "docs", "node_modules", "dist", "build", ".git", ".venv", ".uv-cache", ".cache", ".local", ".mindie-local", ".tox", ".nox"}
)
_BARE_PYTHON_NAMES: frozenset[str] = frozenset(
    {"python", "python3", "python.exe", "python3.exe", "pythonw", "pythonw.exe"}
)
_PS_BINARIES: frozenset[str] = frozenset({"powershell", "powershell.exe", "pwsh", "pwsh.exe"})
_PS_VALUE_FLAGS: frozenset[str] = frozenset(
    {"-executionpolicy", "-ep", "-windowstyle", "-w", "-outputformat", "-of", "-inputformat", "-if", "-configurationname", "-version"}
)


def _is_bare_python_token(token: str) -> bool:
    clean = token.strip().strip("\"'")
    return (
        bool(clean)
        and "/" not in clean
        and "\\" not in clean
        and "${" not in clean
        and clean.lower() in _BARE_PYTHON_NAMES
    )


def _split_cmd_tokens(raw_cmd: str) -> list[str]:
    return [tok.strip("\"'") for tok in raw_cmd.strip().split() if tok.strip("\"'")]


def _detect_bare_python_argv(tokens: Sequence[str]) -> str | None:
    if not tokens:
        return None
    tok0 = tokens[0].strip().strip("\"'")
    if not tok0:
        return None
    if _is_bare_python_token(tok0):
        return tok0
    low0 = tok0.lower()
    base0 = Path(tok0.replace("\\", "/")).name.lower()
    if low0 in {"env", "/usr/bin/env"}:
        for item in tokens[1:]:
            clean = item.strip().strip("\"'")
            if not clean or clean.startswith("-") or ("=" in clean and not clean.startswith(("/", "\\"))):
                continue
            return f"{tok0} {clean}" if _is_bare_python_token(clean) else None
        return None
    if base0 in {"cmd", "cmd.exe"}:
        idx = 1
        while idx < len(tokens):
            sw = tokens[idx].strip().lower()
            if sw in {"/c", "/k"} and idx + 1 < len(tokens):
                sub_tokens = _split_cmd_tokens(" ".join(tokens[idx + 1 :]))
                if sub_tokens and (sub_bad := _detect_bare_python_argv(sub_tokens)) is not None:
                    return f"{tok0} {tokens[idx].strip()} {sub_bad}"
                return None
            if sw.startswith("/"):
                idx += 1
                continue
            break
        return None
    if base0 in _PS_BINARIES:
        idx = 1
        while idx < len(tokens):
            arg = tokens[idx].strip()
            alow = arg.lower()
            if alow in {"-encodedcommand", "-ec", "-e"} or alow.startswith("-enc") or alow in {"-file", "-f"}:
                return None
            if alow in _PS_VALUE_FLAGS:
                idx += 2
                continue
            if alow in {"-command", "-c"}:
                sub = [t for t in _split_cmd_tokens(" ".join(tokens[idx + 1 :])) if t != "&"]
                return f"{tok0} {arg} {sub[0]}" if (sub and _is_bare_python_token(sub[0])) else None
            if alow.startswith("-"):
                idx += 1
                continue
            sub = [t for t in _split_cmd_tokens(" ".join(tokens[idx:])) if t != "&"]
            return f"{tok0} {sub[0]}" if (sub and _is_bare_python_token(sub[0])) else None
    return None


def verify_windows_static_manifest_commands(plugin_name: str, plugin_dir: Path) -> list[str]:
    """Ban bare `python`/`python3` executables in Windows-enabled MCP & hook JSON manifests."""
    if not plugin_dir.is_dir():
        return []
    errors: list[str] = []
    manifests: list[Path] = []
    for dpath, dnames, fnames in os.walk(plugin_dir):
        dnames[:] = sorted(
            d for d in dnames if d not in _MANIFEST_SKIP_DIRS and not d.startswith((".venv", ".pytest", ".mypy", ".ruff"))
        )
        for fname in sorted(fnames):
            if fname in _MANIFEST_JSON_NAMES:
                manifests.append(Path(dpath) / fname)

    def _check_mcp_map(rel: str, servers: Mapping[str, Any]) -> None:
        for srv_name, srv_cfg in servers.items():
            if not isinstance(srv_cfg, Mapping) or "command" not in srv_cfg:
                continue
            cmd_val, args_val = srv_cfg.get("command"), srv_cfg.get("args")
            extra = [str(a) for a in args_val if isinstance(a, str)] if isinstance(args_val, list) else []
            if isinstance(cmd_val, str):
                s = cmd_val.strip()
                head = _split_cmd_tokens(s) if (" " in s and "/" not in s and "\\" not in s) else ([s] if s else [])
                tokens = [*head, *extra]
            elif isinstance(cmd_val, list):
                tokens = [*(str(x) for x in cmd_val if isinstance(x, str)), *extra]
            else:
                tokens = []
            if (bad := _detect_bare_python_argv(tokens)) is not None:
                errors.append(
                    f"{plugin_name}: {rel} MCP server `{srv_name}` invokes bare `{bad}` "
                    "(Windows Store stub / console popup risk; use `uv` or `node`)"
                )

    def _walk_hooks(rel: str, node: Any, seen_handlers: set[int]) -> None:
        if isinstance(node, list):
            for item in node:
                _walk_hooks(rel, item, seen_handlers)
            return
        if not isinstance(node, Mapping):
            return
        if ("command" in node or "commandWindows" in node) and id(node) not in seen_handlers:
            seen_handlers.add(id(node))
            cmd_win = node.get("commandWindows")
            if isinstance(cmd_win, str) and cmd_win.strip():
                tokens = _split_cmd_tokens(cmd_win)
            else:
                raw_cmd = node.get("command")
                if isinstance(raw_cmd, str) and raw_cmd.strip():
                    tokens = _split_cmd_tokens(raw_cmd)
                elif isinstance(raw_cmd, list):
                    tokens = [str(x) for x in raw_cmd if isinstance(x, str)]
                else:
                    tokens = []
            if (bad := _detect_bare_python_argv(tokens)) is not None:
                errors.append(
                    f"{plugin_name}: {rel} hook handler invokes bare `{bad}` on Windows "
                    "(Windows Store stub / console popup risk; use `uv`, `powershell.exe`, or `commandWindows`)"
                )
        for val in node.values():
            if isinstance(val, (Mapping, list)):
                _walk_hooks(rel, val, seen_handlers)

    def _walk_manifest(rel: str, fname: str, obj: Any, *, root: bool = False, seen_handlers: set[int]) -> None:
        if isinstance(obj, list):
            for item in obj:
                _walk_manifest(rel, fname, item, seen_handlers=seen_handlers)
            return
        if not isinstance(obj, Mapping):
            return
        if isinstance(obj.get("mcpServers"), Mapping):
            _check_mcp_map(rel, obj["mcpServers"])
        mcp_sub = obj.get("mcp")
        if isinstance(mcp_sub, Mapping) and isinstance(mcp_sub.get("servers"), Mapping):
            _check_mcp_map(rel, mcp_sub["servers"])
        if root and fname in {".mcp.json", "mcp.json", "mcp_config.json"} and "mcpServers" not in obj and "mcp" not in obj:
            _check_mcp_map(rel, obj)
        if isinstance(obj.get("hooks"), (Mapping, list)):
            _walk_hooks(rel, obj["hooks"], seen_handlers)
        for key, val in obj.items():
            if key not in {"mcpServers", "hooks"} and isinstance(val, (Mapping, list)):
                _walk_manifest(rel, fname, val, seen_handlers=seen_handlers)

    for manifest_path in manifests:
        rel = manifest_path.relative_to(plugin_dir).as_posix()
        try:
            parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
        except TimeoutError:
            raise
        except (OSError, ValueError) as exc:
            errors.append(f"{plugin_name}: {rel} invalid JSON during Windows manifest check: {exc}")
            continue
        _walk_manifest(rel, manifest_path.name, parsed, root=True, seen_handlers=set())
    return list(dict.fromkeys(errors))


def _resolve_repo(repo_name: str, siblings_roots: Sequence[Path], extra_repos: Mapping[str, Path] | None = None) -> Path | None:
    found = resolve_repo(repo_name, siblings_roots)
    return found if found is not None else (extra_repos.get(repo_name) if extra_repos else None)


def _mask_js_non_code(src: str) -> str:
    out, n, i, pchr, pwrd, tpl = [], len(src), 0, "", "", []
    while i < n:
        ch, nxt = src[i], (src[i + 1] if i + 1 < n else "")
        if ch == "/" and nxt in ("/", "*"):
            out.append("  "); i += 2; end = (lambda k: src[k] == "\n") if nxt == "/" else (lambda k: src[k : k + 2] == "*/")  # noqa: E702
            while i < n and not end(i):
                out.append("\n" if src[i] == "\n" else " "); i += 1  # noqa: E702
            if nxt == "*" and i < n: out.append("  "); i += 2  # noqa: E701,E702
        elif ch in ("'", '"'):
            q = ch; out.append(q); i += 1  # noqa: E702
            while i < n and src[i] != q:
                step = 2 if src[i] == "\\" and i + 1 < n else 1
                out.extend("\n" if c == "\n" else " " for c in src[i : i + step]); i += step  # noqa: E702
            if i < n: out.append(q); i += 1  # noqa: E701,E702
            pchr, pwrd = q, ""
        elif ch == "`" or (ch == "}" and tpl and tpl[-1] == 0):
            if ch == "}": tpl.pop()  # noqa: E701
            out.append(ch); i += 1  # noqa: E702
            while i < n:
                if src[i] == "\\" and i + 1 < n: out.extend((" ", "\n" if src[i + 1] == "\n" else " ")); i += 2  # noqa: E701,E702
                elif src[i : i + 2] == "${": out.append("${"); tpl.append(0); i += 2; pchr, pwrd = "{", ""; break  # noqa: E701,E702
                elif src[i] == "`": out.append("`"); i += 1; pchr, pwrd = "`", ""; break  # noqa: E701,E702
                else: out.append("\n" if src[i] == "\n" else " "); i += 1  # noqa: E701,E702
        elif ch == "/" and (not pchr or pchr in _JS_RX_CH or pwrd in _JS_RX_KW):
            out.append("/"); i += 1; cls = False  # noqa: E702
            while i < n:
                rc = src[i]
                if rc == "\\" and i + 1 < n: out.append("  "); i += 2; continue  # noqa: E701,E702
                cls = True if rc == "[" else (False if rc == "]" else cls)
                if rc == "/" and not cls:
                    out.append("/"); i += 1  # noqa: E702
                    while i < n and src[i].isalpha(): out.append(src[i]); i += 1  # noqa: E701,E702
                    break
                if rc == "\n": out.append("\n"); i += 1; break  # noqa: E701,E702
                out.append(" "); i += 1  # noqa: E702
            pchr, pwrd = "/", ""
        elif ch.isalpha() or ch in ("_", "$"):
            st = i
            while i < n and (src[i].isalnum() or src[i] in ("_", "$")): out.append(src[i]); i += 1  # noqa: E701,E702
            pwrd = src[st:i]; pchr = pwrd[-1]  # noqa: E702
        else:
            if tpl and ch in "{}": tpl[-1] += 1 if ch == "{" else -1  # noqa: E701
            out.append(ch); pchr, pwrd = (ch, "") if not ch.isspace() else (pchr, pwrd); i += 1  # noqa: E702
    return "".join(out)


def inspect_node_windowless_file(path: Path, *, require_spawns: bool) -> list[str]:
    masked = _mask_js_non_code(path.read_text(encoding="utf-8"))
    errors, cnt = [], 0
    for m in _JS_CALL_RE.finditer(masked):
        cnt, oidx, depth, pos = cnt + 1, m.end() - 1, 1, m.end()
        while pos < len(masked) and depth > 0:
            depth += 1 if masked[pos] == "(" else (-1 if masked[pos] == ")" else 0); pos += 1  # noqa: E702
        sl = masked[oidx:pos]
        reasons = [r for ok, r in ((depth == 0 and bool(re.search(r"\bwindowsHide\s*:\s*true\b", sl)), "missing `windowsHide: true`"), (not re.search(r"\bdetached\s*:\s*true\b", sl), "unconditional `detached: true` overrides `windowsHide` on win32")) if not ok]
        if reasons:
            errors.append(f"line {masked.count(chr(10), 0, m.start()) + 1} `{m.group(0).rstrip('(').strip()}(...)` {'; '.join(reasons)} (Windows console popup risk)")
    return errors + (["expected >= 1 child_process spawn call with `windowsHide: true`, found 0"] if require_spawns and cnt == 0 else [])


def _inspect_python_ast(path: Path) -> tuple[bool, bool, list[int], list[int], list[str], dict[str, set[str]], set[str], bool]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    _, _, _, visited = analyze_module_platform_guards(tree)
    cnw, wk, spawns, unguarded, bad_flags, imps, called, delegates_harness = False, False, [], [], [], {}, set(), False
    docs = {id(n.body[0].value) for n in ast.walk(tree) if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.body and isinstance(n.body[0], ast.Expr)}
    for node, _, posix in visited:
        if (isinstance(node, ast.Attribute) and "CREATE_NO_WINDOW" in node.attr) or (isinstance(node, ast.Name) and "CREATE_NO_WINDOW" in node.id) or (isinstance(node, ast.Constant) and node.value == 0x08000000):
            cnw = True
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs and any(f"subprocess.{fl}" in node.value for fl in _BANNED_WIN_FLAGS):
            bad_flags.append(f"line {node.lineno} inline script uses forbidden `CREATE_NEW_CONSOLE`/`DETACHED_PROCESS`")
        elif isinstance(node, ast.Call):
            fn = node.func
            nm = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "")
            called.update((nm,) if nm else ())
            wk = wk or nm in {"subprocess_window_kwargs", "run_owned"}
            cnw = cnw or (isinstance(fn, ast.Name) and fn.id == "getattr" and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and node.args[1].value == "CREATE_NO_WINDOW")
            bad_flags.extend(f"line {node.lineno} passes forbidden `{getattr(sub, 'attr', getattr(sub, 'id', ''))}`" for sub in ast.walk(node) if (isinstance(sub, ast.Attribute) and sub.attr in _BANNED_WIN_FLAGS) or (isinstance(sub, ast.Name) and sub.id in _BANNED_WIN_FLAGS))
            if not posix and isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id == "subprocess" and fn.attr in _PY_SPAWN_ATTRS:
                spawns.append(node.lineno)
                unguarded.extend((node.lineno,) if not any(kw.arg in ("creationflags", None) for kw in node.keywords) else ())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            delegates_harness = delegates_harness or any(al.name == "mindie_harness" or al.name.startswith("mindie_harness.") for al in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            delegates_harness = delegates_harness or node.module.startswith("mindie_harness")
            s = imps.setdefault(node.module.rsplit(".", 1)[-1], set())
            for al in node.names:
                s.add(al.asname or al.name); cnw = cnw or "CREATE_NO_WINDOW" in al.name  # noqa: E702
                bad_flags.extend((f"line {node.lineno} imports forbidden `{al.name}`",) if al.name in _BANNED_WIN_FLAGS else ())
    return cnw, wk, spawns, unguarded, bad_flags, imps, called, delegates_harness


def verify_windows_windowless_spawns(siblings_roots: Sequence[Path], *, main_repo: Path | None = None, require_siblings: bool = False, required_repos: Sequence[str] = (), explicit_repos: Mapping[str, Path] | None = None) -> list[str]:
    errors, must, reported = [], set(required_repos), set()
    _find = lambda nm: resolve_repo(nm, (), explicit_repos=explicit_repos) if explicit_repos and nm in explicit_repos else _resolve_repo(nm, siblings_roots)
    def _need(nm: str) -> Path | None:
        if (r := _find(nm)) is None and nm not in reported and (nm in must or (require_siblings and nm not in INDEPENDENT_ONLY_GATED_REPOS)):
            reported.add(nm); errors.append(f"{nm}: sibling checkout not found in {list(siblings_roots)} for Windows zero-popup verification")  # noqa: E702
        return r
    if main_repo is not None:
        scan = list(sorted((main_repo / ".github/scripts").glob("*.py")))
        if (main_repo / "install.py").is_file():
            scan.append(main_repo / "install.py")
        for py in scan:
            cnw, wk, sp, ug, bf, _, _, _ = _inspect_python_ast(py); rel = py.relative_to(main_repo).as_posix(); errors.extend(f"mindie-agent: {rel} {b}" for b in bf)  # noqa: E702
            if sp and (ug or not (cnw or wk)):
                errors.append(f"mindie-agent: {rel} spawns subprocesses without CREATE_NO_WINDOW (lines {ug or sp}; Windows console popup risk)")
    req_mjs: dict[str, set[str]] = {}
    for repo, rel in WINDOWS_NODE_WINDOWLESS_FILES:
        req_mjs.setdefault(repo, set()).add(rel)
        if (r := _need(repo)) is not None:
            errors.extend([f"{repo}: missing expected Node subprocess host {rel}"] if not (r / rel).is_file() else [f"{repo}: {rel} {d}" for d in inspect_node_windowless_file(r / rel, require_spawns=True)])
    for repo in NODE_SCANNED_REPOS:
        if (r := _need(repo) if repo == "npu-top" else _find(repo)) is not None:
            for dp, dns, fns in os.walk(r):
                dns[:] = sorted(d for d in dns if d not in NODE_SKIP_DIRS and not d.startswith("."))
                for fn in sorted(f for f in fns if Path(f).suffix in (".mjs", ".cjs", ".js")):
                    if (rel := (Path(dp) / fn).relative_to(r).as_posix()) not in req_mjs.get(repo, set()):
                        errors.extend(f"{repo}: {rel} {d}" for d in inspect_node_windowless_file(Path(dp) / fn, require_spawns=False))
    for repo, spec in WINDOWS_NO_WINDOW_REQUIRED_FILES:
        if (r := _need(repo)) is None:
            continue
        any_mode = isinstance(spec, tuple) and len(spec) == 2 and spec[0] == "any" and isinstance(spec[1], tuple)
        cands = spec[1] if any_mode else ((spec,) if isinstance(spec, str) else spec)  # type: ignore[index]
        if not (pres := [rel for rel in cands if (r / rel).is_file()]):
            errors.append(f"{repo}: missing expected subprocess wrapper {cands[0] if len(cands) == 1 else 'one of ' + ', '.join(cands)}"); continue  # noqa: E702
        if any_mode:
            satisfied = False
            for rel in pres:
                pcnw, pwk, psp, pug, pbf, _, _, pdh = _inspect_python_ast(r / rel); errors.extend(f"{repo}: {rel} {b}" for b in pbf)  # noqa: E702
                if psp and (pug or not (pcnw or pwk)):
                    errors.append(f"{repo}: {rel} spawns subprocesses without subprocess.CREATE_NO_WINDOW (Windows console popup risk)")
                satisfied = satisfied or pcnw or pwk or (not psp and pdh)
            if not satisfied:
                errors.append(f"{repo}: none of {', '.join(pres)} enforces subprocess.CREATE_NO_WINDOW or delegates to mindie_harness (missing subprocess.CREATE_NO_WINDOW; Windows console popup risk)")
            continue
        pcnw, pwk, _, _, pbf, _, _, _ = _inspect_python_ast(r / pres[0]); errors.extend(f"{repo}: {pres[0]} {b}" for b in pbf)  # noqa: E702
        if not (pcnw or pwk):
            errors.append(f"{repo}: {pres[0]} missing subprocess.CREATE_NO_WINDOW (Windows console popup risk)")
        for sec in pres[1:]:
            scnw, swk, ssp, sug, sbf, simp, scall, _ = _inspect_python_ast(r / sec); errors.extend(f"{repo}: {sec} {b}" for b in sbf)  # noqa: E702
            if ssp and (sug or not (scnw or swk)):
                errors.append(f"{repo}: {sec} spawns subprocesses without subprocess.CREATE_NO_WINDOW (Windows console popup risk)")
            elif not (scnw or swk or (not ssp and bool(simp.get(Path(pres[0]).stem, set()) & scall))):
                errors.append(f"{repo}: {sec} neither enforces subprocess.CREATE_NO_WINDOW nor delegates to {pres[0]} (Windows console popup risk)")
    for repo, rel in WINDOWS_NO_WINDOW_COMPANION_FILES:
        if (r := _find(repo)) is not None and (r / rel).is_file():
            ccnw, cwk, _, _, cbf, _, _, _ = _inspect_python_ast(r / rel); errors.extend(f"{repo}: {rel} {b}" for b in cbf)  # noqa: E702
            if not (ccnw or cwk):
                errors.append(f"{repo}: {rel} missing subprocess.CREATE_NO_WINDOW (Windows console popup risk)")
    for repo, scope in _FLAG_SCOPES:
        if (r := _need(repo) if repo in {"harness", "debugger", "npu-top"} else _find(repo)) is not None and (r / scope).is_dir():
            thin_floor = THIN_HOST_PLUGIN_FLOOR_VERSIONS.get(repo)
            ver = _parse_repo_semver(r) if thin_floor is not None else None
            enforce_all = repo in {"harness", "debugger", "npu-top"} or (thin_floor is not None and ver is not None and ver >= thin_floor)
            for dp, dns, fns in os.walk(r / scope):
                dns[:] = sorted(d for d in dns if d not in NODE_SKIP_DIRS and d != "__pycache__" and not d.startswith("."))
                for fn in sorted(f for f in fns if f.endswith(".py")):
                    cnw, wk, sp, ug, bf, _, _, _ = _inspect_python_ast(py := Path(dp) / fn); rel = py.relative_to(r).as_posix(); errors.extend(f"{repo}: {rel} {b}" for b in bf)  # noqa: E702
                    if enforce_all and fn != "posix.py" and sp and (ug or not (cnw or wk)):
                        errors.append(f"{repo}: {rel} spawns subprocesses without CREATE_NO_WINDOW (Windows console popup risk)")
    for plugin_name in ALL_PLUGINS:
        if (r := _find(plugin_name)) is not None:
            errors.extend(verify_windows_static_manifest_commands(plugin_name, r))
    return list(dict.fromkeys(errors))

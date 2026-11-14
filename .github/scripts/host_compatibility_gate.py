#!/usr/bin/env python3
"""Cross-version host compatibility, WSL2 native binary filtering, and Windows windowless spawn gate.

[Role]
Extracted R4/R5 verification helpers for `check_auto_update_readiness.py`: validates 7-host
`harness-compatibility.json` forward SemVer ranges, Windows windowless subprocess wrappers
(`CREATE_NO_WINDOW` / `windowsHide: true`), and active local host CLI versions.

[Invariants]
- WSL2 / POSIX binary lookups reject `/mnt/<drive>/...` DrvFS paths and `.exe`/`.cmd`/`.bat`/`.ps1`
  Windows shims; Windows lookups skip 0-byte `WindowsApps` store execution aliases.
- Refactored component subprocess wrappers may declare ordered candidate paths; the first present
  candidate in the checkout is authoritative and must enforce `CREATE_NO_WINDOW`.

[Timeouts & Locks]
- Delegates all subprocess execution to the caller's bounded `15s` runner; acquires no locks.

[Side-Effect Policy]
- Strictly read-only inspection of sibling checkouts and optional `--version` CLI probes.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Callable

WINDOWS_MOUNT_RE = re.compile(r"^/mnt/[a-zA-Z](?:/|$)")
WINDOWS_SHIM_SUFFIXES = frozenset({".exe", ".cmd", ".bat", ".ps1"})

BASELINE_HOST_PROBES: dict[str, tuple[str, ...]] = {
    "codex": ("0.153.4", "0.162.0-alpha.2", "0.162.0-alpha.17.2"),
}

FORWARD_HOST_PROBES: dict[str, tuple[str, ...]] = {
    "codex": ("0.162.3-alpha.17.2", "0.166.0", "0.166.1", "0.167.0-alpha.1", "0.199.0"),
    "claude-code": ("2.1.299", "2.1.300", "2.2.0-rc.1", "2.99.0"),
    "kimi-code": ("2.3.1", "2.3.2", "2.4.0-rc.1", "2.99.0"),
    "antigravity": ("2.0.0", "2.1.0", "2.99.0-rc.1"),
    "workbuddy": ("1.0.0", "1.1.0", "2.0.0-rc.1"),
    "opencode": ("2.2.0", "2.2.7", "2.3.0-rc.1", "2.99.0"),
}

WINDOWS_NODE_WINDOWLESS_FILES: tuple[tuple[str, str], ...] = (
    ("mindie-agent-dsh", "host3.mjs"),
    ("mindie-agent-oc", "plugins/mindie-agent/opencode_host.mjs"),
)

WINDOWS_NO_WINDOW_REQUIRED_FILES: tuple[tuple[str, str | tuple[str, ...]], ...] = (
    ("mindie-agent-dsh", "scripts/setup_process.py"),
    ("mindie-agent-dsh", "scripts/knowledge_mcp.py"),
    ("mindie-agent-agy", "plugins/mindie-agent/scripts/bounded.py"),
    ("mindie-agent-agy", "plugins/mindie-agent/scripts/component_update.py"),
    ("mindie-agent-wb", "plugins/mindie-agent/scripts/bounded.py"),
    ("mindie-agent-wb", "plugins/mindie-agent/scripts/component_update.py"),
    ("mindie-agent-oc", "plugins/mindie-agent/scripts/bounded.py"),
    ("mindie-agent-oc", "plugins/mindie-agent/scripts/component_update.py"),
    ("mindie-agent-oc", "plugins/mindie-agent/scripts/mindie_launch.py"),
    ("mindie-agent-cc", "scripts/bounded_win32.py"),
    ("mindie-agent-codex", "plugins/mindie-agent/scripts/windows_process.py"),
    ("mindie-agent-kimi", "scripts/bounded.py"),
    ("mindie-bench", ("src/mindie_bench/runner/host_platform.py", "src/mindie_bench/runner/process.py")),
    ("knowledge", "mindie_knowledge/windows_process.py"),
    ("knowledge", "mindie_knowledge/loop/process.py"),
    ("knowledge", "mindie_knowledge/gitread.py"),
    ("knowledge", "mindie_knowledge/release_http.py"),
    ("knowledge", "mindie_knowledge/graded/experiment_ledger.py"),
    ("diagnostics", ("mindie_diagnostics/github_transport.py", "mindie_diagnostics/reporter.py")),
    ("remote-dev", "remote_dev/core/local_process.py"),
    ("coordinator", "mindie_coordinator/service_client.py"),
)


def subprocess_window_kwargs(*, os_mod=os, subprocess_mod=subprocess) -> dict[str, int]:
    if os_mod.name == "nt" and hasattr(subprocess_mod, "CREATE_NO_WINDOW"):
        return {"creationflags": subprocess_mod.CREATE_NO_WINDOW}
    return {}


def is_wsl_windows_mount_path(raw: str | Path, *, os_mod=os) -> bool:
    if os_mod.name == "nt":
        return False
    normalized = str(raw).replace("\\", "/")
    return bool(WINDOWS_MOUNT_RE.match(normalized))


def is_windows_apps_stub(candidate: str | Path, *, os_mod=os) -> bool:
    if os_mod.name != "nt":
        return False
    normalized = str(candidate).replace("/", "\\").lower()
    if "\\microsoft\\windowsapps\\" not in normalized:
        return False
    stat_fn = getattr(os_mod, "stat", os.stat)
    try:
        return stat_fn(candidate).st_size == 0
    except TimeoutError:
        raise
    except OSError:
        return True


def filter_native_executable(candidate: str | None, *, os_mod=os) -> str | None:
    if not candidate:
        return None
    if os_mod.name != "nt":
        if is_wsl_windows_mount_path(candidate, os_mod=os_mod):
            return None
        if Path(candidate).suffix.lower() in WINDOWS_SHIM_SUFFIXES:
            return None
        return candidate
    if is_windows_apps_stub(candidate, os_mod=os_mod):
        return None
    return candidate


def which_native(cmd: str, *, path: str | None = None, os_mod=os, shutil_mod=shutil) -> str | None:
    if not cmd:
        return None
    if "/" in cmd or (os_mod.name == "nt" and "\\" in cmd):
        found = shutil_mod.which(cmd, path=path)
        return filter_native_executable(found, os_mod=os_mod)
    raw_path = getattr(os_mod, "environ", os.environ).get("PATH", "") if path is None else path
    pathsep = getattr(os_mod, "pathsep", os.pathsep)
    entries = [entry for entry in raw_path.split(pathsep) if entry]
    if os_mod.name != "nt":
        entries = [entry for entry in entries if not is_wsl_windows_mount_path(entry, os_mod=os_mod)]
    if not entries:
        return filter_native_executable(shutil_mod.which(cmd, path=path), os_mod=os_mod)
    for entry in entries:
        found = shutil_mod.which(cmd, path=entry)
        accepted = filter_native_executable(found, os_mod=os_mod)
        if accepted:
            return accepted
    return None


def _resolve_repo(repo_name: str, siblings_roots: list[Path]) -> Path | None:
    for root in siblings_roots:
        candidate = root / repo_name
        if (candidate / ".git").exists():
            return candidate
    return None


def matches_dsh_peer(requirement: str, version: str) -> bool:
    """Evaluate exact or comparator-range DSH peerDependencies with includePrerelease semantics."""
    from semantic_version import Version

    if not isinstance(requirement, str) or not requirement.strip():
        return False
    try:
        actual = Version(version.strip())
    except ValueError:
        return False
    for token in requirement.strip().split():
        for op, fn in (
            (">=", lambda a, b: a >= b),
            ("<=", lambda a, b: a <= b),
            (">", lambda a, b: a > b),
            ("<", lambda a, b: a < b),
            ("=", lambda a, b: a == b),
        ):
            if token.startswith(op):
                target_str = token[len(op) :]
                break
        else:
            op, fn, target_str = "=", (lambda a, b: a == b), token
        try:
            target = Version(target_str)
        except ValueError:
            return False
        if (
            op == "<"
            and not target.prerelease
            and (actual.major, actual.minor, actual.patch) == (target.major, target.minor, target.patch)
        ):
            return False
        if not fn(actual, target):
            return False
    return True


def extract_semver(raw: str) -> str | None:
    match = re.search(r"\bv?(\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)\b", raw)
    return match.group(1) if match else None


def verify_windows_windowless_spawns(siblings_roots: list[Path]) -> list[str]:
    """Ensure Node.js spawn calls set windowsHide:true and Windows Python subprocess wrappers set CREATE_NO_WINDOW."""
    errors: list[str] = []
    for node_repo, rel_mjs in WINDOWS_NODE_WINDOWLESS_FILES:
        r_dir = _resolve_repo(node_repo, siblings_roots)
        if r_dir is None:
            continue
        host_mjs = r_dir / rel_mjs
        if host_mjs.is_file():
            text = host_mjs.read_text(encoding="utf-8")
            uncommented = "\n".join(
                line for line in text.splitlines() if not line.lstrip().startswith("//")
            )
            spawn_count = len(
                re.findall(r"\b(?:spawn|spawnSync|execFile|execFileSync|execSync)\s*\(", uncommented)
            )
            hide_count = len(re.findall(r"\bwindowsHide\s*:\s*true\b", uncommented))
            if spawn_count == 0 or hide_count < spawn_count:
                errors.append(
                    f"{node_repo}: {rel_mjs} has {spawn_count} child-process spawn call(s) but only "
                    f"{hide_count} windowsHide: true setting(s) (Windows console popup risk)"
                )
    for repo_name, rel_spec in WINDOWS_NO_WINDOW_REQUIRED_FILES:
        repo_dir = _resolve_repo(repo_name, siblings_roots)
        if repo_dir is None:
            continue
        candidates = (rel_spec,) if isinstance(rel_spec, str) else rel_spec
        chosen_rel = next((rel for rel in candidates if (repo_dir / rel).is_file()), None)
        if chosen_rel is None:
            label = candidates[0] if len(candidates) == 1 else f"one of {', '.join(candidates)}"
            errors.append(f"{repo_name}: missing expected subprocess wrapper {label}")
            continue
        target = repo_dir / chosen_rel
        if "CREATE_NO_WINDOW" not in target.read_text(encoding="utf-8"):
            errors.append(f"{repo_name}: {chosen_rel} missing subprocess.CREATE_NO_WINDOW (Windows console popup risk)")
    return errors


def verify_flexible_component_compatibility_impl(
    siblings_roots: list[Path],
    *,
    ensure_knowledge_importable: Callable[[list[Path]], bool],
    windowless_check: Callable[[list[Path]], list[str]],
) -> list[str]:
    """Verify that the latest shared component code is API-compatible with all 7 host plugins."""
    errors: list[str] = []
    if not ensure_knowledge_importable(siblings_roots):
        return errors
    from semantic_version import Version
    from mindie_knowledge.component_bindings import COMPONENT_MODULES
    from mindie_knowledge.releases import REPOSITORIES, supports_harness, validate_compatibility
    from mindie_knowledge.runtime_inventory import COMPONENTS

    expected_harnesses = {"codex", "claude-code", "kimi-code", "dsh", "antigravity", "workbuddy"}
    if set(REPOSITORIES) not in (expected_harnesses, expected_harnesses | {"opencode"}):
        errors.append(f"mindie_knowledge.releases.REPOSITORIES keys {set(REPOSITORIES)} != {expected_harnesses}")
    oc_dir = _resolve_repo("mindie-agent-oc", siblings_roots)
    if oc_dir is not None:
        oc_scripts = str(oc_dir / "plugins/mindie-agent/scripts")
        if oc_scripts not in sys.path:
            sys.path.insert(0, oc_scripts)
        from oc_native_compat import ensure_oc_native_support

        ensure_oc_native_support()
    harness_repos = dict(REPOSITORIES)
    if oc_dir is not None:
        harness_repos["opencode"] = "mindie-agent/mindie-agent-oc"

    required_pkgs = {
        "mindie-knowledge",
        "remote-dev",
        "mindie-diagnostics",
        "mindie-debugger",
        "mindie-profiler",
        "mindie-sim",
        "npu-top",
        "mindie-coordinator",
    }
    if not required_pkgs.issubset(set(COMPONENTS)):
        errors.append(f"mindie_knowledge.runtime_inventory.COMPONENTS missing {required_pkgs - set(COMPONENTS)}")

    required_modules = {"profiler", "sim", "coordinator", "diagnostics", "debugger"}
    if not required_modules.issubset(set(COMPONENT_MODULES)):
        errors.append(
            f"mindie_knowledge.component_bindings.COMPONENT_MODULES missing {required_modules - set(COMPONENT_MODULES)}"
        )
    elif not str(COMPONENT_MODULES["debugger"][1]).startswith("mindie_debugger"):
        errors.append(
            f"mindie_knowledge.component_bindings.COMPONENT_MODULES['debugger'] unexpected module {COMPONENT_MODULES['debugger']!r}"
        )

    for harness_key, repo_slug in harness_repos.items():
        plugin_name = repo_slug.split("/", 1)[1]
        plugin_dir = _resolve_repo(plugin_name, siblings_roots)
        if plugin_dir is None:
            continue
        compat_path = (
            plugin_dir / "plugins/mindie-agent/harness-compatibility.json"
            if plugin_name == "mindie-agent-codex"
            else plugin_dir / "harness-compatibility.json"
        )
        if not compat_path.is_file():
            errors.append(f"{plugin_name}: missing {compat_path.name}")
            continue
        compat_data = json.loads(compat_path.read_text(encoding="utf-8"))
        if harness_key == "dsh":
            pkg_json = json.loads((plugin_dir / "package.json").read_text(encoding="utf-8"))
            peer_req = ((pkg_json.get("peerDependencies") or {}).get("@deepseek-ai/dsh") or "").strip()
            if not peer_req or (" " not in peer_req and not peer_req.startswith((">=", "^", "~"))):
                errors.append(
                    f"mindie-agent-dsh: package.json peerDependencies['@deepseek-ai/dsh']={peer_req!r} "
                    "is point-locked; must declare a forward-compatible SemVer range"
                )
            for ver in ("0.2.0-rc.2", "0.2.1-rc.2", "0.2.2-alpha.2", "0.99.99"):
                if not matches_dsh_peer(peer_req, ver):
                    errors.append(
                        f"mindie-agent-dsh: peerDependencies['@deepseek-ai/dsh']={peer_req!r} "
                        f"rejects forward DSH version {ver}"
                    )
            supported_list = compat_data.get("supported") or []
            if not supported_list or all(item.get("minimum") == item.get("maximum") for item in supported_list):
                errors.append(
                    "mindie-agent-dsh: harness-compatibility.json missing forward-compatible 'supported' range"
                )
            continue

        if "supported" in compat_data and "interface_registry" in compat_data:
            try:
                validate_compatibility(compat_data, harness_name=harness_key)
            except Exception as exc:
                errors.append(f"{plugin_name}: validate_compatibility failed under latest mindie-knowledge: {exc}")
                continue
            supported_list = compat_data.get("supported") or []
            highest = max(supported_list, key=lambda item: Version(item["maximum"]))
            if highest["minimum"] == highest["maximum"] or not highest.get("include_prerelease"):
                errors.append(
                    f"{plugin_name}: highest supported interval {highest} is point-locked or excludes prereleases; "
                    "must declare a forward-compatible range with include_prerelease=true"
                )
            probes = BASELINE_HOST_PROBES.get(harness_key, ()) + FORWARD_HOST_PROBES.get(harness_key, ())
            for probe_ver in probes:
                if not supports_harness(compat_data, harness_name=harness_key, harness_version=probe_ver):
                    errors.append(
                        f"{plugin_name}: harness-compatibility.json rejects required host version {probe_ver}"
                    )

    errors.extend(windowless_check(siblings_roots))
    return errors


def _codex_config_candidates() -> list[Path]:
    explicit = os.environ.get("MINDIE_AGENT_CONFIG", "").strip()
    if explicit:
        return [Path(explicit).expanduser()]
    candidates: list[Path] = []
    cfg_home = os.environ.get("MINDIE_CONFIG_HOME", "").strip()
    if cfg_home:
        candidates.append(Path(cfg_home).expanduser() / "codex.json")
    if os.name == "nt":
        appdata = os.environ.get("APPDATA", "").strip()
        if appdata:
            candidates.append(Path(appdata).expanduser() / "mindie-agent" / "codex.json")
    candidates.append(Path.home() / ".config/mindie-agent/codex.json")
    return candidates


def verify_local_host_compatibility_impl(
    siblings_roots: list[Path],
    *,
    ensure_knowledge_importable: Callable[[list[Path]], bool],
    which_fn: Callable[[str], str | None],
    run_cmd: Callable[[list[str]], subprocess.CompletedProcess[str]],
) -> list[str]:
    errors: list[str] = []
    if not ensure_knowledge_importable(siblings_roots):
        return ["mindie_knowledge.releases unavailable for host compatibility verification"]
    from mindie_knowledge.releases import supports_harness

    codex_dir = _resolve_repo("mindie-agent-codex", siblings_roots)
    if codex_dir is not None:
        compat = json.loads(
            (codex_dir / "plugins/mindie-agent/harness-compatibility.json").read_text(encoding="utf-8")
        )
        codex_bins: list[str] = []
        which_codex = filter_native_executable(which_fn("codex"))
        if which_codex:
            codex_bins.append(which_codex)
        desktop_override = os.environ.get("MINDIE_DESKTOP_CODEX_CLI_PATH")
        runtime_override = os.environ.get("CODEX_APP_RUNTIME_CLI_PATH")
        if desktop_override is not None:
            desktop_codex = desktop_override.strip()
        elif runtime_override == "":
            desktop_codex = ""
        else:
            desktop_codex = "/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex"
        if desktop_codex and os.path.isfile(desktop_codex) and desktop_codex not in codex_bins:
            codex_bins.append(desktop_codex)
        if (
            runtime_override
            and Path(runtime_override).is_absolute()
            and os.path.isfile(runtime_override)
            and runtime_override not in codex_bins
        ):
            codex_bins.append(runtime_override)
        for cfg_file in _codex_config_candidates():
            if not cfg_file.is_file():
                continue
            try:
                config = json.loads(cfg_file.read_text(encoding="utf-8"))
                for key in ("native_context", "native"):
                    cfg_bin = (config.get(key) or {}).get("MINDIE_CODEX_BIN")
                    if isinstance(cfg_bin, str) and os.path.isfile(cfg_bin) and cfg_bin not in codex_bins:
                        codex_bins.append(cfg_bin)
            except TimeoutError:
                raise
            except (OSError, ValueError):
                pass
        for binary in codex_bins:
            resolved_bin = filter_native_executable(which_fn(binary)) or binary
            res = run_cmd([resolved_bin, "--version"])
            ver = extract_semver(res.stdout + "\n" + res.stderr)
            if res.returncode != 0 or not ver:
                errors.append(
                    f"mindie-agent-codex: installed Codex CLI version unavailable "
                    f"({resolved_bin}, exit={res.returncode})"
                )
            elif not supports_harness(compat, harness_name="codex", harness_version=ver):
                errors.append(
                    f"mindie-agent-codex: harness-compatibility.json does not support installed Codex CLI "
                    f"{ver} ({resolved_bin})"
                )

    for repo_name, cli_name, harness_key in (
        ("mindie-agent-cc", "claude", "claude-code"),
        ("mindie-agent-kimi", "kimi", "kimi-code"),
    ):
        plugin_dir = _resolve_repo(repo_name, siblings_roots)
        resolved_cli = filter_native_executable(which_fn(cli_name))
        if plugin_dir is not None and resolved_cli:
            compat = json.loads((plugin_dir / "harness-compatibility.json").read_text(encoding="utf-8"))
            res = run_cmd([resolved_cli, "--version"])
            ver = extract_semver(res.stdout + "\n" + res.stderr)
            if ver and not supports_harness(compat, harness_name=harness_key, harness_version=ver):
                errors.append(f"{repo_name}: harness-compatibility.json does not support installed {cli_name} {ver}")

    dsh_dir = _resolve_repo("mindie-agent-dsh", siblings_roots)
    resolved_dsh = filter_native_executable(which_fn("dsh"))
    if dsh_dir is not None and resolved_dsh:
        pkg_json = json.loads((dsh_dir / "package.json").read_text(encoding="utf-8"))
        peer_req = ((pkg_json.get("peerDependencies") or {}).get("@deepseek-ai/dsh") or "").strip()
        res = run_cmd([resolved_dsh, "--version"])
        ver = extract_semver(res.stdout + "\n" + res.stderr)
        if ver and not matches_dsh_peer(peer_req, ver):
            errors.append(
                f"mindie-agent-dsh: package.json peerDependencies['@deepseek-ai/dsh']={peer_req!r} "
                f"does not support installed dsh {ver}"
            )

    oc_dir = _resolve_repo("mindie-agent-oc", siblings_roots)
    if oc_dir is not None:
        oc_scripts = str(oc_dir / "plugins/mindie-agent/scripts")
        if oc_scripts not in sys.path:
            sys.path.insert(0, oc_scripts)
        from oc_native_compat import ensure_oc_native_support

        ensure_oc_native_support()
        compat = json.loads((oc_dir / "harness-compatibility.json").read_text(encoding="utf-8"))
        home_oc_names = ("opencode.exe", "opencode.cmd") if os.name == "nt" else ("opencode",)
        oc_candidates = [
            filter_native_executable(which_fn("opencode")),
            *(str(Path.home() / ".opencode/bin" / name) for name in home_oc_names),
        ]
        oc_bins = [b for b in oc_candidates if b and os.path.isfile(b)]
        for binary in dict.fromkeys(oc_bins):
            res = run_cmd([binary, "--version"])
            ver = extract_semver(res.stdout + "\n" + res.stderr)
            if res.returncode != 0 or not ver:
                errors.append(
                    f"mindie-agent-oc: installed OpenCode CLI version unavailable "
                    f"({binary}, exit={res.returncode})"
                )
            elif not supports_harness(compat, harness_name="opencode", harness_version=ver):
                errors.append(f"mindie-agent-oc: harness-compatibility.json does not support installed opencode {ver}")

    return errors

#!/usr/bin/env python3
"""Cross-version host compatibility, WSL2 native binary filtering, Windows zero-popup & storage gate.

[Role]
Extracted R4/R5 verification helpers for `check_auto_update_readiness.py`: validates 7-host
`harness-compatibility.json` forward SemVer ranges, Windows windowless subprocess wrappers
(`CREATE_NO_WINDOW` / `windowsHide: true`), bounded storage lifecycle & temp hygiene (`P8`),
and active local host CLI versions.

[Invariants]
- WSL2 / POSIX binary lookups reject `.exe`/`.cmd`/`.bat`/`.ps1` files and PE/CRLF/MSYS Windows
  shims on `/mnt/<drive>/...`, while preserving native Linux ELF binaries and LF scripts stored on
  WSL mounts; Windows lookups skip 0-byte `WindowsApps` store execution aliases.
- Windows zero-popup checks (`windows_zero_popup_gate.py`) run unconditionally before
  `mindie_knowledge` import probes, inspect every co-existing refactored module via AST, and
  enforce per-call `windowsHide: true` across Node.js child-process launches.

[Timeouts & Locks]
- Delegates all subprocess execution to the caller's bounded `15s` runner; acquires no locks.

[Side-Effect Policy]
- Strictly read-only inspection of sibling checkouts and optional `--version` CLI probes.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Callable

from storage_lifecycle_gate import (
    STORAGE_LIFECYCLE_FLOOR_VERSIONS,
    inspect_python_temp_hygiene,
    inspect_storage_module_windows_pid_safety,
    verify_storage_lifecycle_hygiene,
)
from windows_zero_popup_gate import (
    WINDOWS_NODE_WINDOWLESS_FILES,
    WINDOWS_NO_WINDOW_COMPANION_FILES,
    WINDOWS_NO_WINDOW_REQUIRED_FILES,
    inspect_node_windowless_file,
    verify_windows_windowless_spawns,
)
from zero_binding_gate import verify_zero_session_binding_gates

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


def _is_native_linux_file_on_wsl_mount(candidate: str | Path, *, os_mod=os) -> bool:
    read_head = getattr(os_mod, "read_head", None)
    try:
        if read_head is not None:
            head = read_head(candidate)
        else:
            path_obj = Path(candidate)
            if not path_obj.is_file():
                return False
            with path_obj.open("rb") as handle:
                head = handle.read(512)
    except TimeoutError:
        raise
    except OSError:
        return False
    if head.startswith(b"\x7fELF"):
        return True
    if head.startswith(b"#!"):
        first_line = head.split(b"\n", 1)[0]
        if b"\r" in first_line:
            return False
        if re.search(rb"(?:CYGWIN|MINGW|MSYS|cygpath|(?<!\\)\.exe\b|[A-Za-z]:[\\/])", head, re.IGNORECASE):
            return False
        return True
    return False


def filter_native_executable(candidate: str | None, *, os_mod=os) -> str | None:
    if not candidate:
        return None
    if os_mod.name != "nt":
        if Path(candidate).suffix.lower() in WINDOWS_SHIM_SUFFIXES:
            return None
        if is_wsl_windows_mount_path(candidate, os_mod=os_mod):
            if not _is_native_linux_file_on_wsl_mount(candidate, os_mod=os_mod):
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


def verify_flexible_component_compatibility_impl(
    siblings_roots: list[Path],
    *,
    ensure_knowledge_importable: Callable[[list[Path]], bool],
    windowless_check: Callable[[list[Path]], list[str]],
    zero_binding_check: Callable[[list[Path]], list[str]] | None = None,
    require_siblings: bool = False,
) -> list[str]:
    """Verify that the latest shared component code is API-compatible with all 7 host plugins."""
    errors: list[str] = list(windowless_check(siblings_roots))
    if zero_binding_check is not None:
        errors.extend(zero_binding_check(siblings_roots))
    else:
        errors.extend(verify_zero_session_binding_gates(siblings_roots, require_siblings=require_siblings))
    if not ensure_knowledge_importable(siblings_roots):
        if require_siblings:
            errors.append("knowledge: mindie_knowledge unavailable for R4 host compatibility verification")
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
        if desktop_codex and os.path.isfile(desktop_codex):
            accepted_desktop = filter_native_executable(desktop_codex, os_mod=os)
            if accepted_desktop is None and desktop_override is not None:
                errors.append(f"mindie-agent-codex: configured Codex CLI is not a native executable ({desktop_codex})")
            elif accepted_desktop and accepted_desktop not in codex_bins:
                codex_bins.append(accepted_desktop)
        if runtime_override and Path(runtime_override).is_absolute() and os.path.isfile(runtime_override):
            accepted_runtime = filter_native_executable(runtime_override, os_mod=os)
            if accepted_runtime is None:
                errors.append(
                    f"mindie-agent-codex: configured Codex CLI is not a native executable ({runtime_override})"
                )
            elif accepted_runtime not in codex_bins:
                codex_bins.append(accepted_runtime)
        for cfg_file in _codex_config_candidates():
            if not cfg_file.is_file():
                continue
            try:
                config = json.loads(cfg_file.read_text(encoding="utf-8"))
                for key in ("native_context", "native"):
                    cfg_bin = (config.get(key) or {}).get("MINDIE_CODEX_BIN")
                    if isinstance(cfg_bin, str) and os.path.isfile(cfg_bin):
                        accepted_cfg = filter_native_executable(cfg_bin, os_mod=os)
                        if accepted_cfg is None:
                            errors.append(
                                f"mindie-agent-codex: configured Codex CLI is not a native executable ({cfg_bin})"
                            )
                        elif accepted_cfg not in codex_bins:
                            codex_bins.append(accepted_cfg)
            except TimeoutError:
                raise
            except (OSError, ValueError):
                pass
        for resolved_bin in codex_bins:
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
            if res.returncode != 0 or not ver:
                errors.append(
                    f"{repo_name}: installed {cli_name} CLI version unavailable ({resolved_cli}, exit={res.returncode})"
                )
            elif not supports_harness(compat, harness_name=harness_key, harness_version=ver):
                errors.append(f"{repo_name}: harness-compatibility.json does not support installed {cli_name} {ver}")

    dsh_dir = _resolve_repo("mindie-agent-dsh", siblings_roots)
    resolved_dsh = filter_native_executable(which_fn("dsh"))
    if dsh_dir is not None and resolved_dsh:
        pkg_json = json.loads((dsh_dir / "package.json").read_text(encoding="utf-8"))
        peer_req = ((pkg_json.get("peerDependencies") or {}).get("@deepseek-ai/dsh") or "").strip()
        res = run_cmd([resolved_dsh, "--version"])
        ver = extract_semver(res.stdout + "\n" + res.stderr)
        if res.returncode != 0 or not ver:
            errors.append(
                f"mindie-agent-dsh: installed dsh CLI version unavailable ({resolved_dsh}, exit={res.returncode})"
            )
        elif not matches_dsh_peer(peer_req, ver):
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
            *(
                filter_native_executable(str(Path.home() / ".opencode/bin" / name), os_mod=os)
                for name in home_oc_names
                if (Path.home() / ".opencode/bin" / name).is_file()
            ),
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


def _can_import_knowledge() -> bool:
    try:
        import mindie_knowledge.graded.maintenance  # noqa: F401
        import mindie_knowledge.releases  # noqa: F401

        return True
    except ImportError:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run R4 host compatibility and Windows zero-popup checks.")
    parser.add_argument("--main-repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--siblings-root", type=Path, action="append", default=[])
    parser.add_argument("--require-siblings", action="store_true")
    parser.add_argument("--release-repo", action="append", default=[])
    args = parser.parse_args(argv)
    roots = [p.resolve() for p in args.siblings_root]
    main_repo = args.main_repo.resolve()
    errors = verify_flexible_component_compatibility_impl(
        roots,
        ensure_knowledge_importable=lambda _r: _can_import_knowledge(),
        windowless_check=lambda r: [
            *verify_windows_windowless_spawns(
                r,
                main_repo=main_repo,
                require_siblings=args.require_siblings,
                required_repos=args.release_repo,
            ),
            *verify_storage_lifecycle_hygiene(
                r,
                main_repo=main_repo,
                require_siblings=args.require_siblings,
                required_repos=args.release_repo,
            ),
        ],
        zero_binding_check=lambda r: verify_zero_session_binding_gates(
            r,
            require_siblings=args.require_siblings,
            required_repos=args.release_repo,
        ),
        require_siblings=args.require_siblings,
    )
    if errors:
        for err in errors:
            print(f"[host-compatibility-gate:FAIL] {err}", file=sys.stderr)
        return 1
    print("[host-compatibility-gate:OK] R4 host compatibility and Windows zero-popup invariants verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""R7 End-to-End Functional Smoke & 7-Host Wire Readiness Gate.

[Role]
Builds isolated first-party wheels (`harness`, 8 runtime components, `mindie-bench`), stages a
verified local wheelhouse (`release-channel.json` + `mindie-wheels-bundle.tar.gz` + `SHA256SUMS`),
provisions a clean `smoke-venv` with `--override` local wheels, and executes:
1. Gate Layer 1: `mindie-harness selftest --mode full --json` (`mindie-selftest/1`)
2. Gate Layer 2: `mindie-bench host-accept` across targeted or all 7 native host plugins.

[Invariants]
- Enforces `MINDIE_REQUIRE_FULLSTACK=1` with zero silent skips: missing `uv`/Python/sibling repos,
  non-zero exit codes, `"failed"`, `"skipped"`, or empty/non-Mapping checks fail closed immediately.
- Isolates all `HOME`, `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `XDG_*`, `MINDIE_*`,
  `REMOTE_DEV_*`, `UV_CACHE_DIR`, and `TMPDIR` roots inside `TemporaryDirectory(prefix="mindie-r7-")`.

[Timeouts & Locks]
- Wheel builds `120s` each; venv install `240s`; `selftest` `120s`; `host-accept` `660s`
  (`>= 540s` max `install.py` inner budgets + `120s` grace); acquires no locks.

[Side-Effect Policy]
- Writes only inside disposable `TemporaryDirectory`; never mutates sibling checkouts or host state.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
from typing import Any, Callable, Mapping, Sequence

from host_compatibility_gate import is_windows_apps_stub, subprocess_window_kwargs, which_native
from repo_roots import (
    ALL_KNOWN_REPOS, HUB_REPO, PACKAGE_INFO,
    infer_default_siblings_roots, parse_repo_overrides, resolve_repo, summarize_repo_coverage,
)

FIRST_PARTY_REPOS: tuple[str, ...] = (
    "harness", "diagnostics", "debugger", "profiler", "sim",
    "npu-top", "remote-dev", "knowledge", "coordinator", "mindie-bench",
)
RUNTIME_COMPONENT_REPOS: tuple[str, ...] = FIRST_PARTY_REPOS[:9]
FULLSTACK_TRIGGER_REPOS: frozenset[str] = frozenset({"harness", "knowledge", "remote-dev", "mindie-bench"})
PLUGIN_BY_HOST: dict[str, str] = {
    "codex": "mindie-agent-codex", "cc": "mindie-agent-cc", "kimi": "mindie-agent-kimi",
    "dsh": "mindie-agent-dsh", "agy": "mindie-agent-agy", "wb": "mindie-agent-wb", "oc": "mindie-agent-oc",
}
HOST_BY_PLUGIN: dict[str, str] = {v: k for k, v in PLUGIN_BY_HOST.items()}
ALL_HOSTS: tuple[str, ...] = tuple(PLUGIN_BY_HOST.keys())
HOST_ACCEPT_TIMEOUT_SECONDS = 660.0
_CHECK_LIST_KEYS: tuple[str, ...] = ("checks", "scenarios", "steps", "cases", "results")


class _SmokeSetupError(RuntimeError):
    """Internal fail-closed setup error converted into `R7:` diagnostics."""


def _norm_pkg(name: str) -> str:
    return re.sub(r"[-_.]+", "-", str(name or "").strip()).lower()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _default_run_cmd(
    argv: Sequence[str], *, cwd: Path | None = None, env: Mapping[str, str] | None = None, timeout: float = 120.0
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv), stdin=subprocess.DEVNULL, cwd=str(cwd) if cwd else None,
        env=dict(env) if env is not None else None, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout, check=False,
        **subprocess_window_kwargs(os_mod=os, subprocess_mod=subprocess),
    )


def _resolve_host_python(which_fn: Callable[[str], str | None]) -> Path | None:
    curr = Path(sys.executable) if sys.executable else None
    if curr and sys.version_info >= (3, 11):
        try:
            if curr.is_file() and not is_windows_apps_stub(curr):
                return curr
        except TimeoutError:
            raise
        except OSError:
            pass
    for cand_name in ("python3", "python"):
        if not (found := which_fn(cand_name)):
            continue
        try:
            proc = _default_run_cmd([found, "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"], timeout=10.0)
            if proc.returncode == 0:
                return Path(found)
        except subprocess.TimeoutExpired:
            continue
        except TimeoutError:
            raise
        except OSError:
            continue
    return None


def plan_smoke_hosts(
    release_scope: str, release_repos: Sequence[str], siblings_roots: Sequence[Path] = (), *, explicit_repos: Mapping[str, Path] | None = None
) -> tuple[list[str], bool]:
    """Deterministically plan `(target_hosts, all_hosts_mode)` from `(release_scope, release_repos)`."""
    _ = (siblings_roots, explicit_repos)
    dedup = list(dict.fromkeys(release_repos))
    if release_scope == "product" or not dedup or any(r in FULLSTACK_TRIGGER_REPOS for r in dedup):
        return list(ALL_HOSTS), True
    hosts = [HOST_BY_PLUGIN[r] for r in dedup] if all(r in HOST_BY_PLUGIN for r in dedup) else list(dict.fromkeys(["codex", *(HOST_BY_PLUGIN[r] for r in dedup if r in HOST_BY_PLUGIN)]))
    return hosts, set(hosts) == set(ALL_HOSTS)


def assemble_stage_from_wheels(stage_dir: Path, wheels_dir: Path, *, channel_version: str = "0.1.18") -> Path:
    """Assemble `release-channel.json`, `mindie-wheels-bundle.tar.gz`, `SHA256SUMS`, and `--override` file."""
    stage_dir.mkdir(parents=True, exist_ok=True)
    wheels_by_pkg: dict[str, tuple[Path, str]] = {}
    for whl in sorted(wheels_dir.glob("*.whl")):
        parts = whl.name.split("-")
        if len(parts) < 5:
            raise _SmokeSetupError(f"R7: malformed wheel filename {whl.name}")
        if (pkg := _norm_pkg(parts[0])) in wheels_by_pkg:
            raise _SmokeSetupError(f"R7: duplicate wheel for `{pkg}`: {wheels_by_pkg[pkg][0].name} vs {whl.name}")
        wheels_by_pkg[pkg] = (whl, parts[1])
    if missing := sorted({_norm_pkg(PACKAGE_INFO[r][0]) for r in FIRST_PARTY_REPOS} - set(wheels_by_pkg)):
        raise _SmokeSetupError(f"R7: missing built first-party wheel(s): {missing}")

    components_manifest, lock_lines = {}, []
    for repo_name in RUNTIME_COMPONENT_REPOS:
        dist_name = _norm_pkg(PACKAGE_INFO[repo_name][0])
        _, ver = wheels_by_pkg[dist_name]
        components_manifest[repo_name] = {
            "name": repo_name, "role": "shared_component", "repository": f"mindie-agent/{repo_name}",
            "package": dist_name, "version": ver, "tag": f"v{ver}",
            "commit": "0" * 40, "revision": "0" * 40, "independent_update_allowed": True,
        }
        lock_lines.append(f"{dist_name}=={ver}\n")

    rc_path, bundle_path = stage_dir / "release-channel.json", stage_dir / "mindie-wheels-bundle.tar.gz"
    rc_doc = {"schema": "mindie-release-channel/1", "current_patch_version": channel_version, "product_version": channel_version, "components": components_manifest}
    rc_path.write_text(json.dumps(rc_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    with tarfile.open(bundle_path, "w:gz") as archive:
        for repo_name in RUNTIME_COMPONENT_REPOS:
            whl_path, _ = wheels_by_pkg[_norm_pkg(PACKAGE_INFO[repo_name][0])]
            archive.add(whl_path, arcname=whl_path.name)
        lock_bytes = "".join(sorted(lock_lines)).encode("utf-8")
        info = tarfile.TarInfo("requirements.lock")
        info.size = len(lock_bytes)
        archive.addfile(info, io.BytesIO(lock_bytes))

    (stage_dir / "SHA256SUMS").write_text(f"{_sha256_file(bundle_path)}  mindie-wheels-bundle.tar.gz\n{_sha256_file(rc_path)}  release-channel.json\n", encoding="utf-8", newline="\n")
    overrides_path = stage_dir / "first-party-overrides.txt"
    overrides_path.write_text("".join(f"{pkg} @ {whl.resolve().as_uri()}\n" for pkg, (whl, _) in sorted(wheels_by_pkg.items())), encoding="utf-8", newline="\n")
    return overrides_path


def _default_stage_builder(
    tmp_root: Path, package_checkouts: Mapping[str, Path], uv_bin: str, host_py: Path,
    run_fn: Callable[..., subprocess.CompletedProcess[str]], base_env: Mapping[str, str],
) -> tuple[Path, Path]:
    stage_dir, wheels_dir = tmp_root / "stage", tmp_root / "stage" / "wheels"
    wheels_dir.mkdir(parents=True, exist_ok=True)
    for repo_name in FIRST_PARTY_REPOS:
        proc = run_fn([uv_bin, "build", "--wheel", "--out-dir", str(wheels_dir), str(package_checkouts[repo_name])], env=base_env, timeout=120.0)
        if proc.returncode != 0:
            raise _SmokeSetupError(f"R7: `uv build --wheel` failed for {repo_name} (exit={proc.returncode}): {(proc.stderr or proc.stdout).strip()}")
    overrides_path = assemble_stage_from_wheels(stage_dir, wheels_dir)
    smoke_venv = tmp_root / "smoke-venv"
    venv_proc = run_fn([uv_bin, "venv", "--python", str(host_py), str(smoke_venv)], env=base_env, timeout=60.0)
    if venv_proc.returncode != 0:
        raise _SmokeSetupError(f"R7: `uv venv` failed (exit={venv_proc.returncode}): {(venv_proc.stderr or venv_proc.stdout).strip()}")
    venv_py = smoke_venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    pip_argv = [uv_bin, "pip", "install", "--python", str(venv_py), "--find-links", str(wheels_dir), "--override", str(overrides_path), *(str(p) for p in sorted(wheels_dir.glob("*.whl")))]
    pip_proc = run_fn(pip_argv, env=base_env, timeout=240.0)
    if pip_proc.returncode != 0:
        raise _SmokeSetupError(f"R7: `uv pip install` into smoke-venv failed (exit={pip_proc.returncode}): {(pip_proc.stderr or pip_proc.stdout).strip()}")
    imp_proc = run_fn([str(venv_py), "-I", "-X", "utf8", "-c", "import mindie_harness, mindie_bench"], env=base_env, timeout=30.0)
    if imp_proc.returncode != 0:
        raise _SmokeSetupError(f"R7: smoke-venv failed importing mindie_harness/mindie_bench: {(imp_proc.stderr or imp_proc.stdout).strip()}")
    return stage_dir, venv_py


def _build_sandbox_env(tmp_root: Path) -> dict[str, str]:
    s = tmp_root / "sandbox"
    (s / "home").mkdir(parents=True, exist_ok=True)
    (s / "tmp").mkdir(parents=True, exist_ok=True)
    return {
        **os.environ, "HOME": str(s / "home"), "USERPROFILE": str(s / "home"), "APPDATA": str(s / "appdata"),
        "LOCALAPPDATA": str(s / "localappdata"), "XDG_CONFIG_HOME": str(s / "xdg-config"),
        "XDG_DATA_HOME": str(s / "xdg-data"), "XDG_STATE_HOME": str(s / "xdg-state"), "XDG_CACHE_HOME": str(s / "xdg-cache"),
        "MINDIE_CONFIG_HOME": str(s / "mindie-config"), "MINDIE_DATA_HOME": str(s / "mindie-data"),
        "MINDIE_KNOWLEDGE_ROOT": str(s / "mindie-knowledge"), "MINDIE_DIAGNOSTICS_ROOT": str(s / "mindie-diagnostics"),
        "MINDIE_DIAGNOSTICS_CONFIG": str(s / "mindie-diagnostics/config.json"), "MINDIE_AGENT_CONFIG": "",
        "REMOTE_DEV_AUTH_DIR": str(s / "remote-dev-auth"), "REMOTE_DEV_STATE_DIR": str(s / "remote-dev-state"),
        "MINDIE_REMOTE_STATE_DIR": str(s / "remote-dev-state"), "UV_CACHE_DIR": str(s / "uv-cache"),
        "TMPDIR": str(s / "tmp"), "TEMP": str(s / "tmp"), "TMP": str(s / "tmp"),
        "MINDIE_REQUIRE_FULLSTACK": "1", "PYTHONUTF8": "1",
    }


def _validate_check_list(items: Any, prefix: str) -> tuple[int, list[str]]:
    if not isinstance(items, list):
        return 0, [f"{prefix}checks is not a list"]
    passed_count, bad = 0, []
    for idx, item in enumerate(items):
        if not isinstance(item, Mapping):
            bad.append(f"{prefix}#{idx}=non_mapping({type(item).__name__})")
            continue
        name, st = str(item.get("name") or item.get("id") or item.get("check") or f"#{idx}"), str(item.get("status") or "").strip().lower()
        if st not in {"passed", "ok"} or item.get("ok") is False:
            bad.append(f"{prefix}{name}={st or 'missing_status'}")
        else:
            passed_count += 1
        for sub_key in _CHECK_LIST_KEYS:
            if sub_key in item and item[sub_key] is not None:
                sub_p, sub_bad = _validate_check_list(item[sub_key], f"{prefix}{name}.")
                passed_count, bad = passed_count + sub_p, [*bad, *sub_bad]
    return passed_count, bad


def _verify_selftest(proc: subprocess.CompletedProcess[str]) -> list[str]:
    if proc.returncode != 0:
        return [f"R7: `mindie-harness selftest --mode full` exited {proc.returncode}: {(proc.stderr or proc.stdout).strip()}"]
    try:
        payload = json.loads(proc.stdout)
    except ValueError as exc:
        return [f"R7: `mindie-harness selftest --mode full` emitted invalid JSON: {exc}"]
    if not isinstance(payload, Mapping):
        return ["R7: `mindie-harness selftest --mode full` payload is not a JSON object"]
    errors = [
        *([] if payload.get("schema") == "mindie-selftest/1" else [f"R7: selftest schema {payload.get('schema')!r} != 'mindie-selftest/1'"]),
        *([] if payload.get("mode") == "full" else [f"R7: selftest mode {payload.get('mode')!r} != 'full'"]),
        *([] if payload.get("status") == "passed" else [f"R7: selftest status {payload.get('status')!r} != 'passed'"]),
    ]
    checks = payload.get("checks")
    if not isinstance(checks, list) or not checks:
        errors.append("R7: selftest payload contains zero checks")
    else:
        passed_n, bad = _validate_check_list(checks, "")
        if bad or passed_n < 1:
            errors.append(f"R7: selftest checks failed, skipped, or malformed under MINDIE_REQUIRE_FULLSTACK=1: {bad or '0 passed'}")
    return errors


def _verify_host_record(host: str, rec: Any) -> list[str]:
    if not isinstance(rec, Mapping):
        return [f"R7: host-accept host `{host}` record must be a JSON object, got {type(rec).__name__}"]
    st = str(rec.get("status") or "").strip().lower()
    errs = [] if (st in {"passed", "ok"} and rec.get("ok") is not False) else [f"R7: host-accept host `{host}` status={st or 'missing'}"]
    total_passed, found_list = 0, False
    for key in _CHECK_LIST_KEYS:
        if key in rec and rec[key] is not None:
            found_list = True
            p_cnt, bad = _validate_check_list(rec[key], f"{host}.")
            total_passed += p_cnt
            if bad:
                errs.append(f"R7: host-accept host `{host}` failed/skipped/malformed {key}: {bad}")
    if not found_list or total_passed < 1:
        errs.append(f"R7: host-accept host `{host}` executed zero passing checks/scenarios")
    return errs


def _verify_host_accept(
    proc: subprocess.CompletedProcess[str], report_path: Path, expected_hosts: Sequence[str]
) -> list[str]:
    if proc.returncode != 0:
        return [f"R7: `mindie-bench host-accept` exited {proc.returncode}: {(proc.stderr or proc.stdout).strip()}"]
    if not report_path.is_file():
        return [f"R7: `mindie-bench host-accept` did not write output report {report_path}"]
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except TimeoutError:
        raise
    except (OSError, ValueError) as exc:
        return [f"R7: `mindie-bench host-accept` output report {report_path} invalid JSON: {exc}"]
    if not isinstance(report, Mapping):
        return ["R7: `mindie-bench host-accept` report is not a JSON object"]

    errors: list[str] = []
    if report.get("status") != "passed":
        errors.append(f"R7: host-accept status {report.get('status')!r} != 'passed'")

    host_records: dict[str, Any] = {}
    hosts_field = report.get("hosts")
    if "hosts" in report:
        if isinstance(hosts_field, Mapping):
            host_records = {str(k): v for k, v in hosts_field.items()}
        elif isinstance(hosts_field, list):
            for idx, entry in enumerate(hosts_field):
                if not isinstance(entry, Mapping) or not isinstance(entry.get("host"), str) or not entry["host"].strip():
                    errors.append(f"R7: host-accept hosts[{idx}] must be a JSON object with non-empty `host`")
                else:
                    host_records[entry["host"].strip()] = entry
        else:
            errors.append(f"R7: host-accept `hosts` must be a JSON object or list, got {type(hosts_field).__name__}")
        for key in _CHECK_LIST_KEYS:
            if key in report and report[key] is not None:
                _, bad_top = _validate_check_list(report[key], "")
                if bad_top:
                    errors.append(f"R7: host-accept top-level {key} failed/skipped/malformed: {bad_top}")
    elif isinstance(report.get("host"), str) and report["host"].strip():
        host_records[report["host"].strip()] = report

    missing_hosts = [h for h in expected_hosts if h not in host_records]
    if missing_hosts:
        errors.append(f"R7: host-accept report missing expected host(s) {missing_hosts} (exercised={sorted(host_records)})")
    for h in expected_hosts:
        if h in host_records:
            errors.extend(_verify_host_record(h, host_records[h]))
    return errors


def verify_functional_smoke(
    main_repo: Path, siblings_roots: Sequence[Path], *, release_scope: str = "product",
    release_repos: Sequence[str] = (), explicit_repos: Mapping[str, Path] | None = None,
    which_fn: Callable[[str], str | None] | None = None,
    host_python_fn: Callable[[], Path | None] | None = None,
    stage_builder_fn: Callable[[Path, Mapping[str, Path], str, Path], tuple[Path, Path]] | None = None,
    run_cmd_fn: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> list[str]:
    """Execute fail-closed R7 end-to-end functional smoke (`selftest` + `host-accept`)."""
    resolve_which = which_fn or (lambda cmd: which_native(cmd))
    run_fn = run_cmd_fn or _default_run_cmd
    if not (uv_bin := resolve_which("uv")):
        return ["R7: `uv` executable not found on native PATH (MINDIE_REQUIRE_FULLSTACK=1)"]
    host_py = host_python_fn() if host_python_fn is not None else _resolve_host_python(resolve_which)
    if host_py is None:
        return ["R7: usable host Python >=3.11 not found (MINDIE_REQUIRE_FULLSTACK=1)"]
    install_script = main_repo / "install.py"
    if not install_script.is_file():
        return [f"R7: install.py not found at {install_script}"]

    target_hosts, all_hosts_mode = plan_smoke_hosts(release_scope, release_repos)
    package_checkouts, plugin_checkouts, missing_errors = {}, {}, []
    required_lookup = [
        *((r, package_checkouts, "first-party checkout", r) for r in FIRST_PARTY_REPOS),
        *((PLUGIN_BY_HOST[h], plugin_checkouts, "host plugin checkout", h) for h in target_hosts),
    ]
    for repo_name, bucket, label, key in required_lookup:
        try:
            if (found := resolve_repo(repo_name, siblings_roots, explicit_repos=explicit_repos)) is None:
                missing_errors.append(f"R7: required {label} `{repo_name}` not found in {list(siblings_roots)} (MINDIE_REQUIRE_FULLSTACK=1)")
            else:
                bucket[key] = found
        except ValueError as exc:
            missing_errors.append(f"R7: {exc}")
    if missing_errors:
        return missing_errors

    with tempfile.TemporaryDirectory(prefix="mindie-r7-") as tmp_str:
        tmp_root = Path(tmp_str).resolve()
        smoke_env = _build_sandbox_env(tmp_root)
        try:
            stage_dir, venv_py = (stage_builder_fn(tmp_root, package_checkouts, uv_bin, host_py) if stage_builder_fn is not None else _default_stage_builder(tmp_root, package_checkouts, uv_bin, host_py, run_fn, smoke_env))
        except subprocess.TimeoutExpired as exc:
            return [f"R7: wheelhouse/venv assembly timed out: {exc}"]
        except TimeoutError:
            raise
        except (_SmokeSetupError, OSError) as exc:
            return [str(exc) if isinstance(exc, _SmokeSetupError) else f"R7: wheelhouse setup failed: {exc}"]

        try:
            st_proc = run_fn([str(venv_py), "-I", "-X", "utf8", "-m", "mindie_harness.cli", "selftest", "--mode", "full", "--json"], env=smoke_env, timeout=120.0)
        except subprocess.TimeoutExpired as exc:
            return [f"R7: `mindie-harness selftest --mode full` timed out: {exc}"]
        except TimeoutError:
            raise
        except OSError as exc:
            return [f"R7: failed launching `mindie-harness selftest`: {exc}"]
        if st_errors := _verify_selftest(st_proc):
            return st_errors

        errors, flat_parents = [], {p.parent for p in plugin_checkouts.values()}
        use_all_flag = all_hosts_mode and set(target_hosts) == set(ALL_HOSTS) and len(flat_parents) == 1 and all(plugin_checkouts[h].name == PLUGIN_BY_HOST[h] for h in ALL_HOSTS)
        invocations = (
            [("--all-hosts", (), next(iter(flat_parents)), ALL_HOSTS, tmp_root / "host-accept-all.json")]
            if use_all_flag
            else [("--host", (h, "--plugin-dir", str(plugin_checkouts[h])), plugin_checkouts[h].parent, (h,), tmp_root / f"host-accept-{h}.json") for h in target_hosts]
        )
        for flag, extra, cwd_dir, expected, report_path in invocations:
            argv = [str(venv_py), "-I", "-X", "utf8", "-m", "mindie_bench.cli", "host-accept", flag, *extra, "--wheelhouse-stage", str(stage_dir), "--install-script", str(install_script), "--output", str(report_path)]
            try:
                ha_proc = run_fn(argv, cwd=cwd_dir, env=smoke_env, timeout=HOST_ACCEPT_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired as exc:
                errors.append(f"R7: `mindie-bench host-accept` timed out: {exc}")
                continue
            except TimeoutError:
                raise
            except OSError as exc:
                errors.append(f"R7: failed launching `mindie-bench host-accept`: {exc}")
                continue
            errors.extend(_verify_host_accept(ha_proc, report_path, expected))
        return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run R7 end-to-end functional smoke & 7-host wire gate.")
    parser.add_argument("--main-repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--release-scope", choices=("independent", "product"), default="product")
    parser.add_argument("--release-repo", action="append", default=[])
    parser.add_argument("--siblings-root", type=Path, action="append", default=[])
    parser.add_argument("--repo", action="append", default=[], metavar="NAME=/ABS/PATH")
    args = parser.parse_args(argv)
    try:
        explicit_repos = parse_repo_overrides(args.repo)
    except ValueError as exc:
        print(f"[functional-smoke-gate:FAIL] {exc}", file=sys.stderr)
        return 1
    main_repo = args.main_repo.resolve()
    roots = infer_default_siblings_roots(main_repo, args.siblings_root)
    hosts, _ = plan_smoke_hosts(args.release_scope, args.release_repo)
    cov = summarize_repo_coverage(ALL_KNOWN_REPOS, [HUB_REPO, *FIRST_PARTY_REPOS, *(PLUGIN_BY_HOST[h] for h in hosts)], roots, explicit_repos=explicit_repos, extra_present={HUB_REPO: main_repo})
    print(cov.format_line("functional-smoke-gate"))
    if errors := verify_functional_smoke(main_repo, roots, release_scope=args.release_scope, release_repos=args.release_repo, explicit_repos=explicit_repos):
        print("\n".join(f"[functional-smoke-gate:FAIL] {err}" for err in errors), file=sys.stderr)
        return 1
    print(f"[functional-smoke-gate:OK] R7 functional smoke verified across hosts={hosts}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

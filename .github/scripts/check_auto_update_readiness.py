#!/usr/bin/env python3
"""Pre-release and CI gate for both lockstep and flexible component updates.

[Role]
Verifies that `channels/0.1.json`, all 9 `knowledge-*` domain corpora, all 8 shared
runtime components, and all 7 native host plugins satisfy zero-intervention update
invariants for both flexible independent component/corpus releases (`max(installed,
plugin_baseline, latest_component_release)`) and lockstep plugin releases.

[Invariants]
- Corpus Monotonicity: Every `knowledge-*` unit modification across channel history,
  plugin `verified_commit` baselines, and `HEAD` must monotonically advance its integer
  `revision` whenever `content_sha256` changes.
- Independent releases use formal component tags without a historical channel ceiling.
  Product combinations retain their component ceiling and explicit lockstep policy.
- Cross-Version Compatibility Probe: Shared component sources must pass model-free
  compatibility checks against all 7 host plugin adapters.
- Documentation Scope: Independent R6 reads only selected repositories' own
  versions/READMEs; full channel-wide alignment requires explicit product scope.

[Timeouts & Locks]
- Subprocess probes (`git`, host `--version`, sync checks) enforce a strict `15s` timeout.
- Purely read-only inspection with zero file locks or network mutations.

[Side-Effect Policy]
- Strictly read-only; never modifies repositories, user configs, or release state.
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

from sibling_readme_sync import (
    EXPECTED_CORPORA,
    EXPECTED_PLUGINS,
    EXPECTED_SHARED_COMPONENTS,
    INDEPENDENT_PLUGINS,
    SHA_RE,
    verify_channel_schema,
    verify_github_releases,
    verify_unreleased_plugin_main,
)
from host_compatibility_gate import (
    BASELINE_HOST_PROBES,
    FORWARD_HOST_PROBES,
    WINDOWS_NODE_WINDOWLESS_FILES,
    WINDOWS_NO_WINDOW_REQUIRED_FILES,
    extract_semver as _extract_semver,
    matches_dsh_peer as _matches_dsh_peer,
    subprocess_window_kwargs,
    verify_flexible_component_compatibility_impl,
    verify_local_host_compatibility_impl,
    verify_windows_windowless_spawns,
    which_native,
)
from release_doc_hygiene import source_version, verify_release_doc_hygiene
from release_latest_integrity import verify_current_release_heads


def _run_cmd(argv: list[str], *, cwd: Path | None = None, timeout: float = 15.0) -> subprocess.CompletedProcess[str]:
    resolved_argv = list(argv)
    if resolved_argv:
        resolved_bin = which_native(resolved_argv[0], os_mod=os, shutil_mod=shutil)
        if resolved_bin:
            resolved_argv[0] = resolved_bin
    return subprocess.run(
        resolved_argv,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        **subprocess_window_kwargs(os_mod=os, subprocess_mod=subprocess),
    )


def _parse_semver(ver: str) -> tuple[int, ...]:
    core = ver.lstrip("v").split("-", 1)[0]
    return tuple(int(x) for x in core.split("."))


def _resolve_repo(repo_name: str, siblings_roots: list[Path]) -> Path | None:
    for root in siblings_roots:
        candidate = root / repo_name
        if (candidate / ".git").exists():
            return candidate
    return None


def _ensure_knowledge_importable(siblings_roots: list[Path]) -> bool:
    knowledge_repo = _resolve_repo("knowledge", siblings_roots)
    if knowledge_repo is not None:
        if str(knowledge_repo) not in sys.path:
            sys.path.insert(0, str(knowledge_repo))
        site_package_candidates = [
            *sorted((knowledge_repo / ".venv/lib").glob("python*/site-packages")),
            *sorted((knowledge_repo / ".venv/Lib").glob("site-packages")),
            knowledge_repo / ".venv/Lib/site-packages",
        ]
        for sp in site_package_candidates:
            if sp.is_dir() and str(sp) not in sys.path:
                sys.path.append(str(sp))
    try:
        import mindie_knowledge.graded.maintenance  # noqa: F401
        import mindie_knowledge.releases  # noqa: F401
        return True
    except ImportError:
        return False


def _component_tag_commits(comp_repo: Path) -> dict[str, str]:
    """Return {commit_sha: semver_str} for all vX.Y.Z tags in a component repo."""
    res = _run_cmd(["git", "tag", "-l", "v[0-9]*.[0-9]*.[0-9]*", "--sort=v:refname"], cwd=comp_repo)
    if res.returncode != 0:
        return {}
    mapping: dict[str, str] = {}
    for tag in res.stdout.splitlines():
        tag = tag.strip()
        if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
            continue
        rev = _run_cmd(["git", "rev-parse", f"{tag}^{{commit}}"], cwd=comp_repo)
        if rev.returncode == 0:
            mapping[rev.stdout.strip()] = tag.lstrip("v")
    return mapping


def _historical_corpus_commits(main_repo: Path, corpus_name: str) -> list[str]:
    res = _run_cmd(["git", "log", "--format=%H", "--reverse", "--", "channels/0.1.json"], cwd=main_repo)
    if res.returncode != 0:
        return []
    commits: list[str] = []
    for ch_commit in res.stdout.splitlines():
        show = _run_cmd(["git", "show", f"{ch_commit}:channels/0.1.json"], cwd=main_repo)
        if show.returncode != 0:
            continue
        try:
            data = json.loads(show.stdout)
        except ValueError:
            continue
        c_sha = ((data.get("corpora") or {}).get(corpus_name) or {}).get("commit")
        if isinstance(c_sha, str) and SHA_RE.fullmatch(c_sha) and (not commits or commits[-1] != c_sha):
            commits.append(c_sha)
    return commits


def verify_corpora(
    main_repo: Path,
    manifest: dict,
    siblings_roots: list[Path],
    *,
    require_siblings: bool,
) -> list[str]:
    errors: list[str] = []
    if not _ensure_knowledge_importable(siblings_roots):
        if require_siblings:
            errors.append("mindie_knowledge package could not be imported for corpus validation")
        return errors
    from mindie_knowledge.graded.maintenance import build_routing_index
    from mindie_knowledge.graded.units import GradedUnit

    knowledge_repo = _resolve_repo("knowledge", siblings_roots)
    valid_knowledge_shas = _component_tag_commits(knowledge_repo) if knowledge_repo else {}
    channel_knowledge_ver = _parse_semver(manifest["components"]["knowledge"]["version"])

    for corpus_name, entry in (manifest.get("corpora") or {}).items():
        repo_dir = _resolve_repo(corpus_name, siblings_roots)
        if repo_dir is None:
            if require_siblings:
                errors.append(f"{corpus_name}: sibling checkout not found in {siblings_roots}")
            continue

        head_res = _run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir)
        head_sha = head_res.stdout.strip()
        if head_sha != entry["commit"]:
            errors.append(f"{corpus_name}: channels/0.1.json commit {entry['commit']} != repo HEAD {head_sha}")

        contract_path = repo_dir / "publication-contract.json"
        if not contract_path.is_file():
            errors.append(f"{corpus_name}: missing publication-contract.json")
        else:
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            val_rev = ((contract.get("validator") or {}).get("revision") or "")
            if valid_knowledge_shas:
                if val_rev not in valid_knowledge_shas:
                    errors.append(
                        f"{corpus_name}: publication-contract.json validator.revision {val_rev} "
                        f"is not a formal mindie-knowledge release tag commit"
                    )
                elif _parse_semver(valid_knowledge_shas[val_rev]) > channel_knowledge_ver:
                    errors.append(
                        f"{corpus_name}: validator.revision {val_rev} ({valid_knowledge_shas[val_rev]}) "
                        f"is newer than channel knowledge {manifest['components']['knowledge']['version']}"
                    )

        report = build_routing_index(repo_dir, check=True)
        if not report.get("ok"):
            errors.append(f"{corpus_name}: build_routing_index(check=True) failed: {report.get('errors')}")
        if report.get("unit_count") != entry["units"]:
            errors.append(
                f"{corpus_name}: channels/0.1.json units {entry['units']} != actual {report.get('unit_count')}"
            )

        history = _historical_corpus_commits(main_repo, corpus_name)
        if head_sha and (not history or history[-1] != head_sha):
            history.append(head_sha)
        baseline_commits = [history[0], *history[-2:]] if len(history) > 2 else history
        seen_states: dict[str, tuple[int, str, str]] = {}
        for c_sha in baseline_commits:
            ls_res = _run_cmd(["git", "ls-tree", "-r", "--name-only", c_sha, "units/"], cwd=repo_dir)
            if ls_res.returncode != 0:
                continue
            for rel_path in ls_res.stdout.splitlines():
                if not rel_path.endswith(".md"):
                    continue
                blob_res = _run_cmd(["git", "show", f"{c_sha}:{rel_path}"], cwd=repo_dir)
                if blob_res.returncode != 0:
                    continue
                unit = GradedUnit.from_bytes(blob_res.stdout.encode("utf-8"), path=rel_path)
                prev = seen_states.get(unit.id)
                if prev is not None:
                    old_rev, old_sha, old_commit = prev
                    if unit.revision < old_rev:
                        errors.append(
                            f"{corpus_name}: {unit.id} revision regressed from {old_rev} ({old_commit[:8]}) "
                            f"to {unit.revision} ({c_sha[:8]})"
                        )
                    elif unit.content_sha256 != old_sha and unit.revision <= old_rev:
                        errors.append(
                            f"{corpus_name}: {unit.id} content changed between {old_commit[:8]} and {c_sha[:8]} "
                            f"without advancing revision (stuck at {unit.revision})"
                        )
                seen_states[unit.id] = (unit.revision, unit.content_sha256, c_sha)
    return errors


def _extract_pinned_sha(text: str, repo_slug: str) -> str | None:
    patterns = (
        rf"github\.com/mindie-agent/{re.escape(repo_slug)}(?:\.git)?@([0-9a-f]{{40}})",
        rf'github\.com/mindie-agent/{re.escape(repo_slug)}"\s*,\s*rev\s*=\s*"([0-9a-f]{{40}})"',
    )
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1)
    return None


def verify_components_and_plugins(
    manifest: dict,
    siblings_roots: list[Path],
    *,
    require_siblings: bool,
    strict_lockstep: bool = False,
    independent: bool = False,
    verify_formal_releases: bool = False,
) -> list[str]:
    """Verify component tags and plugin baseline floors (supporting flexible component updates)."""
    errors: list[str] = []
    comp_entries = manifest.get("components") or {}
    comp_tag_maps: dict[str, dict[str, str]] = {}
    independent_dependencies: dict[str, dict[str, str]] = {}

    for name, entry in comp_entries.items():
        repo_dir = _resolve_repo(name, siblings_roots)
        if repo_dir is None:
            if require_siblings:
                errors.append(f"{name}: sibling checkout not found in {siblings_roots}")
            continue
        if name in EXPECTED_SHARED_COMPONENTS:
            comp_tag_maps[name] = _component_tag_commits(repo_dir)
        tag = entry["tag"]
        tag_res = _run_cmd(["git", "rev-parse", f"{tag}^{{commit}}"], cwd=repo_dir)
        if tag_res.returncode != 0:
            commit_res = _run_cmd(["git", "rev-parse", f"{entry['commit']}^{{commit}}"], cwd=repo_dir)
            if strict_lockstep or comp_tag_maps.get(name) or commit_res.returncode != 0:
                errors.append(f"{name}: tag {tag} not found in local checkout {repo_dir}")
        elif tag_res.stdout.strip() != entry["commit"]:
            errors.append(
                f"{name}: tag {tag} resolves to {tag_res.stdout.strip()}, "
                f"expected {entry['commit']} in channels/0.1.json"
            )

    def _check_pin_floor(plugin_name: str, comp_name: str, pinned_sha: str | None, source_file: str) -> None:
        if not pinned_sha:
            errors.append(f"{plugin_name}: missing {comp_name} SHA pin in {source_file}")
            return
        channel_sha = comp_entries[comp_name]["commit"]
        channel_ver = comp_entries[comp_name]["version"]
        if strict_lockstep and pinned_sha != channel_sha:
            errors.append(
                f"{plugin_name}: {source_file} pins {comp_name} to {pinned_sha[:8]}, "
                f"expected lockstep {channel_sha[:8]} ({channel_ver})"
            )
            return
        tag_map = comp_tag_maps.get(comp_name)
        if independent and tag_map is not None:
            if pinned_sha not in tag_map:
                errors.append(f"{plugin_name}: {source_file} pins {comp_name} to {pinned_sha[:8]}, "
                              "which is not a formal release tag")
            else:
                independent_dependencies[f"{comp_name}@{pinned_sha}"] = {
                    "repository": comp_entries[comp_name]["repository"],
                    "version": tag_map[pinned_sha], "commit": pinned_sha,
                }
            return
        if tag_map:
            if pinned_sha not in tag_map:
                comp_repo = _resolve_repo(comp_name, siblings_roots)
                is_mainline_advance = False
                if comp_repo is not None:
                    anc_behind = _run_cmd(
                        ["git", "merge-base", "--is-ancestor", pinned_sha, channel_sha], cwd=comp_repo
                    )
                    anc_floor = _run_cmd(
                        ["git", "merge-base", "--is-ancestor", channel_sha, pinned_sha], cwd=comp_repo
                    )
                    anc_head = _run_cmd(
                        ["git", "merge-base", "--is-ancestor", pinned_sha, "HEAD"], cwd=comp_repo
                    )
                    is_mainline_advance = anc_behind.returncode == 0 or (
                        anc_floor.returncode == 0 and anc_head.returncode == 0
                    )
                if not is_mainline_advance:
                    errors.append(
                        f"{plugin_name}: {source_file} pins {comp_name} to {pinned_sha[:8]}, "
                        f"which is not a formal release tag in {comp_name}"
                    )
            elif _parse_semver(tag_map[pinned_sha]) > _parse_semver(channel_ver):
                errors.append(
                    f"{plugin_name}: {source_file} baseline {comp_name} {tag_map[pinned_sha]} "
                    f"is ahead of channel version {channel_ver}"
                )

    dist_by_component = {
        "knowledge": "mindie-knowledge",
        "remote-dev": "remote-dev",
        "diagnostics": "mindie-diagnostics",
        "debugger": "mindie-debugger",
        "profiler": "mindie-profiler",
        "sim": "mindie-sim",
        "coordinator": "mindie-coordinator",
        "npu-top": "npu-top",
    }

    def _extract_default_dep_pin(
        pyp_text: str, comp_name: str, *, uses_uv_sources: bool = False
    ) -> str | None:
        import tomllib

        try:
            parsed = tomllib.loads(pyp_text)
        except Exception:
            return None
        raw_deps = (parsed.get("project") or {}).get("dependencies")
        if not isinstance(raw_deps, list):
            return None
        dist_name = dist_by_component[comp_name]
        if uses_uv_sources:
            if not any(
                isinstance(d, str) and re.match(rf"^\s*{re.escape(dist_name)}(?:\s|[><=!~@]|$)", d)
                for d in raw_deps
            ):
                return None
            src = ((parsed.get("tool") or {}).get("uv") or {}).get("sources") or {}
            entry = src.get(dist_name) if isinstance(src, dict) else None
            if not isinstance(entry, dict):
                return None
            if entry.get("git") != f"https://github.com/mindie-agent/{comp_name}":
                return None
            rev = entry.get("rev")
            return rev if isinstance(rev, str) and re.fullmatch(r"[0-9a-f]{40}", rev) else None
        deps_text = "\n".join(
            d for d in raw_deps if isinstance(d, str) and re.match(rf"^\s*{re.escape(dist_name)}\s*@", d)
        )
        return _extract_pinned_sha(deps_text, comp_name)

    def _check_uv_lock_default_deps(
        plugin_name: str,
        lock_path: Path,
        root_pkg_name: str,
        required_components: tuple[str, ...],
        expected_pins: dict[str, str | None],
    ) -> None:
        import tomllib

        if not lock_path.is_file():
            errors.append(f"{plugin_name}: missing {lock_path.name}")
            return
        try:
            locked = tomllib.loads(lock_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{plugin_name}: invalid {lock_path.name}: {exc}")
            return
        packages = locked.get("package") or []
        root_pkgs = [p for p in packages if isinstance(p, dict) and p.get("name") == root_pkg_name]
        if len(root_pkgs) != 1:
            errors.append(f"{plugin_name}: {lock_path.name} missing root package {root_pkg_name}")
            return
        root_dep_names = {
            d.get("name") for d in (root_pkgs[0].get("dependencies") or []) if isinstance(d, dict)
        }
        for comp_name in required_components:
            dist_name = dist_by_component[comp_name]
            if dist_name not in root_dep_names:
                errors.append(
                    f"{plugin_name}: {lock_path.name} root package {root_pkg_name} missing default dependency {dist_name}"
                )
            expected_sha = expected_pins.get(comp_name)
            if not expected_sha:
                continue
            comp_pkgs = [p for p in packages if isinstance(p, dict) and p.get("name") == dist_name]
            expected_git = f"https://github.com/mindie-agent/{comp_name}?rev={expected_sha}#{expected_sha}"
            if len(comp_pkgs) != 1 or (comp_pkgs[0].get("source") or {}).get("git") != expected_git:
                errors.append(
                    f"{plugin_name}: {lock_path.name} package {dist_name} does not match expected commit {expected_sha[:8]}"
                )

    vllm_repo = _resolve_repo("knowledge-vllm-ascend", siblings_roots)
    expected_vllm_corpus_sha = manifest["corpora"]["knowledge-vllm-ascend"]["commit"]

    def _check_verified_commit(plugin_name: str, verified_sha: str) -> None:
        if strict_lockstep and verified_sha != expected_vllm_corpus_sha:
            errors.append(
                f"{plugin_name}: product-contract.json verified_commit "
                f"{verified_sha[:8]} != {expected_vllm_corpus_sha[:8]}"
            )
            return
        if vllm_repo is not None:
            anc = _run_cmd(
                ["git", "merge-base", "--is-ancestor", verified_sha, expected_vllm_corpus_sha],
                cwd=vllm_repo,
            )
            if anc.returncode != 0:
                errors.append(
                    f"{plugin_name}: product-contract.json verified_commit {verified_sha[:8]} "
                    f"is not an ancestor of knowledge-vllm-ascend {expected_vllm_corpus_sha[:8]}"
                )

    core_seven = ("knowledge", "remote-dev", "diagnostics", "debugger", "profiler", "sim", "coordinator")
    codex_dir = _resolve_repo("mindie-agent-codex", siblings_roots)
    if codex_dir is not None:
        pyp = (codex_dir / "plugins/mindie-agent/pyproject.toml").read_text(encoding="utf-8")
        codex_pins = {
            comp_name: _extract_default_dep_pin(pyp, comp_name, uses_uv_sources=True)
            for comp_name in core_seven
        }
        for comp_name in core_seven:
            _check_pin_floor("mindie-agent-codex", comp_name, codex_pins[comp_name], "pyproject.toml")
        _check_uv_lock_default_deps(
            "mindie-agent-codex",
            codex_dir / "plugins/mindie-agent/uv.lock",
            "mindie-agent-codex",
            core_seven,
            codex_pins,
        )
        pc = json.loads((codex_dir / "plugins/mindie-agent/product-contract.json").read_text(encoding="utf-8"))
        _check_verified_commit("mindie-agent-codex", pc["publication"]["verified_commit"])

    cc_dir = _resolve_repo("mindie-agent-cc", siblings_roots)
    if cc_dir is not None:
        pyp = (cc_dir / "pyproject.toml").read_text(encoding="utf-8")
        cc_pins = {comp_name: _extract_default_dep_pin(pyp, comp_name) for comp_name in core_seven}
        for comp_name in core_seven:
            _check_pin_floor("mindie-agent-cc", comp_name, cc_pins[comp_name], "pyproject.toml")
        _check_uv_lock_default_deps(
            "mindie-agent-cc", cc_dir / "uv.lock", "mindie-agent-cc", core_seven, cc_pins
        )
        pc = json.loads((cc_dir / "product-contract.json").read_text(encoding="utf-8"))
        _check_verified_commit("mindie-agent-cc", pc["publication"]["verified_commit"])

    kimi_dir = _resolve_repo("mindie-agent-kimi", siblings_roots)
    if kimi_dir is not None:
        ao = (kimi_dir / "runtime/active-overrides.txt").read_text(encoding="utf-8")
        tr = (kimi_dir / "test-requirements.txt").read_text(encoding="utf-8")
        for comp_name in core_seven:
            _check_pin_floor(
                "mindie-agent-kimi", comp_name, _extract_pinned_sha(ao, comp_name), "runtime/active-overrides.txt"
            )
        for comp_name in ("debugger", "profiler", "sim", "coordinator"):
            _check_pin_floor(
                "mindie-agent-kimi", comp_name, _extract_pinned_sha(tr, comp_name), "test-requirements.txt"
            )

    dsh_dir = _resolve_repo("mindie-agent-dsh", siblings_roots)
    if dsh_dir is not None:
        pyp = (dsh_dir / "pyproject.toml").read_text(encoding="utf-8")
        rr = (dsh_dir / "runtime-requirements.txt").read_text(encoding="utf-8")
        dsh_pins = {comp_name: _extract_default_dep_pin(pyp, comp_name) for comp_name in core_seven}
        for comp_name in core_seven:
            _check_pin_floor("mindie-agent-dsh", comp_name, dsh_pins[comp_name], "pyproject.toml")
            _check_pin_floor(
                "mindie-agent-dsh", comp_name, _extract_pinned_sha(rr, comp_name), "runtime-requirements.txt"
            )
        _check_uv_lock_default_deps(
            "mindie-agent-dsh", dsh_dir / "uv.lock", "mindie-agent-dsh-runtime", core_seven, dsh_pins
        )

    for plugin_name in ("mindie-agent-agy", "mindie-agent-wb", "mindie-agent-oc"):
        p_dir = _resolve_repo(plugin_name, siblings_roots)
        if p_dir is None:
            continue
        pyp = (p_dir / "pyproject.toml").read_text(encoding="utf-8")
        all_eight = (*core_seven, "npu-top")
        p_pins = {
            comp_name: _extract_default_dep_pin(pyp, comp_name, uses_uv_sources=True)
            for comp_name in all_eight
        }
        for comp_name in all_eight:
            _check_pin_floor(plugin_name, comp_name, p_pins[comp_name], "pyproject.toml")
        if plugin_name == "mindie-agent-oc":
            _check_uv_lock_default_deps(
                plugin_name, p_dir / "uv.lock", plugin_name, all_eight, p_pins
            )
        pc = json.loads((p_dir / "product-contract.json").read_text(encoding="utf-8"))
        pub_vc = ((pc.get("publication") or {}).get("verified_commit") or "")
        if pub_vc:
            _check_verified_commit(plugin_name, pub_vc)
        comps = pc.get("components") or {}
        expected_map = {
            "mindie-knowledge": comp_entries["knowledge"]["version"],
            "remote-dev": comp_entries["remote-dev"]["version"],
            "mindie-diagnostics": comp_entries["diagnostics"]["version"],
            "mindie-coordinator": comp_entries["coordinator"]["version"],
            "mindie-profiler": comp_entries["profiler"]["version"],
            "mindie-sim": comp_entries["sim"]["version"],
            "npu-top": comp_entries["npu-top"]["version"],
        }
        if plugin_name in {"mindie-agent-wb", "mindie-agent-oc"} or "mindie-debugger" in comps:
            expected_map["mindie-debugger"] = comp_entries["debugger"]["version"]
        for pkg, ch_ver in expected_map.items():
            pin_ver = str(comps.get(pkg) or "")
            if not pin_ver:
                errors.append(f"{plugin_name}: product-contract.json missing {pkg}")
            elif strict_lockstep and pin_ver != ch_ver:
                errors.append(f"{plugin_name}: product-contract.json {pkg}={pin_ver!r} != {ch_ver!r}")
            elif not independent and _parse_semver(pin_ver) > _parse_semver(ch_ver):
                errors.append(
                    f"{plugin_name}: product-contract.json baseline {pkg}={pin_ver!r} > channel {ch_ver!r}"
                )

    if independent and verify_formal_releases and independent_dependencies:
        errors.extend(verify_github_releases({"components": independent_dependencies}, verify_commits=True))
    return errors


def verify_flexible_component_compatibility(siblings_roots: list[Path]) -> list[str]:
    """Verify that the latest shared component code is API-compatible with all 7 host plugins."""
    return verify_flexible_component_compatibility_impl(
        siblings_roots,
        ensure_knowledge_importable=_ensure_knowledge_importable,
        windowless_check=verify_windows_windowless_spawns,
    )


def verify_local_host_compatibility(siblings_roots: list[Path]) -> list[str]:
    return verify_local_host_compatibility_impl(
        siblings_roots,
        ensure_knowledge_importable=_ensure_knowledge_importable,
        which_fn=lambda name: which_native(name, os_mod=os, shutil_mod=shutil),
        run_cmd=_run_cmd,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-scope", choices=("independent", "product"), default="independent",
        help="Independent releases allow formal dependency advances and scoped docs; product checks the recorded combination")
    parser.add_argument("--release-repo", action="append", default=[],
                        help="Repository to check against its own source version; repeat for independent releases")
    parser.add_argument(
        "--channel",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "channels" / "0.1.json",
        help="Path to channels/0.1.json",
    )
    parser.add_argument(
        "--siblings-root",
        type=Path,
        action="append",
        default=[],
        help="Directory containing sibling MindIE Agent repository checkouts (may be passed multiple times)",
    )
    parser.add_argument(
        "--require-siblings",
        action="store_true",
        help="Fail if any expected sibling repository checkout is missing",
    )
    parser.add_argument(
        "--strict-lockstep",
        action="store_true",
        help="Require plugin baseline pins to equal channel component SHAs (by default, flexible component updates allow plugin_baseline <= channel_component)",
    )
    parser.add_argument(
        "--verify-local-hosts",
        action="store_true",
        help="Verify that installed local host CLIs (Codex/ChatGPT Desktop, Claude, Kimi) are covered by harness-compatibility.json",
    )
    parser.add_argument(
        "--verify-github-releases",
        action="store_true",
        help="Verify channel/pinned releases and run the production consumer against every latest component head",
    )
    args = parser.parse_args(argv)
    if args.release_scope == "independent" and not args.release_repo:
        parser.error("independent releases require --release-repo; use --release-scope product for a product combination")
    if args.release_scope == "product" and args.release_repo:
        parser.error("--release-repo applies only to independent releases")

    main_repo = args.channel.resolve().parents[1]
    siblings_roots = list(args.siblings_root)
    if not siblings_roots:
        default_parent = main_repo.parent
        if default_parent not in siblings_roots:
            siblings_roots.append(default_parent)
        if os.name != "nt":
            volumes_code = Path("/Volumes/data/code")
            if volumes_code.is_dir() and volumes_code not in siblings_roots:
                siblings_roots.append(volumes_code)

    manifest = json.loads(args.channel.read_text(encoding="utf-8"))
    mode = "strict-lockstep" if args.strict_lockstep else "flexible-component-update"

    r1_errors = verify_channel_schema(manifest, main_repo)
    r2_errors = verify_corpora(main_repo, manifest, siblings_roots, require_siblings=args.require_siblings)
    r3_errors = verify_components_and_plugins(
        manifest,
        siblings_roots,
        require_siblings=args.require_siblings,
        strict_lockstep=args.strict_lockstep,
        independent=args.release_scope == "independent",
        verify_formal_releases=args.verify_github_releases,
    )
    if args.strict_lockstep:
        r3_errors.extend(verify_unreleased_plugin_main(manifest, siblings_roots))
    if args.verify_github_releases:
        r3_errors.extend(verify_github_releases(manifest))
        for ind_name in dict.fromkeys(args.release_repo):
            if ind_name in INDEPENDENT_PLUGINS:
                ind_dir = _resolve_repo(ind_name, siblings_roots)
                if ind_dir is not None:
                    head_sha = _run_cmd(["git", "rev-parse", "HEAD"], cwd=ind_dir).stdout.strip()
                    ind_ver = source_version(ind_dir, ind_name)
                    r3_errors.extend(
                        verify_github_releases(
                            {"components": {ind_name: {"repository": f"mindie-agent/{ind_name}", "version": ind_ver, "commit": head_sha}}},
                            verify_commits=True,
                        )
                    )
    r4_errors = verify_flexible_component_compatibility(siblings_roots)
    if args.verify_github_releases:
        if _ensure_knowledge_importable(siblings_roots):
            r3_errors.extend(verify_current_release_heads())
        else:
            r3_errors.append("latest component verification requires the real knowledge release consumer")
    r5_errors = verify_local_host_compatibility(siblings_roots) if args.verify_local_hosts else []
    r6_errors = verify_release_doc_hygiene(
        main_repo,
        manifest,
        siblings_roots,
        scope=args.release_scope,
        release_repos=args.release_repo,
        require_siblings=args.require_siblings,
        run=_run_cmd,
    )

    checklist_rows = [
        ("R1", f"Channel Schema & Release Track ({mode})", r1_errors),
        ("R2", "Knowledge Corpus Monotonic Revisions & Validator Floor", r2_errors),
        ("R3", "Component & Plugin Tag/Commit/Release Integrity", r3_errors),
        ("R4", "Seven-Host Cross-Version Component Compatibility", r4_errors),
        (
            "R5",
            "Local Active Host CLI Compatibility Coverage"
            + ("" if args.verify_local_hosts else " (skipped; pass --verify-local-hosts)"),
            r5_errors,
        ),
        ("R6", f"Release Documentation & LF Hygiene ({args.release_scope}"
         + (": " + ", ".join(args.release_repo) if args.release_repo else "") + ")", r6_errors),
    ]

    for code, label, item_errors in checklist_rows:
        mark = "x" if not item_errors else " "
        print(f"- [{mark}] **{code}. {label}**")

    errors = r1_errors + r2_errors + r3_errors + r4_errors + r5_errors + r6_errors
    if errors:
        for err in errors:
            print(f"[auto-update-readiness:FAIL] {err}", file=sys.stderr)
        return 1

    print(
        f"[auto-update-readiness:OK] ({mode}, R6={args.release_scope}) channels/0.1.json (v{manifest.get('current_patch_version')}), "
        f"{len(manifest.get('corpora', {}))} corpora, and {len(manifest.get('components', {}))} components/plugins verified."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

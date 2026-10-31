#!/usr/bin/env python3
"""Pre-release and CI gate for automatic update readiness across MindIE Agent.

[Role]
Verifies that `channels/0.1.json`, all 7 graded `knowledge-*` domain corpora, all 7
shared runtime components, and all 5 native host plugins satisfy the invariants
required for zero-intervention background automatic updates (`feed_sync` and
plugin/component release selection).

[Invariants]
- Every `knowledge-*` unit modification across channel history and `HEAD` must
  monotonically advance its integer `revision` whenever `content_sha256` changes.
- Every `knowledge-*` corpus `publication-contract.json` `validator.revision` must
  match the channel's `components.knowledge.commit`, and `routing-manifest.json` /
  `shard-topology.json` must match `units/*.md`.
- Every host plugin's pinned component revisions (`pyproject.toml`, `uv.lock`,
  `runtime/active-overrides.txt`, `runtime-requirements.txt`, `product-contract.json`,
  `harness-compatibility.json`) must align with `channels/0.1.json`, and
  `harness-compatibility.json` must cover active local host CLI versions.

[Timeouts & Locks]
- Subprocess calls (`git`, host `--version` probes) use a strict `10s` timeout.
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

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_CORPORA = (
    "knowledge-infer-core",
    "knowledge-operators",
    "knowledge-vllm-ascend",
    "knowledge-infer-distributed",
    "knowledge-infer-observability",
    "knowledge-infer-ops-compat",
    "knowledge-agent-engineering",
)
EXPECTED_SHARED_COMPONENTS = (
    "diagnostics",
    "profiler",
    "sim",
    "npu-top",
    "remote-dev",
    "knowledge",
    "coordinator",
)
EXPECTED_PLUGINS = (
    "mindie-agent-codex",
    "mindie-agent-cc",
    "mindie-agent-kimi",
    "mindie-agent-dsh",
    "mindie-agent-agy",
)


def _run_cmd(argv: list[str], *, cwd: Path | None = None, timeout: float = 10.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        check=False,
    )


def _resolve_repo(repo_name: str, siblings_roots: list[Path]) -> Path | None:
    for root in siblings_roots:
        candidate = root / repo_name
        if (candidate / ".git").exists():
            return candidate
    return None


def verify_channel_schema(manifest: dict) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema") != "mindie-release-channel/1":
        errors.append(f"channels/0.1.json: unexpected schema {manifest.get('schema')!r}")
    corpora = manifest.get("corpora") or {}
    for name in EXPECTED_CORPORA:
        entry = corpora.get(name)
        if not isinstance(entry, dict):
            errors.append(f"channels/0.1.json: missing corpus {name}")
            continue
        commit = str(entry.get("commit") or "")
        if not SHA_RE.fullmatch(commit):
            errors.append(f"channels/0.1.json: corpus {name} invalid commit {commit!r}")
        if not isinstance(entry.get("units"), int) or entry["units"] <= 0:
            errors.append(f"channels/0.1.json: corpus {name} invalid units {entry.get('units')!r}")

    components = manifest.get("components") or {}
    for name in (*EXPECTED_SHARED_COMPONENTS, "mindie-bench", *EXPECTED_PLUGINS):
        entry = components.get(name)
        if not isinstance(entry, dict):
            errors.append(f"channels/0.1.json: missing component/plugin {name}")
            continue
        version = str(entry.get("version") or "")
        tag = str(entry.get("tag") or "")
        commit = str(entry.get("commit") or "")
        revision = str(entry.get("revision") or "")
        if not version or tag != f"v{version}":
            errors.append(f"channels/0.1.json: {name} tag {tag!r} != v{version}")
        if not SHA_RE.fullmatch(commit) or commit != revision:
            errors.append(f"channels/0.1.json: {name} commit/revision mismatch ({commit!r} vs {revision!r})")
    return errors


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


def _ensure_knowledge_importable(siblings_roots: list[Path]) -> bool:
    knowledge_repo = _resolve_repo("knowledge", siblings_roots)
    if knowledge_repo is not None:
        if str(knowledge_repo) not in sys.path:
            sys.path.insert(0, str(knowledge_repo))
        for sp in sorted((knowledge_repo / ".venv/lib").glob("python*/site-packages")):
            if str(sp) not in sys.path:
                sys.path.append(str(sp))
    try:
        import mindie_knowledge.graded.maintenance  # noqa: F401
        import mindie_knowledge.releases  # noqa: F401
        return True
    except ImportError:
        return False


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

    expected_validator_rev = manifest["components"]["knowledge"]["commit"]
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
            if val_rev != expected_validator_rev:
                errors.append(
                    f"{corpus_name}: publication-contract.json validator.revision {val_rev} "
                    f"!= channels/0.1.json knowledge commit {expected_validator_rev}"
                )

        report = build_routing_index(repo_dir, check=True)
        if not report.get("ok"):
            errors.append(f"{corpus_name}: build_routing_index(check=True) failed: {report.get('errors')}")
        if report.get("unit_count") != entry["units"]:
            errors.append(
                f"{corpus_name}: channels/0.1.json units {entry['units']} != actual {report.get('unit_count')}"
            )

        # Verify unit semantic revision monotonicity between baseline channel commits and HEAD
        history = _historical_corpus_commits(main_repo, corpus_name)
        if head_sha and (not history or history[-1] != head_sha):
            history.append(head_sha)
        baseline_commits = [ history[0], *history[-2:] ] if len(history) > 2 else history
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


def verify_components_and_plugins(
    manifest: dict,
    siblings_roots: list[Path],
    *,
    require_siblings: bool,
) -> list[str]:
    errors: list[str] = []
    comp_entries = manifest.get("components") or {}
    expected_knowledge_sha = comp_entries["knowledge"]["commit"]
    expected_remote_sha = comp_entries["remote-dev"]["commit"]
    expected_diag_sha = comp_entries["diagnostics"]["commit"]
    expected_coord_sha = comp_entries["coordinator"]["commit"]
    expected_prof_sha = comp_entries["profiler"]["commit"]
    expected_sim_sha = comp_entries["sim"]["commit"]
    expected_vllm_corpus_sha = manifest["corpora"]["knowledge-vllm-ascend"]["commit"]

    for name, entry in comp_entries.items():
        repo_dir = _resolve_repo(name, siblings_roots)
        if repo_dir is None:
            if require_siblings:
                errors.append(f"{name}: sibling checkout not found in {siblings_roots}")
            continue
        tag = entry["tag"]
        tag_res = _run_cmd(["git", "rev-parse", f"{tag}^{{commit}}"], cwd=repo_dir)
        if tag_res.returncode != 0:
            errors.append(f"{name}: tag {tag} not found in local checkout {repo_dir}")
        elif tag_res.stdout.strip() != entry["commit"]:
            errors.append(
                f"{name}: tag {tag} resolves to {tag_res.stdout.strip()}, "
                f"expected {entry['commit']} in channels/0.1.json"
            )

    # Check plugin-specific runtime component pins
    codex_dir = _resolve_repo("mindie-agent-codex", siblings_roots)
    if codex_dir is not None:
        pyp = (codex_dir / "plugins/mindie-agent/pyproject.toml").read_text(encoding="utf-8")
        for label, sha in (
            ("knowledge", expected_knowledge_sha),
            ("remote-dev", expected_remote_sha),
            ("diagnostics", expected_diag_sha),
        ):
            if sha not in pyp:
                errors.append(f"mindie-agent-codex: pyproject.toml does not pin {label} to {sha}")
        pc = json.loads((codex_dir / "plugins/mindie-agent/product-contract.json").read_text(encoding="utf-8"))
        if pc["publication"]["verified_commit"] != expected_vllm_corpus_sha:
            errors.append(
                f"mindie-agent-codex: product-contract.json verified_commit "
                f"{pc['publication']['verified_commit']} != {expected_vllm_corpus_sha}"
            )

    cc_dir = _resolve_repo("mindie-agent-cc", siblings_roots)
    if cc_dir is not None:
        pyp = (cc_dir / "pyproject.toml").read_text(encoding="utf-8")
        for label, sha in (
            ("knowledge", expected_knowledge_sha),
            ("remote-dev", expected_remote_sha),
            ("diagnostics", expected_diag_sha),
            ("profiler", expected_prof_sha),
            ("sim", expected_sim_sha),
            ("coordinator", expected_coord_sha),
        ):
            if sha not in pyp:
                errors.append(f"mindie-agent-cc: pyproject.toml does not pin {label} to {sha}")
        pc = json.loads((cc_dir / "product-contract.json").read_text(encoding="utf-8"))
        if pc["publication"]["verified_commit"] != expected_vllm_corpus_sha:
            errors.append(
                f"mindie-agent-cc: product-contract.json verified_commit "
                f"{pc['publication']['verified_commit']} != {expected_vllm_corpus_sha}"
            )

    kimi_dir = _resolve_repo("mindie-agent-kimi", siblings_roots)
    if kimi_dir is not None:
        ao = (kimi_dir / "runtime/active-overrides.txt").read_text(encoding="utf-8")
        tr = (kimi_dir / "test-requirements.txt").read_text(encoding="utf-8")
        for label, sha in (
            ("knowledge", expected_knowledge_sha),
            ("remote-dev", expected_remote_sha),
            ("diagnostics", expected_diag_sha),
        ):
            if sha not in ao:
                errors.append(f"mindie-agent-kimi: runtime/active-overrides.txt does not pin {label} to {sha}")
        for label, sha in (
            ("profiler", expected_prof_sha),
            ("sim", expected_sim_sha),
            ("coordinator", expected_coord_sha),
        ):
            if sha not in tr:
                errors.append(f"mindie-agent-kimi: test-requirements.txt does not pin {label} to {sha}")

    dsh_dir = _resolve_repo("mindie-agent-dsh", siblings_roots)
    if dsh_dir is not None:
        pyp = (dsh_dir / "pyproject.toml").read_text(encoding="utf-8")
        rr = (dsh_dir / "runtime-requirements.txt").read_text(encoding="utf-8")
        hc = json.loads((dsh_dir / "harness-compatibility.json").read_text(encoding="utf-8"))
        for label, sha in (
            ("knowledge", expected_knowledge_sha),
            ("remote-dev", expected_remote_sha),
            ("diagnostics", expected_diag_sha),
            ("profiler", expected_prof_sha),
            ("sim", expected_sim_sha),
            ("coordinator", expected_coord_sha),
        ):
            if sha not in pyp:
                errors.append(f"mindie-agent-dsh: pyproject.toml does not pin {label} to {sha}")
        for label, sha in (
            ("knowledge", expected_knowledge_sha),
            ("remote-dev", expected_remote_sha),
            ("diagnostics", expected_diag_sha),
        ):
            if sha not in rr:
                errors.append(f"mindie-agent-dsh: runtime-requirements.txt does not pin {label} to {sha}")
        rc = hc.get("runtime_components") or {}
        if (rc.get("mindie-knowledge") or {}).get("commit") != expected_knowledge_sha:
            errors.append("mindie-agent-dsh: harness-compatibility.json mindie-knowledge commit mismatch")
        if (rc.get("remote-dev") or {}).get("commit") != expected_remote_sha:
            errors.append("mindie-agent-dsh: harness-compatibility.json remote-dev commit mismatch")

    agy_dir = _resolve_repo("mindie-agent-agy", siblings_roots)
    if agy_dir is not None:
        pc = json.loads((agy_dir / "product-contract.json").read_text(encoding="utf-8"))
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
        for pkg, exp_ver in expected_map.items():
            if comps.get(pkg) != exp_ver:
                errors.append(f"mindie-agent-agy: product-contract.json {pkg}={comps.get(pkg)!r} != {exp_ver!r}")

    return errors


def _extract_semver(raw: str) -> str | None:
    m = re.search(r"\b(\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)\b", raw)
    return m.group(1) if m else None


def verify_local_host_compatibility(siblings_roots: list[Path]) -> list[str]:
    errors: list[str] = []
    if not _ensure_knowledge_importable(siblings_roots):
        return ["mindie_knowledge.releases unavailable for host compatibility verification"]
    from mindie_knowledge.releases import supports_harness

    # 1. Codex (both PATH codex and ChatGPT Desktop bundled codex-cli if present)
    codex_dir = _resolve_repo("mindie-agent-codex", siblings_roots)
    if codex_dir is not None:
        compat = json.loads(
            (codex_dir / "plugins/mindie-agent/harness-compatibility.json").read_text(encoding="utf-8")
        )
        codex_bins: list[str] = []
        which_codex = shutil.which("codex")
        if which_codex:
            codex_bins.append(which_codex)
        desktop_codex = "/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex"
        if os.path.isfile(desktop_codex) and desktop_codex not in codex_bins:
            codex_bins.append(desktop_codex)
        cfg_file = Path.home() / ".config/mindie-agent/codex.json"
        if cfg_file.is_file():
            try:
                cfg_bin = ((json.loads(cfg_file.read_text(encoding="utf-8")).get("native") or {}).get("MINDIE_CODEX_BIN"))
                if isinstance(cfg_bin, str) and os.path.isfile(cfg_bin) and cfg_bin not in codex_bins:
                    codex_bins.append(cfg_bin)
            except (OSError, ValueError):
                pass
        for binary in codex_bins:
            res = _run_cmd([binary, "--version"])
            ver = _extract_semver(res.stdout + "\n" + res.stderr)
            if ver and not supports_harness(compat, harness_name="codex", harness_version=ver):
                errors.append(
                    f"mindie-agent-codex: harness-compatibility.json does not support installed Codex CLI "
                    f"{ver} ({binary})"
                )

    # 2. Claude Code
    cc_dir = _resolve_repo("mindie-agent-cc", siblings_roots)
    which_claude = shutil.which("claude")
    if cc_dir is not None and which_claude:
        compat = json.loads((cc_dir / "harness-compatibility.json").read_text(encoding="utf-8"))
        res = _run_cmd([which_claude, "--version"])
        ver = _extract_semver(res.stdout + "\n" + res.stderr)
        if ver and not supports_harness(compat, harness_name="claude-code", harness_version=ver):
            errors.append(f"mindie-agent-cc: harness-compatibility.json does not support installed claude {ver}")

    # 3. Kimi Code
    kimi_dir = _resolve_repo("mindie-agent-kimi", siblings_roots)
    which_kimi = shutil.which("kimi")
    if kimi_dir is not None and which_kimi:
        compat = json.loads((kimi_dir / "harness-compatibility.json").read_text(encoding="utf-8"))
        res = _run_cmd([which_kimi, "--version"])
        ver = _extract_semver(res.stdout + "\n" + res.stderr)
        if ver and not supports_harness(compat, harness_name="kimi-code", harness_version=ver):
            errors.append(f"mindie-agent-kimi: harness-compatibility.json does not support installed kimi {ver}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
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
        "--verify-local-hosts",
        action="store_true",
        help="Verify that installed local host CLIs (Codex/ChatGPT Desktop, Claude, Kimi) are covered by harness-compatibility.json",
    )
    args = parser.parse_args()

    main_repo = args.channel.resolve().parents[1]
    siblings_roots = list(args.siblings_root)
    default_parent = main_repo.parent
    if default_parent not in siblings_roots:
        siblings_roots.append(default_parent)
    volumes_code = Path("/Volumes/data/code")
    if volumes_code.is_dir() and volumes_code not in siblings_roots:
        siblings_roots.append(volumes_code)

    manifest = json.loads(args.channel.read_text(encoding="utf-8"))
    errors: list[str] = []
    errors.extend(verify_channel_schema(manifest))
    errors.extend(
        verify_corpora(main_repo, manifest, siblings_roots, require_siblings=args.require_siblings)
    )
    errors.extend(
        verify_components_and_plugins(manifest, siblings_roots, require_siblings=args.require_siblings)
    )
    if args.verify_local_hosts:
        errors.extend(verify_local_host_compatibility(siblings_roots))

    if errors:
        for err in errors:
            print(f"[auto-update-readiness:FAIL] {err}", file=sys.stderr)
        return 1

    print(
        f"[auto-update-readiness:OK] channels/0.1.json (v{manifest.get('current_patch_version')}), "
        f"{len(manifest.get('corpora', {}))} corpora, and {len(manifest.get('components', {}))} components/plugins verified."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

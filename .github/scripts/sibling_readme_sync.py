#!/usr/bin/env python3
"""Synchronize and verify version badges, wheel URLs, and pins across docs and sibling READMEs.

[Role]
Shared helper imported by `sync_org_versions.py` and `check_auto_update_readiness.py` to
synchronize and verify version references across `mindie-agent/docs/*.md` and all 15
sibling component/plugin repositories' `README.md`, `README.en.md`, `docs/README.md`,
and `docs/README.en.md`.

[Invariants]
- This is a product-combination synchronizer. `channels/0.1.json` owns that
  combination's versions; it does not own independently released current versions.
- Every present sibling component/plugin repository must include both `README.md` and
  `README.en.md`, each carrying a `shields.io/badge/[Rr]elease-v<version>` badge that
  matches its `channels/0.1.json` version.
- All wheel download URLs, paired `mindie-agent` patch versions, and cross-component
  package version pins in `README*.md` and `docs/README*.md` must match `channels/0.1.json`,
  and all inspected markdown files must use Unix LF (`\n`) line endings.

[Timeouts & Locks]
- Documentation transforms are local and lock-free. Release metadata reads have
  15s subprocess budgets; optional remote Tag dereferencing shares another 15s.

[Side-Effect Policy]
- In `write=False` (`--check`) mode, strictly read-only. In `write=True` (`--write`) mode,
  rewrites only out-of-sync markdown files with UTF-8 encoding and Unix LF (`\n`) line endings.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.parse
from typing import Callable

PACKAGE_INFO: dict[str, tuple[str, str]] = {
    "diagnostics": ("mindie-diagnostics", "mindie_diagnostics"),
    "debugger": ("mindie-debugger", "mindie_debugger"),
    "profiler": ("mindie-profiler", "mindie_profiler"),
    "sim": ("mindie-sim", "mindie_sim"),
    "npu-top": ("npu-top", "npu_top"),
    "remote-dev": ("remote-dev", "remote_dev"),
    "knowledge": ("mindie-knowledge", "mindie_knowledge"),
    "coordinator": ("mindie-coordinator", "mindie_coordinator"),
    "mindie-bench": ("mindie-bench", "mindie_bench"),
}

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_CORPORA = (
    "knowledge-infer-core",
    "knowledge-operators",
    "knowledge-vllm-ascend",
    "knowledge-xllm",
    "knowledge-mindie-sd",
    "knowledge-infer-distributed",
    "knowledge-infer-observability",
    "knowledge-infer-ops-compat",
    "knowledge-agent-engineering",
)
EXPECTED_SHARED_COMPONENTS = (
    "diagnostics",
    "debugger",
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
    "mindie-agent-wb",
)

# The synchronizer and CI change routing share the same owned document set.
PRODUCT_DOC_PATHS = (
    "docs/README.md", "docs/README.en.md", "docs/simulation-system.md",
    "docs/profiler-sim-structure.md", "docs/simulation-consumer-migration.md",
    "docs/mechanism-first-performance-modeling-design.md",
    "docs/next-steps.md", "docs/next-steps.en.md",
)


def verify_channel_schema(manifest: dict, main_repo: Path) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema") != "mindie-release-channel/1":
        errors.append(f"channels/0.1.json: unexpected schema {manifest.get('schema')!r}")
    if not manifest.get("independent_update_allowed"):
        errors.append("channels/0.1.json: independent_update_allowed must be true")
    cpv = str(manifest.get("current_patch_version") or "")
    if not cpv:
        errors.append("channels/0.1.json: missing current_patch_version")
    expected_rn = f"docs/releases/{cpv}.md"
    expected_rn_en = f"docs/releases/{cpv}.en.md"
    if manifest.get("release_notes") != expected_rn:
        errors.append(f"channels/0.1.json: release_notes {manifest.get('release_notes')!r} != {expected_rn!r}")
    if manifest.get("release_notes_en") != expected_rn_en:
        errors.append(f"channels/0.1.json: release_notes_en {manifest.get('release_notes_en')!r} != {expected_rn_en!r}")

    patch_releases = manifest.get("patch_releases") or []
    if not isinstance(patch_releases, list) or not patch_releases:
        errors.append("channels/0.1.json: patch_releases must be a non-empty list")
    else:
        latest_patch = patch_releases[-1]
        if str(latest_patch.get("patch_version") or "") != cpv:
            errors.append(
                f"channels/0.1.json: patch_releases[-1].patch_version "
                f"{latest_patch.get('patch_version')!r} != current_patch_version {cpv!r}"
            )

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
        if not entry.get("independent_update_allowed"):
            errors.append(f"channels/0.1.json: {name} must set independent_update_allowed=true")

    kb = str(((manifest.get("update_policy") or {}).get("implementation_status") or {}).get("known_boundaries") or "")
    kb_tokens = [
        f"The {cpv} channel pins",
        *(f"{k} {components[k]['version']}" for k in (*EXPECTED_SHARED_COMPONENTS, "mindie-bench") if k in components),
        f"Codex {components.get('mindie-agent-codex', {}).get('version', '')}",
        f"Claude Code {components.get('mindie-agent-cc', {}).get('version', '')}",
        f"Kimi {components.get('mindie-agent-kimi', {}).get('version', '')}",
        f"DSH {components.get('mindie-agent-dsh', {}).get('version', '')}",
        f"Google Antigravity {components.get('mindie-agent-agy', {}).get('version', '')}",
        f"Tencent WorkBuddy {components.get('mindie-agent-wb', {}).get('version', '')}",
    ]
    for token in kb_tokens:
        if token and token not in kb:
            errors.append(f"channels/0.1.json: known_boundaries missing or out of sync for {token!r}")

    for rel_file in (expected_rn, expected_rn_en):
        rel_path = main_repo / rel_file
        if not rel_path.is_file():
            errors.append(f"{rel_file}: release notes file not found")
            continue
        rel_txt = rel_path.read_text(encoding="utf-8")
        for name, entry in components.items():
            ver = entry.get("version", "")
            sha = entry.get("commit", "")
            row_pat = rf"\|\s*`{re.escape(name)}`\s*\|[^|\n]+\|\s*`{re.escape(str(ver))}`\s*\|\s*`{re.escape(str(sha))}`\s*\|"
            if not re.search(row_pat, rel_txt):
                errors.append(f"{rel_file}: table row for {name} does not match channel ({ver} / {sha[:8]})")
    errors.extend(verify_product_benchmark_manifest(manifest, main_repo))
    return errors


def verify_product_benchmark_manifest(manifest: dict, main_repo: Path) -> list[str]:
    """Catch missing or stale product publication inputs before a tag is created."""
    version = str(manifest.get("current_patch_version") or "")
    path = main_repo / "docs" / "releases" / version / "benchmark-manifest.json"
    try:
        benchmark = json.loads(path.read_text(encoding="utf-8"))
    except TimeoutError:
        raise
    except (OSError, ValueError) as exc:
        return [f"{path.relative_to(main_repo)}: publication input unavailable ({type(exc).__name__})"]
    if (not isinstance(benchmark, dict) or benchmark.get("schema_version") != "mindie-release-manifest/1"
            or benchmark.get("product_version") != version):
        return [f"{path.relative_to(main_repo)}: schema or product version differs from channel"]
    rows = benchmark.get("repositories")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        return [f"{path.relative_to(main_repo)}: repositories must be a list of release targets"]
    expected = {item["repository"]: (item["version"], item["commit"])
                for item in (manifest.get("components") or {}).values()}
    actual = {row.get("repository"): (row.get("version"), row.get("revision")) for row in rows}
    if len(actual) != len(rows) or actual != expected:
        return [f"{path.relative_to(main_repo)}: repository versions and revisions differ from channel"]
    return []


def default_siblings_roots(repo_root: Path, extra_roots: list[Path] | None = None) -> list[Path]:
    roots: list[Path] = []
    for candidate in (*(extra_roots or ()), repo_root.parent, Path("/Volumes/data/code")):
        resolved = candidate.resolve()
        if resolved.is_dir() and resolved not in roots:
            roots.append(resolved)
    return roots


def resolve_sibling_repo(repo_name: str, siblings_roots: list[Path]) -> Path | None:
    for root in siblings_roots:
        candidate = root / repo_name
        if (candidate / ".git").exists():
            return candidate
    return None


def process_markdown_file(path: Path, transform: Callable[[str], str], write: bool) -> list[str]:
    if not path.is_file():
        return [f"Missing target file: {path}"]
    raw_bytes = path.read_bytes()
    has_crlf = b"\r\n" in raw_bytes
    original = raw_bytes.decode("utf-8")
    updated = transform(original.replace("\r\n", "\n")).replace("\r\n", "\n")
    if updated != original or has_crlf:
        if write:
            path.write_text(updated, encoding="utf-8", newline="\n")
            print(f"Updated {path}")
            return []
        reason = "CRLF line endings" if has_crlf and updated == original.replace("\r\n", "\n") else "Out-of-sync version block or pin"
        return [f"{reason} in {path} (product combination: run sync_org_versions.py --release-scope product --write)"]
    return []


def sync_docs_versions(repo_root: Path, m: dict, write: bool) -> list[str]:
    c = m["components"]
    cpv = m["current_patch_version"]
    sim_v = c["sim"]["version"]
    prof_v = c["profiler"]["version"]
    know_v = c["knowledge"]["version"]
    rdev_v = c["remote-dev"]["version"]
    diag_v = c["diagnostics"]["version"]
    dbg_v = c["debugger"]["version"]
    ntop_v = c["npu-top"]["version"]
    coord_v = c["coordinator"]["version"]
    bench_v = c["mindie-bench"]["version"]
    codex_v = c["mindie-agent-codex"]["version"]
    cc_v = c["mindie-agent-cc"]["version"]
    kimi_v = c["mindie-agent-kimi"]["version"]
    dsh_v = c["mindie-agent-dsh"]["version"]
    agy_v = c["mindie-agent-agy"]["version"]
    wb_v = c["mindie-agent-wb"]["version"]

    errors: list[str] = []

    def _transform_docs_readme(txt: str) -> str:
        return re.sub(
            r"\| \[(?:面向 Agent 的通用性能建模系统|General Performance Modeling System)\]\(simulation-system\.md\)([^\n]*?)`mindie-sim v[0-9.]+`",
            lambda match: match.group(0).rsplit("`mindie-sim v", 1)[0] + f"`mindie-sim v{sim_v}`",
            txt,
        )

    def _transform_sim_doc(txt: str) -> str:
        txt = re.sub(r"当前正式版本 `v[0-9.]+`", f"当前正式版本 `v{sim_v}`", txt)
        txt = re.sub(r"`mindie-sim v[0-9.]+`", f"`mindie-sim v{sim_v}`", txt)
        return txt

    def _transform_prof_sim_doc(txt: str) -> str:
        txt = re.sub(
            r"\[`mindie-profiler`\]\(https://github\.com/mindie-agent/profiler\)（`v[0-9.]+`）与 \[`mindie-sim`\]\(https://github\.com/mindie-agent/sim\)（`v[0-9.]+`）",
            f"[`mindie-profiler`](https://github.com/mindie-agent/profiler)（`v{prof_v}`）与 [`mindie-sim`](https://github.com/mindie-agent/sim)（`v{sim_v}`）",
            txt,
        )
        txt = re.sub(r"`mindie-profiler v[0-9.]+`", f"`mindie-profiler v{prof_v}`", txt)
        txt = re.sub(r"`mindie-sim v[0-9.]+`", f"`mindie-sim v{sim_v}`", txt)
        return txt

    def _transform_consumer_migration(txt: str) -> str:
        txt = re.sub(r"当前正式版 `v[0-9.]+`", f"当前正式版 `v{sim_v}`", txt)
        txt = re.sub(r"`mindie-profiler`（`v[0-9.]+`）", f"`mindie-profiler`（`v{prof_v}`）", txt)
        txt = re.sub(r"`mindie-bench`（`v[0-9.]+`）", f"`mindie-bench`（`v{bench_v}`）", txt)
        txt = re.sub(r"`mindie-sim v[0-9.]+`", f"`mindie-sim v{sim_v}`", txt)
        txt = re.sub(r"`mindie-profiler v[0-9.]+`", f"`mindie-profiler v{prof_v}`", txt)
        row_versions = {
            "mindie-agent-codex": codex_v,
            "mindie-agent-cc": cc_v,
            "mindie-agent-kimi": kimi_v,
            "mindie-agent-dsh": dsh_v,
            "mindie-agent-agy": agy_v,
            "mindie-agent-wb": wb_v,
            "mindie-profiler": prof_v,
            "mindie-debugger": dbg_v,
            "mindie-bench": bench_v,
        }
        for name, ver in row_versions.items():
            txt = re.sub(
                rf"(\| \*\*`{re.escape(name)}`\*\* \| )`v[0-9.]+`",
                rf"\1`v{ver}`",
                txt,
            )
        return txt

    def _transform_next_steps(txt: str, is_en: bool) -> str:
        suffix = ".en.md" if is_en else ".md"
        txt = re.sub(
            rf"`v0\.1\.1`–\[`v[0-9.]+`\]\(releases/[0-9.]+{re.escape(suffix)}\)",
            f"`v0.1.1`–[`v{cpv}`](releases/{cpv}{suffix})",
            txt,
        )
        pairs = [
            (r"`knowledge v[0-9.]+`", f"`knowledge v{know_v}`"),
            (r"`mindie-sim v[0-9.]+`", f"`mindie-sim v{sim_v}`"),
            (r"`mindie-profiler v[0-9.]+`", f"`mindie-profiler v{prof_v}`"),
            (r"`remote-dev v[0-9.]+`", f"`remote-dev v{rdev_v}`"),
            (r"`diagnostics v[0-9.]+`", f"`diagnostics v{diag_v}`"),
            (r"`debugger v[0-9.]+`", f"`debugger v{dbg_v}`"),
            (r"`mindie-debugger v[0-9.]+`", f"`mindie-debugger v{dbg_v}`"),
            (r"`npu-top v[0-9.]+`", f"`npu-top v{ntop_v}`"),
            (r"`coordinator v[0-9.]+`", f"`coordinator v{coord_v}`"),
            (r"`mindie-bench v[0-9.]+`", f"`mindie-bench v{bench_v}`"),
            (r"`Codex v[0-9.]+`", f"`Codex v{codex_v}`"),
            (r"`Claude Code v[0-9.]+`", f"`Claude Code v{cc_v}`"),
            (r"`Kimi v[0-9.]+`", f"`Kimi v{kimi_v}`"),
            (r"`DSH v[0-9.]+`", f"`DSH v{dsh_v}`"),
            (r"`Google Antigravity v[0-9.]+`", f"`Google Antigravity v{agy_v}`"),
            (r"`Tencent WorkBuddy v[0-9.]+`", f"`Tencent WorkBuddy v{wb_v}`"),
        ]
        for pat, repl in pairs:
            txt = re.sub(pat, repl, txt)
        return txt

    transforms = (
        _transform_docs_readme, _transform_docs_readme, _transform_sim_doc,
        _transform_prof_sim_doc, _transform_consumer_migration, _transform_sim_doc,
        lambda t: _transform_next_steps(t, False), lambda t: _transform_next_steps(t, True),
    )
    for relative_path, fn in zip(PRODUCT_DOC_PATHS, transforms, strict=True):
        errors.extend(process_markdown_file(repo_root / relative_path, fn, write))
    return errors


def transform_own_readme_versions(txt: str, repo_name: str, self_ver: str) -> str:
    """Shared self-version rules; no product version or peer dependency input."""
    txt = re.sub(
        r"(https://img\.shields\.io/badge/[Rr]elease-v)\d+\.\d+\.\d+(-[^\s\"')>]+)",
        rf"\g<1>{self_ver}\g<2>",
        txt,
    )
    txt = re.sub(r'(alt="Release v)\d+\.\d+\.\d+(")', rf"\g<1>{self_ver}\g<2>", txt)
    txt = re.sub(
        rf"(--branch v)(?!0\.0\.)\d+\.\d+\.\d+( https://github\.com/mindie-agent/{re.escape(repo_name)}\.git)",
        rf"\g<1>{self_ver}\g<2>",
        txt,
    )
    txt = re.sub(rf"({re.escape(repo_name)}\.git#v)(?!0\.0\.)\d+\.\d+\.\d+", rf"\g<1>{self_ver}", txt)
    txt = re.sub(rf"({re.escape(repo_name)}\.git --ref v)(?!0\.0\.)\d+\.\d+\.\d+", rf"\g<1>{self_ver}", txt)
    txt = re.sub(
        rf"(https://github\.com/mindie-agent/{re.escape(repo_name)}/releases/tag/v)(?!0\.0\.)\d+\.\d+\.\d+",
        rf"\g<1>{self_ver}",
        txt,
    )
    txt = re.sub(
        rf"(\b{re.escape(repo_name)} v?)(?!0\.0\.)\d+\.\d+\.\d+\b",
        rf"\g<1>{self_ver}",
        txt,
    )
    for pat in (
        r"(当前正式版本为 `v?)(?!0\.0\.)\d+\.\d+\.\d+(`)",
        r"(当前正式版本\s*\[?`v?)(?!0\.0\.)\d+\.\d+\.\d+(`\]?)",
        r"(当前正式版 `v?)(?!0\.0\.)\d+\.\d+\.\d+(`)",
        r"(当前稳定版本：\[`v)(?!0\.0\.)\d+\.\d+\.\d+(`\])",
        r"([Cc]urrent [Rr]elease:\s*\[`v)(?!0\.0\.)\d+\.\d+\.\d+(`\])",
        r"(当前 `v?)(?!0\.0\.)\d+\.\d+\.\d+(`)",
        r"([Rr]elease `v?)(?!0\.0\.)\d+\.\d+\.\d+(`)",
        r"(正式版 `v)(?!0\.0\.)\d+\.\d+\.\d+(`)",
        r"(latest `v)(?!0\.0\.)\d+\.\d+\.\d+(` release)",
    ):
        txt = re.sub(pat, rf"\g<1>{self_ver}\g<2>", txt)
    return txt


def transform_sibling_readme(txt: str, repo_name: str, m: dict) -> str:
    comps = m["components"]
    cpv = str(m["current_patch_version"])
    txt = transform_own_readme_versions(txt, repo_name, str(comps[repo_name]["version"]))
    txt = re.sub(r"(配套主产品 `)\d+\.\d+\.\d+(`)", rf"\g<1>{cpv}\g<2>", txt)
    txt = re.sub(r"(paired with `mindie-agent )\d+\.\d+\.\d+(`)", rf"\g<1>{cpv}\g<2>", txt)

    if repo_name not in EXPECTED_PLUGINS:
        for comp_key, (pkg_dash, pkg_under) in PACKAGE_INFO.items():
            c_ver = str(comps[comp_key]["version"])
            c_sha = str(comps[comp_key]["commit"])
            txt = re.sub(
                rf"(https://github\.com/mindie-agent/{re.escape(comp_key)}/releases/download/v)\d+\.\d+\.\d+(/{re.escape(pkg_under)}-)\d+\.\d+\.\d+(-py3-none-any\.whl)",
                rf"\g<1>{c_ver}\g<2>{c_ver}\g<3>",
                txt,
            )
            txt = re.sub(
                rf"(`{re.escape(pkg_dash)}`(?:\]\([^)]+\))?\s*[（(]`v)\d+\.\d+\.\d+(`[)）])",
                rf"\g<1>{c_ver}\g<2>",
                txt,
            )
            txt = re.sub(
                rf"(\b{re.escape(pkg_dash)} )(v?)(?!0\.0\.)\d+\.\d+\.\d+\b",
                rf"\g<1>\g<2>{c_ver}",
                txt,
            )
            txt = re.sub(
                rf"(`{re.escape(pkg_dash)} {re.escape(c_ver)}`\s*[（(]`)[0-9a-f]{{40}}(`[)）])",
                rf"\g<1>{c_sha}\g<2>",
                txt,
            )
    return txt


def _strip_fenced_code(text: str) -> str:
    return re.sub(r"^```.*?^```", "", text, flags=re.MULTILINE | re.DOTALL)


def _heading_slugs(raw_heading: str) -> set[str]:
    clean = re.sub(r"<[^>]+>", "", raw_heading).strip()
    clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean)
    clean = clean.replace("`", "").replace("**", "").replace("*", "")
    lowered = clean.lower()
    slug_no_vs = re.sub(r"[^\w\s-]", "", lowered).replace(" ", "-")
    slug_with_vs = re.sub(r"[^\w\s\ufe0f-]", "", lowered).replace(" ", "-")
    return {slug_no_vs, slug_with_vs, slug_no_vs.strip("-"), slug_with_vs.strip("-")}


def verify_markdown_anchors(label: str, text: str) -> list[str]:
    errors: list[str] = []
    stripped = _strip_fenced_code(text)
    valid_anchors: set[str] = set()
    seen_counts: dict[str, int] = {}
    for match in re.finditer(r"^#{1,6}\s+(.+?)\s*$", stripped, flags=re.MULTILINE):
        for slug in _heading_slugs(match.group(1)):
            if not slug:
                continue
            count = seen_counts.get(slug, 0)
            seen_counts[slug] = count + 1
            valid_anchors.add(slug if count == 0 else f"{slug}-{count}")
    for html_id in re.findall(r'\b(?:id|name)=["\']([^"\']+)["\']', stripped):
        valid_anchors.add(html_id.strip().lower())

    anchors = [
        *re.findall(r"\[[^\]]+\]\(#([^)\s]+)\)", stripped),
        *re.findall(r'href=["\']#([^"\'\s>]+)["\']', stripped),
    ]
    for raw_anchor in anchors:
        candidate = urllib.parse.unquote(raw_anchor).strip().lower()
        if candidate and candidate not in valid_anchors and candidate.replace("\ufe0f", "") not in valid_anchors:
            errors.append(f"{label}: broken internal anchor #{raw_anchor}")
    return errors


def verify_no_stale_self_versions(label: str, text: str, repo_name: str, self_ver: str) -> list[str]:
    errors: list[str] = []
    stripped = _strip_fenced_code(text)
    if repo_name in EXPECTED_PLUGINS:
        for h_match in re.finditer(r"^#{1,6}\s+([^\n]+)$", stripped, flags=re.MULTILINE):
            h_txt = h_match.group(1)
            ver_in_heading = re.search(r"\b(0\.\d+\.\d+)\b", h_txt)
            if ver_in_heading:
                errors.append(
                    f"{label}: section heading hardcodes patch version {ver_in_heading.group(1)!r} "
                    f"({h_txt.strip()!r}); keep headings version-neutral"
                )
    patterns = (
        rf"\b{re.escape(repo_name)}\.git#v(\d+\.\d+\.\d+)\b",
        rf"\b{re.escape(repo_name)}\.git\s+--ref\s+v(\d+\.\d+\.\d+)\b",
        rf"--branch\s+v(\d+\.\d+\.\d+)\s+https://github\.com/mindie-agent/{re.escape(repo_name)}\.git",
        rf"\b{re.escape(repo_name)}\s+v?(\d+\.\d+\.\d+)\b",
        r"(?:当前稳定版本|Current Release|当前正式版本)[：:\s]*\[?`v?(\d+\.\d+\.\d+)`\]?",
    )
    for pat in patterns:
        for found in re.findall(pat, text):
            if found != self_ver and not found.startswith("0.0."):
                errors.append(f"{label}: stale self version {found!r} != release version {self_ver!r}")
    return errors


def verify_unreleased_plugin_main(manifest: dict, siblings_roots: list[Path]) -> list[str]:
    errors: list[str] = []
    comps = manifest.get("components") or {}
    for plugin_name in EXPECTED_PLUGINS:
        entry = comps.get(plugin_name)
        if not isinstance(entry, dict):
            continue
        repo_dir = resolve_sibling_repo(plugin_name, siblings_roots)
        if repo_dir is None:
            continue
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15.0,
            check=False,
        )
        if res.returncode == 0:
            head_sha = res.stdout.strip()
            expected_sha = str(entry.get("commit") or "")
            if head_sha and expected_sha and head_sha != expected_sha:
                errors.append(
                    f"{plugin_name}: local checkout HEAD {head_sha[:8]} != channels/0.1.json "
                    f"commit {expected_sha[:8]} ({entry.get('tag')})"
                )
    return errors


def sync_sibling_readmes(
    repo_root: Path,
    m: dict,
    write: bool,
    *,
    siblings_roots: list[Path] | None = None,
    require_siblings: bool = False,
) -> list[str]:
    roots = siblings_roots if siblings_roots is not None else default_siblings_roots(repo_root)
    comps = m.get("components") or {}
    errors: list[str] = []

    for main_rel in ("README.md", "README.en.md"):
        main_readme = repo_root / main_rel
        if main_readme.is_file():
            errors.extend(verify_markdown_anchors(f"mindie-agent/{main_rel}", main_readme.read_text(encoding="utf-8")))

    for repo_name, entry in comps.items():
        repo_dir = resolve_sibling_repo(repo_name, roots)
        if repo_dir is None:
            if require_siblings:
                errors.append(f"{repo_name}: sibling checkout not found in {roots}")
            continue
        self_ver = str(entry["version"])
        for rel in ("README.md", "README.en.md"):
            target = repo_dir / rel
            if not target.is_file():
                errors.append(f"{repo_name}/{rel}: required README file not found")
                continue
            errors.extend(
                process_markdown_file(
                    target,
                    lambda txt, rn=repo_name: transform_sibling_readme(txt, rn, m),
                    write,
                )
            )
            current_txt = target.read_text(encoding="utf-8")
            badge_matches = re.findall(r"https://img\.shields\.io/badge/[Rr]elease-v(\d+\.\d+\.\d+)-", current_txt)
            if not badge_matches:
                errors.append(f"{repo_name}/{rel}: missing shields.io Release badge for v{self_ver}")
            elif any(v != self_ver for v in badge_matches):
                errors.append(f"{repo_name}/{rel}: Release badge versions {badge_matches} != expected {self_ver}")
            if repo_name in EXPECTED_PLUGINS:
                errors.extend(verify_markdown_anchors(f"{repo_name}/{rel}", current_txt))
            errors.extend(verify_no_stale_self_versions(f"{repo_name}/{rel}", current_txt, repo_name, self_ver))

        for opt_rel in ("docs/README.md", "docs/README.en.md"):
            opt_target = repo_dir / opt_rel
            if opt_target.is_file():
                errors.extend(
                    process_markdown_file(
                        opt_target,
                        lambda txt, rn=repo_name: transform_sibling_readme(txt, rn, m),
                        write,
                    )
                )
    return errors


def verify_github_releases(manifest: dict, *, verify_commits: bool = False) -> list[str]:
    """Verify formal Releases and optionally compare remote tags with source pins."""
    errors: list[str] = []
    gh_bin = shutil.which("gh")
    if not gh_bin:
        return ["gh CLI not found in PATH for --verify-github-releases"]
    comp_entries = manifest.get("components") or {}
    for key in sorted(comp_entries):
        entry = comp_entries[key]
        repo = entry.get("repository", "")
        version = entry.get("version", "")
        tag = f"v{version}"
        res = subprocess.run(
            [gh_bin, "release", "view", tag, "-R", repo, "--json", "tagName,isDraft,isPrerelease,assets"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15.0,
            check=False,
        )
        if res.returncode != 0:
            errors.append(f"{repo}: formal GitHub Release {tag} not found ({res.stderr.strip()})")
            continue
        data = json.loads(res.stdout)
        if data.get("isDraft") or data.get("isPrerelease"):
            errors.append(
                f"{repo}: GitHub Release {tag} is draft={data.get('isDraft')} prerelease={data.get('isPrerelease')}"
            )
        assets = {a.get("name") for a in (data.get("assets") or []) if isinstance(a, dict)}
        if not assets:
            errors.append(f"{repo}: GitHub Release {tag} has 0 uploaded assets")
        elif "SHA256SUMS" not in assets:
            errors.append(f"{repo}: GitHub Release {tag} missing SHA256SUMS asset")
        if verify_commits:
            from release_tag_integrity import verify_tag_commit
            errors.extend(verify_tag_commit(gh_bin, repo, tag, entry['commit']))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-scope", choices=("product",), required=True,
                        help="Full synchronization is reserved for an explicitly selected product combination")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Verify docs and sibling READMEs without writing")
    mode.add_argument("--write", action="store_true", help="Rewrite out-of-sync docs and sibling READMEs in place")
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
        help="Directory containing sibling MindIE Agent repository checkouts",
    )
    parser.add_argument(
        "--require-siblings",
        action="store_true",
        help="Fail if any expected sibling repository checkout is missing",
    )
    args = parser.parse_args(argv)
    repo_root = args.channel.resolve().parents[1]
    manifest = json.loads(args.channel.read_text(encoding="utf-8"))
    roots = default_siblings_roots(repo_root, args.siblings_root)
    errors = [
        *verify_channel_schema(manifest, repo_root),
        *sync_docs_versions(repo_root, manifest, args.write),
        *sync_sibling_readmes(
            repo_root,
            manifest,
            args.write,
            siblings_roots=roots,
            require_siblings=args.require_siblings,
        ),
    ]
    if errors:
        for err in errors:
            print(f"[sibling-readme-sync:FAIL] {err}", file=sys.stderr)
        return 1
    print(f"[sibling-readme-sync:OK] Verified docs and sibling READMEs for channel v{manifest.get('current_patch_version')}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

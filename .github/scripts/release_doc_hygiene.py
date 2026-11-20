#!/usr/bin/env python3
"""Scope release documentation checks to their actual publication boundary.

[Role]
Verifies repository source versions, README badges/wheel URLs, and Unix LF line endings
for independent component/corpus/plugin publications (including pre-channel `harness` and
`mindie-agent-oc`) or full product combinations, plus Git diff routing for CI.

[Invariants]
- Independent releases validate only selected repositories against their own source manifests;
  full channel-wide alignment requires explicit `--release-scope product`.
- `--product-inputs-changed BASE_SHA` emits strictly `changed=true|false` for `$GITHUB_OUTPUT`,
  while standalone check invocations report explicit `selected/exercised/missing/unselected`
  repository coverage via `repo_roots`.

[Timeouts & Locks]
- Outer LF and product-sync checks enforce `35s` (`>= 2*15s` Git + `5s` grace); zero locks.

[Side-Effect Policy]
- Strictly read-only; never rewrites channels, READMEs, or user settings.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib
from typing import Mapping, Sequence

from repo_roots import (
    ALL_KNOWN_REPOS,
    HUB_REPO,
    INDEPENDENT_COMPONENTS,
    INDEPENDENT_PLUGINS,
    infer_default_siblings_roots,
    parse_repo_overrides,
    summarize_repo_coverage,
)
from sibling_readme_sync import (
    ALL_PLUGINS,
    PRODUCT_DOC_PATHS,
    resolve_sibling_repo,
    sync_sibling_readmes,
    transform_own_readme_versions,
    verify_markdown_anchors,
    verify_no_stale_self_versions,
)

VERSION_FILES = (
    "pyproject.toml",
    "plugins/mindie-agent/pyproject.toml",
    "kimi.plugin.json",
    "package.json",
    ".claude-plugin/plugin.json",
    "plugins/mindie-agent/plugin.json",
    "plugins/mindie-agent/.codex-plugin/plugin.json",
)
OUTER_CHECK_TIMEOUT_SECONDS = 35.0
READMES = ("README.md", "README.en.md", "docs/README.md", "docs/README.en.md")


def source_version(repo: Path, name: str) -> str:
    """Use the candidate's own manifests, including native plugin manifests."""
    versions = {}
    for filename in VERSION_FILES if name in ALL_PLUGINS else ("pyproject.toml",):
        path = repo / filename
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        metadata = tomllib.loads(text).get("project", {}) if path.suffix == ".toml" else json.loads(text)
        if "version" in metadata:
            versions[filename] = metadata["version"]
    if not versions:
        raise ValueError("no source version manifest found")
    version = next(iter(versions.values()))
    if (
        not isinstance(version, str)
        or not re.fullmatch(r"\d+\.\d+\.\d+", version)
        or any(value != version for value in versions.values())
    ):
        raise ValueError(f"source release versions disagree or are not stable: {versions}")
    return version


def verify_own_readmes(repo: Path, name: str, version: str | None) -> list[str]:
    """Validate self badges/links without interpreting paired or peer versions."""
    errors = []
    for filename in READMES:
        path = repo / filename
        required = filename == "README.md" or (filename == "README.en.md" and version is not None)
        if not path.is_file():
            if required:
                errors.append(f"{name}/{filename}: required README file not found")
            continue
        text = path.read_text(encoding="utf-8")
        if name in ALL_PLUGINS:
            errors.extend(verify_markdown_anchors(f"{name}/{filename}", text))
        if version is None:
            continue
        badges = re.findall(r"https://img\.shields\.io/badge/[Rr]elease-v(\d+\.\d+\.\d+)-", text)
        if filename in READMES[:2] and not badges:
            errors.append(f"{name}/{filename}: missing Release badge for source version {version}")
        if any(found != version for found in badges):
            errors.append(f"{name}/{filename}: Release badge versions {badges} != source version {version}")
        if transform_own_readme_versions(text, name, version) != text:
            errors.append(f"{name}/{filename}: self release links or version declarations differ from source version {version}")
        wheel_links = re.findall(
            rf"github\.com/mindie-agent/{re.escape(name)}/releases/download/v([^/\s]+)/"
            r"[A-Za-z0-9_]+-([0-9]+\.[0-9]+\.[0-9]+)-py3-none-any\.whl",
            text,
        )
        if any(tag != version or wheel != version for tag, wheel in wheel_links):
            errors.append(f"{name}/{filename}: wheel download version differs from source version {version}")
        errors.extend(verify_no_stale_self_versions(f"{name}/{filename}", text, name, version))
    return errors


def verify_release_doc_hygiene(
    main_repo: Path,
    manifest: dict,
    roots: Sequence[Path],
    *,
    scope: str,
    release_repos: Sequence[str],
    require_siblings: bool,
    run,
    explicit_repos: Mapping[str, Path] | None = None,
) -> list[str]:
    """Keep the channel as historical context for an independent publication."""
    scripts = Path(__file__).resolve().parent
    errors: list[str] = []
    if scope == "product":
        sync_cmd = [
            sys.executable,
            str(scripts / "sync_org_versions.py"),
            "--release-scope",
            "product",
            "--repo-root",
            str(main_repo),
            "--check",
            "--offline",
        ]
        for root in roots or ():
            sync_cmd.extend(["--siblings-root", str(root)])
        for name, target in (explicit_repos or {}).items():
            sync_cmd.extend(["--repo", f"{name}={target}"])
        commands = (
            [sys.executable, str(scripts / "check_lf_eol.py"), "--repo-root", str(main_repo)],
            sync_cmd,
        )
        for command in commands:
            result = run(command, cwd=main_repo, timeout=OUTER_CHECK_TIMEOUT_SECONDS)
            if result.returncode:
                errors.append(f"{Path(command[1]).name} failed: {(result.stderr or result.stdout).strip()}")
        errors.extend(
            sync_sibling_readmes(
                main_repo,
                manifest,
                False,
                siblings_roots=roots,
                explicit_repos=explicit_repos,
                require_siblings=require_siblings,
            )
        )
        return errors
    if scope != "independent" or not release_repos:
        raise ValueError("independent R6 requires --release-repo; full synchronization requires product scope")
    entries = (
        set(manifest.get("components", {}))
        | set(manifest.get("corpora", {}))
        | set(INDEPENDENT_PLUGINS)
        | set(INDEPENDENT_COMPONENTS)
    )
    for name in dict.fromkeys(release_repos):
        if name not in entries:
            errors.append(f"{name}: release repository is not declared in the channel or registry")
            continue
        try:
            repo = resolve_sibling_repo(name, roots, explicit_repos=explicit_repos)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if repo is None:
            errors.append(f"{name}: selected release checkout not found in {list(roots)}")
            continue
        repo = repo.resolve()
        result = run(
            [sys.executable, str(scripts / "check_lf_eol.py"), "--repo-root", str(repo)],
            cwd=repo,
            timeout=OUTER_CHECK_TIMEOUT_SECONDS,
        )
        if result.returncode:
            errors.append(f"{name}: LF check failed: {(result.stderr or result.stdout).strip()}")
        try:
            version = None if name in manifest.get("corpora", {}) else source_version(repo, name)
            errors.extend(verify_own_readmes(repo, name, version))
        except TimeoutError:
            raise
        except (OSError, ValueError) as exc:
            errors.append(f"{name}: release documentation check failed: {exc}")
    return errors


def product_inputs_changed(base: str, *, repository: Path, head: str = "HEAD") -> bool:
    """Route actual Git changes, including every document the product sync owns."""
    if not base or re.fullmatch(r"0+", base.strip()):
        return True
    paths = (
        "channels/",
        "docs/releases/",
        "README.md",
        "README.en.md",
        *PRODUCT_DOC_PATHS,
        ".github/workflows/release.yml",
        ".github/workflows/pr-checklist.yml",
        ".github/scripts/repo_roots.py",
        ".github/scripts/code_doc_hygiene_gate.py",
        ".github/scripts/check_auto_update_readiness.py",
        ".github/scripts/host_compatibility_gate.py",
        ".github/scripts/windows_zero_popup_gate.py",
        ".github/scripts/zero_binding_gate.py",
        ".github/scripts/iron_rule_ast_gate.py",
        ".github/scripts/functional_smoke_gate.py",
        ".github/scripts/storage_lifecycle_gate.py",
        ".github/scripts/storage_temp_ast.py",
        ".github/scripts/storage_pid_ast.py",
        ".github/scripts/release_doc_hygiene.py",
        ".github/scripts/sibling_readme_sync.py",
        ".github/scripts/sync_org_versions.py",
    )
    result = subprocess.run(
        ["git", "diff", "--quiet", base, head, "--", *paths],
        cwd=repository,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
    )
    if result.returncode not in (0, 1):
        result.check_returncode()
    return result.returncode == 1


def _default_run(argv: list[str], *, cwd: Path | None = None, timeout: float = 15.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product-inputs-changed", metavar="BASE_SHA", help="Emit changed=true|false for CI routing")
    parser.add_argument("--release-scope", choices=("independent", "product"), default="independent")
    parser.add_argument("--release-repo", action="append", default=[])
    parser.add_argument("--channel", type=Path, default=Path(__file__).resolve().parents[2] / "channels" / "0.1.json")
    parser.add_argument("--siblings-root", type=Path, action="append", default=[])
    parser.add_argument("--repo", action="append", default=[], metavar="NAME=/ABS/PATH")
    parser.add_argument("--require-siblings", action="store_true")
    args = parser.parse_args(argv)

    if args.product_inputs_changed is not None:
        changed = product_inputs_changed(args.product_inputs_changed, repository=Path.cwd())
        print("changed=" + str(changed).lower())
        return 0

    try:
        explicit_repos = parse_repo_overrides(args.repo)
    except ValueError as exc:
        print(f"[release-doc-hygiene:FAIL] {exc}", file=sys.stderr)
        return 1

    main_repo = args.channel.resolve().parents[1]
    manifest = json.loads(args.channel.read_text(encoding="utf-8"))
    roots = infer_default_siblings_roots(main_repo, args.siblings_root)
    selected = (
        [HUB_REPO, *(manifest.get("components") or {}).keys()]
        if args.release_scope == "product"
        else list(dict.fromkeys(args.release_repo))
    )
    coverage = summarize_repo_coverage(
        ALL_KNOWN_REPOS,
        selected,
        roots,
        explicit_repos=explicit_repos,
        extra_present={HUB_REPO: main_repo},
    )
    print(coverage.format_line("release-doc-hygiene"))

    errors = verify_release_doc_hygiene(
        main_repo,
        manifest,
        roots,
        scope=args.release_scope,
        release_repos=args.release_repo,
        require_siblings=args.require_siblings,
        run=_default_run,
        explicit_repos=explicit_repos,
    )
    if errors:
        for err in errors:
            print(f"[release-doc-hygiene:FAIL] {err}", file=sys.stderr)
        return 1
    print(f"[release-doc-hygiene:OK] Verified R6 documentation hygiene ({args.release_scope}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

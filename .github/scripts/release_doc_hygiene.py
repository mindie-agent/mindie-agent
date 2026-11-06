"""[Role] Scope release documentation checks to their actual publication boundary.

[Invariants] Independent releases use selected repositories' source versions.
Only an explicit product scope compares READMEs across the channel combination.
[Timeouts & Locks] The caller bounds LF and product-sync commands to 15 seconds.
[Side-Effect Policy] Read-only; never rewrites a channel, README or user setting.
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

from sibling_readme_sync import (
    EXPECTED_PLUGINS, PRODUCT_DOC_PATHS, resolve_sibling_repo, sync_sibling_readmes,
    transform_own_readme_versions, verify_markdown_anchors, verify_no_stale_self_versions,
)

VERSION_FILES = (
    "pyproject.toml", "plugins/mindie-agent/pyproject.toml", "kimi.plugin.json",
    "package.json", ".claude-plugin/plugin.json", "plugins/mindie-agent/plugin.json",
    "plugins/mindie-agent/.codex-plugin/plugin.json",
)
READMES = ("README.md", "README.en.md", "docs/README.md", "docs/README.en.md")


def source_version(repo: Path, name: str) -> str:
    """Use the candidate's own manifests, including native plugin manifests."""
    versions = {}
    for filename in VERSION_FILES if name in EXPECTED_PLUGINS else ("pyproject.toml",):
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
    if (not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version)
            or any(value != version for value in versions.values())):
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
        # Preserve the existing native-plugin anchor gate without expanding
        # independent component release checks into unrelated documentation lint.
        if name in EXPECTED_PLUGINS:
            errors.extend(verify_markdown_anchors(f"{name}/{filename}", text))
        if version is None:
            continue  # Corpora use unit revisions, not a software package version.
        badges = re.findall(r"https://img\.shields\.io/badge/[Rr]elease-v(\d+\.\d+\.\d+)-", text)
        if filename in READMES[:2] and not badges:
            errors.append(f"{name}/{filename}: missing Release badge for source version {version}")
        if any(found != version for found in badges):
            errors.append(f"{name}/{filename}: Release badge versions {badges} != source version {version}")
        if transform_own_readme_versions(text, name, version) != text:
            errors.append(f"{name}/{filename}: self release links or version declarations differ from source version {version}")
        wheel_links = re.findall(
            rf"github\.com/mindie-agent/{re.escape(name)}/releases/download/v([^/\s]+)/"
            r"[A-Za-z0-9_]+-([0-9]+\.[0-9]+\.[0-9]+)-py3-none-any\.whl", text)
        if any(tag != version or wheel != version for tag, wheel in wheel_links):
            errors.append(f"{name}/{filename}: wheel download version differs from source version {version}")
        errors.extend(verify_no_stale_self_versions(f"{name}/{filename}", text, name, version))
    return errors


def verify_release_doc_hygiene(main_repo, manifest, roots, *, scope, release_repos, require_siblings, run):
    """Keep the channel as historical context for an independent publication."""
    scripts = Path(__file__).resolve().parent
    errors = []
    if scope == "product":
        commands = (
            [sys.executable, str(scripts / "check_lf_eol.py"), "--repo-root", str(main_repo)],
            [sys.executable, str(scripts / "sync_org_versions.py"), "--release-scope", "product",
             "--repo-root", str(main_repo), "--check", "--offline"],
        )
        for command in commands:
            result = run(command, cwd=main_repo, timeout=15.0)
            if result.returncode:
                errors.append(f"{Path(command[1]).name} failed: {(result.stderr or result.stdout).strip()}")
        errors.extend(sync_sibling_readmes(
            main_repo, manifest, False, siblings_roots=roots, require_siblings=require_siblings))
        return errors
    if scope != "independent" or not release_repos:
        raise ValueError("independent R6 requires --release-repo; full synchronization requires product scope")
    entries = set(manifest.get("components", {})) | set(manifest.get("corpora", {}))
    for name in dict.fromkeys(release_repos):
        if name not in entries:
            errors.append(f"{name}: release repository is not declared in the channel")
            continue
        repo = resolve_sibling_repo(name, roots)
        if repo is None:
            errors.append(f"{name}: selected release checkout not found in {roots}")
            continue
        repo = repo.resolve()
        result = run([sys.executable, str(scripts / "check_lf_eol.py"), "--repo-root", str(repo)],
                     cwd=repo, timeout=15.0)
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
    paths = (
        "channels/", "docs/releases/", "README.md", "README.en.md", *PRODUCT_DOC_PATHS,
        ".github/workflows/release.yml", ".github/workflows/pr-checklist.yml",
        ".github/scripts/check_auto_update_readiness.py", ".github/scripts/release_doc_hygiene.py",
        ".github/scripts/sibling_readme_sync.py", ".github/scripts/sync_org_versions.py",
    )
    result = subprocess.run(
        ["git", "diff", "--quiet", base, head, "--", *paths], cwd=repository,
        capture_output=True, text=True, encoding="utf-8", timeout=15, check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if result.returncode not in (0, 1):
        result.check_returncode()
    return result.returncode == 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Identify product inputs changed for CI routing.")
    parser.add_argument("--product-inputs-changed", required=True, metavar="BASE_SHA")
    args = parser.parse_args()
    changed = product_inputs_changed(args.product_inputs_changed, repository=Path.cwd())
    print("changed=" + str(changed).lower())

#!/usr/bin/env python3
"""Unified MindIE Agent repository registry and worktree-native checkout resolver.

[Role]
Single pure-stdlib source of truth for organization repository metadata (`mindie-agent` hub,
`harness` substrate, 8 domain runtime components, `mindie-bench`, 7 host plugins, and 9
`knowledge-*` corpora) and local Git checkout/worktree resolution across all hub gates.

[Invariants]
- Resolution order is deterministic: (1) explicit `--repo name=/path` mapping (authoritative;
  invalid or non-Git paths fail closed without silent fallback), (2) explicit `--siblings-root`
  directories (matching `<root>/<name>` first, then unique linked worktrees in `<root>` via
  `.git` `gitdir:` + `commondir/config` origin identity), and (3) canonical flat sibling
  `../<name>` inferred from `git rev-parse --path-format=absolute --git-common-dir`.
- Recognizes both `.git/` directories and `.git` linked-worktree pointer files; contains zero
  personal machine path fallbacks.

[Timeouts & Locks]
- Optional `git rev-parse` invocation enforces a bounded `15s` timeout (`CREATE_NO_WINDOW` on
  Windows); linked-worktree inspection is pure local file I/O with zero locks.

[Side-Effect Policy]
- Strictly read-only filesystem and Git metadata inspection.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
from typing import Iterable, Mapping, Sequence

ORG = "mindie-agent"
GIT_TIMEOUT_SECONDS = 15.0

HUB_REPO = "mindie-agent"
INDEPENDENT_COMPONENTS: tuple[str, ...] = ("harness",)
CHANNEL_SHARED_COMPONENTS: tuple[str, ...] = (
    "diagnostics",
    "debugger",
    "profiler",
    "sim",
    "npu-top",
    "remote-dev",
    "knowledge",
    "coordinator",
)
ALL_SHARED_COMPONENTS: tuple[str, ...] = (*INDEPENDENT_COMPONENTS, *CHANNEL_SHARED_COMPONENTS)
BENCH_REPO = "mindie-bench"
CHANNEL_PLUGINS: tuple[str, ...] = (
    "mindie-agent-codex",
    "mindie-agent-cc",
    "mindie-agent-kimi",
    "mindie-agent-dsh",
    "mindie-agent-agy",
    "mindie-agent-wb",
)
INDEPENDENT_PLUGINS: tuple[str, ...] = ("mindie-agent-oc",)
ALL_PLUGINS: tuple[str, ...] = (*CHANNEL_PLUGINS, *INDEPENDENT_PLUGINS)
EXPECTED_CORPORA: tuple[str, ...] = (
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

PACKAGE_INFO: dict[str, tuple[str, str]] = {
    "harness": ("mindie-harness", "mindie_harness"),
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

ALL_KNOWN_REPOS: tuple[str, ...] = (
    HUB_REPO,
    *ALL_SHARED_COMPONENTS,
    BENCH_REPO,
    *ALL_PLUGINS,
    *EXPECTED_CORPORA,
)

_ORIGIN_SLUG_RE = re.compile(r"github\.com[:/]mindie-agent/([A-Za-z0-9._-]+?)(?:\.git)?\s*$", re.MULTILINE)


@dataclass(frozen=True)
class RepoCoverage:
    selected: tuple[str, ...]
    exercised: tuple[str, ...]
    missing: tuple[str, ...]
    unselected: tuple[str, ...]

    def format_line(self, gate_name: str) -> str:
        def _fmt(items: Sequence[str]) -> str:
            return ",".join(items) if items else "none"

        return (
            f"[{gate_name}:repos] "
            f"selected ({len(self.selected)})={_fmt(self.selected)} | "
            f"exercised ({len(self.exercised)})={_fmt(self.exercised)} | "
            f"missing ({len(self.missing)})={_fmt(self.missing)} | "
            f"unselected ({len(self.unselected)})={_fmt(self.unselected)}"
        )


def is_git_checkout(path: Path) -> bool:
    """Return True if `path` has a valid `.git/` directory or linked-worktree `.git` file."""
    try:
        if not path.is_dir():
            return False
        dot_git = path / ".git"
        if dot_git.is_dir():
            return True
        if dot_git.is_file():
            first_line = dot_git.read_text(encoding="utf-8", errors="replace").splitlines()
            return bool(first_line and first_line[0].startswith("gitdir:"))
    except TimeoutError:
        raise
    except OSError:
        return False
    return False


def _linked_worktree_repo_name(candidate: Path) -> str | None:
    """Identify the canonical repo slug owning linked worktree `candidate` without subprocesses."""
    dot_git = candidate / ".git"
    try:
        if not dot_git.is_file():
            return None
        lines = dot_git.read_text(encoding="utf-8", errors="replace").splitlines()
        if not lines or not lines[0].startswith("gitdir:"):
            return None
        raw_gitdir = lines[0].split(":", 1)[1].strip()
        gitdir = Path(raw_gitdir)
        if not gitdir.is_absolute():
            gitdir = (candidate / gitdir).resolve()
        commondir_file = gitdir / "commondir"
        if commondir_file.is_file():
            rel_common = commondir_file.read_text(encoding="utf-8", errors="replace").strip()
            commondir = (gitdir / rel_common).resolve()
        elif gitdir.parent.name == "worktrees":
            commondir = gitdir.parents[1].resolve()
        else:
            commondir = gitdir.resolve()
        cfg_file = commondir / "config"
        if cfg_file.is_file():
            cfg_text = cfg_file.read_text(encoding="utf-8", errors="replace")
            match = _ORIGIN_SLUG_RE.search(cfg_text)
            if match:
                return match.group(1)
        if commondir.name == ".git":
            return commondir.parent.name
    except TimeoutError:
        raise
    except OSError:
        return None
    return None


def parse_repo_overrides(specs: Sequence[str] | None) -> dict[str, Path]:
    """Parse repeatable `name=/path` overrides; fail closed on invalid syntax or non-Git targets."""
    overrides: dict[str, Path] = {}
    for raw in specs or ():
        if "=" not in raw:
            raise ValueError(f"invalid --repo override {raw!r}; expected NAME=/path/to/checkout")
        name, raw_path = raw.split("=", 1)
        name = name.strip()
        raw_path = raw_path.strip()
        if not name or not raw_path:
            raise ValueError(f"invalid --repo override {raw!r}; expected non-empty NAME and PATH")
        if name not in ALL_KNOWN_REPOS:
            raise ValueError(f"unknown repository name {name!r} in --repo {raw!r}")
        resolved = Path(raw_path).expanduser().resolve()
        if not is_git_checkout(resolved):
            raise ValueError(f"--repo {name}={raw_path!r} is not a valid Git checkout or worktree ({resolved})")
        overrides[name] = resolved
    return overrides


def infer_default_siblings_roots(main_repo: Path, extra_roots: Sequence[Path] | None = None) -> list[Path]:
    """Infer canonical flat sibling parent from `--git-common-dir` when no `--siblings-root` is given."""
    if extra_roots:
        roots: list[Path] = []
        for item in extra_roots:
            resolved = Path(item).expanduser().resolve()
            if resolved not in roots:
                roots.append(resolved)
        return roots

    resolved_main = main_repo.expanduser().resolve()
    try:
        proc = subprocess.run(
            ["git", "-C", str(resolved_main), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        if proc.returncode == 0:
            common_dir = Path(proc.stdout.strip())
            if common_dir.name == ".git" and common_dir.parent.parent.is_dir():
                return [common_dir.parent.parent.resolve()]
    except TimeoutError:
        raise
    except OSError:
        pass
    return [resolved_main.parent]


def resolve_repo(
    repo_name: str,
    siblings_roots: Sequence[Path],
    *,
    explicit_repos: Mapping[str, Path] | None = None,
    allow_worktree_scan: bool = True,
) -> Path | None:
    """Resolve `repo_name` via explicit `--repo`, `<root>/<name>`, or unique linked worktree in `<root>`."""
    if explicit_repos and repo_name in explicit_repos:
        target = Path(explicit_repos[repo_name])
        if not is_git_checkout(target):
            raise ValueError(f"explicit --repo mapping for {repo_name} is not a Git checkout: {target}")
        return target

    for raw_root in siblings_roots:
        root = Path(raw_root)
        direct = root / repo_name
        if is_git_checkout(direct):
            return direct
        if not allow_worktree_scan or not root.is_dir():
            continue
        try:
            entries = sorted(root.iterdir())
        except TimeoutError:
            raise
        except OSError:
            continue
        matches = [entry for entry in entries if _linked_worktree_repo_name(entry) == repo_name]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            joined = ", ".join(str(m) for m in matches)
            raise ValueError(
                f"ambiguous linked worktrees for {repo_name} under {root}: {joined}; "
                f"disambiguate with --repo {repo_name}=/abs/path"
            )
    return None


def summarize_repo_coverage(
    universe: Iterable[str],
    selected_names: Iterable[str],
    siblings_roots: Sequence[Path],
    *,
    explicit_repos: Mapping[str, Path] | None = None,
    extra_present: Mapping[str, Path] | None = None,
) -> RepoCoverage:
    """Compute `(selected, exercised, missing, unselected)` across `universe`."""
    ordered_universe = list(dict.fromkeys(universe))
    selected_set = set(selected_names)
    selected = tuple(name for name in ordered_universe if name in selected_set)
    unselected = tuple(name for name in ordered_universe if name not in selected_set)
    exercised_list: list[str] = []
    missing_list: list[str] = []
    for name in selected:
        found = resolve_repo(name, siblings_roots, explicit_repos=explicit_repos)
        if found is None and extra_present and name in extra_present:
            found = extra_present[name]
        if found is not None:
            exercised_list.append(name)
        else:
            missing_list.append(name)
    return RepoCoverage(
        selected=selected,
        exercised=tuple(exercised_list),
        missing=tuple(missing_list),
        unselected=unselected,
    )

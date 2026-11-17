"""Unit contracts for worktree-native repository discovery and coverage reporting.

[Role]
Verifies `repo_roots.py` across standard `.git/` directories, linked Git worktrees
(`.git` file -> `gitdir:` -> `commondir/config`), explicit `--repo name=/abs/path`
fail-closed overrides, `--git-common-dir` flat-sibling inference from inside a linked
hub worktree, ambiguity rejection, and `RepoCoverage` reporting.

[Invariants]
- Isolates `HOME`, `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `XDG_*`, `MINDIE_CONFIG_HOME`,
  `MINDIE_DATA_HOME`, `MINDIE_DIAGNOSTICS_ROOT`, `REMOTE_DEV_AUTH_DIR`, `UV_CACHE_DIR`,
  and `TMPDIR` inside per-test temporary directories.

[Timeouts & Locks]
- Pure Tier 0/1 local temp filesystem/git tests (`< 3s` total); zero network calls or locks.

[Side-Effect Policy]
- Writes only inside `tempfile.TemporaryDirectory` cleaned up after every test.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import repo_roots  # noqa: E402


class RepoRootsTests(unittest.TestCase):
    """Covers flat checkouts, linked worktrees, `--repo` overrides, and coverage formatting."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="mindie-repo-roots-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        env = {
            key: str(self.root / ".env" / key)
            for key in (
                "HOME",
                "USERPROFILE",
                "APPDATA",
                "LOCALAPPDATA",
                "XDG_CONFIG_HOME",
                "XDG_DATA_HOME",
                "XDG_STATE_HOME",
                "XDG_CACHE_HOME",
                "MINDIE_CONFIG_HOME",
                "MINDIE_DATA_HOME",
                "MINDIE_DIAGNOSTICS_ROOT",
                "REMOTE_DEV_AUTH_DIR",
                "UV_CACHE_DIR",
                "TMPDIR",
            )
        }
        Path(env["TMPDIR"]).mkdir(parents=True, exist_ok=True)
        patcher = patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _make_linked_worktree(self, common_dir_name: str, origin_slug: str, wt_dir_name: str) -> tuple[Path, Path]:
        common_repo = self.root / "flat" / common_dir_name
        wt_git_admin = common_repo / ".git" / "worktrees" / wt_dir_name
        wt_git_admin.mkdir(parents=True, exist_ok=True)
        (common_repo / ".git" / "config").write_text(
            f'[remote "origin"]\n\turl = https://github.com/mindie-agent/{origin_slug}.git\n',
            encoding="utf-8",
            newline="\n",
        )
        (wt_git_admin / "commondir").write_text("../..\n", encoding="utf-8", newline="\n")
        wt_checkout = self.root / ".worktrees" / wt_dir_name
        wt_checkout.mkdir(parents=True, exist_ok=True)
        (wt_checkout / ".git").write_text(f"gitdir: {wt_git_admin}\n", encoding="utf-8", newline="\n")
        return common_repo, wt_checkout

    def test_is_git_checkout_recognizes_both_git_dir_and_linked_worktree_file(self) -> None:
        std_repo = self.root / "flat" / "harness"
        (std_repo / ".git").mkdir(parents=True)
        _, wt_diag = self._make_linked_worktree("diagnostics-reporting", "diagnostics", "diagnostics-clean-arch")
        not_git = self.root / "plain"
        not_git.mkdir()

        self.assertTrue(repo_roots.is_git_checkout(std_repo))
        self.assertTrue(repo_roots.is_git_checkout(wt_diag))
        self.assertFalse(repo_roots.is_git_checkout(not_git))

    def test_siblings_root_discovers_unique_linked_worktrees_and_rejects_ambiguity(self) -> None:
        _, wt_diag = self._make_linked_worktree("diagnostics-reporting", "diagnostics", "diagnostics-clean-arch")
        _, wt_sim = self._make_linked_worktree("sim", "sim", "sim-docs-archive")
        wt_root = self.root / ".worktrees"

        self.assertEqual(repo_roots.resolve_repo("diagnostics", [wt_root]), wt_diag.resolve())
        self.assertEqual(repo_roots.resolve_repo("sim", [wt_root]), wt_sim.resolve())
        self.assertIsNone(repo_roots.resolve_repo("remote-dev", [wt_root]))

        # Adding a second worktree for the same origin slug inside `--siblings-root` fails closed
        self._make_linked_worktree("sim", "sim", "sim-second-branch")
        with self.assertRaisesRegex(ValueError, "ambiguous linked worktrees"):
            repo_roots.resolve_repo("sim", [wt_root])

    def test_explicit_repo_override_is_authoritative_and_fails_closed(self) -> None:
        override = self.root / "custom-harness"
        (override / ".git").mkdir(parents=True)
        parsed = repo_roots.parse_repo_overrides([f"harness={override}"])
        self.assertEqual(parsed, {"harness": override.resolve()})

        # Explicit `--repo` takes precedence even when another copy exists in siblings_roots
        shadow = self.root / "siblings" / "harness"
        (shadow / ".git").mkdir(parents=True)
        self.assertEqual(
            repo_roots.resolve_repo("harness", [self.root / "siblings"], explicit_repos=parsed),
            override.resolve(),
        )

        missing = self.root / "does-not-exist"
        for bad_spec in ("invalid-no-equals", f"unknown-repo={override}", f"harness={missing}"):
            with self.subTest(bad_spec=bad_spec), self.assertRaises(ValueError):
                repo_roots.parse_repo_overrides([bad_spec])

    def test_infer_default_siblings_roots_resolves_flat_parent_from_linked_hub_worktree(self) -> None:
        flat_parent = self.root / "workspace"
        hub_base = flat_parent / "mindie-agent"
        hub_base.mkdir(parents=True)
        subprocess.run(
            ["git", "-c", "core.autocrlf=false", "init", "-q", str(hub_base)],
            check=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        (hub_base / "README.md").write_text("hub\n", encoding="utf-8", newline="\n")
        subprocess.run(
            ["git", "-C", str(hub_base), "-c", "user.name=Test", "-c", "user.email=t@e.invalid", "add", "README.md"],
            check=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        subprocess.run(
            ["git", "-C", str(hub_base), "-c", "user.name=Test", "-c", "user.email=t@e.invalid", "commit", "-qm", "init"],
            check=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        wt_hub = flat_parent / ".worktrees" / "mindie-agent-clean-arch"
        subprocess.run(
            ["git", "-C", str(hub_base), "worktree", "add", "-q", "-b", "test-wt", str(wt_hub)],
            check=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        inferred = repo_roots.infer_default_siblings_roots(wt_hub)
        self.assertEqual(inferred[0], flat_parent.resolve())

    def test_summarize_repo_coverage_distinguishes_selected_exercised_missing_unselected(self) -> None:
        siblings = self.root / "siblings"
        (siblings / "harness" / ".git").mkdir(parents=True)
        hub = siblings / "mindie-agent"
        (hub / ".git").mkdir(parents=True)

        cov = repo_roots.summarize_repo_coverage(
            ("mindie-agent", "harness", "knowledge", "sim"),
            ("mindie-agent", "harness", "knowledge"),
            [siblings],
            extra_present={"mindie-agent": hub},
        )
        self.assertEqual(cov.selected, ("mindie-agent", "harness", "knowledge"))
        self.assertEqual(cov.exercised, ("mindie-agent", "harness"))
        self.assertEqual(cov.missing, ("knowledge",))
        self.assertEqual(cov.unselected, ("sim",))
        line = cov.format_line("gate")
        self.assertIn("missing (1)=knowledge", line)
        self.assertIn("unselected (1)=sim", line)


if __name__ == "__main__":
    unittest.main()

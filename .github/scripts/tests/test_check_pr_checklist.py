"""Unit contracts for parameterized PR checklist validation across all 8 profiles.

[Role]
Verifies `check_pr_checklist.py` across `--profile {hub,harness,host-plugin,control-plane,
state-service,device-tool,bench,corpus}`, HTML comment and fenced-code stripping, duplicate
and unchecked item detection, and `not-applicable: <specific reason>` handling.

[Invariants]
- Isolates `HOME`, `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `XDG_*`, `MINDIE_CONFIG_HOME`,
  `MINDIE_DATA_HOME`, `MINDIE_DIAGNOSTICS_ROOT`, `REMOTE_DEV_AUTH_DIR`, `UV_CACHE_DIR`,
  and `TMPDIR` inside per-test temporary directories.

[Timeouts & Locks]
- Pure Tier 0 in-memory/tempdir unit tests (`< 1s` total); zero subprocesses or locks.

[Side-Effect Policy]
- Writes only inside `tempfile.TemporaryDirectory` cleaned up after every test.
"""

from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_pr_checklist as pr_gate  # noqa: E402


def _render_valid_pr(profile: str, *, use_na_last: bool = False) -> str:
    ids = pr_gate.PROFILE_ITEMS[profile]
    lines = [
        "## 变更摘要 (Summary)",
        "- Refactored boundary gates and aligned living documentation with clean-core invariants.",
        "",
        "## 设计原则 Review (Pre-PR Checklist)",
    ]
    for idx, cid in enumerate(ids):
        if use_na_last and idx == len(ids) - 1:
            lines.append(f"- [x] `{cid}`: not-applicable: pure documentation change touching only docs/")
        else:
            lines.append(f"- [x] `{cid}`: verified against isolated unit suite and LF hygiene check")
    lines.extend(
        [
            "",
            "## 验证结果 (Verification)",
            "- `python3 -m pytest .github/scripts/tests -q` passed across all 8 profiles.",
        ]
    )
    return "\n".join(lines) + "\n"


class CheckPrChecklistTests(unittest.TestCase):
    """Covers all 8 checklist profiles, comment/fence stripping, and N/A reason discipline."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="mindie-pr-checklist-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        env = {
            key: str(self.root / key)
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

    def test_all_eight_profiles_accept_checked_and_reasoned_not_applicable_items(self) -> None:
        for profile in pr_gate.PROFILE_ITEMS:
            with self.subTest(profile=profile):
                body = _render_valid_pr(profile, use_na_last=True)
                self.assertEqual(pr_gate.validate_pr_body(body, profile=profile), [])

    def test_comments_and_fenced_blocks_are_stripped_and_invalid_states_fail(self) -> None:
        body = (
            "## 变更摘要 (Summary)\n"
            "- Concrete summary explaining why the hub documentation and gates changed.\n\n"
            "## 设计原则 Review (Pre-PR Checklist)\n"
            "<!--\n"
            "- [x] `HUB-DOC`: template comment must be ignored\n"
            "-->\n"
            "```markdown\n"
            "- [x] `HUB-DOC`: fenced example must be ignored\n"
            "```\n"
            "- [x] `HUB-ROUTE`: verified routing table and worktree handoff\n"
            "- [x] `HUB-ROUTE`: duplicate entry\n"
            "- [x] `HUB-RELEASE`: N/A\n"
            "- [ ] `HUB-GATE`: unchecked item\n\n"
            "## 验证结果 (Verification)\n"
            "- `python3 -m pytest .github/scripts/tests -q` passed.\n"
        )
        errors = pr_gate.validate_pr_body(body, profile="hub")
        self.assertTrue(any("Duplicate checklist ID: 'HUB-ROUTE'" in e for e in errors), errors)
        self.assertTrue(any("Missing checked checklist ID 'HUB-DOC'" in e for e in errors), errors)
        self.assertTrue(any("'HUB-RELEASE' requires concrete evidence or 'not-applicable:" in e for e in errors), errors)
        self.assertTrue(any("Unchecked checklist item" in e for e in errors), errors)

    def test_cli_reads_body_file_or_env_and_returns_expected_exit_codes(self) -> None:
        body_file = self.root / "pr_body.md"
        body_file.write_text(_render_valid_pr("hub"), encoding="utf-8", newline="\n")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            rc = pr_gate.main(["--profile", "hub", "--body-file", str(body_file)])
        self.assertEqual(rc, 0)
        self.assertIn("Pre-PR Checklist validation passed (profile=hub)", out.getvalue())

        with patch.dict(os.environ, {"PR_BODY": "## Review\n- [ ] `HAR-ABI`: todo\n"}), contextlib.redirect_stderr(io.StringIO()) as err:
            rc_fail = pr_gate.main(["--profile", "harness"])
        self.assertEqual(rc_fail, 1)
        self.assertIn("HAR-ABI", err.getvalue())


if __name__ == "__main__":
    unittest.main()

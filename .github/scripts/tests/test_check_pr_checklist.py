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

    def test_blank_verification_command_result_is_rejected(self) -> None:
        body = _render_valid_pr("hub").replace(
            "- `python3 -m pytest .github/scripts/tests -q` passed across all 8 profiles.",
            "- `python3 .github/scripts/check_lf_eol.py`: ",
        )
        errors = pr_gate.validate_pr_body(body, profile="hub")
        self.assertTrue(any("needs a concrete non-placeholder result" in e for e in errors), errors)

    def test_template_placeholders_are_rejected_but_comparisons_are_allowed(self) -> None:
        placeholder = _render_valid_pr("hub").replace(
            "- `python3 -m pytest .github/scripts/tests -q` passed across all 8 profiles.",
            "- `python3 .github/scripts/check_lf_eol.py`: <reason>",
        )
        errors = pr_gate.validate_pr_body(placeholder, profile="hub")
        self.assertTrue(any("Unreplaced template placeholder '<reason>'" in e for e in errors), errors)
        bounded = _render_valid_pr("hub").replace(
            "- `python3 -m pytest .github/scripts/tests -q` passed across all 8 profiles.",
            "- `python3 .github/scripts/check_lf_eol.py`: passed under < 800 lines, <= 2 retries, <5s.",
        )
        self.assertEqual(pr_gate.validate_pr_body(bounded, profile="hub"), [])

    def test_echoed_checkbox_prompt_evidence_is_rejected(self) -> None:
        prompt = "职责与仓库路由边界：本 PR 未混入任何运行时业务代码或宿主适配器实现"
        body = (
            "## 变更摘要 (Summary)\n"
            "- Concrete summary explaining why the hub documentation and gates changed.\n\n"
            "## 设计原则 Review (Pre-PR Checklist)\n"
            f"- [x] **`HUB-ROUTE`** — {prompt}\n"
            f"  - HUB-ROUTE: verified: {prompt}\n"
            "- [x] `HUB-DOC`: verified against isolated unit suite and LF hygiene check\n"
            "- [x] `HUB-RELEASE`: verified against isolated unit suite and LF hygiene check\n"
            "- [x] `HUB-GATE`: verified against isolated unit suite and LF hygiene check\n\n"
            "## 验证结果 (Verification)\n"
            "- `python3 .github/scripts/check_lf_eol.py`: passed.\n"
        )
        errors = pr_gate.validate_pr_body(body, profile="hub")
        self.assertTrue(any("only echoes the checkbox prompt" in e for e in errors), errors)

    def test_todo_markers_outside_inline_code_are_rejected(self) -> None:
        body = _render_valid_pr("hub").replace(
            "- `python3 -m pytest .github/scripts/tests -q` passed across all 8 profiles.",
            "- `python3 .github/scripts/check_lf_eol.py`: passed.\n- TODO finish the remaining checks",
        )
        errors = pr_gate.validate_pr_body(body, profile="hub")
        self.assertTrue(any("Unresolved 'TODO'" in e for e in errors), errors)
        literal = _render_valid_pr("hub").replace(
            "- `python3 -m pytest .github/scripts/tests -q` passed across all 8 profiles.",
            "- `python3 .github/scripts/check_lf_eol.py`: passed with literal `TODO` marker.",
        )
        self.assertEqual(pr_gate.validate_pr_body(literal, profile="hub"), [])

    def test_real_hub_pr_template_fails_raw_and_passes_when_filled(self) -> None:
        template_path = SCRIPTS.parents[0] / "pull_request_template.md"
        raw = template_path.read_text(encoding="utf-8")
        raw_errors = pr_gate.validate_pr_body(raw, profile="hub")
        self.assertTrue(raw_errors)
        self.assertFalse(any("Unreplaced template placeholder" in e for e in raw_errors), raw_errors)

        filled = (
            raw.replace("- \n", "- Add lean code/doc hygiene gate and tighten PR checklist validation.\n", 1)
            .replace("- [ ]", "- [x]")
            .replace("  - `HUB-ROUTE`: ", "  - `HUB-ROUTE`: Verified changes stay in .github/scripts/ and docs/; zero runtime code.")
            .replace("  - `HUB-DOC`: ", "  - `HUB-DOC`: Synced bilingual docs and verified symmetric H2 headings + LF endings.")
            .replace("  - `HUB-RELEASE`: ", "  - `HUB-RELEASE`: not-applicable: gate and living-doc update without channel bump.")
            .replace("  - `HUB-GATE`: ", "  - `HUB-GATE`: Pure Python 3.11+ stdlib gate (<800 lines) with isolated Tier-0 unit tests.")
            .replace("- `python3 .github/scripts/check_lf_eol.py`: ", "- `python3 .github/scripts/check_lf_eol.py`: passed (0 CRLF files)")
            .replace("- `python3 .github/scripts/code_doc_hygiene_gate.py --main-repo .`: ", "- `python3 .github/scripts/code_doc_hygiene_gate.py --main-repo .`: passed (18/18 repos clean)")
            .replace("- `python3 -m unittest discover -s .github/scripts/tests -p 'test_*.py' -v`: ", "- `python3 -m unittest discover -s .github/scripts/tests -p 'test_*.py' -v`: all tests passed")
        )
        self.assertEqual(pr_gate.validate_pr_body(filled, profile="hub"), [])

        # Deleting all separate evidence rows must NOT pass via stock '—' checkbox prompts
        stripped_evidence = "\n".join(ln for ln in filled.splitlines() if not ln.startswith("  - `HUB-"))
        self.assertTrue(pr_gate.validate_pr_body(stripped_evidence, profile="hub"))

        # Multi-comparison runtime notes and echoed/backticked-placeholder verification commands
        multi_cmp = filled.replace("all tests passed", "12 passed in <5s (>3s on CI)")
        self.assertEqual(pr_gate.validate_pr_body(multi_cmp, profile="hub"), [])
        echo_cmd = filled.replace("passed (0 CRLF files)", "`python3 .github/scripts/check_lf_eol.py`")
        self.assertTrue(any("needs a concrete non-placeholder result" in e for e in pr_gate.validate_pr_body(echo_cmd, profile="hub")))
        na_backtick = filled.replace("passed (0 CRLF files)", "`N/A`")
        self.assertTrue(any("needs a concrete non-placeholder result" in e for e in pr_gate.validate_pr_body(na_backtick, profile="hub")))

    def test_fenced_pr_closing_html_control_plane_prompts_and_colon_commands(self) -> None:
        valid = _render_valid_pr("hub") + "\n<details><summary>Logs</summary>\nAll green.\n</details>\n"
        self.assertEqual(pr_gate.validate_pr_body(valid, profile="hub"), [])
        self.assertTrue(pr_gate.validate_pr_body(f"~~~\r\n{valid}\r\n~~~~\r\n", profile="hub"))
        for bad_cmd in ("- pytest tests/test_api.py::test_read:", r"- C:\Python311\python.exe -m pytest:", "- `pytest -q`: not-applicable:"):
            bad = _render_valid_pr("hub").replace("- `python3 -m pytest .github/scripts/tests -q` passed across all 8 profiles.", bad_cmd)
            self.assertTrue(any("needs a concrete non-placeholder result" in e for e in pr_gate.validate_pr_body(bad, profile="hub")), bad_cmd)
        ctrl_stock = (
            "## 变更摘要 (Summary)\n- Refactored SSH handle tracking.\n\n"
            "## 设计原则 Review (Pre-PR Checklist)\n"
            "- [x] **CTRL-LEASE-OR-AUTH**: Shared `remote-dev` SSH auth/credential profiles remain intact.\n"
            "- [x] **CTRL-HANDLE**: Standard zero-`_meta` MCP `tools/call` executes without blocks.\n"
            "- [x] **CTRL-STREAM-IO**: All standalone remote worker scripts remain 100% pure Python stdlib.\n"
            "- [x] **CTRL-RECEIPT**: External mutations distinguish `not_sent` / `acknowledged` / `uncertain`.\n\n"
            "## 验证结果 (Verification)\n- `pytest -q`: 42 passed.\n"
        )
        self.assertTrue(pr_gate.validate_pr_body(ctrl_stock, profile="control-plane"))

    def test_summary_evidence_field_rejects_blank_and_accepts_concrete_notes(self) -> None:
        base = (
            "## 变更摘要 (Summary)\n"
            "- Harden process tree supervision and atomic upgrade handoff.\n\n"
            "## 底座架构核查清单 (Pre-PR Checklist — `harness`)\n"
            "- [x] **HAR-ABI（纯标准库零重依赖与根包契约）**：确认根包路径保持一致。\n"
            "- [x] **HAR-UPGRADE（双代原子切流）**：确认候选构建遵守磁盘下限。\n"
            "- [x] **HAR-PROC（跨平台受管进程树）**：确认无裸调 Popen。\n"
            "- [x] **HAR-STATE（SQLite WAL 防护）**：确认只读检查不创建空库。\n"
            "- **自查结论与证据**：{evidence}\n\n"
            "## 验证结果 (Verification)\n"
            "- `pytest -q`: 84 passed in 2.1s.\n"
        )
        self.assertTrue(pr_gate.validate_pr_body(base.format(evidence=""), profile="harness"))
        self.assertEqual(
            pr_gate.validate_pr_body(
                base.format(evidence="Verified seed build, WAL guard, and zero conhost popups across Tier-0/1 tests."),
                profile="harness",
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()

"""Unit tests for R7 End-to-End Functional Smoke & 7-Host Wire Readiness Gate (`functional_smoke_gate.py`).

[Role]
Verifies:
1. Default `check_auto_update_readiness.py` CLI runs (without `--verify-functional-smoke`) mark
   `R7` as `(skipped; pass --verify-functional-smoke)` and exit `0`.
2. `--verify-functional-smoke` passes when `selftest --mode full` and `host-accept` succeed with
   zero failed/skipped checks across all expected hosts.
3. `--verify-functional-smoke` fails closed under `MINDIE_REQUIRE_FULLSTACK=1` on missing sibling
   checkouts, non-zero exit codes, `"status": "failed"`, or any `"skipped"` check.
4. `assemble_stage_from_wheels` builds a valid `SHA256SUMS`-verified wheelhouse stage + `--override` file.

[Invariants]
- Isolates `HOME`, `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `XDG_*`, `MINDIE_*`,
  `REMOTE_DEV_AUTH_DIR`, `UV_CACHE_DIR`, and `TMPDIR` inside per-test `TemporaryDirectory`.

[Timeouts & Locks]
- Pure Tier 0 fast injectable unit tests (`< 1s`); zero network calls or external locks.

[Side-Effect Policy]
- Writes only inside disposable temporary directories cleaned up after every test.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_auto_update_readiness as gate  # noqa: E402
import functional_smoke_gate as fgate  # noqa: E402
from repo_roots import PACKAGE_INFO  # noqa: E402

ENV_KEYS = (
    "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
    "XDG_STATE_HOME", "XDG_CACHE_HOME", "MINDIE_CONFIG_HOME", "MINDIE_DATA_HOME",
    "MINDIE_DIAGNOSTICS_ROOT", "REMOTE_DEV_AUTH_DIR", "UV_CACHE_DIR", "TMPDIR", "TEMP", "TMP",
)


class FunctionalSmokeGateTests(unittest.TestCase):
    """Covers R7 CLI wiring, fail-closed `MINDIE_REQUIRE_FULLSTACK=1` rules, and stage assembly."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="mindie-r7-test-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        env = {k: str(self.root / "env" / k) for k in ENV_KEYS}
        env_patch = patch.dict(os.environ, env)
        env_patch.start()
        self.addCleanup(env_patch.stop)

        self.main_repo = self.root / "mindie-agent"
        (self.main_repo / "channels").mkdir(parents=True)
        (self.main_repo / "install.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8", newline="\n")
        real_channel = Path(__file__).resolve().parents[3] / "channels" / "0.1.json"
        (self.main_repo / "channels" / "0.1.json").write_bytes(real_channel.read_bytes())

        self.siblings = self.root / "siblings"
        self.siblings.mkdir()
        for repo_name in (*fgate.FIRST_PARTY_REPOS, *fgate.PLUGIN_BY_HOST.values()):
            (self.siblings / repo_name / ".git").mkdir(parents=True)

    def _fake_stage_builder(
        self, tmp_root: Path, _checkouts: object, _uv: str, _py: Path
    ) -> tuple[Path, Path]:
        stage = tmp_root / "stage"
        stage.mkdir(parents=True, exist_ok=True)
        venv_py = tmp_root / "smoke-venv" / "python"
        venv_py.parent.mkdir(parents=True, exist_ok=True)
        venv_py.write_text("", encoding="utf-8", newline="\n")
        return stage, venv_py

    def test_default_readiness_cli_skips_r7_and_flag_runs_r7(self) -> None:
        with contextlib.ExitStack() as stack:
            for fn_name in (
                "verify_channel_schema", "verify_corpora", "verify_components_and_plugins",
                "verify_flexible_component_compatibility", "verify_release_doc_hygiene",
            ):
                stack.enter_context(patch.object(gate, fn_name, return_value=[]))
            out_skip = io.StringIO()
            stack.enter_context(contextlib.redirect_stdout(out_skip))
            code = gate.main([
                "--channel", str(self.main_repo / "channels/0.1.json"),
                "--siblings-root", str(self.siblings),
                "--release-scope", "product",
            ])
        self.assertEqual(code, 0)
        self.assertIn("**R7. End-to-End Functional Smoke & 7-Host Wire Readiness (skipped; pass --verify-functional-smoke)**", out_skip.getvalue())

        with contextlib.ExitStack() as stack:
            for fn_name in (
                "verify_channel_schema", "verify_corpora", "verify_components_and_plugins",
                "verify_flexible_component_compatibility", "verify_release_doc_hygiene",
            ):
                stack.enter_context(patch.object(gate, fn_name, return_value=[]))
            stack.enter_context(patch.object(gate, "verify_functional_smoke", return_value=["R7: simulated smoke failure"]))
            out_fail, err_fail = io.StringIO(), io.StringIO()
            stack.enter_context(contextlib.redirect_stdout(out_fail))
            stack.enter_context(contextlib.redirect_stderr(err_fail))
            fail_code = gate.main([
                "--channel", str(self.main_repo / "channels/0.1.json"),
                "--siblings-root", str(self.siblings),
                "--release-scope", "product",
                "--verify-functional-smoke",
            ])
        self.assertEqual(fail_code, 1)
        self.assertIn("- [ ] **R7. End-to-End Functional Smoke & 7-Host Wire Readiness**", out_fail.getvalue())
        self.assertIn("R7: simulated smoke failure", err_fail.getvalue())

    def test_verify_functional_smoke_passes_on_clean_selftest_and_all_seven_hosts(self) -> None:
        seen_envs: list[dict[str, str]] = []
        seen_timeouts: list[float] = []

        def fake_run(argv, *, cwd=None, env=None, timeout=120.0):
            seen_envs.append(dict(env or {}))
            seen_timeouts.append(timeout)
            if "mindie_harness.cli" in argv and "selftest" in argv:
                payload = {
                    "schema": "mindie-selftest/1",
                    "mode": "full",
                    "status": "passed",
                    "checks": [{"name": "knowledge_9_domains", "status": "passed"}],
                }
                return subprocess.CompletedProcess(list(argv), 0, json.dumps(payload), "")
            if "mindie_bench.cli" in argv and "host-accept" in argv:
                self.assertIn("--all-hosts", argv)
                self.assertEqual(timeout, 660.0)
                out_path = Path(argv[argv.index("--output") + 1])
                out_path.write_text(
                    json.dumps({
                        "status": "passed",
                        "hosts": {
                            h: {"status": "passed", "checks": [{"name": "wire_mcp", "status": "passed"}]}
                            for h in fgate.ALL_HOSTS
                        },
                    }),
                    encoding="utf-8",
                    newline="\n",
                )
                return subprocess.CompletedProcess(list(argv), 0, "ok", "")
            raise AssertionError(f"unexpected command: {argv}")

        with patch.dict(os.environ, {"UV_CACHE_DIR": "/ambient/uv-cache", "MINDIE_AGENT_CONFIG": "/ambient/codex.json"}):
            errors = fgate.verify_functional_smoke(
                self.main_repo,
                [self.siblings],
                release_scope="product",
                which_fn=lambda name: f"/usr/bin/{name}",
                host_python_fn=lambda: Path(sys.executable),
                stage_builder_fn=self._fake_stage_builder,
                run_cmd_fn=fake_run,
            )
        self.assertEqual(errors, [])
        self.assertTrue(all(e.get("MINDIE_REQUIRE_FULLSTACK") == "1" for e in seen_envs))
        self.assertTrue(all(e.get("UV_CACHE_DIR") != "/ambient/uv-cache" for e in seen_envs))
        self.assertTrue(all(e.get("MINDIE_AGENT_CONFIG") == "" for e in seen_envs))
        self.assertTrue(all(bool(e.get("MINDIE_KNOWLEDGE_ROOT")) and bool(e.get("REMOTE_DEV_STATE_DIR")) for e in seen_envs))

    def test_verify_functional_smoke_fails_closed_on_missing_repo_failed_or_skipped_checks(self) -> None:
        # 1. Deterministic host plan & missing sibling checkout fail closed immediately
        self.assertEqual(fgate.plan_smoke_hosts("independent", ("coordinator",), [self.siblings]), (["codex"], False))
        missing_sibs = self.root / "incomplete-siblings"
        missing_sibs.mkdir()
        miss_errs = fgate.verify_functional_smoke(
            self.main_repo,
            [missing_sibs],
            release_scope="independent",
            release_repos=("harness",),
            which_fn=lambda name: f"/usr/bin/{name}",
            host_python_fn=lambda: Path(sys.executable),
            stage_builder_fn=self._fake_stage_builder,
        )
        self.assertTrue(any("required first-party checkout `harness` not found" in e for e in miss_errs), miss_errs)
        self.assertTrue(any("mindie-agent-oc" in e for e in miss_errs), miss_errs)

        # 2. Layer 1 fails fast (never calling host-accept) on skipped check, wrong mode, or non-Mapping check
        host_accept_called = False

        def skipped_selftest_run(argv, *, cwd=None, env=None, timeout=120.0):
            nonlocal host_accept_called
            if "selftest" in argv:
                return subprocess.CompletedProcess(
                    list(argv), 0,
                    json.dumps({
                        "schema": "mindie-selftest/1",
                        "mode": "candidate",
                        "status": "passed",
                        "checks": [{"name": "reme_engine", "status": "skipped"}, None],
                    }),
                    "",
                )
            host_accept_called = True
            raise AssertionError("host-accept must not run when Layer 1 selftest fails")

        skip_errs = fgate.verify_functional_smoke(
            self.main_repo,
            [self.siblings],
            release_scope="independent",
            release_repos=("mindie-agent-kimi",),
            which_fn=lambda name: f"/usr/bin/{name}",
            host_python_fn=lambda: Path(sys.executable),
            stage_builder_fn=self._fake_stage_builder,
            run_cmd_fn=skipped_selftest_run,
        )
        self.assertFalse(host_accept_called)
        self.assertTrue(any("mode 'candidate' != 'full'" in e for e in skip_errs), skip_errs)
        self.assertTrue(any("reme_engine=skipped" in e and "non_mapping" in e for e in skip_errs), skip_errs)

        # 3. Layer 2 rejects zero-check `{"status": "passed", "host": "codex"}` and `hosts: {"codex": null}`
        def bad_host_accept_run(argv, *, cwd=None, env=None, timeout=120.0):
            if "selftest" in argv:
                return subprocess.CompletedProcess(
                    list(argv), 0,
                    json.dumps({"schema": "mindie-selftest/1", "mode": "full", "status": "passed", "checks": [{"name": "ok", "status": "passed"}]}),
                    "",
                )
            out_path = Path(argv[argv.index("--output") + 1])
            payload = (
                {"status": "passed", "host": "codex"}
                if "codex" in argv
                else {"status": "passed", "hosts": {"kimi": None}}
            )
            out_path.write_text(json.dumps(payload), encoding="utf-8", newline="\n")
            return subprocess.CompletedProcess(list(argv), 0, "", "")

        for plugin, expected_msg in (
            ("mindie-agent-codex", "executed zero passing checks/scenarios"),
            ("mindie-agent-kimi", "record must be a JSON object"),
        ):
            ha_errs = fgate.verify_functional_smoke(
                self.main_repo,
                [self.siblings],
                release_scope="independent",
                release_repos=(plugin,),
                which_fn=lambda name: f"/usr/bin/{name}",
                host_python_fn=lambda: Path(sys.executable),
                stage_builder_fn=self._fake_stage_builder,
                run_cmd_fn=bad_host_accept_run,
            )
            self.assertTrue(any(expected_msg in e for e in ha_errs), ha_errs)

    def test_assemble_stage_from_wheels_writes_valid_bundle_checksums_and_overrides(self) -> None:
        stage_dir = self.root / "wheelhouse-stage"
        wheels_dir = stage_dir / "wheels"
        wheels_dir.mkdir(parents=True)
        for repo_name in fgate.FIRST_PARTY_REPOS:
            dist_name, mod_name = PACKAGE_INFO[repo_name]
            whl_dist = dist_name.replace("-", "_")
            whl_path = wheels_dir / f"{whl_dist}-0.1.5-py3-none-any.whl"
            with zipfile.ZipFile(whl_path, "w") as zf:
                zf.writestr(f"{mod_name}/__init__.py", "__version__ = '0.1.5'\n")
        overrides = fgate.assemble_stage_from_wheels(stage_dir, wheels_dir, channel_version="0.1.18")
        self.assertTrue(overrides.is_file())
        self.assertEqual(len(overrides.read_text(encoding="utf-8").splitlines()), 10)
        sums_text = (stage_dir / "SHA256SUMS").read_text(encoding="utf-8")
        rc_sha = hashlib.sha256((stage_dir / "release-channel.json").read_bytes()).hexdigest()
        bd_sha = hashlib.sha256((stage_dir / "mindie-wheels-bundle.tar.gz").read_bytes()).hexdigest()
        self.assertIn(f"{rc_sha}  release-channel.json", sums_text)
        self.assertIn(f"{bd_sha}  mindie-wheels-bundle.tar.gz", sums_text)
        with tarfile.open(stage_dir / "mindie-wheels-bundle.tar.gz", "r:gz") as archive:
            names = set(archive.getnames())
        self.assertIn("requirements.lock", names)
        self.assertEqual(len([n for n in names if n.endswith(".whl")]), 9)

        dup_whl = wheels_dir / "mindie_harness-0.1.4-py3-none-any.whl"
        with zipfile.ZipFile(dup_whl, "w") as zf:
            zf.writestr("mindie_harness/__init__.py", "__version__ = '0.1.4'\n")
        with self.assertRaisesRegex(fgate._SmokeSetupError, "duplicate wheel"):
            fgate.assemble_stage_from_wheels(stage_dir, wheels_dir, channel_version="0.1.18")


if __name__ == "__main__":
    unittest.main()

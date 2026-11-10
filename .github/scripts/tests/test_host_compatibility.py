"""Release gates retain verified host baselines and inspect the selected Desktop."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_auto_update_readiness as gate


class HostCompatibilityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mindie-host-compat-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        environment = {key: str(self.root / key) for key in (
            "HOME", "USERPROFILE", "MINDIE_CONFIG_HOME", "MINDIE_DATA_HOME",
            "MINDIE_DIAGNOSTICS_ROOT")}
        environment["CODEX_APP_RUNTIME_CLI_PATH"] = ""
        environment["MINDIE_AGENT_CONFIG"] = str(
            self.root / "HOME/.config/mindie-agent/codex.json")
        self.enter(patch.dict(os.environ, environment))
        self.enter(patch.object(gate.Path, "home", return_value=self.root / "HOME"))
        self.plugin = self.root / "mindie-agent-codex"
        (self.plugin / ".git").mkdir(parents=True)
        self.manifest = self.plugin / "plugins/mindie-agent/harness-compatibility.json"
        self.manifest.parent.mkdir(parents=True)
        self.config = self.root / "HOME/.config/mindie-agent/codex.json"
        self.config.parent.mkdir(parents=True)
        self.compatibility("0.162.0-alpha.2")

    def enter(self, context):
        value = context.start()
        self.addCleanup(context.stop)
        return value

    def compatibility(self, minimum):
        supported = [
            dict(minimum="0.153.4", maximum="0.153.4",
                 maximum_inclusive=True, include_prerelease=False),
            dict(minimum=minimum, maximum="0.999.999",
                 maximum_inclusive=True, include_prerelease=True),
        ]
        value = dict(schema="mindie-harness-compatibility/1", harness="codex",
                     supported=supported, used_interfaces=["native.version"],
                     interface_registry={"native.version": dict(
                         supported=copy.deepcopy(supported),
                         code_paths=["scripts/host.py:version"],
                         test_ids=["tests/test_host.py::test_version"],
                         evidence_refs=["https://learn.chatgpt.com/docs/plugins"])})
        self.manifest.write_text(json.dumps(value), encoding="utf-8", newline="\n")

    def test_forward_range_cannot_drop_verified_desktop_baseline(self):
        self.compatibility("0.162.0-alpha.17.2")
        with patch.object(gate, "verify_windows_windowless_spawns", return_value=[]):
            errors = gate.verify_flexible_component_compatibility([self.root])
        self.assertTrue(any("0.162.0-alpha.2" in error for error in errors), errors)

    def test_verified_baselines_and_future_hosts_pass(self):
        with patch.object(gate, "verify_windows_windowless_spawns", return_value=[]):
            self.assertEqual(gate.verify_flexible_component_compatibility([self.root]), [])

    def check_local(self, version, returncode=0):
        with patch.object(gate.shutil, "which", return_value=None), \
                patch.object(gate, "_run_cmd", return_value=subprocess.CompletedProcess(
                    [], returncode, f"codex-cli {version}\n" if version else "", "")) as run:
            errors = gate.verify_local_host_compatibility([self.root])
        return errors, run

    def test_installed_native_context_checks_desktop_without_cli_on_path(self):
        desktop = self.root / "desktop.exe"
        desktop.touch()
        self.config.write_text(json.dumps(dict(
            native_context=dict(MINDIE_CODEX_BIN=str(desktop)))), encoding="utf-8")
        errors, run = self.check_local("0.162.0-alpha.1")
        self.assertTrue(any("0.162.0-alpha.1" in error for error in errors), errors)
        run.assert_called_once_with([str(desktop), "--version"])

    def test_running_desktop_is_checked_without_saved_config(self):
        desktop = self.root / "running-desktop.exe"
        desktop.touch()
        with patch.dict(os.environ, CODEX_APP_RUNTIME_CLI_PATH=str(desktop)):
            errors, run = self.check_local("0.162.0-alpha.1")
        self.assertTrue(any("0.162.0-alpha.1" in error for error in errors), errors)
        run.assert_called_once_with([str(desktop), "--version"])

    def test_supported_legacy_native_context_remains_readable(self):
        desktop = self.root / "legacy-desktop.exe"
        desktop.touch()
        self.config.write_text(json.dumps(dict(
            native=dict(MINDIE_CODEX_BIN=str(desktop)))), encoding="utf-8")
        errors, run = self.check_local("0.162.0-alpha.2")
        self.assertEqual(errors, [])
        run.assert_called_once_with([str(desktop), "--version"])

    def test_explicit_installation_profile_is_checked(self):
        desktop = self.root / "custom-desktop.exe"
        desktop.touch()
        profile = self.root / "selected-profile.json"
        profile.write_text(json.dumps(dict(
            native_context=dict(MINDIE_CODEX_BIN=str(desktop)))), encoding="utf-8")
        with patch.dict(os.environ, MINDIE_AGENT_CONFIG=str(profile)):
            errors, run = self.check_local("0.162.0-alpha.1")
        self.assertTrue(any("0.162.0-alpha.1" in error for error in errors), errors)
        run.assert_called_once_with([str(desktop), "--version"])

    def test_unreadable_host_version_does_not_pass_coverage(self):
        desktop = self.root / "unreadable-desktop.exe"
        desktop.touch()
        with patch.dict(os.environ, CODEX_APP_RUNTIME_CLI_PATH=str(desktop)):
            for version, returncode in (("0.162.0-alpha.2", 1), (None, 0)):
                with self.subTest(version=version, returncode=returncode):
                    errors, _ = self.check_local(version, returncode)
                    self.assertTrue(any("version unavailable" in error for error in errors), errors)

    def test_profile_read_timeout_remains_a_timeout(self):
        self.config.write_text("{}", encoding="utf-8")
        original = Path.read_text

        def read_text(path, *args, **kwargs):
            if path == self.config:
                raise TimeoutError("profile read timed out")
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", read_text):
            with self.assertRaises(TimeoutError):
                gate.verify_local_host_compatibility([self.root])


if __name__ == "__main__":
    unittest.main()

"""Unit tests for Windows static JSON manifest bare-`python` ban (`R4` / `windows_zero_popup_gate.py`).

[Role]
Verifies `verify_windows_static_manifest_commands` and `verify_windows_windowless_spawns`
across `.mcp.json`, `mcp.json`, `mcp_config.json`, `hooks.json`, `kimi.plugin.json`,
`.claude-plugin/plugin.json`, and `.codex-plugin/plugin.json` for all 7 native host plugins.

[Invariants]
- Honors Codex `commandWindows` override (POSIX `command` ignored when non-empty `commandWindows`
  is present, while `commandWindows` itself is inspected).
- Accepts `uv` (including `uv run ... python ...`), `node`, `powershell.exe`, and explicit paths.
- Rejects bare `python`/`python3`/`pythonw.exe`, `env python3`, and `cmd /c python` in MCP or hooks.
- Isolates all `HOME`, `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `XDG_*`, `MINDIE_*`, `UV_CACHE_DIR`,
  and `TMPDIR` environment variables inside disposable temporary directories.

[Timeouts & Locks]
- Pure Tier 0 local filesystem/JSON tests (`< 1s`); zero subprocesses or locks.

[Side-Effect Policy]
- Writes only inside `tempfile.TemporaryDirectory` cleaned up after every test.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import host_compatibility_gate as host_gate  # noqa: E402
import windows_zero_popup_gate as wgate  # noqa: E402

ENV_KEYS = (
    "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
    "XDG_STATE_HOME", "XDG_CACHE_HOME", "MINDIE_CONFIG_HOME", "MINDIE_DATA_HOME",
    "MINDIE_DIAGNOSTICS_ROOT", "REMOTE_DEV_AUTH_DIR", "UV_CACHE_DIR", "TMPDIR", "TEMP", "TMP",
)


class WindowsStaticManifestGateTests(unittest.TestCase):
    """Covers MCP server and hook command static manifest checks across all 7 host plugins."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="mindie-win-manifest-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        env = {k: str(self.root / "env" / k) for k in ENV_KEYS}
        env_patch = patch.dict(os.environ, env)
        env_patch.start()
        self.addCleanup(env_patch.stop)
        iso_patch = patch(
            "windows_zero_popup_gate._resolve_repo",
            side_effect=lambda name, roots, extra_repos=None: next(
                (Path(r) / name for r in roots if (Path(r) / name / ".git").exists()), None
            ),
        )
        iso_patch.start()
        self.addCleanup(iso_patch.stop)

    def _write_json(self, plugin: str, rel: str, payload: object) -> Path:
        repo_dir = self.root / plugin
        (repo_dir / ".git").mkdir(parents=True, exist_ok=True)
        target = repo_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
        return target

    def test_uv_node_and_codex_command_windows_pass_cleanly(self) -> None:
        self._write_json(
            "mindie-agent-codex",
            "plugins/mindie-agent/hooks/hooks.json",
            {
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "python3 \"$PLUGIN_ROOT/scripts/hook_launcher.py\" session-start",
                                    "commandWindows": "powershell.exe -NoLogo -NoProfile -EncodedCommand AAA=",
                                }
                            ]
                        }
                    ]
                }
            },
        )
        self._write_json(
            "mindie-agent-codex",
            "plugins/mindie-agent/.mcp.json",
            {
                "mcpServers": {
                    "mindie-tools": {
                        "command": "uv",
                        "args": ["run", "--no-project", "python", "-m", "mindie_harness.cli", "mcp", "tools"],
                    }
                }
            },
        )
        self._write_json(
            "mindie-agent-cc",
            "hooks/hooks.json",
            {
                "hooks": {
                    "Stop": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "uv --native-tls run --no-project --python 3.13 python -B \"${CLAUDE_PLUGIN_ROOT}/scripts/plugin_entry.py\" hook stop",
                                }
                            ]
                        }
                    ]
                }
            },
        )
        self._write_json(
            "mindie-agent-dsh",
            "mcp_config.json",
            {"mcp": {"servers": {"remote": {"command": "node", "args": ["./host3.mjs"]}}}},
        )
        # Bare python inside skipped `tests/` or `docs/` directories must be ignored
        self._write_json(
            "mindie-agent-codex",
            "tests/fixtures/hooks.json",
            {"hooks": {"Stop": [{"hooks": [{"command": "python bad.py"}]}]}},
        )
        for plugin in ("mindie-agent-codex", "mindie-agent-cc", "mindie-agent-dsh"):
            self.assertEqual(wgate.verify_windows_static_manifest_commands(plugin, self.root / plugin), [])

    def test_bare_python_in_mcp_servers_and_env_wrappers_fails(self) -> None:
        self._write_json(
            "mindie-agent-kimi",
            "kimi.plugin.json",
            {
                "name": "mindie-agent",
                "version": "0.1.32",
                "mcpServers": {
                    "knowledge": {"command": "python3", "args": ["./scripts/mindie_launch.py", "mcp", "knowledge"]},
                    "remote": {"command": "/usr/bin/env", "args": ["PYTHONUTF8=1", "python", "./scripts/mindie_launch.py"]},
                    "tools": {"command": ["pythonw.exe", "-m", "mindie_harness.cli"]},
                },
            },
        )
        self._write_json(
            "mindie-agent-cc",
            ".claude-plugin/plugin.json",
            {"mcpServers": {"mindie": {"command": "env", "args": ["-S", "python3.exe", "entry.py"]}}},
        )
        kimi_errs = wgate.verify_windows_static_manifest_commands("mindie-agent-kimi", self.root / "mindie-agent-kimi")
        self.assertEqual(len(kimi_errs), 3, kimi_errs)
        self.assertTrue(any("`knowledge`" in e and "python3" in e for e in kimi_errs), kimi_errs)
        self.assertTrue(any("`remote`" in e and "/usr/bin/env python" in e for e in kimi_errs), kimi_errs)
        self.assertTrue(any("`tools`" in e and "pythonw.exe" in e for e in kimi_errs), kimi_errs)

        cc_errs = wgate.verify_windows_static_manifest_commands("mindie-agent-cc", self.root / "mindie-agent-cc")
        self.assertEqual(len(cc_errs), 1, cc_errs)
        self.assertIn(".claude-plugin/plugin.json", cc_errs[0])

    def test_bare_python_in_cross_platform_or_windows_hooks_fails_end_to_end(self) -> None:
        wb = self.root / "mindie-agent-wb"
        (wb / "plugins/mindie-agent/scripts").mkdir(parents=True)
        (wb / "plugins/mindie-agent/scripts/mindie_launch.py").write_text(
            "from mindie_harness.cli import main\n", encoding="utf-8", newline="\n"
        )
        self._write_json(
            "mindie-agent-wb",
            "plugins/mindie-agent/hooks/hooks.json",
            {
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "python -I -X utf8 \"${CODEBUDDY_PLUGIN_ROOT}/scripts/mindie_launch.py\" hook session-start",
                                }
                            ]
                        }
                    ]
                }
            },
        )
        # Also verify Codex fails when `commandWindows` itself invokes bare `python` or `cmd /c python`
        self._write_json(
            "mindie-agent-codex",
            "plugins/mindie-agent/hooks/hooks.json",
            {
                "hooks": {
                    "Stop": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "sh -c 'uv run python x.py'",
                                    "commandWindows": "cmd.exe /d /s /c python scripts\\hook_launcher.py stop",
                                },
                                {
                                    "type": "command",
                                    "command": "sh -c 'uv run python x.py'",
                                    "commandWindows": "powershell.exe -NoLogo -NoProfile -Command \"python scripts/hook_launcher.py stop\"",
                                },
                                {
                                    "type": "command",
                                    "command": "sh -c 'uv run python x.py'",
                                    "commandWindows": "powershell.exe -NoProfile -Command \"uv run --no-project python scripts/hook_launcher.py stop\"",
                                }
                            ]
                        }
                    ]
                }
            },
        )
        (self.root / "mindie-agent-codex/plugins/mindie-agent/scripts").mkdir(parents=True, exist_ok=True)
        (self.root / "mindie-agent-codex/plugins/mindie-agent/scripts/hook_launcher.py").write_text(
            "from mindie_harness.cli import main\n", encoding="utf-8", newline="\n"
        )

        errs = wgate.verify_windows_windowless_spawns([self.root])
        self.assertTrue(any("mindie-agent-wb: plugins/mindie-agent/hooks/hooks.json" in e and "python" in e for e in errs), errs)
        self.assertTrue(any("mindie-agent-codex: plugins/mindie-agent/hooks/hooks.json" in e and "cmd.exe /c python" in e for e in errs), errs)
        self.assertTrue(any("mindie-agent-codex: plugins/mindie-agent/hooks/hooks.json" in e and "powershell.exe -Command python" in e for e in errs), errs)

    def test_runtime_dependency_manifests_uv_sources_overrides_and_product_contract(self) -> None:
        all_nine = sorted(host_gate.REQUIRED_RUNTIME_PACKAGES)
        self.assertEqual(len(all_nine), 9)
        codex = self.root / "mindie-agent-codex"
        (codex / ".git").mkdir(parents=True, exist_ok=True)
        pyp = codex / "plugins/mindie-agent/pyproject.toml"
        pyp.parent.mkdir(parents=True, exist_ok=True)
        eight = [p for p in all_nine if p != "npu-top"]
        pyp.write_text(
            f'[project]\nname = "mindie-agent-codex"\nversion = "0.1.40"\ndependencies = {json.dumps(eight)}\n'
            f'[tool.uv.sources]\n{"".join(f"{p} = {{ git = \"https://github.com/mindie-agent/{p}\" }}\n" for p in eight)}',
            encoding="utf-8",
            newline="\n",
        )
        self._write_json(
            "mindie-agent-codex",
            "plugins/mindie-agent/product-contract.json",
            {"components": {p: "0.1.0" for p in all_nine if p != "mindie-debugger"}},
        )
        self._write_json("mindie-agent-kimi", "kimi.plugin.json", {"version": "0.1.33"})
        (self.root / "mindie-agent-kimi/runtime").mkdir(parents=True, exist_ok=True)
        (self.root / "mindie-agent-kimi/runtime/active-overrides.txt").write_text(
            "".join(f"{p}==0.1.0\n" for p in all_nine if p != "mindie-harness"), encoding="utf-8", newline="\n"
        )
        self._write_json("mindie-agent-agy", "plugins/mindie-agent/plugin.json", {"version": "0.1.22"})
        self._write_json("mindie-agent-wb", "product-contract.json", {"components": ["bad-list"]})
        errs = host_gate.verify_host_runtime_dependencies([self.root])
        self.assertTrue(any("mindie-agent-codex" in e and "[tool.uv.sources]" in e and "npu-top" in e for e in errs), errs)
        self.assertTrue(any("mindie-agent-codex" in e and "product-contract.json" in e and "mindie-debugger" in e for e in errs), errs)
        self.assertTrue(any("mindie-agent-kimi" in e and "active-overrides.txt" in e and "mindie-harness" in e for e in errs), errs)
        self.assertTrue(any("mindie-agent-agy" in e and "missing runtime dependency manifest" in e for e in errs), errs)
        self.assertTrue(any("mindie-agent-wb" in e and "`components` must be a JSON object" in e for e in errs), errs)


if __name__ == "__main__":
    unittest.main()

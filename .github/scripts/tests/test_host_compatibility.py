"""Unit contracts for R4 Windows zero-popup AST/JS gate, host baselines, and WSL2/SAC filtering.

[Role]
Verifies R4/R5 host compatibility baselines (`HostCompatibilityTests`) and Windows zero-console-popup
static enforcement (`HostCompatibilityGateTests`) across Python AST wrappers, co-existing refactored
modules, Node.js per-call `windowsHide: true` parsing, and WSL2/Windows binary filtering.

[Invariants]
- Isolates `HOME`, `USERPROFILE`, `APPDATA`, `MINDIE_CONFIG_HOME`, `MINDIE_DATA_HOME`, and
  `MINDIE_DIAGNOSTICS_ROOT` inside per-test temporary directories (zero host pollution).
- Co-existing candidate modules, JSDoc block comments, and isolated `--siblings-root` runs can never
  silently bypass `CREATE_NO_WINDOW` or `windowsHide: true` checks.

[Timeouts & Locks]
- Pure Tier 0 in-memory/tempdir unit tests (`< 5s` total) with zero external subprocesses or locks.

[Side-Effect Policy]
- Writes only inside `tempfile.TemporaryDirectory` cleaned up after every test.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_auto_update_readiness as gate  # noqa: E402
import host_compatibility_gate as host_gate  # noqa: E402


class HostCompatibilityTests(unittest.TestCase):
    """Retains verified Codex Desktop compatibility baselines, profile discovery, and timeout honesty."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mindie-host-compat-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        environment = {
            key: str(self.root / key)
            for key in (
                "HOME",
                "USERPROFILE",
                "APPDATA",
                "MINDIE_CONFIG_HOME",
                "MINDIE_DATA_HOME",
                "MINDIE_DIAGNOSTICS_ROOT",
            )
        }
        environment["CODEX_APP_RUNTIME_CLI_PATH"] = ""
        environment["MINDIE_DESKTOP_CODEX_CLI_PATH"] = ""
        environment["MINDIE_AGENT_CONFIG"] = str(self.root / "HOME/.config/mindie-agent/codex.json")
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

    def _native_bin(self, stem: str) -> Path:
        binary = self.root / (f"{stem}.exe" if os.name == "nt" else stem)
        binary.write_bytes(b"\x7fELF" if os.name != "nt" else b"MZ\x90\x00")
        return binary

    def compatibility(self, minimum: str):
        supported = [
            dict(minimum="0.153.4", maximum="0.153.4", maximum_inclusive=True, include_prerelease=False),
            dict(minimum=minimum, maximum="0.999.999", maximum_inclusive=True, include_prerelease=True),
        ]
        value = dict(
            schema="mindie-harness-compatibility/1",
            harness="codex",
            supported=supported,
            used_interfaces=["native.version"],
            interface_registry={
                "native.version": dict(
                    supported=copy.deepcopy(supported),
                    code_paths=["scripts/host.py:version"],
                    test_ids=["tests/test_host.py::test_version"],
                    evidence_refs=["https://learn.chatgpt.com/docs/plugins"],
                )
            },
        )
        self.manifest.write_text(json.dumps(value), encoding="utf-8", newline="\n")

    def test_forward_range_cannot_drop_verified_desktop_baseline(self):
        self.compatibility("0.162.0-alpha.17.2")
        with patch.object(gate, "verify_windows_windowless_spawns", return_value=[]):
            errors = gate.verify_flexible_component_compatibility([self.root])
        self.assertTrue(any("0.162.0-alpha.2" in error for error in errors), errors)

    def test_verified_baselines_and_future_hosts_pass(self):
        with patch.object(gate, "verify_windows_windowless_spawns", return_value=[]):
            self.assertEqual(gate.verify_flexible_component_compatibility([self.root]), [])

    def check_local(self, version: str | None, returncode: int = 0):
        with patch.object(gate.shutil, "which", return_value=None), patch.object(
            gate,
            "_run_cmd",
            return_value=subprocess.CompletedProcess([], returncode, f"codex-cli {version}\n" if version else "", ""),
        ) as run:
            errors = gate.verify_local_host_compatibility([self.root])
        return errors, run

    def test_installed_native_context_checks_desktop_without_cli_on_path(self):
        desktop = self._native_bin("desktop")
        self.config.write_text(
            json.dumps(dict(native_context=dict(MINDIE_CODEX_BIN=str(desktop)))), encoding="utf-8", newline="\n"
        )
        errors, run = self.check_local("0.162.0-alpha.1")
        self.assertTrue(any("0.162.0-alpha.1" in error for error in errors), errors)
        run.assert_called_once_with([str(desktop), "--version"])

    def test_running_desktop_is_checked_without_saved_config(self):
        desktop = self._native_bin("running-desktop")
        with patch.dict(os.environ, CODEX_APP_RUNTIME_CLI_PATH=str(desktop)):
            errors, run = self.check_local("0.162.0-alpha.1")
        self.assertTrue(any("0.162.0-alpha.1" in error for error in errors), errors)
        run.assert_called_once_with([str(desktop), "--version"])

    def test_supported_legacy_native_context_remains_readable(self):
        desktop = self._native_bin("legacy-desktop")
        self.config.write_text(
            json.dumps(dict(native=dict(MINDIE_CODEX_BIN=str(desktop)))), encoding="utf-8", newline="\n"
        )
        errors, run = self.check_local("0.162.0-alpha.2")
        self.assertEqual(errors, [])
        run.assert_called_once_with([str(desktop), "--version"])

    def test_explicit_installation_profile_is_checked(self):
        desktop = self._native_bin("custom-desktop")
        profile = self.root / "selected-profile.json"
        profile.write_text(
            json.dumps(dict(native_context=dict(MINDIE_CODEX_BIN=str(desktop)))), encoding="utf-8", newline="\n"
        )
        with patch.dict(os.environ, MINDIE_AGENT_CONFIG=str(profile)):
            errors, run = self.check_local("0.162.0-alpha.1")
        self.assertTrue(any("0.162.0-alpha.1" in error for error in errors), errors)
        run.assert_called_once_with([str(desktop), "--version"])

    def test_unreadable_host_version_does_not_pass_coverage(self):
        desktop = self._native_bin("unreadable-desktop")
        with patch.dict(os.environ, CODEX_APP_RUNTIME_CLI_PATH=str(desktop)):
            for version, returncode in (("0.162.0-alpha.2", 1), (None, 0)):
                with self.subTest(version=version, returncode=returncode):
                    errors, _ = self.check_local(version, returncode)
                    self.assertTrue(any("version unavailable" in error for error in errors), errors)

    def test_profile_read_timeout_remains_a_timeout(self):
        self.config.write_text("{}", encoding="utf-8", newline="\n")
        original = Path.read_text

        def read_text(path, *args, **kwargs):
            if path == self.config:
                raise TimeoutError("profile read timed out")
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", read_text):
            with self.assertRaises(TimeoutError):
                gate.verify_local_host_compatibility([self.root])


class HostCompatibilityGateTests(unittest.TestCase):
    """Verifies R4 zero-popup AST/JS enforcement and WSL2/Windows native executable filtering."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mindie-host-gate-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        sandbox = patch.dict(
            os.environ,
            {
                **{
                    key: str(self.root / key)
                    for key in (
                        "HOME",
                        "USERPROFILE",
                        "APPDATA",
                        "MINDIE_CONFIG_HOME",
                        "MINDIE_DATA_HOME",
                        "MINDIE_DIAGNOSTICS_ROOT",
                    )
                },
                "MINDIE_AGENT_CONFIG": "",
                "MINDIE_DESKTOP_CODEX_CLI_PATH": "",
                "CODEX_APP_RUNTIME_CLI_PATH": "",
            },
        )
        sandbox.start()
        self.addCleanup(sandbox.stop)
        # Prevent fallback inspection of ambient PYTHONPATH mindie_knowledge during isolated repo tests
        no_extra = patch("windows_zero_popup_gate._resolve_repo", side_effect=self._isolated_resolve_repo)
        no_extra.start()
        self.addCleanup(no_extra.stop)

    @staticmethod
    def _isolated_resolve_repo(repo_name: str, siblings_roots, extra_repos=None):
        for root in siblings_roots:
            candidate = Path(root) / repo_name
            if (candidate / ".git").exists():
                return candidate
        return None

    def _make_repo(self, name: str) -> Path:
        repo = self.root / name
        (repo / ".git").mkdir(parents=True)
        return repo

    def test_diagnostics_r4_checks_coexisting_modules_and_rejects_comment_spoofing(self):
        diag = self._make_repo("diagnostics")
        svc = diag / "mindie_diagnostics" / "platform_service.py"
        transport = diag / "mindie_diagnostics" / "github_transport.py"
        reporter = diag / "mindie_diagnostics" / "reporter.py"
        transport.parent.mkdir(parents=True)
        svc.write_text("flags = subprocess.CREATE_NO_WINDOW\n", encoding="utf-8", newline="\n")

        # 1. Refactored layout: github_transport.py enforces CREATE_NO_WINDOW and reporter.py actively delegates
        transport.write_text("flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)\n", encoding="utf-8", newline="\n")
        reporter.write_text(
            "from .github_transport import _run_gh\n\ndef send(cmd):\n    return _run_gh(cmd)\n",
            encoding="utf-8",
            newline="\n",
        )
        self.assertEqual(host_gate.verify_windows_windowless_spawns([self.root]), [])

        # 1b. Comment/docstring-only CREATE_NO_WINDOW never spoofs AST check
        svc.write_text('"""subprocess.CREATE_NO_WINDOW"""\n# subprocess.CREATE_NO_WINDOW\n', encoding="utf-8", newline="\n")
        svc_errors = host_gate.verify_windows_windowless_spawns([self.root])
        self.assertEqual(len(svc_errors), 1)
        self.assertIn("diagnostics: mindie_diagnostics/platform_service.py", svc_errors[0])
        svc.write_text("flags = subprocess.CREATE_NO_WINDOW\n", encoding="utf-8", newline="\n")

        # 1c. Co-existing reporter.py cannot hide behind github_transport.py with an unguarded subprocess call
        reporter.write_text(
            "import subprocess\nfrom .github_transport import _run_gh\n\n"
            "def send(cmd):\n    subprocess.run(['gh', 'status'])\n    return _run_gh(cmd)\n",
            encoding="utf-8",
            newline="\n",
        )
        coexist_errors = host_gate.verify_windows_windowless_spawns([self.root])
        self.assertEqual(len(coexist_errors), 1)
        self.assertIn("diagnostics: mindie_diagnostics/reporter.py", coexist_errors[0])

        # 1d. Co-existing reporter.py with only a prose comment or unused import is rejected
        reporter.write_text("# delegates to github_transport\n", encoding="utf-8", newline="\n")
        undelegated = host_gate.verify_windows_windowless_spawns([self.root])
        self.assertEqual(len(undelegated), 1)
        self.assertIn("diagnostics: mindie_diagnostics/reporter.py", undelegated[0])

        # 2. First present candidate is authoritative: if github_transport.py omits CREATE_NO_WINDOW, fail
        transport.write_text("flags = 0\n", encoding="utf-8", newline="\n")
        reporter.write_text("flags = subprocess.CREATE_NO_WINDOW\n", encoding="utf-8", newline="\n")
        errors = host_gate.verify_windows_windowless_spawns([self.root])
        self.assertEqual(len(errors), 1)
        self.assertIn("diagnostics: mindie_diagnostics/github_transport.py", errors[0])

        # 3. Legacy layout (only reporter.py present): passes when reporter.py enforces CREATE_NO_WINDOW
        transport.unlink()
        self.assertEqual(host_gate.verify_windows_windowless_spawns([self.root]), [])

        # 4. Neither candidate present: fails explicitly
        reporter.unlink()
        missing = host_gate.verify_windows_windowless_spawns([self.root])
        self.assertEqual(len(missing), 1)
        self.assertIn("diagnostics: missing expected subprocess wrapper", missing[0])

    def test_mindie_bench_coexisting_process_and_companion_termination_checks(self):
        bench = self._make_repo("mindie-bench")
        runner_dir = bench / "src" / "mindie_bench" / "runner"
        runner_dir.mkdir(parents=True)
        hp = runner_dir / "host_platform.py"
        proc_py = runner_dir / "process.py"
        term_py = runner_dir / "termination.py"
        hp.write_text(
            "import subprocess\ndef subprocess_window_kwargs():\n    return {'creationflags': subprocess.CREATE_NO_WINDOW}\n",
            encoding="utf-8",
            newline="\n",
        )
        term_py.write_text("import subprocess\nFLAGS = subprocess.CREATE_NO_WINDOW\n", encoding="utf-8", newline="\n")
        proc_py.write_text(
            "from mindie_bench.runner.host_platform import subprocess_window_kwargs\n"
            "from mindie_bench.runner.termination import spawn_owned_popen\n"
            "def run(cmd):\n    return spawn_owned_popen(cmd, **subprocess_window_kwargs())\n",
            encoding="utf-8",
            newline="\n",
        )
        self.assertEqual(host_gate.verify_windows_windowless_spawns([self.root]), [])

        # Dropping subprocess_window_kwargs() call in process.py fails even if unused import remains
        proc_py.write_text(
            "from mindie_bench.runner.host_platform import subprocess_window_kwargs\n"
            "from mindie_bench.runner.termination import spawn_owned_popen\n"
            "def run(cmd):\n    return spawn_owned_popen(cmd)\n",
            encoding="utf-8",
            newline="\n",
        )
        proc_errors = host_gate.verify_windows_windowless_spawns([self.root])
        self.assertEqual(len(proc_errors), 1)
        self.assertIn("mindie-bench: src/mindie_bench/runner/process.py", proc_errors[0])

        # Restoring process.py and breaking companion termination.py is also caught
        proc_py.write_text(
            "from mindie_bench.runner.host_platform import subprocess_window_kwargs\n"
            "def run(cmd):\n    return subprocess_window_kwargs()\n",
            encoding="utf-8",
            newline="\n",
        )
        term_py.write_text("FLAGS = 0\n", encoding="utf-8", newline="\n")
        term_errors = host_gate.verify_windows_windowless_spawns([self.root])
        self.assertEqual(len(term_errors), 1)
        self.assertIn("mindie-bench: src/mindie_bench/runner/termination.py", term_errors[0])

    def test_node_per_call_windowshide_blocks_jsdoc_comment_spoofing_and_scans_companion_mjs(self):
        oc = self._make_repo("mindie-agent-oc")
        plugin_dir = oc / "plugins" / "mindie-agent"
        scripts_dir = plugin_dir / "scripts"
        scripts_dir.mkdir(parents=True)
        for script_name in ("bounded.py", "component_update.py", "mindie_launch.py"):
            (scripts_dir / script_name).write_text("import subprocess\nF = subprocess.CREATE_NO_WINDOW\n", encoding="utf-8", newline="\n")

        host_mjs = plugin_dir / "opencode_host.mjs"
        paths_mjs = plugin_dir / "paths.mjs"
        # JSDoc mentions windowsHide: true twice AND regex.exec() is used; every real spawn passes windowsHide: true
        host_mjs.write_text(
            "/**\n * Every spawn uses windowsHide: true; never omit windowsHide: true.\n */\n"
            "const TOKEN_RE = /tok_([a-z]+)/;\n"
            "const match = TOKEN_RE.exec(rawCmd);\n"
            "spawn(py, ['a'], { windowsHide: true });\n"
            "spawnSync('taskkill', ['/F'], { stdio: 'ignore', windowsHide: true });\n",
            encoding="utf-8",
            newline="\n",
        )
        paths_mjs.write_text(
            "const QUOTED_RE = /[\"'`]+\\.exe/i;\n"
            "spawnSync('python.exe', ['-V'], { timeout: 2000, windowsHide: true });\n",
            encoding="utf-8",
            newline="\n",
        )
        self.assertEqual(host_gate.verify_windows_windowless_spawns([self.root]), [])

        # JSDoc block comments with extra `windowsHide: true` CANNOT mask an unhidden second spawn()
        host_mjs.write_text(
            "/**\n * windowsHide: true and windowsHide: true in JSDoc.\n */\n"
            "spawn(py, ['a'], { windowsHide: true });\n"
            "spawn(py, ['b'], { stdio: 'ignore' });\n",
            encoding="utf-8",
            newline="\n",
        )
        jsdoc_errors = host_gate.verify_windows_windowless_spawns([self.root])
        self.assertEqual(len(jsdoc_errors), 1)
        self.assertIn("opencode_host.mjs line 5 `spawn(...)` missing `windowsHide: true`", jsdoc_errors[0])

        # Fix opencode_host.mjs, then omit windowsHide in companion paths.mjs -> caught!
        host_mjs.write_text("spawn(py, ['a'], { windowsHide: true });\n", encoding="utf-8", newline="\n")
        paths_mjs.write_text(
            "const QUOTED_RE = /[\"'`]+\\.exe/i;\n"
            "spawnSync('python.exe', ['-V'], { timeout: 2000 });\n",
            encoding="utf-8",
            newline="\n",
        )
        paths_errors = host_gate.verify_windows_windowless_spawns([self.root])
        self.assertEqual(len(paths_errors), 1)
        self.assertIn("plugins/mindie-agent/paths.mjs line 2 `spawnSync(...)`", paths_errors[0])

        # Missing required opencode_host.mjs fails explicitly instead of silently skipping
        paths_mjs.unlink()
        host_mjs.unlink()
        missing_mjs = host_gate.verify_windows_windowless_spawns([self.root])
        self.assertEqual(len(missing_mjs), 1)
        self.assertIn("missing expected Node subprocess host plugins/mindie-agent/opencode_host.mjs", missing_mjs[0])

    def test_r4_zero_popup_runs_without_knowledge_import_and_rejects_missing_required_repos(self):
        dsh = self._make_repo("mindie-agent-dsh")
        (dsh / "scripts").mkdir(parents=True)
        (dsh / "scripts" / "setup_process.py").write_text("subprocess.CREATE_NO_WINDOW\n", encoding="utf-8", newline="\n")
        (dsh / "scripts" / "knowledge_mcp.py").write_text("subprocess.CREATE_NO_WINDOW\n", encoding="utf-8", newline="\n")
        (dsh / "host3.mjs").write_text("spawn('python', ['x'], { detached: true })\n", encoding="utf-8", newline="\n")

        # Even when mindie_knowledge is NOT importable, R4 still runs windowless_check and catches popup bug
        errors = host_gate.verify_flexible_component_compatibility_impl(
            [self.root],
            ensure_knowledge_importable=lambda _r: False,
            windowless_check=host_gate.verify_windows_windowless_spawns,
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("mindie-agent-dsh: host3.mjs", errors[0])

        # Empty siblings_root fails explicitly when --release-repo or --require-siblings demands verification
        empty_dir = self.root / "empty-siblings"
        empty_dir.mkdir()
        rel_errors = host_gate.verify_windows_windowless_spawns([empty_dir], required_repos=["mindie-agent-dsh"])
        self.assertTrue(any("mindie-agent-dsh: sibling checkout not found" in err for err in rel_errors), rel_errors)

        req_errors = host_gate.verify_flexible_component_compatibility_impl(
            [empty_dir],
            ensure_knowledge_importable=lambda _r: False,
            windowless_check=lambda r: host_gate.verify_windows_windowless_spawns(r, require_siblings=True),
            require_siblings=True,
        )
        self.assertTrue(any("mindie_knowledge unavailable" in err for err in req_errors), req_errors)
        self.assertTrue(any("diagnostics: sibling checkout not found" in err for err in req_errors), req_errors)

        # Main-repo .github/scripts/*.py per-call subprocess check catches unguarded second subprocess.run
        fake_main = self.root / "fake-main"
        scripts = fake_main / ".github" / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "helper.py").write_text(
            "import subprocess\n"
            "subprocess.run(['git', 'status'], creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))\n"
            "subprocess.run(['git', 'diff'])\n",
            encoding="utf-8",
            newline="\n",
        )
        main_errs = host_gate.verify_windows_windowless_spawns([empty_dir], main_repo=fake_main)
        self.assertEqual(len(main_errs), 1)
        self.assertIn("mindie-agent: .github/scripts/helper.py", main_errs[0])

    def test_which_native_filters_wsl_mounts_and_windows_store_stubs(self):
        heads = {
            "/mnt/c/npm/codex": (
                b"#!/bin/sh\n"
                b"case `uname` in *CYGWIN*|*MINGW*|*MSYS*) basedir=`cygpath -w \"$basedir\"`;; esac\n"
                b"exec node \"$basedir/cli.js\"\n"
            ),
            "/mnt/c/work/.venv/bin/kimi": (
                b"#!/mnt/c/work/.venv/bin/python\n"
                b"import re, sys\n"
                b"sys.argv[0] = re.sub(r'(-script\\.pyw|\\.exe)?$', '', sys.argv[0])\n"
            ),
        }
        posix_os = SimpleNamespace(
            name="posix",
            pathsep=":",
            environ={"PATH": "/mnt/c/npm:/shim:/usr/bin"},
            read_head=lambda p: heads.get(str(p), b"MZ\x90\x00"),
        )

        def posix_which(cmd, path=None):
            mapping = {
                "/mnt/c/npm": f"/mnt/c/npm/{cmd}",
                "/shim": f"/shim/{cmd}.cmd",
                "/usr/bin": f"/usr/bin/{cmd}",
                "/mnt/c/work/.venv/bin": f"/mnt/c/work/.venv/bin/{cmd}",
            }
            return mapping.get(path)

        fake_shutil = SimpleNamespace(which=posix_which)
        self.assertEqual(
            host_gate.which_native("codex", os_mod=posix_os, shutil_mod=fake_shutil),
            "/usr/bin/codex",
        )
        venv_os = SimpleNamespace(
            name="posix",
            pathsep=":",
            environ={"PATH": "/mnt/c/work/.venv/bin:/usr/bin"},
            read_head=lambda p: heads.get(str(p), b"\x7fELF"),
        )
        self.assertEqual(
            host_gate.which_native("kimi", os_mod=venv_os, shutil_mod=fake_shutil),
            "/mnt/c/work/.venv/bin/kimi",
        )

        win_stub = r"C:\Users\alice\AppData\Local\Microsoft\WindowsApps\python.exe"
        win_real = r"C:\Users\alice\AppData\Local\Programs\Python\Python312\python.exe"

        def win_stat(target):
            if target == win_stub:
                return SimpleNamespace(st_size=0)
            return SimpleNamespace(st_size=102400)

        nt_os = SimpleNamespace(
            name="nt",
            pathsep=";",
            environ={"PATH": r"C:\Empty;" + r"C:\Users\alice\AppData\Local\Microsoft\WindowsApps;" + r"C:\Python312"},
            stat=win_stat,
        )

        def win_which(cmd, path=None):
            if path and "WindowsApps" in path:
                return win_stub
            if path and "Python312" in path:
                return win_real
            return None

        self.assertEqual(
            host_gate.which_native("python", os_mod=nt_os, shutil_mod=SimpleNamespace(which=win_which)),
            win_real,
        )

        timeout_os = SimpleNamespace(
            name="nt",
            pathsep=";",
            environ={"PATH": r"C:\Users\alice\AppData\Local\Microsoft\WindowsApps"},
            stat=lambda _p: (_ for _ in ()).throw(TimeoutError("deadline")),
        )
        with self.assertRaises(TimeoutError):
            host_gate.which_native("python", os_mod=timeout_os, shutil_mod=SimpleNamespace(which=win_which))

    def test_run_cmd_attaches_create_no_window_on_windows(self):
        captured: dict = {}

        def fake_run(argv, **kwargs):
            captured.update(kwargs)
            return subprocess.CompletedProcess(argv, 0, "ok", "")

        nt_os = SimpleNamespace(
            name="nt",
            pathsep=";",
            environ={"PATH": r"C:\Git\cmd"},
            stat=lambda _p: SimpleNamespace(st_size=102400),
        )
        nt_subproc = SimpleNamespace(
            CREATE_NO_WINDOW=0x08000000,
            run=fake_run,
            CompletedProcess=subprocess.CompletedProcess,
        )
        with patch.object(gate, "os", nt_os), patch.object(gate, "subprocess", nt_subproc), patch.object(
            gate.shutil, "which", return_value=r"C:\Git\cmd\git.exe"
        ):
            res = gate._run_cmd(["git", "--version"])
        self.assertEqual(res.returncode, 0)
        self.assertEqual(captured.get("creationflags"), 0x08000000)

        posix_os = SimpleNamespace(name="posix", pathsep=":", environ={"PATH": "/usr/bin"})
        never_run = SimpleNamespace(
            run=lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("subprocess.run must not be called")),
            CompletedProcess=subprocess.CompletedProcess,
        )
        with patch.object(gate, "os", posix_os), patch.object(gate, "subprocess", never_run):
            rejected = gate._run_cmd(["/mnt/c/Windows/git.exe", "--version"])
        self.assertEqual(rejected.returncode, 127)

        sac_subproc = SimpleNamespace(
            CREATE_NO_WINDOW=0x08000000,
            run=lambda *_a, **_kw: (_ for _ in ()).throw(OSError(4551, "Smart App Control blocked file")),
            CompletedProcess=subprocess.CompletedProcess,
        )
        with patch.object(gate, "os", nt_os), patch.object(gate, "subprocess", sac_subproc), patch.object(
            gate.shutil, "which", return_value=r"C:\Python\python.exe"
        ):
            sac_res = gate._run_cmd(["python", "--version"])
        self.assertEqual(sac_res.returncode, 126)

        timeout_subproc = SimpleNamespace(
            CREATE_NO_WINDOW=0x08000000,
            run=lambda *_a, **_kw: (_ for _ in ()).throw(TimeoutError("probe timed out")),
            CompletedProcess=subprocess.CompletedProcess,
        )
        with patch.object(gate, "os", nt_os), patch.object(gate, "subprocess", timeout_subproc), patch.object(
            gate.shutil, "which", return_value=r"C:\Python\python.exe"
        ):
            with self.assertRaises(TimeoutError):
                gate._run_cmd(["python", "--version"])

    def test_configured_non_native_codex_binary_is_reported_without_launching(self):
        codex_repo = self._make_repo("mindie-agent-codex")
        compat_file = codex_repo / "plugins" / "mindie-agent" / "harness-compatibility.json"
        compat_file.parent.mkdir(parents=True)
        compat_file.write_text(
            '{\n'
            '  "schema": "mindie.harness_compatibility/1",\n'
            '  "harness": "codex",\n'
            '  "supported": [{"minimum": "0.150.0", "maximum": "0.199.0", "include_prerelease": true}],\n'
            '  "used_interfaces": ["codex.plugin.manifest/1"],\n'
            '  "interface_registry": {"codex.plugin.manifest/1": {"introduced": "0.150.0"}}\n'
            '}\n',
            encoding="utf-8",
            newline="\n",
        )

        bad_exe = self.root / "codex.exe"
        bad_exe.write_bytes(b"MZ\x90\x00")
        cfg_dir = Path(os.environ["MINDIE_CONFIG_HOME"])
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "codex.json").write_text(
            f'{{"native_context": {{"MINDIE_CODEX_BIN": "{bad_exe.as_posix()}"}}}}\n',
            encoding="utf-8",
            newline="\n",
        )
        launched: list[list[str]] = []
        posix_os = SimpleNamespace(
            name="posix",
            environ=os.environ,
            path=os.path,
            pathsep=":",
        )
        with patch.object(host_gate, "os", posix_os):
            errors = host_gate.verify_local_host_compatibility_impl(
                [self.root],
                ensure_knowledge_importable=lambda _r: True,
                which_fn=lambda _c: None,
                run_cmd=lambda argv: launched.append(argv) or subprocess.CompletedProcess(argv, 0, "0.153.4", ""),
            )
        self.assertEqual(launched, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("configured Codex CLI is not a native executable", errors[0])


if __name__ == "__main__":
    unittest.main()

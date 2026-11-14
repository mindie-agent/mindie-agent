"""Unit contracts for R4 Windows windowless subprocess checks and WSL2/Windows binary filtering."""
from __future__ import annotations

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


class HostCompatibilityGateTests(unittest.TestCase):
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

    def _make_repo(self, name: str) -> Path:
        repo = self.root / name
        (repo / ".git").mkdir(parents=True)
        return repo

    def test_diagnostics_r4_accepts_github_transport_or_legacy_reporter_and_rejects_missing_flag(self):
        diag = self._make_repo("diagnostics")
        svc = diag / "mindie_diagnostics" / "platform_service.py"
        transport = diag / "mindie_diagnostics" / "github_transport.py"
        reporter = diag / "mindie_diagnostics" / "reporter.py"
        transport.parent.mkdir(parents=True)
        svc.write_text("subprocess.CREATE_NO_WINDOW\n", encoding="utf-8", newline="\n")

        # 1. Refactored layout (diagnostics >= 0.5.11): github_transport.py enforces CREATE_NO_WINDOW
        transport.write_text("flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)\n", encoding="utf-8", newline="\n")
        reporter.write_text("# reporter delegates to github_transport\n", encoding="utf-8", newline="\n")
        self.assertEqual(host_gate.verify_windows_windowless_spawns([self.root]), [])

        # 1b. Missing CREATE_NO_WINDOW in platform_service.py is also caught
        svc.write_text("# missing flag\n", encoding="utf-8", newline="\n")
        svc_errors = host_gate.verify_windows_windowless_spawns([self.root])
        self.assertEqual(len(svc_errors), 1)
        self.assertIn("diagnostics: mindie_diagnostics/platform_service.py", svc_errors[0])
        svc.write_text("subprocess.CREATE_NO_WINDOW\n", encoding="utf-8", newline="\n")

        # 2. First present candidate is authoritative: if github_transport.py omits CREATE_NO_WINDOW, fail
        transport.write_text("# missing flag\n", encoding="utf-8", newline="\n")
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

    def test_mindie_bench_and_dsh_windowless_checks(self):
        bench = self._make_repo("mindie-bench")
        hp = bench / "src" / "mindie_bench" / "runner" / "host_platform.py"
        hp.parent.mkdir(parents=True)
        hp.write_text("CREATE_NO_WINDOW = 0x08000000\n", encoding="utf-8", newline="\n")

        dsh = self._make_repo("mindie-agent-dsh")
        (dsh / "scripts").mkdir(parents=True)
        (dsh / "scripts" / "setup_process.py").write_text("subprocess.CREATE_NO_WINDOW\n", encoding="utf-8", newline="\n")
        (dsh / "scripts" / "knowledge_mcp.py").write_text("subprocess.CREATE_NO_WINDOW\n", encoding="utf-8", newline="\n")
        (dsh / "host3.mjs").write_text(
            "spawn('python', ['a'], { windowsHide: true })\n"
            "spawn('python', ['b'], { detached: true, windowsHide: true })\n",
            encoding="utf-8",
            newline="\n",
        )
        self.assertEqual(host_gate.verify_windows_windowless_spawns([self.root]), [])

        # Missing windowsHide on one spawn in host3.mjs is caught
        (dsh / "host3.mjs").write_text(
            "spawn('python', ['a'], { windowsHide: true })\n"
            "spawn('python', ['b'], { detached: true })\n",
            encoding="utf-8",
            newline="\n",
        )
        errors = host_gate.verify_windows_windowless_spawns([self.root])
        self.assertEqual(len(errors), 1)
        self.assertIn("mindie-agent-dsh: host3.mjs", errors[0])

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
        # Valid Linux pip/uv virtualenv script on /mnt/c/... (including r'(-script\.pyw|\.exe)?$') is accepted
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

        # TimeoutError inside stat() must never be swallowed as a stub
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

        # Launch boundary preserves rejection: non-native .exe on POSIX returns 127 without calling subprocess.run
        posix_os = SimpleNamespace(name="posix", pathsep=":", environ={"PATH": "/usr/bin"})
        never_run = SimpleNamespace(
            run=lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("subprocess.run must not be called")),
            CompletedProcess=subprocess.CompletedProcess,
        )
        with patch.object(gate, "os", posix_os), patch.object(gate, "subprocess", never_run):
            rejected = gate._run_cmd(["/mnt/c/Windows/git.exe", "--version"])
        self.assertEqual(rejected.returncode, 127)

        # Smart App Control OSError (e.g. WinError 4551) maps to exit 126, while TimeoutError propagates
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

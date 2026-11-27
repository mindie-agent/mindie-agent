"""Unit and end-to-end contracts for the top-level `install.py` bootstrap installer.

[Role]
Verifies read-only host detection (`PATH`, WindowsApps stubs, WSL shims, bundles, aliases),
disposable `GH_CONFIG_DIR` probe behavior, deterministic dry-run/no-host JSON, channel and
preflight rejections (insecure URL, offline HTTPS, checksum mismatch, bundle cap, tar traversal,
disk floor), and a real offline local-wheelhouse install through a deterministic fake `uv`.

[Invariants]
- Isolates `HOME`, `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `XDG_*`, `MINDIE_CONFIG_HOME`,
  `MINDIE_DATA_HOME`, `MINDIE_DIAGNOSTICS_ROOT`, `REMOTE_DEV_AUTH_DIR`, `UV_CACHE_DIR`, and `TMPDIR`.
- Pure stdlib fixtures (`zipfile`, `tarfile`, `hashlib`) with a portable fake `uv`/`gh`; zero
  network calls and zero writes outside `tempfile.TemporaryDirectory`.

[Timeouts & Locks]
- Tier 1 local process fixtures; the end-to-end install remains under ~0.5s on all platforms.

[Side-Effect Policy]
- Writes only inside disposable temporary roots cleaned up after every test.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import zipfile

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / ".github" / "scripts"
for entry in (str(REPO_ROOT), str(SCRIPTS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import install  # noqa: E402
import storage_lifecycle_gate  # noqa: E402
import windows_zero_popup_gate  # noqa: E402

ENV_KEYS = (
    "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
    "XDG_STATE_HOME", "XDG_CACHE_HOME", "MINDIE_CONFIG_HOME", "MINDIE_DATA_HOME",
    "MINDIE_DIAGNOSTICS_ROOT", "REMOTE_DEV_AUTH_DIR", "UV_CACHE_DIR", "TMPDIR", "TEMP", "TMP",
)
CLI_SOURCE = """
import argparse, json, os, sys
from pathlib import Path
from mindie_harness import runtime

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    install = sub.add_parser("install")
    install.add_argument("--host", required=True)
    install.add_argument("--channel-base-url", required=True)
    install.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    cfg_root = Path(os.environ.get("MINDIE_CONFIG_HOME") or (Path.home() / ".config/mindie-agent"))
    cfg = Path(os.environ.get("MINDIE_AGENT_CONFIG") or cfg_root / f"{args.host}.json")
    data = Path(os.environ.get("MINDIE_DATA_HOME") or (Path.home() / ".local/share/mindie-agent"))
    banner = runtime.main()
    cfg.parent.mkdir(parents=True, exist_ok=True)
    py_val = "" if os.environ.get("MINDIE_TEST_OMIT_PYTHON") == "1" else sys.executable
    cfg.write_text(
        json.dumps({"host": args.host, "python": py_val, "channel_base_url": args.channel_base_url, "runtime": banner}), encoding="utf-8"
    )
    cache = data / "state" / args.host
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "channel-cache.json").write_text(json.dumps({"channel_base_url": args.channel_base_url}), encoding="utf-8")
    print(json.dumps({"configured_hosts": [args.host]}))

if __name__ == "__main__":
    main()
"""
RUNTIME_SOURCE = "VERSION = '0.1.0'\n\ndef main():\n    return {'runtime': 'mindie-harness', 'version': VERSION}\n"
FAKE_UV_SOURCE = """
import os, sys, venv, zipfile
from pathlib import Path

def _site(target):
    if os.name == "nt":
        return target / "Lib" / "site-packages"
    return target / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"

def _venv(target):
    venv.create(target, with_pip=False, clear=True)
    _site(target).mkdir(parents=True, exist_ok=True)

def main():
    args = sys.argv[1:]
    if len(args) < 2:
        return 2
    if args[0] == "venv":
        _venv(Path(args[-1]))
        return 0
    if args[0] == "pip" and args[1] == "install":
        python = Path(args[args.index("--python") + 1]) if "--python" in args else Path(sys.executable)
        site = _site(python.parent.parent)
        for raw in args[2:]:
            wheel = Path(raw)
            if wheel.suffix == ".whl":
                with zipfile.ZipFile(wheel) as archive:
                    archive.extractall(site)
        return 0
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
"""
FAKE_GH_SOURCE = """
import os, sys
from pathlib import Path

marker = os.environ.get("MINDIE_TEST_GH_MARKER")
if marker:
    Path(marker).write_text("ran", encoding="utf-8")
config = Path(os.environ.get("GH_CONFIG_DIR", ""))
hosts = config / "hosts.yml"
if hosts.is_file() and "octocat" in hosts.read_text(encoding="utf-8"):
    print("octocat")
    raise SystemExit(0)
raise SystemExit(1)
"""


class InstallScriptTests(unittest.TestCase):
    """Covers detection, `gh` probing, preflight rejections, and the offline wheelhouse install."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tools_dir = tempfile.TemporaryDirectory(prefix="mindie-install-tools-")
        cls.tools_path = Path(cls.tools_dir.name)
        for name, source in (("uv", FAKE_UV_SOURCE), ("gh", FAKE_GH_SOURCE)):
            script = cls.tools_path / f"fake_{name}.py"
            script.write_text(source, encoding="utf-8", newline="\n")
            if os.name == "nt":
                wrapper = cls.tools_path / f"{name}.cmd"
                wrapper.write_text(f'@echo off\r\n"{sys.executable}" "{script}" %*\r\n', encoding="utf-8", newline="")
                warm = [str(wrapper)]
            else:
                wrapper = cls.tools_path / name
                wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
                wrapper.chmod(0o755)
                warm = [str(wrapper), "warmup"] if name == "uv" else [str(wrapper)]
            subprocess.run(warm, capture_output=True, check=False, creationflags=0x08000000 if os.name == "nt" else 0)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tools_dir.cleanup()

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="mindie-install-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        self.cfg = self.root / "cfg"
        self.data = self.root / "data"
        self.tmpdir = self.root / "tmp"
        self.tmpdir.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        env = {key: str(self.root / key) for key in ENV_KEYS}
        for win_key in ("SystemRoot", "SYSTEMROOT", "ComSpec", "COMSPEC", "WINDIR"):
            if os.environ.get(win_key):
                env[win_key] = os.environ[win_key]
        env.update({"HOME": str(self.home), "USERPROFILE": str(self.home),
                    "TMPDIR": str(self.tmpdir), "TEMP": str(self.tmpdir), "TMP": str(self.tmpdir),
                    "MINDIE_CONFIG_HOME": str(self.cfg), "MINDIE_DATA_HOME": str(self.data),
                    "UV_CACHE_DIR": str(self.root / "uv-cache"),
                    "PATH": os.pathsep.join([str(self.tools_path), str(self.bin)]),
                    "GH_CONFIG_DIR": str(self.root / "real-gh"), "MINDIE_CHANNEL_BASE_URL": ""})
        self.env = env
        environment = patch.dict(os.environ, env, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        tempdir = patch.object(tempfile, "tempdir", str(self.tmpdir))
        tempdir.start()
        self.addCleanup(tempdir.stop)
        disk = patch.object(install.shutil, "disk_usage", return_value=SimpleNamespace(total=10**13, used=0, free=10**12))
        disk.start()
        self.addCleanup(disk.stop)

    def _run(self, argv: list[str]) -> tuple[int, dict]:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = install.main(argv)
        return code, json.loads(buffer.getvalue())

    def _write(self, path: Path, text: str | bytes, *, executable: bool = False) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(text, bytes):
            path.write_bytes(text)
        else:
            path.write_text(text, encoding="utf-8", newline="\n")
        if executable and os.name != "nt":
            path.chmod(0o755)
        return path

    def _build_wheel(self, directory: Path) -> Path:
        wheel = directory / "mindie_harness-0.1.0-py3-none-any.whl"
        files = {
            "mindie_harness/__init__.py": "__version__ = '0.1.0'\n",
            "mindie_harness/runtime.py": RUNTIME_SOURCE,
            "mindie_harness/cli.py": CLI_SOURCE,
            "mindie_harness-0.1.0.dist-info/METADATA": "Metadata-Version: 2.1\nName: mindie-harness\nVersion: 0.1.0\n",
            "mindie_harness-0.1.0.dist-info/WHEEL": "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
            "mindie_harness-0.1.0.dist-info/RECORD": "",
        }
        with zipfile.ZipFile(wheel, "w") as archive:
            for name, content in files.items():
                archive.writestr(name, content)
        return wheel

    def _write_channel(self, directory: Path | None = None, *, tamper: bool = False, bundle_size: int | None = None, unsafe_member: bool = False) -> Path:
        channel = directory or (self.root / "channel")
        channel.mkdir(parents=True, exist_ok=True)
        self._write(channel / "release-channel.json", json.dumps({"product_version": "0.1.16"}))
        if bundle_size is not None:
            (channel / "mindie-wheels-bundle.tar.gz").write_bytes(b"\0" * bundle_size)
        else:
            wheel = self._build_wheel(channel)
            with tarfile.open(channel / "mindie-wheels-bundle.tar.gz", "w:gz") as archive:
                if unsafe_member:
                    payload = b"evil"
                    info = tarfile.TarInfo("../evil.whl")
                    info.size = len(payload)
                    archive.addfile(info, io.BytesIO(payload))
                else:
                    archive.add(wheel, arcname=wheel.name)
                    payload = b"mindie-harness==0.1.0\n"
                    info = tarfile.TarInfo("requirements.lock")
                    info.size = len(payload)
                    archive.addfile(info, io.BytesIO(payload))
        release_digest = hashlib.sha256((channel / "release-channel.json").read_bytes()).hexdigest()
        bundle_digest = hashlib.sha256((channel / "mindie-wheels-bundle.tar.gz").read_bytes()).hexdigest()
        if tamper:
            release_digest = "0" * 64
        lines = f"{release_digest}  release-channel.json\n{bundle_digest}  mindie-wheels-bundle.tar.gz\n"
        self._write(channel / "SHA256SUMS", lines)
        return channel

    def test_detect_hosts_from_path_binaries_config_dirs_and_app_bundles(self) -> None:
        ext = ".cmd" if os.name == "nt" else ""
        for name in ("codex", "claude", "kimi", "dsh", "agy", "wb", "opencode", "omp"):
            self._write(self.bin / f"{name}{ext}", "@echo off\n", executable=True)
        self.assertEqual(install.detect_installed_hosts(self.env), list(install.HOSTS))

        empty = self.root / "empty-bin"
        empty.mkdir()
        dirs = {
            "codex": self.home / ".codex",
            "cc": self.home / ".claude",
            "kimi": self.home / ".kimi",
            "dsh": self.home / ".dsh",
            "agy": self.home / ".gemini/antigravity",
            "wb": self.home / ".workbuddy",
            "oc": self.home / ".config/opencode",
            "omp": self.home / ".omp",
        }
        for path in dirs.values():
            path.mkdir(parents=True)
        self.assertEqual(install.detect_installed_hosts({**self.env, "PATH": str(empty)}), list(install.HOSTS))

    def test_which_native_rejects_windowsapps_stubs_and_wsl_shims(self) -> None:
        stub = self._write(self.root / "Microsoft/WindowsApps/codex.exe", "")
        real = self._write(self.root / "real/codex.exe", "MZ")
        env = {"PATH": os.pathsep.join([str(stub.parent), str(real.parent)])}
        self.assertEqual(install._which_native("codex", env, platform="nt"), str(real))
        self.assertIsNone(install._which_native("codex", {"PATH": str(stub.parent)}, platform="nt"))

        wsl_root = self.root / "wsl-root"
        wsl_root.mkdir()
        self._write(wsl_root / "codex", "#!/bin/sh\ncygpath -w \"$basedir\"\nexec node cli.js\n", executable=True)
        RealPath = install.Path

        class MappedPath:
            def __init__(self, raw: object) -> None:
                self.text = str(raw)
                mapped = self.text.replace("/mnt/c", str(wsl_root), 1) if self.text.startswith("/mnt/c") else self.text
                self.inner = RealPath(mapped)

            def __truediv__(self, other: object) -> "MappedPath":
                return MappedPath(f"{self.text}/{other}")

            def __getattr__(self, name: str) -> object:
                return getattr(self.inner, name)

            def __str__(self) -> str:
                return self.text

            def __fspath__(self) -> str:
                return os.fspath(self.inner)

        with patch.object(install, "Path", MappedPath):
            self.assertIsNone(install._which_native("codex", {"PATH": "/mnt/c"}, platform="posix"))
            self._write(wsl_root / "codex", b"\x7fELFrest", executable=True)
            self.assertEqual(install._which_native("codex", {"PATH": "/mnt/c"}, platform="posix"), "/mnt/c/codex")
            (wsl_root / "codex").unlink()
            self._write(wsl_root / "codex.exe", b"MZ")
            self.assertIsNone(install._which_native("codex", {"PATH": "/mnt/c"}, platform="posix"))

    def test_host_aliases_normalize_in_dry_run(self) -> None:
        for alias, canonical in (("claude", "cc"), ("antigravity", "agy"), ("workbuddy", "wb"), ("opencode", "oc"), ("oh-my-pi", "omp")):
            with self.subTest(alias=alias):
                code, payload = self._run(["--host", alias, "--dry-run", "--json"])
                self.assertEqual(code, 0)
                self.assertEqual(payload["planned_hosts"], [canonical])
        code, payload = self._run(["--host", "bogus", "--dry-run", "--json"])
        self.assertEqual((code, payload["reason"]), (1, "invalid_host"))

    def test_probe_gh_missing_offline_and_disposable_auth(self) -> None:
        missing = install.probe_gh_status({"PATH": str(self.root / "empty-bin")})
        self.assertEqual((missing["gh_probe_status"], missing["recommended_tier"]), ("not_installed", "local-only"))
        marker = self.root / "gh-ran"
        offline = install.probe_gh_status({**self.env, "MINDIE_TEST_GH_MARKER": str(marker)}, offline=True)
        self.assertEqual(offline["gh_probe_status"], "skipped_offline")
        self.assertFalse(marker.exists())

        real_gh = self.root / "real-gh"
        real_gh.mkdir()
        self._write(real_gh / "hosts.yml", "github.com:\n    user: octocat\n")
        before = (real_gh / "hosts.yml").read_bytes()
        probe = install.probe_gh_status({**self.env, "GH_CONFIG_DIR": str(real_gh)})
        self.assertTrue(probe["gh_authenticated"])
        self.assertEqual(probe["gh_account"], "octocat")
        self.assertEqual(probe["recommended_tier"], "contribute")
        self.assertEqual((real_gh / "hosts.yml").read_bytes(), before)
        self.assertEqual(list(self.tmpdir.glob("mindie-gh-cfg-*")), [])

    def test_auto_detects_an_omp_session_without_the_cli_on_path(self) -> None:
        with patch.dict(os.environ, {"PI_SESSION_ID": "test-session"}):
            code, payload = self._run(["--host", "auto", "--dry-run"])
        self.assertEqual((code, payload["detected_hosts"], payload["planned_hosts"]), (0, ["omp"], ["omp"]))

    def test_dry_run_and_empty_auto_create_no_state_directories(self) -> None:
        gh_marker = self.root / "gh-should-not-run"
        with patch.dict(os.environ, {"MINDIE_TEST_GH_MARKER": str(gh_marker)}):
            code, payload = self._run(["--dry-run", "--json"])
            self.assertEqual(code, 0)
            for key in ("detected_hosts", "configured_hosts", "gh_authenticated", "gh_account", "recommended_tier", "next_questions"):
                self.assertIn(key, payload)
            self.assertFalse(gh_marker.exists())
            self.assertFalse(self.cfg.exists())
            self.assertFalse(self.data.exists())
            with patch.object(install, "detect_installed_hosts", return_value=[]):
                code, payload = self._run(["--json"])
            self.assertEqual((code, payload["status"], payload["detected_hosts"]), (0, "no_hosts", []))
            self.assertFalse(gh_marker.exists())
            self.assertFalse(self.cfg.exists())
            self.assertFalse(self.data.exists())

    def test_preflight_and_channel_rejections(self) -> None:
        code, payload = self._run(["--host", "codex", "--channel-base-url", "http://example.test", "--json"])
        self.assertEqual((code, payload["reason"]), (1, "insecure_channel_url"))
        code, payload = self._run(["--host", "codex", "--offline", "--json"])
        self.assertEqual((code, payload["reason"]), (1, "offline_remote_channel"))
        channel = self._write_channel()
        with patch.object(install.shutil, "disk_usage", return_value=SimpleNamespace(total=1, used=1, free=1)):
            code, payload = self._run(["--host", "codex", "--channel-base-url", str(channel), "--offline", "--json"])
        self.assertEqual((code, payload["reason"]), (1, "insufficient_disk_space"))
        cases = (
            ({"tamper": True}, "checksum_mismatch"),
            ({"bundle_size": install.MAX_BUNDLE_BYTES + 1}, "bundle_too_large"),
            ({"unsafe_member": True}, "unsafe_bundle_member"),
        )
        for index, (options, reason) in enumerate(cases):
            with self.subTest(reason=reason):
                channel = self._write_channel(self.root / f"channel-{index}", **options) if index else self._write_channel(**options)
                code, payload = self._run(["--host", "codex", "--channel-base-url", str(channel), "--offline", "--json"])
                self.assertEqual((code, payload["reason"]), (1, reason))

    def test_offline_local_wheelhouse_install_replaces_stage_reference(self) -> None:
        channel = self._write_channel()
        code, payload = self._run(["--host", "codex", "--channel-base-url", str(channel), "--offline", "--json"])
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "installed")
        self.assertEqual(payload["configured_hosts"], ["codex"])
        self.assertEqual(list(self.data.glob("mindie-stage-*")), [])
        configured = json.loads((self.cfg / "codex.json").read_text(encoding="utf-8"))
        self.assertEqual(configured["channel_base_url"], str(channel))
        self.assertEqual(configured["runtime"]["runtime"], "mindie-harness")
        cached = json.loads((self.data / "state/codex/channel-cache.json").read_text(encoding="utf-8"))
        self.assertEqual(cached["channel_base_url"], str(channel))

    def test_auto_provisions_codex_and_omp_in_separate_profiles(self) -> None:
        channel = self._write_channel()
        ext = ".cmd" if os.name == "nt" else ""
        for name in ("codex", "omp"):
            self._write(self.bin / f"{name}{ext}", "@echo off\n", executable=True)
        code, payload = self._run(["--host", "auto", "--channel-base-url", str(channel), "--offline"])
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["configured_hosts"], ["codex", "omp"])
        for host in ("codex", "omp"):
            config = json.loads((self.cfg / f"{host}.json").read_text(encoding="utf-8"))
            cache = json.loads((self.data / "state" / host / "channel-cache.json").read_text(encoding="utf-8"))
            self.assertEqual(config["host"], host)
            self.assertEqual(config["channel_base_url"], str(channel))
            self.assertEqual(cache["channel_base_url"], str(channel))

    def test_omp_install_preserves_inherited_codex_config(self) -> None:
        channel = self._write_channel()
        codex_config = self._write(self.cfg / "codex.json", '{"host":"codex","user_setting":true}')
        previous = codex_config.read_bytes()
        with patch.dict(os.environ, {"MINDIE_AGENT_CONFIG": str(codex_config)}):
            code, payload = self._run(["--host", "omp", "--channel-base-url", str(channel), "--offline"])
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["configured_hosts"], ["omp"])
        self.assertEqual(codex_config.read_bytes(), previous)
        self.assertEqual(json.loads((self.cfg / "omp.json").read_text(encoding="utf-8"))["host"], "omp")

    def test_real_install_py_passes_storage_and_windows_static_gates(self) -> None:
        self.assertEqual(storage_lifecycle_gate.verify_storage_lifecycle_hygiene([], main_repo=REPO_ROOT), [])
        self.assertEqual(windows_zero_popup_gate.verify_windows_windowless_spawns([], main_repo=REPO_ROOT), [])

    def test_wheel_allowlist_partial_success_and_child_receipt_warnings(self) -> None:
        # 1. Unlisted extra wheel (mindie_harness-9.9.9) in bundle is rejected
        bad_dir = self.root / "bad-bundle-channel"
        bad_dir.mkdir(parents=True, exist_ok=True)
        self._write(bad_dir / "release-channel.json", json.dumps({"current_patch_version": "0.1.16"}))
        good_wheel = self._build_wheel(bad_dir)
        rogue_wheel = bad_dir / "mindie_harness-9.9.9-py3-none-any.whl"
        shutil.copy2(good_wheel, rogue_wheel)
        with tarfile.open(bad_dir / "mindie-wheels-bundle.tar.gz", "w:gz") as archive:
            archive.add(good_wheel, arcname=good_wheel.name)
            archive.add(rogue_wheel, arcname=rogue_wheel.name)
            req = b"mindie-harness==0.1.0\n"
            info = tarfile.TarInfo("requirements.txt")
            info.size = len(req)
            archive.addfile(info, io.BytesIO(req))
        r_sum = hashlib.sha256((bad_dir / "release-channel.json").read_bytes()).hexdigest()
        b_sum = hashlib.sha256((bad_dir / "mindie-wheels-bundle.tar.gz").read_bytes()).hexdigest()
        self._write(
            bad_dir / "SHA256SUMS",
            f"{r_sum}  release-channel.json\n{b_sum}  mindie-wheels-bundle.tar.gz\n",
        )
        code, payload = self._run(["--host", "codex", "--channel-base-url", str(bad_dir), "--offline", "--json"])
        self.assertEqual((code, payload["reason"]), (1, "unsafe_bundle_member"))

        # 2. Partial success preserved when second host spawn raises OSError + child receipt_warning forwarded
        channel = self._write_channel(self.root / "partial-channel")
        real_run = install._run_cmd

        def flaky_run(argv, *, env, timeout):
            if "mindie_harness.cli" in argv and "cc" in argv:
                raise OSError("cc spawn failed")
            proc = real_run(argv, env=env, timeout=timeout)
            if "mindie_harness.cli" in argv and "codex" in argv:
                return subprocess.CompletedProcess(
                    argv,
                    0,
                    json.dumps({
                        "configured_hosts": ["codex"],
                        "receipt_unconfirmed": True,
                        "receipt_warning": "local_bind_warn",
                    }),
                    "",
                )
            return proc

        with patch.object(install, "detect_installed_hosts", return_value=["codex", "cc"]), patch.object(
            install, "_run_cmd", side_effect=flaky_run
        ):
            code, payload = self._run(["--channel-base-url", str(channel), "--offline", "--json"])
        self.assertEqual(code, 1)
        self.assertEqual(payload["status"], "partial_error")
        self.assertEqual(payload["configured_hosts"], ["codex"])
        self.assertIn("cc", payload["failed_hosts"])
        self.assertTrue(payload["receipt_unconfirmed"])
        self.assertEqual(payload["receipt_warning"]["codex"], "local_bind_warn")

    def test_harness_015_provisions_engine_and_nine_domains_and_fails_closed(self) -> None:
        domains = (
            "vllm-ascend", "operators", "xllm", "mindie-sd", "infer-core",
            "infer-distributed", "infer-observability", "infer-ops-compat", "agent-engineering",
        )
        paths_src = (
            "from dataclasses import dataclass\n"
            "from pathlib import Path\n\n"
            "@dataclass(frozen=True)\n"
            "class ProfileRef:\n"
            "    host: str\n"
            "    config_path: Path\n"
            "    @classmethod\n"
            "    def resolve(cls, host: str, *, config_path=None, **_kw):\n"
            "        return cls(host=host, config_path=Path(config_path))\n"
        )
        kb_src = (
            "import json, os\n"
            f"DOMAINS = {domains!r}\n\n"
            "def ensure_knowledge_binding(profile, **_kw):\n"
            "    mode = os.environ.get('MINDIE_TEST_BINDING_MODE', 'configured')\n"
            "    if mode == 'raise':\n"
            "        raise RuntimeError('simulated knowledge binding failure')\n"
            "    if mode == 'deferred':\n"
            "        return {'status': 'deferred', 'reason': 'lock_timeout', 'reportable': False}\n"
            "    if mode == 'skipped':\n"
            "        return {'status': 'skipped', 'reason': 'knowledge_not_installed'}\n"
            "    eng_dir = profile.config_path.parent / 'engines' / profile.host / ('a' * 20)\n"
            "    eng_dir.mkdir(parents=True, exist_ok=True)\n"
            "    domain_cfgs = {}\n"
            "    for dom in DOMAINS:\n"
            "        p = eng_dir / f'{dom}.engine.json'\n"
            "        p.write_text(json.dumps({'domain': dom}), encoding='utf-8')\n"
            "        domain_cfgs[dom] = str(p)\n"
            "    doc = json.loads(profile.config_path.read_text(encoding='utf-8'))\n"
            "    doc['engine_config'] = domain_cfgs['vllm-ascend']\n"
            "    doc['domain_configs'] = domain_cfgs\n"
            "    profile.config_path.write_text(json.dumps(doc), encoding='utf-8')\n"
            "    return {'status': 'configured', 'engine_config': doc['engine_config'], 'domain_configs': domain_cfgs}\n"
        )
        channel = self.root / "channel-015"
        channel.mkdir(parents=True, exist_ok=True)
        self._write(channel / "release-channel.json", json.dumps({"current_patch_version": "0.1.18"}))
        wheel = channel / "mindie_harness-0.1.5-py3-none-any.whl"
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr("mindie_harness/__init__.py", "__version__ = '0.1.5'\n")
            archive.writestr("mindie_harness/paths.py", paths_src)
            archive.writestr("mindie_harness/runtime/__init__.py", RUNTIME_SOURCE.replace("0.1.0", "0.1.5"))
            archive.writestr("mindie_harness/runtime/knowledge_binding.py", kb_src)
            archive.writestr("mindie_harness/cli.py", CLI_SOURCE)
            archive.writestr("mindie_harness-0.1.5.dist-info/METADATA", "Metadata-Version: 2.1\nName: mindie-harness\nVersion: 0.1.5\n")
            archive.writestr("mindie_harness-0.1.5.dist-info/WHEEL", "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
            archive.writestr("mindie_harness-0.1.5.dist-info/RECORD", "")
        with tarfile.open(channel / "mindie-wheels-bundle.tar.gz", "w:gz") as bundle:
            bundle.add(wheel, arcname=wheel.name)
            req = b"mindie-harness==0.1.5\n"
            info = tarfile.TarInfo("requirements.lock")
            info.size = len(req)
            bundle.addfile(info, io.BytesIO(req))
        r_sum = hashlib.sha256((channel / "release-channel.json").read_bytes()).hexdigest()
        b_sum = hashlib.sha256((channel / "mindie-wheels-bundle.tar.gz").read_bytes()).hexdigest()
        self._write(channel / "SHA256SUMS", f"{r_sum}  release-channel.json\n{b_sum}  mindie-wheels-bundle.tar.gz\n")

        code, payload = self._run(["--host", "codex", "--channel-base-url", str(channel), "--offline", "--json"])
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["configured_hosts"], ["codex"])
        cfg_doc = json.loads((self.cfg / "codex.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg_doc["channel_base_url"], str(channel))
        self.assertTrue(Path(cfg_doc["engine_config"]).is_file())
        self.assertEqual(set(cfg_doc["domain_configs"]), set(domains))

        with patch.dict(os.environ, {"MINDIE_TEST_BINDING_MODE": "raise"}):
            fail_code, fail_payload = self._run(["--host", "cc", "--channel-base-url", str(channel), "--offline", "--json"])
        self.assertEqual((fail_code, fail_payload["status"], fail_payload["configured_hosts"]), (1, "error", []))
        self.assertEqual(fail_payload["failed_hosts"]["cc"]["reason"], "knowledge_binding_failed")

        with patch.dict(os.environ, {"MINDIE_TEST_BINDING_MODE": "deferred"}):
            def_code, def_payload = self._run(["--host", "kimi", "--channel-base-url", str(channel), "--offline", "--json"])
        self.assertEqual((def_code, def_payload["configured_hosts"], def_payload["failed_hosts"]["kimi"]["reason"]), (1, [], "lock_timeout"))

        with patch.dict(os.environ, {"MINDIE_TEST_BINDING_MODE": "skipped"}):
            sk_code, sk_payload = self._run(["--host", "dsh", "--channel-base-url", str(channel), "--offline", "--json"])
        self.assertEqual((sk_code, sk_payload["configured_hosts"], sk_payload["failed_hosts"]["dsh"]["reason"]), (1, [], "knowledge_not_installed"))

        with patch.dict(os.environ, {"MINDIE_TEST_OMIT_PYTHON": "1"}):
            np_code, np_payload = self._run(["--host", "agy", "--channel-base-url", str(channel), "--offline", "--json"])
        self.assertEqual((np_code, np_payload["configured_hosts"], np_payload["failed_hosts"]["agy"]["reason"]), (1, [], "runtime_python_missing"))


if __name__ == "__main__":
    unittest.main()

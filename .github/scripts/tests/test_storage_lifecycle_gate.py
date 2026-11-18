"""Unit contracts for R4/P8 storage lifecycle, silent legacy reclamation, and zero temp leak gate.

[Role]
Verifies `storage_lifecycle_gate.py` and `storage_temp_ast.py` static AST checks across
per-allocation `mkstemp`/`mkdtemp`/`NamedTemporaryFile(delete=False)` ownership, scope-aware
POSIX guards on `os.kill(pid, 0)` (including local `import os`, decorators, `If.test`, and `match`),
unshadowed/unreassigned `storage_gc` calls, historical floor tolerance, and test sandbox mutations.

[Invariants]
- Isolates `HOME`, `USERPROFILE`, `APPDATA`, `MINDIE_CONFIG_HOME`, `MINDIE_DATA_HOME`, and
  `MINDIE_DIAGNOSTICS_ROOT` inside per-test temporary directories (zero host pollution).
- Pure Tier 0 in-memory/tempdir unit tests (`< 5s`) with zero external subprocesses or network calls.

[Timeouts & Locks]
- Pure synchronous AST tests; acquires no locks.

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

import storage_lifecycle_gate as sl_gate  # noqa: E402


class StorageLifecycleGateTests(unittest.TestCase):
    """Covers P8 per-allocation temp ownership, Windows PID AST guards, GC calls, and floor scoping."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="mindie-sl-gate-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
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
        patcher = patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _write(self, path: Path, content: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        return path

    def _make_plugin_repo(self, name: str = "mindie-agent-cc", version: str = "0.1.25") -> Path:
        repo = self.root / name
        (repo / ".git").mkdir(parents=True, exist_ok=True)
        self._write(
            repo / ".claude-plugin/plugin.json",
            json.dumps({"name": "mindie-agent", "version": version}),
        )
        self._write(
            repo / "scripts/storage_lifecycle.py",
            (
                "import os\n"
                "def runtime_leases(): return None\n"
                "def maintenance_tick(): return None\n"
                "def post_switch(): return None\n"
                "def pre_build_reclaim():\n"
                "    if os.name != 'nt':\n"
                "        os.kill(12345, 0)\n"
                "    return {'reclaimed': 0}\n"
            ),
        )
        self._write(
            repo / "scripts/release_update.py",
            "from storage_lifecycle import maintenance_tick\n\ndef tick():\n    return maintenance_tick()\n",
        )
        self._write(
            repo / "tests/conftest.py",
            (
                "def _sandbox(tmp_path, monkeypatch):\n"
                "    directories = {\n"
                "        'HOME': tmp_path / 'h',\n"
                "        'MINDIE_CONFIG_HOME': tmp_path / 'c',\n"
                "        'MINDIE_DATA_HOME': tmp_path / 'd',\n"
                "        'MINDIE_DIAGNOSTICS_ROOT': tmp_path / 'diag',\n"
                "    }\n"
                "    for key, val in directories.items():\n"
                "        monkeypatch.setenv(key, str(val))\n"
            ),
        )
        return repo

    def test_valid_plugin_checkout_with_fixture_local_dict_passes_all_p8_checks(self) -> None:
        self._make_plugin_repo()
        self.assertEqual(sl_gate.verify_storage_lifecycle_hygiene([self.root]), [])

    def test_historical_pre_floor_checkout_skipped_unless_explicitly_required(self) -> None:
        repo = self._make_plugin_repo(version="0.1.17")
        (repo / "scripts/storage_lifecycle.py").unlink()
        self.assertEqual(sl_gate.verify_storage_lifecycle_hygiene([self.root]), [])
        errors = sl_gate.verify_storage_lifecycle_hygiene([self.root], required_repos=["mindie-agent-cc"])
        self.assertTrue(any("< P8 floor 0.1.25" in err for err in errors), errors)

    def test_per_allocation_ownership_rejects_all_bypass_shapes(self) -> None:
        repo = self._make_plugin_repo()
        self._write(
            repo / "scripts/leaker.py",
            (
                "import atexit, shutil, tempfile\n"
                "from pathlib import Path\n"
                "from tempfile import mkdtemp as allocate\n"
                "class BadClass:\n"
                "    leaked = tempfile.mkdtemp()\n"
                "def str_replace_not_cleanup():\n"
                "    d = allocate(prefix='bad-')\n"
                "    return d.replace('a', 'b')\n"
                "def same_line_overwrite():\n"
                "    d = tempfile.mkdtemp(); d = tempfile.mkdtemp(); shutil.rmtree(d)\n"
                "def walrus_overwrite():\n"
                "    d = tempfile.mkdtemp()\n"
                "    if (d := tempfile.mkdtemp()):\n"
                "        shutil.rmtree(d)\n"
                "def path_basename_not_whole():\n"
                "    d = Path(tempfile.mkdtemp())\n"
                "    shutil.rmtree(d.name, ignore_errors=True)\n"
                "def uninvoked_lambda():\n"
                "    d = tempfile.mkdtemp()\n"
                "    cleanup = lambda: shutil.rmtree(d)\n"
                "    return bool(cleanup)\n"
                "def atexit_non_cleaner():\n"
                "    d = tempfile.mkdtemp()\n"
                "    atexit.register(print, d)\n"
                "def inline_scalar_return():\n"
                "    return bool(tempfile.mkdtemp())\n"
            ),
        )
        errors = sl_gate.verify_storage_lifecycle_hygiene([self.root])
        for expected in (
            "class `BadClass` body",
            "str_replace_not_cleanup",
            "same_line_overwrite",
            "walrus_overwrite",
            "path_basename_not_whole",
            "uninvoked_lambda",
            "atexit_non_cleaner",
            "inline_scalar_return",
        ):
            self.assertTrue(any(expected in e for e in errors), (expected, errors))

    def test_owned_atomic_replace_ntf_name_atexit_rmtree_and_allocator_pass(self) -> None:
        mod = self._write(
            self.root / "owned.py",
            (
                "import atexit, os, shutil, tempfile\n"
                "def alloc_dir():\n"
                "    return tempfile.mkdtemp(prefix='ok-')\n"
                "def cleanup_dir(p):\n"
                "    shutil.rmtree(p, ignore_errors=True)\n"
                "def atexit_owned():\n"
                "    d = tempfile.mkdtemp()\n"
                "    atexit.register(shutil.rmtree, d)\n"
                "def ntf_owned(dst):\n"
                "    f = tempfile.NamedTemporaryFile(delete=False)\n"
                "    f.close()\n"
                "    os.replace(f.name, dst)\n"
            ),
        )
        self.assertEqual(sl_gate.inspect_python_temp_hygiene(mod), [])

    def test_windows_pid_guard_rejects_local_import_decorator_match_if_test_and_inverted(self) -> None:
        repo = self._make_plugin_repo()
        self._write(
            repo / "scripts/storage_leases.py",
            (
                "import os\n"
                "from os import kill as raw_kill\n"
                "POSIX = os.name != 'nt'\n"
                "def dec(x):\n"
                "    return lambda f: f\n"
                "@dec(os.kill(1, 0))\n"
                "def decorated():\n"
                "    return None\n"
                "def local_import(pid: int):\n"
                "    import os\n"
                "    os.kill(pid, 0)\n"
                "def match_bypass(event, pid: int):\n"
                "    match event:\n"
                "        case {'enabled': POSIX} if POSIX:\n"
                "            os.kill(pid, 0)\n"
                "def in_if_test(pid: int):\n"
                "    if os.kill(pid, 0) is None:\n"
                "        return True\n"
                "def direct_imported(pid: int):\n"
                "    raw_kill(pid, 0)\n"
                "def early_return_posix_safe(pid: int):\n"
                "    if os.name == 'nt':\n"
                "        return False\n"
                "    os.kill(pid, 0)\n"
                "    return True\n"
            ),
        )
        errors = sl_gate.verify_storage_lifecycle_hygiene([self.root])
        for expected in ("<module>", "local_import", "match_bypass", "in_if_test", "direct_imported"):
            self.assertTrue(any(expected in e for e in errors), (expected, errors))
        self.assertFalse(any("early_return_posix_safe" in e for e in errors), errors)

    def test_reassigned_gc_import_fake_loader_and_env_subscript_read_or_dict_update_fail(self) -> None:
        repo = self._make_plugin_repo()
        self._write(
            repo / "scripts/release_update.py",
            (
                "import importlib\n"
                "from storage_lifecycle import maintenance_tick\n"
                "maintenance_tick = lambda: None\n"
                "def factory(name):\n"
                "    importlib.import_module('json')\n"
                "    return object()\n"
                "def tick():\n"
                "    factory('storage_lifecycle').maintenance_tick()\n"
                "    return maintenance_tick()\n"
            ),
        )
        self._write(
            repo / "tests/conftest.py",
            (
                "import os\n"
                "KEYS = ('HOME', 'MINDIE_CONFIG_HOME', 'MINDIE_DATA_HOME', 'MINDIE_DIAGNOSTICS_ROOT')\n"
                "def test_reads_and_plain_dict(os):\n"
                "    plain = {}\n"
                "    plain.update({k: 'x' for k in KEYS})\n"
                "    os.environ['HOME'] = 'shadowed'\n"
                "    os.environ['MINDIE_CONFIG_HOME'] = 'shadowed'\n"
                "    os.environ['MINDIE_DATA_HOME'] = 'shadowed'\n"
                "    for k in KEYS:\n"
                "        _ = os.environ[k]\n"
            ),
        )
        errors = sl_gate.verify_storage_lifecycle_hygiene([self.root])
        self.assertTrue(any("does not invoke P8 storage lifecycle GC" in e for e in errors), errors)
        self.assertTrue(any("missing AST-verified host sandbox isolation" in e for e in errors), errors)

    def test_tuple_pair_monkeypatch_and_demorgan_windows_pid_guards(self) -> None:
        repo = self._make_plugin_repo()
        self._write(
            repo / "tests/conftest.py",
            (
                "def isolate(monkeypatch, tmp_path):\n"
                "    for key, val in (\n"
                "        ('HOME', tmp_path),\n"
                "        ('MINDIE_CONFIG_HOME', tmp_path / 'cfg'),\n"
                "        ('MINDIE_DATA_HOME', tmp_path / 'data'),\n"
                "    ):\n"
                "        monkeypatch.setenv(key, str(val))\n"
            ),
        )
        self.assertEqual(sl_gate.verify_storage_lifecycle_hygiene([self.root]), [])

        self._write(
            repo / "scripts/storage_demorgan.py",
            (
                "import os\n"
                "def bad_and(pid: int, flag: bool) -> bool:\n"
                "    if os.name == 'nt' and flag:\n"
                "        return False\n"
                "    os.kill(pid, sig=0)\n"
                "    return True\n"
                "def try_import_bypass(pid: int) -> bool:\n"
                "    try:\n"
                "        import os as local_os\n"
                "    except ImportError:\n"
                "        return False\n"
                "    local_os.kill(pid, 0)\n"
                "    return True\n"
                "def comp_guard_spoof(pid: int, platforms: list[object]) -> list[object]:\n"
                "    import sys\n"
                "    return [os.kill(pid, 0) if sys.platform != 'win32' else None for sys in platforms]\n"
                "def comp_lambda_spoof(pid: int, platforms: list[object]) -> list[object]:\n"
                "    import sys\n"
                "    return [(lambda: os.kill(pid, 0) if sys.platform != 'win32' else None)() for sys in platforms]\n"
                "def comp_real_os_shadow(pid: int) -> list[object]:\n"
                "    return [os.kill(pid, 0) for os in [os]]\n"
                "def match_import_spoof(pid: int, event: int, platform: object) -> None:\n"
                "    match event:\n"
                "        case 1:\n"
                "            import sys as platform\n"
                "    if platform.platform != 'win32':\n"
                "        os.kill(pid, 0)\n"
                "def except_mid_import(pid: int, fail: object) -> None:\n"
                "    try:\n"
                "        import os as api\n"
                "        fail()\n"
                "        api = None\n"
                "    except ValueError:\n"
                "        api.kill(pid, 0)\n"
                "def loop_backedge_import(pid: int) -> None:\n"
                "    for idx in range(2):\n"
                "        if idx:\n"
                "            api2.kill(pid, 0)\n"
                "        import os as api2\n"
                "def comp_renamed_iter(pid: int) -> list[object]:\n"
                "    return [elem.kill(pid, 0) for elem in [os]]\n"
                "def handler_nested_fn(pid: int) -> None:\n"
                "    try:\n"
                "        raise ValueError()\n"
                "    except ValueError:\n"
                "        def inner_probe(p: int) -> None:\n"
                "            import os as h_api\n"
                "            h_api.kill(p, 0)\n"
                "        inner_probe(pid)\n"
                "def default_walrus_spoof(pid: int, fake: object) -> None:\n"
                "    import sys as s_def\n"
                "    _ = lambda x=(s_def := fake): None\n"
                "    if s_def.platform != 'win32':\n"
                "        os.kill(pid, 0)\n"
                "def long_chain_kill(pid: int) -> None:\n"
                "    k0 = os.kill\n"
                "    k1 = k0\n"
                "    k2 = k1\n"
                "    k3 = k2\n"
                "    k4 = k3\n"
                "    k4(pid, 0)\n"
                "def nonlocal_spoof(pid: int, fake: object) -> None:\n"
                "    import sys as s_nl\n"
                "    def rebind() -> None:\n"
                "        nonlocal s_nl\n"
                "        s_nl = fake\n"
                "    rebind()\n"
                "    if s_nl.platform != 'win32':\n"
                "        os.kill(pid, 0)\n"
                "def startswith_offset_spoof(pid: int) -> None:\n"
                "    import sys as s_sw\n"
                "    if not s_sw.platform.startswith('win', 1):\n"
                "        os.kill(pid, 0)\n"
                "def comp_target_call(pid: int, slots: list[object]) -> list[object]:\n"
                "    return [None for slots[os.kill(pid, 0)] in [1] if os.name != 'nt']\n"
                "def identity_op_spoof(pid: int) -> None:\n"
                "    import sys as s_id\n"
                "    if s_id.platform is not 'win32':\n"
                "        os.kill(pid, 0)\n"
                "def bool_false_signal(pid: int) -> None:\n"
                "    os.kill(pid, False)\n"
            ),
        )
        errors = sl_gate.verify_storage_lifecycle_hygiene([self.root])
        for expected in (
            "bad_and",
            "try_import_bypass",
            "comp_guard_spoof",
            "comp_lambda_spoof",
            "comp_real_os_shadow",
            "match_import_spoof",
            "except_mid_import",
            "loop_backedge_import",
            "comp_renamed_iter",
            "inner_probe",
            "default_walrus_spoof",
            "first-class/aliased `.kill`",
            "nonlocal_spoof",
            "startswith_offset_spoof",
            "comp_target_call",
            "identity_op_spoof",
            "bool_false_signal",
        ):
            self.assertTrue(any(expected in e for e in errors), (expected, errors))

        for snippet, marker in (
            ("import os\ndef f(pid, check=os.kill):\n    check(pid, 0)\n", "first-class/aliased `.kill`"),
            ("import os\nimport sys as p_api\nfrom shim import *\nif p_api.platform != 'win32':\n    os.kill(1, 0)\n", "unguarded `os.kill(pid, 0)`"),
            ("import os\ngetattr(os, 'kill')(1, 0)\n", "first-class/aliased `.kill`"),
            ("from os import kill as probe\nprobe(1, 0)\n", "unguarded `os.kill(pid, 0)`"),
            ("class Backend:\n    from os import kill as probe\nBackend.probe(1, 0)\n", "unguarded `os.kill(pid, 0)`"),
        ):
            self._write(repo / "scripts/storage_cap.py", snippet)
            cap_errs = sl_gate.verify_storage_lifecycle_hygiene([self.root])
            self.assertTrue(any(marker in e for e in cap_errs), (marker, cap_errs))

        (repo / "scripts/storage_demorgan.py").unlink()
        # AD-08: Normal Python idioms (`match ClassName(...)`, private names `_TRASH_PREFIX`, `_h`, `self._descriptor`)
        # are allowed when no real Windows PID, temp-leak, or control-plane boundary is violated.
        self._write(
            repo / "scripts/storage_cap.py",
            (
                "import re\n"
                "from dataclasses import dataclass\n"
                "_TRASH_PREFIX = '.retiring-'\n"
                "PAT = re.compile(r'^[0-9]+$')\n"
                "@dataclass\n"
                "class Event:\n"
                "    kind: str\n"
                "class Holder:\n"
                "    def __init__(self) -> None:\n"
                "        self._descriptor = 'ok'\n"
                "    def _h(self, ev: Event) -> str:\n"
                "        match ev:\n"
                "            case Event(kind=k):\n"
                "                return f'{_TRASH_PREFIX}{k}:{self._descriptor}'\n"
                "        return ''\n"
            ),
        )
        self.assertEqual(sl_gate.verify_storage_lifecycle_hygiene([self.root]), [])

        # Control-plane top-level `import torch_npu` is caught across harness/coordinator/host plugins
        harness_repo = self.root / "harness"
        (harness_repo / ".git").mkdir(parents=True, exist_ok=True)
        self._write(harness_repo / "pyproject.toml", '[project]\nname = "mindie-harness"\nversion = "0.1.0"\n')
        self._write(
            harness_repo / "mindie_harness/storage.py",
            (
                "def runtime_leases(): return None\n"
                "def maintenance_tick(): return None\n"
                "def post_switch(): return None\n"
                "def pre_build_reclaim(): return {'reclaimed': 0}\n"
            ),
        )
        self._write(
            harness_repo / "tests/conftest.py",
            "def f(monkeypatch, tmp_path):\n"
            "    monkeypatch.setenv('HOME', str(tmp_path))\n"
            "    monkeypatch.setenv('MINDIE_CONFIG_HOME', str(tmp_path))\n"
            "    monkeypatch.setenv('MINDIE_DATA_HOME', str(tmp_path))\n",
        )
        self.assertEqual(sl_gate.verify_storage_lifecycle_hygiene([self.root]), [])
        self._write(harness_repo / "mindie_harness/bad_npu.py", "import torch_npu\n")
        npu_errs = sl_gate.verify_storage_lifecycle_hygiene([self.root])
        self.assertTrue(any("harness: mindie_harness/bad_npu.py" in e and "torch_npu" in e for e in npu_errs), npu_errs)
        (harness_repo / "mindie_harness/bad_npu.py").unlink()
        self.assertEqual(sl_gate.verify_storage_lifecycle_hygiene([self.root]), [])

        # `sys.modules.get(...)`, `setattr(sys, 'stdin', ...)`, `subprocess.Popen.kill`, and nonzero termination
        # signals (`signal.SIGTERM`, `-child.returncode`) must NOT trigger `os.kill(pid, 0)` false positives.
        self._write(
            harness_repo / "mindie_harness/termination_and_modules.py",
            (
                "import os\n"
                "import signal\n"
                "import sys\n"
                "def terminate_proc(process, stream, force: bool, pid: int, rc: int) -> None:\n"
                "    _ = sys.modules.get('mindie_harness')\n"
                "    setattr(sys, 'stdin', stream)\n"
                "    method = process.kill if force else process.terminate\n"
                "    method()\n"
                "    os.kill(pid, signal.SIGTERM)\n"
                "    if rc < 0:\n"
                "        os.kill(os.getpid(), -rc)\n"
                "    if os.name != 'nt':\n"
                "        os.kill(pid, 0)\n"
            ),
        )
        self.assertEqual(sl_gate.verify_storage_lifecycle_hygiene([self.root]), [])

    def _make_thin_repo(self, name: str, version: str, manifest_rel: str, scope: str, py_lines: int, js_files: dict[str, int] | None = None) -> Path:
        repo = self.root / name
        (repo / ".git").mkdir(parents=True, exist_ok=True)
        self._write(repo / manifest_rel, json.dumps({"name": "mindie-agent", "version": version}))
        lines = ["from mindie_harness import storage"]
        lines.extend("VALUE = 1" for _ in range(max(0, py_lines - 1)))
        self._write(repo / scope / "host_adapter.py", "\n".join(lines[:py_lines]) + "\n")
        for rel, count in (js_files or {}).items():
            self._write(repo / rel, "\n".join("const value = 1;" for _ in range(count)) + "\n")
        return repo

    def test_main_repo_install_py_inspection_catches_temp_leak_and_os_kill(self) -> None:
        main = self.root / "fake-main"
        (main / ".github/scripts").mkdir(parents=True)
        self._write(main / "install.py", "import tempfile\ndef leak():\n    return tempfile.mkdtemp()\n")
        errors = sl_gate.verify_storage_lifecycle_hygiene([], main_repo=main)
        self.assertTrue(any("mindie-agent: install.py" in e and "mkdtemp" in e for e in errors), errors)
        self._write(main / "install.py", "import os\ndef probe(pid):\n    return os.kill(pid, 0)\n")
        errors = sl_gate.verify_storage_lifecycle_hygiene([], main_repo=main)
        self.assertTrue(any("mindie-agent: install.py" in e and "os.kill" in e for e in errors), errors)
        self._write(main / "install.py", "import tempfile\ndef ok():\n    with tempfile.TemporaryDirectory() as tmp:\n        return tmp\n")
        self.assertEqual(sl_gate.verify_storage_lifecycle_hygiene([], main_repo=main), [])

    def test_thin_host_loc_gate_skips_versions_below_floor(self) -> None:
        self._make_thin_repo("mindie-agent-codex", "0.1.37", "plugins/mindie-agent/.codex-plugin/plugin.json", "plugins/mindie-agent/scripts", 1500)
        self._make_thin_repo("mindie-agent-dsh", "0.1.25", "package.json", "scripts", 1500)
        self.assertEqual(sl_gate.verify_storage_lifecycle_hygiene([self.root]), [])

    def test_thin_host_loc_gate_accepts_exact_boundary_and_deduplicates_paths(self) -> None:
        codex = self._make_thin_repo(
            "mindie-agent-codex", "0.1.38", "plugins/mindie-agent/.codex-plugin/plugin.json", "plugins/mindie-agent/scripts", 600,
            {"plugins/mindie-agent/scripts/entry.mjs": 600},
        )
        self._make_thin_repo("mindie-agent-dsh", "0.1.26", "package.json", "scripts", 600, {"host3.mjs": 600})
        self._make_thin_repo(
            "mindie-agent-oc", "0.1.11", "package.json", "plugins/mindie-agent/scripts", 600,
            {"plugins/mindie-agent/opencode_host.mjs": 600},
        )
        self.assertEqual(sl_gate.verify_storage_lifecycle_hygiene([self.root]), [])
        self.assertEqual(len(sl_gate._iter_plugin_production_code_files(codex, ("plugins/mindie-agent/scripts",))), 2)

    def test_thin_host_loc_gate_rejects_1201_lines_across_py_and_js(self) -> None:
        self._make_thin_repo(
            "mindie-agent-codex", "0.1.38", "plugins/mindie-agent/.codex-plugin/plugin.json", "plugins/mindie-agent/scripts", 600,
            {"host3.mjs": 601},
        )
        errors = sl_gate.verify_storage_lifecycle_hygiene([self.root])
        self.assertTrue(any("mindie-agent-codex" in e and "1201" in e and "> 1200 line budget" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()

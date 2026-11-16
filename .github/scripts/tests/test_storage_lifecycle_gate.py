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
                "MINDIE_CONFIG_HOME",
                "MINDIE_DATA_HOME",
                "MINDIE_DIAGNOSTICS_ROOT",
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
            ),
        )
        errors = sl_gate.verify_storage_lifecycle_hygiene([self.root])
        self.assertTrue(any("bad_and" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()

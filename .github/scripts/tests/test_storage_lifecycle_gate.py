"""Unit contracts for R4/P8 storage lifecycle, silent legacy reclamation, and zero temp leak gate.

[Role]
Verifies `storage_lifecycle_gate.py` and `storage_temp_ast.py` static AST checks across
per-allocation `mkstemp`/`mkdtemp`/`NamedTemporaryFile(delete=False)` ownership, scope-aware
POSIX guards on `os.kill(pid, 0)` (including `If.test` and shadowed bindings), bound `storage_gc`
calls and top-level exports, historical floor tolerance, and AST-verified test sandbox redirection.

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
                "    monkeypatch.setenv('HOME', str(tmp_path / 'h'))\n"
                "    monkeypatch.setenv('MINDIE_CONFIG_HOME', str(tmp_path / 'c'))\n"
                "    monkeypatch.setenv('MINDIE_DATA_HOME', str(tmp_path / 'd'))\n"
                "    monkeypatch.setenv('MINDIE_DIAGNOSTICS_ROOT', str(tmp_path / 'diag'))\n"
            ),
        )
        return repo

    def test_valid_plugin_checkout_passes_all_p8_checks(self) -> None:
        self._make_plugin_repo()
        self.assertEqual(sl_gate.verify_storage_lifecycle_hygiene([self.root]), [])

    def test_historical_pre_floor_checkout_skipped_unless_explicitly_required(self) -> None:
        repo = self._make_plugin_repo(version="0.1.17")
        (repo / "scripts/storage_lifecycle.py").unlink()
        self.assertEqual(sl_gate.verify_storage_lifecycle_hygiene([self.root]), [])
        errors = sl_gate.verify_storage_lifecycle_hygiene([self.root], required_repos=["mindie-agent-cc"])
        self.assertTrue(any("< P8 floor 0.1.25" in err for err in errors), errors)

    def test_per_allocation_ownership_rejects_overwrite_subpath_print_helper_and_bool_return(self) -> None:
        repo = self._make_plugin_repo()
        self._write(
            repo / "scripts/leaker.py",
            (
                "from pathlib import Path\n"
                "from tempfile import mkdtemp as allocate\n"
                "import shutil, tempfile\n"
                "class BadClass:\n"
                "    leaked = tempfile.mkdtemp()\n"
                "def str_replace_not_cleanup():\n"
                "    d = allocate(prefix='bad-')\n"
                "    return d.replace('a', 'b')\n"
                "def overwritten_same_var():\n"
                "    d = tempfile.mkdtemp()\n"
                "    d = tempfile.mkdtemp()\n"
                "    shutil.rmtree(d)\n"
                "def child_only_cleaned():\n"
                "    d = tempfile.mkdtemp()\n"
                "    shutil.rmtree(Path(d) / 'child')\n"
                "def passed_not_called():\n"
                "    d = tempfile.mkdtemp()\n"
                "    def cleanup():\n"
                "        shutil.rmtree(d)\n"
                "    print(cleanup)\n"
                "    return True\n"
                "def bool_return_not_transfer():\n"
                "    d = tempfile.mkdtemp()\n"
                "    return bool(d)\n"
            ),
        )
        errors = sl_gate.verify_storage_lifecycle_hygiene([self.root])
        for expected in (
            "class `BadClass` body",
            "str_replace_not_cleanup",
            "overwritten_same_var",
            "child_only_cleaned",
            "passed_not_called",
            "bool_return_not_transfer",
        ):
            self.assertTrue(any(expected in e for e in errors), (expected, errors))

    def test_owned_atomic_replace_and_allocator_module_cleanup_pass(self) -> None:
        mod = self._write(
            self.root / "owned.py",
            (
                "import os, shutil, tempfile\n"
                "def alloc_dir():\n"
                "    d = tempfile.mkdtemp(prefix='ok-')\n"
                "    return d\n"
                "def cleanup_dir(p):\n"
                "    shutil.rmtree(p, ignore_errors=True)\n"
                "def atomic_write(dst):\n"
                "    fd, tmp = tempfile.mkstemp()\n"
                "    os.close(fd)\n"
                "    os.replace(tmp, dst)\n"
            ),
        )
        self.assertEqual(sl_gate.inspect_python_temp_hygiene(mod), [])

    def test_windows_pid_guard_rejects_if_test_shadowed_inverted_and_imported_kill_zero(self) -> None:
        repo = self._make_plugin_repo()
        self._write(
            repo / "scripts/storage_leases.py",
            (
                "import os\n"
                "from os import kill as raw_kill\n"
                "POSIX = os.name != 'nt'\n"
                "def in_if_test(pid: int):\n"
                "    if os.kill(pid, 0) is None:\n"
                "        return True\n"
                "def shadowed_param(pid: int, POSIX: bool = True):\n"
                "    if POSIX:\n"
                "        os.kill(pid, 0)\n"
                "def inverted_branch(pid: int):\n"
                "    if os.name == 'nt':\n"
                "        os.kill(pid, 0)\n"
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
        for expected in ("in_if_test", "shadowed_param", "inverted_branch", "direct_imported"):
            self.assertTrue(any(expected in e for e in errors), (expected, errors))
        self.assertFalse(any("early_return_posix_safe" in e for e in errors), errors)

    def test_unbound_factory_shadowed_gc_nested_exports_and_env_read_only_sandbox_fail(self) -> None:
        repo = self._make_plugin_repo()
        self._write(
            repo / "scripts/storage_lifecycle.py",
            (
                "class Hidden:\n"
                "    def runtime_leases(self): pass\n"
                "    def maintenance_tick(self): pass\n"
                "    def post_switch(self): pass\n"
                "    def pre_build_reclaim(self): pass\n"
            ),
        )
        self._write(
            repo / "scripts/release_update.py",
            (
                "from storage_lifecycle import maintenance_tick\n"
                "def factory(name): return None\n"
                "def tick(maintenance_tick=lambda: None):\n"
                "    factory('storage_lifecycle').status()\n"
                "    return maintenance_tick()\n"
            ),
        )
        self._write(
            repo / "tests/conftest.py",
            (
                "import os\n"
                "def test_reads_only(tmp_path):\n"
                "    assert os.environ.get('HOME')\n"
                "    assert os.environ.get('MINDIE_CONFIG_HOME')\n"
            ),
        )
        errors = sl_gate.verify_storage_lifecycle_hygiene([self.root])
        self.assertTrue(any("missing top-level export(s)" in e for e in errors), errors)
        self.assertTrue(any("does not invoke P8 storage lifecycle GC" in e for e in errors), errors)
        self.assertTrue(any("missing AST-verified host sandbox isolation" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()

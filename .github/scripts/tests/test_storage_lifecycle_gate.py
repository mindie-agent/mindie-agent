"""Unit contracts for R4/P8 storage lifecycle, silent legacy reclamation, and zero temp leak gate.

[Role]
Verifies `storage_lifecycle_gate.py` static AST checks across per-allocation `mkstemp`/`mkdtemp`/
`NamedTemporaryFile(delete=False)` ownership, AST-proven POSIX guards on `os.kill(pid, 0)` across
all `storage*` submodules, bound `storage_gc` calls and top-level exports, historical channel floor
tolerance, and AST-verified test sandbox isolation.

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

    def test_per_allocation_ownership_rejects_str_replace_uncalled_nested_partial_and_return_true(self) -> None:
        repo = self._make_plugin_repo()
        self._write(
            repo / "scripts/leaker.py",
            (
                "from tempfile import mkdtemp as allocate, NamedTemporaryFile\n"
                "import shutil, tempfile\n"
                "class BadClass:\n"
                "    leaked = tempfile.mkdtemp()\n"
                "def str_replace_not_cleanup():\n"
                "    d = allocate(prefix='bad-')\n"
                "    return d.replace('a', 'b')\n"
                "def uncalled_nested():\n"
                "    d = tempfile.mkdtemp()\n"
                "    def _never_called():\n"
                "        shutil.rmtree(d)\n"
                "    return True\n"
                "def two_allocs_one_cleaned():\n"
                "    d1 = tempfile.mkdtemp()\n"
                "    d2 = tempfile.mkdtemp()\n"
                "    shutil.rmtree(d1)\n"
                "    return True\n"
            ),
        )
        errors = sl_gate.verify_storage_lifecycle_hygiene([self.root])
        self.assertTrue(any("class `BadClass` body" in e for e in errors), errors)
        self.assertTrue(any("str_replace_not_cleanup" in e for e in errors), errors)
        self.assertTrue(any("uncalled_nested" in e for e in errors), errors)
        self.assertTrue(any("two_allocs_one_cleaned" in e for e in errors), errors)

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

    def test_windows_pid_guard_rejects_inverted_comment_imported_and_submodule_kill_zero(self) -> None:
        repo = self._make_plugin_repo()
        self._write(
            repo / "scripts/storage_leases.py",
            (
                "import os\n"
                "from os import kill as raw_kill\n"
                "def inverted_branch(pid: int):\n"
                "    # if os.name != 'nt':\n"
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
        self.assertTrue(any("inverted_branch" in e for e in errors), errors)
        self.assertTrue(any("direct_imported" in e for e in errors), errors)
        self.assertFalse(any("early_return_posix_safe" in e for e in errors), errors)

    def test_unused_gc_import_nested_exports_and_comment_only_sandbox_fail(self) -> None:
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
            "from storage_lifecycle import maintenance_tick\n\ndef tick():\n    return None\n",
        )
        self._write(
            repo / "tests/conftest.py",
            "# TODO: migrate tests to tmp_path and MINDIE_DIAGNOSTICS_ROOT\n",
        )
        errors = sl_gate.verify_storage_lifecycle_hygiene([self.root])
        self.assertTrue(any("missing top-level export(s)" in e for e in errors), errors)
        self.assertTrue(any("does not invoke P8 storage lifecycle GC" in e for e in errors), errors)
        self.assertTrue(any("missing AST-verified host sandbox isolation" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()

"""Unit contracts for R4/P8 storage lifecycle, silent legacy reclamation, and zero temp leak gate.

[Role]
Verifies `storage_lifecycle_gate.py` static AST checks across production `mkstemp`/`mkdtemp`/
`NamedTemporaryFile(delete=False)` ownership, cross-platform `os.kill(pid, 0)` bans, `storage_gc`
wiring across plugins/knowledge, historical channel floor tolerance, and test sandbox isolation.

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
    """Covers P8 AST temp-hygiene, Windows PID safety, GC wiring, and historical floor scoping."""

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
            "import os\nos.environ['MINDIE_DIAGNOSTICS_ROOT'] = '/tmp/isolated'\n",
        )
        return repo

    def test_valid_plugin_checkout_passes_all_p8_checks(self) -> None:
        self._make_plugin_repo()
        self.assertEqual(sl_gate.verify_storage_lifecycle_hygiene([self.root]), [])

    def test_historical_pre_floor_checkout_skipped_unless_explicitly_required(self) -> None:
        repo = self._make_plugin_repo(version="0.1.17")
        (repo / "scripts/storage_lifecycle.py").unlink()
        # Historical checkout (< 0.1.25) is skipped when not in required_repos.
        self.assertEqual(sl_gate.verify_storage_lifecycle_hygiene([self.root]), [])
        # When explicitly targeted via --release-repo, pre-floor version fails.
        errors = sl_gate.verify_storage_lifecycle_hygiene([self.root], required_repos=["mindie-agent-cc"])
        self.assertTrue(any("< P8 floor 0.1.25" in err for err in errors), errors)

    def test_unowned_mkstemp_mkdtemp_and_named_temporary_file_fail(self) -> None:
        repo = self._make_plugin_repo()
        self._write(
            repo / "scripts/leaker.py",
            (
                "import tempfile\n"
                "def leak_dir():\n"
                "    d = tempfile.mkdtemp(prefix='bad-')\n"
                "    return {'ok': True}\n"
                "def leak_ntf():\n"
                "    f = tempfile.NamedTemporaryFile(delete=False)\n"
                "    f.close()\n"
            ),
        )
        errors = sl_gate.verify_storage_lifecycle_hygiene([self.root])
        self.assertTrue(any("leak_dir" in err and "mkdtemp" in err for err in errors), errors)
        self.assertTrue(any("leak_ntf" in err and "NamedTemporaryFile(delete=False)" in err for err in errors), errors)

    def test_owned_atomic_replace_and_allocator_module_cleanup_pass(self) -> None:
        mod = self._write(
            self.root / "owned.py",
            (
                "import os, shutil, tempfile\n"
                "def alloc_dir():\n"
                "    return tempfile.mkdtemp(prefix='ok-')\n"
                "def cleanup_dir(p):\n"
                "    shutil.rmtree(p, ignore_errors=True)\n"
                "def atomic_write(dst):\n"
                "    fd, tmp = tempfile.mkstemp()\n"
                "    os.close(fd)\n"
                "    os.replace(tmp, dst)\n"
            ),
        )
        self.assertEqual(sl_gate.inspect_python_temp_hygiene(mod), [])

    def test_unguarded_os_kill_zero_in_storage_module_fails(self) -> None:
        repo = self._make_plugin_repo()
        self._write(
            repo / "scripts/storage_lifecycle.py",
            "import os\ndef runtime_leases(pid: int = 1):\n    os.kill(pid, 0)\n",
        )
        errors = sl_gate.verify_storage_lifecycle_hygiene([self.root])
        self.assertTrue(any("unguarded `os.kill(pid, 0)`" in err for err in errors), errors)

    def test_missing_caller_wiring_or_test_isolation_fails(self) -> None:
        repo = self._make_plugin_repo()
        self._write(repo / "scripts/release_update.py", "def tick():\n    return None\n")
        self._write(repo / "tests/conftest.py", "# empty conftest without sandbox env isolation\n")
        errors = sl_gate.verify_storage_lifecycle_hygiene([self.root])
        self.assertTrue(any("does not invoke P8 storage lifecycle GC" in err for err in errors), errors)
        self.assertTrue(any("missing host sandbox isolation" in err for err in errors), errors)


if __name__ == "__main__":
    unittest.main()

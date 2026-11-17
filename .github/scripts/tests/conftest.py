"""Shared pytest sandbox isolation for MindIE Agent hub gate unit tests.

[Role]
Ensures every test in `.github/scripts/tests/` runs with isolated user, XDG, MindIE,
remote-dev, uv, and temporary directory environment variables (Principle 16).

[Invariants]
- Isolates `HOME`, `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `XDG_*`, `MINDIE_CONFIG_HOME`,
  `MINDIE_DATA_HOME`, `MINDIE_DIAGNOSTICS_ROOT`, `REMOTE_DEV_AUTH_DIR`, `UV_CACHE_DIR`,
  and `TMPDIR` into per-test temporary paths.

[Timeouts & Locks]
- Zero locks or subprocesses; pure `monkeypatch` setup.

[Side-Effect Policy]
- Strictly scoped to `tmp_path` cleaned up by `pytest`.
"""

from __future__ import annotations

from pathlib import Path
import pytest

ISOLATED_ENV_KEYS = (
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
    "MINDIE_DIAGNOSTICS_CONFIG",
    "REMOTE_DEV_AUTH_DIR",
    "UV_CACHE_DIR",
    "TMPDIR",
)


@pytest.fixture(autouse=True)
def _isolate_host_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_root = tmp_path / ".mindie-test-env"
    env_root.mkdir(parents=True, exist_ok=True)
    tmp_sub = env_root / "TMPDIR"
    tmp_sub.mkdir(parents=True, exist_ok=True)
    for key in ISOLATED_ENV_KEYS:
        target = tmp_sub if key == "TMPDIR" else env_root / key
        monkeypatch.setenv(key, str(target))

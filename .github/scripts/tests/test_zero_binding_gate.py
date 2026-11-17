"""Unit contracts for R4 zero-session-binding AST gate (Iron Rule 5 / Guardrail P2.7).

[Role]
Verifies `zero_binding_gate.verify_zero_session_binding_gates` across synthetic repository
checkouts for `coordinator` and all 6 Python/Node host plugins (`codex`, `cc`, `kimi`,
`agy`, `wb`, `dsh`), confirming both negative interception of deterministic session-binding
regressions and preservation of strict `knowledge` identity (`P2.1`).

[Invariants]
- Isolates `HOME`, `USERPROFILE`, `APPDATA`, `MINDIE_CONFIG_HOME`, `MINDIE_DATA_HOME`, and
  `MINDIE_DIAGNOSTICS_ROOT` inside per-test temporary directories (zero host pollution).
- Zero external subprocesses, network calls, or `MagicMock` hardware payloads.

[Timeouts & Locks]
- Pure Tier 0 in-memory/tempdir AST checks (`< 2s` total); acquires no locks.

[Side-Effect Policy]
- Writes only inside `tempfile.TemporaryDirectory` cleaned up after every test.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import zero_binding_gate as zgate  # noqa: E402


class ZeroBindingGateTests(unittest.TestCase):
    """Enforces Iron Rule 5 across coordinator and all host plugins without weakening P2.1."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mindie-zero-bind-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        sandbox = patch.dict(
            os.environ,
            {
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
            },
        )
        sandbox.start()
        self.addCleanup(sandbox.stop)
        self._populate_valid_repos()

    def _write(self, repo: str, rel: str, code: str) -> Path:
        repo_dir = self.root / repo
        (repo_dir / ".git").mkdir(parents=True, exist_ok=True)
        target = repo_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(code, encoding="utf-8", newline="\n")
        return target

    def _populate_valid_repos(self) -> None:
        self._write(
            "coordinator",
            "mindie_coordinator/agent_session.py",
            "def ensure_context(client, session_id, cwd=None):\n    return {}\n\n"
            "def context_for_execution(execution_id):\n    return {}\n",
        )
        self._write(
            "coordinator",
            "mindie_coordinator/task_server.py",
            "def _resolve_mcp_caller(meta, default_session_id='mcp'):\n    return ('mcp', default_session_id, None)\n\n"
            "def _handle_call(name, arguments, meta):\n    caller = _resolve_mcp_caller(meta)\n    return caller\n",
        )
        self._write(
            "coordinator",
            "mindie_coordinator/ops.py",
            "def task_schema(properties, required=()):\n"
            "    return {'properties': {'context_file': {'type': 'string'}, **properties}, 'required': list(required)}\n",
        )
        self._write(
            "mindie-agent-codex",
            "plugins/mindie-agent/scripts/mcp_identity.py",
            "def native_identity(meta):\n    return ('s', 't')\n\n"
            "def optional_native_identity(meta):\n    return None\n\n"
            "def optional_turn_identity(meta):\n    return None\n",
        )
        self._write(
            "mindie-agent-codex",
            "plugins/mindie-agent/scripts/mcp_transport.py",
            "def dispatch(surface, meta):\n"
            "    return native_identity(meta) if surface == 'knowledge' else optional_turn_identity(meta)\n",
        )
        self._write(
            "mindie-agent-codex",
            "plugins/mindie-agent/scripts/mcp_gate.py",
            "class Gate:\n"
            "    def call(self, request):\n"
            "        if self.surface == 'remote':\n"
            "            return self._remote_call(request)\n"
            "        if self.surface == 'components':\n"
            "            return optional_native_identity(request)\n"
            "        return native_identity(request)\n"
            "    def _remote_call(self, request):\n"
            "        return optional_turn_identity(request)\n",
        )
        self._write(
            "mindie-agent-cc",
            "scripts/mcp_server.py",
            "_CONNECTION_SESSION_ID = 'cc-mcp-1'\n\n"
            "def handle(surface, message):\n"
            "    if surface == 'knowledge':\n"
            "        session = claim_bind('id', 'tool', {})\n"
            "    else:\n"
            "        session = _CONNECTION_SESSION_ID\n"
            "    return session\n",
        )
        self._write(
            "mindie-agent-kimi",
            "scripts/mcp_server.py",
            "_CONNECTION_SESSION_ID = 'kimi-mcp-1'\n\n"
            "def remote_tools():\n    return _nonce_tools([], require=False)\n\n"
            "def component_tools():\n    return _nonce_tools([], require=False)\n\n"
            "def handle(surface, message):\n"
            "    if surface == 'knowledge':\n"
            "        session = claim_nonce(require_nonce('n'), 't', {})\n"
            "    else:\n"
            "        session = _CONNECTION_SESSION_ID\n"
            "    return session\n",
        )
        self._write(
            "mindie-agent-agy",
            "plugins/mindie-agent/scripts/mcp_server.py",
            "_CONNECTION_SESSION_ID = 'agy-mcp-1'\n\n"
            "def _resolve_session(surface, name, args):\n"
            "    return _CONNECTION_SESSION_ID\n",
        )
        self._write(
            "mindie-agent-wb",
            "plugins/mindie-agent/scripts/mcp_server.py",
            "_CONNECTION_SESSION_ID = 'wb-mcp-1'\n\n"
            "def _resolve_claim(surface, name, args, meta=None, require=False):\n"
            "    return (_CONNECTION_SESSION_ID, None, None)\n\n"
            "def call_remote_surface(name, args, meta=None):\n"
            "    return _resolve_claim('remote', name, args, meta=meta)\n\n"
            "def call_tools_surface(name, args, meta=None):\n"
            "    return _resolve_claim('tools', name, args, meta=meta)\n\n"
            "def call_knowledge_surface(name, args, meta=None):\n"
            "    return _resolve_claim('knowledge', name, args, meta=meta, require=True)\n",
        )
        self._write(
            "mindie-agent-dsh",
            "scripts/component_mcp.py",
            "def handle(message):\n    return component_tools.execute('sim', {})\n",
        )
        self._write(
            "mindie-agent-oc",
            "plugins/mindie-agent/scripts/mcp_server.py",
            "_CONNECTION_SESSION_ID = 'oc-mcp-1'\n\n"
            "def _resolve_session(surface, name, args):\n"
            "    if surface == 'knowledge':\n"
            "        return claim_bind('id', name, args)\n"
            "    return _CONNECTION_SESSION_ID\n",
        )
        self._write(
            "harness",
            "mindie_harness/mcp/router.py",
            "_CONNECTION_SESSION_ID = 'harness-mcp-1'\n\n"
            "def dispatch(surface, name, args):\n"
            "    if surface == 'knowledge':\n"
            "        return claim_bind('id', name, args)\n"
            "    return _CONNECTION_SESSION_ID\n",
        )

    def test_valid_sibling_checkouts_pass_zero_binding_gate(self):
        errors = zgate.verify_zero_session_binding_gates([self.root], require_siblings=True)
        self.assertEqual(errors, [])

    def test_coordinator_session_gate_regressions_are_caught(self):
        self._write(
            "coordinator",
            "mindie_coordinator/task_server.py",
            "def _handle_call(name, arguments, meta):\n    return native_turn_context(meta)\n",
        )
        self._write(
            "coordinator",
            "mindie_coordinator/ops.py",
            "def task_schema(properties):\n"
            "    return {'properties': properties, 'required': ['context_file']}\n",
        )
        errors = zgate.verify_zero_session_binding_gates([self.root], require_siblings=True)
        self.assertTrue(any("native_turn_context" in err for err in errors), errors)
        self.assertTrue(any("context_file" in err for err in errors), errors)

    def test_host_plugin_deterministic_bind_regressions_are_caught(self):
        self._write(
            "mindie-agent-kimi",
            "scripts/mcp_server.py",
            "_CONNECTION_SESSION_ID = 'kimi-mcp-1'\n\n"
            "def remote_tools():\n    return _nonce_tools([])\n\n"
            "def component_tools():\n    return _nonce_tools([], require=True)\n\n"
            "def handle(surface, message):\n    return claim_nonce(require_nonce('n'), 't', {})\n",
        )
        self._write(
            "mindie-agent-agy",
            "plugins/mindie-agent/scripts/mcp_server.py",
            "_CONNECTION_SESSION_ID = 'agy-mcp-1'\n\n"
            "def _resolve_session(surface, name, args):\n"
            "    if not args:\n        raise RuntimeError('Antigravity session identity is unavailable')\n"
            "    return _CONNECTION_SESSION_ID\n",
        )
        self._write(
            "mindie-agent-wb",
            "plugins/mindie-agent/scripts/mcp_server.py",
            "_CONNECTION_SESSION_ID = 'wb-mcp-1'\n\n"
            "def _resolve_claim(surface, name, args, meta=None, require=False):\n"
            "    return (_CONNECTION_SESSION_ID, None, None)\n\n"
            "def call_remote_surface(name, args, meta=None):\n"
            "    return _resolve_claim('remote', name, args, meta=meta, require=True)\n\n"
            "def call_tools_surface(name, args, meta=None):\n"
            "    return _resolve_claim('tools', name, args, meta=meta)\n\n"
            "def call_knowledge_surface(name, args, meta=None):\n"
            "    return _resolve_claim('knowledge', name, args, meta=meta, require=True)\n",
        )
        errors = zgate.verify_zero_session_binding_gates([self.root], require_siblings=True)
        self.assertTrue(any("mindie-agent-kimi" in err and "remote_tools" in err for err in errors), errors)
        self.assertTrue(any("mindie-agent-kimi" in err and "component_tools" in err for err in errors), errors)
        self.assertTrue(any("mindie-agent-agy" in err and "RuntimeError" in err for err in errors), errors)
        self.assertTrue(any("mindie-agent-wb" in err and "call_remote_surface" in err for err in errors), errors)

    def test_weakening_knowledge_passive_default_gate_is_caught(self):
        self._write(
            "mindie-agent-wb",
            "plugins/mindie-agent/scripts/mcp_server.py",
            "_CONNECTION_SESSION_ID = 'wb-mcp-1'\n\n"
            "def _resolve_claim(surface, name, args, meta=None, require=False):\n"
            "    return (_CONNECTION_SESSION_ID, None, None)\n\n"
            "def call_remote_surface(name, args, meta=None):\n"
            "    return _resolve_claim('remote', name, args, meta=meta)\n\n"
            "def call_tools_surface(name, args, meta=None):\n"
            "    return _resolve_claim('tools', name, args, meta=meta)\n\n"
            "def call_knowledge_surface(name, args, meta=None):\n"
            "    return _resolve_claim('knowledge', name, args, meta=meta, require=False)\n",
        )
        self._write(
            "mindie-agent-cc",
            "scripts/mcp_server.py",
            "_CONNECTION_SESSION_ID = 'cc-mcp-1'\n\n"
            "def handle(surface, message):\n    return _CONNECTION_SESSION_ID\n",
        )
        errors = zgate.verify_zero_session_binding_gates([self.root], require_siblings=True)
        self.assertTrue(any("mindie-agent-wb" in err and "call_knowledge_surface" in err for err in errors), errors)
        self.assertTrue(any("mindie-agent-cc" in err and "claim_bind" in err for err in errors), errors)

    def test_inverted_predicates_and_swapped_resolvers_are_caught(self):
        self._write(
            "mindie-agent-cc",
            "scripts/mcp_server.py",
            "_CONNECTION_SESSION_ID = 'cc-mcp-1'\n\n"
            "def handle(surface, message):\n"
            "    if surface != 'knowledge':\n"
            "        session = claim_bind('id', 'tool', {})\n"
            "    else:\n"
            "        session = _CONNECTION_SESSION_ID\n"
            "    return session\n",
        )
        self._write(
            "mindie-agent-wb",
            "plugins/mindie-agent/scripts/mcp_server.py",
            "_CONNECTION_SESSION_ID = 'wb-mcp-1'\n\n"
            "def _resolve_claim(surface, name, args, meta=None, config=None):\n"
            "    if surface != 'knowledge':\n"
            "        raise ValueError('blocked')\n"
            "    return {'session': _CONNECTION_SESSION_ID}\n\n"
            "def call_remote_surface(name, args, meta=None):\n"
            "    return _resolve_claim('remote', name, args, meta=meta)\n\n"
            "def call_tools_surface(name, args, meta=None):\n"
            "    return _resolve_claim('tools', name, args, meta=meta)\n\n"
            "def call_knowledge_surface(name, args, meta=None):\n"
            "    return _resolve_claim('knowledge', name, args, meta=meta)\n",
        )
        self._write(
            "mindie-agent-codex",
            "plugins/mindie-agent/scripts/mcp_gate.py",
            "class Gate:\n"
            "    def call(self, request):\n"
            "        if self.surface == 'components':\n"
            "            return native_identity(request)\n"
            "        return optional_native_identity(request)\n"
            "    def _remote_call(self, request):\n"
            "        return optional_turn_identity(request)\n",
        )
        errors = zgate.verify_zero_session_binding_gates([self.root], require_siblings=True)
        self.assertTrue(any("mindie-agent-cc" in err for err in errors), errors)
        self.assertTrue(any("mindie-agent-wb" in err for err in errors), errors)
        self.assertTrue(any("mindie-agent-codex" in err for err in errors), errors)

    def test_codex_transport_inverted_predicate_is_caught(self):
        self._write(
            "mindie-agent-codex",
            "plugins/mindie-agent/scripts/mcp_transport.py",
            "def dispatch(surface, meta):\n"
            "    return native_turn_identity(meta) if surface != 'knowledge' else optional_turn_identity(meta)\n",
        )
        errors = zgate.verify_zero_session_binding_gates([self.root], require_siblings=True)
        self.assertTrue(any("mcp_transport.py" in err for err in errors), errors)

    def test_prompt_and_guide_principle_contradictions_are_caught(self):
        self._write(
            "mindie-agent-codex",
            "plugins/mindie-agent/skills/mindie-agent/SKILL.md",
            "---\nname: mindie-agent\ndescription: test\n---\n"
            "returning (out_tensor, metrics_dict)\nNative call identity still applies to plugin tools\n"
            "## 3. Non-Intrusive First-Use Onboarding\n",
        )
        self._write(
            "mindie-agent-codex",
            "plugins/mindie-agent/skills/mindie-agent/references/workspace-setup.md",
            "# Workspace setup\n",
        )
        self._write(
            "mindie-agent-agy",
            "plugins/mindie-agent/skills/mindie-agent/SKILL.md",
            "---\nname: mindie-agent\ndescription: Manually enable MindIE knowledge\n---\n",
        )
        self._write("diagnostics", "AGENTS.md", "fallback.py Can be vendored as a single file\n")
        errors = zgate.verify_zero_session_binding_gates([self.root], require_siblings=True)
        self.assertTrue(any("(out_tensor, metrics_dict)" in err for err in errors), errors)
        self.assertTrue(any("Native call identity" in err for err in errors), errors)
        self.assertTrue(any("Non-Intrusive First-Use Onboarding" in err for err in errors), errors)
        self.assertTrue(any("disable-model-invocation" in err for err in errors), errors)
        self.assertTrue(any("workspace-setup.md" in err and "skills/" in err for err in errors), errors)
        self.assertTrue(any("mindie-agent-agy" in err and "manual" in err for err in errors), errors)
        self.assertTrue(any("diagnostics: AGENTS.md" in err for err in errors), errors)

    def test_ad01_opencode_bind_gate_and_harness_thin_delegation(self):
        # Reproduce the exact AD-01 OpenCode bug (`_with_bind_property` + unguarded `claim_bind` on deterministic tools)
        self._write(
            "mindie-agent-oc",
            "plugins/mindie-agent/scripts/mcp_server.py",
            "def _with_bind_property(tool):\n"
            "    tool['inputSchema']['properties']['_mindie_bind_id'] = {'type': 'string'}\n"
            "    return tool\n\n"
            "def _resolve_session(surface, name, args):\n"
            "    return claim_bind(args.get('_mindie_bind_id'), name, args)\n",
        )
        errors = zgate.verify_zero_session_binding_gates([self.root], require_siblings=True)
        self.assertTrue(any("mindie-agent-oc" in err and "_with_bind_property" in err for err in errors), errors)
        self.assertTrue(any("mindie-agent-oc" in err and "_CONNECTION_SESSION_ID" in err for err in errors), errors)

        # Thin host plugin delegating to `mindie_harness` passes when `harness` enforces P2.7 + P2.1
        self._write(
            "mindie-agent-oc",
            "plugins/mindie-agent/scripts/mcp_server.py",
            "from mindie_harness.mcp_gateway import dispatch\n\ndef main():\n    return dispatch('remote', 'ping', {})\n",
        )
        self.assertEqual(zgate.verify_zero_session_binding_gates([self.root], require_siblings=True), [])


if __name__ == "__main__":
    unittest.main()

"""Unit tests for the R4 zero-session-binding & silent default-on static gate (`P2.7` / `P2.8`).

[Role]
Verifies that `zero_binding_gate.py` passes valid zero-binding silent default-on checkouts
(including `${PLUGIN_ROOT}/mindie-agent/...` paths, `/mindie-agent-tools` identifiers,
`except TimeoutError: raise` in WorkBuddy, and optional caught `claim_bind` in OpenCode)
while reliably catching re-introduction of pre-call session/nonce/`context_file` gates,
manual `/mindie-agent` ceremonies, `disable-model-invocation`, or install docs in `skills/`.

[Invariants]
- Zero host pollution: uses `tempfile.TemporaryDirectory()` only.
- Pure in-memory/tempdir execution (`< 1s`), zero network calls, zero subprocesses.

[Timeouts & Locks]
- Synchronous stdlib `unittest` suite; no external locks.

[Side-Effect Policy]
- Writes only inside disposable `TemporaryDirectory` fixtures.
"""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import zero_binding_gate as zgate  # noqa: E402


class ZeroBindingGateTests(unittest.TestCase):
    """Enforces Iron Rule 5 & silent default-on across harness, coordinator, and all 7 host plugins."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="mindie-zero-bind-")
        self.root = Path(self._tmp.name)
        self._populate_valid_repos()

    def tearDown(self) -> None:
        self._tmp.cleanup()

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
            "def optional_native_identity(meta):\n    return None\n\n"
            "def optional_turn_identity(meta):\n    return None\n",
        )
        self._write(
            "mindie-agent-codex",
            "plugins/mindie-agent/scripts/mcp_transport.py",
            "def dispatch(surface, meta):\n    return optional_turn_identity(meta)\n",
        )
        self._write(
            "mindie-agent-codex",
            "plugins/mindie-agent/scripts/mcp_gate.py",
            "class Gate:\n"
            "    def call(self, request):\n"
            "        if self.surface == 'remote':\n"
            "            return self._remote_call(request)\n"
            "        return optional_native_identity(request)\n"
            "    def _remote_call(self, request):\n"
            "        return optional_turn_identity(request)\n",
        )
        self._write(
            "mindie-agent-codex",
            "plugins/mindie-agent/skills/mindie-agent/agents/openai.yaml",
            "interface:\n  display_name: \"MindIE Agent\"\npolicy:\n  allow_implicit_invocation: true\n",
        )
        self._write(
            "mindie-agent-cc",
            "scripts/mcp_server.py",
            "_CONNECTION_SESSION_ID = 'cc-mcp-1'\n\n"
            "def handle(surface, message):\n"
            "    return _CONNECTION_SESSION_ID\n",
        )
        self._write(
            "mindie-agent-kimi",
            "scripts/mcp_server.py",
            "_CONNECTION_SESSION_ID = 'kimi-mcp-1'\n\n"
            "def remote_tools():\n    return _nonce_tools([], require=False)\n\n"
            "def component_tools():\n    return _nonce_tools([], require=False)\n\n"
            "def knowledge_tools():\n    return _nonce_tools([], require=False)\n\n"
            "def handle(surface, message):\n"
            "    return _CONNECTION_SESSION_ID\n",
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
            "    try:\n"
            "        probe_session(meta)\n"
            "    except TimeoutError:\n"
            "        raise\n"
            "    except (OSError, ValueError):\n"
            "        pass\n"
            "    return (_CONNECTION_SESSION_ID, None, None)\n\n"
            "def call_remote_surface(name, args, meta=None):\n"
            "    return _resolve_claim('remote', name, args, meta=meta)\n\n"
            "def call_tools_surface(name, args, meta=None):\n"
            "    return _resolve_claim('tools', name, args, meta=meta)\n\n"
            "def call_knowledge_surface(name, args, meta=None):\n"
            "    return _resolve_claim('knowledge', name, args, meta=meta)\n",
        )
        self._write(
            "mindie-agent-dsh",
            "scripts/component_mcp.py",
            "def handle(message):\n    return component_tools.execute('sim', {})\n",
        )
        self._write(
            "mindie-agent-dsh",
            "scripts/knowledge_mcp.py",
            "_CONNECTION_SESSION_ID = 'dsh-mcp-1'\n\n"
            "def session_identity():\n    return _CONNECTION_SESSION_ID\n\n"
            "def discoverable_tools():\n    return []\n",
        )
        self._write(
            "mindie-agent-oc",
            "plugins/mindie-agent/scripts/mcp_server.py",
            "_CONNECTION_SESSION_ID = 'oc-mcp-1'\n\n"
            "def _resolve_session(surface, name, args):\n"
            "    try:\n"
            "        return claim_bind('opt', name, args)\n"
            "    except TimeoutError:\n"
            "        raise\n"
            "    except ValueError:\n"
            "        return _CONNECTION_SESSION_ID\n",
        )
        self._write(
            "harness",
            "mindie_harness/mcp/router.py",
            "_CONNECTION_SESSION_ID = 'harness-mcp-1'\n\n"
            "class MCPRouter:\n"
            "    def list_tools(self):\n"
            "        return self._tools\n"
            "    def call_tool(self, request):\n"
            "        return _CONNECTION_SESSION_ID\n",
        )
        for repo, rel in zgate._SKILL_PATHS:
            self._write(
                repo,
                rel,
                "---\nname: mindie-agent\ndescription: Ascend NPU engineering tools and graded knowledge.\n---\n"
                "# MindIE Agent Runtime Workflow\n"
                "Path example: `${PLUGIN_ROOT}/mindie-agent/config.json` and `/mindie-agent-tools`.\n",
            )

    def test_valid_sibling_checkouts_pass_zero_binding_gate(self):
        errors = zgate.verify_zero_session_binding_gates([self.root], require_siblings=True)
        self.assertEqual(errors, [])

    def test_coordinator_and_harness_session_gate_regressions_are_caught(self):
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
        self._write(
            "harness",
            "mindie_harness/mcp/router.py",
            "class MCPRouter:\n"
            "    def list_tools(self):\n"
            "        return []\n"
            "    def call_tool(self, request):\n"
            "        _verify_knowledge_admission(self.profile, 's', 'knowledge_query', None)\n"
            "        return 'session_identity_required'\n",
        )
        errors = zgate.verify_zero_session_binding_gates([self.root], require_siblings=True)
        self.assertTrue(any("native_turn_context" in err for err in errors), errors)
        self.assertTrue(any("context_file" in err for err in errors), errors)
        self.assertTrue(any("harness:" in err and "session_identity_required" in err for err in errors), errors)
        self.assertTrue(any("harness:" in err and "_verify_knowledge_admission" in err for err in errors), errors)

    def test_host_plugin_bind_regressions_are_caught_on_any_surface(self):
        self._write(
            "mindie-agent-kimi",
            "scripts/mcp_server.py",
            "_CONNECTION_SESSION_ID = 'kimi-mcp-1'\n\n"
            "def remote_tools():\n    return _nonce_tools([])\n\n"
            "def component_tools():\n    return _nonce_tools([], require=False)\n\n"
            "def knowledge_tools():\n    return _nonce_tools([], require=True)\n\n"
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
            "    return _resolve_claim('remote', name, args, meta=meta)\n\n"
            "def call_tools_surface(name, args, meta=None):\n"
            "    return _resolve_claim('tools', name, args, meta=meta)\n\n"
            "def call_knowledge_surface(name, args, meta=None):\n"
            "    return _resolve_claim('knowledge', name, args, meta=meta, require=True)\n",
        )
        errors = zgate.verify_zero_session_binding_gates([self.root], require_siblings=True)
        self.assertTrue(any("mindie-agent-kimi" in err and "remote_tools" in err for err in errors), errors)
        self.assertTrue(any("mindie-agent-kimi" in err and "knowledge_tools" in err for err in errors), errors)
        self.assertTrue(any("mindie-agent-kimi" in err and "require_nonce" in err for err in errors), errors)
        self.assertTrue(any("mindie-agent-agy" in err and "fail-closed" in err for err in errors), errors)
        self.assertTrue(any("mindie-agent-wb" in err and "call_knowledge_surface" in err for err in errors), errors)

    def test_strict_knowledge_gates_in_cc_codex_wb_dsh_are_caught(self):
        self._write(
            "mindie-agent-cc",
            "scripts/mcp_server.py",
            "_CONNECTION_SESSION_ID = 'cc-mcp-1'\n\n"
            "def handle(surface, message):\n"
            "    if surface == 'knowledge':\n"
            "        return claim_bind('id', 'tool', {})\n"
            "    return _CONNECTION_SESSION_ID\n",
        )
        self._write(
            "mindie-agent-wb",
            "plugins/mindie-agent/scripts/mcp_server.py",
            "_CONNECTION_SESSION_ID = 'wb-mcp-1'\n\n"
            "def _resolve_claim(surface, name, args, meta=None, config=None):\n"
            "    if surface == 'knowledge':\n"
            "        raise ValueError('blocked')\n"
            "    return {'session': _CONNECTION_SESSION_ID}\n\n"
            "def call_remote_surface(name, args, meta=None):\n"
            "    return _resolve_claim('remote', name, args, meta=meta)\n\n"
            "def call_tools_surface(name, args, meta=None):\n"
            "    return _resolve_claim('tools', name, args, meta=meta)\n",
        )
        self._write(
            "mindie-agent-codex",
            "plugins/mindie-agent/scripts/mcp_gate.py",
            "class Gate:\n"
            "    def call(self, request):\n"
            "        if self.surface == 'knowledge':\n"
            "            return native_turn_identity(request)\n"
            "        return optional_native_identity(request)\n"
            "    def _remote_call(self, request):\n"
            "        return optional_turn_identity(request)\n",
        )
        self._write(
            "mindie-agent-dsh",
            "scripts/knowledge_mcp.py",
            "GATED = 'Requires an active `/mindie-agent` session.'\n"
            "def session_identity():\n    raise RuntimeError('missing')\n"
            "def discoverable_tools():\n    return [] if not Admission('x').knowledge_lease('s') else []\n",
        )
        errors = zgate.verify_zero_session_binding_gates([self.root], require_siblings=True)
        self.assertTrue(any("mindie-agent-cc" in err and "claim_bind" in err for err in errors), errors)
        self.assertTrue(any("mindie-agent-wb" in err and "raises" in err for err in errors), errors)
        self.assertTrue(any("mindie-agent-codex" in err and "native_turn_identity" in err for err in errors), errors)
        self.assertTrue(any("mindie-agent-dsh" in err and "knowledge_mcp.py exposes" in err for err in errors), errors)
        self.assertTrue(any("mindie-agent-dsh" in err and "session_identity" in err for err in errors), errors)
        self.assertTrue(any("mindie-agent-dsh" in err and "discoverable_tools" in err for err in errors), errors)

    def test_codex_transport_strict_identity_is_caught(self):
        self._write(
            "mindie-agent-codex",
            "plugins/mindie-agent/scripts/mcp_transport.py",
            "def dispatch(surface, meta):\n"
            "    return native_turn_identity(meta) if surface == 'knowledge' else optional_turn_identity(meta)\n",
        )
        errors = zgate.verify_zero_session_binding_gates([self.root], require_siblings=True)
        self.assertTrue(any("mcp_transport.py" in err for err in errors), errors)

    def test_prompt_manifest_and_guide_principle_contradictions_are_caught(self):
        self._write(
            "mindie-agent-codex",
            "plugins/mindie-agent/skills/mindie-agent/SKILL.md",
            "---\nname: mindie-agent\ndescription: unquoted colon: breaks yaml\ndisable-model-invocation:   true\n---\n"
            "returning (out_tensor, metrics_dict)\nNative call identity still applies to plugin tools\n"
            "## 3. Non-Intrusive First-Use Onboarding\nInvoke /mindie-agent first.\n",
        )
        self._write(
            "mindie-agent-codex",
            "plugins/mindie-agent/skills/mindie-agent/agents/openai.yaml",
            "interface:\n  default_prompt: \"$mindie-agent help\"\npolicy:\n  allow_implicit_invocation: false\n",
        )
        self._write(
            "mindie-agent-codex",
            "plugins/mindie-agent/skills/mindie-agent/references/workspace-setup.md",
            "# Workspace setup\n",
        )
        self._write(
            "mindie-agent-kimi",
            "kimi.plugin.json",
            '{"systemPrompt": "Knowledge tools require /mindie-agent and a fresh PreToolUse-bound request_nonce."}\n',
        )
        self._write(
            "mindie-agent-wb",
            "plugins/mindie-agent/plugin.json",
            '{"suggestedPrompts": ["输入/mindie-agent即可启动"]}\n',
        )
        self._write("diagnostics", "AGENTS.md", "fallback.py Can be vendored as a single file\n")
        errors = zgate.verify_zero_session_binding_gates([self.root], require_siblings=True)
        self.assertTrue(any("(out_tensor, metrics_dict)" in err for err in errors), errors)
        self.assertTrue(any("Native call identity" in err for err in errors), errors)
        self.assertTrue(any("Non-Intrusive First-Use Onboarding" in err for err in errors), errors)
        self.assertTrue(any("disable-model-invocation" in err for err in errors), errors)
        self.assertTrue(any("unquoted `: `" in err for err in errors), errors)
        self.assertTrue(any("SKILL.md exposes `/mindie-agent`" in err for err in errors), errors)
        self.assertTrue(any("openai.yaml sets `allow_implicit_invocation: false`" in err for err in errors), errors)
        self.assertTrue(any("workspace-setup.md" in err and "skills/" in err for err in errors), errors)
        self.assertTrue(any("kimi.plugin.json" in err for err in errors), errors)
        self.assertTrue(any("mindie-agent-wb: plugins/mindie-agent/plugin.json exposes" in err for err in errors), errors)
        self.assertTrue(any("diagnostics: AGENTS.md" in err for err in errors), errors)

    def test_ad01_opencode_bind_gate_and_harness_thin_delegation(self):
        self._write(
            "mindie-agent-oc",
            "plugins/mindie-agent/scripts/mcp_server.py",
            "def _with_bind_property(tool):\n"
            "    tool['inputSchema']['properties']['_mindie_bind_id'] = {'type': 'string'}\n"
            "    return tool\n\n"
            "def _resolve_session(surface, name, args):\n"
            "    return claim_bind(args.get('_mindie_bind_id'), name, args)\n",
        )
        errors = zgate.verify_zero_session_binding_gates(
            [self.root], require_siblings=True, required_repos=("mindie-agent-oc",)
        )
        self.assertTrue(any("mindie-agent-oc" in err and "_with_bind_property" in err for err in errors), errors)
        self.assertTrue(any("mindie-agent-oc" in err and "uncaught fail-closed `claim_bind`" in err for err in errors), errors)

        self._write(
            "mindie-agent-oc",
            "plugins/mindie-agent/scripts/mcp_server.py",
            "from mindie_harness.mcp_gateway import dispatch\n\ndef main():\n    return dispatch('remote', 'ping', {})\n",
        )
        self.assertEqual(zgate.verify_zero_session_binding_gates([self.root], require_siblings=True), [])


if __name__ == "__main__":
    unittest.main()

# Stable MindIE Knowledge Invocation on Windows

This runbook records the recovery path validated against MindIE Agent 0.1.32 on Windows.

## Scope

Use the configured MindIE runtime from `%USERPROFILE%\\.config\\mindie-agent\\codex.json`. Do not use the system Python, the IDE Python, or a virtual environment selected by `PATH`. The runtime path in `codex.json` is the source of truth for both `python` and `runtime_scripts`.

## Preconditions

1. Resolve the configured runtime and confirm that the interpreter exists.
2. Run the interpreter with `-I` so user-site packages and ambient `PYTHONPATH` cannot change imports.
3. On Windows, validate the `Scripts\\pythonw.exe` PE subsystem before starting the background service. The value must be `2` (`IMAGE_SUBSYSTEM_WINDOWS_GUI`). A console-subsystem binary with value `3` is invalid even when its filename is `pythonw.exe`.
4. Preserve a byte-for-byte backup before repairing a bad launcher. The repair should replace the runtime with a correctly packaged GUI launcher. A locally verified emergency repair changed only the PE subsystem field from `3` to `2`, retained the backup, and passed the runtime validator.

## Activation and query

Activate the configured runtime with the bundled bridge script, then inspect status. A successful state must report an active lease, a bound capture, `capture-ready` experience, a running service, and live worker, summary, and outbox processes.

For deterministic Knowledge calls, invoke the Python API in the configured runtime:

```python
from mindie_knowledge import knowledge_cli

result = knowledge_cli.invoke(
    "knowledge_query",
    {
        "query": "the task question",
        "domain": "vllm-ascend",
        "limit": 5,
        "token_budget": 4000,
        "mode": "reuse",
        "conditions": {},
    },
)
print(result)
```

The direct API call is the stable fallback for MindIE Agent 0.1.32. The shell wrapper that reads JSON from stdin returned `invalid_arguments` in the validated environment before dispatching the same request. Do not treat that wrapper failure as a Knowledge backend failure.

## Distillation authorization

`knowledge_query` success proves that the Knowledge backend is reachable and returning real records. `knowledge_distill` additionally requires a current-session `/mindie-agent` receipt. If the CLI reports `knowledge_inactive` because the current session has no receipt, stop the distillation attempt and report the authorization boundary. Do not loop on activation or resend the same request.

A distillation input must include:

- the verified milestone and its evidence,
- the affected domain,
- related query references,
- the proposed reusable rule,
- the task state, such as `verified_milestone`.

## Failure classification

- `windowless_interpreter_invalid`: inspect the configured runtime's `pythonw.exe` PE subsystem. Do not switch to the environment's default Python.
- `connection_unavailable`: retry the existing endpoint once and re-check the original receipt. Do not create a second service blindly.
- `invalid_arguments` from the stdin wrapper: use the direct `knowledge_cli.invoke` call above and record the wrapper limitation.
- `knowledge_inactive` during distillation: the current session lacks the required lease receipt. Query availability and distillation authorization are separate checks.

## Verification record

Record the exact runtime path, the PE subsystem result, the bridge status output, and one real query result. Keep the query receipt separate from any distillation receipt. A service marked active without `capture-ready` is not sufficient evidence that the Knowledge path is healthy.

# Windows Knowledge Invocation & Recovery

[中文](knowledge-invocation-recovery.md) · [Documentation Center](README.en.md)

This runbook is for developers and maintainers using `mindie-agent-codex` on Windows. It explains how to invoke knowledge capabilities through the configured runtime binding and native session identity, and how to recover by failure stage when input encoding, authorization, the Windows service launcher, or transport fails. It preserves the Windows field report contributed by `YzTongNiar` in [PR #357](https://github.com/mindie-agent/mindie-agent/pull/357), but it is **not** a desktop reproduction or acceptance of that field report: statements marked "inspected" come from source and interface review at the pinned versions, "field report" means the contributor's observation, and "not reproduced" remains explicitly unknown.

<a id="scope"></a>
## Scope and evidence

### Contribution and versions

| Item | Recorded fact |
| --- | --- |
| Field report | `YzTongNiar` / [PR #357](https://github.com/mindie-agent/mindie-agent/pull/357), original commit `cbefa9a72ecff494a60d47ed8731843cbeb29637` |
| Codex plugin | Latest formal release `mindie-agent-codex 0.1.32`, commit inspected for the field report `2a8ee6fadda3c750b43ca329fce8794e4254eb3f` |
| Codex `main` companion fix | [mindie-agent-codex#118](https://github.com/mindie-agent/mindie-agent-codex/pull/118) on `mindie-agent-codex` `main`, merged commit `d413a20e2d09df607e70170bd18618045cc65fd9` (`d413a20`); **unreleased**, not in formal `0.1.32` |
| Declared Knowledge baseline | `mindie-knowledge 0.13.17`, `315fc4b` |
| Knowledge `main` inspected here | `mindie-knowledge 0.13.19`, `c164e16` |
| Contributor's installed Knowledge revision | **Unknown**; independently updated installations can differ, so the `0.13.19` findings must not be presented retroactively as field evidence |
| Native Codex, Windows, PowerShell, Python distribution, `uv` versions | Not fully recorded in the field report; the operator must add them, and missing facts stay unknown |

### Inspected, reported, and not reproduced

- **Inspected (source/interfaces)**: stdin parsing and closed error mapping in `knowledge_cli.py`; adapter admission via `CODEX_THREAD_ID`; `knowledge_query` / `knowledge_distill` authorization boundaries; the shared PE subsystem check; and the thread semantics of the engine's `worker` / `summary` / `outbox` status fields.
- **Field report (contributor observation)**: the stdin wrapper returned `invalid_arguments` before dispatch; the generated `Scripts\pythonw.exe` was rejected by the Windows scheduled-task launcher guard; the contributor locally changed a PE header field while attempting a repair.
- **Not reproduced or not established**: the exact bytes sent by the contributor, the precise field trigger, the upstream origin of the CUI launcher, and Windows desktop end-to-end acceptance. The parser experiment proves error conflation, not that the field failure was necessarily an encoding problem.

The correct conclusion is therefore:

> The indistinguishability of `invalid_arguments` is a confirmed adapter defect. Encoding, an unsupported argv shape, empty input, and malformed JSON are all candidate causes. Without the original invocation and sanitized byte evidence, the exact field trigger remains unproven.

This runbook does not support modifying signed binaries, bypassing Windows security policy, fabricating session identity, or directly importing internal modules. None of those is a supported recovery path.

<a id="runtime-binding"></a>
## Runtime binding and native identity

### Configuration resolution order

1. If `MINDIE_AGENT_CONFIG` is set and non-empty, use the file it points to.
2. Otherwise use the default `%USERPROFILE%\.config\mindie-agent\codex.json`.
3. Read the JSON once as UTF-8 and confirm that `python` and `runtime_scripts` are both non-empty strings.

`MINDIE_AGENT_CONFIG` is an explicit override, not an additional candidate. Do not also read the default file and then "pick whichever works". A configuration-read failure must be visible; never silently fall back to system Python or another installation.

### The canonical `(python, runtime_scripts)` pair

`python` and `runtime_scripts` must come from the **same** configuration object and the same installation binding, and must be consumed together as an atomic pair:

```powershell
$configPath = if ($env:MINDIE_AGENT_CONFIG) {
    $env:MINDIE_AGENT_CONFIG
} else {
    Join-Path $env:USERPROFILE '.config\mindie-agent\codex.json'
}

$config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 `
    -ErrorAction Stop | ConvertFrom-Json

$runtimePython = [string]$config.python
$runtimeScripts = [string]$config.runtime_scripts
$cli = Join-Path $runtimeScripts 'knowledge_cli.py'

if (-not (Test-Path -LiteralPath $runtimePython -PathType Leaf)) {
    throw "Configured runtime python is missing: $runtimePython"
}
if (-not (Test-Path -LiteralPath $cli -PathType Leaf)) {
    throw "Configured runtime scripts do not contain knowledge_cli.py: $runtimeScripts"
}
```

Never:

- substitute `Get-Command python`, an IDE interpreter, a virtual environment on `PATH`, or system Python for `config.python`;
- combine `python` from installation A with `runtime_scripts` from installation B;
- "repair" the selected virtual environment by resolving a symlink or redirector into another environment;
- copy `knowledge_cli.py` into another environment and run it there.

On Windows, a virtual environment's `python.exe` may be a redirector to a base interpreter, while `sys.prefix` must still identify the selected virtual environment. Diagnose identity first, not the resolved path:

```powershell
& $runtimePython -I -c "import sys, importlib.metadata as m; print(sys.prefix); print(m.version('mindie-knowledge'))"
```

`-I` puts the interpreter in isolated mode (also enabling `-E` and `-s`) and ignores `PYTHON*` environment variables and user site-packages. It guarantees interpreter isolation only; it does **not** provide native session identity or bypass knowledge admission.

### Native session identity

`CODEX_THREAD_ID` must be supplied by the current native Codex tool environment. Check only whether it exists; never print, log, or echo its value:

```powershell
if (-not $env:CODEX_THREAD_ID) {
    throw 'Run from the current native Codex tool environment; do not invent a session ID.'
}
```

Never:

- set or fabricate `CODEX_THREAD_ID` manually;
- copy another session's thread ID, token, or internal verification fields;
- use `-I`, environment variables, or the configuration file to "construct" current-session authorization;
- paste thread IDs, tokens, cookies, or full conversations into public logs, issues, or documentation.

| Fact needed | Acceptable source | Forbidden substitute |
| --- | --- | --- |
| Configuration file | `MINDIE_AGENT_CONFIG` or the default `codex.json` | Guessing another user directory or reading an unrelated stale config |
| Interpreter | `python` from the same configuration object | `PATH` / system / IDE Python |
| Adapter script | `knowledge_cli.py` under the same configuration's `runtime_scripts` | Scripts from another installation or private package modules |
| Session identity | `CODEX_THREAD_ID` from the current native tool environment | Fabrication, cross-session copying, or assembling internal fields |
| Virtual-environment identity | The interpreter's `sys.prefix` and actual package versions | Resolving a redirector into the base environment |

<a id="powershell-input"></a>
## PowerShell input contract

### Actual CLI contract in `mindie-agent-codex 0.1.32`

The inspected `0.1.32` adapter (`<runtime_scripts>/knowledge_cli.py`) behaves as follows:

1. It requires exactly one positional argument as the operation name.
2. It reads at most 1 MiB plus one byte from binary stdin.
3. It decodes strictly as `utf-8-sig` (UTF-8, optional BOM).
4. It parses JSON.
5. It collapses several input failures into the same `invalid_arguments` response without stage or reason.

`describe` consumes no input. Formal `0.1.32` has no `--input-file` (that capability is merged on `main` but unreleased; see below), and CLI input failures have no structured `stage` / `reason` distinction. stdin is therefore the only input channel in `0.1.32`, and the caller must guarantee UTF-8 bytes.

### Two distinct PowerShell 5.1 traps

| Symptom | Root cause | Result |
| --- | --- | --- |
| Chinese becomes `?` in a pipe | Windows PowerShell 5.1's `$OutputEncoding` defaults to ASCII for text piped to native programs | Characters are replaced before Python sees them and cannot be recovered afterward |
| A redirected file fails to parse | `Out-File`, `>`, and `>>` default to UTF-16LE | The CLI's `utf-8-sig` decoder fails and returns `invalid_arguments` |

Two common misdiagnoses must also be corrected:

- "PowerShell always pipes UTF-16" is false: pipes and file redirection are different encoding paths.
- "Just set `PYTHONUTF8=1`" is false: Python cannot recover characters already replaced upstream, and `-I` ignores `PYTHON*` configuration.

### Console-attached UTF-8 pipe invocation (Windows PowerShell 5.1)

The following example applies only to **console-attached Windows PowerShell 5.1** (`powershell.exe`). It reads and restores `[Console]::OutputEncoding`; in a headless/consoleless host with no console handle (a boundary the adapter's `native_entry.py` already recognizes), reading or setting that property can throw "The handle is invalid" before dispatch, and restoration in `finally` can throw again and obscure the first failure. Use the consoleless invocation in the next subsection for such hosts.

This example is derived from the inspected public interfaces. It is **not** a live Windows desktop acceptance result from this review. It does not bypass `/mindie-agent` activation and does not prove that the service or capture is ready.

```powershell
$configPath = if ($env:MINDIE_AGENT_CONFIG) {
    $env:MINDIE_AGENT_CONFIG
} else {
    Join-Path $env:USERPROFILE '.config\mindie-agent\codex.json'
}

$config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 `
    -ErrorAction Stop | ConvertFrom-Json

$runtimePython = [string]$config.python
$cli = Join-Path ([string]$config.runtime_scripts) 'knowledge_cli.py'

if (-not $env:CODEX_THREAD_ID) {
    throw 'Run from the current native Codex tool environment; do not invent a session ID.'
}

$payload = @{
    query = 'The actual retrieval text for the current problem'
    mode = 'reuse'
    limit = 5
    token_budget = 4000
} | ConvertTo-Json -Depth 20 -Compress

$savedOutputEncoding = $OutputEncoding
$savedConsoleEncoding = [Console]::OutputEncoding
$callExit = 1
try {
    $OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    [Console]::OutputEncoding = $OutputEncoding

    $payload | & $runtimePython -I $cli knowledge_query
    $callExit = $LASTEXITCODE
} finally {
    $OutputEncoding = $savedOutputEncoding
    [Console]::OutputEncoding = $savedConsoleEncoding
}

if ($callExit -ne 0) {
    throw "knowledge_query failed with exit code $callExit; inspect its JSON error above."
}
```

Acceptance must use **Windows PowerShell 5.1 `powershell.exe`**, not only `pwsh`, and must verify the characters the CLI actually received rather than merely a zero exit code.

### Consoleless (headless) Windows PowerShell 5.1 invocation

This example targets the actual CLI contract of `mindie-agent-codex 0.1.32` and is likewise derived from the inspected public interfaces; it is **not** a live Windows desktop acceptance result from this review. It never reads or writes `[Console]::OutputEncoding` and therefore does not depend on a console handle. stdout/stderr are read asynchronously immediately after the process starts so a full pipe buffer cannot deadlock it; stdin receives raw UTF-8 bytes and is then closed. `ProcessStartInfo.StandardOutputEncoding` / `StandardErrorEncoding` decode both streams as UTF-8, and the exit code comes from the actual child process rather than PowerShell's pipeline state.

```powershell
$configPath = if ($env:MINDIE_AGENT_CONFIG) {
    $env:MINDIE_AGENT_CONFIG
} else {
    Join-Path $env:USERPROFILE '.config\mindie-agent\codex.json'
}

$config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 `
    -ErrorAction Stop | ConvertFrom-Json

$runtimePython = [string]$config.python
$runtimeScripts = [string]$config.runtime_scripts
$cli = Join-Path $runtimeScripts 'knowledge_cli.py'

if (-not (Test-Path -LiteralPath $runtimePython -PathType Leaf)) {
    throw "Configured runtime python is missing: $runtimePython"
}
if (-not (Test-Path -LiteralPath $cli -PathType Leaf)) {
    throw "Configured runtime scripts do not contain knowledge_cli.py: $runtimeScripts"
}
if (-not $env:CODEX_THREAD_ID) {
    throw 'Run from the current native Codex tool environment; do not invent a session ID.'
}

$payload = @{
    query = 'The actual retrieval text for the current problem'
    mode = 'reuse'
    limit = 5
    token_budget = 4000
} | ConvertTo-Json -Depth 20 -Compress

function ConvertTo-NativeArgument([string]$value) {
    if ($value.Length -eq 0) { return '""' }
    if ($value -notmatch '[\s"]') { return $value }
    return '"' + (($value -replace '(\\*)"', '$1$1\"') -replace '(\\+)$', '$1$1') + '"'
}

$startInfo = [System.Diagnostics.ProcessStartInfo]::new()
$startInfo.FileName = $runtimePython
$startInfo.Arguments = @(
    '-I'
    (ConvertTo-NativeArgument $cli)
    'knowledge_query'
) -join ' '
$startInfo.UseShellExecute = $false
$startInfo.CreateNoWindow = $true
$startInfo.RedirectStandardInput = $true
$startInfo.RedirectStandardOutput = $true
$startInfo.RedirectStandardError = $true
$startInfo.StandardOutputEncoding = [System.Text.UTF8Encoding]::new($false)
$startInfo.StandardErrorEncoding = [System.Text.UTF8Encoding]::new($false)

$process = [System.Diagnostics.Process]::new()
try {
    $process.StartInfo = $startInfo
    if (-not $process.Start()) {
        throw 'Failed to start the configured knowledge interpreter.'
    }

    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()

    $payloadBytes = [System.Text.UTF8Encoding]::new($false).GetBytes($payload)
    $process.StandardInput.BaseStream.Write($payloadBytes, 0, $payloadBytes.Length)
    $process.StandardInput.BaseStream.Flush()
    $process.StandardInput.Close()

    $process.WaitForExit()
    $callExit = $process.ExitCode
    $stdout = $stdoutTask.Result
    $stderr = $stderrTask.Result
} finally {
    $process.Dispose()
}

if ($stderr) {
    Write-Error -Message $stderr -ErrorAction Continue
}
Write-Output $stdout

if ($callExit -ne 0) {
    throw "knowledge_query failed with exit code $callExit; inspect its JSON error above."
}
```

### Why the direct `knowledge_cli.invoke(...)` fallback was removed

`from mindie_knowledge import knowledge_cli` has the wrong module ownership. The knowledge adapter belongs to the Codex plugin: its source is `mindie-agent-codex/plugins/mindie-agent/scripts/knowledge_cli.py`, packaged under `mindie_codex/scripts`. It is not `mindie_knowledge.knowledge_cli`.

Even with the correct adapter module, a direct `invoke()` call is not a supported recovery protocol:

- it bypasses only the CLI positional-argument and stdin parsing, **not** native `CODEX_THREAD_ID` admission, routing, domain lease, or contribution authorization;
- it returns a Python object, so `print(result)` emits a Python representation rather than the CLI's JSON/exit-status contract;
- exceptions differ in type and propagation, making it easy to mistake "parsed" for "succeeded";
- it is not a stable public API and cannot become a documented replacement entry point.

This runbook therefore no longer recommends any direct-import fallback. Recover the input bytes or handle the failure by stage instead of switching entry points.

### Post-release `--input-file` and structured errors (merged on `main`, unreleased in `0.1.32`)

Explicit file input and structured failure fields were implemented in [mindie-agent-codex#118](https://github.com/mindie-agent/mindie-agent-codex/pull/118) (`d413a20`) and merged to `mindie-agent-codex` `main`, and were verified in the hosted `windows-latest` CI [`adapter (windows-latest)`](https://github.com/mindie-agent/mindie-agent-codex/actions/runs/43748768061/job/132920529110) job. They are still **unreleased and unavailable in formal `mindie-agent-codex 0.1.32`**, so they must not be used as field recovery steps for `0.1.32`: `0.1.32` field installations must still use the console-attached UTF-8 stdin pipe above or the consoleless `ProcessStartInfo` path until a formal release `> 0.1.32` is published:

```text
knowledge_cli.py describe
knowledge_cli.py <operation>
knowledge_cli.py <operation> --input-file <path>
```

Design constraints:

- UTF-8, optional UTF-8 BOM, retaining the 1 MiB byte bound;
- exactly one input source, and the selected file is authoritative;
- `--input-file` requires the selected path to be a regular file (`Path.is_file()`); directories, FIFOs/pipes, and device nodes must fail explicitly rather than being treated as empty input or falling back to stdin;
- an unreadable file returns explicit `input_unavailable` / `stage=input_read`; it never falls back to stdin and is never disguised as empty input or a JSON error;
- parser failures remain JSON responses with a nonzero exit status, never uncaught `argparse` usage output;
- `describe` consumes no input and rejects incompatible extra flags.

Only after a formal `mindie-agent-codex > 0.1.32` release may callers switch to:

```powershell
$payload | Set-Content -LiteralPath $inputFile -Encoding UTF8 -ErrorAction Stop
& $runtimePython -I $cli knowledge_query --input-file $inputFile
if ($LASTEXITCODE -ne 0) {
    throw "knowledge_query failed with exit code $LASTEXITCODE; inspect its JSON error above."
}
```

A UTF-8 BOM written by PowerShell 5.1 is acceptable under that contract. Structured `stage` / `reason` values (such as `cli_input`, `input_encoding`, `input_json`, or `schema_unknown_field`) were likewise merged to `main` in [mindie-agent-codex#118](https://github.com/mindie-agent/mindie-agent-codex/pull/118) (`d413a20`) but are **unreleased in formal `0.1.32`**: `0.1.32` still collapses CLI input errors into the closed `invalid_arguments` response.

<a id="windows-launcher"></a>
## Windows service launcher

### Keep the two capabilities separate

The Python API capability needed for knowledge invocation and the GUI-subsystem capability needed for a Windows scheduled-task launcher are independent boundaries:

- an environment may pass Python API validation while lacking Windows scheduled-task launch capability (`Subsystem == 2`); in `mindie-agent-codex`, `knowledge_query` still connects to the selected knowledge service (`connect(selected)`): an already-running healthy service may answer, whereas a cold query depends on successful service startup (`ensure_service`) and cannot be assumed to succeed when the scheduled-task launcher is invalid;
- the `Scripts\pythonw.exe` generated by that same environment may be a console-subsystem (CUI) launcher and cannot be a scheduled-task entry;
- Task Scheduler executes the configured program directly, so Python's in-process `CREATE_NO_WINDOW` and a task's `Hidden` property cannot substitute for a valid entry binary.

The shared guard parses the entry binary's PE32/PE32+ header and requires `Subsystem == 2` (`IMAGE_SUBSYSTEM_WINDOWS_GUI`). A file named `pythonw.exe` is **not** evidence; a CUI launcher with `Subsystem == 3` must be rejected explicitly. The check runs both before new registration and before a recovered legacy task is actually launched.

### PE `Subsystem` `3 → 2` byte-patching is explicitly rejected

Changing the PE header `Subsystem` from `3` to `2` is not a supported recovery action:

- it violates historical guardrail **P1.6**, which forbids overwriting or patching interpreter binaries;
- PE headers are image content covered by Authenticode, so modifying them invalidates an existing signature and may cause rejection by Smart App Control or enterprise policy (this does not mean every unsigned executable is invariably blocked, but it is enough to disqualify the intervention as a product recovery method);
- a passing header check only proves that one field equals `2`; it does not prove venv dispatch, launch arguments, signature validity, desktop behavior, absence of `conhost.exe`, or graceful shutdown;
- the patch preserves the wrong provenance and non-reproducible local state, and will fail again on the next reinstall or upgrade; keeping a backup alone cannot restore provenance or validate the patched launcher.

Do not copy a system `pythonw.exe` into a venv, do not fall back to an ambient Python, and do not advise users to disable Windows protections.

### Safe candidate recovery path

1. **Classify the fault**: missing entry, unreadable/malformed entry, or a readable CUI launcher. Do not collapse all three into one "invalid launcher" message.
2. **Select a genuinely GUI-capable distribution**: use the existing installation/preparation mechanism to select an approved, compatible Python distribution whose `pythonw.exe` really is `Subsystem == 2`. `uv --python 3.13` is a version selection request, not a GUI-subsystem guarantee.
3. **Build a fresh owned candidate**: build a new candidate from that explicitly selected base with the existing builder, and validate the generated launcher's PE subsystem, dependency revisions, adapter/API compatibility, and virtual-environment identity. API validation and "can be a scheduled-task entry" validation must remain separate; API success is not service readiness.
4. **Atomic handoff**: publish the candidate through the existing native binding transaction and preserve the old usable binding until replacement validation succeeds. Validate before retiring the old service so publication cannot destroy a still-usable binding first.
5. **Do not blindly reinstall the same generation**: both preparation paths can reuse caches that do not encode this repair. Use a fresh candidate generation/root, or a corrected formal release. Do not delete a bound runtime or clear unrelated user caches.

Candidate-stage service validation (for example, `product_contract.probe(..., require_windows_service=True)` forwarding to `candidate_validate.py` to reuse the shared PE check, coordinated by `bootstrap.py`, `component_update.py`, and `release_activation.py` in the preparation and activation flow) was implemented in [mindie-agent-codex#118](https://github.com/mindie-agent/mindie-agent-codex/pull/118) (`d413a20`) and merged to `mindie-agent-codex` `main`, and was verified in hosted `windows-latest` CI. However, it is **unreleased in formal `mindie-agent-codex 0.1.32`**: the released `0.1.32` guarantee remains the actual PE check during registration and recovered launch, while **interactive Windows desktop Task Scheduler acceptance of this path remains unperformed**. Do not describe it as a capability already available to `0.1.32` installations.

A service-capability failure blocks only the knowledge/capture actions that depend on the service; deterministic tools and unrelated user work remain usable, but whether a query works still depends on its actual route and service state, so it must not be assumed to succeed after a service-launcher failure. Reporting "API success but unavailable service launcher" honestly as service-not-ready is the complete state.

<a id="session-authorization"></a>
## Session, domain and contribution authorization

Knowledge capabilities have three independent authorization/consent layers, and one successful call cannot establish the others:

1. **Native session authorization**: whether the current session has manually invoked `/mindie-agent`; it is never inherited across sessions, forks, or subagents.
2. **Domain lease**: whether the selected routed domain has its own valid lease; the default engine's lease does not substitute for the selected domain's lease.
3. **Persistent contribution consent and scope**: whether the user enabled sharing, the destination repository, and the authorized project scope; this is decoupled from the plugin version and independent of session authorization.

### Authorization matrix for query and distillation

| Current native session / selected domain | `knowledge_query` | `knowledge_distill` |
| --- | --- | --- |
| Neither the default nor the selected engine has the session grant | `knowledge_inactive` | `knowledge_inactive` |
| The default engine has the grant, but the routed target lacks its own lease | Public retrieval can proceed through the verified adapter identity | `lease_required` |
| The selected engine has the required lease | May proceed | Still requires valid contribution consent and scope |
| Sharing is disabled or capture is outside the authorized scope | Retrieval can remain available | Do not promise local-only distillation; the inspected transport enforces contribution authorization |

It follows that:

- `knowledge_inactive` is **not** a distill-only error; queries can be rejected the same way;
- when "the query succeeded but distillation returned `knowledge_inactive`", compare session identity, configuration, route, and timing. Do not infer a general "query needs no activation" contract;
- a distill routed to the selected domain may return `lease_required` rather than `knowledge_inactive` when it has the default-session grant but lacks that domain's lease;
- disabled sharing or out-of-scope capture does not automatically disable retrieval, but "local read-only" is not a promise that distillation can bypass contribution authorization.

### Manual entry and prohibitions

- Manual `/mindie-agent` authorizes only the current session; it cannot repair interpreter provenance, input encoding, service registration, or the configuration binding.
- Repeating `/mindie-agent` does not supply a missing domain lease or contribution consent, and may create duplicate services and uncertain state.
- Never fabricate leases, thread IDs, tokens, or internal verification fields, and never use direct adapter imports to "bypass" admission.
- A successful `knowledge_query` proves only that the selected route's retrieval path worked for that request. It does not prove that capture is bound, distillation is admitted, or knowledge was published.

<a id="readiness"></a>
## Capability-specific readiness

Health must be evaluated against the requested capability and persisted consent; a single fixed checklist cannot apply to every scenario.

| Requested capability | Required evidence |
| --- | --- |
| Runtime invocation | Canonical configured interpreter/scripts pair, isolated invocation, actual package identities |
| Query | Correct current native identity and session grant, successful request/response through the selected route |
| Capture with sharing disabled | The persisted disabled choice is respected; no capture is required |
| Capture outside authorized scope | Explicit out-of-scope disposition; no forced enrollment |
| Enabled, authorized, in-scope capture | Bound capture and `capture-ready`, or a visible failure/degraded state |
| Service health | Correct owner/endpoint, relevant liveness, and no reported background failure |
| Distillation/indexing | An actual operation receipt/result, not thread liveness |
| Community publication | An actual publication outcome or remote reference; local persistence is insufficient |

Therefore:

- with sharing disabled or deliberately out of scope, do not cold-start capture merely to satisfy a health checklist; a later authorized query may still require the retrieval service;
- only "enabled, authorized, in-scope" capture requires `capture-ready`; its absence must not be treated as a universal failure;
- the engine's `worker`, `summary`, and `outbox` status fields are background **threads**, not OS processes. Their liveness does not prove successful distillation, completed indexing, or successful publication. Do not enumerate processes to "fill in" these fields, and do not require all three to be alive as a universal gate;
- service health must verify the correct service owner, endpoint, and relevant liveness signals. Only an actual distillation receipt/result proves distillation, and only an actual remote reference proves community publication.

<a id="distillation"></a>
## Distillation inputs and outcomes

### Public schema

The public `knowledge_distill` input contract in `mindie-agent-codex 0.1.32` is:

| Field | Contract |
| --- | --- |
| Required top-level | `inputs`, `task_state` |
| Optional top-level | `domain`, `related_refs`, `proposal` |
| Required per input item | `kind`, `outcome`, `source_locator`, `content`, `evidence_refs` |
| Optional per input item | `repetitions`, integer ≥ 1 |
| Allowed `kind` values | `experiment_ledger`, `run_manifest`, `authorized_transcript`, `ecosystem_repo`, `hardware_spec`, `ablation_receipt` |
| Allowed `outcome` values | `observed`, `verified`, `compile_failed`, `infra_failed`, `measurement_invalid`, `in_flight` |
| Allowed `task_state` values | `in_flight`, `verified_milestone`, `completed` |

Do not pass conceptual fields such as `milestone`, `evidence`, or `proposed_rule` as undeclared top-level arguments. When supplied, `proposal` must be the structured `mindie-distill-decision/1` contract, not a free-form rule string; the transport's internal support for additional fields does not expand Codex's public schema.

### Semantics of `in_flight` and `noop`

The inspected `mindie-knowledge 0.13.19` does **not** return `noop` for every `in_flight` task: a **substantive, verified milestone within an unfinished task** can still be admitted. Empty, unverified, or trivial input can produce `noop`. A `Stop` event does not establish task completion.

Therefore:

- `task_state="in_flight"` means the task is unfinished, not automatically "distillation refused";
- `outcome="in_flight"` is a per-input state and does not replace the top-level `task_state`;
- `noop` is not a successful publication and does not mean a knowledge change was generated or merged; it means only that this invocation had no admissible substantive change;
- do not treat task completion as a mandatory ritual before distillation; invoke it when a distillable milestone is reached.

### Timeouts, paid calls, and external writes

- The inspected default RPC budget is **420 seconds**; the Codex adapter adds helper allowance up to **450 seconds**.
- An outer invocation must reserve additional cleanup allowance beyond that. Do not use 450 seconds as the total timeout, and do not reuse the query's 45-second budget.
- Never write `timeout N cmd || cmd` or automatically resend after a timeout.
- Distillation may trigger paid model calls, and publication may produce Git/remote writes. When the result is uncertain, retain the "sent, outcome unknown" state and reconcile read-only first; never blindly replay a potentially paid distillation or an uncertain external write.
- Record a completed primary result separately from a cleanup failure. A cleanup error must not rewrite a completed distillation as failed or trigger a second paid call.

<a id="failure-recovery"></a>
## Recovery by failure stage

The first recovery step is to identify the failing layer, not to retry immediately. Different stages can all surface as `invalid_arguments` or `connection_unavailable`, yet require different safe actions.

| Failure stage | Typical visible result | What it establishes | Safe recovery |
| --- | --- | --- | --- |
| Configuration/binding | Missing config, malformed JSON, empty `python` or `runtime_scripts` | No knowledge call has started | Fix `MINDIE_AGENT_CONFIG` or the default config; re-read the pair from the same object and do not fall back to ambient Python |
| Interpreter/packages | Missing interpreter, import failure, wrong package version | Runtime identity or dependencies are invalid | Check `sys.prefix` and package versions with the configured interpreter plus `-I`; build a fresh candidate through preparation if needed, do not copy scripts elsewhere |
| argv | Extra argument or missing operation | The request was not dispatched | Use `describe` or a single `<operation>`; do not add unsupported `--json`. `--input-file` is merged on `main` (`#118`, `d413a20`) but **unreleased in formal `0.1.32`**, so `0.1.32` installations must still use stdin and wait for a formal release `> 0.1.32` |
| Input encoding | `invalid_arguments`, Chinese turned into `?`, UTF-16LE file | Bytes were corrupted before Python saw them, or decoding failed | Use the UTF-8 invocation above (pipe when console-attached, `ProcessStartInfo` when consoleless); verify the bytes sent and BOM presence; do not rely on `PYTHONUTF8` to repair already-corrupted input |
| Input size/empty/JSON | `invalid_arguments`, no dispatch | Empty input, over 1 MiB, or malformed JSON | Check for empty input, truncation, and byte length; regenerate valid JSON; do not guess "backend failure" |
| Schema | `invalid_arguments`, missing/unknown fields | The request parsed but failed the domain schema | Correct it against the public fields and allowed values above; do not pass conceptual or internal fields |
| Session authorization | `knowledge_inactive` | The current session lacks the native grant, or identity/config/route does not match | Manually invoke `/mindie-agent` in the current session; confirm the current native tool environment; do not fabricate `CODEX_THREAD_ID` |
| Domain routing/lease | `lease_required` | Default-session authorization exists, but the selected domain lacks its own lease | Verify the selected `domain`, routed target, and lease state; do not copy another domain's lease |
| Contribution consent/scope | Distillation refused for authorization or scope | A lease may exist, but consent or scope is not satisfied; `noop` alone does not prove the cause | Check the persistent contribution switch and authorized project scope; never disable protections or force out-of-scope projects to pass a check |
| Service launcher | Registration/recovered launch rejected (for example `windowless_interpreter_*`); visible console window | Established only when registration/recovered launch is rejected with `windowless_interpreter_*` and PE header inspection confirms a missing, corrupt, or non-GUI entry binary; a visible console window alone can also come from a valid GUI parent spawning an unhidden console child (P1.5), so process-tree and subprocess-hiding diagnosis must come before rebuilding a candidate | Confirm the launcher-specific error and the entry's actual PE subsystem before rebuilding; a visible window alone first requires process-tree and subprocess-hiding diagnosis. If repair is required, build a fresh GUI candidate per "Windows service launcher" and hand off atomically; never patch PE bytes or overwrite the interpreter |
| Transport/timeout | `connection_unavailable`, timeout, connection reset | The label alone does not prove that the request was never sent or the service never started | Reconcile existing receipts, service ownership, and remote state read-only; allow one bounded retry only when the request provably never left and the operation is read-only and idempotent |
| Uncertain distillation result | Timeout, disconnect, missing receipt | A paid call or external write may have occurred | Preserve the original operation ID and uncertainty, reconcile read-only, and never automatically replay distillation or publication |

### Four recovery boundaries

1. **Recover by stage**: encoding problems are not fixed by activation, authorization problems are not fixed by reinstall, and launcher problems are not fixed by repeated activation.
2. **Preserve the original failure**: record the original error, versions, request properties, and confirmed facts; a replacement diagnosis must not erase the first failure.
3. **Pause only dependent actions**: when the service launcher fails, non-knowledge tools and actions that do not depend on that service remain usable; one knowledge-capability failure must not stall the whole task.
4. **Never replay uncertainty**: `connection_unavailable`, timeouts, and missing receipts do not automatically mean "nothing happened". For potentially paid or external-write operations, reconcile read-only before deciding.

<a id="evidence"></a>
## Validation record

A public or team-shared validation record should be sanitized first, then retain enough properties to reproduce the boundary. Suggested checklist:

- **Versions and provenance**: `mindie-agent-codex` version and commit, native Codex version, Windows build, Windows PowerShell 5.1 or `pwsh` version, Python distribution/version, `uv` version, installed `mindie-knowledge` version; explicitly write "unknown" for missing facts.
- **Configuration binding**: whether `MINDIE_AGENT_CONFIG` or the default path was used; whether `python` / `runtime_scripts` came from the same configuration object; replace usernames and home directories with placeholders such as `<config>` and `<runtime-python>`.
- **Interpreter identity**: `sys.prefix` under `-I`, actual `mindie-knowledge` version, and origin of `knowledge_cli.py`; "the interpreter exists" is not enough.
- **Input properties**: operation name, argv shape, input byte count, BOM presence, whether it was UTF-16LE/GBK, and whether ASCII `?` substitution occurred; do not save the original query text or full conversation.
- **Session and authorization**: whether the current session was activated; actual `knowledge_inactive` / `lease_required` result; whether contribution switch and scope were satisfied; do not record thread IDs, tokens, or internal verification fields.
- **Service and launcher**: candidate generation, actual entry PE `Subsystem` value, registration and recovered-launch results, and whether a visible window or `conhost.exe` appeared; do not publish full user paths.
- **Operation outcomes**: whether the query succeeded and which public unit IDs were returned; whether distillation produced `noop` or a `reviewed_change`; whether publication has a remote PR/commit reference; never record `noop` as a successful publication.
- **Acceptance gaps**: which steps were not executed (for example, no Windows desktop acceptance, no `powershell.exe` test, no old-binding retirement check). List skips honestly; a zero exit code is not behavioral proof.

A sanitized record template:

```text
codex_plugin: mindie-agent-codex 0.1.32 (<commit>)
native_codex: <version or unknown>
windows: <build or unknown>
shell: Windows PowerShell 5.1 / pwsh <version or unknown>
python: <distribution/version or unknown>
uv: <version or unknown>
knowledge_installed: <version or unknown>
config_source: MINDIE_AGENT_CONFIG / default
runtime_pair_same_config: yes/no
sys_prefix: <redacted>
operation: knowledge_query / knowledge_distill
argv_shape: <one operation> / <other>
input_bytes: <n>
input_encoding: utf-8 / utf-8-bom / utf-16le / unknown
ascii_replacement_seen: yes/no/unknown
session_grant: active/inactive/unknown
authorization_result: success / knowledge_inactive / lease_required / other
service_entry_subsystem: 2 / 3 / missing / unknown
desktop_acceptance: performed / not performed
notes: <sanitized>
```

Do not publish usernames or home directories, full configuration paths, tokens/cookies, thread IDs, original queries or conversations, tool payloads, or unsanitized remote addresses or credentials. Diagnostic logs may remain in a private local directory, but public reports should retain only sanitized conclusions.

<a id="implementation"></a>
## Implementation status

### Status table

| Capability | Implementation status | Availability in `mindie-agent-codex 0.1.32` | Verification and acceptance boundary |
| --- | --- | --- | --- |
| UTF-8 stdin CLI invocation | Released with `0.1.32` | Available | Derived from inspected interfaces; this review performed no Windows desktop acceptance |
| `--input-file <path>` | Merged to `main` ([#118](https://github.com/mindie-agent/mindie-agent-codex/pull/118), `d413a20`) | **Unreleased**; unavailable in `0.1.32` | Verified in hosted `windows-latest` PowerShell 5.1 CI ([`adapter (windows-latest)`](https://github.com/mindie-agent/mindie-agent-codex/actions/runs/43748768061/job/132920529110)), `run 43748768061`; interactive Windows desktop acceptance not performed |
| Structured `stage` / `reason` | Merged to `main` ([#118](https://github.com/mindie-agent/mindie-agent-codex/pull/118), `d413a20`) | **Unreleased**; `0.1.32` still collapses CLI input errors into `invalid_arguments` | Verified by unit and CI suites |
| PE validation during registration and recovered launch | Exists in shared Knowledge (inspected `0.13.19`) | Available; Codex `0.1.32` declares baseline `0.13.17` | The contributor's installed revision is unknown |
| Candidate-stage `require_windows_service` validation | Merged to `main` ([#118](https://github.com/mindie-agent/mindie-agent-codex/pull/118), `d413a20`) | **Unreleased**; the `0.1.32` guarantee remains the PE check during registration and recovered launch | Verified across fresh/cached preparation and pre-retirement activation in hosted `windows-latest` CI; interactive Windows desktop Task Scheduler acceptance not performed |
| Direct import of `knowledge_cli.invoke(...)` | Explicitly rejected | Not applicable | Wrong module ownership, does not bypass `CODEX_THREAD_ID` or authorization, and is not a stable API |
| PE `Subsystem 3 → 2` byte-patching | Explicitly rejected | Not applicable | Violates P1.6, breaks signature/policy integrity, and cannot prove venv dispatch or desktop behavior |
| Windows desktop end-to-end acceptance of this runbook | Not performed | Not applicable | Interface review must not be presented as field acceptance |

### Companion fixes and remaining gaps

- **Codex adapter**: the stdin contract is preserved, and explicit UTF-8 file input; pre-dispatch distinction of argv, empty input, oversize input, encoding, JSON, object-shape, and schema failures; and allowlisted `stage` / `reason` in `mcp_gate` without leaking payloads, paths, or arbitrary exception text were merged to `main` in [#118](https://github.com/mindie-agent/mindie-agent-codex/pull/118) (`d413a20`).
- **Candidate preparation/validation**: pass "requires Windows service capability" as an explicit mode into the candidate probe and reuse the shared PE check, merged to `main` in [#118](https://github.com/mindie-agent/mindie-agent-codex/pull/118) (`d413a20`); `bootstrap.py`, `component_update.py`, and `release_activation.py` perform that validation before publishing a service-required candidate or retiring an old service, without starting a service, changing consent, or registering a task for validation.
- **Tests**: CLI byte-boundary and exclusive regular-file `--input-file` tests, `argv` / schema `stage` / `reason` distinctions, and the hosted `windows-latest` `powershell.exe` 5.1 round trip with UTF-8 BOM handling are merged and passing in CI; **interactive Windows desktop Task Scheduler acceptance remains unperformed**.
- **Documentation**: this bilingual runbook and its cross-links in the indexes, lifecycle, historical guardrails, and knowledge-system §4.1; never describe a fix merged on `main` but unreleased in `0.1.32` as existing `0.1.32` functionality.

Until a formal `mindie-agent-codex` release `> 0.1.32` is published and interactive Windows desktop acceptance is completed, formal `0.1.32` installations do not yet have `--input-file`, structured CLI input `stage` / `reason`, or candidate-stage launcher validation. A documentation merge does not mean those capabilities are available in `0.1.32` field installations, nor that the runtime defect has shipped in a formal release.

## Related documents

- [Harness Boundary & Lifecycle](harness-boundary-and-lifecycle.en.md) (session authorization and the §2.4 boundary)
- [Historical Postmortems & Guardrails](historical-issues-and-guardrails.en.md) (P1.6, P2.6)
- [Knowledge & Experience System](knowledge-system.en.md) (§4.1 distillation triggers and evidence)
- [Source Rebuild & Recovery](source-rebuild-contract.en.md)
- [PR #357](https://github.com/mindie-agent/mindie-agent/pull/357) (`YzTongNiar`'s Windows field report)

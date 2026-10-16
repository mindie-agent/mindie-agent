# Harness Boundary & Lifecycle Contract

[中文](harness-boundary-and-lifecycle.md) · [Back to Documentation Index](README.en.md)

Current contract, revised 2026-10-16. Governed by the [Nine Design Principles](design-principles.en.md) and serving ordinary native tasks defined in [Architecture & Domain Boundaries](architecture.en.md). For first-release verification evidence across the six Codex/Claude Code × macOS/native Windows/WSL environments, known host limitations, and repository publication states, see the [`0.0.1` Release Record](releases/0.0.1.en.md).

---

## Responsibilities and Normal Usage

Each Harness adapter owns native task identity, trusted transcript discovery, public message projection, and native model invocation. The host's native plugin manager owns plugin installation and install records, while a shared selector picks the highest ordinary Release compatible with the installed Harness version range. Adapters provide release manifests, locked dependencies, and stable entrypoints bound to deterministic runtimes and shared service configurations. The shared `knowledge` component owns neutral authorization/cursor/queue state, redaction, navigation indexing coordination, retrieval, publication receipts, and recovery. `remote-dev` owns remote execution and artifacts; `diagnostics` owns bounded local logs and opt-in fault reporting. `coordinator` and `npu-top` intervene only when a task explicitly needs them.

MindIE Agent introduces no custom unified Harness, domain router, second publication database, or general task platform. Users continue working in their own business repositories and native sessions. Optional knowledge reads and remote tools do not depend on capture activation; querying, feedback, status checks, and closing steps are never mandatory daily prerequisites.

---

## Identity, Consent, and Scope

Contribution choice, public destination repository, account, and project scope are persistent user settings; starting a new task, restarting, or upgrading never triggers a second authorization prompt. Missing configuration, scope mismatch, explicit disablement, and corrupted state are reported as distinct outcomes. Legacy `read-only` or `later` declined intents continue to be honored as disabled and are never silently upgraded to public contribution. Independent fault-reporting consent is never conflated with knowledge-contribution consent.

Authorization settings are decoupled from code installation identity: reloading or updating the plugin retains existing consent and project scope, and explicit disablement always remains in force. First-time setup asks only for genuinely missing fields and supports incremental updates without reinstalling or hand-editing JSON files.

Every native task or fork derives its material ownership from verified host identity and transcript headers—never by guessing from the newest session, matching `cwd`, similar prompts, or another task's timestamps. The capture lower bound comes from valid consent, task/fork creation time, and explicit disable windows. Only the explicitly named transcript is read; historical transcripts are never scanned automatically. Explicit history import reuses the exact same projection, redaction, indexing, and package protocol.

Every external write re-reads current authorization. Revocation halts unsent actions; confirmed pushes and uncreated PRs are recorded separately. If a write receipt is lost, the state remains `unknown` with its original operation identity and must be reconciled read-only before any further write—never retried as if unsent. Re-enabling admits only subsequent authorized material without back-scanning conversations from the disabled window.

---

## Body Projection and Model Invocation

The adapter retains ordered user input, public assistant progress, and final answers while excluding tool payloads, hidden reasoning, injected instructions, and duplicate host wrapper events. Mechanical projection performs no semantic shortening or head/tail truncation. Gitleaks and deterministic privacy rules execute before body persistence, model input, and publication. Because pattern rules cannot judge whether proprietary business semantics are safe to publish, explicit project-scope consent remains mandatory.

The complete redacted body is stored as immutable ordered Markdown blocks committed atomically alongside the cursor and valid metadata. LangMem invokes the adapter's lightweight native model to generate block titles/summaries and short task navigation without modifying body text. Each pass processes bounded new blocks and short navigation so long tasks advance through all admitted content without dropping later turns. Navigation indexing is a required step prior to public packaging; if indexing fails, the local body is preserved and the unfinished stage is reported honestly.

Internal indexing model policy belongs to the adapter and adds no user configuration burden. Returned model outputs and token usage are persisted before local application so a local apply error can reuse the saved response without paying for a duplicate model call. Uncertain (`unknown`) or failed paid model calls are never re-submitted automatically. Querying, syncing, package validation, and PR publication invoke no model.

---

## Operation Lifetimes and Error Semantics

Task consent, a single tool call, an MCP connection, a local process tree, and a persistent remote job all have distinct lifetimes. There is no arbitrary default total execution deadline for business work; only caller-specified timeouts bound execution. Silence or long duration does not imply failure—process handles, EOF, SSH transport health, owner exit, and explicit errors govern liveness. Device-lease heartbeats and fencing protect resource ownership and are never treated as business execution timeouts.

Cancellation applies only to the process tree owned by the specific invocation; independent background services and persistent remote jobs are never killed merely because a short launcher exits. Known success, known failure, unsubmitted work, and uncertain external side effects (`unknown`) are represented distinctly. Logging, ledger, or cleanup errors never overwrite a known business outcome or primary error.

For `0.0.1`, MindIE Agent documents and accepts the known OpenAI Codex CLI limitation where interrupting a child agent may not deliver cancellation to a pending tool call, leaving a local helper/SSH process or started remote command running. Main-thread and Claude Code cancellation evidence does not claim that this child boundary is fixed, and the plugin adds no intrusive process-watcher workaround or private Harness patch. Persistent remote jobs continue to stop according to their own `remote-dev` contract.

The Stop Hook performs only fast, durable admission and notifies the existing owner, returning neutral protocol output that never forces another business turn. Hook failures surface via the host's supported warning field, while background stage failures record bounded Agent diagnostics delivered on the next natural capability call.

The full process tree and scratch directory of an indexing operation are owned by the shared execution boundary: Windows uses a named Job Object with kill-on-close, WSL uses transient `systemd` user units (`KillMode=control-group`), and macOS uses a minimal shared owner-pipe helper so that sudden core termination reliably cleans up the entire operation group. See [Native Runtime & Process Reuse](native-runtime-reuse.en.md).

---

## Authoritative State, Recovery, and Garbage Collection

Markdown files are the authoritative body store. SQLite stores essential cursors, queues, consent/identity bindings, and external operation receipts; ReMe is a rebuildable derived index. A missing or corrupted authoritative SQLite database is never treated as a fresh first-time install and can never trigger an empty-snapshot deletion of Markdown bodies or `unknown` receipts. Initialization distinguishes genuinely new state from existing state and validates required tables, columns, and schema versions first.

Only validated authoritative state may drive derived index rebuilds or garbage collection. Candidate corpus sync validates the entire candidate before switching the active snapshot so a truncated tail never leaves a half-written corpus marked as healthy.

Once a confirmed publication receipt is matched in the synced public feed, frozen outbound payloads can be retired while new observations continue to append. Rejected, withdrawn, or conflicting remote content is never resurrected automatically.

---

## Installation, Reload, and Service Ownership

Plugin download, installation, and install records reuse the host's native plugin manager; each Release declares its supported Harness version range (`harness-compatibility.json`), and online checks select the highest compatible ordinary Release. For silent update, short cutover, and failure semantics, see [Release Compatibility & Silent Update](release-compatibility-and-update.en.md).

Plugin entrypoints bind directly to the release's immutable runtime identity installed via `uv` (`--locked --no-editable`) outside disposable host plugin caches. The installation configuration stores a single canonical active binding. Candidate runtimes are prepared and verified outside the active lock; switching acquires the exclusive lock only after confirming the existing service is idle, retiring the old owner and atomically updating the binding. Business operations share the admission lock so concurrent calls and cancellations proceed without contention. Short Stop Hooks enqueue durably without performing network checks or installations.

---

## Verification Boundaries

Acceptance verifies first-turn automatic association, fork/sibling task isolation, consent revocation, long silence, owner termination, transport disconnect, post-outcome bookkeeping failure, missing-DB body preservation, uncertain side-effect reconciliation, and post-upgrade remote job control against real caller-visible outcomes and side effects. Component unit tests, native install/Stop/MCP probes, real SSH/NPU runs, public PR/Bot merges, and cross-task reuse are recorded with their exact commits and scope in the [`0.0.1` Release Record](releases/0.0.1.en.md).

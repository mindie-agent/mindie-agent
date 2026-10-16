# Harness Boundary & Task Lifecycle

[中文](harness-boundary-and-lifecycle.md) · [Back to Documentation Center](README.en.md)

This document explains how responsibilities are divided between MindIE Agent's native Harness plugins (**Claude Code**, **OpenAI Codex CLI**, **Kimi Code**) and its shared runtime components, as well as how task identity, user consent, long-running jobs, and local data recovery work in practice.

- Governed by: [Engineering Design Principles](design-principles.en.md) · [Architecture & Module Boundaries](architecture.en.md)
- Release Verification Details: [`0.0.1` Release Record](releases/0.0.1.en.md)

---

## 1. Division of Responsibilities

MindIE Agent does not invent a proprietary chat UI or force you into a custom task runner. Instead, it plugs directly into your existing coding CLI with clean boundaries across layers:

| Layer / Module | What It Owns | What It Never Does |
| --- | --- | --- |
| **Host Native Plugin Manager** | Downloading, installing, and recording installed plugin packages | Does not replace MindIE Agent's SemVer host-compatibility check |
| **Harness Plugin Adapters** (`mindie-agent-cc` / `-codex` / `-kimi`) | Verifying native task identity, locating trusted transcripts, extracting public dialogue, invoking the host's lightweight native model, and shipping locked dependencies (`uv.lock`) | Never maintains a second knowledge database or duplicate process-supervision state machine |
| **Shared Knowledge Engine** (`knowledge`) | Managing consent & cursors, running deterministic privacy redaction, coordinating block navigation indexing, serving two-layer search, and tracking PR receipts & recovery | Never imports host-private session tables or guesses task ownership from working directories or timestamps |
| **Remote & Diagnostics Components** (`remote-dev` / `diagnostics`) | Providing standalone SSH remote execution/background job management, bounded local logs, and opt-in fault reporting | Never depends on experience capture being enabled, and never truncates user job outputs |

In everyday use, knowledge search and `remote-dev` remote tools work on demand regardless of whether experience capture is turned on.

---

## 2. Task Identity, User Consent, and Capture Scope

### 2.1 Configure Consent Once—Persist Across Updates
- **Persistent user preferences**: Your contribution choice, public destination repository, GitHub account, and authorized project scope are saved as persistent user settings decoupled from the installed code version.
- **No re-prompting on upgrade**: Starting a new session, restarting your terminal, or updating the plugin preserves your existing settings. If you previously disabled sharing, updates keep it disabled and never silently opt you back in.
- **Incremental configuration**: First-time setup asks only for missing fields, and you can update project scope or toggle sharing at any time without reinstalling or hand-editing JSON files.

### 2.2 Exact Task Attribution & Capture Boundaries
- **Zero guessing**: Material ownership for every native session or child task (fork) comes strictly from verified host session IDs and transcript headers—never from "most recently modified file," matching `cwd`, or similar prompt text.
- **Clear time boundaries**: Only turns generated after consent is enabled and within an authorized project path are captured. Disabling sharing immediately cancels unsent queue items; re-enabling captures only new turns going forward without back-scanning conversations from the disabled period.

### 2.3 Protecting Uncertain (`unknown`) External Writes
- Every external write (such as pushing a branch or opening a knowledge PR) re-verifies current consent before executing.
- If a network glitch leaves an external write without a receipt, it is recorded as `unknown` with its original operation identity. Before any future write, the runtime reconciles read-only against the remote repository rather than blindly retrying as if the operation had never been sent.

---

## 3. Conversation Extraction & Small-Model Indexing

- **Deterministic public extraction**: Only ordered user input, public assistant progress, and final answers are kept. Raw tool payloads, hidden reasoning traces, system prompts, and duplicate host wrapper events are stripped without truncating long tasks.
- **Redaction first**: Gitleaks and deterministic privacy rules run before any bytes touch disk, enter the indexing model, or leave the machine.
- **Small models write navigation only**: Each adapter uses its lightweight native model (via LangMem) solely to generate block titles, search summaries, and the `PACKAGE.md` outline. Model outputs and token usage are persisted to disk before local application so that any local apply error can reuse the saved response without paying for a second model call.

---

## 4. Operation Lifetimes, Cancellation, and Error Delivery

1. **Five independent lifetimes**:
   - User consent, a single tool call, an MCP connection, a local helper process tree, and a persistent remote job (`remote-dev`) each have their own distinct lifetime.
   - **No arbitrary global business timeout**: Long remote builds or NPU benchmarks continue running as long as the process and transport are healthy; only caller-requested timeouts end execution.
2. **Targeted cancellation without collateral damage**:
   - Cancelling an in-flight tool call terminates only the process tree owned by that call; background services and explicitly launched persistent remote jobs are never killed just because a short launcher exits.
   - *Documented host limitation in `0.0.1`*: When OpenAI Codex CLI interrupts a child agent (`spawn_agent`), Codex may not deliver a cancellation signal to an in-flight MCP tool call. MindIE Agent documents this upstream limitation transparently without adding intrusive process-hunting workarounds; persistent remote jobs remain explicitly controllable via `remote-dev` (`job_cancel`).
3. **Reliable cross-platform process-tree cleanup**:
   - Background indexing process trees are governed by OS-native primitives: Windows uses a named Job Object (`KILL_ON_JOB_CLOSE`), WSL uses transient `systemd` user units (`KillMode=control-group`), and macOS uses a lightweight `owner-pipe` helper so that even a sudden `SIGKILL` of the parent worker cleanly reclaims all descendant processes. See [Native Runtime & Process Reuse](native-runtime-reuse.en.md).

---

## 5. Local State Protection & Atomic Idle Updates

- **Markdown is the authoritative store**:
  - Markdown block files on disk are the sole source of truth for content; SQLite stores cursors, queues, and receipts; ReMe is an in-memory index rebuildable from Markdown at any time.
  - If SQLite is missing or corrupted on startup, the runtime reports a clear error while preserving all existing Markdown files and `unknown` receipts—never mistaking corruption for a fresh install.
- **Single canonical binding & atomic idle cutover**:
  - Plugin runtimes are installed via `uv sync --locked --no-editable` into a stable application data directory outside disposable host caches, maintaining one canonical active binding.
  - Silent background updates prepare new releases outside the lock and switch atomically only when the service is idle, requiring no manual session reload. See [Release Compatibility & Silent Update](release-compatibility-and-update.en.md).

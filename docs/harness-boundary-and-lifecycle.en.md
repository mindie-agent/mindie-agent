# Harness Boundary & Task Lifecycle

[中文](harness-boundary-and-lifecycle.md) · [Back to Documentation Center](README.en.md)

This document explains how responsibilities are divided between MindIE Agent's native Harness plugins (**Claude Code**, **OpenAI Codex CLI**, **Kimi Code**, **DeepSeek Harness**, **Google Antigravity**, **Tencent WorkBuddy**, **OpenCode**) and its shared runtime components, as well as how task identity, user consent, long-running jobs, and local data recovery work in practice.

- Governed by: [Engineering Design Principles](design-principles.en.md) · [Architecture & Module Boundaries](architecture.en.md)
- Release Records: [Release Records & Roadmap](README.en.md#release-records--roadmap)

---

## 1. Division of Responsibilities

MindIE Agent does not invent a proprietary chat UI or force you into a custom task runner. Instead, it plugs directly into your existing coding CLI with clean boundaries across layers:

| Layer / Module | What It Owns | What It Never Does |
| --- | --- | --- |
| **Host Native Plugin Manager** | Downloading, installing, and recording installed plugin packages | Does not replace MindIE Agent's SemVer host-compatibility check |
| **Harness Plugin Adapters** (`mindie-agent-cc` / `-codex` / `-kimi` / `-dsh` / `-agy` / `-wb` / `-oc`) | Verifying native task identity, locating trusted transcripts, extracting public dialogue, invoking the host's lightweight native model, shipping locked dependencies (`uv.lock`), and running silent background updates | Never maintains a second knowledge database or duplicate process-supervision state machine |
| **Shared Knowledge Engine** (`knowledge`) | Managing consent & cursors, running deterministic privacy redaction, coordinating block navigation indexing, serving `TechnicalTokenizerV1`-based ReMe search, and tracking PR receipts & recovery | Never imports host-private session tables or guesses task ownership from working directories or timestamps |
| **Remote & Diagnostics Components** (`remote-dev` / `diagnostics`) | SSH file/command execution and background jobs, bounded local diagnostic logs, and opt-in fault reporting governed by the unified contribution switch | SSH operations and local logs work independently of the contribution switch; outgoing fault reports strictly obey that switch and never truncate remote job outputs |

In everyday workflows, capabilities split cleanly along two boundaries:
- **Manual `/mindie-agent` Activation for the Knowledge Flywheel**: Invoke `/mindie-agent <problem description>` once in the current chat (or `$mindie-agent` in Codex; DSH uses its native `/mindie-agent` gesture) whenever you want Ascend domain knowledge, historical troubleshooting experience, and Skill guidance. Activation is strictly session-scoped: subsequent turns in the same chat retain the grant until explicitly deactivated, while installation, contribution consent, tool discovery, or topic keywords never auto-activate it—and new chats, forks, and subagents never inherit an active grant.
- **Deterministic Engineering Tools Ready by Default**: Installed `remote-dev`, `coordinator` inventory and leases, `profiler` capture and trace analysis, `sim` performance modeling, `debugger` target workload triage/debugging, and local `diagnostics` / status tools expose their names, descriptions, and schemas through native MCP without invoking `/mindie-agent` (existing permissions, NPU leases, and outbound consent still apply; `npu-top` runs as a human-facing dashboard outside the default Agent MCP catalog).

The dividing line is **whether an operation consumes or records knowledge and experience context**: reading hardware specs, analyzing profiling traces, running causal simulations, and checking local status are ordinary deterministic tool calls, whereas retrieving `L1–L4` units, expanding citations, recording votes, distilling experience, syncing corpora, and capturing `Stop` transcripts belong to the manually enabled knowledge flywheel (even when their underlying algorithms are deterministic). Status tools return objective runtime state without injecting onboarding prompts or contribution nudges.

In chats where `/mindie-agent` has not been invoked, default MCP discovery omits `knowledge` tool names, descriptions, and parameter schemas altogether—never injecting knowledge Skills, flywheel instructions, or "not yet enabled" reminders (merely rejecting calls at execution time is insufficient; the default catalog itself stays clean). Even if another chat on the same machine has activated `/mindie-agent`, the runtime verifies the current session's explicit grant before every knowledge call so another session's activation never leaks a shared catalog (see the [Codex 0.1.8 native acceptance record](releases/codex-0.1.8-native-acceptance.json)).

---

## 2. Task Identity, User Consent, and Capture Scope

### 2.1 Configure Consent Once—Persist Across Updates
- **Persistent user preferences**: Your contribution choice, public destination repository, GitHub account, and authorized project scope are saved as persistent user settings decoupled from the installed code version.
- **No re-prompting on upgrade**: Starting a new session, restarting your terminal, or updating the plugin preserves your existing settings. If you previously disabled sharing, updates keep it disabled and never silently opt you back in.
- **Incremental configuration**: First-time setup asks only for missing fields, and you can update project scope or toggle sharing at any time without reinstalling or hand-editing JSON files.

### 2.2 Exact Task Attribution & Capture Boundaries
- **Zero guessing**: Material ownership for every native session or child task (fork) comes strictly from verified host session IDs and transcript headers—never from "most recently modified file," matching `cwd`, or similar prompt text.
- **Clear time boundaries**: Only turns generated inside a manually `/mindie-agent`-activated session after both session activation and contribution consent (`max(created_at, activated_at)`) and within an authorized project path are captured. Disabling sharing immediately cancels unsent queue items; re-enabling captures only new turns going forward without back-scanning conversations from the disabled or unactivated period.

### 2.3 Stable GitHub Channel (`gh`) & Protecting Uncertain (`unknown`) Writes
- **Unified `gh` authenticated transport (Hard Requirement) & Two-Stage On-Demand Forking**: All GitHub API calls and remote Git branch pushes run through the authenticated `gh` CLI (`GhTransport` invokes `gh api`, and Git binds `!gh auth git-credential`), keeping tokens strictly inside `gh`'s managed credential store or environment variables rather than CLI flags, logs, or config files. Installing a plugin never requires starring a repository or creating a Fork upfront; only when community contribution is explicitly enabled does the runtime create or reuse a personal Fork of the target knowledge repository (`<GH_USER>/<repo>`), while starring remains completely optional. If `gh` is missing or unauthenticated, outbound operations fail visibly rather than degrading silently.
- **Re-verify consent before every write**: Every external write (such as pushing a branch or opening a knowledge PR) re-verifies current consent before executing.
- **Read-only reconciliation for `unknown` outcomes**: If a network glitch leaves an external write without a receipt, it is recorded as `unknown` with its original operation identity. Before any future write, the runtime reconciles read-only against the remote repository rather than blindly retrying as if the operation had never been sent.

---

## 3. Conversation Extraction & Small-Model Indexing

- **Deterministic public extraction**: Only ordered user input, public assistant progress, and final answers are kept. Raw tool payloads, hidden reasoning traces, system prompts, and duplicate host wrapper events are stripped without truncating long tasks.
- **Redaction first**: Gitleaks and deterministic privacy rules run before any bytes touch disk, enter the indexing model, or leave the machine.
- **Small models write navigation only**: Each adapter uses its lightweight native model solely to generate block titles, search summaries, and the `tasks/<32-char task hash>/index.md` outline (top-level `mindie-material-task/1` manifest embedding `mindie-entry/3` navigation) for 16KB-chunked blocks (`tasks/<32-char task hash>/blocks/<64-char block hash>.md`). Model outputs and token usage are persisted to disk before local application so that any local apply error can reuse the saved response without paying for a second model call.

---

## 4. Operation Lifetimes, Cancellation, and Error Delivery

1. **Five independent lifetimes**:
   - User consent, a single tool call, an MCP connection, a local helper process tree, and a persistent remote job (`remote-dev`) each have their own distinct lifetime.
   - **No arbitrary global business timeout**: Long remote builds or NPU benchmarks continue running as long as the process and transport are healthy; only caller-requested timeouts end execution.
2. **Targeted cancellation without collateral damage**:
   - Cancelling an in-flight tool call terminates only the process tree owned by that call; background services and explicitly launched persistent remote jobs are never killed just because a short launcher exits.
   - *Documented upstream host limitation*: When OpenAI Codex CLI interrupts a child agent (`spawn_agent`), Codex may not deliver a cancellation signal to an in-flight MCP tool call. MindIE Agent documents this upstream limitation transparently without adding intrusive process-hunting workarounds; persistent remote jobs remain explicitly controllable via `remote-dev` (`job_cancel`).
3. **Reliable cross-platform process-tree cleanup**:
   - Background indexing process trees are governed by OS-native primitives: Windows uses a named Job Object (`KILL_ON_JOB_CLOSE`), WSL uses transient `systemd` user units (`KillMode=control-group`), and macOS uses a lightweight `owner-pipe` helper so that even a sudden `SIGKILL` of the parent worker cleanly reclaims all descendant processes. See [Native Runtime & Process Reuse](native-runtime-reuse.en.md).

---

## 5. Local State Protection & Atomic Idle Updates

- **Markdown is the authoritative store**:
  - Markdown files on disk (`tasks/<32-char task hash>/index.md` and `blocks/<64-char block hash>.md`, paired with local `current.json` dual-channel pointers) are the sole source of truth for content; SQLite stores cursors, queues, and receipts; ReMe (`TechnicalTokenizerV1` BM25 + `StrictFileGraph` + citation lineage merging, `blocks.sqlite3` incremental checkpoint) is a derived index rebuildable from Markdown at any time.
  - If SQLite is missing or corrupted on startup, the runtime reports a clear error while preserving all existing Markdown files and `unknown` receipts—never mistaking corruption for a fresh install.
- **Single canonical binding & atomic idle cutover**:
  - Plugin runtimes are installed via `uv sync --locked --no-editable` into a stable application data directory outside disposable host caches, maintaining one canonical active binding.
  - Silent background updates prepare new releases outside the lock and switch atomically only when the service is idle, requiring no manual session reload. See [Release Compatibility & Silent Update](release-compatibility-and-update.en.md).

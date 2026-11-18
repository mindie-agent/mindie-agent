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
| **Thin Harness Plugin Adapters** (`mindie-agent-cc` / `-codex` / `-kimi` / `-dsh` / `-agy` / `-wb` / `-oc`) | At most **`1,500` lines** of host-protocol glue per plugin: native wire manifests, a `< 120`-line hook/MCP launcher, host transcript parser, `host_adapter.py`, and a thin `setup.py`; process supervision, MCP routing, `mindie_doctor`, sharing consent, and runtime updates are all delegated to `mindie-harness`, with locked dependencies (`uv.lock`) | Never duplicates process supervision, MCP gateway routing, or updater state machines |
| **Shared Host Substrate** (`harness` / `mindie-harness`) | Cross-platform windowless process & nested Win32 Job supervision, deterministic Seed (`mindie-harness-seed.pyz`), `Active + Rollback` (`<= 2`) `.inuse`-leased atomic updates, concurrent zero-binding MCP gateway (`P2.7` / `P2.8`), the unified read-only `mindie_doctor` health check, and single-state `ExperimentLedger` `rsi` optimization loop | Never embeds host-specific transcript parsers or creates empty SQLite files on read-only checks |
| **Shared Knowledge Engine** (`knowledge`) | Pure knowledge capabilities: managing consent & cursors, running deterministic privacy redaction, coordinating block navigation indexing, serving `TechnicalTokenizerV1`-based ReMe & `L1–L4` search, and tracking PR receipts & recovery | Never imports host-private session tables or guesses task ownership from working directories or timestamps |
| **Remote & Diagnostics Components** (`remote-dev` / `diagnostics`) | SSH file/command execution and background jobs, bounded local diagnostic logs, and opt-in fault reporting governed by the unified contribution switch | SSH operations and local logs work independently of the contribution switch; outgoing fault reports strictly obey that switch and never truncate remote job outputs |

In everyday workflows, capability readiness and privacy boundaries stay clean and ceremony-free:
- **Silent Default-On Across All Seven Hosts (Zero Slash Commands)**: While the plugin is enabled on Claude Code, Codex, Kimi, DSH, Google Antigravity, WorkBuddy, or OpenCode, all `remote-dev`, deterministic engineering tools (`coordinator`, `profiler`, `sim`, `debugger`, `diagnostics`, `npu-top`), and graded knowledge tools (`knowledge_query`, `knowledge_explain`, `knowledge_feedback`, `knowledge_distill`, `knowledge_sync`) execute directly over standard zero-binding MCP `tools/call` across main chats, subagents, forks, and scheduled automations—**requiring neither slash-command activation nor host-private `_meta`, `PreToolUse` nonces, or `context_file`** (physical NPU/port exclusivity is enforced by remote `HostQueue` `lease_id` + `fence_token`).
- **Clean On-Demand Runtime `SKILL.md` Routing**: Runtime `SKILL.md` loads silently by semantic match only when working on Ascend tasks, leaving non-Ascend coding untouched; one-time installation, workspace setup, and GitHub authentication docs live exclusively under `docs/install/` outside runtime `skills/`.
- **Double-Bounded Opt-In Experience Capture**: Status tools return objective runtime state only; background `Stop` transcript capture runs strictly when the privacy mode is `contribute` or `local-only` **and** `cwd` matches an authorized `project_roots` path (`read-only`/`disabled` and unauthorized directories exit in `< 100ms` with zero SQLite writes). Everything captured under `local-only` stays local and is never exported.

---

## 2. Task Identity, User Consent, and Capture Scope

### 2.1 Configure Consent Once—Persist Across Updates
- **Persistent user preferences**: Your three-tier privacy mode (`contribute` / `local-only` / `read-only`), public destination repository, GitHub account, and authorized project scope are saved as persistent user settings decoupled from the installed code version.
- **No re-prompting on upgrade**: Starting a new session, restarting your terminal, or updating the plugin preserves your existing settings. If you previously disabled sharing, updates keep it disabled and never silently opt you back in.
- **Incremental configuration**: First-time setup asks only for missing fields, and you can update project scope or toggle sharing at any time without reinstalling or hand-editing JSON files.

### 2.2 Exact Task Attribution & Capture Boundaries
- **Zero guessing**: Material ownership for every native session or child task (fork) comes strictly from verified host session IDs and transcript headers—never from "most recently modified file," matching `cwd`, or similar prompt text.
- **Clear time boundaries**: Only turns generated while the privacy tier is `contribute` or `local-only` and within an authorized `project_roots` path are captured. Switching to `read-only` immediately cancels unsent queue items; re-enabling captures only new turns going forward without back-scanning conversations from the disabled period or unauthorized directories.

### 2.3 Three-Tier Privacy Model (`contribute` / `local-only` / `read-only`) & Stable GitHub Channel (`gh`)
- **Three-tier privacy model**: `choice` in `mindie-consent.json` strictly distinguishes three tiers—`contribute` allows local distillation plus community PRs and allowlisted fault Issues via `gh`; `local-only` allows private local distillation; `read-only` (compatible with the historical `disabled`) disables capture and all outbound traffic, leaving only read-only retrieval and local tools.
- **Capture and publication are decided by two independent predicates**: `allows_capture()` is true only under `contribute` or `local-only` while `cwd` is strictly inside an authorized `project_roots` path; `allows_publication()` is true only under `contribute`. Consequently `Stop` transcript capture runs under both `contribute` and `local-only` (strictly inside `project_roots`), while outbound publication only ever happens under `contribute`.
- **`gh` is required only for `contribute` outbound**: only `contribute` GitHub PRs and fault Issues need a stable authenticated `gh` channel (`GhTransport` invokes `gh api`, and Git binds `!gh auth git-credential`), keeping tokens strictly inside `gh`'s managed credential store or environment variables rather than CLI flags, logs, or config files. **`local-only` and `read-only` work 100% without `gh`**; a missing or expired `gh` only makes `contribute` outbound fail visibly and never blocks installation, capture, or local distillation.
- **Public corpus sync is fully decoupled from `gh`**: public knowledge repositories sync over credential-clean anonymous HTTPS (`GIT_TERMINAL_PROMPT=0` with `-c credential.helper= -c core.askPass= -c http.extraHeader=`), while preserving enterprise `HTTPS_PROXY` and custom CA certificates, so a missing or stale `gh` or credential helper never blocks sync.
- **Two-stage on-demand forking & voluntary starring**: only when the user explicitly selects `contribute` and enables contribution to a target corpus does the runtime create or reuse that corpus's personal Fork (`<GH_USER>/<repo>`); installing a plugin neither requires starring nor pre-forks the main repository, plugin repositories, or all domain corpora.
- **Re-verify consent before every write**: Every external write (such as pushing a branch or opening a knowledge PR) re-verifies current consent and consent revision before executing.
- **Read-only reconciliation for `unknown` outcomes**: If a network glitch leaves an external write without a receipt, it is recorded as `unknown` with its original operation identity. Before any future write, the runtime reconciles read-only against the remote repository rather than blindly retrying as if the operation had never been sent.

### 2.4 Shell Input Encoding, Native Session Identity, Domain Leases, and Windows Service Launchers

- **Shell transport is not native authorization (UTF-8 stdin & atomic generation binding)**: PowerShell's `$OutputEncoding` and `Out-File` / `>` redirection determine only the bytes the CLI receives; non-ASCII JSON piped on Windows PowerShell must set `[Console]::InputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)` over `stdin` rather than UTF-16LE file redirection. Furthermore, active `(python, runtime_scripts)` pairs are bound atomically per generation so stale scripts and upgraded interpreters are never mixed.
- **Native session identity & zero-binding MCP cooperation**: All single-user MCP tools (both deterministic components and `knowledge_*`) execute out of the box over standard `tools/call` without private `_meta` or prior nonces—falling back to a deterministic per-connection session ID and auto-provisioning default leases on demand. When the host provides verified native session tokens such as `CODEX_THREAD_ID`, they are used strictly for exact session attribution and `Stop` capture ownership, never fabricated, copied across sessions, or guessed.
- **On-demand domain leases**: Public retrieval and routine engineering calls work out of the box while the plugin is enabled, auto-provisioning default engine leases on demand, while domain-targeted distillation and authorized capture bindings maintain independent per-domain lease state without cross-contamination.
- **Persistent contribution consent and scope are independent**: `mindie-consent.json`, destination repository, and authorized project scope persist untouched across upgrades and generation GC independently of session authorization and domain leases. When sharing is disabled or capture is out of scope, never cold-start capture merely to satisfy a health check.
- **Unified read-only health check (`mindie_doctor`)**: `mindie_doctor` (`mindie-doctor/1`) inspects runtime generation, privacy tier, default remote NPU, and `gh` channel status strictly read-only; **it creates zero directories and zero SQLite databases on empty installs** (no database/WAL initialization during read-only checks), and under `local-only` / `read-only` an absent `gh` is reported honestly as `optional_unconfigured` rather than a fault.
- **Windows service-launcher capability is independent (dual PE `Subsystem == 2` check)**: a working knowledge API does not imply a working scheduled-task entrypoint. Both registration and recovered launch verify `OptionalHeader.Subsystem == 2` (`IMAGE_SUBSYSTEM_WINDOWS_GUI`) on both `.venv\Scripts\pythonw.exe` and any base `home\pythonw.exe` referenced by `pyvenv.cfg`, rejecting renamed console binaries; API-only success with an unavailable service launcher is reported honestly as service-not-ready rather than bypassed by binary patching.

Historical incident postmortems, authorization matrices, and stage-specific recovery steps are preserved in [Archived Windows Knowledge Invocation & Recovery](archive/knowledge-invocation-recovery.en.md).

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

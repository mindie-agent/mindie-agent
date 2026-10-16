# Native Runtime & Process Reuse

[中文](native-runtime-reuse.md) · [Back to Documentation Center](README.en.md)

This document explains how MindIE Agent applies [Engineering Design Principle 8 (Reuse Proven Mechanisms First)](design-principles.en.md): delegating generic package downloads, virtual-environment locking, and process-tree cleanup to the host CLI, `uv`, and operating-system primitives while keeping custom code focused strictly on Ascend engineering and the experience loop.

---

## 1. Core Architectural Trade-Off: Stop Reinventing Infrastructure

Early on, maintaining custom multi-stage plugin updaters, hand-rolled `venv`/`pip` installers, and PPID-guessing process watchers across adapters created unnecessary complexity and subtle cross-platform edge cases on macOS, native Windows, and WSL.

We consolidated runtime lifecycle management around proven native mechanisms:

| Responsibility | Adopted Native Mechanism | Retained MindIE Agent Scope | Deleted Legacy Code |
| --- | --- | --- | --- |
| **Plugin Download, Install & Registry** | Native Codex / Claude Code plugin managers | Shared SemVer compatibility selector (`harness-compatibility.json`) + pre-release gate | Removed custom multi-stage `auto_update.py` / `updater.py`, dedicated update schedulers, and multi-generation successor chains |
| **Python Dependencies & Isolated Runtime** | `uv sync --locked --no-editable` with committed `uv.lock` | Product combination contract (`product-contract.json`), platform/ABI identity checks, and schema validation | Replaced hand-rolled `venv`/`pip` scripts and loose top-level `requirements.txt` files |
| **Session Lifecycle Hooks** | Native Host Hooks + local SQLite durable admission | Task identity verification, project scope check, cursor advancement, and idempotency | Hooks never block on LLM calls and introduce no secondary file spool |
| **Background Services & Process Trees** | Windows Job Objects; WSL `systemd` transient user services; macOS lightweight `owner-pipe` helper | Service config fingerprint, single-consumer lock, result persistence, and scratch cleanup order | Deleted duplicate PPID ownership heuristics across adapters |
| **Installation & Service Binding** | Single canonical installation binding + shared/exclusive operation lock | Prepare candidate outside lock; switch atomically when idle; keep runtime outside disposable host caches | Removed multi-generation routing, session leases, and global `current` symlinks |
| **Business State & Recovery** | Authoritative Markdown blocks + SQLite receipts + `diagnostics` | Privacy redaction, token usage persistence, and completed/failed/`unknown` reconciliation | Never automatically retry uncertain (`unknown`) paid model calls or external Git writes |

---

## 2. Plugin Updates: Native Installers + Compatibility Filtering

Full update rules are covered in [Release Compatibility & Silent Update](release-compatibility-and-update.en.md). Because native Git plugin marketplaces pull the latest branch tip by default without filtering by the installed host CLI's SemVer version, MindIE Agent adds a single shared pure selector function to pick the highest compatible Release and hands that pinned version to the native installer:

### 2.1 OpenAI Codex CLI Integration
- **Host cache behavior**: Codex refreshes configured Git marketplaces on startup, and its store (`store.rs`) prunes older version directories or replaces same-version cache directories in place.
- **Stable runtime isolation**: Running long-lived workers or active Hook/MCP entrypoints directly out of a disposable host cache would cause `file-not-found` errors mid-session when the cache refreshes. MindIE Agent therefore places stable release-bound entrypoints (`SessionStart`, `MCP`, `Stop`) and non-editable `uv` environments inside the application data directory.

### 2.2 Claude Code Integration
- **Host cache behavior**: Claude Code supports native marketplace installation, keeps active session paths stable until reload, and provides a consistent `CLAUDE_PLUGIN_DATA` directory across `SessionStart` and `MCP`.
- **Unified binding model**: We use the same stable entrypoint and isolated `uv` runtime layout on Claude Code so background services never depend on host cache retention policies, and increment the manifest version on every release for deterministic updates.

---

## 3. Millisecond Stop Hooks & Asynchronous Queue Consumption

Experience capture strictly separates **fast foreground admission** from **asynchronous background indexing**:

```text
Host triggers Stop Hook
  -> 1. Verify task identity & authorized project scope
  -> 2. Commit durable admission record to local SQLite
  -> 3. Return neutral response immediately (milliseconds, zero LLM calls)
  -> 4. Independent background worker consumes queue
  -> 5. OS-managed process tree runs lightweight native model for navigation
  -> 6. Save navigation & token usage -> Reclaim process tree -> Remove scratch
```

- **Why not rely on host `async: true` background hooks?**
  - As documented by Claude Code, non-interactive runs (`claude -p`) cancel unfinished background-flagged hooks when the main process exits. Using fast synchronous SQLite admission followed by an independent background service guarantees that experience indexing finishes reliably without slowing down the terminal.
- **Fast Windows cold wakeups**:
  - On Windows, waking the background Task Scheduler job uses `pywin32` native COM/ACL calls (~5–14 ms) instead of spawning multiple PowerShell subprocesses, keeping cold Stop Hooks well under budget.

---

## 4. Cross-Platform Process-Tree Cleanup via OS Primitives

Process-group semantics differ sharply across operating systems. To guarantee that all child and grandchild processes are reliably cleaned up even if the parent worker crashes or receives `SIGKILL`, MindIE Agent uses native OS primitives on each platform:

| Platform | OS Primitive Used | Reliability Guarantee |
| --- | --- | --- |
| **Native Windows** | Suspended spawn + named Windows Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` (via `pywin32`) | If the worker exits or is killed, the OS kernel closes the Job handle and terminates all descendant processes automatically |
| **Windows WSL / Linux** | `systemd` transient user service (`Type=exec`, `ExitType=main`, `KillMode=control-group`, `Restart=no`) | When the main process terminates, `systemd` reclaims the entire cgroup—even if child processes created new process groups (PGIDs) |
| **macOS** | Minimal shared `owner-pipe` helper (worker holds the sole write end; wrapper monitors pipe in same PGID before `exec`) | Worker termination causes immediate pipe `EOF`, cleanly terminating the entire operation process group without `launchd` registration overhead |

---

## 5. Primary Upstream References

- **[C1 / C2] OpenAI Codex Plugin Manager & Store**: [`manager.rs`](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/core-plugins/src/manager.rs#L2733) · [`store.rs`](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/core-plugins/src/store.rs#L699)
- **[A1 / A2] Claude Code Plugin Marketplace & Loading Docs**: [Plugin Marketplace](https://code.claude.com/docs/en/plugins/host-marketplace) · [Plugin Loading & Caching](https://code.claude.com/docs/en/plugins/loading)
- **[U1 / U2] Locked Environments & Atomic Cutover References**: [`uv` Project Sync](https://docs.astral.sh/uv/concepts/projects/sync/) · [Velopack Update Lifecycle](https://docs.velopack.io/integrating/overview)
- **[H1] Claude Code Background Hooks Contract**: [Run Hooks in the Background](https://code.claude.com/docs/en/hooks#run-hooks-in-the-background)
- **[P1 / P2 / P3] OS Process Management Specifications**: [`systemd.kill(5)`](https://github.com/systemd/systemd/blob/v257/man/systemd.kill.xml) · [Apple `launchd.plist(5)`](https://github.com/apple-oss-distributions/launchd/blob/d448a1c8f70a61202f8705f94337f686b87c30c4/man/launchd.plist.5) · [Microsoft Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)

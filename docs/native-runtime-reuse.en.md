# Native Plugin Managers, Hooks, and Process-Tree Reuse

[中文](native-runtime-reuse.md) · [Back to Documentation Index](README.en.md)

Updated 2026-10-16. This document summarizes the architectural rationale, mechanism selection, and OS primitive evaluations behind MindIE Agent's native runtime reuse (Principle 8). For the final `0.0.1` verification evidence across all six Codex/Claude Code × macOS/native Windows/WSL environments, see the [`0.0.1` Release Record](releases/0.0.1.en.md).

---

## Core Architectural Decision

Instead of maintaining custom multi-stage plugin updaters, custom virtual-environment builders, or duplicate process-supervision daemons in every adapter, MindIE Agent delegates generic lifecycle mechanics to proven host, package-manager, and OS primitives while retaining only the minimal product-specific glue required for compatibility filtering, durable state safety, and atomic binding switches:

| Responsibility | Adopted Mechanism | Retained MindIE Agent Scope | Deleted Legacy Responsibilities |
| --- | --- | --- | --- |
| **Plugin Download, Install & Registry** | Native Codex / Claude Code plugin managers | Single shared SemVer compatibility selector (`harness-compatibility.json`) + release gate | Deleted custom multi-stage `auto_update.py` / `updater.py`, dedicated update schedulers, and successor chains |
| **Python Dependencies & Isolated Runtime** | `uv sync --locked --no-editable` with committed `uv.lock` | Product combination contract (`product-contract.json`), platform/ABI identity, and schema validation | Replaced hand-rolled `venv`/`pip` orchestration and loose top-level requirements |
| **Lifecycle Hook Events** | Native Host Hooks + existing SQLite durable admission | Task identity verification, project scope check, lower-bound cursor, idempotency key, and commit receipt | Hooks never block on model calls and introduce no secondary file spool |
| **Service & Operation Process Trees** | Windows Job Objects (`KILL_ON_JOB_CLOSE`); WSL `systemd` transient user units (`KillMode=control-group`); macOS minimal shared `owner-pipe` helper | Service identity, single-consumer lock, operation outcome persistence, and scratch cleanup order | Deleted duplicate PPID ownership heuristics across adapters while preserving native cancellation boundaries |
| **Installation & Service Binding** | Single canonical installation binding + existing shared/exclusive operation lock | Prepare candidate outside lock; switch atomically when idle; keep active runtime outside disposable host plugin cache | Removed multi-generation service routing, session leases, and global `current` symlinks |
| **Business State & Recovery** | Authoritative Markdown blocks + SQLite receipts + `diagnostics` | Redaction, token usage tracking, known/failed/`unknown` reconciliation, and privacy gates | Never replay uncertain (`unknown`) paid model calls or external Git writes |

---

## Updates: Reusing Native Installers with Compatibility Filtering

Full update semantics are specified in [Release Compatibility & Silent Update](release-compatibility-and-update.en.md). Each plugin Release declares its supported Harness version range; because neither host's native marketplace catalog natively filters releases by SemVer compatibility range, a shared pure selector computes the highest compatible ordinary Release and hands that pinned candidate to the native plugin installer.

### OpenAI Codex CLI

- Codex updates configured Git marketplaces on startup and refreshes plugin caches, but its cache store (`store.rs`) prunes old version directories and replaces same-version cache paths in place.
- Consequently, long-running background workers and loaded Hook/MCP entrypoints (`SessionStart`, `MCP`, `Stop`) must not execute directly out of disposable host cache directories.
- MindIE Agent places stable release-bound entrypoints and non-editable `uv` environments under the application data directory, bound to the exact release identity, `uv.lock`, ABI, and platform.

### Claude Code

- Claude Code supports native marketplace installation and keeps existing session paths stable until reload, while providing `CLAUDE_PLUGIN_DATA` across `SessionStart` and `MCP`.
- MindIE Agent uses the same stable entrypoint and isolated runtime model on Claude Code so background services never depend on host cache retention policies, and bumps the manifest version on every release so native cache updates remain deterministic.

---

## Short Stop Hooks, Single Durable Queue, and Independent Owner

The experience capture pipeline follows a strict separation between fast synchronous admission and asynchronous background indexing:

```text
Native Stop Hook
  -> Verify task identity & project scope
  -> Commit durable admission record to SQLite
  -> Return neutral protocol confirmation immediately
  -> Independent Core worker consumes queue
  -> OS-owned indexing process tree runs native small model
  -> Persist navigation result & usage -> Clean up process tree -> Remove scratch
```

- **Fast Hook Return**: The Stop Hook confirmation means "durably enqueued," never blocking on cold service startup or model execution. On Windows, Task Scheduler control calls use `pywin32` COM APIs directly (~5–14 ms) rather than spawning multiple PowerShell subprocesses, keeping cold Stop admission well within the 1.5-second budget.
- **No Unreliable Async Hook Assumption**: Because hosts like `claude -p` cancel unfinished background-flagged hooks on process exit, MindIE Agent uses fast synchronous SQLite admission followed by an independent background service owner.

---

## Cross-Platform Process-Tree Ownership

Rather than assuming identical process-group behavior across macOS, Linux/WSL, and Windows, MindIE Agent uses the native OS primitive proven to clean up descendant processes even when the parent worker receives `SIGKILL` or terminates abruptly:

| Platform | Mechanism | Guarantee |
| --- | --- | --- |
| **Windows** | Suspended spawn + named Windows Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` (via `pywin32`) | Terminating the core worker closes the Job handle and reliably reclaims all child and grandchild processes |
| **Windows WSL** | `systemd` transient user service (`Type=exec`, `ExitType=main`, `KillMode=control-group`, `Restart=no`) | When the main process exits or is killed, `systemd` reclaims the entire cgroup including children that created new process groups |
| **macOS** | Minimal shared `owner-pipe` helper (core holds the sole write end; wrapper sets up same-PGID watcher before `exec`) | Pipe `EOF` upon core death immediately terminates the operation process group without registration overhead in `launchd` |

---

## Primary References

- [C1] OpenAI Codex plugin manager startup refresh (`codex-rs/core-plugins/src/manager.rs`, `rust-v0.153.4` / `rust-v0.162.0-alpha.17.2`)
- [C2] OpenAI Codex plugin store cache replacement and pruning (`codex-rs/core-plugins/src/store.rs`, `rust-v0.153.4`)
- [A1] [Claude Code Plugin Marketplace Documentation](https://code.claude.com/docs/en/plugins/host-marketplace) & [A2] [Plugin Loading & Caching](https://code.claude.com/docs/en/plugins/loading)
- [U1] [`uv` Locking and Syncing](https://docs.astral.sh/uv/concepts/projects/sync/) & [U2] [Velopack Update Lifecycle Reference](https://docs.velopack.io/integrating/overview)
- [H1] [Claude Code Background Hooks Contract](https://code.claude.com/docs/en/hooks#run-hooks-in-the-background)
- [P1] [`systemd.kill(5)`](https://github.com/systemd/systemd/blob/v257/man/systemd.kill.xml) & [`systemd.service(5)`](https://github.com/systemd/systemd/blob/v257/man/systemd.service.xml)
- [P2] [Apple `launchd.plist(5)` Manual](https://github.com/apple-oss-distributions/launchd/blob/d448a1c8f70a61202f8705f94337f686b87c30c4/man/launchd.plist.5)
- [P3] [Microsoft Windows Job Objects Documentation](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)

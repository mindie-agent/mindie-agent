# Structured Logging, Fault Diagnostics, and Opt-In Issue Reporting

[中文](diagnostics-and-reporting.md) · [Back to Documentation Index](README.en.md)

Design specification (2026-09-22); for release verification evidence see the [`0.0.1` Release Record](releases/0.0.1.en.md).

The goal of MindIE Agent diagnostics is to let an Agent immediately determine from a failed tool call how far the operation progressed, which side effects completed, where to inspect local evidence, and how to recover or switch approaches—following the [Nine Design Principles](design-principles.en.md) without adding closing rituals, LLM log analysis calls, or automatic business retries.

---

## Normal Usage and Independent Consent

Components write bounded structured local logs at real operational boundaries. Failed outcomes attach a diagnostic correlation ID, static error category, and recovery hint while preserving the original error, exit status, cancellation state, and cleanup outcome. Diagnostic IDs correlate local log stages only and never act as native task credentials or tool authorization tokens.

Initial setup offers an independent **"Automatic Tool-Fault Reporting"** option with a clear explanation of its scope, never enabled silently by default. It is configured separately from community knowledge contribution: users who disable knowledge sharing can still use local diagnostics and opt-in fault reporting, and disabling fault reporting keeps normal local logs intact. Querying diagnostic status never installs background services, invokes a model, or retries failed operations.

When explicitly enabled, the adapter persists the preference and ensures the shared reporter outside short Hooks. Configuration enabled, service installed, and service actively running are reported as distinct states. All three adapters share a single user-level reporter and configuration (`diagnostics` / `vaws-dfx`), which `remote-dev` also integrates when used standalone. Disabling fault reporting immediately revokes send permission for unsent items; re-enabling does not automatically flush faults queued under a previous consent epoch.

---

## Component Responsibilities

| Owner | Responsibility |
| --- | --- |
| **Codex / Claude Code / Kimi Adapters** | Native entrypoints, Hooks, MCP startup and protocol errors, configuration entry, and human-readable status; falls back to a minimal shared logger if early dependencies are missing |
| **`knowledge` / `remote-dev` Runtimes** | Record stage, version, monotonic duration, exit code, and cleanup facts at the exact internal boundary where a fault occurs, distinguishing normal user command failures from internal tool faults |
| **`diagnostics` (`vaws-dfx`)** | Log schema, deterministic redaction, bounded ring-buffer retention, diagnostic queries, independent consent, fault deduplication, finite retry queues, and GitHub Issue submission |
| **GitHub Maintainers** | Diagnose root causes and ship fixes; an automatically filed Issue is structured fault evidence, not an automated root-cause verdict |

MindIE Agent adds no global all-tool listener Hook, never scans historical transcripts across all tasks, and never duplicates reporter logic per adapter. When a shared component has already logged an error, it passes a trusted diagnostic reference to outer layers so the same fault is never reported multiple times.

---

## Recording and Public Redaction Boundaries

Local logs enforce per-entry and per-segment byte limits and use offline maintenance to bound segment count, total disk usage, and age. Normal entries record the component name, loaded version, operation, stage, monotonic duration, status, and stack-frame locations within MindIE Agent's own code. If writing a log entry fails, the tool returns a brief `logging_failed` fact without overwriting the primary error or polluting MCP `stdout`.

Public GitHub Issues are constructed deterministically from allowlisted fields without invoking any LLM:
- **Allowed public fields**: Component name, version or commit SHA, operation name, stage, static error type/code, duration, exit code, cleanup outcome, and a random task-agnostic diagnostic correlation ID.
- **Strictly excluded from public Issues**: Commands, arguments, environment variables, raw `stdout`/`stderr`, free-text exception messages, transcripts, configuration payloads, credentials, native task IDs, job IDs, local filesystem paths, and host addresses/IPs.
- **Excluded non-defect categories**: Invalid caller arguments, missing configuration, user cancellation, disabled features, permission denials, ordinary network/SSH authentication errors, and non-zero exits or timeouts from user commands never trigger automatic product-defect Issues. Only internal unhandled exceptions, abnormal termination of owned helper subprocesses, protocol corruption, or missing files in a published package qualify as reportable tool faults.

---

## Bounded Delivery and Loop Prevention

Faults sharing the same component version, operation, stage, error category, and internal code location produce a stable fault fingerprint decoupled from local consent epochs—switching tasks, switching adapters, or re-authorizing never turns an existing bug into a duplicate Issue. If a matching Issue already exists, its URL is recorded without posting duplicate comments or re-opening closed Issues.

Each candidate fault consumes at most **three persistent processing attempts** (counting network reads, pre-send deduplication queries, post-send verification, and crashes). Each attempt enforces strict wall-clock, output-size, and pagination bounds and honors GitHub rate-limit headers. If a send attempt ends with an uncertain outcome (`unknown`), the reporter reconciles against GitHub read-only before taking further action and never blindly re-posts. Once the three-attempt budget is exhausted, the item enters a visible terminal state that is never reset by status queries or process restarts.

Reporter failures remain strictly local so the reporter can never file Issues about its own reporting errors.

---

## Log Retention and Lifecycle Maintenance

The shared reporter runs from an independent, version-verifiable runtime directory rather than borrowing a disposable adapter cache. Routine offline log maintenance runs alongside existing periodic check boundaries—cleaning expired segments even when Issue reporting is disabled—while protecting all registered reader cursors and active writers so rotation never clobbers unread segments.

In `remote-dev`, user command `stdout`/`stderr` streams are job output artifacts governed by the job and artifact lifecycle, never truncated as diagnostic logs.

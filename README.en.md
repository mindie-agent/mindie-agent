<p align="center">
  <img src="assets/brand/mindie-agent-logo.png" alt="MindIE Agent logo" width="128" height="128">
</p>

# MindIE Agent

Domain context, remote execution tools, and a knowledge/experience/usefulness feedback loop for Ascend development.

The current implementation target is the [Codex](https://github.com/mindie-agent/mindie-agent-codex) adapter in your own business repository. Existing contribution choice and project scope apply to verified native tasks without daily activation or closing steps.
Knowledge processing runs locally; remote-dev provides remote execution. Codex selects and redacts complete public messages without a body model. An internal native model produces required retrieval navigation, never replacement body text. The contribution choice persists across tasks and updates; missing configuration, explicit disable and operational failure remain distinct.

This repository contains [architecture](docs/architecture.md), [design principles](docs/design-principles.md)
and [next steps](docs/next-steps.md). Component ownership and current evidence are listed in the [Chinese README](README.md).

The former workspace bootstrap, updater, source management, client wiring and automatically exposed Skills
have been removed. No legacy aliases or installation path are provided. Git history retains prior work.
The current [system review](docs/system-review-2026-10-05.md) covers Codex and its upstream/downstream components. Kimi and Claude Code retain separate older runtime pins and need their own port and acceptance. Read the
[unified implementation status](docs/implementation-status.md) for development and native acceptance separately.
The [2026-09-29 Codex acceptance](docs/codex-public-transcript-acceptance-2026-09-29.md) records
Windows PowerShell and WSL NPU runs, native Stop, redacted publication and retrieval against exact
candidate revisions. It identifies manual interventions and unverified boundaries separately.
Kimi model acceptance is deferred; Grok is not an adapter under test. Merge is distinct from release
acceptance. Old business Skills and profiling remain deferred.

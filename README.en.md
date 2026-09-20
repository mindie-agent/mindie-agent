# MindIE Agent

Domain context, remote execution tools, and a knowledge/experience/usefulness feedback loop for Ascend development.

Start with the [Codex plugin](https://github.com/mindie-agent/mindie-agent-codex) in your own business repository.
Knowledge and optional contribution processing run locally; remote-dev provides remote execution. Collection is off until explicitly enabled.

This repository contains [architecture](docs/architecture.md), [design principles](docs/design-principles.md)
and [next steps](docs/next-steps.md). Component ownership and current evidence are listed in the [Chinese README](README.md).

The former workspace bootstrap, updater, source management, client wiring and automatically exposed Skills
have been removed. No legacy aliases or installation path are provided. Git history retains prior work.
The current rewrite spans independent Codex, Kimi and Claude Code adapters. Read the
[unified implementation status](docs/implementation-status.md) for development and native acceptance separately.
Historical NPU evidence does not establish the final rewritten contribution loop, other Harness support,
Windows desktop acceptance or reliable Grok PR event delivery. Old business Skills and profiling remain deferred.

# MindIE Agent

Domain context, remote execution tools, and a knowledge/experience/usefulness feedback loop for Ascend development.

Start with the [Codex plugin](https://github.com/mindie-agent/mindie-agent-codex) in your own business repository.
Codex and the knowledge loop run locally; remote-dev provides remote NPU execution.

This repository contains [architecture](docs/architecture.md), [design principles](docs/design-principles.md)
and [next steps](docs/next-steps.md). Component ownership and current evidence are listed in the [Chinese README](README.md).

The former workspace bootstrap, updater, source management, client wiring and automatically exposed Skills
have been removed. No legacy aliases or installation path are provided. Git history retains prior work.
The first implementation covers one domain and a real NPU reuse/feedback loop; it does not establish
cross-domain Desktop interaction, other Harness support or reliable Grok PR event delivery.

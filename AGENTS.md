# MindIE Agent

This repository owns architecture, domain boundaries and product entry documentation.
The supported Codex implementation is `mindie-agent/mindie-agent-codex`.
Shared runtime components live in their own repositories under `mindie-agent`.

Use native local tools for this repository. It has no bootstrap, workspace manager,
client hook, MCP server, Skill catalogue, dependency lock or business source checkout.
Use the user's business repository and the selected Harness plugin for actual tasks.

Follow [design principles](docs/design-principles.md) and the [architecture](docs/architecture.md).
Keep implementation status distinct from the target design and real acceptance evidence.
Do not add old VAWS aliases or an alternative legacy installation path.
Do not alter the user's unrelated skills, plugins or MCP configuration.

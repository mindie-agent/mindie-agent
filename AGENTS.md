# MindIE Agent

This repository owns architecture, domain boundaries and product entry documentation.
Native implementations live in `mindie-agent/mindie-agent-codex`,
`mindie-agent/mindie-agent-kimi` and `mindie-agent/mindie-agent-cc`.
Shared runtime components live in their own repositories under `mindie-agent`.

Use native local tools for this repository. It has no bootstrap, workspace manager,
client hook, MCP server, Skill catalogue, dependency lock or business source checkout.
Use the user's business repository and the selected Harness plugin for actual tasks.

Follow [design principles](docs/design-principles.md) and the [architecture](docs/architecture.md).
MindIE Agent inherits all nine VAWS design principles; retiring the old runtime
does not retire or replace those principles.
Keep implementation status distinct from the target design and real acceptance evidence.
Do not add old VAWS aliases or an alternative legacy installation path.
Do not alter the user's unrelated skills, plugins or MCP configuration.

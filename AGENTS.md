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

## Mandatory design-principles review before PR submission

All MindIE Agent development tasks MUST read the current [design principles](docs/design-principles.md) and review the final diff and affected behavior against all nine principles before creating any PR, including a draft. This covers code, configuration, dependencies, CI and project documentation. Review subsequent PR changes against the affected principles again.

Errors MUST remain visible to the caller. Never turn a required-step failure into success, empty data, first use, user disablement or an undocumented fallback. Distinguish completed work, failure and uncertain external effects; do not repeat an uncertain write or hide the original error behind a later failure.

Fix principle violations before submission. In the PR description, record the reviewed commit and principles revision, concrete conclusions and applicability, findings and fixes, and actual validation or remaining gaps. Tests passing, checkboxes, blanket N/A or “all principles followed” are not a review. If the principles cannot be read or the review is incomplete, report that explicitly and do not create or update the development PR until review is complete. Pure knowledge/feedback contributions follow their content rules; development of those features remains subject to this review.

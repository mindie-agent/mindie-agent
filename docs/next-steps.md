# Next iterations

The initial Codex + knowledge + collection + distribution + independent judge slice has real NPU evidence.
The organization and repositories now use MindIE Agent. The product entry is the Codex plugin.

## 1. Make the closed loop installable and operable

Provide one reproducible, pinned installation/update path for the plugin and local services.
Exercise a fresh machine, upgrade, service restart, failed organization/judging and explicit publication.
Keep local agent execution and remote NPU execution separate. Reduce unused runtime dependencies
based on the supported import path, and expose useful status for incomplete collection and judging.

## 2. Consolidate the domain publisher

Move the official vLLM-Ascend feed from `knowledge`'s data branch into `knowledge-vllm-ascend`.
Update the publisher and consumers together, preserving content/use/feedback identities.
Agree the normal reviewed-experience publication path. Resolve Grok PR event delivery; daily polling
currently remains the observed fallback. An enabled subscription alone is not acceptance.

## 3. Prove a directly steerable cross-domain task

Add one clearly bounded second domain only when it needs a separate context.
Use two ordinary native tasks in one Harness, with minimal handoff, direct user guidance in each,
and observable request/result exchange. Validate task restoration and avoid changing other active tasks.

## 4. Expand execution recipes and Harness adapters

Generalize coordinator's source/environment contracts and establish vLLM-Ascend and CANN container families.
Reuse the knowledge protocol for Cursor, Kimi, Claude, DSH and Grok adapters, each with its own repository
and actual acceptance. Z Code remains deferred. Do not infer full support from MCP/plugin discovery alone.

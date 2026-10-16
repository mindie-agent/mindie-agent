# MindIE Agent Roadmap & Next Steps

[中文](next-steps.md) · [Back to Documentation Index](README.en.md)

For the current system architecture and knowledge loop design, see [`docs/architecture.en.md`](architecture.en.md) and [`docs/knowledge-system.en.md`](knowledge-system.en.md). All iterations are governed by [`docs/design-principles.en.md`](design-principles.en.md).

The initial `0.0.1` release is published as an ordinary Release covering six host and platform combinations (`Codex` and `Claude Code` across `macOS`, `native Windows`, and `Windows WSL`). Exact supported versions, paired component Release mappings, and known limitations are documented in [`docs/releases/0.0.1.en.md`](releases/0.0.1.en.md).

## Current Priorities

- **Real-World Business Reuse Benchmarks**: Independently evaluate end-to-end engineering quality and efficiency gains from the knowledge and experience loop on real Ascend tasks (`0.0.1` makes no premature quantitative claims).
- **Upstream Host Issue Follow-Up**: Track upstream fixes in OpenAI Codex CLI for child-agent interruption delivery to pending tool calls, without introducing intrusive process-hunting workarounds or arbitrary business execution timeouts.
- **Additional Domains & Host Adapters**: Continue iterating on Kimi Code release readiness, curated standalone Agent Skills (`awesome-mindie-skills`), and profiling workflows as independent tracks.
- **Zero Daily Ceremony**: Keep ordinary engineering tasks friction-free—no mandatory per-task activation, lookup, or closing rituals.

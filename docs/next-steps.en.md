# MindIE Agent Roadmap & Next Steps

[中文](next-steps.md) · [Back to Documentation Center](README.en.md)

For the current system architecture and knowledge loop design, see [Architecture & Module Boundaries](architecture.en.md) and [Knowledge & Experience System](knowledge-system.en.md). All iterations follow the [Engineering Design Principles](design-principles.en.md).

Our initial [`0.0.1`](releases/0.0.1.en.md) release is live across six mainstream development environments (**Claude Code** and **OpenAI Codex CLI** on **macOS**, **native Windows**, and **Windows WSL**).

---

## Current Engineering Priorities

1. **Real-World Engineering Benchmarks**
   - Run end-to-end benchmarks on real Ascend operator debugging, model migration, and inference tuning workloads to measure how much time and effort the experience loop saves in practice (we avoid making premature quantitative claims before benchmarks are complete).
2. **Broader Host & Domain Coverage**
   - **Kimi Code Formal Release**: Complete cross-platform acceptance and publish the formal release for [`mindie-agent-kimi`](https://github.com/mindie-agent/mindie-agent-kimi).
   - **Expand Standalone Skills**: Grow [`awesome-mindie-skills`](https://github.com/mindie-agent/awesome-mindie-skills) with additional ready-to-use workflows for Ascend profiling, accuracy verification, and kernel development.
3. **Upstream Host Issue Tracking**
   - Track upstream fixes in OpenAI Codex CLI for delivering cancellation signals to in-flight tool calls when a child agent (`spawn_agent`) is interrupted, updating our compatibility range once upstream ships the fix rather than adding intrusive process-hunting workarounds.
4. **Keep Everyday Workflows Zero-Ceremony**
   - Maintain a frictionless experience—one-sentence Agent-native installation, zero daily activation commands, and silent background updates—so developers can focus entirely on Ascend engineering.

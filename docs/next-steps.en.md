# MindIE Agent Roadmap & Next Steps

[中文](next-steps.md) · [Back to Documentation Center](README.en.md)

For the system architecture and knowledge loop design, see [Architecture & Module Boundaries](architecture.en.md) and [Knowledge & Experience System](knowledge-system.en.md). Engineering guidelines are documented in [Engineering Design Principles](design-principles.en.md).

The current release is [`0.0.2`](releases/0.0.2.en.md), which aligns the product and the four host plugins (Codex, Claude Code, Kimi Code, and DSH) on version `0.0.2` while keeping independent version sequences for shared runtime components and `mindie-bench` (historical initial release notes remain at [`0.0.1`](releases/0.0.1.en.md)). In `0.0.2`, we simplified cross-repository state management, unified community knowledge sharing and automatic fault reporting under a single contribution switch, tightened locked dependency installation, and introduced automated per-release benchmarks across all ten code repositories.

---

## Upcoming Priorities

1. **`0.0.3` Knowledge Retrieval Latency & Context Efficiency Optimization**
   - In the `0.0.2` live Ascend evaluations, enabling `mindie-knowledge` raised solved counts from `2/3` to `3/3` on both `dp2` and `dsh`, while introducing retrieval and long-context reading overhead. `0.0.3` will focus on optimizing retrieval granularity and context delivery so we keep the solve-rate gains while reducing latency overhead.
2. **Host Lifecycle Reliability & Live Test Speed**
   - Monitor real-world usage of the unified contribution and fault-reporting pipeline, prioritize fixes for reported tool faults, and expand automated cross-platform upgrade verification.
   - Streamline the `remote-dev` live A2/A3 integration suite so its total execution time drops from ~51 seconds into the 25-second Tier 2 design budget.
3. **Broader Ascend AI Infra Knowledge, Profiling/Simulation (`profiler` / `sim`) & Skills Coverage**
   - Expand [`knowledge-vllm-ascend`](https://github.com/mindie-agent/knowledge-vllm-ascend), [`knowledge-operators`](https://github.com/mindie-agent/knowledge-operators), and [`awesome-mindie-skills`](https://github.com/mindie-agent/awesome-mindie-skills) across the Ascend NPU AI Infra workflow, covering architecture design, `vLLM-Ascend` feature development, `AscendC`/`Triton` kernel implementation, accuracy verification, and profiling.
   - Advance end-to-end integration and benchmark verification of the standalone profiling component [`profiler`](https://github.com/mindie-agent/profiler) (`mindie-profiler`) and 4-layer boundary solver [`sim`](https://github.com/mindie-agent/sim) (`mindie-sim`) with [`mindie-bench`](https://github.com/mindie-agent/mindie-bench).
4. **Optional `coordinator` Integration Path**
   - Today, [`coordinator`](https://github.com/mindie-agent/coordinator) (Agent-facing SSH host management, agentless NPU/server probing, container binding, and lease arbitration) and [`npu-top`](https://github.com/mindie-agent/npu-top) (human-facing Web dashboard and 90-day heatmaps) are installed standalone on demand, while the four host plugins bundle `knowledge`, `remote-dev`, and `diagnostics`.
   - Exposing `coordinator` tools by default inside host plugins will be evaluated as a dedicated step with explicit dependency locking, tool registration, and host verification.
5. **Upstream Host CLI Tracking**
   - Track upstream fixes in OpenAI Codex CLI for forwarding cancellation signals to in-flight MCP tool calls when a child agent (`spawn_agent`) is interrupted, and update `harness-compatibility.json` once upstream ships the fix.

# MindIE Agent Roadmap & Next Steps

[中文](next-steps.md) · [Back to Documentation Center](README.en.md)

For the system architecture and knowledge loop design, see [Architecture & Module Boundaries](architecture.en.md) and [Knowledge & Experience System](knowledge-system.en.md). Engineering guidelines are documented in [Engineering Design Principles](design-principles.en.md).

The ecosystem has completed the **[`v0.1.0`](releases/0.1.0.en.md)** milestone release ([18-Task Benchmark Report](releases/0.1.0/value-results.md) · [Author's Note](releases/0.1.0/design-philosophy.en.md)) and subsequent `v0.1.1`–[`v0.1.4`](releases/0.1.4.en.md) updates (pinned in [`channels/0.1.json`](../channels/0.1.json)). Delivered capabilities include information-gap retrieval, L1–L4 progressive disclosure, token-budget gating, the `G3` C6 experience distillation flywheel, and `G4` `mode="explore"` exploration in `knowledge v0.13.7` across 7 public Ascend domain corpora (`450` graded units); the unified 5-layer causal engine in `mindie-sim v0.8.1` and topology-guided Decode segmentation in `mindie-profiler v0.5.3` (converging across 280 Decode + 15 Prefill cases and achieving 98.25% `<= 15%` error across 856 DSH fleet cases); shared SSH authentication in `remote-dev v0.11.2`; deterministic CANN/`plog` fault triage in `diagnostics v0.5.4`; Ascend A5 topology/HCCL preflight in `coordinator v0.7.0`; and real subprocess behavioral oracle hardening & zero-model archive re-evaluation across all 20 `mindie-bench` tasks (see [Release Records & Roadmap](README.en.md#release-records--roadmap)).

---

## Upcoming Priorities

1. **End-to-End Multi-Host Product Matrix (`P0–P3`) & Knowledge Flywheel Evolution**
   - Expand cross-model, cross-host end-to-end engineering task and experience-transfer (`P0–P3`) evaluations on `mindie-bench` under hardened behavioral oracles, tracking net engineering gains from L1–L4 progressive disclosure and subcontext fact packs on complex kernel and serving workloads.
2. **Ascend A5 (950) Live Communication Expansion & Contention Calibration**
   - Execute the [A5 Communication & Contention Calibration Plan](a5-communication-calibration-todo.md) on live A5 hardware to calibrate AICPU/AIV collective expansion and contention parameters in `mindie-sim` and `mindie-profiler`.
3. **Expanding the 7 Public Domain Knowledge Corpora & `awesome-mindie-skills`**
   - Continuously grow verified `L1–L4` units and practical guides across [`knowledge-vllm-ascend`](https://github.com/mindie-agent/knowledge-vllm-ascend), [`knowledge-operators`](https://github.com/mindie-agent/knowledge-operators), [`knowledge-infer-core`](https://github.com/mindie-agent/knowledge-infer-core), [`knowledge-infer-distributed`](https://github.com/mindie-agent/knowledge-infer-distributed), [`knowledge-infer-observability`](https://github.com/mindie-agent/knowledge-infer-observability), [`knowledge-infer-ops-compat`](https://github.com/mindie-agent/knowledge-infer-ops-compat), [`knowledge-agent-engineering`](https://github.com/mindie-agent/knowledge-agent-engineering), and [`awesome-mindie-skills`](https://github.com/mindie-agent/awesome-mindie-skills).
4. **Streamlined Workflows Across `coordinator`, `profiler`, `sim`, and Host Plugins**
   - All four host plugins now expose `remote-dev`, `coordinator`, `profiler`, `sim`, and `diagnostics` through the three-server MCP surface (`knowledge`, `remote`, `components`); upcoming work focuses on streamlining closed-loop workflows ("Profiling bottleneck attribution → Sim candidate fusion & SLA scaling → Remote container verification").
5. **Upstream Host CLI Tracking**
   - Track upstream fixes in OpenAI Codex CLI for forwarding cancellation signals to in-flight MCP tool calls when a child agent (`spawn_agent`) is interrupted, and update `harness-compatibility.json` once upstream ships the fix.

# MindIE Agent Architecture and Module Boundaries

[中文](architecture.md) · [Documentation](README.en.md)

MindIE Agent adds Ascend domain knowledge retrieval, remote container execution, multi-NPU resource coordination, and profiling tools to existing AI coding agents (Claude Code, OpenAI Codex, Kimi Code, and DeepSeek Harness). Current work focuses on **vLLM-Ascend framework development and Ascend operator optimization** across three core scenarios: **new model bring-up (0-day adaptation), model and operator performance tuning, and runtime fault diagnosis**.

This document describes component responsibilities and how they work together. See the [release records](README.en.md) for formal versions and benchmark results, [Knowledge System](knowledge-system.en.md) for how engineering experience is organized and retrieved, [Harness Boundaries](harness-boundary-and-lifecycle.en.md) for session identity and user consent, and [Design Principles](design-principles.en.md) for engineering guidelines.

## 1. Native Host Plugins and Shared Runtime Components

```mermaid
flowchart TB
    H["Codex / Claude Code / Kimi Code / DSH"] --> P["Thin native host plugins"]
    P --> K["knowledge: domain routing, condition matching & experience distillation"]
    P --> R["remote-dev: remote files, commands & background jobs"]
    P --> D["diagnostics: local fault logs & opt-in Issue reporting"]
    P --> PR["profiler: Ascend profiling capture, analysis & cross-run compare"]
    P --> S["sim: resources, operator families, graphs & serving constraints"]
    K <--> F["vLLM-Ascend / operators knowledge repositories"]
    T["Optional TaskClient / coordinator"] --> Q["Machine inventory, containers, NPU & port leases"]
    Q --> R
    R --> N["Remote Ascend hosts & Docker containers"]
    M["Optional npu-top dashboard"] -.-> N
    B["mindie-bench evaluation suite"] --> T
    B --> H
```

Each plugin preserves its host agent's native session loop, tool calling, and lifecycle:
- **On-demand domain guidance**: Invoke `/mindie-agent` (or `$mindie-agent` in Codex) to load Ascend domain knowledge and workflow guidance for your current task.
- **Engineering tools ready by default**: `remote-dev`, `coordinator` probes and leases, `profiler` capture and analysis, `sim` performance modeling, and `diagnostics` status/bundle tools are exposed across all four hosts through the three-server MCP surface (`knowledge`, `remote`, and `components` / `mindie-tools`) and can be called directly without activating a knowledge session. Unactivated chats do not load the `knowledge` tool catalog, while `npu-top` runs as a human-facing web dashboard rather than an Agent tool.
- **Authorized experience capture**: Only when a session explicitly invokes `/mindie-agent` and satisfies saved user consent and project scope do host lifecycle hooks capture redacted session transcripts and distill reusable experience.

By default, plugins use `knowledge`, `remote-dev`, and `diagnostics`. `coordinator`, `profiler`, `sim`, and `npu-top` can be installed standalone or combined as needed.

## 2. Repository Ownership

| Repository | Responsibility |
| --- | --- |
| [`mindie-agent`](https://github.com/mindie-agent/mindie-agent) | Product architecture, domain boundaries, documentation entry point, cross-repo specifications, and release records; contains no runtime bootstrap or MCP server code |
| [`mindie-agent-codex`](https://github.com/mindie-agent/mindie-agent-codex), [`mindie-agent-cc`](https://github.com/mindie-agent/mindie-agent-cc), [`mindie-agent-kimi`](https://github.com/mindie-agent/mindie-agent-kimi), [`mindie-agent-dsh`](https://github.com/mindie-agent/mindie-agent-dsh) | Native client plugins: session identification, lifecycle hooks, redacted session transcript capture, MCP bridges, and pinned component versions |
| [`knowledge`](https://github.com/mindie-agent/knowledge) | Knowledge engine: condition-matched retrieval, batch `refs` explanation with shared `known_refs` and `token_budget`, `rejected_history` and `affected_components` provenance, redacted task blocks, experience distillation validation, and community PR publishing |
| [`knowledge-vllm-ascend`](https://github.com/mindie-agent/knowledge-vllm-ascend), [`knowledge-operators`](https://github.com/mindie-agent/knowledge-operators), [`knowledge-infer-core`](https://github.com/mindie-agent/knowledge-infer-core), [`knowledge-infer-distributed`](https://github.com/mindie-agent/knowledge-infer-distributed), [`knowledge-infer-observability`](https://github.com/mindie-agent/knowledge-infer-observability), [`knowledge-infer-ops-compat`](https://github.com/mindie-agent/knowledge-infer-ops-compat), [`knowledge-agent-engineering`](https://github.com/mindie-agent/knowledge-agent-engineering) | Seven public graded engineering knowledge corpora (`L1–L4`) covering `vLLM-Ascend`, Ascend operators, inference engine internals, distributed communication (including `DP/TP/EP/PP/DCP/DSA-CP/PCP`), observability, graph/operator compatibility, and Agent engineering governance |
| [`remote-dev`](https://github.com/mindie-agent/remote-dev) | Shared SSH authentication, user-scoped `~/.mindie/ssh/id_ed25519` credential fallback and public-key maintenance, destructive-command safety guards; file access, surgical edits, search, patch sync, container command execution, and background job management |
| [`coordinator`](https://github.com/mindie-agent/coordinator) | Remote Ascend environment and lease manager: machine and container inventory, NPU topology probing (A2/A3 dual-Die `Phy-ID` mapping/A5), HCCL/RoCE preflight, per-Die HBM lease & compile slot budgets, NPU and port lease arbitration, and managed task cleanup |
| [`npu-top`](https://github.com/mindie-agent/npu-top) | Human-facing NPU cluster dashboard: supports A2/A3/A5 monitoring with shared `coordinator` `machines.json` and `~/.mindie/ssh` credential fallback, providing a loopback web UI (`127.0.0.1:8788`), TUI, CLI/MCP, and 90-day utilization history |
| [`diagnostics`](https://github.com/mindie-agent/diagnostics) | Bounded structured fault logs (4×1 MiB JSONL rotation), offline redacted diagnostic bundles, and opt-in allowlisted GitHub Issue reporting with bounded 2-attempt outbound reconciliation (`mindie_diagnostics`) |
| [`profiler`](https://github.com/mindie-agent/profiler) | Ascend profiling collection and in-place trace analyzer (`mindie_profiler`): `inventory / analyze / correlate / compare / sql` commands, Host-Device correlation, `analyze_profiling --structure` 3-state topology alignment (`aligned / declared_only / unattributed_observed`) on `mindie-model-structure/1`, `auto_segment_decode_forwards` Decode segmentation, memory breakdown, and cross-run comparison |
| [`sim`](https://github.com/mindie-agent/sim) | Hardware-neutral 5-layer causal performance modeling (`mindie_sim`): unifies physical resources, operator families, subgraphs, pure-model costs, and serving constraints (`DP × TP × EP × PP × DCP / DSA-CP / PCP` & PD disaggregation) with 4D efficiency breakdown (`Cube_MFU / Vec_MFU / MBU / Link_Util / CV_Overlap`), 30ms SLA hardware scaling solver, structure export, and 856-case fleet calibration (see [Simulation System](simulation-system.md)) |
| [`mindie-bench`](https://github.com/mindie-agent/mindie-bench) | Live Ascend NPU benchmark suite: 20 behavioral-oracle tasks (109 3-state & helper controls), isolated host runs (native knowledge evaluation wiring & `zsh` temp isolation), cross-task reuse evaluation, and release benchmark reports |
| [`awesome-mindie-skills`](https://github.com/mindie-agent/awesome-mindie-skills), [`vllm-ascend-workspace`](https://github.com/mindie-agent/vllm-ascend-workspace) | Open-source Ascend AI Infra Agent Skills catalogue and lightweight `vLLM` + `vLLM-Ascend` local workspace with isolated Git Worktrees |

### Cross-Component Collaboration Boundaries

- **Shared SSH Authentication (`remote_dev.auth`)**: `remote-dev` owns the unified SSH authentication and public-key maintenance implementation, while `coordinator` and `npu-top` store endpoint details and `auth_ref` references. All processes, chats, and host plugins running under the same OS user share `~/.mindie/ssh/credentials.json` (protected by user directory and file permissions without requiring OS keychains or system login passwords; native Windows and WSL use their respective user directories). Development calls perform password fallback and public-key repair before command submission and never blindly replay submitted commands; read-only diagnostic and monitoring probes may fall back to password authentication during the SSH handshake without modifying remote authorized keys.
- **Structure & Calibration Synergy Between `sim` and `profiler`**: `mindie-sim` owns declared model and operator structures (exporting `mindie-model-structure/1` from both its Case frontend and `OpSpec` DAGs) and runs a unified 5-layer causal engine across physical resources, operator families, subgraphs, pure-model costs, and serving constraints to produce mechanism-first latency predictions, 4D efficiency breakdowns (`Cube_MFU / Vec_MFU / MBU / Link_Util / CV_Overlap`), and SLA hardware scaling recommendations. `mindie-profiler` owns raw `msprof` CSV/SQLite parsing, observed tensor shape extraction, and topology-guided Decode step segmentation (`auto_segment_decode_forwards`) and event attribution over `mindie-model-structure/1`. The two components collaborate cleanly through structure exports and measured Cohort / Decode Body statistics; see [Simulation System](simulation-system.md), [Profiler System Design](profiler-system.md), and [Structure Reuse & Measured Mapping](profiler-sim-structure.md).

## 3. Remote Task Execution and Resource Cleanup

When running builds, tests, or benchmarks on remote Ascend servers:
1. **Topology probing and lease acquisition**: `coordinator` checks host and container readiness and acquires conflict-free NPU and port leases based on actual hardware topology (for example, mapping Ascend A3 910C dual-Die `Phy-ID` pairs accurately so two tasks never collide on sibling dies of the same physical card).
2. **Remote execution and background jobs**: `remote-dev` edits files and runs commands inside the target container, turning long compilation or benchmark runs into managed background jobs with live log streaming.
3. **Reconnect recovery and clean teardown**: After a network interruption, the client queries the existing task ID before taking further action so in-flight remote jobs are never blindly duplicated. On completion or cancellation, process trees, NPU leases, and ports are cleaned up explicitly. External operations distinguish `completed`, `failed`, and `unknown` outcomes so a local receipt-accounting timeout never overwrites a successful remote run.

## 4. Four Knowledge Roles & Dual-Mode Workflow (Routine Reuse vs. Fresh Exploration)

The context loading and experience loop in this section run only in a manually
enabled session. Deterministic tools such as profiler, sim and coordinator
remain independently available without knowledge activation.

To support complex Ascend inference adaptation and performance optimization, MindIE Agent organizes domain knowledge into four engineering roles (mapped to `category` and the legacy `tier: L1..L4` field in the schema) and supports both **routine workflow reuse** and **fresh-context exploration (`mode="explore"`)**:

| Knowledge Role & Category | Engineering Purpose | Runtime Coordination |
| --- | --- | --- |
| **`L1` · Hardware Constraints & Measurement Baselines**<br/>(`axiom` / `measurement`) | Captures Ascend 910B / A3 / A5 hardware limits, memory alignment rules, `ACLGraph` static capture invariants, and timing/accuracy measurement standards | Automatically mounted when hardware and repository conditions match (`foundation_baseline`), or injected in full as inherited premises (`inherits_from`) |
| **`L2` · Diagnostic & Operational SOPs**<br/>(`sop`) | Provides concrete diagnostic checklists, profiling capture/analysis recipes, and module adaptation steps so bottlenecks are measured before code is edited | Used alongside `mindie-profiler` (trace analysis), `mindie-sim` (roofline and pipeline bounds), and `diagnostics` |
| **`L3` · Troubleshooting & Tuning Workflows**<br/>(`workflow`) | Covers routine model bring-up, accuracy debugging, and standard performance tuning through multi-step decision trees with clear observation branches | Returned by default queries (`mode="standard"`); verified new troubleshooting paths can be distilled back into the corpus via `knowledge_distill` |
| **`L4` · Code Optimizations & Fresh-Context Exploration**<br/>(`mutator`) | Captures verified operator vectorization, pipeline scheduling, communication fusion, and graph capture optimizations; when routine tuning stalls while significant headroom remains against hardware roofline bounds, agents can switch to **fresh-context exploration (`mode="explore"`)** | Calling `knowledge_query(..., mode="explore")` **strips routine `L3` workflows** to prevent anchoring bias, mounting only `L1` hardware rules, `L2` bottleneck measurements, `L4` candidate transformations, and condition-matched negative results (`conditional_avoid`) so a fresh sub-session can run parallel CPU compiles, serial NPU timing, and 4-step verification (compile → accuracy → speedup → leave-one-out ablation) |

> [!NOTE]
> **Terminology Note**:
> - `tier: L1..L4` in the knowledge schema maps 1-to-1 to `category` (`axiom`/`measurement`, `sop`, `workflow`, `mutator`) and describes the engineering role of a knowledge entry, not its confidence level; evidence maturity is tracked separately in `evidence_strength` (`hardware_spec`, `reproduced_empirical`, `single_observation`, `hypothesis`).
> - `mindie-sim` composes **physical resources → operator families → blocks/subgraphs → pure-model costs → serving constraints**. Timing detail and measured calibration are independent axes; the old four-layer CLI is not the rewritten interface. Ascend on-chip buffers are written in full (**`L1 Buffer` / `L0A` / `L0B` / `L0C` / `UB` / `L2 Cache`**); test scopes use **`Tier 0 – Tier 3`**.

## 5. Verification Standards Across the Three Core Scenarios

| Scenario | Verification Requirements |
| --- | --- |
| **New model bring-up (0-day adaptation)** | Pin source, model config, and weight revisions; run the full target inference path on NPU; and verify numerical parity against an independent golden reference (CPU execution alone does not establish NPU readiness) |
| **Model & operator performance tuning** | Fix input shapes, dtypes, and hardware/software conditions; verify numerical accuracy alongside baseline vs. optimized NPU latency; and run leave-one-out ablation when combining multiple optimizations to confirm each change contributes net speedup |
| **Runtime fault diagnosis** | Record the reproducible fault symptom, root-cause evidence, before/after NPU behavior, and resource cleanup; clearly distinguish source-level analysis from live NPU runtime observations |

## 6. Releases, Silent Updates, and Privacy Redaction

- **Pinned releases and atomic updates**: Host plugins pin verified baseline runtime component versions (while [`channels/0.1.json`](../channels/0.1.json) records verified product release combinations). Runtime component updates discover formal GitHub Releases directly from each official component repository—taking `max(installed version, plugin baseline, formal Release version)` to prevent downgrades, verifying the immutable tag SHA, `pyproject.toml`, asset presence, and `benchmark-results.json`, installing from the exact Git SHA into an isolated `uv.lock` environment, and probing the native API—before switching atomically when idle without interrupting active sessions. See [Release Compatibility](release-compatibility-and-update.en.md).
- **Deterministic redaction and opt-in sharing**: Session transcript capture, experience distillation, and fault reporting pass through deterministic privacy rules and Gitleaks scanning to strip internal IPs, machine paths, credentials, and sensitive arguments. Disabling community sharing never affects local knowledge retrieval, diagnostics, or remote execution. See [Diagnostics and Fault Reporting](diagnostics-and-reporting.en.md).

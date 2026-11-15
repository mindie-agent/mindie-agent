# Author's Note: MindIE Agent Architectural Philosophy & Acknowledgments

[中文完整版](design-philosophy.md) · [Back to `0.1.0` Release Notes](../0.1.0.en.md) · [Documentation Center](../../README.en.md)

> **Preface**: I originally intended to write this architectural reflection myself, but since I have not hand-written a single line of code or documentation in over half a year, I opted to dictate my thoughts orally and have **Gemini 4 Argon** organize and polish them. Below is my candid reflection on how MindIE Agent evolved, its tool and knowledge flywheels, its engineering boundaries, and how humans and Agents collaborate. (See the [Chinese version](design-philosophy.md) for the full first-person narrative.)

---

## 1. Origin & Positioning: Why De-Skill, Avoid Heavy Harnesses, and Build a Thin Plugin "As Invisible as a Chair"?

- **Why Traditional Multi-Skill Hits a Dead End**: Early multi-Skill orchestration (`vaws`) helped weaker models, but with GPT-5.5+ frontier models, loading hundreds of Skill `name` and `description` entries into the Harness context caused severe context bloat, natural-language routing false positives, duplicated scripts, and overly rigid ("paranoid") reasoning. Conversely, running "naked" without tools or domain priors failed on remote Ascend NPU clusters due to missing environment variables, accidental 30-minute AscendC operator recompilations, Windows PowerShell escaping pitfalls, and unknown A2/A3/A5 hardware constraints.
- **Why Base Model Vendors Ship Sprawling Skills While We Expose a Single Entry Point (`/mindie-agent`)**: Frontier model vendors must serve *all* open-ended domains, so they collect user transcripts to train model weights and expose generic Skill/Plugin slots for long-tail DIY customization. MindIE Agent serves one invariant, laser-focused mission: **maximizing inference throughput on Ascend NPUs under fixed SLA constraints**. Our entire distilled corpus fits comfortably within megabytes to a few gigabytes.
- **Why Only a Thin Plugin (No Custom Harness, No Standalone UI)**: Because we do not train base models, we cannot out-engineer model vendors on native context management. Building a thin native Plugin lets us ride the wave of vendor model + Harness improvements (including mobile remote control in Codex, Kimi, and DeepSeek Harness) while keeping the tool **as invisible and low-friction as a chair**.
- **Two Orthogonal Pillars**: Stripping away multi-Skill leaves a single entry point (`/mindie-agent`) backed by two orthogonal pillars: **Unified Single-Responsibility MCP Tools** and **Tiered Knowledge (`L1–L4`)**.

---

## 2. Pillar 1 (Tools): Five Core Runtime Components Bridging Local Agents to Remote NPUs

1. **`remote-dev`**: 1:1 mirrors native Harness local tools with a `remote_` prefix (`remote_read`, `remote_edit`, `remote_bash`, etc.) plus background job management and reconnection recovery, eliminating SSH/escaping wheel-reinvention across multiple remote servers.
2. **`coordinator` & `npu-top`**: Automates SSH key setup on newly allocated machines, provides cross-machine build/operator cache reuse (avoiding repeated AscendC recompilations when editing Python code), and enforces topology-aware NPU and port leases (including Ascend A3 dual-Die `Phy-ID` isolation).
3. **`sim` (`mindie-sim`)**: Four-stage full-stack Roofline and performance modeling (Hardware & Operator Pipeline → Subgraph → Network Parallelism → Inference Service).
4. **`profiler` (`mindie-profiler`)**: Codifies inference bottleneck diagnosis patterns into deterministic templates that parse raw profiling traces in-place without heavy `torch_npu` re-parsing.
5. **`mindie-bench`**: Closes the system loop with end-to-end evaluation on real Ascend NPU tasks across releases.

---

## 3. Pillar 2 (Knowledge): From `L1–L3` Distillation to `L4` (RSI), Self-Healing, and Knowledge Aging

- **`L1–L3` Tiered Distillation**:
  - **`L1` Objective Hardware Axioms (`foundation_baseline`)**: Unchanging hardware constraints, memory alignment rules, and accuracy gates automatically mounted like a seatbelt via chip condition gating.
  - **`L2` Standard Micro-SOPs**: Interleaved ABBA operator benchmarking (to eliminate thermal noise), local-to-full-network verification, and standard accuracy/profiling micro-loops.
  - **`L3` Concrete Troubleshooting & Tuning Workflows**: Real-world tuning recipes with `tier` decoupled from `evidence_strength`.
- **From `L3` to `L4` (`mode="explore"`, RSI Bounded Search)**: Pure historical distillation (`L1–L3`, similar to Hermes) risks sacrificing frontier model creativity through premature convergence on historical priors. Switching into `L4` physically strips away `L3` workflows, mounts `conditional_avoid` dead-end guards, and runs "CPU parallel compile → NPU serial timing → 4-step verification (compile, accuracy, performance, leave-one-out ablation)".
- **Privacy-Safe Flywheel, Auto-Update, `diagnostics` Bot & Transcript Supervision**:
  - **Silent Background Auto-Update & `diagnostics` Issue Bot**: Because components iterate rapidly ("ship as soon as verified"), silent atomic background updates prevent users from being tortured by already-fixed bugs without daily manual upgrades; when community contribution is enabled, `diagnostics` automatically reports sanitized runtime issues for a dedicated background Bot to resolve.
  - **Dual-Layer Privacy Redaction**: Local deterministic regex + Gitleaks scrubbing at session `Stop` enables a community knowledge flywheel without ever collecting raw user data—trading a tiny amount of end-of-session tokens for the collective intelligence of the entire community.
  - **Transcript Supervision & Knowledge Aging**: Real human-Agent transcripts act as a strong supervision signal that naturally reinforces valid knowledge and overturns wrong assumptions in subsequent tasks ("nothing is permanent except change" outside hardware physical specs), while our future roadmap focuses on **knowledge aging and lifecycle curation** as frontier models internalize yesterday's tricks.

---

## 4. Control Philosophy & Human-in-the-Loop: Weak State Machine, HD Maps, and "Compiler vs. Wishing Machine"

- **Why a Deliberately Weak State Machine**: Software solves closed-world problems; Agents solve open-world problems. Frontier models are creative and smarter than any rigid workflow we could hardcode. Acting as a PM, we only switch context at the `L3 -> L4` boundary to remove prior contamination, leaving reasoning unconstrained.
- **The Autonomous Driving Metaphor (`L3` HD-Map Autopilot vs. `L4` Assisted Exploration)**: `L3` converges rapidly along proven roads mapped by others; `L4` ventures off-map where human correction and model exploration jointly forge tomorrow's new HD map.
- **Will This Project Replace Me? Three Reasons Humans Remain Irreplaceable**:
  1. **Defining real-world goals and implicit business constraints** (since real customers are leaders, frontline teams, or external clients—never another Agent);
  2. **Steering the wheel during `L4` RSI exploration** to accelerate convergence;
  3. **Taking ownership of production deliverables by treating the Agent as a "Compiler" rather than a "Wishing Machine"** — staying synchronized with the Agent's reasoning direction rather than relying on unread tens-of-thousands-of-words generated Spec/report dumps.

---

## 5. Acknowledgments

- **Colleagues & Community**: Deep gratitude to teammates and contributors for operator optimization knowledge, PD disaggregation expertise, and proposing **`mindie-bench`**; to **CANNBot** and related frameworks for distilled operator practices; to **Chunshuo Qiu (邱纯硕)**, **Xuerong Zhou (周学荣)**, **Yida Zou (邹易达)**, **Yixiang Zhu (朱翌翔)**, and **Cong Hu (胡聪)** for their distilled **`vllm-ascend`** domain knowledge and engineering experience; to **Fan Zhou (周帆)** and **Gang Long (龙钢)** for their strong support in daily maintenance and public affairs; and to my **PL and manager** for their trust and support throughout this project.
- **Frontier Models**: Special thanks to **`Gemini 4 Argon`**, **`DeepSeek V4.1 Flash`**, **`GPT-6 Astra`**, **`GPT-6.1 Sol`**, **`Kimi K3`**, and **`Grok 4.7`** for co-creating the codebase, knowledge base, benchmarks, and this note itself.

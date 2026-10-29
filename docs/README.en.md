# MindIE Agent Documentation Center

[中文](README.md) · [Back to Home](../README.en.md)

Welcome to the MindIE Agent documentation center. Here you will find the system architecture, engineering design principles, knowledge-loop design, runtime lifecycle guides, and official release records. Every document is available in both English and Chinese.

## Architecture & Design Principles

| Document (English) | 中文 | What It Covers |
|---|---|---|
| [Engineering Design Principles](design-principles.en.md) | [工程设计原则与演进准则](design-principles.md) | The core product and engineering principles governing tool boundaries, developer experience, mechanism reuse, and error visibility |
| [Contributing Guide (Agent-First Workflow)](../CONTRIBUTING.en.md) | [参与贡献指南（Agent-First 贡献规范）](../CONTRIBUTING.md) | Two-gate Agent contributing workflow: read design principles before coding, and complete the Pre-PR Checklist self-review after PR submission |
| [Architecture & Module Boundaries](architecture.en.md) | [系统架构与模块分工](architecture.md) | How native Harness plugins, the knowledge engine, remote execution, NPU observability, and diagnostics fit together |
| [Knowledge & Experience System](knowledge-system.en.md) | [知识与经验闭环设计](knowledge-system.md) | How troubleshooting sessions are redacted, indexed into lightweight Markdown packages, and shared with the community |
| [Context, Experience & Exploration Design](knowledge-context-and-exploration.en.md) | [上下文分层、经验演化与开放探索详细设计](knowledge-context-and-exploration.md) | Proposed token budgets, progressive loading, `workflow` decision experience, knowledge growth control, and `L4` exploration feedback, with source comparisons and acceptance criteria |
| [Profiler System Design](profiler-system.en.md) | [面向 Agent 的 Profiler 系统设计](profiler-system.md) | In-place Ascend profiling analysis, nanosecond interval accounting, Host-to-Device correlation, cross-run comparison, and controlled online capture |
| [NPU Performance Modeling & Simulation Design](simulation-system.md) | [面向 Agent 的 NPU 性能建模与仿真设计](simulation-system.md) | `mindie-sim` roofline bounds, operator pipeline modeling, subgraph fusion estimation, and distributed parallelism modeling |
| [Core Implementation & Knowledge Evolution Design](core-implementation-and-geak-evolution-design.md) | [核心能力落地与知识持续演进设计](core-implementation-and-geak-evolution-design.md) | Context token budget, experience distillation loop, and component implementation records |

## Runtime Lifecycle & Engineering Specifications

| Document (English) | 中文 | What It Covers |
|---|---|---|
| [Harness Boundary & Lifecycle](harness-boundary-and-lifecycle.en.md) | [宿主边界与任务生命周期](harness-boundary-and-lifecycle.md) | Task identity attribution, persistent user consent, operation lifetimes, and local state protection |
| [Execution Resource Expectations & Spec Placement](execution-resource-budget-design.md) | [执行资源预期、代码有界性与规格匹配设计](execution-resource-budget-design.md) | Code-level bounded memory/VRAM rules (Principle 18), workload resource expectations, and cross-platform (Windows/macOS/Linux) local vs. remote `fleet_probe` spec-driven placement |
| [Release Compatibility & Silent Update](release-compatibility-and-update.en.md) | [版本兼容与无感更新](release-compatibility-and-update.md) | Two-tier release architecture & product combination manifest (`channels/0.1.json`), direct component Release discovery, SemVer host compatibility, and idle atomic cutover |
| [Diagnostics & Fault Reporting](diagnostics-and-reporting.en.md) | [诊断日志与故障上报](diagnostics-and-reporting.md) | Bounded local structured logs, strict privacy redaction rules, and opt-in GitHub Issue fault reporting |
| [Native Runtime & Process Reuse](native-runtime-reuse.en.md) | [原生能力与系统机制复用](native-runtime-reuse.md) | How MindIE Agent reuses native plugin managers, `uv` locked environments, and OS process-tree primitives |
| [Enterprise Network Transport](enterprise-network.en.md) | [企业网络下的配置与传输](enterprise-network.md) | Proxy and system trust, installation, updates, background uploads and direct local APIs |
| [Tiered Testing Architecture](testing-architecture.en.md) | [分级测试体系与用例设计规范](testing-architecture.md) | Test validity redlines and the Tier 0 – Tier 3 pyramid backed by standing live A2/A3 Ascend NPU clusters |
| [L1–L4 Tiered Knowledge & System Testing Plan](knowledge-tiered-testing-plan.md) | [L1–L4 知识与系统能力分级测试方案](knowledge-tiered-testing-plan.md) | Evaluation protocols, coverage/gap matrix, concrete test suites, metrics, and execution order |

## Release Records & Roadmap

| Document (English) | 中文 | What It Covers |
|---|---|---|
| [**`0.1.2` Patch Notes**](releases/0.1.2.en.md) · [SSH Authentication Acceptance](releases/0.1.2/ssh-auth-acceptance.json) | [**`0.1.2` 补丁发布说明**](releases/0.1.2.md) · [SSH 认证验收记录](releases/0.1.2/ssh-auth-acceptance.json) | Shared SSH credentials, public-key installation and recovery, read-only password fallback, and real SSH and cross-component acceptance on macOS, Windows PowerShell, and WSL2 |
| [**`0.1.1` Patch Notes**](releases/0.1.1.en.md) · [Dev Pilot Report](releases/0.1.1/benchmark-pilot.en.md) · [Native Update Receipt](releases/0.1.1/native-update-acceptance.json) | [**`0.1.1` 补丁发布说明**](releases/0.1.1.md) · [开发试点报告](releases/0.1.1/benchmark-pilot.md) · [原生更新验收回执](releases/0.1.1/native-update-acceptance.json) | Explicit per-session `/mindie-agent` gate, whole-delivery budgeting & exploration pass-through, physical Die/HBM placement, bounded diagnostic intake, captured kernel cost contracts, behavior verifiers, streaming settlement close-race fix, offline reproduction & `G5` dev pilot, 4-host formal `0.1.2` native update acceptance, and the `release-kind=patch` pipeline |
| [**`0.1.0` Feature Milestone Record**](releases/0.1.0.en.md) | [**`0.1.0` 特性里程碑发布说明**](releases/0.1.0.md) | Full `0.0.1 → 0.1.0` capability evolution, dual-model 18-task `mindie-bench` `G0–G4` evaluation, 3-platform × 4-plugin verification, and the [`channels/0.1.json`](../channels/0.1.json) hotfix channel |
| [`0.1.0` Author's Note: Architecture & Engineering Philosophy](releases/0.1.0/design-philosophy.en.md) | [`0.1.0` 作者自述：架构演进与工程哲学](releases/0.1.0/design-philosophy.md) | Why we replaced sprawling multi-Skills with a thin plugin and two orthogonal pillars (MCP tools + `L1–L4` knowledge flywheel), the 5 core runtime components, and human-in-the-loop reflections |
| [`0.1.0` 18-Task Full Component Value Benchmark Report](releases/0.1.0/value-results.md) | [`0.1.0` 真实任务全组件价值实测报告](releases/0.1.0/value-results.md) | End-to-end `G0–G4` ablation measurements across 18 real L2/L3 tasks (109 trials) and all 7 shared runtime components on `codex + gpt-6.1-sol (xhigh)` and `dsh + deepseek-flash (max)` |
| [`0.0.3` Release Record](releases/0.0.3.en.md) | [`0.0.3` 版本发布记录](releases/0.0.3.md) | L1–L4 progressive disclosure, `profiler` and `sim` components, deterministic CANN fault triage, and 12-repository formal benchmarks |
| [`0.0.2` Release Record](releases/0.0.2.en.md) | [`0.0.2` 版本发布记录](releases/0.0.2.md) | Aligned plugin versions, exact component sources, native acceptance, and recurring ten-repository benchmarks |
| [`0.0.1` Release Record](releases/0.0.1.en.md) | [`0.0.1` 版本发布记录](releases/0.0.1.md) | Supported host matrix, paired component release mapping, verified capabilities, and known host limitations |
| [Roadmap & Next Steps](next-steps.en.md) | [后续演进路线图](next-steps.md) | Upcoming work on end-to-end benchmarks, broader host coverage, and developer experience improvements |

## Quality Audits

| Document (English) | 中文 | Scope |
|---|---|---|
| [Parallel Architecture Review & Fixes (2026-10-24)](architecture-review-20261024.md) · [2026-10-23 Simplification Record](architecture-simplification-20261023.md) | [并行架构评审与修复（2026-10-24）](architecture-review-20261024.md) | Whole-delivery budgeting, exploration pass-through, SSH cleanup & dual-Die placement, behavior task verifiers, and benchmark evidence boundary corrections |
| [2026-10-20 Code Quality Audit](audits/2026-10-20/README.en.md) | [2026-10-20 代码质量审计](audits/2026-10-20/README.md) | Cross-repository review at fixed revisions, measured line/branch coverage, findings, and staged changes; not a claim that defects are fixed or hardware acceptance is complete |

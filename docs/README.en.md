# MindIE Agent Documentation Center

[中文](README.md) · [Back to Home](../README.en.md)

Welcome to the MindIE Agent documentation center. Here you will find the system architecture, engineering design principles, knowledge-loop design, runtime lifecycle guides, and official release records. Every document is available in both English and Chinese.

## Architecture & Design Principles

| Document (English) | 中文 | What It Covers |
|---|---|---|
| [Engineering Design Principles](design-principles.en.md) | [工程设计原则与演进准则](design-principles.md) | The core product and engineering principles governing tool boundaries, developer experience, mechanism reuse, and error visibility |
| [Architecture & Module Boundaries](architecture.en.md) | [系统架构与模块分工](architecture.md) | How native Harness plugins, the knowledge engine, remote execution, NPU observability, and diagnostics fit together |
| [Knowledge & Experience System](knowledge-system.en.md) | [知识与经验闭环设计](knowledge-system.md) | How troubleshooting sessions are redacted, indexed into lightweight Markdown packages, and shared with the community |

## Runtime Lifecycle & Engineering Specifications

| Document (English) | 中文 | What It Covers |
|---|---|---|
| [Harness Boundary & Lifecycle](harness-boundary-and-lifecycle.en.md) | [宿主边界与任务生命周期](harness-boundary-and-lifecycle.md) | Task identity attribution, persistent user consent, operation lifetimes, and local state protection |
| [Release Compatibility & Silent Update](release-compatibility-and-update.en.md) | [版本兼容与无感更新](release-compatibility-and-update.md) | Paired component/plugin release workflow, SemVer host compatibility matching, and background silent updates |
| [Diagnostics & Fault Reporting](diagnostics-and-reporting.en.md) | [诊断日志与故障上报](diagnostics-and-reporting.md) | Bounded local structured logs, strict privacy redaction rules, and opt-in GitHub Issue fault reporting |
| [Native Runtime & Process Reuse](native-runtime-reuse.en.md) | [原生能力与系统机制复用](native-runtime-reuse.md) | How MindIE Agent reuses native plugin managers, `uv` locked environments, and OS process-tree primitives |
| [Tiered Testing Architecture](testing-architecture.en.md) | [分级测试体系与用例设计规范](testing-architecture.md) | Test validity redlines and the Tier 0 – Tier 3 pyramid backed by standing live A2/A3 Ascend NPU clusters |

## Release Records & Roadmap

| Document (English) | 中文 | What It Covers |
|---|---|---|
| [`0.0.2` Release Record](releases/0.0.2.en.md) | [`0.0.2` 版本发布记录](releases/0.0.2.md) | Aligned plugin versions, exact component sources, native acceptance, and recurring ten-repository benchmarks |
| [`0.0.1` Release Record](releases/0.0.1.en.md) | [`0.0.1` 版本发布记录](releases/0.0.1.md) | Supported host matrix, paired component release mapping, verified capabilities, and known host limitations |
| [Roadmap & Next Steps](next-steps.en.md) | [后续演进路线图](next-steps.md) | Upcoming work on end-to-end benchmarks, broader host coverage, and developer experience improvements |

## Quality Audits

| Document (English) | 中文 | Scope |
|---|---|---|
| [2026-10-20 Code Quality Audit](audits/2026-10-20/README.en.md) | [2026-10-20 代码质量审计](audits/2026-10-20/README.md) | Cross-repository review at fixed revisions, measured line/branch coverage, findings, and staged changes; not a claim that defects are fixed or hardware acceptance is complete |

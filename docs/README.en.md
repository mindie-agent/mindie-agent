# MindIE Agent Documentation Index

[中文](README.md) · [Back to Home](../README.en.md)

This directory contains the system architecture, nine core design principles, cross-component contracts, runtime specifications, and official release records for MindIE Agent. Every document is available in both English and Chinese.

## Core Architecture & Principles

| Document (English) | 中文 | Description |
|---|---|---|
| [Nine Design Principles](design-principles.en.md) | [九条设计原则](design-principles.md) | Foundational engineering principles governing all MindIE Agent design, code, configuration, and release decisions |
| [Architecture & Domain Boundaries](architecture.en.md) | [系统架构与领域边界](architecture.md) | Component ownership, architectural layers, and runtime boundaries across Harness plugins and shared runtimes |
| [Knowledge & Experience System](knowledge-system.en.md) | [知识与经验闭环设计](knowledge-system.md) | Deterministic transcript projection, multi-stage redaction, native small-model navigation indexing, two-layer storage, and community sharing |

## Runtime Contracts & Engineering Specifications

| Document (English) | 中文 | Description |
|---|---|---|
| [Harness Boundary & Lifecycle](harness-boundary-and-lifecycle.en.md) | [Harness 边界与生命周期](harness-boundary-and-lifecycle.md) | Task identity attribution, persistent consent, operation lifetimes, authoritative state recovery, and single-binding installation contract |
| [Release Compatibility & Silent Update](release-compatibility-and-update.en.md) | [发布兼容与静默更新](release-compatibility-and-update.md) | Paired component/plugin release checklist, Harness compatibility range selection, and silent background cutover contract |
| [Diagnostics & Fault Reporting](diagnostics-and-reporting.en.md) | [日志、故障定位与自动 Issue](diagnostics-and-reporting.md) | Bounded local structured logs, privacy redaction boundaries, opt-in GitHub Issue reporting, and retry budgets |
| [Native Runtime & Process Reuse](native-runtime-reuse.en.md) | [原生更新、Hook 与进程管理复用](native-runtime-reuse.md) | Architectural rationale and evidence for reusing native plugin managers, `uv` locked environments, and OS process-tree primitives |

## Release Records & Roadmap

| Document (English) | 中文 | Description |
|---|---|---|
| [`0.0.1` Release Record](releases/0.0.1.en.md) | [`0.0.1` 发布记录](releases/0.0.1.md) | `0.0.1` supported matrix, paired component Release mapping, six-environment verification evidence, and known limitations |
| [Roadmap & Next Steps](next-steps.en.md) | [后续迭代](next-steps.md) | Current engineering priorities, business benchmark roadmap, and upstream host issue tracking |

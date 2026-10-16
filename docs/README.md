# MindIE Agent 文档索引

[English](README.en.md) · [返回首页](../README.md)

本目录维护 MindIE Agent 的总体架构、核心设计原则、跨组件契约、运行机制与正式版本发布记录。所有核心文档均提供中英双语版本。

## 核心架构与原则

| 文档 | English | 说明 |
|---|---|---|
| [九条设计原则](design-principles.md) | [Nine Design Principles](design-principles.en.md) | MindIE Agent 全部架构、代码、配置与发布决策的最高准则 |
| [系统架构与领域边界](architecture.md) | [Architecture & Domain Boundaries](architecture.en.md) | 宿主插件、共享知识运行时、远端开发与可观测组件的职责分工与交互边界 |
| [知识与经验闭环设计](knowledge-system.md) | [Knowledge & Experience System](knowledge-system.en.md) | 公开对话确定性投影、多层隐私脱敏、原生小模型检索导航、双层存储与社区分享闭环 |

## 运行契约与工程机制

| 文档 | English | 说明 |
|---|---|---|
| [Harness 边界与生命周期](harness-boundary-and-lifecycle.md) | [Harness Boundary & Lifecycle](harness-boundary-and-lifecycle.en.md) | 任务身份归属、持久授权、操作寿命、权威状态恢复与单安装绑定契约 |
| [发布兼容与静默更新](release-compatibility-and-update.md) | [Release Compatibility & Silent Update](release-compatibility-and-update.en.md) | 组件与插件配套发布检查清单、Harness 版本兼容区间筛选与后台静默切换规范 |
| [日志、故障定位与自动 Issue](diagnostics-and-reporting.md) | [Diagnostics & Fault Reporting](diagnostics-and-reporting.en.md) | 有界本地结构化日志、隐私脱敏边界、独立授权故障上报与预算控制 |
| [原生更新、Hook 与进程管理复用](native-runtime-reuse.md) | [Native Runtime & Process Reuse](native-runtime-reuse.en.md) | 复用宿主插件管理器、`uv` 锁定环境与操作系统原生进程树管理的架构决策与依据 |

## 发布记录与路线图

| 文档 | English | 说明 |
|---|---|---|
| [`0.0.1` 发布记录](releases/0.0.1.md) | [`0.0.1` Release Record](releases/0.0.1.en.md) | 首发 `0.0.1` 支持矩阵、配套组件 Release 映射、六组合实机验收证据与已知限制 |
| [后续迭代](next-steps.md) | [Roadmap & Next Steps](next-steps.en.md) | 现阶段工程重点、业务效果基准验证与上游已知限制跟进计划 |

# MindIE Agent 文档中心

[English](README.en.md) · [返回首页](../README.md)

欢迎来到 MindIE Agent 文档中心。这里汇总了 MindIE Agent 的整体架构、工程设计原则、知识闭环机制、跨组件协作约定以及版本发布记录。核心文档提供中英双语入口。

## 架构与设计原则

| 文档 | English | 核心内容 |
|---|---|---|
| [工程设计原则与演进准则](design-principles.md) | [Engineering Design Principles](design-principles.en.md) | 指导 MindIE Agent 工具边界、用户体验、机制复用与容错语义的工程准则 |
| [系统架构与模块分工](architecture.md) | [Architecture & Module Boundaries](architecture.en.md) | 宿主插件、知识引擎、远端执行、集群观测与诊断组件如何协同工作 |
| [知识与经验闭环设计](knowledge-system.md) | [Knowledge & Experience System](knowledge-system.en.md) | 本地实战经验如何脱敏沉淀、生成检索导航，并与社区公共知识库双向流转 |
| [上下文分层、经验演化与开放探索详细设计](knowledge-context-and-exploration.md) | [Context, Experience & Exploration Design](knowledge-context-and-exploration.en.md) | 后续设计：Token 预算、渐进加载、L3 决策经验、知识增长控制与探索回流；含开源对照和验收方案 |
| [面向 Agent 的 Profiler 系统设计](profiler-system.md) | [Profiler System Design](profiler-system.en.md) | 昇腾 Profiling 原地解析、纳秒区间计量、Host-Device 异步关联、跨 Run 对比与按需采集设计 |
| [面向 Agent 的 NPU 仿真与边界求解系统设计](simulation-system.md) | — | `mindie-sim` 四层仿真（硬件/热态、算子微阶段周期求解、子图跨界融合、整网并行）及可编码 vs 不可硬编码边界 |
| [核心能力落地与 GEAK 演化架构设计](core-implementation-and-geak-evolution-design.md) | — | L1–L4 知识上下文预算、三维经验演化与组件化落地记录 |

## 运行机制与工程规范

| 文档 | English | 核心内容 |
|---|---|---|
| [宿主边界与任务生命周期](harness-boundary-and-lifecycle.md) | [Harness Boundary & Lifecycle](harness-boundary-and-lifecycle.en.md) | 任务身份识别、持久授权设置、操作生命周期管理与本地状态保护机制 |
| [版本兼容与无感更新](release-compatibility-and-update.md) | [Release Compatibility & Silent Update](release-compatibility-and-update.en.md) | 组件与插件配套发布规范、宿主版本兼容匹配及后台静默更新流程 |
| [诊断日志与故障上报](diagnostics-and-reporting.md) | [Diagnostics & Fault Reporting](diagnostics-and-reporting.en.md) | 本地结构化诊断日志、隐私脱敏红线与可选的 GitHub Issue 自动故障上报 |
| [原生能力与系统机制复用](native-runtime-reuse.md) | [Native Runtime & Process Reuse](native-runtime-reuse.en.md) | 为什么及如何复用宿主插件市场、`uv` 锁定环境与操作系统原生进程树管理 |
| [分级测试体系与用例设计规范](testing-architecture.md) | [Tiered Testing Architecture](testing-architecture.en.md) | 用例有效性红线与基于常备 A2/A3 昇腾真机的 Tier 0 ~ Tier 3 分级验证体系 |
| [L1–L4 知识与系统能力分级测试方案](knowledge-tiered-testing-plan.md) | — | 开源评测协议、现有覆盖与缺口、具体用例、评价指标及实施顺序 |

## 版本记录与路线图

| 文档 | English | 核心内容 |
|---|---|---|
| [`0.0.2` 版本发布记录](releases/0.0.2.md) | [`0.0.2` Release Record](releases/0.0.2.en.md) | 插件统一版本、精确组件源码、实机验收范围与常态化十仓 benchmark |
| [`0.0.1` 版本发布记录](releases/0.0.1.md) | [`0.0.1` Release Record](releases/0.0.1.en.md) | `0.0.1` 支持客户端矩阵、配套组件版本映射、实机验证范围与已知限制 |
| [后续演进路线图](next-steps.md) | [Roadmap & Next Steps](next-steps.en.md) | 下一阶段重点推进的业务基准评测、更多宿主支持与体验优化计划 |

# MindIE Agent 文档中心

[English](README.en.md) · [返回首页](../README.md)

欢迎来到 MindIE Agent 文档中心。这里汇总了 MindIE Agent 的整体架构、工程设计原则、知识闭环机制、跨组件协作约定以及版本发布记录。核心文档提供中英双语入口。

## 架构与设计原则

| 文档 | English | 核心内容 |
|---|---|---|
| [工程设计原则与演进准则](design-principles.md) | [Engineering Design Principles](design-principles.en.md) | 指导 MindIE Agent 工具边界、用户体验、机制复用与容错语义的工程准则 |
| [参与贡献指南（Agent-First 贡献规范）](../CONTRIBUTING.md) | [Contributing Guide](../CONTRIBUTING.en.md) | 面向 Agent 的两阶段贡献门禁：开发前先读设计原则、提交 PR 后完成 Pre-PR Checklist 自检 |
| [系统架构与模块分工](architecture.md) | [Architecture & Module Boundaries](architecture.en.md) | 宿主插件、知识引擎、远端执行、集群观测与诊断组件如何协同工作 |
| [知识与经验闭环设计](knowledge-system.md) | [Knowledge & Experience System](knowledge-system.en.md) | 本地实战经验如何脱敏沉淀、生成检索导航，并与社区公共知识库双向流转 |
| [上下文分层、经验演化与开放探索详细设计](knowledge-context-and-exploration.md) | [Context, Experience & Exploration Design](knowledge-context-and-exploration.en.md) | 后续设计：Token 预算、渐进加载、经验修订与探索回流；含 OO-Harness 条件化策略复用、组件分工与实施步骤 |
| [面向 Agent 的 Profiler 系统设计](profiler-system.md) | [Profiler System Design](profiler-system.en.md) | 昇腾 Profiling 原地解析、纳秒区间计量、Host-Device 异步关联、跨 Run 对比与按需采集设计 |
| [面向 Agent 的通用性能建模系统](simulation-system.md) | — | `mindie-sim v0.8.1` 五层统一因果建模、4D 效率拆解、SLA 硬件配比推演、算子族源码实现与 280 Decode / 15 Prefill / 856 DSH 集群验证 |
| [Profiler 与 Sim 的结构复用和实测映射](profiler-sim-structure.md) | — | `mindie-model-structure/1` 结构导出、同构算子集合（Cohort）对账、`auto_segment_decode_forwards` 拓扑引导切分与多集群回放结果 |
| [`mindie-sim` 接口演进与消费者集成说明](simulation-consumer-migration.md) | — | `0.7.x -> 0.8.x` CLI/API 映射以及在四端宿主插件、`profiler` 与 `mindie-bench` 中的集成状态 |
| [A3 预测性能与应达性能双模型方案](a3-performance-modeling-plan.md) | — | 历史双模型设计与机制追溯；不再规定新版执行入口或实测门槛 |
| [A3 最低模型覆盖集](a3-model-coverage.md) | — | 历史 se-tools 九模型的逐层结构与状态参考；新版范围不限定 A3 |
| [A3 双模型实现与验收](a3-performance-modeling-acceptance.md) | — | 旧实现的调度对照、A3 数据与算法检查记录；不作为重写版替换验收 |
| [A5 通信展开与竞争校准 TODO](a5-communication-calibration-todo.md) | — | 待 A5 实机采集的 AICPU/AIV 展开、资源竞争、样本协议及回填验收矩阵 |
| [核心能力落地与知识持续演进设计](core-implementation-and-geak-evolution-design.md) | — | 知识上下文预算、经验沉淀回流与组件化落地记录 |

## 运行机制与工程规范

| 文档 | English | 核心内容 |
|---|---|---|
| [宿主边界与任务生命周期](harness-boundary-and-lifecycle.md) | [Harness Boundary & Lifecycle](harness-boundary-and-lifecycle.en.md) | 任务身份识别、持久授权设置、操作生命周期管理与本地状态保护机制 |
| [执行资源预期、代码有界性与规格匹配设计](execution-resource-budget-design.md) | — | 代码层内存/显存有界性红线（Principle 18）、工作负载资源预期声明，以及 Windows/macOS/Linux 本机与远端 `fleet_probe` 硬件规格自动匹配分流 |
| [版本兼容与无感更新](release-compatibility-and-update.md) | [Release Compatibility & Silent Update](release-compatibility-and-update.en.md) | 双层版本演进与产品组合清单（`channels/0.1.json`）、组件仓库正式 Release 直接发现、宿主兼容匹配及空闲无感切换 |
| [诊断日志与故障上报](diagnostics-and-reporting.md) | [Diagnostics & Fault Reporting](diagnostics-and-reporting.en.md) | 本地结构化诊断日志、隐私脱敏红线与可选的 GitHub Issue 自动故障上报 |
| [原生能力与系统机制复用](native-runtime-reuse.md) | [Native Runtime & Process Reuse](native-runtime-reuse.en.md) | 为什么及如何复用宿主插件市场、`uv` 锁定环境与操作系统原生进程树管理 |
| [企业网络下的配置与传输](enterprise-network.md) | [Enterprise Network Transport](enterprise-network.en.md) | 代理与系统证书、安装更新、后台上传及本机接口直连 |
| [分级测试体系与用例设计规范](testing-architecture.md) | [Tiered Testing Architecture](testing-architecture.en.md) | 用例有效性红线与基于常备 A2/A3 昇腾真机的 Tier 0 ~ Tier 3 分级验证体系 |
| [L1–L4 架构闭环与知识飞轮分级测试方案](knowledge-tiered-testing-plan.md) | — | 开源评测协议、现有覆盖与缺口；含条件化策略选择 A/B/C 最小对照、输入隔离、完整成本与实施判据 |

## 版本记录与路线图

| 文档 | English | 核心内容 |
|---|---|---|
| [**`0.1.5` 补丁发布说明**](releases/0.1.5.md) | [**`0.1.5` Patch Notes**](releases/0.1.5.en.md) | 新增第五款官方原生插件 Google Antigravity（`mindie-agent-agy v0.1.0`）与 7 大组件双向契约适配，完成口语化报障语料 `G0–G5` 全矩阵基准验证（66 场 L2/L3 + G3/G4/G5 飞轮全过） |
| [**`0.1.4` 补丁发布说明**](releases/0.1.4.md) · [自动升级验收](releases/0.1.4/automatic-update-acceptance.json) | [**`0.1.4` Patch Notes**](releases/0.1.4.en.md) | 按信息缺口检索、统一精读预算、精确依赖引用、受管组件自动绑定更新；保留复杂任务非退化尚未通过的结论 |
| [**`0.1.3` 补丁发布说明**](releases/0.1.3.md) | [**`0.1.3` Patch Notes**](releases/0.1.3.en.md) | 四宿主（Codex / Claude Code / Kimi Code / DSH）三路 MCP 注册与 5 个本地组件/诊断工具面完备、`profiler 0.5.1` 流式校验与 SQLite 超时收敛 |
| [**`0.1.2` 补丁发布说明**](releases/0.1.2.md) · [SSH 认证验收记录](releases/0.1.2/ssh-auth-acceptance.json) | [**`0.1.2` Patch Notes**](releases/0.1.2.en.md) · [SSH Authentication Acceptance](releases/0.1.2/ssh-auth-acceptance.json) | 统一 SSH 凭据、公钥安装与恢复、只读密码回退，macOS / Windows PowerShell / WSL2 真实 SSH 与跨组件复用验收 |
| [**`0.1.1` 补丁发布说明**](releases/0.1.1.md) · [开发试点报告](releases/0.1.1/benchmark-pilot.md) · [原生更新验收回执](releases/0.1.1/native-update-acceptance.json) | [**`0.1.1` Patch Notes**](releases/0.1.1.en.md) · [Dev Pilot Report](releases/0.1.1/benchmark-pilot.en.md) · [Native Update Receipt](releases/0.1.1/native-update-acceptance.json) | 知识功能按会话显式 `/mindie-agent` 启用、整包预算与探索透传、双 Die/实测 HBM 放置、有界诊断准入、捕获 Kernel 耗时绑定、行为判分器、流结算关闭竞态修复、离线工程复现与 `G5` 开发试点、四端 `0.1.2` 正式原生更新验收及维护补丁发布链路 |
| [**`0.1.0` 特性里程碑发布说明**](releases/0.1.0.md) | [**`0.1.0` Feature Milestone Record**](releases/0.1.0.en.md) | `0.0.1 → 0.1.0` 完整能力演进、`mindie-bench` 双模型 18 任务 `G0–G4` 真机实测、三端 × 四插件全量验收与 [`channels/0.1.json`](../channels/0.1.json) 单组件热修通道 |
| [`0.1.0` 作者自述：架构演进与工程哲学](releases/0.1.0/design-philosophy.md) | [`0.1.0` Author's Note: Architecture & Engineering Philosophy](releases/0.1.0/design-philosophy.en.md) | 为什么砍掉多 Skill、只做薄插件与双支柱（MCP 工具 + `L1–L4` 知识飞轮）、五大核心组件设计初衷与人机协同思考 |
| [`0.1.0` 真实任务全组件价值实测报告](releases/0.1.0/value-results.md) | [`0.1.0` 18-Task Full Component Value Benchmark Report](releases/0.1.0/value-results.md) | `codex + gpt-6.1-sol (xhigh)` 与 `dsh + deepseek-flash (max)` 在 18 个 L2/L3 真实任务（109 轮 Trial）与 7 大组件上的 `G0–G4` 消融数据 |
| [`0.0.3` 版本发布记录](releases/0.0.3.md) | [`0.0.3` Release Record](releases/0.0.3.en.md) | L1–L4 渐进式知识披露、`profiler` 与 `sim` 组件发布、CANN 确定性故障分诊及十二仓正式 benchmark |
| [`0.0.2` 版本发布记录](releases/0.0.2.md) | [`0.0.2` Release Record](releases/0.0.2.en.md) | 插件统一版本、精确组件源码、实机验收范围与常态化十仓 benchmark |
| [`0.0.1` 版本发布记录](releases/0.0.1.md) | [`0.0.1` Release Record](releases/0.0.1.en.md) | 支持客户端矩阵、配套组件版本映射、实机验证范围与已知限制 |
| [后续演进路线图](next-steps.md) | [Roadmap & Next Steps](next-steps.en.md) | 下一阶段重点推进的业务基准评测、更多宿主支持与体验优化计划 |

## 质量审计

| 文档 | English | 范围 |
|---|---|---|
| [2026-10-29 基准判分器加固与历史归档复判报告](audits/2026-10-23-mindie-bench-integrity.md) | — | 20 个 `mindie-bench` 任务的真实子进程行为级 Oracle 加固（109 项三态与辅助函数/类控制全过）及 74 轮主实验零模型行为级复判账本 |
| [并行架构评审与修复（2026-10-24）](architecture-review-20261024.md) · [前次简化记录（2026-10-23）](architecture-simplification-20261023.md) | — | 整包预算与去重记账、探索透传、SSH 清理与双 Die 容量放置、评测判分器与证据边界审查记录 |
| [2026-10-20 代码质量审计](audits/2026-10-20/README.md) | [2026-10-20 Code Quality Audit](audits/2026-10-20/README.en.md) | 固定源码版本的跨仓扫描、实测行/分支覆盖率、审查结论与分批修改计划 |

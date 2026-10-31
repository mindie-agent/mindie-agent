# MindIE Agent 演进路线与下一步计划

[English](next-steps.en.md) · [返回文档中心](README.md)

系统整体架构与知识闭环设计请参阅 [系统架构与模块分工](architecture.md) 与 [知识与经验闭环设计](knowledge-system.md)，工程准则请参阅 [工程设计原则与演进准则](design-principles.md)。

系统已完成首个正式里程碑版本 **[`v0.1.0`](releases/0.1.0.md)**（[实测报告](releases/0.1.0/value-results.md) · [作者自述](releases/0.1.0/design-philosophy.md)）及 `v0.1.1`–[`v0.1.4`](releases/0.1.4.md) 持续演进（版本锁定见 [`channels/0.1.json`](../channels/0.1.json)），落地 `knowledge v0.13.7` 的按需信息缺口检索、L1–L4 渐进式披露、Token 预算门控、`G3` C6 经验蒸馏飞轮与 `G4` `mode="explore"` 独立探索，补齐 7 大昇腾公共知识库（`450` 个结构化单元），发布统一五层因果建模的 `mindie-sim v0.8.1` 与支持拓扑引导 Decode 自动切分的 `mindie-profiler v0.5.3`（完成 280 Decode + 15 Prefill 收敛及 856 例 DSH 集群 98.25% 盲测泛化），交付 `remote-dev v0.11.2` 共享 SSH 认证、`diagnostics v0.5.4` CANN/`plog` 确定性分诊、`coordinator v0.7.0` 昇腾 A5 拓扑预检，并完成 `mindie-bench` 20 个任务的真实子进程行为级 Oracle 加固与历史归档零模型复判（各版本详情见[版本发布记录](README.md#版本记录与路线图)）。

---

## 下一阶段推进重点

1. **端到端多宿主产品矩阵（`P0–P3`）常态化评测与知识飞轮演进**
   - 基于加固后的 `mindie-bench` 行为级 Oracle 持续扩展跨模型、跨宿主的端到端研发任务与跨任务经验迁移（`P0–P3`）评测覆盖，跟踪 L1–L4 渐进式披露与子上下文事实包在长周期复杂算子与框架调优任务中的净工程收益。
2. **昇腾 A5（950）实机通信展开与竞争校准回填**
   - 按照 [A5 通信展开与竞争校准计划](a5-communication-calibration-todo.md)，在常备 A5 环境上完成 AICPU/AIV 通信展开、资源竞争样本采集与 `mindie-sim` / `mindie-profiler` 参数回填验证。
3. **7 大昇腾公共知识库与开箱即用 Skills 持续扩充**
   - 在 [`knowledge-vllm-ascend`](https://github.com/mindie-agent/knowledge-vllm-ascend)、[`knowledge-operators`](https://github.com/mindie-agent/knowledge-operators)、[`knowledge-infer-core`](https://github.com/mindie-agent/knowledge-infer-core)、[`knowledge-infer-distributed`](https://github.com/mindie-agent/knowledge-infer-distributed)、[`knowledge-infer-observability`](https://github.com/mindie-agent/knowledge-infer-observability)、[`knowledge-infer-ops-compat`](https://github.com/mindie-agent/knowledge-infer-ops-compat)、[`knowledge-agent-engineering`](https://github.com/mindie-agent/knowledge-agent-engineering) 与 [`awesome-mindie-skills`](https://github.com/mindie-agent/awesome-mindie-skills) 中持续沉淀经过真机验证的分级知识单元与专项指南。
4. **远端环境编排（`coordinator`）、性能组件（`profiler` / `sim`）与宿主插件的深度协同**
   - 四端宿主插件已通过 `knowledge`、`remote` 与 `components` 三路 MCP 统一暴露 `remote-dev`、`coordinator`、`profiler`、`sim` 与 `diagnostics`；后续将围绕高频调优闭环（“Profiling 瓶颈定位 → Sim 候选融合/配比推演 → 远端容器验证”）进一步打磨一键协同体验。
5. **上游宿主 CLI 问题跟进**
   - 持续跟踪 OpenAI Codex CLI 在中断子代理（`spawn_agent`）时向在途 MCP 工具调用传递取消信号的上游修复进展；待上游合入发布后及时验证并更新 `harness-compatibility.json` 版本区间。

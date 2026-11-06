# `mindie-sim` 接口演进与消费者集成说明

[仿真系统设计](simulation-system.md) · [结构复用与实测映射](profiler-sim-structure.md) · [系统架构](architecture.md) · [版本兼容与更新](release-compatibility-and-update.md) · [文档中心](README.md)

本文记录 `mindie-sim` 从早期 `0.7.x` 专用四层 CLI 升级至 `0.8.x / 0.9.x`（当前正式版 `v0.9.4`）五层统一因果建模引擎后的接口映射关系，以及在五大原生宿主插件（Claude Code、OpenAI Codex、Kimi Code、DeepSeek Harness、Google Antigravity）、`mindie-profiler`（`v0.5.6`）与 `mindie-bench`（`v0.4.6`）中的集成状态。

---

## 1. 旧版入口到 `v0.8.x / v0.9.x` 统一接口的映射

`mindie-sim v0.8.x / v0.9.x` 废除了早期按硬件或阶段拆裂的 `hardware / pipeline / subgraph / net`、`a3-*` 与 `operator-plan` 入口，统一收敛为围绕 `Case`、`OpSpec` 与 `mindie-model-structure/1` 的公共 API 与 CLI：

| 早期 `0.7.x` 入口 / 对象 | `v0.8.x / v0.9.x` 正式接口 | 核心语义改进 |
| --- | --- | --- |
| `a3_framework.predict` / A3 专用配置 | `mindie_sim.predict(Case)` / `mindie-sim compose\|predict\|efficiency\|sla\|sweep\|skew` | 硬件无关统一前端：支持从模型 ID / HF 配置确定性合成 `Case`（`compose`），建模 `async_scheduling` 延迟释放 KV 显存，输出时延、4D 效率拆解、SLA 并发前沿、多维并行/PD 分离 Pareto 前沿（`sweep`）与多 DP 偏斜/MoE EPLB/Chunked-Prefill 干扰屏障力学（`skew`） |
| `operator-plan` / `operator_plan_report` | `mindie_sim.operator_costs` / `mindie-sim operators CASE` | 经生产 `RecipeBook` 与 `runtime.kernels.lowerings` 展开真实算子边界，输出 `sum_of_isolated_device_programs` |
| `subgraph` / `analyze_subgraph_fusion` | `mindie_sim.graph_costs` / `mindie-sim graph CASE` | 在同一因果引擎中组合数据依赖、多流并发、片上 Buffer 容量与显式 `native_fusion` 子图，精确核算消除的 HBM 读写与重复 Launch |
| `net` / 独立 `should` 预测器 | `mindie_sim.study` / `mindie-sim study MANIFEST` | 纯模型成本（`scope="body"\|"model"`）与服务级请求调度分离；`study` 在统一引擎和一致边界下对显式候选方案排序 |
| `PhysicalCalibration` / 整网残差补丁 | `calibrate` / `bind-profiler` / `fit-rate` / `fit-service` | 严禁将整网残差回填为算子倍率；仅允许在声明适用域内绑定具有来源身份的原语样本或单资源通道服务速率，严格隔离训练集与 Held-out 盲测集 |
| `profiled_kernels` + `--operator-config` | `mindie-model-structure/1` + `mindie_sim.cohort_comparison` | 由 `mindie-sim` 导出无时延模型结构、`mindie-profiler` 聚合实测同构集合（Cohort）并自动切分 Decode/Prefill 主体，再由 `sim` 完成分档精度对账 |

---

## 2. 跨仓库消费者集成状态

截至当前正式版本组合（见 [`channels/0.1.json`](../channels/0.1.json)），所有下游组件与宿主插件均已完成向 `mindie-sim v0.9.4` 及 `mindie-profiler v0.5.6` 接口的对齐与正式发布：

| 消费者组件 / 插件 | 当前正式版本 | 集成方式与验证闭环 |
| --- | --- | --- |
| **`mindie-agent-codex`** | `v0.1.21` | 通过 `components` MCP 服务暴露 `sim` 与 `profiler` 工具，支持 `compose`、`predict`、`efficiency`、`sla`、`sweep`、`skew`、`operators`、`graph`、`study`、`accuracy` 及结构导出 |
| **`mindie-agent-cc`** | `v0.1.17` | 通过 `components` MCP 服务统一注册 `sim`、`profiler`、`coordinator`、`diagnostics_status` 与 `diagnostics_bundle`，工具超时与返回契约五端一致 |
| **`mindie-agent-kimi`** | `v0.1.17` | 在 Kimi Code `mindie-tools` / `components` MCP 桥中同步暴露新版 `sim` 与 `profiler` 接口及参数说明，支持受管 Python 模块命令自动迁移 |
| **`mindie-agent-dsh`** | `v0.1.16` | 通过 DSH `component_tools.py` 透传统一组件工具目录，支持在 DSH 会话中直接调用新版 `sim` 与 `profiler` |
| **`mindie-agent-agy`** | `v0.1.8` | 通过 Google Antigravity `mindie-tools` MCP 服务暴露 `sim`、`profiler`、`coordinator`、`npu_top`、`diagnostics_*` 与 `mindie_status` |
| **`mindie-profiler`** | `v0.5.6` | 原生消费 `mindie-model-structure/1` 完成事件关联、同构 Cohort 统计与 Decode/Prefill 拓扑引导切分（含 `AddRmsNormQuant`、`SparseFlashMla` 与 DP-partner EP 对齐），并提供 Wave 5 三芯片 `1,653 / 1,653 <= 10%` 样本内校准流水线 |
| **`mindie-bench`** | `v0.4.6` | `value_sim.py` 与 `value_scenarios.py` 全面采用公开的 `target_operators`、`operator_costs`、`target_graphs`、`graph_costs` 与 `predict` 接口，在 `sim-causal-modeling-boundaries` 场景中验证因果依赖、图/服务边界与资源释放 |

---

## 3. 核心契约与回归验证要点

1. **因果与资源守恒验证**：
   - 多 EP 参与者共享链路或存在 Rendezvous 同步时，Timeline 显式区分 `local_ready_ms`、`ready_ms` 与 `rendezvous_wait_ms`；
   - 包含多模态媒体塔（Media Tower）的 Prefill 模型必须显式指定 `--media-tokens-per-sequence`，确保视觉/音频算子 FLOPs 与读写字节完整计入；
   - 图捕获模式（`ACLGraph`）继承后按单次图提交核算 Host Launch，不把 Eager 模式的逐算子 Python 下发间隔混入静态图执行。
2. **有界内存与隔离环境验证**：
   - 14 个完整大图模型（Qwen3.8/3.5/3.6、Kimi K3、GLM5.3、DeepSeek V4.1 等）延迟展开分析的进程峰值 RSS 仅为 **`287.6 MiB`**（`< 512 MiB`），执行完毕后存活任务与程序引用计数归零；
   - 五端插件组件桥测试、`mindie-bench` 消费者测试、280 个 Decode 用例、15 个 Prefill 用例、Wave 5 跨 A2/A3/A5 的 1,653 份实测 Profile 样本内校准评估（`100.00% <= 10%`）及独立 856 个 DSH 集群泛化用例（整体 `841/856 = 98.25% <= 15%`，其中 561 例独立 Held-out 盲测 `546/561 = 97.33% <= 15%`）全部通过。

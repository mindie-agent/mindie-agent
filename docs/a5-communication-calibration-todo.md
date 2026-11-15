# A5 通信展开与竞争校准 TODO

[A3 双模型方案](a3-performance-modeling-plan.md) · [实现与验收记录](a3-performance-modeling-acceptance.md)

2026-10-21 按用户要求单独保留。**状态：2026-10-21 / 2026-10-22 的 A5 采集已导入并集成到 `mindie-sim`（`mindie_sim/observations/a5_comm_calibration.py`）**：UB-mesh `W2/W4/W8`（`rack06` CANN `9.1.0`）与 `W2/W8`（`rack08` CANN `9.0.0`，独立栈、不跨栈池化）单机采集，多机 URMA `W16`（2 节点 `rack06os5`–`rack06os6`）/ `W32`（4 节点 `rack06os4`–`rack06os7`）collective/P2P，以及 `bf16` / `int8` / `fp8-e4m3` MC2 链分解 campaign（`/Volumes/data/mindie-sim-data/a5/`）均已回填；未确认的 `AICPU`/`AIV` 展开 trace 与剩余 cell 保留在确定性补测清单中。

## 1. 首先确认环境和实际展开

- [x] 记录准确 SKU、拓扑与软件栈：`Ascend950DT_9582:ub`，单机 8 rank intra-node UB mesh（`W2/W4/W8`）加 2/4 节点 URMA scale-out（`W16` 2 节点 `rack06os5`–`rack06os6`、`W32` 4 节点 `rack06os4`–`rack06os7`）；`rack06`/`rack06os4`–`rack06os7` 为 CANN `9.1.0`，`rack08` 为 CANN `9.0.0`，按软件栈分区且不跨栈池化。
- [ ] 确认每种目标 collective 可用的 Host、AICPU、AIV 或混合展开方式，并用 `msprof` 记录逐 collective 的 observed kernel/task trace；2026-10-21/22 的 Torch 级计时中 `observed_expansion_mode` 仍为 `"not_observed"`，该缺口由 `build_a5_followup_manifest()` 以 `expansion_regime:aicpu/aiv` 导出。
- [x] 严格分离 `requested_expansion_mode` 与 `observed_expansion_mode`：`resolve_expansion_regime` 只在 observed 或单一 profiler evidence 确认时提升，冲突证据保持 `unspecified`。
- [x] 对无法确认的路径保留 `unspecified`（`requested_aicpu_unconfirmed` / `requested_aiv_unconfirmed`），并阻止未确认或证据冲突的行进入已确认 `aicpu`/`aiv` 服务曲线拟合。

## 2. 分阶段采集矩阵

先执行单变量小矩阵，定位转折点后加密，并将未测组合留在补测清单中。以下 payload 和 rank 是候选扫描点，执行前按实际合法拓扑裁剪，不把不存在的配置记成通过。

| 维度 | 候选采集点 | 要分离的影响 |
| --- | --- | --- |
| 操作 | all-reduce、all-gather、reduce-scatter、all-to-all、P2P/KV transfer | 归约、交换、搬运和完成语义 |
| 展开方式 | 每种已确认合法的 AICPU、AIV、Host 或混合路径 | 控制、下发、设备执行与完成通知 |
| payload | 1/4/16/64 KiB，256 KiB，1/4/16/64/128 MiB，观测转折点前后 | 启动开销、算法切换、流水和带宽区间 |
| rank 与放置 | 2/4/8 rank；同封装、跨封装、跨节点的实际可用组 | 参与组、物理链路和拥塞域 |
| 数值与布局 | BF16/FP16/FP32；目标模型实际使用的其他合法 dtype/layout | 归约吞吐、转换与额外搬运 |
| 执行条件 | eager、支持的图模式；首次与预热后分开 | 建连、展开、图 replay、稳定重复执行 |
| 算法 | 默认选择及明确可指定的合法算法 | 同后端不同展开算法的成本差异 |

并发矩阵：

- [ ] 通信 + Cube 主导 GEMM，通信 + Vector 算子，通信 + HBM/MTE 主导搬运，保留各任务独占基线。
- [ ] collective + KV/P2P，在实际共享链路与不共享链路各测一组。
- [ ] 同时启动及错峰启动；记录请求 release、实际开始、完成、各 lane duration 和总 span。
- [ ] 分块数量与 chunk 大小扫描，覆盖启动、稳态、排空及尾块；不能只记录稳态带宽。
- [ ] 代表模型的真实通信 shape 与特性组合，检查采样结论能否影响端到端预测和配置排序。

## 3. 每条样本的必要记录

保存 run/case/rank/trial 身份、请求策略和观测策略及其证据、collective/algorithm、参与组和实际放置、逻辑 payload 与已知 wire work、dtype/layout、stream 和图模式、缓存及缓冲预分配、warmup/iterations、请求错峰与观测错峰、原始逐次耗时、失败及未确认结果。

同一 trial 的多个 rank 记录是相关样本。保留 outlier 和失败记录，不用静默裁剪制造稳定曲线。首次执行、不同计时范围、缓存协议或展开方式不混成同一条件。

## 4. 回填和验收

- [x] 将实际执行的矩阵导入统一样本结构并完成 observation-identity 去重：`ingest_a5_campaign_data` 分离 `single=True` 启动锚点与稳态条件，按 `rack06` vs `rack08` 软件栈分区；`build_a5_followup_manifest` 确定性导出 verified/pending cell。
- [x] 按实际展开路径、拓扑、算法和协议拟合：`fit_a5_service_curves` 使用 `piecewise_linear` + 非负仿射（`nonnegative_affine`）`ServiceCurve`，覆盖 `W2`、`W4`、`W8`、`W16`、`W32` 的 `all_reduce`、`reduce_scatter`、`all_gather`、`all_to_all`、`all_to_allv`（其中 `W2/W4/W8` 的 `int8`/`fp8-e4m3` `all_to_allv` 由 `mc2-quant` 直接实测，`W2–W32` 的 `bf16` `all_to_allv` 由对应 `all_to_all` 曲线等价派生并标注 `provenance.derived_from = "all_to_all"`）及 `p2p_send_recv`；`intra_node_ub` `0->1` 约 `50.8 GB/s`，`cross_node_urma` `0->8` / `0->24` 约 `214–246 GB/s`；`64 KiB` 与 `16 MiB` 作 heldout 验证，不进入 knots。
- [x] 正例：校准后的 A5 曲线可绑定 `ResourceService`、`service_regimes` 和 `PlannedRecipe`，并改变算子级与端到端模型预测。负例：`AICPU != AIV`（永不互为别名）；`A3 != A5`（`Ascend910_93`/`Ascend910B`/`A3` 在 ingest、fit、lookup 均以 `ModelingError` 拒绝）；未确认请求永不进入已确认 `aicpu`/`aiv` 曲线；以上均由 `tests/test_a5_comm_calibration.py` 覆盖。
- [x] 资源竞争语义：`compute_a5_contention_slowdown` 让 `AIV` 与 Vector 计算共享所声明的 Vector 管线资源，`AICPU` 则保留非 Vector 的 transfer/sync 与 MTE/HBM 竞争，不当作免费异步；`build_a5_comm_recipe` 通过 `graph_costs` 并发调度测试验证 AIV Vector 管线共享与 AICPU transfer/sync + HBM 阶段，而 `evaluate_a5_mc2_chains` 汇总 16 条 `bf16`、24 条 `int8`、24 条 `fp8-e4m3` 实测 MC2 链的阶段分解与解析竞争倍率（量化链 `overlap_ratio` 为 `0.6345..0.9571`，中位数 `0.7809`）。
- [ ] 应达候选使用合法展开及资源约束生成时间线，独立于预测残差；报告完整模型可行目标与最优性搜索范围。

## 5. 已集成校准结果与待补测清单（2026-10-21 / 2026-10-22）

`/Volumes/data/mindie-sim-data/a5/` 下 7 个 campaign 的实测摘要已内嵌到 `a5_comm_golden.py`，并由 `ingest_a5_campaign_data` 归一化接入 `mindie-sim`：356 条稳态 condition、68 条 `single=True` 启动锚点、64 条 MC2 chain；拟合得到 38 个默认 cell 和 47 条 stack-specific 曲线（`unfitted` 为空），`64 KiB` / `16 MiB` 共 82 条 heldout 不进入 knot。所有 condition 的 `observed_expansion_mode` 均为 `"not_observed"`，未把 AICPU/AIV 请求提升为 observed。

### 5.1 已导入 campaign 与实测结论

| campaign | 日期 | 栈 / CANN | 覆盖 | 关键结果 |
| --- | --- | --- | --- | --- |
| `comm-rack06` | 2026-10-21 | `rack06` / `9.1.0` | `W2/W4/W8` 单机 UB | `all_reduce`、`all_gather`、`reduce_scatter`、`all_to_all`、`p2p_send_recv`（`0->1`） |
| `comm-rack08` | 2026-10-21 | `rack08` / `9.0.0` | `W2/W8` 单机 UB | 独立软件栈；`all_gather` 128 MiB 为 1.93 ms，`rack06` 为 3.06 ms，保留为独立 stack 曲线 |
| `comm-w16` | 2026-10-22 | `rack06` / `9.1.0` | `W16` 2 节点 `rack06os5`–`rack06os6`，URMA | 4 collectives + `p2p_send_recv` `0->1` / `0->8` |
| `comm-w32` | 2026-10-22 | `rack06` / `9.1.0` | `W32` 4 节点 `rack06os4`–`rack06os7`，URMA | 4 collectives + `p2p_send_recv` `0->8` / `0->24` |
| `mc2-rack06-r1` | 2026-10-21 | `rack06` | EP2/EP4，`bf16` | 8 条 MC2 链，64/128 experts，512–2048 tokens |
| `mc2-rack08-r1` | 2026-10-21 | `rack08` | EP2/EP4，`bf16` | 8 条 MC2 链，与 `rack06` 分栈 |
| `mc2-quant` | 2026-10-22 | `rack06` | `int8` / `fp8-e4m3`，`all_to_allv` | 24 + 24 条 MC2 链；量化链 overlap ratio `0.6345..0.9571`，中位数 `0.7809` |

关键实测结论：

- **Collective/P2P**：`W2` 到 `W32` 的 5 类 collective 均有 strict-key 曲线（其中 `all_to_allv` 在 `W2/W4/W8` 的 `int8`/`fp8-e4m3` 为直接实测，在 `W2–W32` 的 `bf16` 由对应 `all_to_all` 曲线等价派生并标注 `derived_from = "all_to_all"`）；`p2p_send_recv` 的 `intra_node_ub` `0->1` 约 `50.8 GB/s`，`cross_node_urma` `0->8` / `0->24` 约 `214–246 GB/s`，跨节点单对 P2P 达到单机 UB 的约 4.2–4.8 倍。
- **软件栈隔离**：`rack06`（CANN `9.1.0`）与 `rack08`（CANN `9.0.0`）不共享曲线池；同一 cell 存在多个栈时默认优先 `9.1.0` `rack06`，存在多个自定义栈时以 `a5_incompatible_software_stacks_require_selector` 拒绝隐式合并。
- **MC2 重叠**：`overlap_ratio = chain_p50_ms / sum_leg_p50_ms`，小于 1 表示链耗时低于各 leg 简单求和。`bf16` 16 条链为 `0.9425..1.1272`（中位数 `1.0331`），`int8` 24 条为 `0.6345..0.9488`（中位数 `0.7558`），`fp8-e4m3` 24 条为 `0.6379..0.9571`（中位数 `0.7859`）；48 条量化链合并为 `0.6345..0.9571`，中位数 `0.7809`。量化链 `contention_degradation_multiplier > 1`，expansion regime 保持 `unspecified`。

### 5.2 代码入口与测试

`mindie_sim/observations/a5_comm_calibration.py` 的公开入口：

- `resolve_expansion_regime(...)`：解析 requested/observed/profiler evidence，只有 observed 或单一 profiler evidence 才能确认 AICPU/AIV，冲突或无证据时保持 `unspecified`。
- `ingest_a5_campaign_data(source=None)`：归一化 7 个 campaign，完成 observation-identity 去重、`single=True` 启动锚点分离、软件栈和 MC2 chain 保留。
- `fit_a5_service_curves(ingested=None, *, holdout_payloads=(65536, 16777216))`：按 strict key 拟合 piecewise-linear + 非负仿射 `ServiceCurve`，训练/heldout 分离。
- `compute_a5_contention_slowdown(...)`：计算 AIV 共享 Vector 或 AICPU 非 Vector 的 transfer/sync/MTE/HBM 竞争 slowdown。
- `evaluate_a5_mc2_chains(ingested=None)`：汇总 16 条 `bf16`、24 条 `int8`、24 条 `fp8-e4m3` MC2 链的重叠率、stage 分解与竞争倍率。
- `build_a5_followup_manifest(ingested=None)`：确定性导出 verified cell 与 5 个 pending cell。
- `A5CommCalibrationBundle`：保存 strict-key `curves` / `stack_curves` / `fits` / `holdout` / `single_op_anchors`，并提供 `lookup_curve`、`bind_service_curve`、`to_service_regime`、`build_a5_comm_recipe`。

实现拆分在 `a5_comm_ingest.py`（解析、流式读取、去重、展开解析）、`a5_comm_binding.py`（`ResourceService` / `service_regimes` / `PlannedRecipe` 绑定与 wire/payload 换算）、`a5_comm_golden.py`（内嵌 2026-10-21/22 实测表）和 `calibration.py`（显式 re-export）；`tests/test_a5_comm_calibration.py` 覆盖上述正负控制、stack 隔离、heldout 不变性、manifest 确定性、live mount 与 golden 一致性，以及绑定后端到端预测变化。

### 5.3 待补测清单

`build_a5_followup_manifest()` 当前确定性导出 5 个 pending cell：

| cell | 要求 | 保留原因 |
| --- | --- | --- |
| `expansion_regime:aicpu/aiv` | `msprof` task-trace confirmation | 没有实测行观察到 AICPU/AIV 展开引擎 |
| `collective:W64-8node` | W64 8-node expansion | W32 是当前最宽实测 mesh，W64 外推未验证 |
| `p2p_send_recv:0->4:intra_node_ub` | 0->4 intra-node P2P pair | 仅测了 0->1 单机 pair |
| `contention:live_sweeps` | live concurrent contention sweeps | 竞争倍率是解析模型，不是实测 sweep |
| `all_to_allv:W16-W32` | measured all_to_allv lane | W16/W32 无直接实测 `all_to_allv` condition（当前 `bf16` `W2–W32` 的 `all_to_allv` 曲线由 `all_to_all` 派生） |

上述缺口不影响已导入曲线的 strict-key 查询和绑定；其中 4 个 condition 驱动项（`expansion_regime:aicpu/aiv`、`collective:W64-8node`、`p2p_send_recv:0->4:intra_node_ub`、`all_to_allv:W16-W32`）在导入实测 condition 后重跑 `fit_a5_service_curves` 与 `build_a5_followup_manifest` 即可移入 `verified`，而 `contention:live_sweeps` 还需在导入实测并发 sweep 后同步更新 `build_a5_followup_manifest` 的判定逻辑。

交付原始数据、环境与协议、实际展开证据、导入后的覆盖清单、留出误差和代表模型案例；缺少样本不阻断通用解析模型。

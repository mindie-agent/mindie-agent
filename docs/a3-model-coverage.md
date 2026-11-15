# A3 建模最低模型覆盖集

[双模型设计](a3-performance-modeling-plan.md) · [实现与验收](a3-performance-modeling-acceptance.md)

根据 2026-10-21 的明确需求，`maoxx241/se-tools` 的所有模型配置构成本轮最低覆盖集。已核对 `main` 的 `models/*/config.json` 共九项；其中 `deepseek-v4-10t` 与 `qwen3.8-27b` 没有出现在七项的 workbook catalog 中，仍必须纳入。来源修订 `ae8779fdd5a602bd3a4358bca93b2161d134a47b` 只记录本次核验来源，不作为模型准入或版本兼容门槛。

“覆盖”要求从原配置构建实际层结构、算子 shape、权重与状态、通信和依赖，并贯通 `predict`、`should`、`search`。不能只增加模型名称，也不能把混合结构统一改写成普通 MLA/MoE。下面记录源配置事实与验收要求；本轮已完成的结构与参考产物验收见第 4 节，性能精度单独判断。

## 1. 必须覆盖的九个配置

| 配置 | 主体规模 | 必须保留的结构 |
| --- | --- | --- |
| `deepseek-v4-flash-0731` | H4096，43 层，256 routed experts/top6，1 shared expert | 2 层 SWA-only、21 层 C4、20 层 C128；滑窗、压缩/索引、分组输出投影、mHC、FP4 expert 路径及可选 DSpark/MTP |
| `deepseek-v4-pro-0813` | H7168，61 层，384/top6，1 shared expert | 30 层 C4、31 层 C128；压缩比例的逐层调度、索引 top-k、mHC 和低秩/分组投影 |
| `deepseek-v4-10t` | 归档配置与 Pro 的 JSON 语义相同 | 独立模型标识和来源；不能据名称猜测参数量，也不能把相同配置视为相同 checkpoint |
| `deepseek-v4.1-flash` | H5120，40 层，384/top6，1 shared expert | 40 个消费者、4 个 KV owners、8 个 TopK owners；跨层共享、候选块选择、Engram、mHC、DSpark/MTP；配置包含 vision |
| `glm-5.3` | H6144，78 主体层，256/top8，1 shared expert | 首 3 dense、后 75 MoE；DSA/MLA、21 个 index 生成源与共享索引、独立 QK/V 维度、可选 1 层 MTP |
| `kimi-k3` | H7168，93 层，896/top16，2 shared experts | 69 KDA + 24 MLA，首 1 dense；latent MoE routed 宽度 3584，不能当成 7168；门控、状态、AttnRes；配置包含 vision |
| `kimi-k3-dspark` | H7168，5 层，64 Q heads/16 KV heads，head_dim64，I14336 | 独立 draft 图、target 93 层关联、block7、confidence/Markov 头、接受/拒绝反馈和目标验证成本 |
| `qwen3.8-2.4t-a95b` | H8192，92 层，512/top10，shared I2048 | 69 GDN + 23 gated GQA；线性状态/卷积、门控、MoE、可选 MTP |
| `qwen3.8-27b` | H5120，64 层，dense I17408 | 48 GDN + 16 gated GQA；Q24/KV4/head_dim256 的投影维度；配置包含 27 层 vision encoder |

`num_nextn_predict_layers` 等扩展配置中的额外条目不自动算作主体层。主体层数、可选 draft/MTP 层和接受率模型应分别表达。文本请求不执行未使用的视觉路径；提供图像/视频输入时，patch、视觉编码器、merge/projector 与新增文本 token 必须实际展开。

## 2. 跨模型的统一验收要求

1. **输入与结构**：读取原配置，保留逐层类型、有效主体层数、dtype/量化分组、独立投影维度和来源。允许修改合法 shape、batch、并行度及版本元数据后重新估计。
2. **状态与内存**：分别核算驻留权重、活动专家读取、普通/压缩 KV、KDA/GDN recurrent 状态、卷积状态、共享 KV/index、Engram 与 workspace。按 owner 和实际 rank 计算，不能按消费者层数重复存储共享数据。
3. **计算与依赖**：各分支的生产者先完成再消费；跨层共享索引、Q/KV 双分支、draft→target verify、图像→文本进入同一执行计划。计算量与物理 padding 分开记录。
4. **特性与通信**：TP/EP/PP/DCP、稀疏选择、压缩、quant/cast、graph、prefix、KV transfer 与 Engram 搬运改变算子 shape、字节与依赖；重新生成整个受影响计划。
5. **双模型**：预测复现指定策略，应达独立生成合法候选与时间线。两条路径使用同一模型数学语义，不能一条漏算某种层或状态。
6. **泛化与实测**：未实测的合法 shape 仍有解析预测；按照实际展开出的算子/特性/竞争条件生成可执行补测请求。分开报告结构验证、数值预测误差和实机业务指标。

## 3. 最小判别矩阵

- 对九个完整配置分别运行短 prefill、decode 和混合 case；选择容量足够的明确 A3 拓扑。机器不足时应返回真实容量原因，不能缩小模型结构后标为同一模型通过。
- 检查 `B-1/B/B+1` 的请求调度，以及压缩 ratio、窗口、top-k、candidate block、graph bucket 和 expert capacity 边界。
- 检查 V4.1 的 shared KV/index 只在 owner 生产、消费者保留依赖；改变 owner 映射后容量和生产次数相应变化。
- 检查 Kimi latent MoE 的 3584 宽度与外部 7168 宽度之间实际投影和通信；KDA/GDN decode 不错误增加随 context 线性增长的普通 KV。
- 检查 Qwen 的 gated GQA、GLM 的 dense/MoE 混合，以及独立 Q/K/V 维度；不能只以模型总参数量推算耗时。
- 检查 DSpark/MTP 关闭、启用且全拒绝、部分接受、全接受的计算/采样/KV 变化；接受率为输入或校准分布，不伪造推理正确率。
- 对带 vision 配置的模型分别检查纯文本与有媒体输入，确认新增视觉图、merge 后 token 和时序依赖。

来源为 [se-tools 模型目录](https://github.com/maoxx241/se-tools/tree/ae8779fdd5a602bd3a4358bca93b2161d134a47b/models)、对应 `config.json`、`lib/` 中的语义公式、`scripts/model-analysis-specs.mjs` 及模型自己的来源记录。公式与归档说明用于交叉核对；时间精度必须由本轮真实测量和留出数据另行验证。

## 4. 本轮覆盖结果

九个完整模型均已接入公开 `predict`、`should`、`search`。
参考产物位于运行时工作树
`/Volumes/data/code/mindie-sim-a3-modeling/examples/model-reference/`，
包含各模型结构、case、约束、搜索域、当前结果及可执行补测清单。
54 项公开行为场景和两个跨 case 控制通过；最终参考产物的
128 项独立一致性检查通过，未缩减主体层数或隐藏容量不足。

每模型参考实际评估三个应达计划和两个搜索候选，记录理论下界 L、
已评估可行目标 U、准备任务与完成时间。当前参考为
prompt8/output1 的解析结果；多于八个 die 的 fabric 是显式合成
拓扑，不能作为真实多机端到端性能或部署可行性证据。

当前算子清单派生 11,386 个条件，选取 318 个采集请求，保留
4,902 个 pending 条件和 82 个 family/recipe 分组；具体形状与
协议可经 campaign materialize 导出。这些派生数量不代表实测覆盖。
独立留出评分中，75 个 GEMM 条件的公开成本 WAPE 从解析基线
22.51% 降至校准后的 14.53%；直接曲线仅支持 69/159 个条件。
**整体性能精度未通过，九模型整体验收尚未收敛。**
完整证据、误差与范围见 [验收记录](a3-performance-modeling-acceptance.md)。

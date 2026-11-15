# L1–L4 架构闭环与知识飞轮分级测试方案

[返回文档中心](README.md) · [分级测试规范](testing-architecture.md) · [上下文与经验演化设计](knowledge-context-and-exploration.md)

本方案覆盖 `vllm-ascend`、`operators` 两个领域，面向模型与算子适配、问题诊断、性能优化三类任务。验收分别回答四个问题：知识是否正确且适用、Agent 在 `L1–L4` 四层认知与执行架构中是否正确使用、使用后任务是否改善、经验能否迁移并随新证据修订。四类结果分别报告，不合成一个“知识系统总分”。

实施重点是复用已有知识契约、任务运行器、独立判分器和结果账本，补齐真实检索对照、未见任务、跨会话学习以及代码变换泛化。开源项目提供评测协议参考；其公开成绩不作为 MindIE 的能力或收益证据。

## 1. 范围与分级口径（消除 `L1–L4` 架构分级与知识库类别混用）

| 维度 | 含义 | 使用方式 |
| --- | --- | --- |
| **系统认知与执行架构 `L1–L4`** | `L1` 硬件约束与语法基座；`L2` 性能剖析与仿真定界；`L3` Hermes 经验收敛模式；`L4` RSI 去偏置发散探索模式 | 定义 Agent 解决昇腾复杂工程问题的四层认知与执行闭环（详见[系统架构 §4](architecture.md#4-l1l4-四层认知与执行架构及知识飞轮)） |
| **知识飞轮内容类别 `category`** | `axiom / measurement`（约束与测量基线，服务 `L1/L2`）；`sop`（操作规程，服务 `L2/L3`）；`workflow`（决策经验，服务 `L3`）；`mutator`（受控代码变换，服务 `L3/L4`） | 标注 `knowledge` 飞轮中的结构化知识类型（现有 Schema 遗留的 `tier: L1..L4` 字段及下文 `L1-01..L4-05` 用例编号均表示“服务于对应 `L1–L4` 架构层级的知识与闭环能力”，不代表把 `knowledge` 定义为“L1–L4 分级知识库”） |
| **工程验证范围 `Tier 0–3`** | 纯内存、本地组件、真实 NPU 集成、真实宿主短 Canary | 决定验证环境、频率和预算 |
| **NPU 物理拓扑规模 `S0–S3`** | `S0` 单 Die 算子微基准、`S1` 2–4 Dies 子集群、`S2` 8–16 Dies 整机/同机 PD 分离、`S3` 双机 RoCE 跨节点 | 决定真实多卡/分布式评测的硬件拓扑层级 |
| **任务族 `B1–B4`** | 物理诊断、SOP 与过期经验处理、多步骤收敛、长周期探索 | 保留既有任务族分层；一个任务可同时涉及多个知识类别与架构层级 |
| **bench `environment.l1/l2/l3`** | 现有 `TaskSpec` 的执行环境档位 | 历史字段名，不新增 `environment.l4` |
| **产品组 `P0–P3`** | `P0` 原生宿主、`P1` 工具基线、`P2` 完整产品（含知识库）、`P3` 带跨任务经验谱系的产品 | 沿用 `mindie-value-suite/2`；不把历史 G0–G3 结果改名为 P 系列 |
| **宿主执行控制** | DSH 固定标准模式（`preset=standard` / `tools.mode="native"`）与默认思考强度 `reasoningEffort="max"` | 所有对照分组保持同一宿主模式与思考强度；bench 的 `build_dsh_profile` 显式声明 `reasoningEfforts` 与 `tools.mode="native"` |
| **机制消融** | 角色、账本、检索、并行探索的单因素比较 | 固定其余输入与总预算；本方案的加载、检索和更新条件是独立子实验 |

经验提炼（`knowledge_distill`）是从已验证里程碑中学习并修订知识的过程，可更新任意 `category` 的知识单元。常规 `L3` 任务可以直接复用已知 `mutator` 变换；`L4` 开放探索也可能产出一项新的 `sop` 诊断规程或 `measurement` 边界。以上定义与[系统架构](architecture.md)及[上下文与经验设计](knowledge-context-and-exploration.md)保持一致，产品组和执行档位分别以 [Product value suite v2][B-product-doc]、[TaskSpec][B-models] 为准。

本方案按 2026-10-20 检查到的源码制定：

| 仓库 | 检查修订 | 证据边界 |
| --- | --- | --- |
| `mindie-agent` | `a1648d58877a1db5ca9a4ca29eba21579f7d46a9` | 架构与测试要求 |
| `knowledge` | `b900f11ef6be1edfe54e3d739b10588bc0cb0fce` | 实现及测试源码（含 PR #84/#85 合入的全响应预算、父生命周期闭包、默认同主题对照与多目标三轴评估） |
| `mindie-bench` | `4a8b9a9e7b81d424062bc2079423ec1d2c9aff19` | 实现、任务定义及测试源码（含 PR #13 合入的生产 `RoutingIndex` 委托与默认保留有效小收益） |
| `knowledge-operators` | `755167140d2c4390aa042eb137ed89f3e2218376` | 算子领域分级知识单元与路由清单 |
| `knowledge-vllm-ascend` | `5a6a3844ef08c888128859889bf527d77d3058aa` | vLLM-Ascend 领域分级知识单元与路由清单 |

下文“已有覆盖”表示已找到对应实现和测试，不能自动解释为当前修订已实测通过。“历史实测”绑定原报告的代码、语料、宿主与条件。

机制吸收补充检查使用 `knowledge@02ccb63`、`mindie-bench@c606777`，见第 4.6 节。该 bench 修订已提供 `evaluation/knowledge_tiered.py` 的真实知识接口回放、`bridge_run_receipt_to_feedback` 和 `run_sequential_learning_episodes`；后者仍消费提供的提案，属于组件链路覆盖，真实 organizer 学习与新宿主任务的结论仍待验收。下文旧快照中的“待补”不能覆盖这项增量，也不能据此升格为真实迁移通过。

## 2. 开源协议如何采用

| 项目与来源 | 采用的设计 | 对应范围与调整 |
| --- | --- | --- |
| [LongMemEval-V2][O-longmem] | 分别测事实、状态、工作流、环境陷阱、前提识别；同时报告质量与检索延迟 | 用于 L1/L2 的适用性题集；问答成绩之后仍需真实执行验证 |
| [SkillsBench][O-skillsbench]、[Skill-Usage][O-skillusage] | 无知识、精选知识、自主加载、含干扰项检索分别比较；执行产物由 verifier 判定 | 区分知识内容、检索选择、采用行为和任务收益；保留自然触发协议 |
| [SkillLearnBench][O-skilllearn] | 知识产物、执行轨迹、任务成功分别评分 | 用于蒸馏质量诊断；有效替代路径不因偏离参考步骤而扣分 |
| [STATE-Bench Learning Track][O-state] | 从训练轨迹提炼经验，在独立测试任务上评价下游收益 | 用于冻结语料后的迁移实验；计入其默认公开指标未必覆盖的离线提炼和索引成本 |
| [PAST-Bench][O-past] | 有顺序的任务族、新会话、经验保留对照、更新与遗忘检查 | 用于连续学习；另设工具相同、初始知识相同、只阻断跨任务更新的对照 |
| [AgentKernelArena][O-arena] | 原始实现与候选实现使用同一批隐藏输入，区分正确性回退与收益保留 | 复用现有私有 shape 和性能证据机制；增加候选冻结后的泛化复验与分类汇总 |
| [RSI-Inference Bench][O-rsi] | 固定推理引擎，真实执行模型支持、优化和回归修复任务，独立验证产物 | 已有 native inference 管线承接；继续使用 MindIE runner，不引入 Pier/Harbor 运行依赖 |
| [OO-Harness][O-ooharness] | 按执行需求形成专用策略，分别学习执行方法与选择条件，固定后用独立任务评测 | 用第 4.7 节分离题面选择、证据选择与默认路径；完整计入前缀、选择和后续执行成本，结果不外推为昇腾收益 |
| [HarnessPro][O-harnesspro] | 带初始通过率下界的帕累托非支配筛选、`lite`/`medium`/`heavy` 归一化加权平方距离选择、Cost-of-Pass ($\text{CoP}$) 与无泄漏生成式测试门禁 | 用于多档位策略/候选对比与评测门禁（`select_pareto_candidates`）；剔除前置串行分类器开销，交互式会话不硬锁工具调用，且 `infra_error` 严格独立于 `passed=false` |

协议移植需保留以下具体边界：

- SkillLearnBench 让方法使用 `instance-1` 生成知识，而其[默认评测入口][O-skilllearn-runner]会枚举全部实例。MindIE 必须显式划出未参与学习的实例和任务族，分别报告同族泛化与跨族迁移。
- PAST-Bench 的[无持久化实现][O-past-runner]还会关闭相关记忆、技能与会话检索工具。该对照可以衡量整套持久化能力，不能单独归因于知识修订。
- AgentKernelArena 的隐藏输入复验需要单独调用；普通任务完成不代表泛化复验完成。换名称或复用可见输入也不产生新的隐藏样本。
- Apple 的[局部性能奖励][O-rsi-scoring]使用 `max(0, speedup - 1)`。MindIE 已把连续实测值和验收结果分开，应继续保留低于 1 的比值、失败、预算超限与缺失观测，详见 [native inference 协议][B-inference-doc]。
- HarnessPro 的测试集成本只统计冻结后候选在测试集上的单任务平均 Token 账单，不含多轮进化期间的 Rollout、Planner、Editor 与测试合成开销；且当无标注任务需要合成验证脚本时，只允许从公开任务契约与独立参考构造断言，严禁从待测候选产物中倒推期望常量或 Hash。

## 3. 现有覆盖与缺口

### 3.1 实现与测试覆盖

| 能力 | 已有实现与用例 | 仍需补齐的证据 |
| --- | --- | --- |
| L1 条件与依赖 | [graded units][K-units] 覆盖硬件/版本条件、未知条件、跨层依赖、父修订、基础规则；[渐进加载][K-context]覆盖缺失前提和不适用状态 | 真实领域问题的适用性标注；Agent 是否补查条件、是否错误采用 |
| L2 完整流程加载 | [渐进加载][K-context]覆盖完整闭包、共享父正文去重、窄预算整单元排除、导航无正文 | 在 NPU 上执行 SOP 后的结果、关键依赖顺序、异常分支与停止行为 |
| L3 决策与探索 | knowledge 的[经验与探索用例][K-experience]覆盖停滞、负例条件、有效性/目标达成/可复用性三轴；bench 的 [RSI helpers][B-rsi]及[测试][B-rsi-tests]覆盖上下文、编译/计时计划和账本 | 当前 helpers 的调用主要见测试；需真实宿主触发、原生子上下文隔离、实际实验调度和决策轨迹 |
| L4 变换与测量 | [性能门禁][B-performance]及[测试][B-performance-tests]覆盖私有 shape、buffer 轮转、同步计时、ACLGraph、workspace、warm server；[L4 准入][K-ablation]及[跨仓契约测试][B-graded-ablation]绑定消融和最终组合 | 扩展真实变换族；补候选冻结后的新输入、条件边界和端到端收益保持 |
| 上下文压缩与重读 | [knowledge 用例][K-context]按精确版本和 `known_refs` 检查重读；[bench 回放][B-replay]有压缩后的加载成本 | 真实宿主压缩后正文是否仍可见；仅保留 ref 时是否重读 |
| 使用与修订 | [经验回放][K-experience]已有 discovered/loaded/applied/evaluated、重复事件去重、未确认结果、`U@1 → U@2` | 测试中的事件和提案由用例提供；需将真实采用行为、运行结果和修订串起来 |
| 检索对照与观测 | [知识条件配置][B-models]已有 advisory/explicit/oracle；[相关用例][B-conditions]检查显式检索和允许语料供给；[broker][B-broker]和[计量测试][B-broker-tests]记录真实 query/explain 调用 | broker 仅允许读取工具；调用次数不代表采用、正确使用或学习完成。干扰语料与适用性题集需补 |
| 冻结经验与谱系 | [P3 admission][B-p3]和[测试][B-p3-tests]已有 Seed、capture、C6、consumer、冻结、独立审阅、下游绑定及成本检查 | 有效谱系实例和不同任务族的真实收益；结构合法不能替代语义独立性审阅 |
| 评测完整性 | [coverage][B-coverage]区分缺失、样本不足与就绪；产品比较绑定条件与预算，保留四态结果 | 为本方案新增指标提供实际观测；按任务族处理相关性，避免用重复运行增加独立样本量 |
| NPU 知识链路 | [live NPU 用例][K-live]读取 A2/A3 拓扑，再验证脱敏、存储和检索 | 其中故障与修复叙述是用例构造的；该测试不证明发生过真实算子故障或完成过修复 |

三处实现边界应优先闭合：

1. **离线回放不等于 Agent 行为（需补非模拟适用性与干扰项评测器）。** [knowledge_replay.py][B-replay]已委托生产 `mindie_knowledge.graded.index.RoutingIndex` 并显式标记 `simulation_only=True`，但其 `steps/attempts` 由基线值和未就绪次数推算，增长回放的稀有条件保留来自输入事件。后续必须在 `mindie-bench` 提供直接针对真实 `GradedRepository.query/explain` 的适用性题集与干扰项评测器（区分 `matched`、`mismatch`、`condition_unknown` 与近似干扰项错误采用），并将回放指标与真实轨迹指标严格分栏。
2. **三轴结果、隐藏输入泛化与回执-反馈桥接需接入执行闭环。** `knowledge` 与 `mindie-bench` 的 `evaluate_rsi_candidate_gates()` / `evaluate_exploration_axes()` 已默认开启 `preserve_subtarget_evidence=True`（`1 < speedup < 目标` 且高于噪声时返回 `verdict="subtarget_valid"`、`distill_ready=True`，不生成 `conditional_avoid` 通用反证）。下一步需在 `mindie-bench` 补齐：（a）候选冻结后的隐藏输入五分类泛化评估（`L4-02`）；（b）从运行回执到 `knowledge_feedback`（`applied` / `evaluated`）及跨会话 `distill`（`U@1 → U@2`）的确定性桥接，且严格遵守[设计原则 14](design-principles.md#14-故障边界禁止静默回退与-unknown-外部状态保护)：**次要回执/反馈/提炼记账失败绝不覆写已成功的主任务验证结果**，设备/环境故障统一标为 `inconclusive`。
3. **DSH 宿主标准模式与 `max` 思考强度契约固化。** `mindie-bench` 的 `build_dsh_profile` 在生成隔离 DSH profile 时，必须显式固定 `tools.mode="native"`（标准模式，防止环境变量 `DSH_TOOLS_MODE=ptc` 漂移），并在 `providers.bench.models` 声明 `reasoningEfforts` 映射、在 `agent-default-model` 设置默认 `reasoningEffort="max"`，避免 `dsh-llm-pi-ai` 将自定义路由模型判定为不支持推理而拒绝 `max`。

### 3.2 当前语料视图与业务题

两个领域的 `main` 分支（`knowledge-operators@7551671`、`knowledge-vllm-ascend@5a6a384`）及 [bench 语料回放测试][B-replay-tests]在本次检查时如下：

| 语料视图 | L1 / L2 / L3 / L4 | 已有主题 | 选题缺口 |
| --- | --- | --- | --- |
| `operators`，共 11 条 | 3 / 3 / 3 / 2 | 内存与 tiling 约束、测量方法、RMSNorm、FP32 Reduction 与 UB 对齐、向量化 BF16→FP32 累加与写回融合 L4 mutator、瓶颈收敛、Triton 特化与重编译 | 已具备两类 L4 代码变换族与条件回退边界（`L4-01` / `L4-04`）；后续需在独立保留 shape 与新算子族上继续扩充端到端实测 |
| `vllm-ascend` transcript content，共 11 条 | 3 / 4 / 3 / 1 | hybrid model bringup、GDN/idle DP（含空批 zero-pad workspace 与 HCCL 保活 L4 mutator）、ACLGraph capture 失效排查、prefill/decode 瓶颈收敛、通信与状态约束 | 已补齐带适用条件与回退契约的首个 L4 变换单元；后续需继续补充第二类推理图变换族与跨模型/版本保留诊断题 |

可优先复用的已提交任务定义有 [fused RMSNorm 性能][T-rmsnorm]、[K3 GDN idle-DP 状态][T-idle]、[KDA 变长 workspace 正确性][T-kda]、[过期 fused-MC2 配置迁移][T-stale]。其 `evidence="verified"` 是任务元数据，不构成本次重新验证；这些题可作为开发与协议调试材料，保留集资格需按题源暴露记录另行审阅。

### 3.3 已有实测的适用范围

本地执行证据根记为 `EXECUTION_ROOT`。两个已读取的记录可用来界定现状，不能迁移为当前源码成绩：

| 记录 | 可支持的事实 | 限制 |
| --- | --- | --- |
| `wave4/knowledge/dsh-final-core-5f0097b-v1/final-report.json`，生成于 2026-10-20 02:11 UTC | 原修订 `5f0097b`、67 条 canonical 单元及 2 条继承控制单元；40 问含 3 道控制题，共 240 次调用；报告 cold p95 12.428 ms、hot p95 0.843 ms | 原报告 `native_harness_e2e=pending_not_run`、`acceptance_claim=false`；不是当前 `7bf9036` 的全面性能或任务收益结果 |
| `execution-status.json` 中 `active_wave.benchmark_denominators`，条目检查于 2026-10-19 21:29 UTC | 当时已验收题均标为 `exposed_dev`，`ready_heldout_items=0`；B1–B4 目标共 60 个 evaluation items | 不是 60 个独立任务族，也不是实时全量库存认证；新实验前必须重审题源与可用状态 |

语料与报告身份见第 9 节。发布能力结论时应绑定新的实际 consumer 语料与运行修订，不能沿用本节数字。

## 4. 具体用例与判据

以下用例是实施清单。状态中的“部分已有”只覆盖第 3 节所列机制；业务、宿主和硬件证据仍按各行要求补齐。确定性规则由代码判定，语义适用性与决策质量用独立审阅的标注；LLM judge 只能辅助诊断，不替代正确性 oracle 或硬件测量。

每项落地时，在既有 TaskSpec、实验计划和回执中记录：题源与 task family/split、知识版本及适用条件、可见输入与私有 oracle、实验分组与预算、实际运行和指标来源。用例编号用于关联测试与业务任务，不建立第二套任务状态文件。

### 4.1 L1 约束与事实

| 用例 | 输入与触发 | 独立判据 | 现状与执行层 |
| --- | --- | --- | --- |
| L1-01 硬件条件边界 | 同一条 tiling/对齐知识分别配匹配 SoC、另一 SoC、缺失 SoC 的问题；数值取自真实规格或采集 | 匹配时可用；不匹配不采用；缺事实先获取事实。条件未知时允许发现导航，但不标为可执行 | 条件契约部分已有；Tier 0，真实条件获取用 Tier 2 |
| L1-02 软件版本与过期事实 | 同一问题提供旧配置结论、新版软件契约和已知冲突观察 | 选择当前版本路径；保留旧版本适用范围；不能把版本变化写成所有环境都禁用 | 修订/替代机制已有；语义题与任务对照待补，Tier 0/1 加业务实验 |
| L1-03 测量结论外推 | 已验证 shape/dtype/workload 集合，另给未覆盖 shape、dtype 或组合 | 只在证据支持条件内采用；未覆盖条件标待验证；不得把单算子收益推成整模型收益 | 条件与 L4 workload 绑定已有；语义标注及 NPU 边界待补 |
| L1-04 知识缺失与近似干扰 | 无相关知识，或只有词面相近但领域/条件不同的知识 | 不编造来源或实测；能通过当前环境继续诊断。无检索调用本身不判失败 | no-hit/stale 元数据已有；干扰题集和真实行为待补 |

### 4.2 L2 操作方法

| 用例 | 输入与触发 | 独立判据 | 现状与执行层 |
| --- | --- | --- | --- |
| L2-01 数值与状态验证 SOP | 从 KDA workspace 或 GDN 状态题构造可重复失败和参考修复 | 原始缺陷失败、参考修复通过；Agent 产物通过隐藏检查；验证边界覆盖 shape、状态与必要同步 | 已有业务题，可先做 Dev；Tier 1 验证契约，真实业务实验验证 NPU |
| L2-02 Graph capture 诊断 | 提供实际采集的 capture 失败与成功对照，以及分配/stream 条件 | 完成必要探针，区分适用原因；最终 capture/replay 实际通过。只删除测试或关闭验证不算修复 | 知识和性能探针已有；任务配对待补 |
| L2-03 Triton 重编译诊断 | 固定内核，改变运行时标量和代表性输入，提供真实编译/执行计数 | 区分语义变化与不必要特化；结果正确；分别记录编译次数、冷启动、稳定执行时间 | SOP/L3 知识已有；新的可复现任务与测量待补 |
| L2-04 前提失败后停止 | SOP 中设备、依赖或基准健康检查失败；失败只发生于测试沙箱 | 透明记录失败，修复条件或停止；不执行依赖无效前提的测量，不生成知识反证 | 错误传播机制已有；完整宿主行为待补，Tier 1/2 与短 Canary |

步骤判分只约束必要前提、关键操作和验证结果，不要求复述文档或匹配唯一工具调用序列。

### 4.3 L3 决策经验

| 用例 | 输入与触发 | 独立判据 | 现状与执行层 |
| --- | --- | --- | --- |
| L3-01 相同慢现象、不同瓶颈 | 分别准备带宽、计算、host/同步开销导致的慢任务；证据来自真实采集 | 后续实验能区分原因；分别记录正确分支、无效实验和定位成本；不因“多调用工具”加分 | 有收敛知识；有根因标注的真实任务组待补 |
| L3-02 多步骤状态收敛 | idle-DP、活跃 rank、不同状态对象和调度条件；参考结果由独立 oracle 给出 | 找到首个状态分歧，修复后同时通过 idle 与 active 条件；不跳过通信/状态契约 | idle-DP 题已有；迁移任务和分支覆盖待补 |
| L3-03 停滞与有效进展 | 连续无信息实验、新定位信息、基础设施故障、噪声内结果各成一组 | 仅真实无信息停滞触发换方法；新信息重置停滞；故障先修执行条件；小收益保留为条件化观察 | 三轴和停滞 helpers 已有；实际调用链与真实行为待补 |
| L3-04 经验失效后进入探索 | 旧 L3 连续失效，保留有效 L1/L2 和可用 L4，在真实宿主新子上下文中探索 | 实际上下文不再携带旧 L3 推荐正文；负例仅在匹配条件下约束候选；最终有可验证结论或明确预算终止 | 上下文构造测试已有；原生隔离与端到端调度待补 |

### 4.4 L4 代码变换

| 用例 | 输入与触发 | 独立判据 | 现状与执行层 |
| --- | --- | --- | --- |
| L4-01 适用条件与回退 | residual-free RMSNorm 变换，另给有 residual、不同 dtype/layout、非对齐边界 | 支持条件内数值正确；条件外使用正确路径或明确不适用；不能为了快而删分支 | 一个 L4 及性能题已有；边界覆盖与新变换族待补 |
| L4-02 隐藏输入泛化 | 候选冻结后，原始实现与候选使用同一批未曝光合法输入及相同容差 | 每项分别记录 both_pass、opt_regression、both_fail、opt_improvement、evaluation_error；只有可比且正确的项进入性能比值 | 私有 shape/测量机制已有；冻结后复验流程与分类汇总待补 |
| L4-03 局部收益与系统回归 | 构造算子加速，但 workspace、graph 或 warm-server workload 退化的候选 | 保留局部收益，同时由实际失败门禁拒绝系统验收；全部 guard workload 都要测 | native performance/inference 契约与用例已有；新变换真实 NPU 实测待补 |
| L4-04 消融与最终组合 | 多因素候选，包含相互依赖的因素；逐项移除并重新验证最终保留组合 | 区分主效应与依赖；噪声内结果不强行剪枝；最终组合有独立验证，不能复用完整候选结果冒充 | C4→C6 准入与最终组合绑定已有；更多真实候选族待补 |

`OracleFreezer` 保护所封存的 oracle，`MeasurementGuard` 保护明确捕获的函数绑定；两者都不能证明 oracle 语义完备。任务准入先用参考解和已知错误解检查判分器，再进行候选实验。CPU 编译只用于支持该路径的任务；需要设备完成的阶段使用实际租约和对应预算。

### 4.5 跨层加载与长期学习

| 用例 | 输入与触发 | 独立判据 | 现状与执行层 |
| --- | --- | --- | --- |
| X-01 共享前提与预算 | 两条 L3 共享 L1/L2；逐步收紧导航和正文预算 | 父正文只计一次；未加载前提明确可见；不把截断流程标为可采用；计量覆盖完整返回响应 | knowledge 契约已有；bench 简化回放需与实际接口对齐，Tier 0/1 |
| X-02 压缩后的可见性 | 真实宿主分别保留正文、只留 ref、留下旧 revision；随后继续依赖该知识 | 只留引用或旧版本时重新读取完整正文；保留正文时避免无意义重读 | 模拟 `known_refs` 已有；每个被声明支持的宿主需实测，Tier 3 或长实验 |
| X-03 父修订与领域边界 | 更新/撤回父规则；两个领域使用相同局部单元 ID；旧客户端再次查询 | 当前闭包版本一致；失效前提阻断采用；领域不串用；旧引用按接口约定明确失效或定位，不悄悄返回新内容 | 版本、撤回和多域用例已有；真实 consumer 串联待补，Tier 1 |
| X-04 创建、复用、反证、修订 | 新会话 A 创建 U@1；B 复用；C 给有效反证；D 使用 U@2；E 回测旧适用条件 | 每步绑定实际知识版本与运行结果；新条件生效且旧条件未被误删；测试结论不泄漏到同轮冻结保留集 | 两任务组件回放已有；完整真实顺序实验待补 |
| X-05 重复事件与未确认观察 | 重复上报同一 run；设备失败；新独立 run 给有效支持/反驳 | 重复事件不增加证据数；设备失败为 inconclusive；只有独立有效验证改变支持/反驳统计 | 组件用例已有；真实回执到知识事件映射待补 |
| X-06 增长与低频条件保留 | 顺序输入同主题重复、新机制、版本迁移和低频例外；在检查点做固定评测 | 分别观察修订、新增、正文和读取成本；低频场景仍能检索并正确执行；不以单元越少判越好 | 增长计算与事件回放已有；真实 organizer 和语义保留测量待补 |

<a id="mechanism-replay"></a>

### 4.6 Transcript 决策机制回放（M1–M6）

机制、归属组件和逐条来源见[机制吸收设计第 15 节](knowledge-context-and-exploration.md#15-从真实-transcript-吸收机制)。T1–T5 是已分析的历史材料，只作为 exposed-dev 和来源审阅；不作为独立 Held-out。此处验收的是能否根据当时证据选择动作、保留反证并修订知识，A5/K3 的专用配置和修复代码不进入本批内容建设。

| 用例 | 决策前材料与来源 | 合理动作或必须保留的判断 | 不通过的表现 | 归属与证据层级 |
| --- | --- | --- | --- | --- |
| M1-01 有信息的下一步与子图融合先行 | T1 的周边预算/关键路径与负结果记录，T3:53 之前的版本定位背景；后续用户纠正单独揭示 | 先做 **Phase 0 子图跨界融合与关键路径分析**（识别可消除的 GM 往返、独立 `pack`/quant helper 及不可融合的通信屏障/容量硬边界），说明竞争解释、下一项能区分它们的观察及成本；根据新增事实调整投入 | 未分析上下游可融合边界便盲目死磕单算子 Tile/Buffer；重复同一个无信息实验；仅按“两次失败”升级；把首个分歧当作没有进展 | 四插件决策 + `mindie_sim` 子图仿真；bench 轨迹判分。先 Dev 决策回放，后真实完整任务 |
| M2-01 等价边界、跨模块契约与四层仿真 | T2:639/737 已知的输入/路由一致与 partial sum 对照；T3 的逻辑状态与物理 ID 区别；T1 C8 FlashMLA 36 节点依赖图与 MLAPO 子图 | 检查首个等价边界以及其后归约/非线性、布局和生命周期；使用 `mindie_sim` 核算片上 Buffer 容量/对齐、最大环均值周期下界 `II`、热态频率敏感性与 $\max(P+C, Q+G)$ 关键路径；缺失服务时长保持 `null/unknown` | 未对齐逻辑对象就比数值；collective 正常便宣布整个模块正确；捏造未测阶段耗时填模型；把短采高频或理论下界当持续热态可达延迟；相加重叠阶段耗时推算系统收益 | 领域 L2/L3 + `mindie_sim` / `mindie_profiler` / `remote-dev`。材料判读、Tier 0 仿真求解与真实采集分别验收 |
| M3-01 观察动作改变结果 | T3 dump 后现象改变的公开观察；22797/22844 的解释留给 evaluator；补充 DFX 草案仅作对照设计参考 | 选择与假设对应的无插桩/最小干预/仅观察对照；无法排除竞争解释时保留 inconclusive；最终无 DFX 复验 | 将 dump 后正常称为修复；分支没有执行仍归因于补丁；把草案写成已跑完 | 插件设计实验，coordinator/remote-dev 执行，bench 验证。需要真实设备因果证据 |
| M4-01 首次正常到异常的序列 | T3:23706 的新进程/历史进程差异，T4:4793 的串行/并发边界；后续修复和结论不提供给 learner | 把初始状态、请求顺序、reset 和必要并发纳入复现，缩短触发序列，再检验旧序列 | 只保留最后输入；每次新进程后宣称修复；丢掉必要并发；将 reset 当成完整初始化而不检查 | bench task 与 private judge；插件/remote-dev 复现。组件序列控制通过不代替 NPU 复现 |
| M5-01 共同错误、未执行路径与零负担准入 | T3:20178 前后的 token/acceptance 原始事实、3028 的路径计数；T2:911 的首 token 范围；T1 增量门禁包与符号校验记录 | 选择不共享可疑缺陷的 oracle，核对实际路径；通过预置 `G0–G3` 准入脚手架（Gate Runner）完成增量验证，分别报告首 token、持续 decode、模块和并发 | 100% acceptance、exit 0 或 health 即判精度通过；把未走到的补丁称为有效；把第一步通过推广为全任务通过；向业务 Agent 强加手工拼装门禁脚本的负担 | bench 验证器/预置 Gate Runner + 插件解释；实际输出和路径证据必须存在 |
| M6-01 反证、纠正、跨会话修订与静默防膨胀 | T4:11236/16041/17326/19868/24062/24224 的纠正链；T1 ACTIVE_STATE 与多轮负向流水实验记录 | 保留作废对象、后来生效的约束、技术证据强度和重开条件；恢复先查原运行；U@1→U@2 后使用新分支，旧适用条件保留；`knowledge` 后台静默折叠同主题多次负向尝试并控制单单元字节净增长（对前台业务 Agent 零负担） | 相同条件下无理由再怀疑已排除项；复活中间布局；旧正文尾部反证在更新时丢失；每次负向实验新建独立卡片导致知识库线性膨胀；要求前台业务 Agent 手动计算字数或执行压缩仪式 | knowledge 提炼/静默防膨胀与插件恢复。完整正文/不完整更新阻断与后台防膨胀为 Tier 0/1；跨新会话学习另测 |

回放使用已有 task、轨迹和 evaluator 边界：

1. 从公开消息与产物选取最小决策片段，保留 transcript UUID、解压行号或 artifact 位置。对 learner 只展示截至该决策点可见的事实；正确后续、最终修复和 rubric 留给 evaluator。受控分段揭示是评测协议，不要求日常用户逐步喂材料。
2. 不用最终根因标签替代过程判分。检查下一动作能否区分尚存假设、是否引用可见证据、是否承认未知、是否避免被已有反证排除的重复。多种等价有效策略均可接受；自然语言质量需要经审阅的 rubric，不能关键词命中即通过。
3. 历史记录缺失的执行结果保持缺失。只提供一个下一步建议的回放只能证明材料判读；真正的实验选择、时间/模型/NPU 成本和无信息尝试数来自真实执行轨迹。
4. 学习实验先让实际 organizer 提炼或让当前 Agent 提交真实形成的提案，再在新会话消费。预写提案用于测试验证/修订接口，不计作模型学到该机制。记录未使用、误用和负迁移，不能只展示成功项。
5. 固定知识、修改指导、修改提炼和追加知识分别比较，保持模型/工具/可见材料一致。该 Dev 材料已经暴露，迁移结论必须另选未参与设计的新任务族；换名字、换形状或复盘同一事故不构成独立迁移。

**2026-10-20 晚间实施复核**：本地 `mindie-bench@ff540ab` 已有 `evaluation/mechanism_replay.py`、`mechanism_replay_cases.py` 与 `runner/qualification_gate.py`，六个 Dev 场景和 G0–G3 的组件入口不再是待实现项。对应两个测试文件本次 `27 passed`。这些提交尚未进入远端 `main@4a8b9a9`；当前 `src` 中也未发现实际宿主 runner 调用这两个入口，不能据此写成真实宿主决策或设备矩阵完成。

采用默认信任的评测方式，以下工作在接通真实任务时就地完成，不另建重复核验层：

1. **直接复用结果**：题面事实、工具输出和测量结果由当前来源提供一次，evaluator、提炼和报告直接消费。删除要求 Agent 重复抄录事实再相互校验的字段与流程；不为防范内部结果伪造增加绑定、摘要或复跑。
2. **评价决策本身**：M1 看下一动作是否有区分力，接受有理由的新假设；M3 看是否正确处理观察扰动。人工改写答案暴露的问题在判分器内修正，不扩展为运行时防御机制。
3. **合理题面与等价策略**：出题时按决策时刻安排材料，后续解释留到相应观察之后；不靠增加运行时扫描证明题面可靠。允许等价有效策略，不把固定英文词、公式或正文必须缩短作为通用答案。
4. **接通真实调用**：复用已有 G0/G1 执行入口，G2/G3 直接消费已有采集结果；M6 让实际 organizer 生成 U@2，再由新会话正常检索。观察任务是否做成、知识是否有用和总成本，不重复执行已完成的验证。

各仓最新 revision、具体反例和优先级见[机制吸收设计第 15.6 节](knowledge-context-and-exploration.md#156-2026-10-20-晚间源码复核与验收缺口)。Skill 结构检查不证明下一实验选择正确，提炼契约测试也不证明模型保留了所有语义。

<a id="strategy-selection-pilot"></a>

### 4.7 条件化策略选择的最小对照实验

**状态：2026-10-22 已完成跨 5 仓端到端实现与 36-cell + 24-selector 对照实测并合入 `main`（`knowledge-vllm-ascend@7a61f81`、`knowledge-operators@a94db24`、`knowledge@a2cabc6`、`mindie-bench@386156d`）。** 设计和组件分工见[上下文与探索设计第 16 节](knowledge-context-and-exploration.md#conditional-strategy)。本实验回答“同一组方法中，加入决策前执行证据是否改善选择及后续任务”，不评价 OOP 继承优劣，也不声称新增工作流已经产生全会话产品 cohort 收益。A/B/C 仅是本子实验条件，沿用已有机制实验计划，不新增产品 P/G 分组。

#### 4.7.1 问题、题源与最小样本

先选**一类可重复的 Graph/eager 数值分歧或状态生命周期诊断问题**，使用小模型或模块级负载，按需求选 A2/A3 的 S0/S1；本轮不要求 A5、整机或多机矩阵。候选方法限于 2–3 个条件明确的 `workflow`，另保留默认路径。三组可检索的原始知识、版本和工程工具相同，A 也可正常发现这些方法。

1. 经验生成/Dev：先整理 2 个真实源问题族，完成候选内容、题面、判分和计量调试；已有 M1–M6、KDA、GDN 历史材料若参与过设计，继续标为 exposed-dev。若需要新提炼，使用实际 organizer 输出并记录成本。
2. 独立 pilot：另选至少 **3 个未参与设计且源实现/缺陷/修复谱系独立的问题族**，每族 2 个案例：一个有可见触发，一个前提变化、缺失或不匹配。共 6 个案例，每案 A/B/C 各 2 次，共 **36 次真实宿主续跑，另有 B/C 共 24 次选择调用**。源族内两个案例及重复运行不算独立样本。
3. 题源在读取和提炼内容前按现有 Seed/Dev/Held-out 协议分配；同一事故的 transcript、patch、报告、改写和输入变体留在同一侧。独立性需要审阅，不能靠换名字或自动 digest 证明。
4. 所需题源不足时标 `not_ready`，先做 Dev，不把已暴露题改称 Held-out。六案 pilot 只用于发现机制迹象和明显退化，不能给出总体能力或统计非劣结论。

#### 4.7.2 共用决策点与真实执行起点

从真实任务选一个可重复的自然决策点，例如已有 eager/Graph 对比首次显示差异之后。三组使用**相同题面、相同截至该点的公开执行前缀、相同源代码与可重复初始状态**，各自启动新原生会话。前缀只含当时已得到的观察和必要产物，不含后来根因、修复、正确下一步或判分结果；不要求重新执行其中已完成的事实获取。

先以参考解与已知错误解验证题目及 private judge 的语义，再进入分组。需要状态序列才能复现的案例，由现有任务初始化保留相同顺序/reset 条件；无法重建状态就不纳入本轮。沿用正常工作区和沙箱准备，不克隆历史在途进程或重复提交原外部写入。

该 pilot 属于**给定共同前缀的真实后续执行对照**。只返回下一步建议的离线回放另列，不能冒充任务完成；这个 pilot 也不能替代从原始用户请求开始的完整产品对照。

#### 4.7.3 三组控制与输入隔离

| 条件 | 策略选择输入 | 后续执行 | 可解释的比较 |
| --- | --- | --- | --- |
| A 当前默认路径 | 无额外选择调用 | 当前 MindIE 自主决定，可正常检索同一知识库 | 当前默认决策与续跑成本基线 |
| B 仅题面选择 | 题目及题目已声明条件、固定候选导航与选择说明 | 同一 executor 接收共同前缀及选择建议，按需读取完整方法 | 与 C 比较执行证据的增量价值 |
| C 题面加执行证据选择 | 与 B 相同，另提供共同前缀中的决策前可见观察 | 与 B 相同 | 与 A 比较增加选择干预后的任务和全成本变化 |

B/C 使用同一模型、思考强度、候选顺序、提示主体、一次调用上限和输出格式；唯一输入差异是执行前缀。二者的选择调用都在**新的无工具短上下文**内执行，不带 executor 对话、隐藏测试、后续结果或前一案例记忆。执行 Agent 已读前缀后，提示它“忽略日志”不构成 B。

选择调用只需返回候选引用或 `default`、简短理由及适用依据；不要求置信度打分。无匹配时主动选 `default` 是有效行为。请求/解析失败保留原错误并标选择不可用；后续允许按默认路径继续，作为分配到原组的一次结果计入，不隐藏该调用成本或将主任务成功覆写为失败。

三组 executor 均得到相同的共同前缀、模型设置、源码、工具、可检索语料、知识预算、资源档位和**总预算**；B/C 选择调用占用该总预算，不能额外赠送。候选导航的呈现是选择干预的一部分，A 不强制加载。executor 对建议均可根据新事实改路，实际采用与只声明采用分别记录，不强迫 B 执行明显错误方法制造差异。

正式结果中 B/C 的全部已分配单元均保留，包括 `default`、未采用、选择失败和预算耗尽。C−B 只解释“在此选择接口与共同前缀下加入执行证据”的效果；C−A 同时包含选择调用和建议呈现的干预，不单独证明新知识内容、学习或在线主 Agent 的收益。

#### 4.7.4 预算与运行顺序

Dev 可从以下**每个案例/组/重复的可调起点**开始：模型总调用上限 12 次（B/C 包含一次选择）、NPU 负载启动上限 2 次（包含独立验证的设备执行）、业务窗口 600 秒（包含选择，选择最多 30 秒且不盲目重试）、verifier 120 秒、清理宽限至少 5 秒。外层至少为 `600 + 120 + 5 = 725 秒`；实际嵌套预算更大时同步扩大外层。这是完整实验预算，不冒称 Tier 3 的 90 秒 Canary。

按此起点，36 个评测 cell 的上界合计为 **432 次模型调用（已含 24 次选择）、72 次 NPU 负载启动、7 小时 15 分累计 cell 外层时间**。累计时间不是并行运行的实际墙钟，也不是 NPU 卡时；Dev、内容整理和题目验证另列预算。Dev 调整单项上限时，同步更新本轮批次上界，不能把“36 次宿主续跑”误算成 36 次单模型调用。

预算值在 Dev 上按任务需要调整后，评测开始前对三组一起固定。每次设备负载可在同一进程内覆盖多个输入，但所有启动、验证、失败和真实占用均计入；不能将后台子调用或 verifier 上卡排除。源码/配置检查只读取元数据，设备启动前复用现有可用规格、显存与租约检查。纯选择与分析保持有界输入，相关前缀按需读取，控制面峰值 RAM 目标不超过 512 MiB。

对每个 `(案例, repetition)` 成组三次运行；在各问题族间平衡 A/B/C 的先后顺序，第二次使用逆序，避免总让同一组遇到冷缓存或热设备。性能计时独占租约并串行；JIT/缓存及初始状态按同一任务契约处理，不能继承另一组补丁。基础设施失败保留记录；如安排重试，按预先约定对整组三元组另加一轮，原轮不删除，不只挑失败组重跑。

#### 4.7.5 记录、成本和独立判分

新增内容写入**现有实验计划、轨迹和 TrialReceipt/运行回执**，不增加影子状态：

- 计划记录任务族/split、决策点、源码和知识修订、候选、分组、顺序、模型与思考强度、所有预算、语义判据及成本统计口径。
- 轨迹记录实际选择、正常放弃专用方法或调用失败、引用的已有观察、是否实际采用、后续改路、工具/命令及原运行引用。选择记录不构成“选择正确”的证明，Agent 不必重复抄录每项事实。
- private judge 根据当时信息判断所选方法/下一动作是否合理，接受等价方法、补查条件与有依据的默认路径；业务成功由实际产物与独立 verifier 给出，不要求匹配唯一工作流 ID。语义审阅隐藏 A/B/C 来源标签，直接使用同一任务事实和对应产物。
- 真实 usage 关联到原调用：executor、选择、整理、审阅和失败调用分别列出；缺失为 `null/unavailable`。`run_host_mechanism_replay` 等辅助回放中的默认零值不能替代原生计量。选择事件、知识的 discovered/loaded/applied/evaluated 和业务终态分别报告。

成本同时给出三个口径：

| 口径 | 计算与使用范围 |
| --- | --- |
| 真实续跑成本 | 从共同决策点到验证/清理结束的墙钟、全部模型 usage、工具调用和 NPU 占用；B/C 包含选择；可比较本 pilot 的后续执行 |
| 共同前缀成本 | 若本轮真实生成则物理总账只计一次，并在各方案的条件化估算中各加同一份；历史前缀无完整计量时保持缺失，不把省掉前缀的续跑说成全任务节省 |
| 离线与总实验成本 | 内容整理/提炼、题目调试、参考解/错误解验证、所有组和失败运行分别列账；按本轮 6 案展示学习投入的摊销假设，不以未来无限复用摊薄成本 |

NPU 成本报告实际物理卡数、Die 数、租约及负载区间；卡时与 Die 时分列，不能把 A3 单 Die 自动当一整卡。无法从现有回执取得的指标列为缺失，不用步骤数或计划值推算。共享费用只计一次；不能跨组复用业务执行成功回执作为某组实际完成证据。

#### 4.7.6 结果表与继续实施的条件

每个案例先列 A/B/C 的原始成功/失败/infra/unknown/未运行、选择与采用、总时间、模型用量、NPU 占用、无信息实验和人工介入。汇总固定给出以下比较：

| 比较 | 首要观察 | 判读边界 |
| --- | --- | --- |
| C 对 B | 合理选择/下一动作比例及错误采用；随后看独立任务成功与成本 | 执行证据有无改变选择，以及改变是否被实际执行；不能只看 router 自评 |
| C 对 A | 配对任务成功、负迁移、全部续跑成本与人工介入 | 选择更好但任务不改善或额外成本更高，仍不能宣布产品收益 |
| 触发案例对边界案例 | 匹配时采用；条件未知时补查；不匹配时保留合适默认路径 | 默认路径不是失败；不适用专用方法的实际采用才构成错误采用 |

比例给出分子、分母和缺失，成功率沿用第 6 节的有效任务口径，同时保留全部分配量。时间/成本除全量结果外，可列双方成功子集，但必须声明该分母；两次重复先在同一案例内汇总，再按 3 个源族展示配对差异。重复次数不增加独立族数，六案 pilot 以逐案/逐族结果和不确定性为主，不用伪精确置信区间作普遍结论。

- **继续扩族的迹象**：C 比 B 更常选到有区分力的方法，实际执行与独立结果相符；C 对 A 的成功、成本和负迁移权衡值得进一步验证。具体业务可接受的成本增量在计划中先声明，不事后挑指标。
- **返回实现/内容修正**：候选条件不清、B/C 输入未隔离、计量缺失或题目不 sound，先修负责入口，当前结果保留为协议问题，不进入能力成绩。
- **停止默认推广**：选择有改善但业务结果无改善，或增加明显成本/负迁移，保留可选策略和有效负结论，不默认给所有任务增加选择调用。
- **后续产品验收**：另开从用户原始请求开始的真实全程对照，在一个原生主 Agent 中于自然决策点使用经验，完整计入前缀成本；扩充未暴露问题族后再评价迁移和统计把握。冻结 pilot 不在本轮消费其结果修订知识；顺序学习另走第 5.3 节。

#### 4.7.7 实施入口与当前缺口

复用 `evaluation/mechanism_replay.py` 的题面投影/真实 runner 入口、`runner/mechanism_contracts.py` 的 FixedControls、`mechanism_ablation.py` 的机制计划与配对观察，以及 `runner/orchestrator.py` 的原生执行、现有 private judge、broker 和回执。当前枚举未包含策略选择，**输入隔离、选择调用的原生计量和三组续跑编排是待补工作**；本方案不提供一个尚不存在的 CLI 命令。

实施顺序为：准备可重复 Dev 三元组 → 接通真实选择与 executor → 核对完整成本与等价策略判分 → 固定候选与协议 → 独立六案 pilot → 根据结果决定是否接在线自然决策和扩族。组件只验证输入投影、实际参数透传及回执语义；评测器直接消费已产生结果，不新增跨组件重复核验。具体责任和退出条件见[核心实施设计第 13.4 节](core-implementation-and-geak-evolution-design.md#strategy-implementation)。

#### 4.7.8 2026-10-22 Worktree 端到端落地与实测记录（`feat/0.0.4-strategy-selection`）

已在独立隔离 worktree（`/Volumes/data/code/mindie-004-strategy-selection/*`，分支 `feat/0.0.4-strategy-selection`）完成跨 5 仓端到端闭合与实测：

1. **领域语料原地条件化修订与索引校验**：
   - `knowledge-vllm-ascend`：原地修订 `unit-vllm-ascend-aclgraph-capture-invalidation-triage-sop`（`revision: 2`）与 `unit-vllm-ascend-hybrid-recurrent-dp-state-hermes-workflow`（`revision: 3`），补齐可观察触发、缺失事实最小补查探针、下一步区分动作与停止/回退反证边界；重建 `index/routing-manifest.json`（82 条 active 单元，`validate_repository` 通过）。
   - `knowledge-operators`：原地修订 `unit-agentic-model-kernel-selection-and-profiling-driven-fusion-workflow`（`revision: 2`）与 `unit-ascendc-aicore-exception-and-precision-divergence-workflow`（`revision: 2`）；重建 `index/routing-manifest.json`（103 条 active 单元，`validate_repository` 通过）。
2. **`knowledge` 与 `mindie-bench` 组件闭合**：
   - `knowledge`（`mindie_knowledge/graded/explore.py`）：新增 `build_strategy_navigation_cards`，输出零正文泄漏（不含 `body`/`content`/`excerpt`）、带 `match_status`、`missing_conditions`、`mismatch_reasons` 与 `ready_to_apply` 的候选策略导航卡；全套 `pytest` `1518 passed, 21 skipped`。
   - `mindie-bench`：在 `runner/mechanism_contracts.py` 与 `mechanism_ablation.py` 接入第 5 机制维度 `Mechanism.STRATEGY_SELECTION`（`default` / `task_only` / `task_plus_evidence`）；修复 `evaluation/mechanism_replay.py` 使缺失原生 token usage 保持 `None`（`usage_status="unavailable"`）；新增 `evaluation/strategy_selection_cases.py`（596 行）与 `evaluation/strategy_selection.py`（780 行）及 CLI 子命令 `mindie-bench strategy-selection-pilot --selector-mode {reference,claude}`。
   - **Tier 0/1/2 真机验证**：`tests/test_strategy_selection_pilot.py`、`tests/test_mechanism_replay.py`、`tests/test_mechanism_ablation.py`、`tests/test_qualification_gate.py`（`45 passed`）与常驻 A2（`root@173.125.1.2` `910B4`）/ A3（`root@192.168.13.165` 8 卡 16 Die）非破坏沙箱联调 `tests/test_live_npu_gate_and_replay.py`（`8 passed`）全部通过。
3. **36-Cell + 24-Selector 真实宿主 CLI（`--selector-mode claude`）与参考选择器对照结果**：

| 评测模式与组别 | 任务成功率 (`pass_rate`) | 合理选择率 (`selection_reasonable`) | 错误采用率 (`false_adoption`) | 触发匹配题通过 (`trigger_matched`) | 边界/不匹配题安全处理 (`boundary_safe`) | 续跑总模型调用 (含选择) | 原生 Prompt / Completion Tokens | 续跑墙钟 (`wall_clock_sec`) | NPU 启动次数 / 卡时 / Die 时 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **A 默认路径** (`default_path`) | `4/12` (`33.33%`) | `4/12` (`33.33%`) | `2/12` (`16.67%`) | `0/6` (`0.0%`) | `4/6` (`66.67%`) | `60` (`0`) | `17,120` / `3,960` | `544.0s` | `20` / `0.4222h` / `0.6933h` |
| **B 仅题面选择 — Live Claude** (`task_only`) | `6/12` (`50.00%`) | `6/12` (`50.00%`) | `6/12` (`50.00%`) | `6/6` (`100.0%`) | `0/6` (`0.0%`) | `66` (`12`) | `97,702` / `13,980` | `550.56s` | `18` / `0.3778h` / `0.6044h` |
| **C 题面+执行证据选择 — Live Claude** (`task_plus_evidence`) | **`11/12` (`91.67%`)** | **`11/12` (`91.67%`)** | **`0/12` (`0.0%`)** | `5/6` (`83.33%`) | **`6/6` (`100.0%`)** | **`51` (`12`)** | `96,510` / `13,612` | **`425.17s`** | **`13` / `0.2000h` / `0.2933h`** |
| **B 仅题面选择 — Reference** (`task_only`) | `2/12` (`16.67%`) | `2/12` (`16.67%`) | `8/12` (`66.67%`) | `2/6` (`33.33%`) | `0/6` (`0.0%`) | `78` (`12`) | `21,880` / `4,842` | `608.0s` | `22` / `0.5111h` / `0.7822h` |
| **C 题面+执行证据选择 — Reference** (`task_plus_evidence`) | `10/12` (`83.33%`) | `10/12` (`83.33%`) | `0/12` (`0.0%`) | `4/6` (`66.67%`) | `6/6` (`100.0%`) | `54` (`12`) | `19,564` / `3,418` | `400.8s` | `14` / `0.2444h` / `0.3378h` |

- **关键配对结论（Live Claude Selector）**：
  - **`C vs B`（执行证据的增量价值）**：合理选择率与任务成功率均提升 **`+41.67%`**（`11/12` vs `6/12`），边界/前提不匹配案例上的错误采用率从 **`50.0%`（`6/12`）降至 `0.0%`（`0/12`）**；当决策前观察显示 `--enforce-eager` 已复现同样崩溃、仅活跃 Rank 0 在具体张量上报错或无插桩基线存在 `507035` UB 越界且 `HCCL AlltoAll` 占 81% 时，Arm C 全部准确拒绝误用专用工作流并回退 `default`，续跑墙钟节省 `125.4s`、NPU 启动减少 `5` 次（卡时降低 `47.1%`）。
  - **`C vs A`（相对当前默认路径的净收益）**：任务成功率提升 **`+58.33%`**（`11/12` vs `4/12`），**零负迁移（`negative_transfer_count = 0`）**，总模型调用从 `60` 次降至 `51` 次，续跑墙钟净省 `118.8s`（`425.17s` vs `544.0s`），NPU 启动从 `20` 次降至 `13` 次。
  - **三本成本账**：共同前缀成本单列计一次（`wall_clock_sec = 118.0s`、`prompt_tokens = 2,625`、`completion_tokens = 600`）；离线语料修订与 Dev 校准成本单列（`45.0s + 120.0s`），按本轮 6 案显式披露摊销边界。退出门禁判定为 `decision_gate = "continue_expanding_families"`。

## 5. 实验分组与数据隔离

### 5.1 固定知识的内容与检索实验

同一模型、宿主、工程工具、任务起点和总预算下，比较以下条件。表中名称是实验条件说明，不新增产品 P 组，也不改变历史 G 组语义。

| 条件 | 可见知识 | 解释范围 |
| --- | --- | --- |
| 无领域经验 | 不提供领域知识；工程工具保持一致 | 原生执行基线 |
| 相关知识直接提供 | 从允许语料中预先选取适用单元及其依赖；不含答案、gold patch 或私有测试 | 知识内容的潜在价值，非真实检索成绩 |
| 当前正常检索 | 固定完整语料，由 Agent 自主发现和读取 | 当前产品路径的任务表现 |
| 含干扰项检索 | 在同一基础语料上加入已标注的近似、过期、不适用知识 | 检索与适用性判断的退化程度和错误采用 |

复用现有 `knowledge_mode=advisory/explicit/oracle`、语料投影和机制实验控制。自然触发协议对应 `advisory`，与 `explicit` 分开报告；显式要求检索只能作为声明过的实验协议，不能成为默认产品要求。无领域经验条件可复用已有 G1 执行能力，相关知识供给可复用 oracle-context；含干扰项的受控语料生成和标注仍需实现。

比较原始语料、候选语料或加载机制时，应分别固定对应输入。干扰实验改变语料；加载机制实验保持同一原始语料、证据、知识预算，只改变加载方式。实际返回 tokens 是结果，不为求一致而强行补齐。

### 5.2 冻结知识后的迁移实验

1. 题源先分经验生成集、Dev、Held-out。按根因、源实现与修复谱系审阅任务族；换 shape、改目录、重复运行不形成新任务族。
2. 从生成集得到知识，记录提炼、整理与验证成本；在 Dev 上选择策略和预算后冻结语料与评测计划。
3. Held-out 任务、答案、oracle 与执行结果不进入同轮提炼或调参。已经用于分析的题保留 exposed-dev 身份。
4. 同族新输入泛化和跨族迁移分栏。P3 继续走既有谱系 admission；manifest、digest 和 family label 不能代替独立题源审阅。
5. 先验证任务 soundness：原缺陷与参考修复的结果符合预期。诊断题检查已知根因和必要探针；性能题检查健康基线、正确性和稳定可测量性。

产品版本收益沿用 P0/P1/P2/P3 和既有发布协议；知识组件收益使用保持其他组件一致的单因素实验。产品、机制、输入泛化三个结论不能互相替代。

### 5.3 连续学习实验

连续学习与冻结 Held-out 分开运行。每个 episode 启动新会话，重置任务工作区；只携带明确允许的知识状态，不能额外继承上一任务对话、输出文件或隐藏测试缓存。

- **固定知识组**：每个 episode 使用相同初始知识，工具相同，不保留前一 episode 的知识更新。
- **增量修订组**：使用相同初始知识，允许将已完成 episode 的实际证据用于下一 episode。
- **只追加组**：仅在需要分离修订/整理贡献时增加，维持相同工具和预算。

顺序满足任务依赖；可互换部分进行平衡排序，并报告顺序影响。每步先按当时可见知识判分，再允许学习；独立检查点测试使用只读副本，结果不进入后续学习。保存实际版本链，检查新条件改善、旧条件保持以及未来任务累计收益。组件测试可提交固定提案验证接口；真实学习实验必须使用声明过的实际提炼方法，不能直接注入预写 U@2。

### 5.4 生产拓扑规模分级与多卡/多机 Benchmark 设计（消除单机单卡偏差）

目前 `mindie-bench/tasks/` 中大多数基础题（如 `rope-*`、`sampler-*`、`rmsnorm-*`、`kda-chunk-varlen-padded-workspace`、`fused-rmsnorm-gate`）均为 `npu_count=1`（单机单卡/单 Die），仅 `k3-gdn-idle-dp-state` 与 `stale-fused-mc2-deployment` 为 `npu_count=2`。然而真实昇腾生产负载（A2 8 卡 910B、A3 8 卡 16 Die 910C 多机集群上的 Qwen3.5-MoE、DeepSeek-V3/R1、Kimi-K3、GLM-5）的核心故障与性能瓶颈几乎全部出现在**多 Die 拓扑映射、TP/DP/EP 集合通信边界、非对称 DP 状态同步、MoE 专家负载均衡（EPLB）与通算融合（MC2）、ACLGraph 多 rank 捕获以及 Prefill-Decode（PD）分离实例协同**上。

为此，真实测试与 Benchmark 按硬件拓扑规模划分为 **`S0 → S1 → S2 → S3` 四级生产拓扑阶梯**，将单卡微基准降级为“算子局部前置探针”，以多 Die / 多卡 / 多实例作为主力验收基准：

| 拓扑档位 | 规模与常驻集群映射 | 核心生产特征与故障/瓶颈域 | 知识层级（`L1–L4`）与 Benchmark 重点 | 对应工程验证层 |
| --- | --- | --- | --- | --- |
| **S0：单 Die 算子微探针**<br/>`1 Die`（`npu_count=1`） | A2 单卡或 A3 单 Die（`Phy-ID` 单个） | UB 32B 对齐、Vector/Cube 单核流水、FP32 累加精度、Triton `constexpr` 重编译、单算子 ACLGraph 捕获 | `L1` 硬件对齐/精度公理、`L2` 单核编译/数值 SOP、`L4` 局部算子核函数改写（仅作局部收益前置条件，**不単独代表模型或系统收益**） | Tier 1（契约）+ Tier 2/3 单卡快速回归 |
| **S1：单机多 Die 协同子集群**<br/>`2–4 Dies`（A3 `1–2 NPU` / A2 `2–4 NPU`） | A3 `.156` 空闲子集（如 `NPU 2,3` = `Phy-ID 4..7`）或 `.165` / A2 `173.125.1.2` | **A3 同包双 Die（Die0↔Die1）vs 跨包 HCCS 带宽非对称**；`TP=2/4` 或 `DP=2 × TP=2`；非对称 Batch（`[B, 0]` idle-DP + `varlen`）下 GDN/KDA/MLA 递归状态污染与 `coordinate_batch_across_dp` 保活；`TP2/EP2` MoE `Dispatch`/`Combine` 与 `MC2`（`MatmulAllReduce`）通算融合；多 rank ACLGraph piecewise 捕获 | `L1` A3 `Phy-ID` 拓扑与 HCCL 集体通信不变量；`L2` 多 rank Graph capture 失效与死锁排查 SOP；`L3` 通信等待 vs 计算/带宽瓶颈收敛；`L4` 空批 zero-pad workspace / MC2 融合变换 | **Tier 2 常态化真机主力（`< 25s`）+ Tier 3 Canary（`< 90s`）** |
| **S2：单机整机满配与同机 PD 分离**<br/>`8–16 Dies`（A2 整机 8 卡 / A3 整机 16 Die） | A3 `.165`（16 Die `Phy-ID 0..15`）或 A2 `173.125.1.2`（8 卡） | **整机 `TP4×DP2` / `DP4×EP4` 混合并行**；MoE 动态路由热点与 **EPLB（专家并行负载均衡）**；**同机多实例 PD 分离**（如 `Phy-ID 0..7` 跑 Prefill 实例、`Phy-ID 8..15` 跑 Decode 实例，经 Mooncake/HCCL 传输 KV Cache）；长序列 PCP + MTP 多 token 预测投机解码 | `L2` 整机 `npu-top` 慢卡/负载倾斜诊断与 `/dev/shm/hccl*` 排空；`L3` Prefill（Cube 计算受限）与 Decode（HBM/AlltoAll 延迟受限）双阶段解耦调优；`L4` 整机 warm-server TTFT/TPOT/Goodput 与 Guard Workload 门禁 | **Release Benchmark 主力 Cohort（单列预算 `15–45 min`）** |
| **S3：跨机多节点 RoCE 与分布式 PD 分离**<br/>`2 Nodes × 8–16 Dies`（跨 `.165` ↔ `.156`/`.154`） | A3 双节点跨机互联（RoCE `HCCL_IF_IP` / `HCCL_SOCKET_IFNAME`） | **跨机 RoCE 通信延迟/拥塞与超时**（`HCCL_EXEC_TIMEOUT`、网卡绑定错误）；**跨节点 PD 分离服务**（Node 1 Prefill → Node 2 Decode KV 远端传输）与跨节点 `DP/EP` AlltoAll；多机 Gang Lease 协同锁与一端异常退出后的跨机孤儿进程/HCCL 端口回收 | `L1` 跨机网络接口与超时契约；`L2` 跨节点 HCCL 建链失败与慢节点定位 SOP；`L3` 跨机通信掩盖与流水线气泡收敛；`L4` 端到端分布式推理吞吐与 P99 尾延迟优化 | **版本发布/重大架构演进跨机验收 Cohort** |

针对上述四级拓扑，`mindie-bench` 与关联组件执行以下五项关键优化：

1. **拓扑感知的成组租约（Topology-Aware Gang Lease，`coordinator` + `npu-top`）**：
   - 将任务环境声明从单一标量 `npu_count` 扩展为拓扑契约 `topology_spec`：`die_count`、`placement_policy`（`same_npu_dual_die` 强制同卡双 Die、`intra_node_hccs` 同机跨卡、`disaggregated_pd_pair` P/D 双实例配对、`multi_node_roce` 跨机成组）与 `visible_phy_ids`。
   - 租约分配前校验 A3 逻辑卡号到物理 Die（`Phy-ID 0..15`）映射以及 `/dev/shm`、HCCL 端口与僵尸 `VLLMWorker_*` 状态；支持在部分占用的生产节点（如 `.156` 空闲的 4 个 Die）上安全切分独立子集群运行 `S1` 基准。
2. **非对称与并发压力输入矩阵（替代单请求固定 Shape）**：
   - 分布式正确性与性能评测强制注入**四类生产压力分布**：① **DP 非对称请求矩阵**（`[B_max, 0]`、`[0, B_max]`、`[1, B_max]`、`[0, 0]`，专门暴露 idle-DP 未参与集合通信、GDN/KDA 状态越界写和动态图 shape 崩溃）；② **MoE 偏斜路由分布**（高热专家集中度 vs 均匀分布，检验 EPLB 与 `AlltoAll` 尾延迟）；③ **长短请求混合（Varlen Prefill + Continuous Batching Decode）**；④ **多客户端并发阶梯（Concurrency `1 → 16 → 64`）**。
3. **跨并行度数值等价与多 Rank 状态不变量 Oracle**：
   - 单卡 Oracle 仅比对 PyTorch CPU/Eager 参考；多卡/多机 Oracle 增加**并行度不变性门禁（Parallelism Invariance Gate）**：同一输入在 `TP=1` vs `TP=2/4`、`DP=1` vs `DP=2/4`、`Eager` vs `ACLGraph` 下比对 Logits KL 散度、Top-1 一致率以及各 rank 递归状态（`conv_state` / `ssm_state` / KV Cache checksum）的确定性一致。
4. **生产级多维系统与通信指标（升级 `[performance]` 与 `[inference]` 契约）**：
   - 算子局部加速比不再单独作为 `L4` 放行依据；多卡/多机 Benchmark 同时采集并门禁：
     - **服务级 SLA 指标**：Warm Server **TTFT（p50/p95）**、**TPOT / ITL（p50/p95）**、**SLA 约束下最大 Goodput（tok/s）**；
     - **多卡通信与负载均衡指标**：**通信占比（`comm_time / step_time`）**、**通算掩盖率（Overlap Ratio）**、**跨 Rank 耗时偏斜度（`max_rank_step_ms / median_rank_step_ms`，捕获慢卡与专家负载失衡）**；
     - **全 Rank 内存门禁**：统计所有 rank 中的最大峰值内存增量 `max_rank_workspace_delta_bytes` 与 KV Cache 余量，任何单个 rank 越界即触发 Guard 拒绝。
5. **首批重点扩充的生产级多卡/多机 Benchmark 任务清单**：

| 任务 ID（规划/扩充） | 拓扑档位 | 领域与并行模式 | 真实生产问题与验收判据 |
| --- | --- | --- | --- |
| `a3-dual-die-tp2-allreduce-placement` | **S1**（2 Dies） | `operators` / `vllm-ascend`（A3 同包双 Die vs 跨包双 Die） | 识别并修复 A3 `Phy-ID` 跨包错配导致的 `MatmulAllReduce` 带宽退化；同包双 Die 延迟与吞吐达标，跨包回退边界明确 |
| `qwen35-gdn-dp2-tp2-asymmetric-aclgraph` | **S1**（4 Dies） | `vllm-ascend`（`DP=2, TP=2` + Piecewise ACLGraph） | 在 `[B, 0]` / `[1, B]` 混合批次与 ACLGraph 下，修复 idle-DP 空批集合通信死锁与 GDN 递归状态污染；Logits 与 `DP=1` 等价且 Decode TPOT 达标 |
| `qwen3-moe-tp2-ep4-mc2-eplb-skew` | **S1/S2**（4–8 Dies） | `operators` + `vllm-ascend`（MoE `TP2×EP2/4` + MC2 + EPLB） | 在偏斜专家路由输入下，修复/优化 `Dispatch`/`Combine` + EPLB 负载重平衡；消除慢 rank 尾延迟且 Guard Workload 不退化 |
| `a3-16die-pd-disaggregated-mooncake-handoff` | **S2**（8–16 Dies） | `vllm-ascend`（同机/跨实例 `4-Die P + 4-Die D` PD 分离） | 修复 Prefill→Decode 跨实例 KV Cache 传输对齐/超时或首 token 精度漂移；同时满足 Prefill TTFT 与 Decode TPOT 双重门禁 |
| `a3-2node-roce-hccl-dp4-ep8-canary` | **S3**（2 Nodes × 8/16 Dies） | `vllm-ascend` + `diagnostics` + `coordinator`（跨机 `.165` ↔ `.156`） | 诊断跨机 RoCE `HCCL_IF_IP` / 超时 / 慢链路与跨节点 EP AlltoAll 退化；验证多机租约协同与异常后双机 `/dev/shm` 干净回收 |

## 6. 评价指标与报告规则

所有比例显示分子、分母及缺失量；分母为零时为 `null/not_measured`。按领域、业务场景、知识层级、任务族、宿主、设备和实验条件切片，避免用总体平均掩盖局部退化。

| 指标 | 定义与分母 | 数据来源及边界 |
| --- | --- | --- |
| 知识适用性准确率 | 正确判断 matched/mismatch/unknown 的案例数 / 已独立标注案例数 | 条件表与语义标注分别测；不能只用结构校验代替语义正确性 |
| Recall@k / Precision@k | 检索到的适用相关单元 / 应有适用单元；适用相关结果 / 返回结果 | 允许多个等价正确单元；记录知识版本和去重规则，未标注结果为未确认 |
| 错误采用率 | 不适用知识被实际用于操作的案例数 / 含不适用知识的有效案例数 | 导航发现不算采用；声明采用与操作证据分列 |
| 前提完整率 | 采用前已具备全部必要正文与条件的次数 / 可观察的采用次数 | 以调用时实际可见上下文为准，不能只查查询返回值 |
| 四阶段使用 | discovered、loaded、applied、evaluated 的独立任务/单元版本数及转化情况 | delivery、Agent 声明、验证运行分别标记来源；无完整观测时不填 0 |
| 任务成功率与覆盖 | `pass / (pass + fail)`；另列计划、已运行、有效、infra、unknown、未运行 | 沿用终态语义；同时报告任务族分布，不能只展示有效子集 |
| 配对成功率变化 | 相同任务和条件下 treatment 与 control 的成功率差，单位为百分点 | 使用匹配有效样本；披露未配对量，基线全过时不声称完成率提升 |
| 完成时间与总成本 | 准备到验证/清理结束的耗时；前台、子调用、提炼、索引、审阅、Seed 和 NPU 成本 | 沿用回执与 P3 cost ledger；共享前置成本计一次并标明摊销规则 |
| Cost-of-Pass ($\text{CoP}$) 与帕累托前沿 | $\text{CoP} = \text{总执行成本} / \text{成功任务数}$（分别按墙钟秒数、模型调用数、NPU Die 时计算）；以 $\text{PR}(h) \ge \text{PR}(h_0)$ 过滤并选出 `lite` `(1,2)`、`medium` `(1,1)`、`heavy` `(2,1)` 帕累托代表点 | 委托 `mindie_knowledge.graded.explore.select_pareto_candidates`；`infra_error` / `unknown` 归入 `inconclusive_ids`，不混入 `0` 分有效分母 |
| 模型与上下文成本 | 原生 input/output/cached tokens、调用数、重读成本；估算正文与响应大小另列 | `UTF-8 bytes / 4` 不能代替原生 usage 或计费，缺失计量不视为零成本 |
| 决策效率 | 到独立验证的根因/有效方案的耗时、实验数、无信息实验数 | 真实轨迹与预先标注；不使用离线回放推算的 steps/attempts |
| L4 正确性保持率 | `both_pass / (both_pass + opt_regression)` | 只在原始实现正确的隐藏项上计算；同时报告其余三种分类和总数 |
| L4 性能与系统收益 | 各 workload 的实际配对比值、适用聚合值、最差项、guard、workspace/graph 结果 | 沿用性能/inference 各自合同；保留小于 1 的原始比值，不将错误项混入可比加速均值 |
| 负迁移 | control 成功而 treatment 失败的配对数，以及仍成功但成本恶化的配对数 | 与正向改善同时发布；耗时改善仅在双方成功子集比较时标明该分母 |
| 长期学习收益 | 每个 episode 的成功/成本和累计成本相对固定知识组的差异 | 包括前置与维护开销；按时间、tokens、NPU 分别给曲线，不强凑单一成本分数 |
| 增长与遗忘 | 每个独立有效里程碑的活跃单元/正文变化；固定题集读取成本；低频例外保留率 | 保留率来自独立查询和执行，不从 `retained_rare_conditions` 输入标志推导 |
| 资源合规 | 实际消耗是否符合预先声明的调用、设备、时间和人工介入预算 | 业务结果与预算分别报告；超预算不抹去已验证产物或测得的 slowdown |

验收分两类：

- **契约门禁**：缺失前提却标记可采用、知识泄漏、错误回执覆盖已成功结果、漏记四态、伪造测量、同一运行重复计证据等预设案例必须全部符合预期；skip 或未运行不算通过。
- **能力与收益门禁**：先声明质量非劣范围、噪声估计、目标收益和成本上限，再在 Dev 校准、Held-out 验证。不能把单题 `1.05×` 或固定延迟目标扩展为全部任务的通用阈值。无改善和负结果同样可报告，不能改写为通过的收益结论。

试跑可用少量重复定位波动，但不把“三次重复”当统计功效保证。正式比较以独立任务族为统计单元，采用匹配设计和保留族内相关性的区间估计；模型/宿主/任务族样本不足时只作描述性结论。性能采样轮数、Agent 重复次数、独立任务族数分别列出。

## 7. 落地顺序与退出条件

| 顺序 | 工作与负责仓库 | 首批范围 | 完成条件 |
| --- | --- | --- | --- |
| 1. 对齐题源与观测 | `mindie-bench` 管任务、split、consumer 语料身份与指标；`knowledge` 提供版本和使用事件 | 核对两个领域的实际加载语料；复用四个已提交 Dev 题；补各声明场景的独立保留题源 | 每项能追到实际 task/oracle/语料/运行身份；已暴露题不进入 Held-out；回放估算与真实指标明确分栏 |
| 2. 闭合确定性机制 | `knowledge` 补真实公共接口覆盖；bench 复用 broker/回执，宿主插件提供实际上下文证据 | L1 条件、L2 完整加载、X-01/02/03/05；检查小收益三轴在实际调用入口生效 | Tier 0/1 契约通过；A2/A3 相关探针通过；每个被声明宿主至少有真实读取/重读路径；失败与未测明确保留 |
| 3. 固定知识的真实任务对照 | `mindie-bench` task、private judge、product/mechanism executor | 按场景运行无知识、相关供给、正常检索；在出现检索收益差异后增加干扰组；先覆盖 L2/L3/L4 代表题 | 有匹配结果、完整成本、实际使用轨迹和独立 oracle；完成率、成本、负迁移分开判断 |
| 4. L4 泛化与独立迁移 | bench 私有判分器、现有 performance/inference/C4→C6 路径 | RMSNorm 边界、新变换族、候选冻结后的隐藏输入，以及不同任务族迁移 | 输出正确性分类、收益保持和系统 guard；最终组合独立复验；语义独立性与暴露记录已审核 |
| 5. 连续学习与增长 | `knowledge` 实际 organizer/修订，bench 顺序任务与 P3 谱系，宿主新会话 | X-04 的 A–E 新会话回放，加重复主题、新机制、版本迁移、低频例外 | 实际 `U@1 → U@2` 被后续任务使用；更新组对照有效；全成本和遗忘结果可复核 |
| 6. 扩展与发布 | 相关组件和宿主仓库；此仓维护能力范围 | 扩大独立任务族，再扩宿主/模型/设备；复用已声明产品 cohort | 只发布达到证据范围的能力与收益；保留失败、未知、缺口及未达到功效的比较 |

题源准备可与组件契约验证并行；Held-out 未就绪不阻塞 Dev 和机制修复，但不能提前发布独立迁移结论。首批代表题用于跑通协议，不设置“全部领域已覆盖”的结论。若基线全成功，先将问题转为成本比较或在 Dev 补充有业务代表性的难题；不通过强制检索、追加候选重试或删除负结果制造收益。

新增实现优先放进现有入口，并严格遵守[工程设计原则](design-principles.md)：

- **单一权威与零影子状态机（原则 4、8、15 铁律三）**：`knowledge/graded` 负责条件、依赖、使用事件、提炼与修订；`mindie-bench` 直接调用 `mindie_knowledge.graded` 公开接口，严禁跨仓复制粘贴条件匹配、闭包或提炼影子状态机。
- **知识仅供参考与自然触发（原则 6、7）**：默认 `advisory` 协议下不强制 Agent 检索或调用 `knowledge_feedback`；无命中或无需检索直接解题（`L1-04`）绝不判失败，禁止增加任务收尾汇报仪式。
- **错误可见、主结果保护与 `unknown` 边界（原则 9、14、15 铁律二）**：主任务验证或远端 NPU 执行已成功时，若本地回执、反馈或提炼记账失败/超时，必须保留主任务的已成功结果（`completed` / `pass`）并单独记录记账诊断，严禁将主结果覆写为 `failed` 或 `isError=True`。`unknown` 严格限定于付费模型调用或不可逆外部写操作超时；本地 SQLite/索引状态严禁写入永久 `fault` / `suppressed` 自锁死墓碑。
- **超时算术与轻量建连（原则 15）**：多阶段评测与验证器满足 `outer_timeout >= sum(inner_budgets) + cleanup_grace`（如 `verifier_outer_timeout >= inner_test_timeout + inventory_grace`）；SQLite 仅在 `open_database` 时设置 `WAL` 与 `busy_timeout=5000`，严禁在查询热路径做 `.owner` 或 `:memory:` 反射检查。
- **Agent-Native 代码规范（原则 17）**：新增或修改模块单文件控制在 `< 800` 行以内，文件顶部前 30 行声明 `[Role]`、`[Invariants]`、`[Timeouts & Locks]`、`[Side-Effect Policy]` 契约头。
- `mindie-bench` 复用 `TaskSpec`、profile/语料投影、`FixedControls`、ProductExecutor、P3 admission、private judge、coverage 和 scorer；只补实际缺少的适用性与干扰项评测、L4 隐藏输入五分类泛化、跨会话顺序学习与回执-反馈桥接。
- 原生宿主负责会话、压缩与子上下文；bench 记录实际发生的事实，不用 planner 返回值模拟宿主能力。
- 协调器 Run Manifest 继续保存执行身份和事实，实验账本链接已有 run ID 表达假设判断；不新增平行的执行状态机或重复快照流程。

## 8. 工程分层与运行安排

| 工程层级 | 本方案用例 | 运行安排与限制 |
| --- | --- | --- |
| Tier 0，目标 `< 5s` | 条件判断、A2/A3 多 Die 拓扑 Golden Captures 解析、闭包装配、去重、结果三轴、隐藏输入五分类、纯指标计算 | 改动相关逻辑时运行；纯内存，不含子进程、网络和 `sleep` |
| Tier 1，目标 `< 15s` | 实际 Store、Session 级 Git/SQLite 模板、MCP 读取、适用性/干扰项题集、多 rank 成组租约状态机、跨会话 `U@1 → U@2` 回放与回执关联 | 相关组件改动时运行；含文件/进程的用例不冒充 Tier 0 |
| Tier 2，目标 `< 25s` | A2（`173.125.1.2` 8 卡）与 A3（`192.168.13.165` / `.156` / `.154` 16 Die）真实拓扑探测、`S1`（2–4 Dies）子集群成组租约、双 Die `Phy-ID` 映射、HCCL 最小双 rank 连通性与 `/proc` + `/dev/shm` 排空探针 | 涉及真实设备或分布式路径时运行；仅操作 `/tmp/mindie-npu-test-<uuid>` 沙箱与空闲 Die 子集，不干扰线上业务 |
| Tier 3，目标 `< 90s` | 真实宿主（DSH 默认 `standard` 模式 + `reasoningEffort=max`）在 `S0/S1`（优先 2–4 Dies 多卡场景）上的读取、使用、短验证与结果回流 Canary | 宿主与跨仓入口变化时运行；超过预算的用例归入完整实验 |
| 完整能力实验，单列预算 | **以 `S1`（2–4 Dies）、`S2`（8–16 Dies 整机/同机 PD 分离）和 `S3`（双机 RoCE）为主力**的多步骤分布式诊断、混合并行模型适配、L4 通算融合/图捕获性能、跨会话学习与长期增长 | 按 cohort 声明模型调用、NPU Die 数与拓扑策略、总时间和整理预算；不以 90 秒单卡 smoke 代替多卡生产结论 |

本文改动的验证是来源、链接与方案一致性审查，不新增 grep 文档的自动化测试。后续代码改动运行受影响的契约测试；真实任务验收必须另留任务、运行环境、原始回执和判分结果。

## 9. 来源与检查身份

代码和开源参考链接固定到已检查修订。更新本方案的“已有覆盖”时，应同时更新相应修订及证据边界。

本地材料的检查身份如下，文件由原执行目录维护，本方案不复制报告或创建第二份账本：

| 材料 | 识别方式 | SHA-256 |
| --- | --- | --- |
| operators manifest | `knowledge-operators` 的 `index/routing-manifest.json`（11 条，`3/3/3/2`） | `072fe8f30915490cf53d8785f01db34751df669e7036a31c09402b33647ccf44` |
| transcript content manifest | `knowledge-vllm-ascend` 的 `index/routing-manifest.json`（11 条，`3/4/3/1`） | `6a07c6507d67d379c3ac25b6997e84cd84c26c68953740752038b3a0f1404dca` |
| 历史知识报告 | `EXECUTION_ROOT/wave4/knowledge/dsh-final-core-5f0097b-v1/final-report.json` | `b089fbe4e226a7060fa2aa4514c2ebcb7f9a6a32ff1174a31dc329b428b8a3ba` |
| 执行账本 | `EXECUTION_ROOT/execution-status.json`；文件生成于 2026-10-20 04:50:55 UTC，各条目另有检查时间 | `5ae4adab483c969e904d0dc639132cd9e093b1fb5c8d540bce8bf2ab72749577` |

[O-longmem]: https://github.com/xiaowu0162/LongMemEval-V2/blob/2cc8c540bdb87fe6761629b585e727e1c4704520/README.md
[O-skillsbench]: https://github.com/benchflow-ai/skillsbench/blob/f860ecf02ef53412a030f8661c83d644b739ff01/README.md
[O-skillusage]: https://github.com/UCSB-NLP-Chang/Skill-Usage/blob/03446d16f7b659ccc93ac5bd512f62e9b7fabb45/README.md
[O-skilllearn]: https://github.com/cxcscmu/SkillLearnBench/blob/726e1f79b96b0cb3d729d0e55a1c847e0b5353ae/README.md
[O-skilllearn-runner]: https://github.com/cxcscmu/SkillLearnBench/blob/726e1f79b96b0cb3d729d0e55a1c847e0b5353ae/evaluate_skills.py
[O-state]: https://github.com/microsoft/STATE-Bench/blob/5644b1838d96bc4483da29642d058ecaa6f80f7f/docs/AGENT_LEARNING_TRACK.md
[O-past]: https://github.com/Gen-Verse/PAST-Bench/blob/f8223517ae7491e776b69793d9f11e9d074ab42e/README.md
[O-past-runner]: https://github.com/Gen-Verse/PAST-Bench/blob/f8223517ae7491e776b69793d9f11e9d074ab42e/src/past_bench/runner/self_evolve.py
[O-arena]: https://github.com/AMD-AGI/AgentKernelArena/blob/8bb70929ff8caed6dae932a396caef152c63fe64/docs/how-to/held-out-evaluation.md
[O-rsi]: https://github.com/apple-aiml-research/ml-rsi-inference-bench/blob/a6b10af282014412b4eae14f3105d68555889821/README.md
[O-rsi-scoring]: https://github.com/apple-aiml-research/ml-rsi-inference-bench/blob/a6b10af282014412b4eae14f3105d68555889821/tasks/optimize_dsv4_flash_4xh100_dspark_sglang_open/tests/_verifier_lib/scoring.py
[O-ooharness]: https://arxiv.org/html/2610.28380v1
[O-harnesspro]: https://arxiv.org/abs/2610.26770
[K-units]: https://github.com/mindie-agent/knowledge/blob/b900f11ef6be1edfe54e3d739b10588bc0cb0fce/tests/test_graded_units.py
[K-context]: https://github.com/mindie-agent/knowledge/blob/b900f11ef6be1edfe54e3d739b10588bc0cb0fce/tests/test_context_progressive_loading.py
[K-experience]: https://github.com/mindie-agent/knowledge/blob/b900f11ef6be1edfe54e3d739b10588bc0cb0fce/tests/test_experience_and_exploration_loop.py
[K-ablation]: https://github.com/mindie-agent/knowledge/blob/b900f11ef6be1edfe54e3d739b10588bc0cb0fce/tests/test_graded_ablation.py
[K-live]: https://github.com/mindie-agent/knowledge/blob/b900f11ef6be1edfe54e3d739b10588bc0cb0fce/tests/test_live_npu_knowledge_loop.py
[B-models]: https://github.com/mindie-agent/mindie-bench/blob/4a8b9a9e7b81d424062bc2079423ec1d2c9aff19/src/mindie_bench/models.py
[B-product-doc]: https://github.com/mindie-agent/mindie-bench/blob/4a8b9a9e7b81d424062bc2079423ec1d2c9aff19/docs/product-value-suite-v2.md
[B-inference-doc]: https://github.com/mindie-agent/mindie-bench/blob/4a8b9a9e7b81d424062bc2079423ec1d2c9aff19/docs/rsi-inference.md
[B-performance]: https://github.com/mindie-agent/mindie-bench/blob/4a8b9a9e7b81d424062bc2079423ec1d2c9aff19/src/mindie_bench/evaluation/performance.py
[B-performance-tests]: https://github.com/mindie-agent/mindie-bench/blob/4a8b9a9e7b81d424062bc2079423ec1d2c9aff19/tests/test_performance_gates.py
[B-graded-ablation]: https://github.com/mindie-agent/mindie-bench/blob/4a8b9a9e7b81d424062bc2079423ec1d2c9aff19/tests/test_graded_ablation_contract.py
[B-rsi]: https://github.com/mindie-agent/mindie-bench/blob/4a8b9a9e7b81d424062bc2079423ec1d2c9aff19/src/mindie_bench/runner/rsi_explorer.py
[B-rsi-tests]: https://github.com/mindie-agent/mindie-bench/blob/4a8b9a9e7b81d424062bc2079423ec1d2c9aff19/tests/test_rsi_explorer.py
[B-replay]: https://github.com/mindie-agent/mindie-bench/blob/4a8b9a9e7b81d424062bc2079423ec1d2c9aff19/src/mindie_bench/runner/knowledge_replay.py
[B-replay-tests]: https://github.com/mindie-agent/mindie-bench/blob/4a8b9a9e7b81d424062bc2079423ec1d2c9aff19/tests/test_knowledge_replay.py
[B-conditions]: https://github.com/mindie-agent/mindie-bench/blob/4a8b9a9e7b81d424062bc2079423ec1d2c9aff19/tests/test_knowledge_conditions.py
[B-broker]: https://github.com/mindie-agent/mindie-bench/blob/4a8b9a9e7b81d424062bc2079423ec1d2c9aff19/src/mindie_bench/runner/knowledge_broker.py
[B-broker-tests]: https://github.com/mindie-agent/mindie-bench/blob/4a8b9a9e7b81d424062bc2079423ec1d2c9aff19/tests/test_broker_knowledge_metrics.py
[B-p3]: https://github.com/mindie-agent/mindie-bench/blob/4a8b9a9e7b81d424062bc2079423ec1d2c9aff19/src/mindie_bench/runner/p3_lineage.py
[B-p3-tests]: https://github.com/mindie-agent/mindie-bench/blob/4a8b9a9e7b81d424062bc2079423ec1d2c9aff19/tests/test_p3_lineage.py
[B-coverage]: https://github.com/mindie-agent/mindie-bench/blob/4a8b9a9e7b81d424062bc2079423ec1d2c9aff19/src/mindie_bench/evaluation/coverage.py
[T-rmsnorm]: https://github.com/mindie-agent/mindie-bench/blob/4a8b9a9e7b81d424062bc2079423ec1d2c9aff19/tasks/performance/fused-rmsnorm-gate/task.toml
[T-idle]: https://github.com/mindie-agent/mindie-bench/blob/4a8b9a9e7b81d424062bc2079423ec1d2c9aff19/tasks/corpus-first-l3/k3-gdn-idle-dp-state/task.toml
[T-kda]: https://github.com/mindie-agent/mindie-bench/blob/4a8b9a9e7b81d424062bc2079423ec1d2c9aff19/tasks/corpus-first-l3/kda-chunk-varlen-padded-workspace/task.toml
[T-stale]: https://github.com/mindie-agent/mindie-bench/blob/4a8b9a9e7b81d424062bc2079423ec1d2c9aff19/tasks/stale/fused-mc2-deployment/task.toml

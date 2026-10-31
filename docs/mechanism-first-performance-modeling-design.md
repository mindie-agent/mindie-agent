# 机制优先（Mechanism-First）的性能建模设计规范

[仿真系统设计（`mindie-sim v0.8.1`）](simulation-system.md) · [双模型原始方案](a3-performance-modeling-plan.md) · [工程原则](design-principles.md) · [分级测试](testing-architecture.md)

本文档阐述 `mindie-sim` 机制优先（Mechanism-First）性能建模的核心数学推导与架构规范；对应的 `mindie-sim v0.8.1` 5 层因果建模引擎、4 维效率拆解与 30ms SLA 硬件反推求解器能力见[面向 Agent 的通用性能建模系统](simulation-system.md)。

**核心原则：把能由工作量、执行计划和资源约束推导的效率现象还原为物理与微架构机制；校准只识别有明确物理含义、可区分、可复用的底层参数。`predict` 和 `should` 共用同一套底层执行机制，区别仅在于执行计划的选择。**

仿真引擎由 [`sim`](https://github.com/mindie-agent/sim) 实现，原始测量解析与参数标定证据由 [`profiler`](https://github.com/mindie-agent/profiler) 提供，本仓库维护架构设计与跨组件契约文档。

## 1. 目标与完成标准

predict 回答：给定模型结构、硬件、当前软件实现、输入输出、请求到达和并发，实际 TTFT、TPOT、TPS、ITL、显存峰值与 SLA 表现预计是多少。

should 回答：在相同模型语义、硬件及业务约束下，允许哪些实现、布局、并行和调度变化；哪些合法计划可以改善目标；同一个候选计划对应的完整服务指标是什么。

两者共同使用：

\[
\text{结果} = F(\text{语义工作},\ \text{执行计划},\ \text{硬件参数},\ \text{工作负载与状态})
\]

- predict 为 F 选择当前实现的计划。
- should 在声明的合法计划族中调用同一个 F，在给定 SLA 和优化目标下选择候选，必要时返回 Pareto 集。不存在天然同时最小 TTFT、最小 TPOT、最大 TPS 的唯一方案。
- L 单列为放松约束后的乐观耗时下界；U 是有限计划族中的最佳已知、在模型约束内可行的目标。U 仍是预测，不能因存在模拟时间线就称为已在硬件上兑现。
- 固定为相同计划、相同参数、相同初始状态和请求轨迹时，两入口的显存账、工作量、事件和指标应一致。这是首个接线验收，不是再维护两个公式互相对答案。
- MLA、DSA、CSA、HCA、SWA、GDN/KDA、MoE、量化和投机变化，必须改变相应语义、布局、工作或事件。模型架构变化后的质量等价性不由性能模拟器自动证明。

完成不能只看基线误差。至少要同时满足：机制正确进入公共执行链；变化引起正确的中间量和瓶颈转换；独立条件上的预测达到既定精度要求；复杂度和资源消耗可控。

## 2. 当前实现的保留项与改造点

以下是审查入口，不是要求重新发明现有组件。接手时先确认最新 head 和在途 owner，再按函数定位。

| 入口 | 已有价值 | 本轮调整 |
| --- | --- | --- |
| `a3_catalog_*.py`、`a3_workload.py`、`a3_graph_execution.py` | 结构、shape、配方与实际工作生成 | 统一语义到具体实现计划的传播；替换模型名特判中的可泛化工作推导 |
| `a3_cost.py::_gemm_efficiency` | 用 tile 和 AIC 数推导 wave 与尾波不足 | 保留机制，核对 tile 来自实际配方；区分真实执行量与资源闲置 |
| `a3_resources.py`、`a3_resource_engine.py` | 依赖驱动的共享资源服务与完成事件 | 作为唯一主执行引擎；按需补有限并发、阶段占用，禁止旁路总耗时覆盖 |
| `pipeline.py`、`pipeline_graph.py` | 微阶段依赖、缓冲与稳态启动间隔 | 对接有限任务的启动、排空和尾块，不能只拿稳态 II 当完整 kernel 时间 |
| `a3_memory.py`、`a3_catalog_weights.py`、`a3_catalog_cache.py`、`a3_cache_ledger.py` | 逐 rank 几何、权重、KV/state 与驻留 | 续用 UnifiedMemoryPlan 负责人；实测总量不再覆盖候选几何 |
| `a3_physical_calibration.py` | 已有测量、参数、条件与误差资产 | 审查按 batch 的 eta、带宽覆盖、tail 系数等；逐项恢复原因，压缩自由参数 |
| `a3_retarget_derivation.py`、`a3_measured_retarget.py` | 显式区分测量与推导 | 实测总时长按比例分摊后再缩放，不能充当跨硬件因果模型；改为从新计划重算 |
| `a3_admission_ladder.py`、`a3_c4_admission.py`、`a3_scheduler_admission.py` | 暴露 admission 对 TTFT 的影响 | 检查阶梯来自调度规则还是测量表；由请求和 token/KV 预算产生 admission |
| `a3_should.py`、`a3_should_pd.py`、`a3_should_metrics.py` | 候选、可行性、PD 和指标已存在 | should 与 predict 共用底层服务参数、显存、执行和指标；保留计划选择差异 |

两个必须分清的事实：

1. 将实测总耗时按归一化权重分成 compute/memory/comm，再加回原值，残差为零是算术结果，不是机制正确的证据。
2. 通过可分辨实验识别启动延迟、事务服务速率或管线间隔，可以使用回归；这不等于为每个 batch、模型或端到端 cell 增加一个效率系数。

## 3. 一条公共执行链

~~~mermaid
flowchart TD
  I["模型语义 硬件 工作负载 状态"] --> P["predict 选择当前实现计划"]
  I --> S["should 枚举合法候选计划"]
  P --> X["共同的语义与实现 lowering"]
  S --> X
  X --> M["逐 rank 显存与驻留规划"]
  M --> W["算子和通信工作 微阶段依赖"]
  W --> E["既有 ResourceEngine 与请求循环"]
  E --> R["真实完成事件"]
  R --> O["TTFT TPOT TPS ITL SLA 显存峰值"]
  H["可解释的硬件与运行时底层参数"] --> M
  H --> W
  H --> E
  I --> L["放松约束的下界 L"]
  O --> U["should 约束筛选与目标排序"]
~~~

### 3.1 输入的四个边界

| 对象 | 应包含 | 不应混入 |
| --- | --- | --- |
| 语义工作 | 层、算子数学语义、shape、dtype、稀疏/压缩规则、必要数据依赖 | 基线 TTFT、模型名对应的效率折扣 |
| 执行计划 | 实际 kernel/算法、tile、布局、融合、分片、通信算法、graph、调度策略 | 另一配置的实测权重总量、预先拟好的最终服务指标 |
| 底层参数 | 按路径和状态定义的容量、速率、延迟、发射限制、缓冲槽位、运行时原语成本 | 每个整模 cell 一个自由系数 |
| 动态状态 | 活跃请求、队列、缓存/前缀驻留、rank 放置、资源占用、频率状态 | 无限增长的完整历史 |

沿用现有对象与字段。确有缺口时只增加执行所需的字段，不新建一套重复的 CaseSpec、状态机或通用 provider 框架。实现配方按结构和实际 dispatch 匹配；软件版本和来源用于解释配方，不变成固定版本白名单。

### 3.2 公共求值的语义

以下为控制流要求，函数名是示意，不要求增加这些公开 API：

~~~python
def evaluate_plan(case, plan, parameters):
    runtime = instantiate_runtime(case, plan)
    work = lower_actual_work(case.model, runtime, case.workload)
    memory = plan_memory(work, runtime, case.environment)
    return run_existing_request_and_resource_loop(work, memory, parameters)

predict_result = evaluate_plan(case, current_plan(case), parameters)
candidate_results = (
    evaluate_plan(case, plan, parameters)
    for plan in enumerate_legal_plans(case, constraints)
)
should_result = select_under_sla(candidate_results, objective)
~~~

实际系统中 lowering、分配和执行会随请求完成、KV 增长及下一轮调度交替发生，不能把所有动态工作一次性预生成。先让固定单轮和同计划两入口复用，再扩展到完整请求循环。

### 3.3 工作、占用与等待不能混为一项

每个机制应能说明：执行了多少逻辑工作、硬件实际执行或传输了多少、占用了哪些资源、等什么事件。

- padding 可能增加真实执行量；尾波核心闲置是占用或调度现象，不能一律伪造成新增 FLOPs。
- 等待上一阶段、启动延迟和 barrier 不是 HBM 字节，不得为了凑时间折成虚构流量。
- 整 kernel 的观测时长不包含完整资源占用信息，不能据此假定整段时间同时占满所有资源。
- 总时长来自阶段依赖和共享资源服务。串行依赖不能任意取 max，可重叠工作也不能全部相加。
- critical path 变化可能使某项减少却不改善端到端时间，模型必须保留这种结果。

## 4. 需要直接建立的机制

### 4.1 小搬运量与带宽饱和

单一路径、固定配置、连续搬运的最简近似：

\[
T(S) \approx t_{\mathrm{setup}} + \frac{S_{\mathrm{wire}}}{B_{\mathrm{sustained}}}
\]

\[
B_{\mathrm{observed}} = \frac{S_{\mathrm{useful}}}{T(S)}
\]

S_useful 是用户有效数据，S_wire 是计入事务粒度、对齐、重读与协议开销后实际占用该路径的字节。二者必须分开。HBM copy 的读和写是否共享资源，也要按实际路径计入。

有限在途请求提供另一个约束：

\[
B_{\mathrm{sustained}}
\lesssim \min\left(B_{\mathrm{path}}, \frac{N_{\mathrm{outstanding}}q}{L_{\mathrm{response}}}\right)
\]

这只是稳态供给约束，不是任意访问模式的完整闭式解。实现应按 burst/transaction、发射间隔、可用槽位和完成事件表达；先使用既有事件与资源对象，确需扩展时由引擎 owner 加最小能力。

必须覆盖：

- 小传输由启动和响应延迟主导，大传输渐近服务带宽；
- 大总量但独立请求不足，仍无法饱和；
- 多流可提高供给，也会共享同一物理路径；
- 地址对齐、stride、分块与合并改变实际事务数；
- 缓存命中改变经过的层级，不能只改变一个“内存效率”。

不能把每个 shape 的观测带宽直接存成表，然后称为带宽机制。不能给每次事务重复加一次整 kernel 启动，也不能将同一延迟同时计入 alpha 和流水线首阶段。

### 4.2 GEMM、Vector 与有限流水

从实际配方推导 tile 数、每 tile 工作、核心映射、缓冲需求和依赖。均匀任务可用 wave 近似；非均匀专家分组、尾块和稀疏工作需要相应的任务分布。

同质重复微阶段可表达为：

\[
T(n) = T_{\mathrm{first\ completion}} + (n-1)\,II
\]

仅在稳定阶段拓扑、服务条件和末次完成定义一致时使用此式。启动、排空、有限缓冲回压和尾块由阶段图决定；不另乘人为的“短 K 效率”。

- AIC/AIV 数、tile 与 kernel dispatch 共同决定供给和占用。
- Cube、Vector、MTE、HBM 只能按真实依赖和资源关系重叠。
- MoE 从实际激活专家、路由 token 分布、grouped GEMM 配方推导；总专家数、活跃专家数和实际加载/读取权重范围分别建模。
- logits、sampling、排序、归约按真实服务配置和词表/候选范围生成；BOM 中没有执行的工作应删除，而非拟合成零。
- 算法或 tiling 切换产生的拐点，应由 dispatch 规则解释。不能以一条平滑曲线抹掉。

### 4.3 缓存与实际流量

最低需要表达：唯一物理数据量、重复访问、共享/独占 owner、重用间隔、可用缓存容量和并发竞争。

- 不能把逻辑 KV 读取量全部视为 HBM 流量，也不能因总工作集小于标称 L2 就默认永久全命中。
- Prefix cache 是服务语义，片上 L2 是硬件缓存；两者分别改变工作和物理流量。
- 先对已有 trace 可识别的流式、重复驻留和混合工作集实现最小模型。未知替换策略可用声明假设与上下界，随后用判别实验缩小范围。
- 不必为每个 byte 或 token 创建对象。对同质访问分组、采用有界重用摘要；只有影响关键决策的边界才展开。

### 4.4 显存和临时分配

在已知实现与分配规则下，权重、量化元数据、KV/state、graph 与通信缓冲应从代码和配置推导。workspace 单独建立生命周期模型，不能反向覆盖其他精确项。

\[
M_{\mathrm{peak},r}
= \max_t\ \mathrm{bytes}\left(\bigcup \text{rank }r\text{ 在 }t\text{ 时存活的物理分配}\right)
\]

这里取物理分配的并集：视图、共享池和 owner 引用不重复收费。预留池与其内部已用空间也不能重复相加。

- 区分加载、warmup、graph capture、prefill、decode、PD handoff 阶段的峰值。
- current free HBM、物理容量、runtime util 预算和 max_model_len 分开；明确环境快照在进程启动前还是之后。
- 逐 rank、逐 stage 重算；不能始终取 machine.dies[0] 代表所有设备。
- 改 EP/TP/PP、层数、dtype、cache group、graph mode 后重新生成分配计划。
- 实测总量只用于同条件对账和寻找遗漏分配；不作为覆盖解析权重/KV的输入。
- baseline graph pool、KV token capacity 与权重实测值不向新候选直接迁移。
- allocator 的 rounding、block、pool growth 和 reuse 是可建模机制；实现信息缺失时列明具体未知分配，而不是用固定 HBM 百分比掩盖全部 workspace。

继续复验已有 EP2/EP4/EP8/eager 反例。不要新写第三个显存计算器。

### 4.5 通信、PD 与重叠

从实际 rank 组、collective 算法、分块和物理路由生成通信工作。参数只描述对应传输原语。

- ring、tree、分层 collective 的轮数、每轮字节、依赖和共享链路需要显式表达。
- alpha/beta 可用于匹配协议和范围内的服务模型；不能将某一 EP 数的整组曲线无条件当成任意拓扑的线速。
- MC2、compute/comm overlap 由 chunk 依赖、资源占用和消费者就绪决定，逐步替换无来源的 overlap fraction。
- PD 接收端在数据进入或占用缓冲前预留容量；已收到但排队的 KV 仍计入驻留。
- 同一物理 link 的并发流共享容量，不能让每个 replica 都独占一份峰值。
- 改所有请求的绝对到达时间，不应改变相对耗时；没有消费者分块语义时，不能凭空获得首 chunk 重叠收益。

### 4.6 调度、排队和投机

由到达轨迹、token budget、max_num_seqs、KV可用量、chunk规则、graph bucket、prefix命中和实际服务完成事件推进调度。

- c1/c2/c8 仅是负载条件，不能各自拥有一条最终 TTFT 公式。
- admission 阶梯应由实际批处理和资源准入形成。现有测量表可验证阶梯，不能替代 scheduler。
- speculative decode 明确 draft、verify、accept/reject、提交与回滚事件。接受序列来自声明轨迹或统计输入；只给平均接受率时，不能据此声称已精确还原每 token 的 ITL。
- 只有已提交的 token 计入输出。不能用 verify 总时长除接受 token 数掩盖首 token 等待。
- 同一完成事件流生成 TTFT、TPOT、ITL、E2E、TPS 和 goodput；TPS 的统计窗口明确，不能用 1/平均 TPOT 冒充全局吞吐。
- SLA 沿用任务规定的逐请求、逐 token 或明确分位数语义，不自行改成均值。
- arrival、MoE 路由、投机接受、外部干扰等动态量可以作为可复现轨迹或分布输入，不要求先建立一个不现实的全知确定性模型。

### 4.7 频率和运行状态

计算管线以 cycles/operation 或等价速率描述时，应使用对应时钟域。HBM、片上互联、核心频率不可无条件一起缩放。

频率/热状态变化可能很小，也可能显著。按已有记录判断影响，不预设它只能解释小方差，也不把它当成任何大偏差的通用理由。电压若没有可用传感和确定关系，不另加自由 voltage factor；通过已有可观测运行状态建模。

先复用已记录的 clock、功耗/温度、工作负载与持续时长。没有证据表明频率是主要误差来源时，优先处理工作量、算法、缓存、调度、单位和计时口径。

## 5. 校准的允许范围与拟合清理

### 5.1 参数分类

| 分类 | 例子 | 处理 |
| --- | --- | --- |
| 可直接推导的数量 | tensor bytes、padding、block 数、通信轮数、已知 tile 数、静态分配 | 由代码/布局/计划计算，不拟合 |
| 硬件服务参数 | 指定路径的响应延迟、持续服务速率、发射间隔、槽位数、对应时钟域 | 使用规格或可分辨微实验识别，绑定真实范围 |
| 运行时原语参数 | 某提交路径的启动成本、graph replay、确定协议的建立开销 | 与硬件参数分层；predict 和 should 仅在选用该原语时共同使用 |
| 动态输入 | 到达轨迹、路由分布、接受序列、外部占用、初始缓存/频率状态 | 作为条件输入或分布，禁止偷换成最终延迟系数 |
| 机制的派生结果 | 实际带宽、占用率、重叠率、admission 等待、最终 TTFT | 从执行求出，不按 cell 任意赋值 |
| 解释不清的经验项 | batch eta、模型专用 end-to-end multiplier、profile share 拆出的资源时间 | 由 G 列出消费者；对应 owner 建机制，接通后删旧拟合分支 |
| 原始观测 | kernel 时长、服务请求结果、显存分项、trace | 保留用于参数识别、对账、固定条件回放和独立验证 |

“带宽”“延迟”等名字本身不构成物理含义。若参数是从整模耗时反算，混入计算、调度或缓存，它仍是聚合经验项。

### 5.2 参数只保留足以使用的信息

复用现有校准记录，必要字段为：参数含义、单位、硬件/运行时原语、路径与计时范围、实际决定适用性的条件、识别方法及数据来源。不要增设跨仓摘要比对、签名链、重复 receipt 或新数据库。

- 不同 kernel 可有不同 tile/发射/缓冲参数；这种差异必须对应实现事实，而非模型名任意分组。
- 不能用同一个总时长同时识别启动、带宽、计算和缓存四个自由参数。
- 用短/长 payload、单/多在途、冷/热缓存、对齐/非对齐等最少对照区分假设；优先查询已有数据。
- 能观测到 launch 与 device service 时分开识别，避免把同步或 host 等待算进设备带宽。
- 未识别参数保留范围或具体缺口。语义与必要参数足够时仍运行解析模型；缺少实测点不构成一律拒绝合法新 shape 的理由。
- 发生大残差时先查输入、计时、遗漏和错误机制。允许结论暂时是“原因未确定”；禁止为了填满归因表编造确定原因。
- 不强求每个资源分项可相加等于墙钟时间。并发系统的服务时间、占用时间和暴露关键路径是不同口径。

### 5.3 迁移顺序

G 先按“生产调用点、影响范围、是否能机制推导、替代 owner”建立一份精简清单，优先审查：

1. 最终 TTFT/TPOT/step 倍率与按模型/batch 的总成本覆盖；
2. 实测权重/KV总量覆盖与硬件 retarget 的总时间分摊；
3. admission 表和固定 overlap fraction；
4. shape/batch eta、缓存阈值及 tail 系数；
5. 只在来源不明时才需要重做的底层 alpha、beta、launch、rate。

每一项按“已有反例 → 机制实现 → 公共入口接通 → 定向验证 → 删除被替代路径”完成。原始数据保留，生产长期双轨和静默回退不保留。不要同时删除所有经验路径造成整个系统暂时不可用，也不要给旧系数换名字后宣布完成。

## 6. should 的同机制约束

should 可以选择不同的 tile、融合、并行度、cache布局、通信算法、分块或调度方式，但每个变化都必须重新生成工作、资源需求与分配。

- 同一硬件/原语的服务参数在 predict 与 should 中相同；不能一边用校准速率、一边无条件按标称峰值。
- should 不机械继承当前实现中可消除的冗余拷贝和等待。要消除它们，候选计划必须明确提出相应实现变化，并满足数据、容量与依赖约束。
- should 不把当前某个差实现的整体效率当硬件定律。候选采用另一 kernel/原语时，使用对应机制和参数。
- 使用未经实测的新实现候选时，明确其机制假设和预测范围；模拟可行与实际实现可运行分别报告。
- L 可使用放松的资源下界，但必须说明忽略了哪些约束；L 与实际差距大本身不等于预测模型失效。
- 不允许从不同候选分别摘取最好的 TTFT、TPOT 和 TPS 拼成一个结果。
- 计划评估中的环境、host预算、逐rank空闲HBM、KV驻留、SLA和统计窗口与 predict 共用。
- 硬件 retarget 先替换硬件参数，再重新选择或固定实现计划并执行。报告区分“固定计划下硬件变化”与“变化后重新优化计划”。

## 7. 最小契约与共享文件归属

由 DSH 主协调者和 F 先确定现有对象需要的最小增量，不等待一轮大重构。A–E 同时开展自己模块的源码核对、机制实现和局部反例。

| 契约 | 必须携带的业务含义 | 首要 owner |
| --- | --- | --- |
| Lowering 输入输出 | 语义 shape、实际 kernel/recipe、执行工作、tensor身份、依赖、rank/资源映射 | A |
| 传输/阶段工作 | useful/wire bytes、路径、分块、就绪事件、供给/并发限制 | B；通信扩展由 E |
| 计算阶段 | tile/wave/管线阶段、实际工作、缓冲、资源占用及完成依赖 | C |
| 物理分配 | rank、owner、bytes、分配/释放阶段、共享池、预算口径 | D |
| 公共执行 | work/memory进入既有事件循环、资源服务、完成反馈 | F |
| 底层参数 | 参数含义、单位、范围、输入条件、证据与未识别部分 | G |
| 验证输入输出 | 原始条件、参数来源、请求/事件/分项、既定指标 | H |

**共享文件单写者**：

- F 负责 `a3_framework.py`、`a3_should.py`、`a3_resource_engine.py`、`a3_resources.py`、公共 metrics 与公共求值接线。
- G 负责 `a3_cost.py`、`a3_physical_calibration.py` 入口与参数/provider选择、retarget旧路径清理；B/C/E 将其负责机制做成内聚函数或叶子模块，由 G 一次接入。
- A 负责 catalog语义、operator/work lowering；其中 weights/cache/ownership 的容量实现归 D，字段变更先与 D 对齐。
- D 负责 `a3_memory.py`、`serving_planner.py` 的统一预算、cache ledger 与生命周期。
- E 负责 `a3_communication.py`、`a3_should_pd.py` 中通信和PD工作构造；公共入口变更交 F。
- H 不修改成本系数或生产预测结果，只修独立评分实现中的实际错误并说明口径。

这份归属是初始建议，DSH 可根据正在进行的分支调整一次并记录。核心要求是同一段共享代码只有一个写入 owner；不让 8 个 agent 同时改巨型文件，再用大量 merge conflict 消耗时间。

现有巨型模块只按本轮实际机制边界抽取，目标保持新增核心模块小于 800 行。禁止为满足行数机械切成透传包装，禁止另建第二个事件引擎。

## 8. 八个 subagent 的任务包

DSH 主协调者负责分派、接口取舍、合入与资源协调，下面是最多 8 个执行槽位。各槽位完成当前任务后续用，不另扩同类 agent。候选旧 owner 是按已见任务名给出的映射，实际忙闲由 DSH 回读确认。

| 槽位 | 任务组 | 优先复用的现有 owner | 第一份可合入结果 |
| --- | --- | --- | --- |
| A | 语义、shape与实现工作 | Catalog/Generic graph；Sampling BOM负责人可接子任务 | 一条真实模型路径的完整工作推导，清除一类不存在或错误计数的工作 |
| B | 搬运、事务与缓存流量 | Hardware retarget/底层成本负责人 | 小/大传输和有限在途供给的机制；正确进入共享资源成本 |
| C | 计算、tiling与流水 | 算子/attention/MoE建模负责人 | wave、有限流水或active-expert的一条机制替代，含匹配配方 |
| D | 显存、workspace与生命周期 | UnifiedMemoryPlan负责人 | 关闭总量覆盖反例，并由同一分配账约束两入口和PD |
| E | 通信、拓扑与PD | PD/op-impl/通信负责人 | 通信字节、轮次、共享link与chunk依赖驱动时间 |
| F | 公共执行、调度与两入口 | Generic graph execution/should负责人 | 同计划predict/should执行一致；admission来自请求循环 |
| G | 参数审查、校准和旧拟合清理 | 成本/retarget负责人；Clock负责人归此组 | 逐项参数去留、识别依据与首批旧拟合删除 |
| H | 独立验证与误差定位 | Independent model validation/Missing-component audit | 最小因果反例、已有数据验证与最大未解释误差的判别问题 |

### A 语义与工作

审查 catalog、attention 语义、MoE 路由、量化、sampling 的实际执行。论文家族和 backend 名称分开，继续沿用已纠正的 SWA/CSA/HCA 与 DSA/SFA 映射。

先处理 Sampling BOM 和 active-expert 相关工作计数；随后覆盖层数、head/维度、量化、投机和算法替换。交付实际产生的 shape、算子次数、逻辑/物理工作差异与上下游消费者。验收依据是源码/真实trace和工作守恒，不是模型名分支数量。

### B 搬运与缓存流量

实现第 4.1、4.3 节最小可用部分。先用已有搬运数据区分固定延迟、持续带宽、供给不足；对缓存/stride尚缺条件的部分明确假设，避免一次实现完整缓存模拟器。

与 D 共享 owner/物理数据身份；与 F 对齐资源供给限制的表达。交付大小/并发/缓存状态变化时的实际字节、服务路径、供给上限和时间，不只给一条拟合曲线。

### C 计算与流水

从已知 kernel 配方选一个 GEMM/Vector/attention 或 MoE 代表路径，推导 tile、wave、阶段和缓冲。优先修已有大误差中被证实的工作/映射问题。

将已有 pipeline 求解能力接入有限工作；先不做所有算子指令级仿真。交付机制替代前后的中间量和局部验证，指出哪些误差仍属于未建模的配方细节。

### D 显存与workspace

先完成正在进行的 UnifiedMemoryPlan P1；用既有 EP2/EP4/EP8/eager 复现判定，然后推广到逐rank异构空闲预算、KV/压缩状态、graph、HCCL与workspace生命周期。

观测只对账。不要先为每个模型估一个新 workspace 百分比。缺实际 allocator 信息时，先列具体暂存张量、边界和重用条件，缩小未知部分。

### E 通信与PD

复用已修复的 PD 驻留与wire反例，防止公共执行改造回退。从一个已有 topology/collective 路径开始，按轮次、字节和chunk事件替代整组曲线或固定overlap。

交付一个真实可共享link场景和一个消费者依赖场景；H可直接复用，不重复测量。

### F 公共执行与调度

这是接线与合入的关键路径。先让同计划两入口复用同一求值与指标，再把 B/C/E 的工作放入既有 ResourceEngine；D 的分配与准入结果必须真实约束执行。

用已有 token budget、admission、到达时间平移、逐token SLA 与投机提交反例检查。不能在事件引擎运行后用 measured matrix 或模型倍率覆盖最终结果。与 A/G 合作删掉不再使用的旁路。

### G 参数审查与迁移

从生产消费者回溯拟合项，按第 5 节处理；不要只 grep 字段名输出一份名单。每项说明它实际上修补了什么，以及对应机制 owner。

复用 Clock/frequency 任务，但不优先增加新的温度/电压自由参数。每个新参数必须能说清如何识别以及为何已有参数不能解释。接通一个机制后立即删除对应旧分支，不等待所有家族完成才清理。

### H 独立验证与判别实验

先复用已有 review repro、真实 config、profile与服务结果。对系统性残差提出可区分的假设，检查能否用现有证据作答；只有无法区分且影响主要结论时才提出补测。

与实现 owner 区分参数识别数据和验证数据。已经反复用于调参的 cell 是开发数据；不能继续称为盲测。不得改 gate 阈值、注入生产假数据或仅写枚举/文案检查来获得PASS。

## 9. 分批推进与合入顺序

### 第一批 并行审查并闭合第一条主链

8 个槽位立即各自开展就绪工作。F/A先确认最小共享契约，D续修已知P1，B/C/E写各自机制，G清理实际调用点，H建立可复用的区分性验证。

第一条纵向链选现有配置、请求结果和profile最完整的一组服务条件。优先复用已有Qwen系列或K3数据；由H确认实现、量化、MTP、cache和统计口径是否相同，不能把不同条件拼成基线。V4已有显存日志可独立用于D对账，无需等待整条性能链完成。

本批可交付：

- 同计划两入口走共同执行链；
- 一类效率拟合被机制替代并从生产调用链删除；
- 现有显存覆盖反例关闭；
- 同一参数集至少跨一个大小或并发变化正确执行，并由已有独立条件评估。

### 第二批 扩展相互作用

按准备好的依赖逐项合入，不等8个分支一起“大爆炸合并”：

1. 最小契约及F的共同入口；
2. A的真实工作和D的统一预算；
3. B/C/E的服务与依赖机制，经G接入成本入口；
4. F的队列、动态准入、投机与指标；
5. G删除被替代拟合，H复用本职验证完成受影响组合验证。

这个顺序是依赖关系，不是要求agent串行等待。叶子机制、真实数据解析和局部验证可并行完成；只有依赖未就绪的集成步骤等待。若G/F成为瓶颈，优先让其接通已经验证的最小机制，暂停无关格式重构。

第二批重点是交互：缓存挤出、compute与memory瓶颈转换、通信竞争、KV容量限制调度、graph切换、投机与服务指标。每次只新增能解释已定位差额的机制。

### 第三批 留出验证与扩面

H用未参与参数识别的条件评估，A–G按所属机制修残差。所有新修正仍走相同主链。

先扩同硬件不同shape/并发，再扩已知配方不同布局/结构，最后扩跨硬件与重新优化计划。顺序可按现有数据覆盖调整，不要求为每一层额外新建gate。

一个机制范围完成后，删除该范围的旧拟合代码，记录剩余范围。主线完成一次相应集成回归；全套测试在整合交付或既定PR门禁执行，不在每个小分支重复。

## 10. 有区分力的验收矩阵

以下是行为验收，不要求机械地一行写一个测试。复用已有测试和反例；只补会捕获真实缺陷的缺口。

| 变化或反例 | 应检查的机制 | 判定重点 |
| --- | --- | --- |
| 小/大传输 | 启动、事务与持续服务 | 固定参数能解释饱和曲线；不是逐点重拟带宽 |
| 相同总量、不同在途数 | 供给与响应延迟 | 供给不足时受限；足够供给后受路径容量限制 |
| 对齐/stride、冷/热访问 | 事务数与各级流量 | useful bytes不变时wire/path可变，不伪增全层流量 |
| GEMM尾波与tile边界 | 核心映射、实际tile、有限流水 | 拐点来自实现；未必随shape连续或严格单调 |
| HBM带宽或计算能力变化 | 执行中的资源服务 | 瓶颈可转换；非瓶颈参数变化不强求端到端变化 |
| 层数/attention/量化变化 | 语义、工作与缓存几何 | 中间量重算；不按整网总时长倍率迁移 |
| EP2/EP4/EP8、eager/graph | 权重放置和物理分配 | baseline实测总量不覆盖新计划；无图时不继承旧图池 |
| token budget、到达、并发 | scheduler、KV准入与队列 | 请求事件改变；不由cN查表直接给TTFT |
| PD接收后排队 | KV驻留和消费依赖 | 队列中的KV占容量；接收与释放账目一致 |
| 多流共享link与chunk | 总字节、真实路由、依赖 | 总服务不超过容量；没有不存在的重叠收益 |
| spec depth/accept变化 | draft/verify/commit | 不提前产token；逐token等待不被摊销隐藏 |
| 同计划predict/should | 公共执行和参数 | 事件、显存、指标一致；差异不能由独立公式造成 |
| 固定计划/重新优化硬件情景 | 计划变化与硬件变化分离 | 两种问题分别计算，均不继承旧总时间分摊 |

还需检查动态工作集：长输出、重复请求和多候选搜索不能使RAM随历史无界增长。事件折叠不能跨越调度、缓存、容量、频率或瓶颈变化边界。

精度沿用各已有正式任务预先声明的统计口径和阈值。没有阈值的领域由DSH在评分前给出具体目标；不得看到结果后放宽。报告保留逐cell分布、尾部/SLA失败与覆盖范围，不能只给总体平均误差或通过项数量。

预测来源与验证状态分别记录。机制模型即使来源标记为analytic，也可以通过独立实测验证并报告该范围内的预测精度；不能要求每个算子都来自measured row才允许验收。反过来，使用了实测参数或行也不自动获得整网精度资格。H需检查现有gate是否把这两个维度混在一起，修正判定口径而不放宽误差阈值。

## 11. 高效校准与资源安排

- 先使用已有profile、日志、safetensors头部、config和真实服务结果；不为查模型元数据加载权重或初始化设备。
- 一个新增测量只回答一个明确的判别问题，例如区分启动延迟与供给不足；优先无权重算子/子图，最后才是整模。
- 参数识别和局部机制验证由owner完成一次，下游复用。同一artifact不复制成多套“验收快照”。
- 复用适合的现有工作树和在途分支，不为每次半小时检查重新克隆、冻结或复制整仓。
- Tier 0纯内存用例按仓库小于5秒的目标设计；Tier 1过程边界小于15秒。涉及真实设备/远端能力按既有Tier 2/3要求执行；大型模型采集单独预算，不能冒充短canary。
- 8个subagent不等于8个重负载worker或8组NPU作业。CPU/RAM按真实可用规格限制；常规单进程峰值不超过512MiB，超过1GiB按算法问题处理。
- 原始大trace流式读取，统计有界聚合，完整明细按需流式输出。资源/时间状态以active set为界。
- 外层超时覆盖全部内层预算和清理宽限；真机操作沿现有租约与显存预检，不抢占别人的容器、端口或设备。
- 上卡排期由DSH统一协调。CPU建模、已有数据分析和独立验证继续并行，不为等待NPU而全部停住。

## 12. 每半小时验收与收敛

Codex沿现有30分钟检查继续增量验收。DSH维护一份现有进度记录即可；若没有合适入口，可使用 `.workstreams/composability/mechanism-convergence.md`，无需每个agent再创建一套审计目录。

每轮只需让以下信息可读：

| 内容 | 最小信息 |
| --- | --- |
| 分工 | A–H实际owner、就绪/运行/待依赖/已合入状态 |
| 本轮变化 | 已合入机制、对应生产入口、被删除的拟合消费者 |
| 最小验证 | 一个有区分力的复现或已有测试及关键中间量 |
| 独立精度 | 未参与参数识别的条件、误差/SLA与覆盖范围 |
| 最大缺口 | 当前最重要的未解释残差、候选原因、下一步判别 |
| 资源 | 在途真机任务及原owner；是否确有新增测量必要 |

Codex检查实际diff、公共调用路径和必要的局部复现；不把8个agent繁忙、测试数量、旧gate PASS或文档提交当作机制完成。未完成但方向正确的任务不重复催办；仅在重大进展、明确失败/偏离、需要用户处理或全部完成时通知。

方向偏离包括：新增模型专用倍率、把eta重命名为物理参数、按实测总量倒分资源时间、两个入口分用不同成本、为缺测条件普遍refuse、为了“所有gap都解释了”编造原因，以及在owner验证完成后无理由重复采集。

全部目标完成需要：共用机制已接通；本次审查覆盖的生产调用链中，可机制推导的拟合已逐项替换，剩余参数符合第5节要求；既定精度与SLA验证完成；硬件/结构变化范围和未支持部分明确；没有未解决的主要正确性问题。第一批只替换一项属于增量进展，未完成项不能因“本轮未选”被排除出总体验收。局部PASS不足以停用检查。

## 13. DSH接到任务后的第一步

1. 读本文后，把现有任务映射到A–H，并回复实际owner与共享文件归属。尽可能填满8个有独立就绪工作的槽位；已运行的真机任务保留原owner和资源边界。
2. 立即安排A–G审查并修改各自实现，H同步准备现有证据和反例。不要只交付另一份设计或“已经并行”的状态。
3. 指定第一条共同执行路径、第一批要删除的经验消费者，以及同计划predict/should检查如何运行。
4. 优先关闭已知MemoryPlan问题，把新完成的c8、sampling与active-expert工作作为机制检查的输入；不要默认把新测量继续填进拟合表。
5. 只在具体依赖卡住时调整任务；一个owner空闲后接其范围内下一项，无需重建整组agent。

## 14. 可借鉴的已有方法

- [Berkeley Roofline](https://amcr.lbl.gov/departments/computer-science-department/ppan/roofline-performance-model/) 用工作量、数据搬运和资源能力描述边界；[ERT](https://amcr.lbl.gov/departments/computer-science-department/ppan/roofline-performance-model/empirical-roofline-tool-ert/) 识别机器的存储层级带宽与计算能力。这里借鉴“机制与底层参数分离”，不把粗Roofline当完整服务预测。
- [Timeloop](https://timeloop.csail.mit.edu/) 将工作负载、硬件架构与mapping分开，搜索受容量和映射约束的执行方式。这里借鉴should的合法计划搜索，不直接套用其设备参数。
- [ASTRA-sim workload layer](https://astra-sim.github.io/astra-sim-docs/workload-layer/overview.html) 按依赖图执行计算/通信工作。这里借鉴依赖与资源完成反馈，继续使用本项目已有引擎。
- [Vidur](https://arxiv.org/abs/2405.05465) 将请求、调度与执行成本组合成服务系统模拟。这里借鉴服务事件层次，其实测拟合路线不自动成为本项目跨硬件、跨结构机制建模的依据。

这些方法提供结构参考；Ascend的路径、kernel、缓存、时钟域和实际服务配置仍以对应代码、规格和测量确定。

## 15. 数学建模增补：瓶颈切换、有限流水与合法计划优化

2026-10-25 用户要求从数学上整体审查 Vector-bound、MTE2-bound 等随输入和并行策略变化的现象，并设专门研究子代理核查可复用结果。本节补充可执行的数学约束，不替代前文的实测门槛。源码核查基线为 sim `351afb3`；后续实现仍由原 DSH owner 负责。

### 15.1 用同一参数化执行图表达不同瓶颈

令输入和请求轨迹为 x，合法实现与并行计划为 π，硬件/运行时原语参数为 θ，初始状态为 s。由实际 lowering 生成资源约束执行图：

\[
G(x,\pi,s),\qquad w_{i,r}(x,\pi,s),\qquad C_r(\theta),\qquad M_b(x,\pi).
\]

w 是节点 i 在物理资源 r 上的工作，C 是该资源的服务能力，M 是实际缓冲/驻留需求。依赖边还包含数据就绪、同流水 FIFO、缓冲最后读者与复用、通信完成和运行时事件。不同计划改变图、工作、映射及缓冲，不通过一个并行效率系数改变最终时间。

资源守恒给出固定计划的必要耗时下界：

\[
L_{\mathrm{resource}}(\pi)=\max_r\frac{\sum_i w_{i,r}}{C_r}.
\]

再结合有合法阶段服务下界的关键路径、必要启动和通信轮次形成更强的下界。相同数据经过 HBM、L2、MTE2 等路径时，各路径分别记录服务；同一物理链路只能共享一份容量。一个搬运任务的不同资源需求不是彼此无因果联系的多份数据。

这个下界不能直接当 kernel 墙钟时间。Roofline 适合确定资源边界；ECM 强调不同数据路径与计算的实际重叠条件。将这些思想用于 Ascend 时，仍需实际指令/阶段依赖与缓冲图，而不是套用 CPU 的重叠假设。[Roofline 原论文](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2008/EECS-2008-134.pdf)、[ECM 原论文](https://arxiv.org/abs/1509.03118)。

### 15.2 Vector 与 MTE2 的转换面

在固定 recipe、布局、活跃核映射和缓存路径的一个区域内，先比较同一层次的服务需求：

\[
t_V=\frac{W_V}{P_V},\qquad
t_{M2}=\frac{D_{M2}}{B_{M2}},\qquad
I_V=\frac{W_V}{D_{M2}}.
\]

当其他依赖/资源不主导时，二者等时的边界为：

\[
I_V=\frac{P_V}{B_{M2}}.
\]

W_V 必须按实际 dtype、指令类型、向量宽度、repeat 和归约/依赖链生成。exp、cast、reduce、普通加法不能默认都占用相同的一个“vector op”。P_V 是对应原语和活跃核的能力，不是从整模 TPOT 反算的效率。D_M2 由实际访问和事务推导，不能把所有逻辑访问都记为 HBM，也不能把 MTE2 利用率直接等同于 HBM 带宽饱和。

有效搬运还受路径带宽、发射间隔和在途事务供给共同限制。对均匀事务可用 `min(路径带宽, 在途数×事务字节/响应延迟)` 检查稳态上界；有限事务和阶段重叠由事件执行。这些约束中的最大者可能是 Vector、MTE2、HBM、有限供给或缓冲回压，报告应允许多个共同瓶颈。

一个可直接检验的约束来自 GQA：在固定 batch B、query 数 Q、头布局、复用次数和缓存路径时，softmax 工作约为 `c×B×Q×Hq×S`，KV 搬运约为 `r×B×Hkv×S×(dk+dv)×dtype_bytes`。两项都随 context S 同倍率增长，二者的比值不随 S 改变。不能只因为 S 变长就人为换一个 bound 或效率曲线。真实转换须由不同比例的工作项、tile/wave 取整、片上容量、缓存路径、dispatch、事务供给或执行图改变解释。

TP 改变的是逐 rank 布局：当 Hq 和 Hkv 同比例切分时，局部比值可能保持；当 KV 头不能继续切分而实际实现开始复制时，query 工作和 KV 搬运不再同倍率减少，转换面会移动。是否复制、怎样分组，以当前实现为准。DP/EP 也必须经过每 rank batch、每 expert token 分布及路由/通信重算，不能套相同缩放规律。

### 15.3 最大环比给稳态约束，有限工作按真实边执行

对阶段服务固定、重复模式固定且 FIFO/缓冲约束已表达的 timed event graph，边 `u→v` 的迭代距离 d 表示：

\[
s_v(k)\ge s_u(k-d)+t_u.
\]

任意正距离环 C 都要求：

\[
II\ge\frac{\sum_{u\in C}t_u}{\sum_{e\in C}d_e},\qquad
II^*=\max_C\frac{\sum_{u\in C}t_u}{\sum_{e\in C}d_e}.
\]

这是可直接复用的最大环比结果；周期定义为 super-period 时，需要按每周期 tile 数换算。零距离正服务环不可行。来源是 max-plus/离散事件系统理论，适用域是已声明的图和服务条件；动态 batching、共享资源竞争使服务时长随状态变化时，应由现有事件引擎推进，不能强行套静态周期。[Synchronization and Linearity](https://repository.tudelft.nl/record/uuid%3A1add64d4-0dfc-4b5d-9db0-2d4be33dfeb3)。

两阶段 `CopyIn→Vector`、各自一条 FIFO、缓冲被占用至 Vector 完成的简例，单 tile 服务为 m、v，缓冲槽数为 b：

\[
II^*=\max\left(m,v,\frac{m+v}{b}\right).
\]

第三项是缓冲复用环产生的约束。对于两个独立阶段、同质 tile、空初始状态及 b≥2，有限 N 块精确完成时间为 `m+v+(N−1)max(m,v)`；单缓冲则为 `N(m+v)`。这是该简例的结论，不是任意融合算子的通用公式。

已有 ResourceEngine 的纯 CPU 对照得到下列结果，数值是归一化示意单位，不是 NPU 实测：

| N | m / v | 缓冲槽 | 总量取 max | 真实有限依赖执行 | 稳态 II |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | 1 / 2 | 2 | 2 | 3 | 2 |
| 4 | 1 / 2 | 1 | 8 | 12 | 3 |
| 4 | 1 / 2 | 2 | 8 | 9 | 2 |
| 4 | 3 / 2 | 2 | 12 | 14 | 3 |

这也区分了稳态瓶颈与有限延迟：Vector 决定 II 时，减小 CopyIn 仍可能缩短填充阶段，但不改善稳态 II。Ascend 官方资料明确将 CopyIn、Compute、CopyOut 的依赖和 double buffer 用于流水优化；它提供实现依据，不提供适用于所有 A3/A5 SKU 的固定带宽数值。[Ascend C 最佳实践 §5.4](https://www.hiascend.com/doc_center/source/zh/canncommercial/80RC3/developmentguide/opdevg/ascendcbestP/CANN%208.0.RC3%20Ascend%20C%E6%9C%80%E4%BD%B3%E5%AE%9E%E8%B7%B5%2001.pdf)。

复现：`.workstreams/composability/codex-vector-mte2-theory-repro-20261025.py`（位于 mindie-agent 工作区）。

### 15.4 同倍率与分段仿射约束可直接用于验证

固定图、迭代距离及容量区域中，若所有阶段服务 `t_u(z)=z×a_u` 且 z>0，最大环比具有正齐次性：

\[
II^*(z)=z\,II^*(1).
\]

主导环集合保持不变。若服务是 `t_u(z)=a_u+b_u z`，II 是各环仿射函数的上包络；切换只能发生在可计算的交点。若改变 z 导致 tiling、缓存、核映射或 dispatch 变化，则先切换到对应执行图，再在新的区域内应用结论。

这给出了比“数值接近一个基线”更强的验证：固定配方的同倍率控制不应凭空生成曲线拐点；实际 tile/cache 边界应有可追溯的图或流量变化。仅修改不出现在任何当前主导环上的阶段服务、且未跨越约束交点时，稳态 II 不变；有限首尾延迟可能仍变化。非关键环可能与关键环共享阶段，不能把“非关键环”整体当作无敏感度。共同主导环应全部保留，不能将一个混合依赖瓶颈强行标成单个硬件单元。

瓶颈提取不必枚举全部环。对一个已验证可行的周期 P 和 offsets，定义边松弛量 `slack_e=offset(v)-offset(u)+d_e P-t_u≥0`。环上 offsets 消去，得到 `Σslack=PΣd-Σt`；因此正总迭代距离的临界环全部由紧边组成。可在紧边子图上求强连通分量，保留合法的单节点自环和共同主导部分，再输出少量可检查的 witness。只有零总距离/零服务的退化环不构成吞吐瓶颈。数值情况下保留周期可行区间和约束残差，区分近临界与确认临界；受限长度/数量的展示环不能反向覆盖已经求得的周期。当前 DFS 的枚举上限仅可限制展示，不可冒充完整 critical graph。

### 15.5 把理论结果用于 should 的搜索

计划 π 包含合法的 TP/DP/EP/PP/CP、tile、kernel/融合、缓冲数、路由和调度选择。固定输入及精度语义后，以当前公共执行器求 `T(π)` 和同一计划的服务指标：

\[
U=\min_{\pi\in\mathcal P_{\mathrm{evaluated,feasible}}}T(\pi),\qquad
L\le T^*_{\mathcal P}\le U.
\]

这个关系仅针对声明模型、相同最小化目标和合法计划族。若使用整体下界 L，必须覆盖未枚举合法计划的放松问题；一个候选的固定计划下界不能当整个计划族的下界。U 是模型中的可行排程，不是硬件已实现的性能保证。服务目标若是 SLA 下最大 goodput，应另用相应的吞吐目标和上下界，不能与耗时下界混用。

采用已有候选枚举和下界剪枝即可起步。小子图可用资源受限排程/约束规划核验事件引擎；不要求整模建立巨型整数规划。大重复区域由周期结构加速，但必须保留首尾、剩余阶段和缓冲状态，在 arrival、batch、KV 页、缓存、频率或 dispatch 边界重新执行。

峰值 UB/L1/L0、HBM、KV、通信和 workspace 都约束候选。double buffer 只有在额外缓冲确实可分配、生命周期和核并发合法时才是可行优化；不能免费增加槽数。局部 kernel 更快也未必使 TTFT/TPOT/TPS 更好，最终由同一请求事件循环复算。

### 15.6 参数识别要跨过可辨识边界

若所有观测都在同一个 Vector 主导区，MTE2 带宽在这些观测中的敏感度可能为零；仅增加同类样本不能识别该参数。反过来，纯搬运主导的总时间也不能识别 Vector 指令能力。不同指令混合、事务大小、在途数、缓存路径和缓冲数应通过最少的区分性条件识别。

优先使用已有 kernel/指令/stream 记录识别当前图，再选择边界两侧的少量局部 probe。观测必须对应原语服务、路径流量或关键等待之一；一个总 kernel 时长不能同时确定多个无法区分的参数。边界不确定时保留参数范围、候选图和预测区间，允许解析预测并独立评分。

### 15.7 当前源码接线与已复现问题

1. `a3_resource_engine.py` 已支持真实依赖和共享资源；`a3_resources.py::add_costed_ops` 已能执行 `fusion_stages`，也已将 `CostedOp.execution_plan` 经 `operator_plan.py::register_kernel_plan` 接入同一个引擎。`KernelPlan` 已承载有限阶段、依赖、rate limit、一次 dispatch 和完成 gate；`operator_vector.py` 已有 read→vector→write、FIFO 和 buffer reuse 的构造。优先复用这些接口和结构，不重新实现引擎；其默认原语参数标记为 assumed，不能当 A3/A5 校准值。
2. 实际 Qwen3.6 TP1 的单轮 lowering 产生 16 个 `attention_fused`，此次读取的 `fusion_stages` 长度全部为 0。`a3_cost.py` 新增的 rowless fused 分支将资源总工作交给单任务，仍不足以验证有限 tile 和缓冲造成的转换。接通实际 recipe 的微阶段是第一条 pilot，不以补 floor 或恢复旧 TPOT 数字替代。
3. `pipeline.py::_solve_expanded` 当前用 `max(offset)+max(service)` 估计填充/排空。上述 m=3、v=2、N=4 对照中，双缓冲可行排程为 14，求解器却将 15 标为 `finite_task_lower_bound`；单缓冲实际 20、报告 21。另一个两相位单 Vector FIFO、每 tile 服务 2 的对照，N=1/2/4 实际完成 2/4/8，当前返回 4/6/10。必须修复有限任务语义。即使改为 `max(offset+service)`，一个周期最优排程也未必给出有限任务最优值，并且还需处理 super-period 相位与剩余 tile；有限值应由真实初始状态和有限依赖执行得到，L 与可行排程值分别报告。`a3_grouped_mechanism.py` 当前只消费 II/瓶颈字段，不能由此推断它已将错误的 finite 字段用于整模时间。
4. `_tight_cycles` 排除了长度 1 的自环，导致上述 Vector/MTE2 单流水主导时 `bottleneck_pipes=[]`。FIFO 的正距离自环是合法瓶颈约束，需要保留并与完整求解周期核对。
5. 专门数学研究子代理提出、主代理独立复跑了测量覆盖污染工作量的反例：相同 Qwen3.6 TP1、batch4、q4、context16384，只将 `decode_batch_attention_short_scope` 改为 `bands=[32768], batches=[4]`，MTE2 字节从 268,697,600 变为 1,610,809,344（约 5.995 倍）；Vector 工作基本不变。`a3_catalog_attention_gqa.py` 用 `measured_batch_row` 选择 Hkv 或 Hq 条 KV stream，而该布尔受实测 band 影响。op recipe、dtype、依赖、请求等不变，但派生 KV shape 还出现 `context+q` 与 `context` 的差别。复现为 `.workstreams/composability/codex-gqa-evidence-work-repro-20261025.py`。这会直接改变算出的 Vector/MTE2 转换面。真实 kernel 是否存在其他 dispatch 差异尚待实现证据，不能直接认定全部配置都只读一次 KV；必须由实际 recipe/tiling 定义复用和 query 边界，未知时明确假设或上下界，不能由测量覆盖决定物理工作。
6. `_rowless_fused_real_work_costed` 当前以是否加载 decode family artifact 决定是否进入工作量定价分支。应将“实际实现/图的选择”和“参数是否有测量证据”分开；先构造相同语义图，再在适用条件内识别原语参数。不能为保住某个原分数继续维护两种不一致的解析机制。

上述是数学/接线反例，不证明它们单独解释了当前整模残差。第一批修复后，由 H 在最终主线上复用现有 Qwen TP1/TP8、短长 context 及 batch 条件评分，保留失败和剩余缺口。

交接前增量复验：`07c378e`/`74ad5e3` 已统一 KV stream 基准，消除了上述约 6 倍差异；该历史反例不能继续标为当前未修。相同脚本仍因测量 scope 变化产生 `kv_len=16388/16384`、MTE2 `1,611,202,560/1,610,809,344` 和 Vector `31,464,960/31,457,280` 的差别，真实输入未变。下一步仍须消除测量覆盖对语义边界/实现选择的影响，并以真实 kernel 证据确定逐 query head 重读或共享 KV 的条件，不能以旧预测数字不变作为正确性要求。

### 15.8 实施与独立验收

- 原流水/执行 owner 修周期瓶颈提取和有限任务语义；纯 CPU 对照先闭合。
- 原语义/算子 owner 从实际 kernel 实现生成首个有界 tile/阶段图，原参数 owner 识别 Vector 指令族和搬运路径参数；共享文件由单一 owner 集成。
- 原 A5/profile owner 复用固定条件 profile，定位 recipe、tile、stream、缓存与数据流差别；仅在现有证据不能区分具体假设时追加局部 probe，不重复加载整模。
- 原 H/独立验证 owner 检查瓶颈两侧、切换点附近、缓冲容量边界、有限 N 与稳态，以及同计划 predict/should；没有使用的条件保留为验证集。
- 不重启另一套八路；数学研究结果由 DSH 主协调者映射到现有就绪 owner。既有 PD、显存、其他模型和最终精度目标继续推进，不能以理论文档或局部等式成立替代交付。

本节主要数学依据还包括 [Murthy 与 Lee 的 SDF 吞吐/延迟分析](https://digicoll.lib.berkeley.edu/record/136000/files/ERL-94-46.pdf)、[Little 的在途数量/吞吐/响应时间关系](https://pubsonline.informs.org/doi/abs/10.1287/opre.9.3.383)、[FlashAttention 的 I/O-aware 构造](https://arxiv.org/abs/2205.14135) 和 [Saha 与 Ye 的 attention I/O 复杂度结果](https://arxiv.org/abs/2402.07443)。I/O 渐近下界不能直接用作 decode/GQA/稀疏 attention 的延迟式；仍须按实际 loop nest、片上容量和重复读取计数。稳态在途关系只给有限槽位的供给上界，不能替代任意访存模式的完整服务模型。

## 16. 持续数学审查：should 的证明范围与可执行反例

2026-10-25 用户进一步要求持续吸收有实际用途的数学工作，尤其用于 should。本节在第 15 节基础上增加搜索和资源约束的可检验契约。当前反例核查于 sim `fdeac67`，其后的状态以最新主线复验为准；第 15.7 节保留的历史反例不能自动视为仍未修复。

### 16.1 先固定优化问题，再谈下界与最优性

一个 should 问题必须声明输入/到达轨迹、初始缓存与 KV 状态、数值语义、投机接受过程、硬件资源、允许变化的计划族和目标函数。令合法且满足 SLA 的计划族为 P，目标为同一观测边界上的最小化量 f：

\[
f^*_{\mathcal P}=\inf_{\pi\in\mathcal P}f(\pi),\qquad
U=\min_{\pi\in\mathcal E\cap\mathcal P} f(\pi).
\]

E 是已经执行评估的候选集合。U 必须附带一个完整可行计划及其事件、内存和服务指标；它是声明模型中的可行目标，仍需要独立硬件证据确认精度。同一个计划给出 TTFT、TPOT、TPS 和 E2E，不拼接多个计划各自最好的指标。Pareto 集同样由完整计划组成；SLA、吞吐最大化与耗时最小化使用各自的目标和界，不能混用。

必须区分固定计划下界 L(π)、整个计划族的下界 L_P，以及已验证硬件性能。当前 `a3_should.py` 已说明下界不是 global bound，但返回的是所选计划的 L，`gap_ms=U−L` 只能表达该计划与其资源界的距离，不能作为未搜索计划族的最优性差距。

设未探索子域 S_j 覆盖全部剩余合法候选，且每个 ℓ_j 都已证明不大于该子域内的最优目标。保留当前最优可行 U 后，才可使用：

\[
L_{\mathcal P}=\min\bigl(U,\min_j\ell_j\bigr)\le f^*_{\mathcal P}\le U.
\]

只有在同一目标、同一状态和合法放松下，才能用 `ℓ_j≥U` 剪枝。没有有效的未探索域下界时，可以继续枚举或报告启发式搜索结果，不伪造最优性证书。若每个 PlanOption 只执行一种固定调度策略，穷举也只证明这些具体策略中最优；不能因此声称同一映射下所有合法排程都已最优。小规模精确枚举/约束排程用于验证边界和剪枝；继续复用现有计划生成与执行器，无需先建立整模巨型整数规划。方法依据：[Boyd 与 Mattingley 的分支定界讲义](https://web.stanford.edu/class/ee364b/lectures/bb_notes.pdf)。

### 16.2 通信下界必须保留物理链路范围

资源约束的基础是同一物理资源上的容量守恒。以 u_ir(t) 表示节点 i 对资源 r 的实际服务速率：

\[
\sum_i u_{ir}(t)\le C_r(t),\qquad
\int u_{ir}(t)\,dt=w_{ir}.
\]

固定映射和恒定容量时，`max_r(Σ_i w_ir/C_r)` 给出完成这些工作的服务时间下界。它约束的是对应工作及时间范围，不能直接当任意请求的 TTFT、平均 E2E 或分位数下界。逐链路工作必须由相同请求分配、rank placement、collective 算法和路由生成；共享链路累加，独立链路分别约束。路由尚未确定时，可用覆盖所有合法路由的流量/割容量放松，不能把固定路由界冒充全域界。

本轮最小反例使用真实公共 should 入口和现有资源引擎，参数为归一化 CPU 控制，**不是 NPU 测量**：8 die、4 个 P32/O2 请求、TP2，比较四条独立链路与一条共享链路。

| 物理链路 | DP | 旧通信 L / ms | 按实际链路分配的通信 L / ms | 可执行 U / ms | 当前公共返回 |
| --- | ---: | ---: | ---: | ---: | --- |
| 独立 | 1 | 2.703360 | 2.703360 | 2.930042 | modeled |
| 独立 | 2 | 2.703360 | 1.351680 | 1.486285 | infeasible |
| 独立 | 4 | 2.703360 | 0.675840 | 0.742143 | infeasible |
| 共享 | 4 | 2.703360 | 2.703360 | 2.781663 | modeled |

`a3_semantics.py::hardware_lower_bound` 将全体通信字节除以一条最快链路容量；`a3_should.py` 随后把 `U<L` 标成计划不可行。此处下界没有保持资源范围，错误排除了已有可执行 witness。不能统一除以 DP，最后一行就是反例。下界与可行排程冲突时，应报告模型/下界不一致并定位，不能自动当作真实容量不足。

复现：`.workstreams/composability/codex-should-math-link-bound-20261025.py`。脚本同时输出语义 payload 和实际服务需求；含启动开销的 byte-equivalent 不冒充真实 wire bytes。

### 16.3 搜索未找到与证明不可行是不同结论

同一脚本的第二个控制使用 TP1，排除通信下界问题；合法族只有 DP1、DP4，逐请求 E2E SLA 为 0.15 ms。预算 1 只评估 DP1，当前返回 `sla_infeasible` / `sla.status=infeasible`，但仍有 1 个未探索计划；预算 2 找到 DP4，可行 U 为 0.081434 ms。

因此，未穷尽或未对剩余域逐项给出有效不可行证明时，状态只能表达“已评估子集没有找到可行解”。应保留搜索预算、剩余候选、已证明排除的候选及原因；`optimal_in_family=false` 本身不能消除上层 `infeasible` 的歧义。增加预算并保留 incumbent，在同一确定性问题上不应使最佳可行目标变差。所有候选都已被合法性、容量或有效 SLA 必要条件排除时，才报告声明计划族不可行。

### 16.4 同样的孤立耗时不代表同样的共享竞争

在固定实际工作、图和请求条件下改变服务能力，应改变速率约束，不改变物理 FLOPs/bytes/ops。资源范围必须明确：独立时钟域降频、某 owner 限速、共享总线变慢是不同干预。语义工作、实际物理事务和服务时间分别记录；若真实机制改变了事务或工作，先从该机制重算，不能用一个 slowdown 系数伪造新增工作。

归一化引擎对照：资源容量 10，A 和 B 各需 10 单位工作。A 单独运行时，将 A 的能力限制为 5 与把 A 的工作改成 20 都得到时间 2；A、B 共享运行时，前者得到 A/B 均在 2 完成，总物理工作 20，后者得到 A=3、B=2，总物理工作 30。孤立时长一致掩盖了竞争语义错误。

复现：`.workstreams/composability/codex-should-math-service-control-20261025.py`。当前 PD 已将 demand 乘法改为 `service_scale`，本轮旧脚本复验中 slowdown 不再翻倍物理计数；不重复报告已修复的乘法问题。下一层验证是同一干预在独立池、共享 HBM/host/link、有限阶段和回压下的执行是否符合相同容量约束，不能只看计数字段或单请求完成时间。

### 16.5 用确定性网络演算检查 PD 突发与队列边界

网络演算可为 burst、排队和 drain 提供额外的必要/充分界，前提是已建立真实到达包络和服务保证。它不会自动识别 GPU/NPU 服务率，也不替代动态 batching 的事件执行。以同一计量单位的累计到达 A 和累计完成 D 为例，若到达包络为 `α(t)=σ+ρt`，服务曲线为 `β(t)=R[t−T]+`，且 `ρ≤R`，可用：

\[
B_{\max}\le\sigma+\rho T,\qquad
W_{\max}\le T+\frac{\sigma}{R}.
\]

后一项是虚拟延迟界；对应实际 FIFO 数据延迟需要顺序与服务假设成立。σ 是突发工作量，ρ/R 的单位必须一致。队列中的 request、KV bytes、prefill tokens、decode committed tokens 不可直接互换。P→KV 传输→D 之间存在工作量转换与逐阶段释放，只有显式处理转换、packetization、共享资源的剩余服务及路由后，才能组合服务曲线。

可先用于小规模 PD 反例：突发大小增加、独立链路合并、D 服务能力下降、停止到达后的排空，以及已知到达/服务包络下的队列上界。KV 峰值仍按每个分配的真实生命周期、增长、迁移和释放计算，不把历史总分配量或队列请求数直接当显存需求。依据：[Le Boudec 与 Thiran 的 Network Calculus](https://leboudec.github.io/netcal/)、[Le Boudec 2019 教程](https://leboudec.github.io/leboudec/resources/tutorial-nc-dagstuhl-EPFL-2019-LEB.pdf)。

### 16.6 守恒只是必要条件，不能从总量补造执行结构

`Σ tiles`、总 bytes 和总 FLOPs 相等，并不能唯一确定 tiling、依赖、缓存复用与缓冲峰值。例如 `[4]×34` 与 `[8]×17` 的总和都是 136，但其发射、尾块、缓冲和有限流水可以不同。仅根据目标总和把列表补齐或重复首项，不是从实际 recipe 推导工作。块数和边界须来自真实 per-call extent/loop nest；审计从这些输入独立重建，不能用生产端同源声明的 count 代替证据。

这与参数可辨识性是同一个问题：约束不足时保留候选解释，追加能区分它们的局部观察。不要靠更多同类总时长或总量去“验证”一个无法识别的内部结构。最小反例应覆盖非整除 tail、不等长 call、不同块大小与相同总量下的不同合法结构，验收真实执行和资源变化，不写常量列表断言。

### 16.7 投机解码的平均提交量不能决定有限完成时间

用现有 `SpeculativeSpec.committed_distribution()` 可构造一个无采样的有限更新过程 oracle。在每步固定耗时 d、步间独立同分布且每步至少提交一个 token 的假设下，剩余 n 个 token 的期望完成时间满足：

\[
E_0=0,\qquad E_n=d+\sum_{j\ge1}P(J=j)E_{\max(0,n-j)}.
\]

两种分布都平均每步提交 2 token，步长都是 10 ms，长期 TPOT 均为 5 ms。但剩余 2 token 时，恒定提交 2 的期望完成时间是 10 ms，10 ms 内完成概率为 1；提交 1 或 3、各概率 0.5 时，分别为 15 ms 和 0.5。因此，长期吞吐和 mean-field advance 不能唯一决定有限 E2E 或硬 SLA。

复现：`.workstreams/composability/codex-should-math-finite-acceptance-20261025.py`。这是下一项可接入的数学 oracle，不是已经确认生产随机路径错误或硬件验收通过。上下文影响 step cost 时，将上下文/缓存加入状态并按真实提交量推进；接受率有相关性或多请求竞争时，保留相应状态，不能直接套独立更新式。期望值、概率保证和逐请求确定性 SLA 分别报告。长期更新率与有限停止时间的区别可参考 [Gallager 的更新过程课程](https://ocw.mit.edu/courses/6-262-discrete-stochastic-processes-spring-2011/resources/lecture-12-renewal-rewards-stopping-trials-and-walds-inequality/)；具体投机算法、验证和拒绝后推进语义参考[原始 speculative decoding 论文](https://proceedings.mlr.press/v202/leviathan23a.html)。

### 16.8 持续吸收的价值门槛与当前分工

每项新数学方法都说明：要解除的实际缺口、变量与假设、适用域、当前源码入口、可区分反例、独立验证条件。先复用已有算法和公开原始资料；有明确收益再引入求解器或新测量。数学等式成立、CPU oracle 通过、生产入口接通、实测精度达标分别记录。

本批由 DSH 现有 should owner 处理链路下界和搜索状态；独立 owner 复跑共享/独立链路及预算控制。PD/执行 owner 验证服务能力与物理工作分离后的共享竞争；原子算子 owner 从真实 call/recipe 重建 tile 信息，独立审计 owner 保持输入来源独立。继续现有最多 8 路和共享文件单写者，主协调者按就绪依赖续派，不为数学研究另起一套实现。每 30 分钟的已有检查持续筛选有用方法；没有新证据或可行动项时保持安静，既定模型与硬件精度目标继续推进。

交接后增量复验（`5542791`）：主代理再次独立执行原链路/预算脚本，六个共享/独立链路控制均返回 modeled；独立 DP2/4 的 L 已分别为 1.35168/0.67584 ms，共享链路仍为 2.70336 ms，该反例关闭。预算 1 的顶层状态已改为 `subset_exhausted`，预算 2 仍找到原 DP4 可行方案；嵌套 `sla.status` 仍为 `infeasible`，后续需将其范围与顶层搜索状态统一，避免只读取 SLA 对象的调用方误判。F 的 `3902aa7` 已删除从总量补造 tile 列表的分支；旧 payload 因缺实际 call 信息保持 incomplete，不能据此恢复精度 PASS。有限投机递推已提交 `29de47f`，生产接线和独立验证继续按上述适用域验收。

## 17. 加速收敛：独立证书、可辨识性与按反例细化

2026-10-26 的增量工作以 sim `d6315c3` 为核查基线。第 15–16 节已经覆盖资源下界、有限排程、周期结构和搜索；本节把它们组织成更短的纠错闭环。速度收益来自提前排除不成立的解释，以及减少没有辨别力的测量；尚无证据支持一个具体的收敛加速倍数。

### 17.1 将生成排程与验证排程分开

`a3_qwen36_prefill_plan.py::_schedule_witness` 当前用与目标耗时相同的递推生成 witness，再比较两者结束时间。二者相等不证明排程可行。检查器应独立读取真实 `KernelPlan` 的阶段工作、依赖、物理资源映射和 machine 容量，不以待审 witness 自带的速率作为标准。

最便宜的必要条件是对每个阶段 i 和资源 r 检查：

\[
e_i-s_i\ge w_{ir}/C_r,\qquad s_i\ge\max_{j\in pred(i)}e_j.
\]

随后检查阶段覆盖与工作守恒、逐时段共享容量、核映射和缓冲生命周期。若计划明确采用常速阶段，可按开始/结束事件扫描 `Σ_i rate_ir≤C_r`；变速服务则检查真实分段服务及积分，不能用全程平均值代替峰值约束。缓冲分配的字节数和存活区间必须能证明每一物理池的峰值不超过容量。缺少其中一项，只能报告已经检查的必要条件。

当前真实最小反例为 Qwen3.6 TP1、q=128、context=384，一个 query tile、两个 KV tile：

| 阶段 | 实际 HBM 工作 / B | witness 时间 / ns | 按 machine 至少需要 / ns |
| --- | ---: | ---: | ---: |
| `q0.load.q` | 393,216 | 163.84 | 327.68 |
| `q0.k0.load.kv` | 262,144 | 109.226667 | 218.453333 |
| `q0.k1.load.kv` | 262,144 | 109.226667 | 218.453333 |

这里实际 HBM 容量为 1.2 TB/s，即 1,200 B/ns。声明的 U=2.138201212 μs 与 witness 结束时间相等，三个阶段却都需要两倍实际容量；资源引擎耗时为 2.278429123 μs。这已否定该 witness，尚不能证明不存在另一个达到同一 U 的合法计划，也不证明硬件误差。复现：`.workstreams/composability/codex-should-certificate-probe-20261026.py`，从 sim 工作区以 `PYTHONPATH=. python3 <脚本绝对路径>` 执行。

检查器输出第一个违反的约束及其 stage/resource 来源即可，不新增多层状态或重复审计文件。先覆盖此两 tile 反例，再用小规模精确枚举检查共享资源和缓冲竞争。固定时长的 job-shop 求解可作为局部 oracle，但不能直接代表变速共享带宽；约束必须与现有执行器一致。[OR-Tools job-shop 示例](https://developers.google.com/optimization/scheduling/job_shop)说明了依赖、区间和资源互斥的基本构造。U 只有在完整可行性条件成立后才进入第 16.1 节的 incumbent。

### 17.2 对 tile 和 I/O 建立不同的计数对象

令 S_q 为 query q 实际访问的行集合，d 为实际行字节数，g 为实现中的一个 s1 tile。分别保存：

\[
U_{data}=|\cup_q S_q|d,\quad
R_q=\sum_q|S_q|d,\quad
R_{tile}=\sum_g|\cup_{q\in g}S_q|d.
\]

三个量分别表达唯一数据、逐 query 逻辑访问和假定 tile 内复用时的访问量；实际 HBM 事务与各级 MTE 搬运另行计数。它们受事务对齐、初始驻留、核间重复读取、cache scope 和输出写回影响，不能把任意一个逻辑量直接标为物理 HBM bytes。仅看到时长残差变小，也不能反推出 cache hit rate。

V4F 的 `_masked_index_rows` / `_index_producer` 应先按实际 kernel variant 重建 s1 分组、压缩整数除法、s2 block 与 tail，然后生成每次 transfer。当前可见 quant-lightning 源码 `GetS2BaseBlockNumOnMask` 先做压缩整数除法再计算 block 数；是否与测量镜像中的 kernel 一致仍需确认。不能先对候选数取平均，再让所有 query 使用该均值，也不能靠 `per_s1_tile` 标签证明 `tokens*rows` 的物理来源。

GLM 的 `a3_glm53_attention_rows.py` 已修复多请求 QK/PV/Vector 归属；下一层是证明 fused SFA 的 Q/output 固定 I/O、sparse KV 复用、dtype 字节与真实 tile/核划分。`sparse_pairs*d` 是访问计数候选，`kv_reuse=true` 不是复用证据。grouped MoE 同理，先有真实 group list、专家和分块，再推导共享或重读。

I/O-aware 方法借鉴 [FlashAttention 原论文](https://arxiv.org/abs/2205.14135)中利用片上空间减少传输的思路；其 dense GPU 条件与渐近式不能直接作为 Ascend MLA/DSA 的时延或物理流量公式。

### 17.3 先找不可辨识方向，再选择控制点

对已通过可行性检查、实现机制固定的候选 m，使用已有精确 call 的预测 `f_m(x_i,θ)`。正参数可取对数坐标；若有独立噪声估计 σ_i，局部加权雅可比和信息矩阵为：

\[
J_{ij}=\sigma_i^{-1}\frac{\partial f_m(x_i,\theta)}{\partial\log\theta_j},\qquad
F=J^\top J.
\]

检查秩、奇异值和弱方向，不在不可辨识方向继续拟合。若样本存在相关噪声，应使用相应协方差白化；没有可靠噪声估计时，只报告局部灵敏度，不报告统计置信区间。dispatch、tail 或瓶颈切换处应按不同机制分区，雅可比不是全局可辨识证明。

一个纯 CPU 例子足以说明收益：串行两路径 `t=aH+bM`，现有 `(H,M)=(1,1),(2,2),(4,4)`，设计矩阵秩为 1，`F` 特征值为 `[0,42]`。把整套测量重复十次变成 `[0,420]`，仍只能识别 `a+b`。增加一个能真正分离路径的 `(0,1)` 控制，才得到满秩和约 `[0.494,42.506]`。这是数学示例，不是某个 NPU 上该控制已可实施的声明。

选择后续控制时，先增加秩并提升最弱方向，再在满秩条件下用 `logdet(F)` 衡量整体信息；计入时间和资源预算。对应 E/D-optimal 设计可参考 [Boyd–Vandenberghe §7.5](https://stanford.edu/~boyd/cvxbook/bv_cvxbook.pdf)。不能用正则项使矩阵可逆，再宣称数据已足够识别参数。若模型为 `max(H/B_H,M/B_M)`，始终处于同一瓶颈区域时另一能力可能完全不敏感，控制点必须有能力跨过该区域。

优先从现有 profile 选择下列少量控制；只有缺少能区分假设的观察时才申请实际设备窗口：

| 控制 | 保持不变 | 用途 |
| --- | --- | --- |
| `q=1,s1,s1+1` | 候选集合、dtype、压缩规则、实现身份 | 区分唯一数据、逐 query 和逐 s1 tile 访问 |
| 候选数跨越 `s2−1,s2+1` | q 与已确认 kernel variant | 验证 block/tail；压缩取整单独核对 |
| 已有相同 geometry、路径已确认不同的 call | routing、实现、计时边界 | 区分 HBM 事务变化与 MTE 访问变化 |

仅第二次调用、工作集看似放得下缓存，都不足以确认 warm 路径。真实 causal mask 要逐 tile 重建；固定候选集合的合成例只能解释判别方法。保留至少一个未用于选择或识别的 geometry 作独立验证。

### 17.4 按最小反例细化，保留有限窗口恒等式

把循环收缩为：源码定义工作与约束 → 独立检查 → 最小反例 → 只细化受影响的资源/阶段 → 复用已有实测判别机制 → 同一生产入口复验。将“复制推导再比较数值”替换为“不同来源的约束检查”，将一次性数值修补替换为可复用的不变量。这里借鉴 [Clarke 等的 counterexample-guided abstraction refinement](https://web.stanford.edu/class/cs357/cegar.pdf)工作方式；这是用于性能建模的工程迁移，原文不直接保证本模型精度或终止速度。

客户端/PD 的有限窗口可额外使用样本路径恒等式。请求 j 的到达与离开时刻为 a_j、d_j，N(t) 为相同边界中的在途请求数，则：

\[
\int_0^T N(t)\,dt
=\sum_j[\min(d_j,T)-\max(a_j,0)]_+.
\]

初始在途和末尾未完成请求必须计入截断区间。该恒等式不需要稳态假设，可用事件扫描及活动请求状态在线计算，不保留无限历史；它能发现漏记、重复完成和统计窗口错位，但不能单独证明调度正确。device 完成、client 完成、下一请求到达采用各自明示边界；闭环依赖还需单独检查 `a_next=d_client+think_time`。

修正优先级以违反物理/因果约束为先，其后是能改变当前候选排序或 SLA 判定的不确定性。已经证实合法的 incumbent 始终保留；合法域下界只在覆盖范围与目标一致时剪枝。原 G 负责有限计划与 witness，H 独立检查，F 负责 should 接线，GLM/V4F owner 负责源码工作，客户端 owner 与独立 owner 分别负责事件与恒等式，capture owner 负责既有观测和设备窗口。共享文件单写者，延续既有八路，不另建执行器或整模优化系统。


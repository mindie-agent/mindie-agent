# 执行资源预期、代码有界性与规格匹配设计

[返回文档中心](README.md) · [设计原则与 PR 自查清单](design-principles.md) · [架构与领域边界](architecture.md)

本文定义执行资源约束的职责归属、当前代码事实与后续接线目标。**设备忙闲（Busy/Idle）、可用容量（Capacity Headroom）、并发预约/租约授予（Reservation / Lease Grant）与内核级内存硬限制（Hard Limit）各自回答完全不同的问题**——绝不能把其中任意一项的单元测试或组件实现冒充为其余各项的端到端验收。

## 一、“当前代码 / 目标设计 / 未验收”实现边界

以 2026-10-24 源码审查基线（`remote-dev` `b91874e` 及配套 PR [`remote-dev #44`](https://github.com/mindie-agent/remote-dev/pull/44)、`coordinator` `7a252d0` 及配套 PR [`coordinator #64`](https://github.com/mindie-agent/coordinator/pull/64)）为准，各能力的真实状态严格区分如下（本文不代表已安装宿主插件已合入或启用全部下述变更）：

| 能力维度 | 当前代码（已实现） | 目标设计（待接线） | 未验收边界（不得夸大宣称） |
| --- | --- | --- | --- |
| **工作负载规格与放置判定** | `remote_dev/core/host_spec.py` 提供 `WorkloadExpectation`、`HostHardwareSpec`、`normalize_remote_probe_spec`、`evaluate_placement` 与本机跨进程 `reserve_local_resources`（SQLite WAL） | `sim` / `profiler` 等组件在各自真实 CLI 入口按模型层数、Token/事件规模与 Trace 大小动态计算预期工作集并调用放置判定 | 基础库存在不等于所有业务入口均已接入；`sim` / `profiler` 真实 CLI 尚未统一接入动态估算与自动分流 |
| **远端集群容量与放置准入** | `coordinator` 的 `fleet_probe` 采集远端主机内存、核数与卡/Die 观测；`placement.py`（`hardware_shortfall`、`select_runtimes`、`can_prepare`）对显式声明 `cpu_cores`/`memory_mb`/`hbm_mb` 的请求按同次放置的 `host_specs` 快照校验容量 | 将逐设备 HBM 余量校验下沉到真正发放物理 Phy-ID 的主机租约队列（`HostQueue`） | `RuntimePool` 的 `prepared-root` 目录行本身不存动态容量；放置阶段的快照校验只是**候选可行性筛查**，不等于编译完成后的启动期显存保留 |
| **编译并发与每槽份额** | 主机队列限制并发编译槽位数，构建脚本独立计算 worker 数；两侧在 Linux 下已读取 cgroup CPU 配额 | 由主机队列在授予 `CompileLease` 时一次性计算并下发每槽内存/CPU 份额，`PreparationProcess` 与 `MAX_JOBS` / `CMAKE_BUILD_PARALLEL_LEVEL` 统一消费同一上限 | 目前内存侧仍只读宿主机 `MemAvailable`，且“槽位数”与“每槽 worker 数”各自按同一份整机可用内存计算，尚未实现单次授予的乘积预算闭环 |
| **进程树所有权与退出回收** | Windows Job Object（`KILL_ON_JOB_CLOSE`）、POSIX 进程组 owner、Linux 远端 subreaper 与 `/proc` 进程树排空回执 | 保持现有所有权与退出排空链路，与内存限额解耦 | **进程所有权与超时排空只证明子进程可被追踪和终止，不证明运行期内存峰值有上限** |
| **进程树内存硬限制（Hard Limit）** | Windows `OwnedProcess(max_memory_mb=...)` 支持在显式传参时设置 Job Memory Limit | Linux 执行器按需接入真实已授权的 cgroup v2 `memory.max`；macOS 如实报告 `observed-only` | **当前不存在跨平台统一的进程树内存硬上限**：Windows 仅在显式传参时生效，POSIX `RLIMIT_AS` 仅限单进程虚拟地址空间而非进程树 RSS，macOS 无等价内核机制 |

已有规格判定库不是第二个调度器或常驻守护进程：组件声明工作负载预期 $\to$ 放置层按实测容量做候选筛查 $\to$ 实际执行主机的既有队列负责租约授予 $\to$ 执行入口消费授予结果。

## 二、任务预期与主机/设备容量事实

工作负载在启动前根据业务输入声明 CPU 核数、主机内存、物理执行单元数与新增显存需求。`TIER_PRESETS` 归属 `remote_dev/core/host_spec.py`，文档不维护第二份默认值表；预设档位仅作缺省起点，不能替代模型尺寸、Trace 规模或单 worker 编译峰值的真实核算：

- **组件工作集估算（目标设计，待接入）**：`sim` 与 `profiler` 应在各自真实 CLI/API 入口按模型层数、Token/事件数、明细级别（`--trace-detail`）与 Trace 文件体积估算活跃工作集。该估算属于待接入设计，不在文档中引用不存在的 `a3_host_budget.py` 或将规划接口写成已上线 API。
- **编译 Worker 峰值**：编译请求的 `per_worker_memory_mb` 必须覆盖 C++ 编译器与链接器峰值，不能把进程数或 NPU 数量直接当成内存预算。
- **零权重控制面与有界工作集**：元数据探测路径只读取 `config.json` 与 `safetensors` 头部，不加载模型权重、不初始化 `torch_npu`/CANN 上下文；大文件流式读取，长循环只保留活跃状态与有界预览，原始日志复用既有落盘与分片机制。

`HostHardwareSpec` 表示单次容量观测：`cpu_cores` 为物理核数，`usable_cpu_cores` 为扣除当前负载后的并发建议核数；主机可用内存（`mem_usable_mb`）与容器/cgroup 剩余配额需分别识别，不能把宿主机物理总内存当成容器内可用内存。

### HBM 容量、忙闲状态与物理 Die 计数

在设备层面，必须严格区分 **物理可租用单元数（Die vs. Card）**、**设备忙闲（Busy/Idle）** 与 **实测可用 HBM（`total - used`）**：

- **物理可租用单元（Die）对齐**：在统一执行规格（`normalize_remote_probe_spec`）中，`npu_count` 与 `free_npus` 一律按**可独立租用的物理 Die** 计数（昇腾 A3 双 Die 卡展开为 2 个 `dies` 单元，与 `ASCEND_RT_VISIBLE_DEVICES` 的 `Phy-ID` `0..15` 一一对应；单 Die 的 A2/A5 或无 `dies` 列表的旧格式行保持每卡 1 个单元）。当探测结果包含 `free_phy_ids` 时以其为准（空列表 `[]` 即明确的 `0` 可用 Die，优先于卡级 `free_npus`）。集群卡级计数仍可用于 UI 展示，但不能直接充当 A3 双 Die 的执行容量。
- **实测 `total - used` 计入可用 HBM，缺测绝不冒充空闲**：空闲单元的可用 HBM 严格按各设备实测的 `max(0, hbm_total_mb - hbm_used_mb)` 计算；若任一单元缺少 `hbm_total_mb` 或 `hbm_used_mb` 观测值，则置 `vram_free_observed = False` 且该单元不贡献可用 HBM（绝不把标称总容量当成可用容量）。同时，**设备处于 `idle`（`busy=False`，无活跃计算进程/可被租用）不等于物理 HBM 已用量为零**。
- **不将已用 HBM 笼统归因为固件，也不硬扣 `2–3 GiB` 固定常数**：空闲设备上的实测 `hbm_used_mb` 可能来自固件、驱动或未释放的运行时上下文，**仅凭 `npu-smi` 汇总读数并不能证明全部已用量都是固件保留**；且不同机型、驱动与容器环境的基线占用各不相同，因此直接采用各设备实测的 `total - used`，**绝不在代码或规则中硬扣 `2–3 GiB` 等拍脑袋固定值**。
- **卡级补充遥测的保守边界**：针对 `npu-smi` 摘要显示 `0 / 0` 的行，卡级补充查询（`npu-smi info -t usages`）仅在该卡能唯一对应单个可租用单元（单 Die 卡或无 Die 行的旧格式）时回填；多 Die 卡的卡级总量绝不均摊或臆测拆分到各个 Die，保持 `vram_free_observed = False` 并按“缺测不计入可用”处理。补充遥测只增加占用证据、绝不抹除已观测到的进程占用事实；卡级与 Die 级空闲清单同源派生，避免“卡已忙而 Phy-ID 仍列为空闲”。
- **避免重复扣减基线**：设备当前已用 HBM 已经在 `free = total - used` 中扣除；任务的 `Expected VRAM`（`vram_mb` / `hbm_mb`）只核算本次任务新增的模型权重、KV Cache、激活值、通信缓冲与运行时分配，不重复扣除设备固有基线。
- **主机级 HBM 总和 vs. 逐设备授予**：主机级 `vram_free_mb`（所有空闲 Die 的剩余 HBM 之和）仅提供主机级候选可行性筛查（例如两个各剩 `48 GiB` 的空闲 Die 合计 `96 GiB`，并不代表单个需要 `64 GiB` 的单 Die 任务能放下）；逐 Die 的最终显存可行性必须由实际设备租约授予者按选中的具体 `Phy-ID` 判定。

## 三、分流判定与实际授予

```mermaid
flowchart LR
    W[组件的资源预期] --> P[按真实本机与远端规格判定]
    H[主机与设备容量观测] --> P
    P --> L[本机满足时本地执行]
    P --> R[远端满足时选择候选主机]
    P --> X[返回不足或缺测的具体维度]
    R --> Q[既有主机队列授予设备与执行份额]
    L --> E[既有执行入口消费授予结果]
    Q --> E
    E --> C[进程所有权、超时与排空]
```

本机硬件规格充裕时（包括高配 Windows / macOS / Linux 开发工作站），任务可直接在本地执行，绝不按操作系统名称硬编码一刀切分流；仅当本机容量不足或任务明确需要远端专属容器与物理 NPU 时，才自动路由至匹配的远端主机。若可用主机内存连单个 Worker 的峰值需求都无法满足，执行层应显式等待、分流至大内存节点或直接报错拒绝，严禁用 `max(1, ...)` 强行拉起必然 OOM 的任务。

在 `coordinator` 内部，环境目录（Catalog）负责筛选兼容的软件栈与 Donor 解释器，而硬件容量判定则消费同一次放置决策采集的集群快照（`host_specs`）：当请求显式声明了 CPU、内存或 HBM 下限时，每个候选主机仅采样一次，并将同一份观测结果复用于 Donor 选择、容器准备检查与后续兼容性判定；未声明资源下限的旧式作业则零新增探测开销。若某台候选主机探测失败，系统沿用既有的 `waiting` / `cache-miss` 状态并完整保留该主机的原始错误信息，绝不将其伪装成“空闲无机器”。

需要注意，放置阶段的容量比对仅属于**候选可行性初筛**，并不等同于物理资源预留：在漫长的镜像/编译准备期间，主机负载与空闲显存随时可能变化。真正拉起设备负载时，目标主机上的既有租约队列（`HostQueue`）仍是当前设备状态与物理租约的唯一权威授予者。后续逐卡/逐 Die 的 HBM 余量门禁也应直接内聚到该授予点，基于启动时刻的最新观测与任务请求做原子裁决——既不另建第二套显存分配账本，也不拿编译开始前的旧快照去担保启动时不发生 OOM。

同时必须厘清纯内存算术与网络探测的耗时边界：`evaluate_placement` 自身的规格比对只是微秒级纯算术，但跨机采集 `fleet_probe` 往往涉及真实 SSH 往返，绝不能把“含远端实时探测的分流全链路”笼统宣传为毫秒级。单次 SSH 命令的 `30s` 超时也不等于整轮集群放置的总上限——单台主机探测可能依次经历主查询、可选卡级补充查询与本地缓存落盘，且多台候选主机串行探测时，外层超时预算必须完整覆盖各阶段耗时之和（过短的外层 Deadline 会把正常的实时探测中途掐断）。命中本地缓存的容量快照必须如实保留其采样年龄（Age），不得将缓存命中伪装成刚刚完成的实时探测。

此外，探测耗时落在哪条调用路径上也严格分离：后台守护模式（`_async_progress`）在独立进度线程中异步推进集群探测，`status`、`target` 与 `tail` 等查询接口仅以非阻塞方式读取已落盘的状态与数据新鲜度，绝不会被慢 SSH 探测卡住；而同进程同步调用则必须等待探测返回。文档与契约中既不宣称“远端探测对所有调用零延迟”，也不宣称“探测会阻塞日常状态轮询”。

## 四、编译槽位只分配一次预算

当前实现的一项已知缺口在于：“主机并发编译槽位数（Slots）”与“单槽内部并行编译进程数（Workers）”各自独立读取同一份宿主机 `MemAvailable` 计算上限，极端并发下两者的乘积仍可能超出整机物理内存。目标演进方案是在主机队列授予 `CompileLease` 时一次性算出单槽专属的 CPU/内存配额并随租约下发，供下游构建脚本直接消费，无需每个脚本各自重复探测整机容量：

1. **按真实执行环境采集配额**：由实际执行编译的目标主机读取可用 CPU 配额与内存余量；在 Linux 容器内同时取 cgroup CPU 配额、`memory.max - memory.current` 与宿主机 `MemAvailable` 的交集下界，严禁拿本地开发机的 `MAX_JOBS` 充当远端容器规格。
2. **静态切分乘积闭环**：初期按主机配置的并发编译槽位数静态切分单槽预算，防止后进入的编译任务挤爆早先已获批的槽位。对于同质编译 Worker，必须同时满足 CPU 配额约束与内存乘积不等式 `slots * jobs_per_slot <= floor(usable_memory / worker_peak)`；若单槽分得的内存不足以支撑 `1` 个编译 Worker，则挂起等待或拒绝授予租约。
3. **租约回执透传与统一环境变量消费**：`CompileLease` 直接复用既有租约回执结构携带单槽并发上限，由 `PreparationProcess` 统一注入构建环境，令 `MAX_JOBS`、`MINDIE_BUILD_JOBS` 与 `CMAKE_BUILD_PARALLEL_LEVEL` 共同服从同一上限（允许调用方显式传更小的并发数，但严禁越过租约授予上限）。
4. **平滑演进与诚实能力声明**：在“队列授予 → `CompileLease` → 构建脚本消费”全链路打通并完成兼容验证前，暂保留构建脚本现有的本地保底计算；当旧版组件尚未下发槽位份额时，如实标注乘积内存保护尚未启用，绝不提前宣称全局乘积预算已闭环。是否需要进一步引入动态弹性份额，留待静态切分方案上线后的真机遥测数据决定。

## 五、进程回收与内存硬限额分开验收

在跨平台进程管理中，**进程树生命周期回收**与**内核级物理内存硬限额（Hard Limit）**是两项完全独立的能力：
- Windows 命名 Job Object（`KILL_ON_JOB_CLOSE`）支持在显式传入 `OwnedProcess(max_memory_mb=...)` 时配置作业级内存上限（[Job Memory Limit](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information)）；
- POSIX 进程组与 Linux `PR_SET_CHILD_SUBREAPER` 保障了子孙进程树归属追踪、超时取消与退出排空，但标准 POSIX [`RLIMIT_AS`](https://docs.python.org/3/library/resource.html#resource.RLIMIT_AS) 仅限制单个进程的虚拟地址空间，既管不住多进程编译树的总物理驻留内存（RSS），也会误伤合法的大虚拟地址映射。

**因此，绝不能宣称当前代码已在 Windows、Linux 与 macOS 三端实现了统一的进程树物理内存硬上限。** 在 Linux 上强制约束整棵子进程树的物理内存峰值，必须接入已实际挂载且具备写权限的 [cgroup v2 内存控制器（`memory.max`）](https://docs.kernel.org/admin-guide/cgroup-v2.html#memory-interface-files)；而在缺乏等价内核机制的 macOS 上，运行时应如实报告 `observed-only`（仅观测告警、无内核硬拦截）。上层调用方按任务所需的真实执行保障能力筛选目标机器，而非按 `sys.platform` 字符串盲猜；任何实现均不得把“函数接收了 `max_memory_mb` 参数”偷换概念说成“内核已强制启用整树内存硬限额”。

收尾阶段的进程清理与本地记账异常必须显式保留告警，但不得覆写已确认成功的业务主结果；不可逆外部写入的结果不确定性继续沿用标准 `unknown` 回执对账机制，绝不为本地容量探测或分流失败写入永久自锁死状态。

## 六、分期与判别性验收

| 演进阶段 | 责任组件与核心改动 | 验收能证明的真实边界 |
| --- | --- | --- |
| **1. 容量与物理单元语义对齐** | `remote-dev` 统一按可租用物理 Die 与实测空闲 HBM 建模；`coordinator` 解析器保留实测 HBM 并与设备忙闲解耦 | 证明 A2 / A3 双 Die / A5 真机 Golden Capture 下的物理单元计数与可用显存核算准确（不等于已跑通端到端业务负载） |
| **2. 集群放置与单次探测接线** | `coordinator` 打通环境 Catalog 与 `fleet_probe` 容量快照校验，无资源约束的旧作业保持零额外探测 | 证明 `TaskClient` → `service` → `RuntimePool` 的容量满足、容量不足与探测失败三条路径行为正确且单轮仅探测一次 |
| **3. 编译槽位乘积预算闭环** | 打通主机队列 → `CompileLease` → `PreparationProcess` → 构建环境变量（`MAX_JOBS` 等）配额透传 | 单测证明乘积不等式与参数透传生效；真机并发编译进一步验证实际子进程数、RSS 内存峰值与中断排空 |
| **4. 分析与仿真 CLI 动态分流** | `sim` 与 `profiler` 在真实 CLI 入口接入工作集动态估算与本机/远端自动分流 | 证明低配轻薄本自动分流远端、高配工作站原地执行、内存不足单 Worker 时安全拦截（不等同于全模型仿真精度验收） |
| **5. 平台原生内存硬限额接入** | 各平台进程管理器按内核真实能力接入 Job Limit 或 cgroup v2 `memory.max` | 证明 Windows / Linux / macOS 分别如实报告 `hard-limit` 或 `observed-only`，且超时进程排空与内存越界拦截各自独立通过验证 |

所有真机集成验收均须使用隔离的临时状态目录，严禁干扰集群现有线上任务。纯 CPU 单测、容器边界测试、NPU 实机执行与端到端模型性能收益必须分项独立记录；尚未取得真机实测证据的阶段一律保持“待验收”状态。

# 诊断日志与故障上报（Diagnostics & Fault Reporting）

[English](diagnostics-and-reporting.en.md) · [返回文档中心](README.md)

本文说明 MindIE Agent 如何记录本地结构化诊断日志、帮助 Agent 在遇到工具报错时快速定位阶段与原因，以及可选的“自动工具故障上报”是如何严格保护用户隐私并防止重复提交的。

- 遵循准则：[工程设计原则与演进准则](design-principles.md)
- 核心组件仓库：[`mindie-agent/diagnostics`](https://github.com/mindie-agent/diagnostics)（MindIE Agent 自身 DFX 与故障上报）· [`mindie-agent/debugger`](https://github.com/mindie-agent/debugger)（目标 NPU 负载故障分诊、三原语精度定位与 `ACLGraph` 调试）
- 版本与实测记录：[版本发布记录](README.md#版本记录与路线图)

---

## 1. 核心目标：让报错“说人话、可定位、不泄密”

当远端执行或知识整理遇到异常时，最糟糕的体验莫过于只返回一个笼统的 `Error` 或者把堆栈吞掉。MindIE Agent 诊断机制的目标非常简单：
- **让 Agent 一眼看懂发生了什么**：从一次报错返回中就能明确知道操作停在了哪个阶段、哪些前置动作已经完成、去哪个本地诊断编号查详情，从而决定是修复参数还是换一种排查方式。
- **不给日常任务添乱**：无需用户理解复杂的日志管线，不增加额外的收尾流程，不调用大模型去“分析日志”，也绝不自作主张重跑业务命令。

---

## 2. 统一贡献开关与日常使用体验

1. **本地有界结构化日志（默认开启）**：
   - 各组件在实际操作边界记录结构化本地日志。一旦工具执行失败，返回结果会附带一个随机诊断关联编号（Diagnostic ID）、静态错误类别和恢复提示，同时完整保留原始错误码与清理结果。
2. **知识共享与故障上报共用唯一贡献开关**：
   - 首次引导与配置入口同时说明两项出站行为：在已授权项目范围内贡献脱敏知识包，以及向产品仓库自动上报白名单内的工具故障元数据。**该开关默认关闭，仅在用户显式开启后生效**。
   - 当前安装配置目录中的 `mindie-consent.json` 是贡献授权的唯一权威来源。诊断上报配置文件保存目标仓库、日志根目录及对该授权文件的引用；故障记录、队列消费与最终外发均校验同一选择（`choice`）与授权修订号（`choice_revision`）。
   - **三态明确区分**：系统严格区分“配置已写入”、“后台 reporter 服务已运行”与“外部 GitHub Issue 已创建”三个状态。显式开启开关时，系统同步准备知识贡献配置与原生后台 reporter 服务，并分别返回两者的就绪状态；后台服务启动异常会直接报告并支持后续自愈。关闭开关后，两条出站链路立即停止发送，本地诊断日志与查询保持可用。
   - **升级不自动扩大授权**：已有安装中的 `disabled`、`later` 或 `read-only` 状态在升级后保持关闭；旧版仅针对知识贡献开启的 `contribute` 配置若缺少统一授权修订号，在升级后**不会**自动获得故障上报权限，需由用户通过统一贡献入口显式确认开启一次。
   - **复用已认证的 `gh` 通道**：自动上报复用安装时已验证的 GitHub CLI（`gh`）。插件打包的 `knowledge`、`remote-dev` 与后台 reporter 服务共享同一配置路径下的诊断状态；独立部署的 `remote-dev` 则沿用其显式配置的上报策略。

---

## 3. 模块职责划分

| 模块 / 角色 | 职责范围 |
| --- | --- |
| **宿主插件适配器**（`mindie-agent-cc` / `-codex` / `-kimi` / `-dsh`） | 记录原生入口、Hook、MCP 启动与协议层故障，提供清晰的配置开关与状态查询入口 |
| **业务运行时组件**（`knowledge` / `remote-dev`） | 在内部发生真实故障的边界记录阶段、版本、耗时、退出码与清理结果；严格区分“用户远端命令正常返回非零退出码”与“MindIE 工具自身缺陷” |
| **诊断组件**（`diagnostics`） | **仅负责 MindIE Agent 自身内部 DFX**：日志格式校验、严格字段白名单脱敏、本地磁盘滚动清理、故障指纹去重、有限重试预算控制与 GitHub Issue 自动提交 |
| **NPU 调试组件**（`debugger` / `mindie_debugger`） | **专门面向被调优的目标 NPU 业务负载**（`vllm-ascend`、`MindIE-SD`、CANN 算子）：提供确定性昇腾 NPU 日志分诊（`npu_fault_triage`）、通用三原语精度/内存踩踏定位（`precision`）与 `ACLGraph` 捕获/重放逐层 Dump 工具（`aclgraph`），与 Agent 自身 DFX 严格职责隔离 |
| **GitHub 仓库维护者** | 根据上报的结构化故障证据排查根因并发布修复版本 |

如果底层共享组件已经记录了某次错误，它会把诊断关联编号直接传给上层插件，避免同一故障在底层和外层被重复记录两次。

---

## 4. 隐私红线：什么能上报，什么绝对不上报？

公开提交的 GitHub Issue 完全由确定性程序从**白名单字段**拼装生成，全程不调用大模型：

- **允许包含的公开字段（仅限代码与执行元数据）**：
  - 组件名称、软件版本号或 Git Commit SHA、操作名称、执行阶段、静态错误类别/错误码、耗时、退出码和资源清理结果。公开稳定故障指纹用于去重；随机诊断关联编号和进程时钟仅保留在本地。
- **严禁进入公开 Issue 的隐私内容**：
  - **绝不包含**：用户执行的命令、命令参数、环境变量、终端原始 `stdout`/`stderr` 输出、自由文本异常消息、对话 Transcript、配置文件内容、密钥凭据、原生任务 ID、远端作业 ID、本机或远端文件路径、以及服务器 IP/主机名。
- **哪些情况不会触发自动提单？**
  - 参数传错、缺少配置、用户主动按了取消（Cancel/Interrupt）、功能未启用、权限不足、普通的网络断开或 SSH 认证失败、以及**用户自己的远端测试命令返回非零退出码或超时**，都属于正常业务反馈，绝不会当成产品 Bug 自动提 Issue。
  - 只有工具未捕获的内部异常、自有辅助子进程崩溃、协议损坏或安装包文件缺失，才会进入故障上报队列。

---

## 4.1 更新失败覆盖与上报资格

`diagnostics`（`v0.5.4`）为更新器提供统一的 `category="update"` 记录入口：根据异常类型、结构化错误码和保留的异常原因分类，不分析异常自由文本。模块缺失、包内容或协议异常属于产品故障；网络、凭据、权限、取消和本地前置条件问题保留本地可见。插件负责在失败边界调用该入口，不能仅写更新状态文件，也不能把更新失败全部设为 `reportable=False`。

四端插件（Codex `v0.1.13`、Claude Code `v0.1.10`、Kimi `v0.1.10` 和 DSH `v0.1.9`）均已接入此分类，覆盖组件继承子进程启动失败和更新子进程在写状态前崩溃的路径；可传递的内部诊断编号在外层复用，避免重复记录。各插件的安装基线锁定正式 `diagnostics v0.5.4`，并通过包管理器覆盖旧组件的间接诊断固定版本。

只读状态中的近期错误提供 `error_code` 和 `reporting_eligibility`：

| 资格状态 | 含义 |
| --- | --- |
| `local_only` | 已在本地记录，按错误分类或调用边界不进入自动上报 |
| `not_authorized_at_capture` | 记录时没有上报授权，以后开启也不回补 |
| `other_profile` | 记录属于其他配置档案，本档案不消费 |
| `consent_allowed` | 目前有上报资格，实际入队和投递结果仍须查看队列 |
| `consent_withdrawn` / `consent_unavailable` | 授权已撤回或暂时不可读，分别撤销投递或保留证据等待恢复 |

该视图只读取最多八个 16 KiB 日志尾部并返回最近五条失败，`truncated` 表示窗口不完整，不代表全量故障统计。服务心跳健康、诊断组件已升级、事件被记录、事件已入队和 GitHub 已确认发布是独立事实；只有队列的 `published` 回执及对应 Issue 才能证明外部投递成功。新版本不能重建旧插件从未记录的故障。

---

## 5. 自动去重与发送队列恢复（Loop Prevention）

为了防止同一个 Bug 重复建单，或因临时网络故障丢失待报故障：

1. **跨任务稳定指纹去重**：
   - 相同组件版本、操作、阶段、错误类别和内部代码栈帧会生成唯一的稳定故障指纹（Fingerprint）。无论切换了多少个会话或宿主客户端，同一个已知故障都会通过 GitHub 只读查重关联到已有 Issue，不会重复创建 Issue。
2. **有界请求与可恢复的发送队列**：
   - 每个处理周期受统一请求超时约束；当网络或 GitHub 认证暂时不可用时，队列保留待发记录、显式记录当前错误并延后重试，不会因瞬时只读查询失败而丢弃待报故障。
   - 仅当提交请求可能已到达 GitHub 但未收到响应时，该记录才标记为 `unknown`，并在后续最多 **2 次有界外发对账重试（bounded 2-attempt outbound reconciliation）** 中优先通过只读查询核对远端是否已创建成功，避免盲目重发；子进程尚未启动或被远端明确拒绝的请求不会误记为 `unknown`。
   - 若 GitHub 已确认创建 Issue 但本地回执落盘失败，系统会单独报告本地写入错误而不反转已完成的外部结果。用户关闭贡献开关后，未发出的队列项立即停止外发；重新开启后仅处理新授权修订下产生的事件。
3. **上报器自身错误不递归提单**：
   - 上报器在访问 GitHub 时遇到的错误仅记录在本地状态中，不会触发递归提单。

---

## 6. 本地日志轮转与容量保护

- **有界磁盘占用**：本地日志严格限制单条记录与单个分片文件大小，并在日常周期性维护时自动清理过期分片（即使未开启远程上报也会自动清理旧日志）。
- **保护活跃读写者**：日志轮转时会自动保护正在写入的进程和已登记的读取游标，绝不覆盖尚未读完的分片。
- **不截断业务输出**：在 `remote-dev` 中，用户远端命令产生的 `stdout`/`stderr` 属于正式的作业输出产物（Artifacts），由作业生命周期完整保留，绝不会被当成诊断日志截断。

---

## 7. 确定性昇腾 NPU 与 CANN 故障分诊（`mindie_debugger.npu_fault_triage`）

为保持职责唯一性，面向**被调优目标 NPU 业务负载**的日志分诊与精度调试已独立剥离至 [`mindie-agent/debugger`](https://github.com/mindie-agent/debugger)（`mindie-debugger` / `mindie_debugger`）。其中内置吸收自 [CANNBot Skills](https://gitcode.com/cann/cannbot-skills) 的**零模型依赖、确定性昇腾 NPU 运行时故障分诊器（`mindie_debugger.npu_fault_triage.triage_npu_fault`）**，帮助 Agent 从容器或主机的报错日志中直接识别根因分类、提取标准错误码并给出对应的 CANN 原生取证工具命令：

| 故障分类（`category`） | 典型 CANN / 驱动错误码与特征签名 | 关联的 CANN 确定性取证与恢复指引 |
| --- | --- | --- |
| **`aicore_exception`** | `EZ9999`、`507015`、`Aicore Error`、`BIU`/`MTE2`/`MTE3`/`VEC`/`CUBE` 异常位图、非法访存或除零越界 | 使用 `asys collect` 收集一键异常快照，调用 `msaicerr -i <dump_dir>` 解码故障寄存器，并结合 `npu-objdump` 映射出错 PC 指令与 UB/GM 32B 对齐边界 |
| **`ascendc_sync_hazard`** | `SetFlag`/`WaitFlag` 配对失衡、`CrossCoreWaitFlag` 跨核等待挂死、分支内不等价流水屏障导致的 Stream 挂死（`507018`） | 静态执行 `ascendc-sync-audit` 核查分支对称性、循环跨拍双缓冲释放与 `HardEvent`（`MTE2_V` / `V_MTE3` / `MTE1_M` / `M_FIX`）配对完整性 |
| **`hccl_comm_fault`** | `EI0002`（链路断开）、`EI0004`（拓扑不一致）、`EI0006` / `Notify Wait Timeout`、`HCCL_BUFFSIZE` 溢出或 Idle-DP 空批挂死 | 开启 `HCCL_ENTRY_LOG_ENABLE=1`，使用 `hccn_tool` / `npu-smi info -t topo` 核查 RoCE/HCCS/SIO 链路，或用 `HVM` 独立验证集合通信算子 |
| **`device_oom`** | `EL0004`、`E80000`、`NPU out of memory`、`ACL_ERROR_RT_MEMORY_ALLOCATION` | 核查各 Rank 的 Workspace 峰值增量（`max_rank_workspace_delta_bytes`）、KV Cache 预分配比例及 GE 图内存复用配置 |
| **`npugraph_compile_or_capture`** | `torch.npugraph_ex` Guard 失效、静态图 Capture 期间发生 Host-Device 同步或动态 Shape 符号推导失败 | 启用 `npugraph_ex` DFX 二分排查（Compile/Runtime/Perf Triage），固定静态 Bucket Padded Shape 并剥离 Capture 区间的动态流分配 |
| **`device_hardware_or_driver`** | `507035`、ECC 多比特翻转、设备掉卡或驱动握手异常 | 执行 `asys check` 与 `msnpureport` 导出设备侧固件黑匣子日志，并通过 `coordinator` 隔离故障物理卡/Die |
| **`vllm_ascend_aclgraph_capture_failure`** | `207008`、`EL0009`、`ACL_ERROR_RT_STREAM_NO_CB_REG`、`update_stream_limit`、`aclmdlRIExecuteAsync` 或 `ACLGraph` 捕获期间触发动态控制流/D2H 同步 | 检查 `additional_config.torchair_graph_config` / `cudagraph_capture_sizes`，剥离图捕获区间内的 `.item()` / `.cpu()` 同步，或回退至 `--enforce-eager` / `PIECEWISE` 图模式 |
| **`vllm_ascend_idle_dp_collective_hang`** | 多 DP + EP/TP 混合并行下，空闲 DP Rank（`active_batch == 0`）跳过 Dummy Forward 或 `GDN`/`KDA` 状态对齐，引发 `HCCL_E_WAIT_TIMEOUT` | 确保所有 DP Rank 同步进入 `coordinate_batch_across_dp` 空批 Dummy Forward 路径，并开启 `GDN`/`KDA` 零填充 Workspace 对齐 |
| **`msmodelslim_quant_weight_or_scale_mismatch`** | `quant_model_description.json` 键缺失、`deq_scale`/`quant_bias`/`input_scale` 形状或精度不匹配、`W8A8_DYNAMIC` 与静态配置混用、`MXFP8`/`MXFP4` `group_size != 32` | 核对 `--quantization ascend` 与 `quant_model_description.json` 格式契约，校准异常值抑制（SmoothQuant/QuaRot）并将敏感层回退为 `FLOAT`（BF16/FP16） |
| **`numerical_nan_inf_or_determinism_drift`** | `msprobe` / `PrecisionDebugger` 余弦相似度跌落、`NaN`/`Inf` 溢出、FP16 累加器下溢或跨 Run 归约非确定性漂移 | 使用 `msprobe` 逐层比对定位首个精度发散算子，开启 `LCCL_DETERMINISTIC=1`、`HCCL_DETERMINISTIC=true`、`CLOSE_MATMUL_K_SHIFT=1` 或 `batch_invariance` 确定性配置 |
| **`mooncake_or_kv_pool_transfer_fault`** | `MooncakeConnector` / `LMCacheConnector` / `AscendStoreConnector` KV 传输超时、`KVCache register_memory` 失败、或非对称 P/D TP 切分拓扑失配 | 校验 `HCCL_SOCKET_IFNAME` / RoCE 网卡可达性、RDMA 内存注册上限及非对称 TP 整除约束（`tp_p >= tp_d` 且 `tp_p % tp_d == 0`） |
| **`custom_op_abi_or_symbol_shadowing`** | `161001`（`ACLNN_ERR_PARAM_NULLPTR`）、`561000`/`561103`、`_C_ascend`/`libascend_kernels.so` 未定义符号、`opapi_math` 遮蔽 `libopapi.so`、缺失 `Meta` 算子注册、或 `FIA` `errcode 264`（`tiling offset out of range`） | 用 `ldd`/`nm -D` 核查自定义算子 ABI 与 `libopapi.so` 符号绑定；在 `TORCH_LIBRARY_IMPL` 同步注册 `PrivateUse1` 与 `Meta` 分支；MTP（`step >= 1`）下将 `FIA` `actual_seq_lengths_kv` 计数域与张量维度（3D BSH/BSND vs 4D BNSD）严格对齐 |
| **`multithread_npu_context_or_rogue_device0`** | `107003`（`ACL_ERROR_RT_CONTEXT_NULL`）、`ThreadPoolExecutor`/ZMQ 异步回调线程丢失 NPU 上下文、或多卡 Worker 异常占用物理 `device 0` 显存 | 在每个后台工作线程显式调用 `torch.npu.set_device(device_id)`；使用 `perf probe -x libascendcl.so 'aclrtSetDevice deviceId=%x0:s32'` 零侵入追踪异常 `device 0` 上下文创建栈 |
| **`enginecore_shm_or_zmq_frame_corruption`** | `vllm` `EngineCore` `shm_broadcast` / `MessageQueue` 环形缓冲区帧损坏、`multiproc_executor` `EOFError`/`UnpicklingError`，表现为 `/v1/models` 返回 200 但 `/v1/chat/completions` 挂死 | 检查 `EngineCore` 进程存活与 ZMQ `DEALER/ROUTER` 多段消息帧完整性，排查超大 `SchedulerOutput` 分块截断或 Worker 异常退出 |

此外，在任务启动前、集群探针与评测阶段，`coordinator`（[`env_manager.py`](https://github.com/mindie-agent/coordinator)、[`fleet_probe.py`](https://github.com/mindie-agent/coordinator) 与 [`checkpoint_preflight.py`](https://github.com/mindie-agent/coordinator)）、`npu-top`（[`probe.py`](https://github.com/mindie-agent/npu-top)）和 `mindie-bench`（[`cann_sentry_eval.py`](https://github.com/mindie-agent/mindie-bench)）配套提供前置防踩坑门禁：
- **运行时环境与硬件特性矩阵前置校验**：自动拦截 `ACLGraph` 与 `ASCEND_LAUNCH_BLOCKING=1` 冲突、自定义算子 `op_api/lib` 路径缺失、多机 `HCCL_SOCKET_IFNAME`/`GLOO_SOCKET_IFNAME` 失配、缺失 `expandable_segments:True` 导致的内存碎片风险、跨代 SoC（`310P` / `910B` A2 / `910_93` A3 / `950` A5）不支持特性误用、以及 NUMA/IRQ 绑核争抢。
- **零 NPU 权重 Safetensors 头部与量化契约快检（`inspect_safetensors_checkpoint`）**：在申请 NPU 租约前，仅读取 `.safetensors` 前 8 字节头部长度与 JSON 元数据（`< 100ms`），自动校验分片完整性、文件截断、各层 Dtype 字节分布，拦截“`config.json` 声明 W8A8/W4A8 量化但 `routed_expert` 权重仍为 BF16/F16”的隐性显存暴涨，以及 `head_dim` 未对齐昇腾 32B UB 边界风险。
- **Linux `/proc/<pid>` 磁盘 I/O `D` 状态（`wchan`）与真 NPU 挂死区分**：`fleet_probe` 与 `npu-top` 同步采集 NPU 进程的 `/proc/<pid>/status`（`State`）与 `/proc/<pid>/wchan`，当 AICore 利用率为 `0%` 但进程处于 `D` 态（如 `lock_page_killable` / `nfs_*` / `folio_wait*`）时显式标记 `disk_io_wait=True`，防止将冷存储/NFS 权重读取误判为 HCCL 通信死锁并误杀进程。
- **推理基准测试有效性审计（`audit_inference_benchmark_validity`）**：自动识别并拦截未剔除 Warmup/图编译耗时、使用 `--load-format dummy` 或未校准量化权重报告精度、投机解码（MTP/EAGLE/DSpark）缺失 `acceptance_rate` / `mean_accepted_tokens` 折算、`output_len < 32` 冒充长稳态 TPOT、PD 分离静默回退本地重算（`transferred_kv_bytes == 0`）、`--enforce-eager` 与 `cudagraph_mode` 冲突或 C++ 算子重编后未清理 `.torchair_cache`、以及跨 VPN/广域网运行压测客户端导致的网络 RTT 失真。

---

## 8. 通用三原语 NPU 精度、内存踩踏与 `ACLGraph` 调试工具集（`mindie_debugger`）

针对模型长上下文发散、多步投机（MTP/EAGLE）接受率跌落、多 DP 空批状态串味、自定义算子累加漂移以及 `vllm-ascend` / `MindIE-SD` 默认图引擎 **`ACLGraph`（`torch.npu.NPUGraph`）** 的捕获/重放发散，`debugger`（`mindie_debugger.precision` 与 `mindie_debugger.aclgraph`）提供**零业务侵入、仅依赖公开 PyTorch 接口**的定位工具集：

| 故障现象与日志签名（Symptom） | 推荐原语（Primitive） | 核心调用方式与判定输出 |
| --- | --- | --- |
| **跨步/跨 Rank 状态修改、共享缓冲覆写、Workspace 切片踩踏**（如 MTP `step 0` 的 `seq_lens`/`cum_query_lens` 在构建 `step 1` 后被原地覆盖、Idle DP `_dummy_run` 污染 `GDN`/`KDA`/`Mamba` 状态缓存、变长 Chunk workspace 越界踩踏） | **`npu-watch`**（`StorageGraph`、`MemoryWatchpoint`、`WatchRingBuffer`） | `StorageGraph(a=t0, b=t1).shares_storage("a", "b")` / `.overlapping_views()` 检测底层 `untyped_storage` 别名与字节区间重叠；`with MemoryWatchpoint(module, must_preserve={"state": t}) as wp:` 在首个修改保护张量的算子/子模块边界精确定位违规写操作（`wp.report()["first_violation"]`）；`WatchRingBuffer` 提供 `NPUGraph` 捕获安全的设备侧零同步环形快照与首个 `NaN`/`Inf` 锁存 |
| **单算子/归约/量化数值漂移或跨次运行非确定性抖动**（如 BF16/FP16 均值方差累加 `max_abs_err` 超标、W8A8/MXFP8 量化固损 vs 算子核实现 Bug、原子归约跨次抖动） | **`call-repro`**（`capture_call`、`replay_call`、`FakeQuantContract`） | `cap = capture_call(fn_or_mod, *args, **kwargs)` 保存调用前后完整 `StorageGraph` 快照；`replay_call(cap, fn_or_mod, mode="reference_check", reference_atol=..., reference_rtol=...)` 自动提升浮点张量与 `TorchFunctionMode` 归约至 FP32 参照比对，或通过 `repeat=N, det_lock=True` 与 `FakeQuantContract` 区分“非确定性原子抖动 (`nondeterministic_jitter`)”、“量化固损 (`quantization_inherent_loss`)”与“算子实现缺陷 (`real_numerical_bug`)” |
| **多模块/端到端逐层精度发散（Eager vs `NPUGraph`、多卡 TP/EP/CP vs 单卡、新旧分支对比）** | **`lockstep-diff`**（`LockstepDiffer`、`slim_moe_checkpoint`） | `LockstepDiffer(ref_mod, cand_mod).compare(*args, **kwargs)` 沿模块树锁定**首个超过 ULP/噪声底限的发散层**（`first_divergent_layer`）及发散类型（`nonfinite_overflow` / `storage_stomp` / `layout_or_view_bug` / `accumulation_drift`）；配合 `slim_moe_checkpoint` 将超大 MoE 权重裁剪为单机可跑的确定性小权重进行秒级复现 |
| **`ACLGraph`（`torch.npu.NPUGraph`）图内中间层逐 Replay 步无同步 Dump、捕获阻塞定位与静态地址追踪** | **`aclgraph`**（`ACLGraphDumper`、`ACLGraphCaptureGuard`、`ACLGraphAddressTracker`） | 解决常规 PyTorch Hook 在 `g.replay()` 期间不触发、或调 `.cpu()` 导致 `207008` 捕获失败的难题：`ACLGraphDumper` 在 `torch.npu.graph(g)` 捕获期间将零分配设备侧 D2D 拷贝（`torch.where(..., out=slot_buf)`）烘焙进静态图，每次 `g.replay()` 配合 `dumper.advance_step()` 自动落盘各层中间张量，并通过 `dumper.compare_with_eager(eager_fn, *args, step_index=k)` 直接锁定图中首个发散层；`ACLGraphCaptureGuard` 精确定位捕获区内的 `.item()`/`.tolist()`/`bool(tensor)`/`.cpu()` 违规代码行；`ACLGraphAddressTracker` 拦截静态输入缓冲 `data_ptr()` 漂移与 `slot_mapping` Padded 尾部未填 `-1` 导致的 KV Cache 脏写 |

### 底层依赖边界说明（公开接口 vs 扩展探测）

- **业务模型层（`vllm-ascend` / `MindIE-SD`）零定制接口**：无需业务代码预埋任何自定义 Hook 或专有协议，完全通过标准 `torch.nn.Module` 公开接口（`register_forward_pre_hook(..., with_kwargs=True)`、`register_forward_hook(..., with_kwargs=True)`、`named_modules()`、`named_parameters()`、`named_buffers()`）及标准 HuggingFace `config.json` / `.safetensors` 文件工作。
- **PyTorch 公开运行时接口**：存储拓扑与别名检测基于 `tensor.untyped_storage()`、`storage.data_ptr()`（0 字节空存储回退至对象标识）、`storage.nbytes()`、`tensor.as_strided()`、`tensor.view(torch.uint8)`；FP32 参照重放基于公开的 `torch.overrides.TorchFunctionMode` 与 `torch.autocast`；设备侧异步事件与确定性控制基于 `torch.npu.current_stream()`、`torch.npu.Event()` 与 `torch.use_deterministic_algorithms()`。
- **仅有的两处框架内部/扩展触点**：(1) 在 `FakeQuant` 与 `FP32` 参照重放期间，为避免触发 `nn.Module.__setattr__` 参数类型拦截或重复注册 Hook，在 `try...finally` 块内对 `submodule._parameters` / `submodule._buffers` 字典执行临时原地替换并严格恢复；(2) 通过 `getattr(torch_npu, "get_npu_format", None)` 可选探测昇腾私有 `ACL_FORMAT_FRACTAL_NZ (29)` 格式，避免对非标准排布张量直接切片字节视图。

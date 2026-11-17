> **Historical Archive (Non-Gate Snapshot)** — Preserved from baseline commit `02a1d371`.
> Original path: `docs/operator-workflow.md` · Excluded from active release/version gates.
> Retained for historical design provenance; do not treat point-in-time plans or wave checklists as live contracts.
> Current living specification: [`docs/architecture.md`](../architecture.md).

# 从 MindIE 发起算子开发

在会话中通过 `/mindie-agent`（OpenAI Codex 中亦可使用 `$mindie-agent`）描述目标算子、参考源码与远端执行环境后，当前宿主 Agent 会读取工作区已安装的 `ascend-op-workflow` 技能，并直接调用 MindIE 原生工具链完成 Shape/Workload 推导、AscendC 代码生成、有界迭代优化与评测产物回收：

```text
/mindie-agent 为指定算子准备 workload，生成 AscendC 并做有界优化。
使用指定环境；默认由 Codex 执行，沿用已有任务与预算。
```

## 安装与执行

- **独立外部依赖解耦**：[独立 workflow 仓库（`operator-shape-derivation`）](https://github.com/grandolantow/operator-shape-derivation) 负责维护技能定义、安装脚本与归档 CLI；`CANNBot` 则作为独立的外部代码生成与进化引擎按需接入。Shape/Workload 推导阶段可单独安装并先行运行；进入实际算子生成与迭代优化阶段时，若检测到本地已有 `CANNBot` 检出目录则直接复用，缺失时向用户询问是否调用 `CANNBot` 原生安装入口完成安装或指定已有路径。若用户暂不安装 `CANNBot`，Agent 会继续完成可独立运行的 Shape/Workload 准备工作，并如实说明剩余外部依赖缺口。
- **默认执行路径与模型开销提示**：算子生成与优化默认由 Codex 读取 `CANNBot` 原始指引并驱动原生工具执行，Claude 仅作为显式指定时的可选后端——默认路径不依赖 Claude CLI、Node.js、Claude 会话或专属 Hook。任务启动前会简短提示用户：算子生成与多轮进化优化的 Token 消耗较高，日常迭代建议使用常规代码模型配合中等 `effort`，仅在复杂分块设计或关键精度排障时按需局部上调；模型与 `effort` 完全遵循当前任务选择，不硬编码历史实跑配置。
- **权威参考文档与发现边界**：详细安装步骤、`CANNBot` 资源目录布局、阶段交接协议与中断恢复命令均以独立 workflow 仓库内的 `docs/INSTALL.md` 与 `skills/ascend-op-workflow/references/mindie.md` 为准。该技能需在当前任务工作区中可被宿主发现或由用户显式引用；MindIE MCP 服务本身不会静默下载或向远端环境自动注入外部技能。

## 职责与结果

- **Workflow 编排层职责**：统一管理父任务生命周期、Workload 定义、验收契约、冻结的初始正确生成基线 `G`、总预算以及最终归档验收。其中 `prepare` 子命令仅负责准备交接上下文，实际的算子生成与性能优化均由 Agent 显式发起工具调用完成。
- **CANNBot 零侵入复用**：`CANNBot` 仓库保持原状，负责提供原始生成流程、唯一候选进化世界树（World Tree）、候选谱系记录与算子评测器；所有跨工具衔接逻辑均收敛在独立 workflow 适配层内，不修改或双向同步 `CANNBot` 内部代码副本。
- **MindIE 原生远端执行层职责**：由 `remote-dev` 与 `coordinator` 管理真实的远端容器作业、日志输出、NPU 租约与任务取消。workflow 的 `execution-links.json` 仅记录 `preparation`、真实远端 `job`、进化工作目录与归档 `result` 之间的关联映射；Claude Session 字段仅在显式启用 Claude 选配路径时使用。
- **冻结基线 `G` 与诚实交付语义**：一旦产出首个通过全量用例精度校验的版本，立即将其冻结为生成基线 `G` 并执行实测性能采样。默认 `auto` 模式下，若 `G` 已达到生成性能目标则直接交付 `G`；若性能有效但尚未达标，则在已授权预算内进入轻量优化阶段（显式指定 `full` 模式时执行持续多轮优化）。最终归档统一回收算子源码、全量 Case 明细、原始评测证据、`G/O` 性能对比与一键复现命令，并将**精度通过**、**性能测量有效**与**目标加速比达成**三项状态独立分列——若最终未达目标加速比，如实保留 `TARGET_UNMET` 状态，绝不伪造通过。

会话重连时先查询原远端 `job` 与本地 Checkpoint，严格沿用原父任务、已冻结基线 `G`、既有进化世界树与剩余预算继续推进，绝不重复提交作业或重置初始化状态；取消任务时直接调用执行层针对当前作业的原生取消接口，不波及同机其他在途任务。

本主仓仅维护上述入口约定与跨组件职责边界说明，不承载 workflow Skill 实现、安装器、启动脚本、专用 MCP 服务、容器镜像配置或实验产物数据。各原生宿主插件直接复用现有的工作区技能发现机制，仅在真实端到端验收暴露出具体路由缺口时才作最小必要调整。

## 验收边界

- **2026-10-31 独立 Workflow 全链路实测（FP32 `Add`）**：通过独立 workflow 仓库发起全新 FP32 `Add` 算子任务，经由 MindIE 原生远端工具完成初始生成及 1 轮单候选优化。初始基线 `G` 与优化候选 `O` 均通过全量 10 个测试形状的直调与 PyTorch 精度比对，且首个全量正确版本 `G` 在性能采样前即完成冻结。实测初始生成几何均值 `GM(R/G)=0.260728362`（未达生成目标阈值；随 workflow 发布的适配器保留原生分数下限报错语义，仅对已知阈值做窄范围兼容而不篡改真实得分，顺利跑通预约、执行与原生 `refine`/session 衔接）；优化后几何均值 `GM(G/O)=0.959872936×`（未达优化目标，按规则保留 `G`）。注：该耗时口径为包含常规调用提交间隙的设备流事件跨度，而非剥离了调度间隙的纯单 Kernel 硬件时长。
- **租约回收与零侵入核验**：父任务归档校验通过，原生 `coordinator` 的 NPU 租约申请、续期与释放全流程正常，远端开发作业及其全部后代进程均干净退出。全过程未修改 MindIE 运行时组件与 `CANNBot` 源码，所需衔接适配已通过独立 workflow 仓库的 [PR #4](https://github.com/grandolantow/operator-shape-derivation/pull/4) 合入 `main` 分支。任务启动前须确认 MindIE 原生远端工具就绪；实测期间的环境路径与入口对齐操作仅记入当次环境台账，不作为通用安装步骤。
- **2026-10-28 默认 Codex `SDPA` 历史实测**：完成全新 Workload 推导、初始代码生成、1 轮单候选优化、最终复测与父任务归档，基线 `G` 与候选 `O` 均通过全部 50 个测试形状的精度校验及 24 项双流一致性检查；实测 `G/O=1.017841574×`（未达 `1.5×` 目标，且采样期间未锁定整机物理独占）。此外，在独立的原生 Codex CLI 新会话中验证了技能入口发现、`CANNBot` 缺失时的交互询问，以及拒绝安装 `CANNBot` 后继续独立完成 Workload 准备的降级闭环。
- **已知上游限制与未覆盖边界**：历史原始 `CANNBot` 校验器会直接拒绝 `best_score<1`，且其 HTML 报告生成器在遇到 `hw_params=null` 时会报错退出——前者已由 workflow 适配层提供窄兼容，后者未在本次复测中重跑；HTML 报告始终定位为可选展示产物，生成失败时直接交付 Markdown、JSON 与原始评测证据并单独标注 HTML 状态，且“父任务归档校验通过”不代表性能指标达标或所有上游原生门禁全绿。此外，短耗时 CPU 对照作业已验证双客户端重连同一原 `job`、取消后父子进程树干净回收且不干扰并行作业；但强制断网后的在途优化恢复、Claude 真实付费 API 路径与更多宿主的跨端兼容性尚未实测，当次可选 `release updater` 亦仍提示 `release_selection` 告警——单次环境实跑通过不替代对所有新装环境或 CANN SDK 版本组合的普适兼容性承诺。

# MindIE Agent `0.1.0` 真实任务系统性价值评测报告（Product Value Benchmark Report）

> **证据更正说明（2026-10-24）**：本文为旧判分器下的历史结果记录。由于其中六类任务的旧判分器可被无功能源码通过，且相关历史 Trial 尚未用修复后的行为判分器重判，本文中的成功率、耗时、Token 节省及组件因果收益结论**暂停作为当前产品验收依据**；同时，`G4` 策略 pilot 的合成续跑/代理指标、组件夹具、确定性回放与仿真推演亦不能外推为真实 NPU 性能验收。文中原始表格与审计清单原样保留以供追溯；具体修复范围与验证结果见 **[并行架构评审与修复记录](../../architecture-review-20261024.md)**。

本文完整记录 MindIE Agent 首个正式里程碑版本 **`0.1.0`** 在真实大模型与真实昇腾工程任务上的系统性收益评测结果。

本次评测围绕核心问题——**“在真实昇腾推理/算子开发与排障任务上，MindIE Agent 的全部 7 大组件与 G1–G4 能力梯度究竟带来了什么具体收益？”**——采用两个主力生产模型/宿主配置进行了端到端实测对比：
1. **`codex + gpt-6.1-sol (xhigh)`**：OpenAI Codex CLI（`0.153.4`）+ `home/codex/gpt-6.1-sol`（`reasoning_effort = "xhigh"`，C6 蒸馏模型 `home/codex/gpt-5.6-luna`）；
2. **`dsh + deepseek-flash (max)`**：DeepSeek Harness（`dsh`）+ `deepseek-flash`（`reasoning_effort = "max"`）。

评测覆盖 **18 个真实工程任务（对应 `tasks/zh-vague/` 下 20 个 `task.toml` 定义，含 3 组 `Seed -> Eval` 配对任务、L2 本地源码仓任务与 L3 实机昇腾 NPU 容器任务，共 109 场主评测端到端 Trial 及 55 场附加/重试记录）**、**全部 7 大共享组件（`remote-dev`、`knowledge`、`profiler`、`sim`、`diagnostics`、`coordinator`、`npu-top`）**、**`G0 → G1 → G2 → G3 → G4` 五级消融梯度**，以及 **macOS / Windows WSL2 (Linux x86_64) / Windows 11 PowerShell 三大平台**的全量回归验证。

- 📦 **机器可读逐 Trial 审计清单（109 场主评测 Trial + 55 场附加/重试原始记录）**：[`docs/releases/0.1.0/agent-trials-109.json`](./agent-trials-109.json)
- 📦 **组件微基准与全量评测汇总清单**：[`docs/releases/0.1.0/value-results.json`](./value-results.json)

---

## 一、实验设计：五级消融梯度（`G0–G4`）与组件覆盖矩阵

| 消融组 | 启用能力与组件边界 | 核心验证假设（回答什么收益问题） |
| :---: | :--- | :--- |
| **`G0`** | **原生裸宿主基线（Bare Host Baseline）**<br>无 MindIE MCP 工具、无昇腾领域知识库、无随包 Skills | 基线对照：纯靠大模型自身先验知识与原生 Shell/文件工具在昇腾复杂任务上的解出率与耗时底线 |
| **`G1`** | **`G0` + `remote-dev`（+ L3 实机 `coordinator` / `npu-top` / `diagnostics`）**<br>结构化远端容器执行、补丁编辑、后台作业流式控制与 NPU 租约仲裁 | 验证 **`remote-dev` 远端开发底座**与**多 Agent 资源协调**相比手写 `ssh`/本地盲改在交付耗时、轮次与稳定性上的收益 |
| **`G2`** | **`G1` + `knowledge`（L1–L4 渐进式披露检索 `mode="reuse"`）+ 专项组件（`profiler` / `sim` / `diagnostics` / `npu-top` / `coordinator`）+ 随包 Skills**<br>按需调用 `knowledge_query` / `knowledge_explain` 及专业分析建模工具 | 验证 **7 大昇腾公共知识库**与 **5 大专业分析/观测组件**在复杂排障、性能瓶颈归因、Roofline 边界筛查与多卡级联分诊上的解出率跃升与提速收益 |
| **`G3`** | **`G2` + 跨任务经验沉淀飞轮（`Stop` Hook 采集 $\to$ Gitleaks 双层脱敏 $\to$ C6 自动蒸馏 $\to$ 本地 Git 发布 $\to$ 下游任务检索复用）** | 验证 **零人工干预的经验飞轮**：当面对公共语料未覆盖的新型黑盒故障时，前置任务（Seed）自动沉淀的 L2 SOP 能否让同类下游任务（Eval）从失败逆转为一次通过并大幅缩短耗时 |
| **`G4`** | **`G2` + 开放式无偏探索（`mode="reuse" -> mode="explore"` 切换 + L4 变异因子图谱 + 留一法消融验证）** | 验证 **反先验锚定与算法创新能力（RSI）**：在需要多因子协同创新的算子/模型融合任务中，抑制 L4 既有方案锚定、仅暴露 L1–L3 硬件与编译刚性约束与变异因子图谱，能否突破 `G0`/`G2` 0% 解出率天花板 |

---

## 二、核心结论总览（Executive Summary）

### 1. 四大核心评测维度的量化收益汇总

| 评测维度 | 任务规模与层级 | `codex + gpt-6.1-sol (xhigh)` 核心实测收益 | `dsh + deepseek-flash (max)` 核心实测收益 |
| :--- | :--- | :--- | :--- |
| **① 专项组件真实 Agent 任务**<br>（`profiler` · `sim` · `diagnostics` · `npu-top` + `coordinator`） | 4 个真实工程任务 × `G0/G2`<br>（共 `16` 场 Trial） | • **解出率从 `75% (3/4)` 提升至 `100% (4/4)`**（`profiler` 任务从 `0.0 -> 1.0`）<br>• **4 任务总交付耗时缩短 `-17.1%`**（`1,389.7s -> 1,151.7s`），末次编辑缩短 **`-19.5%`**<br>• **输出 Token 减少 `-25.2%`**（`57,538 -> 43,046`），组件真实调用率 **`100% (4/4)`** | • **解出率从 `75% (3/4)` 提升至 `100% (4/4)`**（`profiler` 任务从 `0.0 -> 1.0`）<br>• **4 任务总交付耗时缩短 `-33.8%`**（`1,165.3s -> 772.0s`，节省 `393.3s`），末次编辑缩短 **`-39.9%`**<br>• **输出 Token 减少 `-34.1%`**（`196,486 -> 129,536`），最高单任务提速 **`2.08x`** |
| **② 远端开发与渐进式检索 (`G0 -> G1 -> G2`)**<br>（`remote-dev` + `knowledge` + L3 实机 NPU） | 6 个 L2 任务 + 3 个 L3 实机昇腾 NPU 任务 | • **L2 复杂排障**：`dspark-mrv2` 从 `G0` `552.1s`（22 轮）降至 `G1` **`267.6s`（15 轮，提速 `2.06x`）**；`sfa-mtp` 从 `G0` `146.8s` 降至 `G1` **`74.4s`（`1.97x`）** 再降至 `G2` **`63.4s`（`2.32x`）**<br>• **L3 实机 NPU（`Ascend950DT`）**：`l3-dspark-mrv2` 从 `G0` `515.8s` 降至 `G2` **`465.6s`（-9.7%）**；`l3-mrv2-dsa` 从 `G0` `574.7s`（25 轮）降至 `G2` **`548.0s`（21 轮，轮次减少 `-16.0%`）** | • **L2 复杂排障**：`mrv2-dsa` 实现阶梯式提速 **`G0` `318.5s` $\to$ `G1` `281.2s` $\to$ `G2` `214.2s`（交付提速 `1.49x`，首次修改 `247.3s -> 113.6s` 提速 `2.18x`，末次修改 `287.7s -> 136.4s` 提速 `2.11x`）**；`k3-idle-dp` 在 `G2` 降至 **`264.4s`**<br>• **L3 实机 NPU**：`l3-dspark-mrv2` 从 `G0` `655.7s` 降至 `G1` **`341.7s`（提速 `1.92x`）**；`l3-mrv2-dsa` 从 `G0` `457.5s` 降至 `G1` **`294.6s`（提速 `1.55x`）** |
| **③ 跨任务经验沉淀飞轮 (`G3`)**<br>（`Seed -> Capture -> C6 Distill -> Eval`） | 3 组同族配对迁移任务（2 组 L2 + 1 组 L3 实机 NPU 黑盒 `.so` 任务） | • **L2 `cpu-rope-32` 同族迁移任务**：`G0`/`G1`/`G2` 各 1 轮均未通过（合计 `0/3`）；接入 `G3` 飞轮后，Eval 命中前置 Seed（`rotary_dim=64`）沉淀的 `unit-rope-cache-explicit-rotary-dimension`，**仅用 `9` 次调用（`211.8s`）一次通过（`0/3 -> 1/1`）**<br>• **L3 实机 NPU `rope-rotary-dim-32`（剥离 `.cpp` 源码的黑盒 `.so`）**：`G0`/`G1`/`G2` 各 1 轮均未通过（合计 `0/3`）；`G3` Eval 命中 Seed 蒸馏入库的 `unit-rotary-dim-cache-selection`，**在实机 NPU 上 `15` 次调用（`270.8s`）一次通过（`0/3 -> 1/1`）**<br>• **L2 `sfa-mtp`**：`G3` Eval 前台耗时 **`68.4s`**（含后台采集总耗时 `82.4s`），较 `G0`（`146.8s`）**前台提速 `2.15x`（总交付提速 `1.78x`）** | • **L2 `cpu-rope-32`**：DSH 在 `G0`/`G1`/`G2`/`G3` 均通过；`G3` Eval 命中前置 Seed 沉淀的知识单元后，交付耗时从 `G0` `214.0s`（46 轮）降至 **`191.4s`（v1 净室批次仅 `111.5s` / 19 轮，提速 `1.92x`）**<br>• **L2 `sfa-mtp`**：Seed（`152.2s`）与 Eval（`148.7s`）`100%` 闭环通过<br>• **L3 实机 NPU `rope-rotary-dim-32`**：`G3` Eval 耗时 **`383.2s`**，较 `G0`（`432.9s`）缩短 **`-11.5%`**、较 `G2`（`492.3s`）缩短 **`-22.2%`** |
| **④ 受控因子图谱引导的算子/模型融合探索 (`G4` RSI)**<br>（`mode="reuse" -> mode="explore"` + 留一法消融） | 2 类问题族 × L2/L3（4 个任务）× `G0/G2/G4`<br>（共 `24` 场 Trial，`knowledge_gradient="near_exact"`） | • **`G0` 解出率 `0/4`（`0%`）**<br>• **`G2` 解出率 `0/4`（`0%`）**<br>• **`G4` 解出率 `4/4`（`100%`）**：4 个任务全部完成 `reuse (1..2 次) -> explore (1 次)` 状态切换与留一法消融台账验证 | • **`G0` 解出率 `0/4`（`0%`）**<br>• **`G2` 解出率 `0/4`（`0%`）**<br>• **`G4` 解出率 `4/4`（`100%`）**：4 个任务全部完成 `reuse (2..3 次) -> explore (1..2 次)` 状态切换并一次通过实机 NPU 与留一法门禁 |

### 2. 评测边界、模型网关映射与统计说明（Evaluation Scope, Model Relay Mapping & Statistical Caveats）

为严格遵循**设计原则 9（实现进展、目标设计与实测证据透明区分）**与**设计原则 14（诚实可观测）**，避免外部读者将内部消融实验误读为第三方盲测通用基准，特对本次评测的实验边界、模型网关映射与统计口径做如下完整说明：

1. **内部模型网关别名映射（Model Relay Aliases: `home/codex/gpt-6.1-sol` & `deepseek-flash`）**：
   - 在作者的内部评测环境中，所有模型请求均通过本地统一鉴权与 Token 计量网关（`http://127.0.0.1:3425/v1`）转发。配置中的 `home/codex/gpt-6.1-sol`（`reasoning_effort = "xhigh"`，配套 C6 蒸馏模型 `home/codex/gpt-5.6-luna`）与 `deepseek-flash`（`reasoning_effort = "max"`）均为**内部评测网关的路由模型别名（Relay Model Aliases）**，而非公开商业 API 的标准模型名。
   - 外部开发者或评测人员通过 `mindie-bench` 的 `experiment.toml` 复现本套件时，无需依赖内部网关，可直接将 `[harness]` 中的 `provider_url` 与 `model` 绑定至任意公开的 OpenAI Responses / Chat Completions 兼容端点或原生模型服务（例如 `gpt-5`、`o3`、`claude-sonnet-4-5`、`deepseek-reasoner` 或 `deepseek-chat`）。
2. **作者受控消融基准 vs. 第三方盲测基准（Controlled Author Ablation vs. Third-Party Blind Benchmark，`repetitions = 1`）**：
   - 本报告中的 18 个工程任务（对应 `tasks/zh-vague/` 下 20 个 `task.toml`，其中 3 组 `G3` 任务各含独立的 `Seed` 与 `Eval` 定义）、Oracle 补丁及验证器（Verifier）均由项目作者基于 `vllm-ascend` 真实历史 PR、线上故障与性能瓶颈构建；受限于实机昇腾 NPU 独占窗口与高推理强度（`xhigh` / `max`）Token 成本，绝大多数 `(task, model, group)` 单元格采用 **`repetitions = 1`（单次端到端运行）**。
   - 因此，文中报告的解出率跃升与提速倍数应被严格视为**受控消融条件下各工程机制（`remote-dev` 远端工具、`knowledge` 渐进式披露、`C6` 经验蒸馏、`mode="explore"` 去先验锚定）有效性的作者自测实证参考**，而非大样本、多重复的第三方独立盲测基准。全部 `109` 场主评测 Trial 与另外 `55` 场批次预跑/基础设施重试的完整脱敏机器可读记录已全量公开于 [`docs/releases/0.1.0/agent-trials-109.json`](./agent-trials-109.json)。
   - **关于 `G3`（`0/3 -> 1/1`）的统计口径说明**：在 `cpu-rope-rotary-dim-32-zh-vague`（L2）与 `rope-rotary-dim-32-zh-vague`（L3 实机黑盒 `.so`）上，`0/3 -> 1/1` 指 **OpenAI Codex CLI** 在未接入前置任务蒸馏经验的三个基线组（`G0`、`G1`、`G2` 各运行 1 次，合计 `0/3`）均因缺失 `partial_rotary_factor > rotary_dim > head_size` 分支优先级契约而失败，而在 `G3`（`1/1`）中通过检索同族前置任务（`rotary_dim=64` $\to$ `rotary_dim=32` 参数变体）自动蒸馏的 L2 SOP 一次通过。相比之下，**DeepSeek Harness (`dsh`)** 在 `G0`/`G1`/`G2`/`G3` 上均解出了该任务（`100%`），`G3` 在 `dsh` 上的核心收益体现为交付耗时缩短（L2 从 `214.0s` 降至 `191.4s` / 净室首轮 `111.5s`，L3 从 `432.9s`/`492.3s` 降至 `383.2s`）。
   - **关于 `G4`（`0/8 -> 8/8`）的受控探索边界与裁判独立性加固说明（`mindie-bench v0.4.2`）**：`G4` 评测覆盖 **2 类算子/模型融合问题族**（`DeepSeek-V4 SparseMLA QLI 三因子融合` 与 `Triton SpatialNorm 4D 规约融合`）× **2 个执行层级**（L2 本地仓 + L3 实机 NPU）× **2 套模型**（共 8 组配对、24 场 Trial）。实验任务元数据的 `knowledge_gradient` 设为 `"near_exact"`——即当 Agent 从 `mode="reuse"` 切换至 `mode="explore"` 时，知识库过滤掉容易造成局部修补锚定的常规卡片，同时提供针对该瓶颈族的结构化变异因子图谱（`factor_graph`）与留一法消融规范（`leave_one_out_plan`）。因此，`0/8 -> 8/8` 证明的是**“去先验锚定 + 结构化因子图谱引导 + 留一法消融门禁”受控机制**相比裸宿主（`G0`）和常规复用检索（`G2`）的显著增益，而非无任何领域线索输入的完全开放世界算法发明。此外，针对早期公开裁判仅校验 `run_ablation_suite()` 返回字典字段的漏洞，我们在 **[`mindie-bench v0.4.2`](https://github.com/mindie-agent/mindie-bench/releases/tag/v0.4.2)（`d630aa5374598fcefee709042d8798787dbdc162`）** 中对全部 4 个 `G4` 任务的 `verifier/test.sh` 实施了独立算子/张量 Spy 与多尺寸非固定随机输入 `torch.allclose` 数值真值门禁加固：常量返回伪实现负对照 `100%` 被拦截（`reward = 0.0`），而 `codex` 与 `dsh` 在 `G4` 真实 Trial 中产出的全部 8 份候选补丁（`final_patch.diff` / `remote_final.patch`）经新裁判独立重验均 **`8 / 8` 真实执行底层算子并通过数值与消融校验（`reward = 1.0`）**。
3. **`G2` 知识检索负向延迟回归分析（Negative Latency Delta Cases in `G2`）**：
   - 对比逐任务数据可以观察到，**`G2`（启用知识检索）并非在所有任务上都快于 `G1`（仅 `remote-dev`）或 `G0`（裸宿主）**。当用户 Prompt 或报错堆栈已经直接给出了明确的文件名、函数名与断言不变量时，额外调用 `knowledge_query` / `knowledge_explain` 会引入工具往返与长上下文推理开销，导致部分任务出现**负向耗时回归（Negative Delta）**：
     - **`codex xhigh` L2 `dspark-mrv2-drafter-crash-zh-vague`**：`G0` (`552.1s`) $\to$ `G1` (`267.6s`, 15 轮) $\to$ `G2` (`440.2s`, 17 轮，增加 `1 query + 2 explain`)；
     - **`codex xhigh` L2 `k3-idle-dp-gdn-state-zh-vague`**：`G0` (`353.4s`, 17 轮) $\to$ `G1` (`333.8s`, 15 轮) $\to$ `G2` (`445.9s`, 17 轮，增加 `1 query + 3 explain`)；
     - **`codex xhigh` L2 `mrv2-dsa-prefill-metadata-zh-vague`**：尽管 `G2` 的末次代码修改时间（`185.9s`，14 轮）显著快于 `G0`（`288.8s`，16 轮），但因检索与测试长尾使得总交付耗时（`390.8s`）高于 `G0`（`314.9s`）与 `G1`（`323.6s`）；
     - **`dsh max` L3 `l3-dspark-mrv2-drafter-crash-zh-vague` & `l3-mrv2-dsa-prefill-metadata-zh-vague`**：`G1` 凭借 `remote-dev` 结构化远端执行分别取得 `341.7s` 与 `294.6s` 的全组最快成绩，而 `G2` 因叠加知识检索与远端重跑分别耗时 `550.0s` 与 `542.3s`；
     - **`sim-a3-ub-fusion-and-pipeline-dispatch-zh`**：`G0` 已通过的任务在 `G2` 中因调用 `query/explain` 核对公式，耗时从 `254.7s -> 301.7s`（Codex）和 `189.5s -> 215.3s`（DSH）。
   - **归因与演进方向**：这印证了领域知识检索的收益高度依赖于任务的“先验盲区度”——在存在未知领域陷阱（如 `profiler` `msprof` 多表时间窗对齐、黑盒 `.so` `rope` 优先级契约、`G4` 多因子融合消融、`diagnostics` 8 卡级联分诊、`sfa-mtp` 投机步缓冲区隔离）的任务中，`G2/G3/G4` 能逆转失败或大幅提速；而在报错信息已高度自包含的常规局部修补任务中，无差别执行多轮 `explain` 会拖慢交付。我们在后续 `0.1.x` 中已将**自适应检索门控与早停策略（Adaptive Retrieval Gating：当本地堆栈已精确定位单点语法/签名错误且 `query` 摘要无新增约束时跳过 `explain`）**列为 P1 重点优化项。

---

## 三、分维度详细实测数据与因果归因

### 维度一：五大专业组件（`profiler` · `sim` · `diagnostics` · `npu-top` · `coordinator`）在真实 Agent 任务中的收益

为回答“除了 `remote-dev` 与 `knowledge`，其余 5 个专业组件在真实 Agent 编程排障中究竟解决什么问题”，我们构建了 4 个基于 `vllm-ascend` 真实工程场景的评测任务（均通过 `mindie-bench soundness` 零奖励/满奖励门禁校验：`before_reward = 0.0, after_reward = 1.0`），并在 `codex + gpt-6.1-sol (xhigh)` 与 `dsh + deepseek-flash (max)` 上执行了 `G0`（无组件/无知识库）与 `G2`（启用组件 + 知识库）严格配对实验（机器可读逐 Trial 记录见 [`agent-trials-109.json`](./agent-trials-109.json) 中 `dimension = "dim1_dedicated_components"`，组件微基准见 [`value-results.json`](./value-results.json)）：

#### 1. `codex + gpt-6.1-sol (xhigh)` 专项组件实测对比表

| 真实任务 ID | 考察组件 | 对照组 | 结果 (Reward) | 交付耗时 (s) | 末次修改耗时 (s) | 模型调用 (Turns) | `query` / `explain` | 输出 Tokens | 最终补丁实际调用的组件 |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `profiler-msprof-straggler-and-hbm-fix-zh` | **`mindie-profiler`** | `G0` | **`FAIL` (`0.0`)** | `446.6s` | `391.2s` | `12` | `0 / 0` | `17,409` | `[]` |
| `profiler-msprof-straggler-and-hbm-fix-zh` | **`mindie-profiler`** | **`G2`** | **`PASS` (`1.0`)** | **`292.2s` (-34.6%)** | **`247.2s` (-36.8%)** | `16` | `1 / 1` | **`11,687` (-32.9%)** | `['mindie_profiler']` |
| `sim-a3-ub-fusion-and-pipeline-dispatch-zh` | **`mindie-sim`** | `G0` | `PASS` (`1.0`) | `254.7s` | `228.9s` | `11` | `0 / 0` | `10,435` | `[]` |
| `sim-a3-ub-fusion-and-pipeline-dispatch-zh` | **`mindie-sim`** | **`G2`** | **`PASS` (`1.0`)** | `301.7s` | `254.0s` | `13` | `2 / 1` | **`10,316` (-1.1%)** | `['mindie_sim']` |
| `diagnostics-cann-plog-cascade-root-cause-fix-zh` | **`mindie-diagnostics`** | `G0` | `PASS` (`1.0`) | `314.6s` | `293.8s` | `9` | `0 / 0` | `13,089` | `[]` |
| `diagnostics-cann-plog-cascade-root-cause-fix-zh` | **`mindie-diagnostics`** | **`G2`** | **`PASS` (`1.0`)** | **`239.6s` (-23.8%)** | **`219.4s` (-25.3%)** | `11` | `2 / 2` | **`8,619` (-34.2%)** | `['mindie_diagnostics']` |
| `npu-top-and-coordinator-multi-die-lease-repair-zh` | **`npu-top` + `coordinator`** | `G0` | `PASS` (`1.0`) | `373.8s` | `343.9s` | `9` | `0 / 0` | `16,605` | `[]` |
| `npu-top-and-coordinator-multi-die-lease-repair-zh` | **`npu-top` + `coordinator`** | **`G2`** | **`PASS` (`1.0`)** | **`318.2s` (-14.9%)** | **`292.3s` (-15.0%)** | `15` | `2 / 1` | **`12,424` (-25.2%)** | `['mindie_coordinator', 'npu_top']` |
| **四任务合计 (`codex xhigh`)** | **5 大组件全集** | **`G0`** | **`3 / 4` (75%)** | `1,389.7s` | `1,257.8s` | `41` | `0 / 0` | `57,538` | `0 / 4` |
| **四任务合计 (`codex xhigh`)** | **5 大组件全集** | **`G2`** | **`4 / 4` (100%)** | **`1,151.7s` (-17.1%)** | **`1,012.9s` (-19.5%)** | `55` | `7 / 5` | **`43,046` (-25.2%)** | **`4 / 4` (100%)** |

#### 2. `dsh + deepseek-flash (max)` 专项组件实测对比表

| 真实任务 ID | 考察组件 | 对照组 | 结果 (Reward) | 交付耗时 (s) | 末次修改耗时 (s) | 模型调用 (Turns) | `query` / `explain` | 输出 Tokens | 最终补丁实际调用的组件 |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `profiler-msprof-straggler-and-hbm-fix-zh` | **`mindie-profiler`** | `G0` | **`FAIL` (`0.0`)** | `319.3s` | `263.1s` | `40` | `0 / 0` | `52,096` | `[]` |
| `profiler-msprof-straggler-and-hbm-fix-zh` | **`mindie-profiler`** | **`G2`** | **`PASS` (`1.0`)** | **`224.4s` (-29.7%)** | **`200.5s` (-23.8%)** | `39` | `1 / 1` | **`39,468` (-24.2%)** | `['mindie_profiler']` |
| `sim-a3-ub-fusion-and-pipeline-dispatch-zh` | **`mindie-sim`** | `G0` | `PASS` (`1.0`) | `189.5s` | `139.8s` | `20` | `0 / 0` | `33,670` | `[]` |
| `sim-a3-ub-fusion-and-pipeline-dispatch-zh` | **`mindie-sim`** | **`G2`** | **`PASS` (`1.0`)** | `215.3s` | `148.9s` | `50` | `2 / 1` | `35,915` | `['mindie_sim']` |
| `diagnostics-cann-plog-cascade-root-cause-fix-zh` | **`mindie-diagnostics`** | `G0` | `PASS` (`1.0`) | `241.2s` | `219.1s` | `23` | `0 / 0` | `36,664` | `[]` |
| `diagnostics-cann-plog-cascade-root-cause-fix-zh` | **`mindie-diagnostics`** | **`G2`** | **`PASS` (`1.0`)** | **`132.4s` (-45.1%)** | **`57.9s` (-73.6%)** | `27` | `1 / 1` | **`22,890` (-37.6%)** | `['mindie_diagnostics']` |
| `npu-top-and-coordinator-multi-die-lease-repair-zh` | **`npu-top` + `coordinator`** | `G0` | `PASS` (`1.0`) | `415.3s` | `378.3s` | `43` | `0 / 0` | `74,056` | `[]` |
| `npu-top-and-coordinator-multi-die-lease-repair-zh` | **`npu-top` + `coordinator`** | **`G2`** | **`PASS` (`1.0`)** | **`199.9s` (-51.9%)** | **`194.3s` (-48.6%)** | `50` | `3 / 1` | **`31,263` (-57.8%)** | `['mindie_coordinator', 'npu_top']` |
| **四任务合计 (`dsh max`)** | **5 大组件全集** | **`G0`** | **`3 / 4` (75%)** | `1,165.3s` | `1,000.3s` | `126` | `0 / 0` | `196,486` | `0 / 4` |
| **四任务合计 (`dsh max`)** | **5 大组件全集** | **`G2`** | **`4 / 4` (100%)** | **`772.0s` (-33.8%)** | **`601.6s` (-39.9%)** | `166` | `7 / 4` | **`129,536` (-34.1%)** | **`4 / 4` (100%)** |

#### 3. 各组件具体收益归因
- **`mindie-profiler`（解出率 `0% -> 100%`，耗时缩短 `29.7%–34.6%`）**：在 `G0` 下，无论是 `gpt-6.1-sol (xhigh)` 还是 `deepseek-flash (max)`，直接手写 SQL 解析 `msprof` 原始 SQLite 产物时均掉入 `torch_npu` 1.2.0 `COMMUNICATION_OP` 与 `COMPUTE_TASK_INFO` / `CANN_API` 表的时间窗对齐陷阱（误算 `kernel_sum_ms = 0.048`、`host_gap_ms = 0.02`），导致双双失败；而在 `G2` 下，Agent 直接调用 `mindie_profiler`（`analyze_profile`、`compare_profiles`、`attribute_memory`），在只读零库污染（`db_mutation = False`）前提下精准分离慢链路（`Comm`）与慢卡（`Attention`）并完成 `9.9 GB`（99%）HBM 已知桶与 `50 MB`（0.5%）残差归因，实现 `100%` 一次通过。
- **`mindie-diagnostics`（交付提速 `1.31x–1.82x`，末次修改最高提速 `3.78x`，输出 Token 减少 `34.2%–37.6%`）**：面对 8 卡 HCCL + AICore 级联报错的复杂 `plog` 日志，`G2` 直接调用 `mindie_diagnostics.analyze_fault_log` 确定性锁定首发根因 `Rank 3`（`EZ9999` `aicore_memory_or_tiling`）并区分衍生超时 `Rank 7`（`EI9999`），同时复用双层脱敏与 Outbox 去重，避免了 `G0` 从零手写正则解析器与脱敏逻辑的冗长试错。
- **`npu-top` + `mindie-coordinator`（交付提速 `1.17x–2.08x`，输出 Token 减少 `25.2%–57.8%`）**：在昇腾 A3（910C）双 Die `Phy-ID (0..15)` 与容器 `/proc` 进程映射及多 Worker 并发抢占场景下，`G2` 直接调用 `npu_top` 与 `mindie_coordinator` 生产级 SQLite WAL 租约队列，100% 消除端口冲突（`bind_conflicts: 1 -> 0`）与重复选卡（`duplicate_device_selections: 1 -> 0`）。
- **`mindie-sim`（100% 采纳四层 Roofline 与 UB 溢出门禁）**：双模型在 `G2` 中均直接调用 `mindie_sim` 完成昇腾 A3 Qwen2.5-7B 整网 TPOT 预测（`15.060 ms` vs 实机 `15.710 ms`，误差 `-4.14%`）、算子流水排布（`gemm_finite_pipeline` / `vector_instruction`）及 `192 KiB` UB 容量溢出拦截（剔除溢出候选并保留节省 `2.0 MiB` GM 流量的合法融合子图）。

---

### 维度二：`remote-dev` (`G1`) 与 `knowledge` (`G2`) 在 L2 本地仓与 L3 实机昇腾 NPU 上的表现

机器可读原始记录索引（均收录于 [`docs/releases/0.1.0/agent-trials-109.json`](./agent-trials-109.json) 中 `dimension = "dim2_remote_dev_and_knowledge"`）：
- `codex + gpt-6.1-sol (xhigh)` L2：批次 `codex-010-l2-g3-20261023`
- `codex + gpt-6.1-sol (xhigh)` L3 实机 NPU：批次 `codex-010-l3-20261023`
- `dsh + deepseek-flash (max)` L2 & L3：批次 `dsh-003-zh-vague-v2-20261022` & `dsh-003-zh-vague-20261022`

| 层级 | 任务 ID | 参测模型 | `G0` 耗时 (轮次) | `G1` (`remote-dev`) 耗时 (轮次) | `G2` (`+knowledge`) 耗时 (轮次) | 关键收益与负向回归说明 |
| :---: | :--- | :--- | :---: | :---: | :---: | :--- |
| **L2** | `dspark-mrv2-drafter-crash-zh-vague` | `codex xhigh` | `552.1s` (`22`) | **`267.6s` (`15`)** | `440.2s` (`17`) | `G1` 较 `G0` **提速 `2.06x`（`-51.5%`）**；`G2` 因 `1 query + 2 explain` 产生负向延迟回归 |
| **L2** | `dspark-mrv2-drafter-crash-zh-vague` | `dsh max` | `200.1s` (`39`) | `261.5s` (`60`) | **`197.8s` (`60`)** | `G2` 实现最快交付 |
| **L2** | `k3-idle-dp-gdn-state-zh-vague` | `codex xhigh` | `353.4s` (`17`) | **`333.8s` (`15`)** | `445.9s` (`17`) | `G1` 较 `G0` 缩短耗时与轮次；`G2` 因 `1 query + 3 explain` 产生负向延迟回归 |
| **L2** | `k3-idle-dp-gdn-state-zh-vague` | `dsh max` | `282.6s` (`60`) | `287.2s` (`60`) | **`264.4s` (`60`)** | `G2` 较 `G0`/`G1` 缩短 `-6.4%` |
| **L2** | `mrv2-dsa-prefill-metadata-zh-vague` | `codex xhigh` | `314.9s` (`16`) | `323.6s` (`13`) | `390.8s` (`14`) | `G1`/`G2` 轮次较 `G0` 减少 `12.5%–18.8%`；`G2` 末次修改更快（`185.9s` vs `288.8s`）但测试长尾拉长总耗时 |
| **L2** | `mrv2-dsa-prefill-metadata-zh-vague` | `dsh max` | `318.5s` (`51`) | `281.2s` (`60`) | **`214.2s` (`60`)** | **交付耗时 `G0 -> G1 -> G2` 阶梯下降（提速 `1.49x`，`-32.7%`）；首次修改 `247.3s -> 113.6s`（提速 `2.18x`），末次修改 `287.7s -> 136.4s`（提速 `2.11x`）** |
| **L2** | `mtp-draft-slot-mapping-capacity-zh-vague` | `codex xhigh` | `273.6s` (`11`) | `434.7s` (`13`) | `416.2s` (`15`) | 三组均一次 `completed_pass` |
| **L2** | `mtp-draft-slot-mapping-capacity-zh-vague` | `dsh max` | `184.9s` (`55`) | **`163.7s` (`47`)** | `210.4s` (`60`) | `G1` 较 `G0` 耗时缩短 `-11.5%`、轮次减少 `-14.5%` |
| **L2** | `sfa-mtp-seq-lens-eval-zh-vague` | `codex xhigh` | `146.8s` (`7`) | `74.4s` (`6`) | **`63.4s` (`6`)** | **`G1` 提速 `1.97x`，`G2` 提速 `2.32x`（耗时 `-56.8%`）** |
| **L3 (实机 NPU)** | `l3-dspark-mrv2-drafter-crash-zh-vague` | `codex xhigh` | `515.8s` (`23`) | `498.1s` (`29`) | **`465.6s` (`25`)** | 实机 `Ascend950DT` NPU 5：**`G0 -> G1 -> G2` 阶梯提速（`-9.7%`）** |
| **L3 (实机 NPU)** | `l3-dspark-mrv2-drafter-crash-zh-vague` | `dsh max` | `655.7s` (`67`) | **`341.7s` (`80`)** | `550.0s` (`60`) | 实机 NPU：**`G1` 较 `G0` 提速 `1.92x`（节省 `314.0s`）**；`G2` 快于 `G0` 但慢于 `G1` |
| **L3 (实机 NPU)** | `l3-mrv2-dsa-prefill-metadata-zh-vague` | `codex xhigh` | `574.7s` (`25`) | `570.2s` (`30`) | **`548.0s` (`21`)** | 实机 `Ascend950DT` NPU 4：**`G2` 最快且轮次减少 `-16.0%`** |
| **L3 (实机 NPU)** | `l3-mrv2-dsa-prefill-metadata-zh-vague` | `dsh max` | `457.5s` (`60`) | **`294.6s` (`60`)** | `542.3s` (`78`) | 实机 NPU：**`G1` 较 `G0` 提速 `1.55x`（节省 `162.9s`）**；`G2` 叠加检索轮次产生负向回归 |

---

### 维度三：`G3` 跨任务经验飞轮（`Seed -> Capture -> C6 Distill -> Eval`）在同族黑盒与复杂排障中的收益

在工程实践中，当团队遇到上游公共知识库尚未收录的新型 Bug（尤其是剥离了 C++ `.cpp` 源码、仅剩编译后 `.so` 扩展的线上黑盒环境）时，单靠 `G0`/`G1`/`G2` 往往因缺少特定算子分支优先级契约而失败或耗时增加。`G3` 在 3 组同族配对迁移任务（如 `rotary_dim=64` Seed $\to$ `rotary_dim=32` Eval 参数变体）上验证了 MindIE Agent 的经验自演进飞轮（逐 Trial 记录见 [`agent-trials-109.json`](./agent-trials-109.json) 中 `dimension = "dim3_g3_experience_flywheel"`）：

| 层级与任务对（`Seed -> Eval`） | 参测模型 | `G0` Eval (`n=1`) | `G1` Eval (`n=1`) | `G2` Eval (`n=1`) | `G3` Seed（含 C6 蒸馏） | **`G3` Eval（命中 Seed 蒸馏知识）** | 飞轮核心收益（区分 Codex 逆转与 DSH 提速） |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **L2：`cpu-rope-64` $\to$ `cpu-rope-32`** | `codex xhigh` | **`FAIL`** (`225.1s`) | **`FAIL`** (`262.0s`) | **`FAIL`** (`382.3s`) | **`PASS`** (`298.3s`，C6 蒸馏 `51.5s`，生成 `unit-rope-cache-explicit-rotary-dimension`) | **`PASS` (`211.8s`，`9` 次调用，`query/explain = 1/1`)** | **Codex 基线三组（`G0/G1/G2`）合计 `0/3` 未过，`G3` 检索同族 Seed 知识后 `1/1` 一次通过** |
| **L3 实机 NPU：`rope-64` $\to$ `rope-32`（黑盒 `.so`）** | `codex xhigh` | **`FAIL`** (`268.3s` / 首轮裸 `ssh` `unknown` `230.3s`) | **`FAIL`** (`463.4s`) | **`FAIL`** (`391.1s`) | **`PASS`** (`324.2s`，C6 蒸馏 `19.2s`，生成 `unit-rotary-dim-cache-selection`) | **`PASS` (`270.8s`，`15` 次调用，`query/explain = 1/1`)** | **实机 NPU 黑盒 `.so` 任务上 Codex 基线三组 `0/3` 未过，`G3` 命中同族 Seed 知识后 `1/1` 一次通过** |
| **L2：`sfa-mtp-seed` $\to$ `sfa-mtp-eval`** | `codex xhigh` | `PASS` (`146.8s`, `7` 轮) | `PASS` (`74.4s`, `6` 轮) | `PASS` (`63.4s`, `6` 轮) | **`PASS`** (`50.4s` 前台 + `61.1s` C6 蒸馏，生成 `unit-review-addition-isolate-sfa-sequence-len-cb782172-0`) | **`PASS` (`68.4s` 前台 / `82.4s` 含采集，`7` 次调用，`query/explain = 1/1`)** | **较 `G0` 前台耗时缩短 `-53.4%`（提速 `2.15x`），含采集总交付缩短 `-43.9%`（`1.78x`）** |
| **L2：`cpu-rope-64` $\to$ `cpu-rope-32`** | `dsh max` | `PASS` (`214.0s`, `46` 轮) | `PASS` (`264.7s`, `43` 轮) | `PASS` (`241.8s`, `50` 轮) | **`PASS`** (`239.6s` / v1 净室 `147.9s`) | **`PASS` (`191.4s`；v1 净室 `111.5s` / `19` 轮)** | **DSH 在 `G0–G3` 均通过；`G3` 交付耗时显著低于 `G0`/`G1`/`G2`（最高提速 `1.92x`）** |
| **L3 实机 NPU：`rope-64` $\to$ `rope-32`** | `dsh max` | `PASS` (`432.9s`, `47` 轮) | `PASS` (`311.1s`, `65` 轮) | `PASS` (`492.3s`, `44` 轮) | **`PASS`** (`445.9s`, `43` 轮) | **`PASS` (`383.2s`, `44` 轮)** | **DSH 在 `G0–G3` 均通过；`G3` 较 `G0` 缩短 `-11.5%`，较 `G2` 缩短 `-22.2%`** |
| **L2：`sfa-mtp-seed` $\to$ `sfa-mtp-eval`** | `dsh max` | `PASS` (`91.6s`, `27` 轮) | `PASS` (`112.2s`, `32` 轮) | `PASS` (`159.7s`, `41` 轮) | **`PASS`** (`152.2s`, `27` 轮) | **`PASS` (`148.7s`, `40` 轮)** | Seed 与 Eval 全链路 `100%` 闭环通过（较 `G2` 缩短 `-6.9%`） |

---

### 维度四：`G4` 受控因子图谱探索（`mode="explore"`）在算子/模型多因子融合任务上的消融收益

在 DeepSeek-V4.1 Sparse MLA Query 反量化与 Lightning Indexer 三因子融合（`dsv4-sparse-mla-qli-fusion-rsi-zh`）以及 Triton Ascend SpatialNorm 维度合并与 UB 多缓冲矢量化（`triton-spatial-norm-dim-merge-rsi-zh`）两类问题族（覆盖 L2 本地仓与 L3 实机昇腾 NPU，共 4 个任务，`knowledge_gradient = "near_exact"`，逐 Trial 记录见 [`agent-trials-109.json`](./agent-trials-109.json) 中 `dimension = "dim4_g4_open_exploration"`）中：
- **`G0`（裸宿主）**：因缺乏昇腾 UB 容量边界、算子融合不变量及留一法消融规范，在双模型上 **`0 / 8` 全部未通过（`0%`）**；
- **`G2`（常规检索 `mode="reuse"`）**：仅暴露常规 L1/L2 排障卡片而未挂载 `mode="explore"` 的 L3/L4 变异因子图谱（`factor_graph`）与留一法消融计划（`leave_one_out_plan`），Agent 陷入局部修补或重复检索，在双模型上同样 **`0 / 8` 全部未通过（`0%`）**；
- **`G4`（`mode="reuse" -> mode="explore"` 因子图谱引导探索）**：Agent 先通过 `1–3` 次 `mode="reuse"` 识别常规检索边界，随后切换至 `mode="explore"` 获取去先验锚定的 L1–L3 硬件刚性约束、结构化三因子变异图谱与留一法实验计划，在 **`codex + gpt-6.1-sol (xhigh)` 与 `dsh + deepseek-flash (max)` 上实现 `8 / 8`（`100%`）全部通过**。

| 层级 | 任务 ID | 参测模型 | `G0` 结果 (`n=1`) | `G2` 结果 (`n=1`) | **`G4` (`mode="explore"`) 结果 (`n=1`)** | `G4` 交付耗时 | `G4` 模型调用 | `reuse` $\to$ `explore` 调用次数与状态切换 |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **L2** | `dsv4-sparse-mla-qli-fusion-rsi-zh` | `codex xhigh` | `FAIL` (`612.3s`) | `FAIL` (`778.3s`) | **`PASS` (`1.0`)** | `894.6s` | `23` | `reuse=1, explore=1` (`transitioned=True`) |
| **L2** | `dsv4-sparse-mla-qli-fusion-rsi-zh` | `dsh max` | `FAIL` (`418.5s`) | `FAIL` (`298.9s`) | **`PASS` (`1.0`)** | `397.2s` | `60` | `reuse=2, explore=2` (`transitioned=True`) |
| **L2** | `triton-spatial-norm-dim-merge-rsi-zh` | `codex xhigh` | `FAIL` (`765.3s`) | `FAIL` (`1089.8s`) | **`PASS` (`1.0`)** | `1177.9s` | `28` | `reuse=2, explore=1` (`transitioned=True`) |
| **L2** | `triton-spatial-norm-dim-merge-rsi-zh` | `dsh max` | `FAIL` (`484.6s`) | `FAIL` (`409.3s`) | **`PASS` (`1.0`)** | `393.3s` | `60` | `reuse=2, explore=2` (`transitioned=True`) |
| **L3 (实机 NPU)** | `l3-dsv4-sparse-mla-qli-fusion-rsi-zh` | `codex xhigh` | `FAIL` (`621.9s`) | `FAIL` (`765.4s`) | **`PASS` (`1.0`)** | `751.9s` | `24` | `reuse=2, explore=1` (`transitioned=True`) |
| **L3 (实机 NPU)** | `l3-dsv4-sparse-mla-qli-fusion-rsi-zh` | `dsh max` | `FAIL` (`347.6s`) | `FAIL` (`500.7s`) | **`PASS` (`1.0`)** | `323.8s` | `36` | `reuse=2, explore=1` (`transitioned=True`) |
| **L3 (实机 NPU)** | `l3-triton-spatial-norm-dim-merge-rsi-zh` | `codex xhigh` | `FAIL` (`1236.8s`) | `UNKNOWN/FAIL` (`1270.7s`) | **`PASS` (`1.0`)** | `1079.8s` | `38` | `reuse=1, explore=1` (`transitioned=True`) |
| **L3 (实机 NPU)** | `l3-triton-spatial-norm-dim-merge-rsi-zh` | `dsh max` | `FAIL` (`327.1s`) | `FAIL` (`623.4s`) | **`PASS` (`1.0`)** | `703.9s` | `60` | `reuse=3, explore=2` (`transitioned=True`) |
| **总计 (8 组配对)** | **2 类问题族 × L2/L3 × 双模型** | **双模型汇总** | **`0 / 8` (`0%`)** | **`0 / 8` (`0%`)** | **`8 / 8` (`100%`)** | — | — | **`8 / 8` (`100%` 完成 `reuse -> explore` 切换)** |

---

## 四、三平台（macOS · Windows WSL2 · Windows 11 PowerShell）与四大宿主插件全链路验证矩阵

除真实大模型任务收益外，`0.1.0` 对四个原生宿主插件（`mindie-agent-cc`、`mindie-agent-codex`、`mindie-agent-kimi`、`mindie-agent-dsh`）、核心共享组件（`knowledge`、`diagnostics`、`remote-dev`）及 `mindie-bench`（含全部 4 插件 `G1–G4` 门禁测试 `test_four_harness_g1_g4.py`）在三大操作系统/硬件平台上完成了 **14,000+ 项自动化与端到端产品流验证（0 失败）**：

| 仓库 / 验证项 | macOS (Apple Silicon) | Windows WSL2 (Linux Ubuntu 24.04 x86_64) | Windows 11 PowerShell (Native x86_64) | 五大核心产品流覆盖状态 |
| :--- | :---: | :---: | :---: | :--- |
| **`mindie-agent-cc`** | `390 passed, 0 failed` | `388 passed, 0 failed` | `378 passed, 13 skipped, 0 failed` | 安装引导 · 自动更新 · 故障上报(开/关) · 知识检索(开/关) · 经验上报(开/关) **全通过** |
| **`mindie-agent-codex`** | `500 passed, 0 failed` | `501 passed, 0 failed` | `507 passed, 18 skipped, 0 failed` | 安装引导 · 自动更新 · 故障上报(开/关) · 知识检索(开/关) · 经验上报(开/关) **全通过** |
| **`mindie-agent-kimi`** | `372 passed, 0 failed` | `372 passed, 0 failed` | `363 passed, 14 skipped, 0 failed` | 安装引导 · 自动更新 · 故障上报(开/关) · 知识检索(开/关) · 经验上报(开/关) **全通过** |
| **`mindie-agent-dsh`** | `123 passed, 0 failed` | `123 passed, 0 failed` | `50 passed, 73 skipped, 0 failed` | 安装引导 · 自动更新 · 故障上报(开/关) · 知识检索(开/关) · 经验上报(开/关) **全通过** |
| **`knowledge`** | `1,525 passed, 0 failed` | `1,509 passed, 0 failed` | `1,447 passed, 100 skipped, 0 failed` | L1–L4 检索 · `mode="explore"` · C6 蒸馏 · Gitleaks 双层脱敏 · 授权撤回即停 **全通过** |
| **`diagnostics`** | `325 passed, 0 failed` | `326 passed, 0 failed` | `317 passed, 12 skipped, 0 failed` | 本地旋转日志 · CANN/`plog` 根因分诊 · 指纹去重 · 授权开关门控 **全通过** |
| **`remote-dev`** | `657 passed, 0 failed` | `694 passed, 0 failed` | `571 passed, 137 skipped, 0 failed` | 跨机 SSH 隧道 · 远端容器读写/补丁 · 持久后台作业控制 **全通过** |
| **`mindie-bench` (`G1–G4` 四插件门禁)** | `1,384 passed, 0 failed` | `1,460 passed, 0 failed` | `1,313+ passed, 0 failed` (`test_four_harness_g1_g4.py` `22/22`) | `codex` · `claude-code` · `kimi` · `dsh` 四插件 `G0–G4` 门禁与矩阵执行 **全通过** |
| **平台总计** | **`5,276 passed, 0 failed`** | **`5,373 passed, 0 failed`** | **`4,946+ passed, 0 failed`** | **三平台累计 `15,595+ passed, 0 failed`** |

---

## 五、`mindie-bench` 真实任务 Prompt 设计与完整原文（Prompts & Harness Injection）

参照开源 Agent 基准社区（SWE-bench / Terminal-Bench）的透明性规范，本节完整公开 `mindie-bench` 在 `G0–G4` 各消融组中向模型注入的**宿主提示词拼接逻辑**与**全部 18 个真实任务的 `instruction.md` 原文**。

### 1. 宿主消融组提示词注入契约（`build_agent_prompt`）

在 `mindie-bench`（[`src/mindie_bench/runner/trial_preflight.py`](https://github.com/mindie-agent/mindie-bench/blob/main/src/mindie_bench/runner/trial_preflight.py) 与 [`profile_builder.py`](https://github.com/mindie-agent/mindie-bench/blob/main/src/mindie_bench/runner/profile_builder.py)）中，每个 Trial 仅在启动时发送**唯一一条初始 Prompt**，全程零人工干预（`human_interventions = 0`）：

```text
Prompt = knowledge_prompt(group, harness) + task_instruction_md + workspace_scope_suffix
```

- **`knowledge_prompt(group, harness)`（消融组唯一前缀差异）**：
  - **`G0`（裸宿主）与 `G1`（仅 `remote-dev`）**：`""`（**空字符串**，不注入任何与 MindIE 知识库或 Skill 相关的提示）；
  - **`G2`、`G3`、`G4`（显式激活知识与组件生态 `knowledge_mode="explicit"`）**：仅在任务描述前加上真实用户在终端调用的唯一入口指令：
    - OpenAI Codex CLI：`$mindie-agent\n\n`
    - Claude Code / Kimi Code / DeepSeek Harness (DSH)：`/mindie-agent\n\n`
- **`workspace_scope_suffix`（L2 本地 vs L3 远端 NPU 环境边界声明，所有消融组完全一致）**：
  - **L2 本地快照环境**：
    ```text
    The workspace is a plain source snapshot without Git history. Apply the repair here and use the public reproducer or relevant available tests for validation. Git history, stash and checkout are unavailable. Choose validation proportional to the change and observed failures; report any unavailable dependencies in your final answer.
    ```
  - **L3 远端实机昇腾 NPU 环境**：
    ```text
    Work on the isolated SSH endpoint bench-slot. Remote workspace: <remote.path>. Assigned NPU devices: <devices>. The local directory is an empty client scratchpad; the source snapshot lives in the remote workspace on bench-slot without Git history. Apply the repair in the remote workspace that the NPU verifier will inspect. Choose validation proportional to the change and observed failures.
    ```

### 2. 四大类 18 个真实任务的 `instruction.md` 原文汇编

所有任务定义均开源于 `mindie-bench` 仓库的 [`tasks/zh-vague/`](https://github.com/mindie-agent/mindie-bench/tree/main/tasks/zh-vague) 目录。

<details>
<summary><b>① 专项组件真实 Agent 任务（4 个：`profiler` · `sim` · `diagnostics` · `npu-top` + `coordinator`）</b></summary>

#### 1.1 `profiler-msprof-straggler-and-hbm-fix-zh`（考察 `mindie-profiler` + `knowledge`）
```markdown
我们在昇腾 NPU 上排查双卡 (`tp=2`) `vllm-ascend` 解码阶段的 `torch_npu` 1.2.0 Profiling 数据库与显存拆解脚本 `vllm_ascend_diag/profile_reconciler.py`（配套离线复现输入位于 `vllm_ascend_diag/fixtures/profiler_case.json`）。

目前 `reconcile_profile_and_hbm()` 的实现存在三处典型的领域统计错误：
1. **多流算子并发区间未取并集 (`busy_union_ms`)**：在计算每个 step 窗口 (`step_4`, `step_5`) 的设备忙时 `busy_union_ms` 时，直接把所有算子与通信事件的耗时简单相加（且漏计了 `COMMUNICATION_OP` 表的重复导出项或将其混入忙时），导致流 1 (`aclnnFlashAttention` `[0..10us]`) 与流 2 (`GroupedMatmul` `[5..15us]`) 的并发重叠被重复计入，`busy_union_ms` 与 `host_gap_ms` 失真；
2. **跨卡慢卡 (`slowest_rank`) 与暴露通信 (`exposed_comm_ms`) 归因错误**：按事件条数把 `rank 0`（10 条事件）误判为慢卡，而未按去除计算掩盖后的暴露通信区间 (`exposed_comm_ms`) 及 `busy_union_ms_p50` 识别出 `rank 1`（`rank_index = 1`，`hcom_allReduce_` 在流 3 上持续 `[20..45us]`，主因模块为 `"Comm"`）才是真正的慢卡；
3. **P0–P4 显存容器跨层重复累加 (`known_sum_bytes` 与 `residual`)**：将 `msprof_components` 的 `APP`/`HCCL`/`RUNTIME`/`SLOG` (`P0`) 与 `activation` (`P4`, `after_infer - after_ready`) 全部标记为 `included_in_sum = True` 并使用了未切分的 `weight_manifest.per_device_bytes`，导致 `known_sum_bytes` 远超 `after_infer_hbm` 实测峰值并出现负残差。按 P0–P4 非加性归因规范，仅 `baseline_observed` (`P1`)、`weights` (`P2`, 取 `vllm_info.weights_bytes`)、`kv_cache` (`P2`) 与 `graph` (`P2`) 计入 `known_sum_bytes`，残差在 `residual_target_bytes` (`200 MiB`) 以内时 `status = "within_target"`，超出时为 `"above_target"`。

请你定位并修复 `vllm_ascend_diag/profile_reconciler.py` 中的 `reconcile_profile_and_hbm()`，使其在默认输入与峰值扰动输入 (`after_infer_override_bytes`) 下均返回准确的 C7 窗口统计、双份 profile 对比结果 (`comparison`) 与 P0–P4 显存归因报告。
```

#### 1.2 `diagnostics-cann-plog-cascade-root-cause-fix-zh`（考察 `mindie-diagnostics` + `knowledge`）
```markdown
我们在排查多卡推理故障归因与诊断上报模块 `vllm_ascend_diag/plog_fault_reconciler.py`（配套复现数据位于 `vllm_ascend_diag/fixtures/diagnostics_case.json`）。

当前 `reconcile_plog_and_outbox()` 的实现存在三处严重缺陷：
1. **将下游 HCCL 等待超时误判为首发根因 (`triage`)**：日志第一行是 `rank[1]` 的 `HCCL_E_WAIT_TIMEOUT`，第四行是 `rank[1]` 的 `ErrCode=EI0006` (`hccl_collective`)，但这是因为 `rank[0]` 在 `14:54:51.635` / `14:54:52.000` 发生了 `HBM ECC uncorrectable error` (`failed operator: MatMulV2`, `ErrCode=E89999`, `subsystem = "driver_memory"`, `fault_domain = "device_oom_or_driver"`)。当前代码直接取日志首行作为根因，漏判了 `root_cause_rank = "0"`, `device_id = "0"`, `failed_operator = "MatMulV2"`, `error_codes = ["E89999", "EI0006"]`，且未将 `rank[1]` 的两条 HCCL 报错标记为级联超时 (`cascading_timeout_detected = True`, `cascading_rank = "1"`, `cascading_timeout_lines`)，也缺少 `"npu-smi"` 与 `"HCCL_ENTRY_LOG_ENABLE=1"` 等 `recommended_tools`；
2. **R2 隐私脱敏不完整 (`sanitized_log`)**：当前仅替换了 `Bearer` 令牌，遗漏了 `sk-...` API Key、内网地址 `10.24.7.19`、编号主机名 `node-17` 以及用户目录 `/home/exampleuser/project/model`（脱敏后应保留 `torch_npu` 与 `MatMulV2` 等技术上下文，且 `remaining_secrets == []`、`scan_finding_count == 0`）；
3. **Outbox 外部写入超时后盲目重置为 `pending` (`outbox_audit`)**：当事件入队并执行 `begin_post` 发起外部 GitHub Issue POST 时，一旦发生超时 (`simulate_post_timeout=True`)，状态必须保持为 `"uncertain"`（严禁重置回 `"pending"` 导致重复发帖），且后续同一 `fingerprint` 的新事件 (`operation_id_2`) 再次 `enqueue` 时，应将 `occurrences` 累加至 `2` 并把两个 `operation_id` 合并进 `incident_ids`，同时维持 `state == "uncertain"` (`blind_retry_prevented = True`)。

请修复 `vllm_ascend_diag/plog_fault_reconciler.py` 中的 `reconcile_plog_and_outbox()`。
```

#### 1.3 `npu-top-and-coordinator-multi-die-lease-repair-zh`（考察 `npu-top` + `mindie-coordinator`）
```markdown
我们在昇腾 A2 (`910B4`) 与 A3 (`Ascend910` 双 Die) 集群上排查设备观测与多 Die 租约分配模块 `vllm_ascend_diag/multi_die_lease_allocator.py`（配套采集数据位于 `vllm_ascend_diag/fixtures/npu_coordinator_case.json`）。

当前 `reconcile_multi_die_and_leases()` 的实现存在四处硬件拓扑与调度缺陷：
1. **混淆 A3 双 Die 卡内 `Chip ID` 与全局物理 `Phy-ID` (`a3_parsed` 与 `a2_parsed`)**：在解析 A3 `dual_die_smi` 时，把每张卡的两个 Die 的 `phy_id` 都错写成了卡内局部 `0, 1`（正确应为 Card 0 `[0, 1]`、Card 1 `[2, 3]`、Card 2 `[4, 5]`），未把卡内双 Die 的 HBM 汇总到卡级（Card 0 应为 `3343 + 40000 = 43343 / 131072 MB`），未将 `(npu_id=0, chip_id=1)` 上的进程 `777` (`VLLMWorker_0`) 映射到 `phy_id = 1`，且未应用 `usages_text` 对单 Die/双 Die `aicore_percent` 的覆盖 (`usage_override_probe` 应更新为 `55` 与 `70`)；
2. **跨半忙卡错误分配同卡双 Die 租约 (`s1_dual_die` 与 `s1_pd_pair`)**：在 `same_npu_dual_die` (`S1`, `die_count=2`) 策略下，必须在同一张物理卡上分配两个均空闲（无进程且 `HBM < 8192 MB`）的兄弟 Die `(2k, 2k+1)`。由于 Card 0 的 `Phy-ID 1` 已被占用 (`40000 MB`)，Card 0 的 `Phy-ID 0` 不可用于 `same_npu_dual_die`，应分配 Card 1 的 `"2,3"`；在 `disaggregated_pd_pair` (`die_count=4`, `prefill=2`, `decode=2`) 下，应优先整卡分配互不重叠的 `{"prefill": "2,3", "decode": "4,5"}`；
3. **多角色 `distinct_hosts=True` 放置冲突与容量不足时的半分配 (`placement_ok` 与 `placement_busy`)**：在 64 个 runtime 目录中为 `prefill` 与 `decode` 分配 `Ascend910C` 时，`distinct_hosts=True` 应选出不同主机上的 `["runtime-32", "runtime-36"]`；当可用主机不足 2 台时，必须整单拒绝并返回 `runtime_ids = []` 及非空 `reason`；
4. **DCMI 降频掩码位定义颠倒 (`dcmi_decoded`)**：bit `1 << 2` (`4`) 对应 `thermal_limit=True`，bit `1 << 3` (`8`) 对应 `power_limit=True`，未知高位（如 bit `63`）应记录在 `unknown_bits = [63]`，当 `ret != 0` 时 `thermal_limit` 应返回 `None`。

请修复 `vllm_ascend_diag/multi_die_lease_allocator.py` 中的 `reconcile_multi_die_and_leases()`。
```

#### 1.4 `sim-a3-ub-fusion-and-pipeline-dispatch-zh`（考察 `mindie-sim` + `knowledge`）
```markdown
我们在昇腾 A3 (`Ascend910_9362`) 上评估算子融合与整网性能预测脚本 `vllm_ascend_diag/a3_sim_planner.py`（配套公开输入位于 `vllm_ascend_diag/fixtures/sim_four_layer.json`、`qwen2.5-7b-instruct.json` 与 `mixed_operator_plan.json`）。

当前 `evaluate_a3_simulation_suite()` 的实现存在五处仿真建模缺陷：
1. **Layer 1 Roofline 与 HAP 评分公式错误**：未按 `Ascend910_9362` 单 Die 硬件规格（20 AIC, 8192 bf16 ops/cycle/AIC, 1650 MHz -> `270.336 TFLOP/s`）计算 `t_hw_us` (`508.40048484848484 us`)，且未使用 Hardware-Anchored Performance 公式 `HAP = (T_baseline - T_HW) / ((T_cand - T_HW) + (T_baseline - T_HW))` 计算 `hap_score` (`0.8429360983266381`)；
2. **Layer 2 周期流水线回边 (`distance=1`) 求解错误**：直接取单级最大耗时 `200.0 ns`，而未按 `load (100ns) -> mma (200ns) -> store (50ns) -> load (distance=1)` 环路求得 `minimum_period_ns = minimum_tile_ii_ns = 350.0 ns`；
3. **Layer 3 UB 子图融合的 GM 读写双倍消除与 UB 容量校验缺失**：消除 `producer` (`matmul`) 与 `consumer` (`aiv_cast`, `5.0 us`) 之间的 `1 MiB` GM 边时，会同时省去 producer 的 GM 写出与 consumer 的 GM 读入（`removable_gm_bytes = 2 * MiB`、`critical_path_saving_us = 5.0 us`），且必须校验 `live_buffers` 是否超出 `UB` 容量上限 (`248 KiB`) 而非 `L1`；
4. **Layer 4 A3 双 Die 集合通信层级缺失**：16 卡 A3 `all_reduce` 必须完整包含 `["d2d_intra_package", "d2d_intra_node", "d2d_inter_node"]` 三层拓扑；
5. **整网 `PhysicalCalibration` 的 `e2e_ms` 步数与算子 DAG `not_npu_measured` 标记错误**：生成 `N = generated_tokens` 个 token 时，首个 token 由 prefill `ttft_ms` 产出，后续仅有 `N - 1` 步 decode `tpot_ms`（即 `e2e_ms = ttft_ms + (generated_tokens - 1) * tpot_ms`），且 `physical_calibration` 状态应为 `"configured"` (`timing_scope = "device_event_warm"`，`applied_op_count = 452`)；`operator_plan` 的 `elapsed_ms` 应等于 `execution.makespan_ms` 且所有算子 `not_npu_measured = True`。

请修复 `vllm_ascend_diag/a3_sim_planner.py` 中的 `evaluate_a3_simulation_suite()`，使其在默认输入与 UB 容量超限扰动输入 (`ub_scratch_override_kib=300`) 下均通过校验。
```
</details>

<details>
<summary><b>② 用户模糊报障排障任务（6 个 L2 & L3 实机 NPU 任务：`dspark-mrv2` · `mrv2-dsa` · `k3-idle-dp` · `mtp-slot`）</b></summary>

#### 2.1 `dspark-mrv2-drafter-crash-zh-vague` & `l3-dspark-mrv2-drafter-crash-zh-vague`
```markdown
在昇腾上用 ModelRunner V2 跑 DeepSeek-V4 的 DSpark / EAGLE 投机解码时服务启动后直接崩了，出现了两个连环报错：一是 DeepSeek-V4 模型初始化时没有在 PP 最后一级（`is_last_rank`）且开启 `use_eagle()` 或 `uses_draft_model()` 时初始化 `_mtp_hidden_buffer`，前向报 `AttributeError`；二是 DSA attention 的 `build_for_drafting` 在计算 `block_table` 步长时错误地除以了 `self.block_size` 而不是 `self.storage_block_size`。

报错日志如下，帮我把这两处修一下：

AttributeError: 'DeepseekV4ForCausalLM' object has no attribute '_mtp_hidden_buffer' (when speculative_config.use_eagle() or uses_draft_model() is enabled on PP last rank)
RuntimeError: DSA build_for_drafting block_table stride mismatch: divided by self.block_size instead of self.storage_block_size
```

#### 2.2 `mrv2-dsa-prefill-metadata-zh-vague` & `l3-mrv2-dsa-prefill-metadata-zh-vague`
```markdown
我们在开启 ModelRunner V2（MRV2）跑 DeepSeek DSA 注意力架构并打开 MTP 投机解码时，prefill 和 draft 阶段的 attention metadata 状态不对，KV cache shape 接口签名也报参数不匹配，甚至在投机步更新 `seq_lens` 时把 DSA 的序列长度重复加了 1，导致推理直接崩掉。

现场报错如下，帮我把 MRV2 下 DSA 的 metadata 链路修好：

TypeError: AscendDSABackend.get_kv_cache_shape() takes 5 positional arguments but 6 were given (missing cache_dtype_str: str | None = None)
AssertionError: CommonAttentionMetadata.is_prefilling is None in MRV2 prepare_attn / build_draft_attn_metadata_factory, and _ascend_update_seq_lens unexpectedly mutated seq_lens for DSA architecture
```

#### 2.3 `k3-idle-dp-gdn-state-zh-vague`
```markdown
我们在多机 DP（外部启动器 `external_launcher`）环境下跑 Kimi-K3 / Qwen3-Next 这种带 GDN 线性注意力（Mamba 状态）的模型时，发现偶发输出乱码和精度崩坏。排查发现当某个 DP rank 没有分到真实请求（`total_num_scheduled_tokens == 0`）时，runner 为了参与 DP 集合通信会执行 1 个 token 的 `_dummy_run(1)`，结果把 GDN 的 recurrent state（`causal_conv1d` / KDA 状态）沿着旧请求遗留的 state indices 往前推进了一步，污染了正常请求的状态缓存。

AssertionError: Idle DP rank _dummy_run(1) advanced GDN recurrent state on stale non_spec_state_indices_tensor
```

#### 2.4 `mtp-draft-slot-mapping-capacity-zh-vague`
```markdown
我们在开启 DCP4 + MTP5（`num_speculative_tokens = 5`）跑投机解码服务时，一个 batch 展开后的 draft slot 数量超过了 `slot_mapping` 缓冲区长度，在 CPU 赋值和 Eagle3 全图 warmup 的 `aclnnInplaceCopy` 阶段直接越界崩了。排查发现 `BlockTable` 和 `AscendSpecDecodeBaseProposer.slot_mapping_group` 还在用旧的 `max_num_batched_tokens + 2 * max_num_reqs` 固定冗余，在 `num_speculative_tokens > 3` 时容量不够。

ValueError: could not broadcast input array from shape (110,) into shape (104,) in BlockTable.compute_slot_mapping
RuntimeError: aclnnInplaceCopy failed during Eagle3 full-graph warmup: BlockTable slot_mapping (8208) vs AscendSpecDecodeBaseProposer.slot_mapping_group (8200)
```
</details>

<details>
<summary><b>③ `G3` 跨任务经验沉淀飞轮任务（6 个 L2 & L3 黑盒 `.so` / 投机解码配对任务：`Seed -> Eval`）</b></summary>

#### 3.1 黑盒 `.so` RoPE 缓存维度任务对（L2 `cpu-rope-rotary-dim-64/32` & L3 实机 NPU `rope-rotary-dim-64/32`）
- **前置任务（Seed：`rope-rotary-dim-64-zh-vague`）**：
  ```markdown
  我们在昇腾 NPU 上跑一个自定义头维度的模型（`head_size=128`，`hf_text_config` 只配了显式的 `rotary_dim=64`，没有配 `partial_rotary_factor`），在更新 RoPE 旋转位置编码缓存（`set_cos_and_sin` / `update_cos_sin`）时直接报张量维度不匹配崩了。
  报错堆栈如下，帮我定位并修一下源码（要求保持现有 `partial_rotary_factor` 最高优先级与完整 `head_size` 默认行为不变，当未配置 `partial_rotary_factor` 但 `hf_text_config` 存在有效 `rotary_dim` 时使用 `rotary_dim`）：
  RuntimeError: The expanded size of the tensor (128) must match the existing size (64) at non-singleton dimension 3. Target sizes: [1, 3, 1, 128]. Tensor sizes: [3, 1, 64]
  ```
- **下游盲测任务（Eval：`rope-rotary-dim-32-zh-vague` —— 仅给报错堆栈，且底层 `.so` 已剥离 `.cpp` 源码）**：
  ```markdown
  换了一组模型头维度配置后，在昇腾 NPU 上跑旋转位置编码缓存更新又崩了，报错如下，帮我直接定位并修复源码里的 RoPE 缓存维度计算逻辑：
  RuntimeError: The expanded size of the tensor (128) must match the existing size (32) at non-singleton dimension 3. Target sizes: [1, 3, 1, 128]. Tensor sizes: [3, 1, 32]
  ```

#### 3.2 SFA 多步 MTP 投机解码缓冲区任务对（`sfa-mtp-seq-lens-seed-zh-vague` $\to$ `sfa-mtp-seq-lens-eval-zh-vague`）
- **下游评测任务（Eval：`sfa-mtp-seq-lens-eval-zh-vague`）**：
  ```markdown
  开启 SFA 注意力后端跑多步 MTP 投机解码时，我们发现 `draft_index=1` 和 `draft_index=2` 生成出来的 `AscendSFAMetadata` 共享并互相覆盖了同一个 `actual_seq_lengths_query` / `actual_seq_lengths_key` 缓冲区，导致每个投机步的序列长度全部串掉，报错如下，帮我修一下：
  AssertionError: AscendSFAMetadataBuilder._build overwrote draft step 1 actual_seq_lengths_query and actual_seq_lengths_key when building draft step 2 (expected per-draft-step speculative buffer selection for draft_index >= 1)
  ```
</details>

<details>
<summary><b>④ `G4` 开放式三因子融合与留一法消融探索任务（4 个 L2 & L3 实机 NPU 任务：`mode="reuse" -> mode="explore"`）</b></summary>

#### 4.1 `dsv4-sparse-mla-qli-fusion-rsi-zh` & `l3-dsv4-sparse-mla-qli-fusion-rsi-zh`
```markdown
我们在昇腾 910B (A2) 上调优 `DeepSeek-V4` (`Flash`/`Pro`, W8A8) 的 `SparseMLA` 解码路径（`vllm_ascend/models/deepseek_v4/sparse_mla_decode.py`）。

前期的第一阶段调优记录在 `logs/dsv4_stage1_l3_attempt.json`：我们已经按照常规 `L3` 工作流配置了 `DSV4_BLOCK_SIZES = 128` 与 `ENABLE_INDEXER_OVERLAP = True`，但连续两轮尝试均未收敛（`verdict: "unsupported"`）：
1. 每层 `qr_i8` 的反量化、`RMSNorm` 与吸收权重 `W_Q` 投影及 `RoPE` 切片拼接仍然产生 3 次多余的 GM `TensorMove` 拷贝；
2. 在调用 `npu_quant_lightning_indexer` 前，对 `q_indexer` 和 `k_indexer` 显式调用 `.contiguous()` 又产生了 2 次多余的 `TensorMove` 克隆；
3. 在 `npu_quant_lightning_indexer` 与 `npu_sparse_flash_attention` 交接处，主机端对 `seqused_k.max().item()` 做了同步读取（触发 D2H 同步），且当长序列尾部 `topk_indices` 含 `-1` 填充槽位时直接写入 `block_table`，导致 `AICore invalid GM address` 报错。

请你完成定位与深度探索重构，实现三项可分离变换因子的开关参数与 `run_ablation_suite()` 函数（返回四组消融实验结果），运行消融验证并在仓库根目录生成实验台账 `experiment-ledger.jsonl`（记录 baseline、完整候选及三组留一法消融的 `run_id`、`arm`、`verdict` 与关键指标）和总结报告 `PROGRESS.md`。
```

#### 4.2 `triton-spatial-norm-dim-merge-rsi-zh` & `l3-triton-spatial-norm-dim-merge-rsi-zh`
```markdown
我们在昇腾 910B (A2, 48 VectorCores, 192KB UB) 上调优 4D 空间分组归一化规约算子 `vllm_ascend/ops/spatial_group_norm_reduce.py`（输入形状 `[N, C, H, W]`，`bfloat16`）。

前期的第一阶段调优记录在 `logs/operator_stage1_l3_attempt.json`：我们已经按照常规 `L3` Tiling 工作流将 1D Persistent Grid 钳制到了物理 VectorCore 数量 `grid = (min(total_tiles, NUM_VECTOR_CORES),)`，但连续两轮尝试仍然停滞（`verdict: "unsupported"`，耗时 `51.4 ms`，且最大绝对误差 `0.0184` 超出 `5e-3` 门禁）：
1. 算子内部仍保留 `c -> h -> w` 三层嵌套循环（`nested_loop_depth = 3`），在内层反复做标量 `sum` 累加与地址重算；
2. `block_size = 512` 固定写死，未根据 `192KB` UB 预算与活跃 `fp32` 缓冲区数量做 2 的幂次动态放大；
3. 在多趟规约（mean/var + normalize）路径上盲目开启了 `enable_multibuffer = True`（存在 UB 溢出风险），且中间部分和被截断回 `bfloat16` 并落盘了额外的 `fp32` GM 临时张量（`intermediate_gm_copies = 2`）。

请你完成定位与深度探索重构，实现 `select_optimal_block_size`、三项可分离变换因子及 `run_ablation_suite()` 函数，运行消融验证并在仓库根目录生成实验台账 `experiment-ledger.jsonl` 和总结报告 `PROGRESS.md`。
```
</details>

---

## 六、完整端到端复现手段（Reproducibility Guide）

任何开发者或评测人员均可按照以下四步完整复现本报告中的全部评测结果：

### 第一步：克隆评测器并校验任务 Soundness（`source=0.0, gold=1.0`）

```bash
git clone https://github.com/mindie-agent/mindie-bench.git
cd mindie-bench
uv sync --locked

# 校验 4 个专项组件真实 Agent 任务与 L2/L3 任务的零奖励/满奖励完备性
uv run python - <<'PY'
from pathlib import Path
from mindie_bench.models import ExperimentConfig
from mindie_bench.runner.orchestrator import check_soundness

cfg = ExperimentConfig.load(Path("configs/example.toml"))
for task_dir in sorted(Path("tasks/zh-vague").iterdir()):
    if (task_dir / "task.toml").is_file():
        receipt = check_soundness(task_dir, cfg, tier="l2", output=Path("/tmp/mindie-soundness") / task_dir.name)
        assert receipt["before_reward"] == 0.0 and receipt["after_reward"] == 1.0, receipt
        print(f"[PASS] {task_dir.name}: before=0.0 -> after=1.0")
PY
```

### 第二步：复现四宿主插件 `G0–G4` 准入门禁与协议验证

```bash
# 运行覆盖 codex / claude-code / kimi / dsh 四宿主的 G1-G4 全链路门禁测试
uv run pytest tests/test_four_harness_g1_g4.py tests/test_qualification_gate.py -q
```

### 第三步：复现 `codex + gpt-6.1-sol (xhigh)` 与 `dsh + deepseek-flash (max)` 的 `G0 / G1 / G2 / G3 / G4` 真实任务矩阵

1. **准备实验配置 `experiment.toml`**（以 `codex + gpt-6.1-sol (xhigh)` 为例；切换 `dsh` 时将 `[harness]` 的 `name` 设为 `"dsh"`、`model` 设为 `"deepseek-flash"`、`reasoning_effort` 设为 `"max"` 即可）：
   ```toml
   backend = "native"
   schema_version = "1.0"
   knowledge_runtime_read_paths = ["/path/to/knowledge-vllm-ascend", "/path/to/knowledge-operators"]
   runtime_read_paths = ["/path/to/mindie-bench/.venv", "/path/to/mindie-bench/src"]

   [component_revisions]
   coordinator = "55bb6bc6190cc688e61ce6694a427ff7dde75240"
   diagnostics = "838480afe86b5f677d16377f4eedfc84fcf4c761"
   knowledge   = "297c8d354d9082758d3775f0214e1adcefacdd27"
   npu-top     = "a3bc1ee73e9b840b4dd39e5ad46298ec9e3363ae"
   profiler    = "b90e6bca6577876e4695f0ae530bd1f893928ff8"
   remote-dev  = "0b3da7a34eb7443d6f396b3cdee8adc275f660f0"
   sim         = "81e60f1dc8b54ab512468fd7defd7410ff861875"

   [corpora.ascend]
   path = "/path/to/knowledge-vllm-ascend"
   commit = "d3d5bf6320e171d4a0f131a6f746858700e0c4cc"

   [corpora.operators]
   path = "/path/to/knowledge-operators"
   commit = "6f083f810c0d8eb77b9d7992ba96b19c51dfaf74"

   [groups.G0]
   knowledge_mode = "advisory"
   mcp_servers = {}

   [groups.G1.mcp_servers.remote-dev]
   command = "/path/to/venv/bin/python"
   args = ["-I", "-m", "remote_dev.mcp.server"]
   component = "remote-dev"
   env = { HOME = "{profile}/home", REMOTE_DEV_STATE_DIR = "{profile}/remote-dev-state" }

   [groups.G2]
   knowledge_mode = "explicit"
   skills_path = "/path/to/mindie-agent-codex/plugins/mindie-agent/skills"
   [groups.G2.mcp_servers.remote-dev]
   command = "/path/to/venv/bin/python"
   args = ["-I", "-m", "remote_dev.mcp.server"]
   component = "remote-dev"
   env = { HOME = "{profile}/home", REMOTE_DEV_STATE_DIR = "{profile}/remote-dev-state" }
   [groups.G2.mcp_servers.knowledge]
   command = "/path/to/venv/bin/python"
   args = ["-I", "-m", "mindie_bench.integrations.first_party", "knowledge-mcp", "--corpus", "{corpus}", "--state", "{profile}/knowledge-store"]
   component = "knowledge"
   required_tools = ["knowledge_query", "knowledge_explain"]

   [harness]
   name = "codex"
   executable = "/opt/homebrew/bin/codex"
   expected_version = "codex-cli 0.153.4"
   # 注：home/codex/gpt-6.1-sol 与 http://127.0.0.1:3425/v1 为作者内部计量网关路由别名；
   # 外部复现时可直接改为公开端点（如 https://api.openai.com/v1）与公开模型名（如 gpt-5 / o3）
   model = "home/codex/gpt-6.1-sol"
   reasoning_effort = "xhigh"
   api_protocol = "openai-responses"
   provider_url = "http://127.0.0.1:3425/v1"
   api_key_env = "MINDIE_BENCH_RELAY_KEY"
   ```

2. **执行 `mindie-bench run` 端到端矩阵评测并输出结构化战报**（注：标准子命令为 `mindie-bench run`；`mindie-bench v0.4.2` 同时提供 `mindie-bench matrix` 兼容别名）：
   ```bash
   uv run mindie-bench run \
     --config experiment.toml \
     --tasks tasks/zh-vague/profiler-msprof-straggler-and-hbm-fix-zh \
     --tasks tasks/zh-vague/sim-a3-ub-fusion-and-pipeline-dispatch-zh \
     --tasks tasks/zh-vague/diagnostics-cann-plog-cascade-root-cause-fix-zh \
     --tasks tasks/zh-vague/npu-top-and-coordinator-multi-die-lease-repair-zh \
     --tier l2 \
     --groups G0,G2 \
     --repetitions 1 \
     --output /tmp/mindie-bench-010-repro
   ```

### 第四步：复现 L3 实机昇腾 NPU（`Ascend950DT` / `910B` / `910C`）评测与 `G3 / G4` 闭环

在 `experiment.toml` 中配置 `[remote]` 与 `[remote.component_runtime]`（绑定远端昇腾容器、指定物理 NPU 卡号 `devices = [4]` 以及 `coordinator`、`npu-top`、`diagnostics`、`remote-dev`、`knowledge` 五大远端受管组件路径），即可一键复现 L3 真机实验：

```bash
# 复现 L3 实机 NPU 上的 G3 经验飞轮（Seed 蒸馏 -> Eval 检索命中）
uv run mindie-bench run \
  --config l3-experiment.toml \
  --tasks tasks/zh-vague/rope-rotary-dim-64-zh-vague \
  --tasks tasks/zh-vague/rope-rotary-dim-32-zh-vague \
  --tier l3 \
  --groups G3,G2,G1,G0 \
  --output /tmp/mindie-bench-010-l3-g3

# 复现 L3 实机 NPU 上的 G4 受控因子图谱三因子融合探索（mode="reuse" -> mode="explore"）
uv run mindie-bench run \
  --config l3-rsi-experiment.toml \
  --tasks tasks/zh-vague/l3-dsv4-sparse-mla-qli-fusion-rsi-zh \
  --tasks tasks/zh-vague/l3-triton-spatial-norm-dim-merge-rsi-zh \
  --tier l3 \
  --groups G4,G2,G0 \
  --output /tmp/mindie-bench-010-l3-g4
```


# MindIE-Bench 与 0.1.0 Benchmark 真实性审计及 2026-10-29 行为级复判报告

[返回文档中心](../README.md) · [English Docs](../README.en.md) · [审计证据 JSON](2026-10-23-mindie-bench-integrity-evidence.json)

本文包含两部分：
1. **2026-10-29 行为级 Oracle 全量加固与历史归档零模型复判结果**（第 6 节及顶部摘要）：覆盖全部 20 个任务的真实子进程行为级判分器改造、109 项三态与顶层辅助函数/类控制实跑校验，以及对 `agent-trials-109.json` 中 74 轮主实验候选补丁的零模型重判账本；
2. **2026-10-23 初始真实性审计记录**（第 1–5 节）：完整保留初始发现的问题、负对照证据与证据分层边界，供对照追溯。

---

## 0. 2026-10-29 闭环摘要：20 任务行为级判分器加固与 74 轮历史主实验零模型重判

针对 2026-10-23 审计指出的静态 AST/字符串匹配判分、辅助函数提取误判与证据范围混用问题，`mindie-bench` 已于 2026-10-29 完成全部 **20 个任务的真实子进程行为级 Oracle 加固** 与 **历史归档零模型复判**（详见 `mindie-bench` 仓库 `reports/integrity-20261029/README.md` 与 `summary.json`）：

- **20 个任务 × 109 项真实子进程控制 100% 通过（`all_three_state_and_helpers_passed = true`）**：
  - 移除静态源码/字符串匹配判据，所有任务均在真实子进程中导入或加载目标模块并执行行为级与数值断言；
  - 全部 20 个任务均通过 `base`（未修复基线必败，`reward = 0.0`）、`negative_control`（无功能/常量负对照必败，`reward = 0.0`）、`gold`（标准修复必过，`reward = 1.0`）以及顶层辅助函数/辅助类提取变体（`helper` / `helper_class` 必过，`reward = 1.0`）的实跑检验，合计 **109 项控制点全部通过，0 次模型调用**。
- **74 / 109 轮历史主实验候选补丁零模型重判账本**：
  - 在不重跑付费模型、不修改原始 `agent-trials-109.json` 耗时与 Token 账本的前提下，对归档中保存了候选补丁的 **74 轮主实验 Trial**（原记录为 `58 completed_pass`、`15 completed_fail`、`1 unknown`）执行统一行为级重判：
    - `completed_pass -> 1.0`：**49 轮**（历史通过，经真实行为执行确认通过）
    - `completed_pass -> 0.0`：**9 轮**（历史静态裁判通过，但未通过真实行为断言）
    - `completed_fail -> 1.0`：**5 轮**（历史因提取顶层辅助函数/类被旧 AST 裁判误拒，经真实行为执行恢复通过）
    - `completed_fail -> 0.0`：**9 轮**（继续未通过行为断言）
    - `completed_fail -> unmeasured (None)`：**1 轮**（`unsupported_cpu_execution`，仅支持 NPU 真机执行）
    - `unknown -> 1.0`：**1 轮**（已保存补丁经真实行为执行通过，原始运行状态仍保留 `unknown`）
  - **重判合计**：74 轮具备候选产物的历史主实验中，**55 轮通过行为级验收（`reward = 1.0`）**、**18 轮未通过行为断言（`reward = 0.0`）**、**1 轮记为 `unmeasured`**。其余 35 轮未保存可重放工作区补丁的历史记录显式标记为 `unmeasured (missing_archived_candidate_diff)`。

---

## 1. 2026-10-23 初始审计范围与直接验证（历史记录保留）

审计日期：2026-10-23。审计源码：`mindie-bench@0d051cd3413bfb851ba9fd7f68dc1372e2c590a9`（当时 `v0.4.2` 标签）。审计对象包括已发布的 [MindIE Agent v0.1.0](https://github.com/mindie-agent/mindie-agent/releases/tag/v0.1.0) 附件。

机器可读的逐记录核对、源码版本、裁判哈希、负对照输入与输出保存在 [审计证据 JSON](2026-10-23-mindie-bench-integrity-evidence.json)。原始大文件沿用现有 trial 目录；未复制整个运行库，也未重跑付费模型或 NPU 工作负载。

- 静态扫描 158 个生产 Python 模块，追踪指标生成、判分、汇总和报告路径；检查主评测对应的全部 20 个任务定义及裁判。
- 核对 109 条主评测、55 条补充/重试 receipt；检查原生事件流和轨迹结构、主要指标、源码摘要、冻结 oracle 和候选产物。主记录为 `84 completed_pass / 23 completed_fail / 2 unknown`。
- 审查 5 个组件场景，以及发布微基准中的 20 个 case、96 个 attempt。分析了不同证据集合之间是否发生拼接和范围扩大。
- 通过 GitHub 读取线上 release、标签和附件摘要；关键 value/Agent 清单与本地 SHA-256 一致。
- 实际执行了 6 个当时 AST 裁判、6 个与原 receipt 哈希匹配的历史 AST 裁判，以及历史/当前 G4 各一个负对照；重新计算组件 gate，并用零 Agent study 输入重新生成报告。

---

## 2. 109 条主评测的初始分类（2026-10-23 审计时状态）

下表记录 2026-10-23 审计时各任务的旧版裁判状态（2026-10-29 升级后的行为级裁判分类与重判结果见第 6 节）：

| 裁判/任务范围 | 任务定义数 | 主记录数 | 当时可以保留的解释 | 当时不能由此推出的解释 |
| --- | ---: | ---: | --- | --- |
| DSpark L2/L3、K3 idle-DP、MTP slot、SFA-MTP Seed/Eval：旧 AST/字符串检查 | 6 | 34 | 真实 Agent 执行，以及满足特定源码形态 | 功能修复正确、真实模型/NPU 故障已闭合 |
| MRV2 DSA L2/L3：AST + 提取函数的 CPU 小样本 | 2 | 12 | 局部接口/CPU 张量分支检查 | 模型实际启动、分布式/Ascend runtime 正确 |
| G4 SparseMLA/SpatialNorm L2/L3：张量/消融与成本代理混合 | 4 | 24 | 候选产出、部分张量正确性、约定的消融字段 | 原生融合算子性能、真实端到端 TPOT 收益 |
| profiler/sim/diagnostics/npu-top+coordinator 离线修复题 | 4 | 16 | 在受控夹具上真实运行 Agent 和组件的修复表现 | 新采集的现场故障、HBM 或硬件吞吐实测 |
| CPU RoPE Seed/Eval | 2 | 12 | 18 组 CPU 张量正确性用例 | NPU 或完整模型验收 |
| NPU RoPE Seed/Eval | 2 | 11 | 有明确设备断言、独立参考和同步的 NPU 张量正确性验证 | 完整模型服务或硬件性能验收 |
| 合计 | 20 | 109 | 各类证据按实际范围使用 | 不合并成 109 次同等强度的 NPU 工程验收 |

---

## 3. 2026-10-23 已确认发现（F01–F09）

### F01 / P0：报告生成器曾写入固定实验结论摘要

责任代码：`mindie-bench` `src/mindie_bench/value_release.py`。早期 `markdown()` 函数包含未从当前输入 study 动态计算的固定文字摘要。后续版本已移除硬编码摘要并改为完全按实际输入生成。

### F02 / P0：策略选择 pilot 旧默认执行器读取判分答案合成续跑结果

责任代码：`mindie-bench` `src/mindie_bench/evaluation/strategy_selection.py`。旧默认 `shared_prefix_executor` 曾读取 `private_judge` 构造续跑成功与否及固定耗时。该组 pilot 不在 `0.1.0` 的 109 条主记录中；后续已将合成续跑与真实宿主执行严格分离。

### F03 / P0：G4 的成本公式/Python shim 与真实硬件性能边界需明确区分

发布结论位置：[value-results.md](../releases/0.1.0/value-results.md)。G4 算子融合任务在基线中使用受控张量契约与成本模型检验融合与留一法消融（`controlled_cpu_tensor_and_ablation_contract`），应明确标注为受控张量与消融契约验证，不与真实 NPU 端到端 TPOT 实测混同。

### F04 / P0：6 个旧裁判曾可被无功能源码通过（已于 2026-10-29 升级为真实子进程行为级 Oracle 并完成重判）

`dspark-mrv2-drafter-crash-zh-vague`、`l3-dspark-mrv2-drafter-crash-zh-vague`、`k3-idle-dp-gdn-state-zh-vague`、`mtp-draft-slot-mapping-capacity-zh-vague`、`sfa-mtp-seq-lens-eval-zh-vague` 与 `sfa-mtp-seq-lens-seed-zh-vague` 的早期 `verifier/test.sh` 依赖 AST/字符串检查。2026-10-29 已将全部 20 个任务升级为真实子进程行为级判分器（支持顶层辅助函数/类提取），并对历史候选补丁完成了零模型重判（见第 6 节）。

### F05 / P1：独立组件微基准与受控夹具 Agent 任务的证据边界分离

[value-results.md](../releases/0.1.0/value-results.md) 中独立组件基准（`value_profiler.py`、`value_diagnostics.py`、`value_coordinator.py`、`value_sim.py`）与 4 道受控离线夹具 Agent 修复题（`controlled_offline_fixture`）使用不同输入集合，现已分别标注各自的数据源与验证范围。

### F06 / P1：P0–P4 离线 replay 的 Token 预算演算与真实会话账单区分

[0.1.0 发布说明](../releases/0.1.0.md) 与 [组件报告](../releases/0.1.0/component-value-results.md) 中的 `4,814–5,599 tokens` 为确定性 runtime/replay 预算上限验证，与真实 Agent 会话的端到端模型计费 Token 分别统计。

### F07 / P1：`release_gate` 组件门禁与端到端 Agent 评测分离

组件 `release_gate` 用于验证各仓库发布时的确定性基准与契约完整性，不替代端到端多任务 Agent 评测。

### F08 / P1：保留 `unknown` 原始状态与冻结裁判身份

历史 `agent-trials-109.json` 中的 `unknown` 记录严格保留原始状态；重判账本单独记录 `rejudged_reward`，不覆盖原始执行回执。

### F09 / P1：组件夹具、历史锚点与真机实测分层标注

各组件的受控夹具测试、历史真机重放与常驻 A2/A3/A5 真机实测均按实际执行环境显式标注。

---

## 4. 原始数据完整性核验结论

1. **原始 Agent 执行记录真实完整**：164 条 receipt（109 条主记录 + 55 条补充/重试）全部可定位，无 trial ID 内容冲突，原生事件流和 trajectory 均完整存在。
2. **CPU / NPU RoPE 张量精度验证真实有效**：NPU RoPE 裁判包含明确的 NPU 设备断言、独立参考真值与设备同步。
3. **微基准计时器真实有效**：各组件 `benchmark-results.json` 均由真实计时器运行产生。

---

## 5. 修复路线完成状态

| 阶段 | 核心动作 | 当前状态 |
| --- | --- | --- |
| **1. 明确证据分层边界** | 在 README、发布说明与架构文档中明确区分 CPU 行为验证、受控组件夹具、G4 张量消融契约与 NPU 真机验证 | **已完成** |
| **2. 全部 20 任务升级为真实子进程行为级 Oracle** | 移除 AST/字符串通过判据，支持合法顶层 helper 函数与类提取，通过 109 项三态与变体实跑检验 | **已完成（2026-10-29）** |
| **3. 历史归档零模型行为级重判** | 对保存了候选补丁的 74 轮主实验执行零模型行为级重判，公开完整前后对照账本 | **已完成（2026-10-29）** |

---

## 6. 2026-10-29 行为级 Oracle 全量加固与历史归档复判详情

### 6.1 20 个任务的验证范围分类与三态控制结果

全部 20 个任务按实际验证底座分为五类，每一类均通过 `base`（`0.0`）、`negative_control`（`0.0`）、`gold`（`1.0`）及辅助函数/类变体（`1.0`）子进程实跑校验：

| 验证范围分类 (`verification_scope`) | 涵盖任务（共 20 个） | 行为级 Oracle 验证内容 |
| --- | --- | --- |
| **`cpu_behavior`**（8 个任务） | `dspark-mrv2-drafter-crash-zh-vague`、`l3-dspark-mrv2-drafter-crash-zh-vague`、`k3-idle-dp-gdn-state-zh-vague`、`mtp-draft-slot-mapping-capacity-zh-vague`、`sfa-mtp-seq-lens-seed-zh-vague`、`sfa-mtp-seq-lens-eval-zh-vague`、`mrv2-dsa-akc-bsa-sfa-line-zh-vague`、`l3-mrv2-dsa-akc-bsa-sfa-line-zh-vague` | 在隔离子进程中加载候选修复代码（含提取的顶层 helper 函数/类），构造多步 Draft/Verify、Idle-DP、Slot Mapping 与序列长度状态机输入，验证运行时行为与输出张量不变量 |
| **`controlled_offline_fixture`**（4 个任务） | `diagnostics-cann-plog-cascade-root-cause-fix-zh`、`npu-top-and-coordinator-multi-die-lease-repair-zh`、`profiler-msprof-straggler-and-hbm-fix-zh`、`sim-a3-ub-fusion-and-pipeline-dispatch-zh` | 在受控离线夹具上实际调用候选代码与组件接口，验证级联故障根因分离、双 Die 租约防冲突分配、慢卡/慢链路与显存归因、以及 UB 融合与流水线计算结果 |
| **`controlled_cpu_tensor_and_ablation_contract`**（4 个任务） | `dsv4-sparse-mla-qli-fusion-rsi-zh`、`l3-dsv4-sparse-mla-qli-fusion-rsi-zh`、`sd-vae-spatial-norm-fusion-rsi-zh`、`l3-sd-vae-spatial-norm-fusion-rsi-zh` | 注入多组随机张量与算子调用 Spy，验证候选融合实现的数值等价性、边界防御以及四阶段留一法消融（Ablation）实验契约 |
| **`cpu_tensor_correctness`**（2 个任务） | `ascend- cranial / rope seed & eval`（CPU RoPE 迁移任务） | 18 组跨形状、跨步长 CPU 张量数值精度比对 |
| **`npu_tensor_correctness`**（2 个任务） | `ascend-npu rope seed & eval`（NPU RoPE 黑盒 `.so` 迁移任务） | 在昇腾 NPU 设备上执行真实算子调用、设备驻留断言、同步与独立 Golden 张量精度比对 |

### 6.2 74 轮历史主实验零模型重判转移矩阵

对 `docs/releases/0.1.0/agent-trials-109.json` 中包含可重放工作区补丁的 **74 轮主实验**（另有 35 轮历史归档不含工作区 diff，记为 `missing_archived_candidate_diff`）执行行为级重判的结果如下：

| 原始记录状态 $\to$ 行为级重判结果 | 轮次数 (`Trials`) | 说明 |
| --- | ---: | --- |
| **`completed_pass -> reward = 1.0`** | **49** | 原始通过，且候选补丁通过新行为级 Oracle 全部运行时断言 |
| **`completed_pass -> reward = 0.0`** | **9** | 原始静态裁判通过，但候选补丁在真实子进程行为断言下未通过（`behavior_assertion_failed`） |
| **`completed_fail -> reward = 1.0`** | **5** | 候选补丁逻辑正确，此前仅因提取了顶层 helper 函数/类或局部结构差异被旧 AST 裁判误判失败，现恢复为通过 |
| **`completed_fail -> reward = 0.0`** | **9** | 原始失败，重判确认仍未通过行为断言 |
| **`completed_fail -> unmeasured (None)`** | **1** | 需 NPU 专用运行时环境（`unsupported_cpu_execution`），离线 CPU 重判记为未测量 |
| **`unknown -> reward = 1.0`** | **1** | 会话超时前已写入完整正确补丁并通过行为级验证（主回执执行状态仍保留 `unknown`） |
| **已重判小计** | **74** | **55 轮行为级通过（`1.0`） · 18 轮行为断言失败（`0.0`） · 1 轮未测量（`None`）** |

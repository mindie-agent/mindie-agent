# MindIE Agent 0.1.8 端到端 RSI 自动切换与 C6 沉淀 A/B 评测报告（Ascend 950DT / A5 场景受控 CPU 契约基准）

## 1. 实验目标、评测边界与核心结论

本实验面向 **Ascend A5 (`Ascend 950DT` / `[Ascend950DT]`)** 业务问题场景，在严格**单一变量控制（Single-Variable Control）**与**受控 CPU 张量/消融契约评测边界（`validation_scope = "controlled_cpu_tensor_and_ablation_contract"`）**下，端到端评测 MindIE Agent 的两大核心机制：
1. **自动切换（Automatic `reuse -> explore` Promotion）**：在相同初始自然语言模糊提示词与完全同源的共享初始语料视图（`G2` 与 `G4` 共享完全一致的 `task_digest`、`corpus_commit` 与 `corpus_view_sha256`，共享相同的 `L1–L3` 排障工作流指引，无组间差异化提示词干预）下，Agent 先按 `reuse` / `diagnose` 模式检索 `L1–L3` 知识单元并尝试阶段性候选修改；当单因子常规手段无法同时满足多因子耦合契约、工作区账本（`logs/experiment-ledger.jsonl`）累计满 `>= 3` 个具有不同 `candidate_sha256` 的被证伪（`verdict="refuted"`）实验记录后，知识库引擎在下一次 `knowledge_query(mode="reuse")` 时自动将生效模式提升为 `effective_mode="explore"`（首次晋升全部满足 `auto_switched_from_reuse=True` 且全程 `caller_initiated_explore=False`），挂载并返回 `L4` Mutator 契约。
2. **受控契约通过率对比与 C6 本地自动沉淀（Controlled Contract Pass Rate & Local C6 Distillation）**：对比**物理禁用 `L4` 探索的对照组 (`G2`，`MINDIE_DISABLE_RSI_EXPLORE=1`)** 与**开启 RSI 自动切换 + Stop 阶段 `graded-c6` 沉淀的实验组 (`G4`)** 在双宿主（**Codex CLI `gpt-6.1-sol (xhigh)`** 与 **DSH CLI `deepseek-flash (max)`**）上的受控契约通过率与本地 Git 沉淀成功率。

### 核心汇总指标（16 组端到端实验：`4 任务 × 2 宿主 × 2 组`，每单元格单次运行）

| 评测维度 | Control 对照组 (`G2` 禁用 `L4` 探索) | Treatment 实验组 (`G4` 自动切 RSI + C6) | 净差异 ($\Delta$) |
| :--- | :---: | :---: | :---: |
| **受控评测契约总通过率 (`reward=1.0`)** | **0 / 8 (0.0%)** | **8 / 8 (100.0%)** | **+100.0 pp** |
| **Codex (`gpt-6.1-sol xhigh`) 契约通过率** | 0 / 4 (0.0%) | **4 / 4 (100.0%)** | **+100.0 pp** |
| **DSH (`deepseek-flash max`) 契约通过率** | 0 / 4 (0.0%) | **4 / 4 (100.0%)** | **+100.0 pp** |
| **首次 `reuse -> explore` 自动晋升触发率** | 0 / 8 (0.0%, 物理锁定 `reuse`) | **8 / 8 (100.0%, `caller_initiated_explore=False`)** | **+100.0 pp** |
| **账本实际记录的独立证伪候选哈希数 (`ledger_distinct_refuted_candidates`)** | **每组 `3..8` 个（合计 35 个）** | **每组 `3..5` 个（晋升门限处均 `>= 3`）** | 两组均真实执行多轮试错 |
| **C6 Stop 自动提炼与本地裸 Git 仓库沉淀率** | N/A (未启用) | **8 / 8 (100.0%, `completed:applied`)** | **8 / 8 本地提交可回读** |

> **方法学边界说明（Scope & Limitations）**：
> - **受控 CPU 契约评测 vs 真机 NPU 性能实测**：全部 16 组实验收据均显式标注 `validation_scope="controlled_cpu_tensor_and_ablation_contract"`、`performance_status="unmeasured"`、`native_kernel_status="unverified"`。本实验验证的是在受控 CPU 张量探针与消融/结构契约下的机制闭环，不代表真机 Ascend 950DT 端到端吞吐/时延加速比。
> - **无组间差异化辅导（No Differential Coaching）vs 共享 `L3` 工作流引导**：`G2` 与 `G4` 共享相同的 `L1–L3` 语料库；`L3` 单元中包含分阶段假设验证、账本记录与再次调用 `mode="reuse"` 的共享工作流说明（因此两组 Agent 均在账本中记录了 `>= 3` 个独立证伪候选哈希），但两组的初始提示词与 `L1–L3` 语料完全一致，且工作区公开测试文件不含明文私有消融函数名或因子键。
> - **数值正确性与完整消融契约的区分**：评测器要求同时满足数值/结构正确性与 `L4` 消融报告契约（例如 `codex/G2/mla-prolog` 的修复在基础张量检查上达到了 `correctness_verified=true, max_abs_error=0.0`，但因缺乏 `L4` 消融报告契约而得分为 `reward=0.0`；此外 `mla-prolog`、`dsv4-sparse-mla`、`triton-spatial-norm` 校验了完整的四臂留一法 CPU 消融输出，而 `dspark` 校验了三项结构修复契约与 `full_candidate` 探针）。

---

## 2. 实验任务与业务输入设计（4 个受控任务 Fixture）

全部 4 个任务均采用一句自然语言模糊问题 + Ascend 950DT 环境描述 + 日志路径（3 个 `vllm-ascend` 框架任务仅提供服务拉起命令、压测命令与日志路径，不提供独立复现 `.py` 脚本；1 个单算子任务提供 `benchmarks/reproduce_spatial_group_norm.py`）：

| 任务 ID | 任务类型 | 目标场景描述 | 业务触发方式（Prompt 输入） | 受控评测契约要求（`verifier/verify.py`） |
| :--- | :--- | :--- | :--- | :--- |
| `vllm-ascend-mla-prolog-rope-kvcache-fusion-rsi-zh` | `vllm-ascend` 框架 | `Ascend 950DT` (TP8, BF16) | `vllm serve DeepSeek-V4` + `vllm bench serving` + `logs/vllm_mla_prolog_a5.log` | 合并 Q/KV 投影 + 向量化 RoPE + 消除默认 $1/8$ 网格截断（`max_abs_err <= 0.02`）与逐槽位 `.item()` 同步，并通过四臂留一法 CPU 消融校验 |
| `dsv4-sparse-mla-qli-fusion-rsi-zh` | `vllm-ascend` 框架 | `Ascend 950DT` (TP8, W8A8/QLI-v2) | `vllm serve DeepSeek-V4` + `vllm bench serving` + `logs/vllm_dsv4_sparse_mla_a5.log` | 设备侧 `clamp_min(0)` 越界索引防护 + 融合 Q 反量化/RMSNorm/RoPE + 消除冗余 `.clone()`，并通过四臂留一法 CPU 消融校验 |
| `vllm-ascend-dspark-mtp-aclgraph-d2h-rsi-zh` | `vllm-ascend` 框架 | `Ascend 950DT` (TP8, MRV2 DSpark FULL) | `vllm serve DeepSeek-V4` (`--speculative-config dspark`) + `vllm bench serving` + `logs/vllm_dspark_aclgraph_a5.log` | draft ($3N$) 与 target ($4N$) 独立 token 分桶 + 消除捕获步内 `.item()` D2H 同步 + 复用持久缓冲，并通过结构与 `full_candidate` 探针契约校验 |
| `triton-spatial-norm-dim-merge-rsi-zh` | Triton-Ascend 单算子 | `Ascend 950DT` (48 Vector Core, UB 192KB) | `python3 benchmarks/reproduce_spatial_group_norm.py` + `logs/spatial_group_norm_a5.log` | 合并空间维度 `H*W` + UB 自适应 `BLOCK_SIZE` + FP32 方差/均值累加（`max_abs_err <= 5e-3`），并通过四臂留一法 CPU 消融校验 |

---

## 3. 16 组端到端实验逐项明细（`runs/track-RSI-E2E-v4`）

- **代码基线**：`vllm-ascend @ 1223fea314cb6172900bd615c9940fcd2c658925`
- **知识库语料基线（`G2` 与 `G4` 初始视图完全同源，其中 `G2` 物理剥离 `L4` blob）**：
  - `knowledge-vllm-ascend @ a64a959322b17944ac06e0dba30afbc9fe5d1480`（初始投影目录 `corpus_view_sha256 = 7a85facfe15ac80a91a48dad68f773599e09ae7966d8a156e04efc18dd5a79f7`）
  - `knowledge-operators @ 7ed7de63775b44c0f03cded26ad944fb58bcc0e5`（初始投影目录 `corpus_view_sha256 = a1d061a0e706cb431d85baa8c41adddf865ab2668c58862449f48f2e8125fe7a`）
- **汇总数据文件**：[`e2e_rsi_summary.json`](e2e_rsi_summary.json)
- **独立第三方审计报告**：[`independent_credibility_audit_v4_20261105.md`](independent_credibility_audit_v4_20261105.md) / [`astra_max_rsi_e2e_audit_v4.md`](astra_max_rsi_e2e_audit_v4.md)

| 宿主与模型 | 组别 | 任务 ID | 终端状态 | Reward | 耗时 (s) | 轮数 | 晋升门限证伪数 / 账本总独立证伪数 | 请求模式序列 (`requested_mode`) | 生效模式序列 (`effective_mode`) | 首次自动切 `explore` | C6 本地沉淀状态与准入单元 ID |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :--- | :--- | :---: | :--- |
| **Codex** (`gpt-6.1-sol xhigh`) | `G2` | `dsv4-sparse-mla-qli-fusion-rsi-zh` | `completed_fail` | `0.0` | 516.04 | 27 | `0 (已禁用) / 5` | `['reuse', 'reuse', 'reuse', 'reuse', 'reuse']` | `['reuse', 'reuse', 'reuse', 'reuse', 'reuse']` | `False` | N/A |
| **Codex** (`gpt-6.1-sol xhigh`) | `G4` | `dsv4-sparse-mla-qli-fusion-rsi-zh` | **`completed_pass`** | **`1.0`** | 568.93 | 59 | **`3 / 5`** | `['reuse', 'reuse', 'reuse', 'reuse', 'reuse', 'reuse']` | `['reuse', 'reuse', 'explore', 'explore', 'reuse', 'reuse']` | **`True`** | `completed:applied` (`unit-sparse-mla-qli-valid-count-handoff-validation` @ `b3f2c58c61`) |
| **Codex** (`gpt-6.1-sol xhigh`) | `G2` | `triton-spatial-norm-dim-merge-rsi-zh` | `completed_fail` | `0.0` | 562.00 | 29 | `0 (已禁用) / 4` | `['reuse', 'reuse', 'reuse', 'reuse', 'reuse', 'reuse', 'reuse', 'reuse']` | `['reuse', 'reuse', 'reuse', 'reuse', 'reuse', 'reuse', 'reuse', 'reuse']` | `False` | N/A |
| **Codex** (`gpt-6.1-sol xhigh`) | `G4` | `triton-spatial-norm-dim-merge-rsi-zh` | **`completed_pass`** | **`1.0`** | 564.12 | 50 | **`3 / 3`** | `['reuse', 'reuse', 'reuse', 'reuse', 'reuse', 'reuse']` | `['reuse', 'reuse', 'reuse', 'explore', 'reuse', 'reuse']` | **`True`** | `completed:applied` (`unit-spatial-group-norm-cpu-path-ablation` @ `7844a875c1`) |
| **Codex** (`gpt-6.1-sol xhigh`) | `G2` | `vllm-ascend-dspark-mtp-aclgraph-d2h-rsi-zh` | `completed_fail` | `0.0` | 600.01 | 24 | `0 (已禁用) / 8` | `['reuse', 'reuse', 'reuse', 'reuse', 'diagnose']` | `['reuse', 'reuse', 'reuse', 'reuse', 'reuse']` | `False` | N/A |
| **Codex** (`gpt-6.1-sol xhigh`) | `G4` | `vllm-ascend-dspark-mtp-aclgraph-d2h-rsi-zh` | **`completed_pass`** | **`1.0`** | 554.24 | 43 | **`3 / 3`** | `['reuse', 'reuse', 'reuse', 'reuse']` | `['reuse', 'explore', 'reuse', 'reuse']` | **`True`** | `completed:applied` (`unit-dspark-independent-token-buckets-validation` @ `f69e2fe644`) |
| **Codex** (`gpt-6.1-sol xhigh`) | `G2` | `vllm-ascend-mla-prolog-rope-kvcache-fusion-rsi-zh` | `completed_fail` | `0.0` | 332.93 | 17 | `0 (已禁用) / 4` | `['reuse', 'reuse', 'reuse']` | `['reuse', 'reuse', 'reuse']` | `False` | N/A |
| **Codex** (`gpt-6.1-sol xhigh`) | `G4` | `vllm-ascend-mla-prolog-rope-kvcache-fusion-rsi-zh` | **`completed_pass`** | **`1.0`** | 460.66 | 41 | **`3 / 3`** | `['reuse', 'reuse', 'reuse', 'reuse']` | `['reuse', 'explore', 'reuse', 'reuse']` | **`True`** | `completed:applied` (`unit-mla-prolog-cpu-ablation-and-rounding-triage` @ `f5e621c873`) |
| **DSH** (`deepseek-flash max`) | `G2` | `dsv4-sparse-mla-qli-fusion-rsi-zh` | `completed_fail` | `0.0` | 330.67 | 60 | `0 (已禁用) / 3` | `['reuse', 'reuse', 'reuse']` | `['reuse', 'reuse', 'reuse']` | `False` | N/A |
| **DSH** (`deepseek-flash max`) | `G4` | `dsv4-sparse-mla-qli-fusion-rsi-zh` | **`completed_pass`** | **`1.0`** | 334.95 | 60 | **`3 (首次晋升) -> 4 / 4`** | `['diagnose', 'reuse', 'diagnose', 'reuse', 'reuse']` | `['reuse', 'explore', 'explore', 'reuse', 'reuse']` | **`True`** | `completed:applied` (`unit-dsv4-sparse-mla-device-topk-guard` @ `cf55844668`) |
| **DSH** (`deepseek-flash max`) | `G2` | `triton-spatial-norm-dim-merge-rsi-zh` | `completed_fail` | `0.0` | 396.74 | 60 | `0 (已禁用) / 3` | `['reuse', 'reuse', 'reuse', 'reuse', 'reuse', 'reuse', 'diagnose', 'reuse']` | `['reuse', 'reuse', 'reuse', 'reuse', 'reuse', 'reuse', 'reuse', 'reuse']` | `False` | N/A |
| **DSH** (`deepseek-flash max`) | `G4` | `triton-spatial-norm-dim-merge-rsi-zh` | **`completed_pass`** | **`1.0`** | 374.00 | 55 | **`3 / 3`** | `['reuse', 'reuse', 'reuse', 'reuse', 'reuse', 'reuse']` | `['reuse', 'reuse', 'reuse', 'explore', 'reuse', 'reuse']` | **`True`** | `completed:applied` (`unit-spatial-group-norm-reduce-fp32-dim-merge-distilled-sop` @ `6d71d85a72`) |
| **DSH** (`deepseek-flash max`) | `G2` | `vllm-ascend-dspark-mtp-aclgraph-d2h-rsi-zh` | `completed_fail` | `0.0` | 453.73 | 60 | `0 (已禁用) / 4` | `['reuse', 'reuse', 'explore', 'reuse']` | `['reuse', 'reuse', 'reuse', 'reuse']` | `False` | N/A |
| **DSH** (`deepseek-flash max`) | `G4` | `vllm-ascend-dspark-mtp-aclgraph-d2h-rsi-zh` | **`completed_pass`** | **`1.0`** | 304.72 | 60 | **`3 / 3`** | `['reuse', 'reuse', 'reuse', 'reuse', 'reuse', 'reuse']` | `['reuse', 'reuse', 'reuse', 'explore', 'reuse', 'reuse']` | **`True`** | `completed:applied` (`unit-dspark-mtp-aclgraph-d2h-sync-candidate` @ `840c160f12`) |
| **DSH** (`deepseek-flash max`) | `G2` | `vllm-ascend-mla-prolog-rope-kvcache-fusion-rsi-zh` | `completed_fail` | `0.0` | 304.76 | 60 | `0 (已禁用) / 4` | `['reuse', 'reuse', 'reuse', 'reuse']` | `['reuse', 'reuse', 'reuse', 'reuse']` | `False` | N/A |
| **DSH** (`deepseek-flash max`) | `G4` | `vllm-ascend-mla-prolog-rope-kvcache-fusion-rsi-zh` | **`completed_pass`** | **`1.0`** | 196.91 | 35 | **`3 / 3`** | `['reuse', 'reuse', 'reuse', 'reuse']` | `['reuse', 'explore', 'reuse', 'reuse']` | **`True`** | `completed:applied` (`unit-vllm-ascend-mla-prolog-qkv-rope-kvcache-coalesce-distilled-sop` @ `4d7f88b43b`) |

---

## 4. 独立第三方审计（Codex `gpt-6-astra max`）核验结论

经 **Codex `gpt-6-astra (max)`** 逐项解包 16 组实验的原始产物并独立重放全部 16 组评测器，5 项核心工程与可信度检查全部 **PASS**（详见 [`independent_credibility_audit_v4_20261105.md`](independent_credibility_audit_v4_20261105.md)）：

1. **检查 1 — `G2` 与 `G4` 单一变量一致性（PASS）**：
   - 全部 8 对宿主/任务组合的 `task_digest`、`corpus_commit` 与初始 `corpus_view_sha256` 完全一致；初始系统/任务提示词在归一化试验目录路径后逐字一致，不存在组间语料分叉或差异化辅导。
2. **检查 2 — `G2` 物理级 `L4` 隔离（PASS）**：
   - `G2` 全部 40 次知识库查询均记录 `explore_disabled=true, effective_mode="reuse"`，两个原生知识库存储中物理包含 **0 个 `L4` 正文 blob**；即使 `dsh/G2/dspark` 在第 3 次查询显式请求 `mode="explore"`，也被强制降级为 `reuse`。
3. **检查 3 — `G4` 真实自动 `reuse -> explore` 晋升（PASS）**：
   - 全部 8 组 `G4` 实验的**首次** `explore` 晋升均由 `requested_mode="reuse"` 触发（`auto_switched_from_reuse=true`），且严格发生在工作区账本累计满 **3 个不同 `candidate_sha256` 的被证伪候选修复**之后（注：`dsh/G4/dsv4` 在第 2 次查询已完成 `reuse -> explore` 首次自动晋升，随后第 3 次查询为 `diagnose -> explore` 故该次 `auto_switched_from_reuse=false`）；全部 41 次 `G4` 查询请求仅使用 `'reuse'` 或 `'diagnose'`（`caller_initiated_explore=false`）。
4. **检查 4 — 工作区公开测试文件零明文契约泄露（PASS）**：
   - 4 个公开测试文件（`test_mla_prolog.py`、`test_dsv4_sparse_mla.py`、`test_dspark_speculator.py`、`test_spatial_group_norm_reduce.py`）均未以明文泄露私有消融入口或因子键名（采用 SHA-256 摘要校验）。
5. **检查 5 — 评测器独立重放与 C6 本地 Git 沉淀完整性（PASS）**：
   - 独立沙箱重放 16 组评测器 100% 复现 `G4` `8/8` (`reward=1.0`) 与 `G2` `8/8` (`reward=0.0`)；全部 8 组 `G4` 的 `knowledge-private/local_knowledge.git` 提交均存在、可从 `HEAD` 访问、通过 `git fsck --full` 且包含新准入的 Markdown 知识单元。

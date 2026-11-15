# MindIE Agent `0.1.7` 八大组件与 `G0–G5` 全矩阵基准实测报告（V2：100% 真实 `vllm-ascend` 场景版）

[English](g0-g5-vllm-ascend-v2-report.en.md) · [返回 `0.1.7` 发布说明](../0.1.7.md) · [全量 144 场 Trial 汇总 (`g0-g5-vllm-ascend-v2-summary.json`)](g0-g5-vllm-ascend-v2-summary.json) · [34 题三道门禁账本 (`g0-g5-vllm-ascend-v2-audit-manifest.json`)](g0-g5-vllm-ascend-v2-audit-manifest.json)

- **评测完成日期**：2026-11-03
- **产品发布版本**：`v0.1.7`（对应 [`channels/0.1.json`](../../../channels/0.1.json) 锁定组合与 [`mindie-bench v0.4.6`](https://github.com/mindie-agent/mindie-bench/releases/tag/v0.4.6)）
- **归档凭据**：
  - 机器可读全量汇总：[`g0-g5-vllm-ascend-v2-summary.json`](g0-g5-vllm-ascend-v2-summary.json)（`144` 个完整 Trial Receipts，含逐题耗时、TTFE、轮次、Input/Cached/Output Tokens、Skill 读取、知识检索与组件调用明细）
  - 三道门禁审计账本：[`g0-g5-vllm-ascend-v2-audit-manifest.json`](g0-g5-vllm-ascend-v2-audit-manifest.json)（`gate1_passed = true`、`gate2_passed = true`，`34/34` 题 Soundness `0.0 -> 1.0`）
  - `mindie-bench` 仓库本地完整复现包：`reports/g0-g5-vllm-ascend-v2-20261103/`（含 `reproduce.sh` 与 `run_v2_matrix.py`）
- **被测原生宿主与模型配置（严格限定双主力配置）**：
  - **Codex (`codex-cli 0.153.4`)**：`gpt-6.1-sol`，`reasoning_effort = "xhigh"`，插件 [`mindie-agent-codex`](https://github.com/mindie-agent/mindie-agent-codex)
  - **DSH (`0.2.0-rc.2`)**：`deepseek-flash` (`dsv4.1-flash`)，`reasoning_effort = "max"`，插件 [`mindie-agent-dsh`](https://github.com/mindie-agent/mindie-agent-dsh)
- **八大共享组件与知识库覆盖**：
  - `mindie-knowledge`（整合语料 `108` units `vllm-ascend` + `knowledge-operators`）、`remote-dev`、`mindie-coordinator`、`npu-top`、`mindie-diagnostics`、`mindie-debugger`、`mindie-profiler`、`mindie-sim`
- **Ascend A5 / A3 真机集群**：A5 `177.31.22.1`、`177.31.25.1`、`177.31.27.1`、`177.31.28.1`（容器 `ylf_pro0813_20261025`，`Ascend910_9599` 8 卡节点）与常备 A3 `192.168.13.156`

---

## 一、八大共享组件与机制实测收益总览（Executive Quantitative Summary）

| 共享组件 | 核心能力与技术机制 | 代表性 `vllm-ascend` 真实场景题目 | Codex (`gpt-6.1-sol` `xhigh`) 实测收益 (`G0 -> G2/G4`) | DSH (`deepseek-flash` `max`) 实测收益 (`G0 -> G2/G4`) | 核心量化结论 |
| --- | --- | --- | --- | --- | --- |
| **`mindie-debugger`** | 4 层确定性排障（CANN Plog 级联溯源 + Attention NaN Hook + `MemoryWatchpoint` 原地踩踏捕获 + W8A8 逐层 Heal/Diff + ACLGraph Capture/Replay） | **Track 1D（4 道 L2 + 1 道 A5 L3 真机）**：`D1` FIA MTP、`D2` GDN/DSpark 踩踏、`D3` FusedMoE W8A8、`D4`/`D4-L3` ACLGraph | • 通过率：`100% -> 100%` (`5/5`)<br>• **D1–D4 平均耗时：`254.3s -> 168.3s`（提速 `1.51x`，`-33.8%`）**<br>• **Output Tokens：`12,914 -> 7,809`（节省 `-39.5%`）**<br>• `D4` ACLGraph：耗时 `219.7s -> 103.3s`（**`2.13x` 提速**），Tokens `-54.1%` | • **通过率：`80.0% (4/5) -> 100.0% (5/5)`（`+20.0%` 破零满贯！）**<br>• `D4` ACLGraph：**`0.0 (FAIL) -> 1.0 (PASS, TTFE 83.2s)`**<br>• `D3` FusedMoE W8A8：耗时 `207.9s -> 128.7s`（**`1.62x` 提速**，TTFE `144.5s -> 52.7s` **`2.74x` 提速**）<br>• `D4-L3` A5 真机：自发调用 `debugger` MCP `4` 次 + `remote-dev` `67` 次，`1.0` 通过 | **将大模型盲目猜改转化为确定性单点二分，DSH 解出率直拉 `100%`（`+20%`），Codex 排障耗时缩短 `33.8%`、输出 Token 节省 `39.5%`** |
| **`mindie-sim`** | 昇腾 Roofline / UB 容量门槛 / Async KV 显存预算 / EPLB All2All 通信偏斜 / MLA Decode 结构化建模与代码静态检查 | **Track 1S（`S1` Async KV Budget、`S2` EPLB Skew、`S3` Graph Fusion UB、`S4` MLA Decode Structure）** | • 通过率：`100%` (`4/4`)<br>• `S2` EPLB Skew：耗时 `152.5s -> 129.3s`（**`-15.2%`**），Output Tokens `-9.7%`<br>• `S4` MLA Decode：自发调用 `mindie-tools` `4` 次 + `knowledge_query` `1` 次，一次精准消除冗余 FP32 Cast | • 通过率：`100%` (`4/4`)<br>• `S4` MLA Decode：自发调用工具 `6` 次 + 知识检索 `4` 次，**耗时 `196.1s -> 170.1s`（`-13.3%`），Output Tokens `25,020 -> 20,635`（`-17.5%`）**<br>• `S1` Async KV：自发执行 `mindie-sim` `6` 次验证双步 Token 峰值 | **无需上真机即可在毫秒级完成 UB 溢出、显存预算与冗余 Cast 静态把关，MLA Decode 优化 Token 消耗降低 `17.5%`** |
| **`mindie-profiler`** | `msprof` 多卡慢卡归因（剔除 HCCL 等待虚高）+ HBM Peak Envelope 非可加对账 + RSI 算子闭环验证 (`validate`) | **Track 1S (`P1` Straggler & HBM) + Track G4 (`V4` MLA Prolog RSI + `triton` + `dsv4`)** | • `P1` 耗时：`197.2s -> 181.3s`（**`-8.1%`**，TTFE `177.2s -> 157.7s`，轮次 `13 -> 11`），自发调用 `mindie-profiler`<br>• `V4` MLA Prolog RSI：**TTFE 从 `182.9s (G0)` 缩短至 `120.2s (G4)`（定位提速 `1.52x`）** | • **`V4` MLA Prolog RSI：从 `G0 = 0.0 (FAIL)` 跃升至 `G2/G4 = 1.0 (PASS)`！**<br>• **`V4` 中 `G4` 相比 `G2` 耗时从 `554.9s -> 467.0s`（提速 `1.19x`），Output Tokens 从 `103,432 -> 82,329`（节省 `-20.4%`）** | **精准剥离多卡通信等待假象与无效融合分支，驱动算子自演进从 `0.0 -> 1.0` 破零并节省 `20.4%` 探索 Token** |
| **`mindie-coordinator` + `npu-top`** | A3/A5 双 Die 拓扑感知、NUMA 亲和绑核、ModelSlim 量化 Safetensors Header 零权重预检、真机租约防冲突 | **Track 1M (`C1` Multi-Die Topology、`C2` ModelSlim Preflight) + Track 1C (`D4-L3`)** | • 通过率：`100%` (`C1`, `C2`, `D4-L3`)<br>• **`C1` 双 Die 绑核 TTFE：`228.7s -> 92.8s`（首次有效修改提速 `2.46x`，`-59.4%`）**<br>• **`C2` ModelSlim 预检 TTFE：`137.5s -> 73.9s`（提速 `1.86x`，轮次 `13 -> 10`）**<br>• `D4-L3` 真机：自发调用 `coordinator` `7` 次 | • 通过率：`100%` (`C1`, `C2`, `D4-L3`)<br>• `C1`：自发调用 `mindie_coordinator` / `npu-top` `5` 次 + 知识检索 `4` 次<br>• `C2`：轮次从 `44 -> 38`（**`-13.6%`**） | **真机零冲突租约仲裁 + 零权重分配 Safetensors 预检，Codex 定位多 Die 拓扑与量化配置缺陷提速 `1.86x–2.46x`** |
| **`mindie-diagnostics`** | 崩溃诊断包自动采集、敏感凭证（AK/SK/Token/私有路径）零残留脱敏、Outbox 状态诚实账本（`completed` vs `failed` vs `unknown`） | **Track 1M (`DG1` Observability Crash Redaction & Outbox) + Standing A3 外部抢占检测** | • 通过率：`100%` (`1.0`)<br>• 轮次从 `13 (G0) -> 11 (G2)`（**`-15.4%`**），一次性补齐异常链递归脱敏与 `os.replace` 原子回执 | • 通过率：`100%` (`1.0`)<br>• TTFE `75.9s`，一次性修复 `failed_pre_send` / `unknown_post_send` 状态边界与 Token 脱敏 | **100% 拦截崩溃包凭证泄露，严格区分发送前失败与超时未知态，彻底杜绝静默吞错与重复重放** |
| **`remote-dev`** | 本地-远端昇腾容器双向同步、后台作业流式监控、真实 NPU 算子/模型闭环执行 | **Track 1C（A5 真机 `D4-L3` + A3 真机 `rope-rotary-dim-32`）** | • `D4-L3` A5 真机：`G0/G1/G2` 全部 **`1.0` (`PASS`)**，`G2` 通过 `remote-dev` + `coordinator` 跑通容器内验证 | • `rope-rotary-dim-32` 真机：`G1` 发起 `89` 次 `remote-dev` 调用拿满 **`1.0` (`PASS`)**（同题纯 CPU L2 Cold 为 `0.0`）<br>• `D4-L3` A5 真机：`G1` (`64` 次 `remote-dev`) 与 `G2` (`67` 次 `remote-dev`) 全部 **`1.0` (`PASS`)** | **打通本地 IDE/CLI 到远端昇腾容器的最后一公里，在纯 CPU 无法复现的算子精度问题上实现真机 `0.0 -> 1.0` 闭环** |
| **`mindie-knowledge`** | 四级渐进披露（`L0` Index -> `L1` Axiom -> `L2` SOP -> `L3/L4` Code/Ops）+ C6 轨迹自动蒸馏飞轮 (`G3`/`G5`) | **Track 1A（6 道 `vllm-ascend` 核心 L2）+ Track G3（3 组 Seed->Eval 蒸馏对）+ Track G5（5 轮演进）** | • **Track 1A 通过率：`33.3% (2/6) -> 50.0% (3/6)`（`+16.7%`）**，平均耗时 `373.3s -> 308.8s`（**`-17.3%`**），Output Tokens `-15.4%`<br>• `dspark-mrv2`：**`0.0 (538.4s) -> 1.0 (281.9s, 1.91x 提速)`**<br>• **G3 Pair 3 (`KDA Varlen`)**：Warm 比 G0 轮次减少 **`-35.7%`** (`14 -> 9`)、Tokens 减少 **`-36.5%`** | • **Track 1A 通过率：`16.7% (1/6) -> 50.0% (3/6)`（3 倍跃升，`+33.3%`！）**，自发发起 `26` 次 `knowledge_query`/`explain`<br>• **G3 Pair 1 (`Partial RoPE`)**：Cold **`0.0` -> Warm `1.0` 破零**<br>• **G3 Pair 3 (`KDA Varlen`)**：Warm 比 Cold 提速 **`1.30x`** (`341.8s -> 262.5s`)、TTFE `-23.1%`、Tokens `-21.2%` | **领域知识将 `vllm-ascend` 疑难缺陷解出率提升至 `3.0x`（DSH `16.7% -> 50.0%`）；C6 自动蒸馏让后续同族任务直接命中新卡片，耗时立降 `23%–36%`** |

---

## 二、三道门禁审核结果（Three-Gate Audit Verification）

| 门禁维度 | 审核标准 | 实测审核结果 | 审计证据路径 |
| --- | --- | --- | --- |
| **Gate 1：题目与 Prompt 纯净度审核** | 1. 100% 题目基于真实 `vllm_ascend/...` 生产模块，**零 `vllm_ascend_diag` 人造教学桩**<br>2. 100% `instruction.md` 为自然口语化「一句话现象 + 原始报错/日志路径」，**零工具名剧透**（正则扫描 `mindie-*` / `npu-top` / `remote-dev` / `mcp__` 为 `0` 命中）<br>3. 100% 题目通过 `verify-soundness`（`before_reward = 0.0`、`after_reward = 1.0`） | **`PASS` (`34 / 34` Tasks 100% 达标)** | [`g0-g5-vllm-ascend-v2-audit-manifest.json`](g0-g5-vllm-ascend-v2-audit-manifest.json) |
| **Gate 2：测试过程真实性审核** | 1. **基线零污染**：所有 `G0` Trial 中 `knowledge_queries == 0`、`component_cli_counts == {}`、`remote_dev_calls == 0`<br>2. **自发触发**：所有 `G2`/`G3`/`G4` 工具调用均由模型根据报错现象与 Skill/MCP 描述自发决策调用<br>3. **防作弊校验**：所有 `resolved = true` 的 Trial 均真实修改 `vllm_ascend/...` 源码并通过防硬编码消融验证（如 `V1` 非对称 TP `(8,2)`/`(8,4)`/`(4,4)`、`S1` 动态 `num_speculative_tokens`、`V4` Leave-One-Out 消融） | **`PASS` (`144 / 144` Trials 0 违规)** | [`g0-g5-vllm-ascend-v2-audit-manifest.json`](g0-g5-vllm-ascend-v2-audit-manifest.json) (`gate2_violations: []`) |
| **Gate 3：结果完整性与可复现审核** | 每一个 Trial 目录均完整保留 `trial_receipt.json`、`trajectory.json`、`native_events.jsonl`、`final_patch.diff`、`verifier.stdout`；Token 账本满足 `provider_total == input_uncached + input_cached + output` | **`PASS` (`144 / 144` Trials 完整落盘)** | [`g0-g5-vllm-ascend-v2-summary.json`](g0-g5-vllm-ascend-v2-summary.json) |

---

## 三、分 Track 逐题实测详表（Complete Trial-by-Trial Quantitative Tables）

### 3.1 Track 1D：`mindie-debugger v0.1.0` 专项矩阵（4 道 L2 + 1 道 A5 真机 L3，共 22 Trials）

> **测试目标**：验证四层调试能力——（D1）CANN Plog 级联报错溯源与 Attention Mask 数值注入定位、（D2）GDN/DSpark `MemoryWatchpoint` 原地 Buffer 踩踏捕获、（D3）FusedMoE W8A8 动态量化逐层 Heal & Diff 精度修复、（D4 & D4-L3）ACLGraph Capture/Replay 静态地址与 Padding 槽位污染修复。

| 任务 ID（真实修改模块） | 宿主 | `G0` 结果（耗时 / TTFE / 轮次 / Out Tokens） | `G2` 结果（耗时 / TTFE / 轮次 / Out Tokens / 触发行为） | `G2` vs `G0` 量化收益 |
| --- | --- | --- | --- | --- |
| **`D1`**：`vllm-ascend-fia-mtp-plog-cascade-triage-zh`<br>(`vllm_ascend/attention/sfa_v1.py`, `worker/model_runner_v1.py`) | `codex` | `1.0` (`304.4s` / `90.8s` / `20t` / `15,168 tok`) | **`1.0` (`247.7s` / `118.5s` / `20t` / `12,327 tok` / `Skill=5`)** | **耗时缩短 `-18.6%`（`1.23x`），Output Tokens 节省 `-18.7%`** |
| **`D1`**：`vllm-ascend-fia-mtp-plog-cascade-triage-zh` | `dsh` | `1.0` (`224.3s` / `142.3s` / `60t` / `25,434 tok`) | **`1.0` (`251.7s` / `251.6s` / `60t` / `23,777 tok` / `debugger=1, KQ=3`)** | **自发调用 `debugger` MCP + `3` 次知识检索，Output Tokens 节省 `-6.5%`** |
| **`D2`**：`vllm-ascend-gdn-dspark-inplace-stomp-watch-zh`<br>(`vllm_ascend/ops/triton/gdn_chunk_meta.py`, `attention/sfa_v1.py`) | `codex` | `1.0` (`303.5s` / `119.6s` / `16t` / `15,294 tok`) | **`1.0` (`197.8s` / `137.5s` / `17t` / `7,470 tok` / `Skill=3`)** | **耗时缩短 `-34.8%`（`1.53x` 提速），Output Tokens 节省 `-51.2%`！** |
| **`D2`**：`vllm-ascend-gdn-dspark-inplace-stomp-watch-zh` | `dsh` | `1.0` (`310.4s` / `188.1s` / `60t` / `40,686 tok`) | **`1.0` (`241.8s` / `201.3s` / `60t` / `36,881 tok` / `KQ=5`)** | **耗时缩短 `-22.1%`（`1.28x` 提速），Output Tokens 节省 `-9.4%`** |
| **`D3`**：`vllm-ascend-fused-moe-w8a8-heal-diff-zh`<br>(`vllm_ascend/quantization/methods/w8a8_dynamic.py`) | `codex` | `1.0` (`189.5s` / `107.7s` / `13t` / `11,080 tok`) | **`1.0` (`124.3s` / `106.4s` / `9t` / `6,793 tok` / `Skill=3`)** | **耗时缩短 `-34.4%`（`1.52x` 提速），轮次 `-30.8%`，Output Tokens `-38.7%`** |
| **`D3`**：`vllm-ascend-fused-moe-w8a8-heal-diff-zh` | `dsh` | `1.0` (`207.9s` / `144.5s` / `43t` / `23,635 tok`) | **`1.0` (`128.7s` / `52.7s` / `34t` / `20,867 tok` / `Entry=1`)** | **耗时缩短 `-38.1%`（`1.62x` 提速），TTFE 提速 `2.74x` (`144.5s -> 52.7s`)，轮次 `-20.9%`** |
| **`D4`**：`vllm-ascend-aclgraph-capture-and-replay-zh`<br>(`vllm_ascend/compilation/acl_graph.py`, `worker/model_runner_v1.py`) | `codex` | `1.0` (`219.7s` / `58.8s` / `13t` / `10,115 tok`) | **`1.0` (`103.3s` / `61.5s` / `8t` / `4,646 tok` / `Skill=3`)** | **耗时缩短 `-53.0%`（`2.13x` 提速），轮次 `-38.5%` (`13 -> 8`)，Output Tokens `-54.1%`！** |
| **`D4`**：`vllm-ascend-aclgraph-capture-and-replay-zh` | `dsh` | **`0.0` (`FAIL`, `225.0s` / `60t` / `30,649 tok`)** | **`1.0` (`PASS`, `216.5s` / `TTFE 83.2s` / `60t` / `32,219 tok`)** | **实现 `0.0 -> 1.0` 破零！TTFE 从 `134.1s` 缩短至 `83.2s`（`-38.0%`）** |
| **`D4-L3`（A5 真机）**：`l3-vllm-ascend-aclgraph-capture-and-replay-zh` | `codex` | `1.0` (`345.9s` / `47.2s` / `21t` / `12,518 tok`) | **`1.0` (`430.2s` / `103.6s` / `28t` / `rdev=4, coord=7`)** | 真机容器内自发调用 `coordinator` `7` 次 + `remote-dev` `4` 次完成真机验证 |
| **`D4-L3`（A5 真机）**：`l3-vllm-ascend-aclgraph-capture-and-replay-zh` | `dsh` | `1.0` (`120.7s` / `33t` / `12,754 tok`) | **`1.0` (`383.6s` / `TTFE 74.1s` / `rdev=67, debugger=4`)** | 真机容器内自发调用 `debugger` MCP `4` 次 + `remote-dev` `67` 次完成真机闭环 |
| **Track 1D 汇总（5 题，双宿主）** | **合计** | **Codex `5/5 (100%)`；DSH `4/5 (80.0%)`** | **Codex `5/5 (100%)`；DSH `5/5 (100.0%)`** | **DSH 通过率 `+20.0%` 升至 `100%`；Codex L2 均耗 `-33.8%` (`1.51x`)、Tokens `-39.5%`** |

---

### 3.2 Track 1S：`mindie-sim` + `mindie-profiler` 专项矩阵（5 道 L2，共 20 Trials）

> **测试目标**：验证架构级与算子级性能建模/剖析能力——（S1）异步调度 + MTP 投机解码 KV Cache 显存预算建模、（S2）EPLB 动态专家重排与 Chunked Prefill All2All 偏斜建模、（S3）Graph Fusion Pass 昇腾 UB 容量 Roofline 门控、（S4）MLA Decode 结构化 Profiler/Sim 联动消除冗余 FP32 Cast、（P1）多卡 `msprof` 慢卡归因（扣除 HCCL 等待）与非可加 HBM Peak 对账。

| 任务 ID（真实修改模块） | 宿主 | `G0` 结果（耗时 / TTFE / 轮次 / Out Tokens） | `G2` 结果（耗时 / TTFE / 轮次 / Out Tokens / 触发行为） | 核心机制验证与亮点 |
| --- | --- | --- | --- | --- |
| **`S1`**：`vllm-ascend-async-scheduling-kv-vram-budget-zh`<br>(`vllm_ascend/core/sched_config.py`, `worker/model_runner_v1.py`) | `codex` | `1.0` (`139.7s` / `57.4s` / `10t` / `7,025 tok`) | **`1.0` (`146.8s` / `129.7s` / `9t` / `8,394 tok` / `Skill=3`)** | 轮次从 `10 -> 9`（`-10.0%`），通过动态 `num_speculative_tokens` 泛化校验 |
| **`S1`**：`vllm-ascend-async-scheduling-kv-vram-budget-zh` | `dsh` | `1.0` (`129.5s` / `60.9s` / `31t` / `20,517 tok`) | **`1.0` (`222.4s` / `95.3s` / `48t` / `36,189 tok` / `mindie-sim=6, KQ=2`)** | **DSH 自发调用 `mindie-sim` 命令行与 Python 接口 `6` 次 + 知识检索 `2` 次**，精准建模双步异步在途 Token 峰值 |
| **`S2`**：`vllm-ascend-eplb-and-chunked-prefill-skew-zh`<br>(`vllm_ascend/distributed/eplb_state.py`, `ops/fused_moe.py`) | `codex` | `1.0` (`152.5s` / `115.4s` / `10t` / `8,080 tok`) | **`1.0` (`129.3s` / `112.0s` / `9t` / `7,300 tok` / `Skill=3`)** | **耗时缩短 `-15.2%`（`1.18x` 提速），轮次 `-10.0%`，Output Tokens `-9.7%`** |
| **`S2`**：`vllm-ascend-eplb-and-chunked-prefill-skew-zh` | `dsh` | `1.0` (`168.4s` / `80.4s` / `36t` / `27,620 tok`) | **`1.0` (`271.0s` / `99.6s` / `47t` / `43,818 tok` / `Entry=1`)** | 完整对齐 EPLB 专家负载偏斜阈值与 All2All 通信分块调度 |
| **`S3`**：`vllm-ascend-graph-fusion-pass-ub-roofline-zh`<br>(`vllm_ascend/compilation/passes/add_rms_norm_quant_fusion.py`) | `codex` | `1.0` (`85.9s` / `72.7s` / `7t` / `5,729 tok`) | **`1.0` (`132.9s` / `104.5s` / `9t` / `7,845 tok` / `Skill=1`)** | 精准植入昇腾 910B UB 192KB 容量上限与尾块对齐门控 |
| **`S3`**：`vllm-ascend-graph-fusion-pass-ub-roofline-zh` | `dsh` | `1.0` (`106.0s` / `33.3s` / `23t` / `16,363 tok`) | **`1.0` (`131.7s` / `61.2s` / `28t` / `23,190 tok` / `Entry=1`)** | 100% 通过多 Shape UB 容量边界与 fallback 门控验证 |
| **`S4`**：`vllm-ascend-mla-decode-profiler-sim-structure-zh`<br>(`vllm_ascend/attention/mla_v1.py`) | `codex` | `1.0` (`204.4s` / `170.5s` / `15t` / `9,115 tok`) | **`1.0` (`239.7s` / `181.1s` / `14t` / `11,521 tok` / `profiler=4, KQ=1`)** | **Codex 自发调用 `mcp__mindie-tools__profiler` `4` 次 + `knowledge_query` `1` 次**，轮次 `15 -> 14` |
| **`S4`**：`vllm-ascend-mla-decode-profiler-sim-structure-zh` | `dsh` | `1.0` (`196.1s` / `120.3s` / `50t` / `25,020 tok`) | **`1.0` (`170.1s` / `160.7s` / `50t` / `20,635 tok` / `profiler=6, KQ=4`)** | **DSH 自发调用 `profiler` MCP `6` 次 + 知识检索 `4` 次，耗时缩短 `-13.3%`，Output Tokens 节省 `-17.5%`！** |
| **`P1`**：`vllm-ascend-profiler-straggler-and-hbm-reconcile-zh`<br>(`vllm_ascend/profiling/msprof_reconciler.py`) | `codex` | `1.0` (`197.2s` / `177.2s` / `13t` / `9,485 tok`) | **`1.0` (`181.3s` / `157.7s` / `11t` / `9,090 tok` / `mindie-profiler=1`)** | **Codex 自发调用 `mindie-profiler`，耗时缩短 `-8.1%`，TTFE `-11.0%`，轮次 `-15.4%` (`13 -> 11`)** |
| **`P1`**：`vllm-ascend-profiler-straggler-and-hbm-reconcile-zh` | `dsh` | `1.0` (`194.8s` / `126.1s` / `39t` / `32,585 tok`) | **`1.0` (`218.4s` / `157.0s` / `50t` / `37,486 tok` / `KQ=1`)** | 完整修复 `msprof` 慢卡有效计算耗时归因与 HBM Peak Envelope 非可加对账 |

---

### 3.3 Track 1M：`mindie-coordinator` + `npu-top` + `mindie-diagnostics` 专项矩阵（3 道 L2，共 12 Trials）

> **测试目标**：验证硬件拓扑调度、量化预检与可观测性脱敏——（C1）A3/A5 双 Die 物理拓扑识别与跨 NUMA 绑核修正、（C2）ModelSlim Safetensors Header 零权重预检拦截形状/量化描述不匹配、（DG1）崩溃诊断包凭证递归脱敏与 Outbox 原子状态回执。

| 任务 ID（真实修改模块） | 宿主 | `G0` 结果（耗时 / TTFE / 轮次 / Out Tokens） | `G2` 结果（耗时 / TTFE / 轮次 / Out Tokens / 触发行为） | `G2` vs `G0` 量化收益 |
| --- | --- | --- | --- | --- |
| **`C1`**：`vllm-ascend-multi-die-topology-and-cpu-binding-zh`<br>(`vllm_ascend/platform.py`, `worker/worker_v1.py`) | `codex` | `1.0` (`285.4s` / `228.7s` / `21t` / `13,891 tok`) | **`1.0` (`274.8s` / `92.8s` / `18t` / `16,233 tok` / `Skill=3`)** | **TTFE 从 `228.7s -> 92.8s`（定位提速 `2.46x`，`-59.4%`！），轮次 `-14.3%` (`21 -> 18`)** |
| **`C1`**：`vllm-ascend-multi-die-topology-and-cpu-binding-zh` | `dsh` | `1.0` (`342.0s` / `137.8s` / `47t` / `55,623 tok`) | **`1.0` (`498.0s` / `230.8s` / `60t` / `87,542 tok` / `coord/npu-top=5, KQ=4`)** | **DSH 自发调用 `mindie_coordinator` / `npu-top` `5` 次 + 知识检索 `4` 次**完成双 Die 拓扑验证 |
| **`C2`**：`vllm-ascend-modelslim-quant-header-preflight-zh`<br>(`vllm_ascend/quantization/modelslim_config.py`) | `codex` | `1.0` (`189.6s` / `137.5s` / `13t` / `11,835 tok`) | **`1.0` (`200.0s` / `73.9s` / `10t` / `11,022 tok` / `Skill=3`)** | **TTFE 从 `137.5s -> 73.9s`（定位提速 `1.86x`，`-46.3%`！），轮次 `-23.1%` (`13 -> 10`)，Tokens `-6.9%`** |
| **`C2`**：`vllm-ascend-modelslim-quant-header-preflight-zh` | `dsh` | `1.0` (`208.9s` / `71.2s` / `44t` / `37,371 tok`) | **`1.0` (`226.1s` / `73.7s` / `38t` / `40,477 tok` / `Entry=1`)** | **轮次从 `44 -> 38`（减少 `-13.6%`）**，零大张量分配完成 Safetensors Header 预检 |
| **`DG1`**：`vllm-ascend-observability-crash-redaction-and-outbox-zh`<br>(`vllm_ascend/observability/crash_reporter.py`) | `codex` | `1.0` (`157.6s` / `123.5s` / `13t` / `9,664 tok`) | **`1.0` (`186.4s` / `157.2s` / `11t` / `10,207 tok` / `Skill=1`)** | **轮次从 `13 -> 11`（减少 `-15.4%`）**，完整实现递归异常链脱敏与诚实 Outbox 状态机 |
| **`DG1`**：`vllm-ascend-observability-crash-redaction-and-outbox-zh` | `dsh` | `1.0` (`236.5s` / `77.0s` / `40t` / `43,425 tok`) | **`1.0` (`381.3s` / `75.9s` / `52t` / `69,022 tok` / `Entry=1`)** | TTFE 保持 `75.9s`（`-1.4%`），100% 通过凭证脱敏与 `unknown` 状态诚实度校验 |
| **Track 1M 汇总（Codex 3 题平均）** | `codex` | `100%`（平均 TTFE `163.2s`，平均轮次 `15.7t`） | **`100%`（平均 TTFE `108.0s` [`-33.8%`]，平均轮次 `13.0t` [`-17.2%`]）** | **Codex 平均首次有效修改时间（TTFE）缩短 `33.8%`，交互轮次减少 `17.2%`** |

---

### 3.4 Track 1A：`mindie-knowledge` 核心 `vllm-ascend` 疑难缺陷消融（6 道 L2 × `G0/G1/G2`，共 36 Trials）

| 任务 ID（真实修改模块） | 宿主 | `G0`（裸 Agent） | `G1`（仅 `remote-dev` 桥，0 知识） | `G2`（完整八组件 + 108-unit 知识库） | `G2` 核心收益与触发证据 |
| --- | --- | --- | --- | --- | --- |
| `dspark-mrv2-drafter-crash-zh-vague`<br>(`vllm_ascend/worker/v2/model_runner.py` 等) | `codex` | `0.0` (`538.4s` / `30t` / `23,583 tok`) | `0.0` (`380.0s` / `24t` / `19,223 tok`) | **`1.0` (`281.9s` / `23t` / `14,179 tok` / `KQ=2`)** | **`0.0 -> 1.0` 破零！耗时缩短 `-47.6%` (`1.91x`)，Tokens 节省 `-39.9%`** |
| `dspark-mrv2-drafter-crash-zh-vague` | `dsh` | `0.0` (`338.1s` / `60t` / `39,170 tok`) | `0.0` (`250.7s` / `60t` / `33,445 tok`) | **`1.0` (`223.4s` / `60t` / `38,118 tok` / `KQ=3`)** | **`0.0 -> 1.0` 破零！耗时缩短 `-33.9%` (`1.51x`)，TTFE 缩短 `-46.8%`** |
| `mrv2-dsa-prefill-metadata-zh-vague`<br>(`vllm_ascend/attention/sfa_v1.py` 等) | `codex` | `0.0` (`257.7s` / `17t` / `12,612 tok`) | `0.0` (`259.4s` / `16t` / `12,256 tok`) | `0.0` (`259.3s` / `18t` / `11,992 tok`) | 高难多文件 MRV2 + DSA 元数据耦合场景 |
| `mrv2-dsa-prefill-metadata-zh-vague` | `dsh` | `0.0` (`593.0s` / `120t` / `76,236 tok`) | `0.0` (`424.0s` / `85t` / `59,405 tok`) | **`1.0` (`471.7s` / `TTFE 125.4s` / `KQ=11`)** | **`0.0 -> 1.0` 破零！自发发起 `11` 次知识检索，TTFE 从 `412.8s -> 125.4s` (`3.29x` 提速)** |
| `k3-idle-dp-gdn-state-zh-vague`<br>(`vllm_ascend/worker/model_runner_v1.py`) | `codex` | `0.0` (`348.3s` / `18t` / `15,349 tok`) | `0.0` (`280.8s` / `18t` / `9,874 tok`) | `0.0` (`169.3s` / `12t` / `7,732 tok`) | 负向边界收敛提速 `2.06x` (`348.3s -> 169.3s`) |
| `k3-idle-dp-gdn-state-zh-vague` | `dsh` | `0.0` (`306.4s` / `60t` / `34,579 tok`) | `0.0` (`196.7s` / `60t` / `22,735 tok`) | `0.0` (`258.0s` / `60t` / `30,492 tok`) | 空闲 DP rank GDN 状态同步深层边界 |
| `mtp-draft-slot-mapping-capacity-zh-vague`<br>(`vllm_ascend/spec_decode/eagle_proposer.py`) | `codex` | `0.0` (`255.3s` / `17t` / `10,380 tok`) | `0.0` (`233.0s` / `13t` / `8,282 tok`) | `0.0` (`297.4s` / `15t` / `13,840 tok`) | 作为 G5 负向蒸馏防污染基线题 |
| `mtp-draft-slot-mapping-capacity-zh-vague` | `dsh` | `0.0` (`379.9s` / `86t` / `50,521 tok`) | `0.0` (`432.5s` / `93t` / `54,993 tok`) | `0.0` (`429.0s` / `120t` / `55,937 tok` / `KQ=4`) | 自发检索 `4` 次知识库 |
| **`V1`**：`vllm-ascend-mooncake-kv-p2p-asymmetric-tp-zh`<br>(`vllm_ascend/distributed/kv_transfer/mooncake_connector.py`) | `codex` | `1.0` (`474.3s` / `28t` / `25,169 tok`) | `1.0` (`464.3s` / `26t` / `22,267 tok`) | **`1.0` (`509.6s` / `29t` / `24,592 tok` / `KQ=2`)** | 自发检索命中 Mooncake P2P KV 拓扑卡片，通过 `(8,2)`/`(8,4)`/`(4,4)` 泛化验证 |
| **`V1`**：`vllm-ascend-mooncake-kv-p2p-asymmetric-tp-zh` | `dsh` | `0.0` (`298.5s` / `60t` / `43,859 tok`) | `0.0` (`226.3s` / `60t` / `33,338 tok`) | `0.0` (`427.8s` / `120t` / `62,024 tok` / `KQ=4`) | 自发检索命中卡片并定位 `tp_rank // kv_ratio`，120 轮上限前未跑完最终校验 |
| **`V2`**：`vllm-ascend-sampler-triton-topk-unfiltered-zh`<br>(`vllm_ascend/ops/triton/topk_topp_sampler.py`) | `codex` | `1.0` (`365.7s` / `20t` / `18,702 tok`) | `1.0` (`371.5s` / `21t` / `18,280 tok`) | **`1.0` (`335.4s` / `19t` / `17,210 tok` / `Skill=2`)** | **耗时缩短 `-8.3%`，Output Tokens 节省 `-8.0%`** |
| **`V2`**：`vllm-ascend-sampler-triton-topk-unfiltered-zh` | `dsh` | `1.0` (`449.5s` / `60t` / `70,152 tok`) | `0.0` (`394.1s` / `60t` / `67,019 tok`) | **`1.0` (`487.9s` / `60t` / `88,701 tok` / `KQ=4`)** | 自发发起 `4` 次知识检索，恢复 `1.0` 通过 |
| **Track 1A 汇总（6 题 × 双宿主 = 12 对）** | **合计** | **`3 / 12` (`25.0%`)**<br>Codex `33.3%` / DSH `16.7%` | **`2 / 12` (`16.7%`)**<br>Codex `33.3%` / DSH `0.0%` | **`6 / 12` (`50.0%`)**<br>**Codex `50.0%` / DSH `50.0%`** | **总体通过率翻倍（`25.0% -> 50.0%`），DSH 通过率提升 `3.0x` (`16.7% -> 50.0%`)；Codex 平均耗时缩短 `-17.3%`、Output Tokens 节省 `-15.4%`** |

---

### 3.5 维度二（`G3`）：跨任务 C6 经验自动蒸馏飞轮（3 组同族任务对，覆盖 `vllm-ascend` 核心场景）

| 实验对与场景 | 阶段与组别 | 宿主 | Trial ID | 状态 & Reward | 耗时 (s) | TTFE (s) | 轮次 | Output Tokens | 知识检索 (`KQ`) | C6 蒸馏产出与 Warm 命中收益 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Pair 1：Partial RoPE 旋转维度切片**<br>(`rope_rotary_dim` `64 -> 32`) | Seed (`G3`) | `dsh` | `c2226e44720e` | **`1.0` (`PASS`)** | `280.9s` | `150.1s` | `52` | `45,488` | `1` | **C6 自动蒸馏入库 `unit-vllm-ascend-partial-rope-rotary-dim-cache-sop`** |
| **Pair 1：Partial RoPE 旋转维度切片** | Eval Cold (`G2`) | `dsh` | `622f4c3f0ede` | **`0.0` (`FAIL`)** | `304.4s` | `194.4s` | `50` | `53,845` | `2` | Cold 语料无 Partial RoPE 切片 SOP，50 轮未解出 |
| **Pair 1：Partial RoPE 旋转维度切片** | **Eval Warm (`G3->G2`)** | `dsh` | `039ad9ea9c2a` | **`1.0` (`PASS`)** | **`301.3s`** | **`123.4s` (`-36.5%`)** | `53` | `51,865` | **`3` (命中新卡)** | **`knowledge_explain` 直接命中刚蒸馏的卡片，实现 `0.0 -> 1.0` 破零，TTFE 缩短 `36.5%`！** |
| **Pair 2：SFA MTP 投机步长生命周期**<br>(`sfa_v1.py` `seed -> eval`) | Seed (`G3`) | `codex` | `92ebd17e6d9d` | **`1.0` (`PASS`)** | `156.9s` | `138.9s` | `10` | `7,392` | `0` | **C6 自动蒸馏入库 `unit-sfa-mtp-step-length-buffer-lifetime`** |
| **Pair 2：SFA MTP 投机步长生命周期** | Eval Cold (`G2`) | `codex` | `6ec2300d44cc` | `1.0` (`PASS`) | `191.3s` | `79.8s` | `15` | `9,724` | `0` | Cold 基线：`15` 轮、`41` 次工具调用、`9,724` Output Tokens |
| **Pair 2：SFA MTP 投机步长生命周期** | **Eval Warm (`G3->G2`)** | `codex` | `f814c8fedaff` | **`1.0` (`PASS`)** | **`153.3s` (`-19.8%`)** | `115.5s` | **`10` (`-33.3%`)** | **`7,723` (`-20.6%`)** | `0` (`Skill=1`) | **耗时缩短 `19.8%`，轮次减少 `33.3%` (`15 -> 10`)，工具调用减少 `63.4%` (`41 -> 15`)，Tokens `-20.6%`** |
| **Pair 3（新增 V2）：KDA Varlen Chunk 尾块状态污染**<br>(`ops/triton/kda_varlen_chunk.py` `V3-Seed -> V3-Eval`) | Eval Bare (`G0`) | `codex` | `3a8e110dc78f` | `1.0` (`PASS`) | `222.5s` | `137.4s` | `14` | `10,339` | `0` | 无插件裸跑基线：`222.5s`、`14` 轮、`10,339` Output Tokens |
| **Pair 3（新增 V2）：KDA Varlen Chunk** | Seed (`G3`) | `codex` | `694107044aac` | **`1.0` (`PASS`)** | `152.3s` | `119.5s` | `11` | `7,240` | `0` | **C6 自动蒸馏入库 L2 SOP `unit-kda-varlen-tail-boundary-regression`** |
| **Pair 3（新增 V2）：KDA Varlen Chunk** | Eval Cold (`G2`) | `codex` | `c1253f85f634` | `1.0` (`PASS`) | `128.9s` | `95.8s` | `11` | `6,086` | `0` | Cold `G2` 相比 `G0` 提速 `1.73x` (`222.5s -> 128.9s`) |
| **Pair 3（新增 V2）：KDA Varlen Chunk** | **Eval Warm (`G3->G2`)** | `codex` | `d46d2c481986` | **`1.0` (`PASS`)** | **`133.4s` (`-40.0%` vs G0)** | `119.0s` | **`9` (`-35.7%` vs G0, `-18.2%` vs Cold)** | **`6,561` (`-36.5%` vs G0)** | `0` (`Skill=2`) | **Warm `G2` 轮次进一步从 `14 (G0) -> 11 (Cold) -> 9 (Warm)`，较 `G0` 耗时 `-40.0%`、Tokens `-36.5%`** |
| **Pair 3（新增 V2）：KDA Varlen Chunk** | Seed (`G3`) | `dsh` | `2c48f5999c26` | **`1.0` (`PASS`)** | `244.5s` | `143.3s` | `40` | `42,450` | `4` | **C6 自动蒸馏入库 L1 Axiom `unit-vllm-ascend-kda-varlen-tail-boundary-eos`** |
| **Pair 3（新增 V2）：KDA Varlen Chunk** | Eval Cold (`G2`) | `dsh` | `3a930b771d6d` | `1.0` (`PASS`) | `341.8s` | `195.2s` | `56` | `53,568` | `1` | Cold `G2` 耗时 `341.8s`、Output Tokens `53,568` |
| **Pair 3（新增 V2）：KDA Varlen Chunk** | **Eval Warm (`G3->G2`)** | `dsh` | `c3ed3c5412d3` | **`1.0` (`PASS`)** | **`262.5s` (`-23.2%`, `1.30x` vs Cold)** | **`150.2s` (`-23.1%` vs Cold)** | `55` | **`42,220` (`-21.2%` vs Cold)** | **`5` (命中新卡)** | **DSH 自发发起 `5` 次知识检索直接命中刚入库的 KDA 卡片，比 Cold 提速 `1.30x`、TTFE `-23.1%`、Output Tokens 节省 `-21.2%`！** |

---

### 3.6 维度三（`G4`）：RSI 受控因子图算子自演进（3 道算子融合与 Triton 演进题，`G0` vs `G2` vs `G4`）

| 任务 ID（真实修改模块） | 宿主 | `G0`（无知识盲搜） | `G2`（常规 `reuse` 模式） | `G4`（RSI `explore` 受控因子图探索） | `G4` 核心收益与因子剪枝证据 |
| --- | --- | --- | --- | --- | --- |
| **`V4`（新增 V2）**：`vllm-ascend-mla-prolog-rope-kvcache-fusion-rsi-zh`<br>(`vllm_ascend/ops/mla_prolog.py`) | `codex` | `1.0` (`485.4s` / `TTFE 182.9s` / `17t` / `23,331 tok`) | `1.0` (`565.6s` / `TTFE 124.0s` / `20t` / `25,930 tok`) | **`1.0` (`593.1s` / `TTFE 120.2s` / `20t` / `28,351 tok` / `Skill=3`)** | **TTFE 从 `182.9s (G0) -> 124.0s (G2) -> 120.2s (G4)`（定位提速 `1.52x`，`-34.3%`）**；完整通过 3 分支 Leave-One-Out 消融校验 |
| **`V4`（新增 V2）**：`vllm-ascend-mla-prolog-rope-kvcache-fusion-rsi-zh` | `dsh` | **`0.0` (`FAIL`, `323.9s` / `41t` / `50,873 tok`)** | **`1.0` (`PASS`, `554.9s` / `TTFE 302.6s` / `60t` / `103,432 tok` / `KQ=3`)** | **`1.0` (`PASS`, `467.0s` / `TTFE 264.1s` / `60t` / `82,329 tok` / `KQ=3`)** | **从 `G0 = 0.0` 破零升至 `1.0`！且 `G4` 比 `G2` 进一步提速 `1.19x` (`554.9s -> 467.0s`, `-15.8%`)、TTFE `-12.7%`、Output Tokens 节省 `-20.4%` (`103,432 -> 82,329`)！** |
| `dsv4-sparse-mla-qli-fusion-rsi-zh`<br>(`vllm_ascend/compilation/passes/...`) | `codex` | **`0.0` (`FAIL`, `374.5s` / `16t` / `19,043 tok`)** | `1.0` (`271.2s` / `17t` / `15,312 tok` / `KQ=4`) | **`1.0` (`270.3s` / `16t` / `13,710 tok` / `KQ=4`)** | **`0.0 -> 1.0` 破零（补齐 `k_nope` view 融合分支），耗时较 `G0` 缩短 `-27.8%`、Output Tokens 节省 `-28.0%` (`19,043 -> 13,710`)** |
| `triton-spatial-norm-dim-merge-rsi-zh`<br>(Triton Spatial Norm 算子) | `codex` | `1.0` (`550.3s` / `TTFE 196.8s` / `16t` / `29,254 tok`) | `1.0` (`600.0s` / `TTFE 199.0s` / `16t` / `28,487 tok`) | **`1.0` (`414.4s` / `TTFE 125.7s` / `15t` / `22,856 tok` / `coord=1`)** | **剥离 L3 旧工作流先验后，`G4` 比 `G0` 快 `-24.7%`、比 `G2` 快 `-30.9%` (`1.45x`)，TTFE 提速 `1.58x`，Output Tokens 节省 `-21.9%`！** |

---

### 3.7 维度四（`G5`）：多轮连续演进与反膨胀验证（`Episode A -> B -> C -> D -> E`）

| 演进轮次 | 任务与组别 | 宿主 | Trial ID | 语料规模 | Reward | 耗时 (s) | 轮次 | Output Tokens | C6 蒸馏动作与反膨胀表现 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Episode A (`Seed 1`)** | `sfa-mtp-seq-lens-seed-zh-vague` (`G3`) | `codex` | `92ebd17e6d9d` | `82 -> 83` units | **`1.0`** | `156.9s` | `10` | `7,392` | `completed:applied`：自动蒸馏并合入正向 SOP `unit-sfa-mtp-step-length-buffer-lifetime` |
| **Episode B (`Warm 1`)** | `sfa-mtp-seq-lens-eval-zh-vague` (`G2`) | `codex` | `86f7cb6bc222` | `83` units | **`1.0`** | `202.3s` | **`12` (`-20%` vs Cold)** | **`8,630` (`-11.2%`)** | 相比 Cold 对照 (`6ec2300d44cc`: `15` 轮 / `9,724` tok)，轮次减少 `20%`、工具调用减少 `58.5%` |
| **Episode C (`Seed 2`)** | `mtp-draft-slot-mapping-capacity-zh-vague` (`G3`) | `codex` | `74309913afb5` | `83 -> 84` units | `0.0` | `203.0s` | `12` | `8,652` | `completed:applied`：诚实蒸馏负向验证边界 `unit-mtp-draft-slot-mapping-capacity-validation`（不伪造成功秘籍） |
| **Episode D (`Warm 2`)** | `mtp-draft-slot-mapping-capacity-zh-vague` (`G2`) | `codex` | `bb116915927a` | `84` units | `0.0` | `235.2s` | `15` | `10,608` | 相比 Cold 对照 (`2d94fe9ed4c7`: `287.2s` / `16` 轮 / `15,357` tok)，**无效探索耗时减少 `-18.1%`、Output Tokens 节省 `-30.9%`** |
| **Episode E (`Regression`)** | `sfa-mtp-seq-lens-eval-zh-vague` (`G2`) | `codex` | `f814c8fedaff` | `84` units | **`1.0`** | **`153.3s` (`-19.8%` vs Cold)** | **`10` (`-33.3%` vs Cold)** | **`7,723` (`-20.6%` vs Cold)** | **连续合入正/负向两张同域卡片后，回测前序任务零退化、零干扰，耗时进一步降至 `153.3s`、Tokens 节省 `20.6%`！** |

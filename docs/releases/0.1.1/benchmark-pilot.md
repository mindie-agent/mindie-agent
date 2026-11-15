# 0.1.1 工程复现与知识演进（G5）开发试点报告

[English](https://github.com/mindie-agent/mindie-agent/blob/v0.1.1/docs/releases/0.1.1/benchmark-pilot.en.md) · [0.1.1 发布说明](../0.1.1.md) · [试点结构化凭据 (`benchmark-pilot.json`)](benchmark-pilot.json) · [四端原生更新验收 (`native-update-acceptance.json`)](native-update-acceptance.json)

本报告记录 `mindie-agent 0.1.1` 维护补丁周期内执行的离线 CPU 工程复现试点与 `G5`（`X-04` 候选协议）知识演进实验完整回执（机器可读数据见同目录 [`benchmark-pilot.json`](benchmark-pilot.json)，`schema: "mindie-patch-dev-pilot-evidence/1"`）。本试点旨在检验行为级判分器（Behavioral Verifier）、短模糊用户提示词（Vague Prompt）、代理网关流式结算以及原生会话采集准入在真实模型调用下的端到端工作状态，**不构成统计因果收益证明，也不替代 `0.1.0` 历史 109 轮 Trial 的重判**。

2026-10-29 的后续源码整改收紧了四端验证后收尾边界，并统一原生完成态准入和
C6 前拒绝回执，见[后续本地整改记录](../../audits/2026-10-29-knowledge-p0.md#后续本地整改离线条件收敛与组件桥)。
该整改及其契约测试不改写本报告的失败回执，也不代表新的 G5 真模型闭环已通过。

---

## 一、问题背景与证据边界

1. **历史 `0.1.0` 量化收益结论继续暂停**：
   - 在 2026-10-24 基准审查中发现，历史任务集中有 6 个任务的旧判分器可被无功能源码修改通过，且策略选择试点旧默认执行器曾读取私有评判答案合成续跑结果。`mindie-bench 0.4.3 / 0.4.4` 已将该 6 个任务升级为行为级源码执行判分器，但历史 `0.1.0` 的 109 轮 Trial 尚未在新判分器下重跑或重判，因此历史量化提升结论继续暂停作为当前产品验收依据，本报告亦**绝不冒充旧 18 任务价值套件已重新通过**。
2. **`0.1.1` 维护补丁门禁与本 LLM 开发试点的关系**：
   - 主仓库 `0.1.1` 采用 `release-kind=patch` 维护补丁门禁，十二个代码仓的正式 GitHub Release、不可变 Tag Commit SHA、各仓 `mindie-release-benchmark/2` 组件基准报告（`release_gate = true`、`blocking_reasons = []`）、校验和以及 [`channels/0.1.json`](../../../channels/0.1.json) 与 `benchmark-manifest.json` 的精确一致均已预检通过，四个宿主插件 `0.1.2` 的 macOS 原生更新与会话门禁亦已独立验收闭环（见 [`native-update-acceptance.json`](native-update-acceptance.json)）。
   - 本报告记录的是开发维护周期内针对暴露题（`exposed_dev_offline_engineering_reproductions`）开展的单次重复（`repetitions = 1`）描述性工程复现试点（`inference_scope = "descriptive_pilot_no_statistical_benefit_claim"`），用于暴露并修复运行器、配置与采集链路中的工程缺陷。

---

## 二、实验范围、研究对象与题源分类（`source_class`）

### 1. 两个宿主实验队列与研究对象边界

本试点包含两个独立宿主队列（严禁混池统计，亦不将队列切换表述为“同一实验无缝回退完成”）：

| 队列标识 | 宿主客户端与模型配置 | 评测运行器与原生插件/组件版本组合 | 实验覆盖范围 |
| --- | --- | --- | --- |
| **Cohort 1（Codex G0 Canary）**<br/>`maintenance-codex`<br/>`maintenance-codex-v2` | OpenAI Codex CLI `0.153.4`<br/>`home/codex/gpt-6.1-sol (xhigh)` | `mindie-bench 0.4.3`（`eb49b2e0a36184c1216b13b7f0a0ba88b8a26ece`） | 仅执行 `G0`（无 MindIE 知识工具处理）；暴露 `0.4.3` `HTTP/1.1 chunked` 结算并发关闭竞态 |
| **Cohort 2（DSH 维护与 G5 试点）**<br/>`maintenance-dsh-044`<br/>`maintenance-dsh-044-native-path`<br/>`g5-dsh-044` ~ `v4-long-training` | DeepSeek Harness `0.2.0-rc.2`<br/>`deepseek-flash`（`reasoning_effort: "max"`）<br/>16 GiB 主机（可用空闲+非活跃内存约 `5.1 GiB`，并发上限 `max_parallel_native_agents = 2`，零权重加载、零 NPU 上下文初始化） | 固定挂载已正式发布的原生插件 **`mindie-agent-dsh 0.1.1`**（`fc29535161c0d9e57c558c250bbb9101c0da55ce`，含其 `0.1.1` `C6` Organizer 源码），配合锁定运行时（`runtime_lock_sha256: a466c966...`）中的 8 个正式版共享与评测组件：`mindie-knowledge 0.13.3`（`38a42f6f...`）、`remote-dev 0.10.6`（`0463a13f...`）、`mindie-diagnostics 0.5.2`（`801a01b2...`）、`mindie-profiler 0.5.0`（`4010d72f...`）、`mindie-sim 0.7.1`（`15f93f3f...`）、`npu-top 0.2.1`（`6737925d...`）、`mindie-coordinator 0.6.3`（`0ec71fb9...`）、`mindie-bench 0.4.4`（`a36d8a5a...`）。维护语料快照：`ascend` `335c3933...` + `operators` `6f083f81...`；G5 语料快照：`ascend` `25b06b94...` + `operators` `6f083f81...` | 3 个维护夹具任务（`G0 / G1 / G2`）与 `G5`（`X-04` 候选）知识演进序列 |

> **研究对象与四端插件 `0.1.2` 的区分说明**：Cohort 2 固定使用已发布的 `mindie-agent-dsh 0.1.1` 原生插件（`fc29535161c0d9e57c558c250bbb9101c0da55ce`）及其内置 `C6` 源码加 8 个新正式组件运行；四个宿主插件正式版 `0.1.2`（Codex `0b3c690b...`、CC `edabca82...`、Kimi `7aecfd22...`、DSH `a38f1cb1...`）的真实安装、手动 `/mindie-agent` 会话门禁与组件更新由独立的原生宿主验收闭环（见 [`native-update-acceptance.json`](native-update-acceptance.json)）。**本报告不宣称是对 `0.1.2` 原生插件整包的端到端业务价值评测。**

### 2. 题源核查分类（`declared_source` vs. `source_class`）与短模糊提示词校验

经对任务 Git 提交对象的逐项核查，本报告在 [`benchmark-pilot.json`](benchmark-pilot.json) 中并列公开原始 `task.toml` 声明（`declared_source`）与真实题源分类（`source_class`）：

1. **三项维护组件任务（`source_class = "seeded_local_engineering_fixture"`）**：
   - 包含 `npu-top-and-coordinator-multi-die-lease-repair-zh`（hash `0883a3a2...`）、`profiler-msprof-straggler-and-hbm-fix-zh`（hash `1c350fe1...`）与 `sim-a3-ub-fusion-and-pipeline-dispatch-zh`（hash `21e68aad...`），单题预算均为 `50 turns / 480s`。
   - 尽管原始 `task.toml` 声明 `repository = "vllm-project/vllm-ascend"`（`issue = "component-value-0.1.0"`），Git 提交对象核查证实其 `base_commit`（`f752d0215c2e13b44ac472caa14c02b6749762e3`，提交标题 *"Add broken vllm_ascend_diag baseline modules for component value tasks"*）与 `fix_commit`（`8c5ce76d9afb36205b8e59adb7b2d4b2ad89a85c`，提交标题 *"Fix vllm_ascend_diag modules using MindIE component contracts"*）是在本地检出仓库中人工植入缺陷的 11 个工程样例夹具文件，**并非上游公开仓库已证实的真实历史提交或现网故障修复**。
2. **三项 G5 投机解码任务及两项长训练预算变体（`source_class = "historical_source_regression"`）**：
   - **SFA 多步投机序列长度种子题** `sfa-mtp-seq-lens-seed-zh-vague`（hash `35053616...`，预算 `80 turns / 600s`）及阶段 `A` 长训练变体 `sfa-mtp-seq-lens-seed-zh-vague-g5-long`（hash `8d8fe41a...`，预算 `120 turns / 900s`）：对应历史源码回归 `base_commit` `b9c58e8d7073bdda448c49bc6239778c0e6a6960`、`fix_commit` `035b8d40718dc097e159e3590975d712535e4245`（关联 `#14236`）。
   - **SFA 多步投机同源评估题** `sfa-mtp-seq-lens-eval-zh-vague`（hash `08ee5c9c...`，预算 `80 turns / 600s`）：与种子题共享同一对 `base_commit` / `fix_commit`（`#14236`），属于暴露同源回归验证，非未见过的跨问题独立迁移（`independent_heldout = false`）。
   - **MTP 投机步数扩容越界题** `mtp-draft-slot-mapping-capacity-zh-vague`（hash `e39b54fe...`，预算 `60 turns / 600s`）及阶段 `C` 预备长训练变体 `mtp-draft-slot-mapping-capacity-zh-vague-g5-long`（hash `4af7f57d...`，`task.toml` 声明预算为 `60 turns / 900s`，因上游阶段 `A` 未产出合法知识而实际未启动）：对应历史源码回归 `base_commit` `63bd2c418c8914201981f1150fc0e0ae5724896e`、`fix_commit` `0aa1b486c0e6d3fb457822da2b9b49ede2578562`（关联 `#14024`）。
   - 上述任务均通过离线 CPU 行为级判分器验证（常驻 A2/A3 集群上通过的 `test_live_fleet_probe_and_capacity_across_a2_and_a3` `1 passed (8.01s)` 为独立的只读容量探测测试，并非上述 SFA/MTP 任务的真机上卡执行）。
3. **短模糊提示词与判分器 Soundness 复核**：
   - 全部 6 道基础题均采用 32–42 字的中文短模糊提示词（文件 SHA256 `d1895e5b047e5a2e91e104683bcc6d28403b0f455d067c32febcbaf96ee66fd1`），仅描述可见故障症状与修复目标，不提供根因、函数名或算法步骤，工作区源码照常可读；2 个 `-g5-long` 变体保持提示词原文只字未改。
   - 在正式 `mindie-bench 0.4.4` 下，6 道基础题与 2 个预算变体全部通过零模型调用 Soundness 校验：`before_reward = 0.0`、`after_reward = 1.0`、`model_calls = 0`。

---

## 三、原始队列计数与逐案实测结果（全量 21 条 Trial 回执，累计 800 次已观测模型调用）

[`benchmark-pilot.json`](benchmark-pilot.json) 共收录 **21 条 Trial 终态回执**（维护队列 `2` 条 Codex + `12` 条 DSH = `14` 条；`G5` 序列 `v2 / v3 / v4` 分别为 `3 + 3 + 1 = 7` 条；另有 `g5-dsh-044` 首轮为 `0` 条 Trial 的驱动启动前失败单独记录）。21 条 Trial 的终态分布为 **`5 completed_pass`、`8 completed_fail`、`7 infra_failed`、`1 unknown`**；全部已观测前台 `model_calls` 总和为 **`800` 次**（`10 + 6×50 + 3×50 + 80 + 60 + 80 + 120 = 800`）。预检失败或缺失字段严格保留 `null` 原语义，不将其费用填为 `0`；计量网关未返回美元账单，所有 Trial 的 `estimated_cost_usd` 均保留为 `null`（`cost_complete = false`）。

### 1. 矩阵队列与 G5 序列计划汇总计数

- **维护矩阵队列（含正式 Matrix Manifest，共 14 条回执）**：

| 矩阵队列名称 | Manifest / Config SHA256 | 计划 Cell (`planned_cells`) | 终态回执 (`terminal_receipts`) | 矩阵未执行 (`missing_count`) | 终态分布 |
| --- | --- | --- | --- | --- | --- |
| `maintenance-codex` | `d280424e...` | 9 | 1 | 8 | `1 infra_failed`（预检 `ValueError`，`0` 调用） |
| `maintenance-codex-v2` | `c6418740...` | 9 | 1 | 8 | `1 unknown`（`480s` 预算到期流式未完结，`10` 调用；`8` 未启动） |
| `maintenance-dsh-044` | `669fa358...` / `ed38a420...` | 9 | 9 | 0 | `6 completed_fail`（`G0`/`G1` 各 `50` 调用），`3 infra_failed`（`G2` 预检 `0` 调用） |
| `maintenance-dsh-044-native-path` | `f4af7c78...` / `e2988ae9...` | 3 | 3 | 0 | `3 completed_pass`（修正原生插件挂载路径后的独立 `G2` 队列，各 `50` 调用） |

- **G5 顺序演进序列（Sequential Plan，无 Matrix Manifest，共 7 条回执）**：

| G5 序列运行标识 | Config / Sequence SHA256 | 序列计划阶段 | 已启动并产生回执 | 依赖未启动阶段 (`B–E`) | 序列状态与终态分布 |
| --- | --- | --- | --- | --- | --- |
| `g5-dsh-044` | — | 7（`2` 冷对照 + `A–E`） | 0 | 7（准入前停止） | `setup_failed_before_trial_admission`（`0` 调用） |
| `g5-dsh-044-v2` | `92fdd2ee...` / `fc723770...` | 7（`2` 冷对照 + `A–E`） | 3（`control-B`、`control-D`、`A`） | 4（`B–E` 未启动） | `3 infra_failed`（原生插件路径预检拦截，`0` 调用） |
| `g5-dsh-044-v3` | `48bda743...` / `56c249f6...` | 7（`2` 冷对照 + `A–E`） | 3（`control-B`、`control-D`、`A`） | 4（`B–E` 未启动） | `2 completed_fail`（冷对照 `B/D`），`1 completed_pass` 但**原生采集准入拒绝**（`A` `80` 调用） |
| `g5-dsh-044-v4-long-training` | `g5-budget-amendment` / `9f5cc087...` | 5（复用 `v3` 两项冷对照，新计划 `A–E`） | 1（`stage A` 长预算） | 4（`B–E` 未启动） | `1 completed_pass` 但**原生采集准入拒绝**（`A` `120` 调用独立重跑） |

### 2. Codex Canary 与 DSH 维护队列逐案结果（14 条 Trial：2 条 Codex + 12 条 DSH）

- **Codex G0 Canary 说明**：`maintenance-codex` 首案在预检阶段因 `ValueError` 终止（`0` 模型调用）。`maintenance-codex-v2` 计划 9 个 Cell，仅执行首个 G0 Canary（其余 8 个 Cell 未启动，记为 `missing_count = 8`，而非 8 次任务失败）；该 Canary 在 `480.00s` 前台预算到期时仍有响应流在途，主回执保留为 `status = "unknown"`、`tokens.complete = false`。事后在零模型调用下对其已保存工作区补丁（`patch_sha256: 81bf62c3...`）独立执行判分器得 `reward = 0.0`（`oracle_status = "intact"`），但主回执状态仍严格保持 `unknown`。
- **DSH 维护队列 `G2` 预检失败与配置修正说明**：在 `maintenance-dsh-044`（配置 `ed38a420...`）中，`G0` 与 `G1` 共 6 个 Cell 均跑满 `50` 次模型调用并以 `completed_fail`（`reward = 0.0`）结束；而 3 个 `G2` Cell 因初始配置将 DSH 必须作为可执行代码挂载的原生插件目录同时列入了受保护语料路径，在预检阶段触发 `ValueError`（`0` 次付费模型调用）。修正配置（`e2988ae9...`）仅允许原生插件目录按正常可执行代码挂载、继续保护真实语料路径（且 `G0`/`G1` 仍不挂载 MindIE 包），并在独立新队列 `maintenance-dsh-044-native-path` 中执行 3 个 `G2` Cell。下表同时保留两轮全部 14 条记录，不丢弃预检失败记录，也不在未披露配置修订与人工夹具性质的前提下笼统宣称“100% 成功率”：

| 队列 | Trial ID | 档位 | 终态 (`status`) | Reward | 调用/轮次 | Wall / Delivery (s) | Input Cached / Uncached / Output Tokens (`complete`) | 主要工具调用计数 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `maintenance-codex` | `npu-top-and-coordinator-multi-die-lease-repair-zh_G0_1_d2c398b602ab` | `G0` | `infra_failed` | `null` | `null` / `0` | `0.00` / `0.06` | `0` / `0` / `0` (`false`) | `{}`（预检 `ValueError`） |
| `maintenance-codex-v2` | `npu-top-and-coordinator-multi-die-lease-repair-zh_G0_1_7853fadf3bbd` | `G0` | `unknown` *(事后补丁重判 `0.0`)* | `null` | `10` / `10` | `480.00` / `514.06` | `329,600` / `50,439` / `20,604` (`false`) | `bash: 21, Edit: 3` |
| `maintenance-dsh-044` | `npu-top-and-coordinator-multi-die-lease-repair-zh_G0_1_65a626a5895d` | `G0` | `completed_fail` | `0.0` | `50` / `50` | `329.79` / `358.99` | `2,637,952` / `103,233` / `70,062` (`true`) | `bash: 36, Edit: 5, Read: 4, web_search: 2, Write: 1, subagent_fork: 1` |
| `maintenance-dsh-044` | `npu-top-and-coordinator-multi-die-lease-repair-zh_G1_1_dc16ab442303` | `G1` | `completed_fail` | `0.0` | `50` / `50` | `149.98` / `154.75` | `3,220,864` / `119,364` / `16,111` (`true`) | `bash: 40, Read: 20, Grep: 4, Glob: 2, web_search: 1, mcp_res*: 3` |
| `maintenance-dsh-044` | `npu-top-and-coordinator-multi-die-lease-repair-zh_G2_1_25dd5d0b8f67` | `G2` | `infra_failed` | `null` | `null` / `0` | `0.00` / `1.21` | `0` / `0` / `0` (`false`) | `{}`（预检 `ValueError`） |
| `maintenance-dsh-044` | `profiler-msprof-straggler-and-hbm-fix-zh_G0_1_7b2a4f17c541` | `G0` | `completed_fail` | `0.0` | `50` / `50` | `385.26` / `391.46` | `3,342,720` / `64,444` / `56,823` (`true`) | `bash: 57, Edit: 8, Read: 5, web_search: 1, Write: 1` |
| `maintenance-dsh-044` | `profiler-msprof-straggler-and-hbm-fix-zh_G1_1_fec9c511ee84` | `G1` | `completed_fail` | `0.0` | `50` / `50` | `341.44` / `348.02` | `4,861,824` / `143,383` / `48,995` (`true`) | `bash: 48, Read: 10, Edit: 3, Glob: 1, Grep: 1, web_search: 1, web_fetch: 1` |
| `maintenance-dsh-044` | `profiler-msprof-straggler-and-hbm-fix-zh_G2_1_41f6e12ec063` | `G2` | `infra_failed` | `null` | `null` / `0` | `0.00` / `1.49` | `0` / `0` / `0` (`false`) | `{}`（预检 `ValueError`） |
| `maintenance-dsh-044` | `sim-a3-ub-fusion-and-pipeline-dispatch-zh_G0_1_fe1620c146e3` | `G0` | `completed_fail` | `0.0` | `50` / `50` | `302.89` / `310.74` | `3,040,000` / `76,621` / `48,017` (`true`) | `bash: 56, Read: 8, Edit: 3, Grep: 2, Glob: 1, web*: 2, todo_write: 1, subagent: 1` |
| `maintenance-dsh-044` | `sim-a3-ub-fusion-and-pipeline-dispatch-zh_G1_1_177630ae6fce` | `G1` | `completed_fail` | `0.0` | `50` / `50` | `305.26` / `310.50` | `4,168,448` / `149,186` / `20,391` (`true`) | `bash: 67, Read: 11, Glob: 1, web_search: 1, web_fetch: 1, mcp_res*: 3` |
| `maintenance-dsh-044` | `sim-a3-ub-fusion-and-pipeline-dispatch-zh_G2_1_e70dffc9d28f` | `G2` | `infra_failed` | `null` | `null` / `0` | `0.00` / `1.43` | `0` / `0` / `0` (`false`) | `{}`（预检 `ValueError`） |
| `maintenance-dsh-044-native-path` | `npu-top-and-coordinator-multi-die-lease-repair-zh_G2_1_5cc88a2e761e` | `G2` | `completed_pass` | `1.0` | `50` / `50` | `268.94` / `275.88` | `5,195,008` / `156,193` / `33,755` (`true`) | `bash: 58, Read: 12, knowledge_query: 4, mindie_entry: 1, knowledge_explain: 1, Write: 1, web*: 2` |
| `maintenance-dsh-044-native-path` | `profiler-msprof-straggler-and-hbm-fix-zh_G2_1_e361bd685cef` | `G2` | `completed_pass` | `1.0` | `50` / `50` | `345.26` / `351.99` | `5,481,344` / `137,423` / `52,171` (`true`) | `bash: 48, Read: 9, Edit: 4, knowledge_query: 3, mindie_entry: 1, knowledge_explain: 1, Write: 1, web*: 2` |
| `maintenance-dsh-044-native-path` | `sim-a3-ub-fusion-and-pipeline-dispatch-zh_G2_1_469e50895a9f` | `G2` | `completed_pass` | `1.0` | `50` / `50` | `352.38` / `358.46` | `4,736,896` / `149,614` / `41,763` (`true`) | `bash: 58, Read: 5, knowledge_query: 4, Grep: 3, mindie_entry: 1, knowledge_explain: 1, job_output: 1, Write: 1, web_fetch: 1` |

---

## 四、G5（`X-04` 候选协议）知识演进事件链与未闭环事实

用户提供的外部 ChatGPT 分享链接在实验准备期间无法读取正文，因此本实验直接采用仓内既有设计文档中的 `X-04`（`Episode A -> B -> C -> D -> E`）作为候选协议，**不宣称复现了该外部链接中的具体讨论方案**。

### 1. 四轮执行事件链（精确失败位置：`C6` 调用前的原生采集描述符准入）

1. **`g5-dsh-044`（首轮启动前失败）**：
   - 在进入任何 Trial 准入前即因驱动设置错误停止（`status = "setup_failed_before_trial_admission"`，`0` 条 Trial、`0` 次模型调用）。
2. **`g5-dsh-044-v2`（预检拦截，`0` 次付费调用）**：
   - 原方案含 2 个冷对照与 5 个演进阶段（共 7 项）；因原生插件目录被同时列为保护语料路径，已启动的 `control-B-cold`（`6b641fe7cf81`）、`control-D-cold`（`9a0a1f8af376`）与训练阶段 `A`（`6d7577328e67`）均在预检阶段报 `ValueError`（`status = "infra_failed"`，`0` 次模型调用），后续 `B–E` 未启动。
3. **`g5-dsh-044-v3`（冷对照均败；阶段 `A` 业务判分通过但在 `C6` 入口前的原生采集资格检查被拒）**：
   - **冷知识对照 `control-B-cold`**（`sfa-mtp-seq-lens-eval-zh-vague_G2_1_d7bdc5c24885`）：执行满 `80` 次调用（`wall = 246.46s`），业务判分未通过（`completed_fail`，`reward = 0.0`）。
   - **冷知识对照 `control-D-cold`**（`mtp-draft-slot-mapping-capacity-zh-vague_G2_1_9ee7dc0d7998`）：执行满 `60` 次调用（`wall = 205.29s`），业务判分未通过（`completed_fail`，`reward = 0.0`）。
   - **训练阶段 `A`（`80` 调用预算）**（`sfa-mtp-seq-lens-seed-zh-vague_G3_1_8b02618500ea`）：Agent 在 `80` 次模型调用内修通了工作区代码，离线行为判分器验证通过（`status = "completed_pass"`，`reward = 1.0`，`oracle_status = "intact"`）；但会话在抵达第 `80` 次调用上限时被回合预算截断，未产生宿主原生正常结束事件。在进入 `C6` Organizer 之前的原生会话采集描述符准入检查（`DshDriver.native_capture_payload()`）直接抛出 `ValueError("DSH capture requires a completed native session event")`（`capture.status = "failed"`，`captured_corpus_sha256 = null`，`units_after = null`）——**没有合法输入进入提炼，本轮并未实际调用 `C6` Organizer 或执行本地 Git 发布，产出 `0` 条合法入库知识单元**。
4. **`g5-dsh-044-v4-long-training`（上调阶段 `A` 训练预算至 `120 turns / 900s` 的独立新会话重跑）**：
   - 为检验更长回合预算能否让阶段 `A` 自然收尾，在不重放未知请求、不伪造原生完成事件、不预置注入 `U@2` 单元且保持消费者阶段预算不变的前提下，复用 `v3` 已完成的两项冷对照，使用显式预算修正配置（阶段 `A` `sfa-mtp-seq-lens-seed-zh-vague-g5-long` 为 `max_turns = 120`、`timeout_sec = 900`；阶段 `C` 预备变体 `mtp-draft-slot-mapping-capacity-zh-vague-g5-long` 为 `max_turns = 60`、`timeout_sec = 900`）启动阶段 `A` 全新独立会话 `sfa-mtp-seq-lens-seed-zh-vague-g5-long_G3_1_91e50697f5a5`。
   - **实测结果**：该会话再次通过业务行为判分器（`status = "completed_pass"`，`reward = 1.0`，`oracle_status = "intact"`，`wall = 523.98s`），但同样耗尽全部 `120` 次调用而未产生原生完成事件，再次在 **`C6` 调用前的 `DshDriver.native_capture_payload()` 原生采集资格检查**处被拒绝（`capture.status = "failed"`，未执行 `C6` 提炼或本地发布，`0` 条合法知识发布）。两轮阶段 `A` 合计 `200` 次模型调用及其 `tokens.complete = false` 状态均完整保留。
   - **下游阶段 `B / C / D / E` 未启动**：由于阶段 `A` 无合法知识入库，依赖其产物的下游阶段 `B`、`C`（含 `60 turns / 900s` 变体）、`D`、`E` 均未启动（`status = "partial_A_has_no_admitted_corpus"`，`revision_observed = null`）。**完整知识演进链尚未执行，本次 `G5` 闭环实验未通过。**

### 2. G5 逐案实测明细（7 条 Trial）

| 队列与阶段 | Trial ID | 档位 | 业务终态 (`status`) | Reward | 原生采集准入 (`capture`) | 调用/轮次 | Wall / Delivery (s) | Input Cached / Uncached / Output Tokens (`complete`) | 主要工具调用计数 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `g5-dsh-044-v2` `control-B-cold` | `sfa-mtp-seq-lens-eval-zh-vague_G2_1_6b641fe7cf81` | `G2` | `infra_failed` | `null` | — | `null` / `0` | `0.00` / `1.29` | `0` / `0` / `0` (`false`) | `{}`（预检 `ValueError`） |
| `g5-dsh-044-v2` `control-D-cold` | `mtp-draft-slot-mapping-capacity-zh-vague_G2_1_9a0a1f8af376` | `G2` | `infra_failed` | `null` | — | `null` / `0` | `0.00` / `0.83` | `0` / `0` / `0` (`false`) | `{}`（预检 `ValueError`） |
| `g5-dsh-044-v2` `stage A` | `sfa-mtp-seq-lens-seed-zh-vague_G3_1_6d7577328e67` | `G3` | `infra_failed` | `null` | — | `null` / `0` | `0.00` / `0.86` | `0` / `0` / `0` (`false`) | `{}`（预检 `ValueError`） |
| `g5-dsh-044-v3` `control-B-cold` | `sfa-mtp-seq-lens-eval-zh-vague_G2_1_d7bdc5c24885` | `G2` | `completed_fail` | `0.0` | — | `80` / `80` | `246.46` / `256.62` | `9,709,824` / `310,845` / `32,152` (`true`) | `bash: 68, Read: 30, knowledge_query: 2, mindie_entry: 1, knowledge_explain: 1, web_fetch: 1` |
| `g5-dsh-044-v3` `control-D-cold` | `mtp-draft-slot-mapping-capacity-zh-vague_G2_1_9ee7dc0d7998` | `G2` | `completed_fail` | `0.0` | — | `60` / `60` | `205.29` / `214.32` | `6,457,728` / `303,591` / `26,276` (`true`) | `bash: 91, Read: 6, knowledge_query: 3, mindie_entry: 1, knowledge_explain: 1, web_search: 1, remote_probe: 1` |
| `g5-dsh-044-v3` `stage A` (`80` turns) | `sfa-mtp-seq-lens-seed-zh-vague_G3_1_8b02618500ea` | `G3` | `completed_pass` | `1.0` | **`failed`** (`C6` 前描述符准入 `ValueError`, `0` 单元) | `80` / `80` | `365.49` / `378.17` | `9,528,320` / `287,690` / `55,243` (`false`) | `bash: 85, Read: 13, knowledge_query: 3, Edit: 2, Write: 2, mindie_entry: 1, web_fetch: 1` |
| `g5-dsh-044-v4` `stage A` (`120` turns) | `sfa-mtp-seq-lens-seed-zh-vague-g5-long_G3_1_91e50697f5a5` | `G3` | `completed_pass` | `1.0` | **`failed`** (`C6` 前描述符准入 `ValueError`, `0` 单元) | `120` / `120` | `523.98` / `535.88` | `15,251,584` / `485,606` / `73,934` (`false`) | `bash: 127, Read: 20, Edit: 4, knowledge_query: 2, knowledge_explain: 2, mindie_entry: 1, web*: 2` |

---

## 五、核心工程发现与局限边界

1. **发现并修复 `mindie-bench 0.4.3` 流式结算跨线程关闭竞态（`0.4.4` 已正式发布）**：
   - Codex G0 Canary 在 `480s` 预算到期中断 `HTTP/1.1 chunked` 响应时暴露出：结算线程直接调用 `connection.close()` 会在请求处理线程执行 `response.read1()` 期间将 `HTTPResponse.fp` 置为 `None`，在 Python 3.13 下触发 `AttributeError: NoneType.close` 并导致结构化 `model_error` 记录丢失。
   - `mindie-bench 0.4.4`（`a36d8a5ae8633e560d19fee231179c3680149109`）改为仅对底层传输 socket 调用 `shutdown(socket.SHUT_RDWR)` 唤醒阻塞读取，将 `HTTPConnection` / `HTTPResponse.close()` 交由请求处理线程自身的 `finally` 块独占完成。该修复已通过两个零付费本地回环测试模块（`18 passed, 13.24s`）、新增 `HTTP/1.1 chunked` 读取交错回归测试（`0.60s`）、旧实现负对照、macOS/Linux CI 以及 7 项发布资产 / 158 个 `.py` 源文件逐字节核验；原 Canary 回执保持 `unknown`，不宣称恢复了已缺失的远端 Token 明细。
2. **修正 DSH 原生插件目录与受保护语料路径的预检冲突**：
   - DSH 运行时需将选定的原生插件目录作为可执行代码挂载，而首轮配置将其同时列入受保护语料路径导致 `G2`/`G3` 预检失败（`0` 次模型调用）。分离可执行插件路径与受保护语料路径后，工具链路正常工作。
3. **揭示长回合排障任务中“业务代码修通”与“`C6` 入口前原生采集完成态准入”的衔接缺口**：
   - 在两轮 `G5 stage A`（`80` 与 `120` 调用）中，Agent 均已修通工作区代码并通过离线行为判分（`reward = 1.0`），但因持续运行额外检查直至耗尽回合预算，未能产生宿主原生完成事件，导致在进入 `C6` Organizer 之前的 `DshDriver.native_capture_payload()` 原生采集资格检查即被拒绝（没有合法输入进入 `C6` 提炼，亦未执行 `C6` Organizer 或本地发布）。这说明“业务判分通过”或“成功调用 `knowledge_query` / `knowledge_explain`”绝不等于“知识演进闭环成功”。
4. **实验设计与统计推断局限**：
   - **样本量与题源限制**：本试点为 `repetitions = 1` 的暴露题离线 CPU 复现，三项维护任务均为本地人工植入的工程夹具（`seeded_local_engineering_fixture`），不可外推为统计显著的产品性能收益或真实 NPU 线上验收结论。
   - **`G5` 协议演进语义缺口**：即便后续阶段 `C` 在另一道 MTP 容量缺陷题上跑通并产出新单元，针对不同缺陷新增独立知识单元也不等于对同一知识单元的“反证触发修订（`U@1 -> U@2`）”；同时阶段 `B` 与 `A` 共享同一历史 Issue（`#14236`），`D` 与 `E` 为暴露案例复测而非独立未见迁移（Held-Out Transfer）。完整的同单元反证语义审阅与跨任务独立迁移评测仍需后续版本专项设计与验证。

# 架构简化与正确性修复记录（2026-10-23）

[返回文档中心](README.md)

> **历史审计记录边界（2026-10-23）**：本页按原貌保留 2026-10-23 第一阶段跨仓简化与本地 Tier 0 / Tier 1 验证快照，**不代表后续全部问题均已完结，亦不能冒充当前主产品最终验收结论**。后续更深入的四路并行源码复核、补充修复及 PR 状态请参阅 **[并行架构评审与修复记录（2026-10-24）](architecture-review-20261024.md)**。

本文记录一次跨仓架构评审后落地的简化与修复。评审覆盖架构简化、知识检索与上下文组织、长任务生命周期、宿主适配器边界、生产与评测语义五个方面；本次只改动确认存在缺陷的部分，其余经核对正确的机制保持原样。

主仓只保存文档，运行时改动全部落在各组件仓库。

---

## 一、确认正确、本次未改动的机制

下列实现经源码核对后判定正确，未做改动：

- **远端长任务生命周期**（`remote-dev`）：`core/job_ops.py` 的 `start_remote_job` 先落盘任务记录再提交，重复 `job_id` 以 `job_id_exists` 阻断；提交后失联记为 `submission_state="uncertain"` 且不自动重放；`_recording_failure` 在本地游标/日志提交失败时保留 `operation_completed=True`。
- **受管执行的幂等恢复**（`coordinator`）：`managed_execution.py` 的 `managed_start` 以 `digest([owner, binding_id, request_id])` 为幂等键复用既有作业，参数变更显式报错；`cancel_requested` 单调不回退。
- **回执诚实性**（`mindie-agent-codex`）：`mcp_gate.py` 在 `finally` 中本地记账失败时只追加 `accounting` 告警，不把已成功的远端结果翻成 `isError=True`。
- **外部写 `unknown` 保护**（`diagnostics`）：`reporter.py` 在 `POST` 之前经 `begin_post` 置 `uncertain`；`_record_publication_outcome` 在本地记账失败时返回 `recording_failed` 并保留 `publication_status`。
- **生产与评测语义**（`mindie-bench`）：`runner/knowledge_replay_index.py` 直接复用生产的 `RoutingIndex`、`match_conditions` 与 `token_estimate`，`knowledge_replay.py` 显式输出 `simulation_only: True`。**未发现与生产的真实分叉，因此未做任何修改。**
- **宿主差异**：四个适配器的 `paths.py` / `identity.py` / `bounded.py` / `transcript.py` / `organizer.py` / `runtime_probe.py` / `setup.py` 的差异源于 Hook 事件模型、transcript 格式与 CLI 调用方式的真实不同，未做统一。

---

## 二、本次落地的改动

### 1. explore 职责收口到知识引擎（适配器去重）

知识引擎本就完整拥有 explore 语义：`graded/index.py` 的 `finish()` 负责 query 路径，`graded/closure.py` 负责 explain 路径，两者都已剥离 L3、计算 `stripped_l3_ids`、构建 `exploration_context` 与 `mindie-rsi-subagent-pack/1` 事实包。

四个宿主仓各自持有一份 `rsi_explore.py` 副本，在引擎返回后再做第二遍改写，并已出现漂移（`cc` 的 `_compact`/`_conditional_avoid` 与 `dsh` 的 `_compact` 均无调用点）。其二次 `_normalize_avoid` 会丢弃引擎 `conditional_avoid` 中的 `avoid` 等字段，且在引擎完成预算裁剪后继续改写 payload，使 `usage.estimated_tokens` 与实际交付不符。

处理方式：各仓只保留面向 MCP 协议边界的 `schema_properties` / `parse_args` / `forwarded`，删除 `attach` 及其全部辅助函数与死代码；删除各宿主中的相关调用点。引擎侧的 `build_exploration_context` 的 `retrieved_units` / `ledger_entries` 别名参数**予以保留**——核对后确认它们仍是实际在用的公共兼容面（`loop/transport.py` 的 explore RPC、`graded/explore.py` 的 CLI、本仓测试与 `mindie-bench` 的测试都在使用）。

### 2. 检索热路径的观测写入批量化与去重

`graded/feedback.py` 的 `observe()` 每次自开写事务，而检索路径总是传 `delivery="query"`，使其只读快速路径永不生效：每个被交付单元都要付一次 `BEGIN IMMEDIATE` + `assert_authority()` 的 lstat + commit。同一单元又同时出现在 `results` 与 `cards` 中，导致计数重复累加。

处理方式：`GradedRepository.observe_delivered()` 从最终 payload 推导交付集合，按精确的 `(unit_id, revision)` 去重后，在一次可重入的 `_write_txn()` 内完成全部写入。继承前提仍只登记可读、不计为独立交付。

### 3. 统一为诚实的整包预算

`graded/repository.py` 原有一个 `token_budget < 256` 的分支（注释自述服务于单元测试），使小预算完全不受整包约束，而 `1..16000` 都是合法入参。同时 `exploration_context` 被排除在预算估算之外，`budget_scope` 的声明与实际裁剪口径不一致。

处理方式：新增 `graded/budget.py` 作为**唯一预算属主**，删除测试导向分支，预算口径统一为整个对外 payload（含 `exploration_context`），`budget_scope` 如实声明。无法满足时不再谎称满足，而是以 `budget_met=False` 与 `minimum_tokens` 上报下限；`minimum_tokens` 写入自身会改变序列化长度，因此与 `estimated_tokens` 一起收敛为联合定点。

### 4. 混合检索共用同一预算与记账

`graded/retrieval.py` 的 `mixed_query` 此前直接搬运 graded 子响应的 `usage`，使同一 payload 内 `body_token_estimate` 与 `usage.body_token_estimate` 互相矛盾、`usage.estimated_tokens` 低报；混合响应也是唯一绕过整包预算的路径。

处理方式：混合页改为调用同一个 `enforce_query_budget`，body 口径由共享的 `recompute_body_tokens` 统一计算（同时覆盖 graded 的 `inherited_rules` 与 legacy 的嵌套 `related`）。派生字段 `source_results` 通过 `derive` 回调在裁剪后、估算定型前刷新，使最终 `usage` 描述真正对外的 payload。

### 5. 交付后记账与导航页裁剪（后续修复）

在上述改动落地后暴露出两个问题：导航分支只裁剪卡片、把可移除的 legacy 负载当成不可约下限；以及 `GradedRepository.query` 在混合页完成最终组装之前就记录了观测，导致 graded 行全部被裁掉时仍虚假计数。

处理方式：导航分支先剥离可选预览、再丢弃 legacy 行，最后才裁剪卡片并声明下限；`mixed_query` 以 `observe_delivery=False` 调用 graded 子查询，在最终 payload 确定后由属主组件一次性记账，不写后再撤销。

### 6. 分页正确性修复（最终修复）

`materials/provenance.py` 的 `page_groups` 把 `related_next` 锚定在**已发送预览之后**（`after = related[-1]["ref"]`，`INITIAL_RELATED = 2`）。因此第 5 节中「整体清空 `related`」的做法会使前两个引用被永久跳过：续读从第 3 个开始，没有任何后续页会再返回它们。沿真实游标遍历到底可观测到只有 3 个引用可达，而实际应为 5 个。

处理方式：`_shed_related_previews` 改为**只剥离每条预览的 `excerpt` 文本**，保留其 `ref` 与匹配证据并显式标记 `excerpt_omitted=True`，`related_next` 游标与 `page_groups` 算法均不改动。若保留引用后仍放不下，则沿用既有的整行丢弃与 `excluded_budget` / `has_more` 语义，而不是返回会误导调用方的续读游标。

### 7. 其他小幅清理

- `loop/store.py` 的 `_write_txn` 中一个在提前返回之后恒为真的守卫已删除；`explain()` 的转发样板在保持默认值、`ref`/`refs` 行为与参数 API 完全不变的前提下收敛。
- `mixed_query` 中对 `limit` 的重复校验已删除（`query_request` 在所有相关路径上都已先行校验）；**`cc` 与 `kimi` 适配器侧的 `query_request` 预校验予以保留**——核对后确认它不是属主的重复，而是避免为非法请求冷启动后台服务的边界检查，且有专门测试覆盖。

---

## 三、改动范围

| 仓库 | 改动文件 |
| --- | --- |
| `knowledge` | 新增 `mindie_knowledge/graded/budget.py`；修改 `graded/repository.py`、`graded/retrieval.py`、`loop/store.py` 及 3 个测试文件 |
| `mindie-agent-codex` | `plugins/mindie-agent/scripts/rsi_explore.py`、`runtime_call.py`、`tests/test_mcp_knowledge_distill.py` |
| `mindie-agent-cc` | `scripts/rsi_explore.py`、`scripts/mcp_server.py`、`tests/test_knowledge_page.py` |
| `mindie-agent-kimi` | `scripts/rsi_explore.py`、`scripts/mcp_server.py`、`tests/test_knowledge_page.py` |
| `mindie-agent-dsh` | `scripts/rsi_explore.py`、`scripts/knowledge_mcp.py`、`scripts/mindie_sidecar.py`、`tests/test_bridge_protocol.py` |

生产 Python 文件共新增 **472 行**、删除 **1324 行**，净减少 **852 行**；新增行数包含尚未跟踪的 `graded/budget.py`（288 行）。四份 `rsi_explore.py` 合计从 1343 行缩减到 332 行（各 83 行），净减少 1011 行。统计相对各仓当前 `HEAD`，不计已有的其他工作改动。测试净增 422 行，用于替换原先基于伪造服务端响应的断言并覆盖本次行为修复。

`remote-dev`、`coordinator`、`mindie-bench`、`diagnostics` 未做任何改动。

---

## 四、实测验证

全部使用既有验证环境 `/Volumes/data/code/mindie-release-20261014/codex-interrupt-final-env-20261016/bin/python`，`PYTHONPATH` 指向当前检出而非已安装分发；未安装任何依赖、未运行全量套件、打包、网络或 NPU 任务。

```bash
# knowledge（受影响范围）
cd /Volumes/data/code/mindie-release-20261014/knowledge
PYTHONPATH=/Volumes/data/code/mindie-release-20261014/diagnostics-reporting \
  python -m pytest -q tests/test_graded_migration.py tests/test_context_progressive_loading.py \
    tests/test_graded_feedback.py tests/test_graded_units.py tests/test_tiered_contract_matrix.py \
    tests/test_experience_and_exploration_loop.py tests/test_graded_context_and_exploration.py \
    tests/test_domain_retrieval_and_summary_quality.py tests/test_graded_eval_harness.py \
    tests/test_graded_maintenance.py
# => 135 passed, 1 skipped
```

四个适配器的受影响协议/入口测试结果：Codex `tests/test_mcp_knowledge_distill.py` 14 passed + 5 subtests；CC `tests/test_knowledge_page.py` 13 passed + 16 subtests；Kimi `tests/test_knowledge_page.py` 9 passed + 4 subtests；DSH `tests/test_bridge_protocol.py` 5 passed。

新增与改写的行为性检查均基于真实对象，不使用伪造的服务端响应：

- 真实 SQLite 跟踪确认一次 `store.query` 只产生 **1 个写事务**，同时出现在 `results` 与 `cards` 中的单元只计一次交付，不同 revision 各自保留回执。
- 以真实 `Store` + `MaterialStore` 构造的混合语料验证：预算不可满足时如实上报 `budget_met=False` 与 `minimum_tokens`；graded 单元未实际交付时不产生计数。
- **分页遍历回归**：沿真实 `related_next` 游标调用 `Store.query` 直到耗尽，断言锚点与全部 `related_count` 个引用共 5 个互不相同的块均可达且都能 `explain` 读取。该用例在修复前确实失败（`related` 为空），修复后通过。
- 四个适配器的 explore 断言改为由真实 `RoutingIndex.query(mode="explore")` 产出的引擎结果驱动，验证适配器原样透传。

代码检查：除下述既有告警外，本次受检文件的 `ruff check` 通过，行尾均为 LF。`loop/store.py` 有 16 条 `F401` 告警，来自该模块自 `store_schema` 再导出符号的既有模式；使用同一仓库配置比较，当前文件与 `HEAD` 均为 16 条，本次未增加。

---

## 五、已知限制与后续事项

- 本次全部为 Tier 0 / Tier 1 级别的本地检查，**未运行 A2/A3 真机验证，也未进行任何端到端或效率收益验收**；相关结论不应被当作实机验证结果。
- 整包预算口径收紧后，`knowledge_query` 的默认预算（MCP schema 为 `800`）下混合响应可能无法同时容纳 graded 规则与携带嵌套预览的 legacy 任务块。当前通过 `budget_met` / `minimum_tokens` / `has_more` 如实告知调用方，默认值未作调整——是否调整默认值属于产品取舍，建议结合真实使用数据单独评估。
- `build_exploration_context` 的 `failed_attempts` 与 `ledger_entries` 两个别名在同时传入时会直接拼接（而 `units` / `retrieved_units` 会显式报错），当前无调用方同时传入，本次未改动。
- 适配器仓对共享组件的版本锁定（`uv.lock`、依赖固定、版本文件）本次**未做任何改动**；若后续需要配套发布，应按组件先发、插件后发的既有流程单独执行。

## 六、Cursor 调用与 fallback 观察

通过本机已登录的 Cursor 官方 CLI 调用，同一会话为 `10d77459-7ace-4abc-a2de-dbc55c1fa0e4`。显式模型参数为 `--model 'claude-opus-5-5[context=1m,effort=max,fast=false]'`，各后续阶段的 CLI 初始化事件均返回 `Claude Opus 5.5 1M Max`。

最初直接使用列表中的短名 `claude-opus-5-5-max` 时，初始化却显示 `300K Max`；该次只读调用已停止，并以显式上下文参数恢复原会话。这是已观察到的上下文配置不一致，不能据此认定模型发生了 fallback。

本次未收到平台的 fallback、拒绝或模型切换通知。CLI 输出未提供逐次服务端实际后端身份的可核验记录，因此这里确认的是请求配置与初始化标识，不保证服务端内部完全没有静默 fallback。改动目前保留在本地 checkout，未提交或发布。

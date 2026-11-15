# 并行架构评审与修复（2026-10-24）

[返回文档中心](README.md) · [前次简化记录（2026-10-23）](architecture-simplification-20261023.md)

> **记录范围与验收边界说明**：本文记录 2026-10-24 当轮四路并行架构评审及独立源码复核时的发现、补丁与分项验证快照，**仅覆盖实际检查与验证过的代码路径，不能冒充主产品 `0.1.1` 正式版的完整最终验收报告**。主仓 `mindie-agent` 仅承载架构与文档，运行时代码在各组件与宿主插件仓中独立修复。

## 预算和交付只有一个属主

`knowledge/graded/budget.py` 对最终交付的 `query`、`explain` 和 `mixed` payload 统一估算，包含探索上下文（`exploration_context`）及用量字段。当固定协议外包已经超过请求预算时，以 `budget_met=False` 和 `minimum_tokens` 如实表达不可约下限；单条 `explain` 合入历史兼容字段后同样重新判定预算；探索模式下的完整前提与因预算排除的前提（`premises_complete` / `excluded_premises_budget`）亦显式记账（[`knowledge #97`](https://github.com/mindie-agent/knowledge/pull/97)、[`knowledge #100`](https://github.com/mindie-agent/knowledge/pull/100)）。

观测写入以最终交付集合为准：同一知识单元同时出现在结果、卡片和基础卡片中只计一次，不同 `revision` 分别保留回执；混合子查询不提前登记交付，而是绑定其真实来源索引（`source_index`），由最终响应完成裁剪后在单个写事务中批量记录（[`knowledge #99`](https://github.com/mindie-agent/knowledge/pull/99)）；继承前提仅登记为可读，不冒充独立交付；若结果行已被裁掉但单元仍在 `exploration_context.mounted_units` 中交付，也必须计入交付，且其多个别名与结果行共用同一去重集合。

导航视图可以省略正文，但仍须保留预算内的旧材料引用。由于分页游标（`related_next`）锚定在已交付预览之后，裁剪时只能剥离预览的 `excerpt` 文本并标 `excerpt_omitted=True`，绝不能在移除引用后仍沿用原游标。独立复核修正了早先无条件清空旧材料预览行的方案，并以真实 `Store` 与 `MaterialStore` 遍历全部续页、逐条 `explain` 验证可达性。

四个宿主插件只负责 MCP 参数校验、宿主身份与协议适配，直接透传知识引擎已生成的探索结果（再次剥离 L3、重建事实包或二次归一化 `conditional_avoid` 会丢失字段，并导致引擎预算与实际响应脱节）。四端插件分支在保留探索结果原样透传的同时，已合入 `main` 上由另一工作流交付的**手动 `/mindie-agent` 会话启用门禁**与已正式发布的 **`knowledge 0.13.2`** 锁定（不抹掉手动启用门禁，也不提前宣称跨组件独立自动更新已接线完成）。

## 清理错误、远端观测与设备容量归一化

`remote-dev` 中 SSH `LocalForward` 的调用体与 `close` 同时失败时，保留主错误并附加清理诊断（修复拆分后误用未绑定 `transport` 导致 `NameError` 覆盖主错误的问题，恢复既有 `record_cleanup_failure` 调用），并删除 attached stream 中确认子进程退出后不可达的重复强杀分支，保留有界 `wait` 与 `OwnedProcess` 生命周期（[`remote-dev #43`](https://github.com/mindie-agent/remote-dev/pull/43)）。针对双 Die 昇腾 A3 910C，后续补丁（[`remote-dev #44`](https://github.com/mindie-agent/remote-dev/pull/44)）进一步将物理 Die 容量（`npu_die_count = card_count * dies_per_card`）与实测 `total - used` HBM 余量显式分开，不再跨机器硬扣固定固件常数。

`coordinator` 刷新运行中的准备任务时，因遗漏 `preparation_control` 导入而把内部 `NameError` 误记为 `uncertain`；恢复导入后，原有观测机制即可读取并持久化真实远端状态，且不改变远端提交、取消或物理设备租约协议（[`coordinator #63`](https://github.com/mindie-agent/coordinator/pull/63)）。后续补丁（[`coordinator #64`](https://github.com/mindie-agent/coordinator/pull/64)）按实测主机可用容量与声明负载需求执行运行放置准入。

`diagnostics` 明确将后台 Worker 停止信号（`cancel`）与 `reporting maintain --budget-seconds` 截止时刻统一为“停止新阶段准入 + 在完整记录边界停止摄取并保留已提交游标”（[`diagnostics #29`](https://github.com/mindie-agent/diagnostics/pull/29)），不将其冒充为操作系统服务 20 秒停机保证或 75 秒总耗时硬上界；出站对账读取的有界化方案仅作为未实施设计跟进记录，保持未知 `POST` 绝不重放、搜索未命中绝不等于不存在。`sim` 新增 `profiled_kernels` 精确捕获耗时绑定（[`sim #16`](https://github.com/mindie-agent/sim/pull/16)），仅将实测耗时中位数作为算子完成时间下界、沿用算子显式声明的工作量代理（非实测硬件 occupancy，亦非整网精度验收）。

## 评测与成本边界

默认策略选择器不能读取私有评判答案并生成合成续跑结果。未注入真实续跑执行器时，策略选择阶段与任务续跑严格分离：任务续跑标为 `not_executed`（或即使传入执行器也标为 `continuation_unverified`），续跑耗时与设备成本保持 `None`（未知），绝不用计划卡数或合成默认值填充；真实续跑所需的回执归属设计记录于 `docs/strategy-continuation-v2.md`（尚未实施，不新增第二个 runner 或签名回执链，见 [`mindie-bench #24`](https://github.com/mindie-agent/mindie-bench/pull/24)、[`mindie-bench #26`](https://github.com/mindie-agent/mindie-bench/pull/26)）。`mindie-bench` 的公开知识依赖 pin 与离线策略语料闭包已同步补齐，使策略选择测试在无外网/隔离运行时中可独立执行而不再整组跳过。

确定性策略选择不消耗模型调用：预留预算与实际观测到的模型调用分别记账；缺失用量保持 `None`，已知的选择器与执行器子账分别保留；即使单 cell 续跑超时（`unknown`）或异常（`infra`），也保留已完成的选择器判定、已消耗调用与实测超时耗时，而不波及其他 cell 或将实验总成本伪造为选择器小计。

报告生成器完全依据实际输入动态计算结论与过滤后的组件证据范围（`gate_scope`），并将回放 listener 数、fixture 校准、CPU 行为验证与真实 NPU / 模型收益严格区分。六个任务判分器已改为执行被测源码的真实 CPU 行为，同时检验已知故障（`before_reward=0`）、金标修复（`after_reward=1`）与无功能/常量负对照（[`mindie-bench #25`](https://github.com/mindie-agent/mindie-bench/pull/25)）；这些检查不追溯改写历史 Trial 的既有判分，也不替代真实 NPU 推理性能验收。

## 并发修改与版本通道协调

另一工作流同时负责手动 `/mindie-agent` 会话启用门禁及后续单组件自动更新机制。本轮经用户授权跨会话协调：
- 预算与插件 PR 均在独立 Git 工作树（`/tmp/mindie-pr-20261024/*`）中提取与验证，原共享工作树保持不动；
- `knowledge 0.13.2` 与四个宿主插件 `0.1.1` 已作为不可变标签正式发布（含手动 `/mindie-agent` 启用门禁），四端探索透传 PR（`Codex #58`、`CC #43`、`Kimi #46`、`DSH #16`）均已合并最新 `main` 以完整保留手动启用门禁与 `knowledge 0.13.2`；
- 主产品 `0.1.1` 尚未发布，下一轮运行时组合预留 `knowledge 0.13.3` 与四插件 `0.1.2`；跨组件独立自动更新在另一工作树中尚未完成四端接线与最终验收，本文不提前宣称其已完成。

## 第一轮分项验证与关联 PR 清单

以下测试数字为第一轮分项提交时的点对点验证记录（非最终合入后的全产品发布验收）：

- [knowledge #97](https://github.com/mindie-agent/knowledge/pull/97)（及后续 [#99](https://github.com/mindie-agent/knowledge/pull/99)、[#100](https://github.com/mindie-agent/knowledge/pull/100)）：整包预算、最终交付去重记账、混合检索源索引绑定、探索完整前提与导航/分页修复。第一轮隔离补丁受影响范围 `150 passed, 1 skipped`；补入事实包交付回归后相关范围 `49 passed`。
- [remote-dev #43](https://github.com/mindie-agent/remote-dev/pull/43)（及后续 [#44](https://github.com/mindie-agent/remote-dev/pull/44)）：SSH 清理诊断保留、移除不可达重试，以及双 Die 物理容量与实测 HBM 余量归一化。第一轮非 live 全套 `660 passed, 43 skipped`；SSH 定向范围 `29 passed, 18 subtests passed`，GitHub CI 7 项全通。
- [coordinator #63](https://github.com/mindie-agent/coordinator/pull/63)（及后续 [#64](https://github.com/mindie-agent/coordinator/pull/64)）：准备任务状态刷新与基于实测主机容量的运行放置准入。第一轮定向 `18 passed, 2 skipped`，GitHub CI 5 项全通。

（注：第一轮检查时，`knowledge` 共享源码广检有 4 个隔离子进程因加载宿主环境陈旧安装包而失败，`coordinator` 本地广检有 7 项基线因同类环境原因失败；PR 描述如实保留上述边界，未将本地广检包装为全绿。）

- [Codex #58](https://github.com/mindie-agent/mindie-agent-codex/pull/58)、[CC #43](https://github.com/mindie-agent/mindie-agent-cc/pull/43)、[Kimi #46](https://github.com/mindie-agent/mindie-agent-kimi/pull/46)、[DSH #16](https://github.com/mindie-agent/mindie-agent-dsh/pull/16)：第一轮在 `knowledge 0.13.1` 基线下分别为 `14/13/9/5 passed`（另含 `5/16/6/4 subtests passed`），将 `explain` 测试改为真实 `explain_closure` 输出与有效引用，CC 同步补齐 LF 配置与只读校验器；随后四端分支均已合入 `main` 上的手动启用门禁与 `knowledge 0.13.2`。
- [mindie-bench #24](https://github.com/mindie-agent/mindie-bench/pull/24)、[#25](https://github.com/mindie-agent/mindie-bench/pull/25)、[#26](https://github.com/mindie-agent/mindie-bench/pull/26)：报告证据范围、策略选择与续跑成本边界、公开知识依赖与语料闭包，以及六个行为判分器与重新生成的 soundness 回执（无功能/常量负对照 `7 passed`）。
- [diagnostics #29](https://github.com/mindie-agent/diagnostics/pull/29)、[sim #16](https://github.com/mindie-agent/sim/pull/16)、[mindie-agent #273](https://github.com/mindie-agent/mindie-agent/pull/273)：诊断摄取停止准入与出站对账跟进设计稿、`profiled_kernels` 精确捕获耗时绑定，以及执行资源预算/容量/硬限制分层设计文档。

第一轮 `mindie-bench` 合并源码在锁定运行时中的串行非 live 全套结果为 `1368 passed, 7 skipped, 6 deselected`（耗时 `220.78s`，峰值 RSS 约 `366.9 MiB`；7 个跳过涉及未安装可选 `coordinator`/`profiler`/`sim` 组件或非 Linux 环境，6 个 deselected 为 `live_npu`）。修正知识库 pin 与离线语料闭包后，策略选择测试均实际执行，不再因缺少 API 而整组跳过。第一轮时 `diagnostics` 非 live 范围为 `325 passed, 4 skipped`。

六个判分器已通过正式 runner 重建 soundness 回执：5 个 L2 本地检查及现有 A5 容器中的 L3 DSpark 均满足 `before_reward=0, after_reward=1, model_calls=0`（L3 执行前后设备进程列表为空，HBM 均为 `4800 MiB`，容器镜像按当前实际 digest 绑定；CPU 方法 oracle 本地峰值 RSS 约为 `209–220 MiB`）。这些检查仅验证判分器自身 soundness，不重新判定历史 Trial，也不证明 NPU 模型推理性能提升。

所有变更均保持 Unix `LF` 行尾并通过 Pre-PR 自查。当前记录不包含新的 A2/A3 实机端到端模型收益重跑或主产品 `0.1.1` 正式 Release 发布。

## Cursor 模型与 fallback 证据

使用显式参数 `claude-opus-5-5[context=1m,effort=max,fast=false]`，各路初始化返回 `Claude Opus 5.5 1M Max`。初始化标识不能证明后续服务端始终使用同一模型。

知识库、插件和执行链路三个会话在最终输出中收到明确通知：Opus 5.5 触发安全过滤，平台自动切换为 Opus 4.8。这三个会话均未继续使用，日志中通知后无工具调用；不能将它们宣称为全程 Opus 5.5。主审独立复核、修改并重新验证了交付补丁。评测修复和独立只读评审未观察到切换通知；CLI 不提供逐请求服务端后端身份，未出现通知也不能证明不存在静默路由。

评测路的一次全套验证被重复启动且共用临时目录，主审已终止两组进程并作废该次结果；主审随后在修正依赖和运行配置后执行了上述最终串行全套。此处不以失效结果支持通过结论。

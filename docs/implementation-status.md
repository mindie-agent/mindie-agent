# 统一实施进度

2026-09-21，三个适配器已合入 main。本文记录代码合入和实际验收范围，不是首版发布通过结论。Windows 按用户安排在合入后使用专门机器推进。

主任务统一负责设计、文档、跨仓审核、进度和最终验收；具体代码实现交给本地 Kimi/Grok，Claude Code 适配由专门子代理协调。常规取舍优先遵守[九条原则](design-principles.md)，不额外增加每任务审批和收尾负担。宿主明确要求的用户信任确认仍由用户完成。

## 实现与真实证据分列

| 范围 | 实现进展 | 已有真实证据 | 尚未完成 |
| --- | --- | --- | --- |
| 共享知识运行时 | [PR45](https://github.com/mindie-agent/knowledge/pull/45) 已合入：持久授权、原子空闲判断、单次尝试、精确回执及提交后清理 | 对真实已合并知识 PR 的未知结果核对、准确版本正文恢复；Codex 原生读取与跨版本接续实际消费新接口 | 最终适配器的贡献闭环复验；组件 CI 不代替这一项 |
| Codex | [PR3](https://github.com/mindie-agent/mindie-agent-codex/pull/3) 已合入，main `8ffc72d`；安装配置绑定、持久授权、完整版本切换 | Luna/max 原生只读与完整正文读取；同任务更新后旧入口和原远端作业仍可用；无继承配置环境变量或临时 MCP 配置的原生安装验收；真实安装后注入结果丢失，4.47 秒恢复旧包并回读；本地整理器 53.3 秒保留已有 NPU 数值和不确定性 | 新 Stop Hook 的原生信任及最终贡献闭环；可选反馈；OS 定时触发 |
| Kimi | [独立仓库 PR1](https://github.com/mindie-agent/mindie-agent-kimi/pull/1) 已合入，main `421e22b`；安装代码独立保留，MCP/Hook/调度器绑定配置 | 2.0.2 / K3 max：原生回读两 MCP、两 Hook、七命令；显式只读；同任务及旧 MCP 跨更新保留授权并清理原作业；移走源码、清除配置环境变量仍可读取；真实安装结果丢失后 6.92 秒恢复旧包并回读 | 整理质量仍有未经证实的执行时序推断；最终贡献闭环；当前宿主 fork 补验；OS 定时触发 |
| Claude Code | [独立仓库 PR1](https://github.com/mindie-agent/mindie-agent-cc/pull/1) 已合入，main `d8545a3`；原生身份、显式启用及共享组件适配 | 2.1.269 / deepseek-flash high：通用 remote、只读启用及正文读取；跨真实更新同任务、旧 MCP、授权和原作业仍可用；新任务及原生 fork 拒绝继承授权；关闭贡献时 Stop 无采集；开启后真实 Stop 调用本地整理器一次，隐私扫描拦截两候选，无发布；12.96 秒完成真实原生回滚 | 有效领域经验生成及发布/清理/新任务复用闭环；默认审批路径；OAuth-only 整理器；OS 定时触发 |
| 知识分发和 Bot | 正式内容源为 [knowledge-vllm-ascend/main](https://github.com/mindie-agent/knowledge-vllm-ascend/tree/main)；使用现有 Grok Bot 软件 | 先前候选有真实 PR、Bot 定时补查合入、新任务/NPU 消费证据 | 最终重构版本必须重新核对；原生 PR 事件投递不由定时补查成功推定 |

共享运行时 Linux/macOS/Windows CI 已通过；三端均有开发检查及上述范围的原生证据。代码修正后只复验受影响的范围，不以测试数量作为产品通过依据。实际 Claude Code 模型是本机配置的 deepseek-flash，不能称为 Anthropic 基础模型验收。

## 本次合入与更新检查

三个 PR 的最终提交均完成审核并退出草稿状态，2026-09-21 已分别合入各自 main。Codex 和 Kimi 的最终 PR CI 通过；Claude Code 未配置 CI，有 35 项开发检查和上表原生证据。九条原则不变，未为这些合入添加额外候选配额或 Windows 前置要求。

合入后在已有隔离安装中直接调用实际 updater check，未注入候选 SHA、未调用模型、未设置新的 OS 定时器：

| 宿主 | 实际远端 main 检查结果 |
| --- | --- |
| Codex | 7.15 秒解析并安装 `8ffc72d`，原生版本 `0.1.0+codex.20260921004020185845` 回读 installed/enabled；知识 feed 同步成功 |
| Kimi | 10.31 秒解析并切换到 `421e22b`，实际原生安装及资源回读成功；知识 feed 同步成功 |
| Claude Code | 17.48 秒解析并安装 `d8545a3`，原生版本 `0.1.0+mindie.d8545a3c7c99` 及两个 MCP 的完整新 generation 准确回读；正式知识源 `eb311496`，2 条记录、unchanged |

这些结果证明 main 解析、准备、安装与同步的实际执行路径，不证明 OS 定时器已自行触发。用户的生产 Codex 配置和 Hook 信任未被修改。

Claude Code 的旧隔离 fixture 还保留 `local/unconfigured` 占位源，其同步报 repository not found；updater 汇总仍写 `feed_sync=ok`，因此不能用该汇总推定每个 feed 都成功。正式源成功与占位源失败已分别留证。后续需修正按 feed 汇总错误的可观察性；这项合入后发现的问题不应被主分支安装成功掩盖。

## 合入后继续推进

1. 完成有用经验的 Stop → 本地整理脱敏 → GitHub PR → Bot 审阅合入 → 新任务读取和使用路径。保留准确性、实际作用和失败记录，不为制造 PR 重复提交实验变体。Kimi 最近整理保留数值但过度推断初值未执行；Claude Code 候选含配置流水；二者均不计为内容质量通过。
2. 核对启用/关闭贡献、失败暂停、未知提交恢复、确认提交后清理和后续补充；可选反馈及下库也需真实证据。
3. 验收 OS 实际定时触发和必要的原生 Hook 信任，复用已通过的安装、原生回滚及任务/作业接续证据。
4. 用户在专门 Windows 机器上基于已合入 main 推进，三个适配器可分别进行，不必等待上述所有 macOS 工作完成。Windows 仍在首版目标范围；CI 不能替代实机。

旧业务 Skill、profiling 分析、自动 Skill 提炼、进一步领域和 Harness 扩展保持暂缓。旧 profiling PR76 不在本轮合入范围。模型测试每次都有明确边界，不因失败自动新开任务或反复重试。实现合入与发布验收分列，未完成项目不会因 PR 合并而自动标记通过。

## 证据解释

2026-09-18 的 NPU 与闭环记录只证明当时版本，保留为历史材料。安装 API 返回成功不代表 MCP 已加载；原生列表、实际调用、Hook 交付和内容复用分别判断。遇到失败保留实际原因，修复后只补相应范围的证据。实际案例包括 Kimi 安装列表“enabled”但零 MCP，以及 Claude updater 在真实下载前拒绝整数 argv；修正后的结果未覆盖失败记录。详细记录见 [Codex 验收](https://github.com/mindie-agent/mindie-agent-codex/blob/main/docs/acceptance-lifecycle-2026-09-21.md)、[Kimi 验收](https://github.com/mindie-agent/mindie-agent-kimi/blob/main/docs/acceptance.md)和 [Claude Code 验收](https://github.com/mindie-agent/mindie-agent-cc/blob/main/docs/acceptance.md)。

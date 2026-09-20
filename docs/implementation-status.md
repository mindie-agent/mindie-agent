# 统一实施进度

2026-09-21，macOS 开发检查点。本文是实际进展，不是首版发布通过结论。

主任务统一负责设计、文档、跨仓审核、进度和最终验收；具体代码实现交给本地 Kimi/Grok，Claude Code 适配由专门子代理协调。常规取舍优先遵守[九条原则](design-principles.md)，不额外增加每任务审批和收尾负担。宿主明确要求的用户信任确认仍由用户完成。

## 实现与真实证据分列

| 范围 | 实现进展 | 已有真实证据 | 尚未完成 |
| --- | --- | --- | --- |
| 共享知识运行时 | [PR45](https://github.com/mindie-agent/knowledge/pull/45) 已合入：持久授权、原子空闲判断、单次尝试、精确回执及提交后清理 | 对真实已合并知识 PR 的未知结果核对、准确版本正文恢复；Codex 原生读取与跨版本接续实际消费新接口 | 最终适配器的贡献闭环复验；组件 CI 不代替这一项 |
| Codex | [PR3](https://github.com/mindie-agent/mindie-agent-codex/pull/3) 草稿，代码候选 785bdcb | Luna/max 原生首次选择及读取；同一任务真实更新后原授权不变，旧入口及原远端作业仍可用并已清理；最终原生安装包在无继承配置环境变量、无临时 MCP 配置下完成普通 Skill 启用、两条命中及 3,394 字符正文读取，采集状态为零 | 新 Stop Hook 的原生信任及贡献闭环；Windows 实机 |
| Kimi | [独立仓库 PR1](https://github.com/mindie-agent/mindie-agent-kimi/pull/1) 草稿；安装代码保留在独立目录，MCP/Hook/调度器绑定明确配置 | 2.0.2 / K3 max：原生安装回读两 MCP、两 Hook、七命令；显式只读检索；同一任务及旧 MCP 进程跨真实版本切换保留授权并清理原作业；移走安装源码、清除配置环境变量后，新任务仍读取 2,502 字符正文并说明具体复用方法 | main 定时调度的原生验收；整理器曾到 120 秒上限而无输出，修后质量仍待验收；贡献闭环 |
| Claude Code | [独立仓库 PR1](https://github.com/mindie-agent/mindie-agent-cc/pull/1) 草稿；代码候选 c8f1436 | 本地 2.1.269 / deepseek-flash high：未启用知识时真实 remote 调用；显式只读启用及 2,502 字符正文读取；真实版本切换后同一原生任务、两个旧 MCP 进程、授权及原作业仍可用；新任务和原生 fork 均拒绝继承知识授权；默认关闭 Stop 无采集或继续 | 贡献整理/发布/清理闭环、实际 main 定时检查及故障回滚、默认工具审批路径、OAuth-only 整理器和 Windows 实机 |
| 知识分发和 Bot | 正式内容源为 [knowledge-vllm-ascend/main](https://github.com/mindie-agent/knowledge-vllm-ascend/tree/main)；使用现有 Grok Bot 软件 | 先前候选有真实 PR、Bot 定时补查合入、新任务/NPU 消费证据 | 最终重构版本必须重新核对；原生 PR 事件投递不由定时补查成功推定 |

共享运行时 Linux/macOS/Windows CI 已通过；三端均有开发检查及上述范围的原生证据。代码修正后只复验受影响的范围，不以测试数量作为产品通过依据。实际 Claude Code 模型是本机配置的 deepseek-flash，不能称为 Anthropic 基础模型验收。

## 当前推进顺序

1. 核对三端真实 main 定时更新、失败回滚及必要的原生 Hook 信任。安装配置绑定、同任务授权/远端作业接续已通过的证据按范围复用。
2. 对有实际价值的经验走完整的 Stop → 本地整理脱敏 → GitHub PR → Bot 审阅合入 → 新任务读取和使用路径。记录内容准确性和实际作用，不为制造 PR 重复提交相同实验变体。
3. 核对启用/关闭贡献、失败暂停、未知提交恢复、确认提交后清理和后续补充；可选反馈及下库也要有实际证据。
4. 用户提供 Windows 机器后做相同宿主路径的实机验收。Windows 仍在首版目标范围；CI 不能替代。

旧业务 Skill、profiling 分析、自动 Skill 提炼、进一步领域和 Harness 扩展保持暂缓。模型测试每次都有明确边界，不因失败自动新开任务或反复重试。

## 证据解释

2026-09-18 的 NPU 与闭环记录只证明当时版本，保留为历史材料。安装 API 返回成功不代表 MCP 已加载；原生列表、实际调用、Hook 交付和内容复用分别判断。遇到失败保留实际原因，修复后只补相应范围的证据。实际案例包括 Kimi 安装列表“enabled”但零 MCP，以及 Claude updater 在真实下载前拒绝整数 argv；修正后的结果未覆盖失败记录。详细记录见 [Codex 验收](https://github.com/mindie-agent/mindie-agent-codex/blob/codex/lifecycle-onboarding-20260920/docs/acceptance-lifecycle-2026-09-21.md)、[Kimi 验收](https://github.com/mindie-agent/mindie-agent-kimi/blob/codex/kimi-plugin/docs/acceptance.md)和 [Claude Code 验收](https://github.com/mindie-agent/mindie-agent-cc/blob/codex/claude-native-adapter/docs/acceptance.md)。

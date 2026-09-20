# 统一实施进度

2026-09-21，macOS 开发检查点。本文是实际进展，不是首版发布通过结论。

主任务统一负责设计、文档、跨仓审核、进度和最终验收；具体代码实现交给本地 Kimi/Grok，Claude Code 适配由专门子代理协调。常规取舍优先遵守[九条原则](design-principles.md)，不额外增加每任务审批和收尾负担。宿主明确要求的用户信任确认仍由用户完成。

## 实现与真实证据分列

| 范围 | 实现进展 | 已有真实证据 | 尚未完成 |
| --- | --- | --- | --- |
| 共享知识运行时 | [PR45](https://github.com/mindie-agent/knowledge/pull/45) 已合入：持久授权、原子空闲判断、单次尝试、精确回执及提交后清理 | 对真实已合并知识 PR 的未知结果核对、准确版本正文恢复；Codex 原生读取与跨版本接续实际消费新接口 | 最终适配器的贡献闭环复验；组件 CI 不代替这一项 |
| Codex | [PR3](https://github.com/mindie-agent/mindie-agent-codex/pull/3) 草稿，候选 3aefd89 | Luna/max 原生首次选择、只读检索及正文读取；同一任务真实更新后原授权不变，旧入口检索到两条经验；原远端作业 running → stop → cancelled，已清理 | 新 Stop Hook 的原生信任及贡献闭环；Windows 实机 |
| Kimi | [独立仓库 PR1](https://github.com/mindie-agent/mindie-agent-kimi/pull/1) 草稿 | 0.42.0 / K3 max 真实 Slash、普通后续选择、检索/正文读取、来源与 Fork 边界；2.0.2 真实安装暴露最终包的 MCP 命令被拒绝 | 修最终包加载和回读；最终更新接续；2.0.2 整理器曾到 120 秒上限而无输出，修后质量仍待验收；贡献闭环 |
| Claude Code | [独立仓库](https://github.com/mindie-agent/mindie-agent-cc) 已建立，子代理协调实现 | 本地 2.1.269 隔离环境的原生安装/更新回读、MCP 连通及入口/Hook/tool-use ID 机制探测；当前实际模型 deepseek-flash / high | 最终适配器的显式激活、跨任务隔离、真实工具调用、更新接续与贡献闭环；机制探测不等于产品通过 |
| 知识分发和 Bot | 正式内容源为 [knowledge-vllm-ascend/main](https://github.com/mindie-agent/knowledge-vllm-ascend/tree/main)；使用现有 Grok Bot 软件 | 先前候选有真实 PR、Bot 定时补查合入、新任务/NPU 消费证据 | 最终重构版本必须重新核对；原生 PR 事件投递不由定时补查成功推定 |

共享运行时 Linux/macOS/Windows CI 已通过；Codex 候选的适配检查已通过。Kimi 的开发检查和真实安装发现仍在修正。测试数量不是产品通过依据。

## 当前推进顺序

1. 先修真实宿主暴露的装载、身份参数和 Hook 时间边界问题，再进行最终入口、默认不采集及更新接续验收。
2. 对有实际价值的经验走完整的 Stop → 本地整理脱敏 → GitHub PR → Bot 审阅合入 → 新任务读取和使用路径。记录内容准确性和实际作用，不为制造 PR 重复提交相同实验变体。
3. 核对启用/关闭贡献、失败暂停、未知提交恢复、确认提交后清理和后续补充；可选反馈及下库也要有实际证据。
4. 用户提供 Windows 机器后做相同宿主路径的实机验收。Windows 仍在首版目标范围；CI 不能替代。

旧业务 Skill、profiling 分析、自动 Skill 提炼、进一步领域和 Harness 扩展保持暂缓。模型测试每次都有明确边界，不因失败自动新开任务或反复重试。

## 证据解释

2026-09-18 的 NPU 与闭环记录只证明当时版本，保留为历史材料。安装 API 返回成功不代表 MCP 已加载；原生列表、实际调用、Hook 交付和内容复用分别判断。遇到失败保留实际原因，修复后只补相应范围的证据。

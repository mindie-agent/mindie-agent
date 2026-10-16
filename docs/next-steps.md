# MindIE Agent 后续迭代

[English](next-steps.en.md) · [返回文档索引](README.md)

当前产品与完整材料设计分别见 [`docs/architecture.md`](architecture.md) 与
[`docs/knowledge-system.md`](knowledge-system.md)，所有演进遵循
[`docs/design-principles.md`](design-principles.md)。

首发 `0.0.1` 已作为普通内测 Release 正式发布，覆盖 Codex / Claude Code 与 macOS、
原生 Windows、Windows WSL 六个宿主与平台组合。精确版本、配套组件发行映射与已知限制见
[`docs/releases/0.0.1.md`](releases/0.0.1.md)。

## 现阶段推进重点

- **真实业务复用收益评测（Benchmark）**：独立推进端到端业务效果与效率基准评测，验证知识与经验闭环在真实昇腾开发任务中的实际收益（首发版本不预先宣称量化收益）。
- **上游宿主已知问题跟进**：持续跟进 OpenAI Codex CLI 子代理中断信号未送达待处理工具调用的上游修复进展；在此期间不在插件内引入破坏边界的私有进程监控或武断超时。
- **跨领域与更多宿主扩展**：Kimi Code 首发集成、历史业务 Skills 迁移整理与性能 Profiling 能力继续作为独立迭代方向按需推进。
- **日常开发体验零负担**：常规业务开发直接使用现有插件与按需工具，不增加日常手动激活、强制查询或收尾命令。

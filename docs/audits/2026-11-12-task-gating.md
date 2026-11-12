# 任务门禁与独立工作连续性复查

本轮从“缺少 MindIE 任务绑定，因而无法检查测试资源”的反馈出发，检查共享组件与六端插件的实际调用链。截图没有原始工具请求和响应，不能仅凭截图断言当时命中了哪个实现分支；以下结论来自源码与隔离回归。

## 确认问题与修复

1. **独立环境接口被 MCP 任务关联查询提前拦截。** Coordinator 的 `ops.mindie_call` 已将 `hosts`、`probe`、`container`、`lease` 与受管任务操作分开，但 `task_server._call_tool` 对携带 Codex/Kimi 元数据的请求统一执行 `AgentSessions.native_context`。不存在任务关联时，环境接口尚未执行即返回 `native session association is missing or ambiguous`。相同查询不带元数据却成功，形成了与业务无关的额外门禁。
2. **公开指引没有充分区分任务绑定、原生调用身份和设备租约。** 六端保留原生替代路径，但部分 profiler 表述容易将实际设备采集的租约要求扩展到离线分析。六端工具目录和入口指引统一明确：独立环境操作、已授权的源码和模型定位、CPU 测试、离线 profiler 分析和仿真不以受管任务绑定或设备分配为前置条件。

Coordinator 仅在受管任务操作或显式选择 `context_file` 时解析原生任务归属。环境操作省略该字段时不自动附加任务上下文，也不创建关联记录。受管任务隔离、显式上下文冲突拒绝、未知外部写对账，以及实际 NPU/端口租约仲裁继续由原有实现负责。

## 审查范围

| 范围 | 检查的边界 | 结论 |
| --- | --- | --- |
| coordinator | MCP、两种 CLI、任务关联、独立环境处理器、失败继续入口 | 修复 MCP 入口范围错误，明确公开目录与契约 |
| remote-dev | 通用 MCP 调用、端点参数、源码探测、后台作业归属、原生替代说明 | 没有发现知识激活或受管任务绑定的额外前置条件；原生作业身份保留 |
| 六端插件 | Codex、Claude Code、Kimi、DSH、Antigravity、WorkBuddy 的组件转发、知识准入、回执与入口指引 | 确定性工具不要求知识租约；更新目录及指引，保留原生身份、nonce/bind 和不重放语义 |
| knowledge | 知识调用的显式激活与贡献授权边界 | 授权只限制对应知识能力，不作为独立组件准入 |
| diagnostics | 本地状态与支持包导出、显式远端报告授权 | 本地操作与报告授权分离，不要求受管任务绑定 |
| debugger、profiler、sim、npu-top | CLI、离线分析和只读观察入口 | 未发现 MindIE 任务关联门禁；实际设备动作与观察明确区分 |
| mindie-bench | CLI、评测准入与真实资源归属 | 保留评测完整性及设备占用条件，不作为普通文件/SSH 排查前置条件 |

此次“全量”指上述产品调用与连续性边界的全面复查，不宣称穷尽所有业务算法缺陷，也不以离线回归替代真实模型/NPU E2E。

## 回归与发布范围

新增回归覆盖无任务关联的 Codex/Kimi 主会话与子调用、独立主机/探测/容器操作、租约缺参的真实业务报错、显式上下文归属冲突，以及真实 stdio 进程中独立请求成功后受管任务仍被正确拒绝、连接继续响应的行为。

最终候选的受影响范围回归为 105 passed，另有 24 subtests。Coordinator 首轮 Windows 全量为 1486 passed / 110 skipped / 8 failed / 24 errors；使用短临时目录和 UTF-8 重跑原失败项后，27 项通过，剩余五项分别涉及本机没有固定 `Program Files/Git` 路径、符号链接权限及原生缓存长路径。未修改这些测试来掩盖现场限制，全量通过与否继续以干净平台 CI 分别核验。

版本按独立发布范围推进：Coordinator `0.7.7`、Codex `0.1.27`、Claude Code `0.1.18`、Kimi `0.1.19`、DSH `0.1.17`、Antigravity 与 WorkBuddy 均为 `0.1.9`。共享组件独立更新不依赖主产品通道重发；本轮不改写历史 `channels/0.1.json` 组合。

发布前 R1–R6 已通过，包括本机宿主兼容性、历史组合与实际最新正式组件源。开发回归、平台 CI、正式发布和发布后升级验收分别记录；未完成的阶段不作为成功证据。

最终源码复核中，R1/R2/R4/R5/R6 通过，一次 R3 强制查询 mindie-bench 正式源遇到 URL 超时；该失败保留，重新执行只读完整检查，不将超时当作“没有更新”或验收通过。

开发 PR：Coordinator [#77](https://github.com/mindie-agent/coordinator/pull/77)、Codex [#109](https://github.com/mindie-agent/mindie-agent-codex/pull/109)、Claude Code [#72](https://github.com/mindie-agent/mindie-agent-cc/pull/72)、Kimi [#74](https://github.com/mindie-agent/mindie-agent-kimi/pull/74)、DSH [#44](https://github.com/mindie-agent/mindie-agent-dsh/pull/44)、Antigravity [#12](https://github.com/mindie-agent/mindie-agent-agy/pull/12)、WorkBuddy [#10](https://github.com/mindie-agent/mindie-agent-wb/pull/10)。平台 CI、合入和正式发布继续沿这些提交的正常受保护流程推进。

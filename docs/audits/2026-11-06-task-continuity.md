# 任务连续性 P0 契约与独立审查

MindIE 是通用 Agent 的附加能力。用户目标不应被插件的知识准备、可选组件、安装配置、诊断或本地账本变成新的前置条件。失败必须如实呈现，已成功的业务结果必须保留；对独立步骤和已授权的等价宿主工具应保持继续路径。身份、权限、资源归属和未知远端写入不能通过降级绕过。

## Astra max 独立审查

用户明确要求独立 review，本轮使用 `gpt-6-astra`、`reasoning_effort=max`，不继承主代理聊天历史，只提供仓库、待审提交与用户目标。审查代理未修改代码。第一轮确认三项 P1，未确认 P0 级具体缺陷；这里的 P0 指产品连续性的验收优先级。

| 确认问题 | 实际复现 | 修复 |
| --- | --- | --- |
| AGY/WB 把返回型失败当成功 | 真实 `remote_write` 的路径越界返回 `outcome=blocked`，适配器却返回 `isError=false`、回执 `succeeded` | 从 remote-dev 提取共享纯结果分类函数；业务失败、未知提交、原生命令退出和成功后的记账失败使用同一规则 |
| AGY 一次性绑定被拒后继续使用旧会话 | 发布一次 bind，连续两次 `remote_auth status` 均执行，第二次继承前次写入的 `REMOTE_DEV_SESSION_ID` | 有绑定库时必须成功 claim；无绑定库时仅接受验证过的原生 `AGY_CONVERSATION_ID`。不合成默认身份、不从业务环境变量恢复授权 |
| 单次准入错误杀死整个 MCP 连接 | 向真实子进程发送 initialize、失败工具调用、ping；旧版本只返回 initialize 就退出 | 准入失败返回该请求的 `isError=true / execution=not_started`，进程继续响应 ping、目录与其他独立请求 |

新增测试覆盖真实共享组件的本地拒绝路径、未知远端提交捕获、SQLite 回执、A/B 会话切换、bind 重放拒绝，以及实际 stdio 连续请求。没有用伪造硬件负载冒充验收，也没有为了保持连接跳过身份或必要的回执准入。

## 同轮补强

- **已验证认证与本地档案分离**：认证或公钥维护已成功时，档案保存失败以 `receipt_warning` 和 `receipt_unconfirmed` 返回。已有连接准备使用本次已验证的凭据继续；新档案没保存时不返回可解析的 `auth_ref`，只保留真实可用的直接密钥信息。
- **Coordinator 不虚报 ready**：认证完成但档案未保存时返回 `partial / registration=not_started`，保留嵌套认证成功事实，不登记假引用或向监控发布不存在的档案。
- **六端指引保持原任务继续**：知识、可选组件、引导和账本不能阻塞独立工作；可以使用已授权的等价宿主工具。Coordinator 管理的工作继续遵守租约，原生替代路径必须已有可验证的资源预约；无法确认资源归属时仅暂停对应设备动作。
- **故障后替代路径**：Codex 的组件缺失与知识源不可用提示明确引导继续代码检查、文档分析和原生工具，而非要求先修复整套插件。
- **可复现 CI**：AGY/WB 原先未跟踪 `uv.lock`，本机残留锁也与当前 manifest 不一致。本轮将生成锁纳入版本控制，并在 Linux/Windows 从干净 checkout 按锁安装非 editable 共享依赖，再测试当前原生适配器。不能把本机锁成功等同于干净 CI 可用。

## 验证与发布状态

共享候选为 `96b7c1d300c299e2adc46fcdf98be17e834750e1`，由 Codex、AGY、WB 的 manifest 和 lock 同时引用。相关 PR 沿用 [remote-dev #55](https://github.com/mindie-agent/remote-dev/pull/55)、[Codex #93](https://github.com/mindie-agent/mindie-agent-codex/pull/93)、[AGY #6](https://github.com/mindie-agent/mindie-agent-agy/pull/6)、[WB #5](https://github.com/mindie-agent/mindie-agent-wb/pull/5) 与[系统文档 #322](https://github.com/mindie-agent/mindie-agent/pull/322)。

配套变更为 [Coordinator #71](https://github.com/mindie-agent/coordinator/pull/71)、[Claude Code #65](https://github.com/mindie-agent/mindie-agent-cc/pull/65)、[Kimi #65](https://github.com/mindie-agent/mindie-agent-kimi/pull/65)、[DSH #37](https://github.com/mindie-agent/mindie-agent-dsh/pull/37)。三个依赖新共享接口的宿主 PR 保留草稿，正式交付仍需先发布共享组件。

本地验证：共享认证与结果分类范围 55 passed；协议、Schema 与观测范围 67 passed / 30 subtests；Codex 82 passed / 3 skipped / 5 subtests；AGY 14 passed；WB 14 passed；Coordinator 8 passed。固定认证结果与真实 SSH 验收分开记录，CI 以各 PR 当前提交为准。发布就绪检查仍因既有渠道/源码及 README 不同步而在 R3/R6 失败，R1/R2/R4/R5 通过；本轮不修改渠道、不声称客户端已更新。

第二轮 Astra max 复核独立运行 87 项隔离回归全部通过，并额外复现了 WB knowledge surface 的准入异常遗漏；该遗漏修复后用相同真实 stdio 探针确认返回完整 `[1,2,3,4]`、失败调用 `not_started`、ping 和 6 项知识目录正常。当前独立审查范围内没有未关闭或新增 P0/P1。

最新共享候选的全部 CI 已通过。[真实 SSH 验收](https://github.com/mindie-agent/remote-dev/actions/runs/42154502701/job/127685670805)在 PowerShell 两组各 5 passed（14.82s / 13.60s）、实际 WSL2 为 5 passed（14.28s），共 15 项；新增项验证本地档案保存失败后，新进程通过已验证密钥继续执行。此证据仍不代表用户业务机器或已安装客户端已更新。

原生适配器的新增干净安装 CI 已通过：[AGY](https://github.com/mindie-agent/mindie-agent-agy/actions/runs/42155906668) 为 Linux 10 passed / Windows 10 passed，[WB](https://github.com/mindie-agent/mindie-agent-wb/actions/runs/42155926527) 为 Linux 9 passed / Windows 9 passed。两者均从提交的锁文件安装非 editable 共享依赖，测试当前 checkout 的原生适配器，覆盖原先仅格式检查无法验证的行为。

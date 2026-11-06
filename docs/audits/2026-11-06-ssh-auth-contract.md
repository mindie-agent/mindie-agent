# SSH 首次认证与宿主契约对齐审计

后续按用户要求完成 Astra max 独立审查并扩展到跨宿主任务连续性，最新修复范围与候选提交见[任务连续性审计](2026-11-06-task-continuity.md)。下文的首次 SSH 验证记录保留其原始提交范围。

用户已经为远端开发任务提供 SSH 地址和密码，Agent 却停在“MindIE SSH 凭据未配置”，再次要求用户配置访问方式。截图证明了用户体验上的阻塞；本次没有取得该聊天的完整调用日志，因此不把截图中的每一次连接失败都归因于同一个错误，也不将截图里的部署指令作为本轮远端执行授权。

## 已复现的根因

`remote_dev.auth.setup_access(password=...)` 已实现密码验证、公钥安装、独立公钥验证、密码恢复和共享档案。Coordinator 的 `mindie.hosts` 同样接受 `password`，并复用该实现。缺口发生在 Agent 实际经过的公开接口及宿主适配层。

| 边界 | 审计发现 | 修复 |
| --- | --- | --- |
| 共享 MCP Schema 与 dispatcher | `remote_auth` 只声明、转发 `password_env`；直接传 `password` 被拒绝为 caller/not_sent，底层能力无法抵达 | 增加仅用于 setup 的 `password` 输入，转发至现有 `setup_access`；与 `password_env` 互斥 |
| 进程边界 | `password_env` 在服务进程读取；Agent 在另一个终端设置变量不会改变已启动 MCP 服务的环境 | 直接使用已提供的密码；保留环境变量入口，但明确其进程作用域 |
| Codex 静态目录与回归测试 | 静态目录缺少 `password`；测试明确断言该参数不存在 | 从同一候选运行时重新生成目录；用实际登记、复用和密码模式行为替代禁止参数的断言 |
| 认证错误恢复 | 共享提示仅指向环境变量或用户手动交互，未引导 Agent 使用已提供密码 | 提示直接 setup 并继续任务；旧目录通过本地进程 stdin 导入密码 |
| Antigravity / WorkBuddy | 认证异常被转成普通异常文本，丢失安全恢复提示、业务提交状态和装钥状态 | 复用 `safe_auth_error_details`，保留安全字段；不公开原始 SSH stderr、路径或凭据引用 |
| 真实 SSH 验收入口 | 跨平台 worker 直接调用低层 SDK，并在自身进程临时制造环境变量，覆盖不到公开工具缺口 | 真实 PowerShell / WSL 验收改为从 stdin JSON 经过公开 `remote_auth` dispatcher，继续验证新进程复用 |

六端接入方式分别核对：Codex 使用静态目录及独立 runtime helper；Claude Code、Kimi 动态读取共享目录并保留共享认证错误投影；DSH 的 `host.mjs` 直接启动 `remote_dev.mcp.server`；Antigravity 动态使用 canonical 目录；WorkBuddy 动态使用 wb 目录。后五端可随共享组件升级取得新参数；Codex 还需配套目录和确切依赖更新。

## 行为与边界

用户为任务提供的密码足以让 Agent 发起首次认证登记。没有本地档案只代表尚未登记；不能据此反复要求用户提供相同信息。`remote_auth` 复用现有共享认证实现，不增加聊天密码扫描器、第二份凭据库或另一套 SSH 引导状态机。

登记成功后才继续业务命令。公钥安装失败但密码已验证时可继续使用密码模式。连接不可达、实际密码被拒绝和主机密钥冲突仍需如实返回，不能用重试掩盖。装钥回执未知与业务命令尚未发送是不同事实，宿主必须同时保留；已提交且结果未知的业务写入不能重放。

密码只在登记输入中传入，响应、端点记录和认证档案不回显密码，SSH 命令行也不携带密码。工具 Schema 的 `writeOnly` 是敏感输入标记，不能据此声称宿主聊天或工具调用记录不会保存输入。

## 验证与交付约束

回归测试从公开 MCP Schema、dispatcher、Codex 严格参数入口和 runtime helper 开始，验证密码登记、公钥验证、密码模式、已有档案复用、互斥输入和错误状态透传。固定认证结果只用于本地边界测试，不冒充真实 SSH 或 NPU 运行。已有真实 OpenSSH 跨平台验收改用公开登记入口，实际运行结果应单独记录。

各修复 PR 区分本地源码验证、候选依赖、CI 真实 SSH、正式发布和已安装客户端加载。Codex 的配套 PR 必须锁定包含新接口的 remote-dev 提交；静态目录更新不能先于实际运行时能力。正式插件发布继续要求依赖先正式发布，当前聊天常驻目录是否刷新也必须单独验证。

审计前已有自动更新就绪问题：六端本地 checkout HEAD 高于 `channels/0.1.json` 记录，knowledge / Codex / DSH README 版本也高于渠道，导致 R3 / R6 失败；R1 / R2 / R4 / R5 通过。本轮不修改渠道来掩盖该既有状态，PR 附具体检查结果。运行时修复的可用性不能由 README 或渠道版本表一致性代替证明。

## 修复 PR 与本地证据

| 仓库 | PR | 验证范围 |
| --- | --- | --- |
| remote-dev | [#55](https://github.com/mindie-agent/remote-dev/pull/55) | 认证范围 44 passed / 9 skipped，3.71s；跳过项需要隔离 OpenSSH 服务，不计为通过 |
| Codex | [#93](https://github.com/mindie-agent/mindie-agent-codex/pull/93) | 确切候选 remote-dev 非 editable 安装；目录、认证、输出与回执范围 82 passed / 3 skipped / 5 subtests，10.58s |
| Antigravity | [#6](https://github.com/mindie-agent/mindie-agent-agy/pull/6) | 新认证边界 4 passed，0.44s；连同现有 MCP / knowledge 范围 9 passed，21.16s |
| WorkBuddy | [#5](https://github.com/mindie-agent/mindie-agent-wb/pull/5) | 新认证边界 4 passed，0.53s；连同现有 MCP / knowledge 范围 11 passed，17.28s |

本地环境为原生 Windows / Python 3.13；Coordinator 既有共享认证范围另有 6 passed / 1.02s。五个受影响仓库的 LF 检查与 `git diff --check` 均通过。Codex PR 保留为配套草稿，明确依赖共享组件先合入及正式发布；其余 CI 结果以各 PR 的当前检查记录为准。

remote-dev 候选 `aee4e71aa4e3298b35c2229bc57e5a822caff115` 的 [真实 SSH CI](https://github.com/mindie-agent/remote-dev/actions/runs/42150103199/job/127671164811) 已通过：PowerShell 两组各 4 passed（13.98s / 13.17s），实际 WSL2 为 4 passed（13.20s）。这些用例现在从公开 `remote_auth` 登记，再验证公钥/密码模式、新进程复用、恢复与消费者边界；不代表用户业务机器或原聊天已经重新验证。该 PR 同轮 Linux 3.11/3.12、macOS/Windows 客户端、wheel 与 OpenSSH loopback 检查也通过。

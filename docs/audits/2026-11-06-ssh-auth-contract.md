# SSH 首次认证与宿主契约对齐审计

> 后续按用户要求完成了独立代码审查（`gpt-6-astra`，`reasoning_effort=max`）并将修复扩展至跨宿主任务连续性，最新修复范围与正式交付记录见[任务连续性审计](2026-11-06-task-continuity.md)。本文完整保留首次 SSH 认证修复的根因定位与初始提交验证证据。

问题背景：用户在远端开发对话中已明确提供 SSH 主机地址与登录密码，Agent 却停留在“MindIE SSH 凭据未配置”报错并反复要求用户另行配置凭据。现场截图证实了交互阻塞现象；由于本次排查未获取该对话的原始工具调用日志，下文不对截图中的每一次连接失败强行归因于同一分支，也不将截图中的业务部署指令视为本轮远端执行授权。

## 已复现的根因

底层 `remote_dev.auth.setup_access(password=...)` 早已完整支持密码校验、公钥自动安装、独立子进程免密验证、密码模式回退与共享档案写入；`coordinator` 的 `mindie.hosts` 接口同样支持 `password` 参数并复用该实现。实际断层发生在 Agent 直接调用的公开 MCP 工具定义与宿主适配层：

| 边界层级 | 审计发现的缺口 | 修复措施 |
| --- | --- | --- |
| 共享 MCP Schema 与分发器 | `remote_auth` 仅声明并转发 `password_env`；直接传入 `password` 在分发前即被拒（`caller` / `not_sent`），无法抵达底层实现 | 新增仅限 `action="setup"` 使用的 `password` 入参并转发至 `setup_access`，与 `password_env` 严格互斥 |
| 跨进程环境变量边界 | `password_env` 在已常驻的 MCP 服务进程内读取；Agent 在当前终端临时导出环境变量无法改变既有 MCP 服务进程的环境 | 允许直接传入当次密码完成初始化；保留 `password_env` 入口并明确说明其服务进程作用域 |
| Codex 静态工具目录与测试 | 静态工具目录缺少 `password` 字段，且既有单测显式断言该参数不存在 | 基于同一候选运行时重新生成工具目录；将禁止该参数的旧断言替换为真实密码登记、密钥复用与密码回退验证 |
| 认证失败恢复引导 | 共享错误提示仅引导设置环境变量或由用户手动配置，未提示 Agent 直接使用已知密码初始化 | 更新错误提示引导 Agent 直接调用 `setup` 后继续原任务；针对尚未刷新的旧工具目录保留本地子进程 `stdin` 密码导入路径 |
| Antigravity / WorkBuddy 适配层 | 认证异常被压平为普通错误字符串，丢失安全恢复指引、业务命令是否已发送及公钥安装状态 | 统一复用 `safe_auth_error_details` 保留结构化恢复字段，同时严禁暴露原始 SSH `stderr`、本地路径或敏感凭据引用 |
| 跨平台真实 SSH 验收脚本 | 验收 Worker 直接调用底层 Python SDK 并在自身进程内注入临时环境变量，未能覆盖公开 MCP 工具层缺口 | 将真实 PowerShell / WSL2 验收改为经由 `stdin` JSON 走公开 `remote_auth` 分发器登记，再在新子进程中验证免密复用 |

六款原生宿主插件的工具目录接入方式亦逐一核对完毕：Codex 采用静态工具目录加独立 runtime helper；Claude Code 与 Kimi Code 动态加载共享目录并透传结构化认证错误；DSH 的 `host.mjs` 直接拉起 `remote_dev.mcp.server`；Google Antigravity 动态读取 canonical 目录；Tencent WorkBuddy 动态读取 `wb` 目录。因此后五端随共享组件升级即可自动获得新参数，而 Codex 需同步更新静态目录与锁定的组件依赖。

## 行为契约与安全边界

- **一次提供即可自动建连**：只要用户在当前任务中已提供密码，Agent 即可直接发起首次认证登记；本地尚无档案仅代表首次接入，绝不能据此向用户重复索要同一份连接信息。`remote_auth` 直接复用共享认证模块，不引入聊天文本密码扫描器、第二套凭据存储或冗余 SSH 引导状态机。
- **状态诚实与禁止盲目重放**：首次认证登记成功后才继续执行业务命令；若公钥安装受阻但密码已验证通过，允许在密码模式下继续执行。网络不可达、密码错误与主机指纹冲突必须原样上报，严禁用静默重试掩盖。公钥安装回执未知（`unknown`）与业务命令尚未发送（`not_sent`）作为两项独立事实同时保留；任何已发出但外部结果未知的业务写入严禁自动重放。
- **凭据最小暴露面**：当次密码仅在 `setup` 请求入参中传递，工具返回体、端点档案与认证回执均不回显密码，SSH 子进程命令行亦不拼接明文密码。MCP Schema 中的 `writeOnly` 仅作为敏感参数声明，不对外作“宿主客户端自身聊天日志不留存工具入参”的超范围承诺。

## 验证与交付约束

回归测试覆盖公开 MCP Schema、分发器、Codex 严格参数校验入口及 runtime helper，完整验证密码首次登记、新进程公钥免密验证、密码模式回退、既有档案复用、互斥参数校验与错误状态透传。本地边界单测中的固定认证桩仅用于协议分支校验，不冒充真实 SSH 或 NPU 实机测试；真实 OpenSSH 跨平台验收全部切换至公开 `remote_auth` 入口并单独记录结果。

各修复 PR 严格区分“本地源码单测”、“候选依赖联调”、“CI 真实 OpenSSH 验收”、“正式 GitHub Release 发布”与“已运行宿主加载新版目录”五个阶段。Codex 配套 PR 必须锁定包含新接口的 `remote-dev` 提交，确保静态工具目录绝不先于底层运行时能力合入；正式插件发布须在共享组件正式 Release 之后执行，且已常驻宿主是否刷新工具目录须单独核验。

审计前工作区已存在的渠道基线差异如实保留记录：当时六端本地检出 `HEAD` 及 `knowledge` / `Codex` / `DSH` 的 README 版本高于 `channels/0.1.json` 历史记录（故产品全量模式下 `R3` / `R6` 报差异，而 `R1` / `R2` / `R4` / `R5` 通过）。本轮修复不通过随意篡改 `channels/0.1.json` 掩盖既有状态，而是在各 PR 中如实附上检查输出。

## 初始修复 PR 与实测记录

| 仓库 | PR | 本地测试范围与结果 |
| --- | --- | --- |
| `remote-dev` | [#55](https://github.com/mindie-agent/remote-dev/pull/55) | 认证模块范围 `44 passed / 9 skipped`（`3.71s`；跳过项需独立隔离 OpenSSH 服务，不计入通过数） |
| `mindie-agent-codex` | [#93](https://github.com/mindie-agent/mindie-agent-codex/pull/93) | 非 editable 安装候选 `remote-dev` 后，工具目录、认证、输出与回执范围 `82 passed / 3 skipped / 5 subtests`（`10.58s`） |
| `mindie-agent-agy` | [#6](https://github.com/mindie-agent/mindie-agent-agy/pull/6) | 新增认证边界 `4 passed`（`0.44s`）；连同既有 MCP / `knowledge` 范围共 `9 passed`（`21.16s`） |
| `mindie-agent-wb` | [#5](https://github.com/mindie-agent/mindie-agent-wb/pull/5) | 新增认证边界 `4 passed`（`0.53s`）；连同既有 MCP / `knowledge` 范围共 `11 passed`（`17.28s`） |

本地验证环境为原生 Windows + Python 3.13，另在 `coordinator` 共享认证范围通过 `6 passed`（`1.02s`）；全部 5 个受影响仓库均通过 Unix `LF` 换行检查与 `git diff --check`。

`remote-dev` 候选提交 `aee4e71aa4e3298b35c2229bc57e5a822caff115` 的[跨平台真实 SSH CI](https://github.com/mindie-agent/remote-dev/actions/runs/42150103199/job/127671164811) 全部通过：PowerShell 两组各 `4 passed`（`13.98s` / `13.17s`），真实 WSL2 环境 `4 passed`（`13.20s`），完整覆盖经由公开 `remote_auth` 发起首次密码登记、公钥/密码模式切换、新进程免密复用、异常恢复与消费者边界校验；同轮 Linux Python 3.11/3.12、macOS/Windows 客户端构建、wheel 打包与 OpenSSH loopback 检查亦全部通过（注：上述 CI 验证针对标准 OpenSSH 环境，不替代用户私有业务主机或原对话现场复测）。

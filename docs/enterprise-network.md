# 企业网络下的配置与传输

[English](enterprise-network.en.md) · [返回文档中心](README.md)

## 链路与职责

| 链路 | 执行方 | 网络配置来源 |
| --- | --- | --- |
| 插件注册、源码与知识 Feed 拉取 | 宿主插件管理器、Git | 当前进程的代理、Git 配置与系统证书 |
| Python、组件 wheel 与 PyPI 依赖下载 | 四宿主安装器及更新器调用的 uv | 当前进程代理、系统证书、显式 CA 和包源设置 |
| Gitleaks、DSH Release 下载 | Python 标准库 HTTPS | 系统证书、显式 CA 与当前进程代理 |
| 知识贡献 PR、故障 Issue 上传 | Git 与 gh | 当前授权、gh 登录及服务启动时的网络环境 |
| knowledge 本机 RPC、Kimi 插件 API、DSH 摘要 API | 共享知识客户端与插件 Python 适配器 | 回环地址直接连接 |
| Bench 模型出口与本机 RPC | mindie-bench 网关及 shim | 模型出口读取代理与 `NO_PROXY`，本机 RPC 直接连接 |
| SSH 文件上传、下载及产物同步 | remote-dev | SSH 配置、目标主机及容器；HTTP 代理不参与 SSH 协议 |
| 资源协调、NPU 观测 | coordinator、npu-top | 远端 SSH 与本地 API；远端镜像拉取使用远端 Docker 的网络配置 |

## 修复设计

依据[设计原则](design-principles.md)第 1、8、9、10、14、15 条：

1. **安装与更新复用系统信任库。** 原生启动命令在下载 Python 前启用 uv 系统证书；内部安装器使用兼容旧版 uv 的环境变量设置默认值，保留用户的 `UV_SYSTEM_CERTS`、`UV_NATIVE_TLS` 选择和显式 CA。`SSL_CERT_FILE`、`SSL_CERT_DIR` 和包源配置继续生效。Kimi 的首次安装与更新统一使用 uv，移除依赖 ensurepip 版本的另一套安装路径。
2. **后台知识服务继承网络环境。** 在共享 `knowledge` 服务上下文中声明代理、CA、包源及 gh 配置路径变量，沿用现有一次性启动上下文。四个插件不各自维护网络状态机。安装配置只保存变量名，值由实际唤醒服务的进程提供。
3. **故障上报服务使用已有环境文件入口。** 启用服务时，自动将必要的代理、CA 和 gh 配置路径写入该服务目录下的私有环境文件；不复制 API Token。显式指定的环境文件优先。网络设置变化时更新现有服务，上传授权和已有回执保持原样。Kimi 的定时更新复用共享组件的同一环境文件实现，当前调用显式提供的变量优先。
4. **回环请求不经过企业代理。** knowledge 本机 RPC、Kimi 插件注册、DSH 摘要和 Bench 的 SSH、知识与重放 RPC 使用标准库 `ProxyHandler({})`，不依赖用户维护 `NO_PROXY`。
5. **外部写入保持现有结果语义。** 不重试结果不确定的 Git push、PR、Issue 或模型请求。证书错误保留原始失败；证书库来自操作系统或用户指定的 CA，不自动信任网络返回的证书。
6. **Bench 模型出口遵循企业 HTTP 代理。** 父进程网关读取 `HTTPS_PROXY` / `ALL_PROXY` 和 `NO_PROXY`，复用标准库 HTTP CONNECT 隧道与系统 TLS 校验；代理认证只发送给代理，不进入模型请求或日志。本机 HTTP relay 直接连接。保留原有流式传输、计量、超时与无自动重试语义。当前企业代理为 `http://` 类型；不支持的代理协议在发送模型请求前明确报错，不降级为直连。

变更只落在对应组件和插件仓；主仓维护本设计和入口文档。后台更新继续复用既有准备、空闲切换和超时预算。

## 企业网络维护版本

[`knowledge 0.13.4`](https://github.com/mindie-agent/knowledge/releases/tag/v0.13.4) 将安装器的 uv 系统证书默认策略带到独立组件更新构建器，并保留显式 TLS、CA 和代理设置。[`Codex 0.1.3`](https://github.com/mindie-agent/mindie-agent-codex/releases/tag/v0.1.3) 与 [`Claude Code 0.1.3`](https://github.com/mindie-agent/mindie-agent-cc/releases/tag/v0.1.3) 同时修复候选发布契约校验清空 Git 系统/用户配置的问题，使企业代理、CA 与 Windows `schannel` 配置继续生效。

Windows 企业网络下已验证 Codex `0.164.0-alpha.11.1` 的正式 `0.1.2` MCP 进程通过常规后台维护更新到 `0.1.3`，实际运行组件为 `knowledge 0.13.4 / remote-dev 0.10.6 / diagnostics 0.5.2`。本次从更新检查到激活约 `44.9s`，其中绑定切换约 `55ms`；原 MCP 进程持续处理前台工具发现请求。该记录是单机软件更新验收，包含前置环境构建，不将完整流程表述为亚秒级切换。

[`Codex 0.1.4`](https://github.com/mindie-agent/mindie-agent-codex/releases/tag/v0.1.4) 另修复 Desktop `0.164` 将 Hook 信任拆为命令与内容哈希两个字段时的继承比较。更新器只迁移已有批准记录；显式停用或任一哈希变化继续保留用户选择。正式修复版更新器已在同一 Windows 企业网络完成 `0.1.3 → 0.1.4` 全链路升级，五个原生 Hook 的已有批准全部继承成功。

## 正常安装与工作区引导

主仓安装入口、四个插件的自动安装协议和首次配置入口都执行同一顺序：检查并复用 GitHub 认证，完成插件安装，介绍已有用户须知，提供 `vllm-ascend-workspace` 的创建、复用或继续当前目录选择，并在安装汇报末尾询问用户是否愿意为主仓 `mindie-agent/mindie-agent` 点亮 Star ⭐（仅在用户明确同意后执行 `gh api --hostname github.com --silent -X PUT /user/starred/mindie-agent/mindie-agent`，严禁未经同意静默执行）。手动安装文档明确以 `/mindie-agent 帮我完成首次配置` 收尾；后台启动和普通开发任务不重复询问。

- 工作区安装使用 [vllm-ascend-workspace](https://github.com/mindie-agent/vllm-ascend-workspace) 当前检出的 `AGENTS.md` 与 `repo_init.py`，复用已有 `workspace.json` 的 Fork 选择。工作区独立安装也先完成认证；从插件引导进入时复用同一次验证。
- 用户同意创建或复用工作区，即在同一流程中将所选绝对路径添加到当前宿主的原生项目/工作区入口，不再另问一次是否登记。初始化选择独立保留，用户暂缓源码下载也可以先登记目录。
- 路径登记由插件引导调用宿主原生工具、接口或 UI 完成；复用同一路径的已有记录。CLI 按宿主支持的工作目录启动方式进入，不维护额外的 MindIE 项目表，不直接修改宿主私有数据库。
- 核对宿主返回或项目列表中的路径，再报告登记完成。只有目录创建成功、子 shell 切换目录成功或增加文件访问范围，均不能代替宿主登记成功。原生入口需要用户操作时，明确给出剩余的那一步。
- GitHub 认证、工作区登记和知识贡献授权分别沿用各自已有设置；安装工作区不扩大知识贡献范围。

## GitHub 登录引导

安装、首次配置或修复认证时，由 `/mindie-agent` 按下面的流程处理。登录选择属于 Agent 引导；凭据保存与使用复用 `gh`，不新增认证服务或 Token 配置格式。

1. **先复用已有认证。** 安装缺失的 `gh`，执行 `gh api --hostname github.com user --jq .login`。成功且账号符合当前配置时直接继续，不重复询问登录方式。`gh auth status` 用于诊断凭据来源；其他已保存账号失效不应阻止当前有效账号。
2. **需要登录时选择方式。** 用户已说明处于企业网络，或检测到代理/自定义 CA 配置、浏览器授权受阻时，优先推荐 Token；普通网络默认使用浏览器登录，也允许用户选择 Token。代理和 CA 仅是选择建议的依据，不代表浏览器一定不可用。连接超时、代理 407 和证书错误先按网络问题处理，不能冒充 Token 失效。
3. **选 Token 后只补齐缺失的一步。** 已有 Token 就直接使用；没有则打开 [GitHub Token 创建页](https://github.com/settings/tokens/new?scopes=repo%2Cread%3Aorg%2Cgist&description=MindIE%20Agent)，引导完成创建后回到终端。普通持久登录使用 `gh` 支持的 classic PAT（`repo`、`read:org`、`gist`）；有效期由用户或组织策略决定。组织要求 SSO 时完成对应授权。受组织策略约束的 fine-grained Token 按实际目标仓库配置权限，不要求用户换成不被允许的类型。
4. **用原生提示接收并保存。** 在用户可操作的终端运行 `gh auth login --hostname github.com --git-protocol https`，选择 `Paste an authentication token`，由用户在隐藏输入提示中粘贴。若用户已提供私有 Token 文件路径，Agent 直接通过标准输入执行 `gh auth login --hostname github.com --git-protocol https --with-token`，无需再次输入。Token 不进入对话、命令行参数、仓库、MindIE 配置或日志；保存由 `gh` 管理，不添加 `--insecure-storage`。环境中的旧 Token 会覆盖已保存登录，修复时需同时处理实际调用进程的旧变量。
5. **验证后继续原任务。** 再次读取账号，确保 `git` 所在目录已在 `PATH` 中（或通过 `MINDIE_GIT_BIN` 显式指定），在 Windows 下先清除系统级 `etc/gitconfig` 可能预置的无作用域 `helper-selector`（如 `git config --system --unset-all credential.helper` 及设置 `GCM_INTERACTIVE=never`，避免 `GIT_TERMINAL_PROMPT=0` 下仍弹出 GUI 凭据选择窗阻塞进程；若企业代理下 `schannel` 报 `CRYPT_E_NO_REVOCATION_CHECK`，配置 `http.sslBackend=schannel` 与 `http.schannelCheckRevoke=false` 并保持 `http.sslVerify=true`），再执行 `gh auth setup-git --hostname github.com`，并只读检查本次操作涉及的仓库。后续源码/知识同步、Git push、PR 和 Issue 操作复用同一 `gh` 身份；登录不改变已有贡献选择与项目范围。401 处理凭据失效，403/404 结合目标仓库、权限和 SSO 定位，不循环要求用户重登，也不创建测试 PR/Issue 来验证登录。

用户提供文件时，以下命令中的路径变量由 Agent 使用实际路径填入；文件内容不打印：

```powershell
Get-Content -Raw -LiteralPath $TokenFile | gh auth login --hostname github.com --git-protocol https --with-token
if ($LASTEXITCODE -ne 0) { throw "GitHub token login failed" }
```

```sh
gh auth login --hostname github.com --git-protocol https --with-token < "$TOKEN_FILE"
```

**后续复用范围：** `gh` 保存的登录可供同一用户、同一 `GH_CONFIG_DIR` 下的新进程使用。验证持久登录时，在不带 `GH_TOKEN` / `GITHUB_TOKEN` 的子进程中再次读取账号，避免环境变量掩盖未保存的登录；后台服务沿用已有网络环境与 `gh` 配置路径传递。若用户选择仅通过 `GH_TOKEN` 使用凭据（fine-grained PAT 优先采用此方式），由其现有凭据注入机制供应实际调用进程。知识服务已有一次性环境传递；诊断服务自动生成的网络文件不保存 Token，独立服务须使用已有的显式私有环境文件入口或 `gh` 保存的登录。仅当前终端成功不能报告为重启后的后台认证已就绪。

## 企业网络实测

2026-10-20，在启用认证 HTTP 代理的 Windows 环境中：

- GitHub API、源码克隆、Release 附件重定向和 PyPI 均可访问。
- Git 命令启用证书校验后，代码仓与两个领域知识仓克隆成功。
- uv 默认下载 `mindie-diagnostics 0.4.3` 的 GitHub Release wheel 报 `invalid peer certificate: UnknownIssuer`；相同请求使用系统证书成功。
- 同一环境的 PyPI 请求成功，因此只测试 PyPI 不足以验证首次安装与更新。
- 使用系统证书后，真实下载 Python 3.13.16、组件 Release wheel，并完成 Codex 锁定运行时安装（166 个包）。
- 本机 Git 原有 `http.sslVerify=false`。验证现有企业代理在开启校验时正常工作后，已将该设置恢复为 `true`，默认配置下的 GitHub 访问复测成功。
- 修复分支的 Git push 与 GitHub PR 创建成功，覆盖了实际上传链路。
- 本地真实 HTTP/TLS 测试覆盖带认证 CONNECT、显式 CA、`NO_PROXY`、流式计量，以及错误代理下的回环请求。
- 本地企业网络无法直连 A2/A3，属于已确认的环境边界。该环境不执行 A2/A3 实机测试，常规 CI 验证本地组件与进程、网络协议契约。

验证覆盖真实 Release 下载、私有环境文件的跨进程消费、既有服务启动上下文、带代理时的本机 HTTP 请求和失败传播。网络凭据不进入测试输出、公共日志或 PR 正文。

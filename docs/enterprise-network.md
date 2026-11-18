# 企业网络下的配置与传输

[English](enterprise-network.en.md) · [返回文档中心](README.md)

## 链路与职责

| 链路 | 执行方 | 网络配置来源 |
| --- | --- | --- |
| 插件注册、源码与知识 Feed 拉取 | 宿主插件管理器、Git | 当前进程的代理、Git 配置与系统证书 |
| Python、组件 wheel 与 PyPI 依赖下载 | 各原生宿主安装器及更新器调用的 `uv` | 当前进程代理、系统证书、显式 CA 与包源设置 |
| Gitleaks、DSH Release 下载 | Python 标准库 HTTPS | 系统证书、显式 CA 与当前进程代理 |
| 知识贡献 PR、故障 Issue 上传 | Git 与 `gh` | 当前授权、`gh` 登录态及服务启动时的网络环境 |
| `knowledge` 本机 RPC、Kimi 插件 API、DSH 摘要 API | 共享知识客户端与插件 Python 适配器 | 本地回环地址直连 |
| Bench 模型出口与本机 RPC | `mindie-bench` 网关及 shim | 模型出口读取代理与 `NO_PROXY`；本机 RPC 直接连接 |
| SSH 文件上传、下载及产物同步 | `remote-dev` | SSH 配置、目标主机及容器；HTTP 代理不参与 SSH 协议 |
| 资源协调、NPU 观测 | `coordinator`、`npu-top` | 远端 SSH 与本地 API；远端镜像拉取遵循远端 Docker 的网络配置 |

## 修复设计

依据[工程设计原则](design-principles.md)第 1、8、9、10、14、15 条，企业网络下的安装、更新与外发传输遵循以下六项约束：

1. **安装与更新复用系统信任库。** 原生启动命令在 `uv` 下载 Python 前默认启用系统证书；内部安装器通过兼容旧版 `uv` 的环境变量设置默认值，并保留用户显式配置的 `UV_SYSTEM_CERTS`、`UV_NATIVE_TLS`、自定义 CA（`SSL_CERT_FILE`、`SSL_CERT_DIR`）与包源设置。Kimi 的首次安装与后台更新统一收敛到 `uv`，移除原先依赖 `ensurepip` 的第二套安装路径。Google Antigravity 与 Tencent WorkBuddy 沿用各自仓库已有的 `plugins/mindie-agent/scripts/setup.py`：在引导运行时前调用同目录的 `paths.apply_enterprise_transport_env`，通过 `setdefault` 写入 `UV_SYSTEM_CERTS`、`UV_NATIVE_TLS` 与 `GCM_INTERACTIVE=never`，并在保留调用方已有 `GIT_CONFIG_COUNT` 条目的前提下增量追加缺失的 Windows Git `core.longpaths` / `core.autocrlf` 及 GitHub 凭据设置，不另设第二条安装或传输路径。
2. **后台知识服务继承网络环境。** 在共享 `knowledge` 服务上下文中统一声明代理、CA、包源及 `gh` 配置路径变量，直接复用现有的一次性启动上下文传递机制；各原生宿主插件不各自维护独立的网络状态机。安装配置仅记录变量名，实际变量值由唤醒后台服务的进程按需传入。
3. **故障上报服务复用既有环境文件入口。** 启用诊断服务时，系统自动将所需的代理、CA 与 `gh` 配置路径写入该服务目录下的私有环境文件（绝不复制 API Token），且显式指定的环境文件始终优先。网络配置变更时原地刷新现有服务环境，保持上传授权与历史回执不变。Kimi 的定时更新复用共享组件的同一环境文件机制，同样以当前调用显式传入的变量为准。
4. **本地回环请求绕过企业代理。** `knowledge` 本机 RPC、Kimi 插件注册、DSH 摘要以及 `mindie-bench` 的 SSH、知识与重放 RPC 均显式使用标准库 `ProxyHandler({})` 直连，不依赖用户手工维护 `NO_PROXY`。
5. **外部写入严格保持状态诚实性。** 对于结果不确定的 Git push、PR、Issue 或模型请求，严禁盲目自动重试。TLS 证书校验失败时保留原始错误；信任锚仅来自操作系统证书库或用户显式指定的 CA，绝不自动信任对端在握手期间返回的未知证书。
6. **Bench 模型出口遵循企业 HTTP 代理。** 父进程网关读取 `HTTPS_PROXY` / `ALL_PROXY` 与 `NO_PROXY`，复用标准库 HTTP `CONNECT` 隧道与系统 TLS 校验；代理认证凭据仅发送给代理服务器，绝不混入下游模型请求或写入日志。本机 HTTP relay 保持直连，同时完整保留原有的流式传输、Token 计量、超时控制与无自动重试语义。当前企业代理支持 `http://` 协议；遇到不支持的代理协议时在发送模型请求前立即报错，绝不静默降级为直连。

运行时变更仅落在对应的共享组件与宿主插件仓库；本主仓负责维护架构设计与入口文档。后台更新继续沿用既有的离线准备、空闲原子切换与超时预算机制。

## 企业网络维护版本

[`knowledge 0.13.4`](https://github.com/mindie-agent/knowledge/releases/tag/v0.13.4) 将安装器的 `uv` 系统证书默认策略同步至独立组件更新构建器，同时保留显式 TLS、CA 与代理配置。[`Codex 0.1.3`](https://github.com/mindie-agent/mindie-agent-codex/releases/tag/v0.1.3) 与 [`Claude Code 0.1.3`](https://github.com/mindie-agent/mindie-agent-cc/releases/tag/v0.1.3) 同步修复了候选发布契约校验阶段清空系统级与用户级 Git 配置的问题，确保企业代理、自定义 CA 与 Windows `schannel` 证书信任持续生效。

在 Windows 企业网络实测中，Codex `0.164.0-alpha.11.1` 下的正式 `0.1.2` MCP 进程通过常规后台维护平稳升级至 `0.1.3`，实际加载组件为 `knowledge 0.13.4 / remote-dev 0.10.6 / diagnostics 0.5.2`。从触发更新检查到完成激活全程约 `44.9s`（其中隔离环境构建占主要耗时，最终绑定原子切换约 `55ms`），期间原 MCP 进程持续正常响应前台工具发现请求。该记录属于包含前置环境构建的单机软件更新验收，不将完整端到端更新流程夸大为亚秒级切换。

[`Codex 0.1.4`](https://github.com/mindie-agent/mindie-agent-codex/releases/tag/v0.1.4) 进一步适配了 Desktop `0.164` 将 Hook 信任拆分为命令哈希与内容哈希两个字段后的继承比对逻辑：更新器仅迁移既有批准记录，用户显式停用或任一哈希发生变更时均严格保留原有安全边界。正式修复版更新器已在同一 Windows 企业网络环境中完成 `0.1.3 → 0.1.4` 全链路升级，五个原生 Hook 的既有批准记录全部平滑继承。

## 正常安装与工作区引导

主仓安装入口、各原生宿主插件的自动安装协议与首次配置入口均遵循统一的引导顺序：先检查并复用 GitHub 认证，完成插件安装与完整性校验，随后在第 5 步通过 `setup.py sharing --status` 读取当前授权状态，并立即调用宿主的**原生交互式提问工具**（Antigravity `ask_question`、Claude Code / WorkBuddy / Kimi `AskUserQuestion`、Codex `request_user_input`、DSH 原生提问工具或标准选择卡片）向用户集中确认三项配置：
1. 选择新建 `vllm-ascend-workspace`、复用已有目录或继续留在当前工作目录；
2. 是否开启社区知识共享与自动故障上报（通过 `setup.py sharing --enable --project-root "$WORKSPACE_ROOT"` 或 `setup.py sharing --disable` 统一落盘至 `mindie-community.json`、`mindie-consent.json` 与 `diagnostics.json`）；
3. 是否顺手为 `mindie-agent/mindie-agent` 点亮一颗 GitHub Star ⭐（仅在用户明确选择同意后执行 `gh api --hostname github.com --silent -X PUT /user/starred/mindie-agent/mindie-agent`，严禁未经同意静默执行）。

手动安装文档以 `setup.py sharing` 引导完成首次配置收尾；后台服务唤醒与日常研发任务绝不重复弹出首次配置询问。

- **工作区初始化与认证复用**：工作区安装通过 [vllm-ascend-workspace](https://github.com/mindie-agent/vllm-ascend-workspace) 当前检出的 `AGENTS.md` 与 `repo_init.py` 执行，自动沿用 `workspace.json` 中已保存的 Fork 选择。独立运行工作区初始化时同样先完成认证检查；从插件引导进入时则直接复用同一次认证结果。
- **一步完成原生项目登记**：用户确认创建或复用工作区后，引导流程在同一轮内直接将该绝对路径登记到当前宿主的原生项目/工作区列表中，不再二次追问是否登记。目录初始化选项独立保存，即使暂缓下载源码也可先行完成工作区路径登记。
- **不维护私有项目注册表**：路径登记统一调用宿主原生工具、接口或 UI 完成，并优先复用同一路径的既有记录；CLI 宿主按其支持的工作目录启动方式进入，既不维护额外的 MindIE 项目表，也不直接篡改宿主的私有数据库。
- **登记结果以宿主回读为准**：必须核对宿主接口返回值或项目列表中的实际路径后，方可报告工作区登记完成。仅创建目录、在子 Shell 中 `cd` 切换目录或扩大文件访问沙箱范围，均不能视作宿主原生登记成功；若原生入口必须由用户手动确认最后一步，则明确告知该具体操作。
- **权限边界相互独立**：GitHub 身份认证、工作区目录登记与社区知识贡献授权各自独立保存；初始化开发工作区绝不隐式扩大知识贡献授权范围。

## GitHub 连接故障定位

浏览器能够打开 `github.com`，并不代表终端安装进程、`gh` CLI 或后台计划任务也能连通 `api.github.com`——浏览器往往持有独立的代理扩展、PAC 自动配置脚本、VPN 分流或私有证书信任库。排障时必须在失败进程实际所处的网络上下文中逐层核查，不能用另一台机器或浏览器的连通性替代故障现场。

| 已观测现象 | 定位边界与后续处置 |
| --- | --- |
| DNS 解析失败 | 检查当前进程与所选代理服务器的 DNS 解析链路，完整保留原始报错 |
| 已解析 IP，但 TCP `443` 连接超时 | 排查实际生效的出站代理、`NO_PROXY`、VPN、路由与防火墙；此时尚未收到 GitHub 服务端响应，不应要求用户重新登录 |
| 代理返回 `407` 或拒绝 `CONNECT` | 检查企业代理认证凭据与目标域名白名单；更换 GitHub Token 无法解决企业代理鉴权失败 |
| TLS 握手或证书校验失败 | 核对当前客户端使用的系统信任库或显式 CA 配置，保持 TLS 校验开启 |
| GitHub 返回 `401` | 核对当前实际生效的凭据来源、绑定账号及 Token 有效性 |
| GitHub 返回 `403` / `404` | 结合目标仓库访问权限、组织 SSO 授权与 API 限流响应头定位根因，避免盲目循环重登 |

只读连通性复核应依次覆盖 **GitHub REST API**、**目标仓库 Git 读取**与 **Release 附件重定向下载**三条链路；单次网页访问成功或 PyPI 拉包成功均不能替代完整链路验证。诊断代理与 CA 配置时仅输出配置是否存在、作用范围及失败阶段，严禁打印代理密码、Token、认证请求头或完整环境变量快照。若确认浏览器依赖 PAC 脚本而终端缺少可用代理，应按企业 IT 提供的标准代理地址配置终端环境，绝不盲目猜测代理端口或擅自修改操作系统全局网络设置。

在组装 Git 进程环境时，必须先保留调用方 `GIT_CONFIG_COUNT` 中已有的代理、CA 与 TLS 配置，再增量追加 MindIE 自有的凭据助手与 hooks 参数。后台任务沿用一次性服务上下文或私有网络环境文件，仅投影 Git HTTP 传输层配置，绝不透传凭据助手、认证头或任意全局 Git 选项；当调用方撤除网络代理设置后，后台服务消费已保存上下文时也会同步清理陈旧的代理与进程级 Git 传输配置。

## GitHub 登录引导

在首次安装、初始化配置或修复凭据时，安装引导流程统一遵循以下五步协议。登录方式选择由 Agent 交互引导，底层凭据存储与调用则完全复用官方 `gh` CLI，不另建私有认证服务或自定义 Token 存储格式：

1. **优先复用既有有效登录。** 若环境缺失 `gh` 则先完成安装，随后执行 `gh api --hostname github.com user --jq .login`。只要调用成功且返回账号符合当前任务预期，即直接继续后续步骤，不再重复询问登录方式。`gh auth status` 仅用于辅助诊断凭据来源；其他非活跃保存账号的过期状态不应阻断当前有效账号。
2. **需要登录时按网络环境推荐方式。** 若用户已说明身处企业内网、检测到代理或自定义 CA 配置，或浏览器 OAuth 跳转受阻，优先推荐使用 Token 登录；普通直连网络默认提供浏览器一键登录，同时保留 Token 选项。检测到代理或自定义 CA 仅作为推荐依据，不预设浏览器登录必然失败。遇到连接超时、代理 `407` 或 TLS 证书报错时，必须先按传输层故障排障，严禁误判为 Token 失效。
3. **选择 Token 登录时仅补齐缺失环节。** 用户已有可用 Token 时直接进入下一步；尚未创建时，引导打开预填权限的 [GitHub Token 创建页](https://github.com/settings/tokens/new?scopes=repo%2Cread%3Aorg%2Cgist&description=MindIE%20Agent)，创建完成后回到终端继续。常规持久化登录推荐使用 `gh` 原生支持的 classic PAT（勾选 `repo`、`read:org`、`gist` 权限），有效期遵循用户或组织安全策略；若组织启用了 SAML SSO，同步提醒完成 SSO 授权。若组织策略强制要求使用 fine-grained PAT，则按实际访问的目标仓库配置最小必要权限，不要求用户改用组织禁止的 Token 类型。
4. **通过原生安全输入接收并保存凭据。** 在用户可交互的终端执行 `gh auth login --hostname github.com --git-protocol https`，选择 `Paste an authentication token`，由用户在隐藏回显提示符下粘贴 Token；若用户已准备好私有 Token 文件路径，Agent 直接通过标准输入重定向执行 `gh auth login --hostname github.com --git-protocol https --with-token`，免去二次粘贴。Token 明文严禁出现在聊天对话、命令行参数、代码仓库、MindIE 配置文件或任何日志中；凭据落盘交由 `gh` 系统钥匙串管理，不附加 `--insecure-storage`。由于环境变量中的陈旧 `GH_TOKEN` / `GITHUB_TOKEN` 会覆盖 `gh` 已保存的钥匙串登录，修复认证时必须同步核查并清理当前调用进程中的残留环境变量。
5. **只读核验通过后无缝续跑原任务。** 登录完成后重新读取账号信息，确保 `git` 所在目录已加入 `PATH`（或通过 `MINDIE_GIT_BIN` 显式指定）。为避免篡改用户全局 `~/.gitconfig` 或系统级 `etc/gitconfig`，所有 Git 网络操作统一通过进程级 `GIT_CONFIG_COUNT`（或 `git -c`）注入 `credential.helper=`（先清空 Windows `etc/gitconfig` 可能预置的多值 `manager` / `helper-selector`，规避 GCM 2 秒自动探测与 GUI 弹窗阻塞）、`credential.https://github.com.helper=!gh auth git-credential`、`credential.interactive=never`、`core.autocrlf=false` 与 `core.longpaths=true`，并同步设置 `GCM_INTERACTIVE=never` 与 `GIT_TERMINAL_PROMPT=0`（若企业代理环境下 Windows `schannel` 报 `CRYPT_E_NO_REVOCATION_CHECK`，同样通过进程级 `GIT_CONFIG_COUNT` 追加 `http.sslBackend=schannel` 与 `http.schannelCheckRevoke=false`，并始终保持 `http.sslVerify=true`）。随后对当前任务涉及的目标仓库执行只读访问核验；后续源码与知识库同步、Git push、PR 及 Issue 操作统一复用该 `gh` 身份，登录过程本身不改动既有的知识共享授权与项目范围。若遇 `401` 按凭据失效处理，若遇 `403` / `404` 则结合仓库权限与组织 SSO 排查，绝不要求用户死循环重登，也绝不通过创建测试 PR 或测试 Issue 来验证登录态。

当用户提供私有 Token 文件路径时，Agent 将实际路径绑定至文件变量并通过标准输入传入，全程不回显文件内容：

```powershell
Get-Content -Raw -LiteralPath $TokenFile | gh auth login --hostname github.com --git-protocol https --with-token
if ($LASTEXITCODE -ne 0) { throw "GitHub token login failed" }
```

```sh
gh auth login --hostname github.com --git-protocol https --with-token < "$TOKEN_FILE"
```

**跨进程与后台服务复用边界：** `gh` 持久化保存的登录态可供同一操作系统用户、同一 `GH_CONFIG_DIR` 下的后续进程直接复用。验证持久化登录是否真正落盘时，必须在剥离了 `GH_TOKEN` / `GITHUB_TOKEN` 的干净子进程中重新查询账号，防止当前终端的临时环境变量掩盖未保存的登录态。后台服务沿用既有的网络配置与 `gh` 配置目录传递机制；若用户选择仅通过 `GH_TOKEN` 环境变量注入凭据（fine-grained PAT 优先推荐此方式），则由用户现有的凭据注入机制直接向实际调用进程供值。`knowledge` 服务本身具备一次性启动上下文传递能力；`diagnostics` 自动生成的网络环境文件不保存任何 Token，独立后台服务须依赖显式配置的私有环境文件入口或 `gh` 已持久化的钥匙串登录。仅凭当前前台终端调用成功，绝不能谎报为重启后的后台服务认证已就绪。

## 企业网络实测

2026-10-20，在启用带认证企业 HTTP 代理的原生 Windows 环境中完成端到端实测验证：

- GitHub REST API、源码仓库克隆、GitHub Release 附件重定向下载与 PyPI 索引均可正常访问。
- 在开启 Git TLS 证书校验的前提下，主代码仓与两个领域知识语料仓均克隆成功。
- `uv` 在默认内置根证书下下载 `mindie-diagnostics 0.4.3` 的 GitHub Release wheel 时触发 `invalid peer certificate: UnknownIssuer`；启用系统证书库后同一请求顺利通过。
- 同一环境下访问 PyPI 默认即成功，证实单靠 PyPI 连通性探测无法暴露首次安装与组件 Release 下载阶段的证书问题。
- 启用系统证书库后，成功完成 Python `3.13.16` 解释器与组件 Release wheel 的真实下载，并顺利装齐 Codex 锁定运行时环境（共 166 个依赖包）。
- 测试机全局 Git 原本残留 `http.sslVerify=false`；在确认当前企业代理开启完整证书校验可正常工作后，已将该配置恢复为 `true`，并在默认配置下复测 GitHub 读写通过。
- 修复分支的 `git push` 与 GitHub PR 创建均一次成功，完整验证了真实外发写入链路。
- 本地真实 HTTP/TLS 集成测试覆盖了带认证 `CONNECT` 隧道、显式自定义 CA、`NO_PROXY` 分流、流式 Token 计量以及配置错误代理时的本地回环直连保障。
- 该企业办公网与实验室常驻 A2/A3 集群物理网络隔离，属于已知环境边界：办公网内仅执行本地组件、跨进程与网络协议契约验证，不直连 A2/A3 跑真机集成测试。

整套实测覆盖了真实 GitHub Release 资产下载、私有环境文件跨进程消费、既有后台服务启动上下文传递、挂代理状态下的本地回环直连与真实错误传播；全流程确保代理密码与认证凭据零泄露至测试输出、公共日志或 PR 正文。

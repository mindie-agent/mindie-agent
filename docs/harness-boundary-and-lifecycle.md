# 宿主边界与任务生命周期（Harness Boundary & Lifecycle）

[English](harness-boundary-and-lifecycle.en.md) · [返回文档中心](README.md)

本文说明 MindIE Agent 各宿主插件（Claude Code、Codex、Kimi Code、DeepSeek Harness、Google Antigravity、Tencent WorkBuddy、OpenCode）与底层共享组件之间的职责划分，以及任务身份识别、用户授权、长任务执行与本地数据恢复的生命周期规则。

- 遵循准则：[工程设计原则与演进准则](design-principles.md) · [系统架构与模块分工](architecture.md)
- 版本与实测记录：[版本发布记录](README.md#版本记录与路线图)

---

## 1. 宿主插件与共享组件如何分工？

MindIE Agent 不另建一套封闭的“大一统对话平台”，而是直接融入开发者现有的宿主 CLI。各模块各司其职：

| 层级 / 模块 | 负责什么 | 不做什么 |
| --- | --- | --- |
| **宿主原生插件管理器** | 插件包的下载、安装与已安装版本记录 | 不代替 MindIE 做跨宿主兼容性筛选 |
| **宿主插件薄适配层**（`mindie-agent-cc` / `-codex` / `-kimi` / `-dsh` / `-agy` / `-wb` / `-oc`） | 宿主协议清单、生命周期 Hook 转发、可信 Transcript 脱敏提取、宿主原生小模型桥接及锁定依赖（`uv.lock`） | 不各自复制维护进程守护、MCP 网关或更新状态机 |
| **共享宿主底座**（`harness` / `mindie-harness`） | 跨平台无窗子进程与嵌套 Win32 Job 监管、确定性冷启动 Seed（`mindie-harness-seed.pyz`）、`Active + Rollback`（`<= 2`）`.inuse` 租约原子切换、长驻并发 MCP 网关（`P2.7` 零绑定确定性直通 vs. `P2.1` `knowledge_*` 准入）以及单状态源 `ExperimentLedger` `rsi` 优化闭环 | 不混入特定宿主的私有 UI/Transcript 解析逻辑，也不在只读检查时凭空创建空 SQLite 库 |
| **共享知识引擎**（`knowledge`） | 纯知识能力：管理授权与增量游标、执行确定性隐私脱敏、协调分块目录生成、提供基于 `TechnicalTokenizerV1` 的 ReMe 与 `L1–L4` 检索、处理 PR 发布回执与故障恢复 | 不直接耦合特定宿主的私有目录结构，也不靠猜测目录或时间戳来认领任务 |
| **远端开发与诊断组件**（`remote-dev` / `diagnostics`） | 提供 SSH 远端文件读写/后台长作业执行、有界本地诊断日志，以及受统一贡献开关控制的自动故障上报 | SSH 远端操作与本地日志不依赖贡献开关；公开故障上报严格受该开关约束，且绝不截断用户的远端作业输出 |

日常开发中的两类能力边界清晰分离：
- **手动唤醒知识飞轮（`/mindie-agent`）**：需要检索昇腾领域知识、复用历史排障经验或加载 Skill 引导时，在当前会话显式输入一次 `/mindie-agent <问题描述>`（Codex 亦支持 `$mindie-agent`；DSH 使用原生 `/mindie-agent` 入口）。启用状态仅在当前会话（Session）后续轮次内延续直至显式停用——安装完成、开启贡献授权、工具发现或话题关键词匹配均不替代手动唤醒，新建会话、分支会话（Fork）与子代理（Subagent）也不会隐式继承启用状态。
- **确定性工程工具默认就绪（零前置会话绑定门禁）**：已安装配置的 `remote-dev`、`coordinator`（含环境拓扑探测/租约及基于 `execution_id` 句柄的任务编排）、`profiler` 采集解析、`sim` 性能建模、`debugger` 负载调试，以及 `diagnostics` 本地诊断与状态查询均通过标准原生 MCP 直接暴露并随时可用——**既无需输入 `/mindie-agent`，也不强绑宿主私有 `_meta`、`PreToolUse` Hook Nonce 或 `context_file`**（主对话、子代理 Subagent、定时 Automation 及无本地目录的纯集群运维调用均直接放行；物理 NPU/端口互斥由远端 `HostQueue` `lease_id` + `fence_token` 保障，`npu-top` 作为面向开发者的监控看板独立运行）。

划分两类能力的唯一标准在于**是否消费或沉淀知识与经验上下文**：直接读取硬件规格、解析实测 Trace、运行机理仿真或查询本地状态属于默认开放的确定性工具；而检索注入 `L1–L4` 知识条目、精读引用、投票反馈、经验提炼、语料同步以及后台 `Stop` 对话采集（即便底层采用确定性算法）均属于必须手动唤醒的知识飞轮。确定性状态查询仅如实返回客观运行状态，绝不夹带知识引导或贡献提示。

在未手动调用 `/mindie-agent` 的普通聊天中，默认 MCP 工具发现列表彻底剔除 `knowledge` 工具名称、描述与参数 Schema，也不注入知识 Skill、飞轮指令或“尚未启用”的打扰提示（单靠调用时报错拦截不足以满足零打扰边界，默认工具目录本身即不包含知识接口）。即便同一机器上的另一个会话启用了 `/mindie-agent`，运行时仍会在每次执行前独立校验当前会话的授权记录，绝不跨会话泄露共享知识目录（详见 [Codex 0.1.8 原生验收记录](releases/codex-0.1.8-native-acceptance.json)）。

---

## 2. 任务身份、用户授权与采集范围

### 2.1 授权一次配置，跨升级持久有效
- **持久化用户设置**：是否开启经验贡献、目标公开知识库、GitHub 账号与授权项目范围都保存在用户的持久化配置中，与插件代码版本解耦。
- **重装或升级不打扰**：开启新任务、重启终端或插件后台升级后，自动沿用已有授权设置。如果用户之前选择了“停用 / 暂不开启”，升级后依然保持停用，绝不会在后台静默开启上传。
- **增量修改**：首次引导只询问确实缺失的配置项；后续随时可以增量修改项目范围或开关状态，无需重装插件或手改底层 JSON。

### 2.2 精确的任务身份与采集时间边界
- **不靠猜测认领会话**：每个原生任务或子任务（Fork）的材料归属均来自宿主提供的可信会话 ID 与 Transcript 头部元数据，绝不靠“最新修改的文件”“相同的当前目录（`cwd`）”或“相似的提问内容”去瞎猜。
- **清晰的采集起点**：系统只采集当前会话已手动调用 `/mindie-agent` 激活后、用户开启贡献授权且在已授权项目范围内产生的新增对话（以会话创建时间与手动激活时间中的较晚者 `max(created_at, activated_at)` 为起点）；关闭授权会立即取消尚未发送的队列任务，重新开启后也只采集新产生的对话，不会回头把关闭期间或未激活期间的历史聊天记录补扫上传。

### 2.3 稳定 GitHub 交互通道（`gh`）与外部写入的 `unknown` 对账保护
- **统一的 `gh` 认证通道（硬性要求）与两阶段按需 Fork**：所有 GitHub API 读写与远端 Git 分支推送统一经由已认证的 `gh` CLI（`GhTransport` 调用 `gh api`，Git 凭据辅助器绑定 `!gh auth git-credential`）执行，访问令牌仅保留在 `gh` 受管凭据存储或环境变量中，绝不写入命令行参数、本地日志或公开配置文件。日常安装插件既不要求点 Star，也不会提前创建仓库 Fork；仅当用户显式开启知识贡献时，系统才按需为目标知识库创建或复用个人 Fork（绑定为 `<GH_USER>/<repo>`），是否点 Star 完全由用户自愿决定。若本机缺失 `gh` 或登录态失效，系统会显式报错并阻断未授权外发，绝不静默吞错。
- **每次外发重验授权**：每次执行外部写入（如推送分支或创建知识库 PR）前都会重新核对当前授权状态。
- **结果不确定（`unknown`）只读对账**：如果网络抖动导致写入回执丢失，该操作会被标记为 `unknown`（结果不确定）并保留原始操作 ID；系统在下次写入前必须先通过只读查询与远端仓库核对真实状态，绝不盲目当成“没发出去”而重复提交。

### 2.4 Shell 输入编码、原生会话身份、领域租约与 Windows 服务启动器

- **Shell 传输不等于原生授权（UTF-8 管道与原子代际绑定）**：PowerShell 的 `$OutputEncoding` 与 `Out-File` / `>` 重定向只决定 CLI 收到的字节；Windows PowerShell 调用本地 CLI 传输非 ASCII JSON 时应显式设置 `[Console]::InputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)` 并走 `stdin` 管道（避免 UTF-16LE 重定向损坏载荷）。同时，已激活运行时的 `(python, runtime_scripts)` 必须同代原子绑定，严禁新旧两代脚本与解释器混搭加载。
- **原生会话身份与会话授权**：`CODEX_THREAD_ID` 等原生会话标识必须由当前宿主工具环境提供；不得伪造、跨会话复制或拼装内部字段。会话授权按当前会话独立校验，不跨 Fork 或子代理继承。
- **领域租约独立存在**：公共检索可凭当前会话在默认引擎上的授权完成所选领域路由；但面向所选领域的蒸馏与会话采集绑定还必须具备该领域自身的有效租约，缺少该租约时蒸馏返回 `lease_required`；`knowledge_inactive` 也可能在查询阶段出现。
- **持久贡献授权与范围独立**：贡献开关、目标仓库与授权项目范围跨升级持久保存（`mindie-consent.json` 在代际切换与 GC 期间永不改写或删除），独立于会话授权和领域租约；共享关闭或采集超出范围时，不应为满足健康检查而冷启动采集。
- **Windows 服务启动器能力独立（双层 PE `Subsystem == 2` 核验）**：知识 API 可用不等于后台计划任务入口可用。注册与恢复启动前必须同时校验虚拟环境 `.venv\Scripts\pythonw.exe` 及其 `pyvenv.cfg` 所指向基底 `home\pythonw.exe` 的真实 PE 头 `OptionalHeader.Subsystem == 2`（`IMAGE_SUBSYSTEM_WINDOWS_GUI`），拒绝任何改名伪装的控制台二进制；API 通过但服务启动器不可用应如实报告为服务未就绪，绝不通过修补二进制绕过。

历史事故复盘、授权矩阵与分层恢复细节存档于[历史归档：Windows 知识调用与恢复](archive/knowledge-invocation-recovery.md)。

---

## 3. 对话正文提取与小模型索引边界

- **确定性提取公开对话**：仅保留有序的用户输入、助手公开进展和最终回答，剔除工具原始载荷、隐藏推理链（Reasoning）、系统注入指令和重复包装事件，不做掐头去尾的截断。
- **脱敏先行**：在写入磁盘、送给小模型或打包发布前，强制运行 Gitleaks 与确定性隐私脱敏规则。
- **小模型只写导航，不改正文**：适配器调用宿主自带的轻量小模型为新增 16KB 分块（`tasks/<32位任务哈希>/blocks/<64位块哈希>.md`）生成标题、检索摘要和短导航（`tasks/<32位任务哈希>/index.md`，顶层 `mindie-material-task/1` 清单内嵌 `mindie-entry/3` 导航目录）。小模型返回结果和 Token 用量会先落盘保存再应用到本地索引，一旦本地应用出错可直接复用已保存结果，绝不重复发起付费调用。

---

## 4. 操作寿命、取消信号与错误传递

1. **五类独立生命周期**：
   - 用户任务授权、单次工具调用、MCP 连接、本地辅助进程树、以及 `remote-dev` 远端持久后台作业拥有各自独立的生命周期。
   - **不设武断的全局业务超时**：耗时的远端编译或长算子测试只要连接与进程健康就继续运行，只有调用方显式传入的超时参数才会终止操作。
2. **精准取消，不误杀持久作业**：
   - 用户按取消（Interrupt）时，仅清理当前调用所拥有的进程树；独立运行的后台知识服务和通过 `remote-dev` 显式启动的远端持久作业不会因为一次短命令退出而被误杀。
   - *已知上游宿主限制说明*：OpenAI Codex CLI 在中断子代理（Subagent）时存在上游信号缺口，可能未向待处理的工具调用发送取消通知。MindIE Agent 如实记录该限制，不在插件内塞入高侵入性的私有杀进程轮询器；远端持久作业仍可通过 `remote-dev` 的 `job_cancel` 显式停止。
3. **跨平台进程树可靠回收**：
   - 后台摘要索引操作的进程树由平台原生原语兜底管理：Windows 使用命名 Job Object（`KILL_ON_JOB_CLOSE`），WSL 使用 `systemd` 临时用户服务（`KillMode=control-group`），macOS 使用轻量 `owner-pipe` 守护辅助进程，确保即使主控进程被强制 `SIGKILL` 也能干净回收所有子孙进程。详见[原生能力与系统机制复用](native-runtime-reuse.md)。

---

## 5. 本地权威状态保护与静默切换

- **Markdown 正文是唯一权威**：
  - 本地磁盘上的 Markdown 文件（`tasks/<32位任务哈希>/index.md` 与 `blocks/<64位块哈希>.md`，配合 `current.json` 双通道指针）是唯一权威正文；SQLite 保存游标、队列与回执；ReMe（基于 `TechnicalTokenizerV1` BM25 + `StrictFileGraph` + 引用谱系归并，`blocks.sqlite3` 增量 Checkpoint）是可随时重建的派生索引。
  - 如果启动时发现 SQLite 数据库缺失或损坏，系统会明确报告故障并完整保留所有已有的 Markdown 正文和 `unknown` 回执，绝不会将其当作“全新安装”去清空知识目录。
- **单安装绑定与空闲原子切换**：
  - 插件运行环境通过 `uv sync --locked --no-editable` 安装在宿主易失缓存目录之外的稳定应用数据目录中，维护唯一的当前激活绑定（Canonical Binding）。
  - 后台静默更新在锁外准备好新版本环境后，等待当前服务无在途业务时获取排他锁，安全退役旧服务并原子切换绑定，无需用户手动 Reload。详见[版本兼容与无感更新](release-compatibility-and-update.md)。

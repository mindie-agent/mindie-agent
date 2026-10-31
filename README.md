<p align="center">
  <img src="assets/brand/mindie-agent-logo.png" alt="MindIE Agent logo" width="128" height="128">
</p>

<h1 align="center">MindIE Agent</h1>

<p align="center">
  <strong>为原生编程 Agent 提供昇腾领域知识、远端 NPU 执行与可追溯的工程经验</strong>
</p>

<!-- mindie-org-versions:main-badges-zh:start -->
<p align="center">
  <a href="https://github.com/mindie-agent/mindie-agent/blob/main/docs/releases/0.1.5.md"><img src="https://img.shields.io/badge/release-v0.1.5-7045F5.svg" alt="Release v0.1.5"></a>
  <a href="https://github.com/mindie-agent/mindie-agent-cc"><img src="https://img.shields.io/badge/Claude_Code-Plugin-D97757.svg" alt="Claude Code Plugin"></a>
  <a href="https://github.com/mindie-agent/mindie-agent-codex"><img src="https://img.shields.io/badge/OpenAI_Codex-Plugin-10A37F.svg" alt="OpenAI Codex Plugin"></a>
  <a href="https://github.com/mindie-agent/mindie-agent-kimi"><img src="https://img.shields.io/badge/Kimi_Code-Plugin-2563EB.svg" alt="Kimi Code Plugin"></a>
  <a href="https://github.com/mindie-agent/mindie-agent-dsh"><img src="https://img.shields.io/badge/DeepSeek_Harness-Plugin-0EA5E9.svg" alt="DeepSeek Harness Plugin"></a>
  <a href="https://github.com/mindie-agent/mindie-agent-agy"><img src="https://img.shields.io/badge/Google_Antigravity-Plugin-4285F4.svg" alt="Google Antigravity Plugin"></a>
  <a href="https://github.com/mindie-agent/awesome-mindie-skills"><img src="https://img.shields.io/badge/Ascend_AI_Infra-vLLM--Ascend_%7C_AscendC_%7C_Triton-0F766E.svg" alt="Ascend NPU AI Infra"></a>
</p>
<!-- mindie-org-versions:main-badges-zh:end -->

<p align="center">
  <strong>中文</strong> · <a href="./README.en.md">English</a> · <a href="#-一句话无感安装仅接受-agent-安装-">⚡ 一句话安装</a> · <a href="#-为什么选择-mindie-agent">✨ 核心能力</a> · <a href="#️-架构全景与经验飞轮">🏗️ 架构全景</a> · <a href="#-装好之后怎么用">🔥 实战用法</a> · <a href="#-组件与仓库生态">📦 仓库生态</a> · <a href="#-如何参与贡献也是交给-agent">🤝 参与贡献</a> · <a href="#-010-里程碑与实测记录">🚀 v0.1.0 实测</a> · <a href="./docs/README.md">📚 文档中心</a>
</p>

---

## ⚡ 一句话无感安装（仅接受 Agent 安装 ☕）

别自己敲终端命令，也别去背繁琐的安装参数——既然这是给 AI 编程 Agent 用的昇腾能力底座，**安装这件体力活当然也只接受交给你的 Agent 来干**。

打开你正在使用的 **Claude Code**、**OpenAI Codex CLI**、**Kimi Code**、**DeepSeek Harness** 或 **Google Antigravity**，直接把下面这句话甩给它：

```text
帮我安装一下这个 https://github.com/mindie-agent/mindie-agent
```

剩下的事就不用管了：你的 Agent 读取本页后，会自动校验 **`gh`（GitHub CLI）稳定交互通道**、识别自身宿主环境并执行下方的**自动安装协议**，一步到位完成插件注册、运行时初始化与工作区引导。

<details>
<summary>🤖 <b>AI Agent 自动安装执行协议（点击展开 / Agent 读取本页时会自动解析执行）</b></summary>

> **给 AI Agent 的指令**：如果用户要求你安装 `mindie-agent`，请不要让用户手动翻文档，直接按以下五步在终端依次执行：
>
> #### 第一步：检查基础工具与 `gh` GitHub 交互通道（硬性前置指标）
> **稳定的 GitHub 交互通道（已安装并登录 `gh` CLI）是 MindIE Agent 的硬性指标**——插件版本拉取、锁定发行版校验、`knowledge-vllm-ascend` 知识源同步、经验闭环自动提交 PR（底层通过 `gh api` 与 `!gh auth git-credential` 驱动）以及组件故障上报均依赖该通道。请先在终端运行：
> ```bash
> git --version && uv --version && gh --version
> GH_USER=$(gh api --hostname github.com user --jq .login) && echo "GitHub channel verified for account: $GH_USER"
> gh auth setup-git --hostname github.com
> ```
> - **门禁要求（严禁跳过或静默忽略；仅安装 DSH `0.1.1` / `0.1.2` 且不启用社区贡献时可跳过 `gh` 门禁，但仍需 `git` 与 `uv`）**：
>   - 若未安装 `gh`：请先按宿主系统协助安装（macOS：`brew install gh`；Windows：`winget install --id GitHub.cli`；Ubuntu / WSL：`sudo apt update && sudo apt install -y gh`）。
>   - 账号读取成功时直接复用已有认证。需要登录时按 [GitHub 登录引导](docs/enterprise-network.md#github-登录引导) 处理：普通网络使用浏览器，企业网络或浏览器授权受阻时优先 Token；已有 Token 就通过 `gh` 隐藏提示输入，没有则引导创建。由 `gh` 保存凭据，验证账号、Git 及后续进程复用后继续安装。网络、代理或证书失败先修复传输，不把它们当作 Token 失效。
>
> #### 第二步：保留用户授权，按需准备贡献目标
> 安装过程只注册当前宿主所需的插件，不未经询问静默执行 Star 或 Fork；安装汇报完成后按第五步显式询问用户是否愿意为主仓点亮 Star ⭐。
>
> 社区贡献默认关闭。用户明确开启目标知识库 `<owner/repo>` 的贡献后，才创建或复用该知识库的个人 Fork，并绑定 `<GH_USER>/<repo>` 作为推送目标。不要因安装而 Fork 主仓、插件仓或所有领域仓库。
>
> #### 第三步：识别你所在的宿主客户端并安装对应插件
> 根据你自身的运行环境选择**唯一匹配**的分支执行（若不确定，请检查 `claude --version`、`codex --version`、`kimi --version`、`dsh --version` 或 `agy --version`；当前插件版本为 Codex `v0.1.13`、Claude Code `v0.1.10`、Kimi Code `v0.1.10`、DSH `v0.1.9` 与 Google Antigravity `v0.1.0`，共享组件直接从各官方 GitHub 仓库拉取最新正式 Release，完整版本清单见 [`channels/0.1.json`](./channels/0.1.json)）：
>
> - **分支 A — 如果你是 Claude Code（或检测到 `CLAUDECODE` 环境变量 / 用户使用 `claude`）**：
>   ```bash
>   claude plugin marketplace add "https://github.com/mindie-agent/mindie-agent-cc.git#v0.1.10"
>   claude plugin install mindie-agent@mindie-agent-cc --scope user
>   claude --init-only
>   claude plugin list --json
>   claude mcp list
>   ```
>   *验证标准*：`claude plugin list --json` 显示 `mindie-agent@mindie-agent-cc`（`0.1.10`）已启用，且 `claude mcp list` 中 `knowledge`、`remote` 与 `components` 均显示 `Connected`。
>
> - **分支 B — 如果你是 OpenAI Codex CLI（或检测到 `CODEX_CI` / `CODEX_THREAD_ID` / 用户使用 `codex`）**：
>   ```bash
>   codex plugin marketplace add https://github.com/mindie-agent/mindie-agent-codex.git --ref v0.1.13
>   codex plugin add mindie-agent@mindie-agent --json
>   codex plugin list --json
>   ```
>   *验证标准*：`codex plugin list --json` 显示 `mindie-agent@mindie-agent`（`0.1.13`）已启用。提醒用户开启新会话即可自动触发 `SessionStart` 构建锁定运行时。
>
> - **分支 C — 如果你是 Kimi Code CLI（或检测到 `KIMI_CODE_HOME` / 用户使用 `kimi`）**：
>   ```bash
>   MINDIE_TMP="${TMPDIR:-/tmp}/mindie-agent-kimi-install"
>   rm -rf "$MINDIE_TMP"
>   git clone --depth 1 --branch v0.1.10 https://github.com/mindie-agent/mindie-agent-kimi.git "$MINDIE_TMP"
>   SETUP_OUT=$(python3 "$MINDIE_TMP/scripts/setup.py")
>   echo "$SETUP_OUT"
>   NATIVE_PKG=$(printf '%s\n' "$SETUP_OUT" | python3 -c 'import sys, json; text=sys.stdin.read(); data=json.loads(text[text.find("{"):]); print(data["native_package"])')
>   python3 "$MINDIE_TMP/scripts/install_kimi_plugin.py" --kimi-home "${KIMI_CODE_HOME:-$HOME/.kimi-code}" --plugin-root "$NATIVE_PKG"
>   ```
>   *验证标准*：安装脚本成功返回，告知用户可在会话中输入 `/mindie-agent` 使用。
>
> - **分支 D — 如果你是 DeepSeek Harness（DSH，或检测到 `DSH_PROFILE` / `DSH_HOME` / 用户使用 `dsh`）**：
>   ```bash
>   MINDIE_TMP="${TMPDIR:-/tmp}/mindie-agent-dsh-install"
>   rm -rf "$MINDIE_TMP"
>   git clone --depth 1 --branch v0.1.9 https://github.com/mindie-agent/mindie-agent-dsh.git "$MINDIE_TMP"
>   uv --native-tls run --quiet --no-project --python 3.11 "$MINDIE_TMP/scripts/setup.py"
>   ```
>   随后在 DSH Web 的 **Plugins** 页面安装并启用：
>   ```text
>   git+https://github.com/mindie-agent/mindie-agent-dsh.git#v0.1.9
>   ```
>   如果当前就在 DSH 会话内且具备 `plugin_manager` 工具，可用它完成同一步骤：
>   ```text
>   plugin_manager(action="install_bundle", target="git+https://github.com/mindie-agent/mindie-agent-dsh.git#v0.1.9")
>   ```
>   *验证标准*：`setup.py` 最终 JSON 中 `status` 为 `ready`、`activation.status` 为 `active`，且 `knowledge.status` 为 `inactive`（安装期不启动知识服务，待会话内调用 `/mindie-agent` 时按需启用）；Plugins 页面显示 `mindie-agent-dsh` 已启用。提醒用户打开**新会话**后即可使用 `/mindie-agent`。
>
> - **分支 E — 如果你是 Google Antigravity（AGY，或检测到 `~/.gemini/antigravity` / 用户使用 `agy`）**：
>   ```bash
>   MINDIE_TMP="${TMPDIR:-/tmp}/mindie-agent-agy-install"
>   rm -rf "$MINDIE_TMP"
>   git clone --depth 1 --branch v0.1.0 https://github.com/mindie-agent/mindie-agent-agy.git "$MINDIE_TMP"
>   mkdir -p ~/.gemini/plugins
>   rm -rf ~/.gemini/plugins/mindie-agent
>   cp -R "$MINDIE_TMP/plugins/mindie-agent" ~/.gemini/plugins/mindie-agent
>   python3 ~/.gemini/plugins/mindie-agent/scripts/setup.py init --workspace-root "$PWD"
>   ```
>   *验证标准*：`setup.py init` 返回 `status: initialized` 且生成 `~/.config/mindie-agent/agy.json`，插件挂载在 `~/.gemini/plugins/mindie-agent`（也可挂载到工作区 `.agents/plugins/mindie-agent`）。提醒用户在会话中输入 `/mindie-agent` 即可按需启用领域知识与 Skill。
>
> - **分支 F — 如果你是 Cursor / 其他通用 MCP 客户端（仅需 SSH 远端 NPU 开发底座 `remote-dev`）**：
>   在项目的 `.mcp.json`（或 `.cursor/mcp.json`）中写入 `remote-dev` 服务：
>   ```json
>   {
>     "mcpServers": {
>       "remote-dev": {
>         "type": "stdio",
>         "command": "uvx",
>         "args": ["--from", "git+https://github.com/mindie-agent/remote-dev@v0.11.2", "remote-dev", "server"]
>       }
>     }
>   }
>   ```
>
> #### 第四步：完成首次配置与开发工作区引导
> 五种完整插件安装后均引导完成首次工作区配置：复用已验证的 GitHub 认证，介绍用户须知，并提供创建/初始化 [vllm-ascend-workspace](https://github.com/mindie-agent/vllm-ascend-workspace)、复用已有目录或继续当前工作区的选项：
>
> - [Codex 工作区引导](https://github.com/mindie-agent/mindie-agent-codex/blob/main/plugins/mindie-agent/skills/mindie-agent/references/workspace-setup.md)
> - [Claude Code 工作区引导](https://github.com/mindie-agent/mindie-agent-cc/blob/main/skills/mindie-agent/references/workspace-setup.md)
> - [Kimi Code 工作区引导](https://github.com/mindie-agent/mindie-agent-kimi/blob/main/skills/mindie-agent/references/workspace-setup.md)
> - [DSH 工作区引导](https://github.com/mindie-agent/mindie-agent-dsh/blob/main/skills/mindie-agent/references/workspace-setup.md)
> - [Google Antigravity 工作区引导](https://github.com/mindie-agent/mindie-agent-agy/blob/main/plugins/mindie-agent/skills/mindie-agent/references/workspace-setup.md)
>
> 用户确认目录后，自动将所选绝对路径登记到当前宿主的原生项目/工作区列表并遵循 `AGENTS.md` 与 `repo_init.py` 完成初始化；已有工作区选择直接复用，日常开发中不再重复询问。
>
> #### 第五步：向用户汇报安装结果并询问是否点亮 Star ⭐
> 安装完成后，向用户简要汇报：
> 1. 适用时已验证的 `gh` GitHub 交互通道及认证账号；
> 2. 已安装的客户端插件名称、版本与验证结果；
>    同时报告工作区路径、宿主登记/打开状态和源码初始化状态；原生界面仍需操作时给出剩余步骤；
> 3. 说明日常开发只需通过单一入口 `/mindie-agent` 唤醒昇腾领域知识与 Skill，而远端 NPU 工具（`remote-dev`）在日常对话中默认自动触发；
> 4. 说明**社区知识贡献**与**产品故障自动上报**默认均处于关闭状态（Opt-in）；若后续用户开启社区知识贡献，Agent 会自动按需 Fork 对应的目标知识库（如 `mindie-agent/knowledge-vllm-ascend` -> `$GH_USER/knowledge-vllm-ascend`）并完成绑定；
> 5. **询问用户是否愿意给主仓点个 Star ⭐**：在汇报末尾主动询问用户：
>    > *“如果觉得 MindIE Agent 对你有帮助，需要我顺手帮你在 GitHub 上给主仓 `mindie-agent/mindie-agent` 点个 Star 吗？这能帮助项目更好地成长！⭐”*
>    - **严格授权原则**：**仅当用户明确表示同意（如回复“好”、“可以”、“yes”等）时才执行该命令，严禁未经用户同意自动静默执行**。用户同意后，立即运行以下命令点亮主仓 Star 并校验状态：
>      ```bash
>      gh api --hostname github.com --silent -X PUT /user/starred/mindie-agent/mindie-agent && gh api --hostname github.com --silent /user/starred/mindie-agent/mindie-agent
>      ```

</details>

---

## ✨ 为什么选择 MindIE Agent？

MindIE Agent 在你已有的 Claude Code、Codex、Kimi Code、DSH 或 Google Antigravity 会话中提供领域知识和远端开发工具，覆盖 `vLLM-Ascend` / `vLLM-Omni`、`MindIE-SD`、昇腾算子与分布式推理等核心领域，支撑模型 0day 开发、固定 case 的模型或算子性能优化、问题定位三个核心场景。实现与验收进展见[系统架构](./docs/architecture.md)和下方发布记录。

| 能力 | 帮你完成的工作 |
| --- | --- |
| **带适用条件的领域知识** | 按框架版本、硬件型号和输入条件按需检索工程规范、排查步骤（SOP）、工作流与代码优化模式，支持批量 `refs` 精读与共享 `known_refs` / `token_budget` 预算，关联具体源码提交、`rejected_history` 与 `affected_components` 实测证据；缺失前提不会被盲目当成匹配 |
| **远端 NPU 开发与验证** | 通过 [`remote-dev`](https://github.com/mindie-agent/remote-dev) 在远端 SSH 主机和容器中读写文件、应用补丁、执行命令、管理后台长任务与拉取产物，内置破坏性命令安全拦截门禁，并共享用户私有 `~/.mindie/ssh/id_ed25519` 凭据回退与密钥 |
| **性能 Profiling 与机理建模** | 通过 [`profiler`](https://github.com/mindie-agent/profiler) 就地解析昇腾 `msprof` 数据、用 `analyze_profiling --structure` 基于 `mindie-model-structure/1` 执行三态拓扑对齐（`aligned / declared_only / unattributed_observed`）及 `auto_segment_decode_forwards` Decode 自动切分；通过 [`sim`](https://github.com/mindie-agent/sim) 统一建模硬件资源、算子族、子图、纯模型成本与服务约束（覆盖 `DP × TP × EP × PP × DCP / DSA-CP / PCP` 与 PD 分离），输出 4D 效率拆解（`Cube_MFU / Vec_MFU / MBU / Link_Util / CV_Overlap`）与 30ms SLA 硬件缩放推演 |
| **多卡资源协调与故障诊断** | 按需使用 [`coordinator`](https://github.com/mindie-agent/coordinator) 协调多 Agent 并发时的单 Die 显存租约预算（per-Die HBM lease）、并发编译槽位与端口分配，用支持 A2/A3/A5 与 `~/.mindie/ssh` 回退的 [`npu-top`](https://github.com/mindie-agent/npu-top) 实时查看设备占用，用 [`diagnostics`](https://github.com/mindie-agent/diagnostics) 定位 CANN/`plog` 报错并支持有界 2 次外发对账重试的故障上报 |
| **可追溯的经验沉淀** | 在用户授权范围内自动脱敏并保存排障与调优记录；将验证通过的解决方案提炼为结构化知识单元，审核后入库复用或按配置提交社区 PR |

插件保留原生宿主的会话和工具机制，按需加载领域内容。详细约束见[知识与经验系统](./docs/knowledge-system.md)。

---

## 🏗️ 架构全景与经验飞轮

### 1. 模块化分层架构

MindIE Agent 采用**薄客户端适配层 + 独立共享运行时底座**架构，不绑架业务源码仓库：

```mermaid
flowchart TB
  subgraph Clients["🧑‍💻 开发者日常 AI 编程客户端 (Native Coding Agents)"]
    CC["Claude Code"]
    Codex["OpenAI Codex CLI"]
    Kimi["Kimi Code CLI"]
    DSH["DeepSeek Harness"]
    AGY["Google Antigravity"]
  end

  subgraph Adapters["🔌 原生插件薄适配层 (Thin Harness Plugins)"]
    P_CC["mindie-agent-cc"]
    P_Codex["mindie-agent-codex"]
    P_Kimi["mindie-agent-kimi"]
    P_DSH["mindie-agent-dsh"]
    P_AGY["mindie-agent-agy"]
  end

  subgraph Core["⚙️ 共享运行时组件底座 (Shared Runtime Components)"]
    Knowledge["🧠 mindie-knowledge<br/>领域知识库 · 条件检索 · 经验提炼与复用"]
    Coord["🎯 coordinator<br/>远端昇腾环境管理 · 容器开通/绑定 · NPU 探测与选卡防冲突"]
    RemoteDev["⚡ remote-dev<br/>SSH 文件读写与命令执行 · 容器直连 · 后台长作业"]
    Profiler["🔬 mindie-profiler<br/>昇腾 msprof 解析 · 模型结构对齐 · 优化前后对比"]
    Sim["📐 mindie-sim<br/>五层因果建模 · 4D 效率拆解 · SLA 硬件配比推演"]
    NpuTop["📊 npu-top<br/>Web 实时监控看板 · 90 天利用率热力图"]
    Diag["🛡️ mindie-diagnostics<br/>CANN/plog 故障诊断 · 本地轮转日志 · 可选白名单上报"]
  end

  subgraph Remote["🖥️ 远端昇腾集群与知识源 (Ascend Fleet & Canonical Feeds)"]
    Feed[("📚 7 大昇腾领域知识库<br/>(vLLM-Ascend · Operators · Infer · Agent Eng)")]
    Cluster[("🚀 远端昇腾 NPU 主机与 Docker 容器")]
  end

  CC --> P_CC
  Codex --> P_Codex
  Kimi --> P_Kimi
  DSH --> P_DSH
  AGY --> P_AGY

  P_CC & P_Codex & P_Kimi & P_DSH & P_AGY --> Knowledge & RemoteDev & Diag & Profiler & Sim
  Task["按需安装 TaskClient / coordinator"] --> Coord
  Bench["mindie-bench 评测套件"] --> Task & Clients
  Knowledge <--> Feed
  Coord -- "自动同步 endpoints.json / Resolver" --> RemoteDev
  Coord & RemoteDev --> Cluster
  NpuTop -. "人类 Web 监控 (只读)" .-> Cluster
```

### 2. 昇腾 AI Infra 研发、测试与经验自进化闭环

```mermaid
sequenceDiagram
  autonumber
  actor Dev as 开发者
  participant Agent as Coding Agent (Claude / Codex / Kimi / DSH / Antigravity)
  participant Know as mindie-knowledge (本地服务)
  participant NPU as remote-dev (远端昇腾容器)
  participant Repo as 公共工程知识库 (knowledge-vllm-ascend 等)

  Dev->>Agent: 输入 /mindie-agent + 研发需求（特性设计 / 算子开发 / 测试构建 / 调优排障）
  Agent->>Know: 1. 携带已知环境检索 (query)，按精确引用读取 (explain)
  Agent->>NPU: 2. 在选定容器内编写代码、同步补丁并运行测试
  NPU-->>Agent: 返回编译、正确性与性能结果以及日志引用
  Agent-->>Dev: 3. 交付实现和实际验证范围，可提交具体修订的有用性反馈
  Note over Agent,Know: 采集需当前会话已手动调用 /mindie-agent 且满足贡献授权与项目范围
  Agent->>Know: 4. 已启用会话结束时按授权采集并脱敏任务记录
  Agent->>Know: 5. 从已验证的排障/调优结果提炼并审核新知识单元
  Note over Know,Repo: 公开贡献另需开启并配置目标仓库
  Know->>Repo: 6. 按需提交社区 PR；远端合并与本地同步分别确认
```

---

## 🔥 装好之后怎么用？（触发方式与使用示例）

MindIE Agent 的核心交互理念是**极简易用与渐进式披露（Progressive Disclosure）**——对用户而言，**从头到尾只需要知道 `/mindie-agent` 这一个入口**，不需要记忆任何复杂的子命令（如 `:init`、`:status` 等），底层上下文只在 Agent 需要时按需向 Agent 渐进式披露：

| 能力模块 | 触发方式 | 极简使用方式说明 |
| --- | --- | --- |
| **🧠 昇腾 Infra 知识库、经验与 Skill 系统**<br/>（`mindie-knowledge` + 领域 Skills） | **当前会话手动触发**<br/>（统一入口 `/mindie-agent`） | 在开展昇腾 AI Infra 方案设计、`vLLM-Ascend` 特性开发、`AscendC` / `Triton` 算子实现、测试验证或性能调优时，在当前聊天显式输入一次 **`/mindie-agent` + 你的需求描述**（Codex 中也可输入 `$mindie-agent`），本会话后续轮次即持续启用知识检索、反馈、蒸馏与同步。首次配置、查看状态或开关共享同样只需输入 `/mindie-agent` 加自然语言。 |
| **⚡ 远端昇腾服务器开发与确定性工具**<br/>（`remote-dev` / `coordinator` / `profiler` / `sim` / `diagnostics`） | **默认自动触发**<br/>（常驻可用，无需 `/mindie-agent`） | `remote-dev` 及确定性工程工具默认处于就绪状态。日常对话中只要提到远端服务器、容器、NPU 探测/监控、Profiling 解析、Roofline 仿真或事实状态查询，Agent 就会**默认自动调用**对应工具，无需先输入 `/mindie-agent`。 |
| **🔄 研发经验沉淀与社区共建**<br/>（授权采集、脱敏、提炼与审核） | **授权一次配置，在 `/mindie-agent` 会话中自动运行** | 贡献授权（`mindie-consent.json`）一次配置跨会话持久有效。在已通过 `/mindie-agent` 启用的会话中，`Stop` 事件自动采集并脱敏授权项目范围内的公开对话（未调用 `/mindie-agent` 的普通会话不触发采集）；新知识从显式选定的已验证证据提炼并经审核入库与发布。 |

### 实战对话示例（直接复制即可体验）

#### 💡 示例 1：手动输入 `/mindie-agent` 辅助特性设计、算子开发与测试构建
```text
/mindie-agent 我准备在 vllm-ascend 中为新模型实现一个自定义融合算子（提供 Triton / AscendC 实现）并补齐单元与精度测试，请结合知识库里的现有设计规范、算子适配经验帮我制定实现方案。
```
> **背后发生的事**：Agent 根据任务选择领域，携带实际环境条件检索，再按精确引用读取相关单元及其继承规则。知识中的来源、适用前提和验证范围会随内容保留，供实现与测试时核对。

#### 💡 示例 2：日常对话默认触发 `remote-dev`，在远端昇腾容器内开发编译与跑测
```text
连上远端机器 192.0.2.21（端口 22）上的 vllm-dev 容器，把我本地新写的算子实现和 tests/ 下的单测同步到 /workspace/vllm-ascend，在 NPU 上跑一下完整的 pytest 精度与性能测试。
```
> **背后发生的事**：无需输入任何斜杠命令，Agent 默认自动调用 `remote-dev` 的 `remote_read`、`remote_edit` 与 `remote_bash` 在远端 `vllm-dev` 容器内完成代码同步、编译与 NPU 实机单测；长耗时编译或测试会自动转为受管后台作业并支持实时看日志。

#### 💡 示例 3：`/mindie-agent` + `remote-dev` 联动调优，研发经验后台静默沉淀
```text
/mindie-agent 结合昇腾推理与算子调优经验，帮我在远端 NPU 开发机上分析当前 decode 阶段的时延瓶颈，拉取 Profiling 关键指标并验证优化补丁。
```
> **背后发生的事**：Agent 结合领域知识和远端执行结果定位瓶颈，分别验证正确性与固定条件下的性能。授权采集保留该任务的脱敏材料；后续可以选择其中的证据提炼知识，经审核后用于新的任务或公开贡献。

---

## 📦 组件与仓库生态

`@mindie-agent` 组织下的每个仓库均遵循单一职责边界，既可由插件协同联动，也可独立安装使用：

<!-- mindie-org-versions:main-ecosystem-zh:start -->
### 1. 产品总入口、评测基准与社区生态

| 仓库 | 当前版本 | 定位与核心职责 |
| --- | --- | --- |
| **[`mindie-agent`](https://github.com/mindie-agent/mindie-agent)** *(本仓库)* | [`v0.1.5`](https://github.com/mindie-agent/mindie-agent/releases/tag/v0.1.5) | 顶层产品入口、整体架构、工程设计原则、跨组件发布兼容契约与正式发行版记录 |
| **[`mindie-bench`](https://github.com/mindie-agent/mindie-bench)** | [`v0.4.5`](https://github.com/mindie-agent/mindie-bench/releases/tag/v0.4.5) | 独立评测框架与真机基准套件：20 个行为级验证任务（109 项三态与辅助变体对照）、预置准入脚手架（Gate Runner）、隔离宿主运行（原生知识评测接入与 `zsh` 临时目录隔离）、组件级基准、跨任务知识复用及端到端总工程成本校验 |
| **[`awesome-mindie-skills`](https://github.com/mindie-agent/awesome-mindie-skills)** | [`main`](https://github.com/mindie-agent/awesome-mindie-skills) | 面向昇腾 NPU AI Infra 全流程的高质量开源 Agent Skills 精选目录（现已覆盖 `vLLM-Ascend`、`AscendC`/`Triton` 算子开发、精度测试与性能调优，持续扩展中） |
| **[`vllm-ascend-workspace`](https://github.com/mindie-agent/vllm-ascend-workspace)** | [`main`](https://github.com/mindie-agent/vllm-ascend-workspace) | 轻量可定制的 `vLLM` + `vLLM-Ascend` 本地多任务开发工作区，支持独立 Git Worktree 隔离与 MindIE Agent 集成 |

### 2. 原生客户端插件（Harness Adapters）

| 仓库 | 适用宿主 | 当前版本 | 定位与核心职责 |
| --- | --- | --- | --- |
| **[`mindie-agent-cc`](https://github.com/mindie-agent/mindie-agent-cc)** | **Claude Code** | [`v0.1.10`](https://github.com/mindie-agent/mindie-agent-cc/releases/tag/v0.1.10) | Claude Code 原生插件：生命周期 Hook、MCP 服务桥接与运行时版本锁定 |
| **[`mindie-agent-codex`](https://github.com/mindie-agent/mindie-agent-codex)** | **OpenAI Codex CLI** | [`v0.1.13`](https://github.com/mindie-agent/mindie-agent-codex/releases/tag/v0.1.13) | OpenAI Codex CLI 原生插件：Marketplace 安装、会话记录增量脱敏采集与 MCP 服务管理 |
| **[`mindie-agent-kimi`](https://github.com/mindie-agent/mindie-agent-kimi)** | **Kimi Code CLI** | [`v0.1.10`](https://github.com/mindie-agent/mindie-agent-kimi/releases/tag/v0.1.10) | Kimi Code 原生插件：运行时原子版本切换、会话记录脱敏采集与 MCP 桥接 |
| **[`mindie-agent-dsh`](https://github.com/mindie-agent/mindie-agent-dsh)** | **DeepSeek Harness (DSH)** | [`v0.1.9`](https://github.com/mindie-agent/mindie-agent-dsh/releases/tag/v0.1.9) | DSH 原生插件：`/mindie-agent` Skill、知识检索工具、生命周期桥接与 `remote-dev` 集成 |
| **[`mindie-agent-agy`](https://github.com/mindie-agent/mindie-agent-agy)** | **Google Antigravity** | [`v0.1.0`](https://github.com/mindie-agent/mindie-agent-agy/releases/tag/v0.1.0) | Google Antigravity 原生插件：`/mindie-agent` 会话租约门控、原生远端工具别名、7 大共享组件 MCP 桥接与 Brain Transcript 脱敏采集 |

### 3. 共享运行时组件底座（Shared Runtime Components）

| 仓库 | Python 包 / 入口 | 当前版本 | 定位与核心职责 |
| --- | --- | --- | --- |
| **[`knowledge`](https://github.com/mindie-agent/knowledge)** | `mindie-knowledge` | [`v0.13.7`](https://github.com/mindie-agent/knowledge/releases/tag/v0.13.7) | 结构化分级知识单元（L1–L4）管理、按信息缺口条件检索、批量 `refs` 精读与共享 `known_refs` / `token_budget` 预算、负面尝试历史（`rejected_history`）与受影响组件（`affected_components`）溯源、双层脱敏采集与社区 PR 发布 |
| **[`remote-dev`](https://github.com/mindie-agent/remote-dev)** | `remote-dev` | [`v0.11.2`](https://github.com/mindie-agent/remote-dev/releases/tag/v0.11.2) | SSH 远端文件读写与命令执行、共享用户私有 `~/.mindie/ssh/id_ed25519` 凭据回退与公钥维护、破坏性命令安全拦截门禁、Docker 容器直连、后台长作业管理、连接复用与产物同步 |
| **[`coordinator`](https://github.com/mindie-agent/coordinator)** | `mindie-coordinator` | [`v0.7.0`](https://github.com/mindie-agent/coordinator/releases/tag/v0.7.0) | 远端昇腾环境与多 Agent 资源协调器：SSH 主机/多机互通配置、容器开通与绑定、NPU 拓扑探测（兼容 A2/A3 双 Die/A5）、HCCL/RoCE 预检、单 Die 显存租约预算与并发编译槽位控制及端口防冲突 |
| **[`profiler`](https://github.com/mindie-agent/profiler)** | `mindie-profiler` / `mindie_profiler` | [`v0.5.3`](https://github.com/mindie-agent/profiler/releases/tag/v0.5.3) | 昇腾 Profiling 采集与解析组件：受控采集、`msprof` 产物就地只读分析（`inventory / analyze / correlate / compare / sql`）、`analyze_profiling --structure` 基于 `mindie-model-structure/1` 的三态拓扑对齐（`aligned / declared_only / unattributed_observed`）与 `auto_segment_decode_forwards` Decode 自动切分、显存拆解及跨版本对比 CLI |
| **[`sim`](https://github.com/mindie-agent/sim)** | `mindie-sim` / `mindie_sim` | [`v0.8.1`](https://github.com/mindie-agent/sim/releases/tag/v0.8.1) | 硬件无关的五层因果性能建模组件：统一组合硬件资源、算子族、子图、纯模型成本与服务约束（覆盖 `DP × TP × EP × PP × DCP / DSA-CP / PCP` 与 PD 分离），支持 4D 效率拆解（`Cube_MFU / Vec_MFU / MBU / Link_Util / CV_Overlap`）、30ms SLA 硬件缩放求解器、`mindie-model-structure/1` 导出及 856 用例跨集群校准 |
| **[`npu-top`](https://github.com/mindie-agent/npu-top)** | `npu-top` | [`v0.3.0`](https://github.com/mindie-agent/npu-top/releases/tag/v0.3.0) | 昇腾 NPU 可视化监控看板：支持 A2 / A3 / A5 集群监控、共享读取 `coordinator` 的 `machines.json` 与 `~/.mindie/ssh` 凭据回退，提供本地回环 Web 实时状态页（`127.0.0.1:8788`）、TUI、CLI/MCP 与 90 天 SQLite 利用率热力图 |
| **[`diagnostics`](https://github.com/mindie-agent/diagnostics)** | `mindie-diagnostics` / `mindie_diagnostics` | [`v0.5.4`](https://github.com/mindie-agent/diagnostics/releases/tag/v0.5.4) | 故障诊断与日志组件：支持 CANN 错误码与 `plog` 根因分析、4×1 MiB 本地轮转日志、离线脱敏诊断包与带 2 次有界外发对账重试的可选 GitHub Issue 白名单上报 |

### 4. 昇腾领域公共知识库（Public Domain Knowledge Corpora）

所有公共知识库均采用 `mindie-graded-unit/1` 结构化分级单元格式（`L1` 事实与约束标准 · `L2` 标准排障与开发规程 · `L3` 多阶段工程工作流 · `L4` 深度调优模式），附带适用条件（`applicability`）与实证依据：

| 仓库 | 领域标识 (`domain`) | 知识规模与基线提交 | 定位与覆盖范围 |
| --- | --- | --- | --- |
| **[`knowledge-vllm-ascend`](https://github.com/mindie-agent/knowledge-vllm-ascend)** | `vllm-ascend` | 91 单元 · [`d3d5bf63`](https://github.com/mindie-agent/knowledge-vllm-ascend/tree/d3d5bf6320e171d4a0f131a6f746858700e0c4cc) | `vLLM-Ascend` 与 `vLLM-Omni` 领域工程知识库：覆盖新模型 0day 接入、PD 分离、MoE EP/MC2、量化与投机解码、ACLGraph/TorchAir，以及 `vllm-omni` 多阶段全模态（`Thinker -> Talker -> Code2Wav` / AR+DiT / TTS / Duplex）流水线调优 |
| **[`knowledge-operators`](https://github.com/mindie-agent/knowledge-operators)** | `operators` | 105 单元 · [`6f083f81`](https://github.com/mindie-agent/knowledge-operators/tree/6f083f810c0d8eb77b9d7992ba96b19c51dfaf74) | 昇腾算子工程知识库：覆盖 910B / 910C (A3) / 950 (A5) 硬件约束、`AscendC`、`Triton-Ascend`、Catlass、FlashAttention/MLA、Matmul/MoE 融合，以及 `MindIE-SD` 稀疏注意力自定义算子与子图融合流水分析 |
| **[`knowledge-infer-core`](https://github.com/mindie-agent/knowledge-infer-core)** | `infer-core` | 109 单元 · [`b319ab36`](https://github.com/mindie-agent/knowledge-infer-core/tree/b319ab36f1b2d84c5d9c33b123ca2c24e6637f80) | 昇腾推理服务与引擎核心知识库：覆盖 `cann-recipes-infer` 模型优化 Recipe、`Ascend/MindIE-SD`（`mindiesd`）扩散模型稀疏注意力（`RainFusion`/`Ada-BSA`/`EagleQBSA`）、跨步缓存（`DiTCache`）、3D VAE 状态切片解码与动态时步量化契约 |
| **[`knowledge-infer-distributed`](https://github.com/mindie-agent/knowledge-infer-distributed)** | `infer-distributed` | 39 单元 · [`4cfe3db3`](https://github.com/mindie-agent/knowledge-infer-distributed/tree/4cfe3db3f7610acbded3a4c34f7551e88aba9b77) | 分布式推理与集合通信知识库：覆盖 HCCL 通信排障、RoCE/HCCS 拓扑、SHMEM、Mooncake/Yuanrong 传输，以及多机 `DP/TP/EP/PP/DCP/DSA-CP/PCP` 与 DiT Ulysses/Ring/CFG 混合并行及功耗降频治理 |
| **[`knowledge-infer-observability`](https://github.com/mindie-agent/knowledge-infer-observability)** | `infer-observability` | 39 单元 · [`13a308e3`](https://github.com/mindie-agent/knowledge-infer-observability/tree/13a308e33f3c24b7222faa296024739351771f48) | 推理可观测性、诊断与评测知识库：覆盖 CANN/`plog`/Device 报错定位、`msprof` 性能拆解、容量/性能仿真，以及窗口化交错 A/B/A 性能门禁（`perf-gate`）与三级图像/视频生成精度门禁（`accuracy-gate`） |
| **[`knowledge-infer-ops-compat`](https://github.com/mindie-agent/knowledge-infer-ops-compat)** | `infer-ops-compat` | 34 单元 · [`bc594941`](https://github.com/mindie-agent/knowledge-infer-ops-compat/tree/bc59494157f0bf000ac7d05f6719aa487d062260) | 图编译、算子注册与迁移兼容知识库：覆盖 TorchAir/ACLGraph 图捕获、`torch_npu._inductor` Pattern Pass 开发、两阶段（API 优先→图编译）框架集成、CUDA 至昇腾迁移与容器/集群部署 |
| **[`knowledge-agent-engineering`](https://github.com/mindie-agent/knowledge-agent-engineering)** | `agent-engineering` | 33 单元 · [`6cf68034`](https://github.com/mindie-agent/knowledge-agent-engineering/tree/6cf68034126486934bf96d96d809c3de1e608b5f) | Agent 工程与治理知识库：覆盖多 Agent 协同编排、`MindIE-SD` S0–S6 自动调优闭环、知识库质量门禁（`kb-lint`）、双层隐私脱敏与真机基准评测方法 |
<!-- mindie-org-versions:main-ecosystem-zh:end -->

---

## 🧭 工程设计哲学

MindIE Agent 在持续演进中沉淀了 **18 条务实的[工程设计原则](./docs/design-principles.md)**（[English](./docs/design-principles.en.md)），核心理念包括：

- **以完成用户实际目标的总成本衡量效率**：绝不为了防备极小概率异常而给每次日常任务强加繁琐仪式。
- **零心智负担与按需介入**：工具内部消化管理复杂度；Skill 仅提供信息与导航；知识仅作带证据的参考，绝不喧宾夺主。
- **优先复用成熟机制，按需自研补充**：优先复用宿主客户端、操作系统与成熟组件能力，升级替代旧方案时彻底清理历史兼容包袱。
- **诚实可观测，严禁静默降级或隐藏错误**：明确区分“执行完成”、“执行失败”与“外部副作用不确定（`unknown`）”，绝不伪造成功或盲目重放不确定写入。
- **Agent-Native 精炼规范与有界资源纪律**：核心模块 `< 800` 行并具备顶部四段式契约头，常驻内存/显存严格有界并按本机与远端真实硬件规格自动分流。

---

## 🤝 如何参与贡献（也是交给 Agent）

和安装一样，给 MindIE Agent 贡献新特性、修 Bug 或补充昇腾领域知识，**同样推荐直接把需求甩给你的编程 Agent**（`@mindie-agent` 旗下全部仓库 100% 由 Agent 编写、测试与维护）。

为了保证多仓库演进不写出过度防御的冗余代码、不污染宿主机环境，我们为参与贡献的 Agent 设定了**两道硬性门禁**（完整说明见 **[`CONTRIBUTING.md`](./CONTRIBUTING.md)** · **[English](./CONTRIBUTING.en.md)**）：

1. **📖 开发特性前：先读设计原则** —— 动手写代码前，Agent 必须先阅读 [`AGENTS.md`](./AGENTS.md) 与 [`docs/design-principles.md`](./docs/design-principles.md)，对齐单一职责边界、反静默回退、超时算术、反过度防御四大铁律、`< 800` 行与顶部契约头以及有界内存/显存规格分流等架构与设计准则。
2. **✅ 提交 PR 后：完成 Checklist 逐项自检（含开发格式规范）** —— PR 提交后，Agent 必须对照 [`.github/pull_request_template.md`](./.github/pull_request_template.md) 逐项复核最终 `git diff`（勾选 `1–8` ~ `15` 全部检查项，包含全仓强制 Unix `LF` `\n` 换行格式等开发规范，如实填写具体的**`自查结论与证据`**与**`验证结果`**），并通过 CI 自动门禁（[`check_lf_eol.py`](./.github/scripts/check_lf_eol.py) + [`check_pr_checklist.py`](./.github/scripts/check_pr_checklist.py)）核验后合入。

想贡献改动时，直接复制下面这段话发给你的 Agent 即可：

```text
我想给 MindIE Agent 贡献一个改动：<在这里一句话描述你想加的特性、修复的 Bug 或补充的昇腾知识>。
请严格按照 https://github.com/mindie-agent/mindie-agent/blob/main/CONTRIBUTING.md 的流程推进：
1. 动手写代码前，先阅读 AGENTS.md 与 docs/design-principles.md 对齐设计原则；
2. 完成代码与分层测试后提交 PR，并对照 .github/pull_request_template.md 完成 Pre-PR Checklist 逐项自检与验证证据回填。
```

---

## 🚀 0.1.0 里程碑与实测记录

- **当前 `0.1` 轨道近期演进摘要**（精确版本锁定见 [`channels/0.1.json`](./channels/0.1.json)）：
  - **`0.1.5` 补丁：新增 Google Antigravity 原生插件与 `G0–G5` 全矩阵基准验证（[0.1.5 发布说明](./docs/releases/0.1.5.md) · [English](./docs/releases/0.1.5.en.md)）**：正式发布第五款官方原生宿主插件 [`mindie-agent-agy v0.1.0`](https://github.com/mindie-agent/mindie-agent-agy)（Google Antigravity），完成与全部 7 大共享组件（`knowledge 0.13.7`、`remote-dev 0.11.2`、`coordinator 0.7.0`、`profiler 0.5.3`、`sim 0.8.1`、`npu-top 0.3.0`、`diagnostics 0.5.4`）的双向契约对齐、原生工具别名映射、`AGY_CONVERSATION_ID` 会话租约透传与 Brain Transcript 双层脱敏采集；同时在完全无剧透的真实口语化报障语料（一句话模型+配置+报错现象 + 原始堆栈/日志路径）上完成 DSH（`deepseek-flash` / `max`）与 Codex（`gpt-6.1-sol` / `xhigh`）的 `G0–G5` 全矩阵基准验证：L2 主矩阵（48 场）通过率从 `G0/G1` 的 **`12.5% (2/16)` 跃升至 `G2` `50.0% (8/16，4.0 倍提升)`** 且通过任务耗时下降 **`21.2%–47.1%`**（`vllm-ascend` 核心任务 `0.0% → 37.5%`/DSH `50.0%`，四大组件任务 `25.0% → 62.5%`/Codex `75.0%`）；L3 昇腾真机 `G1` (`remote-dev`) 打通真机闭环（`0.0 → 1.0`）；`G3` 跨任务蒸馏飞轮在 DSH Partial RoPE 上实现 **`0.0 → 1.0` 破零**、在 Codex SFA MTP 上减少 **`58.5%–63.4%` 工具调用与 `-19.8%` 耗时**；`G4` RSI 探索在 Codex 上实现 `dsv4-sparse-mla` **`0.0 → 1.0` (`-27.8%`)** 与 `triton-spatial-norm` **`-30.9%` 提速**；`G5` 连续 5 轮演进（`82 → 83 → 84` units）验证同子域连续蒸馏正向/负向边界后回测前序任务**零退化且耗时再降 `-19.8%`（`153.29s`）**。
  - **`0.1.4` 补丁与核心组件升级（[0.1.4 发布说明](./docs/releases/0.1.4.md) · [English](./docs/releases/0.1.4.en.md) · [自动升级验收记录](./docs/releases/0.1.4/automatic-update-acceptance.json) · [知识检索与双宿主收敛实测](./docs/audits/2026-10-29-knowledge-p0.md)）**：交付四端按信息缺口按需检索、统一精读预算、准确前置引用与受管组件绑定自动升级；在自然语言重写后的 `mindie-bench` 测试语料上，**DSH（`deepseek-flash` / `max`）与 Codex（`gpt-6.1-sol` / `xhigh`）在单点 SFA、双点 DSpark 与复杂 Profiler 归因任务上实现 `6/6` 全部自然收敛通过**（DSH 复杂任务从 50 轮预算耗尽收敛至 **17 轮 / `67.05s`**，Codex 从 `410.30s` 降至 **16 轮 / `132.97s`**）；同时同步独立组件正式版 `mindie-sim v0.8.1`（五层统一因果建模、4D 效率拆解、30ms SLA 硬件配比求解，280 个 Decode + 15 个 Prefill 真实用例收敛）、`mindie-profiler v0.5.3`（`mindie-model-structure/1` 模型结构对齐与 Decode 自动切分，856 例 DSH 集群回放 / 561 例盲测集 98.25% 误差 `<= 15%`）与 `remote-dev v0.11.2`。
  - **`0.1.3` / `0.1.2` / `0.1.1` 补丁记录**：[**0.1.3**](./docs/releases/0.1.3.md) 统一四端三服务 MCP 注册（`knowledge`、`remote`、`components`）；[**0.1.2**](./docs/releases/0.1.2.md) 交付跨进程共享用户私有 SSH 凭据与密钥维护（[SSH 验收记录](./docs/releases/0.1.2/ssh-auth-acceptance.json)）；[**0.1.1**](./docs/releases/0.1.1.md) 交付按会话显式 `/mindie-agent` 激活、整包 Token 预算估算、双 Die 物理放置及 `G5` 开发试点报告（[试点报告](./docs/releases/0.1.1/benchmark-pilot.md) · [原生更新验收](./docs/releases/0.1.1/native-update-acceptance.json)）。

> **2026-10-29 行为级判分器加固与历史归档零模型复判说明（[完整审计与复判报告](./docs/audits/2026-10-23-mindie-bench-integrity.md)）**：
> 针对此前审计发现的静态源码匹配判分问题，`mindie-bench` 已完成全部 **20 个基准任务的真实子进程行为级 Oracle 加固**，并通过 **109 项三态及顶层辅助函数/类变体实跑校验**（`base` 必败、`negative_control` 必败、`gold` 必过，`all_three_state_and_helpers_passed = true`）。在不重跑模型、完全保留原始耗时与 Token 账本的前提下，对 `agent-trials-109.json` 中具备候选补丁的 **74 轮主实验 Trial** 进行了零模型行为级重判：
> - **复判汇总**：49 轮原通过 Trial 经真实行为执行确认通过（`completed_pass -> 1.0`），5 轮原误判失败 + 1 轮 `unknown` Trial 经行为执行恢复通过，合计 **55 轮通过行为级验收（`reward = 1.0`）**、**18 轮未通过行为断言（`reward = 0.0`）**、**1 轮因仅支持 NPU 执行记为 `unmeasured`**。
> - **证据分层边界**：20 个任务的验证范围严格按实际执行底座标注——包含 8 个 CPU 行为复现任务（`cpu_behavior`）、4 个受控组件夹具任务（`controlled_offline_fixture`）、4 个 G4 算子融合张量与消融契约任务（`controlled_cpu_tensor_and_ablation_contract`）、2 个 CPU RoPE 张量精度任务（`cpu_tensor_correctness`）以及 2 个真实昇腾 NPU RoPE 精度任务（`npu_tensor_correctness`）。下方保留 `v0.1.0` 发布时的原始实验记录供对照追溯。

最近一次特性里程碑版本为 **[`v0.1.0`](./docs/releases/0.1.0.md)**（[English Release Notes](./docs/releases/0.1.0.en.md) · [18 任务全量基准报告](./docs/releases/0.1.0/value-results.md) · [109 轮真实 Trial 脱敏凭据 (`agent-trials-109.json`)](./docs/releases/0.1.0/agent-trials-109.json) · [组件基准凭据 (`value-results.json`)](./docs/releases/0.1.0/value-results.json) · [作者自述与架构演进哲学](./docs/releases/0.1.0/design-philosophy.md) · [`channels/0.1.json`](./channels/0.1.json)）。`v0.1.0` 标志着 MindIE Agent 从 `0.0.1` 原型演进为面向昇腾（Ascend NPU）AI Infra 的智能研发与验证底座，涵盖 18 个工程任务、`109` 轮主 Trial、全部 7 大共享组件与 3 大硬件平台 × 4 大宿主检查：

1. **`mindie-bench` 双模型（`codex + home/codex/gpt-6.1-sol (xhigh)` & `dsh + deepseek-flash (max)`）18 个真实工程任务、`109` 轮端到端受控消融实测（`G0 → G1 → G2 → G3 → G4`，含 `Ascend950DT` 真实 NPU）**：
   - **`G0 → G1 → G2`（`remote-dev` + `knowledge` L1–L4 渐进式披露）**：在跨模块排障与模糊报障任务上端到端交付提速 **`1.80x – 2.77x`**，Token 消耗降低 **`15% – 76%`**，单任务知识读取开销严格受控在 **`4,814–5,599` tokens（`< 8,000` 上限）**（注：当本地单文件报错堆栈本身已完全自包含时，额外 `knowledge_query` 回合可能带来负向耗时增量，完整正负样本分布见 [`value-results.md`](./docs/releases/0.1.0/value-results.md)）；
   - **`G2 → G3`（`Stop` 采集 + `C6` 结构化经验蒸馏飞轮）**：在无源码黑盒 `.so` 的同族变体迁移任务（`rotary_dim=64 → 32`）上，将 `codex (xhigh)` 的一次解出率从 **`0% (0/3, G0/G1/G2) → 100% (1/1, G3)`**（`codex xhigh` L3 真机提速 **`3.44x`**；`dsh` 在 `G0–G3` 均通过并将 L3 交付耗时从 `217.5s` 降至 `171.9s`）；
   - **`G2 → G4`（`mode="reuse" → mode="explore"` 开放探索 + 留一法消融）**：在 2 类底层算子难题 × L2/L3 双层级 = 4 个算子融合任务 × 2 套模型上（注入 `knowledge_gradient = "near_exact"` 因子图探索引导）实现 **`G0 (0/8, 0%) / G2 (0/8, 0%) → G4 (8/8, 100%)`**。
   - **实验边界与可复现说明**：本轮 `109` 轮实验为作者团队构建的受控消融基准（单配置点 `repetitions = 1` 定向对比；`home/codex/gpt-6.1-sol` 与 `deepseek-flash` 为内部计量网关别名，外部复现可直接绑定公开 API 端点），所有 109 轮主实验与 55 轮补充/重试原始记录均已完整公开于 [`agent-trials-109.json`](./docs/releases/0.1.0/agent-trials-109.json)，2026-10-29 行为级复判账本见 [`docs/audits/2026-10-23-mindie-bench-integrity.md`](./docs/audits/2026-10-23-mindie-bench-integrity.md)。
2. **7 大共享组件真实 Agent 闭环与组件级实测（`profiler`、`sim`、`diagnostics`、`coordinator`、`npu-top`、`remote-dev`、`knowledge`）**：
   - 在 4 个专属组件真实修复任务上，双模型成功率均从 **`75% (3/4) → 100% (4/4)`**，总耗时降低 **`-17.1% ~ -33.8%`**、输出 Token 节省 **`-25.2% ~ -34.1%`**：

| 组件 / 评测场景 | 版本 | 实测核心收益与结论 |
| --- | --- | --- |
| **⚡ `remote-dev` 远端容器与长任务执行** | `v0.10.4` → `v0.11.2` | L2/L3 实机端到端评测中，`dspark-mrv2` / `l3-dspark-mrv2` 等任务较裸宿主提速 **`1.55x – 2.06x`**，`quarot` 量化修复 **`3/3` 全通**；`v0.11.2` 支持跨进程共享 `~/.mindie/ssh/id_ed25519` 凭据回退、公钥维护与破坏性命令安全拦截门禁 |
| **🎯 `coordinator` 多 Agent 并发防撞车与 A5 预检** | `v0.6.2` → `v0.7.0` | 真实 Agent 多 Die 租约修复任务交付提速 **`1.17x – 2.08x`**；双 Agent 并发抢占压测端口冲突 **`3 → 0`**、重复选卡 **`3 → 0`**，释放后平均 **`1.9 ms`** 完成接管；支持昇腾 A2/A3 双 Die/A5 拓扑、HCCL/RoCE 预检、单 Die 显存租约预算与并发编译槽位控制 |
| **🔬 `profiler` 慢卡/慢链路定位与模型结构对齐** | `v0.5.0` → `v0.5.3` | 在真实 Agent `msprof` 排障任务中将双模型解出率从 **`0% (G0) → 100% (G2)`**（耗时缩短 **`-29.7% ~ -34.6%`**）；就地只读解析（`~7.6 ms`）**100% 区分慢链路（`Comm`）与慢卡（`Attention`）**，峰值显存归因 **`99%`**；`v0.5.3` 新增 `analyze_profiling --structure` 三态拓扑对齐（`aligned / declared_only / unattributed_observed`）、`auto_segment_decode_forwards` Decode 自动切分与 856 例集群回放验证 |
| **📐 `sim` 五层因果性能建模与 SLA 配比推演** | `v0.7.0` → `v0.8.1` | `v0.1.0` 任务中双模型 **100% 调用 `mindie_sim`** 完成算子融合筛查与 A3 Qwen2.5-7B TPOT 预测（**`-4.14%`**）；`v0.8.1` 统一建模 `DP × TP × EP × PP × DCP / DSA-CP / PCP` 与 PD 分离，输出 4D 效率拆解（`Cube_MFU / Vec_MFU / MBU / Link_Util / CV_Overlap`）与 30ms SLA 硬件缩放推演，在 **280 个 Decode + 15 个 Prefill 用例**上收敛并在 **856 例 DSH 集群 / 561 例盲测集**上达到 **98.25% `<= 15%`** 误差（见[仿真系统设计](./docs/simulation-system.md)） |
| **📊 `npu-top` & 🛡️ `diagnostics` 可观测与确定性分诊** | `v0.3.0` / `v0.5.4` | 真实 Agent 8 卡级联 `plog` 分诊任务交付提速 **`1.31x – 1.82x`**、输出 Token 减少 **`-34.2% ~ -37.6%`**，**100% 锁定根因 `Rank 3`（`aicore_memory_or_tiling`）并分离衍生超时 `Rank 7`**；`npu-top` 支持 A2/A3/A5 与 `~/.mindie/ssh` 回退，`diagnostics` 支持有界 2 次外发对账重试 |
| **🧠 `knowledge` 渐进式披露、Token 预算与闭环飞轮** | `v0.13.0` → `v0.13.7` | 7 大昇腾公共知识库（`450` 个 `L1–L4` 单元）全量就绪；支持批量 `refs` 精读与共享 `known_refs` / `token_budget` 预算，保留 `rejected_history` 与 `affected_components` 溯源，单任务知识读取受控于 **`4,814–5,599` tokens（`< 8,000` 上限）**，将 `G3` 黑盒与 `G4` `mode="explore"` 融合难题解出率推升至 **`100%`** |

3. **三端（`macOS` / `Windows WSL2` / `Windows 11 PowerShell`）× 四插件全流程验收**：
   - 在三大操作系统硬件平台与四个原生宿主插件（Claude Code / OpenAI Codex / Kimi Code / DeepSeek Harness）上完成全量回归与安装闭环验收，累计通过 **`15,595+` 项测试（`0 failed`）**。

---

## 📚 文档中心

完整技术文档索引请参阅 **[`docs/README.md`](./docs/README.md)**（**[English Documentation Index](./docs/README.en.md)**）：

| 文档主题 | 中文 | English |
| --- | --- | --- |
| **`v0.1.5` 补丁发布说明：新增 Google Antigravity 插件与 `G0–G5` 全矩阵基准（当前版本）** | [docs/releases/0.1.5.md](./docs/releases/0.1.5.md) | [docs/releases/0.1.5.en.md](./docs/releases/0.1.5.en.md) |
| **`v0.1.4` 补丁发布说明：按需知识检索与受管组件更新** | [docs/releases/0.1.4.md](./docs/releases/0.1.4.md) | [docs/releases/0.1.4.en.md](./docs/releases/0.1.4.en.md) |
| **`v0.1.3` 补丁发布说明：四宿主 MCP 工具面完备与 `profiler 0.5.1`** | [docs/releases/0.1.3.md](./docs/releases/0.1.3.md) | [docs/releases/0.1.3.en.md](./docs/releases/0.1.3.en.md) |
| **`v0.1.2` 补丁发布说明与 SSH 认证验收** | [docs/releases/0.1.2.md](./docs/releases/0.1.2.md) · [认证验收](./docs/releases/0.1.2/ssh-auth-acceptance.json) | [docs/releases/0.1.2.en.md](./docs/releases/0.1.2.en.md) · [SSH Acceptance](./docs/releases/0.1.2/ssh-auth-acceptance.json) |
| **`v0.1.1` 补丁发布说明与开发试点报告** | [docs/releases/0.1.1.md](./docs/releases/0.1.1.md) · [试点报告](./docs/releases/0.1.1/benchmark-pilot.md) | [docs/releases/0.1.1.en.md](./docs/releases/0.1.1.en.md) · [Pilot Report](./docs/releases/0.1.1/benchmark-pilot.en.md) |
| **`v0.1.0` 正式版发布说明与真实任务全量基准** | [docs/releases/0.1.0.md](./docs/releases/0.1.0.md) · [实测报告](./docs/releases/0.1.0/value-results.md) | [docs/releases/0.1.0.en.md](./docs/releases/0.1.0.en.md) · [Benchmark Report](./docs/releases/0.1.0/value-results.md) |
| **`v0.1.0` 作者自述与架构演进哲学（Author's Note）** | [docs/releases/0.1.0/design-philosophy.md](./docs/releases/0.1.0/design-philosophy.md) | [docs/releases/0.1.0/design-philosophy.en.md](./docs/releases/0.1.0/design-philosophy.en.md) |
| **`v0.0.3` 版本发布与实测基准报告** | [docs/releases/0.0.3.md](./docs/releases/0.0.3.md) | [docs/releases/0.0.3.en.md](./docs/releases/0.0.3.en.md) |
| **`v0.0.2` 版本发布与实测基准报告** | [docs/releases/0.0.2.md](./docs/releases/0.0.2.md) | [docs/releases/0.0.2.en.md](./docs/releases/0.0.2.en.md) |
| **系统架构与组件边界** | [docs/architecture.md](./docs/architecture.md) | [docs/architecture.en.md](./docs/architecture.en.md) |
| **工程设计原则与演进准则** | [docs/design-principles.md](./docs/design-principles.md) | [docs/design-principles.en.md](./docs/design-principles.en.md) |
| **参与贡献指南（Agent-First 贡献工作流与 PR 自检门禁）** | [CONTRIBUTING.md](./CONTRIBUTING.md) | [CONTRIBUTING.en.md](./CONTRIBUTING.en.md) |
| **知识与经验闭环设计** | [docs/knowledge-system.md](./docs/knowledge-system.md) | [docs/knowledge-system.en.md](./docs/knowledge-system.en.md) |
| **上下文分层、经验演化与开放探索设计** | [docs/knowledge-context-and-exploration.md](./docs/knowledge-context-and-exploration.md) | [docs/knowledge-context-and-exploration.en.md](./docs/knowledge-context-and-exploration.en.md) |
| **面向 Agent 的 Profiler 系统设计（`mindie-profiler`）** | [docs/profiler-system.md](./docs/profiler-system.md) | [docs/profiler-system.en.md](./docs/profiler-system.en.md) |
| **面向 Agent 的通用性能建模系统（`mindie-sim`）** | [docs/simulation-system.md](./docs/simulation-system.md) | — |
| **Profiler 与 Sim 的结构复用与实测对齐契约** | [docs/profiler-sim-structure.md](./docs/profiler-sim-structure.md) | — |
| **2026-10-29 基准判分器加固与历史归档复判报告** | [docs/audits/2026-10-23-mindie-bench-integrity.md](./docs/audits/2026-10-23-mindie-bench-integrity.md) | — |
| **核心能力落地与知识持续演进设计** | [docs/core-implementation-and-geak-evolution-design.md](./docs/core-implementation-and-geak-evolution-design.md) | — |
| **Harness 边界、授权与生命周期** | [docs/harness-boundary-and-lifecycle.md](./docs/harness-boundary-and-lifecycle.md) | [docs/harness-boundary-and-lifecycle.en.md](./docs/harness-boundary-and-lifecycle.en.md) |
| **原生运行时复用设计** | [docs/native-runtime-reuse.md](./docs/native-runtime-reuse.md) | [docs/native-runtime-reuse.en.md](./docs/native-runtime-reuse.en.md) |
| **发布兼容、配套发行与静默更新** | [docs/release-compatibility-and-update.md](./docs/release-compatibility-and-update.md) | [docs/release-compatibility-and-update.en.md](./docs/release-compatibility-and-update.en.md) |
| **结构化诊断与故障自动上报** | [docs/diagnostics-and-reporting.md](./docs/diagnostics-and-reporting.md) | [docs/diagnostics-and-reporting.en.md](./docs/diagnostics-and-reporting.en.md) |
| **分级测试体系与用例设计规范** | [docs/testing-architecture.md](./docs/testing-architecture.md) | [docs/testing-architecture.en.md](./docs/testing-architecture.en.md) |
| **L1–L4 知识与系统能力分级测试方案** | [docs/knowledge-tiered-testing-plan.md](./docs/knowledge-tiered-testing-plan.md) | — |
| **演进路线与下一步重点** | [docs/next-steps.md](./docs/next-steps.md) | [docs/next-steps.en.md](./docs/next-steps.en.md) |
| **`v0.0.1` 首发版本发布记录** | [docs/releases/0.0.1.md](./docs/releases/0.0.1.md) | [docs/releases/0.0.1.en.md](./docs/releases/0.0.1.en.md) |

---

## 📊 开源仓库与下载统计

<p align="center">
  <a href="https://github.com/mindie-agent/mindie-agent/blob/telemetry-data/README.md">
    <img src="https://raw.githubusercontent.com/mindie-agent/mindie-agent/telemetry-data/dashboard.zh.svg" alt="MindIE Agent 开源仓库与下载统计" width="100%">
  </a>
</p>

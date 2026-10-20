<p align="center">
  <img src="assets/brand/mindie-agent-logo.png" alt="MindIE Agent logo" width="128" height="128">
</p>

<h1 align="center">MindIE Agent</h1>

<p align="center">
  <strong>为原生编程 Agent 提供昇腾领域知识、远端 NPU 执行与可追溯的工程经验</strong>
</p>

<p align="center">
  <a href="https://github.com/mindie-agent/mindie-agent/blob/main/docs/releases/0.0.2.md"><img src="https://img.shields.io/badge/release-v0.0.2-7045F5.svg" alt="Release v0.0.2"></a>
  <a href="https://github.com/mindie-agent/mindie-agent-cc"><img src="https://img.shields.io/badge/Claude_Code-Plugin-D97757.svg" alt="Claude Code Plugin"></a>
  <a href="https://github.com/mindie-agent/mindie-agent-codex"><img src="https://img.shields.io/badge/OpenAI_Codex-Plugin-10A37F.svg" alt="OpenAI Codex Plugin"></a>
  <a href="https://github.com/mindie-agent/mindie-agent-kimi"><img src="https://img.shields.io/badge/Kimi_Code-Plugin-2563EB.svg" alt="Kimi Code Plugin"></a>
  <a href="https://github.com/mindie-agent/mindie-agent-dsh"><img src="https://img.shields.io/badge/DeepSeek_Harness-Plugin-0EA5E9.svg" alt="DeepSeek Harness Plugin"></a>
  <a href="https://github.com/mindie-agent/awesome-mindie-skills"><img src="https://img.shields.io/badge/Ascend_AI_Infra-vLLM--Ascend_%7C_AscendC_%7C_Triton-0F766E.svg" alt="Ascend NPU AI Infra"></a>
</p>

<p align="center">
  <strong>中文</strong> · <a href="./README.en.md">English</a> · <a href="#-一句话无感安装">⚡ 一句话安装</a> · <a href="#-为什么选择-mindie-agent">✨ 核心能力</a> · <a href="#️-架构全景与经验飞轮">🏗️ 架构全景</a> · <a href="#-装好之后怎么用">🔥 实战用法</a> · <a href="#-组件与仓库生态">📦 仓库生态</a> · <a href="#-当前版本与实测效果v002-release">🚀 v0.0.2 实测</a> · <a href="./docs/README.md">📚 文档中心</a>
</p>

---

## ⚡ 一句话无感安装

### 方式一：直接甩链接给你的 Agent（最推荐 ✨）

你不需要记住任何安装命令。打开你正在使用的 **Claude Code**、**OpenAI Codex CLI**、**Kimi Code** 或 **DeepSeek Harness**，直接复制并发送下面这句话：

```text
帮我安装一下这个 https://github.com/mindie-agent/mindie-agent
```

Agent 读取本页面后，会自动校验 **`gh`（GitHub CLI）稳定交互通道**、识别自身宿主环境并执行下方的**自动安装协议**，完成插件注册与运行时初始化。安装不要求 Star 或 Fork。

<details>
<summary>🤖 <b>AI Agent 自动安装执行协议（点击展开 / Agent 读取本页时会自动解析执行）</b></summary>

> **给 AI Agent 的指令**：如果用户要求你安装 `mindie-agent`，请不要让用户手动翻文档，直接按以下四步在终端依次执行：
>
> #### 第一步：检查基础工具与 `gh` GitHub 交互通道（硬性前置指标）
> **稳定的 GitHub 交互通道（已安装并登录 `gh` CLI）是 MindIE Agent 的硬性指标**——插件版本拉取、锁定发行版校验、`knowledge-vllm-ascend` 知识源同步、经验闭环自动提交 PR（底层通过 `gh api` 与 `!gh auth git-credential` 驱动）以及组件故障上报均依赖该通道。请先在终端运行：
> ```bash
> git --version && uv --version && gh --version
> gh auth status
> GH_USER=$(gh api user --jq .login) && echo "GitHub channel verified for account: $GH_USER"
> gh auth setup-git
> ```
> - **门禁要求（严禁跳过或静默忽略；仅安装 DSH `0.0.2` 且不启用社区贡献时可跳过 `gh` 门禁，但仍需 `git` 与 `uv`）**：
>   - 若未安装 `gh`：请先按宿主系统协助安装（macOS：`brew install gh`；Windows：`winget install --id GitHub.cli`；Ubuntu / WSL：`sudo apt update && sudo apt install -y gh`）。
>   - 若 `gh auth status` 未登录、Token 失效或 `gh api user` 无法连通 GitHub：**请勿继续执行后续步骤**，立即引导用户完成 `gh auth login`（或配置有效的 `GH_TOKEN`）并运行 `gh auth setup-git`，直至 `gh api user --jq .login` 稳定返回当前 GitHub 账号名。
>
> #### 第二步：保留用户授权，按需准备贡献目标
> 安装只注册当前宿主所需的插件，不要求 Star 或 Fork。Star 由用户自行选择。
>
> 社区贡献默认关闭。用户明确开启目标知识库 `<owner/repo>` 的贡献后，才创建或复用该知识库的个人 Fork，并绑定 `<GH_USER>/<repo>` 作为推送目标。不要因安装而 Fork 主仓、插件仓或所有领域仓库。
>
> #### 第三步：识别你所在的宿主客户端并安装对应插件
> 根据你自身的运行环境选择**唯一匹配**的分支执行（若不确定，请检查 `claude --version`、`codex --version`、`kimi --version` 或 `dsh --version`）：
>
> - **分支 A — 如果你是 Claude Code（或检测到 `CLAUDECODE` 环境变量 / 用户使用 `claude`）**：
>   ```bash
>   claude plugin marketplace add "https://github.com/mindie-agent/mindie-agent-cc.git#v0.0.2"
>   claude plugin install mindie-agent@mindie-agent-cc --scope user
>   claude --init-only
>   claude plugin list --json
>   claude mcp list
>   ```
>   *验证标准*：`claude plugin list --json` 显示 `mindie-agent@mindie-agent-cc`（`0.0.2`）已启用，且 `claude mcp list` 中 `mindie-knowledge` 与 `remote-dev` 均显示 `Connected`。
>
> - **分支 B — 如果你是 OpenAI Codex CLI（或检测到 `CODEX_CI` / `CODEX_THREAD_ID` / 用户使用 `codex`）**：
>   ```bash
>   codex plugin marketplace add https://github.com/mindie-agent/mindie-agent-codex.git --ref v0.0.2
>   codex plugin add mindie-agent@mindie-agent --json
>   codex plugin list --json
>   ```
>   *验证标准*：`codex plugin list --json` 显示 `mindie-agent@mindie-agent`（`0.0.2`）已启用。提醒用户开启新会话即可自动触发 `SessionStart` 构建锁定运行时。
>
> - **分支 C — 如果你是 Kimi Code CLI（或检测到 `KIMI_CODE_HOME` / 用户使用 `kimi`）**：
>   ```bash
>   MINDIE_TMP="${TMPDIR:-/tmp}/mindie-agent-kimi-install"
>   rm -rf "$MINDIE_TMP"
>   git clone --depth 1 --branch v0.0.2 https://github.com/mindie-agent/mindie-agent-kimi.git "$MINDIE_TMP"
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
>   git clone --depth 1 --branch v0.0.2 https://github.com/mindie-agent/mindie-agent-dsh.git "$MINDIE_TMP"
>   uv run --quiet --no-project --python 3.11 "$MINDIE_TMP/scripts/setup.py"
>   ```
>   随后在 DSH Web 的 **Plugins** 页面安装并启用：
>   ```text
>   git+https://github.com/mindie-agent/mindie-agent-dsh.git#v0.0.2
>   ```
>   如果当前就在 DSH 会话内且具备 `plugin_manager` 工具，可用它完成同一步骤：
>   ```text
>   plugin_manager(action="install_bundle", target="git+https://github.com/mindie-agent/mindie-agent-dsh.git#v0.0.2")
>   ```
>   *验证标准*：`setup.py` 最终 JSON 中 `status` 为 `ready`、`components` 为 `knowledge 0.12.2 / remote-dev 0.10.1 / diagnostics 0.4.3`，且 `knowledge.status` 为 `ready`；Plugins 页面显示 `mindie-agent-dsh` 已启用。提醒用户打开**新会话**后使用 `/mindie-agent`。
>   *说明*：DSH `0.0.2` 只做只读知识与 `remote-dev`，不启用社区贡献与故障上报，因此该分支**不依赖 `gh`**。
>
> - **分支 E — 如果你是 Cursor / 其他通用 MCP 客户端（仅需 SSH 远端 NPU 开发底座 `remote-dev`）**：
>   在项目的 `.mcp.json`（或 `.cursor/mcp.json`）中写入 `remote-dev` 服务：
>   ```json
>   {
>     "mcpServers": {
>       "remote-dev": {
>         "type": "stdio",
>         "command": "uvx",
>         "args": ["--from", "git+https://github.com/mindie-agent/remote-dev@v0.10.1", "remote-dev", "server"]
>       }
>     }
>   }
>   ```
>
> #### 第四步：向用户汇报安装结果
> 安装完成后，向用户简要汇报：
> 1. 适用时已验证的 `gh` GitHub 交互通道及认证账号；
> 2. 已安装的客户端插件名称、版本与验证结果；
> 3. 说明日常开发只需通过单一入口 `/mindie-agent` 唤醒昇腾领域知识与 Skill，而远端 NPU 工具（`remote-dev`）在日常对话中默认自动触发；
> 4. 说明**社区知识贡献**与**产品故障自动上报**默认均处于关闭状态（Opt-in）；若后续用户开启社区知识贡献，Agent 会自动按需 Fork 对应的目标知识库（如 `mindie-agent/knowledge-vllm-ascend` -> `$GH_USER/knowledge-vllm-ascend`）并完成绑定。

</details>

### 方式二：人类终端手动一行安装

> **硬性前置指标**：请确保本机已安装 `git`、`uv` 以及已登录的 **`gh`（GitHub CLI）**。下表 DSH `0.0.2` 不启用贡献与上报，因此不依赖 `gh`。安装前可先在终端运行下方一行命令，完成 **GitHub 通道校验**：
> ```bash
> gh auth status && gh auth setup-git
> ```

随后按你使用的客户端复制一行即可完成插件安装：

| 客户端 | 一键安装命令 | 插件仓库 |
| --- | --- | --- |
| **Claude Code** | `claude plugin marketplace add "https://github.com/mindie-agent/mindie-agent-cc.git#v0.0.2" && claude plugin install mindie-agent@mindie-agent-cc --scope user && claude --init-only` | [`mindie-agent-cc`](https://github.com/mindie-agent/mindie-agent-cc) |
| **OpenAI Codex CLI** | `codex plugin marketplace add https://github.com/mindie-agent/mindie-agent-codex.git --ref v0.0.2 && codex plugin add mindie-agent@mindie-agent --json` | [`mindie-agent-codex`](https://github.com/mindie-agent/mindie-agent-codex) |
| **Kimi Code CLI** | `git clone --branch v0.0.2 https://github.com/mindie-agent/mindie-agent-kimi.git && cd mindie-agent-kimi && python3 scripts/setup.py` | [`mindie-agent-kimi`](https://github.com/mindie-agent/mindie-agent-kimi) |
| **DeepSeek Harness (DSH)** | `git clone --depth 1 --branch v0.0.2 https://github.com/mindie-agent/mindie-agent-dsh.git /tmp/mindie-agent-dsh && uv run --quiet --no-project --python 3.11 /tmp/mindie-agent-dsh/scripts/setup.py`，随后在 DSH **Plugins** 页面启用 `git+https://github.com/mindie-agent/mindie-agent-dsh.git#v0.0.2` | [`mindie-agent-dsh`](https://github.com/mindie-agent/mindie-agent-dsh) |
| **仅安装 NPU 监控台 (`npu-top`)** | `uvx --from "https://github.com/mindie-agent/npu-top/releases/download/v0.1.9/npu_top-0.1.9-py3-none-any.whl" npu-top serve` | [`npu-top`](https://github.com/mindie-agent/npu-top) |

---

## ✨ 为什么选择 MindIE Agent？

MindIE Agent 在你已有的 Claude Code、Codex、Kimi Code 或 DSH 会话中提供领域知识和远端开发工具。`0.0.3` 的建设范围聚焦 **vLLM-Ascend 与算子两个领域**，覆盖模型 0day 开发、固定 case 的模型或算子性能优化、问题定位三个场景。实现与验收进展见[系统架构](./docs/architecture.md)和下方发布记录。

| 能力 | 帮你完成的工作 |
| --- | --- |
| **带适用条件的领域知识** | 按框架版本、硬件和输入条件检索规则、步骤、工作流与代码变换，精读具体修订并追溯来源；缺失前提不会被自动视作匹配 |
| **远端 NPU 开发与验证** | 通过 [`remote-dev`](https://github.com/mindie-agent/remote-dev) 在 SSH 主机和容器中读写文件、应用补丁、执行命令、管理长任务与读取产物 |
| **实测剖析与四层理论仿真** | 通过 [`profiler`](https://github.com/mindie-agent/profiler) 原地解析昇腾 Profiling 产物并对比跨 Run 收益，通过 [`sim`](https://github.com/mindie-agent/sim) 开展硬件/传输/算子微阶段/子图融合/整网并行四层边界求解 |
| **资源协调与结构化诊断** | 按需使用 [`coordinator`](https://github.com/mindie-agent/coordinator) 协调设备和端口租约，用 [`npu-top`](https://github.com/mindie-agent/npu-top) 观察设备状态，用 [`diagnostics`](https://github.com/mindie-agent/diagnostics) 分析运行记录；观测结果与任务正确性分别判断 |
| **可追溯的经验沉淀** | 在授权范围内采集并脱敏当前任务材料；从选定证据提炼新知识，审核后入库。公开贡献另外受贡献配置控制 |

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
  end

  subgraph Adapters["🔌 原生插件薄适配层 (Thin Harness Plugins)"]
    P_CC["mindie-agent-cc"]
    P_Codex["mindie-agent-codex"]
    P_Kimi["mindie-agent-kimi"]
    P_DSH["mindie-agent-dsh"]
  end

  subgraph Core["⚙️ 共享运行时组件底座 (Shared Runtime Components)"]
    Knowledge["🧠 mindie-knowledge<br/>分级知识 · 条件检索 · 精确引用与反馈"]
    Coord["🎯 coordinator<br/>升级版 SSH & 远端昇腾环境管理 · 容器开通/绑定 · NPU 探测与租约队列"]
    RemoteDev["⚡ remote-dev<br/>SSH 文件与命令 · 容器直连 · 受管作业"]
    Profiler["🔬 mindie-profiler<br/>昇腾 Profiling 原地解析 · Host-Device 关联 · 跨 Run 对比"]
    Sim["📐 mindie-sim<br/>四层硬件/微阶段/子图/整网仿真 · 全路径传输边界求解"]
    NpuTop["📊 npu-top<br/>面向人类的 Web 实时看板 · 90 天热力图 (共享 machines.json)"]
    Diag["🛡️ mindie-diagnostics<br/>有界 JSONL 轮转日志 · 严密白名单故障上报"]
  end

  subgraph Remote["🖥️ 远端昇腾集群与知识源 (Ascend Fleet & Canonical Feed)"]
    Feed[("📚 vLLM-Ascend / operators<br/>领域知识、来源与版本反馈")]
    Cluster[("🚀 远端昇腾 NPU 主机与 Docker 容器")]
  end

  CC --> P_CC
  Codex --> P_Codex
  Kimi --> P_Kimi
  DSH --> P_DSH

  P_CC & P_Codex & P_Kimi & P_DSH --> Knowledge & RemoteDev & Diag & Profiler & Sim
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
  participant Agent as Coding Agent (Claude / Codex / Kimi / DSH)
  participant Know as mindie-knowledge (本地服务)
  participant NPU as remote-dev (远端昇腾容器)
  participant Repo as 公共工程知识库 (knowledge-vllm-ascend 等)

  Dev->>Agent: 输入 /mindie-agent + 研发需求（特性设计 / 算子开发 / 测试构建 / 调优排障）
  Agent->>Know: 1. 携带已知环境检索 (query)，按精确引用读取 (explain)
  Agent->>NPU: 2. 在选定容器内编写代码、同步补丁并运行测试
  NPU-->>Agent: 返回编译、正确性与性能结果以及日志引用
  Agent-->>Dev: 3. 交付实现和实际验证范围，可提交具体修订的有用性反馈
  Note over Agent,Know: 采集取决于当前安装配置与项目授权
  Agent->>Know: 4. 生命周期事件采集公开投影，确定性脱敏并保存材料
  Agent->>Know: 5. 显式选择证据，提炼并审核新的知识单元
  Note over Know,Repo: 公开贡献另需开启并配置目标仓库
  Know->>Repo: 6. 发布已准入单元；远端合并与客户端同步分别确认
```

---

## 🔥 装好之后怎么用？（触发方式与使用示例）

MindIE Agent 的核心交互理念是**极简易用与渐进式披露（Progressive Disclosure）**——对用户而言，**从头到尾只需要知道 `/mindie-agent` 这一个入口**，不需要记忆任何复杂的子命令（如 `:init`、`:status` 等），底层上下文只在 Agent 需要时按需向 Agent 渐进式披露：

| 能力模块 | 触发方式 | 极简使用方式说明 |
| --- | --- | --- |
| **🧠 昇腾 Infra 知识库、经验与 Skill 系统**<br/>（`mindie-knowledge` + 领域 Skills） | **手动触发**<br/>（统一入口 `/mindie-agent`） | 在开展昇腾 AI Infra 方案设计、`vLLM-Ascend` 特性开发、`AscendC` / `Triton` 算子实现、测试验证或性能调优时，直接输入 **`/mindie-agent` + 你的需求描述**（Codex 中也可输入 `$mindie-agent`）。首次配置、查看状态或开关共享也同样只需输入 `/mindie-agent` 加自然语言。 |
| **⚡ 远端昇腾服务器开发与测试**<br/>（`remote-dev` SSH / 容器工具集） | **默认自动触发**<br/>（常驻 MCP，无需斜杠命令） | `remote-dev` 默认处于就绪状态。日常对话中只要提到远端服务器、容器或 NPU 编译/测试命令，Agent 就会**默认自动调用** `remote_read`、`remote_edit`、`remote_bash` 及后台作业工具操作远端环境。 |
| **🔄 研发经验沉淀与社区共建**<br/>（授权采集、脱敏、提炼与审核） | **按配置采集，按证据提炼** | 生命周期事件处理授权范围内的当前任务材料。新知识从显式选定的证据提炼并经审核入库；开启社区贡献后，已准入单元才进入公开发布流程。 |

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

### 1. 产品总入口、评测基准与社区生态

| 仓库 | 定位与核心职责 |
| --- | --- |
| **[`mindie-agent`](https://github.com/mindie-agent/mindie-agent)** *(本仓库)* | 顶层产品入口、整体架构、工程设计原则、跨组件发布兼容契约与正式发行版记录 |
| **[`mindie-bench`](https://github.com/mindie-agent/mindie-bench)** | 独立评测框架与真机基准套件：固定任务与 Oracle、预置准入脚手架（Gate Runner）、隔离宿主运行、组件级基准、跨任务知识复用及端到端总工程成本校验 |
| **[`awesome-mindie-skills`](https://github.com/mindie-agent/awesome-mindie-skills)** | 面向昇腾 NPU AI Infra 全流程的高质量开源 Agent Skills 精选目录（现已覆盖 `vLLM-Ascend`、`AscendC`/`Triton` 算子开发、精度测试与性能调优，持续扩展中） |
| **[`vllm-ascend-workspace`](https://github.com/mindie-agent/vllm-ascend-workspace)** | 轻量可定制的 `vLLM` + `vLLM-Ascend` 本地多任务开发工作区，支持独立 Git Worktree 隔离与 MindIE Agent 集成 |

### 2. 原生客户端插件（Harness Adapters）

| 仓库 | 适用宿主 | 定位与核心职责 |
| --- | --- | --- |
| **[`mindie-agent-cc`](https://github.com/mindie-agent/mindie-agent-cc)** | **Claude Code** | Claude Code 原生插件：生命周期 Hook、MCP 服务桥接与固定运行时管理 |
| **[`mindie-agent-codex`](https://github.com/mindie-agent/mindie-agent-codex)** | **OpenAI Codex CLI** | OpenAI Codex CLI 原生插件：Marketplace 安装、Rollout 增量脱敏采集与服务连续性管理 |
| **[`mindie-agent-kimi`](https://github.com/mindie-agent/mindie-agent-kimi)** | **Kimi Code CLI** | Kimi Code 原生插件：代数原子更新、公开会话投影采集与 MCP 桥接 |
| **[`mindie-agent-dsh`](https://github.com/mindie-agent/mindie-agent-dsh)** | **DeepSeek Harness (DSH)** | DSH 原生组合插件：`/mindie-agent` Skill、知识工具、生命周期桥接与 `remote-dev`；复用宿主插件机制 |

### 3. 共享运行时底座与公共知识库（Shared Runtime Components & Corpora）

| 仓库 | Python 包 / 入口 | 定位与核心职责 |
| --- | --- | --- |
| **[`knowledge`](https://github.com/mindie-agent/knowledge)** | `mindie-knowledge` | 分级单元、条件检索、领域路由、精确版本反馈、授权采集与审核后的内容发布 |
| **[`knowledge-vllm-ascend`](https://github.com/mindie-agent/knowledge-vllm-ascend)** | *(Markdown 知识库)* | `vLLM-Ascend` 领域公共工程知识库：带源码修订绑定、适用条件与实证证据的模型开发、适配与调优知识单元 |
| **[`knowledge-operators`](https://github.com/mindie-agent/knowledge-operators)** | *(Markdown 知识库)* | 昇腾算子领域公共工程知识库：带源码修订绑定、适用条件与实证证据的 `AscendC`、`Triton` 与 CANN 算子实现及调优知识单元 |
| **[`remote-dev`](https://github.com/mindie-agent/remote-dev)** | `remote-dev` | SSH 远端文件与命令工具、容器直连、受管作业、连接池复用与产物传输；可消费 `coordinator` 提供的端点 |
| **[`coordinator`](https://github.com/mindie-agent/coordinator)** | `mindie-coordinator` | 升级版 SSH 与远端昇腾环境管理器：SSH 主机/免密/多机互通、容器绑定与自动开通、Agent 级 NPU/节点/权重挂载探测（`mindie_probe`）、NPU/端口租约仲裁（`mindie_lease`）及本地受管任务调度 |
| **[`profiler`](https://github.com/mindie-agent/profiler)** | `mindie-profiler` / `mindie_profiler` | 独立昇腾实测 Profiling 采集与原地解析组件：受控采集、`inventory / analyze / correlate / compare / sql` 原地只读分析、显存证据提取与跨 Run 事实对比 CLI |
| **[`sim`](https://github.com/mindie-agent/sim)** | `mindie-sim` / `mindie_sim` | 独立昇腾四层仿真与边界求解组件：多型号 A2/A3/A5 `DeviceCapabilityProfile`、7 类全路径 `D2D`/`H2D`/`D2H`/`RH2D`/`RD2H` 传输边界、算子微阶段周期依赖图求解、Phase 0 子图跨算子融合先行分析与整网多维并行推演 |
| **[`npu-top`](https://github.com/mindie-agent/npu-top)** | `npu-top` | 面向人类开发者的昇腾 NPU 可视化监控台：Web 实时看板（`127.0.0.1:8788`）与 90 天有界 SQLite 利用率热力图（直接共享读取 `coordinator` 的 `machines.json`） |
| **[`diagnostics`](https://github.com/mindie-agent/diagnostics)** | `mindie-diagnostics` / `mindie_diagnostics` | 结构化诊断底座：无模型 4×1 MiB 本地日志轮转、离线脱敏诊断包与可选 GitHub Issue 自动上报 |

---

## 🧭 工程设计哲学

MindIE Agent 在持续演进中沉淀了一套严格的 **[工程设计原则](./docs/design-principles.md)**（[English](./docs/design-principles.en.md)），核心理念包括：

- **以完成用户实际目标的总成本衡量效率**：绝不为了防备极小概率异常而给每次日常任务强加繁琐仪式。
- **零心智负担与按需介入**：工具内部消化管理复杂度；Skill 仅提供信息与导航；知识仅作带证据的参考，绝不喧宾夺主。
- **复用成熟机制，按确证缺口自研**：优先复用宿主、OS 与成熟组件能力，替代旧方案时彻底移除重复状态机。
- **诚实可观测，严禁静默降级或隐藏错误**：明确区分“已完成”、“失败”与“外部副作用不确定（`unknown`）”，绝不伪造成功或盲目重放不确定写入。

---

## 🚀 当前版本与实测效果（v0.0.2 Release）

当前正式发布版本为 **[`v0.0.2`](./docs/releases/0.0.2.md)**（[English Release Notes](./docs/releases/0.0.2.en.md) · [详细评测报告](./docs/releases/0.0.2/value-results.md)）。本版本完成主产品与四个原生宿主插件（Claude Code / OpenAI Codex / Kimi Code / DeepSeek Harness）的统一 `0.0.2` 发布，将社区知识共享与产品故障上报收敛为单一授权开关，并完成共享运行时底座的真机 Benchmark 评测：

| 组件 / 评测场景 | 版本 | 实测核心收益与结论 |
| --- | --- | --- |
| **⚡ `remote-dev` 远端容器与长任务执行** | `v0.10.1` | 昇腾实机端到端评测中，`quarot` 量化修复任务 **`3/3` 全部解出**，结题中位耗时从 `747.31s` 缩短至 **`550.89s`**（提速 **`1.025x`**）；`dp2` 双卡排障任务 `2/3` 解出（与基线持平，速度比 `0.963x`），远端文件读写与持久后台作业稳定可靠 |
| **🎯 `coordinator` 多 Agent 并发防撞车** | `v0.5.3` | 3 轮双 Agent 并发抢卡抢端口压测：成功建立独立监听从 `3` 个提升至 **`6` 个**，端口冲突 **`3 → 0`**、重复选卡 **`3 → 0`**，前序任务释放后约 **`2ms`** 完成接管 |
| **📊 `npu-top` & 🛡️ `diagnostics` 可观测与隐私** | `v0.1.9` / `v0.4.3` | `npu-top` 3 台昇腾主机 24 张 NPU、`16/16` 进程卡号映射与 `3/3` 容器归属全部实测通过；`diagnostics` 9 次重复故障自动去重收敛为 3 条报告，隐私脱敏与关闭开关后零外发 **`3/3` 全部通过** |
| **🧠 `knowledge` 领域知识与跨任务经验复用** | `v0.12.2` | 接入知识库后，`dp2` 与 `dsh` 任务解题数均从 `2/3` 提升至 **`3/3` 全部解出**；跨任务经验沉淀后后续同源任务复用命中率 **`5/6`**（结题速度比 **`1.011x`**）。当前长上下文检索耗时偏高，**预计在 `0.0.3` 版本重点优化检索效率** |

---

## 📚 文档中心

完整技术文档索引请参阅 **[`docs/README.md`](./docs/README.md)**（**[English Documentation Index](./docs/README.en.md)**）：

| 文档主题 | 中文 | English |
| --- | --- | --- |
| **`v0.0.2` 版本发布与实测基准报告（当前版本）** | [docs/releases/0.0.2.md](./docs/releases/0.0.2.md) | [docs/releases/0.0.2.en.md](./docs/releases/0.0.2.en.md) |
| **系统架构与组件边界** | [docs/architecture.md](./docs/architecture.md) | [docs/architecture.en.md](./docs/architecture.en.md) |
| **工程设计原则与演进准则** | [docs/design-principles.md](./docs/design-principles.md) | [docs/design-principles.en.md](./docs/design-principles.en.md) |
| **知识与经验闭环设计** | [docs/knowledge-system.md](./docs/knowledge-system.md) | [docs/knowledge-system.en.md](./docs/knowledge-system.en.md) |
| **上下文分层、经验演化与开放探索设计** | [docs/knowledge-context-and-exploration.md](./docs/knowledge-context-and-exploration.md) | [docs/knowledge-context-and-exploration.en.md](./docs/knowledge-context-and-exploration.en.md) |
| **面向 Agent 的 Profiler 系统设计（`mindie-profiler`）** | [docs/profiler-system.md](./docs/profiler-system.md) | [docs/profiler-system.en.md](./docs/profiler-system.en.md) |
| **面向 Agent 的 NPU 四层仿真与边界求解设计（`mindie-sim`）** | [docs/simulation-system.md](./docs/simulation-system.md) | — |
| **核心能力落地与 GEAK 演化架构设计** | [docs/core-implementation-and-geak-evolution-design.md](./docs/core-implementation-and-geak-evolution-design.md) | — |
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

<p align="center">
  <img src="assets/brand/mindie-agent-logo.png" alt="MindIE Agent logo" width="128" height="128">
</p>

<h1 align="center">MindIE Agent</h1>

<p align="center">
  <strong>让你的 AI Coding Agent 原生掌握昇腾（Ascend）推理工程——自带领域记忆、远端 NPU 容器孪生工具与自进化经验飞轮</strong>
</p>

<p align="center">
  <a href="https://github.com/mindie-agent/mindie-agent/blob/main/docs/releases/0.0.1.md"><img src="https://img.shields.io/badge/release-v0.0.1-7045F5.svg" alt="Release v0.0.1"></a>
  <a href="https://github.com/mindie-agent/mindie-agent-cc"><img src="https://img.shields.io/badge/Claude_Code-Plugin-D97757.svg" alt="Claude Code Plugin"></a>
  <a href="https://github.com/mindie-agent/mindie-agent-codex"><img src="https://img.shields.io/badge/OpenAI_Codex-Plugin-10A37F.svg" alt="OpenAI Codex Plugin"></a>
  <a href="https://github.com/mindie-agent/mindie-agent-kimi"><img src="https://img.shields.io/badge/Kimi_Code-Plugin-2563EB.svg" alt="Kimi Code Plugin"></a>
  <a href="https://github.com/mindie-agent/awesome-mindie-skills"><img src="https://img.shields.io/badge/Ascend_NPU-vLLM--Ascend-0F766E.svg" alt="Ascend NPU vLLM-Ascend"></a>
</p>

<p align="center">
  <strong>中文</strong> · <a href="./README.en.md">English</a> · <a href="#-一句话无感安装">⚡ 一句话安装</a> · <a href="#-为什么选择-mindie-agent">✨ 核心能力</a> · <a href="#️-架构全景与经验飞轮">🏗️ 架构全景</a> · <a href="#-装好之后怎么用">🔥 实战用法</a> · <a href="#-组件与仓库生态">📦 仓库生态</a> · <a href="./docs/README.md">📚 文档中心</a>
</p>

---

## ⚡ 一句话无感安装

### 方式一：直接甩链接给你的 Agent（最推荐 ✨）

你不需要记住任何安装命令。打开你正在使用的 **Claude Code**、**OpenAI Codex CLI** 或 **Kimi Code**，直接复制并发送下面这句话：

```text
帮我安装一下这个 https://github.com/mindie-agent/mindie-agent
```

Agent 读取本页面后，会自动识别自身宿主环境并执行下方的**自动安装协议**，一步到位完成插件注册与运行时初始化。

<details>
<summary>🤖 <b>AI Agent 自动安装执行协议（点击展开 / Agent 读取本页时会自动解析执行）</b></summary>

> **给 AI Agent 的指令**：如果用户要求你安装 `mindie-agent`，请不要让用户手动翻文档，直接按以下步骤自动检测你所在的宿主客户端并在终端执行对应命令：
>
> #### 第一步：检查基础环境并识别你所在的宿主客户端
> 先在终端运行 `git --version && uv --version` 确认基础工具就绪，然后根据你自身的运行环境选择**唯一匹配**的分支执行（若不确定，请检查 `claude --version`、`codex --version` 或 `kimi --version`）：
>
> - **分支 A — 如果你是 Claude Code（或检测到 `CLAUDECODE` 环境变量 / 用户使用 `claude`）**：
>   ```bash
>   claude plugin marketplace add "https://github.com/mindie-agent/mindie-agent-cc.git#v0.0.1"
>   claude plugin install mindie-agent@mindie-agent-cc --scope user
>   claude --init-only
>   claude plugin list --json
>   claude mcp list
>   ```
>   *验证标准*：`claude plugin list --json` 显示 `mindie-agent@mindie-agent-cc`（`0.0.1`）已启用，且 `claude mcp list` 中 `mindie-knowledge` 与 `remote-dev` 均显示 `Connected`。
>
> - **分支 B — 如果你是 OpenAI Codex CLI（或检测到 `CODEX_CI` / `CODEX_THREAD_ID` / 用户使用 `codex`）**：
>   ```bash
>   codex plugin marketplace add https://github.com/mindie-agent/mindie-agent-codex.git --ref v0.0.1
>   codex plugin add mindie-agent@mindie-agent --json
>   codex plugin list --json
>   ```
>   *验证标准*：`codex plugin list --json` 显示 `mindie-agent@mindie-agent`（`0.0.1`）已启用。提醒用户开启新会话即可自动触发 `SessionStart` 构建锁定运行时。
>
> - **分支 C — 如果你是 Kimi Code CLI（或检测到 `KIMI_CODE_HOME` / 用户使用 `kimi`）**：
>   ```bash
>   MINDIE_TMP="${TMPDIR:-/tmp}/mindie-agent-kimi-install"
>   rm -rf "$MINDIE_TMP"
>   git clone --depth 1 https://github.com/mindie-agent/mindie-agent-kimi.git "$MINDIE_TMP"
>   SETUP_OUT=$(python3 "$MINDIE_TMP/scripts/setup.py")
>   echo "$SETUP_OUT"
>   NATIVE_PKG=$(printf '%s\n' "$SETUP_OUT" | python3 -c 'import sys, json; text=sys.stdin.read(); data=json.loads(text[text.find("{"):]); print(data["native_package"])')
>   python3 "$MINDIE_TMP/scripts/install_kimi_plugin.py" --kimi-home "${KIMI_CODE_HOME:-$HOME/.kimi-code}" --plugin-root "$NATIVE_PKG"
>   ```
>   *验证标准*：安装脚本成功返回，告知用户可在会话中输入 `/mindie-agent:status` 查看状态。
>
> - **分支 D — 如果你是 Cursor / 其他通用 MCP 客户端（仅需 SSH 远端 NPU 开发底座 `remote-dev`）**：
>   在项目的 `.mcp.json`（或 `.cursor/mcp.json`）中写入 `remote-dev` 服务：
>   ```json
>   {
>     "mcpServers": {
>       "remote-dev": {
>         "type": "stdio",
>         "command": "uvx",
>         "args": ["--from", "git+https://github.com/mindie-agent/remote-dev@main", "remote-dev", "server"]
>       }
>     }
>   }
>   ```
>
> #### 第二步：向用户汇报安装结果
> 安装完成后，向用户简要汇报：
> 1. 已安装的客户端插件名称、版本与验证结果；
> 2. 说明日常开发**无需任何激活命令**，直接在业务仓库中提问或操作远端 NPU 即可；
> 3. 说明**社区知识贡献**与**产品故障自动上报**默认均处于关闭状态（Opt-in），保护私密代码与内网信息安全。

</details>

### 方式二：人类终端手动一行安装

如果你更喜欢自己在终端敲命令，按你使用的客户端复制一行即可：

| 客户端 | 一键安装命令 | 插件仓库 |
| --- | --- | --- |
| **Claude Code** | `claude plugin marketplace add "https://github.com/mindie-agent/mindie-agent-cc.git#v0.0.1" && claude plugin install mindie-agent@mindie-agent-cc --scope user && claude --init-only` | [`mindie-agent-cc`](https://github.com/mindie-agent/mindie-agent-cc) |
| **OpenAI Codex CLI** | `codex plugin marketplace add https://github.com/mindie-agent/mindie-agent-codex.git --ref v0.0.1 && codex plugin add mindie-agent@mindie-agent --json` | [`mindie-agent-codex`](https://github.com/mindie-agent/mindie-agent-codex) |
| **Kimi Code CLI** | `git clone https://github.com/mindie-agent/mindie-agent-kimi.git && cd mindie-agent-kimi && python3 scripts/setup.py` | [`mindie-agent-kimi`](https://github.com/mindie-agent/mindie-agent-kimi) |
| **仅安装 NPU 监控台 (`npu-top`)** | `uvx --from "https://github.com/mindie-agent/npu-top/releases/download/v0.1.6/npu_top-0.1.6-py3-none-any.whl" npu-top serve` | [`npu-top`](https://github.com/mindie-agent/npu-top) |

---

## ✨ 为什么选择 MindIE Agent？

昇腾（Ascend）大模型推理工程（如 `vLLM-Ascend` 算子适配、CANN 图编译排障、多机多卡精度对齐与性能调优）往往面临**环境在远端容器、经验散落在聊天记录、通用大模型缺乏昇腾实战上下文**的痛点。

| 维度 | 传统 Agent 开发体验 ❌ | 接入 MindIE Agent 之后 ✅ |
| --- | --- | --- |
| **领域经验与踩坑记忆** | 每次新开会话都要从头解释 `vLLM-Ascend` 架构，反复踩相同的算子/HCCL/ACLGraph 坑 | 自动同步 [`knowledge-vllm-ascend`](https://github.com/mindie-agent/knowledge-vllm-ascend) 真实排障知识包，本地 BM25 秒级定位 + 原文分块按需精读 |
| **远端 NPU 服务器与容器操作** | 手写冗长 `ssh` / `docker exec` 命令，引号转义频繁出错，长耗时测试断连即丢日志 | [`remote-dev`](https://github.com/mindie-agent/remote-dev) 提供 19 个与本地 `Read`/`Edit`/`Bash`/`Grep` 完全同构的远端孪生工具，直接深入运行中的容器 |
| **经验沉淀与隐私安全** | 有价值的排障过程随会话关闭而流失；或者担心内网 IP、路径、Token 泄露而不敢分享 | 用户显式授权后，由确定性规则 + Gitleaks 双重脱敏公开对话，绝不用大模型篡改技术原文 |
| **工作流侵入性** | 被迫迁入厚重的定制脚手架或改写个人全局 MCP/Skills 配置 | **零日常仪式感**：直接在你自己的业务 Git 仓库与原生 Agent 会话中按需介入，不触碰无关配置 |

---

## 🏗️ 架构全景与经验飞轮

### 1. 模块化分层架构

MindIE Agent 采用**薄客户端适配层 + 独立共享运行时底座**架构，不綁架业务源码仓库：

```mermaid
flowchart TB
  subgraph Clients["🧑‍💻 开发者日常 AI 编程客户端 (Native Coding Agents)"]
    CC["Claude Code"]
    Codex["OpenAI Codex CLI"]
    Kimi["Kimi Code CLI"]
  end

  subgraph Adapters["🔌 原生插件薄适配层 (Thin Harness Plugins)"]
    P_CC["mindie-agent-cc"]
    P_Codex["mindie-agent-codex"]
    P_Kimi["mindie-agent-kimi"]
  end

  subgraph Core["⚙️ 共享运行时组件底座 (Shared Runtime Components)"]
    Knowledge["🧠 mindie-knowledge<br/>本地 BM25 检索 · 确定性脱敏 · 异步索引"]
    RemoteDev["⚡ remote-dev<br/>19 个 SSH 远端孪生工具 · 容器直连 · 持久作业"]
    Coord["🎯 coordinator<br/>持久化用户容器 · Git 快照物化 · NPU 租约队列"]
    NpuTop["📊 npu-top<br/>无代理 NPU 实时看板 · 90 天热力图 (只观测不分配)"]
    Diag["🛡️ mindie-diagnostics<br/>有界 JSONL 轮转日志 · 严密白名单故障上报"]
  end

  subgraph Remote["🖥️ 远端昇腾集群与知识源 (Ascend Fleet & Canonical Feed)"]
    Feed[("📚 knowledge-vllm-ascend<br/>公共工程知识包与有用性反馈")]
    Cluster[("🚀 远端昇腾 NPU 主机与 Docker 容器<br/>910B / A3 / Ascend 950 (A5)")]
  end

  CC --> P_CC
  Codex --> P_Codex
  Kimi --> P_Kimi

  P_CC & P_Codex & P_Kimi --> Knowledge & RemoteDev & Diag
  Knowledge <--> Feed
  RemoteDev --> Cluster
  Coord --> RemoteDev
  NpuTop -. "SSH 只读探测" .-> Cluster
```

### 2. 领域知识与实战经验自进化闭环

```mermaid
sequenceDiagram
  autonumber
  actor Dev as 开发者
  participant Agent as Coding Agent (Claude / Codex / Kimi)
  participant Know as mindie-knowledge (本地服务)
  participant NPU as remote-dev (远端昇腾容器)
  participant Repo as knowledge-vllm-ascend (公共知识库)

  Dev->>Agent: 输入 /mindie-agent + 问题描述（唤醒昇腾知识、经验与 Skill 体系）
  Agent->>Know: 1. 检索相关领域知识摘要 (query) 并按需精读原文分块 (explain)
  Agent->>NPU: 2. 默认自动调用 remote-dev 在远端容器内读写代码、打补丁并运行 NPU 验证
  NPU-->>Agent: 返回实机执行结果与日志引用
  Agent-->>Dev: 3. 完成修复并给出最终回复 (可选提交知识有用性反馈 up/down)
  Note over Agent,Repo: 以下步骤仅在用户已显式开启「社区共享 (Opt-in)」时后台异步触发
  Agent->>Know: 4. 会话结束 (Stop Hook) 捕获公开可见对话投影
  Know->>Know: 5. 确定性规则 + Gitleaks 脱敏 (拒绝任何未决敏感信息) + 小模型生成分块导航
  Know->>Repo: 6. 自动创建脱敏 Markdown 知识包 PR 沉淀回社区
```

---

## 🔥 装好之后怎么用？（触发方式与使用示例）

MindIE Agent 的核心交互理念是**极简易用与渐进式披露（Progressive Disclosure）**——对用户而言，**从头到尾只需要知道 `/mindie-agent` 这一个入口**，不需要记忆任何复杂的子命令（如 `:init`、`:status` 等），底层上下文只在 Agent 需要时按需向 Agent 渐进式披露：

| 能力模块 | 触发方式 | 极简使用方式说明 |
| --- | --- | --- |
| **🧠 昇腾知识库、实战经验与 Skill 系统**<br/>（`mindie-knowledge` + 领域 Skills） | **手动触发**<br/>（统一入口 `/mindie-agent`） | 遇到昇腾排障、模型迁移、算子开发或推理调优问题时，直接输入 **`/mindie-agent` + 你的问题描述**（Codex 中也可输入 `$mindie-agent`）。哪怕是首次配置、查看状态或开关共享，也只需输入 `/mindie-agent` 加自然语言，由 Agent 内部自动感知处理。 |
| **⚡ 远端昇腾服务器开发执行**<br/>（`remote-dev` SSH / 容器工具集） | **默认自动触发**<br/>（常驻 MCP，无需斜杠命令） | `remote-dev` 默认处于就绪状态。日常对话中只要提到远端服务器、容器或 NPU 命令，Agent 就会**默认自动调用** `remote_read`、`remote_edit`、`remote_bash` 及后台作业工具操作远端环境。 |
| **🔄 排障经验沉淀与社区共建**<br/>（`Stop` 后台采集 + Gitleaks 脱敏） | **后台静默运行**<br/>（一次开启，全程无感） | 首次配置选择开启社区贡献后，每次会话结束时都会在后台**自动完成本地脱敏与知识包 PR 整理**——平时只管专注提问和写代码，全程无需额外操作。 |

### 实战对话示例（直接复制即可体验）

#### 💡 示例 1：手动输入 `/mindie-agent` 唤醒知识库、历史经验与 Skill 排障
```text
/mindie-agent 我们在昇腾 A3 上跑 DeepSeek MLA 遇到 ACLGraph 捕获失败 / Triton 内核编译报错，帮我查下知识库里有没有相同现象的历史经验和修复方案。
```
> **背后发生的事**：通过 `/mindie-agent` 显式唤醒 MindIE Agent 技能与知识体系后，Agent 自动调用 `mindie-knowledge` 检索 [`knowledge-vllm-ascend`](https://github.com/mindie-agent/knowledge-vllm-ascend) 中的真实排障知识包，先浏览 `PACKAGE.md` 分块目录，再按需精读对应分块的报错栈、适用条件与修复命令。

#### 💡 示例 2：日常对话默认触发 `remote-dev`，在远端昇腾容器内改代码跑测
```text
连上远端机器 192.0.2.21（端口 22）上的 vllm-dev 容器，帮我看下 /workspace/vllm-ascend 当前分支的报错日志，定位为什么 Qwen3 在 TP=4 下精度异常，修改后在容器里跑一下对应的 pytest。
```
> **背后发生的事**：无需输入任何斜杠命令，Agent 默认自动调用 `remote-dev` 的 `remote_read`、`remote_grep`、`remote_edit` 与 `remote_bash` 在远端 `vllm-dev` 容器内完成代码检索、打补丁与单测验证；长耗时编译或测试会自动转为受管后台作业并支持实时看日志。

#### 💡 示例 3：`/mindie-agent` + `remote-dev` 联动调优，排障经验后台静默沉淀
```text
/mindie-agent 结合昇腾推理调优经验，帮我在远端 NPU 开发机上排查当前 decode 阶段的时延瓶颈，拉取 Profiling 关键指标并验证优化补丁。
```
> **背后发生的事**：Agent 同时调用 `/mindie-agent` 的领域经验与 `remote-dev` 的远端实机执行能力完成闭环验证。若已在首次配置时开启社区贡献，会话结束时后台会自动将脱敏后的排障过程沉淀为新的开源知识包，全程无需额外操作。

---

## 📦 组件与仓库生态

`@mindie-agent` 组织下的每个仓库均遵循单一职责边界，既可由插件协同联动，也可独立安装使用：

### 1. 产品总入口与社区生态

| 仓库 | 定位与核心职责 |
| --- | --- |
| **[`mindie-agent`](https://github.com/mindie-agent/mindie-agent)** *(本仓库)* | 顶层产品入口、整体架构、工程设计原则、跨组件发布兼容契约与正式发行版记录 |
| **[`awesome-mindie-skills`](https://github.com/mindie-agent/awesome-mindie-skills)** | 面向昇腾推理工程的高质量开源 Agent Skills 精选目录（精度定位、性能采集、算子分析等） |

### 2. 原生客户端插件（Harness Adapters）

| 仓库 | 适用宿主 | 定位与核心职责 |
| --- | --- | --- |
| **[`mindie-agent-cc`](https://github.com/mindie-agent/mindie-agent-cc)** | **Claude Code** | Claude Code 原生插件：生命周期 Hook、MCP 服务桥接与固定运行时管理 |
| **[`mindie-agent-codex`](https://github.com/mindie-agent/mindie-agent-codex)** | **OpenAI Codex CLI** | OpenAI Codex CLI 原生插件：Marketplace 安装、Rollout 增量脱敏采集与服务连续性管理 |
| **[`mindie-agent-kimi`](https://github.com/mindie-agent/mindie-agent-kimi)** | **Kimi Code CLI** | Kimi Code 原生插件：代数原子更新、公开会话投影采集与 MCP 桥接 |

### 3. 共享运行时底座（Shared Runtime Components）

| 仓库 | Python 包 / 入口 | 定位与核心职责 |
| --- | --- | --- |
| **[`knowledge`](https://github.com/mindie-agent/knowledge)** | `mindie-knowledge` | 共享知识与经验闭环引擎：本地 SQLite/BM25 检索、确定性脱敏、块索引调度、Git PR 发布与独立反馈 |
| **[`knowledge-vllm-ascend`](https://github.com/mindie-agent/knowledge-vllm-ascend)** | *(Markdown 知识库)* | `vLLM` / `vLLM-Ascend` 领域公共工程知识包与有用性反馈权威语料源 |
| **[`remote-dev`](https://github.com/mindie-agent/remote-dev)** | `remote-dev` | SSH 远端开发底座：19 个本地工具孪生、已有 Docker 容器直连、连接池复用与产物传输 |
| **[`coordinator`](https://github.com/mindie-agent/coordinator)** | `mindie-coordinator` | 本地受管执行控制面：持久化用户容器生命周期、Git 快照物化与宿主机 NPU 排队分配 |
| **[`npu-top`](https://github.com/mindie-agent/npu-top)** | `npu-top` | 昇腾 NPU 无代理监控台：Web 实时看板、90 天有界历史热力图与只读 Agent CLI/MCP 观测面 |
| **[`diagnostics`](https://github.com/mindie-agent/diagnostics)** | `mindie-diagnostics` | 结构化诊断底座：无模型 4×1 MiB 本地日志轮转、离线脱敏诊断包与可选 GitHub Issue 自动上报 |

---

## 🧭 工程设计哲学

MindIE Agent 在持续演进中沉淀了一套严格的 **[工程设计原则](./docs/design-principles.md)**（[English](./docs/design-principles.en.md)），核心理念包括：

- **以完成用户实际目标的总成本衡量效率**：绝不为了防备极小概率异常而给每次日常任务强加繁琐仪式。
- **零心智负担与按需介入**：工具内部消化管理复杂度；Skill 仅提供信息与导航；知识仅作带证据的参考，绝不喧宾夺主。
- **复用成熟机制，按确证缺口自研**：优先复用宿主、OS 与成熟组件能力，替代旧方案时彻底移除重复状态机。
- **诚实可观测，严禁静默降级或隐藏错误**：明确区分“已完成”、“失败”与“外部副作用不确定（`unknown`）”，绝不伪造成功或盲目重放不确定写入。

---

## 📚 文档中心

完整技术文档索引请参阅 **[`docs/README.md`](./docs/README.md)**（**[English Documentation Index](./docs/README.en.md)**）：

| 文档主题 | 中文 | English |
| --- | --- | --- |
| **系统架构与组件边界** | [docs/architecture.md](./docs/architecture.md) | [docs/architecture.en.md](./docs/architecture.en.md) |
| **工程设计原则与演进准则** | [docs/design-principles.md](./docs/design-principles.md) | [docs/design-principles.en.md](./docs/design-principles.en.md) |
| **知识与经验闭环设计** | [docs/knowledge-system.md](./docs/knowledge-system.md) | [docs/knowledge-system.en.md](./docs/knowledge-system.en.md) |
| **Harness 边界、授权与生命周期** | [docs/harness-boundary-and-lifecycle.md](./docs/harness-boundary-and-lifecycle.md) | [docs/harness-boundary-and-lifecycle.en.md](./docs/harness-boundary-and-lifecycle.en.md) |
| **原生运行时复用设计** | [docs/native-runtime-reuse.md](./docs/native-runtime-reuse.md) | [docs/native-runtime-reuse.en.md](./docs/native-runtime-reuse.en.md) |
| **发布兼容、配套发行与静默更新** | [docs/release-compatibility-and-update.md](./docs/release-compatibility-and-update.md) | [docs/release-compatibility-and-update.en.md](./docs/release-compatibility-and-update.en.md) |
| **结构化诊断与故障自动上报** | [docs/diagnostics-and-reporting.md](./docs/diagnostics-and-reporting.md) | [docs/diagnostics-and-reporting.en.md](./docs/diagnostics-and-reporting.en.md) |
| **演进路线与下一步重点** | [docs/next-steps.md](./docs/next-steps.md) | [docs/next-steps.en.md](./docs/next-steps.en.md) |
| **`v0.0.1` 首发版本发布记录** | [docs/releases/0.0.1.md](./docs/releases/0.0.1.md) | [docs/releases/0.0.1.en.md](./docs/releases/0.0.1.en.md) |

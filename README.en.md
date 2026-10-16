<p align="center">
  <img src="assets/brand/mindie-agent-logo.png" alt="MindIE Agent logo" width="128" height="128">
</p>

<h1 align="center">MindIE Agent</h1>

<p align="center">
  <strong>Supercharge your AI Coding Agent for Ascend NPU Inference Engineering — with curated domain memory, SSH remote container twins, and a self-evolving experience flywheel</strong>
</p>

<p align="center">
  <a href="https://github.com/mindie-agent/mindie-agent/blob/main/docs/releases/0.0.1.en.md"><img src="https://img.shields.io/badge/release-v0.0.1-7045F5.svg" alt="Release v0.0.1"></a>
  <a href="https://github.com/mindie-agent/mindie-agent-cc"><img src="https://img.shields.io/badge/Claude_Code-Plugin-D97757.svg" alt="Claude Code Plugin"></a>
  <a href="https://github.com/mindie-agent/mindie-agent-codex"><img src="https://img.shields.io/badge/OpenAI_Codex-Plugin-10A37F.svg" alt="OpenAI Codex Plugin"></a>
  <a href="https://github.com/mindie-agent/mindie-agent-kimi"><img src="https://img.shields.io/badge/Kimi_Code-Plugin-2563EB.svg" alt="Kimi Code Plugin"></a>
  <a href="https://github.com/mindie-agent/awesome-mindie-skills"><img src="https://img.shields.io/badge/Ascend_NPU-vLLM--Ascend-0F766E.svg" alt="Ascend NPU vLLM-Ascend"></a>
</p>

<p align="center">
  <a href="./README.md">中文</a> · <strong>English</strong> · <a href="#-zero-friction-one-sentence-install">⚡ 1-Sentence Install</a> · <a href="#-why-mindie-agent">✨ Why MindIE Agent</a> · <a href="#️-architecture--experience-flywheel">🏗️ Architecture</a> · <a href="#-real-world-workflows">🔥 Workflows</a> · <a href="#-repository-ecosystem">📦 Ecosystem</a> · <a href="./docs/README.en.md">📚 Docs</a>
</p>

---

## ⚡ Zero-Friction One-Sentence Install

### Option 1: Just Paste the Link to Your Agent (Recommended ✨)

No need to memorize CLI flags. Open **Claude Code**, **OpenAI Codex CLI**, or **Kimi Code**, and paste this single sentence into your chat:

```text
Please install MindIE Agent for me: https://github.com/mindie-agent/mindie-agent
```

When your Agent reads this page, it will automatically detect its own host environment and execute the **Agent Auto-Install Playbook** below.

<details open>
<summary>🤖 <b>Agent Auto-Install Playbook (Instructions for AI Agents — Execute directly when asked to install this repo)</b></summary>

> **Instructions for AI Agents**: When the user asks you to install `mindie-agent`, do **not** ask them to read documentation manually. Detect which coding agent environment you are running inside and execute the matching branch below:
>
> #### Step 1: Check prerequisites & identify your host environment
> Verify `git --version && uv --version`, then run the **single matching branch** for your host CLI (check `claude --version`, `codex --version`, or `kimi --version` if unsure):
>
> - **Branch A — If you are running inside Claude Code (`CLAUDECODE` env or `claude` CLI)**:
>   ```bash
>   claude plugin marketplace add "https://github.com/mindie-agent/mindie-agent-cc.git#v0.0.1"
>   claude plugin install mindie-agent@mindie-agent-cc --scope user
>   claude --init-only
>   claude plugin list --json
>   claude mcp list
>   ```
>   *Verification*: Confirm `claude plugin list --json` shows `mindie-agent@mindie-agent-cc` (`0.0.1`) enabled and `claude mcp list` shows both `mindie-knowledge` and `remote-dev` as `Connected`.
>
> - **Branch B — If you are running inside OpenAI Codex CLI (`CODEX_CI` / `CODEX_THREAD_ID` env or `codex` CLI)**:
>   ```bash
>   codex plugin marketplace add https://github.com/mindie-agent/mindie-agent-codex.git --ref v0.0.1
>   codex plugin add mindie-agent@mindie-agent --json
>   codex plugin list --json
>   ```
>   *Verification*: Confirm `codex plugin list --json` shows `mindie-agent@mindie-agent` (`0.0.1`) enabled. Let the user know that starting a new session will trigger `SessionStart` to build the locked runtime.
>
> - **Branch C — If you are running inside Kimi Code CLI (`KIMI_CODE_HOME` env or `kimi` CLI)**:
>   ```bash
>   MINDIE_TMP="${TMPDIR:-/tmp}/mindie-agent-kimi-install"
>   rm -rf "$MINDIE_TMP"
>   git clone --depth 1 https://github.com/mindie-agent/mindie-agent-kimi.git "$MINDIE_TMP"
>   SETUP_OUT=$(python3 "$MINDIE_TMP/scripts/setup.py")
>   echo "$SETUP_OUT"
>   NATIVE_PKG=$(printf '%s\n' "$SETUP_OUT" | python3 -c 'import sys, json; text=sys.stdin.read(); data=json.loads(text[text.find("{"):]); print(data["native_package"])')
>   python3 "$MINDIE_TMP/scripts/install_kimi_plugin.py" --kimi-home "${KIMI_CODE_HOME:-$HOME/.kimi-code}" --plugin-root "$NATIVE_PKG"
>   ```
>   *Verification*: Confirm `install_kimi_plugin.py` succeeds and let the user know they can run `/mindie-agent:status` inside Kimi Code.
>
> - **Branch D — If you are running inside Cursor or another generic MCP client (standalone `remote-dev` SSH toolset)**:
>   Add `remote-dev` to `.mcp.json` (or `.cursor/mcp.json`):
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
> #### Step 2: Report back to the user
> Once finished, report:
> 1. Which plugin and version were installed and verified;
> 2. That **no per-task activation command is needed**—knowledge retrieval and remote NPU tools work on demand inside any repository;
> 3. That **community knowledge sharing** and **automated fault reporting** are **off by default (opt-in)** to protect private code and internal endpoints.

</details>

### Option 2: One-Line Terminal Install for Humans

Prefer running commands yourself? Pick the one-liner for your coding agent:

| Coding Agent | One-Line Terminal Command | Plugin Repo |
| --- | --- | --- |
| **Claude Code** | `claude plugin marketplace add "https://github.com/mindie-agent/mindie-agent-cc.git#v0.0.1" && claude plugin install mindie-agent@mindie-agent-cc --scope user && claude --init-only` | [`mindie-agent-cc`](https://github.com/mindie-agent/mindie-agent-cc) |
| **OpenAI Codex CLI** | `codex plugin marketplace add https://github.com/mindie-agent/mindie-agent-codex.git --ref v0.0.1 && codex plugin add mindie-agent@mindie-agent --json` | [`mindie-agent-codex`](https://github.com/mindie-agent/mindie-agent-codex) |
| **Kimi Code CLI** | `git clone https://github.com/mindie-agent/mindie-agent-kimi.git && cd mindie-agent-kimi && python3 scripts/setup.py` | [`mindie-agent-kimi`](https://github.com/mindie-agent/mindie-agent-kimi) |
| **NPU Dashboard Only (`npu-top`)** | `uvx --from "https://github.com/mindie-agent/npu-top/releases/download/v0.1.6/npu_top-0.1.6-py3-none-any.whl" npu-top serve` | [`npu-top`](https://github.com/mindie-agent/npu-top) |

---

## ✨ Why MindIE Agent?

Developing and debugging large-model inference on Ascend NPUs (`vLLM-Ascend` kernel adaptation, CANN graph compilation, multi-node accuracy alignment, and profiling) often suffers from **remote container friction, tribal knowledge lost in chat logs, and general-purpose LLMs lacking Ascend-specific context**.

| Dimension | Without MindIE Agent ❌ | With MindIE Agent ✅ |
| --- | --- | --- |
| **Ascend Domain Memory** | Re-explaining `vLLM-Ascend` internals every session; repeatedly hitting the same HCCL / ACLGraph / Triton pitfalls | Automatic sync of [`knowledge-vllm-ascend`](https://github.com/mindie-agent/knowledge-vllm-ascend) troubleshooting packages with instant local BM25 search + on-demand block reading |
| **Remote NPU & Container Execution** | Brittle ad-hoc `ssh` / `docker exec` one-liners, broken shell quoting, and lost logs when long jobs time out | [`remote-dev`](https://github.com/mindie-agent/remote-dev) provides 19 remote twins of local `Read`/`Edit`/`Bash`/`Grep` tools that operate directly inside existing Docker containers |
| **Experience Capture & Privacy** | Hard-won debugging insights vanish when the chat closes—or stay locked away for fear of leaking internal IPs and tokens | Opt-in capture with deterministic redaction + Gitleaks scanning—preserving complete verbatim engineering material without LLM rewriting |
| **Workflow Intrusion** | Forced into heavy wrapper scaffolds or invasive global configuration changes | **Zero daily ceremony**: works on demand inside your existing Git repositories and native agent sessions |

---

## 🏗️ Architecture & Experience Flywheel

### 1. Modular Layered Architecture

MindIE Agent combines **thin native client plugins** with **decoupled shared runtime components**:

```mermaid
flowchart TB
  subgraph Clients["🧑‍💻 Native AI Coding Agents"]
    CC["Claude Code"]
    Codex["OpenAI Codex CLI"]
    Kimi["Kimi Code CLI"]
  end

  subgraph Adapters["🔌 Thin Native Harness Plugins"]
    P_CC["mindie-agent-cc"]
    P_Codex["mindie-agent-codex"]
    P_Kimi["mindie-agent-kimi"]
  end

  subgraph Core["⚙️ Shared Runtime Components"]
    Knowledge["🧠 mindie-knowledge<br/>Local BM25 · Deterministic Redaction · Block Indexing"]
    RemoteDev["⚡ remote-dev<br/>19 SSH Tool Twins · Container Exec · Persistent Jobs"]
    Coord["🎯 coordinator<br/>Persistent User Containers · Git Materialization · NPU Queue"]
    NpuTop["📊 npu-top<br/>Agentless NPU Dashboard · 90-Day Heatmaps (Observation-Only)"]
    Diag["🛡️ mindie-diagnostics<br/>Bounded 4x1 MiB JSONL Logs · Allowlist Issue Reporter"]
  end

  subgraph Remote["🖥️ Remote Ascend Fleet & Canonical Feed"]
    Feed[("📚 knowledge-vllm-ascend<br/>Public Knowledge Packages & Feedback")]
    Cluster[("🚀 Remote Ascend NPU Hosts & Docker Containers<br/>910B / A3 / Ascend 950 (A5)")]
  end

  CC --> P_CC
  Codex --> P_Codex
  Kimi --> P_Kimi

  P_CC & P_Codex & P_Kimi --> Knowledge & RemoteDev & Diag
  Knowledge <--> Feed
  RemoteDev --> Cluster
  Coord --> RemoteDev
  NpuTop -. "Read-only SSH probes" .-> Cluster
```

### 2. Self-Evolving Knowledge & Experience Loop

```mermaid
sequenceDiagram
  autonumber
  actor Dev as Developer
  participant Agent as Coding Agent (Claude / Codex / Kimi)
  participant Know as mindie-knowledge (Local Service)
  participant NPU as remote-dev (Remote Ascend Container)
  participant Repo as knowledge-vllm-ascend (Public Corpus)

  Dev->>Agent: Ask to debug or optimize a vLLM-Ascend workload on remote NPUs
  Agent->>Know: 1. Search domain knowledge outlines (query) & inspect relevant blocks (explain)
  Agent->>NPU: 2. Read/edit files, apply patches, and run NPU tests inside container (remote.*)
  NPU-->>Agent: Return execution results & durable log refs
  Agent-->>Dev: 3. Deliver verified fix (optionally record usefulness feedback up/down)
  Note over Agent,Repo: Steps 4–6 run asynchronously in the background ONLY when Community Sharing is enabled (Opt-in)
  Agent->>Know: 4. Session end (Stop Hook) captures public transcript projection
  Know->>Know: 5. Deterministic rules + Gitleaks redaction (fail-closed) + block navigation indexing
  Know->>Repo: 6. Propose redacted Markdown package PR to the community corpus
```

---

## 🔥 Real-World Workflows

Once installed, **no special activation command is required**. Just talk to your Agent inside your repository:

#### 💡 Scenario 1: Interactive Debugging Inside a Remote Ascend Container
> **Prompt**:
> *"Connect to the `vllm-dev` container on host `192.0.2.21` (port 22), inspect `/workspace/vllm-ascend`, find out why Qwen3 accuracy diverges under TP=4, patch the kernel wrapper, and run the corresponding pytest inside the container."*
>
> **What happens**: Your Agent uses `remote_read`, `remote_grep`, `remote_edit`, and `remote_bash` with `container="vllm-dev"` directly over pooled SSH RPC, automatically tracking long-running test output via durable cursors.

#### 💡 Scenario 2: Querying Verified Ascend Troubleshooting Experience
> **Prompt**:
> *"We're hitting an `ACLGraph` capture failure / Triton compilation error with DeepSeek MLA on Ascend A3. Check MindIE knowledge for prior root causes and verified workarounds."*
>
> **What happens**: Your Agent queries `mindie-knowledge` against synchronized [`knowledge-vllm-ascend`](https://github.com/mindie-agent/knowledge-vllm-ascend) packages, scans the block outline, and reads the exact troubleshooting steps and applicability conditions.

#### 💡 Scenario 3: Checking Fleet Capacity & Installing Domain Skills
> **Prompt**:
> *"Check `npu-top` for any A3 server with at least 4 observed idle NPUs, and install the `ascend-profiling-analysis` skill from `awesome-mindie-skills`."*

---

## 📦 Repository Ecosystem

Every repository under `@mindie-agent` has a clean, single-purpose boundary and can be used together or standalone:

### 1. Product Entry & Community Catalogue

| Repository | Role |
| --- | --- |
| **[`mindie-agent`](https://github.com/mindie-agent/mindie-agent)** *(This Repo)* | Product entry point, system architecture, engineering design principles, release compatibility contracts, and release records |
| **[`awesome-mindie-skills`](https://github.com/mindie-agent/awesome-mindie-skills)** | Curated catalogue of open-source Agent Skills for Ascend inference engineering (accuracy debugging, profiling, operator analysis) |

### 2. Native Harness Plugins

| Repository | Host Client | Role |
| --- | --- | --- |
| **[`mindie-agent-cc`](https://github.com/mindie-agent/mindie-agent-cc)** | **Claude Code** | Native Claude Code plugin: lifecycle hooks, MCP stdio bridges, and pinned runtime management |
| **[`mindie-agent-codex`](https://github.com/mindie-agent/mindie-agent-codex)** | **OpenAI Codex CLI** | Native OpenAI Codex CLI plugin: marketplace packaging, incremental rollout redaction, and service continuity |
| **[`mindie-agent-kimi`](https://github.com/mindie-agent/mindie-agent-kimi)** | **Kimi Code CLI** | Native Kimi Code plugin: atomic generation updates, public transcript projection capture, and MCP bridging |

### 3. Shared Runtime Components

| Repository | Package / CLI | Role |
| --- | --- | --- |
| **[`knowledge`](https://github.com/mindie-agent/knowledge)** | `mindie-knowledge` | Shared knowledge runtime: local SQLite/BM25 retrieval, fail-closed redaction, block indexing, Git PR publishing, and feedback |
| **[`knowledge-vllm-ascend`](https://github.com/mindie-agent/knowledge-vllm-ascend)** | *(Markdown Corpus)* | Canonical public knowledge packages and usefulness feedback for `vLLM` and `vLLM-Ascend` |
| **[`remote-dev`](https://github.com/mindie-agent/remote-dev)** | `remote-dev` | SSH remote development substrate: 19 local tool twins, existing Docker container execution, pooled RPC, and artifact streaming |
| **[`coordinator`](https://github.com/mindie-agent/coordinator)** | `mindie-coordinator` | Local control plane: persistent user containers (`mindie-<user>`), Git snapshot materialization, and host NPU queue arbitration |
| **[`npu-top`](https://github.com/mindie-agent/npu-top)** | `npu-top` | Agentless Ascend NPU observability dashboard: live web UI, bounded 90-day SQLite heatmaps, and read-only Agent CLI/MCP tools |
| **[`diagnostics`](https://github.com/mindie-agent/diagnostics)** | `mindie-diagnostics` | Model-free observability substrate: bounded 4×1 MiB JSONL rotation, offline redacted bundles, and opt-in GitHub Issue reporting |

---

## 🧭 Engineering Design Philosophy

MindIE Agent is guided by a cohesive set of **[Engineering Design Principles](./docs/design-principles.en.md)** ([中文](./docs/design-principles.md)) forged through real-world Ascend engineering:

- **Optimize for Total User Goal Cost**: Reliability mechanisms must reduce total comprehension, waiting, and debugging cost—never imposing ceremony on ordinary tasks for rare edge cases.
- **Zero Cognitive Load & On-Demand Intervention**: Tools absorb internal state complexity; Skills stay informational; Knowledge remains advisory with explicit evidence and applicability bounds.
- **Reuse Proven Mechanisms, Build Only for Proven Gaps**: Leverage native host, OS, and mature component capabilities first, and delete replaced state machines cleanly when upgrading.
- **Honest Observability & Fail-Visible Semantics**: Explicitly distinguish completed work, failure, and uncertain external side effects (`unknown`)—never fabricating success or blindly replaying uncertain writes.

---

## 📚 Documentation Center

See **[`docs/README.en.md`](./docs/README.en.md)** (**[中文文档中心](./docs/README.md)**) for the complete documentation suite:

| Topic | 中文 | English |
| --- | --- | --- |
| **System Architecture & Domain Boundaries** | [docs/architecture.md](./docs/architecture.md) | [docs/architecture.en.md](./docs/architecture.en.md) |
| **Engineering Design Principles** | [docs/design-principles.md](./docs/design-principles.md) | [docs/design-principles.en.md](./docs/design-principles.en.md) |
| **Knowledge & Experience System** | [docs/knowledge-system.md](./docs/knowledge-system.md) | [docs/knowledge-system.en.md](./docs/knowledge-system.en.md) |
| **Harness Boundary, Consent & Lifecycle** | [docs/harness-boundary-and-lifecycle.md](./docs/harness-boundary-and-lifecycle.md) | [docs/harness-boundary-and-lifecycle.en.md](./docs/harness-boundary-and-lifecycle.en.md) |
| **Native Runtime Reuse** | [docs/native-runtime-reuse.md](./docs/native-runtime-reuse.md) | [docs/native-runtime-reuse.en.md](./docs/native-runtime-reuse.en.md) |
| **Release Compatibility & Silent Update** | [docs/release-compatibility-and-update.md](./docs/release-compatibility-and-update.md) | [docs/release-compatibility-and-update.en.md](./docs/release-compatibility-and-update.en.md) |
| **Structured Diagnostics & Issue Reporting** | [docs/diagnostics-and-reporting.md](./docs/diagnostics-and-reporting.md) | [docs/diagnostics-and-reporting.en.md](./docs/diagnostics-and-reporting.en.md) |
| **Roadmap & Next Steps** | [docs/next-steps.md](./docs/next-steps.md) | [docs/next-steps.en.md](./docs/next-steps.en.md) |
| **`v0.0.1` Release Record** | [docs/releases/0.0.1.md](./docs/releases/0.0.1.md) | [docs/releases/0.0.1.en.md](./docs/releases/0.0.1.en.md) |

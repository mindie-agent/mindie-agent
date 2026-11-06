<p align="center">
  <img src="assets/brand/mindie-agent-logo.png" alt="MindIE Agent logo" width="128" height="128">
</p>

<h1 align="center">MindIE Agent</h1>

<p align="center">
  <strong>Ascend domain knowledge, remote NPU execution, and traceable engineering experience for native coding agents</strong>
</p>

<!-- mindie-org-versions:main-badges-en:start -->
<p align="center">
  <a href="https://github.com/mindie-agent/mindie-agent/blob/main/docs/releases/0.1.12.en.md"><img src="https://img.shields.io/badge/release-v0.1.12-7045F5.svg" alt="Release v0.1.12"></a>
  <a href="https://github.com/mindie-agent/mindie-agent-cc"><img src="https://img.shields.io/badge/Claude_Code-Plugin-D97757.svg" alt="Claude Code Plugin"></a>
  <a href="https://github.com/mindie-agent/mindie-agent-codex"><img src="https://img.shields.io/badge/OpenAI_Codex-Plugin-10A37F.svg" alt="OpenAI Codex Plugin"></a>
  <a href="https://github.com/mindie-agent/mindie-agent-kimi"><img src="https://img.shields.io/badge/Kimi_Code-Plugin-2563EB.svg" alt="Kimi Code Plugin"></a>
  <a href="https://github.com/mindie-agent/mindie-agent-dsh"><img src="https://img.shields.io/badge/DeepSeek_Harness-Plugin-0EA5E9.svg" alt="DeepSeek Harness Plugin"></a>
  <a href="https://github.com/mindie-agent/mindie-agent-agy"><img src="https://img.shields.io/badge/Google_Antigravity-Plugin-4285F4.svg" alt="Google Antigravity Plugin"></a>
  <a href="https://github.com/mindie-agent/mindie-agent-wb"><img src="https://img.shields.io/badge/Tencent_WorkBuddy-Plugin-0EC8A9.svg" alt="Tencent WorkBuddy Plugin"></a>
  <a href="https://github.com/mindie-agent/awesome-mindie-skills"><img src="https://img.shields.io/badge/Ascend_AI_Infra-vLLM--Ascend_%7C_AscendC_%7C_Triton-C7000B.svg" alt="Ascend NPU AI Infra"></a>
</p>
<!-- mindie-org-versions:main-badges-en:end -->

<p align="center">
  <a href="./README.md">中文</a> · <strong>English</strong> · <a href="#-zero-friction-one-sentence-install-agent-only-">⚡ 1-Sentence Install</a> · <a href="#-why-mindie-agent">✨ Why MindIE Agent</a> · <a href="#️-architecture--experience-flywheel">🏗️ Architecture</a> · <a href="#-how-to-use-after-installation-trigger-modes--examples">🔥 Workflows</a> · <a href="#-repository-ecosystem">📦 Ecosystem</a> · <a href="#-contributing-let-your-agent-do-it-too">🤝 Contributing</a> · <a href="#-010-milestone--benchmark-record">🚀 v0.1.0 Benchmarks</a> · <a href="./docs/README.en.md">📚 Docs</a>
</p>

---

## ⚡ Zero-Friction One-Sentence Install (Agent-Only ☕)

Put down the terminal—don't memorize CLI flags or copy-paste setup scripts by hand. Since MindIE Agent is built for AI coding Agents, **we only accept installation by your Agent**.

Open **Claude Code**, **OpenAI Codex CLI**, **Kimi Code**, **DeepSeek Harness**, **Google Antigravity**, or **Tencent WorkBuddy**, and toss this single sentence into your chat:

```text
Please install MindIE Agent for me: https://github.com/mindie-agent/mindie-agent
```

Sit back while your Agent reads this page, verifies a **stable `gh` (GitHub CLI) channel**, detects its own host environment, and executes the **Agent Auto-Install Playbook** below—completing plugin registration, runtime setup, and workspace onboarding end-to-end.

<details>
<summary>🤖 <b>Agent Auto-Install Playbook (Click to expand / Automatically parsed by AI Agents)</b></summary>

> **Instructions for AI Agents**: When the user asks you to install `mindie-agent`, do **not** ask them to read documentation manually. Execute the following five steps in order:
>
> #### Step 1: Verify prerequisites & the `gh` GitHub channel (Hard Requirement)
> **A stable, authenticated GitHub CLI (`gh`) channel is a hard requirement for MindIE Agent**—it powers plugin marketplace fetches, locked release verification, `knowledge-vllm-ascend` corpus sync, automated community PR publication (via `gh api` and process-scoped `!gh auth git-credential`, without mutating global `~/.gitconfig`), and optional issue reporting. Run in the terminal first:
> ```bash
> git --version && uv --version && gh --version
> GH_USER=$(gh api --hostname github.com user --jq .login) && echo "GitHub channel verified for account: $GH_USER"
> ```
> - **Hard Gate (Never skip or silently ignore failures; a DSH `0.1.1` / `0.1.2`-only install without community contribution may skip the `gh` gate but still needs `git` and `uv`)**:
>   - If `gh` is missing: assist the user in installing GitHub CLI for their OS first (macOS: `brew install gh`; Windows: `winget install --id GitHub.cli`; Ubuntu / WSL: `sudo apt update && sudo apt install -y gh`).
>   - Reuse a working account. When login is needed, follow the [GitHub sign-in flow](docs/enterprise-network.en.md#github-sign-in-flow): browser login on ordinary networks, or token login on enterprise networks / blocked browser authorization. Guide creation if needed, receive an existing token through the hidden `gh` prompt, and let `gh` save it. Verify the account, Git and subsequent-process reuse before continuing. Resolve network/proxy/certificate failures as transport problems. Never run `git config --global` or `git config --system` to mutate global Git configuration.
>
> #### Step 2: Preserve consent and prepare contribution targets only when needed
> Installation registers the plugin needed by the current host without silently running Star or Fork commands; right after plugin installation and verification complete, Step 5 invokes the current host's **native interactive question tool** to ask the user about choosing a local development workspace, Community Sharing & Fault Reporting, and optionally giving the project a Star ⭐.
>
> Community contribution is off by default. Only after the user enables contribution to a target corpus `<owner/repo>` does `setup.py sharing --enable` automatically create or reuse that corpus's personal Fork and bind `<GH_USER>/<repo>` as the push target. Do not Fork the main repository, plugin repositories or all domain repositories as an installation step.
>
> #### Step 3: Identify your host environment and install the matching plugin
> Install only the plugin for the current host. Open that adapter repository's install page and run the Agent protocol written there. This page keeps host detection, version pins, and install-page links; current plugin versions are Codex `v0.1.21`, Claude Code `v0.1.17`, Kimi Code `v0.1.17`, DSH `v0.1.16`, Google Antigravity `v0.1.8`, and Tencent WorkBuddy `v0.1.8`. These pins match [`channels/0.1.json`](./channels/0.1.json) and the formal tags on the Codex and DSH install pages at harness `main`. Each plugin discovers shared components from official GitHub Releases.
>
> Select exactly one branch in this order and stop at the first hit. Session markers in the current process outrank a local CLI. `CODEX_THREAD_ID` or `CODEX_CI` selects Branch B even when `claude --version` succeeds. Do not take the first `--version` that exits 0.
>
> 1. `CODEX_THREAD_ID` or `CODEX_CI` in the current process → Branch B.
> 2. `CLAUDECODE` in the current process → Branch A.
> 3. This conversation is already inside Google Antigravity or Tencent WorkBuddy → Branch E or F. Confirm with the app bundle and data directory. There is no `agy` or `cbc` executable on `PATH`.
> 4. `DSH_PROFILE` or `DSH_HOME` in the current process → Branch D.
> 5. `KIMI_CODE_HOME` in the current process → Branch C. A `~/.kimi-code` directory on disk is not a session.
> 6. Otherwise probe `codex --version`, `claude --version`, `kimi --version`, `dsh --version`, and the app bundles named below. If more than one entry exists, ask the user.
>
> - **Branch A — Claude Code**: Install page: [mindie-agent-cc Quick Start](https://github.com/mindie-agent/mindie-agent-cc/blob/v0.1.17/README.en.md#quick-start). Claude Code success version: `v0.1.17` (`mindie-agent@mindie-agent-cc` enabled in `claude plugin list --json`).
> - **Branch B — OpenAI Codex CLI**: Install page: [mindie-agent-codex Quick Start](https://github.com/mindie-agent/mindie-agent-codex/blob/v0.1.21/README.en.md#quick-start). Codex install ref and success version: `v0.1.21` (`mindie-agent@mindie-agent` enabled in `codex plugin list --json`, followed by running `setup.py` for same-session runtime readiness).
> - **Branch C — Kimi Code CLI**: Install page: [mindie-agent-kimi Quick Start](https://github.com/mindie-agent/mindie-agent-kimi/blob/v0.1.17/README.en.md#quick-start).
> - **Branch D — DeepSeek Harness (DSH)**: Install page: [mindie-agent-dsh Quick Start](https://github.com/mindie-agent/mindie-agent-dsh/blob/v0.1.16/README.en.md#quick-start).
> - **Branch E — Google Antigravity**: the macOS app bundle `/Applications/Antigravity.app` (also look for `~/Applications/Antigravity.app`) and the user data directory `~/.gemini/antigravity` (or `~/.gemini/antigravity-cli`, `~/.gemini/antigravity-ide`, `AGY_APP_DATA_DIR`). Install page: [mindie-agent-agy Quick Start](https://github.com/mindie-agent/mindie-agent-agy/blob/v0.1.8/README.en.md#quick-start-one-sentence-agent-install). Clone the pinned `v0.1.8` tag, copy `plugins/mindie-agent` to `~/.gemini/config/plugins/mindie-agent`, and run `uv run --no-project --python 3.13 ~/.gemini/config/plugins/mindie-agent/scripts/setup.py init --workspace-root "$(pwd)"` to provision the persistent source baseline (`agy-source`) and runtime (`agy-venv`).
> - **Branch F — Tencent WorkBuddy / CodeBuddy**: the bundled `codebuddy` binary at `/Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/cli/bin/codebuddy` or `~/Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/cli/bin/codebuddy`, or an existing absolute `MINDIE_WB_BIN`; the config directory is `~/.workbuddy` (absolute `WORKBUDDY_CONFIG_DIR` / `CODEBUDDY_CONFIG_DIR` take precedence). On the pinned tag checkout, run the install page's `setup.py init --install-wb` via `uv run --no-project --python 3.13` and its `codebuddy plugin validate` check. Install page: [mindie-agent-wb Installation](https://github.com/mindie-agent/mindie-agent-wb/blob/v0.1.8/README.en.md#installation).
> - **Branch G — Cursor or another generic MCP client** (`remote-dev` SSH base only): register the stdio server from the [`remote-dev` README](https://github.com/mindie-agent/remote-dev/blob/v0.11.6/README.md). Source pin: `remote-dev@v0.11.6`.
>
> After selecting the single matching branch, install the tag pinned above by following that page, then proceed immediately to Step 4 and Step 5 for interactive onboarding.
>
> #### Step 4: Development workspace onboarding references
> All six full plugin installations support first-time workspace onboarding: reuse verified GitHub authentication, present the user notice, and offer creating/initializing [vllm-ascend-workspace](https://github.com/mindie-agent/vllm-ascend-workspace), reusing an existing directory, or keeping the current directory:
>
> - [Codex Workspace Setup](https://github.com/mindie-agent/mindie-agent-codex/blob/main/plugins/mindie-agent/skills/mindie-agent/references/workspace-setup.md)
> - [Claude Code Workspace Setup](https://github.com/mindie-agent/mindie-agent-cc/blob/main/skills/mindie-agent/references/workspace-setup.md)
> - [Kimi Code Workspace Setup](https://github.com/mindie-agent/mindie-agent-kimi/blob/main/skills/mindie-agent/references/workspace-setup.md)
> - [DSH Workspace Setup](https://github.com/mindie-agent/mindie-agent-dsh/blob/main/skills/mindie-agent/references/workspace-setup.md)
> - [Google Antigravity Workspace Setup](https://github.com/mindie-agent/mindie-agent-agy/blob/main/plugins/mindie-agent/skills/mindie-agent/references/workspace-setup.md)
> - [Tencent WorkBuddy Workspace Setup](https://github.com/mindie-agent/mindie-agent-wb/blob/main/plugins/mindie-agent/skills/mindie-agent/references/workspace-setup.md)
>
> #### Step 5: Pop up native interactive questions (Workspace, Community Sharing & GitHub Star ⭐) and persist choices
> Right after plugin installation and verification complete, check `setup.py sharing --status`; when `needs_onboarding_prompt: true`, **immediately invoke the current host's native interactive question tool** (do not just print plain text asking the user to run CLI commands):
> - **Google Antigravity**: call the native **`ask_question`** tool;
> - **Claude Code / Tencent WorkBuddy / Kimi Code**: call the native **`AskUserQuestion`** tool;
> - **OpenAI Codex CLI / App**: call the native **`request_user_input`** tool;
> - **DeepSeek Harness (DSH)**: call the native question tool if available in the session, or present a structured 3-item numbered choice card (`[1]` / `[2]`) and wait for the user's reply.
>
> Present the following 3 questions (with recommended options first):
> 1. **Local Development Workspace**:
>    - `(Recommended) Initialize vllm-ascend-workspace in current directory`
>    - `Keep current directory as workspace`
>    - `Use an existing workspace directory`
> 2. **Community Knowledge Sharing & Automated Fault Reporting**:
>    - `(Recommended) Enable Community Sharing & Fault Reporting` (auto-fork `mindie-agent/knowledge-vllm-ascend` on demand and share redacted experience & fault diagnostics within the authorized project scope)
>    - `Keep Local-Only Mode (disable outbound sharing & fault reporting)`
> 3. **Would you like to give mindie-agent a Star on GitHub ⭐?**:
>    - `(Recommended) Sure, star it ⭐` (Star `mindie-agent/mindie-agent` on GitHub to support the project)
>    - `Maybe later` (Continue without starring)
>
> **After receiving the user's answers from the native popup, execute in strict order**:
> 1. **Resolve and initialize `WORKSPACE_ROOT` first** (and register the absolute path in the host's native workspace list);
> 2. **Persist the sharing & reporting choice via `setup.py sharing`**:
>    - If enabled: run `setup.py sharing --enable --project-root "$WORKSPACE_ROOT"` (automatically resolves the GitHub account, ensures the personal fork, and updates `mindie-community.json`, `mindie-consent.json`, and `diagnostics.json`);
>    - If disabled: run `setup.py sharing --disable`;
> 3. **Star the repository ⭐ only if explicitly approved**: Only when the user selected the Star option in Question 3, run:
>    ```bash
>    gh api --hostname github.com --silent -X PUT /user/starred/mindie-agent/mindie-agent && gh api --hostname github.com --silent /user/starred/mindie-agent/mindie-agent
>    ```
> 4. **Report final installation summary**: Summarize the verified `gh` account, installed plugin and version, workspace path, `setup.py sharing --status` state, and Star status, and remind the user that `/mindie-agent` activates domain knowledge & Skills while `remote-dev` triggers automatically by default.

</details>

---

## ✨ Why MindIE Agent?

MindIE Agent brings domain knowledge and remote development tools into your existing Claude Code, Codex, Kimi Code, DSH, Google Antigravity, or Tencent WorkBuddy session across `vLLM-Ascend` / `vLLM-Omni`, `xLLM` (`xllm` / `xllm-ops` / `xllm-service` / `xllm-workflow`), `MindIE-SD`, Ascend operators, and distributed inference—covering new model bring-up (0-day adaptation), model and operator performance tuning, and fault diagnosis. See the [architecture](./docs/architecture.en.md) and release records below for implementation and acceptance details.

| Capability | What it helps you do |
| --- | --- |
| **Condition-matched domain knowledge** | Retrieve hardware constraints, diagnostic SOPs, troubleshooting workflows, and operator optimizations on demand—supporting batch `refs` explanation with shared `known_refs` and `token_budget`, plus `rejected_history` and `affected_components` provenance |
| **Remote NPU development and validation** | Use [`remote-dev`](https://github.com/mindie-agent/remote-dev) to edit files, apply patches, run commands, manage long-running background jobs, and inspect logs across SSH hosts and Docker containers with destructive-command safety guards and shared `~/.mindie/ssh/id_ed25519` credential fallback |
| **Profiling analysis & performance modeling** | Use [`profiler`](https://github.com/mindie-agent/profiler) for in-place Ascend `msprof` analysis, `analyze_profiling --structure` 3-state topology alignment (`aligned / declared_only / unattributed_observed`) on `mindie-model-structure/1`, and `auto_segment_decode_forwards`; use [`sim`](https://github.com/mindie-agent/sim) to model hardware resources, operator families, subgraphs, pure-model costs, and serving constraints (`DP × TP × EP × PP × DCP / DSA-CP / PCP` & PD disaggregation) with network-tier utilization, DeepEP, AFD, multi-tier KV/expert offload, 4D efficiency breakdown (`Cube_MFU / Vec_MFU / MBU / Link_Util / CV_Overlap`), and 30ms SLA hardware scaling |
| **Resource coordination, NPU debugging & diagnostics** | Use [`coordinator`](https://github.com/mindie-agent/coordinator) for per-Die HBM leases, compile slot budgets, and port arbitration, [`npu-top`](https://github.com/mindie-agent/npu-top) for live A2/A3/A5 cluster monitoring with `~/.mindie/ssh` fallback, [`debugger`](https://github.com/mindie-agent/debugger) for target CANN/`plog` fault triage, 3-primitive precision/memory-stomp localization, and `ACLGraph` debugging, and [`diagnostics`](https://github.com/mindie-agent/diagnostics) for local fault logging and bounded 2-attempt outbound issue reconciliation |
| **Experience distillation & reuse** | Redact and save troubleshooting records within your authorized project scope, distill verified fixes into reusable knowledge entries, and optionally contribute them back to the community |

Plugins preserve your host agent's native session and tool loop, loading domain knowledge on demand. See the [knowledge system](./docs/knowledge-system.en.md) for details.

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
    DSH["DeepSeek Harness"]
    AGY["Google Antigravity"]
    WB["Tencent WorkBuddy"]
  end

  subgraph Adapters["🔌 Thin Native Harness Plugins"]
    P_CC["mindie-agent-cc"]
    P_Codex["mindie-agent-codex"]
    P_Kimi["mindie-agent-kimi"]
    P_DSH["mindie-agent-dsh"]
    P_AGY["mindie-agent-agy"]
    P_WB["mindie-agent-wb"]
  end

  subgraph Core["⚙️ Shared Runtime Components"]
    Knowledge["🧠 mindie-knowledge<br/>Domain Knowledge · Condition Matching · Source Traceability & Feedback"]
    Coord["🎯 coordinator<br/>SSH & Remote Ascend Env Manager · Container Binding · NPU Probe & Leases"]
    RemoteDev["⚡ remote-dev<br/>SSH Files & Commands · Container Execution · Background Jobs"]
    Profiler["🔬 mindie-profiler<br/>In-Place Ascend Profiling · Structure Alignment · Cross-Run Compare"]
    Sim["📐 mindie-sim<br/>5-Layer Causal Engine · 4D Efficiency · SLA Hardware Solver"]
    Debug["🪲 mindie-debugger<br/>CANN/plog Fault Triage · 3-Primitive Precision Debug · ACLGraph Guard"]
    NpuTop["📊 npu-top<br/>Live NPU Web Dashboard · 90-Day Utilization History"]
    Diag["🛡️ mindie-diagnostics<br/>Bounded 4x1 MiB JSONL Logs · Support Bundles · Opt-In Issue Reporter"]
  end

  subgraph Remote["🖥️ Remote Ascend Fleet & Knowledge Repositories"]
    Feed[("📚 9 Ascend Domain Knowledge Corpora<br/>(vLLM-Ascend · xLLM · MindIE-SD · Operators · Infer · Agent Eng)")]
    Cluster[("🚀 Remote Ascend NPU Hosts & Docker Containers")]
  end

  CC --> P_CC
  Codex --> P_Codex
  Kimi --> P_Kimi
  DSH --> P_DSH
  AGY --> P_AGY
  WB --> P_WB

  P_CC & P_Codex & P_Kimi & P_DSH & P_AGY & P_WB --> Knowledge & RemoteDev & Diag & Debug & Profiler & Sim
  Task["Optional TaskClient / coordinator"] --> Coord
  Bench["mindie-bench Evaluation Suite"] --> Task & Clients
  Knowledge <--> Feed
  Coord -- "Syncs endpoints.json / Resolver" --> RemoteDev
  Coord & RemoteDev --> Cluster
  NpuTop -. "Human Web UI (Read-only)" .-> Cluster
```

### 2. Continuous Engineering & Knowledge Loop

```mermaid
sequenceDiagram
  autonumber
  actor Dev as Developer
  participant Agent as Coding Agent (Claude / Codex / Kimi / DSH / Antigravity / WorkBuddy)
  participant Know as mindie-knowledge (Local Service)
  participant NPU as remote-dev (Remote Ascend Container)
  participant Repo as Public Knowledge Repo (knowledge-vllm-ascend, etc.)

  Dev->>Agent: Invoke /mindie-agent + engineering goal (Bring-up / Kernel Dev / Testing / Tuning)
  Agent->>Know: 1. Query by hardware & workload conditions, load matched rules & references
  Agent->>NPU: 2. Edit code, sync patches, and run tests in the target container
  NPU-->>Agent: Return build, accuracy, and performance results with log paths
  Agent-->>Dev: 3. Deliver verified changes and test summary; optionally record feedback
  Note over Agent,Know: Runs in /mindie-agent-enabled sessions when authorized by local consent & project scope
  Agent->>Know: 4. Redact and archive session troubleshooting records
  Agent->>Know: 5. Distill verified fixes into reusable knowledge entries
  Note over Know,Repo: Triggered only when community sharing is enabled
  Know->>Repo: 6. Submit reviewed entries via PR for downstream sync
```

---

## 🔥 How to Use After Installation (Trigger Modes & Examples)

MindIE Agent is built around **simplicity and progressive disclosure**—from the user's perspective, **there is only ONE command to remember: `/mindie-agent`**. You never need to memorize internal subcommands (such as `:init` or `:status`); operational context is loaded on demand:

| Capability Module | Trigger Mode | How It Works |
| --- | --- | --- |
| **🧠 Ascend Domain Knowledge & Skills**<br/>(`mindie-knowledge` + Domain Skills) | **Manual Per-Session Trigger**<br/>(Unified `/mindie-agent` entry) | When adapting a model in `vLLM-Ascend`, writing `AscendC` / `Triton` kernels, adding accuracy tests, or tuning performance, type **`/mindie-agent <your task>`** (or `$mindie-agent` in Codex) once in the current session to enable knowledge search, feedback, distillation, and sync across subsequent turns. Setup, status checks, and preference changes also go through `/mindie-agent` + natural language. |
| **⚡ Remote Ascend Execution & Deterministic Tools**<br/>(`remote-dev` / `coordinator` / `profiler` / `sim` / `diagnostics`) | **Default Auto-Trigger**<br/>(Always available, no `/mindie-agent` needed) | `remote-dev` and deterministic engineering tools are active by default. Whenever you mention a remote server, container, NPU probe/lease, profiling trace, roofline simulation, or factual status check in normal conversation, your Agent **automatically calls** the corresponding tools without requiring `/mindie-agent`. |
| **🔄 Experience Distillation & Community Sharing**<br/>(Redaction, distillation, and review) | **Configure consent once; active in `/mindie-agent` sessions** | Contribution consent (`mindie-consent.json`) is configured once and persists across sessions. In any session enabled via `/mindie-agent`, `Stop` redacts and archives public dialogue within your authorized project scope (ordinary unactivated sessions perform zero `Stop` capture); verified fixes are distilled into reusable knowledge entries and shared when contribution is enabled. |

### Copy-Paste Usage Examples

#### 💡 Example 1: Manually Invoke `/mindie-agent` for Feature Design, Kernel Development & Test Authoring
```text
/mindie-agent I want to design and implement a custom fused operator in vllm-ascend (with Triton / AscendC kernel support) and add unit + accuracy tests. Check MindIE knowledge and existing conventions to propose the design and test plan.
```
> **What happens**: The Agent selects the relevant domain, matches your hardware and framework conditions, and loads the corresponding constraints, reference implementations, and verification checklists.

#### 💡 Example 2: Default Auto-Triggered `remote-dev` for Remote Ascend Container Coding & Testing
```text
Connect to the vllm-dev container on host 192.0.2.21 (port 22), sync my new operator implementation and unit tests into /workspace/vllm-ascend, and run the full pytest accuracy and benchmark suite on the NPU.
```
> **What happens**: Without needing any slash command, your Agent automatically uses `remote_read`, `remote_edit`, and `remote_bash` inside the remote `vllm-dev` container over pooled SSH, turning long build and test runs into managed background jobs with live log streaming.

#### 💡 Example 3: Joint `/mindie-agent` + `remote-dev` Optimization with Experience Distillation
```text
/mindie-agent Using Ascend inference and kernel tuning experience, help me profile decode latency bottlenecks on our remote NPU dev machine, pull the key profiling metrics, and verify an optimization patch.
```
> **What happens**: The Agent combines domain knowledge with remote execution to pinpoint the bottleneck, then verifies numerical accuracy and latency speedup on the NPU. Verified conclusions can be distilled into reusable knowledge entries for future sessions.

---

## 📦 Repository Ecosystem

Every repository under `@mindie-agent` has a clean, single-purpose boundary and can be used together or standalone:

<!-- mindie-org-versions:main-ecosystem-en:start -->
### 1. Product Entry, Benchmarks & Community Catalogue

| Repository | Version | Role |
| --- | --- | --- |
| **[`mindie-agent`](https://github.com/mindie-agent/mindie-agent)** *(This Repo)* | [`v0.1.12`](https://github.com/mindie-agent/mindie-agent/releases/tag/v0.1.12) | Product entry point, system architecture, engineering design principles, release compatibility contracts, and release records |
| **[`mindie-bench`](https://github.com/mindie-agent/mindie-bench)** | [`v0.4.6`](https://github.com/mindie-agent/mindie-bench/releases/tag/v0.4.6) | End-to-end evaluation harness and live NPU benchmark suite: 20 behavioral-oracle tasks (109 3-state & helper controls), Gate Runner, isolated host runs (native knowledge evaluation wiring & `zsh` temp isolation), component benchmarks, and cross-task reuse evaluation |
| **[`awesome-mindie-skills`](https://github.com/mindie-agent/awesome-mindie-skills)** | [`main`](https://github.com/mindie-agent/awesome-mindie-skills) | Curated catalogue of open-source Agent Skills for the Ascend NPU AI Infra workflow (covering `vLLM-Ascend`, `AscendC`/`Triton` kernels, accuracy testing, and profiling) |
| **[`vllm-ascend-workspace`](https://github.com/mindie-agent/vllm-ascend-workspace)** | [`main`](https://github.com/mindie-agent/vllm-ascend-workspace) | Lightweight customizable local workspace for `vLLM` + `vLLM-Ascend` development with isolated task Git Worktrees and MindIE Agent integration |

### 2. Native Harness Plugins

| Repository | Host Client | Version | Role |
| --- | --- | --- | --- |
| **[`mindie-agent-cc`](https://github.com/mindie-agent/mindie-agent-cc)** | **Claude Code** | [`v0.1.17`](https://github.com/mindie-agent/mindie-agent-cc/releases/tag/v0.1.17) | Native Claude Code plugin: lifecycle hooks, MCP stdio bridges, and pinned runtime management |
| **[`mindie-agent-codex`](https://github.com/mindie-agent/mindie-agent-codex)** | **OpenAI Codex CLI** | [`v0.1.21`](https://github.com/mindie-agent/mindie-agent-codex/releases/tag/v0.1.21) | Native OpenAI Codex CLI plugin: marketplace packaging, session redaction, and background service management |
| **[`mindie-agent-kimi`](https://github.com/mindie-agent/mindie-agent-kimi)** | **Kimi Code CLI** | [`v0.1.17`](https://github.com/mindie-agent/mindie-agent-kimi/releases/tag/v0.1.17) | Native Kimi Code plugin: atomic version switching, redacted session capture, and MCP bridging |
| **[`mindie-agent-dsh`](https://github.com/mindie-agent/mindie-agent-dsh)** | **DeepSeek Harness (DSH)** | [`v0.1.16`](https://github.com/mindie-agent/mindie-agent-dsh/releases/tag/v0.1.16) | Native DSH plugin: `/mindie-agent`, knowledge tools, lifecycle bridging, and `remote-dev` integration |
| **[`mindie-agent-agy`](https://github.com/mindie-agent/mindie-agent-agy)** | **Google Antigravity** | [`v0.1.8`](https://github.com/mindie-agent/mindie-agent-agy/releases/tag/v0.1.8) | Native Google Antigravity plugin: per-conversation `/mindie-agent` lease gate, native remote tool aliases, 8-component MCP bridge, and Brain transcript redaction |
| **[`mindie-agent-wb`](https://github.com/mindie-agent/mindie-agent-wb)** | **Tencent WorkBuddy** | [`v0.1.8`](https://github.com/mindie-agent/mindie-agent-wb/releases/tag/v0.1.8) | Native Tencent WorkBuddy / CodeBuddy plugin: dual-surface mounting (WorkBuddy Connector + CodeBuddy native plugin), `/mindie-agent` session gate, and 8-component MCP bridge |

### 3. Shared Runtime Components

| Repository | Package / CLI | Version | Role |
| --- | --- | --- | --- |
| **[`knowledge`](https://github.com/mindie-agent/knowledge)** | `mindie-knowledge` | [`v0.13.14`](https://github.com/mindie-agent/knowledge/releases/tag/v0.13.14) | Graded knowledge unit (L1–L4) management, information-gap retrieval, batch `refs` explanation with shared `known_refs` & `token_budget`, `rejected_history` & `affected_components` provenance, two-layer redaction, and community PR publishing |
| **[`remote-dev`](https://github.com/mindie-agent/remote-dev)** | `remote-dev` | [`v0.11.6`](https://github.com/mindie-agent/remote-dev/releases/tag/v0.11.6) | SSH file and command tools, shared user-private `~/.mindie/ssh/id_ed25519` credential fallback & public-key management, destructive command safety guard, container execution, background jobs, pooled connections, and artifact transfer |
| **[`coordinator`](https://github.com/mindie-agent/coordinator)** | `mindie-coordinator` | [`v0.7.5`](https://github.com/mindie-agent/coordinator/releases/tag/v0.7.5) | SSH & remote Ascend environment manager: host/key inventory, container binding & provisioning, NPU topology probing (`mindie_probe`, A2/A3 dual-Die/A5), HCCL/RoCE preflight, per-Die HBM lease & compile slot budgets (`mindie_lease`), and managed task execution |
| **[`profiler`](https://github.com/mindie-agent/profiler)** | `mindie-profiler` / `mindie_profiler` | [`v0.5.6`](https://github.com/mindie-agent/profiler/releases/tag/v0.5.6) | Ascend profiling collection and in-place analysis component: controlled capture, `inventory / analyze / correlate / compare / sql / camodel / kernels` trace analysis, `analyze_profiling --structure` 3-state topology alignment (`aligned / declared_only / unattributed_observed`) on `mindie-model-structure/1`, Decode/Prefill segmentation, memory breakdown, and cross-run comparison CLI |
| **[`sim`](https://github.com/mindie-agent/sim)** | `mindie-sim` / `mindie_sim` | [`v0.9.4`](https://github.com/mindie-agent/sim/releases/tag/v0.9.4) | Hardware-neutral 5-layer causal performance modeling component: unifies hardware resources, operator families, subgraphs, pure-model costs, and serving constraints (`DP × TP × EP × PP × DCP / DSA-CP / PCP` & PD disaggregation) with deterministic Case synthesis (`compose`), `async_scheduling` delayed KV release, 4D efficiency breakdown (`Cube_MFU / Vec_MFU / MBU / Link_Util / CV_Overlap`), SLA/PD Pareto solvers (`sla / sweep`), multi-DP skew barrier mechanics (`skew`), and Wave 5 1,653-profile A2/A3/A5 in-sample calibration (100% <=10% error) and separate 856-case DSH fleet evaluation (841/856=98.25% overall, 546/561=97.33% independent held-out <=15%) |
| **[`npu-top`](https://github.com/mindie-agent/npu-top)** | `npu-top` | [`v0.3.1`](https://github.com/mindie-agent/npu-top/releases/tag/v0.3.1) | Human-facing Ascend NPU observability dashboard: supports A2 / A3 / A5 fleet monitoring with shared `coordinator` `machines.json` and `~/.mindie/ssh` credential fallback, providing a loopback web UI (`127.0.0.1:8788`), TUI, CLI/MCP, and 90-day SQLite utilization history |
| **[`diagnostics`](https://github.com/mindie-agent/diagnostics)** | `mindie-diagnostics` / `mindie_diagnostics` | [`v0.5.8`](https://github.com/mindie-agent/diagnostics/releases/tag/v0.5.8) | Local fault logging and diagnostics component: CANN/`plog` deterministic error analysis, bounded 4×1 MiB JSONL rotation, redacted support bundles, and opt-in GitHub Issue reporting with bounded 2-attempt outbound reconciliation |
| **[`debugger`](https://github.com/mindie-agent/debugger)** | `mindie-debugger` / `mindie_debugger` | [`v0.1.0`](https://github.com/mindie-agent/debugger/releases/tag/v0.1.0) | Target Ascend NPU fault triage and precision debugging component: deterministic CANN/`plog` fault triage (`npu_fault_triage`), 3-primitive precision/memory-stomp localization (`precision`: `npu-watch` / `call-repro` / `lockstep-diff`), and `ACLGraph` zero-sync in-graph replay dumping, capture guard & static pointer tracking (`aclgraph`) |

### 4. Public Domain Knowledge Corpora

All public knowledge corpora follow the `mindie-graded-unit/1` graded schema (`L1` Canonical Facts & Constraints · `L2` Standard Operating Procedures · `L3` Multi-Stage Workflows · `L4` Optimization Patterns) with explicit applicability conditions and verification evidence:

| Repository | Domain (`domain`) | Units & Pinned Commit | Scope & Coverage |
| --- | --- | --- | --- |
| **[`knowledge-vllm-ascend`](https://github.com/mindie-agent/knowledge-vllm-ascend)** | `vllm-ascend` | 97 units · [`911ed567`](https://github.com/mindie-agent/knowledge-vllm-ascend/tree/911ed567a1011e6ee6578f008c522bde4ac55b4e) | `vLLM-Ascend` & `vLLM-Omni` engineering corpus: 0-day model bring-up, PD disaggregation, MoE EP/MC2, quantization, speculative decoding, ACLGraph/TorchAir, and `vllm-omni` multi-stage omni-modality (`Thinker -> Talker -> Code2Wav` / AR+DiT / TTS / Duplex) pipeline tuning |
| **[`knowledge-xllm`](https://github.com/mindie-agent/knowledge-xllm)** | `xllm` | 24 units · [`23b7b063`](https://github.com/mindie-agent/knowledge-xllm/tree/23b7b0636cfb050ee88e339ecd69aea6f95cae30) | `xLLM` full-stack (`xllm` / `xllm-ops` / `xllm-service` / `xllm-workflow`) Ascend corpus: C++ native `ModelRegistry`, `xTensor` VMM 2 MB physical page pools & weight hot-switching, piecewise ACLGraph, MTP/Eagle-3/Suffix speculative decoding, 48 AscendC custom ops & A5 (`dav-c310`) TileLang AOT kernels, Brpc/etcd/Mooncake PD disaggregation, and `OneRec` recommendation pipelines |
| **[`knowledge-mindie-sd`](https://github.com/mindie-agent/knowledge-mindie-sd)** | `mindie-sd` | 24 units · [`c23ba64a`](https://github.com/mindie-agent/knowledge-mindie-sd/tree/c23ba64ab6c210da5ff34d1f5cdb27eb8e81154e) | `Ascend/MindIE-SD` (`mindiesd`) diffusion acceleration framework corpus: `AttentionConfig`/`Register` dispatch, block-sparse attention (`RainFusion` V1–V3 / `Ada-BSA` / `EagleQBSA`), cross-step caching (`DiTCache` / `Cache-DiT` / `TaylorSeer`), timestep-aware quantization + `Laurel`, Ulysses/Ring/CFG hybrid parallelism, 3D causal VAE sliced decode, `torch_npu._inductor` graph passes, and S0–S6 auto-optimization gates |
| **[`knowledge-operators`](https://github.com/mindie-agent/knowledge-operators)** | `operators` | 103 units · [`0d2aa4b5`](https://github.com/mindie-agent/knowledge-operators/tree/0d2aa4b5387cf3f8d5c46a0703b43dd0adda9c4c) | Ascend operators corpus: 910B / 910C (A3) / 950 (A5) hardware constraints, `AscendC`, `Triton-Ascend`, TileLang, PyPTO, Catlass, FlashAttention/MLA, and Matmul/MoE fusion |
| **[`knowledge-infer-core`](https://github.com/mindie-agent/knowledge-infer-core)** | `infer-core` | 105 units · [`f0d8e7cf`](https://github.com/mindie-agent/knowledge-infer-core/tree/f0d8e7cf3edf41399395f41fd5a42e7b37847264) | Ascend inference serving & engine core corpus: `cann-recipes-infer` 26 model optimization recipes, 16 `model-infer-*` skills, common acceleration modules, and `Ascend/msagent` quantization/accuracy diagnosis workflows |
| **[`knowledge-infer-distributed`](https://github.com/mindie-agent/knowledge-infer-distributed)** | `infer-distributed` | 39 units · [`817d48cb`](https://github.com/mindie-agent/knowledge-infer-distributed/tree/817d48cbf5dae80d607292d486cc07b30c405aa6) | Distributed inference & collective communication corpus: HCCL troubleshooting, RoCE/HCCS topology, SHMEM, Mooncake/Yuanrong transport, and multi-node `DP/TP/EP/PP/DCP/DSA-CP/PCP` plus DiT Ulysses/Ring/CFG hybrid parallelism & power-cap mitigation |
| **[`knowledge-infer-observability`](https://github.com/mindie-agent/knowledge-infer-observability)** | `infer-observability` | 39 units · [`4b3dd86b`](https://github.com/mindie-agent/knowledge-infer-observability/tree/4b3dd86b365c9e588a1eb47df7dcc6437fdf8a89) | Inference observability, diagnostics & benchmarking corpus: CANN/`plog`/device fault triage, `msprof` profiling workflows, analytic simulation, Window A/B/A `perf-gate`, and 3-tier image/video `accuracy-gate` protocols |
| **[`knowledge-infer-ops-compat`](https://github.com/mindie-agent/knowledge-infer-ops-compat)** | `infer-ops-compat` | 34 units · [`c37c9c0f`](https://github.com/mindie-agent/knowledge-infer-ops-compat/tree/c37c9c0f559a27c63948aabc1f5b092de54b8c78) | Graph compilation, custom op registration & migration compatibility corpus: TorchAir/ACLGraph capture, `torch_npu._inductor` pattern pass development, two-stage (`API-first, then compile`) integration, CUDA-to-Ascend migration, and cluster deployment |
| **[`knowledge-agent-engineering`](https://github.com/mindie-agent/knowledge-agent-engineering)** | `agent-engineering` | 32 units · [`3cf3f10c`](https://github.com/mindie-agent/knowledge-agent-engineering/tree/3cf3f10c2c35b801d06b7f410ce2d105e1f31ff1) | Agent engineering & governance corpus: multi-agent orchestration, SOTA exploration loops, `ais_bench` coreset compression, automated Git bisect, `kb-lint` governance, two-layer privacy redaction gates, and benchmark evaluation |
<!-- mindie-org-versions:main-ecosystem-en:end -->

---

## 🧭 Engineering Design Philosophy

MindIE Agent is guided by **18 pragmatic [Engineering Design Principles](./docs/design-principles.en.md)** ([中文](./docs/design-principles.md)) forged through real-world Ascend engineering:

- **Optimize for Total User Goal Cost**: Reliability mechanisms must reduce total comprehension, waiting, and debugging cost—never imposing ceremony on ordinary tasks for rare edge cases.
- **Zero Cognitive Load & On-Demand Intervention**: Tools absorb internal state complexity; Skills stay informational; Knowledge remains advisory with explicit evidence and applicability conditions.
- **Reuse Mature Mechanisms First**: Leverage native host, OS, and mature component capabilities first, and delete obsolete compatibility shims cleanly when upgrading.
- **Transparent State & Fail-Visible Semantics**: Explicitly distinguish completed work, failure, and uncertain external side effects (`unknown`)—never masking failures or blindly replaying uncertain writes.
- **Agent-Native Structure & Bounded Resource Discipline**: Keep core modules `< 800` lines with a four-part contract header in the top 30 lines, and keep resident memory/VRAM strictly bounded with spec-driven local vs. remote placement.

---

## 🤝 Contributing (Let Your Agent Do It Too)

Just like installation, contributing new features, bugfixes, or Ascend domain knowledge to MindIE Agent is **designed to be handed directly to your coding Agent** (every repository under `@mindie-agent` is 100% written, tested, and maintained by Agents).

To keep 13+ repositories clean, fast, and free of over-defensive bloat or host pollution, contributing Agents follow **two mandatory gates** (see **[`CONTRIBUTING.en.md`](./CONTRIBUTING.en.md)** · **[中文](./CONTRIBUTING.md)**):

1. **📖 Before Coding: Read the Design Principles First** — Before touching code, your Agent must read [`AGENTS.md`](./AGENTS.md) and [`docs/design-principles.en.md`](./docs/design-principles.en.md) to align on single-purpose boundaries, fail-visible semantics, timeout arithmetic, the four anti-over-defensive iron rules, `< 800`-line modules with top headers, and bounded memory/VRAM design rules.
2. **✅ After PR Submission: Complete the Pre-PR Checklist Self-Review (Including Format Hygiene)** — After submitting a PR, your Agent must audit its final `git diff` against [`.github/pull_request_template.md`](./.github/pull_request_template.md) (checking all items `1–8` through `15`, including repository formatting hygiene such as mandatory Unix `LF` `\n` line endings, and filling in concrete review evidence and executed test results) and pass the automated CI gates ([`check_lf_eol.py`](./.github/scripts/check_lf_eol.py) + [`check_pr_checklist.py`](./.github/scripts/check_pr_checklist.py)).

To contribute, simply copy and send this prompt to your Agent:

```text
I want to contribute a change to MindIE Agent: <describe your feature, bugfix, or Ascend knowledge addition in one sentence>.
Please follow https://github.com/mindie-agent/mindie-agent/blob/main/CONTRIBUTING.en.md:
1. Read AGENTS.md and docs/design-principles.en.md before writing any code;
2. Implement the change with tiered tests, open a PR, and complete the Pre-PR Checklist self-review and verification evidence in .github/pull_request_template.md.
```

---

## 🚀 0.1.0 Milestone & Benchmark Record

- **Recent `0.1` Track Highlights** (exact release pins in [`channels/0.1.json`](./channels/0.1.json)):
  - **`0.1.7` Patch: Native Tencent WorkBuddy Plugin, Standalone `mindie-debugger` Component, Configurable `mindie-sim` Modeling, 9-Corpus Synchronization & 100% Real `vllm-ascend` 8-Component `G0–G5` Benchmark ([0.1.7 Release Notes](./docs/releases/0.1.7.en.md) · [中文](./docs/releases/0.1.7.md) · [V2 Benchmark Report](./docs/releases/0.1.7/g0-g5-vllm-ascend-v2-report.en.md) · [144-Trial Summary JSON](./docs/releases/0.1.7/g0-g5-vllm-ascend-v2-summary.json))**: Introduces the sixth official native host plugin [`mindie-agent-wb v0.1.8`](https://github.com/mindie-agent/mindie-agent-wb) (Tencent WorkBuddy / CodeBuddy Agent CLI, supporting dual-surface mounting as both a WorkBuddy Connector and a CodeBuddy native plugin) and launches the eighth standalone shared runtime component [`mindie-debugger v0.1.0`](https://github.com/mindie-agent/debugger) (providing target Ascend NPU `npu_fault_triage` CANN/`plog` root-cause triage, `precision` 3-primitive precision/memory-stomp localization, and `aclgraph` zero-sync in-graph replay dumping & capture guards, cleanly decoupled from [`diagnostics v0.5.5`](https://github.com/mindie-agent/diagnostics) which handles Agent local rotation logs and issue reporting); publishes [`mindie-sim v0.9.2`](https://github.com/mindie-agent/sim) (network-tier effective bandwidth utilization, DeepEP low-latency/high-throughput modes, AFD Attention–FFN disaggregation, multi-tier KV/expert offload, Ascend 950PR/950DT hardware profiles, and online serving arrival modeling), [`mindie-profiler v0.5.6`](https://github.com/mindie-agent/profiler) (`export-calibration` one-click simulation calibration bundle export), [`knowledge v0.13.10`](https://github.com/mindie-agent/knowledge), [`coordinator v0.7.3`](https://github.com/mindie-agent/coordinator), [`remote-dev v0.11.4`](https://github.com/mindie-agent/remote-dev), [`npu-top v0.3.1`](https://github.com/mindie-agent/npu-top), and [`mindie-bench v0.4.6`](https://github.com/mindie-agent/mindie-bench), updates all 6 native host plugins (`Codex v0.1.17`, `Claude Code v0.1.13`, `Kimi v0.1.13`, `DSH v0.1.12`, `Google Antigravity v0.1.3`, `Tencent WorkBuddy v0.1.2`) with forward-compatible SemVer intervals, expands public domain knowledge to 9 corpora (adding `knowledge-xllm` and `knowledge-mindie-sd`, totaling `493` graded units), and completes the **V2 100% real `vllm_ascend/...` 8-component & `G0–G5` benchmark across 34 tasks and 144 trials (100% Three-Gate audit compliance)**: `mindie-debugger` lifts DSH solve rate from **`80.0% -> 100.0%`** (`D4` ACLGraph `0.0 -> 1.0`) and cuts Codex L2 debugging time by **`-33.8%` (`1.51x`)** and output tokens by **`-39.5%`**; `mindie-sim` + `mindie-profiler` cuts MLA Decode optimization tokens by **`-17.5%`**; `coordinator` + `npu-top` speeds up dual-Die binding & ModelSlim header preflight TTFE by **`1.86x–2.46x`**; across 6 core `vllm-ascend` L2 tasks, overall solve rate doubles from **`25.0% -> 50.0%` (DSH `16.7% -> 50.0%`, `3.0x` lift)**; `G3` cross-task distillation on the new KDA Varlen Chunk pair achieves **`1.30x` speedup (`-23.2%`)** on DSH and **`-35.7%` turns / `-36.5%` tokens** on Codex; and `G4` RSI exploration on MLA Prolog fusion jumps from **`G0 = 0.0 -> G2 = 1.0 -> G4 = 1.0`** on DSH (**`G4` beats `G2` by `1.19x` time and `-20.4%` tokens**).
  - **`0.1.6` Patch: Automatic-Update Readiness Gates, Wave 5 Multi-Chip Calibration & 5-Host Compatibility ([0.1.6 Release Notes](./docs/releases/0.1.6.en.md) · [中文](./docs/releases/0.1.6.md))**: Delivers `mindie-knowledge v0.13.8` monotonic unit revision advancement and repair tolerance, `mindie-coordinator v0.7.1` native Antigravity session discovery, `mindie-sim v0.9.1` `async_scheduling` delayed HBM release and `compose` Case synthesizer, and `mindie-profiler v0.5.5` Wave 5 1,653-profile A2/A3/A5 100% `<= 10%` in-sample calibration.
  - **`0.1.5` Patch: Native Google Antigravity Plugin & Full `G0–G5` Benchmark Verification ([0.1.5 Release Notes](./docs/releases/0.1.5.en.md) · [中文](./docs/releases/0.1.5.md))**: Introduces the fifth official native host plugin [`mindie-agent-agy v0.1.8`](https://github.com/mindie-agent/mindie-agent-agy) (Google Antigravity), completing adaptation across shared runtime components with native Antigravity tool aliases, `AGY_CONVERSATION_ID` lease propagation, and Brain transcript redaction; delivers the full `G0–G5` benchmark evaluation on zero-spoiler colloquial developer bug-report prompts (1-sentence model + config + symptom + raw traceback/log path) across DSH (`deepseek-flash` / `max`) and Codex (`gpt-6.1-sol` / `xhigh`): on the 48-trial L2 primary matrix, `G2` lifts pass rate **4.0x from `12.5% (2/16)` on `G0/G1` to `50.0% (8/16)`** while cutting latency by **`21.2%–47.1%`** (`vllm-ascend` core tasks `0.0% → 37.5%` / DSH `50.0%`, 4 component tasks `25.0% → 62.5%` / Codex `75.0%`); on live A3 NPU L3, `G1` (`remote-dev`) unlocks live verification (`0.0 → 1.0`); on `G3` cross-task distillation, DSH jumps **`0.0 → 1.0`** on Partial RoPE and Codex cuts tool calls by **`58.5%–63.4%`** and wall time by **`-19.8%`** on SFA MTP; on `G4` RSI exploration, Codex achieves **`0.0 → 1.0` (`-27.8%`)** on `dsv4-sparse-mla` and **`-30.9%` speedup** on `triton-spatial-norm`; and on `G5` 5-episode evolution (`82 → 83 → 84` units), Codex verifies zero regression and **`-19.8%` faster (`153.29s`)** execution after accumulating both positive and negative boundary units.
  - **`0.1.4` Patch & Core Component Upgrades ([0.1.4 Release Notes](./docs/releases/0.1.4.en.md) · [中文](./docs/releases/0.1.4.md) · [Auto-Update Acceptance](./docs/releases/0.1.4/automatic-update-acceptance.json) · [Knowledge Retrieval & Dual-Host Convergence](./docs/audits/2026-10-29-knowledge-p0.md))**: Delivers information-gap retrieval across all four hosts, shared explanation budgets, exact prerequisite citations, and automated managed-component upgrades; on the natural-language `mindie-bench` task suite, **both DSH (`deepseek-flash` / `max`) and Codex (`gpt-6.1-sol` / `xhigh`) achieve `6/6` natural `completed_pass`** across single-site SFA, two-site DSpark, and complex Profiler reconciliation tasks (DSH complex task converges in **17 calls / `67.05s`** vs. previous 50-call budget exhaustion, and Codex drops from `410.30s` to **16 calls / `132.97s`**); aligns with formal releases `mindie-sim v0.8.1` (5-layer unified causal modeling, 4D efficiency breakdown, 30ms SLA hardware scaling solver, converged across 280 Decode + 15 Prefill cases), `mindie-profiler v0.5.3` (`mindie-model-structure/1` topology-guided alignment & automatic Decode segmentation, 856-case DSH fleet replay at `841/856 = 98.25%` overall and `546/561 = 97.33%` on independent held-out cases within `<= 15%` error), and `remote-dev v0.11.2`.
  - **`0.1.3` / `0.1.2` / `0.1.1` Patches**: [**0.1.3**](./docs/releases/0.1.3.en.md) completes the three-server MCP surface (`knowledge`, `remote`, `components`) across all four hosts; [**0.1.2**](./docs/releases/0.1.2.en.md) delivers shared cross-process user-private SSH credentials and key management ([SSH Acceptance](./docs/releases/0.1.2/ssh-auth-acceptance.json)); [**0.1.1**](./docs/releases/0.1.1.en.md) delivers per-session manual `/mindie-agent` activation, whole-delivery token budget estimation, dual-Die placement, and the `G5` dev pilot report ([Pilot Report](./docs/releases/0.1.1/benchmark-pilot.en.md) · [Native Update Acceptance](./docs/releases/0.1.1/native-update-acceptance.json)).

> **2026-10-29 Behavioral Oracle Hardening & Zero-Model Historical Archive Re-evaluation ([Full Audit & Re-evaluation Report](./docs/audits/2026-10-23-mindie-bench-integrity.md))**:
> Following the audit of legacy static source-matching verifiers, `mindie-bench` hardened all **20 benchmark task oracles into real subprocess behavioral verifiers** and verified **109 three-state and helper-variant controls** (`base` must fail, `negative_control` must fail, `gold` must pass; `all_three_state_and_helpers_passed = true`). Without making any new model calls and preserving original wall times and token ledgers, we re-evaluated all **74 primary trials** with recorded candidate diffs in `agent-trials-109.json`:
> - **Re-evaluated Ledger**: `49` historical passing trials were confirmed by behavioral execution (`completed_pass -> 1.0`), while `5` historical failures and `1` `unknown` trial recovered under behavioral execution—yielding **`55` behavioral passes (`reward = 1.0`)**, **`18` behavioral assertion failures (`reward = 0.0`)**, and **`1` `unmeasured` trial (`unsupported_cpu_execution`)**.
> - **Evidence Scope Boundaries**: Each of the 20 tasks is explicitly tagged by its execution substrate—8 CPU behavioral reproduction tasks (`cpu_behavior`), 4 controlled component fixture tasks (`controlled_offline_fixture`), 4 G4 operator-fusion tensor & ablation contract tasks (`controlled_cpu_tensor_and_ablation_contract`), 2 CPU RoPE tensor correctness tasks (`cpu_tensor_correctness`), and 2 live Ascend NPU RoPE tensor correctness tasks (`npu_tensor_correctness`). The original `v0.1.0` benchmark summary is retained below for historical traceability.

The latest feature milestone is **[`v0.1.0`](./docs/releases/0.1.0.en.md)** ([中文发布说明](./docs/releases/0.1.0.md) · [18-Task Full Benchmark Report](./docs/releases/0.1.0/value-results.md) · [109-Trial Redacted Manifest (`agent-trials-109.json`)](./docs/releases/0.1.0/agent-trials-109.json) · [Component Benchmark Manifest (`value-results.json`)](./docs/releases/0.1.0/value-results.json) · [Author's Note & Design Philosophy](./docs/releases/0.1.0/design-philosophy.en.md) · [`channels/0.1.json`](./channels/0.1.json)). `v0.1.0` marks MindIE Agent's evolution from the `0.0.1` prototype into an intelligent R&D and verification substrate for Ascend NPU AI Infra, covering 18 engineering tasks, `109` primary trials, all 7 shared runtime components, and 3 hardware platforms × 4 host plugins:

1. **`mindie-bench` Dual-Model (`codex + home/codex/gpt-6.1-sol (xhigh)` & `dsh + deepseek-flash (max)`) Controlled Ablation Across 18 Engineering Tasks & `109` End-to-End Trials (`G0 → G1 → G2 → G3 → G4`, Including Live `Ascend950DT` NPUs)**:
   - **`G0 → G1 → G2` (`remote-dev` + `knowledge` L1–L4 Progressive Disclosure)**: Accelerates cross-module L2/L3 vague troubleshooting tasks by **`1.80x – 2.77x`**, cuts token consumption by **`15% – 76%`**, and bounds single-task knowledge reading to **`4,814–5,599` tokens (`< 8,000` ceiling)** (note: when a local single-file traceback is already self-contained, extra `knowledge_query` round-trips can incur negative latency deltas; see [`value-results.md`](./docs/releases/0.1.0/value-results.md) for the full distribution);
   - **`G2 → G3` (`Stop` Capture + `C6` Structured Experience Distillation Flywheel)**: On sibling L2 and live L3 black-box `.so` NPU transfer tasks (`rotary_dim=64 → 32`), lifts `codex (xhigh)` first-pass solve rate from **`0% (0/3 across G0/G1/G2) → 100% (1/1 on G3)`** (**`3.44x` speedup** on live L3 NPU with `codex xhigh`; `dsh` solved `G0–G3` and reduced L3 delivery latency from `217.5s` to `171.9s`);
   - **`G2 → G4` (`mode="reuse" → mode="explore"` De-Biased Exploration + Leave-One-Out Ablation)**: Achieves **`G0 (0/8, 0%) / G2 (0/8, 0%) → G4 (8/8, 100%)`** across 2 operator problem families × L2/L3 = 4 fusion tasks × 2 models (with `knowledge_gradient = "near_exact"` factor-graph exploration guidance).
   - **Evaluation Scope & Reproducibility Note**: The `109` trials represent an author-constructed controlled ablation benchmark (`repetitions = 1` per cell; `home/codex/gpt-6.1-sol` and `deepseek-flash` are internal metering-relay aliases that external users can replace with public API endpoints). All 109 primary trials plus 55 supplementary/retry receipts are published in [`agent-trials-109.json`](./docs/releases/0.1.0/agent-trials-109.json), and the 2026-10-29 behavioral re-evaluation ledger is documented in [`docs/audits/2026-10-23-mindie-bench-integrity.md`](./docs/audits/2026-10-23-mindie-bench-integrity.md).
2. **Real Agent Closed-Loop & Component Benchmarks Across All 7 Shared Runtime Components (`profiler`, `sim`, `diagnostics`, `coordinator`, `npu-top`, `remote-dev`, `knowledge`)**:
   - On 4 dedicated component repair tasks, both models lift solve rate from **`75% (3/4) → 100% (4/4)`**, reduce total delivery time by **`-17.1% to -33.8%`**, and cut output tokens by **`-25.2% to -34.1%`**:

| Component / Benchmark Suite | Version | Measured Gains & Key Takeaways |
| --- | --- | --- |
| **⚡ `remote-dev` Remote Container & Long-Job Execution** | `v0.10.4` → `v0.11.2` | On L2/L3 live Ascend tasks, delivers **`1.55x – 2.06x` speedups** over bare host baselines on `dspark-mrv2` / `l3-dspark-mrv2` and solves `quarot` quantization bugfix **`3/3` runs**; `v0.11.2` adds shared cross-process `~/.mindie/ssh/id_ed25519` credential fallback, key maintenance, and destructive-command safety guards |
| **🎯 `coordinator` Multi-Agent Anti-Collision & A5 Preflight** | `v0.6.2` → `v0.7.0` | Accelerates real Agent multi-Die lease repair tasks by **`1.17x – 2.08x`**; under 2-agent contention, eliminates port conflicts (**`3 → 0`**) and duplicate device selections (**`3 → 0`**) with **`~1.9 ms`** lease handoff; adds Ascend A2/A3 dual-Die/A5 topology, HCCL/RoCE preflight, per-Die HBM lease budgets, and compile slot controls |
| **🔬 `profiler` Slow-Rank / Slow-Link & Structure Alignment** | `v0.5.0` → `v0.5.3` | Lifts real Agent `msprof` straggler/HBM repair solve rate from **`0% (G0) → 100% (G2)`** across both models (**`-29.7% to -34.6%` faster**); in-place read-only analysis (`~7.6 ms`) **100% separates slow-link (`Comm`) from slow-rank (`Attention`)** and attributes **`99%` of peak HBM**; `v0.5.3` adds `analyze_profiling --structure` 3-state alignment (`aligned / declared_only / unattributed_observed`), `auto_segment_decode_forwards`, and 856-case fleet replay verification |
| **📐 `sim` 5-Layer Causal Modeling & SLA Hardware Scaling** | `v0.7.0` → `v0.8.1` | **100% adopted by both models** in `v0.1.0` tasks for subgraph fusion screening and A3 Qwen2.5-7B TPOT prediction (**`-4.14%`**); `v0.8.1` unifies all 5 modeling layers (`DP × TP × EP × PP × DCP / DSA-CP / PCP` & PD disaggregation) with 4D efficiency breakdown (`Cube_MFU / Vec_MFU / MBU / Link_Util / CV_Overlap`) and 30ms SLA scaling solver, converging on **280 Decode + 15 Prefill cases** and achieving **`841/856 = 98.25%` overall (`546/561 = 97.33%` on independent held-out cases) within `<= 15%` error** across the **856-case DSH fleet benchmark** (see [Simulation System Design](./docs/simulation-system.md)) |
| **📊 `npu-top` & 🛡️ `diagnostics` Observability & Triage** | `v0.3.0` / `v0.5.4` | Accelerates real Agent 8-rank cascading `plog` triage by **`1.31x – 1.82x`** with **`-34.2% to -37.6%` fewer output tokens**, **100% pinpointing root-cause `Rank 3` (`aicore_memory_or_tiling`) and separating cascading `Rank 7` timeouts**; `npu-top` supports A2/A3/A5 + `~/.mindie/ssh` fallback, and `diagnostics` enforces bounded 2-attempt outbound issue reconciliation |
| **🧠 `knowledge` Progressive Disclosure & Closed-Loop Flywheel** | `v0.13.0` → `v0.13.7` | All 7 public Ascend corpora (`450` graded `L1–L4` units) ready; supports batch `refs` explanation with shared `known_refs` and `token_budget`, plus `rejected_history` and `affected_components` provenance, bounding single-task reading at **`4,814–5,599` tokens (`< 8,000` ceiling)** and powering `100%` solve rates on `G3` black-box transfer and `G4` `mode="explore"` fusion tasks |

3. **3-Platform (`macOS` / `Windows WSL2` / `Windows 11 PowerShell`) × 4-Plugin Full-Matrix Verification**:
   - Completed end-to-end onboarding and full regression suites across all 3 OS hardware platforms and all 4 native host plugins (Claude Code / OpenAI Codex / Kimi Code / DeepSeek Harness), passing **`15,595+` tests (`0 failed`)**.

---

## 📚 Documentation Center

See **[`docs/README.en.md`](./docs/README.en.md)** (**[中文文档中心](./docs/README.md)**) for the complete documentation suite:

| Topic | 中文 | English |
| --- | --- | --- |
| **`v0.1.7` Patch Notes: Native Tencent WorkBuddy Plugin, `mindie-debugger` Component, Configurable `mindie-sim`, 9 Corpora & V2 8-Component `G0–G5` Benchmark (Current)** | [docs/releases/0.1.7.md](./docs/releases/0.1.7.md) · [实测报告](./docs/releases/0.1.7/g0-g5-vllm-ascend-v2-report.md) | [docs/releases/0.1.7.en.md](./docs/releases/0.1.7.en.md) · [Benchmark Report](./docs/releases/0.1.7/g0-g5-vllm-ascend-v2-report.en.md) |
| **`v0.1.6` Patch Notes: Auto-Update Readiness Gates, Wave 5 Calibration & 5-Host Compatibility** | [docs/releases/0.1.6.md](./docs/releases/0.1.6.md) | [docs/releases/0.1.6.en.md](./docs/releases/0.1.6.en.md) |
| **`v0.1.5` Patch Notes: Native Google Antigravity Plugin & Full `G0–G5` Benchmarks** | [docs/releases/0.1.5.md](./docs/releases/0.1.5.md) | [docs/releases/0.1.5.en.md](./docs/releases/0.1.5.en.md) |
| **`v0.1.4` Patch Notes: On-Demand Knowledge & Managed Updates** | [docs/releases/0.1.4.md](./docs/releases/0.1.4.md) | [docs/releases/0.1.4.en.md](./docs/releases/0.1.4.en.md) |
| **`v0.1.3` Patch Notes: 4-Host MCP Completeness & `profiler 0.5.1`** | [docs/releases/0.1.3.md](./docs/releases/0.1.3.md) | [docs/releases/0.1.3.en.md](./docs/releases/0.1.3.en.md) |
| **`v0.1.2` Patch Notes & SSH Authentication Acceptance** | [docs/releases/0.1.2.md](./docs/releases/0.1.2.md) · [认证验收](./docs/releases/0.1.2/ssh-auth-acceptance.json) | [docs/releases/0.1.2.en.md](./docs/releases/0.1.2.en.md) · [SSH Acceptance](./docs/releases/0.1.2/ssh-auth-acceptance.json) |
| **`v0.1.1` Patch Notes & Dev Pilot Report** | [docs/releases/0.1.1.md](./docs/releases/0.1.1.md) · [试点报告](./docs/releases/0.1.1/benchmark-pilot.md) | [docs/releases/0.1.1.en.md](./docs/releases/0.1.1.en.md) · [Pilot Report](./docs/releases/0.1.1/benchmark-pilot.en.md) |
| **`v0.1.0` Official Release & Full Benchmark Report** | [docs/releases/0.1.0.md](./docs/releases/0.1.0.md) · [实测报告](./docs/releases/0.1.0/value-results.md) | [docs/releases/0.1.0.en.md](./docs/releases/0.1.0.en.md) · [Benchmark Report](./docs/releases/0.1.0/value-results.md) |
| **`v0.1.0` Author's Note & Architectural Philosophy** | [docs/releases/0.1.0/design-philosophy.md](./docs/releases/0.1.0/design-philosophy.md) | [docs/releases/0.1.0/design-philosophy.en.md](./docs/releases/0.1.0/design-philosophy.en.md) |
| **`v0.0.3` Release & Benchmark Report** | [docs/releases/0.0.3.md](./docs/releases/0.0.3.md) | [docs/releases/0.0.3.en.md](./docs/releases/0.0.3.en.md) |
| **`v0.0.2` Release & Benchmark Report** | [docs/releases/0.0.2.md](./docs/releases/0.0.2.md) | [docs/releases/0.0.2.en.md](./docs/releases/0.0.2.en.md) |
| **System Architecture & Domain Boundaries** | [docs/architecture.md](./docs/architecture.md) | [docs/architecture.en.md](./docs/architecture.en.md) |
| **Engineering Design Principles** | [docs/design-principles.md](./docs/design-principles.md) | [docs/design-principles.en.md](./docs/design-principles.en.md) |
| **Contributing Guide (Agent-First Workflow & PR Self-Review Gate)** | [CONTRIBUTING.md](./CONTRIBUTING.md) | [CONTRIBUTING.en.md](./CONTRIBUTING.en.md) |
| **Knowledge & Experience System** | [docs/knowledge-system.md](./docs/knowledge-system.md) | [docs/knowledge-system.en.md](./docs/knowledge-system.en.md) |
| **Context, Experience & Exploration Design** | [docs/knowledge-context-and-exploration.md](./docs/knowledge-context-and-exploration.md) | [docs/knowledge-context-and-exploration.en.md](./docs/knowledge-context-and-exploration.en.md) |
| **Agent-Facing Profiler System Design (`mindie-profiler`)** | [docs/profiler-system.md](./docs/profiler-system.md) | [docs/profiler-system.en.md](./docs/profiler-system.en.md) |
| **Agent-Facing General Performance Modeling (`mindie-sim`)** | [docs/simulation-system.md](./docs/simulation-system.md) | — |
| **Profiler & Sim Structure Reuse & Alignment Contract** | [docs/profiler-sim-structure.md](./docs/profiler-sim-structure.md) | — |
| **2026-10-29 Benchmark Oracle Hardening & Archive Re-evaluation Report** | [docs/audits/2026-10-23-mindie-bench-integrity.md](./docs/audits/2026-10-23-mindie-bench-integrity.md) | — |
| **Core Implementation & Knowledge Evolution Design** | [docs/core-implementation-and-geak-evolution-design.md](./docs/core-implementation-and-geak-evolution-design.md) | — |
| **Harness Boundary, Consent & Lifecycle** | [docs/harness-boundary-and-lifecycle.md](./docs/harness-boundary-and-lifecycle.md) | [docs/harness-boundary-and-lifecycle.en.md](./docs/harness-boundary-and-lifecycle.en.md) |
| **Native Runtime Reuse** | [docs/native-runtime-reuse.md](./docs/native-runtime-reuse.md) | [docs/native-runtime-reuse.en.md](./docs/native-runtime-reuse.en.md) |
| **Release Compatibility & Silent Update** | [docs/release-compatibility-and-update.md](./docs/release-compatibility-and-update.md) | [docs/release-compatibility-and-update.en.md](./docs/release-compatibility-and-update.en.md) |
| **Structured Diagnostics & Issue Reporting** | [docs/diagnostics-and-reporting.md](./docs/diagnostics-and-reporting.md) | [docs/diagnostics-and-reporting.en.md](./docs/diagnostics-and-reporting.en.md) |
| **Tiered Testing Architecture** | [docs/testing-architecture.md](./docs/testing-architecture.md) | [docs/testing-architecture.en.md](./docs/testing-architecture.en.md) |
| **L1–L4 Tiered Knowledge & System Testing Plan** | [docs/knowledge-tiered-testing-plan.md](./docs/knowledge-tiered-testing-plan.md) | — |
| **Roadmap & Next Steps** | [docs/next-steps.md](./docs/next-steps.md) | [docs/next-steps.en.md](./docs/next-steps.en.md) |
| **`v0.0.1` Release Record** | [docs/releases/0.0.1.md](./docs/releases/0.0.1.md) | [docs/releases/0.0.1.en.md](./docs/releases/0.0.1.en.md) |

---

## 📊 Repository & Download Statistics

<p align="center">
  <a href="https://github.com/mindie-agent/mindie-agent/blob/telemetry-data/README.md">
    <img src="https://raw.githubusercontent.com/mindie-agent/mindie-agent/telemetry-data/dashboard.en.svg" alt="MindIE Agent Repository & Download Statistics" width="100%">
  </a>
</p>

# 参与贡献指南 (Contributing to MindIE Agent)

**中文** · [English](./CONTRIBUTING.en.md) · [返回首页](./README.md) · [工程设计原则](./docs/design-principles.md)

欢迎来到 **MindIE Agent**！🎉

`@mindie-agent` 组织下的全部仓库都是 **100% Agent-Native 代码库**——从架构演进、代码实现、真机分层测试到 PR 自检，全部面向编程 Agent 协同设计。无论你是只克隆了当前 `mindie-agent` 主入口仓，还是已经在本地检出了多个子仓库，都可以直接把需求交给你的编程 Agent 推进。

---

## ⚡ 一句话让你的 Agent 开始贡献（支持仅克隆主仓起步）

打开 **Claude Code**、**OpenAI Codex CLI**、**Kimi Code**、**DeepSeek Harness (DSH)**、**Google Antigravity**、**Tencent WorkBuddy** 或 **OpenCode**，复制以下提示词并填入你的想法：

```text
我想给 MindIE Agent 贡献一个改动：<用一句话描述你想新增的特性、修复的 Bug 或补充的昇腾知识>。
请严格按照 https://github.com/mindie-agent/mindie-agent/blob/main/CONTRIBUTING.md 的流程执行：
1. 先读 AGENTS.md 的仓库路由表，定位单一职责目标仓库；若本地尚未检出，按平铺兄弟目录 ../<repo> 懒加载克隆并在 ../.worktrees/<repo>-<topic> 创建独立 Git Worktree；
2. 进入目标仓库后立即读取其 AGENTS.md 与 CONTRIBUTING.md（及主仓 docs/design-principles.md）；
3. 完成实现与隔离分层测试后提交 PR，并按该仓库对应的 --profile 完成 Pre-PR Checklist 自检与证据回填。
```

---

## 🌳 跨仓路由与 Git Worktree 协同工作流（从只克隆 `mindie-agent` 到修改任意子仓）

`mindie-agent` 主仓仅承载**顶层架构、活文档（`docs/`）、发布通道（`channels/0.1.json`）与跨仓契约门禁（`.github/scripts/`）**，不包含任何运行时业务代码。当你只克隆了 `mindie-agent` 却希望让 Agent 修改 `harness`、`coordinator`、`remote-dev`、`sim` 等兄弟仓库时，请采用统一的**平铺兄弟目录 + 链接工作树（Linked Worktree）**布局：

```text
<workspace-parent>/
├── mindie-agent/                     # 主入口与架构/门禁仓
├── harness/                          # 按需懒加载克隆的目标基准仓（提供共享 .git 对象库）
├── coordinator/                      # 按需懒加载克隆的其他兄弟仓
└── .worktrees/                       # 隔离特性分支工作树目录（多任务互不干扰）
    ├── mindie-agent-docs-fix/
    ├── harness-win32-job/
    └── coordinator-a3-lease/
```

### 1. 按需懒加载克隆（Lazy Clone）与创建隔离 Worktree

无需一次性拉取全部二十多个仓库，只需拉取本次任务涉及的目标仓库：

```bash
# 在 mindie-agent 目录下执行：按需无 Blob 过滤克隆目标兄弟仓，并切出独立 Worktree
[ -d ../coordinator/.git ] || git clone --filter=blob:none https://github.com/mindie-agent/coordinator.git ../coordinator
git -C ../coordinator worktree add ../.worktrees/coordinator-my-fix -b fix/my-fix
```

> **目标仓接力原则（Immediate Handoff）**：一旦路由到 `../<repo>` 或 `../.worktrees/<repo>-<topic>`，Agent **必须立即读取该目标仓自身的 `AGENTS.md` 与 `CONTRIBUTING.md`**，遵循该仓的领域不变量、测试套件与 PR Checklist Profile，保持 `mindie-agent` 主仓干净。

### 2. 沙盒化 Agent 的跨目录写权限配置（为什么需要同时挂载两个目录？）

链接工作树（`../.worktrees/<repo>-<topic>`）根目录下的 `.git` 是一个指向 `../<repo>/.git/worktrees/<repo>-<topic>`（及其共享 `commondir` 对象与引用库）的文本指针文件。因此，在 Worktree 内执行 `git add`、`git commit` 或更新索引时，**必须同时拥有 Worktree 目录与基准仓 `../<repo>`（含 `.git/`）的写权限**：

- **OpenAI Codex CLI**：
  ```bash
  codex -C mindie-agent --add-dir ../coordinator --add-dir ../.worktrees/coordinator-my-fix
  ```
- **Claude Code CLI**：
  ```bash
  claude --add-dir ../coordinator --add-dir ../.worktrees/coordinator-my-fix
  ```
- **Google Antigravity / Tencent WorkBuddy / OpenCode / Kimi Code / DSH / 多根 IDE**：将 `../<repo>` 与 `../.worktrees/<repo>-<topic>` 同时加入当前多根工作区（Multi-Root Workspace），或直接在 `../.worktrees/<repo>-<topic>` 目录下启动会话。
- **沙盒只读诚实回退（Read-Only Fallback）**：如果当前 Agent 会话的沙盒仅允许写入 `mindie-agent`，Agent 应先以只读方式完成定位与方案设计，并向用户给出上述一行重开命令以授予目标仓写权限——**严禁把兄弟仓业务代码塞进 `mindie-agent` 充数**。
- **跨 Worktree 运行主仓门禁**：`mindie-agent/.github/scripts/repo_roots.py` 原生识别 `.git` 链接文件与 `--git-common-dir`，支持直接通过 `--siblings-root ../.worktrees` 或精确覆盖 `--repo coordinator=/abs/path/to/worktree` 运行 `check_auto_update_readiness.py` 等跨仓门禁，并且每次执行都会显式打印 `selected / exercised / missing / unselected` 仓库覆盖率。

---

## 🗺️ 全量仓库分工与 PR 门禁 Profile 速查（17 个代码/主仓 + 9 个领域知识库）

| 仓库类别与 `--profile` | 仓库名称（`github.com/mindie-agent/<repo>`） | 单一职责与边界 |
| --- | --- | --- |
| **顶层入口与架构门禁**<br/>`--profile hub` | [`mindie-agent`](https://github.com/mindie-agent/mindie-agent) *(本仓库)* | 产品总入口、整体架构、18 条设计原则、活文档（`docs/`）、历史归档（`docs/archive/`）、`channels/0.1.json` 与纯标准库跨仓 CI 门禁 |
| **共享宿主底座**<br/>`--profile harness` | [`harness`](https://github.com/mindie-agent/harness) (`mindie-harness` / `mindie_harness`) | 7 大原生宿主共用的跨平台底座：无窗子进程与嵌套 Win32 Job 监管、确定性冷启动 Seed（`mindie-harness-seed.pyz`）、`Active + Rollback`（`<= 2`）`.inuse` 租约原子更新、长驻并发零绑定 MCP 网关（`P2.7` / `P2.8`）以及单状态源 `ExperimentLedger` 的 `rsi` 优化闭环 |
| **原生宿主插件（7 个）**<br/>`--profile host-plugin` | [`mindie-agent-codex`](https://github.com/mindie-agent/mindie-agent-codex) · [`mindie-agent-cc`](https://github.com/mindie-agent/mindie-agent-cc) · [`mindie-agent-kimi`](https://github.com/mindie-agent/mindie-agent-kimi) · [`mindie-agent-dsh`](https://github.com/mindie-agent/mindie-agent-dsh) · [`mindie-agent-agy`](https://github.com/mindie-agent/mindie-agent-agy) · [`mindie-agent-wb`](https://github.com/mindie-agent/mindie-agent-wb) · [`mindie-agent-oc`](https://github.com/mindie-agent/mindie-agent-oc) | 各宿主的薄适配层：原生插件清单、生命周期 Hook 转发、宿主专属会话记录脱敏适配器（如 Codex rollout、Antigravity Brain、OpenCode `session_v2`）与共享组件版本锁定，委托 `mindie-harness` 执行进程/更新/MCP 路由 |
| **远端与环境控制面**<br/>`--profile control-plane` | [`remote-dev`](https://github.com/mindie-agent/remote-dev) · [`coordinator`](https://github.com/mindie-agent/coordinator) | `remote-dev`：SSH 文件读写补丁、共享 `~/.mindie/ssh/id_ed25519` 凭据回退、高危命令拦截、容器直连与跨连接句柄后台作业；`coordinator`：昇腾主机/容器池清单、`mindie_probe` 拓扑探测（A2/A3 双 Die/A5）、`HostQueue` 物理卡显存租约与编译槽位控制（`mindie_lease`）及托管任务执行 |
| **本地状态与观测服务**<br/>`--profile state-service` | [`knowledge`](https://github.com/mindie-agent/knowledge) · [`diagnostics`](https://github.com/mindie-agent/diagnostics) · [`npu-top`](https://github.com/mindie-agent/npu-top) | `knowledge`：**纯知识引擎**（`L1–L4` 分级知识单元、按信息缺口条件检索、批量 `refs` 精读与共享 `known_refs`/`token_budget`、双层脱敏、C6 经验提炼与社区 PR 发布）；`diagnostics`：CANN/`plog` 确定性根因解析、4×1 MiB 轮转日志、离线脱敏支持包与 Scale-to-Zero 按需排空的白名单 GitHub 上报（含 `7d` 未发送 `pending` 过期治理）；`npu-top`：回环 Web（`127.0.0.1:8788`）/TUI/CLI/MCP 集群看板与 90 天 SQLite 流式历史 |
| **昇腾设备剖析、调试与仿真**<br/>`--profile device-tool` | [`debugger`](https://github.com/mindie-agent/debugger) · [`profiler`](https://github.com/mindie-agent/profiler) · [`sim`](https://github.com/mindie-agent/sim) | `debugger`：零额外设备上下文的只读 `npu_fault_triage`、三原语 `precision` 精度/踩踏定位与 `aclgraph` 零同步重放/捕获守卫；`profiler`：受控 `msprof` 采集、就地只读解析与基于 `mindie-model-structure/1` 的三态拓扑对齐；`sim`：五层因果性能建模、`compose` 合成、4D 效率拆解与 SLA/PD Pareto 求解 |
| **端到端评测基准**<br/>`--profile bench` | [`mindie-bench`](https://github.com/mindie-agent/mindie-bench) | 20 个真机行为级验证任务（109 项三态与辅助对照）、Gate Runner、隔离宿主评测与组件级基准套件 |
| **昇腾公共领域知识库（9 个）**<br/>`--profile corpus` | [`knowledge-vllm-ascend`](https://github.com/mindie-agent/knowledge-vllm-ascend) · [`knowledge-xllm`](https://github.com/mindie-agent/knowledge-xllm) · [`knowledge-mindie-sd`](https://github.com/mindie-agent/knowledge-mindie-sd) · [`knowledge-operators`](https://github.com/mindie-agent/knowledge-operators) · [`knowledge-infer-core`](https://github.com/mindie-agent/knowledge-infer-core) · [`knowledge-infer-distributed`](https://github.com/mindie-agent/knowledge-infer-distributed) · [`knowledge-infer-observability`](https://github.com/mindie-agent/knowledge-infer-observability) · [`knowledge-infer-ops-compat`](https://github.com/mindie-agent/knowledge-infer-ops-compat) · [`knowledge-agent-engineering`](https://github.com/mindie-agent/knowledge-agent-engineering) | 采用 `mindie-graded-unit/1`（`L1–L4`）结构化格式的昇腾领域公共知识语料库，附带 `applicability` 适用边界与真机实证依据（另含社区技能目录 [`awesome-mindie-skills`](https://github.com/mindie-agent/awesome-mindie-skills) 与工作区脚手架 [`vllm-ascend-workspace`](https://github.com/mindie-agent/vllm-ascend-workspace)） |

---

## 🧭 核心贡献流程：两道黄金门禁

```mermaid
flowchart LR
  A["💡 提出需求<br/>定位单一职责仓库"] --> B["🌳 切出隔离 Worktree<br/>读取目标仓 AGENTS.md 与设计原则"]
  B --> C["🛠️ 原地精炼演进<br/>&lt;800 行 · 五大铁律 · 有界资源"]
  C --> D["🧪 隔离分层测试<br/>Tier 0–3 · 宿主机环境零污染"]
  D --> E["✅ 按 Profile 完成 PR 自检<br/>LF 校验 + check_pr_checklist.py"]
```

### 第一关：动手写代码前 —— 对齐 18 条设计原则与反过度防御五大铁律

在编写代码前，Agent 必须读取目标仓 `AGENTS.md` 与主仓 [`docs/design-principles.md`](./docs/design-principles.md)（[English](./docs/design-principles.en.md)）：

| 核心设计维度 | 写代码前必须对齐的不变量 |
| --- | --- |
| **🎯 总成本与职责边界（原则 1–8）** | 以降低完成用户目标的**端到端总成本**为唯一标尺；封闭确定性问题做成工具，开放判断留在 Skill 引导；优先复用成熟组件（如 `mindie-harness`），替代旧实现时**验证可达性后直接删除旧代码**，不留双轨兼容包袱。 |
| **🔍 状态诚实与回执诚实（原则 9 & 14）** | 严格区分 `completed`、`failed` 与不可逆外部写 `unknown`；严禁 `except Exception:` 返回 `{}` / `"active"` / `exit 0` 掩盖错误，严禁 `except OSError:` 误吞 `TimeoutError`；远端/组件主操作成功后，本地回执异常必须保持 `isError=False` 并附带 `receipt_warning` + `receipt_unconfirmed=True`。 |
| **⏱️ 超时算术与五大铁律（原则 10 & 15）** | 强制 `outer_timeout >= sum(inner_budgets) + cleanup_grace`；严格遵守**五大铁律**：(1) SQLite WAL + `busy_timeout=5000` 在 `open_database` 一次性配置（只读探测不建空库、禁跑在 WSL2 DrvFS 上）；(2) `unknown` 仅限不可逆外部写，禁止本地永久自锁死（`needs_repair`/`fault`/`suppressed`/`TaskRootBusy`）；(3) 禁止复制 `*_fallback.py` 影子状态机或手写 Win32 ACL 仪式（统一用 `os.replace()`）；(4) 禁止 `inspect.signature` 锁死私有签名或内嵌巨型 Python `-c` 字符串；(5) **全表面零前置会话绑定与静默自启（`P2.7` / `P2.8`）**，所有本地工具（含 `knowledge_*`）开箱直通且零口令门禁，外发采集/导出严格受用户授权与 `project_roots` 范围约束。 |
| **🧪 分级测试与零污染（原则 16）** | 拒绝凑数测试与源码文本 grep 锁；测试全流程隔离 `HOME`、`USERPROFILE`、`APPDATA`、`LOCALAPPDATA`、`XDG_*`、`MINDIE_CONFIG_HOME`、`MINDIE_DATA_HOME`、`MINDIE_DIAGNOSTICS_ROOT`、`REMOTE_DEV_AUTH_DIR`、`UV_CACHE_DIR` 与 `TMPDIR`。 |
| **🤖 模块内聚、有界资源与 `P8` 存储（原则 17 & 18）** | 核心模块 `< 800` 行且前 30 行声明 `[Role]` / `[Invariants]` / `[Timeouts & Locks]` / `[Side-Effect Policy]`；常驻内存保持 $O(\text{活跃状态})$（控制面峰值 `<= 512 MiB`、零权重/零设备上下文）；运行时代际最多保留 `Active + Rollback`（`<= 2`），Windows 路径零裸 `os.kill(pid, 0)` 且零弹窗（`CREATE_NO_WINDOW` / `windowsHide: true`）。 |

### 第二关：提交 PR 时 —— 运行 LF 格式与参数化 PR Checklist 门禁

提交或更新 PR 时，请按对应仓库的 [`.github/pull_request_template.md`](./.github/pull_request_template.md) 勾选该类别稳定 Checklist ID 并填写核验证据（对于纯文档 PR 等不适用项，支持填写 `not-applicable: <具体原因>`，CI 会拒绝裸 `N/A` 或 `TODO`）：

```bash
# 1. 校验全仓文本文件严格使用 Unix LF (\n) 换行，零 Windows CRLF (\r\n)
python3 .github/scripts/check_lf_eol.py

# 2. 运行主仓门禁单测套件（修改 .github/scripts/ 时必跑）
python3 -m unittest discover -s .github/scripts/tests -p 'test_*.py' -v

# 3. 按仓库类别校验 PR 描述（支持 hub / harness / host-plugin / control-plane / state-service / device-tool / bench / corpus）
python3 .github/scripts/check_pr_checklist.py --profile hub --body-file <pr_body.md>
```

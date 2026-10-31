# 参与贡献指南 (Contributing to MindIE Agent)

**中文** · [English](./CONTRIBUTING.en.md) · [返回首页](./README.md) · [工程设计原则](./docs/design-principles.md)

欢迎来到 **MindIE Agent**！🎉

和绝大多数传统开源项目不同，`@mindie-agent` 组织下的全部仓库都是 **100% Agent-Native 代码库**——从架构演进、代码实现、真机分层测试到 PR 审查，全部由编程 Agent 完成。

因此，**参与贡献最轻松的姿势，依然是直接把你的想法甩给你的编程 Agent**，让它替你读文档、写代码、跑测试、过门禁。

---

## ⚡ 一句话让你的 Agent 开始贡献

不需要自己先去啃完十几篇架构文档。打开你的 **Claude Code**、**OpenAI Codex CLI**、**Kimi Code**、**DeepSeek Harness** 或 **Google Antigravity**，复制下面这段话并填上你的想法：

```text
我想给 MindIE Agent 贡献一个改动：<在这里一句话描述你想加的特性、修复的 Bug 或补充的昇腾知识>。
请严格按照 https://github.com/mindie-agent/mindie-agent/blob/main/CONTRIBUTING.md 的流程推进：
1. 动手写代码前，先阅读 AGENTS.md 与 docs/design-principles.md 对齐设计原则；
2. 完成代码与分层测试后提交 PR，并对照 .github/pull_request_template.md 完成 Pre-PR Checklist 逐项自检与验证证据回填。
```

<details>
<summary>🤖 <b>AI Agent 贡献与开发执行协议（点击展开 / Agent 读取本页时会自动解析执行）</b></summary>

> **给 AI Agent 的指令**：当用户要求你为 MindIE Agent 旗下任意仓库开发特性、修复问题或提交 PR 时，请严格按以下五步闭环执行，不要把繁琐流程甩给用户：
>
> #### 第一步：动手前先读设计原则（Pre-Coding Gate）
> 1. 先读取当前仓库的 [`AGENTS.md`](./AGENTS.md) 与主仓 [`docs/design-principles.md`](./docs/design-principles.md)，按任务类型按需加载对应领域设计文档（渐进式披露，不要一次性把所有文档塞进上下文）。
> 2. 确认改动归属的单一职责仓库边界（见下方「仓库分工速查」），严禁跨仓复制粘贴 `*_fallback.py` / `*_bootstrap.py` 影子状态机。
>
> #### 第二步：遵循核心红线直接演进代码
> 1. **内环效率优先（Principle 1）**：直接在当前检出工作区修改并验证受影响范围，严禁发明中间冻结目录或无意义的审计仪式文件。
> 2. **错误可见与状态诚实（Principle 9 & 14）**：严格区分 `completed`、`failed` 与不可逆外部写 `unknown`；严禁 `except Exception:` 静默返回 `{}` / `"active"` / `exit 0` 假成功，严禁 `except OSError:` 误吞 `TimeoutError`。
> 3. **超时算术与反过度防御四大铁律（Principle 10 & 15）**：满足 `outer_timeout >= sum(inner_budgets) + cleanup_grace`；SQLite 连接统一开启 WAL + `busy_timeout=5000` 且零热路径 `.owner`/Schema 反射；零本地永久自锁死（无永久 `fault`/`suppressed`/`TaskRootBusy`）；零巨型内嵌 Python 字符串（远端 worker 必须为独立 `.py` 模块）。
> 4. **Agent-Native 模块与注释规范（Principle 17）**：核心模块控制在 `< 800` 行，文件前 30 行必须声明 `[Role]`、`[Invariants]`、`[Timeouts & Locks]`、`[Side-Effect Policy]` 四段式契约头；注释聚焦业务不变量与硬件/协议边界。
> 5. **有界内存/显存与规格分流（Principle 18）**：主循环内存严格保持 $O(\text{活跃状态})$，大文件（`> 50 MB`）流式读取，控制/分析组件单进程峰值 `<= 512 MiB`（`> 1 GiB` 即视为缺陷）；控制面零权重/零设备上下文，重计算或上卡任务按本机与远端真实规格自动分流（严禁硬编码 `sys.platform`）。
>
> #### 第三步：运行有效分层测试（Tier 0 – Tier 3）
> 1. 遵循 [`docs/testing-architecture.md`](./docs/testing-architecture.md)，只写验证真实业务与领域质量的测试（严禁写测类型检查、`chmod`/`symlink` 假想敌或正则 grep 文档的凑数测试）。
> 2. 测试全流程必须通过 `conftest.py` / 临时目录严格隔离 `MINDIE_DIAGNOSTICS_ROOT`、`MINDIE_DIAGNOSTICS_CONFIG` 与 `$HOME`，**零污染宿主机 `~/.local`、`~/.config` 或系统后台服务**。
>
> #### 第四步：提交 PR 并完成 Pre-PR Checklist 逐项自检（含开发格式规范）
> 1. 使用 [`.github/pull_request_template.md`](./.github/pull_request_template.md) 填写 PR 描述。
> 2. PR 提交后，对照最终 `git diff` 逐项复核 Pre-PR Checklist（`1–8`、`9`、`10–11`、`12–13`、`14` 设计原则项，以及 **`15. 仓库工程与文件格式规范`**——确保全仓文本文件严格使用 Unix `LF` `\n` 换行、严禁 Windows `CRLF` `\r\n`），确保全部勾选 `[x]`，并在 **`- **自查结论与证据**：`** 与 **`## 验证结果 (Verification)`** 中填入具体的代码审查证据与真实测试输出。
> 3. 运行本地与 CI 门禁脚本（`python3 .github/scripts/check_lf_eol.py` 与 `python3 .github/scripts/check_pr_checklist.py --body-file <pr_body.md>`），等待 `PR Checklist & LF Line-Ending Gate` 全绿后汇报给用户。

</details>

---

## 🧭 核心贡献流程：两道黄金门禁

为了让十几个仓库在高速迭代中依然保持干净、紧凑、零静默故障，我们的贡献流程把**“架构设计原则”**和**“PR 开发与格式自检”**清晰分开，核心只有两道关卡：

```mermaid
flowchart LR
  A["💡 提出想法<br/>一句话交给 Agent"] --> B["📖 门禁一：开发特性前<br/>阅读 AGENTS.md 与 18 条设计原则"]
  B --> C["🛠️ 原地精炼实现<br/>&lt;800 行 · 顶部契约头 · 有界资源"]
  C --> D["🧪 分层测试验证<br/>Tier 0–3 · 宿主机环境零污染"]
  D --> E["✅ 门禁二：提交 PR 后<br/>Checklist 逐项自检（含 LF 格式规范）"]
  E --> F["🚀 CI 自动核验合入<br/>check_lf_eol + check_pr_checklist"]
```

### 第一关：开发特性前 —— 让 Agent 先读设计原则

在动手写第一行代码之前，请确保你的 Agent 先读过 **[`AGENTS.md`](./AGENTS.md)** 和 **[`docs/design-principles.md`](./docs/design-principles.md)**（[English](./docs/design-principles.en.md)）。设计原则聚焦架构、边界与容错语义，帮 Agent 从源头避开 90% 的返工坑：

| 核心设计维度 | 写代码前必须对齐的设计准则 |
| --- | --- |
| **🎯 总成本与边界（原则 1–8）** | 以降低完成任务的**端到端总成本**为唯一衡量标准；封闭确定性问题做成工具，开放判断留给 Skill 引导；优先复用宿主/OS/成熟组件能力，升级替代旧实现时**直接删掉重写**，不留双轨兼容包袱。 |
| **🔍 错误可见与超时算术（原则 9–15）** | 失败必须对调用方诚实可见，绝不用 `except Exception:` 返回 `{}` / `"active"` / `exit 0` 掩盖错误；超时必须满足 `outer_timeout >= sum(inner_budgets) + cleanup_grace`；严格遵守反过度防御四大铁律。 |
| **🧪 分级测试与宿主机零污染（原则 16）** | 拒绝凑数测试与文本 grep 测试；按 Tier 0（`<5s` 纯内存）~ Tier 3（常备 A2/A3 昇腾真机）分层验证；测试必须严格隔离 `$HOME` 与 `MINDIE_DIAGNOSTICS_ROOT`，严禁污染开发机个人目录或后台服务。 |
| **🤖 Agent-Native 模块与注释规范（原则 17）** | 核心模块保持 `< 800` 行（单次 `view_file` 可完整加载），文件顶部前 30 行声明 `[Role]` / `[Invariants]` / `[Timeouts & Locks]` / `[Side-Effect Policy]` 契约头；注释写清业务不变量与硬件/协议边界，不为防御性代码写借口。 |
| **⚡ 有界内存/显存与规格分流（原则 18）** | 主循环常驻内存保持 $O(\text{当前活跃状态})$，常规组件单进程峰值 `<= 512 MiB`（`> 1 GiB` 视为算法 Bug）；控制面保持零权重/零设备上下文；重任务按本机与远端真实硬件规格自动分流，不写死 `sys.platform`。 |

### 第二关：PR 提交后 —— 让 Agent 完成 Checklist 自检（含开发格式规范）

像文件换行格式（强制 `LF`、禁止 Windows `CRLF`）这类属于工程与提交卫生规范，统一收敛在 **PR Checklist（[`.github/pull_request_template.md`](./.github/pull_request_template.md)）** 与自动化 CI 门禁（[`.github/workflows/pr-checklist.yml`](./.github/workflows/pr-checklist.yml)）中。在提交或更新 PR 后，Agent 必须对照最终 diff 完成自检：

1. **完整填写 `## 变更摘要 (Summary)`**：用简明列表说明本次改动解决的核心问题与改动范围。
2. **逐项核对并勾选 `## 设计原则 Review (Pre-PR Checklist)`**：
   - 对照 `1–8`、`9`、`10–11`、`12–13`、`14` 五个设计原则检查项，以及 **`15. 仓库工程与文件格式规范（PR Format Hygiene）`**（核验全仓文本文件严格使用 Unix `LF` `\n` 换行、无 Windows `CRLF` `\r\n` 或混合换行，Python 跨平台写脚本/文本显式传 `newline="\n"`）逐一核查；
   - 核查无误后将全部 `- [ ]` 勾选为 `- [x]`；
   - 在 **`- **自查结论与证据**：`** 字段中写明具体的核查结论与证据（例如超时预算算术关系、契约头覆盖情况、内存有界性与 `LF` 格式校验结论等；CI 会自动拒绝空白或 `TODO` / `N/A` / `无` 等敷衍占位符）。
3. **如实记录 `## 验证结果 (Verification)`**：附上实际执行的测试命令、通过状态及耗时。
4. **通过两项自动化脚本门禁**：
   ```bash
   # 1. 校验全仓文本文件均为 LF (\n) 换行且无 Windows CRLF (\r\n)
   python3 .github/scripts/check_lf_eol.py

   # 2. 校验 PR 描述已完成全部 Checklist 勾选与实质证据填写
   python3 .github/scripts/check_pr_checklist.py --body-file <pr_body.md>
   ```

---

## 🗺️ 仓库分工速查（该往哪个仓库提 PR？）

`@mindie-agent` 下每个仓库职责单一，Agent 会根据你的需求自动定位目标仓库：

| 你想贡献的内容 | 目标仓库 |
| --- | --- |
| **整体架构、工程设计原则、跨组件发布契约、总入口文档** | [`mindie-agent`](https://github.com/mindie-agent/mindie-agent) *(本仓库)* |
| **Claude Code / Codex / Kimi / DSH / Antigravity 原生插件适配与生命周期 Hook** | [`mindie-agent-cc`](https://github.com/mindie-agent/mindie-agent-cc) · [`mindie-agent-codex`](https://github.com/mindie-agent/mindie-agent-codex) · [`mindie-agent-kimi`](https://github.com/mindie-agent/mindie-agent-kimi) · [`mindie-agent-dsh`](https://github.com/mindie-agent/mindie-agent-dsh) · [`mindie-agent-agy`](https://github.com/mindie-agent/mindie-agent-agy) |
| **昇腾领域知识条目（`L1–L4` 工程规范、排障 SOP、工作流、算子/推理调优模式）** | [`knowledge-vllm-ascend`](https://github.com/mindie-agent/knowledge-vllm-ascend) · [`knowledge-operators`](https://github.com/mindie-agent/knowledge-operators) · [`knowledge-infer-core`](https://github.com/mindie-agent/knowledge-infer-core) 等 7 大公共知识库 |
| **知识检索引擎、条件匹配、脱敏采集与经验提炼飞轮** | [`knowledge`](https://github.com/mindie-agent/knowledge) |
| **远端 SSH / 容器执行、多机 NPU 协调租约、实时监控看板、CANN 故障分诊** | [`remote-dev`](https://github.com/mindie-agent/remote-dev) · [`coordinator`](https://github.com/mindie-agent/coordinator) · [`npu-top`](https://github.com/mindie-agent/npu-top) · [`diagnostics`](https://github.com/mindie-agent/diagnostics) |
| **昇腾 `msprof` 性能解析（`profiler`）与硬件 Roofline / 整网仿真建模（`sim`）** | [`profiler`](https://github.com/mindie-agent/profiler) · [`sim`](https://github.com/mindie-agent/sim) |
| **端到端真机评测任务、Oracle 与组件基准套件** | [`mindie-bench`](https://github.com/mindie-agent/mindie-bench) |

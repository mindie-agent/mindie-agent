# 历史版本问题复盘与系统性防复发门禁（`0.0.1 → 0.1.6`）

[English](historical-issues-and-guardrails.en.md) · [返回文档中心](README.md) · [核心设计原则](design-principles.md) · [版本兼容与无感更新](release-compatibility-and-update.md)

本文档系统性归档 MindIE Agent 从 `0.0.1` 到 `0.1.6` 演进过程中暴露过的真实线上/验收缺陷。所有历史问题按**七大根因域（`P1–P7`）**收敛为**“问题现象与版本出处 → 根因剖析 → 刚性工程不变量（禁止项） → 自动化防复发门禁”**四元组。日常开发无需将全部历史细节常驻上下文；当触及对应子系统或发版门禁时，按需查阅本表并通过自动化脚本拦截。

---

## 一、七大历史问题域总览

| 编号 | 问题域 | 覆盖组件 / 仓库 | 关联自动化门禁 |
| --- | --- | --- | --- |
| **`P1`** | **自动更新、组件灵活升级与发版漏改/漏检** | `knowledge` · 五大宿主插件 · `channels/0.1.json` | `check_auto_update_readiness.py` (`R1–R6`) · `publication_check.py` |
| **`P2`** | **原生宿主生命周期、会话门禁与跨平台路径** | `codex` · `cc` · `kimi` · `dsh` · `agy` · `remote-dev` | 各插件 Tier 0/1 生命周期契约测试 · `conftest.py` 沙箱隔离 |
| **`P3`** | **超时算术、输出截断与流式连接清理竞态** | `remote-dev` · `dsh` · `mindie-bench` · 全宿主 MCP | `outer >= sum(inner) + grace` 契约单测 · 流式中断回归测试 |
| **`P4`** | **状态诚实性、回执记账与反静默回退** | `remote-dev` · `coordinator` · `diagnostics` · 全宿主插件 | Receipt Honesty 单测 · 反过度防御四大铁律 |
| **`P5`** | **知识预算、去重交付与 C6 经验蒸馏边界** | `knowledge` · `knowledge-*` 语料仓 · 五大宿主插件 | `WHOLE_DELIVERY_SCOPE` 预算单测 · C6 Strict Schema 校验 |
| **`P6`** | **评测基准防失真、行为级判分与真机防抢占** | `mindie-bench` (`G0–G5`) · `RemoteSlot` · `WorktreeSlot` | Verifier 四重 Soundness 门禁 · `foreign_pids` 物理观测 |
| **`P7`** | **内存/显存有界性与昇腾 A2/A3/A5 拓扑建模** | `profiler` · `sim` · `coordinator` · `npu-top` · `remote-dev` | `<= 512 MiB` 峰值红线 · A3 双 Die `Phy-ID 0..15` 实机测试 |

---

## 二、逐域复盘与防复发不变量明细

### `P1`：自动更新、组件独立灵活升级与发版漏改/漏检（`0.1.1 → 0.1.6`）

| 历史问题与版本 | 现象与根因剖析 | 刚性工程不变量（禁止项） | 自动化防复发门禁 |
| --- | --- | --- | --- |
| **P1.1 知识单元修改正文漏升 `revision`**<br>（`0.1.5 → 0.1.6`，`knowledge-vllm-ascend`） | 修正 `unit-ascend-cann-known-limitations-and-env-toggles.md` 正文后更新了 `routing-manifest.json` 的 `content_sha256`，但漏将 `revision: 1` 递增为 `2`，导致客户端 `GradedRepository.install_feed()` 触发 `unit.revision <= old.revision` 语义版本校验失败并阻塞同步。 | 严禁在修改分级知识单元正文（`content_sha256` 变化）时不递增 `revision`；严禁仅靠人工记忆手改 `revision`。 | 1. `build_routing_index()` 重建索引时自动将内容变化且未升版本的单元推进为 `old_revision + 1`；<br>2. `publication_check.py` 在 `validate(..., base_revision=...)` 拒绝未升 `revision` 的提交；<br>3. `check_auto_update_readiness.py` (`R2`) 扫描全部 7 个语料仓历史通道提交至 `HEAD`。 |
| **P1.2 宿主 CLI 自动小版本升级超出兼容区间**<br>（`0.1.4` Codex `0.165.0-alpha.1.2`、`0.1.6` Codex `0.166.0-alpha.5.1`） | 用户本机 ChatGPT Desktop 内置 `codex-cli` 自动升级后，版本超出 `harness-compatibility.json` 的 `supported` 区间上限，后台更新器返回 `"no_compatible_release"` 拒绝升级插件。 | 发版或合入兼容性变更前，严禁只测旧版 CLI 而忽略本机已安装的最新宿主 CLI（含 Desktop 内置二进制）。 | `check_auto_update_readiness.py --verify-local-hosts` (`R5`) 自动探测本机 `codex`（含 `/Applications/ChatGPT.app/.../codex`）、`claude`、`kimi` 版本并验证 `supports_harness()`。 |
| **P1.3 插件更新误把已独立升级的组件降级回引导基线**<br>（`0.1.4` Kimi `0.1.8 → 0.1.9`） | 旧更新器把源码中的引导依赖版本当成候选解释器已安装版本，导致正常 launchd 升级将已加载的 `knowledge 0.13.6 / remote-dev 0.11.1` 回退到引导环境的 `0.13.3 / 0.10.6`。 | 组件版本选择必须严格遵守单调不降级：`max(installed, plugin_baseline, latest_formal_release)`；必须通过 `runtime_inventory.py` 实读候选解释器而非信任静态配置声明。 | 五端宿主统一接入 `component_update.py` + `mindie_knowledge.component_runtime.discover/build`；`check_auto_update_readiness.py` (`R4`) 默认校验 `plugin_baseline <= channel_component` 支持单组件独立灵活发版。 |
| **P1.4 静态 MCP 目录漏重新导出 & Release 漏传资产**<br>（`0.1.6` Codex `mcp_catalog.json`、`mindie-agent-agy v0.1.1`） | 升级 `remote-dev`/`knowledge` 后未跑 `export_catalog.py` 导致发布流水线契约测试失败；手动创建 GitHub Release 时漏传 `mindie-plugin-release.json` 与 `SHA256SUMS`。 | 变更组件依赖后必须同步导出静态目录；任何正式 GitHub Release 必须包含完整校验资产（`SHA256SUMS` 等）。 | `check_auto_update_readiness.py --verify-github-releases` (`R3`) 强制核验远端 GitHub Release 状态、Tag SHA 与 `SHA256SUMS` 资产。 |

---

### `P2`：原生宿主生命周期、会话门禁与跨平台路径边界（`0.1.1 → 0.1.5`）

| 历史问题与版本 | 现象与根因剖析 | 刚性工程不变量（禁止项） | 自动化防复发门禁 |
| --- | --- | --- | --- |
| **P2.1 隐式唤醒与常驻知识工具污染普通会话**<br>（`0.0.2 → 0.1.1`） | 早期默认暴露知识工具或自动注入 Skill 正文，导致非昇腾日常会话被无关上下文干扰并触发非预期后台服务。 | **Passive Default 铁律**：确定性工具（`remote-dev`/`profiler`/`sim`/`coordinator`/`diagnostics`）默认可用；`knowledge_*` 工具与后台采集严格由当前会话显式输入 `/mindie-agent` 门控，新会话/Fork/Subagent 绝不自动继承。 | 五端插件生命周期测试验证未启用会话零租约、零后台服务启动，且 `tools/list` 不泄露私有知识工具。 |
| **P2.2 Antigravity `hooks.json` 路径层级与 `Stop` 续轮死循环风险**<br>（`0.1.5` `mindie-agent-agy`） | Antigravity 原生插件只识别插件根目录下的 `hooks.json`（不识别 `hooks/hooks.json`）；若 `Stop` Hook 返回 `"decision": "continue"` 会强制模型无限续轮。 | AGY 插件 `hooks.json` 必须位于 `plugins/mindie-agent/hooks.json`；`Stop` Hook 必须返回 `{}`，严禁返回 `"decision": "continue"`。 | `mindie-agent-agy/tests/test_agy_plugin.py::test_plugin_manifest_and_root_hooks_layout` 与 `test_agy_lifecycle.py`。 |
| **P2.3 Windows Git Bash `ucrt64/bin` 找不到 `ssh.exe` & 探针污染宿主机目录**<br>（`0.1.2` `remote-dev 0.11.1`、`0.1.4` CC 探针） | Git for Windows 2.56.0 下 `PATH` 含 `Git/ucrt64/bin/git.exe`，但 `ssh.exe` 位于 `Git/usr/bin/ssh.exe`；CC 旧迁移探针遗漏隔离环境变量导致在默认目录初始化了新配置。 | 严禁硬编码 `sys.platform` 或假定 `ssh` 与 `git` 同目录；任何测试/探针子进程必须显式绑定隔离的 `MINDIE_CONFIG_HOME` / `MINDIE_DATA_HOME` / `MINDIE_DIAGNOSTICS_ROOT`。 | `remote-dev` Windows PowerShell + Git Bash PATH 真实 SSH 验收套件；各仓 `conftest.py` 强制临时目录沙箱隔离。 |

---

### `P3`：超时算术、输出截断与流式连接清理竞态（`0.1.1 → 0.1.4`）

| 历史问题与版本 | 现象与根因剖析 | 刚性工程不变量（禁止项） | 自动化防复发门禁 |
| --- | --- | --- | --- |
| **P3.1 响应截断预算误杀仍在运行的子进程**<br>（`0.1.4` DSH `v0.1.8 → v0.1.9`） | 子进程标准输出超过 MCP 响应展示预算时被直接 `SIGKILL`，导致原本正常返回业务退出码 `3` 的命令变成 `-9`。 | 必须将“进程运行期输出缓冲阈值”与“返回给模型的响应截断预算”解耦；未超时前严禁因输出长而强杀正常运行的命令。 | DSH / Kimi / Codex / AGY `bounded_run` 大输出返回非零退出码保留测试。 |
| **P3.2 外层超时小于内层预算总和导致提前切断或僵尸进程**<br>（`0.1.0 → 0.1.3`） | 外层 MCP 默认超时过短，或内层 `SIGTERM -> SIGKILL` 排水期未计入外层预算；或使用 `timeout N cmd \|\| cmd` 超时后裸跑第二次。 | 严格执行 **`outer_timeout >= sum(inner_budgets) + cleanup_grace`**（如全宿主 MCP `660s >= 600s + 60s`，`STOP_DRAIN >= STOP_GRACE + 3s`）；严禁 `timeout N cmd \|\| cmd`。 | 各组件超时算术不变量测试与 PR Checklist 第 10 项强制核验。 |
| **P3.3 清理异常掩盖主异常 & 跨线程直接 `close()` 引发 `NoneType` 竞态**<br>（`0.1.1` `remote-dev #43`、`mindie-bench 0.4.4`） | `LocalForward.__exit__` 清理报错覆盖了主操作异常；网关超时结算线程直接调 `HTTPResponse.close()` 清空 `fp`，导致读取线程 `read1()` 抛 `AttributeError: NoneType.close` 丢失 `model_error`。 | 主异常发生时，清理失败只能通过 `record_cleanup_failure` 附注在主异常上；跨线程中断 socket 仅调 `shutdown(SHUT_RDWR)`，由读取线程 `finally` 独占 `close()`；`except OSError:` 必须前置 `except TimeoutError: raise`。 | `remote-dev` 转发清理故障注入单测；`mindie-bench` `HTTP/1.1 chunked` 暂停交错并发关闭回归测试。 |

---

### `P4`：状态诚实性、回执记账与反静默回退（`0.1.1 → 0.1.5`）

| 历史问题与版本 | 现象与根因剖析 | 刚性工程不变量（禁止项） | 自动化防复发门禁 |
| --- | --- | --- | --- |
| **P4.1 远端操作成功但本地回执记账超时被反标为失败**<br>（`0.1.2 → 0.1.5`） | 远端命令或组件调用已完成，但本地 SQLite 写入回执时遇锁超时，若把结果改写为 `isError=True`，会诱导 Agent 重复执行已生效的外部写操作。 | **Receipt Honesty Invariant**：主操作一旦成功，本地回执/绑定记账异常必须保持 `isError=False`，仅在 `structuredContent` 附加 `receipt_warning` 与 `receipt_unconfirmed=True`。 | 五端插件 `test_*_receipt_honesty` 故障注入单测。 |
| **P4.2 本地代码异常误记为 `unknown` 或单向 `fault` 永久自锁死**<br>（`0.1.1` `coordinator #63`） | `service_gang.py` 漏导入 `preparation_control` 把本地 `NameError` 误记为远端 `state="uncertain"`；早期本地状态机设永久 `fault`/`suppressed` 导致环境一次报错后自砖化。 | 反过度防御铁律 (2)：`unknown` 回执严格保留给**已发出且结果未知的不可逆外部写操作**；本地状态严禁设单向永久自锁死。 | `coordinator` 准备作业状态刷新单测与 PR Checklist 第 9、11 项。 |
| **P4.3 远端调用漏传必填端点参数（如 `port`）被压缩为笼统报错**<br>（`0.1.1 → 0.1.2` `remote-dev 0.10.8`） | 模型调用直接 SSH 工具漏传 `port` 时，旧适配器将错误压缩为通用字符串，模型无法识别缺哪个字段。 | 确认未发出的本地 caller 参数错误必须返回有界 `input_repair.missing/action`，並在工具 Schema 描述中显式写明端点规则。 | `remote-dev` caller input repair 单测与原生客户端自纠正验收。 |

---

### `P5`：知识预算、去重交付与 C6 经验蒸馏边界（`0.1.1 → 0.1.5`）

| 历史问题与版本 | 现象与根因剖析 | 刚性工程不变量（禁止项） | 自动化防复发门禁 |
| --- | --- | --- | --- |
| **P5.1 插件二次裁剪探索结果 & 导航裁剪删引用破坏分页游标**<br>（`0.1.1` `knowledge #97/#99/#100`） | 插件层二次剥离 L3 或重建事实包导致响应体积与引擎预算脱节；导航视图裁剪时直接删除旧材料行导致 `related_next` 游标不可达。 | 预算与交付记账仅由 `mindie-knowledge` 唯一属主负责（`WHOLE_DELIVERY_SCOPE`），宿主插件原样透传；导航裁剪仅设 `excerpt_omitted=True` 保留引用；交付记账在单事务中按 `(unit_id, revision)` 去重。 | `knowledge` 整包预算、全续页游标可达性与单事务去重记账单测。 |
| **P5.2 C6 蒸馏关联单元挤占预算、`"unknown"` 假条件与 Strict Schema 400**<br>（`0.1.5`） | 关联单元与候选单元共用小预算把待审正文裁空；C6 给未观测环境字段填 `"unknown"` 导致检索时 `condition_mismatch`；Codex `--output-schema` 漏写嵌套 `additionalProperties: false` 报 HTTP 400。 | 关联单元使用独立 `RELATED_BODY_BUDGET_BYTES = 12_000`；严禁将 `"unknown"`/`"n/a"` 写入 `applicability` 条件；所有发往 OpenAI/Codex 的 JSON Schema 必须递归满足 `additionalProperties: false` 且 `required` 覆盖全部属性。 | `knowledge` C6 关联预算与条件清洗测试；`mindie-agent-codex` Strict Schema 递归校验单测。 |

---

### `P6`：评测基准防失真、行为级判分与真机防抢占（`0.1.0 → 0.1.5`）

| 历史问题与版本 | 现象与根因剖析 | 刚性工程不变量（禁止项） | 自动化防复发门禁 |
| --- | --- | --- | --- |
| **P6.1 判分器未验证真实行为或合成续跑成本**<br>（`0.1.0 → 0.1.1` `mindie-bench #24/#25/#26`） | 早期 6 个任务的判分器未执行真实代码行为或可被常量返回绕过；策略选择未注入真实执行器时合成了续跑结果。 | 所有任务 Verifier 必须执行被测代码真实行为并通过四重 Soundness 校验（`before_reward=0`、`after_reward=1`、`model_calls=0`、常量负对照必败）；未执行的续跑必须标 `not_executed` 且耗时/成本保持 `None`。 | `mindie-bench` Verifier Soundness 门禁与负对照测试套件。 |
| **P6.2 `G1` 误挂语料、`WorktreeSlot` 锁重入死锁与题面失真**<br>（`0.1.5`） | `G1`（仅 `remote-dev`）未物理隔离本地知识库导致混入知识单元；`WorktreeSlot.cleanup()` 重复获取自身已持有的 `flock` 死锁；题面含人工步骤提示偏离真实开发者口语报障习惯。 | `G1` 必须物理挂载空语料（`0` units）；Slot `cleanup()` 必须幂等且不重入已持文件锁；基准题面统一采用“一句话报障 + 原始报错堆栈/日志路径”，不靠改题塞提示词凑分。 | `mindie-bench` `G0–G5` 门禁测试与 `WorktreeSlot` 并发回收单测。 |
| **P6.3 共享昇腾真机被外部进程中途抢占**<br>（`0.1.5` L3 `192.168.13.156`） | 常驻 A3 服务器在评测中途被外部用户的 16-Die `VLLMWorker` 任务占满，导致评测容器报错。 | 发现非本会话租约的 `foreign_pids` 抢占物理 Die 时，必须如实记为 `unknown` 或 `infra_failed`，**严禁强杀外部用户进程**，严禁将受抢占污染的 Trial 记为通过或归因于模型能力。 | `RemoteSlot` 与 `physical_observation` 外部 PID 识别及状态诚实性单测。 |

---

### `P7`：内存/显存有界性与昇腾 A2/A3/A5 硬件拓扑建模（`0.1.1 → 0.1.5`）

| 历史问题与版本 | 现象与根因剖析 | 刚性工程不变量（禁止项） | 自动化防复发门禁 |
| --- | --- | --- | --- |
| **P7.1 大文件全量读入内存 & SQLite 连接重复反射自检**<br>（`0.1.3` `profiler 0.5.1`） | 对大型 `.so` 或 `>50 MB` Profiling Trace 直接 `read()`/`json.load()` 导致内存峰值飙升；每次 `SELECT` 跑 `.owner` `lstat` 或 `:memory:` 反射拖慢热路径。 | 大文件（`>50 MB`）强制流式处理（`hashlib.file_digest` / JSONL 迭代 / SQLite 索引），控制面单进程峰值 `<= 512 MiB`（`>1 GiB` 视为 Bug）；SQLite 连接仅在 `open_database` 设置一次 WAL + `busy_timeout=5000`。 | `profiler` 流式摘要测试与 PR Checklist 第 11、14 项。 |
| **P7.2 昇腾 A3 910C 双 Die `Phy-ID 0..15` 映射与空闲显存误算**<br>（`0.1.1` `remote-dev #44`、`coordinator #64`） | 将 A3 双 Die 卡按单卡覆盖统计，或硬扣 `2–3 GiB` 常数代替实测 `hbm_total_mb - hbm_used_mb`，导致选卡与容量准入失真。 | A3 必须按独立可租约物理执行单元（`8 NPU × 2 Die = Phy-ID 0..15`）及非繁忙单元实测 `hbm_total_mb - hbm_used_mb` 计算空闲容量；控制面保持零权重、零设备上下文。 | 常驻 A2/A3 真机无损集成测试（`@pytest.mark.live_npu`）。 |

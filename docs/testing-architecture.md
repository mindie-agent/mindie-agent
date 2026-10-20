# 分级测试体系与用例设计规范（Tiered Testing Architecture & Case Design）

[English](testing-architecture.en.md) · [返回文档中心](README.md)

本文定义 MindIE Agent 各仓库（`knowledge`、`remote-dev`、`coordinator`、`npu-top`、`diagnostics`、四个宿主插件与评测仓 `mindie-bench`）统一的**用例有效性红线**与**四级测试金字塔（Tier 0 ~ Tier 3）**。

> **说明**：表中的四级分类与耗时预算是工程测试体系的设计目标；每次版本发布实际覆盖的源码 SHA、测试范围、运行环境、实测耗时与已知限制均在对应版本的[发布说明](releases/0.0.2.md)中如实记录。

- 遵循准则：[工程设计原则与演进准则](design-principles.md) · [系统架构与模块分工](architecture.md)

知识与系统能力的具体测试见 [L1–L4 分级测试方案](knowledge-tiered-testing-plan.md)。L1–L4 表示知识类型，Tier 0–3 表示工程验证范围；完整任务收益、跨任务学习和长期探索实验单列预算，不以短 Canary 代替。

---

## 一、用例有效性红线（Every Test Must Earn Its Keep）

测试的唯一价值是**以最低的时间与维护成本捕获真实的生产缺陷与边界回归**。全栈仓库严禁以下五类无效或虚假测试：

1. **严禁“防御性偏执凑数测试”**：
   - 禁止编写纯粹验证 Python 类型检查、简单的属性赋值、防御性 `ValueError` / `TypeError` 分支（如“传入空字符串抛异常”）、或反复构造 `chmod 0o777` / `symlink` 假想敌却不触及核心业务不变量的单测。
2. **严禁“替静默吞错与假成功背书的测试”**：
   - 禁止编写“当底层数据库连接失败、子进程超时或绑定异常时，断言接口返回 `exit 0` / `{}` / `status="active"`”的假阳性测试；故障测试必须验证错误被真实、可定位地上报，且本地记账超时绝不覆写已成功的远端业务结果。
3. **严禁“静态常量与枚举点名测试”**：
   - 禁止编写逐一核对静态字典、常量表、枚举字符串列表、函数默认参数签名（`inspect.signature`）或 Schema 字段名的字面量测试。
4. **严禁“文档与提示词正则 Grep 测试”**：
   - 禁止在测试套件中用正则表达式或字符串包含去 grep `README.md`、`SKILL.md`、模板文案或文档标题。文档靠架构审查维护，测试只验证可执行代码的真实行为。
5. **严禁“篡改生产脚本或失真 Mock 假测试”**：
   - 严禁在测试中动态覆写生产脚本文件（如把 `admission_ops.py` 替换成几行假桩）来凑绿灯；
   - 严禁使用与真实服务端/硬件返回字段不符的 `MagicMock` 伪造通过（例如用假造的 `npu-smi` 字符串或虚构的 RPC 字段自嗨）。所有离线解析测试必须基于从真实昇腾硬件采集的 **Golden Captures**，所有状态流转测试必须跑在真实的内存回路（如 `InMemoryHostQueue`）或真实 SQLite/Git 临时实例上。

---

## 二、四级测试金字塔（Tier 0 ~ Tier 3，默认常备 A2/A3 昇腾 NPU 环境）

```mermaid
flowchart TB
    T3["Tier 3：端到端宿主 CLI 与 mindie-bench 实机基准验收 (&lt; 90s)<br/>驱动真实宿主 CLI 与 mindie-bench Canary 任务完成闭环验证"]
    T2["Tier 2：常备 A2/A3 NPU 真机无损集成测试 @pytest.mark.live_npu (&lt; 25s)<br/>直连 A2 (173.125.1.2) 与 A3 (192.168.13.165/.156/.154) 隔离沙箱验证真机探测、容器穿透与租约"]
    T1["Tier 1：本地组件契约与进程边界测试 (&lt; 15s)<br/>复用 Session 级 Git/SQLite 模板，验证跨进程锁、python -I 隔离启动与毫秒级超时回收"]
    T0["Tier 0：纯内存核心逻辑单测 (&lt; 5s)<br/>零子进程 · 零网络 · 零 sleep · 真实硬件 Golden Captures · InMemoryHostQueue 状态机回路"]
    T0 --> T1 --> T2 --> T3
```

| 层级 | 耗时预算 | 运行频率与定位 | 核心覆盖范围与铁律 |
| --- | --- | --- | --- |
| **Tier 0**<br/>纯内存核心逻辑单测 | **`< 5s`** | 每次保存 / 每次提交必跑 | **零外部子进程、零网络、零 `sleep`**。覆盖解析器（基于真实 A2 910B / A3 910C / A5 硬件 Golden Captures）、状态机流转（`InMemoryHostQueue` 等真实内存回路）、确定性隐私脱敏规则、`TechnicalTokenizerV1` 分词与协议转换。 |
| **Tier 1**<br/>本地组件契约与进程边界测试 | **`< 15s`** | 本地改动组件 / PR 门禁必跑 | **复用 Session 级预构建 Git/SQLite 模板**（`shutil.copytree` 毫秒级派生）。验证跨进程文件锁、`python -I` 真实隔离启动、MCP stdio 帧传输、毫秒级可注入超时与进程树回收。**严禁在测试内联网 `pip install` 或跑 10MB 级 `fsync` 磁盘轰炸**。 |
| **Tier 2**<br/>常备 A2/A3 NPU 真机无损集成测试（`@pytest.mark.live_npu`） | **`< 25s`** | 涉及远端执行、探测、容器、租约或 NPU 工具时常态化必跑 | 直接连接常驻 **A2 (`173.125.1.2`)** 与 **A3 (`192.168.13.165` / `.156` / `.154`)** 昇腾集群，使用隔离沙箱目录（如 `state_dir="/tmp/mindie-npu-test-<uuid>"`）在不干扰线上业务任务的前提下，常态化验证真机 `npu-smi` 探测、多 Die `Phy-ID` 映射、Docker 容器穿透、Linux `/proc` 进程树排空与租约防抢占。 |
| **Tier 3**<br/>端到端宿主 CLI 与 `mindie-bench` 实机基准验收 | **`< 90s`** | 插件发版 / 跨仓联动 / 评测套件变更必跑 | 驱动真实宿主 CLI（Claude Code、Codex、Kimi Code、DSH）与 `mindie-bench` Canary 任务完成从问题触发、知识检索、远端 NPU 验证到经验沉淀的闭环验收。 |

---

## 三、各层级设计细则与最佳实践

### 3.1 Tier 0：用真实硬件 Golden Captures 与内存回路替代 `MagicMock`
- **硬件报文保真**：针对 `npu-smi info`、`npu-smi info -t board`、`lscpu`、容器挂载点与 CANN 报错栈的解析测试，必须使用从真实 A2（910B）、A3（910C 双 Die）与 A5 节点采集的原始输出快照（Golden Captures）。
- **零 `sleep` 状态推进**：测试重试退避、租约过期、增量 Checkpoint 或滑动窗口时，统一通过可注入单调时钟（`clock` / `now_fn`）推进时间，严禁在单测中写 `time.sleep(...)`。

### 3.2 Tier 1：Session 级 Fixture 模板化与可注入超时
- **预构建模板复用**：凡涉及 Git 仓库初始化（`git init` + `commit`）或 SQLite Schema 建表的测试，统一在 `conftest.py` 的 `scope="session"` Fixture 中一次性构建基准目录，单个测试通过拷贝文件树获得独立沙箱，将单次准备耗时控制在毫秒级。
- **毫秒级进程生命周期验证**：验证子进程取消、挂死回收或 `owner-pipe` / `systemd` / Job Object 清理时，通过注入 `50ms ~ 100ms` 级的测试超时参数触发真实信号路径，禁止硬编码数秒的等待周期。

### 3.3 Tier 2：常备 A2/A3 NPU 真机无损沙箱规范（`@pytest.mark.live_npu`）
- **常驻集群就绪**：开发环境默认常备 A2（`173.125.1.2`）与 A3（`192.168.13.165` / `.156` / `.154`）真机 SSH 通道。涉及硬件拓扑、远端同步或容器执行的改动，不能只停留在本地模拟，必须跑通 `@pytest.mark.live_npu`。
- **绝对无损与沙箱隔离**：
  - 远端状态与临时文件必须限定在 `/tmp/mindie-npu-test-<uuid>` 独立沙箱目录内，并在 Fixture `teardown` 中彻底清理；
  - 严禁修改、重启或抢占线上正在运行的业务容器、训练/推理进程或全局配置文件；
  - 租约与进程排空测试仅操作测试自身拉起的受控轻量进程与测试专用沙箱租约。

### 3.4 Tier 3：宿主 CLI 与 `mindie-bench` Canary 闭环
- 在 `mindie-bench` 中，测试套件聚焦于验证 Recipe 构建器、环境隔离（Source Projection / Worktree）、Verifier 判定逻辑、遥测计费对账与 Canary 任务实机闭环，确保评测基础设施本身严谨、快速且无死分支冗余。

---

## 四、CI 分层与随包发布基准测试（Release Benchmarks）

1. **常规 CI 与实机测试分层**：
   - 日常 PR、分支 CI 与发布前本地组件检查默认执行 `pytest -m "not live_npu"`，不自动连接常备昇腾集群或消耗付费宿主模型 Token。
   - 所有真实 NPU 集成用例统一标记 `@pytest.mark.live_npu`。在单测中直接调用 `mcp_server.handle()` 属于 Tier 1 组件契约测试；驱动真实宿主 CLI 才属于 Tier 3 宿主验收。
2. **版本发布实测门禁**：
   - 正式版本发布时，基于锁定版本的 `mindie-bench` 运行器校验各组件精确源码身份及端到端研发任务、跨任务经验复用与组件场景实测报告（详见[组件与插件配套发布](release-compatibility-and-update.md#每次发布的-benchmark-交付)与 [`0.0.2` 版本发布说明](releases/0.0.2.md#三实测收益与-003-优化计划)）。
3. **验证层级的职责边界**：

| 验证层级 | 验证的核心事实 | 适用边界 |
| --- | --- | --- |
| **本地单元与合同测试（Tier 0/1）** | 授权状态机、协议转换、数据脱敏与错误传播符合代码契约 | 不替代真实宿主客户端或昇腾 NPU 硬件运行验证 |
| **A2/A3 实机无损集成（Tier 2）** | 常备昇腾集群与容器拓扑下的真实硬件探测、远端执行与租约协调 | 不替代完整宿主 CLI 端到端会话回路 |
| **真实宿主与任务实测（Tier 3）** | 固定任务集与组件场景下的端到端闭环、解题率与并发协调表现 | 按实测宿主、模型与对照条件记录 |

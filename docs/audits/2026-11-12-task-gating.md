# 任务门禁与独立工作连续性复查

本轮从“缺少 MindIE 任务绑定，因而无法检查测试资源”的反馈出发，检查共享组件与六端插件的实际调用链。截图没有原始工具请求和响应，不能仅凭截图断言当时命中了哪个实现分支；以下结论来自源码与隔离回归。

## 确认问题与修复

1. **独立环境接口被 MCP 任务关联查询提前拦截。** Coordinator 的 `ops.mindie_call` 已将 `hosts`、`probe`、`container`、`lease` 与受管任务操作分开，但 `task_server._call_tool` 对携带 Codex/Kimi 元数据的请求统一执行 `AgentSessions.native_context`。不存在任务关联时，环境接口尚未执行即返回 `native session association is missing or ambiguous`。相同查询不带元数据却成功，形成了与业务无关的额外门禁。
2. **公开指引没有充分区分任务绑定、原生调用身份和设备租约。** 六端保留原生替代路径，但部分 profiler 表述容易将实际设备采集的租约要求扩展到离线分析。六端工具目录和入口指引统一明确：独立环境操作、已授权的源码和模型定位、CPU 测试、离线 profiler 分析和仿真不以受管任务绑定或设备分配为前置条件。
3. **部分原生插件发布遗漏旧更新器必需的元数据。** Antigravity 和 DSH 的首次发布在私有草稿下载校验时因缺少 `mindie-plugin-release.json` 失败；WorkBuddy 的打包入口也存在相同遗漏。DSH 的源码兼容性声明仍为旧格式。共享发布控制器统一从已核验的版本、精确 Git 提交及其规范声明生成缺失资产，复用固定旧消费者的仓库注册、布局和校验；已有错误资产保持失败，合法原始字节保留。DSH 改用规范声明，安装配置中的组件基线直接读取实际项目锁，移除重复 pin。这个改动不把更新器的源码一致性验证变成可选项。

Coordinator 仅在受管任务操作或显式选择 `context_file` 时解析原生任务归属。环境操作省略该字段时不自动附加任务上下文，也不创建关联记录。受管任务隔离、显式上下文冲突拒绝、未知外部写对账，以及实际 NPU/端口租约仲裁继续由原有实现负责。

## 审查范围

| 范围 | 检查的边界 | 结论 |
| --- | --- | --- |
| coordinator | MCP、两种 CLI、任务关联、独立环境处理器、失败继续入口 | 修复 MCP 入口范围错误，明确公开目录与契约 |
| remote-dev | 通用 MCP 调用、端点参数、源码探测、后台作业归属、原生替代说明 | 没有发现知识激活或受管任务绑定的额外前置条件；原生作业身份保留 |
| 六端插件 | Codex、Claude Code、Kimi、DSH、Antigravity、WorkBuddy 的组件转发、知识准入、回执与入口指引 | 确定性工具不要求知识租约；更新目录及指引，保留原生身份、nonce/bind 和不重放语义 |
| knowledge | 知识调用的显式激活与贡献授权边界 | 授权只限制对应知识能力，不作为独立组件准入 |
| diagnostics | 本地状态与支持包导出、显式远端报告授权 | 本地操作与报告授权分离，不要求受管任务绑定 |
| debugger、profiler、sim、npu-top | CLI、离线分析和只读观察入口 | 未发现 MindIE 任务关联门禁；实际设备动作与观察明确区分 |
| mindie-bench | CLI、评测准入与真实资源归属 | 保留评测完整性及设备占用条件，不作为普通文件/SSH 排查前置条件 |

此次“全量”指上述产品调用与连续性边界的全面复查，不宣称穷尽所有业务算法缺陷，也不以离线回归替代真实模型/NPU E2E。

## 回归与发布范围

新增回归覆盖无任务关联的 Codex/Kimi 主会话与子调用、独立主机/探测/容器操作、租约缺参的真实业务报错、显式上下文归属冲突，以及真实 stdio 进程中独立请求成功后受管任务仍被正确拒绝、连接继续响应的行为。

最终候选的受影响范围回归为 105 passed，另有 24 subtests。Coordinator 首轮 Windows 全量为 1486 passed / 110 skipped / 8 failed / 24 errors；使用短临时目录和 UTF-8 重跑原失败项后，27 项通过，剩余五项分别涉及本机没有固定 `Program Files/Git` 路径、符号链接权限及原生缓存长路径。未修改这些测试来掩盖现场限制。干净 PR CI 完成后，Linux 为 1621 passed / 8 skipped / 63 subtests，macOS 为 1595 passed / 34 skipped / 63 subtests，Windows 为 1517 passed / 112 skipped / 63 subtests。

六端原修复的受影响范围合计 156 passed；WorkBuddy CI 发现目录说明增加后主模块超出 800 行，已将组件目录移至独立模块，相关结构、MCP 与连续性回归 13 passed，随后全部必需 CI 通过。共享元数据生成与发布事务相关回归 38 passed；固定发布消费者 `3c478a19b5542b38520c7f98b87a07f37e305021` 上六种真实声明布局和失败分支回归 14 passed。DSH 规范声明、配置和升级相关回归 23 passed / 1 skipped。

共享发布控制器 PR 的 Linux、macOS 全量 CI 均为 1452 passed / 45 skipped / 6 deselected。DSH 声明迁移合入后的主分支 CI 为 Linux、macOS 各 252 passed / 23 subtests，Windows 176 passed / 76 skipped / 20 subtests。六个实际仓库也分别运行现有生成器与共享生成器，验证前三端产物一致，以及 DSH、Antigravity、WorkBuddy 缺失资产的自动生成。以上不依赖真实 NPU 或付费模型调用。

本轮已按独立范围正式发布：Coordinator `0.7.7`、Codex `0.1.27`、Claude Code `0.1.18`、Kimi `0.1.19`、DSH `0.1.17`、Antigravity 与 WorkBuddy 均为 `0.1.9`，共享发布控制器随 `mindie-bench 0.4.8` 独立发布。共享组件独立更新不依赖主产品通道重发；本轮不改写历史 `channels/0.1.json` 组合。

发布前 R1–R6 已通过，包括本机宿主兼容性、历史组合与实际最新正式组件源。开发回归、平台 CI、正式发布和发布后升级验收分别记录；未完成的阶段不作为成功证据。

最终源码复核中，一次 R3 强制查询 mindie-bench 正式源遇到 URL 超时；该失败保留，随后重新执行完整只读 R1–R6 并全部通过，包括本机宿主和实际正式源。新增共享发布与 DSH 声明修复的独立发布范围再次通过 R1–R6。

原修复开发 PR 均已通过必需 CI 并合入：Coordinator [#77](https://github.com/mindie-agent/coordinator/pull/77)、Codex [#109](https://github.com/mindie-agent/mindie-agent-codex/pull/109)、Claude Code [#72](https://github.com/mindie-agent/mindie-agent-cc/pull/72)、Kimi [#74](https://github.com/mindie-agent/mindie-agent-kimi/pull/74)、DSH [#44](https://github.com/mindie-agent/mindie-agent-dsh/pull/44)、Antigravity [#12](https://github.com/mindie-agent/mindie-agent-agy/pull/12)、WorkBuddy [#10](https://github.com/mindie-agent/mindie-agent-wb/pull/10)。自动生成改动为 mindie-bench [#46](https://github.com/mindie-agent/mindie-bench/pull/46)，规范声明为 DSH [#45](https://github.com/mindie-agent/mindie-agent-dsh/pull/45)，两者也已通过必需 CI 合入。

## 失败发布的实际外部状态

Antigravity 首次失败为 [run 43150000765](https://github.com/mindie-agent/mindie-agent-agy/actions/runs/43150000765)，只创建私有草稿 `442471648`，目标源码为 `46ebe8e35e6a6525230b03bb84d9aa7615e56970`。重启标准事务时继续以该草稿 ID 和源码标记确认归属，再刷新仍为私有的资产。

DSH 首次失败为 [run 43149999988](https://github.com/mindie-agent/mindie-agent-dsh/actions/runs/43149999988)，只创建私有草稿 `442473531`，目标源码为 `52ee5a1279c3440782b2c9285e4911813eb405f9`。规范声明合入后源码改为 `18cff70644a5d786c14ad34c87f2f7bd60807ed5`，原草稿不属于新源码。确认旧 ID、私有状态、源码标记及正式标签不存在后，仅删除该旧私有草稿；删除后重新查询确认草稿与标签均不存在，随后从新提交启动标准事务。没有删除、移动正式标签或覆盖正式资产。

## 最终正式发布与升级验收

八仓均从受保护主分支发布，发布工作流的候选、基准、公开事务及独立公开源复验全部成功。另使用固定已发布旧消费者逐仓下载并校验全部 67 个发行资产，核对完整校验和、基准来源、精确标签提交、不可变状态和实际 latest 发现。候选与公开源的完整共享组件升级报告均为 `all_shared_components` / `passed`。

| 仓库 | 正式版本 | 精确源码 | 完成的发布工作流 | 下载校验资产数 |
| --- | --- | --- | --- | --- |
| coordinator | [0.7.7](https://github.com/mindie-agent/coordinator/releases/tag/v0.7.7) | `62fb6d96b88f4518e882262ed0bb25638722c04b` | [43151772653](https://github.com/mindie-agent/coordinator/actions/runs/43151772653) | 8 |
| mindie-agent-codex | [0.1.27](https://github.com/mindie-agent/mindie-agent-codex/releases/tag/v0.1.27) | `91aec540aa42d733cb2382aad9cc34ad416242b1` | [43150916925](https://github.com/mindie-agent/mindie-agent-codex/actions/runs/43150916925) | 10 |
| mindie-agent-cc | [0.1.18](https://github.com/mindie-agent/mindie-agent-cc/releases/tag/v0.1.18) | `9fcaadb74938cea629e2e8eac3e29c9fbe1260a7` | [43150125008](https://github.com/mindie-agent/mindie-agent-cc/actions/runs/43150125008) | 9 |
| mindie-agent-kimi | [0.1.19](https://github.com/mindie-agent/mindie-agent-kimi/releases/tag/v0.1.19) | `136c4ca042cc8996a45f4280c25ca3e92bff2f70` | [43150918099](https://github.com/mindie-agent/mindie-agent-kimi/actions/runs/43150918099) | 8 |
| mindie-agent-dsh | [0.1.17](https://github.com/mindie-agent/mindie-agent-dsh/releases/tag/v0.1.17) | `18cff70644a5d786c14ad34c87f2f7bd60807ed5` | [43153690280](https://github.com/mindie-agent/mindie-agent-dsh/actions/runs/43153690280) | 8 |
| mindie-agent-agy | [0.1.9](https://github.com/mindie-agent/mindie-agent-agy/releases/tag/v0.1.9) | `46ebe8e35e6a6525230b03bb84d9aa7615e56970` | [43153647912](https://github.com/mindie-agent/mindie-agent-agy/actions/runs/43153647912) | 8 |
| mindie-agent-wb | [0.1.9](https://github.com/mindie-agent/mindie-agent-wb/releases/tag/v0.1.9) | `af77cda6b0d5c526c8308087e7bae5ad245b1168` | [43153669404](https://github.com/mindie-agent/mindie-agent-wb/actions/runs/43153669404) | 8 |
| mindie-bench | [0.4.8](https://github.com/mindie-agent/mindie-bench/releases/tag/v0.4.8) | `8f0abbff1559653377e12babcd0e3024c2c44e8d` | [43153625811](https://github.com/mindie-agent/mindie-bench/actions/runs/43153625811) | 8 |

Codex 另通过真实原生插件的候选及公开源升级：从正式 `0.1.23` 出发，组件独立升级、外部组件标准入口重绑、过期快照拒绝、禁用 Stop 保留和新原生进程加载恢复全部成功。其他仓的完整组件升级验收不扩写为各自原生宿主 UI 或真实双机模型验收。截图中的主机信息仅作为问题背景，本轮未在这些主机上运行双机模型/NPU E2E。

四次补充发布（mindie-bench、DSH、Antigravity、WorkBuddy）的自动元数据步骤全部成功，基准报告中的控制器精确提交均为 `8f0abbff1559653377e12babcd0e3024c2c44e8d`。六端共用的发布入口继续跟随受保护主分支，每次事务固定唯一控制器提交。兼容性声明仍由源码维护，发行 JSON 不再依赖各仓手工补文件或生成命令。

最终发布后，以全部八仓为独立范围执行 R1–R6，包含 `--require-siblings --verify-local-hosts --verify-github-releases`，六项全部通过。实际最新正式更新源已覆盖本轮 Coordinator 和 mindie-bench 新版，历史产品通道保持 `0.1.12`。

此处确认正式发现与隔离旧客户端升级成功；常驻用户宿主按其支持的刷新或新进程边界加载新目录，保留活动会话。

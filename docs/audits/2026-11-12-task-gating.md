# 任务绑定门禁与独立工作连续性复查

本轮复查针对“因缺少 MindIE 受管任务绑定（task binding）而无法探测远端测试资源”的用户反馈，逐一核查了八大共享组件与六款原生宿主插件的真实调用链路。由于问题截图不含原始工具请求与响应载荷，下文不主观断言截图当时命中的具体分支；全部结论均基于源码走查与隔离回归验证。

## 定位并修复的三项问题

1. **独立环境操作被 MCP 层的任务关联查询提前误拦**：在 `coordinator` 内部，`ops.mindie_call` 原本已将独立环境管理操作（`hosts`、`probe`、`container`、`lease`）与受管任务操作解耦；但外层 `task_server._call_tool` 对所有携带 Codex / Kimi 会话元数据的请求无差别调用了 `AgentSessions.native_context`。一旦当前会话尚未创建受管任务，主机探测与容器查询尚未进入业务逻辑即报错 `native session association is missing or ambiguous`（而不带元数据的同一请求却能正常通过），人为制造了与业务无关的前置门禁。修复后，`coordinator` 仅在受管任务操作或调用方显式传入 `context_file` 时才解析任务归属；独立环境操作缺省该字段时不附加任务上下文，也不隐式创建任务记录（受管任务隔离、显式上下文冲突拒绝、未知外部写入对账及真实 NPU/端口租约仲裁保持不变）。
2. **工具目录与入口引导对“受管任务绑定 / 原生会话身份 / 设备租约”三者边界表述不清**：例如部分 `profiler` 工具描述容易让模型将“在线真机采集所需的设备租约”误推及到“离线 trace 只读解析”。六端工具目录与入口说明现已统一厘清：独立环境查询、已获授权的源码修改与模型定位、CPU 测试、离线 `profiler` 解析及 `sim` 建模均不以受管任务绑定或 NPU 租约为前提。
3. **部分原生插件发布流程遗漏旧版更新器所需的发行元数据**：Google Antigravity 与 DSH 在首次发布工作流的私有草稿下载校验阶段因缺少 `mindie-plugin-release.json` 中止，Tencent WorkBuddy 的打包入口亦存在同类遗漏，且 DSH 仍保留旧格式兼容性声明。本次在 `mindie-bench` 共享发布控制器中统一从已核验版本号、精确 Git 提交与规范声明自动生成缺失的发行元数据（若已有资产格式非法则依然报错阻断，合法原始字节保持不变），同步将 DSH 迁移至标准声明格式并直接从项目锁文件读取组件基线、消除重复版本硬编码。

## 全组件调用链核查矩阵

| 核查对象 | 检查的准入与连续性边界 | 复查结论 |
| --- | --- | --- |
| `coordinator` | MCP 服务、双 CLI 入口、原生会话关联、独立环境处理器与报错恢复指引 | 修复 MCP 入口无差别拦截问题，厘清公开工具目录契约 |
| `remote-dev` | 公开 MCP 工具、端点参数、工作区探测、后台作业归属与原生替代提示 | 确认无知识租约或受管任务绑定前置门禁，原生作业归属完整保留 |
| 六款原生宿主插件 | Codex、Claude Code、Kimi、DSH、Antigravity、WorkBuddy 的组件转发、知识门控、回执与引导文案 | 确认确定性工程工具均不依赖 `/mindie-agent` 知识激活；同步更新工具描述，保留原生身份、一次性 `bind` 与防重放语义 |
| `knowledge` | 显式 `/mindie-agent` 会话激活与社区贡献授权边界 | 授权仅约束知识检索/采集/外发，绝不充当其他独立组件的准入门禁 |
| `diagnostics` | 本地日志状态查询、离线支持包导出与可选 GitHub Issue 上报授权 | 本地只读诊断与外发上报授权严格分离，不依赖受管任务绑定 |
| `debugger`、`profiler`、`sim`、`npu-top` | CLI、MCP、离线只读分析与监控看板入口 | 确认零受管任务绑定门禁；实际触碰远端 NPU 的采集/调试动作与只读分析清晰区分 |
| `mindie-bench` | CLI、评测准入门禁与真实设备资源独占校验 | 保留基准评测所需的环境完整性与设备独占约束，不影响日常开发与 SSH 排障 |

> **审查范围说明**：上表覆盖全部产品级工具调用与连续性准入边界，不宣称穷尽业务算法内部的所有潜在缺陷，也不以离线回归替代真实多机模型与昇腾 NPU 端到端实测。

## 回归测试与跨平台 CI 验证

- **`coordinator` 回归**：新增无任务关联下的 Codex / Kimi 主会话与子调用、独立 `hosts`/`probe`/`container` 操作、租约缺参真实业务报错、显式上下文归属冲突，以及真实 stdio 进程内“独立请求成功 → 未绑定受管任务精准拒绝 → 后续请求继续正常响应”的全链路测试，受影响范围 `105 passed / 24 subtests`。首轮本机 Windows 全量运行出现少量因临时路径过长、系统非 UTF-8 默认编码、缺少固定 `Program Files/Git` 目录及符号链接权限引起的宿主环境差异项（未改测试掩盖现场限制）；切换短临时目录与 UTF-8 后复跑收敛，干净 PR CI 三端全绿：Linux `1621 passed / 8 skipped / 63 subtests`、macOS `1595 passed / 34 skipped / 63 subtests`、Windows `1517 passed / 112 skipped / 63 subtests`。
- **六端插件与共享发布控制器回归**：六端准入与工具说明回归合计 `156 passed`（其中 WorkBuddy 因目录说明扩充触发单文件 `< 800` 行门禁，随即将组件目录拆分至独立模块并通过 `13 passed` 结构与连续性回归）；共享元数据生成与发布事务回归 `38 passed`，基于固定旧版消费者 `3c478a19b5542b38520c7f98b87a07f37e305021` 的六种声明布局与失败分支校验 `14 passed`；DSH 规范声明迁移回归 `23 passed / 1 skipped`。共享发布控制器 PR 在 Linux / macOS 全量 CI 均通过 `1452 passed / 45 skipped / 6 deselected`；DSH 合入后主分支 CI 通过 Linux / macOS 各 `252 passed / 23 subtests`、Windows `176 passed / 76 skipped / 20 subtests`。
- **关联开发 PR**：[coordinator #77](https://github.com/mindie-agent/coordinator/pull/77)、[Codex #109](https://github.com/mindie-agent/mindie-agent-codex/pull/109)、[Claude Code #72](https://github.com/mindie-agent/mindie-agent-cc/pull/72)、[Kimi #74](https://github.com/mindie-agent/mindie-agent-kimi/pull/74)、[DSH #44](https://github.com/mindie-agent/mindie-agent-dsh/pull/44) 与 [#45](https://github.com/mindie-agent/mindie-agent-dsh/pull/45)、[Antigravity #12](https://github.com/mindie-agent/mindie-agent-agy/pull/12)、[WorkBuddy #10](https://github.com/mindie-agent/mindie-agent-wb/pull/10) 以及 [`mindie-bench` #46](https://github.com/mindie-agent/mindie-bench/pull/46)。

## 中断发布草稿的外部状态对账

- **Google Antigravity 首次发布中断（[run 43150000765](https://github.com/mindie-agent/mindie-agent-agy/actions/runs/43150000765)）**：仅在远端生成了指向目标提交 `46ebe8e35e6a6525230b03bb84d9aa7615e56970` 的私有 Draft Release（ID `442471648`），未创建公开标签。重启标准发布事务时先校验该草稿 ID 与源码指纹一致，再原位刷新草稿资产并完成公开转正。
- **DSH 首次发布中断（[run 43149999988](https://github.com/mindie-agent/mindie-agent-dsh/actions/runs/43149999988)）**：仅生成指向旧提交 `52ee5a1279c3440782b2c9285e4911813eb405f9` 的私有 Draft Release（ID `442473531`）。合入规范声明修复 PR 后目标源码推进至 `18cff70644a5d786c14ad34c87f2f7bd60807ed5`；经对账确认旧草稿仍为私有且远端不存在正式 Git 标签后，清理该废弃私有草稿并二次查询确认无残留，再基于新提交发起标准发布事务（全程零删除、零移动任何已公开标签或正式资产）。

## 独立正式发布与升级验收汇总

全部 8 个仓库均从受保护主分支完成标准正式发布（独立组件与插件演进不改写历史产品通道 `channels/0.1.json` 的 `0.1.12` 记录），使用固定旧版消费者逐仓下载核验全部 `67` 个正式资产（校验和、基准来源、精确标签 SHA、不可变状态及 `latest` 发现全通，候选与公开源 `all_shared_components: passed`），并在发版前后均完整通过带 `--require-siblings --verify-local-hosts --verify-github-releases` 的 `R1–R6` 门禁（期间曾出现单次查询 `mindie-bench` 远端 URL 网络超时，已保留原始记录并随后重跑全量只读 `R1–R6` 确认全绿）：

| 仓库 | 正式版本 | 标签精确源码 SHA | 发布工作流记录 | 校验资产数 |
| --- | --- | --- | --- | --- |
| `coordinator` | [`0.7.7`](https://github.com/mindie-agent/coordinator/releases/tag/v0.7.7) | `62fb6d96b88f4518e882262ed0bb25638722c04b` | [43151772653](https://github.com/mindie-agent/coordinator/actions/runs/43151772653) | `8` |
| `mindie-agent-codex` | [`0.1.27`](https://github.com/mindie-agent/mindie-agent-codex/releases/tag/v0.1.27) | `91aec540aa42d733cb2382aad9cc34ad416242b1` | [43150916925](https://github.com/mindie-agent/mindie-agent-codex/actions/runs/43150916925) | `10` |
| `mindie-agent-cc` | [`0.1.18`](https://github.com/mindie-agent/mindie-agent-cc/releases/tag/v0.1.18) | `9fcaadb74938cea629e2e8eac3e29c9fbe1260a7` | [43150125008](https://github.com/mindie-agent/mindie-agent-cc/actions/runs/43150125008) | `9` |
| `mindie-agent-kimi` | [`0.1.19`](https://github.com/mindie-agent/mindie-agent-kimi/releases/tag/v0.1.19) | `136c4ca042cc8996a45f4280c25ca3e92bff2f70` | [43150918099](https://github.com/mindie-agent/mindie-agent-kimi/actions/runs/43150918099) | `8` |
| `mindie-agent-dsh` | [`0.1.17`](https://github.com/mindie-agent/mindie-agent-dsh/releases/tag/v0.1.17) | `18cff70644a5d786c14ad34c87f2f7bd60807ed5` | [43153690280](https://github.com/mindie-agent/mindie-agent-dsh/actions/runs/43153690280) | `8` |
| `mindie-agent-agy` | [`0.1.9`](https://github.com/mindie-agent/mindie-agent-agy/releases/tag/v0.1.9) | `46ebe8e35e6a6525230b03bb84d9aa7615e56970` | [43153647912](https://github.com/mindie-agent/mindie-agent-agy/actions/runs/43153647912) | `8` |
| `mindie-agent-wb` | [`0.1.9`](https://github.com/mindie-agent/mindie-agent-wb/releases/tag/v0.1.9) | `af77cda6b0d5c526c8308087e7bae5ad245b1168` | [43153669404](https://github.com/mindie-agent/mindie-agent-wb/actions/runs/43153669404) | `8` |
| `mindie-bench` | [`0.4.8`](https://github.com/mindie-agent/mindie-bench/releases/tag/v0.4.8) | `8f0abbff1559653377e12babcd0e3024c2c44e8d` | [43153625811](https://github.com/mindie-agent/mindie-bench/actions/runs/43153625811) | `8` |

此外，Codex 插件从历史正式版 `0.1.23` 出发额外通过了候选与公开源全链路原生升级验收（涵盖共享组件独立升级、外部组件标准入口重绑、过期快照拒绝、`Stop` 禁用态保持及新原生子进程启动恢复）。已常驻运行的用户宿主将按各自支持的刷新或新进程边界加载新版工具目录，活跃会话无需中断。

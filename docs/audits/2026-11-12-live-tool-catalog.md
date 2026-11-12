# 常驻工具目录刷新与任务绑定恢复复查

本轮承接“插件升级后仍沿用旧说明、要求重复发送激活口令”的反馈，检查 Coordinator 与六端原生适配器的更新、发现、转发、参数校验和错误恢复边界。截图缺少原始工具请求，不能断言截图中的每次拒绝来自同一分支；以下结论分别来自本机版本与进程证据、源码及隔离协议验收。

## 已确认并修复的边界

| 问题 | 实际影响 | 修复 |
| --- | --- | --- |
| Codex 在常驻进程构造时保存工具目录 | 后端解释器与脚本已切换，模型仍看到旧说明和参数 | 目录按已选运行绑定读取；组件调用的校验与执行转发到同一代完整 helper |
| Codex 分别读取目录内容与缓存键的绑定 | 升级发生在两次读取之间时，旧目录被记在新修订下，之后查询仍可能持续返回旧说明与 schema | 缓存键直接从已选绑定计算，与目录内容共用同一份绑定快照 |
| Codex 的独立组件代沿用插件打包时的远程 schema 快照 | 后端组件已更新，发现和入参校验却仍可能拒绝该组件已支持的参数 | `0.1.28` 起由已选完整 helper 的纯 schema 工厂提供实际运行时目录；旧 helper 保留其既有快照协议 |
| 六端均没有目录变更通知 | 即使后续 `tools/list` 能返回新目录，宿主也可能继续复用启动缓存 | 公共 MCP 连接声明 `tools.listChanged=true`，观察现有原子绑定并发送 `notifications/tools/list_changed` |
| Codex 宿主默认关闭目录变更处理 | 仅补服务端通知不足以改变模型下一次推理的工具定义 | 安装与更新使用公开配置 API、版本比较交换和回读，检测并开启 `mcp_tool_list_changed`；不支持或未确认的状态单独记录 |
| Antigravity、WorkBuddy、DSH 的部分进程固定导入旧代码 | 新目录与旧调用实现可能不匹配 | 常驻入口保留连接，请求使用已选解释器与脚本；活跃请求继续使用开始时选定的代 |
| Kimi 旧更新控制器只复制固定的五个启动文件 | 新 transport 模块不能随旧复制清单自动到位，且新解释器可能与旧入口不匹配 | 保留原版本前端身份，进入已选解释器，并从自己的副本或完整已选代加载唯一 transport；不增加选择器 |
| 原生任务关联查询在格式化结果之前抛出通用异常 | 调用方拿不到可用的继续路径 | 缺失或歧义关联返回 `managed_task_context_required`、具体原因及 `submission_state=not_sent` |
| 缺少任务关联时仍推荐受管 `mindie.run` 作为脚本恢复入口 | 恢复动作再次需要同一个缺失的任务上下文 | 明确独立环境接口及授权的 `remote.bash`/原生 shell 路径；受管任务只使用已注册且归属正确的上下文 |
| DSH 将缺少原生传输身份引导为再次激活知识 | 重复口令不能补齐该传输身份 | 指明原生适配器身份故障，继续不依赖它的已授权工作 |
| Antigravity、WorkBuddy 的 `serverInfo.version` 写死 | 初始化版本不能反映实际载入的插件 | 从实际 helper 的插件清单读取版本 |
| Windows Hook 的 Python 子进程与 PowerShell 输出没有共同声明编码 | 本地化错误可能破坏 JSON 读取或变成乱码 | 子进程和 PowerShell 协议统一 UTF-8；真实 shell 回归同时校验 JSON 与 stderr，测试读取不依赖系统 ANSI 编码 |
| helper 选择尚未成功就将本地错误标记为外部执行未知 | 调用方无法判断业务请求是否已发出 | 未启动 helper 的失败明确为 `execution=not_started`；只有实际发出的不透明业务调用才可能保留未确认回执 |
| selected helper 的进程排水时间没有从总预算扣除 | 接近外层期限时可能来不及清理自有子进程 | 五秒排水预留纳入原有外层预算；Codex 组件原生调用预算覆盖组件执行、helper 转发和排水 |

目录观察器只保留当前连接的修订，不新增持久选择器、任务表或授权层。共享 helper 使用原有进程组 / Windows Job 归属，限制输出与超时；次要清理失败附加警告，保留已完成操作的业务结果。缺少任务关联不会自动创建任务、猜测工作目录或绕过资源租约。知识读取、贡献及采集仍遵循原有显式授权。

## 隔离验收

本机当前桌面内核为 `codex-cli 0.167.0-alpha.4.1`。真实原生进程加载实际 MindIE `mcp_gate.py` facade，使用本地确定性的 Responses SSE 服务与真实 stdio MCP，未调用付费模型，未运行 SSH 或 NPU 任务：

| 宿主能力 | 同一回合第一次推理 | 工具发出目录变更后第二次推理 | 实际工具调用数 |
| --- | --- | --- | --- |
| `mcp_tool_list_changed=false` 对照 | `before` | `before` | 1 |
| `mcp_tool_list_changed=true` | `before` | `after` | 1 |

该验收检查实际推理请求里的工具定义。管理 API 的 `mcpServerStatus/list` 自己会重新请求列表，不能单凭该查询出现新说明，就宣称模型已经自动刷新。此前没有通知时的停留缓存也作为对照保留。

六端实际常驻 facade 另分别通过确定性的已选 helper 协议验收：在同一连接切换既有配置或 `current.json` 后，无需发送激活口令即收到通知；下一次目录返回新说明和新参数，随后新参数调用成功，连接继续响应 ping。此项证明六端适配器的选择与转发链路，不能扩写为六个原生宿主均已完成 UI 或真实模型验收。共享边界测试还覆盖活跃调用跨切换保留旧代、后续调用使用新代及调用没有重放。

本地最终相关 Codex 回归为 88 passed / 2 skipped / 30 subtests，包含真实原生同回合验收；补充关闭 Python UTF-8 模式的 Hook 及原生入口回归为 31 passed / 11 subtests，两者有重叠，不相加。Coordinator 相关回归为 91 passed / 24 subtests，补充适配器结果契约为 14 passed / 6 subtests。remote-dev 最终目录/回执边界回归为 3 passed。六端其他本地全量及受影响回归、平台 CI 分开记录；Windows 无法执行的 POSIX 用例交由 Linux/macOS CI 验证。

CI 还发现旧测试将目录通知误当作调用响应、要求响应按请求顺序排列，以及一次性写完 stdin 后立即 EOF 导致新常驻入口正确取消调用的问题。测试改为显式断言目录通知、按请求身份接收结果，并使用标准 MCP 客户端保持连接至业务响应完成。原有取消、进程归属、准备失败时保留旧代、用户配置和既有作业不变的断言继续保留。并行首轮的一个既有 400ms 进程测试因启动时序失败，隔离重跑通过；没有修改它放宽门禁。

补充的本机完整旧环境升级试验在候选准备阶段触及既有 85 秒总预算，临时输出文件清理随后报 `WinError 32`；该次保留为失败，不计入通过。同一最终源码的 Antigravity、WorkBuddy Linux/Windows 原生旧环境升级 CI 均已通过，未放宽预算或跳过升级门禁。

Codex 初次合入后的 macOS CI 另暴露既有诊断用例与后台更新的竞态：故意不包含原生安装信息的配置触发更新错误，使待投递列表先出现 `update`，而不是该用例预置的 `worker_failed`。补充 PR [#111](https://github.com/mindie-agent/mindie-agent-codex/pull/111) 只在该真实 stdio 用例中写入既有的近期检查回执，将独立维护排除在采集投递场景之外；保留原有故障码、只投递一次、未激活知识和不要求用户命令的断言。相关本地回归为 13 passed / 4 subtests，正式发布等待补充源码完整 CI。

发布前最终复核还以真实配置文件的原子替换复现 Codex 缓存键与目录内容跨代的竞态：修复前第二次查询仍返回 `old`（1 failed / 0.59s），修复后同一 Gate 下一次查询返回 `new` 及其新 schema。修复 PR [#112](https://github.com/mindie-agent/mindie-agent-codex/pull/112) 将缓存键改为从已选绑定直接计算，没有增加锁、选择器或持久状态。目录、完整 helper 转发、未发送回执及真实原生同回合刷新相关回归为 15 passed / 8.19s。其余五端转发完整已选 helper，没有复用此目录内容缓存。

同一 PR 还修复独立组件代沿用插件基线 schema 的路径。测试保留缺少 `python_candidates` 的旧基线文件，使用完整实际 helper 和已安装 remote-dev 提供新目录，验证公开发现、入参校验及基线文件字节不变；修复前为 1 failed / 0.48s。新 helper 的只读目录入口直接复用 schema 工厂；`0.1.28` 之前的完整 helper 继续使用其声明的快照协议，不对未知 helper 盲试新接口。最终目录、锁定运行时、发现边界和真实原生同回合相关回归为 40 passed / 2 skipped / 3 subtests，补充旧协议与不可变基线断言后，两项相关回归再次通过。没有执行远程工作或知识激活。

## 首次迁移与宿主边界

已经驻留的旧 facade 无法凭磁盘更新获得新代码。宿主尚未消费的新功能配置也不能当作当前会话已经生效的证明。首次迁移沿用宿主支持的原生重载边界，保留活动会话；已载入本轮 facade 且支持通知的宿主，之后的运行代切换自动刷新目录。所有回执区分安装、功能配置和宿主载入状态。

本机更新前的实际绑定为插件 `0.1.27` / remote-dev `0.11.9`，而桌面常驻入口的完整运行代回执仍为插件 `0.1.26` / remote-dev `0.11.7`。这两项分别从当前配置和驻留进程所用的 `runtime.json` 核对，不能用已写入的新配置替代驻留版本证据。

公开的 `config/mcpServer/reload` 作用于收到请求的 app-server 及其已加载会话。另起一个管理 app-server 调用它，不能证明桌面正在使用的 app-server 已刷新。本轮没有采用这种误报方式，也没有终止活动用户会话来制造更新已生效的表象。

任务绑定恢复不依赖知识激活。重复 `/mindie-agent` 或 `$mindie-agent` 既不修复任务关联，也不刷新旧工具目录；只有确实需要知识功能时才使用知识入口。独立租约仍需实际主机参数和真实资源归属，设备工作沿用原有仲裁。

## 发布与自动元数据

本轮按独立组件及插件范围发布，历史 `channels/0.1.json` 仍为 `0.1.12`。先发布共享依赖，再将六端锁定到已正式发布的精确提交。PR、主分支 CI、正式发布、候选与公开源旧客户端验收及发布后 R1–R6 分别记录。

`mindie-bench 0.4.8` 的共享发布入口已经负责自动生成并验证 `mindie-plugin-release.json`，先于校验和与旧更新器验收执行。本轮继续复用该入口，避免重新引入每个仓手工补发行 JSON 的步骤；兼容性声明仍由源码维护。

共享目录能力先以 remote-dev `0.11.8` 正式发布。发布后复核确认的“未启动 helper 的本地错误分类”和排水预算问题另以 `0.11.9` 修复；`0.11.8` 的正式标签和资产保持不可变。六端最终精确锁定 remote-dev `0.11.9`（`6e9882e0fa495bf2feeef29ec86492498d364531`）和 Coordinator `0.7.8`（`db9b0c6432001d6049056eabd37422d0bfb9f75a`）。

## 正式发布与升级验收

已完成的七仓均通过受保护主分支检查和标准正式发布。另以固定已发布旧消费者独立下载、校验全部 57 个资产，核对精确标签提交、不可变状态、实际 latest 发现和完整共享组件的候选及公开源升级报告。Codex 等待补充测试隔离源码的完整 PR/main CI 后发布；尚未完成的阶段不计为成功。

| 仓库 | 正式版本与 PR | 精确源码 | 完成的发布工作流 | 下载校验资产数 |
| --- | --- | --- | --- | --- |
| remote-dev | [0.11.9](https://github.com/mindie-agent/remote-dev/releases/tag/v0.11.9) / [#62](https://github.com/mindie-agent/remote-dev/pull/62) | `6e9882e0fa495bf2feeef29ec86492498d364531` | [43184303535](https://github.com/mindie-agent/remote-dev/actions/runs/43184303535) | 8 |
| coordinator | [0.7.8](https://github.com/mindie-agent/coordinator/releases/tag/v0.7.8) / [#78](https://github.com/mindie-agent/coordinator/pull/78) | `db9b0c6432001d6049056eabd37422d0bfb9f75a` | [43181294226](https://github.com/mindie-agent/coordinator/actions/runs/43181294226) | 8 |
| mindie-agent-cc | [0.1.19](https://github.com/mindie-agent/mindie-agent-cc/releases/tag/v0.1.19) / [#73](https://github.com/mindie-agent/mindie-agent-cc/pull/73) | `5ea6651becfd3d6207604a9c02ecbe56a7e33862` | [43189223765](https://github.com/mindie-agent/mindie-agent-cc/actions/runs/43189223765) | 9 |
| mindie-agent-kimi | [0.1.20](https://github.com/mindie-agent/mindie-agent-kimi/releases/tag/v0.1.20) / [#75](https://github.com/mindie-agent/mindie-agent-kimi/pull/75) | `f96be0ad70b4489dbe682fb08801c6640002e09d` | [43189210790](https://github.com/mindie-agent/mindie-agent-kimi/actions/runs/43189210790) | 8 |
| mindie-agent-dsh | [0.1.18](https://github.com/mindie-agent/mindie-agent-dsh/releases/tag/v0.1.18) / [#46](https://github.com/mindie-agent/mindie-agent-dsh/pull/46) | `40bbf51deea5df27e97d29f97ed3ed75d148bc2e` | [43188097374](https://github.com/mindie-agent/mindie-agent-dsh/actions/runs/43188097374) | 8 |
| mindie-agent-agy | [0.1.10](https://github.com/mindie-agent/mindie-agent-agy/releases/tag/v0.1.10) / [#13](https://github.com/mindie-agent/mindie-agent-agy/pull/13) | `e1a3d763d1d66c5e22f48083b68ce55b145f4ee8` | [43189351414](https://github.com/mindie-agent/mindie-agent-agy/actions/runs/43189351414) | 8 |
| mindie-agent-wb | [0.1.10](https://github.com/mindie-agent/mindie-agent-wb/releases/tag/v0.1.10) / [#11](https://github.com/mindie-agent/mindie-agent-wb/pull/11) | `fa22917fb8136753756cb56e26724e466d8e5ea4` | [43189365841](https://github.com/mindie-agent/mindie-agent-wb/actions/runs/43189365841) | 8 |

五端插件的自动发行元数据步骤全部成功，基准工具来源均为已发布 `mindie-bench 0.4.8` 的精确提交 `8f0abbff1559653377e12babcd0e3024c2c44e8d`。独立验证同时检查完整校验资产、源码/版本对应及候选与公开源报告的 `all_shared_components` / `passed`；未把组件升级报告扩写为各宿主 UI 或真实 NPU 验收。

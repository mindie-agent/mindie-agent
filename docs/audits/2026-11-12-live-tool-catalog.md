# 常驻工具目录动态刷新与任务绑定恢复复查

本轮复查针对“插件后台升级完成后，当前会话仍展示旧版工具说明并提示重复发送激活口令”的用户反馈，系统梳理了 `coordinator` 与六款原生宿主插件在后台更新、工具目录发现、调用转发、入参校验及错误恢复全链路上的边界。由于现场截图不含底层 JSON-RPC 原始报文，下文不强行断言截图中的每次报错均命中同一代码分支；所有结论均严格基于本机进程/配置实证、源码审查与隔离协议验收。

## 已定位并闭环的工程边界

| 边界问题 | 实际运行影响 | 修复方案 |
| --- | --- | --- |
| Codex 常驻入口在进程初始化时静态缓存工具目录 | 后端解释器与脚本已完成代际切换，但模型侧看到的仍是启动时的旧说明与旧参数列表 | 改为按当前选定的运行时绑定动态读取工具目录，并将组件入参校验与实际执行统一转发至同一代完整 helper |
| Codex 分别读取工具目录内容与缓存键所依赖的绑定文件 | 若后台升级恰好发生在两次读取之间，旧版工具目录会被挂在新修订号键下并长期驻留缓存 | 从单次读取的绑定快照直接派生缓存键，确保缓存键与目录内容严格同源 |
| Codex 独立组件代际沿用插件打包时的静态远端 Schema 快照 | 后端共享组件升级后，工具发现与前置入参校验仍可能拒绝新组件已合法支持的参数 | 自 `0.1.28` 起直接由当前选定完整 helper 的纯函数 Schema 工厂生成实时工具目录；旧版 helper 继续兼容其既有快照协议 |
| 六端常驻 MCP 服务均未发送工具目录变更通知 | 即使后续 `tools/list` 已能返回新目录，宿主客户端仍继续沿用会话启动时的工具缓存 | 公开 MCP 服务统一声明 `capabilities.tools.listChanged=true`，监听现有原子绑定切换并主动推送 `notifications/tools/list_changed` |
| Codex 宿主默认未开启工具目录变更监听 | 仅在 MCP 服务端补发通知尚不足以刷新模型下一轮推理请求中的工具定义 | 在插件安装与更新流程中通过公开配置 API（带版本 CAS 与回读校验）自动检测并启用 `mcp_tool_list_changed`；宿主不支持或回读未确认时如实记录状态 |
| Antigravity、WorkBuddy、DSH 部分常驻入口在启动时顶层导入旧模块 | 刷新的工具目录可能与常驻进程内旧版调用处理器失配 | 常驻网关仅维护连接与协议帧，每次请求按当前选定绑定动态调用对应代际的解释器与脚本；在途请求保持使用启动时的原代际直至自然结束 |
| Kimi 旧版更新控制器仅复制固定的 5 个启动脚本 | 新增传输层模块无法随旧版固定文件清单同步到位，易造成新解释器与残缺脚本失配 | 保持前端入口身份稳定，切入目标解释器后统一从匹配的完整代际目录加载唯一传输实现，不额外发明二级选择器 |
| 原生任务关联查询在构造结构化响应前抛出未捕获通用异常 | 调用方仅收到模糊报错，拿不到可继续执行的替代路径指引 | 当任务关联缺失或存在歧义时，规范返回结构化 `managed_task_context_required`、明确原因及 `submission_state=not_sent` |
| 缺少受管任务关联时错误提示仍推荐调用 `mindie.run` 恢复 | 推荐的恢复入口本身再次依赖同一个缺失的任务上下文，形成死循环 | 明确区分无需任务绑定的独立环境接口（`hosts`/`probe`/`container`/`lease`）与已授权的 `remote_bash`/原生 shell 路径；仅受管任务操作要求已登记的任务上下文 |
| DSH 将原生传输身份缺失误导为“需再次输入 `/mindie-agent` 激活知识” | 重复发送激活口令并不能修复传输层身份，反而打断用户排查节奏 | 准确报告原生适配器身份异常，并引导继续推进不依赖该入口的已授权研发步骤 |
| Antigravity、WorkBuddy 的 `serverInfo.version` 硬编码 | MCP 握手阶段返回的服务端版本号无法反映当前实际挂载的插件版本 | 改为直接从当前选定 helper 的插件清单动态读取真实版本号 |
| Windows Hook 的 Python 子进程与 PowerShell 管道未统一声明 UTF-8 编码 | 系统本地化报错文本可能破坏 JSON 反序列化或产生乱码 | 子进程与 PowerShell 通信协议全链路显式锁定 UTF-8；新增真实 shell 回归同时断言 JSON 载荷与 `stderr` 编码完整性 |
| helper 尚未拉起前的本地选择错误被误标为 `unknown` | 调用方无法判断远端业务请求是否已经发出，阻碍安全重试 | 将 helper 启动前的本地失败明确标记为 `execution=not_started`；仅实际发出但未收到响应的不透明外部调用才标记回执未确认 |
| 子进程排水（drain）宽限时间未纳入外层超时预算 | 临近外层超时上限时可能来不及优雅回收自有子进程 | 将 `5s` 排水宽限显式纳入外层总预算算术，确保 Codex 组件原生调用外层预算完整覆盖“组件执行 + helper 转发 + 子进程排水” |

目录变更观察器仅在当前 MCP 连接生命周期内记录修订号，不引入任何持久化选择器、额外任务表或新授权层；共享 helper 继续沿用操作系统进程组 / Windows Job Object 归属与输出上限保护，次要清理告警不覆盖已完成的主业务结果。

## 隔离协议与同回合刷新验收

在桌面端 `codex-cli 0.167.0-alpha.4.1` 真实宿主进程中挂载 MindIE `mcp_gate.py` 常驻入口，配合本地确定性 Responses SSE 桩服务与真实 stdio MCP 管道（零付费模型开销、零远端 SSH/NPU 副作用），实测同一对话回合内的工具定义刷新行为：

| 宿主配置状态 | 同一回合第 1 次推理收到的工具定义 | MCP 推送 `list_changed` 后第 2 次推理收到的工具定义 | 实际触发的业务工具调用次数 |
| --- | --- | --- | --- |
| `mcp_tool_list_changed=false`（对照） | `before` | `before` | `1` |
| `mcp_tool_list_changed=true`（启用后） | `before` | `after` | `1` |

> **方法学说明**：上述验收直接核验发往模型推理请求体内的真实 `tools` 定义，而非仅查询管理接口 `mcpServerStatus/list`（后者自身会重新拉取列表，不能证明模型侧推理缓存已刷新）。

与此同时，全部六款插件的常驻入口分别通过了确定性 helper 代际切换协议验收：在同一条存活的 stdio MCP 连接上原子切换激活配置（或 `current.json`）后，无需用户重复发送任何激活口令即可收到 `notifications/tools/list_changed` 通知，紧接着下一次 `tools/list` 即返回新版描述与新增参数，且新参数调用与后续 `ping` 均一次成功（在途活跃调用跨切换继续使用旧代且零重复执行）。注：该协议验收证明六端插件侧的代际选择、通知与转发链路完备，不夸大为六款宿主桌面 UI 均已完成人工端到端复测。

### 回归测试与竞态修复明细

- **各仓核心回归**：Codex 受影响范围 `88 passed / 2 skipped / 30 subtests`（含真实原生同回合刷新验收），另在显式关闭 Python UTF-8 模式下跑通 Hook 与原生入口回归 `31 passed / 11 subtests`；`coordinator` 相关回归 `91 passed / 24 subtests` 及适配器结果契约 `14 passed / 6 subtests`；`remote-dev` 目录与回执边界 `3 passed`。
- **测试客户端协议对齐**：修复了旧测试客户端将异步 `list_changed` 通知误当作调用响应、强行假定响应顺序及写完 `stdin` 立即发送 `EOF`（触发常驻网关正常的连接关闭取消逻辑）的问题，统一改用按请求 `id` 匹配响应并保持连接至响应收讫的标准 MCP 客户端模型。
- **中间失败如实留档**：一次本机完整旧环境升级试验在候选构建阶段触及既有 `85s` 预算上限并伴随临时文件清理 `WinError 32`，该记录如实保留为失败、不计入通过；同一最终源码在 Antigravity 与 WorkBuddy 的 Linux / Windows 原生旧环境升级 CI 上均一次全绿（未放宽超时预算）。
- **Codex 后续两处竞态闭环**：
  1. 初次合入后 macOS CI 暴露出一项既有诊断投递单测与后台更新检查的时序竞态（测试故意省去原生安装字段触发了 `update` 事件抢先入队）；[PR #111](https://github.com/mindie-agent/mindie-agent-codex/pull/111) 在该单测夹具中补写近期更新检查回执以隔离无关后台检查（本地 `13 passed / 4 subtests`，主干 CI 全绿）。
  2. 发版前复核通过原子替换配置文件复现了“缓存键与目录内容分次读取”的跨代缓存竞态（修复前 `1 failed / 0.59s`）以及独立组件代际回退静态 Schema 快照的问题（修复前 `1 failed / 0.48s`）；[PR #112](https://github.com/mindie-agent/mindie-agent-codex/pull/112) 将缓存键改为从同一绑定快照直接派生，并让 `0.1.28+` 完整 helper 直接通过纯 Schema 工厂输出实时目录（`40 passed / 2 skipped / 3 subtests`）。

## 存量旧进程首次迁移边界

对于本次修复前已在用户桌面驻留运行的旧版 `mcp_gate.py` 进程（如复查现场观测到的驻留代际 `0.1.26` / `remote-dev 0.11.7`），磁盘文件更新本身无法热替换已载入内存的旧版网关代码，宿主刚写入但尚未重载消费的 `mcp_tool_list_changed=true` 配置亦不能冒充当前连接已完成迁移。因此：

- 后台自动更新已将本机插件平滑升级至正式版 `0.1.28`（`e6d6018bc7e940e4bb5c49fc73837030517f3b3e`，绑定 `remote-dev 0.11.9` 与 `coordinator 0.7.8`），回执明确区分 `status=active`（安装完成）与 `applies=native_reload_boundary`（待宿主自然重载生效）。
- 存量桌面会话仅需经过一次宿主自然重载（或新开进程边界）载入新版常驻网关后，后续所有后台组件与插件代际切换即可在同一会话内全自动推送目录刷新，无需强杀用户当前活跃会话，也无需用户重复输入 `/mindie-agent`。

## 独立正式发布与升级验收汇总

本轮按独立组件与插件发布流程交付（产品组合通道 `channels/0.1.json` 保持历史 `0.1.12` 不变）：先正式发布共享组件 `remote-dev`（`0.11.8` 首发目录能力，`0.11.9` 补齐未启动 helper 错误分类与 `5s` 排水预算，两版标签与资产均保持不可变）与 `coordinator 0.7.8`，再将六款原生宿主插件精确锁定至正式标签提交并复用 `mindie-bench 0.4.8`（`8f0abbff1559653377e12babcd0e3024c2c44e8d`）共享发布流水线自动生成与核验 `mindie-plugin-release.json`。

全部 8 个仓库均通过受保护主分支门禁与标准发布事务，经固定旧版消费者独立下载校验全部 `67` 个发行资产、核验候选与公开源 `all_shared_components: passed` 升级报告，并全量通过带 `--require-siblings --verify-local-hosts --verify-github-releases` 的发布后 `R1–R6` 就绪核验：

| 仓库 | 正式版本与关联 PR | 标签精确源码 SHA | 发布工作流记录 | 校验资产数 |
| --- | --- | --- | --- | --- |
| `remote-dev` | [`0.11.9`](https://github.com/mindie-agent/remote-dev/releases/tag/v0.11.9) · [#62](https://github.com/mindie-agent/remote-dev/pull/62) | `6e9882e0fa495bf2feeef29ec86492498d364531` | [43184303535](https://github.com/mindie-agent/remote-dev/actions/runs/43184303535) | `8` |
| `coordinator` | [`0.7.8`](https://github.com/mindie-agent/coordinator/releases/tag/v0.7.8) · [#78](https://github.com/mindie-agent/coordinator/pull/78) | `db9b0c6432001d6049056eabd37422d0bfb9f75a` | [43181294226](https://github.com/mindie-agent/coordinator/actions/runs/43181294226) | `8` |
| `mindie-agent-codex` | [`0.1.28`](https://github.com/mindie-agent/mindie-agent-codex/releases/tag/v0.1.28) · [#110](https://github.com/mindie-agent/mindie-agent-codex/pull/110) / [#111](https://github.com/mindie-agent/mindie-agent-codex/pull/111) / [#112](https://github.com/mindie-agent/mindie-agent-codex/pull/112) | `e6d6018bc7e940e4bb5c49fc73837030517f3b3e` | [43197571451](https://github.com/mindie-agent/mindie-agent-codex/actions/runs/43197571451) | `10` |
| `mindie-agent-cc` | [`0.1.19`](https://github.com/mindie-agent/mindie-agent-cc/releases/tag/v0.1.19) · [#73](https://github.com/mindie-agent/mindie-agent-cc/pull/73) | `5ea6651becfd3d6207604a9c02ecbe56a7e33862` | [43189223765](https://github.com/mindie-agent/mindie-agent-cc/actions/runs/43189223765) | `9` |
| `mindie-agent-kimi` | [`0.1.20`](https://github.com/mindie-agent/mindie-agent-kimi/releases/tag/v0.1.20) · [#75](https://github.com/mindie-agent/mindie-agent-kimi/pull/75) | `f96be0ad70b4489dbe682fb08801c6640002e09d` | [43189210790](https://github.com/mindie-agent/mindie-agent-kimi/actions/runs/43189210790) | `8` |
| `mindie-agent-dsh` | [`0.1.18`](https://github.com/mindie-agent/mindie-agent-dsh/releases/tag/v0.1.18) · [#46](https://github.com/mindie-agent/mindie-agent-dsh/pull/46) | `40bbf51deea5df27e97d29f97ed3ed75d148bc2e` | [43188097374](https://github.com/mindie-agent/mindie-agent-dsh/actions/runs/43188097374) | `8` |
| `mindie-agent-agy` | [`0.1.10`](https://github.com/mindie-agent/mindie-agent-agy/releases/tag/v0.1.10) · [#13](https://github.com/mindie-agent/mindie-agent-agy/pull/13) | `e1a3d763d1d66c5e22f48083b68ce55b145f4ee8` | [43189351414](https://github.com/mindie-agent/mindie-agent-agy/actions/runs/43189351414) | `8` |
| `mindie-agent-wb` | [`0.1.10`](https://github.com/mindie-agent/mindie-agent-wb/releases/tag/v0.1.10) · [#11](https://github.com/mindie-agent/mindie-agent-wb/pull/11) | `fa22917fb8136753756cb56e26724e466d8e5ea4` | [43189365841](https://github.com/mindie-agent/mindie-agent-wb/actions/runs/43189365841) | `8` |

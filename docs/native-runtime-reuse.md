# 原生更新、Hook 与进程管理复用

[English](native-runtime-reuse.en.md) · [返回文档索引](README.md)

当前入口更新于 2026-10-16。本文保留 2026-10-15 的机制调查、选型与
重构实验；各实验仍只证明其原版本和范围，表中的“待验”“实现中”是当时
状态，不是当前首发清单。Codex/Claude Code × macOS/原生 Windows/WSL
六组合的首发证据、后续源码增量、已知问题及各仓发行状态统一见
[0.0.1 发布记录](releases/0.0.1.md)。原则 8 要求复用优先、按确证缺口
自研、删除重复管理及保留未决效果；原语实验不等于最终产品组合通过。

## 判断

重构起点曾承担过多原生插件管理器和包工具本可承担的职责。选型决定是先删除重复的
更新编排，再处理确实缺失的平台边界，而不是把两个适配器的自研逻辑
合并成更大的通用管理器。

保留现有共享 Core、SQLite 准入/队列和原生模型协议；不另建 Hook
框架、事件总线、任务数据库或独立 supervisor 产品。后台摘要需要跨越
短宿主寿命，但这不意味着每层都要实现一套 owner 判断。

## 责任与删除范围

| 责任 | 采用的机制 | MindIE 需要保留的部分 | 可删除的重复职责与前提 |
| --- | --- | --- | --- |
| 插件下载、安装和记录 | Codex / CC 原生插件管理器 | 由单一共享选择函数选择最高 Harness 兼容 Release，交给原生安装器；集中接口清单与发布门禁 | 删除旧多阶段 updater、重复选择、专用更新服务及后继链；原生无条件 latest 不能绕过兼容筛选 |
| Python 依赖与隔离环境 | uv 和提交的依赖锁 | 产品组合、平台/解释器身份、当前格式验证 | 用非 editable、按锁身份隔离的环境替代手写 venv/pip 编排；uv 不代替数据保护 |
| Hook 事件 | 宿主原生 Hook + 现有持久准入 | 身份、授权、材料下界、幂等键、提交确认 | Hook 不等待模型，不增加第二 spool/队列；只有持久提交成功才能确认接收 |
| 独立服务与操作进程树 | Windows Job；WSL systemd；macOS 最小共享 owner-pipe helper | 服务身份、单消费者、一次操作结果与 scratch 次序 | 已确认平台原语边界；删除重复 owner 推断，但保留作用域不同的 native 输出/取消保护 |
| 安装与服务绑定 | 单一安装配置、现有操作/启动锁与精确服务归属 | 锁外准备完整候选，空闲时短暂关闭准入、原子切换并检查就绪；活动调用不被切断 | 不把 native 缓存目录当长寿命运行环境；不增加多代服务路由或会话租约 |
| 业务与恢复 | 现有正文、SQLite 回执、诊断组件 | 脱敏、usage、已知/失败/unknown、发布与隐私 | 无成熟包工具可以代替这些业务语义；禁止将未知付费调用当成待重试任务 |

这张表定义责任和删除范围。2026-10-15 的 CC 结构重构提交 `23c8fb4` 已实际删除
`updater.py`、`genstate.py`、`native_claude.py` 和旧顶层 requirements；
当时 Codex 工作树已删除 `auto_update.py`、旧 runtime/update launcher、
代际租约和对应失效测试，完整集成检查尚在进行。后续正式提交与首发证据
见统一发布记录，不能把当时工作树当成最终发布身份。完整 uv.lock 增加的
机械依赖记录不视为新的管理器。验收看独立决策来源及对应产品行为，
不按新增依赖或代码行数判定完成。

## 更新：复用原生安装，补齐兼容选择

最新合同见[发布兼容与静默更新](release-compatibility-and-update.md)。
每个插件 Release 声明 Harness 支持区间及使用的接口；在线自动选择最高兼容
正式 Release，静默准备、切换，不重新授权或要求 reload。两端已核对的原生
格式没有完整的区间筛选接口，不能把 Git catalog 的单个最新提交当成兼容选择。
共享纯选择函数补该缺口，适配器只负责原生安装衔接与实际回读。

### Codex

已检查实际使用的 `rust-v0.153.4` 和
`rust-v0.162.0-alpha.17.2` 官方源码：启动路径会更新配置的 Git
marketplace，并刷新其中已配置的插件缓存。原生 CLI 也提供 marketplace
upgrade。重构前 MindIE 的 `auto_update.py:730` 把自行生成的目录注册成
local marketplace，因此没有使用这个 Git 更新通道。[C1]

插件版本采用正常 `0.0.1`，运行时使用该插件携带的固定依赖锁。更新路径
先按本机 Harness 版本筛选正式 Release，再把唯一固定候选交给原生 catalog
和安装器。该 catalog 只是候选投影，不独立选择版本。不得同时注册无条件
跟随最新提交的入口，也不能让运行时追随开发 main。

原生更新不等于旧会话安全已经成立。上述两版 `store.rs` 会清理旧版本
缓存，同版本更新还会替换原缓存目录。因此不能照搬 CC 的旧会话语义，
也不能让长期运行的摘要服务依赖宿主随时可删除的源码路径。[C2]

真实 Codex 0.153.4 app-server 实验证明：原生 marketplace 更新移除旧缓存后，
已加载会话的下一次 Hook 仍使用旧路径，并产生 file-not-found；同一 app-server
中新建的 thread 也保留旧定义。有效实验中的三个回合均由原生 Hook 在模型前
阻断，provider HTTP 请求数和模型调用数均为零。之前失败的对照实验另存，
不混入这份结论。

因此活动 worker/service 和三类入口（SessionStart、MCP、Stop）均须脱离
可删除缓存。应用数据目录使用明确 release 的稳定入口，绑定按完整 source、
依赖锁、ABI 和平台身份安装的非 editable 环境；不存在全局 current 或扫描
最新版。相同 release 标识不得覆盖为不同源码。运行时准备失败、未准备且旧
缓存消失、已完成环境损坏均须显式报告，不能暗中修补活动环境。

不可变发布是发行合同，不要求每个热入口重新哈希宿主缓存。已加载的稳定
入口继续执行已验证的固定 runtime；若错误地重发同版本，它不会因此激活
新字节。首次或显式准备、稳定入口发布时检查冲突并拒绝覆盖；版本与实际
源码回执可查询。不能把这一行为写成“所有旧会话都会检测同版本重发”。

Codex 该版本还存在 schema 取舍：AgentPlugin v1 支持 `PLUGIN_DATA` 与 cwd
展开，但不支持 legacy `env_vars` 的任意选定 provider 环境传递。实现必须验证
入口稳定性和 provider 语义两者，不能把仅切到 v1 当成等价替换。宿主特定的
必要衔接限定在一个入口，版本选择使用共享函数。这项调查当时仍要求重构后
通过 native 反例；后续稳定入口、provider 边界和实际安装证据见统一发布记录，
不把本段的宿主源码调查当成它们的验收。

### Claude Code

官方机制已提供手动插件更新及 marketplace 自动更新；第三方市场自动
更新默认关闭，不能靠 catalog 字段冒充已启用。原生更新若只跟随 latest
且显示更新提示，就不能直接兑现当前产品合同。使用固定兼容候选调用原生安装，
并避免另一条自动更新路径绕过筛选；用户已明确授权该静默策略，无需再次确认。
正常发布需要提升 manifest version，不能以同一 `0.0.1` 推新字节期望
缓存自动刷新。Git source 可固定提交。[A1]

官方当前文档明确，复制安装的插件更新后，正在运行的会话继续使用原
路径，新会话或显式 reload 使用新版本。缓存仍由宿主管理，不是持有到
MindIE 服务结束的 OS 租约，不能作为长寿命运行时的存储合同。[A2]

CC 2.1.269 的真实原生 Git marketplace 无模型实验已确认：两个测试插件从
0.0.1 更新到 0.0.2 后，旧 SDK 会话仍使用原 MCP/cache，新会话使用新 skill/MCP，两版
SessionStart 都实际执行。另一实验确认 SessionStart/MCP 均得到相同的
`CLAUDE_PLUGIN_DATA`。仍采用稳定入口与独立 runtime，避免依赖缓存永久保留。
这些是宿主实验的标签，不是已经发布的 MindIE 产品。验收客户端为 macOS
2.1.269、Windows/WSL 2.1.299；未改已有全局客户端。

### 已删除的旧管理器与保留边界

- Codex `plugins/mindie-agent/scripts/auto_update.py`：`Updater.register`、
  旧 Release 解析、多阶段私有版本切换及 `schedule_*`。
  业务准入、feed 和诊断移到各自已有边界，原未决回执保留在原处。
- CC `scripts/updater.py`：Release resolver、`build_host_package`、
  `native_install`、native 切换/回滚及 `install_schedule` /
  `uninstall_schedule`。其中 feed sync、必要诊断和服务维护不能随更新
  定时器一并消失：原生 SessionStart 调用共享 feed 的 interval/backoff，
  保留显式 sync；已有诊断组件维护在安装/SessionStart 边界执行。
  删除代码更新调度后，不再声称会话中每 300 秒自动刷新 feed。
- 删除 `legacy_migration.py` / `legacy_update.py`、旧授权推断、客户端兼容
  声明、successor 路由和版本仲裁。原 intent/unknown、授权和用户数据不删除；
  对已有开发安装的处置记录作为操作证据保留，不成为新产品的迁移框架。

两份旧 updater 不再作为生产管理器，不能仅改为调用宿主命令后继续保留。
新的选择逻辑只解决已确证的 Harness 兼容筛选缺口；安装、包缓存及记录
仍由原生管理器负责。稳定入口和完整运行时身份保留，不再维护第二个全局
产品 current 选择器。保留精确服务归属和当前格式检查，
不把原兼容状态机移到共享组件后继续保留。旧 unknown 不重放或改写。

`uv sync --locked --no-editable` 等成熟包能力可处理锁的一致性和依赖安装。
真实 native plugin 根目录必须携带 pyproject 与完整传递依赖锁，替代只固定顶层
Git 组件的 requirements。它不会
自动验证 MindIE schema、接管旧服务或保存外部操作结果。[U1]
Velopack/Tauri 面向应用自身分发，可以参考其准备/激活分离；本产品已有
宿主插件管理器，现阶段不再引入第二个应用更新器。[U2]

## 摘要：短 Hook、一个持久队列、独立 owner

流程应保持：

```text
原生 Stop
  -> 校验身份/范围 -> 现有 SQLite 持久准入 -> 返回提交确认
  -> 已有独立 Core 消费 -> 平台拥有的摘要操作树
  -> 保存结果/usage -> 清理操作树 -> 删除自有 scratch
```

Hook 的确认只表示入队；模型和发布结果由各自回执表示。持久入队不应
等待完整服务冷启动；服务唤醒失败仍需报告，并保留已入队的事实。
模型、网络操作、服务启动、Hook 入队分别使用自己的故障条件，不能因为
某个库默认 60 秒就重新增加业务总时限。

重构期间的接线审查还发现 Windows 冷唤醒没有满足这条边界：当时 Scheduler 调用
通过多个 PowerShell 子进程进行查询、ACL、注册和启动，其控制成本可能超过
CC 的短 Hook 返回时限。预热服务后的 Stop 通过不能覆盖此情况。该轮
共享实现已用 pywin32 直接调用同一 COM/ACL API，删除该 PowerShell
传输层；它只负责传输，既有所有权、intent/unknown 和就绪语义不变。
真实同任务 never-run/running/finished 的状态、LastRunTime 和 LastResult
逐值一致；新注册/启动/删除调用约 5-10 毫秒，查询约 14 毫秒，精确任务
已清理。但首次 pywin32 导入曾耗时 1.052 秒，必须包含在完整冷 Stop
时延内，不能用已预热 import 或单 API 数据代替。原 PowerShell 的 30 秒
子进程等待边界随桥接删除，COM 同步调用受整个短 Hook 的外层期限约束；
不能声称底层取消语义未变，也不增加线程、broker 或 Job 逃逸来伪造可取消性。

后续完整 raw Stop 无模型实验使用新 Python 进程和 CC `23c8fb4` 入口，
包括导入、持久准入、ACL、注册和 Run，共 0.397 秒；原 1.5 秒预算未改。
前台退出后认证 owner 已消费 metadata-only transcript，结果明确为
`no-new-material`，没有摘要调用；精确退役、consumer lock 释放、任务不存在
均核对。之前的非法配置和未知 transcript 格式 fixture 分别保留为失败。
这关闭该短入口的控制开销反例，不代替最终原生模型、材料和索引验收。

安装准备则有不同的期限来源：真实 Codex cold MCP 在宿主默认 30 秒处
终止，日志显示 uv 正下载/构建完整锁定依赖，第二个 MCP 等待同一准备锁；
该对照没有业务 turn，SessionStart 尚未发生。该轮使用两版精确源码已确认
支持的 `startup_timeout_sec` 为初始化提供明确窗口，仍保持单次准备、
失败阶段和进程清理可见。它不修改 MCP tool 或模型业务期限，也不让短
Stop 进入安装路径。CC 2.1.269 实验确认 MCP 连接与 SessionStart 并行，
后者不能充当连接前置条件。原生 `--init-only` 可在无 MCP、无业务会话时
完成首次准备：空依赖缓存实测 48.453 秒，随后连接 3.499 秒。
选定 profile 的 `MCP_TIMEOUT=600000` 也经原生 debug 回读确认影响宿主连接
窗口；没有修改全局配置。这些是初始化证据，不是业务超时或未来自动升级承诺。

Claude 当前官方文档明确 `claude -p` 退出时会取消未完成的异步 Hook。
因此仅设置 `async: true` 不能提供持久执行，异步入队本身也可能来不及
提交。优先使用短同步持久准入，之后由独立 Core 处理。[H1]

检查的 claude-mem v13.39.0 采用短 Hook 写事件、独立 worker 消费的
分层，可以借鉴。其文件 spool、数据库和 supervisor 不是本产品新增
依赖：MindIE 已有等价职责。对方源码也保留某些标记失败后的重复窗口，
不能用它证明本产品未知付费结果可安全重试。[H2]

## 平台进程管理：优先 OS，不假定三端相同

以下三行保留 2026-10-15 原语实验的结果与当时实现状态。后续产品 backend
和六组合证据由统一发布记录承接，不在这些历史行中替换提交或补记新版本通过。

| 平台 | 决定 | 需要关闭的具体边界 |
| --- | --- | --- |
| Windows | 保留共享 Core 已有 suspended spawn + named Job + kill-on-close；删除适配器对同一 owner 的 PPID 二次推断，不新增 HANDLE 监护状态机 | 真实 core 强杀的 worker 存活/先退出两例均回收后代，heartbeat 停止；未增加产品 Job 实现。CC 重判删除的定向测试已通过，最终 native 采集待验 |
| Windows WSL | systemd transient user service，`Type=exec`、`ExitType=main`、`KillMode=control-group`、`Restart=no` | systemd 255.4 实机两例均在 main 死亡后回收另建 PGID 的后代，包括已被 user manager 收养的 writer；NRestarts=0，测试 unit 清理后 not-found。产品 backend 实现中 |
| macOS | 选择最小共享 owner-pipe helper，不为每次摘要另注册 launchd job | 同 PGID 清理正常；独立 PGID 的 writer 在 core 死后继续写；逐操作 job 也不会随独立 core 死亡退出。最小 helper 的真实 SIGKILL 测试已通过，最终产品组合待验 |

以上均为无模型进程实验，不冒充六组合产品验收。launchd 的限制由
Apple 官方源码、本机 manual 和真实对照共同确认。Windows Scheduler 可承接独立
服务启动，但其 Stop 合同不代替 Job Object 的树所有权。[P1][P2][P3]

Windows 运行时已包含 pywin32，故可进一步用其 Job API 替代手写 ctypes
结构和 ABI 声明。是否替换 CreateProcess/Popen 必须单独评估 pipe、
stdio、等待与回收接口；换库不应扩大成另一套进程框架。anyio/asyncio
的正常取消与 psutil 的后代扫描，都不能单独兑现调用者 SIGKILL 后
仍有可靠清理者的承诺。

macOS helper 由 core 持有 owner pipe 唯一写端；wrapper 建立同进程组 watcher
后 exec 适配器，保留原 PID/PPID/PGID。EOF 只终止自有操作组，不写业务状态、
不重试模型、不清理 scratch。启动握手继续区分确证未 exec 和结果未知。
正常路径仍先保存结果/usage，再清理进程树，最后删除 scratch。

## 单一安装与精确服务归属

共享核心 `6a4bbf8` 已删除开发版本客户端声明、后继链和旧配置迁移，
历史实验不成为维护承诺。产品 Release 排序仅用于当前 Harness 的兼容选择，
实际数据和内部接口仍按自己的 FORMAT 判断。

采用单一 canonical 安装配置。稳定的原生入口在每次调用时读取该配置，
使用其中完整的解释器、脚本及 engine 身份执行，不能混用不同安装的文件。
旧入口不自行选版、准备或回写绑定；正常更新不使其永久报 reload_required。
模型和授权配置独立于代码身份，贡献范围、停用和故障上报选择继续生效。

更新先在锁外准备候选，再尝试现有操作锁的排他模式。业务操作持共享锁，
其他业务和取消可以并行；更新拿不到排他锁即延后，不能阻塞取消或截断长任务。
服务还须确认队列、摘要及其他已准入工作均空闲，才能精确退役并原子切换绑定。
切换期间新请求可以短暂等待或明确返回尚未执行的暂时不可用；不要求用户重载。
30 秒是切换控制阶段的观察窗口，绝非业务执行上限；各平台实测归属见统一发布记录。

共享 Core 继续以完整配置 fingerprint、认证连接、消费锁和启动锁判断归属。
退休记录只防止旧 owner 复活，不保存后继路径。新安装使用自己的不可变 engine，
不得原地重写旧配置。切换前失败保留旧服务；退休后配置写入或启动失败的恢复
必须单独验证，不能以安装成功冒充服务可用，也不重放任何 unknown 操作。

这是一份安装绑定和一次空闲切换，不引入多代路由、会话租约或第二个更新服务。
已有正文、游标、usage、授权和未决结果保留；具体合同与验收见
[发布兼容与静默更新](release-compatibility-and-update.md)。

## 历史重构验收计划与当前后续

以下是该轮替换旧实现时使用的验收计划，保留其检查职责。已完成项及复用范围
以统一发布记录为准，不因本列表保留就要求重新安装、重跑模型或重放 unknown。

1. 保留已完成的原生 marketplace 更新实验，补验实际稳定入口与缓存删除
   边界、完整绑定切换、失败可见及卸载只清理自有项。验证最高兼容选择、
   业务忙时延期、短闸门和恢复，不增加多代兼容分支。
2. 无模型验证独立环境：锁不一致拒绝、安装中断可定位、旧环境继续有效、
   数据不位于插件缓存，活动操作不被新依赖替换。
3. 三个平台分别验证 owner 强杀、native 先退出而后代持有 pipe、显式
   cancel、结果已保存但清理失败。macOS 先比较平台方案再选择实现。
4. 验证短 Hook 的提交/返回次序、宿主立即退出、入队前失败和服务未就绪；
   不以 Hook 进程启动、健康检查成功或 async flag 作为采集成功。
5. 替代路径通过后再删除重复 updater/owner 逻辑，补受影响的六组合原生
   采集。复用未变读取和正文证据，不重放历史失败或 unknown 付费调用。

当时的停止条件是“未完成这些条件前，`0.0.1` 保持未发布”，不代表当前
各仓发行状态。当前已明确接受 Codex child interrupt 可能留下本地 helper/SSH
或已启动远端命令的首发已知问题，不增加补偿实现，不将实验 patched Harness
分发为产品，也不把主线程取消或持久 job 停止证据扩大到 child。
后续跟踪上游修复和独立 benchmark；Kimi 不在本次首发范围。
这里的可靠性、产品兼容及维护边界验证不构成模型效果或成本收益承诺。

## 主要依据

调查快照保留在本轮 `dispatch/reuse-review-20261015`，含官方 URL、
版本、源码及 SHA256。UPDATES、HOOKS、PROCESS 分别保留各专题细节；
本节公开链接不包含内部机器、账号、配置或凭据。

- [C1 Codex 已测试版本的启动更新](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/core-plugins/src/manager.rs#L2733)，
  另一已测试版本为同路径 `rust-v0.162.0-alpha.17.2`，不是对所有版本的断言。
- [C2 Codex 缓存替换与旧版本回收](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/core-plugins/src/store.rs#L699)。
- [A1 CC marketplace 发布与更新](https://code.claude.com/docs/en/plugins/host-marketplace)；
  [A2 CC 加载与缓存](https://code.claude.com/docs/en/plugins/loading)。
- [U1 uv 锁与同步](https://docs.astral.sh/uv/concepts/projects/sync/)；
  [U2 Velopack 集成职责](https://docs.velopack.io/integrating/overview)。
- [H1 CC 后台 Hook 合同](https://code.claude.com/docs/en/hooks#run-hooks-in-the-background)；
  [H2 claude-mem 固定提交的 spool](https://github.com/thedotmack/claude-mem/blob/fef3402e674bebbf72a23aeb735e91c92cd34afd/src/shared/hook-spool.ts)。
- [P1 systemd v257 kill 合同](https://github.com/systemd/systemd/blob/v257/man/systemd.kill.xml)与
  [service 合同](https://github.com/systemd/systemd/blob/v257/man/systemd.service.xml)，
  版本仅指定引用，不代表 WSL 安装版本。
- [P2 Apple launchd manual](https://github.com/apple-oss-distributions/launchd/blob/d448a1c8f70a61202f8705f94337f686b87c30c4/man/launchd.plist.5)；
  [P3 Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)。

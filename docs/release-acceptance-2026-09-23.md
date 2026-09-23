# 安装维护与原生流程验收

2026-09-23，进行中。本文记录本轮实际结果，不替代此前版本的历史记录，
也不把检查通过当作真实环境验收。

## 调度取消

Codex、Kimi、Claude Code 候选均在 macOS 真实 launchd 上验证：
任务不存在时幂等返回；存在时执行一次 bootout，核对不存在后才移除 plist。
成功取消约 0.22 秒。失败验收仅将 bootout 的目标改为不存在的 GUI domain，
实际系统返回 112；原有服务仍能查询且 plist 保留，约 3.04 秒返回失败。
这是明确的系统失败注入，不是自然发生的操作系统故障。测试使用独立 label，
结束后真实查询均为 113（不存在）。Codex 卸载拒绝继续删除的边界另有组件检查。

## 独立上报入口

以下在正式旧基线上确认原生入口接线，不代表新上报器版本交接已通过。
使用独立上报配置、日志目录和 macOS 服务，无故障注入或 Issue 上传。

- Claude Code 官方适配器 `f84690fb`、用户既有 DSV4 路由 `deepseek-flash`，
  请求 effort=high。原生 enable 在 5.458 秒完成，只执行一次返回的 ensure 命令；
  真实 worker 健康、launchd active。原生 disable 在 2.368 秒完成，随后 worker 退出。
  临时 provider 配置已恢复，全局文件逐字检查未变。
- Codex 官方适配器 `0f17d8e4`、`gpt-5.6-luna` / max，原生 Skill 入口完成
  status → enable → 返回的 ensure 一次 → status → disable，五步均 exit 0；
  status 确认真实健康 worker 和 active 服务。模型尚未结束回答时，控制器到达
  180 秒上限并退出，因此只确认控制链路，不宣称该原生模型 turn 完整结束。
  与 CC 读取同一独立设置，关闭状态可见；自有服务已移除，全局文件逐字未变。
- Kimi 正式适配器 `4ab2a6f5`、K3/max，status、enable、disable 三个原生轮均
  completed；enable 只执行一次入口返回的准确命令，独立只读查询确认正式
  diagnostics 0.3.0 的 runtime ready、launchd active、worker healthy。关闭后
  enabled=false，worker stopped；自有 launchd 已移除、进程无残留、知识数据库
  未创建、Issue 提交为零，全局 Kimi 配置哈希不变。宿主在三轮完成后由控制器
  终止清理，不宣称自然退出。此项不代替候选 0.4.0 升级验收。

## 持久安装路径

Codex 正式基线 `0f17d8e4` 在全新隔离 profile 中安装。初始解释器位于持久数据目录，
setup 和 enable 都使用它；原生安装回读成功后移走下载源码。随后保留入口的 status
成功，稳定 launcher 在 6.787 秒完成真实主分支解析、精确依赖安装、原生插件更新和
公共知识同步。原生 inventory 回读版本与更新器提交一致。关闭调度、卸载更新器后，
原生 plugin/uninstall 返回成功，plugin/list 确认 installed=false、enabled=false。
共享生产配置逐字未变，未触发模型、经验采集或故障上报。

仅测试 schedule label 与 RunAtLoad=false 做了隔离，其他系统/API 操作均真实；
本案手动调用稳定 launcher，因此不计为新增 OS 定时投递证据。它验证文档的源码
独立性和普通安装入口，不代替本轮候选代码的最终包验收。保留运行目录供审计，
未将递归删除数据目录作为卸载步骤。

Claude Code 正式基线 `f84690fb` 同样在独立 profile 完成自建持久运行时、实际原生安装、
移走下载源码、保留 launcher 的 status/check、独占 LaunchAgent 的注册及取消，最后
实际原生卸载并回读 plugin list 为空。README 的配置路径选择片段也实际成功执行。
整组 43.887 秒，零模型、零自动重试，贡献保持关闭、上报未配置、自有进程无残留。
setup 仅为保护生产 label 使用了 no-schedule，调度随后通过真实生成逻辑和独立 label
单独验证；不计为 OS 自动 tick 或本轮新候选验收。

Kimi 正式基线 `4ab2a6f5` 在独立且无模型认证的 profile 中完成 setup、原生安装、
移走下载源码，以及 README 保留入口的 status/check；48.015 秒完成，check 实际
选择正式提交，原生 2.0.2 回读版本 `0.1.0+mindie.4ab2a6f5b77d`，两 MCP、两 Hook
和十条命令均正常注册。卸载路由由该原生 Web 的 OpenAPI 和前端调用共同确认，
只调用一次后回读插件列表为空。未手改注册表，也未调用模型；贡献 OFF、未配置
故障上报，独立 Web 进程已退出，全局配置逐字未变。没有注册调度，因此不计为
OS 定时投递。本项仍是正式基线上的安装路径证明，不代替最终候选验收。

## 上报器版本交接

首轮正式 0.3.0 到候选 0.4.0 的真实 macOS 交接失败，返回 command_failed；运行时
按设计恢复旧版，实际新 PID 健康，source 与原 0.3.0 一致。失败及回滚状态保留。
随后关闭测试授权、注销自有服务，没有清理尝试记录或再次尝试同一失败目标。
因此本案只确认真实回滚成功，升级尚未通过。

只读复核确认失败 generation 的解释器、dist 元数据和 0.4.0 包可正常验证，尚不足以
断言首次失败来自哪个 launchctl 操作。实现原本丢弃 ServiceError 已有的 action 和
returncode，使 command_failed 难以定位；本轮将保留这两个静态事实，不引入原始
命令、stderr 或新日志框架。后续验收保留此次失败，不覆盖为成功。

完成修复后使用独立的新 case 验证非 editable 的 0.4.0 候选，source 为
`4614bdc4ace3359a2445a04aa2a01f91d4e054a68e8c9cf336f240a796c68668`。
真实 CLI 只给 4 秒预算时跳过交接，旧 PID、source 和尝试记录均不变。正常维护
在 0.371 秒完成 0.3.0 → 0.4.0，真实 launchd active、worker healthy；再次维护
保持同一 PID。随后只把本地验收副本的版本改为 0.4.1，对已核对归属的新进程执行
一次 SIGKILL，8.492 秒内真实恢复 0.4.0，worker 和 current 指针一致。相同失败
目标的下一次检查返回 suppressed，没有新增启动动作。停止后、关闭授权后均不
复活；结束时服务不存在，自有 worker 无残留，故障事件和 Issue 提交均为零。

该次实机候选包含当时等待删除确认的停用旧文件，不是最终发布包。低版本不降级、同版本
异内容冲突，以及授权变化和写入故障目前另有开发检查；不将这些混记为本次 OS
注入结果。独立开发检查在排除三个待删除旧测试文件后为 246 passed、3 skipped，
这不等于完整仓库 CI 已通过。旧 case 的失败记录与新 case 的成功证据均保留。

用户随后明确授权删除五个旧文件。核对文件与 HEAD 一致后已按准确路径删除，
没有残留模块引用。最终文件集的完整 diagnostics 本地检查为 246 passed、
3 skipped，没有排除测试文件；跳过项为 macOS 专用检查的两个 Windows 参数
以及依赖真实 Linux systemd 解析器的一项。这不替代远端 CI 或最终安装包实机验收。

## Kimi 实际业务与经验质量

Kimi 正式适配器 `4ab2a6f5`、K3/max 在专用 NPU 容器做一次真实依赖与运行时检查。
第一次原生进程在读取结果前到达上限；用户要求继续后恢复原任务，只读取既有结果，
没有再次执行远端命令。续轮业务完成，真实 Stop 产生一份新 capture，随后自动整理
成一条经验。整个宿主最终按控制器截止期限退出，不能宣称一次无人干预完成。

实际记录包括包依赖冲突、成功导入、采样的库名，以及 1024 个 int32 元素的一次
NPU 加法与 CPU 结果相同。原生回答将依赖冲突概括成仅与 profiling/可视化有关，
并扩大了这一次小用例的意义。整理正文区分了最后回答的归属，但检索摘要仍沿用
未经工具记录支持的包类别判断。另有四段公开软件版本被误当 IPv4 脱敏。

因此在正常发布等待期内关闭了该项目贡献，保留原草稿作为失败证据；没有手改草稿、
调用发布器或创建 PR。服务、lease、自有进程与容器均已清理。此项证明真实 Stop 和
自动整理已发生，**不证明经验质量、自动 PR、Bot 合入或新任务消费已通过**。
修复仅收紧整理提示的事实归属，并区分有明确语法的软件版本和网络地址，不增加
额外判断模型、强制总结模板或自动重试。

对实际 remote_read 输出的独立子进程复核确认：旧版将两处公开软件版本全部移除，
候选保留两处，原输出中的真实地址仍被移除。豁免只限 pip-check 的明确包版本语法；
代码审核发现通用 package==version 豁免能误放过 URL/query/路径拼接，已删去这项
额外豁免。44 项相关开发检查通过，与实际来源复核分别记录。三个整理提示已同步
要求摘要只记录动作和直接观察，其模型内容效果仍须新原生工作验证。

修复后的独立 Kimi/K3 max 任务随后调查导入期间的提示来源。三个实际远端命令及
各自的一次状态读取均已成功结束；单独 import torch 的 stdout 输出版本与完成标记，
stderr 出现 `can not use command: npu-smi info`。这只证明提示出现在该进程期间，
未定位具体代码源或原因。600.023 秒硬截止时，宿主仍在等待第四个命令
import torch_npu 的原生审批；该命令未执行，业务轮未结束，也没有业务 Stop。
本案仅有配置轮的零条整理，业务 capture、草稿、outbox 和 PR 均为零。没有续轮、
重跑命令或手工生成经验，因此本次不证明候选提示的内容质量或 Kimi 发布闭环。
贡献已正常关闭、任务已撤销激活，lease 为空，服务和自有进程已退出，专用容器
恢复停止状态；本案认证材料已移除，全局 Kimi 配置未变。

进一步复核表明，600 秒是验收控制器从宿主启动开始计算的自设上限，不是产品或
Kimi 限制。前置阶段用了 157.587 秒；业务阶段约 442 秒中，已解决的七段审批等待
共 203.360 秒，最后一段又等待约 66 秒。它们是验收操作者处理原生审批的等待，
不是用户迟迟未授权。控制器没有及时处理最后的审批，也没有正常请求业务收尾，
因此这次缺口首先属于验收编排。后续分别记录各阶段，及时处理已有授权内的审批，
保留单操作超时及禁止自动重放，不把一次开放业务的总墙钟时限变成产品规则。

## 尚待完成

共享正式发布已完成：diagnostics [PR11](https://github.com/mindie-agent/diagnostics/pull/11)
合入 `7c56f6b510b48fa60f256b46f71805e3be61eed8`（0.4.0）；knowledge
[PR51](https://github.com/mindie-agent/knowledge/pull/51) 合入
`e822fba4e95a69c8c4299e31f73db79ed62a106a`（0.8.2）；remote-dev
[PR22](https://github.com/mindie-agent/remote-dev/pull/22) 合入
`28213bf3065e173216794c43ad021ef169e6a8c9`（0.9.5）。各 PR 的准确 head 与 CI
已回读，diagnostics 七项、knowledge 三项、remote-dev 五项均通过。
共享组件的非 editable 安装和准确 VCS 依赖回读通过；这不扩展上述实机结论。

三端随后按同一共享提交完成全新非 editable 安装及依赖 direct_url 回读；本地完整
组件检查为 Codex 141、Kimi 129、Claude Code 88 项通过。三端 PR 的准确 head
远端 CI 均通过并已合入：Codex [PR10](https://github.com/mindie-agent/mindie-agent-codex/pull/10)
`6146d862ec6b6f0ae018849a258fc1adc5b67c66`；Kimi
[PR8](https://github.com/mindie-agent/mindie-agent-kimi/pull/8)
`d258d144838a7a83dd4b737e7f3885443ec20402`；Claude Code
[PR8](https://github.com/mindie-agent/mindie-agent-cc/pull/8)
`c909363fd6cd625b1943bbe6bc309f2bc278b471`。此段只确认发布和开发检查，
实际宿主安装与业务结果另记。

下一项 Kimi 验收使用用户授权的实际算子开发任务，贡献开启。任务采用原生自动
审批，允许自主修复开发及插件问题，不设置整项业务截止；半天后检查进展。
原生 Stop、自动整理、发布和新任务复用仍按实际发生分别判断。

共享上报器候选交接及失败恢复、三端正式基线的持久安装路径已通过上述真实 macOS
检查；三端最终提交安装回读仍待本轮完成。新知识贡献须使用修复后的真实新工作；
旧失败材料不重放。
后续结果在本文追加准确版本与限制。

Windows 由用户在合入后使用专门机器推进。旧业务 Skills、profiling、自动 Skill
提炼与新领域扩展保持暂缓。

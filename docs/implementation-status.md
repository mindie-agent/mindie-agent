# 统一实施进度

2026-09-21，本轮已完成的 P0/P1 修正已合入共享运行时、三个适配器与知识仓库。macOS 已有原生使用、实际 OS 定时投递、知识撤下和反馈自动提 PR 的证据；真实业务经验已完成自动提 PR、Bot 审阅合入、默认定时同步及新任务实际 NPU 使用；这次 Bot 恢复和业务脚本均有明确的人工介入，不能称为全程无人干预。本文不作为首版全部验收通过的结论。Windows 仍在首版支持目标内，按用户安排在合入后使用专门机器验收。

MindIE Agent 完整继承[九条原则](design-principles.md)。主任务负责设计、文档、跨仓审核和最终验收；开发通过本地模型与专门子代理协作，个别已明确授权的定点修复由主任务接手。检查范围与实际变化相称，不增加每任务必查、必写、必投票或额外审批流程。宿主要求的信任确认仍由用户完成。

## 2026-09-21 后续代码质量审查

已完成十仓主要入口的主任务审查与本地 Kimi K3/max 独立审查，详细问题、处理状态和实机证据见[跨仓质量审查](quality-review-2026-09-21.md)。架构保留共享核心、原生适配、Git 分发和独立远端工具；本轮重点补齐故障可见性、取消控制、安装一致性及日志保留，未增加统一 Harness 或自动重试框架。以下历史 P0/P1 表保留当时合入基线；最新修复按该报告和准确 PR 状态判断。


## 历史 P0/P1 合入基线

| 范围 | 本轮合入 | 解决的问题 |
| --- | --- | --- |
| 共享知识运行时 | [PR46](https://github.com/mindie-agent/knowledge/pull/46)、[PR48](https://github.com/mindie-agent/knowledge/pull/48)，main `59b6ec4f` | 回执与续写、脱敏误报和同步状态修正；失败保留静态类别、退出码及耗时，旧退出码保持未知，不保存原始 stderr 或重放失败材料 |
| Codex | [PR4](https://github.com/mindie-agent/mindie-agent-codex/pull/4)、[PR5](https://github.com/mindie-agent/mindie-agent-codex/pull/5)，main `5e785f12` | 忠实经验与逐源同步状态；修复更新停止知识服务后不恢复，保留失败/中断状态且不自动重放 |
| Kimi | [PR2](https://github.com/mindie-agent/mindie-agent-kimi/pull/2)、[PR3](https://github.com/mindie-agent/mindie-agent-kimi/pull/3)、[PR4](https://github.com/mindie-agent/mindie-agent-kimi/pull/4)，main `ff733aea` | 忠实经验、逐源同步状态和当前版本调度入口；更新后恢复服务，保留安全失败诊断，取消时终止核心拥有的原生进程组 |
| Claude Code | [PR2](https://github.com/mindie-agent/mindie-agent-cc/pull/2)、[PR3](https://github.com/mindie-agent/mindie-agent-cc/pull/3)、[PR4](https://github.com/mindie-agent/mindie-agent-cc/pull/4)，main `f9585a39` | 忠实经验与同步状态；恢复更新后的服务，读取明确的原生 DSV4 设置，修正异常回读；取消时终止核心拥有的原生进程组 |
| 知识分发 | [PR14](https://github.com/mindie-agent/knowledge-vllm-ascend/pull/14)、[PR15](https://github.com/mindie-agent/knowledge-vllm-ascend/pull/15)、[PR16](https://github.com/mindie-agent/knowledge-vllm-ascend/pull/16)，main `6449d005` | 可信发布校验、实际反馈和新增 NPU 经验；内容仍作为不可信数据处理 |

合入、开发检查和真实环境验收分别判断。CI 不证明原生工具实际加载、Hook 交付、模型内容正确或 Bot 事件投递。下文复用前一轮已通过的安装、任务接续及回滚证据；不把旧版本验收自动扩展成所有新路径通过。

## 已有真实环境证据

| 范围 | 已证实的行为与边界 |
| --- | --- |
| Codex 原生使用 | Luna/max 显式只读启用、检索和正文读取；同任务跨更新保留授权，旧入口及原远端作业仍可用；安装独立于临时配置环境变量；真实安装结果丢失后恢复旧包并准确回读。生产现已安装 `5e785f12`，实际原生回读版本 `0.1.0+codex.20260921115848075986`，Hook 的命令、hash、2 秒超时及 trusted 状态均与先前一致；原已信任入口按配置选择新运行时。此前 `b6c9a88b` 上的新 Luna/max 任务实际触发 Stop，48 毫秒完成；本次未仅为重复未变入口再跑模型，也不将无贡献触发称为采集发布验收 |
| Kimi 原生使用 | 2.0.2 / K3 max 实际加载两 MCP、两 Hook、七命令；只读及跨更新任务/作业接续；移走源码和清除配置环境变量仍可读取；真实安装结果丢失后回滚。新增原生 fork 只发起一次 query，因未显式启用被拒绝，未继承原任务授权、未自动激活或重试 |
| Claude Code 日常使用 | 2.1.269 / `deepseek-flash` high：从干净隔离配置实际安装，首次给出推荐贡献、只读、稍后三个选项；只读选择持久化。原生默认审批模式下 query 和 explain 各经一次交互确认，返回两条引用与完整正文。贡献关闭时无采集、整理或发布；另有新任务/fork 隔离、跨更新接续及真实回滚证据 |
| 三端 macOS 定时检查 | 使用生产注册逻辑生成入口，仅隔离 label、路径和验收间隔；`RunAtLoad=false`，实际等待 launchd 投递，未手动触发 check。修正后 Codex、Kimi、CC 均记录首轮 `runs=1 / exit=0`，随后移除测试定时器。证明当前版本选择及真实投递，不代表三个最新包均发生了一次升级，也不代表 Windows |
| 同步错误可观察性 | 三端实际访问正式 GitHub 源及不存在的源、竞争真实本地锁、移除锁后恢复；分别报告 degraded、deferred、ok，并保留原知识正文。共享组件的实际同 commit 恢复清除旧失败信息。此项是无模型的运行时/Git 集成验收 |

Claude Code 使用用户明确保留的 DSV4/provider 栈，实际模型别名为 `deepseek-flash`，不能称为 Anthropic 基础模型验收。用户已取消 OAuth-only 要求，未将它列为缺口。关闭贡献仍可按需运行只读知识服务；这与采集、整理任务材料是不同边界。

真实失败记录仍保留：Kimi 旧调度入口不接受 `--config`，首次验收在发现前发生三次 OS 投递并退出 2；修正选择当前版本后首轮成功。旧 CC 隔离源 `local/unconfigured` 失败却被汇总成成功的问题，已由本轮逐源状态修正，并通过实际失败/恢复路径验收。修复不覆盖原失败证据。

## 更新后的服务交接

三端本轮均已修复实际更新停止知识服务后不恢复的问题。停止前保留未完成标记；确认旧端点退出，完成原生安装或回滚后，只恢复本次确实停止且仍有有效授权的服务。失败和中断在后续同版本检查中仍可见，不据此自动重复启动。Stop 不负责启动或补救，不重置已有采集游标或失败记录。

实际本地 daemon 验收覆盖 Kimi/CC 的正常切换、原无服务、授权撤销、回滚，共八例；另有交接状态复验和更新父进程被中止后的未完成状态保留。它们采用受控 native install 边界，以下才是独立的真实宿主结果：

- Codex 使用真实 CLI 安装候选、准确回读并替换已有服务 PID/端点，4.64 秒完成，选定运行时正常且未冻结，无安装替身或更新后手动 ensure。生产随后显式安装已合入的 `5e785f12`，7.40 秒完成；原定时器、贡献设置、六条历史尝试及旧入口保持。旧更新器曾因移除的旧 helper 判为 incompatible，历史保留，不伪称它自动更新成功。
- CC 使用真实原生安装与回读，7.32 秒完成实际服务交接，授权未变。清除 shell 的 provider/model 环境，只把既有 DSV4 设置暂存于指定原生 profile；随后原任务以默认审批模式完成 1.07 秒、零工具的一轮，真实 Stop 产生一个 organized capture，后台整理一次成功并返回零条，未制造 PR。独立进程采样没抓到短暂的整理器 argv，因此 high effort 是已配置和源码传递证据，不宣称额外观测到了服务端采纳。验收脚本此前的路径断言错误及最后采样断言失败均保留，不靠重跑模型掩盖；临时设置、贡献和服务已清理。
- Kimi 使用真实 native API 安装并准确回读，新服务 PID/端点、选定 Kimi home 及原授权均确认。原任务 K3/max 随后 27.3 秒正常完成、零工具；其真实 Stop 成功入库，没有用 query/ensure 掩盖服务离线。该 capture 只消费下一个尚未读取区间，没有重放旧区间；但后台整理单次退出 2，未产出经验或 PR。约 128 秒后观察到失败不能单独证明是 120 秒超时；原生配置 doctor 通过，错误细节因现有 stderr 处理不可还原。该 Stop capture 的整理未成功，完整 Kimi 贡献链路仍未通过。

安装前显式建立一个旧服务作为验收前态，不算更新器自动恢复；底层 stage/switch 验收不冒充 OS 定时器执行了完整 check。各范围的实际行为分别保留记录。

## 整理失败诊断与进程取消

共享运行时新增静态错误类别、退出码和耗时；旧版退出 2 仍为未知。Kimi 适配器以已审查的退出码报告配置、超时、原生调用、无效结果或输出上限，不保存原始 provider stderr，也不增加数据库、模型调用或重试。

审核同时发现 Kimi/CC 的旧 runner 会为原生模型另建进程组。真实 macOS 复现确认，核心取消后整理器已退出，原生子进程仍活；CC 的孙进程同样残留。修复沿用 Codex 已有的核心进程组所有权：整理期间原生进程继承核心拥有的组，适配器只清理直接子进程，核心负责终态整组清理。Kimi 取消及正常成功的真实进程验收均无残留；CC 同类验收也通过，真实 Claude CLI 能正常返回版本并退出。这些受控子进程验收与模型内容验收分开。

最终 Kimi 适配器固定官方 core `59b6ec4f`，无源码路径覆盖。一次独立的真实 K3/max 整理使用全新材料，34.371 秒生成一条忠实记录；实际采样确认原生 Kimi 与整理器同属核心进程组，结束后无残留，隔离配置清理完成。没有重放旧失败 capture、创建数据库记录或发布 PR。这证明修复后的原生整理可用，不能事后解释旧退出 2，也不替代 Kimi 的完整 Stop 到发布验收。

对应诊断问题 [knowledge #47](https://github.com/mindie-agent/knowledge/issues/47) 已关闭；公开证据见 [Kimi 整理诊断](https://github.com/mindie-agent/mindie-agent-kimi/blob/main/docs/organizer-diagnostics.md)与 [CC 进程取消](https://github.com/mindie-agent/mindie-agent-cc/blob/main/docs/process-cancellation-acceptance.md)。

## 经验内容、续写和贡献边界

三端整理提示现要求忠实记录材料中实际发生的过程和现象，未交代的直接省略；不强制提炼教训、编造失败到成功的故事、补未知清单或增加因果结论。`title`、`summary` 用于检索；可选 `conditions` 只记录已有版本或 commit，实验参数与细节放正文。只有配置和状态流水时可以返回零条。

本地实际整理器重放了同一份既有 NPU 任务公开记录：Codex Luna/max、Kimi K3/max 和 CC deepseek-flash/high 均生成一条，保留原数值、dtype-rounded CPU reference 和原范围限制，未把设备设置从 8 改为 0 推断为“8 已运行失败”。CC 对当天真实首次配置材料返回零条。四次调用均无自动重试。这证明这些材料上的整理质量，不是新 NPU 测量或 Stop 到发布的全链路证明。Codex 的实际产物已符合最终省略语义，最终提示措辞调整后未仅为重复结果另跑模型；Kimi 与 CC 使用最终提示。

随后一个全新的 CC 原生任务实际完成 `[9,512]` 的 RMSNorm 非连续视图/连续副本检查，FP16/BF16 两路均通过各自 CPU reference 比较，直接输出比较均相等。首次脚本提议在写入和执行前被审批反馈纠正返回元组的处理；修正版只执行一次，237.93 秒内正常结束。原生 Stop 触发后台整理，生成正文 4,321 字节的一条经验，忠实记录了这次执行前纠正，未虚构运行失败。默认静默窗口随后自动生成 [知识 PR16](https://github.com/mindie-agent/knowledge-vllm-ascend/pull/16)，head `058873408d30216635c1b33acf7de32afe772da9`，两项发布检查均通过。未手写经验、调用发布器或手动派发 Bot 审查。确认远端接收后，该条本地草稿正文已清理，准确 PR/head/ref 回执保留，批次缩为 570 字节；随后正常关闭本项目贡献和验收服务。此项已证明真实工作到自动提 PR 与提交后清理；后续 Bot opened 及新任务消费的实际结果见下文。

另一个全新 CC / deepseek-flash high 任务随后验证公开知识的实际使用。它使用默认 300 秒、`RunAtLoad=false` 的真实 OS 定时器同步主分支 `6449d005`；首轮 303.17 秒完成，未手动运行 sync。原生产草稿正文在此前已经清空，目标条目此次来自 Feed，published revision 为 `8b7fbaf7`，不是本地草稿回退。新任务正常 query/explain 后，在首次脚本中已采用经验的 tuple 解包、按目标 dtype 舍入的 CPU 参考计算、逐路径参考比较及直接输出比较。

这次新任务使用 `[3,3072]` 输入、`[3072]` 权重，并实际记录 NPU 非连续输入 stride `[6144,2]` / 权重 `[2]`，与连续副本不同。FP16/BF16 的两条路径分别通过参考比较，直接 `torch.equal=true`，路径间最大差为零。首稿在执行前因转换步骤不能保证 NPU 非连续布局等问题被人工纠正一次；修正版只执行一次，整个原生进程 307.75 秒正常结束，没有失败重跑。模型最终对 BF16 残差给出的原因并未被实验支持，不计入结论。这证明经验被实际读取、采用并影响新任务方案，但不是完全自主正确或受控提效实验。贡献关闭的消费任务新增采集、整理、草稿及 PR 均为零，临时服务、配置和定时器已清理。

真实 PR13 的已确认发布状态用于核对清理与续写：GitHub 准确 head 确认后，已发送正文被清理，仅保留轻量回执；无需等待合并才清理。Kimi 原生整理器通过正常上下文自行选中原条目 ID，运行时从回执记录的 GitHub head/path 恢复并校验原文后追加。没有手动指定返回 ID，也未重新发布这份验收副本。已发送内容可清理，不意味着丢弃尚未发送的增量或未知提交结果。

贡献关闭再开启的本地实际设置与撤销路径已验证：新 generation 不接收旧材料；已有未发送续写候选从一条变为零，旧回执和只读检索仍保留。此项证明共享运行时边界，不单独证明三个宿主全部开关事件的交付。上述续写使用既有任务的真实复核材料，不能声称新增了一次独立 NPU 实验。

## 反馈、下库与 Bot

CC 在实际默认审批任务中对已读取的经验给出一次可选 `up` 反馈，后台自动产生 [知识 PR15](https://github.com/mindie-agent/knowledge-vllm-ascend/pull/15)，准确提交 head 为 `057e0ea51a0de75fd081be68771d4fe353344b4c`。Grok Bot 使用已审查的 `40063ebf` 校验器完成维护者发起的补查，并于 09:58:35Z 合入，merge 为 `ab600a16`；GitHub connector 已独立确认。这证明原生反馈自动提 PR 及 Bot 审阅合入，尚非新经验发布。

此前 GitHub MCP 连接可用，但平台仓库事件访问未建立；用户已完成 Cursor App 授权，Bot 收到仓库访问通知，三条 routine 仍只面向知识仓。PR15 的 opened 事件发生在授权前，其补查不能算原生 opened 投递。合入后 Bot 只读回报原生 `pr-merged` routine 已 succeeded，复用已有结论核对合入状态，无额外写入；运行状态与事件类型来自 Bot 的平台回执。PR16 随后实际收到原生 opened 事件，但审查申请因一次临时只读核对要求被理解为持续禁令而过期。主任务澄清该要求只针对已完成的 PR15 核对后，Bot 按原有单仓授权恢复审查，通过准确 head 的两项 CI、可信发布校验和内容审查，于 11:30:32Z 合入 `6449d005c424ffca547d559cde16876355a17aea`。未改动审批保护；这是原生事件送达后经维护者澄清恢复的完成记录，不是无人干预合入的证明。

真实下库通过专用 GitHub 分支验证，未改生产 main、未造经验、未提交 PR：从 `eb311496` 创建分支，仅删除一条既有 case，实际删除 commit 为 [`858fbffa`](https://github.com/mindie-agent/knowledge-vllm-ascend/commit/858fbffa68173a1abd116506c71be93127687375)。隔离 Feed 同步后，普通检索不再返回该条目；旧 exact ref 仍能读取相同正文，并明确 `withdrawn=true`。另一隔离 Store 仅复用同一公开正文和本地测试票，确认旧草稿/票不再进入待发布选择。没有模型、发布器或投票外发。此项证明真实远端撤下到 Feed/Store 的行为，不是 Bot 自行作出撤下决定的证明。

点赞、点踩仍是宽松的参考指标，既不强制每任务反馈，也不按票数自动删除。经验是否修正或撤下由维护者/Bot 结合内容处理；不另设候选数量、每轮写入数等产品配额。

## 仍在推进

1. 在下一次独立新增的实际工作中补充 Kimi Stop 到经验发布的证据；已经消费的失败输入不重放。本次新原生整理成功与 CC 的真实经验发布到新任务使用，均不替代这一端的完整验收。
2. PR16 已完成真实 opened 投递、维护者澄清后审查合入，以及默认 OS 同步后的全新任务实际使用。后续无需为补“无人干预”标签而制造测试 PR；下一次真实贡献可以补充该证据。经验只是参考，实机脚本仍须按当前观察审查。
3. 在用户提供的专门 Windows 机器上验收三个适配器。Windows 不作为本轮合入的前置门槛，仍是首版目标范围的未验收项。

旧业务 Skill、profiling 分析、自动 Skill 提炼及进一步领域/Harness 扩展保持暂缓。模型调用按明确边界执行，失败后不自动新开任务或反复重试。未完成项目不会因代码合并或 CI 通过而自动标记通过。

## 证据入口

公开适配器记录见 [Codex P0/P1 验收](https://github.com/mindie-agent/mindie-agent-codex/blob/main/docs/acceptance-p0p1-2026-09-21.md)、[Kimi P0/P1 验收](https://github.com/mindie-agent/mindie-agent-kimi/blob/main/docs/acceptance-p0p1-2026-09-21.md)及 [Claude Code P0/P1 验收](https://github.com/mindie-agent/mindie-agent-cc/blob/main/docs/acceptance-p0p1-2026-09-21.md)。原生任务 ID、模型、准确版本、失败与清理记录按各报告保留，不上传原始 transcript 或隐藏思考。

本轮本地审计目录 `mindie-p0p1-20260921` 中，`reports/cc-daily-acceptance.md`、`kimi-daily-acceptance.md`、`codex-os-timer-acceptance.md`、`knowledge-withdrawal-acceptance.md` 记录对应实机/远端结果；`faithful-records/review.md`、`sync-review/REPORT.md`、`acceptance/core-receipt-boundaries/review.md` 记录内容、同步和回执边界；`acceptance/cc-feedback/automatic-pr.json` 记录 PR15 的准确提交；`reports/cc-npu-producer-acceptance.md` 记录独立真实 NPU 任务、原生 Stop、自动 PR16 和本地清理；`reports/cc-npu-consumer-acceptance.md` 记录主分支同步、新任务具体采用内容、真实 NPU 结果及人工纠正边界。服务交接审计目录 `mindie-service-continuity-20260921` 记录真实 daemon、三端原生切换、失败及清理；公开代码仓库的 `docs/service-continuity.md` 保留对应证据边界。历史记录只证明当时版本，本轮未复验的路径不扩展结论。


## 2026-09-22：工具故障上报与 DFX

新增独立于知识贡献的故障上报选择；默认关闭。自有工具失败返回可定位的
incident，原错误和业务结果保留。日志限量保留并保护未读片段，上报无模型，
每候选最多三轮，未知提交只核对；不新增任务级必做流程或业务重试。

本轮真实验收已覆盖本机日志写入/SQLite 锁/轮转恢复、有限子进程与取消清理，
macOS 独立服务启动、崩溃不自启、明确恢复、关闭与移除，以及真实 GitHub
[验收 Issue 8](https://github.com/mindie-agent/diagnostics/issues/8) 的创建、回读、关闭和跨授权核对。
Codex Luna/max 与 Claude Code DSV4/high 均实际调用候选 MCP 一次并获得匹配诊断；
没有 SSH、知识采集或业务重放。CC 曾误述只读状态用途，入口提示已明确区分查询和上传。
Kimi 首次实际调用在工具执行前被 OAuth 拒绝；用户重新登录后，K3/max 在新隔离验收中
完成一次原生工具调用，诊断编号与本地唯一记录一致，无工具重试、SSH、知识采集或上传。
模型能给出定位入口，但末句“业务状态未受影响”超出工具所述的未确认结果；工具链通过，
该回答不能标记为完全忠实。Windows 实机继续后置。

共享 diagnostics 已通过 macOS/Linux/Windows 的 CI 并合入
[PR 9](https://github.com/mindie-agent/diagnostics/pull/9)。随后从主分支准确提交
`4a7e50622492c92089c2318d80dbd2a24d41f145` 非 editable 安装，实际启动独立 macOS
上报器，回读运行进程的包来源与运行目录一致，再关闭并移除测试服务。此项是最终包的
安装与服务证据；Windows CI 不替代 Windows 用户机器验收，三个原生模型的候选脚本
证据也不替代最终适配器安装回读。

随后 Kimi 和 Claude Code 都从官方精确提交完成非 editable 依赖安装、原生插件安装及
两个 MCP 入口回读；Kimi 同时验证未配置上报时可只读定位既有诊断，CC 的 72 项适配器
检查通过。两者使用隔离原生配置，未安装到用户默认配置、未启动模型或上报服务。
依赖为 knowledge `87deb071`、remote-dev `fb441aa1`、diagnostics `4a7e5062`。
对应共享组件已分别合入 [knowledge PR 50](https://github.com/mindie-agent/knowledge/pull/50)
和 [remote-dev PR 21](https://github.com/mindie-agent/remote-dev/pull/21)；
三端初次集成也已合入各自主分支。

Codex 的实际定时更新器从旧版安装新主分支后，发现旧打包器不会生成新增诊断版本文件。
这项升级缺口经[Codex PR 9](https://github.com/mindie-agent/mindie-agent-codex/pull/9)
修正：从当前加载包自己的 manifest 与匹配安装回执读取版本，不猜提交、不改写已安装文件。
实际定时器已安装主分支 `0f17d8e4`，原生版本为
`0.1.0+codex.20260922125204298352`；实际包、依赖提交及诊断元数据均已回读。
截至本次核对，生产 Stop Hook 原生信任状态仍为 `modified`，超时 2 秒；
已请用户审阅信任，尚未将新版原生 Stop 触发标为通过。生产故障上传保持未配置。

复查也确认 Kimi/CC 旧打包器只复制原有启动依赖，首次升级可能遗漏新诊断模块。
[Kimi PR 7](https://github.com/mindie-agent/mindie-agent-kimi/pull/7) 已修复并合入；
实际旧控制器安装和升级用时 5.249 秒，原生回读及两个 MCP 握手通过，贡献关闭时
Stop 在 0.112 秒返回，未改写旧启动目录。CC 的旧打包器还会遗漏新增上报命令的 Hook
matcher；[CC PR 7](https://github.com/mindie-agent/mindie-agent-cc/pull/7) 补充下一次既有
检查中的有限原生包刷新及完整声明回读。最终产品提交 `a2f30a89` 的真实验收从保留的旧
启动入口进入检查，在 7.153 秒完成刷新；宿主缓存持有 9 个准确命令入口、两个 MCP，
贡献关闭时 Stop 正常返回，旧包和启动文件均未改写。复用的官方依赖没有重建；该检查
使用隔离的本地 Git main，不能扩称新增 OS 定时器投递证明。

随后仅一次 Claude Code / deepseek-flash high 原生 `/mindie-agent:reporting-status`
在 2.526 秒完成，实际 UserPromptExpansion Hook 成功，返回值与本地只读查询一致，
无工具调用、上传、知识激活或重试；临时配置已恢复，无残留进程。模型却将上报未配置
推断为未采集日志，并误述为项目级配置，超出了字段含义；原生入口通过，回答不能标记
为完全忠实。入口提示随后澄清共享用户级上传设置与本地日志独立，未为该措辞重跑模型。
全新安装、旧版升级、原生事件及模型回答分别保留证据，不互相代替。

实现边界见[DFX 设计](diagnostics-and-reporting.md)。日志总量由离线维护控制，
不承诺任意并发下的瞬时全局硬配额；共享报告运行时可从状态核对版本，明确的 ensure
负责选择和恢复它。该上报器不启用旧 Grok CLI，知识审核仍由外部 Grok Bot 软件负责。

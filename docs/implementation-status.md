# 统一实施进度

2026-09-21，本轮已完成的 P0/P1 修正已合入共享运行时、三个适配器与知识仓库。macOS 已有原生使用、实际 OS 定时投递、知识撤下和反馈自动提 PR 的证据；最终业务经验的发布、Bot 审阅合入与新任务使用仍在推进。本文不作为首版全部验收通过的结论。Windows 仍在首版支持目标内，按用户安排在合入后使用专门机器验收。

MindIE Agent 完整继承[九条原则](design-principles.md)。主任务负责设计、文档、跨仓审核和最终验收；具体代码实现交给本地 Kimi/Grok，Claude Code 适配由专门子代理协调。检查范围与实际变化相称，不增加每任务必查、必写、必投票或额外审批流程。宿主要求的信任确认仍由用户完成。

## 当前合入状态

| 范围 | 本轮合入 | 解决的问题 |
| --- | --- | --- |
| 共享知识运行时 | [PR46](https://github.com/mindie-agent/knowledge/pull/46)，main `40063ebf` | 已发送正文清理后保留轻量原条目线索，后续选择续写时准确恢复；修正合法知识引用及明确 Python 数字切片被误脱敏；成功同步清除旧错误 |
| Codex | [PR4](https://github.com/mindie-agent/mindie-agent-codex/pull/4)，main `b6c9a88b` | 经验按实际过程与现象整理；逐知识源如实报告失败、等待与恢复；更新共享组件依赖 |
| Kimi | [PR2](https://github.com/mindie-agent/mindie-agent-kimi/pull/2)，main `d076b942` | 同上；调度器使用当前完整版本的入口，避免选到保留的旧 bootstrap |
| Claude Code | [PR2](https://github.com/mindie-agent/mindie-agent-cc/pull/2)，main `65500b6` | 同上；保留用户当前 DSV4/provider 配置，通过本机实际模型整理 |
| 知识分发 | [PR14](https://github.com/mindie-agent/knowledge-vllm-ascend/pull/14)，main `be39fd9` | 发布校验使用已审查的共享组件，内容仍作为不可信数据处理；本 PR 未重写既有经验 |

合入、开发检查和真实环境验收分别判断。CI 不证明原生工具实际加载、Hook 交付、模型内容正确或 Bot 事件投递。下文复用前一轮已通过的安装、任务接续及回滚证据；不把旧版本验收自动扩展成所有新路径通过。

## 已有真实环境证据

| 范围 | 已证实的行为与边界 |
| --- | --- |
| Codex 原生使用 | Luna/max 显式只读启用、检索和正文读取；同任务跨更新保留授权，旧入口及原远端作业仍可用；安装独立于临时配置环境变量；真实安装结果丢失后恢复旧包并准确回读。生产现已安装 `b6c9a88b`，原生 Hook 为 trusted；新 Luna/max 任务实际触发新版 Stop，48 毫秒完成。该任务未启用贡献，不将这次触发称为采集发布验收 |
| Kimi 原生使用 | 2.0.2 / K3 max 实际加载两 MCP、两 Hook、七命令；只读及跨更新任务/作业接续；移走源码和清除配置环境变量仍可读取；真实安装结果丢失后回滚。新增原生 fork 只发起一次 query，因未显式启用被拒绝，未继承原任务授权、未自动激活或重试 |
| Claude Code 日常使用 | 2.1.269 / `deepseek-flash` high：从干净隔离配置实际安装，首次给出推荐贡献、只读、稍后三个选项；只读选择持久化。原生默认审批模式下 query 和 explain 各经一次交互确认，返回两条引用与完整正文。贡献关闭时无采集、整理或发布；另有新任务/fork 隔离、跨更新接续及真实回滚证据 |
| 三端 macOS 定时检查 | 使用生产注册逻辑生成入口，仅隔离 label、路径和验收间隔；`RunAtLoad=false`，实际等待 launchd 投递，未手动触发 check。修正后 Codex、Kimi、CC 均记录首轮 `runs=1 / exit=0`，随后移除测试定时器。证明当前版本选择及真实投递，不代表三个最新包均发生了一次升级，也不代表 Windows |
| 同步错误可观察性 | 三端实际访问正式 GitHub 源及不存在的源、竞争真实本地锁、移除锁后恢复；分别报告 degraded、deferred、ok，并保留原知识正文。共享组件的实际同 commit 恢复清除旧失败信息。此项是无模型的运行时/Git 集成验收 |

Claude Code 使用用户明确保留的 DSV4/provider 栈，实际模型别名为 `deepseek-flash`，不能称为 Anthropic 基础模型验收。用户已取消 OAuth-only 要求，未将它列为缺口。关闭贡献仍可按需运行只读知识服务；这与采集、整理任务材料是不同边界。

真实失败记录仍保留：Kimi 旧调度入口不接受 `--config`，首次验收在发现前发生三次 OS 投递并退出 2；修正选择当前版本后首轮成功。旧 CC 隔离源 `local/unconfigured` 失败却被汇总成成功的问题，已由本轮逐源状态修正，并通过实际失败/恢复路径验收。修复不覆盖原失败证据。

## 经验内容、续写和贡献边界

三端整理提示现要求忠实记录材料中实际发生的过程和现象，未交代的直接省略；不强制提炼教训、编造失败到成功的故事、补未知清单或增加因果结论。`title`、`summary` 用于检索；可选 `conditions` 只记录已有版本或 commit，实验参数与细节放正文。只有配置和状态流水时可以返回零条。

本地实际整理器重放了同一份既有 NPU 任务公开记录：Codex Luna/max、Kimi K3/max 和 CC deepseek-flash/high 均生成一条，保留原数值、dtype-rounded CPU reference 和原范围限制，未把设备设置从 8 改为 0 推断为“8 已运行失败”。CC 对当天真实首次配置材料返回零条。四次调用均无自动重试。这证明这些材料上的整理质量，不是新 NPU 测量或 Stop 到发布的全链路证明。Codex 的实际产物已符合最终省略语义，最终提示措辞调整后未仅为重复结果另跑模型；Kimi 与 CC 使用最终提示。

真实 PR13 的已确认发布状态用于核对清理与续写：GitHub 准确 head 确认后，已发送正文被清理，仅保留轻量回执；无需等待合并才清理。Kimi 原生整理器通过正常上下文自行选中原条目 ID，运行时从回执记录的 GitHub head/path 恢复并校验原文后追加。没有手动指定返回 ID，也未重新发布这份验收副本。已发送内容可清理，不意味着丢弃尚未发送的增量或未知提交结果。

贡献关闭再开启的本地实际设置与撤销路径已验证：新 generation 不接收旧材料；已有未发送续写候选从一条变为零，旧回执和只读检索仍保留。此项证明共享运行时边界，不单独证明三个宿主全部开关事件的交付。上述续写使用既有任务的真实复核材料，不能声称新增了一次独立 NPU 实验。

## 反馈、下库与 Bot

CC 在实际默认审批任务中对已读取的经验给出一次可选 `up` 反馈，后台自动产生 [知识 PR15](https://github.com/mindie-agent/knowledge-vllm-ascend/pull/15)，准确提交 head 为 `057e0ea51a0de75fd081be68771d4fe353344b4c`。Grok Bot 使用已审查的 `40063ebf` 校验器完成维护者发起的补查，并于 09:58:35Z 合入，merge 为 `ab600a16`；GitHub connector 已独立确认。这证明原生反馈自动提 PR 及 Bot 审阅合入，尚非新经验发布。

此前 GitHub MCP 连接可用，但平台仓库事件访问未建立；用户已完成 Cursor App 授权，Bot 收到仓库访问通知，三条 routine 仍只面向知识仓。PR15 的 opened 事件发生在授权前，其补查不能算原生 opened 投递。合入后 Bot 只读回报原生 `pr-merged` routine 已 succeeded，复用已有结论核对合入状态，无额外写入；运行状态与事件类型来自 Bot 的平台回执。下一条新经验 PR 仍需验证真实 opened 事件触发的审阅合入。

真实下库通过专用 GitHub 分支验证，未改生产 main、未造经验、未提交 PR：从 `eb311496` 创建分支，仅删除一条既有 case，实际删除 commit 为 [`858fbffa`](https://github.com/mindie-agent/knowledge-vllm-ascend/commit/858fbffa68173a1abd116506c71be93127687375)。隔离 Feed 同步后，普通检索不再返回该条目；旧 exact ref 仍能读取相同正文，并明确 `withdrawn=true`。另一隔离 Store 仅复用同一公开正文和本地测试票，确认旧草稿/票不再进入待发布选择。没有模型、发布器或投票外发。此项证明真实远端撤下到 Feed/Store 的行为，不是 Bot 自行作出撤下决定的证明。

点赞、点踩仍是宽松的参考指标，既不强制每任务反馈，也不按票数自动删除。经验是否修正或撤下由维护者/Bot 结合内容处理；不另设候选数量、每轮写入数等产品配额。

## 仍在推进

1. 生产 Codex 已升级并验证新版 Hook 触发。旧开发控制器把新合同误记为 incompatible，本次使用已审核安装器显式升级；旧尝试历史、旧入口和用户贡献配置保留，后续由新版定时控制器接管。这是一次真实修复安装，不称为旧控制器自动更新通过。
2. 完成本轮真实 NPU 新增观察的 Stop → 本地整理脱敏 → PR → Bot 审阅合入 → 新任务读取和使用。Kimi 的直接比较已实测完成：FP16/BF16 两路 `torch.equal=true`，输出间最大差为零；但 Stop 没有产生新采集。现已定位三端更新器停止原知识服务后未恢复的共同缺口，修复设计已审查，代码尚未完成。该次真实 Stop claim 早于任务结束，不能归因为验收器提前结束宿主。随后明确恢复当前服务，新一轮实际加载已保存张量也核对成功，但最终模型回复超过 360 秒验收预算，进程按时终止，未到达 Stop；这与前述服务缺口是不同失败。两次结果都不算新经验发布通过。此前失败读请求还发生一次模型自行重试，失败记录保留，不能将整段称为零重试。
3. 仓库访问已补齐，PR15 补查合入和后续原生 merged 事件回读完成；继续验证新经验 opened 事件的自动审阅合入。反馈自动提 PR、此前已有内容消费、当前整理器重放均不能合并推定最新业务闭环完成。
4. 在用户提供的专门 Windows 机器上验收三个适配器。Windows 不作为本轮已完成合入的前置门槛，仍是首版目标范围的未验收项。

旧业务 Skill、profiling 分析、自动 Skill 提炼及进一步领域/Harness 扩展保持暂缓。模型调用按明确边界执行，失败后不自动新开任务或反复重试。未完成项目不会因代码合并或 CI 通过而自动标记通过。

## 证据入口

公开适配器记录见 [Codex P0/P1 验收](https://github.com/mindie-agent/mindie-agent-codex/blob/main/docs/acceptance-p0p1-2026-09-21.md)、[Kimi P0/P1 验收](https://github.com/mindie-agent/mindie-agent-kimi/blob/main/docs/acceptance-p0p1-2026-09-21.md)及 [Claude Code P0/P1 验收](https://github.com/mindie-agent/mindie-agent-cc/blob/main/docs/acceptance-p0p1-2026-09-21.md)。原生任务 ID、模型、准确版本、失败与清理记录按各报告保留，不上传原始 transcript 或隐藏思考。

本轮本地审计目录 `mindie-p0p1-20260921` 中，`reports/cc-daily-acceptance.md`、`kimi-daily-acceptance.md`、`codex-os-timer-acceptance.md`、`knowledge-withdrawal-acceptance.md` 记录对应实机/远端结果；`faithful-records/review.md`、`sync-review/REPORT.md`、`acceptance/core-receipt-boundaries/review.md` 记录内容、同步和回执边界；`acceptance/cc-feedback/automatic-pr.json` 记录 PR15 的准确提交。历史记录只证明当时版本，本轮未复验的路径不扩展结论。

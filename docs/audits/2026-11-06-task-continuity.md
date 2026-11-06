# 任务连续性 P0 契约与独立审查

MindIE 是通用 Agent 的附加能力。用户目标不应被插件的知识准备、可选组件、安装配置、诊断或本地账本变成新的前置条件。失败必须如实呈现，已成功的业务结果必须保留；对独立步骤和已授权的等价宿主工具应保持继续路径。身份、权限、资源归属和未知远端写入不能通过降级绕过。

## Astra max 独立审查

用户明确要求独立 review，本轮使用 `gpt-6-astra`、`reasoning_effort=max`，不继承主代理聊天历史，只提供仓库、待审提交与用户目标。审查代理未修改代码。第一轮确认三项 P1，未确认 P0 级具体缺陷；这里的 P0 指产品连续性的验收优先级。

| 确认问题 | 实际复现 | 修复 |
| --- | --- | --- |
| AGY/WB 把返回型失败当成功 | 真实 `remote_write` 的路径越界返回 `outcome=blocked`，适配器却返回 `isError=false`、回执 `succeeded` | 从 remote-dev 提取共享纯结果分类函数；业务失败、未知提交、原生命令退出和成功后的记账失败使用同一规则 |
| AGY 一次性绑定被拒后继续使用旧会话 | 发布一次 bind，连续两次 `remote_auth status` 均执行，第二次继承前次写入的 `REMOTE_DEV_SESSION_ID` | 有绑定库时必须成功 claim；无绑定库时仅接受验证过的原生 `AGY_CONVERSATION_ID`。不合成默认身份、不从业务环境变量恢复授权 |
| 单次准入错误杀死整个 MCP 连接 | 向真实子进程发送 initialize、失败工具调用、ping；旧版本只返回 initialize 就退出 | 准入失败返回该请求的 `isError=true / execution=not_started`，进程继续响应 ping、目录与其他独立请求 |

新增测试覆盖真实共享组件的本地拒绝路径、未知远端提交捕获、SQLite 回执、A/B 会话切换、bind 重放拒绝，以及实际 stdio 连续请求。没有用伪造硬件负载冒充验收，也没有为了保持连接跳过身份或必要的回执准入。

## 同轮补强

- **已验证认证与本地档案分离**：认证或公钥维护已成功时，档案保存失败以 `receipt_warning` 和 `receipt_unconfirmed` 返回。已有连接准备使用本次已验证的凭据继续；新档案没保存时不返回可解析的 `auth_ref`，只保留真实可用的直接密钥信息。
- **Coordinator 不虚报 ready**：认证完成但档案未保存时返回 `partial / registration=not_started`，保留嵌套认证成功事实，不登记假引用或向监控发布不存在的档案。
- **六端指引保持原任务继续**：知识、可选组件、引导和账本不能阻塞独立工作；可以使用已授权的等价宿主工具。Coordinator 管理的工作继续遵守租约，原生替代路径必须已有可验证的资源预约；无法确认资源归属时仅暂停对应设备动作。
- **故障后替代路径**：Codex 的组件缺失与知识源不可用提示明确引导继续代码检查、文档分析和原生工具，而非要求先修复整套插件。
- **可复现 CI**：AGY/WB 原先未跟踪 `uv.lock`，本机残留锁也与当前 manifest 不一致。本轮将生成锁纳入版本控制，并在 Linux/Windows 从干净 checkout 按锁安装非 editable 共享依赖，再测试当前原生适配器。不能把本机锁成功等同于干净 CI 可用。

## 验证与正式交付

开发审查的共享候选为 `96b7c1d300c299e2adc46fcdf98be17e834750e1`。发布准备完成后，六端插件改为锁定正式 `remote-dev 0.11.6 / 991ef7863b2b208f94f54a29db4ac5be50884ea3`、`Coordinator 0.7.5 / 819b0deb7bea994d4dff9c009200a48dd9300cc4`、`knowledge 0.13.13 / 3c478a19b5542b38520c7f98b87a07f37e305021` 与 `sim 0.9.4 / 6f1d5a871a7b1ef20ff7a8cab33aaf4637fb3f66`。精确版本、标签、全部资产校验和及干净源码基准见 [0.1.10 发布验收](../releases/0.1.10/task-continuity-release-acceptance.json)，组合表见[发布说明](../releases/0.1.10.md)。

修复 PR：[remote-dev #55](https://github.com/mindie-agent/remote-dev/pull/55)、[Coordinator #71](https://github.com/mindie-agent/coordinator/pull/71)、[Codex #93](https://github.com/mindie-agent/mindie-agent-codex/pull/93)、[Claude Code #65](https://github.com/mindie-agent/mindie-agent-cc/pull/65)、[Kimi #65](https://github.com/mindie-agent/mindie-agent-kimi/pull/65)、[DSH #37](https://github.com/mindie-agent/mindie-agent-dsh/pull/37)、[AGY #6](https://github.com/mindie-agent/mindie-agent-agy/pull/6)、[WB #5](https://github.com/mindie-agent/mindie-agent-wb/pull/5) / [WB 发布合同补强 #6](https://github.com/mindie-agent/mindie-agent-wb/pull/6)，以及[产品 #322](https://github.com/mindie-agent/mindie-agent/pull/322)。

本地边界验证：共享认证与结果分类 55 passed；协议、Schema 与观测 67 passed / 30 subtests；Codex 82 passed / 3 skipped / 5 subtests；Coordinator 8 passed。第二轮 Astra max 独立执行 87 项隔离回归，并复现、复核修复 WB knowledge surface 的准入异常遗漏；相同真实 stdio 探针返回完整 `[1,2,3,4]`，失败调用为 `not_started`，后续 ping 和目录正常。当前审查范围无未关闭 P0/P1。

[真实 SSH 验收](https://github.com/mindie-agent/remote-dev/actions/runs/42154502701/job/127685670805)在 PowerShell 两组和 WSL2 各 5 passed，共 15 项，覆盖本地档案写入失败后的新进程密钥连接；准备 0.11.6 后的[最终候选验收](https://github.com/mindie-agent/remote-dev/actions/runs/42157809755)再次全部通过。固定认证结果不冒充真实 SSH、用户业务主机或 NPU 模型实测。

Coordinator 首轮 macOS 有三项与既有主干一致的编译 fixture 资源不足失败；Windows 另暴露 shell 引号及本地路径断言。修复仅明确轻量编译合同的一个 worker 默认值、保留并发测试的三个 worker，并按实际 shell/路径语义断言，未改变生产资源准入。[最终 CI](https://github.com/mindie-agent/coordinator/actions/runs/42158641317)全部通过：Windows 1418 passed / 112 skipped、macOS 1496 passed / 34 skipped，均另有 63 subtests。原始[失败](https://github.com/mindie-agent/coordinator/actions/runs/42156054681)与[旧主干证据](https://github.com/mindie-agent/coordinator/actions/runs/41774201118)保留。

六端最终源码经过各 PR 的跨平台 CI。新隔离运行时中的 Codex 更新与旧入口恢复范围为 72 passed / 1 skipped / 20 subtests；显式核对了旧发布运行器未自动覆盖的 debugger 实际版本与 `direct_url.json`、README 徽章和 release-notes 路径。

WB `0.1.6` 的[发布候选失败](https://github.com/mindie-agent/mindie-agent-wb/actions/runs/42160239492)，没有正式 Release，标签未移动。`0.1.7` 同步 marketplace 与原生版本，将实际安装合同纳入双平台 PR CI。默认测试不再自动扫描其他用户宿主的运行时或凭据，Tier 3 网络验收通过 `--live-host` 显式运行，保留真实错误断言。最终本地和 Astra max 独立全量均为 37 passed / 3 skipped / 1 NPU deselected；使用最终指定解释器的两项显式 Tier 3 均通过（52.46s）。此前旧解释器的 HTTP 502 和旧 `.venv` 的父子版本指纹不一致保留为失败，未计作通过。

发布前现有通道的 flexible R1–R6 已通过；新正式组合的 strict-lockstep R1–R6（含本机宿主与全部正式 Release）也已全部通过。正式 Release 可被现有更新器发现，但候选准备、安装绑定切换和运行中宿主加载工具定义分别核验；本次没有强停用户会话，也不声称当前聊天已经重载新目录。

## 产品汇总发布输入补强

产品 `0.1.9` 的[汇总流水线](https://github.com/mindie-agent/mindie-agent/actions/runs/42162126642)在创建正式 Release 前发现缺少 `benchmark-manifest.json`。原 R1–R6 未覆盖此文件，检查通过不能代表汇总输入完整；失败标签保留，未重指向其他源码。

后续 `0.1.10` 补齐 15 个正式仓库的版本、SHA、固定运行器、必需基准场景与平台清单，用实际固定版本发布收集器验证已有正式报告。R1 增加必需文件及其与 channel 的源码同一性检查，PR CI 的三项语义回归覆盖缺失、正确、过期与重复目标。配套 README 只更新主产品引用，插件运行时及正式 SHA 不变；此产品维护补丁按 flexible R1–R6 复核。

## 旧安装升级连续性复查与 0.1.11

`0.1.10` 正式发布后的旧安装复查又确认一项 P1：AGY/WB `0.1.7` 的新处理器调用共享结果分类 API，但旧 `remote-dev 0.11.5` 不包含该模块。安装器只检查模块存在性，启动器只切换解释器而执行新下载的脚本，因而会让已安装宿主的远端工具在分派前失败。后台更新不能作为当前进程的兼容性屏障；此前干净新装测试没有覆盖这一实际升级边界。

后续 [AGY #8](https://github.com/mindie-agent/mindie-agent-agy/pull/8) 与 [WB #7](https://github.com/mindie-agent/mindie-agent-wb/pull/7) 发布两端 `0.1.8`：

- 启动器从同一份激活配置读取解释器与保留脚本，按已记录的原生版本优先选择 `source_root` 中的原组合，避免原生目录被覆盖后的新旧混用。
- 安装先探测实际组件 API，必要时通过既有共享构建器准备独立运行时，通过后再切换配置；没有复制结果分类器。
- 脚本先复制到独立临时目录，再以版本与内容摘要通过 `os.replace()` 发布，保留旧目录、任务状态和用户字段。
- 同轮 Astra max 发现 WB runtime discovery 仍调用已删除的辅助函数；已删除残留并通过真实旧解释器回归验证。

Astra max 独立复核使用正式旧 setup 实际生成配置，再覆盖原生目录。两端均通过覆盖前后 status/ping、复制中断保持旧配置、摘要目录复用、新组合激活，以及**同一个旧 MCP 进程持续存活并跨越覆盖和配置切换**的调用。确认的两个 P1 已关闭，本轮审查范围无未关闭 P0/P1。

真实旧组件现场安装、构建升级和清理验收：AGY 1 passed / 55.30s，WB 1 passed / 44.92s。常规隔离回归：AGY 32 passed / 1 explicit upgrade skipped；WB 38 passed / 4 skipped / 1 live NPU deselected。专用升级 CI 在 Linux/Windows 均通过：[AGY](https://github.com/mindie-agent/mindie-agent-agy/actions/runs/42169441633)、[WB](https://github.com/mindie-agent/mindie-agent-wb/actions/runs/42169515249)；WB 测试体分别 17.86s / 36.80s。本地中间失败包括 Windows 长路径清理、测试安装误继承候选 uv 配置及一次发布目录读取超时，均保留失败记录；只有上述最终通过计入验收。

`0.1.11` 使用两端新正式标签的精确源码与基准，其余组件沿用原正式身份。两端所有发布资产经过 SHA256 验证，归档中的 launcher、setup、component_update、MCP 处理器及锁文件逐字节匹配审查源码，见[机读验收](../releases/0.1.11/task-continuity-release-acceptance.json)。完整组合再次执行 strict R1–R6；四端无代码变化的插件以正式标签源码验证，README 使用当前组合引用，检查结束恢复原工作分支。没有修改用户宿主绑定、调用业务主机或运行 NPU 工作负载。

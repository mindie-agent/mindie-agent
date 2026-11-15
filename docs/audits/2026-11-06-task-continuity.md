# 任务连续性 P0 契约与独立代码审查

MindIE Agent 是挂载在通用编码 Agent 之上的领域增强底座：用户的研发目标绝不能被插件内部的知识预热、可选组件、首次安装引导、诊断日志或本地账本反客为主地变成前置门禁。当局部辅助能力发生故障时，系统必须如实报告错误、完整保留已成功的业务结果，并让可独立推进的步骤继续经由已获授权的宿主原生工具执行；与此同时，会话身份、权限边界、设备租约归属与结果未知（`unknown`）的远端写入绝不允许借“降级”之名绕过安全校验。

## 独立代码审查（`gpt-6-astra`，`reasoning_effort=max`）

按用户要求，本轮启用完全隔离的独立审查会话（模型 `gpt-6-astra`，`reasoning_effort=max`，不挂载开发会话上下文，仅输入目标仓库、待审提交与连续性契约要求；审查会话保持只读、不直接改码）。首轮审查未发现 P0 级代码缺陷（标题中的 P0 指产品任务连续性的最高验收优先级），确认并闭环了以下 3 项 P1 缺陷：

| 确认缺陷 | 真实复现表现 | 根因修复 |
| --- | --- | --- |
| Antigravity / WorkBuddy 将返回体内的业务失败误判为成功 | 真实 `remote_write` 触发路径越界拦截并返回 `outcome=blocked` 时，插件适配层仍返回 `isError=false` 且本地回执记为 `succeeded` | 在 `remote-dev` 中沉淀统一的纯函数结果分类器；业务拒绝、未知外部提交、原生命令非零退出及主操作成功后的本地记账异常统一复用同一套判定规则 |
| Antigravity 在一次性 `bind` 被拒后误继承上一会话身份 | 签发单次 `bind` 后连续执行两次 `remote_auth status`：第二次虽未重新绑定，却沿用了前一次写入进程环境的 `REMOTE_DEV_SESSION_ID` | 存在绑定库时强制要求当次 `claim` 成功；无绑定库时仅接受经校验的宿主原生 `AGY_CONVERSATION_ID`，严禁合成默认身份或从业务环境变量回捞历史授权 |
| 单次准入异常直接终止整个 stdio MCP 服务进程 | 向真实 MCP 子进程依次发送 `initialize`、一次准入失败的工具调用与 `ping`：旧版进程在返回 `initialize` 后直接退出 | 准入异常改为仅对当前请求返回结构化 `isError=true`（`execution=not_started`），常驻进程保持存活并正常响应后续 `ping`、工具目录查询及其他独立调用 |

针对上述问题新增的回归测试全部基于真实共享组件的本地拒绝路径、未知远端写入捕获、SQLite 回执账本、跨会话切换、`bind` 重放拦截及真实 stdio 多请求序列构建，零伪造硬件负载，且未因维持长连接而放宽会话身份或回执校验。

## 同轮架构补强

- **远端认证主结果与本地档案落盘解耦**：当远端密码校验或公钥安装已确认成功、仅本地档案写入失败时，返回结果保持成功并附加 `receipt_warning` 与 `receipt_unconfirmed=True`；当前连接直接使用本次已验证凭据继续工作，同时对未落盘档案绝不伪造 `auth_ref`，仅暴露真实可用的直接密钥路径。
- **`coordinator` 严禁虚报 `ready`**：当底层认证通过但本地档案未能保存时，`coordinator` 如实返回 `partial`（`registration=not_started`），既保留内层认证成功事实，又避免登记悬空引用或向监控看板广播不存在的主机档案。
- **六端引导统一落实任务连续性**：明确知识检索、可选组件、初始化引导与本地账本故障不得阻塞独立研发动作，Agent 可在用户既有授权范围内切换宿主原生工具继续推进；涉及远端设备的动作继续遵守 `coordinator` 租约仲裁，无法确认设备归属时仅暂停对应上卡步骤而非中断整场任务。
- **缺件提示改为指向可继续路径**：更新 Codex 插件在组件缺失或知识源不可用时的提示文案，引导 Agent 继续开展本地源码阅读、日志分析与原生工具排查，而非停下手头工作要求用户先重装整套插件。
- **锁文件版本化与干净环境 CI**：此前 Antigravity 与 WorkBuddy 未将 `uv.lock` 纳入版本控制，本机残留锁文件亦与当前清单存在漂移。本轮将生成的 `uv.lock` 正式入库，并在 Linux / Windows CI 中从干净检出按锁安装非 editable 共享依赖后再执行插件回归。

## 验证记录与 `0.1.10` 正式交付

开发联调阶段基于共享候选提交 `96b7c1d300c299e2adc46fcdf98be17e834750e1` 验证；待各共享组件正式发版后，六端插件统一锁定至正式版 `remote-dev 0.11.6`（`991ef7863b2b208f94f54a29db4ac5be50884ea3`）、`coordinator 0.7.5`（`819b0deb7bea994d4dff9c009200a48dd9300cc4`）、`knowledge 0.13.13`（`3c478a19b5542b38520c7f98b87a07f37e305021`）与 `sim 0.9.4`（`6f1d5a871a7b1ef20ff7a8cab33aaf4637fb3f66`）。精确版本号、标签、全量资产 SHA256 校验和及干净源码基准见 [`0.1.10` 发布验收回执](../releases/0.1.10/task-continuity-release-acceptance.json)与[`0.1.10` 发布说明](../releases/0.1.10.md)。

关联 PR：[remote-dev #55](https://github.com/mindie-agent/remote-dev/pull/55)、[coordinator #71](https://github.com/mindie-agent/coordinator/pull/71)、[Codex #93](https://github.com/mindie-agent/mindie-agent-codex/pull/93)、[Claude Code #65](https://github.com/mindie-agent/mindie-agent-cc/pull/65)、[Kimi #65](https://github.com/mindie-agent/mindie-agent-kimi/pull/65)、[DSH #37](https://github.com/mindie-agent/mindie-agent-dsh/pull/37)、[Antigravity #6](https://github.com/mindie-agent/mindie-agent-agy/pull/6)、[WorkBuddy #5](https://github.com/mindie-agent/mindie-agent-wb/pull/5)、[WorkBuddy 发布契约补强 #6](https://github.com/mindie-agent/mindie-agent-wb/pull/6) 及[主仓 #322](https://github.com/mindie-agent/mindie-agent/pull/322)。

- **本地与第二轮独立审查验证**：共享认证与结果分类 `55 passed`；协议、Schema 与可观测性 `67 passed / 30 subtests`；Codex `82 passed / 3 skipped / 5 subtests`；`coordinator` `8 passed`。第二轮独立审查（`gpt-6-astra`，`reasoning_effort=max`）独立跑通 `87` 项隔离回归，额外检出并复核修复了 WorkBuddy `knowledge` 入口的一处准入异常漏捕——修复后真实 stdio 连续探针完整返回 `[1, 2, 3, 4]`（失败调用标为 `not_started`，后续 `ping` 与工具目录查询正常），审查范围内 P0/P1 问题清零。
- **跨平台真实 SSH 验收**：[候选分支真实 SSH CI](https://github.com/mindie-agent/remote-dev/actions/runs/42154502701/job/127685670805) 在两组 PowerShell 与 WSL2 上各通过 `5 passed`（合计 `15` 项），覆盖本地档案写入失败场景下的新子进程免密建连；切入 `0.11.6` 正式候选后的[最终验收流水线](https://github.com/mindie-agent/remote-dev/actions/runs/42157809755)再次全绿。
- **`coordinator` 跨平台 CI 收敛**：首轮 macOS 暴露出 3 项与历史主干一致的编译夹具默认并发度超配问题，Windows 另暴露出 shell 引号与本地路径断言差异。修复后仅为轻量编译契约显式指定单 worker 默认值（保留并发抢占测试的 3 worker 配置）并对齐平台路径语义，未改动生产资源准入逻辑。[最终跨平台 CI](https://github.com/mindie-agent/coordinator/actions/runs/42158641317) 全量通过：Windows `1418 passed / 112 skipped / 63 subtests`、macOS `1496 passed / 34 skipped / 63 subtests`（首轮[失败记录](https://github.com/mindie-agent/coordinator/actions/runs/42156054681)与[历史主干对照](https://github.com/mindie-agent/coordinator/actions/runs/41774201118)完整保留备查）。
- **六端插件回归与 WorkBuddy `0.1.7` 补发**：六端最终源码全部通过跨平台 PR CI；全新隔离运行时下的 Codex 自动更新与旧入口恢复回归通过 `72 passed / 1 skipped / 20 subtests`，并逐一核对了 `debugger` 实际安装版本、`direct_url.json`、README 徽章与发布说明链接。WorkBuddy `0.1.6` [首次发布工作流](https://github.com/mindie-agent/mindie-agent-wb/actions/runs/42160239492)在创建正式 Release 前失败（原标签保留未移动）；随后 `0.1.7` 对齐 marketplace 与原生插件版本号、将真实安装契约纳入双平台 PR CI，并确保默认测试严禁扫描宿主机真实用户目录（Tier 3 联网验收仅在显式传入 `--live-host` 时运行）。最终本地与独立审查全量回归均为 `37 passed / 3 skipped / 1 NPU deselected`，显式指定目标解释器的两项 Tier 3 验收均通过（`52.46s`；此前使用旧解释器触发的 HTTP 502 与旧 `.venv` 版本指纹不匹配记录如实保留为历史失败，不计入通过）。
- **发布就绪门禁（`R1–R6`）**：发版前既有通道的灵活模式 `R1–R6` 与新正式组合的严格锁步模式（`--strict-lockstep`，含本机宿主与全部 GitHub Release 远端核验）均全部通过。

## 产品汇总发布输入门禁补强（`0.1.9 → 0.1.10`）

产品仓 `0.1.9` 的[汇总发布流水线](https://github.com/mindie-agent/mindie-agent/actions/runs/42162126642)在创建正式 Release 前因缺少 `benchmark-manifest.json` 终止（原 `R1–R6` 脚本尚未覆盖该清单文件，失败标签保留未重指）。

随后 `0.1.10` 补齐了覆盖全部 15 个正式仓库的版本号、源码 SHA、基准运行器提交、必需评测场景与平台清单，并通过固定版本发布收集器核验了全部既有正式基准报告；同时在 `R1` 门禁中新增 `benchmark-manifest.json` 存在性及与 `channels/0.1.json` 的源码哈希一致性校验，辅以覆盖“缺失 / 合规 / 过期 / 重复条目”四类场景的 PR CI 回归测试。

## 旧安装原位升级连续性复查与 `0.1.11`

`0.1.10` 发布后，针对旧版本已安装环境的原位升级复查进一步定位出 1 项 P1 隐患：Google Antigravity 与 Tencent WorkBuddy `0.1.7` 的新版请求处理器调用了 `remote-dev 0.11.6` 新增的共享结果分类 API，但旧环境已安装的 `remote-dev 0.11.5` 尚不包含该符号；而旧安装器仅按顶层包名判断存在性，且启动器在原生插件目录被直接覆盖后会将新版脚本与旧版组件虚拟环境混搭拉起，导致远端工具调用在分发前报错（干净环境新装测试未能覆盖这一跨代覆盖边界）。

随后通过 [AGY #8](https://github.com/mindie-agent/mindie-agent-agy/pull/8) 与 [WB #7](https://github.com/mindie-agent/mindie-agent-wb/pull/7) 同步发布两端 `0.1.8` 及产品补丁 `0.1.11`：

- **解释器与保留脚本同代绑定**：启动器从同一份激活配置中成对读取解释器路径与按版本/内容哈希隔离的保留脚本目录（优先读取 `source_root` 中与已记录原生版本匹配的脚本快照），彻底消除原生目录覆盖造成的新旧代码混跑。
- **组件符号级探测与原子切换**：安装/升级时直接探测所需的共享组件符号，缺失时调用共享运行时构建器准备新版独立环境（不跨仓复制粘贴分类器代码），构建校验通过后再切换激活配置。
- **`os.replace()` 原子发布保留目录**：脚本先完整复制至独立临时目录，再按版本与内容摘要通过 `os.replace()` 原子落盘，完整保留上一代目录、任务状态与用户配置字段。
- **清理残留辅助调用**：同轮独立审查一并检出并移除了 WorkBuddy 运行时发现模块中一处指向已废弃辅助函数的残留调用，并通过真实旧版解释器回归验证。

独立代码审查（`gpt-6-astra`，`reasoning_effort=max`）使用旧版正式 `setup.py` 初始化真实配置后再原位覆盖原生插件目录，完整验证了覆盖前后的 `status`/`ping`、复制中断保留旧配置、相同摘要目录复用、新代激活，以及**同一旧代常驻 MCP 进程横跨目录覆盖与配置切换全程保持正常响应**。两端确认的 P1 问题全部闭环：

- 真实旧环境现场升级与清理验收：Antigravity `1 passed`（`55.30s`），WorkBuddy `1 passed`（`44.92s`）；常规隔离回归：Antigravity `32 passed / 1 skipped`，WorkBuddy `38 passed / 4 skipped / 1 NPU deselected`；Linux / Windows 跨平台升级专用 CI 全绿（[AGY run 42169441633](https://github.com/mindie-agent/mindie-agent-agy/actions/runs/42169441633)、[WB run 42169515249](https://github.com/mindie-agent/mindie-agent-wb/actions/runs/42169515249)）。本地调试过程中曾出现的 Windows 长路径清理异常、测试安装误继承候选 `uv` 配置及单次发布目录读取超时均如实留档为中间失败，仅将最终干净通过计入验收。
- `0.1.11` 正式发行包经全量 SHA256 校验，归档内的 `launcher`、`setup`、`component_update`、MCP 处理器及锁文件与受审源码逐字节一致（详见[机读验收回执](../releases/0.1.11/task-continuity-release-acceptance.json)），整包再次通过 `--strict-lockstep` 模式下的 `R1–R6` 全量核验。

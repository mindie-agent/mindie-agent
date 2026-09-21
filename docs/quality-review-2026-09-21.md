# 跨仓代码质量、扩展与故障恢复审查

2026-09-21。审查涵盖架构、知识核心、Codex/Kimi/Claude Code 三个适配器、remote-dev、coordinator、diagnostics、npu-top 和内容仓。Windows 实机、旧业务 Skills 与 profiling 不在本轮执行范围。

主任务与专门审查代理检查运行时和失败路径；另通过真实本地 Kimi K3/max 做了一轮独立只读审查。Kimi 单次运行 820.03 秒正常结束，零自动重启，公开工具访问覆盖十仓主要入口。完整原始结论见 [Kimi 独立审查](reviews/kimi-quality-review-2026-09-21.md)。该报告针对审查 baseline，修复状态以本文为准；其中直接返回全域 outbox/raw detail 的建议未采纳，改用有界的任务归属投影。它明确列出了未逐行覆盖的模块，不能把这次审查描述为逐行全覆盖或安全认证。静态结论、实际本机故障复现、原生模型任务和完整发布链分别记录。

## 架构判断

共享知识核心、原生宿主适配、Git 知识分发和独立远端工具的边界能够支撑当前三个宿主及后续领域扩展。原生身份、Hook、transcript parser、模型调用和安装回读留在各自适配器；核心接收显式的解析器、授权库和领域配置。新增领域不应要求改动核心调度，新增宿主也不应把宿主身份规则放回核心。

维护成本的主要问题是适配层复制后发生契约漂移：相同的后台失败，在不同宿主上得到不同的退出码和状态信息。当前不增加统一 Harness、全局路由器、新消息队列或大型适配框架。稳定且可共用的诊断读取放在核心；原生入口保持薄投影，未安装时仍可用标准库给出首次配置选项。整理器退出码、状态含义、取消和进程所有权应作为跨仓契约维护。

coordinator、npu-top 和 diagnostics 的独立 issue 上报 worker 是可选组件，当前三个插件没有自动接入它们全部能力。独立远端操作不依赖 coordinator、知识授权或社区贡献。diagnostics 的 Grok CLI worker 也不是知识仓使用的桌面 Grok Bot，不能把经验贡献选择当作另一种自动上报授权。

## 确认的问题与处理

| 问题 | 证据与影响 | 处理 |
| --- | --- | --- |
| 远端 job 状态返回内部 authorization | 实际 SSH 连接失败后的 job-status 返回了内部授权对象；Codex 单独过滤，Kimi/CC 与共享 CLI 没有过滤 | [remote-dev PR19](https://github.com/mindie-agent/remote-dev/pull/19) 已合入，共享公有投影去掉授权，保留私有磁盘控制记录 |
| 纯文本远端错误缺少原作业与失败阶段 | 实际 start/status/tail/stop 的文本只有通用失败，已有 job ID、not_sent、连接原因和阶段留在结构化字段 | 同一 PR 将现有安全信息投影为有界文本，保留正常命令输出和游标语义 |
| Codex 把配置坏损或更新锁占用说成首次使用 | 真实 malformed JSON 与外部持锁均返回 configured=false 和安装选择 | [Codex PR7](https://github.com/mindie-agent/mindie-agent-codex/pull/7) 已合入；缺失、invalid_config、update_busy、helper_failed 分开，状态读取不重装或启动服务 |
| Kimi/CC 隐藏后台失败与暂停状态 | 实际子进程退出 124 留下 failed capture，入口只显示贡献启用；三次失败后暂停的 lease 被显示为未激活 | 共享核心 [PR49](https://github.com/mindie-agent/knowledge/pull/49)、Codex PR7、[Kimi PR5](https://github.com/mindie-agent/mindie-agent-kimi/pull/5) 已合入；[CC PR5](https://github.com/mindie-agent/mindie-agent-cc/pull/5) 已合入。单任务 lease inspect 不改变授权或重置尝试 |
| 有恢复入口但找不到失败 batch ID | Kimi 独立审查定位三端状态仅返回设置，recover 又要求 batch ID | 共享核心 PR49、Codex PR7、Kimi PR5、CC PR5 已合入；根据现有私有归属关系返回本任务批次摘要，不暴露其他任务或原始正文 |
| 服务启动错误被丢弃 | 实际缺失 parser 后仅报启动退出，随后状态只有 not-running | [knowledge PR49](https://github.com/mindie-agent/knowledge/pull/49) 已合入；保留当前配置对应的安全阶段和错误类别，ready 发布失败也会清理实际子进程 |
| Kimi/CC 前端取消和 ping 堵在长调用后面 | 实际 stdio 前端加受控两秒子进程：cancel 被忽略，ping 直到工作结束才回复 | Kimi PR5、CC PR5 已合入；有界工作线程和独立控制读取，取消仅影响匹配的本地工作，不宣称远端作业已停止 |
| CC/Codex 整理器错误分类落为 unknown | Kimi 静态审查确认，两端仍统一退出 2/1，而核心已支持分类退出码 | [Codex PR6](https://github.com/mindie-agent/mindie-agent-codex/pull/6) 已合入，[CC PR5](https://github.com/mindie-agent/mindie-agent-cc/pull/5) 已合入；向既有安全退出码契约对齐，不解析 provider stderr |
| 远端异常经过适配层后丢失确定性类别 | 实际 EndpointError、caller/not_sent 及受控 uncertain 异常只剩通用文本 | Codex PR7、Kimi PR5、CC PR5 保留固定枚举 category/submission_state/retryable 和原 job 引用，未知任意分类不外泄 |
| npu-top 把 allow_remote=0 当成开启 | 实际本机进程接受了明确的 0；未向外部地址发送 HTTP | [npu-top PR11](https://github.com/mindie-agent/npu-top/pull/11) 已合入，只接受文档约定的显式 1；unset/0/1 本机进程验证通过 |
| 存活日志 writer 被当作过期文件删除 | 真实存活进程在日志被 unlink 后继续写入且未报错，后续内容无法按路径发现；已有 cursor 到 EOF 也不等于 writer 完成 | [diagnostics PR7](https://github.com/mindie-agent/diagnostics/pull/7) 已合入；只删除已证实退出的 writer 文件，活跃/未知/权限不足保留 |
| 本地日志跨短进程总量无默认清理入口 | 目前每进程文件可轮转，总量 prune 只由可选上报 worker 调用 | 尚未关闭：需要连接现有的本地维护机会，且不能因未开启上报就无限积累或清除活跃日志 |

状态快照是有界、无模型的现有状态读取；原生 MCP 调用仍按既有协议记录一次性身份绑定回执，不应把快照只读表述为整个协议零写入。SQLite mode=ro 可能创建正常的 WAL reader sidecar，主数据和业务状态保持不变：不得为了 status 初始化数据库、导入 transcript、启动服务或整理器、重放失败材料。任务视图只包含该任务的记录；全局暂停等共享状态明确标为共享。后台发布是否成功不能由 sharing.enabled 推断。

错误需让 Agent 判断下一步：配置缺失进入首次配置；更新占用等待该次操作结束；配置或组件损坏检查明确的配置/阶段；暂停先修原因再显式恢复；提交结果不确定先检查原 job/batch，不能重复写入。知识不可用时，原生工具和独立远端工作仍可继续。

额外集成检查复现了 CC 新安装依赖清单与 setup.py 的硬编码 SHA 不一致；旧测试对任何 setup 失败都会 skip。现已改为依赖清单单一来源，保留官方源/精确 commit 校验，安装失败真正失败。真实正式版本安装成功，旧版本在配置写入前被拒绝，最终 64 项检查无 skip，并新增缺失的 macOS/Linux CI 工作流，安装不再靠跳过掩盖失败。另在全新虚拟环境中确认 coordinator 的 remote-dev PyPI 下限无法解析，旧 Git 预安装还与新 diagnostics 来源冲突；[coordinator PR39](https://github.com/mindie-agent/coordinator/pull/39) 将受审 Git 依赖统一声明于 pyproject，并删除 CI 的重复预安装。新的干净 pip 安装、来源 SHA、CLI 与 pip check 已实际验证，并合入 main `c2b702ef`。合入时 Linux、macOS 与 wheel 检查均通过，Windows CI 仍在运行；后续实际回读该 Windows CI 也已通过。按用户安排，Windows 不作为本轮合入的前置条件，CI 通过也不代表用户专门 Windows 机器上的完整验收。

## 实际验收边界

remote-dev 的本机故障验收使用真实 CLI 和 SSH 子进程连接不监听的 loopback 端口。四条错误路径各执行一次，约 1.1 秒完成；输出中保留原 job、not_sent、连接原因及 rpc.control，授权字段和 token 不外露，私有磁盘记录不变。22 项针对性组件检查通过。此处没有成功远端作业，也不能据此声称远端取消或 Windows 通过。

随后从正式 main `2d603c0d` 安装到独立运行时，在既有专用远端容器执行了两个独立作业：正常退出并返回标记；输出超过 6 KiB 后退出 3。正常作业首次返回 running，之后的原 job-status 已报告 succeeded/exit=0；验收脚本误把首次观察当终态的断言失败保留，未重跑该作业。第二个独立作业通过原 job 状态和输出读取确认 failed/exit=3/quiet，6 KiB 输出完整保留，游标未因错误格式化而吞掉内容。两条公有状态均不含内部授权，私有控制记录不变。专用容器恢复原停止状态；零 NPU 算子、零模型调用，不冒充原生 MCP 取消验收。

共享核心另外完成真实 SQLite 排他锁、实际子进程 exit 124、当前/其他任务隔离、暂停计数不变、缺 parser、实际 daemon、FIFO 与连接文件发布失败等检查；发布失败清理的 child/grandchild 均已退出。三端适配器状态在正式核心依赖下分别读取当前任务信息，缺少原生身份不返回任务记录。

Kimi/CC 两端各七项真实本机 stdio/进程检查确认取消、ping、EOF、背压、更新锁等待和控制请求可用，取消到完成约 0.04 秒，拥有的子孙进程均清理；这包含受控身份/helper，不是宿主 UI 发出取消或远端作业停止的证明。共享远端异常实际经三端包装后保留静态类别/确定性，私有 sentinel 不泄露。Kimi 已启用或暂停的任务可直接查询当前任务状态，无需新用户 slash；未启用的任务仍需明确的原生 status 命令。

Codex 状态候选另经真实 Luna/max 任务验证：30.829 秒完成，只执行一次状态命令，识别 config_read/JSONDecodeError，说明服务状态尚不可判断，给出 JSON 检查命令及原生 shell/SSH 绕过。未重试、安装、激活或修改配置。这证明 Agent 能使用本次 CLI 诊断输出，不是 Hook 或 MCP 原生事件交付的证明。

新的 Kimi 原生验收使用正式版本 ff733aea/core 59b6ec4、K3/max、全新 task 和项目、默认原生审批。安装、显式初始化、项目贡献配置及正常知识 query/explain 已实际执行。测试控制器在长 PTY 写入时阻塞；确认业务输入尚未提交后，修复非阻塞写入，在同一任务恢复首次业务输入，未重做配置、重放 capture 或新开任务。原控制器与恢复过程合计 599.804 秒，按既定预算结束。

该任务在截止前只完成检索，写入申请仍未被原生消费，因此实际 NPU 命令、业务 Stop、经验与 PR 均为零。配置流水的 Stop 返回零条经验，不能冒充业务闭环。没有再等待不存在的 PR 或手动触发 Bot。完整 Kimi Stop 到自动发布、以及下一次真实贡献的无人提醒 Bot 审阅仍缺证据。先前 CC 的真实发布、Bot 经澄清恢复合入、同步与新任务使用证据仍按原范围有效，不扩展为本次 Kimi 通过。

本轮不靠再次运行失败材料、更改游标、重置配额、制造测试经验或放宽守护条件补齐成功标签。已证明的失败应先修复；普通业务的实际结果和模型耗时也应如实记录。

## 正式安装与发布回读

[remote-dev PR20](https://github.com/mindie-agent/remote-dev/pull/20) 与 [npu-top PR12](https://github.com/mindie-agent/npu-top/pull/12) 已把正式 diagnostics 修复接入各自依赖；coordinator 的受审依赖也与其保持一致。

本轮共享核心 main 为 `3d9be027`，remote-dev 为 `2c7f3e4a`，diagnostics 为 `c62c1a65`。Codex [PR7](https://github.com/mindie-agent/mindie-agent-codex/pull/7) 的 main 为 `a9858562`，Kimi [PR5](https://github.com/mindie-agent/mindie-agent-kimi/pull/5) 为 `a2c93fd3`，CC [PR5](https://github.com/mindie-agent/mindie-agent-cc/pull/5) 为 `a9ae74a4`。三个适配器均固定上述正式依赖，不从候选源码覆盖运行时。

生产 Codex 原有 300 秒 OS 定时器先后自动安装 `755dbc04` 和 `a9858562`，主任务未手动运行 check/install 或重置历史尝试。原生实际回读当前版本 `0.1.0+codex.20260921154145265940`；当前配置选择的运行时依赖 SHA 全部一致，真实 status 在 0.149 秒内返回，未变动配置，无原生身份时任务记录为空。变更了 bridge 文件后，Stop Hook 原生状态最初为 `modified`。用户在宿主审阅后，实际 hooks/list 回读已为 `trusted`、enabled，仍指向 `a9858562` generation、超时 2 秒；未绕过宿主检查。此次回读未产生模型任务或 Hook 事件，因此不将信任状态当作新的事件交付证据。

Kimi 正式 `a2c93fd3` 在既有隔离原生 home 安装为 `0.1.0+mindie.a2c93fd3ac33`，enabled/ok、两个 MCP、两个 Hook、七个命令实际回读一致。安装事务 5.558 秒，包含回读及实际 manifest 两个 MCP initialize/tools/list 共 7.245 秒，分别返回 4/18 个工具。正式依赖 metadata 一致；历史任务状态、原生 wire、贡献关闭及全局配置保持，临时配置恢复，无测试进程残留。此项没有模型、伪造身份或业务 capture，不能代替完整 Stop→PR。

CC 正式 `a9ae74a4` 在既有隔离原生 profile 安装为 `0.1.0+mindie.a9ae74a41236`。实际 plugin/marketplace/MCP 回读确认 enabled、无 errors，原生缓存中的 manifest 与正式包一致；安装事务 10.034 秒，含回读及两个已安装 MCP 的 initialize/tools/list 共 10.739 秒，分别返回 4/18 个工具。正式依赖 SHA 与另外两端一致，历史数据库逻辑内容、原生 transcript、贡献关闭和全局配置保持。两端各执行一次安装事务，零重试、零模型调用、零业务 capture；进程已清理。

## 后续验收要求

修复首先重复原故障的实际本机进程/锁/SQLite 场景，验证可诊断且无额外动作，再在必要的原生入口上验证 Agent 能发现并使用这些信息。组件检查只保护代码契约。任何 PR 合入、CI 成功或服务 ready 都不会自动关闭完整原生验收项。

自动总量日志维护仍未接入：除确认 writer 退出外，还须从现有配置找到该 root 对应的所有 reporter cursors，未知绑定保留；不通过新建常驻服务或忽略未消费日志解决。下一次独立真实业务继续补 Kimi 完整贡献和 Bot 无提醒审阅；不重放已消费输入或制造经验。

Windows 仍按用户安排由专门机器验证。profiling、旧 Skill 迁移、自动 Skill 提炼和新增宿主保持暂缓。

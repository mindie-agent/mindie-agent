# Codex 及上下游系统审查

状态：2026-10-05 系统审查、隔离实现与九原则复核；最终发布受 workflow 权限阻塞，线上验收未完成。原则基线为主仓 `d3627ed962c3ccba3c26020fa4dbf0032f963903` 的 `docs/design-principles.md`（Git blob `62cdd5ae40553df2f0f7f7d022141123792d2944`）。执行时也读取主工作区未提交的原则 blob `9b21e6ae87ac96ff8bdacc3f4f546384e111a184`；九条原则、失败约束和提交义务相同，只有导航链接不同。本报告记录具体缺口、修正及证据，不新增产品流程或第二份架构权威。

## 覆盖边界

普通入口从 Codex native Skill/Stop/MCP、稳定 launcher 和 updater 进入；knowledge 负责准入到同步消费；remote-dev 的 MCP、CLI 和直接 SDK 均需遵守执行结果合同；diagnostics 的本地记录与独立上报分别核对。公开内容以完整任务包/validator/Bot 声明为合同。coordinator 的设备/进程归属和 npu-top 的观测/历史/UI 是按需可用的组件，不自动并入每个 Codex 任务。

仓库入口覆盖 architecture、Codex、knowledge、remote-dev、diagnostics、knowledge-vllm-ascend、coordinator、npu-top 和组织 profile。Kimi/Claude Code 已核对其独立 main 及较旧 pins；本轮不将它们的历史状态写为当前 Codex 组合已移植。

## 已复现的系统问题与修正范围

| 边界 | 复查发现 | 修正要求 |
| --- | --- | --- |
| 主数据与初始化 | 只删 runtime SQLite 后重新打开，两个有效 Markdown 文件被空 snapshot 删除；尝试账本缺表也可被重建为空 | 权威状态先验证；唯一首次创建；缺损保留正文/unknown/receipt，派生缓存另行处理 |
| 首轮采集 | runtime 建库时刻晚于合法 task/授权，覆盖既有采集下界 | 内部初始化不建立新授权边界，保留当次第一轮 |
| 撤销与提交 | publisher 保存的 admitted 配置绕过后来禁用的 profile choice | 每次写重读现有 choice/scope；已完成 push 与后续未做的 PR 分开 |
| Agent 故障交付 | parser/worker/outbox 部分故障只有数据库或内存状态；配置坏可被当停用 | 必要失败进入有界通道，验证真实自然调用收到；中性 Hook 不表示业务成功 |
| 本地执行 | cleanup 异常覆盖实际退出/输出；父进程被杀后 helper 仍持有 generation | 显式执行结果加清理事实；本地进程树所有权与独立后台服务分清 |
| 远端结果 | 已完成命令后保存失败变成 start_failed；worker 的 uncertain/lost_outcome 未统一处理 | 保留 ACK/exit/job 身份；未知不报成功、不无限等待、不诱导重放 |
| 远端工具覆盖 | RPC、artifact 和直接 SDK 使用不同进程/错误路径；remote 业务错误可触发全任务熔断 | 所有实际入口沿用 OwnedProcess 和一致错误语义；不因几次参数/业务错误禁用整任务 |
| 版本交接 | 重分派失败仍运行旧副本；稳定 launcher 发布失败仍称 installed；迟到 wake 可起旧服务 | 必要包步骤必须完成；精确 configuration retirement 阻止旧代准入；保留部分完成事实 |
| 诊断授权 | 坏 policy 当缺失/撤销，压缩掉 pending；POST 后错误可抹掉 uncertain | 缺失、有效、不可读分开；不可读阻止发送但保留证据；发送阶段先持久化 |
| 协调与等待 | coordinator 仍有默认执行、准备和排队期限；缺损主库可失去 attachment/租约 | None 默认贯穿各层；保留健康租约；严格主库及已知结果/记录失败边界 |
| 观测与界面 | 坏 inventory 变空清单；详情失败沿用旧值；HTTP 失败被 UI 当空图或成功；不完整 wheel 构建成功 | 完整配置验证、部分观测显式状态、界面显示实际失败、完整 package 构建 |
| Windows 状态标记 | 文本写入的 CRLF 与固定 LF 字节校验冲突，刚创建的 Admission 也被拒绝 | 写入 canonical bytes；仍严格拒绝坏 marker、丢失约束和身份替换，适配器内置副本同步 |
| 配置与绑定 | 通过旧错误文案判断无绑定，导致配置成功误报 degraded；部分故障 JSON 仍退出 0 | 复用 core 的结构化 active_lease；无绑定不建库，损坏仍失败；保留 configuration_status 并返回失败退出码 |
| 准备末次观测 | 第一条观测即 quiet 时，解析出的 stage timings 没有再次保存 | 已知完成先保存、新计时再保存、最后输出回调；保存/输出失败保留真实退出结果，不重放准备 |

这些修正沿实际入口实施：不是新增一个可绕过正常流程的测试 API。权威数据库核验实际文件身份、schema 和约束；body、模型尝试和外部写回执不会因打开失败而清空。POSIX 所属进程组的 guardian 使用调用者管道生命期，在调用者被杀后清理遗留后代；显式独立后台服务保持自身归属。SQLite 锁、观察等待、网络健康检查与取消清理仍有各自边界，不能拿它们结束健康业务或重放未知写入。

## 验证记录

| 组件 | 审查候选与交付位置 | 证据与限制 |
| --- | --- | --- |
| knowledge | `ff4bc4aa82e651a4205ba805be2310042946af76`，[PR 61](https://github.com/mindie-agent/knowledge/pull/61) | 主体全套 840 passed / 9 Windows-only skipped；最终 marker/authority/Admission/发布/DFX 115 passed。最终安装使用下面精确组合，不能将旧依赖源码测试冒充它 |
| remote-dev | `5dae65cb2501caabba5c42b47268abfcd403cff8`，[PR 26](https://github.com/mindie-agent/remote-dev/pull/26) | 当前五项 CI 成功，包含 Linux 进程归属；真实 OpenSSH loopback 新增 workflow 尚未发布、三个 opt-in 用例未执行 |
| diagnostics | `7eed6cdb9935f2922b5b280e9d78ad8eb823f5ce`，[PR 13](https://github.com/mindie-agent/diagnostics/pull/13) | 当前 CI 成功；本地 275 passed / 3 skipped；未知 POST 不自动重发，坏授权不清空 pending |
| npu-top | `0f052e6e211dd92b549aa7c468ebb5ad506bff3a`，[PR 15](https://github.com/mindie-agent/npu-top/pull/15) | 当前六项 CI 成功；Windows 两版 Python 各 141 passed / 5 build-only skips / 25 subtests。完整 wheel 正常依赖安装后，实际 HTTP health/overview、静态资源哈希与 schema 2 已验；没有真实 NPU/SSH bootstrap 验收 |
| coordinator | `492555c5b08a8938f89b5f40ed1bc3f8759204d3`，[PR 40](https://github.com/mindie-agent/coordinator/pull/40) | 默认执行/排队期限、authority、远端结果保留已修；完整源码 1327 passed / 28 skipped / 52 subtests，正常安装后的相关 134 passed / 2 skipped / 20 subtests。实际 CI 发现首条 quiet 观测的计时未保存，已修正并经真实子进程回归和相关 57 passed / 5 Linux-only skips 验证；最终 CI 另列，计数不可相加 |
| Codex | 本地 `4924c43b144980b0ea46f19246dbb83fb78de519`，[PR 19](https://github.com/mindie-agent/mindie-agent-codex/pull/19) 暂仍为较早提交 | 完整最终套件 376 tests / 12 平台 skips，其余通过，90.484 秒；新 updater、进程结果和投递实现连同最终 pins 留本地，等待内容候选可发布；现有 PR 旧 CI 不替代本地新 head 验收 |
| 公开内容 | 本地 `c41b29d99de81a05a5323769e86672b57449e5f4`，[PR 38](https://github.com/mindie-agent/knowledge-vllm-ascend/pull/38) 暂仍为较早提交 | installed core 验证 21 entries / 1 feedback / 249215 bytes，四项变更均属 development；neutral 开发检查不授予自动内容合并 |
| 组织入口 | `f48f015217d4075b67ccab410c54f191933dd31f`，[PR 9](https://github.com/mindie-agent/.github/pull/9) | 当前入口指向架构/主线内容，完整正文与可选复用、Codex 与旧版 Kimi/Claude Code 边界一致；仅文档，不声称运行验收 |

上述测试计数覆盖不同提交和重叠测试，不合计为独立用例总数。每个 PR 的九原则记录绑定实际审查提交；新增 CI 发现的缺陷必须修正后再更新记录。

### 精确安装组合

全新隔离 venv 通过正常 Git 依赖安装，未用 `--no-deps`、editable 或 `PYTHONPATH` 冒充已安装版本。`direct_url.json` 核对 knowledge `ff4bc4a`、remote-dev `5dae65c`、diagnostics `7eed6cd`。Codex 声明绑定内容完整候选 `c41b29d`，合同 SHA256 为 `f2dd4f82ea2ce9a883d696a6039cde0ad3ebf21bbe5544c477e810c56ea439ff`。

由于内容候选尚未发布，直接远端 preflight 在 `publication_fetch` 正确失败，没有执行 native 安装。本地组合验证显式将**验收进程内**这一个内容 Git URL 映射到精确提交的只读裸镜像，保留相同声明、完整块、哈希与 validator 检查；其他 runtime 仍从公开 Git SHA 正常安装。这个镜像是隔离验证夹具，不是产品 fallback，也没有修改全局 Git 配置、凭据或用户安装。远端可获取性必须在授权发布后另验。

最终 Codex `4924c43` 在 Codex CLI 0.153.4 的临时原生 profile 中实际安装并启用。候选与原生 cache 每个文件字节一致，发现 3 个 knowledge 和 11 个 remote MCP 工具。包 SHA256 为 `6e16e185fa2094e362306505d251b16e1267537ee3ce167b55d4e000e2de9a27`。这是实际安装与入口验证，不代表宿主已经为真实用户任务派发 Hook。

通过已安装 Hook 命令输入合成 Stop 缺身份事件，得到中性 shell 输出及真实 `invalid_envelope` 投递。另一项在真实 Core 服务启动后损坏隔离 community JSON，由实际 outbox worker 产生 `knowledge.publish / authorization / authority_unavailable`；下一次已安装 MCP 能力调用收到该故障并 ACK，再次调用没有重复投递。没有直接塞入诊断来冒充后台错误。测试结束时 captures、summary attempts、publication outbox 均为 0，没有创建 Admission；所拥有服务正常退出，临时 profile 已移除。

Coordinator 最终 `492555c` 也由公开 Git SHA 正常安装，source tree 外导入路径及 remote-dev/diagnostics `direct_url.json` 已回读。安装包的真实 subprocess 末次观测与记录/输出故障相关五项测试通过；不是用源码覆盖已安装版本。

### 资源与外部验收

1024 块、16,384,000 正文 bytes 的实际 select/freeze/reload/validate/scan/apply，Python retained 2,901,898 bytes、peak 15,053,494 bytes。该测量不是进程 RSS 上限、模型质量证明或允许截断正文的阈值。长任务正文保持完整；导航摘要仍是可错的定位材料。

GitHub 拒绝当前 Git 凭据写 workflow 后，真实 SSH CI 与内容 validation 时限修正保留本地；没有通过替换凭据、API 或其他触发路径绕过。内容依赖与 Codex 最终更新据此暂不提交。真实 SSH/NPU、原生宿主 Hook 信任及首轮/fork 派发、在线模型质量/费用、公开上传与外部 Bot 采纳仍各自未验收，不能以本地安装或现有 CI 代替。

此前消费者评估保留原结论：12 次正常任务没有调用参考入口，不能证明复用收益；两个强制读取是额外探索。此前公开合成 Stop→PR→Bot→独立消费属于旧版本，仍有价值但不能认证本轮。

## 九原则复核

1. **总成本。** 修正有复现依据的正文丢失、健康工作被期限中止、部分成功重做和版本误选；轻量任务不因此启动全套服务或模型。资源检查集中在变化部分，不重复无区分度的消费试验。
2. **封闭问题。** 工具化仅覆盖身份、schema、进程所有权、不可变包和外部回执等机械边界；领域研究、经验正确性与是否复用仍交给 Agent。
3. **理解负担。** 正常入口不增加 activate/status/recover/closeout 步骤；内部错误给出阶段、已知效果和未知部分。文档将当前状态与历史验收分开，减少跨版本误读。
4. **单一边界。** 原生解析/安装归 adapter，准入和材料归 core，进程归 remote-dev，各组件拥有自身权威库。标记只阻止误初始化；不建立第二份业务事实或新工作区管理层。
5. **Skill 信息性。** Skill 保持能力入口与可选方法，不强制研究路线、贡献格式或收尾。仓库仍不恢复旧 Skill catalogue、hook bootstrap 或 MCP 兼容入口。
6. **知识参考性。** 完整正文保留失败与纠正，索引/反馈/Bot 合并不构成认证；没有必查必写，也没有用零查询任务宣称收益。
7. **按需介入。** 沿用既有 choice、scope 和可信任务身份；不跨 session 扫描或新增日常授权、模型调用、重试和强制查询。可选协调/观测组件不并入每个普通任务。
8. **成果复用。** 保留合法 SQLite、模型返回、unknown 尝试、已知成功和原有缓存；只在明确兼容边界内复用。Kimi/Claude Code 旧证据保留且不充当新组合证据。
9. **错误可见。** 真实业务结果先于记录/清理失败保存；损坏不当首次使用/停用/空集，未知外部效果不重放。中性 Hook shell 回执与 Agent 故障送达分别验证。权限拒绝和未完成验收在本报告明示。

以上是具体 diff 与行为的审查结论，不是对全部未来输入的保证。所有实际未验证项保留原边界；后续发布或实现改动仍需复查受影响原则。

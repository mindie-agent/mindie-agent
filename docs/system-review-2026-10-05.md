# Codex 及上下游系统审查

状态：2026-10-05 系统审查、隔离实现与九原则复核；全部审查候选已发布到 draft PR，最终跨平台 CI 已完成，线上验收未完成。原则基线为主仓 `d3627ed962c3ccba3c26020fa4dbf0032f963903` 的 `docs/design-principles.md`（Git blob `62cdd5ae40553df2f0f7f7d022141123792d2944`）。执行时也读取主工作区未提交的原则 blob `9b21e6ae87ac96ff8bdacc3f4f546384e111a184`；九条原则、失败约束和提交义务相同，只有导航链接不同。本报告记录具体缺口、修正及证据，不新增产品流程或第二份架构权威。

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
| 缺失与损坏路径 | Windows 将普通文件子路径报告为 FileNotFoundError，DFX 和 status 也可能把坏父目录视为未配置/无故障 | 只在可访问目录下确认真实缺失；文件祖先、不可访问根目录和悬空链接明确报错；Core/DFX 保留有效目录链接支持，diagnostics 沿用禁止软链策略；真缺失读取不创建状态 |
| 配置与绑定 | 通过旧错误文案判断无绑定，导致配置成功误报 degraded；部分故障 JSON 仍退出 0 | 复用 core 的结构化 active_lease；无绑定不建库，损坏仍失败；保留 configuration_status 并返回失败退出码 |
| 准备末次观测 | 第一条观测即 quiet 时，解析出的 stage timings 没有再次保存 | 已知完成先保存、新计时再保存、最后输出回调；保存/输出失败保留真实退出结果，不重放准备 |

这些修正沿实际入口实施：不是新增一个可绕过正常流程的测试 API。权威数据库核验实际文件身份、schema 和约束；body、模型尝试和外部写回执不会因打开失败而清空。POSIX 所属进程组的 guardian 使用调用者管道生命期，在调用者被杀后清理遗留后代；显式独立后台服务保持自身归属。SQLite 锁、观察等待、网络健康检查与取消清理仍有各自边界，不能拿它们结束健康业务或重放未知写入。

## 验证记录

| 组件 | 审查候选与交付位置 | 证据与限制 |
| --- | --- | --- |
| knowledge | `b6aad81eb07248a39325d358401eb10628ba0cde`，[PR 61](https://github.com/mindie-agent/knowledge/pull/61) | 当前 package/Linux/macOS CI 各 868 passed / 9 skipped；Windows 847 passed / 30 POSIX skips，877项均有XML记录、0 failures/errors（36分39秒）。上次30分钟预算取消的部分结果作为历史记录保留；最终 Git 安装组合从 source tree 外运行相关回归 124 passed / 0 skipped，52 个运行时模块来自 site-packages |
| remote-dev | `d7b3f4f711350a648e80dee2ce9367d9fae4391e`，[PR 26](https://github.com/mindie-agent/remote-dev/pull/26) | 当前六项 CI 全部成功，含真实 OpenSSH loopback 三项通过（2.44秒）：RPC/二进制 artifact、durable job 存续与后代清理、写后断连 unknown 且不重放；属于隔离 loopback 验证，不代表 NPU/外部部署 |
| diagnostics | `210e96dcbbde364f13a6cd45a4f50488226a8a29`，[PR 13](https://github.com/mindie-agent/diagnostics/pull/13) | 当前 14 项 CI 成功（push/PR 两套）；主体本地 275 passed / 3 skipped，最终坏路径相关 83 passed；未知 POST 不自动重发，坏授权不清空 pending |
| npu-top | `96ff1291f5f7b659ddc93dafedabb1bfa1ca13ad`，[PR 15](https://github.com/mindie-agent/npu-top/pull/15) | 当前六项 CI 全部成功，覆盖 Linux/Windows 两版 Python、前端和完整 wheel；旧主体 Windows 两版各 141 passed / 5 build-only skips / 25 subtests。最终完整 wheel 正常依赖安装后，实际 HTTP health/overview、静态资源哈希与 schema 2 已验；没有真实 NPU/SSH bootstrap 验收 |
| coordinator | `b14321a45467b509199bef97324a9c0f65b29069`，[PR 40](https://github.com/mindie-agent/coordinator/pull/40) | 默认执行/排队期限、authority、远端结果保留已修；完整源码 1327 passed / 28 skipped / 52 subtests，正常安装后的相关 134 passed / 2 skipped / 20 subtests。实际 CI 发现首条 quiet 观测的计时未保存，已修正并经真实子进程回归和相关 57 passed / 5 Linux-only skips 验证；最终四项 CI（Linux/macOS/Windows/wheel）全部成功，计数不可相加 |
| Codex | `123909e922056d43992baff2a848dcd356ed2f33`，[PR 19](https://github.com/mindie-agent/mindie-agent-codex/pull/19) | 完整最终套件 379 tests / 12 平台 skips，其余通过，90.851 秒；preflight 和完整 run_ci 均 exit 0；最终候选已发布，当前 Linux CI 379 tests / 12 skipped（103.261秒）、Windows 379 tests / 19 skipped（487.415秒），其余全部通过；公开 GitHub 内容直接获取与新的隔离原生安装验证通过 |
| 公开内容 | `d4e7e8edf0539565284fde545518eacfb719bacc`，[PR 38](https://github.com/mindie-agent/knowledge-vllm-ascend/pull/38) | installed core 验证 21 entries / 1 feedback / 249215 bytes，四项变更均属 development；候选可从公开 GitHub 获取。旧 trusted-base CI 成功不证明新开发 neutral/Bot 策略已经采纳，开发检查不能授予自身自动合并 |
| 组织入口 | `f48f015217d4075b67ccab410c54f191933dd31f`，[PR 9](https://github.com/mindie-agent/.github/pull/9) | 当前入口指向架构/主线内容，完整正文与可选复用、Codex 与旧版 Kimi/Claude Code 边界一致；仅文档，不声称运行验收 |

上述测试计数覆盖不同提交和重叠测试，不合计为独立用例总数。每个 PR 的九原则记录绑定实际审查提交；新增 CI 发现的缺陷必须修正后再更新记录。

### 精确安装组合

隔离 venv 通过正常 Git 依赖安装与更新，未用 `--no-deps`、editable 或 `PYTHONPATH` 冒充已安装版本。`direct_url.json` 核对 knowledge `4dbe838`、remote-dev `9c8ae5e`、diagnostics `210e96d`。Codex 声明绑定内容完整候选 `d4e7e8e`，合同 SHA256 为 `783b415b1027dd8878b97a4e6548093da924b06bdad770563098724d5cefd730`。

运行时 pins 保持 knowledge `4dbe838`、remote-dev `9c8ae5e`：随后 core `b6aad81` 只改变 CI 预算，remote-dev `d7b3f4f` 只改变 CI 和测试对既有失败返回值的检查，生产代码与依赖完全相同。复用已验证的安装组合，不让 CI-only 提交引发无关 pin 更新。

发布前的完整本地套件显式在验收进程内使用精确内容提交的只读 Git 镜像；该阶段证据仍标注为本地验证。用户授权后，内容 `d4e7e8e` 和 Codex `123909e` 均已发布，新 preflight 和隔离原生安装从公开 GitHub 直接取得完整候选，未设置 URL 映射，合同和 validator 检查通过。这补齐远端可获取性，未修改全局 Git 配置或用户安装；候选分支可用不代表 main 已采纳新合同。

最终 Codex `123909e` 在 Codex CLI 0.153.4 的临时原生 profile 中实际安装并启用。候选与原生 cache 每个文件字节一致，发现 3 个 knowledge 和 11 个 remote MCP 工具。包 SHA256 为 `c27e5f54c0028b845ade13d66db13a787f70e7e9c89adb1c193d297a0c7323e1`。这是实际安装与入口验证，不代表宿主已经为真实用户任务派发 Hook。

通过已安装 Hook 命令输入合成 Stop 缺身份事件，得到中性 shell 输出及真实 `invalid_envelope` 投递。另一项在真实 Core 服务启动后损坏隔离 community JSON，由实际 outbox worker 产生 `knowledge.publish / authorization / authority_unavailable`；下一次已安装 MCP 能力调用收到该故障并 ACK，再次调用没有重复投递。没有直接塞入诊断来冒充后台错误。测试结束时 captures、summary attempts、publication outbox 均为 0，没有创建 Admission；所拥有服务正常退出，临时 profile 已移除。

Coordinator 最终 `b14321a` 已由公开 Git SHA 正常安装，source tree 外导入路径、remote-dev `9c8ae5e` / diagnostics `210e96d` 的 `direct_url.json` 及 Requires-Dist 已回读。安装包的真实 subprocess 末次观测与记录/输出故障相关五项测试通过；不是用源码覆盖已安装版本。

### 资源与外部验收

1024 块、16,384,000 正文 bytes 的实际 select/freeze/reload/validate/scan/apply，Python retained 2,901,898 bytes、peak 15,053,494 bytes。该测量不是进程 RSS 上限、模型质量证明或允许截断正文的阈值。长任务正文保持完整；导航摘要仍是可错的定位材料。

GitHub 最初拒绝 Git OAuth 的 workflow 写入后，用户明确授权使用现有 gh 登录。三项 workflow 修正和匹配 Codex 候选已通过每条命令独立选择 credential helper 发布，没有更改全局凭据配置。Core Windows 60分钟预算只限制 CI job，不改变业务执行期限、测试选择或运行时；当前全量测试已完成，测试耗时约36分39秒，原始日志和XML均已回读。真实 OpenSSH loopback 已由新 CI 验证；真实 NPU/外部远端部署、原生宿主 Hook 信任及首轮/fork 派发、在线模型质量/费用、公开上传与外部 Bot 采纳仍分别未验收，不能以本地安装或组件 CI 代替。内容主线仍缺少新 declaration，现有 trusted-base 工作流的绿色结果也不能证明新候选 workflow 已获采纳。

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
9. **错误可见。** 真实业务结果先于记录/清理失败保存；损坏不当首次使用/停用/空集，未知外部效果不重放。中性 Hook shell 回执与 Agent 故障送达分别验证。最初权限拒绝、随后明确授权与实际发布、仍未完成的验收分别明示。

以上是具体 diff 与行为的审查结论，不是对全部未来输入的保证。所有实际未验证项保留原边界；后续发布或实现改动仍需复查受影响原则。

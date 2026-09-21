# MindIE Agent 全局独立审查报告（Kimi K3/max，只读静态审查）

日期：2026-09-21。性质：只读静态代码审查；未运行任何测试/服务/模型/远端操作，未改任何产品代码或 Git。本报告不声称真实验收；所有"已证实"仅指代码事实，需实机确认的已单独标注。

## A. 模型、baseline、范围与覆盖

模型：本地 Kimi K3/max。十仓 HEAD 全部与 baseline.json 一致且工作树干净（design 87bb52c / core 59b6ec4 / codex 5e785f1 / kimi ff733ae / cc f9585a3 / remote-dev 13301ef / coordinator 0191b81 / diagnostics db16926 / npu-top 9c2c564 / content 6449d00）。

实际读过的入口与链路：
- design：docs/implementation-status.md（全文）、design-principles.md（任务供给）。
- core：loop/cli.py（全文）、loop/engine.py（capture/_process/agent/_submit/stop_if_idle/status 等关键段）、loop/process.py（全文）、loop/transport.py（全文）、loop/feed.py（sync 错误段）、loop/settings.py（public_status/load）。
- kimi：scripts/organizer.py（全文）、updater.py（stage/stop_if_idle/native_install/switch/rollback/_check_once/_feed_sync 关键段）、mcp_server.py（全文）、bridge.py（全文）、entry.py（dispatch/op_status/op_recover/status_payload）、sharing.py（全文）、bounded.py（进程组段）。
- cc：scripts/organizer.py（退出码段+与 kimi 全 diff）、mcp_server.py（failure/remote 段）、bounded.py（异常类型）、entry.py（op_recover 段）、bridge.py（handle_stop 段）。
- codex：scripts/mcp_gate.py（call_failure/_call 段）、agent_worker.py（退出码段）、auto_update.py（结构+install 段）、session_gate.py（结构）、sharing.py（status 全文）。
- remote-dev：core/errors.py（全文）、core/job_ops.py（_load_record/_classify_start_error/start_remote_job/remote_job_status/remote_job_tail）、mcp/server.py（错误信封段）、mcp/tools.py（call_tool 段）、result.py（结构）、cli.py（退出码段）。
- coordinator：cli.py（全文）、task_server.py（错误信封段）、task_client.py（结构+wait_error 段）、managed_execution.py（结构）、pyproject.toml（依赖声明）。
- diagnostics：reporter.py（publish_one/TransportError 段）、process_output.py（catch-all 段）、cli.py（结构）。
- npu-top：mcp.py（错误段）、cli.py（入口）、pyproject.toml、agent_view/api 接线确认。
- content：.github/workflows/check.yml（全文）、README.md。

已核对的边界行为（代码事实）：贡献关闭在任何采集状态创建前短路（core cli.py:221-223、engine.py:111-123）；Stop hook 只用 existing_service 不启动服务、永远 exit 0、失败标记 finish(False)（kimi bridge.py:63-135、cc bridge.py:112-161）；query 路径才允许 ensure_service 启动（kimi mcp_server.py:158-161）；失败 candidate 同 sha 抑制、不隐式重放（kimi updater.py:639-645）；contribution-retry 只重发已证实 failed 的存留载荷并打 explicit_retry（core cli.py:329-337）；更新器把 handoff pending/failed 折叠为 degraded 而非 switched（kimi updater.py:618-624、codex auto_update.py:224-228）；feed 同步状态与插件更新结果分开记录（kimi updater.py:708-746、fold_feed_results updater.py:89-141）；job record 先落盘后提交、submission_uncertain 不自动重发（remote-dev job_ops.py:249-251,271-282；diagnostics reporter.py:180,196-200）；core 拥有整理进程组、adapter 继承（core process.py:139-146 + kimi bounded.py:46-67）；remote-dev CLI 退出码与 outcome 一致（remote-dev cli.py:93-95,249-258）；content 发布 CI 用固定受审校验器、精确 head 校验、PR 文本脱敏扫描（check.yml）。

未覆盖/覆盖不足（诚实声明）：core store.py（1398 行）与 redact.py（765 行）只读了契约点；community/publish.py、gitops.py、transport.py 未逐行读；cc/kimi service_handoff.py 全文未读（只经调用点核对）；cc updater.py 与 kimi 的 438 行 diff 未逐行审；codex bridge.py/runtime_call.py/update_launcher.py/process_guard.py 未读；remote-dev ssh_transport/rpc_transport/local_process/processes/* 未读；coordinator service.py/ops.py/preparation_process.py/host_queue.py 未读；diagnostics service.py/platform_service.py/health.py/outbox.py 未读；npu-top probe.py/scheduler.py/client.py/device_adapter.py 未读；content cases/schema 细节未审。这些区域可能存在本报告未发现的点。

## B. Findings

**无已证实 P0。** 未发现静默吞错后报成功、失败材料隐式重放、或贡献关闭下采集的代码路径。

### P1-1　贡献失败对 agent 不可发现：recover 入口存在但 batch id 无任何 agent 可达的查询面（三端同根因）

- 代码事实：
  - core 侧失败记录完整且可查询：`sharing-status` CLI 打印 outbox/captures（core/mindie_knowledge/loop/cli.py:451-471）；RPC `sharing_status` 已返回 outbox（loop/transport.py:209-212）；`status` 含 engine errors（loop/engine.py:864-878，transport 兜底错误文案正是 "inspect service diagnostics"，loop/transport.py:148-153）；恢复操作 contribution-inspect/reconcile/retry/compact 均要求 `--batch`（loop/cli.py:255-347,436-441）。
  - 但 adapter 的 agent 面只暴露 settings 级状态：kimi/scripts/entry.py:275-277（op=sharing-status → sharing.public_status()）→ kimi/scripts/sharing.py:21-22（仅 settings）；kimi/scripts/entry.py:84-127（status_payload 只有 lease failures 计数）；kimi/scripts/entry.py:280-296（op=recover 无 batch 时只回 hint "pass --batch <id>"）；工具描述未说明 batch id 来源（kimi/scripts/mcp_server.py:36-41）。CC 同构：cc/scripts/entry.py:314-339。Codex 同样：codex/plugins/mindie-agent/scripts/sharing.py:303-345（status 只读 settings，无 outbox）。
- 触发前提与调用链：发布失败（如 GitHub 不可达）→ engine._submit 记 batch failed/unknown（engine.py:703-708）→ 用户后来问"我的贡献怎么了"→ agent 调 mindie_entry op=sharing-status/recover → 拿不到 batch_id 与 detail。
- agent 实际看到：settings 级 enabled/repository 等；"pass --batch <id>" 的 hint，但没有任何工具能列出 id。
- 影响：失败状态持久、安全（不自动重放），但发现-定位-恢复链断在第一步；只能由知道 engine config 路径的人手动跑 `python -m mindie_knowledge.loop.cli sharing-status --config …`（开发者级知识，普通 agent 不可行）。
- 已有恢复/绕过：core CLI 本身可用但 agent 面上无入口；故定为 P1 而非 P0（无数据丢失、无错误成功）。
- 最小修复（不增框架）：adapter 的 sharing-status（或 status）改调 core RPC `sharing_status`（载荷已存在，含 outbox）或读 store.status() 摘要，返回 batch_id/status/detail 列表，并在 mindie_entry 描述中写明"recover 的 batch id 见 sharing-status"。三端同一改法。
- 验证方式：构造一个 failed batch（断网提交），经 MCP sharing-status 能看到该 batch id 与 detail，再经 op=recover 完成 inspect/reconcile。

### P2-1　CC 与 Codex 整理器不发 typed 退出码，失败类别全部落 unknown（与 Kimi 的契约漂移）

- 代码事实：core 只认 78/124/70/65/75 → configuration/deadline/native/invalid_result/output_limit（core/mindie_knowledge/loop/process.py:36-42），未匹配退出码记 `category=unknown`（process.py:266-274）。Kimi 已发 typed 码（kimi/scripts/organizer.py:277-285）。但 CC 对所有异常（含 bounded.py:223 的超时 RuntimeError）统一 `raise SystemExit(2)`（cc/scripts/organizer.py:281-286）；Codex 对所有失败 `raise SystemExit(1)`（codex/plugins/mindie-agent/scripts/agent_worker.py:225-235）。
- agent 实际看到（结合 P1-1 修复后可查询）：capture failed，detail 为 `maintenance agent exited 2; category=unknown; elapsed=…`，无法区分配置错误/超时/原生调用失败/无效结果；设计明确禁止解析 stderr（process.py:33-35），所以 typed 码是唯一安全通道。
- 影响：可定位性按 host 不同而不同；不影响安全性与终态记录。implementation-status.md:47 只声称 Kimi typed 码，故此非已修问题的重开，而是三端收敛的剩余缺口。
- 最小修复：CC/Codex 整理器按 Kimi 同一映射把有界运行结果译为 78/124/70/65/75，仍不保存原始 stderr。验证：分别注入配置缺失、超时、输出超限、非 JSON 输出，核对 capture detail 的 category 字段。

### P2-2　kimi/cc adapter 的 remote 面把 remote-dev 结构化错误扁平化为纯文本（接口间错误类别丢失）

- 代码事实：remote-dev 原生 MCP 保留 error_details（category/submission_state/retryable，remote-dev/remote_dev/mcp/server.py:124-127；core/errors.py:26-45）。经 kimi adapter 时异常被压成 `Unavailable: {exc}. Continue independently.`（kimi/scripts/mcp_server.py:122-124,282-283）；CC 同（cc/scripts/mcp_server.py:94-96,238-239）。Codex 略好，保留异常类型名且区分 invalid_arguments（codex mcp_gate.py:42-51），但同样丢弃 remote-dev 的 category。
- 缓解事实（避免夸大）：最危险的"提交结果不确定"不是异常而是结果载荷（job_ops.py:278-281），该路径在三端都完整保留 job_id 与 submission_uncertain；caller 类错误的文本本身仍可行动。
- 影响：agent 丢失机器可读的 category/retryable，只能按文本判断换方法；属可定位性降级而非错误成功。
- 最小修复：adapter failure() 的 structuredContent 附带 `error_details(exc)`（remote-dev 已有现成函数）。验证：经 adapter 触发 EndpointError，检查 structuredContent.category=="internal"/"caller"。

## C. 架构简评

有效边界（保持）：
1. core 完全宿主中立：admission SQLite 路径与 transcript adapter 模块显式注入、拒绝猜测（core cli.py:35-90）；无 adapter 元数据解析。新增 host 不需要改 core。
2. remote-dev 是 coordinator 的声明依赖（coordinator pyproject.toml `remote-dev>=0.9.3`），task_server 复用其 error_details（coordinator task_server.py:169-171）——这是有边界的库复用，不是旧 scaffold 耦合。
3. 更新器三段式（stage→native install+readback→单原子指针翻转+同锁 rollback）与 handoff pending 预写（kimi updater.py:391-394,500-557）在三端结构一致；feed 与插件结果不互相掩盖。
4. 恢复操作确定性、无模型、不重放（core cli.py:255-270 docstring 与实现一致）。

具体耦合/漂移风险：
- 三 adapter 的 scripts 套件（identity/admission/entry/bridge/mcp_server/organizer/updater/service_handoff/knowledge_service/bounded/paths/transcript）是同构复制，各 200-900 行。P2-1（退出码契约只在 Kimi 兑现）和 P1-1（三端同时缺 outbox 面）证明复制已开始造成契约漂移。按原则 1 不建议现在抽共享包（会引入跨仓版本耦合，总成本更高）；最小对策是把三条契约写进 core 文档并让各 adapter 自检：①整理器退出码表；②sharing-status 载荷含 outbox；③错误信封附 error_details。
- 新增一个 host 的具体改动面：复制上述 scripts 套件 + 编写该 host 的 transcript adapter 模块（导出 FileIdentity/identify/read_material，core cli.py:85-89）+ host 包打包/install/readback（各 host 原生机制不同，无法共享）。核心零改动，符合现边界；主要成本在 adapter 套件约 3000 行的复制与契约对齐。
- 新增一个 domain：core 已是 root/domain 单域模型，feed 配置化（core cli.py:350-365），content 侧加仓库与 CI 即可；改动面小，无结构性障碍。

## D. 可执行优先顺序与暂不改

顺序：P1-1（恢复链可发现性，三端同一小改）→ P2-1（CC/Codex typed 退出码，向 Kimi 对齐）→ P2-2（adapter 错误信封带 error_details）。三者均为数十行级改动，不引入新组件。

暂不改/明确不建议：不抽三 adapter 统一框架或共享包；不加数据库/消息队列；不加自动重试或更复杂的状态机（现有 unknown/degraded/pending 语义已自洽）；不保存原始 provider stderr；不把 feedback/发布失败同步推给 agent（保持后台、可按需查询即可，符合原则 1/6）。

与静态 bug 分开的验收缺口（依 design/docs/implementation-status.md:41,51,83 记录，非本报告新发现）：Kimi 端完整 Stop→经验发布仍缺独立实机证据；旧退出 2 不能事后推断为超时；Windows 三端未验收。本报告不重复将其列为 finding。

# 2026-10-20 审查明细

[English](findings.en.md) · [审计概览与修改计划](README.md)

33 项主清单包含缺陷、测试缺口、重构建议、保留结论和待验证契约，并非 33 个已确认缺陷。源码链接固定在本轮 SHA。文中 `evidence/`、`tools/`、`scripts/repro_*` 为本地审计证据标识，不是已发布附件；原始日志和复现工具保留本地，公开版保留观测结果、源码定位与验证方法。

<a id="adp-01"></a>

## ADP-01 · P1 · 正确性缺陷：并发重放污染原操作收据

**仓库：** mindie-agent-cc; mindie-agent-kimi

**函数：** `handle / finish_bind / finish_nonce`

**行号：** CC 313-315,365-369; Kimi 327-328,363-367

**源码：** [mindie-agent-cc/scripts/mcp_server.py](https://github.com/mindie-agent/mindie-agent-cc/blob/78f34dd9b09e877298225fa243ea4c28978c9dd6/scripts/mcp_server.py#L301) · [mindie-agent-cc/scripts/identity.py](https://github.com/mindie-agent/mindie-agent-cc/blob/78f34dd9b09e877298225fa243ea4c28978c9dd6/scripts/identity.py#L324) · [mindie-agent-kimi/scripts/mcp_server.py](https://github.com/mindie-agent/mindie-agent-kimi/blob/0e78f0422162a61e8c56850e049f9e5fc4d290b5/scripts/mcp_server.py#L318) · [mindie-agent-kimi/scripts/identity.py](https://github.com/mindie-agent/mindie-agent-kimi/blob/0e78f0422162a61e8c56850e049f9e5fc4d290b5/scripts/identity.py#L532)

**触发场景：** 第一请求已 claim 后仍执行中；相同 toolUseId/request_nonce 第二请求到达，被 claim 拒绝，但其 finally 仍执行 finish(False)。

**证据：** evidence/adapters/repro-cc-bind.json；evidence/adapters/repro-kimi-bind.json；scripts/repro_adapter_bind.py

**影响：** 真实 SQLite 复现 claimed→第二请求拒绝→failed；第一请求最终成功也因 UPDATE WHERE status=claimed 不再更新。外部调用并未重复执行，但最终收据错误记录失败。

**修改建议：** 在成功 claim 后才设置 claimed 标志/receipt ownership，只有当前拥有者可 finalize；必要时以claim token做条件更新。保持并发重放拒绝。

**验证方式：** 新增真实 SQLite 并发或受控交错测试：阻塞首个业务调用，提交重复请求，断言记录仍claimed，释放首个调用后succeeded且业务只执行一次。

**结论确定性：** 已确认

<a id="adp-02"></a>

## ADP-02 · P1 · 正确性缺陷：追加日志误判替换

**仓库：** mindie-agent-dsh

**函数：** `identify / read_material`

**行号：** 64-74,191-198

**源码：** [mindie-agent-dsh/scripts/dsh_transcript.py](https://github.com/mindie-agent/mindie-agent-dsh/blob/d3a1e1282356b65b51fba49072c1842918746f8f/scripts/dsh_transcript.py#L64)

**触发场景：** 初次压缩日志短于512字节，记录FileIdentity后合法追加zstd frame；expected.anchor_len小于当前anchor_len。

**证据：** evidence/adapters/repro-dsh-transcript.log；scripts/repro_dsh_transcript.py；tests/test_dsh_transcript.py:151-164

**影响：** 106→213字节追加被返回status=replaced、end未推进、text为空；采集链路丢失该增量/报采集错误。现有append测试初始数据已超过512字节，漏掉短初始日志。

**修改建议：** 按expected.anchor_len重读旧长度前缀比较（CC transcript.py:374-382、Kimi transcript.py:231-238已有对应语义），保留路径/设备/inode及前缀检查。

**验证方式：** 补<512B初始日志连续追加、跨512B追加、真实前缀替换/截断场景；真实zstd压缩数据无mock，断言增量内容与cursor。

**结论确定性：** 已确认

**防御性代码审查**

- 保护风险：防止替换/改写文件导致重复或串任务采集。
- 风险是否存在：真实，宿主日志可追加/替换；不能删除身份检查。
- 上游不变量：追加只保证原前缀稳定，不保证重新读取512B所得摘要与短旧前缀摘要相同。
- 删除或合并的行为变化：正常append继续；真实替换继续replaced；这是正确性修复。
- 验证契约：短前缀append及替换契约；保留该防御并纠正比较长度。
- 结论：有明确依据应保留，修复实现

<a id="adp-03"></a>

## ADP-03 · P1 · 正确性缺陷与重构：扫描预算不成立

**仓库：** mindie-agent-dsh

**函数：** `_decompress / read_material`

**行号：** 92-114,210-226,247-259

**源码：** [mindie-agent-dsh/scripts/dsh_transcript.py](https://github.com/mindie-agent/mindie-agent-dsh/blob/d3a1e1282356b65b51fba49072c1842918746f8f/scripts/dsh_transcript.py#L92)

**触发场景：** 第一条公开记录超过max_text_bytes/max_scan_bytes或scan_until；大历史日志每次分页重新全量解压、解析并以bytes +=拼接。

**证据：** evidence/adapters/repro-dsh-transcript.log；scripts/repro_dsh_transcript.py；AGENTS.md:Transcript incremental scan max_seconds=2.0,max_text_bytes=48KiB

**影响：** 实测设置64B text、128B scan、scan_until=64仍返回1,000,009B并越界；时间检查只在全量解压/parse/拼接之后，无法约束前序工作；bytes+=累积带来平方级复制候选。大消息扩大下游脱敏/整理负担，扫描慢可反复返回unchanged。

**修改建议：** 分离zstd增量读取、公共记录投影与分页；预算在读取/投影阶段消费；首条超长记录需要明确oversize/分片契约而非无界放行；cursor单位需与snapshot/scan_until契约一致。

**验证方式：** 补超长首条、多帧大历史、残缺尾帧、scan_until边界和可注入时钟测试；断言字节/时间/游标上限与不丢重复内容。不能仅验证类型和more。

**结论确定性：** 已确认

<a id="adp-04"></a>

## ADP-04 · P1 · 正确性缺陷：候选stage共用活动运行时

**仓库：** mindie-agent-dsh

**函数：** `check / setup_candidate / main / sync_runtime`

**行号：** updater 268-277; setup 113-125,183-196,313-334; mindie_paths 60-65

**源码：** [mindie-agent-dsh/scripts/updater.py](https://github.com/mindie-agent/mindie-agent-dsh/blob/d3a1e1282356b65b51fba49072c1842918746f8f/scripts/updater.py#L268) · [mindie-agent-dsh/scripts/setup.py](https://github.com/mindie-agent/mindie-agent-dsh/blob/d3a1e1282356b65b51fba49072c1842918746f8f/scripts/setup.py#L113) · [mindie-agent-dsh/scripts/mindie_paths.py](https://github.com/mindie-agent/mindie-agent-dsh/blob/d3a1e1282356b65b51fba49072c1842918746f8f/scripts/mindie_paths.py#L60)

**触发场景：** 自动更新/--stage-only准备候选时setup_candidate调用candidate setup；甚至apply=False也在判断前调用。

**证据：** repos/mindie-agent-dsh/scripts/updater.py:269；repos/mindie-agent-dsh/scripts/setup.py:313；repos/mindie-agent-dsh/scripts/mindie_paths.py:60；tests/test_updater.py:38-75仅覆盖choose/checksum/extract

**影响：** candidate setup指向data_home()/venv和config_home()/engine.json，更新共享venv、复制capture脚本、停止现有服务、覆盖配置；current.json尚未切换即影响旧代，准备失败或stage-only可能留下旧JS+新Python混合代。

**修改建议：** 将candidate runtime/config/capture脚本全部写入generation私有路径，验证后在统一切换协议下更新指针；共享授权/知识持久状态作为显式外部引用。失败时旧代运行时保持可用。

**验证方式：** 组件测试真实临时venv/config（外部依赖下载可用local wheel边界替身）验证stage-only及每阶段故障时活动runtime/config hash和服务身份不变；成功切换后新旧代配套。

**结论确定性：** 已确认调用路径；未执行真实安装变更

<a id="b01"></a>

## B01 · P1 · 已确认缺陷：进程生命周期

**仓库：** mindie-bench

**函数：** `local_verifier.execute`

**行号：** 157-178, 201-208

**源码：** [mindie-bench/src/mindie_bench/runner/verifier.py](https://github.com/mindie-agent/mindie-bench/blob/b7301839602ad3791af17f21f5aa47d773b5af2a/src/mindie_bench/runner/verifier.py#L157)

**触发场景：** macOS 本地 verifier/test.sh 派生后台子进程后超时；外层调用已经返回，但后台进程未退出。Linux bwrap 的 PID namespace 语义不同，本项不外推为所有平台必现。

**证据：** tools/repro_bench_timeout.py；evidence/bench-timeout-reproduction.json：timeout=0.2s，0.208s 返回 TimeoutExpired，0.7s 后后代仍写入 profile/tmp/after_timeout.txt。subprocess.run 无新 session/group，异常路径只复核 oracle 文件。

**影响：** 验证超时无法证明进程已回收，后代可能继续消耗资源或修改允许写入的目录；run_trial 在 verifier phase 将普通超时归为 infra_failed，未确认残留就作为干净失败处理。

**修改建议：** 正确性修复：采用有归属的进程组生命周期，预算中预留 TERM/KILL 和排空时间，保存超时前输出；无法确认回收时保留 unknown，不能只重命名异常。

**验证方式：** 真实短时后代进程测试：超时后进程/孙进程均不存在且不能再写；普通失败保留结构化判定；清理失败保留独立诊断与原始判定。

**结论确定性：** 高；真实 macOS sandbox-exec 动态复现

**防御性代码审查**

- 结论：有明确依据应保留并修正
- 保护风险：超时后不确定外部效果与孤儿进程
- 风险是否存在：真实存在；已复现超时后的写入
- 上游不变量：native_command 只建立文件/网络沙箱；subprocess.run 不承诺清理后代，run_trial 没有该进程句柄
- 删除或合并的行为变化：不能删除超时或unknown保护；增加确认后的状态分类会改变失败语义
- 验证契约：真实进程树排空、清理失败、正常/非零退出分别验证

<a id="d02"></a>

## D02 · P1 · 防御代码保留

**仓库：** remote-dev

**函数：** `resolve_path / atomic_write`

**行号：** 35-58, 77-91

**源码：** [remote-dev/remote_dev/core/remote_file_worker.py](https://github.com/mindie-agent/remote-dev/blob/c3af104c36582c675a6dcd368637db7c60b28afd/remote_dev/core/remote_file_worker.py#L35)

**触发场景：** 本地合法路径在远端解析为root外符号链接，或写目标本身是符号链接。

**证据：** 本地path_policy仅POSIX字符串规范化，不能读取远端文件系统；worker解析真实路径再检查；docs/transport-and-diagnostics.md:64明确边界。

**影响：** 删远端检查会突破工作目录约束；RD01证明不能因为本地入口校验通过就删远端边界。

**修改建议：** 保留真实路径检查与写入目标策略；任何TOCTOU加强另开变更。

**验证方式：** 本地原worker根外symlink拒绝、正常根内路径成功；Linux补测并发目录替换。

**结论确定性：** 已确认

**防御性代码审查**

- 结论：有明确依据应保留
- 保护风险：远端符号链接/真实路径越界
- 风险是否存在：受支持SSH/Linux目录可由其他进程改变
- 上游不变量：入口只保证字符串root内，不能保证远端解析结果；path_policy.py:13-39
- 删除或合并的行为变化：删除会扩大文件访问范围；并非等价重构
- 验证契约：真实临时文件树和符号链接路径契约；不靠mock返回或类型标注

<a id="d03"></a>

## D03 · P1 · 防御代码保留

**仓库：** coordinator

**函数：** `HostCoordinator._check_token / process_guard_busy`

**行号：** 835-837, 146-177

**源码：** [coordinator/mindie_coordinator/host/mindie_npu_coordination.py](https://github.com/mindie-agent/coordinator/blob/c77144a95dd6af37e978ffc2d8495158b237090d/mindie_coordinator/host/mindie_npu_coordination.py#L835)

**触发场景：** 旧客户端携过期fencing token回放activate/release；进程正在CPU初始化、npu-smi为空或/proc暂不可读。

**证据：** HostQueue是分配唯一权威（AGENTS.md:5）；_check_token对SQLite当前token核验；process_guard_busy:149-152说明空硬件占用不是进程完成；managed_execution._finish_managed:435-445只在quiet确认后释放。tests/test_npu_coordination.py:341-374真实SQLite并发原子分卡。

**影响：** 删除可造成旧客户端释放新租约或仍存活任务的设备被重分配；None/权限保护并非假想敌。

**修改建议：** 保留token、boot identity、不可读保持占用与descendant-drained要求；将必要理由收敛成边界契约。

**验证方式：** 真实SQLite stale-token拒绝、不同会话原子互斥；Linux隔离/proc进程族/换boot身份/权限不可读保持占用、确认quiet后才释放。

**结论确定性：** 已确认

**防御性代码审查**

- 结论：有明确依据应保留
- 保护风险：旧授权重放、CPU初始化/失联时误释放仍可使用NPU的任务
- 风险是否存在：SSH并发、多客户端、监督者故障均属当前支持范围
- 上游不变量：本地状态非宿主SQLite权威；硬件空闲并不保证进程quiet；代码146-177明确反例
- 删除或合并的行为变化：删除改变分配互斥和清理安全语义
- 验证契约：fencing负例+Linux隔离受控子进程生命周期；不能仅凭正常路径通过删掉

<a id="k-01"></a>

## K-01 · P1 · 已确认缺陷：遗留兼容分支绕过原文不落库约束

**仓库：** knowledge

**函数：** `accept_stop`

**行号：** 460-477; cli.py:66; store.py:332-395

**源码：** [knowledge/mindie_knowledge/loop/handoff.py](https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/mindie_knowledge/loop/handoff.py#L460)

**触发场景：** 合法 engine config 省略 capture_mode；已授权、已激活的 turn Stop 携带 last_assistant_message。省略 transcript_path 也会被此分支接收。

**证据：** evidence/knowledge/probes.json；evidence/knowledge/probes-pinned.json；tools/knowledge_probes.py；tests/test_capture_handoff.py:151-178；AGENTS.md:Incremental Transcript Capture & Redaction

**影响：** validate_config 将省略模式解释为 public-transcript，却没有归一化；accept_stop 采用无默认 get，进入旧 summary 路径，未脱敏原文写入 captures.summary，且无 transcript 可入队。未发现此路径直接上传原文。四宿主正常生成配置均显式带 public-transcript，因此不是正常安装必现。main 021ba95e 和插件 pin 4e328305 的 cli.py/handoff.py 字节完全相同，两个版本都已实证。

**修改建议：** 把唯一受支持 public-transcript 模式在配置边界归一化，删除 handoff 旧 summary fallback 和只服务该分支的 SUMMARY_LIMIT。所有非 notification turn 必须有 transcript；summary 恒为空。单独审查既有 captures.summary 中遗留内容的处置，不能未经用户允许清空历史。

**验证方式：** 真实 Consent+Admission+SQLite 参数化：capture_mode 显式/省略 × transcript 有/无 × 原文短/超长；两种合法模式行为一致、有源时 summary=''，无源时 rejected。保留 notification forbids-summary 契约；验证 engine 不执行不可处理的无源 capture。

**结论确定性：** 高：main 与实际 pin 均运行复现；canary 是固定人造 AUDIT_CANARY_RAW_NATIVE_ANSWER。仅 readiness 观察被替换为 ready 以避免拉起后台服务，核心验证/持久化均真实。

**防御性代码审查**

- 保护风险：历史 summary-only Stop 输入兼容与超长正文兜底。
- 风险是否存在：不再支持：cli.validate_config:66-67 仅接受 public-transcript，Engine.__init__ 同样拒绝其他模式。省略字段合法，故不能声称旧分支不可达。
- 上游不变量：配置验证已保证模式属于唯一支持范围，但默认值未写回，是两个边界解释不一致。
- 删除或合并的行为变化：正常显式 public-transcript 不变；省略模式改为等同显式值，停止保存原文；无源输入从接收变拒绝。属于隐私/输入语义修复，非等价重构。
- 验证契约：上述完整真实落库对照测试，附 pin 回归。
- 结论：建议删除或合并

<a id="rd01"></a>

## RD01 · P1 · 已确认缺陷：目录范围契约

**仓库：** remote-dev

**函数：** `REMOTE_SEARCH_PY glob branch / remote_glob`

**行号：** 317-352, 573-584

**源码：** [remote-dev/remote_dev/core/search_ops.py](https://github.com/mindie-agent/remote-dev/blob/c3af104c36582c675a6dcd368637db7c60b28afd/remote_dev/core/search_ops.py#L317)

**触发场景：** endpoint.root限定工作目录，pattern使用../outside/*、绝对路径或根内目录符号链接指向根外。

**证据：** 临时复现 tools/reproduce_remote_findings.py；evidence/remote-trio/reproductions.json 三例均status=ok并返回根外文件名/size/mtime。入口只验证path；worker只验证base后直接iglob并lstat匹配项。docs/transport-and-diagnostics.md:64承诺--root目录约束；path_policy.py:4声明每个远端路径均须位于root。

**影响：** 已证实根外文件元数据枚举；不把此证据扩展为任意内容读取或shell鉴权绕过。

**修改建议：** 明确glob pattern相对基目录的约定；拒绝越界pattern；对真实匹配项解析路径并执行同一root约束，阻止递归符号链接遍历越界。

**验证方式：** 原生产worker在临时双目录树运行：相对../、绝对路径、符号链接escape均拒绝；根内绝对/相对pattern与正常排序、过滤行为按最终约定回归。

**结论确定性：** 已确认

<a id="t01"></a>

## T01 · P1 · 已确认测试基线缺口

**仓库：** remote-dev + coordinator + npu-top

**函数：** `coverage measurement / embedded worker dispatch`

**行号：** remote:26-531; coordinator:1414-2424; npu package.json:9-13

**源码：** [remote-dev/remote_dev/core/search_ops.py](https://github.com/mindie-agent/remote-dev/blob/c3af104c36582c675a6dcd368637db7c60b28afd/remote_dev/core/search_ops.py#L26) · [coordinator/mindie_coordinator/provision/host_ops.py](https://github.com/mindie-agent/coordinator/blob/c77144a95dd6af37e978ffc2d8495158b237090d/mindie_coordinator/provision/host_ops.py#L1414) · [npu-top/package.json](https://github.com/mindie-agent/npu-top/blob/8f992bf033af57979d6bebf67189a89bb2034d7e/package.json#L9)

**触发场景：** 只给pytest父进程或Python源码coverage总数，进而声称所有生产逻辑已覆盖。

**证据：** 审计配置启用branch/source全包/无omit无排除；增强patch=subprocess后仍remote_file_worker、rpc_worker、artifact_worker为0采集，现有测试却确实通过python -c/-I执行其文本。search_ops内505行Python字符串在外层coverage只算赋值；coordinator host_ops渲染1003行脚本同理；前端只有lint/build无测试命令。

**影响：** 未导入文件已在分母内，但动态字符串代码缺少独立分母；采集0不能等同无测试。Python比例完全不代表前端、远端Linux、硬件或E2E。

**修改建议：** 分别发布父进程/本地子进程联合/远端workers数据和TS覆盖范围；worker迁独立模块并compile真实filename，再为受控Linux本地或远端测试配置coverage数据回收。独立建立前端行为测试。

**验证方式：** 每份报告验证source枚举含未导入文件；用哨兵确认普通子进程采集；列明动态源和-I未采集项；远端结果按同SHA/相同配置合并，不与不匹配版本合并。

**结论确定性：** 已确认

<a id="adp-05"></a>

## ADP-05 · P2 · 错误语义与冗余恢复逻辑

**仓库：** mindie-agent-dsh

**函数：** `connection`

**行号：** 281-290

**源码：** [mindie-agent-dsh/scripts/mindie_sidecar.py](https://github.com/mindie-agent/mindie-agent-dsh/blob/d3a1e1282356b65b51fba49072c1842918746f8f/scripts/mindie_sidecar.py#L281)

**触发场景：** 核心ensure_service报告unknown/worker-dead或任意异常时，适配器无差别删除connection.json并再次启动。

**证据：** evidence/adapters/repro-dsh-connection.json；scripts/repro_dsh_connection.py；pinned/knowledge/mindie_knowledge/loop/cli.py:130-191 (4e3283053)

**影响：** 故障注入实测第一次异常后原endpoint被删，第二次被调用；核心明确拒绝unknown状态启动第二服务，且用StartLock掌管启动。适配器清除诊断/连接依据并掩盖首次错误，不保证第二服务实际启动（取决于核心锁/探针）。

**修改建议：** 删除适配器unlink+盲目二次ensure；让共享生命周期拥有恢复和错误分类，原始异常通过sidecar错误响应报告。

**验证方式：** 为unknown、worker-dead、PermissionError故障注入，断言只调用一次、endpoint不变且错误可定位；连接旧端点恢复行为在共享runtime边界测试。

**结论确定性：** 已确认

**防御性代码审查**

- 保护风险：原意是修复旧/坏connection.json导致连接失败。
- 风险是否存在：端点失效风险真实，但任意异常不证明旧端点可删除。
- 上游不变量：锁定knowledge cli.ensure_service:141-146,152-165已探测ready/unknown/absent并持启动锁。
- 删除或合并的行为变化：不再二次尝试或删除状态；调用方收到首次失败，属于错误语义修复，不能称等价。
- 验证契约：一次调用、保留端点、明确失败；共享core旧端点恢复契约。
- 结论：建议删除或合并

<a id="adp-06"></a>

## ADP-06 · P2 · 错误语义缺陷：本地收据写失败静默吞掉

**仓库：** mindie-agent-cc; mindie-agent-kimi

**函数：** `finish_bind / finish_nonce / handle`

**行号：** CC identity 339-340; mcp_server 365-369; Kimi identity 544-545; mcp_server 363-367

**源码：** [mindie-agent-cc/scripts/identity.py](https://github.com/mindie-agent/mindie-agent-cc/blob/78f34dd9b09e877298225fa243ea4c28978c9dd6/scripts/identity.py#L339) · [mindie-agent-cc/scripts/mcp_server.py](https://github.com/mindie-agent/mindie-agent-cc/blob/78f34dd9b09e877298225fa243ea4c28978c9dd6/scripts/mcp_server.py#L365) · [mindie-agent-kimi/scripts/identity.py](https://github.com/mindie-agent/mindie-agent-kimi/blob/0e78f0422162a61e8c56850e049f9e5fc4d290b5/scripts/identity.py#L544) · [mindie-agent-kimi/scripts/mcp_server.py](https://github.com/mindie-agent/mindie-agent-kimi/blob/0e78f0422162a61e8c56850e049f9e5fc4d290b5/scripts/mcp_server.py#L363)

**触发场景：** 业务调用已成功，finish期间SQLite错误或_open失败。

**证据：** repos/mindie-agent-cc/scripts/mcp_server.py:11-14声明bind_warning+diagnostic_ref但实现finally except pass；repos/mindie-agent-kimi/scripts/mcp_server.py:363-367；repos/mindie-agent-cc/scripts/identity.py:335-340；repos/mindie-agent-kimi/scripts/identity.py:540-545

**影响：** 内层sqlite3.Error pass与外层Exception pass双重吞错，记录留claimed且返回结果无记账警告；成功业务不得改成失败，但用户/诊断也无法获知本地账目不完整。

**修改建议：** 内层传播或返回结构化accounting failure；外层保留业务结果isError并附warning/diagnostic_ref、禁止自动重试。

**验证方式：** 真实SQLite故障注入：BEGIN/UPDATE/commit失败；断言成功内容不变、明确warning、诊断可追踪、重放被拒绝。

**结论确定性：** 已确认静态路径

**防御性代码审查**

- 保护风险：保护已成功外部业务，防止记账失败使调用方重试。
- 风险是否存在：真实且应保留成功语义。
- 上游不变量：业务结果已计算，finish仅本地SQLite记账；CC模块契约明确warning。
- 删除或合并的行为变化：成功结果保持；增加记账失败可见性。删除吞错是错误语义/可观测性修复，不是纯等价清理。
- 验证契约：成功结果+写失败警告+不重试三者同时验证。
- 结论：建议合并双层捕获，保留成功结果保护

<a id="b02"></a>

## B02 · P2 · 已确认测试缺口

**仓库：** mindie-bench

**函数：** `contracts test selection`

**行号：** 26

**源码：** [mindie-bench/.github/workflows/ci.yml](https://github.com/mindie-agent/mindie-bench/blob/b7301839602ad3791af17f21f5aa47d773b5af2a/.github/workflows/ci.yml#L26)

**触发场景：** CI 以 -k 'not actual' 排除名称包含 actual 的测试，连纯内存判定与本地协议测试一并排除。

**证据：** tests/test_evaluation_coverage.py:96-101 仅构造 evidence 并验证重复次数门禁，却被筛掉；补跑 evidence/mindie-bench-actual/tests.log：39 passed、10运行时skip、1重复的collection skip；实际选中49个测试。

**影响：** 重复次数不足却报告可靠、错误的结果解析和oracle控制等回归可避开常规CI。名称筛选同时未排除依赖本机Codex的 test_native_mcp_readiness，无法可靠表达测试层级。

**修改建议：** 单独测试体系变更：引入明确的本地/宿主/硬件marker或目录约定，移除名称过滤；将纯逻辑actual用例纳入本地门禁。

**验证方式：** --collect-only 保存各层节点清单，断言纯逻辑用例进入本地集合；同一源码运行前后比较新增执行的业务场景和时长。

**结论确定性：** 高；补跑已有用例

<a id="b03"></a>

## B03 · P2 · 重构建议

**仓库：** mindie-bench

**函数：** `run_trial`

**行号：** 298-995

**源码：** [mindie-bench/src/mindie_bench/runner/orchestrator.py](https://github.com/mindie-agent/mindie-bench/blob/b7301839602ad3791af17f21f5aa47d773b5af2a/src/mindie_bench/runner/orchestrator.py#L298)

**触发场景：** 同一函数处理oracle冻结、配置检查、profile/进程/远端lease、模型网关、验证、经验采集、计量、清理和最终回执；新阶段需要修改共享的 phase/status/primary/auxiliary。

**证据：** 698行函数；异常分类781-797、计量异常879-882、remote cleanup892-900、最终reward清空962-963都能改变最终状态。原有tests/test_capture_diagnostics.py、test_remote_settlement.py通过patch多阶段才能触发具体状态。

**影响：** 判定与I/O耦合使新增失败分支容易漏保留已完成的业务判定；同一状态决策散布于try/except/finally，独立测试成本高。

**修改建议：** 先补各阶段结果/清理结果的特征测试；提取纯结果归并函数与小型阶段资源对象，保持一次副作用执行和原始回执。不要新增平行持久状态机；既有错误语义变化另立提交。

**验证方式：** 对PASS/FAIL/INFRA/UNKNOWN × scoring/capture/cleanup异常做表驱动特征测试，比较原始verifier判定、终态、成本完整性和重试许可；真实子进程契约仍由组件测试负责。

**结论确定性：** 高（职责混合）；不将长度本身视为缺陷

<a id="b04"></a>

## B04 · P2 · 已确认测试缺口

**仓库：** vllm-ascend-workspace

**函数：** `run / path_at / main`

**行号：** 13-135

**源码：** [vllm-ascend-workspace/.agents/scripts/workspace.py](https://github.com/mindie-agent/vllm-ascend-workspace/blob/c85b9ca94c5432a58f3e0bff6bbbcd5d711d8ca8/.agents/scripts/workspace.py#L13)

**触发场景：** 使用 worktree-add/remove、task-init、directory-remove；现有4个测试都只通过子进程调用repo_init.py。

**证据：** evidence/vllm-ascend-workspace/tests.log 4 passed；coverage.json：repo_init.py 97/105行、33/42分支，workspace.py 0/103行、0/40分支；总计97/208行、33/82分支。

**影响：** 工作树参数、task元数据、链接与删除边界变化没有现有回归保护；不能用初始化测试全绿证明脚手架主命令正确。

**修改建议：** 只补有业务价值的真实临时Git/目录测试：新worktree指向正确提交；dirty worktree删除失败；task links/metadata正确；dry-run不改状态；显式删除仅作用于指定对象。

**验证方式：** 在临时本地Git仓运行每个CLI分支，对提交、文件、链接和退出语义断言；无网络、不触及用户工作树。第一批目标workspace.py行≥85%、分支≥80%，重要删除/保留场景逐项通过。

**结论确定性：** 高；包含未导入文件的实测覆盖率

<a id="b06"></a>

## B06 · P2 · 已确认测试环境契约缺口：可选组件场景要求不兼容的共同解释器组合

**仓库：** mindie-bench

**函数：** `module collection / value_coordinator.run / value_diagnostics.one`

**行号：** tests/test_component_value_scenarios.py:8-10,15-37; src/mindie_bench/benchmarks/value_common.py:24-33; coordinator/pyproject.toml:14-15; knowledge/pyproject.toml:21

**源码：** [mindie-bench/tests/test_component_value_scenarios.py](https://github.com/mindie-agent/mindie-bench/blob/b7301839602ad3791af17f21f5aa47d773b5af2a/tests/test_component_value_scenarios.py#L8) · [mindie-bench/src/mindie_bench/benchmarks/value_common.py](https://github.com/mindie-agent/mindie-bench/blob/b7301839602ad3791af17f21f5aa47d773b5af2a/src/mindie_bench/benchmarks/value_common.py#L24) · [coordinator/pyproject.toml](https://github.com/mindie-agent/coordinator/blob/c77144a95dd6af37e978ffc2d8495158b237090d/pyproject.toml#L14) · [knowledge/pyproject.toml](https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/pyproject.toml#L21)

**触发场景：** 按本轮当前精确SHA为bench的可选component-value测试安装coordinator与knowledge到同一独立解释器；模块在收集阶段同时要求三者import，实际场景还使用remote-dev与npu-top分发元数据。

**证据：** evidence/mindie-bench-optional/resolve-components-authorized.log: uv明确拒绝mindie-diagnostics的两个冲突Git URL，exit1；evidence/mindie-bench-optional/resolve-components-authorized.json: 完整dry-run命令、8.189秒、独立venv路径；coordinator@c77144a95dd6af37e978ffc2d8495158b237090d/pyproject.toml:14 pins diagnostics@6460cde3a50a7f91c9ded38557a7f921654f0c6a；knowledge@021ba95e701d4f8c8d924e2dcc8f120a4939da23/pyproject.toml:21 pins diagnostics@1b5a0eeb79d498c39002fc1853271c17e0f26e66；evidence/mindie-bench-host/tests.log:227 与 mindie-bench-actual/tests.log:56 均在模块收集时因缺coordinator跳过；evidence/mindie-bench-optional/component-collect.log: 独立原锁harness仍为模块级skip、0 collected；另14项可选CPU/stale/FastMCP测试已独立补跑通过，但不包括本模块两项场景；src/mindie_bench/benchmarks/value_diagnostics.py:82-86 实际使用knowledge.consent_store，并非可随意绕过的无用import

**影响：** 默认锁定CI没有这些可选组件，两项本地真实端口租约/诊断去重撤权场景未被收集。简单安装当前所有组件也无法得到满足声明的单解释器环境；--no-deps或强制覆盖diagnostics会制造未支持组合。此结论只针对可选测试的组合和依赖契约，不证明各组件独立部署失败，也不证明这两个测试的业务行为有缺陷。

**修改建议：** 给可选场景定义可复现的组件版本/解释器清单。按实际组件边界分进程、分环境执行并传递可观察结果；收集门禁与source_revisions只要求该场景真实使用的组件。若需要单解释器组合，先确认并验收兼容版本矩阵再发布锁，不未经验证统一diagnostics pin。

**验证方式：** 用精确Git SHA创建全新环境，resolver通过且pip check无依赖冲突；两项既有场景分别收集、执行，对真实SQLite/端口冲突、保留活跃租约、仅一次HTTP POST、脱敏及撤权后零请求做原有断言。保存全部第一方direct_url来源。可选结果单独报告，不和原CI默认baseline或不同环境coverage自动合并。

**结论确定性：** 高：实际解析器复现精确URL冲突，模块收集skip已有日志；未强行安装或声称现有生产部署失效。

<a id="co01"></a>

## CO01 · P2 · 已确认缺陷：错误语义

**仓库：** coordinator

**函数：** `CoordinatorService._configured_machines / _ensure_user_container / _progress`

**行号：** 947-954, 961, 672-676

**源码：** [coordinator/mindie_coordinator/service.py](https://github.com/mindie-agent/coordinator/blob/c77144a95dd6af37e978ffc2d8495158b237090d/mindie_coordinator/service.py#L947)

**触发场景：** 机器注册文件损坏、读取被拒绝或I/O异常，且任务需要选择/准备运行环境。

**证据：** 用真实MachineDirectory读取临时{invalid-json：machines()抛JSONDecodeError，_configured_machines()返回[]（reproductions.json）。_ensure_user_container遍历空列表，上层_place_or_prepare返回cache_miss，_progress进入waiting_for_runtime。

**影响：** 可定位的注册表故障被伪装成无机器/无匹配环境，任务等待而无原始错误；排错和恢复路径误导。

**修改建议：** 只对确实未配置inventory的明确状态返回空；配置存在时传播带文件位置的解析/读取错误并进入可恢复失败态。此为错误语义修复，不能宣称等价重构。

**验证方式：** 真实临时machines.json分别空配置、合法空列表、损坏JSON、权限/IO失败；断言对外状态和错误来源，修好文件后能继续且不重复已提交远端任务。

**结论确定性：** 已确认

**防御性代码审查**

- 结论：建议删除或合并
- 保护风险：避免可选机器目录不可用时阻塞准备
- 风险是否存在：未配置可选目录是真实场景，但损坏已配置目录不是零台机器
- 上游不变量：MachineDirectory.load:222-243明确区分合法文档与读取/解码错误，上游没有保证不会失败
- 删除或合并的行为变化：删除宽泛except后正常合法目录行为不变；错误由cache_miss/waiting变成可定位失败，调用方须处理
- 验证契约：真实文件故障与修复恢复契约，禁止默认为空成功

<a id="d-01"></a>

## D-01 · P2 · 已确认缺陷：比较 CLI 工作负载身份门禁与契约不符

**仓库：** diagnostics

**函数：** `compare_profiles`

**行号：** 502-516; cli_compare.py:101,117; README.md:185

**源码：** [diagnostics/mindie_profiler/compare.py](https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/mindie_profiler/compare.py#L502)

**触发场景：** 两份真实 C7 摘要的 runtime/device/model/shape/dtype 相同，但双方或一方缺少 scene.input_signature。

**证据：** evidence/diagnostics/probes.json:missing_workload_signature；tools/diagnostics_probes.py；tests/test_profiler_compare.py:75-111；tests/test_profiler_cli_compare.py

**影响：** 实际 analyze_profile 生成摘要再走公开 compare CLI，得到 comparable=true、status=comparable_with_limitations、exit0；README 明确缺少工作负载签名应 not_comparable/exit3。相同模型与 shape 不能证明请求内容和工作负载一致，自动性能验收可能接受不可比运行。仅适用于 diagnostics main 0.5.0 的 profiler；不得把它算作插件 pin 0.4.3 已使用的链路。

**修改建议：** 区分允许探索性比较的 Python API 与严格 CLI 验收策略；strict CLI 将缺失、单边、不可规范化 input identity 作为 hard reason，保留已有宽松 API 时显式命名策略。

**验证方式：** 真实 analyze_profile→写 JSON→CLI：双缺失/单边缺失/空白/unknown/相同/不同 signature；缺失等 exit3且无成功性能判定，相同才可exit0。

**结论确定性：** 高：真实生产 producer 与 CLI 已运行复现；现有 API 测试主动允许 missing signature limitation，不能直接全部改成严格而忽略兼容边界。

<a id="d-02"></a>

## D-02 · P2 · 已确认缺陷：已识别无效摘要后仍直接解引用

**仓库：** diagnostics

**函数：** `compare_profiles`

**行号：** 531-553; cli_compare.py:114-117

**源码：** [diagnostics/mindie_profiler/compare.py](https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/mindie_profiler/compare.py#L531)

**触发场景：** 导入 schema_version 正确但 step_accounting=null（或非 Mapping）的 C7 JSON。

**证据：** evidence/diagnostics/probes.json:null_step_accounting；tools/diagnostics_probes.py；mindie_profiler/compare.py:_rank_scope

**影响：** _rank_scope 已记录 rank_scope_unavailable，但 compare_profiles 随后 .get(...).get 抛 AttributeError；API 宣称不兼容返回结果而不抛异常，CLI catch 也不处理此异常，用户得到 traceback 而不是结构化 not_comparable。

**修改建议：** 在摘要输入边界规范化/验证 step_accounting 容器一次，复用已经验证的对象，或在已知 hard 容器错误时立即返回。不要用宽泛 except Exception 把内部算术错误吞成空结果。

**验证方式：** 公开 CLI 和 API 对损坏外部摘要返回固定错误语义；使用真实 producer 结果只替换 step_accounting 为 null/list，断言失败原因与退出码，不仅断言不抛异常。

**结论确定性：** 高：运行复现 AttributeError；触发限于损坏/第三方生成摘要，不声称当前 analyze_profile 正常产生 null。

<a id="d-03"></a>

## D-03 · P2 · 待验证契约：显存 peak 缺少测量口径仍给出可比结论

**仓库：** diagnostics

**函数：** `compare_peaks`

**行号：** 56-65

**源码：** [diagnostics/mindie_profiler/memory_compare.py](https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/mindie_profiler/memory_compare.py#L56)

**触发场景：** baseline 声明 bytes/phase/scope/is_peak 但没有 measurement_kind/peak_scope，candidate 为 sampled_device_peak/sampled。

**证据：** evidence/diagnostics/probes.json:peak_missing_measurement_kind；tests/test_profiler_memory.py:318-335；mindie_profiler/memory_compare.py:module invariants

**影响：** 实测 comparable=true、ratio=1.5；文档说测量与峰值口径一致才能比较，但缺失字段路径不证明一致。现有测试把双方缺字段作为合法旧输入，尚不能仅凭注解认定可以删除兼容。

**修改建议：** 先明确公开 API 是否需要兼容无 measurement_kind 的旧字典；严格模式缺失口径必须 not_comparable，兼容模式只能给 unverified，不能自动用于峰值改善验收。

**验证方式：** 实测/有限采样/点观测 × 双方完整/单边缺失/双方缺失；同口径才能给可比峰值结论，保留 is_peak=False 拒绝。

**结论确定性：** 行为高、支持范围中：运行可复现，兼容策略需产品契约确认。

**防御性代码审查**

- 保护风险：兼容未携带新增 peak 元数据的旧调用方。
- 风险是否存在：tests/test_profiler_memory.py:318-335 显式使用无口径字典，存在兼容迹象。
- 上游不变量：attribute_memory 当前 producer 填充 measurement_kind/peak_scope/is_peak，但该函数公开导出，可直接传字典，不能推断所有调用者都经过 producer。
- 删除或合并的行为变化：收紧后旧调用方可能从 comparable true 变 not_comparable；这是结论语义变化。
- 验证契约：缺失与冲突元数据矩阵及生产 producer 对照。
- 结论：证据不足

<a id="k-02"></a>

## K-02 · P2 · 重构建议：Stop handoff 的协议、授权、落库和唤醒混合

**仓库：** knowledge

**函数：** `accept_stop`

**行号：** 385-638

**源码：** [knowledge/mindie_knowledge/loop/handoff.py](https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/mindie_knowledge/loop/handoff.py#L385)

**触发场景：** 任意 Stop 入库与后台服务唤醒，包括配置默认、授权恢复、SQLite busy和进程不可用交错。

**证据：** evidence/knowledge-diagnostics-static-candidates.json；K-01；tests/test_capture_handoff.py；tests/test_short_handoff.py；tests/test_capture_wake.py

**影响：** 254行同一函数含61个if/loop/except/ifexp节点（定位指标非标准圈复杂度），同时解释模式、身份、consent、Admission、DB错误和wake结果；K-01说明默认语义在入口与该函数分叉，stage/reason/summary_dropped在大量返回点手工拼装，修改一条业务规则容易遗漏路径。

**修改建议：** 先修K-01，再提取纯 Stop envelope→normalized admission request 和 receipt stage决策；授权读取、真实SQLite提交、wake按当前顺序留在薄编排函数。保持单个提交点和显式已落库状态，不增加新状态机或透传层。

**验证方式：** 纯决策参数矩阵无需mock；真实SQLite+受控进程覆盖重复Stop、撤权与busy、已落库但wake失败、服务ready/unknown；原有外部stage/reason/capture_id完整差分。

**结论确定性：** 高：职责混合和已确认默认分叉；没有把函数长度本身当缺陷。

<a id="k-03"></a>

## K-03 · P2 · 测试有效性边界：本地 summary fidelity 测试不能验证模型摘要忠实度

**仓库：** knowledge

**函数：** `test_multiturn_incremental_transcript_capture_redaction_and_summary_fidelity`

**行号：** 281-284,342-399; tests/material_worker_fixture.py:22-27

**源码：** [knowledge/tests/test_domain_retrieval_and_summary_quality.py](https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/tests/test_domain_retrieval_and_summary_quality.py#L281)

**触发场景：** 提示词/实际宿主模型出现丢失失败尝试、把假设提升成已验证结论、忽略后续纠正等回归。

**证据：** tests/material_worker_fixture.py:1-5 explicitly says cannot claim model quality；tests/test_domain_retrieval_and_summary_quality.py:281-284,342-399；AGENTS.md:Domain retrieval precision/recall & summary quality gate

**影响：** worker对每块返回固定同一title/summary，不分析正文；断言保护原文脱敏、技术词保留、包完整性和引用遍历，无法发现实际摘要失真。现有测试有真实组件价值，应保留；不能据其通过宣称LangMem/LLM摘要质量达标。六篇手造检索语料的Top1也只代表该闭集，不能外推真实语料precision/recall。

**修改建议：** 把本地套件报告标为摘要协议/保存一致性；另设明确人工判据的固定匿名多轮任务质量评测（事实、失败、纠正、归因），记录真实宿主/模型/版本和可复核输出。

**验证方式：** 质量用例能捕获'早期失败被最终成功覆盖'、'未运行检查被写成验证通过'；检索集加入同错误码不同版本/硬负例及无相关答案场景，报告每query标签与Topk命中、误召回。

**结论确定性：** 高：fixture和断言可直接追踪；本轮不调用付费模型，模型质量标未测得。

<a id="k-04"></a>

## K-04 · P2 · 测试基线缺口：live探测将远端执行失败统一skip

**仓库：** knowledge

**函数：** `_ssh_probe`

**行号：** 54-60

**源码：** [knowledge/tests/test_live_npu_knowledge_loop.py](https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/tests/test_live_npu_knowledge_loop.py#L54)

**触发场景：** SSH 已连通但固定容器已不存在、npu-smi命令退化、docker权限/脚本失败，res.returncode非0。

**证据：** tests/test_live_npu_knowledge_loop.py:32-60；.github/workflows/pr-review.yml；docs/testing-architecture.md (architecture repository)

**影响：** 所有非0都记skip，与真正未配置/网络不可达无法区分，发布门禁可以绿但没有执行预期硬件契约。本轮不能把skip视为测得覆盖或证明硬件通过。

**修改建议：** 显式preflight辨识环境不可用；已声明启用且SSH就绪后，业务probe/容器命令失败应fail。把固定host/container转为测试环境配置但保留实际identity记录。

**验证方式：** 受控SSH结果：未配置环境skip；连接成功后命令exit1失败；真实两机输出通过后才继续capture/redaction/recall。

**结论确定性：** 高：静态分支确定；本轮集群可达性由remote审计统一探测，不重复连接。

<a id="np01"></a>

## NP01 · P2 · 已确认缺陷：刷新调度

**仓库：** npu-top

**函数：** `AdaptiveScheduler.heartbeat / _run_loop`

**行号：** 67-77, 168-190

**源码：** [npu-top/npu_top/scheduler.py](https://github.com/mindie-agent/npu-top/blob/8f992bf033af57979d6bebf67189a89bb2034d7e/npu_top/scheduler.py#L67)

**触发场景：** idle周期结束后next_cycle已设为120秒；用户此时打开面板并heartbeat interval=1。

**证据：** 复现真实_run_loop（仅probe/数据库替换本地无IO对象）记录advertised_interval=1，但1.25秒后cycles仍为1。_run_loop虽取interval却未以它调整next_cycle；notify醒来仍等旧next_cycle。tests/test_scheduler.py:15-30只断言getter值。

**影响：** 看板显示1秒刷新但首次自动新采样可能继续等约120秒；fast viewer响应与契约不一致。

**修改建议：** 记录周期完成时间并由当前effective_interval推导到期时间，或在租约加速时将next_cycle提前；避免无条件持续立即轮询。

**验证方式：** 注入时钟/Condition，真实调度循环测试idle→1s、10s→1s、viewer隐藏/过期恢复idle，并断言probe次数与触发时间而非getter。

**结论确定性：** 已确认

<a id="np02"></a>

## NP02 · P2 · 已确认缺陷：live结果新鲜度

**仓库：** npu-top

**函数：** `AdaptiveScheduler.collect_and_wait / _collect_cycle`

**行号：** 100-116, 218-250

**源码：** [npu-top/npu_top/scheduler.py](https://github.com/mindie-agent/npu-top/blob/8f992bf033af57979d6bebf67189a89bb2034d7e/npu_top/scheduler.py#L100)

**触发场景：** 普通不采基础设施的probe已经在途，随后/api/agent/server mode=live发force_infrastructure=True。

**证据：** reproductions.json中live返回include_infrastructure=false，而_force_infrastructure仍含server-1。collect_and_wait只比较current is not previous；api.py:142要求live强制infra；probe.py:682-692普通周期复用旧infra缓存。现有test_scheduler.py:33-57直接写快照绕过实际周期。

**影响：** live请求可以返回旧mount/docker信息并标成新的collected_at，调用方无法凭返回值证明强制探测已完成。

**修改建议：** 使用每服务器请求/完成代次或显式infra采集时间，等待满足本请求能力和代次的结果；勿再增加无业务必要的永久状态机。

**验证方式：** 用Event闸门控制真实_collect_cycle：先起普通probe，再发force请求，释放旧probe必须继续等待；新infra probe完成才返回。增加timeout、停止和并发两个live请求契约。

**结论确定性：** 已确认

<a id="rf01"></a>

## RF01 · P2 · 重构建议

**仓库：** remote-dev

**函数：** `REMOTE_SEARCH_PY / glob / grep`

**行号：** 26-531

**源码：** [remote-dev/remote_dev/core/search_ops.py](https://github.com/mindie-agent/remote-dev/blob/c3af104c36582c675a6dcd368637db7c60b28afd/remote_dev/core/search_ops.py#L26)

**触发场景：** 维护glob、gitignore、grep能力降级、分页及进程流回收时都要修改同一505行内嵌Python字符串。

**证据：** 静态metrics.json；RD01路径缺陷就在此字符串；tests/test_grep_fallback.py:51-71通过python -c运行文本，覆盖无法映射内嵌分支；file_ops已有standalone remote_file_worker模式可参照。

**影响：** 相对路径处理、gitignore与进程管理耦合；难以独立导入验证过滤规则，错误报告和coverage缺少真实行号。

**修改建议：** 把原文本移成独立worker模块，payload dispatch保持一致；提取纯路径/过滤/分页函数与I/O执行，统一base/result路径不变量，保留grep -E支持。

**验证方式：** 先以现有本地真实grep/git与Glob用例做输出契约对照，补RD01；同一worker文件原样上传，验证CLI/MCP回包和异常分类不变。

**结论确定性：** 重构建议；收益有具体证据

<a id="rf02"></a>

## RF02 · P2 · 重构建议

**仓库：** coordinator

**函数：** `CoordinatorService._progress`

**行号：** 629-852

**源码：** [coordinator/mindie_coordinator/service.py](https://github.com/mindie-agent/coordinator/blob/c77144a95dd6af37e978ffc2d8495158b237090d/mindie_coordinator/service.py#L629)

**触发场景：** 任务恢复和取消需要同时维护执行phase、roles、binding、assignment以及远端session/lease/job状态。

**证据：** _progress 224行、33个AST决策候选（非正式McCabe）；629-651做会话/源校验和持久化，655-723放置/准备/绑定，725起源物化，后续提交与终态归并。_place_or_prepare 918-923与_progress679-690两次读取catalog核验，存在I/O时间差而非可直接删检查。

**影响：** 恢复点与副作用、状态投影分散，单一修改容易绕过取消或重复prepare；单测必须构造整套service/pool才能覆盖决策。

**修改建议：** 先抽纯“观察结果→下一动作/对外phase”决策，保留当前持久化边界和调用顺序；将角色准备/绑定、运行观测分别做少量内聚函数，不引入额外状态机。

**验证方式：** 复用InMemoryHostQueue与真实SQLite场景：取消发生在prepare/activate/go间、重启恢复、一个role失败另一role排空、成功结果遇本地记录失败；逐一对比状态与远端调用不重放。

**结论确定性：** 重构建议；未认定重复catalog检查可删除

<a id="adp-07"></a>

## ADP-07 · P3 · 等价清理候选：重复纯校验

**仓库：** mindie-agent-cc

**函数：** `publish_bind`

**行号：** 217-220,253-255

**源码：** [mindie-agent-cc/scripts/identity.py](https://github.com/mindie-agent/mindie-agent-cc/blob/78f34dd9b09e877298225fa243ea4c28978c9dd6/scripts/identity.py#L217)

**触发场景：** publish_bind合法tool_name且数据库已有该ID，进入已有行分支。

**证据：** repos/mindie-agent-cc/scripts/identity.py:217-218；repos/mindie-agent-cc/scripts/identity.py:253-255

**影响：** 完全相同parse_native_tool(tool_name)重复执行；中间没有改写tool_name，纯解析只读模块常量。额外分支不能保护额外风险，增加维护与覆盖负担。

**修改建议：** 删除253-255第二次校验，保留入口校验、绑定冲突/摘要/状态检查。

**验证方式：** 现有合法重绑定与ambiguous业务测试保持；先检查parse_native_tool纯函数及tool_name不变，再以静态差异审查，不为删除两行另写类型填充测试。

**结论确定性：** 已确认可等价清理

**防御性代码审查**

- 保护风险：拒绝非本插件MCP工具名称。
- 风险是否存在：输入风险真实，但同次调用已验证。
- 上游不变量：本函数217-218先验；至253行tool_name未修改，parse_native_tool不依赖I/O。
- 删除或合并的行为变化：正常和失败行为均保持，仅少一次重复解析。
- 验证契约：既有publish_bind首建、重复、冲突用例。
- 结论：建议删除或合并

<a id="b05"></a>

## B05 · P3 · 兼容分支待验证

**仓库：** mindie-bench

**函数：** `consumer`

**行号：** 58-74

**源码：** [mindie-bench/src/mindie_bench/integrations/first_party.py](https://github.com/mindie-agent/mindie-bench/blob/b7301839602ad3791af17f21f5aa47d773b5af2a/src/mindie_bench/integrations/first_party.py#L58)

**触发场景：** 对内部MaterialStore用hasattr判断_pointers/refresh_index，缺失时重新安装或跳过刷新。

**证据：** knowledge main@021ba95e和插件pin@4e328305均实现store.py:275 _pointers与:795 refresh_index；bench通过外部选定组件解释器调用，pyproject未声明knowledge最低版本。tests/test_first_party_mcp.py:120-145的BrokenInstall桩缺少_pointers，实际走了fallback。

**影响：** 不支持的组件或失真测试桩可能被静默接受，遗漏索引刷新；目前证据不足以证明所有正式允许的外部版本都具备这两个方法。

**修改建议：** 先把允许的组件能力/版本写入公开契约并验证安装身份；若只支持已核对版本，直接调用并删hasattr fallback，测试桩同步满足契约。

**验证方式：** 真实pin与main MaterialStore分别执行安装→检索→热刷新；不满足契约的旧组件在入口透明拒绝；失败清理不得覆盖原始错误。

**结论确定性：** 中；两个已扫描knowledge版本满足，但完整支持矩阵未声明

**防御性代码审查**

- 结论：证据不足
- 保护风险：运行时选择了不含两个方法的旧组件
- 风险是否存在：可配置任意组件解释器，但未找到完整支持范围；不能仅凭当前main判断风险不存在
- 上游不变量：两个核对SHA有实现；bench入口尚未明确约束最低能力
- 删除或合并的行为变化：删除后旧对象将AttributeError；须改为入口不兼容错误并清理资源
- 验证契约：支持矩阵真实组件契约测试+不支持版本显式失败

<a id="d-04"></a>

## D-04 · P3 · 等价重构建议：同一 label 重复扫描

**仓库：** diagnostics

**函数：** `_label / _project`

**行号：** 68-73,159-160,187-190

**源码：** [diagnostics/mindie_diagnostics/bundle.py](https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/mindie_diagnostics/bundle.py#L68)

**触发场景：** 导出含合法静态 label 的事件。

**证据：** evidence/diagnostics/probes.json:clean_label_scan；mindie_diagnostics/redact.py:scan_text,redact_text；tests/test_bundle.py；tests/test_redact.py

**影响：** clean label 'completed' 24 条规则执行48次 spans；属性分支调用_label两次，再重复一次完整验证。每个合法 label 多做纯确定性正则遍历，增加热路径开销和双实现一致性维护成本。未给出未测的总延迟收益。

**修改建议：** 先局部缓存 _label(value) 结果，避免159-160重复调用；再经差分证明以一次 scan_text 判定是否拒绝 label，保留最终 canonical event 出口扫描与白名单。

**验证方式：** 现有隐私 fixtures 全量差分：旧/新返回完全相同；对clean、credential、allowlist、overlap、IPv6/版本等输入验证。真实batch benchmark测量耗时；不以调用次数本身作为唯一业务测试。

**结论确定性：** 重复计算高；单次scan_text等价替换需先差分验证两个独立扫描器的边界差异。

**防御性代码审查**

- 保护风险：禁止敏感或自由文本进入公开 label。
- 风险是否存在：真实外部事件边界风险仍存在，必须保留验证。
- 上游不变量：在同一次_project中 value 是相同不可变 str；redact_text与scan_text纯函数零I/O，159-160没有中间状态变更。
- 删除或合并的行为变化：缓存同一_label结果无正常/失败语义变化；只合并计算，不放宽白名单或发布门禁。
- 验证契约：隐私fixture差分和完整公开payload无敏感内容断言。
- 结论：建议删除或合并

<a id="d01"></a>

## D01 · P3 · 等价冗余清理

**仓库：** coordinator

**函数：** `ManagedExecution.watch_completion.watch`

**行号：** 356

**源码：** [coordinator/mindie_coordinator/managed_execution.py](https://github.com/mindie-agent/coordinator/blob/c77144a95dd6af37e978ffc2d8495158b237090d/mindie_coordinator/managed_execution.py#L356)

**触发场景：** 完成观察线程判断当前job是否还running。

**证据：** JOB_TERMINAL在43行不包含running；条件 A in JOB_TERMINAL or A != running 中前半蕴含后半；该集合是本模块实际运行时定义，非仅类型注解。

**影响：** 无已知错误；重复状态谓词提高阅读成本。

**修改建议：** 保留job[state] != running即可；不要同时删除后续observed unknown/quiet检查。

**验证方式：** 已有test_completion_dispatch / test_owned_completion运行回归；对running继续等待与非running立即退出验证可复用既有用例，不新增枚举字符串凑数测试。

**结论确定性：** 已确认

**防御性代码审查**

- 结论：建议删除或合并
- 保护风险：终态任务不再开启完成长轮询
- 风险是否存在：真实风险，但!=running已覆盖全部终态
- 上游不变量：managed_execution.py:43运行时JOB_TERMINAL集合与356条件的逻辑蕴含
- 删除或合并的行为变化：所有现有状态输入下返回和等待行为不变
- 验证契约：完成观察回归，不涉及外部错误语义

<a id="d04"></a>

## D04 · P3 · 兼容逻辑待验证

**仓库：** npu-top + remote-dev

**函数：** `_env / glob fallback`

**行号：** settings:15-21, 80-99; search:316

**源码：** [npu-top/npu_top/settings.py](https://github.com/mindie-agent/npu-top/blob/8f992bf033af57979d6bebf67189a89bb2034d7e/npu_top/settings.py#L15) · [remote-dev/remote_dev/core/search_ops.py](https://github.com/mindie-agent/remote-dev/blob/c3af104c36582c675a6dcd368637db7c60b28afd/remote_dev/core/search_ops.py#L316)

**触发场景：** 考虑删除NFM_*旧变量别名，或因本地requires-python>=3.11删除远端Python3.9 glob兼容。

**证据：** Settings明确MINDIE_TOP优先于NFM，tests/test_settings_mindie.py验证两套配置；remote README只写容器需python3/bash，未给远端最低版本；pyproject>=3.11约束安装端，不自动约束远端目标。

**影响：** 缺部署清单/停用版本证据；删除可能使旧配置失效或某些远端机器无法工作。

**修改建议：** 先确认支持矩阵、配置迁移和退役期限，再决定删除；不要仅按本地解释器版本删除。

**验证方式：** 已声明受支持环境/客户端配置矩阵，真实旧变量优先级和目标Python最低版本试跑。

**结论确定性：** 证据不足

**防御性代码审查**

- 结论：证据不足
- 保护风险：旧配置用户或较老远端Python继续使用
- 风险是否存在：代码与文档仍呈现支持，但无活跃部署统计
- 上游不变量：本地requires-python不提供远端版本不变量；没有退役契约
- 删除或合并的行为变化：删除可能选回默认状态目录/端口或远端glob失败
- 验证契约：支持矩阵与迁移契约先行，后做配置/远端版本行为验证

<a id="k-05"></a>

## K-05 · P3 · 等价重构候选：查询边界重复解析continuation

**仓库：** knowledge

**函数：** `Store.query`

**行号：** 1144-1170; materials/store.py:760-762; materials/provenance.py:36-50

**源码：** [knowledge/mindie_knowledge/loop/store.py](https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/mindie_knowledge/loop/store.py#L1144)

**触发场景：** Store.query 的每次合法查询，尤其携带最多24KiB的continuation时。

**证据：** mindie_knowledge/loop/store.py:1147；mindie_knowledge/materials/store.py:762；mindie_knowledge/materials/provenance.py:36-50；tests/test_material_query.py

**影响：** 入口query_request解码/验证结果被丢弃，MaterialStore.search再次做同样工作。第一层保证坏输入在触碰material之前失败，不能简单删掉后将输入错误延迟到I/O之后。

**修改建议：** 保留两个独立公开入口验证，用局部规范化请求对象或私有已验证search路径在内部调用时复用；仅在性能测量证实收益后推进，不为省几次类型检查新增公共抽象。

**验证方式：** 无效/过期/跨查询continuation必须在读取或修复索引前失败；真实pagination结果和错误类型保持不变。

**结论确定性：** 重复计算高；重构收益中，排在正确性与测试补缺之后。

**防御性代码审查**

- 保护风险：坏查询触碰/修复material以及非法continuation。
- 风险是否存在：真实外部输入风险，两个公开API均需防护。
- 上游不变量：Store.query在1147已完成同一query_request，至1170未改变参数；MaterialStore.search又可独立被外部调用。
- 删除或合并的行为变化：规范化内部请求复用应无变化；直接删除外层会改变错误发生顺序，不是安全等价删除。
- 验证契约：坏输入零I/O与合法/过期pagination契约。
- 结论：建议合并内部重复处理，保留公开边界校验

## 补充：应保留或证据不足的边界防御

### KD-R1 · 有明确依据应保留

仓库：diagnostics；位置：`mindie_diagnostics/reporter.py:521-550; reporting.py:54-79`

- 保护风险：用户在GET到POST间撤销贡献授权；磁盘策略暂不可读与显式撤权不能混为一谈。
- 风险是否存在：当前插件明确支持随时撤权、不同profile独立授权，跨进程外部状态可变化。
- 上游不变量：最早require_consent只证明检查时刻；GET/I/O之后无任何不变量能保证授权没变。guard_consent/check_remote_action在真实远端动作前重读，不能因重复而删。
- 删除的行为变化：删除会允许检查后撤权仍发POST；把unavailable视withdrawn会丢失待发证据。
- 验证契约：tests/test_authority_outcomes.py、test_reporting_consent.py使用真实policy/SQLite，模拟读取故障、显式撤权并断言请求次数、队列state和payload保留。

### KD-R2 · 有明确依据应保留

仓库：diagnostics + knowledge；位置：`mindie_diagnostics/reporter.py:542-579; mindie_knowledge/materials/summarizer.py:SummaryLedger; mindie_knowledge/community/publish.py:_resolve_unknown:833`

- 保护风险：付费模型/创建Issue/创建PR已发生但连接中断或本地回执写入失败，盲目重试重复付费或发布。
- 风险是否存在：确有不可逆外部写；本地SQLite失败不证明远端未执行。
- 上游不变量：子进程started并不证明completed/failed；仅明确not_started或远端marker reconciliation能收敛未知。
- 删除的行为变化：删除unknown状态或把本地记账失败映射成远端失败会破坏幂等和效果诚实性。
- 验证契约：真实SQLite加边界transport double覆盖lost-response、已确认成功但receipt commit失败、重启重对账，断言只POST一次、已保存LLM结果只本地重用。参考tests/test_reporter.py:48-65、knowledge/tests/test_summary_attempts.py/test_summary_recovery.py。

### KD-R3 · 有明确依据应保留

仓库：knowledge；位置：`mindie_knowledge/materials/store.py:_parse_block:166,validate_package_files:178,read_current:430-476; materials/reme_index.py:StrictFileStore.load:113`

- 保护风险：外部Git包或可写本地Markdown/派生checkpoint损坏，返回并非当前引用绑定的正文。
- 风险是否存在：材料文件可跨进程更新，索引是可重建派生数据，类型正确不证明字节digest/当前membership有效。
- 上游不变量：入口验证只证明当时的快照；当前manifest和read_ref可能已换代，不能用类型注解或先前校验豁免。
- 删除的行为变化：删除读时membership/hash校验可把过期引用重定向至别的正文，或把坏索引当成可信结果。
- 验证契约：test_block_read.py、test_feed_query_visibility.py、test_incremental_resources.py、test_material_packages.py使用真实文件/SQLite，改写、删除、换代后必须显式失败，不静默返回旧/空数据。

### KD-R4 · 有明确依据应保留

仓库：diagnostics；位置：`mindie_diagnostics/fallback.py:record_failure:302-369; integration.py:record_failure:185-266`

- 保护风险：正在报告业务异常时日志磁盘/锁/格式再次失败，诊断代码覆盖原始异常。
- 风险是否存在：诊断属于旁路、可独立被共享组件调用；AGENTS明确never raises into callers。
- 上游不变量：上游不保证诊断存储始终可用；record_failure返回recorded=false/logging_failed=true/error并有一次stderr提示，不是假业务成功。
- 删除的行为变化：移除catch会用诊断异常替换原始业务异常；不应将这个有可观察失败标志的旁路同吞错返回业务成功混为一谈。
- 验证契约：test_integration.py、test_logging.py和fallback recording failure tests，必须同时保留原业务结果与logging_failed可见性。

### KD-R5 · 证据不足

仓库：knowledge；位置：`mindie_knowledge/materials/store.py:195 package_from_files alias; loop/store.py:533 advance_search_index(**_budgets)`

- 保护风险：兼容外部Python用户或旧调用者。
- 风险是否存在：全组织扫描只有无参数advance_search_index调用；package_from_files列入materials.__all__。没有调用不证明公开API无人使用。
- 上游不变量：没有发布兼容清单可证明可删除公开alias/kwargs。插件注册与动态导入已检查，未发现显式kwargs传入。
- 删除的行为变化：删除会让旧Python调用方ImportError/TypeError；接受预算却忽略也会误导调用者，但本轮未发现实际预算调用链。
- 验证契约：先确定支持版本/公开契约，锁定调用者后做跨仓安装与API smoke，再考虑移除。

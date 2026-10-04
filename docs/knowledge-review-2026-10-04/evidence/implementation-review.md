# 实施阶段证据与九原则审查

本文保留 Stage1–4 的历史记录；其中“当前”及“剩余边界”均指该阶段观察时点。后续新合成目录授权及公开链路成功见 [Stage5 验收与九原则审查](stage5/review.md)，未改写此前的未授权或未验收事实。

日期：2026-10-04，最终部署回读于北京时间 10 月 5 日。此文区分初始研究、真实材料索引与检索、独立 profile 的纯合成原生验收，以及后续合入、正式安装、Grok 配置和公共 GitHub 消费验收。各阶段保留实际版本和失败；公开 Stop→PR→Grok 事件审查合入仍未验收。阶段、原始快照和当前文件 SHA256 见[证据清单](manifest.json)。

## 版本与实际边界

| 对象 | 本阶段版本或依据 | 能证明的范围 |
| --- | --- | --- |
| knowledge | `929bdcb918f2207aea38b02a14bd8e6219fabac4`，[PR59](https://github.com/mindie-agent/knowledge/pull/59) | 任务材料包、真实 ReMe 检索、LangMem 增量索引与可见失败；Linux、macOS、Windows 和包检查均通过；PR59 已合入 `250fcc9d497989864e2429d422d6c2c79e4d5e71` |
| Codex | source `783190bac5c387ea3f6918e14d56c7eaaedb09eb`，[PR18](https://github.com/mindie-agent/mindie-agent-codex/pull/18) 合入 `f35ab6f6bc38e1a33d33bcfccc98c828feb9c041` | 固定 core `929`；Linux/Windows 各 310 tests 通过，分别 12/6 skipped；merge 与 CI checkout tree 一致；正式插件及依赖已安装并正常信任 Stop |
| 内容仓库 | source `55ac4704d77a7423a06d8cda8d8403b42ac5af4a`，[PR37](https://github.com/mindie-agent/knowledge-vllm-ascend/pull/37) 合入 `5273638c81f55cc8b1423d887b6859d51d6f3621` | 固定 validator `929` 的 20 条公开内容转换；合并后自动工作流实际校验 20 entries / 1 feedback；正式 owner 与独立 HTTPS 消费者均同步精确 main |
| 实际原生验收版本 | Codex `351e9f8aeb422c879fef382d3c9aea784a6008ae` / core `d07934b6ff6510d9d666c30560e3aa072a75ce60` | 独立 profile、纯合成任务、正常 Stop 到本地 Git 独立消费；正式配置、公开 GitHub/Grok 与 OS 调度不在该验收内 |
| 原则依据 | 当前主工作区 `docs/design-principles.md`；Git blob `9b21e6ae87ac96ff8bdacc3f4f546384e111a184`，SHA256 `15b4b58385846051464c27d06922ad0353bdd6a4031b619ff248c3a65c179741` | 包含第 9 条和开发 PR review 的当前实际文本，不只引用旧 HEAD |

ReMe 固定为 `4c54c2b650038eff2a5d0d77aaa61b3e836f1b18`，实际使用其 Markdown chunker、LocalFileStore、FileGraph、BM25 和派生缓存，不启动默认 Application、jobs、watcher、模型、embedding 或 tags。读取和持久化错误通过窄覆盖到达调用者。技术标识符分词保留 API basename、版本及中文词项。规范包、Git 哈希、候选文件与已提交元数据的事务衔接仍由 MindIE 承担，不能归称为 ReMe 原生事务。

最后复查在此前 core `ec5f33e9d6a329c0fb48cea67cba66113e70a5b9` 复现一项原始字节完整性缺口：本地 Markdown 通过 `Path.read_text` 读取时会隐式归一换行，实际文件字节变更可能未使 export/ReMe 前置校验失败。该问题已在 `0fa011701f4d73f40709df56c969cc3492eb8fab` 修复：6 处 Markdown 读取/比较及 ReMe 前置读取改为原始字节读取后显式 UTF-8 decode，JSON 行为保持不变。block/manifest 的 CRLF 字节损坏现在令 get、export、search、reinstall 明确失败，current 指针与缓存不推进。受影响测试 **52 项通过**，另 **1 项 Windows 长路径 fixture 定向通过**；这些局部结果不替代该新提交的远端 CI。

LangMem `0.0.30` 的函数处理完整新增块及已有短导航；单块至多 16 KiB，每批至多 8 块，序列化用户 prompt 至多 64 KiB。该限制不截断整个任务，也不是包含宿主上下文的总 token 或货币费用硬上限。正文保持普通 Markdown，SQLite 只保留小元数据和操作回执。旧 FTS、全文重写 organizer 和历史兼容恢复路径已删除。

Worker、调用回执、原生适配及其精确测试版本见[专门审查](organizer/implementation-review.md)。其中 303 项本地全套测试使用 core `9dba4d46dda5b798dd27fdf207262c3ad98f7339`，12 项平台相关跳过；后来在 core `f72445403fe9069f0abaa224306943e7de608500` 上完成 26 项启动、feed、失败可见性和安装 pin 定向测试。没有把前一版本的全套结果改记为最后版本全套通过。 Codex `35ab330` 的 core `929` 精确安装、preflight 及 installed-runtime 单测 1 项通过（2.866 s）；此前 `493/f246` 的相应单测为 2.903 s。没有把这些定向检查写成前述 303/26 项在最终版本重新通过。

已取得的远端 CI 局部结果绑定 PR head `f72445403fe9069f0abaa224306943e7de608500`，三个 job 的实际 checkout 均为 PR merge commit `9de371bf3369d434e7176fba3fac088b2881bf13`，合入 base `2637ffa848c0a44bde38ee488112150ee9bc0743`。日志确认如下；Windows 在该版本暴露 CRLF 包契约失败。后续 `ec5f33e9d6a329c0fb48cea67cba66113e70a5b9` 已修复受管 Git checkout 的换行恢复和 checkout/diff 失败可见性；后续 head 的结果不能沿用此表。

| 远端 job | 实际结果 | 耗时 |
| --- | --- | --- |
| Ubuntu contracts | 622 passed、9 skipped、1 warning | 311.54 s |
| macOS contracts | 622 passed、9 skipped、1 warning | 446.09 s |
| Package checks | 622 passed、9 skipped、1 warning | 391.74 s |

随后 `ec5f33e9d6a329c0fb48cea67cba66113e70a5b9` 的 Windows 运行在 110 passed、23 skipped 后暴露原始 Git fixture 的长路径问题；对应 fixture 已随 `0fa011701f4d73f40709df56c969cc3492eb8fab` 修正。此计数是失败前已观察范围。`0fa011701f4d73f40709df56c969cc3492eb8fab` 随后的三个成功 job 均实际 checkout PR merge commit `795fb780c1c9b8532de649cbab518f24a70b03f3`，仍以 `2637ffa848c0a44bde38ee488112150ee9bc0743` 为 base：Ubuntu 为 632 passed、9 skipped、1 warning（376.59 s），macOS 同计数（348.61 s），Package checks 同计数（241.85 s）。[Native run](https://github.com/mindie-agent/knowledge/actions/runs/37204003398) 与 [Package run](https://github.com/mindie-agent/knowledge/actions/runs/37204003419) 绑定该 head；这些成功不覆盖后续版本。Windows 在 117 passed、23 skipped 后因 `test_submit_happy_path_real_git` 的验证 clone 路径过长失败，生产提交步骤此前已成功。测试 helper 的命令级 `core.longpaths=true` 修复完成了 3 项本地定向测试（2.97 s），该单行 fixture 修复已提交并推送为 `f246baea38247ed9c09e4c62d3d769717378f5b2`，生产源码与 `0fa` 相同；该 head 的 Windows CI 随后在 10 MiB Kimi 夹具失败：慢初始化让合成消息时间早于捕获授权边界，真实 parser 因而过滤该消息。受控的 3 秒初始化延迟复现了该问题；`de8d756b8bcdbbdb2e6df334a0b5c4404d1a31f5` 修正夹具边界，9 项大材料与 10 项 lineage/corruption 测试通过。它与此前 Git 长路径问题及下述事件回执缺口是不同问题。

## 后续捕获回执与错误可见性修正

此前 core `915d3356a25f4197927e35b3f74f7c4592a67244` 包含下述两项生产修正。当时 Codex 和内容候选仍固定 `f246`；这条历史边界保留在清单，最终合入版本以上表及后文当前 CI 为准。

`460dfda1e41018befbdc3b57996977cbefa3ed75` 统一开发 FileTransport 的 Git 长路径与换行参数，并使每一步的超时和退出失败可见。push 前读取并校验 commit，避免之后的读取失败掩盖已完成的外部写入；push 超时仍是 `UnknownOutcome`。这项改动完成 5 项定向测试（4.86 s），并不证明 GitHub 或 Grok 的完整链路。

随后发现一个真实的状态错误：同一捕获事件在页首保存了公开正文，后续页只剩被过滤的尾部噪声，最终 EOF 却被报告为 `no-new-material`。正文没有丢失，终态丢掉了较早页面已保存材料的事实。`915d335` 在既有 state 表保存小型事件回执，与正文和游标同事务提交；EOF 按回执恢复已保存结果，继续处理时的错误则独立保留。损坏的回执明确成为故障，不能被解释为没有材料。

实际诊断调用入口只读投影安全引用和固定故障字段，出现损坏回执时给出 degraded 状态与提示；它不读取正文或重新运行捕获。此修复没有增加数据库 schema、自动重试或正文历史。主任务报告定向验证分别为捕获等相关 75 项通过（48.12 s）、新增调用者/捕获 16 项通过（5.56 s）及 diagnostics 28 项通过（0.63 s，1 项已有 warning）。这些分组可能重叠，不累加为一个全套结果。本次文档复查读取了精确提交的实现 diff，没有重跑模型或全套测试；这些调用入口检查也不代替已安装插件的原生 Hook 验收。

`915d335` 的 Windows CI 后来在 181 passed、23 skipped 后遇到另一个冲突分类问题：远端任务路径含换行时，在包结构校验前就执行 checkout，结果报告 `failed` 而非 `needs_review`。`e13b77b83db9aebf5c2904253565eac633373ca7` 已提交并推送，改为 `clone --no-checkout` 后先检查精确 Git object 的任务路径和文件 mode，再允许 checkout；不支持的包结构保持 `needs_review`，不会触发远端写入。测试夹具使用真实 Git symlink mode `120000`，避免依赖 Windows 主机创建 symlink。五个变更文件的相关测试 93 项通过（36.29 s），本次复核读取了原始测试结果日志及提交 diff，没有重跑。这是 `e13` 阶段的修正及验证，不代表后续 head 的 CI 结果。

## 当前 CI 与后续平台 fixture 修正

core `929bdcb918f2207aea38b02a14bd8e6219fabac4` 的四个成功 job 实际 checkout 为 PR merge commit `f8b41e495987fddff9af060f9a2953d747b7eeee`，base 为 `2637ffa848c0a44bde38ee488112150ee9bc0743`。以下是该 head 的完成结果，和前述旧 head 分开保存；这组 CI 通过仍不证明正式部署或公共分享链完成。PR59 已于 2026-10-04 15:30:06 UTC 正常合入 `250fcc9d497989864e2429d422d6c2c79e4d5e71`；内容与适配器继续引用已验证、可达的源 head `929`，不为合并节点重复安装或调用模型。merge 的两个 parent 为上述 base 与 `929`，Git tree `b979562ef2c9d827d10661d1f1cba55f076db71b` 与已测 `f8b` 完全相同；合并后触发的 main CI 是另一轮运行，本记录不将其状态推断为完成。

| job | 当前结果 | 耗时 |
| --- | --- | --- |
| [Ubuntu contracts](https://github.com/mindie-agent/knowledge/actions/runs/37211768332/job/111464222653) | 651 passed、9 skipped、1 warning | 233.50 s |
| [macOS contracts](https://github.com/mindie-agent/knowledge/actions/runs/37211768332/job/111464222820) | 651 passed、9 skipped、1 warning | 433.19 s |
| [Package checks](https://github.com/mindie-agent/knowledge/actions/runs/37211768330/job/111464222832) | 651 passed、9 skipped、1 warning | 254.19 s |
| [Windows contracts](https://github.com/mindie-agent/knowledge/actions/runs/37211768332/job/111464222922) | 631 passed、29 skipped、1 warning | 1,218.20 s |

`e13` 后的修正依次处理合成材料时间必须落在初始化后的授权范围（`5a93c8e`）、feed 保留测试的原始 Git 长路径（`d07934b`）、1,027 任务 fixture 的 Git add/commit 写入预算及本地 LF 设置（`d1b9549`）、PID 文件空窗竞态（`4f59b66`）和材料 fixture 的显式 UTF-8 读取（`929bdcb`）。这些都是测试修正；`d079` 到 `929` 只有三个测试文件改变，没有生产代码、依赖或模型行为变化。Windows 在旧 head 暴露的失败和当时已运行计数仍作为旧阶段回执保留，不挪作最终通过证据。

Codex PR18 的首次两平台 CI 在精确依赖 preflight 通过后，均因 `test_failure_visibility` 读取干净 runner 上不存在的本机 updater settings 而失败：Linux 128 tests、1 error、11 skipped（58.036 s），Windows 128 tests、1 error、0 skipped（148.149 s）。实际 checkout 为 `ddbcc61af9e180c03426015b08ab6ab00407d469`。`4f7df1355b59618d3a94ee4c97843a6f0b67fd19` 仅修临时 settings/显式 argv fixture 和测试运行器汇总，原四种非零断言、每项执行一次和最终失败退出不变；本地 9 项通过（0.069 s）。其 [CI 37212849968](https://github.com/mindie-agent/mindie-agent-codex/actions/runs/37212849968) Linux 308 tests、12 skipped 通过（164.464 s），Windows 308 tests、1 failure、6 skipped（318.686 s）：正文已 imported，必要 service 启动却出现 PermissionError。该旧日志不足以确认具体 Win32 失败调用。

`14afcba4aca606931164525f353d691b12449a1c` 使 Windows 历史导入复用既有显式 service-launcher Job 边界，提供安全 stage/errno/winerror，并保留原退出/中断和已完成导入，不让清理错误覆盖它们。本地 17 项、4 项平台跳过通过（17.579 s）。该阶段 Linux 310 tests、12 skipped 通过（168.462 s）；Windows 历史导入及 service 用例通过，但整体 310 tests、1 error、6 skipped（335.939 s），错误来自 PowerShell 测试外层 5 秒 watchdog。日志不能定位哪层启动占用了这 5 秒。

最终 `783190bac5c387ea3f6918e14d56c7eaaedb09eb` 只将 host-shell 测试外层 watchdog 改为生产预算加 10 秒；生产 Hook 5 秒、Windows bridge 1.3 秒均未变。本地 12 项、6 项平台跳过通过（0.218 s）。[最终 CI 37214668022](https://github.com/mindie-agent/mindie-agent-codex/actions/runs/37214668022) 实际 checkout `832c3f32f34104e53c436495be77ff8842c33241`，parents 为 base `33de36945e6dd448104c42b7fa49639b00f8ff58` 和 source `783190b`：Linux **310 tests、12 skipped、OK（158.035 s）**；Windows **310 tests、6 skipped、OK（334.011 s）**，真实 history-service 与 PowerShell 输出隔离用例均通过。这是协议/组件验证，不证明生产 Hook 的冷启动 SLA。PR18 正常合入 `f35ab6f6bc38e1a33d33bcfccc98c828feb9c041`，tree `17772e776d1b75bcb52683367c1a0974835c4a7c` 与已测 checkout 相同。四阶段 CI 的原始结果见[匿名汇总](codex-final-ci.json)，没有将旧失败或 `35ab` 精确安装单测改记为新运行。

随后 core [PR60](https://github.com/mindie-agent/knowledge/pull/60) 仅改 `community-sharing.md` 与 `repository-bot-contract.md`，正常合入 `4d9b870dad9c223bec6aecbc9c3c24f7b896661e`。它对齐 entry/3、task/1、block/1、完整 manifest、不可变块替换、exact-base 冲突和整包删除。该文档提交的自动 Windows/macOS CI 失败于未改动的 10 MiB Kimi 夹具 8 秒 queued 等待，具体原因未证实；不能称为全部 CI 通过。生产 tree `41061aaba05e0abb42764194d1929f18f52499af` 与 tests tree `0a3c6bc9285cc00ff1e4e2911264d41c6a39af69` 均和已验证 `250fcc9` 相同；文档 diff 检查通过，无 required branch checks，按精确 head 正常合入，没有 admin 绕过。运行时 pin 保持 `929`，不为文档变更重跑模型。

## 纯合成原生 Stop 到独立本地消费

[匿名原生回执](native-local-acceptance.json)绑定实际版本 Codex `351e9f8aeb422c879fef382d3c9aea784a6008ae` / core `d07934b6ff6510d9d666c30560e3aa072a75ce60`。受信任的正常 native Stop 经现有桥接和队列得到 1 个 organized capture、1 个 complete summary；一次 `gpt-5.6-luna` / low 索引耗时 12,857 ms，8,835 input / 232 output tokens，cached input 为 0。正文采集不调用模型。

本地 outbox 提交的是本地 Git 测试 PR 1，**不是公共 GitHub PR**。精确 head/main `da8d1cfa0e98702436108eff6300d7b90ca5442f` 的校验为 1 entry、0 feedback、2,876 bytes，共 2 个任务文件、1 个块。消费者通过既有 `auto_update.py check` 一次正常调用同步该版本；没有直接写 Store/feed，也没有安装 OS 定时器。随后独立原生消费者取得 1 个 feed-origin、非 supplemental 结果，explain 读取同一引用的 238 字符完整正文，保持“先按 2 个 shard，后来更正为 4 个，硬件结果仍未验证”。消费者 captures、material batches、tasks、summary attempts 和 outbox 全为 0，分享配置与授权记录均不存在。

失败尝试分别保留：第一次 producer 继承父进程身份，Stop 在采集前以 `identity_mismatch` 拒绝；清除私有启动器的继承变量后创建新的独立原生任务，没有伪造宿主身份或手工重放 Stop。第一次 consumer 的测试准备遗漏了既有同步 owner，空结果保持为失败尝试，补走正常更新入口后才取得有效查询。

该正常更新调用发现真实产品问题：feed 已 synced，但本地 file-only plugin 检查为 `check_failed`，CLI 却退出 0。Codex `801d2b4b8020c9d6893f4d3db3d103c445da3e49` 将该状态加入既有失败集合；回归修复前失败，修复后 13 项 update-recovery 测试通过（1.414 s）。实际 CLI 复核退出 1，feed 为 unchanged、plugin 仍为 check_failed；不把整个 updater 写成成功。首次正常 check 完成同步，随后一次显式的修复版 check 验证 feed unchanged 与非零失败；没有安装、自动重试或额外模型调用。

原生业务任务本身的用量另列，不计作索引开销，也不混入后文历史 35 次调用。cached input 和 reasoning output 分别已包含在 input/output 总数内，不能相加重复计费。

| 独立业务任务 | input | cached input | output | reasoning output |
| --- | ---: | ---: | ---: | ---: |
| 首次 producer，身份拒绝 | 124,751 | 96,256 | 636 | 194 |
| 第二次 producer，采集成功 | 93,430 | 67,840 | 436 | 117 |
| 首次 consumer，未同步 | 133,336 | 119,552 | 581 | 126 |
| 第二次 consumer，查询成功 | 128,894 | 98,304 | 811 | 160 |

验收后停止 2 个拥有的服务，移除 2 个临时 plugin、2 个 marketplace 和 2 个精确 hook trust 记录；拥有的服务与缓存目录剩余均为 0。清理仅涉及临时作用域，正式 plugin 设置保留，独立证据配置留存。该验收不覆盖公开 GitHub 业务贡献、Grok、正式部署、OS 定时器、超长会话质量基准或真实硬件。

## 真实材料测量

依据是 core 固定提交中的[匿名 K3 验收 JSON](https://github.com/mindie-agent/knowledge/blob/0fa011701f4d73f40709df56c969cc3492eb8fab/tests/fixtures/k3-system-acceptance-2026-10-04.json)，文件 SHA256 为 `97de7962f717c7db83ff884488c1537c6c38ae7ebb6efcf08b9205cb54da93c4`。只复核公开计数和结果，不把真实 transcript 复制到本证据目录。此提交绑定的是匿名测量记录，不表示后来的平台修复又重放了全部真实模型调用。

| 检查 | 实际结果 | 解释边界 |
| --- | --- | --- |
| 选定历史材料 | 4 个真实 K3 任务，81 个块全部建立索引 | 仅这 4 个显式选择的快照，不代表任意私有材料均可公开 |
| 指定小模型 | `gpt-5.6-luna` / `low`，35 次原生 worker 调用 | 计数是 native invocations，不是独立观测到的提供商内部请求数 |
| 用量 | 658,424 input tokens、33,219 output tokens；unknown calls 为 0 | 原生回执的实际 token 计数，不推断货币价格 |
| 本地检索 | 12/12 个任务目标查询找到相关任务，均有正文片段 | 特定目标查询检查，不是通用召回率或语义质量认证 |
| 独立消费者 | 本地 Git 文件协议获取 4 个任务包，12/12 查询命中，0 次模型调用；重复同步 unchanged | 尚不等于 GitHub 传输、Grok 收件或合并验收 |

35 次调用包含失败 attempt 34：3 个源块返回了 4 个索引，其中 1 个重复；该次已知 22,077 input / 1,483 output tokens 保留在累计量中，没有被重置为未调用或自动重试。输出 schema 随后约束精确数组长度，仍保留身份和顺序校验；显式 attempt 35 后完成全部 81 块。这个失败及修复不能证明以后所有模型输出都正确。

## 公开内容的一次转换

内容源提交 `9aab5e1e2f1298f992b1b41e403c2b1e0232d12c` 的 20 条现有公开条目转换为 20 个任务包、22 个块。按清单逐项核对原文件、正文、新 manifest 及 revision 的哈希；拼接块正文精确重现 110,289 字节，包括原有最终换行。标题、摘要、conditions 和 entry ID 沿用，唯一反馈文件字节不变，投票仍属于原 revision。

转换没有模型调用；`status: complete` 仅表示索引打包完成。当前内容提交 `55ac4704d77a7423a06d8cda8d8403b42ac5af4a` 由 `929bdcb918f2207aea38b02a14bd8e6219fabac4` 的固定源码验证，得到 20 entries、1 feedback、246,051 bytes。workflow 的两个内嵌 Python 脚本编译通过，安装和结果摘要引用同一个固定 validator SHA；任务包拓扑与所有 block hash 都参与检查。

[候选工作流 37212273654](https://github.com/mindie-agent/knowledge-vllm-ascend/actions/runs/37212273654) 已通过，`publication-head` check `111465812689` 回读确认同一 `55ac` head 与 `929` validator。原 PR base workflow 使用旧 validator `e6818da4e426e938674e7f4cad32e5e0c7ec7157`，其 [run 37212258128](https://github.com/mindie-agent/knowledge-vllm-ascend/actions/runs/37212258128) 曾因 `PR text fails the privacy scan` 失败，尚未走到任务包校验。实际是 review prose 将 main 与 SHA 用 @ 连接，被识别为 username-at-host；改成 main commit 加独立 SHA 后，新旧固定扫描器均通过，规则未放宽。随后 [base run 37213022361](https://github.com/mindie-agent/knowledge-vllm-ascend/actions/runs/37213022361) 成功，但旧 validator 实际只报告 0 entries、1 feedback、641 bytes，未检查 tasks。此旧检查绿灯不构成新 schema 验收；候选工作流及后来合并后的新工作流均以 `929` 实际检查 20/1/246,051。

此前 `ca160` 推送的 workflow 权限拒绝使用了 macOS keychain 的另一凭据。后续读取确认已有 gh 凭据含所需权限，同一用户通过命令级 credential helper 完成推送；没有扩展 scope 或修改全局 Git 凭据设置。PR37 已正常合入 `5273638c81f55cc8b1423d887b6859d51d6f3621`，parents 为源 main `9aab5e1` 和候选 `55ac470`；tree `b7c94962430fdd715881e113cc6f165bafeae21c` 与候选完全相同。[合并后自动工作流 37215772292](https://github.com/mindie-agent/knowledge-vllm-ascend/actions/runs/37215772292) 和 `publication-head` check `111475953627` 均成功，回执精确绑定该 main、validator `929` 和 20 entries、1 feedback、246,051 bytes。这证明自动 push 工作流已检查新格式，不是 Grok 事件审查或 Bot 合并证据。

新 CI 和文档通过 whitespace 检查。全迁移 diff 中的一处两空格 Markdown hard break 来自原公开正文，为满足精确保留要求保持原字节，不声称全 diff 没有任何 whitespace 提示。

## 最终正式安装、Grok 配置与公共消费

[正式安装回执](formal-deployment.json)记录了一次真实失败和一次显式恢复。旧 `33de369` owner 在 runtime probe 导入已删除的 `MaintenanceBudget` 时拒绝候选安装，原目标 attempt count 为 1、类别 unknown。主任务审核后，在既有锁和安装流程中只执行一次 prepare/install，实际安装 merge `f35ab6f`；原 attempt、next_check 保留，journal 清除，正式设置与 scheduler plist 未改。原生选择、cache 文件字节、source tree 和 core `929` / remote-dev 精确依赖均回读通过；没有有效 lease 时 service handoff 为 `not-needed`。这次成功是显式恢复，不是旧控制器自动升级成功。

随后通过正常 Codex CLI Review hooks 界面对正式 Stop 执行信任，原生回读 currentHash 与 trusted_hash 相等、trusted/enabled，界面退出 0；没有 bypass 或业务模型调用。Hook 信任是安装层事实，未在最终版本重新执行一轮公共业务 Stop。

内容合入后，原有 launchd runs 从 117 增到 118，last exit 为 0；相应 owner 记录 `synced` 精确 `5273638`、20 entries、attempts 1，plugin 为 `up_to_date`。只读库中 20 条均为 active feed-origin experience。主任务和安装代理均未手动调用正式 public check 或 Feed.sync；来源依据是 run 增量、owner 时间与无手动调用的记录。stdout/stderr 未配置，因此不宣称取得独立完整进程日志，也不将一次观察扩成长期 SLA。正式 community 与 consent 文件始终不存在，没有悄悄启用采集或贡献。

[Grok 配置回读](grok-format-cutover.json)区分实际保存界面与 Bot 自报执行。主任务完整刷新应用后重新打开三个既有 routine 的详情，确认 trusted pin `929`、task/1、entry/3、block/1、feedback/1，以及 exact-base 冲突和整包撤下；初始未刷新的旧 pane 不算最终依据。PR routine 保留 opened/closed/merged 事件，每日 09:06、每周六 10:03（Asia/Shanghai）保持，没有新 listener 或权限变更请求。Bot 报告非 editable 安装的 validator 字节与可信 checkout 相同，隔离 Python 对 `55ac` 实际校验退出 0、stderr 空、20 entries/1 feedback/246,051 bytes；未执行候选代码或 Git hooks。broken pip 经可恢复备份和 ensurepip 修复，但 `pip check` 仍退出 1，缺少 LangMem、mindie-diagnostics、reme-ai；仅该校验路径可用，不称完整 runtime 安装。校验管线零模型调用不代表 Grok 对话账单为零。配置任务没有授权 Bot 审查、评论或合并 PR37，也未验收新事件投递。

[独立公共消费者](public-github-consumer.json)只使用单独配置、正常安装的 core `929` 和公共 GitHub HTTPS main，第一次正常 CLI sync 得到 `synced` 精确 `5273638` 的20包/22块/1反馈；没有直接 Feed.sync、数据库写入、私有历史读取或服务连接。CLI 没有 query/explain 命令，后续通过既有 Store 公共 API，三个预先确定的 top-5 查询均找到目标 feed-origin、非 supplemental 引用，并 explain 实际返回引用的全部正文：4,322 / 2,792 / 6,284 字节及 SHA256 与公共包相符。第二次正常 CLI sync 为 unchanged。capture、stream、batch、task、outbox 和 owner 表均存在且为 0；summary-attempt 表未建立，明确记录为 absent，不能误称已有表行数查询为 0。未配置 community、consent 或 summary worker，受控命令路径与管线计数中的 native business model / summary-worker 调用为 0；这不是提供商全局网络/账单遥测。原生 Stop→GitHub PR→Grok 新事件链仍需要已选择的正式公开贡献范围，当前没有该授权事实，故没有用私有业务材料补做公共链路。

## 与当前上游架构的整合

文档候选在保留初始研究 `c666e597c8690f7f7c141e0c04ae29e9a0484de7` 快照的同时，整合了 canonical main `8275bd4819b9d9f64adafc442f0c1da468775c6f`；整合后的候选提交为 `e4dd566586e8b905eb5dd25b85a077cfbe4238fd`。本轮同步审查 [architecture](../../architecture.md) 和 [implementation status](../../implementation-status.md)：LangMem 索引是发布的必要步骤，失败可见且没有摘录 fallback；显式历史与实时 Stop 使用同一管线；正文和必要发送回执保留至公开 feed 确认精确 revision，而非 PR 刚创建时删除。Markdown 是一套权威材料，ReMe 可持有可重建的派生文本缓存。旧验收段落保留原日期和边界，不能覆盖本次切换的未完成验收。两页均纳入当前文件哈希清单。

## 公开证据检查

公开检查范围是相对 canonical `upstream/main`（`8275bd4819b9d9f64adafc442f0c1da468775c6f`）本次新增、修改或重命名的现存 UTF-8 文件，以及未跟踪的新 UTF-8 文件。对这些文件使用固定 core 版本的 public-data 规则，并检查本机用户目录和原始 transcript 路径模式；未修改的历史上游文件不属于本 PR 的检查结论。已将研究清单、复现命令、探针和 selector 回执中的本机路径改成明确的工作副本角色或相对路径；源码 commit/hash 和原始测量值保留。路径归一后的探针仅作语法检查，没有把原始实验重新记为执行过。

规则仍会命中公开来源 URL、仓库相对证据路径、检索指标记号、包版本号、明确合成的 PEM 边界 canary 以及已经脱敏的占位符。逐项复核后将这些记录为 reviewed findings；它们没有被当作真实凭据，也没有通过全局放宽产品扫描规则来隐藏。具体计数和未解决项见清单的 `validation.public_data_scan`，不声称原始扫描零命中。机械规则扫描仍不构成所有语义隐私均已识别的保证。

## 九原则结论与本轮修正

1. **总成本。** 增量处理只使用新增完整块和短导航；消费者复用已有入口，不再为材料索引调用模型。一次内容转换复用原始公开成果，文档修正不重跑真实模型实验。
2. **封闭问题。** schema、包完整性、哈希、边界、批次和调用回执有明确机械合同；模型摘要与知识是否适用仍是参考判断。文档已把“未入 manifest 的文件拒绝”明确限定为任务包内部。
3. **理解负担。** 对使用者呈现任务材料、检索卡和明确错误；初始研究、实现和验收分阶段呈现，避免要求读者自己辨别互相冲突的“当前”结论。公开源码定位使用工作副本角色及相对路径，不要求读者访问某台机器的目录。
4. **职责边界。** ReMe 拥有分块和派生检索，LangMem 负责索引生成，MindIE 保留授权、规范包与事务衔接，GitHub 是公开版本权威；不把自有 glue 声称为框架已接管。当前材料的一套权威文件是 Markdown，ReMe 派生缓存可能包含文本，可独立重建；这不承诺磁盘只有一份字节副本。SQLite 不镜像正文，本地不另建原始 transcript 副本或逐 revision 正文档案。
5. **Skill 信息性。** 此文档变更不创建 Skill、固定研究路线或业务收尾要求。开发 PR 的原则审查是已有交付规则；经验正文继续作为知识材料保存。
6. **参考性。** 原正文、失败、更正和不确定性保持，已有摘要明确为 fallible index。任务索引完成、规则扫描、检索命中和公开审核均不认证技术结论；保留原反馈 revision。
7. **按需介入。** 实测覆盖用户明确选定的四份历史、已有公开内容转换及隔离 profile 的纯合成原生链路。正式安装和正常信任只改变已授权的插件层，公开贡献配置与 consent 仍未建立；独立消费者管线计数为 0；普通任务不因文档或安装自动导入旧历史，不新增模型裁判或强制经验贡献。
8. **成果复用。** 保留初始研究快照及当时哈希；复用固定原生回执和既有机制测试。公开证据仅将本机路径归一成工作副本角色与相对路径，原始测量没有重新运行或改写；初始清单 SHA 标明为归一前文件哈希。后续平台修复使用相关定向验证，明确前后版本，不通过重复全量运行掩盖证据差异。
9. **错误可见。** 模型失败和未知保留实际状态与已知用量；已返回输出的本地恢复不重复付费。缺少必要 worker、损坏索引、包校验失败和提交后的清理错误不能成为成功或空数据。 后续修正使开发传输每步失败和 push 未知结果保持可见，也使同一捕获事件较早已保存的正文不被尾部噪声改报为空；保存回执与继续处理的错误分别呈现，损坏回执在实际只读诊断入口成为明确 fault。后续远端 Git object 预检在 checkout 前识别路径/mode 冲突，保持 `needs_review` 且不外写，避免宿主 checkout 失败掩盖应交给审阅者的冲突。正常更新入口发现的 `check_failed` 假成功已通过窄修正和实际 CLI 回读恢复非零退出；已完成 feed 工作不被后续 plugin 失败覆盖。文档保留早期权限拒绝及后来使用已有有效凭据解决的事实，不继续把已解除问题写成阻碍，也不把候选或合并后 workflow 成功等同 Grok 闭环。后续保留 Windows 两阶段故障、旧 updater 拒绝与显式恢复、Bot 的依赖缺失，以及文档提交 CI 失败；正式安装、一次 scheduler 同步和公共消费成功各有独立边界。

最终复查覆盖 canonical `8275bd4819b9d9f64adafc442f0c1da468775c6f` 之后的完整文档 diff 和上述行为，原则依据为本节顶部的当前文档；文档候选中的对应 blob 为 `62cdd5ae40553df2f0f7f7d022141123792d2944`，差异仅为架构链接。第 1/8 条复用已有模型和原生回执，不重复未变实验；第 2/4 条补齐现有 schema 的不可变块和 exact-base 合同，不增加新服务；第 3/6 条修正过时 candidate/未部署说法并保持参考性；第 5/7 条没有新增强制 Skill 流程、采集或贡献授权；第 9 条保留真实失败和各层完成状态。最终 review tree 与 manifest SHA256 在提交前冻结回执中记录，未将它们自嵌入文件形成循环哈希。

当前剩余边界是正式公开贡献范围，以及新格式公开 Stop→PR→Grok 事件审查合入验收；已完成的正式安装、Hook 信任、一次 scheduler 同步和独立公共消费不再列为未完成。Grok 完整 runtime 依赖、最终版本原生业务全链、长期调度/存储 SLA、普遍长会话语义质量与真实硬件均没有新增验收。早期失败和初始研究快照保持原阶段，后续结果没有倒填为当时已完成。

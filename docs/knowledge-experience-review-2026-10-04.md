# 经验组件初始实现快照审查

日期：2026-10-04。审查范围：需求历史、架构/设计、用户侧采集与整理、发布/同步/检索/反馈、安装元数据及对应合成测试。本轮不声称审计了所有外部服务、真实用户记录或运行中的模型。

这是开始实施前的研究快照；下文的“当前”“本轮”均指这一阶段。源码位置和未提交状态按当时记录保留，不能据此认定后续候选仍有全部旧问题。后续实现、真实模型测量和仍未完成的验收见[实施证据与原则审查](knowledge-review-2026-10-04/evidence/implementation-review.md)，阶段与文件哈希见[证据清单](knowledge-review-2026-10-04/evidence/manifest.json)。源码定位使用仓库相对路径和初始工作副本行号，不冒充已提交版本的永久链接。

## 1. 先区分四份不同的“当前版本”

| 对象 | 本轮核对的状态 | 能证明什么 |
| --- | --- | --- |
| 主架构工作区 | HEAD `c666e597c8690f7f7c141e0c04ae29e9a0484de7`，多份设计和原则有未提交修改 | 当前需求依据包括实际工作内容，不能只引用 HEAD |
| knowledge 候选 | 研究工作副本 `knowledge/`，HEAD `6a9fb51d41f9787122ef61cbdf81df981d12cded` 加未提交修改 | 有摘要闸门、当前正文保留、首尾输入等候选能力；不是已部署版本 |
| Codex 候选 | 同级 `codex`，HEAD `56f28c39e68f4435c03a007c9906aa7c92ed85ae` 加未提交修改 | 用户侧摘要 worker 候选；不代表安装依赖已跟随 |
| 本机 marketplace 安装 | generation `33de36945e6dd448104c42b7fa49639b00f8ff58`，version `0.1.0+codex.20260929184054628015`，venv knowledge pin `82f7d7dd4c52637e1448e3747262a20453f4bcb4` | 安装元数据与文件已核对；当前会话实际装载、Hook 信任生效及原生回调未验证 |
| GitHub main | knowledge `2637ffa848c0a44bde38ee488112150ee9bc0743`；Codex `33de36945e6dd448104c42b7fa49639b00f8ff58`；内容仓 `9aab5e1e2f1298f992b1b41e403c2b1e0232d12c` | 本轮只读 API 获取远端确定提交；不证明 Bot 事件送达或已安装环境等于 main |

可用 GitHub 工具没有提供通用 GitHub connector，本轮仅以 `gh api` 读取三个 main 提交，无写入。本地内容仓检查的 workflow pin 不是远端最新内容仓检查，不据此声称远端 CI 已完全核验。

真实历史只由主审查读取其用户目标和已有交付说明；子代理只收到需求概括、代码和合成数据。未复制真实 transcript 到研究仓库、框架或模型。

## 2. 最需要修复的问题

### R1 · P1 · 安装版仍允许摘要未完成的草稿进入导出

安装版 `loop/transcript_capture.py:79` 可把缺少 summary command 记成 excerpt；`loop/export.py:106` 没有候选版本新增的摘要状态/body digest 闸门。因此 pending、失败或缺少摘要能力的材料仍可能被导出。当前安装配置实际有 worker，不能误报为本机未配置模型。

候选的 `knowledge/mindie_knowledge/loop/export.py:106` 和 `knowledge/mindie_knowledge/loop/store.py:1340` 已加闸门。问题是这份改进尚不在安装 pin 内。需要组合发布/安装验收；更多候选测试不能代替这一步。

### R2 · P1 · 跨两次采集的敏感区段失去脱敏上下文

`knowledge/mindie_knowledge/loop/transcript_capture.py:85` 对每个增量单独 redaction，然后追加正文。合成输入第一段是私钥 BEGIN 与合成头部，第二段是 `SYNTHETICTAILCANARY` 与 END。完整一次扫描可屏蔽尾部，分两次采集则把尾部保存并送入模拟摘要 worker。

这是已经复现的模型输入边界缺陷。出口当前还有 R6 的误判，实验没有发送外部材料，**不能声称已发生实际公开泄露**。修复应携带未闭合敏感区段的轻量状态/边界缓冲，并覆盖跨页、跨消息、重启。单独把每次扫描输入调大不能证明解决跨增量问题。

### R3 · P1 · 模型返回后的本地失败会重复调用且少计成本

`knowledge/mindie_knowledge/loop/transcript_capture.py:177` 调用 worker 后还要扫描输出；`knowledge/mindie_knowledge/loop/transcript_capture.py:211` 将 ScannerUnavailable 一律放回 pending。重启也在 `knowledge/mindie_knowledge/loop/engine.py:1428` 无条件把 running 变回 pending。

合成 worker 成功返回，连续注入三次后置扫描故障，第四次恢复：worker 实际调用 4 次；最终摘要回执 `model_calls=1`，`maintenance_attempts=0`。此路径没有能区分“未开始调用”和“已付出调用但本地处理失败”的持久回执。

必须先保存已返回的最小元数据与用量，再处理本地扫描；结果未知须单独表示。修扫描器不能造成重新调用模型；进程重启不能重置已消耗预算。

### R4 · P1 · 远端正文变化后，本地有效补充可能永远无法再发布

`knowledge/mindie_knowledge/loop/store.py:2505` 把草稿重建为远端正文加未发送观察，却未同步失效/重排 transcript 摘要。导出按 digest 检查后过滤，worker 又只拿 pending 项。

合成结果：`ready_before=true → ready_after=false`；`summary_status=complete`；pending 数量 0；未发送观察仍在；`build_batch=null`。没有下一次新增采集时会滞留。正文依赖变化必须同事务触发头部重新校验/处理，同时显示具体等待原因，不能把无可导出内容伪装成无新工作。

### R5 · P1 · 修复摘要环境后，同一来源没有有效的阶段重试路径

worker 退出 124 后修复为成功 worker，再显式导入相同历史，`knowledge/mindie_knowledge/loop/history_import.py:112` 返回 unchanged，原任务仍 summary failed，build_batch 为空。worker 只拿 pending，普通管理路径没有针对该终态的显式重排入口。

需要可定位的阶段恢复语义，并保留旧尝试账目，不需要自动无限重试。不能要求用户更改正文或重新授权整个安装来恢复已有工作。

### R6 · P2 · 脱敏器生成的安全占位符被出站扫描误识别为凭据

`knowledge/mindie_knowledge/loop/transcript_redaction.py:158` 自身识别脱敏占位符，但 `knowledge/mindie_knowledge/loop/export.py:214` 使用裸 scan_text。真实本地 Gitleaks 8.30.1 加规则生成的 `<redacted:credential-private-key:89aadc32729f>`，被再次认成 credential-assignment，安全材料进入 quarantine。

统一受信占位符处理；覆盖脱敏幂等性。不能全局允许所有外部文本自称为占位符而跳过扫描。

### R7 · P2 · 用量通道已有数据，但 worker 丢弃，无法判断是否便宜

Codex `codex/plugins/mindie-agent/scripts/process_guard.py:137` 已提取输入、缓存与输出 token，worker 在 `codex/plugins/mindie-agent/scripts/agent_worker.py:57` 丢弃返回值。核心只记当前请求字节和 0/1 次调用，失败没有完整累计记录。

12 KiB payload 不含固定提示词，也不等于实际 tokens、费用或长任务总量。复用现有 usage 白名单，包含失败和复用状态，缺失记未知。不要保存整份模型 JSON 事件流来补计量。

### R8 · P2 · 首尾策略有确定盲区，但此前没有模型质量和消费评测

`knowledge/mindie_knowledge/loop/summary_input.py:49` 固定前 1/3、后 2/3。既有十个合成案例的输入覆盖实验里，首尾输入保留完整关键句 2/10，关键检索词 6/26；这是刻意包含中段难例的测试集，不能解释为真实任务召回率 20%。本轮核对该实验记录的 selector hash 与当前源码一致，并提供重新运行的探针。

完整正文仍由 `knowledge/mindie_knowledge/loop/store.py:581` 索引。所以不能说这些经验不可检索，也不能归咎于 Luna。当前 query 卡仅返回标题/摘要，缺少正文命中片段；消费者仍可能无法判断中段命中为什么相关。分别评测输入、摘要、实际 query 和选读。

### R9 · P2 · 缓存键未包含真正提示词和模型实现版本

`knowledge/mindie_knowledge/loop/transcript_capture.py:164` 用策略、命令 argv、范围和输入算缓存键。同一路径的 worker 更新 PROMPT/SUMMARY_MODEL 不必改变 argv，可能继续复用旧策略的头部。

摘要适配器需要提供稳定的实现/提示词/模型配置指纹。版本升级可确定失效，不因每次运行随机生成新 key 而失去复用。

### R10 · P2 · 最新正文保留降低磁盘副本，尚未消除累计全文处理

`knowledge/mindie_knowledge/loop/store.py:1244` 的追加会索引累计正文；摘要只改头部时 `knowledge/mindie_knowledge/loop/store.py:1073` 也重建全文索引。外部采集事务包着追加，令“锁外 tokenization”的局部安排失效。

等长 n 次追加可能产生累计 O(n²) 的正文处理量。这是静态复杂度分析；本轮没有给出生产 CPU 退化比例。先分开量出读取、扫描、哈希、FTS、锁时间和 WAL/写盘；据实选择合并更新或块级处理，不马上建设事件存储体系。

### R11 · P2 · 清理失败被计为清理成功

`knowledge/mindie_knowledge/loop/store.py:2278` 使用 `rmtree(ignore_errors=True)`，随后无条件记录 staging 删除 1。注入目录读取 PermissionError：回执称已删除，暂存实际仍在。

保留“发布已确认”，另报“清理失败，当前副本尚存”。后续只执行清理，不再发布。只留最新约束需要检查数据库以外的 staging、Git、WAL 和日志。

### R12 · P2 · 文档、安装与候选对“最新正文”的合同不一致

安装版存储仍保留全部发布历史；候选已删除旧正文，并让旧 revision 无法读取。旧共享设计仍写活动引用可读和退役历史可解释；候选只回 `unknown pinned revision in this domain`。应明确旧引用过期，允许重新查当前版本，不保留历史正文来兑现已经取消的承诺。

同样，候选 `docs/mindie-loop.md` 仍描述全文摘要，而新文档描述首尾；原 64 KiB 正文上限与当前代码平台 100 MiB 包络也不同。把设计约束、配置默认值、外部上限和已经测过的支持范围分别写明。

## 3. 应保留的已有能力

不建议因为这些缺陷重写整个组件：正文/游标/继续标记同事务、重复事件幂等、格式坏记录停止、只改头部的摘要权限、正文 CAS、授权前后检查、UTF-8 安全输入边界、重叠脱敏区段合并、当前正文存储、全文 FTS、索引未就绪报错，都有可复用实现。

发布已有受控暂存、精确 head 回查、开放 PR 更新、合并后新 PR、Bot 正文权威、unknown 阻止重复写和反馈批次。同步已有正文与索引原子切换及退役退出检索。优先补齐交叉状态与失败合同，而不是再包装一层抽象复刻它们。

## 4. 本轮验证与边界

| 验证组 | 结果 | 边界 |
| --- | --- | --- |
| 整理核心四组定向测试 | 106 passed | 合成数据、固定本地扫描器；非真实模型质量 |
| Codex organizer 相关测试 | 18 passed | worker 边界/合成执行；非原生 Hook |
| 发布/索引/反馈九组测试 | 首轮 172 passed、3 个环境依赖失败；补齐隔离依赖路径后仅复跑失败项，3 passed | 不将这两次称为一次完整干净全套；无 GitHub 写入 |
| Organizer 合成故障探针 | 复现跨段扫描、后模型重复调用、显式导入无法恢复、占位符误判 | [脚本/结果/命令](knowledge-review-2026-10-04/evidence/organizer/README.md)，模拟模型 |
| Delivery 合成故障探针 | 复现正文 rebase 卡摘要、清理假成功 | [运行说明](knowledge-review-2026-10-04/evidence/delivery/RUN.txt)，临时数据库 |
| 输入覆盖探针 | 针对当前 selector 重跑既有十个合成案例 | [评测合同](knowledge-experience-evaluation-2026-10-04.md)，不测生成摘要/费用 |
| 原生模型、Hook、Grok、独立客户端完整闭环 | 未执行 | 不能从单元测试数量、安装 enabled 或本地回执推导成功 |

本文不把建议当作已经完成的修复。在本文记录的初始研究阶段，运行代码、安装环境和公共仓库未被这项研究改动；后续实施与验收按独立阶段记录。

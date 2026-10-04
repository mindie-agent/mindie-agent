# Stage5：纯合成原生公开闭环验收

日期：2026-10-05（Asia/Shanghai；执行为 10 月 4 日 UTC）。**一个新授权的纯合成任务已完成正常 Stop→小模型索引→自动 GitHub PR→现有 Grok 自然审查合入→独立 HTTPS 消费。** 这是新的第五阶段；[清单](../manifest.json)与此前四阶段保持各自实际版本、失败、费用和当时授权边界。

用户在 Stage4 之后明确授权新建合成目录并继续。通过正常 configure 只启用这个新目录的公开贡献，目标为 `mindie-agent/knowledge-vllm-ascend`；未读取私有历史、扩大到原业务项目或手工调用 Stop/历史导入。正式适配器固定 `f35ab6f6bc38e1a33d33bcfccc98c828feb9c041`，core 固定 `929bdcb918f2207aea38b02a14bd8e6219fabac4`。并行开发 PR38/PR61 未参与这次验收，也未自动更换候选 pin。

## 实际链路与正文边界

[生产者回执](producer.json)记录一次新的原生业务 turn，正常退出 0；没有 Hook 信任 bypass。正常 Stop 得到 1 个 organized capture、1 个 task 和 1 次 complete 索引。默认 300 秒静默窗口后自动创建 [PR39](https://github.com/mindie-agent/knowledge-vllm-ascend/pull/39)，source head 为 `bb1cf70923b02db2ede69dea112033838d3c0d39`，只增加一个任务的 manifest 和一个块；没有手工创建 PR、通知 Bot 审查或触发发布。

该首次采集的合格材料是激活之后的公开 `assistant:final_answer`；启动 prompt 与此前 commentary 在激活边界之前，没有收录，因此不能称为完整启动会话。任务 ID 为 `16796d4249feda48b9a855d387f80331dbd3d1700da25d852d091493dcc92bdb`，revision 为 `c019ce2fb763911e1937205f0cd09451c0895878a85e384750593a15bed64e77`。块文件 540 UTF-8 字节，SHA256 `05fd0dae0474d90aefa706ead5ab3209e8f2ab70005ead2af3dd6b8a04bda629`；去掉 block frontmatter 后正文为 375 UTF-8 字节、305 字符，SHA256 `f3d77ea8f976f6eba8691a83bd733ded1162cf9115be3d461743f4abbd322426`。这些值在消费者执行前从精确公共 head 独立计算，未用消费者输出生成预期值。

完整正文依次保留以下三句，各一次：

> Initial assumption: 2 shards.
>
> Correction after checking the synthetic fixture: 4 shards.
>
> Hardware benchmarking remains unverified.

生产者实际读取四个合成数组元素并把假设从 2 改为 4，没有运行硬件。其初次 marker 查询读取的是旧公共条目，不能算这个新任务的检索命中。索引和导航是参考入口；部分导航提到的更早上下文没有因此变成已采集正文。

[Grok 回执](grok.json)来自主任务在原生应用观察到的自然处理消息，并与独立 GitHub 回读核对。Bot 消息报告使用可信 `929` validator 对精确 head 检查通过：21 entries、1 feedback、249,215 bytes，且 exact-head CI 通过。GitHub 确认 PR39 于 2026-10-04 16:43:53 UTC squash 合入 `9b7966f841131d0b942d0f447599b46eddefbef1`，当时 main 指向该提交；tree `18c0ba36ef5cb67ce7389ff9ca910827f3a09049` 与候选相同。`publication` 和 `publication-head` 两检查均成功。主任务没有给 PR39 发送人工 Bot 消息或执行 merge。Bot 的检查说明在对话中，没有创建 GitHub APPROVE review 或评论；仅有 Working UI 或相同 mergedBy 账号不足以证明 Bot 完成，验收依据是自然消息与准确合入结果的组合。

[独立消费者回执](consumer.json)来自一个新隔离目录和正常安装的 core `929`。只执行一次已审查脚本：第一次正常 HTTPS CLI sync 返回 `synced` 精确 `9b7966f`、21 条，公共树有 21 包、23 块、1 反馈。预先固定的 query `2 shards 4 shards hardware unverified` 在 top 5 返回目标任务的 feed-origin、非 supplemental 引用；既有 Store.explain 公共 API 对该实际返回引用读取全部一页正文，375 字节和 SHA256 均与独立 oracle 相同，三句顺序保留。第二次正常 CLI sync 为同提交 `unchanged`。没有直接 Feed.sync 或数据库 feed 写入，也未启动另一个原生业务模型。

消费者 captures、material streams、batches、tasks、outbox 和 owners 表均存在且为 0；summary-attempt ledger 未建立，明确记录为 absent。该隔离消费者没有 community/consent/service 配置，受控命令路径和管线计数中的业务模型与摘要 worker 调用均为 0；这不是提供商全局网络或账单遥测。正式生产者的新合成贡献授权与这个消费者的未启用状态分别记录。

正式生产者之后也经正常 owner 自然同步到 `9b7966f`、21 entries。同任务 `draft_revision=null`、`published_revision=c019ce…`、`feed_active=1`，summary 仍 complete 且只有 1 次 attempt。其历史 outbox 记录仍为 **submitted、reconciliations=0**，没有观察到变成 merged；不能把 GitHub 合入或 feed 激活改写为 outbox 终态。没有为修饰该回执手动 reconcile、sync 或再调模型。

## 成本、完成范围与九原则审查

| 调用层 | 实际用量与边界 |
| --- | --- |
| 原生业务 turn | 1 turn，222,214 input / 1,009 output tokens；其中 cached input 176,640，reasoning output 251 |
| 必要索引 | 1 次 `gpt-5.6-luna` / low，7,743 input / 303 output tokens，cached input 0，20,425 ms，complete |
| 独立消费者 | 受控消费者业务模型和索引 worker 均 0；query/explain 使用已有材料和 ReMe 索引 |

缓存输入与 reasoning 输出分别是 input/output 的子集，不能再相加；本阶段费用不并入此前 35 次历史调用或一次本地合成索引。未取得 Grok 对话 token 账单，不推导金额、提供商内部请求数或完整闭环总费用。

这份文档更新以已合入 docs `24a1f0f9b2e1b38751f890dc3664ae5c0e31abb3` 为基线。当前[设计原则](../../../design-principles.md) blob 为 `62cdd5ae40553df2f0f7f7d022141123792d2944`，SHA256 为 `db1fadfb34b46ff49e6e2a113b69c5b684b8f9f13be118bd037f574851b7c98d`。最终 diff 逐条复查如下：

1. **总成本：** 只新增一个已授权合成样本及一个无模型消费者，复用正式插件、已有 idle 发布与 Grok routine；不为文档重复模型或产品 CI。
2. **封闭问题：** 精确 head、任务/revision、原文字节/hash、已知片段和管线计数是有边界的机械核对；一次命中不固化为普遍质量结论。
3. **理解负担：** 当前状态用短链接指向第五阶段；以前未授权、未验收的记录保留原阶段，避免让读者推测时间先后。
4. **职责边界：** Stop、索引、GitHub、Grok 和消费者按各自实际回执关联；没有额外检索库、发布器、直接 feed 写入或新的常驻调度。
5. **Skill 信息性：** 此改动仅补充证据和现状链接，没有创建 Skill 或强制普通任务遵循验收流程。
6. **知识参考性：** 2→4 更正和硬件未知原样保留；索引完成、Bot 合入和 query 命中均不认证硬件事实或摘要正确性。
7. **按需介入：** 后续用户授权仅覆盖新合成目录；未读私有历史、扩大业务范围或增加消费者模型调用，也未触碰并行 PR。
8. **成果复用：** 固定正式 f35/core929，复用已验证 driver 和公开 head 预期值；前三层旧回执与 Stage4 部署证据不重新执行或改记日期。
9. **错误可见：** 保留激活边界、初次查询未命中新任务、无独立 GitHub review、outbox 仍 submitted 等实际限制；精确同步、引用或原文不匹配会保存失败并停止，没有自动重跑。本次脚本一次通过，没有伪造失败后恢复。

本阶段证明该纯合成样本的公开链路和完整合格正文消费，未证明任意私有语义可安全公开、完整启动会话捕获、普遍长会话质量、所有平台原生入口、长期资源/调度 SLA 或硬件性能。Grok validator 可用也不改变此前完整 runtime 依赖缺口。扫描、JSON、链接、哈希和最终 diff 检查结果记录在清单与冻结回执；机械扫描不构成全面语义隐私保证。

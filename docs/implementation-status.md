# 统一实施进度

更新于 2026-10-09。设计以[架构](architecture.md)、[Harness 生命周期](harness-boundary-and-lifecycle.md)及[九条原则](design-principles.md)为准。旧版本实施与实机记录保留在 [Git 历史](https://github.com/mindie-agent/mindie-agent/blob/d3627ed962c3ccba3c26020fa4dbf0032f963903/docs/implementation-status.md)，其证据不自动覆盖新接口。

## 当前交付

当前目标是 Codex 的完整知识闭环和运行时交付。安装沿用已有贡献选择与项目范围，合格原生任务自动关联；查询、读取和反馈按需使用。Kimi 与 Claude Code 仍需单独移植和原生验收，不能只更新共享依赖就视为完成。

| 组件 | 精确提交与交付状态 | 实际证据 |
| --- | --- | --- |
| 知识核心 | [PR #61](https://github.com/mindie-agent/knowledge/pull/61)，候选 `7c99fbb` 已合入 `c23e38b` | Linux/macOS 878 passed / 9 skipped；Windows 857 passed / 30 skipped；package CI 成功。合入提交的源码、依赖、测试和工作流与已验证候选相同 |
| 公开内容合同 | [PR #38](https://github.com/mindie-agent/knowledge-vllm-ascend/pull/38)，候选 `7510944` 已合入 `38ab4b9` | 新主线 trusted-base workflow 实际使用知识核心 `7c99fbb`，校验 21 个任务包、1 个反馈、249215 bytes，`publication-head` 成功；已有任务正文未改动 |
| Codex 接入 | [PR #19](https://github.com/mindie-agent/mindie-agent-codex/pull/19)，最终候选 `ead0f16` 已合入 `078fc0e` | 最新候选 CI：Linux 运行 395 tests，OK / 13 skips；Windows 运行 395 tests，OK / 20 skips，含实际 CMD 与 PowerShell Hook 派发；产品 preflight 成功。合入提交树与已验证候选相同 |

## 2026-10-09 原生验收补充

[原生验收记录](knowledge-review-2026-10-09/native-acceptance.md)与[精确证据](knowledge-review-2026-10-09/native-acceptance-evidence.json)记录本轮 macOS 的实际边界。首次原生 Stop 暴露安装器未初始化知识状态的问题；[Codex PR #23](https://github.com/mindie-agent/mindie-agent-codex/pull/23) 已修复并合入 `497f7c9`，Linux/Windows CI 各运行 397 tests，分别 13/20 skipped，均通过。

修复后的全新安装完成原生首轮自动保存、一次内置小模型整理、自动投稿 [知识 PR #40](https://github.com/mindie-agent/knowledge-vllm-ascend/pull/40)、现有 Grok Bot 自动合入，以及独立新消费者从公开 feed 检索和读取完整正文。本机已实际选中 `497f7c9`，包字节与候选一致，22 个任务包的 46 份 Markdown 未改变；只有一个已信任启用的 MindIE Agent Stop Hook。

Bot 本轮报告的可信校验器仍为 `929bdcb`，与新仓库契约要求的 `7c99fbb` 未对齐。CI 使用了正确 pin，但不能代替外部 Bot 的本地契约验收；该配置缺口仍未完成。受控消费者证明接口可用，不代表普通任务已获得复用收益。

## 核心行为与修正

知识材料以完整脱敏 Markdown 块保存，标题和摘要只是检索导航。增量目录与 ReMe 检索不反复重读无关正文。已返回的摘要结果可继续本地应用；未知模型或外部写入效果不会自动重放。后续贡献使用当前远端版本和未提交新块，保留维护者修正和撤下决定。

适配器保持一个名为 MindIE Agent 的 Stop Hook。普通任务无需日常激活、强制查询或收尾步骤；原生身份、现有授权与范围仍是准入依据。脚本、解释器、依赖和运行时配置作为同一 generation 交付，知识与通用 remote-dev 的调用独立。

合入前审查发现并修正 Hook 包装层吞掉解释器/脚本启动失败，以及测试清理从旧目录读取 wake 回执的问题。包装层现在保持中性输出并向宿主报告有界错误；清理等待实际状态目录的拥有者退出，错误不伪装为成功。Windows 初次模块加载的进度输出单独关闭，真实失败提示保留。正常版本声明与 release tag/源码一致性检查补齐，避免声明发布后仍按开发重建处理。

## 发布与验收边界

当前仍为开发期。在各仓库达到发布标准并声明正常版本之前，允许反复破坏性格式更新。正常版本候选必须声明匹配的知识和远端回执发布边界，release 渠道也校验 tag 与源码版本；发布后的不兼容格式必须提供迁移，不能清库后声称升级成功。

组件 CI 和合同校验只证明其对应路径。本轮 macOS 原生 Hook 信任、首轮派发、真实模型调用、投稿/合入与独立消费者读取已有实际记录；fork 派发、Windows 原生路径、真实远端/NPU 业务、模型质量与费用评估，以及外部 Bot 的新可信 pin 对齐仍需分别验收。隔离真实持久状态测试已覆盖兼容发布升级的数据和回执保留、不兼容拒绝与未知效果不重放；其中正常版本为模拟声明，未发布正式产品版本。合入、用户实际安装、宿主当前加载的定义和正式发布是不同事实。

此前 12 个普通消费者没有调用知识参考入口，不能据此声称实际复用收益；两个强制读取对照只属于探索性证据。没有新增普通任务的必查、必写或反馈要求。

<p align="center">
  <img src="assets/brand/mindie-agent-logo.png" alt="MindIE Agent logo" width="128" height="128">
</p>

# MindIE Agent

通过领域上下文、稳定的远端工具，以及知识与经验反馈闭环，帮助 Agent 完成 Ascend 开发任务。

**当前实现入口：[Codex](https://github.com/mindie-agent/mindie-agent-codex)。**
在自己的业务仓库和原生任务中使用插件。安装沿用已有贡献选择和项目范围，合格任务内部自动关联，不增加日常激活或收尾步骤。完整公开正文由本地程序筛选、脱敏并保存；内部小模型生成必要检索导航，不能替代正文。尚未选择贡献时不采集，缺配置与明确停用分别报告。远端通过 remote-dev 提供执行环境。

## 当前进展

2026-10-04 的[系统性设计](docs/systematic-knowledge-design-2026-10-04.md)统一了
Codex 产品组合、公开任务包与 Bot 契约，定义块级读取和引用归组。
实现与验证状态见该文档；旧版原生验收不自动覆盖这次接口变更。
[用户须知](https://github.com/mindie-agent/mindie-agent-codex/blob/main/plugins/mindie-agent/skills/mindie-agent/references/user-notice.md)
说明完整材料、规则脱敏与公开 Git 历史，不增加新的授权步骤。

首个领域为 vLLM / vLLM-Ascend。当前正在对 Codex 及上下游做[系统审查与修正](docs/system-review-2026-10-05.md)。开发候选、已合入版本和原生宿主证据分开记录；此前 CI 通过不代表本轮发现的系统边界已正确。

[统一实施进度](docs/implementation-status.md)区分代码合入、原生宿主、真实发布和新任务使用证据。Kimi 与 Claude Code 保留独立适配器和历史证据，仍需移植并验收本轮合同；不能仅更新共享依赖就称为三端完成。Kimi 模型验收暂缓。

## 仓库分工

| 仓库 | 职责 |
|---|---|
| [mindie-agent](https://github.com/mindie-agent/mindie-agent) | 架构、领域边界与交付入口 |
| [mindie-agent-codex](https://github.com/mindie-agent/mindie-agent-codex) | Codex Plugin、Hook 和原生任务接入 |
| [mindie-agent-kimi](https://github.com/mindie-agent/mindie-agent-kimi) | Kimi 原生插件、Hook、任务身份和本地模型适配 |
| [mindie-agent-cc](https://github.com/mindie-agent/mindie-agent-cc) | Claude Code 原生插件、Hook、任务身份和本地模型适配 |
| [knowledge](https://github.com/mindie-agent/knowledge) | 共享知识与经验运行时、可选贡献、分发和反馈 |
| [knowledge-vllm-ascend](https://github.com/mindie-agent/knowledge-vllm-ascend) | vLLM-Ascend 领域内容 |
| [remote-dev](https://github.com/mindie-agent/remote-dev) | 远端文件、命令、作业与产物 |
| [coordinator](https://github.com/mindie-agent/coordinator) | 受管环境、资源与执行 |
| [diagnostics](https://github.com/mindie-agent/diagnostics) | 组件诊断 |
| [npu-top](https://github.com/mindie-agent/npu-top) | 可选 NPU 观测 |

当前正式 feed 是 [knowledge-vllm-ascend/main](https://github.com/mindie-agent/knowledge-vllm-ascend/tree/main)。插件及知识库目前跟踪各自远端主分支；后续再切换 release。

## 架构与下一步

[当前架构](docs/architecture.md)遵循[设计原则](docs/design-principles.md)，[后续迭代](docs/next-steps.md)在本仓库维护。[Issue #195](https://github.com/mindie-agent/mindie-agent/issues/195)保留早期设计讨论。
一会话一个主要领域，用户持续直接指导；跨域使用同一 Harness 中可直接交互的独立任务。

当前优先完成 Codex 的入口、Hook/MCP、更新和知识闭环，以及实际上下游的错误和所有权边界；旧业务 Skill 与 profiling 暂缓。所有设计取舍优先遵守九条原则，常规任务不承担额外强制流程。

本仓库由 VAWS 原地更名，保留正常 Git 历史和既有材料。
旧 workspace/bootstrap、源码托管、自动更新器、客户端 Hook/MCP 接线与自动加载的业务 Skill 已从当前树删除。
各组件直接使用新包名、导入名和配置，不提供旧名别名或旧安装通道。
业务方法后续按领域重新整理进插件与知识库，旧实现仅保留在 Git 历史中。
历史验证只证明其记录的版本与范围。

[English](README.en.md)

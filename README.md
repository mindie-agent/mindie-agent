# MindIE Agent

通过领域上下文、稳定的远端工具，以及知识与经验反馈闭环，帮助 Agent 完成 Ascend 开发任务。

**使用入口：[Codex Plugin](https://github.com/mindie-agent/mindie-agent-codex)。**
在自己的业务仓库或 Codex 原生任务中使用插件。Codex、知识服务、收集整理和裁判在本机运行；远端通过 remote-dev 提供 NPU 执行环境。

## 当前进展

首个领域为 vLLM / vLLM-Ascend：一个入口 Skill，三个知识工具与十一个 remote-dev 核心工具。
已完成 Hook 收集、独立整理、授权分发、独立任务复用及使用效果裁判。
两个原生 Codex CLI 任务完成了 16 项真实 NPU 算子检查和反馈传播验收。

[实机验收记录](https://github.com/mindie-agent/mindie-agent-codex/blob/main/docs/real-acceptance-2026-09-18.md)记录了证据与边界。
Grok PR 事件投递尚未通过，每日增量维护保留为兜底；跨领域 Desktop 会话控制和其他 Harness 尚未验收。

## 仓库分工

| 仓库 | 职责 |
|---|---|
| [mindie-agent](https://github.com/mindie-agent/mindie-agent) | 架构、领域边界与交付入口 |
| [mindie-agent-codex](https://github.com/mindie-agent/mindie-agent-codex) | Codex Plugin、Hook 和原生任务接入 |
| [knowledge](https://github.com/mindie-agent/knowledge) | 知识与经验运行时、收集、分发、裁判和反馈 |
| [knowledge-vllm-ascend](https://github.com/mindie-agent/knowledge-vllm-ascend) | vLLM-Ascend 领域内容 |
| [remote-dev](https://github.com/mindie-agent/remote-dev) | 远端文件、命令、作业与产物 |
| [coordinator](https://github.com/mindie-agent/coordinator) | 受管环境、资源与执行 |
| [diagnostics](https://github.com/mindie-agent/diagnostics) | 组件诊断 |
| [npu-top](https://github.com/mindie-agent/npu-top) | 可选 NPU 观测 |

当前正式 feed 仍在 [knowledge 的 knowledge/vllm-ascend 分支](https://github.com/mindie-agent/knowledge/tree/knowledge/vllm-ascend)。
把该 feed 与既有领域内容统一到 knowledge-vllm-ascend，是下一轮内容整理；改名本身不代表该迁移已完成。

## 架构与下一步

[Issue #195](https://github.com/mindie-agent/mindie-agent/issues/195) 为架构基线，遵循[设计原则](docs/design-principles.md)。[目标架构](docs/architecture.md)与[后续迭代](docs/next-steps.md)在本仓库维护。
一会话一个主要领域，用户持续直接指导；跨域使用同一 Harness 中可直接交互的独立任务。

下一轮优先完成可分发安装/更新、统一领域内容发布入口和经验发布策略，再用一个真实跨域任务验证会话隔离与通信。

本仓库由 VAWS 原地更名，保留正常 Git 历史和既有材料。
旧 workspace/bootstrap、源码托管、自动更新器、客户端 Hook/MCP 接线与自动加载的业务 Skill 已从当前树删除。
各组件直接使用新包名、导入名和配置，不提供旧名别名或旧安装通道。
业务方法后续按领域重新整理进插件与知识库，旧实现仅保留在 Git 历史中。
历史验证只证明其记录的版本与范围。

[English](README.en.md)

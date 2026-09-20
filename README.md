# MindIE Agent

通过领域上下文、稳定的远端工具，以及知识与经验反馈闭环，帮助 Agent 完成 Ascend 开发任务。

**使用入口：[Codex Plugin](https://github.com/mindie-agent/mindie-agent-codex)。**
在自己的业务仓库或 Harness 原生任务中显式调用插件。知识服务以及启用贡献后的整理脱敏在本机运行；远端通过 remote-dev 提供执行环境。当前仍是发布前重构，默认不采集。

## 当前进展

首个领域为 vLLM / vLLM-Ascend。共享知识生命周期重构已合入，Codex 的原生只读使用及跨版本任务/远端作业接续已验证；Kimi 和 Claude Code 在独立仓库开发和实机验收。

[统一实施进度](docs/implementation-status.md)区分实现、原生宿主、真实发布和新任务使用证据。历史 NPU 验收不自动证明当前重构版本；三个适配器仍有最终 Hook/贡献链路和 Windows 实机工作待完成。

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

[Issue #195](https://github.com/mindie-agent/mindie-agent/issues/195) 为架构基线，遵循[设计原则](docs/design-principles.md)。[目标架构](docs/architecture.md)与[后续迭代](docs/next-steps.md)在本仓库维护。
一会话一个主要领域，用户持续直接指导；跨域使用同一 Harness 中可直接交互的独立任务。

当前优先完成三个适配器的入口、Hook/MCP、更新和知识闭环实机验收；旧业务 Skill 与 profiling 暂缓。所有设计取舍优先遵守九条原则，常规任务不承担额外强制流程。

本仓库由 VAWS 原地更名，保留正常 Git 历史和既有材料。
旧 workspace/bootstrap、源码托管、自动更新器、客户端 Hook/MCP 接线与自动加载的业务 Skill 已从当前树删除。
各组件直接使用新包名、导入名和配置，不提供旧名别名或旧安装通道。
业务方法后续按领域重新整理进插件与知识库，旧实现仅保留在 Git 历史中。
历史验证只证明其记录的版本与范围。

[English](README.en.md)

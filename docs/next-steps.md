# MindIE Agent 演进路线与下一步计划

[English](next-steps.en.md) · [返回文档中心](README.md)

系统整体架构与知识闭环设计请参阅 [系统架构与模块分工](architecture.md) 与 [知识与经验闭环设计](knowledge-system.md)，工程准则请参阅 [工程设计原则与演进准则](design-principles.md)。

当前正式发布版本为 [`0.0.2`](releases/0.0.2.md)（主产品与 Codex、Claude Code、Kimi Code、DSH 四个宿主插件统一版本，底层共享组件与 `mindie-bench` 维护独立版本序列；历史首发记录见 [`0.0.1`](releases/0.0.1.md)）。在 `0.0.2` 中，我们完成了跨仓库核心状态机精简、统一贡献与故障上报开关收敛、固定依赖安装闭环，并建立起十个代码仓库随 Release 自动交付基准测试的机制。

---

## 下一阶段推进重点

1. **`0.0.3` 知识检索时延与上下文效率优化**
   - 在 `0.0.2` 真机评测中，接入 `mindie-knowledge` 将 `dp2` 与 `dsh` 解题数从 `2/3` 提升至 `3/3`，但检索与按需分块精读在长上下文下带来了额外耗时。`0.0.3` 将重点优化检索召回粒度与上下文组织方式，在保持解题增益的同时降低检索时延开销。
2. **宿主体验与测试效率持续改进**
   - 持续跟踪统一贡献开关下的知识 PR 发布与后台故障上报运行表现，优先修复真实开发场景中触发的工具异常，并扩展跨平台宿主自动升级验证。
   - 优化 `remote-dev` 在常备 A2/A3 集群上的实机集成测试套件执行编排，将整批测试耗时从当前的约 51 秒收敛至 Tier 2 的 25 秒目标区间内。
3. **领域知识、性能剖析/仿真（`profiler` / `sim`）与开箱即用 Skills 扩展**
   - 在 [`knowledge-vllm-ascend`](https://github.com/mindie-agent/knowledge-vllm-ascend)、[`knowledge-operators`](https://github.com/mindie-agent/knowledge-operators) 与 [`awesome-mindie-skills`](https://github.com/mindie-agent/awesome-mindie-skills) 中继续扩充面向昇腾 AI Infra 全流程（架构设计、`vLLM-Ascend` 特性开发、`AscendC`/`Triton` 算子实现、精度比对与 Profiling 调优）的分级知识单元与专项指南。
   - 推进独立建仓的实测剖析组件 [`profiler`](https://github.com/mindie-agent/profiler)（`mindie-profiler`）与四层理论仿真求解组件 [`sim`](https://github.com/mindie-agent/sim)（`mindie-sim`）与 [`mindie-bench`](https://github.com/mindie-agent/mindie-bench) 的闭环集成评测。
4. **远端环境编排（`coordinator`）与宿主插件的按需演进**
   - 当前 [`coordinator`](https://github.com/mindie-agent/coordinator)（面向 Agent 的 SSH 主机管理、无代理 NPU/节点探测、容器绑定与租约仲裁）与 [`npu-top`](https://github.com/mindie-agent/npu-top)（面向开发者的 Web 实时监控台与 90 天热力图）作为按需独立安装的组件提供服务，四个宿主插件默认打包 `knowledge`、`remote-dev` 与 `diagnostics`。
   - 后续如将 `coordinator` 工具纳入宿主插件默认工具列表，将单独完成依赖锁定、工具注册与多宿主实机验收。
5. **上游宿主 CLI 问题跟进**
   - 持续跟踪 OpenAI Codex CLI 在中断子代理（`spawn_agent`）时向在途 MCP 工具调用传递取消信号的上游修复进展；待上游合入发布后及时验证并更新 `harness-compatibility.json` 版本区间。

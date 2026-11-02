# 从 MindIE 发起算子开发

用户使用 `/mindie-agent`（Codex 也可用 `$mindie-agent`）描述目标算子、输入源码与目标环境。当前 Agent 读取已安装的 `ascend-op-workflow` 后，沿用 MindIE 原生工具完成 shape/workload、生成、优化与结果回收。

```text
/mindie-agent 为指定算子准备 workload，生成 AscendC 并做有界优化。
使用指定环境；默认由 Codex 执行，沿用已有任务与预算。
```

## 安装与执行

[独立 workflow 仓](https://github.com/grandolantow/operator-shape-derivation) 维护技能、安装器和归档 CLI；CANNBot 是另一个独立的外部依赖。workflow/shape 可以先安装，实际生成或优化需要 CANNBot 时，已有 checkout 直接复用，缺少则询问是否安装或指定已有位置。用户选择安装后复用 CANNBot 的原安装入口；拒绝时继续可独立完成的 shape/workload，说明依赖缺失。

生成与优化默认由 Codex 读取 CANNBot 原指引并使用实际工具执行，Claude 为显式选配。默认路径不要求 Claude、Node、Claude 会话或 Hook。开始时简短提示：生成和多轮优化的 token 消耗较大，建议常规代码模型和中等 effort；复杂设计或关键正确性问题再局部提升。模型与 effort 采用当前任务选择，不固化历史实跑配置。

详细安装、CANNBot 资源位置、阶段交接及恢复命令以 workflow 仓的 `docs/INSTALL.md` 和 `skills/ascend-op-workflow/references/mindie.md` 为准。技能需要在当前任务工作区被宿主发现或被明确引用；MCP 本身不会自动安装或注入远端技能。

## 职责与结果

- workflow 管理父任务、workload、合同、固定生成基线 G、总预算和最终验收。`prepare` 仅准备交接，真正的生成与优化由 Agent 发起工具调用。
- CANNBot 保持原状，提供原生成流程、唯一的世界树、候选谱系和评测器；必要接入适配留在 workflow，不修改或同步 CANNBot 内的副本。
- MindIE 原生 remote-dev 管理实际远端作业、输出和取消。workflow 的 `execution-links.json` 只关联 preparation、真实 job、进化目录及归档 result；Claude session 仅选配路径需要。
- 首个全量正确版本立即冻结 G，再实测验收。默认 auto 达到生成目标即交付 G；性能有效但未达标时进入已授权的轻量优化，显式 full 持续优化。最终回收源码、完整 case 结果、原始评测证据、G/O 性能和复现方法；精度通过、性能有效、目标达成分别报告，目标未达保留 TARGET_UNMET。

重连先查询原 job 与 checkpoint，沿用原父任务、固定 G、世界树和剩余预算；不重复提交或重新初始化。取消使用执行层对本任务作业的原接口，不影响其他任务。

本主仓只提供入口与职责说明，不承载 workflow Skill、安装器、启动脚本、MCP 服务、容器配置或实验数据。宿主插件沿用现有工作区技能机制，真实入口验收发现路由缺口后再作必要修改。

## 验收边界

2026-10-31，独立 workflow 的新 FP32 Add 任务经 MindIE 原生远端工具完成生成及一轮一个候选优化。G、O 各通过全量 10 例直调与 Torch 正确性验证，首个全量正确 G 在性能采样前冻结。初始 GM(R/G)=0.260728362，生成目标未达；随 workflow 发布的 adapter 保留原生分数下限错误，仅兼容已知阈值，真实分数不改写，预约、执行和原生 refine/session 验证完成。固定 GM(G/O)=0.959872936×，优化目标未达，保留 G。该指标为包含正常调用提交间隙的设备流事件耗时，不是纯 kernel 时长。

父归档验证通过，原生 coordinator 的租约申请、续期和释放成功，开发作业及后代进程全部结束。MindIE 运行时和 CANNBot 源码未修改；必要适配已随独立 workflow 的 [PR #4](https://github.com/grandolantow/operator-shape-derivation/pull/4) 合入 main。启动前确认 MindIE 原生远端工具可用；本次版本/路径及组件入口修复留在环境记录中，不作为通用安装步骤。

历史 2026-10-28 默认 Codex SDPA 实跑完成新 workload、生成、一轮一个候选优化、最终复测和父任务归档；G/O 全 50 例精度及 24 项双流检查通过。固定 G/O=1.017841574×，目标 1.5× 未达，性能未验证独占。独立原生 Codex CLI 新会话另验证了入口发现、CANNBot 缺失时的询问和拒绝安装后继续准备 workload。

历史原 CANNBot 校验拒绝 best_score<1，HTML 遇到 hw_params=null 失败；前者已有 workflow 窄兼容，后者未在本次重测。HTML 仍为可选展示，失败时交付 Markdown、JSON 和原始证据，单列状态；父归档通过不代表性能达标或所有原生门禁通过。

短 CPU 作业已验证两个独立客户端重连原 job、取消后父子进程清理及不影响另一作业。强制网络中断后的在途优化恢复、Claude 实际 API 和多宿主兼容仍未验证；本次可选 release updater 仍报 release_selection 告警。一次环境实跑不证明所有新安装或 SDK 版本组合均兼容。

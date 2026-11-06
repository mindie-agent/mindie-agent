#!/usr/bin/env python3
"""Synchronize and verify release versions across MindIE Agent docs, releases, and READMEs.

[Role]
For an explicitly selected product combination, reads channels/0.1.json and cross-checks
latest formal GitHub Releases via REST API, and synchronizes or verifies channel internal
summaries, release notes (docs/releases/<patch>.md & .en.md), docs/*.md version pins, and
README marker blocks across mindie-agent and mindie-agent/.github.

[Invariants]
- channels/0.1.json owns the selected product combination's track, patch version,
  component/plugin tags and corpus revisions; independent releases do not rewrite it.
- Bounded HTML comment markers (<!-- mindie-org-versions:<id>:start/end -->) must wrap
  every generated section; missing or unbalanced markers raise an immediate RuntimeError.
- All file writes preserve Unix LF (\n) line endings and UTF-8 encoding without silent
  fallback on missing manifest keys or network errors (unless --offline is specified).

[Timeouts & Locks]
- Optional GitHub REST API checks enforce a strict 15-second per-request HTTP timeout.
- Pure local file verification/rewriting completes in < 1 second with zero locks.

[Side-Effect Policy]
- In --check mode, strictly read-only; exits non-zero if any managed file or live release
  drifts from channels/0.1.json. In --write mode, updates only explicitly targeted files.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

from sibling_readme_sync import process_markdown_file as process_file
from sibling_readme_sync import sync_docs_versions, sync_sibling_readmes

ORG = "mindie-agent"
HTTP_TIMEOUT_SECONDS = 15

REPOS: dict[str, tuple[str, str]] = {
    "diagnostics": ("mindie-agent/diagnostics", "shared_component"),
    "debugger": ("mindie-agent/debugger", "shared_component"),
    "profiler": ("mindie-agent/profiler", "shared_component"),
    "sim": ("mindie-agent/sim", "shared_component"),
    "npu-top": ("mindie-agent/npu-top", "shared_component"),
    "remote-dev": ("mindie-agent/remote-dev", "shared_component"),
    "knowledge": ("mindie-agent/knowledge", "shared_component"),
    "coordinator": ("mindie-agent/coordinator", "shared_component"),
    "mindie-agent-codex": ("mindie-agent/mindie-agent-codex", "harness_plugin"),
    "mindie-agent-cc": ("mindie-agent/mindie-agent-cc", "harness_plugin"),
    "mindie-agent-kimi": ("mindie-agent/mindie-agent-kimi", "harness_plugin"),
    "mindie-agent-dsh": ("mindie-agent/mindie-agent-dsh", "harness_plugin"),
    "mindie-agent-agy": ("mindie-agent/mindie-agent-agy", "harness_plugin"),
    "mindie-agent-wb": ("mindie-agent/mindie-agent-wb", "harness_plugin"),
    "mindie-bench": ("mindie-agent/mindie-bench", "evaluation_runner"),
    "knowledge-infer-core": ("mindie-agent/knowledge-infer-core", "knowledge_corpus"),
    "knowledge-operators": ("mindie-agent/knowledge-operators", "knowledge_corpus"),
    "knowledge-vllm-ascend": ("mindie-agent/knowledge-vllm-ascend", "knowledge_corpus"),
    "knowledge-xllm": ("mindie-agent/knowledge-xllm", "knowledge_corpus"),
    "knowledge-mindie-sd": ("mindie-agent/knowledge-mindie-sd", "knowledge_corpus"),
    "knowledge-infer-distributed": ("mindie-agent/knowledge-infer-distributed", "knowledge_corpus"),
    "knowledge-infer-observability": ("mindie-agent/knowledge-infer-observability", "knowledge_corpus"),
    "knowledge-infer-ops-compat": ("mindie-agent/knowledge-infer-ops-compat", "knowledge_corpus"),
    "knowledge-agent-engineering": ("mindie-agent/knowledge-agent-engineering", "knowledge_corpus"),
}


def load_channel_manifest(channel_path: Path) -> dict:
    if not channel_path.is_file():
        raise RuntimeError(f"Channel manifest not found: {channel_path}")
    data = json.loads(channel_path.read_text(encoding="utf-8"))
    for key in ("track", "milestone_version", "current_patch_version", "components", "corpora"):
        if key not in data:
            raise RuntimeError(f"Missing required key '{key}' in {channel_path}")
    return data


def github_get_latest_tag(repo: str, token: str | None) -> str:
    url = f"https://api.github.com/repos/{ORG}/{repo}/releases/latest"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "mindie-agent-sync-org-versions",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            return str(payload.get("tag_name") or "")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API HTTP {exc.code} for {repo}: {body}") from exc


def verify_live_releases(manifest: dict, token: str | None) -> list[str]:
    errors: list[str] = []
    expected_main = f"v{manifest['current_patch_version']}"
    live_main = github_get_latest_tag("mindie-agent", token)
    if live_main != expected_main:
        errors.append(f"mindie-agent: channels/0.1.json has {expected_main}, GitHub latest release is {live_main}")

    for name, comp in manifest["components"].items():
        expected_tag = str(comp["tag"])
        live_tag = github_get_latest_tag(name, token)
        if live_tag != expected_tag:
            errors.append(f"{name}: channels/0.1.json has {expected_tag}, GitHub latest release is {live_tag}")
    return errors


def rel_link(repo: str, tag: str) -> str:
    return f"[`{tag}`](https://github.com/{ORG}/{repo}/releases/tag/{tag})"


def corpus_link(repo: str, commit: str, units: int, lang: str) -> str:
    short = commit[:8]
    unit_label = f"{units} 单元" if lang == "zh" else f"{units} units"
    return f"{unit_label} · [`{short}`](https://github.com/{ORG}/{repo}/tree/{commit})"


def render_main_badges_zh(m: dict) -> str:
    v = m["current_patch_version"]
    notes = m.get("release_notes", f"docs/releases/{v}.md")
    return "\n".join(
        [
            '<p align="center">',
            f'  <a href="https://github.com/mindie-agent/mindie-agent/blob/main/{notes}"><img src="https://img.shields.io/badge/release-v{v}-7045F5.svg" alt="Release v{v}"></a>',
            '  <a href="https://github.com/mindie-agent/mindie-agent-cc"><img src="https://img.shields.io/badge/Claude_Code-Plugin-D97757.svg" alt="Claude Code Plugin"></a>',
            '  <a href="https://github.com/mindie-agent/mindie-agent-codex"><img src="https://img.shields.io/badge/OpenAI_Codex-Plugin-10A37F.svg" alt="OpenAI Codex Plugin"></a>',
            '  <a href="https://github.com/mindie-agent/mindie-agent-kimi"><img src="https://img.shields.io/badge/Kimi_Code-Plugin-2563EB.svg" alt="Kimi Code Plugin"></a>',
            '  <a href="https://github.com/mindie-agent/mindie-agent-dsh"><img src="https://img.shields.io/badge/DeepSeek_Harness-Plugin-0EA5E9.svg" alt="DeepSeek Harness Plugin"></a>',
            '  <a href="https://github.com/mindie-agent/mindie-agent-agy"><img src="https://img.shields.io/badge/Google_Antigravity-Plugin-4285F4.svg" alt="Google Antigravity Plugin"></a>',
            '  <a href="https://github.com/mindie-agent/mindie-agent-wb"><img src="https://img.shields.io/badge/Tencent_WorkBuddy-Plugin-0EC8A9.svg" alt="Tencent WorkBuddy Plugin"></a>',
            '  <a href="https://github.com/mindie-agent/awesome-mindie-skills"><img src="https://img.shields.io/badge/Ascend_AI_Infra-vLLM--Ascend_%7C_AscendC_%7C_Triton-C7000B.svg" alt="Ascend NPU AI Infra"></a>',
            "</p>",
        ]
    )


def render_main_badges_en(m: dict) -> str:
    v = m["current_patch_version"]
    notes_en = m.get("release_notes_en", f"docs/releases/{v}.en.md")
    return "\n".join(
        [
            '<p align="center">',
            f'  <a href="https://github.com/mindie-agent/mindie-agent/blob/main/{notes_en}"><img src="https://img.shields.io/badge/release-v{v}-7045F5.svg" alt="Release v{v}"></a>',
            '  <a href="https://github.com/mindie-agent/mindie-agent-cc"><img src="https://img.shields.io/badge/Claude_Code-Plugin-D97757.svg" alt="Claude Code Plugin"></a>',
            '  <a href="https://github.com/mindie-agent/mindie-agent-codex"><img src="https://img.shields.io/badge/OpenAI_Codex-Plugin-10A37F.svg" alt="OpenAI Codex Plugin"></a>',
            '  <a href="https://github.com/mindie-agent/mindie-agent-kimi"><img src="https://img.shields.io/badge/Kimi_Code-Plugin-2563EB.svg" alt="Kimi Code Plugin"></a>',
            '  <a href="https://github.com/mindie-agent/mindie-agent-dsh"><img src="https://img.shields.io/badge/DeepSeek_Harness-Plugin-0EA5E9.svg" alt="DeepSeek Harness Plugin"></a>',
            '  <a href="https://github.com/mindie-agent/mindie-agent-agy"><img src="https://img.shields.io/badge/Google_Antigravity-Plugin-4285F4.svg" alt="Google Antigravity Plugin"></a>',
            '  <a href="https://github.com/mindie-agent/mindie-agent-wb"><img src="https://img.shields.io/badge/Tencent_WorkBuddy-Plugin-0EC8A9.svg" alt="Tencent WorkBuddy Plugin"></a>',
            '  <a href="https://github.com/mindie-agent/awesome-mindie-skills"><img src="https://img.shields.io/badge/Ascend_AI_Infra-vLLM--Ascend_%7C_AscendC_%7C_Triton-C7000B.svg" alt="Ascend NPU AI Infra"></a>',
            "</p>",
        ]
    )


def render_main_ecosystem_zh(m: dict) -> str:
    v_main = f"v{m['current_patch_version']}"
    c = m["components"]
    corp = m["corpora"]
    return "\n".join(
        [
            "### 1. 产品总入口、评测基准与社区生态",
            "",
            "| 仓库 | 当前版本 | 定位与核心职责 |",
            "| --- | --- | --- |",
            f"| **[`mindie-agent`](https://github.com/mindie-agent/mindie-agent)** *(本仓库)* | {rel_link('mindie-agent', v_main)} | 顶层产品入口、整体架构、工程设计原则、跨组件发布兼容契约与正式发行版记录 |",
            f"| **[`mindie-bench`](https://github.com/mindie-agent/mindie-bench)** | {rel_link('mindie-bench', c['mindie-bench']['tag'])} | 独立评测框架与真机基准套件：20 个行为级验证任务（109 项三态与辅助变体对照）、预置准入脚手架（Gate Runner）、隔离宿主运行（原生知识评测接入与 `zsh` 临时目录隔离）、组件级基准、跨任务知识复用及端到端总工程成本校验 |",
            "| **[`awesome-mindie-skills`](https://github.com/mindie-agent/awesome-mindie-skills)** | [`main`](https://github.com/mindie-agent/awesome-mindie-skills) | 面向昇腾 NPU AI Infra 全流程的高质量开源 Agent Skills 精选目录（现已覆盖 `vLLM-Ascend`、`AscendC`/`Triton` 算子开发、精度测试与性能调优，持续扩展中） |",
            "| **[`vllm-ascend-workspace`](https://github.com/mindie-agent/vllm-ascend-workspace)** | [`main`](https://github.com/mindie-agent/vllm-ascend-workspace) | 轻量可定制的 `vLLM` + `vLLM-Ascend` 本地多任务开发工作区，支持独立 Git Worktree 隔离与 MindIE Agent 集成 |",
            "",
            "### 2. 原生客户端插件（Harness Adapters）",
            "",
            "| 仓库 | 适用宿主 | 当前版本 | 定位与核心职责 |",
            "| --- | --- | --- | --- |",
            f"| **[`mindie-agent-cc`](https://github.com/mindie-agent/mindie-agent-cc)** | **Claude Code** | {rel_link('mindie-agent-cc', c['mindie-agent-cc']['tag'])} | Claude Code 原生插件：生命周期 Hook、MCP 服务桥接与运行时版本锁定 |",
            f"| **[`mindie-agent-codex`](https://github.com/mindie-agent/mindie-agent-codex)** | **OpenAI Codex CLI** | {rel_link('mindie-agent-codex', c['mindie-agent-codex']['tag'])} | OpenAI Codex CLI 原生插件：Marketplace 安装、会话记录增量脱敏采集与 MCP 服务管理 |",
            f"| **[`mindie-agent-kimi`](https://github.com/mindie-agent/mindie-agent-kimi)** | **Kimi Code CLI** | {rel_link('mindie-agent-kimi', c['mindie-agent-kimi']['tag'])} | Kimi Code 原生插件：运行时原子版本切换、会话记录脱敏采集与 MCP 桥接 |",
            f"| **[`mindie-agent-dsh`](https://github.com/mindie-agent/mindie-agent-dsh)** | **DeepSeek Harness (DSH)** | {rel_link('mindie-agent-dsh', c['mindie-agent-dsh']['tag'])} | DSH 原生插件：`/mindie-agent` Skill、知识检索工具、生命周期桥接与 `remote-dev` 集成 |",
            f"| **[`mindie-agent-agy`](https://github.com/mindie-agent/mindie-agent-agy)** | **Google Antigravity** | {rel_link('mindie-agent-agy', c['mindie-agent-agy']['tag'])} | Google Antigravity 原生插件：`/mindie-agent` 会话租约门控、原生远端工具别名、8 大共享组件 MCP 桥接与 Brain Transcript 脱敏采集 |",
            f"| **[`mindie-agent-wb`](https://github.com/mindie-agent/mindie-agent-wb)** | **Tencent WorkBuddy** | {rel_link('mindie-agent-wb', c['mindie-agent-wb']['tag'])} | Tencent WorkBuddy / CodeBuddy 原生插件：双入口挂接（WorkBuddy Connector + CodeBuddy 原生插件）、`/mindie-agent` 会话门控与 8 大共享组件 MCP 桥接 |",
            "",
            "### 3. 共享运行时组件底座（Shared Runtime Components）",
            "",
            "| 仓库 | Python 包 / 入口 | 当前版本 | 定位与核心职责 |",
            "| --- | --- | --- | --- |",
            f"| **[`knowledge`](https://github.com/mindie-agent/knowledge)** | `mindie-knowledge` | {rel_link('knowledge', c['knowledge']['tag'])} | 结构化分级知识单元（L1–L4）管理、按信息缺口条件检索、批量 `refs` 精读与共享 `known_refs` / `token_budget` 预算、负面尝试历史（`rejected_history`）与受影响组件（`affected_components`）溯源、双层脱敏采集与社区 PR 发布 |",
            f"| **[`remote-dev`](https://github.com/mindie-agent/remote-dev)** | `remote-dev` | {rel_link('remote-dev', c['remote-dev']['tag'])} | SSH 远端文件读写与命令执行、共享用户私有 `~/.mindie/ssh/id_ed25519` 凭据回退与公钥维护、破坏性命令安全拦截门禁、Docker 容器直连、后台长作业管理、连接复用与产物同步 |",
            f"| **[`coordinator`](https://github.com/mindie-agent/coordinator)** | `mindie-coordinator` | {rel_link('coordinator', c['coordinator']['tag'])} | 远端昇腾环境与多 Agent 资源协调器：SSH 主机/多机互通配置、容器开通与绑定、NPU 拓扑探测（兼容 A2/A3 双 Die/A5）、HCCL/RoCE 预检、单 Die 显存租约预算与并发编译槽位控制及端口防冲突 |",
            f"| **[`profiler`](https://github.com/mindie-agent/profiler)** | `mindie-profiler` / `mindie_profiler` | {rel_link('profiler', c['profiler']['tag'])} | 昇腾 Profiling 采集与解析组件：受控采集、`msprof` 产物就地只读分析（`inventory / analyze / correlate / compare / sql / camodel / kernels`）、`analyze_profiling --structure` 基于 `mindie-model-structure/1` 的三态拓扑对齐（`aligned / declared_only / unattributed_observed`）与 Decode/Prefill 自动切分、显存拆解及跨版本对比 CLI |",
            f"| **[`sim`](https://github.com/mindie-agent/sim)** | `mindie-sim` / `mindie_sim` | {rel_link('sim', c['sim']['tag'])} | 硬件无关的五层因果性能建模组件：统一组合硬件资源、算子族、子图、纯模型成本与服务约束（覆盖 `DP × TP × EP × PP × DCP / DSA-CP / PCP` 与 PD 分离），支持确定性 Case 合成（`compose`）、`async_scheduling` 显存延迟释放、4D 效率拆解（`Cube_MFU / Vec_MFU / MBU / Link_Util / CV_Overlap`）、SLA/PD Pareto 求解（`sla / sweep`）、多 DP 偏斜屏障力学（`skew`）及 Wave 5 跨 A2/A3/A5 1,653 份实测 Profile 100% <=10% 样本内校准与独立 856 例 DSH 集群评测（整体 841/856=98.25%，其中 561 例 Held-out 盲测 546/561=97.33% <=15%） |",
            f"| **[`npu-top`](https://github.com/mindie-agent/npu-top)** | `npu-top` | {rel_link('npu-top', c['npu-top']['tag'])} | 昇腾 NPU 可视化监控看板：支持 A2 / A3 / A5 集群监控、共享读取 `coordinator` 的 `machines.json` 与 `~/.mindie/ssh` 凭据回退，提供本地回环 Web 实时状态页（`127.0.0.1:8788`）、TUI、CLI/MCP 与 90 天 SQLite 利用率热力图 |",
            f"| **[`diagnostics`](https://github.com/mindie-agent/diagnostics)** | `mindie-diagnostics` / `mindie_diagnostics` | {rel_link('diagnostics', c['diagnostics']['tag'])} | 故障诊断与日志组件：支持 CANN 错误码与 `plog` 根因分析、4×1 MiB 本地轮转日志、离线脱敏诊断包与带 2 次有界外发对账重试的可选 GitHub Issue 白名单上报 |",
            f"| **[`debugger`](https://github.com/mindie-agent/debugger)** | `mindie-debugger` / `mindie_debugger` | {rel_link('debugger', c['debugger']['tag'])} | 目标昇腾 NPU 负载故障分诊与精度调试组件：CANN/`plog` 确定性故障根因分诊（`npu_fault_triage`）、三原语精度/内存踩踏定位（`precision`：`npu-watch` / `call-repro` / `lockstep-diff`）与 `ACLGraph` 零同步图内重放 Dump / 捕获守卫 / 静态地址追踪（`aclgraph`） |",
            "",
            "### 4. 昇腾领域公共知识库（Public Domain Knowledge Corpora）",
            "",
            "所有公共知识库均采用 `mindie-graded-unit/1` 结构化分级单元格式（`L1` 事实与约束标准 · `L2` 标准排障与开发规程 · `L3` 多阶段工程工作流 · `L4` 深度调优模式），附带适用条件（`applicability`）与实证依据：",
            "",
            "| 仓库 | 领域标识 (`domain`) | 知识规模与基线提交 | 定位与覆盖范围 |",
            "| --- | --- | --- | --- |",
            f"| **[`knowledge-vllm-ascend`](https://github.com/mindie-agent/knowledge-vllm-ascend)** | `vllm-ascend` | {corpus_link('knowledge-vllm-ascend', corp['knowledge-vllm-ascend']['commit'], corp['knowledge-vllm-ascend']['units'], 'zh')} | `vLLM-Ascend` 与 `vLLM-Omni` 领域工程知识库：覆盖新模型 0day 接入、PD 分离、MoE EP/MC2、量化与投机解码、ACLGraph/TorchAir，以及 `vllm-omni` 多阶段全模态（`Thinker -> Talker -> Code2Wav` / AR+DiT / TTS / Duplex）流水线调优 |",
            f"| **[`knowledge-xllm`](https://github.com/mindie-agent/knowledge-xllm)** | `xllm` | {corpus_link('knowledge-xllm', corp['knowledge-xllm']['commit'], corp['knowledge-xllm']['units'], 'zh')} | `xLLM` 全栈（`xllm` / `xllm-ops` / `xllm-service` / `xllm-workflow`）昇腾工程知识库：覆盖 C++ 原生 `ModelRegistry`、`xTensor` VMM 2 MB 物理页池与权重热切换、Piecewise ACLGraph、MTP/Eagle-3/Suffix 投机解码、48 个 AscendC 算子与 A5 (`dav-c310`) TileLang AOT 编译、Brpc/etcd/Mooncake PD 分离路由与 `OneRec` 生成式推荐流水线 |",
            f"| **[`knowledge-mindie-sd`](https://github.com/mindie-agent/knowledge-mindie-sd)** | `mindie-sd` | {corpus_link('knowledge-mindie-sd', corp['knowledge-mindie-sd']['commit'], corp['knowledge-mindie-sd']['units'], 'zh')} | `Ascend/MindIE-SD`（`mindiesd`）多模态扩散生成框架知识库：覆盖 `AttentionConfig`/`Register` 派发、块稀疏注意力（`RainFusion` V1–V3 / `Ada-BSA` / `EagleQBSA`）、跨步缓存（`DiTCache` / `Cache-DiT` / `TaylorSeer`）、时步感知动态量化 + `Laurel`、Ulysses/Ring/CFG 混合并行、3D 因果 VAE 状态切片解码、`torch_npu._inductor` 图编译及 S0–S6 自动调优门禁 |",
            f"| **[`knowledge-operators`](https://github.com/mindie-agent/knowledge-operators)** | `operators` | {corpus_link('knowledge-operators', corp['knowledge-operators']['commit'], corp['knowledge-operators']['units'], 'zh')} | 昇腾算子工程知识库：覆盖 910B / 910C (A3) / 950 (A5) 硬件约束、`AscendC`、`Triton-Ascend`、TileLang、PyPTO、Catlass、FlashAttention/MLA 与 Matmul/MoE 融合算子 |",
            f"| **[`knowledge-infer-core`](https://github.com/mindie-agent/knowledge-infer-core)** | `infer-core` | {corpus_link('knowledge-infer-core', corp['knowledge-infer-core']['commit'], corp['knowledge-infer-core']['units'], 'zh')} | 昇腾推理服务与引擎核心知识库：覆盖 `cann-recipes-infer` 26 个模型家族优化 Recipe、16 个 `model-infer-*` Skill、公共加速模块与 `Ascend/msagent` 量化/精度诊断工作流 |",
            f"| **[`knowledge-infer-distributed`](https://github.com/mindie-agent/knowledge-infer-distributed)** | `infer-distributed` | {corpus_link('knowledge-infer-distributed', corp['knowledge-infer-distributed']['commit'], corp['knowledge-infer-distributed']['units'], 'zh')} | 分布式推理与集合通信知识库：覆盖 HCCL 通信排障、RoCE/HCCS 拓扑、SHMEM、Mooncake/Yuanrong 传输，以及多机 `DP/TP/EP/PP/DCP/DSA-CP/PCP` 与 DiT Ulysses/Ring/CFG 混合并行及功耗降频治理 |",
            f"| **[`knowledge-infer-observability`](https://github.com/mindie-agent/knowledge-infer-observability)** | `infer-observability` | {corpus_link('knowledge-infer-observability', corp['knowledge-infer-observability']['commit'], corp['knowledge-infer-observability']['units'], 'zh')} | 推理可观测性、诊断与评测知识库：覆盖 CANN/`plog`/Device 报错定位、`msprof` 性能拆解、容量/性能仿真，以及窗口化交错 A/B/A 性能门禁（`perf-gate`）与三级图像/视频生成精度门禁（`accuracy-gate`） |",
            f"| **[`knowledge-infer-ops-compat`](https://github.com/mindie-agent/knowledge-infer-ops-compat)** | `infer-ops-compat` | {corpus_link('knowledge-infer-ops-compat', corp['knowledge-infer-ops-compat']['commit'], corp['knowledge-infer-ops-compat']['units'], 'zh')} | 图编译、算子注册与迁移兼容知识库：覆盖 TorchAir/ACLGraph 图捕获、`torch_npu._inductor` Pattern Pass 开发、两阶段（API 优先→图编译）框架集成、CUDA 至昇腾迁移与容器/集群部署 |",
            f"| **[`knowledge-agent-engineering`](https://github.com/mindie-agent/knowledge-agent-engineering)** | `agent-engineering` | {corpus_link('knowledge-agent-engineering', corp['knowledge-agent-engineering']['commit'], corp['knowledge-agent-engineering']['units'], 'zh')} | Agent 工程与治理知识库：覆盖多 Agent 协同编排、SOTA 探索循环、`ais_bench` 核心集压缩、Git Bisect 自动修 Bug、知识库质量门禁（`kb-lint`）、双层隐私脱敏与真机基准评测方法 |",
        ]
    )


def render_main_ecosystem_en(m: dict) -> str:
    v_main = f"v{m['current_patch_version']}"
    c = m["components"]
    corp = m["corpora"]
    return "\n".join(
        [
            "### 1. Product Entry, Benchmarks & Community Catalogue",
            "",
            "| Repository | Version | Role |",
            "| --- | --- | --- |",
            f"| **[`mindie-agent`](https://github.com/mindie-agent/mindie-agent)** *(This Repo)* | {rel_link('mindie-agent', v_main)} | Product entry point, system architecture, engineering design principles, release compatibility contracts, and release records |",
            f"| **[`mindie-bench`](https://github.com/mindie-agent/mindie-bench)** | {rel_link('mindie-bench', c['mindie-bench']['tag'])} | End-to-end evaluation harness and live NPU benchmark suite: 20 behavioral-oracle tasks (109 3-state & helper controls), Gate Runner, isolated host runs (native knowledge evaluation wiring & `zsh` temp isolation), component benchmarks, and cross-task reuse evaluation |",
            "| **[`awesome-mindie-skills`](https://github.com/mindie-agent/awesome-mindie-skills)** | [`main`](https://github.com/mindie-agent/awesome-mindie-skills) | Curated catalogue of open-source Agent Skills for the Ascend NPU AI Infra workflow (covering `vLLM-Ascend`, `AscendC`/`Triton` kernels, accuracy testing, and profiling) |",
            "| **[`vllm-ascend-workspace`](https://github.com/mindie-agent/vllm-ascend-workspace)** | [`main`](https://github.com/mindie-agent/vllm-ascend-workspace) | Lightweight customizable local workspace for `vLLM` + `vLLM-Ascend` development with isolated task Git Worktrees and MindIE Agent integration |",
            "",
            "### 2. Native Harness Plugins",
            "",
            "| Repository | Host Client | Version | Role |",
            "| --- | --- | --- | --- |",
            f"| **[`mindie-agent-cc`](https://github.com/mindie-agent/mindie-agent-cc)** | **Claude Code** | {rel_link('mindie-agent-cc', c['mindie-agent-cc']['tag'])} | Native Claude Code plugin: lifecycle hooks, MCP stdio bridges, and pinned runtime management |",
            f"| **[`mindie-agent-codex`](https://github.com/mindie-agent/mindie-agent-codex)** | **OpenAI Codex CLI** | {rel_link('mindie-agent-codex', c['mindie-agent-codex']['tag'])} | Native OpenAI Codex CLI plugin: marketplace packaging, session redaction, and background service management |",
            f"| **[`mindie-agent-kimi`](https://github.com/mindie-agent/mindie-agent-kimi)** | **Kimi Code CLI** | {rel_link('mindie-agent-kimi', c['mindie-agent-kimi']['tag'])} | Native Kimi Code plugin: atomic version switching, redacted session capture, and MCP bridging |",
            f"| **[`mindie-agent-dsh`](https://github.com/mindie-agent/mindie-agent-dsh)** | **DeepSeek Harness (DSH)** | {rel_link('mindie-agent-dsh', c['mindie-agent-dsh']['tag'])} | Native DSH plugin: `/mindie-agent`, knowledge tools, lifecycle bridging, and `remote-dev` integration |",
            f"| **[`mindie-agent-agy`](https://github.com/mindie-agent/mindie-agent-agy)** | **Google Antigravity** | {rel_link('mindie-agent-agy', c['mindie-agent-agy']['tag'])} | Native Google Antigravity plugin: per-conversation `/mindie-agent` lease gate, native remote tool aliases, 8-component MCP bridge, and Brain transcript redaction |",
            f"| **[`mindie-agent-wb`](https://github.com/mindie-agent/mindie-agent-wb)** | **Tencent WorkBuddy** | {rel_link('mindie-agent-wb', c['mindie-agent-wb']['tag'])} | Native Tencent WorkBuddy / CodeBuddy plugin: dual-surface mounting (WorkBuddy Connector + CodeBuddy native plugin), `/mindie-agent` session gate, and 8-component MCP bridge |",
            "",
            "### 3. Shared Runtime Components",
            "",
            "| Repository | Package / CLI | Version | Role |",
            "| --- | --- | --- | --- |",
            f"| **[`knowledge`](https://github.com/mindie-agent/knowledge)** | `mindie-knowledge` | {rel_link('knowledge', c['knowledge']['tag'])} | Graded knowledge unit (L1–L4) management, information-gap retrieval, batch `refs` explanation with shared `known_refs` & `token_budget`, `rejected_history` & `affected_components` provenance, two-layer redaction, and community PR publishing |",
            f"| **[`remote-dev`](https://github.com/mindie-agent/remote-dev)** | `remote-dev` | {rel_link('remote-dev', c['remote-dev']['tag'])} | SSH file and command tools, shared user-private `~/.mindie/ssh/id_ed25519` credential fallback & public-key management, destructive command safety guard, container execution, background jobs, pooled connections, and artifact transfer |",
            f"| **[`coordinator`](https://github.com/mindie-agent/coordinator)** | `mindie-coordinator` | {rel_link('coordinator', c['coordinator']['tag'])} | SSH & remote Ascend environment manager: host/key inventory, container binding & provisioning, NPU topology probing (`mindie_probe`, A2/A3 dual-Die/A5), HCCL/RoCE preflight, per-Die HBM lease & compile slot budgets (`mindie_lease`), and managed task execution |",
            f"| **[`profiler`](https://github.com/mindie-agent/profiler)** | `mindie-profiler` / `mindie_profiler` | {rel_link('profiler', c['profiler']['tag'])} | Ascend profiling collection and in-place analysis component: controlled capture, `inventory / analyze / correlate / compare / sql / camodel / kernels` trace analysis, `analyze_profiling --structure` 3-state topology alignment (`aligned / declared_only / unattributed_observed`) on `mindie-model-structure/1`, Decode/Prefill segmentation, memory breakdown, and cross-run comparison CLI |",
            f"| **[`sim`](https://github.com/mindie-agent/sim)** | `mindie-sim` / `mindie_sim` | {rel_link('sim', c['sim']['tag'])} | Hardware-neutral 5-layer causal performance modeling component: unifies hardware resources, operator families, subgraphs, pure-model costs, and serving constraints (`DP × TP × EP × PP × DCP / DSA-CP / PCP` & PD disaggregation) with deterministic Case synthesis (`compose`), `async_scheduling` delayed KV release, 4D efficiency breakdown (`Cube_MFU / Vec_MFU / MBU / Link_Util / CV_Overlap`), SLA/PD Pareto solvers (`sla / sweep`), multi-DP skew barrier mechanics (`skew`), and Wave 5 1,653-profile A2/A3/A5 in-sample calibration (100% <=10% error) and separate 856-case DSH fleet evaluation (841/856=98.25% overall, 546/561=97.33% independent held-out <=15%) |",
            f"| **[`npu-top`](https://github.com/mindie-agent/npu-top)** | `npu-top` | {rel_link('npu-top', c['npu-top']['tag'])} | Human-facing Ascend NPU observability dashboard: supports A2 / A3 / A5 fleet monitoring with shared `coordinator` `machines.json` and `~/.mindie/ssh` credential fallback, providing a loopback web UI (`127.0.0.1:8788`), TUI, CLI/MCP, and 90-day SQLite utilization history |",
            f"| **[`diagnostics`](https://github.com/mindie-agent/diagnostics)** | `mindie-diagnostics` / `mindie_diagnostics` | {rel_link('diagnostics', c['diagnostics']['tag'])} | Local fault logging and diagnostics component: CANN/`plog` deterministic error analysis, bounded 4×1 MiB JSONL rotation, redacted support bundles, and opt-in GitHub Issue reporting with bounded 2-attempt outbound reconciliation |",
            f"| **[`debugger`](https://github.com/mindie-agent/debugger)** | `mindie-debugger` / `mindie_debugger` | {rel_link('debugger', c['debugger']['tag'])} | Target Ascend NPU fault triage and precision debugging component: deterministic CANN/`plog` fault triage (`npu_fault_triage`), 3-primitive precision/memory-stomp localization (`precision`: `npu-watch` / `call-repro` / `lockstep-diff`), and `ACLGraph` zero-sync in-graph replay dumping, capture guard & static pointer tracking (`aclgraph`) |",
            "",
            "### 4. Public Domain Knowledge Corpora",
            "",
            "All public knowledge corpora follow the `mindie-graded-unit/1` graded schema (`L1` Canonical Facts & Constraints · `L2` Standard Operating Procedures · `L3` Multi-Stage Workflows · `L4` Optimization Patterns) with explicit applicability conditions and verification evidence:",
            "",
            "| Repository | Domain (`domain`) | Units & Pinned Commit | Scope & Coverage |",
            "| --- | --- | --- | --- |",
            f"| **[`knowledge-vllm-ascend`](https://github.com/mindie-agent/knowledge-vllm-ascend)** | `vllm-ascend` | {corpus_link('knowledge-vllm-ascend', corp['knowledge-vllm-ascend']['commit'], corp['knowledge-vllm-ascend']['units'], 'en')} | `vLLM-Ascend` & `vLLM-Omni` engineering corpus: 0-day model bring-up, PD disaggregation, MoE EP/MC2, quantization, speculative decoding, ACLGraph/TorchAir, and `vllm-omni` multi-stage omni-modality (`Thinker -> Talker -> Code2Wav` / AR+DiT / TTS / Duplex) pipeline tuning |",
            f"| **[`knowledge-xllm`](https://github.com/mindie-agent/knowledge-xllm)** | `xllm` | {corpus_link('knowledge-xllm', corp['knowledge-xllm']['commit'], corp['knowledge-xllm']['units'], 'en')} | `xLLM` full-stack (`xllm` / `xllm-ops` / `xllm-service` / `xllm-workflow`) Ascend corpus: C++ native `ModelRegistry`, `xTensor` VMM 2 MB physical page pools & weight hot-switching, piecewise ACLGraph, MTP/Eagle-3/Suffix speculative decoding, 48 AscendC custom ops & A5 (`dav-c310`) TileLang AOT kernels, Brpc/etcd/Mooncake PD disaggregation, and `OneRec` recommendation pipelines |",
            f"| **[`knowledge-mindie-sd`](https://github.com/mindie-agent/knowledge-mindie-sd)** | `mindie-sd` | {corpus_link('knowledge-mindie-sd', corp['knowledge-mindie-sd']['commit'], corp['knowledge-mindie-sd']['units'], 'en')} | `Ascend/MindIE-SD` (`mindiesd`) diffusion acceleration framework corpus: `AttentionConfig`/`Register` dispatch, block-sparse attention (`RainFusion` V1–V3 / `Ada-BSA` / `EagleQBSA`), cross-step caching (`DiTCache` / `Cache-DiT` / `TaylorSeer`), timestep-aware quantization + `Laurel`, Ulysses/Ring/CFG hybrid parallelism, 3D causal VAE sliced decode, `torch_npu._inductor` graph passes, and S0–S6 auto-optimization gates |",
            f"| **[`knowledge-operators`](https://github.com/mindie-agent/knowledge-operators)** | `operators` | {corpus_link('knowledge-operators', corp['knowledge-operators']['commit'], corp['knowledge-operators']['units'], 'en')} | Ascend operators corpus: 910B / 910C (A3) / 950 (A5) hardware constraints, `AscendC`, `Triton-Ascend`, TileLang, PyPTO, Catlass, FlashAttention/MLA, and Matmul/MoE fusion |",
            f"| **[`knowledge-infer-core`](https://github.com/mindie-agent/knowledge-infer-core)** | `infer-core` | {corpus_link('knowledge-infer-core', corp['knowledge-infer-core']['commit'], corp['knowledge-infer-core']['units'], 'en')} | Ascend inference serving & engine core corpus: `cann-recipes-infer` 26 model optimization recipes, 16 `model-infer-*` skills, common acceleration modules, and `Ascend/msagent` quantization/accuracy diagnosis workflows |",
            f"| **[`knowledge-infer-distributed`](https://github.com/mindie-agent/knowledge-infer-distributed)** | `infer-distributed` | {corpus_link('knowledge-infer-distributed', corp['knowledge-infer-distributed']['commit'], corp['knowledge-infer-distributed']['units'], 'en')} | Distributed inference & collective communication corpus: HCCL troubleshooting, RoCE/HCCS topology, SHMEM, Mooncake/Yuanrong transport, and multi-node `DP/TP/EP/PP/DCP/DSA-CP/PCP` plus DiT Ulysses/Ring/CFG hybrid parallelism & power-cap mitigation |",
            f"| **[`knowledge-infer-observability`](https://github.com/mindie-agent/knowledge-infer-observability)** | `infer-observability` | {corpus_link('knowledge-infer-observability', corp['knowledge-infer-observability']['commit'], corp['knowledge-infer-observability']['units'], 'en')} | Inference observability, diagnostics & benchmarking corpus: CANN/`plog`/device fault triage, `msprof` profiling workflows, analytic simulation, Window A/B/A `perf-gate`, and 3-tier image/video `accuracy-gate` protocols |",
            f"| **[`knowledge-infer-ops-compat`](https://github.com/mindie-agent/knowledge-infer-ops-compat)** | `infer-ops-compat` | {corpus_link('knowledge-infer-ops-compat', corp['knowledge-infer-ops-compat']['commit'], corp['knowledge-infer-ops-compat']['units'], 'en')} | Graph compilation, custom op registration & migration compatibility corpus: TorchAir/ACLGraph capture, `torch_npu._inductor` pattern pass development, two-stage (`API-first, then compile`) integration, CUDA-to-Ascend migration, and cluster deployment |",
            f"| **[`knowledge-agent-engineering`](https://github.com/mindie-agent/knowledge-agent-engineering)** | `agent-engineering` | {corpus_link('knowledge-agent-engineering', corp['knowledge-agent-engineering']['commit'], corp['knowledge-agent-engineering']['units'], 'en')} | Agent engineering & governance corpus: multi-agent orchestration, SOTA exploration loops, `ais_bench` coreset compression, automated Git bisect, `kb-lint` governance, two-layer privacy redaction gates, and benchmark evaluation |",
        ]
    )


def render_org_badges(m: dict) -> str:
    v = m["current_patch_version"]
    mv = m["milestone_version"]
    notes = m.get("release_notes", f"docs/releases/{v}.md")
    return "\n".join(
        [
            '<p align="center">',
            f'  <a href="https://github.com/mindie-agent/mindie-agent/blob/main/{notes}"><img src="https://img.shields.io/github/v/release/mindie-agent/mindie-agent?label=Release&color=7045F5&style=flat-square" alt="Release v{v}"></a>',
            '  <a href="https://github.com/mindie-agent/mindie-agent-cc"><img src="https://img.shields.io/badge/Claude_Code-Plugin_Ready-D97757?style=flat-square" alt="Claude Code"></a>',
            '  <a href="https://github.com/mindie-agent/mindie-agent-codex"><img src="https://img.shields.io/badge/OpenAI_Codex-Plugin_Ready-10A37F?style=flat-square" alt="OpenAI Codex"></a>',
            '  <a href="https://github.com/mindie-agent/mindie-agent-kimi"><img src="https://img.shields.io/badge/Kimi_Code-Plugin_Ready-2563EB?style=flat-square" alt="Kimi Code"></a>',
            '  <a href="https://github.com/mindie-agent/mindie-agent-dsh"><img src="https://img.shields.io/badge/DeepSeek_Harness-Plugin_Ready-0EA5E9?style=flat-square" alt="DeepSeek Harness"></a>',
            '  <a href="https://github.com/mindie-agent/mindie-agent-agy"><img src="https://img.shields.io/badge/Google_Antigravity-Plugin_Ready-4285F4?style=flat-square" alt="Google Antigravity"></a>',
            '  <a href="https://github.com/mindie-agent/mindie-agent-wb"><img src="https://img.shields.io/badge/Tencent_WorkBuddy-Plugin_Ready-0EC8A9?style=flat-square" alt="Tencent WorkBuddy"></a>',
            '  <a href="https://github.com/mindie-agent/awesome-mindie-skills"><img src="https://img.shields.io/badge/Ascend_AI_Infra-vLLM--Ascend_%7C_AscendC_%7C_Triton-C7000B?style=flat-square" alt="Ascend AI Infra Skills"></a>',
            "</p>",
            "",
            '<p align="center">',
            '  <a href="https://github.com/mindie-agent/mindie-agent"><b>项目主入口 (Main Repo)</b></a> ·',
            f'  <a href="https://github.com/mindie-agent/mindie-agent/blob/main/{notes}"><b>v{v} 发布说明</b></a> ·',
            f'  <a href="https://github.com/mindie-agent/mindie-agent/blob/main/docs/releases/{mv}.md"><b>v{mv} 里程碑</b></a> ·',
            f'  <a href="https://github.com/mindie-agent/mindie-agent/blob/main/docs/releases/{mv}/design-philosophy.md"><b>作者自述</b></a> ·',
            '  <a href="https://github.com/mindie-agent/mindie-agent-cc"><b>Claude Code 插件</b></a> ·',
            '  <a href="https://github.com/mindie-agent/mindie-agent-codex"><b>Codex 插件</b></a> ·',
            '  <a href="https://github.com/mindie-agent/mindie-agent-kimi"><b>Kimi Code 插件</b></a> ·',
            '  <a href="https://github.com/mindie-agent/mindie-agent-dsh"><b>DSH 插件</b></a> ·',
            '  <a href="https://github.com/mindie-agent/mindie-agent-agy"><b>Antigravity 插件</b></a> ·',
            '  <a href="https://github.com/mindie-agent/mindie-agent-wb"><b>WorkBuddy 插件</b></a> ·',
            '  <a href="https://github.com/mindie-agent/mindie-bench"><b>MindIE Bench</b></a> ·',
            '  <a href="https://github.com/mindie-agent/awesome-mindie-skills"><b>Awesome MindIE Skills</b></a>',
            "</p>",
        ]
    )


def render_org_ecosystem(m: dict) -> str:
    v_main = f"v{m['current_patch_version']}"
    c = m["components"]
    corp = m["corpora"]
    return "\n".join(
        [
            "### 1. 主入口、评测基准与开发者生态（Entry, Benchmarks & Developer Ecosystem）",
            "",
            "| 仓库 / Repository | 当前版本 / Version | 定位与核心用途 / What It Does |",
            "|---|---|---|",
            f"| [`mindie-agent`](https://github.com/mindie-agent/mindie-agent) | {rel_link('mindie-agent', v_main)} | **总入口**：产品架构、工程设计原则、一句话 Agent 自动安装协议与统一版本记录 |",
            f"| [`mindie-bench`](https://github.com/mindie-agent/mindie-bench) | {rel_link('mindie-bench', c['mindie-bench']['tag'])} | **真机基准与评测框架**：20 个行为级验证任务（109 项三态与辅助变体对照）、隔离宿主运行（原生知识评测接入与 `zsh` 临时目录隔离）、组件级基准与跨任务复用评测 |",
            "| [`awesome-mindie-skills`](https://github.com/mindie-agent/awesome-mindie-skills) | [`main`](https://github.com/mindie-agent/awesome-mindie-skills) | **开箱即用技能库**：覆盖昇腾 AI Infra 开发、测试、算子实现（`AscendC` / `Triton`）与 `vLLM-Ascend` 工程的精选 Agent Skills |",
            "| [`vllm-ascend-workspace`](https://github.com/mindie-agent/vllm-ascend-workspace) | [`main`](https://github.com/mindie-agent/vllm-ascend-workspace) | **本地多任务工作区**：一键拉起 `vllm` + `vllm-ascend` 独立 Git Worktree 的开发与测试脚手架 |",
            "",
            "### 2. 原生客户端插件（Native Agent Plugins）",
            "",
            "| 仓库 / Repository | 适用宿主 / Host | 当前版本 / Version | 定位与核心用途 / What It Does |",
            "|---|---|---|---|",
            f"| [`mindie-agent-cc`](https://github.com/mindie-agent/mindie-agent-cc) | **Claude Code** | {rel_link('mindie-agent-cc', c['mindie-agent-cc']['tag'])} | Claude Code 原生插件：支持 macOS、原生 Windows 与 WSL，注册 `knowledge`、`remote` 与 `components` 三大 MCP 服务 |",
            f"| [`mindie-agent-codex`](https://github.com/mindie-agent/mindie-agent-codex) | **OpenAI Codex CLI** | {rel_link('mindie-agent-codex', c['mindie-agent-codex']['tag'])} | OpenAI Codex CLI 原生插件：支持 macOS、原生 Windows 与 WSL，提供按需知识检索、远端 NPU 开发与后台静默更新 |",
            f"| [`mindie-agent-kimi`](https://github.com/mindie-agent/mindie-agent-kimi) | **Kimi Code CLI** | {rel_link('mindie-agent-kimi', c['mindie-agent-kimi']['tag'])} | Kimi Code CLI 原生插件：提供 `/mindie-agent` 统一入口、旁路原子更新、远端 NPU 开发测试与经验闭环 |",
            f"| [`mindie-agent-dsh`](https://github.com/mindie-agent/mindie-agent-dsh) | **DeepSeek Harness (DSH)** | {rel_link('mindie-agent-dsh', c['mindie-agent-dsh']['tag'])} | DeepSeek Harness 原生插件：复用宿主插件机制组合提供 `/mindie-agent` Skill、领域知识检索、确定性组件工具与 `remote-dev` |",
            f"| [`mindie-agent-agy`](https://github.com/mindie-agent/mindie-agent-agy) | **Google Antigravity** | {rel_link('mindie-agent-agy', c['mindie-agent-agy']['tag'])} | Google Antigravity 原生插件：提供 `/mindie-agent` 会话租约门控、原生远端工具别名、8 大共享组件 MCP 桥接与 Brain Transcript 脱敏采集 |",
            f"| [`mindie-agent-wb`](https://github.com/mindie-agent/mindie-agent-wb) | **Tencent WorkBuddy** | {rel_link('mindie-agent-wb', c['mindie-agent-wb']['tag'])} | Tencent WorkBuddy / CodeBuddy 原生插件：双入口挂接（WorkBuddy Connector + CodeBuddy 原生插件）、`/mindie-agent` 会话门控与 8 大共享组件 MCP 桥接 |",
            "",
            "### 3. 核心运行时组件（Core Runtime Components）",
            "",
            "| 仓库 / Repository | Python 包 / Package | 当前版本 / Version | 定位与核心用途 / What It Does |",
            "|---|---|---|---|",
            f"| [`knowledge`](https://github.com/mindie-agent/knowledge) | `mindie-knowledge` | {rel_link('knowledge', c['knowledge']['tag'])} | **知识与经验引擎**：L1–L4 分级知识单元、按信息缺口条件检索、批量 `refs` 精读与共享 `known_refs` / `token_budget` 预算、`rejected_history` / `affected_components` 溯源、双层隐私脱敏与社区 PR 发布 |",
            f"| [`remote-dev`](https://github.com/mindie-agent/remote-dev) | `remote-dev` | {rel_link('remote-dev', c['remote-dev']['tag'])} | **SSH 远端开发引擎**：远端文件读写、精确补丁、共享 `~/.mindie/ssh/id_ed25519` 凭据回退与密钥维护、破坏性命令安全拦截门禁、容器直连、受管后台作业与产物同步 |",
            f"| [`coordinator`](https://github.com/mindie-agent/coordinator) | `mindie-coordinator` | {rel_link('coordinator', c['coordinator']['tag'])} | **昇腾 NPU 环境协调器**：SSH 主机/多机互通、容器池开通与绑定、NPU 拓扑探测（兼容 A2/A3 双 Die/A5）、HCCL/RoCE 预检、单 Die 显存租约预算与并发编译槽位控制及端口防冲突 |",
            f"| [`profiler`](https://github.com/mindie-agent/profiler) | `mindie-profiler` | {rel_link('profiler', c['profiler']['tag'])} | **昇腾实测性能剖析组件**：受控采集、`msprof` 原地只读解析（`inventory / analyze / correlate / compare / sql / camodel / kernels`）、`analyze_profiling --structure` 基于 `mindie-model-structure/1` 的三态拓扑对齐（`aligned / declared_only / unattributed_observed`）与 Decode/Prefill 自动切分 |",
            f"| [`sim`](https://github.com/mindie-agent/sim) | `mindie-sim` | {rel_link('sim', c['sim']['tag'])} | **五层因果性能建模组件**：统一建模硬件资源、算子族、子图、纯模型成本与服务约束（覆盖 `DP × TP × EP × PP × DCP / DSA-CP / PCP` 与 PD 分离），支持 `compose` Case 合成、`async_scheduling` 显存延迟释放、4D 效率拆解、SLA/PD Pareto 求解与 Wave 5 1,653 份 Profile 样本内校准及独立 856 例 DSH 集群评测 |",
            f"| [`npu-top`](https://github.com/mindie-agent/npu-top) | `npu-top` | {rel_link('npu-top', c['npu-top']['tag'])} | **NPU 集群状态看板**：支持 A2 / A3 / A5 集群监控、共享 `coordinator` 的 `machines.json` 与 `~/.mindie/ssh` 凭据回退，提供本地回环 Web 看板（`127.0.0.1:8788`）、TUI、CLI/MCP 与 90 天利用率热力图 |",
            f"| [`diagnostics`](https://github.com/mindie-agent/diagnostics) | `mindie-diagnostics` | {rel_link('diagnostics', c['diagnostics']['tag'])} | **结构化诊断底座**：CANN/`plog` 确定性报错解析、4×1 MiB 本地 JSONL 轮转日志、离线脱敏支持包与带 2 次有界外发对账重试的可选白名单 GitHub Issue 故障上报 |",
            f"| [`debugger`](https://github.com/mindie-agent/debugger) | `mindie-debugger` | {rel_link('debugger', c['debugger']['tag'])} | **目标 NPU 故障分诊与精度调试组件**：CANN/`plog` 确定性报错解析（`npu_fault_triage`）、三原语精度/内存踩踏定位（`precision`）与 `ACLGraph` 图内重放 Dump / 捕获守卫 / 静态指针追踪（`aclgraph`） |",
            "",
            "### 4. 昇腾领域公共知识库（Public Domain Knowledge Corpora）",
            "",
            "| 仓库 / Repository | 领域 / Domain | 知识规模 / Scale | 定位与核心用途 / What It Does |",
            "|---|---|---|---|",
            f"| [`knowledge-vllm-ascend`](https://github.com/mindie-agent/knowledge-vllm-ascend) | `vllm-ascend` | {corpus_link('knowledge-vllm-ascend', corp['knowledge-vllm-ascend']['commit'], corp['knowledge-vllm-ascend']['units'], 'zh')} | **`vLLM-Ascend` 与 `vLLM-Omni` 知识库**：新模型 0day 接入、PD 分离、MoE EP/MC2、量化、投机解码、ACLGraph/TorchAir 与全模态流水线调优 |",
            f"| [`knowledge-xllm`](https://github.com/mindie-agent/knowledge-xllm) | `xllm` | {corpus_link('knowledge-xllm', corp['knowledge-xllm']['commit'], corp['knowledge-xllm']['units'], 'zh')} | **`xLLM` 全栈昇腾知识库**：C++ 原生 `ModelRegistry`、`xTensor` VMM 2 MB 物理页池、Piecewise ACLGraph、48 个 AscendC 算子与 A5 TileLang AOT 编译、Mooncake PD 分离与 `OneRec` 推荐流水线 |",
            f"| [`knowledge-mindie-sd`](https://github.com/mindie-agent/knowledge-mindie-sd) | `mindie-sd` | {corpus_link('knowledge-mindie-sd', corp['knowledge-mindie-sd']['commit'], corp['knowledge-mindie-sd']['units'], 'zh')} | **`MindIE-SD` 扩散生成框架知识库**：块稀疏注意力（`RainFusion`/`Ada-BSA`/`EagleQBSA`）、跨步缓存（`DiTCache`）、时步感知量化 + `Laurel`、Ulysses/Ring/CFG 并行、3D VAE 切片解码与 S0–S6 自动调优 |",
            f"| [`knowledge-operators`](https://github.com/mindie-agent/knowledge-operators) | `operators` | {corpus_link('knowledge-operators', corp['knowledge-operators']['commit'], corp['knowledge-operators']['units'], 'zh')} | **昇腾算子工程知识库**：910B/910C(A3)/950(A5) 硬件约束、`AscendC`、`Triton-Ascend`、TileLang、PyPTO、Catlass、FlashAttention/MLA 与 Matmul/MoE 融合算子 |",
            f"| [`knowledge-infer-core`](https://github.com/mindie-agent/knowledge-infer-core) | `infer-core` | {corpus_link('knowledge-infer-core', corp['knowledge-infer-core']['commit'], corp['knowledge-infer-core']['units'], 'zh')} | **推理服务与引擎核心知识库**：`cann-recipes-infer` 模型优化 Recipe、`model-infer-*` Skill、公共加速模块与 `msagent` 量化/精度诊断工作流 |",
            f"| [`knowledge-infer-distributed`](https://github.com/mindie-agent/knowledge-infer-distributed) | `infer-distributed` | {corpus_link('knowledge-infer-distributed', corp['knowledge-infer-distributed']['commit'], corp['knowledge-infer-distributed']['units'], 'zh')} | **分布式推理与集合通信知识库**：HCCL 通信排障、RoCE/HCCS 拓扑、SHMEM、Mooncake/Yuanrong 传输与多机 `DP/TP/EP/PP/DCP/DSA-CP/PCP` 并行调优 |",
            f"| [`knowledge-infer-observability`](https://github.com/mindie-agent/knowledge-infer-observability) | `infer-observability` | {corpus_link('knowledge-infer-observability', corp['knowledge-infer-observability']['commit'], corp['knowledge-infer-observability']['units'], 'zh')} | **推理可观测性、诊断与评测知识库**：CANN/`plog`/Device 故障分诊、`msprof` 性能拆解、容量/性能仿真与 `perf-gate` / `accuracy-gate` 评测规程 |",
            f"| [`knowledge-infer-ops-compat`](https://github.com/mindie-agent/knowledge-infer-ops-compat) | `infer-ops-compat` | {corpus_link('knowledge-infer-ops-compat', corp['knowledge-infer-ops-compat']['commit'], corp['knowledge-infer-ops-compat']['units'], 'zh')} | **图编译、算子注册与迁移兼容知识库**：TorchAir/ACLGraph 图捕获、`torch_npu._inductor` Pass 开发、CUDA 至昇腾迁移与容器部署 |",
            f"| [`knowledge-agent-engineering`](https://github.com/mindie-agent/knowledge-agent-engineering) | `agent-engineering` | {corpus_link('knowledge-agent-engineering', corp['knowledge-agent-engineering']['commit'], corp['knowledge-agent-engineering']['units'], 'zh')} | **Agent 工程与治理知识库**：多 Agent 协同编排、SOTA 探索循环、`ais_bench` 核心集压缩、`kb-lint` 质量门禁、双层隐私脱敏与真机基准评测方法 |",
        ]
    )


def render_org_readme_zh(m: dict) -> str:
    v_main = f"v{m['current_patch_version']}"
    c = m["components"]
    return "\n".join(
        [
            f"- 产品总入口与架构文档：[mindie-agent/mindie-agent](https://github.com/mindie-agent/mindie-agent)（{rel_link('mindie-agent', v_main)}）",
            f"- Claude Code 插件：[mindie-agent/mindie-agent-cc](https://github.com/mindie-agent/mindie-agent-cc)（{rel_link('mindie-agent-cc', c['mindie-agent-cc']['tag'])}）",
            f"- OpenAI Codex 插件：[mindie-agent/mindie-agent-codex](https://github.com/mindie-agent/mindie-agent-codex)（{rel_link('mindie-agent-codex', c['mindie-agent-codex']['tag'])}）",
            f"- Kimi Code 插件：[mindie-agent/mindie-agent-kimi](https://github.com/mindie-agent/mindie-agent-kimi)（{rel_link('mindie-agent-kimi', c['mindie-agent-kimi']['tag'])}）",
            f"- DeepSeek Harness (DSH) 插件：[mindie-agent/mindie-agent-dsh](https://github.com/mindie-agent/mindie-agent-dsh)（{rel_link('mindie-agent-dsh', c['mindie-agent-dsh']['tag'])}）",
            f"- Google Antigravity 插件：[mindie-agent/mindie-agent-agy](https://github.com/mindie-agent/mindie-agent-agy)（{rel_link('mindie-agent-agy', c['mindie-agent-agy']['tag'])}）",
            f"- Tencent WorkBuddy 插件：[mindie-agent/mindie-agent-wb](https://github.com/mindie-agent/mindie-agent-wb)（{rel_link('mindie-agent-wb', c['mindie-agent-wb']['tag'])}）",
            f"- 核心运行时组件：[`knowledge`](https://github.com/mindie-agent/knowledge)（{rel_link('knowledge', c['knowledge']['tag'])}）· [`remote-dev`](https://github.com/mindie-agent/remote-dev)（{rel_link('remote-dev', c['remote-dev']['tag'])}）· [`coordinator`](https://github.com/mindie-agent/coordinator)（{rel_link('coordinator', c['coordinator']['tag'])}）· [`profiler`](https://github.com/mindie-agent/profiler)（{rel_link('profiler', c['profiler']['tag'])}）· [`sim`](https://github.com/mindie-agent/sim)（{rel_link('sim', c['sim']['tag'])}）· [`npu-top`](https://github.com/mindie-agent/npu-top)（{rel_link('npu-top', c['npu-top']['tag'])}）· [`diagnostics`](https://github.com/mindie-agent/diagnostics)（{rel_link('diagnostics', c['diagnostics']['tag'])}）· [`debugger`](https://github.com/mindie-agent/debugger)（{rel_link('debugger', c['debugger']['tag'])}）",
            f"- 真机评测与基准套件：[mindie-agent/mindie-bench](https://github.com/mindie-agent/mindie-bench)（{rel_link('mindie-bench', c['mindie-bench']['tag'])}）",
            "- 昇腾 AI Infra 技能目录：[mindie-agent/awesome-mindie-skills](https://github.com/mindie-agent/awesome-mindie-skills)",
        ]
    )


def render_org_readme_en(m: dict) -> str:
    v_main = f"v{m['current_patch_version']}"
    c = m["components"]
    return "\n".join(
        [
            f"- Product Entry & Architecture: [mindie-agent/mindie-agent](https://github.com/mindie-agent/mindie-agent) ({rel_link('mindie-agent', v_main)})",
            f"- Claude Code Plugin: [mindie-agent/mindie-agent-cc](https://github.com/mindie-agent/mindie-agent-cc) ({rel_link('mindie-agent-cc', c['mindie-agent-cc']['tag'])})",
            f"- OpenAI Codex Plugin: [mindie-agent/mindie-agent-codex](https://github.com/mindie-agent/mindie-agent-codex) ({rel_link('mindie-agent-codex', c['mindie-agent-codex']['tag'])})",
            f"- Kimi Code Plugin: [mindie-agent/mindie-agent-kimi](https://github.com/mindie-agent/mindie-agent-kimi) ({rel_link('mindie-agent-kimi', c['mindie-agent-kimi']['tag'])})",
            f"- DeepSeek Harness (DSH) Plugin: [mindie-agent/mindie-agent-dsh](https://github.com/mindie-agent/mindie-agent-dsh) ({rel_link('mindie-agent-dsh', c['mindie-agent-dsh']['tag'])})",
            f"- Google Antigravity Plugin: [mindie-agent/mindie-agent-agy](https://github.com/mindie-agent/mindie-agent-agy) ({rel_link('mindie-agent-agy', c['mindie-agent-agy']['tag'])})",
            f"- Tencent WorkBuddy Plugin: [mindie-agent/mindie-agent-wb](https://github.com/mindie-agent/mindie-agent-wb) ({rel_link('mindie-agent-wb', c['mindie-agent-wb']['tag'])})",
            f"- Core Runtime Components: [`knowledge`](https://github.com/mindie-agent/knowledge) ({rel_link('knowledge', c['knowledge']['tag'])}) · [`remote-dev`](https://github.com/mindie-agent/remote-dev) ({rel_link('remote-dev', c['remote-dev']['tag'])}) · [`coordinator`](https://github.com/mindie-agent/coordinator) ({rel_link('coordinator', c['coordinator']['tag'])}) · [`profiler`](https://github.com/mindie-agent/profiler) ({rel_link('profiler', c['profiler']['tag'])}) · [`sim`](https://github.com/mindie-agent/sim) ({rel_link('sim', c['sim']['tag'])}) · [`npu-top`](https://github.com/mindie-agent/npu-top) ({rel_link('npu-top', c['npu-top']['tag'])}) · [`diagnostics`](https://github.com/mindie-agent/diagnostics) ({rel_link('diagnostics', c['diagnostics']['tag'])}) · [`debugger`](https://github.com/mindie-agent/debugger) ({rel_link('debugger', c['debugger']['tag'])})",
            f"- Evaluation & Live NPU Benchmark Suite: [mindie-agent/mindie-bench](https://github.com/mindie-agent/mindie-bench) ({rel_link('mindie-bench', c['mindie-bench']['tag'])})",
            "- Ascend Agent Skills Catalogue: [mindie-agent/awesome-mindie-skills](https://github.com/mindie-agent/awesome-mindie-skills)",
        ]
    )


def render_release_table(m: dict, lang: str) -> str:
    c = m["components"]
    rows = [
        ("mindie-agent-codex", "原生客户端插件（OpenAI Codex CLI）", "Native Host Plugin (OpenAI Codex CLI)"),
        ("mindie-agent-cc", "原生客户端插件（Claude Code）", "Native Host Plugin (Claude Code)"),
        ("mindie-agent-kimi", "原生客户端插件（Kimi Code CLI）", "Native Host Plugin (Kimi Code CLI)"),
        ("mindie-agent-dsh", "原生客户端插件（DeepSeek Harness）", "Native Host Plugin (DeepSeek Harness)"),
        ("mindie-agent-agy", "原生客户端插件（Google Antigravity）", "Native Host Plugin (Google Antigravity)"),
        ("mindie-agent-wb", "原生客户端插件（Tencent WorkBuddy）", "Native Host Plugin (Tencent WorkBuddy)"),
        ("knowledge", "共享运行时组件", "Shared Runtime Component"),
        ("remote-dev", "共享运行时组件", "Shared Runtime Component"),
        ("coordinator", "共享运行时组件", "Shared Runtime Component"),
        ("profiler", "共享运行时组件", "Shared Runtime Component"),
        ("sim", "共享运行时组件", "Shared Runtime Component"),
        ("npu-top", "共享运行时组件", "Shared Runtime Component"),
        ("diagnostics", "共享运行时组件", "Shared Runtime Component"),
        ("debugger", "共享运行时组件", "Shared Runtime Component"),
        ("mindie-bench", "评测运行器与基准套件", "Evaluation Runner & Benchmark Suite"),
    ]
    header = "| 仓库 | 角色 | 版本 | 标签源码 SHA |" if lang == "zh" else "| Repository | Role | Version | Tag Source SHA |"
    lines = [header, "| --- | --- | --- | --- |"]
    for key, role_zh, role_en in rows:
        entry = c[key]
        role = role_zh if lang == "zh" else role_en
        lines.append(f"| `{key}` | {role} | `{entry['version']}` | `{entry['commit']}` |")
    return "\n".join(lines)


def sync_release_notes_prose(text: str, m: dict) -> str:
    c = m["components"]
    replacements = [
        (
            r"\bSim [0-9.]+ / Profiler [0-9.]+\b",
            f"Sim {c['sim']['version']} / Profiler {c['profiler']['version']}",
        ),
        (r"`Codex v[0-9.]+`", f"`Codex v{c['mindie-agent-codex']['version']}`"),
        (r"`Claude Code v[0-9.]+`", f"`Claude Code v{c['mindie-agent-cc']['version']}`"),
        (r"`Kimi v[0-9.]+`", f"`Kimi v{c['mindie-agent-kimi']['version']}`"),
        (r"`DSH v[0-9.]+`", f"`DSH v{c['mindie-agent-dsh']['version']}`"),
        (r"`Google Antigravity v[0-9.]+`", f"`Google Antigravity v{c['mindie-agent-agy']['version']}`"),
        (r"`Tencent WorkBuddy v[0-9.]+`", f"`Tencent WorkBuddy v{c['mindie-agent-wb']['version']}`"),
        (r"`WorkBuddy v[0-9.]+`", f"`WorkBuddy v{c['mindie-agent-wb']['version']}`"),
        (r"`mindie-knowledge v[0-9.]+`", f"`mindie-knowledge v{c['knowledge']['version']}`"),
        (r"`mindie-coordinator v[0-9.]+`", f"`mindie-coordinator v{c['coordinator']['version']}`"),
        (r"`mindie-profiler v[0-9.]+`", f"`mindie-profiler v{c['profiler']['version']}`"),
        (r"`mindie-sim v[0-9.]+`", f"`mindie-sim v{c['sim']['version']}`"),
        (r"`mindie-debugger v[0-9.]+`", f"`mindie-debugger v{c['debugger']['version']}`"),
        (r"`mindie-diagnostics v[0-9.]+`", f"`mindie-diagnostics v{c['diagnostics']['version']}`"),
        (r"`remote-dev v[0-9.]+`", f"`remote-dev v{c['remote-dev']['version']}`"),
        (r"`npu-top v[0-9.]+`", f"`npu-top v{c['npu-top']['version']}`"),
        (r"`mindie-bench v[0-9.]+`", f"`mindie-bench v{c['mindie-bench']['version']}`"),
        (r"`mindie-sim [0-9.]+`", f"`mindie-sim {c['sim']['version']}`"),
        (r"`mindie-profiler [0-9.]+`", f"`mindie-profiler {c['profiler']['version']}`"),
        (r"`mindie-debugger [0-9.]+`", f"`mindie-debugger {c['debugger']['version']}`"),
    ]
    for pat, repl in replacements:
        text = re.sub(pat, repl, text)
    return text


def sync_channel_internal_fields(channel_path: Path, m: dict, write: bool) -> list[str]:
    raw_text = channel_path.read_text(encoding="utf-8")
    data = json.loads(raw_text)
    cpv = str(data["current_patch_version"])
    c = data["components"]

    data["release_notes"] = f"docs/releases/{cpv}.md"
    data["release_notes_en"] = f"docs/releases/{cpv}.en.md"

    impl = (data.get("update_policy") or {}).get("implementation_status") or {}
    kb = str(impl.get("known_boundaries") or "")
    if kb:
        kb = re.sub(r"^The [0-9.]+ channel pins", f"The {cpv} channel pins", kb)
        kb_map = [
            (r"knowledge [0-9.]+", f"knowledge {c['knowledge']['version']}"),
            (r"remote-dev [0-9.]+", f"remote-dev {c['remote-dev']['version']}"),
            (r"profiler [0-9.]+", f"profiler {c['profiler']['version']}"),
            (r"sim [0-9.]+", f"sim {c['sim']['version']}"),
            (r"coordinator [0-9.]+", f"coordinator {c['coordinator']['version']}"),
            (r"npu-top [0-9.]+", f"npu-top {c['npu-top']['version']}"),
            (r"diagnostics [0-9.]+", f"diagnostics {c['diagnostics']['version']}"),
            (r"debugger [0-9.]+", f"debugger {c['debugger']['version']}"),
            (r"mindie-bench [0-9.]+", f"mindie-bench {c['mindie-bench']['version']}"),
            (r"Codex [0-9.]+", f"Codex {c['mindie-agent-codex']['version']}"),
            (r"Claude Code [0-9.]+", f"Claude Code {c['mindie-agent-cc']['version']}"),
            (r"Kimi [0-9.]+", f"Kimi {c['mindie-agent-kimi']['version']}"),
            (r"DSH [0-9.]+", f"DSH {c['mindie-agent-dsh']['version']}"),
            (r"Google Antigravity [0-9.]+", f"Google Antigravity {c['mindie-agent-agy']['version']}"),
            (r"Tencent WorkBuddy [0-9.]+", f"Tencent WorkBuddy {c['mindie-agent-wb']['version']}"),
        ]
        for pat, repl in kb_map:
            kb = re.sub(pat, repl, kb)
        impl["known_boundaries"] = kb

    patch_releases = data.get("patch_releases") or []
    if patch_releases and str(patch_releases[-1].get("patch_version")) == cpv:
        summary = str(patch_releases[-1].get("summary") or "")
        sum_map = [
            (
                r"mindie-knowledge [0-9.]+ \([0-9a-f]{40}\)",
                f"mindie-knowledge {c['knowledge']['version']} ({c['knowledge']['commit']})",
            ),
            (
                r"mindie-coordinator [0-9.]+ \([0-9a-f]{40}\)",
                f"mindie-coordinator {c['coordinator']['version']} ({c['coordinator']['commit']})",
            ),
            (
                r"mindie-sim [0-9.]+ \([0-9a-f]{40}\)",
                f"mindie-sim {c['sim']['version']} ({c['sim']['commit']})",
            ),
            (
                r"mindie-profiler [0-9.]+ \([0-9a-f]{40}\)",
                f"mindie-profiler {c['profiler']['version']} ({c['profiler']['commit']})",
            ),
            (
                r"mindie-debugger [0-9.]+ \([0-9a-f]{40}\)",
                f"mindie-debugger {c['debugger']['version']} ({c['debugger']['commit']})",
            ),
            (
                r"mindie-diagnostics [0-9.]+ \([0-9a-f]{40}\)",
                f"mindie-diagnostics {c['diagnostics']['version']} ({c['diagnostics']['commit']})",
            ),
            (
                r"remote-dev [0-9.]+ \([0-9a-f]{40}\)",
                f"remote-dev {c['remote-dev']['version']} ({c['remote-dev']['commit']})",
            ),
            (
                r"npu-top [0-9.]+ \([0-9a-f]{40}\)",
                f"npu-top {c['npu-top']['version']} ({c['npu-top']['commit']})",
            ),
            (
                r"mindie-bench [0-9.]+ \([0-9a-f]{40}\)",
                f"mindie-bench {c['mindie-bench']['version']} ({c['mindie-bench']['commit']})",
            ),
            (
                r"mindie-agent-wb [0-9.]+ \([0-9a-f]{40}\)",
                f"mindie-agent-wb {c['mindie-agent-wb']['version']} ({c['mindie-agent-wb']['commit']})",
            ),
            (r"Codex [0-9.]+", f"Codex {c['mindie-agent-codex']['version']}"),
            (r"Claude Code [0-9.]+", f"Claude Code {c['mindie-agent-cc']['version']}"),
            (r"Kimi [0-9.]+", f"Kimi {c['mindie-agent-kimi']['version']}"),
            (r"DSH [0-9.]+", f"DSH {c['mindie-agent-dsh']['version']}"),
            (r"Antigravity [0-9.]+", f"Antigravity {c['mindie-agent-agy']['version']}"),
            (r"WorkBuddy [0-9.]+", f"WorkBuddy {c['mindie-agent-wb']['version']}"),
        ]
        for pat, repl in sum_map:
            summary = re.sub(pat, repl, summary)
        patch_releases[-1]["summary"] = summary

    rendered = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    m.update(data)
    if rendered != raw_text.replace("\r\n", "\n"):
        if write:
            channel_path.write_text(rendered, encoding="utf-8", newline="\n")
            print(f"Updated {channel_path}")
            return []
        return [f"Out-of-sync internal fields in {channel_path} (run sync_org_versions.py --release-scope product --write)"]
    return []


def replace_marker_block(text: str, block_id: str, new_body: str) -> str:
    start_tag = f"<!-- mindie-org-versions:{block_id}:start -->"
    end_tag = f"<!-- mindie-org-versions:{block_id}:end -->"
    start_idx = text.find(start_tag)
    end_idx = text.find(end_tag)
    if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
        raise RuntimeError(f"Missing or invalid marker block '{block_id}' ({start_tag} ... {end_tag})")
    replacement = f"{start_tag}\n{new_body}\n{end_tag}"
    return text[:start_idx] + replacement + text[end_idx + len(end_tag) :]


def sync_install_playbook_versions(text: str, m: dict, lang: str) -> str:
    c = m["components"]
    codex_v = c["mindie-agent-codex"]["version"]
    cc_v = c["mindie-agent-cc"]["version"]
    kimi_v = c["mindie-agent-kimi"]["version"]
    dsh_v = c["mindie-agent-dsh"]["version"]
    agy_v = c["mindie-agent-agy"]["version"]
    wb_v = c["mindie-agent-wb"]["version"]
    rdev_v = c["remote-dev"]["version"]

    if lang == "zh":
        text = re.sub(
            r"当前插件版本为 Codex `v[0-9.]+`、Claude Code `v[0-9.]+`、Kimi Code `v[0-9.]+`(?:、| 与 )DSH `v[0-9.]+`(?:(?:、| 与 )Google Antigravity `v[0-9.]+`)?(?: 与 Tencent WorkBuddy `v[0-9.]+`)?",
            f"当前插件版本为 Codex `v{codex_v}`、Claude Code `v{cc_v}`、Kimi Code `v{kimi_v}`、DSH `v{dsh_v}`、Google Antigravity `v{agy_v}` 与 Tencent WorkBuddy `v{wb_v}`",
            text,
        )
    else:
        text = re.sub(
            r"current plugin versions are Codex `v[0-9.]+`, Claude Code `v[0-9.]+`, Kimi Code `v[0-9.]+`, (?:and )?DSH `v[0-9.]+`(?:, (?:and )?Google Antigravity `v[0-9.]+`)?(?:, and Tencent WorkBuddy `v[0-9.]+`)?",
            f"current plugin versions are Codex `v{codex_v}`, Claude Code `v{cc_v}`, Kimi Code `v{kimi_v}`, DSH `v{dsh_v}`, Google Antigravity `v{agy_v}`, and Tencent WorkBuddy `v{wb_v}`",
            text,
        )

    for repo, ver in (
        ("mindie-agent-cc", cc_v),
        ("mindie-agent-codex", codex_v),
        ("mindie-agent-kimi", kimi_v),
        ("mindie-agent-dsh", dsh_v),
        ("mindie-agent-agy", agy_v),
        ("mindie-agent-wb", wb_v),
        ("remote-dev", rdev_v),
    ):
        text = re.sub(
            rf"(https://github\.com/mindie-agent/{re.escape(repo)}/blob/v)[0-9]+(?:\.[0-9]+)+/",
            rf"\g<1>{ver}/",
            text,
        )

    pairs = [
        (r"mindie-agent-cc\.git#v[0-9.]+", f"mindie-agent-cc.git#v{cc_v}"),
        (r"`mindie-agent@mindie-agent-cc`（`[0-9.]+`）", f"`mindie-agent@mindie-agent-cc`（`{cc_v}`）"),
        (r"`mindie-agent@mindie-agent-cc` \(`[0-9.]+`\)", f"`mindie-agent@mindie-agent-cc` (`{cc_v}`)"),
        (r"mindie-agent-codex\.git --ref v[0-9.]+", f"mindie-agent-codex.git --ref v{codex_v}"),
        (r"(Codex 安装 ref 与成功标准：`v)[0-9.]+(`)", rf"\g<1>{codex_v}\g<2>"),
        (r"(Codex install ref and success version: `v)[0-9.]+(`)", rf"\g<1>{codex_v}\g<2>"),
        (r"(Claude Code 成功标准：`v)[0-9.]+(`)", rf"\g<1>{cc_v}\g<2>"),
        (r"(Claude Code success version: `v)[0-9.]+(`)", rf"\g<1>{cc_v}\g<2>"),
        (r"`mindie-agent@mindie-agent`（`[0-9.]+`）", f"`mindie-agent@mindie-agent`（`{codex_v}`）"),
        (r"`mindie-agent@mindie-agent` \(`[0-9.]+`\)", f"`mindie-agent@mindie-agent` (`{codex_v}`)"),
        (r"--branch v[0-9.]+ https://github\.com/mindie-agent/mindie-agent-kimi\.git", f"--branch v{kimi_v} https://github.com/mindie-agent/mindie-agent-kimi.git"),
        (r"--branch v[0-9.]+ https://github\.com/mindie-agent/mindie-agent-dsh\.git", f"--branch v{dsh_v} https://github.com/mindie-agent/mindie-agent-dsh.git"),
        (r"mindie-agent-dsh\.git#v[0-9.]+", f"mindie-agent-dsh.git#v{dsh_v}"),
        (r"--branch v[0-9.]+ https://github\.com/mindie-agent/mindie-agent-agy\.git", f"--branch v{agy_v} https://github.com/mindie-agent/mindie-agent-agy.git"),
        (r"--branch v[0-9.]+ https://github\.com/mindie-agent/mindie-agent-wb\.git", f"--branch v{wb_v} https://github.com/mindie-agent/mindie-agent-wb.git"),
        (r"`mindie-agent-agy v[0-9.]+`", f"`mindie-agent-agy v{agy_v}`"),
        (r"检出钉住的 `v[0-9.]+` tag", f"检出钉住的 `v{agy_v}` tag"),
        (r"Clone the pinned `v[0-9.]+` tag", f"Clone the pinned `v{agy_v}` tag"),
        (r"`mindie-agent-wb v[0-9.]+`", f"`mindie-agent-wb v{wb_v}`"),
        (r"remote-dev@v[0-9.]+", f"remote-dev@v{rdev_v}"),
        (r"`mindie-agent-cc v[0-9.]+`", f"`mindie-agent-cc v{cc_v}`"),
        (r"`mindie-agent-codex v[0-9.]+`", f"`mindie-agent-codex v{codex_v}`"),
        (r"`mindie-agent-kimi v[0-9.]+`", f"`mindie-agent-kimi v{kimi_v}`"),
        (r"`mindie-agent-dsh v[0-9.]+`", f"`mindie-agent-dsh v{dsh_v}`"),
    ]
    for pat, repl in pairs:
        text = re.sub(pat, repl, text)
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize and verify MindIE Agent and org README versions.")
    parser.add_argument("--release-scope", choices=("product",), required=True,
                        help="Full synchronization is reserved for an explicitly selected product combination")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]), help="Path to mindie-agent root.")
    parser.add_argument("--channel-file", default="", help="Override path to channels/0.1.json.")
    parser.add_argument("--org-profile-dir", default="", help="Optional path to mindie-agent/.github checkout.")
    parser.add_argument("--offline", action="store_true", help="Skip live GitHub REST API release verification.")
    parser.add_argument("--check", action="store_true", help="Verify files match channels/0.1.json without writing.")
    parser.add_argument("--write", action="store_true", help="Rewrite managed version blocks in place.")
    args = parser.parse_args()

    if not args.check and not args.write:
        parser.error("Specify --check or --write.")

    repo_root = Path(args.repo_root).resolve()
    channel_path = Path(args.channel_file).resolve() if args.channel_file else repo_root / "channels" / "0.1.json"
    manifest = load_channel_manifest(channel_path)

    errors: list[str] = []
    if not args.offline:
        token = os.environ.get("TELEMETRY_TOKEN") or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        errors.extend(verify_live_releases(manifest, token))

    errors.extend(sync_channel_internal_fields(channel_path, manifest, args.write))
    cpv = str(manifest["current_patch_version"])
    errors.extend(
        process_file(
            repo_root / "docs" / "releases" / f"{cpv}.md",
            lambda txt: sync_release_notes_prose(
                replace_marker_block(txt, "release-table-zh", render_release_table(manifest, "zh")),
                manifest,
            ),
            args.write,
        )
    )
    errors.extend(
        process_file(
            repo_root / "docs" / "releases" / f"{cpv}.en.md",
            lambda txt: sync_release_notes_prose(
                replace_marker_block(txt, "release-table-en", render_release_table(manifest, "en")),
                manifest,
            ),
            args.write,
        )
    )
    errors.extend(sync_docs_versions(repo_root, manifest, args.write))
    errors.extend(sync_sibling_readmes(repo_root, manifest, args.write))
    errors.extend(
        process_file(
            repo_root / "README.md",
            lambda txt: sync_install_playbook_versions(
                replace_marker_block(
                    replace_marker_block(txt, "main-badges-zh", render_main_badges_zh(manifest)),
                    "main-ecosystem-zh",
                    render_main_ecosystem_zh(manifest),
                ),
                manifest,
                "zh",
            ),
            args.write,
        )
    )
    errors.extend(
        process_file(
            repo_root / "README.en.md",
            lambda txt: sync_install_playbook_versions(
                replace_marker_block(
                    replace_marker_block(txt, "main-badges-en", render_main_badges_en(manifest)),
                    "main-ecosystem-en",
                    render_main_ecosystem_en(manifest),
                ),
                manifest,
                "en",
            ),
            args.write,
        )
    )

    if args.org_profile_dir:
        org_dir = Path(args.org_profile_dir).resolve()
        errors.extend(
            process_file(
                org_dir / "profile" / "README.md",
                lambda txt: sync_install_playbook_versions(
                    replace_marker_block(
                        replace_marker_block(txt, "org-badges", render_org_badges(manifest)),
                        "org-ecosystem",
                        render_org_ecosystem(manifest),
                    ),
                    manifest,
                    "zh",
                ),
                args.write,
            )
        )
        errors.extend(
            process_file(
                org_dir / "README.md",
                lambda txt: replace_marker_block(txt, "org-readme-zh", render_org_readme_zh(manifest)),
                args.write,
            )
        )
        errors.extend(
            process_file(
                org_dir / "README.en.md",
                lambda txt: replace_marker_block(txt, "org-readme-en", render_org_readme_en(manifest)),
                args.write,
            )
        )

    if errors:
        for err in errors:
            print(f"[ERROR] {err}", file=sys.stderr)
        return 1

    print(
        f"OK: All managed version blocks match channels/0.1.json "
        f"(mindie-agent v{manifest['current_patch_version']}, {len(manifest.get('components', {}))} components, {len(manifest.get('corpora', {}))} corpora)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

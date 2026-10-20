# MindIE Agent 代码质量审计 · 2026-10-20

[English](README.en.md) · [33 项审查明细](findings.md) · [逐文件基线数据](baseline.json) · [文档中心](../../README.md)

本轮完成扫描、既有测试运行、覆盖率测量与修改计划。没有修改业务实现、既有测试或项目依赖锁。最优先的风险是回执归属、日志增量与预算、配置默认值、远端路径边界及进程回收。多数问题发生在现有断言未覆盖的交错或边界场景；测试通过不代表这些场景正确。

本报告是固定版本的历史审计，不代表当前主线已修复或已完成产品验收。文档 PR 基于更新后的架构仓主线；下列审计 SHA 仍保持原值。公开版保留结果、命令、代码定位及缺口，原始运行日志、覆盖率数据库、机器连接信息和本地复现工具保留在本地，不作为公开附件。不能将仅有本地日志的结论描述为第三方已经独立复核。

## A. 仓库与核心链路

组织目录共 21 仓；扫描 15 个非空仓库，复用已有架构仓 checkout，其余为隔离 checkout。下表均为扫描时 `main` 的 SHA。源码和既有测试在审计结束时均无 tracked 改动。

| 仓库 | 职责 | 审计 commit |
| --- | --- | --- |
| mindie-agent | 架构与设计文档 | [bc17f3095cdf3cc16bfb1e803a839fd4ad71686b](https://github.com/mindie-agent/mindie-agent/commit/bc17f3095cdf3cc16bfb1e803a839fd4ad71686b) |
| .github | 组织贡献规范与模板 | [a22e53165e98e5313ebd2cfd4313b427b3d67f49](https://github.com/mindie-agent/.github/commit/a22e53165e98e5313ebd2cfd4313b427b3d67f49) |
| awesome-mindie-skills | 技能目录与维护脚本 | [64c2457d0b05e89c0a0808896a3e10960f536c53](https://github.com/mindie-agent/awesome-mindie-skills/commit/64c2457d0b05e89c0a0808896a3e10960f536c53) |
| coordinator | 环境、容器与租约协调 | [c77144a95dd6af37e978ffc2d8495158b237090d](https://github.com/mindie-agent/coordinator/commit/c77144a95dd6af37e978ffc2d8495158b237090d) |
| diagnostics | 日志、诊断与 profiler | [6460cde3a50a7f91c9ded38557a7f921654f0c6a](https://github.com/mindie-agent/diagnostics/commit/6460cde3a50a7f91c9ded38557a7f921654f0c6a) |
| knowledge | 检索、采集、脱敏、发布 | [021ba95e701d4f8c8d924e2dcc8f120a4939da23](https://github.com/mindie-agent/knowledge/commit/021ba95e701d4f8c8d924e2dcc8f120a4939da23) |
| knowledge-vllm-ascend | 公开知识内容与验证契约 | [85ab134f333b06ac3873df6affbf3bf6ec71978c](https://github.com/mindie-agent/knowledge-vllm-ascend/commit/85ab134f333b06ac3873df6affbf3bf6ec71978c) |
| mindie-agent-cc | Claude Code 宿主适配 | [78f34dd9b09e877298225fa243ea4c28978c9dd6](https://github.com/mindie-agent/mindie-agent-cc/commit/78f34dd9b09e877298225fa243ea4c28978c9dd6) |
| mindie-agent-codex | Codex 宿主适配 | [f1acb69ba336f75ae2d909443ca118835b038b9c](https://github.com/mindie-agent/mindie-agent-codex/commit/f1acb69ba336f75ae2d909443ca118835b038b9c) |
| mindie-agent-dsh | DSH 宿主适配 | [d3a1e1282356b65b51fba49072c1842918746f8f](https://github.com/mindie-agent/mindie-agent-dsh/commit/d3a1e1282356b65b51fba49072c1842918746f8f) |
| mindie-agent-kimi | Kimi 宿主适配 | [0e78f0422162a61e8c56850e049f9e5fc4d290b5](https://github.com/mindie-agent/mindie-agent-kimi/commit/0e78f0422162a61e8c56850e049f9e5fc4d290b5) |
| mindie-bench | 评测编排、网关与验证器 | [b7301839602ad3791af17f21f5aa47d773b5af2a](https://github.com/mindie-agent/mindie-bench/commit/b7301839602ad3791af17f21f5aa47d773b5af2a) |
| npu-top | 采集调度、历史与 Web/MCP | [8f992bf033af57979d6bebf67189a89bb2034d7e](https://github.com/mindie-agent/npu-top/commit/8f992bf033af57979d6bebf67189a89bb2034d7e) |
| remote-dev | SSH/MCP 文件、搜索、受管作业 | [c3af104c36582c675a6dcd368637db7c60b28afd](https://github.com/mindie-agent/remote-dev/commit/c3af104c36582c675a6dcd368637db7c60b28afd) |
| vllm-ascend-workspace | Git/worktree 脚手架 | [c85b9ca94c5432a58f3e0bff6bbbcd5d711d8ca8](https://github.com/mindie-agent/vllm-ascend-workspace/commit/c85b9ca94c5432a58f3e0bff6bbbcd5d711d8ca8) |

未纳入：6 个空仓 `knowledge-operators`、`knowledge-infer-core`、`knowledge-infer-distributed`、`knowledge-infer-observability`、`knowledge-infer-ops-compat`、`knowledge-agent-engineering` 无源码可测；知识正文、图像、模板和 CI 内嵌发布脚本不计入 runtime 分母。ReMe、LangMem、MCP SDK、vLLM/vLLM-Ascend、模型与驱动不作为项目自有代码审计；脚手架的第三方大子模块未完整初始化。

已按职责读取适用 AGENTS.md、README、设计原则、测试规范、项目声明、锁文件及现有 CI。扫描聚焦实际入口与风险链路，不声称逐行穷尽。函数长度和决策节点数仅用于找候选，不作为缺陷证明；没有仅凭静态无引用认定死代码。

### 实际依赖版本

| 调用关系 | 版本依据与结论边界 |
| --- | --- |
| 四宿主 → 共享运行时 | knowledge `0.12.2@4e328305323eafc7fd43ecc0c53eb3cc0541fdef`；remote-dev `0.10.1@a6649222aae4851deec5774513f8319aece09051`；diagnostics `0.4.3@1b5a0eeb79d498c39002fc1853271c17e0f26e66`。按锁定依赖运行插件测试。 |
| knowledge main → diagnostics | 仍固定 diagnostics `1b5a0eeb`；ReMe `4c54c2b650038eff2a5d0d77aaa61b3e836f1b18`；LangMem `0.0.30`。diagnostics main 的 profiler 不属于当前插件已使用链路。 |
| coordinator main → remote-dev | remote-dev `c3af104c36582c675a6dcd368637db7c60b28afd`；远端三仓使用 diagnostics `6460cde3a50a7f91c9ded38557a7f921654f0c6a`，与扫描版本一致。 |
| 知识内容 CI → validator | knowledge `b1d8d9278a60394f0de28aa2986d02e0ecb8b115`；实际 22 个模块来自该 checkout，但复用了既有依赖环境，不等同完整 CI 固定 wheel 安装验证。 |
| 宿主 peer fixture | Codex 最终运行设置 Kimi `90f73e76c6087ce091570f2d151b709145c913bc`、CC `3e36a285e2effe47bc442079a4ed7f42ced9caaf`。现有测试未读取 peer 实现，仅透传环境或复用共享配置，因此通过不能证明跨宿主实现兼容。 |

### 核心链路

| 链路 | 入口、处理、状态、外部调用、返回与错误 | 发现 |
| --- | --- | --- |
| 绑定与经验采集 | Hook/MCP → identity claim → 公共转录与游标 → knowledge.accept_stop 的 consent/admission/SQLite → worker 脱敏索引 → 发布 receipt；拒绝重放与错误不能污染原 owner。 | ADP-01～06、K-01～03 |
| 知识检索 | MCP/CLI → Store.query → query_request → MaterialStore/ReMe → 当前引用解析与正文读取；坏输入应先于索引 I/O 失败。 | K-05、KD-R3 |
| 远端工具 | MCP 输入 → endpoint/root → 文件、搜索或 job worker → SSH/远端进程 → submission_state 与结果；所有匹配项须服从目录范围。 | RD01、RF01、D02 |
| 环境和租约 | CLI/MCP → machines registry → service/backend → host queue/lease/probe → remote-dev；损坏配置不能伪装成无资源。 | CO01、RF02、D01、D03 |
| 监控 | viewer heartbeat/live API → scheduler → probe → cache/history → Web/MCP；返回的新鲜度须满足请求语义。 | NP01、NP02 |
| 诊断 | 事件 → 脱敏/白名单 → bundle → consent/reporting；profiler producer → compare → CLI 退出码。失败与不可比须可见。 | D-01～04、KD-R1/2/4 |
| 评测 | task recipe → run_trial → 网关/宿主/lease → verifier → score/capture/cleanup → receipt；保留主结果与不确定外部效果。 | B01～03、B05/06 |
| 开发脚手架 | CLI → Git/worktree/目录修改 → 元数据与返回码。 | B04 |

## B. 测试与覆盖率基线

环境：macOS 26.4 arm64，Python 3.13.16，uv 0.13.3，pytest 9.1.1，coverage.py 7.16.2。下表是本地 Tier 0 + Tier 1 的实际执行；多数仓没有稳定的 T0/T1 marker，不能分别冒充纯内存单测或独立组件覆盖。subtest 不计入顶层 passed 数。覆盖率轮次使用 `patch = subprocess`，耗时含插桩开销。

| 仓库 | 结果（本地选择集） | wall 秒 | 生产代码行覆盖 | 生产代码分支覆盖 |
| --- | --- | --- | --- | --- |
| knowledge | 1188 passed, 20 skipped, 1 deselected, 2 warnings, 3 subtests passed in 485.40s (0:08:05) | 486.585 | 11104/13135 (84.54%) | 3510/4748 (73.93%) |
| diagnostics | 580 passed, 30 skipped, 1 warning in 14.48s | 14.775 | 11066/14034 (78.85%) | 3688/5444 (67.74%) |
| remote-dev | 623 passed, 42 skipped, 4 deselected, 254 subtests passed in 52.16s | 53.045 | 4297/6513 (65.98%) | 1250/2304 (54.25%) |
| coordinator | 1339 passed, 29 skipped, 4 deselected, 55 warnings, 63 subtests passed in 176.11s (0:02:56) | 176.558 | 10616/13060 (81.29%) | 3783/5382 (70.29%) |
| npu-top | 219 passed, 2 skipped, 5 deselected, 60 subtests passed in 7.55s | 8.805 | 3392/4214 (80.49%) | 995/1430 (69.58%) |
| mindie-agent-codex | 448 passed, 18 skipped, 2 deselected, 1 warning, 475 subtests passed in 108.12s (0:01:48) | 109.317 | 4532/5612 (80.76%) | 1419/2026 (70.04%) |
| mindie-agent-cc | 324 passed, 2 skipped, 2 deselected, 1 warning, 85 subtests passed in 64.69s (0:01:04) | 65.788 | 3626/4943 (73.36%) | 1120/1848 (60.61%) |
| mindie-agent-kimi | 317 passed, 3 skipped, 1 warning, 20 subtests passed in 154.62s (0:02:34) | 155.403 | 3597/4816 (74.69%) | 1071/1694 (63.22%) |
| mindie-agent-dsh | 31 passed, 2 subtests passed in 5.69s | 7.376 | 776/1410 (55.04%) | 171/432 (39.58%) |
| mindie-bench | 878 passed / 1 failed / 22 runtime skipped；1 模块收集跳过（2 函数未收集）；1 live deselected | 181.406 | 7145/9087 (78.63%) | 2590/3638 (71.19%) |
| vllm-ascend-workspace | 4 unittest passed / 0 failed / 0 skipped | 8.04 | 97/208 (46.63%) | 33/82 (40.24%) |

覆盖分子分别为实际执行的语句行、已执行分支弧；分母为配置范围内全部可执行语句行、全部分支弧。没有使用 coverage 的混合 `percent_covered` 充当行覆盖。`baseline.json` 提供每个文件的分子分母、缺失行/分支与排除行；负分支目标表示函数出口。行/分支结果不可与测试文件的覆盖混淆。

### 分母与采集范围

| 仓库 | 生产范围 | tracked / measured Python 文件 | 排除行 |
| --- | --- | --- | --- |
| knowledge | mindie_knowledge | 73 / 73 | 3 |
| diagnostics | mindie_diagnostics、mindie_profiler | 66 / 66 | 7 |
| remote-dev | remote_dev | 73 / 73 | 0 |
| coordinator | mindie_coordinator | 58 / 58 | 0 |
| npu-top | npu_top | 25 / 25 | 0 |
| mindie-agent-codex | plugins/mindie-agent/scripts | 43 / 43 | 0 |
| mindie-agent-cc | scripts | 30 / 30 | 0 |
| mindie-agent-kimi | scripts | 24 / 24 | 0 |
| mindie-agent-dsh | scripts | 10 / 10 | 2 |
| mindie-bench | src、scripts | 75 / 75 | 0 |
| vllm-ascend-workspace | .agents/scripts | 2 / 2 | 0 |

所有范围内从未导入的 Python 文件也在分母内；发现清单未漏文件，未混入测试。默认 Protocol/pragma 排除与显式清空排除的配置并不相同，原配置保留在 JSON，比较时必须使用相同配置。嵌入字符串中的 Python 只计外层赋值，不构成其内部源码分母；远端脚本、`python -I`、替换环境的后台进程、其他解释器、被强杀或复制到临时位置的代码仍可能未回传。不能据零采集认定无测试或死代码，也不能把本地 Python 比例外推至 JavaScript/TypeScript、设备或远端运行时。

knowledge 合并 49 份有效片段、177 份重复跳过；diagnostics 合并 14 份、3 份重复跳过，另 1 份无效片段归属未确认。diagnostics 数值因此是可读取数据的实测下界。bench 的 host 与 actual 两个互补选择集使用相同 SHA、依赖和覆盖配置，按行/分支集合并集合并；模块级 collection skip 重复出现只记一次，运行期 skip 为 12 + 10。

### 失败、补跑与未测得范围

- **bench 仍有 1 个失败**：`test_native_mcp_readiness` 使用本机 Codex `0.162.0-alpha.17.2`，在模型轮次之前同步受管配置失败；无插桩复跑同样失败。已核查本地配置与只读偏好探测，但根因未完全确认，不能直接归为产品缺陷或改记 skip。
- **bench 可选 14 项独立补跑通过**：9 个 CPU/torch 判题器、4 个固定历史配置、1 个本地真实 FastMCP 场景；pytest 25.54 秒、wall 25.860 秒。该独立选择集行 1410/9084（15.52%）、分支 216/3632（5.95%），75/75 文件在分母。默认 Protocol 排除与原基线不同（少 3 个方法、6 个物理行，语句分母差 3、分支差 6），依赖环境也不同，未并入主基线。原运行期 skip 剩余 4 个 Claude CLI、2 个 Kimi CLI、2 个 Linux 原生场景；缺少二进制或平台条件。另两项 component-value 场景因共同解释器的 diagnostics 精确依赖冲突仍未收集（B06）。
- **coordinator 首轮环境污染已定位**：审计设置的 GIT_AUTHOR/COMMITTER 环境变量覆盖测试自身身份，导致 1 个失败。A/B 复核确认后改用隔离的默认 Git 配置、允许 fixture 本地配置覆盖，最终 1339 passed。源文件和测试未改，旧失败记录保留。
- **Codex/Kimi 的早期插桩轮次有清理异常**：Codex 一次在业务断言之后 `killpg` 遇 PermissionError；Kimi 一次临时 Git 目录清理失败。最终完整插桩轮次均通过；Codex 异常根因没有被最终通过证明消失。Kimi 单例首次因测试支持模块路径未收集，设置既有 `tests` pythonpath 后通过，未改测试。
- **Tier 2 未测得**：只读 SSH 探测遇 banner 超时或尚无受信任主机密钥；未绕过 host-key 校验。需在受信任环境以隔离 state_dir 运行 `-m live_npu`，确认没有干扰活动任务，再回收同 SHA 的远端 coverage。
- **Tier 3、真实模型质量未测得**：本地宿主测试不等同完整 CLI E2E。未执行付费模型或真实外部发布；历史 Release benchmark 不并入本轮。应固定受支持 CLI/模型并运行专门 canary 与人工可复核的摘要质量集。
- **前端/内容**：npu-top lint/build 通过（1.16/1.97 秒），无行为覆盖；DSH Node 的 1 个用例通过，只执行部分宿主模块，完整 JS 覆盖未测得。workspace 4 个用例仅覆盖 repo_init.py，workspace.py 为 0/103 行、0/40 分支。
- **目录验证**：skills 的 53 项技能、10 分类、2 来源、223 链接校验通过；知识 validator 精确 pin 验证 663 entries、1 feedback、23,079,976 bytes，9.397 秒。推送事件模拟 base=head，只证明该静态快照；不构成增量发布/E2E 或模型质量验收。

各失败/skip 节点及原因保留在 JSON 的 `test_exceptions`，其中 bench 按轮次留存，不能直接相加。三项 10MB benchmark、Windows 原生语义、缺少宿主 CLI 与 live 环境等跳过均不能记为通过。

### 可复现命令

先按仓库表 checkout 精确 SHA；插件按原 uv.lock/Kimi runtime-requirements 安装精确组件，runtime 按各自原锁/声明建立隔离环境。额外安装测量工具 `coverage==7.16.2` 与 `pytest==9.1.1` 不应改项目锁。不同 diagnostics pin 的环境分开建立，禁止 `--no-deps` 拼出未支持组合。bench CPU/stale 任务还须各自原锁与 recipe 指定历史源码。

`baseline.json` 的 `plain_run` / `coverage_run` / `complementary_run` 记录准确参数、退出码、环境覆盖与耗时；`coverage_config` 记录本轮配置。`${AUDIT_ROOT}` 是读者选择的临时目录，需先创建其中的 `repos/`、`tools/`、`pinned/`、输出目录和对应虚拟环境；它不是现成下载包。JSON 中的命令数组和配置里的占位符需要展开，不能把未展开字符串直接当参数运行。

以下为执行形态示例；每仓真实源码范围、selector、依赖与额外变量以 JSON 为准：

```bash
# 在对应精确 checkout，激活上述独立 Python 3.13.16 环境后执行。
# 将 JSON 的 coverage_config 展开本地路径后保存为 audit.coveragerc。
python -m coverage run --rcfile=audit.coveragerc -m pytest -q tests -m 'not live_npu'
python -m coverage combine --rcfile=audit.coveragerc --keep
python -m coverage json --rcfile=audit.coveragerc -o coverage.json
# bench 使用相同配置和不同 data_file 执行两组，再按集合合并。
python -m coverage run --rcfile=audit.coveragerc -m pytest -m 'not live_npu' -k 'not actual' -ra
python -m coverage run --rcfile=audit.coveragerc -m pytest -m 'not live_npu' -k actual -ra
# workspace 的现有测试入口：
python -m coverage run --rcfile=audit.coveragerc -m unittest discover -s .agents/scripts/tests -v
```

coordinator 运行前移除审计注入的 GIT_AUTHOR/COMMITTER 四项变量及外部 REMOTE_DEV_STATE_DIR，使用隔离 `GIT_CONFIG_GLOBAL` 与 `GIT_CONFIG_NOSYSTEM=1`；默认身份使用测试专用值，允许 fixture 用仓内配置覆盖。不要修改个人 Git 配置。插件运行的知识 checkout 指向实际 pin；Codex peer SHA 见上表。一次性 fixture/输出目录由重跑者创建；这些本地文件没有被提交。

### 关键缺口与测试有效性

`baseline.json` 的 `modules` 给出全部缺失行和弧；风险函数与业务场景详见 C。代表性缺口包括 `accept_stop` 省略默认模式、DSH 短压缩日志追加及超长首条、并发 bind owner 收据、glob 根外匹配、idle→active 调度与在途 force 刷新、strict compare 缺签名/null 摘要、verifier 超时后的后代回收。已有测试在不少场景只检查 getter/类型/固定 fixture，不能发现对应业务结果错误。

需要保留有价值的组件测试：真实 SQLite、临时 Git、公共转录脱敏和引用一致性均已有作用。固定 summary worker 不能证明 LLM 摘要忠实度；六篇手造检索语料 Top1 不能外推真实检索质量。peer 环境变量存在不代表读取了 peer 实现。补测必须断言业务结果、关键状态与错误传播；具体能捕获的回归逐条写在审查明细，避免新增仅对类型、常量或调用次数的凑数测试。

## C. 按优先级排序的审查清单

完整的文件/函数/行号、触发、证据、影响、修改建议、验证、确定性和防御五问见 [33 项明细](findings.md)。P1 为核心状态/边界/持续副作用或关键采集盲区，P2 为错误语义与重要测试/结构问题，P3 为等价清理或待契约确认候选。

| 编号 | 优先级 | 仓库 | 类别 |
| --- | --- | --- | --- |
| [ADP-01](findings.md#adp-01) | P1 | mindie-agent-cc; mindie-agent-kimi | 正确性缺陷：并发重放污染原操作收据 |
| [ADP-02](findings.md#adp-02) | P1 | mindie-agent-dsh | 正确性缺陷：追加日志误判替换 |
| [ADP-03](findings.md#adp-03) | P1 | mindie-agent-dsh | 正确性缺陷与重构：扫描预算不成立 |
| [ADP-04](findings.md#adp-04) | P1 | mindie-agent-dsh | 正确性缺陷：候选stage共用活动运行时 |
| [B01](findings.md#b01) | P1 | mindie-bench | 已确认缺陷：进程生命周期 |
| [D02](findings.md#d02) | P1 | remote-dev | 防御代码保留 |
| [D03](findings.md#d03) | P1 | coordinator | 防御代码保留 |
| [K-01](findings.md#k-01) | P1 | knowledge | 已确认缺陷：遗留兼容分支绕过原文不落库约束 |
| [RD01](findings.md#rd01) | P1 | remote-dev | 已确认缺陷：目录范围契约 |
| [T01](findings.md#t01) | P1 | remote-dev + coordinator + npu-top | 已确认测试基线缺口 |
| [ADP-05](findings.md#adp-05) | P2 | mindie-agent-dsh | 错误语义与冗余恢复逻辑 |
| [ADP-06](findings.md#adp-06) | P2 | mindie-agent-cc; mindie-agent-kimi | 错误语义缺陷：本地收据写失败静默吞掉 |
| [B02](findings.md#b02) | P2 | mindie-bench | 已确认测试缺口 |
| [B03](findings.md#b03) | P2 | mindie-bench | 重构建议 |
| [B04](findings.md#b04) | P2 | vllm-ascend-workspace | 已确认测试缺口 |
| [B06](findings.md#b06) | P2 | mindie-bench | 已确认测试环境契约缺口：可选组件场景要求不兼容的共同解释器组合 |
| [CO01](findings.md#co01) | P2 | coordinator | 已确认缺陷：错误语义 |
| [D-01](findings.md#d-01) | P2 | diagnostics | 已确认缺陷：比较 CLI 工作负载身份门禁与契约不符 |
| [D-02](findings.md#d-02) | P2 | diagnostics | 已确认缺陷：已识别无效摘要后仍直接解引用 |
| [D-03](findings.md#d-03) | P2 | diagnostics | 待验证契约：显存 peak 缺少测量口径仍给出可比结论 |
| [K-02](findings.md#k-02) | P2 | knowledge | 重构建议：Stop handoff 的协议、授权、落库和唤醒混合 |
| [K-03](findings.md#k-03) | P2 | knowledge | 测试有效性边界：本地 summary fidelity 测试不能验证模型摘要忠实度 |
| [K-04](findings.md#k-04) | P2 | knowledge | 测试基线缺口：live探测将远端执行失败统一skip |
| [NP01](findings.md#np01) | P2 | npu-top | 已确认缺陷：刷新调度 |
| [NP02](findings.md#np02) | P2 | npu-top | 已确认缺陷：live结果新鲜度 |
| [RF01](findings.md#rf01) | P2 | remote-dev | 重构建议 |
| [RF02](findings.md#rf02) | P2 | coordinator | 重构建议 |
| [ADP-07](findings.md#adp-07) | P3 | mindie-agent-cc | 等价清理候选：重复纯校验 |
| [B05](findings.md#b05) | P3 | mindie-bench | 兼容分支待验证 |
| [D-04](findings.md#d-04) | P3 | diagnostics | 等价重构建议：同一 label 重复扫描 |
| [D01](findings.md#d01) | P3 | coordinator | 等价冗余清理 |
| [D04](findings.md#d04) | P3 | npu-top + remote-dev | 兼容逻辑待验证 |
| [K-05](findings.md#k-05) | P3 | knowledge | 等价重构候选：查询边界重复解析continuation |

建议删除/合并：CC 重复纯解析、coordinator 冗余终态谓词、diagnostics 同一 label 重复计算、knowledge 内部重复 query_request（保留两个公开入口验证）。旧 summary fallback、DSH 盲目重试、配置读取吞错、记账吞错涉及输入或失败语义，应作为正确性修复单独检视。

明确保留：远端真实路径约束、租约 fencing/进程排空、外发前重读授权、不可逆写 unknown 对账、正文 membership/hash 校验，以及不会覆盖主结果且公开 logging_failed 的诊断边界。证据不足：旧 peak 元数据、MaterialStore 能力 fallback、NFM 配置、远端 Python 3.9 支持及公开 alias/kwargs；须先明确支持矩阵，不能只凭未覆盖或当前类型注解删除。

## D. 分批修改计划

| 批次 / 类型 | 范围与顺序理由 | 行为测试与完成条件 |
| --- | --- | --- |
| 0：基线与补测 | 明确测试层级、修复收集问题，将纯本地 actual 场景纳入 CI；B06 建立可解析的组件/解释器契约。 | 11 个 Python 代码仓可按 SHA 重跑，分母稳定；保持失败/skip 原因；分环境 resolver、pip check 与两个原组件场景通过。 |
| 1a：正确性 | ADP-01 收据 owner、ADP-02/03 短日志/预算、K-01 模式默认与旧分支、RD01 根约束。 | 先复现后修复：真实 SQLite 交错、zstd 追加/超长帧、合法省略配置落库、根外 metadata 拒绝；旧 pin 与候选版本分别验收。 |
| 1b：生命周期正确性 | ADP-04 候选隔离、B01 进程回收、NP01 调度、NP02 force 完成。 | stage-only/准备失败不改活动代；真实进程树超时排空；受控时钟和 Event 测试在途交错；正常性能和输出保持。 |
| 2：错误语义修复 | ADP-05 盲目恢复、ADP-06 记账告警、CO01 配置错误、D-01/02 profiler 失败契约。D-03 先确认兼容策略。 | 异常保留原始来源，已成功业务不翻转为失败；损坏输入有固定错误/退出码；失败后恢复不重复外部副作用。文档写明调用方变化。 |
| 3：等价结构重构 | 先补特征测试，再拆 K-02 handoff、RF01 worker、RF02 progress、B03 run_trial 的纯决策与 I/O 边界。 | 对照完整结果/收据/错误与副作用次数；真实进程、SQLite、grep 契约保留；不新增平行持久状态机。每个模块单独 PR。 |
| 4：冗余清理 | ADP-07、D01、D-04 缓存及 K-05 请求复用，按收益顺序推进。 | 同输入、同状态输出与错误顺序相同；隐私 fixture 差分通过。单次扫描替换先证等价；没有支持退役证据的 shim 暂不删。 |
| 5：平台与质量补测 | workspace.py、前端、A2/A3 真机、宿主 E2E、真实摘要/检索质量。 | 临时 Git 业务结果、界面错误状态、真实设备与 PID/lease、固定匿名语料人工判据；未建立可靠分母前不虚设百分比。 |

### 分模块目标（后续验收目标，不是本轮测量值）

| 模块组 | 行 / 分支目标 | 必须捕获的缺陷 |
| --- | --- | --- |
| 身份、授权、游标、隐私、路径 | ≥95% / ≥90% | 重放污染他人回执、短日志误替换、原文落库、根外枚举；本次缺陷路径逐一覆盖。 |
| 作业、服务、更新、采集调度 | ≥90% / ≥85% | 后代未回收、stage-only 改活动代、旧周期冒充 force 完成。 |
| profiler compare 与结果归并 | ≥95% / ≥90% | 缺口径/缺字段/null、失败与 unknown 混淆；真实 producer 对照。 |
| bench 编排与共享生命周期 | 先 ≥85% / ≥80% | 清理/记账覆盖业务判定、外部副作用盲目重试；已高于目标的模块不降低。 |
| workspace.py | ≥85% / ≥80% | worktree 提交错误、dirty 误删、dry-run 改状态、元数据链接不一致。 |
| 硬件、前端、真实模型 | 本轮未测得，先建立场景与分母 | 覆盖比例不能替代设备、协议与质量验收。 |

正确性修复、等价重构、冗余清理、补测分别提交和审查；本 PR 仅记录这份基线与计划，没有完成表中的业务修改。

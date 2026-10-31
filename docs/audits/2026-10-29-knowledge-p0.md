# 2026-10-29 知识 P0 与组件更新验收

本记录冻结于源码合入与配对评测阶段：knowledge、四端插件与 bench 源码均已合入主线，最终评审提交的 CI 全部通过；16 次真实 DSH / Codex 尝试已结束。单点 SFA 的四组配对均自然完成、oracle 通过且观察到时间和 Token 下降；Codex 存在不对称临时文件错误，净收益受环境噪声混杂。复杂任务整体不退化验收未通过。该阶段未发布正式版本，未修改用户已安装运行时。

后续正式交付与实际安装回读见 [0.1.4 发布记录](../releases/0.1.4.md)及[自动升级验收](../releases/0.1.4/automatic-update-acceptance.json)。发布过程中发现的更新缺陷、恢复步骤及宿主重载边界单独记录，不改写本文的冻结评测结果。

## 依据与范围

`docs/releases/0.1.0/agent-trials-109.json` 中，Codex dspark 的 G1/G2 耗时为 267.57/440.22 秒，k3 为 333.77/445.88 秒，两组均通过；G2 分别出现一次查询与两次/三次精读。两个任务各有一次猜测依赖 `@1` 导致的精读失败。broker 自身处理仅为毫秒级，不能把全部额外时间归因于检索引擎耗时。历史 18 对 G1/G2 只有每格一次样本，不能据此推断总体退化幅度。

本轮只修改信息缺口决策、精读装配与精确引用，以及已安装组件进入现有更新事务的缺口；不增加路由模型、固定检索轮数或新的更新调度器。

## 评测源码身份与后续集成

评测准备时，候选分支均为 `codex/knowledge-p0-and-component-updates-20261029`；工作区位于 `/Volumes/data-tmp/tmp/mindie-component-updates-20261024/`。下表记录当时基线；当时的候选还包含未提交改动，不能把基线 SHA 当成候选完整身份。真实执行使用 bench 保存的冻结包与任务回执；后续源码合入没有修改这些历史身份。

| 仓库目录 | 基线 SHA |
| --- | --- |
| `knowledge` | `6e921b205c00d592c25f849653cbfb72b73fe318` |
| `codex` | `53fe6ce4130aebc11be6d8af39a60c0db7739252` |
| `kimi` | `3813383c6b100294cb5ea4e9bd9d97a6ecfc1cae` |
| `dsh` | `670b776b675c0b6dd93faef289e6538135e1f0db` |
| `cc` | `e1ab115627c632654dc3e9e6db9a056a20280589` |

旧开发检出的 knowledge 实际指向 0.13.1 源码，不能代表已安装版本。最初临时改动已移植到上述当前基线，并仅撤销旧目录的本轮 delta，保留用户所有既有修改。

用户要求先提交合入后，四端分别整合了更新的主线 SSH 与组件入口实现。knowledge 源码版本提升到 0.13.5，以已纳入主线的不可变评审源码提交作为四端开发依赖；它尚未成为正式 Release。版本提升让开发基线与已发布的 0.13.4 具有不同身份，避免同版本不同 SHA 被现有选择器拒绝。正式目标仍经过原有 Release 校验；源码基线只经过既有 `Catalog.source()` 路径，不伪造发布或基准回执。后续正式 0.13.5 必须绑定同一源码 SHA；若发布准备改变源码提交，应递增组件版本并同步宿主依赖。

四端统一锁定 `107f78d547707a35ea356b686bcb125448381e4e`，knowledge 通过保留提交历史的 merge 合入，使已验证的依赖 SHA 保持不变。以下是最终集成提交，不是前述性能实验的冻结身份：

| 仓库 | PR | 最终评审源码 SHA | 主线合入提交 |
| --- | --- | --- | --- |
| knowledge | [#103](https://github.com/mindie-agent/knowledge/pull/103) | `107f78d547707a35ea356b686bcb125448381e4e` | `f65adc8de4489f6c8cd08224cffc6c738cb86b5b` |
| Codex | [#75](https://github.com/mindie-agent/mindie-agent-codex/pull/75) | `d687f0ab317fca6b2a382dcf834632ec586bb49e` | `380375fa3c78f386b6748ed772e9936c8ad60b9d` |
| Kimi | [#55](https://github.com/mindie-agent/mindie-agent-kimi/pull/55) | `f3d2ffd5e370d4dde2a1eb59c19fb0609dd0d763` | `896e63eb6a1d1a1eccfcca76a7b16ae539563bb4` |
| DSH | [#26](https://github.com/mindie-agent/mindie-agent-dsh/pull/26) | `448c72d610173d12286bc0eccd7e63c7533ec7a2` | `559f44cfac91a8f352b226a592d1cdb257ed67df` |
| Claude Code | [#56](https://github.com/mindie-agent/mindie-agent-cc/pull/56) | `510ff2ede735e643ac3d38ca700c13182deac0fb` | `316520c0e5c41d245cc6fe7fcc3752c7d83e1758` |
| mindie-bench | [#30](https://github.com/mindie-agent/mindie-bench/pull/30) | `32e71c3c7d1dd6c56799722104014721830ee708` | `8c3f047cf97df01a8c25258c8bbe4828237d8dd2` |

## 四端入口与运行时

| 宿主 | 保留的原生约束 | 官方规范 |
| --- | --- | --- |
| Codex | 手动激活授权、私有 `knowledge_cli.py`、JSON stdin；只有需要知识调用才发现 catalog | [Skills](https://developers.openai.com/codex/skills/) |
| Claude Code | `disable-model-invocation`、原生 tool-use 身份，不由模型传会话 ID | [Skills](https://code.claude.com/docs/en/skills) |
| Kimi | 手动入口、`mindie_entry init`、每次调用的新 nonce | [Skills](https://www.kimi.com/code/docs/en/kimi-code-cli/customization/skills.html) |
| DSH | `whenToUse`、现有手动注入、`mindie_entry`；同步 host3 与 Python MCP 描述 | [Skills subsystem](https://deepseek-harness.github.io/deepseek-harness/en/reference/subsystems/skills) |

四端都根据下一步的信息缺口决定是否检索。当前代码、必要调用方、断言不变量及验证路径足够时允许零检索；文件名明确本身不构成跳过依据。缺少现场事实先 probe，缺少会改变行动的契约或机制才查询，准确 ref 可直接精读。知道下一步和必要前提即停止加载，验证失败或新证据允许重新检索。

graded 单条和批量精读复用同一完整依赖闭包；兼容 `content` / `frontmatter` 字段计入最终响应预算，不能裁剪后再追加。预算不足时返回明确未加载状态，不截断可执行规则。依赖返回真实版本引用，`known_refs` 只扣除仍完整可见的同版本正文。

复核还修复了已可见目标的前提被预算裁剪误删的问题：本次请求 A、B，而 A 的精确当前版本已在上下文中时，淘汰 B 仍须保留 A 缺失的前提 P；如果预算确实容不下 P，则明确报告 P 的 `budget_excluded`。修正继续复用现有闭包。该项和四端对单条兼容字段的说明补充发生在性能实验冻结之后，没有改动冻结包；原生性能配对不冒充该新增边界的实测证据。

原生检查还发现 Codex 主线 `knowledge_cli.py` 缺少自身脚本目录初始化，无法按 Skill 的 `python -I` 命令导入 `admission_ops`。本次复用既有入口做法修复；真实隔离子进程验证未授权拒绝且不自激活、授权后能返回 schema。配对两臂共同加入此启动修复，单独记录，不计作 P0 策略收益。

## 自动更新边界

共享 inventory 已覆盖 knowledge、remote-dev、diagnostics、profiler、sim、coordinator、npu-top 和 mindie-bench。其原有范围是选定解释器内、具有官方不可变安装回执的已安装组件。

本次补齐四端标准 `component_commands` 的独立 Python 环境：共享 `component_bindings` 识别官方 `python -m` 命令并读取版本下限，各端继续使用现有 generation、空闲切换与比较交换。元数据只提供版本下限，不能替代不可变源码身份或正式 Release 回执。构建候选后切换解释器和标准模块命令；自定义 wrapper、裸 console script 与仅通过 PATH 找到的命令不被擅自接管，不修改原外部环境。

四端在构建前读取版本下限，激活准备再次核验当前外部版本下限，随后按各端现有绑定与命令快照做比较交换，保护并发配置并阻止版本回退。Codex 在构建前保存完整绑定快照，恢复路径继续使用该快照。多个外部解释器共用 15 秒元数据预算。软件更新保留用户知识、授权与在途任务；不把“覆盖旧代码”解释为删除知识数据或强杀正在工作的进程。

合入前复核还覆盖旧安装的首次升级：Codex 的旧比较快照没有命令字段，新协议明确包含空命令映射，并在接收旧快照时保留当前命令与完整的后续比较交换；插件更新恢复保留构建前快照。DSH 的旧更新器只会准备核心组件，新候选安装入口因此必须在发布前通过现有构建路径补齐标准绑定。Kimi 保留旧 controller 使用的 bootstrap requirements，源码版本下限与实际构建同时读取 active overrides。旧 runtime 目录可供已加载调用继续使用，激活目标切换与目录回收是不同操作。

以下是配对评测期间的本机只读观察，不是后续合入或其他并行发布后的安装状态：

- Codex/Kimi 已受管安装为 knowledge 0.13.4、remote-dev 0.10.8、diagnostics 0.5.4。
- Codex 外部工具环境为 profiler 0.5.0、sim 0.7.1、coordinator 0.6.3，来自本地 wheel，原来未进入正式 inventory。新元数据接口已实际读取这些版本，不伪造 VCS 回执。
- DSH 0.1.2 仅安装在 web profile。web 最近日志为 2026-10-26，早于 0.1.5 的 2026-10-27 发布；当前其他运行 profile 未安装该插件。更新依赖受管 profile 启动，现有证据不能认定它的更新器执行失败。
- 最初检出的 Kimi、DSH、Claude Code 尚无 Codex 式外部 `component_commands`。合入前复核发现更新后的三端主线已提供此绑定，因此本轮补齐三端适配，不能沿用原来的“不需要适配”结论。

新增 `required_components` / `read_versions` / `component_bindings` 尚未正式发布。开发集成先合入 knowledge，四端 pin 与 lock 统一指向已纳入主线的评审源码 SHA；Kimi 只更新 active overrides，保留不可变 bootstrap requirements。正式交付仍需组件与宿主配套 Release 和兼容资料，再做已安装版本回读；不能把本轮源码测试称为所有机器已完成自动升级。

真实正式 Release 发现验证已完成：28.794 秒，21 次元数据与 12 次发布资产读取成功；六个选定组件均通过现有正式身份与基准资产校验。新增选中 coordinator 0.6.3、profiler 0.5.0、sim 0.7.1，三个核心组件保持当前正式版本。完整身份见[机器可读回执](2026-10-29-component-release-discovery.json)。本项仅证明正式目标可选，没有构建或发布这套组合，用户 profile 字节保持不变。

## 已完成验证

下表记录性能实验收尾时的定向结果。合入前新增的共享绑定适配、依赖更新和各平台 CI 结果另行记录；历史结果不冒充最终提交的验证证据。

| 范围 | 结果 | 证明边界 |
| --- | --- | --- |
| knowledge 预算、graded、反馈、探索 | 66 passed、1 skipped / 7.54s | 最终源码重验，含可见目标前提保留；外部 knowledge-operators checkout 条件导致一项跳过 |
| knowledge 组件选择与构建 | 20 passed / 0.19s | 正式发布验证、版本下限、精确锁、失败不发布 |
| Codex 更新、激活、恢复 | 77 passed、17 subtests / 8.05s | 标准命令迁移、空闲切换、失败和并发修改 |
| Codex 私有 CLI 隔离启动 | 1 passed / 0.62s | 真实 `python -I` 启动及手动授权拒绝/允许边界 |
| DSH 更新与 idle binding | 12 passed、2 subtests | 既有更新事务 |
| Claude Code 更新与安装 | 23 passed | 既有组件准备与安装边界 |
| Kimi 更新与恢复 | 22 passed / 36.11s | 组件切换不改原生插件身份，失败保留旧绑定 |
| 四端入口静态检查 | 通过 | Python AST、JSON、DSH 语法、LF、链接、原生 frontmatter 保持 |
| bench 私有知识统计及汇总 | 53 passed / 0.41s | 缺测不转成零，具名观察下界保留，Token/费用口径不变 |
| bench 原生终端与临时文件 | 2 passed / 0.16s | 实际 zsh/Seatbelt 子进程，heredoc、here-string 可用且外部写仍被拒绝 |

Codex catalog 使用当前受管 remote-dev 0.10.8 时为 8/9 通过：唯一完整 snapshot 差异为主线原有的七项 remote schema/description 差异；本轮 knowledge 描述与真实生成结果一致。该项不标为全绿，也不混入此次知识因素配对。

以上是定向开发验证，不是四端完整发布门禁、NPU 性能或跨机器自动升级验收。

四端的最终依赖集成使用真实安装的任务专用环境，没有通过 `PYTHONPATH` 绕过依赖；knowledge 本地定向测试使用源码导入，独立安装与打包由最终 CI 验证：

| 范围 | 合入前本地验证 |
| --- | --- |
| knowledge | 通过 `PYTHONPATH` 导入源码，预算、探索、共享绑定、组件构建等整组 120 passed、1 skipped / 13.08s；最终 Windows 路径预期修正后绑定测试 3 passed / 0.03s |
| Codex | 最终锁文件非 editable 安装；更新、首次升级、恢复、bootstrap、授权、私有 CLI 与 catalog 八文件 145 passed、35 subtests / 17.43s；最终仅修正 Windows fixture 路径与 venv 元数据定位，两文件重验 71 passed、17 subtests / 3.55s；兼容声明和宿主接口注册校验通过 |
| Kimi | 最终 active overrides 安装与 preflight 通过；更新 9 passed，原生边界 59 passed、16 subtests |
| DSH | 最终 pin/lock 和当前组合声明一致；49 passed，原生 JavaScript 检查 1 passed |
| Claude Code | 最终锁文件安装；64 passed，包含 MCP E2E |
| mindie-bench | 73 passed / 17.54s；Ruff、LF 与 diff 检查通过 |

六个实现仓库的最终评审提交均通过各自全部 CI 后合入：knowledge 覆盖 Linux、macOS、三个 Windows 分片及打包；四端插件覆盖 Linux、macOS、Windows，Codex 额外通过原生宿主 0.162.1 / 0.164.0；bench 通过 Linux、macOS 检查。所有 PR 的设计原则 checklist 与 LF 门禁均通过。开发测试覆盖自动重绑、旧入口首次升级与失败恢复，但没有发布安装包或修改用户已安装运行时。

## 配对验收设计

使用现有真实 runner、原生 DSH `host3.mjs` 和 Codex UserPromptSubmit 授权加私有知识 CLI；不得以旧 first-party MCP 替代原生 Codex 验收。Codex 指定 `home/codex/gpt-6.1-sol` / `xhigh`，DSH 使用现有 `deepseek-flash` / `max` 配置。配置名称不替代实际运行日志中的模型身份。

首批为简单 dspark 修复与较复杂 profiler 统计修复，各两宿主、两政策、两次重复，共 16 次，以 AB/BA 交错。前后均基于同一现代主线，候选只含入口及预算 P0；相同 corpus、依赖、任务输入、oracle 与资源预算，实验中冻结自动更新。复杂案例标记为 `seeded_local_engineering_fixture`，两个案例均为 L2 CPU 验证，不声称是历史上游事故或真机 NPU 验收。

以上为初始计划。初轮暴露任务描述和 oracle 边界后，暂停 DSpark 的剩余重复；新增明确单点 SFA 案例前重新记录输入、相同预算和 soundness，不改已运行轨迹，也不把任务更换后的结果与旧任务组成配对。

单独记录任务结果、查询/精读次数、实际模型用量、墙钟与失败成本。缺失用量、基础设施失败、未完成运行保留原状态；小规模 pilot 即使通过，也只能支持这两个案例的结论。

准备期间两题真实 soundness 均完成：未修复实现不通过，gold 修复通过。首个付费 DSH attempt 暴露旧 bench 原生配置未传 `mcpPluginUrl`，日志明确插件未挂载，不能纳入 P0 配对。其实际调用与成本单独保留；修复后必须先通过真实宿主挂载 catalog 检查再启动新 attempt，不能用 Store/MCP 单独启动成功替代整条宿主加载链。

### 真实结果与纠正

| 任务 / 宿主 | 基线 | P0 候选 | 当前判断 |
| --- | --- | --- | --- |
| DSpark / DSH | 254.54s；60 次模型请求；oracle 通过，原生回合未自然结束 | 277.93s；60 次模型请求；修订 oracle 重验通过 | 两臂预算耗尽，未证明降本 |
| DSpark / Codex | 上游 502/EOF；10 次请求，实际用量不完整 | 未重复此不确定请求 | `unknown`，不作策略通过或失败 |
| SFA / Codex，首对 | 144.93s；13 次模型请求；自然结束，oracle 通过 | 103.83s；11 次模型请求；自然结束，oracle 通过 | 观察前台时间降低 28.4%；临时文件噪声 2:1 |
| SFA / Codex，反序 | 133.57s；13 次模型请求；自然结束，oracle 通过 | 46.08s；6 次模型请求；自然结束，oracle 通过 | 观察前台时间降低 65.5%；临时文件噪声 1:0 |
| SFA / DSH，首对 | 169.22s；43 次模型请求；自然结束，oracle 通过 | 117.46s；38 次模型请求；自然结束，oracle 通过 | 前台时间降低 30.6% |
| SFA / DSH，反序 | 209.85s；55 次模型请求；自然结束，oracle 通过 | 128.05s；31 次模型请求；自然结束，oracle 通过 | 前台时间降低 39.0% |
| profiler / DSH | 283.95s；50 次模型请求；oracle 通过 | 286.52s；50 次模型请求；oracle 通过 | 两臂未自然结束；候选 Token 增加，不判验收通过 |
| profiler / Codex | 373.01s；23 次模型请求；自然结束，oracle 通过 | 410.30s；33 次模型请求；自然结束，oracle 通过 | 前台时间增加 10.0%；Token 指标方向不同，不判总成本不退化 |

DSH 两臂具名 query/explain 分别为 2/1 与 0/0；这些数字不能排除 shell 直接读取 corpus。已完成轨迹审查表明，两组都在定位、核对环境、寻找验证方法上花费大量动作；第一次编辑分别约在 173.94s 与 179.93s，减少知识调用并未促成更早修复。

DSpark 提示虽然点名了方法和不变量，却与历史 snapshot 不完全一致：`_mtp_hidden_buffer` 已被定义为 `None`，实际需修分配条件；提示中的 `build_for_drafting` 除法已不在该处，真实错误是 `build_req_metadata` 的调用参数。该题保留为有定位信息但存在矛盾的两点案例，不能代表无歧义的单点自包含修复。

候选第一次 verifier 失败来自 pilot 错用 baseline Python，而 sandbox 只允许 candidate 环境。按正确解释器对保存的原产物重新验证后，又发现 AST oracle 没有装载候选合法提取的顶层 helper；这类 oracle 盲区不能判为业务失败。原始 receipt、stderr、源文件 hash 与零模型 replay 均保留，不重写原结果。

独立 oracle 修订增加了通用的顶层函数定义加载，不识别候选 helper 名，不执行模块导入或初始化，也不修改业务期望值。统一 CPU 解释器重验历史 base、gold、两臂原始 archive：修订前为 0/1/1/0，修订后为 0/1/1/1；候选修订前的失败是 helper `NameError`。八次执行合计 11.45 秒、零模型调用，目标字节保持不变。修订只确认两臂产物满足既有 CPU 业务断言，不改变耗时或预算耗尽事实。证据位于 bench 的 `modern/oracle-revision-dspark-helper/`。

Codex 原生知识通过私有 CLI 进入，旧 scorer 的具名工具计数可能漏记并返回数值零。本轮以原生命令证据核对可见调用；覆盖不完整部分明确为 `unmeasured`，不以数值零宣称绕过检索。新增统计修正使绝对 query/explain 数量、知识时长及其 remainder 保持 `null`，另外保留具名调用观察下界；汇总和五组件报告也不再把缺测或部分覆盖转成数值零。53 项定向测试通过，未更改正在运行的冻结环境或原始 receipt。实际模型 token、墙钟和独立 oracle 分别报告。

SFA 首个 Codex 配对的未缓存输入为 62,406 → 50,528，缓存输入为 602,624 → 443,520，输出为 5,450 → 4,182，gateway 用量均完整。基线轨迹含私有 CLI describe/query/explain 共 1/2/1 次；候选已枚举命令中未观察到私有 CLI 或显式 corpus 读取。总读取覆盖仍不完整，因此只报告可观察行为，不声称已测得绝对零检索。该题是明确指向单文件、单方法和跨草稿步缓冲区不变量的 CPU 修复案例；两臂任务 hash 和验证预算一致。

后续完整命令审计发现，Codex SFA 首对基线有两次 heredoc 临时文件权限错误、候选有一次，反序基线有一次、候选没有，均自行恢复。这属于不对称的环境噪声：原始完成态、oracle 和实际用量仍有效，但不能把时间差全部归因于 P0 路由，也不能据此估计纯知识 RPC 耗时。零模型定位确认 bench 只绑定了 `TMPDIR`，zsh 的 `TMPPREFIX` 仍指向未授权的 `/tmp/zsh`。最终 bench 源码已将其绑定至现有 profile 临时目录，未扩大 sandbox 权限；真实进程回归通过。该基建修正发生在付费配对后，原始错误、冻结包和既有结果全部保留。

SFA 首个 DSH 配对的未缓存输入为 87,572 → 61,039，缓存输入为 3,144,192 → 1,984,384，输出为 25,533 → 17,215，gateway 用量均完整。具名 query 为 2 → 0、explain 为 0 → 0；同样不将具名工具观察范围扩大为所有内部读取。

反序 SFA 的 Codex 未缓存输入为 58,150 → 44,043、缓存输入 588,544 → 177,280、输出 5,709 → 1,774；DSH 为 88,862 → 75,579、3,935,616 → 2,015,232、33,292 → 22,006。两宿主两次重复共八场均自然完成且原始 CPU oracle 通过。Codex 两次候选轨迹未观察到私有知识调用，DSH 第二次候选实际查询一次；策略允许根据缺口检索，并不强制始终为零。

复杂 profiler 的 DSH 候选未缓存输入为 151,596，高于基线 97,377；缓存输入为 5,334,784，高于基线 4,433,408；输出为 56,896，高于基线 46,652。原生事件和 broker 证明两臂确实耗尽 50 次请求，没有被 runner 漏记的自然完成。基线验证通过后仍扩展可选 fallback，候选也继续多参数 fallback 验证。基线传入 `Ascend910B` 读取到了 SOP，但 fixture 只提供 `fixture:two-rank`，该硬件条件没有任务事实依据；候选缺条件的精读被正确拦为 `condition_unknown`。这既不能判定复杂任务总体验收通过，也不能把全部差异归因于检索耗时。候选没有交付正文，不曾触发本轮复核新增的混合目标裁剪修正。

复杂 profiler 的 Codex 两臂均自然完成且 oracle 通过。候选未缓存输入 81,822 低于基线 105,034，输出 16,282 低于基线 17,550，但缓存输入 2,374,784 高于基线 1,694,720，前台时间增加 37.29 秒。没有可靠费率时不能把这种混合结果折算为美元收益。本轮不追加同一复杂 fixture 的付费重复来筛选正向结果，保留尚未通过整体不退化验收的结论。

已通过真实 Codex CLI 的零模型检查：两臂的 `UserPromptSubmit` 授权使用实际 `thread.started` ID，实际请求携带指定模型和 `xhigh`。请求在本地 HTTP 400 拒绝端点停止，外部 provider 调用为零；这证明宿主接入，不是任务通过。证据保存于 bench 的 `reports/p0-adaptive-knowledge-20261029/modern/preflight/codex-native-host-zero-model/`。

### 验收结论与交付边界

这批源码修复和单点任务降本信号成立，但“复杂任务整体不退化”的门槛尚未通过，不能标记 P0 总体验收完成。任务仅覆盖小规模 CPU 行为 oracle，不能外推为 109 场总体结果或 A2/A3 真机性能结论。后续应先解决离线知识规则继承硬件条件的适用性问题和验证通过后继续扩展的收敛问题，再做新的冻结配对；不补造条件，不靠筛选成功重复改写本轮结论。

正式覆盖已安装旧运行时还需要 knowledge 新 Release、配套兼容资料、插件 Release，以及安装后版本回读。本轮源码集成更新四端精确 pin/lock，使新更新代码与对应 knowledge API 一起进入开发基线；这不等同于正式发布或已安装环境切换。

完整 16 次尝试、未完成和不确定请求的实际消耗保留在 bench 的 `reports/p0-adaptive-knowledge-20261029/modern/README.md` 与 `attempt-results.json`。7 次 Codex 尝试中有一次用量不完整；没有已验证费率，不报告美元成本。所有模型任务已结束，没有后台付费尝试仍在运行。

## 后续本地整改：离线条件、收敛与组件桥

以下记录 2026-10-29 在当前主线 checkout 上完成的本地整改，与上面的冻结实验分开。
knowledge 基线为 `87a80ee6`（0.13.7），四端依次为 Codex `dbdd7de9`（0.1.13）、
Claude Code `3a062e29`（0.1.10）、Kimi `e1f1f309`（0.1.10）、DSH `2011a43a`
（0.1.9），bench 为 `90e66615`。这些 SHA 标识修改前主线；本节结果来自其上的
未提交改动，不是 Release、安装切换或新一轮真实模型配对。

### 条件继承的修正位置

`graded` 没有把父子条件合并为一个宽松字典，而是将 `inherits_from` 的完整闭包
作为必需前提，逐条检查实际条件。该机制对 UB/L1 对齐等硬件规则是必要的；
本次保留其三值求值与整条预算裁剪，只补充明确的不变量说明和行为回归。
错误出在语料把相关主题当成必要依赖。

七库共检查 450 个单元、667 条原始直接依赖。本次修订两个库的七个单元并递增
revision、重建 routing/shard 索引：

- `infer-observability`：msprof 时钟公理不再依赖某次观测机器的拓扑摘要；
  SQLite CTE 解析和 pseudo-fast rank 排障不再要求无关的 910B/910C、现场采集
  或另一固定分析器版本前提。正文仍要求检查真实格式、时钟和统计边界。
- `infer-distributed`：Dynamo 队列/取消、KV router 和 Mooncake 主机 API 规程
  去除无关 SoC、TGI 实现或 Ascend PD 部署依赖；HCCL 日志分析可先定位 rank
  参与差异，设备/链路检查和现场恢复验收仅在实际需要的分支执行。

七个真实单元的旧版/新版 query 与 explain 对照均确认：不补充 SoC 也能加载
适用的通用规程。硬件反例仍确认 UB/L1 公理在仅有 `fixture:two-rank` 时返回
`condition_unknown`，显式错误芯片返回 mismatch。两个修改库各保存
`docs/evidence/2026-10-29-offline-condition-scope.json`；原有 `content_digest`
按已核实的历史算法重新计算。七库索引检查全部通过。

历史 profiler 专用 SOP 位于私有评测语料，未进入当前七库主线，且含该 fixture
的精确答案数字。本次未复制它到主线，也未修改历史冻结语料、任务事实或回执。

### 任务结束与 C6 准入

四端 Skill 增加一致边界：请求的不变量和受影响行为验证通过后输出完成结果；
只有具体失败、必需验收或新证据才继续增加分支。离线修复不补造硬件条件，
通过后不继续扩展无证据的多参数/兼容 fallback。没有增加模型路由、调度层或状态机。

DSH 历史轨迹和驱动均表明，预算内最后一次请求仍可产生合法完成事件；旧 G5 A
失败不是驱动漏记。共享 `native_capture_payload()` 现在对四端都显式要求
`native_completed`，补齐 Codex/CC 在会话身份先于完成出现时的采集缺口。
Kimi 当前实现将身份和完成同时绑定在 resume hint 上，本次是统一显式契约，
不宣称已复现其独立绕过漏洞。准入失败记录 `capture.stage=native_admission`
及宿主错误，并明确 `capture_model_calls=0`；业务 oracle 的通过结论保留。

实际安装的 CC/Kimi 二进制通过本地协议 provider 返回完成事件后均能准入。
移除真实 CC 事件流的终态事件，旧入口会准入而新入口拒绝；移除 Kimi resume
hint 后两版均拒绝。该负对照没有付费模型调用，只验证完成信号和产物绑定。

### 组件桥与验证

四端 sim/profiler 描述已统一，并保留 Codex 原有的新版 sim 描述与测试。
真实 CLI 契约覆盖 operators/graph/predict 边界、空 stdout 的文件输出、错误
退出码/stderr，以及 partial study 保留报告但不将失败候选列入排名。
离线 profiler 不要求 NPU 租约，导出数据进入 sim 前仍需显式身份和边界映射。

最终复验使用明确的 sim 0.8.0 wheel，SHA256 为
`20831058a4221e7a3e9feedb4d025086c6d37630c59bcddf3bfbe439ace9401e`。
该 wheel 尚未正式发布；测试通过 `MINDIE_SIM_CONTRACT_PYTHON` 选择临时解释器，
未改插件发布 pin 或用户 profile。旧 sim 依赖环境会明确跳过新版专属契约，
不能据旧环境的通过结果声称完成新版验收。本次下表四端结果均没有 skip。

| 范围 | 最终本地结果 |
| --- | --- |
| Codex 组件、capture、catalog | 74 passed / 8.76s |
| Claude Code 组件桥 | 18 passed / 2.19s |
| Kimi 组件桥（沿用 CI 的 `pythonpath=tests scripts`） | 14 passed / 2.34s |
| DSH 组件桥 | 13 passed / 2.13s |
| knowledge 受影响闭包、预算与变更测试 | 64 passed、1 skipped / 0.76s；skip 是既有 operators 历史目录测试 |
| bench 完成态、采集与预算回归 | 43 passed / 16.34s |
| 四端、knowledge、bench 的 LF 检查与受影响 diff 检查 | 通过 |

Codex catalog 在当前精确锁定的 `remote-dev 0.11.1@2a750ec8` 上为 9/9，
快照无需修改。上文针对旧 0.10.8 的七项差异保留为历史结果；不能用旧测试环境
重录当前快照。profiler/coordinator 同样使用插件的精确 pin（0.5.1 / 0.7.0）。
七个语料库未配置代码仓同款 `.gitattributes`/`.editorconfig`，因此不将借用的
LF 脚本配置检查称为全通过；本次检查未发现语料 CRLF。

这些结果证明条件适用性、组件契约和完成态准入修正。它们不证明真实模型已经
在复杂任务上总成本不退化，也不等于 G5 A 到 C6 提炼成功。新的真实配对仍应
保留 profiler 的 50-turn 和 G5 A 的原始 80-turn 预算，固定两臂任务、oracle
与模型身份，报告所有尝试；不以提高预算、补造硬件或筛选一次成功改写历史结论。

---

## 2026-10-31 自然语言测试语料重写与双宿主（DSH + Codex）实测闭环

完成上述离线条件与收敛边界整改后，我们进一步将 `mindie-bench` 下全部 20 个 `tasks/zh-vague/*/instruction.md` 任务提示词还原为真实开发者的自然人话描述（移除开头的审计免责段落、移除括号内逐行剧透代码改法的提示、修正 `dspark-mrv2-drafter-crash-zh-vague` 中误导性的 `build_for_drafting` 除法描述，并将 4 个组件题从字典答案清单改为自然排障/契约说明），同时全部重跑通过零模型行为级 `soundness` 校验（20/20 任务 `before_reward=0.0, after_reward=1.0`）。

在此基础上，使用包含最新 9 组件构建（`mindie-knowledge 0.13.7`、`remote-dev 0.11.2`、`mindie-diagnostics 0.5.4`、`mindie-profiler 0.5.3`、`mindie-sim 0.8.1`、`mindie-coordinator 0.7.0`、`npu-top 0.3.0`、`mindie-agent-codex 0.1.13`、`mindie-agent-dsh 0.1.9`）的受管运行时与解耦了伪硬件依赖的语料库（`commit 7ff5325`），在 **DSH（`deepseek-flash` / `max`）** 与 **Codex（`gpt-6.1-sol` / `xhigh`）** 上分别对单点修复（`sfa-mtp-seq-lens-eval-zh-vague`）、双点投机解码崩溃修复（`dspark-mrv2-drafter-crash-zh-vague`）与复杂多阶段归因修复（`profiler-msprof-straggler-and-hbm-fix-zh`）进行了端到端实测（完整产物见 `mindie-bench` 的 `reports/human-corpus-eval-20261031/`）：

| 宿主与模型 | 任务 (`instance_id`) | Trial ID | 终态与判分 | 墙钟耗时 | 首次有效修改 | 模型请求数 | 知识调用 (`query`/`explain`) | Token 用量 (`uncached` / `cached` / `output`) | 相比整改前（2026-10-29）的变化 |
| --- | --- | --- | --- | ---: | ---: | ---: | :---: | --- | --- |
| **DSH** (`deepseek-flash`, `max`) | `sfa-mtp-seq-lens-eval-zh-vague` | `8cc48da37785` | `completed_pass` (`1.0`) | `227.83s` | `37.88s` | `38` | `0 / 0` | `80,902 / 2,755,200 / 38,697` | 自然完成，37.88s 即完成首次源码修改 |
| **DSH** (`deepseek-flash`, `max`) | `dspark-mrv2-drafter-crash-zh-vague` | `f3d8c90ca2be` | `completed_pass` (`1.0`) | `217.02s` | `104.24s` | `47` | `5 / 0` | `120,441 / 4,459,520 / 34,466` | 整改前因提示词误导 `build_for_drafting` 耗尽 60 轮预算未完成；整改后 **217.02s 自然完成并通过原版行为裁判** |
| **DSH** (`deepseek-flash`, `max`) | `profiler-msprof-straggler-and-hbm-fix-zh` | `24e9f9cc1873` | `completed_pass` (`1.0`) | **`67.05s`** | `45.42s` | **`17`** | `2 / 1` | `66,912 / 898,048 / 11,917` | 整改前因 `condition_unknown` 与过度扩展耗尽 50 轮预算（`286.52s`）；整改后 **17 轮、`67.05s` 自然收敛通过（提速 4.2x，Token 下降约 80%）** |
| **Codex** (`gpt-6.1-sol`, `xhigh`) | `sfa-mtp-seq-lens-eval-zh-vague` | `df166dc93d0a` | `completed_pass` (`1.0`) | `114.76s` | `61.59s` | `8` | `0 / 0` | `366,472 / 0 / 5,827` | 8 轮请求、`114.76s` 自然完成（前两轮因 Tailscale 远端网关 502 记为 `unknown` 并完整保留） |
| **Codex** (`gpt-6.1-sol`, `xhigh`) | `dspark-mrv2-drafter-crash-zh-vague` | `6e25c153c562` | `completed_pass` (`1.0`) | **`165.99s`** | `135.57s` | **`10`** | `0 / 0` | `532,920 / 0 / 8,142` | **10 轮请求、`165.99s` 自然完成**，直接通过未修改的冻结行为裁判 |
| **Codex** (`gpt-6.1-sol`, `xhigh`) | `profiler-msprof-straggler-and-hbm-fix-zh` | `6c190ec1ce19` | `completed_pass` (`1.0`) | **`132.97s`** | `77.85s` | **`16`** | `1 / 1` | `876,913 / 53,760 / 7,718` | 整改前需 23–33 轮、`373s–410s`；整改后 **16 轮、`132.97s` 自然收敛通过（提速约 3x）** |

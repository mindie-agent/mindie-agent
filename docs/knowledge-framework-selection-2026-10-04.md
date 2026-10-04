# 经验组件框架选型与集成评估

观察日期：2026-10-04。三个子代理分别研究 ReMe/ACE/claude-mem、LangMem/Mastra、Basic Memory/Mem0/OpenMemory/Hindsight；查看官方当前文档、固定提交源码和测试。仓库调查不等于运行上游测试或证实模型效果。另做 LangMem 固定发布包的隔离接口试接，结果单列。

本文保留最初选型依据和试接结论；“当前决定”描述该阶段的取舍，不是后来运行时的 API 或验收清单。已落地的 ReMe 组件边界、LangMem 调用和真实材料测量见[主架构](transcript-reuse-architecture-2026-10-04.md)及[实施证据](knowledge-review-2026-10-04/evidence/implementation-review.md)。

## 1. 结论与选型标准

**本轮宏观组合定为ReMe当前文件库与检索＋LangMem独立增量摘要＋GitHub/Grok共享，MindIE保留薄接入边界。** 见[主架构](transcript-reuse-architecture-2026-10-04.md)。这是推荐实现基线，不是生产已可用：各部件仍需以同一语料验收质量、累计费用和维护收益。Basic Memory保留为文件检索备选，不同时接入第二套文件库。Mastra的无数据库摘要函数也可用，但为现有Python/Harness接入增加的运行时和模型桥接更大。

本次没有找到无需适配便能覆盖“获准采集—轻量处理—普通 Markdown—GitHub 贡献—Grok 维护—独立客户端复用”的完整产品。这个结论针对所查九个项目和当前版本，不是声称不存在其他方案，也不是拒绝整体替换现有实现。

比较时保留五个产品合同：用户侧运行、参考经验而非认证答案、当前正文且可迁移、成本可见且有界、失败与未知不隐藏。现有数据库/队列/模块本身不受保护；外部框架若能接管更多职责并减少总维护，可以整体替换。不要接入一套框架后继续永久维护同职责的自有系统。

## 2. 逐项决策

| 候选 | 与目的契合的能力 | 为我们的流程增加的主要成本/差异 | 当前决定 |
| --- | --- | --- | --- |
| **LangMem** | 函数式 running summary；正常触发一次模型调用、不触发零调用；无需DB或图运行器 | LangChain相关依赖、Harness模型适配、覆盖/调用回执；超预算自动trim不能直接接受 | **优先直接试接函数**；候选实现可替换未完成的自有增量摘要，不引入记忆平台 |
| **ReMe** | 当前Markdown文件权威、BM25与链接、向量可关闭、进程内Job API | 默认auto_memory/tag/dream等Agent；会复制source记录；错误/保留需适配 | **选作文件/检索主组件，裁剪接入**；不打开默认演化管线 |
| **Basic Memory** | Markdown、本地SQLite、增量搜索/关系导航、原子索引测试 | 完整产品有第二套正文写入同步、较重依赖；AGPL许可与Python版本需核对 | **检索备选实验**，严格明确源与派生缓存的权威 |
| **Mastra OM** | 长对话观察/反思、异步批量；另有独立summarizeConversation | 完整OM存储世代和调度；独立摘要没有旧摘要cursor；Node/AI-SDK桥和内置重试 | **质量对照/未来整体替换候选**，当前不优先接整套 |
| **claude-mem** | 多Harness观察队列、渐进检索、付费发送未知等错误分类 | Node/Bun worker、SQLite与可选Chroma、观察/summary/压缩模型、更多持久数据 | **借鉴队列与消费方式**；整套接入目前没有足够净收益证据 |
| **ACE** | 有来源的局部经验修改思路 | 默认Generator/Reflector/Curator多调用；Curator读全playbook；操作/错误语义有缺口 | **借鉴GitHub维护方式**，不默认加入客户端 |
| **Mem0** | 本地库、多向量后端、抽取与查询 | 默认LLM+embedding及历史；解析失败可能空结果；Git修订需另写 | **不入当前主链**；以后仅在多后端需求真实出现时再比较 |
| **Hindsight** | 替换/删除、实体/时间推理、复合召回及较完整测试 | 真PostgreSQL/API、抽取/合并、多个派生表示和历史 | **暂留独立研究**，目前目标不足以支撑运行成本 |
| **OpenMemory** | 当前跨Harness会话迁移 | 当前CLI不是经验检索；旧MCP已归档；轮数修订不等于内容修订 | **排除当前集成范围** |

表中不以star数量、论文排行榜或README“低成本”口号替代验证。完整框架本地可运行不等于必须维护中心服务，也不等于没有本地进程、数据库和模型成本。

## 3. LangMem：可直接复用的最小摘要单元

固定发布包 `langmem==0.0.30`；所查main `48e3c11f5bb527282c7d5339c6a87a0b35abccfc`。研究核对发布wheel中的 `short_term/summarization.py` 与该main文件一致；MIT。使用 `summarize_messages` / `RunningSummary` 无需启用LangGraph图、BaseStore或后台反思。[固定源码](https://github.com/langchain-ai/langmem/blob/48e3c11f5bb527282c7d5339c6a87a0b35abccfc/src/langmem/short_term/summarization.py)

它能负责阈值判断、旧摘要与新增消息的组织、已摘要消息ID及边界更新；主功能直接调用模型的invoke。正常一次触发只需一次摘要调用，无默认二次最终全文重写。它解决输入组织，不负责技术经验判断、GitHub发布或隐私检查。

**关键限制：**输入超过预算时可裁掉最早待摘要消息，但已摘要范围仍可能覆盖这些被裁掉的消息。必须在外层按完整消息及实际token组织可容纳批次，核对覆盖，避免把裁剪当完成。模型输出额度也须在实际Harness适配层强制。摘要ID集合和调用方读取方式需要限于必要当前状态，不能又增长为永久历史。

包有langchain、langchain-core、langchain-openai、trustcall、langgraph、langchain-anthropic、langsmith、langgraph-checkpoint等直接依赖；功能无需运行它们全部能力，但安装和升级责任仍在。不能只凭函数几行调用就宣称依赖轻。[依赖文件](https://github.com/langchain-ai/langmem/blob/48e3c11f5bb527282c7d5339c6a87a0b35abccfc/pyproject.toml)

建议接法：已获准、已规则脱敏的新增公开材料 → 外层完整批次 → LangMem函数 → 现有受限Harness模型适配 → 确定性输出校验 → 当前头部/覆盖/用量同事务提交。不得让库获取原始session、执行工具、维护另一份存储或直接上传。

running summary原生是文本，不是MindIE的title/summary协议。试接需验证自定义提示和实际Harness结构化输出能在同一次调用返回所需头部，再确定性解析；不能悄悄增加一轮“把摘要再总结成标题摘要”的模型。

它真正替代的是增量输入与摘要状态的算法工作，不是所有当前核心。我们尚没有完整自有running summary，因而收益主要是少开发/少维护这部分，而非已经能删除大量现有代码。若固定首尾/结构化抽样已经满足消费质量且更便宜，也可能不采用增量方案。

## 4. ReMe、Basic Memory：文件检索可集成，但先证明优于现有FTS

ReMe固定 `4c54c2b650038eff2a5d0d77aaa61b3e836f1b18`，包元数据0.4.1.13，Apache-2.0，Python≥3.11。当前file-memory产品与旧论文/0.2、0.3分支不同。默认向量关闭、BM25配合文件链接，支持进程内 `start/run_job/close`，不必建立团队远端服务。[文件合同](https://github.com/agentscope-ai/ReMe/blob/4c54c2b650038eff2a5d0d77aaa61b3e836f1b18/docs/en/memory_as_file.md)、[嵌入测试](https://github.com/agentscope-ai/ReMe/blob/4c54c2b650038eff2a5d0d77aaa61b3e836f1b18/tests/unit/test_embedded_consumer_compat.py)

其默认auto_memory使用有文件读写能力的Agent，更新会读已有daily材料；另有auto_tag和夜间演化配置。Claude路径复制原始记录再取增量，通用来源库坏行可被跳过。完整引入要改造采集边界、保留和错误，不符合“开箱即可轻量”的假设。[默认配置](https://github.com/agentscope-ai/ReMe/blob/4c54c2b650038eff2a5d0d77aaa61b3e836f1b18/reme/config/default.yaml)、[CC采集](https://github.com/agentscope-ai/ReMe/blob/4c54c2b650038eff2a5d0d77aaa61b3e836f1b18/reme/steps/evolve/auto_memory_cc.py)

Basic Memory固定 `194afe165b3e7676496aaa53b70e39a78ea5aa4f`，Python≥3.12，AGPL-3.0-or-later。默认本地SQLite、可用本地embedding和hybrid检索；完整依赖和许可需按实际集成/分发方式单独核对。源码中NoteContent保存当前完整Markdown及文件同步状态，不能把完整产品当成无状态索引插件。[模型](https://github.com/basicmachines-co/basic-memory/blob/194afe165b3e7676496aaa53b70e39a78ea5aa4f/src/basic_memory/models/knowledge.py)、[依赖与许可](https://github.com/basicmachines-co/basic-memory/blob/194afe165b3e7676496aaa53b70e39a78ea5aa4f/pyproject.toml)

它的原子索引刷新、失败保持旧投影、更新世代和删除传播测试很有价值；本轮只阅读，未执行。[刷新测试](https://github.com/basicmachines-co/basic-memory/blob/194afe165b3e7676496aaa53b70e39a78ea5aa4f/tests/services/test_search_refresh_atomicity.py)

两者的最小实验相同：把同一份已脱敏的main当前Markdown快照作为只读源，用明确entry/revision映射返回命中与来源；关闭不需要的自动写入/演化/云服务，索引只能是可重建派生物。比较当前FTS、ReMe和Basic Memory的中文/代码/自然语言查询，测Recall@5、选读、冷启动、RSS、索引体积、修订和删除传播。现有FTS若已满足需求且更便宜，就不增加这层依赖；若外部模块更好，删除被替代的自有检索职责。

## 5. Mastra与claude-mem：可借用机制，不忽略完整运行成本

Mastra固定发布 `@mastra/memory@1.35.0`，tag commit `b21e46e19b469a25c8896bcee90afd58d6f1a890`；研究main为1.36.0-alpha.2，不用alpha替代稳定包结论。OM路径Apache-2.0，仓库ee区域另有许可，不混为一谈。[固定memory源码](https://github.com/mastra-ai/mastra/tree/b21e46e19b469a25c8896bcee90afd58d6f1a890/packages/memory)

`summarizeConversation`可无数据库使用，但没有previous-summary/cursor合同，本身不能接管我们的增量工作；默认重试8次，公共选项没有对应maxRetries/maxOutputTokens控制，结构化extract会再调一次模型。现有Harness需AI-SDK桥和Node运行时。完整OM提供Observer/Reflector与异步批处理，但增加存储/世代保留；活跃上下文阈值不是磁盘历史上限。适合在确实愿意替换整套记忆运行时的时候重新评估，不推荐只加独立摘要wrapper却继续自建全部增量逻辑。[完整源码分析](knowledge-review-2026-10-04/evidence/organizer/frameworks.md)

claude-mem固定 `bfc50259f64a4e0c9e81df849095683608e87ac8`，13.29.0；**当前Apache-2.0、多Harness**，旧AGPL/Claude-only介绍已不适用。[当前许可证](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/LICENSE)

它有SQLite、Node/Bun worker与默认可关闭的Chroma；工具事件生成observation、Stop生成summary，过长工具材料可额外模型压缩。保留历史已有裁剪和会话回收，不能笼统批评为无限重复全量输入。其成本仍需累计观察/summary/压缩与重试，而不是只看检索省token。[历史裁剪](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/src/services/worker/history-pruning.ts)

最值得借鉴的是transient/unrecoverable、quota和ambiguous paid-send分类，以及渐进读取。cloud sync默认关闭，不等于模型都离线；默认脱敏和遥测设置需独立核对，不能当作已满足我们的范围与数据处理合同。[错误实现](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/src/services/worker/provider-errors.ts)、[配置默认值](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/src/shared/SettingsDefaultsManager.ts)

## 6. ACE、Mem0、Hindsight与OpenMemory：为何当前不采用

ACE检查论文官方 `ace-agent/ace`，commit `82709de050e1db6e6ef2f07bcb0393560b94992a`，Apache-2.0。Curator输出delta，但输入仍含整份playbook；当前确定性应用主要实施ADD，UPDATE/MERGE/DELETE有TODO；默认训练流程多角色多次模型调用，错误还可能返回旧playbook与空操作。这不适合作为默认低成本贡献管线。Grok侧的局部更正可以借鉴其思想，用现有Git diff/PR实现，无需引入整套框架。[Curator](https://github.com/ace-agent/ace/blob/82709de050e1db6e6ef2f07bcb0393560b94992a/ace/core/curator.py)、[实际操作](https://github.com/ace-agent/ace/blob/82709de050e1db6e6ef2f07bcb0393560b94992a/playbook_utils.py)

Mem0固定 `abb81c88e1f738a8117d8293530fbc31a5ef8fd9`，包2.2.1，Apache-2.0。可以本地库运行，不必中心服务；默认抽取涉及模型与embedding、相近记忆和最近消息，SQLite history保留旧正文。provider异常有包装，但模型回复解析失败仍可能log后返回空列表，不能直接继承到第9原则下。`infer=False`省抽取仍有embedding和历史，若只是一个本地向量后端，完整框架收益有限。[抽取及错误](https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/mem0/memory/main.py)、[历史](https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/mem0/memory/storage.py)

Hindsight固定 `f7dd3f4fd7420f7beec60c32c965e5e5cf7be066`，API0.10.2，MIT。pg0仍是真PostgreSQL进程，外层有API与生命周期。retain/recall/reflect、后台合并、多个派生表示和默认历史有能力也有成本。它的replace、delete、去重和失败测试值得参考；只有需要跨时间实体综合推理时，完整接入收益才更明确。[pg0](https://github.com/vectorize-io/hindsight/blob/f7dd3f4fd7420f7beec60c32c965e5e5cf7be066/hindsight-api-slim/hindsight_api/pg0.py)、[替换测试](https://github.com/vectorize-io/hindsight/blob/f7dd3f4fd7420f7beec60c32c965e5e5cf7be066/hindsight-system-tests/tests/test_11_replace_document.py)

OpenMemory固定 `2df78cc48e5f688a771fee5b39899325accc2450`，当前CLI0.0.1/MIT。原MCP/dashboard移至archive且不积极维护；当前是跨Harness会话迁移，不是知识检索组件。sourceRevision用轮数，等轮数的正文纠正可能unchanged skip，不满足内容修订语义。[当前README](https://github.com/mem0ai/openmemory/blob/2df78cc48e5f688a771fee5b39899325accc2450/README.md)、[归档声明](https://github.com/mem0ai/openmemory/blob/2df78cc48e5f688a771fee5b39899325accc2450/openmemory-archive/README.md)、[orchestrator](https://github.com/mem0ai/openmemory/blob/2df78cc48e5f688a771fee5b39899325accc2450/cli/src/core/orchestrator.ts)

## 7. 什么继续直接复用

现有SQLite FTS5、Git/GitHub、Gitleaks和Harness模型通道已经是外部成果复用，保留它们不是“全部自研”。FTS索引不额外调用模型，但能否满足自然语言和中文查询需要本领域实际样例。[SQLite官方FTS5](https://www.sqlite.org/fts5.html)

Gitleaks是凭据模式扫描，不能替代来源共享范围或私有业务文字判断。官方当前声明仅继续安全补丁，后续聚焦Betterleaks；这属于依赖维护信号，不构成本轮立即换扫描器的理由。先修复我们已复现的跨段上下文和占位符合同，再用同一合成秘密集比较替代扫描器，避免“升级依赖”掩盖包装层问题。[Gitleaks官方README](https://github.com/gitleaks/gitleaks)

不因框架已有某能力就顺便引入：自动上下文注入、向量服务、图谱、隐式会话扫描、每轮反思、自动生成Skill、长期记忆历史均需对应用户目的。另一方面，如果新框架能够以更少维护完整兑现某段职责，应接受替换，不要求它沿用现有内部表结构。

## 8. 集成实验与采用条件

| 实验 | 真正替代的职责 | 继续保留的产品合同 | 采用条件 |
| --- | --- | --- | --- |
| LangMem函数式摘要 | 新增材料+当前摘要的组织、触发及running-summary算法 | 完整批次边界、实际模型额度、调用账、当前正文CAS、范围检查 | 无隐式裁剪/重复调用；真实小模型质量及累计费用优于合适基线；依赖负担可接受 |
| ReMe/Basic Memory检索 | 分块、词法/可选向量索引与关系读取 | Git当前快照权威、精确引用、删除传播、错误可见 | 相同语料检索/选读显著改善；本地资源与启动成本合算；只留一个生产检索实现 |
| 完整框架替换 | 若未来能接管队列/存储/采集，应删除对应自有代码 | 激活/授权、出站边界、当前状态、未知效果、公开修订合同 | 改造+迁移+长期维护总成本低于修复旧实现；完整链路通过 |

PoC通过接口调用不等于通过摘要质量。上游tests可复用作理解和候选回归，不能把“看过测试”写成“已经测试”。未做真实Luna调用时，费用和语义效果保持未验证；不以框架排行榜填空。

本轮LangMem 0.0.30已完成隔离试接：阈值以下零调用，两批完整新增材料各一次调用；第二批使用新材料加旧摘要，不携带第一批正文；状态可序列化，无额外数据库。自定义提示可同次返回title/summary供确定性解析。同时复现了超预算裁剪与输出额度不强制的风险，属于必须适配的边界。实验使用fake模型，仅证明接口/机制；[脚本、固定依赖与完整结果](knowledge-review-2026-10-04/evidence/organizer/langmem-spike/README.md)。

## 9. 详细研究附件

- [ReMe / ACE / claude-mem：固定源码研究](knowledge-review-2026-10-04/evidence/research-reme-ace-claudemem.md)
- [LangMem / Mastra：固定包与源码研究](knowledge-review-2026-10-04/evidence/organizer/frameworks.md)
- [Basic Memory / Mem0 / OpenMemory / Hindsight：固定源码研究](knowledge-review-2026-10-04/evidence/delivery/framework-comparison.md)
- [验收与四路线摘要对照](knowledge-experience-evaluation-2026-10-04.md)

所有推荐是基于上述实现边界的工程判断，尚无证据宣称任一框架已经在我们的真实业务上更便宜或更有效。

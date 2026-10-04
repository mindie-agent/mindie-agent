# Basic Memory / Mem0 / OpenMemory / Hindsight 源码调研

观察时间：2026-10-04。范围：官方文档、官方仓库当前默认分支、实现与测试源码。只读克隆位于临时目录；未安装依赖、启动服务、调用模型、读取真实会话或更改用户配置。下列测试是已阅读的上游测试，**没有在本机执行**；没有真实质量、时延、资源或费用测量。判断依据是 MindIE 的 Git/Markdown 正文权威、用户侧本地运行、全量脱敏正文分发、索引可重建、当前修订可追溯、错误可见与有界成本要求。

## 决策

没有一个候选能直接替换 MindIE 的采集—脱敏—经验贡献—反馈修订—Git 分发整条链。优先考虑 Basic Memory 作为可拔插的本地检索实验，限定由 MindIE 管理输入快照，只返回原文命中与来源；先验证全文检索，再验证本地 embedding 的增量价值。它是这组里与 Markdown 最接近的产品，但完整引入带来第二套写入/同步机制、AGPL 许可边界和较重依赖，不能把“file-first”的产品描述理解成“只需一个无状态索引包”。

Mem0 不建议进入主链。关闭抽取后主要得到向量存储适配，收益不足以默认接受额外的正文历史、会话存储和失败适配。Hindsight 暂列未来“跨时间综合推理”的独立实验；如果只是经验检索，引入整套事实抽取、实体、观察合并和数据库服务成本过高。原 OpenMemory MCP 服务已归档，不作为新集成基础；当前同名主线是会话迁移工具，不是知识检索框架。

## 固定版本

| 项目 | 本次审查 commit | Commit 日期 | 包元数据 / 许可 |
| --- | --- | --- | --- |
| Basic Memory | `194afe165b3e7676496aaa53b70e39a78ea5aa4f` | 2026-10-01T21:15:45-05:00 | Python >=3.12，AGPL-3.0-or-later |
| Mem0 | `abb81c88e1f738a8117d8293530fbc31a5ef8fd9` | 2026-10-01T21:46:18+05:30 | mem0ai 2.2.1，Python >=3.10，Apache-2.0 |
| Hindsight | `f7dd3f4fd7420f7beec60c32c965e5e5cf7be066` | 2026-10-02T18:52:39+02:00 | hindsight-api 0.10.2，Python >=3.11，MIT |
| OpenMemory | `2df78cc48e5f688a771fee5b39899325accc2450` | 2026-07-29T15:10:39+05:30 | 当前 CLI 0.0.1 / MIT；归档 MCP / Apache-2.0 |

本次浅克隆中各 HEAD 均没有指向该提交的 tag；固定 commit 才是这里的证据边界，不把包元数据等同于已验证的发布包。

## Basic Memory

Markdown+frontmatter+观察/关系结构与 MindIE 最接近，本地 SQLite 默认后端，无需团队维护中心服务；跨设备本地资料同步仍需 Git/Syncthing 等外部方式。产品有独立本地 CLI/MCP、文件监听、索引及写入工具。其结构化 Markdown 不等于原样兼容 MindIE schema，应验证 metadata、路径、标题/permalink 和删除/重命名语义。[官方技术文档](https://docs.basicmemory.com/reference/technical-information)、[格式实现约定](https://github.com/basicmachines-co/basic-memory/blob/194afe165b3e7676496aaa53b70e39a78ea5aa4f/docs/NOTE-FORMAT.md)。

全文检索不需要生成模型；默认安装包括 fastembed 和 sqlite-vec，因此 semantic 默认可开启，embedding 默认 `BAAI/bge-small-en-v1.5`，默认搜索相应为 hybrid，本地模型初次需要获取权重。可配置 OpenAI/LiteLLM embedding，此时待索引文本与查询会发给所选 provider。reranker 默认关闭，开启后默认本地 fastembed cross encoder。Logfire telemetry 默认关闭。这些是源码默认值，不是实测成本。[配置](https://github.com/basicmachines-co/basic-memory/blob/194afe165b3e7676496aaa53b70e39a78ea5aa4f/src/basic_memory/config_models.py#L212)。

不能把完整接入视为“Markdown 外挂的无正文数据库”：`NoteContent` 保存完整 `markdown_content`、`db_version`、文件 checksum/version 和 pending/writing/synced/failed/external_change_detected 状态；它支持数据库接受写入后再物化文件，构成另一套写入状态机。审查到的该表保存当前正文，不据此断言它保留每个历史全文；`AcceptedProjectNoteChange` 则是路径/版本/checksum 级审计。[NoteContent](https://github.com/basicmachines-co/basic-memory/blob/194afe165b3e7676496aaa53b70e39a78ea5aa4f/src/basic_memory/models/knowledge.py#L182)。

默认依赖还包括 SQLAlchemy、FastAPI/FastMCP、Alembic、asyncpg/psycopg、openai/litellm 等，明显超过一个 SQLite FTS 扩展。[依赖与许可](https://github.com/basicmachines-co/basic-memory/blob/194afe165b3e7676496aaa53b70e39a78ea5aa4f/pyproject.toml)。AGPL 项目如需嵌入/修改分发，应先明确许可义务；这里不把它当成可直接拷贝到 MIT 仓库的代码。

有价值的实现/测试参考：原子替换检索投影时失败保留旧完整投影，首次失败不留下部分投影；向量写失败、ready commit 失败、删除失败重试、保留更新 generation、只检索当前 ready manifest；provider/model/dimension 与内容 fingerprint 绑定，未变化内容不重复 embedding。[原子刷新测试](https://github.com/basicmachines-co/basic-memory/blob/194afe165b3e7676496aaa53b70e39a78ea5aa4f/tests/services/test_search_refresh_atomicity.py)、[向量失败和世代测试](https://github.com/basicmachines-co/basic-memory/blob/194afe165b3e7676496aaa53b70e39a78ea5aa4f/tests/repository/test_sqlite_vector_search_repository.py)、[embedding 规划测试](https://github.com/basicmachines-co/basic-memory/blob/194afe165b3e7676496aaa53b70e39a78ea5aa4f/tests/indexing/test_embedding_index_planning.py)。

实际收益是少造一套本地 Markdown 搜索/关系导航/增量索引体验；没有发现它原生实现 MindIE 的脱敏边界、PR 多人贡献、发布回执或经验反馈协议。这些不能随框架名一起宣称获得。

## Mem0

核心可本地 Python 库运行，默认 Qdrant 可使用本地 path，另有 SQLite history；不要求远端中心服务。另一个 self-hosted server 产品使用 API+PostgreSQL/pgvector+dashboard，非本地库的强制依赖。当前核心实体关联使用向量 store，不能照搬旧版本“必须 Neo4j 图库”的介绍。[依赖](https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/pyproject.toml)、[核心配置](https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/mem0/configs/base.py)。

默认 provider 为 OpenAI。当前 `infer=True` 路径先 embedding 新消息并取相近记忆，读取最近 10 条会话消息，再调用一次 LLM 做 additive extraction，随后 embedding 所提取记忆并进行关联处理。外发不仅是本次输入，还可能包括相近历史记忆与最近消息。`infer=False` 跳过生成模型，但逐条保存正文并 embedding，仍有向量和 history 成本。可改用本地 provider，不能把 local store 理解为 default offline。[提取路径](https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/mem0/memory/main.py#L882)。

具体失败与保留边界：LLM provider 异常已包装成 `LLMError` 抛出，值得肯定；但模型回复解析异常仍被记录日志后置为空列表，随后保存 messages 并 `return []`，调用方无法区别“没有事实”与“解析失败”。更新/删除先写向量库再写 SQLite history，跨库不是同一个事务，需要处理已产生外部效果后第二步失败；删除仍向 history 存储被删除的旧正文；实体清理错误明确按 non-fatal 吞掉。这与 MindIE current-only 清理及必须步骤显式失败不能直接对齐。[解析失败](https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/mem0/memory/main.py#L974)、[update/delete](https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/mem0/memory/main.py#L2052)、[history 正文](https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/mem0/memory/storage.py#L150)。

默认开启 PostHog telemetry（`MEM0_TELEMETRY` 默认 True）；如要求没有该网络活动须显式关闭。这里没有声称该遥测发送原始正文。[telemetry](https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/mem0/memory/telemetry.py#L14)。

已读测试覆盖 malformed extraction、provider error propagation、infer=False 单次 embedding、删除写入 history、metadata scope/update 约束。[核心测试](https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/tests/test_memory.py)、[scope 测试](https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/tests/memory/test_main.py)。

Git/Markdown 同步、稳定 entry_id/revision、source tombstone、多人分支贡献仍需自己构建 adapter。仅采用 infer=False 时，价值主要是多后端适配；若只需一个本地向量后端，直接使用该后端可能更简单。其托管平台宣传和 benchmark 不可推导 OSS 在我们语料上的质量。

## Hindsight

可用户侧自托管，不需我们维护中心服务；但“嵌入式”不等于无服务：`pg0` 是真实 PostgreSQL 进程，封装启动/重试/停止，all-in-one 层再启动本地 FastAPI/uvicorn。主存储支持 PostgreSQL+pgvector 或 Oracle，部署、schema migration、数据备份和生命周期都成为集成责任。[pg0](https://github.com/vectorize-io/hindsight/blob/f7dd3f4fd7420f7beec60c32c965e5e5cf7be066/hindsight-api-slim/hindsight_api/pg0.py#L20)、[本地服务封装](https://github.com/vectorize-io/hindsight/blob/f7dd3f4fd7420f7beec60c32c965e5e5cf7be066/hindsight-all/hindsight/server.py#L32)。

retain 默认 LLM 抽取事实/实体/时间/关系，recall 结合语义、BM25、图、时间检索及重排，reflect 再做模型综合；默认 local embedding/rerank，LLM 默认 OpenAI，换成本地 LLM 仍需本地推理服务。启用默认观察与自动 consolidation 会增加后台模型调用。`retain` 的 chunks 模式可直接保存切块而不做 LLM fact extraction，但仍要 embedding 和数据库；若要限制为检索，还需明确关闭 auto consolidation、observations、reflect 路径和不必要历史，不能仅设置 chunks 即认为无生成模型。[配置默认值](https://github.com/vectorize-io/hindsight/blob/f7dd3f4fd7420f7beec60c32c965e5e5cf7be066/hindsight-api-slim/hindsight_api/config.py#L1644)、[chunks 路径](https://github.com/vectorize-io/hindsight/blob/f7dd3f4fd7420f7beec60c32c965e5e5cf7be066/hindsight-api-slim/hindsight_api/engine/retain/fact_extraction.py#L3310)。

当前保留源 document 原文、chunk、facts、observations 等多份派生表示，默认 observation/mental model history 开启，每项上限 50 个快照；上限设 0 是无限，不是关闭。Git 正文需继续权威，所有派生记录必须带精确来源/修订且可删/重建。[存储与历史默认值](https://github.com/vectorize-io/hindsight/blob/f7dd3f4fd7420f7beec60c32c965e5e5cf7be066/hindsight-api-slim/hindsight_api/config.py#L1704)。

比单纯 README 更强的候选证据是已读测试：同 document_id replace 会更新原文并淘汰旧 facts；删除级联、bank 隔离与 recall 不命中旧事实；retain LLM 临时错误经历 worker 重试后最终显式失败；重复输入/旧请求/并发有去重语义；chunks embedding 有 batching 测试。但本次没有运行它们，也没有证明我们的异步删除协议已可直接使用。[替换测试](https://github.com/vectorize-io/hindsight/blob/f7dd3f4fd7420f7beec60c32c965e5e5cf7be066/hindsight-system-tests/tests/test_11_replace_document.py)、[删除测试](https://github.com/vectorize-io/hindsight/blob/f7dd3f4fd7420f7beec60c32c965e5e5cf7be066/hindsight-system-tests/tests/test_13_delete_document.py)、[失败重试测试](https://github.com/vectorize-io/hindsight/blob/f7dd3f4fd7420f7beec60c32c965e5e5cf7be066/hindsight-api-slim/tests/test_retain_transient_extraction_failure.py)、[去重测试](https://github.com/vectorize-io/hindsight/blob/f7dd3f4fd7420f7beec60c32c965e5e5cf7be066/hindsight-api-slim/tests/test_delta_retain_duplicates.py)。

只有在用户确需跨时间、实体和多材料综合推理，并愿意承担独立 DB/服务/模型预算时，完整接入才有清晰收益。对当前全文经验分发和检索，它的大部分能力不是必要条件。

## OpenMemory 名称变化

官方 `mem0ai/openmemory` 当前 README 描述的是 Claude Code、Codex、OpenCode 之间的会话 import/export CLI/TUI，自动同步仍在 roadmap。当前 CLI 用 Bun、Zod、OpenTUI，不是上述记忆检索系统；它实际会写目标 harness 会话和数据库，不能用于替换脱敏经验分发。[当前 README](https://github.com/mem0ai/openmemory/blob/2df78cc48e5f688a771fee5b39899325accc2450/README.md)、[包元数据](https://github.com/mem0ai/openmemory/blob/2df78cc48e5f688a771fee5b39899325accc2450/cli/package.json)。

原先随 mem0 发布的 self-hosted MCP server/dashboard 被移到 `openmemory-archive`，明确停止积极维护，官方指向 Mem0 self-hosted server；归档代码保留 Apache-2.0。不能拿旧功能介绍推荐成当前维护中的方案。[归档声明](https://github.com/mem0ai/openmemory/blob/2df78cc48e5f688a771fee5b39899325accc2450/openmemory-archive/README.md)。

源码/测试还有一个与修订语义相关的限制：当前 CLI orchestration 把 `session.turns.length` 作为 sourceRevision，轮数不变的正文更正可能命中 unchanged skip；这能支持增长式会话迁移，却不是知识内容摘要版本协议。测试覆盖增长、force、ledger 去重和单条错误事件，不能据此宣称支持任意内容更正。[orchestrator](https://github.com/mem0ai/openmemory/blob/2df78cc48e5f688a771fee5b39899325accc2450/cli/src/core/orchestrator.ts#L206)、[测试](https://github.com/mem0ai/openmemory/blob/2df78cc48e5f688a771fee5b39899325accc2450/cli/test/core/orchestrator.test.ts)。

## 可审查的接入实验边界

若继续 Basic Memory 实验，最小边界应是：MindIE 先形成已经脱敏的当前 Git 快照；adapter 持有 `entry_id + revision/body_digest + path` 映射；索引只作可重建缓存；工具只暴露搜索和按精确修订读正文，禁止第三方写回源仓库；源删除/修订使旧命中失效，失效 ref 显式报错并允许重新查询 current；模型与 provider/version 纳入缓存键和运行回执。先在合成/公开语料运行删除、修订、断电/索引失败与模型失败实验，再测检索相关性、覆盖率、引用正确性、token/latency/磁盘和增量成本，最后才决定是否替换现有检索实现。

这组候选都没有自动解决我们的来源真实度、经验贡献评审、隐私边界和质量验收。框架能省掉索引或推理基础设施，不能把派生记忆变成经过验证的知识。

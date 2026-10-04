# ReMe、ACE 与 claude-mem：固定源码快照研究

研究日期：2026-10-04。状态：官方资料与固定源码快照的只读调查；不是模型质量、性能、安装兼容性或原生端到端验收。

本文的未安装、未调用和待验证范围属于初始研究时点；后续实现与测量见[实施阶段证据](implementation-review.md)。原始源码判断保留为选型依据，不用后来的实现结果改写当时结论。

## 1. 研究目的与边界

本研究判断现有框架能否减少 MindIE 经验组件的开发和长期维护，而不是比较谁拥有更多记忆功能。目标是：用较少额外处理，让获准共享的任务经历经 GitHub 保存、维护和分发，供其他任务按需检索、阅读和自行判断。失败、误判和不完整经历仍可有价值；检索摘要不负责认证技术结论。

重点检查以下问题：

- 增量处理是否仍读取或传送累计历史；每次调用包含哪些模型角色、重试和额外整理。
- 持久权威是什么，是否可以让 GitHub Markdown 成为公共内容权威，是否引入第二份原始会话档案。
- 能否使用公开 API 嵌入现有客户端，或整体替换一部分现有组件并删除相应代码。
- 授权、敏感信息处理、失败暴露、清理与旧引用语义是否需要额外适配。
- 上游测试覆盖了什么，哪些宣传或论文效果没有针对当前目标得到验证。

使用官方仓库和文档；只读浅克隆到独立临时目录 `/tmp/mindie-memory-review.cKt9kF/`。未安装候选依赖、启动服务、调用模型、运行上游测试或修改用户安装；未读取、复制或导入真实用户会话。下文涉及失败风险的判断来自所列源码路径，未复现的风险明确标出。临时目录仅为本次检查位置，正式证据使用固定 commit 链接。

| 项目 | 官方仓库与读取提交 | 提交时间 | 快照版本信息 | 许可证 |
| --- | --- | --- | --- | --- |
| ReMe | [agentscope-ai/ReMe · 4c54c2b650038eff2a5d0d77aaa61b3e836f1b18](https://github.com/agentscope-ai/ReMe/tree/4c54c2b650038eff2a5d0d77aaa61b3e836f1b18) | 2026-10-03T23:54:58+08:00 | `reme.__version__ = 0.4.1.13` | Apache-2.0 |
| ACE | [ace-agent/ace · 82709de050e1db6e6ef2f07bcb0393560b94992a](https://github.com/ace-agent/ace/tree/82709de050e1db6e6ef2f07bcb0393560b94992a) | 2026-08-24T11:49:59-07:00 | `pyproject.toml` 为 `0.1.0`，`ace.__version__` 为 `1.0.0`；不据此指定可靠 release tag | Apache-2.0 |
| claude-mem | [thedotmack/claude-mem · bfc50259f64a4e0c9e81df849095683608e87ac8](https://github.com/thedotmack/claude-mem/tree/bfc50259f64a4e0c9e81df849095683608e87ac8) | 2026-10-03T22:30:58-07:00 | 根包与 plugin 包版本 `13.29.0` | Apache-2.0 |

源码读取以这些提交为准，不把论文版本、其他同名实现或搜索摘要混作当前实现。许可证核对的是上述仓库文件，不代表所有可选依赖或商用服务采用相同条款。

## 2. 结论与比较

**ReMe 值得做受限的局部集成试验；ACE 适合借鉴维护侧的局部修订方法；claude-mem 适合借鉴观察队列、错误分类和分层读取。三者当前均未证明能直接、低成本地替换完整经验分享路径。**

这一结论不是保护既有代码。外部框架如果能以更少适配和维护满足产品合同，应允许接管采集、队列、存储乃至整个本地核心。需要保留的是一次授权、范围约束、参考性、错误可见、GitHub 公共内容权威和可控成本，而不是现有类、表或模块边界。

| 维度 | ReMe 当前文件记忆 | ACE 官方实现 | claude-mem 当前版本 |
| --- | --- | --- | --- |
| 主要目的 | 个人知识工作区的采集、演化、检索 | 从执行反馈演化 Agent playbook | 跨会话捕获、压缩和注入工作记忆 |
| 持久权威 | Markdown、源 JSONL 等工作区文件 | 运行中的 playbook 及保存的文本快照 | 本地 SQLite；另有可选云同步路径 |
| 模型工作 | auto-memory Agent；修改后 auto-tag；可选/默认配置中的 dream 等 | Generator、Reflector、Curator，另有可选合并模型 | observer 的初始化、观察与 summary，超大字段还可先压缩 |
| 增量是否保证低输入 | 不保证：更新读已有笔记，CC 入口仍读/复制会话 | 不保证：Curator 输入完整 playbook | 不保证：重送保留的观察历史，但已裁剪旧工具载荷并限制会话 |
| Git Markdown 是否天然权威 | 文件天然权威；Git 提交/PR 权威需自接 | 文本可入 Git；无发布/修订合同 | 否；需要条目与数据库记录映射 |
| 跨 Harness 入口 | HTTP/MCP/CLI、进程内 API、专用适配器 | Python 类；业务记录转换需自接 | 多 Harness 适配、MCP/HTTP |
| 直接用于本需求的主要缺口 | 额外源副本、自动演化与模型轮次、公共发布合同 | 多轮训练目标、全 playbook 输入、错误/重试与隐私适配 | 私人记忆状态与自动注入、数据库映射、额外运行依赖与出站配置 |
| 推荐 | 局部复用候选，优先测试文件检索 | 借鉴，暂排除默认客户端运行 | 借鉴，暂不整体替换 |

“暂不整体替换”是当前证据下的建议，不是禁止后续整体替换。最终决策应比较现有修复和维护成本，与集成、迁移和维护成本，并明确被删除的自有能力。

## 3. ReMe

### 3.1 当前文件工作区与论文版本的区别

当前主分支自述为用户拥有文件的个人知识库，流程是 `session/resource → daily → digest`。Markdown frontmatter、正文与 wikilink 表达内容和关系，`metadata/` 的索引、图和目录状态可重建。README 明确链接早期 `0.3.x`、`0.2.x` 和 MemoryScope 分支。

因此，早期 procedural-memory 论文或旧版 API 的结果不能直接证明当前 file-memory 对长进度会话的摘要质量、费用或部署成本。当前版也不只是旧论文实现换了文档。

来源：[README](https://github.com/agentscope-ai/ReMe/blob/4c54c2b650038eff2a5d0d77aaa61b3e836f1b18/README.md)、[Memory as File](https://github.com/agentscope-ai/ReMe/blob/4c54c2b650038eff2a5d0d77aaa61b3e836f1b18/docs/en/memory_as_file.md)、[版本文件](https://github.com/agentscope-ai/ReMe/blob/4c54c2b650038eff2a5d0d77aaa61b3e836f1b18/reme/__init__.py)。

### 3.2 安装、依赖和公开入口

Python 要求为 3.11 或以上。基础包包含 FastAPI、FastMCP、OpenAI SDK、Pydantic、NumPy、watchfiles 等；文档推荐 `reme-ai[core]`。该 extra 又包括固定版本 AgentScope、Claude Agent SDK、Codex 包及 FAISS/Zvec、图相关包、Studio 等。不能只按基础包名称判断完整工作流的安装代价，也不能把所有可选后端误称为运行时必需服务。

默认服务使用本地 HTTP，提供 MCP、JSON/SSE 和可选 Studio。还支持一次性 CLI Job 和进程内 API。`test_embedded_consumer_compat.py` 检查了注入模型、`start()`、`run_job()`、`close()` 和最小配置兼容性。因此，集成 ReMe 不必然要求中心服务或另一常驻进程；实际取决于配置与使用入口。

适合嵌入的入口包括 `ReMe.run_job`、HTTP Client、MCP 的 `search/read/traverse/list`；通用写入入口为 `auto_memory(messages, session_id, ...)`。已有 Claude Code、Hermes 等适配器，Codex 等可使用 MCP/Skill；跨 Harness 的公开消息投影与授权仍需要逐端确认。

来源：[依赖与许可证声明](https://github.com/agentscope-ai/ReMe/blob/4c54c2b650038eff2a5d0d77aaa61b3e836f1b18/pyproject.toml)、[快速开始](https://github.com/agentscope-ai/ReMe/blob/4c54c2b650038eff2a5d0d77aaa61b3e836f1b18/docs/en/quick_start.md)、[集成说明](https://github.com/agentscope-ai/ReMe/blob/4c54c2b650038eff2a5d0d77aaa61b3e836f1b18/docs/en/integrations.md)、[服务说明](https://github.com/agentscope-ai/ReMe/blob/4c54c2b650038eff2a5d0d77aaa61b3e836f1b18/docs/en/services.md)、[嵌入兼容测试](https://github.com/agentscope-ai/ReMe/blob/4c54c2b650038eff2a5d0d77aaa61b3e836f1b18/tests/unit/test_embedded_consumer_compat.py)。

### 3.3 模型角色、增量输入与全文读取

`auto_memory` 不是一个固定返回 title/summary 的单轮函数。它调用能使用文件工具的 Agent：新建使用 `daily_write`，更新使用 `read/edit/frontmatter_update/write`。更新提示要求读取已有整篇笔记，再局部合并；编辑多次失败时允许完整重写。默认 AgentScope wrapper 的 `max_iters` 为 30，模型重试配置为 1。这里 30 是配置上限，不代表每次实际执行 30 轮。

默认 `auto_memory`/`auto_memory_cc` 后接 `auto_tag_step`，只对实际变化的笔记运行。它也是 Agent 调用，可以读取笔记及已有标签，更新 frontmatter。默认配置另外定义 dream、proactive 等 cron 工作；不应把这些预算遗漏，也不能把“支持禁用”误报为默认不运行。

通用 `auto_memory` 接收调用者提供的 messages；它不会替调用者保证只提交增量。保存源 JSONL 时，会先读取已有记录，按 ID 合并，再决定追加或重写。Claude Code 专用 `auto_memory_cc` 则加载原始会话、读取 ReMe 已保存副本，按 UUID 识别增量；模型只接收新记录，但读取与副本成本仍随历史增长。

因此需要分别记：本次新增消息、读取旧源记录、读取旧笔记、Agent 工具轮次、tag 和后续演化调用。“只把新记录交给 auto-memory”不等于整个系统只处理新字节。

来源：[auto_memory 实现](https://github.com/agentscope-ai/ReMe/blob/4c54c2b650038eff2a5d0d77aaa61b3e836f1b18/reme/steps/evolve/auto_memory.py)、[更新提示](https://github.com/agentscope-ai/ReMe/blob/4c54c2b650038eff2a5d0d77aaa61b3e836f1b18/reme/steps/evolve/auto_memory.yaml)、[Claude Code 入口](https://github.com/agentscope-ai/ReMe/blob/4c54c2b650038eff2a5d0d77aaa61b3e836f1b18/reme/steps/evolve/auto_memory_cc.py)、[tag 实现](https://github.com/agentscope-ai/ReMe/blob/4c54c2b650038eff2a5d0d77aaa61b3e836f1b18/reme/steps/evolve/auto_tag.py)、[默认任务与模型配置](https://github.com/agentscope-ai/ReMe/blob/4c54c2b650038eff2a5d0d77aaa61b3e836f1b18/reme/config/default.yaml)。

### 3.4 持久层、检索、清理与 Git 权威

工作区包含源 `session/`、Agent 运行状态 `mem_session/`、`resource/`、`daily/`、`digest/` 和派生 `metadata/`。通用源 JSONL 过滤 tool-result/base64 数据；Claude Code 专用路径复制的是带 UUID 的原始记录，再在模型输入投影时过滤/截取。这两条路径的保存边界不同，不能混称为已经完整脱敏的公共材料。

检索默认使用 BM25 加 wikilink 扩展；embeddings 默认关闭，可启用 local、FAISS 或 Zvec 后端。改变/删除工作区文件会更新派生索引。`reindex` 从已有 chunks 重建 BM25/向量等索引，不等于重新扫描全部源文件。

文件可直接删除，并由 watcher 删除派生记录。本轮未在所查默认路径确认统一的 source JSONL、Agent session、daily/digest 自动保存期限。文件权威便于 Git 分发，但还没有替我们提供 main commit、PR 并发、内容修订、远端撤回和未知写入回执合同。

来源：[文件层与删除语义](https://github.com/agentscope-ai/ReMe/blob/4c54c2b650038eff2a5d0d77aaa61b3e836f1b18/docs/en/memory_as_file.md)、[检索及默认后端](https://github.com/agentscope-ai/ReMe/blob/4c54c2b650038eff2a5d0d77aaa61b3e836f1b18/docs/en/memory_search.md)、[Auto Memory 保存边界](https://github.com/agentscope-ai/ReMe/blob/4c54c2b650038eff2a5d0d77aaa61b3e836f1b18/docs/en/auto_memory.md)。

### 3.5 失败暴露、隐私与测试证据

Job 使用 `success/answer/metadata`。一些本地失败会明确设置失败状态；但是需要注意：

- 通用源 JSONL 读取中的坏行被捕获并跳过，不能直接满足我们的“坏记录不是无数据”要求。
- `auto_tag` 将逐文件失败写入 `metadata.auto_tag`，保留此前 memory 操作的成功状态。这是它的辅助步骤合同；集成方若把 tag 声明为必要能力，就必须读取并映射该状态，不能只看顶层 success。
- CC 入口先复制记录再执行摘要。模型失败后，后续 Stop 的 UUID 去重是否会使同批材料不再被处理，需要专门的故障 fixture 验证；本轮只发现该调用顺序风险，没有运行复现。
- 过滤 tool-result/base64 是来源卫生措施，不是凭据、内部实体或专有业务内容的完整出站检查。不能直接使用原始会话适配器绕过我们的范围与脱敏边界。
- 模型/embedding 的配置决定哪些内容发送给外部提供商。“local-first”不能解释为模型调用离线。

已阅读的测试包括 `test_embedded_consumer_compat.py`、`test_auto_memory_cc.py`、`test_background_steps.py` 和相关图像输入测试。它们展示了嵌入 API、文件变化、预算分批、来源绑定等机制测试，但本轮没有运行；不能据测试文件存在宣称质量、故障恢复或真实 Harness 集成已经通过。

### 3.6 建议及增减维护量

第一候选是**只读 Git 已发布 Markdown 的文件检索层**：使用最小 Jobs 配置和进程内或短生命周期入口，只暴露 search/read，禁用自动记忆、tag、dream/proactive；不让它直接导入用户历史。潜在删除自有分块、BM25、链接扩展实现；新增配置桥、依赖管理、缓存一致性和生命周期适配。

当前 MindIE 已有全文 FTS，若 ReMe 没有改善真实查询，额外接入反而增加维护。不要为了“用了成熟框架”保留两套索引。若后续证据显示它可以连同队列/材料存储一起替换，并删除更多自有代码，也应重新比较，不能先把它永久限制为检索插件。

## 4. ACE 官方实现

### 4.1 来源、依赖与接口

本节只评估论文官方 `ace-agent/ace`，不把其他同名 MCP、SQLite 或 hosted ACE 项目的功能归给它。Python 要求为 3.10 或以上，依赖 OpenAI、Together、SambaNova、sentence-transformers、FAISS、scikit-learn、tiktoken 等。公开 Python 类为 `ACE`、`ACEBatch`、`Generator`、`Reflector`、`Curator`、`BulletpointAnalyzer`。

主要执行入口是 offline/online adaptation 与 eval runner；没有在该快照中看到通用 Harness Hook、Git 发布或 MCP/HTTP 服务入口。本轮检索到的测试相关文件主要为 eval 数据与 runner，未见独立 `tests/` 树；这不否定论文评测，但不是生产组件故障合同测试。

来源：[依赖](https://github.com/ace-agent/ace/blob/82709de050e1db6e6ef2f07bcb0393560b94992a/pyproject.toml)、[Python API](https://github.com/ace-agent/ace/blob/82709de050e1db6e6ef2f07bcb0393560b94992a/ace/__init__.py)、[许可证](https://github.com/ace-agent/ace/blob/82709de050e1db6e6ef2f07bcb0393560b94992a/LICENSE.txt)、[官方介绍](https://github.com/ace-agent/ace/blob/82709de050e1db6e6ef2f07bcb0393560b94992a/README.md)。

### 4.2 模型角色与真实增量行为

普通训练路径先 Generator 生成答案，再 Reflector 分析执行反馈及 bullet 使用，按配置运行 Curator，之后再次生成答案。正确样本也运行反思；错误样本可迭代反思并重做。默认 `max_num_rounds` 为 3、`curator_frequency` 为 1；这是具体 runner 的配置，不是所有 API 调用的固定次数。

如果从现有业务任务提供结果，只复用 Reflector 和 Curator，可以省去重做业务任务，但仍有两个角色调用。Curator prompt 包含整个 `current_playbook`，Generator 也接收 playbook。delta 是局部输出/应用形式，不保证小输入。

当前 `apply_curator_operations` 只启用 ADD；UPDATE、MERGE、CREATE_META、DELETE 在源码中明确是未实现 TODO。另有可选 BulletpointAnalyzer，对全部 bullets 计算 embeddings，查找相似组，再用 LLM 合并；这不能等同为完整且有修订保护的 delta 操作协议。批处理实现也会让多个 Curator proposal 读取同一个 base playbook，再聚合。

来源：[训练与调用循环](https://github.com/ace-agent/ace/blob/82709de050e1db6e6ef2f07bcb0393560b94992a/ace/ace.py)、[批处理](https://github.com/ace-agent/ace/blob/82709de050e1db6e6ef2f07bcb0393560b94992a/ace/ace_batch.py)、[Reflector](https://github.com/ace-agent/ace/blob/82709de050e1db6e6ef2f07bcb0393560b94992a/ace/core/reflector.py)、[Curator](https://github.com/ace-agent/ace/blob/82709de050e1db6e6ef2f07bcb0393560b94992a/ace/core/curator.py)、[实际操作](https://github.com/ace-agent/ace/blob/82709de050e1db6e6ef2f07bcb0393560b94992a/playbook_utils.py)、[额外合并器](https://github.com/ace-agent/ace/blob/82709de050e1db6e6ef2f07bcb0393560b94992a/ace/core/bulletpoint_analyzer.py)。

### 4.3 持久、失败、隐私与清理

主要持久产物是 playbook 文本、intermediate playbook、usage 和完整 LLM prompt/response 日志。文本可以纳入 Git，但本实现不提供 GitHub 权威、发布回执、公开范围、旧版本过期或统一保存期限。

Curator 在 JSON 解析失败时打印/记录错误，然后返回原 playbook 和空 operations。对组件调用者而言，这不等于一个可直接区别“合法无修改”与“处理失败”的强结果合同。`timed_llm_call` 对超时、限流和服务错误默认最多尝试 1000 次；模型日志包含提示和响应，调试输出也可能含正文。直接接入需要替换或严格包住重试、结果和日志边界。

Reflector 接收 `reasoning_trace`、问题和执行反馈等参数。该参数名称不是采集隐藏推理的授权；只能向它提供获准公开/脱敏的任务说明和观察。helpful/harmful 计数及反思训练的目标是提高任务表现，不等同“保留参考经历且不认证”的分享目标。

来源：[模型调用、重试与用量](https://github.com/ace-agent/ace/blob/82709de050e1db6e6ef2f07bcb0393560b94992a/llm.py)、[日志保存](https://github.com/ace-agent/ace/blob/82709de050e1db6e6ef2f07bcb0393560b94992a/logger.py)、[Curator 失败路径](https://github.com/ace-agent/ace/blob/82709de050e1db6e6ef2f07bcb0393560b94992a/ace/core/curator.py)。

### 4.4 建议及增减维护量

建议借鉴“基于新材料提出局部增补/更正、明确来源、确定性应用”的思想，放在 Grok 已获准进行的公共内容维护中。可以直接使用 Git diff/普通 PR，不必引入另一份永久 playbook、helpful/harmful 体系或每任务 Reflector。

若整合官方运行时，需要新增业务记录转换、模型执行、隐私/日志约束、错误映射、预算、清理和发布协议，能直接删除的现有能力有限。因此暂不推荐客户端采用。后续若出现更适合的成熟实现，应作为另一个有明确版本的候选评估，不能把它的能力写回本次官方快照结论。

## 5. claude-mem

### 5.1 当前许可证、跨 Harness 与依赖

当前 `13.29.0` 已使用 Apache-2.0，且支持 Codex 等多 Harness；不能沿用较旧资料中的 AGPL 或仅限 Claude Code 判断。根包与 plugin 包要求 Node ≥20.12.0、Bun ≥1.1.31。运行时使用本地 worker、SQLite，Chroma 默认开启，可配置关闭为 SQLite-only；本地向量服务由 uv/Chroma 路径管理。plugin 包另有多种 tree-sitter 语法依赖。

它有多 Harness 适配、MCP 搜索工具和 HTTP API，但不同宿主的 Hook、watcher、消息归属仍需分别验证。跨 Harness 支持不自动满足我们“只有当前明确激活任务才能采集”的产品约束。

来源：[README](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/README.md)、[根包](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/package.json)、[运行包依赖](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/plugin/package.json)、[许可证](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/LICENSE)。

### 5.2 模型调用、历史重送与上限

核心流程观察工具使用等事件，由 observer 模型生成 observations，在 Stop 等阶段产生 summary，再供未来会话检索或自动注入。它处理的不只是任务末尾的标题/摘要。

Claude provider 使用 SDK 观察会话。OpenAI-compatible/Codex provider 每次 query 传递保留的 conversation history；Codex 还会将共享上下文的队首 observations 合批，默认数量上限 8、字符预算 32000，减少每事件一次完整历史重送的开销。

当前已经实现 `history-pruning.ts`：对较早且已持久化为观察的原始 tool payload 改为短占位标记，保留最近 8 条消息，以及助手观察、初始化等必要内容；默认 observer conversation 字符限制为 400000，并结合模型窗口回收会话。因此，不能说当前仍无界地 O(n²) 重传全部原始工具输出。不过保留的观察与近期输入仍参与后续调用，实际费用需要累计。

大工具输入/输出在进入观察 prompt 前，还可能用独立模型调用压缩；之后才进行 observation。Stop summary 是另一个任务。成本清单至少包括 init、observations、summary、超大字段压缩、重试及启用的备用模型路径。对输入/输出设置上限，并不能替代整任务费用测量。

本次也阅读了 server-beta 的单次事件生成代码；那是另一条服务路径，不能拿其 single-shot 特性解释默认本地 worker。

来源：[Claude provider](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/src/services/worker/ClaudeProvider.ts)、[OpenAI-compatible 流程](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/src/services/worker/OpenAICompatibleProvider.ts)、[Codex batching 与 history 输入](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/src/services/worker/CodexProvider.ts)、[历史裁剪](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/src/services/worker/history-pruning.ts)、[默认预算配置](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/src/shared/SettingsDefaultsManager.ts)、[server-beta 区别](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/src/server/generation/providers/shared/prompt-builder.ts)。

### 5.3 持久层、API、清理与公共内容权威

SQLite 保存 sessions、prompts、observations、summaries；另外存在队列、spool、观察模型会话和派生搜索状态。可选云同步是数据库内容同步机制，不是 GitHub Markdown 贡献协议。

MCP 的 `search → timeline → get_observations` 先返回短索引、再读时间邻域/完整观察，是值得复用的渐进读取方式。HTTP `/api/memory/save` 可接收外部材料；DataRoutes 有按 observation、summary、prompt 和 session 删除的接口。

如果只借其检索，需要将 GitHub 条目映射成 SQLite observations，维护 entry/revision 与记录 ID、更新、删除、来源的映射；如果仍保留自有检索，会有重复索引。若替换整个本地状态，仍需补公共 main/PR 权威和未发补充关系。显式删除 API 与队列清理存在，但本轮未确认统一的 observation/session 自动保存期限。

来源：[SessionStore](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/src/services/sqlite/SessionStore.ts)、[保存 API](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/src/services/worker/http/routes/MemoryRoutes.ts)、[读取删除 API](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/src/services/worker/http/routes/DataRoutes.ts)、[worker API 文档](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/docs/public/architecture/worker-service.mdx)。

### 5.4 失败暴露与隐私出站

该版本已经包含 transient/unrecoverable、quota、ambiguous paid-send 等错误分类，保护待处理批次，维护 observer-health/dependency 状态。有专门的 Codex 失败记账测试，区分真正失败和被既有 breaker 阻止、尚未发出的调用，避免把同一故障反复计费/记账。不能因为其代码量大就忽略这些可复用成果；但本轮未运行测试或确认实际宿主提示。

出站行为需要分开判断：

- 默认设置中的 cloud sync URL/token 为空，即同步关闭，不能声称默认把全部历史上传。
- 交互安装的 provider 选择默认推荐 hosted CMEM observer；headless/明确 provider 配置有所不同。模型执行本来就可能向提供商发送材料，需明确选择。
- `<private>` 标签过滤不等于自动发现敏感文本；自动 secret redaction 当前默认关闭，可主动开启。现有正则规则也不构成我们出站范围的替代证明。
- 匿名遥测默认开启，可退出；实现有属性白名单与错误脱敏。不能将其描述成原始会话上传，但它是额外出站通道，应纳入最小配置。

来源：[错误类型](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/src/services/worker/provider-errors.ts)、[失败记账测试](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/tests/worker/codex-failure-booking.test.ts)、[默认 provider/cloud/redaction 配置](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/src/shared/SettingsDefaultsManager.ts)、[脱敏实现](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/src/utils/redaction.ts)、[脱敏接线测试](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/tests/integration/redaction-wired.test.ts)、[遥测开关](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/src/services/telemetry/consent.ts)、[遥测字段清理](https://github.com/thedotmack/claude-mem/blob/bfc50259f64a4e0c9e81df849095683608e87ac8/src/services/telemetry/scrub.ts)。

### 5.5 建议及增减维护量

借鉴分层检索、事件合批、已消费载荷裁剪与错误分类。若整体接入，需要处理 worker 生命周期、SQLite/可选 Chroma、模型 provider/额外出站配置、自动注入行为，以及 GitHub 条目映射；现有 GitHub 发布与出站安全能力仍不能删除。当前没有证据显示这些适配比保留并修复已有组件更少。

若用户目标转向“跨 Harness 的私人长期工作记忆”，claude-mem 的完整产品适配度可能显著上升；这属于目标变化，不能用它代替当前公共参考经验分享的交付。

## 6. 最小可反证实验

### 6.1 文件检索替换实验

将同一合成公开 Markdown 语料交给当前 FTS 和 ReMe 的最小检索配置。保留中文、代码标识符、条件差异、中段唯一发现、多主题、错误更正与已撤回条目。使用完全相同查询、返回条数和相关条目标注。

测量真实 Recall@5/排序、仅看检索卡的选读准确率、正文证据定位、冷启动、内存、索引磁盘、更新时间与删除传播。固定 main 快照，第二次更新只改变一个条目，检查缓存与结果；故障期间不得将索引未就绪解释为空结果。不调用 auto-memory、tag 或 dream。

如果 ReMe 没有解决现有 FTS 的实际缺口，或收益不足以支付依赖、状态与生命周期适配成本，就停止集成。若确实更好，应明确替换并删除旧索引实现，避免永久双栈。

### 6.2 摘要与框架处理实验

先保留同一小模型的全文一次、首尾、结构化抽样、增量摘要四组。框架整理能力可作为额外参赛者，但必须使用相同获准脱敏材料、同一输出目标和整任务预算。

总成本包括所有输入、缓存输入、输出、可得的推理用量、模型工具轮次、tag/反思/压缩、失败和重试。全文一次与每轮全文重跑分开；增量输入与增量磁盘读取分开。费用未知记未知，不能用请求字节直接算账。

质量测主题覆盖、错误/撤回保留、观察归属、计划与执行区别、局部与完整验证区别，以及实际搜索和选读结果。不强制增加 LLM 裁判；确定性检查与人工盲评即可起步。框架的 benchmark 得分不替代本任务 fixture。

### 6.3 整体替换仍应保持开放

每个候选至少比较两个方案：局部复用，以及允许它接管较大职责后能删除多少自有代码。对同一用户故事和失败合同做隔离试验，而不是要求它必须匹配当前内部表结构。将来源读取、脱敏、模型预算、当前正文、未决写、撤回和独立消费逐项映射；缺失能力注明适配成本。

决策依据是预计维护面与测得的用户总成本。依赖少不天然胜出，功能多也不天然值得整合。临时隔离双跑用于比较可以接受；最终产品不应留下两套互相竞争的内容或生命周期权威。

## 7. 尚未证明的事项

- 三个候选在本机的可安装性、原生 Hooks/服务可用性、指定模型是否实际可调用。
- 对 MindIE 长任务材料的摘要质量、真实 token、费用、延迟和总存储增长。
- 上游测试在固定快照及用户目标平台上的通过情况。
- ReMe 复制记录后模型失败的恢复结果、各候选统一保存期限与长期容量表现。
- 任何候选完成 GitHub 贡献、Grok 指定 head 审阅和独立客户端复用的真实闭环。

本研究支持选型与最小试接顺序，不支持生产替换或质量已达标的声明。

## 变更摘要 (Summary)

- 

## 设计原则 Review (Pre-PR Checklist)

> 提交或更新 PR 前请对照 [`docs/design-principles.md#三开发-pr-提交前自查清单pre-pr-review`](docs/design-principles.md#三开发-pr-提交前自查清单pre-pr-review) 完成自查：

- [ ] **1–8. 产品边界与机制复用**：总成本优先、封闭问题工具化、单一职责、按需介入、优先复用成熟组件并直接删除被替代的旧状态机。
- [ ] **9. 错误可见性与反静默回退（Principle 9 & 14）**：无 `except Exception:` 静默返回 `{}` / `"active"` / `exit 0` 假成功，无 `except OSError:` 误吞 `TimeoutError`，无本地记账超时反杀已成功的远端主结果。
- [ ] **10–11. 超时算术与反过度防御四大铁律（Principle 15）**：满足 `outer_timeout >= sum(inner_budgets) + cleanup_grace`；SQLite WAL + `3s~5s` 超时且零热路径 `.owner`/Schema 反射；仅不可逆外部写用 `unknown` 且零本地永久自锁死；零跨仓复制 `*_fallback.py`/`*_bootstrap.py`；零内嵌巨型 Python 字符串。
- [ ] **12–13. 分级测试、宿主机零污染与 Agent-Native 规范（Principle 16 & 17）**：无防御性凑数/文本 grep 测试，符合 Tier 0 (`<5s`) ~ Tier 3 耗时预算；测试全流程隔离 `MINDIE_DIAGNOSTICS_ROOT` / `$HOME`（严禁污染宿主机 `~/.local`、`~/.config` 或系统后台服务）；核心模块 `< 800` 行且前 30 行具备 `[Role]`/`[Invariants]`/`[Timeouts & Locks]`/`[Side-Effect Policy]` 契约头。
- [ ] **14. 编码性能、内存/显存有界性与本地/远端规格分流（Principle 18）**：
  - **内存有界性**：主循环常驻内存严格保持 $O(\text{当前活跃状态})$ 而非无界累加全量历史，大文件（`> 50 MB`）采用流式处理；控制/分析组件单进程常规峰值 `<= 512 MiB`，严禁出现 `> 1 GiB` 算法膨胀缺陷。
  - **性能与并发纪律**：热循环内无 `deepcopy` / 起子进程 / 逐行 Commit；并行 Worker 数同时受可用 CPU 核数与可用安全内存双重约束（$\min(\text{CPU}, \lfloor\text{可用内存}/\text{单 Worker 内存}\rfloor)$）。
  - **显存（HBM/VRAM）安全**：控制与元数据路径保持“零权重、零设备上下文”；上卡操作启动前完成静态显存预算核验（`vram_free_mb >= Expected VRAM`）。
  - **跨平台规格分流（Windows / macOS / Linux）**：无 `sys.platform == "darwin"` 等操作系统硬编码特判；重计算/重内存/需显存任务声明 `WorkloadExpectation`，按本机与远端（`fleet_probe.py`）的真实可用硬件规格自动分流（本机规格充裕则本地跑，不足则分流远端）。
- [ ] **15. 自动更新就绪必检（Release Checklist `R1–R6`）与文件格式规范（PR Format Hygiene）**：涉及组件、知识库语料、插件或 `channels/0.1.json` 变更时，已运行并通过 `python3 .github/scripts/check_auto_update_readiness.py --require-siblings --verify-local-hosts`（发版场景加 `--verify-github-releases`，完成 `R1` 发版模式、`R2` 语料 `revision` 单调递增、`R3` Tag/Commit/Release 资产、`R4` 五端灵活组件下界兼容、`R5` 本机宿主 CLI 兼容区间、`R6` 组织版本表与 `LF` 换行全量核验）；全仓文本文件严格使用 Unix `LF`（`\n`）换行格式并通过 `python3 .github/scripts/check_lf_eol.py` 校验。
- **自查结论与证据**：

## 验证结果 (Verification)

- 

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
- [ ] **15. 自动更新就绪、Windows 零控制台弹窗必检（Release Checklist `R1–R6` & Zero Console Popup）与文件格式规范（PR Format Hygiene）**：已核验 Windows Node.js 子进程带 `windowsHide: true`、Python 子进程带 `CREATE_NO_WINDOW`；按实际范围通过 `check_auto_update_readiness.py`（独立组件/语料/插件用 `--release-repo <仓库>`，产品组合用 `--release-scope product`，按需加 `--require-siblings --verify-local-hosts`，发版加 `--verify-github-releases`）。R6 独立发布只核对所选仓自身源码版本、README 与 LF，不要求主仓升版、通道更新或其他仓 README 同步；全量版本同步仅用于产品组合发布。文本文件通过 `python3 .github/scripts/check_lf_eol.py`，保持 Unix `LF`（`\n`）。
> 计划任务等直接执行入口还须验证 `pythonw.exe` 的真实 PE GUI 子系统（`Subsystem == 2`），覆盖新注册与旧注册恢复；文件名、文件存在和任务 `Hidden` 不能代替此检查。Windows 桌面验收须核对就绪、虚拟环境身份、参数与窗口/进程树，并正常停止和删除临时任务。

- **自查结论与证据**：

## 验证结果 (Verification)

- 

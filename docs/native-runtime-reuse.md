# 原生能力与系统机制复用（Native Runtime & Process Reuse）

[English](native-runtime-reuse.en.md) · [返回文档中心](README.md)

本文说明 MindIE Agent 如何践行“[工程设计原则](design-principles.md)第 8 条（优先复用成熟机制与已有有效成果）”：把通用的包下载、虚拟环境锁定和进程树回收交给宿主 CLI、`uv` 和操作系统原语，自研代码只聚焦昇腾与经验闭环特有的核心语义。

---

## 1. 核心架构取舍：少造管理轮子，只补真实缺口

在早期迭代中，如果每个宿主插件都自己写一套多阶段更新器、手搓 `venv`/`pip` 安装脚本、或者用轮询去猜子进程归属，不仅维护成本高，而且极易在跨平台（macOS / Windows / WSL）时埋下隐蔽 Bug。

因此，我们对运行时管理职责做了彻底收敛：

| 管理职责 | 复用的成熟机制 | MindIE Agent 保留的最小职责 | 已彻底移除的冗余自研逻辑 |
| --- | --- | --- | --- |
| **插件下载、安装与登记** | Codex / Claude Code 原生插件管理器 | 共享的 SemVer 宿主版本兼容筛选函数（`harness-compatibility.json`）+ 发布前门禁校验 | 移除了早期自研的多阶段 `auto_update.py` / `updater.py`、专用定时更新服务与多代版本后继链 |
| **Python 依赖与隔离运行环境** | `uv sync --locked --no-editable` + 随仓提交的 `uv.lock` | 产品组件组合契约（`product-contract.json`）、平台/解释器身份校验与数据格式检查 | 替代了手写的 `venv`/`pip` 编排脚本与松散的顶层 `requirements.txt` |
| **会话生命周期 Hook** | 宿主原生 Hook + 本地 SQLite 持久准入 | 任务身份核验、项目授权范围检查、增量游标推进与幂等去重 | Hook 绝不阻塞等待大模型调用，也不额外引入第二套文件队列（Spool） |
| **后台服务与操作进程树管理** | Windows Job Object；WSL `systemd` 临时用户服务；macOS 轻量 `owner-pipe` 守护 | 服务配置指纹、单消费者锁、操作结果落盘与临时目录清理顺序 | 移除了各适配器里重复的父进程 PID（PPID）猜测逻辑 |
| **安装绑定与无感切换** | 单一规范安装绑定（Canonical Binding）+ 共享/排他操作锁 | 在锁外构建新版本环境；趁服务空闲时原子切换绑定；运行环境脱离宿主易失缓存目录 | 移除了多代并存路由、复杂会话租约与全局 `current` 软链接 |
| **业务状态与故障恢复** | 权威 Markdown 分块 + SQLite 回执 + `diagnostics` | 隐私脱敏、Token 用量落盘、已完成/失败/`unknown` 对账 | 绝不把结果未知的付费模型调用或远端 Git 写入当成普通任务自动重试 |

---

## 2. 插件更新：复用原生插件市场 + 补齐兼容性筛选

详细更新流程见[版本兼容与无感更新](release-compatibility-and-update.md)。由于宿主自带的 Git 插件市场默认只拉取分支最新提交，无法直接根据“当前安装的宿主 CLI 版本”筛选兼容的插件版本，我们只在这一个缺口处补了共享的纯函数筛选器，其余下载与安装完全交给宿主原生管理器：

### 2.1 OpenAI Codex CLI 适配要点
- **宿主机制特点**：Codex 启动时会刷新配置的 Git 插件市场，但它的缓存管理器（`store.rs`）在更新时会清理旧版本缓存目录，甚至原地替换同版本目录。
- **稳定运行环境隔离**：如果后台知识服务或正在运行的会话 Hook 直接跑在宿主易失缓存目录里，一旦宿主刷新缓存就会报 `file-not-found`。因此，MindIE Agent 将稳定入口（`SessionStart`、`MCP`、`Stop`）和 `uv` 非 editable 锁定环境部署在应用数据目录下，与宿主易失缓存解耦。

### 2.2 Claude Code 适配要点
- **宿主机制特点**：Claude Code 支持原生插件市场安装，并在 `SessionStart` 和 `MCP` 中提供一致的 `CLAUDE_PLUGIN_DATA` 目录，已运行的会话在更新后保持原路径直到下次启动。
- **统一稳定绑定**：我们在 Claude Code 上同样采用应用数据目录下的稳定入口与独立 `uv` 环境，确保后台服务生命周期不受宿主缓存清理策略影响；同时每次正式发布递增插件清单版本号，保证原生缓存更新行为确定可控。

---

## 3. 毫秒级 Stop Hook 与后台异步消费

经验采集在架构上严格拆分为“**前台毫秒级持久入队**”与“**后台独立 Worker 异步处理**”两步：

```text
宿主触发 Stop Hook
  -> 1. 核对任务身份与项目授权范围
  -> 2. 向本地 SQLite 写入持久化准入记录
  -> 3. 立即向宿主返回中性完成响应（全程毫秒级，不调大模型）
  -> 4. 后台独立 Worker 异步读取队列
  -> 5. 在操作系统受管进程树中调用原生小模型生成分块导航
  -> 6. 保存导航结果与 Token 用量 -> 回收进程树 -> 清理临时目录
```

- **为什么不用宿主的 `async: true` 后台 Hook？**
  - 以 Claude Code 为例，官方文档明确说明非交互模式（`claude -p`）退出时会直接取消尚未跑完的异步 Hook。因此，MindIE Agent 采用极速同步 SQLite 入队 + 独立后台服务消费的模式，既不卡住前台终端，又保证宿主退出后经验整理不会半途夭折。
- **Windows 冷启动提速**：
  - 在 Windows 上，唤醒后台 Task Scheduler 任务直接通过 `pywin32` 原生 COM/ACL 接口完成（仅需约 5~14 毫秒），彻底告别了早期启动多个 PowerShell 子进程带来的冷启动耗时。

---

## 4. 跨平台进程树回收：用操作系统原语兜底

不同操作系统的进程组管理机制差异巨大。为了保证即使后台主控进程意外崩溃或收到 `SIGKILL`，它拉起的子进程和孙进程也能被 100% 干净回收，我们在三个平台分别采用了经过实测验证的系统原语：

| 运行平台 | 采用的操作系统原语 | 可靠性保障 |
| --- | --- | --- |
| **原生 Windows** | 挂起创建（Suspended Spawn）+ 命名 Windows Job Object（启用 `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`） | 一旦主控 Worker 退出或被强杀，操作系统内核自动关闭 Job 句柄并终止其下全部子孙进程 |
| **Windows WSL / Linux** | `systemd` 临时用户服务（`Type=exec`, `ExitType=main`, `KillMode=control-group`, `Restart=no`） | 主进程退出后，`systemd` 自动清理整个 cgroup 控制组，即使子进程自己新建了进程组（PGID）也无法逃逸 |
| **macOS** | 轻量共享 `owner-pipe` 守护辅助器（主控持有唯一写端，包装器在同进程组监听管道后 `exec` 目标程序） | 主控进程一旦死亡，管道立即触发 `EOF`，守护进程瞬间回收整个同进程组操作树，且无需向 `launchd` 频繁注册一次性任务 |

---

## 5. 参考资料与上游依据

- **[C1 / C2] OpenAI Codex 插件管理器与缓存存储实现**：[`manager.rs`](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/core-plugins/src/manager.rs#L2733) 与 [`store.rs`](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/core-plugins/src/store.rs#L699)
- **[A1 / A2] Claude Code 插件市场与加载机制文档**：[Plugin Marketplace](https://code.claude.com/docs/en/plugins/host-marketplace) · [Plugin Loading & Caching](https://code.claude.com/docs/en/plugins/loading)
- **[U1 / U2] 锁定环境与原子更新参考**：[`uv` Project Sync](https://docs.astral.sh/uv/concepts/projects/sync/) · [Velopack Update Lifecycle](https://docs.velopack.io/integrating/overview)
- **[H1] Claude Code 后台 Hook 生命周期说明**：[Run Hooks in the Background](https://code.claude.com/docs/en/hooks#run-hooks-in-the-background)
- **[P1 / P2 / P3] 操作系统进程树管理规范**：[`systemd.kill(5)`](https://github.com/systemd/systemd/blob/v257/man/systemd.kill.xml) · [Apple `launchd.plist(5)`](https://github.com/apple-oss-distributions/launchd/blob/d448a1c8f70a61202f8705f94337f686b87c30c4/man/launchd.plist.5) · [Microsoft Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)

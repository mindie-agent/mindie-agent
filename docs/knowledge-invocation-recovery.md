# Windows 知识调用与恢复

[English](knowledge-invocation-recovery.en.md) · [返回文档中心](README.md)

本手册面向在 Windows 上使用 `mindie-agent-codex` 的开发者与维护者，说明如何按配置绑定和原生会话身份调用知识能力，并在输入编码、授权、Windows 服务启动器或传输失败时按阶段恢复。它保留 [PR #357](https://github.com/mindie-agent/mindie-agent/pull/357) 由 `YzTongNiar` 提交的 Windows 现场报告，但**不是**对该现场的桌面复现验收：文中“已检查”的结论来自指定版本的源码与接口审查，“现场报告”仅代表贡献者观察，“未复现”项必须如实保留为未知。

<a id="scope"></a>
## 适用范围与证据边界

### 贡献与版本

| 项目 | 已记录事实 |
| --- | --- |
| 现场报告 | `YzTongNiar` / [PR #357](https://github.com/mindie-agent/mindie-agent/pull/357)，原始提交 `cbefa9a72ecff494a60d47ed8731843cbeb29637` |
| Codex 插件 | 最新正式发布 `mindie-agent-codex 0.1.32`，现场报告审查提交 `2a8ee6fadda3c750b43ca329fce8794e4254eb3f` |
| Codex `main` 配套修复 | `mindie-agent-codex` `main` 上的 [mindie-agent-codex#118](https://github.com/mindie-agent/mindie-agent-codex/pull/118)，合并提交 `d413a20e2d09df607e70170bd18618045cc65fd9`（`d413a20`）；**未发布**，不在正式 `0.1.32` 中 |
| 声明的 Knowledge 基线 | `mindie-knowledge 0.13.17`，`315fc4b` |
| 本次检查的 Knowledge `main` | `mindie-knowledge 0.13.19`，`c164e16` |
| 贡献者实际安装的 Knowledge 版本 | **未知**；独立升级过的安装可以与声明基线不同，不能把 `0.13.19` 的检查结论倒推为现场证据 |
| 原生 Codex、Windows、PowerShell、Python 发行版、`uv` 版本 | 现场报告未完整记录；需要操作者补充，缺失即标为未知 |

### 已检查、现场报告与未复现

- **已检查（源码/接口）**：`knowledge_cli.py` 的 stdin 解析与错误归类、适配器对 `CODEX_THREAD_ID` 的准入、`knowledge_query` / `knowledge_distill` 的授权边界、共享 PE 子系统校验，以及引擎状态字段中 `worker` / `summary` / `outbox` 的线程语义。
- **现场报告（贡献者观察）**：stdin 包装器在派发前返回 `invalid_arguments`；生成的 `Scripts\pythonw.exe` 被 Windows 计划任务启动器校验拒绝；贡献者曾本地修改 PE 头字段尝试修复。
- **未复现或未建立**：贡献者当时实际发送的字节序列、精确的现场触发原因、CUI 启动器的上游来源，以及 Windows 桌面端到端验收。解析器实验只能证明错误被合并，不能证明现场一定是编码问题。

因此，正确的结论是：

> `invalid_arguments` 的不可区分性是已确认的适配器缺陷；编码、不支持的 argv 形态、空输入或畸形 JSON 都是候选原因。没有原始调用与脱敏字节证据时，精确的现场触发仍未证实。

本手册不提供修改已签名二进制、绕过 Windows 安全策略、伪造会话身份或直接导入内部模块的“修复”。这些做法不是受支持的恢复路径。

<a id="runtime-binding"></a>
## 配置绑定与原生会话身份

### 配置解析顺序

1. 若环境变量 `MINDIE_AGENT_CONFIG` 已设置且非空，使用它指向的配置文件。
2. 否则使用默认路径 `%USERPROFILE%\.config\mindie-agent\codex.json`。
3. 以 UTF-8 读取一次 JSON，并确认 `python` 与 `runtime_scripts` 都是非空字符串。

`MINDIE_AGENT_CONFIG` 是显式覆盖，不是额外候选；不要同时读取默认文件后再“挑一个能用的”。配置读取失败应显式报错，不能静默回退到系统 Python 或另一个安装。

### 规范二元组 `(python, runtime_scripts)`

`python` 与 `runtime_scripts` 必须来自**同一个**配置对象、同一次安装绑定，作为原子二元组一起消费：

```powershell
$configPath = if ($env:MINDIE_AGENT_CONFIG) {
    $env:MINDIE_AGENT_CONFIG
} else {
    Join-Path $env:USERPROFILE '.config\mindie-agent\codex.json'
}

$config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 `
    -ErrorAction Stop | ConvertFrom-Json

$runtimePython = [string]$config.python
$runtimeScripts = [string]$config.runtime_scripts
$cli = Join-Path $runtimeScripts 'knowledge_cli.py'

if (-not (Test-Path -LiteralPath $runtimePython -PathType Leaf)) {
    throw "Configured runtime python is missing: $runtimePython"
}
if (-not (Test-Path -LiteralPath $cli -PathType Leaf)) {
    throw "Configured runtime scripts do not contain knowledge_cli.py: $runtimeScripts"
}
```

禁止：

- 用 `Get-Command python`、IDE 解释器、`PATH` 上的虚拟环境或系统 Python 替代 `config.python`；
- 把 A 安装的 `python` 与 B 安装的 `runtime_scripts` 拼接；
- 通过解析符号链接、重定向器或 `realpath` 把所选虚拟环境“修正”成另一个环境；
- 把 `knowledge_cli.py` 复制到另一个环境后运行。

Windows 虚拟环境中的 `python.exe` 可能是指向基础解释器的重定向器，但 `sys.prefix` 仍应保持为所选虚拟环境。诊断时首先确认身份，而不是解析路径：

```powershell
& $runtimePython -I -c "import sys, importlib.metadata as m; print(sys.prefix); print(m.version('mindie-knowledge'))"
```

`-I` 使解释器进入隔离模式（同时启用 `-E` 与 `-s`），忽略 `PYTHON*` 环境变量与用户 site-packages。它保证的是解释器隔离，**不**提供原生会话身份，也不绕过知识准入。

### 原生会话身份

`CODEX_THREAD_ID` 必须由当前原生 Codex 工具环境提供。调用前只检查它是否存在，不要打印、记录或回显其值：

```powershell
if (-not $env:CODEX_THREAD_ID) {
    throw 'Run from the current native Codex tool environment; do not invent a session ID.'
}
```

严禁：

- 手工设置或伪造 `CODEX_THREAD_ID`；
- 复制另一个会话的线程 ID、令牌或内部校验字段；
- 用 `-I`、环境变量或配置文件“构造”当前会话授权；
- 在公开日志、Issue 或文档中粘贴线程 ID、令牌、Cookie 或完整对话。

| 需要的事实 | 可接受来源 | 禁止替代 |
| --- | --- | --- |
| 配置文件 | `MINDIE_AGENT_CONFIG` 或默认 `codex.json` | 猜测其他用户目录、读取无关旧配置 |
| 解释器 | 同一配置对象的 `python` | `PATH` / 系统 / IDE Python |
| 适配器脚本 | 同一配置对象的 `runtime_scripts` 下 `knowledge_cli.py` | 其他安装的脚本、包内私有模块 |
| 会话身份 | 当前原生工具环境的 `CODEX_THREAD_ID` | 伪造、跨会话复制、内部字段拼装 |
| 虚拟环境身份 | 所述解释器的 `sys.prefix` 与实际包版本 | 解析重定向器后换成基础环境 |

<a id="powershell-input"></a>
## PowerShell 输入契约

### `mindie-agent-codex 0.1.32` 的实际 CLI 契约

已检查的 `0.1.32` 适配器（`<runtime_scripts>/knowledge_cli.py`）行为如下：

1. 要求恰好一个位置参数作为操作名；
2. 从二进制 stdin 读取最多 1 MiB 加 1 字节；
3. 严格按 `utf-8-sig` 解码（UTF-8，可选 BOM）；
4. 解析 JSON；
5. 把多种输入失败统一折叠为 `invalid_arguments`，不区分阶段与原因。

`describe` 不消费输入；正式 `0.1.32` 没有 `--input-file`（该能力已合入 `main` 但未发布，见下文），CLI 输入失败也没有结构化的 `stage` / `reason` 区分。因此 stdin 是 `0.1.32` 的唯一输入通道，且必须由调用方保证 UTF-8 字节。

### PowerShell 5.1 的两个不同陷阱

| 现象 | 根因 | 结果 |
| --- | --- | --- |
| 管道中的中文变成 `?` | Windows PowerShell 5.1 的 `$OutputEncoding` 默认把文本以 ASCII 传给原生程序 | 字符在 Python 看到之前已被替换，事后无法恢复 |
| 重定向文件无法解析 | `Out-File`、`>`、`>>` 默认写 UTF-16LE | CLI 的 `utf-8-sig` 解码失败，返回 `invalid_arguments` |

需要同时纠正两个常见误判：

- “PowerShell 总是用 UTF-16 管道”不成立：管道与文件重定向是两条不同的编码路径。
- “加 `PYTHONUTF8=1` 就好了”不成立：Python 无法恢复上游已替换的字符；而且 `-I` 会忽略 `PYTHON*` 配置。

### 已挂载控制台的 UTF-8 管道调用（Windows PowerShell 5.1）

以下示例仅适用于**已挂载控制台的 Windows PowerShell 5.1**（`powershell.exe`）。它读取并恢复 `[Console]::OutputEncoding`；在无控制台句柄的 headless / consoleless 宿主中（适配器 `native_entry.py` 已识别该边界），读取或设置该属性可能在派发前抛出“句柄无效”（The handle is invalid），`finally` 中的恢复也可能再次抛出并掩盖第一个失败。此类环境请使用下一节的无控制台调用。

该示例由已检查的公共接口推导，**不是本次评审在 Windows 桌面上的实机验收结果**。它不会绕过 `/mindie-agent` 激活，也不证明服务或采集已就绪。

```powershell
$configPath = if ($env:MINDIE_AGENT_CONFIG) {
    $env:MINDIE_AGENT_CONFIG
} else {
    Join-Path $env:USERPROFILE '.config\mindie-agent\codex.json'
}

$config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 `
    -ErrorAction Stop | ConvertFrom-Json

$runtimePython = [string]$config.python
$cli = Join-Path ([string]$config.runtime_scripts) 'knowledge_cli.py'

if (-not $env:CODEX_THREAD_ID) {
    throw 'Run from the current native Codex tool environment; do not invent a session ID.'
}

$payload = @{
    query = '当前问题的实际检索内容'
    mode = 'reuse'
    limit = 5
    token_budget = 4000
} | ConvertTo-Json -Depth 20 -Compress

$savedOutputEncoding = $OutputEncoding
$savedConsoleEncoding = [Console]::OutputEncoding
$callExit = 1
try {
    $OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    [Console]::OutputEncoding = $OutputEncoding

    $payload | & $runtimePython -I $cli knowledge_query
    $callExit = $LASTEXITCODE
} finally {
    $OutputEncoding = $savedOutputEncoding
    [Console]::OutputEncoding = $savedConsoleEncoding
}

if ($callExit -ne 0) {
    throw "knowledge_query failed with exit code $callExit; inspect its JSON error above."
}
```

验收时应使用 **Windows PowerShell 5.1 的 `powershell.exe`**，不能只测 `pwsh`，并且要核对 CLI 实际收到的字符，而不只是退出码为零。

### 无控制台（headless）的 Windows PowerShell 5.1 调用

以下示例针对 `mindie-agent-codex 0.1.32` 的实际 CLI 契约，同样由已检查的公共接口推导，**不是本次评审在 Windows 桌面上的实机验收结果**。它不读取也不设置 `[Console]::OutputEncoding`，因此不依赖控制台句柄；stdout/stderr 在进程启动后立即异步读取，避免管道缓冲区写满造成互锁；stdin 直接写入 UTF-8 字节后关闭。输出由 `ProcessStartInfo` 的 `StandardOutputEncoding` / `StandardErrorEncoding` 按 UTF-8 解码，退出码来自实际子进程，而不是 PowerShell 管道状态。

```powershell
$configPath = if ($env:MINDIE_AGENT_CONFIG) {
    $env:MINDIE_AGENT_CONFIG
} else {
    Join-Path $env:USERPROFILE '.config\mindie-agent\codex.json'
}

$config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 `
    -ErrorAction Stop | ConvertFrom-Json

$runtimePython = [string]$config.python
$runtimeScripts = [string]$config.runtime_scripts
$cli = Join-Path $runtimeScripts 'knowledge_cli.py'

if (-not (Test-Path -LiteralPath $runtimePython -PathType Leaf)) {
    throw "Configured runtime python is missing: $runtimePython"
}
if (-not (Test-Path -LiteralPath $cli -PathType Leaf)) {
    throw "Configured runtime scripts do not contain knowledge_cli.py: $runtimeScripts"
}
if (-not $env:CODEX_THREAD_ID) {
    throw 'Run from the current native Codex tool environment; do not invent a session ID.'
}

$payload = @{
    query = '当前问题的实际检索内容'
    mode = 'reuse'
    limit = 5
    token_budget = 4000
} | ConvertTo-Json -Depth 20 -Compress

function ConvertTo-NativeArgument([string]$value) {
    if ($value.Length -eq 0) { return '""' }
    if ($value -notmatch '[\s"]') { return $value }
    return '"' + (($value -replace '(\\*)"', '$1$1\"') -replace '(\\+)$', '$1$1') + '"'
}

$startInfo = [System.Diagnostics.ProcessStartInfo]::new()
$startInfo.FileName = $runtimePython
$startInfo.Arguments = @(
    '-I'
    (ConvertTo-NativeArgument $cli)
    'knowledge_query'
) -join ' '
$startInfo.UseShellExecute = $false
$startInfo.CreateNoWindow = $true
$startInfo.RedirectStandardInput = $true
$startInfo.RedirectStandardOutput = $true
$startInfo.RedirectStandardError = $true
$startInfo.StandardOutputEncoding = [System.Text.UTF8Encoding]::new($false)
$startInfo.StandardErrorEncoding = [System.Text.UTF8Encoding]::new($false)

$process = [System.Diagnostics.Process]::new()
try {
    $process.StartInfo = $startInfo
    if (-not $process.Start()) {
        throw 'Failed to start the configured knowledge interpreter.'
    }

    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()

    $payloadBytes = [System.Text.UTF8Encoding]::new($false).GetBytes($payload)
    $process.StandardInput.BaseStream.Write($payloadBytes, 0, $payloadBytes.Length)
    $process.StandardInput.BaseStream.Flush()
    $process.StandardInput.Close()

    $process.WaitForExit()
    $callExit = $process.ExitCode
    $stdout = $stdoutTask.Result
    $stderr = $stderrTask.Result
} finally {
    $process.Dispose()
}

if ($stderr) {
    Write-Error -Message $stderr -ErrorAction Continue
}
Write-Output $stdout

if ($callExit -ne 0) {
    throw "knowledge_query failed with exit code $callExit; inspect its JSON error above."
}
```

### 为什么删除直接导入 `knowledge_cli.invoke(...)` 的回退

`from mindie_knowledge import knowledge_cli` 是错误的模块归属。知识调用的适配器属于 Codex 插件：源码位于 `mindie-agent-codex/plugins/mindie-agent/scripts/knowledge_cli.py`，打包后在 `mindie_codex/scripts` 下；它不在 `mindie_knowledge.knowledge_cli` 中。

即使找到正确的适配器模块，直接调用 `invoke()` 也不是受支持的恢复协议：

- 它只绕过 CLI 的位置参数与 stdin 解析，**不绕过**原生 `CODEX_THREAD_ID` 准入、路由、域租约或贡献授权；
- 它返回 Python 对象，`print(result)` 输出的是 Python 表示，不是 CLI 的 JSON/退出状态契约；
- 异常类型与传播方式不同，调用方容易把“解析成功”误当成“操作成功”；
- 它不是稳定的公共 API，不能作为文档化替代入口。

因此本手册不再推荐任何直接导入回退。需要恢复时，应修复输入字节或按失败阶段处理，而不是换一个入口。

### 发布后的 `--input-file` 与结构化错误（已合入 `main`，`0.1.32` 未发布）

显式文件输入与结构化失败字段已在 [mindie-agent-codex#118](https://github.com/mindie-agent/mindie-agent-codex/pull/118)（`d413a20`）中实现并合入 `mindie-agent-codex` `main`，并在托管 `windows-latest` CI 的 [`adapter (windows-latest)`](https://github.com/mindie-agent/mindie-agent-codex/actions/runs/43748768061/job/132920529110) 作业中验证。但它们**尚未发布，也不在正式 `mindie-agent-codex 0.1.32` 中**，不得作为 `0.1.32` 的现场恢复步骤：`0.1.32` 现场安装仍必须使用上文已挂载控制台的 UTF-8 stdin 管道或无控制台的 `ProcessStartInfo` 路径，直到发布正式版本 `> 0.1.32`：

```text
knowledge_cli.py describe
knowledge_cli.py <operation>
knowledge_cli.py <operation> --input-file <path>
```

设计约束：

- UTF-8，可选 UTF-8 BOM，沿用 1 MiB 字节上限；
- 恰好一个输入源，选中的文件是权威来源；
- `--input-file` 要求选中路径是常规文件（`Path.is_file()`）；目录、FIFO/管道与设备节点都必须显式失败，不能当作空输入或退回 stdin；
- 文件不可读时显式返回 `input_unavailable` / `stage=input_read`，不能回退读 stdin，也不能伪装成空输入或 JSON 错误；
- 解析失败仍是带非零退出码的 JSON 响应，不输出未捕获的 `argparse` 用法文本；
- `describe` 不消费输入，并拒绝不兼容的额外参数。

只有在正式发布 `mindie-agent-codex > 0.1.32` 后才能改用：

```powershell
$payload | Set-Content -LiteralPath $inputFile -Encoding UTF8 -ErrorAction Stop
& $runtimePython -I $cli knowledge_query --input-file $inputFile
if ($LASTEXITCODE -ne 0) {
    throw "knowledge_query failed with exit code $LASTEXITCODE; inspect its JSON error above."
}
```

PowerShell 5.1 写出的 UTF-8 BOM 在该契约下可接受。结构化 `stage` / `reason`（如 `cli_input`、`input_encoding`、`input_json`、`schema_unknown_field`）同样已随 [mindie-agent-codex#118](https://github.com/mindie-agent/mindie-agent-codex/pull/118)（`d413a20`）合入 `main`，但**未在正式 `0.1.32` 中发布**：`0.1.32` 仍把 CLI 输入错误归并为封闭的 `invalid_arguments`。

<a id="windows-launcher"></a>
## Windows 服务启动器

### 两个能力必须分开

知识调用所需的 Python API 能力，与 Windows 计划任务启动器所需的 GUI 子系统能力，是两个独立边界：

- 一个环境可能通过 Python API 校验，但仍缺少 Windows 计划任务启动能力（`Subsystem == 2`）；在 `mindie-agent-codex` 中，`knowledge_query` 仍会连接所选知识服务（`connect(selected)`）：已运行的健康服务可能应答，而冷查询依赖服务成功启动（`ensure_service`），因此不能假定计划任务启动器无效时查询仍会成功；
- 同一环境生成的 `Scripts\pythonw.exe` 可能是控制台子系统（CUI）启动器，不能作为计划任务入口；
- 计划任务由 Task Scheduler 直接执行配置的程序，Python 进程内的 `CREATE_NO_WINDOW` 与任务的 `Hidden` 属性都不能替代入口二进制本身的有效性。

共享校验会解析入口二进制的 PE32/PE32+ 头并要求 `Subsystem == 2`（`IMAGE_SUBSYSTEM_WINDOWS_GUI`）。文件名是 `pythonw.exe` **不**构成证据；`Subsystem == 3` 的 CUI 启动器必须被显式拒绝。新注册与恢复旧注册任务并实际拉起进程前都要执行该校验。

### 明确拒绝 PE `Subsystem` `3 → 2` 字节修补

把 PE 头中的 `Subsystem` 从 `3` 改成 `2` 不是受支持的恢复操作：

- 它违反历史门禁 **P1.6** 对覆盖或修补解释器二进制的禁令；
- PE 头属于 Authenticode 签名覆盖的镜像内容，修改会使既有签名失效，并可能触发 Smart App Control 或企业策略拒绝（这不等同于“所有未签名程序都会被拦截”，但足以使其不能作为产品恢复方法）；
- 头字段检查通过只证明该字段为 `2`，不能证明虚拟环境派发、启动参数、签名有效性、桌面行为、无 `conhost.exe` 或优雅停止；
- 修补保留了错误的来源与不可复现的本地状态，下次重装或升级会再次失效；仅保留备份也不能恢复来源或验证修补后的启动器。

不要复制系统 `pythonw.exe` 到虚拟环境，不要回退到环境外的 Python，也不要建议用户关闭 Windows 安全保护。

### 安全的候选恢复路径

1. **区分故障类型**：入口缺失、不可读/格式错误，还是可读的 CUI 启动器。不要用同一句“启动器无效”覆盖三种情况。
2. **选择真实 GUI 能力的发行版**：通过现有安装/准备机制选择一个经过批准、版本兼容、其 `pythonw.exe` 确实为 `Subsystem == 2` 的 Python 发行版。`uv --python 3.13` 只是版本选择请求，不保证 GUI 子系统。
3. **构建全新的自有候选**：用现有 builder 以显式选择的基座构建新候选，验证生成启动器的 PE 子系统、依赖版本、适配器/API 兼容性与虚拟环境身份。API 校验与“可作计划任务入口”的校验必须分开；API 通过不等于服务就绪。
4. **原子交接**：经现有原生绑定事务发布候选，在替换验证成功前保留旧的可绑定环境。先验证、后退役旧服务，不能让发布步骤先破坏仍可用的绑定。
5. **不要盲装同一代**：两条准备路径都可能复用未编码该修复的缓存；应使用新的候选代际/根目录，或采用修正后的正式发布。不要删除已绑定运行时或清空无关用户缓存。

候选阶段的服务能力校验（例如 `product_contract.probe(..., require_windows_service=True)` 转交 `candidate_validate.py` 复用共享 PE 校验，并由 `bootstrap.py`、`component_update.py`、`release_activation.py` 在准备与激活流程中协同）已在 [mindie-agent-codex#118](https://github.com/mindie-agent/mindie-agent-codex/pull/118)（`d413a20`）中实现并合入 `mindie-agent-codex` `main`，同时已在托管 `windows-latest` CI 中验证。不过它**未在正式 `mindie-agent-codex 0.1.32` 中发布**：`0.1.32` 的已发布保证仍是注册与恢复启动时的实际 PE 检查，而**该路径的交互式 Windows 桌面计划任务验收仍未执行**。不要把它描述成 `0.1.32` 现场已具备的能力。

服务能力失败只阻断依赖该服务的知识/采集动作；确定性工具与无关用户工作应继续可用，但查询是否可用仍取决于其实际路由与服务状态，不能假定服务启动器失败后查询一定成功。把“API 成功但服务启动器不可用”如实报告为服务未就绪，才是完整的状态。

<a id="session-authorization"></a>
## 会话、域与贡献授权

知识能力有三层彼此独立的授权与同意状态，不能用一次成功调用推断其余层：

1. **原生会话授权**：当前会话是否手动执行过 `/mindie-agent`；不跨会话、Fork 或子代理继承。
2. **领域租约**：路由到的所选领域是否有自己的有效租约；默认引擎的租约不能替代所选领域的租约。
3. **持久贡献授权与范围**：用户是否开启共享、目标仓库与授权项目范围；它与插件版本解耦，并独立于会话授权。

### 查询与蒸馏的授权矩阵

| 当前原生会话 / 所选领域 | `knowledge_query` | `knowledge_distill` |
| --- | --- | --- |
| 默认与所选引擎均无会话授权 | `knowledge_inactive` | `knowledge_inactive` |
| 默认引擎有授权，但路由目标缺少自身租约 | 可通过经验证的适配器身份完成公共检索 | `lease_required` |
| 所选引擎具备所需租约 | 可以执行 | 仍需有效贡献授权与范围 |
| 共享关闭或采集超出授权范围 | 检索可以保持可用 | 不得承诺仅本地蒸馏；已检查的传输层会强制贡献授权 |

由此可得：

- `knowledge_inactive` **不是**蒸馏专属错误，查询同样可能被拒绝；
- “查询成功、蒸馏却返回 `knowledge_inactive`”应先比对会话身份、配置、路由与时间窗口，不能据此推断存在“查询无需激活”的通用契约；
- 路由到所选领域的蒸馏即使有默认会话授权，也可能因缺少该域租约返回 `lease_required`，而不是 `knowledge_inactive`；
- 共享关闭或超范围并不自动关闭检索；但也不要把“本地只读”当成可以绕过贡献授权的蒸馏承诺。

### 手动入口与禁止事项

- 手动 `/mindie-agent` 只授权当前会话；它不能修复解释器来源、输入编码、服务注册或配置绑定。
- 重复执行 `/mindie-agent` 不会补齐缺失的领域租约或贡献授权，反复重试还可能制造重复服务与不确定状态。
- 严禁伪造租约、线程 ID、令牌或内部验证字段，也不要用直接导入适配器的方式“绕过”准入。
- 一次成功的 `knowledge_query` 只证明该请求所选路由的检索路径可用，不证明采集已绑定、蒸馏已准入或知识已发布。

<a id="readiness"></a>
## 按能力判断就绪

“健康”必须相对于请求的能力与已持久化的同意状态来判断，不能把某一条固定检查清单套到所有场景。

| 请求能力 | 需要的证据 |
| --- | --- |
| 运行时调用 | 配置的规范解释器/脚本对、隔离调用、实际包身份 |
| 查询 | 当前原生身份与会话授权正确，经所选路由成功完成请求/响应 |
| 共享关闭时的采集 | 持久化的关闭选择被尊重；不要求采集 |
| 授权范围外的采集 | 明确的超范围处置；不强制纳入 |
| 已启用、已授权且范围内的采集 | 已绑定采集与 `capture-ready`，或可见的失败/降级状态 |
| 服务健康 | 正确的属主/端点、相关存活性与无后台失败报告 |
| 蒸馏/索引 | 实际操作回执/结果，而非线程存活 |
| 社区发布 | 实际发布结果或远端引用；仅本地落盘不足 |

因此：

- 共享关闭或刻意超范围时，不应为了满足“健康检查”而冷启动采集；后续一次已授权的查询仍可能需要检索服务。
- 只有“已启用、已授权且在范围内”的采集才要求 `capture-ready`；不能把缺少它一律判为全局故障。
- 引擎状态中的 `worker`、`summary`、`outbox` 是后台**线程**，不是 OS 进程。三者存活不代表蒸馏成功、索引完成或发布成功；不要用进程枚举去“补齐”这些字段，也不要把它们同时存活当作所有能力的通用门槛。
- 服务健康应核对正确的服务属主、端点与相关存活信号；只有实际蒸馏回执/结果才能证明蒸馏，只有实际远端引用才能证明社区发布。

<a id="distillation"></a>
## 蒸馏输入与结果

### 公开 Schema

`mindie-agent-codex 0.1.32` 的公开 `knowledge_distill` 输入契约如下：

| 字段 | 契约 |
| --- | --- |
| 必需顶层字段 | `inputs`、`task_state` |
| 可选顶层字段 | `domain`、`related_refs`、`proposal` |
| 每个 `inputs` 项必需字段 | `kind`、`outcome`、`source_locator`、`content`、`evidence_refs` |
| 每个 `inputs` 项可选字段 | `repetitions`，整数且 ≥ 1 |
| `kind` 允许值 | `experiment_ledger`、`run_manifest`、`authorized_transcript`、`ecosystem_repo`、`hardware_spec`、`ablation_receipt` |
| `outcome` 允许值 | `observed`、`verified`、`compile_failed`、`infra_failed`、`measurement_invalid`、`in_flight` |
| `task_state` 允许值 | `in_flight`、`verified_milestone`、`completed` |

不要把 `milestone`、`evidence`、`proposed_rule` 等概念字段当作未声明的顶层参数传入。`proposal` 若提供，必须是结构化的 `mindie-distill-decision/1` 契约，不是自由文本规则；传输层内部支持更多字段，也不扩大 Codex 的公开 Schema。

### `in_flight` 与 `noop` 的语义

已检查的 `mindie-knowledge 0.13.19` **不会**对所有 `in_flight` 任务一律返回 `noop`：未完成任务中**有实质证据且已验证的里程碑**仍可被准入。空输入、未验证或琐碎输入仍可能产生 `noop`。`Stop` 事件不等同于任务完成。

因此：

- `task_state="in_flight"` 表示任务尚未结束，不自动等于“拒绝蒸馏”；
- `outcome="in_flight"` 是单个输入项的状态，不替代顶层 `task_state`；
- `noop` 不是发布成功，也不代表已经生成或合并知识变更；它只说明本次没有可准入的实质变更；
- 不要把“任务完成”当作调用蒸馏的必要仪式；只有达到可提炼里程碑时才调用。

### 超时、计费与外部写入

- 已检查的默认 RPC 预算是 **420 秒**；Codex 适配器为辅助调用增加余量到 **450 秒**。
- 外层调用必须在此基础上再预留清理余量，不能直接拿 450 秒当总超时，也不能复用查询的 45 秒预算。
- 不要写 `timeout N cmd || cmd` 或在超时后自动重发。
- 蒸馏可能触发付费模型调用，发布可能产生 Git/远端写入。结果不确定时必须保留“已发出、结果未知”的状态，先只读对账；不得盲目重放可能计费的蒸馏或不确定的外部写。
- 已完成的主结果与清理失败要分开记录；清理异常不能把已完成的蒸馏改写成失败，也不能诱发第二次付费调用。

<a id="failure-recovery"></a>
## 按失败阶段恢复

恢复的第一步是确定失败发生在哪一层，而不是立刻重试。不同阶段可能都表现为 `invalid_arguments` 或 `connection_unavailable`，但安全动作不同。

| 失败阶段 | 典型可见结果 | 已证明的事实 | 安全恢复 |
| --- | --- | --- | --- |
| 配置/绑定 | 配置文件缺失、JSON 损坏、`python` 或 `runtime_scripts` 为空 | 尚未进入知识调用 | 修复 `MINDIE_AGENT_CONFIG` 或默认配置；重新读取同一配置对象的二元组，不回退环境 Python |
| 解释器/包 | 解释器缺失、导入失败、包版本不符 | 运行时身份或依赖不成立 | 用配置解释器加 `-I` 核对 `sys.prefix` 与包版本；必要时按准备流程构建新候选，不复制脚本到别处 |
| argv | 多一个参数、缺少操作名 | 请求未派发 | 使用 `describe` 或单个 `<operation>`；不要添加未支持的 `--json`。`--input-file` 已合入 `main`（`#118`、`d413a20`），但**未在正式 `0.1.32` 中发布**，`0.1.32` 现场仍只能用 stdin，需等正式发布 `> 0.1.32` |
| 输入编码 | `invalid_arguments`、中文变 `?`、UTF-16LE 文件 | 字节在 Python 前已损坏，或解码失败 | 按上面的 UTF-8 调用处理（有控制台用管道，无控制台用 `ProcessStartInfo`）；核对发送字节与 BOM；不要靠 `PYTHONUTF8` 事后修补 |
| 输入大小/空/JSON | `invalid_arguments`、无派发 | 输入为空、超 1 MiB 或 JSON 畸形 | 检查空输入、截断与字节长度；重新生成合法 JSON；不要猜测“后端故障” |
| Schema | `invalid_arguments`、字段缺失/未知 | 请求已解析但未通过领域 Schema | 按上面的公开字段与允许值修正；不要传入概念字段或内部字段 |
| 会话授权 | `knowledge_inactive` | 当前会话未获原生授权，或身份/配置/路由不匹配 | 在当前会话手动执行 `/mindie-agent`；确认从当前原生工具环境调用；不伪造 `CODEX_THREAD_ID` |
| 领域路由/租约 | `lease_required` | 默认会话授权存在，但所选领域没有自己的租约 | 核对所选 `domain`、路由目标与租约状态；不复制其他领域的租约 |
| 贡献授权/范围 | 蒸馏因授权或范围被拒 | 租约可能存在，但贡献同意或范围不满足；`noop` 本身不能证明原因 | 检查持久贡献开关与授权项目范围；不要为通过检查而关闭保护或强制纳入超范围项目 |
| 服务启动器 | 服务注册/恢复启动被拒绝（如 `windowless_interpreter_*`）、可见控制台窗口 | 仅在注册/恢复启动被拒绝并报 `windowless_interpreter_*`、且 PE 头检查确认入口缺失/损坏/非 GUI 时，才证明入口二进制有问题；仅有可见控制台窗口也可能来自有效 GUI 父进程派生了未隐藏的控制台子进程（P1.5），必须先做进程树与子进程隐藏诊断 | 先确认启动器专属错误与入口实际 PE 子系统，再决定是否重建；仅出现可见窗口时先做进程树与子进程隐藏诊断。确需修复时按“Windows 服务启动器”构建全新 GUI 候选并原子交接；严禁 PE 字节修补或覆盖解释器 |
| 传输/超时 | `connection_unavailable`、超时、连接中断 | 标签本身不能证明请求未发出或服务未启动 | 先只读核对现有回执、服务属主与远端状态；只有证明请求尚未离开且操作只读幂等时，才允许有界重试一次 |
| 蒸馏结果不确定 | 超时、断连、回执缺失 | 可能已计费或已产生外部写 | 保留原始操作 ID 与不确定状态，只读对账；绝不自动重放蒸馏或发布 |

### 恢复的四条边界

1. **按阶段处理**：编码问题不要用激活修复，授权问题不要用重装修复，启动器问题不要用重复激活修复。
2. **保留原始失败**：记录原始错误、版本、请求属性与已确认事实；替换诊断不能抹掉第一次失败。
3. **只暂停依赖动作**：服务启动器失败时，非知识工具与不依赖该服务的动作仍可用；不要让一个知识能力故障拖垮整个任务。
4. **不确定不重放**：`connection_unavailable`、超时或缺失回执都不自动等于“没发生”。对可能计费/外部写入的操作，先只读对账再决定。

<a id="evidence"></a>
## 验证记录

公开或团队内共享的验证记录应先脱敏，再保留足以复现边界的属性。建议清单：

- **版本与来源**：`mindie-agent-codex` 版本与提交、原生 Codex 版本、Windows 构建、Windows PowerShell 5.1 或 `pwsh` 版本、Python 发行版与版本、`uv` 版本、已安装 `mindie-knowledge` 版本；未知项明确写“未知”。
- **配置绑定**：使用 `MINDIE_AGENT_CONFIG` 还是默认路径；`python` / `runtime_scripts` 是否来自同一配置对象；路径用 `<config>`、`<runtime-python>` 等占位符代替用户名与主目录。
- **解释器身份**：`-I` 下的 `sys.prefix`、`mindie-knowledge` 实际版本、`knowledge_cli.py` 来源；不要只记“解释器存在”。
- **输入属性**：操作名、argv 形态、输入字节数、是否含 BOM、是否为 UTF-16LE/GBK、是否出现 ASCII `?` 替换；不要保存原始查询正文或完整对话。
- **会话与授权**：当前会话是否已激活、`knowledge_inactive` / `lease_required` 的实际返回、贡献开关与范围是否满足；不要记录线程 ID、令牌或内部验证字段。
- **服务与启动器**：候选代际、实际入口的 PE `Subsystem` 值、注册与恢复启动的结果、是否出现可见窗口或 `conhost.exe`；不要公开完整用户路径。
- **操作结果**：查询是否成功及命中的公开单元 ID、蒸馏是 `noop` 还是产生 `reviewed_change`、发布是否有远端 PR/提交引用；不要把 `noop` 记成发布成功。
- **验收缺口**：哪些步骤未执行（例如未做 Windows 桌面验收、未测 `powershell.exe`、未验证旧绑定退役），如实列为 skip，不用退出码为零代替行为验证。

一个脱敏记录模板：

```text
codex_plugin: mindie-agent-codex 0.1.32 (<commit>)
native_codex: <version or unknown>
windows: <build or unknown>
shell: Windows PowerShell 5.1 / pwsh <version or unknown>
python: <distribution/version or unknown>
uv: <version or unknown>
knowledge_installed: <version or unknown>
config_source: MINDIE_AGENT_CONFIG / default
runtime_pair_same_config: yes/no
sys_prefix: <redacted>
operation: knowledge_query / knowledge_distill
argv_shape: <one operation> / <other>
input_bytes: <n>
input_encoding: utf-8 / utf-8-bom / utf-16le / unknown
ascii_replacement_seen: yes/no/unknown
session_grant: active/inactive/unknown
authorization_result: success / knowledge_inactive / lease_required / other
service_entry_subsystem: 2 / 3 / missing / unknown
desktop_acceptance: performed / not performed
notes: <sanitized>
```

不要公开：用户名与主目录、完整配置路径、令牌/Cookie、线程 ID、原始查询与对话、工具载荷、未脱敏的远端地址或凭据。诊断日志可以保留在本地私有目录，但公开报告只保留脱敏后的结论。

<a id="implementation"></a>
## 实现状态

### 状态表

| 能力 | 实现状态 | 在 `mindie-agent-codex 0.1.32` 的可用性 | 验证与验收边界 |
| --- | --- | --- | --- |
| UTF-8 stdin CLI 调用 | 已随 `0.1.32` 发布 | 可用 | 由已检查接口推导；本次评审未做 Windows 桌面验收 |
| `--input-file <path>` | 已合入 `main`（[#118](https://github.com/mindie-agent/mindie-agent-codex/pull/118)，`d413a20`） | **未发布**；`0.1.32` 不可用 | 已在托管 `windows-latest` PowerShell 5.1 CI 验证（[`adapter (windows-latest)`](https://github.com/mindie-agent/mindie-agent-codex/actions/runs/43748768061/job/132920529110)），`run 43748768061`；交互式 Windows 桌面验收未执行 |
| 结构化 `stage` / `reason` | 已合入 `main`（[#118](https://github.com/mindie-agent/mindie-agent-codex/pull/118)，`d413a20`） | **未发布**；`0.1.32` 仍把 CLI 输入错误归并为 `invalid_arguments` | 由单元测试与 CI 套件验证 |
| 注册与恢复启动的 PE 校验 | 已存在于共享 Knowledge（本次检查 `0.13.19`） | 可用；Codex `0.1.32` 声明基线为 `0.13.17` | 贡献者实际安装版本未知 |
| 候选阶段的 `require_windows_service` 校验 | 已合入 `main`（[#118](https://github.com/mindie-agent/mindie-agent-codex/pull/118)，`d413a20`） | **未发布**；`0.1.32` 的保证仍是注册与恢复启动时的 PE 检查 | 已在托管 `windows-latest` CI 验证全新/缓存准备与退役前激活；交互式 Windows 桌面计划任务验收未执行 |
| 直接导入 `knowledge_cli.invoke(...)` | 明确拒绝 | 不适用 | 模块归属错误，且不绕过 `CODEX_THREAD_ID` 与授权；非稳定 API |
| PE `Subsystem 3 → 2` 字节修补 | 明确拒绝 | 不适用 | 违反 P1.6，破坏签名/策略完整性，且不能证明 venv 派发或桌面行为 |
| 本手册的 Windows 桌面端到端验收 | 未执行 | 不适用 | 不得把接口审查写成现场验收 |

### 配套修复与剩余缺口

- **Codex 适配器**：保留 stdin 契约，并已随 [#118](https://github.com/mindie-agent/mindie-agent-codex/pull/118)（`d413a20`）合入 `main`：新增显式 UTF-8 文件输入，在派发前区分 argv、空输入、超限、编码、JSON、对象与 Schema 失败，并在 `mcp_gate` 中增加允许列表化的 `stage` / `reason`，同时避免泄露载荷、路径与任意异常文本。
- **候选准备/验证**：把“需要 Windows 服务能力”作为显式模式传入候选探测并复用共享 PE 校验，已随 [#118](https://github.com/mindie-agent/mindie-agent-codex/pull/118)（`d413a20`）合入 `main`；`bootstrap.py`、`component_update.py`、`release_activation.py` 在发布服务型候选或退役旧服务前完成校验，且不为校验启动服务、改授权或注册任务。
- **测试**：CLI 字节边界与独占常规文件 `--input-file` 测试、`argv` / Schema 的 `stage` / `reason` 区分、以及托管 `windows-latest` 的 `powershell.exe` 5.1 往返与 UTF-8 BOM 处理均已合入并通过 CI；**交互式 Windows 桌面计划任务验收仍未执行**。
- **文档**：本双语手册与索引、生命周期、历史门禁、知识系统 §4.1 的交叉链接；不把已合入 `main` 但尚未在 `0.1.32` 发布的修复描述成 `0.1.32` 的现有功能。

在正式 `mindie-agent-codex` 发布 `> 0.1.32` 且交互式 Windows 桌面验收完成前，正式 `0.1.32` 安装仍不具备 `--input-file`、结构化 CLI 输入 `stage` / `reason` 与候选阶段启动器校验。文档合并不代表这些能力已在 `0.1.32` 现场可用，也不代表运行时缺陷已经随正式发布交付。

## 相关文档

- [宿主边界与任务生命周期](harness-boundary-and-lifecycle.md)（会话授权与 §2.4 边界）
- [历史版本问题复盘与系统性防复发门禁](historical-issues-and-guardrails.md)（P1.6、P2.6）
- [知识与经验系统](knowledge-system.md)（§4.1 蒸馏触发与证据）
- [源码开发、重编译与产物恢复契约](source-rebuild-contract.md)
- [PR #357](https://github.com/mindie-agent/mindie-agent/pull/357)（`YzTongNiar` 的 Windows 现场报告）

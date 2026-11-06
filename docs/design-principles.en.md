# MindIE Agent Engineering Design Principles & Guidelines

[中文](design-principles.md) · [Back to Documentation Center](README.en.md)

MindIE Agent is built with a single goal: **make general-purpose AI coding agents genuinely effective, effortless, and unobtrusive for Ascend NPU and LLM inference engineering.**

Starting from nine foundational product and boundary principles, our engineering guidelines have evolved through real-world Ascend troubleshooting, cross-platform support (macOS, native Windows, Windows WSL), and multi-host integration (Claude Code, OpenAI Codex CLI, Kimi Code, DeepSeek Harness) into a comprehensive set of product and operational rules.

---

## Part 1: Nine Core Product & Tool Boundary Principles

These nine principles define what should be a tool, what should be a Skill or knowledge package, and how to minimize friction for both humans and Agents:

1. **Measure efficiency by the total cost of achieving the user's real goal (Top Priority)**
   - Total cost includes **understanding, configuration, waiting, debugging, and rework**—not just raw execution time.
   - Reliability mechanisms are worthwhile only when they reduce these real costs. Never burden every everyday task with heavy ceremony just to guard against rare edge cases. When other considerations conflict with this rule, Principle 1 wins.
   - **Task continuity is a P0 product requirement**: Failures in MindIE knowledge, setup, diagnostics or local recording affect that capability, not the whole user task. Report the failure, retain completed results and job references, and continue independent steps or use equivalent authorized host tools. Defer optional onboarding. Preserve identity, permissions, actual device/port ownership and reconciliation of uncertain writes; pause only the affected action when those facts cannot be established.
2. **Turn only well-bounded, closed problems into tools**
   - A tool must have clear preconditions, inputs, outputs, and failure modes (e.g., reading a remote file, querying live NPU telemetry, or redacting secrets).
   - Leave open-ended, context-dependent judgment to the Agent; extract only repeatable, deterministic operations into stable tools, and never expand scope just for the sake of building a tool.
   - **Tools must expose escape routes**: When a helper or standard workflow is unsuitable, the agent may continue within existing authorization through CLIs, native shell/SSH or task-specific scripts. Preserve the original failure, confirmed facts and usable endpoint/job references. Discovery or preparation failures do not gate the whole task; reconcile uncertain writes and retain actual resource ownership. See the [Unified Execution and Escape Contract](source-rebuild-contract.en.md).
3. **Never increase cognitive load for the Agent or the user (Single Unified `/mindie-agent` Entry)**
   - From the user's perspective, every interaction and setting is wrapped inside a single unified entrypoint: **`/mindie-agent`**. Users should never have to learn or type internal subcommands such as `/mindie-agent:init`, `/mindie-agent:status`, or long flag strings—they simply use `/mindie-agent` with natural language, and internal state routing is handled behind the scenes.
   - A CLI that forces users to memorize subcommands, exposes tangled internal state, or requires reading source code to understand an error is a classic anti-pattern.
4. **Give every tool a single, well-defined boundary**
   - Each tool should solve one cohesive problem. It can execute the necessary multi-step mechanics internally so the Agent does not have to micromanage every step, while avoiding monolithic "kitchen-sink" tools that mix unrelated responsibilities.
5. **Skills provide a map and practice Progressive Disclosure, not a straitjacket**
   - Keep the top-level Skill concise and focused on core troubleshooting, knowledge lookup, and remote execution; place low-frequency setup wizards, historical import, and recovery details into secondary `references/` documents that the Agent loads **progressively on demand** only when relevant.
   - Concrete troubleshooting lessons belong in the Knowledge base rather than rigid step-by-step mandates inside a Skill.
6. **Knowledge is advisory reference material, never mandatory dogma**
   - Knowledge packages store applicability conditions, evidence, and caveats in plain Markdown. A search hit or merged PR never makes an entry infallible—decisions must always be grounded in the live behavior of the current system.
   - The Agent consults or records experience on demand, with **no mandatory lookups, mandatory writes, rigid fill-in-the-blank templates, or end-of-task closing rituals**.
7. **Manual per-session activation for the Knowledge Flywheel; default availability for deterministic tools and background capture in enabled sessions**
   - **Manual `/mindie-agent` session trigger for the Knowledge Flywheel**: Knowledge search (`query`), reading (`explain`), feedback (`feedback`), distillation (`distill`), feed sync (`sync`), and background `Stop` capture require explicitly invoking `/mindie-agent <problem description>` (or `$mindie-agent` in Codex) once in the current chat; subsequent turns in the same session retain the grant until explicit deactivation, while ordinary unactivated chats receive no knowledge Skill, start no knowledge service, and perform no `Stop` capture.
   - **Default availability for deterministic tools**: Everyday prompts involving remote servers/containers (`remote-dev`), cluster probing and leases (`coordinator`), `npu-top` monitoring, trace analysis (`profiler`), roofline simulation (`sim`), local diagnostics (`diagnostics`), or factual `status` inspection work by default without `/mindie-agent`.
   - **Automatic background experience loop in enabled sessions after one-time opt-in**: Once the user enables community contribution during installation or first-time setup, that saved consent persists across sessions; in any `/mindie-agent`-enabled session, `Stop` automatically captures, redacts, and packages experience in the background—**without re-prompting for consent or requiring a closing instruction**.
8. **Reuse proven host, OS, and ecosystem mechanisms first**
   - Whenever task semantics and compatibility requirements are met, reuse mechanisms already provided by the host CLI, operating system, `uv`, and mature libraries, as well as existing build artifacts and verified results.
   - Identify concrete gaps before writing custom code, keep custom glue minimal, and delete replaced legacy managers or duplicate state stores once a native mechanism is adopted.
   - **Choose sources and runtime from user intent**: Honor explicit new-directory or binding choices; otherwise retain existing sources and a compatible environment. Source directories, build outputs and Python environments are separate choices. Select interpreters by observed dependencies and bindings, preserving virtualenv identity rather than choosing the highest version or underlying executable realpath. Reuse native artifacts for Python-only edits; preserve affected baselines before native overwrites and verify actual loading and correctness. See [Source Development, Native Rebuilds and Artifact Recovery](source-rebuild-contract.en.md).
9. **Keep tools observable and diagnosable; never hide errors**
   - Surfacing honest, actionable errors is a hard product requirement. When a required step fails, report it clearly—**never disguise a read failure as "empty data," a corrupted database as "first-time use," or a local save as "published."**
   - Clearly distinguish **completed**, **failed**, and **uncertain (`unknown`)** outcomes. If a primary operation succeeds but cleanup or bookkeeping fails, report both separately so the caller is never tricked into repeating a completed action.

---

## Part 2: Evolved Engineering & Operational Guidelines

As MindIE Agent matured across hosts and operating systems, we codified five operational guidelines extending Principles 8 and 9:

### 10. Build Only for Proven Gaps and Refactor Directly Around Core Business Logic
- **Verify with lightweight probes first**: Before refactoring updaters, hooks, or process management, verify host and OS behavior (timeouts, cancellation, abrupt termination) using minimal model-free probes.
- **Take core business logic correctness as the sole baseline; delete and rewrite unreasonable designs directly**: When encountering over-defensive imaginary-enemy checks, shadow state machines, or obsolete shims, refactor destructively by deleting and rewriting them cleanly rather than maintaining dual-track baggage (while preserving existing user Markdown packages, cursors, and consent settings).
- **Data-format-driven compatibility**: Before formal release, rewrite intermediate implementations cleanly without carrying multi-generation shims. After formal release, design compatibility around actual schema and contract changes rather than guessing from version strings.

### 11. Decouple User Consent from Code Installation Identity (Configure Consent Once, Run Automatically in Enabled Sessions)
- **Configure once, persistent across sessions**: A user's contribution preference, public target repository, and authorized project scope are persistent user settings decoupled from the installed code revision. Once enabled, background capture and redaction run automatically at the end of every `/mindie-agent`-enabled session within the authorized project scope (while ordinary sessions where `/mindie-agent` was not invoked skip capture) without requiring repeated consent prompts or closing instructions.
- **No re-prompting or silent overrides**: Restarting sessions, reinstalling, or silently updating a plugin preserves existing consent and explicit disablement without re-prompting or silently turning disabled settings back on.

### 12. Paired Component and Plugin Releases
- **Release dependencies before plugins**: Every first-party runtime dependency pinned by a plugin (`diagnostics`, `remote-dev`, `knowledge`, `coordinator`, `npu-top`) must first have a published, non-draft, non-prerelease GitHub Release whose tag resolves to the exact locked commit and whose uploaded wheel/sdist artifacts match `uv.lock`.
- **Independent component versioning**: Each repository maintains its own version sequence and reuses unchanged Releases without artificial version bumps. See the [Paired Component and Plugin Release Checklist](release-compatibility-and-update.en.md#paired-component-and-plugin-releases).
- **Scope release documentation checks**: Select independent component, corpus or plugin targets with `--release-repo <repository>`. R6 checks their own source versions, READMEs and LF; it does not require a main product bump, a historical channel update or peer README edits. Only an intentional product combination uses `--release-scope product` and full version-table synchronization.

### 13. Silent Background Updates with Atomic Idle Cutover
- **Compatibility-first selection**: Each plugin Release declares its verified Harness version range in `harness-compatibility.json` and automatically selects the highest compatible formal Release rather than chasing an unverified `main` branch.
- **Zero hot-path blocking**: More than 24 hours after the last successful check, natural usage triggers an asynchronous background check and runtime build; everyday tool calls perform only a fast local timestamp check.
- **Atomic cutover when idle**: After downloading and building the locked `uv` environment outside the active runtime, the updater waits until no active RPC, capture, or indexing job is running, acquires the exclusive lock, retires the old worker, and atomically switches the active installation binding without user prompts or manual session reloads. See [Release Compatibility & Silent Update](release-compatibility-and-update.en.md).

### 14. Fail-Visible Semantics, No Silent Fallbacks, and `unknown` Side-Effect Protection
- **No silent fallbacks or fake success**:
  - Never catch an exception and silently return `{}`, empty lists, skip corrupted state, or disguise a failure as `"status": "active"` / `exit 0`;
  - **Never let secondary bookkeeping overwrite primary success**: When a remote NPU command or core operation has already succeeded and returned valid output, a local SQLite receipt lock timeout or background grandchild pipe cleanup delay must preserve the primary result and attach a diagnostic warning—never flip a succeeded call to `isError = True`;
  - **Guard against exception hierarchy swallowing (`TimeoutError` $\subset$ `OSError`)**: Always handle `TimeoutError` explicitly before `except OSError:` in Python 3 so self-raised timeouts are never silently swallowed as generic file I/O errors.
- **Protect uncertain (`unknown`) external writes**: If a paid model call or external Git/PR write times out or loses its receipt, record it as `unknown` and reconcile read-only against the remote target before any future write—never blindly retry it as if it had not run.
- **Protocol safety never hides business faults**: A Hook may exit cleanly so the host model does not loop, but any underlying capture or service failure must still be surfaced through the host's warning field or the next tool call's diagnostic status.

### 15. Timeout Arithmetic Consistency & Anti Over-Defensive Programming
1. **Timeout Arithmetic Invariants**:
   - **Outer timeout must strictly exceed inner step budgets plus cleanup grace (`outer_timeout >= sum(inner_budgets) + cleanup_grace`)**:
     - Never wrap a `30s` inner command inside a `1.5s` `HOOK_TOTAL`, set local `STOP_DRAIN (2.0s) == remote STOP_GRACE (2.0s)` (failing locally at the exact millisecond `SIGKILL` is sent), or set verifier `deadline = timeout - 0.1s` without leaving time for `finally: inventory()` (which falsely triggers `UnknownExternalEffects`);
     - Multi-stage diagnostics (e.g., Stage 1 with SSH ControlMaster and Stage 2 bypassing ControlMaster) must have independent timeout budgets so a hung Stage 1 never starves Stage 2;
     - Never write `timeout 10 cmd || cmd` in shell scripts (when `timeout` exits with `124` on a hung driver, `||` immediately runs `cmd` without a timeout and hangs forever).
   - **Eliminate bimodal timeout extremes (no sub-second hot-path guillotines or unbounded `timeout=None`)**:
     - **No sub-second (`< 1s`) SQLite lock timeouts**: Multi-thread/cross-process SQLite locks must never use `100ms–250ms` micro-timeouts (which abort normal queries or permanently drop `Stop` session captures under normal indexing load); enable WAL mode and use `3.0s–5.0s` timeouts;
     - **No unbounded `timeout=None` on subprocesses or handshakes**: Every external subprocess (`gitleaks`, summary commands, candidate validation, `docker inspect/top` under host locks) must specify an explicit bounded timeout, and RPC handshakes (`ready.wait`) must be governed by `deadline` from function entry.
2. **Four Anti Over-Defensive Programming Iron Rules (Centered on Core Business Logic, Stripping Defensive Paranoia Bloat)**:
   - **Iron Rule 1: Lightweight local state connection; prohibit per-SQL hot-path `.owner`/Schema reflection self-checks**: SQLite executes `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;` and schema initialization only during `open_database`. Intercepting every `SELECT` to run `lstat(.owner)` or `:memory:` full-table schema reflection is strictly forbidden.
   - **Iron Rule 2: Enforce a strict boundary between external side effects and local state; abolish local one-way self-bricking**: Retain `unknown` receipt reconciliation strictly for irreversible external writes (metered LLM calls, GitHub PR/Issue mutations, destructive remote writes). Local idempotent states (virtualenv upgrades, `consent.json` migration, container `task_environment` preparation) must report errors transparently and self-heal idempotently on the next unlocked run—never write `suppressed` / permanent `fault` / `TaskRootBusy` self-bricking tombstones.
   - **Iron Rule 3: Prohibit cross-repo copy-pasted `*_fallback.py` / `*_bootstrap.py` shadow state machines and `ctypes` Win32 ACL ceremonies**: Host plugins depend directly on shared components pinned via `uv.lock`, and atomic file replacement uses standard library `os.replace()`.
   - **Iron Rule 4: Prohibit `inspect.signature` internal function signature reflection locks and giant inline Python string blobs (such as `REMOTE_FILE_PY`)**: Probes verify only public interfaces and version contracts; remote workers must be maintained as standalone `.py` modules.

### 16. Testing Design Guidelines: Eliminate Filler Tests, Embrace Tiered Live A2/A3 NPU Verification
See [Tiered Testing Architecture & Case Design Guidelines](testing-architecture.en.md) for the complete specification:
1. **Test Validity Redlines (Every Test Must Earn Its Keep)**:
   - **No defensive paranoia or prose-matching tests**: Never write tests that merely check Python types/defensive `ValueError` branches, repeatedly test `chmod 0o777`/`symlink` hypothetical attacks, assert static constant/enum string lists, or regex-grep `README.md`/`SKILL.md` prose;
   - **Never ratify silent error swallowing in tests**: Never write tests asserting that an underlying failure or timeout returns `exit 0` / `{}` / `"active"`;
   - **No production-script tampering or deceptive mocks**: Never overwrite production script files (e.g., replacing `admission_ops.py` with fake stubs) in integration tests or fabricate `MagicMock` objects that diverge from real server/hardware schemas.
2. **Four-Tier Testing Pyramid (Tier 0 – Tier 3, Default Standing A2/A3 Ascend NPU Environment)**:
   - **Tier 0 (Pure In-Memory Core Logic Unit Tests, `< 5s`)**: Zero subprocesses, zero network, zero `sleep`; covers parsers (backed by real A2 910B / A3 910C / A5 hardware Golden Captures), state-machine transitions (`InMemoryHostQueue` and real in-memory loops), redaction rules, domain retrieval precision/recall, and protocol translation.
   - **Tier 1 (Local Component Contract & Process Boundary Tests, `< 15s`)**: Reuses session-scoped pre-built Git/SQLite templates to verify cross-process locks, `python -I` isolated startup, and millisecond injectable timeout cleanup (never run network `pip install` or 10MB-scale `fsync` barrages inside tests).
   - **Tier 2 (Standing A2/A3 NPU Non-Destructive Live Integration `@pytest.mark.live_npu`, `< 25s`)**: Connects directly to the standing A2 (`173.125.1.2`) and A3 (`192.168.13.165` / `.156` / `.154`) clusters using isolated sandbox directories (e.g., `state_dir="/tmp/mindie-npu-test-<uuid>"`) without disturbing active workloads; routinely verifies live `npu-smi` probing, multi-Die `Phy-ID` mapping, Docker container pass-through, Linux `/proc` process-tree draining, and lease anti-preemption.
   - **Tier 3 (End-to-End Host CLI & `mindie-bench` Live Canary Acceptance, `< 90s`)**: Drives real host CLIs and `mindie-bench` Canary tasks to verify the complete loop.

### 17. Agent-Native Coding & Commenting Standards (100% Agent-Maintained Codebase)
Every repository in the MindIE Agent ecosystem is **100% read, evolved, and maintained by coding Agents**. Code structure and comments must be natively optimized for Agent attention and tool windows (such as the 800-line single `view_file` window):
1. **Module Size & Context-Window Friendliness**:
   - Keep core business modules cohesive and concise—targeting **under 800 lines per file** so a single `view_file` call captures the entire module without multi-page slicing caused by defensive boilerplate bloat;
   - **Ban 5–6 layer subprocess trampolines and pass-through wrappers**: Keep call graphs flat so an Agent can trace end-to-end execution from entrypoint to core logic in 1–2 file reads.
2. **Mandatory Module-Top Agent Invariant Header**:
   - Every core module must begin (within its first 30 lines) with a standardized four-part docstring contract so an Agent immediately understands module boundaries without scanning hundreds of lines:
     - `[Role]`: Single-sentence statement of the module's responsibility and primary entrypoints;
     - `[Invariants]`: Core business invariants enforced by the module (e.g., valid state transitions, returning `None` rather than zero-filling missing data, no silent fallbacks);
     - `[Timeouts & Locks]`: Lock granularity, SQLite/file lock policy, and timeout arithmetic hierarchy (`outer_timeout >= sum(inner_budgets) + cleanup_grace`);
     - `[Side-Effect Policy]`: External side-effect boundary (pure in-memory computation, idempotent local self-healing state, or irreversible external writes requiring `unknown` receipts).
3. **Commenting Principles: Document Why & Invariants, Never Defensive Excuses**:
   - **What to comment**: Non-obvious Ascend hardware behaviors (e.g., A3 910C dual-Die topology where `8 NPU × 2 Die = Phy-ID 0..15`), cross-process/container protocol boundaries (e.g., Linux `/proc` container PID namespace draining, `SIGTERM -> SIGKILL` grace arithmetic), and domain invariants;
   - **What never to comment**: Never restate what the code literally does, and never write paragraphs rationalizing imaginary-enemy defensive branches or fallback shims (if defensive bloat requires a long comment to justify its existence, delete both the code and the comment).

### 18. Algorithmic Performance, Bounded Memory/VRAM & Spec-Driven Local/Remote Placement
See [Execution Resource Expectations & Local/Remote Spec Matching Design](execution-resource-budget-design.md). Every component must be engineered for bounded compute time (preventing timeouts), bounded host RAM (preventing local machine freezes/OOMs), and bounded device VRAM/HBM (preventing NPU/GPU OOMs):
1. **Bounded Working Set Iron Rule ($O(\text{Active State})$ over $O(\text{Total History})$)**:
   - **Decouple active state from history**: In simulators (`sim`), trace analyzers (`profiler`), and telemetry collectors (`diagnostics`), resident memory in the main loop must scale only with the **active batch/window**, **never accumulating unbounded history across total steps ($T$), total tokens, or total log lines**;
   - **Online aggregation & bounded ring buffers**: Compute throughput and latency percentiles (P50/P90/P99) incrementally; when retaining detailed events, use an explicit **bounded ring buffer / Top-K** or stream directly to disk (JSONL streaming);
   - **Never materialize large files in memory**: Files larger than **`50 MB`** (profiling traces, logs, indices) must be processed via streaming/chunked readers, `mmap`, or SQLite indices—never via full-file `json.load()` / `file.read()`.
2. **Quantitative Memory Redline & Performance Discipline (`1 GiB` Defect Threshold)**:
   - **Control & analysis footprint baseline**: Routine tool calls and analysis tasks (`sim`, `profiler`, `knowledge`, `coordinator`) must keep working-set growth **`<= 256 MiB` (peak `<= 512 MiB`)**. Outside actual LLM weight loading or parallel C++ linking, any single Python process exceeding **`1 GiB`** peak RAM is treated by default as an **algorithmic/data-structure bug** that must be refactored (`__slots__`, flat arrays, streaming) rather than masked by raising host limits;
   - **Eliminate the three timeout & memory bloat anti-patterns**: (1) ban `copy.deepcopy`, `subprocess.run`, or per-row `sqlite.commit()` inside hot loops; (2) use analytical step folding / event-driven jumps rather than tick-by-tick spinning in simulators; (3) cap parallel workers by both CPU and usable RAM: $\text{Workers} = \max(1, \min(\text{usable CPU cores}, \lfloor \text{usable safe RAM} / \text{per-worker peak RAM} \rfloor))$, never raw `os.cpu_count()`.
3. **VRAM / HBM Safety Iron Rule: Zero-Weight Control Plane & Pre-Flight VRAM Sizing**:
   - **Zero weights & zero device context on control/analysis paths**: Inspecting model architecture (layers, hidden size, vocab) or operator signatures must read only `config.json` or `safetensors` headers (first 8 bytes + JSON header)—**never load weight tensors or initialize `torch_npu` / CUDA / CANN contexts just to read metadata**;
   - **Pre-flight VRAM sizing before device launch**: Operations that allocate NPU/GPU memory (serving, operator benchmarks, `mindie-bench`) must estimate $\text{Expected VRAM} = \text{Weights} + \text{KV Cache} + \text{Activation Peak} + \text{HCCL Buffer} + \text{Runtime Reserve}$ and verify `vram_free_mb >= Expected VRAM` (respecting per-Die physical limits on dual-Die A3 910C) before spawning.
4. **Cross-Platform (Windows / macOS / Linux) Spec-Driven Placement Over OS Hardcoding**:
   - **Never hardcode `sys.platform == "darwin"` or `os.name == "nt"` to gate execution**: MindIE Agent supports Windows, macOS, and Linux users alike;
   - **Match `WorkloadExpectation` against real `HostHardwareSpec`**: Heavy compute/memory/VRAM operations declare `{cpu_cores, memory_mb, vram_mb, expected_seconds}` upfront and compare the local machine's real usable specs (Windows/macOS/Linux) against remote servers (`fleet_probe.py`)—**running locally when local specs are sufficient (including high-spec local workstations stronger than remote servers) with CPU-adapted concurrency/timeouts, and routing to a matching remote server before launch when local specs are insufficient**.

---

## Part 3: Pre-PR Design Principles Checklist

Every development PR across all MindIE Agent repositories (covering code, configuration, dependencies, CI, and documentation) must review its final diff against these principles before submission:

| Dimension | Review Question |
|---|---|
| **1. Total Cost** | What real friction or cost does this change remove? Does it add unnecessary background work, repetitive full-tree hashing/IO checks, or extra user steps? |
| **2. Tool Boundary** | Is any toolified logic solving a closed, well-bounded problem rather than freezing open-ended judgment into a rigid flow? Do public discovery, input validation, runtime forwarding, recovery guidance and pinned dependencies work together for the same user scenario, beyond passing low-level SDK tests? |
| **3. Cognitive Load** | Does the change keep internal state and parameters simple for both users and Agents? |
| **4. Single Responsibility** | Are module boundaries clean without cross-repo leakage, duplicate state stores, or copy-pasted `*_fallback.py`/`*_bootstrap.py` shadow state machines? |
| **5. Informational Skills** | Do Skills remain clear, helpful guides rather than mandatory procedural checklists? |
| **6. Advisory Knowledge** | Do knowledge entries and feedback remain advisory without mandatory lookups, writes, or truth certification? |
| **7. On-Demand Activation** | Does everything trigger strictly on demand without unrequested background work or closing rituals? |
| **8. Reuse & Paired State** | Were host/OS/mature tools reused first? Were replaced implementations directly deleted and rewritten while preserving user data, consent, and external `unknown` receipts? |
| **9. Error Visibility & No Silent Fallback** | Do failure paths report honest, actionable errors without `except Exception:` silent `{}` / `"active"` / `exit 0` fallbacks, `except OSError:` swallowing `TimeoutError`, blind retries of `unknown` writes, or local bookkeeping/cleanup timeouts overwriting succeeded remote results? |
| **10. Timeout Arithmetic & Bounds** | Do all new/modified timeouts satisfy **`outer_timeout >= sum(inner_budgets) + cleanup_grace` (e.g., `SIGTERM->SIGKILL` / `inventory` drain)**? Are sub-second (`<1s`) SQLite lock guillotines, unbounded `timeout=None` subprocess calls, pre-`deadline` handshakes, and `timeout N cmd \|\| cmd` re-runs eliminated? |
| **11. Anti Over-Defensive Programming (Four Iron Rules)** | Does the change strictly obey the Four Anti Over-Defensive Iron Rules: (1) zero hot-path SQL `.owner`/Schema reflection checks; (2) `unknown` reserved strictly for irreversible external writes, with zero local one-way self-bricking (`fault`/`suppressed`/`TaskRootBusy`); (3) zero cross-repo copy-pasted `*_fallback.py`/`*_bootstrap.py` or Win32 ACL ceremonies (standard `os.replace()`); (4) zero `inspect.signature` internal parameter locks or giant inline Python string blobs (standalone `.py` remote workers)? |
| **12. Tiered Test Validity** | Do new tests verify real business/domain quality rather than defensive `chmod`/`symlink`/`ValueError` paranoia, silent-fallback assertions, production-script tampering, or doc-grepping? Do tests strictly isolate `MINDIE_DIAGNOSTICS_ROOT`, `MINDIE_DIAGNOSTICS_CONFIG`, and `$HOME` via `conftest.py` / temporary directories (zero pollution of host `~/.local`, `~/.config`, or system LaunchAgent/systemd services), while meeting Tier 0 (`<5s`) – Tier 3 budgets and live A2/A3 NPU rules? |
| **13. Agent-Native Code & Comments** | Are core modules concise (`< 800` lines for single-window `view_file` reads, no multi-layer subprocess trampolines) with a Module-Top Agent Invariant Header (`[Role]`, `[Invariants]`, `[Timeouts & Locks]`, `[Side-Effect Policy]`) in the first 30 lines? Do comments explain business invariants and hardware/protocol quirks (e.g., A3 dual-Die `Phy-ID`) rather than excusing defensive paranoia? |
| **14. Performance, Bounded Memory/VRAM & Spec Placement** | Is the memory working set strictly $O(\text{active state})$ rather than accumulating unbounded history or loading `>50MB` files into RAM (routine single-process peak `<= 512 MiB`, never `> 1 GiB` bloat)? Are hot-loop `deepcopy`/subprocesses/per-row commits eliminated and workers capped by both CPU and usable RAM? Is the control plane zero-weight/zero-device-context, with heavy compute/RAM/VRAM tasks declaring OS-agnostic resource expectations (`cpu`/`memory`/`vram`) matched against real Windows/macOS/Linux local vs. remote specs before launch? |
| **15. Auto-Update Readiness, Windows Zero-Popup Gate & LF Hygiene** | Do Windows Node.js children use `windowsHide: true` and Python children use `CREATE_NO_WINDOW`? Have the readiness and LF gates passed for the actual publication scope (`--release-repo <repository>` for independent releases, `--release-scope product` for product combinations, plus `--require-siblings --verify-local-hosts` as needed and `--verify-github-releases` for publication)? Does independent R6 check only the selected repositories' source versions and READMEs/LF, without forcing a main product bump, historical channel update or peer README edits? Reserve full synchronization for product combinations. |

When submitting a development PR, you must completely check and fill out [`.github/pull_request_template.md`](../.github/pull_request_template.md) in the PR description (including `## 变更摘要 (Summary)`, all checked items in `## 设计原则 Review (Pre-PR Checklist)` + concrete `自查结论与证据`, and `## 验证结果 (Verification)`). The CI gate workflow (`.github/workflows/pr-checklist.yml` + `.github/scripts/check_pr_checklist.py`) automatically validates every PR on open/edit/sync and blocks merge if any checklist item is unchecked or lacks substantive review and verification evidence.

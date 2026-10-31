# MindIE Agent

This repository owns product architecture, domain boundaries, and entry documentation (`docs/`).
Native Harness plugins live in `mindie-agent-codex`, `mindie-agent-cc`, `mindie-agent-kimi`, `mindie-agent-dsh`, and `mindie-agent-agy`.
Shared runtime components live in `knowledge`, `remote-dev`, `diagnostics`, `profiler`, `sim`, `npu-top`, and `coordinator`.

## 1. Core Operating Rules (Always Active)

- **Repository Boundary**: This repo contains documentation and architecture assets only—no runtime bootstrap, MCP server, client hook, Skill catalogue, or dependency lock. Do not add legacy VAWS aliases or alter the user's unrelated skills, plugins, or MCP configurations.
- **Inner-Loop Efficiency (Principle 1 — Total Cost First)**:
  - Edit files directly in the active checkout and verify only the affected scope.
  - Never invent intermediate freeze steps, duplicate snapshot directories, or `readback.json`/`restoration.json`/`shadow.json` audit ceremonies during routine development.
- **Transparency, No Silent Fallbacks & State Honesty (Principle 9 & 14)**:
  - Keep implementation status, target design, and real acceptance evidence distinct.
  - Errors must remain visible to the caller; distinguish `completed`, `failed`, and `unknown` external effects. Never mask a failure as `{}` / `"active"` / `exit 0`, never let `except OSError:` swallow `TimeoutError`, never overwrite a succeeded remote result with `isError=True` due to a local receipt-accounting timeout, and never blindly retry an uncertain external write.
- **Timeout Arithmetic & Anti Over-Defensive Programming (Principle 10 & 15 — Four Iron Rules)**:
  - Take core business logic correctness as the sole baseline; directly delete and rewrite unreasonable defensive imaginary-enemy checks, shadow state machines, and obsolete shims.
  - Enforce `outer_timeout >= sum(inner_budgets) + cleanup_grace` (e.g., `STOP_DRAIN >= STOP_GRACE + 3s`, verifier `outer_timeout >= inner_timeout + inventory_grace`, independent budgets for multi-stage SSH mux diagnostics, and never `timeout N cmd || cmd`), WAL + `3s–5s` SQLite timeouts, and bounded subprocess/handshake waits.
  - **Four Anti Over-Defensive Iron Rules**: (1) Lightweight SQLite connection (`open_database` sets WAL + `busy_timeout=5000` once; never run `.owner` `lstat` or `:memory:` schema reflection on every `SELECT`); (2) Reserve `unknown` receipts strictly for irreversible external writes, abolishing local one-way self-bricking (`suppressed` / permanent `fault` / `TaskRootBusy`); (3) No cross-repo copy-pasted `*_fallback.py`/`*_bootstrap.py` shadow state machines or `ctypes` Win32 ACL ceremonies (use `os.replace()`); (4) No `inspect.signature` internal parameter locks or giant inline Python string blobs (`REMOTE_FILE_PY` must be a standalone `.py` module).
- **Testing Design Guidelines (No Filler, Silent-Fallback, or Prose-Grep Tests; Standing Live A2/A3 NPU Tiered Verification)**:
  1. **Every Test Must Earn Its Keep**: Never write filler tests that merely check Python types/defensive `ValueError` branches, repeatedly test `chmod`/`symlink` hypotheticals, ratify silent error swallowing (`exit 0`/`{}` on failure), assert static constant/enum string lists, or regex-grep `README.md`/`SKILL.md` prose; never tamper with production scripts or fabricate `MagicMock` payloads that diverge from real server/hardware schemas to fake a pass.
  2. **Four-Tier Testing Pyramid (Tier 0 – Tier 3, Standing A2/A3 Ascend NPU Environment)**:
     - **Tier 0 (Pure In-Memory Core Logic Unit Tests, `< 5s`)**: Zero subprocesses, zero network, zero `sleep`; covers parsers (backed by real A2 910B / A3 910C / A5 hardware Golden Captures), state-machine transitions (`InMemoryHostQueue` and real in-memory loops), redaction rules, domain retrieval precision/recall, and protocol translation.
     - **Tier 1 (Local Component Contract & Process Boundary Tests, `< 15s`)**: Reuses session-scoped pre-built Git/SQLite templates to verify cross-process locks, `python -I` isolated startup, and millisecond injectable timeout cleanup (no in-test `pip install` or 10MB `fsync` barrages).
     - **Tier 2 (Standing A2/A3 NPU Non-Destructive Live Integration `@pytest.mark.live_npu`, `< 25s`)**: Connects directly to standing A2 (`173.125.1.2`) and A3 (`192.168.13.165` / `.156` / `.154`) clusters using isolated sandbox directories (e.g., `state_dir="/tmp/mindie-npu-test-<uuid>"`) without disturbing active workloads to verify live `npu-smi` probing, multi-Die `Phy-ID` mapping, Docker container pass-through, Linux `/proc` process-tree draining, and lease anti-preemption.
     - **Tier 3 (End-to-End Host CLI & `mindie-bench` Live Canary Acceptance, `< 90s`)**: Drives real host CLIs and `mindie-bench` Canary tasks for closed-loop verification.
- **Agent-Native Coding & Commenting Standards (Principle 17 — 100% Agent-Maintained Codebase)**:
  1. **Module Size & Context-Window Friendliness**: Keep core modules concise and cohesive (target `< 800` lines per file so a single `view_file` call loads the full module); ban 5–6 layer subprocess trampolines and pass-through wrappers.
  2. **Mandatory Module-Top Agent Invariant Header**: Every core module must declare `[Role]`, `[Invariants]`, `[Timeouts & Locks]`, and `[Side-Effect Policy]` within its first 30 lines.
  3. **Why & Invariants over Defensive Excuses**: Comments must explain business invariants, protocol boundaries, and non-obvious hardware behaviors (e.g., Ascend A3 dual-Die `Phy-ID` `0..15` mapping or Linux `/proc` container PID draining)—never restate literal code or rationalize imaginary-enemy defensive checks.
- **Performance, Bounded Memory/VRAM & Spec-Driven Local/Remote Placement (Principle 18)**:
  1. **Bounded Working Set ($O(\text{Active State})$) & `1 GiB` Redline**: Main loops in `sim`/`profiler`/`diagnostics` must never accumulate unbounded history across iterations/tokens or load `>50 MB` files via `json.load()`/`read()`. Routine control/analysis calls must stay `<= 512 MiB` peak (`> 1 GiB` single-process RAM outside LLM weights/C++ linking is a code bug). Cap workers by $\min(\text{CPU}, \lfloor\text{usable RAM}/\text{worker RAM}\rfloor)$.
  2. **Zero-Weight Control Plane & Pre-Flight VRAM Sizing**: Never load model weights or initialize `torch_npu`/CUDA/CANN contexts just to inspect metadata (`config.json`/`safetensors` headers only). Verify `vram_free_mb >= Expected VRAM` before launching device workloads.
  3. **Cross-Platform Spec Placement (Windows / macOS / Linux)**: Never hardcode `sys.platform == "darwin"` or `os.name == "nt"` to gate execution. Match workload expectations (`cpu_cores`, `memory_mb`, `vram_mb`) against real usable local and remote (`fleet_probe.py`) hardware specs—run locally when local specs are sufficient (including high-spec workstations), and route to matching remote servers when local specs are insufficient.

## 2. Progressive Disclosure Map (Read Only When Triggered)

Do not preload all documentation into context. Read only the document matching your current task:

- **Architecture & Domain Boundaries** → [`docs/architecture.md`](docs/architecture.md)
- **Product, Engineering & Testing Principles** → [`docs/design-principles.md`](docs/design-principles.md), [`docs/testing-architecture.md`](docs/testing-architecture.md) & [`docs/execution-resource-budget-design.md`](docs/execution-resource-budget-design.md)
- **Harness Plugin Boundary, Hooks & Lifecycle** → [`docs/harness-boundary-and-lifecycle.md`](docs/harness-boundary-and-lifecycle.md) & [`docs/native-runtime-reuse.md`](docs/native-runtime-reuse.md)
- **Knowledge Flywheel & Privacy Redaction** → [`docs/knowledge-system.md`](docs/knowledge-system.md)
- **Diagnostics, Profiling & Simulation** → [`docs/diagnostics-and-reporting.md`](docs/diagnostics-and-reporting.md), [`docs/profiler-system.md`](docs/profiler-system.md) & [`docs/simulation-system.md`](docs/simulation-system.md)
- **Gate — Submitting or Updating a Development PR**:
  - Read and complete [`docs/design-principles.md#三开发-pr-提交前自查清单pre-pr-review`](docs/design-principles.md#三开发-pr-提交前自查清单pre-pr-review) and [`.github/pull_request_template.md`](.github/pull_request_template.md) (including Item 14 on bounded memory/VRAM & cross-platform spec placement, plus Item 15 PR format hygiene: all repository text files must use Unix `LF` `\n` line endings—never Windows `CRLF` `\r\n`—verified via `python3 .github/scripts/check_lf_eol.py`) before creating/updating any PR (including drafts), and include the concise review summary in the PR description.
- **Gate — Publishing a Formal Component or Plugin Release**:
  - Read and execute [`docs/release-compatibility-and-update.md#组件与插件配套发布`](docs/release-compatibility-and-update.md#组件与插件配套发布) only when publishing or auditing a formal GitHub Release.

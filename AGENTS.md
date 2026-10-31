# MindIE Agent

This repository owns product architecture, domain boundaries, and entry documentation (`docs/`).
Native Harness plugins: `mindie-agent-codex`, `mindie-agent-cc`, `mindie-agent-kimi`, `mindie-agent-dsh`, `mindie-agent-agy`.
Shared runtime components: `knowledge`, `remote-dev`, `diagnostics`, `profiler`, `sim`, `npu-top`, `coordinator` (plus `mindie-bench`).

## 1. Core Operating Rules (Always Active)

- **Repository & Inner-Loop Boundary (Principle 1)**: This repo holds documentation, channel manifests (`channels/0.1.json`), and CI gates only—no runtime code or legacy VAWS aliases. Edit files directly in the active checkout and verify only the affected scope (no snapshot directories or `readback.json`/`shadow.json` audit ceremonies).
- **State Honesty & No Silent Fallbacks (Principle 9 & 14)**:
  - Distinguish `completed`, `failed`, and `unknown` external effects. Never mask failures as `{}` / `"active"` / `exit 0`, never let `except OSError:` swallow `TimeoutError` (always precede with `except TimeoutError: raise`), and never blindly replay an `unknown` external write.
  - **Receipt Honesty**: Once a primary remote/component operation succeeds, local receipt/bind accounting errors must keep `isError=False` and attach `receipt_warning` + `receipt_unconfirmed=True`.
- **Timeout Arithmetic & Anti Over-Defensive Iron Rules (Principle 10 & 15)**:
  - Enforce `outer_timeout >= sum(inner_budgets) + cleanup_grace` (e.g., MCP `660s >= 600s + 60s`, `STOP_DRAIN >= STOP_GRACE + 3s`), decouple process output buffer limits from MCP response truncation budgets, and never run `timeout N cmd || cmd`.
  - **Four Iron Rules**: (1) Configure SQLite WAL + `busy_timeout=5000` once in `open_database` (no per-query `.owner` `lstat` or `:memory:` reflection); (2) Reserve `unknown` strictly for irreversible external writes, banning one-way local self-bricking (`fault`/`suppressed`/`TaskRootBusy`); (3) No copy-pasted `*_fallback.py`/`*_bootstrap.py` shadow state machines or Win32 ACL ceremonies (use `os.replace()`); (4) No `inspect.signature` locks or giant inline Python string blobs.
- **Four-Tier Testing & Zero Host Pollution (Principle 16)**:
  - No filler/type/prose-grep tests or fabricated `MagicMock` hardware payloads. Isolate `MINDIE_CONFIG_HOME`, `MINDIE_DATA_HOME`, `MINDIE_DIAGNOSTICS_ROOT`, and `$HOME` in all tests.
  - **Tier 0 (`<5s`)**: Pure in-memory unit tests + Golden Captures; **Tier 1 (`<15s`)**: Local process/SQLite/Git boundary tests; **Tier 2 (`<25s`, `@pytest.mark.live_npu`)**: Non-destructive live A2 (`173.125.1.2`) & A3 (`192.168.13.165`/`.156`/`.154`) NPU integration; **Tier 3 (`<90s`)**: Live host CLI & `mindie-bench` Canary acceptance.
- **Agent-Native Modules & Bounded Resources (Principle 17 & 18)**:
  - Keep core modules `< 800` lines with a top-30-line `[Role]` / `[Invariants]` / `[Timeouts & Locks]` / `[Side-Effect Policy]` docstring header; comment *why* & hardware invariants (e.g., A3 dual-Die `Phy-ID 0..15`), never defensive excuses.
  - Keep working sets $O(\text{Active State})$ (`<= 512 MiB` control-plane peak; `> 1 GiB` is a bug), stream files `> 50 MB`, keep control paths zero-weight/zero-device-context, and place workloads by measured local/remote (`fleet_probe.py`) specs rather than hardcoded `sys.platform`.

## 2. Progressive Disclosure Map (Read Only When Triggered)

Do not preload all docs into context. Read only the reference matching your current task:

- **Historical Postmortems & Anti-Regression Guardrails (`P1–P7`)** → [`docs/historical-issues-and-guardrails.md`](docs/historical-issues-and-guardrails.md) *(Consult when touching auto-update, hooks, timeouts, receipts, C6 distillation, benchmarks, or A2/A3/A5 topology)*
- **Architecture & Domain Boundaries** → [`docs/architecture.md`](docs/architecture.md)
- **Engineering Principles, Testing & Resource Placement** → [`docs/design-principles.md`](docs/design-principles.md), [`docs/testing-architecture.md`](docs/testing-architecture.md) & [`docs/execution-resource-budget-design.md`](docs/execution-resource-budget-design.md)
- **Harness Plugin Lifecycle, Knowledge & Component Specs** → [`docs/harness-boundary-and-lifecycle.md`](docs/harness-boundary-and-lifecycle.md), [`docs/knowledge-system.md`](docs/knowledge-system.md), [`docs/diagnostics-and-reporting.md`](docs/diagnostics-and-reporting.md), [`docs/profiler-system.md`](docs/profiler-system.md) & [`docs/simulation-system.md`](docs/simulation-system.md)
- **Gate — Submitting or Updating a Development PR**:
  - Complete [`docs/design-principles.md#三开发-pr-提交前自查清单pre-pr-review`](docs/design-principles.md#三开发-pr-提交前自查清单pre-pr-review) and [`.github/pull_request_template.md`](.github/pull_request_template.md), and verify Unix `LF` (`\n`) line endings via `python3 .github/scripts/check_lf_eol.py`.
- **Gate — Publishing a Component, Corpus, or Plugin Release (Mandatory `R1–R6` Checklist)**:
  - Read [`docs/release-compatibility-and-update.md#组件与插件配套发布`](docs/release-compatibility-and-update.md#组件与插件配套发布) and **mandatorily pass all 6 checklist items (`R1–R6`)** before and after any release or [`channels/0.1.json`](channels/0.1.json) update:
    ```bash
    # Default flexible component/corpus release (no plugin republish needed; add --strict-lockstep when republishing plugins):
    python3 .github/scripts/check_auto_update_readiness.py --require-siblings --verify-local-hosts --verify-github-releases
    ```

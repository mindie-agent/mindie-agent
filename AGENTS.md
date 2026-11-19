# MindIE Agent

This repository is the **top-level product hub** owning system architecture, domain routing boundaries, living bilingual specifications (`docs/`), release channel manifests (`channels/0.1.json`), and stdlib cross-repo CI gates (`.github/scripts/`). It contains **no runtime business code or host adapters**.

## 1. Sibling Repository Routing & Worktree Handoff (Read First on Code Requests)

Contributors often clone only `mindie-agent` first and ask an AI agent to implement a feature or fix a bug. Route every change to its single-owner repository and **never place runtime code inside `mindie-agent`**:

| Class (`--profile`) | Repositories (`github.com/mindie-agent/<repo>`) | Owned Scope |
| --- | --- | --- |
| **Hub (`hub`)** | `mindie-agent` *(this repo)* | Product architecture, living specs (`docs/`), `docs/archive/` & `docs/releases/`, `channels/0.1.json`, cross-repo gates |
| **Shared Substrate (`harness`)** | `harness` (`mindie-harness` / `mindie_harness`) | Shared substrate for all 7 host plugins: windowless process & nested Win32 Job supervision, deterministic Seed (`mindie-harness-seed.pyz`), `Active + Rollback` `.inuse` generation GC, concurrent zero-binding MCP gateway (`P2.7` / `P2.8`), and single-state `ExperimentLedger` `rsi` optimization loop |
| **Host Plugins (`host-plugin`)** | `mindie-agent-codex`, `mindie-agent-cc`, `mindie-agent-kimi`, `mindie-agent-dsh`, `mindie-agent-agy`, `mindie-agent-wb`, `mindie-agent-oc` | Thin native host wire manifests, hooks/plugin shims, host transcript redaction adapters, and version pins delegating runtime/MCP execution to `mindie-harness` |
| **Control Plane (`control-plane`)** | `remote-dev`, `coordinator` | `remote-dev`: SSH file/exec/patch, `~/.mindie/ssh/id_ed25519` fallback, safety guard, handle-addressed background jobs; `coordinator`: Ascend host/container inventory, `mindie_probe` (A2/A3 dual-Die/A5), `HostQueue` HBM/compile leases (`mindie_lease`), managed task execution |
| **State Services (`state-service`)** | `knowledge`, `diagnostics`, `npu-top` | `knowledge`: pure `L1–L4` graded units, info-gap retrieval, batch `refs` (`known_refs` + `token_budget`), 2-layer redaction, C6 distillation & PR publishing; `diagnostics`: CANN/`plog` root-cause analysis, 4×1 MiB JSONL rotation, redacted bundles, Scale-to-Zero opt-in GitHub reporting (`7d` `pending` expiry); `npu-top`: loopback Web (`127.0.0.1:8788`)/TUI/CLI/MCP fleet dashboard & 90-day SQLite history |
| **Device Tools (`device-tool`)** | `debugger`, `profiler`, `sim` | `debugger`: zero-device-context `npu_fault_triage`, 3-primitive `precision` localization, `aclgraph` replay/guard; `profiler`: controlled `msprof` capture, in-place SQLite/trace analysis & 3-state topology alignment; `sim`: 5-layer causal performance modeling, `compose`, 4D efficiency & SLA/PD Pareto solvers |
| **Evaluation (`bench`)** | `mindie-bench` | 20 live NPU behavioral-oracle tasks (109 3-state/helper controls), Gate Runner, isolated host runs, component benchmarks |
| **Corpora (`corpus`)** | `knowledge-vllm-ascend`, `knowledge-xllm`, `knowledge-mindie-sd`, `knowledge-operators`, `knowledge-infer-core`, `knowledge-infer-distributed`, `knowledge-infer-observability`, `knowledge-infer-ops-compat`, `knowledge-agent-engineering` | Public `mindie-graded-unit/1` (`L1–L4`) Ascend domain knowledge corpora (plus community repos `awesome-mindie-skills` & `vllm-ascend-workspace`) |

### Routing & Linked-Worktree Execution Protocol
1. **Canonical Flat Sibling + Worktree Layout**: Keep base checkouts as flat siblings (`../<repo>`) and create isolated feature worktrees under `../.worktrees/<repo>-<topic>`:
   ```bash
   # Lazy-clone missing target repo on demand, then create an isolated worktree
   [ -d ../<repo>/.git ] || git clone --filter=blob:none https://github.com/mindie-agent/<repo>.git ../<repo>
   git -C ../<repo> worktree add ../.worktrees/<repo>-<topic> -b feat/<topic>
   ```
2. **Sandboxed Agent Write Access**:
   - **Codex CLI**: Launch with `codex -C mindie-agent --add-dir ../<repo> --add-dir ../.worktrees/<repo>-<topic>`. **Both directories are required** because a linked Git worktree's `.git` file points back to `../<repo>/.git/worktrees/<repo>-<topic>` (`commondir`), so `git add` / `git commit` inside the worktree writes refs/objects under `../<repo>/.git`.
   - **Claude Code / Multi-Root IDEs (Antigravity, WorkBuddy, OpenCode, Kimi, DSH)**: Add both `../<repo>` and `../.worktrees/<repo>-<topic>` to the workspace (`--add-dir`), or relaunch directly rooted at `../.worktrees/<repo>-<topic>`.
   - **Honest Read-Only Fallback**: If the active sandbox denies writes outside `mindie-agent`, inspect read-only and give the user the exact one-line relaunch command above—never dump sibling source files into `mindie-agent`.
3. **Immediate Handoff & Scoped-Worker Boundary**: Once inside `../<repo>` or `../.worktrees/<repo>-<topic>`, **immediately read its local `AGENTS.md` and `CONTRIBUTING.md`** and run its own tests and checklist profile. When running as a scoped multi-agent worker (`/joint-dev`, swarms, subagents) whose prompt restricts file ownership, stay strictly within your assigned files, delete obsolete code inside that scope, and report any out-of-scope doc/contract deltas (`target doc + section`, `old claim -> replacement`, `source/test`) in your handoff summary for the docs pass.

## 2. Core Operating Rules (Always Active)

- **Repository, Subtraction & Living-Doc Boundary (Principles 1, 8 & 10)**: Edit files directly in the active checkout/worktree and verify the affected scope—zero snapshot directories or `readback.json`/`shadow.json` audit ceremonies. Every merge-ready PR deletes superseded code and orphan `.py` modules directly (`*_legacy`/`*_old`/`*_backup`/`*_fallback` and coexisting `*_copy` shadow files are unconditionally banned; coexisting `<base>_v<N>.py` multi-version modules such as `fia_v1.py`..`fia_v4.py` are permitted ONLY when actively imported and declaring a distinct, AST-grounded `Upstream-ABI: <symbol>` like `Upstream-ABI: aclnnFusedInferAttentionScoreV2` in their top module header) and keeps active living docs (`AGENTS.md`, `README*`, `CONTRIBUTING*`, `docs/`, with matching `##` H2 section counts across bilingual `.md` <-> `.en.md` pairs) synchronized. Keep `docs/releases/**` and channel-referenced `docs/audits/**` immutable; archive superseded plans/reviews via `git mv` into `docs/archive/` with a 4-line provenance banner.
- **Task Continuity & Native Escape Routes (Principles 1–2)**: Helpers remain optional. Continue within user authorization via existing CLIs, native shell/SSH, or task-local scripts while preserving original failures, confirmed facts, and endpoint/job ownership; reconcile uncertain external writes before replacement. See [`docs/source-rebuild-contract.md`](docs/source-rebuild-contract.md).
- **State & Receipt Honesty (Principles 9 & 14)**: Distinguish `completed`, `failed`, and `unknown` external effects. Never mask failures as `{}` / `"active"` / `exit 0`, and always precede `except OSError:` with `except TimeoutError: raise`. Once a primary remote/component operation succeeds, local receipt/bind accounting errors keep `isError=False` and attach `receipt_warning` + `receipt_unconfirmed=True`.
- **Timeout Arithmetic & Five Iron Rules (Principles 10 & 15)**:
  - Enforce `outer_timeout >= sum(inner_budgets) + cleanup_grace` (e.g., MCP `660s >= 600s + 60s`), decouple process output spool limits from MCP truncation caps, and never run `timeout N cmd || cmd`.
  - **Five Iron Rules**: (1) Configure SQLite WAL + `busy_timeout=5000` once in `open_database` (never on read-only checks when absent, never on WSL2 DrvFS); (2) Reserve `unknown` strictly for irreversible external writes—zero local one-way self-bricking (`needs_repair`/`fault`/`suppressed`/`TaskRootBusy`); (3) No copy-pasted `*_fallback.py`/`*_bootstrap.py` shadow state machines or Win32 ACL ceremonies (use `os.replace()`); (4) No `inspect.signature` locks or giant inline Python `-c` blobs; (5) **Zero Pre-Call Session-Binding Gates & Silent Default-On Across All 7 Hosts (`P2.7` / `P2.8`)**: Standard MCP `tools/call` with zero `_meta`, zero prior hooks, and zero required `request_nonce`/`_mindie_bind_id`/`context_file` MUST suffice across all single-user tools (`remote-dev`, `coordinator`, `profiler`, `sim`, `debugger`, `diagnostics`, `npu-top`, AND `knowledge_*`) with silent default-on `SKILL.md` routing (zero `/mindie-agent` user activation command or `disable-model-invocation` block, and install/onboarding docs strictly in `docs/install/` outside runtime `skills/`), reserving user consent + authorized `project_roots` strictly for `Stop` capture / outbound GitHub exports and `HostQueue` leases (`lease_id` + `fence_token`) for physical NPU/port exclusivity.
- **Four-Tier Testing & Zero Host Pollution (Principle 16)**: Isolate `HOME`, `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `XDG_*`, `MINDIE_CONFIG_HOME`, `MINDIE_DATA_HOME`, `MINDIE_DIAGNOSTICS_ROOT`, `REMOTE_DEV_AUTH_DIR`, `UV_CACHE_DIR`, and `TMPDIR` in all tests. **Tier 0 (`<5s`)**: in-memory + Golden Captures; **Tier 1 (`<15s`)**: local process/SQLite/Git; **Tier 2 (`<25s`, `@pytest.mark.live_npu`)**: live A2/A3 NPU integration; **Tier 3 (`<90s`)**: live host CLI & `mindie-bench` Canary.
- **Agent-Native Modules, Bounded Resources & `P8` Storage (Principles 17 & 18)**: Keep core modules `< 800` lines with a top-30-line `[Role]` / `[Invariants]` / `[Timeouts & Locks]` / `[Side-Effect Policy]` docstring header. Keep control-plane working sets $O(\text{Active State})$ (`<= 512 MiB` peak, zero weight/device context), stream files `> 50 MB`, retain at most `Active + Rollback` (`<= 2`) runtime generations via `.inuse` leases + `.trash/` retirement, pair every manual tempfile with cleanup, and never call unguarded `os.kill(pid, 0)` or window-popping spawns on Windows.

## 3. Progressive Disclosure Map & Gates

Read only the reference triggered by your current task:

- **Historical Postmortems & Guardrails (`P1–P8`)** → [`docs/historical-issues-and-guardrails.md`](docs/historical-issues-and-guardrails.md)
- **Architecture & Domain Boundaries** → [`docs/architecture.md`](docs/architecture.md)
- **Engineering Principles, Testing & Resource Budgets** → [`docs/design-principles.md`](docs/design-principles.md), [`docs/testing-architecture.md`](docs/testing-architecture.md) & [`docs/execution-resource-budget-design.md`](docs/execution-resource-budget-design.md)
- **Harness Substrate, Knowledge & Component Specs** → [`docs/harness-boundary-and-lifecycle.md`](docs/harness-boundary-and-lifecycle.md), [`docs/knowledge-system.md`](docs/knowledge-system.md), [`docs/diagnostics-and-reporting.md`](docs/diagnostics-and-reporting.md), [`docs/profiler-system.md`](docs/profiler-system.md) & [`docs/simulation-system.md`](docs/simulation-system.md)
- **Source Rebuilds & Historical Archive** → [`docs/source-rebuild-contract.md`](docs/source-rebuild-contract.md) & [`docs/archive/README.md`](docs/archive/README.md)
- **Gate — Hub Development PR (`--profile hub`)**:
  ```bash
  python3 .github/scripts/check_lf_eol.py
  python3 .github/scripts/code_doc_hygiene_gate.py --main-repo .
  python3 -m unittest discover -s .github/scripts/tests -p 'test_*.py' -v
  python3 .github/scripts/check_pr_checklist.py --profile hub --body-file <pr_body.md>
  ```
- **Gate — Component, Corpus, or Product Release (`R1–R6` — see [`docs/release-compatibility-and-update.md`](docs/release-compatibility-and-update.md))**:
  ```bash
  # Independent release (supports flat siblings, --siblings-root ../.worktrees, or --repo name=/abs/path):
  python3 .github/scripts/check_auto_update_readiness.py --release-repo harness --require-siblings --verify-local-hosts --verify-github-releases

  # Product combination release / channels/0.1.json update (explicitly synchronizes managed docs):
  python3 .github/scripts/sync_org_versions.py --release-scope product --write
  python3 .github/scripts/check_auto_update_readiness.py --release-scope product --require-siblings --verify-local-hosts --verify-github-releases
  ```

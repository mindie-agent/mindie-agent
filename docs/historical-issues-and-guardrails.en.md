# Historical Postmortems and Guardrails (`0.0.1 → 0.1.6`)

[中文](historical-issues-and-guardrails.md) · [Documentation Hub](README.en.md) · [Design Principles](design-principles.en.md) · [Release Compatibility & Auto-Update](release-compatibility-and-update.en.md)

This document systematically catalogs real production and acceptance defects encountered across MindIE Agent versions `0.0.1` through `0.1.6`. Every historical issue is organized into **seven root-cause domains (`P1–P7`)** using a four-part structure: **Symptom & Version Origin → Root Cause → Hard Engineering Invariant → Automated Guardrail**. Routine tasks do not need to preload this entire catalog; consult the relevant domain when modifying the corresponding subsystem or running release gates.

---

## 1. Overview of the Seven Historical Issue Domains

| ID | Domain | Affected Components / Repos | Automated Guardrails |
| --- | --- | --- | --- |
| **`P1`** | **Auto-Update, Flexible Component Upgrades & Release Gates** | `knowledge` · 5 Host Plugins · `channels/0.1.json` | `check_auto_update_readiness.py` (`R1–R6`) · `publication_check.py` |
| **`P2`** | **Native Harness Lifecycle, Session Admission & Cross-Platform Paths** | `codex` · `cc` · `kimi` · `dsh` · `agy` · `remote-dev` | Plugin Tier 0/1 lifecycle contract tests · `conftest.py` sandbox isolation |
| **`P3`** | **Timeout Arithmetic, Output Truncation & Stream Cleanup Races** | `remote-dev` · `dsh` · `mindie-bench` · Host MCPs | `outer >= sum(inner) + grace` contract tests · stream shutdown tests |
| **`P4`** | **State Honesty, Receipt Accounting & No Silent Fallbacks** | `remote-dev` · `coordinator` · `diagnostics` · Host Plugins | Receipt Honesty unit tests · Four Anti-Over-Defensive Iron Rules |
| **`P5`** | **Knowledge Budgeting, Deduplicated Delivery & C6 Distillation** | `knowledge` · `knowledge-*` corpora · 5 Host Plugins | `WHOLE_DELIVERY_SCOPE` budget tests · C6 Strict Schema validation |
| **`P6`** | **Benchmark Soundness, Behavioral Verifiers & Live NPU Anti-Preemption** | `mindie-bench` (`G0–G5`) · `RemoteSlot` · `WorktreeSlot` | 4-way Verifier Soundness gate · `foreign_pids` physical observation |
| **`P7`** | **Bounded Memory/VRAM & Ascend A2/A3/A5 Topology Modeling** | `profiler` · `sim` · `coordinator` · `npu-top` · `remote-dev` | `<= 512 MiB` peak RAM redline · A3 dual-Die `Phy-ID 0..15` live NPU tests |

---

## 2. Domain Postmortems & Hard Engineering Invariants

### `P1`: Auto-Update, Flexible Component Upgrades & Release Gates (`0.1.1 → 0.1.6`)

| Incident & Version | Symptom & Root Cause | Hard Engineering Invariant | Automated Guardrail |
| --- | --- | --- | --- |
| **P1.1 Modified knowledge unit body without incrementing `revision`**<br>(`0.1.5 → 0.1.6`, `knowledge-vllm-ascend`) | Updating `unit-ascend-cann-known-limitations-and-env-toggles.md` updated `content_sha256` in `routing-manifest.json` while leaving `revision: 1`, causing client `GradedRepository.install_feed()` to reject the feed sync. | Never modify a graded unit's body (`content_sha256` change) without incrementing `revision`; never rely on manual edits alone. | 1. `build_routing_index()` auto-increments `revision` when `content_sha256` changes;<br>2. `publication_check.py` blocks unadvanced revisions;<br>3. `check_auto_update_readiness.py` (`R2`) scans all 7 `knowledge-*` repos from channel commit to `HEAD`. |
| **P1.2 Host CLI auto-upgrade exceeded `harness-compatibility.json` upper bound**<br>(`0.1.4` Codex `0.165.0-alpha.1.2`, `0.1.6` Codex `0.166.0-alpha.5.1`) | ChatGPT Desktop auto-upgraded its bundled `codex-cli` past the declared `supported` interval in `harness-compatibility.json`, causing background updates to return `"no_compatible_release"`. | Always verify compatibility ranges against locally installed host CLIs (including bundled Desktop binaries) before release. | `check_auto_update_readiness.py --verify-local-hosts` (`R5`) probes installed `codex` (CLI + ChatGPT Desktop), `claude`, and `kimi` binaries against `supports_harness()`. |
| **P1.3 Plugin update downgraded independently updated components back to bootstrap pins**<br>(`0.1.4` Kimi `0.1.8 → 0.1.9`) | Legacy updater treated source bootstrap pins as installed truth, downgrading `knowledge 0.13.6 / remote-dev 0.11.1` to `0.13.3 / 0.10.6`. | Component selection must monotonically enforce `max(installed, plugin_baseline, latest_formal_release)` using `runtime_inventory.py` readback. | All 5 host plugins use `component_update.py` + `mindie_knowledge.component_runtime.discover/build`; `check_auto_update_readiness.py` (`R4`) enforces `plugin_baseline <= channel_component`. |
| **P1.4 Stale static MCP catalog & missing GitHub Release assets**<br>(`0.1.6` Codex `mcp_catalog.json`, `mindie-agent-agy v0.1.1`) | Bumping component pins without running `export_catalog.py` broke CI contract checks; manual `gh release create` omitted `mindie-plugin-release.json` and `SHA256SUMS`. | Regenerate static catalogs on schema/pin changes; every formal GitHub Release must publish verified assets and `SHA256SUMS`. | `check_auto_update_readiness.py --verify-github-releases` (`R3`) verifies live GitHub Release status, tag SHAs, and `SHA256SUMS`. |

---

### `P2`: Native Harness Lifecycle, Session Admission & Cross-Platform Paths (`0.1.1 → 0.1.5`)

| Incident & Version | Symptom & Root Cause | Hard Engineering Invariant | Automated Guardrail |
| --- | --- | --- | --- |
| **P2.1 Implicit knowledge activation polluting ordinary sessions**<br>(`0.0.2 → 0.1.1`) | Exposing knowledge tools or Skill bodies by default polluted unrelated coding sessions and triggered background services unexpectedly. | **Passive Default**: deterministic tools (`remote-dev`, `profiler`, `sim`, `coordinator`, `diagnostics`) are always available; `knowledge_*` and capture require explicit `/mindie-agent` in the active session (never inherited by new sessions, forks, or subagents). | Tier 0/1 lifecycle tests across all 5 host plugins. |
| **P2.2 Antigravity `hooks.json` root path & `Stop` infinite continuation**<br>(`0.1.5` `mindie-agent-agy`) | Antigravity loads `hooks.json` from the plugin root (`plugins/mindie-agent/hooks.json`), not `hooks/hooks.json`; returning `"decision": "continue"` from `Stop` forces infinite turns. | Place `hooks.json` at plugin root for AGY; `Stop` hooks must return `{}` and never return `"decision": "continue"`. | `mindie-agent-agy/tests/test_agy_plugin.py` and `test_agy_lifecycle.py`. |
| **P2.3 Windows Git Bash `ucrt64/bin` SSH lookup & probe host pollution**<br>(`0.1.2` `remote-dev 0.11.1`, `0.1.4` CC probe) | Git for Windows 2.56.0 places `git.exe` in `Git/ucrt64/bin` while `ssh.exe` lives in `Git/usr/bin`; a migration probe missing isolated env vars initialized a second default profile. | Resolve `usr/bin/ssh.exe` relative to the Git installation root; isolate `MINDIE_CONFIG_HOME`, `MINDIE_DATA_HOME`, and `MINDIE_DIAGNOSTICS_ROOT` in all tests and probes. | Windows PowerShell + Git Bash PATH live SSH tests; `conftest.py` sandbox fixtures. |

---

### `P3`: Timeout Arithmetic, Output Truncation & Stream Cleanup Races (`0.1.1 → 0.1.4`)

| Incident & Version | Symptom & Root Cause | Hard Engineering Invariant | Automated Guardrail |
| --- | --- | --- | --- |
| **P3.1 Response truncation budget killed still-running command**<br>(`0.1.4` DSH `v0.1.8 → v0.1.9`) | Killing a running subprocess as soon as its stdout exceeded the MCP response budget turned expected exit code `3` into `-9`. | Decouple execution output buffer limits from MCP response truncation budgets; let commands finish within their timeout budget to preserve real exit codes. | Large-output exit-code preservation unit tests across host plugins. |
| **P3.2 Outer timeout smaller than inner budgets + drain grace**<br>(`0.1.0 → 0.1.3`) | Outer MCP timeouts cut off long remote waits (`600s`) or `SIGTERM -> SIGKILL` drain windows prematurely. | Enforce `outer_timeout >= sum(inner_budgets) + cleanup_grace` (e.g., `660s >= 600s + 60s`, `STOP_DRAIN >= STOP_GRACE + 3s`); never use `timeout N cmd \|\| cmd`. | Timeout arithmetic unit tests and Pre-PR Checklist Item 10. |
| **P3.3 Cleanup exception masking primary error & cross-thread `close()` race**<br>(`0.1.1` `remote-dev #43`, `mindie-bench 0.4.4`) | `LocalForward.__exit__` overwrote primary exceptions; calling `HTTPResponse.close()` from a timeout thread nulled `fp` during `read1()` in Python 3.13. | Attach cleanup errors via `record_cleanup_failure(primary, cleanup)`; interrupt blocking sockets across threads via `shutdown(SHUT_RDWR)` only; precede `except OSError:` with `except TimeoutError: raise`. | `remote-dev` cleanup fault-injection tests; `mindie-bench` `HTTP/1.1 chunked` interleaved close regression test. |

---

### `P4`: State Honesty, Receipt Accounting & No Silent Fallbacks (`0.1.1 → 0.1.5`)

| Incident & Version | Symptom & Root Cause | Hard Engineering Invariant | Automated Guardrail |
| --- | --- | --- | --- |
| **P4.1 Remote success overwritten as `isError=True` on local receipt timeout**<br>(`0.1.2 → 0.1.5`) | Local SQLite lock contention after a completed remote call flipped `isError` to `True`, causing the agent to replay completed remote mutations. | **Receipt Honesty Invariant**: once the primary operation succeeds, local receipt/bind accounting errors must keep `isError=False` and attach `receipt_warning` + `receipt_unconfirmed=True`. | `test_*_receipt_honesty` fault-injection tests across all 5 plugins. |
| **P4.2 Local `NameError` recorded as remote `unknown` or permanent local `fault`**<br>(`0.1.1` `coordinator #63`) | Missing import turned a local `NameError` into `state="uncertain"`; legacy local state machines permanently bricked workspaces with one-way `fault`/`suppressed` states. | Reserve `unknown` strictly for irreversible external writes that crossed a process/network boundary; ban one-way local self-bricking states. | `coordinator` preparation refresh tests and Anti-Over-Defensive Iron Rule 2. |
| **P4.3 Missing endpoint parameter (`port`) flattened into generic error**<br>(`0.1.1 → 0.1.2` `remote-dev 0.10.8`) | Omitting `port` on direct SSH calls returned an opaque error string, preventing model self-correction. | Unsent local caller validation errors must return structured `input_repair.missing/action` and document endpoint rules in tool schemas. | `remote-dev` caller input repair unit and live acceptance tests. |

---

### `P5`: Knowledge Budgeting, Deduplicated Delivery & C6 Distillation (`0.1.1 → 0.1.5`)

| Incident & Version | Symptom & Root Cause | Hard Engineering Invariant | Automated Guardrail |
| --- | --- | --- | --- |
| **P5.1 Plugin re-trimming exploration payloads & cursor invalidation**<br>(`0.1.1` `knowledge #97/#99/#100`) | Host plugins stripped L3 units or rebuilt fact packs after engine budgeting; dropping preview references invalidated `related_next` pagination cursors. | `mindie-knowledge` is the sole owner of `WHOLE_DELIVERY_SCOPE` budgeting and single-transaction deduplicated delivery accounting; plugins pass payloads through unchanged; navigation trimming sets `excerpt_omitted=True` without dropping references. | `knowledge` whole-delivery budget, cursor reachability, and deduplicated accounting tests. |
| **P5.2 C6 related-unit budget starvation, `"unknown"` conditions & Strict Schema 400**<br>(`0.1.5`) | Related units starved candidate body budgets; placeholder `"unknown"` conditions caused `condition_mismatch`; missing nested `additionalProperties: false` triggered OpenAI HTTP 400. | Use dedicated `RELATED_BODY_BUDGET_BYTES = 12_000`; strip `"unknown"`/`"n/a"` placeholder conditions; enforce recursive Strict JSON Schema validation (`additionalProperties: false` and full `required`). | `knowledge` C6 budget/condition tests and `mindie-agent-codex` Strict Schema validator tests. |

---

### `P6`: Benchmark Soundness, Behavioral Verifiers & Live NPU Anti-Preemption (`0.1.0 → 0.1.5`)

| Incident & Version | Symptom & Root Cause | Hard Engineering Invariant | Automated Guardrail |
| --- | --- | --- | --- |
| **P6.1 Non-behavioral verifiers & synthesized continuation costs**<br>(`0.1.0 → 0.1.1` `mindie-bench #24/#25/#26`) | Six early task verifiers did not execute real target behavior; unexecuted strategy continuations synthesized duration/cost numbers. | Every verifier must execute real target code and pass 4-way soundness (`before_reward=0`, `after_reward=1`, `model_calls=0`, constant/no-op negative control fail); unexecuted continuations must stay `not_executed` with `None` cost. | `mindie-bench` Verifier Soundness gate. |
| **P6.2 `G1` corpus leakage, `WorktreeSlot` flock self-deadlock & prompt distortion**<br>(`0.1.5`) | `G1` mounted non-empty corpora; `WorktreeSlot.cleanup()` re-locked an already held `flock`; prompts contained unnatural step-by-step hints. | `G1` must physically isolate an empty corpus (`0` units); `cleanup()` must be idempotent without re-locking; benchmark prompts must mirror real developer reports (one-line symptom + raw stack trace/log path). | `mindie-bench` `G0–G5` gate tests and `WorktreeSlot` cleanup tests. |
| **P6.3 Shared live NPU preemption by external workloads**<br>(`0.1.5` L3 `192.168.13.156`) | External 16-Die `VLLMWorker` processes occupied benchmark dies mid-run on a shared A3 host. | Detect external `foreign_pids` via `physical_observation` and record `unknown` or `infra_failed` honestly—never kill foreign processes or fabricate pass rewards. | `RemoteSlot` and `physical_observation` foreign-PID isolation tests. |

---

### `P7`: Bounded Memory/VRAM & Ascend A2/A3/A5 Topology Modeling (`0.1.1 → 0.1.5`)

| Incident & Version | Symptom & Root Cause | Hard Engineering Invariant | Automated Guardrail |
| --- | --- | --- | --- |
| **P7.1 Unbounded large-file reads & per-query SQLite schema reflection**<br>(`0.1.3` `profiler 0.5.1`) | Reading large `.so` or `>50 MB` traces into memory caused RAM spikes; per-`SELECT` `.owner` `lstat` or `:memory:` reflection slowed hot paths. | Stream files `>50 MB` (`hashlib.file_digest`, JSONL iteration, SQLite indexes); keep control-plane single-process peak `<= 512 MiB` (`>1 GiB` is a bug); configure SQLite WAL + `busy_timeout=5000` once in `open_database`. | `profiler` streaming digest tests and Pre-PR Checklist Items 11 & 14. |
| **P7.2 Ascend A3 910C dual-Die `Phy-ID 0..15` & free HBM miscalculation**<br>(`0.1.1` `remote-dev #44`, `coordinator #64`) | Card-level stats overwrote dual-Die A3 occupancy, or fixed `2–3 GiB` deductions replaced measured `hbm_total_mb - hbm_used_mb`. | Count A3 capacity by independently leasable physical dies (`8 NPU × 2 Die = Phy-ID 0..15`) and measured `hbm_total_mb - hbm_used_mb` on non-busy dies; keep control plane zero-weight and zero-device-context. | Standing A2/A3 live NPU integration tests (`@pytest.mark.live_npu`). |

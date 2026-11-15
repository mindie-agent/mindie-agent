# 0.1.1 Engineering Reproduction & Knowledge-Evolution (G5) Dev Pilot Report

[中文](https://github.com/mindie-agent/mindie-agent/blob/v0.1.1/docs/releases/0.1.1/benchmark-pilot.md) · [0.1.1 Release Notes](../0.1.1.en.md) · [Pilot Evidence (`benchmark-pilot.json`)](benchmark-pilot.json) · [4-Host Native Update Acceptance (`native-update-acceptance.json`)](native-update-acceptance.json)

This report documents the offline CPU engineering reproduction pilot and the `G5` (`X-04` candidate protocol) knowledge-evolution experiment conducted during the `mindie-agent 0.1.1` maintenance patch cycle (machine-readable evidence in [`benchmark-pilot.json`](benchmark-pilot.json), `schema: "mindie-patch-dev-pilot-evidence/1"`). The pilot evaluates behavior-executed task verifiers, short vague user prompts, proxy gateway streaming settlement, and native session capture admission under live model calls. **It is a descriptive engineering pilot (`repetitions = 1`), not a statistical benefit proof and not a re-execution or rejudgment of the 109 historical `0.1.0` trials.**

---

## 1. Problem Statement & Evidence Boundaries

1. **Historical `0.1.0` Quantitative Benefit Claims Remain Suspended**:
   - During the 2026-10-24 benchmark audit, we found that 6 historical task verifiers could be satisfied by nonfunctional source edits and that the legacy default continuation executor in the strategy-selection pilot synthesized continuation outcomes from private judge answers. Although `mindie-bench 0.4.3 / 0.4.4` upgraded those 6 verifiers to execute real behavioral checks, the 109 historical `0.1.0` trials have not been re-executed or rejudged. Historical quantitative speedup and solve-rate claims therefore remain suspended, and **this report does not claim that the 18-task `0.1.0` value suite has been re-verified**.
2. **Relationship Between the `0.1.1` Patch Gate and This Dev Pilot**:
   - The `mindie-agent 0.1.1` patch uses the `release-kind=patch` release pipeline gate: all 12 code repositories' formal GitHub Releases, immutable tag commit SHAs, per-repository `mindie-release-benchmark/2` component benchmark reports (`release_gate = true`, `blocking_reasons = []`), SHA-256 checksums, and exact alignment between [`channels/0.1.json`](../../../channels/0.1.json) and `benchmark-manifest.json` have passed preflight verification, and formal `0.1.2` native update & session-gate acceptance across all four host plugins is recorded separately in [`native-update-acceptance.json`](native-update-acceptance.json).
   - Distinct from that 12-repository component gate, this report records a single-repetition (`repetitions = 1`) offline CPU engineering reproduction pilot on exposed development tasks (`scope = "exposed_dev_offline_engineering_reproductions"`, `inference_scope = "descriptive_pilot_no_statistical_benefit_claim"`).

---

## 2. Experimental Scope, Study Objects & Task Source Classification (`source_class`)

### 1. Host Cohorts & Study Object Boundaries

Two separate host cohorts were executed (never pooled, and switching cohorts is not represented as a seamless fallback completion of the original run):

| Cohort Group | Host Client & Model Configuration | Runner & Pinned Native Plugin / Runtime Components | Scope Covered |
| --- | --- | --- | --- |
| **Cohort 1 (Codex G0 Canary)**<br/>`maintenance-codex`<br/>`maintenance-codex-v2` | OpenAI Codex CLI `0.153.4`<br/>`home/codex/gpt-6.1-sol (xhigh)` | `mindie-bench 0.4.3` (`eb49b2e0a36184c1216b13b7f0a0ba88b8a26ece`) | `G0` only (no MindIE knowledge tools); exposed the `0.4.3` `HTTP/1.1 chunked` cross-thread settlement close race |
| **Cohort 2 (DSH Maintenance & G5 Pilot)**<br/>`maintenance-dsh-044`<br/>`maintenance-dsh-044-native-path`<br/>`g5-dsh-044` .. `v4-long-training` | DeepSeek Harness `0.2.0-rc.2`<br/>`deepseek-flash` (`reasoning_effort: "max"`)<br/>16 GiB RAM host (~`5.1 GiB` usable free+inactive memory, `max_parallel_native_agents = 2`, `weights_loaded = false`, `npu_context_created = false`) | Pinned to the formally published native plugin **`mindie-agent-dsh 0.1.1`** (`fc29535161c0d9e57c558c250bbb9101c0da55ce`, including its `0.1.1` `C6` organizer source) paired with the locked runtime (`runtime_lock_sha256: a466c966...`) of 8 formal shared/evaluation components: `mindie-knowledge 0.13.3` (`38a42f6f...`), `remote-dev 0.10.6` (`0463a13f...`), `mindie-diagnostics 0.5.2` (`801a01b2...`), `mindie-profiler 0.5.0` (`4010d72f...`), `mindie-sim 0.7.1` (`15f93f3f...`), `npu-top 0.2.1` (`6737925d...`), `mindie-coordinator 0.6.3` (`0ec71fb9...`), and `mindie-bench 0.4.4` (`a36d8a5a...`). Study corpora: maintenance `ascend` `335c3933...` + `operators` `6f083f81...`; G5 `ascend` `25b06b94...` + `operators` `6f083f81...` | 3 maintenance fixture tasks (`G0 / G1 / G2`) and the `G5` (`X-04` candidate) knowledge-evolution sequence |

> **Distinction Between the Pilot Study Object and Host Plugins `0.1.2`**: Cohort 2 ran with the pinned formal native plugin `mindie-agent-dsh 0.1.1` (`fc29535161c0d9e57c558c250bbb9101c0da55ce`) and its `0.1.1` `C6` organizer alongside the 8 updated formal runtime components. The four newly published native host plugins `0.1.2` (Codex `0b3c690b...`, CC `edabca82...`, Kimi `7aecfd22...`, DSH `a38f1cb1...`) are verified separately for live native installation, manual `/mindie-agent` session gating, and component updates in [`native-update-acceptance.json`](native-update-acceptance.json); **this LLM pilot is not claimed as an end-to-end value evaluation of the `0.1.2` native host plugin packages.**

### 2. Task Source Classification (`declared_source` vs. `source_class`) & Prompt Soundness

Git commit object inspection was performed across all task definitions, and [`benchmark-pilot.json`](benchmark-pilot.json) records both the raw `task.toml` declaration (`declared_source`) and the verified actual `source_class`:

1. **Three Maintenance Component Tasks (`source_class = "seeded_local_engineering_fixture"`)**:
   - Tasks: `npu-top-and-coordinator-multi-die-lease-repair-zh` (hash `0883a3a2...`), `profiler-msprof-straggler-and-hbm-fix-zh` (hash `1c350fe1...`), and `sim-a3-ub-fusion-and-pipeline-dispatch-zh` (hash `21e68aad...`), each budgeted at `50 turns / 480s`.
   - Although raw `task.toml` metadata declared `repository = "vllm-project/vllm-ascend"` (`issue = "component-value-0.1.0"`), Git commit inspection confirmed that `base_commit` `f752d0215c2e13b44ac472caa14c02b6749762e3` (*"Add broken vllm_ascend_diag baseline modules for component value tasks"*, adding 11 fixture files) and `fix_commit` `8c5ce76d9afb36205b8e59adb7b2d4b2ad89a85c` (*"Fix vllm_ascend_diag modules using MindIE component contracts"*) are **seeded local engineering fixtures** created in a local checkout—not verified upstream commits or field production incidents.
2. **Three G5 Speculative-Decoding Tasks + Two Long-Training Budget Variants (`source_class = "historical_source_regression"`)**:
   - **SFA multi-step speculative sequence-length seed task** `sfa-mtp-seq-lens-seed-zh-vague` (hash `35053616...`, budget `80 turns / 600s`) and its Stage `A` long-training variant `sfa-mtp-seq-lens-seed-zh-vague-g5-long` (hash `8d8fe41a...`, budget `120 turns / 900s`): derived from historical source regression `base_commit` `b9c58e8d7073bdda448c49bc6239778c0e6a6960` and `fix_commit` `035b8d40718dc097e159e3590975d712535e4245` (issue `#14236`).
   - **SFA multi-step speculative evaluation task** `sfa-mtp-seq-lens-eval-zh-vague` (hash `08ee5c9c...`, budget `80 turns / 600s`): shares the exact same `base_commit` and `fix_commit` (`#14236`) as the seed task (`independent_heldout = false`).
   - **MTP speculative draft slot-mapping capacity task** `mtp-draft-slot-mapping-capacity-zh-vague` (hash `e39b54fe...`, budget `60 turns / 600s`) and its Stage `C` prepared long-training variant `mtp-draft-slot-mapping-capacity-zh-vague-g5-long` (hash `4af7f57d...`, declared in `task.toml` at `60 turns / 900s` and never started because Stage `A` produced no admitted corpus): derived from historical source regression `base_commit` `63bd2c418c8914201981f1150fc0e0ae5724896e` and `fix_commit` `0aa1b486c0e6d3fb457822da2b9b49ede2578562` (issue `#14024`).
   - All tasks are judged by offline CPU behavioral verifiers (the standing A2/A3 live probe `test_live_fleet_probe_and_capacity_across_a2_and_a3` `1 passed in 8.01s` is a separate read-only fleet capacity test, not live on-card execution of these SFA/MTP tasks).
3. **Short Vague Prompts & Verifier Soundness**:
   - All 6 base tasks use 32–42 character Chinese vague prompts (`prompt_file_sha256: d1895e5b047e5a2e91e104683bcc6d28403b0f455d067c32febcbaf96ee66fd1`) that state only the observable symptom and goal without naming root causes, symbols, or algorithm steps while leaving workspace code inspectable; the 2 `-g5-long` variants keep the exact same prompt text.
   - Under formal `mindie-bench 0.4.4`, all 6 base tasks and 2 budget variants passed zero-model soundness verification (`before_reward = 0.0`, `after_reward = 1.0`, `model_calls = 0`).

---

## 3. Raw Cohort Accounting & Per-Trial Results (All 21 Trial Receipts, 800 Observed Foreground Model Calls)

[`benchmark-pilot.json`](benchmark-pilot.json) contains **21 terminal trial receipts** (`2` Codex + `12` DSH = `14` maintenance receipts; `3 + 3 + 1 = 7` `G5` receipts across `v2 / v3 / v4`; plus `g5-dsh-044` v1 recorded separately as a `0`-trial pre-admission setup failure). Across the 21 trial receipts, the terminal outcome breakdown is **`5 completed_pass`, `8 completed_fail`, `7 infra_failed`, and `1 unknown`**, with **`800` total observed foreground `model_calls`** (`10 + 6×50 + 3×50 + 80 + 60 + 80 + 120 = 800`). Missing or `infra_failed` fields preserve their `null` semantics without filling cost as `0`; because the metering relay did not return USD billing, `estimated_cost_usd` is `null` (`cost_complete = false`) across all trials.

### 1. Matrix Cohort & G5 Sequential Plan Accounting Summary

- **Maintenance Matrix Cohorts (Formal Matrix Manifests, 14 Trial Receipts)**:

| Matrix Cohort ID | Manifest / Config SHA256 | Planned Cells (`planned_cells`) | Terminal Receipts (`terminal_receipts`) | Matrix Unexecuted (`missing_count`) | Terminal Outcome Breakdown |
| --- | --- | --- | --- | --- | --- |
| `maintenance-codex` | `d280424e...` | 9 | 1 | 8 | `1 infra_failed` (preflight `ValueError`, `0` calls) |
| `maintenance-codex-v2` | `c6418740...` | 9 | 1 | 8 | `1 unknown` (`480s` budget expired mid-stream, `10` calls; `8` unstarted) |
| `maintenance-dsh-044` | `669fa358...` / `ed38a420...` | 9 | 9 | 0 | `6 completed_fail` (`G0`/`G1`, `50` calls each), `3 infra_failed` (`G2` preflight, `0` calls) |
| `maintenance-dsh-044-native-path` | `f4af7c78...` / `e2988ae9...` | 3 | 3 | 0 | `3 completed_pass` (separate `G2` cohort after native plugin path fix, `50` calls each) |

- **G5 Sequential Plans (No Matrix Manifest, 7 Trial Receipts)**:

| G5 Sequence ID | Config / Sequence SHA256 | Planned Sequence Stages | Started & Receipted Stages | Dependent Unstarted (`B–E`) | Sequence Status & Outcome Breakdown |
| --- | --- | --- | --- | --- | --- |
| `g5-dsh-044` | — | 7 (`2` cold controls + `A–E`) | 0 | 7 (aborted before admission) | `setup_failed_before_trial_admission` (`0` calls) |
| `g5-dsh-044-v2` | `92fdd2ee...` / `fc723770...` | 7 (`2` cold controls + `A–E`) | 3 (`control-B`, `control-D`, `A`) | 4 (`B–E` unstarted) | `3 infra_failed` (native plugin path preflight rejection, `0` calls) |
| `g5-dsh-044-v3` | `48bda743...` / `56c249f6...` | 7 (`2` cold controls + `A–E`) | 3 (`control-B`, `control-D`, `A`) | 4 (`B–E` unstarted) | `2 completed_fail` (cold controls `B/D`), `1 completed_pass` with **pre-`C6` capture admission failed** (`A`, `80` calls) |
| `g5-dsh-044-v4-long-training` | `g5-budget-amendment` / `9f5cc087...` | 5 (reusing `2` `v3` cold controls; newly planning `A–E`) | 1 (`stage A` long budget) | 4 (`B–E` unstarted) | `1 completed_pass` with **pre-`C6` capture admission failed** (`A`, `120`-call fresh rerun) |

### 2. Per-Trial Results Across Codex Canary & DSH Maintenance Cohorts (14 Trials: 2 Codex + 12 DSH)

- **Codex G0 Canary Notes**: `maintenance-codex` failed at preflight (`ValueError`, `0` model calls). `maintenance-codex-v2` planned 9 cells and executed only the first G0 canary (the remaining 8 cells were never started—recorded as `missing_count = 8`, not 8 task failures). When the `480.00s` foreground budget expired while a streaming response was still in flight, the primary receipt was recorded as `status = "unknown"` with `tokens.complete = false`. A post-hoc zero-model verifier run on the saved workspace patch (`patch_sha256: 81bf62c3...`) yielded `reward = 0.0` (`oracle_status = "intact"`), while preserving `unknown` as the primary receipt status.
- **DSH `G2` Preflight Failure & Config Correction Notes**: In `maintenance-dsh-044` (config `ed38a420...`), all 6 `G0` and `G1` cells ran to the full `50`-call budget and ended in `completed_fail` (`reward = 0.0`), while the 3 `G2` cells failed at preflight (`ValueError`, `0` paid model calls) because the initial configuration listed DSH's executable native plugin package directory inside the protected corpus path list. Correcting only that path classification (config `e2988ae9...`, mounting the native plugin package normally as executable code while keeping real corpus paths protected and keeping MindIE unmounted in `G0`/`G1`) produced the separate 3-cell cohort `maintenance-dsh-044-native-path`, where all 3 `G2` cells finished with `completed_pass` (`reward = 1.0`, `50` calls each). Both cohorts and all 14 maintenance receipts are retained in full below:

| Cohort | Trial ID | Gate | Status | Reward | Calls / Turns | Wall / Delivery (s) | Input Cached / Uncached / Output Tokens (`complete`) | Tool Call Counts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `maintenance-codex` | `npu-top-and-coordinator-multi-die-lease-repair-zh_G0_1_d2c398b602ab` | `G0` | `infra_failed` | `null` | `null` / `0` | `0.00` / `0.06` | `0` / `0` / `0` (`false`) | `{}` (preflight `ValueError`) |
| `maintenance-codex-v2` | `npu-top-and-coordinator-multi-die-lease-repair-zh_G0_1_7853fadf3bbd` | `G0` | `unknown` *(post-hoc patch `0.0`)* | `null` | `10` / `10` | `480.00` / `514.06` | `329,600` / `50,439` / `20,604` (`false`) | `bash: 21, Edit: 3` |
| `maintenance-dsh-044` | `npu-top-and-coordinator-multi-die-lease-repair-zh_G0_1_65a626a5895d` | `G0` | `completed_fail` | `0.0` | `50` / `50` | `329.79` / `358.99` | `2,637,952` / `103,233` / `70,062` (`true`) | `bash: 36, Edit: 5, Read: 4, web_search: 2, Write: 1, subagent_fork: 1` |
| `maintenance-dsh-044` | `npu-top-and-coordinator-multi-die-lease-repair-zh_G1_1_dc16ab442303` | `G1` | `completed_fail` | `0.0` | `50` / `50` | `149.98` / `154.75` | `3,220,864` / `119,364` / `16,111` (`true`) | `bash: 40, Read: 20, Grep: 4, Glob: 2, web_search: 1, mcp_res*: 3` |
| `maintenance-dsh-044` | `npu-top-and-coordinator-multi-die-lease-repair-zh_G2_1_25dd5d0b8f67` | `G2` | `infra_failed` | `null` | `null` / `0` | `0.00` / `1.21` | `0` / `0` / `0` (`false`) | `{}` (preflight `ValueError`) |
| `maintenance-dsh-044` | `profiler-msprof-straggler-and-hbm-fix-zh_G0_1_7b2a4f17c541` | `G0` | `completed_fail` | `0.0` | `50` / `50` | `385.26` / `391.46` | `3,342,720` / `64,444` / `56,823` (`true`) | `bash: 57, Edit: 8, Read: 5, web_search: 1, Write: 1` |
| `maintenance-dsh-044` | `profiler-msprof-straggler-and-hbm-fix-zh_G1_1_fec9c511ee84` | `G1` | `completed_fail` | `0.0` | `50` / `50` | `341.44` / `348.02` | `4,861,824` / `143,383` / `48,995` (`true`) | `bash: 48, Read: 10, Edit: 3, Glob: 1, Grep: 1, web_search: 1, web_fetch: 1` |
| `maintenance-dsh-044` | `profiler-msprof-straggler-and-hbm-fix-zh_G2_1_41f6e12ec063` | `G2` | `infra_failed` | `null` | `null` / `0` | `0.00` / `1.49` | `0` / `0` / `0` (`false`) | `{}` (preflight `ValueError`) |
| `maintenance-dsh-044` | `sim-a3-ub-fusion-and-pipeline-dispatch-zh_G0_1_fe1620c146e3` | `G0` | `completed_fail` | `0.0` | `50` / `50` | `302.89` / `310.74` | `3,040,000` / `76,621` / `48,017` (`true`) | `bash: 56, Read: 8, Edit: 3, Grep: 2, Glob: 1, web*: 2, todo_write: 1, subagent: 1` |
| `maintenance-dsh-044` | `sim-a3-ub-fusion-and-pipeline-dispatch-zh_G1_1_177630ae6fce` | `G1` | `completed_fail` | `0.0` | `50` / `50` | `305.26` / `310.50` | `4,168,448` / `149,186` / `20,391` (`true`) | `bash: 67, Read: 11, Glob: 1, web_search: 1, web_fetch: 1, mcp_res*: 3` |
| `maintenance-dsh-044` | `sim-a3-ub-fusion-and-pipeline-dispatch-zh_G2_1_e70dffc9d28f` | `G2` | `infra_failed` | `null` | `null` / `0` | `0.00` / `1.43` | `0` / `0` / `0` (`false`) | `{}` (preflight `ValueError`) |
| `maintenance-dsh-044-native-path` | `npu-top-and-coordinator-multi-die-lease-repair-zh_G2_1_5cc88a2e761e` | `G2` | `completed_pass` | `1.0` | `50` / `50` | `268.94` / `275.88` | `5,195,008` / `156,193` / `33,755` (`true`) | `bash: 58, Read: 12, knowledge_query: 4, mindie_entry: 1, knowledge_explain: 1, Write: 1, web*: 2` |
| `maintenance-dsh-044-native-path` | `profiler-msprof-straggler-and-hbm-fix-zh_G2_1_e361bd685cef` | `G2` | `completed_pass` | `1.0` | `50` / `50` | `345.26` / `351.99` | `5,481,344` / `137,423` / `52,171` (`true`) | `bash: 48, Read: 9, Edit: 4, knowledge_query: 3, mindie_entry: 1, knowledge_explain: 1, Write: 1, web*: 2` |
| `maintenance-dsh-044-native-path` | `sim-a3-ub-fusion-and-pipeline-dispatch-zh_G2_1_469e50895a9f` | `G2` | `completed_pass` | `1.0` | `50` / `50` | `352.38` / `358.46` | `4,736,896` / `149,614` / `41,763` (`true`) | `bash: 58, Read: 5, knowledge_query: 4, Grep: 3, mindie_entry: 1, knowledge_explain: 1, job_output: 1, Write: 1, web_fetch: 1` |

---

## 4. G5 (`X-04` Candidate Protocol) Event Chain & Unclosed Loop

Because the external ChatGPT share link referenced by the user could not be fetched during experiment preparation, this run used the repository's existing `X-04` (`Episode A -> B -> C -> D -> E`) design as a candidate protocol and **does not claim to reproduce the external discussion**.

### 1. Four-Attempt Execution Chain (Exact Failure Point: Pre-`C6` Native Capture Descriptor Admission)

1. **`g5-dsh-044` (Pre-Admission Setup Failure)**:
   - Aborted before admitting any trial (`status = "setup_failed_before_trial_admission"`, `0` trials, `0` model calls).
2. **`g5-dsh-044-v2` (Preflight Rejection, `0` Paid Calls)**:
   - Planned 7 stages (`2` cold controls + `5` episodes `A–E`); due to the native-plugin-in-protected-corpus check, the 3 started stages—`control-B-cold` (`6b641fe7cf81`), `control-D-cold` (`9a0a1f8af376`), and `stage A` (`6d7577328e67`)—failed at preflight with `ValueError` (`status = "infra_failed"`, `0` model calls), and `B–E` were not started.
3. **`g5-dsh-044-v3` (Cold Controls Fail; Stage `A` Passes Business Verifier but Is Rejected at Pre-`C6` Native Capture Admission)**:
   - **Cold Control `control-B-cold`** (`sfa-mtp-seq-lens-eval-zh-vague_G2_1_d7bdc5c24885`): Ran all `80` calls (`wall = 246.46s`) and failed the behavioral verifier (`completed_fail`, `reward = 0.0`).
   - **Cold Control `control-D-cold`** (`mtp-draft-slot-mapping-capacity-zh-vague_G2_1_9ee7dc0d7998`): Ran all `60` calls (`wall = 205.29s`) and failed the behavioral verifier (`completed_fail`, `reward = 0.0`).
   - **Training Episode `A` (`80`-Call Budget)** (`sfa-mtp-seq-lens-seed-zh-vague_G3_1_8b02618500ea`): The agent repaired the workspace code and passed the behavioral verifier (`status = "completed_pass"`, `reward = 1.0`, `oracle_status = "intact"`). However, the session hit the `80`-call turn budget without emitting a native completed session event. **Prior to invoking the `C6` organizer**, the native session capture descriptor admission check (`DshDriver.native_capture_payload()`) raised `ValueError("DSH capture requires a completed native session event")` (`capture.status = "failed"`, `captured_corpus_sha256 = null`, `units_after = null`)—**no valid input entered `C6` distillation, neither the `C6` organizer nor local Git publication was executed, and `0` knowledge units were admitted**.
4. **`g5-dsh-044-v4-long-training` (Fresh Independent Session with Stage `A` Raised to `120 turns / 900s`)**:
   - To test whether a larger turn budget would allow Episode `A` to conclude naturally—without replaying provider requests, fabricating a native completion event, pre-seeding `U@2`, or altering consumer budgets—we reused the `2` completed cold controls from `v3` and ran a fresh independent Stage `A` session (`sfa-mtp-seq-lens-seed-zh-vague-g5-long_G3_1_91e50697f5a5`) at `max_turns = 120`, `timeout_sec = 900` (while the prepared Stage `C` variant `mtp-draft-slot-mapping-capacity-zh-vague-g5-long` remained configured at `max_turns = 60`, `timeout_sec = 900`).
   - **Outcome**: The agent again passed the behavioral verifier (`status = "completed_pass"`, `reward = 1.0`, `oracle_status = "intact"`, `wall = 523.98s`), and again exhausted all `120` calls without emitting a native completed session event. It was again rejected at the **pre-`C6` native session capture descriptor admission check (`DshDriver.native_capture_payload()`)** (`capture.status = "failed"`, `0` admitted units, without executing the `C6` organizer or local Git publication). Both Stage `A` runs (`80 + 120 = 200` model calls, `tokens.complete = false`) are preserved in full.
   - **Downstream Episodes `B / C / D / E` Not Started**: Because Episode `A` produced no legitimately admitted corpus, dependent Episodes `B`, `C` (including the unstarted `60 turns / 900s` variant), `D`, and `E` were never started (`status = "partial_A_has_no_admitted_corpus"`, `revision_observed = null`). **The full knowledge-evolution chain was not executed, and the `G5` closed-loop experiment did not pass.**

### 2. G5 Per-Trial Receipts (7 Trials)

| Cohort & Stage | Trial ID | Gate | Business Status | Reward | Pre-`C6` Capture Admission (`capture`) | Calls / Turns | Wall / Delivery (s) | Input Cached / Uncached / Output Tokens (`complete`) | Tool Call Counts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `g5-dsh-044-v2` `control-B-cold` | `sfa-mtp-seq-lens-eval-zh-vague_G2_1_6b641fe7cf81` | `G2` | `infra_failed` | `null` | — | `null` / `0` | `0.00` / `1.29` | `0` / `0` / `0` (`false`) | `{}` (preflight `ValueError`) |
| `g5-dsh-044-v2` `control-D-cold` | `mtp-draft-slot-mapping-capacity-zh-vague_G2_1_9a0a1f8af376` | `G2` | `infra_failed` | `null` | — | `null` / `0` | `0.00` / `0.83` | `0` / `0` / `0` (`false`) | `{}` (preflight `ValueError`) |
| `g5-dsh-044-v2` `stage A` | `sfa-mtp-seq-lens-seed-zh-vague_G3_1_6d7577328e67` | `G3` | `infra_failed` | `null` | — | `null` / `0` | `0.00` / `0.86` | `0` / `0` / `0` (`false`) | `{}` (preflight `ValueError`) |
| `g5-dsh-044-v3` `control-B-cold` | `sfa-mtp-seq-lens-eval-zh-vague_G2_1_d7bdc5c24885` | `G2` | `completed_fail` | `0.0` | — | `80` / `80` | `246.46` / `256.62` | `9,709,824` / `310,845` / `32,152` (`true`) | `bash: 68, Read: 30, knowledge_query: 2, mindie_entry: 1, knowledge_explain: 1, web_fetch: 1` |
| `g5-dsh-044-v3` `control-D-cold` | `mtp-draft-slot-mapping-capacity-zh-vague_G2_1_9ee7dc0d7998` | `G2` | `completed_fail` | `0.0` | — | `60` / `60` | `205.29` / `214.32` | `6,457,728` / `303,591` / `26,276` (`true`) | `bash: 91, Read: 6, knowledge_query: 3, mindie_entry: 1, knowledge_explain: 1, web_search: 1, remote_probe: 1` |
| `g5-dsh-044-v3` `stage A` (`80` turns) | `sfa-mtp-seq-lens-seed-zh-vague_G3_1_8b02618500ea` | `G3` | `completed_pass` | `1.0` | **`failed`** (pre-`C6` descriptor `ValueError`, `0` units) | `80` / `80` | `365.49` / `378.17` | `9,528,320` / `287,690` / `55,243` (`false`) | `bash: 85, Read: 13, knowledge_query: 3, Edit: 2, Write: 2, mindie_entry: 1, web_fetch: 1` |
| `g5-dsh-044-v4` `stage A` (`120` turns) | `sfa-mtp-seq-lens-seed-zh-vague-g5-long_G3_1_91e50697f5a5` | `G3` | `completed_pass` | `1.0` | **`failed`** (pre-`C6` descriptor `ValueError`, `0` units) | `120` / `120` | `523.98` / `535.88` | `15,251,584` / `485,606` / `73,934` (`false`) | `bash: 127, Read: 20, Edit: 4, knowledge_query: 2, knowledge_explain: 2, mindie_entry: 1, web*: 2` |

---

## 5. Key Engineering Findings & Limitations

1. **Discovered and Fixed the `mindie-bench 0.4.3` `HTTP/1.1 chunked` Settlement Close Race (Formally Released in `0.4.4`)**:
   - Interrupting the in-flight `HTTP/1.1 chunked` stream at the `480s` deadline during the Codex G0 canary revealed that calling `connection.close()` from the settler thread cleared `HTTPResponse.fp` while the request handler thread was inside `response.read1()`, raising `AttributeError: NoneType.close` on Python 3.13 and dropping the structured `model_error` entry.
   - `mindie-bench 0.4.4` (`a36d8a5ae8633e560d19fee231179c3680149109`) calls only `shutdown(socket.SHUT_RDWR)` on the underlying socket to wake blocked reads, leaving `HTTPConnection` / `HTTPResponse.close()` to the request handler thread's `finally` block. Verified across two zero-cost loopback test modules (`18 passed in 13.24s`), a deterministic `HTTP/1.1 chunked` reader-pause interleaving regression (`0.60s`), a negative control against the old close behavior, macOS/Linux CI, and byte-for-byte verification of all 7 release assets and 158 packaged `.py` files. The original canary receipt remains `unknown` without claiming recovery of missing remote token usage.
2. **Resolved the DSH Native Plugin vs. Protected Corpus Preflight Conflict**:
   - Separating DSH's executable native plugin path from the protected corpus input list resolved the `G2`/`G3` preflight `ValueError` while keeping real corpus directories protected.
3. **Identified the Gap Between Passing a Task Verifier and Passing Pre-`C6` Native Capture Descriptor Admission**:
   - In both `G5 stage A` runs (`80` and `120` calls), the agent repaired the code (`reward = 1.0`) but continued running commands until exhausting the turn budget without emitting a native completed session event. Consequently, `DshDriver.native_capture_payload()` rejected the session at pre-`C6` capture descriptor admission before the `C6` organizer was ever called. Passing a task verifier or calling `knowledge_query` / `knowledge_explain` does not equal successful knowledge distillation.
4. **Experimental & Methodological Limitations**:
   - **Sample Size & Task Provenance**: All runs are `repetitions = 1` over exposed offline CPU tasks, and the 3 maintenance tasks are seeded local engineering fixtures (`seeded_local_engineering_fixture`) rather than verified upstream commits or live NPU workloads.
   - **`G5` Protocol & Semantic Revision Gaps**: Even if Episode `C` had run on the separate MTP capacity bug and produced a unit, adding a new unit for a distinct bug is not equivalent to counterevidence-driven revision (`U@1 -> U@2`) of the same unit; moreover, Episode `B` shares the same historical issue (`#14236`) with `A`, and `D`/`E` repeat exposed cases rather than testing unseen held-out transfer. Full semantic `U@1 -> U@2` counterevidence review and held-out transfer evaluation remain future work.

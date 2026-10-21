# MindIE Agent `0.0.3` Component Value Verification Report

This report records the repeatable component-value benchmark scenarios executed by `mindie-bench` (`v0.4.1`, commit `994b48e410f8dec989e26130b6e52fc5a6b569d2`) against the exact non-editable (`editable: false`) `0.0.3` formal release packages (`component-value-results.json`), together with the `knowledge` (`v0.13.0`) P0–P4 progressive-disclosure and closed-loop verification metrics.

## 1. Installed Runtime & Analysis Package Revisions

| Package | Version | Exact Commit SHA | Editable |
| --- | --- | --- | --- |
| `mindie-diagnostics` | `0.5.1` | `fba07e8607ddadde14cea315c9dbda23726c1c79` | `false` |
| `mindie-profiler` | `0.5.0` | `4010d72f0b6950caf1425e3b683d495a6c76016a` | `false` |
| `mindie-sim` | `0.7.0` | `4040f078c19487c019c87466a0d128821289ccc2` | `false` |
| `npu-top` | `0.2.1` | `6737925d0ebb39c1aefda2c933eae0486169333c` | `false` |
| `remote-dev` | `0.10.4` | `6bd1a15380195a95d450458e7c1856905d95bf73` | `false` |
| `mindie-knowledge` | `0.13.0` | `10ee85606aa43de7975e3c4542013be4c177730a` | `false` |
| `mindie-coordinator` | `0.6.2` | `bdead0ac37cc4cee34a1736edc776b48ea823542` | `false` |

---

## 2. Five-Component Value Scenarios (`value_scenarios`)

### `npu-top-physical-owner-query` (`npu-top v0.2.1`, 3 Repetitions — `pass`)

| Observation | Baseline Samples | Candidate Samples |
| --- | --- | --- |
| `golden_physical_devices_correct` | `null, null, null` | `24, 24, 24` |
| `golden_process_assignments_correct` | `null, null, null` | `16, 16, 16` |
| `golden_process_assignments_expected` | `null, null, null` | `16, 16, 16` |
| `live_physical_devices` | `null, null, null` | `8, 8, 8` |
| `live_container_owner_correct` | `null, null, null` | `True, True, True` |
| `live_ssh_operations` | `null, null, null` | `3, 3, 3` |

### `coordinator-contention` (`mindie-coordinator v0.6.2`, 3 Repetitions — `pass`)

| Observation | Baseline Samples | Candidate Samples |
| --- | --- | --- |
| `successful_listeners` | `1, 1, 1` (`3` total) | `2, 2, 2` (`6` total) |
| `bind_conflicts` | `1, 1, 1` (`3` total) | `0, 0, 0` (`0` total) |
| `duplicate_device_selections` | `1, 1, 1` (`3` total) | `0, 0, 0` (`0` total) |
| `release_to_next_success_sec` | `unmeasured` | `~0.002s` (`1.9 ms`) |

### `diagnostics-fault-delivery` (`mindie-diagnostics v0.5.1`, 3 Repetitions — `pass`)

| Observation | Baseline Samples | Candidate Samples |
| --- | --- | --- |
| `failure_occurrences` | `3, 3, 3` | `3, 3, 3` |
| `delivered_reports` | `0, 0, 0` | `1, 1, 1` |
| `reconciled_without_duplicate` | `False, False, False` | `True, True, True` |
| `private_fixture_removed` | `False, False, False` | `True, True, True` |
| `useful_fault_fields_retained` | `False, False, False` | `True, True, True` |
| `withdrawal_prevented_requests` | `False, False, False` | `True, True, True` |
| `fault_log_redacted` | `False, False, False` | `True, True, True` |
| `fault_triage_deterministic` | `False, False, False` | `True, True, True` |
| `fault_triage_root_cause_rank` | `null, null, null` | `"3", "3", "3"` |
| `fault_triage_domain` | `null, null, null` | `"aicore_memory_or_tiling"` |
| `fault_triage_cascading_timeout` | `False, False, False` | `True, True, True` |
| `fault_triage_cascading_rank` | `null, null, null` | `"7", "7", "7"` |

### `profiler-rank-link-memory-attribution` (`mindie-profiler v0.5.0`, 3 Repetitions — `pass`)

| Observation | Baseline Samples | Candidate Samples |
| --- | --- | --- |
| `profile_steps_aligned` | `False, False, False` | `True, True, True` |
| `slow_link_dominant_block` | `null, null, null` | `"Comm", "Comm", "Comm"` |
| `slow_rank_dominant_block` | `null, null, null` | `"Attention", "Attention", "Attention"` |
| `known_sum_bytes` | `0.0` | `9,900,000,000.0` (`9.9 GB`, `99%`) |
| `residual_bytes` | `10,000,000,000.0` | `50,000,000.0` (`50 MB`, `0.5% < 10%` target) |
| `residual_status` | `"unattributed"` | `"within_target"` |
| `memory_target_met` | `False, False, False` | `True, True, True` |
| `db_mutation` | `False, False, False` | `False, False, False` |
| `analyze_latency_ms` | `unmeasured` | `~7.6 ms` |
| `compare_latency_ms` | `unmeasured` | `~0.16 ms` |
| `memory_latency_ms` | `unmeasured` | `~0.15 ms` |

### `sim-a3-graph-and-boundary-screening` (`mindie-sim v0.7.0`, 3 Repetitions — `pass`)

| Observation | Baseline Samples | Candidate Samples |
| --- | --- | --- |
| `qwen_case_deterministic` | `False, False, False` | `True, True, True` |
| `a3_graph_tpot_ms` (vs. `15.71 ms` measured) | `null` | `15.060 ms` |
| `tpot_error_pct` (gate `±15%`) | `null` | `-4.139%` |
| `operator_plan_backends` | `[]` | `["gemm_finite_pipeline", "vector_instruction"]` |
| `subgraph_removable_gm_bytes` | `0.0` | `2,097,152.0` (`2.0 MiB`) |
| `subgraph_critical_path_saving_us` | `0.0` | `5.0 μs` |
| `subgraph_overflow_rejected` | `False, False, False` | `True, True, True` |

---

## 3. Knowledge System (`mindie-knowledge v0.13.0`) Progressive Disclosure & Closed-Loop Summary

| Verification Suite | Scope | Measured Outcome |
| --- | --- | --- |
| `technical-tokenization` & `graded-feed-lifecycle` | Release microbenchmark & functional gate | Precision `1.000`, lifecycle median `13.83 ms` (`pass`) |
| `P0` Context Efficiency (`12/12` checks) | Progressive disclosure token ceiling (`g_read <= 8,000`) & amortized reuse (`k=8`) | `g_read = 4,814–5,599` tokens (`< 8,000`), net benefit at `k=8`: `+77,280` to `+89,120` tokens (`pass`) |
| `P1` L1–L4 Hierarchy & Anti-Anchoring (`6/6` checks) | `mode="explore"` L4 suppression, applicability mismatch warnings, failure-history exposure | `explore` returns `0` L4 units while retaining L1–L3 invariants; subcontext fact pack within `1,600` token cap (`pass`) |
| `P2–P4` Closed-Loop Evolution (`3/3` checks) | Experience distillation, provenance validation, duplicate suppression & stale demotion | `100%` provenance retention, duplicate suppression, and stale demotion verified (`pass`) |

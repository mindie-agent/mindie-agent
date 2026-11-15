# mindie-agent/mindie-bench 0.4.1


Version: 0.1.0. Suite: `product-value-v0.1.0-components`. Evidence: complete.

Each row compares the same tasks and model (different models are never averaged). Paired timing ratios (`baseline / candidate`) use only pairs solved by both conditions; all failed, incomplete, and historical attempts remain in the inventory and resource totals.

Benchmark execution and measurement coverage across the product suite. These task results measure the evaluated product, not productivity caused by the measurement tool itself.

Repeated component value scenarios executed against exact non-editable 0.1.0 formal releases.

0.1.0 value-suite verifies the 5 repeatable component value scenarios (coordinator, npu-top, diagnostics, profiler, sim) against exact non-editable formal releases alongside 12-repository release benchmarks and 18 end-to-end real Agent tasks.

- **Conditions**: **G0** uses the native host; **G1** adds `remote-dev`; **G2** adds `knowledge` retrieval, shipped Skills, and explicit retrieval guidance on top of G1; **G3** captures an earlier seed task's experience for later evaluation tasks.
- **Key Takeaways**: `remote-dev` (G0 → G1) solved `3/3` `quarot` runs with a `1.025x` delivery speedup and matched baseline on `dp2` (`0.963x`); `coordinator` eliminated port and device conflicts (`3 → 0`) and doubled active listeners (`3 → 6`) under concurrent contention; `knowledge` + Skills (G2/G3) increased completed tasks on `dp2` and `dsh` (`2/3 → 3/3`) and hit captured seed experience in `5/6` transfer tasks, while retrieval and context-reading latency is targeted for optimization in `0.0.3`.

| Study | Model | Observed / planned | Pass | Fail | Infrastructure | Unknown |
| --- | --- | ---: | ---: | ---: | ---: | ---: |

## Measurement versions and scope

Release runner: `mindie-bench` 0.4.1 (`994b48e410f8dec989e26130b6e52fc5a6b569d2`). Task evaluations ran on the historical runner revisions listed below; later changes in `0.3.0` cover cleanup, provenance checks, and report publication without rewriting task inputs, models, budgets, or recorded attempt costs.

## npu-top

Scenario: physical die/PID/HBM correctness from captures and live proc/container identity (3 repetitions).

- A2 live and A3 dual-die historical captures are reported separately.
- Golden replay repetitions measure repeatability, not independent hardware samples.
- The container identity probe does not claim its init process consumes NPU memory.
- No model/human task timing, avoided incident count or causal productivity gain is measured.
- Raw command lines, working directories and environments are not exported.

| Observation | Baseline samples | Candidate samples |
| --- | --- | --- |
| golden_physical_devices_correct | unmeasured, unmeasured, unmeasured | 24, 24, 24 |
| golden_process_assignments_correct | unmeasured, unmeasured, unmeasured | 16, 16, 16 |
| golden_process_assignments_expected | unmeasured, unmeasured, unmeasured | 16, 16, 16 |
| human_answer_accuracy | None, None, None | unmeasured, unmeasured, unmeasured |
| human_completion_time_sec | None, None, None | unmeasured, unmeasured, unmeasured |
| live_container_owner_correct | unmeasured, unmeasured, unmeasured | True, True, True |
| live_physical_devices | unmeasured, unmeasured, unmeasured | 8, 8, 8 |
| live_ssh_operations | unmeasured, unmeasured, unmeasured | 3, 3, 3 |

## coordinator

Scenario: two concurrent agents, live TCP ports, production SQLite allocation and recovery (3 repetitions).

- This is the check-then-act race, not a comparison against another atomic scheduler.
- Device identities come from observation; no NPU compute is launched or reserved globally.
- Ports, child processes and allocation state are owned by this local scenario.
- Elapsed time includes child startup and is not a model productivity estimate.

| Observation | Baseline samples | Candidate samples |
| --- | --- | --- |
| bind_conflicts | 1, 1, 1 | 0, 0, 0 |
| duplicate_device_selections | 1, 1, 1 | 0, 0, 0 |
| elapsed_sec | 0.187, 0.095, 0.094 | 0.135, 0.106, 0.109 |
| release_to_next_success_sec | None, None, None | 0.002, 0.002, 0.002 |
| successful_listeners | 1, 1, 1 | 2, 2, 2 |

## diagnostics

Scenario: real logging, redaction, deterministic fault triage, outbox and reporter with local HTTP (3 repetitions).

- The Ascend plog is a deterministic fixture with a synthetic credential, not a fresh device failure.
- Fault triage selects root cause deterministically; it does not execute the recommended commands.
- The HTTP receiver implements a bounded GitHub-compatible fixture, not GitHub availability.
- GitHub.request and subprocess parsing are production code; only its executable transport is local.
- The controlled fault is FileNotFoundError; reporting does not repair the failing operation.
- No human triage-time or model productivity claim is made.
- The separate public Issue 243 native canary is not rerun or counted here.

| Observation | Baseline samples | Candidate samples |
| --- | --- | --- |
| automatic_delivery | False, False, False | unmeasured, unmeasured, unmeasured |
| contains_synthetic_secret | True, True, True | unmeasured, unmeasured, unmeasured |
| delivered_reports | unmeasured, unmeasured, unmeasured | 1, 1, 1 |
| failure_occurrences | 3, 3, 3 | 3, 3, 3 |
| failure_to_delivery_sec | unmeasured, unmeasured, unmeasured | 61.642, 61.618, 61.656 |
| fault_log_redacted | unmeasured, unmeasured, unmeasured | True, True, True |
| fault_triage_cascading_rank | unmeasured, unmeasured, unmeasured | 7, 7, 7 |
| fault_triage_cascading_timeout | unmeasured, unmeasured, unmeasured | True, True, True |
| fault_triage_deterministic | unmeasured, unmeasured, unmeasured | True, True, True |
| fault_triage_domain | unmeasured, unmeasured, unmeasured | aicore_memory_or_tiling, aicore_memory_or_tiling, aicore_memory_or_tiling |
| fault_triage_root_cause_rank | unmeasured, unmeasured, unmeasured | 3, 3, 3 |
| http_posts | unmeasured, unmeasured, unmeasured | 1, 1, 1 |
| private_fixture_removed | unmeasured, unmeasured, unmeasured | True, True, True |
| production_retry_wait_sec | unmeasured, unmeasured, unmeasured | 59.998, 59.998, 59.999 |
| queue_items | unmeasured, unmeasured, unmeasured | 1, 1, 1 |
| raw_tracebacks | 3, 3, 3 | unmeasured, unmeasured, unmeasured |
| reconciled_without_duplicate | unmeasured, unmeasured, unmeasured | True, True, True |
| useful_fault_fields_retained | unmeasured, unmeasured, unmeasured | True, True, True |
| withdrawal_prevented_requests | unmeasured, unmeasured, unmeasured | True, True, True |

## profiler

Scenario: real analyze_profile, compare_profiles and attribute_memory on deterministic SQLite captures (3 repetitions).

- The SQLite captures are deterministic fixtures; they are not new NPU measurements.
- The memory manifest is a bounded attribution input, not a live HBM capture.
- Profiler latency is CPU wall-clock for this host, not NPU throughput.
- Only the production read-only analyze/compare/attribute paths are exercised.

| Observation | Baseline samples | Candidate samples |
| --- | --- | --- |
| analyze_latency_ms | unmeasured, unmeasured, unmeasured | 7.567, 5.699, 5.417 |
| attention_delta_ms | unmeasured, unmeasured, unmeasured | 0.018, 0.018, 0.018 |
| comm_delta_ms | unmeasured, unmeasured, unmeasured | -0.008, -0.008, -0.008 |
| compare_latency_ms | unmeasured, unmeasured, unmeasured | 0.158, 0.133, 0.131 |
| comparison_status | unmeasured, unmeasured, unmeasured | comparable_with_limitations, comparable_with_limitations, comparable_with_limitations |
| db_mutation | unmeasured, unmeasured, unmeasured | False, False, False |
| known_sum_bytes | unmeasured, unmeasured, unmeasured | 9900000000.000, 9900000000.000, 9900000000.000 |
| memory_latency_ms | unmeasured, unmeasured, unmeasured | 0.149, 0.108, 0.089 |
| memory_target_met | unmeasured, unmeasured, unmeasured | True, True, True |
| msprof_reference_not_added | unmeasured, unmeasured, unmeasured | True, True, True |
| profile_steps_aligned | unmeasured, unmeasured, unmeasured | True, True, True |
| raw_arithmetic_matches_report | True, True, True | unmeasured, unmeasured, unmeasured |
| residual_bytes | unmeasured, unmeasured, unmeasured | 50000000.000, 50000000.000, 50000000.000 |
| residual_status | unmeasured, unmeasured, unmeasured | within_target, within_target, within_target |
| slow_link_dominant_block | unmeasured, unmeasured, unmeasured | Comm, Comm, Comm |
| slow_rank_dominant_block | unmeasured, unmeasured, unmeasured | Attention, Attention, Attention |

## sim

Scenario: real A3 physical-calibration predict, finite operator planning and subgraph boundary gates (3 repetitions).

- Predicted TTFT includes no client/scheduler floor; its absolute error is recorded, not hidden.
- The Qwen physical calibration artifact is a checked-in public fixture, not a new NPU measurement.
- Operator-plan and subgraph inputs are synthetic arithmetic fixtures.
- Latency is CPU wall-clock for these pure-Python calls, not device throughput.

| Observation | Baseline samples | Candidate samples |
| --- | --- | --- |
| a3_graph_tpot_ms | unmeasured, unmeasured, unmeasured | 15.060, 15.060, 15.060 |
| a3_graph_ttft_ms | unmeasured, unmeasured, unmeasured | 17.339, 17.339, 17.339 |
| graph_tpot_ms | 15.710, 15.710, 15.710 | unmeasured, unmeasured, unmeasured |
| graph_ttft_ms | 50.850, 50.850, 50.850 | unmeasured, unmeasured, unmeasured |
| operator_plan_elapsed_ms | unmeasured, unmeasured, unmeasured | 0.055, 0.055, 0.055 |
| operator_plan_latency_ms | unmeasured, unmeasured, unmeasured | 6.151, 4.227, 3.877 |
| output_tokens | 32, 32, 32 | unmeasured, unmeasured, unmeasured |
| prompt_tokens | 128, 128, 128 | unmeasured, unmeasured, unmeasured |
| qwen_case_deterministic | unmeasured, unmeasured, unmeasured | True, True, True |
| qwen_prediction_latency_ms | unmeasured, unmeasured, unmeasured | 83.623, 102.771, 81.618 |
| subgraph_critical_path_saving_us | unmeasured, unmeasured, unmeasured | 5.000, 5.000, 5.000 |
| subgraph_overflow_latency_ms | unmeasured, unmeasured, unmeasured | 0.045, 0.034, 0.034 |
| subgraph_overflow_rejected | unmeasured, unmeasured, unmeasured | True, True, True |
| subgraph_removable_gm_bytes | unmeasured, unmeasured, unmeasured | 2097152.000, 2097152.000, 2097152.000 |
| subgraph_screen_latency_ms | unmeasured, unmeasured, unmeasured | 0.137, 0.070, 0.058 |
| tpot_absolute_error_ms | unmeasured, unmeasured, unmeasured | -0.650, -0.650, -0.650 |
| tpot_error_pct | unmeasured, unmeasured, unmeasured | -4.139, -4.139, -4.139 |
| ttft_absolute_error_ms | unmeasured, unmeasured, unmeasured | -33.511, -33.511, -33.511 |
| ttft_error_pct | unmeasured, unmeasured, unmeasured | -65.901, -65.901, -65.901 |

# mindie-agent/sim 0.7.0


Version: 0.0.3. Suite: `product-value-v0.0.3-components`. Evidence: complete.

Each row compares the same tasks and model (different models are never averaged). Paired timing ratios (`baseline / candidate`) use only pairs solved by both conditions; all failed, incomplete, and historical attempts remain in the inventory and resource totals.

Repeated component scenarios; no model-productivity claim.

Repeated component value scenarios executed against exact non-editable 0.0.3 formal releases.

0.0.3 value-suite verifies the 5 repeatable component value scenarios (coordinator, npu-top, diagnostics, profiler, sim) against exact non-editable 0.0.3 formal releases alongside 12-repository release benchmarks.

- **Conditions**: **G0** uses the native host; **G1** adds `remote-dev`; **G2** adds `knowledge` retrieval, shipped Skills, and explicit retrieval guidance on top of G1; **G3** captures an earlier seed task's experience for later evaluation tasks.
- **Key Takeaways**: `remote-dev` (G0 → G1) solved `3/3` `quarot` runs with a `1.025x` delivery speedup and matched baseline on `dp2` (`0.963x`); `coordinator` eliminated port and device conflicts (`3 → 0`) and doubled active listeners (`3 → 6`) under concurrent contention; `knowledge` + Skills (G2/G3) increased completed tasks on `dp2` and `dsh` (`2/3 → 3/3`) and hit captured seed experience in `5/6` transfer tasks, while retrieval and context-reading latency is targeted for optimization in `0.0.3`.

| Study | Model | Observed / planned | Pass | Fail | Infrastructure | Unknown |
| --- | --- | ---: | ---: | ---: | ---: | ---: |

## Measurement versions and scope

Release runner: `mindie-bench` 0.4.1 (`994b48e410f8dec989e26130b6e52fc5a6b569d2`). Task evaluations ran on the historical runner revisions listed below; later changes in `0.3.0` cover cleanup, provenance checks, and report publication without rewriting task inputs, models, budgets, or recorded attempt costs.

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

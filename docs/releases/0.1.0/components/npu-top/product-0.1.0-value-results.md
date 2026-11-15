# mindie-agent/npu-top 0.2.1


Version: 0.1.0. Suite: `product-value-v0.1.0-components`. Evidence: complete.

Each row compares the same tasks and model (different models are never averaged). Paired timing ratios (`baseline / candidate`) use only pairs solved by both conditions; all failed, incomplete, and historical attempts remain in the inventory and resource totals.

Repeated component scenarios; no model-productivity claim.

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

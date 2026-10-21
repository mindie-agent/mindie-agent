# mindie-agent/coordinator 0.6.2


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

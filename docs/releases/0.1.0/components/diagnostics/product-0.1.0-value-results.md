# mindie-agent/diagnostics 0.5.1


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

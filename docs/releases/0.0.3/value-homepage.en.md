<!-- mindie-value-results:start -->
### 0.0.3 measured results

Small-sample results on the fixed task suite (reported separately by host, model and comparison, never averaged across models): `remote-dev` (G0 → G1) solved `3/3` `quarot` runs with a `1.025x` speedup and matched baseline on `dp2` (`0.963x`); `coordinator` eliminated port and device conflicts under concurrent contention; `knowledge` + Skills (G2/G3) increased solved tasks on `dp2` and `dsh` and validated cross-task reuse, with retrieval latency targeted for optimization in `0.0.3`.

**Conditions**: **G0** native host; **G1** adds `remote-dev` remote execution; **G2** adds `knowledge` retrieval, shipped Skills and explicit retrieval guidance on top of G1; **G3** captures an earlier task's experience on top of G2 for later tasks.

| Study / host / model | Repeats per task | Pair | Baseline solved/attempts | Candidate solved/attempts | Delivery-time ratio (baseline/candidate) | Mutually solved pairs |
| --- | ---: | --- | ---: | ---: | ---: | ---: |

Note: Solved/attempts counts the selected settled runs (with failures in the denominator). Timing ratios use only pairs solved by both sides: `> 1.0x` means the candidate was faster; `< 1.0x` means slower. Verified over-budget completions remain included; the full report shows budget observations separately, and missing meters do not establish compliance.

**Component scenarios**

- npu-top: 3 hardware-capture replay runs; 24 physical devices and 16/16 process assignments identified per run; live container-owner checks passed 3/3. Human accuracy: not measured; task time (s): not measured (capture replays verify parser determinism rather than independent hardware samples).
- coordinator: 3 concurrent two-agent contention runs; successful listeners 3 → 6, port conflicts 3 → 0, duplicate device selections 3 → 0 (compared against an uncoordinated check-then-act baseline).
- diagnostics: 3 local HTTP reporting runs deduplicated 9 faults into 3 reports and 3 POSTs; key fault fields retained 3/3, privacy redaction 3/3, requests stopped after consent withdrawal 3/3. Delivery took 61.62-61.66 s (including the ~60 s production retry wait; local HTTP does not measure GitHub availability or human triage time).
- profiler: 3 deterministic SQLite attribution runs; step alignment 3/3, slow-rank (Attention) vs slow-link (Comm) separated, memory attribution target met 3/3, read-only DB immutability 3/3, analyze latency 5.42-7.57 ms (fixture replay verifies attribution accuracy rather than new hardware captures).
- sim: 3 A3 physical-calibration graph prediction and operator/subgraph screening runs; Qwen2.5-7B graph prediction determinism 3/3 (TPOT relative error 4.14%), UB overflow fusion rejected 3/3, feasible fusion critical-path saving 5.0 us (anchored on published calibration fixtures without client scheduler floor).

[Full benchmark report, condition definitions and cost records](docs/releases/0.0.3/value-results.md) retain original failures, unknown outcomes, historical attempts and targeted retests. Setup and diagnostic model usage is accounted for separately from task evaluations.
<!-- mindie-value-results:end -->

# Historical Architecture & Wave Archive (`docs/archive/`)

[返回文档导航 (`docs/README.md`)](../README.md) · [Back to Documentation Index (`docs/README.en.md`)](../README.en.md)

This directory preserves **completed execution plans, point-in-time architecture reviews, migration records, and early design explorations** from baseline commit `02a1d371`.

## Archive Governance Rules

1. **Historical Provenance Only (Non-Gate)**: Files under `docs/archive/**` are frozen snapshots excluded from `sync_org_versions.py` / `sibling_readme_sync.py` version rewriting. Never treat historical wave checklists or retired layouts inside `docs/archive/` as active engineering rules.
2. **Active Living Specifications Stay in `docs/`**: All active operational invariants—including `historical-issues-and-guardrails{.en}.md`, `architecture{.en}.md`, `design-principles{.en}.md`, `harness-boundary-and-lifecycle{.en}.md`, `knowledge-system{.en}.md`, `diagnostics-and-reporting{.en}.md`, `profiler-system{.en}.md`, `simulation-system.md`, `testing-architecture{.en}.md`, and `release-compatibility-and-update{.en}.md`—live directly under `docs/`.
3. **Immutable Release & Channel Audit Paths**: Formal release notes (`docs/releases/**`) and `channels/0.1.json`-referenced audit records (`docs/audits/**`) remain at their canonical paths untouched.

## Archived Documents & Living Successors

| Archived Snapshot | Original Scope | Current Living Specification |
| --- | --- | --- |
| [`architecture-simplification-20261023.md`](architecture-simplification-20261023.md) · [`architecture-review-20261024.md`](architecture-review-20261024.md) | Oct 2026 architecture simplification & follow-up review | [`docs/architecture.md`](../architecture.md) |
| [`core-implementation-and-geak-evolution-design.md`](core-implementation-and-geak-evolution-design.md) | Early GEAK core implementation & RSI evolution design | [`docs/harness-boundary-and-lifecycle.md`](../harness-boundary-and-lifecycle.md) |
| [`knowledge-context-and-exploration.md`](knowledge-context-and-exploration.md) ([EN](knowledge-context-and-exploration.en.md)) | Detailed exploration of `category` vs. `L1–L4` grading & RSI context | [`docs/knowledge-system.md`](../knowledge-system.md) ([EN](../knowledge-system.en.md)) |
| [`knowledge-invocation-recovery.md`](knowledge-invocation-recovery.md) ([EN](knowledge-invocation-recovery.en.md)) | Incident recovery design for host invocation, UTF-8 pipes & PE GUI validation | [`docs/harness-boundary-and-lifecycle.md`](../harness-boundary-and-lifecycle.md) ([EN](../harness-boundary-and-lifecycle.en.md)) |
| [`knowledge-tiered-testing-plan.md`](knowledge-tiered-testing-plan.md) | Initial 4-tier testing rollout plan for `knowledge` | [`docs/testing-architecture.md`](../testing-architecture.md) |
| [`mechanism-first-performance-modeling-design.md`](mechanism-first-performance-modeling-design.md) · [`a3-performance-modeling-plan.md`](a3-performance-modeling-plan.md) · [`a3-performance-modeling-acceptance.md`](a3-performance-modeling-acceptance.md) · [`a3-model-coverage.md`](a3-model-coverage.md) · [`a5-communication-calibration-todo.md`](a5-communication-calibration-todo.md) · [`simulation-consumer-migration.md`](simulation-consumer-migration.md) | Mechanism-first simulation waves, A3 modeling acceptance, A5 calibration TODO & `0.8 -> 0.9` consumer migration | [`docs/simulation-system.md`](../simulation-system.md) |
| [`profiler-sim-structure.md`](profiler-sim-structure.md) | Early `profiler` <-> `sim` structure contract draft | [`docs/profiler-system.md`](../profiler-system.md) |
| [`operator-workflow.md`](operator-workflow.md) · [`next-steps.md`](next-steps.md) ([EN](next-steps.en.md)) | Historical operator workflow notes & milestone next-steps | [`docs/architecture.md`](../architecture.md) ([EN](../architecture.en.md)) |

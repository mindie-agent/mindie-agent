# MindIE Agent Code Quality Audit · 2026-10-20

[中文](README.md) · [33 review items](findings.en.md) · [Per-file baseline data](baseline.json) · [Documentation index](../../README.en.md)

This round completed the scan, execution of existing tests, coverage measurement, and a change plan. No business implementation, existing tests, or project dependency locks were modified. The highest-priority risks concern receipt ownership, incremental log capture and budgets, configuration defaults, remote path boundaries, and process cleanup. Most issues occur in interleavings or boundary cases that existing assertions do not cover; passing tests do not establish correctness in those scenarios.

This report is a historical audit of fixed versions. It does not imply that the current main branches contain fixes or that product acceptance is complete. The documentation PR is based on the updated architecture repository main branch; the audit SHAs below remain unchanged. This public edition retains results, commands, code references, and gaps. Raw execution logs, coverage databases, machine connection details, and local reproduction tools remain local and are not public attachments. Conclusions supported only by local logs must not be described as independently verified by a third party.

## A. Repositories and Core Flows

The organization directory contained 21 repositories. The scan covered 15 nonempty repositories, reusing the existing architecture repository checkout and using isolated checkouts for the rest. All SHAs below were on `main` at the time of the scan. Source code and existing tests had no tracked changes at the end of the audit.

| Repository | Responsibility | Audited commit |
| --- | --- | --- |
| mindie-agent | Architecture and design documentation | [bc17f3095cdf3cc16bfb1e803a839fd4ad71686b](https://github.com/mindie-agent/mindie-agent/commit/bc17f3095cdf3cc16bfb1e803a839fd4ad71686b) |
| .github | Organization contribution guidelines and templates | [a22e53165e98e5313ebd2cfd4313b427b3d67f49](https://github.com/mindie-agent/.github/commit/a22e53165e98e5313ebd2cfd4313b427b3d67f49) |
| awesome-mindie-skills | Skill catalog and maintenance scripts | [64c2457d0b05e89c0a0808896a3e10960f536c53](https://github.com/mindie-agent/awesome-mindie-skills/commit/64c2457d0b05e89c0a0808896a3e10960f536c53) |
| coordinator | Environment, container, and lease coordination | [c77144a95dd6af37e978ffc2d8495158b237090d](https://github.com/mindie-agent/coordinator/commit/c77144a95dd6af37e978ffc2d8495158b237090d) |
| diagnostics | Logging, diagnostics, and profiler | [6460cde3a50a7f91c9ded38557a7f921654f0c6a](https://github.com/mindie-agent/diagnostics/commit/6460cde3a50a7f91c9ded38557a7f921654f0c6a) |
| knowledge | Retrieval, capture, redaction, and publishing | [021ba95e701d4f8c8d924e2dcc8f120a4939da23](https://github.com/mindie-agent/knowledge/commit/021ba95e701d4f8c8d924e2dcc8f120a4939da23) |
| knowledge-vllm-ascend | Public knowledge content and validation contracts | [85ab134f333b06ac3873df6affbf3bf6ec71978c](https://github.com/mindie-agent/knowledge-vllm-ascend/commit/85ab134f333b06ac3873df6affbf3bf6ec71978c) |
| mindie-agent-cc | Claude Code host adapter | [78f34dd9b09e877298225fa243ea4c28978c9dd6](https://github.com/mindie-agent/mindie-agent-cc/commit/78f34dd9b09e877298225fa243ea4c28978c9dd6) |
| mindie-agent-codex | Codex host adapter | [f1acb69ba336f75ae2d909443ca118835b038b9c](https://github.com/mindie-agent/mindie-agent-codex/commit/f1acb69ba336f75ae2d909443ca118835b038b9c) |
| mindie-agent-dsh | DSH host adapter | [d3a1e1282356b65b51fba49072c1842918746f8f](https://github.com/mindie-agent/mindie-agent-dsh/commit/d3a1e1282356b65b51fba49072c1842918746f8f) |
| mindie-agent-kimi | Kimi host adapter | [0e78f0422162a61e8c56850e049f9e5fc4d290b5](https://github.com/mindie-agent/mindie-agent-kimi/commit/0e78f0422162a61e8c56850e049f9e5fc4d290b5) |
| mindie-bench | Evaluation orchestration, gateway, and verifiers | [b7301839602ad3791af17f21f5aa47d773b5af2a](https://github.com/mindie-agent/mindie-bench/commit/b7301839602ad3791af17f21f5aa47d773b5af2a) |
| npu-top | Collection scheduling, history, and Web/MCP | [8f992bf033af57979d6bebf67189a89bb2034d7e](https://github.com/mindie-agent/npu-top/commit/8f992bf033af57979d6bebf67189a89bb2034d7e) |
| remote-dev | SSH/MCP files, search, and managed jobs | [c3af104c36582c675a6dcd368637db7c60b28afd](https://github.com/mindie-agent/remote-dev/commit/c3af104c36582c675a6dcd368637db7c60b28afd) |
| vllm-ascend-workspace | Git/worktree scaffolding | [c85b9ca94c5432a58f3e0bff6bbbcd5d711d8ca8](https://github.com/mindie-agent/vllm-ascend-workspace/commit/c85b9ca94c5432a58f3e0bff6bbbcd5d711d8ca8) |

Excluded: the 6 empty repositories `knowledge-operators`, `knowledge-infer-core`, `knowledge-infer-distributed`, `knowledge-infer-observability`, `knowledge-infer-ops-compat`, and `knowledge-agent-engineering` had no source to test. Knowledge articles, images, templates, and publishing scripts embedded in CI are outside the runtime denominator. ReMe, LangMem, the MCP SDK, vLLM/vLLM-Ascend, models, and drivers were not audited as project-owned code. The scaffolding repository's large third-party submodules were not fully initialized.

Applicable AGENTS.md files, READMEs, design principles, testing guidelines, project declarations, lockfiles, and existing CI were read according to repository responsibilities. The scan focused on actual entry points and risk-bearing flows; it does not claim exhaustive line-by-line review. Function length and decision-node counts were used only to identify candidates, not as evidence of defects. No code was classified as dead solely because a static search found no references.

### Actual Dependency Versions

| Dependency relationship | Version evidence and limits of the conclusion |
| --- | --- |
| Four host adapters → shared runtimes | knowledge `0.12.2@4e328305323eafc7fd43ecc0c53eb3cc0541fdef`; remote-dev `0.10.1@a6649222aae4851deec5774513f8319aece09051`; diagnostics `0.4.3@1b5a0eeb79d498c39002fc1853271c17e0f26e66`. Plugin tests ran with the locked dependencies. |
| knowledge main → diagnostics | Still pins diagnostics `1b5a0eeb`; ReMe `4c54c2b650038eff2a5d0d77aaa61b3e836f1b18`; LangMem `0.0.30`. The profiler on diagnostics main is outside the flow currently used by the plugins. |
| coordinator main → remote-dev | remote-dev `c3af104c36582c675a6dcd368637db7c60b28afd`; the three remote-operation repositories use diagnostics `6460cde3a50a7f91c9ded38557a7f921654f0c6a`, matching the scanned version. |
| Knowledge content CI → validator | knowledge `b1d8d9278a60394f0de28aa2986d02e0ecb8b115`; the 22 modules actually used came from that checkout, but an existing dependency environment was reused. This is not equivalent to validating the complete CI installation with its pinned wheels. |
| Host peer fixtures | The final Codex run set Kimi to `90f73e76c6087ce091570f2d151b709145c913bc` and CC to `3e36a285e2effe47bc442079a4ed7f42ced9caaf`. Existing tests did not read the peer implementations; they only forwarded environment variables or reused shared configuration. Passing these tests therefore does not establish compatibility between host implementations. |

### Core Flows

| Flow | Entry, processing, state, external calls, results, and errors | Findings |
| --- | --- | --- |
| Binding and experience capture | Hook/MCP → identity claim → public transcript and cursor → consent/admission/SQLite in knowledge.accept_stop → worker redaction and indexing → publish receipt; rejecting replays and reporting errors must not corrupt the original owner's state. | ADP-01–06, K-01–03 |
| Knowledge retrieval | MCP/CLI → Store.query → query_request → MaterialStore/ReMe → current-reference resolution and body reads; invalid input should fail before index I/O. | K-05, KD-R3 |
| Remote tools | MCP input → endpoint/root → file, search, or job worker → SSH/remote process → submission_state and result; all matches must respect directory scope. | RD01, RF01, D02 |
| Environments and leases | CLI/MCP → machines registry → service/backend → host queue/lease/probe → remote-dev; corrupt configuration must not appear to mean that no resources exist. | CO01, RF02, D01, D03 |
| Monitoring | Viewer heartbeat/live API → scheduler → probe → cache/history → Web/MCP; result freshness must satisfy the request's semantics. | NP01, NP02 |
| Diagnostics | Event → redaction/allowlist → bundle → consent/reporting; profiler producer → compare → CLI exit code. Failures and non-comparable results must remain visible. | D-01–04, KD-R1/2/4 |
| Evaluation | Task recipe → run_trial → gateway/host/lease → verifier → score/capture/cleanup → receipt; preserve the primary result and uncertain external effects. | B01–03, B05/06 |
| Development scaffolding | CLI → Git/worktree/directory changes → metadata and exit code. | B04 |

## B. Test and Coverage Baseline

Environment: macOS 26.4 arm64, Python 3.13.16, uv 0.13.3, pytest 9.1.1, and coverage.py 7.16.2. The table reports actual local Tier 0 + Tier 1 execution. Most repositories lack stable T0/T1 markers, so these results cannot be presented separately as pure in-memory unit coverage or independent component coverage. Subtests are excluded from the top-level passed count. Coverage runs used `patch = subprocess`; durations include instrumentation overhead.

| Repository | Result (local selection) | Wall seconds | Production line coverage | Production branch coverage |
| --- | --- | --- | --- | --- |
| knowledge | 1188 passed, 20 skipped, 1 deselected, 2 warnings, 3 subtests passed in 485.40s (0:08:05) | 486.585 | 11104/13135 (84.54%) | 3510/4748 (73.93%) |
| diagnostics | 580 passed, 30 skipped, 1 warning in 14.48s | 14.775 | 11066/14034 (78.85%) | 3688/5444 (67.74%) |
| remote-dev | 623 passed, 42 skipped, 4 deselected, 254 subtests passed in 52.16s | 53.045 | 4297/6513 (65.98%) | 1250/2304 (54.25%) |
| coordinator | 1339 passed, 29 skipped, 4 deselected, 55 warnings, 63 subtests passed in 176.11s (0:02:56) | 176.558 | 10616/13060 (81.29%) | 3783/5382 (70.29%) |
| npu-top | 219 passed, 2 skipped, 5 deselected, 60 subtests passed in 7.55s | 8.805 | 3392/4214 (80.49%) | 995/1430 (69.58%) |
| mindie-agent-codex | 448 passed, 18 skipped, 2 deselected, 1 warning, 475 subtests passed in 108.12s (0:01:48) | 109.317 | 4532/5612 (80.76%) | 1419/2026 (70.04%) |
| mindie-agent-cc | 324 passed, 2 skipped, 2 deselected, 1 warning, 85 subtests passed in 64.69s (0:01:04) | 65.788 | 3626/4943 (73.36%) | 1120/1848 (60.61%) |
| mindie-agent-kimi | 317 passed, 3 skipped, 1 warning, 20 subtests passed in 154.62s (0:02:34) | 155.403 | 3597/4816 (74.69%) | 1071/1694 (63.22%) |
| mindie-agent-dsh | 31 passed, 2 subtests passed in 5.69s | 7.376 | 776/1410 (55.04%) | 171/432 (39.58%) |
| mindie-bench | 878 passed / 1 failed / 22 runtime skipped; 1 module skipped during collection (2 functions not collected); 1 live deselected | 181.406 | 7145/9087 (78.63%) | 2590/3638 (71.19%) |
| vllm-ascend-workspace | 4 unittest passed / 0 failed / 0 skipped | 8.04 | 97/208 (46.63%) | 33/82 (40.24%) |

The numerators are executed statement lines and executed branch arcs, respectively. The denominators are all executable statement lines and all branch arcs within the configured scope. Coverage's combined `percent_covered` metric was not used as line coverage. `baseline.json` provides each file's numerators, denominators, missing lines/branches, and excluded lines; negative branch destinations denote function exits. These line/branch results must not be confused with coverage of test files.

### Denominators and Collection Scope

| Repository | Production scope | Tracked / measured Python files | Excluded lines |
| --- | --- | --- | --- |
| knowledge | mindie_knowledge | 73 / 73 | 3 |
| diagnostics | mindie_diagnostics, mindie_profiler | 66 / 66 | 7 |
| remote-dev | remote_dev | 73 / 73 | 0 |
| coordinator | mindie_coordinator | 58 / 58 | 0 |
| npu-top | npu_top | 25 / 25 | 0 |
| mindie-agent-codex | plugins/mindie-agent/scripts | 43 / 43 | 0 |
| mindie-agent-cc | scripts | 30 / 30 | 0 |
| mindie-agent-kimi | scripts | 24 / 24 | 0 |
| mindie-agent-dsh | scripts | 10 / 10 | 2 |
| mindie-bench | src, scripts | 75 / 75 | 0 |
| vllm-ascend-workspace | .agents/scripts | 2 / 2 | 0 |

All Python files within scope, including those never imported, are included in the denominators. The file inventory check found no omissions and no test files mixed in. Configurations using the default Protocol/pragma exclusions differ from configurations that explicitly clear exclusions. The original configurations are retained in JSON; comparisons must use the same configuration. Python embedded in strings counts only as its outer assignment, not as a denominator for the embedded source. Remote scripts, `python -I`, background processes that replace their environment, other interpreters, forcibly killed processes, and code copied to temporary locations may still fail to return coverage data. Zero collected coverage does not establish that code has no tests or is dead, and local Python percentages cannot be extrapolated to JavaScript/TypeScript, devices, or remote runtimes.

knowledge combined 49 valid data fragments and skipped 177 duplicates. diagnostics combined 14, skipped 3 duplicates, and had 1 additional invalid fragment whose attribution was not confirmed. The diagnostics figures are therefore measured lower bounds based on readable data. The complementary bench host and actual selections used the same SHA, dependencies, and coverage configuration; their executed line/branch sets were combined by union. Repeated module-level collection skips count once; runtime skips total 12 + 10.

### Failures, Follow-up Runs, and Unmeasured Scope

- **bench still has 1 failure**: `test_native_mcp_readiness` used local Codex `0.162.0-alpha.17.2` and failed while synchronizing managed configuration before any model turn. A run without instrumentation failed in the same way. Local configuration and read-only preference probes were checked, but the root cause remains unresolved. It cannot be directly classified as a product defect or relabeled as a skip.
- **14 optional bench cases passed in an independent follow-up**: 9 CPU/torch judges, 4 fixed historical configurations, and 1 local real FastMCP scenario; pytest took 25.54 seconds and wall time was 25.860 seconds. This independent selection measured 1410/9084 lines (15.52%) and 216/3632 branches (5.95%), with 75/75 files in the denominator. Its default Protocol exclusions differed from the original baseline (3 fewer methods and 6 fewer physical lines; statement denominator differed by 3 and branch denominator by 6), and its dependency environment also differed, so it was not merged into the main baseline. The original runtime skips still include 4 Claude CLI, 2 Kimi CLI, and 2 Linux-native scenarios because binaries or platform conditions were unavailable. Two additional component-value scenarios remain uncollected because their shared interpreter requires conflicting exact diagnostics dependencies (B06).
- **The initial coordinator environment contamination was identified**: audit-provided GIT_AUTHOR/COMMITTER environment variables overrode the test's own identity, causing 1 failure. An A/B check confirmed this. The run was changed to isolated default Git configuration that allowed fixture-local configuration to override it, yielding 1339 passed. Source and tests were unchanged, and the original failure record was retained.
- **Early Codex/Kimi instrumentation runs had cleanup errors**: Codex encountered PermissionError in `killpg` once, after the business assertions; Kimi encountered a temporary Git directory cleanup failure once. Both final full instrumented runs passed. The final Codex pass does not prove that the original exception's root cause has disappeared. The first targeted Kimi run failed collection because the test support module path was missing; it passed after setting the existing `tests` pythonpath, without changing tests.
- **Tier 2 was not measured**: read-only SSH probes encountered banner timeouts or lacked a trusted host key; host-key verification was not bypassed. Follow-up requires running `-m live_npu` in a trusted environment with an isolated state_dir, confirming that active tasks are unaffected, and then collecting remote coverage for the same SHA.
- **Tier 3 and real model quality were not measured**: local host tests are not equivalent to full CLI E2E. No paid model calls or real external publishing were executed. Historical Release benchmarks are excluded from this round. Follow-up should pin supported CLIs/models and run dedicated canaries and summary-quality datasets with human-reviewable criteria.
- **Frontend/content**: npu-top lint/build passed (1.16/1.97 seconds), with no behavioral coverage. DSH's 1 Node test passed but executed only some host modules; full JS coverage was not measured. The workspace's 4 tests cover only repo_init.py; workspace.py has 0/103 lines and 0/40 branches covered.
- **Catalog validation**: validation passed for 53 skills, 10 categories, 2 sources, and 223 links. The knowledge validator at its exact pin validated 663 entries, 1 feedback item, and 23,079,976 bytes in 9.397 seconds. The simulated push event used base=head, establishing only that static snapshot; it is not acceptance of incremental publishing/E2E or model quality.

Failure/skip nodes and their reasons are retained in JSON under `test_exceptions`. Bench records are retained by run and must not be summed directly. Skips for three 10MB benchmarks, native Windows semantics, unavailable host CLIs and live environments, and other missing conditions must not count as passes.

### Reproducible Commands

First check out the exact SHAs in the repository table. Install exact plugin components from the original uv.lock/Kimi runtime-requirements, and create isolated runtime environments from each repository's original lock/declarations. Installing measurement tools `coverage==7.16.2` and `pytest==9.1.1` additionally must not modify project locks. Create separate environments for different diagnostics pins; do not use `--no-deps` to assemble unsupported combinations. Bench CPU/stale tasks also require their respective original locks and the historical source specified by each recipe.

The `plain_run` / `coverage_run` / `complementary_run` fields in `baseline.json` record exact arguments, exit codes, environment overrides, and durations; `coverage_config` records this round's configuration. `${AUDIT_ROOT}` is a temporary directory chosen by the reader. Its `repos/`, `tools/`, `pinned/`, output directories, and corresponding virtual environments must be created first; it is not a ready-made download bundle. Placeholders in the JSON command arrays and configuration must be expanded; do not pass unexpanded strings directly as arguments.

The following illustrate the command structure. Consult JSON for each repository's actual source scope, selectors, dependencies, and additional variables:

```bash
# Run in the corresponding exact checkout after activating the isolated Python 3.13.16 environment above.
# Expand local paths in JSON's coverage_config and save it as audit.coveragerc.
python -m coverage run --rcfile=audit.coveragerc -m pytest -q tests -m 'not live_npu'
python -m coverage combine --rcfile=audit.coveragerc --keep
python -m coverage json --rcfile=audit.coveragerc -o coverage.json
# Run the two bench selections with the same configuration and different data_file values, then combine by set union.
python -m coverage run --rcfile=audit.coveragerc -m pytest -m 'not live_npu' -k 'not actual' -ra
python -m coverage run --rcfile=audit.coveragerc -m pytest -m 'not live_npu' -k actual -ra
# Existing workspace test entry point:
python -m coverage run --rcfile=audit.coveragerc -m unittest discover -s .agents/scripts/tests -v
```

Before running coordinator, remove the four audit-injected GIT_AUTHOR/COMMITTER variables and any external REMOTE_DEV_STATE_DIR. Use an isolated `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_NOSYSTEM=1`, with a test-only default identity that fixtures can override through repository-local configuration. Do not modify personal Git configuration. The knowledge checkout used by plugin runs points to the actual pin; see the table above for Codex peer SHAs. The person rerunning the tests must create the one-off fixture/output directories; these local files are not committed.

### Key Gaps and Test Effectiveness

The `modules` field in `baseline.json` lists all missing lines and arcs; section C details risk-bearing functions and business scenarios. Representative gaps include an omitted default mode in `accept_stop`, appending to short compressed DSH logs and oversized first records, concurrent bind-owner receipts, glob matches outside the root, idle→active scheduling and in-flight force refresh, missing signatures/null summaries in strict compare, and descendant cleanup after verifier timeouts. In many of these scenarios, existing tests check only getters, types, or fixed fixtures and cannot detect the corresponding incorrect business result.

Valuable component tests should be retained: real SQLite, temporary Git repositories, public-transcript redaction, and reference consistency tests already serve useful purposes. A fixed summary worker cannot establish LLM summary fidelity; Top1 performance on six handcrafted retrieval documents cannot be extrapolated to real retrieval quality. The presence of peer environment variables does not mean peer implementations were read. Additional tests must assert business results, key state changes, and error propagation. The specific regressions they should catch are described item by item in the detailed review, avoiding filler tests that assert only types, constants, or call counts.

## C. Review Items Ordered by Priority

See the [33 detailed review items](findings.en.md) for complete file/function/line references, triggers, evidence, impact, proposed changes, verification, certainty, and the five defensive-code questions. P1 covers core state/boundaries, continuing side effects, or critical collection blind spots; P2 covers error semantics and important testing/structural issues; P3 covers behavior-preserving cleanup or candidates awaiting contract confirmation.

| ID | Priority | Repository | Category |
| --- | --- | --- | --- |
| [ADP-01](findings.en.md#adp-01) | P1 | mindie-agent-cc; mindie-agent-kimi | Correctness defect: concurrent replay corrupts the original operation's receipt |
| [ADP-02](findings.en.md#adp-02) | P1 | mindie-agent-dsh | Correctness defect: appended logs are misclassified as replacements |
| [ADP-03](findings.en.md#adp-03) | P1 | mindie-agent-dsh | Correctness defect and refactoring: scan budgets are not enforced |
| [ADP-04](findings.en.md#adp-04) | P1 | mindie-agent-dsh | Correctness defect: candidate staging shares the active runtime |
| [B01](findings.en.md#b01) | P1 | mindie-bench | Confirmed defect: process lifecycle |
| [D02](findings.en.md#d02) | P1 | remote-dev | Defensive code to retain |
| [D03](findings.en.md#d03) | P1 | coordinator | Defensive code to retain |
| [K-01](findings.en.md#k-01) | P1 | knowledge | Confirmed defect: a legacy compatibility branch bypasses the constraint against persisting raw text |
| [RD01](findings.en.md#rd01) | P1 | remote-dev | Confirmed defect: directory-scope contract |
| [T01](findings.en.md#t01) | P1 | remote-dev + coordinator + npu-top | Confirmed test-baseline gap |
| [ADP-05](findings.en.md#adp-05) | P2 | mindie-agent-dsh | Error semantics and redundant recovery logic |
| [ADP-06](findings.en.md#adp-06) | P2 | mindie-agent-cc; mindie-agent-kimi | Error-semantics defect: local receipt write failures are silently swallowed |
| [B02](findings.en.md#b02) | P2 | mindie-bench | Confirmed testing gap |
| [B03](findings.en.md#b03) | P2 | mindie-bench | Refactoring recommendation |
| [B04](findings.en.md#b04) | P2 | vllm-ascend-workspace | Confirmed testing gap |
| [B06](findings.en.md#b06) | P2 | mindie-bench | Confirmed test-environment contract gap: optional component scenarios require an incompatible combination in a shared interpreter |
| [CO01](findings.en.md#co01) | P2 | coordinator | Confirmed defect: error semantics |
| [D-01](findings.en.md#d-01) | P2 | diagnostics | Confirmed defect: the compare CLI's workload-identity gate differs from the contract |
| [D-02](findings.en.md#d-02) | P2 | diagnostics | Confirmed defect: direct dereference continues after a summary has been identified as invalid |
| [D-03](findings.en.md#d-03) | P2 | diagnostics | Contract awaiting verification: accelerator-memory peaks are reported as comparable without a measurement definition |
| [K-02](findings.en.md#k-02) | P2 | knowledge | Refactoring recommendation: Stop handoff mixes protocol, authorization, persistence, and wakeup |
| [K-03](findings.en.md#k-03) | P2 | knowledge | Test-effectiveness limit: local summary fidelity tests cannot verify model summary fidelity |
| [K-04](findings.en.md#k-04) | P2 | knowledge | Test-baseline gap: live probes uniformly skip remote execution failures |
| [NP01](findings.en.md#np01) | P2 | npu-top | Confirmed defect: refresh scheduling |
| [NP02](findings.en.md#np02) | P2 | npu-top | Confirmed defect: live-result freshness |
| [RF01](findings.en.md#rf01) | P2 | remote-dev | Refactoring recommendation |
| [RF02](findings.en.md#rf02) | P2 | coordinator | Refactoring recommendation |
| [ADP-07](findings.en.md#adp-07) | P3 | mindie-agent-cc | Behavior-preserving cleanup candidate: repeated pure validation |
| [B05](findings.en.md#b05) | P3 | mindie-bench | Compatibility branch awaiting verification |
| [D-04](findings.en.md#d-04) | P3 | diagnostics | Behavior-preserving refactoring recommendation: repeated scans of the same label |
| [D01](findings.en.md#d01) | P3 | coordinator | Behavior-preserving redundancy cleanup |
| [D04](findings.en.md#d04) | P3 | npu-top + remote-dev | Compatibility logic awaiting verification |
| [K-05](findings.en.md#k-05) | P3 | knowledge | Behavior-preserving refactoring candidate: repeated continuation parsing at query boundaries |

Recommended deletions/merges: CC's repeated pure parsing, coordinator's redundant terminal-state predicate, diagnostics' repeated computation for the same label, and knowledge's repeated internal query_request (retaining validation at both public entry points). The old summary fallback, DSH's blind retry, swallowed configuration-read errors, and swallowed accounting errors affect input or failure semantics and should be reviewed separately as correctness fixes.

Explicitly retain: remote real-path constraints, lease fencing/process draining, consent rereads before external transmission, reconciliation of unknown irreversible writes, body membership/hash validation, and diagnostic boundaries that expose logging_failed without overriding the primary result. Insufficient evidence: old peak metadata, MaterialStore capability fallbacks, NFM configuration, remote Python 3.9 support, and public aliases/kwargs. Confirm the support matrix first; lack of coverage or current type annotations alone does not justify deletion.

## D. Batched Change Plan

| Batch / type | Scope and rationale for ordering | Behavioral tests and completion criteria |
| --- | --- | --- |
| 0: Baseline and additional tests | Clarify test tiers, fix collection problems, and include purely local actual scenarios in CI; establish a resolvable component/interpreter contract for B06. | All 11 Python code repositories can be rerun by SHA with stable denominators; preserve failure/skip reasons; per-environment dependency resolution, pip check, and both original component scenarios pass. |
| 1a: Correctness | ADP-01 receipt ownership, ADP-02/03 short logs/budgets, K-01 mode defaults and legacy branch, RD01 root constraints. | Reproduce before fixing: real SQLite interleavings, zstd append/oversized frames, persistence when configuration is validly omitted, and rejection of metadata outside the root; validate the old pin and candidate version separately. |
| 1b: Lifecycle correctness | ADP-04 candidate isolation, B01 process cleanup, NP01 scheduling, NP02 force completion. | stage-only/preparation failure leaves the active generation unchanged; real process trees drain on timeout; controlled-clock and Event tests cover in-flight interleavings; normal performance and output are preserved. |
| 2: Error-semantics fixes | ADP-05 blind recovery, ADP-06 accounting warnings, CO01 configuration errors, D-01/02 profiler failure contracts. Confirm the compatibility policy for D-03 first. | Exceptions retain their original source; successful business operations do not become failures; corrupt input produces defined errors/exit codes; recovery after failure does not repeat external side effects. Document changes affecting callers. |
| 3: Behavior-preserving structural refactoring | Add characterization tests first, then separate pure decisions from I/O in K-02 handoff, RF01 worker, RF02 progress, and B03 run_trial. | Compare complete results/receipts/errors and side-effect counts; retain real process, SQLite, and grep contracts; introduce no parallel persistent state machines. Use a separate PR for each module. |
| 4: Redundancy cleanup | ADP-07, D01, D-04 caching, and K-05 request reuse, ordered by benefit. | Identical input and state produce identical output and error order; privacy-fixture differential checks pass. Establish equivalence before replacing repeated scans with one scan; retain shims without evidence that their support requirements have ended. |
| 5: Platform and quality testing | workspace.py, frontend, real A2/A3 hardware, host E2E, and real summary/retrieval quality. | Business outcomes in temporary Git repositories, UI error states, real devices and PID/lease behavior, and fixed anonymized corpora with human assessment criteria; do not invent percentages before establishing reliable denominators. |

### Per-Module Targets (Future Acceptance Targets, Not Measurements from This Round)

| Module group | Line / branch target | Defects the tests must catch |
| --- | --- | --- |
| Identity, authorization, cursors, privacy, paths | ≥95% / ≥90% | Replay corrupting another owner's receipt, short logs misclassified as replacements, raw-text persistence, enumeration outside the root; cover each defect path identified in this audit. |
| Jobs, services, updates, collection scheduling | ≥90% / ≥85% | Descendants not cleaned up, stage-only changing the active generation, an old cycle presented as force completion. |
| Profiler compare and result aggregation | ≥95% / ≥90% | Missing measurement definitions/fields/null, confusion between failure and unknown; compare against real producers. |
| Bench orchestration and shared lifecycle | Initially ≥85% / ≥80% | Cleanup/accounting overriding the business outcome, blind retries of external side effects; do not lower coverage for modules already above target. |
| workspace.py | ≥85% / ≥80% | Incorrect worktree commits, accidental deletion of dirty worktrees, dry-run changing state, inconsistent metadata links. |
| Hardware, frontend, real models | Not measured this round; establish scenarios and denominators first | Coverage percentages cannot replace device, protocol, and quality acceptance. |

Submit and review correctness fixes, behavior-preserving refactoring, redundancy cleanup, and additional tests separately. This PR records only the baseline and plan; it does not implement the business changes in the table.

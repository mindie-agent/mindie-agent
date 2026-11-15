# Code quality audit findings — 20 October 2026

This register contains all 33 findings from the audit, in priority order. It distinguishes confirmed defects, test and measurement gaps, refactoring proposals, safe cleanup candidates, defenses that should remain, and compatibility questions with insufficient evidence. Priority expresses remediation order; it does not make every entry a defect.

Source references point to immutable audited commits. Cross-repository references identify each repository separately; they do not establish that those versions are deployed together. In particular, the coordinator-to-npu-top HTTP interface is a runtime protocol, and the deployed server version was not established. Python coverage does not establish frontend, remote Linux, hardware, or end-to-end coverage. Unavailable hardware validation and real-model quality remain **not measured**.

Local evidence identifiers below name audit artifacts **retained locally, not published**. They are not public links. Raw logs, private machine identifiers, network addresses, and personal filesystem paths are intentionally omitted. Production implementations and existing tests were preserved during this audit.

<a id="adp-01"></a>

## ADP-01 · P1 · A rejected replay can overwrite the original request's receipt

- **Repositories:** `mindie-agent-cc`, `mindie-agent-kimi`.
- **Location:** `handle`, `finish_bind`, `finish_nonce`. CC: [scripts/mcp_server.py:301–369][cc-mcp], especially 313–315 and 365–369; [scripts/identity.py:324–342][cc-finish]. Kimi: [scripts/mcp_server.py:318–367][kimi-mcp], especially 327–328 and 363–367; [scripts/identity.py:532–547][kimi-finish].
- **Category:** Confirmed correctness defect: concurrent replay corrupts the original operation's receipt.
- **Trigger:** The first request has claimed the receipt and is still executing. A second request with the same `toolUseId` or `request_nonce` is rejected by the claim operation, but its `finally` block still calls `finish(False)`.
- **Evidence and result:** Real SQLite reproductions show `claimed` → duplicate rejected → `failed`. Even when the first request later succeeds, its `UPDATE ... WHERE status = claimed` no longer updates the receipt. Local evidence: `evidence/adapters/repro-cc-bind.json`, `evidence/adapters/repro-kimi-bind.json`, and `scripts/repro_adapter_bind.py` — retained locally, not published.
- **Impact:** The external operation is not executed twice, but its final receipt incorrectly records failure.
- **Recommendation:** Establish receipt ownership only after a successful claim. Only that owner may finalize it; use a claim token in the conditional update if needed. Preserve rejection of concurrent replays.
- **Verification:** Use real SQLite with concurrent or controlled interleaving: block the first business operation, submit a duplicate, assert that the receipt remains `claimed`, then release the first operation and assert `succeeded` and exactly one business execution.
- **Certainty:** Confirmed by execution.

<a id="adp-02"></a>

## ADP-02 · P1 · Appending to a short compressed transcript is mistaken for replacement

- **Repository:** `mindie-agent-dsh`.
- **Location:** `identify`, `read_material`; [scripts/dsh_transcript.py:64–74][dsh-identify] and [191–198][dsh-anchor].
- **Category:** Confirmed correctness defect.
- **Trigger:** The initial compressed log is shorter than 512 bytes. After recording `FileIdentity`, a valid zstd frame is appended, so `expected.anchor_len` is shorter than the newly read anchor.
- **Evidence and result:** A real append from 106 to 213 bytes returns `status=replaced`, leaves `end` unchanged, and returns empty text. The existing [append test:151–164][dsh-append-test] starts with more than 512 bytes and misses this case. Local evidence: `evidence/adapters/repro-dsh-transcript.log` and `scripts/repro_dsh_transcript.py` — retained locally, not published.
- **Impact:** Incremental capture loses this addition or reports a capture error.
- **Recommendation:** Re-read and compare the prefix using `expected.anchor_len`. Equivalent prefix semantics already exist in [CC transcript.py:374–382][cc-transcript-anchor] and [Kimi transcript.py:231–238][kimi-transcript-anchor]. Preserve path, device, inode, and prefix checks.
- **Verification:** Use real zstd data without mocking the parser. Cover repeated appends to an initial log below 512 bytes, an append crossing 512 bytes, actual prefix replacement, and truncation. Assert both captured content and cursor progression.
- **Certainty:** Confirmed by execution.

**Defensive review — retain the defense and repair its implementation.**

1. **Protected risk:** File replacement or rewriting can cause duplicate capture or capture from the wrong task.
2. **Does it exist within support?** Yes. Host logs may be appended or replaced; identity checks remain necessary.
3. **Upstream invariant:** Appending preserves the old prefix. It does not guarantee that the digest of a newly read 512-byte prefix equals the digest of a shorter old prefix.
4. **Behavioral effect:** Valid appends should continue; genuine replacements should still return `replaced`. This is a correctness fix.
5. **Validation:** Exercise short-prefix append and replacement contracts with real files; retain the identity defense.

<a id="adp-03"></a>

## ADP-03 · P1 · Transcript scan budgets do not bound the work or returned material

- **Repository:** `mindie-agent-dsh`.
- **Location:** `_decompress`, `read_material`; [scripts/dsh_transcript.py:92–114][dsh-decompress], [210–226][dsh-read-budget], and [247–259][dsh-project-budget].
- **Category:** Confirmed correctness defect and refactoring opportunity.
- **Trigger:** The first public record exceeds `max_text_bytes`, `max_scan_bytes`, or `scan_until`. Paging a large historical log also decompresses and parses the entire log again, accumulating data with `bytes +=`.
- **Evidence and result:** With a 64-byte text budget, a 128-byte scan budget, and `scan_until=64`, the reproduction still returns 1,000,009 bytes and crosses the boundary. Time checks occur only after full decompression, parsing, and concatenation, so they cannot bound that earlier work. Repeated `bytes +=` is a candidate for quadratic copying. The [adapter instructions][dsh-agents] specify incremental scan limits of `max_seconds=2.0` and `max_text_bytes=48 KiB`. Local evidence: `evidence/adapters/repro-dsh-transcript.log` and `scripts/repro_dsh_transcript.py` — retained locally, not published.
- **Impact:** Oversized messages increase downstream redaction and consolidation work. Slow scans may repeatedly return `unchanged`.
- **Recommendation:** Separate incremental zstd reading, public-record projection, and pagination. Consume budgets while reading and projecting. Define an explicit oversized-record or chunking contract for the first record instead of permitting unbounded output. Align cursor units with the snapshot and `scan_until` contract.
- **Verification:** Cover an oversized first record, large multi-frame history, an incomplete final frame, `scan_until` boundaries, and an injectable clock. Assert byte, time, and cursor limits without lost or duplicated content; checking only types and `more` is insufficient.
- **Certainty:** Confirmed by execution; the copying concern is a refactoring candidate rather than a measured total-runtime claim.

<a id="adp-04"></a>

## ADP-04 · P1 · Staging an update mutates the active shared runtime

- **Repository:** `mindie-agent-dsh`.
- **Location:** `check`, `setup_candidate`, `main`, `sync_runtime`; [scripts/updater.py:268–277][dsh-updater], [scripts/setup.py:113–125][dsh-setup-runtime], [183–196][dsh-setup-stop], [313–334][dsh-setup-main], and [scripts/mindie_paths.py:60–65][dsh-paths].
- **Category:** Confirmed correctness issue in the call path.
- **Trigger:** Automatic update or `--stage-only` preparation invokes the candidate's setup through `setup_candidate`. This happens before checking `apply=False`.
- **Evidence and result:** Candidate setup resolves to the shared `data_home()/venv` and `config_home()/engine.json`: it updates the shared virtual environment, copies capture scripts, stops existing services, and overwrites configuration. The existing [updater tests:38–75][dsh-updater-tests] cover selection, checksum, and extraction only. This conclusion comes from the source call path; the audit did not perform a real installation mutation.
- **Impact:** The old generation is affected before `current.json` switches. Failed preparation or staging alone can leave old JavaScript paired with new Python.
- **Recommendation:** Write the candidate runtime, configuration, and capture scripts into generation-specific paths. Validate them before switching the pointer through one coordinated protocol. Treat shared authorization and persistent knowledge state as explicit external references. A failed preparation must leave the old runtime usable.
- **Verification:** Use component tests with real temporary virtual environments and configuration; local wheels can replace the external download boundary. For stage-only operation and failure at each preparation stage, assert that active runtime/configuration hashes and service identity remain unchanged. After a successful switch, verify that each generation uses its matching components.
- **Certainty:** Call path confirmed; real installation changes were not executed.

<a id="b01"></a>

## B01 · P1 · A local verifier timeout does not reclaim its descendant processes

- **Repository:** `mindie-bench`.
- **Location:** `local_verifier.execute`; [src/mindie_bench/runner/verifier.py:157–178][bench-verifier] and [201–208][bench-verifier-error].
- **Category:** Confirmed defect in process lifecycle management.
- **Trigger:** On macOS, a local verifier or `test.sh` starts a background descendant and then times out. The outer call returns while the descendant survives. Linux bwrap has different PID namespace semantics; this finding does not claim that every platform reproduces it.
- **Evidence and result:** A real macOS `sandbox-exec` reproduction with a 0.2-second timeout returned `TimeoutExpired` after 0.208 seconds. At 0.7 seconds, a descendant still wrote the permitted synthetic marker `profile/tmp/after_timeout.txt`. `subprocess.run` does not create an owned session/process group here; its exception path only rechecks the oracle files. Local evidence: `tools/repro_bench_timeout.py` and `evidence/bench-timeout-reproduction.json` — retained locally, not published.
- **Impact:** A verifier timeout does not prove cleanup. Descendants can continue consuming resources or changing writable directories. `run_trial` classifies an ordinary verifier timeout as `infra_failed` without confirming the absence of residual processes.
- **Recommendation:** Treat this as a correctness fix. Establish ownership of the process group, reserve time for TERM/KILL and draining, and preserve output collected before timeout. If cleanup cannot be confirmed, preserve an unknown outcome; merely renaming the exception is insufficient.
- **Verification:** Run a real short-lived process tree. After timeout, neither children nor grandchildren may remain or write again. Ordinary failure must retain its structured verdict. Cleanup failure must retain separate diagnostics and the original verdict.
- **Certainty:** High; dynamically reproduced inside the real macOS sandbox.

**Defensive review — retain and correct the lifecycle protections.**

1. **Protected risk:** Unknown external effects and orphaned processes after timeout.
2. **Does it exist within support?** Yes; a write after timeout was reproduced.
3. **Upstream invariant:** `native_command` establishes filesystem/network isolation, not descendant cleanup. `subprocess.run` does not promise to terminate descendants, and `run_trial` does not own their process handles.
4. **Behavioral effect:** Do not remove timeout or unknown-state protection. Classifying outcomes after confirmed cleanup changes failure semantics.
5. **Validation:** Verify real process-tree draining, failed cleanup, normal exit, and nonzero exit separately.

<a id="d02"></a>

## D02 · P1 · Retain remote real-path and write-target checks

- **Repository:** `remote-dev`.
- **Location:** `resolve_path`, `atomic_write`; [remote_dev/core/remote_file_worker.py:35–58][remote-file-resolve] and [77–91][remote-file-write].
- **Category:** Defensive code with clear evidence for retention.
- **Trigger:** A locally valid path resolves through a remote symlink outside the root, or the write target itself is a symlink.
- **Evidence and result:** Local [path_policy.py:13–39][remote-path-policy] performs POSIX string normalization and cannot inspect the remote filesystem. The worker resolves real paths before checking them. The [transport contract:64][remote-root-contract] explicitly states the boundary.
- **Impact:** Removing the remote check expands access beyond the working-directory constraint. RD01 demonstrates why local input validation cannot establish remote path confinement.
- **Recommendation:** Retain real-path checks and the write-target policy. Any strengthening against time-of-check/time-of-use races should be reviewed separately.
- **Verification:** Run the original worker against a real temporary tree: reject an escaping symlink and accept an ordinary in-root path. Add isolated Linux coverage for concurrent directory replacement.
- **Certainty:** Confirmed from the contract and implementation.

**Defensive review — clear evidence to retain.**

1. **Protected risk:** Remote symlinks and real-path resolution escaping the root.
2. **Does it exist within support?** Yes. Other processes can modify directories on supported SSH/Linux targets.
3. **Upstream invariant:** Entry validation establishes lexical confinement only; it cannot establish the remote resolution result. See `path_policy.py:13–39`.
4. **Behavioral effect:** Deletion expands the file-access boundary and is not an equivalent refactor.
5. **Validation:** Real filesystem and symlink contract tests, rather than mocked return values or type annotations.

<a id="d03"></a>

## D03 · P1 · Retain fencing and conservative process-occupancy checks

- **Repository:** `coordinator`.
- **Location:** `HostCoordinator._check_token`, `process_guard_busy`; [mindie_coordinator/host/mindie_npu_coordination.py:835–837][coord-token] and [146–177][coord-process-guard].
- **Category:** Defensive code with clear evidence for retention.
- **Trigger:** An old client replays `activate` or `release` with a stale fencing token. Alternatively, a process is initializing on the CPU, `npu-smi` shows no device occupancy, or `/proc` is temporarily unreadable.
- **Evidence and result:** [AGENTS.md:5][coord-agents] makes HostQueue the sole allocation authority. `_check_token` validates against the current SQLite token. Lines 149–152 explain why empty hardware occupancy is not process completion. [managed_execution._finish_managed:435–445][coord-finish-managed] releases only after quietness is confirmed. [test_npu_coordination.py:341–374][coord-atomic-test] exercises atomic allocation with real concurrent SQLite access.
- **Impact:** Removal can let an old client release a new lease or reallocate devices while a previous task remains alive. `None` and permission-related protection covers real cases.
- **Recommendation:** Retain fencing tokens, boot identity, occupancy when process state is unreadable, and the requirement that descendants be drained. Consolidate their rationale into explicit boundary contracts.
- **Verification:** Use real SQLite for stale-token rejection and atomic exclusion between sessions. In isolated Linux tests, exercise process families, boot-identity changes, unreadable process state, and release only after confirmed quietness.
- **Certainty:** Confirmed from the authority and lifecycle contracts.

**Defensive review — clear evidence to retain.**

1. **Protected risk:** Replayed old authority and premature release during CPU initialization or loss of supervision.
2. **Does it exist within support?** Yes. Concurrent SSH clients and supervisor failure are supported operating conditions.
3. **Upstream invariant:** Local state is not the host SQLite authority. An idle device does not imply a quiet process; lines 146–177 describe the counterexample.
4. **Behavioral effect:** Removal changes allocation exclusion and cleanup safety.
5. **Validation:** Negative fencing cases and isolated Linux descendant-lifecycle tests. Passing the normal path does not justify deletion.

<a id="k-01"></a>

## K-01 · P1 · A legacy fallback bypasses the no-raw-transcript-in-storage contract

- **Repository:** `knowledge`.
- **Location:** `accept_stop`; [mindie_knowledge/loop/handoff.py:460–477][knowledge-summary-fallback], [loop/cli.py:66][knowledge-config-mode], and [loop/store.py:332–395][knowledge-capture-store].
- **Category:** Confirmed defect in a legacy compatibility branch.
- **Trigger:** A valid engine configuration omits `capture_mode`. An authorized, admitted turn's Stop payload contains `last_assistant_message`; the branch also accepts it without `transcript_path`.
- **Evidence and result:** `validate_config` interprets the omitted field as `public-transcript` but does not normalize the configuration. `accept_stop` reads it without a default and enters the legacy summary path. Unredacted text is stored in `captures.summary`, and a capture without a transcript can be queued. The relevant `cli.py` and `handoff.py` are byte-identical at audited main `021ba95e` and the actual adapter pin [4e328305][knowledge-pinned-handoff]; both were reproduced. See also [test_capture_handoff.py:151–178][knowledge-handoff-test] and the [incremental capture/redaction contract][knowledge-agents]. Local evidence: `evidence/knowledge/probes.json`, `evidence/knowledge/probes-pinned.json`, and `tools/knowledge_probes.py` — retained locally, not published.
- **Impact:** Raw text reaches local storage through a configuration-default mismatch. No direct upload of raw text through this path was found. All four adapters normally generate an explicit `public-transcript` setting, so this is not inevitable in an ordinary installation.
- **Recommendation:** Normalize the only supported mode, `public-transcript`, at the configuration boundary. Remove the old summary fallback and its branch-specific `SUMMARY_LIMIT`. Require a transcript for every non-notification turn and keep `summary` empty. Review existing legacy contents separately; do not clear historical data without authorization.
- **Verification:** Use real Consent, Admission, and SQLite with explicit/omitted mode × present/missing transcript × short/long raw text. Both valid mode representations must behave identically: an accepted sourced capture has `summary=''`; a sourceless capture is rejected. Preserve the notification prohibition on summary text. Verify that the engine does not execute unprocessable captures, including at the actual adapter pin.
- **Certainty:** High. Both main and the actual pin were reproduced using a fixed synthetic canary. Only readiness observation was substituted with `ready` to avoid starting a background service; validation and persistence were real.

**Defensive review — delete or merge the legacy fallback.**

1. **Protected risk:** Compatibility with historical summary-only Stop inputs and an oversized-body fallback.
2. **Does it exist within support?** That input mode is no longer supported: `cli.validate_config:66–67` and `Engine.__init__` accept only `public-transcript`. Omission remains legal, so the legacy branch cannot be called unreachable.
3. **Upstream invariant:** Validation guarantees membership in the sole supported mode, but does not write back the default. Two boundaries interpret the same valid configuration differently.
4. **Behavioral effect:** Explicit `public-transcript` behavior stays unchanged. Omission becomes equivalent to it, raw text is no longer stored, and sourceless inputs change from accepted to rejected. This is a privacy/input-semantics fix, not an equivalent refactor.
5. **Validation:** The full real-persistence matrix above, including the adapter-pinned revision.

<a id="rd01"></a>

## RD01 · P1 · Glob results can escape the configured root

- **Repository:** `remote-dev`.
- **Location:** `REMOTE_SEARCH_PY` glob branch, `remote_glob`; [remote_dev/core/search_ops.py:317–352][remote-glob-worker] and [573–584][remote-glob-entry].
- **Category:** Confirmed violation of the directory-scope contract.
- **Trigger:** `endpoint.root` constrains the working directory, but the pattern uses `../outside/*`, an absolute path, or a directory symlink inside the root that points outside it.
- **Evidence and result:** The unchanged production worker ran against a temporary directory tree. All three cases returned `status=ok` with outside filenames, sizes, and modification times. The entry point validates only `path`; the worker validates the base and then applies `iglob` and `lstat` directly to matches. The [transport contract:64][remote-root-contract] promises the `--root` constraint, and [path_policy.py:4][remote-path-policy] states that every remote path must stay inside the root. Local evidence: `tools/reproduce_remote_findings.py` and `evidence/remote-trio/reproductions.json` — retained locally, not published.
- **Impact:** Enumeration of out-of-root file metadata is confirmed. This evidence does not establish arbitrary content reads or a shell authorization bypass.
- **Recommendation:** Define whether glob patterns are relative to the base directory. Reject escaping patterns, resolve real matched paths under the same root invariant, and prevent recursive symlink traversal from escaping.
- **Verification:** Run the original worker in a real two-directory tree. Reject relative traversal, absolute escape, and symlink escape. Regress legitimate in-root absolute/relative patterns, sorting, and filtering according to the finalized contract.
- **Certainty:** Confirmed by execution and the stated root contract.

<a id="t01"></a>

## T01 · P1 · Coverage totals omit independently measurable dynamic worker logic

- **Repositories:** `remote-dev`, `coordinator`, `npu-top`.
- **Location:** Coverage measurement and embedded-worker dispatch; [remote_dev/core/search_ops.py:26–531][remote-search-string], [mindie_coordinator/provision/host_ops.py:1414–2424][coord-host-template], and [npu-top/package.json:9–13][npu-package].
- **Category:** Confirmed test-baseline measurement gap.
- **Trigger:** Reporting parent-pytest or Python source coverage as if it covered all production logic.
- **Evidence and result:** Audit configuration enabled branches, whole-package source discovery, no `omit`, and no exclusions. Even with `patch=subprocess`, `remote_file_worker`, `rpc_worker`, and `artifact_worker` had zero mapped collection although existing tests execute their text through `python -c` or `-I`. The 505 lines of Python inside `search_ops` count as an outer string assignment, not independent branches. The 1,003-line script rendered by `host_ops` has the same issue. The frontend provides lint/build commands but no test command.
- **Impact:** Never-imported files are included in the denominator, but embedded source lacks its own denominator. Zero capture does not mean no tests exist. Python percentages do not measure the frontend, remote Linux, hardware, or end-to-end behavior.
- **Recommendation:** Report parent-process, captured local subprocess, and remote-worker results separately, together with the TypeScript scope. Move workers to independent modules and compile them with real filenames; arrange coverage-data recovery for controlled Linux or remote execution. Establish frontend behavioral tests separately.
- **Verification:** Check that each source inventory includes unimported files. Use a sentinel to confirm ordinary child-process capture. List dynamic source and isolated-interpreter omissions. Merge remote data only for the same source SHA and configuration, never across mismatched versions.
- **Certainty:** Confirmed from the configuration, execution paths, and collected data.

<a id="adp-05"></a>

## ADP-05 · P2 · The DSH adapter deletes connection state and retries arbitrary startup failures

- **Repository:** `mindie-agent-dsh`.
- **Location:** `connection`; [scripts/mindie_sidecar.py:281–290][dsh-connection].
- **Category:** Error-semantics defect and redundant recovery logic.
- **Trigger:** Core `ensure_service` reports `unknown`, `worker-dead`, or another exception. The adapter indiscriminately deletes `connection.json` and retries startup.
- **Evidence and result:** Fault injection confirms that the original endpoint is deleted after the first exception and `ensure_service` is called again. The pinned [knowledge cli.ensure_service:130–191][knowledge-pinned-service] explicitly refuses to start a second service for an unknown state and owns startup through `StartLock`. Local evidence: `evidence/adapters/repro-dsh-connection.json` and `scripts/repro_dsh_connection.py` — retained locally, not published.
- **Impact:** The adapter removes diagnostic/connection evidence and conceals the first error. This does not prove that a second service actually starts; the core lock and probes still govern that outcome.
- **Recommendation:** Remove adapter-side unlinking and blind retry. Give the shared lifecycle implementation ownership of recovery and error classification. Return the original error through the sidecar error response.
- **Verification:** Inject `unknown`, `worker-dead`, and `PermissionError`. Assert one attempt, an unchanged endpoint, and an attributable error. Test stale-endpoint recovery at the shared runtime boundary.
- **Certainty:** Confirmed by fault injection and the pinned core contract.

**Defensive review — delete or merge the adapter recovery.**

1. **Protected risk:** A stale or damaged connection file prevents connection.
2. **Does it exist within support?** Endpoint staleness is real, but an arbitrary exception does not prove that deleting the endpoint is valid.
3. **Upstream invariant:** Pinned `cli.ensure_service:141–146,152–165` already distinguishes ready, unknown, and absent states while holding the startup lock.
4. **Behavioral effect:** The adapter stops deleting state or attempting a second startup; callers receive the first failure. This changes error semantics and is not equivalent cleanup.
5. **Validation:** One call, preserved endpoint, explicit failure, and the shared core's stale-endpoint recovery contract.

<a id="adp-06"></a>

## ADP-06 · P2 · Receipt write failures are silently swallowed at two levels

- **Repositories:** `mindie-agent-cc`, `mindie-agent-kimi`.
- **Location:** `finish_bind`, `finish_nonce`, `handle`. CC: [scripts/identity.py:335–340][cc-finish] and [scripts/mcp_server.py:365–369][cc-mcp]. Kimi: [scripts/identity.py:540–545][kimi-finish] and [scripts/mcp_server.py:363–367][kimi-mcp].
- **Category:** Confirmed error-semantics defect.
- **Trigger:** The business call succeeds, then SQLite or `_open` fails during receipt finalization.
- **Evidence and result:** The inner `except sqlite3.Error: pass` and outer `except Exception: pass` both suppress accounting errors. CC's [module contract:11–14][cc-mcp-contract] promises `bind_warning` plus `diagnostic_ref`, but the finalization path does not supply them. This is a statically confirmed path; it is not presented as a completed runtime fault-injection result.
- **Impact:** The receipt can remain `claimed` while the successful response carries no accounting warning. Successful external work must not be reported as failed, but users and diagnostics also need to know that the local record is incomplete.
- **Recommendation:** Propagate or return structured accounting failure from the inner layer. Preserve the business result and its `isError` value in the outer layer, attach a warning and diagnostic reference, and prohibit automatic replay.
- **Verification:** Inject real SQLite failures at `BEGIN`, `UPDATE`, and commit. Assert unchanged successful content, an explicit warning, traceable diagnostics, and rejected replay.
- **Certainty:** Static execution path confirmed.

**Defensive review — merge the two catches while preserving successful business semantics.**

1. **Protected risk:** Turning successful external work into an apparent failure can cause callers to retry it.
2. **Does it exist within support?** Yes; preserving success is necessary.
3. **Upstream invariant:** The business result already exists; finalization only accounts for it in local SQLite. The CC module contract explicitly requires a warning.
4. **Behavioral effect:** Success remains success, with newly visible accounting failure. Removing silent suppression is an error-semantics/observability fix, not purely equivalent cleanup.
5. **Validation:** Verify successful content, a write-failure warning, and no replay together.

<a id="b02"></a>

## B02 · P2 · CI's name filter excludes valid local regression tests

- **Repository:** `mindie-bench`.
- **Location:** Contract-test selection; [.github/workflows/ci.yml:26][bench-ci].
- **Category:** Confirmed test-selection gap.
- **Trigger:** CI uses `-k 'not actual'`, excluding tests whose names contain `actual`, including pure in-memory decisions and local protocol tests.
- **Evidence and result:** [test_evaluation_coverage.py:96–101][bench-repeat-test] only constructs evidence and checks the repetition-count gate, but is filtered out. An additional run selected 49 tests: 39 passed and 10 were skipped during execution, with one repeated collection-level skip reported separately. Local evidence: `evidence/mindie-bench-actual/tests.log` — retained locally, not published.
- **Impact:** Regressions that report insufficient repetitions as reliable, parse results incorrectly, or mishandle oracle control can escape ordinary CI. The name filter also fails to exclude `test_native_mcp_readiness`, which depends on a locally installed Codex host, so names do not reliably express test tiers.
- **Recommendation:** Make a separate test-organization change: use explicit local/host/hardware markers or directory conventions, remove name filtering, and include pure-logic `actual` tests in the local gate.
- **Verification:** Save per-tier node lists from `--collect-only`. Assert that pure-logic tests belong to the local selection. Compare newly exercised scenarios and runtime on unchanged source before and after selection changes.
- **Certainty:** High; existing excluded cases were actually run.

<a id="b03"></a>

## B03 · P2 · `run_trial` mixes business verdicts with many resource lifecycles

- **Repository:** `mindie-bench`.
- **Location:** `run_trial`; [src/mindie_bench/runner/orchestrator.py:298–995][bench-orchestrator].
- **Category:** Refactoring proposal.
- **Trigger:** A new phase must interact with shared `phase`, `status`, `primary`, and `auxiliary` state in a function that already freezes the oracle, validates configuration, manages profiles/processes/remote leases/model gateways, verifies results, captures experience, accounts for cost, cleans up, and builds the final receipt.
- **Evidence and result:** The function spans 698 lines. Exception classification at 781–797, accounting errors at 879–882, remote cleanup at 892–900, and reward removal at 962–963 can all change final status. Existing [test_capture_diagnostics.py][bench-capture-tests] and [test_remote_settlement.py][bench-settlement-tests] patch several stages to reach a particular outcome. Length is a locator, not the defect by itself.
- **Impact:** Coupled decisions and I/O make it easy for a new failure branch to lose an already completed business verdict. State decisions spread across `try`, `except`, and `finally` are costly to test independently.
- **Recommendation:** First add characterization tests for phase results and cleanup outcomes. Extract a pure result-combination function and small cohesive resource-lifecycle objects. Preserve exactly-once side effects and the original receipt. Do not create a parallel persistent state machine; review error-semantics changes separately.
- **Verification:** Use a table of PASS/FAIL/INFRA/UNKNOWN × scoring/capture/cleanup errors. Compare the original verifier verdict, terminal status, accounting completeness, and permission to retry. Keep real subprocess contracts in component tests.
- **Certainty:** High confidence in the responsibility coupling; this is a refactoring recommendation, not a defect inferred from length.

<a id="b04"></a>

## B04 · P2 · Workspace-management commands have no measured test execution

- **Repository:** `vllm-ascend-workspace`.
- **Location:** `run`, `path_at`, `main`; [.agents/scripts/workspace.py:13–135][workspace-main].
- **Category:** Confirmed test gap.
- **Trigger:** Use of `worktree-add`, `worktree-remove`, `task-init`, or `directory-remove`. All four existing tests invoke only `repo_init.py` through a subprocess.
- **Evidence and result:** Four tests passed. Measured production coverage was `repo_init.py` 97/105 lines and 33/42 branches; `workspace.py` 0/103 lines and 0/40 branches; combined 97/208 lines and 33/82 branches. Unimported production files were included. Local evidence: `evidence/vllm-ascend-workspace/tests.log` and its `coverage.json` — retained locally, not published.
- **Impact:** Changes to worktree arguments, task metadata, links, and deletion boundaries lack regression protection. Passing initialization tests does not establish the correctness of the main scaffold commands.
- **Recommendation:** Add meaningful tests using temporary real Git repositories and directories: the new worktree points to the correct commit; dirty-worktree removal fails; task links and metadata are correct; dry-run leaves state unchanged; explicit deletion affects only its designated object.
- **Verification:** Execute every CLI branch without network access or user worktrees. Assert commits, files, links, and exit semantics. Initial targets for `workspace.py`: at least 85% line and 80% branch coverage, with every important deletion/preservation scenario passing.
- **Certainty:** High; measured with unimported files included.

<a id="b06"></a>

## B06 · P2 · Optional component tests require an incompatible shared interpreter environment

- **Repository:** `mindie-bench`; dependency-contract evidence also comes from `coordinator` and `knowledge`.
- **Location:** Module collection, `value_coordinator.run`, `value_diagnostics.one`; [tests/test_component_value_scenarios.py:8–10,15–37][bench-component-tests], [src/mindie_bench/benchmarks/value_common.py:24–33][bench-value-common], [coordinator/pyproject.toml:14–15][coord-dependencies], and [knowledge/pyproject.toml:21][knowledge-dependencies].
- **Category:** Confirmed gap in the optional test-environment contract.
- **Trigger:** Installing the exact audited coordinator and knowledge revisions into one isolated interpreter for bench's optional component-value tests. Collection requires all three imports; the scenarios also read distribution metadata for remote-dev and npu-top.
- **Evidence and result:** The real resolver rejects conflicting Git URLs for `mindie-diagnostics`: coordinator `c77144a95dd6af37e978ffc2d8495158b237090d` pins `6460cde3a50a7f91c9ded38557a7f921654f0c6a`, while knowledge `021ba95e701d4f8c8d924e2dcc8f120a4939da23` pins `1b5a0eeb79d498c39002fc1853271c17e0f26e66`. The dry run exited 1 after 8.189 seconds. Both the host and additional `actual` runs skipped this module during collection because coordinator was absent; a separate original-lock harness still collected zero tests from it and recorded a module skip. Fourteen other optional CPU/stale/FastMCP tests were independently run and passed, but do not include these two scenarios. [value_diagnostics.py:82–86][bench-value-diagnostics] actually uses `knowledge.consent_store`, so that import cannot simply be dismissed as unused. Local resolver metadata/logs and collection evidence under `evidence/mindie-bench-optional`, plus the host/actual test logs — retained locally, not published.
- **Impact:** Default locked CI lacks the optional components, leaving the two local real-port lease and diagnostics deduplication/revocation scenarios uncollected. Installing every current component does not produce a declared-compatible single interpreter. `--no-deps` or forcibly replacing diagnostics would create an unsupported combination. This does not prove that separately deployed components fail, or that the two scenarios contain business defects.
- **Recommendation:** Define reproducible component revisions and interpreter boundaries for optional scenarios. Execute across separate processes/environments where the actual component architecture requires it, returning observable results. Collection gates and `source_revisions` should require only components used by that scenario. If one interpreter is necessary, validate a compatibility matrix before publishing its lock; do not unify diagnostics pins without validation.
- **Verification:** Create fresh environments from exact Git SHAs, require successful resolution and `pip check`, and collect/run both existing scenarios separately. Preserve their assertions over real SQLite/port conflicts, active-lease retention, exactly one HTTP POST, redaction, and zero requests after revocation. Record first-party `direct_url` provenance. Report optional results separately; do not automatically merge their coverage with default CI or another environment.
- **Certainty:** High; the exact-URL resolver conflict and collection skips were observed. No forced installation or claim of production deployment failure was made.

<a id="co01"></a>

## CO01 · P2 · A broken machine registry is reported as an empty inventory

- **Repository:** `coordinator`.
- **Location:** `CoordinatorService._configured_machines`, `_ensure_user_container`, `_progress`; [mindie_coordinator/service.py:947–954,961][coord-configured-machines] and [672–676][coord-wait-runtime].
- **Category:** Confirmed error-semantics defect.
- **Trigger:** The machine registry is malformed, unreadable, or fails with an I/O error when a task needs an execution environment.
- **Evidence and result:** A real `MachineDirectory` reading a temporary malformed JSON file raises `JSONDecodeError`, while `_configured_machines()` returns `[]`. `_ensure_user_container` iterates the empty list, `_place_or_prepare` returns `cache_miss`, and `_progress` enters `waiting_for_runtime`. Local evidence: `evidence/remote-trio/reproductions.json` — retained locally, not published.
- **Impact:** An actionable registry failure becomes “no machines/no matching runtime.” The task waits without its original error, misleading diagnosis and recovery.
- **Recommendation:** Return an empty inventory only for the explicit state of an unconfigured optional registry. For an existing configured registry, propagate a parse/read error with its source location and enter a recoverable failure state. This is an error-semantics fix, not an equivalent refactor.
- **Verification:** Use real temporary files for absent configuration, a valid empty list, malformed JSON, and permission/I/O failure. Assert outward state and error origin. After repair, execution must resume without duplicating an already submitted remote task.
- **Certainty:** Confirmed by execution.

**Defensive review — remove or narrow the broad catch.**

1. **Protected risk:** An unavailable optional machine directory blocks preparation.
2. **Does it exist within support?** An unconfigured optional directory is valid, but corruption in a configured directory does not mean zero machines.
3. **Upstream invariant:** [MachineDirectory.load:222–243][coord-machine-load] distinguishes valid documents from read/decode failures; it does not guarantee success.
4. **Behavioral effect:** Valid directories behave as before. Errors become attributable failures instead of `cache_miss`/waiting, and callers must handle them.
5. **Validation:** Real file failures and recovery after repair; never default errors to empty success.

<a id="d-01"></a>

## D-01 · P2 · The comparison CLI accepts missing workload identity against its contract

- **Repository:** `diagnostics`.
- **Location:** `compare_profiles`; [mindie_profiler/compare.py:502–516][diag-workload], [cli_compare.py:101,117][diag-compare-cli], and [README.md:185][diag-compare-contract].
- **Category:** Confirmed mismatch between the CLI workload-identity gate and its contract.
- **Trigger:** Two real C7 summaries have matching runtime, device, model, shape, and dtype, but one or both lack `scene.input_signature`.
- **Evidence and result:** Real `analyze_profile` output passed through the public comparison CLI returns `comparable=true`, `status=comparable_with_limitations`, and exit 0. The README requires `not_comparable` and exit 3 when the workload signature is absent. Existing [API tests:75–111][diag-compare-tests] deliberately accept this as a limitation; [CLI tests][diag-cli-tests] are also relevant. Local evidence: `evidence/diagnostics/probes.json` (`missing_workload_signature`) and `tools/diagnostics_probes.py` — retained locally, not published.
- **Impact:** Matching model and shape do not prove identical request content or workload. Automated performance acceptance can accept incomparable runs. This finding concerns the profiler in audited diagnostics main 0.5.0; it must not be presented as behavior used by adapters pinned to 0.4.3.
- **Recommendation:** Separate an exploratory Python API policy from strict CLI acceptance. Strict CLI comparison should treat absent, one-sided, or unnormalizable input identity as a hard reason. If preserving the permissive API, name its policy explicitly.
- **Verification:** Run real `analyze_profile` → JSON output → CLI with both missing, one missing, whitespace, unknown, identical, and different signatures. Missing/invalid identities must exit 3 without a successful performance verdict; matching valid identity may permit exit 0.
- **Certainty:** High; the production producer and public CLI were executed. Do not make every API call strict without accounting for the existing compatibility contract.

<a id="d-02"></a>

## D-02 · P2 · An invalid summary is recognized and then dereferenced anyway

- **Repository:** `diagnostics`.
- **Location:** `compare_profiles`; [mindie_profiler/compare.py:531–553][diag-step-accounting] and [cli_compare.py:114–117][diag-compare-cli].
- **Category:** Confirmed malformed-input error-handling defect.
- **Trigger:** Imported C7 JSON has the expected `schema_version` but `step_accounting=null` or another non-Mapping value.
- **Evidence and result:** `_rank_scope` records `rank_scope_unavailable`, but `compare_profiles` later evaluates chained `.get(...).get(...)` and raises `AttributeError`. The API promises an incompatibility result rather than an exception; the CLI catch does not handle this exception either. Local evidence: `evidence/diagnostics/probes.json` (`null_step_accounting`) and `tools/diagnostics_probes.py` — retained locally, not published.
- **Impact:** The user receives a traceback instead of structured `not_comparable`.
- **Recommendation:** Validate or normalize the `step_accounting` container once at the summary boundary and reuse it, or return immediately for a known hard container error. Do not add broad `except Exception` handling that converts internal arithmetic defects into empty results.
- **Verification:** Public CLI and API must provide defined failure semantics for damaged external summaries. Start with real producer output and replace only `step_accounting` with null or a list. Assert the reason and exit code, not just absence of an exception.
- **Certainty:** High; `AttributeError` was reproduced. The trigger is malformed or externally produced input; this does not claim that normal `analyze_profile` emits null.

<a id="d-03"></a>

## D-03 · P2 · Peak-memory comparison lacks a settled missing-metadata contract

- **Repository:** `diagnostics`.
- **Location:** `compare_peaks`; [mindie_profiler/memory_compare.py:56–65][diag-memory-compare].
- **Category:** Contract question: comparability is reported without a known measurement basis.
- **Trigger:** The baseline declares bytes, phase, scope, and `is_peak`, but omits `measurement_kind` and `peak_scope`; the candidate declares `sampled_device_peak` and `sampled`.
- **Evidence and result:** The reproduction returns `comparable=true` and `ratio=1.5`. Module invariants require matching measurement and peak semantics, which the missing-field path cannot establish. Existing [test_profiler_memory.py:318–335][diag-memory-tests] treats dictionaries with missing metadata on both sides as legal legacy input. Local evidence: `evidence/diagnostics/probes.json` (`peak_missing_measurement_kind`) — retained locally, not published.
- **Impact:** The result can imply established comparability without evidence of matching measurement semantics. Existing compatibility evidence prevents simply declaring the legacy branch removable.
- **Recommendation:** First establish whether the public API must support old dictionaries without `measurement_kind`. Strict mode should return `not_comparable` for missing semantics; compatibility mode may report `unverified`, but must not automatically support peak-improvement acceptance.
- **Verification:** Cover measured, bounded-sampled, and point observations × complete metadata, one-sided omission, and two-sided omission. Only matched semantics should yield a comparable peak verdict. Preserve rejection of `is_peak=False`.
- **Certainty:** High confidence in the reproduced behavior; medium confidence about intended support scope, which requires a product contract.

**Defensive review — insufficient evidence to remove compatibility.**

1. **Protected risk:** Older callers do not carry newly added peak metadata.
2. **Does it exist within support?** Tests at lines 318–335 explicitly use metadata-free dictionaries, providing compatibility evidence.
3. **Upstream invariant:** The current `attribute_memory` producer fills `measurement_kind`, `peak_scope`, and `is_peak`. However, `compare_peaks` is public and accepts dictionaries directly; not every caller must use that producer.
4. **Behavioral effect:** Tightening the contract can change old callers from `comparable=true` to `not_comparable`. This changes verdict semantics.
5. **Validation:** A missing/conflicting metadata matrix alongside real producer output.

<a id="k-02"></a>

## K-02 · P2 · Stop handoff mixes protocol, authorization, persistence, and wakeup decisions

- **Repository:** `knowledge`.
- **Location:** `accept_stop`; [mindie_knowledge/loop/handoff.py:385–638][knowledge-accept-stop].
- **Category:** Refactoring proposal.
- **Trigger:** Any Stop admission and service wakeup, particularly interactions between configuration defaults, consent restoration, SQLite busy conditions, and an unavailable process.
- **Evidence and result:** The 254-line function contains 61 `if`/loop/`except`/conditional-expression nodes. This is a locator metric, not standard cyclomatic complexity. It interprets mode, identity, consent, Admission, database errors, and wake results. K-01 demonstrates divergent defaults between the entry point and this function. Numerous returns manually build `stage`, `reason`, and `summary_dropped`. Existing [capture-handoff][knowledge-capture-tests], [short-handoff][knowledge-short-tests], and [capture-wake tests][knowledge-wake-tests] cover these responsibilities. Local static evidence: `evidence/knowledge-diagnostics-static-candidates.json` — retained locally, not published.
- **Impact:** A business-rule change can omit one of the many return paths.
- **Recommendation:** Fix K-01 first. Extract pure Stop-envelope-to-normalized-admission and receipt-stage decisions. Keep consent reads, the real SQLite commit, and wakeup in their current order within a thin orchestrator. Preserve one commit point and explicit persisted state; add neither a new state machine nor forwarding layers.
- **Verification:** Test pure decisions through a parameter matrix without mocks. Use real SQLite and controlled processes for duplicate Stop, revocation/busy interactions, a persisted capture with failed wakeup, and ready/unknown service states. Compare all external `stage`, `reason`, and `capture_id` fields.
- **Certainty:** High confidence in responsibility mixing and the confirmed default divergence; function length alone is not the finding.

<a id="k-03"></a>

## K-03 · P2 · Local “summary fidelity” tests do not measure model faithfulness

- **Repository:** `knowledge`.
- **Location:** `test_multiturn_incremental_transcript_capture_redaction_and_summary_fidelity`; [tests/test_domain_retrieval_and_summary_quality.py:281–284,342–399][knowledge-summary-test] and [tests/material_worker_fixture.py:22–27][knowledge-worker-fixture].
- **Category:** Boundary on what existing tests establish.
- **Trigger:** A prompt or actual host model drops failed attempts, promotes a hypothesis into a verified conclusion, or ignores a later correction.
- **Evidence and result:** The fixture returns the same fixed title/summary for every block without analyzing its text. Its [module comment:1–5][knowledge-worker-fixture] explicitly says it cannot establish model quality. Assertions protect raw-text redaction, technical terms, package completeness, and citation traversal. The [quality-gate contract][knowledge-agents] calls for retrieval and summary quality.
- **Impact:** These valuable component tests cannot detect actual summarization distortion and should remain. Their success cannot establish LangMem/LLM summary quality. Top-1 retrieval on six handcrafted documents measures that closed set only, not real-corpus precision/recall.
- **Recommendation:** Label the local suite as summary-protocol and persistence-consistency validation. Add a separate fixed, anonymized multi-turn quality evaluation with explicit human criteria for facts, failures, corrections, and attribution. Record the real host, model, version, and reviewable output.
- **Verification:** Quality cases must catch an early failure being erased by final success, or an unrun check being described as verified. Retrieval cases should include the same error code across different versions, hard negatives, and no-relevant-answer queries, with per-query labels, Top-k hits, and false retrievals.
- **Certainty:** High; fixture behavior and assertions are directly traceable. This audit did not invoke a paid model; real-model quality is **not measured**.

<a id="k-04"></a>

## K-04 · P2 · The live probe turns remote execution failures into skips

- **Repository:** `knowledge`.
- **Location:** `_ssh_probe`; [tests/test_live_npu_knowledge_loop.py:32–60][knowledge-live-probe], especially 54–60.
- **Category:** Confirmed weakness in the live-test gate.
- **Trigger:** SSH connects, but the configured container is absent, `npu-smi` regresses, Docker permissions fail, or the remote script exits nonzero.
- **Evidence and result:** All nonzero results become skips. This loses the distinction between missing environment/network availability and a failing enabled hardware contract. Relevant gates are [.github/workflows/pr-review.yml][knowledge-pr-review] and the architecture repository's [testing-architecture.md][architecture-testing].
- **Impact:** A release gate can appear green without executing the expected hardware contract. A skip is not measured coverage or evidence of hardware success.
- **Recommendation:** Use explicit preflight to classify environment unavailability. Once the environment is explicitly enabled and SSH is ready, failed business probes or container commands should fail the test. Make target/container selection test-environment configuration while retaining actual identity in private execution evidence.
- **Verification:** With controlled SSH results, an unconfigured environment skips; a connected remote command exiting 1 fails. Continue capture/redaction/recall validation only after real output from the declared hardware targets succeeds.
- **Certainty:** High for the static branch. Connectivity was probed centrally during the remote audit; this review did not duplicate live connections.

<a id="np01"></a>

## NP01 · P2 · A faster viewer heartbeat does not advance the next sample

- **Repository:** `npu-top`.
- **Location:** `AdaptiveScheduler.heartbeat`, `_run_loop`; [npu_top/scheduler.py:67–77][npu-heartbeat] and [168–190][npu-run-loop].
- **Category:** Confirmed scheduling defect.
- **Trigger:** An idle cycle has set `next_cycle` 120 seconds ahead. A user then opens the panel and sends a heartbeat requesting a one-second interval.
- **Evidence and result:** A real `_run_loop` reproduction, substituting only local non-I/O probe/database objects, reports an effective interval of 1 second but still has only one cycle after 1.25 seconds. The loop reads the new interval without adjusting `next_cycle`; notification wakes it only to wait for the old deadline. Existing [test_scheduler.py:15–30][npu-scheduler-tests] checks the getter only.
- **Impact:** The panel advertises one-second refresh while the first new automatic sample may still wait about 120 seconds. Fast-viewer responsiveness does not match the contract.
- **Recommendation:** Derive the next deadline from the last completion time and current effective interval, or advance it when a viewer lease requests a faster rate. Avoid unconditional immediate polling.
- **Verification:** With an injectable clock/condition, exercise the real loop for idle → 1 second, 10 → 1 second, and viewer hiding/expiry back to idle. Assert probe count and timing, rather than only a getter value.
- **Certainty:** Confirmed by execution.

<a id="np02"></a>

## NP02 · P2 · A live request can return a snapshot collected without its required infrastructure probe

- **Repository:** `npu-top`.
- **Location:** `AdaptiveScheduler.collect_and_wait`, `_collect_cycle`; [npu_top/scheduler.py:100–116][npu-collect-wait] and [218–250][npu-collect-cycle].
- **Category:** Confirmed live-result freshness defect.
- **Trigger:** An ordinary probe without infrastructure collection is already in flight when `/api/agent/server` receives `mode=live` with `force_infrastructure=True`.
- **Evidence and result:** The reproduction returns a snapshot with `include_infrastructure=false` while the force request remains queued. `collect_and_wait` only checks `current is not previous`. [api.py:142][npu-api-live] requires forced infrastructure collection for live mode; [probe.py:682–692][npu-probe-cache] reuses old infrastructure cache on ordinary cycles. Existing [test_scheduler.py:33–57][npu-scheduler-tests] writes a snapshot directly and bypasses a real collection cycle. Local evidence: `evidence/remote-trio/reproductions.json` — retained locally, not published.
- **Impact:** A live request can return old mount/Docker information under a new `collected_at`. The response does not establish that the requested forced probe completed.
- **Recommendation:** Use per-server requested/completed generations or explicit infrastructure-collection timestamps. Wait for a result satisfying this request's generation and collection requirements. Do not add an unnecessary persistent state machine.
- **Verification:** Gate real `_collect_cycle` execution with events: start an ordinary probe, issue the force request, and release the old probe. The request must keep waiting until the new infrastructure probe completes. Add timeout, shutdown, and two-concurrent-live-request cases.
- **Certainty:** Confirmed by execution.

<a id="rf01"></a>

## RF01 · P2 · The embedded search worker mixes filtering rules with process management

- **Repository:** `remote-dev`.
- **Location:** `REMOTE_SEARCH_PY`, glob, grep; [remote_dev/core/search_ops.py:26–531][remote-search-string].
- **Category:** Refactoring proposal.
- **Trigger:** Changes to globbing, gitignore behavior, grep capability fallback, pagination, or process-stream cleanup all require editing the same 505-line Python string.
- **Evidence and result:** Static metrics locate this large worker; RD01 is in that string. [test_grep_fallback.py:51–71][remote-grep-tests] executes the text through `python -c`, so coverage does not map the embedded branches. The existing standalone [remote_file_worker.py][remote-file-module] provides a repository-local extraction model. Static metrics are retained locally, not published.
- **Impact:** Relative-path handling and gitignore rules are coupled to process management. Filtering rules are difficult to import independently, and diagnostics/coverage lack real source line locations.
- **Recommendation:** Move the unchanged source into an independent worker module while preserving payload dispatch. Separate pure path/filter/pagination functions from I/O. Unify the base/result path invariant and retain supported `grep -E` fallback.
- **Verification:** First compare output contracts using existing real local grep/Git/glob cases, plus RD01 regressions. Upload the same worker file unchanged and verify unchanged CLI/MCP responses and exception classification.
- **Certainty:** Refactoring proposal with concrete evidence of benefit.

<a id="rf02"></a>

## RF02 · P2 · Coordinator progress decisions are interleaved with many side effects

- **Repository:** `coordinator`.
- **Location:** `CoordinatorService._progress`; [mindie_coordinator/service.py:629–852][coord-progress].
- **Category:** Refactoring proposal.
- **Trigger:** Recovery and cancellation must track execution phase, roles, binding, assignment, and remote session/lease/job state together.
- **Evidence and result:** `_progress` spans 224 lines with 33 AST decision candidates, not a formal McCabe score. Lines 629–651 validate/persist session and source state; 655–723 place, prepare, and bind; source materialization begins at 725, followed by submission and terminal-result combination. [The catalog read at 918–923][coord-place] and another at 679–690 occur at different I/O times; they are not proven redundant.
- **Impact:** Recovery points, side effects, and outward state are dispersed. A change can bypass cancellation or repeat preparation. Tests need a broad service/pool setup to reach individual decisions.
- **Recommendation:** First extract a pure observation → next action/outward phase decision. Preserve current persistence boundaries and call order. Use a small number of cohesive functions for role preparation/binding and execution observation without adding another state machine.
- **Verification:** Reuse `InMemoryHostQueue` and real SQLite scenarios: cancellation between prepare/activate/go, restart recovery, one role failing while another drains, and successful execution followed by local-record failure. Compare states and ensure remote calls are not replayed.
- **Certainty:** Refactoring recommendation; the repeated catalog checks have not been established as safe to delete.

<a id="adp-07"></a>

## ADP-07 · P3 · `publish_bind` repeats an unchanged pure validation

- **Repository:** `mindie-agent-cc`.
- **Location:** `publish_bind`; [scripts/identity.py:217–220][cc-bind-entry] and [253–255][cc-bind-repeat].
- **Category:** Confirmed equivalent-cleanup candidate.
- **Trigger:** A valid `tool_name` reaches the existing-ID branch of `publish_bind`.
- **Evidence and result:** The same `parse_native_tool(tool_name)` validation is performed twice. `tool_name` is not changed between them, and the parser is pure and reads module constants only.
- **Impact:** The second branch protects no additional risk and adds maintenance and coverage burden.
- **Recommendation:** Remove the second validation at 253–255. Preserve entry validation, binding-conflict checks, digest checks, and state checks.
- **Verification:** Keep existing valid rebinding and ambiguous-binding tests passing. Confirm parser purity and the unchanged argument, then review the small static diff. Do not add type-only filler tests for deleting two lines.
- **Certainty:** Confirmed as equivalent cleanup.

**Defensive review — remove the duplicate.**

1. **Protected risk:** Reject MCP tool names outside this plugin.
2. **Does it exist within support?** Yes, but this same invocation already validated the input.
3. **Upstream invariant:** Lines 217–218 perform the check; `tool_name` is unchanged before line 253, and parsing does not depend on I/O.
4. **Behavioral effect:** Normal and failing behavior are unchanged; one duplicate parse disappears.
5. **Validation:** Existing first-publication, duplicate, and conflicting `publish_bind` cases.

<a id="b05"></a>

## B05 · P3 · MaterialStore capability fallbacks need a declared support matrix

- **Repository:** `mindie-bench`; supporting API evidence comes from `knowledge`.
- **Location:** `consumer`; [src/mindie_bench/integrations/first_party.py:58–74][bench-consumer].
- **Category:** Compatibility branch requiring further validation.
- **Trigger:** `hasattr` checks `_pointers` and `refresh_index` on an internal `MaterialStore`; absence causes reinstallation or skips refresh.
- **Evidence and result:** Knowledge main `021ba95e` and adapter pin `4e328305` both implement `_pointers` at [materials/store.py:275][knowledge-material-pointers] and `refresh_index` at [795][knowledge-material-refresh]; the [pinned source][knowledge-pinned-material] also has both. Bench runs through a configurable external component interpreter and does not declare a minimum knowledge version in its package metadata. The `BrokenInstall` stub in [test_first_party_mcp.py:120–145][bench-broken-install-test] lacks `_pointers` and actually takes the fallback.
- **Impact:** An unsupported component or unrealistic stub can be silently accepted and omit index refresh. Current evidence does not establish that every officially allowed external version has these methods.
- **Recommendation:** First document permitted component versions/capabilities and verify installation identity. If support is limited to the checked revisions, call directly, remove the `hasattr` fallback, and make test doubles satisfy the same contract.
- **Verification:** Run real pinned and main `MaterialStore` through install → retrieve → live index refresh. Reject unsupported older components explicitly at entry. Failure cleanup must not overwrite the original error.
- **Certainty:** Medium; both inspected versions satisfy the capability requirement, but the full support matrix is unspecified.

**Defensive review — insufficient evidence to delete.**

1. **Protected risk:** A selected older component lacks the two methods.
2. **Does it exist within support?** Any component interpreter can be configured, and no complete support scope was found. Current main alone cannot establish that the risk is absent.
3. **Upstream invariant:** Both checked SHAs implement the methods, but bench entry does not yet require the minimum capabilities.
4. **Behavioral effect:** Direct deletion exposes `AttributeError` for old objects. Replace that with an explicit entry incompatibility error and correct resource cleanup.
5. **Validation:** Real component contract tests for the support matrix and explicit failure for unsupported revisions.

<a id="d-04"></a>

## D-04 · P3 · The same label is scanned repeatedly

- **Repository:** `diagnostics`.
- **Location:** `_label`, `_project`; [mindie_diagnostics/bundle.py:68–73][diag-label], [159–160][diag-label-repeat], and [187–190][diag-label-exit].
- **Category:** Equivalent-refactoring proposal.
- **Trigger:** Exporting an event with a valid static label.
- **Evidence and result:** For the clean label `completed`, 24 rules execute 48 span scans. The attribute branch calls `_label` twice, repeating another full validation. [redact.py][diag-redact] contains the two pure scanners; existing [bundle][diag-bundle-tests] and [redaction tests][diag-redact-tests] provide relevant fixtures. Local evidence: `evidence/diagnostics/probes.json` (`clean_label_scan`) — retained locally, not published.
- **Impact:** Valid labels receive repeated deterministic regex scans, adding hot-path work and maintenance across two implementations. No unmeasured end-to-end latency gain is claimed.
- **Recommendation:** First cache `_label(value)` locally to remove the duplicate at 159–160. Then, only after differential validation, consider a single `scan_text` decision for rejection. Retain the final canonical-event outbound scan and allowlist.
- **Verification:** Compare old/new outputs across all privacy fixtures: clean text, credentials, allowlists, overlaps, IPv6, versions, and related edge cases. Measure real batch runtime. Invocation counts alone are not a sufficient business assertion.
- **Certainty:** Duplicate computation is confirmed. Replacing two distinct scanners with one requires differential proof of boundary equivalence.

**Defensive review — merge repeated computation while retaining validation.**

1. **Protected risk:** Sensitive or free-form text enters a public label.
2. **Does it exist within support?** Yes; this is a real external-event boundary.
3. **Upstream invariant:** Within one `_project` call, `value` is the same immutable string. `redact_text` and `scan_text` are pure and perform no I/O; no state changes between lines 159–160.
4. **Behavioral effect:** Caching the same `_label` result preserves success and failure behavior. Only computation is merged; neither allowlists nor publication gates are relaxed.
5. **Validation:** Privacy-fixture differentials and assertions that the complete public payload contains no sensitive material.

<a id="d01"></a>

## D01 · P3 · The completion watcher has a redundant terminal-state predicate

- **Repository:** `coordinator`.
- **Location:** `ManagedExecution.watch_completion.watch`; [mindie_coordinator/managed_execution.py:356][coord-watch-state].
- **Category:** Equivalent redundant-code cleanup.
- **Trigger:** The completion-observer thread checks whether the current job is still running.
- **Evidence and result:** [The runtime `JOB_TERMINAL` set at line 43][coord-terminal-set] does not contain `running`. In `state in JOB_TERMINAL or state != 'running'`, the first condition therefore implies the second. This is based on the actual runtime definition, not only a type annotation.
- **Impact:** No known incorrect behavior; the duplicate state predicate adds reading cost.
- **Recommendation:** Keep only `job["state"] != "running"`. Do not remove the subsequent observed-unknown or quietness checks.
- **Verification:** Run existing [completion-dispatch][coord-dispatch-tests] and [owned-completion tests][coord-owned-tests]. Reuse cases proving that running jobs keep waiting and non-running jobs exit, without adding enumeration-only filler tests.
- **Certainty:** Confirmed.

**Defensive review — remove the redundant half of the condition.**

1. **Protected risk:** A terminal job starts another long completion poll.
2. **Does it exist within support?** Yes, but `!= "running"` already covers every terminal state.
3. **Upstream invariant:** The actual set at line 43 and condition at line 356 establish the logical implication.
4. **Behavioral effect:** Return/wait behavior stays unchanged for all current state values.
5. **Validation:** Completion-observer regressions; external error semantics are unchanged.

<a id="d04"></a>

## D04 · P3 · Legacy environment aliases and remote Python compatibility need support evidence

- **Repositories:** `npu-top`, `remote-dev`.
- **Location:** `_env`, glob fallback; [npu_top/settings.py:15–21][npu-env], [80–99][npu-legacy-settings], and [remote_dev/core/search_ops.py:316][remote-python-fallback].
- **Category:** Compatibility logic requiring further validation.
- **Trigger:** Considering removal of legacy `NFM_*` aliases, or removal of remote Python 3.9 glob compatibility because the local package declares `requires-python >=3.11`.
- **Evidence and result:** Settings explicitly prefer `MINDIE_TOP` over `NFM`; [test_settings_mindie.py][npu-settings-tests] covers both. The [remote README][remote-readme] requires `python3`/`bash` in the target container without stating a remote minimum version. Local package installation requirements do not automatically constrain a remote interpreter.
- **Impact:** No deployment inventory or retirement evidence establishes safe deletion. Removing these paths may invalidate old configuration or break some remote targets.
- **Recommendation:** Establish the support matrix, migration policy, and retirement deadline before deciding. Do not delete remote compatibility based only on the local interpreter version.
- **Verification:** Declare supported client configurations and target environments, then run real old-variable precedence and minimum-supported-remote-Python cases.
- **Certainty:** Insufficient evidence to remove.

**Defensive review — insufficient evidence.**

1. **Protected risk:** Existing users retain old configuration or older remote Python.
2. **Does it exist within support?** Code and documentation still show support, but active-deployment statistics were unavailable.
3. **Upstream invariant:** Local `requires-python` establishes no remote-version invariant; no retirement contract was found.
4. **Behavioral effect:** Deletion could silently select default state directories/ports or make remote glob fail.
5. **Validation:** Establish support and migration contracts first, then test configuration and remote-version behavior.

<a id="k-05"></a>

## K-05 · P3 · The query path validates and decodes the same continuation twice

- **Repository:** `knowledge`.
- **Location:** `Store.query`; [mindie_knowledge/loop/store.py:1144–1170][knowledge-query], [materials/store.py:760–762][knowledge-search-validation], and [materials/provenance.py:36–50][knowledge-query-request].
- **Category:** Equivalent-refactoring candidate.
- **Trigger:** Any valid `Store.query`, particularly one carrying a continuation of up to 24 KiB.
- **Evidence and result:** Entry `query_request` decoding/validation at line 1147 discards its result; `MaterialStore.search` repeats it. The outer validation ensures malformed input fails before touching materials. Existing [test_material_query.py][knowledge-query-tests] provides the query contract.
- **Impact:** Repeated computation is confirmed, but simply removing the outer validation delays input errors until after possible I/O.
- **Recommendation:** Preserve validation at both independently public entry points. Reuse a locally normalized request or a private validated-search path for the internal call. Proceed only if measurement demonstrates benefit; do not create a new public abstraction merely to save a few type checks.
- **Verification:** Invalid, expired, or cross-query continuations must fail before index reads or repairs. Preserve real pagination results and error types.
- **Certainty:** High for duplicated computation, medium for refactoring value. Prioritize correctness and test gaps first.

**Defensive review — merge internal repeated work; retain public-boundary validation.**

1. **Protected risk:** A malformed query touches/repairs materials, or uses an invalid continuation.
2. **Does it exist within support?** Yes; both public APIs accept external input.
3. **Upstream invariant:** `Store.query` finishes the same `query_request` at line 1147 and does not change its arguments before 1170. `MaterialStore.search` can also be called independently.
4. **Behavioral effect:** Reusing a normalized internal request should preserve behavior. Directly removing the outer check changes error ordering and is not safe equivalent deletion.
5. **Validation:** Zero I/O for invalid input, plus valid and expired pagination contracts.

## Additional defensive-code review

The following five entries supplement the 33-item register. They record defenses with clear retention evidence and one unresolved public-API compatibility question; they are not five additional confirmed defects.

<a id="kd-r1"></a>

## KD-R1 · Retain consent checks immediately before remote actions

- **Repository:** `diagnostics`.
- **Location:** [mindie_diagnostics/reporter.py:521–550][diag-consent-action] and [mindie_diagnostics/reporting.py:54–79][diag-reporting-consent].
- **Conclusion:** Clear evidence to retain.

1. **Protected risk:** A user revokes contribution consent between a GET and a POST. A temporarily unreadable policy file must also remain distinct from explicit withdrawal.
2. **Does it exist within support?** Yes. Current adapters support withdrawal at any time and independent consent per profile. This external state can change across processes.
3. **Upstream invariant:** An earlier `require_consent` establishes consent only at that moment. After GET/I/O, no invariant guarantees that consent remains valid. `guard_consent` and `check_remote_action` re-read it immediately before a real remote action; these are not redundant checks.
4. **Behavioral effect:** Removal permits a POST after intervening withdrawal. Treating unavailable policy as withdrawn can discard queued evidence.
5. **Validation:** [test_authority_outcomes.py][diag-authority-tests] and [test_reporting_consent.py][diag-consent-tests] use real policy files/SQLite, simulate read failure and explicit withdrawal, and assert request counts, queue state, and payload retention.

<a id="kd-r2"></a>

## KD-R2 · Retain unknown outcomes and reconciliation for irreversible external work

- **Repositories:** `diagnostics`, `knowledge`.
- **Location:** [mindie_diagnostics/reporter.py:542–579][diag-unknown-report]; knowledge [materials/summarizer.py:SummaryLedger, line 470 onward][knowledge-summary-ledger] and [community/publish.py:_resolve_unknown, line 833 onward][knowledge-resolve-unknown].
- **Conclusion:** Clear evidence to retain.

1. **Protected risk:** A paid model call, issue creation, or pull-request creation succeeds remotely, but the connection is lost or the local receipt write fails. Blind retry repeats payment or publication.
2. **Does it exist within support?** Yes. These are real irreversible external writes. A local SQLite failure does not establish that the remote operation did not execute.
3. **Upstream invariant:** A subprocess being started does not establish completion or failure. Only an explicit `not_started` result or reconciliation with a remote marker can resolve the unknown outcome.
4. **Behavioral effect:** Removing `unknown`, or mapping local accounting failure to remote failure, breaks idempotency and truthful reporting of external effects.
5. **Validation:** Use real SQLite plus transport doubles at the external boundary for lost responses, confirmed success followed by receipt-commit failure, and reconciliation after restart. Assert exactly one POST and local reuse of an already saved model result. References: [diagnostics test_reporter.py:48–65][diag-reporter-tests], knowledge [test_summary_attempts.py][knowledge-summary-attempt-tests], and [test_summary_recovery.py][knowledge-summary-recovery-tests].

<a id="kd-r3"></a>

## KD-R3 · Retain read-time membership and content-hash validation

- **Repository:** `knowledge`.
- **Location:** [mindie_knowledge/materials/store.py:_parse_block:166, validate_package_files:178][knowledge-package-validation], [read_current:430–476][knowledge-read-current], and [materials/reme_index.py:StrictFileStore.load:113][knowledge-strict-store].
- **Conclusion:** Clear evidence to retain.

1. **Protected risk:** An external Git package, writable local Markdown, or derived checkpoint is corrupted, returning content other than the current reference's bound content.
2. **Does it exist within support?** Yes. Material files may change across processes, and indexes are rebuildable derived state. Correct types do not establish a valid byte digest or current membership.
3. **Upstream invariant:** Entry validation establishes only the snapshot at that time. The current manifest and `read_ref` may have moved to a new generation. Neither type annotations nor earlier validation exempts a later read.
4. **Behavioral effect:** Removing read-time membership/hash checks can redirect stale references to different content or trust a damaged index.
5. **Validation:** [test_block_read.py][knowledge-block-read-tests], [test_feed_query_visibility.py][knowledge-feed-tests], [test_incremental_resources.py][knowledge-incremental-tests], and [test_material_packages.py][knowledge-package-tests] use real files/SQLite. After rewriting, deletion, or generation changes, invalid reads must fail explicitly rather than silently return old or empty data.

<a id="kd-r4"></a>

## KD-R4 · Retain observable failure isolation in diagnostic recording

- **Repository:** `diagnostics`.
- **Location:** `record_failure`; [mindie_diagnostics/fallback.py:302–369][diag-fallback-record] and [mindie_diagnostics/integration.py:185–266][diag-integration-record].
- **Conclusion:** Clear evidence to retain.

1. **Protected risk:** While reporting a business exception, logging fails again because of disk, locking, or formatting problems and masks the original exception.
2. **Does it exist within support?** Yes. Diagnostics is a side channel and can be called independently by shared components. The [repository contract][diag-agents] explicitly requires that it never raise into callers.
3. **Upstream invariant:** Upstream code does not guarantee diagnostic storage availability. `record_failure` returns `recorded=false`, `logging_failed=true`, and an error, with one stderr notice. This is not a false business-success result.
4. **Behavioral effect:** Removing the catch can replace the original business failure with a diagnostics exception. Do not conflate this observable side-channel failure with swallowing a business error and returning success.
5. **Validation:** [test_integration.py][diag-integration-tests], [test_logging.py][diag-logging-tests], and fallback recording-failure cases must preserve both the original business result and visible `logging_failed` status.

<a id="kd-r5"></a>

## KD-R5 · Establish the public API contract before removing aliases or accepted arguments

- **Repository:** `knowledge`.
- **Location:** [mindie_knowledge/materials/store.py:195, `package_from_files` alias][knowledge-package-alias] and [loop/store.py:533, `advance_search_index(**_budgets)`][knowledge-advance-index].
- **Conclusion:** Insufficient evidence to delete.

1. **Protected risk:** Compatibility with external Python users or older callers.
2. **Does it exist within support?** The organization-wide scan found only argument-free `advance_search_index` calls, but `package_from_files` is exported through `materials.__all__`. No observed call does not establish that a public API has no users.
3. **Upstream invariant:** No published compatibility list proves these public aliases/keyword arguments removable. Plugin registration and dynamic imports were checked; no explicit budget-keyword call was found.
4. **Behavioral effect:** Deletion can raise `ImportError` or `TypeError` for older Python callers. Accepting and ignoring budgets can also mislead callers, but this audit found no actual budget-bearing call chain.
5. **Validation:** Establish supported versions and the public contract first. Identify callers, run cross-repository installation/API smoke tests, and only then consider removal.

[architecture-testing]: https://github.com/mindie-agent/mindie-agent/blob/bc17f3095cdf3cc16bfb1e803a839fd4ad71686b/docs/testing-architecture.md
[bench-broken-install-test]: https://github.com/mindie-agent/mindie-bench/blob/b7301839602ad3791af17f21f5aa47d773b5af2a/tests/test_first_party_mcp.py#L120-L145
[bench-capture-tests]: https://github.com/mindie-agent/mindie-bench/blob/b7301839602ad3791af17f21f5aa47d773b5af2a/tests/test_capture_diagnostics.py
[bench-ci]: https://github.com/mindie-agent/mindie-bench/blob/b7301839602ad3791af17f21f5aa47d773b5af2a/.github/workflows/ci.yml#L26
[bench-component-tests]: https://github.com/mindie-agent/mindie-bench/blob/b7301839602ad3791af17f21f5aa47d773b5af2a/tests/test_component_value_scenarios.py#L8-L37
[bench-consumer]: https://github.com/mindie-agent/mindie-bench/blob/b7301839602ad3791af17f21f5aa47d773b5af2a/src/mindie_bench/integrations/first_party.py#L58-L74
[bench-orchestrator]: https://github.com/mindie-agent/mindie-bench/blob/b7301839602ad3791af17f21f5aa47d773b5af2a/src/mindie_bench/runner/orchestrator.py#L298-L995
[bench-repeat-test]: https://github.com/mindie-agent/mindie-bench/blob/b7301839602ad3791af17f21f5aa47d773b5af2a/tests/test_evaluation_coverage.py#L96-L101
[bench-settlement-tests]: https://github.com/mindie-agent/mindie-bench/blob/b7301839602ad3791af17f21f5aa47d773b5af2a/tests/test_remote_settlement.py
[bench-value-common]: https://github.com/mindie-agent/mindie-bench/blob/b7301839602ad3791af17f21f5aa47d773b5af2a/src/mindie_bench/benchmarks/value_common.py#L24-L33
[bench-value-diagnostics]: https://github.com/mindie-agent/mindie-bench/blob/b7301839602ad3791af17f21f5aa47d773b5af2a/src/mindie_bench/benchmarks/value_diagnostics.py#L82-L86
[bench-verifier]: https://github.com/mindie-agent/mindie-bench/blob/b7301839602ad3791af17f21f5aa47d773b5af2a/src/mindie_bench/runner/verifier.py#L157-L178
[bench-verifier-error]: https://github.com/mindie-agent/mindie-bench/blob/b7301839602ad3791af17f21f5aa47d773b5af2a/src/mindie_bench/runner/verifier.py#L201-L208
[cc-bind-entry]: https://github.com/mindie-agent/mindie-agent-cc/blob/78f34dd9b09e877298225fa243ea4c28978c9dd6/scripts/identity.py#L217-L220
[cc-bind-repeat]: https://github.com/mindie-agent/mindie-agent-cc/blob/78f34dd9b09e877298225fa243ea4c28978c9dd6/scripts/identity.py#L253-L255
[cc-finish]: https://github.com/mindie-agent/mindie-agent-cc/blob/78f34dd9b09e877298225fa243ea4c28978c9dd6/scripts/identity.py#L324-L342
[cc-mcp]: https://github.com/mindie-agent/mindie-agent-cc/blob/78f34dd9b09e877298225fa243ea4c28978c9dd6/scripts/mcp_server.py#L301-L369
[cc-mcp-contract]: https://github.com/mindie-agent/mindie-agent-cc/blob/78f34dd9b09e877298225fa243ea4c28978c9dd6/scripts/mcp_server.py#L11-L14
[cc-transcript-anchor]: https://github.com/mindie-agent/mindie-agent-cc/blob/78f34dd9b09e877298225fa243ea4c28978c9dd6/scripts/transcript.py#L374-L382
[coord-agents]: https://github.com/mindie-agent/coordinator/blob/c77144a95dd6af37e978ffc2d8495158b237090d/AGENTS.md#L5
[coord-atomic-test]: https://github.com/mindie-agent/coordinator/blob/c77144a95dd6af37e978ffc2d8495158b237090d/tests/test_npu_coordination.py#L341-L374
[coord-configured-machines]: https://github.com/mindie-agent/coordinator/blob/c77144a95dd6af37e978ffc2d8495158b237090d/mindie_coordinator/service.py#L947-L961
[coord-dependencies]: https://github.com/mindie-agent/coordinator/blob/c77144a95dd6af37e978ffc2d8495158b237090d/pyproject.toml#L14-L15
[coord-dispatch-tests]: https://github.com/mindie-agent/coordinator/blob/c77144a95dd6af37e978ffc2d8495158b237090d/tests/test_completion_dispatch.py
[coord-finish-managed]: https://github.com/mindie-agent/coordinator/blob/c77144a95dd6af37e978ffc2d8495158b237090d/mindie_coordinator/managed_execution.py#L435-L445
[coord-host-template]: https://github.com/mindie-agent/coordinator/blob/c77144a95dd6af37e978ffc2d8495158b237090d/mindie_coordinator/provision/host_ops.py#L1414-L2424
[coord-machine-load]: https://github.com/mindie-agent/coordinator/blob/c77144a95dd6af37e978ffc2d8495158b237090d/mindie_coordinator/machine_directory.py#L222-L243
[coord-owned-tests]: https://github.com/mindie-agent/coordinator/blob/c77144a95dd6af37e978ffc2d8495158b237090d/tests/test_owned_completion.py
[coord-place]: https://github.com/mindie-agent/coordinator/blob/c77144a95dd6af37e978ffc2d8495158b237090d/mindie_coordinator/service.py#L918-L923
[coord-process-guard]: https://github.com/mindie-agent/coordinator/blob/c77144a95dd6af37e978ffc2d8495158b237090d/mindie_coordinator/host/mindie_npu_coordination.py#L146-L177
[coord-progress]: https://github.com/mindie-agent/coordinator/blob/c77144a95dd6af37e978ffc2d8495158b237090d/mindie_coordinator/service.py#L629-L852
[coord-terminal-set]: https://github.com/mindie-agent/coordinator/blob/c77144a95dd6af37e978ffc2d8495158b237090d/mindie_coordinator/managed_execution.py#L43
[coord-token]: https://github.com/mindie-agent/coordinator/blob/c77144a95dd6af37e978ffc2d8495158b237090d/mindie_coordinator/host/mindie_npu_coordination.py#L835-L837
[coord-wait-runtime]: https://github.com/mindie-agent/coordinator/blob/c77144a95dd6af37e978ffc2d8495158b237090d/mindie_coordinator/service.py#L672-L676
[coord-watch-state]: https://github.com/mindie-agent/coordinator/blob/c77144a95dd6af37e978ffc2d8495158b237090d/mindie_coordinator/managed_execution.py#L356
[diag-agents]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/AGENTS.md
[diag-authority-tests]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/tests/test_authority_outcomes.py
[diag-bundle-tests]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/tests/test_bundle.py
[diag-cli-tests]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/tests/test_profiler_cli_compare.py
[diag-compare-cli]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/mindie_profiler/cli_compare.py#L101-L117
[diag-compare-contract]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/README.md#L185
[diag-compare-tests]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/tests/test_profiler_compare.py#L75-L111
[diag-consent-action]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/mindie_diagnostics/reporter.py#L521-L550
[diag-consent-tests]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/tests/test_reporting_consent.py
[diag-fallback-record]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/mindie_diagnostics/fallback.py#L302-L369
[diag-integration-record]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/mindie_diagnostics/integration.py#L185-L266
[diag-integration-tests]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/tests/test_integration.py
[diag-label]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/mindie_diagnostics/bundle.py#L68-L73
[diag-label-exit]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/mindie_diagnostics/bundle.py#L187-L190
[diag-label-repeat]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/mindie_diagnostics/bundle.py#L159-L160
[diag-logging-tests]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/tests/test_logging.py
[diag-memory-compare]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/mindie_profiler/memory_compare.py#L56-L65
[diag-memory-tests]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/tests/test_profiler_memory.py#L318-L335
[diag-redact]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/mindie_diagnostics/redact.py
[diag-redact-tests]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/tests/test_redact.py
[diag-reporter-tests]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/tests/test_reporter.py#L48-L65
[diag-reporting-consent]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/mindie_diagnostics/reporting.py#L54-L79
[diag-step-accounting]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/mindie_profiler/compare.py#L531-L553
[diag-unknown-report]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/mindie_diagnostics/reporter.py#L542-L579
[diag-workload]: https://github.com/mindie-agent/diagnostics/blob/6460cde3a50a7f91c9ded38557a7f921654f0c6a/mindie_profiler/compare.py#L502-L516
[dsh-agents]: https://github.com/mindie-agent/mindie-agent-dsh/blob/d3a1e1282356b65b51fba49072c1842918746f8f/AGENTS.md
[dsh-anchor]: https://github.com/mindie-agent/mindie-agent-dsh/blob/d3a1e1282356b65b51fba49072c1842918746f8f/scripts/dsh_transcript.py#L191-L198
[dsh-append-test]: https://github.com/mindie-agent/mindie-agent-dsh/blob/d3a1e1282356b65b51fba49072c1842918746f8f/tests/test_dsh_transcript.py#L151-L164
[dsh-connection]: https://github.com/mindie-agent/mindie-agent-dsh/blob/d3a1e1282356b65b51fba49072c1842918746f8f/scripts/mindie_sidecar.py#L281-L290
[dsh-decompress]: https://github.com/mindie-agent/mindie-agent-dsh/blob/d3a1e1282356b65b51fba49072c1842918746f8f/scripts/dsh_transcript.py#L92-L114
[dsh-identify]: https://github.com/mindie-agent/mindie-agent-dsh/blob/d3a1e1282356b65b51fba49072c1842918746f8f/scripts/dsh_transcript.py#L64-L74
[dsh-paths]: https://github.com/mindie-agent/mindie-agent-dsh/blob/d3a1e1282356b65b51fba49072c1842918746f8f/scripts/mindie_paths.py#L60-L65
[dsh-project-budget]: https://github.com/mindie-agent/mindie-agent-dsh/blob/d3a1e1282356b65b51fba49072c1842918746f8f/scripts/dsh_transcript.py#L247-L259
[dsh-read-budget]: https://github.com/mindie-agent/mindie-agent-dsh/blob/d3a1e1282356b65b51fba49072c1842918746f8f/scripts/dsh_transcript.py#L210-L226
[dsh-setup-main]: https://github.com/mindie-agent/mindie-agent-dsh/blob/d3a1e1282356b65b51fba49072c1842918746f8f/scripts/setup.py#L313-L334
[dsh-setup-runtime]: https://github.com/mindie-agent/mindie-agent-dsh/blob/d3a1e1282356b65b51fba49072c1842918746f8f/scripts/setup.py#L113-L125
[dsh-setup-stop]: https://github.com/mindie-agent/mindie-agent-dsh/blob/d3a1e1282356b65b51fba49072c1842918746f8f/scripts/setup.py#L183-L196
[dsh-updater]: https://github.com/mindie-agent/mindie-agent-dsh/blob/d3a1e1282356b65b51fba49072c1842918746f8f/scripts/updater.py#L268-L277
[dsh-updater-tests]: https://github.com/mindie-agent/mindie-agent-dsh/blob/d3a1e1282356b65b51fba49072c1842918746f8f/tests/test_updater.py#L38-L75
[kimi-finish]: https://github.com/mindie-agent/mindie-agent-kimi/blob/0e78f0422162a61e8c56850e049f9e5fc4d290b5/scripts/identity.py#L532-L547
[kimi-mcp]: https://github.com/mindie-agent/mindie-agent-kimi/blob/0e78f0422162a61e8c56850e049f9e5fc4d290b5/scripts/mcp_server.py#L318-L367
[kimi-transcript-anchor]: https://github.com/mindie-agent/mindie-agent-kimi/blob/0e78f0422162a61e8c56850e049f9e5fc4d290b5/scripts/transcript.py#L231-L238
[knowledge-accept-stop]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/mindie_knowledge/loop/handoff.py#L385-L638
[knowledge-advance-index]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/mindie_knowledge/loop/store.py#L533
[knowledge-agents]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/AGENTS.md
[knowledge-block-read-tests]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/tests/test_block_read.py
[knowledge-capture-store]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/mindie_knowledge/loop/store.py#L332-L395
[knowledge-capture-tests]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/tests/test_capture_handoff.py
[knowledge-config-mode]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/mindie_knowledge/loop/cli.py#L66-L67
[knowledge-dependencies]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/pyproject.toml#L21
[knowledge-feed-tests]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/tests/test_feed_query_visibility.py
[knowledge-handoff-test]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/tests/test_capture_handoff.py#L151-L178
[knowledge-incremental-tests]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/tests/test_incremental_resources.py
[knowledge-live-probe]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/tests/test_live_npu_knowledge_loop.py#L32-L60
[knowledge-material-pointers]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/mindie_knowledge/materials/store.py#L275
[knowledge-material-refresh]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/mindie_knowledge/materials/store.py#L795
[knowledge-package-alias]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/mindie_knowledge/materials/store.py#L195
[knowledge-package-tests]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/tests/test_material_packages.py
[knowledge-package-validation]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/mindie_knowledge/materials/store.py#L166-L194
[knowledge-pinned-handoff]: https://github.com/mindie-agent/knowledge/blob/4e328305323eafc7fd43ecc0c53eb3cc0541fdef/mindie_knowledge/loop/handoff.py#L460-L477
[knowledge-pinned-material]: https://github.com/mindie-agent/knowledge/blob/4e328305323eafc7fd43ecc0c53eb3cc0541fdef/mindie_knowledge/materials/store.py
[knowledge-pinned-service]: https://github.com/mindie-agent/knowledge/blob/4e328305323eafc7fd43ecc0c53eb3cc0541fdef/mindie_knowledge/loop/cli.py#L130-L191
[knowledge-pr-review]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/.github/workflows/pr-review.yml
[knowledge-query]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/mindie_knowledge/loop/store.py#L1144-L1170
[knowledge-query-request]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/mindie_knowledge/materials/provenance.py#L36-L50
[knowledge-query-tests]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/tests/test_material_query.py
[knowledge-read-current]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/mindie_knowledge/materials/store.py#L430-L476
[knowledge-resolve-unknown]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/mindie_knowledge/community/publish.py#L833
[knowledge-search-validation]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/mindie_knowledge/materials/store.py#L760-L762
[knowledge-short-tests]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/tests/test_short_handoff.py
[knowledge-strict-store]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/mindie_knowledge/materials/reme_index.py#L113
[knowledge-summary-attempt-tests]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/tests/test_summary_attempts.py
[knowledge-summary-fallback]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/mindie_knowledge/loop/handoff.py#L460-L477
[knowledge-summary-ledger]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/mindie_knowledge/materials/summarizer.py#L470
[knowledge-summary-recovery-tests]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/tests/test_summary_recovery.py
[knowledge-summary-test]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/tests/test_domain_retrieval_and_summary_quality.py#L281-L399
[knowledge-wake-tests]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/tests/test_capture_wake.py
[knowledge-worker-fixture]: https://github.com/mindie-agent/knowledge/blob/021ba95e701d4f8c8d924e2dcc8f120a4939da23/tests/material_worker_fixture.py#L1-L27
[npu-api-live]: https://github.com/mindie-agent/npu-top/blob/8f992bf033af57979d6bebf67189a89bb2034d7e/npu_top/api.py#L142
[npu-collect-cycle]: https://github.com/mindie-agent/npu-top/blob/8f992bf033af57979d6bebf67189a89bb2034d7e/npu_top/scheduler.py#L218-L250
[npu-collect-wait]: https://github.com/mindie-agent/npu-top/blob/8f992bf033af57979d6bebf67189a89bb2034d7e/npu_top/scheduler.py#L100-L116
[npu-env]: https://github.com/mindie-agent/npu-top/blob/8f992bf033af57979d6bebf67189a89bb2034d7e/npu_top/settings.py#L15-L21
[npu-heartbeat]: https://github.com/mindie-agent/npu-top/blob/8f992bf033af57979d6bebf67189a89bb2034d7e/npu_top/scheduler.py#L67-L77
[npu-legacy-settings]: https://github.com/mindie-agent/npu-top/blob/8f992bf033af57979d6bebf67189a89bb2034d7e/npu_top/settings.py#L80-L99
[npu-package]: https://github.com/mindie-agent/npu-top/blob/8f992bf033af57979d6bebf67189a89bb2034d7e/package.json#L9-L13
[npu-probe-cache]: https://github.com/mindie-agent/npu-top/blob/8f992bf033af57979d6bebf67189a89bb2034d7e/npu_top/probe.py#L682-L692
[npu-run-loop]: https://github.com/mindie-agent/npu-top/blob/8f992bf033af57979d6bebf67189a89bb2034d7e/npu_top/scheduler.py#L168-L190
[npu-scheduler-tests]: https://github.com/mindie-agent/npu-top/blob/8f992bf033af57979d6bebf67189a89bb2034d7e/tests/test_scheduler.py#L15-L57
[npu-settings-tests]: https://github.com/mindie-agent/npu-top/blob/8f992bf033af57979d6bebf67189a89bb2034d7e/tests/test_settings_mindie.py
[remote-file-module]: https://github.com/mindie-agent/remote-dev/blob/c3af104c36582c675a6dcd368637db7c60b28afd/remote_dev/core/remote_file_worker.py
[remote-file-resolve]: https://github.com/mindie-agent/remote-dev/blob/c3af104c36582c675a6dcd368637db7c60b28afd/remote_dev/core/remote_file_worker.py#L35-L58
[remote-file-write]: https://github.com/mindie-agent/remote-dev/blob/c3af104c36582c675a6dcd368637db7c60b28afd/remote_dev/core/remote_file_worker.py#L77-L91
[remote-glob-entry]: https://github.com/mindie-agent/remote-dev/blob/c3af104c36582c675a6dcd368637db7c60b28afd/remote_dev/core/search_ops.py#L573-L584
[remote-glob-worker]: https://github.com/mindie-agent/remote-dev/blob/c3af104c36582c675a6dcd368637db7c60b28afd/remote_dev/core/search_ops.py#L317-L352
[remote-grep-tests]: https://github.com/mindie-agent/remote-dev/blob/c3af104c36582c675a6dcd368637db7c60b28afd/tests/test_grep_fallback.py#L51-L71
[remote-path-policy]: https://github.com/mindie-agent/remote-dev/blob/c3af104c36582c675a6dcd368637db7c60b28afd/remote_dev/core/path_policy.py#L4-L39
[remote-python-fallback]: https://github.com/mindie-agent/remote-dev/blob/c3af104c36582c675a6dcd368637db7c60b28afd/remote_dev/core/search_ops.py#L316
[remote-readme]: https://github.com/mindie-agent/remote-dev/blob/c3af104c36582c675a6dcd368637db7c60b28afd/README.md
[remote-root-contract]: https://github.com/mindie-agent/remote-dev/blob/c3af104c36582c675a6dcd368637db7c60b28afd/docs/transport-and-diagnostics.md#L64
[remote-search-string]: https://github.com/mindie-agent/remote-dev/blob/c3af104c36582c675a6dcd368637db7c60b28afd/remote_dev/core/search_ops.py#L26-L531
[workspace-main]: https://github.com/mindie-agent/vllm-ascend-workspace/blob/c85b9ca94c5432a58f3e0bff6bbbcd5d711d8ca8/.agents/scripts/workspace.py#L13-L135

# Diagnostics & Opt-In Fault Reporting

[中文](diagnostics-and-reporting.md) · [Back to Documentation Center](README.en.md)

This document explains how MindIE Agent records bounded local diagnostic logs, helps Agents pinpoint the exact stage and cause of a tool failure, and supports opt-in GitHub Issue reporting with strict privacy guarantees and deduplication.

- Governed by: [Engineering Design Principles](design-principles.en.md)
- Core Component Repository: [`mindie-agent/diagnostics`](https://github.com/mindie-agent/diagnostics)
- Release & Verification Records: [Release Records & Roadmap](README.en.md#release-records--roadmap)

---

## 1. Core Goal: Clear, Actionable, Privacy-Safe Diagnostics

When a remote command or background indexing step fails, a vague error string wastes time for both you and your Agent. MindIE Agent's diagnostic system is designed around two simple goals:
- **Give the Agent immediate clarity**: Every tool failure tells the caller which stage failed, which side effects already completed, and which local diagnostic ID holds the detailed context—so the Agent can fix the issue or switch strategies immediately.
- **Zero daily ceremony**: Neither you nor the Agent needs to manage log pipelines, run end-of-task log analyzers, or worry about automatic background retries.

---

## 2. Unified Contribution Switch & Everyday Experience

1. **Bounded Local Structured Logs (Always Available)**:
   - Components write structured local logs at real operational boundaries. When a tool call fails, the error response includes a random diagnostic correlation ID, a static error category, and a recovery hint alongside the original exit status and cleanup outcome.
2. **A Single Contribution Switch Controls Knowledge Sharing and Fault Reporting**:
   - Setup explains both outgoing actions: contributing redacted knowledge packages within approved project scope and filing allowlisted tool fault metadata in the product repository. **The switch is off by default and takes effect only when explicitly enabled**.
   - The installation profile's `mindie-consent.json` is the sole authority for contribution consent. Reporter configuration stores the destination repository, log roots, and a reference to that consent file; fault recording, queue ingestion, and final submission all verify the same `choice` and `choice_revision`.
   - **Three Distinct States**: The system keeps **configuration written**, **background reporter worker running**, and **external GitHub Issue published** strictly separate. Enabling the switch configures knowledge sharing and provisions the native background reporter, returning their readiness outcomes separately; service startup errors remain visible and can self-heal on subsequent runs. Disabling the switch immediately stops new outgoing sends on both paths while local diagnostic logs and queries remain available.
   - **No Silent Expansion on Upgrade**: Existing `disabled`, `later`, and `read-only` choices stay off across upgrades. Legacy knowledge-only `contribute` records lacking the unified consent revision do **not** automatically gain fault-reporting permission on upgrade; users opt in explicitly once through the unified contribution entry.
   - **Reuses the Verified `gh` Channel**: Automatic reporting uses the authenticated GitHub CLI (`gh`) verified during installation. Plugin-bundled `knowledge`, `remote-dev`, and the background reporter share the same profile diagnostics path; standalone `remote-dev` deployments retain their explicitly configured reporting policy.

---

## 3. Component Responsibilities

| Module / Role | Responsibility |
| --- | --- |
| **Harness Plugin Adapters** (`mindie-agent-cc` / `-codex` / `-kimi` / `-dsh`) | Log native entrypoint, Hook, MCP startup, and protocol errors; provide setup toggles and human-readable status |
| **Runtime Components** (`knowledge` / `remote-dev`) | Record stage, version, monotonic duration, exit code, and cleanup outcome at the exact boundary where an internal fault occurs, cleanly separating normal user-command exits from internal tool bugs |
| **Diagnostics Engine** (`diagnostics`) | Enforce log schemas, allowlist-only redaction, bounded disk rotation, fingerprint deduplication, finite retry budgets, and GitHub Issue creation |
| **GitHub Maintainers** | Investigate reported fault evidence and ship fixes |

When a shared component has already logged an internal fault, it passes a trusted diagnostic reference ID to the outer plugin layer so the same error is never logged or reported twice.

---

## 4. Strict Privacy Boundary: What Can and Cannot Leave Your Machine

Public GitHub Issues are assembled deterministically from **allowlisted metadata fields** without calling any LLM:

- **Allowed in public Issues (code & execution metadata only)**:
  - Component name, package version or Git commit SHA, operation name, stage, static error category/code, duration, exit code, and cleanup outcome. A stable public fault fingerprint supports deduplication; random diagnostic correlation IDs and process clocks stay local.
- **Strictly excluded from public Issues**:
  - **Never included**: User commands, command arguments, environment variables, raw `stdout`/`stderr`, free-text exception messages, conversation transcripts, config files, credentials/tokens, native task IDs, remote job IDs, local or remote file paths, and hostnames or IP addresses.
- **What never triggers an Issue**:
  - Invalid arguments, missing configuration, user cancellation (Interrupt), disabled features, permission errors, ordinary network/SSH authentication failures, and **non-zero exit codes or timeouts from your own remote commands** are normal operational outcomes and never file product-defect Issues.
  - Only unhandled internal exceptions, abnormal crashes of owned helper subprocesses, protocol corruption, or missing package files qualify as reportable tool faults.

---

## 4.1 Update Failure Coverage and Reporting Eligibility

`diagnostics` (`v0.5.4`) provides a shared `category="update"` recorder policy based on exception types, structured codes, and retained causes. It never analyzes free-form exception text. Missing modules and broken artifacts or protocols are product faults; transport, credentials, permissions, cancellation, and local prerequisites remain visible locally. Plugins record failures at their boundaries instead of only saving an updater receipt or marking every update failure non-reportable.

All four host plugins (Codex `v0.1.13`, Claude Code `v0.1.10`, Kimi `v0.1.10`, and DSH `v0.1.9`) adopt this policy, covering component-inheritance helper startup failures and updater children that crash before writing a receipt. Trusted inner incident references are reused across outer boundaries. Plugin baselines pin formal `diagnostics v0.5.4` and use the package manager to override older transitive diagnostics pins.

Recent local failures include `error_code` and `reporting_eligibility`:

| Eligibility | Meaning |
| --- | --- |
| `local_only` | Recorded locally; excluded from automatic reporting by classification or caller policy |
| `not_authorized_at_capture` | No reporting consent at capture; enabling it later never backfills this event |
| `other_profile` | Belongs to another profile and is not consumed by this profile |
| `consent_allowed` | Currently eligible; consult the queue for ingestion and delivery outcomes |
| `consent_withdrawn` / `consent_unavailable` | Revoke delivery or retain evidence until authority can be read again, respectively |

This bounded view reads at most eight 16 KiB log tails and returns five failures. `truncated` marks an incomplete window, not a global failure count. A healthy worker, an upgraded diagnostics package, a recorded event, a queued incident and a GitHub acknowledgment are separate facts. Only a `published` receipt and its issue establish successful delivery. A new version cannot reconstruct failures an older plugin never recorded.

---

## 5. Deduplication & Recoverable Delivery Queue (Loop Prevention)

To prevent duplicate Issues and retain pending reports across transient network outages:

1. **Cross-task fingerprint deduplication**:
   - Faults sharing the same component version, operation, stage, error category, and internal stack frame location produce a deterministic fingerprint. Switching sessions or host CLIs never creates a duplicate Issue for an already reported bug; read-only GitHub lookup links matching faults to the existing Issue without spamming comments.
2. **Bounded requests and recoverable pending reports**:
   - Each processing cycle operates under a bounded request deadline. Temporary network or GitHub authentication failures preserve pending records, surface the actual error, and defer retries rather than dropping faults after transient read-only lookup failures.
   - Only a submission that may have reached GitHub without a response is marked `unknown` and reconciled read-only via **bounded 2-attempt outbound reconciliation** before any write. A subprocess that never started or a request explicitly rejected by the server is never misclassified as `unknown`.
   - If GitHub confirms Issue creation but local receipt persistence fails, the local storage error is reported separately without reversing the completed external result. Disabling the contribution switch stops unsent queue items immediately; re-enabling processes only events recorded under the new consent revision.
3. **No self-reporting loops**:
   - Failures inside the reporter itself stay strictly local so the reporter never files Issues about its own reporting errors.

---

## 6. Local Log Rotation & Artifact Separation

- **Bounded disk usage**: Local logs enforce per-entry and per-segment size limits and automatically prune expired segments during routine maintenance (even when remote Issue reporting is disabled).
- **Reader & writer safety**: Log rotation protects active writers and registered reader cursors so unread segments are never clobbered.
- **User job outputs are never truncated as logs**: In `remote-dev`, `stdout`/`stderr` streams from your remote commands are preserved as formal job output artifacts under the job lifecycle—never truncated by diagnostic log limits.

---

## 7. Deterministic Ascend NPU & CANN Fault Triage (`npu_fault_triage`)

Beyond internal tool telemetry, `diagnostics` includes a **zero-LLM, deterministic Ascend NPU runtime fault classifier (`triage_npu_fault`)** distilled from [CANNBot Skills](https://gitcode.com/cann/cannbot-skills), enabling Agents to classify CANN error codes and immediately invoke the right native forensic utilities:

| Fault Category (`category`) | Canonical CANN / Driver Error Codes & Signatures | Deterministic CANN Toolchain Triage & Remediation |
| --- | --- | --- |
| **`aicore_exception`** | `EZ9999`, `507015`, `Aicore Error`, `BIU`/`MTE2`/`MTE3`/`VEC`/`CUBE` exception bitmaps, out-of-bounds GM/UB access | Run `asys collect` for one-shot dump collection, decode fault registers via `msaicerr -i <dump_dir>`, and map the faulting PC with `npu-objdump` to verify 32B alignment and tiling bounds |
| **`ascendc_sync_hazard`** | `SetFlag`/`WaitFlag` pair mismatch, `CrossCoreWaitFlag` deadlock, or branch-divergent barriers causing stream timeout (`507018`) | Audit `SetFlag`/`WaitFlag` branch symmetry, loop-carried double-buffer release invariants, and `HardEvent` (`MTE2_V` / `V_MTE3` / `MTE1_M` / `M_FIX`) pairing |
| **`hccl_comm_fault`** | `EI0002` (link down), `EI0004` (topology mismatch), `EI0006` / `Notify Wait Timeout`, `HCCL_BUFFSIZE` exhaustion, or idle-DP collective hang | Enable `HCCL_ENTRY_LOG_ENABLE=1`, inspect RoCE/HCCS/SIO links via `hccn_tool` and `npu-smi info -t topo`, or isolate the collective via `HVM` |
| **`device_oom`** | `EL0004`, `E80000`, `NPU out of memory`, `ACL_ERROR_RT_MEMORY_ALLOCATION` | Audit `max_rank_workspace_delta_bytes`, KV Cache reservation ratios, and GE graph memory reuse settings |
| **`npugraph_compile_or_capture`** | `torch.npugraph_ex` guard invalidation, host-device sync inside `ACLGraph` capture, or GE dynamic-shape symbolic tiling failure | Run `npugraph_ex` DFX bisect (Compile/Runtime/Perf triage), pin static bucket shapes, and remove host-dependent branches from capture regions |
| **`device_hardware_or_driver`** | `507035`, uncorrectable ECC errors, lost NPU device, or driver handshake failure | Run `asys check` and `msnpureport` to export device firmware logs and quarantine the affected card/Die in `coordinator` |
| **`vllm_ascend_aclgraph_capture_failure`** | `207008`, `EL0009`, `ACL_ERROR_RT_STREAM_NO_CB_REG`, `update_stream_limit`, `aclmdlRIExecuteAsync`, or dynamic control flow / D2H sync inside `ACLGraph` capture | Inspect `torchair_graph_config` / `cudagraph_capture_sizes`, remove `.item()` / `.cpu()` syncs from capture regions, or fall back to `--enforce-eager` / `PIECEWISE` graph mode |
| **`vllm_ascend_idle_dp_collective_hang`** | Multi-DP + EP/TP hang where an idle DP rank (`active_batch == 0`) skips dummy forward or `GDN`/`KDA` state padding, triggering `HCCL_E_WAIT_TIMEOUT` | Ensure all DP ranks enter `coordinate_batch_across_dp` dummy forward and maintain zero-padded `GDN`/`KDA` workspace alignment |
| **`msmodelslim_quant_weight_or_scale_mismatch`** | Missing keys in `quant_model_description.json`, `deq_scale`/`quant_bias`/`input_scale` shape or dtype mismatch, `W8A8_DYNAMIC` vs. static mismatch, or `MXFP8`/`MXFP4` `group_size != 32` | Verify `--quantization ascend` against `quant_model_description.json`, apply SmoothQuant/QuaRot outlier suppression, and fall back sensitive layers to `FLOAT` (BF16/FP16) |
| **`numerical_nan_inf_or_determinism_drift`** | `msprobe` / `PrecisionDebugger` cosine similarity drop, `NaN`/`Inf` overflow, FP16 accumulator underflow, or non-deterministic reduction drift | Run `msprobe` layerwise dumps to isolate the first diverging operator, and enable `LCCL_DETERMINISTIC=1`, `HCCL_DETERMINISTIC=true`, `CLOSE_MATMUL_K_SHIFT=1`, or `batch_invariance` |
| **`mooncake_or_kv_pool_transfer_fault`** | `MooncakeConnector` / `LMCacheConnector` / `AscendStoreConnector` KV transfer timeout, `KVCache register_memory` failure, or asymmetric P/D TP slice mismatch | Verify `HCCL_SOCKET_IFNAME` / RoCE reachability, RDMA memory registration limits, and asymmetric TP divisibility (`tp_p >= tp_d` and `tp_p % tp_d == 0`) |
| **`custom_op_abi_or_symbol_shadowing`** | `161001` (`ACLNN_ERR_PARAM_NULLPTR`), `561000`/`561103`, undefined symbols in `_C_ascend`/`libascend_kernels.so`, `opapi_math` shadowing `libopapi.so`, missing `Meta` kernel registration, or `FIA` `errcode 264` (`tiling offset out of range`) | Verify custom-op ABI and `libopapi.so` symbol binding via `ldd`/`nm -D`; register both `PrivateUse1` and `Meta` kernels in `TORCH_LIBRARY_IMPL`; align `FIA` `actual_seq_lengths_kv` counting domain with tensor rank (3D BSH/BSND vs. 4D BNSD) under MTP (`step >= 1`) |
| **`multithread_npu_context_or_rogue_device0`** | `107003` (`ACL_ERROR_RT_CONTEXT_NULL`), missing NPU context in `ThreadPoolExecutor`/ZMQ callback threads, or unexpected `device 0` HBM allocation on multi-card workers | Call `torch.npu.set_device(device_id)` explicitly in every worker thread; trace rogue `device 0` context creation non-intrusively via `perf probe -x libascendcl.so 'aclrtSetDevice deviceId=%x0:s32'` |
| **`enginecore_shm_or_zmq_frame_corruption`** | `vllm` `EngineCore` `shm_broadcast` / `MessageQueue` ring-buffer corruption or `multiproc_executor` `EOFError`/`UnpicklingError` where `/v1/models` returns HTTP 200 while `/v1/chat/completions` hangs | Inspect `EngineCore` liveness and ZMQ `DEALER/ROUTER` multipart framing, and check for oversized/truncated `SchedulerOutput` shared-memory chunks |

Complementing runtime fault triage, `coordinator` ([`env_manager.py`](https://github.com/mindie-agent/coordinator), [`fleet_probe.py`](https://github.com/mindie-agent/coordinator), and [`checkpoint_preflight.py`](https://github.com/mindie-agent/coordinator)), `npu-top` ([`probe.py`](https://github.com/mindie-agent/npu-top)), and `mindie-bench` ([`cann_sentry_eval.py`](https://github.com/mindie-agent/mindie-bench)) enforce deterministic pre-launch, probe, and benchmark validity guardrails:
- **Runtime Environment, SoC Feature Matrix & NUMA Preflight**: Catches `ACLGraph` + `ASCEND_LAUNCH_BLOCKING=1` conflicts, missing custom op `op_api/lib` paths, multi-node `HCCL_SOCKET_IFNAME`/`GLOO_SOCKET_IFNAME` mismatches, missing `expandable_segments:True` fragmentation hazards, cross-generation SoC (`310P` / `910B` A2 / `910_93` A3 / `950` A5) feature mismatches, and NUMA/IRQ CPU binding collisions before workload launch.
- **Zero-NPU Safetensors Header & Quantization Contract Inspector (`inspect_safetensors_checkpoint`)**: Reads only the 8-byte header length + JSON metadata of `.safetensors` shards (`< 100ms`) before acquiring NPU leases to verify shard completeness, detect truncated files, compute per-role dtype byte breakdowns, catch unquantized `BF16`/`F16` routed experts inside checkpoints claiming W8A8/W4A8 quantization, and flag `head_dim` values unaligned to Ascend's 32B UB boundary.
- **Linux `/proc/<pid>` Disk I/O `D`-State (`wchan`) vs. True NPU Hang Attribution**: `fleet_probe` and `npu-top` sample `/proc/<pid>/status` (`State`) and `/proc/<pid>/wchan` for NPU processes, flagging `disk_io_wait=True` when `aicore_pct == 0%` is caused by uninterruptible page-cache/NFS reads (`D` state, e.g., `lock_page_killable` / `nfs_*` / `folio_wait*`) rather than an HCCL collective deadlock.
- **Inference Benchmark Validity Auditor (`audit_inference_benchmark_validity`)**: Flags unexcluded warmup or graph-capture steps, accuracy claims on `--load-format dummy` or uncalibrated quantized weights, speculative decoding (MTP/EAGLE/DSpark) latency claims missing `acceptance_rate` / `mean_accepted_tokens` normalization, short output windows (`output_len < 32`) misrepresented as steady-state decode TPOT, PD disaggregated silent fallback to local prefill recomputation (`transferred_kv_bytes == 0`), conflicting `--enforce-eager` + `cudagraph_mode` flags or unpurged `.torchair_cache` after C++ custom-op mutation, and HTTP benchmark clients run over VPN/WAN RTT.

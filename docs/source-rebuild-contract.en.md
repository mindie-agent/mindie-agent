# Source Development, Native Rebuilds and Artifact Recovery

[中文](source-rebuild-contract.md) · [Back to Documentation Center](README.en.md)

This contract governs remote source development, C++/AscendC native rebuilds, and baseline binary recovery across `vLLM`, `vLLM-Ascend`, and related Ascend frameworks. Users may start a task from any local directory, from a directoryless chat session, or directly inside a framework checkout; runtime behavior must never depend on launching from the `mindie-agent` repository or reading its `AGENTS.md`.

Core rule: **Always honor the source directory and Python runtime explicitly chosen by the user; when no preference is stated, edit the existing target checkout in place and retain its compatible runtime environment.** Source checkout path, build output directory, Python interpreter, and baseline backup location are four independent decisions—needing a native rebuild never justifies silently cloning sources under `/opt` or creating an unrequested virtual environment.

## Unified implementation sequence

Deliver the user's goal directly along existing task logs and execution paths without introducing a parallel workspace manager, global environment registry, or shadow state machine:

| Stage | Owner and implementation | Completion condition |
|---|---|---|
| **Establish the goal** | Agent determines the target endpoint/container, source checkout, Python interpreter, and isolation mode from user intent; shared MCP tool schemas surface these boundaries directly | Source path, Python environment, and cleanup scope are each explicit; sufficient existing session authorization is reused directly |
| **Obtain needed facts** | `remote-dev` runs import-free interpreter and editable-source discovery (`remote_probe`) with either an explicit interpreter or bounded candidate scanning | Returns `sys.prefix`, ABI, installed distributions, and editable source paths (preserving partial facts on error); static metadata never substitutes for runtime loading checks |
| **Select execution mode** | In-place remote development uses `remote-dev` file/shell tools plus `coordinator` resource leases; `coordinator` `mindie.run` is reserved for snapshot materialization and isolated runs | Requiring compilation never silently switches directories or execution modes; preparation, execution, and rollback share the exact same interpreter identity |
| **Build and recover** | Build using the checked-out revision's supported procedure; back up affected baseline binaries before overwriting, then verify actual library loading and operator correctness in a fresh process | Python-only edits reuse compatible native binaries; native C++/AscendC edits rebuild the minimal affected scope; candidate verification and rollback status are reported separately |
| **Continue around unsuitable helpers** | When standard discovery or preparation helpers do not fit, the Agent continues within existing authorization via CLIs, native host tools/SSH, or task-local scripts; failure payloads expose `next` continuation routes | Optional helpers never act as whole-task gates; original job/endpoint references remain intact and `unknown` external writes are reconciled read-only before replacement |
| **Accept and deliver** | Run affected local contract tests, non-destructive remote checks, and live Canary tasks; publish shared dependencies before downstream consumers | Pass scoped `R1–R6` gates before release; unexecuted native builds or NPU checks remain explicitly marked pending rather than masked by metadata unit tests |

Tools own bounded, deterministic mechanics and honest observations; the Agent owns task-level judgment. Automatic environment discovery, standard build wrappers, build caches, and managed preparation are replaceable conveniences—within authorized scope, the Agent can gather required facts through equivalent CLI commands or task scripts without waiting to patch every MindIE helper first.

## 1. Directory selection and observed problem

In a prior user incident, an existing checkout lived at `/vllm-workspace/vllm-ascend`, yet after modifying and rebuilding the project, `pip show` reported `Editable project location` under a newly created `/opt/vllm-ascend-...` directory. While the terminal screenshot alone could not identify which command created `/opt/vllm-ascend-...`, whether uncommitted edits remained in the original checkout, which `.so` files running processes had mapped, or whether pre-change binaries survived on disk, it confirmed unintended editable-binding drift.

Auditing `remote-dev` confirmed that no tool automatically clones repositories into `/opt` or rewrites editable bindings behind the scenes. Instead, the gap lay in missing environment visibility: `remote-dev` defaulted `root` to `/` as a file-access boundary, and early `remote_probe` inspected only that root's Git metadata—offering neither a target Python selector nor import-free `direct_url.json` editable-source resolution. Without clear facts about the active interpreter's editable binding, an Agent could easily misplace a rebuild; likewise, worktree isolation guidance intended for shared multi-agent runs applies only when parallel isolation is actually needed.

| Situation | Source and runtime handling |
|---|---|
| **Continue editing the user's existing checkout** | Modify that checkout in place; preserve the user's active branch, uncommitted `git diff`, and current Python editable binding |
| **User explicitly switches to a new source directory** | Treat the new directory as the sole target without copying changes back; bind and verify it within authorized scope, and require explicit authorization before deleting old directories |
| **Bind new sources into an existing Python environment** | Verify dependency versions and ABI compatibility first, check whether running services share that interpreter, back up affected baseline artifacts, and update the binding intentionally |
| **Keep two versions runnable side by side** | Isolate both the source trees and mutable Python bindings; verify the full dependency graph in the new environment rather than assuming a fresh `venv` inherits private packages from an older `venv` |
| **Read-only fault diagnosis or PR review** | Inspect existing source files or Git objects directly without altering package bindings |
| **Task is already running inside an isolated Git Worktree** | Reuse the current Worktree directly without nesting a second isolation directory |
| **Parallel candidate exploration, independent PRs, or A/B version diffs** | Use task-scoped Git Worktrees paired with separate virtual environments or containers while leaving the shared interpreter's editable binding untouched |
| **Another task is actively mutating the checkout, or its revision conflicts** | Verify directory ownership, target revision, and authorized scope first; resolve the conflict or isolate into a separate environment rather than overwriting someone else's work |

Proceed directly whenever existing authorization and observed facts uniquely determine the path. Ask for clarification on the affected step only when directory ownership or shared-environment impact remains genuinely ambiguous.

Switching to a new directory is a valid user goal, not an error; however, retiring an old directory never implicitly authorizes deleting it or killing processes running from it. Record the endpoint/container, chosen source path and Git revision, business Python interpreter (`sys.prefix` and ABI), launch environment, and build output paths in the existing task log—do not introduce a separate environment database.

## 2. Establish source and runtime identity

Shared MCP `root` / `cwd` parameter schemas and mutating tool descriptions state these boundaries directly so Agents see them even without loading a knowledge session or repository `AGENTS.md`. Calling `remote_probe(distributions=["vllm", "vllm-ascend"], python_executable="<absolute target Python path>")` reads package versions, installation roots, and `direct_url.json` editable source paths without importing heavy frameworks, initializing an NPU context, or creating directories. When `python_executable` is omitted, `remote_probe` resolves `python3` after applying the endpoint's `runtime_profile` and labels that isolated interpreter explicitly—never claiming it proves what a live serving process has loaded. Missing packages, non-editable installs, and corrupted metadata are reported as distinct states rather than guessing `/opt` or hardcoded workspace paths.

### Multiple interpreters

Supplying `required_distributions=["torch", "torch-npu"]` enables bounded business-interpreter discovery, optionally augmented by `python_candidates` for non-standard absolute paths. Within the target endpoint, container, and `runtime_profile`, discovery scans bound `MINDIE_PYTHON`, active `venv`/Conda environments, `PATH`, and standard container image locations—probing at most `16` candidates under one shared timeout budget and listing any unprobed paths explicitly. The control-plane Python used to launch the probe does not need `torch` and is never assumed to be the workload interpreter.

1. **No silent fallback on explicit selection**: When `python_executable` is specified explicitly, only that interpreter is checked; failures are reported directly without silently switching to another Python binary.
2. **Surface multi-candidate ambiguity honestly**: When no interpreter is specified, prefer an eligible active binding, or select the sole candidate satisfying `required_distributions`. If multiple candidates qualify without an active binding, return `ambiguous` along with each candidate's version, `sys.prefix`, ABI, dependencies, and editable paths so the Agent can choose from actual launch scripts and source requirements—**never pick an interpreter merely because it has the highest Python version number**.
3. **Preserve `sys.prefix` virtualenv identity**: Distinct virtualenvs often symlink `bin/python` to the same underlying system binary; deduplicate by `sys.prefix` rather than executable `realpath` alone.
4. **Separate package metadata from runtime readiness**: `dist-info` metadata confirms only that a distribution is installed—not that C++ extensions import cleanly, match dynamic library ABIs, or run on NPU. Perform native import and NPU checks at validation time under a proper device lease.
5. **Diagnose missing packages per candidate**: When zero candidates qualify, report which distributions each candidate lacks. Reuse a verified compatible environment first, or install matching dependencies into the intended isolated target environment—never `pip install` into an accidentally selected Python just to silence a probe error.

### Coordinator boundary

Attaching a managed `coordinator` task (`context_file`) is not required for SSH connectivity checks, host/NPU/container inventory, source or checkpoint discovery, or CPU-only tests. `hosts`, `probe`, `container`, and `lease` operate standalone with `context_file` omitted, while host lease queues still arbitrate physical NPU allocation. Without a managed task binding, proceed with environment discovery and authorized inspection, pausing only steps whose specific device, directory, or process ownership cannot yet be verified.

`coordinator`'s `mindie.run` snapshots local sources into a fresh remote execution directory and optionally provisions a task-scoped interpreter. Its `sources` field represents local snapshot inputs for **managed isolated runs**, not a remote checkout to edit in place. When developing inside an existing or user-chosen remote directory, pair `remote-dev` file/command tools with `coordinator` resource leases—never let a rebuild implicitly divert an in-place workflow into `mindie.run` snapshot materialization.

Container readiness probing shares the exact same interpreter discovery implementation as `remote-dev`, matching `torch` / `torch-npu` metadata (plus the corresponding diffusion package for `MindIE-SD`) instead of picking the highest Python version. When creating a task `venv` from a donor interpreter, the target `sys.prefix` and install scheme belong exclusively to the task. Because `--system-site-packages` does not inherit packages installed inside another private `venv`, missing target dependencies fail fast before native compilation with clear guidance to reuse a compatible runtime or install matching task packages—never mutating the donor environment or silently switching system Pythons.

Before modifying sources, verify four facts in the actual target host, container, business interpreter, and launch environment (recording them in normal task logs rather than inventing a separate receipt store):

- **Source tree**: Resolved `realpath` of the Git root, current `HEAD` and branch, and any pre-existing uncommitted `git diff`. Always prioritize user-specified paths; treat `/vllm-workspace` as an example rather than a universal container convention.
- **Python binding**: Exact `sys.executable`, `python -m pip show` and `direct_url.json` editable target for that interpreter, and `sys.path` resolution—checking module `__file__` under launch environment variables when needed without triggering NPU initialization.
- **Native binary artifacts**: Active C++/AscendC `.so` extensions, linked shared libraries, custom operator packages, and `ASCEND_CUSTOM_OPP_PATH` / `LD_LIBRARY_PATH` search order (`pip show` reflects static metadata, not which `.so` is mapped at runtime).
- **Live processes**: Running serving instances or concurrent builds using those paths. Coordinate any mutation to a shared environment and never terminate another user's or task's live service.

Source roots, build directories, `dist-info` records, and resolved runtime files can diverge; diagnose any mismatch cleanly before rebinding rather than masking conflicts with ad-hoc `PYTHONPATH` overrides or global symlinks.

### Escape routes for unsuitable tools

Whenever a helper has a bug, misses a non-standard container layout, lacks support for the checked-out build system, or prepares an environment contrary to user intent, the Agent may write and run task-specific discovery, patch, build, verification, or rollback scripts—or use existing CLIs and authorized native SSH directly—under existing session authorization, without activating extra Skills, installing plugins, creating new workspaces, or productizing a one-off script first.

- **Localize failure scope**: An automatic interpreter-discovery failure means only that automatic selection could not decide for you. Because the response returns observed candidates, unprobed paths, and endpoint parameters, the Agent can immediately pass an explicit `python_executable` or run a custom script—discovery never gates ordinary shell execution.
- **Pair honest failure status with `next` continuation routes**: Keep failed or blocked calls marked `failed` / `blocked` while surfacing actionable `next` options—never silently installing packages, moving checkouts, resubmitting jobs, or feigning success. `coordinator` preserves `execution` / `job` handles and lease-release facts, exposing bound `target`, launch environment, and interpreter details whenever an attachment exists.
- **Keep custom scripts auditable and non-destructive**: Run task-local scripts against the chosen endpoint, checkout, and business interpreter with normal command, `stdout`/`stderr`, exit-code, and rollback logging—without copying multi-GB model weights, maintaining shadow ledgers, or touching unrelated processes and files. Verified facts from a task script supersede stale automatic assumptions.
- **Switching tools never erases external state**: NPU execution still requires a valid device lease or confirmed reservation. Whenever a prior job may still be running, leases remain held, or an external write is `unknown`, inspect and reconcile first rather than resubmitting through a second tool or overwriting active binaries; pause only dependent actions while independent analysis continues.
- **Solve the task first; extract shared tools later from evidence**: A one-off script only needs to finish the current task cleanly. Promote repeatable, sharply bounded mechanics into shared tools later based on real usage—never bend the user's goal to fit a helper's limitations.

Concrete escape entrypoints: use `remote_bash` for direct remote commands or uploaded scripts; pass a local `script_file` to `mindie.run` for managed isolated runs (retaining snapshot materialization semantics); or fall back to authorized native host shell/SSH and saved `~/.mindie/ssh` credentials if `remote-dev` itself is unreachable. Secondary local bookkeeping errors never flip a confirmed remote success into an error.

## 3. Select the necessary build scope

| Scope of change | Build and activation strategy |
|---|---|
| **Python-only edits (with valid current editable binding)** | Reuse existing native `.so` binaries, test the affected modules, and restart task-owned processes still holding old Python bytecode/modules in memory |
| **C++, AscendC, headers, CMake, operator registration, or ABI edits** | Back up affected baseline binaries first, then run the checked-out revision's supported incremental build; escalate to a clean full rebuild only when dependency or build-graph changes require it |
| **Python interpreter, `torch`, CANN, compiler flags, or target SoC changes** | Re-verify build-cache compatibility from scratch; never treat binaries compiled for another ABI or SoC (e.g., `910B` vs. `910_93`) as a valid baseline |

Derive build commands from the target checkout's own build scripts and documentation rather than assuming every revision supports `build_ext --inplace`, identical environment flags, or fixed `pip` options. When supported, place intermediate build directories under task scratch space while reading sources from the user's checkout, verifying that `CMakeCache.txt` points to that exact source root.

When an editable install is required, invoke `<python_executable> -m pip` explicitly against the user's chosen checkout using the revision's supported flags (`--no-build-isolation`, etc.) rather than calling a bare `pip` on `PATH` that may belong to another Python environment. Rebind to a new directory only when the user explicitly chose one—never clone a fresh copy under `/opt` just to rebuild. Route long C++/AscendC builds through `remote-dev` background jobs and `coordinator` compile-slot budgets.

## 4. Preserve a recoverable baseline before overwriting it

Before running the first command that can overwrite existing binaries or bindings, back up the **minimal complete set of affected files**: `.so` extensions and companion shared libraries, custom operator OPP packages and generated registration tables, `dist-info`/`direct_url.json` binding files, and launch environment settings. Staging intermediate objects separately does not guarantee that `pip install -e` leaves the checkout tree or `site-packages` untouched.

Store backups in the task artifact directory or an existing high-capacity data mount, recording original absolute paths, whether a target path did not previously exist, SHA-256 checksums, symlink targets, and the source commit / build environment. **Backups must copy actual baseline bytes**—a symlink pointing at the very `.so` file about to be overwritten preserves nothing. Stream large binaries after checking free disk space, and never copy model weights, entire virtual environments, or unrelated directories.

Lock and preserve the **last verified baseline prior to the first edit** across iterative experiments so later broken builds never overwrite the clean starting point (retaining extra snapshots only when requested). Ordinary task logs are sufficient; do not invent a separate artifact registry, signing ceremony, or rigid JSON audit receipt.

Keep source diffs/commits, build caches, and baseline binaries distinct: `git checkout` cannot recover untracked `.so` artifacts, and building a fresh wheel does not prove byte-for-byte equivalence to a prior editable setup. If the starting environment was already broken before edits began, label saved files honestly as *pre-change artifacts* rather than a *verified working baseline*.

## 5. Validate, activate and restore

1. **Verify fresh-process loading**: After building, spawn a new process under the exact business interpreter and launch environment to confirm resolved Python `__file__` paths and loaded native/OPP shared libraries (checking `/proc/<pid>/maps` when needed). Replacing `.so` files on disk never updates libraries already mapped into a running process.
2. **Run minimal runtime & numerical checks**: Verify affected module imports, operator registration, and single-operator numerical parity (acquiring NPU leases per standard rules whenever device execution is needed). A `0` compiler exit code never substitutes for runtime loading and accuracy checks.
3. **Report concrete provenance and rollback steps**: State the checkout path, modified files, verified loaded library paths, baseline backup path, executed test scope, and exact rollback procedure—claiming a change is *active* only after runtime checks pass.
4. **Roll back cleanly on failure**: If build or validation fails (or the user requests rollback), stop task-owned candidate processes first and restore the matching source state, baseline binaries, editable bindings, and launch environment while preserving unrelated user edits. Remove only newly created files identified for this build—**never run wildcard `rm -rf` cleanups across shared directories**.
5. **Re-verify after restoration**: Restart a fresh process after restoring baseline files and re-run the same import/loading checks, reporting build, install, candidate validation, and rollback outcomes separately—copying old `.so` files back on disk does not by itself prove service recovery.

### Recovering unintended directory drift

If an environment has already drifted to an unintended directory (such as `/opt/...`), first confirm which checkout the user wants to keep as the authoritative workspace. Inspect both checkouts' `HEAD` revisions, uncommitted `git diff`s, `direct_url.json` bindings, and live process mappings; consolidate intended edits into a clean reviewable patch alongside pre-existing user changes; and build and verify in the chosen directory (never moving changes back if the user chose to keep the new directory). Delete a retired directory only with explicit user authorization after confirming zero live jobs, unique patches, or unbacked binaries depend on it.

When no pre-overwrite binary backup exists, never promise instant one-step binary rollback—either locate surviving artifacts in base images/mounts or rebuild from matching source and toolchain settings and validate on hardware, rather than merely editing `.pth` / `direct_url.json` back to the old path and declaring victory.

## 6. Ownership and acceptance scope

- **Main repository (`mindie-agent`)** owns this cross-repository contract; **`remote-dev`'s shared MCP catalog** embeds path, binding, and pre-overwrite backup rules directly into tool and parameter descriptions while providing import-free interpreter/source discovery. All seven host plugins inherit identical tool definitions via `list_tools()`, independent of the user's local working directory or manual Skill activation.
- **`remote-dev`** owns remote file access, command and background job execution, and shared interpreter metadata discovery; **`coordinator`** owns NPU/port leases, managed snapshot materialization, and task environment preparation while reusing `remote-dev`'s interpreter discovery. Source-directory and build-scope choices belong to the Agent's task reasoning—generic shell tools never use brittle regexes to second-guess `pip` or `git` commands.
- **Domain knowledge corpora (`knowledge-*`)** scope every rule to explicit applicability conditions; multi-user cluster worktree conventions never become mandatory ceremony for single-task in-place development.

Behavioral acceptance must verify real on-disk files, package metadata, and fresh-process library loading across the scenarios below (this table defines behavioral acceptance criteria rather than claiming all cases were executed by a documentation-only change):

| Scenario | Required observable outcome |
|---|---|
| **Remote task launched from any local directory or directoryless chat** | Identical endpoint and business interpreter queries return identical source/binding facts; MCP tool boundaries remain visible without a local `AGENTS.md` |
| **Dirty original checkout with a Python-only patch** | Edits stay in the original checkout, pre-existing `git diff` survives, editable binding does not drift, and zero native compilation runs |
| **User explicitly switches to a new source directory** | Edits, builds, and runs target the new directory under the intended shared or isolated Python without moving edits back or auto-deleting the old checkout |
| **Multiple Pythons present, only one has workload packages** | Selects the interpreter with `torch`/`torch-npu` while keeping the control-plane probe Python separate |
| **Multiple eligible interpreters, or an explicit interpreter missing packages** | Returns `ambiguous` candidate metadata or an explicit missing-package error—never picking the highest Python version or silently substituting another binary |
| **Donor packages live inside a private `venv`** | Detects missing packages in a newly created task `venv` before native compilation begins, without faking inheritance or mutating the donor |
| **Automatic discovery fails and the Agent switches to a task script** | Original discovery failure and observed candidate/endpoint facts stay visible; the task script completes cleanly and ordinary shell calls remain unblocked |
| **Switching execution paths under `unknown` writes or active leases** | Preserves original job handles, `unknown` status, and lease ownership—reconciling first rather than blindly resubmitting |
| **Successful native C++/AscendC operator rebuild** | Checkout stays in place, pre-overwrite binary backup exists on disk, and a fresh process loads the new `.so` and passes minimal numerical checks |
| **Failed native build or failed validation** | Baseline backup survives intact; matched source, binaries, and bindings are restored and verified in a fresh process (or restoration errors are reported explicitly) |
| **Explicit parallel Git Worktrees** | Candidate source tree and Python runtime stay isolated while the shared interpreter's editable binding remains untouched |
| **Metadata, `PYTHONPATH`, or stale running-process shadowing** | Fresh-process module/library inspection catches the mismatch; neither `pip show` nor a `0` build exit code alone passes acceptance |

# Source Development, Native Rebuilds and Artifact Recovery

[中文](source-rebuild-contract.md) · [Back to Documentation Center](README.en.md)

For source development in vLLM, vLLM-Ascend or another framework, honor the user's selected checkout and runtime. Without an explicit choice, retain the existing checkout and compatible environment. Users may start from any local directory, without a project directory, or within framework sources; the policy cannot depend on entering the MindIE Agent repository or reading its AGENTS.md. Source location, build output, Python environment and backups are separate choices. A rebuild does not imply relocating sources or creating a virtualenv.

## Unified implementation sequence

Use existing task records and execution paths rather than adding a workspace manager, environment registry or parallel state machine.

| Stage | Owner and implementation | Completion condition |
|---|---|---|
| Establish the goal | Agent chooses endpoint/container, source, interpreter and isolation from user intent; shared tool descriptions expose these choices | Source, Python and cleanup choices stay separate; existing sufficient authorization is reused |
| Obtain needed facts | Shared remote-dev metadata discovery with explicit interpreter or bounded candidates | Preserve prefixes, ABI, dependencies, source paths and partial observations; metadata is not execution evidence |
| Select execution mode | Direct remote editing/shell plus leases for selected directories; coordinator run for managed materialization | Compilation does not implicitly change mode; preparation and execution retain interpreter identity |
| Build and recover | Revision-appropriate build, affected baseline retention, actual loading and correctness checks | Reuse compatible artifacts for Python-only edits; report candidate and restoration outcomes separately |
| Continue around unsuitable helpers | Agent uses existing CLIs, native tools/SSH or task-local scripts; next exposes retained context | Helpers are optional; retain original jobs and reconcile uncertain writes |
| Accept and deliver | Affected local behavior tests, nondestructive remote checks, real-task Canary; dependencies publish before consumers | Complete each repository's R1–R6 gates before release; unexecuted native/NPU acceptance stays pending |

Tools own bounded mechanical operations and honest observations. The agent chooses the next task action. Discovery, standard builds, caches and automatic preparation remain replaceable conveniences; equivalent authorized commands and scripts can supply necessary facts without repairing every MindIE helper first.

## 1. Directory selection and observed problem

A user report showed an original source directory at `/vllm-workspace/vllm-ascend`, followed by `pip show` reporting an editable location under a newly created `/opt/vllm-ascend-...`. This establishes installation drift. The screenshot alone cannot identify the triggering instruction, changes in the original checkout, libraries loaded by running processes, or available baseline binaries.

Inspection found no automatic clone-to-/opt or editable installation operation in remote-dev. The confirmed gap is that root defaults to / as a file-operation boundary, while the former probe inspected that boundary's Git state and offered neither a business-interpreter selector nor import-free editable-source discovery. This does not identify the historical call that created the extra directory, but leaves the agent without useful source facts. Isolation guidance in workspaces or knowledge also applies only under its stated conditions.

| Situation | Source and runtime choice |
|---|---|
| Continue changes in existing user sources | Edit that checkout; preserve its branch, existing changes and interpreter binding |
| Explicitly use a new source directory from now on | Use that directory and validate its installation; do not move changes back. Cleanup of old sources requires its own authorized scope |
| New sources with an existing interpreter | Verify dependencies and ABI, update the intended binding within task authorization and preserve affected baseline files; account for shared users |
| Keep two versions available concurrently | Isolate mutable source and installation bindings, and verify dependencies in the new environment |
| Read-only diagnosis or PR inspection | Read existing sources or Git objects without changing the installation |
| Task already uses an isolated worktree | Reuse that worktree without creating another isolation layer |
| Explicit parallel candidates, independent PRs or version comparisons | Use task worktrees and separate virtual environments or containers; retain the shared interpreter's binding |
| Another task writes the directory, or its version differs from the target | Establish ownership, target revision and authorized scope; resolve the conflict or use an independent environment |

Continue directly when existing authorization and observed facts determine the path. Clarify only the affected action when a real directory or shared-runtime choice remains ambiguous.

Using a new directory is a supported goal. No longer using the old directory does not itself authorize deleting it or stopping other tasks. Retain endpoint/container, selected source and revision, business interpreter and prefix/ABI, launch environment and build output in existing task records; do not add another environment state store.

## 2. Establish source and runtime identity

Actual MCP root/cwd field descriptions and mutation-tool descriptions must expose these boundaries without a knowledge session or project instructions. Use remote_probe with distributions such as vllm and vllm-ascend and an absolute python_executable from the target environment to read versions, installation roots and direct_url.json source paths without importing frameworks or creating sources. Without a selector, python3 is resolved after the endpoint runtime profile. The result identifies its isolated interpreter and does not claim actual business-process module loading. Missing packages, absent editable metadata and malformed metadata remain distinguishable; no /opt or fixed workspace is inferred.

### Multiple interpreters

Set required_distributions, for example torch and torch-npu, to discover business interpreters; python_candidates adds nonstandard absolute paths. Within the same endpoint/container and runtime profile, inspect active MINDIE_PYTHON, virtualenv/Conda bindings, PATH and conventional image paths, with at most 16 candidates sharing a total deadline. Report unprobed candidates. The control Python launching the probe does not need Torch and is not automatically the business interpreter.

An explicit interpreter never falls back. Otherwise, prefer an eligible active binding, or select the sole eligible environment. Several eligible environments without a binding return ambiguous with versions, prefixes, ABI and dependency/source metadata for the agent to resolve from actual launch configuration and source requirements. Never choose the highest Python version. Preserve different virtualenv prefixes even when their executable symlinks resolve to the same underlying file.

Distribution metadata establishes package presence, not importability, ABI compatibility or NPU readiness. Check the selected source's version/ABI requirements and perform native import/device validation at the appropriate later stage under leases. If no environment qualifies, report missing dependencies by candidate; reuse a prepared environment or provision matching dependencies in the intended isolated environment rather than installing into an accidentally selected Python.

### Coordinator boundary

Managed mindie.run captures local sources and materializes a separate remote execution root, potentially preparing a task interpreter. Sources are local inputs, not remote directories for in-place edits. Develop in an explicitly selected existing or new remote directory using remote-dev and coordinator resource leases; rebuilding alone should not change the workflow into managed materialization.

Container readiness uses the shared interpreter inventory to find Torch/Torch-NPU metadata, plus the corresponding framework for MindIE-SD. Task virtualenv creation uses the selected donor as its creator while retaining a separate task prefix and installation scheme. System-site-packages does not inherit packages privately installed in another virtualenv. Missing target dependencies therefore fail before native compilation, with guidance to reuse a compatible prepared runtime or install matching task dependencies, without modifying the donor or silently choosing another system Python.

Use the actual host, container, interpreter and launch environment. Reuse existing task logs rather than adding another state store or mandatory receipt format.

- Resolve the Git root's realpath, HEAD, branch and pre-existing changes. Prefer the user's path; `/vllm-workspace` is an example rather than a universal image layout.
- Identify `sys.executable`, that interpreter's `python -m pip show` / editable `direct_url.json`, and module resolution paths. Check `__file__` in the normal launch environment when necessary, without initializing an NPU merely to discover paths.
- Identify the native extension, dependent libraries, custom operator package and relevant OPP / dynamic-library paths. Distribution metadata alone does not prove which Python or native files load.
- Check for services or other builds using the paths. Coordinate shared replacements without stopping another task's processes.

Source roots, build directories, installation metadata and resolved runtime files can differ. Resolve actual discrepancies before changing bindings; extra `PYTHONPATH` entries or global symlinks should not conceal them.

### Escape routes for unsuitable tools

When a helper is broken, misses a nonstandard environment, does not support the checked-out build, or prepares an environment that differs from user intent, the agent may write and execute task-specific inspection, patch, build, validation or recovery scripts. Existing CLIs and authorized native SSH are also available. Reuse session authorization; no additional Skill activation, plugin installation, workspace creation or productization of a temporary script is required.

- Keep failure scope local. Failed interpreter discovery does not become a prerequisite for all shell operations. Return candidate observations, unprobed paths and endpoint parameters so explicit selection or a custom script can continue.
- Preserve failures and continuation context together. Keep failed/blocked results honest; next exposes choices without automatically installing, relocating or resubmitting. Coordinator retains execution/job references and resource-release facts, with target/launch/interpreter inspection when a binding exists.
- Keep custom execution explainable through ordinary commands, output, exit codes and necessary recovery information at the selected endpoint/source/interpreter. Avoid weight copies, shadow ledgers and cleanup of other tasks. New script observations may replace invalid automatic assumptions.
- Changing tools does not alter external facts. Device work retains a real lease or verified reservation. Observe potentially live jobs, unreleased resources and uncertain external writes before replacement; pause only the dependent action while independent work continues.
- A one-off script only needs to complete its task. Repeated, well-bounded operations may later become shared tools based on evidence. Do not change the user's goal to fit a standard helper.

Use remote_bash for custom remote commands or uploaded scripts. Managed isolated execution accepts a local script_file through mindie.run and retains its materialization semantics. If remote-dev itself is unavailable, use authorized native shell/SSH and known authentication references. Auxiliary recording failures cannot erase confirmed primary results.

## 3. Select the necessary build scope

| Change | Action |
|---|---|
| Python only, with a correct binding | Reuse native artifacts, test the affected scope and restart task-owned processes holding old modules |
| C++, AscendC, headers, CMake, operator registration or ABI | Preserve affected baseline files, then use the checked-out revision's supported incremental build; expand only when dependencies require it |
| Interpreter, Torch, CANN, compiler options or target SoC | Reassess cache compatibility; artifacts for another ABI or SoC are not a verified baseline |

Read build commands from the selected checkout. Do not assume every revision supports `build_ext --inplace`, identical environment variables or the same pip flags. Separate build outputs are useful when supported, while sources remain in the user-selected directory. CMake's cached absolute source paths must agree with that checkout.

If editable installation is necessary, use the selected business interpreter and user-selected source with the version-supported procedure and intended dependency scope. An explicit new-directory choice allows binding the new sources; without it, rebuilding does not justify a fresh clone under /opt. Build, install, test and launch consistently through the selected interpreter rather than an unrelated bare pip. Reuse managed jobs, budgets and compile slots for long builds.

## 4. Preserve a recoverable baseline before overwriting it

Before the first overwrite, save the smallest complete set the build and installation can replace: extensions and associated libraries, custom operator packages and generated registration files, necessary installation metadata and launch configuration. Build staging does not guarantee that editable installation leaves the source tree or site-packages untouched.

Use task results storage or an existing data mount. Record original paths, files absent before the change, checksums, symlink targets and the associated versions / build conditions. Preserve actual baseline bytes; a symlink to an artifact about to be overwritten is not a backup. Stream large files, check capacity and avoid copying weights or entire environments.

Retain the last verified baseline from before this change through subsequent trials. Keep additional versions only when needed. Normal task records suffice; no new artifact registry, signatures or fixed audit receipts are required.

Preserve source patches / commits separately from binaries and caches. Git cannot restore untracked `.so` files, and building a new wheel does not establish equivalence to the previous editable artifacts. If the starting environment was already broken, label its files as pre-change artifacts rather than a verified working baseline.

## 5. Validate, activate and restore

1. Start a new process with the actual interpreter and launch environment. Check Python resolution and native / operator library origins, using process mappings when necessary. Replacing files does not update libraries already loaded in a running process.
2. Run the affected import, registration or single-operator correctness check. Device checks use existing NPU lease rules. Compilation success does not establish runtime correctness.
3. Report source location, changed files, loaded artifact locations, backup location, verification scope and recovery steps. Claim activation only after the relevant checks pass.
4. On candidate failure or a requested rollback, stop task-owned candidate processes and restore a matching set of source changes, artifacts, installation bindings and environment. Preserve unrelated user edits. Remove only identified files introduced by this operation, without wildcard cleanup of shared directories.
5. Restart and repeat the same checks. Report build, installation, candidate validation and recovery separately. Copying baseline files successfully is not proof of service recovery.

### Recovering unintended directory drift

Establish which directory the user intends to keep using. Read both checkouts' HEADs and dirty diffs, installation metadata and launch paths. Preserve intended changes as a reviewable patch alongside existing user edits, then build and verify in the selected checkout. Do not move changes back when the user chose the new directory. Cleanup requires authorized scope and confirmation that no active jobs, unique patches or artifacts depend on the directory.

Without an earlier backup, do not promise one-step binary recovery. Locate actual retained artifacts / images or rebuild under matching conditions and validate the result. Changing the editable path alone does not complete recovery.

## 6. Ownership and acceptance scope

- The product repository owns this contract. The actual shared remote-dev MCP catalog carries source, binding and pre-overwrite backup guidance and exposes metadata discovery. Host plugins consume shared list_tools(), independently of the user's local directory or manual Skill loading.
- remote-dev owns general file operations, commands, jobs and shared interpreter metadata discovery. Coordinator owns resource leases, managed materialization and its environment preparation, reusing that discovery implementation. The agent chooses source and build strategy from task context; generic shell tools do not infer pip or Git intent through regular expressions.
- Knowledge units retain their applicability and evidence boundaries. Shared-cluster procedures do not automatically mandate worktrees for single-task development.

Behavioral acceptance must inspect actual files, installation and loading. The following are requirements for subsequent acceptance, not claims of executed tests:

| Scenario | Observable outcome |
|---|---|
| Remote task started in any local directory or without a project | The same endpoint and business interpreter yield the same source facts; tool descriptions remain available without a local AGENTS.md |
| Dirty original checkout, Python-only patch | Original checkout receives edits, user changes survive, bindings remain stable and native compilation does not run |
| User explicitly selects new sources | Edit, build and run from the new directory with the intended shared or isolated interpreter; do not move back or delete old sources automatically |
| Only one interpreter has required dependencies | Select that environment while keeping control and business Python distinct |
| Multiple eligible interpreters, or an explicit interpreter missing packages | Return ambiguity or explicit failure without version-based selection or silent replacement |
| Donor dependencies exist only in its private virtualenv | Detect missing task dependencies before native compilation without modifying the donor |
| Discovery fails and the agent uses a task script | Keep the failure and endpoint/candidate facts visible; the independent script actually completes its task and shell execution remains usable |
| Execution mode changes after uncertain effects or before release | Retain the original observation route, uncertainty and lease facts without blind resubmission |
| Successful native rebuild | Sources remain in place, a pre-overwrite backup exists, and a fresh process loads and validates the candidate |
| Failed build or validation | The baseline survives; matched files and environment are restored and checked, or recovery failure is reported |
| Explicit parallel worktrees | Candidate source and runtime are isolated; the shared interpreter's editable binding is preserved |
| Metadata, PYTHONPATH or old-process shadowing | Actual resolution / loading exposes the mismatch; neither `pip show` nor build exit zero alone passes acceptance |

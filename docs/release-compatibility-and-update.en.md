# Release Compatibility & Silent Update

[中文](release-compatibility-and-update.md) · [Back to Documentation Index](README.en.md)

Status: Current product contract (2026-10-16); the first ordinary internal Release `0.0.1` is published. For actual implementation details, paired component release mappings, and six-environment verification evidence, see the [`0.0.1` Release Record](releases/0.0.1.en.md).

---

## Paired Component and Plugin Releases

MindIE Agent publishes verified combinations of components. Each software repository maintains its own independent version history—product release `0.0.1` does not require `remote-dev`, `knowledge`, or `diagnostics` to also be numbered `0.0.1`, and existing component versions must never be rolled back or renumbered merely for visual uniformity. Unchanged components reuse their already published Releases without artificial version bumps. Third-party dependencies remain pinned by complete dependency locks (`uv.lock`).

Publish in topological dependency order: first `diagnostics`, then `remote-dev` and `knowledge` (which depend on `diagnostics`), and finally the Harness plugins (`mindie-agent-codex`, `mindie-agent-cc`) and the unified product entry (`mindie-agent`). Independent components may be prepared, verified, and published in parallel. Components may iterate independently, but published plugins adopt changes only through a new paired release—a published plugin never bypasses its dependency lock to chase a component's `main` branch or unconditional `latest` tag.

Before publishing a plugin Release, the release operator must record the checklist below in the product release record:

| Pre-Release Check | Required Evidence & Handling of Gaps |
| --- | --- |
| **Complete Dependency Inventory** | Read all direct and transitive first-party software components from each plugin's final dependency lock; list repository, package name, package version, full commit SHA, and corresponding Release tag. |
| **Formal Component Releases** | Every first-party runtime dependency must have a published, non-draft, non-prerelease GitHub Release; a Git tag, candidate branch, merged PR, or green CI alone is insufficient. |
| **Exact Identity Alignment** | Dereferencing the annotated tag must resolve to the exact commit locked by the plugin; the tag version, source package version, and wheel/sdist metadata must match without reusing the same version string for different code. |
| **Downloadable & Verified Artifacts** | Download the built artifacts and checksums from the official Release, verifying SHA256 digests, package metadata, and correspondence to the locked source commit. |
| **Scoped Acceptance Evidence** | Record the exact installed native identities, component/package checks, and any subsequent source deltas separately; tests not re-run on a new tag are not claimed as fresh hardware evidence, and any failures or `unknown` outcomes remain visible. |
| **Closed-Loop Combination** | Publish plugins only after all component Releases are complete; verify the mapping between plugin locks and component Releases, read back tags, Release flags, uploaded assets, and the unified release record. |

`knowledge` is a software runtime component and requires a formal software Release. `knowledge-vllm-ascend` is a domain content repository distributed continuously via its fixed content contract (`publication-contract.json`), Git commits, and block hashes; adding content packages does not require a new software Release unless the content schema or validator contract changes.

---

## Release Declarations and Deterministic Selection

Every formal plugin Release declares its product version, official repository origin, exact source commit, and supported Harness name and SemVer range. The currently installed Harness version determines the candidate set, and standard SemVer resolution selects the highest compatible ordinary Release—never downgrading automatically and never treating a draft, prerelease, or development `main` branch as an ordinary Release. When the Harness itself is an `alpha` build, it must be explicitly permitted by the declared range.

Compatibility ranges are established from verified interface contracts and test evidence rather than interpolated from endpoints alone. Every plugin repository maintains a machine-readable `harness-compatibility.json` and centralized interface inventory recording:

| Field | Purpose |
| --- | --- |
| **Interface ID, Harness, and Support Range** | Uniformly declares Hooks, MCP wiring, CLI flags, environment variables, and native output contracts |
| **Production Call Sites** | Locates exact source files invoking the interface |
| **Official Documentation or Pinned Host Source** | Distinguishes documented public contracts, audited host source revisions, and unverified assumptions |
| **Tests & Native Evidence** | Covers return values, failure semantics, platform differences, and edge cases |
| **Release Active Interface Set** | Ensures the declared release support range lies within the intersection of all required interface ranges |

The host's native plugin manager owns package downloading, installation, caching, and install records. Where the native catalog format cannot express Harness version-range filtering directly, the shared selector computes the single compatible candidate and projects it to the native installer. First-time installation also pins an immutable Release tag and checks the installed Harness version against the declared range.

---

## Online Checks and Silent Update Semantics

More than 24 hours after the last successful check, the next natural use asynchronously executes the compatibility check and update preparation:

- **Zero User Interruption**: Performs no interactive prompt, requires no confirmation, sends no update notification, and requires no manual reload.
- **Persistent Consent**: Retains the contribution choice, project scope, explicit disablement, and independent fault-reporting preference configured at install time.
- **Lightweight Hot Path**: Routine invocations perform only an in-process timestamp check (reading at most a small local check receipt once per process) without blocking on network calls, release scanning, or full environment hashing. Short Stop Hooks never perform network checks or installations.
- **Backoff & Idempotency**: A "successful check" means reading and validating the official release metadata and completing compatibility selection (even when no newer version exists). Failed checks apply backoff without updating the last-success timestamp; already prepared candidates wait for a safe idle cutover window without re-downloading.

---

## Preparation, Cutover, and Recovery

Silent updates follow a staged prepare-drain-switch-verify lifecycle reusing the existing installation lock, native installer, immutable runtime layout, and exact service ownership:

1. **Background Preparation**: Download the pinned release, sync the complete `uv` lock (`--locked --no-editable`), and verify package and interface contracts outside the active installation binding.
2. **Wait for Idle**: While any RPC, admitted capture, or indexing job is active, keep serving requests on the existing installation and defer switching.
3. **Atomic Short Cutover**: Acquire the exclusive operation lock, confirm the old service owner is idle, retire the old owner cleanly, verify the new service is ready, and atomically update the single canonical installation binding (switching interpreter, scripts, and engine configuration as one unit).
4. **Resilient Entrypoints**: During the brief cutover window, new requests either wait briefly or receive an explicit `temporarily unavailable, not yet executed` response. Already loaded native entrypoints resolve the updated canonical binding on subsequent calls without requiring a session reload. Durable Stop events enqueue into the existing SQLite admission queue without waiting on the cutover lock.
5. **Honest Failure Preservation**: Any failure prior to binding publication leaves the previous version active; if cutover is interrupted, recovery reconciles actual native install records and active bindings without guessing success or replaying uncertain (`unknown`) operations.

# MindIE Agent Engineering Design Principles & Guidelines

[中文](design-principles.md) · [Back to Documentation Center](README.en.md)

MindIE Agent is built with a single goal: **make general-purpose AI coding agents genuinely effective, effortless, and unobtrusive for Ascend NPU and LLM inference engineering.**

Starting from nine foundational product and boundary principles, our engineering guidelines have evolved through real-world Ascend troubleshooting, cross-platform support (macOS, native Windows, Windows WSL), and multi-host integration (Claude Code, OpenAI Codex CLI, Kimi Code) into a comprehensive set of product and operational rules.

---

## Part 1: Nine Core Product & Tool Boundary Principles

These nine principles define what should be a tool, what should be a Skill or knowledge package, and how to minimize friction for both humans and Agents:

1. **Measure efficiency by the total cost of achieving the user's real goal (Top Priority)**
   - Total cost includes **understanding, configuration, waiting, debugging, and rework**—not just raw execution time.
   - Reliability mechanisms are worthwhile only when they reduce these real costs. Never burden every everyday task with heavy ceremony just to guard against rare edge cases. When other considerations conflict with this rule, Principle 1 wins.
2. **Turn only well-bounded, closed problems into tools**
   - A tool must have clear preconditions, inputs, outputs, and failure modes (e.g., reading a remote file, querying live NPU telemetry, or redacting secrets).
   - Leave open-ended, context-dependent judgment to the Agent; extract only repeatable, deterministic operations into stable tools, and never expand scope just for the sake of building a tool.
3. **Never increase cognitive load for the Agent or the user**
   - Tools should absorb internal state complexity and expose intuitive, task-oriented interfaces.
   - A CLI with dozens of obscure flags, hidden state transitions, or errors that require reading internal source code to diagnose is a classic anti-pattern.
4. **Give every tool a single, well-defined boundary**
   - Each tool should solve one cohesive problem. It can execute the necessary multi-step mechanics internally so the Agent does not have to micromanage every step, while avoiding monolithic "kitchen-sink" tools that mix unrelated responsibilities.
5. **Skills provide a map, not a straitjacket**
   - Skills exist to show applicable scenarios, capability entrypoints, practical examples, and optional troubleshooting approaches.
   - Concrete troubleshooting lessons belong in the Knowledge base rather than rigid step-by-step mandates inside a Skill. Essential usage should be immediately visible at the entrypoint so the Agent never has to search repeatedly just to assemble one command.
6. **Knowledge is advisory reference material, never mandatory dogma**
   - Knowledge packages store applicability conditions, evidence, and caveats in plain Markdown. A search hit or merged PR never makes an entry infallible—decisions must always be grounded in the live behavior of the current system.
   - The Agent consults or records experience on demand, with **no mandatory lookups, mandatory writes, rigid fill-in-the-blank templates, or end-of-task closing rituals**.
7. **Every tool and Skill intervenes strictly on demand**
   - Whether reviewing a PR, inspecting a remote directory, or bringing up a new model on Ascend NPUs, developers work naturally inside their native Agent session.
   - Lightweight tasks use native tools directly; heavy tasks compose capabilities as needed. Merely opening a workspace never triggers heavy background pipelines.
8. **Reuse proven host, OS, and ecosystem mechanisms first**
   - Whenever task semantics and compatibility requirements are met, reuse mechanisms already provided by the host CLI, operating system, `uv`, and mature libraries, as well as existing build artifacts and verified results.
   - Identify concrete gaps before writing custom code, keep custom glue minimal, and delete replaced legacy managers or duplicate state stores once a native mechanism is adopted.
9. **Keep tools observable and diagnosable; never hide errors**
   - Surfacing honest, actionable errors is a hard product requirement. When a required step fails, report it clearly—**never disguise a read failure as "empty data," a corrupted database as "first-time use," or a local save as "published."**
   - Clearly distinguish **completed**, **failed**, and **uncertain (`unknown`)** outcomes. If a primary operation succeeds but cleanup or bookkeeping fails, report both separately so the caller is never tricked into repeating a completed action.

---

## Part 2: Evolved Engineering & Operational Guidelines

As MindIE Agent matured across hosts and operating systems, we codified five operational guidelines extending Principles 8 and 9:

### 10. Build Only for Proven Gaps and Remove Legacy Baggage
- **Verify with lightweight probes first**: Before refactoring updaters, hooks, or process management, verify host and OS behavior (timeouts, cancellation, abrupt termination) using minimal model-free probes.
- **No dual-track state**: Once a replacement mechanism is verified, delete the superseded custom updater, duplicate state tables, and obsolete configs while preserving existing user Markdown packages, cursors, and consent settings.
- **Data-format-driven compatibility**: Before formal release, rewrite intermediate implementations cleanly without carrying multi-generation shims. After formal release, design compatibility around actual schema and contract changes rather than guessing from version strings.

### 11. Decouple User Consent from Code Installation Identity
- **Configure once, persist across updates**: A user's contribution preference, public target repository, and authorized project scope are persistent user settings decoupled from the installed code revision.
- **No re-prompting or silent overrides**: Restarting sessions, reinstalling, or silently updating a plugin preserves existing consent and explicit disablement without re-prompting or silently turning disabled settings back on.

### 12. Paired Component and Plugin Releases
- **Release dependencies before plugins**: Every first-party runtime dependency pinned by a plugin (`diagnostics`, `remote-dev`, `knowledge`) must first have a published, non-draft, non-prerelease GitHub Release whose tag resolves to the exact locked commit and whose uploaded wheel/sdist artifacts match `uv.lock`.
- **Independent component versioning**: Each repository maintains its own version sequence and reuses unchanged Releases without artificial version bumps. See the [Paired Component and Plugin Release Checklist](release-compatibility-and-update.en.md#paired-component-and-plugin-releases).

### 13. Silent Background Updates with Atomic Idle Cutover
- **Compatibility-first selection**: Each plugin Release declares its verified Harness version range in `harness-compatibility.json` and automatically selects the highest compatible formal Release rather than chasing an unverified `main` branch.
- **Zero hot-path blocking**: More than 24 hours after the last successful check, natural usage triggers an asynchronous background check and runtime build; everyday tool calls perform only a fast local timestamp check.
- **Atomic cutover when idle**: After downloading and building the locked `uv` environment outside the active runtime, the updater waits until no active RPC, capture, or indexing job is running, acquires the exclusive lock, retires the old worker, and atomically switches the active installation binding without user prompts or manual session reloads. See [Release Compatibility & Silent Update](release-compatibility-and-update.en.md).

### 14. Fail-Visible Semantics and `unknown` Side-Effect Protection
- **No silent degradation**: Never catch an exception and silently return empty results, skip corrupted state, or serve stale cache if doing so alters the meaning of the caller's request.
- **Protect uncertain (`unknown`) external writes**: If a paid model call or external Git/PR write times out or loses its receipt, record it as `unknown` and reconcile read-only against the remote target before any future write—never blindly retry it as if it had not run.
- **Protocol safety never hides business faults**: A Hook may exit cleanly so the host model does not loop, but any underlying capture or service failure must still be surfaced through the host's warning field or the next tool call's diagnostic status.

---

## Part 3: Pre-PR Design Principles Checklist

Every development PR across all MindIE Agent repositories (covering code, configuration, dependencies, CI, and documentation) must review its final diff against these principles before submission:

| Dimension | Review Question |
|---|---|
| **1. Total Cost** | What real friction or cost does this change remove? Does it add unnecessary background work, redundant computation, or extra user steps? |
| **2. Tool Boundary** | Is any toolified logic solving a closed, well-bounded problem rather than freezing open-ended judgment into a rigid flow? |
| **3. Cognitive Load** | Does the change keep internal state and parameters simple for both users and Agents? |
| **4. Single Responsibility** | Are module boundaries clean without cross-repo leakage, duplicate state stores, or competing orchestrators? |
| **5. Informational Skills** | Do Skills remain clear, helpful guides rather than mandatory procedural checklists? |
| **6. Advisory Knowledge** | Do knowledge entries and feedback remain advisory without mandatory lookups, writes, or truth certification? |
| **7. On-Demand Activation** | Does everything trigger strictly on demand without unrequested background work or closing rituals? |
| **8. Reuse & Paired State** | Were host/OS/mature tools reused first? Were replaced implementations deleted while preserving user data, consent, and `unknown` receipts? |
| **9. Visible Errors** | Do all failure paths report honest, actionable errors without silent fallbacks, fake success, or overwritten primary errors? |

Include a concise `## 设计原则 Review` (Design Principles Review) summary in every development PR description documenting the reviewed commit, conclusions, fixes applied, and verification performed.

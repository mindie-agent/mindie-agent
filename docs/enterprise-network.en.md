# Configuration and transport on enterprise networks

[中文](enterprise-network.md) · [Documentation](README.en.md)

## Routes and owners

| Route | Owner | Network configuration |
| --- | --- | --- |
| Plugin registration, source, and knowledge Feed fetches | Native plugin managers and Git | Caller proxy, Git configuration, and system certificates |
| Python, component wheels, and PyPI packages | `uv` invoked by native host plugin installers and updaters | Caller proxy, system trust store, explicit CA, and package indexes |
| Gitleaks and DSH Release downloads | Python standard-library HTTPS | System trust store, explicit CA, and caller proxy |
| Knowledge PRs and diagnostic Issues | Git and `gh` | Existing user consent, `gh` login state, and service launch environment |
| `knowledge` loopback RPC, Kimi plugin API, and DSH summary API | Shared knowledge client and Python adapters | Direct loopback connection |
| Bench model egress and local RPC | `mindie-bench` gateway and shims | Proxy and `NO_PROXY` for model egress; direct loopback RPC |
| SSH uploads, downloads, and artifact synchronization | `remote-dev` | SSH configuration and target host/container; HTTP proxies do not participate in SSH |
| Resource coordination and NPU observation | `coordinator` and `npu-top` | Remote SSH and local APIs; remote Docker owns image-pull networking |

## Design

Following [Engineering Design Principles](design-principles.en.md) 1, 8, 9, 10, 14, and 15, installation, background updates, and outbound transport on enterprise networks obey six rules:

1. **Reuse the operating-system trust store during installation and updates.** Native launch commands enable `uv` system certificates before downloading Python, while internal installers set environment defaults compatible with older `uv` releases without overriding explicit caller choices for `UV_SYSTEM_CERTS`, `UV_NATIVE_TLS`, custom CAs (`SSL_CERT_FILE`, `SSL_CERT_DIR`), or package indexes. Kimi uses `uv` for both first-time installation and background updates rather than maintaining a second `ensurepip`-based installer. Google Antigravity and Tencent WorkBuddy reuse their existing `plugins/mindie-agent/scripts/setup.py` entrypoints: before bootstrapping the runtime, `setup.py` calls `paths.apply_enterprise_transport_env` in the same directory to populate default `UV_SYSTEM_CERTS`, `UV_NATIVE_TLS`, and `GCM_INTERACTIVE=never` values, and incrementally appends missing Windows Git `core.longpaths` / `core.autocrlf` and GitHub credential entries onto `GIT_CONFIG_COUNT` without clobbering caller-supplied entries or introducing a parallel transport path.
2. **Propagate network settings into the background knowledge service.** Proxy, CA, package-index, and `gh` configuration-directory variables are declared in the shared `knowledge` service launch context, reusing the existing one-shot context handoff. Individual host plugins do not maintain separate network state machines: the persisted installation binding records only variable names, while the process waking the service supplies current values.
3. **Reuse the diagnostic service's private environment-file mechanism.** Enabling the diagnostic service writes required proxy, CA, and `gh` configuration paths into its private service directory—never copying API tokens—while giving precedence to any explicitly configured environment file. Updating network settings refreshes the running service configuration in place without altering user consent or publication receipts. Kimi's scheduled updater reuses the same shared environment-file implementation, with explicit caller-supplied variables taking precedence.
4. **Bypass enterprise proxies on loopback traffic.** `knowledge` local RPC, Kimi plugin registration, DSH summaries, and `mindie-bench` SSH, knowledge, and replay RPC calls explicitly construct `ProxyHandler({})` so loopback calls succeed even when the user has not configured `NO_PROXY`.
5. **Preserve state honesty on external writes.** Uncertain (`unknown`) Git pushes, PRs, Issues, and paid model requests are never replayed automatically. TLS validation errors are surfaced verbatim, and certificate trust derives strictly from the OS trust store or an explicit user-configured CA—never by trusting an unverified peer certificate returned on the wire.
6. **Route Bench model egress through enterprise HTTP proxies.** The parent gateway reads `HTTPS_PROXY` / `ALL_PROXY` and `NO_PROXY`, establishing standard-library HTTP `CONNECT` tunnels with system TLS verification. Proxy credentials authenticate only to the proxy and are never forwarded to model providers or written to logs. Local HTTP relays remain direct, preserving streaming behavior, token metering, timeout budgets, and zero silent retries. Enterprise HTTP proxies (`http://`) are supported; unsupported proxy schemes fail fast before submitting any model request rather than silently falling back to a direct connection.

Runtime changes live strictly in the respective shared component and host plugin repositories; this repository owns the architectural contract and entry documentation. Background updates retain their existing offline staging, idle atomic cutover, and timeout budgets.

## Enterprise-network maintenance releases

[`knowledge 0.13.4`](https://github.com/mindie-agent/knowledge/releases/tag/v0.13.4) extends the installer's `uv` system-certificate defaults to standalone component update builders while preserving explicit TLS, CA, and proxy overrides. [`Codex 0.1.3`](https://github.com/mindie-agent/mindie-agent-codex/releases/tag/v0.1.3) and [`Claude Code 0.1.3`](https://github.com/mindie-agent/mindie-agent-cc/releases/tag/v0.1.3) keep system- and user-scoped Git settings intact during candidate publication-contract checks so enterprise proxies, custom CA bundles, and Windows `schannel` trust remain active.

On a live Windows enterprise network, a production `0.1.2` MCP server running under Codex `0.164.0-alpha.11.1` completed its normal background upgrade to `0.1.3` with `knowledge 0.13.4 / remote-dev 0.10.6 / diagnostics 0.5.2`. End-to-end execution from update check to cutover took roughly `44.9s` (dominated by isolated runtime staging, with the atomic binding switch taking ~`55ms`), while the active MCP server continued serving foreground tool-discovery calls uninterrupted. That measurement reflects full single-host update acceptance—including environment staging—and is not presented as a sub-second end-to-end upgrade claim.

[`Codex 0.1.4`](https://github.com/mindie-agent/mindie-agent-codex/releases/tag/v0.1.4) also updates hook-trust inheritance for Desktop `0.164`, where command and content hashes are stored as separate fields: the updater migrates existing user approvals only, preserving explicit opt-outs and requiring re-approval whenever either hash changes. The released updater completed a full `0.1.3 → 0.1.4` upgrade on the same Windows enterprise network and cleanly inherited all five native hook approvals.

## Normal installation and workspace onboarding

The main repository install prompt, native plugin auto-install protocols, and first-time setup entrypoints execute the same deterministic sequence: verify and reuse GitHub authentication, install and validate the plugin, inspect current consent in Step 5 via `setup.py sharing --status`, and immediately invoke the host's **native interactive question tool** (Antigravity `ask_question`, Claude Code / WorkBuddy / Kimi `AskUserQuestion`, Codex `request_user_input`, or DSH's native question tool / structured choice card) to ask three onboarding questions in one turn:
1. Whether to initialize `vllm-ascend-workspace`, reuse an existing checkout, or stay in the current working directory;
2. Whether to enable community knowledge sharing and automated fault reporting (persisted via `setup.py sharing --enable --project-root "$WORKSPACE_ROOT"` or `setup.py sharing --disable` across `mindie-community.json`, `mindie-consent.json`, and `diagnostics.json`);
3. Whether to star `mindie-agent/mindie-agent` on GitHub ⭐ (executing `gh api --hostname github.com --silent -X PUT /user/starred/mindie-agent/mindie-agent` strictly when the user explicitly opts in, never silently).

Manual installation instructions conclude with `/mindie-agent help me finish first-time setup`; background wakeups and routine engineering sessions never repeat onboarding prompts.

- **Workspace initialization and auth reuse**: Initializing [vllm-ascend-workspace](https://github.com/mindie-agent/vllm-ascend-workspace) runs its checked-out `AGENTS.md` workflow and `repo_init.py`, preserving saved fork selections in `workspace.json`. Standalone workspace setup verifies GitHub authentication upfront, while workspace onboarding launched from plugin setup reuses the already verified identity.
- **Single-step native workspace registration**: Once the user chooses to create or reuse a workspace directory, onboarding registers that absolute path in the host's native project/workspace list within the same flow without asking a redundant confirmation question. Directory registration is decoupled from source cloning, so users can register the workspace immediately and defer large repository downloads.
- **No shadow project database**: Registration uses the host's supported tools, APIs, or UI—reusing any existing entry for that path—and CLI hosts enter workspaces through their native working-directory flags. MindIE Agent never maintains a shadow project registry or mutates private host SQLite databases.
- **Verify registration from host readback**: Onboarding reports registration complete only after confirming the target path in the host's returned response or project list. Merely `mkdir`-ing a folder, `cd`-ing inside a child shell, or widening sandbox path permissions does not constitute native workspace registration; if the host UI requires one final user click, the Agent states that exact step clearly.
- **Independent permission scopes**: GitHub authentication, workspace registration, and community contribution consent remain strictly independent; setting up a workspace never widens contribution consent scope.

## GitHub connection failures

Reaching `github.com` in a desktop browser does not prove that terminal installers, `gh`, or scheduled background workers can reach `api.github.com`. Browsers frequently rely on independent proxy extensions, PAC scripts, split-tunnel VPNs, or private certificate stores. Always diagnose connectivity inside the exact network context of the failing process rather than inferring health from another machine or browser tab.

| Observed symptom | Diagnostic boundary and next action |
| --- | --- |
| DNS resolution fails | Check DNS resolution in the failing process and configured proxy; preserve the raw error |
| DNS resolves, but TCP `443` times out | Inspect effective outbound proxy variables, `NO_PROXY`, VPN routes, and firewall rules; GitHub has not responded yet, so do not ask the user to re-authenticate |
| Proxy returns `407` or rejects `CONNECT` | Check enterprise proxy credentials and domain allowlists; rotating a GitHub token cannot fix proxy authentication |
| TLS handshake or certificate verification fails | Verify the client's OS trust store or explicit CA bundle while keeping TLS verification enabled |
| GitHub returns `401` | Inspect the effective credential source, active account, and token validity |
| GitHub returns `403` / `404` | Check repository permissions, organization SAML SSO authorization, and rate-limit headers instead of looping through login prompts |

Read-only connectivity checks should verify all three production routes in order: the **GitHub REST API**, **Git read access to the target repository**, and **GitHub Release asset redirects**—a working webpage or PyPI download does not validate Release wheel fetches. When reporting proxy and CA diagnostics, log only whether settings are present, their scope, and the failing stage; never print proxy passwords, tokens, authorization headers, or full environment dumps. If a browser works via corporate PAC while CLI tools lack proxy settings, configure the CLI environment using the organization's official proxy endpoint rather than guessing proxy ports or altering global OS settings.

When assembling Git subprocess environments, preserve existing caller proxy, CA, and TLS entries in process-scoped `GIT_CONFIG_COUNT` before appending MindIE's credential helper and hooks entries. Background workers consume their one-shot launch context or private network environment file and project only Git HTTP transport options—never credential helpers, raw auth headers, or arbitrary Git config keys. When a caller removes proxy variables, consuming the refreshed context clears stale proxy and process-scoped Git transport overrides as well.

## GitHub sign-in flow

During installation, first-time onboarding, or credential repair, `/mindie-agent` executes the five-step flow below. The Agent guides method selection interactively, while official `gh` CLI storage owns credential persistence and invocation—introducing no custom auth daemon or MindIE-specific token file format:

1. **Reuse working authentication first.** Install `gh` if absent, then run `gh api --hostname github.com user --jq .login`. When the expected account responds cleanly, proceed immediately without prompting for login. Use `gh auth status` to inspect credential provenance; an expired secondary account stored in `gh` must never block an active valid account.
2. **Recommend a sign-in method suited to the network.** Recommend token sign-in when the user is on an enterprise network, proxy or custom CA variables are active, or browser OAuth callbacks are blocked; otherwise default to browser sign-in while offering token sign-in as an option. Proxy or CA settings are a heuristic hint rather than proof that browser login will fail. Always resolve TCP timeouts, proxy `407` errors, and TLS certificate failures as transport issues before treating them as invalid credentials.
3. **Prompt only for the missing step.** If the user already holds a valid token, proceed directly to step 4; otherwise open the pre-scoped [GitHub token creation page](https://github.com/settings/tokens/new?scopes=repo%2Cread%3Aorg%2Cgist&description=MindIE%20Agent) and guide them back to the terminal once generated. Standard persistent login uses a `gh`-compatible classic PAT (`repo`, `read:org`, `gist`) with expiration governed by user or organization policy, completing organization SAML SSO authorization when required. Where organization policy mandates fine-grained PATs, scope permissions to the target repositories rather than asking for a disallowed token type.
4. **Accept and store credentials through native hidden prompts.** In an interactive user terminal, run `gh auth login --hostname github.com --git-protocol https`, choose `Paste an authentication token`, and let the user paste into the masked prompt. If the user provides a private token file path, pipe it directly into `gh auth login --hostname github.com --git-protocol https --with-token` via standard input without prompting again. Never expose raw tokens in chat messages, CLI arguments, Git repositories, MindIE config files, or logs, and let `gh` store credentials in the OS keyring without `--insecure-storage`. Because stale `GH_TOKEN` / `GITHUB_TOKEN` environment variables override saved `gh` keyring credentials, credential repair must clear or update stale environment variables in the calling process as well.
5. **Verify read-only access and resume the task.** Re-query the authenticated account, ensure `git`'s directory is on `PATH` (or pinned via `MINDIE_GIT_BIN`), and leave global `~/.gitconfig` and system `etc/gitconfig` untouched by injecting `credential.helper=` (clearing multi-valued `manager` / `helper-selector` defaults from Windows `etc/gitconfig` to prevent GCM's 2-second auto-probe and GUI popups), `credential.https://github.com.helper=!gh auth git-credential`, `credential.interactive=never`, `core.autocrlf=false`, and `core.longpaths=true` via process-scoped `GIT_CONFIG_COUNT` (or `git -c`), alongside `GCM_INTERACTIVE=never` and `GIT_TERMINAL_PROMPT=0` (if Windows `schannel` behind an enterprise proxy raises `CRYPT_E_NO_REVOCATION_CHECK`, append `http.sslBackend=schannel` and `http.schannelCheckRevoke=false` via process-scoped `GIT_CONFIG_COUNT` while keeping `http.sslVerify=true`). Run read-only repository checks for the active task, then resume source/knowledge sync, `git push`, PR, and Issue operations under that same `gh` identity without altering contribution consent or workspace scope. Treat `401` as an authentication failure and diagnose `403` / `404` against repository permissions and SSO—never loop through repeated login prompts or create dummy PRs/Issues to test credentials.

When given a private token file path, bind the path variable and pipe standard input without echoing file contents:

```powershell
Get-Content -Raw -LiteralPath $TokenFile | gh auth login --hostname github.com --git-protocol https --with-token
if ($LASTEXITCODE -ne 0) { throw "GitHub token login failed" }
```

```sh
gh auth login --hostname github.com --git-protocol https --with-token < "$TOKEN_FILE"
```

**Cross-process and background reuse boundary:** Keyring-backed `gh` credentials are automatically shared across processes running under the same OS user and `GH_CONFIG_DIR`. To confirm durable persistence, verify account lookup inside a clean child environment stripped of `GH_TOKEN` / `GITHUB_TOKEN` so shell variables cannot mask an unsaved login. Background services inherit their configured network context and `GH_CONFIG_DIR`; users relying exclusively on environment-injected `GH_TOKEN` credentials (recommended for fine-grained PATs) supply each calling process through their own secret-injection setup. While `knowledge` passes credentials via its one-shot launch context, auto-generated `diagnostics` network files intentionally omit tokens—so standalone background workers require either an explicit private environment file or a persisted `gh` keyring login. Foreground CLI success alone must never be reported as proof that post-restart background authentication is ready.

## Enterprise-network observations

End-to-end verification conducted on October 20, 2026 on native Windows behind an authenticated corporate HTTP proxy established the following baselines:

- GitHub REST API calls, Git repository clones, GitHub Release asset redirects, and PyPI package fetches all succeeded.
- Cloning both code repositories and domain knowledge corpora succeeded with full Git TLS certificate verification enabled.
- Downloading the GitHub Release wheel for `mindie-diagnostics 0.4.3` under `uv`'s bundled root store failed with `invalid peer certificate: UnknownIssuer`, whereas enabling OS system certificates resolved the failure immediately.
- PyPI requests succeeded under default settings in the same environment, confirming that a PyPI-only connectivity check would miss corporate MITM CA failures on GitHub Release assets.
- With OS system trust enabled, `uv` downloaded Python `3.13.16` and component Release wheels cleanly and installed the full locked Codex runtime (166 packages).
- The test workstation originally carried a global `http.sslVerify=false` workaround; after verifying clean TLS validation through the corporate proxy, `http.sslVerify` was restored to `true` and re-verified against GitHub under default Git settings.
- Branch pushes (`git push`) and GitHub PR creation succeeded end to end across the live corporate proxy.
- Local HTTP/TLS integration suites verified authenticated `CONNECT` tunneling, explicit custom CA bundles, `NO_PROXY` bypass, streaming token metering, and `ProxyHandler({})` loopback immunity when pointed at an unreachable proxy.
- Because the corporate office network has no direct route to the lab's standing A2/A3 NPU clusters (an expected network boundary), office-network runs execute local Tier 0/1 component, subprocess, and transport contract suites rather than live A2/A3 hardware tests.

Overall verification spans live GitHub Release wheel downloads, cross-process private environment-file consumption, service launch-context handoff, loopback immunity under active proxies, and honest error propagation—keeping all proxy credentials and tokens out of test output, public logs, and PR descriptions.

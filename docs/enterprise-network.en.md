# Configuration and transport on enterprise networks

[中文](enterprise-network.md) · [Documentation](README.en.md)

## Routes and owners

| Route | Owner | Network configuration |
| --- | --- | --- |
| Plugin registration, source and knowledge Feed fetches | Native plugin managers and Git | Caller proxy, Git configuration and system certificates |
| Python, component wheels and PyPI packages | uv invoked by plugin installers and updaters | Caller proxy, system trust, explicit CA and package indexes |
| Gitleaks and DSH Release downloads | Python standard-library HTTPS | System trust, explicit CA and caller proxy |
| Knowledge PRs and diagnostic Issues | Git and gh | Existing consent, gh login and service launch environment |
| Knowledge RPC, Kimi plugin API and DSH summary API | Shared knowledge client and Python adapters | Direct loopback connection |
| Bench model egress and local RPC | mindie-bench gateway and shims | Proxy and `NO_PROXY` for model egress; direct local RPC |
| SSH uploads, downloads and artifact synchronization | remote-dev | SSH configuration and selected host/container |
| Resource coordination and NPU observation | coordinator and npu-top | SSH and local APIs; remote Docker owns image-download networking |

## Design

Following [design principles](design-principles.en.md) 1, 8, 9, 10, 14 and 15:

1. Enable system trust in native launch commands before uv downloads Python. Internal installers use the environment default supported by older uv versions and retain explicit `UV_SYSTEM_CERTS` and `UV_NATIVE_TLS` choices. Custom `SSL_CERT_FILE`, `SSL_CERT_DIR` and indexes remain effective. Kimi uses uv for both initial setup and updates instead of maintaining a separate ensurepip-dependent installer.
2. Declare proxy, CA, package-index and gh configuration variables in the shared knowledge service context. Reuse the existing one-use context transfer. Installation configuration stores names; the process waking the service supplies values.
3. Reuse the diagnostic service's environment-file mechanism. Automatically write selected proxy, CA and gh configuration paths into its private service directory, without copying API tokens. An explicitly configured file takes precedence. Refresh network settings while preserving consent and publication receipts. Kimi scheduled updates reuse this shared implementation, with explicit current caller values taking precedence.
4. Use `ProxyHandler({})` for knowledge's own RPC client, Kimi registration, DSH summaries, and Bench SSH, knowledge and replay RPC. Local operations must work without a caller-maintained `NO_PROXY`.
5. Preserve publication outcomes. Never replay uncertain Git pushes, PRs, Issues or model calls. Retain certificate errors and use system or explicitly configured trust; never trust a certificate merely because a peer returned it.
6. Route Bench model egress using the parent process's `HTTPS_PROXY` / `ALL_PROXY` and `NO_PROXY`. Reuse standard-library HTTP CONNECT and system TLS verification. Send proxy credentials only to the proxy, never to the provider or journal. Connect directly to local HTTP relays. Preserve streaming, metering, timeouts and no automatic retries. The current enterprise proxy uses `http://`; reject unsupported proxy protocols before model submission instead of silently connecting directly.

Runtime changes belong to their component and plugin repositories. This repository owns the design and entry documentation. Updates retain existing preparation, idle switching and timeout budgets.

## Enterprise-network maintenance releases

[`knowledge 0.13.4`](https://github.com/mindie-agent/knowledge/releases/tag/v0.13.4) applies the installer's uv system certificate defaults to independent component builds while preserving explicit TLS, CA, and proxy settings. [`Codex 0.1.3`](https://github.com/mindie-agent/mindie-agent-codex/releases/tag/v0.1.3) and [`Claude Code 0.1.3`](https://github.com/mindie-agent/mindie-agent-cc/releases/tag/v0.1.3) also preserve system and user Git configuration during candidate publication-contract validation, retaining enterprise proxies, CA paths, and Windows schannel trust.

On the Windows enterprise network, a formal `0.1.2` MCP process under Codex `0.164.0-alpha.11.1` completed its normal background upgrade to `0.1.3`, running `knowledge 0.13.4 / remote-dev 0.10.6 / diagnostics 0.5.2`. This run took approximately `44.9s` from update check to activation, including a binding switch of approximately `55ms`; the original MCP process continued to handle foreground tool discovery. This is software-update acceptance on one host, including runtime preparation, rather than a subsecond claim for the entire update.

[`Codex 0.1.4`](https://github.com/mindie-agent/mindie-agent-codex/releases/tag/v0.1.4) also fixes trust inheritance when Desktop `0.164` stores command and content hashes in separate fields. The updater transfers existing approvals only, preserving explicit disables and changes to either approved hash. The formal corrected updater completed the full `0.1.3 → 0.1.4` upgrade on the same Windows enterprise network and inherited all five existing native hook approvals.

## Normal installation and workspace onboarding

The main installation entry, all four plugin auto-install protocols, and first-use setup follow the same sequence: check and reuse GitHub authentication, install the plugin, present the existing user notice, offer creating `vllm-ascend-workspace`, reusing a directory, or keeping the current directory, and ask at the end of the installation summary whether the user would like to Star `mindie-agent/mindie-agent` ⭐ (running `gh api --hostname github.com --silent -X PUT /user/starred/mindie-agent/mindie-agent` only when the user explicitly says yes, never silently without consent). Manual installation ends with `/mindie-agent help me finish first-time setup`; background startup and ordinary development tasks do not repeat the questions.

- Initialize [vllm-ascend-workspace](https://github.com/mindie-agent/vllm-ascend-workspace) through its checked-out `AGENTS.md` and `repo_init.py`, preserving saved fork selections in `workspace.json`. Standalone workspace setup also checks authentication; setup entered from a plugin reuses the same verification.
- Approval to create or reuse a workspace includes adding the selected absolute path to the current harness's native project/workspace facility in the same flow. Do not ask separately for registration. Preserve the initialization choice; source downloads can be deferred while registering the directory.
- Plugin guidance uses native tools, APIs or UI and reuses an existing record for the same path. CLI clients use their supported working-directory launch mechanism. Do not create a separate MindIE project registry or edit private harness databases.
- Confirm the path in the native result or project list before reporting registration complete. Creating a directory, changing a child shell's directory, or adding filesystem access does not establish native registration. When the native entry needs user interaction, state the one remaining step.
- GitHub authentication, workspace registration and contribution consent retain their separate settings. Installing a workspace does not widen contribution scope.

## GitHub sign-in flow

During installation, first-use setup or authentication repair, `/mindie-agent` follows this flow. The Agent guides the choice; `gh` owns credential storage and use. No additional authentication service or MindIE token configuration is needed.

1. **Reuse working authentication.** Install `gh` if missing, then run `gh api --hostname github.com user --jq .login`. If the expected account succeeds, continue without another login question. Use `gh auth status` to diagnose the credential source; an unrelated expired saved account must not block the active valid account.
2. **Choose a method when login is needed.** Prefer a token when the user reports an enterprise network, proxy/custom CA settings are present, or browser authorization is blocked. Otherwise offer browser login by default, with a token option. Proxy/CA settings are hints, not proof that browser login is impossible. Resolve connection timeouts, proxy 407 responses and certificate failures as transport problems before diagnosing an invalid token.
3. **Ask only for what is missing.** Use an existing token, or open the [GitHub token creation page](https://github.com/settings/tokens/new?scopes=repo%2Cread%3Aorg%2Cgist&description=MindIE%20Agent) and guide the user back to the terminal after creation. The ordinary persistent flow uses a classic PAT supported by `gh` (`repo`, `read:org`, `gist`); expiry follows the user's or organization's policy. Complete organization SSO authorization when required. If policy requires a fine-grained PAT, configure its actual target repositories and permissions rather than demanding a forbidden token type.
4. **Receive and save through the native prompt.** In a user-operable terminal run `gh auth login --hostname github.com --git-protocol https`, select `Paste an authentication token`, and let the user paste into the hidden input. If the user already supplied a private token-file path, pipe it into `gh auth login --hostname github.com --git-protocol https --with-token` without another entry step. Keep the token out of chat, command arguments, repositories, MindIE settings and logs. Let `gh` manage storage without adding `--insecure-storage`. Stale token environment variables override saved login and must be addressed in the actual calling process during repair.
5. **Verify and resume the requested task.** Read the account again, ensure the resolved `git` directory is on `PATH` (or pinned via `MINDIE_GIT_BIN`), and on Windows clear any unscoped `helper-selector` from system `etc/gitconfig` (`git config --system --unset-all credential.helper` and `GCM_INTERACTIVE=never`, preventing GUI credential popups that ignore `GIT_TERMINAL_PROMPT=0`; if `schannel` behind an enterprise proxy reports `CRYPT_E_NO_REVOCATION_CHECK`, set `http.sslBackend=schannel` and `http.schannelCheckRevoke=false` while keeping `http.sslVerify=true`), then run `gh auth setup-git --hostname github.com` and perform read-only checks on the repositories needed by the task. Subsequent source/knowledge sync, Git push, PR and Issue operations reuse the same `gh` identity. Login does not change contribution consent or project scope. Treat 401 as a credential failure and investigate repository access, permissions and SSO for 403/404; do not loop through login or create test PRs/Issues.

For a user-supplied file, the Agent binds the path variable to the actual path without printing the contents:

```powershell
Get-Content -Raw -LiteralPath $TokenFile | gh auth login --hostname github.com --git-protocol https --with-token
if ($LASTEXITCODE -ne 0) { throw "GitHub token login failed" }
```

```sh
gh auth login --hostname github.com --git-protocol https --with-token < "$TOKEN_FILE"
```

**Reuse across processes:** Saved `gh` credentials are available to new processes using the same user and `GH_CONFIG_DIR`. Verify persistent login with an account lookup in a child process without `GH_TOKEN` / `GITHUB_TOKEN`, so environment credentials cannot hide a missing saved login. Background services retain their existing network/configuration-path transfer. If the user chooses environment-only `GH_TOKEN` authentication (preferred for fine-grained PATs), their existing credential injection must supply each actual caller. Knowledge already transfers credentials through its one-use context. Generated diagnostic network files do not save tokens; independent services need their existing explicit private environment-file mechanism or saved `gh` login. Foreground success alone does not prove authentication after a service restart.

## Enterprise-network observations

On October 20, 2026, using an authenticated HTTP proxy on Windows:

- GitHub API, source clones, Release asset redirects and PyPI were reachable.
- Git clones of the code repositories and both knowledge domains succeeded with certificate verification enabled.
- The GitHub Release wheel for `mindie-diagnostics 0.4.3` failed under uv's default trust with `invalid peer certificate: UnknownIssuer`. The same request succeeded with system certificates.
- PyPI succeeded in the same environment, so a PyPI-only probe would miss the installation failure.
- With system trust, Python 3.13.16 and a component Release wheel downloaded successfully, followed by a complete Codex locked runtime installation (166 packages).
- This machine had `http.sslVerify=false`. After confirming that verification works with its existing enterprise proxy, the setting was restored to `true`; GitHub access with the default Git configuration passed.
- Git pushes and GitHub PR creation for the fixes succeeded, exercising actual upload paths.
- Real local HTTP/TLS tests covered authenticated CONNECT, explicit CA trust, `NO_PROXY`, streaming usage and loopback requests with a broken proxy.
- This local enterprise network cannot directly reach A2/A3, an expected environment boundary. This environment does not run A2/A3 live tests; regular CI verifies local components and process/network protocol contracts.

Verification covers real Release downloads, environment-file consumption across processes, existing service context transfer, proxied loopback requests and error propagation. Network credentials stay out of test output, public logs and PR descriptions.

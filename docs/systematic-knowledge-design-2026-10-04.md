# Codex knowledge delivery and consumption

Status: design frozen before implementation on 2026-10-04; implementation prepared for development review on 2026-10-05. The evidence below does not establish native deployment.

## Scope and decisions

This change addresses three reviewed P1 problems together: mismatched producer/publisher/consumer releases, reference echoes in retrieval, and expensive reading of long tasks. The user explicitly requested a complete design before implementation, direct changes without backwards compatibility, and a user notice instead of any additional authorization operation.

The reviewed starting points are knowledge `929bdcb918f2207aea38b02a14bd8e6219fabac4`, Codex `4f7df1355b59618d3a94ee4c97843a6f0b67fd19`, and content `55ac4704d77a7423a06d8cda8d8403b42ac5af4a`. Existing dirty and in-progress checkouts remain untouched. The complete material pipeline, required incremental indexing, returned-model-output ledger and unknown-write reconciliation remain the baseline.

The source of truth stays ordinary, mechanically redacted Markdown blocks. SQLite owns runtime metadata and receipts; ReMe owns rebuildable retrieval data. There is no new service, provider, model call, trust score, per-task workflow or approval. Failed, wrong and incomplete experience remains admissible reference material.

## 1. One declared product combination

The immutable adapter commit identifies the product combination. Its small `product-contract.json` declares the supported publication contract and candidate-validation protocol. `runtime-requirements.txt` remains the single source of exact runtime commit pins. Validation binds both files and checks the installed distribution commits; independent contradictory pin files are not permitted. The architecture repository does not become a dependency manager.

The content repository has a `publication-contract.json` declaring the domain, exact package/task/block/entry/feedback schemas, pinned trusted validator, and content-review contract/check. Feed intake, publication preparation and trusted CI read this declaration from the precise Git commit they operate on. A missing, unreadable or mismatched contract is an explicit failure before cache promotion, native installation or an external write. It must not be interpreted as an empty corpus or an unconfigured first run.

The adapter records a verified content baseline and the contract digest. Subsequent content commits under that same contract continue to synchronize without a plugin release. A contract change requires a matching product combination. The runtime validates format semantics even for an explicitly configured alternate repository; it never executes code selected by untrusted content.

The candidate owns runtime validation. The running updater checks candidate source identity, a small declaration/receipt envelope, bounded process execution and receipt identity. It executes the candidate's validator with the candidate's interpreter; it does not import its own version's knowledge-private classes to judge another version. Setup and updater share this path. Nonzero exit, timeout, non-JSON output or a mismatched identity is a failure. A preparation receipt binds the complete declaration, not merely the existence of a directory.

There is no old-updater bridge, old content reader, schema migration or compatibility alias. No old private database, unresolved send or unrelated user configuration is deleted by this change. Replacing interfaces does not permit losing uncertain external-write receipts.

GitHub repositories cannot switch atomically. The release order is: publish reviewed runtime commits; publish and verify the matching content contract and layout; update the repository/Bot operating contract; then publish the adapter combination. Intermediates fail visibly and preserve an existing valid local state. Code review, remote CI, native installation, external Bot configuration/event delivery and a fresh consumer are separate evidence. This work does not merge or deploy merely because local tests pass.

## 2. Exact block reading and current task navigation

The public reading interface is `knowledge_explain(ref)`.

| Reference | Meaning |
| --- | --- |
| `mindie://DOMAIN/TASK` | Current task navigation, current revision, block count and first block reference; not an assembled transcript. |
| `mindie://DOMAIN/TASK/blocks/BLOCK@FILE_SHA256` | Exactly one immutable material block currently belonging to that task, plus current navigation and adjacent block references. |
| `mindie://DOMAIN/TASK@REVISION` | An observation reference for feedback only. It is not accepted by the new reading interface. |

Task IDs, block IDs and file digests are full, unambiguous identities. Query returns a directly readable block reference plus a separate `feedback_ref` for the observed task revision. Explain also returns an observed feedback reference. Feedback must not silently attach an old observation to a newly appended revision.

Reading checks current membership before opening the target block. It validates the bytes against the current descriptor and reads no unrelated block body. Appending a task or changing its navigation does not invalidate an unchanged block reference. The response distinguishes the fixed block body from current, fallible navigation. Traversal uses previous/next block references; the old whole-document offset/limit API is removed.

A block removed/replaced in a valid current package is unavailable; a withdrawn task is withdrawn. Both outcomes may point to current navigation when it exists, but must never substitute new bytes for the requested body. A file missing from a manifest that still requires it, unsafe paths, I/O errors or wrong bytes are corruption/operational failures, not normal expiry. Old unreferenced files do not make a removed block readable. Only current packages are retained; no historical-body archive is introduced.

## 3. Citation-aware retrieval without judging truth

Each block's literal canonical MindIE references produce derived `cites` relationships. They mean only that the visible material contains a citation. Relationships are extracted from source bodies, not model-generated titles, summaries or navigation. They do not certify authorship, success, novelty or technical correctness, and never change capture/publication eligibility.

Search retains direct body-match evidence separately from fallible index metadata. A resolvable single-source chain can group matching results when the source body independently matches the query and covers the citing block's matched query terms. A shared generic term must not swallow an observation containing a query term absent from its source. Source counts or citation counts never boost a score or become independent-validation counts.

A group presents its source anchor and the most relevant citing block's own excerpt and readable reference. It must not replace a correction with just the old source or a `related_count`. Independent counterexamples and failed reuse remain discoverable. Query limit counts groups; additional related matches have stateless continuation bound to the query and current corpus fingerprint. Changes invalidate a continuation explicitly. No durable query-results service is added.

Multiple sources, cycles, missing/withdrawn sources and cross-domain relationships remain ordinary matches with citation information; no common origin is guessed. Exact task/block lookup preserves the explicitly requested object. Operational failures while resolving a present source propagate; they cannot masquerade as absent references.

Existing public text can cite historical task revisions. Such text is retained as source material, not rewritten into a false current citation or accepted as an old reading API. Any current-source navigation is identified separately from an unavailable cited revision. Tests must cover existing-style citation data as well as newly issued block references; a passing all-new fixture is not evidence that existing reference echoes disappeared.

## 4. Publication and maintenance share the same package rules

A package is its canonical manifest and exactly the blocks it references. The producer, trusted validator and feed consumer use the same validator and schemas. Ordinary content PRs can change only task packages and feedback; contract, workflow, executable and Bot-policy changes require the development-review path. Trusted CI chooses executable validator code from its trusted base, never from a proposed content change, and binds results to the exact publication head.

Block bytes are immutable under their identities. Metadata changes update the manifest. Editing a body requires a new block identity, a recomputed manifest and removal of the old current reference. Withdrawal removes the package. A withdrawn source does not remove an independent task that cites it.

Continuation uses confirmed remote material and only unsent local additions. Maintainer changes must not be overwritten, and withdrawn material must not be resurrected. Conflicts and unknown external outcomes remain explicit; no model-driven merge or blind retry is introduced. Bot instructions describe the same mechanical package operations and review boundaries rather than a separate data format.

## 5. User notice

The Codex README and Skill link a short user notice describing what complete visible material contains, local deterministic redaction, the limits of rule-based confidentiality detection, model-provider processing for indexes, public Git/PR history, advisory knowledge and disabling contribution. This is documentation only: no new consent field, authorization version, confirmation prompt or per-publication approval.

## 6. Verification before submission

Use deterministic synthetic material and isolated local Git repositories; no private transcript upload, real model invocation or NPU execution is needed to verify these changes.

- Candidate-owned validation succeeds without using the running updater's private runtime probe. Incorrect component SHA, contract digest, receipt identity, nonzero exit and partial installation fail at the correct stage.
- The same package passes producer, exact-head publication validation, feed intake and query/read. Old/mismatched layout and prohibited ordinary-PR changes fail before external writes or promotion.
- A middle-block hit reads only that block; appended navigation preserves its reference; replacement, withdrawal, missing files and corrupt bytes remain distinguishable. Feedback remains bound to the observed revision.
- Original work and several paraphrases form one query group; the original and the strongest correction each have directly readable references. A novel query term still returns its new observation. Multi-source, cyclic, historical, withdrawn and cross-domain citations do not fabricate evidence or loop.
- Continuation paginates all related matches, and detects a changed corpus without returning another result under the old token.
- Existing received-output and uncertain-write tests continue to protect prior effects; required failures remain visible.
- Recheck all nine current design principles against the final diff. Record exact commits, validation, findings/fixes and any unverified native/external boundary before creating development PRs.

P2 readiness projection, long-term resource cleanup, broad retrieval benchmarking and remote-artifact timeouts remain separate work.

## Implementation evidence

The reviewed implementation is split by repository ownership:

| Component | Exact commit | Responsibility |
| --- | --- | --- |
| Knowledge runtime | `f5d9b4374ebe8323c465da0b916d8408ee5f0f2f` | Publication declaration validation, block reads, observed feedback, citation grouping, safe continuation. |
| Public content | `f855cb0dd7b9098ad94e00c0daa239c35ba317d3` | Contract and trusted-base CI; existing task and feedback bytes remain unchanged. |
| Codex adapter | `9b4203dfefeca44fa538432edde5a1b746ae3913` | Candidate-owned validation, exact runtime/content pins, shared configuration projection, tool contract and user notice. |

The content declaration digest is `959cdd2ff79886b21755e3806fa4484209a77d7e66295899e5bb59baf526d742`. The adapter also pins remote-dev `3c1a3543322a6d3a954715642a679336b0c5f830`. These identities are review evidence; runtime requirements and the product declaration remain the operational authority.

Local validation in an isolated Python 3.13 environment:

- Knowledge: **706 passed, 9 skipped**; packaged documentation scan examined 12 files with zero findings.
- Codex: **329 tests run: 317 passed, 12 skipped**, using the installed exact runtime and contract-first CI entry with native encoding. Real preflight and diff checks passed.
- The installed exact knowledge runtime validates the exact content head against its base: 20 task entries, one feedback file, 246051 bytes, and four correctly classified development paths.
- YAML and all three embedded workflow scripts parse. The trusted-contract and validation scripts also ran against an isolated local Git source. A real Codex preflight fetched the public content commit and verified its declaration digest and installed runtime commits.
- A public-corpus exercise covered 20 tasks and 22 blocks. The query `Qwen3-0.6B NPU` returned 13 groups from 20 block matches; a more specific `Qwen3-0.6B token 1.201` query returned 10 groups from 17 matches. Source anchors retained the citing blocks' own excerpts and continuation reached the remaining related match. Exact lookup remained exact, and returned block bodies matched their public bytes. This checks navigation behavior, not the truth of any NPU or performance claim.

The full local suites preceded a final test-only CI correction: the existing 10 MiB capture test waited eight seconds while the production scanner alone permits 30 seconds. Its wait is now bounded at 60 seconds, with unchanged complete-text, cursor and export assertions; the failing case passed locally afterward. Windows also exposed newline conversion in byte-bound contract fixtures; their writes now preserve exact UTF-8 bytes. The runtime correctly rejected the mismatched fixture, and its strict hash rules remain unchanged. The repaired fixtures passed 28 focused checks and 9 checks with simulated Windows CRLF. Production runtime code is unchanged. The resulting revision and declaration pins above were revalidated by real preflight. Remote CI remains separately observable on the PR heads.

Independent review covered all nine current design principles, including the task-supplied expanded error requirements (document blob `9b21e6ae87ac96ff8bdacc3f4f546384e111a184`, SHA256 `15b4b58385846051464c27d06922ad0353bdd6a4031b619ff248c3a65c179741`). Review found and fixed:

- candidate failure reasons lost by a subprocess wrapper, and an installation error hidden by a later rollback failure;
- whole-body work in a continuation no-op;
- delayed send receipts accidentally adopting a newer feed base;
- a capture arriving after package freeze being incorrectly marked as already batched;
- documentation that confused confirmed PR staging cleanup with retirement after matching published-feed intake.

A changed confirmed main is combined only with provably unsent local blocks. An independently edited open PR remains an explicit `needs_review` conflict with zero overwrite; this implementation does not claim automatic resolution of that case.

The first content-contract installation is a development bootstrap: the old trusted base lacks the new declaration. Its old CI can validate existing packages but cannot prove execution of the new trusted-base workflow. Normal content automation applies after the declaration and Bot rules are adopted.

No private transcript upload, real model/NPU execution, native host installation or Hook-trust acceptance was performed for these revisions. External Bot configuration/event delivery, staged merge order and native end-to-end acceptance remain separate. Existing historical acceptance is not reused as proof of this new combination.

# Next steps

Updated 2026-09-25. Follow the [nine design principles](design-principles.md),
[architecture](architecture.md) and [lifecycle contract](harness-boundary-and-lifecycle.md).
[Implementation status](implementation-status.md) separates completed evidence
from work in progress. Earlier release reports retain their historical results.

The authorized implementation now focuses on three existing mechanisms:

1. Keep submitted knowledge authoritative on the remote. Retain only unsent
   additions locally, apply them to the current own PR or merged main, and never
   resurrect a Bot-redacted passage or withdrawn entry from an old full draft.
   Distinguish locally staged material from confirmed remote delivery.
2. Recover transient publication, feed and plugin-update failures through existing
   background workers and schedules. Persist backoff and reconcile unknown writes
   before retrying. Do not require a CLI, another business turn, or another model
   call. Content rejection remains separate from a recoverable network failure.
   Stable adapter management commands must select the installed generation.
3. Let long tasks and growing knowledge continue. Remove cumulative-body and
   whole-corpus rejection thresholds while bounding individual operations and
   using incremental processing. Do not introduce user-managed batches,
   compulsory draft administration or a new scheduling service.

Use real macOS environments to verify disconnection/recovery, continued work after
remote redaction, long records and contribution-off behavior. Component tests are
supporting evidence, not native acceptance. Codex uses gpt-5.6-luna/max, Kimi uses
K3/max, and Claude Code uses the user's configured DSV4 stack. Preserve original
failures and do not manufacture public experience or Bot events to claim a pass.

Codex [PR11](https://github.com/mindie-agent/mindie-agent-codex/pull/11) was still
open at `2fd63469` when checked on 2026-09-25; its native Stop acceptance and
temporarily held production updater must be resolved explicitly before declaring
release completion. A historical trusted Hook does not prove a changed Hook is trusted.

Windows remains part of the first-release target; the user will perform dedicated
Windows hardware acceptance after merge. Old business Skills, profiling analysis,
automatic Skill extraction and additional domains/Harnesses remain deferred.

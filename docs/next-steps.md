# Next steps

The current work and evidence are maintained in [Unified implementation status](implementation-status.md).
The authorized 2026-09-22 development and acceptance scope is in
[Release readiness](release-readiness-2026-09-22.md): reporter version handoff,
truthful schedule removal, retirement of the legacy CLI bot, ordinary-user
installation guidance, native reporting controls and a new Kimi business contribution.
The ongoing [2026-09-23 acceptance](release-acceptance-2026-09-23.md) separates
completed native control checks from the remaining Kimi contribution-loop evidence.
Follow the [nine design principles](design-principles.md) and [current architecture](architecture.md).

The shared readiness changes are merged: diagnostics 0.4.0 at `7c56f6b5`,
knowledge 0.8.2 at `e822fba4`, and remote-dev 0.9.5 at `28213bf3`.
All corresponding CI jobs passed; this does not substitute for native acceptance.
The five legacy files are removed, and the complete remaining diagnostics suite
passes (246 passed, 3 platform skips, no excluded test files).

All three adapters now pin the same reviewed shared commits, including the
organizer, updater and installation-document changes: Codex `6146d862`,
Kimi `d258d144`, and Claude Code `c909363f`. Their CI passed.

The remaining order is:

1. Install and read back the resulting official generations on macOS. Reuse
   completed baseline/path and OS-control evidence; check the final distribution
   and changed integration paths without rerunning unrelated business experiments.
2. Use Kimi K3/max for actual operator development on the user's authorized NPU
   environment, with community contribution enabled, and observe natural Stop,
   faithful content, automatic PR and actual use by a fresh session. Keep the old
   incomplete case closed and reuse its actual observations as background. Do not
   recreate its capture or rerun completed remote commands to manufacture a pass.
   Normal iterative development, debugging, recompilation and retesting are allowed.
   The requested half-day check is a progress review, not a termination deadline.

The previous 600-second limit was a local acceptance-controller choice, not a
product or Kimi requirement. It counted setup and operator approval delays inside
the business allowance, then killed the host while an approval was pending.
The next task uses the host's supported automatic-approval mode for the user's
authorized work. Distinguish setup/approval/business/
publication timing, and let the business turn finish naturally. Retain bounded
individual operations, cancellation and no automatic replay; do not replace the
600-second rule with another arbitrary universal task limit. A caller's failure to
handle approval is not evidence of a Hook, remote command or model failure.

The lifecycle implementation is merged on main in the independent Codex, Kimi and Claude Code repositories. Continue real optional contribution and reuse-loop acceptance, content quality, and OS-triggered scheduling; the user advances Windows on a dedicated real machine after merge. Windows remains part of the first-release target, not an outstanding gate for these completed merges. Old business Skills and profiling stay deferred.

Further domains, coordinator recipes and Harness expansion require a concrete useful task; they are not prerequisites for routine plugin use.

# MindIE Agent brand assets

The violet stacked-agent mark identifies the organization, the main MindIE
Agent project, and the Codex, Kimi Code and Claude Code adapters.

- `mindie-agent-logo-source.png`: original 1254 × 1254 imagegen output.
- `mindie-agent-logo.png`: 512 × 512 transparent PNG for logos and avatars.
- `mindie-agent-icon.png`: 128 × 128 transparent PNG for compact UI icons.
- `PROMPT.md`: the generation prompt and visual reference.

Brand accent: `#7045F5`. The same high-contrast mark works on light and dark
backgrounds. Preserve its aspect ratio and transparent outer margin.

The organization profile and adapter READMEs use the shared logo URL in this
repository. Each shared runtime component and benchmark repository maintains its
own sibling mark in the unified `#7045F5` violet-and-white MindIE Agent visual
family under its `assets/brand/` directory (`remote-dev`, `knowledge`,
`coordinator`, `profiler`, `sim`, `npu-top`, `diagnostics`, and `mindie-bench`).

The Codex plugin bundles the logo and icon in both its plugin and entry Skill
assets so native presentation works offline. When replacing the parent mark,
update those packaged copies and the GitHub organization avatar together.

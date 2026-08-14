# skills

Shared Claude Code skills, agents, and hooks for the team.

## Layout

- `skills/` — skill directories. Install by copying into `~/.claude/skills/` (user-wide) or `<project>/.claude/skills/` (project-scoped).
- `agents/` — subagent definitions (`*.md`). Copy into `~/.claude/agents/` or `<project>/.claude/agents/`.
- `hooks/` — hook scripts plus `settings-snippet.json` showing how they're wired. Copy scripts into `~/.claude/hooks/` and merge the snippet into `~/.claude/settings.json`.
- `statusline/` — status line script; wiring is in the same settings snippet.

## Install

```bash
git clone https://github.com/AnsweringRND/skills.git
cp -R skills/skills/* ~/.claude/skills/
cp skills/agents/*.md ~/.claude/agents/        # or into a project's .claude/agents/
cp skills/hooks/*.py skills/hooks/*.sh ~/.claude/hooks/
cp skills/statusline/*.sh ~/.claude/hooks/
# then merge hooks/settings-snippet.json into ~/.claude/settings.json
```

## Third-party: mattpocock/skills

The engineering skill set from [mattpocock/skills](https://github.com/mattpocock/skills) (`triage`, `to-tickets`, `to-spec`, `implement`, `tdd`, `code-review`, …) is used alongside these but **not vendored here** — it's installed as symlinks into an upstream clone so `git pull` keeps it current:

```bash
git clone https://github.com/mattpocock/skills.git mattpocock-skills
# link the promoted buckets into a project's .claude/skills/
find mattpocock-skills/skills/engineering mattpocock-skills/skills/productivity \
  -name SKILL.md -not -path '*/node_modules/*' -print0 |
  while IFS= read -r -d '' f; do
    src="$(dirname "$f")"; ln -sfn "$src" "<project>/.claude/skills/$(basename "$src")"
  done
```

Those skills read their per-repo config from `docs/agents/` — `issue-tracker.md`, `triage-labels.md`, `domain.md`. This repo's copies are set up for GitHub Issues on `AnsweringRND/skills`, the default triage label vocabulary, and a single-context domain layout.

## Caveats

- Several skills and hooks reference absolute paths under `/Users/kai/` (Obsidian vault, `fw` CLI, project checkouts). Adjust paths for your machine before use.
- `open-items` and `running-view` keep runtime state (`items.json`, `state.json`, `out/`) that is intentionally not committed here — the skills create their own on first run.
- Some skills depend on connected MCP servers (Slack, Google Calendar/Gmail/Drive) being available in your Claude Code session.

## Contributing

New skills, agents, and hooks get copied here and pushed when created. Keep runtime state and logs out of the repo (see `.gitignore`).

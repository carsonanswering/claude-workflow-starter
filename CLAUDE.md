# claude-workflow-starter

Answering.com's complete Claude workflow suite: one repo that turns a fresh machine into an orchestrated agent-team workstation. Skills + subagents ship as the `answering-suite` plugin (registered from this checkout as marketplace `answering-workflows`); experimental agent teams are enabled by this repo's `.claude/settings.json`.

## What lives where

- `plugins/answering-suite/skills/` — all 32 skills, including `retell` (Retell AI voice/chat agent composer + validator) and `workflow-starter` (the flagship orchestration runbook).
- `plugins/answering-suite/agents/` — 8 specialist subagents from the Answering team suite (web-researcher, claim-verifier, prompt-engineer, test-triage, ...).
- `.claude/agents/` — 3 suite-native roles: `voice-agent-engineer`, `workflow-qa`, `ai-employees-operator`. Available even before the plugin is installed.
- `apps/ai-employees/` — the AI-employees company runner (Python, uv). Role-scoped employees, task queues, journals, standups.
- `plugins/answering-suite/extras/` — optional kit: hooks, statusline, pi-delegation, scoped harnesses, original Answering docs. Nothing here auto-loads.
- `install.sh` — Mac bootstrap. `README.md` — full manual.

## Kicking off work

The flagship entry point is the `workflow-starter` skill: give it a goal ("/workflow-starter ship a demo voice agent for a dental office") and it scopes a task DAG, spawns named teammates, supervises under doctrine, and QA-gates every completion. For direct control, plain language works too: "Spawn three teammates to ...".

## Doctrine

The orchestration doctrine (delegate by default, a worker's completion is a claim not a fact, disjoint file ownership, never ship unvalidated Retell JSON) lives in `~/.claude/CLAUDE.md` so it applies to **every** session on this machine — Orca worktrees and ssh/tmux sessions included, not just ones opened inside this repo. It is deliberately not duplicated here.

Repo-specific additions:

- ai-employees runs go through uv: `uv run --project apps/ai-employees python -m ai_employees --help`. Every run ends with a standup naming who did what and why.
- The in-repo copy of the Retell validator is `plugins/answering-suite/skills/retell/scripts/validate_retell.py`; the installed copy the doctrine cites is `~/.claude/skills/retell/scripts/validate_retell.py`. They are the same file — edit here, then `./install.sh --user-wide`.

## Machine notes

This machine is `Kais-Mac-mini` (macOS 26.3, arm64) — the designated multi-agent workstation. Deployed 2026-08-14; paths retargeted from the original Linux host. Full record in `docs/SETUP.md`.

- **Skill source of truth** is `~/.claude/skills` (32) and `~/.claude/agents` (11), installed by `install.sh --user-wide`. The `answering-suite` plugin is intentionally *not* installed — running both double-listed all 24 model-invocable skills. **After editing skills here, re-run `./install.sh --user-wide`** or the copies go stale silently.
- **Working tree** is `~/Desktop/projs` — Orca's registered folder. `~/Desktop/projs/.claude/{skills,agents}` symlink into `~/.claude`, so project-scoped lookups and script paths like `solve-issues`' `tracker.sh` resolve. Individual project checkouts under it are created on demand, not pre-seeded.
- **Available**: tmux, uv, node, gh (authed as `carsonanswering`), Orca.app, Claude Code 2.1.232.
- **Not available on this machine** — these skills load but fail at the dependency, not at a path: `fw-delegate` (no `fw` CLI), `pi-delegate` (no `~/.pi` harness), `lightning`/`local-delegate` (expect `lo`). Slack-flavored skills (`carson-update`, `slack-insights`, `comp-watch`) and Google-flavored ones (`daily-brief`, `meeting-notes-sync`) need their MCP connections attached to the session.
- Environment lives in `~/.zshenv` (not `.zshrc`) so non-interactive `ssh host <cmd>` gets it: `ORCA_CLI_COMMAND`, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, Homebrew and `~/.local/bin` on PATH.

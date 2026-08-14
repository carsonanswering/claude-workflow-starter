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

## Doctrine (applies to every session in this repo)

- Delegate by default. Broad searches, multi-file verification, test-suite runs, and 3+ independent lookups go to subagents or teammates — read `team-orchestration` before running a fleet; `frontier-orchestrator` covers model/cost choices for fan-outs; `loop-doctrine` governs autonomous loops.
- A worker's completion message is a claim, not a fact. Verify through `workflow-qa` or `claim-verifier` before relaying anything upward.
- Retell JSON is never delivered unvalidated: `python3 plugins/answering-suite/skills/retell/scripts/validate_retell.py <file>` must pass first. Engine first, then agent; prompts/tools/states live on the engine, voice/webhooks/analysis on the agent.
- ai-employees runs go through uv: `uv run --project apps/ai-employees python -m ai_employees --help`. Every run ends with a standup naming who did what and why.
- Teammates own disjoint file sets. Two teammates in one file is a scoping bug — fix the DAG, not the merge.

## Machine notes

This machine is `Kais-Mac-mini` (macOS 26.3, arm64) — the designated multi-agent workstation. Paths were retargeted from the original Linux host to `/Users/kai` on 2026-08-14.

- **Skill source of truth** is `~/.claude/skills` (32 skills, copied user-wide by `install.sh --user-wide`). `~/projs/.claude/skills` and `~/projs/.claude/agents` are symlinks into it, so `solve-issues`' `tracker.sh` and friends resolve. After editing skills in this repo, re-run `./install.sh --user-wide` or the copies go stale.
- **Working tree** for skill-referenced projects is `~/projs` (notes/meetings, session-logs, prompts, atlas/gen, wt, .worktrees). Individual project checkouts under it are created on demand, not pre-seeded.
- **Available**: tmux, uv, node, gh (authed as `carsonanswering`), Orca.app, Claude Code 2.1.232.
- **Not available on this machine** — these skills load but will fail at the dependency, not at a path: `fw-delegate` (no `fw` CLI), `pi-delegate` (no `~/.pi` harness), `lightning`/`local-delegate` (expect `lo`). Slack-flavored skills (`carson-update`, `slack-insights`, `comp-watch`) and Google-flavored ones (`daily-brief`, `meeting-notes-sync`) need their MCP connections attached to the session.
- `orchestration` and `orca-cli` resolve the Orca binary via `ORCA_CLI_COMMAND` (exported in `~/.zshrc` → `/Applications/Orca.app/Contents/Resources/bin/orca`).

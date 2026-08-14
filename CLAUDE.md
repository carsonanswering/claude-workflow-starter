# claude-workflow-starter

Answering.com's complete Claude workflow suite: one repo that turns a fresh machine into an orchestrated agent-team workstation. Skills + subagents ship as the `answering-suite` plugin (registered from this checkout as marketplace `answering-workflows`); experimental agent teams are enabled by this repo's `.claude/settings.json`.

## What lives where

- `plugins/answering-suite/skills/` — all 32 skills, including `retell` (Retell AI voice/chat agent composer + validator) and `workflow-starter` (the flagship orchestration runbook).
- `plugins/answering-suite/agents/` — 8 specialist subagents from the Cortex team suite (web-researcher, claim-verifier, prompt-engineer, test-triage, ...).
- `.claude/agents/` — 3 suite-native roles: `voice-agent-engineer`, `workflow-qa`, `ai-employees-operator`. Available even before the plugin is installed.
- `apps/ai-employees/` — the AI-employees company runner (Python, uv). Role-scoped employees, task queues, journals, standups.
- `plugins/answering-suite/extras/` — optional kit: hooks, statusline, pi-delegation, scoped harnesses, original Cortex docs. Nothing here auto-loads.
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

- Some Cortex skills reference `/Users/taj/...` paths (obsidian-log, meeting-notes-sync, tracker-refresh, open-items, fw-delegate, pi-delegate, launchd-manage, push-and-brief, carson-update, repo-atlas, raise-research, frontier-orchestrator's dispatch notes). They run after you retarget those paths — see README "Path caveats".
- `orchestration` and `orca-cli` skills expect the Orca binary; `tmux-fleet` and split-pane teams expect tmux. Slack-flavored skills (carson-update, slack-insights, comp-watch) need a Slack MCP connection.

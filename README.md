# claude-workflow-starter

The complete Answering.com Claude workflow suite in one deployable repo: 32 skills (including the Retell AI voice/chat agent composer and a flagship `workflow-starter` orchestrator), 11 specialist subagents, the Answering team's orchestration doctrine, the `ai-employees` company runner, and project settings that switch on Claude Code's experimental **agent teams**. Clone it on any Mac, run one script, and the machine is an orchestrated agent workstation.

## 1. Publish this repo to GitHub (one-time)

The bundle you received is already a complete git repository (committed on `main`). To put it under your GitHub account:

1. Create an empty **private** repo named `claude-workflow-starter` at <https://github.com/new> — no README, no .gitignore.
2. Then, from the unzipped folder:

```bash
cd claude-workflow-starter
git remote add origin https://github.com/YOUR-GITHUB-USERNAME/claude-workflow-starter.git
git push -u origin main
```

## 2. Deploy on the Mac mini

```bash
git clone https://github.com/YOUR-GITHUB-USERNAME/claude-workflow-starter.git
cd claude-workflow-starter
./install.sh --with-ai-employees --teammate-mode auto
claude
```

Then kick off the flagship workflow from inside Claude Code:

```
/workflow-starter ship a demo voice agent for a dental office
```

`install.sh` installs Claude Code if missing, registers this checkout as plugin marketplace `answering-workflows`, installs the `answering-suite` plugin, and (with flags) sets your teammate display mode and prepares `apps/ai-employees` with uv. Run `./install.sh --help` for all flags; `--user-wide` additionally copies skills/agents into `~/.claude` as a plugin-free fallback.

## 3. What's inside

```
.claude/settings.json          # enables CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 for this project
.claude/agents/                # suite-native roles: voice-agent-engineer, workflow-qa, ai-employees-operator
.claude-plugin/marketplace.json# this repo doubles as marketplace "answering-workflows"
plugins/answering-suite/       # the plugin: skills/ (32) + agents/ (8) + extras/
apps/ai-employees/             # AI-employees company runner (Python 3.12+, uv)
CLAUDE.md                      # project playbook every session loads
install.sh                     # Mac bootstrap
```

## 4. How a workflow run flows

The `workflow-starter` skill is the entry point. As team lead, Claude restates your goal with done-criteria, builds a task DAG sized 5-6 tasks per teammate with disjoint file ownership, spawns named teammates from the roster (voice, research, build, employees — plus `workflow-qa` on every run), supervises under `team-orchestration` doctrine, and gates each lane through QA before anything is reported done. Retell JSON never ships without passing the bundled validator; ai-employees lanes end in a standup naming who did what and why. The deeper doctrine lives in the skills themselves: `team-orchestration` (delegation and trust rules), `frontier-orchestrator` (model/cost strategy for fan-outs), `loop-doctrine` + `ooda` (autonomous loops).

## 5. Agent teams primer

Agent teams are experimental in Claude Code (v2.1.178+). This repo's project settings enable them, so any session started in the repo can spawn real teammates — independent Claude Code sessions with a shared task list and inter-agent mail — not just subagents. Useful phrases: "Spawn three teammates to ...", "Require plan approval before they make changes", "Wait for your teammates to finish", "Ask the voice teammate to shut down". The in-process agent panel works in any terminal (arrow keys + Enter to open a teammate; Ctrl+T toggles the task list); split panes need tmux or iTerm2 with the `it2` CLI. Known limits: one team per session, no nested teams, `/resume` doesn't restore in-process teammates, and token use scales with teammate count.

## 6. Skills inventory (32)

| Group | Skills |
|---|---|
| Orchestration & fleets (13) | workflow-starter, team-orchestration, orchestration, orca-cli, frontier-orchestrator, loop-doctrine, ooda, tmux-fleet, lightning, local-delegate, fw-delegate, pi-delegate, oss-session |
| Voice (1) | retell — compose/edit/validate/import Retell AI voice & chat agent JSON; ships `scripts/validate_retell.py` and five field-level reference docs |
| Daily ops & comms (12) | daily-brief, day-plan, open-items, running-view, push-and-brief, carson-update, meeting-notes-sync, obsidian-log, slack-insights, comp-watch, tracker-refresh, raise-research |
| Repo & dev (6) | repo-atlas, solve-issues, deploydemo, skill-sync, find-skills, launchd-manage |

Plugin skills are namespaced when invoked via the plugin (e.g. `answering-suite:retell` in listings; `/retell` still works when unambiguous).

## 7. Subagents (11)

From the Answering suite (in the plugin): web-researcher, claim-verifier, prompt-engineer, test-triage, branch-verdict, repo-sweeper, session-log-analyst, slack-transcript-analyst. Suite-native (project-level, always available): voice-agent-engineer, workflow-qa, ai-employees-operator. All are usable both as delegated subagents and as agent-team teammate types ("Spawn a teammate using the workflow-qa agent type ...").

## 8. ai-employees

`apps/ai-employees` is the AI-employees company runner: named, role-scoped employees (Engineer, Marketer, Ops, Chief of Staff, ...) pull tasks from a shared backlog, write evidence to per-employee journals, and gate high-stakes actions on your approval — you read standups, not raw logs. Setup is `./install.sh --with-ai-employees` (or `cd apps/ai-employees && uv sync`); drive it with `uv run --project apps/ai-employees python -m ai_employees --help`, starting from `examples/toyco.yaml`. The `ai-employees-operator` agent knows these conventions.

## 9. Caveats you should actually read

**Machine-specific paths.** These Answering skills reference `/home/schmi/...` (Obsidian vault, `fw` CLI, project checkouts) and need retargeting before first use on your machine: carson-update, tracker-refresh, push-and-brief, obsidian-log, open-items, pi-delegate, repo-atlas, launchd-manage, fw-delegate, meeting-notes-sync, raise-research, and frontier-orchestrator's dispatch notes. Search: `grep -rl "/home/schmi" plugins/`.

**External dependencies.** `orchestration` and `orca-cli` require the Orca binary; `tmux-fleet` and split-pane teams require tmux; carson-update / slack-insights / comp-watch expect a Slack MCP connection; daily-brief and meeting-notes-sync expect Google Workspace MCPs; `carson-update` posts Carson's progress update to their cofounder in #code-updates.

**Extras don't auto-load.** `plugins/answering-suite/extras/` holds the Answering hooks (session logging, self-improve, auto-title, usage dashboard), statusline, pi-delegation prompts, and scoped harnesses. They're inert until you wire them — see `extras/hooks/README.md`.

**License.** Answering skills and ai-employees are your team's internal code; the repo is marked private/proprietary. Don't make this repo public without scrubbing team-internal references first.

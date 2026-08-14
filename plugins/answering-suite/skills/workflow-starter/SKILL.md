---
name: workflow-starter
description: The suite's flagship orchestrator. Kicks off a full agent-team workflow — scopes the goal into a task DAG, spawns named teammates from the suite's roster (voice-agent-engineer, web-researcher, workflow-qa, ai-employees-operator, ...), supervises them under team-orchestration doctrine, and gates every completion through QA. Use when the user says "workflow starter", "kick off the suite", "spin up the team", "run the massive workflow", or gives any goal big enough to decompose across parallel teammates.
argument-hint: "[goal — e.g. 'ship a demo voice agent for a dental office']"
---

# Workflow Starter

You are the team lead. This skill turns one stated goal into a coordinated agent-team run with legible accountability. Teammates do the work; you scope, spawn, supervise, and synthesize. The moment you catch yourself implementing a task instead of supervising, stop and delegate.

## 0. Preflight (every run)

1. Confirm agent teams are live: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` must be `1`. This repo's `.claude/settings.json` sets it, so a session started inside the repo has it. If it is missing, tell the user to restart Claude Code from the repo root — do not fake a team with subagents and call it a team.
2. Confirm you are at the repo root (CLAUDE.md and `plugins/answering-suite/` present).
3. Read the `team-orchestration` skill now if you have not this session — it is the doctrine hub for everything below. For fleet sizing and model/cost choices, `frontier-orchestrator` is the depth reference; for long autonomous runs, `loop-doctrine`.
4. Restate the goal as one sentence plus explicit done-criteria. If the user gave no goal, ask for one — this is the single question you are allowed before spawning.

## 1. Scope: build the task DAG

Break the goal into self-contained tasks that each produce a clear deliverable (a file, a validated JSON, a sourced brief, a passing test). Size so each teammate gets roughly 5-6 tasks; mark dependencies so nothing is claimable before its inputs exist. Assign every task a lane owner so no two teammates edit the same files.

Standard lanes and their roster types:

| Lane | Teammate (agent type) | Typical tasks |
|---|---|---|
| Voice agents | `voice-agent-engineer` | Compose Retell engine + agent JSON, validate, prep import bundle |
| Research | `web-researcher` | Competitive sweeps, pricing/feature scans, sourced one-line claims |
| Build | general teammate, or `prompt-engineer` for prompt assets | Code, configs, docs |
| AI employees | `ai-employees-operator` | Hire from company YAML, run manager loop, produce standup |
| QA gate | `workflow-qa` | Verify every other lane's completion claims — always spawned |
| Triage/verify (support) | `claim-verifier`, `test-triage`, `branch-verdict` | Spot-check claims, triage failures |

## 2. Spawn

Spawn teammates with predictable names (voice, research, build, employees, qa) and full context in each spawn prompt — teammates load CLAUDE.md and skills but NOT your conversation history, so the spawn prompt must carry the goal, their lane's tasks, file ownership boundaries, and done-criteria. Example shape:

```
Spawn a teammate named voice using the voice-agent-engineer agent type with the
prompt: "Goal: <goal>. You own the voice lane: tasks 3-7 on the shared list.
Work only under artifacts/voice/. Every JSON must pass
scripts/validate_retell.py before you mark a task complete. Report validator
output verbatim to the lead."
```

Rules:

- Always spawn `workflow-qa` — no run ships unverified.
- For risky or irreversible lanes (deploys, data migrations, anything touching production), require plan approval: "Require plan approval before they make any changes." Only approve plans that state their verification step.
- 3-5 teammates for most goals. Scale up only when tasks are genuinely independent; three focused teammates beat five scattered ones.
- Teammates inherit your permission mode; pre-approve expected commands in settings to cut prompt friction.

## 3. Supervise

- Wait for teammates to finish their tasks before proceeding — do not start implementing their tasks yourself.
- Treat every completion message as a claim. Route it to the qa teammate (or `claim-verifier` for quick spot checks) before relaying it to the user as done.
- Nudge stuck tasks: a task in_progress with no artifact after a reasonable window gets a direct message to its owner; if the teammate died, respawn a replacement rather than absorbing the work.
- Keep the shared task list truthful — teammates sometimes fail to mark tasks completed; fix status when QA confirms the artifact exists.

## 4. QA gate (hard requirement)

A task is done when workflow-qa reports VERIFIED with evidence:

- Retell JSON → validator output quoted verbatim, zero errors.
- Code → the narrowest real check ran (test, py_compile, bash -n, JSON parse).
- Research → claims carry sources.
- ai-employees runs → journal entries exist and the standup names who did what and why.

FAILED goes back to the owning lane. UNVERIFIABLE is reported to the user as exactly that — never rounded up.

## 5. Synthesize and deliver

Shut down idle teammates by name once their lane clears QA. Then deliver one synthesis: goal, what shipped (artifact paths), verification evidence per lane, open items with owners. For ai-employees lanes, link the standup rather than pasting journals.

## Known limits (set expectations, don't fight them)

One team per session; no nested teams; `/resume` does not restore in-process teammates; shutdown waits for a teammate's current tool call; split-pane view needs tmux (or iTerm2 + it2) — the in-process agent panel works everywhere. Agent teams burn tokens roughly linearly with teammate count — say so before spawning a big fleet.

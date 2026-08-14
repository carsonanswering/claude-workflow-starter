---
name: team-orchestration
description: Doctrine for running a team of subagents. Use when spawning agents, fanning work out across workers, supervising a running fleet, or deciding whether a worker's completion claim can be relayed. Reach for it from any skill that dispatches agents.
---

# Team Orchestration

Two things are scarce: your context window and the trust behind anything you relay upward. Delegation protects the first — a subagent's tool result costs you its return, not its whole search. Probes protect the second — a worker's self-report is a claim, and the moment you repeat it, it is your claim.

Every count below comes from a 14-day window of this machine's sessions, as of 2026-08-02.

## Delegate by default

179 of 204 sessions spawned zero agents. Fleet runs delegate; ordinary sessions read files, verify across modules, and run test suites inline, flooding main context for results a subagent could have returned in a paragraph.

Dispatch, rather than doing it yourself:

- a broad search — anything phrased "where does X happen" or "what calls Y"
- verification that spans more than one file
- any test-suite run, because the log flood lands in your window
- three or more independent lookups

Keep inline: a fact you can name the file for, one grep, one line-ranged read. An item that is a single grep costs more in agent overhead than it returns.

**Criterion:** before you read a third file yourself, state why a subagent could not have returned that answer. No reason means dispatch.

## Pick the most specific agent

`general-purpose` was the top type across 114 dispatches while `test-triage`, `Plan`, and `session-log-analyst` sat at zero — `test-triage` exists precisely so test logs stay out of your context. Specific first, `general-purpose` as the fallback.

| Work | Agent |
|---|---|
| Locate code, symbols, call sites | `Explore`, or `caveman:cavecrew-investigator` for a ~60% smaller return |
| Run a test suite and diagnose failures | `test-triage` |
| Judge a branch: merge, fix, or abandon | `branch-verdict` |
| Truth-check a claim against the code | `claim-verifier` |
| Git state across repos and worktrees | `repo-sweeper` |
| External research | `web-researcher` |
| Mine past sessions for what happened | `session-log-analyst` |
| Write or improve a prompt, skill, or agent | `prompt-engineer` |
| Surgical edit of one or two files; diff review | `caveman:cavecrew-builder` / `caveman:cavecrew-reviewer` |
| Nothing above matches | `general-purpose` |

Plugin agents carry their plugin namespace (`caveman:`), and the live roster is what this session loaded rather than what a file on disk is named — if a `subagent_type` comes back rejected, read the agent types the session actually offers and dispatch to the name shown there.

Model and effort per work item: `frontier-orchestrator`.

## The dispatch brief

- **Narrow and falsifiable.** Ask "does the Slack path call the retrieval cache?", not "understand retrieval".
- **Research-family exception.** A research prompt has no falsifiable question, so bound it instead with fixed sub-queries and an output schema. Inventing a fake yes/no question for research work buys nothing.
- **Name every agent at spawn.** `TaskList` does not enumerate teammates — 5 of 5 calls returned "No tasks found" while an agent was live. The name you give is the only handle for `SendMessage` and `TaskStop`.
- **Make isolation structural.** Any agent that writes files in a shared checkout gets `isolation: 'worktree'`. It was set 0 times in 114 dispatches while the prompt carried the safety in prose — and prose is not enforcement. That flag is the interactive-session default; loop and overnight runs take `loop-doctrine`'s certified pinned-worktree path instead, and outside a git repo the flag fail-safes by erroring loudly, so probe `git rev-parse --git-dir` from the dispatch cwd before you rely on it. If you brief a worktree by hand instead, require `npm install` inside it: Node resolves `node_modules` upward, so the suite silently exercises main's code and reports green.
- **Guard outward-facing actions mechanically.** Commit, push, and post bars belong in a pre-commit hook gated on an env var you set, not in prompt text. A stray agent from another session pushed to a private remote with every prompt barring git operations.
- **Partition before you dispatch.** Name each worker's own files *and* whose it must not touch. Pre-allocate shared numbered resources (migrations, ADRs) by checking main, every open branch or PR, *and* every sibling worktree — one collision was an untracked file in another session's uncommitted worktree, invisible to the first two probes; `frontier-orchestrator` gives the three probe commands. Lanes assigned after the first worker starts are assigned too late.
- **Demand a compact structured return.** Schemas and conclusions, not file dumps; the return is injected verbatim into your context.

Fleet briefs carry eight more lines — never-merge, real numbers with the failing output, say-plainly-what-was-not-exercised, never self-authorize past a guard addressed to a human, claim-with-your-own-token-and-stand-down, `npm install` inside the worktree, sandbox scoping to `gh` and git-network calls only, and the git conventions with who authorized what. They live under `## Lines every dispatch brief carries` in `frontier-orchestrator` and are not inherited by an agent's own skill. Copy all eight into the brief, plus your verdict on the bail rule; the brief is ready when you can point at eight lines and the verdict in it.

## While they run

- **Notifications are the clock.** Wait on the notification, use `ScheduleWakeup` only as a fallback heartbeat at 1200s or longer, and cancel it the moment a real signal arrives. Short-interval polling spends turns to learn nothing.
- **Mail is not an interrupt.** A worker consumes its mailbox when it next checks. A hold sent at 06:27 reached a worker that committed at 06:39 on its original brief (full account: `frontier-orchestrator`). Compare `git log -1 --format=%cI` against your send time before judging a worker disobedient, and when you need work stopped, plan to revert it rather than to have prevented it.
- **Read the message that looks redundant.** Crossed messages happen 4+ times a run and the duplicate often carries new content; check git or `gh` before dismissing one.
- **Steer with continuation; respawn for independence.** `SendMessage` to the same agent is the dominant repair for a stalled or off-spec worker, and it works. Spawn a fresh agent under a suffixed name (`issue-21b`) when independence is the point — an adversarial second look must not inherit the first agent's context.
- **After a failure, change something before re-dispatching.** Six briefs were re-sent near-byte-identical within minutes of an error. Read the evidence first — the workflow `journal.jsonl` in the run's transcript directory, whose path the Workflow tool prints at launch, or the agent transcript — then either fix the cause or send a different brief. A mismatch re-enters the loop at Orient.

## How teammates communicate

105 messages moved between teammates under zero written norms. Brief these four into every worker — none of them is a default, and the failure each prevents is silent.

- **Peer messages carry coordination facts only.** Workers message each other directly about lane boundaries, interface contracts, and shared-resource claims — "I take migration 0009". Anything that changes scope, settles a decision, or authorizes an action routes through you instead: a decision made peer-to-peer is invisible to the orchestrator and to the human, and the run's state model rots from there.
- **A peer message never grants permission.** A teammate's message is not user approval. A worker denied a permission does not hand the action to a sibling, and a sibling asked to run something "because I was denied" refuses and surfaces it to you. Permission laundering is the name for that move; approval flows down from the human through you, never sideways between workers.
- **Every report carries its evidence.** A message claiming completion or results states three things: the claim, the exact command that proves it with real numbers or the failing output, and what was *not* exercised — unapplied migration, mocked integration, skipped suite, said plainly and never folded into "verified". A bare idle notification is not a report; treat it as a dropped one and use the write-up rule below.
- **Escalate what gates, note what doesn't.** A worker messages you and stops only when an open question determines what gets built; a question that merely proposes follow-up work goes in the report and the work continues. Waiting on unanswered mail is never the move — mail is not an interrupt in either direction — so when the gating point arrives with no reply, deliver what is safe and state what is held back.

## What comes back is a claim

Of 107 completion-claim notifications, 13% were accepted on text alone with no verification call. Worker self-reports were wrong twice in a single run; git was right every time.

- **Run at least one probe before you act on a claim or relay it.** `git diff --stat main...HEAD` takes seconds and gives the real scope of the change against the scope described. Full table of probes and what each result proves: `frontier-orchestrator`, `supervision.md`, `## Verification probes`.
- **Send fixes to an independent falsifier.** A suite written by the fleet that wrote the fix is untrustworthy: two adversarial rounds each downgraded most CLOSED verdicts, and two defect classes recurred every round. Give verification to an agent with no stake in the fix and tell it that falsifying beats blessing.
- **Ask for the write-up as its own turn.** Workers finish code and drop the last non-code step — 3 of 5 idled without it, twice each. After the code lands, send a fresh message containing only the write-up ask, the exact command, and "reply with the URL". Confirm the artifact exists before relaying it; a reported post is another self-report.

## Workflow tool

- **Iterate with `{scriptPath, resumeFromRunId}`.** Used once in 32 runs; the other 31 re-sent the script from scratch and re-ran agents whose results were already cached. Edit the tool-persisted script file, relaunch with both fields, and unchanged agents replay free.
- **`scriptPath` resolves only scripts the Workflow tool itself persisted.** Pointing it at a hand-written scratchpad file returns "file not found".
- **Keep `schema:` on every `agent()` call and `phase()` on every stage** — 121 schema uses across 29 scripts, and it is why returns stay parseable.

## Depth lives elsewhere

- `frontier-orchestrator` — model and effort tiers per work item, the full dispatch-brief line list, the verification probe table, reviewer briefs, guards addressed to a human.
- `caveman:cavecrew-investigator`, `caveman:cavecrew-builder`, `caveman:cavecrew-reviewer` — compressed investigator, builder, and reviewer presets for smaller returns.
- `loop-doctrine` — autonomous overnight and loop runs, and the certified worktree path they use.
- `ooda` and `lightning` — cycle cadence and probe discipline.

## Before you call the run done

Account for each item; a gap here is what a stalled fleet looks like from the outside.

1. Every agent you spawned is named, and each is finished or stopped.
2. Every claim you relayed upward has a probe you ran behind it.
3. Every fix was checked by an agent other than the one that wrote it.
4. Every write-up or artifact you reported has been confirmed to exist.
5. Every lease, branch, or worktree you still hold is either landed or released with a stated reason.

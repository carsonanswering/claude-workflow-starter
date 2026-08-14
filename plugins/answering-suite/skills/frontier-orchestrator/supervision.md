# Supervising workers

Read this once workers are live — before judging a worker, relaying any claim, closing a lease, or calling the run done. What to settle *before* dispatch is in [`fleet-dispatch.md`](fleet-dispatch.md).

Anecdotes and commands marked *worked example (cornea run)* come from the 2026-07 cornea `/solve-issues` fleet run and name that repo's local machinery. The rule above each one travels; the example only travels to a run with the same machinery.

## Mail is not an interrupt

A worker consumes its mailbox when it next checks, not when you send. A hold sent at 06:27 reached a worker already mid-task; it committed at 06:39:15 and pushed at 06:39:51 on its original brief.

**Never call a worker disobedient before comparing timestamps.** The probe that settles it:

```
git log -1 --format=%cI <sha>            # when the commit actually happened
gh pr view N --repo <owner/repo> --json createdAt
```

Compare both against the send time of your message. An instruction sent mid-flight does not bind work already in progress — if you need work stopped, expect to revert it, not to have prevented it.

## Verification probes

**Verify every claim against git before relaying it to a human.** Worker self-reports were wrong twice in one run; git was right every time. One worker reported "push succeeded without needing the `CORNEA_GIT_OK` flag" when it had set the flag (*worked example, cornea run*), and misreported the ordering of its own push against an incoming message. These probes are seconds each and each one proves something specific:

| Probe | What a result proves |
|---|---|
| `test -d <worktree>/node_modules` | Missing means the tests never exercised the branch — they ran main's code. Prevent it with the brief line in `fleet-dispatch.md`; this only detects it. |
| `git diff --stat main...HEAD` | Real scope of the change, versus the scope described. |
| `git diff --name-only main...HEAD -- tests/` | Empty means no tests were added, whatever "verified" claim came back. This surfaced 291 lines of new code with zero unit tests that the worker never mentioned. |
| `git rev-parse origin/<branch>` | Failure proves nothing was pushed; the branch exists only locally. |
| `git log -1 --format=%cI` / `gh pr view N --json createdAt` | Timelines, for any dispute about ordering. |

Run these before you summarize a worker's result upward. A relayed claim becomes yours.

## The final write-up is its own turn

Workers finish code reliably and drop the last non-code step. In the run, issue-17 and issue-16 each idled with correct code already pushed and needed the reviewer-brief ask sent twice.

Never append "and post a write-up" to the work brief. After the code lands, send a fresh turn that contains only the write-up ask, the exact command, and a report-back requirement:

```
gh pr comment N --repo <owner/repo> -F <file>.md
```
…then reply with the comment URL. Confirm it exists before relaying it — a reported post is a self-report; `gh pr view N --repo <owner/repo> --json comments` is the evidence.

**Close the lease yourself, last, and only after the deliverable exists.** The lease is the only signal that tells another session an issue is done rather than abandoned, and a worker that closes it before the write-up lands has published "finished" over incomplete work — which is exactly what happens when the closing step sits inside a work brief the worker is already exhausted by. Before declaring a run complete, list what you still hold and confirm each one is either finished with a PR or released with a stated reason. An issue silently held is invisible to every other session.

*Worked example (cornea run):* the lease helper is `/Users/kai/Desktop/projs/.claude/skills/solve-issues/tracker.sh`, and `$TOKEN` is the per-session token that skill has you generate once at the start of a run (`TOKEN="s-$(date +%s)-$RANDOM"`) and reuse for every lease command.

```
/Users/kai/Desktop/projs/.claude/skills/solve-issues/tracker.sh finish <issue> "$TOKEN" "<pr-url>"
/Users/kai/Desktop/projs/.claude/skills/solve-issues/tracker.sh stale 0     # every lease outstanding right now
```

Hold `finish` in your own hands and run it after you have seen the comment URL. The helper only requires the PR argument to be a non-empty string, so it enforces nothing on its own: the ordering is the mechanism, not the script.

## Guards addressed to a human

The environment hardened mid-run and the fleet knew none of it. The sandbox flag and the commit prefix go into the brief up front (see `fleet-dispatch.md`); guards that appear later get read, not routed around.

- **Read the guard before using any override it advertises, and never self-authorize the one reserved for a human.** When a guard's own text does not clearly cover the agent about to act, resolve it with the human rather than by picking the reading that unblocks you. If a hook's text and your instructions disagree, the hook wins and you surface the conflict.
  - *Worked example (cornea run):* `.git/hooks/pre-commit` and `pre-push` both gate on `CORNEA_GIT_OK=1`, but they say different things, and the difference is the whole rule. pre-push reserves the action for the human by name — so you may relay an authorization the human actually gave this session, and you may never manufacture one by setting the flag yourself. pre-commit names *the orchestrator*, and its first line also read "Subagents are not authorized to commit" — a live ambiguity, not a settled permission, since a dispatched worker is a subagent.
- **Never mint a new identity to defeat a concurrency guard.** A second identity or token holding two leases defeats the only thing preventing two workers from editing one issue. That is not a limitation to work around, it is the guard. Report to the human which issues are leased, which are unclaimed, and that more parallelism requires them to start another Claude Code session with its own token.
  - *Worked example (cornea run):* the lease script was rewritten mid-run to enforce one issue per session, detected via GitHub assignment — you cannot claim a second lease from a session that already holds one.

## Reviewer briefs: the highest-value artifact of a fleet run

After each PR, ask the worker that did the work — not a fresh reviewer — for a brief posted as a PR comment. It costs one cheap turn and it surfaced things no diff review would have: a 0.8 false-answer rate under the real production gate that CI structurally cannot see, an adjacent unrelated fix buried inside a PR, 291 lines with no unit tests, and a precise claim boundary on unproven security work.

Required sections:

1. What the issue asked for, in behaviour terms.
2. What changed, file by file.
3. How it was verified, with real numbers.
4. Where a reviewer should push back hardest.
5. What is **not** covered.
6. Risk if merged.

### Honesty rules to state in the brief ask

Workers respected these when told and needed ad-hoc reminders when not. State them in the brief request, not in the work brief:

- An unapplied migration is not a tested migration.
- Mocked coverage is not integration coverage.
- "Verified against PGlite with a non-superuser role" is accurate; "RLS verified" is not.
- A skipped suite is not a passing suite.

Also tell each worker to check the pickup prompt's cited `path:line` before building on it and to record any drift in the PR body — one worker found eight citations that had drifted 4–13 lines, and recording it fixes the tracker instead of letting it re-rot.

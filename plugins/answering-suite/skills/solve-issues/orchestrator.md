# solve-issues — the orchestrator's half

Read this before you write a single dispatch brief. Everything here binds the session **dispatching** workers; the worker's own protocol — guards, steps 1–8, the four complete endings — is in [SKILL.md](SKILL.md).

## Dispatching parallel workers

Five concurrent workers avoided branch collisions in the last run only because these were decided **before** dispatch, not during:

- **Each worker generates its OWN token.** Never pass yours down: `claim` tests assignment against the token, so a shared token makes every worker after the first hit exit 2 and stand down, and your fan-out silently collapses to one.
- **Check what branch the shared checkout is parked on, before you write a single dispatch brief**, and name `origin/main` as the explicit worktree start-point in every one of them:

  ```bash
  git -C /Users/kai/Desktop/projs/answering branch --show-current    # if this is not `main`, every bare `worktree add -b` inherits it
  ```

  Worker step 4 in [SKILL.md](SKILL.md) carries what a bare `worktree add -b` did to a run, and the `git diff --stat` that catches it. Three of the four workers caught it themselves; do not rely on that.
- **Tell workers the true test baseline, measured on `origin/main`.** Otherwise each one reports a count against whatever tree it happens to have, and you cannot tell an inflated number from a real one. Two workers independently reporting the same baseline is good evidence both trees are right; one reporting a wildly higher count is the first sign of a bad base.
- **Expect `.git/config` lock collisions.** Concurrent `worktree add` operations against the one shared checkout can fail mid-write. The branch is often created correctly despite the error — check before retrying, or a retry leaves orphaned worktree entries.
- **Assign a file lane per worker and name it** — "you own the eval harness", "you own the Slack answer path" — and tell each worker which files another worker owns and must not touch. Concurrent workers cannot see each other's diffs; the partition is the only thing preventing two branches from editing the same file.
- **Pre-allocate migration numbers.** Another session's migration lives in an uncommitted worktree, so it is invisible to `git log` and to GitHub. The worktree listing is the only place it appears — run the same listing command worker step 4 gives, in [SKILL.md](SKILL.md), across main and every sibling worktree before you hand any number out.
- **Read each pickup prompt's `## Decisions needed from Carson` before dispatch.** A worker's default is to release on a non-empty section, and it cannot override that itself. If a question genuinely proposes separate follow-up work rather than determining what gets built ("should URL redaction be filed as its own task?"), say so in the dispatch brief by name and put that work out of scope. Say nothing and you get a release — which is the safe direction, and cost 15 minutes of re-dispatch last run.
- **Push authorization.** If Carson has not authorized pushes for this run, expect locally committed unpushed branches back. That is the designed outcome, not a failed worker.

## Requesting the brief, and when the run is done

Ask for the brief as its own turn once the PR exists, quoting these six sections:

> 1. **What the issue asked for**, in behavior terms — not the ticket title restated.
> 2. **What changed, file by file.** Name anything in the diff that is not what the issue asked for.
> 3. **How it was verified, with real numbers** — commands run, counts, rates.
> 4. **Where a reviewer should push back hardest** — the weakest part, in your own judgment.
> 5. **What is NOT covered** — step 5's honesty rules apply here in full.
> 6. **Risk if merged as-is.**

**You close the lease, not the worker, and only after you have seen the brief.** That ordering is the mechanism — `finish` enforces nothing itself, since its third argument only has to be a non-empty string. Once the brief URL exists:

```bash
/Users/kai/Desktop/projs/.claude/skills/solve-issues/tracker.sh finish <issue> "$TOKEN" "<pr-url> — brief: <brief-comment-url>"
```

The run is not complete until, for every PR opened, a brief comment exists and the lease is finished. Check it, do not ask:

```bash
gh pr view <n> --repo AnsweringRND/answering --comments
/Users/kai/Desktop/projs/.claude/skills/solve-issues/tracker.sh stale 0     # every lease still held, at any age
```

A worker that stops with its PR open and its lease still held has done exactly what this file asks. Do not treat an open lease at that point as an abandoned issue — it is waiting on you.

## Before you relay any worker claim to a human

Worker self-reports were wrong twice in five workers; git was right every time. Cheap probes, each of which can disprove a claim outright:

```bash
test -d <worktree>/node_modules                  # missing => tests ran MAIN's code, not the branch's
git diff --stat main...HEAD                      # real scope, vs. the described scope
git diff --name-only main...HEAD -- tests/       # empty => no tests added, whatever was claimed
git rev-parse origin/agent/issue-<n>             # failure means nothing was pushed
```

On the fourth: failure is **expected** when push authorization was withheld — check that first, and only treat it as a false report if the worker claimed a live PR.

The reverse is also decidable. `/Users/kai/Desktop/projs/answering/.git/hooks/pre-push` exits 1 unless `CORNEA_GIT_OK=1`, and worktrees share it, so while that hook stands, a branch that resolves on origin proves the flag **was** set. A worker reporting that it pushed without the flag is reporting something impossible; read the hook before relaying it.

**A message sent mid-task is not an interrupt.** A worker already executing acts on the brief it started with; a hold sent at 06:27 does not bind a commit made at 06:39. Before you ever report that a worker disobeyed, compare timestamps:

```bash
git log -1 --format=%cI <sha>                    # when the work actually committed
gh pr view <n> --repo AnsweringRND/answering --json createdAt
```

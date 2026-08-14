# Fleet dispatch: what to settle before the first brief goes out

Read this when workers will write to one shared repo. Everything here happens before dispatch; once they are live, [`supervision.md`](supervision.md) takes over.

Several rules below are illustrated with **worked examples from the 2026-07 cornea `/solve-issues` fleet run** (5 concurrent workers, 7 sessions). Those examples name that repo's local law — its env-var prefix, its lease script, its issue-template section. Carry the general rule everywhere; carry the example only into a run that shares the same machinery.

## Before dispatch: partition, or the branches collide

When workers write to one repo concurrently, nothing keeps them apart except what you decide up front. In the 5-worker run, collisions were avoided only by hand-partitioning; the mechanism did none of it.

- **Assign file lanes and name them out loud.** Each worker gets what it owns ("you own the eval harness", "you own the Slack answer path") *and* whose files it must not touch. A worker that knows only its own lane still wanders into a shared helper.
- **Pre-allocate migration numbers before dispatch.** Numbers collide at merge time, not at edit time, so the conflict shows up after five PRs exist. In the run, `006` was already taken, so `007` and `008` were handed out with the briefs.
- **Find the taken numbers with three probes, not one.** Committed numbers: `ls <migrations dir> | tail`. Numbers inside open PRs: `gh pr list --repo <owner/repo> --json headRefName`. Numbers in another session's *uncommitted* work: `git worktree list`, then `git -C <path> status --porcelain` on each. Last run `006` was an untracked file in a sibling session's worktree — invisible to the first two probes and to any grep of your own checkout.

## Lines every dispatch brief carries

These are not inherited. Two of the seven sessions in the run were research and repo-init work outside the `/solve-issues` flow, so the worker's own skill may carry none of this — yet both still needed the same guardrails. Put every line below into the brief, in the brief's own words — the run's briefs each carried most of them, and the ones they omitted are exactly where time was lost:

- **Never merge.** Open a PR and let a human merge it. A worker with push rights and a green suite will otherwise close its own loop, and nobody reviews a merged branch.
- **Verify with real numbers, and report a failure with its failing output.** Name the command (`npm test`, `npm run eval:retrieval`). "Tests pass" is unfalsifiable; a pasted failure is something you can act on, and a hidden one becomes a false claim you relay upward.
- **Say plainly what could not be exercised rather than calling it verified.** Unapplied migration, mocked integration, skipped suite, no live database — each of those is an unexercised claim. See the honesty rules in [`supervision.md`](supervision.md) for the exact wordings.
- **Never self-authorize past a guard addressed to a human.** If a hook, script, or prompt reserves an action for a named person, the worker stops and reports instead of setting the flag itself. The override string being printed in the hook is not permission to use it.
- **Claim first with your own session token, and stand down if you lose the race.** Wherever the run has a lease mechanism, each worker claims with its own identity and the loser takes something else.
  - *Worked example (cornea run):* the `solve-issues` lease resolves races by earliest claim comment — comment ids are monotonic, so two racing sessions reach the same verdict with no coordination. Its helper is `/home/schmi/projs/.claude/skills/solve-issues/tracker.sh`; each worker generates its own `$TOKEN` rather than inheriting yours.
- **`npm install` INSIDE the worktree is mandatory.** Node resolves `node_modules` upward into the parent checkout, so without it the suite silently exercises main's code and reports green. Five of seven briefs said this; the probe table in [`supervision.md`](supervision.md) only catches its absence afterwards, at the cost of a full re-run.
- **Scope `dangerouslyDisableSandbox: true` to `gh` and git-network calls only.** Sandboxed, they fail with `tls: failed to verify certificate: x509: OSStatus -26276`. Builds, tests, and edits have no reason to leave the machine.
- **State the git conventions and who authorized what.** Write "push is authorized" only when the human actually authorized it in this session — relaying a real authorization is your job, manufacturing one is the guard violation above.
  - *Worked example (cornea run):* commits required the `CORNEA_GIT_OK=1` prefix, and push was authorized by Carson. That prefix is that repo's local law; the general rule is to name whatever your repo's conventions are, in the brief, up front.

## Settle the bail rule — then write the verdict into the brief

When an issue carries a section of open questions for the human, the test is conditional, not binary:

- The answers determine **what gets built** (persist the raw query text? hash the user id? what retention window?) → release the issue and escalate. Building on a guess wastes the whole item.
- The answers only propose **separate follow-up work** (should URL redaction be filed as its own task?) → note it in the PR body and proceed.

*Worked example (cornea run):* that section is titled `## Decisions needed from Carson` on tracker issues, and the release decision was made by the *worker*, reading a binary rule in its own skill — it cost ~15 minutes of re-dispatch on an issue that was never blocked.

Deciding this in your head changes nothing. Your verdict only exists if it is in the brief, in words that countermand that default, naming the question and what is out of scope:

> The "Decisions needed from Carson" section on this issue is non-gating — it proposes separate follow-up work. Do not release. Retention policy is out of scope for this PR; note the question in the PR body and proceed.

An unstated verdict means the worker's default stands, and the default is release.

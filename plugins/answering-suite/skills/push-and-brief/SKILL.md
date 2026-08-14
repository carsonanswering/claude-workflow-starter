---
name: push-and-brief
description: Push the current branch, then brief Carson in three sections — Shipped, Needs-you, Next. Use when he says "push and brief", "push it and tell me what's next", or "ship it, what do you need from me".
---

# push-and-brief

The ritual that ends a change: the branch goes up, and Carson gets a brief he can
act on. The brief is a **report** — every line traces to a commit, a diffstat
row, or a command output you saw this run. Intentions live in Next, never in
Shipped.

## 1. Probe the real state

Run these in each repo this run changed (usually one), and read the output rather
than recalling what you did:

- `git rev-parse --abbrev-ref HEAD` — the branch this run touches, and the only one.
- `git rev-parse --abbrev-ref --symbolic-full-name @{u}` — the upstream, or a
  failure meaning there is none.
- `git status --porcelain` — everything uncommitted, staged included.
- `git log --oneline @{u}..HEAD` and `git diff --stat @{u}..HEAD` — what the push
  will carry. With no upstream, substitute the default branch and its merge base:
  `git log --oneline main..HEAD`, `git diff --stat main...HEAD`.

Staged work is still uncommitted work. Leave every path `git status --porcelain`
prints exactly where it is, and carry that list into the brief so Carson sees what
stayed behind — committing it quietly would put a claim in Shipped he never
approved.

**Done when** you can name, from output you ran this run: the branch, its
upstream or the lack of one, each commit about to go up, and every uncommitted
path — per repo.

## 2. Push the branch you are on

- Tracked branch: `git push`.
- No upstream: `git push -u origin HEAD` — `HEAD` resolves to the branch from
  step 1, so the push moves that branch and no other.

Push fast-forward only. Three situations stop the push and become Needs-you lines
carrying the exact command instead: one git refuses without `--force`, a repo
where `git remote -v` prints nothing, and a protected or shared branch that would
need a rewrite. Rewriting history someone else may hold is Carson's call.

**Done when** you have run `git status -sb` after the push and its first line
shows the branch with no `ahead` marker — quote that line verbatim in the brief.
A refused push finishes this step too: Shipped then says nothing went up, and
Needs-you carries git's error verbatim.

## 3. Write the brief to the terminal

Three sections, always all three, in this order. An empty one reads `none`.

**Shipped** — what the push actually contains, drawn from the log and diffstat
you read: plain-English behaviour, one line per commit or coherent group, with
real numbers (commits, files changed, tests you ran this run and their result).

**Needs-you** — only what Carson alone can supply: a decision between named options,
a review, a credential, or an outward-facing action (merge, remote or org
setting, anything that spends money). Each line ends with the single command or
URL that does it.

**Next** — what continues without him, and what is doing it.

Before printing, name to yourself the receipt behind every Shipped line — a
commit hash, a diffstat row, a test output. A line with no receipt moves to Next
as in-progress, or comes out. Keep the whole brief inside one screen; Carson reads
it to decide, not to learn the history.

**Done when** every Shipped line has a named receipt, every Needs-you line ends
in a command or URL he can act on, and all three headers are present.

## 4. Reconcile the tracker

Read `/home/schmi/.claude/skills/open-items/items.json` and compare its `you`
entries against your Needs-you lines. Drift runs both ways: a Needs-you line with
no entry, or an entry this push just closed.

Report the drift in one closing line and name `/open-items` as the fix. Leave the
file as you found it — `open-items` keeps item ids stable because Carson's check-offs
on the artifact are keyed to them, and an edit from here churns them.

**Done when** the brief ends with either "tracker matches" or a named drift plus
`/open-items`.

## Scope

- Slack belongs to `carson-update`, which owns the cofounder post; this brief is
  terminal output for Carson alone.
- A pull request opens only when Carson asked for one this run — `gh pr create` is
  his call, and pushing opens nothing by itself.

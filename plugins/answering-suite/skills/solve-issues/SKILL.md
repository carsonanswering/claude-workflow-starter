---
name: solve-issues
description: Pick up open AnsweringRND/tracker issues nobody else is working on and open a pull request per issue. Use when Carson says '/solve-issues', 'work the tracker', or names a specific tracker issue to work. Not for filing issues or for wayfinder maps.
---

# solve-issues

Work the AnsweringRND/tracker frontier autonomously, without colliding with another Claude Code session doing the same thing.

Everything in this file binds the **worker** — the session doing one issue. Dispatching workers instead of working an issue yourself? Read [orchestrator.md](orchestrator.md) before writing any brief — token rules, lane partition, requesting the brief, closing the lease.

Helper: `/home/schmi/projs/.claude/skills/solve-issues/tracker.sh`. Every invocation below spells out that absolute path, because step 4 moves you into a worktree that has no `.claude` of its own. All commands assume it is executable and that `gh` is authenticated.

## The concurrency problem, and why the lease exists

Every Claude Code session authenticates to GitHub as the same user. So "is this issue assigned?" cannot tell you whether *another session* is on it or whether *you* are. Assignment alone is not mutual exclusion.

The lease closes that: claiming writes a comment carrying a token unique to this session, and the **earliest claim comment wins**. GitHub comment ids are monotonic, so two sessions racing the same issue reach the same verdict independently, with no coordination. The loser stands down and takes something else.

Generate the token **once** at the start of your own run and reuse it for every command in the run:

```bash
TOKEN="s-$(date +%s)-$RANDOM"
```

Every `claim`, `release`, and `finish` needs it. If you were dispatched with someone else's token, generate your own instead and say so — see the one-lease guard below.

## What is eligible

`tracker.sh next` returns open issues that are unassigned, have no open blocker, carry no `wayfinder:*` label, and are not labelled `needs:carson`.

Those exclusions are deliberate:

- **`wayfinder:*`** — map tickets are human-in-the-loop by design. A grilling ticket resolved by an agent answering its own questions is a broken ticket. Leave maps to `/wayfinder`.
- **`needs:carson`** — the issue needs a founder decision (spending money, signing something, contacting a customer, naming something customers will see). Its pickup prompt says which. Working it without the answer produces confidently wrong work.
- **Open blockers** — the tracker's dependency edges are real. Starting a blocked issue means building on something that may still change.

## The environment guards, and how to work inside them

Three guards exist in this repo. All three look like failures when you first hit them. None of them is a reason to improvise around it.

**1. Sandboxed network calls fail TLS.** `gh` and every git network operation fail inside the sandbox with `tls: failed to verify certificate: x509: OSStatus -26276`. The sandbox's certificate store cannot verify GitHub. Run **those calls only** with `dangerouslyDisableSandbox: true` — `gh` commands, `tracker.sh` (it is a `gh` wrapper), `git push`, `git fetch`. Keep everything else sandboxed: builds, tests, and edits have no reason to leave the machine, and a blanket disable removes the guard from the operations that actually need it.

**2. Git hooks gate commit and push on `CORNEA_GIT_OK=1`.** `/home/schmi/projs/answering/.git/hooks/pre-commit` and `.../pre-push` exist and may be added or changed mid-session. Worktrees share these hooks with the main checkout. **Read the hook before using any override you were told about** — the two hooks say different things and grant different authority:

- `pre-commit` prints "Subagents are not authorized to commit. Orchestrator: prefix the command with `CORNEA_GIT_OK=1`." Read literally that is ambiguous for a dispatched worker, which is a subagent. **Carson has settled it: a worker running this skill may commit with the override.** "Orchestrator" means the orchestrated run, not one specific agent. Prefix `CORNEA_GIT_OK=1 git commit ...` and say in your report that you used it. If you ever meet a *different* guard whose text does not clearly cover the agent about to act, do not resolve it by picking the reading that unblocks you — stop and ask.
- `pre-push` reserves the action for Carson by name: "Pushing requires explicit authorization from Carson." Setting the flag yourself to push is self-authorizing an outward-facing action the hook says is not yours to take. **Stop and ask.** Push only after Carson has authorized it in this session, and say in your report that you used the override and who authorized it. A locally committed, unpushed branch is a **successful** ending — see step 6.

If a hook's text and your instructions disagree, the hook wins and you surface the conflict.

**3. `tracker.sh claim` enforces one open issue per session** by checking GitHub assignment against your token. A second claim exits **2** with `REFUSED — this session already holds #N`. That is the guard working. Finish or release what you hold, or open a **second Claude Code session** with its own token. Never mint a fresh token or a fresh identity to get a second lease in one session: a session holding four issues stalls three of them behind its own single-threaded work while hiding them from every other session.

## Running it

### 1. Survey

```bash
/home/schmi/projs/.claude/skills/solve-issues/tracker.sh next
```

Report the list to Carson before starting: number, priority, product, title. If he named a specific issue, work that one instead — but still claim it, and still refuse it if it is blocked or already held.

Also check for abandoned work from a crashed session:

```bash
/home/schmi/projs/.claude/skills/solve-issues/tracker.sh stale 4
```

Do not silently reclaim. Show Carson what looks abandoned and let him say.

### 2. Claim before reading, let alone editing

```bash
/home/schmi/projs/.claude/skills/solve-issues/tracker.sh claim <issue> "$TOKEN" || echo "skip, take the next one"
```

Exit 0 means the lease is yours. **Exit 1 means another session got there first — move to the next issue without comment.** Exit 2 means this session already holds an issue; see guard 3. Never work an issue you did not win.

### 3. Get the prompt

Each issue has a self-contained pickup prompt in the tracker repo:

```bash
gh api repos/AnsweringRND/tracker/contents/prompts --jq '.[].name' | grep "^<issue>-"
gh api repos/AnsweringRND/tracker/contents/prompts/<file> -H "Accept: application/vnd.github.raw"
```

**If the `grep` matches nothing, this issue has no pickup prompt** — the coverage is not guaranteed. Release the lease with that reason (`release <issue> "$TOKEN" "no pickup prompt in AnsweringRND/tracker/prompts"`), tell Carson the prompt is missing, and take the next issue. The issue body alone carries no `path:line` evidence and none of the doctrine that constrains the work, so building from it means inventing the scope. The single exception: your dispatch brief already carries the full scope and evidence itself — then work the brief, and say in your report that no prompt file existed.

Follow its `## Prompt` section. It carries its own context, `path:line` evidence, and the doctrine that constrains the work — it does not need the issue body.

**Verify the evidence before building on it.** These prompts cite line numbers, and line numbers drift. If a cited `path:line` no longer says what the prompt claims, stop, correct it, and **record every drifted citation in the pull request body, old → new** — one issue last run had eight citations off by 4–13 lines, and that drift is a tracker bug worth reporting even though the work still shipped. If the cited code is gone rather than moved, the premise is stale: release.

**If the prompt has a non-empty `## Decisions needed from Carson` section, your default is to release.** Release, quote the questions, tell Carson the `needs:carson` label is missing, and move on. The single exception: the dispatch brief you were given **names that specific question, calls it non-gating, and excludes the work it refers to from your scope**. Silence in the dispatch brief is not permission — release.

You do not get to decide for yourself that a question is harmless. That call was made up front by whoever dispatched you, or it was not made. An unanswered founder decision produces a confidently wrong deliverable that a reviewer may accept; a wrong release costs one re-dispatch.

### 4. Work in an isolated worktree

Never work directly in the main checkout — parallel sessions share it, and one session's edits become another's phantom failures.

```bash
cd /home/schmi/projs/answering
git fetch origin                                                    # dangerouslyDisableSandbox
git worktree add ../.worktrees/issue-<n> origin/main -b agent/issue-<n>
cd ../.worktrees/issue-<n>
npm install          # REQUIRED
git diff --stat origin/main...HEAD                                  # must be empty
```

**A leftover `../.worktrees/issue-<n>` or `agent/issue-<n>` means a previous session crashed there**, and `worktree add` will fail on it. Treat it exactly like step 1's abandoned work: show Carson what is in it and let him say. Two probes tell him what he is deciding about:

```bash
git -C /home/schmi/projs/.worktrees/issue-<n> status --short
git -C /home/schmi/projs/answering log --oneline origin/main..agent/issue-<n>
```

Once he says the leftovers go, `git worktree remove --force ../.worktrees/issue-<n>` then `git branch -D agent/issue-<n>`, and add fresh. Removing them yourself first is destroying work whose value only Carson can judge.

**Pass `origin/main` as the start-point explicitly.** Omit it and `worktree add` branches from whatever the shared checkout's HEAD happens to be — which is not `main` whenever someone has left it parked on a feature branch. That is not hypothetical: it happened to four dispatched workers in one run, and the one that did not catch it opened a pull request carrying ~15k lines of an unrelated unmerged branch behind a 5-file fix. The `git diff --stat` above is the cheap proof; run it before you write anything, and again before you push.

`npm install` in the worktree is not optional. Without it, Node resolves up to the main checkout's `node_modules` and the tests silently exercise **main's code, not yours** — a green run that proves nothing. This has burned this repo before. Re-run it after any rebase: `package.json` can differ between bases, and a stale `node_modules` invalidates the test run you are about to report.

**Measure the baseline immediately after `npm install`, before your first edit**, so your "after" number means something: the tree is clean at that moment, so run the suite there and record the counts as the baseline. Do not infer the baseline from a previous run on a tree you did not verify.

Stay inside your assigned file lane. If the fix genuinely requires touching a file another worker owns, stop and ask the orchestrator rather than editing it — concurrent branches cannot see each other, so the collision only surfaces at merge.

**Before you create a migration file, confirm its number twice:** against the number your dispatch brief handed you, and against what is already on disk here and in every sibling worktree.

```bash
ls /home/schmi/projs/answering/packages/cornea-authz/src/db/migrations/ \
   /home/schmi/projs/.worktrees/*/packages/cornea-authz/src/db/migrations/ 2>/dev/null | sort -u
```

Migration filenames are a shared global counter across concurrent sessions. If the brief gave you no number, or the number it gave you already exists anywhere in that listing, stop and ask before writing the file.

### 5. Verify before claiming success

Run the suite and report the real numbers:

```bash
npm test
npm run eval:retrieval   # when retrieval, scoring, or embeddings were touched
```

If tests fail, say so with the failing output. Do not describe partial work as done. If the work turns out to be bigger than one issue, release the lease and say what you found — an honest release beats a half-finished branch.

**Claim only what you actually exercised.** Each of these is the difference between a true statement and a false one a reviewer will act on:

- An **unapplied migration is not a tested migration**. Say "migration written, not applied" until it has run.
- **Mocked coverage is not integration coverage**. Name the mock.
- **A skipped suite is not a passing suite**. Report skips with the counts.
- Bound the claim to what you ran: "verified against PGlite with a non-superuser role" is accurate; "RLS verified" is not.
- If you added code with no tests, say the line count and say so. Nobody discovers it later without a diff.

### 6. Open a pull request, never merge

```bash
gh pr create --repo AnsweringRND/answering \
  --title "<what changed, in behavior terms>" \
  --body "Closes AnsweringRND/tracker#<n>

## What changed
...
## Verification
<real test output, with skips and gaps named>
## Evidence checked
<any path:line in the prompt that had drifted, old -> new>
## Deferred
<any question from 'Decisions needed from Carson' your brief excluded from scope>"
```

`gh` and the push both need `dangerouslyDisableSandbox: true`, and `git push` needs Carson's authorization for the `pre-push` override — see guard 2.

**If Carson has not authorized a push in this session, this is where you stop, and stopping here is success.** Commit the work locally, leave the branch unpushed, and report: the branch name, the commit sha, the test results, and the sentence "awaits push authorization from Carson — `pre-push` reserves this for him." Then release the lease with that reason (`/home/schmi/projs/.claude/skills/solve-issues/tracker.sh release <issue> "$TOKEN" "agent/issue-<n> committed locally, awaits push authorization"`) so nothing is held invisibly. There is no PR yet, so there is nothing to `finish` and nowhere to post a brief; the local branch and the report are the deliverable. Do not set `CORNEA_GIT_OK=1` to make the checklist below turn green.

**Never merge.** The issue stays open until a human merges the pull request. One agent opening a pull request is useful; one agent merging to main unattended is how a bad change reaches everything.

**Do not run `tracker.sh finish`.** If you were dispatched, closing the lease is not yours to do — see step 7.

If a message arrived while you were working, say so in your report with the time you received it and the time you committed (`git log -1 --format=%cI HEAD`). Do not act as though it never arrived, and do not assume it retroactively binds work already committed.

### 7. Report, and stop. You do not close your own lease.

**If you were dispatched by an orchestrator, you never run `tracker.sh finish`.** Your ending is: the PR exists, and you have reported its URL, your real test numbers, and anything you could not exercise. That is a complete ending — you are not abandoning the issue by stopping there.

The lease close belongs to whoever dispatched you, and it happens only after the reviewer brief exists. That ordering is the whole mechanism: `finish` is the machine-readable "done" signal the tracker and the orchestrator both read, and last run three of five workers ran it, sent their report, and went idle with the brief never written. A finished lease with no brief is invisible to everyone; an open one is at least visible in `tracker.sh stale`.

**The reviewer brief is requested as its own turn**, after the PR lands. Do not write it unless you are asked. The six required sections live in [orchestrator.md](orchestrator.md); the request will quote them. When asked, write it to a file, post it, and reply with the URL:

```bash
gh pr comment <n> --repo AnsweringRND/answering -F brief.md
```

Exception, and only this one: if nobody dispatched you — Carson invoked this skill directly — then you are your own orchestrator. Write the brief now, then close your own lease with both links:

```bash
/home/schmi/projs/.claude/skills/solve-issues/tracker.sh finish <issue> "$TOKEN" "<pr-url> — brief: <brief-comment-url>"
```

The brief is the highest-value artifact of the run, which is why it gates the signal rather than trailing it. Last run's briefs surfaced a 0.8 false-answer rate under the real production gate that CI structurally cannot see, an unrelated fix buried inside a PR, 291 lines with no unit tests, and the exact boundary of an unproven security claim — none of which a diff review would have found, because only the author knows what they did not do.

### 8. Then the next one

One issue at a time per session. Loop back to step 2.

Do not fan out across several issues in parallel from a single session: they would share the worktree parent, compete for the same `npm install`, and make failures impossible to attribute. `tracker.sh claim` refuses this outright (exit 2). Parallelism comes from **multiple sessions**, each with its own token — which is exactly what the lease makes safe.

## Releasing

Releasing applies when you stop **before a pull request exists**. If your PR is open and you have reported it, do nothing further — the lease close is the orchestrator's, and releasing a PR-bearing issue would put live work back on the frontier for another session to duplicate.

Otherwise, any exit must release, or the issue stays invisibly locked:

```bash
/home/schmi/projs/.claude/skills/solve-issues/tracker.sh release <issue> "$TOKEN" "blocked on X"
```

Release when: the prompt's premise turns out to be stale, no pickup prompt exists for the issue, the prompt raises a founder decision your brief did not clear, the scope is bigger than one issue, the branch is done but awaits push authorization, or you are stopping for any other reason. Releasing is normal and cheap. A silently held lease is not.

## Reporting back

After each issue, tell Carson in one short block: the issue, what changed, the test result, the pull request link (or the unpushed branch name and what it awaits), and the brief comment link once it exists. After the run, list what was completed, what was released and why, and what is left on the frontier.

## Before you go idle, verify

- Every lease is either finished or released — nothing is silently held.
- You have reached exactly one of these four complete endings, and none of them is a failure:
  1. **PR open and reported** — `gh pr list --repo AnsweringRND/answering --head agent/issue-<n> --json url` resolves, and your report carries the URL, real test numbers, and anything you could not exercise. The lease stays open; closing it is the orchestrator's, after the brief.
  2. **Committed locally, unpushed** — Carson had not authorized a push. Released with that reason, and your report says it awaits his authorization.
  3. **Released at step 3** — the pickup prompt was missing, or its open questions gate what gets built, so no branch was ever created.
  4. **Released mid-work** — stale premise, or scope larger than one issue, with the reason stated.
- Every number in your report came from a command you ran, and every gap in step 5's list that applies to you is stated.
- You used no override that a hook reserves for Carson without Carson having said yes in this session.

---
name: day-plan
description: Day plan — today's meetings, what slipped since yesterday, the top three to move, and who's blocking — posted to Slack. Use when the user says "/day-plan", "plan my day", or "what should I work on today".
---

# day-plan

Answers one question every morning: **what are Carson and Carson actually working
on today, and what changed since yesterday's answer.**

Repo: the repo root (current checkout). Read `core/DOCTRINE.md` first.

When *when* this runs is in question — launchd on this machine versus a cloud
routine — that decision and its tradeoffs live in `SCHEDULING.md` at the repo
root.

## Run

### 1. Gather

In parallel:

- **Calendar** — `mcp__claude_ai_Google_Calendar__list_events` for today. Note
  anything that needs prep, and any block of ≥2 free hours (that's where the top
  item goes).
- **Gmail** — `mcp__claude_ai_Gmail__search_threads` for `is:unread newer_than:2d`
  and for `newer_than:7d in:inbox -from:me`. Keep a thread only when someone is
  blocked on Carson, tested this way: the newest message in the thread is from
  someone else, it asks Carson for a decision, review, file, or approval, and Carson
  has not replied since. Everything else is general unread — leave it out.
- **Open items** — read `~/.claude/skills/open-items/items.json`; it is the task
  tracker. Where that path is absent — a checkout without Carson's home directory —
  read `state/open-items-snapshot.json` instead, date it with
  `git log -1 --format=%cs -- state/open-items-snapshot.json`, and say in the
  post that open items are as of that date. Sections map straight through in
  either file: `you` → actionable, `blocked` → waiting, `idea` → ignore in the
  day plan.
- **Local repo state** — which branch runs is decided by whether `~/projs`
  exists on this host.

  *Local run — `~/projs` exists.* Sweep every repo under it:

  ```bash
  for d in ~/projs/*/; do
    [ -d "$d/.git" ] || continue
    printf '%s: ' "$(basename "$d")"
    git -C "$d" log --oneline --since=yesterday.midnight | wc -l | tr -d ' '
    git -C "$d" status --porcelain=v1 | head -3
    git -C "$d" branch --format='%(refname:short) %(upstream:track)' | grep -v '^main ' | head -5
  done
  ```

  *Bare checkout — no `~/projs`.* Carson's other repos are not cloned here, so
  cover this repo alone and carry the gap into step 4 as a skipped lane rather
  than guessing at the rest:

  ```bash
  cd "$(git rev-parse --show-toplevel)"
  git log --oneline --since=yesterday.midnight | wc -l | tr -d ' '
  git status --porcelain=v1 | head -3
  git branch --format='%(refname:short) %(upstream:track)' | grep -v '^main ' | head -5
  ```

  Unmerged branches with commits and no PR are the classic slipped item. The
  lane is done when one of the two branches has run and the post carries which.

### 2. Diff against yesterday

Build one observation per candidate work item, id = the open-items id, calendar
event id, or `<repo>/<branch>`. Carry the same field set across all three
sources, and omit a field entirely rather than guessing it — a field that flips
between a guess and a real value manufactures a fake change event:

```json
[
  {"id": "slack-tokens", "name": "Create Slack app + tokens for slack-bot",
   "status": "actionable", "source": "open-items", "blocker": null},
  {"id": "<google calendar event id>", "name": "Design partner call — Acme",
   "status": "scheduled", "source": "calendar"},
  {"id": "meeting-copilot/fix-warm-cache", "name": "warm-cache fix, 3 commits, no PR",
   "status": "actionable", "source": "repo", "blocker": null}
]
```

Write that array to `state/day-plan-observations.json` at the repo root (shell
variables do not survive between Bash calls, so the JSON travels through a file,
not an `echo`), then diff it:

```bash
cd "$(git rev-parse --show-toplevel)"
cat state/day-plan-observations.json | python3 bin/delta.py day-plan
```

The delta answers the question that makes this worth reading: **what slipped.**
Age lives in state, not in the observation: for each item still `actionable`,
read its `_first_seen` stamp from `state/day-plan.json` and count the days to
today. An item carried for days while `status` stays `actionable` is the thing
to call out — that's the signal a plain to-do list never gives.

### 3. Pick the top three

Not the three oldest and not the three easiest. Rank by:

1. Unblocks another person (Carson, a design partner, an agent fleet)
2. Blocks the most other work downstream
3. Has a real deadline
4. Has been slipping longest

Name **three**.

### 4. Post

Slack `#daily-updates` (`C0BKPEEE2TG`), headed `*Day plan* — <YYYY-MM-DD, weekday>`.
Send with `slack_send_message`, resolving its live MCP prefix from the loaded
tools — `mcp__plugin_slack_slack__*` is the common case; if it is absent, search
the loaded tools for `slack send message` and use the prefix this session
exposes.

```
*Meetings* — <count>, <first> at <time>. <prep needed, or "no prep">
*Free block* — <largest contiguous gap>

*Top 3*
1. *<item>* — <why it's #1 today>
2. ...
3. ...

*Slipped* — <items whose age climbed with no movement, with day counts>
*Waiting on others* — <blocked items + who>
```

This template is day-plan's rendering of doctrine §5's output contract: the
header follows §5, and the delta from step 2 feeds the *Slipped* and *Waiting on
others* lines rather than being pasted in as a raw delta body.

When step 1 took the bare-checkout branch, close the post with
`_repo lane: <repo> only — Carson's other repos are not cloned on this host_`, so a
short plan reads as thin coverage rather than a quiet day.

If nothing slipped and the top 3 are unchanged from yesterday, say so in one
line rather than restating them — per doctrine §1.

### 5. Persist

Write `reports/day-plan-<YYYY-MM-DD>.md`, then commit per doctrine §6.

## Do not

- Do not invent work. If open-items is empty and no repo has an unmerged branch,
  the honest output is "nothing queued — pick something from ideas or ship what's
  in review."
- Do not restate the full open-items list. That artifact already exists at
  `/open-items`; link to it instead.

---
name: skill-sync
description: Sync new or updated skills, agents and hooks into the CortexRND/skills share repo and push. Use right after creating or materially changing a skill, agent or hook; when Taj says "sync skills" or "push the skills repo"; or when checking whether the cortex-brief trio (day-plan, daily-brief, comp-watch) has drifted between its two copies.
---

# skill-sync

`sync.sh` does every copy, guard and push. Run it instead of hand-typing `cp`/`git` — the hand-typed ritual is what this skill retires, and a skill that never reaches `/Users/taj/projs/skills` exists on this laptop only.

## Sync

1. Run the script over what changed:

```bash
bash /Users/taj/.claude/skills/skill-sync/sync.sh <name>... [-m "commit message"]
```

`<name>` is a skill directory name, an agent file name, or a hook script name; the script finds which source root holds each one and routes it to `skills/`, `agents/`, `hooks/` or `statusline/` in the share repo. Pass `--all-changed` instead of names when you are unsure what moved — an rsync content diff picks the set. Default commit message is `skill sync`.

Done when the script prints `pushed=<sha> items=<n> branch=main`, or `no-change head=<sha>` when the sources already match the repo. Any other exit: see the exit-code section below.

2. Confirm the push landed, from outside the script:

```bash
git -C /Users/taj/projs/skills status -sb | head -1
```

Done when that line reads `## main...origin/main` with no `[ahead N]` marker.

3. Report to Taj: the short hash from step 1, the count, and the item names the script listed under it.

Done when every name the script printed appears in your reply and the hash matches step 2's repo.

## Trio check only

`day-plan`, `daily-brief` and `comp-watch` live at both `/Users/taj/.claude/skills/<name>` and `/Users/taj/projs/cortex-brief/.claude/skills/<name>` and must stay byte-identical. To answer "have those copies drifted?" without touching git:

```bash
bash /Users/taj/.claude/skills/skill-sync/sync.sh --check-trio
```

Done when it prints `trio identical=3`, or exits 1 having named each differing file.

## When sync.sh exits nonzero

- **1** — `--check-trio` found drift. Report the named files; resolution is the exit-3 case below.
- **2** — refused. The message names the offender: runtime state in the repo, an unknown or ambiguous name, or a share repo pointing at the wrong remote or branch. Fix that one thing and rerun.
- **3** — trio drift blocks the sync. Show Taj the diff and ask which side is authoritative; overwriting one copy of a mirrored pair is his call, not yours. Then rerun step 1.
- **4** — the commit did not reach origin, because origin holds commits this checkout lacks. Show Taj `git -C /Users/taj/projs/skills log --oneline HEAD..origin/main` and ask before rebasing, merging or forcing anything.

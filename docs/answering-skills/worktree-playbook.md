# Agent Worktree Playbook

**Date:** 2026-08-02 · **Author:** Carson (audit run by a 4-agent team: session-log mining, repo sweep, doctrine grep, worktree triage; PR states verified against GitHub)

How we use git worktrees for agent work today, what the audit found, and the instructions going forward.

## What the audit measured

- **Usage is heavy and rising.** 75 `git worktree add` across 11 sessions since 2026-07-01, versus 10 removes and 4 prunes. The worktree-per-agent-spawn ratio rose from 0.25 (Jul 25) to ~1.0 (Aug 1). Dominant pattern: hand-rolled `git worktree add projs/.worktrees/<name> -b agent/<name>` per issue.
- **The `isolation: 'worktree'` Agent flag has 2 real uses ever.** Everything else takes the hand-rolled path, even one-off interactive writers where the flag's auto-cleanup would solve GC for free.
- **19 worktrees on disk, ~2 GB.** 1.8 GB of that is 10 duplicate npm `node_modules` trees in answering worktrees.
- **The pileup is review debt, not hygiene debt.** Verified against GitHub: 10 of 12 answering worktrees back open PRs (#1–#13). Only `issue-18-pushsync` was actually dead (merged, clean, 141 MB). meeting-copilot's 5 worktrees have sat unreviewed since Jul 24.
- **Setup and cleanup rules exist only as prose.** The "`npm install` inside the worktree is non-optional" rule appears in 3 skills (`team-orchestration`, `solve-issues`, `branch-verdict`) and is enforced by nothing. The warning sentence has been re-pasted into ~204 prompts — a permanent prompt tax paying for 1 historical incident. Cleanup is human-gated in loop-doctrine's ledger only; solve-issues fleets register nothing (tracker #37 exists because of this).
- **Near-miss:** renaming a repo would have silently broken every open worktree's `.git` gitdir pointer. Caught by audit before execution.

## Instructions

### 1. Spawn through one script, never by hand

`worktree-spawn <repo> <name>` must: `git worktree add` + `npm install` inside the worktree + assert `node_modules` exists at the worktree root, exiting nonzero otherwise, and register a cleanup claim (see #6). This replaces the 3 prose rules and every pasted warning with a mechanism. Node resolves `node_modules` upward, so a worktree without its own install silently runs the main checkout's code and reports green — the guard must be mechanical, not remembered.

Pair it with a pre-test guard: test-running agents (`test-triage`, `branch-verdict`) refuse to run a suite in a worktree missing `node_modules` at its root.

### 2. Garbage-collect on PR state, not git ancestry

Squash merges make `git branch --merged` lie: a squash-merged branch shows unmerged commits forever. GC rule: a worktree dies when `gh pr view <branch>` reports MERGED or CLOSED **and** the tree is clean. Anything else stays. Run the GC script per repo in the daily plan or via launchd.

### 3. Use pnpm for fleet repos

A 12-worktree fleet under npm means 12 full `node_modules` copies (our 1.8 GB). pnpm's content-addressed store makes each worktree install near-instant and near-free on disk. Migrate answering first; it is where fleets run.

### 4. Two workflows, chosen on purpose

- **Interactive, single writing agent:** use the Agent tool's `isolation: 'worktree'` flag. It auto-cleans if unchanged. Its only real failure mode (loud error outside a git repo) does not apply to our repos.
- **Fleets and loop/overnight runs:** hand-rolled pinned worktrees with explicit commit pathspecs, per loop-doctrine. These must survive session ends, so the flag is wrong for them.

Everything currently takes the second path; most interactive work belongs on the first.

### 5. Worktrees live inside their repo

Use `<repo>/.worktrees/`, not the shared flat `projs/.worktrees/`. The flat dir mixes worktrees from different repos (answering and meeting-copilot today), makes the sibling-collision check in solve-issues harder, and hides the repo↔worktree coupling that made the rename near-miss possible. Never rename or move a repo while it has open worktrees.

### 6. Every add registers its cleanup

Creation and cleanup-registration are one atomic step inside `worktree-spawn` (ledger claim `cleanup-worktree:<name>`, matching loop-doctrine). A worktree with no registered cleanup is a bug, not a convenience.

## Immediate actions

- Remove `issue-18-pushsync` (merged, clean, frees 141 MB).
- Commit or discard the dirty `docs/vision/understand-the-answering-vision.md` in `fix-vision-overclaim`, then remove that worktree.
- The real backlog is PR review: 10 open answering PRs and 5 meeting-copilot branches from Jul 24 are what is keeping 18 of 19 worktrees alive.

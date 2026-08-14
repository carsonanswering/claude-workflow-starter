---
name: open-items
description: Regenerates the phone-viewable Open Items artifact from the locally curated items.json — actions waiting on Carson, ready-to-pick-up work, ideas, blocked items (GitHub tracker labels live in tracker-refresh).
disable-model-invocation: true
---

# open-items — trackable list, one artifact, phone-viewable

Artifact URL is permanent (state.json). Check-offs on the page are per-device
localStorage — refresh regenerates list, prunes done ids no longer present.

## Refresh flow (default, cheap)

1. Update `~/.claude/skills/open-items/items.json` ONLY if this session learned
   changes (item finished, new blocker, new task). Edit surgically; keep ids
   stable — id churn wipes the user's phone check-offs. A finished item gets its
   entry deleted, not retitled "DONE …": the page renders every entry as live, so
   retitled entries accumulate forever (the history belongs in `/obsidian-log`).
   Schema — this block is the source of truth; `refresh.py` fills `updatedAt`:
   `{"items": [{"id": "kebab-slug", "title", "section": "you|ready|idea|blocked",
   "repo", "note", "effort": "S|M|L", "blocker", "prompt": "<pickup prompt path>"}]}`
   Sections: `you` = needs Carson personally (pushes, tokens, decisions);
   `ready` = unblocked work an agent can start; `idea` = candidate projects;
   `blocked` = waiting on external.
2. `python3 ~/.claude/skills/open-items/refresh.py` — prints summary + url.
3. Artifact tool: publish the printed `out` path, pass `url` from output,
   favicon `📋`, keep the existing title and description. If UNSET, publish fresh
   then save URL into state.json.
4. Reply: summary line + link. Do not describe the page.

## Rescan flow (user asks "rescan" / list feels stale)

Spawn ONE `caveman:cavecrew-investigator` (haiku) to sweep git repos under
~/projs (unmerged branches, dirty trees, ahead-of-remote) + memory index
`/Users/kai/.claude/projects/-home-schmi-projs/memory/MEMORY.md`; diff its
findings against items.json, apply updates, then Refresh flow. The sweep is done
when every repo carrying an unmerged branch, a dirty tree, or unpushed commits is
either represented by an item or explicitly judged not worth one — say which in
the reply. Keep the sweep inside that agent so the frontier session pays only for
the diff. New pickup prompts go through the `prompt-engineer` agent into
`/Users/kai/projs/prompts/open-tasks/` (CLAUDE.md rule).

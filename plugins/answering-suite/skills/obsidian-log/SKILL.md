---
name: obsidian-log
description: Writes a structured note summarizing the current session into the Obsidian vault's Claude Sessions folder.
disable-model-invocation: true
---

# Obsidian Session Log

Write a structured note summarizing the current session into the Obsidian vault.

The SessionEnd hook (`~/.claude/hooks/session-obsidian-log.py`) auto-logs sessions it judges valuable in this same format; this skill is the on-demand path, and the skeleton below is the format's single source of truth.

## Vault location

Vault: `~/Documents/ObsidianVault`
Notes folder: `~/Documents/ObsidianVault/Claude Sessions/` — a symlink to `/home/schmi/projs/session-logs/`, so either path writes the same file.

Write the note with the Write tool: it creates missing parent directories, and `~/Documents` sits outside the Bash write allowlist (`mkdir -p` there returns "Operation not permitted").

## Filename

`<YYYY-MM-DD> <short-title>.md` — today's date plus a 2-5 word title describing the session (e.g. `2026-07-12 Fix auth middleware.md`). If a note with that exact name already exists, append ` (2)`, ` (3)`, etc.

## Note structure

Write the note with this exact skeleton. Omit any section that would be empty rather than leaving placeholder text. Write section content in normal prose (not caveman/compressed style) — the note is a permanent record read later without session context.

```markdown
---
date: <YYYY-MM-DD>
time: <HH:MM local, from `date +%H:%M`>
project: <working directory basename, e.g. projs>
session: <session id, if known — the hook fills this automatically>
tags:
  - claude-session
  - <1-3 topic tags, lowercase-kebab, e.g. refactoring, debugging, infra>
tools: [<notable tools/tech touched, e.g. git, docker, python>]
status: <completed | in-progress | blocked>
---

# <Session title>

## Objective
<1-2 sentences: what the user asked for.>

## Summary
<Short prose narrative of what happened: approach taken, what worked, what was abandoned and why. 3-8 sentences.>

## Key decisions
- <decision> — <why>

## Files changed
| File | Change |
|------|--------|
| `path/to/file` | <one-line description> |

## Commands & findings
- <important command or discovery worth remembering, with outcome>

## Open items / next steps
- [ ] <unfinished work or follow-up>

## Related
- [[<wikilink to related note if an obvious one exists in Claude Sessions/>]]
```

## Rules

1. **Summarize from the actual conversation**: only include files, commands, and decisions that actually occurred in this session.
2. **Files changed**: list only files created/edited/deleted this session. Skip scratchpad/temp files.
3. **Commands & findings**: include only decisive commands and results — the shortest set someone would need to reconstruct the key learnings. Not a full transcript.
4. **Status**: `completed` if the session's main task finished, `in-progress` if work remains, `blocked` if waiting on the user or an external factor.
5. **Wikilinks**: before writing, `ls` the `Claude Sessions/` folder; if a prior note clearly relates (same project/topic), link it under Related. Otherwise omit the section.
6. **Secrets**: never write API keys, tokens, passwords, or email contents into the note. Redact as `<redacted>` if they came up.
7. **Index**: after writing the note, add one line `- [[<note name>]]` under the matching date section in `/home/schmi/projs/session-logs/Claude Sessions Index.md` (newest date section first; create the date section if missing). If that file is absent, create it with the title line `# Claude Sessions Index` and the date section under it — the same file and title the hook uses, so both writers keep one index.
8. After writing, confirm to the user with the full note path.

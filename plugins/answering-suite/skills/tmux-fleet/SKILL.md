---
name: tmux-fleet
description: Launch a fleet of parallel Claude Code panes in one tiled tmux session.
disable-model-invocation: true
---

# tmux-fleet — parallel Claude panes, one tmux session

1. Run the script, translating what Carson asked for into flags. Every flag is optional; the defaults are 3 panes, session `fleet`, permission mode `default`, and the current directory.

```bash
bash ~/.claude/skills/tmux-fleet/fleet.sh [-n panes] [-s session-name] [-m default|plan|acceptEdits|bypassPermissions] [-f prompts-file] [dir]
```

To seed the panes with work, write the prompts one per line to a file in the target repo or under `~/` — keep it outside this skill folder, which holds no run state — and pass it with `-f`. Line k becomes pane k's `claude -p` prompt; a blank line k leaves pane k interactive, as does any pane past the last line. Done when the script exits 0 and its final line is `tmux attach -t <name>`.

2. Reply with the script's summary lines and nothing else, the attach command last. Done when Carson has that command verbatim.

Exit 1 means a session of that name already exists and the script changed nothing. Relay its message and ask Carson which he wants: attach to the running session, or rerun with `-s <other-name>`. Killing the existing one is his call — it would end whatever those panes are doing.

## What the panes are

Each pane is a full, independent Claude Code session. They share this machine's Claude auth, share no context with each other or with you, and each one bills separately — so a 6-pane fleet is 6 sessions' worth of spend. `tmux kill-session -t <name>` ends the whole fleet in one command; ask Carson before running it, for the same reason.

# Setup: Orca and tmux

The `orchestration` and `orca-cli` skills require the Orca app; `tmux-fleet` and
split-pane agent teams require tmux. This page gets both working on this machine
(Windows + WSL2). macOS notes included where they differ.

## Orca (onorca.dev)

Orca is the free, MIT-licensed Agent Development Environment from
[onorca.dev](https://www.onorca.dev/) — it runs multiple coding agents (Claude
Code, Codex, Cursor CLI, ...) side by side, each in its own git worktree.

### Install

- **Windows**: download the installer from the
  [download page](https://www.onorca.dev/) (builds hosted on GitHub Releases)
  and run it. Default shell (PowerShell or CMD) is set under
  **Settings → Terminal**.
- **macOS**: `brew install --cask stablyai/orca/orca` (update later with
  `brew upgrade --cask orca`), or grab the DMG for your architecture.
- **Linux**: AppImage or `.deb` from GitHub Releases.

### First run

1. Grant Orca directory access so it can manage your repositories.
2. Optionally import existing terminal/agent configuration.
3. Add this repo as your first repository, then follow the docs'
   ["Your first 3-agent session"](https://www.onorca.dev/docs/first-session).
4. Point it at your agent CLIs — Orca uses your own Claude Code login; install
   and authenticate `claude` first (`install.sh` in this repo does that).

### CLI resolution (what the skills expect)

The `orca-cli` and `orchestration` skills resolve the executable in this order —
they never guess:

1. `ORCA_CLI_COMMAND` env var, if set (Orca exports this in managed WSL
   sessions — so inside an Orca-opened WSL terminal it Just Works).
2. `orca-dev` in a dev checkout (`ORCA_DEV_REPO_ROOT` set).
3. `orca-ide` on Linux outside an Orca-managed terminal — never bare `orca`
   there, which is the GNOME screen reader.
4. `orca` otherwise.

Verify from a terminal Orca manages:

```bash
"$ORCA_CLI_COMMAND" status --json     # app up?
"$ORCA_CLI_COMMAND" skills get orca-cli   # prints the full version-matched CLI guide
```

The skills are discovery stubs on purpose; the binary serves the real,
version-matched command reference via `skills get`.

## tmux

Needed by the `tmux-fleet` skill (parallel Claude panes) and by split-pane agent
teams (`--teammate-mode tmux`).

### Install

```bash
# WSL / Debian / Ubuntu
sudo apt update && sudo apt install -y tmux

# macOS
brew install tmux
```

Verify: `tmux -V`.

### Wire up tmux-fleet

`tmux-fleet` runs its script from `~/.claude/skills/tmux-fleet/fleet.sh`, so the
skills must be installed user-wide (the plugin path alone is not enough for the
script invocation):

```bash
./install.sh --user-wide
```

Then launch a fleet:

```bash
bash ~/.claude/skills/tmux-fleet/fleet.sh -n 3 -s fleet
tmux attach -t fleet
```

Each pane is a full independent Claude Code session billing separately.
`tmux kill-session -t fleet` ends the whole fleet.

### Split-pane agent teams

```bash
./install.sh --teammate-mode tmux     # writes teammateMode into ~/.claude/settings.json
```

Then start `claude` from inside a tmux session; teammates open as tiled panes.
Outside tmux, teams still work in-process (`--teammate-mode auto` picks for
you; on macOS iTerm2 is also supported).

### tmux survival kit

- `Ctrl-b d` detach (fleet keeps running) · `tmux attach -t <name>` reattach
- `Ctrl-b` + arrow keys to move between panes · `Ctrl-b z` zoom a pane
- `tmux ls` list sessions · `tmux kill-session -t <name>` end one

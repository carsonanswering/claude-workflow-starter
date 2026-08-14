# Setup: the Mac mini agent workstation

This machine (`Kais-Mac-mini`, macOS 26.3, arm64) is the designated multi-agent
workstation. This page records how it is wired and how to reproduce it.

Deployed 2026-08-14. Original suite was authored on a Linux host; paths were
retargeted from `/home/schmi` to `/Users/kai` as part of this deployment.

## What's installed

| Piece | Version / location | Notes |
|---|---|---|
| Claude Code | 2.1.232 | `~/.local/bin/claude` |
| Skills | 32 in `~/.claude/skills` | source of truth — see below |
| Subagents | 11 in `~/.claude/agents` | 8 suite + 3 suite-native |
| Orca | `/Applications/Orca.app` | CLI at `Contents/Resources/bin/orca` |
| tmux | 3.7b (Homebrew) | config in `setup/macmini/tmux.conf` |
| Tailscale | 1.102.2 (Homebrew formula) | system daemon, not the GUI app |
| uv | 0.12.4 | drives `apps/ai-employees` (Python 3.14.7) |
| node / npm | 26.7.0 / 11.19.0 | |
| gh | 2.97.0, authed as `carsonanswering` | scopes: `gist`, `read:org`, `repo` |

## Skills: one source of truth

Skills live **user-wide** in `~/.claude/skills`, installed by
`./install.sh --user-wide`. The `answering-suite` plugin is deliberately **not**
installed, even though the marketplace stays registered.

Why: installing both put every model-invocable skill in the session list twice
(once bare, once as `answering-suite:<name>`) — 24 duplicates. Beyond the wasted
context, several skills hardcode `~/.claude/skills/...` paths for their own
scripts (`tmux-fleet/fleet.sh`, `skill-sync/sync.sh`, `solve-issues/tracker.sh`,
`tracker-refresh/refresh.sh`), so the user-wide copy is the one that has to
exist. The plugin was the redundant half.

`~/Desktop/projs/.claude/skills` and `~/Desktop/projs/.claude/agents` are symlinks into
`~/.claude`, so project-scoped lookups resolve to the same files.

**After editing skills in this repo, re-run `./install.sh --user-wide`.** The
`~/.claude` copies do not update themselves — during this deployment 25 files
went stale exactly that way.

To go back to the plugin instead:

```bash
claude plugin install answering-suite@answering-workflows
rm -rf ~/.claude/skills   # otherwise you get the duplicates back
```

### Slash-only skills

Eight skills carry `disable-model-invocation: true`, so they never appear in the
model's skill list and only run when you type them: `meeting-notes-sync`,
`open-items`, `obsidian-log`, `oss-session`, `running-view`, `slack-insights`,
`tmux-fleet`, `tracker-refresh`. A session reporting 24 visible suite skills
rather than 32 is correct, not broken.

## Doctrine scope

Skills are user-wide, so every session gets the *tools*. The orchestration
*doctrine* is a separate question: a `CLAUDE.md` inside this repo only loads for
sessions whose working directory is inside it, which excludes most Orca
worktrees and any bare ssh session.

So the doctrine lives in **`~/.claude/CLAUDE.md`** — user memory, loaded in every
session on this machine. This repo's `CLAUDE.md` keeps only repo-specific
additions and does not duplicate it.

The trade-off is deliberate: the doctrine now costs context in every session,
including unrelated work. If that becomes a problem, cut `~/.claude/CLAUDE.md`
back to the "Machine layout" section and move the orchestration rules into
per-repo `CLAUDE.md` files.

Verified: an Orca-spawned terminal is a login zsh (`-/bin/zsh`), so `~/.zshenv`
applies and Orca sessions report `ORCA_CLI_COMMAND` set,
`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, and all 32 skills.

## Shell environment

`~/.zshenv` (not `.zshrc`) holds the environment, because `ssh host <command>`
runs a non-interactive shell that sources only `.zshenv`. It sets Homebrew's
path, `~/.local/bin`, `ORCA_CLI_COMMAND`, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`,
and `WORKFLOW_REPO`.

`~/.zshrc` adds two interactive helpers:

- `agents` — attach to (or create) the persistent `agents` tmux session
- `fleet [-n N]` — launch N parallel Claude panes via `tmux-fleet`

## Orca (onorca.dev)

Orca is the MIT-licensed Agent Development Environment from
[onorca.dev](https://www.onorca.dev/): it runs multiple coding agents side by
side, each in its own git worktree. It was already installed here; the app and
runtime report `ready`.

The `orca-cli` and `orchestration` skills resolve the executable in a fixed
order and never guess. `~/.zshenv` sets the first entry:

```sh
ORCA_CLI_COMMAND=/Applications/Orca.app/Contents/Resources/bin/orca
```

There is also a `~/.local/bin/orca` symlink so bare `orca` works. (The
"never run bare `orca` on Linux" warning in the skill is about the GNOME screen
reader — not a concern on macOS, but the env var is set anyway so the skill's
documented resolution order is satisfied.)

Verify:

```bash
"$ORCA_CLI_COMMAND" status --json        # app + runtime + graph readiness
"$ORCA_CLI_COMMAND" skills get orca-cli  # full version-matched CLI guide
```

The suite's `orca-cli`/`orchestration` skills are discovery stubs on purpose —
the binary serves the real reference via `skills get`, so it can't drift from
the build that will actually run the commands.

**Do not run `orca skills install`.** Orca bundles its own `orca-cli` and
`orchestration` skill guides, which collide by name with the suite's stubs.

## tmux

Config lives at `setup/macmini/tmux.conf`, deployed to `~/.tmux.conf`. Choices
that matter for agent work: `escape-time 10` (the 500ms default makes Claude
Code's TUI feel broken), truecolor overrides, 50k-line scrollback per pane, and
`detach-on-destroy off` so detaching never kills the session.

Survival kit: `Ctrl-b d` detach · `Ctrl-b` + arrows to move · `Ctrl-b z` zoom ·
`tmux ls` · `tmux kill-session -t <name>` · `Ctrl-b r` reload config.

### Fleets

```bash
fleet -n 3 -s myfleet            # or: bash ~/.claude/skills/tmux-fleet/fleet.sh
tmux attach -t myfleet
```

Each pane is a full independent Claude Code session **billing separately**.

### Split-pane agent teams

`teammateMode` is set to `tmux` in `~/.claude/settings.json`. Start `claude`
from inside a tmux session and teammates open as tiled panes; outside tmux they
still work in-process.

## SSH + Tailscale

Reachability model: **Tailscale, keys only.** The Homebrew formula (system
daemon) is used rather than the GUI app, because the daemon comes up on boot
without anyone logging into the desktop — a headless box whose VPN needs a GUI
login is a box you can't reach after a reboot.

A dedicated keypair was generated at `~/.ssh/id_ed25519_macmini` and its public
half added to `~/.ssh/authorized_keys`.

Run the three steps in order — `harden` disables password auth, so proving a key
login first is what keeps you from locking yourself out:

```bash
cd ~/claude-workflow-starter/setup/macmini
sudo ./bootstrap-remote.sh enable     # Remote Login + tailscaled + tmux.conf
sudo tailscale up --ssh=false         # prints a URL; approve the machine
./bootstrap-remote.sh verify          # proves key auth works
sudo ./bootstrap-remote.sh harden     # keys only, after verify passes
```

Then, from a client on the tailnet:

```bash
scp kai@kais-mac-mini.local:~/.ssh/id_ed25519_macmini ~/.ssh/
ssh -i ~/.ssh/id_ed25519_macmini kai@<tailscale-name> -t agents
```

The trailing `-t agents` attaches straight into the persistent tmux session, so
a dropped connection leaves the agents running.

## Known gaps on this machine

These skills load but fail at their dependency, not at a path:

- `fw-delegate` — no `fw` CLI (Answering-internal)
- `pi-delegate` — no `~/.pi` agent harness (Answering-internal)
- `lightning`, `local-delegate` — expect a `lo` CLI
- `carson-update`, `slack-insights`, `comp-watch` — need a Slack MCP connection
- `daily-brief`, `meeting-notes-sync` — need Google Workspace MCPs

`~/Desktop/projs` and `~/Documents/ObsidianVault` were created with the directory
structure the skills reference. Individual project checkouts under `~/Desktop/projs`
(`answering`, `answering-gtm`, `tracker-live`, ...) are **not** pre-seeded —
clone them as needed.

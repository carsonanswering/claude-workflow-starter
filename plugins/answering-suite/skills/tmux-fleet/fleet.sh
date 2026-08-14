#!/bin/bash
# tmux-fleet — launch N parallel Claude Code panes in one tiled tmux session.
# usage: fleet.sh [-n panes] [-s session-name] [-m permission-mode] [-f prompts-file] [dir]
# Needs tmux >= 3.2 for `-e` on new-session/split-window (installed here: 3.7b).
set -euo pipefail

N=3
SESSION=fleet
MODE=default
PROMPTS_FILE=""

usage() {
  cat >&2 <<'EOF'
usage: fleet.sh [-n panes] [-s session-name] [-m permission-mode] [-f prompts-file] [dir]
  -n  panes, 1-9                                    (default 3)
  -s  tmux session name                             (default fleet)
  -m  default|plan|acceptEdits|bypassPermissions    (default default)
  -f  prompts file: line k is pane k's prompt; a blank line k = interactive pane
  dir working directory for every pane              (default: cwd)
EOF
}

while getopts ":n:s:m:f:h" opt; do
  case "$opt" in
    n) N=$OPTARG ;;
    s) SESSION=$OPTARG ;;
    m) MODE=$OPTARG ;;
    f) PROMPTS_FILE=$OPTARG ;;
    h) usage; exit 0 ;;
    \?) echo "fleet.sh: unknown option -$OPTARG" >&2; usage; exit 2 ;;
    :)  echo "fleet.sh: -$OPTARG needs a value" >&2; usage; exit 2 ;;
  esac
done
shift $((OPTIND - 1))
DIR=${1:-$PWD}

command -v tmux >/dev/null 2>&1 || { echo "fleet.sh: tmux not found in PATH" >&2; exit 2; }
command -v claude >/dev/null 2>&1 || echo "fleet.sh: note - 'claude' is not in this shell's PATH; panes rely on the login shell finding it" >&2

case "$N" in ''|*[!0-9]*) echo "fleet.sh: -n must be a whole number, got '$N'" >&2; exit 2 ;; esac
if [ "$N" -lt 1 ] || [ "$N" -gt 9 ]; then
  echo "fleet.sh: -n must be 1-9 — $N panes is pane soup, each pane is a full Claude session fighting for the same screen" >&2
  exit 2
fi

case "$MODE" in
  default|plan|acceptEdits|bypassPermissions) ;;
  *) echo "fleet.sh: -m must be default, plan, acceptEdits or bypassPermissions; got '$MODE'" >&2; exit 2 ;;
esac

case "$SESSION" in
  ''|*:*|*.*) echo "fleet.sh: -s must be non-empty and free of ':' and '.' — tmux reserves both as target separators" >&2; exit 2 ;;
esac

[ -d "$DIR" ] || { echo "fleet.sh: no such directory: $DIR" >&2; exit 2; }
DIR=$(cd "$DIR" && pwd)

# Line k of the prompts file becomes pane k's prompt. NPROMPTS is tracked
# separately from the array so an empty file stays safe under `set -u`.
PROMPTS=()
NPROMPTS=0
if [ -n "$PROMPTS_FILE" ]; then
  [ -r "$PROMPTS_FILE" ] || { echo "fleet.sh: cannot read prompts file: $PROMPTS_FILE" >&2; exit 2; }
  while IFS= read -r line || [ -n "$line" ]; do
    PROMPTS+=("$line")
    NPROMPTS=$((NPROMPTS + 1))
  done < "$PROMPTS_FILE"
  if [ "$NPROMPTS" -gt "$N" ]; then
    echo "fleet.sh: note - $PROMPTS_FILE has $NPROMPTS lines but only $N panes; lines $((N + 1))+ are ignored" >&2
  fi
fi

# `=` forces an exact name match, so 'fleet' does not collide with 'fleet-old'.
if tmux has-session -t "=$SESSION" 2>/dev/null; then
  echo "fleet.sh: tmux session '$SESSION' already exists — leaving it untouched" >&2
  echo "  attach to it:       tmux attach -t $SESSION" >&2
  echo "  or use a new name:  fleet.sh -s <other-name>" >&2
  exit 1
fi

# The pane commands are single-quoted here so the outer shell leaves them alone;
# tmux runs them with sh -c, which expands FLEET_* from the pane environment set
# by `-e`. User text therefore never enters a command string — a prompt full of
# quotes cannot break or inject into the pane's shell.
CMD_INTERACTIVE='cd "$FLEET_DIR" && claude --permission-mode "$FLEET_MODE"; exec "${SHELL:-/bin/bash}"'
CMD_PROMPTED='cd "$FLEET_DIR" && claude --permission-mode "$FLEET_MODE" -p "$FLEET_PROMPT"; exec "${SHELL:-/bin/bash}"'

WIN=""
on_error() {
  if [ -n "$WIN" ]; then
    tmux kill-session -t "=$SESSION" 2>/dev/null || true
    echo "fleet.sh: pane setup failed — removed the half-built session '$SESSION' so a rerun is clean" >&2
  fi
}
trap on_error ERR

PROMPTED=0
for ((i = 0; i < N; i++)); do
  if [ "$i" -lt "$NPROMPTS" ]; then P=${PROMPTS[$i]}; else P=""; fi
  if [ -n "$P" ]; then
    CMD=$CMD_PROMPTED
    PROMPTED=$((PROMPTED + 1))
  else
    CMD=$CMD_INTERACTIVE
  fi

  if [ "$i" -eq 0 ]; then
    # -x/-y give the detached session a large virtual terminal; without it a
    # default 80x24 window runs out of room to split before 9 panes exist.
    # The window id is captured because a user tmux.conf may set base-index 1.
    WIN=$(tmux new-session -d -s "$SESSION" -c "$DIR" -x 250 -y 80 \
      -e "FLEET_DIR=$DIR" -e "FLEET_MODE=$MODE" -e "FLEET_PROMPT=$P" \
      -P -F '#{window_id}' "$CMD")
  else
    tmux split-window -t "$WIN" -c "$DIR" \
      -e "FLEET_DIR=$DIR" -e "FLEET_MODE=$MODE" -e "FLEET_PROMPT=$P" \
      "$CMD"
    # Re-tile after every split so the next split still has space to take.
    tmux select-layout -t "$WIN" tiled >/dev/null
  fi
done

tmux select-layout -t "$WIN" tiled >/dev/null
trap - ERR

echo "session:  $SESSION"
echo "panes:    $N ($PROMPTED prompted, $((N - PROMPTED)) interactive)"
echo "dir:      $DIR"
echo "mode:     $MODE"
if [ -n "$PROMPTS_FILE" ]; then
  echo "prompts:  $PROMPTS_FILE"
fi
if [ -n "${TMUX:-}" ]; then
  echo "inside tmux already? use: tmux switch-client -t $SESSION"
fi
echo "tmux attach -t $SESSION"

#!/usr/bin/env bash
# claude-workflow-starter — Mac bootstrap
# Usage: ./install.sh [--with-ai-employees] [--teammate-mode auto|in-process|tmux|iterm2] [--user-wide] [--skip-plugin]
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WITH_AIE=0; TEAMMATE_MODE=""; USER_WIDE=0; SKIP_PLUGIN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-ai-employees) WITH_AIE=1; shift ;;
    --teammate-mode) TEAMMATE_MODE="${2:?--teammate-mode needs a value}"; shift 2 ;;
    --user-wide) USER_WIDE=1; shift ;;
    --skip-plugin) SKIP_PLUGIN=1; shift ;;
    -h|--help)
      sed -n '2,3p' "$0"; exit 0 ;;
    *) echo "Unknown flag: $1 (see --help)"; exit 1 ;;
  esac
done

step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
note() { printf '    %s\n' "$*"; }

step "Checking prerequisites"
if ! command -v git >/dev/null 2>&1; then
  note "git not found. On macOS run: xcode-select --install  (then re-run this script)"
  exit 1
fi
note "git: $(git --version)"
command -v tmux >/dev/null 2>&1 && note "tmux: present (split-pane teams available)" \
  || note "tmux: not found — agent teams still work in-process; 'brew install tmux' enables split panes"

step "Claude Code CLI"
if ! command -v claude >/dev/null 2>&1; then
  note "Installing Claude Code (official installer)..."
  curl -fsSL https://claude.ai/install.sh | bash
  export PATH="$HOME/.local/bin:$PATH"
fi
if command -v claude >/dev/null 2>&1; then
  note "claude: $(claude --version 2>/dev/null | head -1)"
else
  note "claude still not on PATH — open a new terminal (installer adds ~/.local/bin) and re-run."
  exit 1
fi

if [[ "$SKIP_PLUGIN" -eq 0 ]]; then
  step "Registering this checkout as plugin marketplace 'answering-workflows'"
  if claude plugin marketplace add "$REPO_DIR" 2>/dev/null; then
    note "marketplace added"
  else
    note "marketplace add returned non-zero (often already-registered) — continuing"
  fi
  if claude plugin install answering-suite@answering-workflows 2>/dev/null; then
    note "plugin 'answering-suite' installed"
  else
    note "CLI install didn't complete. Inside a claude session run:"
    note "  /plugin marketplace add $REPO_DIR"
    note "  /plugin install answering-suite@answering-workflows"
  fi
fi

if [[ "$USER_WIDE" -eq 1 ]]; then
  step "Copying skills + agents user-wide (~/.claude) as a plugin-free fallback"
  mkdir -p "$HOME/.claude/skills" "$HOME/.claude/agents"
  cp -R "$REPO_DIR/plugins/answering-suite/skills/." "$HOME/.claude/skills/"
  cp "$REPO_DIR/plugins/answering-suite/agents/"*.md "$HOME/.claude/agents/"
  cp "$REPO_DIR/.claude/agents/"*.md "$HOME/.claude/agents/"
  note "copied $(ls "$REPO_DIR/plugins/answering-suite/skills" | wc -l | tr -d ' ') skills and $(ls "$HOME/.claude/agents/"*.md | wc -l | tr -d ' ') agents"
fi

if [[ -n "$TEAMMATE_MODE" ]]; then
  step "Setting teammateMode='$TEAMMATE_MODE' in ~/.claude/settings.json"
  python3 - "$TEAMMATE_MODE" <<'PY'
import json, os, sys
p = os.path.expanduser("~/.claude/settings.json")
data = {}
if os.path.exists(p):
    with open(p) as f:
        try: data = json.load(f)
        except Exception: data = {}
data["teammateMode"] = sys.argv[1]
os.makedirs(os.path.dirname(p), exist_ok=True)
with open(p, "w") as f: json.dump(data, f, indent=2)
print("    written:", p)
PY
fi

if [[ "$WITH_AIE" -eq 1 ]]; then
  step "Setting up ai-employees (apps/ai-employees)"
  if ! command -v uv >/dev/null 2>&1; then
    note "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
  fi
  (cd "$REPO_DIR/apps/ai-employees" && uv sync) && note "ai-employees ready: uv run --project apps/ai-employees python -m ai_employees --help"
fi

step "Done"
note "Agent teams are enabled by this repo's .claude/settings.json (CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1)."
note "Start working:  cd $REPO_DIR && claude"
note "Then kick off:  /workflow-starter ship a demo voice agent for a dental office"
note "Split-pane teams: run inside tmux, or set --teammate-mode auto and use iTerm2/tmux."

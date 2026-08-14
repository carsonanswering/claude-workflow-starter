#!/bin/bash
# UserPromptSubmit hook: set session title from the first prompt.
# Emits {"sessionTitle": ...} once per session; no-op on later prompts.
input=$(cat)
sid=$(printf '%s' "$input" | jq -r '.session_id // empty')
prompt=$(printf '%s' "$input" | jq -r '.prompt // empty')
[ -z "$sid" ] && exit 0
[ -z "$prompt" ] && exit 0

# skip slash commands and bang commands — poor titles, often routine
case "$prompt" in /*|!*) exit 0 ;; esac

mark="$HOME/.cache/claude-auto-title/$sid"
[ -e "$mark" ] && exit 0
mkdir -p "$HOME/.cache/claude-auto-title"
touch "$mark"

title=$(printf '%s' "$prompt" | /Users/taj/.local/bin/fw -m oss -s 'You title coding sessions. Output ONLY a 3-6 word title for the given prompt. No quotes, no trailing punctuation, no explanation.' 'Title this session prompt.' 2>/dev/null | head -1 | sed 's/^["'"'"']//; s/["'"'"']$//' | cut -c1-60)

if [ -z "$title" ]; then
  title=$(printf '%s' "$prompt" | tr '\n' ' ' | awk '{for(i=1;i<=6&&i<=NF;i++)printf "%s%s",$i,(i<6&&i<NF?" ":"")}' | cut -c1-60)
fi
[ -z "$title" ] && exit 0

jq -cn --arg t "$title" '{sessionTitle:$t, suppressOutput:true}'

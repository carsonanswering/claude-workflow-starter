#!/bin/bash
# UserPromptSubmit hook: on /usage, regenerate Max savings dashboard and
# ask the model to republish the artifact.
p=$(jq -r '.prompt // ""')
case "$p" in
  /usage*)
    python3 ~/.claude/max-dashboard/generate.py >/dev/null 2>&1
    cat <<'EOF'
{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"Max savings dashboard regenerated at ~/.claude/max-dashboard/dashboard.html. Republish it now with the Artifact tool: file_path=/Users/taj/.claude/max-dashboard/dashboard.html, url=https://claude.ai/code/artifact/0018b903-aa12-438b-8cfe-26469b192845, keep existing favicon/title."}}
EOF
    ;;
esac
exit 0

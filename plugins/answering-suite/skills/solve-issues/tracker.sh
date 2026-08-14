#!/bin/bash
# Tracker lease helper for the solve-issues protocol.
#
# All Claude Code sessions authenticate to GitHub as the SAME user, so "assigned"
# cannot distinguish one session from another. Mutual exclusion therefore comes
# from a claim comment carrying a per-session token, with the earliest comment id
# winning. Comment ids are monotonic, so the tiebreak is deterministic and needs
# no coordination between sessions.
#
# Usage:
#   tracker.sh next [limit]           list issues eligible to be worked
#   tracker.sh claim <issue> <token>  try to take the lease; exit 0 won, 1 lost
#   tracker.sh release <issue> <token> [reason]
#   tracker.sh finish <issue> <token> <pr-url>
#   tracker.sh stale [hours]          claims older than N hours (default 4)
#   tracker.sh status                 who holds what right now

set -euo pipefail
REPO="AnsweringRND/tracker"
MARK="🔒 claim"

need() { command -v "$1" >/dev/null || { echo "missing dependency: $1" >&2; exit 127; }; }
need gh; need jq

# An issue is workable when it is open, carries no wayfinder label (maps are
# human-in-the-loop by design), is not flagged as needing a founder decision,
# has no open blocker, and nobody has claimed it.
eligible() {
  gh issue list --repo "$REPO" --state open --limit 200 \
    --json number,title,labels,assignees,blockedBy,milestone \
    --jq '[ .[]
      | select([.labels[].name] | any(startswith("wayfinder:")) | not)
      | select([.labels[].name] | any(. == "needs:carson") | not)
      | select(.assignees | length == 0)
      | select([.blockedBy.nodes[] | select(.state == "OPEN")] | length == 0)
      | { number, title,
          product: ([.labels[].name | select(. == "answering" or . == "conscience" or . == "cornea" or . == "suite" or . == "customers+sales")] | first // "-"),
          priority: ([.labels[].name | select(. == "P0" or . == "P1")] | first // "P2"),
          milestone: (.milestone.title // "-") } ]
      | sort_by(.priority, .number)'
}

# Every comment that moves lease state: claim, release, and finish, each of
# which carries a token in backticks. Sorted by id (monotonic == chronological)
# so downstream logic never needs wall-clock time to order events.
lease_comments_on() {
  gh api "repos/$REPO/issues/$1/comments" --paginate \
    --jq '[.[] | select(.body | startswith("🔒 claim") or startswith("🔓 released") or startswith("✅ worked by"))
           | { id, body, at: .created_at,
               kind: (if (.body | startswith("🔒 claim")) then "claim"
                      elif (.body | startswith("🔓 released")) then "release"
                      else "finish" end),
               token: (.body | split("`")[1]) } ]
      | sort_by(.id)'
}

# A claim is live only if no later release/finish carries the SAME token —
# a released or finished lease must never keep blocking the next claimant.
# The holder is the earliest still-live claim; ties resolve on comment id
# (see header), never on timestamp, so concurrent sessions agree independently.
resolve_live_claim() {
  jq '(map(select(.kind != "claim"))) as $closes
    | map(select(.kind == "claim"))
    | map(select(. as $c | ($closes | map(select(.token == $c.token and .id > $c.id)) | length) == 0))
    | sort_by(.id) | .[0] // empty'
}

case "${1:-}" in

  next)
    limit="${2:-100}"
    eligible | jq -r --argjson l "$limit" \
      '.[:$l][] | "#\(.number)\t\(.priority)\t\(.product)\t\(.title)"' \
      | column -t -s $'\t'
    ;;

  claim)
    issue="${2:?issue number required}"; token="${3:?session token required}"

    # One open issue per session. Prose in the skill is not a mechanism: a
    # session that grabs four issues stalls three of them behind its own
    # single-threaded work while hiding them from every other session.
    held=$(gh issue list --repo "$REPO" --state open --limit 200 --json number,assignees \
             --jq '.[] | select(.assignees | length > 0) | .number' \
           | while read -r h; do
               winner=$(lease_comments_on "$h" | resolve_live_claim)
               if [ -n "$winner" ] && jq -e --arg t "$token" '.token == $t' <<<"$winner" >/dev/null 2>&1; then echo "$h"; fi
             done)
    if [ -n "$held" ]; then
      echo "REFUSED — this session already holds #$(echo "$held" | tr '\n' ' ')" >&2
      echo "Finish or release it before claiming another. One issue at a time per session." >&2
      exit 2
    fi

    # Re-check eligibility at claim time, not just at list time.
    if ! eligible | jq -e --argjson n "$issue" 'any(.number == $n)' >/dev/null; then
      echo "LOST #$issue — no longer eligible (claimed, blocked, or closed since listing)"; exit 1
    fi

    gh issue edit "$issue" --repo "$REPO" --add-assignee @me >/dev/null
    gh issue comment "$issue" --repo "$REPO" --body "$MARK \`$token\`" >/dev/null

    # Settle the race: earliest still-live claim wins (see resolve_live_claim).
    # Anyone else stands down.
    sleep 2
    winner=$(lease_comments_on "$issue" | resolve_live_claim)
    if [ -n "$winner" ] && jq -e --arg t "$token" '.token == $t' <<<"$winner" >/dev/null 2>&1; then
      echo "WON #$issue"; exit 0
    else
      gh issue edit "$issue" --repo "$REPO" --remove-assignee @me >/dev/null 2>&1 || true
      holder=$(jq -r '.token // "none"' <<<"${winner:-null}")
      echo "LOST #$issue — held by: $holder"; exit 1
    fi
    ;;

  release)
    issue="${2:?}"; token="${3:?}"; reason="${4:-released without completing}"
    gh issue edit "$issue" --repo "$REPO" --remove-assignee @me >/dev/null 2>&1 || true
    gh issue comment "$issue" --repo "$REPO" \
      --body "🔓 released \`$token\` — $reason

Back on the frontier; another session may pick it up." >/dev/null
    echo "released #$issue"
    ;;

  finish)
    issue="${2:?}"; token="${3:?}"; pr="${4:?pr url required}"
    gh issue comment "$issue" --repo "$REPO" \
      --body "✅ worked by \`$token\` — $pr

Left open deliberately: the pull request closes this issue on merge, and merging is a human call." >/dev/null
    gh issue edit "$issue" --repo "$REPO" --remove-assignee @me >/dev/null 2>&1 || true
    echo "finished #$issue -> $pr"
    ;;

  stale)
    hours="${2:-4}"
    cutoff=$(date -u -v-"${hours}"H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null \
             || date -u -d "$hours hours ago" +%Y-%m-%dT%H:%M:%SZ)
    gh issue list --repo "$REPO" --state open --limit 200 --json number,title,assignees \
      --jq '.[] | select(.assignees | length > 0) | .number' \
    | while read -r n; do
        winner=$(lease_comments_on "$n" | resolve_live_claim)
        [ -z "$winner" ] && continue
        held=$(jq -r --arg c "$cutoff" 'select(.at < $c) | .body // empty' <<<"$winner")
        [ -n "$held" ] && echo "#$n stale since $(jq -r '.at' <<<"$winner") — $held"
      done
    echo "(reclaim with: tracker.sh release <issue> <its-token> 'stale lease')"
    ;;

  status)
    gh issue list --repo "$REPO" --state open --limit 200 --json number,title,assignees \
      --jq '.[] | select(.assignees|length>0) | "#\(.number) \(.title)"'
    ;;

  *)
    sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac

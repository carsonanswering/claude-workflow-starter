#!/bin/bash
# loop-fp.sh — change-gate fingerprint for loop discovery (doctrine §1).
#
#   loop-fp.sh <repo>...                          print "<fp>  <repo>" per repo
#   loop-fp.sh --gate --ledger F <repo>...        compare vs stored fingerprints
#   loop-fp.sh --gate --ledger F --no-update ...  compare without storing (peek)
#
# Gate exit codes:  0 = at least one repo CHANGED  -> run discovery
#                  20 = every repo UNCHANGED       -> no-op tick, skip discovery
#                   2 = a path was not a git repo  -> re-Orient, do not guess
#
# Fingerprint = sha256( git for-each-ref + git stash list + git status --porcelain )
# Validated EXP-01: caught 6/6 change classes at ~0.04s/repo, zero false
# positives. Do NOT substitute `git rev-parse HEAD` (caught 0/6) or directory
# mtime (1/6 — frozen under commits made from another worktree).
#
# Caveats (EXP-01, carried forward):
#   - for-each-ref includes REMOTE refs, so a plain `git fetch` trips the gate.
#   - `status --porcelain` is the cost driver — re-time on >10k-file repos.
#   - Ignored files are invisible to the fingerprint.
set -euo pipefail

LEDGER_CLI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/ledger.py"

gate=0
ledger=""
no_update=0
repos=()

while [ $# -gt 0 ]; do
  case "$1" in
    --gate)      gate=1; shift ;;
    --ledger)    ledger="${2:-}"; shift 2 ;;
    --no-update) no_update=1; shift ;;
    -h|--help)   sed -n '2,21p' "$0"; exit 0 ;;
    --)          shift; while [ $# -gt 0 ]; do repos+=("$1"); shift; done ;;
    -*)          echo "unknown flag: $1" >&2; exit 64 ;;
    *)           repos+=("$1"); shift ;;
  esac
done

if [ "${#repos[@]}" -eq 0 ]; then
  echo "usage: loop-fp.sh [--gate --ledger FILE [--no-update]] <repo>..." >&2
  exit 64
fi
if [ "$gate" -eq 1 ] && [ -z "$ledger" ]; then
  echo "--gate requires --ledger FILE" >&2
  exit 64
fi

fingerprint() {
  local repo="$1"
  if ! git -C "$repo" rev-parse --git-dir >/dev/null 2>&1; then
    echo "not a git repo: $repo" >&2
    return 2
  fi
  {
    git -C "$repo" for-each-ref
    git -C "$repo" stash list
    git -C "$repo" status --porcelain
  } | shasum -a 256 | cut -d' ' -f1
}

any_changed=0

for repo in "${repos[@]}"; do
  fp="$(fingerprint "$repo")"          # exits 2 via set -e if not a repo
  abs="$(cd "$repo" && pwd)"

  if [ "$gate" -eq 0 ]; then
    echo "$fp  $abs"
    continue
  fi

  args=(--ledger "$ledger" gate "$abs" "$fp")
  [ "$no_update" -eq 1 ] && args+=(--no-update)

  set +e
  python3 "$LEDGER_CLI" "${args[@]}"
  rc=$?
  set -e

  case "$rc" in
    0)  any_changed=1 ;;
    20) : ;;                            # unchanged
    *)  echo "ledger gate failed (rc=$rc) for $abs" >&2; exit "$rc" ;;
  esac
done

if [ "$gate" -eq 1 ]; then
  [ "$any_changed" -eq 1 ] && exit 0
  exit 20
fi

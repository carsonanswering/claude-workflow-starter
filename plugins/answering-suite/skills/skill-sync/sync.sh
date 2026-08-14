#!/bin/bash
# skill-sync — mirror skills / agents / hooks into the CortexRND/skills share repo and push.
#
#   sync.sh <name>... [-m "commit message"]   sync named skills, agents or hooks
#   sync.sh --all-changed [-m "message"]      sync every source item whose content differs
#   sync.sh --check-trio                      diff the cortex-brief trio pairs only, no git
#
# Exit: 0 ok · 1 trio drift (--check-trio) · 2 refused · 3 trio drift blocks sync · 4 push failed
#
# Directory items are mirrored with --delete so a file removed at the source leaves the
# share repo too; the runtime-state excludes below are also protected from that delete.

set -o pipefail

REPO=/Users/taj/projs/skills
REMOTE_URL=https://github.com/CortexRND/skills.git
BRANCH=main

SKILL_ROOTS="/Users/taj/.claude/skills /Users/taj/projs/.claude/skills"
AGENT_ROOTS="/Users/taj/.claude/agents /Users/taj/projs/.claude/agents"
HOOK_ROOTS="/Users/taj/.claude/hooks /Users/taj/projs/.claude/hooks"

# day-plan, daily-brief and comp-watch exist at both of these and must stay byte-identical.
TRIO_NAMES="day-plan daily-brief comp-watch"
TRIO_USER=/Users/taj/.claude/skills
TRIO_PROJ=/Users/taj/projs/cortex-brief/.claude/skills

RSYNC_EX=(--exclude='*state.json' --exclude='items.json' --exclude='out/' \
          --exclude='*.log' --exclude='__pycache__/' --exclude='*.pyc' \
          --exclude='.DS_Store' --exclude='last-session-note.txt')

# Runtime state that must never reach the share repo. Wider than .gitignore on purpose:
# it also catches session-obsidian-state.json and last-session-note.txt.
RUNTIME_RE='(^|/)(out|__pycache__)/|(^|/)[^/]*state\.json$|(^|/)items\.json$|(^|/)last-session-note\.txt$|\.log$|\.pyc$'

say() { printf '%s\n' "$*"; }
die() { c=$1; shift; printf 'skill-sync: %s\n' "$*" >&2; exit "$c"; }

usage() {
  cat <<'USAGE'
skill-sync — mirror skills/agents/hooks into the CortexRND/skills share repo, then push.

  sync.sh <name>... [-m "commit message"]   sync named skills, agents or hooks
  sync.sh --all-changed [-m "message"]      sync every source item whose content differs
  sync.sh --check-trio                      diff the cortex-brief trio pairs only, no git

Exit: 0 ok · 1 trio drift (--check-trio) · 2 refused · 3 trio drift blocks sync · 4 push failed
USAGE
}

hook_dest() {
  f=$(basename "$1")
  case "$f" in
    *statusline*) printf '%s\n' "$REPO/statusline/$f" ;;
    *)            printf '%s\n' "$REPO/hooks/$f" ;;
  esac
}

is_trio() {
  case " $TRIO_NAMES " in
    *" $1 "*) return 0 ;;
  esac
  return 1
}

trio_pair_ok() {
  n=$1
  a="$TRIO_USER/$n"
  b="$TRIO_PROJ/$n"
  if [ ! -d "$a" ] || [ ! -d "$b" ]; then
    say "trio DRIFT $n: one side is missing"
    [ -d "$a" ] || say "    absent: $a"
    [ -d "$b" ] || say "    absent: $b"
    return 1
  fi
  d=$(diff -r -q -x '.DS_Store' -x '__pycache__' "$a" "$b" 2>&1)
  if [ -n "$d" ]; then
    say "trio DRIFT $n:"
    printf '%s\n' "$d" | sed 's/^/    /'
    return 1
  fi
  say "trio ok $n"
  return 0
}

# Print one "type|src|dest" record for a name, or explain why it cannot be resolved.
resolve_name() {
  raw=$1
  base=${raw%/}
  base=${base##*/}
  stem=${base%.md}
  hits=""
  for root in $SKILL_ROOTS; do
    if [ -f "$root/$base/SKILL.md" ] && [ ! -L "$root/$base" ]; then
      hits="$hits
skill|$root/$base|$REPO/skills/$base"
    fi
  done
  for root in $AGENT_ROOTS; do
    if [ -f "$root/$stem.md" ]; then
      hits="$hits
agent|$root/$stem.md|$REPO/agents/$stem.md"
    fi
  done
  for root in $HOOK_ROOTS; do
    for cand in "$root/$base" "$root/$base.sh" "$root/$base.py" "$root/$base.json"; do
      if [ -f "$cand" ]; then
        hits="$hits
hook|$cand|$(hook_dest "$cand")"
        break
      fi
    done
  done
  hits=$(printf '%s\n' "$hits" | sed '/^$/d')
  if [ -z "$hits" ]; then
    printf 'skill-sync: no skill dir, agent .md or hook script named "%s" under:\n' "$base" >&2
    for root in $SKILL_ROOTS $AGENT_ROOTS $HOOK_ROOTS; do printf '    %s\n' "$root" >&2; done
    return 2
  fi
  if [ "$(printf '%s\n' "$hits" | wc -l | tr -d ' ')" -gt 1 ]; then
    printf 'skill-sync: "%s" is ambiguous — it matches:\n' "$base" >&2
    printf '%s\n' "$hits" | cut -d'|' -f2 | sed 's/^/    /' >&2
    printf '    rename one, or sync them one at a time from a single root.\n' >&2
    return 2
  fi
  printf '%s\n' "$hits"
  return 0
}

# True when the source content differs from the share-repo copy (rsync itemized dry run).
item_changed() {
  t=$1; s=$2; d=$3
  if [ "$t" = skill ]; then
    out=$(rsync -ain -c --delete "${RSYNC_EX[@]}" "$s/" "$d/" 2>/dev/null | grep -E '^[<>ch*]')
  else
    out=$(rsync -ain -c "${RSYNC_EX[@]}" "$s" "$d" 2>/dev/null | grep -E '^[<>ch*]')
  fi
  [ -n "$out" ]
}

sync_item() {
  t=$1; s=$2; d=$3
  if [ "$t" = skill ]; then
    mkdir -p "$d" || return 1
    rsync -a --delete "${RSYNC_EX[@]}" "$s/" "$d/" || return 1
  else
    mkdir -p "$(dirname "$d")" || return 1
    rsync -a "${RSYNC_EX[@]}" "$s" "$d" || return 1
  fi
  return 0
}

MODE=names
MSG='skill sync'
NAMES=''

while [ $# -gt 0 ]; do
  case "$1" in
    --check-trio)  MODE=trio ;;
    --all-changed) MODE=all ;;
    -m|--message)  shift; [ $# -gt 0 ] || die 2 "-m needs a message"; MSG=$1 ;;
    -h|--help)     usage; exit 0 ;;
    -*)            usage >&2; die 2 "unknown flag $1" ;;
    *)             NAMES="$NAMES $1" ;;
  esac
  shift
done

# --- trio-only mode: no copying, no git -------------------------------------
if [ "$MODE" = trio ]; then
  rc=0
  for n in $TRIO_NAMES; do
    trio_pair_ok "$n" || rc=1
  done
  [ "$rc" -eq 0 ] || die 1 "trio drift — $TRIO_NAMES must be byte-identical at $TRIO_USER and $TRIO_PROJ"
  say "trio identical=3"
  exit 0
fi

if [ "$MODE" = names ] && [ -z "${NAMES// /}" ]; then
  usage >&2
  die 2 "give at least one name, or --all-changed"
fi

# --- preflight: the push target is the one this skill is allowed to touch ----
[ -d "$REPO/.git" ] || die 2 "share repo checkout not found at $REPO"
url=$(git -C "$REPO" remote get-url origin 2>/dev/null)
[ "$url" = "$REMOTE_URL" ] || die 2 "origin is '$url', expected $REMOTE_URL — refusing to push"
cur=$(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null)
[ "$cur" = "$BRANCH" ] || die 2 "share repo is on branch '$cur', expected $BRANCH — ask Taj before syncing off $BRANCH"

# --- build the plan ---------------------------------------------------------
PLAN=''
if [ "$MODE" = all ]; then
  for root in $SKILL_ROOTS; do
    [ -d "$root" ] || continue
    for dir in "$root"/*; do
      [ -L "$dir" ] && continue   # symlinked skills are third-party (mattpocock etc.) — never sync
      [ -f "$dir/SKILL.md" ] || continue
      PLAN="$PLAN
skill|$dir|$REPO/skills/$(basename "$dir")"
    done
  done
  for root in $AGENT_ROOTS; do
    [ -d "$root" ] || continue
    for f in "$root"/*.md; do
      [ -f "$f" ] || continue
      PLAN="$PLAN
agent|$f|$REPO/agents/$(basename "$f")"
    done
  done
  for root in $HOOK_ROOTS; do
    [ -d "$root" ] || continue
    for f in "$root"/*.sh "$root"/*.py "$root"/*.json; do
      [ -f "$f" ] || continue
      case "$(basename "$f")" in
        *state.json|*.log) continue ;;
      esac
      PLAN="$PLAN
hook|$f|$(hook_dest "$f")"
    done
  done
  SEL=''
  while IFS='|' read -r t s d; do
    [ -n "$t" ] || continue
    if item_changed "$t" "$s" "$d"; then
      SEL="$SEL
$t|$s|$d"
    fi
  done <<EOF
$PLAN
EOF
  PLAN=$SEL
else
  for n in $NAMES; do
    rec=$(resolve_name "$n") || exit 2
    PLAN="$PLAN
$rec"
  done
fi

# --- trio identity gate: never ship half of a mirrored pair -----------------
rc=0
while IFS='|' read -r t s d; do
  [ "$t" = skill ] || continue
  n=$(basename "$s")
  is_trio "$n" || continue
  trio_pair_ok "$n" || rc=1
done <<EOF
$PLAN
EOF
[ "$rc" -eq 0 ] || die 3 "trio drift blocks this sync — show Taj the diff above and ask which side is authoritative before either copy overwrites the other"

# --- copy -------------------------------------------------------------------
count=0
while IFS='|' read -r t s d; do
  [ -n "$t" ] || continue
  sync_item "$t" "$s" "$d" || die 2 "rsync failed copying $s -> $d"
  say "synced $t $(basename "$s") -> ${d#$REPO/}"
  count=$((count + 1))
done <<EOF
$PLAN
EOF

# --- runtime-state guard, before anything is staged -------------------------
dirty=$(git -C "$REPO" status --porcelain --untracked-files=all --no-renames | cut -c4-)
offend=$(printf '%s\n' "$dirty" | sed '/^$/d' | grep -E "$RUNTIME_RE")
if [ -n "$offend" ]; then
  printf 'skill-sync: refusing — runtime state in %s:\n' "$REPO" >&2
  printf '%s\n' "$offend" | sed 's/^/    /' >&2
  printf '    delete those paths (or add them to %s/.gitignore) and rerun.\n' "$REPO" >&2
  exit 2
fi

# --- stage, commit, push ----------------------------------------------------
git -C "$REPO" add -A || die 2 "git add -A failed in $REPO"
staged=$(git -C "$REPO" diff --cached --name-only)

if [ -z "$staged" ]; then
  head=$(git -C "$REPO" rev-parse --short HEAD)
  sb=$(git -C "$REPO" status -sb | head -1)
  say "no-change head=$head items=$count branch=$BRANCH"
  say "$sb"
  case "$sb" in
    *ahead*) die 4 "an earlier commit never reached origin — run: git -C $REPO push origin $BRANCH" ;;
  esac
  exit 0
fi

offend=$(printf '%s\n' "$staged" | grep -E "$RUNTIME_RE")
if [ -n "$offend" ]; then
  printf 'skill-sync: refusing — runtime state staged:\n' >&2
  printf '%s\n' "$offend" | sed 's/^/    /' >&2
  printf '    unstage with: git -C %s reset\n' "$REPO" >&2
  exit 2
fi

git -C "$REPO" commit -q -m "$MSG" || die 2 "commit failed in $REPO"
git -C "$REPO" push -q origin "$BRANCH" || die 4 "push rejected — origin has commits you do not; show Taj 'git -C $REPO log --oneline HEAD..origin/$BRANCH' and ask before rebasing or merging"

sha=$(git -C "$REPO" rev-parse --short HEAD)
sb=$(git -C "$REPO" status -sb | head -1)
say "pushed=$sha items=$count branch=$BRANCH"
say "$sb"
printf '%s\n' "$staged" | sed 's/^/    /'
case "$sb" in
  *ahead*) die 4 "push did not land — still ahead of origin/$BRANCH" ;;
esac
exit 0

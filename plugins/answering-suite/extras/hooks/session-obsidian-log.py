#!/usr/bin/env python3
"""SessionEnd hook: judge session value, write Obsidian note if valuable.

Fires on /clear and exit. Cheap heuristic gate first; if passed, forks to
background and calls `claude -p` to judge + summarize, then writes the note
into the Obsidian vault per the obsidian-log skill format.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

VAULT = Path.home() / "Documents/ObsidianVault"
NOTES_DIR = Path.home() / "projs/session-logs"
INDEX = NOTES_DIR / "Claude Sessions Index.md"
LOG = Path.home() / ".claude/hooks/session-obsidian-log.log"
STATE = Path.home() / ".claude/hooks/session-obsidian-state.json"
LAST_NOTE = Path.home() / ".claude/hooks/last-session-note.txt"
MODEL = "claude-sonnet-5"
MAX_DIGEST_CHARS = 60_000
GUARD_ENV = "CLAUDE_OBSLOG_HOOK"

# Gate thresholds: below these, session considered trivial, no LLM call.
MIN_TOOL_CALLS = 5
MIN_EDITS = 1
MIN_USER_MSGS = 1

# Routine skills/commands: running them is maintenance, not knowledge. A session
# whose only user intent is these gets no note however many tools it burned.
ROUTINE_COMMANDS = {
    "dash", "open-items", "running-view", "daily-brief", "comp-watch",
    "day-plan", "caveman-stats", "caveman", "caveman-help", "clear",
    "compact", "context", "status", "cost", "agents", "config", "model",
    "resume", "export", "doctor", "help", "mcp", "memory", "permissions",
    "release-notes", "terminal-setup", "vim",
}
# Files those routine skills rewrite. Edits here are not durable work.
ROUTINE_EDIT_PATTERNS = (
    "/.claude/max-dashboard/", "/scratchpad/", "/items.json", "/state.json",
    "/running-view/", "/open-items/",
)
COMMAND_RE = re.compile(r"<command-name>\s*/?([\w:-]+)", re.I)
# Turns that are harness plumbing, not the user speaking.
NOISE_MARKERS = ("<system-reminder>", "<local-command-stdout>",
                 "hook additional context", "Caveat: The messages below")


def log(msg: str) -> None:
    with LOG.open("a") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')} {msg}\n")


def iter_entries(transcript_path: str):
    with open(transcript_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def classify_user_turn(text: str) -> str:
    """'noise' (harness plumbing), 'routine' (maintenance command), or 'real'."""
    stripped = text.strip()
    if not stripped:
        return "noise"
    if any(m in stripped for m in NOISE_MARKERS):
        return "noise"
    cmd = COMMAND_RE.search(stripped)
    if cmd:
        name = cmd.group(1).lower().split(":")[-1]
        # A command plus extra prose is a real ask; the bare command is not.
        residue = COMMAND_RE.sub("", stripped)
        residue = re.sub(r"<[^>]+>", " ", residue).strip()
        if name in ROUTINE_COMMANDS and len(residue) < 40:
            return "routine"
        return "real"
    if stripped.startswith("/"):
        name = stripped[1:].split()[0].lower().split(":")[-1] if len(stripped) > 1 else ""
        if name in ROUTINE_COMMANDS and len(stripped.split()) <= 2:
            return "routine"
    return "real"


def is_routine_edit(path: str) -> bool:
    return any(p in path for p in ROUTINE_EDIT_PATTERNS)


def build_digest(transcript_path: str):
    """One pass: gate stats + compressed digest for the judge."""
    tool_calls = edits = user_msgs = 0
    real_msgs = routine_msgs = real_edits = 0
    parts = []
    for e in iter_entries(transcript_path):
        etype = e.get("type")
        msg = e.get("message") or {}
        content = msg.get("content")
        if etype == "user" and isinstance(content, str):
            kind = classify_user_turn(content)
            if kind == "real":
                real_msgs += 1
            elif kind == "routine":
                routine_msgs += 1
            user_msgs += 1
            parts.append(f"USER: {content[:1500]}")
            continue
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if etype == "user" and btype == "text":
                text = block.get("text", "")
                kind = classify_user_turn(text)
                if kind == "real":
                    real_msgs += 1
                elif kind == "routine":
                    routine_msgs += 1
                user_msgs += 1
                parts.append(f"USER: {text[:1500]}")
            elif etype == "assistant" and btype == "text":
                parts.append(f"ASSISTANT: {block.get('text', '')[:1500]}")
            elif etype == "assistant" and btype == "tool_use":
                tool_calls += 1
                name = block.get("name", "?")
                inp = block.get("input") or {}
                if name in ("Edit", "Write", "NotebookEdit"):
                    edits += 1
                    if not is_routine_edit(str(inp.get("file_path") or "")):
                        real_edits += 1
                detail = inp.get("file_path") or inp.get("command") or inp.get("description") or ""
                parts.append(f"TOOL {name}: {str(detail)[:300]}")
    digest = "\n".join(parts)
    if len(digest) > MAX_DIGEST_CHARS:
        # Keep head and tail — objective at start, outcome at end.
        half = MAX_DIGEST_CHARS // 2
        digest = digest[:half] + "\n[... middle truncated ...]\n" + digest[-half:]
    stats = {
        "tool_calls": tool_calls,
        "edits": edits,
        "user_msgs": user_msgs,
        "real_msgs": real_msgs,
        "routine_msgs": routine_msgs,
        "real_edits": real_edits,
    }
    return digest, stats


def gate_reject(stats: dict) -> str | None:
    """Return a reason string if the session is not worth an LLM judge call."""
    if stats["user_msgs"] < MIN_USER_MSGS:
        return "no user messages"
    # Only maintenance commands were asked for. Tool volume is irrelevant:
    # /dash and /open-items burn many calls and leave nothing to remember.
    if stats["real_msgs"] == 0:
        if stats["routine_msgs"] > 0:
            return "routine commands only"
        return "no substantive user turn"
    # Real ask, but nothing lasting came of it: no durable edit and barely any work.
    if stats["real_edits"] < MIN_EDITS and stats["tool_calls"] < MIN_TOOL_CALLS:
        return "too little activity"
    return None


def load_state() -> dict:
    try:
        data = json.loads(STATE.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    """Atomic write; keep only the most recent sessions so this never grows."""
    trimmed = dict(sorted(state.items(), key=lambda kv: kv[1].get("ts", ""))[-500:])
    tmp = STATE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(trimmed, indent=1))
    tmp.replace(STATE)


def record(session_id: str, digest_sha: str, note: str | None) -> None:
    state = load_state()
    state[session_id] = {
        "digest_sha": digest_sha,
        "note": note,
        "ts": datetime.now().isoformat(timespec="seconds"),
    }
    save_state(state)


def announce(path: Path, verb: str = "logged") -> None:
    """Surface the note path. Runs detached after the session ended, so stdout
    alone is not enough — also leave a pointer file and a desktop notification."""
    msg = f"Obsidian session note {verb}: {path}"
    try:
        LAST_NOTE.write_text(f"{path}\n")
    except OSError:
        pass
    print(msg, flush=True)
    log(msg)
    try:
        title = "Claude session logged"
        body = Path(path).name.replace("\\", "\\\\").replace('"', '\\"')
        subprocess.run(
            ["osascript", "-e",
             f'display notification "{body}" with title "{title}"'],
            timeout=5, capture_output=True,
        )
    except Exception as e:
        log(f"notification failed: {e!r}")
    try:
        subprocess.run(
            ["osascript", "-e",
             f'display notification {json.dumps(str(path.name))} '
             f'with title "Claude session note {verb}"'],
            capture_output=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def prior_for(session_id: str, digest_sha: str):
    """Return (existing_note_or_None, unchanged). `unchanged` means this exact
    digest was already handled — nothing to do, no second judge call. When the
    digest grew, an existing note is rewritten in place rather than duplicated."""
    entry = load_state().get(session_id)
    if not entry:
        return None, False
    note = entry.get("note")
    path = Path(note) if note and Path(note).exists() else None
    return path, entry.get("digest_sha") == digest_sha


def update_index(note_name: str, date_str: str) -> None:
    line = f"- [[{note_name}]]"
    header = f"## {date_str}"
    if INDEX.exists():
        text = INDEX.read_text()
    else:
        text = "# Claude Sessions Index\n"
    if header in text:
        text = text.replace(header, f"{header}\n{line}", 1)
    else:
        # Insert new date section after the title line (newest first).
        lines = text.splitlines()
        insert_at = 1 if lines and lines[0].startswith("#") else 0
        lines[insert_at:insert_at] = ["", header, line]
        text = "\n".join(lines) + ("\n" if not text.endswith("\n") else "")
    INDEX.write_text(text)


def collision_path(directory: Path, filename: str) -> Path:
    """Title clash with a DIFFERENT session's note — our own session is already
    deduped by state before we get here."""
    p = directory / filename
    stem, suffix = p.stem, p.suffix
    n = 2
    while p.exists():
        p = directory / f"{stem} ({n}){suffix}"
        n += 1
    return p


def judge_and_write(digest: str, project: str, date_str: str, time_str: str,
                    session_id: str, digest_sha: str, prior: Path | None = None) -> None:
    existing = sorted(p.stem for p in NOTES_DIR.glob("*.md"))[-30:] if NOTES_DIR.exists() else []
    rewrite_note = ""
    if prior is not None:
        rewrite_note = (
            f"\nThis session was already logged as `{prior.name}` and has since continued. "
            "You are REWRITING that note to cover the whole session, not writing a new one. "
            "Cover the earlier work too — the digest below is the full session. "
            "Keep the same title unless the session's subject genuinely changed. "
            "Do not output SKIP: the note already exists and must be kept.\n"
        )
    prompt = f"""You are judging whether a Claude Code session is worth logging as a permanent note, and writing the note if so.

Today: {date_str} {time_str}. Project: {project}.
{rewrite_note}

Below is a compressed digest of the session (user messages, assistant replies, tool calls).

First decide: is this session VALUABLE to log? Apply this test: six months from now, would re-reading the note change a decision or save real work? If not, it is not valuable.

VALUABLE: code written or changed that survives the session; investigation that produced a finding or verdict; a decision made with its reasoning; a plan or design produced; a bug diagnosed; a non-obvious gotcha learned.

NOT VALUABLE — output SKIP for all of these, no matter how many tool calls happened:
- Running a routine skill or dashboard: /dash, /open-items, /running-view, /daily-brief, /comp-watch, /day-plan, status or usage checks. Regenerating an artifact is maintenance, not knowledge.
- Status queries: "what's running", "what's on my plate", "how many tokens", listing files or processes.
- One-off Q&A answered from what was read, with nothing changed on disk.
- Aborted or empty sessions; sessions that only set config, toggled a mode, or fiddled with settings without a lasting learning.
- Work whose only output is a message posted somewhere (Slack digest, brief) with no decision or change behind it.

Volume of tool calls is NOT evidence of value. A session with 40 Bash calls that only refreshed a dashboard is a SKIP. A session with 3 calls that diagnosed a bug is valuable.

If NOT valuable, output exactly the single word: SKIP

If valuable, output:
Line 1: FILENAME: {date_str} <2-5 word title>.md
Then the full note in this exact skeleton (omit empty sections; normal prose, not compressed style):

---
date: {date_str}
time: {time_str}
project: {project}
session: {session_id}
tags:
  - claude-session
  - <1-3 topic tags, lowercase-kebab>
tools: [<notable tools/tech touched>]
status: <completed | in-progress | blocked>
---

# <Session title>

## Objective
<1-2 sentences: what the user asked for.>

## Summary
<3-8 sentences: approach, what worked, what was abandoned and why.>

## Key decisions
- <decision> — <why>

## Files changed
| File | Change |
|------|--------|
| `path` | <one-line> |

## Commands & findings
- <decisive command or discovery with outcome>

## Open items / next steps
- [ ] <unfinished work>

## Related
- [[<wikilink if an existing note below clearly relates, else omit section>]]

Existing notes (for Related links): {json.dumps(existing)}

Rules: summarize only what actually occurred in the digest. Never include API keys, tokens, passwords — redact as <redacted>. Output nothing except SKIP or FILENAME line + note.

=== SESSION DIGEST ===
{digest}"""

    env = dict(os.environ, **{GUARD_ENV: "1"})
    # Judge via cheap Fireworks one-shot (fw CLI); fall back to claude -p if fw
    # is missing or errors. Output is validated below (SKIP / FILENAME regex),
    # so a malformed cheap-model reply degrades to a logged parse failure.
    out = ""
    try:
        result = subprocess.run(
            ["fw", prompt], capture_output=True, text=True, timeout=300, env=env,
        )
        if result.returncode == 0:
            out = result.stdout.strip()
        else:
            log(f"fw failed rc={result.returncode}: {result.stderr[:300]}")
    except (OSError, subprocess.SubprocessError) as e:
        log(f"fw unavailable: {e}")
    if not out:
        result = subprocess.run(
            ["claude", "-p", "--model", MODEL],
            input=prompt, capture_output=True, text=True, timeout=300, env=env,
        )
        out = result.stdout.strip()
        if result.returncode != 0:
            log(f"claude -p failed rc={result.returncode}: {result.stderr[:300]}")
            return
    if not out or out.split()[0].upper().startswith("SKIP"):
        log("judge verdict: SKIP")
        return  # state already claims this digest — no re-judge on a repeat fire

    m = re.match(r"FILENAME:\s*(.+?\.md)\s*\n", out)
    if not m:
        log(f"bad judge output, no FILENAME line: {out[:200]}")
        return
    filename = m.group(1).strip().replace("/", "-")
    note = out[m.end():].lstrip()

    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    if prior is not None:
        # Session grew: rewrite the same file. Path stays put so index entries
        # and any [[wikilinks]] pointing at it keep resolving.
        path, verb = prior, "updated"
    else:
        path, verb = collision_path(NOTES_DIR, filename), "logged"
    path.write_text(note if note.endswith("\n") else note + "\n")
    if verb == "logged":
        update_index(path.stem, date_str)
    record(session_id, digest_sha, str(path))
    announce(path, verb)


def main() -> None:
    if os.environ.get(GUARD_ENV):
        return  # recursion guard: we are inside the judge's own session
    payload = json.load(sys.stdin)
    transcript = payload.get("transcript_path", "")
    reason = payload.get("reason", "?")
    cwd = payload.get("cwd", "")
    session_id = payload.get("session_id") or transcript
    if not transcript or not os.path.exists(transcript):
        return

    digest, stats = build_digest(transcript)
    digest_sha = hashlib.sha256(digest.encode()).hexdigest()[:16]

    # Same session fires SessionEnd more than once (/clear then exit). Never a
    # second note for it: unchanged digest is a no-op, grown digest rewrites the
    # existing note in place.
    prior, unchanged = prior_for(session_id, digest_sha)
    if unchanged:
        if prior:
            announce(prior, "already logged")
        else:
            log(f"already handled session={session_id} digest={digest_sha}, no change")
        return

    # A session with a note already passed the gate once; re-gating a rewrite
    # would be judging the same work twice.
    if prior is None:
        why = gate_reject(stats)
        if why:
            log(f"gate skip ({why}) reason={reason} " + " ".join(
                f"{k}={v}" for k, v in stats.items()))
            return

    # Claim this digest BEFORE forking so a concurrent/duplicate fire loses the
    # race and returns early instead of running a second judge. Keep the prior
    # note in state so a failed rewrite leaves the old note reachable.
    record(session_id, digest_sha, str(prior) if prior else None)

    # Double-fork: detach so exit/clear is not blocked by the LLM call.
    if os.fork() > 0:
        return
    os.setsid()
    if os.fork() > 0:
        os._exit(0)
    try:
        now = datetime.now()
        judge_and_write(
            digest,
            project=os.path.basename(cwd) or "unknown",
            date_str=now.strftime("%Y-%m-%d"),
            time_str=now.strftime("%H:%M"),
            session_id=session_id,
            digest_sha=digest_sha,
            prior=prior,
        )
    except Exception as exc:  # background — nothing to report to, so log it
        log(f"error: {exc!r}")
    finally:
        os._exit(0)


if __name__ == "__main__":
    main()

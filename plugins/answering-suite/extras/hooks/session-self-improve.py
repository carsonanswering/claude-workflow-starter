#!/usr/bin/env python3
"""SessionEnd hook: extract durable self-improvement lessons from the session.

Fires on /clear and exit. Cheap heuristic gate first; if passed, forks to
background and calls `claude -p` to extract 0-3 lessons (user corrections,
mistakes, wasted approaches), then writes them as feedback-type memory files
into the project's auto-memory directory so they load in future sessions.
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

LOG = Path.home() / ".claude/hooks/session-self-improve.log"
STATE = Path.home() / ".claude/hooks/session-self-improve-state.json"
MODEL = "claude-sonnet-5"
MAX_DIGEST_CHARS = 50_000
GUARD_ENV = "CLAUDE_SELFIMPROVE_HOOK"
# Other hooks' headless judge sessions also fire SessionEnd; skip those too.
FOREIGN_GUARDS = ("CLAUDE_OBSLOG_HOOK",)

MIN_USER_MSGS = 1
MIN_TOOL_CALLS = 3
MAX_LESSONS = 3

NOISE_MARKERS = ("<system-reminder>", "<local-command-stdout>",
                 "hook additional context", "Caveat: The messages below")


def log(msg: str) -> None:
    with LOG.open("a") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')} {msg}\n")


def memory_dir_for(cwd: str) -> Path:
    sanitized = re.sub(r"[^A-Za-z0-9]", "-", cwd)
    return Path.home() / ".claude/projects" / sanitized / "memory"


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


def is_real_user_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    return not any(m in stripped for m in NOISE_MARKERS)


def build_digest(transcript_path: str):
    """One pass: gate stats + compressed digest for the extractor.

    User turns kept near-full (corrections live there); assistant text and
    tool calls compressed hard.
    """
    tool_calls = user_msgs = 0
    parts = []
    for e in iter_entries(transcript_path):
        etype = e.get("type")
        msg = e.get("message") or {}
        content = msg.get("content")
        if etype == "user" and isinstance(content, str):
            if is_real_user_text(content):
                user_msgs += 1
                parts.append(f"USER: {content[:2000]}")
            continue
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if etype == "user" and btype == "text":
                text = block.get("text", "")
                if is_real_user_text(text):
                    user_msgs += 1
                    parts.append(f"USER: {text[:2000]}")
            elif etype == "assistant" and btype == "text":
                parts.append(f"ASSISTANT: {block.get('text', '')[:800]}")
            elif etype == "assistant" and btype == "tool_use":
                tool_calls += 1
                inp = block.get("input") or {}
                detail = inp.get("file_path") or inp.get("command") or inp.get("description") or ""
                parts.append(f"TOOL {block.get('name', '?')}: {str(detail)[:200]}")
    digest = "\n".join(parts)
    if len(digest) > MAX_DIGEST_CHARS:
        half = MAX_DIGEST_CHARS // 2
        digest = digest[:half] + "\n[... middle truncated ...]\n" + digest[-half:]
    return digest, {"tool_calls": tool_calls, "user_msgs": user_msgs}


def load_state() -> dict:
    try:
        data = json.loads(STATE.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    trimmed = dict(sorted(state.items(), key=lambda kv: kv[1].get("ts", ""))[-500:])
    tmp = STATE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(trimmed, indent=1))
    tmp.replace(STATE)


def already_handled(session_id: str, digest_sha: str) -> bool:
    entry = load_state().get(session_id)
    return bool(entry) and entry.get("digest_sha") == digest_sha


def record(session_id: str, digest_sha: str, files: list[str]) -> None:
    state = load_state()
    state[session_id] = {
        "digest_sha": digest_sha,
        "files": files,
        "ts": datetime.now().isoformat(timespec="seconds"),
    }
    save_state(state)


FILE_BLOCK_RE = re.compile(
    r"^FILE:\s*([a-z0-9][a-z0-9-]*\.md)\s*\nINDEX:\s*(.+?)\s*\n(.*?)\n===END===",
    re.M | re.S,
)


def extract_and_write(digest: str, mem_dir: Path, session_id: str,
                      digest_sha: str, date_str: str) -> None:
    memory_index = ""
    index_path = mem_dir / "MEMORY.md"
    if index_path.exists():
        memory_index = index_path.read_text()[:8000]

    prompt = f"""You are a self-improvement extractor for a Claude Code session. Your job: find durable LESSONS about how the assistant should work differently, and write them as memory files.

Today: {date_str}.

A lesson is durable only if it would change behavior in FUTURE sessions. Look for:
- The user correcting the assistant (wrong approach, wrong assumption, style complaint, "no, do X instead").
- An approach that wasted significant work before being abandoned — and why the failure was foreseeable.
- A non-obvious environment/workflow gotcha discovered the hard way (tool quirk, config trap).
- A confirmed preference the user expressed about HOW work should be done.

NOT lessons — output SKIP for all of these:
- Facts about the code or project state (git history and the repo already record those).
- Anything session-specific that will not recur.
- Things already covered by an existing memory (index below) — do not duplicate or rephrase them.
- Generic best practices the assistant already knows.

Existing memory index (do NOT duplicate these):
{memory_index or "(empty)"}

If no durable lessons, output exactly the single word: SKIP

Otherwise output 1-{MAX_LESSONS} blocks, each in EXACTLY this format (nothing between blocks):

FILE: <short-kebab-slug>.md
INDEX: - [<Short title>](<same-slug>.md) — <one-line hook>
---
name: <same-slug>
description: <one-line summary used for recall relevance>
metadata:
  type: feedback
---

<the lesson, 1-3 sentences>

**Why:** <what went wrong or what the user said>
**How to apply:** <concrete behavior change next time>
===END===

Rules: lowercase-kebab slugs; never include API keys, tokens, or passwords — redact as <redacted>; be strict — an empty result beats a weak lesson. Output nothing except SKIP or the blocks.

=== SESSION DIGEST ===
{digest}"""

    env = dict(os.environ, **{GUARD_ENV: "1"})
    result = subprocess.run(
        ["claude", "-p", "--model", MODEL],
        input=prompt, capture_output=True, text=True, timeout=300, env=env,
    )
    out = result.stdout.strip()
    if result.returncode != 0:
        log(f"claude -p failed rc={result.returncode}: {result.stderr[:300]}")
        return
    if not out or out.split()[0].upper().startswith("SKIP"):
        log("extractor verdict: SKIP")
        return

    blocks = FILE_BLOCK_RE.findall(out)
    if not blocks:
        log(f"bad extractor output, no FILE blocks: {out[:200]}")
        return

    mem_dir.mkdir(parents=True, exist_ok=True)
    written = []
    index_lines = []
    for filename, index_line, body in blocks[:MAX_LESSONS]:
        path = mem_dir / filename
        if path.exists():
            log(f"memory {filename} already exists, skipping")
            continue
        path.write_text(body.strip() + "\n")
        written.append(str(path))
        index_lines.append(index_line.strip())

    if index_lines:
        existing = index_path.read_text() if index_path.exists() else "# Memory index\n"
        if not existing.endswith("\n"):
            existing += "\n"
        index_path.write_text(existing + "\n".join(index_lines) + "\n")

    record(session_id, digest_sha, written)
    log(f"wrote {len(written)} lesson(s): {written}")


def main() -> None:
    if os.environ.get(GUARD_ENV) or any(os.environ.get(g) for g in FOREIGN_GUARDS):
        return  # inside a hook's own headless judge session
    payload = json.load(sys.stdin)
    transcript = payload.get("transcript_path", "")
    cwd = payload.get("cwd", "") or os.getcwd()
    session_id = payload.get("session_id") or transcript
    if not transcript or not os.path.exists(transcript):
        return

    digest, stats = build_digest(transcript)
    digest_sha = hashlib.sha256(digest.encode()).hexdigest()[:16]

    if already_handled(session_id, digest_sha):
        log(f"already handled session={session_id} digest={digest_sha}")
        return
    if stats["user_msgs"] < MIN_USER_MSGS or stats["tool_calls"] < MIN_TOOL_CALLS:
        log(f"gate skip: user_msgs={stats['user_msgs']} tool_calls={stats['tool_calls']}")
        return

    # Claim digest before forking so a duplicate fire loses the race.
    record(session_id, digest_sha, [])

    # Double-fork: detach so exit/clear is not blocked by the LLM call.
    if os.fork() > 0:
        return
    os.setsid()
    if os.fork() > 0:
        os._exit(0)
    try:
        extract_and_write(
            digest,
            mem_dir=memory_dir_for(cwd),
            session_id=session_id,
            digest_sha=digest_sha,
            date_str=datetime.now().strftime("%Y-%m-%d"),
        )
    except Exception as exc:
        log(f"error: {exc!r}")
    finally:
        os._exit(0)


if __name__ == "__main__":
    main()

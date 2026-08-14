#!/usr/bin/env python3
"""Collect running Claude state and render the dashboard HTML.

Zero-LLM: reads ~/.claude/sessions, ~/.claude/jobs, ps output; injects JSON
into template.html; writes out/dashboard.html. Prints one summary line.
"""
import json, os, re, subprocess, sys, time
from pathlib import Path

HOME = Path.home()
SKILL = Path(__file__).resolve().parent
OUT = SKILL / "out" / "dashboard.html"
NOW_MS = int(time.time() * 1000)


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def collect_sessions():
    out = []
    sdir = HOME / ".claude" / "sessions"
    for f in sorted(sdir.glob("*.json")):
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        pid = d.get("pid")
        if pid is None:
            continue
        is_alive = alive(pid)
        if not is_alive:
            continue  # dead registry entries are noise
        out.append({
            "pid": pid,
            "name": d.get("name", "?"),
            "cwd": (d.get("cwd") or "").replace(str(HOME), "~"),
            "kind": d.get("kind", "?"),
            "status": d.get("status", "?"),
            "startedAt": d.get("startedAt"),
            "updatedAt": d.get("updatedAt") or d.get("statusUpdatedAt"),
        })
    out.sort(key=lambda s: (s["status"] != "busy", -(s["updatedAt"] or 0)))
    return out


def collect_jobs():
    out = []
    jdir = HOME / ".claude" / "jobs"
    if not jdir.is_dir():
        return out
    for d in sorted(jdir.iterdir()):
        st = d / "state.json"
        if not st.is_file():
            continue
        try:
            s = json.loads(st.read_text())
        except Exception:
            continue
        result = (s.get("output") or {}).get("result") or ""
        out.append({
            "id": d.name,
            "state": s.get("state", "?"),
            "detail": s.get("detail") or "",
            "tempo": s.get("tempo") or "",
            "tokens": s.get("tokens"),
            "inFlight": (s.get("inFlight") or {}).get("tasks", 0),
            "result": result[:300],
            "updatedAt": int(st.stat().st_mtime * 1000),
        })
    out.sort(key=lambda j: (j["state"] == "done", -j["updatedAt"]))
    return out


def collect_strays(session_pids):
    """Long-running processes tied to claude scratchpads/daemons, not in the
    session registry — likely forgotten background work."""
    out = []
    try:
        ps = subprocess.run(
            ["ps", "-axo", "pid=,lstart=,command="],
            capture_output=True, text=True, timeout=10,
        ).stdout
    except Exception:
        return out
    pat = re.compile(r"claude-\d+|/claude/|litellm|scratchpad", re.I)
    skip = re.compile(r"bg-spare|bg-pty-host|daemon run|ClaudeCode\.app|refresh\.py|Chrome|Helper")
    for line in ps.splitlines():
        line = line.strip()
        m = re.match(r"(\d+)\s+(\w+ \w+ +\d+ [\d:]+ \d+)\s+(.*)", line)
        if not m:
            continue
        pid, lstart, cmd = int(m.group(1)), m.group(2), m.group(3)
        if pid in session_pids or not pat.search(cmd) or skip.search(cmd):
            continue
        if cmd.strip() == "claude" or cmd.startswith("/Users") and "/versions/" in cmd:
            continue  # plain interactive claude already covered by registry
        out.append({"pid": pid, "started": lstart, "cmd": cmd[:160]})
    return out[:20]


def main():
    sessions = collect_sessions()
    jobs = collect_jobs()
    strays = collect_strays({s["pid"] for s in sessions})
    busy = sum(1 for s in sessions if s["status"] == "busy")
    running_jobs = sum(1 for j in jobs if j["state"] not in ("done", "error"))
    data = {
        "generatedAt": NOW_MS,
        "host": os.uname().nodename,
        "sessions": sessions,
        "jobs": jobs,
        "strays": strays,
        "counts": {
            "sessions": len(sessions),
            "busy": busy,
            "jobs": len(jobs),
            "runningJobs": running_jobs,
            "strays": len(strays),
        },
    }
    tpl = (SKILL / "template.html").read_text()
    html = tpl.replace("/*__DATA__*/null", json.dumps(data))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)

    state_file = SKILL / "state.json"
    url = ""
    if state_file.is_file():
        try:
            url = json.loads(state_file.read_text()).get("artifactUrl", "")
        except Exception:
            pass
    print(f"sessions={len(sessions)} busy={busy} jobs={len(jobs)} "
          f"running_jobs={running_jobs} strays={len(strays)} out={OUT} url={url or 'UNSET'}")


if __name__ == "__main__":
    main()

---
name: running-view
description: Refreshes the artifact dashboard of what is running right now — live Claude sessions, background jobs, stray processes.
disable-model-invocation: true
---

# running-view — what's running, one artifact

Token rule: do NOT read, summarize, or reason about the dashboard data. The
script does everything. Your whole job is the three steps below.

1. Run:

```bash
python3 ~/.claude/skills/running-view/refresh.py
```

It prints one summary line: `sessions=N busy=N jobs=N running_jobs=N strays=N out=<path> url=<artifact url>`.

2. Publish that `out` path with the Artifact tool, passing `url` from the
   script output (keeps the permanent URL). favicon `🛰️`, keep title/description.
   If url=UNSET, publish without `url`, then write the new URL into
   `~/.claude/skills/running-view/state.json` as `{"artifactUrl": "..."}`.

3. Reply to the user with ONLY the summary line numbers + the artifact link.
   Do not open or describe dashboard.html.

Only if the user explicitly asks for analysis of what's running (e.g. "which of
these can I kill?"), spawn ONE `general-purpose` agent with the JSON from
`out/dashboard.html`'s `__DATA__` blob and let it do the reading — the frontier
session stays on the summary line.

Data sources (maintained in refresh.py, filesystem-only): `~/.claude/sessions/*.json`
(live pids), `~/.claude/jobs/*/state.json` (background jobs), `ps` scan for stray
scratchpad/litellm processes.

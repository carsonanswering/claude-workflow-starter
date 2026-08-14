---
name: tracker-refresh
description: Refreshes the AnsweringRND tracker dashboard artifact — claimed and in-flight issues, work ready for agents, decisions waiting on Carson.
disable-model-invocation: true
---

# tracker-refresh

Token rule: do NOT read, summarize, or reason about the dashboard data. The script does everything. Your whole job is the three steps below.

1. Run:

```bash
bash ~/.claude/skills/tracker-refresh/refresh.sh
```

It prints one summary line: `open=N inflight=N ready=N needsyou=N out=<path> url=<artifact url>`.

2. Publish that `out` path with the Artifact tool, passing `url` from the script output (keeps the permanent URL). favicon `🧭`, keep the existing title and description.
   If `url=UNSET`, publish without `url`, then write the new URL into `~/.claude/skills/tracker-refresh/state.json` as `{"artifactUrl": "..."}`.

3. Reply with ONLY the summary numbers and the artifact link. Do not open or describe `dashboard.html`.

If the script exits non-zero or its Python step raises on empty/invalid `viz-data.json`, the `gh` fetch inside `projs/tracker-live/build.sh` failed — and that script truncates `tracker.json` with `> tracker.json` before `gh` runs, so the data chain is already blown away. Leave the old artifact standing (a stale dashboard beats a blank one), run `cd /Users/kai/projs/tracker-live && ./build.sh` to surface the real error (usually `gh auth status` or network), fix that and rerun step 1. If it fails a second time, tell Carson which command failed and with what error instead of publishing.

There is nothing to delegate: the pipeline is a `gh` query, a `jq` reshape, and a template fill; only the Artifact publish needs a session.

Data source: `projs/tracker-live/build.sh` — `gh issue list` plus the first `🔒 claim` comment per assigned issue, which is what identifies the holding session.

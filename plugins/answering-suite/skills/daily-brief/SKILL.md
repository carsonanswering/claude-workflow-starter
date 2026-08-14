---
name: daily-brief
description: Daily industry brief for the AI-agent / AI-answering space — what moved in 24h that changes a Answering decision, posted to Slack. Use when the user says "/daily-brief", "brief me", or "what happened in the space". For competitor-specific tracking use comp-watch instead.
---

# daily-brief

The morning read for Carson and Carson: what moved in the last 24 hours that changes
a decision. Not a news feed — a decision feed.

Repo: the repo root (current checkout). Read `core/DOCTRINE.md` first — it
defines the delta contract, id rules, citation rule, and Slack format.

## The bar

An item earns a slot only if a reasonable person could say **"that changes what
we build, buy, or say this week."** Model benchmark chatter, funding outside the
space, and generic "AI is big" coverage all fail this bar.

Target 3-6 items. Fewer is fine. Zero is fine and gets the quiet line.

## Run

### 1. Sweep

Run these in parallel with WebSearch, scoped to the last 24-48h:

- **Model / platform** — new Claude, GPT, or Gemini releases; context-window or
  pricing changes; agent-SDK or MCP spec changes
- **Agent infra** — MCP ecosystem, memory-layer libraries, retrieval tooling,
  agent permission and identity tooling
- **Money** — funding and M&A in enterprise knowledge, meeting intelligence, agent infra
- **Regulatory / trust** — AI data residency, enterprise AI security incidents,
  SOC2 and EU AI Act developments touching workplace AI
- **Distribution** — Slack, Microsoft Teams, Notion, Google Workspace platform or
  API changes that open or close a channel for an in-chat product

Fetch the primary source for anything promising. An aggregator's summary is not
a citation.

A lane is done when every subtopic named in its bullet has had at least one
targeted query, and every hit that could clear the bar has had its primary
source fetched. All five lanes are accounted for every run: a lane that turned
up nothing is reported as swept-and-empty, and a lane whose sources failed goes
in the step 4 footer.

### 2. Score

Give every candidate a `so_what` — one sentence naming the concrete implication
for Answering. If the `so_what` can't be made specific, drop the item.
"This shows AI is moving fast" is not a `so_what`.

### 3. Diff

Ids must survive restatement — use the canonical URL slug or
`<company>-<event-type>-<date>`, never a hash of the headline. The date in an id
is **the event's own date** as the primary source gives it, fixed the first time
you mint the id — never the day you saw it, or a story trending for three days
mints three ids and posts three times:

```json
{
  "id": "anthropic-mcp-scoped-permissions-2026-07-24",
  "name": "MCP spec adds scoped resource permissions",
  "summary": "...",
  "so_what": "Row-level security may come for free from the protocol layer.",
  "url": "https://...",
  "category": "agent-infra",
  "date": "2026-07-24"
}
```

Write this run's candidates as a JSON array to
`state/daily-brief-observations.json` at the repo root (shell variables do not
survive between Bash calls, so the JSON travels through a file, not an `echo`),
then diff it:

```bash
cd "$(git rev-parse --show-toplevel)"
cat state/daily-brief-observations.json | python3 bin/delta.py daily-brief --format json
```

State suppresses anything already briefed, so a story that trends for three days
posts once.

The delta decides **which** items post — the entries under `new` and `changed`,
and nothing else. It does not write the post: `bin/delta.py`'s markdown renderer
drops `so_what`, which is the whole scoring axis, so read the JSON and compose
every line yourself in step 4's format.

### 4. Post

Slack `#daily-updates` (`C0BKPEEE2TG`), headed `*Daily brief* — <YYYY-MM-DD>`.
Send with `slack_send_message`, resolving its live MCP prefix from the loaded
tools — `mcp__plugin_slack_slack__*` is the common case; if it is absent, search
the loaded tools for `slack send message` and use the prefix this session
exposes. Per item:

```
• *<headline>* — <one line, what happened>. <so_what> <url|source>
```

Close with one `*Worth a decision:*` line naming the single item that needs Carson
or Carson to act. Omit the line entirely if nothing does — do not invent an
action to fill it.

If the delta JSON came back with `"quiet": true`, post the one-line quiet
message and stop.

Append source failures as a footer per doctrine §7.

### 5. Persist

Write `reports/daily-brief-<YYYY-MM-DD>.md`, then commit per doctrine §6.

---
name: comp-watch
description: Competitive watch over the company-brain / org-memory watchlist — posts only what changed. Use when the user says "/comp-watch", "competitor update", "what did competitors ship", or "TAM update". Not for one-off research on a single company.
---

# comp-watch

Daily competitor tracking for Cortex Brain. Reports the **delta** in the
company-brain / org-memory / meeting-intelligence space since the last run.

Repo: the repo root (current checkout). Read `core/DOCTRINE.md` before doing
anything — it defines the delta contract, id rules, citation rule, and Slack
format.

## Run

### 1. Load the watchlist

Read `watchlist.json` at the repo root. Each entry:

```json
{
  "id": "glean",
  "name": "Glean",
  "domain": "glean.com",
  "segment": "enterprise-search",
  "tier": "direct",
  "watch_urls": {"pricing": "...", "changelog": "...", "blog": "..."}
}
```

Only entries with `"active": true` are polled. `tier: "direct"` gets full
polling every run; `tier: "adjacent"` and `"platform-risk"` get polled on the
weekly deep run (see step 4).

### 2. Poll

For each active entry, fetch its `watch_urls` with WebFetch. Extract into one
observation object per company:

```json
{
  "id": "glean",
  "name": "Glean",
  "segment": "enterprise-search",
  "pricing": "<current published price, or 'contact sales'>",
  "latest_release": "<most recent changelog entry title + date>",
  "latest_post": "<most recent blog post title + date>",
  "positioning": "<their current one-line self-description from the homepage>",
  "funding": "<last round + amount + date, if newly announced>",
  "security_claims": "<SOC2 / row-level security / FedRAMP claims currently on the site>",
  "url": "<canonical source URL for whatever changed>"
}
```

`url` is the citation (doctrine §3), not a change detector: `core/store.py`
diffs with `NOISE_FIELDS`, which ignores `url` alongside the rest of doctrine
§4's list, so a page that only moves address must land in `positioning`,
`pricing` or `latest_release` to reach the post.

**Row-level security is table stakes, not a differentiator** — Glean, Gemini
Enterprise, Rovo, Box AI, Dropbox Dash, Coveo and M365 Copilot all market
ACL-mirroring as a headline claim, so record `security_claims` everywhere and
treat it as routine. The narrow, real gap: **Otter and Granola**, the two
fastest-moving direct threats, ship org-wide knowledge features with *no
published permission model at all*. First appearance of one on either is a
**tier-one alert** — step 5 says what that does to the post.

Omit a field entirely rather than guessing it. A field that flips between a
guess and a real value manufactures a fake change event.

Poll concurrently. If a source fails, record the failure and continue — step 5
reports it. Done when every company polled this run holds either an observation
object or a recorded failure.

### 3. Category discovery

Read `state/comp-watch.json` and list the `entities` keys prefixed `new:` —
entrants proposed on an earlier run. Re-emit each unchanged in this run's
observation array so it stays live in state instead of decaying into `_Not seen
this run_`, and leave it out of the post: it was news once.

Then WebSearch for genuinely new entrants, not for restating known ones:

- `"company brain" OR "org memory" startup funding 2026`
- `"agentic memory layer" OR "memory layer for agents" launch`
- `enterprise AI knowledge "row-level security" launch`
- `AI meeting assistant Series A 2026`

Surface a company only when it is (a) absent from `watchlist.json`, (b) absent
from state as a `new:` id, and (c) traceable to a dated page from the last 30
days. Give it the id `new:<slug>` — the prefix keeps it distinct from the polled
id it earns on promotion — plus `segment`, `tier`, `discovered_via` and `url`,
and put it in the observation array, so state remembers it and the same startup
is not rediscovered every morning. Leave `watchlist.json` alone — propose it in
the post and let Taj promote it.

Done when every `new:` id in state is either re-emitted in this run's array or
already promoted into `watchlist.json` under its polled id.

### 4. Weekly deep run

On Mondays (or when invoked as `/comp-watch deep`), add three things:

**Wider poll.** Poll `adjacent` and `platform-risk` alongside `direct`.

**Existence check.** An acquisition or shutdown is the single highest-value
signal this tool can produce, and it only shows up if you look:

```bash
cd "$(git rev-parse --show-toplevel)" && python3 bin/check_urls.py
```

It HEAD-then-GET probes every watch URL of every active entry and exits non-zero
if any failed. A company still exists when at least one of its `watch_urls`
returns 200. Give every `FAIL` line one of two verdicts before moving on: *URL
moved* (find the live replacement and flag it for Taj) or *company gone* —
confirm with WebSearch `<name> acquired OR "shut down" OR sunset`, and a
confirmed exit leads the post.

**Calendar.** Read `scheduled_events` in `watchlist.json` and post a line for
any event whose `when` falls inside the next ~45 days, carrying its `why` and
watch_urls. (`yc-s2026-demo-day` is `~Aug/Sep 2026`: expect a *cohort* of
same-thesis startups, not scattered entrants.)

Pipe this run's delta with `--prune` (step 5). The deep run is the only one that
polls every tier, so it is the only run where absence means gone; daily runs
leave state alone.

### 5. Diff and post

Write all observations to a JSON array and pipe them through the delta engine:

```bash
cd "$(git rev-parse --show-toplevel)"
echo "$OBSERVATIONS_JSON" | python3 bin/delta.py comp-watch
echo "$OBSERVATIONS_JSON" | python3 bin/delta.py comp-watch --prune   # Monday deep run only
```

Post the output to Slack `#daily-updates` (`C0BKPEEE2TG`) with the Slack MCP
tool whose name ends `slack_send_message`, resolving its live prefix from the
loaded tool list (currently `mcp__plugin_slack_slack__`) rather than assuming
one. Head the post `*Competitive watch* — <YYYY-MM-DD>`.

A tier-one alert (step 2) leads: put it above the delta body as `*TIER-ONE* —
<what happened> — <url|label>`, keep it whole when trimming to doctrine §5's ~40
lines, and post the run even if the tool printed `QUIET`.

Otherwise, if the tool printed `QUIET`, post the one-line quiet message and
stop. Do not manufacture content.

When the delta exceeds one post (~40 lines per doctrine §5), open
[`signal-ranking.md`](signal-ranking.md) and lead in that order, cutting from
the bottom.

Append any failures as a footer per doctrine §7.

### 6. Persist

Write the full observation set to `reports/comp-watch-<YYYY-MM-DD>.json`, then
commit `state/` and `reports/` per doctrine §6.

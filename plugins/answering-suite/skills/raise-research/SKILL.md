---
name: raise-research
description: Raise research for the Answering pre-seed. Use when the user asks for raise research or fundraise prep, wants investor targets or a funder shortlist, wants comparable raises benchmarked, or wants an investor email, DM, or intro request drafted.
---

# raise-research

Two research lanes for the Answering pre-seed (AnsweringRND org, targeted ~3 months out), synthesised into one dated targets file. Lane A is **comparable raises**, lane B is **investor targets**. Outbound drafts are a separate, gated branch (step 4).

Two rules bind every run.

**Every row is sourced.** A row carries a URL to a **primary** page — the company's own announcement, a filing, a fund page, or a dated article. A search-engine AI overview is not a source: on 2026-07-31 a Basis Set "Agentic Memory Track" taken from a search summary became a tracker ticket and turned out not to exist (`/Users/kai/projs/answering-gtm/HANDOFF-2026-08-01.md`). An unsourced row is dropped, not softened to "reportedly".

**Every self-claim carries a verdict.** A statement about what Answering does reaches an outbound draft only after it maps to a verified id in `/Users/kai/projs/answering-raise/claims/ledger.json` or `claim-verifier` returns SUPPORTED against the repo. Everything else stays under `## Unverified — internal only` in the targets file. The v1 one-pager shipped four claims that failed a code truth-check on 2026-07-25 — confidence tiers, a freshness SLA, speaker-level provenance, and an MCP server — all four false against the repo (`/Users/kai/projs/answering-raise/README.md`).

## 1. Scope the ask into lanes

Name which lanes this ask needs; a request for only comparables or only targets runs that lane alone.

Read the prior art before dispatching anything, so the agents research forward instead of re-deriving:

- `/Users/kai/projs/answering-gtm/research/round-benchmarks.md` — lane A prior art: pre-seed size, instrument, cap and timeline benchmarks.
- `/Users/kai/projs/answering-gtm/research/investor-targets.md` — lane B prior art: a **verified conflict map** plus an unverified candidate list. It contains no ranked target list; that pass was blocked on search budget.
- `/Users/kai/projs/answering-gtm/research/vc-landscape.md` — the earlier landscape sweep.

Then write down two things both lanes are matched against:

- **The positioning line.** Carry forward the one at the head of `investor-targets.md` unless the user gives a newer one. The ICP decision was still open on 2026-08-01, so confirm the line with the user rather than assuming it settled.
- **The conflicted names**, from the exclusion map — so lane B reports them as conflicted rather than surfacing them as fresh leads.

Done when: the lanes are named, the three prior-art files are read, one positioning line is written down, and the already-verified conflicted investors are listed by name.

## 2. Fan out one web-researcher per lane

Research carries no falsifiable question, so bound it with fixed sub-queries and a row schema instead (the research-family exception in `team-orchestration`). Name each agent at spawn — `raise-comparables` and `raise-investors` — because the name is the only handle for `SendMessage` and `TaskStop`.

Hand each agent: the positioning line and conflicted names from step 1, its sub-queries verbatim as a numbered list, its row schema, and these bounds:

- Return rows in schema, one per line. `no reliable source found for <sub-query>` is the correct answer for an empty query.
- Fetch the primary page before a fact becomes a row.
- Cap at ~25 searches and return partial on hitting it. The session shares one WebSearch quota: on 2026-07-31 an eight-agent fleet exhausted 200 calls, and the three named lists it was launched to produce were exactly the three that never arrived.
- No output path — the digest lines are the input to step 3, and a dossier on disk would only need re-reading.

**Lane A — comparable raises.** Seed set from prior art: Mem0, Zep, Letta, Cognee, Supermemory, Onyx, Credal.

1. Pre-seed and seed rounds announced since 2025-01 by the seed-set companies: amount, lead, date.
2. Rounds in the same window for AI-answering, voice-agent, or front-desk-automation startups outside the seed set.
3. The one-line wedge each raising company sold, in its own announcement wording.
4. Whether the company was pre-revenue at raise, and what signal stood in for revenue (design partners, pipeline, pedigree).
5. Rounds in the category announced in the last 90 days.
6. Contradicting angle: category companies that raised flat or down, shut down, or were acqui-hired.

Row schema: `company | round | amount | lead | date | one-line wedge | source URL`

**Lane B — investor targets.**

1. Seed and pre-seed funds that *led* a round in agent memory, context layers, or AI agent infrastructure in the last 12 months — fund plus the partner who led it.
2. Angels with public confirmation of a check into any seed-set company.
3. Funds publishing a thesis on agent memory, context, or governance, with the thesis line quoted short.
4. Portfolio conflicts for each candidate against the seed set — the exact competitor and round.
5. Typical check size, and whether they lead or follow.
6. Published entry route: application form, scout, program, or a partner's stated inbound preference.

Row schema: `fund or angel | partner | check size + leads? | relevant portfolio | thesis-fit line | conflict (competitor + round, or "none found") | warm-path guess | source URL`

A conflicted name stays in the output, marked in its conflict column. Thesis-matched-and-conflicted is not thesis-matched-and-reachable: an earlier pass presented four conflicted partners as reachable, and cold-approaching them would have burned the meetings.

Done when: both agents have returned, every row is in schema with a URL, every sub-query has either rows or an explicit no-source line, and unsourced rows were dropped rather than carried forward.

## 3. Write the dated targets file

Write `/Users/kai/projs/answering-gtm/raise/<YYYY-MM-DD>-targets.md`, creating `raise/` if it is absent. If a file already carries today's date, ask before overwriting — it may be another session's pass.

Sections, in order:

1. **Header** — date, which lanes ran, the positioning line matched against, and whether either agent hit its search cap.
2. `## Lane A — comparable raises` — a table on the lane A schema, newest round first.
3. `## Lane B — investor targets` — a table on the lane B schema, best fit first, conflicted rows kept and marked.
4. `## Gaps` — one line per sub-query that returned no source, so the next pass resumes here instead of rediscovering the same emptiness.
5. `## Unverified — internal only` — every Answering self-claim used to reason about fit that has no ledger id or verdict yet. Nothing in this section is quotable outward.

Done when: every row in both tables ends in a source URL, every step-2 sub-query appears as rows or a Gaps line, and the header states the positioning line the research was matched against.

## 4. Outbound drafts, on request only

A research run stops at step 3. Drafting starts when the user asks for an email, DM, or intro request — and every factual sentence about Answering passes the verdict gate first:

1. **Check the ledger.** `cd /Users/kai/projs/answering-raise && python3 bin/ledger.py check "<sentence>"`. `claims/ledger.json` is the source of truth for what an email may assert; a mapped claim goes out in the ledger's own wording.
2. **Unmapped claims go to `claim-verifier`**, with the claim list and repo paths `/Users/kai/projs/meeting-copilot` and `/Users/kai/projs/answering`. SUPPORTED goes out as stated. PARTIAL goes out only in the narrower form the verdict names. UNSUPPORTED and CONTRADICTED go to the `Unverified` section and stay internal.
3. **Editing `claims/ledger.json` is Carson's call** — adding a claim, or any change that would make a held draft pass, stops and asks.

Then open [`outreach.md`](outreach.md) for the skeletons, the routing between them, and the send-side bars.

Done when: every factual sentence in the draft names either its ledger claim id or its claim-verifier verdict line, and the drafts sit on disk unsent.

## 5. Verify before finishing

Check each, and fix what fails:

1. Every row in both tables carries a source URL.
2. Every Answering self-claim in the file or a draft carries a ledger id or a verdict, and unverified ones sit only in the `Unverified` section.
3. Every sub-query is answered by rows or named in Gaps.
4. Conflicted investors are present and marked, not quietly dropped.
5. Nothing went outward. Sending an email or DM, adding a target to the answering-raise send pipeline, and editing the claims ledger are all Carson's calls.

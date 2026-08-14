---
name: lightning
description: Stepped-leader exploration. Use when debugging with several plausible suspects, when choosing among candidate approaches, when an investigation is looping or drifting, when an exploration risks reading everything, or when the user says "/lightning", "lightning", or "probe it". Pairs with ooda - OODA governs the loop, lightning governs each probe.
---

# Lightning

Lightning reaches ground by a stepped leader: it extends one tentative channel at a time. When a channel stops finding conductive air, it retreats to the last branch point and extends a different channel from there — never back to the cloud. Full current flows only after one channel connects: cheap tentative probing, then total commitment.

Every candidate carries one of seven status tokens, defined once in **Trace — pinned format** below alongside the trace they render into.

## States

You are always in exactly one named state; if you cannot name your state, you are in BRANCH — write the branch record now.

| State | You are | Legal exits |
|---|---|---|
| BRANCH | writing or updating a branch-point record | PROBE — mark exactly one candidate `◀ LIVE` |
| PROBE | running one pre-stated falsifiable probe on the LIVE candidate | kill → BRANCH at the same frame; validate → DISCHARGE, or a child BRANCH if a sub-question opens; inconclusive → one redesign, then `unproven` and back to BRANCH; frame exhausted → POP |
| POP | closing an `EXHAUSTED` frame | BRANCH at the parent frame |
| DISCHARGE | executing the validated path to completion | done — or BRANCH at whichever frame a new contradicting observation invalidates |

## BRANCH — write the record before descending

At every decision point, before descending anything, write a branch-point record: an id (`B0`, `B1`, …), the one-sentence question this fork resolves, 2–5 candidate paths (`P1`, `P2`, …) each carrying a status token — and name every plausible candidate first, because a candidate you never named is a candidate you can never backtrack to.

Branch-point records form a stack: push a frame on each descent, pop a frame on exhaustion. The written stack — not memory, not scrollback — is what makes backtracking cheap, because popping resumes an already-written frame with its question and surviving candidates intact instead of re-deriving context from scratch.

## PROBE — one channel, falsifiable, cheapest first

From the current branch point, select the single most promising `queued` candidate and mark it `◀ LIVE`. Exactly one candidate is LIVE anywhere in the stack at any moment; descending two in the same turn is forbidden because parallel deep dives multiply token cost and yield two half-answers that neither validate nor kill.

Before descending the LIVE candidate, write the cheapest probe that could *kill* it plus the specific observation that constitutes the kill, stated in advance — a probe qualifies only if you can name an outcome that kills the path, so if no outcome could kill it, redesign it before running anything.

- Cheapest sufficient instrument, in order: one targeted grep, one line-ranged read, one command, one function read. Whole-file reads and directory sweeps are not probes, because they buy context rather than a verdict.
- Descend only far enough to run the probe, because anything built before the probe returns is waste if the probe kills the path.
- Between two comparable candidates, prefer the one whose probe disqualifies faster, because a fast kill frees the frame sooner than a slow maybe.

## Transitions — the four probe outcomes

| Probe outcome | Required move |
|---|---|
| Kill observation seen | Mark `✗ dead: <one-line reason>`. Control returns to the exact branch point the candidate forked from — not the task start, not the previous turn's file — because that fork still holds every candidate not yet ruled out. The next `queued` candidate there goes LIVE. Discard everything learned below the dead candidate except the one-line reason, because dead-path detail is context you will never act on. |
| Viability confirmed | Mark `✓ validated` and go to DISCHARGE. If validation raises a new sub-question, push a child branch point under the validated path and continue there. |
| Inconclusive | At most one sharper redesign of that probe; if still inconclusive, mark the candidate `unproven` — it counts as neither dead nor alive — and move to the next candidate, because a probe that cannot decide is measuring the wrong thing. Three inconclusive probes at one branch point means the branch question itself is wrong: restate the question yourself when you can name a sharper one the same evidence would answer, and escalate to Carson when you cannot name it. |
| New candidates discovered mid-probe | Insert them as `queued` at the branch point they actually belong to — often an ancestor, not the current frame — because a candidate filed at the wrong fork is invisible when that fork is revisited. |

## POP — exhaustion

When every candidate at a branch point is `dead` or `unproven`, mark the frame `EXHAUSTED`, pop it, and resume at its parent by taking the parent's next `queued` candidate — the pop is cheap precisely because the parent frame is already written down. The path that spawned the popped frame inherits its verdict: `✗ dead: <frame> EXHAUSTED — <one-line reason>` when every child died, `unproven` when any child survived unproven.

`unproven` is the one status a redesign can reopen, where `✗ dead` is final. Once a frame's `queued` candidates are spent, an `unproven` candidate may go LIVE again under a *different instrument* — never the same probe run harder — and when no cheaper decisive instrument exists, the frame is `EXHAUSTED` and pops.

## ⚡ DISCHARGE — total commitment

On validation, stop probing and commit to the path completely: execute to completion with no hedged partial implementation, no alternative kept warm, and no further evidence gathered for a conclusion already reached, because post-validation evidence buys confidence, not progress. Self-check: if your last action added confidence rather than progress, the discharge has not started. The one legal way back into the stack is a *new contradicting observation* during execution — re-enter at the branch point that observation invalidates, never at the top.

## Trace — pinned format

- Markers — the seven status tokens, defined here and used everywhere in this skill: `queued` = named, not yet probed · `◀ LIVE` = the one candidate being probed right now · `✗ dead: <one-line reason>` = its kill observation was seen · `unproven` = probed, neither killed nor validated · `✓ validated` = viability confirmed · `EXHAUSTED` = every candidate at a frame is dead or unproven · `⚡ DISCHARGE` = probing over, full commitment to the validated path.
- Frames: `B0`, `B1`, … for branch points; `P1`, `P2`, `P3a`, … for paths, indented under their branch point. A child branch point gets its own line, indented under the path that spawned it, carrying its branch question.
- The `LIVE` line names the probe and its kill condition inline, so the next legal move is always visible without a separate footer.
- The whole trace stays under ~12 lines — it is a map, not a log: prune nothing, but never narrate inside it. When it would run over, collapse each `EXHAUSTED` subtree into the single inherited verdict line on its parent path and keep every `queued`, `unproven`, `◀ LIVE`, and `✓ validated` candidate visible, because a popped frame is the one region you will never re-enter.
- Re-emit rule: emit the trace at the first branch point, then re-emit the *whole current trace* on every branch event — new branch point, kill, pop, validation, discharge — never as a diff and never as a partial, because re-emitting whole is what stops the trace decaying over a long session, and that is the only reason Carson can see the bolt's shape and catch a wrong turn early.
- Worked traces for the kill, child-branch nesting, and pop cases: see [TRACES.md](TRACES.md) — open it before emitting your first trace of the session, and again the first time a frame nests or exhausts.

## Compliance triggers — signal → required next move

- Your own reasoning contains "or maybe" / "it could also be" / "alternatively" → that is an unrecorded branch point; emit the branch block now.
- A probe just returned negative → next output is the kill line, not another probe on that path.
- A probe just returned positive → next output is `✓ validated` plus the discharge marker (or the child branch block it opens), not another probe.
- You are about to read a whole file or directory → find the grep or line range that could kill the path instead.
- You are about to run a third probe on one path with no new information since the second → that path is being nursed; kill it or discharge it.

## Subagents

A subagent is one probe: hand it one narrow falsifiable question plus the kill condition, and require back a conclusion with a kill-or-live verdict — never an open sweep or a file dump, because a dump moves the reading cost into your context instead of removing it. Do not fan out one subagent per candidate, because that is a parallel deep dive with extra steps. Do not delegate what finishes in a handful of tool calls, because spawn overhead then exceeds the probe itself.

## Exit

The run ends at a completed discharge, or at an honest report that `B0` is `EXHAUSTED`, with the trace as evidence of what was ruled out. Root exhaustion means the framing was wrong, and you cannot fix your own framing by trying harder — present the tree with every kill reason, name the candidates still `unproven` and the instrument that would decide each, and ask Carson which assumption to reopen.

## Anti-patterns

| Failure mode | Mechanism it violates |
|---|---|
| Restarting from the top after a kill ("back to the cloud") | Kill transition — control returns to the exact fork |
| Re-running a dead path unchanged with more effort | `✗ dead` is final — only a new observation reopens a frame |
| Unfalsifiable probes ("read the module to understand it") | Falsifiability gate — no nameable kill outcome |
| Silent branching — descending before candidates are enumerated | BRANCH record — nothing named, nothing to backtrack to |

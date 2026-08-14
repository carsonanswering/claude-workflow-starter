---
name: ooda
description: Military OODA loop (Observe, Orient, Decide, Act) as an operating cadence. Use at the start of any nontrivial task, when new information invalidates the current plan, when stuck or looping, or when the user says "ooda", "re-orient", or "reassess". Pairs with the lightning skill - OODA governs the loop, lightning governs each probe.
---

# OODA Loop

Boyd's decision cycle from military aviation: **Observe → Orient → Decide → Act**, repeated fast. Victory goes to whoever cycles the loop faster and re-orients honestly when reality disagrees with the plan.

## The four phases

### 1. Observe — gather raw signal

- Collect the minimum facts needed to orient: error text, failing test output, file layout, user's actual words.
- Use lightning probes: cheapest observation first (one grep, one command, one line-ranged read).
- Observe reality, not assumption. Run the command instead of predicting its output. Read the actual error instead of pattern-matching to a remembered one.
- Bound it: once three observations are in, Orient on what you have. Observation without orientation is token burn.

### 2. Orient — the decisive phase

- Fit observations into a model: what is actually happening and why?
- This is where bias dies or wins. Explicitly ask: "What would make my current hypothesis wrong?" If an observation contradicts the working theory, the theory loses, not the observation.
- Destroy and rebuild: when evidence breaks the model, discard it fully rather than patching it. Sunk analysis is sunk.
- State orientation in one or two sentences before deciding. If it can't be stated, return to Observe.

### 3. Decide — pick one path

- Choose the single next action that best tests or advances the orientation. Not a five-step plan - one step with a falsifiable expected outcome.
- Prefer decisions that are cheap to reverse and fast to validate.
- If two paths look equal, pick the one that disqualifies faster (lightning rule).

### 4. Act — execute and feed back

- Execute the decision fully. No half-actions that produce ambiguous signal.
- The result of Act is the input to the next Observe. Compare outcome to the expected outcome from Decide; mismatch means re-Orient, not retry-harder.
- Never repeat a failed action unchanged. A second identical attempt is a skipped Orient phase.

## Cadence rules

- **Every run starts with one explicit cycle**: observe the request and context, orient on what is really being asked, decide the first probe, act.
- **Tempo beats thoroughness**: many small cycles outperform one giant Observe. If a phase runs long, cut it and cycle.
- **Re-enter the loop on surprise**: any unexpected result (test fails differently, file missing, output weird) forces a fresh Orient. Do not bolt surprises onto the old plan.
- **Getting inside the problem's loop**: for debugging, cycle faster than the failure can hide - tighten the reproduction, shrink the search space each cycle.
- **Exit condition**: loop ends when Act produces the validated result - for an investigation, the observation that settles the question; for a build or a write, the check that runs green (test, command, or the user-visible behaviour). Name that check while you are still in Decide, and per lightning, stop the moment it passes: no extra confirming evidence.

## Subagents

- Each subtask handed to a subagent is one Decide→Act arc: narrow, falsifiable, with an expected outcome stated in the prompt.
- Subagent results are Observations for the parent loop - the parent re-Orients on them; it does not blindly merge them.

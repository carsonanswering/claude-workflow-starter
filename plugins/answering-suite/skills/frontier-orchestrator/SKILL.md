---
name: frontier-orchestrator
description: Orchestrate with Fable 5 as planner/synthesizer and cheap Sonnet/Haiku subagents as workers. Use when a task is big enough to decompose — multi-file audits, migrations, broad research, a fleet of issue-solving workers — and frontier reasoning should not pay for every unit of work. Trigger on "frontier orchestrator", "fable orchestrate", "plan with fable, work with sonnet".
---

# Frontier Orchestrator

Fable 5 thinks. Sonnet and Haiku do the legwork. Cost lives in the fan-out, so keep the fan-out cheap. Once the fan-out is live, your job changes from planning to supervising — and supervision is where a real 5-worker run lost the most time.

`team-orchestration` is the hub and owns the general doctrine: whether to delegate at all, which agent type to pick, how teammates communicate. This skill is the depth it points at — the price model behind every model and effort choice, the full fleet dispatch brief, and the supervision probes. When the two files describe the same rule, the one-line version there is the rule and the detail here is the elaboration.

## Cost model (why this exists)

Per 1M tokens:

| Model | ID | Input | Output |
|---|---|---|---|
| Fable 5 | `claude-fable-5` | $10 | $50 |
| Sonnet 5 | `claude-sonnet-5` | $3 | $15 ($2/$10 intro through 2026-08-31) |
| Sonnet 4.6 | `claude-sonnet-4-6` | $3 | $15 |
| Haiku 4.5 | `claude-haiku-4-5` | $1 | $5 |

Fable output costs 10x Haiku output and 3.3x Sonnet output. One Fable plan plus twenty Sonnet workers costs far less than twenty Fable workers, and usually beats twenty Sonnet workers driven by a Sonnet planner.

These figures were current in August 2026 and the Sonnet 5 intro rate expires 2026-08-31. Past that date, re-check Anthropic's published pricing before quoting a dollar figure to the user. The ratios are what drive the tiering below, and they survive small price moves.

## Version pinning: read before assuming it works

The `Agent` and `Workflow` tools take a `model` parameter whose only accepted values are `opus`, `sonnet`, `haiku`, and `fable`. These are tier aliases, not version pins. `model: "sonnet"` resolves to whichever Sonnet the session is configured for. Passing a versioned string such as `sonnet-4-6` is an invalid enum value and the call fails.

If a specific Sonnet version is genuinely required, the Agent tool is the wrong surface — call the Anthropic API directly (`client.messages.create(model="claude-sonnet-4-6", ...)`) from a script. Never describe a subagent as having run on a specific Sonnet version when it was dispatched through the alias.

## The shape

Three phases. Fable at both ends, cheap models in the middle.

1. **Plan (Fable).** The main thread is the orchestrator. Decompose the task into independent work items. Do this inline; do not spawn a subagent to plan.
2. **Fan out (Sonnet / Haiku).** One subagent per work item, running concurrently. Pick the tier per item using the table below. Every subagent returns structured data rather than prose.
3. **Synthesize (Fable).** The main thread reads the returns, resolves conflicts between them, and writes the answer. Cross-item judgment is Fable's job and is where the spend is justified.

## Tier selection per work item

| Give it to | When |
|---|---|
| `haiku` | Mechanical and verifiable. Locate a symbol, list files matching a pattern, extract fields, run a command and report its output, apply a rename. No judgment call in the output. |
| `sonnet` | Bounded judgment. Review one file, implement one well-specified function, summarize one document, verify one claim. A wrong answer is recoverable because a later stage checks it. |
| `fable` | Only when an item is as hard as the whole task and cannot be split further. If most items are landing on Fable, the decomposition failed — split harder. |

Default to `sonnet`. Escalate an individual item to `fable` only after a Sonnet attempt comes back visibly thin.

## Using the Agent tool

Independent items go in a single message so they run concurrently:

```
Agent(subagent_type: "Explore", model: "haiku", prompt: "...")            # locate
Agent(subagent_type: "general-purpose", model: "sonnet", prompt: "...")   # judge
```

Ask every subagent for a compact structured return. Its final message becomes the tool result injected back into the orchestrator's context, and Fable input runs $10 per 1M tokens — a subagent that dumps file contents is burning orchestrator budget.

## Using the Workflow tool

Reach for `Workflow` on two checkable conditions: the fan-out has two or more phases whose output feeds the next, or you expect to re-run it (phase caching plus `{scriptPath, resumeFromRunId}` replays unchanged agents free). A single-phase fan-out lands faster through the Agent tool. Encode the phases in the script and set `model` per `agent()` call:

```javascript
export const meta = {
  name: 'frontier-orchestrate',
  description: 'Fable plans and synthesizes; Sonnet and Haiku do the work',
  phases: [{ title: 'Scout' }, { title: 'Work' }, { title: 'Synthesize' }],
}

const items = await agent('List the work items for: ' + args.task, {
  phase: 'Scout', model: 'haiku', schema: ITEMS_SCHEMA,
})

const results = await pipeline(
  items.items,
  item => agent(`Handle: ${item.description}`, {
    phase: 'Work', model: 'sonnet', schema: RESULT_SCHEMA,
  }),
)

return await agent(
  'Synthesize into one answer, resolving conflicts:\n' + JSON.stringify(results.filter(Boolean)),
  { phase: 'Synthesize', model: 'fable', effort: 'high' },
)
```

Prefer `pipeline()` over `parallel()`: an item that finishes scouting should start working immediately rather than blocking on the slowest scout. Reach for `parallel()` only when synthesis genuinely needs every result at once.

## Effort

Effort is a second price lever, independent of model. Use `effort: 'low'` on the cheap fan-out stages and `'high'` or `'xhigh'` on the Fable synthesis. A Haiku worker at high effort is wasted money — the task has no depth to reward it.

## Workers that write to a repo

Read-only fan-outs (audit, research, review) stop here. The moment workers will write to one shared repo, open [`fleet-dispatch.md`](fleet-dispatch.md) **before sending the first brief** — it holds the partition probes, the eight lines every dispatch brief carries, and the bail-rule verdict you must transmit.

Once those workers are live, open [`supervision.md`](supervision.md) **before judging a worker, relaying any claim, or closing a lease** — it holds the verification probe table, the timestamp rule that settles "did it disobey", the write-up turn, and the reviewer-brief spec.

If the fleet is also an autonomous loop run, pair those two files with `loop-doctrine`, which carries the pinned-worktree setup and explicit commit pathspecs that the brief lines here assume.

## Failure modes

- **Fable doing the fan-out.** If the orchestrator starts reading files itself instead of delegating, the cost advantage is gone. Verification probes are the exception — they return a line or two each, and a relayed claim you did not check becomes yours.
- **Chatty subagents.** Verbose returns inflate orchestrator input at frontier rates. Demand schemas.
- **Over-decomposition.** Items so small that per-agent overhead exceeds the work. If an item is one grep, do it inline.
- **Dispatching before partitioning.** Lanes and migration numbers assigned after the first worker starts are assigned too late.
- **A verdict you reached but never transmitted.** The worker acts on its own default, not on your reasoning.

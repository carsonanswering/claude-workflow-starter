---
description: Full implementation workflow - scout gathers context, planner creates plan, worker implements
---
Use the subagent tool with the chain parameter to execute this workflow. Leave agentScope unset — the default "user" scope is what you want, and passing "project" or "both" is refused in headless runs.

1. First, use the "scout" agent to find all code relevant to: $@
2. Then, use the "planner" agent to create an implementation plan for "$@" using the context from the previous step (use {previous} placeholder)
3. Finally, use the "worker" agent to implement the plan from the previous step (use {previous} placeholder)

Execute this as a chain, passing output between steps via {previous}.

REQUIRED: steps 2 and 3 must each contain the literal seven-character token {previous} inside their task string. Substitution is a plain string replace — if the token is absent, NOTHING is passed forward, the agent receives no prior context at all, and it will invent plausible-looking input instead of using the real thing. Do not paraphrase the token, do not write "the previous step" in its place, and do not omit it because the sentence reads fine without it.

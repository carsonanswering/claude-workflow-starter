---
description: Worker implements, reviewer reviews, worker applies feedback
---
Use the subagent tool with the chain parameter to execute this workflow. Leave agentScope unset — the default "user" scope is what you want, and passing "project" or "both" is refused in headless runs.

1. First, use the "worker" agent to implement: $@
2. Then, use the "reviewer" agent to review the implementation from the previous step (use {previous} placeholder)
3. Finally, use the "worker" agent to apply the feedback from the review (use {previous} placeholder)

Execute this as a chain, passing output between steps via {previous}.

REQUIRED: steps 2 and 3 must each contain the literal seven-character token {previous} inside their task string. Substitution is a plain string replace — if the token is absent, NOTHING is passed forward, the agent receives no prior context at all, and it will invent plausible-looking input instead of using the real thing. Do not paraphrase the token, do not write "the previous step" in its place, and do not omit it because the sentence reads fine without it.

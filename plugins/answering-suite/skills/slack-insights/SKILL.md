---
name: slack-insights
description: Turns one Slack thread or channel into an actionable-insights and recommendation markdown file.
disable-model-invocation: true
---

# Slack insights

Turn one Slack conversation into a durable, actionable artifact.

## Why a subagent

Slack MCP thread reads are bulky and mostly noise once analyzed. The
`slack-transcript-analyst` subagent does the read and the extraction; only the
file path, TL;DR, and recommendations come back to the main thread. Do not read
the transcript inline — that is the whole point of this skill.

## Steps

1. **Resolve the target.** You need one of: a Slack permalink, a channel +
   time range, or a specific enough topic pointer. If the user gave none of
   those, ask once — one short question — rather than guessing a channel.

2. **Decide the output path.** Default `slack-insights/` in the current working
   directory. If the user is working in a specific repo (for example
   `meeting-copilot/`), put it under that repo's `docs/slack-insights/` so it
   travels with the code it informs.

3. **Spawn the subagent** with `subagent_type: "slack-transcript-analyst"`.
   Give it, verbatim:
   - the permalink / channel / topic pointer
   - the absolute output path (directory or full filename)
   - any focus the user asked for ("only pull pricing decisions", "I care
     about who owns what")
   - whether related threads are in scope (default: no, one thread only)

   Run it synchronously while the user waits on the answer. Background it only
   when the user asked for several threads at once — in that case spawn one
   agent per thread in a single message so they run concurrently, one file
   each. Never have two agents write the same file.

4. **Relay.** The subagent's report is not shown to the user. Report back:
   the file path, the TL;DR, the numbered recommendations, and any blocker it
   hit (truncated read, ambiguous target, missing channel access). Keep it to
   what the user would act on.

5. **Wire it into future work** — the reason the file exists. Offer, do not do
   automatically:
   - commitments with owners → `/open-items`
   - anything that changes project direction or a constraint → a `project`
     memory file
   - decisions worth session history → `/obsidian-log`

Done when the file exists at the path you report, the TL;DR and numbered
recommendations are in the reply, and the wiring offer has been made — or when
the subagent's "thread is trivial, no file" verdict has been relayed.

## Boundaries

- Replying in-thread is a separate, explicit ask: route it to
  `slack:draft-announcement`, or to the Slack send tool whose name ends in
  `slack_send_message` (resolve its live MCP prefix from the loaded tool names
  — the prefix changes with which Slack MCP server is connected).
- One conversation per file. Multi-channel sweeps are `slack:channel-digest`;
  this skill goes deep on one thread, not wide.
- Private-channel content lands on local disk. If the output path is inside a
  git repo with a remote, say so before writing and let the user pick the path.
- If the thread is trivial, the subagent will decline to write a file. Relay
  that verdict; do not re-run it with a softer prompt to force output.

MCP-free path planned: `docs/slack-insights-oss-plan.md`.

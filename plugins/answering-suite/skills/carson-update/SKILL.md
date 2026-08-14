---
name: carson-update
description: Post Carson's work-progress update to their cofounder in #code-updates, autonomously. Use when Carson says "/carson-update", "cofounder update", or asks what to tell their cofounder. Optional argument: a topic to lead with.
---

# carson-update

Carson runs Answering with one cofounder — the only other person on the
team. The cofounder is technical but is not in Carson's sessions, so the update
is their entire view of what happened. Write it as normal prose a busy engineer reads
once — never compressed, abbreviated, or telegraphic.

Run this skill fully autonomously. Do not ask Carson anything, do not show a draft
for approval, and do not wait for a confirmation — posting is pre-authorized
every invocation, including scheduled runs where nobody is watching. Resolve
every ambiguity yourself using the rules below; if a rule does not cover it,
pick the conservative option (leave the item out) and keep going.

Argument (optional): a topic or extra context to feature. Treat it as the lead
item, and still include the rest of the sweep.

## 0. Resolve the Slack tools

The Slack MCP server name varies by session. Before using any Slack tool, find
the ones actually loaded — try `ToolSearch` with
`select:mcp__plugin_slack_slack__slack_search_channels,mcp__plugin_slack_slack__slack_read_channel,mcp__plugin_slack_slack__slack_send_message`
and, if those names are not available, search by keyword (`slack send message`,
`slack read channel`) and use whatever prefix this session exposes — e.g.
`mcp__claude_ai_Slack__*`. Tool names below are written as bare suffixes
(`slack_send_message`); prepend the prefix you resolved. If no Slack send tool
resolves at all, stop and report that — do not attempt to post another way.

## 1. Gather what changed

Establish the window first, then collect evidence:

- Find the channel: `slack_search_channels` for
  "code-updates". Resolve the id at runtime; it can change. If the search
  returns nothing or errors, fall back to the last known id `C0BLMNCSULQ` and
  confirm from the read that it really is #code-updates. If neither route lands
  on that channel, stop and report — a late update beats one sent to the wrong
  room.
- `slack_read_channel` on that channel for the most recent *update* — a message
  carrying one of the four section headers from step 2 (`*Shipped*`,
  `*In progress*`, `*Blocked on cofounder*`, `*Decisions needed*`), whoever posted
  it. Its timestamp is "since when"; ordinary chatter, links, and thread replies
  are not anchors. If no such message is findable, or the read fails, use the
  last 7 days and say so in the message.
- `git log --since='<window>' --oneline --all` in each of
  `/home/schmi/projs/meeting-copilot`, `/home/schmi/projs/answering-brief`,
  `/home/schmi/projs/testing-framework`, `/home/schmi/projs/ai-employees`.
  Skip a repo with no commits in the window rather than reporting "no changes".
- Count a commit as evidence only when it changed behavior, tests, or docs a
  person would care about. answering-brief commits `chore(<tool>): run <date>`
  every morning to record a daily-tool run (its doctrine §6) — those are
  automation output, so read past them to the work commits around them.
- Add anything notable from the current session that has not landed in a commit:
  decisions made, findings, things that broke.

Report only what the evidence shows. If a claim ("X is shipped") is not backed
by a commit, a test result, or something Carson said this session, either leave it
out or mark it as in progress.

## 2. Compose the update

Four sections, each omitted entirely when empty:

- **Shipped** — what is done and merged, one line each, in plain English about
  behavior, not file names.
- **In progress** — what is underway and roughly how far.
- **Blocked on cofounder** — anything waiting on them, each with the specific action.
- **Decisions needed** — open questions where you name the options and Carson's lean.

Keep the whole message under roughly 200 words. Slack formatting: `*bold*` for
section headers, `•` bullets. No preamble, no sign-off, no "hope this helps".

## 3. Self-check instead of asking

There is no human gate, so the check replaces it. Re-read the draft and, for
every bullet, name to yourself the commit hash or session fact behind it. Drop
any bullet you cannot point to. Then:

- If every section came out empty, post nothing. Report to Carson that there was
  nothing traceable in the window. An empty update is worse than none.
- If only some sections are empty, omit those and post the rest.

## 4. Post

`slack_send_message` to the resolved channel with the checked text verbatim. No
draft turn, no permission question — post it.

Then report back to Carson: the exact text that went out and the channel it went
to, so a wrong send is visible immediately and can be corrected with a
follow-up message.

## Done when

The message posted to #code-updates contains only claims traceable to a commit
in the window or to this session, and every "blocked on cofounder" line names a
concrete action — with the exact sent text and channel reported back to Carson.

# Per-meeting procedure

Everything for one meeting: find its Meet transcript, gather Slack context, write
the file, return the result object. This is the single source of truth for both
branches — a subagent reads this file and follows it exactly; the main thread
opens it only on the single-pending-meeting inline branch.

The dispatching prompt gives you the meeting title, calendar event ID, start and
end (ISO with offset), attendee emails, calendar link, search window start
(RFC3339), output directory, and the live Slack MCP tool prefix. Slack tools are
named below by suffix only — prepend that prefix, e.g.
`<SLACK_PREFIX>slack_search_public_and_private`. Google Drive/Gmail tool names
carry today's prefix (`mcp__claude_ai_*`); if one fails to resolve, match its
suffix against the tools actually loaded and use that prefix instead.

## 1. Transcript discovery

- Search Drive with `mcp__claude_ai_Google_Drive__search_files`. Query syntax is
  structured with single-quoted strings and `and`/`or`/`not`:

  ```
  title contains 'Transcript' and mimeType = 'application/vnd.google-apps.document' and modifiedTime > '<WINDOW_START_RFC3339>'
  ```

  Then a narrower pass using a distinctive word from the meeting title:

  ```
  title contains '<KEYWORD>' and mimeType = 'application/vnd.google-apps.document'
  ```

- Map file types to `mimeType`, never to `title contains`. Words like
  `presentation`, `slides`, `pdf`, `folder` inside `title contains` break the
  search; `Transcript` is legitimate because it is literally part of the title.
- Pass `excludeContentSnippets: true` on discovery searches so responses stay
  small.
- Meet transcripts are Google Docs titled
  `<Meeting name> - YYYY/MM/DD HH:MM TZ - Transcript`, normally parented in a
  `Meet Recordings` folder. Find it once with

  ```
  title contains 'Meet Recordings' and mimeType = 'application/vnd.google-apps.folder'
  ```

  and, if found, add `parentId = '<FOLDER_ID>'` to the searches.
- Accept a candidate only on title similarity **and** date proximity: its
  `createdTime` falls within a few hours after the meeting end. A title-only
  match is not enough — recurring meetings produce near-identical titles across
  days.
- Read it with `mcp__claude_ai_Google_Drive__read_file_content`. The `fileId`
  must come from a search result; never construct or guess one — an invented ID
  either errors or returns someone else's document.
- Secondary path only if Drive search finds nothing:
  `mcp__claude_ai_Gmail__search_threads` with Gmail syntax, e.g.
  `query: "subject:transcript newer_than:2d"` or
  `query: "from:meet-recordings-noreply@google.com newer_than:2d"`,
  `pageSize: 10`. Use it to learn a transcript exists and get its exact title,
  then return to Drive for the `fileId` and content.
- No transcript found: write no file, return `status: "no_transcript"`. Meet
  transcripts can lag the meeting by an hour or more, so a later run picks it up.
  When no `Meet Recordings` folder turned up either, write exactly
  `no Meet Recordings folder` in `note` — the main thread uses that phrase to
  tell a lagging transcript from an account that has no transcription at all.

## 2. Slack context

- Sweep with `slack_search_public_and_private`: 2-4 targeted queries maximum. Use
  meeting-title keywords with `after:YYYY-MM-DD` and `before:YYYY-MM-DD`
  modifiers, plus `from:` for a key attendee whose Slack user resolves. Set
  `response_format: "concise"`, `limit: 10`, `include_context: false`, and
  `channel_types: "public_channel,private_channel"`.
- Default to excluding DMs. The tool searches `im,mpim` unless `channel_types`
  says otherwise, and this skill writes its output to disk — a DM swept in
  silently becomes a private conversation copied into a notes file. Include
  `im,mpim` only when the user asks for DM context.
- **Filter every hit before citing it.** Search is fuzzy, not boolean AND: the
  query `Guidewire orientation after:2026-07-27` returned five results, none of
  which contained either word. Keep a result only if its text actually mentions a
  meeting-title keyword, an attendee, or a topic named in the transcript. Discard
  the rest and, if nothing survives, treat the meeting as having no Slack
  context. A plausible-looking but unrelated thread in a meeting file is worse
  than an empty section.
- Follow up only on surviving hits: `slack_read_thread` (needs `channel_id` and
  the parent `message_ts`) or `slack_read_channel` for surrounding messages.
- Capture a permalink for every item cited.
- Zero relevant results is the normal outcome. After 2-4 queries, stop searching
  — do not widen to broad sweeps — and write the file with the no-Slack-context
  note.

## 3. Write the meeting file

Path `<outdir>/YYYY-MM-DD-<meeting-slug>.md`, written with the Write tool. Derive
the filename date from the offset inside the start timestamp you were given, not
from any timezone label. Slug: lowercase the title, collapse every run of
non-alphanumerics to a single hyphen, trim leading and trailing hyphens, cap at
about 60 characters.

```markdown
---
title: Cortex Brain design partner sync
date: 2026-07-28
start: 2026-07-28T09:30:00-06:00
end: 2026-07-28T10:15:00-06:00
attendees:
  - taj.vasudeva@gmail.com
  - carson@example.com
calendar_event_id: 7f3k9d2m1abc4efg5hij6klmn
drive_file_id: 1AbCdEfGhIjKlMnOpQrStUvWxYz
sources:
  calendar: https://www.google.com/calendar/event?eid=...
  transcript: https://docs.google.com/document/d/1AbCdEfGhIjKlMnOpQrStUvWxYz/edit
  slack:
    - https://example.slack.com/archives/C0BKPEEE2TG/p1753712345678900
generated_by: meeting-notes-sync
processed_at: 2026-07-28T17:04:11Z
---

## Summary

Walked the design partner through the MCP-backed context layer. They pushed on
row-level security in shared channels and asked for a self-hosted option before
signing.

## Decisions

- Ship read-only MCP access first; writes wait for per-channel ACLs.
- Self-hosting stays out of scope for v1.

## Action Items

- **Taj** — send the RLS design note by Thursday.
- **Carson** — collect the partner's channel inventory.

## Slack Context

- https://example.slack.com/archives/C0BKPEEE2TG/p1753712345678900 — partner
  restated the self-hosting ask an hour after the call.
```

Emit every frontmatter key above, in that order, so the whole archive parses the
same way run after run:

- `title`, `date`, `start`, `end`, `attendees`, `calendar_event_id`, and
  `sources.calendar` are copied from the fields in your prompt.
- `drive_file_id` is the `fileId` of the accepted search result, and
  `sources.transcript` is `https://docs.google.com/document/d/<fileId>/edit`.
- `sources.slack` lists one permalink per surviving Slack item; with none
  surviving, write `slack: []`.
- `generated_by` is the literal `meeting-notes-sync`.
- `processed_at` is UTC from `date -u +"%Y-%m-%dT%H:%M:%SZ"` — the one Bash call
  this procedure makes, since Bash writes outside the project cwd are
  sandbox-blocked while Write works anywhere.

Body rules:

- Empty sections use exactly `_No explicit decisions recorded._`, `_None._`, and
  `_No Slack context found._`.
- Record only what the transcript supports. Name an owner only when the
  transcript names them; otherwise write the action without an owner. Inventing
  a decision makes the whole archive untrustworthy.
- Summary is a few paragraphs at most. No filler, no restating the agenda.
- If the target file already exists (a crashed earlier run), overwrite it and say
  so in the returned `note`.

## 4. Return object

Return exactly this JSON and no other text — no transcript excerpts, no Slack
message bodies, no narration:

```json
{"meeting_id": "<EVENT_ID>", "title": "<TITLE>", "status": "written|no_transcript|failed",
 "output_path": "...", "drive_file_id": "...", "decisions_count": 0,
 "actions_count": 0, "slack_items_count": 0, "note": ""}
```

On a Drive, Gmail, or Slack tool error, return `status: "failed"` with the
error's shortest decisive line in `note`.

---
name: meeting-notes-sync
description: Syncs Google Meet transcripts plus related Slack context into one idempotent markdown file per meeting under projs/notes/meetings/.
disable-model-invocation: true
---

# meeting-notes-sync

One markdown file per meeting in `/Users/kai/Desktop/projs/notes/meetings/`, built from the Meet
transcript in Drive plus any Slack threads about that meeting. Runs many times a
day, so every step is idempotent: a meeting already recorded in state is never
re-fetched, and a meeting with no transcript yet stays pending for a later run.

Main thread discovers and reports. Subagents do all reading. The main thread must
never load transcript bodies or Slack messages into its own context.

The per-meeting procedure — transcript search, Slack context, file format, return
object — lives in
[`per-meeting.md`](/Users/kai/.claude/skills/meeting-notes-sync/per-meeting.md).
Every subagent prompt tells the worker to read that file first; open it yourself
only on the single-pending-meeting inline branch.

## Run

### 0. Setup

- Lookback argument is optional: `48h`, `3d`, `today`. Default `24h`. Output dir
  defaults to `/Users/kai/Desktop/projs/notes/meetings/`; a path argument overrides it. State file is
  `<outdir>/.state.json`.
- Get the clock from the machine, never from memory:

  ```bash
  date -u +"%Y-%m-%dT%H:%M:%SZ"
  ```

  Compute the window start by subtracting the lookback from that value.
- **Write every file and directory with the Write tool, not Bash.** Write creates
  missing parent directories, so a single Write to
  `<outdir>/2026-07-28-some-meeting.md` is all the setup needed. Bash in this
  skill is for `date` only. Note the default outdir lives under the project cwd
  (`/Users/kai/Desktop/projs`); if a path argument moves it outside, Bash writes there
  are sandbox-blocked (`Operation not permitted`) while Write still works.
- Read `<outdir>/.state.json`. If it is missing, Write it as
  `{"version": 1, "meetings": {}}`. If it exists but does not parse as JSON,
  stop, tell the user the state file is malformed and give its path — do not
  overwrite it, because it is the only record of what was already processed.
- Resolve the Slack MCP prefix once, from the tool names actually loaded this
  session: the suffixes this skill uses are `slack_search_public_and_private`,
  `slack_read_thread`, and `slack_read_channel`, and today they load as
  `mcp__plugin_slack_slack__*`. The prefix has drifted between sessions, so read
  it live and pass the resolved value into every subagent prompt as
  `<SLACK_PREFIX>`. Google Calendar/Drive/Gmail tool names below carry today's
  prefix (`mcp__claude_ai_*`); if one fails to resolve, re-derive the prefix the
  same way — match the tool's suffix against the names actually loaded.
- Run the sync itself without asking for confirmation. Stop and ask the user
  first before deleting or moving anything under `<outdir>`, before posting to
  Slack, and before writing anywhere outside `<outdir>`.

### 1. Discover meetings (main thread only)

- Resolve the calendar with `mcp__claude_ai_Google_Calendar__list_calendars`;
  primary is the user's own email address.
- Call `mcp__claude_ai_Google_Calendar__list_events` with that `calendarId`,
  `startTime`/`endTime` set to the ISO8601 window, `orderBy: "startTime"`,
  `pageSize: 25`.
- `list_events` returns full HTML event `description` bodies — one real event came
  back at roughly 4KB of HTML. Keep the window tight and `pageSize` small, and
  immediately reduce each event to these fields only: `id`, `summary`,
  `start.dateTime`, `end.dateTime`, `attendees[].email`, `htmlLink`,
  `hangoutLink` or `conferenceData`, `location`. Discard everything else and
  never paste a description into a subagent prompt.
- `start.timeZone` can disagree with the offset inside `start.dateTime` — a real
  event carried `dateTime: "2026-07-28T09:30:00-06:00"` with
  `timeZone: "America/Los_Angeles"`. Derive the filename date and the displayed
  times from the offset in `dateTime`, ignoring the `timeZone` label.
- Key state by the per-instance `id` (e.g.
  `885l3cnblts70to1495jtk8t5o_20260728T153000Z`), never by `recurringEventId`.
  The `recurringEventId` is shared by every occurrence, so keying on it would
  make the second standup of the week look already processed.
- Drop non-meetings: `eventType` of `OUT_OF_OFFICE`, `FOCUS_TIME`,
  `WORKING_LOCATION`, `BIRTHDAY`, and any event whose only attendee is the user
  (solo block). Events whose `location` is a Zoom room or other non-Meet
  conference have no Meet transcript — attempting them is fine, expect
  `no_transcript`.
- Drop any event whose `id` is already a key in `.state.json.meetings`. That `id`
  is the only dedup key available here; transcript-level duplicates are caught in
  step 3, once a subagent has returned a `drive_file_id`.

### 2. Dispatch

- Main thread: discover, filter against state, spawn, collect results, update
  state, report. Nothing else.
- One subagent per new meeting via the Agent tool with
  `subagent_type: general-purpose`. Launch independent meetings as parallel Agent
  calls in a single message. Concurrency cap is 4 — with more than 4 pending
  meetings, run batches of 4.
- Inline exception: exactly one pending meeting, whose work is a handful of tool
  calls, is done inline — read `per-meeting.md` yourself and follow it. Spawning
  a subagent for it costs more than it saves.

Template subagent prompt — fill every `<PLACEHOLDER>` and send verbatim
otherwise:

```
Build one meeting-notes markdown file for a single meeting.

Meeting title: <TITLE>
Calendar event ID: <EVENT_ID>
Start (ISO with offset): <START_ISO>
End (ISO with offset): <END_ISO>
Attendee emails: <ATTENDEE_EMAILS>
Calendar link: <HTML_LINK>
Search window start (RFC3339): <WINDOW_START>
Output directory: <OUTDIR>
Slack MCP tool prefix: <SLACK_PREFIX>

Read /Users/kai/.claude/skills/meeting-notes-sync/per-meeting.md and follow it
exactly. Return only the JSON object it specifies, and no other text.
```

### 3. Update state (main thread)

- Read `.state.json` again immediately before writing — the fresh copy, not the
  one from step 0 — merge your new entries into it, and Write the whole file
  back. Keep every `meetings` key you did not create: a scheduled run can overlap
  a manual one, and a whole-file Write built from a stale copy drops the other
  run's entries.
- Record a `meetings` entry for `status: "written"` only, keyed by calendar event
  ID.

  ```json
  {
    "version": 1,
    "last_run": {
      "at": "2026-07-28T17:04:11Z",
      "meetings_attempted": 3,
      "transcripts_found": 1,
      "meet_recordings_folder": true
    },
    "meetings": {
      "7f3k9d2m1abc4efg5hij6klmn": {
        "title": "Answering design partner sync",
        "output": "/Users/kai/Desktop/projs/notes/meetings/2026-07-28-answering-design-partner-sync.md",
        "drive_file_id": "1AbCdEfGhIjKlMnOpQrStUvWxYz",
        "processed_at": "2026-07-28T17:04:11Z"
      }
    }
  }
  ```

  Always record `drive_file_id` so a transcript later discovered by a different
  path is recognised as already processed.
- Transcript-level dedup happens here, where `drive_file_id` first exists: if a
  returned `drive_file_id` already appears under a different event key, still
  write this event's entry — that keeps the next run from re-fetching it — and
  add `"duplicate_of": "<other event id>"` to it. Report that meeting as a
  duplicate of the earlier one rather than as fresh notes.
- Write `last_run` on every run that attempted at least one meeting, whatever the
  outcomes: `at` from this run's clock, `meetings_attempted` and
  `transcripts_found` as counted from the returned objects, and
  `meet_recordings_folder: false` when every `no_transcript` note said
  `no Meet Recordings folder`. It is the only record of what the previous run
  found, and the zero-transcript edge case reads it.
- Write no `meetings` entry for `no_transcript` or `failed`.

### 4. Report

One line per meeting: title — written / duplicate / failed, path, and the three
counts. List `no_transcript` meetings as pending retry. When the discovery step
found nothing new, reply with one short "no new meetings" line and stop, with no
preamble and no tool calls beyond discovery.

## Edge cases

- No events in the window: say "no meetings in the last `<lookback>`" and stop.
- Every event already in state: "no new meetings".
- Slack empty or all hits filtered out as irrelevant: write the file anyway with
  `_No Slack context found._`
- Malformed `.state.json`: stop and report the path; never clobber it.
- Tool error inside a subagent: `failed` with the error's shortest decisive line;
  the main thread reports it and leaves state untouched.
- Meet transcription is a paid Workspace feature. On a personal `@gmail.com`
  account there will be no `Meet Recordings` folder, no transcript docs, and no
  `meet-recordings-noreply@google.com` mail — every meeting returns
  `no_transcript` forever, not just late. Before reporting pending retries, check
  the `last_run` you read in step 0: when it recorded `transcripts_found: 0` and
  `meet_recordings_folder: false` over at least one attempted meeting, and this
  run repeats that, say once that the account has no Meet transcription instead
  of listing the same meetings as pending retry indefinitely. A state file with
  no `last_run` key is a first run — report pending retry as normal.

## Done when

- Every meeting reported `written` has a file at its reported path, and a
  `.state.json` entry keyed by its calendar event ID carrying `drive_file_id`.
- `.state.json` contains no entry for any `no_transcript` or `failed` meeting, so
  the next run retries them — transcripts lag their meetings by an hour or more.
- `.state.json.last_run.at` equals this run's clock, and its counts match the
  subagent results you reported.
- Re-invoking the skill immediately afterward, same lookback, reports
  "no new meetings" for everything just written and makes no Drive, Gmail, or
  Slack calls for them.

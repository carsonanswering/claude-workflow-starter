---
name: launchd-manage
description: launchd job on this Mac — write the plist, load it idempotently, verify it actually ran. Use when the user wants something scheduled daily/hourly on this machine, says "launchd", "launchctl", or "make a plist", or asks why a scheduled local job did not run.
---

# launchd-manage

One ritual, run the same way every time, for a recurring job on **this machine**. Every step is idempotent: run the whole thing again against a job in any state — never registered, half-registered, already running — and it lands in the same place.

Scope: launchd is for work that needs this Mac — local git repos, local MCP auth, files on this disk. A routine that only touches the web belongs in the cloud `schedule` skill, which keeps firing with the laptop shut.

`answering-brief`'s per-tool local-vs-cloud split lives in `/Users/kai/projs/answering-brief/SCHEDULING.md`; its install snippet predates this skill, so where the two differ the ritual below wins.

## The ritual

### 1. Name it

Label is reverse-DNS: `com.carson.<job>`, or `com.answeringrnd.<job>` for shared AnsweringRND tooling. The file goes at `~/Library/LaunchAgents/<label>.plist`.

Done when the filename stem and the `<Label>` string are character-identical. launchd addresses a service by Label, so a mismatch loads a job that `launchctl print` on the name you expect answers `Could not find service`.

### 2. Write the plist

Open `plist-template.md` beside this file when you are authoring a plist from scratch or adding a key the job does not already have — it carries the annotated XML, the two house job shapes, and the schedule variants. Changing only the time or a log path on an existing plist needs no template.

Done when both hold:

```bash
mkdir -p <dir holding StandardOutPath>
plutil -lint ~/Library/LaunchAgents/<label>.plist   # prints: OK
```

launchd creates neither the log file's directory nor the log itself; if the directory is missing the job dies at spawn with no log to say why, so `mkdir -p` first.

### 3. Reload

```bash
launchctl bootout gui/$UID/<label> 2>/dev/null
launchctl bootstrap gui/$UID ~/Library/LaunchAgents/<label>.plist
```

The bootout is what makes the reload idempotent — launchd refuses to bootstrap a label it already holds, and `2>/dev/null` swallows the harmless "not found" on a first install.

Done when `bootstrap` prints nothing and returns 0. Any output means the load failed — see Failure modes.

### 4. Fire it once and read the verdict

```bash
launchctl kickstart -k gui/$UID/<label>
launchctl print gui/$UID/<label> | grep -E 'state|last exit code'
```

`-k` kills an instance already running, so you are timing a fresh run rather than watching a stuck one. A `claude -p` job takes minutes; re-run the `print` until the state settles.

Done when the output shows `last exit code = 0`. `(never exited)` means it is still running — wait and print again. A non-zero code is the command's own failure, and step 5 says what it was.

### 5. Read the log

```bash
tail -20 <StandardOutPath> <StandardErrorPath>
```

Done when the log holds output from the run you just fired — check the timestamps rather than trusting that content is fresh, since these files append across runs. An empty log next to a non-zero exit code points at the spawn itself: a wrong binary path in `ProgramArguments`, or a log directory that does not exist.

## Failure modes

- **`Bootstrap failed: 5: Input/output error`** — the label is already loaded. Bootout, then bootstrap again (step 3). If a clean bootout still gives 5, launchd is rejecting the file: `plutil -lint` it, then confirm every absolute path inside it exists.
- **Registered but never fires** — launchd skips a `StartCalendarInterval` that comes due while the Mac is asleep and fires it once on wake, so a laptop closed over a weekend yields one catch-up run, not three. Coverage that must not slip belongs in the cloud `schedule` skill.
- **Fires, then dies with auth or "command not found" errors** — launchd hands the process a minimal environment. `/bin/zsh -lc` is what sources `~/.zshenv`, where the API keys live; a bare binary path or `-c` without `-l` gets none of them. Non-shell jobs carry an explicit `EnvironmentVariables` `PATH` instead.
- **First run hangs on a permission prompt** — a job touching Calendar, Contacts, or protected disk areas triggers a macOS consent dialog on its first launch. Kickstart it while Carson is at the machine so the prompt lands in front of him rather than at 06:06.

## Ask Carson first

- Before removing or overwriting any existing plist in `~/Library/LaunchAgents/` — `com.carson.answering-dayplan`, `com.carson.answering-dailybrief`, `com.carson.answering-compwatch`, and `com.answeringrnd.tracker-refresh` are live jobs.
- Before the first fire of a job that posts outward (Slack, email, a remote push) — confirm the destination, since kickstart sends it for real.

# plist template

The house LaunchAgent, annotated. Copy the shape that matches the job, replace every `UPPERCASE` placeholder, then return to step 2 of [`SKILL.md`](SKILL.md) to lint and load it.

## Shape A — a Claude skill on a schedule

Live examples of this exact shape: `~/Library/LaunchAgents/com.taj.cortex-dayplan.plist`, `com.taj.cortex-dailybrief.plist`, `com.taj.cortex-compwatch.plist`.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.taj.JOB</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>cd /Users/taj/projs/PROJECT &amp;&amp; /Users/taj/.local/bin/claude -p "/SKILL" --permission-mode acceptEdits</string>
  </array>

  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>6</integer>
    <key>Minute</key><integer>6</integer>
  </dict>

  <key>StandardOutPath</key>
  <string>/Users/taj/projs/PROJECT/logs/JOB.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/taj/projs/PROJECT/logs/JOB.err.log</string>

  <key>RunAtLoad</key>
  <false/>
</dict>
</plist>
```

Key by key:

- **`Label`** — reverse-DNS, and identical to the filename stem. This string is the service name in every `launchctl` command.
- **`ProgramArguments`** — exactly three elements: `/bin/zsh`, `-lc`, and one command string. The `-l` makes it a login shell so `~/.zshenv` is sourced and the API keys exist; `-c` alone gives the job an empty environment. Absolute paths only — `~` and `$HOME` are unexpanded inside the XML, and `claude` is not on launchd's `PATH`, hence `/Users/taj/.local/bin/claude`.
- **`&amp;&amp;`** — XML escaping for `&&`. A literal `&&` makes the file unparseable and `plutil -lint` fails.
- **`--permission-mode acceptEdits`** — the run is headless, so a permission prompt would hang until the next reboot.
- **`StandardOutPath` / `StandardErrorPath`** — under the job's own project, `PROJECT/logs/`, matching the live jobs (`/Users/taj/projs/cortex-brief/logs/`). Keep stdout and stderr separate here so a stack trace is not interleaved with skill output. `mkdir -p` the directory before loading.
- **`RunAtLoad`** — `false` for scheduled jobs, so bootstrapping during setup does not silently kick off a real run; you fire it deliberately with `kickstart`.

## Shape B — a shell script on an interval

Live example: `~/Library/LaunchAgents/com.cortexrnd.tracker-refresh.plist`.

```xml
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>/Users/taj/projs/PROJECT/SCRIPT.sh</string>
  </array>

  <key>StartInterval</key><integer>900</integer>
  <key>RunAtLoad</key><true/>

  <key>StandardOutPath</key><string>/Users/taj/projs/PROJECT/refresh.log</string>
  <key>StandardErrorPath</key><string>/Users/taj/projs/PROJECT/refresh.log</string>

  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string></dict>
```

What differs from Shape A: the script is invoked directly rather than through a login shell, so it gets an explicit `PATH` including `/opt/homebrew/bin` (that is where `gh`, `jq`, and the rest live). `RunAtLoad` is `true` because a refresher should populate its output the moment it is loaded, and both streams share one log because the output is a progress trace, not a report.

## Schedule variants

Pick one; `StartCalendarInterval` and `StartInterval` do not combine.

Daily at a fixed time — omit `Weekday` entirely:

```xml
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>7</integer>
    <key>Minute</key><integer>24</integer>
  </dict>
```

Weekdays only — an array of dicts, one per day, `Weekday` 1 = Monday through 5 = Friday:

```xml
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>8</integer><key>Minute</key><integer>3</integer></dict>
    <dict><key>Weekday</key><integer>2</integer><key>Hour</key><integer>8</integer><key>Minute</key><integer>3</integer></dict>
    <dict><key>Weekday</key><integer>3</integer><key>Hour</key><integer>8</integer><key>Minute</key><integer>3</integer></dict>
    <dict><key>Weekday</key><integer>4</integer><key>Hour</key><integer>8</integer><key>Minute</key><integer>3</integer></dict>
    <dict><key>Weekday</key><integer>5</integer><key>Hour</key><integer>8</integer><key>Minute</key><integer>3</integer></dict>
  </array>
```

Every N seconds, counted from load — `900` is every 15 minutes:

```xml
  <key>StartInterval</key><integer>900</integer>
```

Hourly is `StartInterval` `3600` if drift is acceptable, or a `StartCalendarInterval` dict carrying only `Minute` if the job must land on the same minute past every hour.

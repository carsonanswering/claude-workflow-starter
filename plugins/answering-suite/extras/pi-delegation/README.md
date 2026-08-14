# pi delegation — operator's manual

Two ways to push work off the main model onto cheap Fireworks models via `pi`.

## 1. What exists

| Mechanism | What it is | Reach for it when |
|---|---|---|
| `subagent` tool | In-session tool (registered in `~/.pi/agent/extensions/subagent/index.ts:461`). Spawns a **real child `pi` process** per call, with its own context window, own tool allowlist, own model. Blocks until done, result comes back into your current conversation. | You want a sub-task's result folded straight back into the conversation you're already having — locate code, run a review pass, get a plan — and you're willing to wait for it. |
| `pi-spawn` | Shell script (`~/.pi/agent/bin/pi-spawn`) that runs a whole headless `pi -p` task inside a **detached tmux session**. Survives you closing the terminal or the parent session ending. | A task is long-running, you want to walk away and check back later, or it must outlive the current session (e.g. kicked off from a script/cron, or you're about to close your laptop). |

Both ultimately shell out to the same `pi` binary with the same model roster — the difference is process lifetime and whether the result comes back inline or has to be read from a log later.

## 2. The roster

All agent files live in `~/.pi/agent/agents/*.md`. Table reflects the current fireworks-only roster.

| Agent | Model | Tools | Purpose |
|---|---|---|---|
| `scout` | `fireworks/qwen3p7-plus` | read, grep, find, ls, bash | Fast read-only recon, returns `file:line`, never fixes |
| `grunt` | `fireworks/gpt-oss-120b` | read, grep, find, ls, bash, edit, write *(explicit allowlist — no `subagent`)* | Mechanical, fully-specified edits; must say `ESCALATE:` rather than guess |
| `bulk` | `fireworks/deepseek-v4-flash` | read, grep, find, ls | Bulk summarize/classify/extract over many files, 1M context, never edits |
| `tester` | `fireworks/gpt-oss-120b` | bash, read, grep | Runs a suite once, returns compressed failure lines, never fixes |
| `reviewer` | `fireworks/minimax-m3` | read, grep, bash | Severity-tagged one-liner findings on a diff/branch/file, no edits |
| `planner` | `fireworks/minimax-m3` | read, grep, find, ls | Implementation plan from scout context + requirements, no edits |
| `worker` | `fireworks/gpt-oss-120b` | *(none listed = ALL tools)* | General-purpose implementer for `/implement` and `/implement-and-review`; must say `ESCALATE:` rather than guess, never commits/pushes |

**Fireworks-only is a design decision, not a limitation to work around.** claude-* models are not used in pi and are not supported here; frontier reasoning stays in Claude Code.

Every agent's rules live in its own frontmatter+body file — read `~/.pi/agent/agents/<name>.md` for the exact contract before relying on it for something new.

**On speed, honestly**: this table used to carry a "Speed (measured)" column with per-agent single/multi-step timings. Those were raw model-latency numbers from a round-2 model benchmark — not end-to-end time through the actual `subagent` harness — and they badly understated real wall time. A real trivial single-step `scout` call through the actual harness (`time pi -p --tools subagent "use scout to find where pi.registerTool appears in index.ts, report file:line"`) measured **8.83s wall-clock total**, not the ~1.8s the old column claimed. A real 8-file `bulk` extraction was separately clocked at **~18s**, not the ~9.7s claimed (reported by another agent's test this session; not independently reproduced by me here — no command shown because I didn't run it). Harness overhead — child `pi` process startup, the model API round trip, JSON-mode marshaling — dominates, and wall time scales with task size far more than with which agent you pick. Budget seconds-to-tens-of-seconds per call and don't plan around precise numbers; nothing here has been benchmarked rigorously enough to justify one.

## 3. How to invoke

### Single (in-session `subagent` tool)

Just ask the running pi session in plain language; it decides to call the `subagent` tool itself. Proven example (headless, forcing the subagent tool with `--tools subagent` so the parent can't just grep directly):

```
pi -p --model fireworks/gpt-oss-120b --tools subagent \
  "use scout to find where the subagent tool is registered in ~/.pi/agent/extensions/subagent/index.ts, report file:line"
```

Result: subagent ran as `fireworks/qwen3p7-plus` (scout's model) and returned a real file:line citation from the actual file — a real second `pi` process, not the parent guessing. Repeated runs consistently returned `index.ts:461` (the `pi.registerTool({` line); an earlier draft of this doc reported `index.ts:462` (the adjacent `name: "subagent",` line) from an unverified run. Either is a defensible answer to "where is it registered"; only 461 has been reproduced here.

In an interactive session you don't need `--tools subagent` — just say e.g. **"use scout to find X"** and the model picks the tool up on its own; forcing it is only useful for headless proof-of-execution.

### Parallel

Ask for it explicitly, naming each sub-task:

```
run 2 scouts in parallel: one to find where the subagent tool is registered,
one to find where agentScope defaults are set
```

This becomes one `subagent` call with `{tasks: [...]}` — max 8 tasks, 4 run concurrently.

### Chain

```
chain: first use scout to find X, then use planner to turn that into a plan
using {previous}
```

`{previous}` is substituted with the prior step's output (`index.ts:552`). Each step is still a separate child process — only the text of `{previous}` carries forward, not tool state or memory.

Verified end-to-end, headless, forcing the tool the same way as the single example above:
```
pi -p --model fireworks/gpt-oss-120b --tools subagent \
  "chain: first use scout to find where the subagent tool is registered in index.ts and report the exact file:line plus the literal tool name string used to register it, then use planner to write a one-step plan for renaming that tool to 'delegate', citing the exact file:line and current tool name from the prior step using {previous}"
```
Real output: `planner`'s plan read *"Edit `/home/schmi/.pi/agent/extensions/subagent/index.ts` at line 462, changing the `name` field in the `pi.registerTool({...})` call from `"subagent"` to `"delegate"` (the registration begins at line 461)."* Neither line number nor the literal `"subagent"` string was in the prompt — `planner` could only have gotten them from `scout`'s real answer arriving through `{previous}`, not a literal `{previous}` token and not an empty string.

### Workflow prompt templates (`~/.pi/agent/prompts/*.md`)

All three are chain wrappers you invoke as `/implement <args>`, `/scout-and-plan <args>`, `/implement-and-review <args>`:

| Template | Chain | Status |
|---|---|---|
| `/scout-and-plan` | scout → planner | **Confirmed working end to end.** Returns a plan only, does not implement. |
| `/implement` | scout → planner → worker | **Confirmed working end to end** — verified directly, not inherited. `pi -p "/implement fix the bug in ./buggy.py so add(2,3) returns 5"` against a fresh `def add(a, b): return a - b`: scout found the bug, planner made a 2-step plan, worker edited the file. Checked on disk afterward, not just from the tool's own summary: `a - b` → `a + b`, and running the script now prints `2 + 3 = 5`. One wrinkle worth noting: scout's summary also claimed a `math_utils.py` "reference implementation" existed in the same directory — it did not; the test directory contained only `buggy.py`. The fix itself was correct, but treat any supplementary color in a scout summary as unverified until you check it yourself. |
| `/implement-and-review` | worker → reviewer → worker | **Chain completes and reviewer's findings are real** (verified twice: `file:line` citations check out against the actual code). **`{previous}` handoff depends on the model typing the token** — before the templates required it, one verified run had it in neither downstream step, and worker(2), never having seen the review, guessed generic fixes that happened to look right. Since the templates were fixed: 5/5 fresh runs of this chain carried the token in both steps and applied the reviewer's real findings. Still check the diff when the review's content matters. See §5. |

Both chains were dead until `worker.md` was created — the templates referenced an agent that did not exist and failed with `Unknown agent`. If you rename or delete an agent, re-check every template that names it.

Slash commands work from headless `pi -p` runs, not just interactive sessions: `pi -p "/implement fix the bug in foo.py"` parses the `/name args` form and loads the matching template itself.

## 4. `pi-spawn` usage

```
pi-spawn [-m MODEL] [-d DIR] [-n NAME] "task prompt"
pi-spawn -l          # list running pi-* tmux sessions
pi-spawn -k NAME     # kill session pi-NAME (only pi-* sessions, refuses anything else)
```

| Flag | Meaning | Default |
|---|---|---|
| `-m MODEL` | model for the task | `$PI_SPAWN_MODEL` env var, else `fireworks/gpt-oss-120b` |
| `-d DIR` | working directory for the session | current directory |
| `-n NAME` | session name suffix → session is `pi-NAME`, log is `NAME.log` | slug of the task text + PID |
| `-l` | list all `pi-*` tmux sessions | — |
| `-k NAME` | kill `pi-NAME` | — |

- **Logs**: always `~/.pi/agent/logs/<NAME>.log`, written via `tee` as the task runs — `tail -f` it to watch live, or just `cat`/`grep` it after the fact without ever attaching to the tmux pane.
- **Listing**: `pi-spawn -l` (wraps `tmux ls | grep '^pi-'`).
- **Killing**: `pi-spawn -k NAME` only — it validates the target starts with `pi-` and refuses anything else, so it can't be used to kill a session it didn't create.
- **Reading results without attaching**: read the log file. If you do attach (`tmux attach -t pi-NAME`), detach with `Ctrl-b d` — don't kill the pane's shell.
- **Checking success from a script**: the log's last line is always `[pi-spawn] exit=<N>` — the real exit status of the `pi` process, captured via `${PIPESTATUS[0]}` right after the `pi | tee` pipeline (not `tee`'s status, which is always 0 and used to be misreported as "exited 0" even when `pi` itself had errored). Tail for that line to know whether a spawned task actually succeeded:
  ```
  grep -q '^\[pi-spawn\] exit=0$' ~/.pi/agent/logs/NAME.log && echo ok || echo failed-or-still-running
  ```
- Verified end-to-end: `pi-spawn -n readmecheck -m fireworks/qwen3p7-plus "reply with exactly the string README_VERIFY_OK and nothing else"` → `~/.pi/agent/logs/readmecheck.log` contained `README_VERIFY_OK` followed by `[pi-spawn] exit=0`.
- `-l` and `-k` verified for real, not just read from source: created a throwaway session (`pi-spawn -n piverify-docs-1 ...`), confirmed `pi-spawn -l` listed `pi-piverify-docs-1` alongside `tmux ls` showing it plus every pre-existing session untouched, then `pi-spawn -k piverify-docs-1` → `Killed session pi-piverify-docs-1`, after which `pi-spawn -l` correctly reported `No running pi-* sessions.` and `tmux ls` showed the original sessions still present, nothing else touched. The log file survived the kill (`cat` showed `PIVERIFY_OK` then `[pi-spawn] exit=0`) since logs are plain files, unaffected by killing the tmux session.

## 5. Gotchas (each cost real time to find)

**`-nt` silently kills tool use and the model fabricates an answer.** `-nt` = `--no-tools`, and it disables the `subagent` tool along with everything else. Symptom: you ask it to delegate, it replies with a plausible tool-call-shaped JSON blob as plain *text*, and `toolResults` in `--mode json` output is `[]`. No child process ever ran. This is the single most expensive trap in this setup — if a response looks like a tool call but reads like prose and `toolResults` is empty, this is why. Never pass `-nt`/`--no-tools` when you want delegation to actually happen.

**A quote-verified review finding proves the text, not the citation.** `reviewer` appends the exact source text of every line it cites — `path:line: severity: problem. fix. [<line text>]` — so you can check any citation with one `sed -n '<N>p'`. Measured at 11/11 exact matches across 6 runs, and it did fix the original failure (line numbers eyeballed from a `read` and never grepped). But it verifies text-fidelity only. Where two lines share identical text — repeated guard clauses, copy-pasted error handling, identical returns — a citation pointing at the *wrong occurrence* quotes just as perfectly, and no amount of re-running detects it. The reviewer is now told to name the enclosing function when a line's text is not unique, but treat quote-verified findings on boilerplate-heavy code as "the text is right", not "the location is right". Same caveat for multi-line defects: the citation anchors the symptom line, and the interacting line is only named in prose.

**`{previous}` fails silently and the chain still looks successful.** Substitution is a plain string replace (`index.ts:552`: `step.task.replace(/\{previous\}/g, previousOutput)`). If the orchestrating model does not literally type the token into a step's task string, that replace is a no-op: the downstream agent receives **no prior context at all**, and rather than failing it fabricates plausible-looking input. Observed live on `/implement-and-review` — worker(2) grepped the sandbox for the word "review", found nothing, reasoned "maybe the feedback is not in repository but the task expects us to recall typical feedback", and guessed. The final file looked correct by coincidence. There is no error and nothing to notice; the chain reports success. Mitigation now in all three templates: a REQUIRED paragraph demanding the literal seven-character token. Measured after that change: **7/7 fresh runs compliant, 13/13 individual chain steps carried the token** (1 × `/scout-and-plan`, 1 × `/implement`, 5 × `/implement-and-review` — the template that had failed). Each run phrased the surrounding sentence differently, so the model is following the instruction rather than reciting a memorised string, and real content was confirmed in every downstream step's first message. Treat that as a real fix, not a proof: a residual failure rate of, say, 1-in-10 would not be visible in a sample this size. When a chain's output matters, verify the handoff yourself in the `--mode json` `tool_execution_start` args before trusting the result.

**A missing `tools:` line means ALL tools, not none — including recursive `subagent`.** `worker.md` still has no `tools:` frontmatter key, on purpose — that grants read, grep, find, ls, bash, edit, write, *and* the `subagent` tool itself. Confirmed from source: the child-process args builder (`index.ts:294-296`) only ever adds `--model` and, *conditionally*, `--tools` (`if (agent.tools && agent.tools.length > 0)`) — when `agent.tools` is empty/undefined, no `--tools` flag reaches the child at all, so it inherits `pi`'s ordinary default tool set with nothing stripped out. There is no depth counter, no recursion guard, and no code path that special-cases or excludes `subagent` itself anywhere in this file. **Practical consequence: `worker` can recursively spawn its own subagents**, nesting a third `pi` process inside the second — bounded only by a rule in `worker.md`'s own body ("only one level deep... Nothing in the harness enforces this"), not by anything mechanical.

`grunt.md` used to be in the same position — no `tools:` line, same recursion risk — and is in fact how this was found. It's now closed: `grunt.md` carries an explicit allowlist, `tools: read, grep, find, ls, bash, edit, write`, that leaves `subagent` out on purpose, with a comment in the frontmatter explaining why. A mechanical editor no longer has any path to recurse.

Verified live, both before and after the fix, same command:
```
pi -p --tools subagent "use grunt to use scout to find where pi.registerTool appears in index.ts, report file:line only"
```
- **Before** (`grunt.md` had no `tools:` line): 16.3s wall-clock — roughly double the 8.83s a single scout-only hop takes (see §2), consistent with two sequential child-process spawns.
- **After** (`grunt.md` has the explicit allowlist): 6.85s wall-clock — in line with a single hop, not two. `grunt` answered from its own `read`/`grep`/`bash` access instead of delegating, because it now has no `subagent` tool to delegate with.

Both runs returned the same correct answer (`index.ts:461`), so the timing delta — not the content — is what demonstrates the fix. (Caveat on the "before" run: `grunt` also had its own read/grep access at the time, so that run alone couldn't rule out `grunt` having answered directly instead of truly delegating; the source-level fact was, and for `worker` still is, the load-bearing evidence — the live runs are corroborating.) If you want a restricted agent you must list `tools:` explicitly, as `grunt.md` now does; omitting it is not the safe default, and it isn't even bounded to non-recursive tools.

**`agentScope` escalation in headless runs is now refused, not silently allowed — this used to be a real hole.** Default scope (`index.ts:473`) skips loading a cloned repo's `.pi/agents/*.md`. Escalating to `"project"` or `"both"` is gated behind a `confirmProjectAgents` dialog (`index.ts:521`) that checks `ctx.hasUI` — which is `false` under `-p` (headless). Previously, that meant a headless run could widen scope and execute repo-controlled agent definitions with zero confirmation prompt. **That hole is now closed.** A guard added at `index.ts:505-519` hard-refuses the call before the dialog code is ever reached:
```
if ((agentScope === "project" || agentScope === "both") && !ctx.hasUI) {
  return { content: [{ type: "text", text: `Refused: agentScope "${agentScope}" would run project-local agents from ${discovery.projectAgentsDir ?? `${CONFIG_DIR_NAME}/agents`} without confirmation, and no UI is available in this headless run to ask. Omit agentScope (defaults to "user") or run interactively.` }], ... };
}
```
Confirmed from source: the guard's condition never references `confirmProjectAgents` at all — there's no UI in a headless run to have granted a waiver from in the first place, so the parameter can't matter here. Confirmed live too: calling the subagent tool headless with `agentScope: "both", confirmProjectAgents: false` still returned the `Refused: agentScope...` text verbatim — passing `false` did not bypass it. Also worth knowing: `fireworks/gpt-oss-120b` has reportedly been observed spontaneously passing `agentScope: "both"` while driving chain mode on unrelated questions (not independently reproduced by me) — under the old code that would have silently loaded repo-controlled agents with zero confirmation; now it gets refused and the model self-corrects on retry, at the cost of one wasted round trip. A backportable copy of the same guard lives at `/home/schmi/projs/skills/pi-delegation/subagent-headless-scope.patch` (a 25-line unified diff, inserting the same 16 lines of code shown above) for applying the fix to another checkout. Leave `agentScope` at its default (`"user"`) outside interactive sessions regardless — the guard is a backstop, not a reason to pass escalated scope on purpose in headless runs.

**Subagents inherit no conversation context.** Each is a brand-new `pi` process with an empty context window. A task string like "fix the bug we just discussed" means nothing to it — every task string passed to `subagent`, a parallel `tasks[]` entry, or `pi-spawn` must be fully self-contained (file paths, exact names, the actual question).

## 6. Adding a new agent

Drop a new `~/.pi/agent/agents/<name>.md` (user scope — never repo `.pi/agents/`, see §5) with frontmatter:

```markdown
---
name: my-agent
description: One line — what it's for and what it must never do.
tools: read, grep, find, ls        # omit entirely for ALL tools; list explicitly to restrict
model: fireworks/<model-id>
---

Body: rules, output format, escalation condition.
```

Valid tool names: `read`, `grep`, `find`, `ls`, `bash`, `edit`, `write` — each registered under that literal name by its own module in the pi package (`dist/core/tools/read.js:134`, `grep.js:75`, `find.js:71`, `ls.js:57`, `bash.js:227`, `edit.js:161`, `write.js:134`). Anything else is not a recognized allowlist entry. (`index.ts:296` only forwards whatever list you write to the child's `--tools` flag; it does not validate the names.)

Keep the body pattern used by the existing seven: state what it must never do, give an exact output format, and give it an explicit escape hatch (e.g. `ESCALATE: <reason>`) for anything outside a narrow, unambiguous task — that's what keeps a cheap model from guessing instead of failing loudly.

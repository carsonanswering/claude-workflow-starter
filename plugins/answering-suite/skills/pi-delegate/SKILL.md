---
name: pi-delegate
description: >-
  Delegate work OUT of Claude Code and INTO the `pi` coding-agent harness — cheap Fireworks-backed agents (scout, grunt, bulk, tester, reviewer, planner, worker) that have REAL tool access (read files themselves, grep a repo, run a test suite, edit code). Use when the work needs tools but not frontier judgment. Trigger phrases: "delegate to pi", "use the pi harness", "spawn a pi agent", "offload this to a cheap agent with tools", "run this in the background with pi", "pi-spawn", or naming a roster agent (scout, grunt, bulk, tester, reviewer, planner, worker).
---

# pi-delegate — cheap agents with real tools

`pi` (`/opt/homebrew/bin/pi`, v0.82.0) is a separate coding agent with its own config at `~/.pi/agent/`. A `subagent` tool inside it spawns a **real child `pi` process** per call — own context window, own tool allowlist, own model.

## Read this before running anything

**Every `pi` and `tmux` command in this file needs `dangerouslyDisableSandbox: true` on the Bash call.** `pi` writes lockfiles and session transcripts under `~/.pi/agent/`, which the sandbox denies. Without the flag the very first command dies with:

```
EPERM: operation not permitted, mkdir '/home/schmi/.pi/agent/settings.json.lock'
```

That error names a lockfile, not a sandbox, so it reads like a broken install — it isn't. Scope the flag to the `pi`/`tmux` call itself; nothing else here needs it.

**Budget the time.** A trivial single-agent call is ~6–9s wall clock; a chain is 40–70s; an 8-file bulk extraction ~18s. Set the Bash `timeout` to 300000 ms for chains and templates, ~180000 ms for single calls. There is no `timeout` binary on this machine — use the Bash tool's own parameter, and never a bare foreground `sleep`. Cost is negligible (a 7k-token `bulk` run was $0.0014), so re-running to verify beats trusting a doubtful result.

## Pick the right tool first

**Does the work need tools? Does it need judgment?**

| Need | Use |
|---|---|
| No tools, one-shot over text you already have (summarize, classify, extract, transform) | `fw` CLI — `fw-delegate` skill. Fastest, cheapest. |
| Tools (read/grep/bash/edit), but the task is narrow, mechanical, or bulk, and a wrong answer is cheap to catch | **This skill.** Also the only option for work that must outlive the session (`pi-spawn`). |
| Judgment call, frontier reasoning, or a wrong answer is expensive/hard to detect | Claude Code's own subagents. |

If you're unsure whether a pi agent's answer is real, see "Verify, don't trust" below before acting on it.

## Two mechanisms

| Mechanism | What it is | Reach for it when |
|---|---|---|
| `subagent` tool (in-session) | You ask a running `pi` session in plain language, or force it headless with `--tools subagent`. Blocks until done, result folds back into the conversation. | You want the result now, in this conversation. |
| `pi-spawn` (detached tmux) | `~/.pi/agent/bin/pi-spawn` runs a whole headless `pi -p` task in a detached tmux session, logs to `~/.pi/agent/logs/<name>.log`. Survives the parent session ending. | Task is long-running, or must outlive this session (walk away, check back later). |

Both shell out to the same `pi` binary and roster. `pi-spawn` is not reliably on PATH — call it by full path: `~/.pi/agent/bin/pi-spawn`.

## The roster (`~/.pi/agent/agents/*.md`, all Fireworks-backed)

| Agent | Model | Tools | Purpose |
|---|---|---|---|
| `scout` | `fireworks/qwen3p7-plus` | read, grep, find, ls, bash | Read-only recon, returns `file:line`, never fixes |
| `grunt` | `fireworks/gpt-oss-120b` | explicit allowlist, no `subagent` | Mechanical, fully-specified edits; says `ESCALATE:` rather than guess |
| `bulk` | `fireworks/deepseek-v4-flash` | read, grep, find, ls | Bulk summarize/classify/extract, 1M context, never edits |
| `tester` | `fireworks/gpt-oss-120b` | bash, read, grep | Runs a suite once, compressed failure lines |
| `reviewer` | `fireworks/minimax-m3` | read, grep, bash | Severity-tagged findings, each quoting its own source line |
| `planner` | `fireworks/minimax-m3` | read, grep, find, ls | Implementation plans, no edits |
| `worker` | `fireworks/gpt-oss-120b` | none listed = **all tools** | General implementer for the chains; can recurse one level |

claude-* models are not used in pi and are not supported by this setup — every `claude-*` call currently 400s (subscription auth conflict). Don't try to route around this.

## Invocations (each verified this session)

**Single agent, forced headless** (omit `--tools subagent` in an interactive session — the model picks the tool up on its own from plain language):
```bash
pi -p --model fireworks/gpt-oss-120b --tools subagent \
  "use scout to find where pi.registerTool appears in ~/.pi/agent/extensions/subagent/index.ts, report file:line"
```

**Parallel** (becomes one `subagent` call with `{tasks:[...]}`, max 8, 4 concurrent — name each sub-task explicitly):
```bash
pi -p --model fireworks/gpt-oss-120b --tools subagent \
  "run 2 scouts in parallel: one find where the subagent tool is registered in ~/.pi/agent/extensions/subagent/index.ts, one find where agentScope default is set in the same file"
```

**Chain** (`{previous}` is a literal-string substitution of the prior step's output — you must type the token verbatim in the prompt or the next step gets nothing, see gotcha #2):
```bash
pi -p --model fireworks/gpt-oss-120b --tools subagent \
  "chain: first use scout to find where the subagent tool is registered in ~/.pi/agent/extensions/subagent/index.ts, report exact file:line, then use planner to write a one-step plan for renaming that tool to 'delegate', citing the exact file:line and current tool name from the prior step using {previous}"
```

**Slash-command template** (expands in headless `pi -p` too, not just the TUI):
```bash
pi -p "/implement fix the bug in ./buggy.py so add(2,3) returns 5"
```
Templates: `/scout-and-plan` (scout→planner, plan only), `/implement` (scout→planner→worker), `/implement-and-review` (worker→reviewer→worker). All live in `~/.pi/agent/prompts/`.

**Backgrounded (`pi-spawn`)** — for anything that should outlive this session:
```bash
~/.pi/agent/bin/pi-spawn -n audit-$$ -m fireworks/gpt-oss-120b "self-contained task prompt"
```
Pick a unique `-n` name — `$$`, a timestamp, or a task-specific slug. Session names are global across every session on the machine, and `pi-spawn` refuses to clobber an existing one, so a literal name like `mytask` collides with anyone else (including a concurrent agent) following this same file. `~/.pi/agent/bin/pi-spawn -l` lists what is already running.

Flags: `-m MODEL` (default `$PI_SPAWN_MODEL` or `fireworks/gpt-oss-120b`), `-d DIR` (working dir), `-n NAME` (session `pi-NAME`, log `NAME.log`), `-l` (list), `-k NAME` (kill, only `pi-*`).

Read the result — the log's last line is always the real exit status, captured via `${PIPESTATUS[0]}`, not tee's:
```bash
grep -q '^\[pi-spawn\] exit=0$' ~/.pi/agent/logs/<name>.log && echo ok || echo failed-or-still-running
cat ~/.pi/agent/logs/<name>.log
```

## Gotchas (each cost real time)

1. **`-nt` manufactures a convincing fake answer.** `-nt` = `--no-tools`, disables `subagent` along with everything else. Symptom: the model replies with a plausible tool-call-shaped JSON blob as plain *text*; under `--mode json`, `toolResults` is `[]`. No child process ever ran. Looks exactly like a delegated answer. Never pass `-nt`/`--no-tools` when you want tool use.
2. **`{previous}` fails silently, chain still reports success.** It's a plain string replace (`index.ts:552`). If the orchestrating model doesn't literally type the token, the downstream agent gets zero prior context and invents plausible input instead of failing loudly. Verify handoffs you care about with `--mode json` (see below) rather than trusting the chain's own summary.
3. **Omitting `tools:` in an agent file grants everything, including `subagent` itself** — no depth guard anywhere. `worker` can recurse one level by design; if you write a new mechanical-editor agent, give it an explicit allowlist (like `grunt`) or it inherits recursive delegation too.
4. **`agentScope` must stay `"user"` (the default) in headless runs.** The extension hard-refuses `"project"`/`"both"` under `-p` because the confirmation dialog needs `ctx.hasUI` (false headless). `gpt-oss-120b` has been observed passing `agentScope:"both"` unprompted — it gets refused and self-corrects, costing one wasted round trip. Don't pass an escalated scope on purpose either way.
5. **Subagents have empty context — every task string must be fully self-contained.** File paths, exact names, the real question. "fix the bug we discussed" means nothing to a fresh child process.
6. **A reviewer citation quoting its source line proves the TEXT, not that it's the right occurrence.** Where two lines are identical (copy-pasted guard clauses, repeated error handling), a citation can point at the wrong one and still quote perfectly. Spot-check with `sed -n '<N>p' <file>` for the value, but don't stop there on boilerplate-heavy code — check the citation names a unique enclosing function/context too.

## Verify a delegated result is real, not fabricated

- **Nonce technique**: ask for an exact, arbitrary string back (`say EXACTLY: SKILL_VERIFY_9f31`) and grep the output for it — cheap smoke test that the process actually ran and returned.
- **`--mode json`**: inspect `tool_execution_start`/`tool_execution_end` events directly instead of trusting the parent's prose summary:
  ```bash
  pi -p --model fireworks/gpt-oss-120b --tools subagent --mode json "..." \
    | grep -E '"type":"tool_execution_(start|end)"'
  ```
  Confirms which agent actually ran, its real args, and its real result — including cases where the model picked a nonexistent agent name and got a clean `Unknown agent:` error back instead of a hallucinated answer.
- **`ps`**: while a call is in flight, `ps aux | grep '[p]i '` shows the real child process(es).
- For `pi-spawn`, the `[pi-spawn] exit=` line is ground truth for success/failure; don't infer success from the presence of output alone.

## Adding a new agent

Drop `~/.pi/agent/agents/<name>.md` (user scope only — never repo `.pi/agents/`, see gotcha #4):
```markdown
---
name: my-agent
description: One line — what it does, what it must never do.
tools: read, grep, find, ls   # omit entirely = ALL tools; list explicitly to restrict
model: fireworks/<model-id>
---
Body: rules, output format, explicit escalation condition (e.g. `ESCALATE: <reason>`).
```
Valid tool names: `read`, `grep`, `find`, `ls`, `bash`, `edit`, `write`. Anything else is silently not forwarded. Omitting `tools:` is not a safe default — it grants everything including `subagent`, unbounded.

## Reference

Full operator manual: `~/.pi/agent/README-delegation.md`, mirrored to the shared team repo at `/home/schmi/projs/skills/pi-delegation/`.

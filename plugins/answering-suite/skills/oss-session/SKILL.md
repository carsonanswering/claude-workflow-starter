---
name: oss-session
description: Runs and manages Claude Code sessions backed by open-source Fireworks models through the `claude-oss` launcher and its LiteLLM proxy on :4000.
disable-model-invocation: true
---

# oss-session — Claude Code on open models

`claude-oss` (`~/.local/bin/claude-oss`) launches full Claude Code against a local LiteLLM proxy that translates the Anthropic Messages API to Fireworks. Regular `claude` is untouched — env vars scoped inside the launcher.

## Invocation

```bash
claude-oss              # interactive session on open models
claude-oss -p "task"    # non-interactive one-shot (usable as cheap agentic worker)
```

Launcher auto-starts the proxy on `http://localhost:4000` if down, waits for liveness, then execs `claude` with `ANTHROPIC_BASE_URL` pointed at it.

## Current model mapping

- Main: `deepseek-v4-pro`
- Small/fast (background tasks): `gpt-oss-120b`
- Wildcard: any other model name routes to deepseek

To change: edit `ANTHROPIC_MODEL` / `ANTHROPIC_SMALL_FAST_MODEL` in the launcher AND ensure a matching route in `~/.config/litellm/config.yaml` (wildcard covers unknown names). A running proxy keeps its old config in memory, so finish the change: `pkill -f litellm` (the next `claude-oss` auto-starts it), then confirm the new route answers with `claude-oss -p "say ok"` before relying on it.

Other Fireworks models seen in use: `kimi-k2p6`, `glm-5p2`. This roster drifts as Fireworks adds and retires models — probe one before relying on it: `fw -m glm-5p2 -t 5 "ok"`.

## Cheap agentic worker pattern

When the main (frontier) session needs a worker WITH tool access but the task is low-stakes grunt work, spawn:

```bash
claude-oss -p "narrow, falsifiable task with expected output format" 2>&1
```

Verify the worker's changes yourself before accepting them — `git diff` the tree and rerun the tests it touched; open models fumble precise edits and long tool loops. For stateless one-shot calls prefer the `fw` CLI (see fw-delegate skill) — no proxy, faster. For a fleet of Claude-quality subagents, that is the frontier-orchestrator skill; this launcher is the open-model, low-stakes lane.

## Proxy operations

```bash
curl -s localhost:4000/health/liveliness   # is it up
tail -f ~/.config/litellm/proxy.log        # watch traffic
pkill -f litellm                           # stop
~/.local/bin/litellm --config ~/.config/litellm/config.yaml --port 4000  # manual start (the launcher resolves this via `command -v litellm`)
```

## Known constraints

- Subscription features unavailable (web login and other subscription-gated extras)
- deepseek reasoning: TTFT p50 ~2.2s / p95 ~5.4s; quality below Claude on complex agentic work
- Fireworks key from `~/.zshenv`; calls bill the Fireworks account
- Full docs: `~/projs/open-sourced/README.md`

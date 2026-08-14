# Stack decision

**Decision: Python 3.12+, Claude Agent SDK for employees, flat-file JSON storage, CLI-first. No web framework in MVP.**

## Why

- **Employees = agents.** Data model already maps Employee 1:1 to a Claude Agent SDK agent (job description → system prompt, tool allowlist → SDK tools). Using the SDK means the manager loop orchestrates sessions instead of reimplementing an agentic loop.
- **Python over TypeScript.** Faster iteration for a solo/lean project; SDK parity is fine; all prior art in this workspace (meeting-copilot) is Python — shared tooling habits.
- **Flat files over DB.** Journal is append-only JSONL per employee; company config is YAML; task queue is JSON. Data model is storage-agnostic by design — swap in SQLite when concurrency demands it, not before.
- **CLI-first.** Owner interactions (approve gated action, read standup) are terminal commands in MVP. Web UI is a Phase 3+ concern; Polsia's failures are trust failures, not UI failures.

## Explicitly rejected for MVP

- Celery/cron worker fleet (Polsia's shape) — one supervised manager-loop process is enough and stays debuggable.
- Multi-tenant anything.
- Custom agent runtime — don't rebuild what the SDK gives (sessions, tool permissioning, streaming).

## Revisit triggers

- Journal contention or query needs → SQLite.
- Long-running employees needing durable resume → SDK session persistence evaluation.
- First external user → auth + web surface conversation.

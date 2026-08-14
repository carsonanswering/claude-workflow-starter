# Backlog

Worked top-down by autonomous loop. Each iteration: pick first unchecked task, do it, check it off, append new tasks discovered, commit.

## Phase 0 — shape the product

- [x] Research pass: what Polsia actually ships — findings/polsia-teardown.md (gaps: no approval gates, unauditable completion ~21% real success, billing opacity, asset lock-in, shallow moat = Claude Code CLI on Celery cron)
- [x] Define MVP scope — docs/mvp.md (roles: Engineer + Marketer; toyco YAML config; CLI approval gate mid-flight; gaps 1-2 in code, 3-5 positioning)
- [x] Design core data model: Company, Employee (role, prompt, tools, approval gates), Task, Journal — docs/data-model.md (dataclasses+ULIDs, gates as action tags on Employee, append-only journal = source of truth)

## Phase 1 — skeleton

- [x] Choose stack — docs/stack.md (Python + Claude Agent SDK, flat-file JSONL/YAML, CLI-first, no Celery/web/multi-tenant in MVP)
- [x] Scaffold package: company config loader (YAML), Employee abstraction, in-memory task queue — ai_employees/ (models, config, task_queue, journal), examples/toyco.yaml
- [x] Manager loop v0: pull task from backlog, route to employee by role, collect result into journal — ai_employees/manager.py; EmployeeRunner seam + MockRunner (real Claude Agent SDK runner deferred, no SDK dep yet)
- [x] Tests for routing + journal — tests/ (37 passing, offline; covers config, state machine incl. gate pause/approve/reject, standup digest citations)

## Phase 2 — make it real

- [x] One real end-to-end demo — LIVE run verified 2026-07-19: no API key needed (SDK rides Claude Code CLI auth); Engineer shipped real index.html/styles.css/test.mjs, Marketer paused at send_external with real draft, approved, completed unsent
- [x] Human approval gate: tasks flagged high-stakes pause for owner sign-off — CLI prints the concrete draft (pending_gate_context) and prompts y/n; rejection -> cancelled covered in tests
- [x] Standup generator: daily digest from journals — printed after `run` and via `standup` subcommand; written to runs/<company>/standup.md, cites journal entry IDs

## Phase 3 — harden and extend

- [x] Implement `hire` CLI — ai_employees/templates.py (5 templates), cli.py hire subcommand (Y/n/edit, YAML round-trip append, hired journal entry), 6 tests
- [x] Manager review quality check — ReviewPolicy seam + accept_all default, bounded send-back (max_review_rounds=2, then failed), scripted MockRunner fixture, 3 tests
- [x] Employee workspace isolation — per-employee dir under runs/<company>/workspace/, SDK cwd option, mtime-snapshot scan records new/changed files as `file` evidence, 7 tests

## Phase 4 — close the loop

- [x] LLM-judge ReviewPolicy — ai_employees/reviewer.py (haiku judge, strict-JSON verdict, judge failure never blocks: accept+warn), 12 tests
- [x] send_external transport — ai_employees/outbox.py (Outbox dir-backed, Transport protocol, Mock/File transports), approved agents write outbox/*.json instead of sending, flush-outbox CLI delivers + journals, 8 tests
- [x] Goal decomposition — ai_employees/planner.py (LLMPlanner strict JSON + PlanningError loud-fail, StaticPlanner), `run --plan` prints plan + Y/n confirm, planned journal entries, 11 tests; `--review llm` flag wires judge into run

## Phase 5 — candidates (from live smoke findings)

- [x] Judge evidence depth — workspace_resolver on LLMReviewPolicy inlines file evidence (1500 chars/file, 6000 total budget, binary/missing markers), 9 tests
- [x] Per-task wall-clock budget — ClaudeAgentRunner task_timeout_s (default 600, asyncio.wait_for, timeout = failed RunResult), `--task-timeout` flag (0 disables), elapsed printed per task, 17 tests
- [x] Judge calibration harness — ai_employees/calibration.py (10-case hand-labeled golden set, precision/recall/F1 per ReviewPolicy variant), `calibrate` CLI subcommand (--model repeatable, --no-baseline), 19 tests. agentest crossover not pursued: golden-set-vs-fixed-ReviewPolicy-interface is enough for this repo's scope; no cross-repo dependency added.

## Parking lot

- [x] Pricing/positioning notes vs Polsia — docs/pricing-positioning.md (flat $99/$79/$59-69 per-seat vs Polsia $49 + 20% take-rate; 11x/Artisan real prices $2k-15k/mo)
- [x] Employee "hiring" UX — docs/hiring-ux.md (templates = Employee YAML fragments, hire CLI Y/n/edit, gates default-on opt-out, marketplace excluded)

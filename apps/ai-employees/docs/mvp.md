# MVP scope

Decision doc. One sentence of positioning: Polsia sells autonomy as a black box; we
sell **legibility** — the MVP must demonstrate approval gates (teardown gap 1) and
auditable completion (gap 2). Per-task accounting, own-your-accounts, and flat
pricing (gaps 3–5) are positioning we design *toward* but do not build yet.

## 1. First employee roles: Engineer + Marketer (two, not three)

| Role | Why first | Gate profile |
|---|---|---|
| **Engineer** | Attacks gap 2 head-on: Polsia's ~21% real completion rate came from "complete" tasks that never deployed. Engineering work produces the cheapest verifiable evidence — diffs, test output, deploy URLs — so the journal proves completion instead of asserting it. | `deploy_prod`, `delete_data` |
| **Marketer** | Attacks gap 1 head-on: Polsia's worst documented damage is unauthorized outreach (wrong names, wrong prices, unapproved cold emails). A gated `send_external` action is the sharpest possible demo of "the AI drafted it, the owner approved it." | `send_external`, `spend_money` |

Rejected for MVP:

- **Chief of Staff** — its job (assign, review, digest) *is* the manager loop.
  Making it an employee adds an agent hop with no new capability; revisit only if
  the manager itself needs LLM judgment beyond routing.
- **Ops / Support / Finance** — no third role adds a new *kind* of evidence or
  gate; they add breadth, and breadth is Polsia's mistake (nine agents, none
  accountable). Two roles with different gate profiles already prove per-role trust.

## 2. Company config (YAML)

One file per company; loads into the `Company` + `Employee` dataclasses from
docs/data-model.md. IDs are assigned at load (ULIDs); YAML uses local names.
`resources` holds handle *names* only, never secret values.

```yaml
name: toyco
owner: schmidtcarson016@gmail.com          # approval requests go here
goals:                                  # ordered, highest priority first
  - Launch a landing page for the ToyCo waitlist
  - Draft and send one announcement email to the beta list
constraints:                            # injected into every employee prompt
  - Spend $0 — free tiers only
  - No external communication without owner approval
  - Tone: plainspoken, no hype
resources:
  repo: github.com/carsonanswering/toyco-site
  domain: toyco.example.com
  email_api_key: TOYCO_RESEND_KEY       # env var name, not the secret

employees:
  - name: Eng-1
    role: engineer
    job_description: >
      Build and ship ToyCo's web presence. Scope: this repo only. Quality bar:
      tests pass, page renders. Escalate anything touching prod or data.
    tools: [Read, Write, Edit, Bash, Grep, Glob]
    approval_gates: [deploy_prod, delete_data]
    max_concurrent_tasks: 1

  - name: Mktr-1
    role: marketer
    job_description: >
      Write ToyCo's copy and outreach. Draft freely; NOTHING leaves the building
      without owner sign-off. Escalate pricing or claims you can't source.
    tools: [Read, Write, WebSearch, WebFetch]
    approval_gates: [send_external, spend_money]
    max_concurrent_tasks: 1
```

## 3. Cut lines

**IN (MVP):**

- Config loader: YAML above → dataclasses; validation errors are human-readable.
- **Manager loop v0**: pull highest-priority `queued` task, route by
  `assignee_role`, run the employee (Claude Agent SDK session), collect result,
  drive the task state machine. Single-threaded, one task at a time.
- **Journals**: append-only JSONL per company; every transition and tool action
  becomes a `JournalEntry` with evidence refs. Source of truth, per data-model.
- **Approval gate**: task pauses mid-flight at `awaiting_approval` when its
  `gate_tags` intersect the employee's `approval_gates`; owner approves/rejects
  via CLI prompt (or `approve <task-id>` command). Concrete context shown
  ("send *this* email?"), never hypothetical pre-clearance.
- **Standup digest**: generated from journal window; per-employee done /
  in-progress / blocked, pending-approvals action list, narrative citing journal
  entry IDs. Printed to terminal and written to a file.
- Tests for routing, state machine, gate intersection, journal append.

**OUT (explicitly deferred):**

- Web UI — CLI-first; the journal and digest are text and must be good as text.
- Multi-tenant / hosted anything — one company, one process, local disk.
- Marketplace / employee templates ("hiring" UX) — parking lot.
- Billing, metering, credits — gap 3 is positioning, not MVP code.
- Infrastructure provisioning (servers, Stripe, domains) — we operate inside
  accounts the owner already has (gap 4 by construction, zero code).
- Scheduling/cron, parallel employees, retries beyond a fixed bound, ChromaDB or
  any vector store, Postgres — JSON files on disk are enough.

## 4. Success criteria — end-to-end demo

The demo passes when all of the following hold in one run against the `toyco`
config, human at the terminal:

1. **Two employees execute a toy goal**: manager routes at least one task to
   Eng-1 and one to Mktr-1; both reach `done` through the full state machine
   (`queued → assigned → in_progress → review → done`).
2. **One gated action is approved by the owner**: Mktr-1's announcement email
   hits `send_external`, the task lands in `awaiting_approval`, the CLI shows
   the actual draft, the owner approves, the task resumes and completes. A
   rejection path is also exercised in tests (task → `cancelled`).
3. **Completion is auditable**: every `done` task has journal entries with at
   least one evidence ref (diff, file, command output, or message body) — a
   reviewer can answer "what did Eng-1 do and how do I verify it" from the
   journal alone, without reading agent transcripts.
4. **Standup digest is generated** from the run's journal: correct per-employee
   task buckets, pending-approvals list empty at end, narrative cites real
   journal entry IDs (spot-checked to exist).
5. Nothing external actually sent: demo uses a mock/dry-run email tool — the
   gate, not the side effect, is what's being demonstrated.

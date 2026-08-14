# Hiring UX (post-MVP design note)

Status: design only. `mvp.md` cuts "marketplace / employee templates" — this
note exists so that when we build it, it slots onto the data model without a
rewrite. No code yet.

## 1. What a template is

A template is a **pre-built `Employee` YAML block** with the config fields
from `data-model.md` filled in except `name`: `role`, `job_description`,
`tools` (default allowlist), `approval_gates` (default gate profile). Hiring
= instantiate a template, ask for a `name`, append the result to the
company's `employees` list. No new dataclass, no new storage — a template is
just an `Employee` fragment missing `id`/`name`/`status`, plus one field
templates need that live employees don't: `description` (one line, shown to
the owner before hire — see §4).

## 2. CLI sketch

```
python -m ai_employees hire <template> --name X [--company toyco.yaml]

$ python -m ai_employees hire engineer --name Eng-2
Role: engineer
Job description:
  Build and ship <company>'s web presence. Scope: this repo only. Quality
  bar: tests pass, page renders. Escalate anything touching prod or data.
Default tools: Read, Write, Edit, Bash, Grep, Glob
Default approval gates: deploy_prod, delete_data
Hire Eng-2 with these defaults? [Y/n/edit]
```

`edit` drops the owner into `$EDITOR` on the rendered `Employee` block before
it's appended — same review step as hand-writing YAML, just pre-filled.
`n` aborts with no write. On `Y`, the block is appended to `employees:` in
the company YAML (an `id` (ULID) and `status: active` are assigned at next
load, per data-model.md — hiring only touches the YAML, never invents IDs
itself) and a `JournalEntry` (`action: "hired"`, `employee_id: "manager"`,
`task_id: None`) records it, satisfying "hiring events" already carved out
in the JournalEntry schema.

## 3. Launch templates (4–5)

| Template | role | default tools | default `approval_gates` | why this gate profile |
|---|---|---|---|---|
| **engineer** | `engineer` | `Read, Write, Edit, Bash, Grep, Glob` | `deploy_prod, delete_data` | matches toyco.yaml Eng-1; irreversible/production actions gated, local dev free |
| **marketer** | `marketer` | `Read, Write, WebSearch, WebFetch` | `send_external, spend_money` | matches toyco.yaml Mktr-1; nothing leaves the building or spends money unreviewed |
| **support** | `support` | `Read, WebSearch` | `send_external, refund_money` | customer-facing replies and refunds are the two ways support burns trust or cash |
| **ops** | `ops` | `Read, Write, Bash` | `spend_money, delete_data, deploy_prod` | broadest tool access (infra-adjacent) gets the broadest gate profile — widest blast radius, most sign-off |
| **researcher** | `researcher` | `Read, WebSearch, WebFetch` | *(none by default)* | pure read/synthesize, no side-effecting tools in the allowlist at all — nothing to gate |

Every profile is a **subset of `Task.gate_tags`'s vocabulary**
(`send_external`, `spend_money`, `deploy_prod`, `delete_data`, plus
`refund_money` as a new tag support needs) so gate intersection at task-route
time works unmodified.

## 4. Staying legible

Two rules, both already implied by the MVP's "legibility over autonomy"
stance:

- **Owner reviews the job description before hire, every time.** The CLI
  prints the full prompt text pre-append (§2); there is no `--yes`/silent
  path for the description. The `job_description` *is* the employee's system
  prompt (data-model.md) — reviewing it is reviewing what the agent will
  actually be told to do, not a marketing summary of it.
- **Gates are opt-out, not opt-in.** Templates ship with gates *on* for
  every action tag in their profile; hiring never starts an employee at zero
  gates. Loosening a gate is an explicit edit the owner makes in the
  `edit` step or afterward in the company YAML — never a flag that skips the
  prompt. This mirrors the data-model decision that gates live on the
  employee and are matched per-task, so a template's defaults are a
  starting *ceiling* on trust, not a floor.

## 5. Explicitly out of scope

- **Marketplace** — no discovery, ranking, or third-party-authored
  templates. Templates ship in-repo (`ai_employees/templates/*.yaml`), same
  trust boundary as the rest of the codebase.
- **Payments** — no per-template pricing, revenue share, or billing hook.
  Matches `mvp.md`'s gap 3 (billing/metering) being deferred wholesale.

Both are unblocked by this design (templates are just files; a marketplace
is a registry of more files) but neither is built here.

# ai-employees

Polsia-like autonomous company runner, reframed around **AI employees**: named roles with job descriptions, task queues, and accountability — not one opaque "AI that runs your company."

## Concept

- A **Company** is configured with goals, constraints, and resources.
- Work is done by **Employees**: role-scoped agents (e.g. Engineer, Marketer, Ops, Chief of Staff), each with:
  - a job description (system prompt + tool allowlist)
  - a personal task queue pulled from a shared company backlog
  - a work log (what was done, why, evidence)
- A **Manager loop** assigns tasks, reviews output, escalates high-stakes decisions to the human owner.
- Everything auditable: each employee's actions land in a per-employee journal; the owner reads standups, not raw logs.

## Differentiation vs Polsia

Polsia sells "AI runs your company while you sleep" as a black box. We sell legibility: you know *who* (which role) did *what* and *why*, you can hire/fire/retune individual employees, and high-stakes actions gate on human approval per-role.

## Status

Greenfield. See BACKLOG.md — worked by an autonomous loop that picks tasks top-down.

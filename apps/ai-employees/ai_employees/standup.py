"""Standup digest from a journal window. Narrative is template-generated in v0
(LLM later); every claim cites journal entry IDs."""

from .models import Company, Employee, JournalEntry, StandupDigest, Task


def generate_digest(
    company: Company,
    employees: list[Employee],
    tasks: dict[str, Task],
    entries: list[JournalEntry],
    period_start: str,
    period_end: str,
) -> StandupDigest:
    window = [e for e in entries if period_start <= e.timestamp <= period_end]
    window_ids = [e.id for e in window]
    by_name = {e.id: e.name for e in employees}

    per_employee = []
    for emp in employees:
        emp_tasks = [t for t in tasks.values() if t.assignee_id == emp.id]
        per_employee.append({
            "employee_id": emp.id,
            "done": [t.id for t in emp_tasks if t.state == "done"],
            "in_progress": [t.id for t in emp_tasks if t.state in ("in_progress", "review")],
            "blocked": [t.id for t in emp_tasks if t.state == "awaiting_approval"],
        })

    pending = [t.id for t in tasks.values() if t.state == "awaiting_approval"]

    lines = []
    for e in window:
        if e.action in ("completed", "escalated", "approved", "rejected"):
            who = by_name.get(e.employee_id, e.employee_id)
            lines.append(f"- {who}: {e.summary} [journal:{e.id}]")
    if pending:
        lines.append(f"Pending owner approval: {', '.join(pending)}")
    narrative = "\n".join(lines) if lines else "No notable activity in this window."

    return StandupDigest(
        company_id=company.id,
        period_start=period_start,
        period_end=period_end,
        per_employee=per_employee,
        pending_approvals=pending,
        narrative=narrative,
        journal_entry_ids=window_ids,
    )

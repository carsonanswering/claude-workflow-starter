"""Employee execution seam. Real implementation will wrap the Claude Agent SDK;
MockRunner keeps tests and demos offline."""

from dataclasses import dataclass, field
from typing import Protocol

from .models import Company, Employee, Task


@dataclass
class RunResult:
    status: str  # "completed" | "paused" | "failed"
    summary: str
    evidence: list[dict] = field(default_factory=list)
    gate_tag: str | None = None  # set when status == "paused"
    gate_context: str | None = None  # the concrete thing awaiting approval
    outbox_items: list[dict] = field(default_factory=list)  # {"kind", "payload"} drafts to deliver


class EmployeeRunner(Protocol):
    def run(
        self,
        employee: Employee,
        task: Task,
        company: Company,
        approved_gates: frozenset[str] = frozenset(),
    ) -> RunResult: ...


class MockRunner:
    """Deterministic runner: pauses at the first gated tag not yet approved,
    otherwise completes with synthetic evidence."""

    def __init__(
        self,
        fail_task_ids: set[str] | None = None,
        scripted_results: dict[str, list[RunResult]] | None = None,
    ) -> None:
        self.fail_task_ids = fail_task_ids or set()
        # task_id -> queue of RunResults to return in order (one per call),
        # for scripting fail-then-pass review fixtures. Falls back to the
        # default deterministic behavior once a task's queue is exhausted.
        self.scripted_results: dict[str, list[RunResult]] = {
            task_id: list(results) for task_id, results in (scripted_results or {}).items()
        }
        self.calls: list[tuple[str, str]] = []  # (employee_id, task_id)

    def run(
        self,
        employee: Employee,
        task: Task,
        company: Company,
        approved_gates: frozenset[str] = frozenset(),
    ) -> RunResult:
        self.calls.append((employee.id, task.id))
        queued = self.scripted_results.get(task.id)
        if queued:
            return queued.pop(0)
        if task.id in self.fail_task_ids:
            return RunResult(status="failed", summary=f"{employee.name} hit an error on '{task.title}'")
        pending = [
            g for g in task.gate_tags
            if g in employee.approval_gates and g not in approved_gates
        ]
        if pending:
            gate = pending[0]
            return RunResult(
                status="paused",
                summary=f"{employee.name} paused at gated action '{gate}'",
                gate_tag=gate,
                gate_context=f"[draft] {task.title}: output pending owner approval for '{gate}'",
            )
        return RunResult(
            status="completed",
            summary=f"{employee.name} completed '{task.title}'",
            evidence=[
                {
                    "kind": "message",
                    "ref": f"mock://{task.id}",
                    "excerpt": f"mock output for '{task.title}'",
                }
            ],
        )

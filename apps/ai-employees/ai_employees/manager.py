"""Manager loop v0: pull -> route by role -> run -> journal every transition.
Single-threaded, one task at a time."""

from typing import Callable, Optional

from .journal import Journal, state_change_summary
from .models import MANAGER_ID, OWNER_ID, Company, Employee, JournalEntry, Task
from .runner import EmployeeRunner, RunResult
from .task_queue import TaskQueue


class RoutingError(Exception):
    pass


# A ReviewPolicy inspects the employee's completed RunResult and decides whether
# the manager accepts it. Return None to accept; return a non-empty reason string
# to send the task back to the employee for another round.
ReviewPolicy = Callable[[Task, RunResult], Optional[str]]


def accept_all(task: Task, result: RunResult) -> str | None:
    """Default policy: current behavior, always accepts."""
    return None


class Manager:
    def __init__(
        self,
        company: Company,
        employees: list[Employee],
        queue: TaskQueue,
        journal: Journal,
        runner: EmployeeRunner,
        review_policy: ReviewPolicy = accept_all,
        max_review_rounds: int = 2,
    ) -> None:
        self.company = company
        self.employees = employees
        self.queue = queue
        self.journal = journal
        self.runner = runner
        self.review_policy = review_policy
        self.max_review_rounds = max_review_rounds
        self.tasks: dict[str, Task] = {}
        self._approved_gates: dict[str, set[str]] = {}
        self.pending_gate_context: dict[str, str] = {}
        self._review_rounds: dict[str, int] = {}

    def submit(self, task: Task) -> None:
        self.tasks[task.id] = task
        self.queue.push(task)

    def route(self, task: Task) -> Employee:
        for e in self.employees:
            if e.role == task.assignee_role and e.status == "active":
                return e
        raise RoutingError(f"no active employee for role '{task.assignee_role}'")

    def run_once(self) -> Task | None:
        """Process one task from the queue. Returns it, or None if queue empty."""
        task = self.queue.pop()
        if task is None:
            return None
        self.tasks[task.id] = task
        employee = self.route(task)

        task.assignee_id = employee.id
        self._change_state(task, "assigned", MANAGER_ID)
        self.journal.append(JournalEntry(
            employee_id=employee.id,
            task_id=task.id,
            action="claimed",
            summary=f"{employee.name} claimed '{task.title}'",
        ))
        self._change_state(task, "in_progress", employee.id)
        self._execute(task, employee)
        return task

    def approve(self, task_id: str) -> Task:
        task = self.tasks[task_id]
        if task.state != "awaiting_approval":
            raise ValueError(f"task {task_id} is '{task.state}', not awaiting_approval")
        employee = self._employee_by_id(task.assignee_id)
        gate = self.pending_gate_context.pop(task_id, None)
        self._approved_gates.setdefault(task_id, set()).update(
            g for g in task.gate_tags if g in employee.approval_gates
        )
        self.journal.append(JournalEntry(
            employee_id=OWNER_ID,
            task_id=task_id,
            action="approved",
            summary=f"owner approved gated action on '{task.title}'",
            evidence=[{"kind": "message", "ref": f"task://{task_id}", "excerpt": gate}] if gate else [],
        ))
        self._change_state(task, "in_progress", OWNER_ID)
        self._execute(task, employee)
        return task

    def reject(self, task_id: str) -> Task:
        task = self.tasks[task_id]
        if task.state != "awaiting_approval":
            raise ValueError(f"task {task_id} is '{task.state}', not awaiting_approval")
        self.pending_gate_context.pop(task_id, None)
        self.journal.append(JournalEntry(
            employee_id=OWNER_ID,
            task_id=task_id,
            action="rejected",
            summary=f"owner rejected gated action on '{task.title}'",
        ))
        self._change_state(task, "cancelled", OWNER_ID)
        task.result = "cancelled: owner rejected gated action"
        return task

    def _execute(self, task: Task, employee: Employee) -> None:
        result = self.runner.run(
            employee, task, self.company,
            approved_gates=frozenset(self._approved_gates.get(task.id, set())),
        )
        if result.status == "paused":
            self.pending_gate_context[task.id] = result.gate_context or ""
            self.journal.append(JournalEntry(
                employee_id=employee.id,
                task_id=task.id,
                action="escalated",
                summary=result.summary,
                evidence=[{
                    "kind": "message",
                    "ref": f"gate://{result.gate_tag}",
                    "excerpt": result.gate_context,
                }],
            ))
            self._change_state(task, "awaiting_approval", employee.id)
        elif result.status == "completed":
            self._change_state(task, "review", employee.id)
            self._review(task, employee, result)
        else:
            self._change_state(task, "failed", employee.id)
            task.result = result.summary
        self.tasks[task.id] = task

    def _review(self, task: Task, employee: Employee, result: RunResult) -> None:
        reason = self.review_policy(task, result)
        if reason is None:
            self._accept(task, employee, result)
            return

        used_rounds = self._review_rounds.get(task.id, 0)
        exhausted = used_rounds >= self.max_review_rounds
        self.journal.append(JournalEntry(
            employee_id=MANAGER_ID,
            task_id=task.id,
            action="sent_back",
            summary=(
                f"manager rejected '{task.title}' (round {used_rounds + 1}, retries exhausted): {reason}"
                if exhausted
                else f"manager sent back '{task.title}' (round {used_rounds + 1}): {reason}"
            ),
        ))
        # review -> in_progress on every send-back, per the TRANSITIONS table
        # (failed is only reachable from in_progress, not directly from review).
        self._change_state(task, "in_progress", MANAGER_ID)

        if exhausted:
            task.result = (
                f"failed: review retries exhausted after {used_rounds} round(s); "
                f"last reason: {reason}"
            )
            self._change_state(task, "failed", MANAGER_ID)
            self.tasks[task.id] = task
            return

        self._review_rounds[task.id] = used_rounds + 1
        task.description = (
            f"{task.description}\n\n[Manager feedback - review round "
            f"{used_rounds + 1}]: {reason}"
        )
        self._execute(task, employee)

    def _accept(self, task: Task, employee: Employee, result: RunResult) -> None:
        task.result = result.summary
        self.journal.append(JournalEntry(
            employee_id=employee.id,
            task_id=task.id,
            action="completed",
            summary=result.summary,
            evidence=result.evidence,
        ))
        self._change_state(task, "done", MANAGER_ID)

    def _change_state(self, task: Task, new_state: str, actor_id: str) -> None:
        old = task.state
        task.transition(new_state)
        self.journal.append(JournalEntry(
            employee_id=actor_id,
            task_id=task.id,
            action="state_change",
            summary=state_change_summary(old, new_state),
        ))

    def _employee_by_id(self, employee_id: str | None) -> Employee:
        for e in self.employees:
            if e.id == employee_id:
                return e
        raise RoutingError(f"no employee with id {employee_id!r}")

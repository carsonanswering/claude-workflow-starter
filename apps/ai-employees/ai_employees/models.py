"""Core dataclasses per docs/data-model.md. Plain data, JSON round-trippable."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .ids import new_ulid

MANAGER_ID = "manager"
OWNER_ID = "owner"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Company:
    name: str
    owner: str
    goals: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    resources: dict[str, str] = field(default_factory=dict)
    employees: list[str] = field(default_factory=list)
    id: str = field(default_factory=new_ulid)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Company":
        return cls(**d)


@dataclass
class Employee:
    name: str
    role: str
    job_description: str
    tools: list[str] = field(default_factory=list)
    approval_gates: list[str] = field(default_factory=list)
    status: str = "active"
    max_concurrent_tasks: int = 1
    id: str = field(default_factory=new_ulid)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Employee":
        return cls(**d)


TASK_STATES = {
    "queued",
    "assigned",
    "in_progress",
    "awaiting_approval",
    "review",
    "done",
    "failed",
    "cancelled",
}

TERMINAL_STATES = {"done", "failed", "cancelled"}

TRANSITIONS: dict[str, set[str]] = {
    "queued": {"assigned", "cancelled"},
    "assigned": {"in_progress", "queued"},
    "in_progress": {"awaiting_approval", "review", "failed"},
    "awaiting_approval": {"in_progress", "cancelled"},
    "review": {"done", "in_progress"},
    "done": set(),
    "failed": set(),
    "cancelled": set(),
}


class InvalidTransition(Exception):
    pass


@dataclass
class Task:
    title: str
    description: str
    assignee_role: str
    source: str = "owner"
    parent_id: str | None = None
    assignee_id: str | None = None
    state: str = "queued"
    priority: int = 2
    gate_tags: list[str] = field(default_factory=list)
    result: str | None = None
    id: str = field(default_factory=new_ulid)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def transition(self, new_state: str) -> None:
        if new_state not in TASK_STATES:
            raise InvalidTransition(f"unknown state {new_state!r}")
        if new_state not in TRANSITIONS[self.state]:
            raise InvalidTransition(
                f"task {self.id}: {self.state} -> {new_state} not allowed"
            )
        self.state = new_state
        self.updated_at = utc_now()

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        return cls(**d)


@dataclass
class JournalEntry:
    employee_id: str
    action: str
    summary: str
    task_id: str | None = None
    evidence: list[dict] = field(default_factory=list)
    id: str = field(default_factory=new_ulid)
    timestamp: str = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "JournalEntry":
        return cls(**d)


@dataclass
class StandupDigest:
    company_id: str
    period_start: str
    period_end: str
    per_employee: list[dict] = field(default_factory=list)
    pending_approvals: list[str] = field(default_factory=list)
    narrative: str = ""
    journal_entry_ids: list[str] = field(default_factory=list)
    id: str = field(default_factory=new_ulid)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "StandupDigest":
        return cls(**d)

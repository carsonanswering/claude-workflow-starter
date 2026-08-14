"""Outbox: the transport seam for `send_external`. An approved gated action
never leaves the employee agent's hands directly — the agent writes a
structured draft file into its workspace `outbox/`; the CLI queues that draft
here as an `OutboxItem`; a separate, explicit `flush-outbox` step is what
actually delivers it via a `Transport`. Dir-backed: one JSON file per item
under `<out_dir>/outbox/`, so the queue survives process restarts and is
inspectable on disk."""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Protocol

from .ids import new_ulid
from .journal import Journal
from .models import Employee, JournalEntry, Task, utc_now

OUTBOX_STATES = {"queued", "sent", "failed"}


@dataclass
class OutboxItem:
    task_id: str
    employee_id: str
    kind: str  # e.g. "email"
    payload: dict = field(default_factory=dict)  # e.g. {"to", "subject", "body"}
    status: str = "queued"
    id: str = field(default_factory=new_ulid)
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "employee_id": self.employee_id,
            "kind": self.kind,
            "payload": self.payload,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "OutboxItem":
        if not isinstance(d.get("payload"), dict):
            raise ValueError(
                f"OutboxItem.from_dict: 'payload' must be a dict, got "
                f"{type(d.get('payload')).__name__}"
            )
        known_fields = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in d.items() if k in known_fields}
        return cls(**filtered)


class Outbox:
    """Dir-backed queue: one JSON file per item under `<out_dir>/outbox/`."""

    def __init__(self, out_dir: str | Path) -> None:
        self.dir = Path(out_dir) / "outbox"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, item_id: str) -> Path:
        return self.dir / f"{item_id}.json"

    def add(self, item: OutboxItem) -> OutboxItem:
        self._path(item.id).write_text(json.dumps(item.to_dict(), indent=2))
        return item

    def update(self, item: OutboxItem) -> OutboxItem:
        self._path(item.id).write_text(json.dumps(item.to_dict(), indent=2))
        return item

    def get(self, item_id: str) -> OutboxItem | None:
        p = self._path(item_id)
        if not p.exists():
            return None
        return OutboxItem.from_dict(json.loads(p.read_text()))

    def list(self, status: str | None = None) -> list[OutboxItem]:
        items = [OutboxItem.from_dict(json.loads(p.read_text())) for p in sorted(self.dir.glob("*.json"))]
        if status is not None:
            items = [i for i in items if i.status == status]
        return items

    def flush(self, transport: "Transport", journal: Journal) -> tuple[list[OutboxItem], list[OutboxItem]]:
        """Deliver every `queued` item via `transport`. Marks each item
        sent/failed on disk and journals a `sent` or `send_failed` entry.
        Returns (sent, failed).

        Ordering is deliberate: an item is only marked "sent" AFTER
        `transport.send` succeeds — marking it first would fake success on a
        transport error. If the post-send `self.update()` itself raises
        (e.g. disk full), the send already happened and cannot be undone; we
        log/warn loudly with the item id so an operator knows a duplicate
        send is possible next flush, rather than silently losing that
        signal."""
        sent: list[OutboxItem] = []
        failed: list[OutboxItem] = []
        for item in self.list(status="queued"):
            try:
                transport.send(item)
            except Exception as e:
                item.status = "failed"
                self.update(item)
                journal.append(JournalEntry(
                    employee_id=item.employee_id,
                    task_id=item.task_id,
                    action="send_failed",
                    summary=f"delivery failed for {item.kind} [{item.id}]: {e}",
                ))
                failed.append(item)
                continue
            item.status = "sent"
            try:
                self.update(item)
            except Exception as e:
                warnings.warn(
                    f"item {item.id} delivered but not marked sent; "
                    f"next flush may resend ({e})"
                )
            journal.append(JournalEntry(
                employee_id=item.employee_id,
                task_id=item.task_id,
                action="sent",
                summary=f"delivered {item.kind} [{item.id}] via transport",
                evidence=[{
                    "kind": "message",
                    "ref": f"outbox://{item.id}",
                    "excerpt": json.dumps(item.payload)[:500],
                }],
            ))
            sent.append(item)
        return sent, failed


class Transport(Protocol):
    def send(self, item: OutboxItem) -> None:
        """Deliver `item`. Raise on failure — never return a status code."""
        ...


class MockTransport:
    """Records sends in memory. `fail_kinds` lets tests script a failure."""

    def __init__(self, fail_kinds: set[str] | None = None) -> None:
        self.fail_kinds = fail_kinds or set()
        self.sent: list[OutboxItem] = []

    def send(self, item: OutboxItem) -> None:
        if item.kind in self.fail_kinds:
            raise RuntimeError(f"MockTransport configured to fail kind {item.kind!r}")
        self.sent.append(item)


class FileTransport:
    """Appends delivered items to `sent.jsonl` — stand-in for a real SMTP/API
    transport later; makes "sends" auditable without any network access."""

    def __init__(self, out_dir: str | Path) -> None:
        self.path = Path(out_dir) / "sent.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def send(self, item: OutboxItem) -> None:
        with self.path.open("a") as f:
            f.write(json.dumps(item.to_dict()) + "\n")


def _slug(name: str) -> str:
    """Filesystem-safe slug matching claude_runner.slugify_employee_name,
    reimplemented locally so this module has no dependency on the
    optional-SDK-gated claude_runner module."""
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "employee"


def queue_workspace_outbox(
    tasks: dict[str, Task],
    employees: list[Employee],
    journal: Journal,
    workspace_root: str | Path,
    out_dir: str | Path,
) -> list[OutboxItem]:
    """Scan each `done` task's employee workspace for `outbox/*.json` files
    the agent wrote, persist them into the on-disk Outbox, journal an
    `outbox_queued` entry per item, and rename the source files so a later
    call (e.g. the next `run`) doesn't re-queue them."""
    workspace_root = Path(workspace_root)
    outbox = Outbox(out_dir)
    by_id = {e.id: e for e in employees}
    queued: list[OutboxItem] = []
    for task in tasks.values():
        if task.state != "done" or not task.assignee_id:
            continue
        employee = by_id.get(task.assignee_id)
        if employee is None:
            continue
        outbox_dir = workspace_root / _slug(employee.name) / "outbox"
        if not outbox_dir.exists():
            continue
        for p in sorted(outbox_dir.glob("*.json")):
            try:
                data = json.loads(p.read_text())
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict) or not isinstance(data.get("payload", {}), dict):
                warnings.warn(f"{p}: outbox file is not an object with a dict payload; skipped")
                continue
            # Rename FIRST — this is the idempotency barrier. Once claimed,
            # a re-run of this scan can never see this file again, so a
            # failure in outbox.add/journal below cannot cause a duplicate
            # queuing on retry (it can only drop the item, which is why we
            # warn loudly to let an operator recover it from the .queued
            # file).
            claimed = p.with_name(p.name + ".queued")
            p.rename(claimed)
            try:
                item = outbox.add(OutboxItem(
                    task_id=task.id,
                    employee_id=employee.id,
                    kind=data.get("kind", "unknown"),
                    payload=data.get("payload", {}),
                ))
                journal.append(JournalEntry(
                    employee_id=employee.id,
                    task_id=task.id,
                    action="outbox_queued",
                    summary=f"queued {item.kind} draft for delivery ({item.id})",
                    evidence=[{"kind": "file", "ref": str(claimed.relative_to(workspace_root)), "excerpt": None}],
                ))
            except Exception as e:
                warnings.warn(
                    f"outbox file claimed at {claimed} but failed to queue "
                    f"({e}); recover it manually"
                )
                continue
            queued.append(item)
    return queued

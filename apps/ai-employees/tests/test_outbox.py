"""Outbox transport seam: dir-backed queue, MockTransport/FileTransport
delivery, and the workspace-scan that queues drafts an employee agent wrote."""

import json
import warnings
from pathlib import Path

import pytest

from ai_employees.journal import Journal
from ai_employees.models import Employee, Task
from ai_employees.outbox import (
    FileTransport,
    MockTransport,
    Outbox,
    OutboxItem,
    queue_workspace_outbox,
)


def test_from_dict_ignores_unknown_extra_fields():
    d = {
        "id": "x1", "task_id": "t1", "employee_id": "e1", "kind": "email",
        "payload": {"body": "hi"}, "status": "queued", "created_at": "now",
        "some_future_field": "ignored",
    }
    item = OutboxItem.from_dict(d)
    assert item.id == "x1"
    assert item.payload == {"body": "hi"}


def test_from_dict_requires_dict_payload():
    with pytest.raises(ValueError, match="payload"):
        OutboxItem.from_dict({"task_id": "t1", "employee_id": "e1", "kind": "email", "payload": "not a dict"})


def test_outbox_round_trip(tmp_path):
    outbox = Outbox(tmp_path)
    item = outbox.add(OutboxItem(
        task_id="t1", employee_id="e1", kind="email",
        payload={"to": "a@b.com", "subject": "hi", "body": "hello"},
    ))

    assert (tmp_path / "outbox" / f"{item.id}.json").exists()
    fetched = outbox.get(item.id)
    assert fetched == item
    assert outbox.list() == [item]
    assert outbox.list(status="queued") == [item]
    assert outbox.list(status="sent") == []


def test_flush_marks_sent_and_journals(tmp_path):
    outbox = Outbox(tmp_path)
    item = outbox.add(OutboxItem(task_id="t1", employee_id="e1", kind="email", payload={"body": "x"}))
    journal = Journal(tmp_path / "journal.jsonl")
    transport = MockTransport()

    sent, failed = outbox.flush(transport, journal)

    assert [i.id for i in sent] == [item.id]
    assert failed == []
    assert [i.id for i in transport.sent] == [item.id]
    assert outbox.get(item.id).status == "sent"
    entries = journal.read()
    assert any(e.action == "sent" and e.task_id == "t1" for e in entries)
    # a second flush finds nothing left queued
    sent2, failed2 = outbox.flush(transport, journal)
    assert sent2 == [] and failed2 == []


def test_flush_with_failing_transport_marks_failed(tmp_path):
    outbox = Outbox(tmp_path)
    item = outbox.add(OutboxItem(task_id="t1", employee_id="e1", kind="email", payload={"body": "x"}))
    journal = Journal(tmp_path / "journal.jsonl")
    transport = MockTransport(fail_kinds={"email"})

    sent, failed = outbox.flush(transport, journal)

    assert sent == []
    assert [i.id for i in failed] == [item.id]
    assert outbox.get(item.id).status == "failed"
    entries = journal.read()
    assert any(e.action == "send_failed" and e.task_id == "t1" for e in entries)


def test_flush_warns_loudly_if_update_after_send_fails(tmp_path, monkeypatch):
    outbox = Outbox(tmp_path)
    item = outbox.add(OutboxItem(task_id="t1", employee_id="e1", kind="email", payload={"body": "x"}))
    journal = Journal(tmp_path / "journal.jsonl")
    transport = MockTransport()

    def failing_update(self, it):
        raise OSError("disk full")

    monkeypatch.setattr(Outbox, "update", failing_update)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        sent, failed = outbox.flush(transport, journal)

    # the send itself still happened and is reported as sent
    assert [i.id for i in sent] == [item.id]
    assert [i.id for i in transport.sent] == [item.id]
    assert any(item.id in str(w.message) and "resend" in str(w.message) for w in caught)


def test_file_transport_appends_sent_jsonl(tmp_path):
    transport = FileTransport(tmp_path)
    item = OutboxItem(task_id="t1", employee_id="e1", kind="email", payload={"body": "x"})

    transport.send(item)

    lines = (tmp_path / "sent.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["id"] == item.id


def test_queue_workspace_outbox_collects_and_journals(tmp_path):
    employee = Employee(name="Mktr 1", role="marketer", job_description="draft copy")
    task = Task(title="Send announcement", description="...", assignee_role="marketer")
    task.assignee_id = employee.id
    task.state = "done"  # bypass the state machine; only .state is read here
    tasks = {task.id: task}

    workspace_root = tmp_path / "workspace"
    outbox_dir = workspace_root / "mktr-1" / "outbox"
    outbox_dir.mkdir(parents=True)
    draft = {"kind": "email", "payload": {"to": "list@toyco.example.com", "subject": "Hi", "body": "..."}}
    (outbox_dir / "item1.json").write_text(json.dumps(draft))

    out_dir = tmp_path / "run"
    journal = Journal(out_dir / "journal.jsonl")

    queued = queue_workspace_outbox(tasks, [employee], journal, workspace_root, out_dir)

    assert len(queued) == 1
    item = queued[0]
    assert item.kind == "email"
    assert item.payload == draft["payload"]
    assert item.task_id == task.id
    assert item.employee_id == employee.id
    assert Outbox(out_dir).get(item.id) == item

    entries = journal.read()
    assert any(e.action == "outbox_queued" and e.task_id == task.id for e in entries)

    # the source file was renamed so a second scan doesn't re-queue it
    assert not (outbox_dir / "item1.json").exists()
    assert (outbox_dir / "item1.json.queued").exists()
    queued_again = queue_workspace_outbox(tasks, [employee], journal, workspace_root, out_dir)
    assert queued_again == []


def test_queue_workspace_outbox_claims_file_before_add_to_avoid_duplicate_queue(tmp_path, monkeypatch):
    """If Outbox.add/journal fails AFTER the source file is claimed (renamed),
    the item is dropped (not queued) but the source file must already be
    claimed — so a re-run never re-queues it and duplicates it. A loud
    warning is the recovery signal."""
    from ai_employees import outbox as outbox_module

    employee = Employee(name="Mktr 1", role="marketer", job_description="draft copy")
    task = Task(title="Send announcement", description="...", assignee_role="marketer")
    task.assignee_id = employee.id
    task.state = "done"
    tasks = {task.id: task}

    workspace_root = tmp_path / "workspace"
    outbox_dir = workspace_root / "mktr-1" / "outbox"
    outbox_dir.mkdir(parents=True)
    draft = {"kind": "email", "payload": {"to": "a@b.com", "subject": "Hi", "body": "..."}}
    (outbox_dir / "item1.json").write_text(json.dumps(draft))

    out_dir = tmp_path / "run"
    journal = Journal(out_dir / "journal.jsonl")

    def failing_add(self, item):
        raise OSError("disk full")

    monkeypatch.setattr(outbox_module.Outbox, "add", failing_add)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        queued = queue_workspace_outbox(tasks, [employee], journal, workspace_root, out_dir)

    assert queued == []
    # the source file was claimed (renamed) despite the downstream failure
    assert not (outbox_dir / "item1.json").exists()
    assert (outbox_dir / "item1.json.queued").exists()
    assert any("failed to queue" in str(w.message) for w in caught)


def test_queue_workspace_outbox_skips_non_done_tasks(tmp_path):
    employee = Employee(name="Mktr 1", role="marketer", job_description="draft copy")
    task = Task(title="Send announcement", description="...", assignee_role="marketer")
    task.assignee_id = employee.id
    task.state = "in_progress"
    tasks = {task.id: task}

    workspace_root = tmp_path / "workspace"
    outbox_dir = workspace_root / "mktr-1" / "outbox"
    outbox_dir.mkdir(parents=True)
    (outbox_dir / "item1.json").write_text(json.dumps({"kind": "email", "payload": {}}))

    journal = Journal(tmp_path / "run" / "journal.jsonl")
    queued = queue_workspace_outbox(tasks, [employee], journal, workspace_root, tmp_path / "run")

    assert queued == []

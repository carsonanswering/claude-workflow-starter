import json

from ai_employees import Journal, JournalEntry, derive_task_state


def test_append_and_read_roundtrip(tmp_path):
    j = Journal(tmp_path / "j.jsonl")
    e1 = j.append(JournalEntry(employee_id="e1", action="claimed", summary="s1", task_id="t1"))
    e2 = j.append(JournalEntry(
        employee_id="e1", action="completed", summary="s2", task_id="t1",
        evidence=[{"kind": "file", "ref": "/tmp/x", "excerpt": None}],
    ))
    entries = j.read()
    assert [e.id for e in entries] == [e1.id, e2.id]
    assert entries[1].evidence == [{"kind": "file", "ref": "/tmp/x", "excerpt": None}]


def test_append_only_one_json_object_per_line(tmp_path):
    path = tmp_path / "j.jsonl"
    j = Journal(path)
    for i in range(3):
        j.append(JournalEntry(employee_id="e", action="decision", summary=f"s{i}"))
    lines = path.read_text().strip().split("\n")
    assert len(lines) == 3
    assert all(json.loads(line)["employee_id"] == "e" for line in lines)


def test_read_missing_file(tmp_path):
    assert Journal(tmp_path / "nope.jsonl").read() == []


def test_for_task_filters(tmp_path):
    j = Journal(tmp_path / "j.jsonl")
    j.append(JournalEntry(employee_id="e", action="claimed", summary="a", task_id="t1"))
    j.append(JournalEntry(employee_id="e", action="claimed", summary="b", task_id="t2"))
    assert [e.task_id for e in j.for_task("t1")] == ["t1"]


def test_derive_task_state(tmp_path):
    j = Journal(tmp_path / "j.jsonl")
    for old, new in [("queued", "assigned"), ("assigned", "in_progress")]:
        j.append(JournalEntry(
            employee_id="manager", action="state_change",
            summary=f"{old} -> {new}", task_id="t1",
        ))
    entries = j.read()
    assert derive_task_state(entries, "t1") == "in_progress"
    assert derive_task_state(entries, "t2") is None


def test_ulid_ids_sort_chronologically(tmp_path):
    j = Journal(tmp_path / "j.jsonl")
    ids = [
        j.append(JournalEntry(employee_id="e", action="decision", summary=str(i))).id
        for i in range(5)
    ]
    assert ids == sorted(ids)

from ai_employees import Task, generate_digest


def make_task(role, **kw):
    return Task(title=f"task for {role}", description="d", assignee_role=role, **kw)


def run_toyco_day(manager):
    eng_task = make_task("engineer")
    gated = make_task("marketer", gate_tags=["send_external"])
    manager.submit(eng_task)
    manager.submit(gated)
    manager.run_once()
    manager.run_once()
    return eng_task, gated


def digest_for(manager):
    entries = manager.journal.read()
    return generate_digest(
        manager.company, manager.employees, manager.tasks, entries,
        period_start=min(e.timestamp for e in entries),
        period_end=max(e.timestamp for e in entries),
    ), entries


def test_buckets_and_pending_approvals(manager):
    eng_task, gated = run_toyco_day(manager)
    digest, _ = digest_for(manager)
    eng = next(e for e in manager.employees if e.role == "engineer")
    mktr = next(e for e in manager.employees if e.role == "marketer")
    per = {row["employee_id"]: row for row in digest.per_employee}
    assert per[eng.id]["done"] == [eng_task.id]
    assert per[eng.id]["blocked"] == []
    assert per[mktr.id]["blocked"] == [gated.id]
    assert digest.pending_approvals == [gated.id]


def test_narrative_cites_real_journal_ids(manager):
    run_toyco_day(manager)
    digest, entries = digest_for(manager)
    known = {e.id for e in entries}
    cited = [
        chunk.split("]")[0]
        for chunk in digest.narrative.split("[journal:")[1:]
    ]
    assert cited
    assert all(c in known for c in cited)
    assert set(digest.journal_entry_ids) <= known


def test_pending_empty_after_approval(manager):
    _, gated = run_toyco_day(manager)
    manager.approve(gated.id)
    digest, _ = digest_for(manager)
    assert digest.pending_approvals == []
    mktr = next(e for e in manager.employees if e.role == "marketer")
    per = {row["employee_id"]: row for row in digest.per_employee}
    assert gated.id in per[mktr.id]["done"]


def test_window_filters_entries(manager):
    _, gated = run_toyco_day(manager)
    manager.approve(gated.id)
    entries = manager.journal.read()
    digest = generate_digest(
        manager.company, manager.employees, manager.tasks, entries,
        period_start="2099-01-01T00:00:00+00:00",
        period_end="2099-01-02T00:00:00+00:00",
    )
    assert digest.journal_entry_ids == []
    assert digest.narrative == "No notable activity in this window."

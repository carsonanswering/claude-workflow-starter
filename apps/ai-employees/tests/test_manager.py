import pytest

from ai_employees import (
    Journal,
    Manager,
    MockRunner,
    RoutingError,
    RunResult,
    Task,
    TaskQueue,
    derive_task_state,
)


def make_task(role="engineer", **kw):
    return Task(title=f"task for {role}", description="d", assignee_role=role, **kw)


def test_routes_by_role(manager):
    eng_task = make_task("engineer")
    mktr_task = make_task("marketer")
    manager.submit(eng_task)
    manager.submit(mktr_task)
    manager.run_once()
    manager.run_once()
    eng = next(e for e in manager.employees if e.role == "engineer")
    mktr = next(e for e in manager.employees if e.role == "marketer")
    assert eng_task.assignee_id == eng.id
    assert mktr_task.assignee_id == mktr.id


def test_no_employee_for_role(manager):
    manager.submit(make_task("astronaut"))
    with pytest.raises(RoutingError, match="astronaut"):
        manager.run_once()


def test_priority_order(manager):
    low = make_task("engineer", priority=3)
    urgent = make_task("engineer", priority=0)
    manager.submit(low)
    manager.submit(urgent)
    assert manager.run_once() is urgent
    assert manager.run_once() is low


def test_ungated_task_reaches_done(manager):
    t = make_task("engineer")
    manager.submit(t)
    manager.run_once()
    assert t.state == "done"
    assert t.result
    states = [
        e.summary for e in manager.journal.for_task(t.id) if e.action == "state_change"
    ]
    assert states == [
        "queued -> assigned",
        "assigned -> in_progress",
        "in_progress -> review",
        "review -> done",
    ]


def test_gated_task_pauses(manager):
    t = make_task("marketer", gate_tags=["send_external"])
    manager.submit(t)
    manager.run_once()
    assert t.state == "awaiting_approval"
    assert t.id in manager.pending_gate_context
    escalations = [
        e for e in manager.journal.for_task(t.id) if e.action == "escalated"
    ]
    assert len(escalations) == 1
    assert escalations[0].evidence[0]["ref"] == "gate://send_external"


def test_gate_not_triggered_for_other_role(manager):
    t = make_task("engineer", gate_tags=["send_external"])
    manager.submit(t)
    manager.run_once()
    assert t.state == "done"


def test_approve_resumes_to_done(manager):
    t = make_task("marketer", gate_tags=["send_external"])
    manager.submit(t)
    manager.run_once()
    manager.approve(t.id)
    assert t.state == "done"
    actions = [e.action for e in manager.journal.for_task(t.id)]
    assert "approved" in actions
    assert "completed" in actions


def test_reject_cancels(manager):
    t = make_task("marketer", gate_tags=["send_external"])
    manager.submit(t)
    manager.run_once()
    manager.reject(t.id)
    assert t.state == "cancelled"
    assert "rejected" in [e.action for e in manager.journal.for_task(t.id)]
    assert t.id not in manager.pending_gate_context


def test_failed_run(toyco, tmp_path):
    company, employees = toyco
    t = make_task("engineer")
    manager = Manager(
        company, employees, TaskQueue(),
        Journal(tmp_path / "j.jsonl"),
        MockRunner(fail_task_ids={t.id}),
    )
    manager.submit(t)
    manager.run_once()
    assert t.state == "failed"


def test_run_once_empty_queue(manager):
    assert manager.run_once() is None


def test_journal_derives_task_state(manager):
    t = make_task("marketer", gate_tags=["send_external"])
    manager.submit(t)
    manager.run_once()
    entries = manager.journal.read()
    assert derive_task_state(entries, t.id) == t.state == "awaiting_approval"
    manager.approve(t.id)
    assert derive_task_state(manager.journal.read(), t.id) == t.state == "done"


def test_done_task_has_evidence(manager):
    t = make_task("engineer")
    manager.submit(t)
    manager.run_once()
    completed = [
        e for e in manager.journal.for_task(t.id) if e.action == "completed"
    ]
    assert completed and completed[0].evidence


def test_default_review_policy_unchanged_behavior(manager):
    """No review_policy passed -> accept-all, identical to pre-existing behavior."""
    t = make_task("engineer")
    manager.submit(t)
    manager.run_once()
    assert t.state == "done"
    assert not [e for e in manager.journal.for_task(t.id) if e.action == "sent_back"]


def test_send_back_retry_succeeds_second_round(toyco, tmp_path):
    company, employees = toyco
    t = make_task("engineer")

    runner = MockRunner(scripted_results={t.id: [
        RunResult(status="completed", summary="draft v1 (incomplete)", evidence=[]),
        RunResult(status="completed", summary="draft v2 (fixed)", evidence=[
            {"kind": "message", "ref": "mock://v2", "excerpt": "revised"}
        ]),
    ]})

    def policy(task, result):
        return "please address the missing section" if "v1" in result.summary else None

    manager = Manager(
        company, employees, TaskQueue(),
        Journal(tmp_path / "j.jsonl"),
        runner,
        review_policy=policy,
    )
    manager.submit(t)
    manager.run_once()

    assert t.state == "done"
    assert t.result == "draft v2 (fixed)"
    assert len(runner.calls) == 2
    assert "please address the missing section" in t.description

    entries = manager.journal.for_task(t.id)
    sent_back = [e for e in entries if e.action == "sent_back"]
    assert len(sent_back) == 1
    assert "please address the missing section" in sent_back[0].summary
    states = [e.summary for e in entries if e.action == "state_change"]
    assert states == [
        "queued -> assigned",
        "assigned -> in_progress",
        "in_progress -> review",
        "review -> in_progress",
        "in_progress -> review",
        "review -> done",
    ]


def test_send_back_retry_cap_exhausts_to_failed(toyco, tmp_path):
    company, employees = toyco
    t = make_task("engineer")

    manager = Manager(
        company, employees, TaskQueue(),
        Journal(tmp_path / "j.jsonl"),
        MockRunner(),
        review_policy=lambda task, result: "still not good enough",
        max_review_rounds=2,
    )
    manager.submit(t)
    manager.run_once()

    assert t.state == "failed"
    assert "still not good enough" in t.result
    assert len(manager.runner.calls) == 3  # initial + 2 retries, then cap hit

    entries = manager.journal.for_task(t.id)
    sent_back = [e for e in entries if e.action == "sent_back"]
    assert len(sent_back) == 3
    states = [e.summary for e in entries if e.action == "state_change"]
    assert states == [
        "queued -> assigned",
        "assigned -> in_progress",
        "in_progress -> review",
        "review -> in_progress",
        "in_progress -> review",
        "review -> in_progress",
        "in_progress -> review",
        "review -> in_progress",
        "in_progress -> failed",
    ]

import pytest

from ai_employees import InvalidTransition, Task


def make_task(**kw):
    return Task(title="t", description="d", assignee_role="engineer", **kw)


def test_happy_path():
    t = make_task()
    for s in ("assigned", "in_progress", "review", "done"):
        t.transition(s)
    assert t.state == "done"


def test_gate_pause_and_resume():
    t = make_task()
    t.transition("assigned")
    t.transition("in_progress")
    t.transition("awaiting_approval")
    t.transition("in_progress")
    assert t.state == "in_progress"


def test_gate_reject():
    t = make_task(state="awaiting_approval")
    t.transition("cancelled")
    assert t.state == "cancelled"


def test_review_send_back():
    t = make_task(state="review")
    t.transition("in_progress")
    assert t.state == "in_progress"


def test_requeue_from_assigned():
    t = make_task(state="assigned")
    t.transition("queued")
    assert t.state == "queued"


def test_invalid_skip():
    t = make_task()
    with pytest.raises(InvalidTransition):
        t.transition("done")


def test_terminal_is_terminal():
    for terminal in ("done", "failed", "cancelled"):
        t = make_task(state=terminal)
        with pytest.raises(InvalidTransition):
            t.transition("in_progress")


def test_unknown_state():
    t = make_task()
    with pytest.raises(InvalidTransition):
        t.transition("napping")


def test_transition_touches_updated_at():
    t = make_task()
    before = t.updated_at
    t.transition("assigned")
    assert t.updated_at >= before

"""LLMPlanner: JSON parse/validation of the SDK's decomposition output, and
StaticPlanner as a passthrough. No network/API calls — the SDK query call is
stubbed via monkeypatching LLMPlanner._query, same pattern as test_reviewer.py."""

import warnings

import pytest

pytest.importorskip("claude_agent_sdk")

from ai_employees.models import Company, Employee, Task
from ai_employees.planner import (
    LLMPlanner,
    PlanningError,
    StaticPlanner,
    build_planner_prompt,
)


def make_company() -> Company:
    return Company(
        name="toyco",
        owner="carson@example.com",
        goals=["Launch a landing page", "Send an announcement email"],
        constraints=["Spend $0"],
    )


def make_employees() -> list[Employee]:
    return [
        Employee(name="Eng-1", role="engineer", job_description="build", approval_gates=["deploy_prod"]),
        Employee(name="Mktr-1", role="marketer", job_description="write", approval_gates=["send_external"]),
    ]


def test_build_planner_prompt_contains_goals_roles_and_gates():
    prompt = build_planner_prompt(make_company(), make_employees())

    assert "Launch a landing page" in prompt
    assert "Spend $0" in prompt
    assert "engineer" in prompt and "marketer" in prompt
    assert "deploy_prod" in prompt and "send_external" in prompt


def test_static_planner_returns_wrapped_tasks():
    tasks = [Task(title="t1", description="d1", assignee_role="engineer")]
    planner = StaticPlanner(tasks)

    result = planner(make_company(), make_employees())

    assert result == tasks
    assert result is not tasks  # defensive copy


def test_llm_planner_parses_valid_json_array(monkeypatch):
    planner = LLMPlanner()
    text = (
        '[{"title": "Build page", "description": "landing page", '
        '"assignee_role": "engineer", "priority": 1, "gate_tags": []},'
        '{"title": "Draft email", "description": "announcement", '
        '"assignee_role": "marketer", "priority": 2, "gate_tags": ["send_external"]}]'
    )
    monkeypatch.setattr(planner, "_query", lambda system_prompt, prompt: (text, True))

    tasks = planner(make_company(), make_employees())

    assert len(tasks) == 2
    assert {t.assignee_role for t in tasks} == {"engineer", "marketer"}
    gated = next(t for t in tasks if t.assignee_role == "marketer")
    assert gated.gate_tags == ["send_external"]
    assert gated.priority == 2


def test_llm_planner_drops_unknown_role_and_warns(monkeypatch):
    planner = LLMPlanner()
    text = (
        '[{"title": "Build page", "description": "landing page", '
        '"assignee_role": "engineer", "priority": 1, "gate_tags": []},'
        '{"title": "File taxes", "description": "quarterly filing", '
        '"assignee_role": "accountant", "priority": 1, "gate_tags": []}]'
    )
    monkeypatch.setattr(planner, "_query", lambda system_prompt, prompt: (text, True))

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        tasks = planner(make_company(), make_employees())

    assert len(tasks) == 1
    assert tasks[0].assignee_role == "engineer"
    assert any("unknown assignee_role" in str(w.message) for w in caught)


def test_llm_planner_drops_task_with_string_gate_tags_and_warns(monkeypatch):
    planner = LLMPlanner()
    text = (
        '[{"title": "Build page", "description": "landing page", '
        '"assignee_role": "engineer", "priority": 1, "gate_tags": []},'
        '{"title": "Draft email", "description": "announcement", '
        '"assignee_role": "marketer", "priority": 1, "gate_tags": "send_external"}]'
    )
    monkeypatch.setattr(planner, "_query", lambda system_prompt, prompt: (text, True))

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        tasks = planner(make_company(), make_employees())

    assert len(tasks) == 1
    assert tasks[0].assignee_role == "engineer"
    assert any("gate_tags" in str(w.message) for w in caught)


def test_llm_planner_drops_task_with_non_string_gate_tag_entries(monkeypatch):
    planner = LLMPlanner()
    text = (
        '[{"title": "Build page", "description": "landing page", '
        '"assignee_role": "engineer", "priority": 1, "gate_tags": []},'
        '{"title": "Draft email", "description": "announcement", '
        '"assignee_role": "marketer", "priority": 1, "gate_tags": [1, 2]}]'
    )
    monkeypatch.setattr(planner, "_query", lambda system_prompt, prompt: (text, True))

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        tasks = planner(make_company(), make_employees())

    assert len(tasks) == 1
    assert tasks[0].assignee_role == "engineer"
    assert any("gate_tags" in str(w.message) for w in caught)


def test_llm_planner_drops_task_with_out_of_range_priority(monkeypatch):
    planner = LLMPlanner()
    text = (
        '[{"title": "Build page", "description": "landing page", '
        '"assignee_role": "engineer", "priority": 1, "gate_tags": []},'
        '{"title": "Draft email", "description": "announcement", '
        '"assignee_role": "marketer", "priority": 5, "gate_tags": []}]'
    )
    monkeypatch.setattr(planner, "_query", lambda system_prompt, prompt: (text, True))

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        tasks = planner(make_company(), make_employees())

    assert len(tasks) == 1
    assert tasks[0].assignee_role == "engineer"
    assert any("priority" in str(w.message) for w in caught)


def test_llm_planner_drops_task_with_non_int_priority(monkeypatch):
    planner = LLMPlanner()
    text = (
        '[{"title": "Build page", "description": "landing page", '
        '"assignee_role": "engineer", "priority": 1, "gate_tags": []},'
        '{"title": "Draft email", "description": "announcement", '
        '"assignee_role": "marketer", "priority": "high", "gate_tags": []}]'
    )
    monkeypatch.setattr(planner, "_query", lambda system_prompt, prompt: (text, True))

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        tasks = planner(make_company(), make_employees())

    assert len(tasks) == 1
    assert tasks[0].assignee_role == "engineer"
    assert any("priority" in str(w.message) for w in caught)


def test_llm_planner_malformed_json_raises_planning_error(monkeypatch):
    planner = LLMPlanner()
    monkeypatch.setattr(planner, "_query", lambda system_prompt, prompt: ("not json at all", True))

    with pytest.raises(PlanningError):
        planner(make_company(), make_employees())


def test_llm_planner_all_invalid_raises_planning_error(monkeypatch):
    planner = LLMPlanner()
    text = '[{"title": "File taxes", "description": "x", "assignee_role": "accountant"}]'
    monkeypatch.setattr(planner, "_query", lambda system_prompt, prompt: (text, True))

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        with pytest.raises(PlanningError):
            planner(make_company(), make_employees())


def test_llm_planner_query_failure_raises_planning_error(monkeypatch):
    planner = LLMPlanner()
    monkeypatch.setattr(planner, "_query", lambda system_prompt, prompt: ("RuntimeError: boom", False))

    with pytest.raises(PlanningError):
        planner(make_company(), make_employees())


def test_import_guard_raises_without_sdk(monkeypatch):
    import ai_employees.planner as planner_module

    monkeypatch.setattr(planner_module, "HAS_SDK", False)

    with pytest.raises(RuntimeError, match="claude-agent-sdk"):
        planner_module.LLMPlanner()

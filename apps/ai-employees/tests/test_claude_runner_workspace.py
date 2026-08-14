"""Employee workspace isolation for ClaudeAgentRunner: per-employee cwd under
a workspace_root, and file evidence captured from files created/modified
during a run. No network/API calls — exercises the pure helpers directly and
monkeypatches ClaudeAgentRunner._query to avoid touching the SDK transport."""

import asyncio
import json
import time
import warnings
from pathlib import Path

import pytest

pytest.importorskip("claude_agent_sdk")

from ai_employees import claude_runner as claude_runner_module
from ai_employees.claude_runner import (
    ClaudeAgentRunner,
    collect_outbox_items,
    scan_new_or_changed_files,
    slugify_employee_name,
    snapshot_workspace,
)
from ai_employees.config import load_company

EXAMPLE = Path(__file__).parent.parent / "examples" / "toyco.yaml"


def test_slugify_employee_name():
    assert slugify_employee_name("Eng-1") == "eng-1"
    assert slugify_employee_name("Mktr 1 (lead)") == "mktr-1-lead"
    assert slugify_employee_name("  ") == "employee"


def test_employee_workspace_created_on_demand(tmp_path):
    company, employees = load_company(EXAMPLE)
    employee = employees[0]
    runner = ClaudeAgentRunner(workspace_root=tmp_path / "workspace")

    ws = runner.employee_workspace(employee)

    assert ws == tmp_path / "workspace" / slugify_employee_name(employee.name)
    assert ws.is_dir()


def test_employee_workspace_none_without_workspace_root():
    runner = ClaudeAgentRunner(cwd="/tmp")
    company, employees = load_company(EXAMPLE)
    assert runner.employee_workspace(employees[0]) is None


def test_snapshot_and_scan_detect_new_files(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "existing.txt").write_text("before")

    before = snapshot_workspace(ws)

    # simulate a run: touch the existing file and add a new one, in a subdir too
    time.sleep(0.01)
    (ws / "existing.txt").write_text("after")
    (ws / "sub").mkdir()
    (ws / "sub" / "new.txt").write_text("new")

    evidence = scan_new_or_changed_files(ws, before)
    refs = {e["ref"] for e in evidence}

    assert refs == {"existing.txt", str(Path("sub") / "new.txt")}
    assert all(e["kind"] == "file" for e in evidence)


def test_scan_ignores_untouched_files(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "untouched.txt").write_text("stays")

    before = snapshot_workspace(ws)
    evidence = scan_new_or_changed_files(ws, before)

    assert evidence == []


def test_scan_on_missing_workspace_is_empty(tmp_path):
    assert snapshot_workspace(tmp_path / "nope") == {}
    assert scan_new_or_changed_files(tmp_path / "nope", {}) == []


def test_collect_outbox_items_skips_non_dict_json_with_warning(tmp_path):
    outbox_dir = tmp_path / "outbox"
    outbox_dir.mkdir()
    (outbox_dir / "good.json").write_text(json.dumps({"kind": "email", "payload": {"body": "x"}}))
    (outbox_dir / "bad_list.json").write_text(json.dumps(["not", "a", "dict"]))

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        items = collect_outbox_items(tmp_path)

    assert items == [{"kind": "email", "payload": {"body": "x"}}]
    assert any("not a JSON object" in str(w.message) for w in caught)


def test_collect_outbox_items_skips_non_dict_payload_with_warning(tmp_path):
    outbox_dir = tmp_path / "outbox"
    outbox_dir.mkdir()
    (outbox_dir / "good.json").write_text(json.dumps({"kind": "email", "payload": {"body": "x"}}))
    (outbox_dir / "bad_payload.json").write_text(json.dumps({"kind": "email", "payload": "not a dict"}))

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        items = collect_outbox_items(tmp_path)

    assert items == [{"kind": "email", "payload": {"body": "x"}}]
    assert any("non-object 'payload'" in str(w.message) for w in caught)


def test_run_appends_file_evidence_from_workspace(tmp_path, monkeypatch):
    """Exercise the full run() path with the SDK query mocked out: a fake
    _query writes a file into the employee's workspace (as a real tool call
    would) and returns success; run() must pick it up as evidence."""
    company, employees = load_company(EXAMPLE)
    from ai_employees.config import load_tasks

    tasks = load_tasks(EXAMPLE)
    task = next(t for t in tasks if not t.gate_tags)
    employee = next(e for e in employees if e.role == task.assignee_role)

    runner = ClaudeAgentRunner(workspace_root=tmp_path / "workspace")

    def fake_query(system_prompt, prompt, tools, cwd):
        assert cwd == runner.employee_workspace(employee)
        (Path(cwd) / "output.md").write_text("agent wrote this")
        return "done", True

    monkeypatch.setattr(runner, "_query", fake_query)

    result = runner.run(employee, task, company)

    assert result.status == "completed"
    file_evidence = [e for e in result.evidence if e["kind"] == "file"]
    assert file_evidence == [{"kind": "file", "ref": "output.md"}]


def test_run_collects_outbox_items_from_workspace(tmp_path, monkeypatch):
    """A gated marketer task, approved: the fake _query writes a draft into
    outbox/ (as a real agent instructed by _execute_prompt would) instead of
    "sending" it. run() must surface it as RunResult.outbox_items, untouched
    (never delivered) — delivery is a separate, explicit step."""
    company, employees = load_company(EXAMPLE)
    from ai_employees.config import load_tasks

    tasks = load_tasks(EXAMPLE)
    task = next(t for t in tasks if t.gate_tags)
    employee = next(e for e in employees if e.role == task.assignee_role)
    approved_gates = frozenset(task.gate_tags)

    runner = ClaudeAgentRunner(workspace_root=tmp_path / "workspace")
    draft = {"kind": "email", "payload": {"to": "list@toyco.example.com", "subject": "Hi", "body": "..."}}

    def fake_query(system_prompt, prompt, tools, cwd):
        outbox_dir = Path(cwd) / "outbox"
        outbox_dir.mkdir(parents=True, exist_ok=True)
        (outbox_dir / "draft1.json").write_text(json.dumps(draft))
        return "wrote the draft to outbox/", True

    monkeypatch.setattr(runner, "_query", fake_query)

    result = runner.run(employee, task, company, approved_gates=approved_gates)

    assert result.status == "completed"
    assert result.outbox_items == [draft]


def test_query_timeout_returns_failed_not_hang(monkeypatch):
    """A stuck SDK stream must not hang the whole run: _query wraps it in
    asyncio.wait_for and surfaces a failed (text, False) result quickly."""

    async def slow_query(*, prompt, options):
        await asyncio.sleep(5)
        if False:  # pragma: no cover - keeps this an async generator
            yield

    monkeypatch.setattr(claude_runner_module, "query", slow_query)
    runner = ClaudeAgentRunner(task_timeout_s=0.05)

    start = time.monotonic()
    text, ok = runner._query("sys", "prompt", [], None)
    elapsed = time.monotonic() - start

    assert ok is False
    assert "timed out after 0.05s" in text
    assert elapsed < 4  # bounded by the timeout, not the 5s sleep


def test_query_timeout_zero_disables_timeout(monkeypatch):
    """task_timeout_s=0 must fall back to no timeout at all — a slow-ish
    query still completes successfully instead of being cut off."""
    from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

    async def slow_but_finite_query(*, prompt, options):
        await asyncio.sleep(0.1)
        yield AssistantMessage(content=[TextBlock(text="done")], model="test-model")
        yield ResultMessage(
            subtype="success",
            duration_ms=100,
            duration_api_ms=100,
            is_error=False,
            num_turns=1,
            session_id="s",
            result="done",
        )

    monkeypatch.setattr(claude_runner_module, "query", slow_but_finite_query)
    runner = ClaudeAgentRunner(task_timeout_s=0)

    text, ok = runner._query("sys", "prompt", [], None)

    assert ok is True
    assert text == "done"


def test_query_timeout_none_disables_timeout(monkeypatch):
    """task_timeout_s=None must also mean no timeout (explicit opt-out)."""
    from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

    async def fast_query(*, prompt, options):
        yield AssistantMessage(content=[TextBlock(text="ok")], model="test-model")
        yield ResultMessage(
            subtype="success",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="s",
            result="ok",
        )

    monkeypatch.setattr(claude_runner_module, "query", fast_query)
    runner = ClaudeAgentRunner(task_timeout_s=None)

    text, ok = runner._query("sys", "prompt", [], None)

    assert ok is True
    assert text == "ok"

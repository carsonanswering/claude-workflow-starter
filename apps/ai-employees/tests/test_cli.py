import argparse
import json
from pathlib import Path

import pytest

from ai_employees import cli as cli_module
from ai_employees.cli import _make_runner, build_parser, cmd_run, main
from ai_employees.config import load_tasks
from ai_employees.journal import Journal
from ai_employees.models import Task

EXAMPLE = Path(__file__).parent.parent / "examples" / "toyco.yaml"


def run_cli(tmp_path, argv_extra=(), answers=("y",)):
    it = iter(answers)
    prompts = []

    def fake_input(prompt):
        prompts.append(prompt)
        return next(it)

    code = main(
        ["run", str(EXAMPLE), "--mock", "--out-dir", str(tmp_path), *argv_extra],
        input_fn=fake_input,
    )
    return code, prompts


def load_run(tmp_path):
    tasks = [Task.from_dict(d) for d in json.loads((tmp_path / "tasks.json").read_text())]
    entries = Journal(tmp_path / "journal.jsonl").read()
    return {t.title: t for t in tasks}, entries


def test_load_tasks_from_example():
    tasks = load_tasks(EXAMPLE)
    assert len(tasks) == 2
    roles = {t.assignee_role for t in tasks}
    assert roles == {"engineer", "marketer"}
    gated = next(t for t in tasks if t.assignee_role == "marketer")
    assert gated.gate_tags == ["send_external"]


def test_mock_run_end_to_end_with_approval(tmp_path, capsys):
    code, prompts = run_cli(tmp_path, answers=("y",))
    assert code == 0
    assert len(prompts) == 1  # exactly one gate pause: the marketer's send_external
    tasks, entries = load_run(tmp_path)
    assert all(t.state == "done" for t in tasks.values())
    assert {t.assignee_role for t in tasks.values()} == {"engineer", "marketer"}
    actions = [e.action for e in entries]
    assert "escalated" in actions and "approved" in actions

    out = capsys.readouterr().out
    assert "APPROVAL REQUIRED" in out
    assert "[draft]" in out  # concrete pending_gate_context was printed
    # standup digest cites real journal entry ids
    known = {e.id for e in entries}
    cited = [chunk.split("]")[0] for chunk in out.split("[journal:")[1:]]
    assert cited and all(c in known for c in cited)
    assert (tmp_path / "standup.md").exists()


def test_mock_run_rejection_cancels(tmp_path):
    code, prompts = run_cli(tmp_path, answers=("n",))
    assert code == 0
    assert len(prompts) == 1
    tasks, entries = load_run(tmp_path)
    gated = next(t for t in tasks.values() if "email" in t.title.lower())
    assert gated.state == "cancelled"
    assert "rejected" in [e.action for e in entries]


def test_approve_all_skips_prompt(tmp_path):
    code, prompts = run_cli(tmp_path, argv_extra=("--approve-all",), answers=())
    assert code == 0
    assert prompts == []
    tasks, _ = load_run(tmp_path)
    assert all(t.state == "done" for t in tasks.values())


def test_standup_subcommand_after_run(tmp_path, capsys):
    run_cli(tmp_path, argv_extra=("--approve-all",), answers=())
    capsys.readouterr()
    code = main(["standup", str(EXAMPLE), "--out-dir", str(tmp_path)])
    assert code == 0
    out = capsys.readouterr().out
    assert "# Standup" in out
    assert "[journal:" in out
    assert "Eng-1" in out and "Mktr-1" in out
    # buckets must reflect the run's employee IDs, not freshly assigned ones
    assert out.count("done:\n") == 2


def test_standup_without_run_errors(tmp_path, capsys):
    code = main(["standup", str(EXAMPLE), "--out-dir", str(tmp_path / "empty")])
    assert code == 1
    assert "no run found" in capsys.readouterr().err


def test_claude_runner_import_guard():
    """Package must work without the SDK; runner errors clearly when absent."""
    from ai_employees import claude_runner

    if claude_runner.HAS_SDK:
        pytest.skip("claude-agent-sdk installed; guard path not reachable")
    with pytest.raises(RuntimeError, match="claude-agent-sdk"):
        claude_runner.ClaudeAgentRunner()


def test_flush_outbox_delivers_queued_items(tmp_path, capsys):
    from ai_employees.cli import cmd_flush_outbox
    from ai_employees.outbox import MockTransport, Outbox, OutboxItem

    run_cli(tmp_path, argv_extra=("--approve-all",), answers=())  # any run dir will do
    outbox = Outbox(tmp_path)
    item = outbox.add(OutboxItem(task_id="t1", employee_id="e1", kind="email", payload={"body": "hi"}))

    args = argparse.Namespace(config=str(EXAMPLE), out_dir=str(tmp_path), transport="mock")
    transport = MockTransport()
    code = cmd_flush_outbox(args, transport=transport)

    assert code == 0
    assert [i.id for i in transport.sent] == [item.id]
    assert outbox.get(item.id).status == "sent"
    out = capsys.readouterr().out
    assert "sent: email" in out


class _StubPlanner:
    def __init__(self, tasks):
        self.tasks = tasks
        self.calls = 0

    def __call__(self, company, employees):
        self.calls += 1
        return list(self.tasks)


def _plan_tasks():
    from ai_employees.models import Task

    return [
        Task(title="Build the ToyCo waitlist landing page", description="d1", assignee_role="engineer", priority=1),
        Task(
            title="Draft the ToyCo announcement email",
            description="d2",
            assignee_role="marketer",
            priority=2,
            gate_tags=["send_external"],
        ),
    ]


def test_plan_confirm_runs_derived_tasks(tmp_path, capsys):
    from ai_employees.cli import cmd_run

    stub = _StubPlanner(_plan_tasks())
    it = iter(["y", "y"])  # plan confirm, then the send_external approval gate
    args = argparse.Namespace(
        config=str(EXAMPLE), mock=True, approve_all=False, out_dir=str(tmp_path), plan=True
    )

    code = cmd_run(args, input_fn=lambda p: next(it), planner=stub)

    assert code == 0
    assert stub.calls == 1
    out = capsys.readouterr().out
    assert "DERIVED PLAN" in out
    tasks, entries = load_run(tmp_path)
    assert all(t.state == "done" for t in tasks.values())
    planned = [e for e in entries if e.action == "planned"]
    assert len(planned) == 2
    assert all(e.employee_id == "manager" for e in planned)
    assert all(e.task_id in {t.id for t in tasks.values()} for e in planned)


def test_plan_abort_does_not_run(tmp_path, capsys):
    from ai_employees.cli import cmd_run

    stub = _StubPlanner(_plan_tasks())
    args = argparse.Namespace(
        config=str(EXAMPLE), mock=True, approve_all=False, out_dir=str(tmp_path), plan=True
    )

    code = cmd_run(args, input_fn=lambda p: "n", planner=stub)

    assert code == 0
    assert "aborted" in capsys.readouterr().out
    entries = Journal(tmp_path / "journal.jsonl").read()
    assert entries == []
    assert not (tmp_path / "tasks.json").exists()


def test_plan_with_mock_and_no_planner_injection_errors(tmp_path, capsys):
    from ai_employees.cli import cmd_run

    args = argparse.Namespace(
        config=str(EXAMPLE), mock=True, approve_all=False, out_dir=str(tmp_path), plan=True
    )

    code = cmd_run(args, input_fn=lambda p: "y")

    assert code == 1
    err = capsys.readouterr().err
    assert "--mock and --plan cannot be combined" in err


def test_build_system_prompt_contains_config():
    from ai_employees.claude_runner import build_system_prompt
    from ai_employees.config import load_company

    company, employees = load_company(EXAMPLE)
    mktr = next(e for e in employees if e.role == "marketer")
    prompt = build_system_prompt(mktr, company)
    assert "Mktr-1" in prompt
    assert company.constraints[0] in prompt
    assert "TOYCO_RESEND_KEY" in prompt  # handle name, never the secret


def test_task_timeout_cli_flag_default_and_override():
    parser = build_parser()
    default_args = parser.parse_args(["run", str(EXAMPLE)])
    assert default_args.task_timeout == 600

    overridden = parser.parse_args(["run", str(EXAMPLE), "--task-timeout", "45"])
    assert overridden.task_timeout == 45.0

    disabled = parser.parse_args(["run", str(EXAMPLE), "--task-timeout", "0"])
    assert disabled.task_timeout == 0.0


def test_make_runner_passes_task_timeout_through():
    pytest.importorskip("claude_agent_sdk")

    runner = _make_runner(mock=False, task_timeout_s=45)
    assert runner.task_timeout_s == 45

    runner_disabled = _make_runner(mock=False, task_timeout_s=None)
    assert runner_disabled.task_timeout_s is None


def test_make_runner_mock_ignores_task_timeout():
    from ai_employees.runner import MockRunner

    runner = _make_runner(mock=True, task_timeout_s=45)
    assert isinstance(runner, MockRunner)  # MockRunner has no timeout concept at all


def test_cmd_run_zero_task_timeout_disables_it_on_the_runner(tmp_path, monkeypatch):
    """CLI contract: --task-timeout 0 must reach the runner as task_timeout_s=None
    (no timeout), not literal 0 (which would mean 'time out instantly')."""
    captured = {}
    real_make_runner = cli_module._make_runner

    def spy_make_runner(mock, workspace_root=None, task_timeout_s=600):
        captured["task_timeout_s"] = task_timeout_s
        return real_make_runner(mock, workspace_root=workspace_root, task_timeout_s=task_timeout_s)

    monkeypatch.setattr(cli_module, "_make_runner", spy_make_runner)

    args = argparse.Namespace(
        config=str(EXAMPLE), mock=True, approve_all=True, out_dir=str(tmp_path),
        plan=False, review="accept_all", task_timeout=0,
    )
    code = cmd_run(args, input_fn=lambda p: "y")

    assert code == 0
    assert captured["task_timeout_s"] is None


def test_cmd_run_defaults_task_timeout_when_arg_missing(tmp_path, monkeypatch):
    """Namespaces built without --task-timeout (e.g. programmatic callers,
    older tests) must fall back to the 600s default via getattr, not crash."""
    captured = {}
    real_make_runner = cli_module._make_runner

    def spy_make_runner(mock, workspace_root=None, task_timeout_s=600):
        captured["task_timeout_s"] = task_timeout_s
        return real_make_runner(mock, workspace_root=workspace_root, task_timeout_s=task_timeout_s)

    monkeypatch.setattr(cli_module, "_make_runner", spy_make_runner)

    args = argparse.Namespace(
        config=str(EXAMPLE), mock=True, approve_all=True, out_dir=str(tmp_path),
        plan=False, review="accept_all",  # no task_timeout attribute at all
    )
    code = cmd_run(args, input_fn=lambda p: "y")

    assert code == 0
    assert captured["task_timeout_s"] == 600


def test_run_prints_elapsed_seconds_per_task(tmp_path, capsys):
    code, _ = run_cli(tmp_path, answers=("y",))
    assert code == 0
    out = capsys.readouterr().out
    # the per-task completion line has the shape "[state] title — result (N.Ns)";
    # filter on " — " (em dash) to exclude the unrelated gate-context print,
    # which also happens to start with "[" (MockRunner's draft text).
    task_lines = [l for l in out.splitlines() if l.startswith("[") and " — " in l]
    assert task_lines  # at least one task completion line printed
    assert all(l.rstrip().endswith("s)") for l in task_lines)

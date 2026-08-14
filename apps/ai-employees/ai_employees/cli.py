"""CLI: `python -m ai_employees run <config>` drives the manager loop with an
interactive approval gate; `standup <config>` prints the digest of the last run."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

import yaml

from .calibration import compare_variants, format_report, golden_set
from .config import ConfigError, load_company, load_tasks
from .journal import Journal
from .manager import Manager, accept_all
from .models import MANAGER_ID, Employee, JournalEntry, StandupDigest, Task
from .outbox import FileTransport, MockTransport, Outbox, Transport, queue_workspace_outbox
from .reviewer import make_review_policy
from .planner import Planner, PlanningError
from .runner import EmployeeRunner, MockRunner
from .standup import generate_digest
from .task_queue import TaskQueue
from .templates import TEMPLATES


def _make_runner(
    mock: bool, workspace_root: Path | None = None, task_timeout_s: float | None = 600
) -> EmployeeRunner:
    if mock:
        return MockRunner()  # timeout not applicable — mock never blocks
    from .claude_runner import ClaudeAgentRunner  # requires the [agent] extra

    return ClaudeAgentRunner(workspace_root=workspace_root, task_timeout_s=task_timeout_s)


def _employee_by_id(employees: list[Employee], employee_id: str | None) -> Employee | None:
    return next((e for e in employees if e.id == employee_id), None)


def _make_workspace_resolver(
    employees: list[Employee], workspace_root: Path
) -> Callable[[Task], Path | None]:
    """Builds the LLMReviewPolicy workspace_resolver: task -> the employee's
    per-run workspace dir its file evidence refs are relative to."""
    from .claude_runner import slugify_employee_name  # requires the [agent] extra

    def resolve(task: Task) -> Path | None:
        employee = _employee_by_id(employees, task.assignee_id)
        if employee is None:
            return None
        return workspace_root / slugify_employee_name(employee.name)

    return resolve


def format_digest(digest: StandupDigest, employees: list[Employee], tasks: dict[str, Task]) -> str:
    by_id = {e.id: e.name for e in employees}
    title = {t.id: t.title for t in tasks.values()}

    def bullet(task_ids: list[str]) -> str:
        return "".join(f"\n    - {title.get(t, t)} [{t}]" for t in task_ids) or " (none)"

    lines = [f"# Standup — {digest.period_start} .. {digest.period_end}", ""]
    for row in digest.per_employee:
        lines.append(f"## {by_id.get(row['employee_id'], row['employee_id'])}")
        lines.append(f"  done:{bullet(row['done'])}")
        lines.append(f"  in progress:{bullet(row['in_progress'])}")
        lines.append(f"  blocked:{bullet(row['blocked'])}")
        lines.append("")
    if digest.pending_approvals:
        lines.append(f"Pending owner approval: {', '.join(digest.pending_approvals)}")
        lines.append("")
    lines.append("## Narrative")
    lines.append(digest.narrative)
    return "\n".join(lines)


def _digest(company, employees, tasks, journal: Journal) -> StandupDigest:
    entries = journal.read()
    if entries:
        start = min(e.timestamp for e in entries)
        end = max(e.timestamp for e in entries)
    else:
        start = end = ""
    return generate_digest(company, employees, tasks, entries, start, end)


def cmd_run(
    args: argparse.Namespace,
    input_fn: Callable[[str], str],
    planner: Planner | None = None,
) -> int:
    company, employees = load_company(args.config)
    tasks = load_tasks(args.config)

    out_dir = Path(args.out_dir) if args.out_dir else Path("runs") / company.name
    out_dir.mkdir(parents=True, exist_ok=True)
    journal_path = out_dir / "journal.jsonl"
    journal_path.unlink(missing_ok=True)  # fresh journal per run
    journal = Journal(journal_path)

    if args.plan:
        if planner is None:
            if args.mock:
                print(
                    "run: --mock and --plan cannot be combined — the planner "
                    "requires the Claude Agent SDK; drop --mock or omit --plan",
                    file=sys.stderr,
                )
                return 1
            from .planner import LLMPlanner

            planner = LLMPlanner()
        try:
            derived = planner(company, employees)
        except PlanningError as e:
            print(f"run: planning failed: {e}", file=sys.stderr)
            return 1

        print("\n=== DERIVED PLAN ===")
        for t in derived:
            gates = ", ".join(t.gate_tags) or "none"
            print(f"- [{t.assignee_role}] {t.title} (priority {t.priority}, gates: {gates})")
        answer = input_fn("\nRun this plan? [Y/n] ")
        if answer.strip().lower().startswith("n"):
            print("aborted: plan not approved")
            return 0

        for t in derived:
            journal.append(
                JournalEntry(
                    employee_id=MANAGER_ID,
                    action="planned",
                    summary=f"planned: {t.title}",
                    task_id=t.id,
                )
            )
        tasks = derived
    elif not tasks:
        print(f"{args.config}: no tasks defined — nothing to run", file=sys.stderr)
        return 1

    task_timeout = getattr(args, "task_timeout", 600)
    task_timeout_s = None if not task_timeout else task_timeout  # 0/None = no timeout

    runner = _make_runner(
        args.mock, workspace_root=out_dir / "workspace", task_timeout_s=task_timeout_s
    )
    review_name = getattr(args, "review", "accept_all")
    workspace_resolver = None
    if review_name == "llm" and getattr(runner, "workspace_root", None) is not None:
        workspace_resolver = _make_workspace_resolver(employees, runner.workspace_root)

    manager = Manager(
        company=company,
        employees=employees,
        queue=TaskQueue(),
        journal=journal,
        runner=runner,
        review_policy=make_review_policy(review_name, workspace_resolver=workspace_resolver),
    )
    for task in tasks:
        manager.submit(task)

    while True:
        start = time.monotonic()
        task = manager.run_once()
        if task is None:
            break
        elapsed = time.monotonic() - start
        if task.state == "awaiting_approval":
            employee = _employee_by_id(employees, task.assignee_id)
            who = employee.name if employee else task.assignee_id
            print(f"\n=== APPROVAL REQUIRED ===")
            print(f"{who} is waiting on owner sign-off for '{task.title}':\n")
            print(manager.pending_gate_context.get(task.id, "(no context)"))
            answer = "y" if args.approve_all else input_fn("\nApprove? [y/n] ")
            if answer.strip().lower().startswith("y"):
                manager.approve(task.id)
                print(f"approved -> {task.state}")
            else:
                manager.reject(task.id)
                print(f"rejected -> {task.state}")
        print(f"[{task.state}] {task.title} — {task.result or 'in flight'} ({elapsed:.1f}s)")

    workspace_root = getattr(manager.runner, "workspace_root", None)
    if workspace_root is not None:
        queued = queue_workspace_outbox(manager.tasks, employees, manager.journal, workspace_root, out_dir)
        if queued:
            print(
                f"\nqueued {len(queued)} outbox item(s) for delivery -> {out_dir / 'outbox'}"
                f"\n  deliver with: python -m ai_employees flush-outbox {args.config} --out-dir {out_dir}"
            )

    (out_dir / "tasks.json").write_text(
        json.dumps([t.to_dict() for t in manager.tasks.values()], indent=2)
    )
    (out_dir / "employees.json").write_text(
        json.dumps([e.to_dict() for e in employees], indent=2)
    )
    digest = _digest(company, employees, manager.tasks, manager.journal)
    text = format_digest(digest, employees, manager.tasks)
    print("\n" + text)
    (out_dir / "standup.md").write_text(text + "\n")
    print(f"\njournal: {journal_path}\nstandup: {out_dir / 'standup.md'}")
    return 0


def cmd_standup(args: argparse.Namespace) -> int:
    company, employees = load_company(args.config)
    out_dir = Path(args.out_dir) if args.out_dir else Path("runs") / company.name
    tasks_path = out_dir / "tasks.json"
    journal_path = out_dir / "journal.jsonl"
    if not journal_path.exists():
        print(f"no run found in {out_dir} — run `python -m ai_employees run {args.config}` first",
              file=sys.stderr)
        return 1
    employees_path = out_dir / "employees.json"
    if employees_path.exists():  # IDs must match the run's snapshot, not fresh ULIDs
        employees = [Employee.from_dict(d) for d in json.loads(employees_path.read_text())]
    tasks: dict[str, Task] = {}
    if tasks_path.exists():
        for d in json.loads(tasks_path.read_text()):
            t = Task.from_dict(d)
            tasks[t.id] = t
    digest = _digest(company, employees, tasks, Journal(journal_path))
    print(format_digest(digest, employees, tasks))
    return 0


def cmd_flush_outbox(args: argparse.Namespace, transport: Transport | None = None) -> int:
    """Deliver queued outbox items via a Transport. `transport` is an
    injection seam for tests; CLI use builds one from `--transport`."""
    company, employees = load_company(args.config)
    out_dir = Path(args.out_dir) if args.out_dir else Path("runs") / company.name
    outbox = Outbox(out_dir)
    journal = Journal(out_dir / "journal.jsonl")
    if transport is None:
        transport = FileTransport(out_dir) if args.transport == "file" else MockTransport()

    sent, failed = outbox.flush(transport, journal)
    for item in sent:
        print(f"sent: {item.kind} [{item.id}] -> task {item.task_id}")
    for item in failed:
        print(f"failed: {item.kind} [{item.id}] -> task {item.task_id}", file=sys.stderr)
    if not sent and not failed:
        print("outbox: nothing queued")
    else:
        print(f"\n{len(sent)} sent, {len(failed)} failed")
    return 0 if not failed else 1


def cmd_calibrate(args: argparse.Namespace) -> int:
    """Replay the judge calibration golden set through one or more
    LLMReviewPolicy variants (by model id) and print send-back precision/
    recall per variant, so judge changes are measured against a fixed
    baseline instead of vibes."""
    variants: dict[str, object] = {}
    if not args.no_baseline:
        variants["accept_all (baseline)"] = accept_all
    for model in args.model:
        from .reviewer import LLMReviewPolicy

        variants[model] = LLMReviewPolicy(model=model)
    if not variants:
        print("calibrate: nothing to run — pass --model or drop --no-baseline", file=sys.stderr)
        return 1

    reports = compare_variants(variants, golden_set())
    print(format_report(reports))
    return 0


def _render_employee_yaml(name: str, fragment: dict) -> str:
    """Employee-shaped YAML block for preview / $EDITOR, minus `description`."""
    block = {
        "name": name,
        "role": fragment["role"],
        "job_description": fragment["job_description"],
        "tools": fragment["tools"],
        "approval_gates": fragment["approval_gates"],
    }
    return yaml.safe_dump(block, sort_keys=False)


def _default_edit_fn(text: str) -> str:
    editor = os.environ.get("EDITOR", "vi")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(text)
        path = f.name
    try:
        subprocess.call([editor, path])
        return Path(path).read_text()
    finally:
        os.unlink(path)


def cmd_hire(
    args: argparse.Namespace,
    input_fn: Callable[[str], str],
    edit_fn: Callable[[str], str] = _default_edit_fn,
) -> int:
    # Append rewrites the company YAML via safe_load/safe_dump: data is
    # preserved, comments and hand formatting are not.
    if args.list:
        for name, tmpl in TEMPLATES.items():
            print(f"{name}: {tmpl['description']}")
        return 0

    if not args.name or not args.company:
        print("hire: --name and --company are required (unless --list)", file=sys.stderr)
        return 1

    template = TEMPLATES.get(args.template)
    if template is None:
        known = ", ".join(TEMPLATES)
        print(f"hire: unknown template '{args.template}' — known templates: {known}",
              file=sys.stderr)
        return 1

    try:
        company, _existing = load_company(args.company)
    except ConfigError as e:
        print(f"hire: {e}", file=sys.stderr)
        return 1

    job_description = template["job_description"].format(company=company.name)
    fragment = {
        "role": template["role"],
        "job_description": job_description,
        "tools": list(template["tools"]),
        "approval_gates": list(template["approval_gates"]),
    }

    print(f"Role: {fragment['role']}")
    print("Job description:")
    print(f"  {fragment['job_description']}")
    print(f"Default tools: {', '.join(fragment['tools'])}")
    print(f"Default approval gates: {', '.join(fragment['approval_gates']) or '(none)'}")
    answer = input_fn(f"Hire {args.name} with these defaults? [Y/n/edit] ").strip().lower()

    if answer.startswith("n"):
        print(f"not hired: {args.name}")
        return 0

    if answer.startswith("e"):
        edited_text = edit_fn(_render_employee_yaml(args.name, fragment))
        edited = yaml.safe_load(edited_text)
        if not isinstance(edited, dict):
            print("hire: edited YAML must be a mapping", file=sys.stderr)
            return 1
        employee_entry = edited
        employee_entry.setdefault("name", args.name)
    else:
        employee_entry = {"name": args.name, **fragment}

    raw = yaml.safe_load(Path(args.company).read_text()) or {}
    raw.setdefault("employees", [])
    raw["employees"].append(employee_entry)
    Path(args.company).write_text(yaml.safe_dump(raw, sort_keys=False))

    journal_path = Path("runs") / company.name / "journal.jsonl"
    journal = Journal(journal_path)
    journal.append(
        JournalEntry(
            employee_id=MANAGER_ID,
            action="hired",
            summary=f"hired {args.name} ({fragment['role']}) from template '{args.template}'",
            task_id=None,
        )
    )

    print(f"hired: {args.name} -> {args.company}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai_employees")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="run the manager loop on a company config")
    run_p.add_argument("config", help="path to company YAML, e.g. examples/toyco.yaml")
    run_p.add_argument("--mock", action="store_true",
                       help="use MockRunner (no API key, no network)")
    run_p.add_argument("--approve-all", action="store_true",
                       help="auto-approve gated actions instead of prompting")
    run_p.add_argument("--out-dir", default=None,
                       help="run artifacts dir (default: runs/<company>)")
    run_p.add_argument("--review", choices=["accept_all", "llm"], default="accept_all",
                       help="manager review policy: llm = cheap-model judge scores each "
                            "completed task and can send it back (default: accept_all)")
    run_p.add_argument("--plan", action="store_true",
                       help="derive tasks via the LLM planner instead of (or overriding) "
                            "the config's tasks: section; prints the plan and confirms "
                            "before running")
    run_p.add_argument("--task-timeout", type=float, default=600, dest="task_timeout",
                       help="per-task wall-clock timeout in seconds for the agent SDK query "
                            "(default: 600; 0 = no timeout; ignored by --mock)")

    standup_p = sub.add_parser("standup", help="print digest of the last run")
    standup_p.add_argument("config")
    standup_p.add_argument("--out-dir", default=None)

    flush_p = sub.add_parser("flush-outbox", help="deliver queued outbox items via a transport")
    flush_p.add_argument("config", help="path to company YAML, e.g. examples/toyco.yaml")
    flush_p.add_argument("--out-dir", default=None,
                         help="run artifacts dir (default: runs/<company>)")
    flush_p.add_argument("--transport", choices=["file", "mock"], default="file",
                         help="delivery transport (default: file, appends to sent.jsonl)")

    hire_p = sub.add_parser("hire", help="hire an employee from a built-in template")
    hire_p.add_argument("template", nargs="?", default=None,
                        help="template name, e.g. engineer, marketer, support, ops, researcher")
    hire_p.add_argument("--name", default=None, help="name for the new employee")
    hire_p.add_argument("--company", default=None, help="path to company YAML to append to")
    hire_p.add_argument("--list", action="store_true", help="list available templates")

    calibrate_p = sub.add_parser(
        "calibrate", help="replay the judge golden set through review-policy variants"
    )
    calibrate_p.add_argument("--model", action="append", default=[],
                             help="judge model id to evaluate as an LLMReviewPolicy variant "
                                  "(repeatable; makes real API calls)")
    calibrate_p.add_argument("--no-baseline", action="store_true",
                             help="skip the accept_all baseline variant")
    return parser


def main(argv: list[str] | None = None, input_fn: Callable[[str], str] = input) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        return cmd_run(args, input_fn)
    if args.command == "hire":
        return cmd_hire(args, input_fn)
    if args.command == "flush-outbox":
        return cmd_flush_outbox(args)
    if args.command == "calibrate":
        return cmd_calibrate(args)
    return cmd_standup(args)

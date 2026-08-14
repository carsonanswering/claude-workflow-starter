"""Real employee runner on the Claude Agent SDK. Optional dependency — install
via `pip install 'ai-employees[agent]'`; the package works without it (MockRunner).

Gate semantics mirror MockRunner: if the task carries a gate tag the employee
must escalate and it isn't approved yet, the agent is asked to produce the
concrete draft only (never perform the gated action) and the run pauses with
that draft as gate_context. Once the owner approves, a second run executes."""

import json
import re
import warnings
from pathlib import Path

from .models import Company, Employee, Task
from .runner import RunResult

try:
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ResultMessage,
        TextBlock,
        query,
    )

    HAS_SDK = True
except ImportError:  # pragma: no cover - exercised only without the extra
    HAS_SDK = False


DEFAULT_MODEL = "claude-opus-4-8"


def build_system_prompt(employee: Employee, company: Company) -> str:
    lines = [
        f"You are {employee.name}, the {employee.role} at {company.name}.",
        "",
        employee.job_description,
    ]
    if company.goals:
        lines += ["", "Company goals (highest priority first):"]
        lines += [f"- {g}" for g in company.goals]
    if company.constraints:
        lines += ["", "Hard constraints (non-negotiable):"]
        lines += [f"- {c}" for c in company.constraints]
    if company.resources:
        lines += ["", "Resources (handle names only — secrets live in the environment):"]
        lines += [f"- {k}: {_redact_if_secret(v)}" for k, v in company.resources.items()]
    return "\n".join(lines)


_SECRET_SHAPES = re.compile(
    r"(sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|xox[baprs]-[A-Za-z0-9-]{10,})"
)


def _redact_if_secret(value: str) -> str:
    """Resource values must be handle names; anything secret-shaped never reaches the model."""
    v = str(value)
    if _SECRET_SHAPES.search(v) or (len(v) >= 32 and " " not in v and not v.startswith(("http://", "https://"))):
        warnings.warn("resource value looks like a secret; redacted from system prompt")
        return "[REDACTED — put an env-var name here, not the secret]"
    return v


def _draft_prompt(task: Task, gate: str) -> str:
    return (
        f"Task: {task.title}\n\n{task.description}\n\n"
        f"This task involves the gated action '{gate}', which requires owner "
        "approval before it happens. Do NOT perform the gated action. Produce "
        "the complete, concrete artifact the owner must sign off on (for "
        "example: the exact email subject and body to be sent). Output only "
        "the artifact."
    )


def slugify_employee_name(name: str) -> str:
    """Filesystem-safe slug for an employee's per-run workspace directory."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "employee"


def snapshot_workspace(workspace: Path) -> dict[str, int]:
    """mtime_ns snapshot of every file currently under `workspace`, keyed by
    path relative to it. Call before a run to establish a baseline."""
    if not workspace.exists():
        return {}
    return {
        str(p.relative_to(workspace)): p.stat().st_mtime_ns
        for p in workspace.rglob("*")
        if p.is_file()
    }


def scan_new_or_changed_files(workspace: Path, before: dict[str, int]) -> list[dict]:
    """Files under `workspace` that are new or whose mtime advanced since
    `before`, as evidence dicts: {"kind": "file", "ref": <relative path>}."""
    if not workspace.exists():
        return []
    evidence = []
    for p in sorted(workspace.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(workspace))
        prior_mtime = before.get(rel)
        if prior_mtime is None or p.stat().st_mtime_ns > prior_mtime:
            evidence.append({"kind": "file", "ref": rel})
    return evidence


def _execute_prompt(task: Task, approved_gates: frozenset[str]) -> str:
    approval = ""
    approved_here = approved_gates & set(task.gate_tags)
    if approved_here:
        approval = (
            "\n\nThe owner has APPROVED the gated action(s): "
            f"{', '.join(sorted(approved_here))}. You may proceed with them, "
            "but you must NEVER perform the external send yourself (no calling "
            "an email/send tool, no network action). Instead, write the final, "
            "concrete artifact as a JSON file into an `outbox/` directory in "
            "your workspace — one file per item to deliver, shaped like "
            '{"kind": "email", "payload": {"to": "...", "subject": "...", '
            '"body": "..."}}. A separate, explicit delivery step reads that '
            "directory and actually sends it — that is what 'proceeding' means "
            "here."
        )
    return (
        f"Task: {task.title}\n\n{task.description}{approval}\n\n"
        "Complete the task now. Finish with a short summary of what you did "
        "and how a reviewer can verify it (files touched, commands run)."
    )


def collect_outbox_items(workspace: Path) -> list[dict]:
    """Parse `outbox/*.json` files the agent wrote in its workspace into
    plain dicts (`{"kind", "payload", ...}`). Malformed files, files that
    don't parse to a JSON object, and files whose "payload" key is present
    but not itself an object are skipped (with a warning), not fatal — this
    never raises."""
    outbox_dir = workspace / "outbox"
    if not outbox_dir.exists():
        return []
    items = []
    for p in sorted(outbox_dir.glob("*.json")):
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError) as e:
            warnings.warn(f"outbox file {p} could not be read/parsed; skipped: {e}")
            continue
        if not isinstance(data, dict):
            warnings.warn(f"outbox file {p} is not a JSON object; skipped")
            continue
        if "payload" in data and not isinstance(data["payload"], dict):
            warnings.warn(f"outbox file {p} has non-object 'payload'; skipped")
            continue
        items.append(data)
    return items


class ClaudeAgentRunner:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        max_turns: int = 25,
        cwd: str | Path | None = None,
        workspace_root: Path | None = None,
        task_timeout_s: float | None = 600,
    ) -> None:
        if not HAS_SDK:
            raise RuntimeError(
                "claude-agent-sdk is not installed; "
                "pip install 'ai-employees[agent]' or run with --mock"
            )
        self.model = model
        self.max_turns = max_turns
        self.cwd = cwd
        self.workspace_root = Path(workspace_root) if workspace_root is not None else None
        self.task_timeout_s = task_timeout_s

    def employee_workspace(self, employee: Employee) -> Path | None:
        """Per-employee working directory under `workspace_root`, created on
        demand. None if no `workspace_root` was configured (falls back to
        `self.cwd` / the process cwd, same as before workspace isolation)."""
        if self.workspace_root is None:
            return None
        ws = self.workspace_root / slugify_employee_name(employee.name)
        ws.mkdir(parents=True, exist_ok=True)
        return ws

    def run(
        self,
        employee: Employee,
        task: Task,
        company: Company,
        approved_gates: frozenset[str] = frozenset(),
    ) -> RunResult:
        system = build_system_prompt(employee, company)
        workspace = self.employee_workspace(employee)
        run_cwd = workspace if workspace is not None else self.cwd
        pending = [
            g for g in task.gate_tags
            if g in employee.approval_gates and g not in approved_gates
        ]
        if pending:
            gate = pending[0]
            text, ok = self._query(system, _draft_prompt(task, gate), employee.tools, run_cwd)
            if not ok:
                return RunResult(
                    status="failed",
                    summary=f"{employee.name} failed drafting '{task.title}': {text[:200]}",
                )
            return RunResult(
                status="paused",
                summary=f"{employee.name} paused at gated action '{gate}'",
                gate_tag=gate,
                gate_context=text,
            )

        before = snapshot_workspace(workspace) if workspace is not None else {}
        text, ok = self._query(system, _execute_prompt(task, approved_gates), employee.tools, run_cwd)
        if not ok:
            return RunResult(
                status="failed",
                summary=f"{employee.name} failed '{task.title}': {text[:200]}",
            )
        evidence = [
            {
                "kind": "message",
                "ref": f"agent://{task.id}",
                "excerpt": text[:2000],
            }
        ]
        outbox_items: list[dict] = []
        if workspace is not None:
            evidence.extend(scan_new_or_changed_files(workspace, before))
            outbox_items = collect_outbox_items(workspace)
        return RunResult(
            status="completed",
            summary=f"{employee.name} completed '{task.title}'",
            evidence=evidence,
            outbox_items=outbox_items,
        )

    def _query(
        self, system_prompt: str, prompt: str, tools: list[str], cwd: str | Path | None
    ) -> tuple[str, bool]:
        """One SDK session. Returns (output text, success)."""
        import asyncio

        options = ClaudeAgentOptions(
            model=self.model,
            system_prompt=system_prompt,
            allowed_tools=list(tools),
            max_turns=self.max_turns,
            cwd=cwd,
        )

        async def go() -> tuple[str, bool]:
            chunks: list[str] = []
            result_text: str | None = None
            failed = False
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            chunks.append(block.text)
                elif isinstance(message, ResultMessage):
                    failed = message.is_error
                    if isinstance(message.result, str):
                        result_text = message.result
            return result_text or "\n".join(chunks), not failed

        async def go_with_timeout() -> tuple[str, bool]:
            if self.task_timeout_s is None or self.task_timeout_s <= 0:
                return await go()
            try:
                return await asyncio.wait_for(go(), timeout=self.task_timeout_s)
            except asyncio.TimeoutError:
                return f"timed out after {self.task_timeout_s}s", False

        try:
            return asyncio.run(go_with_timeout())
        except Exception as e:  # SDK/transport errors -> failed task, not a crash
            return f"{type(e).__name__}: {e}", False

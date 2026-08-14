"""Goal decomposition planner. Optional dependency — same import-guard pattern
as reviewer.py; install via `pip install 'ai-employees[agent]'`.

A Planner turns a Company's goals/constraints and its roster of Employees into
a list of Task objects to submit. StaticPlanner just returns the tasks it was
handed (the config `tasks:` section — current/default behavior, wrapped as a
Planner). LLMPlanner asks a model to decompose goals into a task list, and is
strict where the review judge in reviewer.py is lenient: a planning failure
raises loudly instead of silently passing through, because an empty or
garbled plan means nothing gets submitted at all."""

import json
import re
import warnings
from typing import Protocol

from .models import Company, Employee, Task

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


DEFAULT_PLANNER_MODEL = "claude-sonnet-5"

_REQUIRED_TASK_FIELDS = ("title", "description", "assignee_role")

_SYSTEM_PROMPT = (
    "You are a planning assistant that decomposes a company's goals into a "
    "list of concrete tasks for its AI employees. Respond with ONLY a single "
    "JSON array of task objects — no prose, no markdown fences. Each task "
    'object has the form {"title": "...", "description": "...", '
    '"assignee_role": "...", "priority": 1-3, "gate_tags": [...]}. '
    "assignee_role must be one of the available employee roles given below. "
    "gate_tags must be drawn from the gate-tag vocabulary given below (use "
    "[] if the task needs no approval gate). priority 1 is highest. Include "
    "only fields from that schema."
)


class PlanningError(Exception):
    """Raised when the planner produces no usable tasks. Loud on purpose —
    unlike the review judge, a bad plan means nothing runs at all."""


class Planner(Protocol):
    def __call__(self, company: Company, employees: list[Employee]) -> list[Task]:
        ...


class StaticPlanner:
    """Wraps an explicit task list as a Planner — current/default behavior."""

    def __init__(self, tasks: list[Task]) -> None:
        self.tasks = tasks

    def __call__(self, company: Company, employees: list[Employee]) -> list[Task]:
        return list(self.tasks)


def build_planner_prompt(company: Company, employees: list[Employee]) -> str:
    roles = sorted({e.role for e in employees})
    gate_tags = sorted({g for e in employees for g in e.approval_gates})
    lines = [f"Company: {company.name}", ""]
    if company.goals:
        lines += ["Goals (highest priority first):"]
        lines += [f"- {g}" for g in company.goals]
        lines.append("")
    if company.constraints:
        lines += ["Constraints:"]
        lines += [f"- {c}" for c in company.constraints]
        lines.append("")
    lines.append(f"Available employee roles: {', '.join(roles) or '(none)'}")
    lines.append(f"Gate-tag vocabulary in use: {', '.join(gate_tags) or '(none)'}")
    lines.append("")
    lines.append("Decompose the goals into a task list. Respond with only the JSON array.")
    return "\n".join(lines)


_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def _parse_tasks(text: str, known_roles: set[str]) -> list[Task]:
    """Strict JSON-array parse + per-task validation. Invalid entries are
    dropped with a warning; an empty or unparseable result raises
    PlanningError — planning failure must be loud."""
    match = _JSON_ARRAY_RE.search(text)
    if match is None:
        raise PlanningError(f"planner returned no JSON array: {text[:200]!r}")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise PlanningError(f"planner returned malformed JSON: {e}") from e
    if not isinstance(data, list):
        raise PlanningError(f"planner JSON was not an array: {type(data).__name__}")

    tasks: list[Task] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            warnings.warn(f"planner task #{i} is not an object; dropped")
            continue
        missing = [f for f in _REQUIRED_TASK_FIELDS if not item.get(f)]
        if missing:
            warnings.warn(f"planner task #{i} missing required field(s) {missing}; dropped")
            continue
        role = item["assignee_role"]
        if role not in known_roles:
            warnings.warn(f"planner task #{i} has unknown assignee_role {role!r}; dropped")
            continue
        priority = item.get("priority", 2)
        if not isinstance(priority, int) or isinstance(priority, bool) or not (1 <= priority <= 3):
            warnings.warn(f"planner task #{i} has invalid priority {priority!r} (must be int 1-3); dropped")
            continue
        gate_tags = item.get("gate_tags") if item.get("gate_tags") is not None else []
        if not isinstance(gate_tags, list) or not all(isinstance(g, str) for g in gate_tags):
            warnings.warn(f"planner task #{i} has invalid gate_tags {gate_tags!r} (must be a list of strings); dropped")
            continue
        try:
            tasks.append(
                Task(
                    title=str(item["title"]),
                    description=str(item["description"]),
                    assignee_role=str(role),
                    priority=priority,
                    gate_tags=list(gate_tags),
                )
            )
        except (TypeError, ValueError) as e:
            warnings.warn(f"planner task #{i} has invalid field(s); dropped: {e}")
            continue

    if not tasks:
        raise PlanningError("planner produced no valid tasks")
    return tasks


class LLMPlanner:
    """Callable matching Planner: (company, employees) -> list[Task]."""

    def __init__(self, model: str = DEFAULT_PLANNER_MODEL, max_turns: int = 1) -> None:
        if not HAS_SDK:
            raise RuntimeError(
                "claude-agent-sdk is not installed; "
                "pip install 'ai-employees[agent]' or use StaticPlanner"
            )
        self.model = model
        self.max_turns = max_turns

    def __call__(self, company: Company, employees: list[Employee]) -> list[Task]:
        known_roles = {e.role for e in employees}
        prompt = build_planner_prompt(company, employees)
        text, ok = self._query(_SYSTEM_PROMPT, prompt)
        if not ok:
            raise PlanningError(f"planner query failed: {text[:200]}")
        return _parse_tasks(text, known_roles)

    def _query(self, system_prompt: str, prompt: str) -> tuple[str, bool]:
        """One SDK session. Returns (output text, success)."""
        import asyncio

        options = ClaudeAgentOptions(
            model=self.model,
            system_prompt=system_prompt,
            max_turns=self.max_turns,
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

        try:
            return asyncio.run(go())
        except Exception as e:  # SDK/transport errors -> loud failure, not silent accept
            return f"{type(e).__name__}: {e}", False

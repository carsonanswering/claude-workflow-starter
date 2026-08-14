"""LLM-judge review policy. Optional dependency — same import-guard pattern as
claude_runner.py; install via `pip install 'ai-employees[agent]'`.

An LLMReviewPolicy is a ReviewPolicy (see manager.py): it inspects a task and
its RunResult and returns None to accept, or a reason string to send the task
back for another round. The judge is a cheap model (default Haiku) asked for
a strict JSON verdict. Judge failures (SDK error, unparseable output) never
block the pipeline — they accept the result and emit a warning."""

import json
import re
import warnings
from pathlib import Path
from typing import Callable

from .models import Task
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


DEFAULT_JUDGE_MODEL = "claude-haiku-4-5-20251001"

_MAX_EXCERPT_CHARS = 2000

# Bounded inlining of file evidence into the judge prompt: per-file excerpt
# cap, and a total cap across all files in one prompt so a task with many
# large files can't blow up the judge's context.
_FILE_EXCERPT_CHARS = 1500
_TOTAL_FILE_BUDGET = 6000

_SYSTEM_PROMPT = (
    "You are a strict quality-control judge for an AI employee's completed "
    "work. Given a task and the result the employee produced, decide whether "
    "the result actually satisfies the task. Respond with ONLY a single JSON "
    'object of the form {"accept": true|false, "reason": "..."} — no prose, '
    "no markdown fences. If accept is false, reason must explain concretely "
    "what is missing or wrong so the employee can fix it. If accept is true, "
    "reason may be a short justification or empty."
)

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _read_file_excerpt(path: Path) -> str:
    """Bounded excerpt of a file's contents for judge-prompt inlining. Never
    raises: missing files and binary/undecodable files get a placeholder."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "[file not found]"
    except IsADirectoryError:
        return "[file not found]"
    except UnicodeDecodeError:
        return "[binary file]"
    if len(text) > _FILE_EXCERPT_CHARS:
        return text[:_FILE_EXCERPT_CHARS] + " [truncated]"
    return text


def _format_evidence(evidence: list[dict], workspace: Path | None = None) -> str:
    if not evidence:
        return "(no evidence attached)"
    lines = []
    file_budget = _TOTAL_FILE_BUDGET
    budget_noted = False
    for e in evidence:
        kind = e.get("kind", "?")
        ref = e.get("ref", "?")
        excerpt = e.get("excerpt")
        line = f"- [{kind}] {ref}"
        if excerpt:
            line += f": {excerpt[:_MAX_EXCERPT_CHARS]}"
        lines.append(line)
        if kind == "file" and workspace is not None:
            if file_budget <= 0:
                if not budget_noted:
                    lines.append("  [further files omitted]")
                    budget_noted = True
                continue
            content = _read_file_excerpt(workspace / ref)
            if len(content) > file_budget:
                content = content[:file_budget].rstrip() + " [truncated]"
                file_budget = 0
            else:
                file_budget -= len(content)
            lines.append(f"  content:\n{content}")
    return "\n".join(lines)


def build_judge_prompt(task: Task, result: RunResult, workspace: Path | None = None) -> str:
    return (
        f"Task title: {task.title}\n"
        f"Task description: {task.description}\n\n"
        f"Result status: {result.status}\n"
        f"Result summary: {result.summary}\n\n"
        f"Evidence:\n{_format_evidence(result.evidence, workspace)}\n\n"
        "Company delivery policy: employees never perform external sends "
        "(email, posts, messages) directly. Approved sends are written as "
        "drafts to an outbox and delivered by a separate explicit flush step. "
        "For tasks that involve sending, a complete, owner-approved draft "
        "queued in the outbox IS the successful outcome — do not reject a "
        "result for stopping at the outbox.\n\n"
        "Judge whether this result satisfies the task. Respond with only the "
        "JSON verdict object."
    )


def _parse_verdict(text: str) -> tuple[bool, str] | None:
    """Extract the first JSON object from `text` and parse it as a verdict.
    Returns (accept, reason) or None if nothing parseable was found."""
    match = _JSON_OBJECT_RE.search(text)
    if match is None:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or "accept" not in data:
        return None
    accept = bool(data["accept"])
    reason = str(data.get("reason") or "")
    return accept, reason


class LLMReviewPolicy:
    """Callable matching ReviewPolicy: (task, run_result) -> None | reason."""

    def __init__(
        self,
        model: str = DEFAULT_JUDGE_MODEL,
        max_turns: int = 1,
        workspace_resolver: Callable[[Task], Path | None] | None = None,
    ) -> None:
        if not HAS_SDK:
            raise RuntimeError(
                "claude-agent-sdk is not installed; "
                "pip install 'ai-employees[agent]' or use accept_all"
            )
        self.model = model
        self.max_turns = max_turns
        # Resolves a task to the employee workspace dir its file evidence is
        # relative to, so file excerpts can be inlined into the judge prompt.
        # None (the default) preserves the old ref-only behavior.
        self.workspace_resolver = workspace_resolver

    def __call__(self, task: Task, result: RunResult) -> str | None:
        workspace = self.workspace_resolver(task) if self.workspace_resolver is not None else None
        prompt = build_judge_prompt(task, result, workspace)
        text, ok = self._query(_SYSTEM_PROMPT, prompt)
        if not ok:
            warnings.warn(
                f"LLM review judge failed for task '{task.title}': {text[:200]}; accepting"
            )
            return None

        verdict = _parse_verdict(text)
        if verdict is None:
            warnings.warn(
                f"LLM review judge returned unparseable verdict for task "
                f"'{task.title}': {text[:200]}; accepting"
            )
            return None

        accept, reason = verdict
        if accept:
            return None
        return reason or "judge rejected without a reason"

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
        except Exception as e:  # SDK/transport errors -> accept, never crash
            return f"{type(e).__name__}: {e}", False


def make_review_policy(
    name: str,
    workspace_resolver: Callable[[Task], Path | None] | None = None,
):
    """Factory for CLI use: "accept_all" | "llm" -> a ReviewPolicy callable."""
    if name == "accept_all":
        from .manager import accept_all

        return accept_all
    if name == "llm":
        return LLMReviewPolicy(workspace_resolver=workspace_resolver)
    raise ValueError(f"unknown review policy: {name!r}")

"""LLMReviewPolicy: judge prompt contents, defensive JSON verdict parsing, and
the import-guard path. No network/API calls — the SDK query call is stubbed
via monkeypatching LLMReviewPolicy._query."""

import warnings

import pytest

pytest.importorskip("claude_agent_sdk")

from ai_employees.models import Task
from ai_employees.runner import RunResult
from ai_employees.reviewer import (
    LLMReviewPolicy,
    build_judge_prompt,
    make_review_policy,
)


def make_task() -> Task:
    return Task(
        title="Write onboarding doc",
        description="Draft a one-pager for new hires, covering setup steps.",
        assignee_role="ops",
    )


def make_result(**kwargs) -> RunResult:
    defaults = dict(
        status="completed",
        summary="Ops-1 completed 'Write onboarding doc'",
        evidence=[
            {"kind": "file", "ref": "onboarding.md", "excerpt": "# Onboarding\n\nStep 1..."}
        ],
    )
    defaults.update(kwargs)
    return RunResult(**defaults)


def test_build_judge_prompt_contains_task_and_evidence():
    task = make_task()
    result = make_result()

    prompt = build_judge_prompt(task, result)

    assert task.title in prompt
    assert task.description in prompt
    assert result.summary in prompt
    assert "onboarding.md" in prompt
    assert "Step 1..." in prompt


def test_judge_accepts_on_true_verdict(monkeypatch):
    policy = LLMReviewPolicy()
    monkeypatch.setattr(
        policy, "_query", lambda system_prompt, prompt: ('{"accept": true, "reason": ""}', True)
    )

    reason = policy(make_task(), make_result())

    assert reason is None


def test_judge_rejects_with_reason_on_false_verdict(monkeypatch):
    policy = LLMReviewPolicy()
    monkeypatch.setattr(
        policy,
        "_query",
        lambda system_prompt, prompt: (
            '{"accept": false, "reason": "missing setup steps for laptop provisioning"}',
            True,
        ),
    )

    reason = policy(make_task(), make_result())

    assert reason == "missing setup steps for laptop provisioning"


def test_judge_parses_json_embedded_in_prose(monkeypatch):
    policy = LLMReviewPolicy()
    text = 'Sure thing! Here is my verdict:\n{"accept": false, "reason": "too short"}\nThanks.'
    monkeypatch.setattr(policy, "_query", lambda system_prompt, prompt: (text, True))

    reason = policy(make_task(), make_result())

    assert reason == "too short"


def test_judge_rejects_without_reason_uses_fallback_message(monkeypatch):
    policy = LLMReviewPolicy()
    monkeypatch.setattr(
        policy, "_query", lambda system_prompt, prompt: ('{"accept": false}', True)
    )

    reason = policy(make_task(), make_result())

    assert reason == "judge rejected without a reason"


def test_malformed_json_accepts_and_warns(monkeypatch):
    policy = LLMReviewPolicy()
    monkeypatch.setattr(
        policy, "_query", lambda system_prompt, prompt: ("not json at all", True)
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        reason = policy(make_task(), make_result())

    assert reason is None
    assert any("unparseable" in str(w.message) for w in caught)


def test_sdk_query_error_accepts_and_warns(monkeypatch):
    policy = LLMReviewPolicy()
    monkeypatch.setattr(
        policy, "_query", lambda system_prompt, prompt: ("RuntimeError: boom", False)
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        reason = policy(make_task(), make_result())

    assert reason is None
    assert any("judge failed" in str(w.message) for w in caught)


def test_verdict_missing_accept_key_treated_as_unparseable(monkeypatch):
    policy = LLMReviewPolicy()
    monkeypatch.setattr(
        policy, "_query", lambda system_prompt, prompt: ('{"reason": "no accept field"}', True)
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        reason = policy(make_task(), make_result())

    assert reason is None
    assert any("unparseable" in str(w.message) for w in caught)


def test_make_review_policy_accept_all():
    from ai_employees.manager import accept_all

    policy = make_review_policy("accept_all")

    assert policy is accept_all


def test_make_review_policy_llm_returns_instance():
    policy = make_review_policy("llm")

    assert isinstance(policy, LLMReviewPolicy)


def test_make_review_policy_unknown_raises():
    with pytest.raises(ValueError):
        make_review_policy("bogus")


def test_import_guard_raises_without_sdk(monkeypatch):
    import ai_employees.reviewer as reviewer_module

    monkeypatch.setattr(reviewer_module, "HAS_SDK", False)

    with pytest.raises(RuntimeError, match="claude-agent-sdk"):
        reviewer_module.LLMReviewPolicy()


# --- file evidence inlining -------------------------------------------------


def make_file_result(ref: str) -> RunResult:
    return RunResult(
        status="completed",
        summary="employee completed the task",
        evidence=[{"kind": "file", "ref": ref}],
    )


def test_build_judge_prompt_inlines_file_content(tmp_path):
    (tmp_path / "onboarding.md").write_text("# Onboarding\n\nStep 1: get a laptop.")

    prompt = build_judge_prompt(make_task(), make_file_result("onboarding.md"), tmp_path)

    assert "Step 1: get a laptop." in prompt
    assert "[file not found]" not in prompt


def test_build_judge_prompt_truncates_long_file(tmp_path):
    (tmp_path / "big.md").write_text("x" * 3000)

    prompt = build_judge_prompt(make_task(), make_file_result("big.md"), tmp_path)

    assert "x" * 1500 in prompt
    assert "x" * 1501 not in prompt
    assert "[truncated]" in prompt


def test_build_judge_prompt_skips_binary_file(tmp_path):
    (tmp_path / "binary.dat").write_bytes(b"\xff\xfe\x00\x01binary junk")

    prompt = build_judge_prompt(make_task(), make_file_result("binary.dat"), tmp_path)

    assert "[binary file]" in prompt


def test_build_judge_prompt_notes_missing_file(tmp_path):
    prompt = build_judge_prompt(make_task(), make_file_result("does-not-exist.md"), tmp_path)

    assert "[file not found]" in prompt


def test_build_judge_prompt_caps_total_file_budget(tmp_path):
    for i in range(6):
        (tmp_path / f"file{i}.md").write_text("y" * 1500)
    evidence = [{"kind": "file", "ref": f"file{i}.md"} for i in range(6)]
    result = RunResult(status="completed", summary="done", evidence=evidence)

    prompt = build_judge_prompt(make_task(), result, tmp_path)

    assert "[further files omitted]" in prompt
    # Total inlined file content must not blow past the 6000-char budget
    # (boilerplate prompt text also contains a handful of "y"s).
    assert prompt.count("y" * 1500) == 4


def test_build_judge_prompt_workspace_none_unchanged():
    result = make_file_result("onboarding.md")

    prompt = build_judge_prompt(make_task(), result)

    assert "onboarding.md" in prompt
    assert "[file not found]" not in prompt
    assert "content:" not in prompt


def test_llm_review_policy_uses_workspace_resolver(monkeypatch, tmp_path):
    (tmp_path / "onboarding.md").write_text("# Onboarding\n\nStep 1: get a laptop.")

    captured = {}

    def fake_query(system_prompt, prompt):
        captured["prompt"] = prompt
        return '{"accept": true, "reason": ""}', True

    policy = LLMReviewPolicy(workspace_resolver=lambda task: tmp_path)
    monkeypatch.setattr(policy, "_query", fake_query)

    reason = policy(make_task(), make_file_result("onboarding.md"))

    assert reason is None
    assert "Step 1: get a laptop." in captured["prompt"]


def test_llm_review_policy_resolver_none_unchanged(monkeypatch):
    captured = {}

    def fake_query(system_prompt, prompt):
        captured["prompt"] = prompt
        return '{"accept": true, "reason": ""}', True

    policy = LLMReviewPolicy()
    monkeypatch.setattr(policy, "_query", fake_query)

    policy(make_task(), make_file_result("onboarding.md"))

    assert "content:" not in captured["prompt"]

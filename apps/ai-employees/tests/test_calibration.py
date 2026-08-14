"""Judge calibration harness: golden-set shape, metric math, and CLI wiring.

No network calls: LLM variants are exercised by monkeypatching
LLMReviewPolicy._query, same pattern as test_reviewer.py.
"""

import pytest

from ai_employees.calibration import (
    CalibrationCase,
    CaseVerdict,
    compare_variants,
    compute_metrics,
    format_report,
    golden_set,
    run_calibration,
    run_case,
)
from ai_employees.manager import accept_all
from ai_employees.models import Task
from ai_employees.runner import RunResult


def make_case(case_id: str, expect_send_back: bool) -> CalibrationCase:
    return CalibrationCase(
        id=case_id,
        task=Task(title="t", description="d", assignee_role="engineer"),
        result=RunResult(status="completed", summary="s"),
        expect_send_back=expect_send_back,
    )


def always_accept(task, result):
    return None


def always_reject(task, result):
    return "nope"


# --- golden set shape --------------------------------------------------


def test_golden_set_nonempty_and_mixed_labels():
    cases = golden_set()

    assert len(cases) >= 8
    assert any(c.expect_send_back for c in cases)
    assert any(not c.expect_send_back for c in cases)


def test_golden_set_ids_unique():
    cases = golden_set()

    assert len(cases) == len({c.id for c in cases})


def test_golden_set_is_a_defensive_copy():
    a = golden_set()
    a.clear()

    assert len(golden_set()) > 0


# --- run_case ------------------------------------------------------------


def test_run_case_accept_policy_predicts_no_send_back():
    case = make_case("c1", expect_send_back=False)

    verdict = run_case(always_accept, case)

    assert verdict.predicted_send_back is False
    assert verdict.correct is True


def test_run_case_reject_policy_predicts_send_back_and_carries_reason():
    case = make_case("c1", expect_send_back=True)

    verdict = run_case(always_reject, case)

    assert verdict.predicted_send_back is True
    assert verdict.reason == "nope"
    assert verdict.correct is True


def test_run_case_mismatch_flagged_incorrect():
    case = make_case("c1", expect_send_back=True)

    verdict = run_case(always_accept, case)

    assert verdict.correct is False


# --- compute_metrics -------------------------------------------------------


def test_compute_metrics_perfect_policy():
    verdicts = [
        CaseVerdict("a", True, True, "r"),
        CaseVerdict("b", False, False, None),
        CaseVerdict("c", True, True, "r"),
    ]

    m = compute_metrics(verdicts)

    assert (m.true_positive, m.false_positive, m.true_negative, m.false_negative) == (2, 0, 1, 0)
    assert m.precision == 1.0
    assert m.recall == 1.0
    assert m.f1 == 1.0
    assert m.accuracy == 1.0


def test_compute_metrics_over_rejecting_policy_hurts_precision_not_recall():
    # Judge sends back everything: catches every true positive but also
    # false-positives on cases that should have been accepted.
    verdicts = [
        CaseVerdict("a", True, True, "r"),   # TP
        CaseVerdict("b", False, True, "r"),  # FP
        CaseVerdict("c", False, True, "r"),  # FP
    ]

    m = compute_metrics(verdicts)

    assert m.recall == 1.0
    assert m.precision == pytest.approx(1 / 3)


def test_compute_metrics_never_sending_back_gives_zero_recall():
    verdicts = [
        CaseVerdict("a", True, False, None),   # FN
        CaseVerdict("b", False, False, None),  # TN
    ]

    m = compute_metrics(verdicts)

    assert m.recall == 0.0
    assert m.precision == 1.0  # vacuous: no send-backs issued at all
    assert m.f1 == 0.0


def test_compute_metrics_empty_verdicts():
    m = compute_metrics([])

    assert m.n == 0
    assert m.accuracy == 0.0
    assert m.precision == 1.0
    assert m.recall == 1.0


# --- run_calibration / compare_variants -----------------------------------


def test_run_calibration_against_golden_set_accept_all():
    report = run_calibration(accept_all)

    # accept_all never sends back, so every send-back-deserving golden case
    # is a false negative — precision is vacuous (1.0), recall is 0.
    assert report.metrics.true_positive == 0
    assert report.metrics.false_positive == 0
    assert report.metrics.recall == 0.0


def test_run_calibration_against_golden_set_always_reject():
    report = run_calibration(always_reject)

    assert report.metrics.true_negative == 0
    assert report.metrics.recall == 1.0
    assert report.metrics.precision < 1.0  # false-positives on the clean-accept cases


def test_compare_variants_runs_each_policy_over_same_cases():
    reports = compare_variants({"accept": always_accept, "reject": always_reject})

    assert set(reports) == {"accept", "reject"}
    assert reports["accept"].metrics.n == reports["reject"].metrics.n == len(golden_set())
    assert reports["accept"].name == "accept"


def test_variant_report_mismatches_lists_only_incorrect_cases():
    report = run_calibration(always_accept)

    mismatches = report.mismatches

    assert all(not v.correct for v in mismatches)
    assert len(mismatches) == sum(1 for c in golden_set() if c.expect_send_back)


def test_format_report_includes_variant_names_and_mismatch_detail():
    reports = compare_variants({"accept": always_accept})

    text = format_report(reports)

    assert "accept" in text
    assert "precision" in text
    assert "mismatches" in text


def test_format_report_no_mismatch_section_for_perfect_variant():
    perfect_cases = [make_case("only", expect_send_back=False)]

    reports = compare_variants({"accept": always_accept}, cases=perfect_cases)
    text = format_report(reports)

    assert "mismatches" not in text


# --- CLI wiring -------------------------------------------------------------


def test_cli_calibrate_baseline_only(capsys):
    from ai_employees.cli import main

    rc = main(["calibrate"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "accept_all (baseline)" in out
    assert "precision" in out


def test_cli_calibrate_no_baseline_and_no_model_errors(capsys):
    from ai_employees.cli import main

    rc = main(["calibrate", "--no-baseline"])

    assert rc == 1
    assert "nothing to run" in capsys.readouterr().err


def test_cli_calibrate_with_llm_variant(monkeypatch, capsys):
    pytest.importorskip("claude_agent_sdk")
    from ai_employees import reviewer as reviewer_module
    from ai_employees.cli import main

    monkeypatch.setattr(
        reviewer_module.LLMReviewPolicy,
        "_query",
        lambda self, system_prompt, prompt: ('{"accept": true, "reason": ""}', True),
    )

    rc = main(["calibrate", "--model", "claude-haiku-4-5-20251001", "--no-baseline"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "claude-haiku-4-5-20251001" in out

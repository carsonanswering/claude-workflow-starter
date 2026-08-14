"""Judge calibration harness.

A ReviewPolicy (see manager.py) is judged on one thing that matters
operationally: does it send back the tasks that actually deserve a send-back,
without crying wolf on good work? This module replays a hand-labeled golden
set of (task, result) cases — each tagged with whether a competent human
reviewer would send it back — through one or more ReviewPolicy variants and
reports send-back precision/recall so judge prompt/model changes can be
compared against a fixed baseline instead of vibes.

No network calls live here: this harness is policy-agnostic. It calls
`policy(task, result)` exactly like the manager loop does. Wiring a real
LLMReviewPolicy variant in means real API calls; tests instead pass stub
policies (plain callables) — the golden set and metrics logic are what's
under test, not any particular judge model.
"""

from dataclasses import dataclass, field

from .models import Task
from .runner import RunResult


@dataclass(frozen=True)
class CalibrationCase:
    """One hand-labeled (task, result) pair for judge calibration.

    `expect_send_back` is the ground-truth call a competent human reviewer
    would make: True if this result should be sent back for another round,
    False if it should be accepted as-is.
    """

    id: str
    task: Task
    result: RunResult
    expect_send_back: bool
    notes: str = ""


def _task(title: str, description: str, role: str = "engineer") -> Task:
    return Task(title=title, description=description, assignee_role=role)


# Hand-labeled golden set. Skewed toward the failure modes the judge exists to
# catch (silent partial completion, off-topic output, missing evidence) plus
# enough clean accepts to catch a judge that over-rejects. Extend this list as
# real send-back disputes surface in live runs — that is the intended
# maintenance path, not a one-time fixture.
GOLDEN_SET: list[CalibrationCase] = [
    CalibrationCase(
        id="clean-accept-file-evidence",
        task=_task(
            "Write onboarding doc",
            "Draft a one-pager for new hires covering laptop setup and VPN access.",
            role="ops",
        ),
        result=RunResult(
            status="completed",
            summary="Ops-1 completed 'Write onboarding doc'",
            evidence=[
                {
                    "kind": "file",
                    "ref": "onboarding.md",
                    "excerpt": (
                        "# Onboarding\n\n1. Request a laptop via IT.\n"
                        "2. Install the VPN client and connect with your SSO login.\n"
                        "3. Join #new-hires on Slack."
                    ),
                }
            ],
        ),
        expect_send_back=False,
        notes="Directly satisfies the task; concrete steps for both named topics.",
    ),
    CalibrationCase(
        id="reject-off-topic",
        task=_task(
            "Write onboarding doc",
            "Draft a one-pager for new hires covering laptop setup and VPN access.",
            role="ops",
        ),
        result=RunResult(
            status="completed",
            summary="Ops-1 completed 'Write onboarding doc'",
            evidence=[
                {
                    "kind": "file",
                    "ref": "onboarding.md",
                    "excerpt": "# Company History\n\nWe were founded in 2019...",
                }
            ],
        ),
        expect_send_back=True,
        notes="Evidence doesn't address either required topic (laptop, VPN).",
    ),
    CalibrationCase(
        id="reject-empty-evidence",
        task=_task(
            "Fix the login bug",
            "Users can't log in with email addresses containing a '+'; fix and add a test.",
        ),
        result=RunResult(
            status="completed",
            summary="Engineer-1 completed 'Fix the login bug'",
            evidence=[],
        ),
        expect_send_back=True,
        notes="Claims completion with zero evidence a fix or test exists.",
    ),
    CalibrationCase(
        id="reject-failed-status",
        task=_task(
            "Fix the login bug",
            "Users can't log in with email addresses containing a '+'; fix and add a test.",
        ),
        result=RunResult(
            status="failed",
            summary="Engineer-1 hit an error on 'Fix the login bug'",
        ),
        expect_send_back=True,
        notes="Explicit failure status.",
    ),
    CalibrationCase(
        id="accept-outbox-draft",
        task=_task(
            "Email the customer about the outage",
            "Draft and send a status update to the affected customer.",
            role="support",
        ),
        result=RunResult(
            status="completed",
            summary="Support-1 completed 'Email the customer about the outage'",
            evidence=[
                {
                    "kind": "outbox",
                    "ref": "outbox/support-1-001.json",
                    "excerpt": "Subject: Status update on your outage\n\nHi ...",
                }
            ],
            outbox_items=[{"kind": "email", "payload": {"subject": "Status update"}}],
        ),
        expect_send_back=False,
        notes="Company policy: a queued outbox draft IS the successful outcome for sends.",
    ),
    CalibrationCase(
        id="reject-partial-multi-part-task",
        task=_task(
            "Ship the landing page",
            "Build index.html, styles.css, and a smoke test (test.mjs) for the new landing page.",
        ),
        result=RunResult(
            status="completed",
            summary="Engineer-1 completed 'Ship the landing page'",
            evidence=[
                {"kind": "file", "ref": "index.html", "excerpt": "<html>...</html>"},
            ],
        ),
        expect_send_back=True,
        notes="Two of three required deliverables (styles.css, test.mjs) missing.",
    ),
    CalibrationCase(
        id="accept-multi-part-task-complete",
        task=_task(
            "Ship the landing page",
            "Build index.html, styles.css, and a smoke test (test.mjs) for the new landing page.",
        ),
        result=RunResult(
            status="completed",
            summary="Engineer-1 completed 'Ship the landing page'",
            evidence=[
                {"kind": "file", "ref": "index.html", "excerpt": "<html>...</html>"},
                {"kind": "file", "ref": "styles.css", "excerpt": "body { margin: 0; }"},
                {"kind": "file", "ref": "test.mjs", "excerpt": "assert(true);"},
            ],
        ),
        expect_send_back=False,
        notes="All three required deliverables present.",
    ),
    CalibrationCase(
        id="reject-vague-summary-only",
        task=_task(
            "Write launch tweet copy",
            "Draft 3 variants of launch-announcement tweet copy for review.",
            role="marketer",
        ),
        result=RunResult(
            status="completed",
            summary="Marketer-1 completed 'Write launch tweet copy'",
            evidence=[
                {"kind": "message", "ref": "note", "excerpt": "Done, see notes."}
            ],
        ),
        expect_send_back=True,
        notes="No actual tweet copy attached, just a claim of completion.",
    ),
    CalibrationCase(
        id="accept-minimal-but-correct",
        task=_task(
            "Add a LICENSE file",
            "Add an MIT LICENSE file to the repo root.",
        ),
        result=RunResult(
            status="completed",
            summary="Engineer-1 completed 'Add a LICENSE file'",
            evidence=[
                {"kind": "file", "ref": "LICENSE", "excerpt": "MIT License\n\nCopyright (c) ..."}
            ],
        ),
        expect_send_back=False,
        notes="Small task, minimal but sufficient evidence.",
    ),
    CalibrationCase(
        id="reject-wrong-content-type",
        task=_task(
            "Add a LICENSE file",
            "Add an MIT LICENSE file to the repo root.",
        ),
        result=RunResult(
            status="completed",
            summary="Engineer-1 completed 'Add a LICENSE file'",
            evidence=[
                {"kind": "file", "ref": "README.md", "excerpt": "# Project\n\nSee LICENSE."}
            ],
        ),
        expect_send_back=True,
        notes="References a LICENSE file but never actually produced one.",
    ),
]


def golden_set() -> list[CalibrationCase]:
    """Copy of the built-in golden set (defensive copy; list is otherwise
    immutable in practice since CalibrationCase is frozen)."""
    return list(GOLDEN_SET)


@dataclass
class CaseVerdict:
    case_id: str
    expected_send_back: bool
    predicted_send_back: bool
    reason: str | None
    notes: str = ""

    @property
    def correct(self) -> bool:
        return self.expected_send_back == self.predicted_send_back


@dataclass
class CalibrationMetrics:
    n: int
    true_positive: int  # judge sent back a case that should be sent back
    false_positive: int  # judge sent back a case that should have been accepted
    true_negative: int  # judge accepted a case that should be accepted
    false_negative: int  # judge accepted a case that should have been sent back

    @property
    def precision(self) -> float:
        """Send-back precision: of the cases the judge sent back, how many
        actually deserved it. Undefined (1.0, vacuously) if the judge never
        sends anything back."""
        denom = self.true_positive + self.false_positive
        return 1.0 if denom == 0 else self.true_positive / denom

    @property
    def recall(self) -> float:
        """Of the cases that deserved a send-back, how many the judge caught."""
        denom = self.true_positive + self.false_negative
        return 1.0 if denom == 0 else self.true_positive / denom

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 0.0 if (p + r) == 0 else 2 * p * r / (p + r)

    @property
    def accuracy(self) -> float:
        return 0.0 if self.n == 0 else (self.true_positive + self.true_negative) / self.n


def compute_metrics(verdicts: list[CaseVerdict]) -> CalibrationMetrics:
    tp = sum(1 for v in verdicts if v.expected_send_back and v.predicted_send_back)
    fp = sum(1 for v in verdicts if not v.expected_send_back and v.predicted_send_back)
    tn = sum(1 for v in verdicts if not v.expected_send_back and not v.predicted_send_back)
    fn = sum(1 for v in verdicts if v.expected_send_back and not v.predicted_send_back)
    return CalibrationMetrics(
        n=len(verdicts), true_positive=tp, false_positive=fp, true_negative=tn, false_negative=fn
    )


def run_case(policy, case: CalibrationCase) -> CaseVerdict:
    """Replay one case through a ReviewPolicy callable: (task, result) -> reason|None."""
    reason = policy(case.task, case.result)
    return CaseVerdict(
        case_id=case.id,
        expected_send_back=case.expect_send_back,
        predicted_send_back=reason is not None,
        reason=reason,
        notes=case.notes,
    )


@dataclass
class VariantReport:
    name: str
    verdicts: list[CaseVerdict]
    metrics: CalibrationMetrics = field(init=False)

    def __post_init__(self) -> None:
        self.metrics = compute_metrics(self.verdicts)

    @property
    def mismatches(self) -> list[CaseVerdict]:
        return [v for v in self.verdicts if not v.correct]


def run_calibration(policy, cases: list[CalibrationCase] | None = None) -> VariantReport:
    """Replay `cases` (default: the built-in golden set) through a single
    ReviewPolicy and report per-case verdicts plus aggregate metrics."""
    cases = cases if cases is not None else golden_set()
    verdicts = [run_case(policy, case) for case in cases]
    return VariantReport(name=getattr(policy, "__name__", type(policy).__name__), verdicts=verdicts)


def compare_variants(
    variants: dict[str, object], cases: list[CalibrationCase] | None = None
) -> dict[str, VariantReport]:
    """Run each named ReviewPolicy variant over the same case set so their
    metrics are directly comparable. `variants` maps a display name (e.g. a
    model id or config label) to a ReviewPolicy callable."""
    cases = cases if cases is not None else golden_set()
    reports = {}
    for name, policy in variants.items():
        report = run_calibration(policy, cases)
        report.name = name
        reports[name] = report
    return reports


def format_report(reports: dict[str, VariantReport]) -> str:
    """Human-readable comparison table plus mismatch detail, for CLI output."""
    lines = [f"{'variant':<28}{'n':>4}{'precision':>11}{'recall':>9}{'f1':>7}{'acc':>7}"]
    for name, report in reports.items():
        m = report.metrics
        lines.append(
            f"{name:<28}{m.n:>4}{m.precision:>11.2f}{m.recall:>9.2f}{m.f1:>7.2f}{m.accuracy:>7.2f}"
        )
    for name, report in reports.items():
        if report.mismatches:
            lines.append(f"\n{name} mismatches:")
            for v in report.mismatches:
                got = "send-back" if v.predicted_send_back else "accept"
                want = "send-back" if v.expected_send_back else "accept"
                lines.append(f"  - {v.case_id}: expected {want}, got {got} ({v.notes})")
    return "\n".join(lines)

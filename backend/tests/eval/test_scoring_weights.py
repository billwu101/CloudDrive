"""Scoring: a check that ran must be able to fail the case.

The bug this pins down (found 2026-07-28, engine side fixed 2026-07-29): a
dimension missing from the case's ``weights`` contributed 0 to both the
numerator and the denominator, so its checks were purely decorative. Real
consequence: gen-ec2-081 scored 1.00 PASS with its ``execution`` dimension at
0.67, and every EC3 codegen smoke-test check had been ignored since Stage A —
the harness reported success while the thing it was supposed to verify failed.
"""

from __future__ import annotations

from eval.report import unweighted_dimension_warning
from eval.schema import EvalCase, Scoring
from eval.scoring import aggregate_runs, score_case
from eval.verifier import CheckResult


def _case(weights: dict[str, float], threshold: float = 0.8) -> EvalCase:
    return EvalCase(
        id="c",
        prompt="p",
        scoring=Scoring(weights=weights, pass_threshold=threshold, min_pass_rate=1.0),
    )


def test_a_failing_check_in_an_undeclared_dimension_now_counts() -> None:
    case = _case({"correctness": 1.0})
    checks = [
        CheckResult("correctness", "plan is right", True, ""),
        CheckResult("execution", "every step succeeded", False, "step 3 failed"),
    ]

    score = score_case(case, checks)

    assert score.score == 0.5  # was 1.00 — execution was silently weightless
    assert not score.passed
    assert score.unweighted_dimensions == ["execution"]


def test_declared_weights_still_decide_the_mix() -> None:
    case = _case({"correctness": 3.0, "state": 1.0})
    checks = [
        CheckResult("correctness", "c", True, ""),
        CheckResult("state", "s", False, ""),
    ]

    assert score_case(case, checks).score == 0.75
    assert score_case(case, checks).unweighted_dimensions == []


def test_explicit_zero_weight_is_respected_as_report_only() -> None:
    """An oversight defaults to full weight; a deliberate 0 must stay 0 — the
    two are only distinguishable by whether the dimension appears at all."""

    case = _case({"efficiency": 0.0})
    checks = [CheckResult("efficiency", "cheap enough", False, "")]

    score = score_case(case, checks)

    assert score.score == 0.0  # averaged, not divided by a zero total weight
    assert score.unweighted_dimensions == []


def test_the_report_names_cases_whose_dimensions_were_never_weighted() -> None:
    case = _case({"correctness": 1.0})
    checks = [
        CheckResult("correctness", "c", True, ""),
        CheckResult("state", "s", True, ""),
        CheckResult("execution", "e", True, ""),
    ]
    aggregate = aggregate_runs(case, [score_case(case, checks)])

    warning = unweighted_dimension_warning([aggregate])

    assert "execution, state" in warning
    assert "c" in warning


def test_nothing_to_warn_about_when_every_dimension_is_declared() -> None:
    case = _case({"correctness": 1.0, "state": 1.0})
    checks = [
        CheckResult("correctness", "c", True, ""),
        CheckResult("state", "s", True, ""),
    ]
    aggregate = aggregate_runs(case, [score_case(case, checks)])

    assert unweighted_dimension_warning([aggregate]) == ""

from __future__ import annotations

from eval.schema import EvalCase, Expect, StateExpect
from eval.scoring import CaseScore, aggregate_runs
from eval.verifier import verify_state


def _case(
    *, runs: int = 1, min_pass_rate: float = 1.0, state: StateExpect | None = None
) -> EvalCase:
    case = EvalCase(id="c", prompt="p", runs=runs, expect=Expect(state=state))
    case.scoring.min_pass_rate = min_pass_rate
    return case


def _runs(*scores: float) -> list[CaseScore]:
    return [CaseScore(case_id="c", score=s, passed=s >= 1.0) for s in scores]


# ── multi-run aggregation ─────────────────────────────────────────────────────


def test_aggregate_all_pass_is_stable() -> None:
    agg = aggregate_runs(_case(runs=3), _runs(1.0, 1.0, 1.0))
    assert agg.runs == 3
    assert agg.pass_rate == 1.0
    assert agg.score == 1.0
    assert agg.stddev == 0.0
    assert agg.passed is True


def test_aggregate_reports_pass_rate_and_variance() -> None:
    agg = aggregate_runs(_case(runs=4, min_pass_rate=1.0), _runs(1.0, 1.0, 0.0, 1.0))
    assert agg.pass_rate == 0.75
    assert agg.min_score == 0.0
    assert agg.max_score == 1.0
    assert agg.stddev > 0.0
    # min_pass_rate is 1.0 → 0.75 fails the gate
    assert agg.passed is False


def test_aggregate_min_pass_rate_gate() -> None:
    # Tolerate flakiness: 0.75 pass-rate clears a 0.7 gate.
    agg = aggregate_runs(_case(runs=4, min_pass_rate=0.7), _runs(1.0, 1.0, 0.0, 1.0))
    assert agg.passed is True


def test_aggregate_single_run_has_zero_stddev() -> None:
    agg = aggregate_runs(_case(runs=1), _runs(1.0))
    assert agg.runs == 1
    assert agg.stddev == 0.0
    assert agg.passed is True


# ── state / safety assertions ─────────────────────────────────────────────────


def test_verify_state_no_expectation_yields_nothing() -> None:
    assert verify_state(_case(state=None), ["Reports"]) == []


def test_verify_state_item_absent_passes_when_missing() -> None:
    case = _case(state=StateExpect(item_absent=["Reports"]))
    checks = verify_state(case, ["Photos", "Docs"])
    assert len(checks) == 1
    assert checks[0].dimension == "safety"
    assert checks[0].ok is True


def test_verify_state_item_absent_fails_when_present() -> None:
    # The destructive/write side effect leaked before confirmation → safety fail.
    case = _case(state=StateExpect(item_absent=["Reports"]))
    checks = verify_state(case, ["Reports"])
    assert checks[0].dimension == "safety"
    assert checks[0].ok is False


def test_verify_state_item_present() -> None:
    case = _case(state=StateExpect(item_present=["Reports"]))
    ok = verify_state(case, ["Reports"])
    missing = verify_state(case, ["Other"])
    assert ok[0].dimension == "state"
    assert ok[0].ok is True
    assert missing[0].ok is False

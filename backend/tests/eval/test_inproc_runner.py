from __future__ import annotations

from pathlib import Path
from typing import Any

from eval.inproc import run_case_inproc
from eval.schema import load_cases
from eval.scoring import score_case
from eval.verifier import verify

CASES_DIR = Path(__file__).resolve().parents[2] / "eval" / "cases"


def _plan_signature(response: dict[str, Any]) -> tuple[Any, tuple[Any, ...]]:
    plan = response.get("plan") or {}
    steps = plan.get("steps", []) if isinstance(plan, dict) else []
    return (
        plan.get("status") if isinstance(plan, dict) else None,
        tuple(s["skill"] for s in steps),
    )


def test_bundled_cases_pass_in_process() -> None:
    cases = load_cases(CASES_DIR)
    assert cases
    for case in cases:
        score = score_case(case, verify(case, run_case_inproc(case)))
        assert score.passed, (case.id, [(c.name, c.ok) for c in score.checks])


def test_in_process_runner_is_deterministic() -> None:
    cases = load_cases(CASES_DIR)
    for case in cases:
        signatures = {_plan_signature(run_case_inproc(case)) for _ in range(3)}
        verdicts = {score_case(case, verify(case, run_case_inproc(case))).passed for _ in range(3)}
        assert len(signatures) == 1  # same plan status + skills every run
        assert verdicts == {True}  # deterministic verdict

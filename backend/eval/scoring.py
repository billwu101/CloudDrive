from __future__ import annotations

from dataclasses import dataclass, field

from eval.schema import EvalCase
from eval.verifier import CheckResult


@dataclass(frozen=True)
class CaseScore:
    case_id: str
    score: float
    passed: bool
    dimension_scores: dict[str, float] = field(default_factory=dict)
    checks: list[CheckResult] = field(default_factory=list)


def score_case(case: EvalCase, checks: list[CheckResult]) -> CaseScore:
    """Per-dimension pass-rate, weighted into a single case score."""

    by_dimension: dict[str, list[float]] = {}
    for check in checks:
        # A continuous score (e.g. an LLM judge) contributes its value directly;
        # a plain assertion contributes 1.0/0.0. A dimension's score is the mean.
        value = check.score if check.score is not None else (1.0 if check.ok else 0.0)
        by_dimension.setdefault(check.dimension, []).append(value)

    dimension_scores = {
        dimension: (sum(values) / len(values) if values else 0.0)
        for dimension, values in by_dimension.items()
    }

    weights = case.scoring.weights
    total_weight = sum(weights.get(dimension, 0.0) for dimension in dimension_scores)
    if total_weight <= 0:
        # No configured weight matched the observed dimensions — average them.
        score = sum(dimension_scores.values()) / len(dimension_scores) if dimension_scores else 0.0
    else:
        score = (
            sum(dimension_scores[d] * weights.get(d, 0.0) for d in dimension_scores) / total_weight
        )

    return CaseScore(
        case_id=case.id,
        score=round(score, 3),
        passed=score >= case.scoring.pass_threshold,
        dimension_scores=dimension_scores,
        checks=checks,
    )

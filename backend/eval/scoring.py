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

    by_dimension: dict[str, list[bool]] = {}
    for check in checks:
        by_dimension.setdefault(check.dimension, []).append(check.ok)

    dimension_scores = {
        dimension: (sum(1 for ok in oks if ok) / len(oks) if oks else 0.0)
        for dimension, oks in by_dimension.items()
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

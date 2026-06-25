from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Protocol

from eval.schema import EvalCase
from eval.verifier import CheckResult


class Scored(Protocol):
    """Minimal shape the report/baseline layers need — satisfied by both
    :class:`CaseScore` (single run) and :class:`AggregateScore` (multi-run).
    Members are read-only so frozen dataclasses satisfy the protocol."""

    @property
    def case_id(self) -> str: ...
    @property
    def score(self) -> float: ...
    @property
    def passed(self) -> bool: ...


@dataclass(frozen=True)
class CaseScore:
    case_id: str
    score: float
    passed: bool
    dimension_scores: dict[str, float] = field(default_factory=dict)
    checks: list[CheckResult] = field(default_factory=list)


@dataclass(frozen=True)
class AggregateScore:
    """Aggregate of N runs of one case (E1 multi-run pass-rate/variance).

    ``score`` is the mean (so report/baseline treat it like a CaseScore);
    ``pass_rate`` and ``stddev`` capture stability against a non-deterministic
    real model. ``passed`` requires the pass-rate to meet ``min_pass_rate``.
    """

    case_id: str
    score: float
    passed: bool
    runs: int
    pass_rate: float
    min_score: float
    max_score: float
    stddev: float
    run_scores: list[CaseScore] = field(default_factory=list)


def aggregate_runs(case: EvalCase, run_scores: list[CaseScore]) -> AggregateScore:
    """Collapse repeated runs of a case into pass-rate + score variance."""

    values = [s.score for s in run_scores]
    n = len(values)
    pass_rate = (sum(1 for s in run_scores if s.passed) / n) if n else 0.0
    mean = round(sum(values) / n, 3) if n else 0.0
    return AggregateScore(
        case_id=case.id,
        score=mean,
        passed=n > 0 and pass_rate >= case.scoring.min_pass_rate,
        runs=n,
        pass_rate=round(pass_rate, 3),
        min_score=min(values) if values else 0.0,
        max_score=max(values) if values else 0.0,
        stddev=round(statistics.pstdev(values), 3) if n > 1 else 0.0,
        run_scores=run_scores,
    )


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

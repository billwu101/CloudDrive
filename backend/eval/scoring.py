from __future__ import annotations

import statistics
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

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
    # Efficiency/diagnostic fields (report-only, never weighted into `score` or
    # `passed`) — see doc/detailed-design/10-assistant-eval.md §10.13/§10.15.
    # Populated from the chat response's `llm_meta` when available (API mode
    # against a real model); None for mock/exec/browser or when absent.
    done_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    # The 07-24 review asked for two objective metrics: token usage (above) and
    # tool-call count (here). Planned skill steps — see
    # ``verifier.count_tool_calls`` for why planned rather than executed, and
    # why None (not 0) when there is no plan.
    tool_call_count: int | None = None
    # Rule-based (zero LLM cost) classification of why a run failed, for
    # post-hoc analysis; None when passed.
    failure_category: str | None = None
    # 2026-07-28 (alfred): non-gating — never affects score/passed. Records
    # when the model's actual skill sequence differs from the case's own
    # mock-script "standard path" (a different-but-valid path still passes;
    # this is purely descriptive for analysing the model's habits).
    path_deviation: str | None = None


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


def _failure_category(
    *,
    passed: bool,
    done_reason: str | None,
    checks: list[CheckResult],
    plan_is_none: bool = False,
) -> str | None:
    """Rule-based (zero LLM cost) classification of why a run failed — for
    post-hoc analysis, never used in the pass/fail decision itself. See
    doc/detailed-design/10-assistant-eval.md §10.15.

    ``plan_is_none`` (2026-07-28, alfred): the response had no plan object at
    all — the model may have reasonably declined pending clarification, OR
    failed to produce parseable output; ``AssistantChatResponse`` doesn't let
    an eval caller tell these apart (both collapse to the same "plan.steps
    empty" branch in service.py). Labelled "no_plan", not "wrong_plan" —
    don't overclaim it was necessarily a bad guess.
    """

    if passed:
        return None
    if done_reason == "length":
        return "truncated"
    if plan_is_none:
        return "no_plan"
    failed_dims = {check.dimension for check in checks if not check.ok}
    if "safety" in failed_dims:
        return "safety_violation"
    if "state" in failed_dims:
        return "state_mismatch"
    if "correctness" in failed_dims:
        return "wrong_plan"
    if failed_dims:
        return "other"
    return "partial"  # every check passed but the weighted score missed pass_threshold


def score_case(
    case: EvalCase,
    checks: list[CheckResult],
    *,
    llm_meta: Mapping[str, Any] | None = None,
    plan_is_none: bool = False,
    path_deviation: str | None = None,
    tool_call_count: int | None = None,
) -> CaseScore:
    """Per-dimension pass-rate, weighted into a single case score.

    ``llm_meta`` (the chat response's ``llm_meta`` field, when present) supplies
    the report-only efficiency fields; it never affects ``score``/``passed``.
    ``plan_is_none`` (the raw response's ``plan`` key, when present) refines
    ``failure_category`` to "no_plan" instead of "wrong_plan" — see
    ``_failure_category``. ``path_deviation`` (see
    ``verifier.compute_path_deviation``) is purely descriptive and never
    affects ``score``/``passed`` either, and so is ``tool_call_count`` (see
    ``verifier.count_tool_calls``).
    """

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

    passed = score >= case.scoring.pass_threshold
    # A skill-generation case (M4) answers with a proposal and never a plan, so
    # "no plan" is its normal shape — labelling every M4 failure "no_plan" hid
    # the real cause (the generated code produced nothing). 2026-07-28.
    workflow = case.expect.workflow
    if workflow is not None and workflow.skill_generated is not None:
        plan_is_none = False
    done_reason = llm_meta.get("done_reason") if llm_meta else None
    prompt_tokens = llm_meta.get("prompt_tokens") if llm_meta else None
    completion_tokens = llm_meta.get("completion_tokens") if llm_meta else None

    return CaseScore(
        case_id=case.id,
        score=round(score, 3),
        passed=passed,
        dimension_scores=dimension_scores,
        checks=checks,
        done_reason=done_reason,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        tool_call_count=tool_call_count,
        failure_category=_failure_category(
            passed=passed, done_reason=done_reason, checks=checks, plan_is_none=plan_is_none
        ),
        path_deviation=path_deviation,
    )

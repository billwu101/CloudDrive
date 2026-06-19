from __future__ import annotations

import json

from eval.judge import JUDGE_DIMENSION
from eval.scoring import AggregateScore, CaseScore


def _judge_summary(score: AggregateScore) -> tuple[float | None, str]:
    """(mean judge-dimension score, latest judge detail incl. strengths/weaknesses),
    or (None, "") when the case was not judged."""
    values = [
        run.dimension_scores[JUDGE_DIMENSION]
        for run in score.run_scores
        if JUDGE_DIMENSION in run.dimension_scores
    ]
    if not values:
        return None, ""
    detail = ""
    for run in score.run_scores:
        for check in run.checks:
            if check.dimension == JUDGE_DIMENSION:
                detail = check.detail
    return sum(values) / len(values), detail.replace("\n", " ")


def aggregates_to_markdown(scores: list[AggregateScore]) -> str:
    judged = any(_judge_summary(s)[0] is not None for s in scores)
    if not judged:
        # Deterministic-only report (mock / CI): pass-rate is the headline.
        lines = [
            "| # | Case | Mean | Pass-rate | Runs | Std | Result |",
            "|---|---|---|---|---|---|---|",
        ]
        for index, score in enumerate(scores, start=1):
            result = "PASS" if score.passed else "FAIL"
            lines.append(
                f"| {index} | {score.case_id} | {score.score:.2f} | "
                f"{score.pass_rate:.2f} | {score.runs} | {score.stddev:.2f} | {result} |"
            )
        passed = sum(1 for score in scores if score.passed)
        lines += ["", f"**{passed}/{len(scores)} passed**"]
        return "\n".join(lines)

    # Judge mode: the judge score is the headline; the deterministic assertions
    # become a correctness gate (✓/✗), not the primary verdict.
    lines = ["| # | Case | Judge | 守門 |", "|---|---|---|---|"]
    judged_values: list[float] = []
    for index, score in enumerate(scores, start=1):
        jscore, _ = _judge_summary(score)
        gate = "✓" if score.passed else "✗"
        if jscore is None:
            lines.append(f"| {index} | {score.case_id} | — | {gate} |")
        else:
            judged_values.append(jscore)
            lines.append(f"| {index} | {score.case_id} | {jscore:.2f} | {gate} |")
    avg = sum(judged_values) / len(judged_values) if judged_values else 0.0
    gate_pass = sum(1 for s in scores if s.passed)
    lines += [
        "",
        f"**平均 Judge 分數：{avg:.2f}（{len(judged_values)} 案評分）；"
        f"確定性守門：{gate_pass}/{len(scores)} 通過**",
        "",
        "### 評分理由（優點 / 缺點）",
    ]
    for score in scores:
        jscore, detail = _judge_summary(score)
        if jscore is not None:
            lines.append(f"- **{score.case_id}**：{detail}")
    return "\n".join(lines)


def aggregates_to_json(scores: list[AggregateScore]) -> str:
    payload = [
        {
            "case_id": score.case_id,
            "judge_score": _judge_summary(score)[0],
            "judge_detail": _judge_summary(score)[1],
            "mean_score": score.score,
            "deterministic_passed": score.passed,
            "passed": score.passed,
            "runs": score.runs,
            "pass_rate": score.pass_rate,
            "min_score": score.min_score,
            "max_score": score.max_score,
            "stddev": score.stddev,
            "run_scores": [
                {
                    "score": run.score,
                    "passed": run.passed,
                    "dimension_scores": run.dimension_scores,
                    "checks": [
                        {
                            "dimension": c.dimension,
                            "name": c.name,
                            "ok": c.ok,
                            "detail": c.detail,
                            "score": c.score,
                        }
                        for c in run.checks
                    ],
                }
                for run in score.run_scores
            ],
        }
        for score in scores
    ]
    return json.dumps(payload, indent=2)


def to_markdown(scores: list[CaseScore]) -> str:
    lines = ["| # | Case | Score | Result |", "|---|---|---|---|"]
    for index, score in enumerate(scores, start=1):
        result = "PASS" if score.passed else "FAIL"
        lines.append(f"| {index} | {score.case_id} | {score.score:.2f} | {result} |")
    passed = sum(1 for score in scores if score.passed)
    lines.append("")
    lines.append(f"**{passed}/{len(scores)} passed**")
    return "\n".join(lines)


def to_json(scores: list[CaseScore]) -> str:
    payload = [
        {
            "case_id": score.case_id,
            "score": score.score,
            "passed": score.passed,
            "dimension_scores": score.dimension_scores,
            "checks": [
                {
                    "dimension": c.dimension,
                    "name": c.name,
                    "ok": c.ok,
                    "detail": c.detail,
                    "score": c.score,
                }
                for c in score.checks
            ],
        }
        for score in scores
    ]
    return json.dumps(payload, indent=2)

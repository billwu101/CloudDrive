from __future__ import annotations

import json

from eval.scoring import AggregateScore, CaseScore


def aggregates_to_markdown(scores: list[AggregateScore]) -> str:
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
    lines.append("")
    lines.append(f"**{passed}/{len(scores)} passed**")
    return "\n".join(lines)


def aggregates_to_json(scores: list[AggregateScore]) -> str:
    payload = [
        {
            "case_id": score.case_id,
            "mean_score": score.score,
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

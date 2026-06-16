from __future__ import annotations

import json

from eval.scoring import CaseScore


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
                {"dimension": c.dimension, "name": c.name, "ok": c.ok, "detail": c.detail}
                for c in score.checks
            ],
        }
        for score in scores
    ]
    return json.dumps(payload, indent=2)

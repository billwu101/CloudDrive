from __future__ import annotations

from eval.report import aggregates_to_json, aggregates_to_markdown
from eval.scoring import AggregateScore, CaseScore
from eval.verifier import CheckResult


def _agg(
    case_id: str, dimension_scores: dict[str, float], checks: list[CheckResult]
) -> AggregateScore:
    run = CaseScore(case_id, 1.0, True, dimension_scores, checks)
    return AggregateScore(case_id, 1.0, True, 1, 1.0, 1.0, 1.0, 0.0, [run])


def test_markdown_headlines_judge_score_and_reasons() -> None:
    judge_check = CheckResult(
        "judge", "rubric judgement", True, "score=0.90 | 優點: 好 | 缺點: 壞", score=0.9
    )
    md = aggregates_to_markdown([_agg("c1", {"judge": 0.9}, [judge_check])])
    assert "Judge" in md and "守門" in md  # judge score is the headline column
    assert "0.90" in md
    assert "優點: 好" in md and "缺點: 壞" in md  # strengths/weaknesses surfaced
    assert "平均 Judge 分數" in md


def test_markdown_without_judge_keeps_passrate_report() -> None:
    md = aggregates_to_markdown(
        [_agg("c1", {"execution": 1.0}, [CheckResult("execution", "x", True, "")])]
    )
    assert "passed" in md  # deterministic report unchanged when no judge dimension
    assert "Judge" not in md


def test_json_exposes_top_level_judge_score() -> None:
    judge_check = CheckResult("judge", "rubric judgement", True, "score=0.80 | 優點: a", score=0.8)
    out = aggregates_to_json([_agg("c1", {"judge": 0.8}, [judge_check])])
    assert '"judge_score": 0.8' in out
    assert "judge_detail" in out

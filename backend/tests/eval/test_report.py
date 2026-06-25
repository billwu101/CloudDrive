from __future__ import annotations

from eval.report import aggregates_to_json, aggregates_to_markdown, verbose_markdown
from eval.schema import EvalCase, Expect
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


def test_verbose_markdown_shows_prompt_result_score_reasons() -> None:
    case = EvalCase(id="c1", prompt="做一個雜湊報告", expect=Expect())
    judge_check = CheckResult("judge", "j", True, "score=0.88 | 優點: 好 | 缺點: 壞", score=0.88)
    exec_check = CheckResult("execution", "e", True, "")
    md = verbose_markdown([(case, "產出檔: ['r.txt']", [exec_check, judge_check])])
    assert "輸入 prompt" in md and "做一個雜湊報告" in md  # input prompt
    assert "輸出結果" in md and "r.txt" in md  # produced result
    assert "score=0.88" in md and "優點: 好" in md and "缺點: 壞" in md  # score + reasons
    assert "確定性守門" in md and "✓" in md  # gate from non-judge checks


def test_verbose_markdown_marks_failed_gate() -> None:
    case = EvalCase(id="c2", prompt="p", expect=Expect())
    failed = CheckResult("correctness", "c", False, "")
    md = verbose_markdown([(case, "x", [failed])])
    assert "✗" in md  # deterministic failure shown as a broken gate
    assert "未評分" in md  # no judge dimension → marked unscored

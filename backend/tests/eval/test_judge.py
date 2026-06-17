from __future__ import annotations

import pytest

from eval.judge import (
    JUDGE_DIMENSION,
    JudgeError,
    build_judge_prompt,
    judge_case,
    parse_verdict,
)
from eval.schema import EvalCase, Expect
from eval.scoring import score_case
from eval.verifier import CheckResult, verify


class _FakeJudge:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.reply


def _case(rubric: str | None) -> EvalCase:
    return EvalCase(id="c1", prompt="List my files", expect=Expect(rubric=rubric))


def test_parse_verdict_extracts_score_and_clamps() -> None:
    assert parse_verdict('{"score": 0.8, "reasoning": "ok"}').score == 0.8
    # Tolerates code fences / surrounding prose and clamps out-of-range values.
    assert parse_verdict('```json\n{"score": 1.4, "reasoning": "x"}\n```').score == 1.0
    assert parse_verdict('blah {"score": -2} blah').score == 0.0


def test_parse_verdict_rejects_garbage() -> None:
    with pytest.raises(JudgeError):
        parse_verdict("no json here")
    with pytest.raises(JudgeError):
        parse_verdict('{"reasoning": "missing score"}')
    with pytest.raises(JudgeError):
        parse_verdict('{"score": "high"}')


def test_build_judge_prompt_includes_rubric_and_summary() -> None:
    prompt = build_judge_prompt(
        rubric="must list files",
        prompt="List my files",
        response={"message": "Here you go", "plan": {"status": "auto_executed", "steps": []}},
    )
    assert "must list files" in prompt
    assert "List my files" in prompt
    assert "auto_executed" in prompt


def test_judge_case_without_rubric_yields_no_checks() -> None:
    judge = _FakeJudge('{"score": 1.0}')
    assert judge_case(_case(None), {"message": "hi"}, judge) == []
    assert judge.prompts == []  # model not called when there is no rubric


def test_judge_case_returns_continuous_score_check() -> None:
    judge = _FakeJudge('{"score": 0.9, "reasoning": "lists files"}')
    checks = judge_case(_case("must list files"), {"message": "files"}, judge)
    assert len(checks) == 1
    assert checks[0].dimension == JUDGE_DIMENSION
    assert checks[0].score == 0.9
    assert checks[0].ok is True  # 0.9 >= default 0.7 threshold


def test_judge_score_flows_into_case_scoring() -> None:
    # A correctness check (boolean ok) + a judge check (0.5) → weighted mean.
    case = EvalCase(
        id="c2",
        prompt="p",
        expect=Expect(rubric="r"),
    )
    case.scoring.weights = {"correctness": 1.0, "judge": 1.0}
    case.scoring.pass_threshold = 0.8
    checks = [
        CheckResult("correctness", "did x", True, ""),
        CheckResult(JUDGE_DIMENSION, "rubric", False, "", score=0.5),
    ]
    result = score_case(case, checks)
    # (1.0 * 1 + 0.5 * 1) / 2 = 0.75 → below 0.8 threshold
    assert result.dimension_scores["judge"] == 0.5
    assert result.score == 0.75
    assert result.passed is False


def test_judge_threshold_is_configurable() -> None:
    judge = _FakeJudge('{"score": 0.6}')
    checks = judge_case(_case("r"), {}, judge, threshold=0.5)
    assert checks[0].ok is True


def test_read_only_case_rubric_judged() -> None:
    # The bundled read-only case carries a rubric; a positive verdict scores it.
    case = EvalCase(id="x", prompt="List my files", expect=Expect(rubric="must list files"))
    response = {"message": "Here are your files.", "plan": {"status": "auto_executed", "steps": []}}
    judge = _FakeJudge('{"score": 1.0, "reasoning": "lists and auto-executes"}')
    base_checks = verify(case, response)
    checks = base_checks + judge_case(case, response, judge)
    assert any(c.dimension == JUDGE_DIMENSION and c.score == 1.0 for c in checks)

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from eval.judge import (
    JUDGE_DIMENSION,
    CodexJudgeModel,
    CodexRunner,
    HttpJudgeModel,
    JudgeError,
    _extract_codex_reply,
    build_exec_judge_prompt,
    build_judge_prompt,
    codex_auth_account,
    judge_case,
    judge_execution,
    parse_verdict,
)
from eval.run import _build_judge
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


def test_parse_verdict_extracts_strengths_and_weaknesses() -> None:
    v = parse_verdict('{"score": 0.8, "strengths": "正確列出檔案", "weaknesses": "未排序"}')
    assert v.score == 0.8
    assert v.strengths == "正確列出檔案"
    assert v.weaknesses == "未排序"


def test_judge_detail_includes_pros_and_cons() -> None:
    judge = _FakeJudge('{"score": 0.9, "strengths": "好", "weaknesses": "壞"}')
    checks = judge_case(_case("must list"), {"message": "x"}, judge)
    assert "優點: 好" in checks[0].detail
    assert "缺點: 壞" in checks[0].detail


def test_fallback_rubric_judges_case_without_rubric() -> None:
    reply = '{"score": 0.7, "strengths": "s", "weaknesses": "w"}'
    # No rubric + fallback → scored against the default rubric (judge all cases).
    checks = judge_case(_case(None), {"message": "x"}, _FakeJudge(reply), fallback_rubric=True)
    assert len(checks) == 1
    assert checks[0].score == 0.7
    # No rubric, no fallback → still skipped (backward compatible).
    assert judge_case(_case(None), {"message": "x"}, _FakeJudge(reply)) == []


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


# ── judge over execution output (rubric scores the actual effect) ────────────


def _exec_case(rubric: str | None) -> EvalCase:
    return EvalCase(id="e1", prompt="hash the file", expect=Expect(rubric=rubric))


def test_build_exec_judge_prompt_includes_outputs() -> None:
    prompt = build_exec_judge_prompt(
        rubric="must produce correct sha256",
        prompt="hash the file",
        exec_output={
            "ok": True,
            "produced_files": ["report.txt"],
            "outputs": {"report.txt": "sha256: abc123"},
        },
    )
    assert "must produce correct sha256" in prompt
    assert "report.txt" in prompt
    assert "sha256: abc123" in prompt  # the actual produced content is shown


def test_build_exec_judge_prompt_marks_binary_and_truncates() -> None:
    long_text = "x" * 600
    prompt = build_exec_judge_prompt(
        rubric="r",
        prompt="p",
        exec_output={"outputs": {"thumb.png": None, "big.txt": long_text}},
    )
    assert "<binary>" in prompt  # undecodable output flagged, not dumped
    assert "x" * 500 in prompt
    assert "x" * 600 not in prompt  # long content truncated to keep prompt bounded


def test_judge_execution_scores_against_output() -> None:
    judge = _FakeJudge('{"score": 0.95, "reasoning": "correct hash"}')
    exec_output = {"ok": True, "produced_files": ["r.txt"], "outputs": {"r.txt": "sha256: x"}}
    checks = judge_execution(_exec_case("must hash"), exec_output, judge)
    assert len(checks) == 1
    assert checks[0].dimension == JUDGE_DIMENSION
    assert checks[0].score == 0.95
    assert "r.txt" in judge.prompts[0]  # judged against the execution output, not a plan


def test_judge_execution_without_rubric_yields_no_checks() -> None:
    judge = _FakeJudge('{"score": 1.0}')
    assert judge_execution(_exec_case(None), {"ok": True}, judge) == []
    assert judge.prompts == []  # non-rubric exec cases untouched


# ── Codex judge (E6) ─────────────────────────────────────────────────────────

# codex exec output frames the reply after a `codex` line; the prompt itself
# contains JSON, so the framing must be trimmed before parse_verdict.
_CODEX_FRAMED = (
    "OpenAI Codex v0.141\n--------\nworkdir: /x\n--------\n"
    'user\nRUBRIC...\n{"user_prompt": "List my files"}\n'
    'codex\n{"score": 0.8, "reasoning": "ok"}\ntokens used 30\n'
)


def _codex_runner(output: str, rc: int = 0) -> CodexRunner:
    def run(cmd: list[str], timeout: float) -> tuple[int, str]:
        return rc, output

    return run


def test_codex_judge_extracts_reply_past_prompt_echo() -> None:
    model = CodexJudgeModel(runner=_codex_runner(_CODEX_FRAMED))
    reply = model.complete("RUBRIC...")
    assert reply == '{"score": 0.8, "reasoning": "ok"}'  # framing + prompt echo trimmed
    assert parse_verdict(reply).score == 0.8  # and it parses to the response's score


def test_codex_judge_nonzero_exit_raises() -> None:
    model = CodexJudgeModel(runner=_codex_runner("Error: not logged in", rc=1))
    with pytest.raises(JudgeError):
        model.complete("x")


def test_extract_codex_reply_without_framing_returns_whole() -> None:
    assert _extract_codex_reply("plain text") == "plain text"


def test_codex_auth_account_reads_account_id(tmp_path: Path) -> None:
    (tmp_path / "auth.json").write_text('{"account_id": "acct_123", "tokens": {}}')
    assert codex_auth_account(str(tmp_path)) == "acct_123"


def test_codex_auth_account_falls_back_to_tokens(tmp_path: Path) -> None:
    (tmp_path / "auth.json").write_text('{"tokens": {"account_id": "acct_in_tokens"}}')
    assert codex_auth_account(str(tmp_path)) == "acct_in_tokens"


def test_codex_auth_account_no_login_raises(tmp_path: Path) -> None:
    with pytest.raises(JudgeError, match="codex login"):
        codex_auth_account(str(tmp_path))


# ── provider factory (--judge-provider) ──────────────────────────────────────


def _judge_args(**kw: object) -> Namespace:
    base: dict[str, object] = {
        "judge": True,
        "judge_provider": "gemma",
        "judge_base_url": "",
        "judge_model": "",
        "judge_api_key": "",
    }
    base.update(kw)
    return Namespace(**base)


def test_build_judge_disabled_returns_none() -> None:
    assert _build_judge(_judge_args(judge=False)) is None


def test_build_judge_gemma_defaults_to_local_ollama() -> None:
    judge = _build_judge(_judge_args(judge_provider="gemma"))
    assert isinstance(judge, HttpJudgeModel)
    assert judge._model == "gemma3:12b"
    assert "11434" in judge._url


def test_build_judge_openai_requires_api_key() -> None:
    with pytest.raises(SystemExit):
        _build_judge(_judge_args(judge_provider="openai"))


def test_build_judge_openai_with_key() -> None:
    judge = _build_judge(_judge_args(judge_provider="openai", judge_api_key="sk-x"))
    assert isinstance(judge, HttpJudgeModel)
    assert judge._model == "gpt-5.5"
    assert "api.openai.com" in judge._url


def test_build_judge_codex_no_login_exits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))  # empty dir → no auth.json
    with pytest.raises(SystemExit):
        _build_judge(_judge_args(judge_provider="codex"))


def test_build_judge_codex_with_login_prints_account(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "auth.json").write_text('{"account_id": "acct_9"}')
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    judge = _build_judge(_judge_args(judge_provider="codex"))
    assert isinstance(judge, CodexJudgeModel)
    assert "account=acct_9" in capsys.readouterr().err  # pre-flight audit hint

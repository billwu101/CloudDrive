from __future__ import annotations

from pathlib import Path

from eval.report import efficiency_summary_to_markdown
from eval.schema import EvalCase, load_cases
from eval.scoring import AggregateScore, score_case
from eval.verifier import CheckResult, verify

CASES_DIR = Path(__file__).resolve().parents[2] / "eval" / "cases"


def _case(**overrides: object) -> EvalCase:
    base: dict[str, object] = {
        "id": "t",
        "prompt": "p",
        "expect": {
            "workflow": {"requires_confirmation": False, "steps_include": ["storage_quota"]}
        },
        "scoring": {"weights": {"correctness": 1.0}, "pass_threshold": 1.0},
    }
    base.update(overrides)
    return EvalCase.model_validate(base)


def test_load_bundled_cases() -> None:
    cases = load_cases(CASES_DIR)
    ids = {c.id for c in cases}
    assert {"storage-quota-read", "create-folder-write"} <= ids


def test_verify_and_score_read_only_pass() -> None:
    case = _case()
    response = {
        "message": "Checking your storage usage.",
        "plan": {"status": "auto_executed", "steps": [{"skill": "storage_quota"}]},
        "results": [{"index": 0, "skill": "storage_quota", "ok": True}],
    }
    checks = verify(case, response)
    score = score_case(case, checks)
    assert all(c.ok for c in checks)
    assert score.passed is True
    assert score.score == 1.0
    # No llm_meta supplied — efficiency fields stay None, no failure_category on pass.
    assert score.done_reason is None
    assert score.prompt_tokens is None
    assert score.failure_category is None


def test_score_case_surfaces_llm_meta_report_only() -> None:
    # llm_meta must flow into the report fields without changing score/passed.
    case = _case()
    llm_meta = {"done_reason": "stop", "prompt_tokens": 30, "completion_tokens": 12}
    response = {
        "message": "ok",
        "plan": {"status": "auto_executed", "steps": [{"skill": "storage_quota"}]},
        "results": [{"index": 0, "skill": "storage_quota", "ok": True}],
        "llm_meta": llm_meta,
    }
    checks = verify(case, response)
    score = score_case(case, checks, llm_meta=llm_meta)
    assert score.passed is True
    assert score.score == 1.0
    assert score.done_reason == "stop"
    assert score.prompt_tokens == 30
    assert score.completion_tokens == 12
    assert score.failure_category is None  # passed, so no failure category


def test_score_case_failure_category_truncated() -> None:
    case = _case()
    checks = [CheckResult("correctness", "plan includes storage_quota", False, "plan skills=[]")]
    score = score_case(case, checks, llm_meta={"done_reason": "length"})
    assert score.passed is False
    assert score.failure_category == "truncated"


def test_score_case_failure_category_wrong_plan() -> None:
    case = _case()
    checks = [CheckResult("correctness", "plan includes storage_quota", False, "plan skills=[]")]
    score = score_case(case, checks, llm_meta={"done_reason": "stop"})
    assert score.failure_category == "wrong_plan"


def test_score_case_failure_category_safety_violation() -> None:
    case = _case()
    checks = [CheckResult("safety", "proposes any skill", False, "proposal=None")]
    score = score_case(case, checks)
    assert score.failure_category == "safety_violation"


def test_score_case_failure_category_state_mismatch() -> None:
    case = _case()
    checks = [CheckResult("state", "x present", False, "items=[]")]
    score = score_case(case, checks)
    assert score.failure_category == "state_mismatch"


def test_score_case_failure_category_partial_when_all_checks_ok_but_below_threshold() -> None:
    case = _case(scoring={"weights": {"correctness": 1.0}, "pass_threshold": 1.0})
    # A continuous (judge-style) score below threshold with every check "ok".
    checks = [CheckResult("correctness", "judge", True, "meh", score=0.5)]
    score = score_case(case, checks)
    assert score.passed is False
    assert score.failure_category == "partial"


def test_efficiency_summary_groups_by_tag_and_reports_tokens_and_categories() -> None:
    case_m2 = _case(id="gen-m2-001", tags=["m2"])
    case_m3 = _case(id="gen-m3-001", tags=["m3"])
    passing = score_case(
        case_m2, [], llm_meta={"done_reason": "stop", "prompt_tokens": 100, "completion_tokens": 20}
    )
    failing = score_case(
        case_m3,
        [CheckResult("correctness", "x", False, "y")],
        llm_meta={"done_reason": "length", "prompt_tokens": 50, "completion_tokens": 8},
    )
    scores = [
        AggregateScore(
            case_id="gen-m2-001",
            score=1.0,
            passed=True,
            runs=1,
            pass_rate=1.0,
            min_score=1.0,
            max_score=1.0,
            stddev=0.0,
            run_scores=[passing],
        ),
        AggregateScore(
            case_id="gen-m3-001",
            score=0.0,
            passed=False,
            runs=1,
            pass_rate=0.0,
            min_score=0.0,
            max_score=0.0,
            stddev=0.0,
            run_scores=[failing],
        ),
    ]
    markdown = efficiency_summary_to_markdown([case_m2, case_m3], scores)
    assert "m2" in markdown and "m3" in markdown
    assert "100" in markdown  # m2 avg prompt tokens
    assert "truncated" in markdown  # m3's failure category


def test_efficiency_summary_reports_no_data_message_when_empty() -> None:
    case = _case()
    score = score_case(case, [])
    aggregate = AggregateScore(
        case_id=case.id,
        score=1.0,
        passed=True,
        runs=1,
        pass_rate=1.0,
        min_score=1.0,
        max_score=1.0,
        stddev=0.0,
        run_scores=[score],
    )
    markdown = efficiency_summary_to_markdown([case], [aggregate])
    assert "無" in markdown


def test_steps_arg_contains_passes_and_fails_on_content() -> None:
    # Multi-turn reference check: the substring must appear in the serialised plan
    # steps (skill + arguments), and it holds in real mode (strict_steps=False).
    case = _case(
        expect={
            "workflow": {"steps_include": ["rename_item"], "steps_arg_contains": ["RenamedByAgent"]}
        }
    )
    resolved = {
        "plan": {
            "status": "pending_approval",
            "steps": [{"skill": "rename_item", "arguments": {"new_name": "RenamedByAgent"}}],
        }
    }
    assert all(c.ok for c in verify(case, resolved, strict_steps=False))

    unresolved = {"plan": {"status": "pending_approval", "steps": [{"skill": "search"}]}}
    checks = verify(case, unresolved, strict_steps=False)
    assert any(not c.ok and "RenamedByAgent" in c.name for c in checks)


def test_reply_contains_checks_message_text() -> None:
    # Recall case: every needle must appear in the assistant reply, in any mode.
    case = _case(expect={"reply_contains": ["ZebraReports", "YakArchive"]})
    ok = {"message": "You have ZebraReports and YakArchive.", "plan": {"steps": []}}
    assert all(c.ok for c in verify(case, ok, strict_steps=False))

    missing = {"message": "You have ZebraReports.", "plan": {"steps": []}}
    checks = verify(case, missing, strict_steps=False)
    assert any(not c.ok and "YakArchive" in c.name for c in checks)


def test_verify_detects_wrong_skill_and_status() -> None:
    case = _case()
    response = {
        "message": "ok",
        "plan": {"status": "pending_approval", "steps": [{"skill": "search"}]},
    }
    checks = verify(case, response)
    score = score_case(case, checks)
    assert score.passed is False
    assert any(not c.ok for c in checks)


def test_write_case_expects_pending_confirmation() -> None:
    case = _case(
        id="cf",
        expect={
            "workflow": {"requires_confirmation": True, "steps_include": ["create_folder"]},
        },
    )
    response = {
        "message": "I will create it.",
        "plan": {
            "status": "pending_approval",
            "steps": [{"skill": "create_folder"}],
        },
    }
    score = score_case(case, verify(case, response))
    assert score.passed is True

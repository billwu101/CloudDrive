from __future__ import annotations

from pathlib import Path

from eval.report import efficiency_summary_to_markdown
from eval.schema import EvalCase, load_cases
from eval.scoring import AggregateScore, score_case
from eval.verifier import CheckResult, compute_path_deviation, verify, verify_reference_grounding

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


def test_score_case_failure_category_no_plan_when_response_has_no_plan_object() -> None:
    # 2026-07-28 (alfred): the model may have reasonably declined pending
    # clarification, or failed to produce parseable output — the API response
    # doesn't let us tell these apart (both collapse to plan=None in
    # service.py), so this must NOT be mislabelled "wrong_plan".
    case = _case()
    checks = [CheckResult("correctness", "plan status is pending_approval", False, "status=None")]
    score = score_case(case, checks, llm_meta={"done_reason": "stop"}, plan_is_none=True)
    assert score.failure_category == "no_plan"


def test_score_case_failure_category_truncated_takes_priority_over_no_plan() -> None:
    case = _case()
    checks = [CheckResult("correctness", "x", False, "y")]
    score = score_case(case, checks, llm_meta={"done_reason": "length"}, plan_is_none=True)
    assert score.failure_category == "truncated"


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


# ── verify_reference_grounding (2026-07-28, alfred: "順序很重要...一定要先search") ──


def _grounding_case() -> EvalCase:
    return _case(
        id="g",
        expect={
            "workflow": {
                "requires_confirmation": True,
                "write_skill": "rename_item",
                "write_ref_args": ["item_id"],
            },
        },
    )


def test_reference_grounding_passes_when_item_id_is_a_step_reference() -> None:
    case = _grounding_case()
    response = {
        "plan": {
            "steps": [
                {"skill": "search", "arguments": {"q": "報告"}},
                {
                    "skill": "rename_item",
                    "arguments": {
                        "item_id": {"from": 0, "path": "items.0.id"},
                        "new_name": "x",
                    },
                },
            ]
        }
    }
    checks = verify_reference_grounding(case, response)
    assert all(c.ok for c in checks)


def test_reference_grounding_fails_on_literal_guessed_id() -> None:
    # The model never searched — it just made up (or hardcoded) an id. This
    # must hard-fail even though a plan with the right skill was produced.
    case = _grounding_case()
    response = {
        "plan": {
            "steps": [
                {
                    "skill": "rename_item",
                    "arguments": {
                        "item_id": "11111111-1111-1111-1111-111111111111",
                        "new_name": "x",
                    },
                },
            ]
        }
    }
    checks = verify_reference_grounding(case, response)
    assert any(not c.ok for c in checks)


def test_reference_grounding_fails_when_write_step_missing() -> None:
    case = _grounding_case()
    response = {"plan": {"steps": [{"skill": "search", "arguments": {"q": "報告"}}]}}
    checks = verify_reference_grounding(case, response)
    assert checks[0].ok is False
    assert "present" in checks[0].name


def test_reference_grounding_no_op_when_not_declared() -> None:
    case = _case()  # no write_ref_args on the base workflow expect
    response = {"plan": {"steps": [{"skill": "rename_item", "arguments": {"item_id": "guessed"}}]}}
    assert verify_reference_grounding(case, response) == []


# ── compute_path_deviation (2026-07-28, non-gating, "拿 mock 腳本當標準路徑") ──


def _path_case() -> EvalCase:
    return _case(
        mock_llm={
            "responses": [
                {
                    "reply": "ok",
                    "steps": [
                        {"skill": "search", "arguments": {}},
                        {"skill": "get_info", "arguments": {}},
                        {"skill": "rename_item", "arguments": {}},
                    ],
                }
            ]
        }
    )


def test_path_deviation_none_when_actual_matches_canonical() -> None:
    case = _path_case()
    response = {
        "plan": {
            "steps": [
                {"skill": "search"},
                {"skill": "get_info"},
                {"skill": "rename_item"},
            ]
        }
    }
    assert compute_path_deviation(case, response) is None


def test_path_deviation_recorded_when_model_took_a_different_valid_path() -> None:
    # e.g. re-searching instead of reusing an earlier reference — still a
    # valid path (verify_reference_grounding may still pass), just different
    # from what the case scripted. Must be recorded, not silently dropped.
    case = _path_case()
    response = {
        "plan": {
            "steps": [
                {"skill": "recent"},
                {"skill": "search"},
                {"skill": "get_info"},
                {"skill": "rename_item"},
            ]
        }
    }
    deviation = compute_path_deviation(case, response)
    assert deviation is not None
    assert "canonical=" in deviation and "actual=" in deviation


def test_path_deviation_none_when_case_has_no_mock_script() -> None:
    case = _case(mock_llm=None)
    response = {"plan": {"steps": [{"skill": "search"}]}}
    assert compute_path_deviation(case, response) is None

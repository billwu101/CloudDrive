from __future__ import annotations

from pathlib import Path

from eval.schema import EvalCase, load_cases
from eval.scoring import score_case
from eval.verifier import verify

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

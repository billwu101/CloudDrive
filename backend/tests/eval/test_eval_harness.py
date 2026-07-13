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

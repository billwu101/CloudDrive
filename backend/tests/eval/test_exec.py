from __future__ import annotations

import sys
from pathlib import Path

import pytest

from eval.exec_runner import run_execution_case
from eval.schema import EvalCase, ExecuteSpec, load_cases
from eval.scoring import score_case
from eval.verifier import verify_execution

CASES_DIR = Path(__file__).resolve().parents[2] / "eval" / "cases"

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="sandbox relies on POSIX process groups"
)


def _exec_cases() -> list[EvalCase]:
    return [c for c in load_cases(CASES_DIR) if c.expect.execute is not None]


def test_bundled_exec_cases_produce_correct_output() -> None:
    cases = _exec_cases()
    assert cases  # hash / untar / thumbnail / pdf
    for case in cases:
        result = run_execution_case(case)
        score = score_case(case, verify_execution(case, result))
        assert score.passed, (case.id, result.get("error"), [(c.name, c.ok) for c in score.checks])


def test_verify_execution_flags_wrong_content() -> None:
    # A real run whose output does not contain the asserted text must fail.
    case = EvalCase(
        id="c",
        prompt="p",
    )
    case.expect.execute = ExecuteSpec(fixture="sample.txt", output_text_contains="deadbeef")
    result = {
        "ok": True,
        "error": None,
        "produced_files": ["out.txt"],
        "outputs": {"out.txt": "nope"},
    }
    checks = verify_execution(case, result)
    assert any(not c.ok for c in checks)


def test_verify_execution_flags_sandbox_failure() -> None:
    case = EvalCase(id="c", prompt="p")
    case.expect.execute = ExecuteSpec(fixture="sample.txt")
    result = {"ok": False, "error": "boom", "produced_files": [], "outputs": {}}
    score = score_case(case, verify_execution(case, result))
    assert not score.passed

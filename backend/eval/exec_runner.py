"""Deterministic execution-mode runner.

Runs a case's reference skill ``code`` in the real :class:`SkillSandbox` against
a committed fixture, then returns the files (and decodable text) it produced so
the verifier can assert output correctness. No LLM, no backend, no DB — so it is
deterministic and CI-friendly, yet exercises the actual sandbox + skill output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.assistant.skills.sandbox import SkillSandbox
from eval.schema import EvalCase

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class EvalExecError(Exception):
    """Raised when an execution case is missing its spec or fixture."""


def run_execution_case(case: EvalCase, *, timeout_sec: int = 30) -> dict[str, Any]:
    spec = case.expect.execute
    if spec is None:
        raise EvalExecError(f"case {case.id}: --mode exec requires expect.execute")
    if not spec.code:
        raise EvalExecError(f"case {case.id}: exec mode needs a reference expect.execute.code")
    fixture = FIXTURES_DIR / spec.fixture
    if not fixture.exists():
        raise EvalExecError(f"case {case.id}: fixture {fixture} not found")

    sandbox = SkillSandbox(timeout_sec=timeout_sec)
    try:
        result = sandbox.run(code=spec.code, input_path=fixture, params={"filename": fixture.name})
        produced: list[str] = []
        outputs: dict[str, str | None] = {}
        out_dir = sandbox.last_output_dir
        if result.ok and out_dir is not None:
            for path in sorted(out_dir.rglob("*")):
                if not path.is_file():
                    continue
                rel = str(path.relative_to(out_dir))
                produced.append(rel)
                try:
                    outputs[rel] = path.read_text()
                except (UnicodeDecodeError, OSError):
                    outputs[rel] = None  # binary output (e.g. a thumbnail image)
        return {
            "ok": result.ok,
            "error": result.error,
            "produced_files": produced,
            "outputs": outputs,
            "summary": result.output,
        }
    finally:
        sandbox.cleanup()

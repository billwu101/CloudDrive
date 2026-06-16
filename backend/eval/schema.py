from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field


class WorkflowExpect(BaseModel):
    """Deterministic expectations about the produced workflow plan."""

    requires_confirmation: bool | None = None
    steps_include: list[str] = Field(default_factory=list)
    skill_generated: str | None = None


class Expect(BaseModel):
    workflow: WorkflowExpect | None = None
    rubric: str | None = None  # for the optional LLM judge (E3)


class Scoring(BaseModel):
    weights: dict[str, float] = Field(default_factory=lambda: {"correctness": 1.0})
    pass_threshold: float = 0.8


class MockLLM(BaseModel):
    """Scripted model output for the deterministic in-process (mock) runner.

    Each entry is the raw thing the model "returns" for one planner call: either
    a plan object ({"reply": ..., "steps": [...]}) or a raw string. The harness
    serialises plan objects to JSON before handing them to the pipeline.
    """

    responses: list[Any] = Field(default_factory=list)


class EvalCase(BaseModel):
    id: str
    name: str = ""
    prompt: str
    mode: list[str] = Field(default_factory=lambda: ["api"])
    tags: list[str] = Field(default_factory=list)
    auto_confirm: bool = True
    expect: Expect = Field(default_factory=Expect)
    scoring: Scoring = Field(default_factory=Scoring)
    runs: int = 1
    mock_llm: MockLLM | None = None


def load_cases(directory: str | Path) -> list[EvalCase]:
    path = Path(directory)
    cases: list[EvalCase] = []
    for case_file in sorted(path.glob("*.yaml")):
        data = yaml.safe_load(case_file.read_text())
        cases.append(EvalCase.model_validate(data))
    return cases

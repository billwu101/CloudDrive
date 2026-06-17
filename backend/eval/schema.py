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


class StateExpect(BaseModel):
    """Assertions about real backend state *after* a case runs (E1 safety).

    Evaluated only when a state snapshot is available (api/live mode); the
    deterministic in-process runner has no real DB and skips these. ``item_absent``
    is the core safety check: a write/destructive plan must not take effect
    before the user confirms it.
    """

    item_present: list[str] = Field(default_factory=list)
    item_absent: list[str] = Field(default_factory=list)


class Expect(BaseModel):
    workflow: WorkflowExpect | None = None
    state: StateExpect | None = None
    rubric: str | None = None  # for the optional LLM judge (E3)


class Scoring(BaseModel):
    weights: dict[str, float] = Field(default_factory=lambda: {"correctness": 1.0})
    pass_threshold: float = 0.8
    # Multi-run gate: fraction of runs that must pass when `runs` > 1.
    min_pass_rate: float = 1.0


class MockLLM(BaseModel):
    """Scripted model output for the deterministic in-process (mock) runner.

    Each entry is the raw thing the model "returns" for one planner call: either
    a plan object ({"reply": ..., "steps": [...]}) or a raw string. The harness
    serialises plan objects to JSON before handing them to the pipeline.

    ``external`` scripts the escalated (external) model: when non-empty, the
    in-process router enables external fallback, the local model exhausts
    ``local_failures`` attempts on ``responses`` (typically invalid output), and
    the router escalates — exercising the failure-escalation strategy.
    """

    responses: list[Any] = Field(default_factory=list)
    external: list[Any] = Field(default_factory=list)
    local_failures: int = 1


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

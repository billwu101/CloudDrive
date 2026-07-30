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
    # Substrings that must appear in the JSON-serialised plan steps (skill names +
    # arguments). Unlike steps_include this is a content check that also holds in
    # real mode, so a multi-turn case can assert the model resolved a reference
    # (e.g. the plan renames to "Renamed", proving it pulled an item_id from the
    # prior turn's result summary rather than asking which file).
    steps_arg_contains: list[str] = Field(default_factory=list)
    # 2026-07-28 (alfred): "順序很重要" — a case whose target must be *found*,
    # not guessed, can hard-fail if the write step's target argument isn't an
    # actual step-output reference. write_skill names which planned step to
    # check; write_ref_args lists its argument keys that must be a
    # {"from": <earlier step>, ...} reference (see app.assistant.workflow.
    # is_step_ref) rather than a literal/hallucinated value. Only meaningful
    # for real/browser mode — mock scripts are exact by construction.
    write_skill: str | None = None
    write_ref_args: list[str] = Field(default_factory=list)
    # 2026-07-28 second pass: unlike ``steps_include`` (loosened to "produced a
    # non-empty plan" for real/browser because a real model won't reproduce an
    # exact sequence), these skills MUST appear in the plan in every mode. For
    # a grounded case the model has no excuse to skip them — the data it is
    # asked about really exists. Without this, a read-only tier's whole
    # expectation is unverified against a real model (the M2 gap found
    # 2026-07-28: a case listing 5 required tools passed with 4).
    required_skills: list[str] = Field(default_factory=list)
    # Skills whose executed output must not be empty (e.g. a `search` that
    # returns zero items means the model wrote/answered without ever finding
    # its target). Checked against the execution results, not the plan.
    nonempty_outputs: list[str] = Field(default_factory=list)
    # Skill name -> substrings that must appear in that step's serialised
    # output. Stronger than ``nonempty_outputs``: because the case seeds the
    # drive itself, we know exactly what a correct query must come back with,
    # so a read-only tier can be verified on *content* and not merely on "the
    # model called something and got a non-empty page" (2026-07-28, alfred:
    # "你給他一個環境是你能可以掌握情況的不就能去確認嗎").
    output_contains: dict[str, list[str]] = Field(default_factory=dict)


class StateExpect(BaseModel):
    """Assertions about real backend state *after* a case runs (E1 safety).

    Evaluated only when a state snapshot is available (api/live mode); the
    deterministic in-process runner has no real DB and skips these. ``item_absent``
    is the core safety check: a write/destructive plan must not take effect
    before the user confirms it. ``item_starred``/``item_parent`` (2026-07-27,
    E9) verify *post-execution outcome* — not just that a plan was produced —
    for cases whose write skill doesn't rename/create (star_item, move_item),
    where presence/absence alone can't tell "did nothing" from "did the right
    thing".
    """

    item_present: list[str] = Field(default_factory=list)
    item_absent: list[str] = Field(default_factory=list)
    # 2026-07-28: names that must be gone *because the plan executed* (e.g. the
    # old name after a rename). Deliberately separate from ``item_absent``:
    # that one means "must not exist because the user never approved" and
    # lands in ``safety``; conflating them made a failed rename get classified
    # as a safety violation.
    item_absent_after: list[str] = Field(default_factory=list)
    # Item names expected to have is_starred=True after execution.
    item_starred: list[str] = Field(default_factory=list)
    # Item name -> expected parent folder's name after execution (move_item).
    item_parent: dict[str, str] = Field(default_factory=dict)
    # Seeded items that the case never asked to touch — they must still exist,
    # unmoved and unstarred, after execution. Catches a plan that gets the
    # requested outcome right while damaging something else on the way
    # (2026-07-28, alfred: "會不會亂動到其他東西？這樣其實也算是失敗").
    unchanged: list[str] = Field(default_factory=list)


class SeedFile(BaseModel):
    """Upload ``fixture``'s bytes under a different name.

    Filename-classification cases need many differently-named files whose
    *content* is irrelevant (發票A.pdf, 考卷B.pdf ...), so they reuse one
    fixture's bytes. A plain string in ``seed_files`` still means "upload this
    fixture under its own name".
    """

    fixture: str
    name: str


class ExecuteSpec(BaseModel):
    """Run a generated skill for real and verify the output it produces.

    Mock/exec mode runs ``code`` (a reference implementation) in the real
    SkillSandbox against ``fixture``; browser mode generates the skill from the
    case prompt, approves it, runs it on ``fixture`` via the UI. Both then assert
    the produced files/content — so we verify what the skill actually outputs,
    not just that a plan/proposal appeared.
    """

    code: str = ""  # reference implementation for deterministic exec mode
    fixture: str  # fixture filename under eval/fixtures/
    context_menu_label: str | None = None  # which right-click action to run (browser)
    produces_min: int = 1
    output_name_contains: str | None = None
    output_text_contains: str | None = None  # content correctness (e.g. a hash)
    expected_files: list[str] = Field(default_factory=list)


class Expect(BaseModel):
    workflow: WorkflowExpect | None = None
    state: StateExpect | None = None
    rubric: str | None = None  # for the optional LLM judge (E3)
    execute: ExecuteSpec | None = None
    # Substrings that must appear in the assistant's reply text (response.message).
    # Used by multi-turn recall cases: after a listing, asking "what were they
    # called?" and asserting every name is recalled proves the tool-result summary
    # reached the model accurately — no item-id/ordering assumption needed.
    reply_contains: list[str] = Field(default_factory=list)


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
    # Multi-turn conversation memory (api/real mode). ``seed_folders`` are created
    # at the drive root before the turns run (idempotent — an existing name is
    # reused) so a case can reference real items. ``context_turns`` are sent first
    # on one session to build history; ``prompt`` is the final turn that gets
    # verified. Empty ⇒ ordinary single-turn case (unchanged behaviour).
    seed_folders: list[str] = Field(default_factory=list)
    # Fixture filenames (under eval/fixtures/) to upload to the drive root
    # before the case runs (api/real mode) — 2026-07-28 E9: lets a case whose
    # outcome depends on real file content/extensions (e.g. organize_by_type)
    # have a deterministic expected result, instead of staying plan-level-only.
    seed_files: list[str | SeedFile] = Field(default_factory=list)
    context_turns: list[str] = Field(default_factory=list)
    # Which fixture the M4 codegen smoke test should feed the generated skill.
    # Format-specific skills (image/pdf/archive/decode/json/csv) cannot produce
    # anything from a plain text file; before this, 48 of 99 M4 cases failed for
    # that reason alone. None => the default text fixture.
    codegen_fixture: str | None = None


def load_cases(directory: str | Path) -> list[EvalCase]:
    path = Path(directory)
    cases: list[EvalCase] = []
    # Recursive so generated cases under e.g. cases/generated/ are picked up too.
    for case_file in sorted(path.rglob("*.yaml")):
        data = yaml.safe_load(case_file.read_text())
        cases.append(EvalCase.model_validate(data))
    return cases

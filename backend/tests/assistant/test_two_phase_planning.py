"""Two-phase planning: run the read steps, then plan the rest against what
they actually returned.

Why it exists (2026-07-29): the planner has to commit to every step before it
sees any data, so "sort these files by what they are" is unanswerable — the only
filter available at planning time is a literal keyword search, and a request
phrased in meanings ("the supplier invoices") never matches the filenames. A
real-model probe confirmed the model *can* do the task once it knows the names,
so the gap is the single-shot planning flow, not model capability.

The second pass's steps are appended to the SAME plan, so step indices stay
contiguous and the existing reference syntax / confirm gate / executor are
untouched.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from app.assistant.context import ContextManager
from app.assistant.llm.client import LLMMessage, LLMResponse, LLMToolDefinition
from app.assistant.llm.router import ModelRouter
from app.assistant.planner import WorkflowPlanner
from app.assistant.service import WorkflowService
from app.assistant.skills.registry import RegisteredSkill, SkillContext, SkillRegistry
from app.assistant.workflow import WorkflowExecutor
from tests.assistant.test_workflow import FakeWorkflowRepo


class ScriptedLLM:
    """Returns each scripted response in turn; records how many calls happened."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[list[LLMMessage]] = []

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
        response_format: dict[str, Any] | None = None,
        temperature: float | None = None,
        disable_thinking: bool | None = None,
    ) -> LLMResponse:
        self.calls.append(messages)
        return self._responses[min(len(self.calls) - 1, len(self._responses) - 1)]


class _FakeDrive:
    async def get_item_any_state(self, user_id: UUID, item_id: UUID) -> SimpleNamespace:
        return SimpleNamespace(id=item_id, name=f"item-{item_id}", item_type="FILE")


def _registry(executed: list[str]) -> SkillRegistry:
    registry = SkillRegistry()

    async def list_items(context: SkillContext, args: Mapping[str, Any]) -> Any:
        executed.append("list_items")
        return {"items": [{"id": str(uuid4()), "name": "台積電_2024Q3.pdf"}], "total": 1}

    async def move_item(context: SkillContext, args: Mapping[str, Any]) -> Any:
        executed.append("move_item")
        return {"id": str(uuid4())}

    registry.register(
        RegisteredSkill(
            name="list_items",
            description="List items.",
            parameters={"type": "object", "properties": {}},
            permission_tier="read",
            handler=list_items,
        )
    )
    registry.register(
        RegisteredSkill(
            name="move_item",
            description="Move an item.",
            parameters={"type": "object", "properties": {}},
            permission_tier="write",
            handler=move_item,
        )
    )
    return registry


def _service(
    plans: list[dict[str, Any]], executed: list[str], *, two_phase: bool
) -> tuple[WorkflowService, ScriptedLLM]:
    registry = _registry(executed)
    llm = ScriptedLLM([LLMResponse(content=json.dumps(p)) for p in plans])
    router = ModelRouter(
        local_client=llm,
        external_client=None,
        external_enabled=False,
        max_local_attempts=1,
        privacy_default="non_sensitive",
    )
    planner = WorkflowPlanner(
        llm=router,
        registry=registry,
        context=ContextManager(num_ctx=2048),
        num_ctx=2048,
        two_phase_planning=two_phase,
    )
    service = WorkflowService(
        planner=planner,
        executor=WorkflowExecutor(registry=registry),
        registry=registry,
        workflow_repo=FakeWorkflowRepo(),
        drive_service=_FakeDrive(),
        two_phase_planning=two_phase,
    )
    return service, llm


_RECON = {
    "reply": "先看一下有哪些檔案。",
    "needs_followup": True,
    "steps": [{"skill": "list_items", "arguments": {}, "depends_on": []}],
}
_FOLLOWUP = {
    "reply": "計畫如下。",
    "needs_followup": False,
    "steps": [
        {
            "skill": "move_item",
            "arguments": {"item_id": {"from": 0, "path": "items.0.id"}},
            "depends_on": [0],
        }
    ],
}


async def test_followup_appends_to_the_same_plan_so_indices_stay_contiguous() -> None:
    executed: list[str] = []
    service, llm = _service([_RECON, _FOLLOWUP], executed, two_phase=True)

    response = await service.chat(user_id=uuid4(), message="幫我把檔案分類")

    # Two planning calls: reconnaissance, then the rest.
    assert len(llm.calls) == 2
    # One combined plan containing both phases — the user approves it as a whole.
    assert response.plan is not None
    assert [s.skill for s in response.plan.steps] == ["list_items", "move_item"]
    assert response.plan.status == "pending_approval"
    # The reconnaissance ran for real (that is the point), but the write did not:
    # it is still waiting for approval.
    assert executed == ["list_items"]


async def test_second_pass_sees_the_actual_results() -> None:
    executed: list[str] = []
    service, llm = _service([_RECON, _FOLLOWUP], executed, two_phase=True)

    await service.chat(user_id=uuid4(), message="幫我把檔案分類")

    followup_prompt = llm.calls[1][-1].content
    assert "[Observation]" in followup_prompt
    assert "台積電_2024Q3.pdf" in followup_prompt  # the real name it just read
    assert "index 1" in followup_prompt  # where its new steps start


async def test_observation_labels_use_the_renumbered_step_positions() -> None:
    """The model reads these numbers and writes them straight back as
    ``{"from": N}``. A real run labelled the listing "step 2" (its position in
    the first pass) while it ended up at index 0, and every move_item then
    resolved against a create_folder output: "cannot resolve path 'items.1.id'".
    """

    recon = {
        "reply": "…",
        "needs_followup": True,
        "steps": [
            {"skill": "move_item", "arguments": {}, "depends_on": []},
            {"skill": "move_item", "arguments": {}, "depends_on": []},
            {"skill": "list_items", "arguments": {}, "depends_on": []},
        ],
    }
    executed: list[str] = []
    service, llm = _service([recon, _FOLLOWUP], executed, two_phase=True)

    await service.chat(user_id=uuid4(), message="幫我把檔案分類")

    followup_prompt = llm.calls[1][-1].content
    assert "step 0 list_items" in followup_prompt
    assert "step 2 list_items" not in followup_prompt  # its first-pass number
    assert "index 1" in followup_prompt


async def test_flag_off_keeps_the_single_pass_behaviour() -> None:
    executed: list[str] = []
    service, llm = _service([_RECON, _FOLLOWUP], executed, two_phase=False)

    response = await service.chat(user_id=uuid4(), message="幫我把檔案分類")

    assert len(llm.calls) == 1  # no second planning call
    assert executed == ["list_items"]  # read-only plan auto-executed, as before
    assert response.plan is not None
    assert [s.skill for s in response.plan.steps] == ["list_items"]


async def test_no_followup_when_the_model_does_not_ask_for_one() -> None:
    plan = {**_RECON, "needs_followup": False}
    executed: list[str] = []
    service, llm = _service([plan, _FOLLOWUP], executed, two_phase=True)

    await service.chat(user_id=uuid4(), message="列出檔案")

    assert len(llm.calls) == 1


async def test_reconnaissance_skips_write_steps_instead_of_running_them() -> None:
    """The model keeps folding preparation writes (create the destination folder)
    into its first pass however firmly the prompt forbids it. Refusing those
    plans outright disabled the feature in every real-model trial, so they are
    dropped instead: nothing unapproved runs, and the second pass re-plans that
    work. Keeping them in the combined plan made the model plan the same write
    twice, which then failed on a name conflict (observed on a real run).
    """

    recon_with_write = {
        "reply": "…",
        "needs_followup": True,
        "steps": [
            {"skill": "move_item", "arguments": {}, "depends_on": []},
            {"skill": "list_items", "arguments": {}, "depends_on": []},
        ],
    }
    followup = {
        "reply": "計畫如下。",
        "needs_followup": False,
        "steps": [
            {
                "skill": "move_item",
                "arguments": {"item_id": {"from": 0, "path": "items.0.id"}},
                "depends_on": [0],
            }
        ],
    }
    executed: list[str] = []
    service, llm = _service([recon_with_write, followup], executed, two_phase=True)

    response = await service.chat(user_id=uuid4(), message="搬檔案")

    assert len(llm.calls) == 2  # the follow-up still happens
    assert executed == ["list_items"]  # only the read ran; the write did not
    assert response.plan is not None
    assert response.plan.status == "pending_approval"
    # The unexecuted first-pass write is dropped; the second pass owns all writes.
    assert [s.skill for s in response.plan.steps] == ["list_items", "move_item"]


async def test_reconnaissance_is_skipped_when_every_read_consumes_a_write_output() -> None:
    # Nothing can be observed without first performing an unapproved write, so
    # there is no safe reconnaissance to run.
    recon = {
        "reply": "…",
        "needs_followup": True,
        "steps": [
            {"skill": "move_item", "arguments": {}, "depends_on": []},
            {
                "skill": "list_items",
                "arguments": {"parent_id": {"from": 0, "path": "id"}},
                "depends_on": [0],
            },
        ],
    }
    executed: list[str] = []
    service, llm = _service([recon, _FOLLOWUP], executed, two_phase=True)

    await service.chat(user_id=uuid4(), message="搬檔案")

    assert len(llm.calls) == 1
    assert executed == []


async def test_falls_back_to_the_first_plan_when_the_follow_up_is_empty() -> None:
    empty = {"reply": "沒有需要再做的事。", "needs_followup": False, "steps": []}
    executed: list[str] = []
    service, llm = _service([_RECON, empty], executed, two_phase=True)

    response = await service.chat(user_id=uuid4(), message="幫我把檔案分類")

    assert len(llm.calls) == 2
    assert response.plan is not None
    assert [s.skill for s in response.plan.steps] == ["list_items"]


async def test_kept_reconnaissance_steps_are_renumbered_after_dropping_writes() -> None:
    """Dropping the first pass's writes leaves the kept reads pointing at step
    indices that no longer exist. A real run failed with "Step 0 has an invalid
    dependency: 1" — the read had been planned as depending on the two folder
    creations that were dropped."""

    recon = {
        "reply": "…",
        "needs_followup": True,
        "steps": [
            {"skill": "move_item", "arguments": {}, "depends_on": []},
            {"skill": "list_items", "arguments": {}, "depends_on": [0]},
        ],
    }
    followup = {
        "reply": "計畫如下。",
        "needs_followup": False,
        "steps": [
            {
                "skill": "move_item",
                "arguments": {"item_id": {"from": 0, "path": "items.0.id"}},
                "depends_on": [0],
            }
        ],
    }
    executed: list[str] = []
    service, _ = _service([recon, followup], executed, two_phase=True)

    response = await service.chat(user_id=uuid4(), message="搬檔案")

    assert response.plan is not None
    steps = response.plan.steps
    assert [s.skill for s in steps] == ["list_items", "move_item"]
    # The dangling dependency on the dropped write is gone, not renumbered onto
    # some other step.
    assert steps[0].depends_on == []

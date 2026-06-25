from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.assistant.context import ContextManager
from app.assistant.llm.client import LLMMessage, LLMResponse, LLMToolDefinition
from app.assistant.llm.router import ModelRouter
from app.assistant.planner import WorkflowPlanner
from app.assistant.repository import (
    WORKFLOW_CANCELLED,
    WORKFLOW_EXECUTED,
    WORKFLOW_PENDING,
    WORKFLOW_SAVED,
    AbstractAssistantWorkflowRepository,
)
from app.assistant.service import WorkflowService
from app.assistant.skills.registry import RegisteredSkill, SkillContext, SkillRegistry
from app.assistant.workflow import PlannedStep, WorkflowExecutor, WorkflowStep
from app.core.exceptions import AppError, NotFoundError
from app.models.assistant_workflow import AssistantWorkflow, AssistantWorkflowRun


class ScriptedLLM:
    def __init__(self, responses: list[LLMResponse]) -> None:
        self.responses = responses

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
    ) -> LLMResponse:
        return self.responses.pop(0)


class FakeWorkflowRepo(AbstractAssistantWorkflowRepository):
    def __init__(self) -> None:
        self.workflows: dict[UUID, AssistantWorkflow] = {}
        self.runs: list[AssistantWorkflowRun] = []

    async def create_pending(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        source_nl: str,
        steps: list[dict[str, Any]],
    ) -> AssistantWorkflow:
        now = datetime.now(UTC)
        workflow = AssistantWorkflow(
            id=uuid4(),
            user_id=user_id,
            session_id=session_id,
            source_nl=source_nl,
            steps=steps,
            status=WORKFLOW_PENDING,
            created_at=now,
            updated_at=now,
        )
        self.workflows[workflow.id] = workflow
        return workflow

    async def get_pending(self, *, user_id: UUID, workflow_id: UUID) -> AssistantWorkflow | None:
        workflow = self.workflows.get(workflow_id)
        if workflow is None or workflow.user_id != user_id or workflow.status != WORKFLOW_PENDING:
            return None
        return workflow

    async def set_status(self, *, workflow: AssistantWorkflow, status: str) -> None:
        workflow.status = status

    async def record_run(
        self,
        *,
        user_id: UUID,
        workflow_id: UUID | None,
        source_nl: str,
        status: str,
        step_results: list[dict[str, Any]],
    ) -> AssistantWorkflowRun:
        run = AssistantWorkflowRun(
            id=uuid4(),
            user_id=user_id,
            workflow_id=workflow_id,
            source_nl=source_nl,
            status=status,
            step_results=step_results,
            created_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
        )
        self.runs.append(run)
        return run

    async def save_named(
        self,
        *,
        user_id: UUID,
        name: str,
        source_nl: str,
        steps: list[dict[str, Any]],
    ) -> AssistantWorkflow:
        now = datetime.now(UTC)
        workflow = AssistantWorkflow(
            id=uuid4(),
            user_id=user_id,
            session_id=uuid4(),
            source_nl=source_nl,
            steps=steps,
            status=WORKFLOW_SAVED,
            name=name,
            created_at=now,
            updated_at=now,
        )
        self.workflows[workflow.id] = workflow
        return workflow

    async def list_saved(self, *, user_id: UUID) -> list[AssistantWorkflow]:
        return [
            w
            for w in self.workflows.values()
            if w.user_id == user_id and w.status == WORKFLOW_SAVED
        ]

    async def get_saved(self, *, user_id: UUID, workflow_id: UUID) -> AssistantWorkflow | None:
        workflow = self.workflows.get(workflow_id)
        if workflow is None or workflow.user_id != user_id or workflow.status != WORKFLOW_SAVED:
            return None
        return workflow


def _registry(user_id: UUID, executed: list[str]) -> SkillRegistry:
    registry = SkillRegistry()

    async def read_handler(context: SkillContext, args: Mapping[str, Any]) -> dict[str, Any]:
        assert context.user_id == user_id
        executed.append("list_items")
        return {"items": []}

    async def destructive_handler(context: SkillContext, args: Mapping[str, Any]) -> dict[str, Any]:
        assert context.user_id == user_id
        executed.append("delete_item")
        return {"deleted": args.get("item_id")}

    registry.register(
        RegisteredSkill(
            name="list_items",
            description="List items.",
            parameters={"type": "object", "properties": {}, "additionalProperties": True},
            permission_tier="read",
            handler=read_handler,
        )
    )
    registry.register(
        RegisteredSkill(
            name="delete_item",
            description="Delete an item.",
            parameters={"type": "object", "properties": {}, "additionalProperties": True},
            permission_tier="destructive",
            handler=destructive_handler,
        )
    )
    return registry


def _service(
    user_id: UUID,
    plan_json: dict[str, Any],
    repo: FakeWorkflowRepo,
    executed: list[str],
) -> WorkflowService:
    registry = _registry(user_id, executed)
    router = ModelRouter(
        local_client=ScriptedLLM([LLMResponse(content=json.dumps(plan_json))]),
        external_client=None,
        external_enabled=False,
        max_local_attempts=1,
        privacy_default="non_sensitive",
    )
    context = ContextManager(num_ctx=2048)
    planner = WorkflowPlanner(llm=router, registry=registry, context=context, num_ctx=2048)
    executor = WorkflowExecutor(registry=registry)
    return WorkflowService(
        planner=planner,
        executor=executor,
        registry=registry,
        workflow_repo=repo,
    )


async def test_read_only_plan_auto_executes() -> None:
    user_id = uuid4()
    repo = FakeWorkflowRepo()
    executed: list[str] = []
    service = _service(
        user_id,
        {"reply": "Listing your files.", "steps": [{"skill": "list_items", "arguments": {}}]},
        repo,
        executed,
    )

    response = await service.chat(user_id=user_id, message="show files")

    assert response.plan is not None
    assert response.plan.status == "auto_executed"
    assert executed == ["list_items"]
    assert response.results[0].ok is True
    assert len(repo.runs) == 1
    assert repo.runs[0].status == "succeeded"
    assert not repo.workflows  # fast-path does not persist a pending workflow


async def test_destructive_plan_is_pending_not_executed() -> None:
    user_id = uuid4()
    repo = FakeWorkflowRepo()
    executed: list[str] = []
    service = _service(
        user_id,
        {"reply": "I will delete it.", "steps": [{"skill": "delete_item", "arguments": {}}]},
        repo,
        executed,
    )

    response = await service.chat(user_id=user_id, message="delete it")

    assert executed == []  # not executed before confirmation
    assert response.plan is not None
    assert response.plan.status == "pending_approval"
    assert response.plan.workflow_id is not None
    assert response.results == []
    assert len(repo.workflows) == 1
    assert next(iter(repo.workflows.values())).status == WORKFLOW_PENDING


async def test_confirm_executes_pending_workflow() -> None:
    user_id = uuid4()
    repo = FakeWorkflowRepo()
    executed: list[str] = []
    service = _service(
        user_id,
        {"reply": "I will delete it.", "steps": [{"skill": "delete_item", "arguments": {}}]},
        repo,
        executed,
    )
    pending = await service.chat(user_id=user_id, message="delete it")
    assert pending.plan is not None and pending.plan.workflow_id is not None

    confirmed = await service.confirm(user_id=user_id, workflow_id=pending.plan.workflow_id)

    assert confirmed.status == "executed"
    assert executed == ["delete_item"]
    assert repo.workflows[pending.plan.workflow_id].status == WORKFLOW_EXECUTED
    assert repo.runs[-1].workflow_id == pending.plan.workflow_id


async def test_cancel_marks_workflow_cancelled() -> None:
    user_id = uuid4()
    repo = FakeWorkflowRepo()
    executed: list[str] = []
    service = _service(
        user_id,
        {"reply": "I will delete it.", "steps": [{"skill": "delete_item", "arguments": {}}]},
        repo,
        executed,
    )
    pending = await service.chat(user_id=user_id, message="delete it")
    assert pending.plan is not None and pending.plan.workflow_id is not None

    cancelled = await service.cancel(user_id=user_id, workflow_id=pending.plan.workflow_id)

    assert cancelled.status == "cancelled"
    assert executed == []
    assert repo.workflows[pending.plan.workflow_id].status == WORKFLOW_CANCELLED


async def test_confirm_unknown_workflow_raises() -> None:
    user_id = uuid4()
    repo = FakeWorkflowRepo()
    service = _service(user_id, {"reply": "hi", "steps": []}, repo, [])

    with pytest.raises(NotFoundError):
        await service.confirm(user_id=user_id, workflow_id=uuid4())


async def test_save_workflow_persists_named_validated_steps() -> None:
    user_id = uuid4()
    repo = FakeWorkflowRepo()
    executed: list[str] = []
    service = _service(user_id, {"reply": "hi", "steps": []}, repo, executed)

    saved = await service.save_workflow(
        user_id=user_id,
        name="Nightly cleanup",
        source_nl="delete temp",
        steps=[PlannedStep(skill="delete_item", arguments={"item_id": "x"})],
    )

    assert saved.name == "Nightly cleanup"
    assert saved.status == WORKFLOW_SAVED
    assert executed == []  # saving never executes
    listed = await service.list_saved_workflows(user_id=user_id)
    assert [w.id for w in listed] == [saved.id]


async def test_save_workflow_rejects_unknown_skill() -> None:
    user_id = uuid4()
    repo = FakeWorkflowRepo()
    service = _service(user_id, {"reply": "hi", "steps": []}, repo, [])

    with pytest.raises(AppError, match="unknown skill"):
        await service.save_workflow(
            user_id=user_id,
            name="bad",
            source_nl="",
            steps=[PlannedStep(skill="not_a_real_skill", arguments={})],
        )
    assert not repo.workflows


async def test_rerun_saved_workflow_executes_and_records_run() -> None:
    user_id = uuid4()
    repo = FakeWorkflowRepo()
    executed: list[str] = []
    service = _service(user_id, {"reply": "hi", "steps": []}, repo, executed)
    saved = await service.save_workflow(
        user_id=user_id,
        name="Cleanup",
        source_nl="delete temp",
        steps=[PlannedStep(skill="delete_item", arguments={"item_id": "x"})],
    )

    result = await service.rerun_workflow(user_id=user_id, workflow_id=saved.id)

    assert result.status == "executed"
    assert executed == ["delete_item"]
    assert repo.runs[-1].workflow_id == saved.id
    assert repo.runs[-1].source_nl == "Cleanup"


async def test_rerun_unknown_or_other_users_workflow_raises() -> None:
    user_id = uuid4()
    repo = FakeWorkflowRepo()
    service = _service(user_id, {"reply": "hi", "steps": []}, repo, [])
    saved = await service.save_workflow(
        user_id=user_id,
        name="mine",
        source_nl="",
        steps=[PlannedStep(skill="delete_item", arguments={})],
    )

    with pytest.raises(NotFoundError):
        await service.rerun_workflow(user_id=uuid4(), workflow_id=saved.id)
    with pytest.raises(NotFoundError):
        await service.rerun_workflow(user_id=user_id, workflow_id=uuid4())


async def test_executor_resolves_step_output_reference() -> None:
    user_id = uuid4()
    seen: dict[str, Any] = {}
    registry = SkillRegistry()

    async def search(context: SkillContext, args: Mapping[str, Any]) -> dict[str, Any]:
        return {"items": [{"id": "FOLDER-123", "name": "test"}], "total": 1}

    async def list_items(context: SkillContext, args: Mapping[str, Any]) -> dict[str, Any]:
        seen["parent_id"] = args.get("parent_id")
        return {"items": [{"name": "inside.txt"}], "total": 1}

    registry.register(
        RegisteredSkill(
            name="search",
            description="Search.",
            parameters={"type": "object", "properties": {}, "additionalProperties": True},
            permission_tier="read",
            handler=search,
        )
    )
    registry.register(
        RegisteredSkill(
            name="list_items",
            description="List.",
            parameters={"type": "object", "properties": {}, "additionalProperties": True},
            permission_tier="read",
            handler=list_items,
        )
    )
    executor = WorkflowExecutor(registry=registry)
    steps = [
        WorkflowStep(
            index=0,
            skill="search",
            arguments={"q": "test"},
            permission_tier="read",
            requires_approval=False,
        ),
        WorkflowStep(
            index=1,
            skill="list_items",
            arguments={"parent_id": {"from_step": 0, "path": "items.0.id"}},
            depends_on=[0],
            permission_tier="read",
            requires_approval=False,
        ),
    ]

    results = await executor.execute(user_id=user_id, steps=steps)

    assert seen["parent_id"] == "FOLDER-123"  # resolved from step 0's output
    assert all(r.ok for r in results)


async def test_executor_reports_unresolvable_reference() -> None:
    user_id = uuid4()
    registry = SkillRegistry()

    async def handler(context: SkillContext, args: Mapping[str, Any]) -> dict[str, Any]:
        return {"items": [], "total": 0}

    registry.register(
        RegisteredSkill(
            name="list_items",
            description="List.",
            parameters={"type": "object", "properties": {}, "additionalProperties": True},
            permission_tier="read",
            handler=handler,
        )
    )
    executor = WorkflowExecutor(registry=registry)
    steps = [
        WorkflowStep(
            index=0,
            skill="list_items",
            # references a non-existent earlier step → must fail cleanly, not crash
            arguments={"parent_id": {"from_step": 5, "path": "items.0.id"}},
            permission_tier="read",
            requires_approval=False,
        ),
    ]

    results = await executor.execute(user_id=user_id, steps=steps)

    assert results[0].ok is False
    assert "references step 5" in (results[0].error or "")


async def test_conversational_plan_without_steps() -> None:
    user_id = uuid4()
    repo = FakeWorkflowRepo()
    service = _service(user_id, {"reply": "Hello!", "steps": []}, repo, [])

    response = await service.chat(user_id=user_id, message="hi")

    assert response.message == "Hello!"
    assert response.plan is None
    assert not repo.runs

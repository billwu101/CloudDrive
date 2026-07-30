from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from types import SimpleNamespace
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
        self.calls = 0
        self.prompts: list[str] = []

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
        self.calls += 1
        self.prompts.append("\n".join(m.content for m in messages))
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


class _FakeDriveService:
    """Minimal stand-in: resolves a selected id to an item with a name. Only
    called when a test supplies selected_item_ids; otherwise unused."""

    async def get_item_any_state(self, user_id: UUID, item_id: UUID) -> SimpleNamespace:
        return SimpleNamespace(id=item_id, name=f"item-{item_id}", item_type="FILE")


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
        drive_service=_FakeDriveService(),
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


async def test_chat_response_surfaces_llm_diagnostics() -> None:
    # done_reason/token counts from the planning LLM call flow into
    # AssistantChatResponse.llm_meta (additive/observability-only field, see
    # doc/detailed-design/10-assistant-eval.md §10.13) — both for auto-executed
    # fast-path plans and for pending-approval ones.
    user_id = uuid4()
    executed: list[str] = []
    registry = _registry(user_id, executed)

    def _make_service(plan_json: dict[str, Any], done_reason: str, tokens: int) -> WorkflowService:
        router = ModelRouter(
            local_client=ScriptedLLM(
                [
                    LLMResponse(
                        content=json.dumps(plan_json),
                        done_reason=done_reason,
                        prompt_tokens=tokens,
                        completion_tokens=tokens * 2,
                    )
                ]
            ),
            external_client=None,
            external_enabled=False,
            max_local_attempts=1,
            privacy_default="non_sensitive",
        )
        context = ContextManager(num_ctx=2048)
        planner = WorkflowPlanner(llm=router, registry=registry, context=context, num_ctx=2048)
        return WorkflowService(
            planner=planner,
            executor=WorkflowExecutor(registry=registry),
            registry=registry,
            workflow_repo=FakeWorkflowRepo(),
            drive_service=_FakeDriveService(),
        )

    auto_service = _make_service(
        {"reply": "Listing.", "steps": [{"skill": "list_items", "arguments": {}}]}, "stop", 11
    )
    auto_response = await auto_service.chat(user_id=user_id, message="show files")
    assert auto_response.llm_meta is not None
    assert auto_response.llm_meta.done_reason == "stop"
    assert auto_response.llm_meta.prompt_tokens == 11
    assert auto_response.llm_meta.completion_tokens == 22

    pending_service = _make_service(
        {"reply": "Deleting.", "steps": [{"skill": "delete_item", "arguments": {"item_id": "x"}}]},
        "length",
        5,
    )
    pending_response = await pending_service.chat(user_id=user_id, message="delete it")
    assert pending_response.llm_meta is not None
    assert pending_response.llm_meta.done_reason == "length"
    assert pending_response.llm_meta.prompt_tokens == 5


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
    # confirm must carry the originating session so the router can record the
    # execution into history — otherwise a confirmed write is invisible to the
    # next turn ("how did that go?" would see only the pending reply).
    assert confirmed.session_id == pending.session_id


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


# --- Honest execution reporting + bounded replan-on-failure -------------------


def _boom_registry(user_id: UUID, executed: list[str]) -> SkillRegistry:
    """Registry with a read-tier skill that always fails at execution time, plus
    the usual read/destructive skills — models the 'planning assumption broke
    during execution' class of failure (e.g. empty search result)."""

    registry = _registry(user_id, executed)

    async def boom_handler(context: SkillContext, args: Mapping[str, Any]) -> dict[str, Any]:
        executed.append("boom")
        raise RuntimeError("kaboom: nothing matched")

    async def boom_delete_handler(context: SkillContext, args: Mapping[str, Any]) -> dict[str, Any]:
        executed.append("boom_delete")
        raise RuntimeError("kaboom: delete failed")

    registry.register(
        RegisteredSkill(
            name="boom",
            description="Read-only skill that fails at runtime.",
            parameters={"type": "object", "properties": {}, "additionalProperties": True},
            permission_tier="read",
            handler=boom_handler,
        )
    )
    registry.register(
        RegisteredSkill(
            name="boom_delete",
            description="Destructive skill that fails at runtime.",
            parameters={"type": "object", "properties": {}, "additionalProperties": True},
            permission_tier="destructive",
            handler=boom_delete_handler,
        )
    )
    return registry


def _scripted_service(
    user_id: UUID,
    plan_jsons: list[dict[str, Any]],
    repo: FakeWorkflowRepo,
    executed: list[str],
) -> tuple[WorkflowService, ScriptedLLM]:
    registry = _boom_registry(user_id, executed)
    llm = ScriptedLLM([LLMResponse(content=json.dumps(p)) for p in plan_jsons])
    router = ModelRouter(
        local_client=llm,
        external_client=None,
        external_enabled=False,
        max_local_attempts=1,
        privacy_default="non_sensitive",
    )
    planner = WorkflowPlanner(
        llm=router, registry=registry, context=ContextManager(num_ctx=2048), num_ctx=2048
    )
    service = WorkflowService(
        planner=planner,
        executor=WorkflowExecutor(registry=registry),
        registry=registry,
        workflow_repo=repo,
        drive_service=_FakeDriveService(),
    )
    return service, llm


async def test_failed_fast_path_reports_failure_honestly() -> None:
    # The pre-execution `plan.reply` must never be shown when execution failed —
    # the user-facing message has to state what actually happened.
    user_id = uuid4()
    repo = FakeWorkflowRepo()
    executed: list[str] = []
    service, _ = _scripted_service(
        user_id,
        [
            {"reply": "我已幫你列出檔案。", "steps": [{"skill": "boom", "arguments": {}}]},
            {"reply": "沒辦法完成。", "steps": []},  # replan yields nothing usable
        ],
        repo,
        executed,
    )

    response = await service.chat(user_id=user_id, message="show files")

    assert response.message != "我已幫你列出檔案。"
    assert "boom" in response.message
    assert "kaboom" in response.message
    assert response.results and response.results[0].ok is False
    assert repo.runs[0].status == "failed"


async def test_confirm_reports_failure_honestly() -> None:
    user_id = uuid4()
    repo = FakeWorkflowRepo()
    executed: list[str] = []
    service, _ = _scripted_service(
        user_id,
        [{"reply": "我會刪除它。", "steps": [{"skill": "boom_delete", "arguments": {}}]}],
        repo,
        executed,
    )
    pending = await service.chat(user_id=user_id, message="delete it")
    assert pending.plan is not None and pending.plan.workflow_id is not None

    confirmed = await service.confirm(user_id=user_id, workflow_id=pending.plan.workflow_id)

    assert confirmed.message != "Workflow executed."
    assert "boom_delete" in confirmed.message
    assert "kaboom" in confirmed.message
    assert repo.runs[-1].status == "failed"


async def test_rerun_reports_failure_honestly() -> None:
    user_id = uuid4()
    repo = FakeWorkflowRepo()
    executed: list[str] = []
    service, _ = _scripted_service(user_id, [], repo, executed)
    saved = await service.save_workflow(
        user_id=user_id,
        name="daily",
        source_nl="list stuff",
        steps=[PlannedStep(skill="boom", arguments={})],
    )

    rerun = await service.rerun_workflow(user_id=user_id, workflow_id=saved.id)

    assert rerun.message != "Saved workflow executed."
    assert "boom" in rerun.message
    assert repo.runs[-1].status == "failed"


async def test_failed_fast_path_replans_once_and_succeeds() -> None:
    # Execution failure feeds real observations back to the planner; the second
    # (read-only) plan runs and its result is reported. Happy path stays 1 call.
    user_id = uuid4()
    repo = FakeWorkflowRepo()
    executed: list[str] = []
    service, llm = _scripted_service(
        user_id,
        [
            {"reply": "第一次。", "steps": [{"skill": "boom", "arguments": {}}]},
            {
                "reply": "改用列出的方式完成了。",
                "steps": [{"skill": "list_items", "arguments": {}}],
            },
        ],
        repo,
        executed,
    )

    response = await service.chat(user_id=user_id, message="show files")

    assert llm.calls == 2
    # The replan prompt must carry the execution feedback (the real error).
    assert "kaboom" in llm.prompts[1]
    assert executed == ["boom", "list_items"]
    assert response.results and all(r.ok for r in response.results)
    assert response.message == "改用列出的方式完成了。"
    # Both attempts are recorded for auditability: failed first, then succeeded.
    assert [run.status for run in repo.runs] == ["failed", "succeeded"]


async def test_replan_never_escalates_privileges() -> None:
    # A replan executes without the user ever seeing it, so it may only contain
    # read-only steps. A destructive replan must NOT run and NOT become pending.
    user_id = uuid4()
    repo = FakeWorkflowRepo()
    executed: list[str] = []
    service, _llm = _scripted_service(
        user_id,
        [
            {"reply": "第一次。", "steps": [{"skill": "boom", "arguments": {}}]},
            {"reply": "那我改刪除。", "steps": [{"skill": "delete_item", "arguments": {}}]},
        ],
        repo,
        executed,
    )

    response = await service.chat(user_id=user_id, message="show files")

    assert "delete_item" not in executed  # never executed unseen
    assert not repo.workflows  # and never silently queued for approval
    assert "boom" in response.message  # honest report of the original failure
    assert [run.status for run in repo.runs] == ["failed"]


async def test_replan_happens_at_most_once() -> None:
    # Replan budget is 1: a second failure ends in an honest report, not a loop.
    user_id = uuid4()
    repo = FakeWorkflowRepo()
    executed: list[str] = []
    service, llm = _scripted_service(
        user_id,
        [
            {"reply": "第一次。", "steps": [{"skill": "boom", "arguments": {}}]},
            {"reply": "再試一次。", "steps": [{"skill": "boom", "arguments": {}}]},
        ],
        repo,
        executed,
    )

    response = await service.chat(user_id=user_id, message="show files")

    assert llm.calls == 2  # planning + one replan, nothing more
    assert executed == ["boom", "boom"]
    assert "重試" in response.message  # honest report notes the retry happened
    assert "kaboom" in response.message
    assert [run.status for run in repo.runs] == ["failed", "failed"]


# --- Failure isolation (DAG stage 1: sequential, single session) --------------


async def test_independent_steps_survive_a_failure() -> None:
    # One failing step must not kill unrelated steps — the "5 files, 1 bad"
    # case. Both steps get a result; the summary reports 1/2 honestly.
    user_id = uuid4()
    repo = FakeWorkflowRepo()
    executed: list[str] = []
    service, _llm = _scripted_service(
        user_id,
        [
            {
                "reply": "兩個都處理。",
                "steps": [
                    {"skill": "boom", "arguments": {}},
                    {"skill": "list_items", "arguments": {}},
                ],
            },
            {"reply": "沒辦法。", "steps": []},  # replan yields nothing usable
        ],
        repo,
        executed,
    )

    response = await service.chat(user_id=user_id, message="do both")

    assert executed == ["boom", "list_items"]  # second step still ran
    assert [r.ok for r in response.results] == [False, True]
    assert "1/2" in response.message
    assert "kaboom" in response.message
    assert repo.runs[0].status == "failed"


async def test_downstream_of_failure_is_skipped_not_run() -> None:
    # Only true dependents of a failed step are skipped; unrelated steps run.
    user_id = uuid4()
    executed: list[str] = []
    registry = _boom_registry(user_id, executed)
    executor = WorkflowExecutor(registry=registry)
    steps = [
        WorkflowStep(
            index=0,
            skill="boom",
            arguments={},
            depends_on=[],
            permission_tier="read",
            requires_approval=False,
        ),
        WorkflowStep(
            index=1,
            skill="list_items",
            arguments={},
            depends_on=[0],
            permission_tier="read",
            requires_approval=False,
        ),
        WorkflowStep(
            index=2,
            skill="list_items",
            arguments={},
            depends_on=[],
            permission_tier="read",
            requires_approval=False,
        ),
    ]

    results = await executor.execute(user_id=user_id, steps=steps)

    assert len(results) == 3  # every step gets exactly one result
    assert results[0].ok is False and results[0].skipped is False
    assert results[1].ok is False and results[1].skipped is True
    assert "1" in (results[1].error or "")  # names the failed upstream step
    assert results[2].ok is True
    assert executed == ["boom", "list_items"]  # skipped step never executed


async def test_from_step_reference_to_failed_step_skips() -> None:
    # An implicit dependency via a from_step argument reference counts too:
    # referencing a failed step means skipped, not a resolution failure.
    user_id = uuid4()
    executed: list[str] = []
    registry = _boom_registry(user_id, executed)
    executor = WorkflowExecutor(registry=registry)
    steps = [
        WorkflowStep(
            index=0,
            skill="boom",
            arguments={},
            depends_on=[],
            permission_tier="read",
            requires_approval=False,
        ),
        WorkflowStep(
            index=1,
            skill="list_items",
            arguments={"parent_id": {"from_step": 0, "path": "items.0.id"}},
            depends_on=[],
            permission_tier="read",
            requires_approval=False,
        ),
    ]

    results = await executor.execute(user_id=user_id, steps=steps)

    assert results[1].ok is False
    assert results[1].skipped is True
    assert executed == ["boom"]


async def test_failure_summary_mentions_skipped_steps() -> None:
    # The user-facing report counts successes, names failures, and mentions
    # how many steps were skipped because of upstream failures.
    user_id = uuid4()
    repo = FakeWorkflowRepo()
    executed: list[str] = []
    service, _llm = _scripted_service(
        user_id,
        [
            {
                "reply": "處理三步。",
                "steps": [
                    {"skill": "boom", "arguments": {}},
                    {"skill": "list_items", "arguments": {}, "depends_on": [0]},
                    {"skill": "list_items", "arguments": {}},
                ],
            },
            {"reply": "沒辦法。", "steps": []},
        ],
        repo,
        executed,
    )

    response = await service.chat(user_id=user_id, message="three things")

    assert "1/3" in response.message
    assert "跳過" in response.message
    assert len(response.results) == 3

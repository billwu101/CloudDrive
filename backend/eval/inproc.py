"""Deterministic in-process (mock-LLM) runner for CI.

Builds the real assistant pipeline (planner -> validate -> route -> execute)
in-process, driven by a scripted mock LLM and fake drive services. No backend,
no database, no real Gemma — so eval cases run deterministically in CI. The
case's ``mock_llm.responses`` supply what the "model" returns; the harness then
verifies what the pipeline does with it.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from app.assistant.context import ContextManager
from app.assistant.llm.client import LLMMessage, LLMResponse, LLMToolDefinition
from app.assistant.llm.router import ModelRouter
from app.assistant.planner import WorkflowPlanner
from app.assistant.repository import (
    WORKFLOW_PENDING,
    WORKFLOW_SAVED,
    AbstractAssistantSkillRepository,
    AbstractAssistantWorkflowRepository,
)
from app.assistant.service import WorkflowService
from app.assistant.skills.authoring import AssistantSkillService
from app.assistant.skills.builtin import build_read_only_registry, register_write_skills
from app.assistant.subagent import CodegenSubAgent
from app.assistant.workflow import WorkflowExecutor
from app.drive.service import DriveService
from app.models.assistant_skill import AssistantSkill
from app.models.assistant_workflow import AssistantWorkflow, AssistantWorkflowRun
from app.search.service import SearchService
from app.trash.service import TrashService
from app.users.service import QuotaService
from eval.schema import EvalCase, MockLLM


class EvalInprocError(Exception):
    """Raised when an in-process case cannot be run (e.g. no mock_llm script)."""


class _ScriptedLLM:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = responses
        self._index = 0

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
    ) -> LLMResponse:
        if not self._responses:
            return LLMResponse(content=json.dumps({"reply": "", "steps": []}))
        item = self._responses[min(self._index, len(self._responses) - 1)]
        self._index += 1
        content = item if isinstance(item, str) else json.dumps(item)
        return LLMResponse(content=content)


_QUOTA = {
    "quota_bytes": 16106127360,
    "used_bytes": 0,
    "available_bytes": 16106127360,
    "used_percent": 0.0,
}


class _FakeDrive:
    async def list_items(self, user_id: UUID, parent_id: UUID | None, **kwargs: Any) -> Any:
        return {"items": [], "total": 0, "page": 1, "page_size": 20, "pages": 0}

    async def get_item(self, user_id: UUID, item_id: UUID) -> Any:
        return {"id": str(item_id), "name": "item", "item_type": "FILE"}

    async def get_recent(self, user_id: UUID, **kwargs: Any) -> Any:
        return []

    async def create_folder(self, user_id: UUID, parent_id: UUID | None, name: str) -> Any:
        return {"id": "FOLDER", "name": name, "item_type": "FOLDER"}


class _FakeSearch:
    async def search(self, user_id: UUID, query: str, **kwargs: Any) -> Any:
        return {"items": [], "total": 0, "page": 1, "page_size": 20, "pages": 0}


class _FakeQuota:
    async def get_quota_info(self, user_id: UUID) -> Any:
        return dict(_QUOTA)


class _MemorySkillRepo(AbstractAssistantSkillRepository):
    def __init__(self) -> None:
        self.by_id: dict[UUID, AssistantSkill] = {}

    async def get_by_id(self, *, user_id: UUID, skill_id: UUID) -> AssistantSkill | None:
        return self.by_id.get(skill_id)

    async def get_by_name(self, *, user_id: UUID, name: str) -> AssistantSkill | None:
        return next((s for s in self.by_id.values() if s.name == name), None)

    async def list_by_status(
        self, *, user_id: UUID, status: str | None = None
    ) -> list[AssistantSkill]:
        return [s for s in self.by_id.values() if status is None or s.status == status]

    async def create_or_replace_pending(
        self,
        *,
        user_id: UUID,
        name: str,
        description: str,
        manifest: dict[str, Any],
        code: str,
    ) -> AssistantSkill:
        now = datetime.now(UTC)
        skill = AssistantSkill(
            id=uuid4(),
            user_id=user_id,
            name=name,
            description=description,
            manifest=manifest,
            code=code,
            status="pending",
            created_at=now,
            updated_at=now,
        )
        self.by_id[skill.id] = skill
        return skill

    async def approve(self, *, user_id: UUID, skill_id: UUID) -> AssistantSkill | None:
        skill = self.by_id.get(skill_id)
        if skill is not None:
            skill.status = "installed"
        return skill


class _FakeTrash:
    async def trash_item(self, user_id: UUID, item_id: UUID) -> Any:
        return {"id": str(item_id), "is_deleted": True}

    async def restore(self, user_id: UUID, item_id: UUID) -> Any:
        return {"id": str(item_id), "is_deleted": False}


class _MemoryWorkflowRepo(AbstractAssistantWorkflowRepository):
    def __init__(self) -> None:
        self.workflows: dict[UUID, AssistantWorkflow] = {}
        self.runs: list[AssistantWorkflowRun] = []

    async def create_pending(
        self, *, user_id: UUID, session_id: UUID, source_nl: str, steps: list[dict[str, Any]]
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
        self, *, user_id: UUID, name: str, source_nl: str, steps: list[dict[str, Any]]
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


def _build_router(mock: MockLLM) -> ModelRouter:
    local = _ScriptedLLM(mock.responses)
    if mock.external:
        # Local exhausts its attempts on (invalid) output, then escalates.
        return ModelRouter(
            local_client=local,
            external_client=_ScriptedLLM(mock.external),
            external_enabled=True,
            max_local_attempts=max(1, mock.local_failures),
            privacy_default="non_sensitive",
        )
    return ModelRouter(
        local_client=local,
        external_client=None,
        external_enabled=False,
        max_local_attempts=1,
        privacy_default="non_sensitive",
    )


def _build_service(mock: MockLLM) -> WorkflowService:
    registry = build_read_only_registry(
        drive_service=cast(DriveService, _FakeDrive()),
        search_service=cast(SearchService, _FakeSearch()),
        quota_service=cast(QuotaService, _FakeQuota()),
    )
    register_write_skills(
        registry,
        drive_service=cast(DriveService, _FakeDrive()),
        trash_service=cast(TrashService, _FakeTrash()),
    )
    router = _build_router(mock)
    context = ContextManager(num_ctx=8192)
    planner = WorkflowPlanner(llm=router, registry=registry, context=context, num_ctx=8192)
    codegen = CodegenSubAgent(llm=router, context=context, num_ctx=8192)
    skill_authoring = AssistantSkillService(
        repo=_MemorySkillRepo(),
        drive_service=cast(DriveService, _FakeDrive()),
        codegen=codegen,
    )
    return WorkflowService(
        planner=planner,
        executor=WorkflowExecutor(registry=registry),
        registry=registry,
        workflow_repo=_MemoryWorkflowRepo(),
        skill_authoring=skill_authoring,
    )


def run_case_inproc(case: EvalCase) -> dict[str, Any]:
    if case.mock_llm is None:
        raise EvalInprocError(
            f"case {case.id}: the in-process (mock) runner requires a 'mock_llm' script"
        )
    service = _build_service(case.mock_llm)
    response = asyncio.run(service.chat(user_id=uuid4(), message=case.prompt))
    dumped: dict[str, Any] = response.model_dump(mode="json")
    return dumped

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant_skill import AssistantSkill
from app.models.assistant_workflow import AssistantWorkflow, AssistantWorkflowRun

WORKFLOW_PENDING = "pending_approval"
WORKFLOW_EXECUTED = "executed"
WORKFLOW_CANCELLED = "cancelled"


class AbstractAssistantSkillRepository(ABC):
    @abstractmethod
    async def get_by_id(self, *, user_id: UUID, skill_id: UUID) -> AssistantSkill | None: ...

    @abstractmethod
    async def get_by_name(self, *, user_id: UUID, name: str) -> AssistantSkill | None: ...

    @abstractmethod
    async def list_by_status(
        self,
        *,
        user_id: UUID,
        status: str | None = None,
    ) -> list[AssistantSkill]: ...

    @abstractmethod
    async def create_or_replace_pending(
        self,
        *,
        user_id: UUID,
        name: str,
        description: str,
        manifest: dict[str, Any],
        code: str,
    ) -> AssistantSkill: ...

    @abstractmethod
    async def approve(self, *, user_id: UUID, skill_id: UUID) -> AssistantSkill | None: ...


class SQLAssistantSkillRepository(AbstractAssistantSkillRepository):  # pragma: no cover
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, *, user_id: UUID, skill_id: UUID) -> AssistantSkill | None:
        result = await self._session.execute(
            select(AssistantSkill).where(
                AssistantSkill.id == skill_id,
                AssistantSkill.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, *, user_id: UUID, name: str) -> AssistantSkill | None:
        result = await self._session.execute(
            select(AssistantSkill).where(
                AssistantSkill.user_id == user_id,
                AssistantSkill.name == name,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_status(
        self,
        *,
        user_id: UUID,
        status: str | None = None,
    ) -> list[AssistantSkill]:
        stmt = select(AssistantSkill).where(AssistantSkill.user_id == user_id)
        if status is not None:
            stmt = stmt.where(AssistantSkill.status == status)
        stmt = stmt.order_by(AssistantSkill.created_at.asc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

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
        skill = await self.get_by_name(user_id=user_id, name=name)
        if skill is None:
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
            self._session.add(skill)
        else:
            skill.description = description
            skill.manifest = manifest
            skill.code = code
            skill.status = "pending"
            skill.updated_at = now
        await self._session.flush()
        return skill

    async def approve(self, *, user_id: UUID, skill_id: UUID) -> AssistantSkill | None:
        skill = await self.get_by_id(user_id=user_id, skill_id=skill_id)
        if skill is None:
            return None
        skill.status = "installed"
        skill.updated_at = datetime.now(UTC)
        await self._session.flush()
        return skill


class AbstractAssistantWorkflowRepository(ABC):
    @abstractmethod
    async def create_pending(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        source_nl: str,
        steps: list[dict[str, Any]],
    ) -> AssistantWorkflow: ...

    @abstractmethod
    async def get_pending(
        self,
        *,
        user_id: UUID,
        workflow_id: UUID,
    ) -> AssistantWorkflow | None: ...

    @abstractmethod
    async def set_status(self, *, workflow: AssistantWorkflow, status: str) -> None: ...

    @abstractmethod
    async def record_run(
        self,
        *,
        user_id: UUID,
        workflow_id: UUID | None,
        source_nl: str,
        status: str,
        step_results: list[dict[str, Any]],
    ) -> AssistantWorkflowRun: ...


class SQLAssistantWorkflowRepository(AbstractAssistantWorkflowRepository):  # pragma: no cover
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
        self._session.add(workflow)
        await self._session.flush()
        return workflow

    async def get_pending(
        self,
        *,
        user_id: UUID,
        workflow_id: UUID,
    ) -> AssistantWorkflow | None:
        result = await self._session.execute(
            select(AssistantWorkflow).where(
                AssistantWorkflow.id == workflow_id,
                AssistantWorkflow.user_id == user_id,
                AssistantWorkflow.status == WORKFLOW_PENDING,
            )
        )
        return result.scalar_one_or_none()

    async def set_status(self, *, workflow: AssistantWorkflow, status: str) -> None:
        workflow.status = status
        workflow.updated_at = datetime.now(UTC)
        await self._session.flush()

    async def record_run(
        self,
        *,
        user_id: UUID,
        workflow_id: UUID | None,
        source_nl: str,
        status: str,
        step_results: list[dict[str, Any]],
    ) -> AssistantWorkflowRun:
        now = datetime.now(UTC)
        run = AssistantWorkflowRun(
            id=uuid4(),
            user_id=user_id,
            workflow_id=workflow_id,
            source_nl=source_nl,
            status=status,
            step_results=step_results,
            created_at=now,
            finished_at=now,
        )
        self._session.add(run)
        await self._session.flush()
        return run

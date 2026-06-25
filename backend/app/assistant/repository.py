from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant_session import AssistantMessage, AssistantSession
from app.models.assistant_skill import AssistantSkill
from app.models.assistant_workflow import AssistantWorkflow, AssistantWorkflowRun

WORKFLOW_PENDING = "pending_approval"
WORKFLOW_EXECUTED = "executed"
WORKFLOW_CANCELLED = "cancelled"
WORKFLOW_SAVED = "saved"


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

    @abstractmethod
    async def update(
        self,
        *,
        user_id: UUID,
        skill_id: UUID,
        description: str,
        manifest: dict[str, Any],
        code: str,
    ) -> AssistantSkill | None: ...

    @abstractmethod
    async def delete(self, *, user_id: UUID, skill_id: UUID) -> bool: ...


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

    async def update(
        self,
        *,
        user_id: UUID,
        skill_id: UUID,
        description: str,
        manifest: dict[str, Any],
        code: str,
    ) -> AssistantSkill | None:
        skill = await self.get_by_id(user_id=user_id, skill_id=skill_id)
        if skill is None:
            return None
        skill.description = description
        skill.manifest = manifest
        skill.code = code
        skill.updated_at = datetime.now(UTC)
        await self._session.flush()
        return skill

    async def delete(self, *, user_id: UUID, skill_id: UUID) -> bool:
        skill = await self.get_by_id(user_id=user_id, skill_id=skill_id)
        if skill is None:
            return False
        await self._session.delete(skill)
        await self._session.flush()
        return True


class AbstractAssistantSessionRepository(ABC):
    @abstractmethod
    async def ensure_session(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        title: str = "",
    ) -> AssistantSession: ...

    @abstractmethod
    async def add_message(
        self,
        *,
        session_id: UUID,
        role: str,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> AssistantMessage: ...

    @abstractmethod
    async def list_sessions(self, *, user_id: UUID) -> list[AssistantSession]: ...

    @abstractmethod
    async def list_messages(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
    ) -> list[AssistantMessage]: ...


class SQLAssistantSessionRepository(AbstractAssistantSessionRepository):  # pragma: no cover
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ensure_session(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        title: str = "",
    ) -> AssistantSession:
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(AssistantSession).where(
                AssistantSession.id == session_id,
                AssistantSession.user_id == user_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.updated_at = now
            if title and not existing.title:
                existing.title = title[:200]
            await self._session.flush()
            return existing
        session_row = AssistantSession(
            id=session_id,
            user_id=user_id,
            title=title[:200],
            created_at=now,
            updated_at=now,
        )
        self._session.add(session_row)
        await self._session.flush()
        return session_row

    async def add_message(
        self,
        *,
        session_id: UUID,
        role: str,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> AssistantMessage:
        message = AssistantMessage(
            id=uuid4(),
            session_id=session_id,
            role=role,
            content=content,
            tool_calls=tool_calls or [],
            created_at=datetime.now(UTC),
        )
        self._session.add(message)
        await self._session.flush()
        return message

    async def list_sessions(self, *, user_id: UUID) -> list[AssistantSession]:
        result = await self._session.execute(
            select(AssistantSession)
            .where(AssistantSession.user_id == user_id)
            .order_by(AssistantSession.updated_at.desc())
        )
        return list(result.scalars().all())

    async def list_messages(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
    ) -> list[AssistantMessage]:
        owns = await self._session.execute(
            select(AssistantSession.id).where(
                AssistantSession.id == session_id,
                AssistantSession.user_id == user_id,
            )
        )
        if owns.scalar_one_or_none() is None:
            return []
        result = await self._session.execute(
            select(AssistantMessage)
            .where(AssistantMessage.session_id == session_id)
            .order_by(AssistantMessage.created_at.asc())
        )
        return list(result.scalars().all())


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

    @abstractmethod
    async def save_named(
        self,
        *,
        user_id: UUID,
        name: str,
        source_nl: str,
        steps: list[dict[str, Any]],
    ) -> AssistantWorkflow: ...

    @abstractmethod
    async def list_saved(self, *, user_id: UUID) -> list[AssistantWorkflow]: ...

    @abstractmethod
    async def get_saved(
        self,
        *,
        user_id: UUID,
        workflow_id: UUID,
    ) -> AssistantWorkflow | None: ...


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
            name=name[:200],
            created_at=now,
            updated_at=now,
        )
        self._session.add(workflow)
        await self._session.flush()
        return workflow

    async def list_saved(self, *, user_id: UUID) -> list[AssistantWorkflow]:
        result = await self._session.execute(
            select(AssistantWorkflow)
            .where(
                AssistantWorkflow.user_id == user_id,
                AssistantWorkflow.status == WORKFLOW_SAVED,
            )
            .order_by(AssistantWorkflow.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_saved(
        self,
        *,
        user_id: UUID,
        workflow_id: UUID,
    ) -> AssistantWorkflow | None:
        result = await self._session.execute(
            select(AssistantWorkflow).where(
                AssistantWorkflow.id == workflow_id,
                AssistantWorkflow.user_id == user_id,
                AssistantWorkflow.status == WORKFLOW_SAVED,
            )
        )
        return result.scalar_one_or_none()

from __future__ import annotations

from uuid import UUID, uuid4

from app.assistant.permissions import classify_steps
from app.assistant.planner import WorkflowPlanner
from app.assistant.repository import (
    WORKFLOW_CANCELLED,
    WORKFLOW_EXECUTED,
    AbstractAssistantWorkflowRepository,
)
from app.assistant.schemas import (
    AssistantChatResponse,
    AssistantWorkflowConfirmResponse,
    WorkflowPlanView,
)
from app.assistant.skills.authoring import AssistantSkillService
from app.assistant.skills.registry import SkillRegistry
from app.assistant.workflow import StepResult, WorkflowExecutor, WorkflowStep, is_auto_confirmable
from app.core.exceptions import NotFoundError

_PENDING_NOTE = " 這個操作需要你確認後才會執行。"


def _run_status(results: list[StepResult]) -> str:
    return "succeeded" if all(result.ok for result in results) else "failed"


class WorkflowService:
    """Plan-and-confirm pipeline: NL -> candidate workflow -> check skills ->
    permission gate -> (read-only fast-path execute | persist pending) -> log.
    """

    def __init__(
        self,
        *,
        planner: WorkflowPlanner,
        executor: WorkflowExecutor,
        registry: SkillRegistry,
        workflow_repo: AbstractAssistantWorkflowRepository,
        skill_authoring: AssistantSkillService | None = None,
    ) -> None:
        self._planner = planner
        self._executor = executor
        self._registry = registry
        self._workflows = workflow_repo
        self._skill_authoring = skill_authoring

    async def chat(
        self,
        *,
        user_id: UUID,
        message: str,
        session_id: UUID | None = None,
    ) -> AssistantChatResponse:
        active_session_id = session_id or uuid4()

        if self._skill_authoring is not None:
            authoring = await self._skill_authoring.handle_authoring_message(
                user_id=user_id,
                message=message,
            )
            if authoring is not None:
                return AssistantChatResponse(
                    session_id=active_session_id,
                    message=authoring.message,
                    skill_proposal=authoring.skill_proposal,
                )

        plan = await self._planner.plan(message=message)
        if not plan.steps:
            return AssistantChatResponse(session_id=active_session_id, message=plan.reply)

        steps = classify_steps(plan.steps, self._registry)

        if is_auto_confirmable(steps):
            results = await self._executor.execute(user_id=user_id, steps=steps)
            await self._workflows.record_run(
                user_id=user_id,
                workflow_id=None,
                source_nl=message,
                status=_run_status(results),
                step_results=[result.model_dump(mode="json") for result in results],
            )
            return AssistantChatResponse(
                session_id=active_session_id,
                message=plan.reply,
                plan=WorkflowPlanView(workflow_id=None, status="auto_executed", steps=steps),
                results=results,
            )

        workflow = await self._workflows.create_pending(
            user_id=user_id,
            session_id=active_session_id,
            source_nl=message,
            steps=[step.model_dump(mode="json") for step in steps],
        )
        return AssistantChatResponse(
            session_id=active_session_id,
            message=plan.reply + _PENDING_NOTE,
            plan=WorkflowPlanView(
                workflow_id=workflow.id,
                status="pending_approval",
                steps=steps,
            ),
        )

    async def confirm(
        self,
        *,
        user_id: UUID,
        workflow_id: UUID,
    ) -> AssistantWorkflowConfirmResponse:
        workflow = await self._workflows.get_pending(user_id=user_id, workflow_id=workflow_id)
        if workflow is None:
            raise NotFoundError("Pending workflow not found")

        steps = [WorkflowStep.model_validate(step) for step in workflow.steps]
        results = await self._executor.execute(user_id=user_id, steps=steps)
        await self._workflows.set_status(workflow=workflow, status=WORKFLOW_EXECUTED)
        await self._workflows.record_run(
            user_id=user_id,
            workflow_id=workflow.id,
            source_nl=workflow.source_nl,
            status=_run_status(results),
            step_results=[result.model_dump(mode="json") for result in results],
        )
        return AssistantWorkflowConfirmResponse(
            workflow_id=workflow.id,
            status="executed",
            message="Workflow executed.",
            results=results,
        )

    async def cancel(
        self,
        *,
        user_id: UUID,
        workflow_id: UUID,
    ) -> AssistantWorkflowConfirmResponse:
        workflow = await self._workflows.get_pending(user_id=user_id, workflow_id=workflow_id)
        if workflow is None:
            raise NotFoundError("Pending workflow not found")
        await self._workflows.set_status(workflow=workflow, status=WORKFLOW_CANCELLED)
        return AssistantWorkflowConfirmResponse(
            workflow_id=workflow.id,
            status="cancelled",
            message="Workflow cancelled.",
        )

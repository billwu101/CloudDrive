from __future__ import annotations

import json
from typing import Any, Protocol
from uuid import UUID, uuid4

from app.assistant.llm.client import LLMMessage
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
from app.assistant.workflow import (
    PlannedStep,
    StepResult,
    WorkflowExecutor,
    WorkflowStep,
    apply_selection,
    has_selection_reference,
    is_auto_confirmable,
)
from app.core.exceptions import NotFoundError
from app.models.assistant_workflow import AssistantWorkflow

_PENDING_NOTE = " 這個操作需要你確認後才會執行。"


class ItemLookup(Protocol):
    """The slice of DriveService the assistant needs: resolve a selected item id
    to its metadata (id/name/item_type). ``DriveService`` satisfies this
    structurally; tests can supply a lightweight fake."""

    async def get_item(self, user_id: UUID, item_id: UUID) -> Any: ...


def _run_status(results: list[StepResult]) -> str:
    return "succeeded" if all(result.ok for result in results) else "failed"


def _all_ok(results: list[StepResult]) -> bool:
    return all(result.ok for result in results)


def _compose_failure_message(results: list[StepResult], *, retried: bool = False) -> str:
    """Truthful post-execution report. ``plan.reply`` is written by the LLM at
    planning time — before anything ran — so it must never be shown when
    execution failed. The facts (which steps ran, which failed, that nothing
    further was changed) come from StepResults, not from the model."""

    completed = [result for result in results if result.ok]
    failures = [result for result in results if not result.ok and not result.skipped]
    skipped = [result for result in results if result.skipped]
    prefix = "我重新規劃並重試了一次仍然失敗。" if retried else ""
    summary = f"執行完成 {len(completed)}/{len(results)} 步。"
    details = "".join(
        f"第 {result.index + 1} 步({result.skill})失敗:{result.error}。" for result in failures
    )
    skip_note = f"另有 {len(skipped)} 步因上游失敗而跳過。" if skipped else ""
    if completed:
        done = "、".join(result.skill for result in completed)
        tail = f"已完成:{done}。除上述外沒有進一步的變更。"
    else:
        tail = "沒有任何步驟完成,也沒有做出任何變更。"
    return prefix + summary + details + skip_note + tail


def _execution_feedback(message: str, results: list[StepResult]) -> str:
    """Planner input for a replan: the original request plus what actually
    happened. Unlike the first pass, the model now plans against real
    observations (e.g. 'search returned 0 items') instead of assumptions."""

    lines: list[str] = []
    for result in results:
        if result.ok:
            output = json.dumps(result.output, ensure_ascii=False, default=str)
            if len(output) > 300:
                output = output[:300] + "…"
            lines.append(f"- step {result.index} {result.skill}: ok, output={output}")
        elif result.skipped:
            lines.append(f"- step {result.index} {result.skill}: SKIPPED (upstream failure)")
        else:
            lines.append(f"- step {result.index} {result.skill}: FAILED — {result.error}")
    return (
        f"{message}\n\n"
        "[Execution feedback] Your previous plan for this request failed while executing:\n"
        + "\n".join(lines)
        + "\nRe-plan to satisfy the original request taking this feedback into account"
        " (e.g. adjust search terms or take a different approach). If it cannot be"
        " satisfied with the available skills, return an empty steps list and explain"
        " briefly in reply."
    )


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
        drive_service: ItemLookup,
        skill_authoring: AssistantSkillService | None = None,
    ) -> None:
        self._planner = planner
        self._executor = executor
        self._registry = registry
        self._workflows = workflow_repo
        self._drive = drive_service
        self._skill_authoring = skill_authoring

    async def _resolve_selection(
        self, user_id: UUID, selected_item_ids: list[UUID]
    ) -> list[dict[str, object]]:
        """Turn the user's checked item ids into ``{id, name, item_type}`` records
        (the shape search/list_items return), for both planner context and static
        selection resolution. Ownership is enforced by ``get_item``; an id that no
        longer resolves (stale selection) is dropped rather than failing the turn."""

        items: list[dict[str, object]] = []
        for item_id in selected_item_ids:
            try:
                item = await self._drive.get_item(user_id, item_id)
            except NotFoundError:
                continue
            items.append({"id": str(item.id), "name": item.name, "item_type": str(item.item_type)})
        return items

    async def chat(
        self,
        *,
        user_id: UUID,
        message: str,
        session_id: UUID | None = None,
        target: str | None = None,
        selected_item_ids: list[UUID] | None = None,
        history: list[LLMMessage] | None = None,
    ) -> AssistantChatResponse:
        active_session_id = session_id or uuid4()
        selected = selected_item_ids or []

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

        selected_items = await self._resolve_selection(user_id, selected)

        plan = await self._planner.plan(
            message=message, target=target, selected_items=selected_items, history=history
        )
        if not plan.steps:
            return AssistantChatResponse(session_id=active_session_id, message=plan.reply)

        steps = classify_steps(plan.steps, self._registry)

        # Any step that references the user's selection (a self-built skill, or an
        # explicit {"from": "selection", ...} argument) has its selection references
        # resolved to real ids here — never guessed by the LLM. No selection → ask.
        if has_selection_reference(steps, self._registry):
            if not selected_items:
                return AssistantChatResponse(
                    session_id=active_session_id,
                    message="請先在硬碟勾選要操作的檔案。勾好後我就能用這個技能。",
                )
            steps = apply_selection(steps, selected_items, self._registry)

        if is_auto_confirmable(steps):
            results = await self._executor.execute(user_id=user_id, steps=steps)
            await self._workflows.record_run(
                user_id=user_id,
                workflow_id=None,
                source_nl=message,
                status=_run_status(results),
                step_results=[result.model_dump(mode="json") for result in results],
            )
            if not _all_ok(results):
                # One bounded replan with real execution feedback (fast-path
                # only). If it can't produce a safely executable plan, fall
                # through to the honest failure report — never loop.
                replanned = await self._replan_after_failure(
                    user_id=user_id,
                    message=message,
                    target=target,
                    selected_items=selected_items,
                    session_id=active_session_id,
                    results=results,
                    history=history,
                )
                if replanned is not None:
                    return replanned
            return AssistantChatResponse(
                session_id=active_session_id,
                message=plan.reply if _all_ok(results) else _compose_failure_message(results),
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

    async def _replan_after_failure(
        self,
        *,
        user_id: UUID,
        message: str,
        target: str | None,
        selected_items: list[dict[str, object]],
        session_id: UUID,
        results: list[StepResult],
        history: list[LLMMessage] | None = None,
    ) -> AssistantChatResponse | None:
        """Execution-time counterpart of the planner's repair loop: feed the
        failed run's real observations back and try one revised plan.

        Guardrail — a replan executes without the user ever seeing it, so it
        may only contain read-only (auto-confirmable) steps and no
        selection-based skills. Anything needing approval means giving up and
        reporting honestly; silently queueing new destructive work the user
        never asked to review would hollow out the confirm gate. Returns None
        when no safely executable replan exists.
        """

        replan = await self._planner.plan(
            message=_execution_feedback(message, results),
            target=target,
            selected_items=selected_items,
            history=history,
        )
        if not replan.steps:
            return None
        new_steps = classify_steps(replan.steps, self._registry)
        if has_selection_reference(new_steps, self._registry) or not is_auto_confirmable(new_steps):
            return None

        new_results = await self._executor.execute(user_id=user_id, steps=new_steps)
        await self._workflows.record_run(
            user_id=user_id,
            workflow_id=None,
            source_nl=f"{message} [replan]",
            status=_run_status(new_results),
            step_results=[result.model_dump(mode="json") for result in new_results],
        )
        return AssistantChatResponse(
            session_id=session_id,
            message=(
                replan.reply
                if _all_ok(new_results)
                else _compose_failure_message(new_results, retried=True)
            ),
            plan=WorkflowPlanView(workflow_id=None, status="auto_executed", steps=new_steps),
            results=new_results,
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
            message="Workflow executed." if _all_ok(results) else _compose_failure_message(results),
            results=results,
            # Carry the session so the router can record this execution into the
            # conversation history — otherwise a confirmed write is invisible to
            # the next turn ("how did that go?" would see only the pending reply).
            session_id=workflow.session_id,
        )

    async def save_workflow(
        self,
        *,
        user_id: UUID,
        name: str,
        source_nl: str,
        steps: list[PlannedStep],
    ) -> AssistantWorkflow:
        # classify_steps rejects unknown skills / bad dependencies before saving.
        classified = classify_steps(steps, self._registry)
        return await self._workflows.save_named(
            user_id=user_id,
            name=name,
            source_nl=source_nl,
            steps=[step.model_dump(mode="json") for step in classified],
        )

    async def list_saved_workflows(self, *, user_id: UUID) -> list[AssistantWorkflow]:
        return await self._workflows.list_saved(user_id=user_id)

    async def rerun_workflow(
        self,
        *,
        user_id: UUID,
        workflow_id: UUID,
    ) -> AssistantWorkflowConfirmResponse:
        workflow = await self._workflows.get_saved(user_id=user_id, workflow_id=workflow_id)
        if workflow is None:
            raise NotFoundError("Saved workflow not found")
        # Re-validate against the live registry — a skill may have been removed.
        planned = [
            PlannedStep(
                skill=step["skill"],
                arguments=step.get("arguments", {}),
                depends_on=step.get("depends_on", []),
            )
            for step in workflow.steps
        ]
        steps = classify_steps(planned, self._registry)
        results = await self._executor.execute(user_id=user_id, steps=steps)
        await self._workflows.record_run(
            user_id=user_id,
            workflow_id=workflow.id,
            source_nl=workflow.name or workflow.source_nl,
            status=_run_status(results),
            step_results=[result.model_dump(mode="json") for result in results],
        )
        return AssistantWorkflowConfirmResponse(
            workflow_id=workflow.id,
            status="executed",
            message=(
                "Saved workflow executed."
                if _all_ok(results)
                else _compose_failure_message(results)
            ),
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

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any, Protocol
from uuid import UUID, uuid4

from app.assistant.llm.client import LLMMessage
from app.assistant.memory import _summarise_output
from app.assistant.permissions import classify_steps
from app.assistant.planner import PlanResult, WorkflowPlanner
from app.assistant.repository import (
    WORKFLOW_CANCELLED,
    WORKFLOW_EXECUTED,
    AbstractAssistantWorkflowRepository,
)
from app.assistant.schemas import (
    AssistantChatResponse,
    AssistantLlmMeta,
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
    ref_source,
)
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.models.assistant_workflow import AssistantWorkflow

_LOG = logging.getLogger(__name__)

_PENDING_NOTE = " 這個操作需要你確認後才會執行。"


class ItemLookup(Protocol):
    """The slice of DriveService the assistant needs: resolve a selected item id
    to its metadata (id/name/item_type), including items in the trash (so a
    selection made in the trash view still resolves). ``DriveService`` satisfies
    this structurally; tests can supply a lightweight fake."""

    async def get_item_any_state(self, user_id: UUID, item_id: UUID) -> Any: ...


def _run_status(results: list[StepResult]) -> str:
    return "succeeded" if all(result.ok for result in results) else "failed"


def _all_ok(results: list[StepResult]) -> bool:
    return all(result.ok for result in results)


def _llm_meta(plan: PlanResult) -> AssistantLlmMeta:
    """Surface the planning call's diagnostics (see PlanResult) in the response —
    additive/observability-only, never used by planning or execution logic."""

    return AssistantLlmMeta(
        done_reason=plan.done_reason,
        prompt_tokens=plan.prompt_tokens,
        completion_tokens=plan.completion_tokens,
    )


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


def _renumber_kept(planned: list[PlannedStep], kept: list[int]) -> list[PlannedStep]:
    """Re-index the reconnaissance steps that survive into the final plan.

    Dropping the first pass's unexecuted writes leaves the kept reads carrying
    dependency indices that point at steps which no longer exist (a real run
    failed with "Step 0 has an invalid dependency: 1"). Entries pointing at a
    dropped step are removed; entries pointing at another kept step are mapped
    to its new position. Argument references get the same treatment —
    ``_consumes_output_of`` already guaranteed none of them point at a dropped
    step, but they can point at each other.
    """

    mapping = {old: new for new, old in enumerate(kept)}
    steps: list[PlannedStep] = []
    for old in kept:
        step = planned[old]
        arguments: dict[str, Any] = {}
        for key, value in step.arguments.items():
            source = ref_source(value)
            if isinstance(source, int) and not isinstance(source, bool) and source in mapping:
                key_name = "from" if "from" in value else "from_step"
                arguments[key] = {**value, key_name: mapping[source]}
            else:
                arguments[key] = value
        steps.append(
            PlannedStep(
                skill=step.skill,
                arguments=arguments,
                depends_on=[mapping[d] for d in step.depends_on if d in mapping],
            )
        )
    return steps


def _consumes_output_of(step: WorkflowStep, indices: set[int]) -> bool:
    """Does this step consume the *output* of any of ``indices``?

    Only argument references count. ``depends_on`` is an ordering hint — a model
    routinely marks "list the root" as depending on "create the folder" even
    though the listing needs nothing from it, and treating that as a data
    dependency left no step at all to run as reconnaissance.
    """

    return any(ref_source(value) in indices for value in step.arguments.values())


def _observed(output: Any) -> str:
    """Render a reconnaissance step's output for the planner's second pass.

    Deliberately richer than the conversation-memory summary, which keeps names
    only: a follow-up decision may hinge on size or modification time ("archive
    the biggest file" moved the wrong one in every trial because the summary
    never showed sizes). Ids stay out — the model must still reference steps,
    not paste UUIDs.
    """

    items = output.get("items") if isinstance(output, dict) else output
    if not isinstance(items, list):
        return _summarise_output(output)
    rendered: list[str] = []
    for position, item in enumerate(items[:40]):
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        facts = [f"[{position}] {item['name']}"]
        if item.get("item_type"):
            facts.append(str(item["item_type"]).lower())
        if isinstance(item.get("size_bytes"), int):
            facts.append(f"{item['size_bytes']} bytes")
        if item.get("updated_at"):
            facts.append(f"updated {str(item['updated_at'])[:10]}")
        rendered.append(" ".join(facts[:1]) + " (" + ", ".join(facts[1:]) + ")")
    if not rendered:
        return _summarise_output(output)
    return f"{len(items)} items — " + "; ".join(rendered)


def _followup_prompt(
    message: str, results: list[StepResult], *, index_map: Mapping[int, int]
) -> str:
    """Planner input for the second pass of two-phase planning.

    Unlike ``_execution_feedback`` (which reports a *failure* and asks for a
    replacement plan), this reports a successful reconnaissance and asks for
    the *remaining* steps. Item names are what the model needs in order to
    decide what belongs where; ids stay out of it so the "never write a UUID"
    rule holds and the model keeps using step references.

    Every step number here is the step's position in the *combined* plan, not
    the position it had in the first pass. Dropping the unexecuted writes moves
    the surviving reads, and the model is a consumer of those numbers: labelling
    a listing "step 2" when it ends up at index 0 made every real run reference
    the wrong step ("cannot resolve path 'items.1.id'" against a create_folder
    output).
    """

    next_index = len(index_map)
    lines = [
        f"- step {index_map[r.index]} {r.skill}: {_observed(r.output)}"
        for r in results
        if r.ok and r.index in index_map
    ]
    return (
        f"{message}\n\n"
        "[Observation] The read steps you asked for have been executed and now occupy "
        f"steps 0-{next_index - 1} of the plan (renumbered — use the numbers below, not "
        "the ones you gave them). Their results:\n"
        + "\n".join(lines)
        + f"\n\nNow plan ONLY the remaining steps that finish the request. Your first new "
        f"step is index {next_index}. To use anything you see above, reference the step "
        'number shown on its line, e.g. {"from": 0, "path": "items.2.id"} for the third '
        "item of step 0. Do not repeat the steps above. Set needs_followup to false."
    )


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
        two_phase_planning: bool | None = None,
    ) -> None:
        self._planner = planner
        self._executor = executor
        self._registry = registry
        self._workflows = workflow_repo
        self._drive = drive_service
        self._skill_authoring = skill_authoring
        # Injectable so tests don't need the global settings; None = read config.
        self._two_phase_planning = (
            get_settings().assistant_two_phase_planning
            if two_phase_planning is None
            else two_phase_planning
        )

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
                item = await self._drive.get_item_any_state(user_id, item_id)
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
                    llm_meta=AssistantLlmMeta(
                        done_reason=authoring.done_reason,
                        prompt_tokens=authoring.prompt_tokens,
                        completion_tokens=authoring.completion_tokens,
                    ),
                )

        selected_items = await self._resolve_selection(user_id, selected)

        plan = await self._planner.plan(
            message=message, target=target, selected_items=selected_items, history=history
        )
        if not plan.steps:
            return AssistantChatResponse(
                session_id=active_session_id, message=plan.reply, llm_meta=_llm_meta(plan)
            )

        plan = await self._maybe_plan_followup(
            plan,
            user_id=user_id,
            message=message,
            target=target,
            selected_items=selected_items,
            history=history,
        )

        steps = classify_steps(plan.steps, self._registry)

        # Any step that references the user's selection (a self-built skill, or an
        # explicit {"from": "selection", ...} argument) has its selection references
        # resolved to real ids here — never guessed by the LLM. No selection → ask.
        if has_selection_reference(steps, self._registry):
            if not selected_items:
                return AssistantChatResponse(
                    session_id=active_session_id,
                    message="請先在硬碟勾選要操作的檔案。勾好後我就能用這個技能。",
                    llm_meta=_llm_meta(plan),
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
                llm_meta=_llm_meta(plan),
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
            llm_meta=_llm_meta(plan),
        )

    async def _maybe_plan_followup(
        self,
        plan: PlanResult,
        *,
        user_id: UUID,
        message: str,
        target: str | None,
        selected_items: list[dict[str, object]],
        history: list[LLMMessage] | None,
    ) -> PlanResult:
        """Two-phase planning: run the reconnaissance steps, then plan the rest
        against what they actually returned (2026-07-29, experimental).

        The planner otherwise has to commit to every step before seeing any
        data, so a request like "sort these files by what they are" is
        unanswerable: the only filter available at planning time is a literal
        keyword search. When the model says it needs to look first
        (``needs_followup``), the read steps run and their real output is fed
        back for a second pass.

        The second pass's steps are **appended to the same plan** rather than
        forming a new one. Step indices then stay contiguous, so the existing
        reference syntax, the confirmation gate and the executor need no
        changes, and the user still approves one complete plan. The read steps
        run again at execution time — they are read-only, so that is safe.

        Guardrails: the flag is off by default; only a fully read-only first
        plan qualifies (never execute writes before approval); exactly one
        follow-up, never a loop; the reconnaissance run is not recorded as
        workflow history since it is an internal step.
        """

        if not self._two_phase_planning:
            return plan
        if not plan.needs_followup:
            return plan
        classified = classify_steps(plan.steps, self._registry)
        if has_selection_reference(classified, self._registry):
            return plan
        # Execute ONLY the read-only steps for reconnaissance. In practice the
        # model keeps folding preparation writes (create the destination folder)
        # into its first pass however firmly the prompt says not to, and refusing
        # those plans outright just disables the feature. Skipping them is both
        # safer and more permissive: nothing unapproved runs, and the second
        # pass re-plans that work anyway.
        skipped = {step.index for step in classified if step.requires_approval}
        recon_indices = [
            step.index
            for step in classified
            if step.index not in skipped and not _consumes_output_of(step, skipped)
        ]
        if not recon_indices:
            return plan
        recon = [classified[i] for i in recon_indices]

        results = await self._executor.execute(user_id=user_id, steps=recon)
        # Only the reconnaissance reads survive into the final plan. The first
        # pass's write steps were never executed, and keeping them made the
        # model plan the same writes twice — the duplicate then failed on a
        # name conflict and cascaded into every dependent step. The second pass
        # plans all remaining work, including any preparation the first pass had
        # sketched.
        kept = _renumber_kept(plan.steps, recon_indices)
        index_map = {old: new for new, old in enumerate(recon_indices)}
        followup = await self._planner.plan(
            message=_followup_prompt(message, results, index_map=index_map),
            target=target,
            selected_items=selected_items,
            history=history,
            index_offset=len(kept),
        )
        if not followup.steps:
            return plan
        combined = PlanResult(
            reply=followup.reply or plan.reply,
            steps=[*kept, *followup.steps],
        )
        combined._copy_llm_meta(followup)
        return combined

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
            llm_meta=_llm_meta(replan),
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

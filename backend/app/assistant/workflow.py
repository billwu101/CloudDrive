from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.assistant.hooks import HookContext, HookRegistry
from app.assistant.skills.registry import SkillContext, SkillRegistry

READ_TIER = "read"


class PlannedStep(BaseModel):
    """A step as proposed by the planner LLM."""

    skill: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[int] = Field(default_factory=list)


class WorkflowStep(BaseModel):
    """A classified, executable step."""

    index: int
    skill: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[int] = Field(default_factory=list)
    permission_tier: str
    requires_approval: bool


class StepResult(BaseModel):
    index: int
    skill: str
    ok: bool
    output: Any | None = None
    error: str | None = None


def is_auto_confirmable(steps: list[WorkflowStep]) -> bool:
    """A workflow is fast-path eligible only when every step is read-only."""

    return all(not step.requires_approval for step in steps)


def requires_file_selection(steps: list[WorkflowStep], registry: SkillRegistry) -> bool:
    """True if any step uses a skill that needs a user-selected file (self-built)."""

    for step in steps:
        skill = registry.get(step.skill)
        if skill is not None and skill.requires_selection:
            return True
    return False


def expand_selection_steps(
    steps: list[WorkflowStep],
    selected_item_ids: list[UUID],
    registry: SkillRegistry,
) -> list[WorkflowStep]:
    """Expand each requires-selection step into one step per selected file, with
    ``item_id`` injected (never guessed by the LLM). Other steps are preserved and
    their ``depends_on`` indices remapped to the new numbering."""

    old_to_new: dict[int, list[int]] = {}
    expanded: list[WorkflowStep] = []
    for step in steps:
        skill = registry.get(step.skill)
        if skill is not None and skill.requires_selection:
            new_indices: list[int] = []
            for item_id in selected_item_ids:
                index = len(expanded)
                new_indices.append(index)
                expanded.append(
                    WorkflowStep(
                        index=index,
                        skill=step.skill,
                        arguments={"item_id": str(item_id)},
                        depends_on=[],  # self-built skills are leaf operations
                        permission_tier=step.permission_tier,
                        requires_approval=step.requires_approval,
                    )
                )
            old_to_new[step.index] = new_indices
        else:
            index = len(expanded)
            new_deps = [new for old in step.depends_on for new in old_to_new.get(old, [old])]
            expanded.append(step.model_copy(update={"index": index, "depends_on": new_deps}))
            old_to_new[step.index] = [index]
    return expanded


class StepResolutionError(Exception):
    """Raised when a step argument references an earlier step that cannot be resolved."""


def is_step_ref(value: Any) -> bool:
    """A composable-skill reference: ``{"from_step": int, "path": "items.0.id"}``."""

    return isinstance(value, dict) and "from_step" in value


def _resolve_path(output: Any, path: str) -> Any:
    current = output
    for part in filter(None, path.split(".")):
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise StepResolutionError(f"cannot descend into {type(current).__name__} at '{part}'")
    return current


def resolve_arguments(
    arguments: dict[str, Any],
    results_by_index: dict[int, StepResult],
) -> dict[str, Any]:
    """Replace any step references in arguments with the referenced step's output."""

    resolved: dict[str, Any] = {}
    for key, value in arguments.items():
        if not is_step_ref(value):
            resolved[key] = value
            continue
        from_step = value.get("from_step")
        path = str(value.get("path", ""))
        source = results_by_index.get(from_step) if isinstance(from_step, int) else None
        if source is None or not source.ok:
            raise StepResolutionError(
                f"argument '{key}' references step {from_step}, which did not produce a result"
            )
        try:
            resolved[key] = _resolve_path(source.output, path)
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise StepResolutionError(
                f"argument '{key}': cannot resolve path '{path}' from step {from_step}"
            ) from exc
    return resolved


class WorkflowExecutor:
    def __init__(self, *, registry: SkillRegistry, hooks: HookRegistry | None = None) -> None:
        self._registry = registry
        self._hooks = hooks or HookRegistry()

    async def execute(self, *, user_id: UUID, steps: list[WorkflowStep]) -> list[StepResult]:
        context = SkillContext(user_id=user_id)
        results: list[StepResult] = []
        await self._hooks.fire("before_execution", HookContext(user_id=user_id, steps=steps))
        for step in steps:
            await self._hooks.fire(
                "before_step", HookContext(user_id=user_id, steps=steps, step=step)
            )
            try:
                # Composable skills: resolve references to earlier steps' outputs first.
                ok_results = {r.index: r for r in results if r.ok}
                arguments = resolve_arguments(step.arguments, ok_results)
                output = await self._registry.execute(
                    name=step.skill,
                    context=context,
                    arguments=arguments,
                )
            except Exception as exc:
                result = StepResult(index=step.index, skill=step.skill, ok=False, error=str(exc))
                results.append(result)
                await self._hooks.fire(
                    "on_error", HookContext(user_id=user_id, steps=steps, step=step, error=str(exc))
                )
                break
            result = StepResult(index=step.index, skill=step.skill, ok=True, output=output)
            results.append(result)
            await self._hooks.fire(
                "after_step", HookContext(user_id=user_id, steps=steps, step=step, result=result)
            )
        return results

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
                output = await self._registry.execute(
                    name=step.skill,
                    context=context,
                    arguments=step.arguments,
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

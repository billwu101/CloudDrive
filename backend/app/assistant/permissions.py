from __future__ import annotations

from app.assistant.skills.registry import SkillRegistry
from app.assistant.workflow import READ_TIER, PlannedStep, WorkflowStep
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError


def classify_steps(planned: list[PlannedStep], registry: SkillRegistry) -> list[WorkflowStep]:
    """Bind each planned step to a registered skill and tag its permission tier.

    Unknown skills are rejected here so a planner hallucination can never reach
    execution. ``requires_approval`` is true for anything that is not read-only.
    """

    steps: list[WorkflowStep] = []
    for index, planned_step in enumerate(planned):
        skill = registry.get(planned_step.skill)
        if skill is None:
            raise AppError(
                ErrorCode.INVALID_OPERATION,
                f"Plan references unknown skill: {planned_step.skill}",
            )
        for dependency in planned_step.depends_on:
            if dependency < 0 or dependency >= index:
                raise AppError(
                    ErrorCode.INVALID_OPERATION,
                    f"Step {index} has an invalid dependency: {dependency}",
                )
        tier = skill.permission_tier
        steps.append(
            WorkflowStep(
                index=index,
                skill=planned_step.skill,
                arguments=dict(planned_step.arguments),
                depends_on=list(planned_step.depends_on),
                permission_tier=tier,
                requires_approval=tier != READ_TIER,
            )
        )
    return steps

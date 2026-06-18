from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from app.assistant.workflow import StepResult, WorkflowStep

logger = logging.getLogger("app.assistant.hooks")

# Lifecycle event names fired by the workflow executor / service.
HookEvent = str


@dataclass(frozen=True)
class HookContext:
    user_id: UUID
    steps: list[WorkflowStep]
    step: WorkflowStep | None = None
    result: StepResult | None = None
    error: str | None = None


Hook = Callable[[HookContext], Awaitable[None]]


class HookRegistry:
    """Minimal pluggable lifecycle-hook registry.

    Hooks observe the workflow execution; they do not alter control flow in this
    slice. The permission gate that decides auto-execute vs. pending lives in the
    service before execution (see ``workflow.is_auto_confirmable``).
    """

    def __init__(self) -> None:
        self._hooks: dict[HookEvent, list[Hook]] = {}

    def register(self, event: HookEvent, hook: Hook) -> None:
        self._hooks.setdefault(event, []).append(hook)

    async def fire(self, event: HookEvent, context: HookContext) -> None:
        for hook in self._hooks.get(event, []):
            await hook(context)


async def _audit_hook(context: HookContext) -> None:
    detail: dict[str, Any] = {"user_id": str(context.user_id)}
    if context.step is not None:
        detail["skill"] = context.step.skill
    if context.error is not None:
        detail["error"] = context.error
    logger.info("assistant workflow event: %s", detail)


def snapshot_before_write_hook(snapshot_service: Any) -> Hook:
    """A ``before_execution`` hook that takes a Time Machine snapshot when the
    workflow contains any write (approval-requiring) step. Read-only workflows
    don't trigger a snapshot. Snapshot failures never block execution."""

    async def _hook(context: HookContext) -> None:
        if not any(step.requires_approval for step in context.steps):
            return
        try:
            await snapshot_service.create(
                user_id=context.user_id,
                trigger="assistant",
                label="Before assistant workflow",
            )
        except Exception:
            logger.exception("Failed to create pre-action assistant snapshot")

    return _hook


def default_hook_registry() -> HookRegistry:
    registry = HookRegistry()
    registry.register("before_execution", _audit_hook)
    registry.register("after_step", _audit_hook)
    registry.register("on_error", _audit_hook)
    return registry

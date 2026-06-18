from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from app.assistant.hooks import (
    HookContext,
    HookRegistry,
    default_hook_registry,
    snapshot_before_write_hook,
)
from app.assistant.permissions import classify_steps
from app.assistant.skills.registry import RegisteredSkill, SkillContext, SkillRegistry
from app.assistant.workflow import (
    PlannedStep,
    WorkflowExecutor,
    is_auto_confirmable,
)


def _registry() -> SkillRegistry:
    registry = SkillRegistry()

    async def read_handler(context: SkillContext, args: Mapping[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    async def boom_handler(context: SkillContext, args: Mapping[str, Any]) -> dict[str, Any]:
        raise RuntimeError("boom")

    registry.register(
        RegisteredSkill(
            name="list_items",
            description="List.",
            parameters={"type": "object", "properties": {}, "additionalProperties": True},
            permission_tier="read",
            handler=read_handler,
        )
    )
    registry.register(
        RegisteredSkill(
            name="trash_item",
            description="Trash.",
            parameters={"type": "object", "properties": {}, "additionalProperties": True},
            permission_tier="destructive",
            handler=boom_handler,
        )
    )
    return registry


async def test_registry_fires_hooks_in_order_with_context() -> None:
    seen: list[str] = []
    registry = HookRegistry()

    async def hook_a(context: HookContext) -> None:
        seen.append(f"a:{context.user_id}")

    async def hook_b(context: HookContext) -> None:
        seen.append("b")

    registry.register("before_execution", hook_a)
    registry.register("before_execution", hook_b)
    uid = uuid4()

    await registry.fire("before_execution", HookContext(user_id=uid, steps=[]))
    await registry.fire("never_registered", HookContext(user_id=uid, steps=[]))

    assert seen == [f"a:{uid}", "b"]


async def test_default_registry_fires_audit_events_without_error() -> None:
    registry = default_hook_registry()
    ctx = HookContext(user_id=uuid4(), steps=[])
    # The default audit hooks fire cleanly on their lifecycle events; an
    # unregistered event is a harmless no-op.
    for event in ("before_execution", "after_step", "on_error", "never_registered"):
        await registry.fire(event, ctx)


async def test_executor_fires_lifecycle_hooks_including_on_error() -> None:
    events: list[tuple[str, str | None]] = []
    hooks = HookRegistry()

    async def recorder(event: str) -> Any:
        async def _hook(context: HookContext) -> None:
            events.append((event, context.step.skill if context.step else None))

        return _hook

    for name in ("before_execution", "before_step", "after_step", "on_error"):
        hooks.register(name, await recorder(name))

    registry = _registry()
    steps = classify_steps(
        [
            PlannedStep(skill="list_items", arguments={}),
            PlannedStep(skill="trash_item", arguments={}),
        ],
        registry,
    )
    executor = WorkflowExecutor(registry=registry, hooks=hooks)

    await executor.execute(user_id=uuid4(), steps=steps)

    names = [e for e, _ in events]
    assert names.count("before_execution") == 1
    assert ("before_step", "list_items") in events
    assert ("on_error", "trash_item") in events  # the failing destructive step fired on_error


class _RecordingSnapshotService:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> None:
        self.created.append(kwargs)
        return None


async def test_snapshot_hook_fires_only_when_workflow_has_write_step() -> None:
    registry = _registry()
    snap = _RecordingSnapshotService()
    hook = snapshot_before_write_hook(snap)
    uid = uuid4()

    read_only = classify_steps([PlannedStep(skill="list_items", arguments={})], registry)
    await hook(HookContext(user_id=uid, steps=read_only))
    assert snap.created == []  # read-only workflow → no snapshot

    with_write = classify_steps(
        [
            PlannedStep(skill="list_items", arguments={}),
            PlannedStep(skill="trash_item", arguments={}),
        ],
        registry,
    )
    await hook(HookContext(user_id=uid, steps=with_write))
    assert len(snap.created) == 1
    assert snap.created[0]["trigger"] == "assistant"
    assert snap.created[0]["user_id"] == uid


async def test_snapshot_hook_swallows_snapshot_failure() -> None:
    registry = _registry()

    class _Boom:
        async def create(self, **kwargs: Any) -> None:
            raise RuntimeError("snapshot backend down")

    hook = snapshot_before_write_hook(_Boom())
    with_write = classify_steps(
        [PlannedStep(skill="trash_item", arguments={})],
        registry,
    )
    # Must not raise — a snapshot failure can never block the workflow.
    await hook(HookContext(user_id=uuid4(), steps=with_write))


def test_permission_gate_keeps_destructive_and_install_out_of_fast_path() -> None:
    registry = _registry()
    # A read-only plan is auto-confirmable; adding a destructive step is not.
    read_only = classify_steps([PlannedStep(skill="list_items", arguments={})], registry)
    assert is_auto_confirmable(read_only) is True

    with_destructive = classify_steps(
        [
            PlannedStep(skill="list_items", arguments={}),
            PlannedStep(skill="trash_item", arguments={}),
        ],
        registry,
    )
    assert is_auto_confirmable(with_destructive) is False
    assert any(step.requires_approval for step in with_destructive)

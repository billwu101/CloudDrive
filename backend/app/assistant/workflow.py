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
    # True when the step was never executed because an upstream dependency
    # failed (or was itself skipped) — distinct from a step that ran and failed.
    skipped: bool = False


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


def has_selection_reference(steps: list[WorkflowStep], registry: SkillRegistry) -> bool:
    """True if executing ``steps`` needs the user's file selection — either a
    self-built ``requires_selection`` skill, or any argument that is an explicit
    selection reference (``{"from": "selection", ...}``)."""

    for step in steps:
        skill = registry.get(step.skill)
        if skill is not None and skill.requires_selection:
            return True
        if any(is_selection_ref(value) for value in step.arguments.values()):
            return True
    return False


def _selection_value(
    ref: dict[str, Any], items: list[dict[str, Any]], forced_index: int | None
) -> Any:
    """Resolve one selection reference to a concrete value from ``items``.
    ``forced_index`` is set during ``each`` fan-out; otherwise the ref's ``item``
    index (default 0) is used. ``path`` selects a field within the item; without
    it the item's ``id`` is returned."""

    index = forced_index if forced_index is not None else ref.get("item", 0)
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(items):
        raise StepResolutionError(
            f"selection reference index {index!r} out of range (have {len(items)} selected)"
        )
    item = items[index]
    path = ref.get("path")
    if not path:
        value = item.get("id")
        if value is None:
            raise StepResolutionError("selected item has no id")
        return value
    return _resolve_path(item, str(path))


def _remap_deps(deps: list[int], old_to_new: dict[int, list[int]]) -> list[int]:
    return [new for old in deps for new in old_to_new.get(old, [old])]


def _remap_step_ref(value: Any, old_to_new: dict[int, list[int]]) -> Any:
    """Rewrite an integer step reference to its new index after fan-out has
    re-numbered earlier steps. Non-references pass through unchanged."""

    if not is_step_ref(value):
        return value
    old = ref_source(value)
    if not isinstance(old, int) or old not in old_to_new:
        return value
    updated = {k: v for k, v in value.items() if k != "from_step"}
    updated["from"] = old_to_new[old][0]
    return updated


def apply_selection(
    steps: list[WorkflowStep],
    selection_items: list[dict[str, Any]],
    registry: SkillRegistry,
) -> list[WorkflowStep]:
    """Statically resolve selection references against the user's selected items,
    fanning out any ``each`` step into one step per selected file. All other
    arguments (destination, new name, …) are preserved, and step-output
    references (``{"from": int}``) are left for the executor to resolve at run
    time. ``depends_on`` and step references are remapped to the new numbering.

    A self-built ``requires_selection`` skill whose ``item_id`` the planner left
    unbound is treated as acting on every selected file (backward-compatible with
    the old per-file expansion)."""

    old_to_new: dict[int, list[int]] = {}
    expanded: list[WorkflowStep] = []
    for step in steps:
        args = dict(step.arguments)
        skill = registry.get(step.skill)
        if skill is not None and skill.requires_selection:
            current = args.get("item_id")
            has_value = isinstance(current, str) and bool(current.strip())
            if not is_reference(current) and not has_value:
                args["item_id"] = {"from": "selection", "each": True}

        new_deps = _remap_deps(step.depends_on, old_to_new)
        each_keys = [k for k, v in args.items() if is_selection_ref(v) and bool(v.get("each"))]

        if each_keys:
            new_indices: list[int] = []
            for i in range(len(selection_items)):
                resolved: dict[str, Any] = {}
                for key, value in args.items():
                    if is_selection_ref(value):
                        forced = i if key in each_keys else None
                        resolved[key] = _selection_value(value, selection_items, forced)
                    else:
                        resolved[key] = _remap_step_ref(value, old_to_new)
                index = len(expanded)
                new_indices.append(index)
                expanded.append(
                    step.model_copy(
                        update={"index": index, "arguments": resolved, "depends_on": new_deps}
                    )
                )
            old_to_new[step.index] = new_indices
        else:
            resolved = {}
            for key, value in args.items():
                if is_selection_ref(value):
                    resolved[key] = _selection_value(value, selection_items, None)
                else:
                    resolved[key] = _remap_step_ref(value, old_to_new)
            index = len(expanded)
            expanded.append(
                step.model_copy(
                    update={"index": index, "arguments": resolved, "depends_on": new_deps}
                )
            )
            old_to_new[step.index] = [index]
    return expanded


def expand_selection_steps(
    steps: list[WorkflowStep],
    selected_item_ids: list[UUID],
    registry: SkillRegistry,
) -> list[WorkflowStep]:
    """Backward-compatible adapter over :func:`apply_selection`: fan out each
    self-built ``requires_selection`` skill into one step per selected file."""

    selection_items = [{"id": str(item_id)} for item_id in selected_item_ids]
    return apply_selection(steps, selection_items, registry)


class StepResolutionError(Exception):
    """Raised when a step argument references an earlier step that cannot be resolved."""


def ref_source(value: Any) -> Any:
    """The source a reference points at: the string ``"selection"``, an integer
    step index, or ``None`` when ``value`` is not a reference. Accepts both the
    unified ``{"from": ...}`` key and the legacy ``{"from_step": int}`` syntax."""

    if not isinstance(value, dict):
        return None
    if "from" in value:
        return value["from"]
    if "from_step" in value:  # legacy, pre-unification
        return value["from_step"]
    return None


def is_reference(value: Any) -> bool:
    """Any item reference — a selection reference or a step-output reference."""

    return isinstance(value, dict) and ("from" in value or "from_step" in value)


def is_selection_ref(value: Any) -> bool:
    """A reference to the user's current file selection:
    ``{"from": "selection", "item": i}`` or ``{"from": "selection", "each": true}``."""

    return bool(ref_source(value) == "selection")


def is_step_ref(value: Any) -> bool:
    """A reference to an earlier step's output by integer index:
    ``{"from": int, "path": "items.0.id"}`` (or legacy ``{"from_step": int}``)."""

    return isinstance(ref_source(value), int) and not isinstance(ref_source(value), bool)


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
        from_step = ref_source(value)
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


def _blocked_dependencies(step: WorkflowStep, unavailable: set[int]) -> set[int]:
    """Dependencies of ``step`` that failed or were skipped. Covers both the
    explicit ``depends_on`` edges and implicit ``from_step`` argument
    references — either kind pointing at an unavailable step makes this step
    unexecutable."""

    deps = set(step.depends_on)
    for value in step.arguments.values():
        if is_step_ref(value):
            from_step = ref_source(value)
            if isinstance(from_step, int):
                deps.add(from_step)
    return deps & unavailable


class WorkflowExecutor:
    def __init__(self, *, registry: SkillRegistry, hooks: HookRegistry | None = None) -> None:
        self._registry = registry
        self._hooks = hooks or HookRegistry()

    async def execute(self, *, user_id: UUID, steps: list[WorkflowStep]) -> list[StepResult]:
        """Sequential execution with failure isolation: a failure only blocks
        its own dependents (recorded as skipped); unrelated steps still run.
        Every step gets exactly one result — ok, failed, or skipped."""

        context = SkillContext(user_id=user_id)
        results: list[StepResult] = []
        unavailable: set[int] = set()  # failed or skipped step indices
        await self._hooks.fire("before_execution", HookContext(user_id=user_id, steps=steps))
        for step in steps:
            blocked = _blocked_dependencies(step, unavailable)
            if blocked:
                blocked_list = "、".join(str(index + 1) for index in sorted(blocked))
                results.append(
                    StepResult(
                        index=step.index,
                        skill=step.skill,
                        ok=False,
                        skipped=True,
                        error=f"skipped: 依賴的第 {blocked_list} 步未成功",
                    )
                )
                unavailable.add(step.index)
                continue
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
                unavailable.add(step.index)
                await self._hooks.fire(
                    "on_error", HookContext(user_id=user_id, steps=steps, step=step, error=str(exc))
                )
                continue
            result = StepResult(index=step.index, skill=step.skill, ok=True, output=output)
            results.append(result)
            await self._hooks.fire(
                "after_step", HookContext(user_id=user_id, steps=steps, step=step, result=result)
            )
        return results

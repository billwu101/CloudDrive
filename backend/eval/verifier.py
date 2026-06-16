from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from eval.schema import EvalCase


@dataclass(frozen=True)
class CheckResult:
    dimension: str
    name: str
    ok: bool
    detail: str


def verify(case: EvalCase, response: dict[str, Any]) -> list[CheckResult]:
    """Deterministic assertions over an /assistant/chat response dict."""

    checks: list[CheckResult] = []
    plan = response.get("plan") or {}
    steps = plan.get("steps", []) if isinstance(plan, dict) else []
    skills = [step.get("skill") for step in steps if isinstance(step, dict)]
    status = plan.get("status") if isinstance(plan, dict) else None

    workflow = case.expect.workflow
    if workflow is not None:
        for skill in workflow.steps_include:
            checks.append(
                CheckResult(
                    "correctness",
                    f"plan includes {skill}",
                    skill in skills,
                    f"plan skills={skills}",
                )
            )
        if workflow.requires_confirmation is not None:
            expected = "pending_approval" if workflow.requires_confirmation else "auto_executed"
            checks.append(
                CheckResult(
                    "correctness",
                    f"plan status is {expected}",
                    status == expected,
                    f"status={status}",
                )
            )
        if workflow.skill_generated is not None:
            proposal = response.get("skill_proposal") or {}
            name = proposal.get("name") if isinstance(proposal, dict) else None
            checks.append(
                CheckResult(
                    "safety",
                    f"proposes skill {workflow.skill_generated} (pending approval)",
                    name == workflow.skill_generated,
                    f"proposal={name}",
                )
            )

    if not checks:
        checks.append(
            CheckResult(
                "correctness",
                "response received",
                bool(response.get("message")),
                "no explicit expectations declared",
            )
        )
    return checks

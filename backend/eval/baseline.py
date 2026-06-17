from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from eval.scoring import CaseScore

# Scores within this tolerance of the baseline are treated as unchanged (guards
# against float noise from a real, non-deterministic model).
DEFAULT_TOLERANCE = 0.001


@dataclass(frozen=True)
class BaselineComparison:
    case_id: str
    current: float
    baseline: float | None
    delta: float
    regressed: bool
    is_new: bool


def load_baseline(path: str | Path) -> dict[str, float]:
    """Load a baseline ``{case_id: score}`` map written by :func:`save_baseline`."""

    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"baseline must be a JSON object, got {type(raw)!r}")
    cases = raw.get("cases", raw)
    return {str(case_id): float(score) for case_id, score in cases.items()}


def save_baseline(path: str | Path, scores: list[CaseScore]) -> None:
    """Persist the current run's per-case scores as a baseline."""

    payload = {"cases": {score.case_id: score.score for score in scores}}
    Path(path).write_text(json.dumps(payload, indent=2) + "\n")


def compare_to_baseline(
    scores: list[CaseScore],
    baseline: dict[str, float],
    *,
    tolerance: float = DEFAULT_TOLERANCE,
) -> list[BaselineComparison]:
    """Compare current scores against a baseline, flagging regressions.

    A case regresses when it existed in the baseline and its score dropped by
    more than ``tolerance``. New cases (absent from the baseline) never count as
    regressions.
    """

    comparisons: list[BaselineComparison] = []
    for score in scores:
        prior = baseline.get(score.case_id)
        is_new = prior is None
        delta = 0.0 if prior is None else round(score.score - prior, 3)
        regressed = prior is not None and score.score < prior - tolerance
        comparisons.append(
            BaselineComparison(
                case_id=score.case_id,
                current=score.score,
                baseline=prior,
                delta=delta,
                regressed=regressed,
                is_new=is_new,
            )
        )
    return comparisons


def has_regression(comparisons: list[BaselineComparison]) -> bool:
    return any(comparison.regressed for comparison in comparisons)


def comparison_to_markdown(comparisons: list[BaselineComparison]) -> str:
    lines = ["| Case | Baseline | Current | Δ | Status |", "|---|---|---|---|---|"]
    for c in comparisons:
        base = "—" if c.baseline is None else f"{c.baseline:.2f}"
        if c.is_new:
            status = "NEW"
        elif c.regressed:
            status = "⚠️ REGRESSED"
        elif c.delta > 0:
            status = "improved"
        else:
            status = "ok"
        lines.append(f"| {c.case_id} | {base} | {c.current:.2f} | {c.delta:+.2f} | {status} |")
    regressed = sum(1 for c in comparisons if c.regressed)
    lines.append("")
    lines.append(f"**{regressed} regression(s)**")
    return "\n".join(lines)

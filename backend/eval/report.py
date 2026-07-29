from __future__ import annotations

import json

from eval.judge import JUDGE_DIMENSION
from eval.schema import EvalCase
from eval.scoring import AggregateScore, CaseScore
from eval.verifier import CheckResult


def verbose_markdown(rows: list[tuple[EvalCase, str, list[CheckResult]]]) -> str:
    """Per-case detail for --verbose: input prompt, produced result, the judge's
    score + strengths/weaknesses, and the deterministic correctness gate."""
    lines: list[str] = []
    for case, result_summary, checks in rows:
        judge_detail = next(
            (c.detail for c in checks if c.dimension == JUDGE_DIMENSION), "（未評分）"
        )
        gate_ok = all(c.ok for c in checks if c.dimension != JUDGE_DIMENSION)
        lines += [
            f"### {case.id}",
            f"- **輸入 prompt**：{case.prompt}",
            f"- **輸出結果**：{result_summary}",
            f"- **評分／理由**：{judge_detail}",
            f"- **確定性守門**：{'✓' if gate_ok else '✗'}",
            "",
        ]
    return "\n".join(lines)


def _judge_summary(score: AggregateScore) -> tuple[float | None, str]:
    """(mean judge-dimension score, latest judge detail incl. strengths/weaknesses),
    or (None, "") when the case was not judged."""
    values = [
        run.dimension_scores[JUDGE_DIMENSION]
        for run in score.run_scores
        if JUDGE_DIMENSION in run.dimension_scores
    ]
    if not values:
        return None, ""
    detail = ""
    for run in score.run_scores:
        for check in run.checks:
            if check.dimension == JUDGE_DIMENSION:
                detail = check.detail
    return sum(values) / len(values), detail.replace("\n", " ")


def aggregates_to_markdown(scores: list[AggregateScore]) -> str:
    judged = any(_judge_summary(s)[0] is not None for s in scores)
    if not judged:
        # Deterministic-only report (mock / CI): pass-rate is the headline.
        lines = [
            "| # | Case | Mean | Pass-rate | Runs | Std | Result |",
            "|---|---|---|---|---|---|---|",
        ]
        for index, score in enumerate(scores, start=1):
            result = "PASS" if score.passed else "FAIL"
            lines.append(
                f"| {index} | {score.case_id} | {score.score:.2f} | "
                f"{score.pass_rate:.2f} | {score.runs} | {score.stddev:.2f} | {result} |"
            )
        passed = sum(1 for score in scores if score.passed)
        lines += ["", f"**{passed}/{len(scores)} passed**"]
        return "\n".join(lines)

    # Judge mode: the judge score is the headline; the deterministic assertions
    # become a correctness gate (✓/✗), not the primary verdict.
    lines = ["| # | Case | Judge | 守門 |", "|---|---|---|---|"]
    judged_values: list[float] = []
    for index, score in enumerate(scores, start=1):
        jscore, _ = _judge_summary(score)
        gate = "✓" if score.passed else "✗"
        if jscore is None:
            lines.append(f"| {index} | {score.case_id} | — | {gate} |")
        else:
            judged_values.append(jscore)
            lines.append(f"| {index} | {score.case_id} | {jscore:.2f} | {gate} |")
    avg = sum(judged_values) / len(judged_values) if judged_values else 0.0
    gate_pass = sum(1 for s in scores if s.passed)
    lines += [
        "",
        f"**平均 Judge 分數：{avg:.2f}（{len(judged_values)} 案評分）；"
        f"確定性守門：{gate_pass}/{len(scores)} 通過**",
        "",
        "### 評分理由（優點 / 缺點）",
    ]
    for score in scores:
        jscore, detail = _judge_summary(score)
        if jscore is not None:
            lines.append(f"- **{score.case_id}**：{detail}")
    return "\n".join(lines)


def unweighted_dimension_warning(scores: list[AggregateScore]) -> str:
    """Name the cases whose checks ran in a dimension the case never weighted.

    Those dimensions are scored at full weight (see ``scoring.score_case``), so
    nothing is silently dropped any more — but the case file is still wrong, and
    an undeclared dimension is how the whole class of "decorative check" bugs
    started. Empty string when there is nothing to report.
    """

    offenders: dict[str, set[str]] = {}
    for score in scores:
        for run in score.run_scores:
            if run.unweighted_dimensions:
                offenders.setdefault(score.case_id, set()).update(run.unweighted_dimensions)
    if not offenders:
        return ""
    lines = [
        "### ⚠ 案例未宣告權重的維度（已以滿權重計分，但案例檔應補上）",
        "",
        "| Case | 未宣告的維度 |",
        "|---|---|",
    ]
    lines += [
        f"| {case_id} | {', '.join(sorted(dimensions))} |"
        for case_id, dimensions in sorted(offenders.items())
    ]
    return "\n".join(lines)


def aggregates_to_json(scores: list[AggregateScore]) -> str:
    payload = [
        {
            "case_id": score.case_id,
            "judge_score": _judge_summary(score)[0],
            "judge_detail": _judge_summary(score)[1],
            "mean_score": score.score,
            "deterministic_passed": score.passed,
            "passed": score.passed,
            "runs": score.runs,
            "pass_rate": score.pass_rate,
            "min_score": score.min_score,
            "max_score": score.max_score,
            "stddev": score.stddev,
            "run_scores": [
                {
                    "score": run.score,
                    "passed": run.passed,
                    "dimension_scores": run.dimension_scores,
                    "done_reason": run.done_reason,
                    "prompt_tokens": run.prompt_tokens,
                    "completion_tokens": run.completion_tokens,
                    "tool_call_count": run.tool_call_count,
                    "failure_category": run.failure_category,
                    "unweighted_dimensions": run.unweighted_dimensions,
                    "path_deviation": run.path_deviation,
                    "checks": [
                        {
                            "dimension": c.dimension,
                            "name": c.name,
                            "ok": c.ok,
                            "detail": c.detail,
                            "score": c.score,
                        }
                        for c in run.checks
                    ],
                }
                for run in score.run_scores
            ],
        }
        for score in scores
    ]
    return json.dumps(payload, indent=2)


def efficiency_summary_to_markdown(cases: list[EvalCase], scores: list[AggregateScore]) -> str:
    """Per-tag rollup of token usage and failure-category distribution.

    Report-only (never affects pass/fail) — lets M2-M5 tiers be compared on
    cost/failure-mode, not just pass-rate. See
    doc/detailed-design/10-assistant-eval.md §10.13/§10.15. Tags come from
    each case's own `tags` (e.g. "m2".."m5"), matched by case_id; a case with
    no matching mX tag or no llm_meta data is skipped.
    """

    by_id = {case.id: case for case in cases}
    tiers = ("m2", "m3", "m4", "m5")
    rows: list[str] = [
        "| Tier | Cases w/ tokens | Avg prompt | Avg completion | Avg 工具呼叫 | 路徑偏離 "
        "| Failure categories |"
    ]
    rows.append("|---|---|---|---|---|---|---|")
    for tier in tiers:
        prompt_tokens: list[int] = []
        completion_tokens: list[int] = []
        tool_calls: list[int] = []
        categories: dict[str, int] = {}
        total_runs = 0
        deviated_runs = 0
        for score in scores:
            case = by_id.get(score.case_id)
            if case is None or tier not in case.tags:
                continue
            for run in score.run_scores:
                total_runs += 1
                if run.prompt_tokens is not None:
                    prompt_tokens.append(run.prompt_tokens)
                if run.completion_tokens is not None:
                    completion_tokens.append(run.completion_tokens)
                if run.tool_call_count is not None:
                    tool_calls.append(run.tool_call_count)
                if run.failure_category is not None:
                    categories[run.failure_category] = categories.get(run.failure_category, 0) + 1
                if run.path_deviation is not None:
                    deviated_runs += 1
        if not prompt_tokens and not categories and total_runs == 0:
            continue
        avg_p = f"{sum(prompt_tokens) / len(prompt_tokens):.0f}" if prompt_tokens else "—"
        avg_c = (
            f"{sum(completion_tokens) / len(completion_tokens):.0f}" if completion_tokens else "—"
        )
        # The 07-24 review's second objective metric (token usage being the
        # first): how many tool calls a tier's plans take on average.
        avg_t = f"{sum(tool_calls) / len(tool_calls):.1f}" if tool_calls else "—"
        cat_str = (
            "、".join(f"{name}×{count}" for name, count in sorted(categories.items()))
            if categories
            else "（無失敗）"
        )
        # 2026-07-28 (alfred): non-gating — how often the model took a
        # different-but-still-passing path than the case's mock-script
        # "standard path", for analysing habitual behaviour, not scoring it.
        dev_str = f"{deviated_runs}/{total_runs}" if total_runs else "—"
        rows.append(
            f"| {tier} | {len(prompt_tokens)} | {avg_p} | {avg_c} | {avg_t} | {dev_str} "
            f"| {cat_str} |"
        )
    if len(rows) <= 2:
        return (
            "（本次無 token/failure_category 資料——需 `--mode api --llm real` 且回應含 llm_meta）"
        )
    return "\n".join(rows)


def to_markdown(scores: list[CaseScore]) -> str:
    lines = ["| # | Case | Score | Result |", "|---|---|---|---|"]
    for index, score in enumerate(scores, start=1):
        result = "PASS" if score.passed else "FAIL"
        lines.append(f"| {index} | {score.case_id} | {score.score:.2f} | {result} |")
    passed = sum(1 for score in scores if score.passed)
    lines.append("")
    lines.append(f"**{passed}/{len(scores)} passed**")
    return "\n".join(lines)


def to_json(scores: list[CaseScore]) -> str:
    payload = [
        {
            "case_id": score.case_id,
            "score": score.score,
            "passed": score.passed,
            "dimension_scores": score.dimension_scores,
            "checks": [
                {
                    "dimension": c.dimension,
                    "name": c.name,
                    "ok": c.ok,
                    "detail": c.detail,
                    "score": c.score,
                }
                for c in score.checks
            ],
        }
        for score in scores
    ]
    return json.dumps(payload, indent=2)

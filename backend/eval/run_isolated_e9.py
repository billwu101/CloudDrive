"""E9 階段 A driver: run the M2-M5 generated cases against a live backend +
real LLM, each case under its own freshly-registered test user.

Why not just `eval.run --mode api --llm real`: that CLI shares one token/test
account across the whole batch. Two problems for a 400-case x N-runs batch:
- `search` is a substring ILIKE match (app/search/repository.py), so repeated
  renames of the same seeded topic name (e.g. "報告" -> "報告_正式版") leave
  behind items that later collide with searches for the same topic across
  other cases/runs — contaminating pass/fail with environment noise, not
  model quality.
- access tokens expire in 30 min; a 400x3 real-model batch runs well past
  that and `eval.run`/`eval.runner` has no refresh logic (unlike
  eval/temp_sweep.py, which does).

This script isolates every (case, run) under its own throwaway registered
user, and writes one JSON line per finished case immediately (resumable via
--resume, and no data lost if a long batch is interrupted partway).

Usage:
    uv run python -m eval.run_isolated_e9 --base-url http://localhost:8001/api/v1 \
        --cases eval/cases/generated --runs 3 --out eval/out/e9_stage_a.jsonl \
        [--tag m2] [--resume] [--limit 5]
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from dataclasses import asdict
from pathlib import Path
from typing import Any

from eval.report import (
    aggregates_to_json,
    aggregates_to_markdown,
    efficiency_summary_to_markdown,
    unweighted_dimension_warning,
)
from eval.runner import (
    EvalRunnerError,
    confirm_workflow_http,
    pending_workflow_id,
    run_case_http,
)
from eval.schema import EvalCase, load_cases
from eval.scoring import AggregateScore, CaseScore, aggregate_runs, score_case
from eval.state import StateFetchError, fetch_items_http
from eval.verifier import (
    CheckResult,
    compute_path_deviation,
    count_tool_calls,
    step_results,
    verify,
    verify_codegen_execution,
    verify_reference_grounding,
    verify_reply_honesty,
    verify_required_skills,
    verify_state,
    verify_step_results,
)


def _register(base_url: str, stamp: str, *, timeout: float = 30.0) -> str:
    body = {
        "email": f"e9_{stamp}@example.com",
        "username": f"e9{stamp}",
        "password": "E9StageATest123!",
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/auth/register",
        data=json.dumps(body).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.load(response)
    token = data.get("access_token")
    if not isinstance(token, str) or not token:
        raise EvalRunnerError(f"register did not return access_token: {data!r}")
    return token


def _run_one_case(case: EvalCase, *, base_url: str, runs: int) -> AggregateScore:
    run_scores: list[CaseScore] = []
    for i in range(runs):
        # A fresh user per run too, not just per case: a case can itself take
        # long enough under real-model latency that reusing a case-scoped
        # token across runs risks the same 30-min expiry this script exists
        # to avoid.
        stamp = f"{case.id}-{i}-{int(time.time() * 1000)}"
        token = _register(base_url, stamp)
        response = run_case_http(case, base_url=base_url, token=token, timeout=180.0)
        # Real model: exact step sequence isn't guaranteed, only that a
        # sensible plan + confirmation tier was produced (matches eval.run's
        # --no-strict-steps behaviour for api+real). This alone does NOT prove
        # the plan was *correct* — that's what confirm+execute+state check
        # below is for.
        checks = verify(case, response, strict_steps=False)
        # Hard gate, unlike strict_steps: a write step must reference an
        # earlier step's real output, not a literal/guessed id (2026-07-28,
        # alfred: "順序很重要...一定要先search").
        checks = [*checks, *verify_reference_grounding(case, response)]
        # Hard gate too: with the case's data really seeded, skipping a
        # declared query tool is a modelling failure, not sequence noise.
        checks = [*checks, *verify_required_skills(case, response)]
        # M4: does the actually-generated code run, not just "proposed a
        # skill" (2026-07-28, alfred). Smoke test only — see
        # eval/codegen_smoke.py docstring for exact scope.
        checks = [*checks, *verify_codegen_execution(case, response)]

        # Unlike eval.run, this driver confirms every pending plan, not just
        # the cases carrying expect.state: each run here owns a throwaway
        # account, so executing costs nothing and keeps the observed state
        # faithful to what a real user would have after approving. Still
        # honours auto_confirm=False — those cases assert that nothing ran
        # *because* the user never approved.
        workflow_id = pending_workflow_id(response) if case.auto_confirm else None
        executed_results = step_results(response)  # auto-executed plans report here
        if workflow_id is not None:
            try:
                confirmed = confirm_workflow_http(base_url, token, workflow_id)
                executed_results = step_results(confirmed)
            except (urllib.error.URLError, EvalRunnerError) as exc:
                checks = [
                    *checks,
                    CheckResult("execution", "workflow confirm succeeded", False, str(exc)),
                ]
        # What happened *during* execution — every step ok, none skipped, the
        # declared read steps actually found something.
        checks = [*checks, *verify_step_results(case, executed_results)]

        state_checks: list[CheckResult] = []
        if case.expect.state is not None:
            try:
                items = fetch_items_http(base_url, token)
                state_checks = verify_state(case, items)
                checks = [*checks, *state_checks]
            except StateFetchError as exc:
                state_checks = [
                    CheckResult("state", "post-execution state fetch succeeded", False, str(exc))
                ]
                checks = [*checks, *state_checks]
        # Rule-based false-claim detector: reply says "done" while the state
        # says otherwise (2026-07-28 alfred — cheap alternative to an LLM judge).
        checks = [*checks, *verify_reply_honesty(case, response, state_checks)]

        llm_meta = response.get("llm_meta")
        plan_is_none = response.get("plan") is None
        path_deviation = compute_path_deviation(case, response)
        tool_call_count = count_tool_calls(response)
        run_scores.append(
            score_case(
                case,
                checks,
                llm_meta=llm_meta,
                plan_is_none=plan_is_none,
                path_deviation=path_deviation,
                tool_call_count=tool_call_count,
            )
        )
    return aggregate_runs(case, run_scores)


def _score_to_jsonable(score: AggregateScore) -> dict[str, Any]:
    payload = asdict(score)
    payload["run_scores"] = [
        {
            **{k: v for k, v in asdict(run).items() if k != "checks"},
            "checks": [asdict(c) for c in run.checks],
        }
        for run in score.run_scores
    ]
    return payload


def _score_from_jsonable(data: dict[str, Any]) -> AggregateScore:
    run_scores = [
        CaseScore(
            case_id=run["case_id"],
            score=run["score"],
            passed=run["passed"],
            dimension_scores=run["dimension_scores"],
            checks=[CheckResult(**c) for c in run["checks"]],
            done_reason=run.get("done_reason"),
            prompt_tokens=run.get("prompt_tokens"),
            completion_tokens=run.get("completion_tokens"),
            tool_call_count=run.get("tool_call_count"),
            failure_category=run.get("failure_category"),
            path_deviation=run.get("path_deviation"),
        )
        for run in data["run_scores"]
    ]
    return AggregateScore(
        case_id=data["case_id"],
        score=data["score"],
        passed=data["passed"],
        runs=data["runs"],
        pass_rate=data["pass_rate"],
        min_score=data["min_score"],
        max_score=data["max_score"],
        stddev=data["stddev"],
        run_scores=run_scores,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--cases", default="eval/cases/generated")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--out", default="eval/out/e9_stage_a.jsonl")
    parser.add_argument("--tag", default=None, help="only cases with this tag (e.g. m2)")
    parser.add_argument("--limit", type=int, default=0, help="0 = no limit")
    parser.add_argument("--resume", action="store_true", help="skip case_ids already in --out")
    args = parser.parse_args()

    cases = load_cases(args.cases)
    if args.tag:
        cases = [c for c in cases if args.tag in c.tags]
    if args.limit:
        cases = cases[: args.limit]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done_ids: set[str] = set()
    if args.resume and out_path.exists():
        for line in out_path.read_text().splitlines():
            if line.strip():
                done_ids.add(json.loads(line)["case_id"])

    with out_path.open("a") as fh:
        for index, case in enumerate(cases, start=1):
            if case.id in done_ids:
                print(f"[{index}/{len(cases)}] {case.id}: skip (already in {args.out})")
                continue
            try:
                score = _run_one_case(case, base_url=args.base_url, runs=args.runs)
            except (EvalRunnerError, urllib.error.URLError) as exc:
                print(f"[{index}/{len(cases)}] {case.id}: ERROR {exc}")
                continue
            fh.write(json.dumps(_score_to_jsonable(score)) + "\n")
            fh.flush()
            print(
                f"[{index}/{len(cases)}] {case.id}: pass_rate={score.pass_rate:.2f} "
                f"mean={score.score:.2f}"
            )

    all_scores = [
        _score_from_jsonable(json.loads(line))
        for line in out_path.read_text().splitlines()
        if line.strip()
    ]
    print()
    print(aggregates_to_markdown(all_scores))
    print()
    print("### 效率指標 / 失敗分類（依 tag 彙總，report-only）")
    print(efficiency_summary_to_markdown(cases, all_scores))
    warning = unweighted_dimension_warning(all_scores)
    if warning:
        print()
        print(warning)
    Path(str(out_path) + ".json").write_text(aggregates_to_json(all_scores))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

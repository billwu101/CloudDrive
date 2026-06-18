from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from eval.baseline import (
    compare_to_baseline,
    comparison_to_markdown,
    has_regression,
    load_baseline,
    save_baseline,
)
from eval.exec_runner import run_execution_case
from eval.inproc import run_case_inproc
from eval.judge import HttpJudgeModel, JudgeModel, judge_case
from eval.report import aggregates_to_json, aggregates_to_markdown
from eval.runner import run_case_http
from eval.runner_browser import run_browser_suite
from eval.schema import EvalCase, load_cases
from eval.scoring import AggregateScore, aggregate_runs, score_case
from eval.state import fetch_item_names_http
from eval.verifier import CheckResult, verify, verify_execution, verify_state


def main() -> int:
    parser = argparse.ArgumentParser(description="Assistant eval harness")
    parser.add_argument("--cases", default="eval/cases", help="Directory of *.yaml eval cases")
    parser.add_argument("--base-url", default="http://localhost:8001/api/v1")
    parser.add_argument(
        "--frontend-url",
        default="http://localhost:8088",
        help="Frontend origin for --mode browser (Playwright drives this)",
    )
    parser.add_argument("--token", default="", help="Bearer access token for the test user")
    parser.add_argument("--mode", choices=["api", "browser", "exec"], default="api")
    parser.add_argument(
        "--llm",
        choices=["mock", "real"],
        default="mock",
        help="mock = deterministic in-process runner (CI); real = HTTP against a live backend",
    )
    parser.add_argument(
        "--judge",
        action="store_true",
        help="Run the LLM judge on cases that declare an `expect.rubric` (needs --judge-base-url)",
    )
    parser.add_argument(
        "--judge-base-url",
        default=os.environ.get("JUDGE_BASE_URL", ""),
        help="OpenAI-compatible base URL for the judge model (recommend a separate model)",
    )
    parser.add_argument("--judge-model", default=os.environ.get("JUDGE_MODEL", ""))
    parser.add_argument("--judge-api-key", default=os.environ.get("JUDGE_API_KEY", ""))
    parser.add_argument(
        "--baseline",
        default="",
        help="Path to a baseline JSON; compare current scores and fail on regression",
    )
    parser.add_argument(
        "--save-baseline",
        default="",
        help="Write the current run's per-case scores to this path as a new baseline",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=0,
        help="Override each case's run count (0 = use the case's own `runs`); "
        "repeats a case to measure pass-rate/variance against a real model",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a Markdown table")
    parser.add_argument(
        "--browser-timeout",
        type=float,
        default=1800.0,
        help="Playwright suite timeout in seconds for --mode browser (large batches need more)",
    )
    args = parser.parse_args()

    cases = [case for case in load_cases(args.cases) if args.mode in case.mode]

    # Browser mode drives the real UI for the whole batch in one Playwright run,
    # then scores the captured /assistant/chat responses with the same verifier.
    browser_responses: dict[str, dict[str, Any]] = {}
    if args.mode == "browser":
        browser_responses = run_browser_suite(
            cases,
            base_url=args.frontend_url,
            api_base_url=args.base_url,
            timeout=args.browser_timeout,
        )

    judge = _build_judge(args)

    scores: list[AggregateScore] = []
    for case in cases:
        runs = args.runs if args.runs > 0 else max(1, case.runs)
        run_scores = []
        for _ in range(runs):
            if args.mode == "exec":
                checks = verify_execution(case, run_execution_case(case))
            elif args.mode == "browser" and case.expect.execute is not None:
                # Browser execution: the spec generated/approved/ran the skill on
                # the fixture and reported produced files + downloaded text.
                checks = verify_execution(case, browser_responses.get(case.id, {}))
            else:
                response = _run_case(case, args, browser_responses)
                # Browser/real plans are non-deterministic — don't gate on exact steps.
                checks = verify(case, response, strict_steps=args.mode != "browser")
                if judge is not None:
                    checks = checks + judge_case(case, response, judge)
                checks = checks + _state_checks(case, args)
            run_scores.append(score_case(case, checks))
        scores.append(aggregate_runs(case, run_scores))

    print(aggregates_to_json(scores) if args.json else aggregates_to_markdown(scores))

    if args.save_baseline:
        save_baseline(args.save_baseline, scores)

    regressed = False
    if args.baseline:
        comparisons = compare_to_baseline(scores, load_baseline(args.baseline))
        if not args.json:
            print()
            print(comparison_to_markdown(comparisons))
        regressed = has_regression(comparisons)

    passed = bool(scores) and all(score.passed for score in scores)
    return 0 if passed and not regressed else 1


def _state_checks(case: EvalCase, args: argparse.Namespace) -> list[CheckResult]:
    """Post-run state/safety assertions — only when a live snapshot is reachable
    (api mode against a real backend with a token). Skipped otherwise (the
    in-process mock runner has no real DB)."""

    if case.expect.state is None:
        return []
    if args.mode != "api" or args.llm != "real" or not args.token:
        return []
    item_names = fetch_item_names_http(args.base_url, args.token)
    return verify_state(case, item_names)


def _build_judge(args: argparse.Namespace) -> JudgeModel | None:
    if not args.judge:
        return None
    if not args.judge_base_url or not args.judge_model:
        sys.stderr.write(
            "error: --judge requires --judge-base-url and --judge-model "
            "(or JUDGE_BASE_URL / JUDGE_MODEL).\n"
        )
        raise SystemExit(2)
    return HttpJudgeModel(
        base_url=args.judge_base_url,
        model=args.judge_model,
        api_key=args.judge_api_key,
    )


def _run_case(
    case: EvalCase,
    args: argparse.Namespace,
    browser_responses: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if args.mode == "browser":
        return browser_responses.get(case.id, {})
    if args.llm == "mock":
        return run_case_inproc(case)
    return run_case_http(case, base_url=args.base_url, token=args.token)


if __name__ == "__main__":
    raise SystemExit(main())

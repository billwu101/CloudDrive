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
from eval.inproc import run_case_inproc
from eval.judge import HttpJudgeModel, JudgeModel, judge_case
from eval.report import to_json, to_markdown
from eval.runner import run_case_http
from eval.runner_browser import run_browser_suite
from eval.schema import EvalCase, load_cases
from eval.scoring import score_case
from eval.verifier import verify


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
    parser.add_argument("--mode", choices=["api", "browser"], default="api")
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
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a Markdown table")
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
        )

    judge = _build_judge(args)

    scores = []
    for case in cases:
        response = _run_case(case, args, browser_responses)
        checks = verify(case, response)
        if judge is not None:
            checks = checks + judge_case(case, response, judge)
        scores.append(score_case(case, checks))

    print(to_json(scores) if args.json else to_markdown(scores))

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

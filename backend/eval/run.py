from __future__ import annotations

import argparse
from typing import Any

from eval.inproc import run_case_inproc
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

    scores = []
    for case in cases:
        response = _run_case(case, args, browser_responses)
        scores.append(score_case(case, verify(case, response)))

    print(to_json(scores) if args.json else to_markdown(scores))
    return 0 if scores and all(score.passed for score in scores) else 1


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

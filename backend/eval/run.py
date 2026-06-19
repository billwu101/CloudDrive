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
from eval.judge import (
    CodexJudgeModel,
    HttpJudgeModel,
    JudgeError,
    JudgeModel,
    codex_auth_account,
    judge_case,
    judge_execution,
)
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
        help="Run the LLM judge on cases that declare an `expect.rubric`",
    )
    parser.add_argument(
        "--judge-provider",
        choices=["gemma", "codex", "openai"],
        default=os.environ.get("JUDGE_PROVIDER", "gemma"),
        help="Judge provider (default gemma). codex uses the developer's local "
        "`codex login`; openai/gemma use OpenAI-compatible HTTP.",
    )
    parser.add_argument(
        "--judge-base-url",
        default=os.environ.get("JUDGE_BASE_URL", ""),
        help="Override the OpenAI-compatible base URL for gemma/openai judge",
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
                exec_output = run_execution_case(case)
                checks = verify_execution(case, exec_output)
                if judge is not None:
                    checks = checks + judge_execution(
                        case, exec_output, judge, fallback_rubric=True
                    )
            elif args.mode == "browser" and case.expect.execute is not None:
                # Browser execution: the spec generated/approved/ran the skill on
                # the fixture and reported produced files + downloaded text.
                exec_output = browser_responses.get(case.id, {})
                checks = verify_execution(case, exec_output)
                if judge is not None:
                    checks = checks + judge_execution(
                        case, exec_output, judge, fallback_rubric=True
                    )
            else:
                response = _run_case(case, args, browser_responses)
                # Browser/real plans are non-deterministic — don't gate on exact steps.
                checks = verify(case, response, strict_steps=args.mode != "browser")
                if judge is not None:
                    checks = checks + judge_case(case, response, judge, fallback_rubric=True)
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

    provider = args.judge_provider
    if provider == "codex":
        # Developer's local `codex login`. Pre-flight: surface which account will
        # be billed, and fail clearly if nobody is logged in.
        try:
            account = codex_auth_account()
        except JudgeError as exc:
            sys.stderr.write(f"error: {exc}\n")
            raise SystemExit(2) from exc
        sys.stderr.write(f"[judge] provider=codex, account={account}\n")
        return CodexJudgeModel(codex_bin=os.environ.get("CODEX_BIN", "codex"))

    # gemma / openai → OpenAI-compatible HTTP. Provider picks the defaults;
    # --judge-base-url / --judge-model override them.
    if provider == "openai":
        base_url = args.judge_base_url or "https://api.openai.com/v1"
        model = args.judge_model or "gpt-5.5"
        if not args.judge_api_key:
            sys.stderr.write(
                "error: --judge-provider openai needs --judge-api-key (or JUDGE_API_KEY).\n"
            )
            raise SystemExit(2)
    else:  # gemma (default): a local Ollama OpenAI-compatible endpoint
        base_url = args.judge_base_url or "http://localhost:11434/v1"
        model = args.judge_model or "gemma3:12b"

    return HttpJudgeModel(base_url=base_url, model=model, api_key=args.judge_api_key)


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

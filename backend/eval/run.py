from __future__ import annotations

import argparse

from eval.report import to_json, to_markdown
from eval.runner import run_case_http
from eval.schema import load_cases
from eval.scoring import score_case
from eval.verifier import verify


def main() -> int:
    parser = argparse.ArgumentParser(description="Assistant eval harness (E1 API runner skeleton)")
    parser.add_argument("--cases", default="eval/cases", help="Directory of *.yaml eval cases")
    parser.add_argument("--base-url", default="http://localhost:8001/api/v1")
    parser.add_argument("--token", default="", help="Bearer access token for the test user")
    parser.add_argument("--mode", choices=["api", "browser"], default="api")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a Markdown table")
    args = parser.parse_args()

    cases = [case for case in load_cases(args.cases) if args.mode in case.mode]
    scores = []
    for case in cases:
        response = run_case_http(case, base_url=args.base_url, token=args.token)
        scores.append(score_case(case, verify(case, response)))

    print(to_json(scores) if args.json else to_markdown(scores))
    return 0 if scores and all(score.passed for score in scores) else 1


if __name__ == "__main__":
    raise SystemExit(main())

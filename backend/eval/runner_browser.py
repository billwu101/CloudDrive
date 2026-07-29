from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from eval.schema import EvalCase

# repo/backend/eval/runner_browser.py -> repo/frontend
_FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


class BrowserRunnerError(Exception):
    """Raised when the Playwright eval suite cannot be driven or produced no output."""


def build_payload(cases: list[EvalCase]) -> list[dict[str, Any]]:
    """The per-case JSON the Playwright spec consumes.

    Extracted from ``run_browser_suite`` so the API-mode/browser-mode parity
    that keeps breaking (``seed_folders`` in 2026-07-27, ``seed_files`` in the
    2026-07-28 audit) is unit-testable without driving a real browser: every
    field a case needs seeded in API mode must appear here too.
    """

    payload: list[dict[str, Any]] = []
    for case in cases:
        item: dict[str, Any] = {
            "id": case.id,
            "prompt": case.prompt,
            "auto_confirm": case.auto_confirm,
        }
        if case.seed_folders:
            item["seed_folders"] = case.seed_folders
        if case.seed_files:
            # Normalised to {fixture, name} pairs: a plain string is a fixture
            # uploaded under its own name, a SeedFile renames it (the
            # filename-classification cases upload one fixture as 發票A.pdf,
            # 考卷B.pdf …). Passing the SeedFile objects through unconverted
            # made json.dumps raise before Playwright even started — found the
            # first time browser mode was actually run, 2026-07-29.
            item["seed_files"] = [
                {"fixture": entry, "name": entry}
                if isinstance(entry, str)
                else {"fixture": entry.fixture, "name": entry.name}
                for entry in case.seed_files
            ]
        # Execution cases also drive approve → run-on-fixture → assert output.
        if case.expect.execute is not None:
            ex = case.expect.execute
            item["execute"] = {
                "fixture": ex.fixture,
                "context_menu_label": ex.context_menu_label,
            }
        payload.append(item)
    return payload


def run_browser_suite(
    cases: list[EvalCase],
    *,
    frontend_dir: Path | None = None,
    base_url: str = "http://localhost:8088",
    api_base_url: str = "http://localhost:8001/api/v1",
    email: str | None = None,
    username: str | None = None,
    password: str = "E2ePassword123!",
    timeout: float = 1800.0,
) -> dict[str, dict[str, Any]]:
    """Drive the assistant UI for every case in one Playwright invocation.

    Bridges to ``frontend/e2e/assistant/assistant-eval.spec.ts``: writes the
    selected cases to a temp JSON file, runs the spec against an already-running
    frontend (the Docker stack at ``base_url`` by default), and reads back the
    captured ``/assistant/chat`` response per case id. Those responses feed the
    same deterministic verifier/scoring used by the API and in-process runners.

    ``seed_folders`` (real folders a case's prompt needs to already exist,
    e.g. M3/M5 scenarios) and ``seed_files`` (fixtures from ``eval/fixtures/``
    a case needs on the drive, e.g. the ``organize_by_type`` scenarios) are
    passed through in the payload; the spec creates/uploads them via the
    backend API before sending the prompt — mirroring ``runner.py``'s
    ``_seed_folders``/``_seed_files`` for the API-mode runner. Both must stay
    in step with the API runner: a case seeded in one mode but not the other
    produces failures that say nothing about the model.
    """

    if not cases:
        return {}

    fe_dir = Path(frontend_dir) if frontend_dir is not None else _FRONTEND_DIR
    if not (fe_dir / "playwright.eval.config.ts").exists():
        raise BrowserRunnerError(f"playwright.eval.config.ts not found under {fe_dir}")

    stamp = str(int(time.time()))
    fixtures_dir = Path(__file__).resolve().parent / "fixtures"
    payload = build_payload(cases)

    with tempfile.TemporaryDirectory(prefix="assistant_eval_") as tmp:
        cases_file = Path(tmp) / "cases.json"
        results_file = Path(tmp) / "results.json"
        cases_file.write_text(json.dumps(payload))

        env = {
            **os.environ,
            "EVAL_CASES_FILE": str(cases_file),
            "EVAL_RESULTS_FILE": str(results_file),
            "EVAL_BASE_URL": base_url,
            "EVAL_API_BASE_URL": api_base_url,
            "EVAL_STAMP": stamp,
            "EVAL_FIXTURES_DIR": str(fixtures_dir),
            "EVAL_EMAIL": email or f"eval_{stamp}@example.com",
            "EVAL_USERNAME": username or f"eval{stamp}",
            "EVAL_PASSWORD": password,
            "PLAYWRIGHT_BROWSERS_PATH": os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ".playwright"),
        }

        cmd = [
            "npx",
            "playwright",
            "test",
            "--config=playwright.eval.config.ts",
        ]
        try:
            proc = subprocess.run(
                cmd,
                cwd=fe_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise BrowserRunnerError(
                "npx/playwright not found — run `npm ci` and "
                "`npm run playwright:install` in frontend/"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise BrowserRunnerError(f"Playwright eval suite timed out after {timeout}s") from exc

        # The spec writes results even when a UI assertion fails, so a non-zero
        # exit code (a failed UI assertion) still yields backend responses to
        # score — we just surface the Playwright output as a warning.
        if proc.returncode != 0:
            sys.stderr.write(
                "warning: Playwright eval suite reported failures "
                f"(exit {proc.returncode}).\n{proc.stdout}\n{proc.stderr}\n"
            )

        if not results_file.exists():
            raise BrowserRunnerError(
                "Playwright eval suite produced no results file.\n"
                f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
            )

        raw = json.loads(results_file.read_text())

    if not isinstance(raw, dict):
        raise BrowserRunnerError(f"unexpected results payload type {type(raw)!r}")
    return {str(case_id): body for case_id, body in raw.items()}


def run_case_browser(
    case: EvalCase,
    *,
    base_url: str = "http://localhost:8088",
    api_base_url: str = "http://localhost:8001/api/v1",
    **kwargs: Any,
) -> dict[str, Any]:
    """Single-case convenience wrapper (drives the suite for just this case)."""

    responses = run_browser_suite([case], base_url=base_url, api_base_url=api_base_url, **kwargs)
    return responses.get(case.id, {})

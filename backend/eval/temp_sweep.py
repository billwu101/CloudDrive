"""Temperature sweep for structured decoding (DEC-031 follow-up experiment).

Measures, for each candidate ``LLM_STRUCTURED_TEMPERATURE``, how often the
real local model (a) fails/loops on planner requests and (b) produces plans
that pass the deterministic eval assertions. Two failure modes pull in
opposite directions — too cold loops (repetition), too hot drifts (wrong
plans) — so the output is a per-temperature table of both rates plus latency.

This is a **developer measurement tool**, not a test: it lives outside
``tests/`` so pytest/CI never collect it, and it needs a reachable Ollama +
the dev database. Run it detached so an SSH/IDE disconnect can't kill it:

    cd backend
    nohup uv run python -m eval.temp_sweep > /tmp/temp_sweep.log 2>&1 &

Results land in ``eval/out/temp_sweep_<timestamp>.{json,md}`` — read them any
time after the run finishes. Each temperature boots a fresh backend on
``--port`` (default 8010) with the overridden env, so the run leaves your dev
server untouched. Re-run whenever the model or the planner prompt changes;
single measurements go stale, the instrument doesn't.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eval.runner import EvalRunnerError, run_case_http
from eval.schema import EvalCase, load_cases
from eval.scoring import score_case
from eval.verifier import verify

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_CASE_IDS = [
    "storage-quota-read",  # the prompt family that looped at temperature 0
    "read-only-list",
    "create-folder-write",
    "safety-destructive-confirm",
]
# A request slower than this is almost certainly looping (normal plans on the
# reference hardware finish in well under a minute).
_LOOP_SUSPECT_SECONDS = 100.0
# Above the backend's own 300s LLM read timeout: we want to observe the
# backend's verdict (retry/503), not clip the sample at the HTTP client.
_SAMPLE_TIMEOUT_SECONDS = 660.0


def _post_json(url: str, body: dict[str, Any], timeout: float = 15.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.load(response)
    return data if isinstance(data, dict) else {}


def _wait_ready(base_url: str, timeout_sec: float = 90.0) -> None:
    deadline = time.monotonic() + timeout_sec
    login = f"{base_url}/auth/login"
    while time.monotonic() < deadline:
        try:
            _post_json(login, {})
        except urllib.error.HTTPError as exc:
            if exc.code == 422:  # validation error == app is up and routing
                return
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(1)
    raise RuntimeError(f"backend at {base_url} not ready within {timeout_sec}s")


def _register_and_login(base_url: str, tag: str) -> str:
    stamp = f"{tag}{int(time.time())}"
    email, password = f"sweep-{stamp}@test.local", "SweepPass123!"
    _post_json(
        f"{base_url}/auth/register",
        {"email": email, "password": password, "username": f"sweep{stamp}"},
    )
    token = _post_json(f"{base_url}/auth/login", {"email": email, "password": password}).get(
        "access_token"
    )
    if not isinstance(token, str) or not token:
        raise RuntimeError("login returned no access token")
    return token


def _boot_backend(port: int, temperature: float) -> subprocess.Popen[bytes]:
    env = {**os.environ, "LLM_STRUCTURED_TEMPERATURE": str(temperature)}
    return subprocess.Popen(
        ["uv", "run", "uvicorn", "app.main:app", "--port", str(port)],
        cwd=_BACKEND_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # own process group -> clean kill of workers
    )


def _stop_backend(proc: subprocess.Popen[bytes]) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    with contextlib.suppress(subprocess.TimeoutExpired):
        proc.wait(timeout=15)


def _run_sample(case: EvalCase, base_url: str, token: str) -> dict[str, Any]:
    started = time.monotonic()
    try:
        response = run_case_http(
            case, base_url=base_url, token=token, timeout=_SAMPLE_TIMEOUT_SECONDS
        )
    except EvalRunnerError as exc:
        elapsed = time.monotonic() - started
        return {
            "case": case.id,
            "ok": False,
            "request_failed": True,
            "loop_suspect": elapsed >= _LOOP_SUSPECT_SECONDS,
            "seconds": round(elapsed, 1),
            "error": str(exc)[:200],
        }
    elapsed = time.monotonic() - started
    checks = verify(case, response, strict_steps=False)  # real model: robust checks
    scored = score_case(case, checks)
    return {
        "case": case.id,
        "ok": scored.passed,
        "request_failed": False,
        "loop_suspect": elapsed >= _LOOP_SUSPECT_SECONDS,
        "seconds": round(elapsed, 1),
        "score": round(scored.score, 3),
    }


def _summarise(temperature: float, samples: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(samples)
    durations = [s["seconds"] for s in samples]
    return {
        "temperature": temperature,
        "runs": total,
        "pass_rate": round(sum(1 for s in samples if s["ok"]) / total, 3) if total else 0.0,
        "request_fail_rate": (
            round(sum(1 for s in samples if s["request_failed"]) / total, 3) if total else 0.0
        ),
        "loop_suspects": sum(1 for s in samples if s["loop_suspect"]),
        "mean_seconds": round(sum(durations) / total, 1) if total else 0.0,
        "max_seconds": max(durations) if durations else 0.0,
        "samples": samples,
    }


def _to_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Temperature | Pass rate | Request failures | Loop suspects | Mean s | Max s |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['temperature']} | {row['pass_rate']:.0%} | {row['request_fail_rate']:.0%} "
            f"| {row['loop_suspects']}/{row['runs']} "
            f"| {row['mean_seconds']} | {row['max_seconds']} |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--temps", default="0.2,0.4,0.6,0.8", help="comma-separated temperatures")
    parser.add_argument("--runs", type=int, default=5, help="samples per case per temperature")
    parser.add_argument("--port", type=int, default=8010, help="port for the throwaway backend")
    parser.add_argument("--cases-dir", default=str(_BACKEND_DIR / "eval" / "cases"))
    parser.add_argument("--case-ids", default=",".join(_DEFAULT_CASE_IDS))
    parser.add_argument("--out-dir", default=str(_BACKEND_DIR / "eval" / "out"))
    args = parser.parse_args()

    wanted = {cid.strip() for cid in args.case_ids.split(",") if cid.strip()}
    cases = [c for c in load_cases(args.cases_dir) if c.id in wanted]
    if not cases:
        raise SystemExit(f"no cases matched ids: {sorted(wanted)}")
    base_url = f"http://127.0.0.1:{args.port}/api/v1"

    results: list[dict[str, Any]] = []
    for raw_temp in args.temps.split(","):
        temperature = float(raw_temp)
        print(f"[sweep] temperature={temperature}: booting backend on :{args.port}", flush=True)
        proc = _boot_backend(args.port, temperature)
        try:
            _wait_ready(base_url)
            token = _register_and_login(base_url, tag=str(temperature).replace(".", ""))
            # Warm-up: the model may need a cold (re)load after keep_alive
            # expiry; without this the first sample conflates load time with a
            # loop. Discarded from the stats.
            warmup = _run_sample(cases[0], base_url, token)
            print(f"[sweep]   warmup (discarded): {warmup}", flush=True)
            samples: list[dict[str, Any]] = []
            for case in cases:
                for i in range(args.runs):
                    sample = _run_sample(case, base_url, token)
                    samples.append(sample)
                    print(f"[sweep]   {case.id} run {i + 1}/{args.runs}: {sample}", flush=True)
        finally:
            _stop_backend(proc)
        results.append(_summarise(temperature, samples))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    (out_dir / f"temp_sweep_{stamp}.json").write_text(json.dumps(results, indent=2))
    markdown = _to_markdown(results)
    (out_dir / f"temp_sweep_{stamp}.md").write_text(markdown + "\n")
    print(markdown, flush=True)
    print(f"[sweep] results written to {out_dir}/temp_sweep_{stamp}.{{json,md}}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

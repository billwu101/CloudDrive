from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from eval.schema import EvalCase
from eval.verifier import CheckResult

JUDGE_DIMENSION = "judge"
_DEFAULT_THRESHOLD = 0.7


class JudgeError(Exception):
    """Raised when the judge model cannot be reached or its reply is unparseable."""


@dataclass(frozen=True)
class JudgeVerdict:
    score: float
    reasoning: str


class JudgeModel(Protocol):
    """A raw text-completion callable. Decoupled from the assistant LLM stack so
    the judge can run against an independent model (recommended) and be faked in
    tests."""

    def complete(self, prompt: str) -> str: ...


_SYSTEM = (
    "You are a strict evaluator of an AI file-assistant. Judge ONLY against the "
    "given rubric. Reply with a single JSON object: "
    '{"score": <float 0..1>, "reasoning": "<one sentence>"}. '
    "1.0 = fully satisfies the rubric, 0.0 = fails it. No prose outside the JSON."
)


def build_judge_prompt(*, rubric: str, prompt: str, response: dict[str, Any]) -> str:
    """Render the judging prompt from the case rubric + the assistant response.

    Only the user-facing message and the produced plan are shown — enough to
    judge intent and behaviour without leaking the harness internals.
    """

    plan = response.get("plan") or {}
    steps = plan.get("steps", []) if isinstance(plan, dict) else []
    skills = [s.get("skill") for s in steps if isinstance(s, dict)]
    proposal = response.get("skill_proposal") or {}
    proposed = proposal.get("name") if isinstance(proposal, dict) else None
    summary = {
        "user_prompt": prompt,
        "assistant_message": response.get("message", ""),
        "plan_status": plan.get("status") if isinstance(plan, dict) else None,
        "plan_skills": skills,
        "proposed_skill": proposed,
    }
    return (
        f"{_SYSTEM}\n\nRUBRIC:\n{rubric}\n\n"
        f"ASSISTANT RESPONSE (summarised):\n{json.dumps(summary, ensure_ascii=False, indent=2)}\n\n"
        'Return JSON only, e.g. {"score": 0.9, "reasoning": "..."}.'
    )


_MAX_CONTENT_CHARS = 500


def build_exec_judge_prompt(*, rubric: str, prompt: str, exec_output: dict[str, Any]) -> str:
    """Render a judging prompt from the rubric + a skill's *actual execution
    output* (produced files and their text), so the judge can score whether the
    effect matches the user's intent — not just the chat plan. Long file contents
    are truncated and binary outputs marked, to keep the prompt bounded."""

    raw_outputs = exec_output.get("outputs") or {}
    file_contents: dict[str, str] = {}
    if isinstance(raw_outputs, dict):
        for name, content in raw_outputs.items():
            if content is None:
                file_contents[str(name)] = "<binary>"
            else:
                text = str(content)
                truncated = text[:_MAX_CONTENT_CHARS]
                file_contents[str(name)] = truncated + (
                    "…" if len(text) > _MAX_CONTENT_CHARS else ""
                )
    summary = {
        "user_prompt": prompt,
        "execution_ok": exec_output.get("ok"),
        "error": exec_output.get("error"),
        "produced_files": exec_output.get("produced_files", []),
        "file_contents": file_contents,
    }
    body = json.dumps(summary, ensure_ascii=False, indent=2)
    return (
        f"{_SYSTEM}\n\nRUBRIC:\n{rubric}\n\n"
        f"SKILL EXECUTION RESULT (summarised):\n{body}\n\n"
        'Return JSON only, e.g. {"score": 0.9, "reasoning": "..."}.'
    )


def parse_verdict(text: str) -> JudgeVerdict:
    """Pull the {score, reasoning} JSON out of a model reply, tolerating code
    fences or surrounding prose, and clamp the score to [0, 1]."""

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise JudgeError(f"judge reply has no JSON object: {text[:200]!r}")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise JudgeError(f"judge reply is not valid JSON: {text[:200]!r}") from exc
    if not isinstance(data, dict) or "score" not in data:
        raise JudgeError(f"judge reply missing 'score': {data!r}")
    try:
        score = float(data["score"])
    except (TypeError, ValueError) as exc:
        raise JudgeError(f"judge score is not a number: {data.get('score')!r}") from exc
    score = max(0.0, min(1.0, score))
    reasoning = str(data.get("reasoning", "")).strip()
    return JudgeVerdict(score=score, reasoning=reasoning)


def _run_judge(model: JudgeModel, prompt: str, threshold: float, name: str) -> list[CheckResult]:
    """Complete the judge prompt and turn the verdict into one judge-dimension
    CheckResult carrying the continuous rubric score (scoring averages it like
    any other dimension)."""
    verdict = parse_verdict(model.complete(prompt))
    return [
        CheckResult(
            dimension=JUDGE_DIMENSION,
            name=name,
            ok=verdict.score >= threshold,
            detail=f"score={verdict.score:.2f} — {verdict.reasoning}",
            score=verdict.score,
        )
    ]


def judge_case(
    case: EvalCase,
    response: dict[str, Any],
    model: JudgeModel,
    *,
    threshold: float = _DEFAULT_THRESHOLD,
) -> list[CheckResult]:
    """Judge a chat case against its rubric (plan/message). No rubric → no checks."""
    rubric = case.expect.rubric
    if not rubric:
        return []
    prompt = build_judge_prompt(rubric=rubric, prompt=case.prompt, response=response)
    return _run_judge(model, prompt, threshold, "rubric judgement")


def judge_execution(
    case: EvalCase,
    exec_output: dict[str, Any],
    model: JudgeModel,
    *,
    threshold: float = _DEFAULT_THRESHOLD,
) -> list[CheckResult]:
    """Judge a skill's *actual execution output* against its rubric (the effect,
    not just the plan). No rubric → no checks, so non-rubric exec cases are
    unaffected."""
    rubric = case.expect.rubric
    if not rubric:
        return []
    prompt = build_exec_judge_prompt(rubric=rubric, prompt=case.prompt, exec_output=exec_output)
    return _run_judge(model, prompt, threshold, "rubric judgement (execution)")


class HttpJudgeModel:
    """OpenAI-compatible /chat/completions judge (e.g. a separate Ollama model).

    Synchronous (urllib) to match the rest of the eval harness; kept independent
    of ``app.assistant.llm`` so the judge model can differ from the model under
    test.
    """

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout: float = 60.0,
    ) -> None:
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._model = model
        self._api_key = api_key
        self._timeout = timeout

    def complete(self, prompt: str) -> str:
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "stream": False,
        }
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        request = urllib.request.Request(
            self._url, data=json.dumps(payload).encode(), method="POST", headers=headers
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as resp:
                body = json.load(resp)
        except Exception as exc:
            raise JudgeError(f"judge model request failed: {exc}") from exc
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise JudgeError(f"unexpected judge response shape: {body!r}") from exc
        if not isinstance(content, str):
            raise JudgeError("judge response content must be a string")
        return content


# (cmd, timeout) -> (returncode, combined stdout+stderr). Injectable for tests.
CodexRunner = Callable[[list[str], float], tuple[int, str]]


def _default_codex_runner(cmd: list[str], timeout: float) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise JudgeError(f"codex judge subprocess failed: {exc}") from exc
    return proc.returncode, proc.stdout + proc.stderr


def _extract_codex_reply(output: str) -> str:
    """Pull the assistant reply out of `codex exec` output — the CLI frames it
    after a ``codex`` line and before a ``tokens used`` line. Necessary because
    the prompt itself contains JSON; without trimming, parse_verdict would latch
    onto the echoed prompt. (Same framing as external_model.codex_client.)"""
    if "\ncodex\n" in output:
        tail = output.rsplit("\ncodex\n", 1)[-1]
        return re.split(r"\ntokens used\b", tail)[0].strip()
    return output.strip()


def codex_auth_account(codex_home: str | None = None) -> str:
    """Read ``account_id`` from the developer's local codex ``auth.json`` for an
    audit hint. Raises :class:`JudgeError` (telling the dev to ``codex login``)
    when no token is present — the only "judge identity" check there is: codex
    keys off whether ``$CODEX_HOME/auth.json`` holds a token, not who you are."""
    home = codex_home or os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex")
    auth_path = os.path.join(home, "auth.json")
    if not os.path.exists(auth_path):
        raise JudgeError(f"no codex login at {auth_path} — run `codex login` first")
    try:
        with open(auth_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise JudgeError(f"cannot read codex auth.json: {exc}") from exc
    tokens = data.get("tokens") if isinstance(data.get("tokens"), dict) else {}
    account = data.get("account_id") or tokens.get("account_id")
    return str(account) if account else "<unknown>"


class CodexJudgeModel:
    """Judge backed by a developer's local Codex subscription (`codex login`).

    Single-developer / local: uses the machine's ``~/.codex`` (or ``CODEX_HOME``)
    directly via ``codex exec`` — no per-request isolation, encryption, or async
    (those are EM3 multi-tenant concerns). Synchronous, to match the rest of the
    eval harness."""

    def __init__(
        self,
        *,
        codex_bin: str = "codex",
        timeout: float = 120.0,
        runner: CodexRunner | None = None,
    ) -> None:
        self._codex_bin = codex_bin
        self._timeout = timeout
        self._runner = runner or _default_codex_runner

    def complete(self, prompt: str) -> str:
        cmd = [self._codex_bin, "exec", "--skip-git-repo-check", prompt]
        returncode, output = self._runner(cmd, self._timeout)
        if returncode != 0:
            raise JudgeError(f"codex judge exited {returncode}: {output[:200]!r}")
        return _extract_codex_reply(output)

from __future__ import annotations

import json
import re
import urllib.request
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


def judge_case(
    case: EvalCase,
    response: dict[str, Any],
    model: JudgeModel,
    *,
    threshold: float = _DEFAULT_THRESHOLD,
) -> list[CheckResult]:
    """Run the LLM judge for a case that declares a rubric.

    Returns a single ``judge``-dimension :class:`CheckResult` carrying the
    continuous rubric score (so scoring averages it like any other dimension);
    cases without a rubric yield no checks.
    """

    rubric = case.expect.rubric
    if not rubric:
        return []

    prompt = build_judge_prompt(rubric=rubric, prompt=case.prompt, response=response)
    verdict = parse_verdict(model.complete(prompt))
    return [
        CheckResult(
            dimension=JUDGE_DIMENSION,
            name="rubric judgement",
            ok=verdict.score >= threshold,
            detail=f"score={verdict.score:.2f} — {verdict.reasoning}",
            score=verdict.score,
        )
    ]


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

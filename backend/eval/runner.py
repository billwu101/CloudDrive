from __future__ import annotations

import json
import urllib.request
from typing import Any

from eval.schema import EvalCase


class EvalRunnerError(Exception):
    """Raised when a case cannot be executed against the backend."""


def run_case_http(
    case: EvalCase,
    *,
    base_url: str,
    token: str,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """API-mode runner: POST the case prompt to a live backend /assistant/chat.

    This drives whatever backend is running at base_url. For deterministic CI
    runs the backend should be configured with a mock LLM (follow-up within E1).
    """

    url = base_url.rstrip("/") + "/assistant/chat"
    data = json.dumps({"message": case.prompt}).encode()
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.load(response)
    except Exception as exc:
        raise EvalRunnerError(f"case {case.id} failed: {exc}") from exc
    if not isinstance(body, dict):
        raise EvalRunnerError(f"case {case.id}: unexpected response type {type(body)!r}")
    return body

from __future__ import annotations

import json
import urllib.error
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
    """API-mode runner: drive a case against a live backend /assistant/chat.

    Single-turn cases POST ``case.prompt`` and return the response. Multi-turn
    cases (conversation memory) first create ``seed_folders`` at the drive root,
    then replay ``context_turns`` on one session to build history, and finally
    send ``prompt`` on that same session — returning the last turn's response so
    the verifier can assert the reference resolved.
    """

    root = base_url.rstrip("/")
    if case.seed_folders:
        _seed_folders(root, token, case.seed_folders, timeout=timeout)

    session_id: str | None = None
    for turn in case.context_turns:
        prior = _chat(root, token, message=turn, session_id=session_id, timeout=timeout)
        session_id = prior.get("session_id") or session_id

    return _chat(root, token, message=case.prompt, session_id=session_id, timeout=timeout)


def _chat(
    root: str, token: str, *, message: str, session_id: str | None, timeout: float
) -> dict[str, Any]:
    body: dict[str, Any] = {"message": message}
    if session_id is not None:
        body["session_id"] = session_id
    return _post(f"{root}/assistant/chat", body, token, timeout=timeout)


def _seed_folders(root: str, token: str, names: list[str], *, timeout: float) -> None:
    """Create each folder at the root; an already-existing name (409) is reused so
    seeding is idempotent across repeated runs against the same test user."""
    for name in names:
        try:
            _post(
                f"{root}/drive/folders", {"name": name, "parent_id": None}, token, timeout=timeout
            )
        except EvalRunnerError as exc:
            if "409" not in str(exc):
                raise


def _post(url: str, body: dict[str, Any], token: str, *, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        raise EvalRunnerError(f"POST {url} failed: {exc.code} {exc.reason}") from exc
    except Exception as exc:
        raise EvalRunnerError(f"POST {url} failed: {exc}") from exc
    if not isinstance(data, dict):
        raise EvalRunnerError(f"POST {url}: unexpected response type {type(data)!r}")
    return data

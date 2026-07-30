from __future__ import annotations

import json
import mimetypes
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from eval.schema import EvalCase, SeedFile

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


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
    cases (conversation memory) first create ``seed_folders``/``seed_files`` at
    the drive root, then replay ``context_turns`` on one session to build
    history, and finally send ``prompt`` on that same session — returning the
    last turn's response so the verifier can assert the reference resolved.
    """

    root = base_url.rstrip("/")
    if case.seed_folders:
        _seed_folders(root, token, case.seed_folders, timeout=timeout)
    if case.seed_files:
        _seed_files(root, token, case.seed_files, timeout=timeout)

    session_id: str | None = None
    for turn in case.context_turns:
        prior = _chat(root, token, message=turn, session_id=session_id, timeout=timeout)
        session_id = prior.get("session_id") or session_id

    return _chat(root, token, message=case.prompt, session_id=session_id, timeout=timeout)


def confirm_workflow_http(
    base_url: str, token: str, workflow_id: str, *, timeout: float = 180.0
) -> dict[str, Any]:
    """POST /assistant/workflows/{id}/confirm — actually execute a pending plan.

    Without this, a "pass" only means the model produced *some* plan; it never
    proves the ``seed_folders``/``ref_search`` grounding resolved to the right
    real item and actually did the right thing (2026-07-27, alfred: 還是要驗證他做
    的對不對吧, 否則沒有意義). Any caller asserting ``expect.state`` must
    call this first, or it will assert a state nobody ever executed.

    Deliberately ``retries=1`` unlike the chat calls: a confirm that fails
    *after* partially executing must not be replayed, or the retry re-runs the
    write steps that already happened.
    """

    return _post(
        f"{base_url.rstrip('/')}/assistant/workflows/{workflow_id}/confirm",
        {},
        token,
        timeout=timeout,
        retries=1,
    )


def pending_workflow_id(response: Mapping[str, Any]) -> str | None:
    """The workflow id of a plan awaiting approval, or None if there is nothing
    to execute (no plan, auto-executed already, or a skill proposal instead)."""

    plan = response.get("plan")
    if not isinstance(plan, Mapping):
        return None
    if plan.get("status") != "pending_approval":
        return None
    workflow_id = plan.get("workflow_id")
    return str(workflow_id) if workflow_id else None


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


def _seed_files(root: str, token: str, entries: list[str | SeedFile], *, timeout: float) -> None:
    """Upload each named fixture (from eval/fixtures/) to the drive root via
    POST /upload/simple — gives a case a real file with a known extension, so
    an outcome like organize_by_type's ``{ext}-files`` folders is deterministic
    and checkable via expect.state, not just "did it produce a plan".

    A ``SeedFile`` entry uploads that fixture's bytes under a different name:
    filename-classification cases need many meaningfully-named files
    (發票A.pdf, 考卷B.pdf ...) whose content is irrelevant.
    """
    for entry in entries:
        fixture = entry if isinstance(entry, str) else entry.fixture
        upload_name = entry if isinstance(entry, str) else entry.name
        path = _FIXTURES_DIR / fixture
        if not path.is_file():
            raise EvalRunnerError(f"seed_files: fixture not found: {path}")
        _upload_simple(root, token, path, timeout=timeout, upload_name=upload_name)


def _upload_simple(
    root: str, token: str, path: Path, *, timeout: float, upload_name: str | None = None
) -> None:
    name = upload_name or path.name
    boundary = uuid.uuid4().hex
    mime_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    body = (
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode()
        + path.read_bytes()
        + f"\r\n--{boundary}--\r\n".encode()
    )
    request = urllib.request.Request(
        f"{root}/upload/simple",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        raise EvalRunnerError(f"upload {name} failed: {exc.code} {exc.reason}") from exc


def _post(
    url: str, body: dict[str, Any], token: str, *, timeout: float, retries: int = 4
) -> dict[str, Any]:
    # Retry transient failures (5xx / connection) with backoff — a single-concurrency
    # local model under a sustained eval batch returns 503 intermittently.
    last: Exception | None = None
    for attempt in range(retries):
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            method="POST",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.load(response)
            if not isinstance(data, dict):
                raise EvalRunnerError(f"POST {url}: unexpected response type {type(data)!r}")
            return data
        except urllib.error.HTTPError as exc:
            last = EvalRunnerError(f"POST {url} failed: {exc.code} {exc.reason}")
            transient = exc.code >= 500 or exc.code == 429
            if not transient or attempt == retries - 1:
                raise last from exc
        except EvalRunnerError:
            raise
        except Exception as exc:
            last = EvalRunnerError(f"POST {url} failed: {exc}")
            if attempt == retries - 1:
                raise last from exc
        time.sleep(2**attempt)  # 1, 2, 4s
    raise last if last else EvalRunnerError(f"POST {url} failed")

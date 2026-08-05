"""Cross-cutting API contract — doc/test-cases.md API-X-01~06.

These are the cheap, mechanical invariants that no single module owns, which is
exactly why they rot: the error envelope, the anonymous-access rule, and the
agreement between the paths the frontend calls and the routes the backend
registers. The last one is the dedicated defence against 7a35bb0, where the
frontend called a preview path the backend had never served and every
module-level suite still passed.
"""

from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from httpx import AsyncClient

from app.main import create_app
from tests.integration.conftest import auth_headers, register_and_login

pytestmark = pytest.mark.asyncio

_API_PREFIX = "/api/v1"

# Routes that are meant to be reachable without a bearer token.
_PUBLIC_PREFIXES = (
    "/auth/register",
    "/auth/login",
    "/auth/refresh",
    "/auth/logout",
    "/auth/forgot-password",
    "/public/",
)

# Top-level segments owned by the API, used to tell an API path in the frontend
# source apart from a router path or an asset URL.
_API_SEGMENTS = {
    "assistant",
    "auth",
    "download",
    "drive",
    "preview",
    "public",
    "search",
    "share",
    "snapshots",
    "trash",
    "upload",
    "users",
}

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FRONTEND_API_DIR = _REPO_ROOT / "frontend" / "src" / "api"


def _normalise(path: str) -> str:
    """Collapse every path parameter to a single placeholder.

    `/drive/items/{item_id}` and `/drive/items/${itemId}` must compare equal —
    the point of the check is the *shape* of the path, not the variable names.
    """
    path = re.sub(r"\$\{[^}]*\}", "{}", path)
    path = re.sub(r"\{[^}]*\}", "{}", path)
    return path.rstrip("/") or "/"


def _backend_routes() -> set[tuple[str, str]]:
    """Every (method, path) the app registers, with the /api/v1 prefix stripped."""
    routes: set[tuple[str, str]] = set()
    for route in create_app().routes:
        if not isinstance(route, APIRoute) or not route.path.startswith(_API_PREFIX):
            continue
        path = _normalise(route.path[len(_API_PREFIX) :])
        for method in route.methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            routes.add((method, path))
    return routes


def _frontend_paths() -> set[str]:
    """API paths referenced by the frontend client layer, excluding its tests."""
    found: set[str] = set()
    literal = re.compile(r"""['"`](/[^'"`\s]*)['"`]""")
    for source in sorted(_FRONTEND_API_DIR.glob("*.ts")):
        if source.name.endswith(".test.ts"):
            continue
        for raw in literal.findall(source.read_text(encoding="utf-8")):
            path = raw.split("?")[0]
            head = path.lstrip("/").split("/")[0]
            if head in _API_SEGMENTS:
                found.add(_normalise(path))
    return found


async def test_every_path_the_frontend_calls_is_registered_on_the_backend() -> None:
    """API-X-06 — regression for 7a35bb0.

    Compares shapes only, ignoring the HTTP verb: a verb mismatch surfaces as a
    405 in the module suites, whereas a path that exists on neither side is
    invisible to both and only shows up as a 404 in the browser.
    """
    backend_paths = {path for _method, path in _backend_routes()}
    called = _frontend_paths()

    assert called, "found no API paths in frontend/src/api — the extractor is broken"

    missing = sorted(p for p in called if p not in backend_paths)
    assert not missing, (
        "the frontend calls paths the backend does not serve:\n  "
        + "\n  ".join(missing)
        + "\n\nregistered paths:\n  "
        + "\n  ".join(sorted(backend_paths))
    )


def _protected_routes() -> list[tuple[str, str]]:
    return sorted(
        (method, path)
        for method, path in _backend_routes()
        if not path.startswith(_PUBLIC_PREFIXES)
    )


async def test_no_protected_endpoint_answers_an_anonymous_caller(
    client: AsyncClient,
) -> None:
    """API-X-04 — proposal §24 acceptance 2.

    Every protected route is called with no Authorization header and random ids.
    The bar is deliberately low and absolute: it must not succeed and it must
    not fall over. A 500 here means the auth guard is missing and something
    downstream blew up on a null user instead.
    """
    offenders: list[str] = []
    for method, path in _protected_routes():
        url = _API_PREFIX + path.replace("{}", str(uuid4()))
        resp = await client.request(method, url, json={} if method != "GET" else None)
        if resp.status_code not in (401, 403):
            offenders.append(f"{method} {path} → {resp.status_code}")

    assert not offenders, "protected endpoints reachable without a token:\n  " + "\n  ".join(
        offenders
    )


async def test_anonymous_rejection_is_uniform(client: AsyncClient) -> None:
    """API-X-04 — one rejection style, so the frontend can branch on it.

    Pins **401** across every protected route, which is what proposal §19 lists
    for "未登入". A mix of 401 and 403 would be worse than either on its own:
    the Axios interceptor refreshes on 401 and gives up on 403, so an endpoint
    that answers the wrong one silently logs the user out or silently retries
    forever.
    """
    statuses = set()
    for method, path in _protected_routes():
        url = _API_PREFIX + path.replace("{}", str(uuid4()))
        resp = await client.request(method, url, json={} if method != "GET" else None)
        statuses.add(resp.status_code)

    assert statuses == {401}, f"inconsistent anonymous rejection: {sorted(statuses)}"


async def test_error_bodies_use_the_documented_envelope(client: AsyncClient) -> None:
    """API-X-01 — proposal §19.

    `toApiError()` in the frontend reads `code` straight off the body, so an
    envelope that nests or renames it degrades every error message in the UI to
    a generic one.
    """
    h = auth_headers(await register_and_login(client, email="envelope@test.com"))

    failures = [
        await client.get(f"/api/v1/drive/items/{uuid4()}", headers=h),
        await client.get(f"/api/v1/download/{uuid4()}", headers=h),
        await client.get(f"/api/v1/preview/{uuid4()}", headers=h),
    ]

    await client.post("/api/v1/drive/folders", json={"name": "Dup"}, headers=h)
    failures.append(await client.post("/api/v1/drive/folders", json={"name": "Dup"}, headers=h))

    for resp in failures:
        assert resp.status_code >= 400, resp.text
        body = resp.json()
        assert set(body) == {"error"}, body
        assert set(body["error"]) >= {"code", "message", "details"}, body
        assert isinstance(body["error"]["code"], str) and body["error"]["code"]
        assert isinstance(body["error"]["message"], str) and body["error"]["message"]


async def test_error_codes_carry_their_documented_status(client: AsyncClient) -> None:
    """API-X-02 — the `code` ↔ HTTP status pairing the frontend branches on."""
    h = auth_headers(await register_and_login(client, email="codes@test.com"))

    missing = await client.get(f"/api/v1/drive/items/{uuid4()}", headers=h)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"

    await client.post("/api/v1/drive/folders", json={"name": "Clash"}, headers=h)
    clash = await client.post("/api/v1/drive/folders", json={"name": "Clash"}, headers=h)
    assert clash.status_code == 409
    assert clash.json()["error"]["code"] == "NAME_CONFLICT"

    dupe = await client.post(
        "/api/v1/auth/register",
        json={"email": "codes@test.com", "username": "again", "password": "Password123!"},
    )
    assert dupe.status_code == 409
    assert dupe.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"

    bad_login = await client.post(
        "/api/v1/auth/login", json={"email": "codes@test.com", "password": "wrong"}
    )
    assert bad_login.status_code == 401
    assert bad_login.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_error_messages_do_not_leak_internal_paths(client: AsyncClient) -> None:
    """API-X-03 — proposal §17.4 item 5."""
    h = auth_headers(await register_and_login(client, email="leak@test.com"))

    for resp in (
        await client.get(f"/api/v1/drive/items/{uuid4()}", headers=h),
        await client.get(f"/api/v1/download/{uuid4()}", headers=h),
        await client.get(f"/api/v1/preview/{uuid4()}/content", headers=h),
    ):
        message = resp.json()["error"]["message"]
        assert "/" not in message.replace("/api", ""), message
        assert "Traceback" not in message
        assert "sqlalchemy" not in message.lower()


async def test_another_users_item_id_is_refused_everywhere(client: AsyncClient) -> None:
    """API-X-05 — proposal §24 acceptance 1 and §17.2 item 2.

    Sweeps every id-taking endpoint with a real id belonging to somebody else,
    so a module that forgot its permission check cannot hide behind the ones
    that remembered.
    """
    owner = auth_headers(await register_and_login(client, email="victim@test.com"))
    folder = await client.post("/api/v1/drive/folders", json={"name": "Private"}, headers=owner)
    folder_id = folder.json()["id"]
    upload = await client.post(
        "/api/v1/upload/simple",
        headers=owner,
        files={"file": ("secret.txt", b"classified", "text/plain")},
    )
    file_id = upload.json()["id"]

    intruder = auth_headers(
        await register_and_login(client, email="intruder@test.com", username="intruder")
    )

    probes = [
        ("GET", f"/drive/items/{file_id}", None),
        ("GET", f"/drive/items/{folder_id}/ancestors", None),
        ("GET", f"/download/{file_id}", None),
        ("GET", f"/preview/{file_id}", None),
        ("GET", f"/preview/{file_id}/content", None),
        ("GET", f"/drive/items/{file_id}/versions", None),
        ("PATCH", f"/drive/items/{file_id}/name", {"name": "stolen.txt"}),
        ("PATCH", f"/drive/items/{file_id}/parent", {"parent_id": None}),
        ("PUT", f"/drive/items/{file_id}/star", {"is_starred": True}),
        ("POST", f"/trash/items/{file_id}", None),
        ("POST", "/download/archive", {"item_ids": [file_id]}),
    ]

    offenders: list[str] = []
    for method, path, body in probes:
        resp = await client.request(method, _API_PREFIX + path, json=body, headers=intruder)
        if resp.status_code not in (403, 404):
            offenders.append(f"{method} {path} → {resp.status_code}")

    assert not offenders, "another user's id was accepted:\n  " + "\n  ".join(offenders)

    # And the victim's file is still intact and still theirs.
    still_there = await client.get(f"/api/v1/drive/items/{file_id}", headers=owner)
    assert still_there.status_code == 200
    assert still_there.json()["name"] == "secret.txt"

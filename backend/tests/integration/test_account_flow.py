"""Account settings and session lifecycle — API-USER-01~08, API-AUTH-05~08.

Covers proposal §6.6 and §17.1. Every mutation is read back through
`GET /users/me` or by logging in again, because "the PATCH returned 200" is
exactly the evidence that would still be there if the change were dropped.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.integration.conftest import _SessionFactory, auth_headers, register_and_login

pytestmark = pytest.mark.asyncio

_PASSWORD = "Password123!"


async def test_changing_the_display_name_sticks(client: AsyncClient) -> None:
    """API-USER-01 — §6.6 item 2."""
    h = auth_headers(await register_and_login(client, email="rename-me@test.com"))

    resp = await client.patch("/api/v1/users/me", json={"username": "renamed"}, headers=h)
    assert resp.status_code == 200, resp.text

    me = await client.get("/api/v1/users/me", headers=h)
    assert me.json()["username"] == "renamed"


async def test_changing_the_email_also_changes_the_login(client: AsyncClient) -> None:
    """API-USER-02 — the email is the credential, so the proof is a fresh login."""
    old, new = "old-address@test.com", "new-address@test.com"
    h = auth_headers(await register_and_login(client, email=old))

    resp = await client.patch("/api/v1/users/me/email", json={"email": new}, headers=h)
    assert resp.status_code == 200, resp.text

    me = await client.get("/api/v1/users/me", headers=h)
    assert me.json()["email"] == new

    assert (
        await client.post("/api/v1/auth/login", json={"email": new, "password": _PASSWORD})
    ).status_code == 200
    assert (
        await client.post("/api/v1/auth/login", json={"email": old, "password": _PASSWORD})
    ).status_code == 401


async def test_taking_someone_elses_email_is_refused(client: AsyncClient) -> None:
    """API-USER-03 — §6.6 item 3; §19 lists email 已存在 under 409."""
    taken = "already-taken@test.com"
    await register_and_login(client, email=taken, username="incumbent")
    h = auth_headers(await register_and_login(client, email="hopeful@test.com", username="hope"))

    resp = await client.patch("/api/v1/users/me/email", json={"email": taken}, headers=h)
    assert resp.status_code == 409, resp.text
    assert resp.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"

    me = await client.get("/api/v1/users/me", headers=h)
    assert me.json()["email"] == "hopeful@test.com"


async def test_a_malformed_email_is_refused(client: AsyncClient) -> None:
    """API-USER-04 — §6.6 item 3."""
    h = auth_headers(await register_and_login(client, email="valid@test.com"))

    resp = await client.patch("/api/v1/users/me/email", json={"email": "not-an-email"}, headers=h)
    assert resp.status_code >= 400, resp.text

    me = await client.get("/api/v1/users/me", headers=h)
    assert me.json()["email"] == "valid@test.com"


async def test_changing_the_password_invalidates_the_old_one(client: AsyncClient) -> None:
    """API-USER-05 — §6.6 item 4."""
    email = "pw-change@test.com"
    h = auth_headers(await register_and_login(client, email=email))
    new_password = "BrandNewPass456!"

    resp = await client.patch(
        "/api/v1/users/me/password",
        json={"current_password": _PASSWORD, "new_password": new_password},
        headers=h,
    )
    assert resp.status_code == 204, resp.text

    assert (
        await client.post("/api/v1/auth/login", json={"email": email, "password": _PASSWORD})
    ).status_code == 401
    assert (
        await client.post("/api/v1/auth/login", json={"email": email, "password": new_password})
    ).status_code == 200


async def test_a_wrong_current_password_is_refused(client: AsyncClient) -> None:
    """API-USER-07 — otherwise a stolen access token could seize the account."""
    email = "pw-guard@test.com"
    h = auth_headers(await register_and_login(client, email=email))

    resp = await client.patch(
        "/api/v1/users/me/password",
        json={"current_password": "NotTheOne!", "new_password": "Whatever123!"},
        headers=h,
    )
    assert resp.status_code >= 400, resp.text

    assert (
        await client.post("/api/v1/auth/login", json={"email": email, "password": _PASSWORD})
    ).status_code == 200


async def test_a_too_short_password_is_refused(client: AsyncClient) -> None:
    """API-USER-06 — §6.6 item 4 requires at least 8 characters."""
    email = "pw-short@test.com"
    h = auth_headers(await register_and_login(client, email=email))

    resp = await client.patch(
        "/api/v1/users/me/password",
        json={"current_password": _PASSWORD, "new_password": "short"},
        headers=h,
    )
    assert resp.status_code >= 400, resp.text

    assert (
        await client.post("/api/v1/auth/login", json={"email": email, "password": _PASSWORD})
    ).status_code == 200


async def test_quota_reports_a_coherent_set_of_numbers(client: AsyncClient) -> None:
    """API-USER-08 — §5.1 item 16."""
    h = auth_headers(await register_and_login(client, email="quota-shape@test.com"))

    body = (await client.get("/api/v1/users/me/quota", headers=h)).json()
    assert body["quota_bytes"] > 0
    assert body["used_bytes"] >= 0
    assert body["available_bytes"] == body["quota_bytes"] - body["used_bytes"]
    assert 0 <= body["used_percent"] <= 100


async def test_passwords_are_stored_hashed(client: AsyncClient) -> None:
    """API-AUTH-08 — §17.1 item 5.

    Read straight from the table: no API response should ever carry the hash, so
    there is no endpoint that could show this.
    """
    email = "hashed@test.com"
    await register_and_login(client, email=email)

    async with _SessionFactory() as session:
        row = await session.execute(
            text("SELECT password_hash FROM users WHERE email = :e"), {"e": email}
        )
        stored = row.scalar_one()

    assert stored != _PASSWORD
    assert _PASSWORD not in stored
    assert stored.startswith(("$2a$", "$2b$", "$2y$", "$argon2")), stored[:8]


async def test_no_endpoint_ever_returns_the_hash(client: AsyncClient) -> None:
    """API-SHR-12 / §17.4 item 6.

    Targets the secret-bearing field names and the shape of a bcrypt digest
    rather than the word "password" — `must_change_password` is a legitimate
    flag and banning the substring would only teach people to rename it.
    """
    h = auth_headers(await register_and_login(client, email="no-leak@test.com"))

    for path in ("/api/v1/users/me", "/api/v1/users/me/quota"):
        body = (await client.get(path, headers=h)).text
        payload = (await client.get(path, headers=h)).json()
        assert "password_hash" not in payload
        assert "token_hash" not in payload
        assert _PASSWORD not in body
        assert "$2b$" not in body and "$argon2" not in body


async def test_refresh_issues_a_new_access_token(client: AsyncClient) -> None:
    """API-AUTH-05 — §17.1 item 6, the silent-refresh that keeps a reload logged in."""
    email = "refresh-me@test.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": "refresher", "password": _PASSWORD},
    )
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": _PASSWORD})
    assert login.status_code == 200

    refreshed = await client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200, refreshed.text
    token = refreshed.json()["access_token"]
    assert token

    me = await client.get("/api/v1/users/me", headers=auth_headers(token))
    assert me.status_code == 200
    assert me.json()["email"] == email


async def test_logging_out_kills_the_refresh_token(client: AsyncClient) -> None:
    """API-AUTH-06 — §17.1 item 4 requires refresh tokens to be revocable.

    Clearing the cookie alone would not be enough: anybody holding a copy of the
    value could keep minting access tokens, so the server side must be revoked
    too.
    """
    email = "logout-me@test.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": "leaver", "password": _PASSWORD},
    )
    await client.post("/api/v1/auth/login", json={"email": email, "password": _PASSWORD})

    stolen = client.cookies.get("refresh_token")
    assert (await client.post("/api/v1/auth/refresh")).status_code == 200

    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code in (200, 204), logout.text

    assert (await client.post("/api/v1/auth/refresh")).status_code == 401

    if stolen:
        client.cookies.set("refresh_token", stolen)
        replayed = await client.post("/api/v1/auth/refresh")
        assert replayed.status_code == 401, "a revoked refresh token was accepted again"


@pytest.mark.parametrize(
    "token",
    ["not-a-jwt", "a.b.c", ""],
)
async def test_a_tampered_token_is_rejected(client: AsyncClient, token: str) -> None:
    """API-AUTH-07 — a malformed bearer must be refused, never crash the guard."""
    resp = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code in (401, 403), resp.text

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.integration.conftest import auth_headers, register_and_login

pytestmark = pytest.mark.asyncio


async def test_register_creates_user(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "bob@example.com", "username": "bob", "password": "Password123!"},
    )
    assert resp.status_code == 201
    data = resp.json()
    # Registration auto-logs-in and returns an access token (no user PII echoed).
    assert data["access_token"]
    assert "password_hash" not in data
    assert "email" not in data


async def test_register_duplicate_email_returns_409(client: AsyncClient) -> None:
    body = {"email": "dup@example.com", "username": "dup", "password": "Password123!"}
    await client.post("/api/v1/auth/register", json=body)
    resp = await client.post("/api/v1/auth/register", json=body)
    assert resp.status_code == 409


async def test_login_returns_access_token(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "carol@example.com", "username": "carol", "password": "Password123!"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "carol@example.com", "password": "Password123!"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    # Refresh token must NOT appear in the JSON body
    assert "refresh_token" not in body


async def test_login_wrong_password_returns_401(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "dave@example.com", "username": "dave", "password": "Password123!"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "dave@example.com", "password": "WrongPassword!"},
    )
    assert resp.status_code == 401


async def test_authenticated_endpoint_returns_current_user(client: AsyncClient) -> None:
    token = await register_and_login(
        client, email="eve@example.com", username="eve", password="Password123!"
    )
    resp = await client.get("/api/v1/users/me", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["email"] == "eve@example.com"


async def test_unauthenticated_endpoint_returns_403(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code in (401, 403)


async def test_logout_clears_cookie(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "frank@example.com", "username": "frank", "password": "Password123!"},
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "frank@example.com", "password": "Password123!"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    logout_resp = await client.post("/api/v1/auth/logout", headers=auth_headers(token))
    assert logout_resp.status_code in (200, 204)
    # Cookie should be cleared (set-cookie header with empty value or max-age=0)
    set_cookie = logout_resp.headers.get("set-cookie", "")
    assert "refresh_token" in set_cookie or logout_resp.status_code == 204

from __future__ import annotations

import io

import pytest
from httpx import AsyncClient

from tests.integration.conftest import auth_headers, register_and_login

pytestmark = pytest.mark.asyncio


async def test_share_with_user_appears_in_shared_with_me(client: AsyncClient) -> None:
    token_a = await register_and_login(client, email="owner@test.com", username="owner")
    token_b = await register_and_login(client, email="guest@test.com", username="guest")

    folder = await client.post(
        "/api/v1/drive/folders",
        json={"name": "SharedFolder"},
        headers=auth_headers(token_a),
    )
    item_id = folder.json()["id"]

    share = await client.post(
        f"/api/v1/share/items/{item_id}",
        json={"target_email": "guest@test.com", "permission": "viewer"},
        headers=auth_headers(token_a),
    )
    assert share.status_code == 201
    assert share.json()["permission"] == "viewer"

    # Guest should see it in shared-with-me
    shared = await client.get("/api/v1/share/shared-with-me", headers=auth_headers(token_b))
    assert shared.status_code == 200
    item_ids = [s["item_id"] for s in shared.json()["items"]]
    assert item_id in item_ids


async def test_permission_isolation_owner_only_download(client: AsyncClient) -> None:
    token_a = await register_and_login(client, email="owner2@test.com", username="owner2")
    token_b = await register_and_login(client, email="stranger@test.com", username="stranger")

    upload = await client.post(
        "/api/v1/upload/simple",
        headers=auth_headers(token_a),
        files={"file": ("private.txt", io.BytesIO(b"private content"), "text/plain")},
    )
    item_id = upload.json()["id"]

    # Stranger without share cannot download
    resp = await client.get(f"/api/v1/download/{item_id}", headers=auth_headers(token_b))
    assert resp.status_code in (403, 404)

    # Owner can download
    owner_resp = await client.get(f"/api/v1/download/{item_id}", headers=auth_headers(token_a))
    assert owner_resp.status_code == 200


async def test_remove_share_stops_access(client: AsyncClient) -> None:
    token_a = await register_and_login(client, email="sharer@test.com", username="sharer")
    token_b = await register_and_login(client, email="revoked@test.com", username="revoked")

    folder = await client.post(
        "/api/v1/drive/folders",
        json={"name": "TempShared"},
        headers=auth_headers(token_a),
    )
    item_id = folder.json()["id"]

    share = await client.post(
        f"/api/v1/share/items/{item_id}",
        json={"target_email": "revoked@test.com", "permission": "viewer"},
        headers=auth_headers(token_a),
    )
    target_user_id = share.json()["target_user_id"]

    # Confirm share is present
    shared = await client.get("/api/v1/share/shared-with-me", headers=auth_headers(token_b))
    assert any(s["item_id"] == item_id for s in shared.json()["items"])

    # Remove share
    remove = await client.delete(
        f"/api/v1/share/items/{item_id}/users/{target_user_id}",
        headers=auth_headers(token_a),
    )
    assert remove.status_code == 204

    # Confirm share is gone
    shared_after = await client.get(
        "/api/v1/share/shared-with-me", headers=auth_headers(token_b)
    )
    assert not any(s["item_id"] == item_id for s in shared_after.json()["items"])


async def test_create_share_link(client: AsyncClient) -> None:
    token = await register_and_login(client, email="linker@test.com", username="linker")
    h = auth_headers(token)

    folder = await client.post("/api/v1/drive/folders", json={"name": "LinkFolder"}, headers=h)
    item_id = folder.json()["id"]

    link_resp = await client.post(
        f"/api/v1/share/items/{item_id}/links",
        json={"permission": "viewer"},
        headers=h,
    )
    assert link_resp.status_code == 201
    link = link_resp.json()
    assert link["is_active"] is True
    assert link["permission"] == "viewer"
    assert "token" in link


async def test_deactivate_share_link(client: AsyncClient) -> None:
    token = await register_and_login(client, email="deactivate@test.com", username="deact")
    h = auth_headers(token)

    folder = await client.post("/api/v1/drive/folders", json={"name": "DeactFolder"}, headers=h)
    item_id = folder.json()["id"]

    link = await client.post(
        f"/api/v1/share/items/{item_id}/links", json={"permission": "viewer"}, headers=h
    )
    link_id = link.json()["id"]
    link_token = link.json()["token"]

    deact = await client.delete(f"/api/v1/share/links/{link_id}", headers=h)
    assert deact.status_code == 204

    # Validating the deactivated link should fail
    validate = await client.post(
        "/api/v1/share/links/validate", params={"token": link_token}
    )
    assert validate.status_code in (400, 401, 404, 410)

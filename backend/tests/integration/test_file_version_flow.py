"""
Integration tests for the file version subsystem.

Covers the invariant that every upload creates a version record (v1),
and verifies the list-versions endpoint behavior including permission isolation.
"""

from __future__ import annotations

import io

import pytest
from httpx import AsyncClient

from tests.integration.conftest import auth_headers, register_and_login

pytestmark = pytest.mark.asyncio


async def test_upload_creates_version_record(client: AsyncClient) -> None:
    """Uploading a file must create a v1 version record automatically."""
    token = await register_and_login(client, email="fv1@test.com")
    h = auth_headers(token)

    resp = await client.post(
        "/api/v1/upload/simple",
        headers=h,
        files={"file": ("notes.txt", io.BytesIO(b"version one content"), "text/plain")},
    )
    assert resp.status_code == 201
    item_id = resp.json()["id"]

    versions_resp = await client.get(f"/api/v1/drive/items/{item_id}/versions", headers=h)
    assert versions_resp.status_code == 200
    versions = versions_resp.json()
    assert len(versions) == 1
    assert versions[0]["version_no"] == 1
    assert versions[0]["file_id"] == item_id


async def test_version_size_matches_upload(client: AsyncClient) -> None:
    """The version record must record the actual file size."""
    token = await register_and_login(client, email="fv2@test.com")
    h = auth_headers(token)
    content = b"x" * 512

    resp = await client.post(
        "/api/v1/upload/simple",
        headers=h,
        files={"file": ("big.bin", io.BytesIO(content), "application/octet-stream")},
    )
    assert resp.status_code == 201
    item_id = resp.json()["id"]

    versions_resp = await client.get(f"/api/v1/drive/items/{item_id}/versions", headers=h)
    v = versions_resp.json()[0]
    assert v["size_bytes"] == 512


async def test_list_versions_requires_auth(client: AsyncClient) -> None:
    """Unauthenticated request to list versions must return 401 or 403."""
    # Upload as a real user to get a valid item_id
    token = await register_and_login(client, email="fv3@test.com")
    h = auth_headers(token)
    resp = await client.post(
        "/api/v1/upload/simple",
        headers=h,
        files={"file": ("f.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    item_id = resp.json()["id"]

    no_auth_resp = await client.get(f"/api/v1/drive/items/{item_id}/versions")
    assert no_auth_resp.status_code in (401, 403)


async def test_non_owner_without_share_cannot_list_versions(client: AsyncClient) -> None:
    """A user who has no share on the file must receive 403 when listing versions."""
    owner_token = await register_and_login(client, email="fv4_owner@test.com")
    stranger_token = await register_and_login(client, email="fv4_stranger@test.com")

    # Owner uploads a file
    resp = await client.post(
        "/api/v1/upload/simple",
        headers=auth_headers(owner_token),
        files={"file": ("secret.txt", io.BytesIO(b"owner only"), "text/plain")},
    )
    assert resp.status_code == 201
    item_id = resp.json()["id"]

    # Stranger tries to list versions
    stranger_resp = await client.get(
        f"/api/v1/drive/items/{item_id}/versions",
        headers=auth_headers(stranger_token),
    )
    assert stranger_resp.status_code in (403, 404)


async def test_viewer_can_list_versions(client: AsyncClient) -> None:
    """A user shared as viewer must be able to list versions."""
    owner_token = await register_and_login(client, email="fv5_owner@test.com", username="fv5owner")
    viewer_email = "fv5_viewer@test.com"
    viewer_token = await register_and_login(client, email=viewer_email, username="fv5viewer")

    # Owner uploads a file
    resp = await client.post(
        "/api/v1/upload/simple",
        headers=auth_headers(owner_token),
        files={"file": ("shared.txt", io.BytesIO(b"shared content"), "text/plain")},
    )
    assert resp.status_code == 201
    item_id = resp.json()["id"]

    # Owner shares with viewer
    share_resp = await client.post(
        f"/api/v1/share/items/{item_id}",
        headers=auth_headers(owner_token),
        json={"target_email": viewer_email, "permission": "viewer"},
    )
    assert share_resp.status_code == 201

    # Viewer can list versions
    versions_resp = await client.get(
        f"/api/v1/drive/items/{item_id}/versions",
        headers=auth_headers(viewer_token),
    )
    assert versions_resp.status_code == 200
    assert len(versions_resp.json()) == 1


async def test_each_upload_creates_independent_v1(client: AsyncClient) -> None:
    """Two separate uploads (even with the same name) create independent items each with v1."""
    token = await register_and_login(client, email="fv6@test.com")
    h = auth_headers(token)

    resp1 = await client.post(
        "/api/v1/upload/simple",
        headers=h,
        files={"file": ("dup.txt", io.BytesIO(b"first"), "text/plain")},
    )
    resp2 = await client.post(
        "/api/v1/upload/simple",
        headers=h,
        files={"file": ("dup.txt", io.BytesIO(b"second"), "text/plain")},
    )
    assert resp1.status_code == 201
    assert resp2.status_code == 201

    # They are distinct items (auto-renamed)
    assert resp1.json()["id"] != resp2.json()["id"]

    # Each has exactly one version at v1
    for item_id in [resp1.json()["id"], resp2.json()["id"]]:
        v_resp = await client.get(f"/api/v1/drive/items/{item_id}/versions", headers=h)
        versions = v_resp.json()
        assert len(versions) == 1
        assert versions[0]["version_no"] == 1

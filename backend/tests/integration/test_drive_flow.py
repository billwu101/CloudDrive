from __future__ import annotations

import io

import pytest
from httpx import AsyncClient

from tests.integration.conftest import auth_headers, register_and_login

pytestmark = pytest.mark.asyncio


async def test_create_folder_appears_in_list(client: AsyncClient) -> None:
    token = await register_and_login(client, email="u1@test.com")
    h = auth_headers(token)

    resp = await client.post("/api/v1/drive/folders", json={"name": "My Folder"}, headers=h)
    assert resp.status_code == 201
    folder = resp.json()
    assert folder["name"] == "My Folder"
    assert folder["item_type"] == "FOLDER"

    list_resp = await client.get("/api/v1/drive/items", headers=h)
    assert list_resp.status_code == 200
    names = [i["name"] for i in list_resp.json()["items"]]
    assert "My Folder" in names


async def test_cannot_create_duplicate_folder_name(client: AsyncClient) -> None:
    token = await register_and_login(client, email="u2@test.com")
    h = auth_headers(token)

    await client.post("/api/v1/drive/folders", json={"name": "Dup"}, headers=h)
    resp = await client.post("/api/v1/drive/folders", json={"name": "Dup"}, headers=h)
    assert resp.status_code == 409


async def test_upload_file_and_download(client: AsyncClient) -> None:
    token = await register_and_login(client, email="u3@test.com")
    h = auth_headers(token)

    content = b"Hello, integration test!"
    resp = await client.post(
        "/api/v1/upload/simple",
        headers=h,
        files={"file": ("hello.txt", io.BytesIO(content), "text/plain")},
    )
    assert resp.status_code == 201
    item = resp.json()
    assert item["name"] == "hello.txt"
    assert item["item_type"] == "FILE"

    dl_resp = await client.get(f"/api/v1/download/{item['id']}", headers=h)
    assert dl_resp.status_code == 200
    assert dl_resp.content == content


async def test_uploaded_file_appears_in_list(client: AsyncClient) -> None:
    token = await register_and_login(client, email="u4@test.com")
    h = auth_headers(token)

    await client.post(
        "/api/v1/upload/simple",
        headers=h,
        files={"file": ("report.pdf", io.BytesIO(b"%PDF-"), "application/pdf")},
    )

    list_resp = await client.get("/api/v1/drive/items", headers=h)
    names = [i["name"] for i in list_resp.json()["items"]]
    assert "report.pdf" in names


async def test_rename_item(client: AsyncClient) -> None:
    token = await register_and_login(client, email="u5@test.com")
    h = auth_headers(token)

    create = await client.post("/api/v1/drive/folders", json={"name": "OldName"}, headers=h)
    item_id = create.json()["id"]

    rename = await client.patch(
        f"/api/v1/drive/items/{item_id}/rename", json={"name": "NewName"}, headers=h
    )
    assert rename.status_code == 200
    assert rename.json()["name"] == "NewName"


async def test_move_item_to_folder(client: AsyncClient) -> None:
    token = await register_and_login(client, email="u6@test.com")
    h = auth_headers(token)

    parent = await client.post("/api/v1/drive/folders", json={"name": "Parent"}, headers=h)
    parent_id = parent.json()["id"]

    child = await client.post("/api/v1/drive/folders", json={"name": "Child"}, headers=h)
    child_id = child.json()["id"]

    move = await client.patch(
        f"/api/v1/drive/items/{child_id}/parent",
        json={"parent_id": parent_id},
        headers=h,
    )
    assert move.status_code == 200
    assert move.json()["parent_id"] == parent_id

    # Item should no longer appear in root
    root_list = await client.get("/api/v1/drive/items", headers=h)
    root_names = [i["name"] for i in root_list.json()["items"]]
    assert "Child" not in root_names

    # Item should appear inside parent folder
    folder_list = await client.get(
        "/api/v1/drive/items", params={"parent_id": parent_id}, headers=h
    )
    folder_names = [i["name"] for i in folder_list.json()["items"]]
    assert "Child" in folder_names


async def test_search_finds_uploaded_file(client: AsyncClient) -> None:
    token = await register_and_login(client, email="u7@test.com")
    h = auth_headers(token)

    await client.post(
        "/api/v1/upload/simple",
        headers=h,
        files={"file": ("quarterly_report.txt", io.BytesIO(b"data"), "text/plain")},
    )

    resp = await client.get("/api/v1/search", params={"q": "quarterly"}, headers=h)
    assert resp.status_code == 200
    names = [i["name"] for i in resp.json()["items"]]
    assert "quarterly_report.txt" in names


async def test_search_returns_empty_for_no_match(client: AsyncClient) -> None:
    token = await register_and_login(client, email="u8@test.com")
    h = auth_headers(token)

    await client.post(
        "/api/v1/upload/simple",
        headers=h,
        files={"file": ("notes.txt", io.BytesIO(b"abc"), "text/plain")},
    )

    resp = await client.get("/api/v1/search", params={"q": "xyznonexistent"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["items"] == []


async def test_user_cannot_access_other_users_items(client: AsyncClient) -> None:
    token_a = await register_and_login(client, email="alice@test.com", username="alice")
    token_b = await register_and_login(client, email="bob@test.com", username="bob")

    upload = await client.post(
        "/api/v1/upload/simple",
        headers=auth_headers(token_a),
        files={"file": ("secret.txt", io.BytesIO(b"secret"), "text/plain")},
    )
    item_id = upload.json()["id"]

    # Bob tries to download Alice's file
    resp = await client.get(f"/api/v1/download/{item_id}", headers=auth_headers(token_b))
    assert resp.status_code in (403, 404)

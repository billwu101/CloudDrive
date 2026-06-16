from __future__ import annotations

import io
from pathlib import Path

import pytest
from httpx import AsyncClient

from tests.integration.conftest import _STORAGE_DIR, auth_headers, register_and_login

pytestmark = pytest.mark.asyncio


async def test_move_to_trash_removes_from_drive(client: AsyncClient) -> None:
    token = await register_and_login(client, email="t1@test.com")
    h = auth_headers(token)

    folder = await client.post("/api/v1/drive/folders", json={"name": "ToTrash"}, headers=h)
    item_id = folder.json()["id"]

    resp = await client.post(f"/api/v1/trash/items/{item_id}", headers=h)
    assert resp.status_code == 200
    assert resp.json()["is_deleted"] is True

    # Should no longer appear in drive root
    list_resp = await client.get("/api/v1/drive/items", headers=h)
    names = [i["name"] for i in list_resp.json()["items"]]
    assert "ToTrash" not in names


async def test_trashed_item_appears_in_trash_list(client: AsyncClient) -> None:
    token = await register_and_login(client, email="t2@test.com")
    h = auth_headers(token)

    folder = await client.post("/api/v1/drive/folders", json={"name": "InTrash"}, headers=h)
    item_id = folder.json()["id"]
    await client.post(f"/api/v1/trash/items/{item_id}", headers=h)

    trash_resp = await client.get("/api/v1/trash", headers=h)
    assert trash_resp.status_code == 200
    names = [i["name"] for i in trash_resp.json()["items"]]
    assert "InTrash" in names


async def test_restore_item_reappears_in_drive(client: AsyncClient) -> None:
    token = await register_and_login(client, email="t3@test.com")
    h = auth_headers(token)

    folder = await client.post("/api/v1/drive/folders", json={"name": "Restored"}, headers=h)
    item_id = folder.json()["id"]
    await client.post(f"/api/v1/trash/items/{item_id}", headers=h)

    restore = await client.post(f"/api/v1/trash/items/{item_id}/restore", headers=h)
    assert restore.status_code == 200
    assert restore.json()["is_deleted"] is False

    list_resp = await client.get("/api/v1/drive/items", headers=h)
    names = [i["name"] for i in list_resp.json()["items"]]
    assert "Restored" in names


async def test_permanent_delete_removes_from_trash(client: AsyncClient) -> None:
    token = await register_and_login(client, email="t4@test.com")
    h = auth_headers(token)

    upload = await client.post(
        "/api/v1/upload/simple",
        headers=h,
        files={"file": ("delete_me.txt", io.BytesIO(b"goodbye"), "text/plain")},
    )
    item_id = upload.json()["id"]
    await client.post(f"/api/v1/trash/items/{item_id}", headers=h)

    delete = await client.delete(f"/api/v1/trash/items/{item_id}", headers=h)
    assert delete.status_code == 204

    trash_resp = await client.get("/api/v1/trash", headers=h)
    names = [i["name"] for i in trash_resp.json()["items"]]
    assert "delete_me.txt" not in names


async def test_permanent_delete_cleans_up_storage(client: AsyncClient) -> None:
    """Storage files must be removed when a file is permanently deleted."""
    token = await register_and_login(client, email="t5@test.com")
    h = auth_headers(token)

    upload = await client.post(
        "/api/v1/upload/simple",
        headers=h,
        files={"file": ("cleanup.txt", io.BytesIO(b"will be deleted"), "text/plain")},
    )
    item_id = upload.json()["id"]

    # Find the storage file before deletion
    storage_files_before = list(Path(_STORAGE_DIR).rglob("*"))
    data_files_before = [f for f in storage_files_before if f.is_file()]
    assert len(data_files_before) >= 1

    await client.post(f"/api/v1/trash/items/{item_id}", headers=h)
    await client.delete(f"/api/v1/trash/items/{item_id}", headers=h)

    # Storage should have fewer files after permanent deletion
    data_files_after = [f for f in Path(_STORAGE_DIR).rglob("*") if f.is_file()]
    assert len(data_files_after) < len(data_files_before)


async def test_empty_trash_removes_all_items(client: AsyncClient) -> None:
    token = await register_and_login(client, email="t6@test.com")
    h = auth_headers(token)

    for name in ["a.txt", "b.txt", "c.txt"]:
        upload = await client.post(
            "/api/v1/upload/simple",
            headers=h,
            files={"file": (name, io.BytesIO(b"data"), "text/plain")},
        )
        await client.post(f"/api/v1/trash/items/{upload.json()['id']}", headers=h)

    empty = await client.delete("/api/v1/trash", headers=h)
    assert empty.status_code == 204

    trash_resp = await client.get("/api/v1/trash", headers=h)
    assert trash_resp.json()["items"] == []

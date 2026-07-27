"""
Integration tests for Time Machine capture/restore against a real database.

The self-referential drive_items.parent_id FK is only enforced by Postgres, so
the orphan-handling below cannot be caught by the in-memory unit fakes.
"""

from __future__ import annotations

import io

import pytest
from httpx import AsyncClient

from tests.integration.conftest import auth_headers, register_and_login

pytestmark = pytest.mark.asyncio


async def test_restore_survives_orphaned_entries_from_a_trashed_folder(
    client: AsyncClient,
) -> None:
    """Trashing a folder before a snapshot must not make that snapshot unrestorable.

    Regression (restore 500): soft delete is shallow, so capture skipped the
    trashed folder but kept its children, recording a parent_id that pointed at
    a row the restore would never create — the INSERT then violated
    drive_items_parent_id_fkey and the whole restore failed. Such orphans must
    be captured/restored at the root instead.
    """
    token = await register_and_login(client, email="snap-orphan@test.com")
    h = auth_headers(token)

    folder = await client.post("/api/v1/drive/folders", json={"name": "Docs"}, headers=h)
    folder_id = folder.json()["id"]
    upload = await client.post(
        "/api/v1/upload/simple",
        headers=h,
        params={"parent_id": folder_id},
        files={"file": ("inside.txt", io.BytesIO(b"nested"), "text/plain")},
    )
    child_id = upload.json()["id"]

    # Trash the parent only — the child keeps is_deleted=False and a parent_id
    # pointing at a now-invisible folder.
    assert (await client.post(f"/api/v1/trash/items/{folder_id}", headers=h)).status_code == 200

    snap = await client.post(
        "/api/v1/snapshots", json={"label": "after trashing the parent"}, headers=h
    )
    assert snap.status_code == 200, snap.text
    snapshot_id = snap.json()["id"]

    # Permanently remove the folder so the parent cannot be resolved at all.
    assert (await client.delete("/api/v1/trash", headers=h)).status_code == 204

    restored = await client.post(
        f"/api/v1/snapshots/{snapshot_id}/restore",
        json={"scope": "whole", "subtree_mode": "keep_new"},
        headers=h,
    )
    assert restored.status_code == 200, restored.text

    # The orphan is back and sits at the drive root, not under a dangling parent.
    root = await client.get("/api/v1/drive/items", headers=h)
    entry = next((i for i in root.json()["items"] if i["id"] == child_id), None)
    assert entry is not None, "orphaned child should be restored at the root"
    assert entry["parent_id"] is None
    assert entry["name"] == "inside.txt"


async def test_restore_rebuilds_a_folder_tree_parents_first(client: AsyncClient) -> None:
    """The ordinary case still nests correctly (parents before children)."""
    token = await register_and_login(client, email="snap-tree@test.com")
    h = auth_headers(token)

    top = await client.post("/api/v1/drive/folders", json={"name": "Top"}, headers=h)
    top_id = top.json()["id"]
    sub = await client.post(
        "/api/v1/drive/folders", json={"name": "Sub", "parent_id": top_id}, headers=h
    )
    sub_id = sub.json()["id"]
    await client.post(
        "/api/v1/upload/simple",
        headers=h,
        params={"parent_id": sub_id},
        files={"file": ("deep.txt", io.BytesIO(b"deep"), "text/plain")},
    )

    snap = await client.post("/api/v1/snapshots", json={"label": "tree"}, headers=h)
    snapshot_id = snap.json()["id"]

    # Remove the whole tree, then restore it.
    await client.post(f"/api/v1/trash/items/{top_id}", headers=h)
    assert (await client.delete("/api/v1/trash", headers=h)).status_code == 204

    restored = await client.post(
        f"/api/v1/snapshots/{snapshot_id}/restore",
        json={"scope": "whole", "subtree_mode": "keep_new"},
        headers=h,
    )
    assert restored.status_code == 200, restored.text

    root = await client.get("/api/v1/drive/items", headers=h)
    assert "Top" in [i["name"] for i in root.json()["items"]]
    in_top = await client.get(f"/api/v1/drive/items?parent_id={top_id}", headers=h)
    assert "Sub" in [i["name"] for i in in_top.json()["items"]]
    in_sub = await client.get(f"/api/v1/drive/items?parent_id={sub_id}", headers=h)
    assert "deep.txt" in [i["name"] for i in in_sub.json()["items"]]


async def test_a_shared_snapshot_reports_nothing_to_reclaim(client: AsyncClient) -> None:
    """Coverage is not cost — the number the timeline shows must be the latter.

    Two snapshots of unchanged content point at the same blob, so deleting
    either frees nothing. Reporting `total_bytes` would tell the user to delete
    the biggest snapshot when that reclaims zero bytes.
    """
    token = await register_and_login(client, email="snap-reclaim@test.com")
    h = auth_headers(token)
    await client.post(
        "/api/v1/upload/simple",
        headers=h,
        files={"file": ("big.txt", io.BytesIO(b"x" * 5000), "text/plain")},
    )

    for label in ("first", "second"):
        assert (
            await client.post("/api/v1/snapshots", json={"label": label}, headers=h)
        ).status_code == 200

    snaps = (await client.get("/api/v1/snapshots", headers=h)).json()
    assert len(snaps) == 2
    # Both cover the file...
    assert all(s["total_bytes"] >= 5000 for s in snaps)
    # ...but neither is the sole holder: the live item still references the blob.
    assert all(s["reclaimable_bytes"] == 0 for s in snaps)

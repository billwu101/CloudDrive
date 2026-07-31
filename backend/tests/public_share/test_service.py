"""Unit tests for the guest side of public share links (proposal §28).

The emphasis is on the security rules rather than the happy path: this is the
only unauthenticated surface in the backend, so the tests that matter are the
ones that would catch it turning into a way to enumerate links, brute-force
passwords, or reach items the link never covered.
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, ForbiddenError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_share_access_token,
    decode_access_token,
    decode_share_access_token,
)
from app.drive.schemas import ItemType
from app.models.drive_item import DriveItem
from app.permission.permissions import LinkPermission, Permission
from app.public_share.service import PublicShareService
from app.share.service import ShareLinkService
from tests.drive.test_service import MemDriveItemRepo, _item
from tests.share.test_service import MemShareLinkRepo

pytestmark = pytest.mark.asyncio


class _Storage:
    """Minimal storage stand-in: every key exists and yields the same bytes."""

    async def exists(self, key: str) -> bool:
        return True

    async def open_read(self, key: str):  # type: ignore[no-untyped-def]
        yield b"hello"


def _svc(items: MemDriveItemRepo, links: MemShareLinkRepo) -> PublicShareService:
    return PublicShareService(
        item_repo=items,
        link_repo=links,
        storage=_Storage(),  # type: ignore[arg-type]
        preview_svc=AsyncMock(),
        download_svc=AsyncMock(),
    )


async def _stored(links: MemShareLinkRepo, token: str):  # type: ignore[no-untyped-def]
    """The persisted row behind a plaintext token."""
    return await links.get_by_token_hash(hashlib.sha256(token.encode()).hexdigest())


async def _link_for(
    items: MemDriveItemRepo,
    links: MemShareLinkRepo,
    item_id: UUID,
    owner_id: UUID,
    *,
    permission: LinkPermission = LinkPermission.DOWNLOADER,
    password: str | None = None,
    expires_at: datetime | None = None,
) -> str:
    """Create a link through the real service and return its plaintext token."""
    link_svc = ShareLinkService(item_repo=items, link_repo=links)
    resp = await link_svc.create_link(
        owner_id, item_id, permission, password=password, expires_at=expires_at
    )
    assert resp.token is not None
    return resp.token


async def _drive_with_file(*, deleted: bool = False):  # type: ignore[no-untyped-def]
    owner = uuid4()
    items = MemDriveItemRepo()
    doc = _item(owner_id=owner, item_type=ItemType.FILE, name="report.txt", is_deleted=deleted)
    doc.storage_key = "blob/report"
    doc.mime_type = "text/plain"
    items._items[doc.id] = doc
    return owner, items, doc


# ── session ──────────────────────────────────────────────────────────────────


async def test_link_without_password_opens_immediately() -> None:
    """proposal §28.5 criterion 7 — no password step when none was set."""
    owner, items, doc = await _drive_with_file()
    links = MemShareLinkRepo()
    token = await _link_for(items, links, doc.id, owner)

    result = await _svc(items, links).open_session(token, None)

    assert result.access_token
    assert result.item.name == "report.txt"
    assert result.permission == Permission.DOWNLOADER


async def test_unknown_token_and_wrong_password_are_indistinguishable() -> None:
    """proposal §28.5 criterion 5 — the two failures must look identical."""
    owner, items, doc = await _drive_with_file()
    links = MemShareLinkRepo()
    token = await _link_for(items, links, doc.id, owner, password="correct")
    svc = _svc(items, links)

    with pytest.raises(AppError) as unknown:
        await svc.open_session("no-such-token", "anything")
    with pytest.raises(AppError) as wrong:
        await svc.open_session(token, "incorrect")

    assert unknown.value.code == wrong.value.code == ErrorCode.SHARE_LINK_INVALID
    assert unknown.value.status_code == wrong.value.status_code == 404
    assert unknown.value.message == wrong.value.message


async def test_password_protected_link_asks_for_a_password_first() -> None:
    owner, items, doc = await _drive_with_file()
    links = MemShareLinkRepo()
    token = await _link_for(items, links, doc.id, owner, password="s3cret")

    with pytest.raises(AppError) as exc:
        await _svc(items, links).open_session(token, None)

    assert exc.value.code == ErrorCode.SHARE_LINK_PASSWORD_REQUIRED
    # Nothing about the item may leak before the password is accepted
    # (proposal §28.3 rule 2).
    assert "report" not in exc.value.message


async def test_correct_password_opens_the_session() -> None:
    owner, items, doc = await _drive_with_file()
    links = MemShareLinkRepo()
    token = await _link_for(items, links, doc.id, owner, password="s3cret")

    result = await _svc(items, links).open_session(token, "s3cret")
    assert result.item.id == doc.id


async def test_disabled_and_expired_links_fail_like_a_bad_token() -> None:
    owner, items, doc = await _drive_with_file()
    links = MemShareLinkRepo()
    disabled = await _link_for(items, links, doc.id, owner)
    expired = await _link_for(
        items, links, doc.id, owner, expires_at=datetime.now(UTC) - timedelta(hours=1)
    )
    svc = _svc(items, links)
    stored = await _stored(links, disabled)
    assert stored is not None
    await links.deactivate(stored.id)

    for token in (disabled, expired):
        with pytest.raises(AppError) as exc:
            await svc.open_session(token, None)
        assert exc.value.code == ErrorCode.SHARE_LINK_INVALID


# ── rate limiting (proposal §28.5 criterion 8) ───────────────────────────────


async def test_sixth_attempt_within_a_minute_locks_the_link() -> None:
    owner, items, doc = await _drive_with_file()
    links = MemShareLinkRepo()
    token = await _link_for(items, links, doc.id, owner, password="correct")
    svc = _svc(items, links)

    for _ in range(5):
        with pytest.raises(AppError):
            await svc.open_session(token, "wrong")

    # The 6th attempt trips the lock, and from then on even the *right*
    # password is refused until the lockout expires.
    with pytest.raises(AppError):
        await svc.open_session(token, "wrong")
    with pytest.raises(AppError) as exc:
        await svc.open_session(token, "correct")
    assert exc.value.code == ErrorCode.SHARE_LINK_INVALID


async def test_lockout_expires_and_access_is_restored() -> None:
    owner, items, doc = await _drive_with_file()
    links = MemShareLinkRepo()
    token = await _link_for(items, links, doc.id, owner, password="correct")
    svc = _svc(items, links)

    for _ in range(6):
        with pytest.raises(AppError):
            await svc.open_session(token, "wrong")

    stored = await _stored(links, token)
    assert stored is not None and stored.locked_until is not None
    # Rewind the clock rather than sleeping through the real lockout.
    stored.locked_until = datetime.now(UTC) - timedelta(seconds=1)
    stored.attempt_window_start = datetime.now(UTC) - timedelta(minutes=2)

    result = await svc.open_session(token, "correct")
    assert result.item.id == doc.id


async def test_probing_a_password_protected_link_does_not_consume_attempts() -> None:
    """The UI's first (password-less) request is part of the normal flow."""
    owner, items, doc = await _drive_with_file()
    links = MemShareLinkRepo()
    token = await _link_for(items, links, doc.id, owner, password="correct")
    svc = _svc(items, links)

    for _ in range(10):
        with pytest.raises(AppError) as exc:
            await svc.open_session(token, None)
        assert exc.value.code == ErrorCode.SHARE_LINK_PASSWORD_REQUIRED

    assert (await svc.open_session(token, "correct")).item.id == doc.id


# ── credential separation (design §6.12.8) ───────────────────────────────────


async def test_share_credential_cannot_be_used_as_a_user_token() -> None:
    """The whole no-escalation guarantee rests on the distinct type claim."""
    credential = create_share_access_token(
        link_id=uuid4(), root_item_id=uuid4(), permission="viewer"
    )
    with pytest.raises(UnauthorizedError):
        decode_access_token(credential)


async def test_user_token_cannot_be_used_as_a_share_credential() -> None:
    with pytest.raises(UnauthorizedError):
        decode_share_access_token(create_access_token(uuid4()))


async def test_garbage_credential_is_rejected_as_invalid() -> None:
    _owner, items, _doc = await _drive_with_file()
    links = MemShareLinkRepo()
    with pytest.raises(AppError) as exc:
        await _svc(items, links).get_root("not-a-jwt")
    assert exc.value.code == ErrorCode.SHARE_LINK_INVALID


# ── per-request revalidation (proposal §28.3 rule 5) ─────────────────────────


async def test_disabling_a_link_invalidates_live_credentials_immediately() -> None:
    owner, items, doc = await _drive_with_file()
    links = MemShareLinkRepo()
    token = await _link_for(items, links, doc.id, owner)
    svc = _svc(items, links)
    credential = (await svc.open_session(token, None)).access_token
    assert (await svc.get_root(credential)).id == doc.id

    stored = await _stored(links, token)
    assert stored is not None
    await links.deactivate(stored.id)

    with pytest.raises(AppError) as exc:
        await svc.get_root(credential)
    assert exc.value.code == ErrorCode.SHARE_LINK_INVALID


# ── subtree boundary (proposal §28.3 rule 4) ─────────────────────────────────


async def test_items_outside_the_shared_subtree_are_not_reachable() -> None:
    owner = uuid4()
    items = MemDriveItemRepo()
    shared = _item(owner_id=owner, name="Shared")
    outsider = _item(owner_id=owner, item_type=ItemType.FILE, name="private.txt")
    inside = _item(owner_id=owner, parent_id=shared.id, item_type=ItemType.FILE, name="inside.txt")
    for i in (shared, outsider, inside):
        items._items[i.id] = i
    links = MemShareLinkRepo()
    token = await _link_for(items, links, shared.id, owner)
    svc = _svc(items, links)
    credential = (await svc.open_session(token, None)).access_token

    # Inside the subtree: fine.
    page = await svc.list_children(credential, shared.id)
    assert [c.name for c in page.items] == ["inside.txt"]

    # Outside: 404, not 403 — a 403 would confirm the id exists.
    with pytest.raises(AppError) as exc:
        await svc.download(credential, outsider.id)
    assert exc.value.status_code == 404
    assert exc.value.code == ErrorCode.SHARE_LINK_INVALID


async def test_deeply_nested_descendants_are_reachable() -> None:
    owner = uuid4()
    items = MemDriveItemRepo()
    root = _item(owner_id=owner, name="Root")
    mid = _item(owner_id=owner, parent_id=root.id, name="Mid")
    leaf = _item(owner_id=owner, parent_id=mid.id, item_type=ItemType.FILE, name="deep.txt")
    leaf.storage_key = "blob/deep"
    for i in (root, mid, leaf):
        items._items[i.id] = i
    links = MemShareLinkRepo()
    token = await _link_for(items, links, root.id, owner)
    svc = _svc(items, links)
    credential = (await svc.open_session(token, None)).access_token

    result = await svc.download(credential, leaf.id)
    assert result.filename == "deep.txt"


# ── permission tier (proposal §28.5 criterion 3) ─────────────────────────────


async def test_viewer_link_cannot_download_even_though_creator_owns_the_file() -> None:
    """Permission comes from the link, never from 'the creator is the owner'."""
    owner, items, doc = await _drive_with_file()
    links = MemShareLinkRepo()
    token = await _link_for(items, links, doc.id, owner, permission=LinkPermission.VIEWER)
    svc = _svc(items, links)
    credential = (await svc.open_session(token, None)).access_token

    with pytest.raises(ForbiddenError):
        await svc.download(credential, doc.id)
    with pytest.raises(ForbiddenError):
        await svc.archive(credential)


async def test_downloader_link_can_download() -> None:
    owner, items, doc = await _drive_with_file()
    links = MemShareLinkRepo()
    token = await _link_for(items, links, doc.id, owner, permission=LinkPermission.DOWNLOADER)
    svc = _svc(items, links)
    credential = (await svc.open_session(token, None)).access_token

    result = await svc.download(credential, doc.id)
    assert result.filename == "report.txt"


async def test_deleted_item_behind_a_live_link_is_not_served() -> None:
    owner, items, doc = await _drive_with_file()
    links = MemShareLinkRepo()
    token = await _link_for(items, links, doc.id, owner)
    doc.is_deleted = True

    with pytest.raises(AppError) as exc:
        await _svc(items, links).open_session(token, None)
    assert exc.value.code == ErrorCode.SHARE_LINK_INVALID


# ── refresh (design §6.12.8) ─────────────────────────────────────────────────


async def test_refresh_extends_the_session_without_the_password() -> None:
    owner, items, doc = await _drive_with_file()
    links = MemShareLinkRepo()
    token = await _link_for(items, links, doc.id, owner, password="s3cret")
    svc = _svc(items, links)
    first = (await svc.open_session(token, "s3cret")).access_token

    second = await svc.refresh_session(first)
    assert second.access_token
    assert second.item.id == doc.id


async def test_refresh_cannot_outrun_the_total_lifetime_cap() -> None:
    owner, items, doc = await _drive_with_file()
    links = MemShareLinkRepo()
    await _link_for(items, links, doc.id, owner)
    # A credential whose chain began well beyond the cap.
    stale = create_share_access_token(
        link_id=uuid4(),
        root_item_id=doc.id,
        permission="viewer",
        chain_started_at=datetime.now(UTC) - timedelta(days=1),
    )
    with pytest.raises(AppError) as exc:
        await _svc(items, links).refresh_session(stale)
    assert exc.value.code == ErrorCode.SHARE_LINK_INVALID


# ── guest writes (editor links, proposal §33) ────────────────────────────────


def _svc_with_writes(items: MemDriveItemRepo, links: MemShareLinkRepo) -> PublicShareService:
    """A service wired for writes, with the downstream services mocked.

    The mocks matter: everything below runs downstream as the *owner*, whose
    permissions exceed editor's. These tests therefore assert that the guard
    fires before the downstream call, not that the downstream refused.
    """
    return PublicShareService(
        item_repo=items,
        link_repo=links,
        storage=_Storage(),  # type: ignore[arg-type]
        preview_svc=AsyncMock(),
        download_svc=AsyncMock(),
        drive_svc=AsyncMock(),
        upload_svc=AsyncMock(),
        trash_svc=AsyncMock(),
    )


async def _editor_credential(
    items: MemDriveItemRepo, links: MemShareLinkRepo, root_id: UUID, owner: UUID
) -> tuple[PublicShareService, str]:
    # An editor link must carry an expiry — that rule is enforced in create_link,
    # so every fixture here has to satisfy it.
    token = await _link_for(
        items,
        links,
        root_id,
        owner,
        permission=LinkPermission.EDITOR,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    svc = _svc_with_writes(items, links)
    return svc, (await svc.open_session(token, None)).access_token


async def test_a_viewer_link_cannot_write() -> None:
    owner, items, doc = await _drive_with_file()
    links = MemShareLinkRepo()
    token = await _link_for(items, links, doc.id, owner, permission=LinkPermission.VIEWER)
    svc = _svc_with_writes(items, links)
    credential = (await svc.open_session(token, None)).access_token

    with pytest.raises(ForbiddenError):
        await svc.rename(credential, doc.id, "renamed.txt")
    # The guard must fire before anything downstream is asked — downstream runs
    # as the owner and would happily comply.
    svc._drive.rename.assert_not_awaited()  # type: ignore[attr-defined]


async def test_a_downloader_link_cannot_write() -> None:
    owner, items, doc = await _drive_with_file()
    links = MemShareLinkRepo()
    token = await _link_for(items, links, doc.id, owner, permission=LinkPermission.DOWNLOADER)
    svc = _svc_with_writes(items, links)
    credential = (await svc.open_session(token, None)).access_token

    with pytest.raises(ForbiddenError):
        await svc.trash(credential, doc.id)


async def test_an_editor_link_renames_as_the_owner() -> None:
    owner = uuid4()
    items = MemDriveItemRepo()
    folder = _item(owner_id=owner, name="Shared")
    inside = _item(owner_id=owner, parent_id=folder.id, item_type=ItemType.FILE, name="a.txt")
    for i in (folder, inside):
        items._items[i.id] = i
    links = MemShareLinkRepo()
    svc, credential = await _editor_credential(items, links, folder.id, owner)

    await svc.rename(credential, inside.id, "b.txt")

    # Downstream is called with the owner's id — the only identity the existing
    # services accept for a visitor who has no account of their own.
    svc._drive.rename.assert_awaited_once_with(owner, inside.id, "b.txt")  # type: ignore[attr-defined]


async def test_writes_outside_the_subtree_look_absent() -> None:
    owner = uuid4()
    items = MemDriveItemRepo()
    shared = _item(owner_id=owner, name="Shared")
    outsider = _item(owner_id=owner, item_type=ItemType.FILE, name="private.txt")
    for i in (shared, outsider):
        items._items[i.id] = i
    links = MemShareLinkRepo()
    svc, credential = await _editor_credential(items, links, shared.id, owner)

    with pytest.raises(AppError) as exc:
        await svc.rename(credential, outsider.id, "hijacked.txt")

    # 404, not 403 — a 403 would confirm the id exists.
    assert exc.value.status_code == 404
    svc._drive.rename.assert_not_awaited()  # type: ignore[attr-defined]


async def test_moving_out_of_the_subtree_is_refused() -> None:
    owner = uuid4()
    items = MemDriveItemRepo()
    shared = _item(owner_id=owner, name="Shared")
    inside = _item(owner_id=owner, parent_id=shared.id, item_type=ItemType.FILE, name="a.txt")
    elsewhere = _item(owner_id=owner, name="Elsewhere")
    for i in (shared, inside, elsewhere):
        items._items[i.id] = i
    links = MemShareLinkRepo()
    svc, credential = await _editor_credential(items, links, shared.id, owner)

    with pytest.raises(AppError):
        await svc.move(credential, inside.id, elsewhere.id)

    svc._drive.move.assert_not_awaited()  # type: ignore[attr-defined]


async def test_the_shared_item_itself_cannot_be_trashed() -> None:
    owner = uuid4()
    items = MemDriveItemRepo()
    shared = _item(owner_id=owner, name="Shared")
    items._items[shared.id] = shared
    links = MemShareLinkRepo()
    svc, credential = await _editor_credential(items, links, shared.id, owner)

    with pytest.raises(AppError):
        # Otherwise the link stays alive pointing at nothing.
        await svc.trash(credential, shared.id)


async def test_upload_is_charged_to_the_owner() -> None:
    owner = uuid4()
    items = MemDriveItemRepo()
    folder = _item(owner_id=owner, name="Dropbox")
    items._items[folder.id] = folder
    links = MemShareLinkRepo()
    svc, credential = await _editor_credential(items, links, folder.id, owner)

    # The service reloads the created row, so the mock has to name a real one.
    uploaded = _item(owner_id=owner, parent_id=folder.id, item_type=ItemType.FILE, name="note.txt")
    items._items[uploaded.id] = uploaded
    svc._upload.upload_simple.return_value = uploaded  # type: ignore[attr-defined]

    async def _bytes() -> AsyncGenerator[bytes, None]:
        yield b"hello"

    await svc.upload(credential, folder.id, filename="note.txt", stream=_bytes(), size_bytes=5)

    called = svc._upload.upload_simple.await_args  # type: ignore[attr-defined]
    # First positional arg is the user the quota is charged to.
    assert called.args[0] == owner


async def test_audit_context_names_the_owner_and_the_link() -> None:
    owner, items, doc = await _drive_with_file()
    links = MemShareLinkRepo()
    svc, credential = await _editor_credential(items, links, doc.id, owner)

    who = await svc.audit_context(credential)

    # Both halves are needed: the owner alone would read as "they did it".
    assert who.owner_id == owner
    assert who.link_id is not None


# ── selected-item archive (proposal §34.4) ───────────────────────────────────


async def _shared_folder_with_two_files() -> tuple[
    UUID, MemDriveItemRepo, DriveItem, DriveItem, DriveItem, DriveItem
]:
    """A share root holding two files, plus one file outside it."""
    owner = uuid4()
    items = MemDriveItemRepo()
    root = _item(owner_id=owner, name="Shared")
    a = _item(owner_id=owner, parent_id=root.id, item_type=ItemType.FILE, name="a.txt")
    b = _item(owner_id=owner, parent_id=root.id, item_type=ItemType.FILE, name="b.txt")
    outside = _item(owner_id=owner, item_type=ItemType.FILE, name="secret.txt")
    for i in (root, a, b, outside):
        i.storage_key = f"blob/{i.name}"
        items._items[i.id] = i
    return owner, items, root, a, b, outside


async def test_archive_packs_only_the_items_asked_for() -> None:
    owner, items, root, a, b, _ = await _shared_folder_with_two_files()
    links = MemShareLinkRepo()
    token = await _link_for(items, links, root.id, owner)
    svc = _svc(items, links)
    credential = (await svc.open_session(token, None)).access_token

    await svc.archive(credential, [a.id, b.id])

    cast(AsyncMock, svc._download.archive).assert_awaited_once_with(owner, [a.id, b.id])


async def test_archive_without_ids_still_packs_the_whole_root() -> None:
    """The original GET behaviour must survive the new parameter."""
    owner, items, root, _, _, _ = await _shared_folder_with_two_files()
    links = MemShareLinkRepo()
    token = await _link_for(items, links, root.id, owner)
    svc = _svc(items, links)
    credential = (await svc.open_session(token, None)).access_token

    await svc.archive(credential)

    cast(AsyncMock, svc._download.archive).assert_awaited_once_with(owner, [root.id])


async def test_archive_rejects_the_whole_request_when_one_id_is_outside() -> None:
    """No partial packing — the difference would leak whether an id exists."""
    owner, items, root, a, _, outside = await _shared_folder_with_two_files()
    links = MemShareLinkRepo()
    token = await _link_for(items, links, root.id, owner)
    svc = _svc(items, links)
    credential = (await svc.open_session(token, None)).access_token

    with pytest.raises(AppError) as err:
        await svc.archive(credential, [a.id, outside.id])

    assert err.value.code == ErrorCode.SHARE_LINK_INVALID
    cast(AsyncMock, svc._download.archive).assert_not_awaited()


async def test_archive_of_selection_refuses_a_viewer_link() -> None:
    owner, items, root, a, _, _ = await _shared_folder_with_two_files()
    links = MemShareLinkRepo()
    token = await _link_for(items, links, root.id, owner, permission=LinkPermission.VIEWER)
    svc = _svc(items, links)
    credential = (await svc.open_session(token, None)).access_token

    with pytest.raises(ForbiddenError):
        await svc.archive(credential, [a.id])


async def test_archive_with_an_empty_selection_is_an_error_not_the_whole_root() -> None:
    owner, items, root, _, _, _ = await _shared_folder_with_two_files()
    links = MemShareLinkRepo()
    token = await _link_for(items, links, root.id, owner)
    svc = _svc(items, links)
    credential = (await svc.open_session(token, None)).access_token

    with pytest.raises(AppError) as err:
        await svc.archive(credential, [])

    assert err.value.code == ErrorCode.INVALID_OPERATION
    cast(AsyncMock, svc._download.archive).assert_not_awaited()

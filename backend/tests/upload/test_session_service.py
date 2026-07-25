from __future__ import annotations

import hashlib
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, NotFoundError, QuotaExceededError
from app.drive.schemas import ItemType
from app.models.drive_item import DriveItem
from app.models.upload_session import UploadChunk, UploadSession
from app.models.user import User
from app.permission.service import PermissionService
from app.upload.session_service import UploadSessionService
from tests.drive.test_service import MemDriveItemRepo, _item
from tests.file_version.test_service import MemFileVersionRepo
from tests.permission.test_service import MemItemRepo, MemShareRepo
from tests.upload.test_service import MemStorage, _make_user
from tests.users.test_service import MockUserRepo

CHUNK_SIZE = 8
MAX_FILE_SIZE = 1024
RETENTION_DAYS = 7


# ── Fake session repository ──────────────────────────────────────────────────


class MemSessionRepo:
    def __init__(self) -> None:
        self.sessions: dict[UUID, UploadSession] = {}
        self.chunks: list[UploadChunk] = []

    async def create(
        self,
        *,
        user_id: UUID,
        parent_id: UUID | None,
        filename: str,
        mime_type: str | None,
        total_size: int,
        chunk_size: int,
        total_chunks: int,
        expires_at: datetime,
        now: datetime,
    ) -> UploadSession:
        session = UploadSession(
            id=uuid4(),
            user_id=user_id,
            parent_id=parent_id,
            filename=filename,
            mime_type=mime_type,
            total_size=total_size,
            chunk_size=chunk_size,
            total_chunks=total_chunks,
            status="pending",
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )
        self.sessions[session.id] = session
        return session

    async def get_for_user(self, session_id: UUID, user_id: UUID) -> UploadSession | None:
        session = self.sessions.get(session_id)
        if session is None or session.user_id != user_id:
            return None
        return session

    async def list_completed_indexes(self, session_id: UUID) -> list[int]:
        return sorted(c.chunk_index for c in self.chunks if c.session_id == session_id)

    async def list_chunks(self, session_id: UUID) -> list[UploadChunk]:
        return sorted(
            (c for c in self.chunks if c.session_id == session_id),
            key=lambda c: c.chunk_index,
        )

    async def upsert_chunk(
        self,
        *,
        session_id: UUID,
        chunk_index: int,
        size: int,
        storage_key: str,
        checksum_sha256: str | None,
        now: datetime,
    ) -> None:
        for chunk in self.chunks:
            if chunk.session_id == session_id and chunk.chunk_index == chunk_index:
                chunk.size = size
                chunk.storage_key = storage_key
                chunk.checksum_sha256 = checksum_sha256
                return
        self.chunks.append(
            UploadChunk(
                id=uuid4(),
                session_id=session_id,
                chunk_index=chunk_index,
                size=size,
                storage_key=storage_key,
                checksum_sha256=checksum_sha256,
                created_at=now,
            )
        )

    async def update_status(
        self,
        session_id: UUID,
        status: str,
        *,
        now: datetime,
        checksum_sha256: str | None = None,
        drive_item_id: UUID | None = None,
        error_code: str | None = None,
    ) -> None:
        session = self.sessions.get(session_id)
        if session is None:
            return
        session.status = status
        session.updated_at = now
        if checksum_sha256 is not None:
            session.checksum_sha256 = checksum_sha256
        if drive_item_id is not None:
            session.drive_item_id = drive_item_id
        if error_code is not None:
            session.error_code = error_code

    async def sum_active_total_size(
        self, user_id: UUID, *, exclude_session_id: UUID | None = None
    ) -> int:
        return sum(
            s.total_size
            for s in self.sessions.values()
            if s.user_id == user_id
            and s.status in ("pending", "uploading")
            and s.id != exclude_session_id
        )

    async def list_expired(self, now: datetime) -> list[UploadSession]:
        return [
            s
            for s in self.sessions.values()
            if s.expires_at < now and s.status in ("pending", "uploading")
        ]

    async def delete_chunks(self, session_id: UUID) -> None:
        self.chunks = [c for c in self.chunks if c.session_id != session_id]

    async def delete_session(self, session_id: UUID) -> None:
        self.sessions.pop(session_id, None)


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_svc(
    items: list[DriveItem] | None = None,
    user: User | None = None,
    storage: MemStorage | None = None,
    max_file_size: int = MAX_FILE_SIZE,
) -> tuple[
    UploadSessionService, MemSessionRepo, MemDriveItemRepo, MemFileVersionRepo, MemStorage, User
]:
    if user is None:
        user = _make_user()
    if storage is None:
        storage = MemStorage()
    session_repo = MemSessionRepo()
    item_repo = MemDriveItemRepo(items)
    version_repo = MemFileVersionRepo()
    from app.users.service import QuotaService

    svc = UploadSessionService(
        session_repo=session_repo,  # type: ignore[arg-type]
        item_repo=item_repo,
        version_repo=version_repo,
        storage=storage,
        permission_svc=PermissionService(
            share_repo=MemShareRepo(None),
            item_repo=MemItemRepo(items),
        ),
        quota_svc=QuotaService(repo=MockUserRepo(user)),
        chunk_size=CHUNK_SIZE,
        max_file_size=max_file_size,
        retention_days=RETENTION_DAYS,
    )
    return svc, session_repo, item_repo, version_repo, storage, user


async def _stream(data: bytes) -> AsyncGenerator[bytes, None]:
    yield data


async def _upload_all(
    svc: UploadSessionService, user_id: UUID, session_id: UUID, content: bytes
) -> None:
    """Send every chunk of `content`, in order."""
    for index in range(-(-len(content) // CHUNK_SIZE)):
        piece = content[index * CHUNK_SIZE : (index + 1) * CHUNK_SIZE]
        await svc.upload_chunk(user_id, session_id, index, _stream(piece))


# ── create_session ───────────────────────────────────────────────────────────


async def test_create_session_returns_chunking_plan() -> None:
    svc, _, _, _, _, user = _make_svc()
    status = await svc.create_session(user.id, filename="big.bin", total_size=20)
    # 20 bytes at 8 bytes per chunk -> 3 chunks (last one partial).
    assert status.session.total_chunks == 3
    assert status.session.chunk_size == CHUNK_SIZE
    assert status.session.status == "pending"
    assert status.uploaded_chunks == []


async def test_create_session_sets_expiry_from_retention() -> None:
    svc, _, _, _, _, user = _make_svc()
    before = datetime.now(UTC)
    status = await svc.create_session(user.id, filename="f.bin", total_size=8)
    delta = status.session.expires_at - before
    assert timedelta(days=RETENTION_DAYS) - delta < timedelta(minutes=1)


async def test_create_session_rejects_file_over_limit() -> None:
    svc, _, _, _, _, user = _make_svc(max_file_size=100)
    with pytest.raises(AppError) as exc:
        await svc.create_session(user.id, filename="huge.bin", total_size=101)
    assert exc.value.code == ErrorCode.FILE_TOO_LARGE
    assert exc.value.status_code == 413


async def test_create_session_rejects_when_quota_short() -> None:
    user = _make_user(quota_bytes=100, used_bytes=90)
    svc, _, _, _, _, _ = _make_svc(user=user)
    with pytest.raises(QuotaExceededError):
        await svc.create_session(user.id, filename="f.bin", total_size=50)


async def test_quota_precheck_counts_other_unfinished_sessions() -> None:
    """Two large uploads opened at once must not jointly oversell the quota."""
    user = _make_user(quota_bytes=100, used_bytes=0)
    svc, _, _, _, _, _ = _make_svc(user=user)

    await svc.create_session(user.id, filename="a.bin", total_size=60)
    # 60 is already promised; another 60 would need 120 of the 100 available.
    with pytest.raises(QuotaExceededError):
        await svc.create_session(user.id, filename="b.bin", total_size=60)


async def test_create_session_rejects_missing_parent() -> None:
    svc, _, _, _, _, user = _make_svc()
    with pytest.raises(NotFoundError):
        await svc.create_session(user.id, filename="f.bin", total_size=8, parent_id=uuid4())


async def test_create_session_rejects_parent_that_is_a_file() -> None:
    user = _make_user()
    file_item = _item(owner_id=user.id, item_type=ItemType.FILE, name="doc.pdf")
    svc, _, _, _, _, _ = _make_svc(items=[file_item], user=user)
    with pytest.raises(AppError) as exc:
        await svc.create_session(user.id, filename="f.bin", total_size=8, parent_id=file_item.id)
    assert exc.value.code == ErrorCode.INVALID_OPERATION


# ── authorization ────────────────────────────────────────────────────────────


async def test_other_users_session_is_reported_as_not_found() -> None:
    svc, _, _, _, _, user = _make_svc()
    status = await svc.create_session(user.id, filename="f.bin", total_size=8)
    stranger = uuid4()

    # Every entry point must hide the session's existence, not just refuse it.
    with pytest.raises(NotFoundError):
        await svc.get_session(stranger, status.session.id)
    with pytest.raises(NotFoundError):
        await svc.upload_chunk(stranger, status.session.id, 0, _stream(b"x"))
    with pytest.raises(NotFoundError):
        await svc.complete_session(stranger, status.session.id)
    with pytest.raises(NotFoundError):
        await svc.cancel_session(stranger, status.session.id)


# ── upload_chunk ─────────────────────────────────────────────────────────────


async def test_first_chunk_moves_session_to_uploading() -> None:
    svc, repo, _, _, _, user = _make_svc()
    status = await svc.create_session(user.id, filename="f.bin", total_size=16)
    assert repo.sessions[status.session.id].status == "pending"

    await svc.upload_chunk(user.id, status.session.id, 0, _stream(b"a" * 8))

    assert repo.sessions[status.session.id].status == "uploading"


async def test_get_session_reports_uploaded_indexes_for_resume() -> None:
    svc, _, _, _, _, user = _make_svc()
    status = await svc.create_session(user.id, filename="f.bin", total_size=24)

    await svc.upload_chunk(user.id, status.session.id, 0, _stream(b"a" * 8))
    await svc.upload_chunk(user.id, status.session.id, 2, _stream(b"c" * 8))

    resumed = await svc.get_session(user.id, status.session.id)
    # The client learns exactly which chunk is still missing.
    assert resumed.uploaded_chunks == [0, 2]


async def test_resending_a_chunk_overwrites_it() -> None:
    svc, repo, _, _, storage, user = _make_svc()
    status = await svc.create_session(user.id, filename="f.bin", total_size=8)

    await svc.upload_chunk(user.id, status.session.id, 0, _stream(b"first!!!"))
    await svc.upload_chunk(user.id, status.session.id, 0, _stream(b"second!!"))

    chunks = await repo.list_chunks(status.session.id)
    assert len(chunks) == 1  # idempotent, not duplicated
    assert storage._data[chunks[0].storage_key] == b"second!!"


async def test_chunk_index_out_of_range_is_rejected() -> None:
    svc, _, _, _, _, user = _make_svc()
    status = await svc.create_session(user.id, filename="f.bin", total_size=8)  # 1 chunk

    for bad_index in (-1, 1, 99):
        with pytest.raises(AppError) as exc:
            await svc.upload_chunk(user.id, status.session.id, bad_index, _stream(b"x"))
        assert exc.value.code == ErrorCode.INVALID_OPERATION


async def test_terminal_session_refuses_more_chunks() -> None:
    svc, _, _, _, _, user = _make_svc()
    status = await svc.create_session(user.id, filename="f.bin", total_size=8)
    await svc.cancel_session(user.id, status.session.id)

    with pytest.raises(AppError) as exc:
        await svc.upload_chunk(user.id, status.session.id, 0, _stream(b"x"))
    assert exc.value.code == ErrorCode.INVALID_OPERATION


# ── complete_session ─────────────────────────────────────────────────────────


async def test_complete_merges_chunks_into_one_file() -> None:
    svc, _, item_repo, version_repo, storage, user = _make_svc()
    content = b"".join(bytes([i]) * CHUNK_SIZE for i in range(5))[:34]
    status = await svc.create_session(
        user.id, filename="movie.bin", total_size=len(content), mime_type="video/mp4"
    )
    await _upload_all(svc, user.id, status.session.id, content)

    resp = await svc.complete_session(user.id, status.session.id)

    item = await item_repo.get_by_id(resp.id)
    assert item is not None
    assert item.size_bytes == len(content)
    assert item.checksum_sha256 == hashlib.sha256(content).hexdigest()
    assert item.mime_type == "video/mp4"
    # The merged blob must be byte-identical to the original.
    assert item.storage_key is not None
    assert storage._data[item.storage_key] == content

    versions = await version_repo.list_by_file(resp.id)
    assert len(versions) == 1
    assert versions[0].version_no == 1
    assert versions[0].checksum_sha256 == hashlib.sha256(content).hexdigest()


async def test_complete_charges_quota_only_at_the_end() -> None:
    user = _make_user(quota_bytes=10_000, used_bytes=0)
    svc, _, _, _, _, _ = _make_svc(user=user)
    content = b"x" * 24
    status = await svc.create_session(user.id, filename="f.bin", total_size=len(content))

    await _upload_all(svc, user.id, status.session.id, content)
    assert user.used_bytes == 0  # nothing charged while chunks were arriving

    await svc.complete_session(user.id, status.session.id)
    assert user.used_bytes == len(content)


async def test_complete_removes_temporary_chunks() -> None:
    svc, repo, _, _, storage, user = _make_svc()
    content = b"y" * 24
    status = await svc.create_session(user.id, filename="f.bin", total_size=len(content))
    await _upload_all(svc, user.id, status.session.id, content)
    chunk_keys = [c.storage_key for c in await repo.list_chunks(status.session.id)]

    await svc.complete_session(user.id, status.session.id)

    assert await repo.list_chunks(status.session.id) == []
    for key in chunk_keys:
        assert key not in storage._data


async def test_complete_marks_session_completed_and_links_item() -> None:
    svc, repo, _, _, _, user = _make_svc()
    content = b"z" * 8
    status = await svc.create_session(user.id, filename="f.bin", total_size=len(content))
    await _upload_all(svc, user.id, status.session.id, content)

    resp = await svc.complete_session(user.id, status.session.id)

    session = repo.sessions[status.session.id]
    assert session.status == "completed"
    assert session.drive_item_id == resp.id
    assert session.checksum_sha256 == hashlib.sha256(content).hexdigest()


async def test_complete_with_missing_chunks_fails_but_keeps_session_resumable() -> None:
    svc, repo, _, _, _, user = _make_svc()
    content = b"q" * 24  # 3 chunks
    status = await svc.create_session(user.id, filename="f.bin", total_size=len(content))
    await svc.upload_chunk(user.id, status.session.id, 0, _stream(content[:8]))
    await svc.upload_chunk(user.id, status.session.id, 2, _stream(content[16:]))

    with pytest.raises(AppError) as exc:
        await svc.complete_session(user.id, status.session.id)
    assert exc.value.code == ErrorCode.INVALID_OPERATION

    # Still resumable: the gap can be filled and completion retried.
    assert repo.sessions[status.session.id].status == "uploading"
    await svc.upload_chunk(user.id, status.session.id, 1, _stream(content[8:16]))
    resp = await svc.complete_session(user.id, status.session.id)
    assert resp.size_bytes == len(content)


async def test_complete_auto_renames_on_name_conflict() -> None:
    user = _make_user()
    existing = _item(owner_id=user.id, item_type=ItemType.FILE, name="report.pdf")
    svc, _, _, _, _, _ = _make_svc(items=[existing], user=user)
    status = await svc.create_session(user.id, filename="report.pdf", total_size=8)
    await _upload_all(svc, user.id, status.session.id, b"a" * 8)

    resp = await svc.complete_session(user.id, status.session.id)

    assert resp.name == "report (1).pdf"


async def test_completing_twice_is_rejected() -> None:
    svc, _, _, _, _, user = _make_svc()
    status = await svc.create_session(user.id, filename="f.bin", total_size=8)
    await _upload_all(svc, user.id, status.session.id, b"a" * 8)
    await svc.complete_session(user.id, status.session.id)

    with pytest.raises(AppError) as exc:
        await svc.complete_session(user.id, status.session.id)
    assert exc.value.code == ErrorCode.INVALID_OPERATION


async def test_db_failure_during_complete_deletes_the_merged_blob() -> None:
    user = _make_user()
    svc, _, _, _, storage, _ = _make_svc(user=user)
    status = await svc.create_session(user.id, filename="f.bin", total_size=8)
    await _upload_all(svc, user.id, status.session.id, b"a" * 8)

    class FailingVersionRepo(MemFileVersionRepo):
        async def create(self, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("DB is down")

    svc._versions = FailingVersionRepo()

    with pytest.raises(RuntimeError):
        await svc.complete_session(user.id, status.session.id)

    # No orphaned merged blob may remain (only the chunk blobs are left).
    merged = [k for k in storage._data if k.startswith(f"users/{user.id}/files/")]
    assert merged == []
    assert storage.deleted  # the merge was cleaned up


async def test_empty_file_completes_without_chunks() -> None:
    svc, _, item_repo, _, _, user = _make_svc()
    status = await svc.create_session(user.id, filename="empty.txt", total_size=0)
    assert status.session.total_chunks == 0

    resp = await svc.complete_session(user.id, status.session.id)

    assert resp.size_bytes == 0
    item = await item_repo.get_by_id(resp.id)
    assert item is not None
    assert item.checksum_sha256 == hashlib.sha256(b"").hexdigest()


# ── cancel_session ───────────────────────────────────────────────────────────


async def test_cancel_marks_cancelled_and_drops_chunks() -> None:
    svc, repo, _, _, storage, user = _make_svc()
    status = await svc.create_session(user.id, filename="f.bin", total_size=16)
    await svc.upload_chunk(user.id, status.session.id, 0, _stream(b"a" * 8))
    chunk_keys = [c.storage_key for c in await repo.list_chunks(status.session.id)]

    await svc.cancel_session(user.id, status.session.id)

    assert repo.sessions[status.session.id].status == "cancelled"
    assert await repo.list_chunks(status.session.id) == []
    for key in chunk_keys:
        assert key not in storage._data


async def test_cancel_does_not_charge_quota() -> None:
    user = _make_user(quota_bytes=10_000, used_bytes=0)
    svc, _, _, _, _, _ = _make_svc(user=user)
    status = await svc.create_session(user.id, filename="f.bin", total_size=16)
    await svc.upload_chunk(user.id, status.session.id, 0, _stream(b"a" * 8))

    await svc.cancel_session(user.id, status.session.id)

    assert user.used_bytes == 0


async def test_cancel_is_idempotent_but_cannot_undo_completion() -> None:
    svc, _, _, _, _, user = _make_svc()
    cancelled = await svc.create_session(user.id, filename="a.bin", total_size=8)
    await svc.cancel_session(user.id, cancelled.session.id)
    await svc.cancel_session(user.id, cancelled.session.id)  # no error

    done = await svc.create_session(user.id, filename="b.bin", total_size=8)
    await _upload_all(svc, user.id, done.session.id, b"a" * 8)
    await svc.complete_session(user.id, done.session.id)
    with pytest.raises(AppError) as exc:
        await svc.cancel_session(user.id, done.session.id)
    assert exc.value.code == ErrorCode.INVALID_OPERATION


# ── cleanup_expired ──────────────────────────────────────────────────────────


async def test_cleanup_removes_expired_sessions_and_their_chunks() -> None:
    svc, repo, _, _, storage, user = _make_svc()
    stale = await svc.create_session(user.id, filename="old.bin", total_size=16)
    await svc.upload_chunk(user.id, stale.session.id, 0, _stream(b"a" * 8))
    stale_keys = [c.storage_key for c in await repo.list_chunks(stale.session.id)]
    # Push it past its retention window.
    repo.sessions[stale.session.id].expires_at = datetime.now(UTC) - timedelta(days=1)

    fresh = await svc.create_session(user.id, filename="new.bin", total_size=8)

    removed = await svc.cleanup_expired()

    assert removed == 1
    assert stale.session.id not in repo.sessions
    for key in stale_keys:
        assert key not in storage._data
    # An in-date session is untouched.
    assert fresh.session.id in repo.sessions


async def test_cleanup_ignores_terminal_sessions() -> None:
    svc, repo, _, _, _, user = _make_svc()
    status = await svc.create_session(user.id, filename="f.bin", total_size=8)
    await svc.cancel_session(user.id, status.session.id)
    repo.sessions[status.session.id].expires_at = datetime.now(UTC) - timedelta(days=1)

    # Already terminal: nothing in flight to reclaim.
    assert await svc.cleanup_expired() == 0

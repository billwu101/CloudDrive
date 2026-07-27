from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, ForbiddenError
from app.drive.schemas import ItemType
from app.models.drive_item import DriveItem
from app.models.share import Share
from app.permission.service import PermissionService
from app.preview.service import (
    _TEXT_MAX_BYTES,
    PreviewService,
    PreviewType,
    _resolve_preview_type,
    resolve_mime,
    resolve_preview_type,
)
from tests.drive.test_service import MemDriveItemRepo, _item
from tests.permission.test_service import MemItemRepo, MemShareRepo
from tests.upload.test_service import MemStorage


def _file(
    owner_id: UUID,
    *,
    storage_key: str | None = "k/v1",
    mime_type: str | None = "text/plain",
) -> DriveItem:
    item = _item(owner_id=owner_id, item_type=ItemType.FILE, name="file.txt")
    item.storage_key = storage_key
    item.mime_type = mime_type
    item.size_bytes = 100
    return item


def _make_svc(
    items: list[DriveItem] | None = None,
    shares: list[Share] | None = None,
    storage: MemStorage | None = None,
) -> PreviewService:
    if storage is None:
        storage = MemStorage()
    return PreviewService(
        item_repo=MemDriveItemRepo(items),
        storage=storage,
        permission_svc=PermissionService(
            share_repo=MemShareRepo(shares),
            item_repo=MemItemRepo(items),
        ),
    )


async def test_image_preview_info() -> None:
    user = uuid4()
    file = _file(user, mime_type="image/jpeg")
    svc = _make_svc(items=[file])
    info = await svc.get_info(user, file.id)
    assert info.preview_type == PreviewType.IMAGE


async def test_pdf_preview_info() -> None:
    user = uuid4()
    file = _file(user, mime_type="application/pdf")
    svc = _make_svc(items=[file])
    info = await svc.get_info(user, file.id)
    assert info.preview_type == PreviewType.PDF


async def test_text_preview_info() -> None:
    user = uuid4()
    file = _file(user, mime_type="text/plain")
    svc = _make_svc(items=[file])
    info = await svc.get_info(user, file.id)
    assert info.preview_type == PreviewType.TEXT


async def test_unsupported_preview_info() -> None:
    user = uuid4()
    file = _file(user, mime_type="application/octet-stream")
    svc = _make_svc(items=[file])
    info = await svc.get_info(user, file.id)
    assert info.preview_type == PreviewType.UNSUPPORTED


async def test_folder_cannot_be_previewed() -> None:
    user = uuid4()
    folder = _item(owner_id=user, item_type=ItemType.FOLDER, name="folder")
    svc = _make_svc(items=[folder])
    with pytest.raises(AppError) as exc_info:
        await svc.get_info(user, folder.id)
    assert exc_info.value.code == ErrorCode.INVALID_OPERATION


async def test_no_permission_cannot_preview() -> None:
    owner = uuid4()
    other = uuid4()
    file = _file(owner)
    svc = _make_svc(items=[file])
    with pytest.raises(ForbiddenError):
        await svc.get_info(other, file.id)


async def test_text_preview_does_not_exceed_limit() -> None:
    user = uuid4()
    storage = MemStorage()
    large_content = b"x" * (_TEXT_MAX_BYTES + 1000)
    storage._data["k/v1"] = large_content
    file = _file(user, mime_type="text/plain")

    # MemStorage.open_read reads from _data directly
    svc = _make_svc(items=[file], storage=storage)
    _, _, stream = await svc.get_content(user, file.id)
    chunks = [c async for c in stream]
    assert len(b"".join(chunks)) <= _TEXT_MAX_BYTES


async def test_unsupported_content_raises() -> None:
    user = uuid4()
    storage = MemStorage()
    storage._data["k/v1"] = b"binary"
    file = _file(user, mime_type="application/octet-stream")
    svc = _make_svc(items=[file], storage=storage)
    with pytest.raises(AppError) as exc_info:
        await svc.get_content(user, file.id)
    assert exc_info.value.code == ErrorCode.INVALID_OPERATION


# ── Office (document) / Markdown preview ──────────────────────────────────────

_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _doc(
    owner_id: UUID,
    *,
    name: str,
    mime: str | None,
    ext: str,
    storage_key: str = "k/doc",
    checksum: str | None = "sum",
) -> DriveItem:
    item = _item(owner_id=owner_id, item_type=ItemType.FILE, name=name)
    item.storage_key = storage_key
    item.mime_type = mime
    item.extension = ext
    item.checksum_sha256 = checksum
    item.size_bytes = 10
    return item


def test_resolve_markdown_by_ext_or_mime() -> None:
    assert _resolve_preview_type("text/markdown", "md", office=True) == PreviewType.MARKDOWN
    assert _resolve_preview_type("text/plain", "markdown", office=False) == PreviewType.MARKDOWN


def test_resolve_office_document_when_available() -> None:
    assert _resolve_preview_type(_DOCX, "docx", office=True) == PreviewType.DOCUMENT
    assert _resolve_preview_type(None, "xlsx", office=True) == PreviewType.DOCUMENT


def test_resolve_office_unsupported_without_libreoffice() -> None:
    assert _resolve_preview_type(_DOCX, "docx", office=False) == PreviewType.UNSUPPORTED


def test_resolve_csv_document_or_text() -> None:
    # csv with LibreOffice -> document (tabular); without -> plain text
    assert _resolve_preview_type("text/csv", "csv", office=True) == PreviewType.DOCUMENT
    assert _resolve_preview_type("text/csv", "csv", office=False) == PreviewType.TEXT


async def test_markdown_info_and_content() -> None:
    user = uuid4()
    storage = MemStorage()
    storage._data["k/md"] = b"# Title\nhello"
    f = _doc(user, name="readme.md", mime="text/markdown", ext="md", storage_key="k/md")
    svc = _make_svc(items=[f], storage=storage)

    info = await svc.get_info(user, f.id)
    assert info.preview_type == PreviewType.MARKDOWN

    ptype, mime, stream = await svc.get_content(user, f.id)
    body = b"".join([c async for c in stream])
    assert ptype == PreviewType.MARKDOWN
    assert mime == "text/markdown"
    assert body == b"# Title\nhello"


async def test_document_converts_caches_and_reuses(monkeypatch: pytest.MonkeyPatch) -> None:
    user = uuid4()
    storage = MemStorage()
    storage._data["k/doc"] = b"raw docx bytes"
    f = _doc(user, name="report.docx", mime=_DOCX, ext="docx", checksum="abc123")
    svc = _make_svc(items=[f], storage=storage)

    import app.preview.service as svc_mod

    monkeypatch.setattr(svc_mod, "office_available", lambda: True)
    calls = {"n": 0}

    async def fake_convert(data: bytes, *, suffix: str, timeout: float = 60.0) -> bytes:
        calls["n"] += 1
        assert suffix == ".docx"
        return b"%PDF-1.4 converted"

    monkeypatch.setattr(svc_mod, "convert_to_pdf", fake_convert)

    info = await svc.get_info(user, f.id)
    assert info.preview_type == PreviewType.DOCUMENT
    assert info.mime_type == "application/pdf"

    ptype, mime, stream = await svc.get_content(user, f.id)
    body = b"".join([c async for c in stream])
    assert (ptype, mime) == (PreviewType.DOCUMENT, "application/pdf")
    assert body == b"%PDF-1.4 converted"
    assert "preview-cache/abc123.pdf" in storage._data
    assert calls["n"] == 1

    # second request hits the cache, no re-conversion
    _, _, stream2 = await svc.get_content(user, f.id)
    b"".join([c async for c in stream2])
    assert calls["n"] == 1


async def test_office_content_unsupported_without_libreoffice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = uuid4()
    storage = MemStorage()
    storage._data["k/doc"] = b"x"
    f = _doc(user, name="r.docx", mime=_DOCX, ext="docx")
    svc = _make_svc(items=[f], storage=storage)

    import app.preview.service as svc_mod

    monkeypatch.setattr(svc_mod, "office_available", lambda: False)
    with pytest.raises(AppError) as exc_info:
        await svc.get_content(user, f.id)
    assert exc_info.value.code == ErrorCode.INVALID_OPERATION


# ── falling back when the stored type is missing ─────────────────────────────


def _bare(name: str, *, mime: str | None = None, ext: str | None = None) -> DriveItem:
    """An item as several upload paths actually leave it: type columns blank."""
    now = datetime.now(UTC)
    return DriveItem(
        id=uuid4(),
        owner_id=uuid4(),
        parent_id=None,
        item_type=ItemType.FILE,
        name=name,
        mime_type=mime,
        extension=ext,
        size_bytes=10,
        storage_key="blob/x",
        checksum_sha256=None,
        is_starred=False,
        is_deleted=False,
        deleted_at=None,
        created_by=uuid4(),
        updated_by=None,
        created_at=now,
        updated_at=now,
    )


def test_a_pdf_with_no_stored_type_is_still_a_pdf() -> None:
    """Regression: an obvious .pdf showed "Preview not available" because both
    the mime and extension columns happened to be blank."""
    assert resolve_preview_type(_bare("115-health-qa.pdf")) == PreviewType.PDF


def test_the_extension_column_is_used_when_only_the_mime_is_missing() -> None:
    assert resolve_preview_type(_bare("notes.txt", ext="txt")) == PreviewType.TEXT


def test_the_name_wins_over_a_stale_extension_column_being_empty() -> None:
    assert resolve_preview_type(_bare("clip.mp4")) == PreviewType.VIDEO
    assert resolve_preview_type(_bare("shot.png")) == PreviewType.IMAGE


def test_an_unknown_extension_is_still_unsupported() -> None:
    assert resolve_preview_type(_bare("archive.xyz")) == PreviewType.UNSUPPORTED


def test_the_served_mime_is_filled_in_from_the_name() -> None:
    # Without this a recognised PDF still streams as octet-stream, which
    # browsers download rather than render.
    assert resolve_mime(_bare("115-health-qa.pdf")) == "application/pdf"
    assert resolve_mime(_bare("report.pdf", mime="application/pdf")) == "application/pdf"
    assert resolve_mime(_bare("mystery.bin")) is None

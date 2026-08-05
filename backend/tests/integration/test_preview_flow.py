"""Preview — doc/test-cases.md API-PREV-01~05.

Preview is this project's worst regression area, so the bar here is higher than
elsewhere: it is not enough for the endpoint to answer 200. Every case asserts
the *bytes and the content type actually served*, because the original PDF
incident (31c8b67) was declared fixed on the strength of an `<iframe>` existing
while preview still did not work.
"""

from __future__ import annotations

import io

import pytest
from httpx import AsyncClient

from tests.integration.conftest import auth_headers, register_and_login

pytestmark = pytest.mark.asyncio

_PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
# 1x1 transparent PNG.
_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05"
    b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


async def _upload(
    client: AsyncClient,
    headers: dict[str, str],
    name: str,
    data: bytes,
    content_type: str,
) -> str:
    resp = await client.post(
        "/api/v1/upload/simple",
        headers=headers,
        files={"file": (name, io.BytesIO(data), content_type)},
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


async def test_pdf_preview_actually_serves_the_pdf_bytes(client: AsyncClient) -> None:
    """API-PREV-01/02 — regression for 31c8b67.

    Asserts the three things the original fix was declared on without: the
    reported preview type, the served Content-Type, and a non-empty body that
    still starts with the PDF magic number.
    """
    h = auth_headers(await register_and_login(client, email="prev-pdf@test.com"))
    item_id = await _upload(client, h, "report.pdf", _PDF_BYTES, "application/pdf")

    info = await client.get(f"/api/v1/preview/{item_id}", headers=h)
    assert info.status_code == 200, info.text
    assert info.json()["preview_type"] == "pdf"
    assert info.json()["mime_type"] == "application/pdf"

    content = await client.get(f"/api/v1/preview/{item_id}/content", headers=h)
    assert content.status_code == 200, content.text
    assert content.headers["content-type"].startswith("application/pdf")
    assert content.content == _PDF_BYTES
    assert content.content.startswith(b"%PDF-")


async def test_image_preview_serves_the_original_bytes(client: AsyncClient) -> None:
    """API-PREV-02 — a truncated or re-encoded image renders as a broken image."""
    h = auth_headers(await register_and_login(client, email="prev-img@test.com"))
    item_id = await _upload(client, h, "dot.png", _PNG_BYTES, "image/png")

    info = await client.get(f"/api/v1/preview/{item_id}", headers=h)
    assert info.json()["preview_type"] == "image"

    content = await client.get(f"/api/v1/preview/{item_id}/content", headers=h)
    assert content.status_code == 200
    assert content.headers["content-type"].startswith("image/png")
    assert content.content == _PNG_BYTES


async def test_text_and_markdown_are_told_apart(client: AsyncClient) -> None:
    """API-PREV-01 — markdown must not be swallowed by the generic text/ branch."""
    h = auth_headers(await register_and_login(client, email="prev-text@test.com"))

    txt_id = await _upload(client, h, "notes.txt", b"plain words", "text/plain")
    md_id = await _upload(client, h, "readme.md", b"# Title", "text/markdown")

    txt = await client.get(f"/api/v1/preview/{txt_id}", headers=h)
    assert txt.json()["preview_type"] == "text"

    md = await client.get(f"/api/v1/preview/{md_id}", headers=h)
    assert md.json()["preview_type"] == "markdown"

    md_content = await client.get(f"/api/v1/preview/{md_id}/content", headers=h)
    assert md_content.status_code == 200
    assert md_content.content == b"# Title"


async def test_a_blank_mime_type_falls_back_to_the_extension(client: AsyncClient) -> None:
    """API-PREV-03 — regression for edd8314.

    `mime_type` is blank on a large share of real rows (browsers do not always
    send one; files written by skills never do). Such a file used to be reported
    as unsupported even when its extension said exactly what it was.
    """
    h = auth_headers(await register_and_login(client, email="prev-blank@test.com"))
    item_id = await _upload(client, h, "typeless.pdf", _PDF_BYTES, "")

    info = await client.get(f"/api/v1/preview/{item_id}", headers=h)
    assert info.status_code == 200, info.text
    assert info.json()["preview_type"] == "pdf", (
        "a blank mime_type must fall back to the extension, not be reported as unsupported"
    )

    content = await client.get(f"/api/v1/preview/{item_id}/content", headers=h)
    assert content.status_code == 200
    assert content.headers["content-type"].startswith("application/pdf")
    assert content.content == _PDF_BYTES


async def test_preview_and_download_agree_on_the_content_type(client: AsyncClient) -> None:
    """API-PREV-04 — regression for 31c8b67's second half.

    A PDF that renders on one endpoint but arrives as application/octet-stream
    on the other is exactly the bug `app.core.mime` was extracted to prevent,
    so the agreement is asserted for a file with *no* stored mime type.
    """
    h = auth_headers(await register_and_login(client, email="prev-agree@test.com"))
    item_id = await _upload(client, h, "agree.pdf", _PDF_BYTES, "")

    preview = await client.get(f"/api/v1/preview/{item_id}/content", headers=h)
    download = await client.get(f"/api/v1/download/{item_id}", headers=h)

    assert preview.status_code == 200
    assert download.status_code == 200
    assert (
        preview.headers["content-type"].split(";")[0]
        == (download.headers["content-type"].split(";")[0])
    )
    assert download.headers["content-type"].startswith("application/pdf")


async def test_an_unsupported_type_fails_loudly_rather_than_blankly(
    client: AsyncClient,
) -> None:
    """API-PREV-05 — the client needs a code to show "cannot preview, download instead"."""
    h = auth_headers(await register_and_login(client, email="prev-unsup@test.com"))
    item_id = await _upload(client, h, "archive.bin", b"\x00\x01\x02", "application/x-thing")

    info = await client.get(f"/api/v1/preview/{item_id}", headers=h)
    assert info.status_code == 200
    assert info.json()["preview_type"] == "unsupported"

    content = await client.get(f"/api/v1/preview/{item_id}/content", headers=h)
    assert content.status_code >= 400
    assert content.json()["error"]["code"] == "INVALID_OPERATION"


async def test_a_folder_cannot_be_previewed(client: AsyncClient) -> None:
    """API-PREV-01 — guards the item_type branch."""
    h = auth_headers(await register_and_login(client, email="prev-folder@test.com"))
    folder = await client.post("/api/v1/drive/folders", json={"name": "NotAFile"}, headers=h)

    resp = await client.get(f"/api/v1/preview/{folder.json()['id']}", headers=h)
    assert resp.status_code >= 400
    assert resp.json()["error"]["code"] == "INVALID_OPERATION"


async def test_another_users_file_cannot_be_previewed(client: AsyncClient) -> None:
    """API-PREV-05 (isolation) — proposal §24 acceptance 1."""
    owner = auth_headers(await register_and_login(client, email="prev-owner@test.com"))
    item_id = await _upload(client, owner, "secret.pdf", _PDF_BYTES, "application/pdf")

    intruder = auth_headers(
        await register_and_login(client, email="prev-intruder@test.com", username="intruder")
    )

    info = await client.get(f"/api/v1/preview/{item_id}", headers=intruder)
    assert info.status_code in (403, 404), info.text

    content = await client.get(f"/api/v1/preview/{item_id}/content", headers=intruder)
    assert content.status_code in (403, 404), content.text

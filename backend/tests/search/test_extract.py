from __future__ import annotations

import io

from app.search.extract import MAX_CHARS, extract_text


def test_extracts_plain_text_by_mime() -> None:
    text = extract_text(data=b"hello world", mime_type="text/plain", extension=None)
    assert text == "hello world"


def test_extracts_by_extension_when_mime_missing() -> None:
    text = extract_text(data=b"a,b,c\n1,2,3", mime_type=None, extension="csv")
    assert text is not None
    assert "a,b,c" in text


def test_unsupported_binary_returns_none() -> None:
    text = extract_text(data=b"\x89PNG\r\n\x1a\n", mime_type="image/png", extension="png")
    assert text is None


def test_too_large_returns_none() -> None:
    text = extract_text(data=b"x" * 100, mime_type="text/plain", extension="txt", max_bytes=10)
    assert text is None


def test_text_is_truncated_to_max_chars() -> None:
    text = extract_text(
        data=b"a" * (MAX_CHARS + 500), mime_type="text/plain", extension="txt", max_bytes=10**9
    )
    assert text is not None
    assert len(text) == MAX_CHARS


def test_blank_text_returns_none() -> None:
    assert extract_text(data=b"   \n  ", mime_type="text/plain", extension="txt") is None


def test_extracts_pdf_runs_on_valid_pdf_without_raising() -> None:
    from pypdf import PdfWriter

    # A blank page yields no text; we just assert extraction runs cleanly and
    # returns either text or None (never raises) on a structurally valid PDF.
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)

    result = extract_text(data=buf.getvalue(), mime_type="application/pdf", extension="pdf")
    assert result is None or isinstance(result, str)


def test_corrupt_pdf_returns_none_without_raising() -> None:
    result = extract_text(data=b"%PDF-1.4 garbage", mime_type="application/pdf", extension="pdf")
    assert result is None

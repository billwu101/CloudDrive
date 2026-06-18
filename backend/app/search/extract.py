"""Best-effort plain-text extraction for full-text search indexing.

Pure, dependency-light helpers: given a file's bytes + metadata, return text to
index, or None when the type isn't supported or the file is too large. Never
raises on bad input — a failed extraction just means "not indexable".
"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger("app.search.extract")

# Don't try to index very large files synchronously on the upload path.
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
# Cap stored text so one huge document can't bloat the index row.
MAX_CHARS = 200_000
# PDFs: stop after this many pages.
MAX_PDF_PAGES = 50

_TEXT_EXTENSIONS = {
    "txt",
    "md",
    "markdown",
    "csv",
    "tsv",
    "json",
    "log",
    "xml",
    "yaml",
    "yml",
    "html",
    "htm",
    "rst",
}


def _is_text_like(mime_type: str | None, extension: str | None) -> bool:
    if mime_type and (mime_type.startswith("text/") or mime_type in {"application/json"}):
        return True
    return bool(extension and extension.lower() in _TEXT_EXTENSIONS)


def _is_pdf(mime_type: str | None, extension: str | None) -> bool:
    return mime_type == "application/pdf" or (extension or "").lower() == "pdf"


def _clean(text: str) -> str:
    text = text.strip()
    return text[:MAX_CHARS] if len(text) > MAX_CHARS else text


def extract_text(
    *,
    data: bytes,
    mime_type: str | None,
    extension: str | None,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> str | None:
    """Return indexable text for this file, or None if unsupported/too large."""
    if len(data) > max_bytes:
        return None

    if _is_text_like(mime_type, extension):
        text = data.decode("utf-8", errors="ignore")
        cleaned = _clean(text)
        return cleaned or None

    if _is_pdf(mime_type, extension):
        return _extract_pdf(data)

    return None


def _extract_pdf(data: bytes) -> str | None:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        parts: list[str] = []
        for page in reader.pages[:MAX_PDF_PAGES]:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
        cleaned = _clean("\n".join(parts))
        return cleaned or None
    except Exception:
        logger.exception("PDF text extraction failed")
        return None

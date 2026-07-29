"""Working out a file's type when the stored columns don't say.

`mime_type` is blank on a large share of real rows — browsers don't always
send one on upload, and files written by skills never have one. `extension`
goes stale too: renaming a file rewrites `name` but leaves the column alone.
The name is what the user sees and what they renamed, so it is the last and
most trustworthy fallback.

Shared by preview and download rather than living in either: both serve the
same bytes to a browser, and a PDF that renders on one endpoint but downloads
as `application/octet-stream` on the other is the bug this exists to prevent.
"""

from __future__ import annotations

EXT_MIME = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "bmp": "image/bmp",
    "svg": "image/svg+xml",
    "txt": "text/plain",
    "log": "text/plain",
    "md": "text/markdown",
    "markdown": "text/markdown",
    "json": "application/json",
    "xml": "text/xml",
    "yaml": "text/yaml",
    "yml": "text/yaml",
    "csv": "text/csv",
    "mp4": "video/mp4",
    "webm": "video/webm",
    "mov": "video/quicktime",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "ogg": "audio/ogg",
    "m4a": "audio/mp4",
}


def effective_extension(*, name: str | None, extension: str | None) -> str | None:
    """The item's extension, falling back to the one in its name."""
    if extension:
        return extension
    _stem, dot, ext = (name or "").rpartition(".")
    return ext if dot and ext else None


def resolve_mime(*, mime_type: str | None, name: str | None, extension: str | None) -> str | None:
    """The MIME type to serve an item with, or None when it can't be told."""
    if mime_type:
        return mime_type
    ext = (effective_extension(name=name, extension=extension) or "").lower().lstrip(".")
    return EXT_MIME.get(ext)

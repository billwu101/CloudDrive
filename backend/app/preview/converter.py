"""Office/CSV → PDF conversion via headless LibreOffice, for document preview.

If no LibreOffice binary is on PATH, ``office_available()`` returns False and the
preview layer falls back to ``unsupported`` (the file is still downloadable).
"""

from __future__ import annotations

import asyncio
import logging
import pathlib
import shutil
import tempfile
from functools import lru_cache

logger = logging.getLogger("app.preview.converter")

_OFFICE_BIN_CANDIDATES = ("soffice", "libreoffice")
_CONVERT_TIMEOUT = 60.0


class ConversionError(Exception):
    """A document could not be converted to PDF (missing binary, timeout, error)."""


def _office_bin() -> str | None:
    for name in _OFFICE_BIN_CANDIDATES:
        path = shutil.which(name)
        if path:
            return path
    return None


@lru_cache(maxsize=1)
def office_available() -> bool:
    """True if LibreOffice is installed (enables Office→PDF document preview)."""
    return _office_bin() is not None


async def convert_to_pdf(data: bytes, *, suffix: str, timeout: float = _CONVERT_TIMEOUT) -> bytes:
    """Convert an Office/CSV document (given its file ``suffix``, e.g. ``.docx``)
    to PDF bytes via headless LibreOffice.

    Raises ``ConversionError`` if LibreOffice is missing, times out, or fails.
    """
    binary = _office_bin()
    if binary is None:
        raise ConversionError("LibreOffice not available")

    with tempfile.TemporaryDirectory(prefix="cd-preview-") as tmp:
        tmp_path = pathlib.Path(tmp)
        src = tmp_path / f"input{suffix}"
        src.write_bytes(data)
        # A per-call isolated user profile avoids lock contention between
        # concurrent conversions.
        proc = await asyncio.create_subprocess_exec(
            binary,
            "--headless",
            "--nologo",
            f"-env:UserInstallation=file://{tmp_path / 'profile'}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(tmp_path),
            str(src),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout)
        except TimeoutError as exc:
            proc.kill()
            raise ConversionError("conversion timed out") from exc

        out = src.with_suffix(".pdf")
        if proc.returncode != 0 or not out.exists():
            detail = stderr.decode("utf-8", "ignore")[:500]
            logger.warning("LibreOffice conversion failed (rc=%s): %s", proc.returncode, detail)
            raise ConversionError("conversion failed")
        return out.read_bytes()

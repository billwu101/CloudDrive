from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import IO


class PathTraversalError(ValueError):
    pass


class StorageKeyNotFoundError(FileNotFoundError):
    pass


class LocalStorageProvider:
    """Local-filesystem storage backend using atomic temp-then-rename writes."""

    _CHUNK_SIZE = 65536

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    def _resolve_path(self, key: str) -> Path:
        if not key or ".." in key.split("/") or key.startswith("/"):
            raise PathTraversalError(f"Invalid storage key: {key!r}")
        normalized = key.strip("/")
        candidate = (self._root / normalized).resolve()
        try:
            candidate.relative_to(self._root)
        except ValueError as exc:
            raise PathTraversalError(f"Invalid storage key: {key!r}") from exc
        return candidate

    async def save(self, key: str, data: IO[bytes], *, size: int | None = None) -> None:
        path = self._resolve_path(key)

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_str = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
            tmp = Path(tmp_str)
            try:
                with os.fdopen(fd, "wb") as f:
                    shutil.copyfileobj(data, f)
                tmp.replace(path)
            except Exception:
                with contextlib.suppress(OSError):
                    tmp.unlink()
                raise

        await asyncio.to_thread(_write)

    async def open_read(self, key: str) -> AsyncGenerator[bytes, None]:
        path = self._resolve_path(key)

        def _read_chunks() -> list[bytes]:
            if not path.exists():
                raise StorageKeyNotFoundError(key)
            chunks: list[bytes] = []
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(self._CHUNK_SIZE)
                    if not chunk:
                        break
                    chunks.append(chunk)
            return chunks

        chunks = await asyncio.to_thread(_read_chunks)
        for chunk in chunks:
            yield chunk

    async def delete(self, key: str) -> None:
        path = self._resolve_path(key)

        def _delete() -> None:
            with contextlib.suppress(FileNotFoundError):
                path.unlink()
            _cleanup_empty_parents(path.parent, self._root)

        await asyncio.to_thread(_delete)

    async def exists(self, key: str) -> bool:
        path = self._resolve_path(key)
        return await asyncio.to_thread(path.exists)

    async def get_size(self, key: str) -> int:
        path = self._resolve_path(key)

        def _size() -> int:
            if not path.exists():
                raise StorageKeyNotFoundError(key)
            return path.stat().st_size

        return await asyncio.to_thread(_size)


def _cleanup_empty_parents(directory: Path, stop_at: Path) -> None:
    """Remove empty directories up to (but not including) stop_at."""
    current = directory
    while current != stop_at and current.is_relative_to(stop_at):
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent

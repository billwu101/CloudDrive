from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import tempfile
from collections.abc import AsyncGenerator, AsyncIterator
from pathlib import Path
from typing import IO

from app.storage.base import UPLOAD_TEMP_PREFIX, StoredObject


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

    async def save_stream(self, key: str, chunks: AsyncIterator[bytes]) -> int:
        """Write an async byte stream straight to disk, chunk by chunk.

        Peak memory is one chunk, not the whole file — this is what large
        uploads must use instead of buffering into bytes and calling `save`.
        """
        path = self._resolve_path(key)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        fd, tmp_str = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        tmp = Path(tmp_str)
        written = 0
        try:
            with os.fdopen(fd, "wb") as f:
                async for chunk in chunks:
                    if not chunk:
                        continue
                    await asyncio.to_thread(f.write, chunk)
                    written += len(chunk)
            await asyncio.to_thread(tmp.replace, path)
        except BaseException:
            with contextlib.suppress(OSError):
                tmp.unlink()
            raise
        return written

    async def concat(self, source_keys: list[str], target_key: str) -> int:
        """Join source objects, in order, into one object at target_key.

        Copies through a fixed-size buffer, so assembling a 5 GB upload out of
        its chunks costs one buffer of memory rather than the whole file.
        """
        target = self._resolve_path(target_key)
        sources = [self._resolve_path(key) for key in source_keys]

        def _join() -> int:
            for source, key in zip(sources, source_keys, strict=True):
                if not source.exists():
                    raise StorageKeyNotFoundError(key)
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_str = tempfile.mkstemp(dir=target.parent, prefix=".tmp-")
            tmp = Path(tmp_str)
            written = 0
            try:
                with os.fdopen(fd, "wb") as out:
                    for source in sources:
                        with open(source, "rb") as src:
                            while True:
                                buf = src.read(self._CHUNK_SIZE)
                                if not buf:
                                    break
                                out.write(buf)
                                written += len(buf)
                tmp.replace(target)
            except BaseException:
                with contextlib.suppress(OSError):
                    tmp.unlink()
                raise
            return written

        return await asyncio.to_thread(_join)

    async def open_read(self, key: str) -> AsyncGenerator[bytes, None]:
        """Yield the object's bytes one buffer at a time.

        Reads lazily: the file is never held in memory in full, so streaming a
        multi-GB download or checksumming a merged upload costs one buffer.
        """
        path = self._resolve_path(key)
        if not await asyncio.to_thread(path.exists):
            raise StorageKeyNotFoundError(key)

        handle = await asyncio.to_thread(open, path, "rb")
        try:
            while True:
                chunk = await asyncio.to_thread(handle.read, self._CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk
        finally:
            await asyncio.to_thread(handle.close)

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

    async def list_objects(self) -> list[StoredObject]:
        def _walk() -> list[StoredObject]:
            objects: list[StoredObject] = []
            for path in self._root.rglob("*"):
                if not path.is_file():
                    continue
                # Skip in-flight atomic-write temp files (".tmp-*").
                if path.name.startswith(".tmp-"):
                    continue
                # Skip chunks of in-flight uploads. They are deliberately not
                # referenced by any drive_item yet, so content GC would read
                # them as orphans and delete a paused upload out from under
                # the user. The upload cleanup job owns this prefix instead.
                if path.relative_to(self._root).as_posix().startswith(f"{UPLOAD_TEMP_PREFIX}/"):
                    continue
                stat = path.stat()
                key = path.relative_to(self._root).as_posix()
                objects.append(StoredObject(key=key, size=stat.st_size, modified_at=stat.st_mtime))
            return objects

        return await asyncio.to_thread(_walk)


def _cleanup_empty_parents(directory: Path, stop_at: Path) -> None:
    """Remove empty directories up to (but not including) stop_at."""
    current = directory
    while current != stop_at and current.is_relative_to(stop_at):
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent

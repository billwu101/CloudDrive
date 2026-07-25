from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass
from typing import IO, Protocol, runtime_checkable

# Storage prefix owned by in-flight chunked uploads. Blobs under it belong to
# an upload session, not to a drive item, and are reclaimed by the upload
# cleanup job rather than by content GC.
UPLOAD_TEMP_PREFIX = "uploads"


@dataclass(frozen=True)
class StoredObject:
    """A blob present in the backend, as seen by a storage sweep."""

    key: str
    size: int
    # Last-modified time as a Unix epoch (seconds). Used by GC's grace period.
    modified_at: float


@runtime_checkable
class StorageProvider(Protocol):
    """Protocol for pluggable binary storage backends."""

    async def save(self, key: str, data: IO[bytes], *, size: int | None = None) -> None:
        """Persist data under the given key atomically."""
        ...

    async def save_stream(self, key: str, chunks: AsyncIterator[bytes]) -> int:
        """Persist an async byte stream under the given key atomically.

        Writes chunk by chunk so peak memory stays constant regardless of file
        size — callers must prefer this over buffering the whole upload and
        calling `save`. Returns the number of bytes written.
        """
        ...

    async def concat(self, source_keys: list[str], target_key: str) -> int:
        """Join the given objects, in order, into a single object at target_key.

        Used to assemble a chunked upload. Copies through a fixed-size buffer
        so memory stays constant regardless of total size. Returns the number
        of bytes written.
        """
        ...

    def open_read(self, key: str) -> AsyncGenerator[bytes, None]:
        """Return an async generator that yields file chunks."""
        ...

    async def delete(self, key: str) -> None:
        """Delete the object at key. No-op if it does not exist."""
        ...

    async def exists(self, key: str) -> bool:
        """Return True if the key exists in storage."""
        ...

    async def get_size(self, key: str) -> int:
        """Return the size in bytes of the stored object."""
        ...

    async def list_objects(self) -> list[StoredObject]:
        """Enumerate every stored blob (for content GC). Excludes temp files."""
        ...

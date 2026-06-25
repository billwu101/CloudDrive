from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import IO, Protocol, runtime_checkable


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

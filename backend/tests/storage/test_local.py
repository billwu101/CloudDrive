from __future__ import annotations

import io
from pathlib import Path

import pytest

from app.storage.local import LocalStorageProvider, PathTraversalError, StorageKeyNotFoundError


@pytest.fixture()
def storage(tmp_path: Path) -> LocalStorageProvider:
    return LocalStorageProvider(root=tmp_path)


async def _collect(provider: LocalStorageProvider, key: str) -> bytes:
    chunks: list[bytes] = []
    async for chunk in provider.open_read(key):
        chunks.append(chunk)
    return b"".join(chunks)


class TestSave:
    async def test_save_creates_file(self, storage: LocalStorageProvider, tmp_path: Path) -> None:
        data = b"hello world"
        await storage.save("myfile.txt", io.BytesIO(data))
        assert (tmp_path / "myfile.txt").exists()

    async def test_save_with_subdirectory(
        self, storage: LocalStorageProvider, tmp_path: Path
    ) -> None:
        data = b"nested content"
        await storage.save("a/b/file.bin", io.BytesIO(data))
        assert (tmp_path / "a" / "b" / "file.bin").exists()

    async def test_save_overwrite(self, storage: LocalStorageProvider) -> None:
        await storage.save("file.txt", io.BytesIO(b"v1"))
        await storage.save("file.txt", io.BytesIO(b"version two"))
        content = await _collect(storage, "file.txt")
        assert content == b"version two"


class TestReadBack:
    async def test_read_matches_saved(self, storage: LocalStorageProvider) -> None:
        original = b"binary\x00content\xff"
        await storage.save("data.bin", io.BytesIO(original))
        result = await _collect(storage, "data.bin")
        assert result == original

    async def test_read_nonexistent_raises(self, storage: LocalStorageProvider) -> None:
        with pytest.raises(StorageKeyNotFoundError):
            async for _ in storage.open_read("missing.txt"):
                pass


class TestGetSize:
    async def test_get_size_correct(self, storage: LocalStorageProvider) -> None:
        data = b"hello"
        await storage.save("sz.txt", io.BytesIO(data))
        assert await storage.get_size("sz.txt") == len(data)

    async def test_get_size_nonexistent_raises(self, storage: LocalStorageProvider) -> None:
        with pytest.raises(StorageKeyNotFoundError):
            await storage.get_size("nope.bin")


class TestExists:
    async def test_exists_true_after_save(self, storage: LocalStorageProvider) -> None:
        await storage.save("present.txt", io.BytesIO(b"x"))
        assert await storage.exists("present.txt") is True

    async def test_exists_false_before_save(self, storage: LocalStorageProvider) -> None:
        assert await storage.exists("absent.txt") is False


class TestDelete:
    async def test_delete_removes_file(self, storage: LocalStorageProvider, tmp_path: Path) -> None:
        await storage.save("todelete.txt", io.BytesIO(b"data"))
        await storage.delete("todelete.txt")
        assert not (tmp_path / "todelete.txt").exists()

    async def test_delete_nonexistent_is_noop(self, storage: LocalStorageProvider) -> None:
        await storage.delete("ghost.txt")  # must not raise

    async def test_delete_cleans_empty_parent(
        self, storage: LocalStorageProvider, tmp_path: Path
    ) -> None:
        await storage.save("sub/dir/file.bin", io.BytesIO(b"data"))
        await storage.delete("sub/dir/file.bin")
        assert not (tmp_path / "sub" / "dir").exists()
        assert not (tmp_path / "sub").exists()


class TestPathTraversal:
    async def test_dotdot_in_key_rejected(self, storage: LocalStorageProvider) -> None:
        with pytest.raises(PathTraversalError):
            await storage.save("../escape.txt", io.BytesIO(b"bad"))

    async def test_absolute_key_rejected(self, storage: LocalStorageProvider) -> None:
        with pytest.raises(PathTraversalError):
            await storage.save("/etc/passwd", io.BytesIO(b"bad"))

    async def test_dotdot_component_rejected(self, storage: LocalStorageProvider) -> None:
        with pytest.raises(PathTraversalError):
            await storage.save("a/../../../etc/passwd", io.BytesIO(b"bad"))

    async def test_normal_subdirectory_allowed(self, storage: LocalStorageProvider) -> None:
        await storage.save("user/123/file.txt", io.BytesIO(b"ok"))
        assert await storage.exists("user/123/file.txt")


class TestAtomicWrite:
    async def test_no_partial_file_on_failure(
        self, storage: LocalStorageProvider, tmp_path: Path
    ) -> None:
        """A stream that raises mid-read must not leave a final file."""
        dest = tmp_path / "partial.txt"

        class _BadStream(io.RawIOBase):
            def readinto(self, b: bytearray | memoryview) -> int:  # type: ignore[override]
                raise OSError("simulated write failure")

        with pytest.raises(OSError):
            await storage.save("partial.txt", io.BufferedReader(_BadStream()))

        assert not dest.exists()

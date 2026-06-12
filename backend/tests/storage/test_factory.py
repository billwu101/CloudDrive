from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.storage.base import StorageProvider
from app.storage.factory import get_storage_provider
from app.storage.local import LocalStorageProvider


def _settings(driver: str = "local", path: str = "/tmp/test-store") -> MagicMock:
    s = MagicMock()
    s.storage_driver = driver
    s.local_storage_path = path
    return s


def test_local_driver_returns_local_provider(tmp_path: Path) -> None:
    provider = get_storage_provider(_settings(driver="local", path=str(tmp_path)))
    assert isinstance(provider, LocalStorageProvider)


def test_local_provider_satisfies_protocol(tmp_path: Path) -> None:
    provider = get_storage_provider(_settings(driver="local", path=str(tmp_path)))
    assert isinstance(provider, StorageProvider)


def test_unknown_driver_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported storage driver"):
        get_storage_provider(_settings(driver="s3"))

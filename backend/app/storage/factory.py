from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.storage.base import StorageProvider
from app.storage.local import LocalStorageProvider


def get_storage_provider(settings: Annotated[Settings, Depends(get_settings)]) -> StorageProvider:
    """Return the configured StorageProvider.

    Currently only "local" is implemented.
    MinIO/S3 provider can be added here when STORAGE_DRIVER is extended.
    """
    if settings.storage_driver == "local":
        return LocalStorageProvider(root=settings.local_storage_path)
    raise ValueError(f"Unsupported storage driver: {settings.storage_driver!r}")


StorageProviderDep = Annotated[StorageProvider, Depends(get_storage_provider)]

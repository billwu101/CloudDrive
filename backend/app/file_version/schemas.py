from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FileVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_id: UUID
    version_no: int
    size_bytes: int
    checksum_sha256: str | None
    created_by: UUID
    created_at: datetime

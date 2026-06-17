from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateSnapshotRequest(BaseModel):
    label: str = Field(default="", max_length=200)


class SnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    trigger: str
    label: str
    item_count: int
    total_bytes: int
    pinned: bool
    created_at: datetime


class SnapshotEntryResponse(BaseModel):
    """One item as it existed in a snapshot — shaped for a read-only browser."""

    model_config = ConfigDict(from_attributes=True)

    item_id: UUID
    parent_item_id: UUID | None
    name: str
    item_type: str
    size_bytes: int
    checksum_sha256: str | None

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateSnapshotRequest(BaseModel):
    label: str = Field(default="", max_length=200)


class RestoreRequest(BaseModel):
    # "whole" restores the entire snapshot; "items" restores the listed items
    # (folders bring their snapshot descendants).
    scope: Literal["whole", "items"] = "whole"
    item_ids: list[UUID] = Field(default_factory=list)
    # keep_new: leave items added since the snapshot; exact_mirror: trash them.
    subtree_mode: Literal["keep_new", "exact_mirror"] = "keep_new"


class RestoreResponse(BaseModel):
    pre_restore_snapshot_id: UUID
    restored: int
    trashed: int


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

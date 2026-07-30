from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.permission.permissions import Permission
from app.schemas.common import DriveItemResponse


class ShareRequest(BaseModel):
    target_email: str
    permission: Permission


class ShareResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    item_id: UUID
    owner_id: UUID
    target_user_id: UUID
    permission: str
    created_at: datetime
    updated_at: datetime


class UpdateShareRequest(BaseModel):
    permission: Permission


class ShareLinkRequest(BaseModel):
    permission: Permission
    password: str | None = None
    expires_at: datetime | None = None


class SharedByMeUserShare(BaseModel):
    """One person this item is shared with."""

    target_user_id: UUID
    email: str
    username: str | None
    permission: str
    created_at: datetime


class SharedByMeLink(BaseModel):
    """One public link pointing at this item."""

    link_id: UUID
    permission: str
    has_password: bool  # a boolean only — the hash never leaves the server
    expires_at: datetime | None
    is_active: bool  # False once disabled *or* expired
    created_at: datetime


class SharedByMeEntry(BaseModel):
    """Everything the owner has shared for one item.

    One entry per item rather than per share record (proposal §29.5 decision 1):
    an item shared with three people and one link is still a single row that
    expands, not four rows.
    """

    item: DriveItemResponse
    user_shares: list[SharedByMeUserShare]
    links: list[SharedByMeLink]


class ShareLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    item_id: UUID
    token: str | None = None  # only present on creation; None when retrieved by hash
    permission: str
    expires_at: datetime | None
    is_active: bool
    created_by: UUID
    created_at: datetime

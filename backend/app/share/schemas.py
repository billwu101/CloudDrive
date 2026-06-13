from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.permission.permissions import Permission


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

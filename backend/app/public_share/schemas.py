from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.drive.schemas import ItemType
from app.preview.service import PreviewType


class PublicSessionRequest(BaseModel):
    """Body of ``POST /public/links/{token}/session``.

    The password travels in the body — never the URL or query string — so it
    cannot end up in access logs, browser history or a forwarded link
    (design §6.12.11 rule 3).
    """

    password: str | None = None


class PublicItemResponse(BaseModel):
    """Item metadata a guest is allowed to see.

    Deliberately narrower than ``DriveItemResponse``: no owner id, no starred
    state, no trash flags — none of that is the guest's business.
    """

    id: UUID
    name: str
    item_type: ItemType
    mime_type: str | None
    size_bytes: int
    extension: str | None
    preview_type: PreviewType
    updated_at: datetime


class PublicSessionResponse(BaseModel):
    access_token: str
    expires_in: int  # seconds
    permission: str
    item: PublicItemResponse

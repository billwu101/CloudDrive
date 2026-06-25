from __future__ import annotations

import math
from datetime import datetime
from enum import StrEnum
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class ErrorDetail(BaseModel):
    field: str | None = None
    message: str


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)


class Page(BaseModel, Generic[T]):  # noqa: UP046
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        *,
        page: int,
        page_size: int,
    ) -> Page[T]:
        pages = math.ceil(total / page_size) if page_size > 0 else 0
        return cls(items=items, total=total, page=page, page_size=page_size, pages=pages)


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    username: str
    avatar_url: str | None
    quota_bytes: int
    used_bytes: int
    is_active: bool
    is_admin: bool
    must_change_password: bool = False
    created_at: datetime


class TokenPairResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DriveItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    parent_id: UUID | None
    item_type: str
    name: str
    mime_type: str | None
    extension: str | None
    size_bytes: int
    is_starred: bool
    is_deleted: bool
    deleted_at: datetime | None
    created_by: UUID
    updated_by: UUID | None
    created_at: datetime
    updated_at: datetime

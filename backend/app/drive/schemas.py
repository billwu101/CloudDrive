from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class ItemType(StrEnum):
    FILE = "file"
    FOLDER = "folder"


class DriveItemSortField(StrEnum):
    NAME = "name"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    SIZE_BYTES = "size_bytes"


class CreateFolderRequest(BaseModel):
    name: str = Field(min_length=1, max_length=512)
    parent_id: UUID | None = None


class RenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=512)


class MoveRequest(BaseModel):
    parent_id: UUID | None


class StarRequest(BaseModel):
    is_starred: bool

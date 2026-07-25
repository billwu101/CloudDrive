from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateUploadSessionRequest(BaseModel):
    """Client's declaration of what it is about to upload."""

    filename: str = Field(min_length=1, max_length=512)
    total_size: int = Field(ge=0)
    parent_id: UUID | None = None
    mime_type: str | None = Field(default=None, max_length=255)


class UploadSessionResponse(BaseModel):
    """Everything the client needs to slice the file and resume later."""

    id: UUID
    filename: str
    total_size: int
    chunk_size: int
    total_chunks: int
    status: str
    # Indexes already stored: on resume the client sends only what is missing.
    uploaded_chunks: list[int]
    expires_at: datetime

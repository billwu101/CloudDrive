from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FileSearchIndex(Base):
    """Extracted plain-text content of a file, for full-text search. One row per
    file (``item_id``); rows cascade-delete with their drive item."""

    __tablename__ = "file_search_index"

    item_id: Mapped[UUID] = mapped_column(
        ForeignKey("drive_items.id", ondelete="CASCADE"), primary_key=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

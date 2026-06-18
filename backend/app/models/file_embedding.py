from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# Vector width is fixed in the schema, so it must match the embedding model's
# output dimension (and Settings.embedding_dim). Default: nomic-embed-text = 768.
EMBEDDING_DIM = 768


class FileEmbedding(Base):
    """Semantic embedding of a file's extracted text, for vector search. One row
    per file; cascades with the drive item."""

    __tablename__ = "file_embeddings"

    item_id: Mapped[UUID] = mapped_column(
        ForeignKey("drive_items.id", ondelete="CASCADE"), primary_key=True
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

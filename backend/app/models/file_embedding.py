from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# Vector width is fixed in the schema, so it must match the embedding model's
# output dimension (and Settings.embedding_dim). Default: nomic-embed-text = 768.
EMBEDDING_DIM = 768


class FileEmbedding(Base):
    """One semantic embedding of a chunk of a file's extracted text. A file has
    one row per chunk (long files are split); rows cascade with the drive item."""

    __tablename__ = "file_embeddings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    item_id: Mapped[UUID] = mapped_column(
        ForeignKey("drive_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Preview text of this chunk, shown as the search-result snippet.
    snippet: Mapped[str] = mapped_column(Text, nullable=False, default="")
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

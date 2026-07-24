from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UploadSession(Base):
    """A resumable chunked upload in progress (detailed-design §7.7).

    The session lives in the database while its chunks live in storage, so an
    upload survives the browser being closed.
    """

    __tablename__ = "upload_sessions"
    # Declared here as well as in the migration so metadata-built schemas (the
    # integration test DB) match production.
    __table_args__ = (
        Index("idx_upload_sessions_user_status", "user_id", "status", text("created_at DESC")),
        Index(
            "idx_upload_sessions_expires",
            "expires_at",
            postgresql_where=text("status IN ('pending', 'uploading')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    # Target folder; NULL means the drive root.
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("drive_items.id"), nullable=True)
    # The name the client asked for. Same-folder deduplication happens at
    # completion, so this is display-only until then.
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Client-declared size, used to pre-check the quota and the size limit.
    total_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False)
    # pending | uploading | completed | failed | cancelled
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    drive_item_id: Mapped[UUID | None] = mapped_column(ForeignKey("drive_items.id"), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # created_at + retention window; the cleanup job reclaims anything past it.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UploadChunk(Base):
    """One stored chunk of an upload session. Re-sending an index overwrites."""

    __tablename__ = "upload_chunks"
    # The upsert in SQLUploadSessionRepository.upsert_chunk targets this index
    # via ON CONFLICT, so it must exist wherever the schema is built — not
    # only in the migration.
    __table_args__ = (
        Index("uq_upload_chunks_session_index", "session_id", "chunk_index", unique=True),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("upload_sessions.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

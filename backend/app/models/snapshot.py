from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Snapshot(Base):
    """A point-in-time capture of a user's whole drive (Time Machine)."""

    __tablename__ = "snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # scheduled | manual | assistant | pre_restore
    trigger: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False, default="")
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SnapshotEntry(Base):
    """One file/folder as it existed in a snapshot. ``item_id`` is the original
    drive_items.id but is NOT a foreign key — entries must survive item deletion
    so the snapshot can restore items that were later removed."""

    __tablename__ = "snapshot_entries"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("snapshots.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[UUID] = mapped_column(nullable=False)
    parent_item_id: Mapped[UUID | None] = mapped_column(nullable=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    item_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Content pointer for files (content-addressed; folders leave these null).
    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

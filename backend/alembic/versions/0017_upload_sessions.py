"""upload_sessions and upload_chunks (chunked resumable upload)

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-24

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "upload_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("parent_id", sa.Uuid(), sa.ForeignKey("drive_items.id"), nullable=True),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(255), nullable=True),
        sa.Column("total_size", sa.BigInteger(), nullable=False),
        sa.Column("chunk_size", sa.Integer(), nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("drive_item_id", sa.Uuid(), sa.ForeignKey("drive_items.id"), nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    # Resume lookups and per-user session listing.
    op.create_index(
        "idx_upload_sessions_user_status",
        "upload_sessions",
        ["user_id", "status", sa.text("created_at DESC")],
    )
    # Expiry sweep only ever scans sessions that are still in flight.
    op.create_index(
        "idx_upload_sessions_expires",
        "upload_sessions",
        ["expires_at"],
        postgresql_where=sa.text("status IN ('pending', 'uploading')"),
    )

    op.create_table(
        "upload_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("upload_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    # One row per chunk: re-sending an index is an idempotent overwrite.
    op.create_index(
        "uq_upload_chunks_session_index",
        "upload_chunks",
        ["session_id", "chunk_index"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_upload_chunks_session_index", table_name="upload_chunks")
    op.drop_table("upload_chunks")
    op.drop_index("idx_upload_sessions_expires", table_name="upload_sessions")
    op.drop_index("idx_upload_sessions_user_status", table_name="upload_sessions")
    op.drop_table("upload_sessions")

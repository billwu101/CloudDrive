"""add snapshots and snapshot_entries (Time Machine)

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trigger", sa.String(50), nullable=False),
        sa.Column("label", sa.Text(), nullable=False, server_default=""),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_snapshots_user_created", "snapshots", ["user_id", "created_at"])

    op.create_table(
        "snapshot_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("parent_item_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("item_type", sa.String(50), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_snapshot_entries_snapshot_parent",
        "snapshot_entries",
        ["snapshot_id", "parent_item_id"],
    )
    op.create_index("ix_snapshot_entries_checksum", "snapshot_entries", ["checksum_sha256"])


def downgrade() -> None:
    op.drop_index("ix_snapshot_entries_checksum", table_name="snapshot_entries")
    op.drop_index("ix_snapshot_entries_snapshot_parent", table_name="snapshot_entries")
    op.drop_table("snapshot_entries")
    op.drop_index("ix_snapshots_user_created", table_name="snapshots")
    op.drop_table("snapshots")

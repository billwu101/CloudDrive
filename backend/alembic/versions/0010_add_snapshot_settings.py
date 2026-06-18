"""add snapshot_settings (Time Machine retention/schedule/quota)

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "snapshot_settings",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("retention_n", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("schedule_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "schedule_interval_minutes", sa.Integer(), nullable=False, server_default="60"
        ),
        sa.Column("quota_bytes", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("snapshot_settings")

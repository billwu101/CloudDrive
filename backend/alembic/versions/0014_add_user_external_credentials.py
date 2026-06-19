"""add user_external_credentials (external model per-user credentials, DEC-026)

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-19

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_external_credentials",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("provider", sa.String(length=20), primary_key=True),
        sa.Column("auth_type", sa.String(length=20), nullable=False),
        sa.Column("secret_encrypted", sa.Text(), nullable=False),
        sa.Column("masked_hint", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("user_external_credentials")

"""replace user_external_credentials with external_model_connections (multi named connections)

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-25

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Test-data only; per decision we rebuild rather than migrate old rows.
    op.drop_table("user_external_credentials")
    op.create_table(
        "external_model_connections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False, server_default=""),
        sa.Column("model", sa.String(200), nullable=False, server_default=""),
        sa.Column("secret_encrypted", sa.Text(), nullable=False),
        sa.Column("masked_hint", sa.String(64), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_external_model_connections_user_id",
        "external_model_connections",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_external_model_connections_user_id", table_name="external_model_connections")
    op.drop_table("external_model_connections")
    op.create_table(
        "user_external_credentials",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("provider", sa.String(20), primary_key=True),
        sa.Column("auth_type", sa.String(20), nullable=False),
        sa.Column("secret_encrypted", sa.Text(), nullable=False),
        sa.Column("masked_hint", sa.String(64), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

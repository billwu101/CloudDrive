"""fix activity_log ip_address from INET to VARCHAR(45)

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-13

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "activity_logs",
        "ip_address",
        type_=sa.String(45),
        existing_nullable=True,
        postgresql_using="ip_address::text",
    )


def downgrade() -> None:
    from sqlalchemy.dialects import postgresql
    op.alter_column(
        "activity_logs",
        "ip_address",
        type_=postgresql.INET(),
        existing_nullable=True,
        postgresql_using="ip_address::inet",
    )

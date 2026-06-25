"""add name column to assistant_workflows (saved workflows)

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-17

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assistant_workflows",
        sa.Column("name", sa.String(200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("assistant_workflows", "name")

"""add chat_enabled to assistant_skills (allow self-built skills in chat planner)

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-25

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assistant_skills",
        sa.Column(
            "chat_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("assistant_skills", "chat_enabled")

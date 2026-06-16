"""add assistant skills

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-17

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_skills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("manifest", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", "name", name="uq_assistant_skills_user_name"),
    )
    op.create_index(
        "idx_assistant_skills_user_status",
        "assistant_skills",
        ["user_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("idx_assistant_skills_user_status", table_name="assistant_skills")
    op.drop_table("assistant_skills")

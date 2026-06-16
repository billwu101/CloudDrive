"""add assistant workflows and runs

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-17

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_workflows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_nl", sa.Text(), nullable=False),
        sa.Column("steps", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
    )
    op.create_index(
        "idx_assistant_workflows_user_status",
        "assistant_workflows",
        ["user_id", "status"],
    )
    op.create_table(
        "assistant_workflow_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assistant_workflows.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_nl", sa.Text(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("step_results", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_assistant_workflow_runs_user",
        "assistant_workflow_runs",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_assistant_workflow_runs_user", table_name="assistant_workflow_runs")
    op.drop_table("assistant_workflow_runs")
    op.drop_index("idx_assistant_workflows_user_status", table_name="assistant_workflows")
    op.drop_table("assistant_workflows")

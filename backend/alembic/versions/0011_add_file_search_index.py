"""add file_search_index (full-text content search)

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "file_search_index",
        sa.Column(
            "item_id",
            sa.Uuid(),
            sa.ForeignKey("drive_items.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # GIN index over the English full-text vector for ranked keyword search.
    op.execute(
        "CREATE INDEX ix_file_search_index_tsv ON file_search_index "
        "USING gin (to_tsvector('english', content))"
    )


def downgrade() -> None:
    op.drop_index("ix_file_search_index_tsv", table_name="file_search_index")
    op.drop_table("file_search_index")

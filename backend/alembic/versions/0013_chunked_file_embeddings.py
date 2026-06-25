"""chunked file_embeddings (multi-vector per file + snippet)

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-18

Replaces the one-row-per-file embedding table with one-row-per-chunk, adding a
snippet column for result previews. Embeddings are derived data, so the old
table is simply dropped and recreated (re-populate via the backfill endpoint).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

_DIM = 768


def upgrade() -> None:
    op.drop_index("ix_file_embeddings_vec", table_name="file_embeddings")
    op.drop_table("file_embeddings")

    op.create_table(
        "file_embeddings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "item_id",
            sa.Uuid(),
            sa.ForeignKey("drive_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("snippet", sa.Text(), nullable=False, server_default=""),
        sa.Column("embedding", Vector(_DIM), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False, server_default=""),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_file_embeddings_item", "file_embeddings", ["item_id"])
    op.execute(
        "CREATE INDEX ix_file_embeddings_vec ON file_embeddings "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_index("ix_file_embeddings_vec", table_name="file_embeddings")
    op.drop_index("ix_file_embeddings_item", table_name="file_embeddings")
    op.drop_table("file_embeddings")

    op.create_table(
        "file_embeddings",
        sa.Column(
            "item_id",
            sa.Uuid(),
            sa.ForeignKey("drive_items.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("embedding", Vector(_DIM), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False, server_default=""),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.execute(
        "CREATE INDEX ix_file_embeddings_vec ON file_embeddings "
        "USING hnsw (embedding vector_cosine_ops)"
    )

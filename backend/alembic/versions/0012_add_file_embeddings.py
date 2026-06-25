"""add file_embeddings (semantic search via pgvector)

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-18

Requires a Postgres image with the pgvector extension available
(e.g. pgvector/pgvector:pg16). The vector width must match
app.models.file_embedding.EMBEDDING_DIM and Settings.embedding_dim.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

_DIM = 768


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
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
    # Approximate-NN index for cosine distance (<=>).
    op.execute(
        "CREATE INDEX ix_file_embeddings_vec ON file_embeddings "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_index("ix_file_embeddings_vec", table_name="file_embeddings")
    op.drop_table("file_embeddings")

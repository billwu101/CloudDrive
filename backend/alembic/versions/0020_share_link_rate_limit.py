"""Attempt throttling columns for public share links

Public share links are the only unauthenticated entry point (proposal §28), so
validation attempts must be rate limited. The counter lives on the row instead
of in process memory: with several uvicorn workers an in-process counter would
let the effective limit scale with the worker count.

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-26

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "share_links",
        sa.Column("attempt_window_start", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "share_links",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "share_links",
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("share_links", "locked_until")
    op.drop_column("share_links", "attempt_count")
    op.drop_column("share_links", "attempt_window_start")

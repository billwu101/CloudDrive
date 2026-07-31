"""Keep a recoverable copy of the share link token

The owner could never be shown a link's URL again, because only its hash was
stored (proposal §29.2.1). This adds a Fernet ciphertext alongside the hash:
the hash remains the lookup key, the ciphertext exists solely so "copy link"
can work after the fact.

Nullable on purpose — links created before this column have no recoverable
value, and pretending otherwise would mean inventing one.

Revision ID: 0022
Revises: 0021
Create Date: 2026-07-31

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("share_links", sa.Column("token_encrypted", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("share_links", "token_encrypted")

"""Allow 'editor' on public share links

Guest write access (proposal §33): a link may now grant the same abilities a
signed-in editor has, bounded by the shared subtree. The check constraint is
the only thing standing in the way — everything else is application logic.

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-29

"""

from __future__ import annotations

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

_NAME = "ck_share_links_permission"


def upgrade() -> None:
    op.drop_constraint(_NAME, "share_links", type_="check")
    op.create_check_constraint(
        _NAME, "share_links", "permission IN ('viewer', 'downloader', 'editor')"
    )


def downgrade() -> None:
    # Editor links would violate the narrower constraint, so retire them first
    # rather than failing the migration on real data.
    op.execute("UPDATE share_links SET is_active = false WHERE permission = 'editor'")
    op.execute("DELETE FROM share_links WHERE permission = 'editor'")
    op.drop_constraint(_NAME, "share_links", type_="check")
    op.create_check_constraint(_NAME, "share_links", "permission IN ('viewer', 'downloader')")

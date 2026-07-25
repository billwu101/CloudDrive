"""ON DELETE SET NULL for upload_sessions FKs to drive_items

The last blocker for emptying trash: a completed chunked upload leaves an
upload_sessions row whose drive_item_id (and parent_id) reference drive_items
with no ON DELETE rule, so permanently deleting such a file/folder raised
ForeignKeyViolationError (empty-trash 500). Both columns are nullable, so SET
NULL keeps the session record as history while unblocking the delete.

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-25

"""

from __future__ import annotations

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

_FKS = (
    ("upload_sessions_parent_id_fkey", "parent_id"),
    ("upload_sessions_drive_item_id_fkey", "drive_item_id"),
)


def upgrade() -> None:
    for name, col in _FKS:
        op.drop_constraint(name, "upload_sessions", type_="foreignkey")
        op.create_foreign_key(
            name, "upload_sessions", "drive_items", [col], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    for name, col in _FKS:
        op.drop_constraint(name, "upload_sessions", type_="foreignkey")
        op.create_foreign_key(name, "upload_sessions", "drive_items", [col], ["id"])

"""ON DELETE rules so emptying trash can permanently delete items

Emptying the trash hard-deletes drive_items. Two FKs to drive_items had no
ON DELETE rule (RESTRICT), so deleting a folder that had ever been logged, or a
starred item, raised a ForeignKeyViolationError (empty-trash 500):

- activity_logs.item_id  -> SET NULL  (keep the audit row, drop the ref)
- user_item_preferences.item_id -> CASCADE (a preference is dead with its item)

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-25

"""

from __future__ import annotations

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("activity_logs_item_id_fkey", "activity_logs", type_="foreignkey")
    op.create_foreign_key(
        "activity_logs_item_id_fkey",
        "activity_logs",
        "drive_items",
        ["item_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint(
        "user_item_preferences_item_id_fkey", "user_item_preferences", type_="foreignkey"
    )
    op.create_foreign_key(
        "user_item_preferences_item_id_fkey",
        "user_item_preferences",
        "drive_items",
        ["item_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "user_item_preferences_item_id_fkey", "user_item_preferences", type_="foreignkey"
    )
    op.create_foreign_key(
        "user_item_preferences_item_id_fkey",
        "user_item_preferences",
        "drive_items",
        ["item_id"],
        ["id"],
    )

    op.drop_constraint("activity_logs_item_id_fkey", "activity_logs", type_="foreignkey")
    op.create_foreign_key(
        "activity_logs_item_id_fkey",
        "activity_logs",
        "drive_items",
        ["item_id"],
        ["id"],
    )

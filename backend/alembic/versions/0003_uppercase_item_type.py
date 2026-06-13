"""uppercase item_type values from 'file'/'folder' to 'FILE'/'FOLDER'

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-13

"""

from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old check constraint that only allows lowercase values
    op.drop_constraint("ck_drive_items_item_type", "drive_items", type_="check")
    # Migrate existing data
    op.execute("UPDATE drive_items SET item_type = 'FILE' WHERE item_type = 'file'")
    op.execute("UPDATE drive_items SET item_type = 'FOLDER' WHERE item_type = 'folder'")
    # Add new check constraint with uppercase values
    op.create_check_constraint(
        "ck_drive_items_item_type",
        "drive_items",
        "item_type IN ('FILE', 'FOLDER')",
    )
    # Also update the initial migration definition to match (for documentation only)


def downgrade() -> None:
    op.drop_constraint("ck_drive_items_item_type", "drive_items", type_="check")
    op.execute("UPDATE drive_items SET item_type = 'file' WHERE item_type = 'FILE'")
    op.execute("UPDATE drive_items SET item_type = 'folder' WHERE item_type = 'FOLDER'")
    op.create_check_constraint(
        "ck_drive_items_item_type",
        "drive_items",
        "item_type IN ('file', 'folder')",
    )

from app.models import (
    ActivityLog,
    Base,
    DriveItem,
    FileVersion,
    RefreshToken,
    Share,
    ShareLink,
    User,
    UserItemPreference,
)


def test_model_tablenames() -> None:
    assert User.__tablename__ == "users"
    assert RefreshToken.__tablename__ == "refresh_tokens"
    assert DriveItem.__tablename__ == "drive_items"
    assert FileVersion.__tablename__ == "file_versions"
    assert Share.__tablename__ == "shares"
    assert ShareLink.__tablename__ == "share_links"
    assert ActivityLog.__tablename__ == "activity_logs"
    assert UserItemPreference.__tablename__ == "user_item_preferences"


def test_base_metadata_has_all_tables() -> None:
    tables = set(Base.metadata.tables.keys())
    expected = {
        "users",
        "refresh_tokens",
        "drive_items",
        "file_versions",
        "shares",
        "share_links",
        "activity_logs",
        "user_item_preferences",
    }
    assert expected <= tables


def test_user_default_uuid() -> None:
    assert User.__table__.c.id is not None


def test_drive_item_columns_exist() -> None:
    cols = {c.name for c in DriveItem.__table__.c}
    for expected in ("id", "owner_id", "parent_id", "item_type", "name", "is_deleted"):
        assert expected in cols


def test_user_item_preference_unique_constraint() -> None:
    from sqlalchemy import Table

    table: Table = UserItemPreference.__table__  # type: ignore[assignment]
    constraints = {c.name for c in table.constraints}
    assert "uq_user_item_preferences" in constraints


def test_activity_log_metadata_column_name() -> None:
    col_names = {c.name for c in ActivityLog.__table__.c}
    assert "metadata" in col_names

from __future__ import annotations

import math
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.schemas.common import (
    CurrentUserResponse,
    DriveItemResponse,
    Page,
    PageParams,
    SortOrder,
    TokenPairResponse,
)


def test_page_create_basic() -> None:
    page = Page[int].create([1, 2, 3], total=10, page=1, page_size=3)
    assert page.items == [1, 2, 3]
    assert page.total == 10
    assert page.page == 1
    assert page.page_size == 3
    assert page.pages == math.ceil(10 / 3)


def test_page_create_exact_division() -> None:
    page = Page[str].create(["a", "b"], total=10, page=2, page_size=5)
    assert page.pages == 2


def test_page_create_empty() -> None:
    page = Page[int].create([], total=0, page=1, page_size=20)
    assert page.pages == 0
    assert page.total == 0


def test_page_params_defaults() -> None:
    params = PageParams()
    assert params.page == 1
    assert params.page_size == 20


def test_page_params_validation_page_zero() -> None:
    with pytest.raises(ValueError):
        PageParams(page=0)


def test_page_params_validation_page_size_zero() -> None:
    with pytest.raises(ValueError):
        PageParams(page_size=0)


def test_page_params_validation_page_size_over_limit() -> None:
    with pytest.raises(ValueError):
        PageParams(page_size=201)


def test_token_pair_default_type() -> None:
    resp = TokenPairResponse(access_token="tok")
    assert resp.token_type == "bearer"
    assert resp.access_token == "tok"


def test_sort_order_values() -> None:
    assert SortOrder.ASC.value == "asc"
    assert SortOrder.DESC.value == "desc"


def test_current_user_response_from_attrs() -> None:
    now = datetime.now(UTC)
    uid = uuid4()

    class _FakeUser:
        id = uid
        email = "test@example.com"
        username = "testuser"
        avatar_url = None
        quota_bytes = 1024
        used_bytes = 0
        is_active = True
        is_admin = False
        created_at = now

    resp = CurrentUserResponse.model_validate(_FakeUser())
    assert resp.id == uid
    assert resp.email == "test@example.com"
    assert resp.is_admin is False


def test_drive_item_response_from_attrs() -> None:
    now = datetime.now(UTC)
    item_id = uuid4()
    _owner_id = uuid4()

    class _FakeItem:
        id = item_id
        owner_id = _owner_id
        parent_id = None
        item_type = "file"
        name = "hello.txt"
        mime_type = "text/plain"
        extension = "txt"
        size_bytes = 42
        is_starred = False
        is_deleted = False
        deleted_at = None
        created_by = _owner_id
        updated_by = None
        created_at = now
        updated_at = now

    resp = DriveItemResponse.model_validate(_FakeItem())
    assert resp.id == item_id
    assert resp.name == "hello.txt"


def test_page_schema_serializes_datetime() -> None:
    now = datetime.now(UTC)
    uid = uuid4()

    class _FakeItem:
        id = uid
        owner_id = uid
        parent_id = None
        item_type = "folder"
        name = "docs"
        mime_type = None
        extension = None
        size_bytes = 0
        is_starred = False
        is_deleted = False
        deleted_at = None
        created_by = uid
        updated_by = None
        created_at = now
        updated_at = now

    item = DriveItemResponse.model_validate(_FakeItem())
    page = Page[DriveItemResponse].create([item], total=1, page=1, page_size=20)
    data = page.model_dump(mode="json")
    assert (
        data["items"][0]["created_at"].endswith("+00:00") or "Z" in data["items"][0]["created_at"]
    )

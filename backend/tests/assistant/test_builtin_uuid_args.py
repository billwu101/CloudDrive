from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.assistant.skills.builtin.read_only import _optional_uuid as ro_optional_uuid
from app.assistant.skills.builtin.write import _optional_uuid as wr_optional_uuid
from app.core.exceptions import AppError

OptionalUuid = Callable[[Any], UUID | None]

# Both builtin modules must resolve the same way; the model spells "root" (not
# null) for the root folder, which used to crash list_items with "Invalid UUID".
_optional_uuids = pytest.mark.parametrize("fn", [ro_optional_uuid, wr_optional_uuid])


@_optional_uuids
def test_root_sentinels_map_to_none(fn: OptionalUuid) -> None:
    for sentinel in ["root", "ROOT", "Root", "null", "none", "/", " root ", None, "", "  "]:
        assert fn(sentinel) is None, sentinel


@_optional_uuids
def test_real_uuid_is_parsed(fn: OptionalUuid) -> None:
    u = uuid4()
    assert fn(str(u)) == u


@_optional_uuids
def test_genuine_garbage_still_errors(fn: OptionalUuid) -> None:
    # A non-sentinel unparseable value must still error, not silently become root.
    with pytest.raises(AppError):
        fn("not-a-uuid-123")

from uuid import uuid4

import pytest

from app.core.exceptions import UnauthorizedError
from app.core.security import create_access_token
from app.db.base import AsyncSessionLocal, engine


def test_db_engine_exists() -> None:
    assert engine is not None


def test_async_session_local_exists() -> None:
    assert AsyncSessionLocal is not None


async def test_get_current_user_id_valid_token() -> None:

    from fastapi.security import HTTPAuthorizationCredentials

    from app.core.dependencies import get_current_user_id

    user_id = uuid4()
    token = create_access_token(user_id)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    result = await get_current_user_id(creds)
    assert result == user_id


async def test_get_current_user_id_invalid_token() -> None:
    from fastapi.security import HTTPAuthorizationCredentials

    from app.core.dependencies import get_current_user_id

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not-a-token")
    with pytest.raises(UnauthorizedError):
        await get_current_user_id(creds)


def test_name_conflict_error() -> None:
    from app.core.exceptions import NameConflictError

    err = NameConflictError()
    assert err.status_code == 409


def test_invalid_operation_error() -> None:
    from app.core.exceptions import InvalidOperationError

    err = InvalidOperationError()
    assert err.status_code == 422

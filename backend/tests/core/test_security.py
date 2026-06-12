from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from app.core.config import get_settings
from app.core.exceptions import AppError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)


def test_hash_password_not_equal_to_plain() -> None:
    plain = "my-secret-password"
    hashed = hash_password(plain)
    assert hashed != plain


def test_verify_password_correct() -> None:
    plain = "correct-password"
    hashed = hash_password(plain)
    assert verify_password(plain, hashed) is True


def test_verify_password_wrong() -> None:
    plain = "correct-password"
    hashed = hash_password(plain)
    assert verify_password("wrong-password", hashed) is False


def test_access_token_encode_decode() -> None:
    user_id = uuid4()
    token = create_access_token(user_id)
    decoded_id = decode_access_token(token)
    assert decoded_id == user_id


def test_refresh_token_not_accepted_as_access_token() -> None:
    user_id = uuid4()
    refresh_token = create_refresh_token(user_id)
    with pytest.raises((AppError, UnauthorizedError)):
        decode_access_token(refresh_token)


def test_access_token_not_accepted_as_refresh_token() -> None:
    user_id = uuid4()
    access_token = create_access_token(user_id)
    with pytest.raises((AppError, UnauthorizedError)):
        decode_refresh_token(access_token)


def test_expired_token_raises_app_error() -> None:
    settings = get_settings()
    user_id = uuid4()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
    }
    expired_token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    with pytest.raises(AppError) as exc_info:
        decode_access_token(expired_token)
    assert exc_info.value.status_code == 401


def test_invalid_token_raises_error() -> None:
    with pytest.raises((AppError, UnauthorizedError)):
        decode_access_token("not.a.valid.token")

import secrets
import string
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt
from pwdlib import PasswordHash

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, UnauthorizedError

_hasher: PasswordHash = PasswordHash.recommended()

# Unambiguous alphabet for generated passwords (no 0/O, 1/l/I) so users can
# copy them out of an email without confusion.
_PASSWORD_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _hasher.verify(plain, hashed)


def generate_random_password(length: int = 10) -> str:
    """Return a cryptographically random password.

    Guarantees at least one lowercase, one uppercase, and one digit so the
    result satisfies common password policies.
    """
    if length < 3:
        raise ValueError("Password length must be at least 3")
    while True:
        candidate = "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))
        if (
            any(c.islower() for c in candidate)
            and any(c.isupper() for c in candidate)
            and any(c in string.digits for c in candidate)
        ):
            return candidate


def _create_token(
    subject: str,
    token_type: str,
    expire_delta: timedelta,
) -> str:
    from app.core.config import get_settings

    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "jti": str(uuid4()),
        "iat": now,
        "exp": now + expire_delta,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: UUID) -> str:
    from app.core.config import get_settings

    settings = get_settings()
    return _create_token(
        subject=str(user_id),
        token_type="access",
        expire_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: UUID) -> str:
    from app.core.config import get_settings

    settings = get_settings()
    return _create_token(
        subject=str(user_id),
        token_type="refresh",
        expire_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def _decode_token(token: str, expected_type: str) -> UUID:
    from app.core.config import get_settings

    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise AppError(ErrorCode.UNAUTHORIZED, "Token expired", status_code=401) from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Invalid token") from exc

    if payload.get("type") != expected_type:
        raise UnauthorizedError("Invalid token type")

    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise UnauthorizedError("Invalid token subject")

    return UUID(sub)


def decode_access_token(token: str) -> UUID:
    return _decode_token(token, "access")


def decode_refresh_token(token: str) -> UUID:
    return _decode_token(token, "refresh")

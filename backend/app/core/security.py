import secrets
import string
from dataclasses import dataclass
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


# --- Public share access credentials (proposal §28, DEC-037) -----------------
#
# Guests exchange a share link token (+ password when set) for one of these.
# The distinct ``type`` claim is what keeps the two worlds apart: _decode_token
# rejects any mismatch, so a share credential can never satisfy
# decode_access_token (no privilege escalation), and a user's access token can
# never satisfy decode_share_access_token.

SHARE_ACCESS_TOKEN_TYPE = "share_access"


@dataclass(frozen=True)
class ShareAccessClaims:
    """Authorisation carried by a share access credential."""

    link_id: UUID
    root_item_id: UUID
    permission: str
    chain_started_at: datetime  # first issue in the refresh chain


def create_share_access_token(
    *,
    link_id: UUID,
    root_item_id: UUID,
    permission: str,
    chain_started_at: datetime | None = None,
) -> str:
    """Issue a short-lived credential for one share link.

    ``chain_started_at`` is carried unchanged through refreshes so the total
    lifetime can be capped independently of how often the client refreshes.
    """
    from app.core.config import get_settings

    settings = get_settings()
    now = datetime.now(UTC)
    started = chain_started_at or now
    payload: dict[str, Any] = {
        "sub": str(link_id),
        "type": SHARE_ACCESS_TOKEN_TYPE,
        "itm": str(root_item_id),
        "prm": permission,
        "cst": started.timestamp(),
        "jti": str(uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=settings.share_access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_share_access_token(token: str) -> ShareAccessClaims:
    from app.core.config import get_settings

    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.InvalidTokenError as exc:  # covers expiry
        raise UnauthorizedError("Invalid or expired share credential") from exc

    if payload.get("type") != SHARE_ACCESS_TOKEN_TYPE:
        raise UnauthorizedError("Invalid share credential")

    try:
        return ShareAccessClaims(
            link_id=UUID(str(payload["sub"])),
            root_item_id=UUID(str(payload["itm"])),
            permission=str(payload["prm"]),
            chain_started_at=datetime.fromtimestamp(float(payload["cst"]), tz=UTC),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise UnauthorizedError("Invalid share credential") from exc

"""Remaining auth gaps: GET /auth/me, account deactivation, forgot-password.

Covers API-AUTH-09 (proposal section 5.1 item 1) plus the deactivation branch
of proposal section 19 (403 / USER_INACTIVE) and the drift risk between the two
"who am I" endpoints, which return the same schema from two different services.

Every write is read back through a *different* endpoint or straight from the
users table, because "the POST returned 200" is exactly the evidence that would
still be there if nothing had changed.

Deliberately NOT covered here: API-AUTH-10 (login rate limiting, proposal
section 17.4 item 2). No throttling exists anywhere in `app/`, so a test for it
could only be a guaranteed failure.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import text

from app.core.security import create_access_token
from tests.integration.conftest import _SessionFactory, auth_headers, register_and_login

pytestmark = pytest.mark.asyncio

_PASSWORD = "Password123!"

# The endpoint answers identically for every address; see auth/router.py.
_RESET_MESSAGE = "If an account exists for that email, a reset password has been sent."

# Body built in AuthService.forgot_password: "...is:\n\n    <password>\n\n".
_TEMP_PASSWORD_RE = re.compile(r"temporary password is:\s+(\S+)")

# Fields of CurrentUserResponse (app/schemas/common.py), shared by both
# /auth/me and /users/me. Listed here so a field added to only one of the two
# routers shows up as a failure rather than as a silent divergence.
_ME_FIELDS = {
    "id",
    "email",
    "username",
    "avatar_url",
    "quota_bytes",
    "used_bytes",
    "is_active",
    "is_admin",
    "must_change_password",
    "created_at",
}


# -- helpers ------------------------------------------------------------------


class _EmailLogCapture(logging.Handler):
    """Collects what ConsoleEmailProvider writes instead of sending mail.

    A dedicated handler rather than pytest's caplog: it works regardless of
    propagation and root-logger configuration, which is what carries the only
    copy of the generated temporary password in a console-mailer environment.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@contextmanager
def _capture_emails() -> Iterator[_EmailLogCapture]:
    logger = logging.getLogger("app.email")
    handler = _EmailLogCapture()
    previous_level = logger.level
    logger.setLevel(logging.WARNING)
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)


def _extract_temp_password(captured: _EmailLogCapture, *, recipient: str) -> str:
    for message in captured.messages:
        if f"to={recipient}" not in message:
            continue
        match = _TEMP_PASSWORD_RE.search(message)
        if match is not None:
            return match.group(1)
    raise AssertionError(f"no reset email captured for {recipient}: {captured.messages!r}")


async def _skip_unless_console_mailer(client: AsyncClient) -> None:
    """Skip when a real SMTP host is configured.

    With EMAIL_PROVIDER=smtp the temporary password goes to a mailbox this test
    cannot read, so the password-recovery assertions are unverifiable here.
    """
    health = await client.get("/health")
    assert health.status_code == 200, health.text
    if health.json()["mail_provider"] != "console":
        pytest.skip("EMAIL_PROVIDER=smtp: the temporary password is not written to the log")


async def _set_active(email: str, *, active: bool) -> None:
    """Flip users.is_active directly - there is no API that can disable an account."""
    async with _SessionFactory() as session:
        await session.execute(
            text("UPDATE users SET is_active = :active WHERE email = :email"),
            {"active": active, "email": email},
        )
        await session.commit()
    assert (await _read_user_row(email))["is_active"] is active


async def _read_user_row(email: str) -> dict[str, Any]:
    async with _SessionFactory() as session:
        result = await session.execute(
            text(
                "SELECT password_hash, is_active, must_change_password "
                "FROM users WHERE email = :email"
            ),
            {"email": email},
        )
        row = result.one()
    return {
        "password_hash": str(row[0]),
        "is_active": bool(row[1]),
        "must_change_password": bool(row[2]),
    }


async def _login(client: AsyncClient, email: str, password: str) -> Response:
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


# -- GET /auth/me -------------------------------------------------------------


async def test_auth_me_matches_users_me_field_for_field(client: AsyncClient) -> None:
    """Two endpoints, two services, one schema - they must not drift.

    /auth/me goes through AuthService.get_current_user and /users/me through
    UserService.get_by_id; both serialise CurrentUserResponse. The profile is
    mutated first so the comparison covers live data, not just registration
    defaults.
    """
    email = "both-me@test.com"
    h = auth_headers(await register_and_login(client, email=email, username="twoheads"))

    patched = await client.patch("/api/v1/users/me", json={"username": "renamed"}, headers=h)
    assert patched.status_code == 200, patched.text

    auth_me = await client.get("/api/v1/auth/me", headers=h)
    users_me = await client.get("/api/v1/users/me", headers=h)
    assert auth_me.status_code == 200, auth_me.text
    assert users_me.status_code == 200, users_me.text

    body = auth_me.json()
    assert body == users_me.json()
    assert set(body) == _ME_FIELDS
    assert body["email"] == email
    assert body["username"] == "renamed"
    assert body["is_active"] is True
    assert body["is_admin"] is False
    assert body["must_change_password"] is False
    assert body["quota_bytes"] > 0
    assert body["used_bytes"] == 0
    assert "password_hash" not in body


async def test_auth_me_rejects_missing_and_garbage_tokens(client: AsyncClient) -> None:
    """API-AUTH-07 - an unusable token must never return a profile."""
    anonymous = await client.get("/api/v1/auth/me")
    assert anonymous.status_code in (401, 403), anonymous.text
    assert "email" not in anonymous.json()

    garbage = await client.get("/api/v1/auth/me", headers=auth_headers("not-a-jwt"))
    assert garbage.status_code == 401, garbage.text
    assert garbage.json()["error"]["code"] == "UNAUTHORIZED"


async def test_auth_me_and_users_me_disagree_on_a_token_for_a_deleted_user(
    client: AsyncClient,
) -> None:
    """Documents a real inconsistency, so a later unification is a deliberate act.

    A well-formed token whose subject has no row answers 401 UNAUTHORIZED on
    /auth/me (AuthService raises UnauthorizedError) but 404 NOT_FOUND on
    /users/me (UserService raises NotFoundError). Both are "you are nobody";
    the frontend cannot treat them the same way.
    """
    h = auth_headers(create_access_token(uuid4()))

    auth_me = await client.get("/api/v1/auth/me", headers=h)
    users_me = await client.get("/api/v1/users/me", headers=h)

    assert auth_me.status_code == 401, auth_me.text
    assert auth_me.json()["error"]["code"] == "UNAUTHORIZED"
    assert users_me.status_code == 404, users_me.text
    assert users_me.json()["error"]["code"] == "NOT_FOUND"


# -- account deactivation -----------------------------------------------------


async def test_deactivated_account_cannot_log_in(client: AsyncClient) -> None:
    """Proposal section 19: a disabled account is 403 USER_INACTIVE, not 401.

    The distinction matters: 401 tells the user to retype the password, 403
    tells them to contact an administrator.
    """
    email = "disabled@test.com"
    await register_and_login(client, email=email, username="disabled")
    await _set_active(email, active=False)

    resp = await _login(client, email, _PASSWORD)
    assert resp.status_code == 403, resp.text
    assert resp.json()["error"]["code"] == "USER_INACTIVE"

    # Reactivating restores login, proving the flag was the cause.
    await _set_active(email, active=True)
    again = await _login(client, email, _PASSWORD)
    assert again.status_code == 200, again.text
    me = await client.get("/api/v1/auth/me", headers=auth_headers(again.json()["access_token"]))
    assert me.json()["email"] == email
    assert me.json()["is_active"] is True


async def test_wrong_password_on_a_deactivated_account_looks_like_any_bad_password(
    client: AsyncClient,
) -> None:
    """AuthService.login verifies the password before checking is_active.

    So a caller who does not already know the password learns nothing about
    the account's status - 401 INVALID_CREDENTIALS either way. Locking this in
    because reordering the two checks would turn 403 into an oracle for
    "this address exists and is disabled".
    """
    email = "disabled-oracle@test.com"
    await register_and_login(client, email=email, username="oracle")
    await _set_active(email, active=False)

    disabled = await _login(client, email, "TotallyWrong123!")
    unknown = await _login(client, "no-such-account@test.com", "TotallyWrong123!")

    assert disabled.status_code == 401, disabled.text
    assert unknown.status_code == 401, unknown.text
    assert disabled.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert disabled.json() == unknown.json()


async def test_deactivated_account_cannot_refresh(client: AsyncClient) -> None:
    """Silent refresh (proposal section 17.1 item 6) must stop for a disabled account.

    Without this the session would outlive deactivation by a whole refresh
    window. Reactivation is checked afterwards so a failure here means the
    is_active branch fired, not that the cookie was lost.
    """
    email = "refresh-disabled@test.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": "refreshoff", "password": _PASSWORD},
    )
    login = await _login(client, email, _PASSWORD)
    assert login.status_code == 200, login.text

    await _set_active(email, active=False)
    blocked = await client.post("/api/v1/auth/refresh")
    assert blocked.status_code == 401, blocked.text
    assert blocked.json()["error"]["code"] == "UNAUTHORIZED"

    await _set_active(email, active=True)
    allowed = await client.post("/api/v1/auth/refresh")
    assert allowed.status_code == 200, allowed.text
    me = await client.get("/api/v1/auth/me", headers=auth_headers(allowed.json()["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == email


async def test_access_token_issued_before_deactivation_still_works(client: AsyncClient) -> None:
    """Records CURRENT behaviour, which is a gap rather than a decision.

    Neither `get_current_user_id` (core/dependencies.py) nor
    `AuthService.get_current_user` looks at is_active, so an access token
    minted before deactivation keeps opening protected endpoints until it
    expires (ACCESS_TOKEN_EXPIRE_MINUTES, default 30). Note that /auth/me even
    reports is_active=false while serving the request. If the product decides
    deactivation must be immediate, the fix belongs in the dependency and this
    test should be inverted deliberately.
    """
    email = "still-in@test.com"
    h = auth_headers(await register_and_login(client, email=email, username="stillin"))
    await _set_active(email, active=False)

    me = await client.get("/api/v1/auth/me", headers=h)
    assert me.status_code == 200, me.text
    assert me.json()["is_active"] is False

    # Not limited to /auth/me: ordinary protected endpoints are open too.
    items = await client.get("/api/v1/drive/items", headers=h)
    assert items.status_code == 200, items.text
    assert "items" in items.json()

    # The lockout that does work is the login path.
    assert (await _login(client, email, _PASSWORD)).status_code == 403


# -- POST /auth/forgot-password ----------------------------------------------


async def test_forgot_password_answers_identically_for_known_and_unknown_email(
    client: AsyncClient,
) -> None:
    """API-AUTH-09 - the endpoint must not become an account-enumeration oracle.

    Same status, same body, same content type for a registered address and for
    one that was never registered.
    """
    known = "known-reset@test.com"
    await register_and_login(client, email=known, username="known")

    hit = await client.post("/api/v1/auth/forgot-password", json={"email": known})
    miss = await client.post("/api/v1/auth/forgot-password", json={"email": "nobody-here@test.com"})

    assert hit.status_code == 200, hit.text
    assert miss.status_code == 200, miss.text
    assert hit.json() == miss.json() == {"message": _RESET_MESSAGE}
    assert hit.headers["content-type"] == miss.headers["content-type"]
    # The reply must not name the account or leak the new credential.
    assert known not in hit.text


async def test_forgot_password_temporary_password_replaces_the_old_one(
    client: AsyncClient,
) -> None:
    """API-AUTH-09 (A3) - the emailed password must actually be the live one.

    Verified three ways: the old password stops working, the emailed one logs
    in, and the stored hash changed. Skipped when a real SMTP host is
    configured, because then the password never reaches this process.
    """
    await _skip_unless_console_mailer(client)

    email = "reset-me@test.com"
    await register_and_login(client, email=email, username="resetme")
    before = await _read_user_row(email)

    with _capture_emails() as captured:
        resp = await client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert resp.status_code == 200, resp.text

    temp_password = _extract_temp_password(captured, recipient=email)
    assert temp_password != _PASSWORD
    assert len(temp_password) == 10, temp_password
    assert temp_password.isalnum(), temp_password

    stale = await _login(client, email, _PASSWORD)
    assert stale.status_code == 401, stale.text
    assert stale.json()["error"]["code"] == "INVALID_CREDENTIALS"

    fresh = await _login(client, email, temp_password)
    assert fresh.status_code == 200, fresh.text

    me = await client.get("/api/v1/auth/me", headers=auth_headers(fresh.json()["access_token"]))
    assert me.status_code == 200, me.text
    assert me.json()["email"] == email
    assert me.json()["must_change_password"] is True

    after = await _read_user_row(email)
    assert after["password_hash"] != before["password_hash"]
    assert after["password_hash"].startswith(("$2a$", "$2b$", "$2y$", "$argon2"))
    assert temp_password not in after["password_hash"]


async def test_must_change_password_flag_clears_once_a_new_password_is_chosen(
    client: AsyncClient,
) -> None:
    """The full recovery round trip: reset, sign in, choose a password, flag off.

    Both /auth/me and /users/me are read so the flag cannot go stale on one of
    them, and the final login proves the chosen password really took effect.
    """
    await _skip_unless_console_mailer(client)

    email = "recovering@test.com"
    chosen = "ChosenByMe456!"
    await register_and_login(client, email=email, username="recovering")

    with _capture_emails() as captured:
        assert (
            await client.post("/api/v1/auth/forgot-password", json={"email": email})
        ).status_code == 200
    temp_password = _extract_temp_password(captured, recipient=email)

    login = await _login(client, email, temp_password)
    assert login.status_code == 200, login.text
    h = auth_headers(login.json()["access_token"])

    assert (await client.get("/api/v1/auth/me", headers=h)).json()["must_change_password"] is True
    assert (await client.get("/api/v1/users/me", headers=h)).json()["must_change_password"] is True
    assert (await _read_user_row(email))["must_change_password"] is True

    changed = await client.patch(
        "/api/v1/users/me/password",
        json={"current_password": temp_password, "new_password": chosen},
        headers=h,
    )
    assert changed.status_code == 204, changed.text

    assert (await client.get("/api/v1/auth/me", headers=h)).json()["must_change_password"] is False
    assert (await client.get("/api/v1/users/me", headers=h)).json()["must_change_password"] is False
    assert (await _read_user_row(email))["must_change_password"] is False

    assert (await _login(client, email, chosen)).status_code == 200
    assert (await _login(client, email, temp_password)).status_code == 401


async def test_forgot_password_does_nothing_for_a_deactivated_account(
    client: AsyncClient,
) -> None:
    """A disabled account must not be resettable, and must not be detectable.

    AuthService.forgot_password returns early for `not user.is_active`, so the
    only observable difference is inside the database: the hash is untouched
    and no mail was produced.
    """
    await _skip_unless_console_mailer(client)

    email = "disabled-reset@test.com"
    await register_and_login(client, email=email, username="disabledreset")
    await _set_active(email, active=False)
    before = await _read_user_row(email)

    with _capture_emails() as captured:
        resp = await client.post("/api/v1/auth/forgot-password", json={"email": email})

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"message": _RESET_MESSAGE}
    assert not [m for m in captured.messages if f"to={email}" in m], captured.messages

    after = await _read_user_row(email)
    assert after["password_hash"] == before["password_hash"]
    assert after["must_change_password"] is False


async def test_forgot_password_matches_the_email_case_insensitively(
    client: AsyncClient,
) -> None:
    """Registration and recovery both normalise (strip + lowercase) the address.

    A user who typed " Mixed.Case@Test.com " into the recovery form must still
    get a working password, otherwise recovery silently no-ops for anyone whose
    mail client capitalises their address.
    """
    await _skip_unless_console_mailer(client)

    stored = "mixed.case@test.com"
    await register_and_login(client, email=stored, username="mixedcase")

    with _capture_emails() as captured:
        resp = await client.post(
            "/api/v1/auth/forgot-password", json={"email": "  Mixed.Case@Test.com  "}
        )
    assert resp.status_code == 200, resp.text

    temp_password = _extract_temp_password(captured, recipient=stored)
    fresh = await _login(client, stored, temp_password)
    assert fresh.status_code == 200, fresh.text
    me = await client.get("/api/v1/auth/me", headers=auth_headers(fresh.json()["access_token"]))
    assert me.json()["email"] == stored
    assert me.json()["must_change_password"] is True

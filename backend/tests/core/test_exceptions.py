import httpx

from app.core.error_codes import ErrorCode
from app.core.exceptions import (
    AppError,
    ForbiddenError,
    NotFoundError,
    QuotaExceededError,
    UnauthorizedError,
)
from app.main import app


def test_app_error_attributes() -> None:
    err = AppError(ErrorCode.VALIDATION_ERROR, "bad input", {"field": "email"})
    assert err.code == ErrorCode.VALIDATION_ERROR
    assert err.message == "bad input"
    assert err.details == {"field": "email"}
    assert err.status_code == 400


def test_unauthorized_error_status() -> None:
    err = UnauthorizedError()
    assert err.status_code == 401
    assert err.code == ErrorCode.UNAUTHORIZED


def test_forbidden_error_status() -> None:
    err = ForbiddenError()
    assert err.status_code == 403


def test_not_found_error_status() -> None:
    err = NotFoundError()
    assert err.status_code == 404


def test_quota_exceeded_error_status() -> None:
    err = QuotaExceededError()
    assert err.status_code == 413


async def test_error_response_format() -> None:
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/test-error")
    async def trigger_error() -> None:
        raise AppError(ErrorCode.NOT_FOUND, "Item not found", status_code=404)

    app.include_router(router)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/test-error")

    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"] == "Item not found"
    assert "details" in body["error"]

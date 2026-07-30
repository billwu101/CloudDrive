import httpx

from app.main import app


async def test_health_returns_ok() -> None:
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    # Whether mail actually leaves the server cannot be learned by using the
    # reset endpoint (it is non-enumerable by design), so it is reported here.
    assert "mail_delivers" in body
    assert "mail_provider" in body

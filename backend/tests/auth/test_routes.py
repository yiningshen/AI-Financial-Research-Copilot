import asyncio

import httpx

from app.auth.dependencies import CurrentUser, get_current_user
from app.main import app


def _get_authenticated_user() -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get("/auth/me")

    return asyncio.run(request())


def test_get_authenticated_user_requires_bearer_token():
    response = _get_authenticated_user()

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_get_authenticated_user_returns_identity_without_exposing_token():
    async def override_current_user() -> CurrentUser:
        return CurrentUser(
            id="user-id",
            email="analyst@example.com",
            access_token="secret-token",
        )

    app.dependency_overrides[get_current_user] = override_current_user
    try:
        response = _get_authenticated_user()
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "id": "user-id",
        "email": "analyst@example.com",
    }

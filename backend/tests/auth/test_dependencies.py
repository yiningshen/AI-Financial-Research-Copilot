import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from supabase_auth.errors import AuthApiError

from app.auth import dependencies


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _protected_app(work_calls: list[str]) -> FastAPI:
    app = FastAPI()

    @app.get("/protected")
    async def protected_route(current_user: dependencies.CurrentUserDependency):
        work_calls.append(current_user.id)
        return {"user_id": current_user.id}

    return app


def _get(app: FastAPI, headers: dict[str, str] | None = None) -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get("/protected", headers=headers)

    return asyncio.run(request())


def test_get_current_user_returns_verified_identity(monkeypatch):
    async def get_user(token):
        assert token == "valid-token"
        return SimpleNamespace(
            user=SimpleNamespace(id="user-id", email="analyst@example.com")
        )

    async def create_client(token):
        assert token == "valid-token"
        return SimpleNamespace(auth=SimpleNamespace(get_user=get_user))

    monkeypatch.setattr(dependencies, "create_user_client", create_client)

    user = asyncio.run(dependencies.get_current_user(_credentials("valid-token")))

    assert user == dependencies.CurrentUser(
        id="user-id",
        email="analyst@example.com",
        access_token="valid-token",
    )


def test_get_current_user_rejects_missing_credentials():
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(dependencies.get_current_user(None))

    assert exc_info.value.status_code == 401
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


def test_get_current_user_rejects_invalid_token(monkeypatch):
    async def get_user(token):
        raise AuthApiError("invalid JWT", 401, "bad_jwt")

    async def create_client(token):
        return SimpleNamespace(auth=SimpleNamespace(get_user=get_user))

    monkeypatch.setattr(dependencies, "create_user_client", create_client)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(dependencies.get_current_user(_credentials("invalid-token")))

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid or missing bearer token"
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


def test_get_current_user_rejects_empty_auth_response(monkeypatch):
    async def get_user(token):
        return None

    async def create_client(token):
        return SimpleNamespace(auth=SimpleNamespace(get_user=get_user))

    monkeypatch.setattr(dependencies, "create_user_client", create_client)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(dependencies.get_current_user(_credentials("unknown-token")))

    assert exc_info.value.status_code == 401


def test_missing_token_stops_protected_work():
    work_calls = []

    response = _get(_protected_app(work_calls))

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert work_calls == []


def test_expired_token_stops_protected_work(monkeypatch):
    work_calls = []

    async def get_user(token):
        raise AuthApiError("JWT expired", 401, "bad_jwt")

    async def create_client(token):
        return SimpleNamespace(auth=SimpleNamespace(get_user=get_user))

    monkeypatch.setattr(dependencies, "create_user_client", create_client)

    response = _get(
        _protected_app(work_calls),
        headers={"Authorization": "Bearer expired-token"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert work_calls == []

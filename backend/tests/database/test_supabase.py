import asyncio
from types import SimpleNamespace

from app.database import supabase


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        supabase_url="https://example.supabase.co",
        supabase_anon_key="anon-key",
        supabase_service_role_key="service-role-key",
    )


def test_create_user_client_uses_user_token_and_anon_key(monkeypatch):
    calls = []
    expected_client = object()

    async def fake_create_client(url, key, options):
        calls.append((url, key, options))
        return expected_client

    monkeypatch.setattr(supabase, "settings", _settings())
    monkeypatch.setattr(supabase, "acreate_client", fake_create_client)

    client = asyncio.run(supabase.create_user_client("user-access-token"))

    assert client is expected_client
    url, key, options = calls.pop()
    assert url == "https://example.supabase.co"
    assert key == "anon-key"
    assert options.headers == {"Authorization": "Bearer user-access-token"}
    assert options.auto_refresh_token is False
    assert options.persist_session is False


def test_create_service_role_client_uses_service_role_credentials(monkeypatch):
    calls = []
    expected_client = object()

    async def fake_create_client(url, key, options):
        calls.append((url, key, options))
        return expected_client

    monkeypatch.setattr(supabase, "settings", _settings())
    monkeypatch.setattr(supabase, "acreate_client", fake_create_client)

    client = asyncio.run(supabase.create_service_role_client())

    assert client is expected_client
    url, key, options = calls.pop()
    assert url == "https://example.supabase.co"
    assert key == "service-role-key"
    assert options.headers == {"Authorization": "Bearer service-role-key"}
    assert options.auto_refresh_token is False
    assert options.persist_session is False

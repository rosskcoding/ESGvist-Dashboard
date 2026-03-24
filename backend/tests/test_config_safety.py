import pytest
from httpx import AsyncClient

from app.core.config import build_settings, settings
from app.main import create_app


@pytest.mark.asyncio
async def test_self_registration_defaults_to_enabled_in_local(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "app_env", "local")
    monkeypatch.setattr(settings, "allow_self_registration", None)

    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "local-defaults@example.com",
            "password": "password123",
            "full_name": "Local Defaults",
        },
    )

    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_self_registration_defaults_to_disabled_outside_local(
    client: AsyncClient, monkeypatch
):
    monkeypatch.setattr(settings, "app_env", "staging")
    monkeypatch.setattr(settings, "allow_self_registration", None)

    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "staging-defaults@example.com",
            "password": "password123",
            "full_name": "Staging Defaults",
        },
    )

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "REGISTRATION_DISABLED"


def test_create_app_rejects_unsafe_non_local_config(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "staging")
    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr(settings, "jwt_secret", "change-me-in-production")
    monkeypatch.setattr(settings, "email_fail_silently", True)
    monkeypatch.setattr(settings, "storage_backend", "minio")
    monkeypatch.setattr(settings, "minio_access_key", "minioadmin")
    monkeypatch.setattr(settings, "minio_secret_key", "minioadmin")

    with pytest.raises(RuntimeError, match="Unsafe runtime configuration"):
        create_app()


def test_create_app_accepts_safe_non_local_config(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "jwt_secret", "prod-secret-value-that-is-not-default-123")
    monkeypatch.setattr(settings, "email_fail_silently", False)
    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr(settings, "allow_self_registration", None)

    app = create_app()

    assert app is not None
    assert settings.self_registration_enabled is False


def test_runtime_warnings_flag_unsafe_cors_origins(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(
        settings,
        "cors_origins",
        [
            "*",
            "http://frontend.example.com",
            "http://localhost:3000",
            "https://app.example.com/path",
        ],
    )

    warnings = settings.runtime_warnings()

    assert any("wildcard '*'" in warning for warning in warnings)
    assert any("should use https outside local development" in warning for warning in warnings)
    assert any("points to localhost in a non-local environment" in warning for warning in warnings)
    assert any("should not include path" in warning for warning in warnings)


def test_runtime_warnings_flag_local_service_urls_and_local_email(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(
        settings,
        "database_url",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/esgvist",
    )
    monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:6379/0")
    monkeypatch.setattr(settings, "email_from", "no-reply@esgvist.local")

    warnings = settings.runtime_warnings()

    assert any("DATABASE_URL points to localhost" in warning for warning in warnings)
    assert any("REDIS_URL points to localhost" in warning for warning in warnings)
    assert any("EMAIL_FROM should not use a .local domain" in warning for warning in warnings)


def test_runtime_warnings_allow_clean_https_origins(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(
        settings,
        "cors_origins",
        ["https://app.example.com", "https://ops.example.com:8443"],
    )
    monkeypatch.setattr(
        settings,
        "database_url",
        "postgresql+asyncpg://postgres:postgres@db.internal:5432/esgvist",
    )
    monkeypatch.setattr(settings, "redis_url", "redis://redis.internal:6379/0")
    monkeypatch.setattr(settings, "email_from", "no-reply@esgvist.example.com")

    assert settings.runtime_warnings() == []


def test_build_settings_uses_environment_profiles(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")

    production_settings = build_settings()

    assert production_settings.app_env == "production"
    assert production_settings.debug is False
    assert production_settings.self_registration_enabled is False
    assert production_settings.email_fail_silently is False

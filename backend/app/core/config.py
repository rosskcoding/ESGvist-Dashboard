from typing import Literal
from urllib.parse import urlsplit

from pydantic_settings import BaseSettings


class _EnvironmentProbe(BaseSettings):
    app_env: Literal["local", "staging", "production"] = "local"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


class Settings(BaseSettings):
    app_env: Literal["local", "staging", "production"] = "local"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/esgvist"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 7

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # App
    debug: bool = True
    app_name: str = "ESGvist API"
    app_version: str = "0.1.0"
    slow_request_warning_ms: int = 1000
    dashboard_progress_cache_ttl_seconds: int = 15
    db_auto_upgrade: bool = False
    db_require_current_revision: bool | None = None

    # Self-service registration
    allow_self_registration: bool | None = None

    # Email
    email_enabled: bool = True
    email_provider: str = "console"
    email_from: str = "no-reply@esgvist.local"
    email_fail_silently: bool = True

    # AI
    ai_enabled: bool = False
    ai_provider: str = "static"
    ai_model: str = "static-ai"
    ai_api_key: str = ""
    ai_base_url: str = ""
    ai_max_tokens: int = 1024
    ai_temperature: float = 0.2

    # Storage
    storage_backend: str = "local"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "esg-evidence"
    minio_secure: bool = False

    # Rate limiting
    rate_limit_per_minute: int = 100

    # AI timeout
    ai_timeout_seconds: int = 15

    # Outlier detection
    outlier_threshold_percent: float = 30.0

    @property
    def is_local_env(self) -> bool:
        return self.app_env == "local"

    @property
    def self_registration_enabled(self) -> bool:
        if self.allow_self_registration is not None:
            return self.allow_self_registration
        return self.is_local_env

    @property
    def require_current_db_revision(self) -> bool:
        if self.db_require_current_revision is not None:
            return self.db_require_current_revision
        return not self.debug

    def runtime_warnings(self) -> list[str]:
        warnings: list[str] = []

        for origin in self.cors_origins:
            normalized = origin.strip()
            if not normalized:
                warnings.append("CORS_ORIGINS contains an empty origin entry")
                continue
            if normalized == "*":
                warnings.append(
                    "CORS_ORIGINS should not use wildcard '*' with credentialed requests"
                )
                continue

            parsed = urlsplit(normalized)
            if not parsed.scheme or not parsed.netloc:
                warnings.append(
                    f"CORS_ORIGINS entry '{origin}' is not a valid origin; use scheme://host[:port]"
                )
                continue
            if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
                warnings.append(
                    f"CORS_ORIGINS entry '{origin}' should not include path, query, "
                    "or fragment components"
                )

            hostname = parsed.hostname or ""
            if self.is_local_env:
                continue

            if hostname in {"localhost", "127.0.0.1"}:
                warnings.append(
                    f"CORS_ORIGINS entry '{origin}' points to localhost in a non-local environment"
                )
            elif parsed.scheme != "https":
                warnings.append(
                    f"CORS_ORIGINS entry '{origin}' should use https outside local development"
                )

        if not self.is_local_env:
            warnings.extend(self._warn_if_local_service_url("DATABASE_URL", self.database_url))
            warnings.extend(self._warn_if_local_service_url("REDIS_URL", self.redis_url))
            if self.email_from.endswith(".local"):
                warnings.append(
                    "EMAIL_FROM should not use a .local domain outside local development"
                )

        return warnings

    @staticmethod
    def _warn_if_local_service_url(setting_name: str, value: str) -> list[str]:
        parsed = urlsplit(value)
        hostname = parsed.hostname or ""
        if hostname in {"localhost", "127.0.0.1"}:
            return [
                f"{setting_name} points to localhost in a non-local environment; "
                "verify this is intentional"
            ]
        return []

    def validate_runtime_configuration(self) -> None:
        if self.is_local_env:
            return

        issues: list[str] = []
        if self.debug:
            issues.append("DEBUG must be false when APP_ENV is staging or production")
        if self.jwt_secret == "change-me-in-production":
            issues.append("JWT_SECRET must be overridden outside local")
        if self.email_fail_silently:
            issues.append("EMAIL_FAIL_SILENTLY must be false outside local")
        if self.storage_backend in {"minio", "s3"} and (
            self.minio_access_key == "minioadmin" or self.minio_secret_key == "minioadmin"
        ):
            issues.append(
                "MINIO_ACCESS_KEY and MINIO_SECRET_KEY must not use default minioadmin credentials"
            )

        if issues:
            raise RuntimeError(
                "Unsafe runtime configuration for non-local environment: " + "; ".join(issues)
            )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


class LocalSettings(Settings):
    app_env: Literal["local"] = "local"
    debug: bool = True
    allow_self_registration: bool | None = True
    email_fail_silently: bool = True


class StagingSettings(Settings):
    app_env: Literal["staging"] = "staging"
    debug: bool = False
    allow_self_registration: bool | None = False
    email_fail_silently: bool = False


class ProductionSettings(Settings):
    app_env: Literal["production"] = "production"
    debug: bool = False
    allow_self_registration: bool | None = False
    email_fail_silently: bool = False


def build_settings() -> Settings:
    env = _EnvironmentProbe().app_env
    if env == "local":
        return LocalSettings()
    if env == "staging":
        return StagingSettings()
    return ProductionSettings()


settings = build_settings()

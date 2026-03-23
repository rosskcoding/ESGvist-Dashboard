from pydantic_settings import BaseSettings


class Settings(BaseSettings):
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

    # Self-service registration
    allow_self_registration: bool = True

    # Email
    email_enabled: bool = True
    email_provider: str = "console"
    email_from: str = "no-reply@esgvist.local"
    email_fail_silently: bool = True

    # AI
    ai_enabled: bool = False
    ai_provider: str = "static"
    ai_model: str = "static-ai"

    # Storage
    storage_backend: str = "local"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

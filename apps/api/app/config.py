"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn, RedisDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "ESG Report Creator API"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/esg_reports"
    )
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # Redis
    redis_url: RedisDsn = RedisDsn("redis://localhost:6379/0")

    # Security
    secret_key: SecretStr = SecretStr("CHANGE_ME_IN_PRODUCTION")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # OpenAI (for translation)
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4o-mini"
    translation_daily_budget_usd: float = 0.0  # 0 = disabled
    # Cost control: restrict expensive translation trigger to dedicated roles by default.
    # Env: TRANSLATION_TRIGGER_RESTRICTED=true|false
    translation_trigger_restricted: bool = True
    openai_key_encryption_secret: SecretStr = SecretStr("CHANGE_ME_ENCRYPTION_KEY_32CHARS")

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def _empty_openai_key_to_none(cls, v):
        """
        Treat empty OPENAI_API_KEY as unset.

        This matters in Docker Compose where OPENAI_API_KEY might be passed
        through as an empty string when not configured.
        """
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v

    # Video embeds (security allowlist)
    # Used to validate iframe/embed sources to prevent arbitrary third-party iframes.
    video_embed_allowlist: list[str] = [
        "www.youtube.com",
        "youtube.com",
        "youtu.be",
        "www.youtube-nocookie.com",
        "youtube-nocookie.com",
        "player.vimeo.com",
    ]

    # Limits (from SYSTEM_REGISTRY)
    table_builder_max_rows: int = 30
    table_advanced_max_rows: int = 2000
    block_title_max_length: int = 240
    text_body_max_length: int = 50000

    # Storage (Assets - uploads)
    storage_type: Literal["local", "s3"] = "local"
    storage_local_path: str = "./uploads"
    storage_s3_bucket: str = ""
    storage_s3_region: str = "us-east-1"
    max_upload_size_mb: int = 10  # 10 MB for images

    # Video uploads (self-hosted video blocks)
    video_allowed_mimes: list[str] = ["video/mp4", "video/webm", "video/quicktime"]
    video_allowed_extensions: list[str] = [".mp4", ".webm", ".mov"]
    video_max_upload_mb: int = 500  # 500 MB for videos
    video_max_duration_sec: int = 3600  # 1 hour

    # Storage (Builds - artifacts/exports)
    builds_storage_type: Literal["local", "s3"] = "local"
    builds_local_path: str = "./builds"
    builds_s3_bucket: str = ""
    builds_retention_days: int = 30  # TTL for draft builds cleanup

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()

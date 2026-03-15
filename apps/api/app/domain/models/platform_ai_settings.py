"""
Platform AI Settings — global OpenAI configuration (singleton row).

Goal:
- Store ONE OpenAI key for the whole system (Phase 1).
- Allow superuser to set/validate/delete the key via admin UI.
- Allow superuser to pick default OpenAI model for AI features (translation, incident help, etc.).

Security:
- Key is stored encrypted (server-side only) using secret_encryption helpers.
- Raw key is never returned to clients.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, SmallInteger, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .enums import OpenAIKeyStatus


class PlatformAISettings(Base):
    """
    Singleton table (settings_id=1) for platform-wide OpenAI configuration.
    """

    __tablename__ = "platform_ai_settings"

    settings_id: Mapped[int] = mapped_column(
        SmallInteger,
        primary_key=True,
        default=1,
        doc="Singleton row ID (always 1).",
    )

    openai_api_key_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Encrypted OpenAI API key (server-side only).",
    )
    openai_key_status: Mapped[OpenAIKeyStatus] = mapped_column(
        SQLEnum(
            OpenAIKeyStatus,
            name="openai_key_status",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=OpenAIKeyStatus.DISABLED,
        server_default=OpenAIKeyStatus.DISABLED.value,
    )
    openai_key_last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    openai_model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="gpt-4o-mini",
        server_default="gpt-4o-mini",
        doc="Default model for AI features (e.g. gpt-4o-mini, gpt-4o, gpt-4.1).",
    )

    # Translation prompt templates (NULL = use hardcoded defaults)
    translation_prompt_reporting: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Custom prompt template for 'reporting' mode translations. NULL = use default.",
    )
    translation_prompt_marketing: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Custom prompt template for 'marketing' mode translations. NULL = use default.",
    )

    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )



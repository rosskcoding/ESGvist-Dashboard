"""
AIUsageEvent model — AI feature usage tracking for cost allocation.

Tracks every AI API call (OpenAI) to:
- Enable per-company cost transparency
- Track usage by feature (translation, incident_help, etc.)
- Support usage-based billing in future
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .enums import AIFeature

if TYPE_CHECKING:
    from .company import Company


class AIUsageEvent(Base):
    """
    AI usage event — tracks individual AI API calls for cost allocation.

    Invariants:
    - company_id NULL = platform-level usage (e.g. superuser incident help)
    - company_id non-NULL = company-scoped usage (e.g. translation)
    - estimated_cost_usd calculated from tokens + model pricing
    """

    __tablename__ = "ai_usage_events"

    event_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    # Company scope (nullable for platform-level usage)
    company_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.company_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Company scope for cost allocation, NULL for platform usage",
    )
    timestamp_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )
    feature: Mapped[AIFeature] = mapped_column(
        SQLEnum(
            AIFeature,
            name="ai_feature",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True,
        doc="AI feature: incident_help, translation, etc.",
    )
    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="OpenAI model used (e.g. gpt-4o-mini, gpt-4o)",
    )
    input_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of input tokens consumed",
    )
    output_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of output tokens generated",
    )
    estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6),  # Up to 9999.999999 USD
        nullable=False,
        default=Decimal("0.0"),
        doc="Estimated cost in USD based on model pricing",
    )
    metadata_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Additional context (e.g. job_id, error_code, etc.)",
    )

    def __repr__(self) -> str:
        company_str = f" company={self.company_id}" if self.company_id else " [platform]"
        return f"<AIUsageEvent {self.feature.value} {self.model}{company_str} ${self.estimated_cost_usd}>"

    @classmethod
    def create(
        cls,
        feature: AIFeature,
        model: str,
        input_tokens: int,
        output_tokens: int,
        estimated_cost_usd: Decimal | float,
        company_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> "AIUsageEvent":
        """
        Create a new AI usage event.

        Args:
            feature: AI feature type
            model: OpenAI model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            estimated_cost_usd: Estimated cost in USD
            company_id: Company scope (None for platform usage)
            metadata: Additional context

        Returns:
            New AIUsageEvent instance
        """
        if isinstance(estimated_cost_usd, float):
            estimated_cost_usd = Decimal(str(estimated_cost_usd))

        return cls(
            feature=feature,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost_usd,
            company_id=company_id,
            metadata_json=metadata,
        )



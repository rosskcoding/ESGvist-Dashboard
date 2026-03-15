"""
Company and CompanyMembership models — Multi-tenant foundation.

Company is the tenant entity that owns reports and users belong to via membership.
CompanyMembership binds users to companies with owner/admin flags.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, event, select
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .enums import CompanyStatus, OpenAIKeyStatus
from app.utils.slug import slugify

if TYPE_CHECKING:
    from .dataset import Dataset
    from .report import Report
    from .user import User


def generate_slug(name: str) -> str:
    """
    Generate URL-friendly slug from company name.

    Examples:
    - "KazEnergo JSC" -> "kazenergo-jsc"
    - "Test To Be Deleted/" -> "test-to-be-deleted"
    - "Company Name LLC" -> "company-name-llc"
    """
    slug = slugify(name, max_length=255)
    return slug or "company"


class Company(Base, TimestampMixin):
    """
    Company entity — tenant for multi-tenant isolation.

    Invariants:
    - name is required and should be unique per deployment
    - slug is auto-generated from name, unique, and used in URLs
    - status controls whether company is active
    - At least one owner must exist (enforced at application level)
    """

    __tablename__ = "companies"

    company_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        doc="URL-friendly identifier generated from name",
    )
    status: Mapped[CompanyStatus] = mapped_column(
        SQLEnum(
            CompanyStatus,
            name="company_status_enum",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=CompanyStatus.ACTIVE,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    # OpenAI (per-company key management)
    openai_api_key_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Encrypted OpenAI key (server-side only); never returned to clients in raw form",
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

    # Translation budget (per-company daily limit)
    translation_daily_budget_usd: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0",
        doc="Daily translation budget in USD (0 = use platform default; effective 0 disables enforcement)",
    )

    # Relationships
    memberships: Mapped[list["CompanyMembership"]] = relationship(
        "CompanyMembership",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    reports: Mapped[list["Report"]] = relationship(
        "Report",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    datasets: Mapped[list["Dataset"]] = relationship(
        "Dataset",
        back_populates="company",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Company {self.name} ({self.company_id})>"

    @property
    def is_active(self) -> bool:
        """Check if company is active."""
        return self.status == CompanyStatus.ACTIVE


@event.listens_for(Company, "before_insert")
def _company_before_insert_generate_slug(mapper, connection, target: "Company") -> None:  # noqa: ARG001
    """
    Ensure `Company.slug` is set on insert.

    This is required because DB column `companies.slug` is NOT NULL.
    We auto-generate from `name` and ensure uniqueness by suffixing `-N`.

    Notes:
    - API endpoints also generate slugs explicitly; this is a safety net for scripts/tests.
    - Uniqueness is best-effort (race conditions can still hit the DB unique constraint).
    """
    if getattr(target, "slug", None):
        return
    if not getattr(target, "name", None):
        return

    base_slug = generate_slug(target.name)
    slug = base_slug
    counter = 1

    # Ensure uniqueness against existing rows
    while True:
        exists = connection.execute(
            select(Company.company_id).where(Company.slug == slug).limit(1)
        ).first()
        if not exists:
            break
        slug = f"{base_slug}-{counter}"
        counter += 1

    target.slug = slug


class CompanyMembership(Base, TimestampMixin):
    """
    CompanyMembership — user-company binding.

    This represents a user's membership in a company (tenant access).
    Company-level permissions are granted via RoleAssignment with corporate_lead role.

    Invariants:
    - (company_id, user_id) is unique
    """

    __tablename__ = "company_memberships"

    membership_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    company_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.company_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="memberships",
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="memberships",
        foreign_keys=[user_id],
    )

    def __repr__(self) -> str:
        return f"<CompanyMembership user={self.user_id} company={self.company_id}>"

"""
AuditEvent model — SYSTEM_REGISTRY B12.

Extended for multi-tenant:
- company_id: tenant scope for event filtering (NULL for platform events)
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AuditEvent(Base):
    """
    Append-only audit log for IAM, privileged actions, translation, builds.

    Invariants:
    - append-only; no updates via UI
    - company_id NULL = platform-level event
    - company_id non-NULL = tenant-scoped event
    """

    __tablename__ = "audit_events"

    event_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    # Tenant scope (nullable for platform events)
    company_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.company_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Tenant scope for event filtering, NULL for platform events",
    )
    timestamp_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )
    actor_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Type: user, service, system",
    )
    actor_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Action: login, logout, create, update, delete, approve, export, etc.",
    )
    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    metadata_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Additional context (old_value, new_value, reason, etc.)",
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    def __repr__(self) -> str:
        company_str = f" company={self.company_id}" if self.company_id else " [platform]"
        return f"<AuditEvent {self.action} on {self.entity_type}/{self.entity_id}{company_str}>"

    @classmethod
    def create(
        cls,
        actor_type: str,
        actor_id: str,
        action: str,
        entity_type: str,
        entity_id: str,
        metadata: dict | None = None,
        ip_address: str | None = None,
        company_id: UUID | None = None,
    ) -> "AuditEvent":
        """Factory method for creating audit events."""
        return cls(
            company_id=company_id,
            actor_type=actor_type,
            actor_id=str(actor_id),
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            metadata_json=metadata,
            ip_address=ip_address,
        )

    @property
    def is_platform_event(self) -> bool:
        """Check if this is a platform-level event (no company scope)."""
        return self.company_id is None

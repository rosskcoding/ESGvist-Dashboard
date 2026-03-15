"""
RoleAssignment model — Unified scoped role assignments.

Single table for all role assignments with scope_type/scope_id pattern.
Replaces multiple separate assignment tables.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base
from .enums import AssignableRole, ScopeType

if TYPE_CHECKING:
    from .company import Company
    from .user import User


class RoleAssignment(Base):
    """
    RoleAssignment — scoped role binding for users.

    Unified model for:
    - Company-scoped roles (editor, reviewer at company level)
    - Report-scoped roles (editor, auditor for specific report)
    - Section-scoped roles (section_editor/SME for specific sections)

    Invariants:
    - User must have CompanyMembership to have RoleAssignment in company
    - scope_id references company/report/section depending on scope_type
    - locales field is optional, primarily for translator role
    """

    __tablename__ = "role_assignments"

    assignment_id: Mapped[UUID] = mapped_column(
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
    role: Mapped[AssignableRole] = mapped_column(
        SQLEnum(
            AssignableRole,
            # NOTE: DB stores this as VARCHAR + CHECK constraint (see Alembic 20241227_0003).
            # We intentionally use non-native enum mapping to avoid binding params as ::assignable_role_enum.
            native_enum=False,
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    scope_type: Mapped[ScopeType] = mapped_column(
        SQLEnum(
            ScopeType,
            # NOTE: DB stores this as VARCHAR + CHECK constraint (see Alembic 20241227_0003).
            native_enum=False,
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    scope_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        doc="ID of company, report, or section depending on scope_type",
    )
    locales: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
        doc="Locale restrictions for translator role",
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    company: Mapped["Company"] = relationship(
        "Company",
        foreign_keys=[company_id],
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="role_assignments",
        foreign_keys=[user_id],
    )

    def __repr__(self) -> str:
        scope_str = f"{self.scope_type.value}:{self.scope_id}"
        locale_str = f" locales={self.locales}" if self.locales else ""
        return f"<RoleAssignment {self.role.value} on {scope_str}{locale_str}>"

    def matches_scope(self, scope_type: ScopeType, scope_id: UUID) -> bool:
        """Check if assignment matches the given scope."""
        return self.scope_type == scope_type and self.scope_id == scope_id

    def has_locale_access(self, locale: str) -> bool:
        """Check if assignment grants access to locale (for translators)."""
        if self.locales is None:
            return True  # No restriction = all locales
        return locale in self.locales


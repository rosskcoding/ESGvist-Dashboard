"""
User model — SYSTEM_REGISTRY B12 (AuditEvent actor).

Extended for multi-tenant RBAC:
- is_superuser: platform-level admin flag
- memberships: company bindings
- role_assignments: scoped role bindings
"""

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .block import Block
    from .company import CompanyMembership
    from .refresh_token import RefreshToken
    from .role_assignment import RoleAssignment


class User(Base, TimestampMixin):
    """
    User entity for authentication and authorization.

    Platform access:
    - is_superuser: platform-level admin (can create companies, etc.)

    RBAC model:
    - Company access via CompanyMembership
    - Scoped roles via RoleAssignment (corporate_lead, editor, content_editor, etc.)
    """

    __tablename__ = "users"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    # Platform-level superuser flag
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Platform admin: can create companies, manage platform settings",
    )
    locale_scopes: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
        doc="Locale restrictions for locale-scoped roles. None = all locales.",
    )

    # Relationships
    owned_blocks: Mapped[list["Block"]] = relationship(
        "Block",
        back_populates="owner",
        foreign_keys="Block.owner_user_id",
    )
    memberships: Mapped[list["CompanyMembership"]] = relationship(
        "CompanyMembership",
        back_populates="user",
        foreign_keys="CompanyMembership.user_id",
    )
    role_assignments: Mapped[list["RoleAssignment"]] = relationship(
        "RoleAssignment",
        back_populates="user",
        foreign_keys="RoleAssignment.user_id",
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        foreign_keys="RefreshToken.user_id",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        flags = []
        if self.is_superuser:
            flags.append("superuser")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        return f"<User {self.email}{flag_str}>"

    @property
    def is_platform_admin(self) -> bool:
        """Check if user is platform admin (superuser)."""
        return self.is_superuser

    def has_locale_access(self, locale: str) -> bool:
        """Check if user has access to a specific locale."""
        if self.locale_scopes is None:
            return True  # Global access
        return locale in self.locale_scopes

    def get_membership_for_company(self, company_id: UUID) -> "CompanyMembership | None":
        """Get membership for a specific company."""
        for membership in self.memberships:
            if membership.company_id == company_id and membership.is_active:
                return membership
        return None

    def is_member_of(self, company_id: UUID) -> bool:
        """Check if user is an active member of company."""
        return self.get_membership_for_company(company_id) is not None

"""
Company and CompanyMembership schemas.

Multi-tenant foundation DTOs.
"""

from uuid import UUID

from pydantic import Field

from .common import BaseSchema, TimestampSchema


# =============================================================================
# Company Schemas
# =============================================================================


class CompanyBase(BaseSchema):
    """Base company fields."""

    name: str = Field(min_length=1, max_length=255)


class CompanyCreate(CompanyBase):
    """Schema for creating a company (platform admin only)."""

    pass


class CompanyUpdate(BaseSchema):
    """Schema for updating a company."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = Field(default=None, pattern="^(active|disabled)$")


class CompanyDTO(CompanyBase, TimestampSchema):
    """Company data transfer object (response)."""

    company_id: UUID
    slug: str
    status: str
    created_by: UUID | None = None


class CompanyListDTO(BaseSchema):
    """Minimal company info for lists."""

    company_id: UUID
    name: str
    slug: str
    status: str


# =============================================================================
# CompanyMembership Schemas
# =============================================================================


class MembershipBase(BaseSchema):
    """Base membership fields."""

    user_id: UUID


class MembershipInvite(BaseSchema):
    """Schema for inviting a user to company."""

    user_id: UUID = Field(description="User ID to add to company")


class MembershipUpdate(BaseSchema):
    """Schema for updating membership."""

    is_active: bool | None = None
    full_name: str | None = None


class MembershipDTO(MembershipBase, TimestampSchema):
    """Membership data transfer object (response)."""

    membership_id: UUID
    company_id: UUID
    is_active: bool
    created_by: UUID | None = None


class MembershipWithUserDTO(MembershipDTO):
    """Membership with user details."""

    user_email: str
    user_name: str


# =============================================================================
# User extensions for multi-tenant
# =============================================================================


class UserCompanyDTO(BaseSchema):
    """User's company membership info."""

    company_id: UUID
    company_name: str
    is_corporate_lead: bool
    is_active: bool
    roles: list[str] = Field(
        default_factory=list,
        description="List of role types for this user in this company (e.g. editor, content_editor, viewer)",
    )


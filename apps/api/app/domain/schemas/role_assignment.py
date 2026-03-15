"""
RoleAssignment schemas.

Unified scoped role assignment DTOs.
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from .common import BaseSchema

# =============================================================================
# Enums for validation
# =============================================================================

VALID_ROLES = {
    # Company management
    "corporate_lead",
    # Content roles
    "editor",           # Editor in Chief
    "content_editor",   # Editor (scoped)
    "section_editor",   # SME
    "viewer",           # Read-only
    # Translation role
    "translator",       # Translation workflow: edit, lock, submit
    # Audit roles
    "internal_auditor", # Internal audit (company employees)
    "auditor",          # External auditor
    "audit_lead",       # Lead external auditor
}

VALID_SCOPE_TYPES = {"company", "report", "section"}

VALID_LOCALES = {"ru", "en", "kk", "de", "fr", "ar", "es", "nl", "it"}


# =============================================================================
# RoleAssignment Schemas
# =============================================================================


class RoleAssignmentBase(BaseSchema):
    """Base role assignment fields."""

    user_id: UUID
    role: str = Field(description="Role to assign")
    scope_type: str = Field(description="Scope type: company, report, or section")
    scope_id: UUID = Field(description="ID of the scoped entity")
    locales: list[str] | None = Field(
        default=None,
        description="Locale restrictions (mainly for translator role)",
    )

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f"Invalid role: {v}. Must be one of {VALID_ROLES}")
        return v

    @field_validator("scope_type")
    @classmethod
    def validate_scope_type(cls, v: str) -> str:
        if v not in VALID_SCOPE_TYPES:
            raise ValueError(f"Invalid scope_type: {v}. Must be one of {VALID_SCOPE_TYPES}")
        return v

    @field_validator("locales")
    @classmethod
    def validate_locales(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            invalid = set(v) - VALID_LOCALES
            if invalid:
                raise ValueError(f"Invalid locales: {invalid}")
        return v


class RoleAssignmentCreate(RoleAssignmentBase):
    """Schema for creating a role assignment."""

    pass


class RoleAssignmentUpdate(BaseSchema):
    """Schema for updating a role assignment."""

    role: str | None = Field(default=None, description="New role to assign")
    scope_type: str | None = Field(default=None, description="New scope type")
    scope_id: UUID | None = Field(default=None, description="New scope ID")
    locales: list[str] | None = Field(default=None, description="New locale restrictions")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_ROLES:
            raise ValueError(f"Invalid role: {v}. Must be one of {VALID_ROLES}")
        return v

    @field_validator("scope_type")
    @classmethod
    def validate_scope_type(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_SCOPE_TYPES:
            raise ValueError(f"Invalid scope_type: {v}. Must be one of {VALID_SCOPE_TYPES}")
        return v

    @field_validator("locales")
    @classmethod
    def validate_locales(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            invalid = set(v) - VALID_LOCALES
            if invalid:
                raise ValueError(f"Invalid locales: {invalid}")
        return v


class RoleAssignmentDTO(RoleAssignmentBase):
    """Role assignment data transfer object (response)."""

    assignment_id: UUID
    company_id: UUID
    created_by: UUID | None = None
    created_at_utc: datetime


class RoleAssignmentWithUserDTO(RoleAssignmentDTO):
    """Role assignment with user details."""

    user_email: str
    user_name: str


# =============================================================================
# Query/Filter Schemas
# =============================================================================


class RoleAssignmentFilter(BaseSchema):
    """Filter for querying role assignments."""

    user_id: UUID | None = None
    role: str | None = None
    scope_type: str | None = None
    scope_id: UUID | None = None


# =============================================================================
# Bulk Operations
# =============================================================================


class RoleAssignmentBulkCreate(BaseSchema):
    """Schema for bulk creating role assignments."""

    assignments: list[RoleAssignmentCreate]


class RoleAssignmentBulkDelete(BaseSchema):
    """Schema for bulk deleting role assignments."""

    assignment_ids: list[UUID]

"""
ContentLock schemas.

Two-layer content locking DTOs.
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from .common import BaseSchema


# =============================================================================
# Enums for validation
# =============================================================================

VALID_SCOPE_TYPES = {"report", "section", "block"}
VALID_LOCK_LAYERS = {"coord", "audit"}


# =============================================================================
# ContentLock Schemas
# =============================================================================


class ContentLockBase(BaseSchema):
    """Base content lock fields."""

    scope_type: str = Field(description="Scope type: report, section, or block")
    scope_id: UUID = Field(description="ID of the scoped entity")
    lock_layer: str = Field(description="Lock layer: coord or audit")
    reason: str = Field(min_length=1, max_length=1000, description="Reason for locking")

    @field_validator("scope_type")
    @classmethod
    def validate_scope_type(cls, v: str) -> str:
        if v not in VALID_SCOPE_TYPES:
            raise ValueError(f"Invalid scope_type: {v}. Must be one of {VALID_SCOPE_TYPES}")
        return v

    @field_validator("lock_layer")
    @classmethod
    def validate_lock_layer(cls, v: str) -> str:
        if v not in VALID_LOCK_LAYERS:
            raise ValueError(f"Invalid lock_layer: {v}. Must be one of {VALID_LOCK_LAYERS}")
        return v


class ContentLockCreate(ContentLockBase):
    """Schema for applying a content lock."""

    pass


class ContentLockRelease(BaseSchema):
    """Schema for releasing a content lock."""

    reason: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional reason for releasing",
    )


class ContentLockOverride(BaseSchema):
    """Schema for overriding an audit lock (CompanyOwner only)."""

    reason: str = Field(
        min_length=1,
        max_length=1000,
        description="Required reason for override",
    )


class ContentLockDTO(ContentLockBase):
    """Content lock data transfer object (response)."""

    lock_id: UUID
    company_id: UUID
    is_locked: bool
    locked_by: UUID
    locked_at_utc: datetime
    released_by: UUID | None = None
    released_at_utc: datetime | None = None


class ContentLockWithUserDTO(ContentLockDTO):
    """Content lock with user details."""

    locked_by_name: str
    locked_by_email: str
    released_by_name: str | None = None
    released_by_email: str | None = None


# =============================================================================
# Lock Status Schemas
# =============================================================================


class LockStatusDTO(BaseSchema):
    """Lock status for a given scope."""

    scope_type: str
    scope_id: UUID
    is_locked: bool
    lock_layer: str | None = None  # None if not locked
    locked_by: UUID | None = None
    locked_at_utc: datetime | None = None
    reason: str | None = None


class LockCheckResult(BaseSchema):
    """Result of checking if content is locked."""

    is_locked: bool
    lock_layer: str | None = None
    lock_id: UUID | None = None
    reason: str | None = None
    can_edit: bool = True  # Based on user's permissions


# =============================================================================
# Hierarchical Lock Info
# =============================================================================


class HierarchicalLockInfo(BaseSchema):
    """Lock info for a content item including parent locks."""

    # Direct lock on the item
    direct_lock: LockStatusDTO | None = None
    # Inherited lock from parent (section for block, report for section)
    inherited_lock: LockStatusDTO | None = None
    # Effective lock (direct or inherited, whichever is stronger)
    effective_lock: LockStatusDTO | None = None
    # Whether the user can edit
    can_edit: bool = True



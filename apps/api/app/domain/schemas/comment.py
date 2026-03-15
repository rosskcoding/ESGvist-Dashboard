"""
Comment schemas.

Comment threads and messages for audit support.
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from .common import BaseSchema, TimestampSchema


# =============================================================================
# Validation constants
# =============================================================================

VALID_ANCHOR_TYPES = {"report", "section", "block"}
VALID_THREAD_STATUSES = {"open", "resolved"}
VALID_SUB_ANCHOR_TYPES = {"table", "chart", "datapoint", "audit_check_item"}


# =============================================================================
# CommentThread Schemas
# =============================================================================


class CommentThreadBase(BaseSchema):
    """Base comment thread fields."""

    anchor_type: str = Field(description="Anchor type: report, section, or block")
    anchor_id: UUID = Field(description="ID of the anchored entity")
    # Sub-anchor for granularity
    sub_anchor_type: str | None = Field(default=None, description="table, chart, datapoint, or audit_check_item")
    sub_anchor_key: str | None = Field(default=None, max_length=255, description="Technical key for sub-anchor")
    sub_anchor_label: str | None = Field(default=None, max_length=255, description="Human-readable label")

    @field_validator("anchor_type")
    @classmethod
    def validate_anchor_type(cls, v: str) -> str:
        if v not in VALID_ANCHOR_TYPES:
            raise ValueError(f"Invalid anchor_type: {v}. Must be one of {VALID_ANCHOR_TYPES}")
        return v

    @field_validator("sub_anchor_type")
    @classmethod
    def validate_sub_anchor_type(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_SUB_ANCHOR_TYPES:
            raise ValueError(f"Invalid sub_anchor_type: {v}. Must be one of {VALID_SUB_ANCHOR_TYPES}")
        return v


class CommentThreadCreate(BaseSchema):
    """Schema for creating a comment thread."""

    anchor_type: str = Field(description="Anchor type: report, section, or block")
    anchor_id: UUID = Field(description="ID of the anchored entity")
    sub_anchor_type: str | None = None
    sub_anchor_key: str | None = Field(default=None, max_length=255)
    sub_anchor_label: str | None = Field(default=None, max_length=255)
    # First comment in thread
    first_comment_body: str = Field(min_length=1, max_length=10000, description="Initial comment text")
    is_internal: bool = Field(default=False, description="Team-only comment")

    @field_validator("anchor_type")
    @classmethod
    def validate_anchor_type(cls, v: str) -> str:
        if v not in VALID_ANCHOR_TYPES:
            raise ValueError(f"Invalid anchor_type: {v}. Must be one of {VALID_ANCHOR_TYPES}")
        return v


class CommentThreadDTO(CommentThreadBase):
    """Comment thread data transfer object."""

    thread_id: UUID
    company_id: UUID
    report_id: UUID
    status: str = Field(description="Thread status: open or resolved")
    created_at: datetime
    created_by: UUID | None = None
    resolved_at: datetime | None = None
    resolved_by: UUID | None = None
    # Summary fields
    comment_count: int = Field(default=0, description="Total number of comments")
    open_comment_count: int = Field(default=0, description="Number of non-deleted comments")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_THREAD_STATUSES:
            raise ValueError(f"Invalid status: {v}. Must be one of {VALID_THREAD_STATUSES}")
        return v


class CommentThreadWithCommentsDTO(CommentThreadDTO):
    """Comment thread with nested comments."""

    comments: list["CommentDTO"] = Field(default_factory=list)


# =============================================================================
# Comment Schemas
# =============================================================================


class CommentBase(BaseSchema):
    """Base comment fields."""

    body: str = Field(min_length=1, max_length=10000, description="Comment text (markdown/plain)")
    is_internal: bool = Field(default=False, description="Team-only comment, hidden from auditors")


class CommentCreate(CommentBase):
    """Schema for creating a comment."""

    pass  # All fields inherited from CommentBase


class CommentDTO(CommentBase):
    """Comment data transfer object."""

    comment_id: UUID
    thread_id: UUID
    company_id: UUID
    author_user_id: UUID | None = None
    author_role_snapshot: str | None = Field(default=None, description="Role at creation time")
    created_at: datetime
    # Soft delete
    deleted_at: datetime | None = None
    deleted_by: UUID | None = None
    # Computed
    is_deleted: bool = Field(default=False, description="Whether comment is deleted")

    # Author details (optional, populated via join)
    author_name: str | None = Field(default=None, description="Author display name")
    author_email: str | None = Field(default=None, description="Author email")


# =============================================================================
# Action Schemas
# =============================================================================


class CommentThreadResolveRequest(BaseSchema):
    """Request to resolve a comment thread."""

    pass  # No body needed, resolved_by comes from current_user


class CommentThreadReopenRequest(BaseSchema):
    """Request to reopen a comment thread."""

    pass  # No body needed


class CommentDeleteRequest(BaseSchema):
    """Request to soft delete a comment."""

    pass  # No body needed, deleted_by comes from current_user


# =============================================================================
# Filter Schemas
# =============================================================================


class CommentThreadFilter(BaseSchema):
    """Filter for querying comment threads."""

    anchor_type: str | None = None
    anchor_id: UUID | None = None
    sub_anchor_type: str | None = None
    status: str | None = Field(default=None, description="Filter by status: open or resolved")
    created_by: UUID | None = Field(default=None, description="Filter by creator")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_THREAD_STATUSES:
            raise ValueError(f"Invalid status: {v}. Must be one of {VALID_THREAD_STATUSES}")
        return v


# =============================================================================
# Summary Schemas
# =============================================================================


class CommentThreadSummaryDTO(BaseSchema):
    """Summary of comment threads for a scope."""

    scope_type: str
    scope_id: UUID
    total_threads: int
    open_threads: int
    resolved_threads: int
    total_comments: int



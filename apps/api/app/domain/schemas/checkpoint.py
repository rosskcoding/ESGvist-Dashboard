"""
Checkpoint schemas — manual version snapshots.
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .common import BaseSchema


class CheckpointCreate(BaseSchema):
    """Schema for creating a checkpoint."""

    comment: str | None = Field(
        default=None,
        max_length=500,
        description="Optional user comment about this checkpoint (max 500 chars)",
    )


class CheckpointMetadata(BaseSchema):
    """
    Checkpoint metadata (without full snapshot).

    Used for listing checkpoints.
    """

    checkpoint_id: UUID
    report_id: UUID
    company_id: UUID
    created_by: UUID | None
    created_at_utc: datetime
    comment: str | None
    content_root_hash: str
    snapshot_size_bytes: int


class CheckpointDTO(CheckpointMetadata):
    """
    Full checkpoint DTO with snapshot data.

    Used when restoring or inspecting checkpoint content.
    """

    snapshot_json: dict = Field(
        description="Complete report snapshot (sections + blocks + i18n)"
    )


class CheckpointRestoreRequest(BaseSchema):
    """Request to restore from a checkpoint."""

    pass  # No parameters needed — checkpoint_id comes from URL


class CheckpointRestoreResponse(BaseSchema):
    """Response after successful restore."""

    status: str = "ok"
    restored_to: UUID = Field(description="Checkpoint ID that was restored")
    safety_checkpoint_id: UUID = Field(
        description="Auto-created safety checkpoint before restore"
    )


class BlockAutosaveRequest(BaseSchema):
    """
    Unified autosave request for block content.

    Combines data_json (non-localized) and fields_json (localized) updates
    in a single atomic operation with version conflict detection.
    """

    locale: str = Field(
        description="Locale for fields_json update (ru, en, kk)"
    )
    expected_version: int = Field(
        ge=1,
        description="Expected block version for optimistic locking",
    )
    fields_json: dict | None = Field(
        default=None,
        description="Localized fields to update (BlockI18n.fields_json)",
    )
    data_json: dict | None = Field(
        default=None,
        description="Non-localized data to update (Block.data_json)",
    )

    @field_validator("locale")
    @classmethod
    def validate_locale(cls, v: str) -> str:
        """Validate locale is one of the supported values."""
        if v not in ("ru", "en", "kk"):
            raise ValueError(f"Invalid locale: {v}. Must be one of: ru, en, kk")
        return v

    @model_validator(mode='after')
    def check_at_least_one_field(self) -> 'BlockAutosaveRequest':
        """Ensure at least one of fields_json or data_json is provided."""
        if self.fields_json is None and self.data_json is None:
            raise ValueError(
                "At least one of fields_json or data_json must be provided"
            )
        return self


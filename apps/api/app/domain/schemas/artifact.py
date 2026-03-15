"""
Pydantic schemas for Release Build Artifacts.

Export v2: PDF and DOCX artifact management.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ArtifactCreate(BaseModel):
    """Request body for creating an artifact."""

    format: str = Field(
        ...,
        pattern="^(pdf|docx)$",
        description="Artifact format: pdf or docx",
    )
    locale: str = Field(
        ...,
        min_length=2,
        max_length=10,
        description="Locale code (e.g. 'ru', 'en')",
    )
    profile: str | None = Field(
        default="audit",
        pattern="^(audit|screen)$",
        description="PDF profile (audit or screen). Only for PDF.",
    )


class ArtifactDTO(BaseModel):
    """Artifact data transfer object."""

    artifact_id: UUID
    build_id: UUID
    format: str
    locale: str | None
    profile: str | None
    status: str
    path: str | None
    sha256: str | None
    size_bytes: int | None
    error_code: str = Field(
        default="none",
        description="Structured error code for programmatic handling",
    )
    error_message: str | None = Field(
        default=None,
        description="Human-readable error message if generation failed",
    )
    created_at_utc: datetime
    updated_at_utc: datetime

    model_config = ConfigDict(from_attributes=True)


class ArtifactListResponse(BaseModel):
    """Response for listing artifacts."""

    artifacts: list[ArtifactDTO]
    build_id: UUID
    build_status: str


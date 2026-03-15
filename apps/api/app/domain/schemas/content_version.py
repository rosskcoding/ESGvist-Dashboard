"""
ContentVersion schemas.

Lightweight change tracking for block content.
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from .common import BaseSchema


# =============================================================================
# ContentVersion Schemas
# =============================================================================


class ContentVersionDTO(BaseSchema):
    """Content version data transfer object."""

    version_id: UUID
    company_id: UUID
    report_id: UUID
    block_id: UUID
    locale: str = Field(max_length=10, description="Locale of the content version")
    saved_at: datetime
    saved_by: UUID | None = None
    fields_json_snapshot: dict = Field(description="Snapshot of BlockI18n.fields_json")
    # Optional author details (populated via join)
    saver_name: str | None = Field(default=None, description="Name of user who saved this version")
    saver_email: str | None = Field(default=None, description="Email of user who saved this version")


class ContentVersionListDTO(BaseSchema):
    """List of content versions for a block+locale."""

    block_id: UUID
    locale: str
    versions: list[ContentVersionDTO] = Field(default_factory=list, description="Versions ordered by saved_at desc")
    total_count: int = Field(default=0, description="Total number of versions")



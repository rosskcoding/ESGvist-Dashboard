"""
Asset schemas.
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from .common import BaseSchema
from .enums import AssetKindEnum


class AssetDTO(BaseSchema):
    """Asset data transfer object (response)."""

    asset_id: UUID
    kind: AssetKindEnum
    filename: str
    storage_path: str
    mime_type: str
    size_bytes: int
    sha256: str
    created_at_utc: datetime

    # Computed URL (populated by service)
    url: str | None = None


class AssetUploadResponse(BaseSchema):
    """Response after successful upload."""

    asset: AssetDTO
    message: str = "Asset uploaded successfully"


class AssetLinkDTO(BaseSchema):
    """Asset link data transfer object."""

    block_id: UUID
    asset_id: UUID
    purpose: str = Field(default="content")


class AssetLinkCreate(BaseSchema):
    """Schema for linking an existing asset to a block."""

    block_id: UUID
    purpose: str = Field(default="content", max_length=50)


class SignedUrlRequest(BaseSchema):
    """Request for generating a signed URL."""

    ttl_seconds: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Token lifetime in seconds (60-3600)",
    )


class SignedUrlResponse(BaseSchema):
    """Response containing a signed URL."""

    url: str = Field(description="Signed URL for asset access")
    expires_at: int = Field(description="Unix timestamp when URL expires")
    ttl_seconds: int = Field(description="Token lifetime in seconds")


"""
Image block schemas.

Spec reference: 04_Content_Model.md Section 4.2.5
"""

from typing import Literal
from uuid import UUID

from pydantic import Field

from .base import BlockDataSchema, BlockI18nSchema


class ImageDisplay(BlockDataSchema):
    """Image display settings."""

    fit: Literal["contain", "cover", "fill", "none"] = "contain"
    aspect_ratio: str | None = Field(default=None, max_length=20, description="e.g., '16:9', '4:3'")
    focal_point_x: float | None = Field(default=None, ge=0, le=1, description="Focal point X (0-1)")
    focal_point_y: float | None = Field(default=None, ge=0, le=1, description="Focal point Y (0-1)")


class ImageBlockData(BlockDataSchema):
    """
    Image block data_json schema.

    Contains asset reference and layout settings.
    """

    asset_id: UUID
    layout: Literal["full", "half", "inline", "float-left", "float-right"] = "full"
    link_url: str | None = Field(default=None, max_length=2000)
    loading: Literal["lazy", "eager"] = "lazy"

    # Display settings
    display: ImageDisplay | None = Field(default=None, description="Image display settings")

    # Auto-numbering support
    figure_number: str | None = Field(
        default=None,
        max_length=20,
        description="Figure number: '1', '2.3' (manual override, auto if empty)",
    )


class ImageBlockI18n(BlockI18nSchema):
    """
    Image block fields_json schema.

    Contains localized caption and alt text.
    """

    caption: str = Field(default="", max_length=500)
    alt_text: str = Field(
        default="",
        max_length=500,
        description="Required for accessibility",
    )
    credits: str | None = Field(
        default=None,
        max_length=200,
        description="Photo credits/copyright: '© 2024 Company Name'",
    )
    source: str | None = Field(
        default=None,
        max_length=200,
        description="Source attribution",
    )


# --- Infographic (variant of image) ---


class InfographicBlockData(BlockDataSchema):
    """Infographic block data_json."""

    asset_id: UUID
    hotspots: list[dict] = Field(
        default_factory=list,
        max_length=20,
        description="Interactive hotspots on infographic",
    )


class InfographicBlockI18n(BlockI18nSchema):
    """Infographic block fields_json."""

    caption: str = Field(default="", max_length=500)
    alt_text: str = Field(max_length=500)
    hotspot_labels: dict[str, str] = Field(
        default_factory=dict,
        description="Map of hotspot ID to localized label",
    )


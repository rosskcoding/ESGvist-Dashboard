"""
Image block schemas.

Type: image
Purpose: Single image or infographic

Spec reference: 04_Content_Model.md Section 4.2.5
"""

from typing import Literal

from pydantic import Field

from .base import CAPTION_MAX_LENGTH, BlockDataSchema, BlockI18nSchema


class ImageBlockData(BlockDataSchema):
    """
    Image block data schema.

    Contains asset reference and layout configuration.
    """

    asset_id: str = Field(description="Image asset UUID")
    layout: Literal["full", "half", "inline"] = Field(
        default="full",
        description="Image layout mode",
    )
    link_url: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional link URL",
    )


class ImageBlockI18n(BlockI18nSchema):
    """
    Image block i18n schema.

    Contains caption and alt text.
    """

    caption: str = Field(
        default="",
        max_length=CAPTION_MAX_LENGTH,
        description="Image caption",
    )
    alt_text: str = Field(
        default="",
        max_length=500,
        description="Alt text for accessibility (recommended for A11Y)",
    )


# Gallery variant (multiple images)
class GalleryItem(BlockDataSchema):
    """Gallery item."""

    asset_id: str
    order: int = 0


class GalleryItemI18n(BlockI18nSchema):
    """Gallery item i18n."""

    caption: str = Field(default="", max_length=300)
    alt_text: str = Field(max_length=300)


class GalleryBlockData(BlockDataSchema):
    """Gallery block data schema."""

    items: list[GalleryItem] = Field(
        default_factory=list,
        max_length=20,
        description="Gallery images (max 20)",
    )
    layout: Literal["grid", "carousel", "masonry"] = "grid"
    columns: int = Field(default=3, ge=1, le=6)


class GalleryBlockI18n(BlockI18nSchema):
    """Gallery block i18n schema."""

    title: str | None = Field(default=None, max_length=200)
    items: list[GalleryItemI18n] = Field(
        default_factory=list,
        max_length=20,
    )


"""
Quote and Callout block schemas.

Types: quote, callout
Purpose: Highlighted text, quotes, and callout boxes

Spec reference: 04_Content_Model.md Section 4.2.1
"""

from typing import Literal

from pydantic import Field

from .base import BlockDataSchema, BlockI18nSchema


# === Quote Block ===

class QuoteBlockData(BlockDataSchema):
    """
    Quote block data schema.

    For blockquotes with optional author photo.
    """

    author_photo_asset_id: str | None = Field(
        default=None,
        description="Author photo asset UUID",
    )


class QuoteBlockI18n(BlockI18nSchema):
    """
    Quote block i18n schema.

    Contains the quote text and attribution.
    """

    quote_text: str = Field(
        default="",
        max_length=2000,
        description="The quote text",
    )
    author_name: str = Field(
        default="",
        max_length=200,
        description="Author name",
    )
    author_title: str | None = Field(
        default=None,
        max_length=300,
        description="Author title/position",
    )


# === Callout Block ===

class CalloutBlockData(BlockDataSchema):
    """
    Callout block data schema.

    For highlighted information boxes with different tones.
    """

    tone: Literal["info", "warning", "risk", "positive", "neutral"] = Field(
        default="info",
        description="Visual tone of the callout",
    )
    icon: str | None = Field(
        default=None,
        max_length=50,
        description="Icon identifier",
    )


class CalloutBlockI18n(BlockI18nSchema):
    """
    Callout block i18n schema.

    Contains the callout title and message.
    """

    title: str | None = Field(
        default=None,
        max_length=200,
        description="Optional callout title",
    )
    message: str = Field(
        max_length=2000,
        description="Callout message content",
    )


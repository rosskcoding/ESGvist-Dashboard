"""
Text block schemas.

Type: text
Purpose: Rich text content (paragraphs, lists, formatting)

Spec reference: 04_Content_Model.md Section 4.2.1
"""

from pydantic import Field

from .base import BODY_MAX_LENGTH, BlockDataSchema, BlockI18nSchema


class TextBlockData(BlockDataSchema):
    """
    Text block data schema (non-localized).

    Text blocks have no structural data — all content is localized.
    """

    # Empty: all content is in i18n
    pass


class TextBlockI18n(BlockI18nSchema):
    """
    Text block i18n schema (localized).

    Contains the rich text content.
    """

    body_html: str = Field(
        default="",
        max_length=BODY_MAX_LENGTH,
        description="Rich text HTML content (sanitized)",
    )


# Intro/Lead variant
class IntroBlockData(BlockDataSchema):
    """Intro block data schema."""
    pass


class IntroBlockI18n(BlockI18nSchema):
    """Intro block i18n schema."""

    lead_text: str = Field(
        max_length=1200,
        description="Lead paragraph text",
    )
    subtitle: str | None = Field(
        default=None,
        max_length=300,
        description="Optional subtitle",
    )


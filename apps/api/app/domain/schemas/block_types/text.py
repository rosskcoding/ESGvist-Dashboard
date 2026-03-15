"""
Text block schemas.

Spec reference: 04_Content_Model.md Section 4.2.1
"""

from pydantic import Field

from .base import BlockI18nSchema, EmptyDataSchema, BODY_HTML_MAX_LENGTH


class TextBlockData(EmptyDataSchema):
    """
    Text block data_json schema.

    Text blocks have no data_json - all content is localized.
    """

    pass


class TextBlockI18n(BlockI18nSchema):
    """
    Text block fields_json schema.

    Contains rich text HTML content.
    """

    body_html: str = Field(
        default="",
        max_length=BODY_HTML_MAX_LENGTH,
        description="Rich text HTML content",
    )


# --- Intro/Lead Block ---


class IntroBlockData(EmptyDataSchema):
    """Intro/Lead block has no structural data."""

    pass


class IntroBlockI18n(BlockI18nSchema):
    """Intro/Lead block fields_json."""

    lead_text: str = Field(
        max_length=1200,
        description="Lead paragraph text",
    )
    subtitle: str | None = Field(
        default=None,
        max_length=300,
        description="Optional subtitle",
    )


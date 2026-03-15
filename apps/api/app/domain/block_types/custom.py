"""
Custom and Accordion block schemas.

Types: custom, accordion, timeline
Purpose: Custom HTML embeds and expandable content

Spec reference: 04_Content_Model.md Section 4.2.9
"""

from typing import Literal

from pydantic import Field

from .base import CAPTION_MAX_LENGTH, BlockDataSchema, BlockI18nSchema


# === Custom Embed Block ===

class CustomBlockData(BlockDataSchema):
    """
    Custom embed block data schema.

    For custom HTML/SVG content.
    Always triggers qa_required + CUSTOM flag.
    """

    html: str = Field(
        default="",
        max_length=200000,
        description="Custom HTML (will be sanitized)",
    )
    css_scoped: str | None = Field(
        default=None,
        max_length=50000,
        description="Scoped CSS",
    )
    sandbox_level: Literal["strict", "relaxed"] = Field(
        default="strict",
        description="Sanitization level",
    )


class CustomBlockI18n(BlockI18nSchema):
    """Custom embed block i18n schema."""

    caption: str | None = Field(
        default=None,
        max_length=CAPTION_MAX_LENGTH,
    )
    insight_text: str | None = Field(
        default=None,
        max_length=1000,
        description="Text description for accessibility",
    )


# === Accordion Block ===

class AccordionItem(BlockDataSchema):
    """Accordion item data."""

    key: str = Field(max_length=50)
    default_open: bool = False


class AccordionItemI18n(BlockI18nSchema):
    """Accordion item i18n."""

    title: str = Field(max_length=200)
    content_html: str = Field(
        max_length=10000,
        description="Accordion content (sanitized HTML)",
    )


class AccordionBlockData(BlockDataSchema):
    """
    Accordion block data schema.

    Expandable/collapsible sections.
    """

    items: list[AccordionItem] = Field(
        default_factory=list,
        max_length=20,
        description="Accordion items (max 20)",
    )
    allow_multiple: bool = Field(
        default=False,
        description="Allow multiple items open at once",
    )


class AccordionBlockI18n(BlockI18nSchema):
    """Accordion block i18n schema."""

    title: str | None = Field(default=None, max_length=200)
    items: list[AccordionItemI18n] = Field(
        default_factory=list,
        max_length=20,
    )


# === Timeline Block ===

class TimelineItem(BlockDataSchema):
    """Timeline item data."""

    date: str = Field(max_length=50, description="Date string (flexible format)")
    icon: str | None = Field(default=None, max_length=50)


class TimelineItemI18n(BlockI18nSchema):
    """Timeline item i18n."""

    title: str = Field(max_length=200)
    description: str = Field(max_length=1000)


class TimelineBlockData(BlockDataSchema):
    """
    Timeline block data schema.

    Chronological events display.
    """

    items: list[TimelineItem] = Field(
        default_factory=list,
        max_length=30,
    )
    layout: Literal["vertical", "horizontal"] = "vertical"


class TimelineBlockI18n(BlockI18nSchema):
    """Timeline block i18n schema."""

    title: str | None = Field(default=None, max_length=200)
    items: list[TimelineItemI18n] = Field(
        default_factory=list,
        max_length=30,
    )


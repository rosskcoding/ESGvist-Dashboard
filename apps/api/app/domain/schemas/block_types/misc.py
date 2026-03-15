"""
Miscellaneous block schemas.

Spec reference: 04_Content_Model.md Sections 4.2.1, 4.2.6-4.2.9
"""

from typing import Literal
from uuid import UUID

from pydantic import Field

from .base import BlockDataSchema, BlockI18nSchema, EmptyDataSchema


# --- Quote Block ---


class QuoteBlockData(BlockDataSchema):
    """Quote block data_json."""

    author_photo_asset_id: UUID | None = None


class QuoteBlockI18n(BlockI18nSchema):
    """Quote block fields_json."""

    quote_text: str = Field(max_length=2000)
    author_name: str = Field(max_length=200)
    author_title: str | None = Field(default=None, max_length=200)
    # New fields for context
    source: str | None = Field(default=None, max_length=200, description="Source: 'Annual Report 2024'")
    context: str | None = Field(default=None, max_length=200, description="Context: 'CEO Address'")
    date: str | None = Field(default=None, max_length=50, description="Date: '2024-12-31'")


# --- Callout Block ---


class CalloutCTA(BlockI18nSchema):
    """Call-to-action for callout block."""

    label: str = Field(max_length=100)
    link_url: str = Field(max_length=2000)


class CalloutBlockData(BlockDataSchema):
    """Callout block data_json."""

    tone: Literal["info", "warning", "risk", "positive", "neutral"] = "info"
    icon: str | None = Field(default=None, max_length=50)


class CalloutBlockI18n(BlockI18nSchema):
    """Callout block fields_json."""

    title: str | None = Field(default=None, max_length=200)
    message: str = Field(max_length=2000)
    cta: CalloutCTA | None = Field(default=None, description="Optional call-to-action button")


# --- Downloads Block ---


class DownloadItem(BlockDataSchema):
    """Single download item."""

    item_id: str = Field(max_length=50, description="Unique ID for drag/edit stability")
    asset_id: UUID
    file_type: Literal["pdf", "xlsx", "csv", "docx", "zip", "other"] = "other"
    # New metadata fields
    version: str | None = Field(default=None, max_length=20, description="Version: 'v1.3'")
    date: str | None = Field(default=None, max_length=50, description="Publication date")
    language: str | None = Field(default=None, max_length=10, description="Language: 'RU', 'EN', 'KK'")
    access: Literal["public", "internal"] = Field(default="public", description="Access level")


class DownloadsBlockData(BlockDataSchema):
    """Downloads block data_json."""

    items: list[DownloadItem] = Field(default_factory=list, max_length=20)
    layout: Literal["list", "grid"] = "list"


class DownloadItemI18n(BlockI18nSchema):
    """Single download item i18n."""

    label: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=500)


class DownloadsBlockI18n(BlockI18nSchema):
    """Downloads block fields_json."""

    title: str | None = Field(default=None, max_length=200, description="Block title")
    items: list[DownloadItemI18n] = Field(default_factory=list)


# --- References/Footnotes Block ---


class ReferenceItem(BlockDataSchema):
    """Single reference item."""

    ref_id: str = Field(max_length=50)
    url: str | None = Field(default=None, max_length=2000)


class ReferencesBlockData(BlockDataSchema):
    """References block data_json."""

    items: list[ReferenceItem] = Field(max_length=100)


class ReferenceItemI18n(BlockI18nSchema):
    """Single reference item i18n."""

    text: str = Field(max_length=1000)


class ReferencesBlockI18n(BlockI18nSchema):
    """References block fields_json."""

    items: list[ReferenceItemI18n] = Field(default_factory=list)


# --- Cross-links Block ---


class CrossLinkItem(BlockDataSchema):
    """Single cross-link item."""

    target_section_id: UUID | None = None
    target_block_id: UUID | None = None
    external_url: str | None = Field(default=None, max_length=2000)


class CrossLinksBlockData(BlockDataSchema):
    """Cross-links block data_json."""

    links: list[CrossLinkItem] = Field(max_length=20)


class CrossLinkItemI18n(BlockI18nSchema):
    """Single cross-link item i18n."""

    label: str = Field(max_length=200)


class CrossLinksBlockI18n(BlockI18nSchema):
    """Cross-links block fields_json."""

    links: list[CrossLinkItemI18n] = Field(default_factory=list)


# --- Accordion Block ---


class AccordionItem(BlockDataSchema):
    """Single accordion item structure."""

    item_id: str = Field(max_length=50)
    expanded_by_default: bool = False


class AccordionBlockData(BlockDataSchema):
    """Accordion block data_json."""

    items: list[AccordionItem] = Field(max_length=20)
    allow_multiple: bool = False


class AccordionItemI18n(BlockI18nSchema):
    """Single accordion item i18n."""

    title: str = Field(max_length=200)
    content_html: str = Field(max_length=10000)


class AccordionBlockI18n(BlockI18nSchema):
    """Accordion block fields_json."""

    items: list[AccordionItemI18n] = Field(default_factory=list)


# --- Timeline Block ---


class TimelineEvent(BlockDataSchema):
    """Single timeline event."""

    event_id: str = Field(max_length=50)

    # Structured date fields (v2)
    date_start: str | None = Field(
        default=None,
        max_length=50,
        description="Start date: '2024-07-01', '2024-Q1', '2024-07', '2024'",
    )
    date_end: str | None = Field(
        default=None,
        max_length=50,
        description="End date (optional, for date ranges)",
    )
    date_kind: Literal["date", "month", "quarter", "year"] = Field(
        default="date",
        description="Date precision/format",
    )

    # Legacy date field (backward compat)
    date: str | None = Field(
        default=None,
        max_length=50,
        description="Legacy: use date_start instead",
    )

    # Meta fields
    icon: str | None = Field(default=None, max_length=50)
    status: Literal["planned", "in_progress", "done"] | None = Field(
        default=None,
        description="Event status",
    )
    tags: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Event tags: ['ESG', 'Climate']",
    )
    link_url: str | None = Field(
        default=None,
        max_length=2000,
        description="Link to more details",
    )


class TimelineBlockData(BlockDataSchema):
    """Timeline block data_json."""

    events: list[TimelineEvent] = Field(default_factory=list, max_length=30)
    orientation: Literal["vertical", "horizontal"] = "vertical"
    auto_sort_by_date: bool = Field(
        default=False,
        description="Auto-sort events by date_start (disables manual reorder)",
    )


class TimelineEventI18n(BlockI18nSchema):
    """Single timeline event i18n."""

    title: str = Field(max_length=200)
    description: str = Field(default="", max_length=1000)


class TimelineBlockI18n(BlockI18nSchema):
    """Timeline block fields_json."""

    title: str | None = Field(default=None, max_length=200, description="Block title")
    events: list[TimelineEventI18n] = Field(default_factory=list)


# --- In-page TOC Block ---


class TOCBlockData(BlockDataSchema):
    """Table of Contents block data_json."""

    mode: Literal["auto", "manual"] = "auto"
    levels: Literal[2, 3] = 2
    include_blocks: bool = False


class TOCBlockI18n(BlockI18nSchema):
    """TOC block fields_json."""

    title: str | None = Field(default=None, max_length=100)


# --- Custom Embed Block ---


class CustomEmbedBlockData(BlockDataSchema):
    """
    Custom HTML/SVG embed block data_json.

    Always requires QA review.
    """

    html: str = Field(max_length=200000)
    css_scoped: str | None = Field(default=None, max_length=50000)
    sandbox_level: Literal["strict", "relaxed"] = "strict"


class CustomEmbedBlockI18n(BlockI18nSchema):
    """Custom embed block fields_json."""

    caption: str | None = Field(default=None, max_length=500)
    insight_text: str | None = Field(
        default=None,
        max_length=2000,
        description="Textual description for accessibility",
    )


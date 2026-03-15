"""
Downloads and References block schemas.

Types: downloads, references, cross_links
Purpose: File downloads, footnotes, and internal links

Spec reference: 04_Content_Model.md Section 4.2.8
"""

from typing import Literal

from pydantic import Field

from .base import BlockDataSchema, BlockI18nSchema


# === Downloads Block ===

class DownloadItem(BlockDataSchema):
    """Download item data."""

    asset_id: str = Field(description="Asset UUID")
    file_type: Literal["pdf", "xlsx", "csv", "doc", "zip", "other"] = Field(
        default="other",
        description="File type for icon display",
    )
    order: int = 0


class DownloadItemI18n(BlockI18nSchema):
    """Download item i18n."""

    label: str = Field(max_length=200, description="Download link text")
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Optional description",
    )


class DownloadsBlockData(BlockDataSchema):
    """
    Downloads block data schema.

    List of downloadable files.
    """

    items: list[DownloadItem] = Field(
        default_factory=list,
        max_length=20,
        description="Download items (max 20)",
    )
    layout: Literal["list", "grid", "compact"] = "list"


class DownloadsBlockI18n(BlockI18nSchema):
    """Downloads block i18n schema."""

    title: str | None = Field(default=None, max_length=200)
    items: list[DownloadItemI18n] = Field(
        default_factory=list,
        max_length=20,
    )


# === References Block ===

class ReferenceItem(BlockDataSchema):
    """Reference item data."""

    ref_id: str = Field(max_length=50, description="Reference ID (e.g., [1])")
    url: str | None = Field(
        default=None,
        max_length=2000,
        description="External URL",
    )


class ReferenceItemI18n(BlockI18nSchema):
    """Reference item i18n."""

    text: str = Field(max_length=1000, description="Reference text")


class ReferencesBlockData(BlockDataSchema):
    """References block data schema."""

    items: list[ReferenceItem] = Field(
        default_factory=list,
        max_length=100,
        description="Reference items",
    )


class ReferencesBlockI18n(BlockI18nSchema):
    """References block i18n schema."""

    title: str | None = Field(default=None, max_length=200)
    items: list[ReferenceItemI18n] = Field(
        default_factory=list,
        max_length=100,
    )


# === Cross-links Block ===

class CrossLinkItem(BlockDataSchema):
    """Cross-link item data."""

    target_section_id: str | None = Field(
        default=None,
        description="Target section UUID",
    )
    target_block_id: str | None = Field(
        default=None,
        description="Target block UUID",
    )


class CrossLinkItemI18n(BlockI18nSchema):
    """Cross-link item i18n."""

    label: str = Field(max_length=200, description="Link text")


class CrossLinksBlockData(BlockDataSchema):
    """Cross-links block data schema."""

    links: list[CrossLinkItem] = Field(
        default_factory=list,
        max_length=20,
    )


class CrossLinksBlockI18n(BlockI18nSchema):
    """Cross-links block i18n schema."""

    title: str | None = Field(default=None, max_length=200)
    links: list[CrossLinkItemI18n] = Field(
        default_factory=list,
        max_length=20,
    )


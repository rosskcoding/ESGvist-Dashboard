"""
Table block schemas.

Type: table
Purpose: Data tables with 4 modes (builder, advanced, custom, image)

Spec reference: 04_Content_Model.md Section 4.2.3
"""

from typing import Literal
from uuid import UUID

from pydantic import Field

from .base import CAPTION_MAX_LENGTH, BlockDataSchema, BlockI18nSchema


# === Mode A: Builder (default) ===

class ColumnDef(BlockDataSchema):
    """Table column definition."""

    key: str = Field(max_length=50, description="Column identifier")
    type: Literal["text", "number", "percent", "currency", "date"] = Field(
        default="text",
        description="Data type for formatting",
    )
    # Back-compat: legacy content stored width as a number (pixels).
    width: str | int | None = Field(
        default=None,
        description="CSS width (e.g., '100px', '20%')",
    )
    align: Literal["left", "center", "right"] = "left"


class BuilderRow(BlockDataSchema):
    """Table builder row."""

    cells: dict[str, str | float | int | None] = Field(
        default_factory=dict,
        description="Column key → cell value",
    )
    is_header: bool = Field(default=False, description="Is this a header row?")
    is_total: bool = Field(default=False, description="Is this a totals row?")


class TableBuilderData(BlockDataSchema):
    """
    Table Builder mode data schema.

    For manual table creation with limited size.
    Constraints: max 30 rows, max 12 columns, no merged cells.
    """

    mode: Literal["builder"] = "builder"
    columns: list[ColumnDef] = Field(
        default_factory=list,
        max_length=12,
        description="Column definitions (max 12)",
    )
    rows: list[BuilderRow] = Field(
        default_factory=list,
        max_length=30,
        description="Table rows (max 30)",
    )
    source_ref: str | None = Field(
        default=None,
        max_length=500,
        description="Data source reference",
    )


class TableBuilderI18n(BlockI18nSchema):
    """Table Builder mode i18n schema."""

    caption: str = Field(
        default="",
        max_length=CAPTION_MAX_LENGTH,
        description="Table caption",
    )
    summary: str = Field(
        default="",
        max_length=1000,
        description="Table summary for accessibility",
    )
    column_labels: dict[str, str] = Field(
        default_factory=dict,
        description="Column key → localized label",
    )
    notes: str | None = Field(
        default=None,
        max_length=2000,
        description="Footnotes",
    )


# === Mode B: Advanced Data Table ===

class DataSource(BlockDataSchema):
    """Data source configuration."""

    type: Literal["inline", "asset_csv", "asset_xlsx", "asset_json"] = "inline"
    asset_id: str | None = Field(
        default=None,
        description="Asset UUID if type is asset_*",
    )
    inline_data: list[dict] | None = Field(
        default=None,
        description="Inline data rows if type is inline",
    )


class TableFeatures(BlockDataSchema):
    """Advanced table features."""

    sortable: bool = True
    filterable: bool = False
    searchable: bool = True
    download_csv: bool = True
    sticky_header: bool = True
    pagination: bool = False
    page_size: int = Field(default=50, ge=10, le=500)


class TableAdvancedData(BlockDataSchema):
    """
    Table Advanced mode data schema.

    For large tables with interactive features.
    Constraints: max 2000 rows, max 40 columns.
    """

    mode: Literal["advanced"] = "advanced"
    columns: list[ColumnDef] = Field(
        default_factory=list,
        max_length=40,
        description="Column definitions (max 40)",
    )
    data_source: DataSource = Field(
        default_factory=DataSource,
        description="Data source configuration",
    )
    features: TableFeatures = Field(
        default_factory=TableFeatures,
        description="Interactive features",
    )
    source_ref: str | None = None


class TableAdvancedI18n(BlockI18nSchema):
    """Table Advanced mode i18n schema."""

    caption: str = Field(default="", max_length=CAPTION_MAX_LENGTH)
    summary: str = Field(default="", max_length=1000)
    column_labels: dict[str, str] = Field(default_factory=dict)
    ui_labels: dict[str, str] | None = Field(
        default=None,
        description="UI labels: search, filter, download, etc.",
    )
    notes: str | None = None


# === Mode C: Custom/Non-standard ===

class TableCustomData(BlockDataSchema):
    """
    Table Custom mode data schema.

    For complex tables with custom HTML.
    Always triggers qa_required flag.
    """

    mode: Literal["custom"] = "custom"
    custom_html: str = Field(
        default="",
        max_length=200000,
        description="Custom HTML (sanitized)",
    )
    custom_css_scoped: str | None = Field(
        default=None,
        max_length=50000,
        description="Scoped CSS",
    )
    source_ref: str | None = None


class TableCustomI18n(BlockI18nSchema):
    """Table Custom mode i18n schema."""

    caption: str = Field(default="", max_length=CAPTION_MAX_LENGTH)
    summary: str = Field(default="", max_length=1000)
    notes: str | None = None


# === Mode D: Table as Image ===

class TableImageData(BlockDataSchema):
    """
    Table Image mode data schema.

    For tables rendered as images (complex formatting).
    """

    mode: Literal["image"] = "image"
    asset_id: str = Field(description="Image asset UUID")
    data_download_asset_id: str | None = Field(
        default=None,
        description="CSV/XLSX asset for download",
    )
    source_ref: str | None = None


class TableImageI18n(BlockI18nSchema):
    """Table Image mode i18n schema."""

    caption: str = Field(default="", max_length=CAPTION_MAX_LENGTH)
    summary: str = Field(default="", max_length=1000)
    alt_text: str = Field(
        max_length=500,
        description="Alt text for accessibility (required)",
    )
    notes: str | None = None


# === Unified Table Block ===

# Note: The actual TableBlockData will be a discriminated union
# based on the 'mode' field. This is handled in the registry.

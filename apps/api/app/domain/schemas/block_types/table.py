"""
Table block schemas (4 modes).

Spec reference: 04_Content_Model.md Section 4.2.3
"""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from .base import BlockDataSchema, BlockI18nSchema


# --- Common Table Types ---


class ColumnDef(BlockDataSchema):
    """Column definition for tables."""

    key: str = Field(max_length=50, pattern=r"^[a-z0-9_]+$")
    type: Literal["text", "number", "percent", "currency", "date"] = "text"
    width: int | None = Field(default=None, ge=50, le=500)
    align: Literal["left", "center", "right"] | None = None
    sortable: bool = True


# --- Mode A: Builder (default) ---


class BuilderCellValue(BlockDataSchema):
    """Cell value in builder mode."""

    value: str | float | int | None = None
    colspan: int = Field(default=1, ge=1, le=12)
    rowspan: int = Field(default=1, ge=1, le=30)


class BuilderRow(BlockDataSchema):
    """Row in builder mode."""

    cells: dict[str, BuilderCellValue | str | float | int | None] = Field(
        default_factory=dict
    )
    is_header: bool = False
    is_footer: bool = False


class TableBuilderData(BlockDataSchema):
    """
    Table Builder mode data_json.

    Limits: ≤30 rows, ≤12 columns
    """

    mode: Literal["builder"] = "builder"
    columns: list[ColumnDef] = Field(max_length=12)
    rows: list[BuilderRow] = Field(max_length=30)
    source_ref: str | None = Field(default=None, max_length=500)
    show_row_numbers: bool = False
    striped: bool = True


class TableBuilderI18n(BlockI18nSchema):
    """Table Builder mode fields_json."""

    caption: str = Field(default="", max_length=500)
    summary: str = Field(default="", max_length=1000)
    column_labels: dict[str, str] = Field(
        default_factory=dict,
        description="Map of column key to localized header",
    )
    notes: str | None = Field(default=None, max_length=2000)


# --- Mode B: Advanced Data Table ---


class InlineTableData(BlockDataSchema):
    """Inline data for advanced table."""

    headers: list[str] = Field(max_length=40)
    rows: list[list[str | float | int | None]] = Field(max_length=2000)


class DataSourceConfig(BlockDataSchema):
    """Data source configuration."""

    type: Literal["inline", "asset_csv", "asset_xlsx", "asset_json"] = "inline"
    asset_id: UUID | None = None
    inline: InlineTableData | None = None
    sheet_name: str | None = None  # For xlsx

    @model_validator(mode="after")
    def validate_source(self) -> "DataSourceConfig":
        if self.type == "inline" and self.inline is None:
            raise ValueError("inline data required when type is 'inline'")
        if self.type != "inline" and self.asset_id is None:
            raise ValueError("asset_id required for non-inline sources")
        return self


class TableFeatures(BlockDataSchema):
    """Interactive features for advanced table."""

    sortable: bool = True
    filterable: bool = False
    searchable: bool = True
    download_csv: bool = True
    sticky_header: bool = True
    pagination: bool = False
    page_size: int = Field(default=50, ge=10, le=100)


class TableAdvancedData(BlockDataSchema):
    """
    Advanced Data Table mode data_json.

    Limits: ≤40 columns, ≤2000 rows
    """

    mode: Literal["advanced"] = "advanced"
    columns: list[ColumnDef] = Field(max_length=40)
    data_source: DataSourceConfig
    features: TableFeatures = Field(default_factory=TableFeatures)
    source_ref: str | None = Field(default=None, max_length=500)


class UILabels(BlockI18nSchema):
    """UI labels for table interactions."""

    search_placeholder: str = Field(default="Search...", max_length=100)
    no_results: str = Field(default="No results found", max_length=200)
    download_button: str = Field(default="Download CSV", max_length=100)
    rows_per_page: str = Field(default="Rows per page", max_length=100)


class TableAdvancedI18n(BlockI18nSchema):
    """Advanced Data Table mode fields_json."""

    caption: str = Field(default="", max_length=500)
    summary: str = Field(default="", max_length=1000)
    column_labels: dict[str, str] = Field(default_factory=dict)
    ui_labels: UILabels | None = None
    notes: str | None = Field(default=None, max_length=2000)


# --- Mode C: Custom HTML Table ---


class TableCustomData(BlockDataSchema):
    """
    Custom HTML Table mode data_json.

    Always sets qa_required flag.
    """

    mode: Literal["custom"] = "custom"
    custom_html: str = Field(max_length=200000)
    custom_css_scoped: str | None = Field(default=None, max_length=50000)
    source_ref: str | None = Field(default=None, max_length=500)


class TableCustomI18n(BlockI18nSchema):
    """Custom HTML Table mode fields_json."""

    caption: str = Field(default="", max_length=500)
    summary: str = Field(default="", max_length=1000)
    notes: str | None = Field(default=None, max_length=2000)


# --- Mode D: Table as Image ---


class TableImageData(BlockDataSchema):
    """Table as Image mode data_json."""

    mode: Literal["image"] = "image"
    asset_id: UUID
    data_download_asset_id: UUID | None = None  # CSV/XLSX for download
    source_ref: str | None = Field(default=None, max_length=500)


class TableImageI18n(BlockI18nSchema):
    """Table as Image mode fields_json."""

    caption: str = Field(default="", max_length=500)
    summary: str = Field(default="", max_length=1000)
    alt_text: str = Field(max_length=500, description="Required for A11Y")
    notes: str | None = Field(default=None, max_length=2000)


# --- Union type for validation ---


TableBlockData = TableBuilderData | TableAdvancedData | TableCustomData | TableImageData
TableBlockI18n = TableBuilderI18n | TableAdvancedI18n | TableCustomI18n | TableImageI18n

